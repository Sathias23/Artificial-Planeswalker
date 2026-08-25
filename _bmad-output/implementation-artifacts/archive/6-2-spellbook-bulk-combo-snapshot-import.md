---
baseline_commit: e1716d295d296e8a197ae11ba61838d8474f24fc
---

# Story 6.2: Spellbook bulk combo-snapshot import

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As the operator,
I want an offline script that imports the Commander Spellbook bulk variant export locally,
so that combo detection is fully local and versioned like the card snapshot.

## Acceptance Criteria

1. **Downloader lives at the data layer and mirrors the Scryfall hardening.** A new module
   `src/data/importers/spellbook_api.py` (sibling to `scryfall_api.py`, AD-9) downloads the
   Spellbook bulk variant export from the pinned constant
   `https://json.commanderspellbook.com/variants.json.gz` (verified live 2026-07-16: ~25.6 MB
   gzip / ~579 MB raw / 100,133 variants — dev re-verifies in Task 0) with: explicit timeout,
   an explicit `User-Agent` (descriptive, e.g. `Artificial-Planeswalker/<version>
   (+https://github.com/Sathias23/Artificial-Planeswalker)`) **and** `Accept` header, streaming
   download to a private per-run temp dir, a hard `max_bytes` ceiling (abort + delete partial,
   no retry on ceiling violation), and **manual exponential backoff** on
   `httpx.HTTPError`/`TimeoutException` mirroring `scryfall_api.py` — `tenacity` is NOT a
   dependency (AD-9). No new runtime dependencies: `httpx`, `ijson`, and stdlib `gzip` cover
   everything.

2. **Wire → canonical `ComboRecord` normalization, failing loudly.** A normalizer in
   `src/data/importers/spellbook.py` transforms each wire variant into a validated
   `ComboRecord` (`src/data/schemas/combo.py`, bucket=None — AD-11):
   - `spellbook_id` ← `id`; `cards` ← `uses[].card.name` repeated `uses[].quantity` times
     (multiplicity-inclusive — the matcher counts duplicates); `commander_required` ←
     `any(uses[].mustBeCommander)` (**the authoritative flag — NOT `zoneLocations`**, which
     is neither necessary nor sufficient); `produces` ← `produces[].feature.name`;
     `popularity` ← `popularity` (int | None).
   - `bracket_tag` is normalized through a **closed letter→token map** — `R→RUTHLESS`,
     `S→SPICY`, `P→POWERFUL`, `O→ODDBALL`, `C→PRECON_APPROPRIATE`, `E→CASUAL`; `B` (BANNED)
     variants are **skipped and counted** (no canonical token exists; Spellbook derives
     bracket `null` for them). **Any other value is a hard error that aborts the import** —
     no fuzzy fallback, no silent alias (5.6 contract; the `ComboBracketTag` Literal is the
     second line of defense).
   - Variants with `status != "OK"` are skipped and counted (today's export is 100% OK, but
     `E`/EXAMPLE can legally appear). Variants with a non-empty `requires[]` (generic
     template requirements like "a sac outlet") are **skipped and counted** — the name-based
     matcher cannot verify a template piece, and importing them would let `match_combos`
     report `included` for combos the deck may not actually have.

3. **Snapshot + metadata tables in `cards.db`, written only here.** New ORM models in
   `src/data/models/combo.py`, registered in `src/data/database.py`'s model-import block
   (`# noqa: F401` — the side-effect import rule):
   - `combo_variants` — one row per imported variant mirroring `ComboRecord`'s stored
     fields exactly (`spellbook_id` PK, `cards` + `produces` as JSON-in-Text with paired
     `*_list` property/setter per the `DeckModel.tags` pattern, `commander_required`,
     `bracket_tag`, `popularity` nullable). `bucket` is **never stored** (matcher-assigned;
     derived fields `type`/`earliest_turn_estimate` never stored either).
   - `combo_variant_pieces` — the piece-name lookup index for Story 6.3's relevance filter:
     one row per (`spellbook_id`, `name_key`), composite PK, indexed on `name_key`, where
     the keys come from the **relocated shared `name_keys()` normalization** (AC 4).
   - `combo_snapshot_meta` — single row (`id` pinned to 1, `CHECK (id = 1)` —
     `import_state` precedent) carrying `imported_at` (import-time `datetime.now(UTC)`,
     ISO-8601), `export_timestamp` + `export_version` (the bulk file's top-level
     `timestamp` / `version` fields — the `data_vintage` source, AD-5/AD-7), and
     `variant_count`.
   - No migration script: these are **new** tables created via `Base.metadata.create_all`
     (`init_database`), which the import script already calls — additive on any existing DB
     (`create_all` only creates missing tables). Like `card_vec`, the snapshot is a **build
     prerequisite, never committed** — a fresh checkout has empty tables and Story 6.3
     treats empty as absent (`combo_data_unavailable`).

4. **`_name_keys` is relocated, not forked (epic-5 retro action item 9).** The DFC
   front-face normalization `_name_keys` moves from `src/logic/assessment/combos.py` to
   `src/data/schemas/combo.py` as public `name_keys()` (beside `ComboRecord`, which already
   documents this exact layering rationale — the data layer cannot import from `src/logic`).
   `src/logic/assessment/combos.py` imports it from there (internal alias `_name_keys` keeps
   its call sites/docstrings intact); **all existing matcher tests pass untouched** — that is
   the relocation's additivity proof. The importer uses it to build the
   `combo_variant_pieces` keys (a DFC piece name `"A // B"` yields two key rows).

