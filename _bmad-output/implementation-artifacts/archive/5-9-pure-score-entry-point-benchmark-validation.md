---
baseline_commit: a42c537 # "test: pin _to_score cross-module parity (Story 5.8 review -> done)" (tree clean at story creation)
---

# Story 5.9: Pure `score()` entry point + benchmark validation

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

> **Sprint/feature numbering:** this is sprint key
> `5-9-pure-score-entry-point-benchmark-validation` (`epic-5`), which is
> **feature Epic 2, Story 2.9** in `_bmad-output/planning-artifacts/epics-deck-power-assessment.md`.
> Sprint Epic 5 = feature Epic 2 "Deterministic scoring core". This is the LAST Epic-5 story —
> it closes the pure core and is its acceptance gate (NFR6/NFR8).

## Story

As the scorer's author,
I want one pure entry point validated against the benchmark,
so that the core is proven deterministic and correctly calibrated.

## Context & why this story exists

Stories 5.2–5.8 shipped every stage of the pure core as single-stage emitters; **nothing
composes them end-to-end yet**. This story ships the composition (`score()`), the object it
returns (`CoreAssessment`), and — critically — the story where the provisional v1 numbers that
5.3–5.8 deliberately deferred finally meet reality: the Story 5.1 **calibration benchmark**
(extended with ≥3 Standard anchors per the 2026-07-12 amendment, proposal P5) and the
**monotonicity property suite**. Four things hang off it:

- **The composition contract everyone already wrote down** — `aggregate.py:22-27` documents it
  verbatim: 5.9's `score()` composes `match_combos` → `dimension_vector` / `bracket_floor` →
  `aggregate_score` + `tier_label`, and under `heuristic_only` the composer never consults
  `bracket_floor`. The fork lives in what is COMPOSED, never inside any module.
- **NFR6 acceptance gate** — the benchmark (5.1's 7 entries + this story's Standard anchors)
  is run for the first time against real scores: precons ~B2, cEDH lists flag as candidates,
  Standard anchors land in their expected tier bands. Weights/thresholds are hand-tuned
  (documented, versioned) until it passes (NFR8).
- **PRD §6 metric 4 properties** — the literal "adding X" monotonicity properties that 5.7's
  SWAP-based tests explicitly deferred here: a strictly-power-positive edit never moves the
  affected output the wrong way.
- **Epic 7 contract** — 7.2/7.3 orchestrate deck-load → resolve → `score()` → serialize.
  `CoreAssessment` is the exact surface they consume; what you name here is what they emit.

Five review-defers from 5.7/5.8 are logged against this story (deferred-work.md 2026-07-14):
the `win_turn_band` guard, the aggregate profile-shape/weight-validity guards, the
`tier_thresholds`=100 degenerate-band domain, the `card_advantage` 98 structural cap, and the
`sixty_card` scale-comparability item (absorbed by per-format `tier_thresholds` tuning).

## Acceptance Criteria

