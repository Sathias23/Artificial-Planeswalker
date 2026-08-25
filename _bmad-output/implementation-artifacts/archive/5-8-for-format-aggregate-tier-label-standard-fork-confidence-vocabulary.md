---
baseline_commit: fde9d8c # "story 5.7 review -> done" docstring-patch commit (tree clean at story creation)
---

# Story 5.8: For-format aggregate, tier label, Standard fork & confidence vocabulary

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

> **Sprint/feature numbering:** this is sprint key
> `5-8-for-format-aggregate-tier-label-standard-fork-confidence-vocabulary` (`epic-5`), which is
> **feature Epic 2, Story 2.8** in `_bmad-output/planning-artifacts/epics-deck-power-assessment.md`.
> Sprint Epic 5 = feature Epic 2 "Deterministic scoring core".

## Story

As the scorer,
I want the aggregate score, human label, Standard path, and confidence vocabulary,
so that every deck gets a labeled score with honest confidence tokens.

## Context & why this story exists

Story 5.7 shipped the 7-dimension integer vector; this story is its first consumer. It
collapses the vector into the **for-format 0–100 score** (FR19) using the profile weights
that have sat unread in `FormatProfile.weights` since 5.2, attaches the **descriptive tier
label** so no score is ever a bare number (FR24), proves the whole path works unchanged
under the **Standard `heuristic_only` profile** (FR20), and defines the **closed AD-6
confidence-reason vocabulary** the edge will emit from (FR21 vocabulary half). Three
things hang off it:

- **FR19 aggregate** — a weighted sum of the `DimensionVector` over the profile's
  `DimensionWeights`, produced as **integer 0–100** (AD-8 discipline starts in the core).
  Deliberately NO 1–10 projection and no absolute cross-format score — the for-format
  0–100 is the diff basis.
- **FR24 label** — every for-format score carries a tier word (Unfocused / Focused /
  Tuned / High-Power / Competitive) from **profile-owned thresholds** (AD-3), so the
  human-facing layer is honest about imprecision (docs/deck-assess.md Option F).
- **5.9/Epic 7 contract** — 5.9's `score()` composes matcher → 5.7 vector → this
  aggregate + label and validates tier bands against the benchmark's Standard anchors;
  Epic 7 serializes `score` + `label` (7.3) and assembles `confidence{level, reasons[]}`
  from the token vocabulary defined here (7.2 / feature 4.2). What you name here is what
  they consume.

Like 5.3–5.7: threshold and weight **values** are provisional v1 numbers that Story 5.9
hand-tunes against the benchmark (NFR8) — tests verify shape, domains, totality, and
monotone directions, never exact numbers. The label **vocabulary** and the confidence
**token set**, by contrast, are closed enums on the AD-7/AD-8 diff surface — stable, not
provisional.

## Acceptance Criteria

