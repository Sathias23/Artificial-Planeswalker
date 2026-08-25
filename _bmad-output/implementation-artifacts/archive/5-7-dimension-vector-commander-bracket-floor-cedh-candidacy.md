---
baseline_commit: 05662f1cf0cfb082abda0f01a53c8dc39a8172f2 # "story 5.6 review -> done" commit (Task 0: found already committed at dev start)
---

# Story 5.7: Dimension vector + Commander Bracket floor + cEDH candidacy

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

> **Sprint/feature numbering:** this is sprint key
> `5-7-dimension-vector-commander-bracket-floor-cedh-candidacy` (`epic-5`), which is
> **feature Epic 2, Story 2.7** in `_bmad-output/planning-artifacts/epics-deck-power-assessment.md`.
> Sprint Epic 5 = feature Epic 2 "Deterministic scoring core".

## Story

As the scorer,
I want the 7-dimension vector and the Commander Bracket floor,
so that a deck gets its power read.

## Context & why this story exists

This is the story where the raw signals become **scores**. Stories 5.3–5.6 shipped
signal-emitters only (category counts, curve/Karsten math, hypergeometrics, matched combo
records) and each one explicitly deferred its 0–100 mapping "to 5.7". This story is that
consumer: it maps signals onto the **7 integer dimensions** (FR16), walks the **WotC Bracket
decision tree** to a floor (FR18), and flags **cEDH candidacy** (never asserting Bracket 5).
Three things hang off it:

- **FR16 vector** — `speed, consistency, resilience, interaction, mana_efficiency,
  card_advantage, combo_potential`, each **integer 0–100, all seven always present for any
  format** (AD-7 fixed shape). `speed` is deterministic from curve + ramp density + combo
  earliest-turn — no goldfish simulation.