1. **One new pure module owns the entry point.** Given the one-module-per-story house pattern
   (5.3 `classifiers` … 5.8 `aggregate`), when the story is done, then
   `src/logic/assessment/scorer.py` exists and contains `score()` and `CoreAssessment`; it is
   pure (no network/DB/clock/random/logging — AD-2) and imports only stdlib, sibling
   `src.logic.assessment` modules (`profiles`, `dimensions`, `aggregate`, `combos`,
   `classifiers`, `consistency`, `mana_base` as needed), and `src.data.schemas` **types only**
   (`Card`/`DeckCard`/`ComboRecord` — data shapes, no I/O); it must NOT import
   `src.data.repositories`, `src.data.database`, `src/search`, `src/mcp_server`,
   `src/logic/mana_curve`, or `src/logic/synergy`. All new public names are exported
   additively from `src/logic/assessment/__init__.py` (`__all__` kept bytewise-sorted).
   [epics 2.9; AD-2; project-context#Framework rules]

2. **The signature is AD-2's, not the epic shorthand.** Given AD-2
   (`score(cards, commanders, combos, profile) -> assessment`; epic 2.9's
   `score(cards, combos, profile)` is shorthand — the matcher needs resolved commanders),
   when defined, then
   `score(deck_cards: Sequence[DeckCard], *, commanders: Sequence[str], variants: Sequence[ComboRecord], profile: FormatProfile) -> CoreAssessment`
   with everything after `deck_cards` keyword-only (house style). `commanders` is the
   already-resolved name list (AD-13 — the core never resolves or queries); `variants` are
   **unmatched** snapshot records (`bucket=None`) — matching happens inside via
   `match_combos` (AD-9). The composition, exactly once each: `match_combos` → matched;
   `dimension_vector(deck_cards, matched_combos=…, profile=…)`;
   `aggregate_score(vector, profile=…)`; `tier_label(score, profile=…)`. [epics 2.9; AD-2;
   AD-9; aggregate.py:22-27]

3. **`CoreAssessment`: frozen, fixed-shape, format-blind keys.** Given AD-7's fixed-shape
   discipline starts in the core, when defined in `scorer.py`, then
   `@dataclass(frozen=True, slots=True) CoreAssessment` carries exactly:
   - `vector: DimensionVector` — all seven dimensions, any format;
   - `for_format_score: int` — the 0–100 aggregate (no 1–10 anywhere, FR19);
   - `tier: TierLabel` — never a bare number (FR24);
   - `bracket_floor: int | None` — populated under `rubric == "brackets"`, `None` under
     `heuristic_only` (the composer **never calls** `bracket_floor()` on the heuristic path);
   - `cedh_candidate: bool` — from `BracketFloorSignal` under `brackets`; `False` under
     `heuristic_only` (candidacy only, never Bracket 5 — FR18);
   - `game_changers: GameChangerSignal` — computed for BOTH rubrics; `card_names` feeds
     `flags.game_changers`, `unknown_count` is the edge's AD-4
     `game_changer_data_unavailable` input (core emits the VALUE, never the token/level);
   - `combos: tuple[ComboRecord, ...]` — the matched records (bucket set, sorted by
     `spellbook_id`, as `match_combos` returns them);
   - `structural_gaps: tuple[str, ...]` — `consistency.structural_gaps(...,
     formula=profile.karsten_formula)`, already bytewise-sorted (FR9);
   - `mass_land_denial: bool` and `extra_turn_chains: bool` — **one decide-once semantic for
     both formats**: MLD = any mass-land-denial card present
     (`detect_mass_land_denial(...).triggered`); extra-turn chain = quantity-aware extra-turn
     count `>= EXTRA_TURN_CHAIN_MIN` (the same rule `bracket_floor` gates on). Computed via
     the format-agnostic classifiers path for both rubrics; a **commander-parity test** pins
     that these equal `BracketFloorSignal.mass_land_denial` / `.extra_turn_chain` on the same
     deck.
   No confidence level, no `reasons[]`, no summary, no `data_vintage`, no serialization —
   those are Epic 7 edge policy (AD-6/AD-7/AD-8). Every field always present (Standard holds
   `bracket_floor=None` + `False` booleans — no format-conditional shape). [epics 2.9; FR23
   values-half; AD-4; AD-7; sprint-change P6]

4. **Determinism & honesty, pinned.** Given NFR1's core half, when tested, then identical
   `(deck_cards, commanders, variants, profile)` inputs yield an **equal** `CoreAssessment`
   (frozen dataclasses + tuple fields make `==` sufficient); inputs are not mutated; no
   `set`/dict-iteration ordering reaches any output; and the module docstring claims exactly
   what the tests pin — composed public functions re-derive `classify_deck`/signals
   internally, so `score()` must NOT claim single-classification (the 5.7 docstring-overclaim
   lesson: sanctioned internal re-derivations exist and are named, not hidden). A rubric-swap
   test (`dataclasses.replace(profile, rubric=…)`) pins that `vector`, `for_format_score`,
   `tier`, and all format-agnostic fields are identical — only `bracket_floor`/
   `cedh_candidate` change between rubrics. [epics 2.9; NFR1; AD-8 core side; 5.7 lesson]

5. **The benchmark grows ≥3 Standard anchors — additively.** Given the 2026-07-12 amendment
   (P5) and 5.1's fixture contract, when extended, then `tests/fixtures/benchmark/` gains
   three new committed Arena-format decklists with manifest rows appended to `_MANIFEST` in
   `tests/fixtures/benchmark_decks.py`: a **current competitive Standard archetype**
   (recommended `expected_tier_label="High-Power"`), a **coherent-but-untuned deck**
   (`"Focused"`), and a **jank pile** (`"Unfocused"`) — with the existing
   `standard_mono_red_aggro` (`"Tuned"`) untouched as a fourth mid anchor, giving four
   distinct Standard bands. Each: `format="standard"`, `expected_bracket=None`,
   `expected_cedh_candidate=False`, exactly 60 mainboard cards, **exact resolvable oracle
   names** (DFCs need the full stored `"Front // Back"` name — `find_by_name_exact` matches
   the whole name; set/collector annotations stay cosmetic), reconstructed from stable public
   archetypes per the accepted 5.1 precedent, `source`/`notes` recorded. The existing 7
   entries are NOT modified; `tests/unit/fixtures/test_benchmark_decks.py` is extended
   additively (any entry-count pin amended to the new total is sanctioned). [epics 2.9;
   sprint-change P5; 5-1 fixture contract; NFR6]

6. **Benchmark validation runs against the real local snapshot — the deferred 5.1 gate.**
   Given 5.1 committed **names only** (resolution explicitly deferred to this story), when
   `tests/integration/logic/test_assessment_benchmark.py` (new dir + `__init__.py`,
   module-level `pytestmark = pytest.mark.integration`) runs, then:
   - a module/session-scoped fixture opens the central DB via
     `create_engine()` (default URL) + `create_session_factory`, guards with
     `is_database_initialized` → `pytest.skip("cards.db not initialized — run
     initialize_database")` when absent/uninitialized (fresh checkout/CI has no DB; the
     RAG-eval precedent: integration tests may depend on operator-local data, but must skip
     LOUDLY, never fail cryptically);
   - every benchmark card name resolves via
     `CardRepository.find_by_name_exact(name)` — **unfiltered** (a format filter hides
     non-legal cards as not-found); ANY unresolved name is a hard
     `pytest.fail` naming the entry + missing names (5.1 guaranteed resolvability — a miss is
     a regression, not a skip);
   - if any resolved card has `game_changer is None`, skip citing the backfill re-import
     (AD-4 window; the Atraxa B3 expectation needs real GC data);
   - deck inputs: `make_deck_card(card, quantity)` rows for ALL parsed cards (commander rows
     included in `deck_cards`), `commanders` = the `is_commander` names — documented as the
     benchmark harness's decide-once convention;
   - **combo variants are hand-built fixtures in the test module** (Epic 6's snapshot does
     not exist yet — the epic overview mandates fixture-validated, no live dependency): for
     each cEDH entry, `make_combo_record(...)` variants whose `cards` are all present in that
     committed decklist, `produces` contains `"infinite"`, and piece MVs are cheap enough
     that `earliest_turn_estimate <= CEDH_COMBO_TURN_MAX` (4) — e.g. Kinnan, Bonder Prodigy +
     Basalt Monolith for the Kinnan list; verify the actual pair against the committed `.txt`
     before writing it. Non-cEDH and Standard entries pass `variants=()` — which also proves
     empty combo data scores without crashing (NFR3 core side). [epics 2.9; 5-1 story
     §deferred; AD-4; AD-13; epic-2 overview "combo fixtures"]

7. **Benchmark assertions with the decide-once tolerance policy.** Given 5.1's documented
   tolerance contract, when asserted (every assertion names the entry key + observed value),
   then per entry through the REAL `score()`:
   - precons (`expected_bracket=2`): `bracket_floor in {2, 3}` (`[expected, expected+1]`);
   - `upgraded_atraxa_superfriends` (3): `bracket_floor in {3, 4}`;
   - cEDH entries (4): `bracket_floor == 4` (== `BRACKET_FLOOR_MAX`; Bracket 5 is never
     asserted and cannot be emitted) AND `cedh_candidate is True`;
   - Commander `expected_tier_label`: within ±1 band index of expected (informative
     expectation; tier cuts are this story's tuning knob);
   - Standard anchors: `bracket_floor is None`, `cedh_candidate is False`, and tier ==
     `expected_tier_label` **exactly** (the FR20 acceptance signal — thresholds/weights are
     tuned per-format until this holds);
   - two consecutive `score()` calls per entry return equal objects (determinism on real
     data). [epics 2.9; NFR6; 5-1 tolerance notes; FR20]

8. **Monotonicity properties + diff-sensitivity — offline, literal edits, through
   `score()`.** Given PRD §6 metric 4 (the properties 5.7's swap tests deferred), when
   `tests/unit/logic/test_assessment_scorer.py` runs (no marker, no DB — synthetic cards via
   `tests/fixtures/assessment.py` builders), then over ≥2 distinct synthetic base decks:
   - **GC-add:** appending a `game_changer=True` card never lowers `bracket_floor`
     (commander profile);
   - **tutor-add:** appending a tutor-tagged card never lowers `vector.consistency` (both
     profiles);
   - **interaction-cut:** removing ALL interaction-tagged cards never raises
     `vector.interaction` (both profiles);
   - **diff-sensitivity:** with a two-piece variant where the deck holds piece A only
     (`almost_included`), adding piece B (`included`) strictly raises
     `vector.combo_potential` and never lowers `bracket_floor`;
   properties are deterministic parametrized loops — **no `hypothesis`, no new dependency**.
   If a property fails under current mappings, that is a calibration finding: tune the
   mapping/weights until it holds; never weaken a literal-add property back to a swap.
   [epics 2.9; PRD §6 metric 4; sprint-change P5; 5.7 swap-test rationale]

9. **Tuning is versioned; the five deferred items are dispositioned.** Given AD-3's bump rule
   and this story's ownership of calibration, when tuning lands, then:
   - ANY profile value change (weights, `tier_thresholds`, `win_turn_band`) bumps that
     profile's `format_profile_version` (v3 → v4) in the same edit, amending the 5.8
     version-pin test (`test_versions_bumped_for_tier_thresholds_addition`) — the ONE
     sanctioned non-additive test edit; a change to a **shared** `dimensions.py` tuning
     constant (keyed by `KarstenFormula` or global) bumps BOTH versions — the version string
     identifies scoring behavior on the AD-8 diff surface, not just profile literals;
   - if the benchmark passes with NO value changes, versions stay v3 and that outcome is
     recorded explicitly;
   - every changed value gets a comment + Completion Notes rationale naming the benchmark
     evidence (NFR8: documented, hand-tuned, adjustable);
   - the five logged defers are each resolved or explicitly re-deferred with a reason:
     (a) `dimensions._speed_score` malformed `win_turn_band` guard, (b) `aggregate`
     profile-shape/weight-validity guards (4-tuple ascending; finite non-negative weights),
     (c) `tier_thresholds` cut==100 degenerate-band domain, (d) `card_advantage` 98
     structural cap (keep-or-change, documented), (e) `sixty_card` scale comparability —
     closed by per-format threshold anchoring against the Standard anchors, stated in the
     profile comments. Guards a–c are cheap defense-in-depth for THIS story's tuning
     workflow (the 5.6 lesson: malformed input must not masquerade as signal); if skipped,
     re-log in deferred-work.md. [AD-3; NFR8; deferred-work.md 2026-07-14]

10. **Scope guard — compose and calibrate, nothing more.** Given the story split, when
    reviewed, then this story ships **no** serialization / `AssessDeckPowerResult` /
    `CompareDeckPowerResult` / `data_vintage` / `summary` (Epic 7, AD-7/AD-8), no confidence
    level-assignment, `reasons[]` assembly, or degradation ladder (Epic 7 / feature 4.2 —
    `CoreAssessment` carries values like `unknown_count`, never tokens/levels), no commander
    RESOLUTION (edge, AD-13 — `score()` consumes resolved names), no combo-snapshot
    repository/import script/`DeckCardModel.commander` (Epic 6), no MCP tool registration,
    and no edits to `src/data/**` (schemas included), `src/mcp_server/**`, `scripts/`,
    `src/search/**`, `classifiers.py`, `mana_base.py`, `consistency.py`, or `combos.py`
    logic. The ONLY modified existing sources are: `src/logic/assessment/__init__.py`
    (additive exports), `profiles.py` (tuned values + bumps, AC9), `dimensions.py` /
    `aggregate.py` (ONLY tuning-constant values, the optional AC9 guards, and
    docstring-accuracy edits), and the sanctioned test/fixture files (AC5–AC8). If a
    function needs a repository, a session, the clock, or an HTTP client — wrong story.
    [epics 2.9 vs Epic 6/7 split; AD-2]

11. **Offline unit tests prove the composition.** Given the project's testing rules, when
    `tests/unit/logic/test_assessment_scorer.py` runs, it verifies at minimum, beyond AC8:
    - **composition equalities:** `score(...)` fields equal the composed calls run manually
      on the same inputs — `vector == dimension_vector(...)`, `for_format_score ==
      aggregate_score(vector, profile=…)`, `tier == tier_label(for_format_score, …)`,
      `combos == match_combos(...)` (same matched records, same order);
    - **rubric fork:** commander profile → `bracket_floor in {2,3,4}` + cedh from the
      signal; `heuristic_only` → `bracket_floor is None` and `cedh_candidate is False`;
      the AC4 rubric-swap invariance for everything else;
    - **commander parity (AC3):** `mass_land_denial`/`extra_turn_chains` equal the
      `BracketFloorSignal` fields on decks WITH and WITHOUT triggers;
    - **fixed shape:** all `CoreAssessment` fields present under both profiles (e.g. via
      `dataclasses.fields` totality);
    - **empty inputs:** `variants=()`, `commanders=()`, and an empty deck all score without
      raising (zero-safe like every 5.3–5.8 primitive);
    - **determinism + non-mutation** (AC4);
    - assertions carry failure messages naming the field/property or the claim is dropped
      (the 5.5 lesson). Runs green under `uv run pytest -m "not integration"` (baseline at
      story creation: **1067 passed, 5 deselected**, clean `a42c537` tree).
    [project-context#Testing Rules; 5-5/5-7/5-8 lessons]

12. **Quality gates pass — including the `src/`-touch plugin mirror.** Given this story
    edits files under `src/`, when committed, then `mypy --strict` passes (full hints,
    Google docstrings on module + every public name), `ruff check` + `ruff format` are
    clean, and the regenerated `plugin/` mirror is staged in the same commit (the pre-commit
    hook is installed in this checkout — verify the
    `plugin/server/src/logic/assessment/` mirror diffs for the new `scorer.py` AND every
    modified core file are staged; never `--no-verify`). [project-context#Code Quality;
    epic-4 retro]

## Tasks / Subtasks

- [x] **Task 0 — Confirm clean baseline** (AC: —)
  - [x] Tree is CLEAN at `a42c537` at story creation. Verify `git status` clean and
        `uv run pytest -m "not integration"` reports **1067 passed, 5 deselected** before
        writing any 5.9 code.
- [x] **Task 1 — `scorer.py`: `CoreAssessment` + `score()`** (AC: 1, 2, 3, 4)
  - [x] Module docstring: the composition contract (matcher → vector/floor → aggregate +
        label), the rubric fork (never calls `bracket_floor` under `heuristic_only`; edge
        emits `bracket: null`), the decide-once trigger semantics, the honest
        internal-re-derivation note (no single-classification claim), Epic-7 consumer map.
  - [x] `CoreAssessment` frozen slotted dataclass with the exact AC3 field set.
  - [x] `score()` per AC2; format-agnostic values (GC signal, structural gaps, triggers,
        matched combos) computed for both rubrics; floor/cedh only under `brackets`.
- [x] **Task 2 — Package exports** (AC: 1)
  - [x] Extend `src/logic/assessment/__init__.py` `__all__` additively (bytewise-sorted;
        `CoreAssessment`, `score`).
- [x] **Task 3 — Offline scorer tests** (AC: 4, 8, 11)
  - [x] `tests/unit/logic/test_assessment_scorer.py`: composition equalities, rubric fork +
        swap invariance, commander parity, fixed shape, empty inputs, determinism,
        monotonicity properties (GC-add / tutor-add / interaction-cut), diff-sensitivity
        (almost_included → included). Reuse/extend `tests/fixtures/assessment.py` builders
        additively (the sanctioned home for card-shaped helpers) or mirror 5.7's local
        tagged-card builders.
- [x] **Task 4 — Standard anchors** (AC: 5)
  - [x] Three new `tests/fixtures/benchmark/*.txt` decklists (competitive / untuned / jank),
        60 mainboard cards each, exact oracle names (full `"A // B"` for DFCs).
  - [x] Append `_MANIFEST` rows (`expected_bracket=None`, labels per AC5, source/notes).
  - [x] Extend `tests/unit/fixtures/test_benchmark_decks.py` additively (amend any count pin).
- [x] **Task 5 — Benchmark integration harness** (AC: 6, 7)
  - [x] `tests/integration/logic/__init__.py` + `test_assessment_benchmark.py`
        (`pytestmark = pytest.mark.integration`).
  - [x] Central-DB fixture (`create_engine()` default → `create_session_factory` →
        `is_database_initialized` skip guard); unfiltered `find_by_name_exact` resolution;
        hard-fail on unresolved names; skip on `game_changer is None`.
  - [x] Hand-built cEDH combo-variant fixtures verified against the committed decklists;
        `variants=()` everywhere else.
  - [x] AC7 assertions with entry-key-naming failure messages + per-entry determinism check.
- [x] **Task 6 — Calibration loop** (AC: 7, 9)
  - [x] Run the benchmark locally (`uv run pytest tests/integration/logic/ -q`); iterate on
        profile weights / `tier_thresholds` / `dimensions.py` tuning constants until AC7 and
        AC8 both hold; bump versions per the AC9 rule; document every change (comment +
        Completion Notes + benchmark evidence). Amend the 5.8 version-pin test if bumped.
- [x] **Task 7 — Deferred-item disposition** (AC: 9)
  - [x] Add (or explicitly re-defer with reason) the `win_turn_band` guard, the aggregate
        shape/weight guards, and the `tier_thresholds` (0,100) domain tightening; disposition
        the `card_advantage` 98 cap; state the scale-comparability closure in profile
        comments. Update `deferred-work.md` accordingly.
- [x] **Task 8 — Quality gates + plugin mirror** (AC: 11, 12)
  - [x] `uv run ruff check . --fix && uv run ruff format .`
  - [x] `uv run mypy src/` (strict) clean.
  - [x] `uv run pytest -m "not integration"` green; benchmark module green-or-skipped
        locally with the DB present (run it — this story IS the gate).
  - [x] Commit with the regenerated `plugin/` mirror staged. Never `--no-verify`.

## Dev Notes

### What this story is — and is NOT

- **IS:** one new pure module `src/logic/assessment/scorer.py` (`score`, `CoreAssessment`);
  three Standard anchor decklists + manifest rows; the benchmark integration harness (the
  deferred 5.1 resolution gate); the literal-add monotonicity/diff-sensitivity suite; the
  calibration pass over profile values + dimension tuning constants with version bumps; the
  five deferred-item dispositions.
- **IS NOT:** the MCP tools, result Pydantic models, serialization, summary, `data_vintage`
  (Epic 7); confidence level assignment / `reasons[]` / degradation ladder (Epic 7 / feature
  4.2 — this core emits `GameChangerSignal.unknown_count`, the edge turns it into
  `game_changer_data_unavailable`); commander resolution / `DeckCardModel.commander` /
  Spellbook import / snapshot repo (Epic 6); any new logic in the 5.3–5.6 signal modules.

### Baseline note (story-creation snapshot, 2026-07-14)

Working tree **clean** at `a42c537` (the 5.8 review-patch commit). Fast-suite baseline
**1067 passed, 5 deselected** measured on this tree. Pre-commit hook (ruff + mypy + plugin
rebuild) IS installed. The live central `cards.db` is imported AND `game_changer`-backfilled
(epic-4 retro: 53 TRUE / 38 180 FALSE / 0 NULL) — the benchmark harness will not skip on
Brad's machine.

### The inventory you compose (all shipped — reinvent nothing)

| Need | Use | Signature (verified at story creation) |
| --- | --- | --- |
| combo matching | `combos.match_combos` | `(deck_cards, *, commanders: Sequence[str], variants: Sequence[ComboRecord]) -> tuple[ComboRecord, ...]` — buckets assigned, sorted by `spellbook_id` |
| 7-dim vector | `dimensions.dimension_vector` | `(deck_cards, *, matched_combos, profile) -> DimensionVector` |
| floor + cedh | `dimensions.bracket_floor` | `(deck_cards, *, matched_combos) -> BracketFloorSignal` — NO profile param; fields: `floor`, `game_changers`, `mass_land_denial(+names)`, `extra_turn_chain(+names)`, `early_two_card_infinite(+ids)`, `cedh_candidate` |
| GC names + unknown count | `dimensions.game_changer_signal` | `(deck_cards) -> GameChangerSignal(known_count, card_names, unknown_count)` — `is True`/`is None`, never coalesced (AD-4) |
| aggregate + label | `aggregate.aggregate_score` / `aggregate.tier_label` | `(vector, *, profile) -> int` / `(score, *, profile) -> TierLabel` |
| structural gaps | `consistency.structural_gaps` | `(deck_cards, *, formula: KarstenFormula) -> tuple[str, ...]` bytewise-sorted |
| MLD / extra-turn | `classifiers.detect_mass_land_denial` / `classify_deck` + `EXTRA_TURN`, `dimensions.EXTRA_TURN_CHAIN_MIN` | presence flag / quantity-aware `CategoryCount.count >= 2` chain rule |
| profiles | `profiles.COMMANDER_PROFILE` / `STANDARD_PROFILE` | v3; weights sum 1.0; `tier_thresholds=(20,40,60,80)` both (the honest zero-information prior YOU now anchor per format) |
| benchmark | `tests.fixtures.benchmark_decks.load_benchmark()` | `() -> tuple[BenchmarkEntry, ...]`; `BenchmarkCard(name, quantity, is_commander)`; expected outcomes categorical only |
| card factories | `tests.fixtures.assessment` | `make_card(**o) -> Card` (GC defaults `None`), `make_deck_card(card, quantity=1, sideboard=False)`, `make_combo_record(**o)` |
| DB access (tests only) | `src.data.database` | `create_engine()` (defaults to central DB URL), `create_session_factory(engine)`, `is_database_initialized(session)`; `CardRepository.find_by_name_exact(name)` → `Card \| None`, matches name OR printed_name case-insensitively |

`score()`'s body is ~15 lines of composition. Resist decorating it.

### Load-bearing decisions (read before writing code)

- **AD-2's four-input signature wins over the epic shorthand.** Epic 2.9 writes
  `score(cards, combos, profile)`; AD-2 and the spine mermaid write
  `scorer(cards, commanders, combos, profile)`. The matcher's `commander_required` gate needs
  the resolved commander names, so the four-input form is the only one that composes. Name
  the parameter `variants` (matching `match_combos`) to make "unmatched in, matched out"
  unmissable.
- **The rubric fork = what is composed.** `aggregate.py`'s documented contract: under
  `heuristic_only` the composer never consults `bracket_floor`. So the ONLY `profile.rubric`
  branch in this module decides whether `bracket_floor()` is called at all —
  `bracket_floor=None` / `cedh_candidate=False` otherwise. No math branches on rubric
  (5.8 pinned `aggregate_score`/`tier_label` rubric-blind; this story's swap test extends
  that to the whole composition minus floor/cedh).
- **Trigger booleans: one semantic, computed format-agnostically, parity-pinned.** AD-7's
  flags block carries `mass_land_denial`/`extra_turn_chains` for every format, but
  `BracketFloorSignal` only exists on the brackets path. Compute both booleans from the
  classifiers path for BOTH rubrics (MLD presence; extra-turn quantity-aware count `>=
  EXTRA_TURN_CHAIN_MIN`) and pin commander-parity with the signal's fields by test. A
  Standard deck running Armageddon factually HAS mass land denial — the flag is
  explainability, not a bracket verdict; `bracket_floor=None` is what says "no bracket".
- **`GameChangerSignal` rides whole.** The edge needs `card_names` (flags) and
  `unknown_count` (confidence input) — carry the signal object rather than flattening, so
  Epic 7 reads one field. Under `brackets`, `bracket_floor()` re-derives its own GC signal
  internally — sanctioned re-derivation; say so in the docstring instead of claiming
  compute-once (the 5.7 overclaim lesson).
- **Benchmark resolution is integration-bound by design.** 5.1 committed exact names only
  and explicitly deferred "resolve against the local snapshot" to 5.9. A fresh checkout has
  no `cards.db` (build prerequisite, never committed — the `card_vec` precedent), so the
  harness SKIPS loudly when uninitialized and FAILS loudly on an unresolved name (that's a
  fixture regression, not an environment gap). Resolution is unfiltered
  `find_by_name_exact` — a format filter would hide non-legal printings as not-found.
- **cEDH candidacy needs combo fixtures, not the snapshot.** `cedh_candidate` requires
  `floor == 4` AND a fast included infinite (`earliest_turn_estimate <=
  CEDH_COMBO_TURN_MAX=4`) AND `tutors >= CEDH_TUTOR_MIN=4` AND `avg MV <=
  CEDH_AVG_MV_MAX=2.5`. With `variants=()` no infinite exists and candidacy is
  unreachable — so the two cEDH entries MUST get hand-built `ComboRecord` fixtures whose
  pieces are actually in the committed lists, whose `produces` contains `"infinite"`
  (`combo_type` keys on that substring), and whose piece MVs are cheap (total ≤ 10, max ≤ 4
  keeps `earliest_turn_estimate <= 4`). Check the `.txt` files first; add the variant to
  match the list, never the other way around.
- **Tolerances are 5.1's documented contract, restated once in code.** Precons
  `[expected, expected+1]`; cEDH floor `== 4` (`BRACKET_FLOOR_MAX` — the core cannot emit 5
  and candidacy is never an assertion of Bracket 5); Standard anchors exact-label (that IS
  the FR20 acceptance signal); Commander labels ±1 band (informative). Encode the policy in
  ONE helper with a docstring citing 5.1, so 5.9's re-cuts can't silently drift it.
- **Version bumps track behavior, not just profile literals.** The 5.7 deviation put
  per-dimension mapping constants in `dimensions.py` (private, `KarstenFormula`-keyed)
  rather than on the profile. If you tune one, the profile version STILL bumps (both
  formats for a shared constant) — `format_profile_version` is the AD-8 diff surface's name
  for "the scoring behavior that produced this"; a silent constant change invalidates every
  cached diff exactly like a silent weight change.
- **Properties are literal adds now — that was the point of deferring them.** 5.7 used
  SWAP-based monotone tests (deck size constant) because literal adds shift hypergeometric
  denominators and avgMV. This story owns making the literal versions hold: if
  tutor-add lowers consistency under current mappings, tune the mapping (that's calibration
  evidence, not a test bug). Never regress the property to a swap to make it pass.
- **No new dependencies.** Property tests are deterministic parametrized loops — no
  `hypothesis`. The harness uses the existing async engine/repository surface — no new
  drivers. Nothing in `pyproject.toml` changes.
- **`_to_score` third copy?** `score()` composes already-scored integers; it maps no floats
  and needs NO `_to_score`. If calibration work ever creates a third copy, the 5.8 docstring
  cue says hoisting to one public home is this story's call — otherwise leave the two
  documented copies alone.
- **Determinism traps:** every `CoreAssessment` collection field is a tuple that arrives
  pre-sorted from its producer (`match_combos` by `spellbook_id`, `structural_gaps`
  bytewise, `GameChangerSignal.card_names` sorted). Do not re-sort, do not pass through a
  `set`, do not iterate a dict of your own making.

### Previous-story intelligence (5.8, just completed)

- **Review outcome:** all 9 ACs satisfied, zero violations; one review patch (the
  `_to_score` cross-module parity test, committed `a42c537`) and two defers INTO this story
  (aggregate guards; threshold-100 domain). Lesson applied here: when a docstring says
  "pinned by tests", the pin must exist — every parity/policy claim in `scorer.py`'s
  docstring needs a named test.
- **5.7 lessons in force:** docstrings must not overclaim (say "composed functions
  re-derive signals internally", not "computes each signal once"); swap-vs-add test
  distinction is deliberate — this story graduates to adds; `BASELINE_BRACKET_FLOOR = 2` is
  what makes precon expectations satisfiable (floor can never read 1).
- **Standing lessons:** verify-by-shape for provisional values, exact pins only for closed
  vocabulary/derived math (5.1→5.8); assert messages naming the surface or drop the claim
  (5.5); pinned values and prose move together — amend the story file if you correct a
  number mid-implementation (5.5); the pinned-version test moves WITH the bump in the same
  edit (5.8 amended v2→v3; you may amend v3→v4); cheap defense-in-depth guards get accepted
  where malformed input could masquerade as signal (5.6 — the AC9 guards are exactly this).
- **5.1 lessons (the fixture you now consume):** decklists were reconstructed-then-validated
  (Brad accepted); the Kinnan list needed a singleton fix — so VERIFY every new Standard
  list sums to 60 and repeats nothing illegally; the offline self-test is shape-only, the
  resolution gate is yours.

### Testing standards

- pytest config in `pyproject.toml`: `asyncio_mode="auto"` (write `async def test_...`
  bare — the benchmark harness needs async repo calls), `--strict-markers`, `--tb=short`.
- Offline scorer tests: flat placement `tests/unit/logic/test_assessment_scorer.py` beside
  the seven existing assessment modules (the subdir move stays deferred; if you do it, move
  all eight in one commit).
- Integration harness: `tests/integration/logic/` is NEW — add `__init__.py` (match the
  sibling `tests/integration/data/` layout) and module-level
  `pytestmark = pytest.mark.integration`. Integration tests are part of the active local
  suite (`-m "not integration"` merely scopes the fast subset — the RAG-eval precedent);
  CI runs the fast subset only, so the skip guard is about fresh checkouts, not CI noise.
- Fixture etiquette: card-shaped helpers belong in `tests/fixtures/assessment.py` (extend
  additively) — do NOT import another test module's private builders.
- `tests.*` is mypy-exempt but write full hints anyway.

## Project Structure Notes

**New/changed files:**

```text
src/
  logic/
    assessment/
      scorer.py             # NEW: CoreAssessment, score() — the composition + rubric fork
      __init__.py           # MODIFIED: additive re-exports (CoreAssessment, score), bytewise-sorted
      profiles.py           # MODIFIED-IF-TUNED: weight/threshold values + v3->v4 bumps (AC9)
      dimensions.py         # MODIFIED-IF-TUNED: private tuning constants; optional win_turn_band guard
      aggregate.py          # MODIFIED-IF-GUARDED: optional shape/weight validity guards (AC9)
tests/
  fixtures/
    benchmark/              # + 3 NEW Standard anchor .txt decklists
    benchmark_decks.py      # MODIFIED: additive _MANIFEST rows (existing 7 entries untouched)
    assessment.py           # MODIFIED (optional): additive tagged-card builders
  unit/
    fixtures/test_benchmark_decks.py    # MODIFIED: additive shape tests; count pin amended
    logic/test_assessment_scorer.py     # NEW: AC4/AC8/AC11 matrix
    logic/test_assessment_profiles.py   # MODIFIED-IF-TUNED: the sanctioned v3->v4 pin amendment
  integration/
    logic/__init__.py                   # NEW
    logic/test_assessment_benchmark.py  # NEW: resolution + AC7 assertions (integration marker)
_bmad-output/implementation-artifacts/deferred-work.md  # MODIFIED: AC9 dispositions
plugin/                     # REGENERATED mirror (verify scorer.py + every touched core file staged)
```

- No changes to `classifiers.py`, `mana_base.py`, `consistency.py`, `combos.py` logic, any
  `src/data`/`src/mcp_server`/`scripts` file, or `pyproject.toml`. No DB objects, no
  migrations.
- Downstream consumers to keep in mind while naming things: **7.2 / feature 4.2** (passes
  snapshot variants + resolved commanders in; maps `unknown_count > 0` →
  `game_changer_data_unavailable`, absent snapshot → `combo_data_unavailable`), **7.3**
  (serializes `CoreAssessment` into `AssessDeckPowerResult`: `bracket_floor=None` →
  `bracket: null`, `game_changers.card_names` → `flags.game_changers`, sorted-list AD-8
  discipline), **7.5** (`compare_deck_power` diffs two of these — field names you choose
  here become delta keys there).

## References

- [Source: _bmad-output/planning-artifacts/epics-deck-power-assessment.md#Story 2.9] — the
  binding ACs (compose, determinism, ≥3 Standard anchors added additively, benchmark
  outcomes, diff-sensitivity, monotonicity properties, hand-tuned documented weights).
- [Source: epics-deck-power-assessment.md#Epic 2 overview] — "Validated with combo
  *fixtures* — no live dependency required"; the FR21/FR23 core-values-vs-edge-policy split
  note.
- [Source: _bmad-output/planning-artifacts/sprint-change-proposal-2026-07-12.md#P5, #P6] —
  benchmark funded (Standard anchors + monotonicity in 5.9; 5.1 fixture extended additively
  inside 5.9); fixed output shape (`bracket: null`).
- [Source: _bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-11/ARCHITECTURE-SPINE.md#AD-2]
  — `score(cards, commanders, combos, profile) -> assessment`, no network/DB/clock; [#AD-4]
  — `unknown_count` never lowers the floor, never coalesce; [#AD-7] — fixed shape, all
  seven keys, `bracket: null` for Standard; [#AD-8] — sorted lists, integer scores, no
  clock; [#AD-13] — commanders arrive resolved; [#Deferred] — weights/benchmark/earliest-turn
  owned by implementation+calibration (this story).
- [Source: src/logic/assessment/aggregate.py:22-27] — the composition contract this story
  implements verbatim; [:83-87] — the `_to_score` third-copy hoisting cue.
- [Source: src/logic/assessment/dimensions.py:607 (dimension_vector), :327 (bracket_floor),
  :294 (BracketFloorSignal), :241/:262 (GameChangerSignal/game_changer_signal), :101-131
  (floor/cEDH constants incl. EXTRA_TURN_CHAIN_MIN=2, CEDH_COMBO_TURN_MAX=4,
  CEDH_TUTOR_MIN=4, CEDH_AVG_MV_MAX=2.5, BRACKET_FLOOR_MAX=4)].
- [Source: src/logic/assessment/combos.py:157 (match_combos), :227 (combo_type keys on
  "infinite" substring), :247 (earliest_turn_estimate: max-piece + cumulative T(T+1)/2)].
- [Source: src/logic/assessment/profiles.py:132/:161] — v3 profiles, weights, thresholds
  `(20,40,60,80)` both formats; [:14-24] — the bump rule + "5.9 hand-tunes" contract.
- [Source: tests/fixtures/benchmark_decks.py:64-111 (BenchmarkCard/BenchmarkEntry), :163
  (load_benchmark), :215-296 (_MANIFEST: 7 entries — 3 precons B2, Atraxa B3, 2 cEDH B4,
  1 Standard)] — names-only fixture; tolerance contract in the module docstring
  ([:13-18]); resolution deferred to this story ([:4-6]).
- [Source: _bmad-output/implementation-artifacts/5-1-compose-the-calibration-benchmark-set.md]
  — reconstructed-list precedent (Brad accepted), 373/373 manual resolution spot-check, the
  Kinnan singleton fix.
- [Source: _bmad-output/implementation-artifacts/deferred-work.md#story-5.8, #story-5.7] —
  the five deferred items AC9 dispositions (aggregate guards; threshold-100 domain;
  card_advantage 98 cap; sixty_card scale comparability; win_turn_band guard).
- [Source: src/data/database.py:27/:64/:120] — `create_engine` (central-DB default),
  `create_session_factory`, `is_database_initialized`; [src/data/repositories/card.py:153]
  — `find_by_name_exact(name, format_filter=None, games=None)` (leave filters None).
- [Source: tests/integration/search/test_rag_eval.py:1-17] — the integration-marker
  precedent: operator-local-data-dependent quality gates live in the active suite.
- [Source: _bmad-output/project-context.md#Framework rules, #Testing Rules, #Code Quality]
  — layering, mypy --strict / ruff / Google docstrings / pytest gates.

## Dev Agent Record

### Agent Model Used

claude-fable-5 (Claude Fable 5)

### Debug Log References

- Baseline verified: clean tree at `a42c537`, fast suite 1067 passed / 5 deselected.
- First benchmark run (pre-calibration): 5 passed / 4 failed / 3 skipped — failures were
  2 DFC front-face-name resolution regressions, the Kinnan cEDH tutor leg, and the jank
  pile at score 23 vs the v3 Focused cut (20); skips were unknown-GC rows (see the
  environment-repair note below).
- Final: fast suite 1119 passed / 17 deselected; FULL suite (integration included)
  1136 passed, 0 failed, 0 skipped — the benchmark module runs green on the live DB.

### Completion Notes List

- **Composition (AC1–AC4):** `src/logic/assessment/scorer.py` ships `score()` (AD-2
  four-input keyword-only signature, `variants` naming) and the frozen slotted
  `CoreAssessment` with exactly the AC3 ten-field shape. The only rubric branch decides
  whether `bracket_floor()` is called; trigger booleans (`mass_land_denial`,
  `extra_turn_chains`) are computed format-agnostically from one `classify_deck` read
  and commander-parity-pinned against `BracketFloorSignal`. The module docstring
  documents the sanctioned internal re-derivations (no single-classification claim) and
  the Epic-7 consumer map. Exports added additively, `__all__` bytewise-sorted.
- **Offline tests (AC4/AC8/AC11):** `tests/unit/logic/test_assessment_scorer.py` — 40
  tests covering composition equalities, rubric fork + swap invariance, commander
  parity, fixed shape, empty inputs, determinism/non-mutation, and the literal-add
  monotonicity properties (GC-add, tutor-add, interaction-cut) + diff-sensitivity
  (almost_included → included strictly raises `combo_potential`) over 2 distinct
  synthetic base decks. All properties held under the v1 mappings without weakening —
  the tutor bonus's additive-only construction survived the literal add. Tagged-card
  builders promoted to `tests/fixtures/assessment.py` (second-consumer consolidation
  lesson).
- **Standard anchors (AC5):** three new committed 60-card lists, every name validated
  against the live snapshot for exact resolution AND Standard legality before
  committing: `standard_dimir_midrange` (High-Power; Kaito/Enduring Curiosity meta
  shell), `standard_mono_white_lifegain` (Focused; coherent theme, clunky removal, no
  draw), `standard_jank_pile` (Unfocused; 3-color high-curve commons, includes one full
  `"A // B"` DFC name to exercise resolution). Manifest rows appended; existing 7
  entries' manifest rows untouched; `test_benchmark_decks.py` extended additively (no
  count pin existed; added the 4-distinct-Standard-bands guard).
- **Benchmark harness (AC6/AC7):** `tests/integration/logic/test_assessment_benchmark.py`
  (integration marker). Design note: the module-scoped fixture is SYNCHRONOUS and does
  one `asyncio.run` resolution sweep (central DB via `create_engine()` default +
  `is_database_initialized` skip guard), yielding plain Pydantic objects so the
  per-entry tests stay pure/sync — avoids pytest-asyncio module-loop-scope pitfalls.
  Unfiltered `find_by_name_exact`; hard-fail on unresolved names; per-entry skip on
  `game_changer is None`. cEDH combo fixtures verified against the committed lists
  (Dramatic Reversal + Isochron Scepter for Tymna/Thrasios; Kinnan + Basalt Monolith,
  `commander_required=True`, for Kinnan — both earliest turn 3 ≤ 4) plus a
  fixture-integrity test class pinning pieces-in-decklist. Tolerance policy encoded
  once in `_assert_expected_outcome` with a docstring citing 5.1.
- **Calibration (AC7/AC8/AC9) — all values documented in-code with benchmark evidence:**
  - *Commander weights re-spread* (speed .10→.15, consistency .20→.15, resilience
    .15→.10, interaction .15→.10, mana_efficiency .10→.05, card_advantage .15,
    combo_potential .15→.30): under v3 the Talrand precon (67) outscored the Tymna cEDH
    list (65) — unsolvable by cuts; at v1 curves interaction (100 everywhere) and
    mana_efficiency (~0 for 99-card decks) carry no separation, combo_potential/speed
    carry nearly all of it. Resulting scores: precons 45/50/54, Atraxa 44, cEDH 68/71.
  - *Commander `tier_thresholds` unchanged* (20,40,60,80) — anchors order cleanly with
    ≥ 6-point margins.
  - *Standard `tier_thresholds`* (20,40,60,80) → (28,45,65,85), anchored on jank 23 /
    lifegain 32 / mono-red 58 / Dimir 73 (every anchor ≥ 5 points from its nearest
    cut); Standard weights unchanged. Standard tiers assert EXACT labels (FR20) — green.
  - *`CEDH_TUTOR_MIN` 4 → 3* (shared dimensions.py constant → bumps BOTH versions):
    the FR6 tutor definition excludes battlefield tutors and library-exile effects, so
    real cEDH lists undercount — the committed Kinnan list carries exactly 3 tagged
    tutors and failed candidacy on this leg alone.
  - *Versions bumped* commander-v3→v4, standard-v3→v4; BOTH 5.8 version pins amended in
    the same edit (`test_assessment_profiles.py::test_versions_bumped_for_story_5_9_calibration`
    and `test_assessment_aggregate.py::test_versions_read_v4` — the aggregate module had
    a second pin; the pin-moves-with-the-bump rule applied to both).
- **Deferred dispositions (AC9), mirrored in deferred-work.md:** (a) `_speed_score` now
  raises on `lo > hi` (lo == hi stays valid — the ±2 pad keeps the divisor non-zero);
  (b) `aggregate_score` raises on negative/non-finite weights, `tier_label` raises on
  cuts not strictly ascending in (0, 100); (c) threshold domain tightened to (0, 100)
  incl. the shape test; (d) `card_advantage` 98 cap KEPT, decision documented in the
  docstring (headroom invisible under weights/cuts; re-normalizing changes every score
  for zero benefit); (e) `sixty_card` scale comparability closed by per-format
  threshold anchoring, stated in the STANDARD_PROFILE comment. All guards test-pinned
  (`TestStory59Guards`, `TestStory59WinTurnBandGuard`).
- **Sanctioned fixture correction (5.1 resolution regressions, Kinnan-fix precedent):**
  two existing decklists carried DFC front-face-only names that do not resolve via
  `find_by_name_exact` — corrected to the full stored names, same cards:
  `precon_talrand_sky_summoner.txt` "Docent of Perfection" → "Docent of Perfection //
  Final Iteration"; `standard_mono_red_aggro.txt` "Kumano Faces Kakkazan" → "Kumano
  Faces Kakkazan // Etching of Kumano". Manifest rows untouched.
- **Environment repair (live central DB — operational, no repo code changed):** the
  story's baseline note ("imported AND backfilled") was stale — the live `cards.db`
  was missing the `game_changer` COLUMN entirely (the 2026-07-10 games-union re-import
  predated/reverted it). Repair: re-ran `scripts/migrate_add_game_changer.py`
  (idempotent ALTER) + the plain `import_scryfall_data.py` re-import (53 TRUE). Two
  residual data-quality issues surfaced and were hand-repaired: (1) bulk-snapshot
  printing churn left ~13k stale duplicate rows with NULL `game_changer` (4,711 names
  resolved first-by-id to a stale row, incl. Rhystic Study) — fixed by copying
  `game_changer` across same-`oracle_id` rows; (2) the import errored on exactly 36
  cards (incl. Blood Crypt, Hallowed Fountain, Reckoner Bankbuster) leaving them NULL —
  none is on the 53-card GC list, so they were set FALSE to mirror the bulk data. Both
  root causes logged as new items in deferred-work.md (importer-owned, out of AC10
  scope). Final DB state: 51,093 FALSE / 96 TRUE / 0 NULL — the AD-4 window is closed
  on this machine and the benchmark runs without skips.
- **Gates (AC11/AC12):** ruff check + format clean; `mypy --strict src/` clean (64
  files); fast suite 1119 passed / 17 deselected; full suite 1136 passed with the
  benchmark green on the live DB; plugin mirror regenerated (new `scorer.py` +
  4 modified core files mirrored) and staged in the story commit.

### File List

- src/logic/assessment/scorer.py (NEW)
- src/logic/assessment/__init__.py (MODIFIED — additive exports)
- src/logic/assessment/profiles.py (MODIFIED — v4 calibration values + comments)
- src/logic/assessment/dimensions.py (MODIFIED — CEDH_TUTOR_MIN, win_turn_band guard, cap docstring)
- src/logic/assessment/aggregate.py (MODIFIED — weight/threshold guards)
- plugin/server/src/logic/assessment/scorer.py (NEW — regenerated mirror)
- plugin/server/src/logic/assessment/__init__.py (MODIFIED — regenerated mirror)
- plugin/server/src/logic/assessment/profiles.py (MODIFIED — regenerated mirror)
- plugin/server/src/logic/assessment/dimensions.py (MODIFIED — regenerated mirror)
- plugin/server/src/logic/assessment/aggregate.py (MODIFIED — regenerated mirror)
- tests/fixtures/assessment.py (MODIFIED — additive tagged-card builders)
- tests/fixtures/benchmark_decks.py (MODIFIED — 3 additive _MANIFEST rows)
- tests/fixtures/benchmark/standard_dimir_midrange.txt (NEW)
- tests/fixtures/benchmark/standard_mono_white_lifegain.txt (NEW)
- tests/fixtures/benchmark/standard_jank_pile.txt (NEW)
- tests/fixtures/benchmark/precon_talrand_sky_summoner.txt (MODIFIED — DFC full-name fix)
- tests/fixtures/benchmark/standard_mono_red_aggro.txt (MODIFIED — DFC full-name fix)
- tests/unit/logic/test_assessment_scorer.py (NEW)
- tests/unit/logic/test_assessment_dimensions.py (MODIFIED — additive guard tests)
- tests/unit/logic/test_assessment_aggregate.py (MODIFIED — additive guard tests + v4 pin + domain tighten)
- tests/unit/logic/test_assessment_profiles.py (MODIFIED — v4 pin amendment)
- tests/unit/fixtures/test_benchmark_decks.py (MODIFIED — additive band-coverage test)
- tests/integration/logic/__init__.py (NEW)
- tests/integration/logic/test_assessment_benchmark.py (NEW)
- _bmad-output/implementation-artifacts/deferred-work.md (MODIFIED — 5 dispositions + 2 new importer items)
- _bmad-output/implementation-artifacts/sprint-status.yaml (MODIFIED — status tracking)
- _bmad-output/implementation-artifacts/5-9-pure-score-entry-point-benchmark-validation.md (MODIFIED — this file)

## Change Log

- 2026-07-14: Story 5.9 implemented (review) — `score()` + `CoreAssessment` composition
  shipped and test-pinned; 3 Standard anchors added (snapshot-validated); benchmark
  integration harness lands the deferred 5.1 resolution gate; calibration pass
  (Commander weights re-spread, Standard cuts anchored, CEDH_TUTOR_MIN 4→3) with
  commander-v4/standard-v4 bumps and both version pins amended; 5 deferred items
  dispositioned (3 guards added + tested, 1 kept-documented, 1 closed by per-format
  anchoring); 2 DFC full-name fixture corrections; live-DB game_changer environment
  repair documented with 2 new importer items logged to deferred-work.md. Full suite
  1136 passed incl. the benchmark green on the live snapshot (NFR6 gate).

- 2026-07-14: Story 5.9 created (ready-for-dev) — ultimate context engine analysis
  completed: comprehensive developer guide covering the AD-2 four-input signature
  reconciliation, the CoreAssessment fixed shape + rubric-fork-by-composition, the
  format-agnostic trigger semantics with commander parity, the names-only benchmark fixture
  and its integration-bound resolution gate (skip-loudly/fail-loudly policy), cEDH combo
  fixtures as the candidacy prerequisite, the decide-once tolerance policy, literal-add
  monotonicity ownership, version-bumps-track-behavior tuning rules, and the five
  deferred-item dispositions. Baseline: clean `a42c537`, 1067 passed / 5 deselected.

## Review Findings

_Code review 2026-07-15 (adversarial: Blind Hunter + Edge Case Hunter + Acceptance
Auditor). 1 decision-needed, 1 patch, 0 deferred, 10 dismissed. Composition, purity,
determinism, non-mutation, and all 12 ACs verified sound; plugin mirror confirmed
byte-identical to `src/` (AC12)._

- [x] **[Review][Decision→Patched] `unknown_gc` skip disables the Standard FR20 gate on data
  Standard never consumes** [tests/integration/logic/test_assessment_benchmark.py:227] —
  RESOLVED: skip narrowed to `entry.format == "commander"` (option a); docstring updated;
  benchmark suite re-run green (12 passed, no Standard skips). —
  the per-entry skip fires for the WHOLE entry (including the exact-tier FR20 assertion at
  :179) whenever any resolved card has `game_changer is None`. But Standard scores are
  `heuristic_only` and never read `game_changer`, so a reopened GC-backfill window (which
  actually happened mid-story — see the "Environment repair" Completion Note) would
  silently skip the headline Standard acceptance signal for an unrelated reason. AC6 says
  literally "skip if any resolved card has `game_changer is None`," but its stated
  rationale is "the Atraxa B3 expectation needs real GC data" — commander-only. Choice:
  (a) narrow the skip to `entry.format == "commander"` (honors AC6 intent, keeps the
  Standard gate live); (b) keep the unconditional skip as literally written in AC6;
  (c) defer.

- [x] **[Review][Patch] `tier_thresholds` domain split-brain — profiles test still allows a
  cut of 100 that the runtime guard rejects** [tests/unit/logic/test_assessment_profiles.py:252]
  — FIXED: assertion `<= 100` → `< 100` + message; docstring prose corrected in both
  `src/` and `plugin/` mirror. ruff + mypy clean; profiles/aggregate suites green.
  — AC9(c) narrowed the domain to `(0, 100)` and the guard (`aggregate.py:164`) now raises
  on `cut >= 100`, but `test_tier_thresholds_in_domain` still asserts `0 < cut <= 100`
  ("must sit in (0, 100]"). A future tuner setting a cut of 100 would pass this test yet
  fail `test_assessment_aggregate.py:370` (`0 < cut < 100`) and crash `tier_label` at
  runtime. Fix: `<= 100` → `< 100` and update its message; also correct the stale
  `(0, 100]` prose in the `tier_thresholds` docstring (`src/logic/assessment/profiles.py:111`).