5. **Idempotent, atomic refresh.** The import is re-runnable: normalization of the ENTIRE
   export completes **before** any table write; then one transaction deletes the previous
   snapshot rows, inserts the new variant + piece rows, upserts the metadata row, and
   commits. Any failure (bad tag, duplicate `spellbook_id`, zero eligible variants — each a
   loud abort) rolls back and **leaves the previous snapshot intact**, as does a failed
   download (which never reaches the DB at all). No `import_state`-style in-progress marker
   is needed — single-transaction atomicity makes a partial snapshot unrepresentable.

6. **Operator-initiated CLI script.** `scripts/import_spellbook_combos.py` mirrors
   `scripts/import_scryfall_data.py`: thin argparse CLI (`--db-path` defaulting to the shared
   central DB via `src.paths.database_path()`, `--temp-dir`), `logging.basicConfig`,
   `asyncio.run(main())`, exit codes 0 / 130 (SIGINT) / 1, and a final summary printing:
   variants in export, imported, skipped (status / requires-template / banned-tag, each with
   its count), piece rows written, export version + timestamp, elapsed time. It never runs
   automatically ("don't re-import casually" rule) and assessment never triggers it (FR14).

7. **Documented alongside the existing data-refresh flow.** README gains a short section
   (pattern: the "Semantic search index" section) covering: what the snapshot is, the one
   command (`uv run python scripts/import_spellbook_combos.py`), the ~2-hourly upstream
   regeneration cadence, that a missing snapshot degrades gracefully
   (`combo_data_unavailable`, Epic 7), and Commander Spellbook attribution.

8. **Type + lint gates pass.** `mypy --strict` over `src/`, `ruff check` + `ruff format`,
   pre-commit succeeds without `--no-verify` (the `build-plugin-sync` hook mirrors `src/` →
   `plugin/server/`; `scripts/` is not mirrored).

9. **Tests prove the pipeline offline (no live network in any test).** Unit: normalizer
   field mapping + skip/error policies + letter-map totality; downloader hardening (headers
   sent, ceiling abort, backoff, partial-file cleanup) via `httpx.MockTransport`
   (`test_download_hardening.py` pattern). Integration (tmp DB + local fixture payload,
   download monkeypatched — `test_scryfall_import_e2e.py` pattern): fresh import populates
   all three tables correctly (incl. DFC piece keys); re-run replaces (idempotent, counts
   stable, meta updated); a poisoned second payload (unknown tag) aborts leaving the FIRST
   snapshot intact; zero-eligible-variants aborts likewise.

## Tasks / Subtasks

