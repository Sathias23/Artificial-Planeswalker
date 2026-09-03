---
baseline_commit: 88b1e66 # 5.4 review-patch commit (review -> done)
---

# Story 5.5: Consistency, interaction & structural-coverage signals

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

> **Sprint/feature numbering:** this is sprint key
> `5-5-consistency-interaction-structural-coverage-signals` (`epic-5`), which is **feature
> Epic 2, Story 2.5** in `_bmad-output/planning-artifacts/epics-deck-power-assessment.md`.
> Sprint Epic 5 = feature Epic 2 "Deterministic scoring core".

## Story

As the scorer,
I want deterministic consistency and structural signals,
so that the vector reflects reliability and coverage without simulation.

## Context & why this story exists

This story adds the **consistency, interaction-detail, and structural-coverage signals**
(FR17, FR7, FR9) to the pure core in `src/logic/assessment/` — the third behavior module
after 5.3's classifiers and 5.4's mana-base math. It turns a deck's cards into three raw
signal families that downstream stories consume:

- **FR17 hypergeometric access** — exact analytic probabilities (no Monte Carlo, AD-2/NFR1)
  of seeing key pieces and hitting land drops by turn N. 5.4 explicitly handed this off:
  "the hypergeometric consistency math over the land count is Story 5.5's"
  (`mana_base.py:6`). **5.7** maps these probabilities onto the integer 0–100 `consistency`
  dimension.
- **FR7 interaction detail** — instant-speed ratio and interaction-CMC distribution over
  5.3's `INTERACTION` tag. **5.7** maps these onto the `interaction` dimension; Epic 7's
  output schema sketch surfaces `instant_speed_ratio` + `count` under `interaction`
  (`docs/deck-assess.md:268`).
- **FR9 structural coverage** — rule-of-8 / functional-redundancy signals plus the 8×8
  coverage read, emitted as a **closed-enum `structural_gaps[]` token list**. This story
  **owns and defines that enum** (AD-6 names it a closed enum alongside the confidence
  tokens); Epic 7's `flags.structural_gaps` serializes exactly these tokens, sorted
  bytewise (AD-8).

Like 5.3 and 5.4, you emit **raw values** (floats/ints/booleans/tokens), never 0–100 scores
— the signal→score mapping curves are 5.7/5.8's, and the aggregate weighting is 5.8's.

## Acceptance Criteria

1. **A pure consistency/structure module exists in `src/logic/assessment/`.** Given AD-2 and
   the 5.3/5.4 precedent, when the module (recommended: `consistency.py`) is added, then it
   contains only pure functions over already-loaded Pydantic schemas (`Card` / `DeckCard`)
   with **no network, DB, clock, file I/O, or imports from `src/search` / `src/mcp_server` /
   `src/logic/mana_curve`** (stdlib + `src.data.schemas` + `src.logic.assessment.classifiers`
   + `src.logic.assessment.mana_base` **public API** only), and all result shapes are frozen
   slots dataclasses with deterministically ordered contents — identical input always yields
   identical output. [epics 2.5; AD-2; AD-8 spirit]

2. **FR17 hypergeometric primitive — exact, analytic, never raises.** Given `math.comb`
   (stdlib; integer-exact, so deterministic across runs/platforms), when the module computes
   draw probabilities, then a public primitive
   `probability_at_least(*, deck_size, copies, drawn, min_count=1) -> float` returns the
   exact hypergeometric P(X ≥ min_count) and degrades on every edge instead of raising,
   with explicit precedence: `min_count <= 0` → `1.0` (trivially satisfied — checked FIRST,
   so an empty deck at turn 0 still reads 1.0); then `deck_size <= 0` or `copies <= 0` or
   `drawn <= 0` → `0.0`; `drawn > deck_size` and `copies > deck_size` clamp; `min_count >
   min(copies, drawn)` → `0.0`. Pinned published-constant tests (AC8) prove the arithmetic.
   [epics 2.5; FR17; NFR3 spirit]

3. **FR17 key-piece & mana access by turn N.** Given the deck's cards
   (`Sequence[DeckCard]`, quantity-aware), when computed, then:
   - a documented **cards-seen convention** is fixed once as a constant/function:
     `cards_seen(turn) = OPENING_HAND_SIZE (7) + turn`, where turn 0 = the opening hand
     (this is the research doc's own convention — its "1 copy in 99 cards ≈ 12% by turn 5"
     worked example is exactly 12 seen cards, `12/99 ≈ 0.1212`);
   - **mana access by turn N**: P(at least N lands among `cards_seen(N)`) computed from the
     deck's quantity-aware land count (reuse 5.4's `compute_curve` for `land_count` — do
     NOT re-implement land detection) and total deck size;
   - **key-piece access by turn N**: the same primitive parameterized by copy count, so
     5.7 can ask "P(≥1 of k functional copies by turn N)" for any category count or combo
     piece without re-deriving math.
   An empty deck returns `0.0` probabilities — never raises. [epics 2.5; FR17;
   docs/deck-assess.md:154]

