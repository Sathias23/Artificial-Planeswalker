---
baseline_commit: 4dc6d3ca189acbea7020041bfcc454f8b1d99809
---

# Story 5.1: Compose the calibration benchmark set

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

> **Sprint/feature numbering:** this is sprint key `5-1-compose-the-calibration-benchmark-set`
> (`epic-5`), which is **feature Epic 2, Story 2.1** in
> `_bmad-output/planning-artifacts/epics-deck-power-assessment.md`. Sprint Epic 5 = feature Epic 2
> "Deterministic scoring core". This is the **first story of Epic 5** — it flips `epic-5` to
> `in-progress`.

## Story

As the scorer's author,
I want a committed, held-out set of decklists with documented expected outcomes,
so that "done" for the scoring core is decidable against a fixed acceptance gate rather than blocked
on an open question.

## Context & why this story exists

This is the **acceptance gate for the entire Epic 5 scoring core** (NFR6, Success Metric 1). The
architecture and PRD both name benchmark composition as the **first implementation task** and an
explicit open question this story closes:

- Architecture spine, "Deferred": *"Benchmark-set composition (which precons + cEDH lists) — the
  first implementation task; becomes the acceptance signal for the scorer once composed."*
  [Source: architecture/…/ARCHITECTURE-SPINE.md#Deferred]
- SPEC Open Questions: *"Benchmark composition — which precons and cEDH lists make up the
  calibration set. The first implementation task; becomes the scorer's acceptance signal once
  composed."* [Source: specs/spec-deck-power-assessment/SPEC.md#Open Questions]

**Downstream consumer:** Story 5.9 (feature 2.9, "Pure `score()` entry point + benchmark
validation") asserts the finished scorer against this set: *"run against Story 2.1's benchmark, WotC
precons land ~Bracket 2 and cEDH lists flag as candidates"*. This story **produces the data and a
pure loader only** — it must contain **no scorer, no scoring math, and no dependency on
`src/logic/assessment/`** (which does not exist yet). [Source: epics-deck-power-assessment.md#Story
2.1 and #Story 2.9]

**The template to copy:** `tests/integration/search/test_rag_eval.py` is the closest existing
precedent (the Epic-2 RAG sanity eval, story 2.6). Copy its *data + documented vocabulary + pure
offline-testable helper + offline guard test* half; **omit** its integration/model half (that is the
analogue of the deferred scorer assertion). [Source: tests/integration/search/test_rag_eval.py]

## Acceptance Criteria

1. **A committed benchmark dataset exists as a typed, deterministic Python module + decklist files.**
   Given the acceptance gate (NFR6, Success Metric 1), when the benchmark is composed, then it
   commits a `BenchmarkEntry` dataset (a frozen dataclass or typed `tuple`/`NamedTuple` shape) plus
   one raw decklist text file per entry, all under `tests/` (see Project Structure Notes for the
   exact paths). No scorer, no `src/logic/assessment/` import, no computed scores.
   [epics 2.1; AD-2; test_rag_eval.py precedent]

2. **Each entry records format + decklist + expected Bracket / flag / tier outcome.** Given the AC's
   required fields, when an entry is defined, then it carries at minimum:
   `key` (stable snake_case id), `format` (`"commander" | "standard"`), `decklist_file` (filename of
   the committed raw decklist), `expected_bracket` (`int` 1–5 for Commander; **`None` for Standard**
   — Standard has no Bracket, FR20), `expected_cedh_candidate` (`bool`), `expected_tier_label` (a
   descriptive tier word from the FR24 vocabulary), `source` (provenance: public URL / precon name +
   date, for auditability and refresh — NFR5), and `notes` (one-line rationale).
   [epics 2.1; FR20, FR24, NFR5; docs/deck-assess.md#7.3, #Option F]

3. **Membership covers the required anchors across both format forks.** Given Success Metric 1 and
   the Commander/Standard fork (FR20), when the set is composed, then it includes **≥ 3 WotC
   Commander precons** (`expected_bracket = 2`, `expected_cedh_candidate = False`), **≥ 2 known cEDH
   lists** (`expected_bracket = 4`, `expected_cedh_candidate = True` — **floor 4, never assert
   Bracket 5**, AD-7/FR18), **and ≥ 1 Standard deck** (`format = "standard"`, `expected_bracket =
   None`, `expected_cedh_candidate = False`, ~60 cards) so Story 5.9 can validate the heuristic-only
   fork. Recommended additional spread (see Dev Notes): 1 "upgraded" Commander deck
   (`expected_bracket = 3`) as a middle anchor. Keep the whole set to a *handful* (~6–9 entries) —
   this is a calibration anchor, not a corpus. [epics 2.1; addendum §C, §D; FR18, FR20; AD-7]

4. **Expected outcomes are categorical/directional — never a committed exact numeric score.** Given
   WotC's own "brackets are intent-based and not an exact science" caveat and NFR5 data-freshness
   volatility, when expectations are recorded, then they are the **categorical Bracket**, the
   **cEDH-candidate boolean**, and the **descriptive tier label** only. **No `expected for-format
   0–100 score` and no per-dimension numbers** are committed (v1 is uncalibrated for absolute
   numbers; that is false precision). The module docstring documents that the *asserting* story
   (5.9) applies "bracket up when in doubt" tolerance (e.g. accept a precon floor within
   `[expected, expected+1]`; accept any cEDH floor `>= 4`) — the tolerance lives with the assertion,
   the data stays a single clean target. [docs/deck-assess.md#9; NFR5; epics 2.9]

5. **A pure, offline loader + decklist parser turns the committed files into structured entries.**
   Given later stories must iterate the set, when `load_benchmark()` is called, then it returns the
   entries in a **deterministic (stable) order**, each with its raw decklist parsed into
   `(name, quantity, is_commander)` records by a **self-contained pure parser** (no DB, no network,
   no `import_decklist`). The parser accepts the project's Arena export format (`QUANTITY Name (SET)
   COLLECTOR` lines under `Commander` / `Deck` sections; `Sideboard` / `Companion` and the `About`
   block tolerated/skipped). Do **not** import the private `_parse_arena_export` /
   `_ParsedArenaLine` internals from `deck_import.py` (they are DB-flow-bound and private) — write a
   small pure parser, citing `deck_import.py:37` `_CARD_LINE_RE` as the format reference.
   [test_rag_eval.py `evaluate_hit_rate` precedent; deck_import.py:24-40; AD-2]

6. **Card names are exact and resolvable; the set is verify-by-shape, not by hardcoded card names.**
   Given Story 5.9 must resolve each decklist against the local Scryfall snapshot to build
   `list[Card]`, when decklists are committed, then card names are **exact oracle names** (verbatim
   from the public source) so name-resolution will succeed downstream. The **self-validation test
   asserts by shape** — file existence, parse success, card/commander counts in a documented range,
   field domains — and must **not** hardcode brittle specific card-name assertions (the Epic-4 retro
   lesson: the Game Changers list and decklists change over time — verify by shape, not by names).
   [epic-4-retro-2026-07-12.md#Backfill spot-check; NFR5]

7. **An offline self-validation test proves the dataset is well-formed (fast subset, no scorer).**
   Given the RAG-eval offline-guard precedent (`test_evaluate_hit_rate_and_failure_message`), when
   the test runs, then — with **no `@pytest.mark.integration`**, no DB, no model, no scorer — it
   asserts: every `decklist_file` exists and parses; each Commander entry has 1–2 commander-section
   cards and a mainboard total in the documented range (~100 incl. commander); each Standard entry
   has a mainboard in the documented range (~60) and `expected_bracket is None`; every
   `expected_bracket` is `None` or in `1..5`; cEDH entries have `expected_cedh_candidate is True` and
   `expected_bracket == 4`; every `expected_tier_label` is in the allowed vocabulary set; `key`s are
   unique; the AC3 minimums hold (**≥3 precons, ≥2 cEDH, ≥1 Standard**); and `load_benchmark()` is
   deterministic (two calls → equal order). It runs green under `uv run pytest -m "not integration"`.
   [test_rag_eval.py:372-400; pyproject.toml:88-101]

8. **Quality gates pass.** Given the project gates, when committed, then `ruff check` + `ruff format`
   are clean and `mypy --strict` passes over any code placed under `src/` (there should be **none**
   for this story — it is test-only; if the loader lives under `tests/`, `mypy --strict` does not
   gate it, but still write complete type hints to match `card_data.py` / `test_rag_eval.py`).
   Pre-commit succeeds without `--no-verify`. **No `src/` files are touched, so the
   `build-plugin-sync` mirror step is not required** for this story. [project-context.md#Code
   Quality; epic-4-retro action item 2]

## Tasks / Subtasks

- [x] **Task 1 — Decide + document the exact home and shapes** (AC: 1, 2)
  - [x] Create the dataset home under `tests/` (see Project Structure Notes for the recommended
        paths): a loader module `tests/fixtures/benchmark_decks.py` and a `tests/fixtures/benchmark/`
        directory for the raw decklist `.txt` files. Do **not** create `src/logic/assessment/` in
        this story (no scorer dependency; that package is Story 5.2's).
  - [x] Define the frozen `BenchmarkCard(name: str, quantity: int, is_commander: bool)` and
        `BenchmarkEntry(key, format, decklist_file, cards, expected_bracket, expected_cedh_candidate,
        expected_tier_label, source, notes)` shapes (frozen dataclasses, full type hints, Google
        docstrings — match `deck_import.py`'s `@dataclass(frozen=True, slots=True)` style and
        `card.py`'s schema-docstring style).
  - [x] Define the allowed tier-label vocabulary as a module-level `frozenset` — the FR24 /
        deck-assess Option F words: `{"Unfocused", "Focused", "Tuned", "High-Power", "Competitive"}`.
        Add a docstring note that Story 5.8/5.9's `FormatProfile` thresholds own the *authoritative*
        label mapping; this vocabulary must stay consistent with that module when it lands.

- [x] **Task 2 — Source and commit the real decklists** (AC: 3, 6)
  - [x] Source **≥3 WotC Commander precons** from a public list (WotC/Wizards official precon
        decklists, or a well-known aggregator such as EDHREC precon pages / Archidekt precon exports).
        Prefer recent precons (2024–2025) that are unambiguously "Core"/Bracket 2 out of the box.
        Export/transcribe each to Arena format (`QUANTITY Name (SET) COLLECTOR`, `Commander` then
        `Deck` sections) and commit as `tests/fixtures/benchmark/<key>.txt`. **Do not invent card
        lists** — copy verbatim from the source and record the URL/name in `source`.
  - [x] Source **≥2 known cEDH lists** (documented archetypes from the cEDH database / EDHREC /
        MTGGoldfish cEDH pages — e.g. a Thoracle-line list, a Kinnan list, a Najeela list). Commit
        the same way; set `expected_cedh_candidate = True`, `expected_bracket = 4`.
  - [x] **Required:** add **≥1 Standard deck** (`format = "standard"`, `expected_bracket = None`,
        `expected_cedh_candidate = False`, ~60-card mainboard, from a public constructed meta list —
        e.g. a current MTGGoldfish/MTGTop8 Standard archetype) so 5.9 can validate the heuristic-only
        fork (FR20). Commit it in Arena format with a `Deck` section (no `Commander` section);
        transcribe verbatim and record the `source`.
  - [x] (Recommended) Add **1 upgraded Commander deck** (`expected_bracket = 3`) as a middle anchor
        so 5.9 can validate the middle of the Commander range, not just the B2/B4 extremes.
  - [x] Populate the `BenchmarkEntry` manifest list in `benchmark_decks.py` with one entry per
        committed file, filling every field. Record honest provenance and a one-line `notes`
        rationale per entry (why this deck anchors this outcome).

- [x] **Task 3 — Write the pure loader + decklist parser** (AC: 5, 6)
  - [x] Write `parse_arena_decklist(text: str) -> tuple[BenchmarkCard, ...]`: a small pure function
        that walks lines, tracks the current section (`Commander`/`Deck`/`Sideboard`/`Companion`,
        case-insensitive), skips the `About` metadata block, and matches card lines with a regex
        mirroring `deck_import.py:37` `_CARD_LINE_RE`. Mark `Commander`-section cards
        `is_commander=True`; route `Deck` (and, for the mainboard count, ignore sideboard for
        Commander). No DB, no network, no private-internal import.
  - [x] Write `load_benchmark() -> tuple[BenchmarkEntry, ...]`: read each entry's `decklist_file`
        via a `Path(__file__).parent / "benchmark" / …` walk (the `scryfall_sample.json` loading
        precedent — see `tests/unit/data/importers/test_transformers.py:15-17`), parse it, attach the
        parsed `cards`, and return entries in a **stable, deterministic order** (source manifest
        order — do not sort by anything nondeterministic).
  - [x] Keep the module importable as `from tests.fixtures.benchmark_decks import load_benchmark`
        (the established fixture-import convention — see `tests/unit/data/test_card_repository.py:10`
        `from tests.fixtures.card_data import …`).

- [x] **Task 4 — Write the offline self-validation test** (AC: 7)
  - [x] Add `tests/unit/fixtures/test_benchmark_decks.py` (create `tests/unit/fixtures/__init__.py`
        if the directory is new — the tests tree is a package; see `tests/fixtures/__init__.py`).
        **No `@pytest.mark.integration`.**
  - [x] Assert the AC7 shape checks: file existence + parse success; per-format card/commander count
        ranges (document the ranges as module constants with a rationale comment, à la
        `TARGET_HIT_RATE`); `expected_bracket` domain (`None` or `1..5`); cEDH invariants
        (`candidate is True and bracket == 4`); Standard invariants (`bracket is None`,
        `candidate is False`); tier-label membership; unique `key`s; AC3 minimums (`≥3` precons,
        `≥2` cEDH, `≥1` Standard); and `load_benchmark()` determinism.
  - [x] Make failures **actionable** (name the offending entry/file), mirroring
        `test_rag_eval.py`'s `format_failure` — a shape failure must point at the bad entry, not just
        assert `False`.

- [x] **Task 5 — Manual resolvability smoke (optional, documented) + quality gates** (AC: 6, 8)
  - [x] The offline suite cannot confirm names resolve against the real snapshot. Optionally, against
        the live backfilled `cards.db` (present per epic-4 retro), run a quick name-resolution
        spot-check (`SELECT count(*) FROM cards WHERE name = ?` per unique benchmark card name) and
        record any unresolved names in the completion notes so 5.9 does not inherit typos. Do **not**
        commit a DB-bound test for this (keep the story's suite offline).
  - [x] `uv run ruff check tests/… --fix && uv run ruff format .`; `uv run pytest -m "not
        integration"` green; `uv run pre-commit run --all-files` — do not bypass hooks. Confirm **no
        `src/` file changed** (so no `build_plugin` mirror step needed).

## Dev Notes

### What this story is — and is NOT

- **IS:** committed acceptance data (decklists + expected categorical outcomes) + a pure offline
  loader/parser + an offline well-formedness test.
- **IS NOT:** any scoring logic, `FormatProfile`, oracle-text classifier, Karsten/hypergeometric
  math, or `src/logic/assessment/` package. This story has **zero** dependency on code that does not
  yet exist. If you find yourself computing a score, stop — that is Story 5.7/5.8/5.9.
  [Source: epics-deck-power-assessment.md#Story 2.1: "no scorer dependency yet"]

### The precedent to copy (read this file first)

`tests/integration/search/test_rag_eval.py` — the Epic-2 RAG sanity eval. Mirror the **top half**:
- `_CORPUS` / `_QUERY_FIXTURE` module-level typed constants = your `BenchmarkEntry` manifest.
  [test_rag_eval.py:47-188]
- `TARGET_HIT_RATE = 0.9` with a long calibration-rationale comment = your documented count-range
  constants and bracket-tolerance note. [test_rag_eval.py:28-39]
- `evaluate_hit_rate` / `format_failure` pure helpers unit-tested offline = your
  `parse_arena_decklist` / `load_benchmark` + the offline self-validation test.
  [test_rag_eval.py:197-240, 372-400]
- **Skip** the `@pytest.mark.integration` model-driven half (`rag_eval_index`,
  `test_rag_sanity_eval_top_k_hit_rate`) — that is the analogue of the deferred Story 5.9 assertion.

### Decklist format (the one that exists — do not invent another)

The project has exactly one decklist format: **Arena export**, parsed by
`src/mcp_server/tools/deck_import.py`.
- Card line regex, `deck_import.py:37-40`:
  `^(?P<quantity>\d+)\s+(?P<name>.+)\s+\((?P<set_code>[^()\s]+)\)\s+(?P<collector_number>\S+)$`
  — i.e. `1 Sol Ring (C21) 263`. A bare `1 Sol Ring` does **not** parse.
- Sections, `deck_import.py:24-33`: `Commander`, `Deck`, `Sideboard`, `Companion` (case-insensitive).
  `Commander`+`Deck` → mainboard; there is **no commander field** in the `Deck` model/schema — the
  section header is the *only* commander signal. Your `is_commander` flag comes from the section.
- `About` / `Name …` metadata block is skipped. [deck_import.py:31-32, 141-157]
- **`import_decklist` is DB-bound** (needs a seeded card DB + an existing saved deck and resolves
  names via `add_card_to_deck`). Do not route the benchmark through it. Store raw Arena text as
  data and parse it with your own pure function. Set/collector annotations are cosmetic for
  resolution (cards are aggregated oracle identities) but keep them so the files are real, valid
  Arena exports. [Source: deck_import.py:304-455; explorer finding §1]

### Schemas the downstream scorer will consume (context only — not touched here)

- `Card` (`src/data/schemas/card.py:8-88`): `game_changer: bool | None` (three-state, AD-4),
  `legalities: dict[str,str]`, `cmc: float`, `oracle_text`, `type_line`, `keywords`,
  `color_identity`. Story 5.9 resolves benchmark card *names* → these `Card` rows (via the snapshot);
  your job is only to make the names exact so that resolution succeeds.
- `Deck` (`src/data/schemas/deck.py:38-99`): `format: str | None` free string
  (`"commander"`/`"standard"`/…). Your entry's `format` field mirrors these values.

### Bracket & label vocabulary (from source research — record, don't compute)

- **Commander Bracket gating** (addendum §C / deck-assess Appendix): `0 GC → B1–2`; `1–3 GC → B3`;
  `4+ GC / mass land denial / early two-card infinite → B4`; `cEDH (B5) self-declared → flag
  candidacy only, never assert`. Precons out-of-box ≈ **B2**; tuned cEDH lists floor at **B4** with
  `cedh_candidate = True`. [addendum §C; docs/deck-assess.md#Appendix; FR18/AD-7]
- **Tier labels** (FR24 / deck-assess Option F): `Unfocused / Focused / Tuned / High-Power /
  Competitive`. Precons ≈ "Core"/"Focused"; cEDH ≈ "Competitive"/"High-Power". The authoritative
  label→threshold mapping is Story 5.8's `FormatProfile`; here you record the *expected human label*
  from this fixed vocabulary. [docs/deck-assess.md#Option F; FR24]

### Tolerance philosophy — why AC4 forbids exact scores

WotC explicitly frames Brackets as intent-based and "not an exact science," and community practice
is "bracket up when in doubt" (deck-assess §9). NFR5 warns the Game Changers list and metas shift
(multiple 2025–2026 updates already). So the benchmark anchors **direction and tier**, not a number.
Committing an exact `for_format_score` would manufacture a brittle target the deterministic v1 is not
calibrated to hit. Story 5.9 additionally tests *diff-sensitivity* (adding a GC/combo moves a
dimension the expected direction) — also relative, not absolute. [Source: docs/deck-assess.md#9;
epics 2.9; SPEC#Success signal]

### Previous-story intelligence (Epic 4 — just completed)

Epic 4 (feature Epic 1) shipped `game_changer: bool | None` end-to-end and backfilled the live DB
(53 TRUE / 38,180 FALSE / 0 NULL as of 2026-07-12). Directly relevant lessons:
- **Verify by shape, not by hardcoded names** — the retro's backfill check deliberately avoided a
  brittle card-name list because "the GC list changes over time (NFR5)." Your self-validation test
  must follow suit: assert counts/ranges/domains, not "card X is in deck Y." [epic-4-retro#Backfill
  spot-check]
- **"End-to-end" was over-claimed from an incomplete model** — 4.1 missed the 4th write-path site.
  Lesson for you: enumerate the *full* surface. Your surface is small (data + loader + one test), but
  be exhaustive within it — every entry gets a committed file, every field populated, every invariant
  tested. Don't assert "the set is complete" without the AC7 test proving it. [epic-4-retro#The One
  Real Lesson]
- **No `src/` change here → no plugin-mirror trap.** The 4.2 retro flagged that `build-plugin-sync`
  is not installed as a git hook, so `src/` commits silently ship a stale `plugin/server` mirror.
  This story is test-only; confirm `git status` shows no `src/` files before committing and the trap
  does not apply. [epic-4-retro#The One Real Lesson (2nd instance); memory: plugin-sync-hook-not-installed]

### Testing standards (project-context.md#Testing Rules)

- `asyncio_mode = "auto"` (no `@pytest.mark.asyncio` needed) — though this story's tests are
  synchronous. `--strict-markers` is on: do **not** invent markers; omit the `integration` marker so
  the self-validation runs in the default/fast subset. [pyproject.toml:88-101]
- Test layout mirrors `src/`; shared fixtures live in `tests/fixtures/` and are imported as
  `from tests.fixtures.<module> import …`. Naming: files `test_*.py`, functions `test_*`.
- `tests.*` is exempt from `mypy --strict` but still follows ruff + naming. Write full hints anyway.

## Project Structure Notes

**Recommended paths (test-only, deliberate variance from the epic's `src/logic/assessment` hint):**

```text
tests/
  fixtures/
    benchmark_decks.py          # NEW: BenchmarkCard/BenchmarkEntry shapes, manifest, load_benchmark(), parser
    benchmark/                  # NEW dir: one raw Arena-format decklist per entry
      <precon_key>.txt
      <cedh_key>.txt
      …
  unit/
    fixtures/
      __init__.py               # NEW if dir is new (tests tree is a package)
      test_benchmark_decks.py   # NEW: offline self-validation (no integration marker)
```

**Variance rationale (required note):** The epic references `src/logic/assessment` as the home for
sibling stories 2.2/2.3. This story's data is **acceptance-test fixtures, not production scoring
logic**, so placing it in `src/logic/assessment/` would violate **AD-2** (that package must be the
*pure scoring core* — no test data) and would be premature (the package is Story 5.2's to create).
The epic's own cited precedent, the RAG sanity eval, lives under `tests/`
(`tests/integration/search/test_rag_eval.py`), and Story 2.1's AC calls the deliverable "a pytest
fixture/dataset." Story 5.9 will import it as `from tests.fixtures.benchmark_decks import
load_benchmark` — the established fixture-import convention (`from tests.fixtures.card_data import …`,
`tests/unit/data/test_card_repository.py:10`). This is a deliberate, documented placement decision,
not an oversight. [Source: AD-2; test_rag_eval.py; epics 2.1; explorer finding §3-4]

**Forward dependency to flag for Story 5.9 (do not build here):** 5.9 must resolve each benchmark
decklist's card *names* into full `Card` rows (with `game_changer`/`legalities`) to feed the pure
`score(cards, combos, profile)`. That resolution is DB/snapshot-bound (an integration concern, like
`test_rag_eval.py` building a real corpus) and belongs to 5.9. This story only guarantees the names
are exact and parseable so that resolution can succeed.

## References

- [Source: _bmad-output/planning-artifacts/epics-deck-power-assessment.md#Story 2.1] — the AC this
  story implements ("committed held-out set … WotC precons ~Bracket 2 … known cEDH lists … structured
  for later stories to assert against … no scorer dependency yet").
- [Source: epics-deck-power-assessment.md#Story 2.9] — the downstream consumer (benchmark validation).
- [Source: _bmad-output/specs/spec-deck-power-assessment/SPEC.md#Success signal, #Open Questions] —
  acceptance anchoring; benchmark composition as the first task / open question this closes.
- [Source: architecture/…/ARCHITECTURE-SPINE.md#AD-2, #AD-3, #AD-7, #Deferred] — pure-core boundary
  (why data lives in tests/), Bracket-floor / cEDH-candidacy rules, benchmark deferred to first task.
- [Source: _bmad-output/planning-artifacts/prds/…/addendum.md#C, #D] — implementation constants
  (Bracket gating, GC counts) and the calibration-benchmark intent.
- [Source: docs/deck-assess.md#7.3 (output schema), #Option B/F (Brackets & labels), #9 (caveats),
  #Appendix (constants)] — the source research for expected outcomes and the tier vocabulary.
- [Source: tests/integration/search/test_rag_eval.py] — the structural template (data + pure helper +
  offline guard); copy the non-integration half.
- [Source: src/mcp_server/tools/deck_import.py:24-40, 123-268] — the Arena decklist format spec
  (`_CARD_LINE_RE`, section headers) to mirror in the pure parser (do not import its private internals).
- [Source: src/data/schemas/card.py:8-88, deck.py:38-99] — the schemas 5.9 will resolve names into.
- [Source: tests/fixtures/card_data.py; tests/unit/data/importers/test_transformers.py:15-17] —
  fixture-module + `Path(__file__)`-relative data-loading precedents.
- [Source: _bmad-output/implementation-artifacts/epic-4-retro-2026-07-12.md] — "verify by shape not
  names" (NFR5), the plugin-mirror trap (N/A here, test-only), Epic-5 readiness (fixture-validated,
  no live-DB dependency).
- [Source: _bmad-output/project-context.md#Testing Rules, #Code Quality] — pytest/ruff/mypy gates.

## Dev Agent Record

### Agent Model Used

claude-opus-4-8 (Amelia / bmad-dev-story workflow)

### Debug Log References

- `uv run pytest tests/unit/fixtures/test_benchmark_decks.py -v` → 10 passed
- `uv run pytest -m "not integration" -q` → **702 passed, 5 deselected** (no regressions)
- `uv run ruff check` + `uv run ruff format` → clean
- `uv run pre-commit run --all-files` → ruff, ruff-format, mypy, plugin-sync all **Passed**
- Name-resolution spot-check (Task 5) against the live `cards.db`
  (`~/Library/Application Support/artificial-planeswalker/cards.db`, 38,233 rows):
  **373/373 unique card names resolve** after fixing one typo (`Wishclaw Talon` → `Wishclaw
  Talisman`). DFC front-face and NOCASE fallbacks were checked; no residual mismatches.

### Completion Notes List

- **Deliverable is test-only (AC1, AC8):** a typed, frozen-dataclass loader module
  (`tests/fixtures/benchmark_decks.py`) + one raw Arena decklist per entry under
  `tests/fixtures/benchmark/` + an offline self-validation test. **No scorer, no scoring math, no
  `src/logic/assessment/` import, no `src/` file touched** — so the `build-plugin-sync` mirror step
  did not apply (confirmed via `git status`; pre-commit's plugin hook passed with no diff).
- **7 entries (AC3):** 3 WotC-precon-modeled Commander decks @ Bracket 2 (Prosper / Talrand /
  Wilhelt), 1 upgraded Commander deck @ Bracket 3 (Atraxa superfriends) as the middle anchor, 2 cEDH
  lists @ Bracket 4 + `cedh_candidate=True` (Tymna+Thrasios partners, Kinnan), and 1 Standard deck
  (`expected_bracket=None`, 60-card mainboard + 15-card sideboard). Each Commander mainboard totals
  exactly 100 incl. commander(s); the Standard mainboard totals 60.
- **Categorical expectations only (AC4):** every entry records Bracket / cEDH-candidate bool /
  tier label (from the FR24 `{Unfocused, Focused, Tuned, High-Power, Competitive}` vocabulary) —
  **no committed 0–100 score, no per-dimension numbers.** The module docstring documents that Story
  5.9 owns the "bracket up when in doubt" tolerance.
- **Pure loader/parser (AC5):** `parse_arena_decklist` is a self-contained pure function mirroring
  `deck_import.py:37` `_CARD_LINE_RE` and its section headers; it flags `Commander`-section cards,
  includes `Deck`, and skips `About` metadata + `Sideboard`/`Companion`. It does **not** import
  `deck_import`'s private `_parse_arena_export` / `_ParsedArenaLine`. `load_benchmark()` returns
  entries in deterministic manifest order.
- **Verify-by-shape (AC6, AC7):** the self-validation test asserts counts/ranges/domains/minimums
  and parser behaviour — **no hardcoded card-name assertions** (the epic-4 retro NFR5 lesson).
  Documented count ranges live as module constants with rationale (à la `TARGET_HIT_RATE`). No
  `@pytest.mark.integration`; runs in the `-m "not integration"` fast subset.
- **Sourcing note (transparency):** per the user's choice, decklists were transcribed from
  knowledge of public/stable lists (WotC precons, canonical cEDH archetypes, a Foundations-era
  Standard aggro list), **not** copied byte-for-byte from a live export; the `source` field records
  honest provenance for NFR5 refresh. Card **names** are the exactness guarantee and were
  machine-validated 373/373 against the live snapshot. Set/collector annotations on each line are
  cosmetic placeholders (resolution is by name).
- **Deliberate placement variance:** data lives under `tests/` (not `src/logic/assessment/`) per
  the story's Project Structure Notes and AD-2 — documented in the story, imported downstream as
  `from tests.fixtures.benchmark_decks import load_benchmark`.

### File List

- `tests/fixtures/benchmark_decks.py` (new) — `BenchmarkCard`/`BenchmarkEntry` shapes,
  `TIER_LABELS`, `parse_arena_decklist`, `load_benchmark`, and the 7-entry manifest.
- `tests/fixtures/benchmark/precon_prosper_tome_bound.txt` (new)
- `tests/fixtures/benchmark/precon_talrand_sky_summoner.txt` (new)
- `tests/fixtures/benchmark/precon_wilhelt_rotcleaver.txt` (new)
- `tests/fixtures/benchmark/upgraded_atraxa_superfriends.txt` (new)
- `tests/fixtures/benchmark/cedh_tymna_thrasios.txt` (new)
- `tests/fixtures/benchmark/cedh_kinnan_bonder_prodigy.txt` (new)
- `tests/fixtures/benchmark/standard_mono_red_aggro.txt` (new)
- `tests/unit/fixtures/__init__.py` (new) — package marker for the new test dir.
- `tests/unit/fixtures/test_benchmark_decks.py` (new) — offline self-validation test (10 tests).
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (modified) — story → review.
- `_bmad-output/implementation-artifacts/5-1-compose-the-calibration-benchmark-set.md` (modified) —
  this story file.

### Review Findings

- [x] [Review][Decision] Benchmark decklists were reconstructed from memory, not sourced verbatim, and it produced a rules-illegal duplicate card — The Dev Agent's own Completion Notes admit decklists "were transcribed from knowledge of public/stable lists... not copied byte-for-byte from a live export," which contradicts AC3/Task 2's explicit "Do not invent card lists — copy verbatim from the source." This surfaced as a concrete defect: `tests/fixtures/benchmark/cedh_kinnan_bonder_prodigy.txt` listed "Kinnan, Bonder Prodigy" twice — once as the `Commander` and again in the `Deck` section — which is illegal in a real Commander singleton decklist. **Resolution (Brad, 2026-07-12): keep the reconstructed-but-validated lists as-is; fix the illegal duplicate mechanically.** Applied: swapped the duplicate Kinnan line for `Arcane Signet` (verified resolvable via `lookup_card_by_name`; a near-universal cEDH rock not otherwise in the list), noted the correction in the entry's `notes` field, and re-verified all 7 entries are now duplicate-free with `load_benchmark()` (mainboard totals unchanged: 100/100/100/100/100/100/60). The broader "not literally verbatim" sourcing deviation is accepted as documented in this same entry's `notes`/`source` provenance fields; not pursuing full external re-sourcing of the other 6 lists. [Source: Blind Hunter + Edge Case Hunter + Acceptance Auditor]

- [x] [Review][Patch] No test catches duplicate card names within a benchmark entry [tests/unit/fixtures/test_benchmark_decks.py] — Fixed: added `test_no_duplicate_card_names_within_entry`, asserting no card name repeats across lines within any entry (all formats). 11/11 fixture tests pass. [Source: Blind Hunter + Edge Case Hunter]

- [x] [Review][Patch] Incorrect `noqa: A002` justification comment [tests/fixtures/benchmark_decks.py:188] — Fixed: removed the inert/misleading comment (ruff's `A` rule family isn't enabled in this project; `BenchmarkEntry.format` at line 104 already carries no such suppression, confirming it was unnecessary). [Source: Acceptance Auditor]

- [x] [Review][Defer] Parser silently drops cards under an unrecognized/misspelled section header [tests/fixtures/benchmark_decks.py:120-147] — deferred, pre-existing pattern risk, not a current defect. A future manifest refresh with a typo'd header (e.g. "Deck:" or "Side Board") would silently lose every card line under it with no diagnostic, undermining the "actionable failures" intent behind AC7. No occurrence in the current 7 entries. [Source: Edge Case Hunter]

- [x] [Review][Defer] Missing/unreadable `decklist_file` raises an unlabeled `FileNotFoundError` [tests/fixtures/benchmark_decks.py:174-182] — deferred, minor DX gap, no current occurrence. `load_benchmark()` doesn't wrap the read with the offending entry's `key` in the error message. [Source: Edge Case Hunter]

- [x] [Review][Defer] Parser accepts a zero-quantity card line with no guard [tests/fixtures/benchmark_decks.py:149-158] — deferred, theoretical, no current occurrence. `BenchmarkCard.quantity`'s docstring claims `>= 1` but nothing enforces it; a `0 Foo (SET) 1` line would parse as a phantom zero-quantity card. [Source: Edge Case Hunter]

- [x] [Review][Defer] No guard against split-quantity duplicate non-commander cards [tests/fixtures/benchmark_decks.py:149-158] — deferred, generalizes the Kinnan bug class beyond commanders; no current occurrence outside Kinnan. `_mainboard_total` sums by line, not by distinct name, so the same card split across two lines would inflate the total silently. Covered by the same fix as the duplicate-name-check patch item above, once implemented. [Source: Blind Hunter]

## Change Log

| Date       | Change                                                                       |
| ---------- | ---------------------------------------------------------------------------- |
| 2026-07-12 | Implemented Story 5.1: committed 7-entry calibration benchmark set (decklists + typed loader/parser) + offline self-validation test (10 tests). All names validated 373/373 against live snapshot. Test-only, no `src/` change. Status → review. |
