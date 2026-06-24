---
baseline_commit: 171d138ab4c82fef64495aebc887f2ad94900b94
---

# Story 2.5: find_similar_cards Tool

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a player,
I want a `find_similar_cards` MCP tool that takes a **seed card** (by name or `card_id`), reads that card's **already-stored** `card_vec` vector (no embedding — it's a point lookup, not an `encode`), runs the Story 2.4 `hybrid_search` KNN seeded by that vector, **excludes the seed's own Oracle identity** so I get genuine alternatives rather than the seed plus its reprints, and composes the same optional relational filters (format-legal, colors, mana-value range, games) into one query,
so that I can discover alternatives, replacements, and synergy pieces from a card I already like — closing Epic 2's two new search tools (FR7) and feeding Epic 3's deckbuilding skills "more cards like this".

## Acceptance Criteria

> Source: [epics.md#Story-2.5](../planning-artifacts/epics.md) (BDD as authored), with implementation-critical clarifications folded in from the real codebase: the **embed-agnostic** `hybrid_search(conn, vector, …)` Story 2.4 built *specifically for this story*, the **sync-only** `card_vec` seam, the seed-vector read-back (the one genuinely new mechanic), oracle-id self-exclusion, and the sync raw-SQL seed resolution (the async `CardRepository` is unreachable on the sync connection). The design spec §5/§6 states it outright: *"`find_similar_cards` uses the same path seeded by a card's stored vector."* **All five ACs must hold simultaneously.**

**AC1 — Seed card's stored vector → top-K nearest cards via the SAME hybrid path (FR7)**
- **Given** `find_similar_cards` with a seed card identifier (`card_name` **or** `card_id`, exactly one)
- **When** invoked
- **Then** it resolves the seed to a `(card_id, oracle_id)`, **reads the seed's stored embedding from `card_vec`** (a point lookup by the TEXT PK `card_id` — *not* a re-embed), and passes that vector to the Story 2.4 [`hybrid_search`](../../src/search/query.py) to retrieve the top-K nearest cards as ranked `SemanticCardHit`s (each a lightweight `CardSummary` + the vec0 `distance`), nearest-first.
- **🔴 Clarification — NO embedding happens. `find_similar_cards` does not take or use an `Embedder`.** The seed vector already exists in the index (Story 2.3 built one row per printing). Read it back with `SELECT embedding FROM card_vec WHERE card_id = ?` and deserialize the BLOB to a 384-dim `float32` array (`np.frombuffer(blob, dtype=np.float32)`), then feed it straight into `hybrid_search` (which re-serializes via `sqlite_vec.serialize_float32`). This is the one new mechanic the spike (Task 0) must close. **Do not** add an `Embedder` parameter to the tool or call `encode` anywhere.

**AC2 — Self-exclusion: the seed (and all its printings) are removed so results are useful alternatives**
- **Given** the seed is its own nearest neighbour (distance ≈ 0, plus every other printing of it sharing a near-identical vector)
- **When** results return
- **Then** **every hit whose `oracle_id` equals the seed's `oracle_id` is excluded** (not just the exact printing) — so the top of the list is genuine alternatives, never the seed echoed back.
- **🔴 Clarification — exclude by `oracle_id`, not `card_id`.** `hybrid_search` already de-dups to one hit per `oracle_id`; the surviving "seed" hit might be a *different* printing UUID than the one passed in, but it's the same Oracle card — so exclude the whole oracle. **Recommended implementation: add an optional `exclude_oracle_id: str | None = None` parameter to `hybrid_search`** (additive, backward-compatible, default `None` — the Story 2.4 `semantic_search_cards` path is unaffected). Skip it inside the existing nearest-first de-dup loop *before* the `limit` check, so the over-fetch/`limit` accounting stays correct (no `limit + 1` dance, no starved result set). [Documented fallback if you choose not to touch `query.py`: call `hybrid_search(limit=limit + 1)`, drop hits where `oracle_id == seed_oracle_id`, then trim to `limit` — but the parameter is cleaner and centralizes the over-fetch math.]

**AC3 — Optional relational filters compose with the similarity query (FR16)**
- **Given** optional `format` (legality), `colors` (+ `color_mode`), `mana_value_min`/`max`, and `games`
- **When** passed
- **Then** they compose into the same hybrid query path as Story 2.4 — `mana_value` + colours as the vec0 metadata pre-filter (inside the KNN), legality/games via the JOIN to `cards` (outside) — by passing them straight through to `hybrid_search` (over-fetch `k`, JOIN/filter, oracle de-dup). No new query logic: 2.5 reuses 2.4's `hybrid_search` verbatim except for the seed vector + the exclusion param.

**AC4 — Seed not resolvable / not in the index → graceful message (no exception surfaced)**
- **Given** a seed that does not resolve to a card, resolves to **multiple** cards, or resolves to a card with **no vector** in `card_vec`
- **When** invoked
- **Then** it returns a graceful structured result, never raising:
  - name/id matches nothing → `status="not_found"` with a check-the-spelling message;
  - name matches **multiple distinct Oracle cards** → `status="ambiguous"` with the candidate `matches` (mirroring [`lookup_card`](../../src/mcp_server/tools/card_lookup.py)'s 2–5 / 6+ buckets) so the caller re-calls with a specific `card_id`;
  - card exists but has **no `card_vec` row** (index incomplete) → `status="not_found"` with a "found '{name}' but it isn't in the semantic index yet" message;
  - neither or both of `card_name`/`card_id` supplied, or a bad filter value (color/game/mana-range/limit) → `status="invalid"` naming the problem.
- **And** when the seed resolves and is indexed but **no other card survives** the filters/exclusion → `status="empty"` with an adjust-your-filters hint.

**AC5 — Stateless; driven through the in-process MCP harness (FR3)**
- **Given** `format`/`games` and every filter
- **When** passed
- **Then** they are **per-call parameters** with no server-side state (D5) — identical to `semantic_search_cards`/`search_cards`.
- **And given** the in-memory MCP client harness (`create_connected_server_and_client_session`, no subprocess) driving `find_similar_cards` against the `seeded_vec_db` fixture (cards + populated `card_vec`)
- **Then** integration assertions pass: a seed returns its nearest *other* card; the seed's own oracle is absent from results; a hybrid filter (e.g. `format="standard"`) excludes the non-legal card; a bad seed name returns `status="not_found"` (`isError=False`); an `invalid` filter returns `status="invalid"` (`isError=False`).

## Tasks / Subtasks

- [x] **Task 0 — De-risk spike: read a stored vector back out of `card_vec`** (AC: 1) — 15 min, throwaway, before writing the tool (mirror the 2.2/2.3/2.4 spike discipline; this is the one unproven mechanic)
  - [x] On a `tmp_path` DB via `ConnectionFactory`: build a tiny `cards` table + `build_card_embeddings` with a fake one-hot embedder (reuse the `test_query.py` `_make_factory`/`_seed_card` shape). Then:
    1. Confirm a **point lookup by PK** returns the vector: `SELECT embedding FROM card_vec WHERE card_id = ?` (no `MATCH`/`k` — `card_id` is the TEXT PRIMARY KEY, so this is a plain row read, not a KNN). Record exactly what the column yields on sqlite-vec **v0.1.9** (expected: a `bytes` BLOB in the compact float32 layout).
    2. Deserialize: `np.frombuffer(blob, dtype=np.float32)` → assert `shape == (EMBEDDING_DIM,)`.
    3. **Round-trip:** feed that vector into `hybrid_search(conn, vec)` and assert the seed card comes back at `distance ≈ 0` — proving read-back fidelity end-to-end.
  - [x] If the raw-BLOB read misbehaves on v0.1.9, capture the fallback in the Debug Log: `SELECT vec_to_json(embedding) FROM card_vec WHERE card_id = ?` → `json.loads` → `np.asarray(..., dtype=np.float32)`. Record the working form; delete the spike file.

- [x] **Task 1 — Seed-vector read helper in `src/search/query.py` (MODIFIED)** (AC: 1) — keep the sqlite-vec read-back specifics in `src/search`, framework-free, fully `mypy --strict`-typed, Google docstring with `Example:`
  - [x] Add `get_card_vector(conn, card_id) -> NDArray[np.float32] | None`: point-SELECT the seed's `embedding` from `CARD_VEC_TABLE` by `CARD_ID_COL` (build SQL from the schema constants — never literal `"card_vec"`), deserialize per the Task 0 finding, return the 384-dim `float32` array, or **`None` if the card has no `card_vec` row** (the "not indexed" signal AC4 needs). Default tuple row factory — index positionally.
  - [x] Add the optional `exclude_oracle_id: str | None = None` parameter to `hybrid_search` (AC2): in the existing nearest-first de-dup loop, `continue` past any row whose `oracle_id == exclude_oracle_id` *before* appending/incrementing toward `limit`. Update the docstring (one line) — default `None` preserves the Story 2.4 behaviour exactly.
  - [x] Re-export `get_card_vector` from `src/search/__init__.py` `__all__`; refresh the package docstring (the find-similar read path now exists; only the RAG eval, Story 2.6, remains).

- [x] **Task 2 — The tool helper `src/mcp_server/tools/find_similar.py` (NEW)** (AC: 1, 2, 3, 4, 5) — thin **sync** wrapper; mirror `semantic_search.py`'s structured-result + graceful-validation shape, **reusing** its `SemanticCardHit` for the hits
  - [x] `SimilarCardsResult(BaseModel)`: `status: Literal["ok", "empty", "invalid", "not_found", "ambiguous"]`, `cards: list[SemanticCardHit] = []` (import `SemanticCardHit` from `semantic_search.py` — do **not** redefine it), `total_count: int = 0`, `seed: CardSummary | None = None` (the resolved seed, echoed back when `ok`/`empty`), `matches: list[CardSummary] = []` (candidates when `ambiguous`), `message: str`. Google docstring.
  - [x] `find_similar_cards(conn, *, card_name=None, card_id=None, colors=None, color_mode="any", mana_value_min=None, mana_value_max=None, format=None, games=None, limit=10) -> SimilarCardsResult` — **no `embedder` parameter** (the seed vector is read, not computed):
    - Validate first (return `status="invalid"`, never raise): exactly one of `card_name`/`card_id` (neither/both → invalid); reuse `semantic_search.py`'s `_VALID_COLORS`/`_VALID_GAMES` vocab + the mana-range/limit checks (import them or replicate — keep modules decoupled, as 2.4 did); normalize empty/whitespace `format` → `None`.
    - **Resolve the seed in sync raw SQL** on `cards` (see Task 2 helper) → `(card_id, oracle_id, CardSummary)` | `not_found` | `ambiguous`.
    - `vec = get_card_vector(conn, seed_card_id)`; if `None` → `status="not_found"` ("found '{name}' but it isn't in the semantic index yet").
    - `hits = hybrid_search(conn, vec, limit=limit, exclude_oracle_id=seed_oracle_id, …filters…)`.
    - No hits → `status="empty"` (adjust-filters hint, `seed` populated); else project each `CardHit` → `SemanticCardHit(card=CardSummary(...), distance=…)` (same projection as `semantic_search.py`) and return `status="ok"` with `total_count`, `seed`, and a "N cards similar to '{seed.name}'" message.
  - [x] Private sync seed resolver `_resolve_seed(conn, card_name, card_id) -> …`: if `card_id` given, `SELECT id, oracle_id, name, mana_cost, cmc, type_line, oracle_text, colors, rarity, set_code FROM cards WHERE id = ?` (→ not_found if absent). Else exact name match (`WHERE lower(name) = lower(?) OR lower(printed_name) = lower(?) ORDER BY id LIMIT 1`), then a partial fallback (`name LIKE ?`) **grouped/distinct by `oracle_id`**: 0 → not_found, 1 oracle → seed, >1 → ambiguous with the distinct-oracle `CardSummary` matches (cap at ~10, mirror `lookup_card`'s `_MAX_MATCHES`/`_REFINE_THRESHOLD`). Build `CardSummary` from the row (`json.loads` the `colors` text, `None`-coerce). Bind every value as a parameter (no f-string interpolation; mind the pre-existing LIKE-wildcard note in [deferred-work](./deferred-work.md) — same accepted risk as the repo, don't regress it).
  - [x] Module docstring; full strict typing; `logger` (`%`-style lazy args); guard clauses over nesting.

- [x] **Task 3 — Register the tool in `src/mcp_server/server.py` (MODIFIED)** (AC: 1, 5) — **no `build_server` signature change** (the `connection_factory` seam already exists from Story 2.4; the embedder is *not* needed here)
  - [x] Register `find_similar_cards` as a **sync `@mcp.tool()`** (plain `def`, FastMCP threadpools it — the 14th tool, alongside the sync `semantic_search_cards` and the 12 async Epic-1 tools). Inside: `conn = connection_factory.get_connection()` (per-thread sqlite-vec connection, NFR6); `return _find_similar_helper(conn, card_name=…, card_id=…, …filters…)`. **Do not** resolve `get_embedder()` — this tool never embeds.
  - [x] LLM-facing docstring: describe the seed (`card_name` **or** `card_id`), each filter, the self-exclusion ("results are alternatives, not the seed"), the `distance` relevance signal, statelessness, and when to prefer it over `semantic_search_cards` (you have a concrete card vs. a description). Mention following up with `lookup_card_by_name` for full detail.

- [x] **Task 4 — Tests** (AC: 1, 2, 3, 4, 5)
  - [x] **`tests/unit/search/test_query.py` (MODIFIED)** — add unit tests for the two new `query.py` pieces (fake embedder + real sqlite-vec, like the existing tests): `get_card_vector` returns the seed's exact stored vector (round-trips to `distance ≈ 0` through `hybrid_search`) and returns `None` for an unindexed `card_id`; `hybrid_search(exclude_oracle_id=…)` drops every printing of that oracle while still returning `limit` other hits (seed two printings of the excluded oracle + ≥2 others).
  - [x] **`tests/integration/mcp_server/test_find_similar_tool.py` (NEW)** — helper-level via `find_similar_cards(conn, …)` on a `tmp_path` `card_vec` (reuse `test_query.py`'s `_FakeEmbedder`/`_make_factory`/`_seed_card` shape; note the [deferred `_FakeEmbedder` triplication](./deferred-work.md) — acceptable, or consolidate if trivial): `ok` (seed → nearest *other* card, seed's oracle absent); self-exclusion across duplicate printings; filters compose (color/mana/format/games narrow results); `not_found` (unknown name); `not_found` (card present in `cards` but not in `card_vec`); `ambiguous` (two distinct-oracle cards sharing a name substring → `matches` returned); `invalid` (neither/both identifiers, bad color/game/mana-range/limit). Resolve seeds by exact `name` (the fixture/table cards have `printed_name=None`).
  - [x] **`tests/integration/test_mcp_tools.py` (MODIFIED)** — add end-to-end `find_similar_cards` through the in-process MCP client using the **existing `seeded_vec_db` fixture** (built by Story 2.4 — cards + populated `card_vec`; **reuse it, do not add a new fixture**) + `build_server(session_factory=…, connection_factory=…)`: seed `card_name="Inferno Dragon"` returns `status="ok"` with the dragon's oracle **absent** and another seeded card present; `format="standard"` excludes the modern-only `Backstreet Goblin`; a bad seed name returns `status="not_found"`, `isError=False`; assert the result is hosted alongside the existing tools (it appears in `list_tools`).

- [x] **Task 5 — Verify (run the commands, capture output)** (AC: all)
  - [x] `uv run pytest tests/unit/search/test_query.py tests/integration/mcp_server/test_find_similar_tool.py -m "not integration" -v` → new/changed tests pass (fast, offline, real sqlite-vec + fake embedder).
  - [x] `uv run pytest tests/ -m "not integration"` → full active suite still green (baseline **499 passed** after Story 2.4 — keep it green, NFR7).
  - [x] `uv run ruff check .` and `uv run ruff format --check .` → clean for story-authored files (`src/search/query.py`, `src/search/__init__.py`, `src/mcp_server/tools/find_similar.py`, `src/mcp_server/server.py`, the new/modified tests). Don't reformat unrelated pre-existing issues.
  - [x] `uv run mypy src/` → clean. `uv run pre-commit run mypy --all-files` too (no new deps → **no new `additional_dependencies`**; `sqlite_vec`/`numpy`/`mcp` already resolve from Stories 2.1–2.4).
  - [x] **Optional real-corpus smoke (AC1/AC2):** with the real `./data/cards.db` (38,232-vector index from Story 2.3), drive `find_similar_cards(card_name="Glorybringer")`; confirm sensible alternatives (other aggressive red flyers/dragons), the seed's own oracle absent, and note end-to-end time in the Debug Log (expect <~100 ms — it's a point read + one KNN, *cheaper* than 2.4 since there's no query embed). Do not assert it in a test.

### Review Findings

- [x] [Review][Patch] Replace `assert` with explicit `if` guard — `assert` is stripped by `python -O`; if `_resolve_seed` ever returns `status="found"` with a `None` field, the code proceeds to dereference `None` and crash with an unhelpful `AttributeError` rather than returning a structured error [`src/mcp_server/tools/find_similar.py:352`]
- [x] [Review][Patch] Add wire-level `status="invalid"` filter test — AC5 explicitly requires "invalid filter returns `status="invalid"` (`isError=False`)" through the in-process MCP harness; no such test exists in `test_mcp_tools.py` [`tests/integration/test_mcp_tools.py`]
- [x] [Review][Patch] Assert `result.seed is not None` in the unindexed `not_found` test — implementation correctly populates `seed` when the card exists but has no `card_vec` row; the test only checks `status` and the message substring, leaving the `seed` population untested [`tests/integration/mcp_server/test_find_similar_tool.py:287`]
- [x] [Review][Patch] Fix `SimilarCardsResult.seed` docstring — the class and `find_similar_cards` returns docstrings say `seed` is echoed back only for `ok`/`empty`; but the implementation also populates `seed=seed.summary` for the "card found but not indexed" `not_found` branch; callers checking `seed is not None` cannot distinguish the two `not_found` sub-cases without parsing the message string [`src/mcp_server/tools/find_similar.py`]
- [x] [Review][Defer] LIKE wildcard injection (`%`/`_` in `card_name`) [`src/mcp_server/tools/find_similar.py:223`] — deferred, pre-existing (explicitly accepted in deferred-work.md; mirrors CardRepository)
- [x] [Review][Defer] `limit > over_fetch_k` silently starves results [`src/search/query.py:hybrid_search`] — deferred, pre-existing (Story 2.4 design; also in 2-4 deferred-work)
- [x] [Review][Defer] `np.frombuffer` returns read-only array — mutation raises ValueError [`src/search/query.py:get_card_vector`] — deferred, pre-existing (current code path never mutates the result)
- [x] [Review][Defer] Empty/corrupted BLOB in `get_card_vector` raises ValueError [`src/search/query.py:get_card_vector`] — deferred, pre-existing (controlled data; `serialize_float32` always writes 1536 bytes)
- [x] [Review][Defer] `_FakeEmbedder` triplicated/quadruplicated across test files — deferred, pre-existing (tracked since 2-4 review in deferred-work.md)
- [x] [Review][Defer] `color_mode` not runtime-validated in `_validation_error` helper [`src/mcp_server/tools/find_similar.py:_validation_error`] — deferred, FastMCP `Literal` validates at wire level; mirrors Story 2.4 pattern
- [x] [Review][Defer] `limit` has no upper bound in `_validation_error` [`src/mcp_server/tools/find_similar.py:_validation_error`] — deferred, pre-existing (over_fetch_k=200 provides a natural cap; also in 2-4 deferred-work)
- [x] [Review][Defer] `_resolve_seed` LIKE query fetches all matching rows without SQL LIMIT [`src/mcp_server/tools/find_similar.py:~229`] — deferred, mirrors CardRepository's unbounded partial-name fetch
- [x] [Review][Defer] `_decode_colors` does not guard against non-list JSON or `JSONDecodeError` [`src/mcp_server/tools/find_similar.py:_decode_colors`] — deferred, infrastructure concern; Scryfall data always produces a JSON array; same pattern as `_coerce_json_list` in `query.py` (pre-existing)
- [x] [Review][Defer] Disambiguation "showing first N" message branch unreachable for 6–10 distinct matches [`src/mcp_server/tools/find_similar.py:253`] — deferred, minor phrasing gap; `len(shown) < len(distinct)` is always false when distinct ≤ _MAX_MATCHES; message correctly states count but says "refine" when all matches are already shown

## Dev Notes

### What this story IS — and is NOT

- **IS:** the **second and final Epic-2 search tool** — a thin **sync** tool `src/mcp_server/tools/find_similar.py::find_similar_cards(conn, card_name|card_id, …)` that (1) resolves the seed in sync raw SQL on `cards`, (2) reads the seed's **stored** vector from `card_vec` via a new `src/search/query.py::get_card_vector`, (3) calls the **existing** Story 2.4 `hybrid_search` seeded by that vector with a new `exclude_oracle_id` arg, and (4) projects to a `SimilarCardsResult` reusing 2.4's `SemanticCardHit`. Plus the `server.py` registration (14th tool) and tests. It realizes spec §5/§6's "`find_similar_cards` uses the same path seeded by a card's stored vector" (FR7). It is the **sixth** `src/search`-adjacent consumer after `ConnectionFactory` (1.2), `Embedder` (2.1), `card_vec` schema (2.2), the index builder (2.3), and `hybrid_search` (2.4).
- **IS NOT:** a re-embed of anything (the seed vector already exists — **read** it, never `encode`), a new query path (reuse `hybrid_search` verbatim aside from the additive exclusion arg), a new test fixture (reuse `seeded_vec_db` from 2.4), or the RAG sanity eval (Story 2.6). **Do not** modify the `Embedder`, the `card_vec` schema, or the index builder (those ports are frozen). **Do not** add an `Embedder` param to this tool, change the distance metric, or build pagination (KNN is top-K). **Do not** reach for the async `CardRepository`/`AsyncSession` — `card_vec` is sync-only; resolve the seed name in raw SQL on the same file (D2).

### 🔴 The one new mechanic: reading the seed's vector back out of `card_vec`

Everything else is a proven Story 2.4 part. The genuinely new piece is reading a stored vector *out* (Stories 2.2–2.4 only ever wrote vectors in or `MATCH`-ed against them):

- It is a **point lookup by the TEXT PRIMARY KEY**, not a KNN: `SELECT embedding FROM card_vec WHERE card_id = ?`. No `MATCH`, no `k` — those are only for similarity scans; a PK read is a plain row fetch.
- The column comes back as a **BLOB** (the compact float32 layout `sqlite_vec.serialize_float32` wrote in Story 2.3). Deserialize with `np.frombuffer(blob, dtype=np.float32)` → a `(384,)` array. Feed it straight into `hybrid_search`, which re-serializes it — so the read and the re-search use the identical encoding (round-trip safe). **Task 0 proves this on the installed v0.1.9** before you build the tool; fallback `vec_to_json(embedding)` + `json.loads` is documented if the raw BLOB read surprises you.
- `get_card_vector` returns **`None` when the `card_id` has no `card_vec` row** — that's the structured signal for AC4's "card exists but isn't indexed". Keep this read in `src/search/query.py` (sqlite-vec specifics belong in `src/search`, framework-free).

### 🔴 Self-exclusion is the point of the tool — exclude the whole Oracle, not one printing

The seed matches itself at distance ≈ 0, and (because the index has every printing — 38,232 rows over ~Oracle cards) several near-identical printings of the seed crowd the top of the raw KNN. Without exclusion, "find me cards like Glorybringer" returns *Glorybringer, Glorybringer, Glorybringer…*. `hybrid_search` already collapses printings to one hit per `oracle_id`; you must then drop that one seed-oracle hit. **Exclude by `oracle_id`** (the resolved seed's oracle), because the surviving printing may differ from the passed `card_id`. The recommended `exclude_oracle_id` param does this inside the existing de-dup loop so the over-fetch (`k=200`) and `limit` accounting stay correct — the seed-plus-reprints simply never consume a `limit` slot. (Epic wording is "excluded **or** clearly marked"; excluding is the cleaner UX and what makes results "useful alternatives".)

### 🔴 This tool is SYNC and needs NO embedder (a simplification vs. Story 2.4)

`find_similar_cards` is a plain sync `def` `@mcp.tool()` for the same reason `semantic_search_cards` is: `card_vec` + sqlite-vec are reachable **only** on the sync `ConnectionFactory` connection ([connection.py](../../src/search/connection.py)); the async aiosqlite engine never loads the extension (`no such module: vec0`). FastMCP threadpools sync tools → per-thread sqlite-vec connection (NFR6). **But unlike 2.4, this tool never embeds** — it reads a stored vector — so:

- The tool helper takes `conn` only (no `embedder`).
- `build_server` needs **no signature change**: the `connection_factory` seam already exists (Story 2.4); the `embedder` seam is simply not used by this tool. The server wrapper does `conn = connection_factory.get_connection()` and calls the helper.
- Seed-name resolution is sync raw SQL on `cards` (same file as `card_vec`, D2) — **not** the async `CardRepository`. Mirror `lookup_card`'s exact-then-partial + disambiguation *shape*, re-implemented as raw SQL (the JOIN/idioms are the `card.py` patterns 2.4 already re-implemented).

> If a future constraint forces async registration, the fallback is `async def` + `await asyncio.to_thread(_run)`. Prefer the plain sync tool — it is the established NFR6 design and this tool has no async dependency at all.

### Result shape — reuse `SemanticCardHit`, new `SimilarCardsResult` for the seed/ambiguity statuses

- Hits are structurally identical to semantic search (a `CardSummary` + `distance`), so **import and reuse `SemanticCardHit`** from [`semantic_search.py`](../../src/mcp_server/tools/semantic_search.py) — do not redefine it.
- The *result envelope* differs because find-similar has seed-resolution outcomes semantic search doesn't: hence a new `SimilarCardsResult` with `status: Literal["ok","empty","invalid","not_found","ambiguous"]`, `seed: CardSummary | None` (echo the resolved seed so the caller sees what it matched), and `matches: list[CardSummary]` (ambiguity candidates, like `CardLookupResult.matches`). `not_found` covers both "no such card" and "card exists but unindexed" (distinct messages, lean enum — same philosophy as `lookup_card`).
- `CardSummary` is the lightweight projection (omits `legalities`/`image_uris`/`card_faces`); its `@field_validator`s coerce null `oracle_text`/`mana_cost`; `colors` JSON text → `json.loads` (`None → []`). Build hits exactly as `semantic_search.py` does ([lines 208–224](../../src/mcp_server/tools/semantic_search.py#L208)).

### Validation & filter semantics (graceful, mirror semantic_search)

- **Reuse** `semantic_search.py`'s `_VALID_COLORS`/`_VALID_GAMES` + the mana-range (`min ≤ max`, both `≥ 0`) + `limit ≥ 1` checks (import them or replicate — modules stay decoupled per the 2.4 precedent). Add the **"exactly one of `card_name`/`card_id`"** guard (neither or both → `invalid`). Normalize empty/whitespace `format` → `None` (the malformed-`json_extract` guard).
- Filters (`colors`/`color_mode`/`mana_value_*`/`format`/`games`/`limit`) pass straight through to `hybrid_search` — same semantics, same `color_mode` set (`any`/`all`/`exact`/`at_most`), same int floor/ceil on mana bounds. No new filter logic.

### Test infra — reuse 2.4's `seeded_vec_db`; the unit lift is small

- The **`seeded_vec_db` fixture already exists** ([conftest.py](../../tests/integration/conftest.py)) and is exactly what end-to-end find-similar needs: 4 cards (`Inferno Dragon` R/5, `Backstreet Goblin` R/4 modern-only, `Mind Dissolve` U/2, `Verdant Elf` G/1) seeded via the async engine **and** a `card_vec` populated by the same deterministic fake embedder. Reuse it — **do not** add a new fixture. With the one-hot fake embedder, every card has a distinct basis vector, so "nearest other card" is deterministic. (The dragon's nearest *other* card depends on the one-hot assignment order; assert on **oracle absence / membership**, not a specific runner-up, unless you control the assignment — keep the assertion robust.)
- For the helper-level `test_find_similar_tool.py` and the `test_query.py` additions, reuse the `_FakeEmbedder`/`_make_factory`/`_seed_card`/`build_card_embeddings` pattern already in [`test_query.py`](../../tests/unit/search/test_query.py). Seed **two printings of one oracle** to prove self-exclusion drops the whole oracle. Use `tmp_path`, `factory.close()` teardown — never `/tmp`.
- **No real-embedder integration test is required** for this story — find-similar never embeds, so there's nothing model-dependent to assert (the read-back + KNN are fully exercised offline by the fake embedder). The real model is covered by 2.4's ranking test and Story 2.6's eval. (An optional real-corpus *smoke* against `./data/cards.db` is the AC1/AC2 Debug-Log note, not a test.)

### Anti-patterns (do NOT do these)

- ❌ Re-embed the seed (call `encode` / pass an `Embedder`) — the vector is already stored; **read** it with `get_card_vector`. This tool has no embedder.
- ❌ Use a KNN/`MATCH` to fetch the seed vector — it's a **point read by PK** (`WHERE card_id = ?`, no `MATCH`/`k`).
- ❌ Exclude by `card_id` instead of `oracle_id` — you'd leak other printings of the seed; exclude the whole oracle.
- ❌ Add `find_similar` query logic to `query.py` beyond `get_card_vector` + the `exclude_oracle_id` arg — reuse `hybrid_search` as-is for the KNN/filter/dedup.
- ❌ Reach for the async `CardRepository`/`AsyncSession` to resolve the seed name — `card_vec` is sync-only; resolve in raw SQL on the `ConnectionFactory` connection (same file, D2).
- ❌ Change `build_server`'s signature — the `connection_factory` seam already exists (2.4); don't add params for a tool that needs none new.
- ❌ Add a new test fixture for the vector DB — reuse `seeded_vec_db`.
- ❌ Redefine `SemanticCardHit` — import it from `semantic_search.py`.
- ❌ Modify the `Embedder`, the `card_vec` schema, or the index builder — frozen ports (2.1/2.2/2.3).
- ❌ Hardcode `"card_vec"`/`"embedding"`/`"color_r"`/`384` — use `CARD_VEC_TABLE`/`EMBEDDING_COL`/`COLOR_COLS`/`EMBEDDING_DIM` constants.
- ❌ Interpolate user filter/seed values into SQL strings — bind them as parameters (the `float[N]` dim is the only literal, already handled in `schema.py`).
- ❌ Emit a KNN without `k`/`LIMIT` — `hybrid_search` already enforces it; don't bypass it.
- ❌ Index `sqlite3.Row` by column name — `ConnectionFactory` connections use the default **tuple** row factory; index positionally (Story 2.2 lesson).
- ❌ Break the Story 2.4 `semantic_search_cards` path — the `exclude_oracle_id` param must default `None` (no behaviour change for 2.4); keep its tests green.
- ❌ Surface exceptions for a missing/ambiguous/unindexed seed — return `not_found`/`ambiguous`/`empty`/`invalid` gracefully (never raise).

### Previous Story Intelligence (2.4 is the direct template; 2.3/2.2/2.1 supply the parts)

- **Story 2.4 handed you the engine you reuse almost whole:** `hybrid_search(conn, vector, …)` was built **embed-agnostic specifically so 2.5 passes a seed vector** ([query.py docstring](../../src/search/query.py) and [`__init__.py`](../../src/search/__init__.py) both say so). Reuse it; your only additions are `get_card_vector` + the `exclude_oracle_id` arg. The `SemanticCardHit`/`CardSummary` projection, the graceful `ok`/`empty`/`invalid` contract, the `_VALID_*` vocab, and the **sync-tool decision** all transfer verbatim from [`semantic_search.py`](../../src/mcp_server/tools/semantic_search.py)/[`server.py`](../../src/mcp_server/server.py). The `seeded_vec_db` fixture is yours to reuse. [Source: [2-4 Dev Agent Record](./2-4-semantic-search-cards-tool-hybrid-query.md).]
- **Story 2.3 handed you** the index (real `./data/cards.db` has a complete **38,232**-vector index for the AC1/AC2 smoke), `build_card_embeddings` (populates test `card_vec`), and the `serialize_float32` write boundary you're now reading back. [Source: [2-3](./2-3-card-embedding-index-builder-idempotent-incremental.md).]
- **Story 2.2 handed you** the schema constants (`CARD_VEC_TABLE`/`CARD_ID_COL`/`EMBEDDING_COL`/`COLOR_COLS`/`MANA_VALUE_COL`) and the **TEXT** `card_id` PK (= `cards.id`; the point lookup is `WHERE card_id = ?` on a text key). [Source: [2-2](./2-2-card-vec-schema-with-metadata-columns.md); [schema.py](../../src/search/schema.py).]
- **Story 2.1** is **not used** here (no embedding) — a deliberate simplification; do not import `get_embedder`/`Embedder` into this tool. [Source: [2-1](./2-1-embedder-port-fastembed-singleton-persistent-cache.md).]
- **Epic-1 pattern for the seed resolver:** [`card_lookup.py`](../../src/mcp_server/tools/card_lookup.py) is the disambiguation template (exact → partial; 0/1/2–5/6+ buckets; `_MAX_MATCHES`/`_REFINE_THRESHOLD`) — re-implement its *shape* as sync raw SQL, swapping the async `CardRepository` calls for parameterized `SELECT`s mirroring [`card.py`](../../src/data/repositories/card.py)'s `_apply_*` idioms.
- **Recurring review findings to pre-empt:** Google-style `Example:` on every public function; `tmp_path` not `/tmp`; `factory.close()` teardown; positional row indexing; build SQL from schema constants; bind all user values as parameters. [Source: [2-1/2-2/2-4 reviews](./deferred-work.md).]
- **Baseline green at 499 passed** (`-m "not integration"`) after Story 2.4; `legacy/` excluded. Keep it green (NFR7).

### Git Intelligence

- HEAD `171d138` "fix: apply Story 2.4 code review patches" closed Story 2.4 (the prior 2.4 commits `dc47b94`/`d5acfb8`; 2.3 `dc47b94`; etc.). The Epic-2 cadence is firm: a 15-min de-risk spike on the installed wheel → thin `src/search` add + thin sync MCP tool → focused fake-embedder + real-sqlite-vec tests → run-and-capture verify → strict scope discipline. This is the next-to-last Epic-2 link (embedder → schema → builder → semantic tool → **similar tool** → eval).
- `src/search/` holds `connection.py`/`embedder.py`/`schema.py`/`index_builder.py`/`query.py` (+ `__init__.py`); 2.5 **extends `query.py`** (no new module there). `src/mcp_server/tools/` gains `find_similar.py` beside `semantic_search.py`; `server.py` gains a 14th tool (no new build_server seam). [Source: `git log`; [src/search/](../../src/search/); [src/mcp_server/tools/](../../src/mcp_server/tools/).]
- Working tree is clean at this baseline — no incidental edits expected beyond the story's File List.

### Latest Tech / Versions (verified for THIS project, 2026-06-22)

| Item | Value | Source |
|---|---|---|
| Seed-vector read-back | `SELECT embedding FROM card_vec WHERE card_id = ?` (point read, no `MATCH`/`k`) → BLOB → `np.frombuffer(blob, dtype=np.float32)` **(prove in Task 0)** | research §B; sqlite-vec Python docs |
| Read-back fallback | `SELECT vec_to_json(embedding) …` → `json.loads` → `np.asarray(..., float32)` if the BLOB read surprises on v0.1.9 | sqlite-vec docs |
| `hybrid_search` | embed-agnostic `(conn, vector, *, limit, over_fetch_k=200, filters…)`; reuse verbatim + add optional `exclude_oracle_id` | [query.py](../../src/search/query.py) (Story 2.4) |
| `sqlite-vec` | v0.1.9 (bundled); `k`/`LIMIT` mandatory **for KNN only** ([#116]); JOIN filtering proven ([#196]) | [research §A](../planning-artifacts/research/technical-sqlite-vec-fastembed-rag-stack-on-windows-research-2026-06-20.md); [test_schema.py](../../tests/unit/search/test_schema.py) |
| Serialization | `sqlite_vec.serialize_float32(list\|ndarray) -> BLOB` — `hybrid_search` re-serializes the read-back vector | Story 2.3/2.4; research §B |
| Legality / games SQL | `json_extract(legalities,'$.<fmt>')='legal'`; `cast(games AS TEXT) LIKE '%"<g>"%'` (handled inside `hybrid_search`) | [card.py:66,95](../../src/data/repositories/card.py#L66) |
| FastMCP tools | sync + async both hosted; sync run in the anyio threadpool (per-thread conn) — this tool is sync, **no embedder** | [server.py](../../src/mcp_server/server.py); project-context NFR6 |
| Index | real `./data/cards.db`: **38,232** vectors (Story 2.3); find-similar is a point read + one KNN (cheaper than 2.4 — no query embed) | [2-3 Debug Log](./2-3-card-embedding-index-builder-idempotent-incremental.md) |
| Python / SQLite | CPython 3.12.13 / SQLite 3.50.4 / Windows / uv | [project-context.md](../project-context.md) |

### Project Structure Notes

Target additions/edits (everything else unchanged):

```
src/
  search/
    __init__.py        # MODIFIED — re-export get_card_vector
    query.py           # MODIFIED — add get_card_vector(conn, card_id); add hybrid_search(exclude_oracle_id=…)
    connection.py      # (unchanged, 1.2) — the sync sqlite-vec connection
    embedder.py        # (unchanged, 2.1) — NOT used by find_similar
    schema.py          # (unchanged, 2.2) — CARD_VEC_TABLE/CARD_ID_COL/EMBEDDING_COL/… constants
    index_builder.py   # (unchanged, 2.3) — build_card_embeddings populates the test card_vec
  mcp_server/
    server.py          # MODIFIED — register sync find_similar_cards tool (14th); no build_server signature change
    tools/
      find_similar.py     # NEW — SimilarCardsResult + find_similar_cards(conn, card_name|card_id, …) (sync, no embedder)
      semantic_search.py  # (unchanged, 2.4) — SemanticCardHit reused; shape mirrored
tests/
  unit/
    search/
      test_query.py       # MODIFIED — get_card_vector round-trip + None; hybrid_search exclude_oracle_id
  integration/
    conftest.py           # (unchanged) — reuse the existing seeded_vec_db fixture
    test_mcp_tools.py      # MODIFIED — one end-to-end find_similar_cards through the in-process MCP client
    mcp_server/
      test_find_similar_tool.py  # NEW — helper-level (fake embedder): ok/empty/invalid/not_found/ambiguous + self-exclusion
```

- **Alignment:** matches spec §5 (tool catalog: `find_similar_cards` *(new)*, "seeded by an existing card's vector") + §6 ("`find_similar_cards` uses the same path seeded by a card's stored vector"). FR7/FR16; D2 single-file; D5 statelessness. [Source: [spec §5/§6](../../docs/superpowers/specs/2026-06-20-mcp-server-architecture-design.md).]
- **Layering check:** `src/search/query.py` (sync infra) is consumed downward by `src/mcp_server/tools/find_similar.py` — no upward import, no cycle. `find_similar.py` imports `SemanticCardHit` from its sibling `semantic_search.py` (both tool layer — fine). `src/search` stays framework-free. ✅
- **No new dependencies / no `pyproject.toml` or `.pre-commit-config.yaml` changes** — `sqlite-vec`, `numpy`, `mcp` are already core; the pre-commit mypy env already resolves them.

### References

- [epics.md — Epic 2 / Story 2.5](../planning-artifacts/epics.md) — user story + the five BDD ACs (seed vector → top-K; seed excluded/marked; filters compose; graceful not-in-index; in-memory harness).
- [design spec §5 / §6](../../docs/superpowers/specs/2026-06-20-mcp-server-architecture-design.md) — tool catalog (`find_similar_cards` *(new)*, seeded by a card's vector); "uses the same path seeded by a card's stored vector"; D5 statelessness; D2 single-file.
- [research §A (hybrid patterns + over-fetch) / §B (serialization)](../planning-artifacts/research/technical-sqlite-vec-fastembed-rag-stack-on-windows-research-2026-06-20.md) — the hybrid query `find_similar` reuses; `serialize_float32` BLOB layout you read back.
- [src/search/query.py](../../src/search/query.py) — `hybrid_search` (reuse) + `CardHit`; **extend** with `get_card_vector` + `exclude_oracle_id`.
- [src/search/schema.py](../../src/search/schema.py) — `CARD_VEC_TABLE`/`CARD_ID_COL`/`EMBEDDING_COL`/`COLOR_COLS`/`MANA_VALUE_COL`; TEXT `card_id` PK (point lookup key).
- [src/search/index_builder.py](../../src/search/index_builder.py) — `build_card_embeddings` (populate the test `card_vec`); `serialize_float32` write boundary (the encoding you deserialize); `_coerce_json_list` to mirror.
- [src/mcp_server/tools/semantic_search.py](../../src/mcp_server/tools/semantic_search.py) — the structured-result + graceful-validation **shape** to mirror; **import** `SemanticCardHit`; reuse `_VALID_COLORS`/`_VALID_GAMES` + range/limit checks; the `CardHit → SemanticCardHit/CardSummary` projection.
- [src/mcp_server/tools/card_lookup.py](../../src/mcp_server/tools/card_lookup.py) — the exact-then-partial + 0/1/2–5/6+ disambiguation **shape** for the sync raw-SQL seed resolver.
- [src/mcp_server/server.py](../../src/mcp_server/server.py) — `@mcp.tool()` sync registration (copy the `semantic_search_cards` pattern); the `connection_factory` seam already present (no signature change).
- [src/data/repositories/card.py](../../src/data/repositories/card.py) — `_apply_format_filter`/`_apply_games_filter`/`_apply_unique_oracle_filter` + `find_by_name_exact`/`find_by_name_partial` idioms to re-implement in raw SQL.
- [src/data/schemas/card.py](../../src/data/schemas/card.py) — `CardSummary` projection (omits heavy fields; NULL-coercion validators) for hits + seed + matches.
- [tests/integration/conftest.py](../../tests/integration/conftest.py) — the **existing `seeded_vec_db` fixture** (reuse it) + `_FakeVecEmbedder`/`_sample_vec_cards`.
- [tests/unit/search/test_query.py](../../tests/unit/search/test_query.py) — fake-embedder + real-sqlite-vec unit style (`_make_factory`/`_seed_card`); extend for `get_card_vector` + `exclude_oracle_id`.
- [tests/integration/mcp_server/test_semantic_search_tool.py](../../tests/integration/mcp_server/test_semantic_search_tool.py) — helper-test template for the new `test_find_similar_tool.py`.
- [tests/integration/test_mcp_tools.py](../../tests/integration/test_mcp_tools.py) — the in-process MCP harness to extend with one end-to-end `find_similar_cards`.
- [Story 2.4](./2-4-semantic-search-cards-tool-hybrid-query.md) / [2.3](./2-3-card-embedding-index-builder-idempotent-incremental.md) / [2.2](./2-2-card-vec-schema-with-metadata-columns.md) — the engine/index/schema this tool consumes; deferrals + recurring review findings.
- [project-context.md](../project-context.md) — RAG/MCP rules (KNN needs `k`/`LIMIT`; over-fetch then JOIN-filter; metadata cols; sync MCP tools threadpooled with per-thread connections; stateless tools; testing layout; ruff/mypy gates).
- [deferred-work.md](./deferred-work.md) — relevant pre-existing items: `_FakeEmbedder` triplication, `limit > over_fetch_k` truncation, `CardSummary` nullability, LIKE-wildcard escaping.

## Dev Agent Record

### Agent Model Used

claude-opus-4-8[1m] (Opus 4.8, 1M context) — BMAD dev-story workflow.

### Debug Log References

- **Task 0 de-risk spike (the one new mechanic — read-back from `card_vec`), throwaway, deleted after run.** On the installed **sqlite-vec v0.1.9**, the PK point lookup `SELECT embedding FROM card_vec WHERE card_id = ?` (no `MATCH`/`k`) returns the column as a **`bytes` BLOB of length 1536** (= `EMBEDDING_DIM` 384 × 4 bytes `float32`). `np.frombuffer(blob, dtype=np.float32)` → exact `(384,)` array. Round-trip proven: feeding that vector into `hybrid_search` returns the seed at `distance == 0.0`. A missing `card_id` point lookup returns `None` (the AC4 "not indexed" signal). **The raw-BLOB read works — the documented `vec_to_json` fallback was NOT needed.**
- **Optional real-corpus smoke (AC1/AC2), not asserted in a test.** `find_similar_cards(card_name="Glorybringer", limit=10)` against the real `./data/cards.db` (38,232-vector index, Story 2.3): `status=ok` in **47.8 ms** (a point read + one KNN — cheaper than 2.4, no query embed). The seed's own oracle is **absent**; alternatives are sensible aggressive red dragons (Stormbreath Dragon, Thundermaw Hellkite, Hellkite Charger, Wrathful Red Dragon, …) — exactly the expected "other aggressive red flyers/dragons".

### Completion Notes List

- **AC1 (seed vector → top-K via the SAME hybrid path):** Added `src/search/query.py::get_card_vector(conn, card_id)` — a PK point read (no `MATCH`/`k`) deserialized with `np.frombuffer(blob, np.float32)`, returning the stored 384-dim vector or `None`. The tool reads, never embeds — **no `Embedder` parameter anywhere** in `find_similar_cards`.
- **AC2 (self-exclusion by oracle):** Added the additive, backward-compatible `exclude_oracle_id: str | None = None` to `hybrid_search`; the skip happens inside the existing nearest-first de-dup loop *before* a hit consumes a `limit` slot (over-fetch/`limit` math stays correct). Excludes the whole oracle, so all printings of the seed drop — never just the passed `card_id`. Default `None` leaves the Story 2.4 path identical (its tests stay green).
- **AC3 (filters compose):** `find_similar_cards` passes `colors`/`color_mode`/`mana_value_*`/`format`/`games` straight through to `hybrid_search` — no new query logic; same hybrid path as 2.4.
- **AC4 (graceful, never raises):** `SimilarCardsResult` with `status` ∈ `ok`/`empty`/`invalid`/`not_found`/`ambiguous`. Seed resolved in **sync raw SQL** on `cards` (`_resolve_seed`, mirroring `lookup_card`'s exact-then-partial / disambiguation shape; every value bound as a parameter). `not_found` covers both "no such card" and "present but unindexed" (distinct messages); `ambiguous` returns distinct-oracle `matches`; `invalid` covers neither/both identifiers and bad color/game/mana-range/limit.
- **AC5 (stateless, in-process harness):** Registered as the **14th tool** — a sync `@mcp.tool()` `find_similar_cards` in `server.py` using only the existing `connection_factory` seam (**no `build_server` signature change**, no embedder). Per-call parameters, no server state. End-to-end coverage through `create_connected_server_and_client_session` against the reused `seeded_vec_db` fixture.
- **Reuse / scope discipline:** Imported (did not redefine) `SemanticCardHit`; reused `hybrid_search` verbatim aside from the additive arg; reused the `seeded_vec_db` fixture (no new fixture); did not touch the `Embedder`, `card_vec` schema, or index builder (frozen ports). No new dependencies; no `pyproject.toml` / `.pre-commit-config.yaml` change.
- **Verification:** new/changed offline tests pass (`test_query.py` +4, `test_find_similar_tool.py` 11 NEW, `test_mcp_tools.py` +4). Full active suite **519 passed, 3 deselected** (`-m "not integration"`; up from the 499 baseline, no regressions — NFR7). `ruff check` + `ruff format --check` clean on story files; `mypy src/` clean (46 files); `pre-commit run mypy --all-files` Passed. No new mypy `additional_dependencies` needed.

### File List

- `src/search/query.py` — MODIFIED: added `get_card_vector(conn, card_id)`; added `exclude_oracle_id` param to `hybrid_search` (skip in de-dup loop); module/`hybrid_search` docstring updates.
- `src/search/__init__.py` — MODIFIED: re-export `get_card_vector` in `__all__`; refreshed package docstring.
- `src/mcp_server/tools/find_similar.py` — NEW: `SimilarCardsResult`, `find_similar_cards`, `_resolve_seed`, `_summary_from_row`, `_validation_error`, `_decode_colors`, `_SeedResolution`.
- `src/mcp_server/server.py` — MODIFIED: import + register the sync `find_similar_cards` tool (14th); module + `build_server` docstring updates (no signature change).
- `tests/unit/search/test_query.py` — MODIFIED: 4 tests for `get_card_vector` (round-trip + `None`) and `hybrid_search(exclude_oracle_id=…)` (drop whole oracle; default preserves behaviour).
- `tests/integration/mcp_server/test_find_similar_tool.py` — NEW: 11 helper-level tests (ok / by card_id / self-exclusion / filter composition / empty / not_found ×3 / ambiguous / invalid).
- `tests/integration/test_mcp_tools.py` — MODIFIED: 4 end-to-end tests through the in-process MCP client (hosted alongside others; alternatives excluding seed oracle; format filter; bad-seed `not_found`).

## Change Log

| Date | Version | Description |
|---|---|---|
| 2026-06-22 | 0.1 | Story drafted via BMAD create-story (ultimate context engine). Surfaced the **one new mechanic** (read the seed's stored vector back from `card_vec` via a PK point-read + `np.frombuffer`, with a required de-risk spike) and that **find_similar needs no `Embedder`** (it reads, never encodes — a simplification vs. 2.4, so no `build_server` change). Locked the **oracle-id self-exclusion** (recommended additive `exclude_oracle_id` arg on the reused `hybrid_search`), the **sync raw-SQL seed resolution** mirroring `lookup_card` (async repo unreachable on the sync conn), the result envelope (`SimilarCardsResult` reusing 2.4's `SemanticCardHit`, with `not_found`/`ambiguous` statuses + echoed `seed`), and **reuse of the existing `seeded_vec_db` fixture**. Status → ready-for-dev. |
| 2026-06-22 | 1.0 | Implemented all 5 tasks (TDD red-green). De-risk spike confirmed the PK read-back on sqlite-vec v0.1.9 (1536-byte float32 BLOB → `np.frombuffer` → `(384,)`; round-trips to distance 0; missing id → `None`). Added `get_card_vector` + `exclude_oracle_id` to `query.py` (re-exported); new sync `find_similar.py` (`SimilarCardsResult` reusing `SemanticCardHit`, sync raw-SQL `_resolve_seed`, graceful `ok`/`empty`/`invalid`/`not_found`/`ambiguous`); registered the 14th tool in `server.py` (no `build_server` change, no embedder). Tests: +4 unit, +11 helper, +4 end-to-end. Full suite **519 passed** (no regressions); ruff/mypy/pre-commit clean. Optional real-corpus smoke on `Glorybringer` → sensible red-dragon alternatives, seed oracle absent, 47.8 ms. Status → review. |
