---
baseline_commit: 921545d87b467e5cc8a9bdeb507ed8a58af73d33
---

# Story 2.2: card_vec Schema with Metadata Columns

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a developer,
I want a `card_vec` `vec0` virtual table in the shared SQLite file — keyed to the relational `cards` row and carrying filterable metadata columns (`mana_value` + the five color booleans) — created through the sqlite-vec-aware `ConnectionFactory`,
so that per-card vectors live alongside the relational data and support pre-filtered KNN that the index builder (Story 2.3) populates and the search tools (Stories 2.4–2.5) query.

## Acceptance Criteria

> Source: [epics.md#Story-2.2](../planning-artifacts/epics.md) (BDD as authored), with implementation-critical clarifications folded in from analysis of the real schema, the design spec §6, and the RAG de-risk research §A. **All five must hold simultaneously.**

**AC1 — `card_vec` `vec0` virtual table exists, keyed to and JOIN-aligned with the relational `cards` table (FR13)**
- **Given** the SQLite file
- **When** the schema-creation function (and the migration script that calls it) runs through a `ConnectionFactory` connection
- **Then** a `vec0` virtual table named `card_vec` exists, JOIN-aligned with the relational `cards` table so `card_vec.card_id = cards.id`.
- **🔴 Clarification — the key column is TEXT, not an integer rowid.** The epics/research phrasing *"rowid = card_id"* assumed an **integer** id (the de-risk spike used fake integer ids `1, 2`). The **real** `cards` primary key is `id: Mapped[str]` — a **Scryfall UUID string** ([src/data/models/card.py:21](../../src/data/models/card.py#L21)). A SQLite `rowid` cannot be a UUID. Therefore declare the key as a **`card_id TEXT PRIMARY KEY`** column inside `vec0` (sqlite-vec supports TEXT primary keys), holding the exact `cards.id` UUID. JOIN-alignment is `card_vec.card_id = cards.id` (text = text) — **not** rowid arithmetic. Do **not** invent an integer surrogate; there is no integer key on `cards` to align to.

**AC2 — 384-dim embedding column + filterable metadata columns (`mana_value`, `color_{w,u,b,r,g}`)**
- **Given** `card_vec`
- **When** declared
- **Then** it has an embedding column of dimension **`EMBEDDING_DIM` (= 384, imported from [src/search/embedder.py](../../src/search/embedder.py) — never hardcode `384`)** plus metadata columns `mana_value` and `color_w`, `color_u`, `color_b`, `color_r`, `color_g` that are filterable in the `WHERE` clause of a KNN query.
- **Clarification — column types & sourcing (this story declares the columns; Story 2.3 populates them):**
  - `embedding float[EMBEDDING_DIM]` — the vector column. Keep the **default distance metric (L2)** — proven by the spike, and ranking-equivalent to cosine for the L2-normalized bge vectors (do not set `distance_metric=cosine`; defer any change to Story 2.4/2.6 tuning).
  - `mana_value integer` — sourced from `cards.cmc` (a `Float`) as `int(cmc)` at build time. Integer matches the discrete "4-drops" filter (`mana_value = 4`) and the research's validated `mana_value BETWEEN 4 AND 4` example, and avoids float-equality pitfalls in the `vec0` `WHERE` clause. (Fractional CMC exists only on non-tournament silver-border cards — out of scope for a Standard tool; flag the `int(cmc)` cast as a Story 2.3 note.)
  - `color_w/color_u/color_b/color_r/color_g integer` — five 0/1 flags sourced from `cards.colors` (the JSON colors array, e.g. `["R"]`), **not** `color_identity` — so the metadata pre-filter matches how `search_cards` interprets "a red card" ([src/data/repositories/card.py](../../src/data/repositories/card.py) `find_by_colors` / `search_advanced` use `colors`). Filter as `color_red = 1` (the spike-validated form). `integer` 0/1 is chosen over a `boolean` type for exact parity with the validated query and to avoid coercion surprises.

**AC3 — Metadata-vs-JOIN split: legality & display via JOIN, no reliance on auxiliary columns**
- **Given** the metadata-vs-JOIN design (research §A, the explicit Phase-1 decision)
- **When** the schema is created
- **Then** the **only** filterable in-`vec0` columns are the six above (`mana_value` + 5 colors); **format-legality and all display fields** (name, type_line, mana_cost, oracle_text, image_uris, rarity, set, legalities, games…) resolve via **JOIN** to `cards` on `card_vec.card_id = cards.id`, **not** as metadata columns.
- **And** no auxiliary (`+`) columns are declared in this story — auxiliary columns **cannot be filtered** (sqlite-vec [#121]) and aren't needed; the schema stays minimal (vector + key + 6 metadata).
- **Rationale:** format-legality is one-card-to-many-formats (a JSON map) and models poorly as a single metadata column; low-cardinality high-selectivity numeric/boolean filters (mana value, colors) belong in `vec0` for cheap pre-filtering, everything else via JOIN. [Source: research §A.]

**AC4 — Documented migration path: a model/dimension change rebuilds `card_vec` (NFR10)**
- **Given** a model/dimension change (e.g. swapping the embedding model or changing 384 → another dim)
- **When** it occurs
- **Then** the documented and supported migration path is to **rebuild** `card_vec` (drop + recreate, then re-run the Story 2.3 builder) — a `vec0` virtual table **cannot** be `ALTER`-ed to change vector dim or add columns.
- **Deliverable:** provide a `drop_card_vec_table(conn)` helper so rebuild = `drop_card_vec_table` → `create_card_vec_table` → re-build index; document this in the module + migration-script docstrings. Also note the ops rule: **WAL-checkpoint before any file-copy backup** of `cards.db` (NFR10).

**AC5 — Unit-tested: a vector insert plus a metadata-filtered KNN query returns the expected rows**
- **Given** the schema
- **When** tested
- **Then** inserting a few 384-dim vectors with metadata and running a metadata-filtered KNN query returns the expected `card_id`(s), and a JOIN to a relational `cards` row resolves display data — proving the TEXT-PK schema, the pre-filter, and JOIN-alignment all work on the installed `sqlite-vec` v0.1.9.
- **Test placement:** fast **unit** tests in `tests/unit/search/test_schema.py` (mirror [tests/unit/search/test_connection.py](../../tests/unit/search/test_connection.py)). These use the **real** `sqlite-vec` extension via `ConnectionFactory` on a `tmp_path` DB — but **no network and no model load** (sqlite-vec is a bundled C extension), so they are **not** `@pytest.mark.integration` (unlike the Embedder's real-model test). Insert vectors with `sqlite_vec.serialize_float32(...)` — serialization in a *test* is fine and necessary here; production serialization-in-the-builder is Story 2.3.

## Tasks / Subtasks

- [x] **Task 1 — Create the `card_vec` schema module `src/search/schema.py`** (AC: 1, 2, 3, 4)
  - [x] One-line module docstring (project convention).
  - [x] Constants as the single source of truth: `CARD_VEC_TABLE = "card_vec"`; the metadata column names (e.g. `MANA_VALUE_COL = "mana_value"`, `COLOR_COLS = ("color_w", "color_u", "color_b", "color_r", "color_g")` — or a single ordered tuple of all metadata cols). **Import `EMBEDDING_DIM` from `src.search.embedder`** for the vector dimension — do not hardcode `384` (Story 2.1 exposed this constant precisely so 2.2/2.3 import it).
  - [x] `create_card_vec_table(conn: sqlite3.Connection) -> None`: execute `CREATE VIRTUAL TABLE IF NOT EXISTS card_vec USING vec0(...)` (build the DDL via an f-string that interpolates `EMBEDDING_DIM`; see Dev Notes "Verified vec0 DDL"), then `conn.commit()`. **Idempotent** (`IF NOT EXISTS`). Precondition (documented): `conn` must come from `ConnectionFactory` (sqlite-vec loaded) — otherwise `USING vec0` raises `no such module: vec0`.
  - [x] `drop_card_vec_table(conn: sqlite3.Connection) -> None`: `DROP TABLE IF EXISTS card_vec` + `conn.commit()` — the NFR10 rebuild seam (rebuild = drop → create → re-run Story 2.3 builder). Document it.
  - [x] Full type hints (`mypy --strict`), Google-style docstrings (`Args`/`Returns`/`Raises`/`Example`) on both public functions, guard clauses over nesting, `logger = logging.getLogger(__name__)` with `%`-style lazy args (log the table create/drop). **Do not** import `sqlite_vec` here — the function only runs SQL through an already-extension-loaded connection.
- [x] **Task 2 — Migration script `scripts/migrate_add_card_vec.py`** (AC: 1, 4)
  - [x] Mirror the *shape* of [scripts/migrate_add_bug_reports.py](../../scripts/migrate_add_bug_reports.py) (module docstring, `uv run python …` usage line, ensure `./data/` parent dir exists) **but use `ConnectionFactory`, NOT `init_database`** — see Dev Notes "Why the async engine can't create `card_vec`". Build `ConnectionFactory()`, `conn = factory.get_connection()`, `create_card_vec_table(conn)`, then `factory.close()`; `print(...)` a confirmation. This script is **sync** (no `asyncio.run`).
  - [x] Resolve the DB path the same way `ConnectionFactory` does (default `./data/cards.db` via `CARDS_DATABASE_URL`); `Path(...).parent.mkdir(parents=True, exist_ok=True)` so a fresh checkout works.
- [x] **Task 3 — Export from `src/search/__init__.py`** (AC: 1)
  - [x] Add `create_card_vec_table`, `drop_card_vec_table`, and `CARD_VEC_TABLE` to the imports and `__all__` (keep `ConnectionFactory`, `Embedder`, `get_embedder`, `EMBEDDING_DIM`). Update the package docstring (the `card_vec` schema now exists; index builder + search tools still land in Stories 2.3–2.5).
- [x] **Task 4 — Unit tests `tests/unit/search/test_schema.py`** (AC: 5, 1, 2, 3) — mirror `test_connection.py` (tmp_path DB, `factory.close()` teardown, plain `def` sync tests)
  - [x] **Idempotency:** `create_card_vec_table` twice on one connection raises nothing and leaves one table.
  - [x] **Table shape:** after creation, `card_vec` exists with the declared columns (assert via a `SELECT` of the columns, or `PRAGMA table_info(card_vec)` / `table_xinfo`). Confirm the key column is `card_id` and the metadata columns are present.
  - [x] **Insert + plain KNN:** insert ≥3 distinct 384-dim vectors (TEXT UUID-style `card_id`s) via `INSERT INTO card_vec(card_id, embedding, mana_value, color_w, …) VALUES (?, sqlite_vec.serialize_float32(vec), ?, …)`; run `SELECT card_id, distance FROM card_vec WHERE embedding MATCH ? AND k = ?` and assert the nearest `card_id` is the expected one.
  - [x] **Metadata-filtered KNN (the core AC):** mirror the spike — query with `… AND k = N AND mana_value = 4 AND color_r = 1` and assert the off-filter card (e.g. `mana_value = 2`) is excluded from results.
  - [x] **JOIN-alignment (proves AC1/AC3 with a TEXT PK):** create a tiny `cards(id TEXT PRIMARY KEY, name TEXT)` table on the same connection, insert rows whose `id` matches the inserted `card_id`s, then `SELECT c.name, v.distance FROM card_vec v JOIN cards c ON c.id = v.card_id WHERE v.embedding MATCH ? AND k = ?` and assert the display field resolves.
  - [x] **Drop:** `drop_card_vec_table` removes the table (subsequent `SELECT … FROM card_vec` raises `no such table`).
  - [x] Use a 384-dim helper (e.g. a near-one-hot or simple deterministic vector per card) so distances are well-separated and assertions are stable; **no hardcoded `/tmp`** paths (Story 1.2 review lesson — use `tmp_path`).
- [x] **Task 5 — Verify (run the commands, capture output)** (AC: all)
  - [x] `uv run pytest tests/unit/search/test_schema.py -v` → new unit tests pass (fast, offline, real sqlite-vec).
  - [x] `uv run pytest tests/ -m "not integration"` → full active suite still green (no regressions; baseline **455 passed** after Story 2.1).
  - [x] `uv run ruff check .` and `uv run ruff format --check .` → clean for all story-authored files (`src/search/schema.py`, `scripts/migrate_add_card_vec.py`, `src/search/__init__.py`, `tests/unit/search/test_schema.py`). (Pre-existing unrelated ruff issues in `_bmad/scripts/*` and `src/mcp_server/tools/card_lookup.py` are out of scope — do not reformat them.)
  - [x] `uv run mypy src/` → clean. Run `uv run pre-commit run mypy --all-files` too (the isolated env already has `mcp`+`numpy` from Story 2.1; `sqlite_vec` is stub-less and covered by `ignore_missing_imports`, so **no new `additional_dependencies` are needed**).
  - [x] (Optional sanity) run `uv run python scripts/migrate_add_card_vec.py` against a throwaway `CARDS_DATABASE_URL` to confirm the script creates the table end-to-end, then discard that DB.

### Review Findings

- [x] [Review][Patch] `_INSERT_SQL` in tests hardcodes color column names instead of using `COLOR_COLS` constant [tests/unit/search/test_schema.py:26-28]
- [x] [Review][Patch] Shape test negative assertion is vacuous; no `PRAGMA table_xinfo` column-type verification for AC2 types [tests/unit/search/test_schema.py:111-117]
- [x] [Review][Defer] Tests call `factory.close()` without try/finally teardown — mirrors inherited pattern from test_connection.py [tests/unit/search/test_schema.py] — deferred, pre-existing
- [x] [Review][Defer] Migration CWD-relative DB path consistent with `ConnectionFactory` default — pre-existing pattern [scripts/migrate_add_card_vec.py] — deferred, pre-existing
- [x] [Review][Defer] `mana_value integer` column accepts Python float inputs without coercion at schema layer — Story 2.3 responsibility [src/search/schema.py] — deferred, pre-existing

## Dev Notes

### What this story IS — and is NOT

- **IS:** the **schema** half of the RAG index — a thin `src/search/schema.py` that **declares and creates** the `card_vec` `vec0` virtual table (TEXT `card_id` PK + `float[384]` embedding + 6 filterable metadata columns), a `drop` helper for the NFR10 rebuild path, a migration script that runs it through `ConnectionFactory`, the package export, and a fast unit test proving insert + metadata-filtered KNN + JOIN. It is the **sibling** of Story 1.2's `ConnectionFactory` and Story 2.1's `Embedder` — same package, same "thin unit + test + scope discipline" shape. This is research design-delta #4 ("`card_vec` schema — metadata cols mana_value + 5 color booleans") [Source: [research §A / §6 deltas](../planning-artifacts/research/technical-sqlite-vec-fastembed-rag-stack-on-windows-research-2026-06-20.md); [epics.md "card_vec schema"](../planning-artifacts/epics.md)].
- **IS NOT:** the **index builder** (Story 2.3 — composing per-card text `name + type_line + mana_cost + oracle_text + keywords`, batch-embedding 60k cards, serializing, the content-hash incremental logic, **populating** the metadata column *values*), the `semantic_search_cards` / `find_similar_cards` tools (Stories 2.4–2.5), or the RAG sanity eval (Story 2.6). **Do not** embed any real cards, compose card text, build a content hash, wire an MCP tool, or write the production INSERT loop here. This story creates an **empty** table and proves its shape with synthetic vectors. Resist scaffolding ahead — Stories 1.2 and 2.1 set this precedent and both code reviews rewarded it.

### 🔴 The card_id type — the one correction that prevents a build-blocking mistake

Every planning doc says `card_vec` is *"keyed by `card_id`, rowid = card_id"*. **That parenthetical is wrong for this codebase** and a dev following it literally will hit a wall:

- The **real** `cards` PK is a **Scryfall UUID string**: `id: Mapped[str] = mapped_column(String, primary_key=True)` ([src/data/models/card.py:21](../../src/data/models/card.py#L21)). Decks use UUID string PKs too ([src/data/models/deck.py](../../src/data/models/deck.py)).
- A SQLite **`rowid` is a 64-bit integer** — it **cannot** hold a UUID. The de-risk spike that wrote "rowid = card_id" used **fake integer ids** (`hybrid KNN (k=2, mana_value=4): [(1, 0.0), (2, 1.5999)]`) — it never exercised the real UUID PK. [Source: [research §Empirical spike](../planning-artifacts/research/technical-sqlite-vec-fastembed-rag-stack-on-windows-research-2026-06-20.md#L221-L226).]
- **Resolution (verified):** `sqlite-vec`'s `vec0` supports a **TEXT primary key**. Declare `card_id TEXT PRIMARY KEY` and store the exact `cards.id` UUID. JOIN-alignment is then `card_vec.card_id = cards.id` (text-to-text). [Source: sqlite-vec `vec0` docs (context7 `/asg017/sqlite-vec`); [metadata release post](https://alexgarcia.xyz/blog/2024/sqlite-vec-metadata-release/index.html).]

> Interpret FR13's intent ("vectors and relational rows are JOIN-aligned"), not its integer-shaped wording. The schema satisfies the *intent* via a TEXT key; it physically cannot satisfy the *literal* "rowid = UUID".

### Verified `vec0` DDL (sqlite-vec v0.1.9, the installed wheel)

```sql
CREATE VIRTUAL TABLE IF NOT EXISTS card_vec USING vec0(
    card_id TEXT PRIMARY KEY,        -- = cards.id (Scryfall UUID); JOIN key, not an integer rowid
    embedding float[384],            -- 384 == EMBEDDING_DIM (import it; default L2 distance)
    mana_value integer,              -- int(cards.cmc); pre-filter, populated by Story 2.3
    color_w integer,                 -- 0/1 from ("W" in cards.colors)
    color_u integer,
    color_b integer,
    color_r integer,
    color_g integer
);
```

- Build the dim from the constant: `f"CREATE VIRTUAL TABLE IF NOT EXISTS {CARD_VEC_TABLE} USING vec0(card_id TEXT PRIMARY KEY, embedding float[{EMBEDDING_DIM}], …)"`. (The dim is a literal in the DDL string — there is no bind-parameter form for `float[N]`.)
- **Metadata columns** are declared as ordinary typed columns inside the `vec0` constructor and are usable in a KNN `WHERE`. [Source: context7 `vec0` examples — `genre text, num_reviews int, mean_rating float, contains_violence boolean`.]
- **Every KNN query needs `k = ?` (or `LIMIT`)** — mandatory on `vec0` ([#116]). The metadata pre-filter (`AND mana_value = 4 AND color_r = 1`) is applied KNN-aware *before* distance, the fastest path. [Source: research §A Pattern 1.]
- **Auxiliary (`+col`) columns are NOT used** (AC3): they can be stored but **cannot be filtered** ([#121]); display data comes from the JOIN instead.

### KNN + JOIN query shape (for the test now; for Stories 2.4–2.5 later)

```sql
-- metadata pre-filter KNN, then JOIN for display/legality
SELECT c.name, c.type_line, v.distance
FROM card_vec v
JOIN cards c ON c.id = v.card_id
WHERE v.embedding MATCH :query_vec
  AND v.k = 20                       -- mandatory
  AND v.mana_value = 4
  AND v.color_r = 1
ORDER BY v.distance;                 -- (over-fetch k, then add JOIN-side predicates — Story 2.4)
```

### Why the async SQLAlchemy engine can NOT create `card_vec` (the migration divergence)

The existing migrations ([scripts/migrate_add_bug_reports.py](../../scripts/migrate_add_bug_reports.py)) run `init_database` → `Base.metadata.create_all` over the **async aiosqlite engine** ([src/data/database.py](../../src/data/database.py)). That engine **does not call `enable_load_extension` / `sqlite_vec.load`**, so `CREATE VIRTUAL TABLE … USING vec0` would fail there with `no such module: vec0`. `card_vec` is therefore created **only** through `ConnectionFactory` (sync `sqlite3`, sqlite-vec loaded, WAL on) — the exact reason that port exists ([src/search/connection.py](../../src/search/connection.py)). Keep the relational schema (cards/decks/bug_reports) on the async engine and the vector table on the sync factory; they share the **same `cards.db` file**, which is the whole point of the single-file topology (D2). Do **not** add `card_vec` to `Base.metadata` or to `init_database`.

### Content-hash storage is Story 2.3's call — keep `card_vec` stable

Story 2.3 needs a per-card **content hash** for incremental rebuilds. **Do not add it to `card_vec` here.** Two reasons: (1) it's out of 2.2's AC scope (the epics list only embedding + mana_value + colors); (2) a `vec0` table **cannot be `ALTER`-ed** to add a column later — adding the hash to `card_vec` would force a full rebuild. **Recommend** (flag for Story 2.3) that the hash live in a small **companion relational table** (e.g. `card_embedding_meta(card_id TEXT PRIMARY KEY, content_hash TEXT)`, created on the async engine), so `card_vec` stays purely vector+pre-filter and the builder reads/writes hashes JOIN-side. This keeps the schema you create now stable across all of Epic 2.

### Distance metric — keep the default (L2), don't bikeshed

The spike used the **default** distance metric (L2 / euclidean) and ranked the dragons correctly. bge vectors are **L2-normalized** (Story 2.1 returns them un-renormalized), and for normalized vectors **L2 ordering == cosine ordering** (monotonic: `L2² = 2 − 2·cos`). So declaring nothing (default L2) is the proven, minimal choice. `distance_metric=cosine` is available and ranking-equivalent; if Stories 2.4/2.6 want interpretable cosine *values* (e.g. a similarity threshold), that's their tuning decision and a `card_vec` rebuild at that point — not a 2.2 concern. [Source: [research §Empirical spike](../planning-artifacts/research/technical-sqlite-vec-fastembed-rag-stack-on-windows-research-2026-06-20.md).]

### Serialization boundary (`serialize_float32` is test-only in this story)

`sqlite_vec.serialize_float32(vec)` (alias `serialize_f32`) turns a float list / `float32` numpy array into the BLOB the embedding column expects (fastembed already emits `float32`; `.astype(np.float32)` is a safety net). Story 2.1's anti-patterns reserved *production* serialization for Story 2.3 — that still holds. **But** AC5 requires inserting a vector to prove the schema, so calling `sqlite_vec.serialize_float32(...)` **inside `test_schema.py`** is correct and necessary here; just don't build a production INSERT loop in `src/`. [Source: [research §B](../planning-artifacts/research/technical-sqlite-vec-fastembed-rag-stack-on-windows-research-2026-06-20.md); sqlite-vec Python docs.]

### Operations — NFR10

- **Rebuild = the only schema migration for vectors.** A model swap or dim change ⇒ `drop_card_vec_table` → `create_card_vec_table` → re-run the Story 2.3 builder. `vec0` has no in-place `ALTER`. Document this in the module + script docstrings.
- **Backups:** WAL-checkpoint (`PRAGMA wal_checkpoint(TRUNCATE)`) before any file-copy backup of `cards.db`, or the latest vectors may sit unflushed in the `-wal` file. (Operational note for docs; not code in this story.) [Source: [research §Deployment & Operations](../planning-artifacts/research/technical-sqlite-vec-fastembed-rag-stack-on-windows-research-2026-06-20.md#L268-L272).]

### Testing standards (from project-context.md + repo conventions)

- pytest config in `pyproject.toml`: `asyncio_mode = "auto"`, `--strict-markers`, `--tb=short`, verbose; `testpaths = ["tests"]`. The schema functions are **sync** → plain `def test_…` (no `async`, no `@pytest.mark.asyncio`).
- Layout **mirrors `src/`**: `tests/unit/search/test_schema.py` (the `tests/unit/search/` package already exists from Stories 1.2/2.1). Naming `test_*.py` / `test_*`. `tests.*` is exempt from `mypy --strict` but still ruff-clean.
- **No `integration` marker.** Unlike the Embedder's real-model test (which downloads ~80 MB), this test uses the **bundled** sqlite-vec C extension via `ConnectionFactory` — no network, no model — so it's a fast **unit** test. `test_connection.py` already runs real sqlite-vec in `tests/unit/search/`; follow that exactly (tmp_path DB, `factory.close()` teardown). [Source: [tests/unit/search/test_connection.py](../../tests/unit/search/test_connection.py); [project-context.md](../project-context.md) "Testing Rules".]
- This story has **no RAG-recall dimension** — recall is Story 2.6's job. AC5 only proves the *schema mechanics* (insert/filter/JOIN), not embedding quality.

### Anti-patterns (do NOT do these)

- ❌ Declare `card_id integer primary key` / try to map the UUID to a rowid — the PK is a UUID string; use `card_id TEXT PRIMARY KEY` (the headline correction above).
- ❌ Invent an integer surrogate key for cards — there is none on `cards`; it would break JOIN-alignment.
- ❌ Add `card_vec` to `Base.metadata` / `init_database` / the async engine — `USING vec0` needs the sqlite-vec extension, which only `ConnectionFactory` loads.
- ❌ Hardcode `384` — import `EMBEDDING_DIM` from `src.search.embedder`.
- ❌ Add a content-hash column (or any `+aux` column) to `card_vec` — out of scope, can't be filtered, and would force a rebuild later; that's Story 2.3 (companion table).
- ❌ Set `distance_metric=cosine` speculatively — keep the proven default L2; defer to 2.4/2.6.
- ❌ Populate real card vectors / compose per-card text / build the incremental loop — Story 2.3.
- ❌ Forget `k = ?` / `LIMIT` on a KNN query — it's mandatory on `vec0` (and a perf cliff if you scan unbounded).
- ❌ Make the schema functions `async` — they run on the sync `ConnectionFactory` path (like `ConnectionFactory` itself).
- ❌ `print()` in `src/` library code — module-level `logger` + `%`-style lazy args; module docstring required. (`print` is fine in the `scripts/` migration.)
- ❌ Hardcode `/tmp/...` in tests (Story 1.2 review caught this) — use `tmp_path`.

### Previous Story Intelligence (Stories 1.2 + 2.1 — the direct templates)

- **The shape to mirror:** Story 1.2 (`ConnectionFactory`) and Story 2.1 (`Embedder`) both delivered a thin `src/search/` port + module constants + a `_resolve_*`/teardown seam + full strict typing + Google docstrings + focused unit tests, with strict scope discipline. `schema.py` is the third sibling — same structure, same discipline. [Source: [1-2-*.md](./1-2-sqlite-connectionfactory-with-wal-extension-loading.md); [2-1-*.md](./2-1-embedder-port-fastembed-singleton-persistent-cache.md).]
- **Code-review patterns that recurred (pre-empt them):** (1) **relative-path → absolute** bug — Story 2.1's `_DEFAULT_CACHE_DIR` resolved against CWD and got a High finding; here the DB path comes from `ConnectionFactory`/`CARDS_DATABASE_URL`, so don't reintroduce a CWD-relative default in the migration script — let the factory resolve it. (2) **cleanup-on-error** — `ConnectionFactory._build_connection` wraps the load sequence in `try/except: conn.close(); raise`; you're reusing that connection, so just don't swallow DDL errors. (3) **Windows path test bug** — use `tmp_path`, never `/tmp`. (4) **Google-style `Example:` sections** were required on every public function in 2.1's review — include them. [Source: [2-1 Review Findings](./2-1-embedder-port-fastembed-singleton-persistent-cache.md#L295-L316); [1-2 Review](./1-2-sqlite-connectionfactory-with-wal-extension-loading.md).]
- **Baseline is green at 455 passed** (`-m "not integration"`) after Story 2.1; `legacy/` excluded. Keep it green (NFR7). [Source: [2-1 Debug Log](./2-1-embedder-port-fastembed-singleton-persistent-cache.md#L255-L260).]
- **`EMBEDDING_DIM = 384`** is already exported from `src/search` (Story 2.1) for exactly this consumer — import it.

### Git Intelligence

- HEAD `921545d` "fix: harden Embedder port …" closed Story 2.1's review. `6ebcdf3` added the Embedder. The Epic-2 cadence is established: thin `src/search` port → unit tests → run-and-capture verify → scope discipline. This story is the next link (embedder → **schema** → builder → tools → eval).
- `src/search/` currently holds `connection.py` + `embedder.py` (+ `__init__.py`); `schema.py` is **green-field** within it. No `card_vec` exists anywhere yet. [Source: `git log`; [src/search/](../../src/search/).]
- Migration scripts are a small, consistent family in `scripts/migrate_*.py` — `migrate_add_card_vec.py` joins them, but is the **first** to use `ConnectionFactory` instead of the async engine (call that out in its docstring). [Source: [scripts/](../../scripts/).]
- No working-tree noise expected — unlike Story 2.1 (which folded in pre-existing `.env.example`/`README.md` edits), the tree is clean at this baseline.

### Latest Tech / Versions (verified for THIS project, 2026-06-21)

| Item | Value | Source |
|---|---|---|
| `sqlite-vec` | **v0.1.9** (bundled wheel; loads cleanly on this Windows build, no fallback driver) | [research §Empirical spike](../planning-artifacts/research/technical-sqlite-vec-fastembed-rag-stack-on-windows-research-2026-06-20.md); `select vec_version()` in [test_connection.py](../../tests/unit/search/test_connection.py) |
| `vec0` TEXT PK | **Supported** — `CREATE VIRTUAL TABLE … USING vec0(id TEXT PRIMARY KEY, embedding float[N], …)` | context7 `/asg017/sqlite-vec` `vec0` docs; [metadata release post](https://alexgarcia.xyz/blog/2024/sqlite-vec-metadata-release/index.html) |
| Metadata columns | Since **v0.1.6**; typed cols (`int`/`float`/`text`/`boolean`) filterable in KNN `WHERE`; **`k`/`LIMIT` mandatory** ([#116]); aux `+col` not filterable ([#121]) | research §A; context7 `vec0` examples |
| Serialization | `sqlite_vec.serialize_float32(list|ndarray)` → BLOB (alias `serialize_f32`) | research §B; sqlite-vec Python docs |
| `EMBEDDING_DIM` | **384** (`from src.search import EMBEDDING_DIM`) | [src/search/embedder.py](../../src/search/embedder.py); Story 2.1 |
| `cards.id` | **TEXT** (Scryfall UUID), PK; `cards.cmc` is **Float**; `cards.colors` is JSON `list[str]` | [src/data/models/card.py](../../src/data/models/card.py) |
| Python / SQLite | CPython 3.12.13 / SQLite 3.50.4 / Windows / uv | [project-context.md](../project-context.md) "Verified platform envelope" |

### Project Structure Notes

Target additions (everything else unchanged):

```
src/
  search/
    __init__.py        # MODIFIED — also re-export create_card_vec_table, drop_card_vec_table, CARD_VEC_TABLE
    connection.py      # (unchanged, Story 1.2) — the sync seam card_vec is created through
    embedder.py        # (unchanged, Story 2.1) — import EMBEDDING_DIM from here
    schema.py          # NEW — card_vec vec0 DDL: create_card_vec_table / drop_card_vec_table + CARD_VEC_TABLE/col constants
scripts/
  migrate_add_card_vec.py  # NEW — creates card_vec via ConnectionFactory (NOT init_database); uv run python …
tests/
  unit/
    search/
      test_schema.py       # NEW — fast unit tests: idempotency, shape, insert+metadata-filtered KNN, JOIN-alignment, drop
```

- **Alignment:** matches spec §4 (`src/search` = "embedding model wrapper + sqlite-vec integration + index builder") and research roadmap step 2 ("Search core — … `card_vec` schema (metadata cols: mana_value + 5 color booleans) …"). [Source: [design spec §4/§6](../../docs/architecture.md); [research §8](../planning-artifacts/research/technical-sqlite-vec-fastembed-rag-stack-on-windows-research-2026-06-20.md).]
- **Layering check:** `src/search` is a sync infra package consumed *downward* by `scripts/` (Story 2.3 builder) and `src/mcp_server` (Stories 2.4–2.5) — no upward import, no cycle. `schema.py` imports only stdlib + `EMBEDDING_DIM` from its sibling `embedder.py`. ✅
- **No new dependencies / no `pyproject.toml` or `.pre-commit-config.yaml` changes** — sqlite-vec is already a core dep (Story 1.1) and the pre-commit mypy env already resolves what's needed.

### References

- [epics.md — Epic 2 / Story 2.2](../planning-artifacts/epics.md) — user story, the five BDD ACs, the "`card_vec` schema" additional requirement (metadata cols `mana_value` + `color_{w,u,b,r,g}`; legality/display via JOIN; aux `+` not filterable; rebuild on model/dim change).
- [research — RAG de-risk §A / §B / §Data Architecture / §Empirical spike / §Deployment](../planning-artifacts/research/technical-sqlite-vec-fastembed-rag-stack-on-windows-research-2026-06-20.md) — the metadata-vs-JOIN decision (Pattern 1+2 hybrid), serialization, single-file topology (`rowid = card_id` written against fake integer ids), the validated `mana_value`/`color_red` pre-filter, the rebuild/WAL-checkpoint ops rules.
- [design spec §3 (D2) / §4 / §6](../../docs/architecture.md) — `sqlite-vec` + `bge-small-en-v1.5`; `src/search` restructure; `card_vec` in the same file keyed by `card_id`, JOIN-able; hybrid query path.
- [src/data/models/card.py](../../src/data/models/card.py) — **`cards` PK is a UUID string**; `cmc` Float; `colors` JSON — the facts that force a TEXT PK and inform metadata sourcing.
- [src/search/connection.py](../../src/search/connection.py) / [tests/unit/search/test_connection.py](../../tests/unit/search/test_connection.py) — the sync seam that loads sqlite-vec, and the exact unit-test style (tmp_path, `factory.close()`, real extension) to mirror.
- [src/search/embedder.py](../../src/search/embedder.py) — exports `EMBEDDING_DIM` to import; the sibling-port shape to match.
- [scripts/migrate_add_bug_reports.py](../../scripts/migrate_add_bug_reports.py) — migration-script shape to mirror (but swap `init_database` → `ConnectionFactory`).
- [Story 2.1](./2-1-embedder-port-fastembed-singleton-persistent-cache.md) / [Story 1.2](./1-2-sqlite-connectionfactory-with-wal-extension-loading.md) — port precedents, review findings (relative-path, cleanup-on-error, Windows path test, `Example:` docstrings), green baseline.
- [project-context.md](../project-context.md) — RAG rules ("`card_vec` in the same DB file keyed by `card_id`", "every KNN query needs `k`/`LIMIT`", metadata cols `mana_value` + colors, "model/dimension change requires rebuilding `card_vec`"), sync-vs-async boundary, testing layout, ruff/mypy gates.

## Dev Agent Record

### Agent Model Used

claude-opus-4-8[1m] (Claude Opus 4.8, 1M context) — BMAD dev-story workflow.

### Debug Log References

- Initial test draft indexed KNN rows by column name (`row[CARD_ID_COL]`); `ConnectionFactory`
  connections use the default **tuple** row factory (no `sqlite3.Row`), so switched to positional
  indexing (`row[0]`) and documented it in the `_knn` helper.
- `ruff check` flagged four `E501` (>100) lines (the migration `print`, two test docstrings, the
  `_INSERT_SQL` column list); wrapped/shortened them. `ruff format` then collapsed the migration
  `print` f-string back onto one line (98 cols inside `print(...)`) — applied and re-verified clean.

### Completion Notes List

- **Task 1 — `src/search/schema.py`:** thin sync module declaring the `card_vec` `vec0` schema.
  `create_card_vec_table` / `drop_card_vec_table` run DDL through an already-extension-loaded
  connection (no `import sqlite_vec` in `src/`); `_build_create_ddl` interpolates `EMBEDDING_DIM`
  (imported from `src.search.embedder` — **not** hardcoded `384`). Key is `card_id TEXT PRIMARY KEY`
  (Scryfall UUID, not an integer rowid), six filterable metadata cols (`mana_value` + `color_w/u/b/r/g`),
  default L2 distance, `IF NOT EXISTS` idempotency. Constants (`CARD_VEC_TABLE`, `CARD_ID_COL`,
  `EMBEDDING_COL`, `MANA_VALUE_COL`, `COLOR_COLS`, `METADATA_COLS`) are the single source of truth
  for Stories 2.3–2.5. Full strict typing + Google docstrings with `Example:` sections.
- **Task 2 — `scripts/migrate_add_card_vec.py`:** sync migration that creates `card_vec` via
  `ConnectionFactory` (the **first** migration to do so, not `init_database` — the async engine
  can't load `vec0`). Lets the factory resolve the DB path (no CWD-relative default — Story 2.1
  review lesson); ensures the parent dir exists; `factory.close()` in `finally`.
- **Task 3 — `src/search/__init__.py`:** re-exports `create_card_vec_table`, `drop_card_vec_table`,
  `CARD_VEC_TABLE` (kept `ConnectionFactory`, `Embedder`, `get_embedder`, `EMBEDDING_DIM`); package
  docstring updated.
- **Task 4 — `tests/unit/search/test_schema.py`:** 7 fast unit tests over the **real** bundled
  sqlite-vec extension (no network, no model load → not `integration`): create-idempotency, table
  shape (TEXT key + 6 metadata cols present, bogus col absent), insert + plain KNN nearest, the core
  **metadata-filtered KNN** excluding the nearest off-filter card, **JOIN-alignment** (`card_vec.card_id
  = cards.id`, TEXT=TEXT) resolving a display field, drop-removes-table, drop-idempotent. `tmp_path`
  DB + `factory.close()` teardown (no `/tmp`); `sqlite_vec.serialize_float32` test-only inserts.
- **Scope discipline (per Dev Notes):** created an **empty** table proven with synthetic vectors —
  no real-card embedding, text composition, content hash, production INSERT loop, `Base.metadata`
  registration, or `distance_metric=cosine`. Content hash deferred to a Story 2.3 companion table.
- **Task 5 — Verify (all green):** new tests `7 passed`; full active suite `465 passed, 1 deselected`
  (`-m "not integration"`, no regressions vs the 455 baseline + 7 new + pre-existing); `ruff check` /
  `ruff format --check` clean on authored files; `mypy src/` clean (42 files); `pre-commit run mypy
  --all-files` Passed; optional end-to-end migration against a throwaway DB created `card_vec`
  (`sqlite_master row: ('card_vec',)`), then discarded.

### File List

- `src/search/schema.py` — **NEW**: `card_vec` `vec0` DDL (`create_card_vec_table` /
  `drop_card_vec_table` + table/column constants).
- `scripts/migrate_add_card_vec.py` — **NEW**: sync migration creating `card_vec` via `ConnectionFactory`.
- `tests/unit/search/test_schema.py` — **NEW**: 7 unit tests (idempotency, shape, KNN, metadata
  pre-filter, JOIN-alignment, drop).
- `src/search/__init__.py` — **MODIFIED**: export `create_card_vec_table`, `drop_card_vec_table`,
  `CARD_VEC_TABLE`; updated package docstring.

_Process artifacts also updated: this story file (Tasks/checkboxes, Dev Agent Record, Status) and
`_bmad-output/implementation-artifacts/sprint-status.yaml` (2-2 → in-progress → review)._

## Change Log

| Date | Version | Description |
|---|---|---|
| 2026-06-21 | 0.1 | Story drafted via BMAD create-story (ultimate context engine). Surfaced the `card_id` TEXT-PK correction (real `cards.id` is a Scryfall UUID, not an integer rowid), the ConnectionFactory-only creation seam (async engine can't load `vec0`), the metadata-vs-JOIN split, default-L2 decision, and the content-hash → companion-table forward note. Status → ready-for-dev. |
| 2026-06-21 | 1.0 | Implemented `card_vec` `vec0` schema (`src/search/schema.py`: TEXT-PK + `float[EMBEDDING_DIM]` + 6 metadata cols, create/drop), ConnectionFactory-based migration script, package exports, and 7 unit tests (insert + metadata-filtered KNN + JOIN-alignment + drop on real sqlite-vec). All verify gates green (465 passed, ruff/mypy/pre-commit clean, e2e migration confirmed). Status → review. |