- **FR18 floor** — Game Changer count (AD-4 read side: `None` never coalesced) + hard
  triggers (mass land denial, extra-turn chains — the "chain refinement" 5.3 deferred here)
  + matched combos (5.6's buckets, `combo_type`, `BRACKET_TAG_TO_BRACKET`) → Bracket floor,
  capped at 4; `cedh_candidate` is a separate boolean, candidacy only.
- **5.8/5.9/Epic 7 contract** — 5.8 aggregates this vector with the profile weights; 5.9's
  `score()` composes everything and validates against the benchmark; Epic 7 serializes the
  floor/GC/chain explainability payloads into `flags`. What you name and shape here is what
  they consume.

Like 5.3–5.6: mapping curves and thresholds are **provisional v1 values that Story 5.9
hand-tunes against the benchmark** (NFR8) — tests verify shape, clamps, and monotone
directions, never exact curve outputs.

## Acceptance Criteria

1. **One new pure module owns the vector and the floor.** Given the one-module-per-story
   house pattern (5.3 `classifiers`, 5.4 `mana_base`, 5.5 `consistency`, 5.6 `combos`),
   when the story is done, then `src/logic/assessment/dimensions.py` exists and contains
   ALL of this story's public surface (AC2–AC6); it is pure (no network/DB/clock/random/
   logging — AD-2), imports only stdlib + `src.data.schemas.*` + the sibling assessment
   modules it consumes (`classifiers`, `mana_base`, `consistency`, `combos`, `profiles`) —
   this story is the sanctioned first cross-module consumer — and never imports
   `src/search`, `src/mcp_server`, `src/data/repositories`, `src/data/models`,
   `src/logic/mana_curve`, or `src/logic/synergy`. All new public names are exported
   additively from `src/logic/assessment/__init__.py` (`__all__` kept bytewise-sorted).
   [epics 2.7; AD-2; AD-9; project-context#Framework rules]

2. **The 7-dimension vector: fixed closed shape, integer 0–100, both formats.** Given
   AD-7's fixed key set, when `DimensionVector` is defined, then it is a frozen slots
   dataclass with **exactly one `int` field per entry in `profiles.DIMENSIONS`, in that
   order** (the `DimensionWeights` precedent — mypy makes a missing/extra dimension a type
   error; a test asserts its field names equal `DIMENSIONS`). And
   `dimension_vector(deck_cards, *, matched_combos, profile) -> DimensionVector`:
   - takes `Sequence[DeckCard]` (quantity-aware), `matched_combos: Sequence[ComboRecord]`
     (the OUTPUT of 5.6's `match_combos` — records with `bucket` set; a record with
     `bucket=None` contributes nothing, documented), and a `FormatProfile`;
   - works identically under **both** profiles — no `rubric` branch inside; the only
     format fork is the `KarstenFormula` selector read from the profile (AC6);
   - every dimension is produced by clamping to `[0, 100]` and converting to `int` via
     **one shared decide-once rounding policy** (recommended: round-half-up
     `int(x + 0.5)` after clamping — banker's-rounding surprises avoided; documented at
     the code site);
   - gathers shared signals **once** per call — one `classify_deck`, one `compute_curve`
     — and feeds the per-dimension helpers from those locals (the logged 5.3
     deferred-work item: `detect_mass_land_denial`/`detect_extra_turn_cards` each
     re-classify the whole deck; do not call them back-to-back);
   - an empty deck yields a full vector (degrade, never raise);
   - identical inputs yield identical output; sideboard rows are NOT filtered (standing
     5.3–5.6 policy, documented + pinned).
   The per-dimension curves are implementation-owned **hard-requirement + recommended-
   model** style (the 5.6 earliest-turn precedent): pure, deterministic, int 0–100,
   documented at the code site, marked provisional/5.9-owned, and respecting the AC8
   monotone directions. Recommended v1 models are in Dev Notes — use them unless you have
   a better documented idea. [epics 2.7; FR16; AD-7; NFR8]

3. **Game Changer read side — `None` is never `False`.** Given AD-4, when
   `game_changer_signal(deck_cards) -> GameChangerSignal` is defined, then the frozen
   signal carries:
   - `known_count: int` — quantity-aware count of cards whose `game_changer is True`
     (a `None` card NEVER counts, in either direction);
   - `card_names: tuple[str, ...]` — unique contributing (True) names, sorted ascending
     bytewise (the `CategoryCount`/`HardTriggerFlag` explainability precedent — Epic 7's
     `flags.game_changers` payload);
   - `unknown_count: int` — quantity-aware count of cards whose `game_changer is None`
     (the edge derives `game_changer_data_unavailable` from this; emitting the AD-6 token
     itself is NOT this story's job).
   Three states stay distinct everywhere; no bool coercion of `None` anywhere in the
   module. [epics 2.7; AD-4; FR11]

4. **The Bracket floor walks the WotC decision tree — deterministic, explainable, capped
   at 4.** Given addendum §C and FR18, when
   `bracket_floor(deck_cards, *, matched_combos) -> BracketFloorSignal` is defined, then
   the floor is `max()` of these contributions, clamped to at most `BRACKET_FLOOR_MAX = 4`:
   - **baseline `BASELINE_BRACKET_FLOOR = 2`** (decide-once, documented at the code site):
     Bracket 1 (Exhibition) is intent-declared exactly like Bracket 5 — card data cannot
     distinguish a deliberate theme build from a core deck, and WotC's own guidance is
     "bracket up when in doubt" — so the computed floor never claims B1 (the effective
     computed range is {2, 3, 4}); FR18's "1–5" is the scale domain, not an emission
     requirement. This also anchors the 5.1 benchmark (precons expected ~B2, 5.9 tolerance
     `[expected, expected+1]`);
   - **Game Changers** (from AC3's `known_count` — `unknown_count` MUST NOT contribute,
     the AD-4 "absent count must not lower the floor" read side): `1–3 → 3`, `>= 4 → 4`
     (`GC_BRACKET_THREE_MIN = 1`, `GC_BRACKET_FOUR_MIN = 4`, addendum §C);
   - **mass land denial**: any `MASS_LAND_DENIAL`-tagged card → `4`;
   - **extra-turn chains** (the refinement 5.3 deferred here — decide-once, provisional):
     quantity-aware `EXTRA_TURN` count `>= EXTRA_TURN_CHAIN_MIN = 2` → chains-capable →
     `4`; a single extra-turn card never raises the floor;
   - **combos** (from `matched_combos`; **only `bucket == "included"` records ever raise
     the floor** — an `almost_included` combo is not in the deck, documented): an included
     two-card infinite (`combo_type(c) == TWO_CARD_INFINITE`) with
     `earliest_turn_estimate(c, deck_cards) <= EARLY_COMBO_TURN_MAX = 6` (provisional) →
     `4`; any other included infinite combo → `3`; additionally every included combo
     contributes `BRACKET_TAG_TO_BRACKET[c.bracket_tag]` (5.6's map — already capped at 4
     by construction).
   `BracketFloorSignal` is a frozen slots dataclass carrying the floor plus the NFR2
   explainability payload: `floor: int`, `game_changers: GameChangerSignal`,
   `mass_land_denial: bool` + sorted contributing names, `extra_turn_chain: bool` + sorted
   contributing names, `early_two_card_infinite: bool` + the sorted `spellbook_id`s that
   drove it, and `cedh_candidate: bool` (AC5). Identical inputs → identical output; empty
   deck + no combos → floor 2, all booleans False. [epics 2.7; FR18; AD-4; AD-11;
   addendum §C]

5. **cEDH candidacy is flagged, never asserted — and tutors stay out of the floor.** Given
   FR18 and the deck-assess research, when candidacy is computed (inside `bracket_floor`,
   surfaced as `BracketFloorSignal.cedh_candidate`), then:
   - the recommended v1 rule (decide-once, documented, provisional constants all `Final`,
     5.9 may retune or relax to a k-of-n vote): candidate iff **floor == 4** AND an
     included infinite combo exists with
     `earliest_turn_estimate <= CEDH_COMBO_TURN_MAX = 4` AND quantity-aware `TUTOR` count
     `>= CEDH_TUTOR_MIN = 4` AND `average_mana_value <= CEDH_AVG_MV_MAX = 2.5`
     (dense fast mana + tutors + compact early combo — docs/deck-assess.md:186);
   - the floor itself NEVER reads the tutor count (WotC removed tutor restrictions from
     Brackets in Oct 2025 — the `classifiers.TUTOR` docstring already warns 5.7 about
     exactly this); tutors inform candidacy and the soft dimensions only;
   - no code path emits floor 5 — `cedh_candidate` is the only Bracket-5 surface.
   [epics 2.7; FR18; docs/deck-assess.md:119,186; classifiers.py:41-43]

6. **`FormatProfile` extends additively; versions bump.** Given AD-3's bump rule and the
   profiles module docstring ("Stories 5.3–5.8 extend this shape additively as real curves
   land"), when the profile is touched, then:
   - `FormatProfile` gains `karsten_formula: KarstenFormula` (imported from
     `src.logic.assessment.mana_base` — no cycle: `mana_base` does not import `profiles`),
     set to `"commander"` on `COMMANDER_PROFILE` and `"sixty_card"` on `STANDARD_PROFILE`
     — this is how `dimension_vector` selects the Karsten formula / anchors / structural
     baselines without a rubric branch (the 5.4/5.5 `KarstenFormula` selector pattern,
     now profile-driven per AD-3);
   - **both** `format_profile_version` strings bump in the same edit
     (`commander-v1 → commander-v2`, `standard-v1 → standard-v2`);
   - `tests/unit/logic/test_assessment_profiles.py` is extended additively (new-field
     checks per format); existing shape/invariant tests keep passing;
   - NO other profile field changes — weights, bands, flags stay untouched (5.8/5.9 own
     them). If a mapping curve needs a per-format parameter beyond `karsten_formula` and
     `win_turn_band`, prefer a `Final` module constant keyed by `KarstenFormula` in
     `dimensions.py` (the 5.4 `_FORMULA_ANCHORS` / 5.5 `STRUCTURAL_GAP_BASELINES`
     precedent) over widening the profile in this story. [epics 2.7; AD-3; FR4;
     profiles.py docstring]

7. **Scope guard — signals in, scores out, nothing more.** Given the story split, when
   reviewed, then this story ships **no** aggregate 0–100 score, no profile-weight read,
   no tier label, no Standard-fork wiring, no confidence tokens or AD-6 vocabulary, no
   `score()` entry point, no benchmark assertion, no serialization, and no edits to
   `classifiers.py`, `mana_base.py`, `consistency.py`, `combos.py`, `synergy.py`, any
   `src/data` / `src/mcp_server` / `scripts/` file, or the benchmark fixtures. The ONLY
   modified existing sources are `profiles.py` (AC6), the two `__init__.py` re-export
   surfaces, and additive test files. The resilience dimension's proxy status (Dev Notes)
   is documented in its PUBLIC docstring — a protection/recursion classifier category is
   explicitly NOT added (AD-10 vocabulary changes are 5.9-owned). [epics 2.7; AD-3;
   AD-10; FR19/FR20/FR21 deferrals]

8. **Offline unit tests prove the read.** Given the project's testing rules, when
   `tests/unit/logic/test_assessment_dimensions.py` runs (no `integration` marker, no DB),
   then using the `tests/fixtures/assessment.py` factories (`make_card` / `make_deck_card`
   / `make_combo_record` — extend additively only if needed; note `make_card` defaults
   `game_changer` to ABSENT → `None`, which is exactly the AD-4 unknown state) it verifies
   at minimum:
   - **vector shape:** `DimensionVector` frozen (assignment raises); field names ==
     `DIMENSIONS`; every value `int` in `[0, 100]` for a populated deck, an empty deck,
     and both profiles (fixed shape, degrade-not-raise);
   - **GC signal:** `True`/`False`/`None` three-state (None counts in `unknown_count`
     only, never `known_count`); quantity-aware; names sorted, unique, True-only;
   - **floor gates, each branch:** 0 GC → 2; 1 and 3 GC → 3; 4 GC → 4; MLD card → 4;
     two extra-turn cards → 4 while one → no raise; included early two-card infinite → 4;
     included late (expensive pieces) two-card infinite → 3; included `RUTHLESS` tag → 4
     via the map; `almost_included` anything → never raises; `bucket=None` records
     contribute nothing; floor never exceeds 4; empty deck → 2;
   - **AD-4 pin:** a deck of 4+ `game_changer=None` cards (0 True) keeps floor 2 and
     reports `unknown_count`, proving unknowns neither raise nor lower;
   - **cEDH:** a constructed dense fixture (4+ GC true, early included infinite, 4+
     tutors, low curve) flags `cedh_candidate=True`; each single missing leg → `False`;
     floor still 4, never 5;
   - **monotone directions (the 2.9 down-payment — SWAP-based, see Dev Notes):** adding a
     Game Changer never lowers the floor (floor is `max`-based, safe under add); swapping
     a vanilla filler card for a tutor (deck size constant) never lowers the `consistency`
     dimension; swapping filler for interaction never lowers `interaction` (and a
     zero-interaction deck scores <= the same deck with interaction swapped in); swapping
     filler for a CHEAP (cmc <= 2) ramp spell never lowers `speed`; an earlier included
     combo (cheaper pieces) never lowers `speed` or `combo_potential`; an included combo
     scores `combo_potential` >= the same combo `almost_included`;
   - **verify-by-shape for provisional curves:** clamps/anchors only (empty deck →
     `combo_potential == 0`; no exact mid-curve pins — the curves are 5.9-owned);
   - **determinism:** two calls on equal input → equal results; shuffled `deck_cards` /
     `matched_combos` input order → identical output; inputs not mutated;
   - **sideboard pin:** a `sideboard=True` row counts (standing not-filtered policy);
   - **profile additions:** `karsten_formula` per format; both version strings bumped
     (test the new values);
   - assertions carry failure messages naming the dimension/gate/signal **or** the task
     claim is dropped (the 5.5 review lesson).
   Runs green under `uv run pytest -m "not integration"` (baseline at story creation:
   **925 passed**, measured with the 5.6 review patches applied). [project-context#Testing
   Rules; 5-5/5-6 review lessons]

9. **Quality gates pass — including the `src/`-touch plugin mirror.** Given this story
   edits files under `src/`, when committed, then `mypy --strict` passes (full hints,
   Google docstrings on module + every public name), `ruff check` + `ruff format` are
   clean, and the regenerated `plugin/` mirror is staged in the same commit (the
   pre-commit hook is installed in this checkout and rebuilds it — verify the
   `plugin/server/src/logic/assessment/` mirror diffs, including `profiles.py` and the new
   `dimensions.py`, are staged; never `--no-verify`). [project-context#Code Quality;
   epic-4 retro]

## Tasks / Subtasks

- [x] **Task 0 — Land the 5.6 review-patch commit; confirm baseline** (AC: —)
  - [x] The working tree at story creation carries the UNCOMMITTED 5.6 review patches
        (`src/data/schemas/combo.py`, `src/logic/assessment/combos.py`, the combos test
        module, both plugin mirrors, the 5-6 story file, `sprint-status.yaml`). Commit
        them FIRST as their own commit (suggested:
        `fix: credit command-zone combo pieces, DFC commander keys & min-length guard (story 5.6 review -> done)`),
        then record that hash as this story's `baseline_commit`.
        *(Found already committed at dev start as `05662f1` — recorded as
        `baseline_commit`; only sprint-status + this story file were dirty.)*
  - [x] Verify `uv run pytest -m "not integration"` reports **925 passed** before writing
        any 5.7 code. *(Confirmed: 925 passed, 5 deselected.)*
- [x] **Task 1 — Profile extension** (AC: 6)
  - [x] Add `karsten_formula: KarstenFormula` to `FormatProfile`; set per profile; bump
        both versions; extend `test_assessment_profiles.py` additively.
- [x] **Task 2 — Module scaffold + GC signal** (AC: 1, 3)
  - [x] `src/logic/assessment/dimensions.py` module docstring: FR16/FR18 seam, consumes
        5.3–5.6 signals + profile, provisional/5.9-owned curves, resilience proxy status,
        decide-once policies (rounding, baseline floor, chain refinement, included-only
        floor raises, sideboard).
  - [x] `GameChangerSignal` + `game_changer_signal` per AC3.
- [x] **Task 3 — Bracket floor + cEDH candidacy** (AC: 4, 5)
  - [x] Gate constants (`Final`, source comments, provisional marks);
        `BracketFloorSignal` + `bracket_floor` walking the AC4 tree with one
        `classify_deck` call; candidacy per AC5 folded into the signal.
- [x] **Task 4 — Dimension vector** (AC: 2)
  - [x] `DimensionVector` (frozen slots, `DIMENSIONS`-shaped) + `dimension_vector` with
        one-shot signal gathering, the shared clamp/round helper, and the seven
        per-dimension mapping helpers (recommended v1 models in Dev Notes; document each
        at its code site; respect the AC8 monotone directions).
- [x] **Task 5 — Package exports** (AC: 1)
  - [x] Extend `src/logic/assessment/__init__.py` `__all__` additively (bytewise-sorted).
- [x] **Task 6 — Offline unit tests** (AC: 8)
  - [x] `tests/unit/logic/test_assessment_dimensions.py` covering the full AC8 matrix.
- [x] **Task 7 — Quality gates + plugin mirror** (AC: 9)
  - [x] `uv run ruff check . --fix && uv run ruff format .`
  - [x] `uv run mypy src/` (strict) clean.
  - [x] `uv run pytest -m "not integration"` green (baseline: **925 passed**; now
        **991 passed** = 925 + 64 dimensions + 2 profile tests).
  - [x] Commit with the regenerated `plugin/` mirror staged (verify `dimensions.py` AND
        `profiles.py` mirror paths). Never `--no-verify`.

## Review Findings

_Code review 2026-07-14 (3 adversarial layers: Blind Hunter, Edge Case Hunter, Acceptance Auditor). All 9 ACs verified SATISFIED; 92 touched tests pass; `mypy --strict` clean; scope guard confirmed. No Critical/Major/correctness/determinism defects — None-vs-False identity checks, `max()`-based idempotent gates, sorted stored tuples, `_to_score` clamp-before-round, gate thresholds, and no-input-mutation all verified. Two low-priority docstring-accuracy patches + three 5.9-calibration defers below._

- [x] [Review][Patch] Module docstring overclaims "one `compute_curve` per entry point" [src/logic/assessment/dimensions.py:611] — FIXED 2026-07-14: module + `dimension_vector` docstrings and the inline comment now state one direct `compute_curve` plus the sanctioned `karsten_land_delta`/`earliest_turn_estimate` internal re-derivations. — `dimension_vector` computes the curve directly (:638) and again inside `karsten_land_delta` (mana_base.py:206), and `earliest_turn_estimate` (which rebuilds `_cmc_by_name`) runs twice per included infinite combo (:662 earliest-infinite loop + :590 in `_combo_potential_score`). Correctness/determinism are fine; the `classify_deck` one-call rule genuinely holds. Fix: tighten the module + `dimension_vector` docstrings (one `classify_deck`; curve computed once directly plus once inside the sanctioned `karsten_land_delta` API); optionally hoist the earliest-turn computation to run once.
- [x] [Review][Patch] `_speed_score` monotonicity docstring is over-broad [src/logic/assessment/dimensions.py:472] — FIXED 2026-07-14: reworded to the AC8 SWAP directions (cheap-ramp / lower-avgMV / earlier-combo), noting an expensive-ramp add can net-lower and that literal "add X" properties are 5.9's. — "more ramp … never lower the score" holds only under the AC8 SWAP / cheap-ramp reading; an expensive ramp spell that raises `average_mana_value` can net-lower the score. The guarded SWAP test is honest; tighten the docstring wording to the swap-based direction so 5.9 isn't misled.
- [x] [Review][Defer] `card_advantage` structurally caps at 98 [src/logic/assessment/dimensions.py:562] — deferred, 5.9 calibration. Max is `_CARD_ADVANTAGE_COUNT_WEIGHT` (80) + max tutor bonus (`min(6,·)·3` = 18) = 98; the dimension cannot emit 99/100. Provisional/5.9-owned by design.
- [x] [Review][Defer] `sixty_card` curve targets are undefended provisional guesses [src/logic/assessment/dimensions.py:177] — deferred, 5.9 calibration. The Commander targets trace to the Command Zone template; the sixty-card values (interaction 8, draw 6, instant/cheap 4) are self-labelled "honest provisional guess," and `mana_efficiency` uses the same land-delta penalty slope for 99- and 60-card decks, so Standard vs Commander vectors are not on a comparable scale until 5.9 anchors them.
- [x] [Review][Defer] `_speed_score` has no guard for a malformed `win_turn_band` (`lo > hi`) [src/logic/assessment/dimensions.py:484] — deferred, not reachable with current data. Both shipped profiles satisfy the documented `lo <= hi` invariant (`(7,10)`, `(5,8)`) and a profile test pins them; a future 5.9 band edit of the form `hi = lo-4` would divide by zero (`band_hi - band_lo + 4`) and `hi < lo` would invert the mapping. Optional cheap defense-in-depth for the band-editing workflow (the accepted 5.6 guard lesson).

## Dev Notes

### What this story is — and is NOT

- **IS:** one new pure module `src/logic/assessment/dimensions.py` (GC signal, Bracket
  floor + cEDH candidacy, 7-dimension vector); one additive `FormatProfile` field +
  version bumps; exports; offline tests.
- **IS NOT:** the weighted aggregate or its 0–100 (5.8), the descriptive tier label (5.8),
  the Standard heuristic-only fork wiring (5.8 — your vector is already format-agnostic),
  the confidence-reason enum (5.8 vocabulary, edge-assembled), `score()` + benchmark
  validation + monotonicity property suite (5.9), commander *resolution* (Epic 7 edge —
  matched combos arrive here already bucketed), any serialization (Epic 7, AD-8), any
  classifier-pattern or Karsten-constant edit (5.9's benchmark pass owns tuning those).
  If a function needs profile *weights*, a DB, the clock, or the network — wrong story.

### Baseline note (story-creation snapshot, 2026-07-14)

**The 5.6 review patches are applied but UNCOMMITTED** — `git status` shows the combos
modules, tests, plugin mirrors, 5-6 story file, and sprint-status modified; the last
commit is `2310306` (the 5.6 feat commit). sprint-status already says 5-6 done. Task 0
lands that commit first so this story starts from a clean tree, mirroring how `9d2e5f9`
("5.5 review -> done") was 5.6's baseline. Fast-suite baseline **925 passed** was measured
WITH those patches in the tree. The pre-commit hook (ruff + mypy + plugin rebuild) IS
installed in this checkout.

### The signal inventory you build from (all already shipped — reinvent nothing)

| Need | Use | Notes |
| --- | --- | --- |
| ramp/draw/interaction/tutor/wincon/MLD/extra-turn counts + names | `classifiers.classify_deck` | one call per public entry point; returns all 9 `CATEGORIES` zero-filled |
| per-card tags joined to cmc/type | `classifiers.classify_card` | the 5.4/5.5 join pattern |
| curve, avgMV, land/spell counts | `mana_base.compute_curve` | zero-safe |
| Karsten land delta + flood/screw | `mana_base.karsten_land_delta(formula=...)` | formula from `profile.karsten_formula` (AC6) |
| per-color pip deficits | `mana_base.compute_pip_signals(formula=...)` | fixed WUBRG five-tuple |
| opener access probabilities | `consistency.redundancy_signals` | fixed nine-tuple, per category |
| land access by turn | `consistency.land_access_by_turn` | exact hypergeometric |
| interaction instant-ratio + CMC dist | `consistency.interaction_signals` | |
| structural gap tokens | `consistency.structural_gaps(formula=...)` | closed enum, if a curve wants them |
| matched combos, buckets | input `matched_combos` (5.6 `match_combos` output) | do NOT call the matcher here — 5.9 wires it |
| combo type / earliest turn | `combos.combo_type`, `combos.earliest_turn_estimate` | derived, never stored |
| tag→bracket ints | `combos.BRACKET_TAG_TO_BRACKET` | Literal-keyed, total |
| GC membership | `Card.game_changer` (`bool \| None`) | AC3; never coalesce None |
| win-turn anchor, formula selector | `profiles.FormatProfile` | `win_turn_band`, new `karsten_formula` |
| dimension key set | `profiles.DIMENSIONS` | the one canonical home — mirror it |

### Load-bearing decisions (read before writing code)

- **Baseline floor 2, cap 4.** B1 and B5 are intent-declared; the computed range is
  {2, 3, 4}. This is what makes the 5.1 benchmark satisfiable (precons expected ~2,
  5.9 tolerance `[expected, expected+1]`) — a floor-1 baseline would fail every precon.
  Decide-once, documented, provisional.
- **`matched_combos` is an input, not a call.** 5.6's `match_combos` needs `commanders`,
  which only the edge resolves (AD-13). Taking bucketed records keeps this module free of
  commander knowledge and gives 5.9 one composition point. Only `included` records raise
  the floor; `almost_included` may inform `combo_potential` (partial credit) but never the
  floor — you cannot trigger a Bracket rule with a card you don't play.
- **Resilience is a documented proxy.** No protection/recursion classifier category exists
  (5.3 shipped 9 tokens; adding one is an AD-10 vocabulary change owned by 5.9's tuning
  pass). v1 resilience = blend of win-route redundancy (how many of the three `WINCON_*`
  categories are non-zero), draw-engine access (rebuild after a wipe), and instant-speed
  interaction share (holding up answers). Say exactly this in the PUBLIC docstring (the
  5.5 review lesson: surprising consequences belong in public docs, not inline comments).
- **Tutors: candidacy and consistency only, never the floor.** WotC removed tutor
  restrictions from Brackets (Oct 2025); `classifiers.py:41-43` already carries the
  warning addressed to this story. Honor it.
- **One `classify_deck` per entry point.** The logged 5.3 deferred-work item is explicit
  that 5.7 is the first multi-signal consumer: read `MASS_LAND_DENIAL` / `EXTRA_TURN` /
  `TUTOR` / wincon buckets from ONE `classify_deck` mapping instead of calling
  `detect_mass_land_denial` + `detect_extra_turn_cards` (each re-classifies the deck).
  `bracket_floor` and `dimension_vector` may each make their own single call (pure module,
  no shared cache) — just never two calls inside one function.
- **Chain refinement = count >= 2 (provisional).** 5.3's `EXTRA_TURN` is presence-only and
  its docstring defers "chain refinement" here. v1 proxy: a deck with two or more
  extra-turn effects (quantity-aware) is chain-capable → floor 4; document that a single
  Time Warp is a B2/B3-legal quantity per WotC's "low quantities, not chained" language.
- **Rounding: one shared helper.** `_to_score(x: float) -> int` = clamp to `[0.0, 100.0]`
  then `int(x + 0.5)`. Every dimension goes through it. Document why not `round()`
  (banker's rounding at .5 is a reviewer surprise; determinism holds either way, clarity
  wins).
- **Determinism traps:** iterate `WUBRG`/`CATEGORIES`/`DIMENSIONS` fixed orders; sort any
  name/id tuple you store (ascending bytewise); no dict-iteration-order dependence on
  inputs; all floats reduced to ints through `_to_score`; no `set` in any stored field.
- **Why the directional tests are SWAP-based:** under raw "add a card", hypergeometric
  denominators grow (every opener probability dips slightly) and `avgMV` shifts — so
  "adding a tutor never lowers consistency" can fail once a bonus term saturates, and
  "adding ramp never lowers speed" fails for an expensive ramp spell raising `avgMV`.
  Swapping a vanilla filler card (deck size constant) isolates the intended direction.
  The literal "adding X" monotonicity **properties** are Story 5.9's (epics 2.9), asserted
  on benchmark-scale fixtures where the calibrated curves must absorb dilution — if your
  curve can't survive a single-card add without inverting, note it in the code-site
  docstring for 5.9's tuning pass.

### Recommended v1 mapping models (guidance — document at code site, 5.9 owns the numbers)

All constants `Final` with source comments, marked provisional. Hard requirements per AC2;
monotone directions per AC8. Suggested shapes:

- **speed** — estimate a win turn, then map inversely onto the profile band:
  `est = mid(win_turn_band) + (avgMV − 3.0) − min(2.0, ramp_count / 5.0)` (Commander: ~5
  ramp ≈ one turn faster; lower curve = faster), then
  `est = min(est, earliest included infinite combo turn + 1.0)` (combo shortcut; skip when
  none), then linear map `[hi+2 → 0, lo−2 → 100]` through `_to_score`. Monotone: ramp ↑ →
  score never ↓; avgMV ↑ → never ↑; earlier combo → never ↓.
- **consistency** — weighted blend of probabilities (each already `[0,1]`):
  `0.35·opener(CARD_DRAW) + 0.25·opener(RAMP) + 0.25·max(opener(WINCON_*)) +
  0.15·land_access_by_turn(4)` scaled ×100, plus `min(tutor_count, 6) · 2.0` bonus, clamp.
  `opener(X)` = `redundancy_signals` opener probability. Tutor bonus is additive-only so
  "adding a tutor never lowers consistency" (a 5.9 monotonicity property) holds by
  construction.
- **resilience** (documented proxy — see load-bearing decisions):
  `40·(win_route_count / 3) + 30·instant_speed_ratio + 30·min(draw_count / baseline, 1.0)`
  where `win_route_count` = number of non-zero `WINCON_*` categories, baseline = the 5.5
  `STRUCTURAL_GAP_BASELINES[formula][CARD_DRAW]` (import, don't restate).
- **interaction** — `70·min(count / target, 1.0) + 20·instant_speed_ratio + 10·cheap_share`
  where `target` = `Final` dict keyed by `KarstenFormula` (`commander: 10` — Command Zone
  template; `sixty_card: 8`), `cheap_share` = fraction of interaction quantity at
  `cmc <= 2` (from `interaction_signals.cmc_distribution`). Zero interaction → 0.
- **mana_efficiency** — start at 100, subtract penalties:
  `6.0·max(0, |karsten delta| − KARSTEN_TOLERANCE_LANDS)` + `3.0·total pip deficit`, clamp.
  Reuses the 5.4 tolerance constant (import it, don't restate 2.0).
- **card_advantage** — `80·min(draw_count / target, 1.0) + min(tutor_count, 6) · 3.0`,
  `target` keyed by formula (`commander: 10`, `sixty_card: 6`), clamp.
- **combo_potential** — 0 when no contributing records. Credit table (per record, by
  `combo_type`): included `TWO_CARD_INFINITE` 50, `MULTI_CARD_INFINITE` 30, `NON_INFINITE`
  15; `almost_included` = half its included credit; `bucket=None` = 0. Earliness bonus per
  included infinite record: `+ max(0, (10 − earliest_turn) · 2)`. Sum, clamp at 100.
  Included ≥ almost_included for the same record and earlier-never-lowers hold by
  construction.

Worked floor examples to pin in tests: 3 GC + no triggers/combos → 3; 1 GC + included
late two-card infinite → 3 (both gates say 3); 0 GC + included `RUTHLESS` non-infinite →
4 (tag map); 0 GC + `almost_included` `RUTHLESS` → 2.

### Previous-story intelligence (5.6, just completed)

- **Review findings to apply proactively here** (each was a review round-trip):
  1. **Double-enforcement bug class:** 5.6's commander gate both gated AND counted the
     same piece as a shortfall, silently demoting the most important combo class. Audit
     every AC4 gate for the same shape — e.g. don't let `unknown_count` leak into
     `known_count` math, don't count an included combo's tag contribution twice.
  2. **Normalization asymmetry:** commanders skipped the DFC front-face split that deck
     cards got. Here: any name list you store must go through ONE sorting/uniquing path.
  3. **Cheap defense-in-depth guards get accepted** (`min_length=1` on `cards`): favor a
     guard where malformed input could silently masquerade as signal (e.g. treat
     `bucket=None` explicitly rather than falling through an `if/elif`).
- **Standing lessons still in force:** Literal-keyed dicts from the start (5.4 — your
  formula-keyed targets); sideboard-row pin per public function (5.4/5.5); both/all enum
  branches exercised (5.4); shared factories in `tests/fixtures/assessment.py`, never a
  second copy (G1); verify-by-shape for provisional values, exact pins only for derived
  math (5.1→5.6); assert messages naming the signal or drop the claim (5.5); keep AC
  prose and pinned test values in sync — amend the story file if you correct a number
  mid-implementation (5.5).
- **Deferred-work items that brush this story:** the `classify_deck` double-call item
  (resolved by the AC2/load-bearing "one call" rule — note it resolved in your completion
  notes); `probability_at_least` [0,1] property test remains optional hardening (you
  consume `redundancy_signals`, not the primitive directly); `classify_card` land-typed
  `INTERACTION` false positives are pre-existing 5.3 behavior — do NOT special-case lands
  in your interaction curve (5.9 calibration owns pattern tuning).
- **Fast-suite baseline: 925 passed** (measured at story creation, 5.6 review patches in
  tree).

### Testing standards

- pytest config in `pyproject.toml`: `asyncio_mode="auto"`, `--strict-markers`,
  `--tb=short`; these tests are synchronous, no markers, in the `-m "not integration"`
  fast subset.
- Flat placement `tests/unit/logic/test_assessment_dimensions.py` beside the five existing
  assessment test modules (the `tests/unit/logic/assessment/` subdir move remains
  deferred; if you do it, move all six in one commit).
- Factories: `make_card(game_changer=True)` etc. — `make_card`'s defaults omit
  `game_changer`, so it is `None` (the unknown state) unless a test sets it; set it
  EXPLICITLY in every GC test so intent is visible. `make_combo_record(bucket="included")`
  for matched inputs.
- `typing.get_args` / `dataclasses.fields` give you `DIMENSIONS`-totality assertions
  without restating the vocabulary.
- `tests.*` is mypy-exempt but write full hints anyway.

## Project Structure Notes

**New/changed files:**

```text
src/
  logic/
    assessment/
      dimensions.py         # NEW: GameChangerSignal, BracketFloorSignal + bracket_floor
                            #      (incl. cedh_candidate), DimensionVector + dimension_vector,
                            #      gate/curve constants (Final, provisional)
      profiles.py           # MODIFIED: + karsten_formula field; both versions bumped (AC6)
      __init__.py           # MODIFIED: additive re-exports
tests/
  unit/
    logic/
      test_assessment_dimensions.py   # NEW: AC8 matrix
      test_assessment_profiles.py     # MODIFIED: additive new-field + version checks
plugin/                     # REGENERATED mirror (hook rebuilds; verify dimensions.py AND
                            # profiles.py mirror paths are staged)
```

- No changes to `src/logic/__init__.py`, any schema/repository/model/importer, `scripts/`,
  `src/mcp_server`, or the benchmark fixtures. No DB objects.
- Downstream consumers to keep in mind while naming things: 5.8 (aggregates
  `DimensionVector` with `profile.weights`; adds the tier label + confidence vocabulary),
  5.9 (`score()` composes matcher → your functions → aggregate; benchmark + monotonicity
  properties), 7.3 (serializes the vector keys, `flags.game_changers`,
  `flags.mass_land_denial` / `extra_turn_chains` / `cedh_candidate` from your signal
  fields).

## References

- [Source: _bmad-output/planning-artifacts/epics-deck-power-assessment.md#Story 2.7] — the
  binding ACs (7 int dimensions always present; floor from GC + triggers + combos; AD-4
  read side; cEDH candidacy only).
- [Source: epics-deck-power-assessment.md#Additional Requirements — Implementation
  constants (addendum §C)] — Bracket gating (0 GC → B1–2; 1–3 → B3; 4+ GC / mass land
  denial / early two-card infinite → B4; cEDH B5 = candidacy flag only).
- [Source: _bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-11/ARCHITECTURE-SPINE.md#AD-2, #AD-3, #AD-4, #AD-7, #AD-11; #Deferred] —
  purity, profile-owned mapping parameters + bump rule, never-coalesce-None, fixed
  7-key vector, tag map; mapping curves are implementation-owned/hand-tuned.
- [Source: docs/deck-assess.md:119] — tutors removed from Bracket gating (Oct 2025);
  [:123-125] — Command Zone template / 8×8 baselines; [:186] — cEDH candidacy signals
  (dense fast mana + tutors + compact combo); [:264-271] — the dimensions output sketch;
  [:328] — Bracket gating quick-reference.
- [Source: src/logic/assessment/profiles.py] — `DIMENSIONS` (the canonical key-set home
  this story's vector must mirror), `win_turn_band`, the additive-extension + bump-rule
  docstring contract.
- [Source: src/logic/assessment/classifiers.py:41-43,53-55] — the tutor floor warning
  addressed to 5.7 and the "chain refinement is Story 5.7's" deferral;
  [src/logic/assessment/consistency.py]; [src/logic/assessment/mana_base.py];
  [src/logic/assessment/combos.py] — the complete signal inventory (see the table).
- [Source: tests/fixtures/benchmark_decks.py docstring] — 5.9's tolerance
  (`[expected, expected+1]` for precons; any cEDH floor >= 4; never assert Bracket 5) —
  the constraint behind `BASELINE_BRACKET_FLOOR = 2`.
- [Source: _bmad-output/implementation-artifacts/deferred-work.md#Deferred from: code
  review of story-5.3] — the `classify_deck` double-call item this story resolves;
  [#story-5.5] — land-typed `INTERACTION` false positive (pre-existing, do not
  special-case here).
- [Source: _bmad-output/implementation-artifacts/5-6-combo-record-combo-bracket-mapping.md#Review
  Findings, #Dev Notes] — the double-enforcement / normalization-asymmetry /
  defense-in-depth lessons; the FR15 feed contract (`bucket == "included"` and
  `combo_type == two_card_infinite`).
- [Source: _bmad-output/project-context.md#Framework rules, #Testing Rules, #Code
  Quality] — layering, mypy --strict / ruff / Google docstrings / pytest gates.

## Dev Agent Record

### Agent Model Used

Claude Fable 5 (claude-fable-5) via Claude Code

### Debug Log References

- Task 0: `05662f1` found already committed at dev start (the 5.6 review-patch commit the
  story expected to land) — recorded as `baseline_commit`; fast suite confirmed at
  925 passed before any 5.7 code.
- Red-green: profile tests written first (2 failed as expected), then the profile
  extension; the full AC8 test matrix (64 tests) written against the not-yet-existing
  `dimensions.py` (collection ImportError = red), then the module implemented to green.
- Final gates: `ruff check` clean, `ruff format` applied, `mypy --strict` clean
  (62 files), fast suite 991 passed / 5 deselected.

### Completion Notes List

- **Implemented** `src/logic/assessment/dimensions.py`: `GameChangerSignal` +
  `game_changer_signal` (AD-4 three-state, identity checks, no bool coercion),
  `BracketFloorSignal` + `bracket_floor` (baseline 2, cap 4; GC gates 1–3→3 / 4+→4; MLD→4;
  extra-turn chain ≥2→4; included-only combo raises with early-two-card-infinite→4,
  other included infinite→3, `BRACKET_TAG_TO_BRACKET` contribution; cEDH candidacy folded
  in), and `DimensionVector` + `dimension_vector` (frozen slots, exactly the `DIMENSIONS`
  key set in order, all curves through the one `_to_score` round-half-up policy).
- **Profile extension (AC6):** `FormatProfile.karsten_formula` added; `commander-v2` /
  `standard-v2` version bumps in the same edit; no other profile field touched.
- **Resolved the 5.3 deferred-work item** (classify_deck double-call): both entry points
  make exactly ONE `classify_deck` + ONE `compute_curve` call and feed all gates/curves
  from locals; opener/land-access probabilities are computed via `probability_at_least`
  directly from those locals instead of `redundancy_signals`/`land_access_by_turn`
  (which re-classify/re-curve internally) — documented in the module docstring.
- **Documented deviation from the Dev-Notes interaction model:** the recommended
  `20·instant_speed_ratio + 10·cheap_share` blend inverts under the AC8 swap direction
  (one sorcery-speed interaction swap dilutes the instant share faster than the count
  term compensates — worked edge: 1 instant answer + 1 sorcery answer). v1 uses
  count-based sub-terms against per-formula targets (`_INSTANT_INTERACTION_TARGETS` /
  `_CHEAP_INTERACTION_TARGETS`), monotone under any interaction swap by construction;
  rationale documented at the constant site for 5.9's tuning pass. A regression test
  pins the dilution edge.
- **Speed curve edge decided:** a deck with zero spells maps to `speed = 0` (cannot win
  at all) — this also makes the empty-deck vector all-zero rather than an absurd
  high-speed read from `avgMV = 0.0`; documented at the code site.
- **Resilience proxy status** documented in the PUBLIC `dimension_vector` docstring
  (win-route redundancy + draw density + instant-speed share; explicitly does NOT
  measure hexproof/counterspell protection or recursion) per the 5.5 review lesson.
- **Tutors never feed the floor** (Oct 2025 WotC change): honored — tutor count is read
  only by the cEDH candidacy rule and the consistency/card_advantage bonuses; the tutor
  bonuses are additive-only so the 5.9 "adding a tutor never lowers" property holds by
  construction.
- **Tests:** 64 new offline tests (AC8 matrix: vector shape both profiles, GC three-state,
  every floor gate branch incl. the worked Dev-Notes examples, AD-4 unknowns pin, cEDH
  full fixture + each missing leg, SWAP-based monotone directions, bucket=None
  contributes nothing, determinism/order-independence/no-mutation, sideboard pin);
  2 additive profile tests. All assertions carry failure messages naming the
  dimension/gate/signal. Suite: 925 → 991 passed, zero regressions.

### File List

- `src/logic/assessment/dimensions.py` (new)
- `src/logic/assessment/profiles.py` (modified — karsten_formula field, v2 bumps)
- `src/logic/assessment/__init__.py` (modified — additive re-exports, sorted)
- `tests/unit/logic/test_assessment_dimensions.py` (new)
- `tests/unit/logic/test_assessment_profiles.py` (modified — additive new-field/version tests)
- `plugin/server/src/logic/assessment/dimensions.py` (regenerated mirror)
- `plugin/server/src/logic/assessment/profiles.py` (regenerated mirror)
- `plugin/server/src/logic/assessment/__init__.py` (regenerated mirror)
- `_bmad-output/implementation-artifacts/5-7-dimension-vector-commander-bracket-floor-cedh-candidacy.md` (this story file)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (status transitions)

## Change Log

- 2026-07-14: Story 5.7 implemented — dimensions module (GC signal, Bracket floor +
  cEDH candidacy, 7-dimension vector), profile karsten_formula extension with v2 bumps,
  additive exports, 66 new tests (fast suite 991 passed). Status → review.

- 2026-07-14: Story 5.7 created (ready-for-dev) — ultimate context engine analysis
  completed: comprehensive developer guide covering the signal-inventory table (5.3–5.6
  public APIs), the baseline-floor-2 / cap-4 decision and its benchmark constraint, the
  matched-combos-as-input seam, the resilience proxy gap, the profile `karsten_formula`
  extension + version bumps, recommended v1 mapping models with monotone directions, and
  the uncommitted-5.6-review-patch baseline (Task 0).