- [x] **Task 0 — Story-start state verification** (epic-5 retro action item 7: verify, don't
      trust)
  - [x] Live DB check (scratchpad script, `uv run python <file>`):
        `SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'combo%'` — expect
        **no rows**. If combo tables already exist, stop and investigate before writing code.
  - [x] Live export check (AC: "URL/format verified against the live export at
        implementation"): HTTP HEAD (or ranged GET) both
        `https://json.commanderspellbook.com/variants.json.gz` and `.../variants.json` —
        expect 200, gz ≈ 25–40 MB; then peek the decompressed head for the top-level key
        order `timestamp`, `version`, `variants` (`aliases` trails at the end). Spot-check
        one variant for the field names in Dev Notes ("Wire format"). If `bracketTag` values
        or `mustBeCommander` are missing/renamed, STOP — the wire map below is stale;
        re-verify before coding.
  - [x] Record both outputs in the Dev Agent Record.

- [x] **Task 1 — Relocate `name_keys` to the schema layer** (AC: 4)
  - [x] Move the function body of `_name_keys` from `src/logic/assessment/combos.py:90` to
        `src/data/schemas/combo.py` as public `name_keys(name: str) -> tuple[str, ...]`
        (module-level, beside `_FACE_SEPARATOR` which moves with it). Extend the combo.py
        module docstring: the name-key policy lives here for the same reason `ComboRecord`
        does — the data-layer importer and the pure matcher must share one normalization,
        and `src/data` cannot import from `src/logic`.
  - [x] In `src/logic/assessment/combos.py`: `from src.data.schemas.combo import name_keys
        as _name_keys` — zero call-site churn; drop the local definition. Keep the
        docstring cross-references pointing at the new home.
  - [x] Run the existing matcher tests untouched (`uv run pytest tests/unit/logic/assessment/
        -q`) — green with no edits is the relocation proof.

- [x] **Task 2 — Downloader module** (AC: 1)
  - [x] Create `src/data/importers/spellbook_api.py`: module constant
        `SPELLBOOK_VARIANTS_URL = "https://json.commanderspellbook.com/variants.json.gz"`,
        a `SpellbookAPIError` exception, and
        `async def download_variants_export(output_path, *, max_retries=3, retry_delay=2.0,
        max_bytes=...) -> Path` mirroring `scryfall_api.download_bulk_data` (streaming
        chunks, progress logging, ceiling abort with partial-file cleanup and NO retry,
        exponential backoff `retry_delay * 2**attempt` for transport errors).
  - [x] Differences from the Scryfall precedent, all deliberate: the URL is a pinned
        constant (no metadata indirection → no `_validate_download_uri` counterpart
        needed); send explicit headers `User-Agent` (descriptive, with repo URL) and
        `Accept: application/json` on the client (AD-9 requires both; Scryfall's client
        predates the rule — do NOT retrofit it here); ceiling default sized for this file
        (e.g. `256 * 1024**2` — the gz is ~26 MB today; generous headroom, still
        disk-safe).
  - [x] **httpx decoding trap (verified live):** the `.gz` object is served with
        `Content-Encoding: gzip`, and httpx **auto-decompresses** encoded responses —
        `response.aiter_bytes()` would yield the ~579 MB decoded stream (silently blowing
        the ceiling and making the saved file plain JSON that `gzip.open` rejects). Stream
        with **`response.aiter_raw()`** so the wire bytes (~26 MB gzip) land on disk, the
        ceiling measures compressed bytes (matching the `content-length` header), and
        Task 4's `gzip.open` reads what it expects. Pin this with a MockTransport test
        serving a `Content-Encoding: gzip` response.
  - [x] Do not add conditional-GET/ETag logic — out of scope for v1 (operator runs this
        rarely; the refresh is a full replace).

- [x] **Task 3 — ORM models + registration** (AC: 3)
  - [x] `src/data/models/combo.py`: `ComboVariantModel` (`__tablename__ = "combo_variants"`),
        `ComboVariantPieceModel` (`"combo_variant_pieces"`, composite PK
        `(spellbook_id, name_key)`, `Index` on `name_key`), `ComboSnapshotMetaModel`
        (`"combo_snapshot_meta"`, `id` PK with `CheckConstraint("id = 1")`). Typed
        `Mapped[...]` + `mapped_column(...)` with dataclass init flags, matching
        `deck_card.py` style. `cards`/`produces` are `Text` JSON columns with paired
        `cards_list`/`produces_list` property+setter (copy the `DeckModel.tags_list`
        json.loads/dumps pattern — never assign raw JSON strings from outside).
  - [x] No FK from `combo_variant_pieces.spellbook_id` to `combo_variants` is required
        (both are written/deleted together in one transaction; keep it simple), but if you
        add one, add `ondelete="CASCADE"`.
  - [x] Register all three in `src/data/database.py`'s model-import block with
        `# noqa: F401` (the side-effect import rule — miss this and `create_all` silently
        skips the tables).
  - [x] Docstrings state: written ONLY by `scripts/import_spellbook_combos.py`; read-only
        everywhere else (AD-5); `bucket`/derived fields deliberately not stored (AD-11).

- [x] **Task 4 — Normalizer + import orchestrator** (AC: 2, 5)
  - [x] `src/data/importers/spellbook.py`:
    - [x] `SPELLBOOK_TAG_TO_CANONICAL: Final[dict[str, ComboBracketTag]]` — exactly the six
          mappings from AC 2 (letter keys). `_BANNED_TAG: Final = "B"`. A wire tag outside
          these seven raises `SpellbookImportError` naming the tag and the variant id.
    - [x] `transform_spellbook_variant(variant: dict) -> ComboRecord | None` — returns a
          validated `ComboRecord` (bucket=None), or `None` for the three counted skip cases
          (non-OK status / non-empty `requires` / banned tag); collects skip reasons via an
          optional stats collector (the `TransformReject` precedent in `transformers.py`).
          Pydantic construction IS the validation: empty `cards`, unknown normalized tag →
          `ValidationError` → import aborts (never catch-and-continue).
    - [x] Streaming parse: `gzip.open(downloaded_path, "rb")` → `ijson` over the stream —
          capture top-level `timestamp` + `version` scalars (they precede `variants` in the
          file), then iterate `variants.item` (the `parser.stream_cards` precedent; the
          trailing top-level `aliases` array is naturally ignored by the prefix filter —
          do not load the 579 MB document into memory).
    - [x] `async def import_spellbook_snapshot(session, *, temp_dir=None) -> SpellbookImportStats`
          orchestrates: download (Task 2) → normalize ALL variants into memory (~100k
          records, fine) → guard: zero eligible variants aborts loudly (a healthy export
          has tens of thousands; zero means a broken/truncated file) → **one transaction**:
          `DELETE` pieces, `DELETE` variants, insert new rows (batch via
          `session.execute(insert(...), [dicts])` for the 100k/200k+ row volume — a
          per-object `session.add` loop will crawl), upsert meta row, `COMMIT`. Rollback on
          any `IntegrityError`/`DatabaseError` before re-raising (transaction discipline).
    - [x] Piece rows: `{name_keys(name) for name in record.cards}` per variant — dedup'd
          set per variant (a quantity-2 piece or a DFC key collision must not produce
          duplicate PK rows).
    - [x] `SpellbookImportStats` dataclass: totals + the three skip counters + piece-row
          count + export timestamp/version + elapsed (mirror `ImportStatistics` shape).
  - [x] `imported_at`: `datetime.now(UTC)` ISO-8601 — clock use is legal HERE (offline
        import path); it is exactly the stored-metadata "as of" that AD-8 lets the
        assessment output cite instead of a call-time clock.

- [x] **Task 5 — CLI script + docs** (AC: 6, 7)
  - [x] `scripts/import_spellbook_combos.py` mirroring `import_scryfall_data.py`: argparse
        (`--db-path` default → `src.paths.database_path()`, `--temp-dir`), engine +
        `init_database(engine)` (creates the new tables additively on existing DBs — this
        replaces any migration script) + session factory, run the orchestrator, print the
        AC-6 summary block, exit 0/130/1. Module docstring: `uv run` usage, "operator-
        initiated, never automatic", upstream regenerates ~every 2 hours, snapshot is a
        build prerequisite never committed.
  - [x] README: short "Combo snapshot (deck power assessment)" section per AC 7, placed
        near the semantic-search-index section. Include Commander Spellbook attribution
        (commanderspellbook.com; data via their public bulk export).

- [x] **Task 6 — Tests (RED first, per TDD discipline)** (AC: 9)
  - [x] `tests/unit/data/schemas/test_combo.py` (or wherever `ComboRecord` tests live —
        extend, don't fork): `name_keys` behavior pinned at its NEW home (plain name → one
        key; `"A // B"` → two keys; lowercasing).
  - [x] `tests/unit/data/importers/test_spellbook_transform.py`: field mapping from a
        representative wire dict (id/cards/quantity-repetition/mustBeCommander-any/
        produces-feature-names/popularity); letter-map: all six letters → canonical tokens;
        `B` → skipped+counted; unknown letter (`"X"`) → loud error naming variant id;
        `status="E"` → skipped+counted; non-empty `requires` → skipped+counted;
        `zoneLocations=["C"]` with `mustBeCommander=false` → `commander_required` False
        (proves the authoritative-flag rule).
  - [x] `tests/unit/data/importers/test_spellbook_download.py`
        (`test_download_hardening.py` pattern, `httpx.MockTransport`): User-Agent + Accept
        headers present on the request; body over `max_bytes` → abort, partial file
        removed, no retry; transport error → backoff then success; all retries exhausted →
        `SpellbookAPIError`.
  - [x] `tests/integration/data/test_spellbook_import_e2e.py` (tmp DB via the
        `test_scryfall_import_e2e.py` `test_db` fixture pattern; monkeypatch
        `download_variants_export` to drop a local gzipped fixture payload):
    - [x] fresh import → variants/pieces/meta rows correct; DFC piece (`"Alive // Well"`)
          yields both key rows; meta carries fixture `timestamp`/`version` + non-null
          `imported_at`; `variant_count` matches.
    - [x] re-run with a changed payload → old rows gone, new rows present, meta updated
          (idempotent replace).
    - [x] second run with a poisoned payload (unknown tag) → raises; FIRST snapshot still
          fully present (atomicity).
    - [x] payload with zero eligible variants → raises; previous snapshot intact.
  - [x] Async tests: plain `async def test_...` (asyncio_mode auto); integration files
        carry the `integration` marker convention.

- [x] **Task 7 — Quality gates** (AC: 8)
  - [x] `uv run ruff check . --fix && uv run ruff format .`
  - [x] `uv run mypy src/`
  - [x] `uv run pytest -m "not integration"` then the new/touched integration files, then
        the full suite — baseline at story start: **1,174 passed, 0 failed, 0 skipped**
        (story 6.1 close). Anything below is a regression you introduced.
  - [x] Optional live acceptance (recommended, mirrors the importer-gate practice): run the
        real script once against the live central DB, record the summary in the Dev Agent
        Record (expect ~100k variants, ~1.5k banned-tag skips, import in seconds).
  - [x] Commit normally — `build-plugin-sync` hook re-mirrors `plugin/server/src/`; never
        hand-edit the mirror.

## Dev Notes

### What this story is (and is NOT)

The **offline import half** of the local combo snapshot (feature Story 3.2, sprint key `6-2`,
AD-5). It does NOT include:
- **The snapshot repository** (Story 6.3) — no read path in `src/data/repositories`, no
  relevance filtering, no `combo_data_unavailable` decision. You only create the tables 6.3
  will read (including the `combo_variant_pieces` index its name-filter needs).
- **Matching or scoring** — `match_combos` (5.6) is done and must not change behavior; the
  only edit to `src/logic/assessment/combos.py` is the `name_keys` import swap (Task 1).
- **Edge/tool work** (Epic 7): no MCP tool calls this script; degradation tokens are Epic 7's.
- **The benchmark re-run with real snapshot data** — epic-5 retro action item 10 fires after
  6.3, not here.

### Wire format — verified against the live export 2026-07-16 (re-verify in Task 0)

Live research (bulk file downloaded + parsed; backend source
`SpaceCowMedia/commander-spellbook-backend` read):

- **URLs:** `https://json.commanderspellbook.com/variants.json.gz` (~25.6 MB, use this) and
  `.../variants.json` (~579 MB raw). **`.zst` does not exist (403).** Served from
  CloudFront/S3; ETag + Last-Modified present. The paginated REST API
  (`backend.commanderspellbook.com/variants/`) is NOT the bulk path — ignore it.
- **Top level:** `{"timestamp": "<ISO-8601>", "version": "<backend release, e.g. 5.6.0>",
  "variants": [...], "aliases": [...]}`. `timestamp` + `version` are the export-version
  metadata (AC 3). `aliases` (dead-variant-id redirects) trails AFTER `variants` — ignored
  by the ijson prefix, but don't be surprised by it when eyeballing the file.
- **Variant keys:** `id`, `status`, `uses`, `requires`, `produces`, `of`, `includes`,
  `identity`, `manaNeeded`, `manaValueNeeded`, `easyPrerequisites`, `notablePrerequisites`,
  `description`, `notes`, `popularity`, `spoiler`, `bracketTag`, `legalities`, `prices`,
  `variantCount`. This story consumes exactly: `id`, `status`, `uses` (`card.name`,
  `quantity`, `mustBeCommander`), `requires` (emptiness only), `produces`
  (`feature.name`), `popularity`, `bracketTag`. Everything else is deliberately dropped —
  the snapshot is `ComboRecord`-shaped, not wire-shaped (AD-5 "not raw JSON").
- **`mustBeCommander` is authoritative** for `commander_required`. `zoneLocations` is a
  trap: backend data has `mustBeCommander: true` with `zoneLocations: ["B"]` (commander
  already on battlefield, 381 entries) and `["C","H"]` with `mustBeCommander: false` (may
  optionally start in command zone, 682 entries). Deriving from `zoneLocations` mis-flags
  both groups.
- **`status` enum** (backend): `N/D/NR/OK/E/R/NW`; the export ships `public_statuses() =
  (OK, EXAMPLE)`. Today: 100,133 records, all `"OK"`. Filter `== "OK"`.
- **Scale (today):** 100,133 variants; `bracketTag` distribution E 86,366 / R 6,254 /
  S 3,015 / P 2,558 / B 1,468 / C 258 / O 214; max popularity 329,870; 0 null popularity
  (but the backend model allows null — keep `int | None`).
- Upstream regenerates **every 2 hours** (k8s CronJob). No published rate-limit/UA policy
  exists (checked repo + docs site + about page) — descriptive UA + single download is
  polite enough.

### The bracket-tag decision (story-creation decision — read before "fixing" it)

Spellbook **renamed its tag vocabulary** since the spine was written: the live enum is
`R`uthless / `S`picy / `P`owerful / `O`ddball / `C`ore / `E`xhibition / `B`anned — there is
no PRECON_APPROPRIATE or CASUAL on the wire. The frozen `ComboBracketTag` Literal (5.6,
test-pinned) keeps the spine's six tokens. Resolution: **normalize at import** via the closed
letter→token map (AC 2). It is semantically lossless — Spellbook's own derived bracket
numbers (R→4, S/P→3, **O/C→2, E→1**, B→null) coincide exactly with the spine's
`BRACKET_TAG_TO_BRACKET` under `C→PRECON_APPROPRIATE (2)`, `E→CASUAL (1)`. `B` has no
canonical token and no bracket number → skip + count (a banned-combo variant must not set a
Bracket floor; deck-legality problems are the legality checker's job, not the combo
snapshot's). This is a **closed explicit map, not a fuzzy fallback** — the 5.6 "no
speculative aliases" rule binds anything OUTSIDE the seven known letters: hard error, abort,
previous snapshot intact. Do NOT widen the `ComboBracketTag` Literal or touch
`BRACKET_TAG_TO_BRACKET` — that reopens the frozen 5.6 contract for zero benefit.

### Skip-vs-error policy (decide-once, tested)

| Wire condition | Action | Why |
|---|---|---|
| `status != "OK"` | skip + count | EXAMPLE variants aren't real combos |
| `requires` non-empty | skip + count | name matcher can't verify a template piece; importing ⇒ false `included` buckets |
| `bracketTag == "B"` | skip + count | banned; no canonical token, Spellbook brackets it `null` |
| `bracketTag` ∉ 7 known letters | **hard error, abort** | unknown vocabulary must never map to a wrong floor (AD-11) |
| duplicate `spellbook_id` | **hard error, abort** (PK violation → rollback) | corrupt export; atomicity keeps old snapshot |
| zero eligible variants after skips | **hard error, abort** | healthy export ⇒ tens of thousands; zero = broken file |
| variant missing `uses[].card.name` / empty `cards` | **hard error, abort** (Pydantic `min_length=1`) | malformed variant must not masquerade as matched (5.6 review patch) |
| `legalities` (any format) | **no filter** | the matcher only matches cards actually in the deck; a format-illegal combo self-filters. Keep the import format-agnostic |

### Atomicity model — why no `import_state` marker

The card importer commits per 1,000-card batch, so it needs the `import_state` in-progress
marker to distinguish "killed mid-import" from "complete". This import is deliberately
different: normalize everything first (fail fast while the DB is untouched), then a
**single transaction** for delete-old + insert-new + meta upsert. A crash at any point
leaves either the old snapshot or the new one — never a partial. WAL mode means concurrent
MCP readers are never blocked; they see the old snapshot until the commit lands. Do not add
the marker, do not batch-commit. (~100k variant rows + ~200k piece rows in one transaction
is a few seconds of SQLite work — verified scale, not a guess.)

### Memory + streaming discipline

The raw JSON is ~579 MB — **never** `json.load` it. Stream: `gzip.open(path)` →
`ijson.parse`/`ijson.items` with prefix `variants.item` (precedent:
`src/data/importers/parser.py::stream_cards`). Capture `timestamp`/`version` from the
event stream before the array starts (they precede `variants` in the file). Normalized
`ComboRecord`s for ~98k eligible variants fit comfortably in memory — collecting them all
before the transaction is the point (fail-fast before touching tables).

### `name_keys` relocation — the one cross-layer edit

`grep -rn "_name_keys" src/ tests/` at story creation: defined+used ONLY inside
`src/logic/assessment/combos.py` (4 call sites, docstring refs; no test imports it). The
alias-import (`from src.data.schemas.combo import name_keys as _name_keys`) is therefore a
zero-churn move. The schema layer is the right home: `ComboRecord`'s module docstring
already documents why cross-layer combo vocabulary lives there (repo returns Pydantic; data
can't import logic). The epic-5 retro (item 9) pinned this story to REUSE the function —
the DFC front-face hazard bit 5.3, 5.6, and 5.9; a re-implementation in the importer is the
exact failure mode being prevented.

### Previous-story intelligence (6.1 + epic-5 retro + importer gate)

- **Verify, don't trust** (retro item 7 → Task 0): this story's notes assert live-DB state
  ("no combo tables") and live-wire state (URL/shape) — both get the cheap probe before code.
- **The Pre-Epic-6 Importer Gate exists because of THIS story**: Sathias ruled 6.2 must be
  built against a healthy import precedent (G-I1/2/3 closed 2026-07-15). Inherit its
  standards: per-item errors surfaced with name + reason in the summary (AC 6's skip
  counters), regression tests that survive a re-import (AC 9's idempotency/atomicity tests).
- **6.1's review lesson** (silent flag-drop in a third constructor): when a value threads
  through multiple constructors, grep every construction site before claiming done. Here:
  `ComboRecord(...)` is constructed in the normalizer AND in test fixtures — keep the
  fixture factory in one place (5.6's tests already have a record factory; reuse it).
- **Plugin mirror:** expect `plugin/server/src/data/...` diffs after commit (generated by
  the hook). `scripts/` is not mirrored.
- **DFC hazard scoreboard:** 5.3 (`oracle_text=""` faces), 5.6 (commander gate missed
  front-face), 5.9 (front-face-only names in fixtures). This story is where the hazard
  crosses layers — hence Task 1 before any importer code.

### Architecture compliance checklist

- **AD-5:** snapshot tables written ONLY by the script; assessment read-only; metadata row
  = `data_vintage` source; canonical rows, not raw JSON.
- **AD-9:** downloader in `src/data/importers/` (sibling to `scryfall_api.py`); manual
  backoff, no `tenacity`; explicit timeout + UA + Accept; failed download leaves previous
  snapshot intact; never imported by `src/logic` or the assessment path.
- **AD-11:** wire → `ComboRecord` normalization here, once; unknown tag = loud error;
  `bucket`/derived fields never stored.
- **AD-2/AD-8 (respected at a distance):** the clock is used only for `imported_at` stored
  metadata (legal — it's input metadata, not call-time output); nothing here touches the
  pure core.
- **Layer contract:** new models return nothing to callers directly — Story 6.3's repo will
  do `ComboRecord.model_validate`-style exits. `src/data` imports nothing from `src/logic`
  (Task 1 exists precisely to keep it that way).
- **Stateless tools rule (D5):** untouched — this is a script, not a tool. Do NOT register
  any MCP tool for the import in this story.

### Testing standards summary

- pytest config in `pyproject.toml`; `asyncio_mode = "auto"` (no marker needed);
  `--strict-markers`; integration tests marked `integration`.
- Layout mirrors `src/`: unit importer tests in `tests/unit/data/importers/`, e2e in
  `tests/integration/data/`. Reuse the `test_db` tmp-path fixture pattern and
  `httpx.MockTransport` helper shape from the named precedent files — do not spin up a new
  harness.
- Fixture payloads: small hand-built dicts gzipped on the fly in the test (or a tiny
  committed `.json` fixture — the scryfall sample precedent); NEVER the real 25 MB export.
- `tests.*` exempt from `mypy --strict`; ruff/naming still apply.
- Full-suite baseline at story start: **1,174 passed / 0 failed / 0 skipped**.

### Project Structure Notes

- New files: `src/data/importers/spellbook_api.py`, `src/data/importers/spellbook.py`,
  `src/data/models/combo.py`, `scripts/import_spellbook_combos.py`, three test files.
- Modified: `src/data/schemas/combo.py` (+`name_keys`), `src/logic/assessment/combos.py`
  (import swap only), `src/data/database.py` (model registration), `README.md`.
- Naming: models suffixed `*Model`; tables `snake_case`; constants `UPPER_SNAKE`;
  Google-style docstrings with module docstring per file; modern 3.12 syntax
  (`int | None`); logging via module `logger` with lazy `%` args (scripts may `print` in
  the summary block — the established CLI precedent).
- Branch: stays on `feat/deck-power-assessment` (no master merge until Epic 7 — epic-5
  retro). Conventional Commit: `feat: spellbook bulk combo-snapshot import (story 6.2)`.

### References

- [Source: _bmad-output/planning-artifacts/epics-deck-power-assessment.md#Story 3.2] — story
  + ACs (epic file numbers this "3.2"; sprint tracks it as `6-2`); AD-5/AD-9/AD-11 texts.
- [Source: _bmad-output/planning-artifacts/sprint-change-proposal-2026-07-12.md#P1/P2/P3] —
  bulk-snapshot re-scope rationale (deleted the live dependency, cache key, clock tokens).
- [Source: _bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-11/ARCHITECTURE-SPINE.md#AD-5]
  — snapshot table + metadata row + read-only rule; #AD-9 downloader placement/policy;
  #AD-11 normalize-at-import.
- [Source: _bmad-output/implementation-artifacts/epic-5-retro-2026-07-15.md#Epic 6 preparation notes]
  — items 7 (`name_keys` reuse), 9 (story-start verification), 10 (post-6.3 benchmark re-run).
- [Source: _bmad-output/implementation-artifacts/5-6-combo-record-combo-bracket-mapping.md#Spellbook wire-format caveat]
  — "6.2 verifies the live export, normalizes wire→ComboBracketTag, fails loudly; no fuzzy
  fallback".
- [Source: src/data/schemas/combo.py] — `ComboRecord` + `ComboBracketTag` (the contract this
  story populates); the layering rationale `name_keys` inherits.
- [Source: src/logic/assessment/combos.py:87-108] — `_name_keys` to relocate; :157-219 the
  matcher consuming stored records (multiplicity via `Counter(cards)` — why quantity
  repetition matters).
- [Source: src/data/importers/scryfall_api.py] — download hardening template (backoff,
  ceiling, partial-file cleanup, streaming).
- [Source: src/data/importers/scryfall.py:30-61] — URI/ceiling policy precedents;
  transaction + rollback discipline.
- [Source: src/data/importers/parser.py] — ijson streaming precedent.
- [Source: src/data/importers/transformers.py] — `TransformReject` collector precedent for
  skip/reject reporting.
- [Source: scripts/import_scryfall_data.py] — CLI shape (args, summary block, exit codes).
- [Source: scripts/build_card_embeddings.py] — build-prerequisite-never-committed pattern +
  bootstrap guard wording.
- [Source: src/data/database.py:17-21] — model side-effect import block to extend.
- [Source: src/data/import_state.py] — the marker this story deliberately does NOT need
  (single-transaction atomicity).
- [Source: src/paths.py] — `database_path()` for the CLI default; `CARDS_DATABASE_URL`
  precedence.
- [Source: tests/unit/data/importers/test_download_hardening.py] — MockTransport test
  pattern; [Source: tests/integration/data/test_scryfall_import_e2e.py] — tmp-DB +
  monkeypatched-download e2e pattern.
- Live wire facts (2026-07-16): bulk export `json.commanderspellbook.com/variants.json[.gz]`;
  backend source github.com/SpaceCowMedia/commander-spellbook-backend
  (`spellbook/models/variant.py` BracketTag/Status enums;
  `spellbook/models/ingredient.py` ZoneLocation + must_be_commander validation;
  `spellbook/tasks/export_variants.py` + `s3_upload.py` export writer;
  `.kubernetes/app/jobs/prod/kubernetes.yaml` 2-hour cron).

## Dev Agent Record

### Agent Model Used

claude-fable-5 (Claude Fable 5)

### Debug Log References

- **Task 0 live DB check (2026-07-16):** `SELECT name FROM sqlite_master WHERE
  type='table' AND name LIKE 'combo%'` against
  `C:\Users\brads\AppData\Local\artificial-planeswalker\cards.db` → **no rows** (clean
  start confirmed).
- **Task 0 live export check (2026-07-16):** HEAD `variants.json.gz` → 200,
  content-length 25,624,172 (~25.6 MB), `content-encoding: gzip`, ETag + Last-Modified
  present; HEAD `variants.json` → 200, 579,221,029 bytes. Decompressed head confirmed
  top-level key order `timestamp` → `version` → `variants`; first variant carried
  exactly the documented keys (`id`, `status`, `uses[].card.name/quantity/
  mustBeCommander/zoneLocations`, `requires`, `produces[].feature.name`, `popularity`,
  `bracketTag`). Wire map NOT stale — proceeded. The httpx decoding trap reproduced
  live: a 256 KiB ranged GET returned 5.4 MB decompressed.
- **MockTransport + `aiter_raw` gotcha (Task 2 tests):** `httpx.Response(content=...)`
  pre-reads its body in `__init__` and marks the stream consumed, so `aiter_raw()`
  raises `StreamConsumed`. Handlers must return `httpx.Response(stream=...)` (a real
  transport-level stream) — encoded as the `_AsyncBody` helper in
  `test_spellbook_download.py`. (`aiter_bytes` masks this by falling back to
  `_content`, which is why the Scryfall tests never hit it.)
- **`ijson.common.items` is deprecated:** initial single-pass header+variants parse
  emitted `DeprecationWarning`; refactored to two passes — `_read_export_header`
  (ijson.parse, terminates at `variants` start_array after a few bytes) +
  `_stream_variants` (modern `ijson.items` on a fresh handle).
- **ijson Decimal coercion:** ijson parses JSON numbers as `Decimal`; `quantity` is
  `int()`-coerced before piece-name list repetition, `popularity` before storage.

### Completion Notes List

- **Task 1:** `_name_keys` relocated to `src/data/schemas/combo.py` as public
  `name_keys()` (with `_FACE_SEPARATOR`); `src/logic/assessment/combos.py` now
  alias-imports it. All 46 matcher tests passed untouched (relocation additivity
  proof); 4 new tests pin the policy at the new home.
- **Task 2:** `spellbook_api.py` mirrors the Scryfall hardening (streaming, ceiling
  abort with no retry + partial-file cleanup, manual exponential backoff) plus the
  AD-9 headers (descriptive UA with repo URL + `Accept: application/json`) and
  `aiter_raw` streaming (wire bytes, ceiling measures compressed size). 8 tests incl.
  two pinning the decoding trap.
- **Task 3:** three ORM models registered in `database.py`'s side-effect import block;
  `bucket`/derived fields never stored; JSON-in-Text `*_list` accessors per the
  `DeckModel.tags` pattern; meta row `CHECK (id = 1)`. 9 tests.
- **Task 4:** closed letter→token map (six pairs), `B` skipped+counted, unknown tag =
  loud `SpellbookImportError` naming variant + tag; skips collected via `VariantSkip`
  (TransformReject precedent); `commander_required = any(mustBeCommander)` (proven
  against a `zoneLocations=["C"]` decoy); orchestrator normalizes everything before
  ONE delete+insert+meta-upsert transaction with rollback on `IntegrityError`/
  `DatabaseError`; per-variant piece keys dedup'd + sorted. 18 unit tests.
- **Task 5:** CLI mirrors `import_scryfall_data.py` (argparse, central-DB default,
  `init_database` in lieu of a migration, AC-6 summary block, exit 0/130/1); README
  gained "Combo snapshot (deck power assessment)" beside the semantic-search section
  + Commander Spellbook attribution (also in Acknowledgments).
- **Task 6:** 5 e2e tests (fresh populate incl. DFC keys, idempotent replace,
  poisoned-payload atomicity, zero-eligible abort, skip counters) on a tmp DB with
  monkeypatched download — no live network in any test.
- **Task 7 gates:** ruff clean; `mypy --strict` clean (67 files); full suite **1,219
  passed / 0 failed / 0 skipped** with 44 new tests collected across the five new
  test files (story-start baseline noted 1,174 — above baseline, zero failures, no
  regressions).
- **Live acceptance (2026-07-16, central DB):** export 100,133 variants → 94,962
  imported; skips: 0 status / 3,719 requires-template / 1,452 banned-tag; 344,176
  piece rows; export version 5.6.0, timestamp 2026-07-16T07:28:23Z; 12.4 s elapsed.
  Post-import sanity: canonical tag distribution (CASUAL 82,835 / RUTHLESS 6,165 /
  SPICY 2,983 / POWERFUL 2,507 / PRECON_APPROPRIATE 258 / ODDBALL 214), meta row
  correct, DFC piece keys present with both full-name and front-face rows.

### File List

- `src/data/schemas/combo.py` (modified — +`name_keys` + `_FACE_SEPARATOR`, module
  docstring extended)
- `src/logic/assessment/combos.py` (modified — `name_keys` alias import, local
  definition dropped)
- `src/data/importers/spellbook_api.py` (new)
- `src/data/importers/spellbook.py` (new)
- `src/data/models/combo.py` (new)
- `src/data/database.py` (modified — combo model registration)
- `scripts/import_spellbook_combos.py` (new)
- `README.md` (modified — combo-snapshot section + attribution)
- `tests/unit/data/schemas/test_combo.py` (new)
- `tests/unit/data/importers/test_spellbook_download.py` (new)
- `tests/unit/data/importers/test_spellbook_transform.py` (new)
- `tests/unit/data/models/test_combo.py` (new)
- `tests/integration/data/test_spellbook_import_e2e.py` (new)
- `plugin/server/src/...` (generated — `build-plugin-sync` pre-commit mirror of the
  `src/` changes)

## Change Log

- 2026-07-16: Story 6.2 implemented — Spellbook bulk combo-snapshot import
  (downloader + normalizer + atomic single-transaction refresh + CLI + docs);
  `name_keys` relocated to the schema layer (epic-5 retro item 9); 44 new tests;
  full suite 1,219 green; live acceptance imported 94,962 variants into the central
  DB. Status → review.

### Review Findings

Code review 2026-07-16 (adversarial: Blind Hunter + Edge Case Hunter + Acceptance
Auditor). Verdict: strongly compliant, all 9 ACs satisfied, plugin mirror byte-identical.
No high/medium findings — all six survivors are Low. Six reviewer claims dismissed
after verification (see summary in the review conversation). **All six patches applied
2026-07-16** (32 affected tests green, mypy + ruff clean, plugin mirror re-synced).

- [x] [Review][Patch] `--temp-dir` download file left behind on the operator-supplied path [src/data/importers/spellbook.py:365] — when `--temp-dir` is passed, `created_dir` stays `None` so the `finally` skips cleanup; `variants.json.gz` (~26 MB) is not deleted (overwritten each run, not accumulated). The `scryfall.py` precedent `unlink(missing_ok=True)`s the file even when the caller owns the dir. **Fixed:** `finally` now unlinks the download file on the caller-supplied-dir branch.
- [x] [Review][Patch] Corrupt/empty/non-gzip download surfaces the wrong exception type [src/data/importers/spellbook.py:199,230] — a truncated/garbage body raises raw `gzip.BadGzipFile`/`EOFError`/`ijson.IncompleteJSONError`, not the `SpellbookImportError` the header/stream docstrings promise for a "broken or truncated file" (the `parser.py` precedent wraps ijson errors). Fails safe (no DB writes; prior snapshot intact) — error-contract inconsistency only. **Fixed:** `_read_export_header` and `_stream_variants` now wrap `(gzip.BadGzipFile, EOFError, ijson.JSONError)` into `SpellbookImportError`.
- [x] [Review][Patch] Unguarded wire dict access aborts with a bare `KeyError` naming no variant [src/data/importers/spellbook.py:167,176] — `use["card"]["name"]` and `entry["feature"]["name"]` `KeyError` on a structurally malformed variant, aborting the whole import. The abort outcome matches the skip-vs-error table, but the bare `KeyError` (no variant id) falls short of the importer-gate "name + reason" diagnostic standard. **Fixed:** both accesses guarded; a missing card/feature name now raises `SpellbookImportError` naming the variant id.
- [x] [Review][Patch] Non-positive quantity silently defaults/drops a piece [src/data/importers/spellbook.py:166] — `int(use.get("quantity") or 1)` maps a real `0` → `1` and a negative → `[name]*-1 == []` (piece dropped), storing an incomplete combo (matcher false-positive risk). Dormant: live Spellbook quantities are ≥1. **Fixed:** `quantity = int(raw) if not None else 1`, repeated `max(quantity, 1)` times — never drops a listed piece.
- [x] [Review][Patch] CLI disposes the engine only on the success path [scripts/import_spellbook_combos.py:114] — `await engine.dispose()` is inside the `try`; any failure returns 1 without disposing. Cosmetic for a short-lived process; belongs in a `finally`. **Fixed:** engine hoisted, disposed in a `finally`.
- [x] [Review][Patch] Mid-transaction rollback branch is untested [src/data/importers/spellbook.py:344 — test gap] — both atomicity tests abort during normalization, before the transaction opens, so `except (IntegrityError, DatabaseError): rollback` never executes under test. The duplicate-`spellbook_id` → PK-violation → rollback guarantee (docstring + skip-vs-error table) has no covering test. **Fixed:** added `test_duplicate_spellbook_id_rolls_back_leaving_snapshot_intact` (duplicate-PK payload → `IntegrityError`, first snapshot survives).