4. **FR9 rule-of-8 / functional-redundancy signals.** Given 5.3's `classify_deck` counts,
   when computed, then a redundancy signal is produced for **every** category token in
   `classifiers.CATEGORIES` (all nine, fixed order — the AD-7 fixed-shape discipline: no
   categories-present-conditional output): the quantity-aware count and the opening-hand
   access probability P(≥1 in 7 cards) against the **actual** deck size, via the AC2
   primitive. The published redundancy anchors (60-card opener: 4 copies → 39.9%, 8 →
   65.4%, 12 → 80.9%) are pinned as exact tests of the primitive, not stored as constants —
   they fall out of the math. [epics 2.5; FR9; addendum §C; docs/deck-assess.md:124]

5. **FR7 interaction detail signals.** Given cards tagged `INTERACTION` by
   `classifiers.classify_card`, when computed, then the module produces, quantity-aware:
   - the **interaction count** (matches `classify_deck`'s count for the token);
   - the **instant-speed count and ratio** (ratio = instant-speed interaction ÷ total
     interaction; `0.0` when the deck has no interaction — documented, never NaN/raise).
     Instant-speed policy (decide-once, documented at the code site): `"instant" in
     type_line.lower()` OR `"flash"` in lowercased `keywords`. Text-granted flash
     ("as though it had flash") is an accepted v1 undercount;
   - the **interaction-CMC distribution** as `(int(cmc) bucket, count)` pairs sorted
     ascending — same bucketing policy as 5.4's `compute_curve` (front-face `cmc`, floor).
   [epics 2.5; FR7; docs/deck-assess.md:118, :268]

6. **FR9 8×8 structural-coverage gaps as a closed token enum this story owns.** Given AD-6
   ("`structural_gaps[]` is likewise a closed enum" whose tokens never embed counts or
   phrases), when coverage is computed, then:
   - the module defines the **closed `structural_gaps` token vocabulary** as module-level
     `Final` string constants plus a fixed `STRUCTURAL_GAP_TOKENS` tuple (the
     `classifiers.CATEGORIES` precedent). Recommended v1 tokens (snake_case, count-free):
     `card_draw_below_baseline`, `interaction_below_baseline`, `ramp_below_baseline`,
     `wincon_missing`;
   - `structural_gaps(deck_cards, *, formula)` evaluates the deck's `classify_deck` counts
     against a per-formula baseline table selected by an **explicit
     `KarstenFormula`-typed parameter** (import the type from `mana_base` — same
     `"commander" | "sixty_card"` fork, same profile-independence rule: if you find
     yourself editing `profiles.py`, stop — that is 5.7/5.8/5.9 territory);
   - baselines are provisional `Final` constants typed `dict[KarstenFormula, ...]` (the
     5.4 review lesson: Literal-keyed dicts from the start), each commented with its source
     (Command Zone template / 8×8 theory / "<6 ramp or <6 interaction is a weakness
     signal", docs/deck-assess.md:123) and marked 5.9-owned;
   - `wincon_missing` fires when the union of the three `WINCON_*` tags is empty;
   - **land adequacy is deliberately NOT a structural-gap token** — 5.4's Karsten
     flood/screw flags already own land-count adequacy; duplicating it here would create
     two sources for one fact (document this at the token definitions);
   - the returned token tuple is **sorted ascending bytewise** (AD-8), deterministic, and
     an empty deck simply falls below every baseline (tokens emitted, no crash).
   [epics 2.5; FR9; AD-6; AD-8]

7. **One vocabulary, no forked constants, provisional values documented.** Given AD-10 and
   AD-3, when the module is reviewed, then it **reuses 5.3's category tokens and
   `classify_card`/`classify_deck`** (never re-implements oracle-text patterns), reuses
   5.4's `compute_curve` for land/spell counts (never re-implements land detection or
   bucketing), makes **no `FormatProfile` change**, and defines every numeric constant
   (baselines, opening-hand size) as a `Final` module constant with a source comment,
   marked provisional where 5.9's benchmark pass owns tuning. No new classifier category is
   added: the 8×8 read maps onto the existing AD-10 taxonomy (the board-wipe sub-tag 5.3
   deferred "to 5.5 if its 8×8 math needs one" is **not needed** — v1 baselines operate on
   the coarse `INTERACTION` count; note this decision in the module docstring).
   [epics 2.5; AD-3; AD-10; NFR8]

8. **Offline unit tests prove the math — including exact published-constant checks.** Given
   the project's testing rules, when the test module runs (no `integration` marker, no DB),
   then hand-built fixtures from `tests/fixtures/assessment.py` verify at minimum:
   - **exact hypergeometric arithmetic on published anchors** (`pytest.approx`): 4/8/12
     copies in a 60-card deck, 7 seen → 0.399 / 0.654 / 0.809; 1 copy in 99 cards, turn 5
     (12 seen) → 12/99 ≈ 0.1212;
   - **the ~91% trap (verified at story-creation):** the research doc's "24 lands in 60 →
     ~91% for ≥2 lands in the opening 7" is actually the value for **8** seen cards
     (7 seen gives ≈ 0.857) — pin BOTH values with the seen-count that produces them, so
     the convention is regression-locked and nobody "fixes" the math to chase the prose;
   - primitive edge cases from AC2 (zero/negative inputs, clamps, `min_count` overflow →
     0.0, `min_count=0` → 1.0), each returning without raising;
   - mana access by turn on a pinned small deck; quantity-awareness (4-ofs count 4);
   - redundancy signals: all nine categories always present in `CATEGORIES` order;
     zero-count categories carry probability 0.0;
   - interaction detail: instant-speed ratio on a mixed instant/sorcery/flash-creature
     removal suite; a flash creature with removal text counts instant-speed; ratio 0.0 on
     zero interaction; CMC distribution sorted and quantity-aware;
   - structural gaps: tokens flip exactly at the baseline constants (reference the module
     constants — provisional values may move in 5.9, the 5.1→5.3 verify-by-shape lesson);
     output sorted bytewise; **both** formula tables exercised (the 5.4 review lesson —
     don't test only one table); empty deck emits the below-baseline tokens without
     raising;
   - **a `sideboard=True` `DeckCard` passed to each public function** (the 5.4 review
     lesson: pin the not-filtered policy so a future filtering regression is caught);
   - **determinism**: two calls on equal input produce equal results; ordered outputs.
   Runs green under `uv run pytest -m "not integration"` (baseline at story creation:
   **819 passed**). [project-context#Testing Rules; 5-4 review findings]

9. **Quality gates pass — including the `src/`-touch plugin mirror.** Given this story adds
   files under `src/`, when committed, then `mypy --strict` passes (full hints, Google
   docstrings on module + public functions — the docstrings define what each signal means),
   `ruff check` + `ruff format` are clean, and the regenerated `plugin/` mirror is staged in
   the same commit (run `uv run python -m scripts.build_plugin` explicitly — the pre-commit
   hook is absent in this checkout, epic-4 action item). [project-context#Code Quality;
   epic-4 retro]

## Tasks / Subtasks

- [x] **Task 1 — Design the signal surface** (AC: 1)
  - [x] Add `src/logic/assessment/consistency.py` with a module docstring naming it the
        FR17/FR7/FR9 module (raw signals only; 0–100 mapping is 5.7/5.8's; combo matching
        is 5.6's) and documenting the no-board-wipe-sub-tag decision (AC7).
  - [x] Frozen slots dataclasses per Dev Notes "Recommended shape".
- [x] **Task 2 — FR17 hypergeometric primitive** (AC: 2)
  - [x] `probability_at_least(*, deck_size, copies, drawn, min_count=1)` via `math.comb`,
        summing the survival tail (or 1 − CDF, whichever reads cleaner); all AC2 edge
        clamps; Google docstring stating exactness + determinism.
  - [x] `OPENING_HAND_SIZE: Final = 7` and `cards_seen_by_turn(turn)` (= 7 + turn, turn 0 =
        opener) with the convention documented (research-doc worked example cited).
- [x] **Task 3 — FR17 access-by-turn signals** (AC: 3)
  - [x] `land_access_by_turn(deck_cards, turn)` → P(≥ turn lands among seen), using
        `compute_curve(deck_cards).land_count` and quantity-aware deck size.
  - [x] Key-piece access: expose via the primitive (documented recipe in the docstring) —
        no speculative wrapper if it would just forward arguments.
- [x] **Task 4 — FR9 redundancy signals** (AC: 4)
  - [x] `redundancy_signals(deck_cards)` → fixed nine-tuple in `CATEGORIES` order joining
        `classify_deck` counts to opener probabilities on actual deck size.
- [x] **Task 5 — FR7 interaction detail** (AC: 5)
  - [x] `interaction_signals(deck_cards)` → count, instant-speed count/ratio (documented
        instant/flash policy), CMC distribution as sorted tuple.
- [x] **Task 6 — FR9 structural gaps** (AC: 6)
  - [x] Token constants + `STRUCTURAL_GAP_TOKENS` tuple; per-formula baseline tables
        (`dict[KarstenFormula, ...]`); `structural_gaps(deck_cards, *, formula)` returning
        a bytewise-sorted token tuple; the lands-exclusion note.
- [x] **Task 7 — Package exports** (AC: 1)
  - [x] Re-export public names from `src/logic/assessment/__init__.py` (extend `__all__`
        additively; consider also exporting `KarstenFormula` if importing it here makes it
        de-facto public API; do not touch `src/logic/__init__.py` or `profiles.py`).
- [x] **Task 8 — Offline unit tests** (AC: 8)
  - [x] `tests/unit/logic/test_assessment_consistency.py` using
        `tests/fixtures/assessment.py` factories; cover the full AC8 matrix; failure
        messages name the card/signal.
- [x] **Task 9 — Quality gates + plugin mirror** (AC: 9)
  - [x] `uv run ruff check . --fix && uv run ruff format .`
  - [x] `uv run mypy src/` (strict) — full hints on all new functions.
  - [x] `uv run pytest -m "not integration"` green (baseline: **819 passed**).
  - [x] Commit with the regenerated `plugin/` mirror staged (`uv run python -m
        scripts.build_plugin`; hook installed as of `88b1e66` — see Baseline note). Never
        `--no-verify`.

### Review Findings

- [x] [Review][Patch] `structural_gaps`'s `sixty_card` ramp baseline is `0`, making
      `ramp_below_baseline` permanently unreachable for the whole format — intentional
      (ramp isn't a 60-card structural requirement) but undocumented in the
      `structural_gaps`/`STRUCTURAL_GAP_TOKENS` public docstrings. [src/logic/assessment/consistency.py:310]
- [x] [Review][Patch] The v1 instant-speed heuristic (`_is_instant_speed`) has no path for
      permanent-based activated-ability interaction (e.g. a land/artifact "{T}: Destroy
      target artifact" with no Flash keyword), understating `instant_speed_ratio` for such
      decks; the module already documents two other v1 gaps but not this one.
      [src/logic/assessment/consistency.py:208]
- [x] [Review][Patch] `redundancy_signals` recomputes deck size via its own
      `sum(deck_card.quantity ...)` instead of reusing `compute_curve`'s
      `land_count + spell_count` (used two functions above it in the same module) —
      currently always equal since `_is_land` is an exhaustive land/spell split, but two
      independently-maintained "total deck size" computations violate the module's own
      "one owner" principle. [src/logic/assessment/consistency.py:180]
- [x] [Review][Patch] AC4/Dev Notes prose cites the rule-of-8 anchor for 12 copies as
      `0.8085`, but the true `math.comb` value is `0.80935…` and the shipped test pins
      `0.8094` — the Dev Agent's own Debug Log Reference already caught and corrected the
      number but never amended the AC/Dev-Notes prose above it.
      [_bmad-output/implementation-artifacts/5-5-consistency-interaction-structural-coverage-signals.md:249,437]
- [x] [Review][Patch] Story doc self-contradicts on pre-commit hook status: the "Baseline
      note" (story-creation snapshot) says the hook IS installed as of `88b1e66`, while
      Task 9 and "Previous-story intelligence" a few sections later still repeat unmodified
      "hook absent" boilerplate. [_bmad-output/implementation-artifacts/5-5-consistency-interaction-structural-coverage-signals.md:241]
- [x] [Review][Patch] Task 8 is checked off claiming "failure messages name the card/signal",
      but every assertion in the new test file is a bare `assert expr` with no message —
      zero matches for `assert ..., "..."`. [tests/unit/logic/test_assessment_consistency.py]
- [x] [Review][Defer] `classify_card` (Story 5.3) doesn't exclude land-typed cards from the
      `INTERACTION`/`CARD_DRAW`/`WINCON_*` tags (only from `RAMP`/`TUTOR`), so a land whose
      oracle text matches an interaction pattern is silently folded into
      `interaction_signals`'s count and CMC-0 bucket — deferred, pre-existing Story 5.3
      classifier behavior, not caused by this change. [src/logic/assessment/consistency.py:259]
- [x] [Review][Defer] `STRUCTURAL_GAP_BASELINES` is `dict[KarstenFormula, dict[str, int]]` —
      the outer `KarstenFormula` key is Literal-checked (the 5.4 review lesson), but the
      inner category keys (`CARD_DRAW`/`INTERACTION`/`RAMP`) remain plain `str`, so a future
      typo'd/missing key is a runtime `KeyError`, not a mypy error — deferred, root cause is
      `classifiers.py`'s untyped category constants from Story 5.3, out of this story's
      scope. [src/logic/assessment/consistency.py:310]
- [x] [Review][Defer] `probability_at_least` — the shared primitive every other function in
      this module (and future 5.6/5.7 combo-probability call sites) delegates to — has only
      pinned exact-value tests, no property/invariant test that output always stays in
      `[0.0, 1.0]` for arbitrary valid inputs — deferred, optional hardening beyond AC8's
      required matrix. [src/logic/assessment/consistency.py:59]

Dismissed as noise (documented/accepted precedent, or not a code defect):
sideboard rows inflating hypergeometric probability math (matches the documented, already-
accepted 5.3/5.4 "caller filters" policy; Epic 7's caller already passes mainboard-only rows
per spec); `structural_gaps[formula]` unguarded `KeyError` for an out-of-`Literal` `formula`
(matches the exact accepted precedent already shipped in `mana_base.py`'s
`karsten_land_delta`/`compute_pip_signals` — mypy enforces the `Literal` contract at call
sites, same as every sibling function); the reviewer's diff excerpt omitting the `plugin/`
mirror files (verified directly against the actual commit that the mirror is present and
byte-identical to `src/` — an artifact of how the review diff was produced, not a code gap).

## Dev Notes

### What this story is — and is NOT

- **IS:** one new pure module of hypergeometric/redundancy/interaction/coverage signal
  functions + frozen result shapes + the closed `structural_gaps` token enum + offline
  tests + `assessment/__init__.py` re-exports.
- **IS NOT:** any signal→0–100 mapping or dimension score (5.7), aggregate weighting or
  confidence-reason tokens (5.8), `ComboRecord` / combo matching / earliest-turn math
  (5.6), `FormatProfile` edits (AC6 — format enters via the explicit `formula` parameter),
  Monte Carlo anything (FR17 is analytic by requirement), new classifier categories or
  pattern edits in `classifiers.py` (AC7), or tool/skill-layer code. If a function needs a
  `FormatProfile`, a DB, or combo data — it belongs to a later story.

### Baseline note (story-creation snapshot, 2026-07-12)

The 5.4 review patches are committed as `88b1e66` (the `baseline_commit`). The
`mana_base.py` API documented below is the **post-review** state (typed
`dict[KarstenFormula, ...]` lookups, `_ANY_COLOR_UNCONDITIONAL_RE`) and is what you'll
consume. Also: **the pre-commit hook IS installed in this checkout as of `88b1e66`**
(ruff, mypy, and the plugin rebuild all ran at commit time) — the epic-4 "hook absent"
caveat no longer holds, but still stage the regenerated `plugin/` mirror in the same
commit (the hook rebuilds it; verify it's staged, never `--no-verify`).

### The published-constant traps (verified by direct computation at story creation)

- **Rule-of-8 anchors are exact:** P(≥1) with `deck_size=60, drawn=7` gives
  4 copies → 0.3995, 8 → 0.6537, 12 → 0.8094 — matching the published 39.9/65.4/80.9%
  (docs/deck-assess.md:124). Safe to pin with `pytest.approx(…, abs=1e-3)`.
- **The turn-N convention is derivable from the doc itself:** "a single copy in a 99-card
  deck is only ~12% to appear by turn 5" (docs/deck-assess.md:154) = 12 seen cards =
  `7 + 5` → the `cards_seen(turn) = 7 + turn` convention (turn 0 = opening hand; i.e. the
  on-the-draw reading). Fix it once as the documented v1 convention; an on-the-play
  variant is a 5.9 refinement, not yours.
- **⚠️ The ~91% figure does NOT match 7 cards.** The doc's "60-card/24-land deck has ~91%
  for ≥2 lands in the opening 7" (docs/deck-assess.md:154) computes to **0.857 at 7 seen
  cards**; 0.910 is the value at **8** seen cards (opener + one draw). The prose is loose,
  not the math. Do NOT bend the primitive to reproduce 91% at 7 cards — pin both values at
  their true seen-counts (AC8) and cite this note.

### Consuming 5.3 + 5.4 (the intended joins)

```python
from src.logic.assessment.classifiers import (
    CATEGORIES, INTERACTION, WINCON_COMBO_PIECE, WINCON_EXPLICIT, WINCON_FINISHER,
    classify_card, classify_deck,
)
from src.logic.assessment.mana_base import KarstenFormula, compute_curve
```

- **Land count / deck size:** `compute_curve(deck_cards)` returns quantity-aware
  `land_count` and `spell_count`; deck size = `land_count + spell_count`. Never
  re-implement `"land" in type_line.lower()` — that policy has one owner (`mana_base._is_land`,
  private; go through `compute_curve`).
- **Interaction membership:** `classify_card(card) & {INTERACTION}` per card (you need
  per-card joins for CMC buckets and instant-speed, exactly the join the `classify_card`
  docstring promises 5.5: "5.5 computes CMC distributions over interaction"). Deck-level
  count via your own quantity-aware loop (must equal `classify_deck`'s count — assert that
  equivalence in a test rather than calling both in production code).
- **Redundancy counts:** `classify_deck(deck_cards)` gives the per-category quantity-aware
  counts + explaining names; join each to the opener probability.
- `classify_card` is pure and unmemoized — one pass per deck card is fine here. If you call
  it once for interaction AND `classify_deck` for redundancy, that's two passes total —
  acceptable (the deferred 5.3 memoization note is still not yours to fix).

### Decide-once policies (document each at its code site)

- **Cards-seen convention:** `cards_seen(turn) = 7 + turn`, turn 0 = opening hand. Cite the
  12/99 worked example. No mulligan modeling in v1 (document).
- **Mana access definition:** P(≥ `turn` lands among `cards_seen(turn)`) — "made every land
  drop through turn N". Clamp: `turn <= 0` → `1.0` (trivially no drops needed) or `0.0`?
  Recommended: `min_count = turn`, so turn 0 → `min_count 0` → `1.0` via the primitive's
  AC2 rule — consistent, no special case.
- **Instant-speed policy:** `"instant" in type_line.lower()` OR `"flash" in`
  lowercased-keywords (`card.keywords or ()`, the 5.3 guard). Multi-face type lines are
  `//`-joined at top level, so an "Instant // Sorcery" split counts instant-speed —
  conservative, accept v1. Text-granted flash is an accepted undercount.
- **Interaction CMC bucketing:** `int(card.cmc)` floor, front-face `cmc` semantics — cite
  5.4's `CurveSignals` docstring; keep identical wording so the two distributions can never
  be read as different policies.
- **Structural baselines (provisional, 5.9 tunes).** Recommended starting tables:
  - `commander`: ramp 6, card_draw 6, interaction 6 — the documented "<6 ramp or <6
    interaction in Commander is a weakness signal" line (docs/deck-assess.md:123); the
    Command Zone template (~10/10/10) is the aspirational reference, the 6-line is the
    *gap* threshold. Wincon: ≥1 card tagged any `WINCON_*`.
  - `sixty_card`: ramp 0 (ramp is not a structural requirement in 60-card decks — a 0
    baseline means the token simply never fires), card_draw 4, interaction 6, wincon ≥1.
    Honest provisional guesses; 5.9's Standard anchors calibrate them.
  Below-baseline means `count < baseline` (strictly less), quantity-aware counts.
- **Tokens are count-free snake_case** (AD-6): `ramp_below_baseline`, never
  `ramp_below_baseline_6`. Counts already live in the redundancy/`classify_deck` signals;
  Epic 7 surfaces them as separate structured fields.
- **Lands excluded from gap tokens:** Karsten flood/screw (5.4) owns land adequacy — two
  sources for one fact would let them disagree. Document at the token definitions.
- **Sideboard rows are NOT filtered** — the 5.3/5.4 policy: deck-composition belongs to the
  caller/edge; a caller wanting played-cards-only signals filters `sideboard=False` first.
  Same one-line caveat in each public docstring. Note the consequence honestly: sideboard
  rows inflate `deck_size` and category counts symmetrically; the edge (Epic 7) passes
  mainboard-only rows.
- **Float determinism:** `math.comb` is exact integer arithmetic; a single final division
  per probability keeps results bit-identical for identical inputs. No `random`, no clock.
  You emit raw floats; 5.7 rounds to int 0–100.

### Recommended shape (guidance, not a straitjacket)

```python
# consistency.py — sketch
OPENING_HAND_SIZE: Final = 7   # v1 convention: cards_seen(turn) = 7 + turn (turn 0 = opener)

def probability_at_least(
    *, deck_size: int, copies: int, drawn: int, min_count: int = 1
) -> float: ...
def cards_seen_by_turn(turn: int) -> int: ...
def land_access_by_turn(deck_cards: Sequence[DeckCard], turn: int) -> float: ...

@dataclass(frozen=True, slots=True)
class RedundancySignal:
    category: str                 # a classifiers.CATEGORIES token
    count: int                    # quantity-aware (classify_deck's count)
    opener_probability: float     # P(>=1 in opening 7) on the actual deck size

def redundancy_signals(deck_cards: Sequence[DeckCard]) -> tuple[RedundancySignal, ...]: ...
    # always all nine, CATEGORIES order — fixed closed shape (AD-7 spirit)

@dataclass(frozen=True, slots=True)
class InteractionSignals:
    count: int                                   # quantity-aware INTERACTION total
    instant_speed_count: int
    instant_speed_ratio: float                   # 0.0 when count == 0
    cmc_distribution: tuple[tuple[int, int], ...]  # (bucket, count), sorted ascending

def interaction_signals(deck_cards: Sequence[DeckCard]) -> InteractionSignals: ...

# FR9 closed gap-token enum — this module owns it; Epic 7 serializes it verbatim (AD-6).
CARD_DRAW_BELOW_BASELINE: Final = "card_draw_below_baseline"
INTERACTION_BELOW_BASELINE: Final = "interaction_below_baseline"
RAMP_BELOW_BASELINE: Final = "ramp_below_baseline"
WINCON_MISSING: Final = "wincon_missing"
STRUCTURAL_GAP_TOKENS: Final[tuple[str, ...]] = (...)  # fixed documented order

def structural_gaps(
    deck_cards: Sequence[DeckCard], *, formula: KarstenFormula
) -> tuple[str, ...]: ...
    # returned tokens sorted ascending bytewise (AD-8)
```

Why this shape: the keyword-only primitive makes call sites self-documenting
(`probability_at_least(deck_size=99, copies=1, drawn=12)`); the fixed nine-tuple mirrors
5.4's fixed five-color tuple (AD-7 spirit — no conditional keys); surfacing `count` next to
`opener_probability` gives Epic 7 the explainability payload (NFR2) without recomputation;
reusing `KarstenFormula` keeps one format-fork vocabulary across the package. Token-order
tip: define `STRUCTURAL_GAP_TOKENS` already bytewise-sorted so the "fixed documented
order" and the AD-8 emission order coincide — one less thing to get wrong.

### Layer & purity rules (AD-2, project-context)

- Allowed imports: stdlib (`math`, `dataclasses`, `typing`, `collections.abc`) +
  `src.data.schemas.card` / `src.data.schemas.deck` + `src.logic.assessment.classifiers` +
  `src.logic.assessment.mana_base` (public names only — never `_is_land` or other
  underscore names). Forbidden: `src/search`, `src/mcp_server`, `src/data/repositories`,
  `src/logic/mana_curve`, `src/logic/synergy`, Pydantic models of your own (frozen
  dataclasses are the package convention).
- Python 3.12 syntax (`X | None`, builtin generics, `Final`, `Literal`); Google docstrings
  on module + every public function; module docstring required.
- Pure functions — no logging needed.

### Previous-story intelligence (5.4, just completed)

- **Surface you consume:** `compute_curve(deck_cards) -> CurveSignals`
  (`.land_count`, `.spell_count`, `.distribution`, `.average_mana_value`),
  `KarstenFormula = Literal["commander", "sixty_card"]` — both public in `mana_base`.
- **5.4 review findings to apply proactively here** (each was a review-cycle round-trip —
  don't repeat them):
  1. Literal-keyed lookup tables: type baseline dicts `dict[KarstenFormula, ...]` from the
     start so an invalid selector is a mypy error, not a runtime `KeyError`.
  2. Include a `sideboard=True` row test for **every** public function (5.4 shipped without
     one and review flagged it).
  3. Exercise **both** formula tables in tests, not just `sixty_card` (5.4's Commander
     anchor cap was initially untested).
  4. Substring vs word-boundary consistency: if you add any regex (you likely need none —
     "instant"/"flash" checks are substring/set membership), keep `\b` discipline
     consistent within the file.
  5. Bare substring phrases overcount (the `_ANY_COLOR_PHRASE` conditional-lands finding) —
     if a text phrase check creeps in, think about qualifier clauses before shipping it.
- **Verify-by-shape lesson (5.1→5.4):** exact-value asserts are right for *published/derived*
  constants (hypergeometric anchors — pure math, safe to pin) and wrong for *provisional*
  tunables (baseline tables — assert tokens flip at the constant, referencing the module
  constant).
- **Null-face lesson (5.3):** face dict values can be explicitly `None` — always
  `face.get(key) or ""`. (You likely never touch `card_faces` in this story — `cmc`,
  `type_line`, `keywords` are all top-level and non-nullable-coerced — but if you do, this
  rule applies.)
- **Plugin mirror:** the pre-commit hook is installed as of `88b1e66` (see Baseline note)
  and runs `scripts.build_plugin` automatically — verify `plugin/server/src/logic/assessment/`
  is staged in the same commit rather than running the script manually. Line-ending-only
  `plugin/*.json` diffs are noise; don't chase them.
- **Fast-suite baseline: 819 passed** (verified at story-creation time, post-5.4-review).

### Testing standards

- pytest config in `pyproject.toml`: `asyncio_mode="auto"`, `--strict-markers`,
  `--tb=short`; these tests are synchronous, no markers, run in the `-m "not integration"`
  fast subset.
- Flat placement `tests/unit/logic/test_assessment_consistency.py` beside the three
  existing assessment test modules (four flat files is still fine; the
  `tests/unit/logic/assessment/` subdir move remains deferred — if you do move, move all
  four in the same commit).
- **Use the shared factories** (`tests/fixtures/assessment.py::make_card/make_deck_card`) —
  do not redefine them (the G1 lesson). For interaction fixtures, real-ish cards read best:
  `make_card(name="Bolt", type_line="Instant", cmc=1.0, oracle_text="Lightning Bolt deals 3
  damage to any target.")` — but remember `classify_card` needs the pattern to match
  (`deals? \d+ damage to (any target|target)`), so quote canonical wordings.
- `tests.*` is mypy-exempt but write full hints anyway (matches siblings).
- Useful pinned-math cases (all derivable by hand, verified at story creation):
  `probability_at_least(deck_size=60, copies=4, drawn=7)` ≈ 0.3995;
  `copies=8` ≈ 0.6537; `copies=12` ≈ 0.8094;
  `(deck_size=99, copies=1, drawn=12)` = 12/99 ≈ 0.12121;
  `(deck_size=60, copies=24, drawn=7, min_count=2)` ≈ 0.8573 and `drawn=8` ≈ 0.9099
  (the ~91% trap pair).

## Project Structure Notes

**New/changed files:**

```text
src/
  logic/
    assessment/
      __init__.py         # MODIFIED: extend __all__ with consistency exports (additive)
      consistency.py      # NEW: FR17/FR7/FR9 — hypergeometric, redundancy, interaction
                          #      detail, structural-gap tokens
tests/
  unit/
    logic/
      test_assessment_consistency.py   # NEW: offline AC8 matrix
plugin/                                # REGENERATED mirror (commit the diff)
```

- Module name `consistency.py` matches the story's center of mass (the hypergeometric
  consistency math); filenames are seed, the boundary (pure, in `assessment/`) is the
  invariant (AD-9). If you split interaction/structure into a second module, keep both
  pure and export from `__init__.py` the same way.
- No changes to `src/logic/__init__.py`, `profiles.py`, `classifiers.py`, `mana_base.py`,
  `mana_curve.py`, `synergy.py`, `tests/fixtures/assessment.py` (unless adding a genuinely
  shared helper), or any `src/mcp_server` file.

## References

- [Source: _bmad-output/planning-artifacts/epics-deck-power-assessment.md#Story 2.5] — the
  three binding ACs (FR17 hypergeometric, FR7 interaction detail, FR9 closed-enum
  `structural_gaps[]`).
- [Source: epics-deck-power-assessment.md#Additional Requirements "Implementation constants
  (addendum §C)"] — redundancy openers 39.9%/65.4%/80.9% (4/8/12 copies).
- [Source: epics-deck-power-assessment.md#Story 2.7, #Story 2.8] — downstream consumers
  (consistency/interaction dimension mapping in 5.7; aggregate + confidence vocabulary in
  5.8) whose needs fix this story's output shapes.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-11/ARCHITECTURE-SPINE.md#AD-2, #AD-6, #AD-8, #AD-10] —
  purity, the closed `structural_gaps[]` enum rule (tokens never embed counts), bytewise
  sorted emission, one shared taxonomy (why classifiers are imported, never re-matched).
- [Source: docs/deck-assess.md:114-127] — 8×8 theory / Command Zone template / "<6 ramp or
  <6 interaction" weakness line / rule-of-8 anchors; [:154-155] — hypergeometric worked
  examples (12/99 by turn 5; the loose ~91% prose) + Karsten context; [:268-284] — the
  output-schema sketch surfacing `instant_speed_ratio`, `count`, consistency notes, and
  `structural_gaps` (Epic 7's serialization target for these signals).
- [Source: src/logic/assessment/classifiers.py:255-350] — `classify_card` (the per-card
  join promised to 5.5), `classify_deck` + `CategoryCount`, `CATEGORIES`, the WINCON_*
  tokens; [:39] — `INTERACTION` covers spot removal, counters, damage, and mass wipes
  (why no board-wipe sub-tag is needed for v1 baselines).
- [Source: src/logic/assessment/mana_base.py:33-64] — `WUBRG` fixed-shape precedent,
  `KarstenFormula` selector, Literal-keyed coefficient dicts (the pattern to copy);
  [:109-140] — `compute_curve` (land_count/spell_count you reuse, bucketing policy to cite).
- [Source: src/logic/assessment/profiles.py:32-40] — `DIMENSIONS` (consistency/interaction
  are dimensions 5.7 maps; you feed them, you don't score them).
- [Source: tests/fixtures/assessment.py] — the shared `make_card`/`make_deck_card`
  factories (G1: never a second copy).
- [Source: _bmad-output/implementation-artifacts/5-4-mana-base-curve-signals.md#Review
  Findings, #Dev Notes] — the five review findings applied proactively here (typed dicts,
  sideboard tests, both tables tested), the sideboard policy, verify-by-shape, plugin
  mirror.
- [Source: _bmad-output/project-context.md#Language-Specific Rules, #Testing Rules, #Code
  Quality] — mypy --strict / ruff / Google docstrings / pytest gates.

## Dev Agent Record

### Agent Model Used

Claude Fable 5 (claude-fable-5) via Claude Code — bmad-dev-story workflow, 2026-07-13.

### Debug Log References

- Pre-implementation verification of every pinned constant by direct `math.comb`
  computation: 60/4/7 → 0.39950, 60/8/7 → 0.65359, 60/12/7 → **0.80935** (the story
  Dev Notes' "0.8085" for 12 copies is itself slightly loose — the published 80.9%
  matches 0.809 at 1e-3, so tests pin 0.8094); 99/1/12 → 12/99 exactly; the ~91% trap
  pair confirmed as 0.8573 @ 7 seen / 0.9099 @ 8 seen.
- TDD red→green: test module written first (import failure confirmed), then
  `consistency.py` + `__init__.py` exports; 56 tests green on first implementation run.
- One test-hygiene fix: fixture helper originally named `test_oracle()` was collected
  by pytest as a test (PytestReturnNotNoneWarning) — renamed to `oracle_wincon()`.

### Completion Notes List

- `src/logic/assessment/consistency.py` implements all three signal families:
  - **FR17**: `probability_at_least` (exact `math.comb` hypergeometric, keyword-only,
    AC2 degradation precedence — `min_count<=0` checked first, then zero/negative → 0.0,
    clamps, unreachable `min_count` → 0.0; single final division for bit-identical
    floats), `OPENING_HAND_SIZE=7`, `cards_seen_by_turn` (7+turn, turn 0 = opener,
    12/99 worked example cited), `land_access_by_turn` (`min_count=turn`, so turn 0 →
    1.0 via the primitive rule — no special case; land count via 5.4's `compute_curve`,
    never re-implemented). Key-piece access is the documented primitive recipe in the
    docstring — no forwarding wrapper added.
  - **FR9 redundancy**: `RedundancySignal` frozen slots dataclass +
    `redundancy_signals` — fixed nine-tuple in `CATEGORIES` order (AD-7), counts from
    `classify_deck`, opener probability against actual deck size; rule-of-8 anchors
    fall out of the math (pinned in tests, not stored).
  - **FR7 interaction**: `InteractionSignals` + `interaction_signals` — quantity-aware
    count, instant-speed count/ratio (policy: `"instant" in type_line.lower()` OR
    `"flash"` in lowercased keywords; ratio 0.0 on zero interaction), CMC distribution
    with 5.4's exact bucketing wording (`int(cmc)` floor, front-face value).
  - **FR9 structural gaps**: the four closed AD-6 tokens (`card_draw_below_baseline`,
    `interaction_below_baseline`, `ramp_below_baseline`, `wincon_missing`) as `Final`
    constants + `STRUCTURAL_GAP_TOKENS` (defined already bytewise-sorted);
    `STRUCTURAL_GAP_BASELINES: Final[dict[KarstenFormula, dict[str, int]]]`
    (commander 6/6/6 per the "<6 ramp or <6 interaction" line; sixty_card 0/4/6 —
    ramp baseline 0 never fires; provisional, 5.9-owned, sources commented);
    `structural_gaps(deck_cards, *, formula)` with strictly-less semantics and the
    lands-exclusion note (Karsten flood/screw owns land adequacy).
- AC7 held: no classifier/profile/mana_base/fixture edits; no new categories; the
  board-wipe sub-tag decision is documented in the module docstring; `KarstenFormula`
  imported from `mana_base` (now also re-exported from the package `__init__`).
- All five 5.4 review findings applied proactively: Literal-keyed baseline dicts,
  sideboard=True test per public function, both formula tables exercised, no new
  regexes (substring/set-membership only), no bare phrase patterns.
- Gates: `ruff check` + `format` clean; `mypy --strict src/` clean (59 files);
  `uv run pytest -m "not integration"` → **875 passed** (819 baseline + 56 new);
  plugin mirror regenerated via `scripts.build_plugin` and staged in the same commit.

### File List

- `src/logic/assessment/consistency.py` (NEW)
- `src/logic/assessment/__init__.py` (MODIFIED — additive re-exports incl. `KarstenFormula`)
- `tests/unit/logic/test_assessment_consistency.py` (NEW)
- `plugin/server/src/logic/assessment/consistency.py` (REGENERATED mirror)
- `plugin/server/src/logic/assessment/__init__.py` (REGENERATED mirror)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (story status tracking)
- `_bmad-output/implementation-artifacts/5-5-consistency-interaction-structural-coverage-signals.md` (this story file)

## Change Log

- 2026-07-13: Story 5.5 implemented — FR17 hypergeometric access, FR7 interaction
  detail, FR9 redundancy + closed `structural_gaps` token enum in
  `src/logic/assessment/consistency.py`; 56 offline tests added (875 total green);
  status → review.
