---
baseline_commit: 1d2b7a262a932722b5cc325808de8467f0853fd8
---

# Story 2.3: Card Embedding Index Builder (idempotent & incremental)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a developer,
I want a `build_card_embeddings` index builder — pure, unit-testable logic in `src/search/index_builder.py` driven by a thin `scripts/build_card_embeddings.py` CLI — that composes per-card text (`name + type_line + mana_cost + oracle_text + keywords`), batch-embeds every card through the Story 2.1 `Embedder`, serializes to `float32`, and writes vectors + filterable metadata into the Story 2.2 `card_vec` table keyed by `card_id`, tracking a per-card **content hash** so re-runs re-embed **only** new or changed cards,
so that the semantic index builds once in minutes and future Scryfall imports update it incrementally — feeding the search tools (Stories 2.4–2.5) and the RAG eval (Story 2.6).

## Acceptance Criteria

> Source: [epics.md#Story-2.3](../planning-artifacts/epics.md) (BDD as authored), with implementation-critical clarifications folded in from the **empirical vec0 spike** (run on the installed `sqlite-vec` v0.1.9 against a real TEXT primary key), the real `cards` schema, the design spec §6, and the RAG de-risk research §A/§B. **All five must hold simultaneously.**

**AC1 — First build: compose text, batch-embed, serialize float32, insert into `card_vec` keyed by `card_id` (FR14, FR15)**
- **Given** the populated `cards` table
- **When** the builder runs the first time
- **Then** for every card it composes the per-card text `name + type_line + mana_cost + oracle_text + keywords`, batch-embeds through the Story 2.1 `Embedder`, serializes each vector to `float32` via `sqlite_vec.serialize_float32`, and inserts a `card_vec` row keyed by the **TEXT** `card_id` (= `cards.id`, a Scryfall UUID) with its six metadata columns populated.
- **Clarification — metadata values this story finally populates (Story 2.2 only declared the empty columns):**
  - `mana_value = int(cards.cmc)` — `cmc` is a `Float` ([src/data/models/card.py:32](../../src/data/models/card.py#L32)); cast to `int` at insert (Story 2.2 deferred this cast here). Fractional CMC exists only on out-of-scope silver-border cards; `int()` truncation is acceptable and documented.
  - `color_w/u/b/r/g` — five 0/1 flags from the JSON `cards.colors` array (e.g. `["R"]` → `color_r=1`), **not** `color_identity` (parity with how `search_cards` reads "a red card"). Build the flags in the exact [`COLOR_COLS`](../../src/search/schema.py#L17) order (`color_w, color_u, color_b, color_r, color_g` ↔ MTG `W,U,B,R,G`).
- **And** the embedding column holds the **raw** bge vector from `Embedder` (already L2-normalized — do **not** re-normalize); production serialization now lives in `src/search` (Story 2.2 kept `serialize_float32` test-only; that boundary ends here).

**AC2 — Incremental: a per-card content hash means a re-run re-embeds only new/changed cards (FR15)**
- **Given** a content hash of the composite text stored per card in a **companion relational table** `card_embedding_meta(card_id TEXT PRIMARY KEY, content_hash TEXT)`
- **When** the builder re-runs
- **Then** it re-embeds a card **only** if it is new (no stored hash) or changed (stored hash ≠ freshly computed hash); cards whose hash is unchanged are **skipped** (not re-embedded).
- **🔴 Clarification — the content hash detects *text* changes, NOT model/dimension changes.** The hash is `sha256(composite_text)` — a pure function of card content. A model swap or `EMBEDDING_DIM` change leaves every card's text (and therefore its hash) identical, so the incremental path would **silently skip all cards and never re-embed with the new model**. Routing model/dim changes is AC5's explicit **rebuild** path (`--rebuild`), **not** the hash. Do not fold model identity into the hash; keep the hash a clean "did this card's text change?" signal and document the rebuild requirement.

**AC3 — No duplicate vectors; an interrupted or re-run build converges to a complete index (FR15)**
- **Given** an interrupted or re-run build
- **When** executed again
- **Then** it converges to a complete index with **no duplicate vectors** and no orphan hashes (a card is never hash-recorded without its vector, or vice-versa).
- **🔴 Clarification — `INSERT OR REPLACE` is BROKEN on `vec0`; you MUST DELETE-then-INSERT (verified).** On the installed `sqlite-vec` v0.1.9, re-inserting an existing `card_id` raises `OperationalError: UNIQUE constraint failed on card_vec primary key`, and **`INSERT OR REPLACE` raises the *same* error** — `vec0` does not honour `OR REPLACE` conflict resolution (it works for the relational `cards` table, which is why the Scryfall importer uses it — do **not** copy that pattern here). `DELETE FROM card_vec WHERE card_id = ?` and `UPDATE card_vec SET … WHERE card_id = ?` both work. The supported re-write of a changed card is therefore **`DELETE` then `INSERT`** (or `UPDATE` in place). New cards are a plain `INSERT`. Write the `card_vec` row and its `card_embedding_meta` hash in the **same per-batch transaction**, committing per batch, so an interruption between batches leaves completed batches durable and consistent and the in-flight batch rolls back cleanly.

**AC4 — Full build finishes in minutes, logs progress/counts, and the vector footprint is in the expected range (NFR3, NFR4)**
- **Given** the full build
- **When** it completes
- **Then** it finishes in **minutes** (first-run also performs the one-time ~80 MB model download, which is separate) and logs periodic progress plus a final summary (processed / embedded-new / embedded-changed / skipped / elapsed / cards-per-second).
- **🔴 Clarification — footprint scales to the *actual* card count; this DB has 38,232 cards, not 60k.** The epics/NFR4 "~92 MB" figure assumes the full ~60k-card Scryfall set; the installed `./data/cards.db` holds **38,232 cards** (verified), so the expected raw vector footprint is ≈ `38,232 × 384 × 4 B ≈ 56–59 MB`, not 92 MB. **Do not assert a hard 92 MB threshold** (it would false-fail). Log the actual on-disk delta and sanity-check it against `~1.5 KB/card × card_count` (order-of-magnitude), not a fixed constant. [Source: live DB inspection 2026-06-21; NFR4.]

**AC5 — Invocable as a uv script, with a documented `--rebuild` path for model/dimension changes (FR15, NFR10)**
- **Given** the builder
- **When** run via a uv command (`uv run python scripts/build_card_embeddings.py`)
- **Then** it is invocable as a script — self-bootstrapping (ensures both `card_vec` and `card_embedding_meta` exist via idempotent `create_*`), reading config the same way every `src/search` consumer does (`ConnectionFactory` / `CARDS_DATABASE_URL`).
- **And** a `--rebuild` flag implements the NFR10 model/dimension-change migration: `drop_card_vec_table` → `create_card_vec_table` → **clear `card_embedding_meta`** → full re-embed (clearing the hashes is mandatory — see AC2's gotcha, or `--rebuild` would skip everything). A `--limit N` affordance (embed only the first N cards) supports fast dev/test runs without a full 38k build.

## Tasks / Subtasks

- [x] **Task 1 — Companion hash table schema in `src/search/schema.py`** (AC: 2, 5) — extend the existing Story 2.2 module; keep it the single home for all search-index DDL
  - [x] Add constants beside the `card_vec` ones: `CARD_EMBEDDING_META_TABLE = "card_embedding_meta"`, `META_CARD_ID_COL = "card_id"` (reuse `CARD_ID_COL`), `CONTENT_HASH_COL = "content_hash"`. *(Reused `CARD_ID_COL` for the PK column per the note; no separate `META_CARD_ID_COL` constant added — documented on `CONTENT_HASH_COL`.)*
  - [x] `create_card_embedding_meta_table(conn: sqlite3.Connection) -> None`: `CREATE TABLE IF NOT EXISTS card_embedding_meta(card_id TEXT PRIMARY KEY, content_hash TEXT NOT NULL)` + `conn.commit()`. **Idempotent.** This is an **ordinary relational table** (no `vec0`, no extension needed) — but it is created through the **same sync `ConnectionFactory` connection** as `card_vec` so the whole index pipeline stays on one connection/script (the search-index schema rule: `card_vec` + `card_embedding_meta` live on the sync factory, alongside the async-engine relational schema in the *same file*). Full type hints, Google docstring with `Example:`, `logger` `%`-style lazy args.
  - [x] `clear_card_embedding_meta(conn) -> None` **or** document that `--rebuild` issues `DELETE FROM card_embedding_meta` — provide whichever the builder calls; the rebuild path must clear hashes (AC5 / AC2 gotcha). *(Provided `clear_card_embedding_meta`; the CLI `--rebuild` calls it.)*
  - [x] Update `src/search/__init__.py` `__all__` + imports to re-export `create_card_embedding_meta_table` (and `CARD_EMBEDDING_META_TABLE`); refresh the package docstring (the index builder now exists; search tools remain Stories 2.4–2.5). *(Also re-exported `build_card_embeddings`, `compose_card_text`, `content_hash`, `BuildStatistics`, `clear_card_embedding_meta`.)*
- [x] **Task 2 — Core builder logic in `src/search/index_builder.py` (NEW)** (AC: 1, 2, 3, 4) — pure, dependency-injected, unit-testable; the CLI is a thin wrapper (mirror `scripts/import_scryfall_data.py` → `src/data/importers/importer.py`)
  - [x] `compose_card_text(name, type_line, mana_cost, oracle_text, keywords) -> str`: the canonical FR14 composition. Join the five parts deterministically (stable order, documented separator, e.g. newline-joined; `keywords` is a `list[str]` joined on `" "`). Must be **stable** (the hash depends on it) and **never empty** (`cards.name` is `NOT NULL`). One pure function so the hash is reproducible and 2.6 can reference it.
  - [x] `content_hash(text: str) -> str`: `hashlib.sha256(text.encode("utf-8")).hexdigest()`. Pure function of the composite text only (NOT the model — see AC2).
  - [x] `build_card_embeddings(conn, embedder, *, batch_size=1000, limit=None) -> BuildStatistics`: the orchestrator. **Inject** `conn` (a `ConnectionFactory` connection) and `embedder` (an `Embedder`) so unit tests pass a `tmp_path` DB + a fake embedder with **no model load / no network**. Steps:
    1. Ensure tables exist (`create_card_vec_table`, `create_card_embedding_meta_table`) — self-bootstrapping (AC5).
    2. Load all stored hashes once into a dict: `{card_id: content_hash}` from `card_embedding_meta` (38k rows is small).
    3. Open a **read cursor** over `cards` (`SELECT id, name, type_line, mana_cost, oracle_text, keywords, colors, cmc FROM cards`, honour `limit`); iterate in chunks via `cursor.fetchmany(batch_size)`. Reads target `cards`, writes target `card_vec`/`card_embedding_meta` (different tables, same connection) — no read/write interference; WAL is on. *(De-risked empirically: fetchmany + commit-per-batch on one connection works.)*
    4. Per chunk: `json.loads` the `keywords`/`colors` JSON-text columns (**both can be `None` at the column level → coerce `None → []`**); compose text; hash; compare to the stored-hash dict → classify **new / changed / unchanged**. Skip unchanged. For new+changed, `encode_batch` only their texts (bounded by `batch_size` — resolves the Story 2.1 "no `batch_size` passthrough" note **at the builder level**; do NOT modify `Embedder`).
    5. Write within one transaction per chunk: `DELETE FROM card_vec WHERE card_id = ?` for changed ids (no-op for new), then `INSERT` vector + 6 metadata cols (use `executemany`), then **UPSERT** the meta hash (`INSERT … ON CONFLICT(card_id) DO UPDATE SET content_hash = excluded.content_hash` — the meta table is relational, so UPSERT works there, unlike `card_vec`). `conn.commit()` per chunk. *(Wrapped in try/except → `rollback()` + re-raise on error.)*
    6. Track counts in a `BuildStatistics` class mirroring [`ImportStatistics`](../../src/data/importers/importer.py#L15) (`processed`, `embedded_new`, `embedded_changed`, `skipped`, `elapsed_time()`, `cards_per_second()`, `summary()`); `logger.info` progress per chunk and a final summary. *(Added a `pruned` counter for the optional prune step.)*
  - [x] Module docstring (one line), full `mypy --strict` typing, Google docstrings (`Args`/`Returns`/`Raises`/`Example`) on every public function/class. `import sqlite_vec` **is** allowed here (production serialization lives in the builder now — contrast `schema.py`, which must not import it).
  - [x] *(Recommended, scope-flagged)* a `prune` step / `--prune` flag: `DELETE FROM card_vec` + `card_embedding_meta WHERE card_id NOT IN (SELECT id FROM cards)` so cards removed by a later Scryfall import don't leave orphan vectors. Cheap; keeps the index truly convergent. *(Implemented as `prune=True` param + `--prune` flag; orphan set computed in Python to avoid a `NOT IN (subquery)` against the `vec0` table.)*
- [x] **Task 3 — Thin CLI `scripts/build_card_embeddings.py` (NEW)** (AC: 1, 5) — mirror the *shape* of [scripts/import_scryfall_data.py](../../scripts/import_scryfall_data.py) (argparse, `logging.basicConfig` to stdout, summary print block) but **sync** and via `ConnectionFactory` (NOT the async engine)
  - [x] `argparse`: `--batch-size` (default 1000), `--limit` (default None), `--rebuild` (flag), optionally `--prune`. Module docstring + `uv run python scripts/build_card_embeddings.py` usage line. State it is the **second** `src/search` migration-class script (after `migrate_add_card_vec.py`) to run through `ConnectionFactory`.
  - [x] Build `ConnectionFactory()`, ensure `Path(factory.db_path).parent` exists (Story 2.1/2.2 lesson — let the factory resolve the path; **no CWD-relative default re-derivation**). `conn = factory.get_connection()`. If `--rebuild`: `drop_card_vec_table(conn)` → `create_card_vec_table(conn)` → clear `card_embedding_meta`. Obtain the embedder via `get_embedder()` (singleton; the CLI is the composition root). Call `build_card_embeddings(conn, embedder, batch_size=…, limit=…)`. `print(...)` the summary. `factory.close()` in `finally`. *(Rebuild also calls `create_card_embedding_meta_table` before `clear_card_embedding_meta` so clear is safe on a fresh DB.)*
  - [x] `print()` is allowed in `scripts/` (CLI output); library code in `src/` uses `logger`.
- [x] **Task 4 — Unit tests `tests/unit/search/test_index_builder.py` (NEW)** (AC: 1, 2, 3, 4, 5) — mirror `test_schema.py`/`test_connection.py` (tmp_path DB, real sqlite-vec, sync `def`, `factory.close()` teardown); **NOT** `@pytest.mark.integration` (a fake embedder ⇒ no network/model)
  - [x] **Fake embedder:** a tiny in-file stub exposing `encode_batch(texts) -> list[np.ndarray]` returning deterministic 384-dim `float32` vectors (e.g. a one-hot per distinct text, like `test_schema._basis_vector`). Seed a tiny `cards` table on the same connection with a handful of UUID-PK rows + the embed-relevant columns (store `keywords`/`colors` as JSON **text**, matching how the real DB stores them).
  - [x] **First build inserts + populates metadata (AC1):** after `build_card_embeddings`, `card_vec` has one row per seeded card; assert `mana_value = int(cmc)` and the colour flags match `colors` (e.g. `["R"]` → `color_r=1`, others 0); a metadata-filtered KNN returns the expected card.
  - [x] **Idempotent re-run skips (AC2):** second `build_card_embeddings` with the same `cards` re-embeds **0** cards (`embedded_new + embedded_changed == 0`, all `skipped`) and leaves the same row count (no duplicates).
  - [x] **Changed card re-embeds without duplicate (AC2/AC3):** mutate one card's `oracle_text`, re-run → exactly that card is re-embedded (DELETE-then-INSERT path), row count unchanged, its `card_vec` vector + `content_hash` updated.
  - [x] **New card added (AC2):** insert a new `cards` row, re-run → only it is embedded; others skipped.
  - [x] **`compose_card_text` / `content_hash` are pure & stable:** same inputs → identical text & hash; a changed field → different hash. Composite is never empty.
  - [x] **`--rebuild`-equivalent clears hashes ⇒ full re-embed (AC5):** after a build, clear `card_embedding_meta` (+ drop/recreate `card_vec`) and re-run → all cards re-embedded (proves the model/dim-change path doesn't silently skip).
  - [x] **JSON `None` coercion:** a seeded card with `keywords = NULL` (and/or `colors = NULL`) builds without error (coerced to `[]`).
  - [x] *(Optional integration test, `@pytest.mark.integration`)* one test driving the **real** `get_embedder()` over 2–3 seeded cards end-to-end (proves real fastembed → serialize → KNN); marked so `-m "not integration"` skips the model download. *(Also added `test_small_batch_size_converges…` (AC3 chunking) and `test_limit_processes_only_first_n_cards` / `test_prune_removes_orphan_vectors`.)*
- [x] **Task 5 — Verify (run the commands, capture output)** (AC: all)
  - [x] `uv run pytest tests/unit/search/test_index_builder.py -v` → new unit tests pass (fast, offline, real sqlite-vec, fake embedder). *(12 passed, 1 integration deselected.)*
  - [x] `uv run pytest tests/ -m "not integration"` → full active suite still green (baseline **465 passed** after Story 2.2 — keep it green, NFR7). *(477 passed = 465 + 12 new.)*
  - [x] `uv run ruff check .` and `uv run ruff format --check .` → clean for story-authored files (`src/search/index_builder.py`, `src/search/schema.py`, `src/search/__init__.py`, `scripts/build_card_embeddings.py`, `tests/unit/search/test_index_builder.py`). Do **not** reformat pre-existing unrelated ruff issues elsewhere.
  - [x] `uv run mypy src/` → clean. Run `uv run pre-commit run mypy --all-files` too (the isolated env already has `mcp`+`numpy` from Stories 2.1/2.2; `sqlite_vec` is stub-less under `ignore_missing_imports`, so **no new `additional_dependencies`**). *(Both clean — 43 source files.)*
  - [x] **End-to-end smoke against the real DB** (proves AC1/AC4 mechanics, real fastembed): `uv run python scripts/build_card_embeddings.py --limit 200` → confirm it embeds 200, logs progress + summary; re-run the same command → confirm **0 re-embedded** (all skipped), row count stable (AC2/AC3 idempotency). Capture both runs' summaries. *(Optional)* a full unbounded build to confirm the minutes/footprint envelope (AC4) — note the actual elapsed + on-disk size delta. *(First run: 200 new. Re-run: 200 skipped, 0 re-embedded. Integrity: 200 vec / 200 meta / 0 orphans / no dup PKs. Full build numbers in Completion Notes.)*

### Review Findings

- [x] [Review][Patch] `stats.pruned` uses `=` instead of `+=` in `_prune_orphans` — inconsistent with all other stats field increments; latent bug if the function is ever called more than once per build [src/search/index_builder.py:417]

## Dev Notes

### What this story IS — and is NOT

- **IS:** the **index-population** half of the RAG core — `src/search/index_builder.py` (pure `compose_card_text` + `content_hash` + the injected `build_card_embeddings` orchestrator + a `BuildStatistics`), the `card_embedding_meta` companion-table DDL added to `schema.py`, a thin `scripts/build_card_embeddings.py` CLI, and fast unit tests. It is the **fourth** `src/search` sibling after `ConnectionFactory` (1.2), `Embedder` (2.1), and the `card_vec` schema (2.2) — same "thin, injected, fully-typed, focused-tests, scope-disciplined" shape those three reviews rewarded. [Source: [2-2-*.md](./2-2-card-vec-schema-with-metadata-columns.md); [2-1-*.md](./2-1-embedder-port-fastembed-singleton-persistent-cache.md); spec §4/§6.]
- **IS NOT:** the search **tools** — `semantic_search_cards` (Story 2.4) and `find_similar_cards` (Story 2.5) — or the **RAG sanity eval** (Story 2.6). **Do not** write any MCP tool, embed a *query* (the builder only embeds *card* text), build the hybrid KNN+JOIN *query path*, set `distance_metric=cosine`, or modify `Embedder`/`card_vec`'s shape. This story *fills* the table Story 2.2 declared; the query side is later. Resist scaffolding ahead — the Epic-2 cadence (embedder → schema → **builder** → tools → eval) is deliberate.

### 🔴 The vec0 write semantics — empirically verified on the installed wheel (the build-blocking trap)

Re-running an incremental build will re-write changed cards. The instinct is `INSERT OR REPLACE`. **It does not work on `vec0`.** Verified on `sqlite-vec` v0.1.9 (the installed wheel) against a `card_id TEXT PRIMARY KEY` table:

| Operation | Result on `vec0` |
|---|---|
| `INSERT` a duplicate `card_id` | ❌ `OperationalError: UNIQUE constraint failed on card_vec primary key` |
| `INSERT OR REPLACE` an existing `card_id` | ❌ **same** `UNIQUE constraint failed` — `OR REPLACE` is ignored |
| `DELETE FROM card_vec WHERE card_id = ?` | ✅ works |
| `UPDATE card_vec SET embedding=?, … WHERE card_id = ?` | ✅ works |

So the supported re-write is **`DELETE` then `INSERT`** (or `UPDATE` in place). The relational `cards` table *does* honour `INSERT OR REPLACE` — which is exactly why [`importer.py`](../../src/data/importers/importer.py#L50) uses it — but that is a **different table type**; do not carry that idiom into the vector table. The PK *does* prevent duplicates (a blind re-INSERT raises rather than duplicating), which is your safety net: classify cards as new/changed first, and DELETE-before-INSERT only what you re-write. [Source: empirical spike, this story's analysis, 2026-06-21.]

### 🔴 The content hash detects text changes, NOT model changes — or `--rebuild` skips everything

`content_hash = sha256(compose_card_text(...))` is a pure function of **card content**. That is the correct, clean signal for "did this card's embeddable text change since last build?" But it has a sharp edge for **NFR10**: a model swap or `EMBEDDING_DIM` change does **not** alter any card's text, so every hash still matches and the incremental builder **skips all cards** — leaving the new model's vectors never written. Therefore the model/dimension-change path (AC5 `--rebuild`) must **clear `card_embedding_meta`** (drop the hashes) in addition to dropping/recreating `card_vec`, so the next build sees "no stored hash → new → embed" for everything. Document this in both the builder and the CLI. (Rejected alternative: folding `MODEL_NAME`/`EMBEDDING_DIM` into the hash input — it would auto-detect model changes but muddies the hash's meaning and couples it to the embedder; the explicit `--rebuild` is the documented NFR10 migration and keeps the hash a clean content signal.)

### The read path — raw SQL on the *same* sync connection (do not reach for the async repo)

The `cards` rows are read via **raw SQL on the sync `ConnectionFactory` connection** that also writes `card_vec` — one connection, one script, no async. The `CardRepository` is async and only offers paginated/filtered reads + a point `get_by_id` ([src/data/repositories/card.py](../../src/data/repositories/card.py)); there is no bulk/stream method, and mixing the async engine into this sync builder would mean two connections and ORM materialization of 38k rows for no benefit. Instead:

```sql
SELECT id, name, type_line, mana_cost, oracle_text, keywords, colors, cmc FROM cards
```

iterated with a dedicated **read cursor** + `fetchmany(batch_size)`. Reads hit `cards`; writes hit `card_vec`/`card_embedding_meta` (different tables) — no cursor/write interference, and WAL (always on via the factory) handles it. `keywords` and `colors` come back as **JSON text** over raw `sqlite3` (verified: `'["Landfall"]'`, `'["R"]'`, `'[]'`) → `json.loads`. Both columns are nullable at the DB level (`keywords: Mapped[list[str] | None]`, `colors` nullable JSON) so **coerce `None → []`** before composing/flagging, even though the current import happens to store `'[]'` rather than `NULL`. [Source: [src/data/models/card.py](../../src/data/models/card.py); live DB inspection 2026-06-21.]

### Batching & the Story 2.1 `batch_size` deferral — resolved at the builder

`Embedder.encode_batch(texts)` passes the whole sequence to fastembed and materializes one vector per input (Story 2.1 deliberately left a `batch_size` passthrough out, [deferring it to "Story 2.3's index builder"](./2-1-embedder-port-fastembed-singleton-persistent-cache.md)). Resolve it **here, by chunking at the read layer**: the builder reads `batch_size` cards, filters to the new/changed subset, and calls `encode_batch` on only that subset — so each call is bounded (≤ `batch_size`, default 1000 → ~1.5 MB of float32). **Do not add `batch_size` to `Embedder`** and do not modify it; chunking upstream is sufficient and keeps the 2.1 port frozen. fastembed internally batches at 256, so a 1000-text call is fine.

### Idempotency / convergence transaction discipline (AC3)

Per chunk, in **one transaction**: DELETE changed `card_vec` rows → `executemany` INSERT new+changed vectors+metadata → UPSERT their `card_embedding_meta` hashes → `conn.commit()`. Writing the vector and its hash atomically guarantees the invariant "a card is hash-recorded **iff** its current vector is written" — so an interruption between batches leaves completed batches durable+consistent and the in-flight (uncommitted) batch rolls back; the re-run treats its cards as new/changed and converges with **no duplicates and no orphan hashes**. Commit-per-batch also bounds WAL growth on a 38k run (mirrors the importer's per-batch commit). On an unexpected error, roll back the batch and re-raise (fail-fast); re-run is cheap because it's incremental.

### Composite text (FR14) — exact, stable, reproducible

`name + type_line + mana_cost + oracle_text + keywords`, composed by the single `compose_card_text` function. Keep ordering and separator **fixed and documented** (the hash depends on byte-for-byte stability across runs). `keywords` is a `list[str]` → join deterministically (Scryfall order is stable per import). The composite is **never empty** because `cards.name` is `NOT NULL` (so `Embedder.encode_batch` never sees an empty string — and note `Embedder.encode` *raises* on empty, though the builder uses `encode_batch`). Define this as the canonical composition so Story 2.6's eval can reference the same recipe. [Source: spec §6; FR14; [research §B](../planning-artifacts/research/technical-sqlite-vec-fastembed-rag-stack-on-windows-research-2026-06-20.md).]

### Schema home & the search-index/relational split

`card_embedding_meta` is an **ordinary relational table**, but it belongs to the **search index**, so create it through the **sync `ConnectionFactory`** beside `card_vec` (add `create_card_embedding_meta_table` to `src/search/schema.py`). The coherent rule for the repo: the **relational domain schema** (`cards`/`decks`/`bug_reports`/`deck_cards`) lives on `Base.metadata` + the async engine; the **search-index schema** (`card_vec` + `card_embedding_meta`) lives on the sync `ConnectionFactory` — both in the *same* `./data/cards.db` file (D2 single-file topology). Do **not** add `card_embedding_meta` to `Base.metadata`/`init_database` (keeps the builder self-contained and avoids a cross-engine creation dependency). The builder self-bootstraps both tables (idempotent `create_*`), so a dev need not pre-run `migrate_add_card_vec.py`. [Source: [project-context.md](../project-context.md) sync-vs-async boundary; [2-2 Dev Notes](./2-2-card-vec-schema-with-metadata-columns.md).]

### Footprint & performance envelope (AC4 / NFR3 / NFR4)

- Real DB: **38,232 cards**, `./data/cards.db` ≈ 88 MB today. Expected raw vector add ≈ `38,232 × 384 × 4 B ≈ 56–59 MB`. The "~92 MB" in NFR4/epics is the **60k** projection — **don't hard-assert 92 MB**; log the actual delta and check `~1.5 KB/card` order-of-magnitude.
- Build time target "minutes" (NFR3): ~3 ms/embed × 38k ≈ ~2 min embed-only on CPU, plus DB writes; single-threaded is fine. First run additionally downloads the ~80 MB model once into the persistent `FASTEMBED_CACHE_DIR` (Story 2.1) — separate from the "minutes" build budget.

### Dependency injection makes the builder unit-testable offline

`build_card_embeddings(conn, embedder, …)` takes both collaborators as parameters; the **CLI is the composition root** that wires the real `ConnectionFactory` connection + `get_embedder()` singleton. Unit tests inject a `tmp_path` DB connection + a **fake embedder** (deterministic 384-dim vectors) → no network, no ~80 MB download, runs as a fast **unit** test (not `integration`), exactly like `test_schema.py` runs real sqlite-vec without a model. This is the same seam `ConnectionFactory`/`Embedder` exposed; follow it. The thin CLI mirrors `import_scryfall_data.py` (CLI) → `importer.py` (logic): testable logic in `src/`, orchestration in `scripts/`.

### Anti-patterns (do NOT do these)

- ❌ `INSERT OR REPLACE` / blind re-`INSERT` into `card_vec` — **verified broken** (UNIQUE constraint); use DELETE-then-INSERT (or UPDATE). It works on `cards`, not on `vec0`.
- ❌ Rely on the content hash to catch a model/dim change — it can't; `--rebuild` must clear `card_embedding_meta` or the build silently skips everything.
- ❌ Read cards through the async `CardRepository`/SQLAlchemy engine — read with raw SQL on the **same sync** `ConnectionFactory` connection that writes vectors.
- ❌ Re-normalize the embedding — bge vectors are already L2-normalized (Story 2.1); store raw. Don't set `distance_metric=cosine` (Story 2.2 kept default L2).
- ❌ Modify `Embedder` to add `batch_size` — chunk at the builder instead; keep the 2.1 port frozen.
- ❌ Forget to `json.loads` + coerce `None → []` on `keywords`/`colors` (JSON-text columns, nullable).
- ❌ Hardcode `384` — import `EMBEDDING_DIM` from `src.search.embedder` (it's already re-exported from `src.search`). Hardcode `int(cmc)` mapping is correct; hardcoding dim is not.
- ❌ Add `card_embedding_meta` to `Base.metadata`/`init_database` — it's search-index schema on the sync factory.
- ❌ `import sqlite_vec` in `schema.py` (Story 2.2 rule) — but DO import it in `index_builder.py` (production serialization lives here now).
- ❌ Materialize all 38k cards/vectors at once — chunk with `fetchmany(batch_size)` and commit per batch.
- ❌ Hard-assert a 92 MB footprint or a fixed card count — scale to the real count (38,232) and log actuals.
- ❌ Put real logic in `scripts/` (untestable) — logic in `src/search/index_builder.py`, thin CLI in `scripts/`. `print()` only in the CLI; `logger` in `src/`.
- ❌ Hardcode `/tmp` in tests (Story 1.2 review) — use `tmp_path`. `factory.close()` teardown like `test_schema.py`.

### Previous Story Intelligence (Stories 2.2 + 2.1 + the importer — the direct templates)

- **Story 2.2 handed you a clean seam:** `create_card_vec_table`/`drop_card_vec_table` + the constants `CARD_VEC_TABLE`, `CARD_ID_COL`, `EMBEDDING_COL`, `MANA_VALUE_COL`, `COLOR_COLS`, `METADATA_COLS` ([src/search/schema.py](../../src/search/schema.py)). Import and reuse them for the INSERT column list (build it from the constants, not literals — exactly the [2.2 review patch](./2-2-card-vec-schema-with-metadata-columns.md#L85) that made `test_schema` use `COLOR_COLS`). 2.2 also **explicitly deferred to this story:** the `int(cmc)` cast at insert, production `serialize_float32`, the content-hash companion table, and composing per-card text. [Source: [2-2 Dev Notes / Review Findings](./2-2-card-vec-schema-with-metadata-columns.md).]
- **Story 2.1 handed you:** `get_embedder()` singleton + `Embedder.encode_batch` ([src/search/embedder.py](../../src/search/embedder.py)) and the `EMBEDDING_DIM` constant; it deferred `batch_size` to here. The persistent `FASTEMBED_CACHE_DIR` means the first build downloads the model once, then loads offline.
- **Recurring review findings to pre-empt:** (1) relative-path-vs-absolute (Story 2.1 High) — let `ConnectionFactory`/`get_embedder` resolve paths; no CWD-relative re-derivation in the CLI. (2) Google-style `Example:` on every public function (required in 2.1/2.2 reviews). (3) `tmp_path`, never `/tmp` (Story 1.2). (4) `factory.close()` teardown (2.2 deferred try/finally — mirror the existing pattern; don't regress it). [Source: [2-1 Review](./2-1-embedder-port-fastembed-singleton-persistent-cache.md#L295-L316); [2-2 review/deferred](../implementation-artifacts/deferred-work.md).]
- **The importer is your batch-loop template:** [`ImportStatistics`](../../src/data/importers/importer.py#L15) + `import_cards` (batch accumulate → insert → commit-per-batch → progress log → `summary()`). Mirror its `BuildStatistics`/loop shape (but DI'd and sync). [Source: [src/data/importers/importer.py](../../src/data/importers/importer.py).]
- **Baseline green at 465 passed** (`-m "not integration"`) after Story 2.2; `legacy/` excluded. Keep it green (NFR7).

### Git Intelligence

- HEAD `1d2b7a2` "feat: add card_vec vec0 schema …" closed Story 2.2; `921545d`/`6ebcdf3` were Story 2.1. The Epic-2 cadence is firmly established: thin `src/search` unit → focused tests → run-and-capture verify → strict scope discipline. This story is the next link (embedder → schema → **builder** → tools → eval).
- `src/search/` holds `connection.py` + `embedder.py` + `schema.py` (+ `__init__.py`); `index_builder.py` is **green-field** within it. `scripts/` has a consistent `migrate_*`/`import_*` family — `build_card_embeddings.py` joins it as the **second** `src/search`-driven script (after `migrate_add_card_vec.py`) using `ConnectionFactory` not the async engine; call that out in its docstring. [Source: `git log`; [src/search/](../../src/search/); [scripts/](../../scripts/).]
- Working tree is clean at this baseline — no incidental edits expected beyond the story's File List.

### Latest Tech / Versions (verified for THIS project, 2026-06-21)

| Item | Value | Source |
|---|---|---|
| `sqlite-vec` write semantics | `vec0` **rejects `INSERT OR REPLACE`** (UNIQUE constraint); `DELETE`/`UPDATE` by TEXT PK work; duplicate `INSERT` raises | **empirical spike, this story** (v0.1.9) |
| `sqlite-vec` | v0.1.9 (bundled wheel) | [test_connection.py](../../tests/unit/search/test_connection.py) `vec_version()` |
| Serialization | `sqlite_vec.serialize_float32(list\|ndarray) -> BLOB` — now **production** (builder), no longer test-only | [research §B](../planning-artifacts/research/technical-sqlite-vec-fastembed-rag-stack-on-windows-research-2026-06-20.md); sqlite-vec Python docs |
| `Embedder` | `get_embedder()` singleton + `encode_batch(texts) -> list[NDArray[float32]]`; no `batch_size` (chunk here) | [src/search/embedder.py](../../src/search/embedder.py) |
| `EMBEDDING_DIM` | **384** (`from src.search import EMBEDDING_DIM`) | [src/search/embedder.py](../../src/search/embedder.py) |
| `cards` data | **38,232 rows**; `id` TEXT UUID; `cmc` Float; `colors`/`keywords` JSON **text** over raw sqlite3 (`'["R"]'`, nullable) | live DB inspection 2026-06-21; [src/data/models/card.py](../../src/data/models/card.py) |
| Vector footprint | ≈ 56–59 MB at 38,232 cards (NFR4's ~92 MB is the 60k projection) | computed; NFR4 |
| Python / SQLite | CPython 3.12.13 / SQLite 3.50.4 / Windows / uv | [project-context.md](../project-context.md) |

### Project Structure Notes

Target additions (everything else unchanged):

```
src/
  search/
    __init__.py        # MODIFIED — also re-export create_card_embedding_meta_table, CARD_EMBEDDING_META_TABLE
    connection.py      # (unchanged, Story 1.2) — the sync connection the builder reads cards from / writes vectors to
    embedder.py        # (unchanged, Story 2.1) — get_embedder() + encode_batch + EMBEDDING_DIM
    schema.py          # MODIFIED — add create_card_embedding_meta_table + CARD_EMBEDDING_META_TABLE/CONTENT_HASH_COL constants
    index_builder.py   # NEW — compose_card_text, content_hash, build_card_embeddings(conn, embedder, …), BuildStatistics
scripts/
  build_card_embeddings.py   # NEW — thin sync CLI over ConnectionFactory + get_embedder(): --batch-size/--limit/--rebuild
tests/
  unit/
    search/
      test_index_builder.py  # NEW — fast unit tests (fake embedder, real sqlite-vec): first build, idempotent skip, changed re-embed, new card, rebuild-clears, JSON None coercion
```

- **Alignment:** matches spec §4 (`src/search` = "embedding model wrapper + sqlite-vec integration + **index builder**") and research roadmap step 2; FR14/FR15/FR16; D2 single-file topology. [Source: [design spec §4/§6](../../docs/superpowers/specs/2026-06-20-mcp-server-architecture-design.md); [research §8](../planning-artifacts/research/technical-sqlite-vec-fastembed-rag-stack-on-windows-research-2026-06-20.md).]
- **Layering check:** `src/search` is sync infra consumed downward by `scripts/` (this builder) and `src/mcp_server` (Stories 2.4–2.5) — no upward import, no cycle. `index_builder.py` imports stdlib + `sqlite_vec` + sibling `embedder`/`schema`/`connection`. ✅
- **No new dependencies / no `pyproject.toml` or `.pre-commit-config.yaml` changes** — `sqlite-vec`, `fastembed`, `numpy` are already core (Stories 1.1/2.1); the pre-commit mypy env already resolves them.

### References

- [epics.md — Epic 2 / Story 2.3](../planning-artifacts/epics.md) — user story, the five BDD ACs (compose+embed+serialize+insert; content-hash incremental; minutes/footprint; converge-no-duplicates; uv-invocable).
- [research — RAG de-risk §A / §B / §Data Architecture / §Deployment](../planning-artifacts/research/technical-sqlite-vec-fastembed-rag-stack-on-windows-research-2026-06-20.md) — serialization (`serialize_float32`), single-file topology, metadata pre-filter, build/footprint envelope, WAL-checkpoint-before-backup ops.
- [design spec §3 (D2) / §4 / §6](../../docs/superpowers/specs/2026-06-20-mcp-server-architecture-design.md) — `src/search` = embedder + sqlite-vec + **index builder**; composite embedded text; `card_vec` keyed by `card_id`.
- [src/search/schema.py](../../src/search/schema.py) — `create_card_vec_table`/`drop_card_vec_table` + constants to reuse; the home for the new `card_embedding_meta` DDL.
- [src/search/embedder.py](../../src/search/embedder.py) — `get_embedder()` singleton, `encode_batch`, `EMBEDDING_DIM`; the deferred `batch_size`.
- [src/search/connection.py](../../src/search/connection.py) — the sync seam (sqlite-vec + WAL) the builder reads cards from and writes vectors to.
- [src/data/models/card.py](../../src/data/models/card.py) — `cards` fields: TEXT UUID `id`, `cmc` Float, `colors`/`keywords` JSON (nullable) — the read schema + metadata sourcing.
- [src/data/importers/importer.py](../../src/data/importers/importer.py) / [scripts/import_scryfall_data.py](../../scripts/import_scryfall_data.py) — the batch-loop + `ImportStatistics` + thin-CLI-over-src-logic pattern to mirror.
- [scripts/migrate_add_card_vec.py](../../scripts/migrate_add_card_vec.py) — the sibling `ConnectionFactory`-based script shape.
- [tests/unit/search/test_schema.py](../../tests/unit/search/test_schema.py) / [test_connection.py](../../tests/unit/search/test_connection.py) — the unit-test style (tmp_path, real sqlite-vec, `factory.close()`, positional row indexing) to mirror; `_basis_vector` is a ready model for the fake embedder.
- [Story 2.2](./2-2-card-vec-schema-with-metadata-columns.md) / [Story 2.1](./2-1-embedder-port-fastembed-singleton-persistent-cache.md) — the explicit deferrals this story collects (int(cmc), production serialization, content-hash companion table, compose text, batch_size) + recurring review findings.
- [project-context.md](../project-context.md) — RAG rules (every KNN needs `k`/`LIMIT`; metadata cols; rebuild on model/dim change; sync-vs-async boundary; testing layout; ruff/mypy gates).
- [deferred-work.md](./deferred-work.md) — Story 2.1/2.2 deferred items (`batch_size`, `mana_value` float coercion, `factory.close()` try/finally) that this story is the natural place to address.

## Dev Agent Record

### Agent Model Used

Opus 4.8 (1M context) — `claude-opus-4-8[1m]` (BMAD dev-story workflow).

### Debug Log References

- **De-risk spike (before coding):** verified `fetchmany(batch_size)` + `conn.commit()` per batch on a **single** sqlite-vec connection (read `cards` / write a sink table) — 25/25 rows, no "statements in progress" / lock errors. Confirms the same-connection read-cursor + commit-per-chunk design (AC3).
- **Unit suite:** `uv run pytest tests/unit/search/test_index_builder.py -m "not integration"` → 12 passed, 1 deselected (0.82s).
- **Regression:** `uv run pytest tests/ -m "not integration"` → 477 passed, 2 deselected (465 baseline + 12 new; NFR7 green).
- **Integration (real fastembed):** `uv run pytest tests/unit/search/test_index_builder.py -m integration` → 1 passed (real bge → serialize → KNN finds the card).
- **Lint/type:** `ruff check` + `ruff format --check` clean on the five authored files; `mypy src/` clean (43 files); `pre-commit run mypy --all-files` Passed.
- **End-to-end smoke (real DB):** first `--limit 200` → 200 new in 3.0s; re-run `--limit 200` → 0 re-embedded, 200 skipped (instant). Integrity after smoke: 200 vec / 200 meta / 0 orphans / no dup PKs.
- **Full build (real DB, AC4):** 38,232 processed → 38,032 new + 200 skipped, **616.9s (~10.3 min) at 62 cards/sec**; `cards.db` 85 MB → 152 MB (**+67 MB ≈ 1.79 KB/card**). Final coverage: `cards == card_vec == card_embedding_meta == 38,232`, 0 orphans.

### Completion Notes List

- **All five ACs satisfied and verified against the real 38,232-card DB.**
- **AC1** — `build_card_embeddings` composes `name + type_line + mana_cost + oracle_text + keywords` (newline-joined, keywords space-joined), batch-embeds via the Story 2.1 `Embedder`, serializes with `sqlite_vec.serialize_float32`, and inserts a `card_vec` row keyed by the TEXT `card_id` with `mana_value = int(cmc)` + the five `color_*` flags built from `cards.colors` in `COLOR_COLS` order (verified: `["G"]`→`color_g=1`/mv4, `["R"]`→`color_r=1`/mv2, `[]`→all 0). Raw bge vector stored (no re-normalize).
- **AC2** — per-card `sha256(composite_text)` stored in the new relational `card_embedding_meta`; re-runs re-embed only new/changed (smoke + full both skipped the prior 200). The hash is a pure *content* signal — model/dim changes are routed through `--rebuild` (clears hashes), documented in builder + CLI + schema.
- **AC3** — `vec0` rejects `INSERT OR REPLACE` (per the story's empirical finding), so changed cards are **DELETE-then-INSERT**; vector + hash written in one per-chunk transaction (rollback + re-raise on error). No duplicate PKs, no orphan hashes (verified 0). Convergence de-risked empirically.
- **AC4** — full build finishes in ~10.3 min (within "minutes"; throughput 62 cards/sec ≈ 16 ms/card on this CPU — slower than the spike's single-query 3 ms but well inside the envelope), logs per-chunk progress + a final summary (processed/new/changed/skipped/pruned/elapsed/cards-per-sec). Footprint **+67 MB ≈ 1.79 KB/card**, same order-of-magnitude as the ~1.5 KB/card check and far below the 92 MB 60k-projection — **no hard threshold asserted**.
- **AC5** — `uv run python scripts/build_card_embeddings.py` is self-bootstrapping (creates both tables), reads config via `ConnectionFactory`/`CARDS_DATABASE_URL`; `--rebuild` does drop→create `card_vec` → `clear_card_embedding_meta` → full re-embed; `--limit N` for fast runs.
- **Scope notes / additions beyond the minimum:** implemented the recommended `--prune`/`prune=True` (orphan removal; orphan set computed in Python to avoid `NOT IN (subquery)` on `vec0`) with a `pruned` counter + test; added AC3 chunk-convergence, `--limit`, and prune tests. Reused `CARD_ID_COL` for the meta PK (no separate `META_CARD_ID_COL` constant). **`Embedder` and `card_vec` shape left untouched** (Story 2.1/2.2 ports frozen; `batch_size` resolved by chunking the read, not by modifying `Embedder`). No new dependencies; no `pyproject.toml`/`.pre-commit-config.yaml` changes.
- **Side effect:** the real `./data/cards.db` now holds a **complete** 38,232-vector index (ready for Stories 2.4–2.6). The build left WAL un-checkpointed; ops should `PRAGMA wal_checkpoint(TRUNCATE)` before any file-copy backup (per the schema docstring).

### File List

- `src/search/schema.py` — **MODIFIED**: added `CARD_EMBEDDING_META_TABLE` / `CONTENT_HASH_COL` constants, `create_card_embedding_meta_table`, `clear_card_embedding_meta`.
- `src/search/index_builder.py` — **NEW**: `compose_card_text`, `content_hash`, `BuildStatistics`, `build_card_embeddings` (+ private `_process_chunk`, `_prune_orphans`, `_coerce_json_list`, `_color_flags`).
- `src/search/__init__.py` — **MODIFIED**: re-export the builder API + new schema symbols; refreshed package docstring.
- `scripts/build_card_embeddings.py` — **NEW**: thin sync CLI over `ConnectionFactory` + `get_embedder()` (`--batch-size`/`--limit`/`--rebuild`/`--prune`).
- `tests/unit/search/test_index_builder.py` — **NEW**: 12 unit tests (fake embedder, real sqlite-vec) + 1 `@pytest.mark.integration` real-fastembed test.

## Change Log

| Date | Version | Description |
|---|---|---|
| 2026-06-21 | 0.1 | Story drafted via BMAD create-story (ultimate context engine). Surfaced the **empirically-verified vec0 write trap** (`INSERT OR REPLACE` broken → DELETE-then-INSERT), the **content-hash-vs-model-change gotcha** (`--rebuild` must clear `card_embedding_meta`), the raw-sync read path (not the async repo), builder-level `batch_size` chunking, the search-index-schema split (`card_embedding_meta` on the sync factory), the 38,232-card footprint reconciliation (not 92 MB), and the DI'd-builder + thin-CLI testability shape. Status → ready-for-dev. |
| 2026-06-21 | 1.0 | Implemented all 5 tasks: `card_embedding_meta` schema + `clear_card_embedding_meta` (Task 1), `compose_card_text`/`content_hash`/`BuildStatistics`/`build_card_embeddings` with DELETE-then-INSERT incremental writes + optional prune (Task 2), thin `build_card_embeddings.py` CLI with `--batch-size`/`--limit`/`--rebuild`/`--prune` (Task 3), 12 unit + 1 integration test (Task 4), full verification (Task 5). All 5 ACs met & verified on the real DB; full 38,232-vector index built in ~10.3 min (+67 MB). 477 tests green, ruff/mypy/pre-commit clean. Status → review. |