1. **One new pure module owns this story's surface.** Given the one-module-per-story
   house pattern (5.3 `classifiers`, 5.4 `mana_base`, 5.5 `consistency`, 5.6 `combos`,
   5.7 `dimensions`), when the story is done, then `src/logic/assessment/aggregate.py`
   exists and contains ALL of this story's public functions and vocabulary constants
   (AC2's `aggregate_score`, AC3's `tier_label`, AC6's confidence vocabulary) — with the
   ONE sanctioned exception that the `TierLabel`/`TIER_LABELS` canonical vocabulary
   lives in `profiles.py` beside `DIMENSIONS` (AC3's one-canonical-home rule, since
   `FormatProfile.tier_thresholds` references it); it is pure (no
   network/DB/clock/random/logging — AD-2) and imports
   only stdlib plus `src.logic.assessment.profiles` and `src.logic.assessment.dimensions`
   (for `DimensionVector` — it consumes the VECTOR, never raw signals): it must NOT
   import `classifiers`, `mana_base`, `consistency`, `combos`, any `src.data.*`,
   `src/search`, `src/mcp_server`, `src/logic/mana_curve`, or `src/logic/synergy`. All
   new public names are exported additively from `src/logic/assessment/__init__.py`
   (`__all__` kept bytewise-sorted). [epics 2.8; AD-2; project-context#Framework rules]

2. **The for-format aggregate: weighted, integer, format-blind.** Given the vector +
   profile weights, when `aggregate_score(vector, *, profile) -> int` is defined, then:
   - it computes the weighted sum by iterating `profiles.DIMENSIONS` in its **fixed
     canonical order**, reading each dimension via `getattr` from BOTH the
     `DimensionVector` and `profile.weights` (their field sets are already pinned equal
     to `DIMENSIONS` by existing tests — mypy + those pins make a fork impossible);
   - the float sum passes through the **same decide-once rounding policy as 5.7**: clamp
     to `[0.0, 100.0]` then round half-up `int(x + 0.5)` — restated as a module-local
     `_to_score` with a docstring cross-referencing `dimensions._to_score` (restated, not
     imported: the sibling helper is private and this story's diff stays additive-only;
     if a third copy ever threatens, hoisting is 5.9's call);
   - the clamp is documented as **float-dust defense only**: weights are non-negative and
     sum to 1.0 (pinned by existing profile tests), so the true range is already
     `[0, 100]` — an all-zero vector yields exactly `0` and an all-100 vector exactly
     `100` under both shipped profiles;
   - it contains **no `rubric` branch and reads no profile field except `weights`** —
     the Commander and Standard paths are the same code; determinism: identical inputs
     yield identical output;
   - **no 1–10 projection, no absolute cross-format score** exists anywhere in the
     module (FR19; the legacy scale is deliberately not emitted). [epics 2.8; FR19;
     AD-3; AD-8; NFR8]

3. **The tier label: closed vocabulary, profile-owned thresholds, total over the
   domain.** Given FR24, when the label surface is defined, then:
   - `profiles.py` gains the canonical closed vocabulary next to `DIMENSIONS` (the
     one-canonical-home precedent): `TierLabel` =
     `Literal["Unfocused", "Focused", "Tuned", "High-Power", "Competitive"]` and
     `TIER_LABELS: Final[tuple[TierLabel, ...]]` in that fixed **ascending-power order**
     (exactly the FR24 wording, hyphen included). The vocabulary is a CLOSED set on the
     AD-7 diff surface — renaming a label is a breaking schema change, not a 5.9 tuning
     knob;
   - `aggregate.tier_label(score, *, profile) -> TierLabel` maps a score to the
     **highest band whose inclusive lower cut ≤ score** (decide-once boundary policy,
     documented at the code site): band 1 (`Unfocused`) implicitly starts at 0; the
     profile's four thresholds are the lower cuts of bands 2–5. The function is **total**:
     every `int` in `[0, 100]` maps to a label (0 → first, 100 → last; a defensive
     out-of-domain input degrades to the nearest band, never raises);
   - label monotonicity holds by construction: a higher score never maps to a
     lower-power label. [epics 2.8; FR24; AD-3; AD-7; docs/deck-assess.md:94-98]

4. **`FormatProfile` extends additively; versions bump; the 5.7 version pin is
   amended.** Given AD-3's bump rule, when the profile is touched, then:
   - `FormatProfile` gains `tier_thresholds: tuple[int, int, int, int]` — four strictly
     ascending lower-cut points in `(0, 100]`, one per band 2–5, documented as the FR24
     mapping parameter. Recommended provisional v1 values for BOTH profiles:
     `(20, 40, 60, 80)` (even quintiles — an honest zero-information prior; 5.9 anchors
     them per format against the benchmark, which is exactly why they are per-profile:
     the 5.7-deferred "Standard vs Commander vectors are not on a comparable scale"
     item is absorbed by per-format threshold tuning, not by cross-format math);
   - **both** `format_profile_version` strings bump in the same edit
     (`commander-v2 → commander-v3`, `standard-v2 → standard-v3`);
   - `tests/unit/logic/test_assessment_profiles.py` is extended additively (thresholds
     shape/domain/ascending per format; `TIER_LABELS` totality vs `TierLabel` via
     `typing.get_args`), and the existing
     `test_versions_bumped_for_karsten_formula_addition` exact-pin test is **amended to
     the v3 strings** — the ONE sanctioned non-additive test edit (the 5.5 lesson: pinned
     values and prose move together);
   - NO other profile value changes — weights, bands, rubric, flags stay untouched
     (5.9 owns weight tuning). [epics 2.8; AD-3; FR4; profiles.py docstring]

5. **The Standard fork is the absence of a fork — proven, not built.** Given FR20
   (rubric `heuristic_only`: curve / interaction / Karsten-60 / combos in, no Bracket,
   no percentile), when the story is done, then:
   - those FR20 inputs already flow through the 5.7 vector under
     `STANDARD_PROFILE.karsten_formula == "sixty_card"` — this story adds **no
     Standard-specific math**; `aggregate_score` + `tier_label` run identically under
     both profiles (AC2's no-rubric-branch rule);
   - a **rubric-swap invariance test** pins it: `dataclasses.replace(profile,
     rubric=<other>)` produces bytewise-identical `aggregate_score` and `tier_label`
     outputs (the aggregate reads `weights`; the label reads `tier_thresholds`; neither
     may read `rubric`);
   - the composition contract for 5.9/Epic 7 is documented in the module docstring:
     under `heuristic_only` the composer never consults `bracket_floor` and the edge
     emits `bracket: null` (AD-7 fixed shape) — the fork lives in what is COMPOSED,
     never inside this module; no percentile and no meta-tier exist anywhere (FR20).
   [epics 2.8; FR20; AD-7]

6. **The AD-6 confidence vocabulary: closed, sorted, count-free, clock-free — tokens
   only, no policy.** Given FR21's vocabulary half, when defined in `aggregate.py`, then:
   - four `Final` token constants exist — `CARDS_UNRESOLVED = "cards_unresolved"`,
     `COMBO_DATA_UNAVAILABLE = "combo_data_unavailable"`,
     `COMMANDER_UNIDENTIFIED = "commander_unidentified"`,
     `GAME_CHANGER_DATA_UNAVAILABLE = "game_changer_data_unavailable"` — plus
     `CONFIDENCE_REASON_TOKENS: Final[tuple[str, ...]]` containing **exactly** those four,
     defined already **bytewise-sorted** so documented order and AD-8 emission order
     coincide (the `STRUCTURAL_GAP_TOKENS` precedent; sorted order is
     `cards_unresolved, combo_data_unavailable, commander_unidentified,
     game_changer_data_unavailable`);
   - `ConfidenceLevel` = `Literal["low", "medium", "high"]` and
     `CONFIDENCE_LEVELS: Final[tuple[ConfidenceLevel, ...]] = ("low", "medium", "high")`
     — documented as **semantic ascending order, not an AD-8 emission list** (the level
     is a scalar; only `reasons[]` lists get bytewise-sorted at the edge);
   - tokens NEVER embed counts or phrasing (all snake_case, no digits — counts live in
     separate structured fields, phrasing only in `summary`); **no clock-derived token
     exists** (the closed four-token set pins this — a "staleness" token cannot be
     added without failing the exact-set test); the commander profile's
     multiplayer-variance caveat is documented as `summary` text driven by
     `multiplayer_variance_caveat`, NEVER a member of this enum;
   - **no assignment policy ships**: no function maps degradations to a level or builds
     a `reasons[]` — that is the edge's job (Epic 7 / feature Story 4.2). This story is
     vocabulary only, exactly like 5.5's `STRUCTURAL_GAP_TOKENS`. [epics 2.8; FR21;
     AD-6; AD-8; ARCHITECTURE-SPINE#AD-6]

7. **Scope guard — vector in, labeled score + vocabulary out, nothing more.** Given the
   story split, when reviewed, then this story ships **no** `score()` entry point, no
   benchmark fixture edits or Standard anchors (5.9 per the 2026-07-12 amendment), no
   monotonicity property suite (5.9), no serialization or `AssessDeckPowerResult` /
   `data_vintage` shape (Epic 7, AD-7/AD-8), no confidence level-assignment or
   degradation ladder (Epic 7 / 4.2), no commander resolution, and no edits to
   `classifiers.py`, `mana_base.py`, `consistency.py`, `combos.py`, `dimensions.py`,
   `synergy.py`, any `src/data` / `src/mcp_server` / `scripts/` file, or the benchmark
   fixtures. The ONLY modified existing sources are `profiles.py` (AC3 vocabulary + AC4
   field/bumps), `src/logic/assessment/__init__.py` (additive re-exports), and
   `tests/unit/logic/test_assessment_profiles.py` (additive + the one sanctioned v3
   pin amendment). If a function needs `DeckCard`s, `ComboRecord`s, a DB, the clock, or
   the network — wrong story. [epics 2.8; AD-2; FR19/FR20/FR21 split notes]

8. **Offline unit tests prove the math and the vocabulary.** Given the project's testing
   rules, when `tests/unit/logic/test_assessment_aggregate.py` runs (no `integration`
   marker, no DB, no card factories needed — `DimensionVector` and `FormatProfile` are
   directly constructible), it verifies at minimum:
   - **aggregate domain & anchors:** `int` in `[0, 100]` for arbitrary valid vectors
     under both shipped profiles; all-zero vector → exactly `0`; all-100 vector →
     exactly `100` (both profiles — the float-dust clamp proof);
   - **rounding policy:** a synthetic profile whose weights produce a `x.5` sum rounds
     half-UP (e.g. weights `0.5/0.5/0/0/0/0/0` with vector values summing to `.5` →
     documents why not `round()`);
   - **monotone:** for EVERY dimension in `DIMENSIONS`, raising that dimension alone
     (others held equal) never lowers the aggregate, under both shipped profiles;
   - **rubric-swap invariance (AC5):** `dataclasses.replace(profile, rubric=…)` leaves
     both `aggregate_score` and `tier_label` outputs identical;
   - **label totality & boundaries:** every `int` score `0..100` maps to a member of
     `TIER_LABELS` under both profiles; each threshold's exact value maps to its band
     (inclusive lower cut) and `threshold - 1` maps to the band below; `0` → first
     label, `100` → last label; higher score never maps to a lower band index;
   - **vocabulary pins:** `CONFIDENCE_REASON_TOKENS` equals exactly the four AD-6
     tokens, is bytewise-sorted as defined, all snake_case with no digits;
     `typing.get_args(ConfidenceLevel)` equals `("low", "medium", "high")`;
     `TIER_LABELS` length 5, matches `typing.get_args(TierLabel)` order;
   - **profile additions (AC4):** `tier_thresholds` per format — four ints, strictly
     ascending, each in `(0, 100]`; both version strings read `commander-v3` /
     `standard-v3`;
   - **determinism:** two calls on equal inputs → equal results; inputs not mutated
     (frozen dataclasses make this cheap — assert equality of repeated calls suffices);
   - assertions carry failure messages naming the function/band/token **or** the claim
     is dropped (the 5.5 review lesson).
   Runs green under `uv run pytest -m "not integration"` (baseline at story creation:
   **991 passed, 5 deselected**, measured on the clean `fde9d8c` tree).
   [project-context#Testing Rules; 5-5/5-7 lessons]

9. **Quality gates pass — including the `src/`-touch plugin mirror.** Given this story
   edits files under `src/`, when committed, then `mypy --strict` passes (full hints,
   Google docstrings on module + every public name), `ruff check` + `ruff format` are
   clean, and the regenerated `plugin/` mirror is staged in the same commit (the
   pre-commit hook is installed in this checkout and rebuilds it — verify the
   `plugin/server/src/logic/assessment/` mirror diffs for the new `aggregate.py` AND
   the modified `profiles.py` / `__init__.py` are staged; never `--no-verify`).
   [project-context#Code Quality; epic-4 retro]

## Tasks / Subtasks

- [x] **Task 0 — Confirm clean baseline** (AC: —)
  - [x] Unlike 5.6/5.7, the tree is CLEAN at story creation: the 5.7 review patches are
        already committed as `fde9d8c` ("fix: tighten dimensions docstrings (story 5.7
        review -> done)"). Verify `git status` is clean and `uv run pytest -m "not
        integration"` reports **991 passed** before writing any 5.8 code.
- [x] **Task 1 — Profile extension + label vocabulary** (AC: 3, 4)
  - [x] Add `TierLabel` + `TIER_LABELS` to `profiles.py` beside `DIMENSIONS`; add
        `tier_thresholds` to `FormatProfile` with the provisional `(20, 40, 60, 80)`
        values + rationale comments; bump both versions to v3 in the same edit.
  - [x] Extend `test_assessment_profiles.py` additively (thresholds shape/domain/
        ascending, labels totality) and amend the v2 version-pin test to v3.
- [x] **Task 2 — Module scaffold + aggregate** (AC: 1, 2)
  - [x] `src/logic/assessment/aggregate.py` module docstring: FR19/FR24/FR20/FR21-
        vocabulary seam, consumes the 5.7 vector + profile (never raw signals),
        decide-once policies (rounding restated, inclusive-lower-cut labels, no rubric
        branch, closed vocabularies), the 5.9/Epic-7 composition contract (heuristic_only
        never consults `bracket_floor`; edge emits `bracket: null`).
  - [x] Local `_to_score` (clamp + half-up, cross-referencing `dimensions._to_score`)
        and `aggregate_score` iterating `DIMENSIONS` in fixed order.
- [x] **Task 3 — Tier label** (AC: 3)
  - [x] `tier_label(score, *, profile) -> TierLabel` — inclusive-lower-cut band walk,
        total over the domain, documented boundary policy.
- [x] **Task 4 — Confidence vocabulary** (AC: 6)
  - [x] Four token constants + `CONFIDENCE_REASON_TOKENS` (defined bytewise-sorted) +
        `ConfidenceLevel` / `CONFIDENCE_LEVELS`, with the count-free/clock-free/
        caveat-is-not-a-reason documentation. No assignment policy.
- [x] **Task 5 — Package exports** (AC: 1)
  - [x] Extend `src/logic/assessment/__init__.py` `__all__` additively (bytewise-sorted).
- [x] **Task 6 — Offline unit tests** (AC: 8)
  - [x] `tests/unit/logic/test_assessment_aggregate.py` covering the full AC8 matrix.
- [x] **Task 7 — Quality gates + plugin mirror** (AC: 9)
  - [x] `uv run ruff check . --fix && uv run ruff format .`
  - [x] `uv run mypy src/` (strict) clean.
  - [x] `uv run pytest -m "not integration"` green (baseline: **991 passed**).
  - [x] Commit with the regenerated `plugin/` mirror staged (verify `aggregate.py`,
        `profiles.py`, `__init__.py` mirror paths). Never `--no-verify`.

## Dev Notes

### What this story is — and is NOT

- **IS:** one new pure module `src/logic/assessment/aggregate.py` (`aggregate_score`,
  `tier_label`, confidence vocabulary constants); the `TierLabel`/`TIER_LABELS`
  vocabulary + `tier_thresholds` field in `profiles.py` with v3 bumps; exports; offline
  tests. It is the SMALLEST Epic-5 story by construction — no deck cards, no combos, no
  probability math. Do not let it grow.
- **IS NOT:** the `score()` entry point or benchmark validation (5.9), the Standard
  benchmark anchors (5.9 per the 2026-07-12 amendment), monotonicity property suites on
  deck fixtures (5.9), weight tuning (5.9), the confidence level-assignment policy /
  degradation ladder / `reasons[]` emission (Epic 7 / feature 4.2), `bracket: null`
  emission or any serialization (Epic 7, AD-7/AD-8), commander resolution (Epic 7 edge).
  If a function needs `DeckCard`, `ComboRecord`, profile `rubric`, a DB, the clock, or
  the network — wrong story.

### Baseline note (story-creation snapshot, 2026-07-14)

The working tree is **clean** at `fde9d8c` — the 5.7 review-patch commit is already
landed (no Task-0 commit debt this time, unlike 5.6/5.7). Fast-suite baseline
**991 passed, 5 deselected** was measured on this tree at story creation. The pre-commit
hook (ruff + mypy + plugin rebuild) IS installed in this checkout.

### The inventory you build from (all already shipped — reinvent nothing)

| Need | Use | Notes |
| --- | --- | --- |
| the 7 integer dimensions | `dimensions.DimensionVector` | frozen slots; fields == `DIMENSIONS` (pinned by 5.7 tests) |
| aggregate weights | `profile.weights` (`DimensionWeights`) | fields == `DIMENSIONS` (pinned); non-negative, sum 1.0 (pinned) |
| the canonical key order | `profiles.DIMENSIONS` | iterate THIS, fixed order — never `dataclasses.fields` order assumptions |
| rounding policy | restate `dimensions._to_score` locally | clamp `[0,100]` then `int(x + 0.5)`; document the cross-reference |
| closed-token precedent | `consistency.STRUCTURAL_GAP_TOKENS` | tokens as `Final` str constants + a bytewise-sorted tuple |
| label vocabulary home | `profiles.TIER_LABELS` (NEW, this story) | beside `DIMENSIONS` — the one-canonical-home precedent |
| tier cut points | `profile.tier_thresholds` (NEW, this story) | four ascending lower cuts for bands 2–5 |

`aggregate_score`'s whole body is ~4 lines:
`_to_score(sum(getattr(vector, d) * getattr(profile.weights, d) for d in DIMENSIONS))`.
Resist decorating it.

### Load-bearing decisions (read before writing code)

- **Restate `_to_score`, don't import the private.** `dimensions._to_score` is private
  by convention; house style reuses only public names cross-module (5.7 imported
  `KARSTEN_TOLERANCE_LANDS`, `STRUCTURAL_GAP_BASELINES` — all public). Promoting it
  public would edit `dimensions.py` (AC7 forbids). Two copies of a documented 2-line
  decide-once policy is the cheaper debt; note in the docstring that a third copy is
  5.9's cue to hoist.
- **Iterate `DIMENSIONS`, not field order.** Determinism must not depend on dataclass
  field declaration order surviving refactors. `DIMENSIONS` is the one canonical order
  (AD-7); both `DimensionVector` and `DimensionWeights` field sets are already pinned
  equal to it, so `getattr` over `DIMENSIONS` is total and mypy-safe via the existing
  test pins.
- **No rubric branch — and prove it with `dataclasses.replace`.** FR20's "Standard
  fork" is satisfied by what the composer (5.9/Epic 7) does NOT call (`bracket_floor`),
  never by branching in the math. `FormatProfile` is a frozen dataclass, so
  `dataclasses.replace(STANDARD_PROFILE, rubric="brackets")` builds the counterfactual
  profile for the invariance test without touching the shipped constants.
- **Labels are CLOSED; thresholds are provisional.** The five label strings enter the
  AD-7 result shape and the AD-8 byte-identical diff surface — renaming "High-Power"
  later invalidates every cached diff, so the vocabulary is fixed now (exact FR24
  strings, hyphen included) and only the four cut-point INTS are 5.9 tuning knobs
  (edit → bump version → re-benchmark, the AD-3 workflow).
- **Per-format thresholds absorb the scale-comparability defer.** The 5.7 review
  deferred "Standard vs Commander vectors are not on a comparable scale until 5.9
  anchors them" — that is exactly why `tier_thresholds` lives on the profile rather
  than as one shared module constant: 5.9 tunes each format's cuts against its own
  benchmark anchors (precons ~B2 band; cEDH high; Standard competitive/mid/jank tiers)
  without cross-format math. Start both at `(20, 40, 60, 80)` — an honest
  zero-information prior, clearly commented as such.
- **Inclusive lower cut, decide once.** `score >= tier_thresholds[i]` promotes into
  band `i+1`; walk from the top (or `bisect_right` on the tuple — either is fine,
  document whichever you pick). Pin the exact boundary behavior in tests (threshold
  value → its band; value−1 → band below) so 5.9's re-cut can't silently flip the
  convention.
- **Vocabulary ≠ policy.** The AD-6 degradation ladder (which degradations map to which
  level, how `reasons[]` is assembled and sorted) is edge code with edge inputs
  (unresolved counts, snapshot presence, commander resolution). Shipping even a
  "helper" policy function here would couple the pure core to run-context semantics it
  cannot see. Tokens + types only — exactly like `STRUCTURAL_GAP_TOKENS` shipped as
  vocabulary in 5.5 and got consumed later.
- **Sorted-where-it-matters:** `CONFIDENCE_REASON_TOKENS` is defined already
  bytewise-sorted (`cards_unresolved` < `combo_data_unavailable` <
  `commander_unidentified` < `game_changer_data_unavailable` — note `comb` < `comm`);
  `CONFIDENCE_LEVELS` and `TIER_LABELS` are SEMANTIC orders (ascending severity /
  ascending power) and must be documented as such — they are scalar vocabularies, not
  AD-8 emission lists, so bytewise sorting does not apply to them.
- **Determinism traps:** no dict iteration over inputs, no `set` anywhere, all floats
  reduced through `_to_score`. The module has no collections to sort at runtime — its
  determinism is structural. Keep it that way.

### Previous-story intelligence (5.7, just completed)

- **Review outcome:** all 9 ACs satisfied on first review; the only patches were two
  docstring-accuracy items (committed as `fde9d8c`). The lesson that generated them:
  **docstrings must not overclaim** — 5.7's module docstring claimed "one
  `compute_curve` per entry point" while sanctioned internal re-derivations existed,
  and `_speed_score` claimed a broader monotonicity than the SWAP-based tests proved.
  For 5.8: claim exactly what the tests pin (e.g. say "monotone per-dimension under
  fixed weights", not "monotone under any profile edit"; say "total over `[0, 100]`,
  defensive outside it", not "accepts any int meaningfully").
- **Three 5.7 defers are logged for 5.9, none for 5.8** (deferred-work.md 2026-07-14):
  `card_advantage` caps at 98 (the aggregate inherits whatever the vector emits — do
  NOT compensate here), the `sixty_card` curve targets / scale-comparability item
  (absorbed by per-format `tier_thresholds`, see load-bearing decisions), and the
  `win_turn_band` malformed-band guard (a `dimensions.py` concern; out of scope).
- **Standing lessons still in force:** Literal-keyed / typed closed sets from the start
  (5.4); both/all enum branches exercised (5.4); verify-by-shape for provisional
  values, exact pins only for closed vocabulary and derived math (5.1→5.7); assert
  messages naming the surface or drop the claim (5.5); keep AC prose and pinned test
  values in sync — amend the story file if you correct a number mid-implementation
  (5.5); the pinned-version test moves WITH the bump in the same edit (this story
  amends the 5.7 v2 pin to v3 — sanctioned, AC4).
- **5.6 review lesson that applies here:** cheap defense-in-depth guards get accepted
  where malformed input could masquerade as signal — hence `tier_label`'s
  degrade-not-raise posture for out-of-domain scores (a future caller bug should
  produce a clamped label, not an IndexError inside the pure core).

### Testing standards

- pytest config in `pyproject.toml`: `asyncio_mode="auto"`, `--strict-markers`,
  `--tb=short`; these tests are synchronous, no markers, in the `-m "not integration"`
  fast subset.
- Flat placement `tests/unit/logic/test_assessment_aggregate.py` beside the six
  existing assessment test modules (the `tests/unit/logic/assessment/` subdir move
  remains deferred; if you do it, move all seven in one commit).
- **No card/deck factories needed** — `DimensionVector(speed=…, …)` and synthetic
  `FormatProfile(...)` / `dataclasses.replace(...)` instances are the only fixtures.
  Build a tiny local helper (e.g. `make_vector(**overrides)` defaulting all seven to a
  mid value) rather than importing `tests/fixtures/assessment.py` — that module is for
  card-shaped inputs this story doesn't have.
- `typing.get_args` on `TierLabel` / `ConfidenceLevel` and `dataclasses.fields` give
  totality assertions without restating vocabulary.
- `tests.*` is mypy-exempt but write full hints anyway.

## Project Structure Notes

**New/changed files:**

```text
src/
  logic/
    assessment/
      aggregate.py          # NEW: aggregate_score, tier_label, _to_score (restated policy),
                            #      CARDS_UNRESOLVED / COMBO_DATA_UNAVAILABLE /
                            #      COMMANDER_UNIDENTIFIED / GAME_CHANGER_DATA_UNAVAILABLE,
                            #      CONFIDENCE_REASON_TOKENS, ConfidenceLevel, CONFIDENCE_LEVELS
      profiles.py           # MODIFIED: + TierLabel, TIER_LABELS, FormatProfile.tier_thresholds;
                            #           both versions bumped v2 -> v3 (AC3/AC4)
      __init__.py           # MODIFIED: additive re-exports, bytewise-sorted
tests/
  unit/
    logic/
      test_assessment_aggregate.py   # NEW: AC8 matrix
      test_assessment_profiles.py    # MODIFIED: additive threshold/label tests + the one
                                     #           sanctioned v2->v3 pin amendment
plugin/                     # REGENERATED mirror (hook rebuilds; verify aggregate.py,
                            # profiles.py AND __init__.py mirror paths are staged)
```

- No changes to `dimensions.py`, `classifiers.py`, `mana_base.py`, `consistency.py`,
  `combos.py`, `src/logic/__init__.py`, any schema/repository/model/importer,
  `scripts/`, `src/mcp_server`, or the benchmark fixtures. No DB objects.
- Downstream consumers to keep in mind while naming things: 5.9 (`score()` composes
  matcher → `dimension_vector`/`bracket_floor` → `aggregate_score` + `tier_label`;
  benchmark tier-band assertions; owns tuning `weights` and `tier_thresholds`), 7.2 /
  feature 4.2 (assembles `confidence{level, reasons[]}` from `CONFIDENCE_REASON_TOKENS`
  + `ConfidenceLevel`), 7.3 (serializes the for-format score + label into
  `AssessDeckPowerResult`; emits `bracket: null` for `heuristic_only`).

## References

- [Source: _bmad-output/planning-artifacts/epics-deck-power-assessment.md#Story 2.8] —
  the binding ACs (0–100 aggregate, no 1–10; label from profile thresholds; Standard
  heuristic_only fork with the label; the closed four-token confidence enum,
  count-free, clock-free, caveat-not-a-reason).
- [Source: epics-deck-power-assessment.md#Epic List / Story 2.9] — the 2026-07-12
  amendment: Standard benchmark anchors + monotonicity properties land with 5.9, not
  here.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-11/ARCHITECTURE-SPINE.md#AD-3, #AD-6, #AD-7, #AD-8; #Deferred] —
  profile-owned mapping parameters + bump rule; the exact four-token enum + `low |
  medium | high` levels, no numeric band, no clock-derived reason, multiplayer caveat
  never a reason; fixed shape with descriptive tier label; sorted-emission /
  integer-score discipline; aggregate weight VALUES deferred to
  implementation/calibration.
- [Source: docs/deck-assess.md:94-98] — Option F descriptive labels ("Unfocused /
  Focused / Tuned / High-Power / Competitive"; human-facing layer atop the numeric
  core); [:77-80] — the weighted-aggregate option the for-format score realizes;
  [:239-241] — hand-tuned, documented, adjustable weights calibrated offline (NFR8).
- [Source: src/logic/assessment/profiles.py] — `DIMENSIONS` (canonical home precedent),
  `DimensionWeights` (fields pinned == `DIMENSIONS`, sum-1.0 pinned), the
  additive-extension + bump-rule docstring contract, current v2 versions.
- [Source: src/logic/assessment/dimensions.py:225-233] — `_to_score`, the decide-once
  clamp + round-half-up policy this story restates; [:430-456] — `DimensionVector`
  frozen shape.
- [Source: src/logic/assessment/consistency.py:298-306] — `STRUCTURAL_GAP_TOKENS`, the
  closed-token-vocabulary precedent (Final constants + bytewise-sorted tuple).
- [Source: tests/unit/logic/test_assessment_profiles.py:197-209] — the v2 version-pin
  test this story amends to v3 (AC4's sanctioned non-additive edit).
- [Source: _bmad-output/implementation-artifacts/5-7-dimension-vector-commander-bracket-floor-cedh-candidacy.md#Review
  Findings, #Dev Notes] — the docstring-overclaim lesson; the three 5.9-deferred items
  (card_advantage 98 cap, sixty_card scale comparability, win_turn_band guard) and why
  none lands here.
- [Source: _bmad-output/implementation-artifacts/deferred-work.md#Deferred from: code
  review of story-5.7] — the scale-comparability defer absorbed by per-format
  `tier_thresholds`.
- [Source: _bmad-output/project-context.md#Framework rules, #Testing Rules, #Code
  Quality] — layering, mypy --strict / ruff / Google docstrings / pytest gates.

## Dev Agent Record

### Agent Model Used

Claude Fable 5 (claude-fable-5) via Claude Code — BMAD dev-story workflow.

### Debug Log References

- Task 0 baseline: `fde9d8c` HEAD, tree clean (story artifacts only), fast suite
  **991 passed, 5 deselected** — exact match to the story-creation snapshot.
- Red-green per task: profile tests failed on `ImportError: TIER_LABELS` before the
  profiles.py edit; aggregate tests failed on collection (module absent) before
  `aggregate.py` was written. Both went green with no implementation retries.
- Final gates: `ruff check` clean (2 files auto-reformatted by `ruff format` — line
  joins only), `mypy --strict src/` clean (63 files), fast suite **1052 passed,
  5 deselected** (991 baseline + 61 new: 53 aggregate + 8 profile additions).

### Completion Notes List

- **Implementation plan (as executed):** Task 1 extended `profiles.py` with the closed
  `TierLabel`/`TIER_LABELS` vocabulary beside `DIMENSIONS` (one-canonical-home rule) and
  the `tier_thresholds: tuple[int, int, int, int]` field (provisional `(20, 40, 60, 80)`
  even quintiles on both profiles, per-format-tuning rationale commented), bumping both
  versions v2→v3 in the same edit; the `FormatProfile` class docstring's parameter list
  was amended to include `tier_thresholds` (the 5.7 no-overclaim lesson, kept honest).
  Tasks 2–4 shipped `src/logic/assessment/aggregate.py`: restated `_to_score` (clamp +
  half-up, docstring cross-referencing `dimensions._to_score` and the hoist-on-third-copy
  cue), `aggregate_score` iterating `DIMENSIONS` via `getattr` (reads ONLY
  `profile.weights`, no rubric branch), `tier_label` as `bisect_right` over
  `tier_thresholds` (inclusive lower cut, total, degrade-not-raise), and the AD-6
  vocabulary (four `Final` tokens + bytewise-sorted `CONFIDENCE_REASON_TOKENS`,
  `ConfidenceLevel`/`CONFIDENCE_LEVELS` documented as semantic order) — tokens only, no
  assignment policy. Task 5 re-exported all new public names from
  `src/logic/assessment/__init__.py` (`__all__` kept bytewise-sorted; note
  `CARDS_UNRESOLVED` sorts BEFORE `CARD_DRAW` bytewise since `S` < `_`).
- **AC5 proven, not built:** no Standard-specific math exists;
  `dataclasses.replace(profile, rubric=<other>)` invariance tests pin that both
  `aggregate_score` and `tier_label` are rubric-blind under both shipped profiles. The
  composition contract (heuristic_only composer never consults `bracket_floor`; edge
  emits `bracket: null`) is documented in the module docstring.
- **AC8 matrix covered** in `tests/unit/logic/test_assessment_aggregate.py` (53 tests):
  domain + exact 0/100 anchors both profiles, half-up rounding pin (synthetic 0.5/0.5
  profile, 50.5→51, with the `round(50.5) == 50` banker's-rounding contrast documented),
  per-dimension monotonicity over all seven dimensions × both profiles, rubric-swap
  invariance, label totality/boundary/monotone/out-of-domain-degrade, exact vocabulary
  pins (bytewise-sorted, snake_case, digit-free; `typing.get_args` totality for both
  Literals), AC4 profile additions (shape/domain/ascending + v3 pins), determinism +
  input non-mutation. Every assertion carries a failure message naming the surface.
- **Sanctioned non-additive test edit:** `test_versions_bumped_for_karsten_formula_addition`
  amended to `test_versions_bumped_for_tier_thresholds_addition` with the v3 strings
  (AC4's one sanctioned amendment; all other `test_assessment_profiles.py` changes are
  additive — `TestTierThresholds` + `TestTierLabels` classes).
- **Scope guard held:** no `score()` entry point, no benchmark/anchor edits, no
  serialization, no confidence assignment policy, no edits to `dimensions.py` /
  `classifiers.py` / `mana_base.py` / `consistency.py` / `combos.py` or any
  `src/data` / `src/mcp_server` / `scripts/` file. Only sanctioned files touched.

### File List

- `src/logic/assessment/aggregate.py` (NEW)
- `src/logic/assessment/profiles.py` (MODIFIED — TierLabel/TIER_LABELS,
  FormatProfile.tier_thresholds, both profiles + v3 bumps, docstring amendment)
- `src/logic/assessment/__init__.py` (MODIFIED — additive re-exports, bytewise-sorted)
- `tests/unit/logic/test_assessment_aggregate.py` (NEW)
- `tests/unit/logic/test_assessment_profiles.py` (MODIFIED — additive threshold/label
  tests + the sanctioned v2→v3 pin amendment)
- `plugin/server/src/logic/assessment/aggregate.py` (REGENERATED mirror, NEW)
- `plugin/server/src/logic/assessment/profiles.py` (REGENERATED mirror)
- `plugin/server/src/logic/assessment/__init__.py` (REGENERATED mirror)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (status tracking)
- `_bmad-output/implementation-artifacts/5-8-for-format-aggregate-tier-label-standard-fork-confidence-vocabulary.md`
  (this story file)

## Review Findings

_Code review 2026-07-14 (adversarial: Blind Hunter + Edge Case Hunter + Acceptance Auditor). Acceptance Auditor: **all 9 ACs satisfied, zero violations.** Core math (bisect boundary policy, clamp + half-up rounding) verified correct by hand. All findings below are low severity; every "malformed profile" edge case is unreachable behind the mypy `tuple[int, int, int, int]` type and the pinned non-negative / sum-to-1.0 / strictly-ascending profile tests._

- [x] [Review][Patch] Add a cross-module `_to_score` parity test [tests/unit/logic/test_assessment_aggregate.py] — **APPLIED.** `aggregate._to_score` (aggregate.py:81-94) is a hand-copy of `dimensions._to_score`, and the module docstring calls it the "shared decide-once policy … pinned by tests", yet no test asserted the two implementations agree. Added `TestToScorePolicyParity` (15 parametrized cases across `.5` rounding boundaries + clamp edges) importing both private helpers; makes the "pinned by tests" claim literally true and guards the seam until 5.9 hoists it (the 5.7 no-overclaim lesson). Fast suite 1052 → 1067 green; ruff + mypy clean.
- [x] [Review][Defer] `tier_label`/`aggregate_score` trust their frozen profile's shape & weight validity [src/logic/assessment/aggregate.py:146,116] — deferred to 5.9. `tier_label` assumes exactly 4 strictly-ascending `tier_thresholds` (a 5+-tuple → `IndexError`; non-ascending → silent mislabel), and `aggregate_score`'s `[0,100]`/monotonicity guarantees assume non-negative, finite weights (a NaN → `ValueError`; a negative weight → silent monotonicity break). All unreachable with the shipped frozen+tested profiles, but 5.9 hand-tunes BOTH `weights` and `tier_thresholds` — optional cheap defense-in-depth for the tuning workflow (parallels the deferred 5.7 `win_turn_band` guard).
- [x] [Review][Defer] `tier_thresholds` domain `(0, 100]` permits a cut of exactly 100 [src/logic/assessment/profiles.py:126] — deferred to 5.9. A cut at 100 makes the top band (`Competitive`) a single-point band reachable only by an exact score of 100; harmless for the shipped `(20, 40, 60, 80)`, but worth a guardrail when 5.9 re-cuts per-format anchors.

_Dismissed as noise (2): the monotonicity test's `>=` assertion is the **correct** encoding of non-decreasing monotonicity (a strict `>` would over-claim and break on a legitimately zero-weighted dimension); the module docstring's `bracket: null` / `heuristic_only` composition narrative is **mandated by AC5**, not a stray claim about behavior this module implements._

## Change Log

- 2026-07-14: Story 5.8 code review — all 9 ACs satisfied (0 violations); 1 optional
  patch (`_to_score` parity test), 2 defers to 5.9 (profile shape/weight-validity guards;
  `tier_thresholds`=100 domain), 2 dismissed. Status → review (patch left as action item).
- 2026-07-14: Story 5.8 implemented (review) — `aggregate.py` (aggregate_score,
  tier_label, AD-6 confidence vocabulary), profiles v3 (TierLabel/TIER_LABELS +
  tier_thresholds), additive exports, 61 new offline tests; fast suite 1052 passed,
  mypy --strict + ruff clean.
- 2026-07-14: Story 5.8 created (ready-for-dev) — ultimate context engine analysis
  completed: comprehensive developer guide covering the vector→aggregate seam (weights
  first read here), the closed-labels/provisional-thresholds split and its AD-8
  rationale, per-format thresholds as the absorber of the 5.7 scale-comparability
  defer, the no-rubric-branch Standard fork + replace()-based invariance proof, the
  vocabulary-not-policy confidence boundary, and the clean `fde9d8c` baseline
  (991 passed).
