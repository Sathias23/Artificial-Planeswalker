---
baseline_commit: dc47b94ec461057416c8dcbc8bd82a4ad1e6b9d7
---

# Story 2.4: semantic_search_cards Tool (hybrid query)

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a player,
I want a `semantic_search_cards` MCP tool that embeds my natural-language query through the Story 2.1 `Embedder`, runs a `k`-bounded KNN over the Story 2.2/2.3 `card_vec` index, and composes optional relational filters (format-legal, colors, mana-value range, games) into the **same hybrid query** — vec0 metadata pre-filter for `mana_value`/colors, JOIN to `cards` for legality/games/display — so that one call answers *"semantically like Glorybringer, Standard-legal red 4-drops"* and returns ranked, de-duplicated card hits in under ~100 ms,
so that Epic 3's deckbuilding skills (and `find_similar_cards`, Story 2.5) can search by meaning, not just keywords.

## Acceptance Criteria

> Source: [epics.md#Story-2.4](../planning-artifacts/epics.md) (BDD as authored), with implementation-critical clarifications folded in from the real codebase (the **sync-only** `card_vec` seam, the async Epic-1 tool pattern, the `CardSummary` projection, the `cards`/`card_vec` JOIN), the design spec §5/§6, and the RAG de-risk research §A (the two hybrid patterns + over-fetch). **All six must hold simultaneously.**

**AC1 — Natural-language query → embed → top-K nearest cards (FR6)**
- **Given** `semantic_search_cards` with a natural-language `query`
- **When** invoked
- **Then** it embeds the query via the **Story 2.1 `Embedder`** (`embedder.encode(query)` → 384-dim `float32`), serializes it with `sqlite_vec.serialize_float32`, runs a KNN against `card_vec`, and returns the top-K nearest cards as structured hits (each carrying a lightweight `CardSummary` **plus the vec0 `distance`**), ordered nearest-first.
- **🔴 Clarification — query embedding is SYMMETRIC plain `encode`, not `query_embed`.** Story 2.1 deliberately deferred the query-vs-passage decision here. **Decision: use `Embedder.encode` (plain `embed`) for the query — the same path the index builder used for card text** — because the de-risk spike ranked correctly with symmetric `embed()` on both sides ([research §Empirical spike](../planning-artifacts/research/technical-sqlite-vec-fastembed-rag-stack-on-windows-research-2026-06-20.md)). **Do NOT add `query_embed`/`encode_query`** or modify the `Embedder` port — asymmetric query embedding is a Story 2.6 recall-tuning lever if the sanity eval shows weakness, not a 2.4 change.
- **And** the empty/whitespace query is guarded at the tool boundary → `status="invalid"` (do **not** call `encode("")` — it **raises `ValueError`** per the Story 2.1 review hardening).

**AC2 — Mandatory `k`/`LIMIT`, over-fetch before relational filtering (FR16)**
- **Given** any KNN query
- **When** executed
- **Then** it carries a **mandatory `k = ?`** (sqlite-vec [#116] — an unbounded vec0 scan raises) and **over-fetches** `k` (e.g. 100–200) so that JOIN-side relational predicates (legality, games) and the oracle-id de-dup can trim the result set down to the requested `limit` without starving it.
- **🔴 Clarification — the index has EVERY printing; de-dup by `oracle_id` or the user sees the same card many times.** Story 2.3 built one `card_vec` row per **`card_id`** (a Scryfall *printing* UUID), over all 38,232 rows including duplicate printings. Identical composite text across printings ⇒ near-identical vectors ⇒ the raw top-K can be 5–10 printings of the **same** card. **Resolve one hit per `oracle_id` (keep the nearest printing), mirroring how `search_cards` de-dups via `_apply_unique_oracle_filter`.** `card_vec` has no `oracle_id` column, so resolve it from the JOIN to `cards`, then de-dup in Python (the metadata pre-filter is KNN-aware; oracle de-dup is post-fetch — another reason to over-fetch `k`).

**AC3 — Optional relational filters compose into the SAME hybrid query (FR16)**
- **Given** optional `format` (legality), `colors` (+ a `color_mode`), `mana_value_min`/`max`, and `games`
- **When** passed
- **Then** they apply in one hybrid query path serving *"semantically like Glorybringer, Standard-legal red 4-drops"*:
  - **`mana_value` + colors → vec0 metadata pre-filter** (inside the KNN, KNN-aware bitmap *before* distance). Map the requested `mana_value_min/max` → `mana_value BETWEEN ? AND ?` (the column is `int(cmc)` — floor the min / ceil the max when callers pass floats); map each requested color → its `color_{w/u/b/r/g}` flag = 1 in [`COLOR_COLS`](../../src/search/schema.py#L17) order.
  - **format-legality + games + display → JOIN to `cards`** on `card_vec.card_id = cards.id` (post-filter). Reuse the **exact idioms** the async repo already uses: legality via `json_extract(cards.legalities, '$.<format>') = 'legal'` ([card.py:66](../../src/data/repositories/card.py#L66)); games via `cast(cards.games AS TEXT) LIKE '%"<game>"%'` (OR across games) ([card.py:95](../../src/data/repositories/card.py#L95)).
- **🔴 Clarification — canonical shape is the CTE hybrid (Pattern 1 inside, Pattern 2 outside).** Per [research §A](../planning-artifacts/research/technical-sqlite-vec-fastembed-rag-stack-on-windows-research-2026-06-20.md#L124): metadata columns pre-filter **inside** the vec0 KNN; the relational JOIN + arbitrary predicates go **outside** (over-fetch `k` first). Use a CTE:
  ```sql
  WITH knn AS (
      SELECT card_id, distance
      FROM card_vec
      WHERE embedding MATCH :qvec
        AND k = :overfetch_k          -- MANDATORY; over-fetched
        AND mana_value BETWEEN :mvmin AND :mvmax   -- optional metadata pre-filter
        AND color_r = 1                            -- optional metadata pre-filter
  )
  SELECT knn.card_id, knn.distance, c.oracle_id,
         c.name, c.mana_cost, c.cmc, c.type_line, c.oracle_text, c.colors, c.rarity, c.set_code
  FROM knn JOIN cards c ON c.id = knn.card_id
  WHERE json_extract(c.legalities, '$.standard') = 'legal'    -- optional JOIN-side
    AND (cast(c.games AS TEXT) LIKE '%"arena"%')               -- optional JOIN-side
  ORDER BY knn.distance;
  ```
  **De-risk the exact SQL with a 15-min spike first** (the Epic-2 cadence — 2.2/2.3 both did): confirm on the installed `sqlite-vec` v0.1.9 that (a) the metadata pre-filter + `MATCH`/`k` coexist inside the CTE and (b) the outer JOIN + `json_extract`/`LIKE` predicates execute. If the CTE form misbehaves, the documented fallback is a **two-step**: KNN-only query → list of `(card_id, distance)` → a second `SELECT … FROM cards WHERE id IN (…)` for filter+display. Capture whichever works in the Debug Log.

**AC4 — 60k-scale latency < ~100 ms end-to-end (NFR1)**
- **Given** the production ~38k-vector index (NFR1's "60k" envelope)
- **When** a query runs
- **Then** it completes end-to-end in **under ~100 ms** (≈3 ms query embed + brute-force KNN <75 ms + JOIN). Over-fetching `k` to 100–200 is still a single brute-force pass and stays inside the envelope.
- **Clarification:** the unit/integration suites run against tiny seeded indexes where latency is not meaningfully measurable — do **not** assert a hard millisecond bound in tests (it would be flaky). NFR1 is validated by an **optional** real-corpus smoke (note the measured time in the Debug Log), not by a test assertion. [Source: [research §Performance](../planning-artifacts/research/technical-sqlite-vec-fastembed-rag-stack-on-windows-research-2026-06-20.md#L295); NFR1.]

**AC5 — Stateless: format/games (and all filters) are per-call parameters (FR3)**
- **Given** `format`/`games` and the other filters
- **When** passed
- **Then** they are **tool parameters** with no server-side state retained between calls — identical to `search_cards`/`validate_deck` (D5). The tool is self-contained; nothing about the previous query persists.

**AC6 — Driven through the in-process MCP harness; graceful invalid/empty (AC7-lineage)**
- **Given** the in-memory MCP client harness (`create_connected_server_and_client_session`, no subprocess)
- **When** `semantic_search_cards` is driven end-to-end against a DB whose `card_vec` is populated for the seeded cards
- **Then** integration assertions pass: a relevant query returns the expected nearest card(s); a hybrid filter (e.g. `format="standard"`) excludes the non-legal card; an invalid filter value (bad color/game/mana-range/empty-query) returns `status="invalid"` (not a surfaced error, `isError=False`); a valid query with no surviving matches returns `status="empty"` gracefully.

## Tasks / Subtasks

- [x] **Task 0 — De-risk spike: the hybrid CTE SQL on the installed wheel** (AC: 3) — 15 min, throwaway, before writing the tool (mirror the 2.2/2.3 spike discipline)
  - [x] On a `tmp_path` DB via `ConnectionFactory`: `create_card_vec_table` + a tiny `cards` table; insert 3–4 rows with distinct vectors + metadata + JSON `legalities`/`games`/`colors`. Run the **CTE hybrid** from AC3 with a metadata pre-filter inside and `json_extract`/`LIKE` JOIN predicates outside. Confirm it returns the expected rows ordered by distance. Record the exact working SQL (and any sqlite-vec quirk) in the Debug Log. If it fails, capture the two-step fallback instead.

- [x] **Task 1 — Reusable hybrid query infra `src/search/query.py` (NEW)** (AC: 1, 2, 3) — embed-agnostic so Story 2.5 (`find_similar_cards`) reuses it with a seed card's stored vector; pure sync, fully `mypy --strict`-typed, Google docstrings with `Example:`
  - [x] Define a small immutable hit type (e.g. a frozen `@dataclass` `CardHit` or `NamedTuple`): `card_id: str`, `oracle_id: str`, `distance: float`, plus the display columns needed to build a `CardSummary` (`name`, `mana_cost`, `cmc`, `type_line`, `oracle_text`, `colors: list[str]`, `rarity`, `set_code`). Keep it framework-free (no Pydantic in `src/search`).
  - [x] `hybrid_search(conn, query_vector, *, limit=10, over_fetch_k=200, mana_value_min=None, mana_value_max=None, colors=None, color_mode="any", format_legal=None, games=None) -> list[CardHit]`:
    - Accept a **vector** (`NDArray[np.float32]` or list) — NOT a query string — so 2.5 can pass a stored vector. Serialize via `sqlite_vec.serialize_float32` (production serialization already lives in `src/search`, Story 2.3).
    - Build the CTE SQL from **schema constants** (`CARD_VEC_TABLE`, `CARD_ID_COL`, `EMBEDDING_COL`, `MANA_VALUE_COL`, `COLOR_COLS`) — never literal `"card_vec"`/`"color_r"`. Map `color_mode` → flag predicates: `any` = `OR(flag=1)`, `all` = `AND(flag=1)`; (optional parity: `exact` = requested `=1` AND others `=0`; `at_most` = others `=0`). Floor `mana_value_min`/ceil `mana_value_max` to ints. Bind the query vector + every filter as parameters (no f-string interpolation of user values — the `float[N]` dim is the only literal, already handled in `schema.py`).
    - Run on the injected `conn` (a `ConnectionFactory` connection — sqlite-vec loaded). Default tuple row factory (no `sqlite3.Row`) — index rows positionally (Story 2.2 lesson). `json.loads` the `colors` JSON-text column (coerce `None → []`, Story 2.3 lesson).
    - **De-dup by `oracle_id`** (keep the nearest hit per oracle), then **trim to `limit`**. Return `[]` on no matches.
  - [x] Re-export `hybrid_search` (+ `CardHit`) from `src/search/__init__.py` `__all__`; refresh the package docstring (the semantic query path now exists; `find_similar_cards` + the RAG eval remain Stories 2.5–2.6).

- [x] **Task 2 — The tool helper `src/mcp_server/tools/semantic_search.py` (NEW)** (AC: 1, 2, 3, 5, 6) — thin sync wrapper; mirror `card_search.py`'s structured-result + graceful-validation shape (but **sync**, not async, and over `ConnectionFactory`, not `AsyncSession`)
  - [x] `SemanticCardHit(BaseModel)`: `card: CardSummary` + `distance: float` (mirror `DeckCardSummary` wrapping a `CardSummary`). `SemanticSearchResult(BaseModel)`: `status: Literal["ok", "empty", "invalid"]`, `cards: list[SemanticCardHit] = []`, `total_count: int = 0`, `query: str`, `message: str`. Google docstrings on both.
  - [x] `semantic_search_cards(conn, embedder, query, *, colors=None, color_mode="any", mana_value_min=None, mana_value_max=None, format=None, games=None, limit=10) -> SemanticSearchResult`:
    - Validate first (reuse `card_search.py`'s `_VALID_COLORS`/`_VALID_GAMES` vocab + the mana-range/limit checks; **import or replicate** — do not couple to `card_search`'s async internals). Empty/whitespace `query`, bad color, bad game, `mana_value_min > max`, `limit < 1` → `status="invalid"` with the offending value named (never raise). Normalize empty/whitespace `format` → `None` (the `search_cards` guard).
    - `vec = embedder.encode(query)`; `hits = hybrid_search(conn, vec, limit=limit, …filters…)`.
    - Project each `CardHit` → `SemanticCardHit(card=CardSummary(id=…, name=…, mana_cost=…, cmc=…, type_line=…, oracle_text=…, colors=hit.colors, rarity=…, set_code=…), distance=hit.distance)`. (`CardSummary`'s NULL-coercion validators handle null `oracle_text`/`mana_cost`/`colors`.)
    - No hits → `status="empty"` with an adjust-your-query hint; else `status="ok"` with a count + nearest-first summary message.
  - [x] Module docstring; full strict typing; `logger` (`%`-style lazy args); guard clauses over nesting; `import sqlite_vec` only where needed (it lives in `src/search/query.py`, not here).

- [x] **Task 3 — Register the tool + inject the sync seams in `src/mcp_server/server.py`** (AC: 1, 5, 6)
  - [x] Extend `build_server(session_factory=None, connection_factory=None, embedder=None)`: add `connection_factory: ConnectionFactory | None = None` (default `ConnectionFactory()` — resolves the **same** DB file as the async engine via `CARDS_DATABASE_URL`/`./data/cards.db`, single-file topology D2) and `embedder: Embedder | None = None` (test seam; **do NOT** call `get_embedder()` at build time — preserve the lazy-load boundary). Keep the existing async tools untouched.
  - [x] Register `semantic_search_cards` as a **sync `@mcp.tool()`** (plain `def`, FastMCP threadpools it — the original project-context "tools are sync `def`" guidance + NFR6 "connection per worker thread"). Inside: `conn = connection_factory.get_connection()` (per-thread, lazily built); `emb = embedder if embedder is not None else get_embedder()` (lazy singleton in production, injected fake in tests); `return _semantic_search_helper(conn, emb, query, …)`. The LLM-facing docstring describes the NL query + each filter + the "one call" hybrid example, and states statelessness (pass filters every call).
  - [x] **Verify FastMCP hosts a sync tool alongside the async Epic-1 tools** (it does — it inspects each callable; sync tools run in the anyio worker threadpool). Note it in Completion Notes.

- [x] **Task 4 — Test infra: a `card_vec`-populated DB fixture** (AC: 6) — the existing `seeded_card_db` builds `cards` via the **async engine only** and has **no `card_vec`**; close that gap without breaking the 8+ tests that use it
  - [x] Add a **new** fixture (e.g. `seeded_vec_db` in `tests/integration/conftest.py` or the new test module) that yields both an async `session_factory` **and** a `ConnectionFactory`: seed a richer `cards` set (distinct enough for semantic ranking + spanning colors/mana/format/**games** — the 3-card `seeded_card_db` is too sparse and omits `games`, [deferred-1.6 note](./deferred-work.md)); then on a `ConnectionFactory(db_path=<same file>)` run `create_card_vec_table` + `create_card_embedding_meta_table` + `build_card_embeddings(conn, embedder)` so `card_vec` is populated for those exact cards. Commit the async seed **before** building vectors (WAL cross-connection visibility — the sync conn reads committed `cards`).
  - [x] Provide a **deterministic fake `Embedder`** (one-hot/basis 384-dim `float32` per distinct text, like [`test_index_builder`'s fake](./2-3-card-embedding-index-builder-idempotent-incremental.md)) for fast offline tests, used for **both** the index build and the query — so KNN is meaningful without a model download. Reserve the **real** `get_embedder()` for the one `@pytest.mark.integration` ranking test.

- [x] **Task 5 — Tests** (AC: 1, 2, 3, 5, 6)
  - [x] **`tests/unit/search/test_query.py` (NEW)** — drive `hybrid_search` directly on a tmp `card_vec` (real sqlite-vec) populated with fake-embedder vectors (so this is a **unit** test, not `integration` — like `test_schema.py`/`test_index_builder.py`): mandatory-`k` present; metadata pre-filter (mana range + color flag) excludes off-filter cards; JOIN-side legality/games predicates trim correctly; **oracle de-dup** keeps one hit per oracle when multiple printings are indexed; `limit` caps results; no-match → `[]`. `tmp_path` + `factory.close()` teardown; no `/tmp`.
  - [x] **`tests/integration/mcp_server/test_semantic_search_tool.py` (NEW)** — helper-level via `semantic_search_cards(conn, fake_embedder, …)`: status `ok`/`empty`/`invalid` paths; filters compose; `CardSummary` projection omits heavy fields; each hit carries a `distance`. Plus **one `@pytest.mark.integration`** test with the **real** embedder: seed a few distinctive cards (e.g. a red flying dragon, a counterspell, a green elf), build real vectors, query *"flying red dragon that deals damage"* → assert the dragon ranks first (honest semantic ranking; precursor to Story 2.6's eval).
  - [x] **`tests/integration/test_mcp_tools.py` (MODIFIED)** — add one end-to-end `semantic_search_cards` through the in-process MCP client using the new `seeded_vec_db` fixture + `build_server(session_factory=…, connection_factory=…, embedder=fake)`: a relevant query returns `status="ok"` with the expected nearest card; `format="standard"` excludes the non-legal card (hybrid filter through the wire); a bad color returns `status="invalid"`, `isError=False`.
  - [x] *(If unit placement is awkward because the query test needs a `cards` table too, place it under `tests/integration/search/` instead — but with a fake embedder it remains fast/offline; keep it out of the `integration` marker unless it loads the real model.)*

- [x] **Task 6 — Verify (run the commands, capture output)** (AC: all)
  - [x] `uv run pytest tests/unit/search/test_query.py tests/integration/mcp_server/test_semantic_search_tool.py -m "not integration" -v` → new tests pass (fast, offline, real sqlite-vec + fake embedder).
  - [x] `uv run pytest tests/integration/mcp_server/test_semantic_search_tool.py -m integration -v` → the real-embedder ranking test passes (uses the cached `bge-small-en-v1.5` from Stories 2.1/2.3).
  - [x] `uv run pytest tests/ -m "not integration"` → full active suite still green (baseline **477 passed** after Story 2.3 — keep it green, NFR7).
  - [x] `uv run ruff check .` and `uv run ruff format --check .` → clean for story-authored files (`src/search/query.py`, `src/search/__init__.py`, `src/mcp_server/tools/semantic_search.py`, `src/mcp_server/server.py`, the new/modified tests). Don't reformat pre-existing unrelated issues.
  - [x] `uv run mypy src/` → clean. `uv run pre-commit run mypy --all-files` too (the isolated env already has `mcp`+`numpy` from Stories 2.1; `sqlite_vec` is stub-less under `ignore_missing_imports` → **no new `additional_dependencies`**).
  - [x] **Optional real-corpus smoke (AC4):** with the real `./data/cards.db` (38,232-vector index already built by Story 2.3), drive `semantic_search_cards` for *"flying red dragon"* and for the *"Standard-legal red 4-drops like Glorybringer"* hybrid; confirm sensible hits and note the measured end-to-end time (expect <~100 ms) in the Debug Log. Do not assert it in a test.

## Dev Notes

### What this story IS — and is NOT

- **IS:** the **first serve-time consumer of the vector index** — a reusable sync hybrid-query infra function `src/search/query.py::hybrid_search(conn, vector, …)` (KNN + vec0 metadata pre-filter + JOIN-to-`cards` legality/games/display + oracle de-dup + over-fetch/limit), a thin sync tool `src/mcp_server/tools/semantic_search.py` that validates → embeds the query → calls `hybrid_search` → projects to a `SemanticSearchResult`, the `build_server` wiring of the **sync** `ConnectionFactory` + `Embedder` seams, the `card_vec`-populated test fixture, and the tests. This realizes spec §6's "one call" hybrid promise (FR6/FR16). It is the **fifth** `src/search` sibling after `ConnectionFactory` (1.2), `Embedder` (2.1), `card_vec` schema (2.2), and the index builder (2.3) — same thin/injected/typed/scope-disciplined shape those four reviews rewarded.
- **IS NOT:** `find_similar_cards` (Story 2.5) or the RAG sanity eval (Story 2.6). **Design `hybrid_search` to take a vector** (so 2.5 fetches a seed card's stored `card_vec` vector and calls the same function) — but **do not** build 2.5's tool, the seed-vector fetch, the self-exclusion logic, or the eval here. **Do not** modify `Embedder`, the `card_vec` schema, or the index builder (the 2.1/2.2/2.3 ports are frozen). **Do not** add `query_embed`/`encode_query`, set `distance_metric=cosine`, or build full pagination (KNN is top-K, not paged). Resist scaffolding ahead — the Epic-2 cadence (embedder → schema → builder → **semantic tool** → similar tool → eval) is deliberate.

### 🔴 The defining architectural decision: this tool is SYNC (the Epic-1 tools are async)

The Epic-1 tools are `async def` and `await` the async `src/data` repositories on the FastMCP event loop (a documented deviation, D-1.3a, *because they wrap async repos*). **`semantic_search_cards` is fundamentally different: the vector index is reachable only on the SYNC `ConnectionFactory` connection.** `card_vec` + `sqlite-vec` are loaded **only** by `ConnectionFactory` ([connection.py](../../src/search/connection.py)); the async aiosqlite engine never calls `enable_load_extension`/`sqlite_vec.load`, so `card_vec` is invisible to it (`no such module: vec0`). Therefore:

- **Register `semantic_search_cards` as a plain sync `def` `@mcp.tool()`.** FastMCP runs sync tools in its **anyio worker threadpool** — exactly the NFR6 model: *connection per worker thread* (`ConnectionFactory.get_connection()` is `threading.local`, so each pool thread lazily gets its own sqlite-vec connection) + *embedding model as a process-lifetime singleton* (`get_embedder()`). No `asyncio.to_thread`, no event-loop blocking, no async repo. This returns to the **original** project-context guidance ("Define tools as sync `def` — FastMCP runs them in a threadpool") that Epic 1 had to set aside.
- **No `AsyncSession` is needed.** Because `card_vec` and `cards` share **one SQLite file** (D2), the sync connection sees `cards` too — so legality/games/display all resolve via a JOIN in the *same* sync query. Re-implement the legality/games predicates as raw SQL (the repo's `json_extract`/`LIKE` idioms) rather than reaching back into the async `CardRepository`.
- **FastMCP hosts mixed sync+async tools fine** — it inspects each registered callable. Confirm with the in-process harness (Task 5).

> If a future constraint forces an async registration, the fallback is `async def` + `await asyncio.to_thread(_run)` where `_run` does `conn = connection_factory.get_connection(); …` on the worker thread. Prefer the plain sync tool — it is simpler and the established NFR6 design.

### 🔴 The hybrid query path — CTE: metadata pre-filter inside, relational JOIN outside (research §A)

[Research §A](../planning-artifacts/research/technical-sqlite-vec-fastembed-rag-stack-on-windows-research-2026-06-20.md#L124) validated §6's headline example with a **two-pattern hybrid**, and it maps 1:1 onto the Story 2.2 schema:

- **Pattern 1 (pre-filter, fastest) — `mana_value` + the 5 color flags** are vec0 **metadata columns**; put them in the KNN `WHERE` so sqlite-vec applies a KNN-aware bitmap *before* distance. These are the only filterable in-vec0 columns.
- **Pattern 2 (post-filter, flexible) — format-legality, games, and all display fields** resolve via **JOIN** to `cards` *outside* the KNN. Because the KNN returns its `k` first, **over-fetch `k` (100–200)** so the JOIN-side trim + oracle de-dup don't starve the `limit`.

Canonical shape is the **CTE** in AC3 (KNN in the CTE with metadata filters; JOIN + `json_extract`/`LIKE` predicates outside, `ORDER BY knn.distance`). **Spike it first** (Task 0) on `sqlite-vec` v0.1.9 — confirm the metadata filter + `MATCH`/`k` coexist in the CTE and the outer JOIN predicates run; record the exact SQL. The Story 2.2 test already proved a **direct** `card_vec JOIN cards … WHERE embedding MATCH ? AND k=?` works ([test_schema.py JOIN test](../../tests/unit/search/test_schema.py)), so the JOIN itself is fine; the open question the spike closes is layering the *outer* relational predicates + metadata pre-filter together. Two-step fallback (KNN-only → `cards WHERE id IN (…)`) documented in AC3 if needed.

Mandatory `k`/`LIMIT` on every KNN ([#116]) — never emit an unbounded vec0 scan (perf cliff + raises). Keep the **default L2** distance from Story 2.2 (ranking-equivalent to cosine for the L2-normalized bge vectors); return the raw `distance` for caller relevance signal — do **not** convert to cosine (a 2.6 tuning concern).

### 🔴 De-dup by oracle_id — or the user sees ten copies of one card

The index is keyed by **printing** (`card_id` = `cards.id`, a per-printing UUID); Story 2.3 embedded **all 38,232 rows**. Many printings share identical composite text (`name + type_line + mana_cost + oracle_text + keywords`) ⇒ identical vectors ⇒ the raw top-K is dominated by duplicate printings of the same card. `search_cards`/`lookup` already de-dup via `_apply_unique_oracle_filter` (one row per `oracle_id`). Mirror that here: select `c.oracle_id` in the JOIN, keep the **nearest** hit per `oracle_id` in Python, then trim to `limit`. This is another reason over-fetch `k` must be generous (de-dup happens *after* the KNN). `card_vec` has no `oracle_id` (Story 2.2 kept it minimal), so it must come from the JOIN — do not try to add it to `card_vec` (can't `ALTER` a `vec0` table; out of scope).

### Result shape — top-K hits with distance, reusing CardSummary

- Return `SemanticSearchResult { status, cards: list[SemanticCardHit], total_count, query, message }`, mirroring `CardSearchResult`'s graceful `ok`/`empty`/`invalid` contract. Each `SemanticCardHit` = `{ card: CardSummary, distance: float }` (wrap `CardSummary`, like `DeckCardSummary` does — keeps the lightweight projection that omits `legalities`/`image_uris`/`card_faces`, [card.py:82](../../src/data/schemas/card.py#L82)).
- **Top-K (a `limit` param, default ~10, sane max ~50), NOT pagination.** KNN returns nearest-first by distance; paging a KNN is awkward and the epic says "top-K nearest". Building `CardSummary` from raw sqlite3 rows: the `colors` column comes back as JSON **text** (`'["R"]'`) → `json.loads` (coerce `None → []`); `CardSummary`'s `@field_validator`s coerce null `oracle_text`/`mana_cost`. (Be aware of the pre-existing [`CardSummary` nullability deferral](./deferred-work.md) — the coercion validators already handle the NULL cases this tool will hit on real data.)

### Validation & filter semantics (graceful, mirror search_cards)

- **Reuse the vocab + checks** from [`card_search.py`](../../src/mcp_server/tools/card_search.py#L53): `_VALID_COLORS = {W,U,B,R,G}`, `_VALID_GAMES = {paper,arena,mtgo}`, mana-range (`min ≤ max`, both `≥ 0`), `limit ≥ 1`. Add an **empty-query guard** (whitespace-only `query` → `invalid`; never call `encode("")`, which raises). Normalize empty/whitespace `format` → `None` (the existing `search_cards` guard against a malformed `json_extract` path).
- **Colors → flags:** map each requested color to its `color_{w/u/b/r/g}` flag via `COLOR_COLS` order. Support at least `color_mode` `"any"` (OR over flags, default) and `"all"` (AND). Optional parity with `search_cards`: `"exact"` (requested `=1` AND the rest `=0`) and `"at_most"` (the rest `=0`) are cheap over 5 boolean cols — add them if it stays clean, else flag for a polish pass. Keep `"any"` the default (the Glorybringer example is single-color).
- **Mana range → `BETWEEN`:** `mana_value` is `int(cmc)`. Floor `mana_value_min`/ceil `mana_value_max` to ints before binding (the [2.2-deferred float-vs-int note](./deferred-work.md) — `WHERE mana_value = 4` won't match a `4.0`, but here both column and bind are ints).

### Test infra — the real lift of this story (don't underestimate Task 4)

The shared `seeded_card_db` fixture ([conftest.py](../../tests/integration/conftest.py)) builds `cards` via the **async engine + `init_database`** only — it does **not** create `card_vec` (needs the sync `ConnectionFactory` + sqlite-vec) and does **not** populate vectors. So semantic-search tests need a DB with **both** the relational rows **and** a populated `card_vec`. The new fixture:
1. File-backed DB; seed a richer `cards` set (distinct texts for ranking, spanning colors/mana/format, **with `games`** — the 3-card fixture omits games) via the async engine; **commit**.
2. `ConnectionFactory(db_path=<same file>)` → `create_card_vec_table` + `create_card_embedding_meta_table` → `build_card_embeddings(conn, fake_embedder)` (reuse the Story 2.3 builder — it's the supported population path; don't hand-roll inserts).
3. Yield `(session_factory, connection_factory)`; `build_server(session_factory=…, connection_factory=…, embedder=fake_embedder)`.

**Embedder in tests:** use a deterministic **fake** (one-hot/basis vectors per distinct text, exactly like the [Story 2.3 builder tests](./2-3-card-embedding-index-builder-idempotent-incremental.md)) for **both** index build and query in the fast suite — so KNN ranking is deterministic with no model download. Reserve **one** `@pytest.mark.integration` test for the **real** `get_embedder()` (cached model from 2.1/2.3) to prove genuine semantic ranking. This mirrors the unit/integration split every prior `src/search` story used.

WAL note: the async engine and the sync `ConnectionFactory` are two connections to the same file. With WAL, the sync connection reads the async-committed `cards` only after that commit — so **commit the seed before building/querying vectors** (the fixture already does, step 1 → step 2).

### Anti-patterns (do NOT do these)

- ❌ Reach for the async `CardRepository`/`AsyncSession` to resolve legality/display — `card_vec` is **sync-only**; do the JOIN in raw SQL on the `ConnectionFactory` connection (same file, D2).
- ❌ Register the tool `async def` and `await` the sqlite-vec work on the loop — make it a **sync `def`** tool (FastMCP threadpools it; per-thread connection; embedder singleton). Async-blocking the loop on a KNN is the wrong model.
- ❌ Call `get_embedder()` at `build_server` time — keep the lazy boundary; resolve the embedder inside the tool (or via the injected override).
- ❌ Emit a KNN without `k`/`LIMIT` — mandatory on `vec0` ([#116]); unbounded = perf cliff + raises.
- ❌ Forget to **over-fetch `k`** — JOIN-side legality/games + oracle de-dup trim post-KNN; a tight `k` starves the result.
- ❌ Skip oracle de-dup — the index has every printing; identical text ⇒ duplicate vectors ⇒ the user sees the same card N times.
- ❌ Add `query_embed`/`encode_query`, modify `Embedder`, change the `card_vec` schema, or set `distance_metric=cosine` — frozen ports; symmetric `encode` + default L2 are proven.
- ❌ Call `encode("")` — it raises `ValueError` (Story 2.1 hardening); guard the empty query → `status="invalid"`.
- ❌ Interpolate user filter values into SQL strings — bind them as parameters (the `float[N]` dim is the only literal, handled in `schema.py`).
- ❌ Hardcode `"card_vec"`/`"color_r"`/`384` — use `CARD_VEC_TABLE`/`COLOR_COLS`/`EMBEDDING_DIM` constants (the schema's single source of truth).
- ❌ Build `card_vec` rows by hand in the test fixture — call `build_card_embeddings` (the supported, tested population path).
- ❌ Index `sqlite3.Row` by column name — `ConnectionFactory` connections use the default **tuple** row factory; index positionally (Story 2.2 lesson). Use `tmp_path`, never `/tmp`; `factory.close()` teardown.
- ❌ Assert a hard latency bound in tests — tiny indexes make it flaky; NFR1 is an optional real-corpus smoke note.
- ❌ Break the existing `seeded_card_db` fixture (8+ tests depend on it) — add a **new** fixture for the vector-populated DB.
- ❌ Build `find_similar_cards`, the seed-vector fetch, self-exclusion, or the RAG eval — Stories 2.5–2.6. Build `hybrid_search` to *accept a vector* so 2.5 reuses it; stop there.

### Previous Story Intelligence (2.3 + 2.2 + 2.1 + Epic-1 tool pattern — the direct templates)

- **Story 2.3 handed you** the populated index + reusable bits: `build_card_embeddings(conn, embedder)` (use it to populate the test fixture's `card_vec`), `compose_card_text`/`content_hash`, the `serialize_float32` production boundary now in `src/search`, and the fake-embedder + tmp-vec-DB unit-test pattern ([`test_index_builder.py`](../../tests/unit/search/test_index_builder.py)). The real `./data/cards.db` already holds a **complete 38,232-vector index** — your AC4 smoke runs against it directly. [Source: [2-3 Dev Agent Record](./2-3-card-embedding-index-builder-idempotent-incremental.md).]
- **Story 2.2 handed you** the schema constants (`CARD_VEC_TABLE`, `CARD_ID_COL`, `EMBEDDING_COL`, `MANA_VALUE_COL`, `COLOR_COLS`, `METADATA_COLS`) — build the SQL from these — the **TEXT** `card_id` PK (= `cards.id` UUID, JOIN is text=text), the metadata-vs-JOIN split, default L2, and the **proven `card_vec JOIN cards` KNN test** to extend. [Source: [2-2](./2-2-card-vec-schema-with-metadata-columns.md); [schema.py](../../src/search/schema.py).]
- **Story 2.1 handed you** `get_embedder()` singleton + `Embedder.encode(text) -> NDArray[float32]` (symmetric query path) and `EMBEDDING_DIM`; `encode("")` **raises** (guard it). [Source: [2-1](./2-1-embedder-port-fastembed-singleton-persistent-cache.md); [embedder.py](../../src/search/embedder.py).]
- **Epic-1 tool pattern to mirror (structure, not async-ness):** `card_search.py` is the closest template — `_VALID_*` vocab, `_validation_error` returning `status="invalid"`, a Pydantic result with `ok/empty/invalid`, and a thin helper the `server.py` `@mcp.tool()` wraps. Reuse that *shape*; swap async/`AsyncSession`/repo → sync/`ConnectionFactory`/raw-SQL. The in-process MCP harness ([test_mcp_tools.py](../../tests/integration/test_mcp_tools.py)) is the end-to-end test vehicle. [Source: [card_search.py](../../src/mcp_server/tools/card_search.py); [server.py](../../src/mcp_server/server.py).]
- **Recurring review findings to pre-empt:** Google-style `Example:` on every public function; `tmp_path` not `/tmp`; `factory.close()` teardown; let `ConnectionFactory` resolve paths (no CWD-relative re-derivation); positional row indexing on `ConnectionFactory` connections. [Source: [2-1/2-2 reviews](./deferred-work.md).]
- **Baseline green at 477 passed** (`-m "not integration"`) after Story 2.3; `legacy/` excluded. Keep it green (NFR7).

### Git Intelligence

- HEAD `dc47b94` "feat: add card embedding index builder …" closed Story 2.3; `1d2b7a2`/`921545d`/`6ebcdf3` were 2.2/2.1. The Epic-2 cadence is firm: thin `src/search` unit (or thin MCP tool) → focused fake-embedder + real-sqlite-vec tests → run-and-capture verify → strict scope discipline. This is the next link (embedder → schema → builder → **semantic tool** → similar tool → eval).
- `src/search/` holds `connection.py` + `embedder.py` + `schema.py` + `index_builder.py` (+ `__init__.py`); `query.py` is **green-field** within it. `src/mcp_server/tools/` has `card_lookup.py`/`card_search.py`/`deck_management.py`/`deck_analysis.py`/`bug_report.py`; `semantic_search.py` joins them as the **first sync** tool helper. `server.py` gains a 13th tool + two injected seams. [Source: `git log`; [src/search/](../../src/search/); [src/mcp_server/tools/](../../src/mcp_server/tools/).]
- Working tree is clean at this baseline — no incidental edits expected beyond the story's File List.

### Latest Tech / Versions (verified for THIS project, 2026-06-21)

| Item | Value | Source |
|---|---|---|
| Hybrid query | CTE: metadata pre-filter inside the `vec0` KNN, relational JOIN + `json_extract`/`LIKE` outside; **over-fetch `k`** | [research §A](../planning-artifacts/research/technical-sqlite-vec-fastembed-rag-stack-on-windows-research-2026-06-20.md#L124) |
| `sqlite-vec` | v0.1.9 (bundled); **`k`/`LIMIT` mandatory** ([#116]); aux `+col` not filterable ([#121]); JOIN filtering ([#196]) | [research §A](../planning-artifacts/research/technical-sqlite-vec-fastembed-rag-stack-on-windows-research-2026-06-20.md); [test_schema.py](../../tests/unit/search/test_schema.py) |
| KNN+JOIN proven | `card_vec JOIN cards ON c.id = v.card_id WHERE embedding MATCH ? AND k = ?` works on the installed wheel | [test_schema.py](../../tests/unit/search/test_schema.py) (Story 2.2) |
| `Embedder` | `get_embedder()` singleton + `encode(text) -> NDArray[float32]`; `encode("")` raises | [embedder.py](../../src/search/embedder.py) |
| Serialization | `sqlite_vec.serialize_float32(list\|ndarray) -> BLOB` — production, lives in `src/search` | Story 2.3; [research §B](../planning-artifacts/research/technical-sqlite-vec-fastembed-rag-stack-on-windows-research-2026-06-20.md) |
| Legality / games SQL | `json_extract(legalities,'$.<fmt>')='legal'`; `cast(games AS TEXT) LIKE '%"<g>"%'` | [card.py:66,95](../../src/data/repositories/card.py#L66) |
| FastMCP tools | both sync + async supported; sync run in the anyio threadpool (per-thread conn) | [server.py](../../src/mcp_server/server.py); project-context.md NFR6 |
| Index | real `./data/cards.db`: **38,232** vectors built (Story 2.3); query embed ~3 ms, KNN <75 ms | [2-3 Debug Log](./2-3-card-embedding-index-builder-idempotent-incremental.md); [research §Performance](../planning-artifacts/research/technical-sqlite-vec-fastembed-rag-stack-on-windows-research-2026-06-20.md#L295) |
| Python / SQLite | CPython 3.12.13 / SQLite 3.50.4 / Windows / uv | [project-context.md](../project-context.md) |

### Project Structure Notes

Target additions (everything else unchanged):

```
src/
  search/
    __init__.py        # MODIFIED — re-export hybrid_search (+ CardHit)
    connection.py      # (unchanged, Story 1.2) — the sync sqlite-vec connection the tool queries on
    embedder.py        # (unchanged, Story 2.1) — get_embedder() + encode() for the query vector
    schema.py          # (unchanged, Story 2.2) — CARD_VEC_TABLE/COLOR_COLS/… constants to build the SQL from
    index_builder.py   # (unchanged, Story 2.3) — build_card_embeddings(): populates card_vec in the test fixture
    query.py           # NEW — hybrid_search(conn, vector, *, filters, k, limit) -> list[CardHit] (embed-agnostic; 2.5 reuses)
  mcp_server/
    server.py          # MODIFIED — build_server(+connection_factory, +embedder); register sync semantic_search_cards tool
    tools/
      semantic_search.py  # NEW — SemanticSearchResult/SemanticCardHit + semantic_search_cards(conn, embedder, query, …) (sync)
tests/
  unit/
    search/
      test_query.py       # NEW — hybrid_search: filters, over-fetch+oracle-dedup, mandatory k, empty (fake embedder, real sqlite-vec)
  integration/
    conftest.py           # MODIFIED (or new module fixture) — seeded_vec_db: cards + populated card_vec + ConnectionFactory
    test_mcp_tools.py      # MODIFIED — one end-to-end semantic_search_cards through the in-process MCP client
    mcp_server/
      test_semantic_search_tool.py  # NEW — helper-level (fake) + one @pytest.mark.integration real-embedder ranking test
```

- **Alignment:** matches spec §5 (tool catalog: `semantic_search_cards` *(new)*, hybrid) + §6 (hybrid query path) and research roadmap step 3 ("add `semantic_search_cards` … over-fetch `k`, then JOIN/filter"). FR6/FR16; D2 single-file; D5 statelessness. [Source: [spec §5/§6](../../docs/superpowers/specs/2026-06-20-mcp-server-architecture-design.md); [research §8/§A](../planning-artifacts/research/technical-sqlite-vec-fastembed-rag-stack-on-windows-research-2026-06-20.md).]
- **Layering check:** `src/search/query.py` is sync infra consumed downward by `src/mcp_server/tools/semantic_search.py` (and Story 2.5) — no upward import, no cycle. The tool layer projects to Pydantic; `src/search` stays framework-free. ✅
- **No new dependencies / no `pyproject.toml` or `.pre-commit-config.yaml` changes** — `sqlite-vec`, `fastembed`, `numpy`, `mcp` are already core; the pre-commit mypy env already resolves them.

### References

- [epics.md — Epic 2 / Story 2.4](../planning-artifacts/epics.md) — user story + the six BDD ACs (embed→top-K; mandatory `k`/over-fetch; hybrid filters in one query; <100 ms; stateless params; in-memory harness).
- [design spec §5 / §6](../../docs/superpowers/specs/2026-06-20-mcp-server-architecture-design.md) — tool catalog (`semantic_search_cards` hybrid), the "one call" Glorybringer example, RAG hybrid query path, D5 statelessness, D2 single-file.
- [research §A (hybrid patterns + over-fetch) / §Performance / §8](../planning-artifacts/research/technical-sqlite-vec-fastembed-rag-stack-on-windows-research-2026-06-20.md) — Pattern 1 (metadata pre-filter) + Pattern 2 (JOIN post-filter), mandatory `k`, over-fetch `k` 100–200, <100 ms envelope, roadmap step 3.
- [src/search/schema.py](../../src/search/schema.py) — `CARD_VEC_TABLE`/`CARD_ID_COL`/`EMBEDDING_COL`/`MANA_VALUE_COL`/`COLOR_COLS`/`METADATA_COLS` to build the SQL from; TEXT-PK JOIN alignment; default L2.
- [src/search/embedder.py](../../src/search/embedder.py) — `get_embedder()` + `encode()` (symmetric query embedding); `encode("")` raises.
- [src/search/index_builder.py](../../src/search/index_builder.py) — `build_card_embeddings` (populate the test `card_vec`); `serialize_float32` production boundary; `_color_flags`/`_coerce_json_list` helpers to mirror.
- [src/search/connection.py](../../src/search/connection.py) — the sync `ConnectionFactory` (sqlite-vec + WAL + per-thread) the tool queries on; tuple row factory.
- [src/mcp_server/tools/card_search.py](../../src/mcp_server/tools/card_search.py) — the structured-result + graceful-validation **shape** to mirror (`_VALID_*`, `status` ok/empty/invalid, thin helper).
- [src/mcp_server/server.py](../../src/mcp_server/server.py) — `build_server` injection pattern (`session_factory`) to extend with `connection_factory`/`embedder`; `@mcp.tool()` registration; async vs the new sync tool.
- [src/data/repositories/card.py](../../src/data/repositories/card.py) — `_apply_format_filter` (`json_extract`) + `_apply_games_filter` (`LIKE`) + `_apply_unique_oracle_filter` idioms to re-implement in raw SQL.
- [src/data/schemas/card.py](../../src/data/schemas/card.py) — `CardSummary` projection (omits heavy fields; NULL-coercion validators) to build hits from.
- [tests/integration/test_mcp_tools.py](../../tests/integration/test_mcp_tools.py) / [tests/integration/conftest.py](../../tests/integration/conftest.py) — the in-process MCP harness + `seeded_card_db` (extend with a `card_vec`-populated fixture).
- [tests/unit/search/test_index_builder.py](../../tests/unit/search/test_index_builder.py) / [test_schema.py](../../tests/unit/search/test_schema.py) — fake-embedder + real-sqlite-vec unit-test style and the proven KNN+JOIN test to extend.
- [Story 2.3](./2-3-card-embedding-index-builder-idempotent-incremental.md) / [2.2](./2-2-card-vec-schema-with-metadata-columns.md) / [2.1](./2-1-embedder-port-fastembed-singleton-persistent-cache.md) — the index/schema/embedder this tool consumes; deferrals + recurring review findings.
- [project-context.md](../project-context.md) — RAG/MCP rules (every KNN needs `k`/`LIMIT`; over-fetch then JOIN-filter; metadata cols; sync MCP tools threadpooled with per-thread connections + singleton embedder; stateless tools; testing layout; ruff/mypy gates).
- [deferred-work.md](./deferred-work.md) — relevant pre-existing items: `CardSummary` nullability, `seeded_card_db` omits `games`, `mana_value` int-vs-float.

## Dev Agent Record

### Agent Model Used

claude-opus-4-8[1m] (Opus 4.8, 1M context) — BMAD dev-story workflow.

### Debug Log References

**Task 0 — Hybrid CTE de-risk spike (2026-06-22, throwaway `_spike_hybrid_cte.py`, deleted after run).**
Confirmed the **canonical AC3 CTE hybrid works as-authored** on the installed `sqlite-vec` v0.1.9 — no two-step fallback needed. Working shape (positional `?` binds, matching the codebase idiom):

```sql
WITH knn AS (
    SELECT card_id, distance
    FROM card_vec
    WHERE embedding MATCH ?            -- serialized query vector
      AND k = ?                        -- MANDATORY, over-fetched
      AND mana_value BETWEEN ? AND ?   -- optional metadata pre-filter (inside KNN)
      AND color_r = 1                  -- optional metadata pre-filter (inside KNN)
)
SELECT knn.card_id, knn.distance, c.oracle_id, c.name, c.colors
FROM knn JOIN cards c ON c.id = knn.card_id
WHERE json_extract(c.legalities, '$.standard') = 'legal'   -- optional JOIN-side post-filter
  AND (cast(c.games AS TEXT) LIKE ?)                        -- optional JOIN-side post-filter ('%"arena"%')
ORDER BY knn.distance
```

Verified with 4 synthetic cards (distinct one-hot vectors): the metadata pre-filter (`mana_value BETWEEN` + `color_r=1`) excludes the off-color card *inside* the KNN; the outer `json_extract` legality and `cast(games AS TEXT) LIKE` predicates each independently trim a row; results are ordered nearest-first by `knn.distance`. Removing the games predicate restores the paper-only card (proving the predicate is the filter), and a query nearest a different basis re-orders correctly. **Decision: implement the CTE form (no fallback).** Follow-up confirmed in `query.py`: the `json_extract` JSON-path and the `games` LIKE pattern can be **bound as parameters** (not interpolated) — a malformed path simply no-matches rather than raising — so **zero user values are f-string-interpolated into SQL** (only schema-constant identifiers are).

**Task 6 — AC4 real-corpus latency smoke (2026-06-22, throwaway `_smoke_ac4.py`, deleted after run).**
Drove `semantic_search_cards` against the real `./data/cards.db` (**38,232**-vector index, Story 2.3) with the real `get_embedder()` (singleton warmed first, so the model load is excluded from the per-query timings). End-to-end (query embed + KNN over-fetch k=200 + JOIN + oracle de-dup), `limit=5`:

| Query | Filters | Status | End-to-end |
|---|---|---|---|
| "flying red dragon that deals damage" | none | ok (5) | **51.4 ms** |
| "Standard-legal red four-drops like Glorybringer" | colors=[R], mana 4–4, format=standard | ok (5) | **40.6 ms** |

Both comfortably **under the ~100 ms NFR1 envelope**. The plain query returns red Dragons nearest-first (Red Dragon @ 0.510, Wrathful Red Dragon, Shockmaw Dragon, …); the hybrid query returns only **red, cmc-4, Standard-legal** cards — the metadata pre-filter + legality JOIN both demonstrably applied on real data. (Relevance is "sensible, not perfect" for the literal-text Glorybringer phrasing — the quantized-model recall tuning + sanity eval are explicitly Story 2.6, per the design.) No millisecond bound is asserted in any test (tiny seeded indexes make it flaky — NFR1 is this optional smoke).

### Completion Notes List

- **The defining decision held: `semantic_search_cards` is a SYNC `def` `@mcp.tool()`.** FastMCP hosts it in its anyio worker threadpool alongside the 12 async Epic-1 tools — verified end-to-end through the in-process MCP client (`test_semantic_search_sync_tool_is_hosted_alongside_async` asserts both the sync tool and the async tools are in `list_tools`). Per-thread sqlite-vec connection via `ConnectionFactory.get_connection()` (NFR6); the embedder is the injected test seam or the lazily-built `get_embedder()` singleton — **never loaded at `build_server` time** (the lazy boundary is preserved).
- **Reusable, embed-agnostic `src/search/query.py::hybrid_search(conn, vector, …)`** is the heart of the story — it takes a *vector*, not a query string, so Story 2.5 (`find_similar_cards`) can pass a seed card's stored vector and reuse it unchanged. It builds the CTE SQL purely from schema constants (`CARD_VEC_TABLE` / `COLOR_COLS` / `MANA_VALUE_COL` / …), binds every filter as a parameter, over-fetches `k=200`, applies oracle-id de-dup in Python (nearest printing kept), then trims to `limit`. Returns framework-free `CardHit` dataclasses (no Pydantic in `src/search`).
- **Hybrid query path = research §A two-pattern split:** `mana_value` + the five `color_*` flags pre-filter *inside* the vec0 KNN (KNN-aware bitmap); format-legality (`json_extract`) + games (`cast … LIKE`) + all display fields resolve via the JOIN to `cards` *outside*. `color_mode` supports all four `search_cards` semantics (`any`/`all`/`exact`/`at_most`); float mana bounds are floored/ceiled to the int column.
- **Oracle de-dup is essential and tested** — the index has every printing (38,232 rows), so without it the top-K is dominated by duplicate printings of one card. `hybrid_search` keeps the nearest hit per `oracle_id`; `test_oracle_dedup_keeps_one_hit_per_oracle` proves two identical-text printings collapse to one.
- **Graceful `ok`/`empty`/`invalid` contract mirrors `card_search.py`** (replicated the colour/games vocab rather than coupling to the async module). The **empty-query guard** catches whitespace at the boundary so `encode("")` (which raises per the Story 2.1 hardening) is never called; whitespace `format` normalizes to `None` (no malformed `json_extract` path).
- **Test infra (the real lift):** added the `seeded_vec_db` fixture — a richer 4-card set (spanning colours/mana/format/**games**) seeded via the async engine, committed, then `card_vec` populated by `build_card_embeddings` on a same-file `ConnectionFactory` with a **deterministic fake embedder** (one-hot per distinct text) yielded to the test so query embeddings match the index offline. The existing `seeded_card_db` (8+ dependents) is untouched. One `@pytest.mark.integration` test uses the **real** model and proves honest semantic ranking ("flying red dragon …" → Inferno Dragon first).
  - Fixture gotcha resolved: the async SQLAlchemy `JSON` column stores Python `None` as the JSON text `'null'` (not SQL NULL), which the frozen Story 2.3 builder's `_coerce_json_list` turns into `None` → `TypeError`. Real Scryfall data uses `[]` (empty array) for absent keywords, so the fixture mirrors that (`keywords=[]`) — no change to the frozen builder.
- **Frozen ports respected:** no change to `Embedder` (symmetric `encode` for the query — no `query_embed`), the `card_vec` schema, the index builder, or the default L2 metric. Raw `distance` is returned as the relevance signal (no cosine conversion — a 2.6 concern). No new dependencies, no `pyproject.toml` / `.pre-commit-config.yaml` change.
- **Validation results:** new offline tests **18 passed** (`test_query.py` 12 + helper-level 6); real-embedder ranking **1 passed**; end-to-end MCP suite **15 passed** (4 new); full active suite **499 passed** (477 baseline + 22 new), 0 regressions (NFR7). `ruff check` + `ruff format --check` clean on all authored files; `mypy src/` clean (45 files); `pre-commit run mypy` passed.

### File List

**New**
- `src/search/query.py` — `hybrid_search(conn, vector, …) -> list[CardHit]` + the `CardHit` dataclass + `ColorMode` (the reusable, embed-agnostic hybrid query path; Story 2.5 reuses it).
- `src/mcp_server/tools/semantic_search.py` — `SemanticSearchResult` / `SemanticCardHit` + the sync `semantic_search_cards(conn, embedder, query, …)` helper (validate → embed → `hybrid_search` → project).
- `tests/unit/search/test_query.py` — 12 unit tests for `hybrid_search` (fake embedder + real sqlite-vec).
- `tests/integration/mcp_server/test_semantic_search_tool.py` — 6 helper-level tests + 1 `@pytest.mark.integration` real-embedder ranking test.

**Modified**
- `src/search/__init__.py` — re-export `CardHit` + `hybrid_search`; refreshed package docstring.
- `src/mcp_server/server.py` — `build_server(+connection_factory, +embedder)`; registered the sync `semantic_search_cards` `@mcp.tool()` (13th tool).
- `tests/integration/conftest.py` — added the `seeded_vec_db` fixture (`SeededVecDB` bundle + `_FakeVecEmbedder` + `_sample_vec_cards`); existing `seeded_card_db` untouched.
- `tests/integration/test_mcp_tools.py` — 4 end-to-end `semantic_search_cards` tests through the in-process MCP client (hosting, nearest hit, format-filter exclusion, invalid color).
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — `2-4` → in-progress → review.

## Change Log

| Date | Version | Description |
|---|---|---|
| 2026-06-22 | 1.0 | Implemented Story 2.4. Task 0 de-risk spike confirmed the canonical AC3 CTE hybrid works as-authored on sqlite-vec v0.1.9 (no two-step fallback). Built the reusable embed-agnostic `hybrid_search` (KNN + vec0 metadata pre-filter inside / `json_extract`+`LIKE` JOIN post-filter outside / over-fetch k=200 / oracle-id de-dup), the sync `semantic_search_cards` tool helper (graceful `ok`/`empty`/`invalid`, empty-query guard, symmetric `encode`), the `build_server` sync seams (`connection_factory`/`embedder`, lazy `get_embedder` preserved), and the `card_vec`-populated `seeded_vec_db` fixture (fake + real embedder split). All filters bound as parameters (no user-value SQL interpolation). AC4 real-corpus smoke: 41–51 ms end-to-end on the 38,232-vector index (< ~100 ms NFR1). Full suite 499 passed (+22), ruff/mypy/pre-commit clean. Status → review. |
| 2026-06-21 | 0.1 | Story drafted via BMAD create-story (ultimate context engine). Surfaced the **sync-tool decision** (vector index is sync-only via `ConnectionFactory`; register `semantic_search_cards` as a sync `def` tool, FastMCP threadpools it — no async repo, no event-loop block), the **CTE hybrid query** (metadata pre-filter inside the KNN, legality/games JOIN outside, over-fetch `k`) with a required de-risk spike, the **oracle-id de-dup** (the index has every printing), the **symmetric `encode` query-embedding** decision (no `query_embed`), the reusable `src/search/query.py::hybrid_search(vector, …)` seam set up for Story 2.5, the **`card_vec`-populated test fixture** gap (existing `seeded_card_db` has no vectors) + fake/real embedder split, and `build_server` `connection_factory`/`embedder` injection. Status → ready-for-dev. |
