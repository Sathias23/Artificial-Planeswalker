---
baseline_commit: 0e6f3982ac5c87f7a0641a8f48504742f7624ed5
---

# Story 5.4: Mana-base & curve signals

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

> **Sprint/feature numbering:** this is sprint key `5-4-mana-base-curve-signals` (`epic-5`),
> which is **feature Epic 2, Story 2.4** in
> `_bmad-output/planning-artifacts/epics-deck-power-assessment.md`. Sprint Epic 5 = feature
> Epic 2 "Deterministic scoring core".

## Story

As the scorer,
I want curve and Karsten mana math,
so that mana efficiency and consistency reflect real mana-base quality.

## Context & why this story exists

This story adds the **mana-base & curve signals** (FR5, FR8) to the pure core in
`src/logic/assessment/` — the second behavior module after 5.3's classifiers. It turns a deck's
cards into raw numeric mana signals that downstream stories consume:

- **5.5 (consistency signals)** computes hypergeometric mana access by turn N (FR17) over *this
  story's* land count, and its 8×8 structural-gap math may read the same curve numbers. The
  hypergeometric functions and the `structural_gaps[]` enum are **5.5's**, not yours.
- **5.7 (dimension vector)** maps this story's raw signals onto the integer 0–100
  `mana_efficiency` dimension (and reads curve/ramp density for `speed`). The signal→0–100
  mapping curves are **5.7/5.8's**, not yours — you emit raw values (floats/ints/booleans), not
  scores.
- **Epic 7's output** surfaces mana-base facts in the `assessment` (the `docs/deck-assess.md`
  §7.3 schema sketch shows `mana_efficiency` carrying `land_count`, `karsten_recommended`, and a
  flood-risk read). Your signal shapes are what the edge will serialize from — keep them frozen
  and deterministic.

The Karsten formulas subtract "cheap card draw + ramp" — that count is built by **joining 5.3's
classifier tags back to each card's `cmc`**, exactly the join `classify_card` was designed for
(its docstring names 5.4 as the consumer). The cheap-CMC cutoff constant is **this story's** to
define (5.3 deliberately did not pre-filter).

## Acceptance Criteria

1. **A pure mana-signals module exists in `src/logic/assessment/`.** Given AD-2 and the 5.3
   precedent, when the module (recommended: `mana_base.py`) is added, then it contains only pure
   functions over already-loaded Pydantic schemas (`Card` / `DeckCard`) with **no network, DB,
   clock, file I/O, or imports from `src/search` / `src/mcp_server` / `src/logic/mana_curve`**
   (stdlib + `src.data.schemas` + `src.logic.assessment.classifiers` only), and all result
   shapes are frozen dataclasses with deterministically ordered contents — identical input
   always yields identical output. [epics 2.4; AD-2; AD-8 spirit]

2. **FR5 curve signals.** Given a deck's cards (`Sequence[DeckCard]`, quantity-aware — the 4-of
   Standard case), when computed, then the module produces:
   - the **mana-curve distribution** (integer CMC bucket → quantity-aware count, lands
     excluded, deterministic order);
   - the **average mana value** (quantity-weighted mean of `cmc` over non-land cards), from
     `cmc` per FR5;
   - the **land count** and non-land **spell count** (quantity-aware).
   An empty or all-land input returns zeroed signals — it must **never raise** (the assessment
   path never crashes; do NOT inherit `src/logic/mana_curve.analyze_mana_curve`'s
   `ValueError`-on-empty behavior). [epics 2.4; FR5; NFR3 spirit]

3. **FR8 Karsten land-count delta → flood/screw flags.** Given the deck's signals, when
   computed, then the Karsten recommended land count is available under **both** published
   formulas — Commander `31.42 + 3.13·avgMV − 0.28·(cheap draw + ramp)` and 60-card
   `19.59 + 1.90·avgMV − 0.28·(cheap draw + ramp)` — selected by an **explicit function
   parameter** (this module stays profile-independent; the 5.7/5.8 caller picks per format).
   The result carries at least: recommended lands (float), actual lands (int), the delta
   (actual − recommended), and **`mana_screw_risk` / `mana_flood_risk` booleans** derived from
   the delta against a documented provisional tolerance constant. "Cheap card draw + ramp" is
   the quantity-aware count of non-land cards tagged `RAMP` or `CARD_DRAW` by
   `classifiers.classify_card` with `cmc <=` this story's documented cheap-CMC cutoff constant
   (Karsten's definition: cheap = MV ≤ 2); a card holding both tags counts **once** (it is one
   spell slot, not two). [epics 2.4; FR8; addendum §C]

4. **FR8 colored-source / pip consistency signals.** Given the deck's cards, when computed,
   then per-color (WUBRG) signals are produced feeding the mana-efficiency dimension:
   - **pip demand:** per color, the quantity-aware total colored-pip count across non-land
     mana costs AND the maximum pip count appearing in any single card's cost (the Karsten
     source-requirement determinant);
   - **colored sources:** per color, the quantity-aware count of Land-typed cards that can
     produce that color (detection policy per Dev Notes — basic land types in `type_line` +
     `add {c}` symbols / "add one mana of any color" in oracle text);
   - a **deterministic per-color adequacy signal** (recommended sources for the color's max
     pip intensity vs actual sources, using the Karsten anchors — 60-card: 1 pip ≈ 14 sources,
     2 pips ≈ 18 — with a documented provisional deck-size scaling for Commander), so 5.7 can
     map it without re-deriving mana math.
   Colorless-only and zero-demand colors are handled without special-casing errors (a color
   with zero pips has no deficit). [epics 2.4; FR8; docs/deck-assess.md:155]

5. **One vocabulary, no forked constants, provisional values documented.** Given AD-10 and
   AD-3, when the module is reviewed, then it **reuses 5.3's `RAMP`/`CARD_DRAW` tags** (never
   re-implements ramp/draw text patterns); all numeric constants (Karsten coefficients, cheap
   cutoff, flood/screw tolerance, pip-source anchors, deck-size scaling) are module-level
   `Final` constants, each with a comment citing its source (addendum §C / deck-assess.md) and
   marked provisional where 5.9's benchmark pass owns tuning; **no `FormatProfile` change** is
   made (format selection enters via the AC3 function parameter, keeping this story
   profile-independent — if you find yourself editing `profiles.py`, stop: that is 5.7/5.8/5.9
   territory and would force a version bump). [epics 2.4; AD-3; AD-10; NFR8]

6. **Offline unit tests prove the math on canonical decks — including exact-formula checks.**
   Given the project's testing rules, when the test module runs (no `integration` marker, no
   DB), then hand-built `Card`/`DeckCard` fixtures verify at minimum:
   - curve distribution / average MV / land count on a small mixed deck, quantity-aware
     (4-ofs count 4) with lands excluded from curve + avg MV;
   - **exact Karsten arithmetic** for both formulas on pinned inputs (e.g. avgMV 3.0 +
     10 cheap draw/ramp → Commander 31.42 + 9.39 − 2.80 = 38.01; 60-card 19.59 + 5.70 − 2.80
     = 22.49) — the coefficients are published constants, so exact-value assertions are
     appropriate here (unlike pattern lists), with tolerance-based float comparison
     (`pytest.approx`);
   - flood and screw booleans flip at the documented tolerance boundary;
   - cheap-count edge cases: a cmc-3 ramp spell is NOT cheap; a cheap card tagged both RAMP
     and CARD_DRAW counts once; a Land-typed card never counts;
   - pip parsing: `{2}{G}{G}` → 2 green pips / max 2; hybrid & Phyrexian symbols follow the
     documented policy; empty `mana_cost` (lands, MDFCs) doesn't crash and follows the
     documented multi-face policy;
   - colored-source counting: a basic Forest → G source; a typed dual (e.g. "Land — Island
     Mountain") → U and R; an "add one mana of any color" land counts for all five; a
     fetchland follows the documented policy;
   - empty-deck / all-lands / zero-spell inputs return zeroed signals without raising;
   - **determinism** (two calls on equal input produce equal results; ordered outputs).
   Tests verify **behavior and published constants**, not provisional tunables' exact values
   (tolerances/anchors may move in 5.9 — assert flags flip *at the constant*, referencing the
   module constant rather than hard-coding its value where the value is provisional). Runs
   green under `uv run pytest -m "not integration"`. [project-context#Testing Rules; 5-1/5-2
   verify-by-shape lesson]

7. **Quality gates pass — including the `src/`-touch plugin mirror.** Given this story adds
   files under `src/`, when committed, then `mypy --strict` passes (full hints, Google
   docstrings on module + public functions — the docstrings define what each signal means),
   `ruff check` + `ruff format` are clean, and the regenerated `plugin/` mirror is staged in
   the same commit (run `uv run python -m scripts.build_plugin` explicitly — the pre-commit
   hook is absent in this checkout, epic-4 action item). [project-context#Code Quality; epic-4
   retro]

## Tasks / Subtasks

- [x] **Task 1 — Design the signal surface** (AC: 1, 2, 5)
  - [x] Add `src/logic/assessment/mana_base.py` with a module docstring naming it the FR5/FR8
        mana-base & curve signal module (raw signals only; 0–100 mapping is 5.7/5.8's).
  - [x] Frozen result dataclasses (slots, the `CategoryCount` precedent), e.g. `CurveSignals`
        (distribution, average_mana_value, land_count, spell_count), `KarstenLandSignal`
        (recommended/actual/delta/flood/screw), and per-color pip/source signals (see Dev
        Notes "Recommended shape").
  - [x] One land-detection helper owning the `"land" in type_line.lower()` policy (matches
        `classifiers.py`'s `is_land` and `mana_curve.py`; document the MDFC consequence).
- [x] **Task 2 — FR5 curve signals** (AC: 2)
  - [x] `compute_curve(deck_cards)` — quantity-aware buckets over `int(card.cmc)` for
        non-lands, quantity-weighted average MV, land/spell counts; zero-safe on empty input.
- [x] **Task 3 — FR8 Karsten land delta** (AC: 3, 5)
  - [x] `CHEAP_DRAW_RAMP_CMC_MAX: Final = 2` (Karsten's cheap definition) + a cheap-count
        helper joining `classify_card` tags to `cmc`, counting a dual-tagged card once,
        excluding lands.
  - [x] Both formula coefficient sets as `Final` constants (addendum §C values verbatim);
        `karsten_land_delta(deck_cards, formula=...)` with an explicit
        `Literal["commander", "sixty_card"]`-style selector.
  - [x] Provisional flood/screw tolerance constant (recommend ±2 lands to start) + the two
        booleans; comment that 5.9 owns tuning.
- [x] **Task 4 — FR8 pip demand & colored sources** (AC: 4, 5)
  - [x] Pip parser over `mana_cost` (compiled regex over `{...}` symbols): plain colored pips
        per WUBRG color; documented policy for hybrid/Phyrexian/twobrid (recommend: excluded
        from hard pip demand, v1) and for empty top-level `mana_cost` with `card_faces`
        (recommend: front face's `mana_cost`, consistent with Scryfall's front-face `cmc`).
  - [x] Colored-source detection over Land-typed cards: basic land-type words in `type_line`
        + `add {c}` colored symbols in lowercased oracle text + "add one mana of any color" →
        all five colors. Document what's out (fetchlands, "commander's color identity" text —
        accepted v1 undercount).
  - [x] Karsten source anchors as constants (60-card: 14/1-pip, 18/2-pip from
        deck-assess.md:155; extrapolate a documented provisional 3+-pip anchor and a
        deck-size scaling rule for 99-card) → per-color adequacy signal.
- [x] **Task 5 — Package exports** (AC: 1)
  - [x] Re-export public names from `src/logic/assessment/__init__.py` (extend `__all__`
        additively; do not touch `src/logic/__init__.py` or `profiles.py`).
- [x] **Task 6 — Offline unit tests** (AC: 6)
  - [x] Promote 5.3's `make_card` / `make_deck_card` factories from
        `tests/unit/logic/test_assessment_classifiers.py` into a shared
        `tests/fixtures/assessment.py` (or similar) and import them from **both** test
        modules in the same commit — do not create a second copy (the `_FakeEmbedder`
        five-copies lesson, pre-epic-3 gate G1).
  - [x] Add `tests/unit/logic/test_assessment_mana_base.py` covering the AC6 matrix; failure
        messages name the card/signal.
- [x] **Task 7 — Quality gates + plugin mirror** (AC: 7)
  - [x] `uv run ruff check . --fix && uv run ruff format .`
  - [x] `uv run mypy src/` (strict) — full hints on all new functions.
  - [x] `uv run pytest -m "not integration"` green (baseline: **777 passed** at story start).
  - [x] Commit with the regenerated `plugin/` mirror staged (`uv run python -m
        scripts.build_plugin`; hook absent). Never `--no-verify`.

### Review Findings

- [x] [Review][Patch] `_ANY_COLOR_PHRASE` substring match overcounts conditional fixing lands as unconditional 5-color sources — `src/logic/assessment/mana_base.py:941` (`_land_source_colors`). The Dev Notes accept Command Tower's "...in your commander's color identity" as a known false positive, but the same bare substring also matches real, commonly-played *conditional* lands such as Reflecting Pool ("Add one mana of any color **that a land you control could produce**"), which is a materially different and broader miscount than the one case the story calls out. Decision (Brad, 2026-07-12): tighten the detection to exclude conditional grants rather than accept the broader imprecision.
- [x] [Review][Patch] `_FORMULA_COEFFICIENTS` / `_FORMULA_ANCHORS` are typed `dict[str, ...]` and looked up with an unchecked `[formula]` in both `karsten_land_delta` and `compute_pip_signals` [src/logic/assessment/mana_base.py]. `KarstenFormula` isn't enforced at runtime, so an unexpected string raises an uncaught `KeyError`, undermining the module's own "must degrade, never raise" framing. Retype the dicts as `dict[KarstenFormula, ...]` for static protection; no test currently exercises an invalid `formula`.
- [x] [Review][Patch] No test constructs a `sideboard=True` `DeckCard` for `compute_curve`/`karsten_land_delta`/`compute_pip_signals` [tests/unit/logic/test_assessment_mana_base.py], unlike the 5.3 precedent (`test_sideboard_cards_are_not_filtered`). Code behavior is correct (none of the three functions reference `sideboard`), but a future regression that starts filtering would go unnoticed.
- [x] [Review][Patch] Basic-land-type detection (`subtype in type_line`) [src/logic/assessment/mana_base.py:943, `_land_source_colors`] has no word-boundary guard, unlike the sibling `add {color}` regex which uses `\b`. Low realistic risk but inconsistent within the same file.
- [x] [Review][Patch] The 3+-pip anchor cap is only asserted for the `sixty_card` table (`test_three_plus_pips_use_the_top_anchor`) [tests/unit/logic/test_assessment_mana_base.py] — no equivalent test covers the `commander` table's top anchor (33).

## Dev Notes

### What this story is — and is NOT

- **IS:** one new pure module of curve/Karsten/pip signal functions + frozen result shapes +
  offline tests + `assessment/__init__.py` re-exports + the shared test-factory promotion.
- **IS NOT:** any signal→0–100 mapping or dimension score (5.7), aggregate weighting (5.8),
  hypergeometric probability math (5.5 — FR17; the Karsten source anchors here are static
  published constants, not computed probabilities), `structural_gaps[]` tokens (5.5),
  `FormatProfile` edits (AC5), confidence tokens (5.8), or tool/skill-layer code. If a
  function needs a `FormatProfile`, a DB, or combo data — it belongs to a later story.

### Do NOT reuse `src/logic/mana_curve.py` — compute fresh (decided; here's why)

`src/logic/mana_curve.py::analyze_mana_curve` (the Epic-1 `analyze_mana_curve` tool's engine)
already computes curve/avg-CMC/land-count — but it is the wrong dependency for the assessment
core, deliberately:

- it takes `list[Card]` with **duplicates for quantity** (the tool layer expands
  `range(dc.quantity)`), while the assessment core's established input is quantity-aware
  `Sequence[DeckCard]` (5.3 precedent);
- it **raises `ValueError` on an empty deck** — the assessment path must degrade, never crash
  (AD-6/NFR3 spirit);
- it returns prose `issues`/`recommendations` strings and coaching feedback — human-phrased
  output that must not leak into the deterministic diff surface (AD-8: phrasing only in
  `summary`, produced at the edge);
- its land-ratio thresholds (38–42%) are a different, coarser heuristic than the Karsten
  formulas FR8 mandates.

This mirrors 5.3's `synergy.py` decision: the legacy module keeps serving its own tool;
consolidation is explicitly out of scope. Add a module-docstring note in `mana_base.py`
cross-referencing `src/logic/mana_curve.py` and stating the deliberate independence, so a
reviewer doesn't flag it as reinvention. **Do not import it** (AC1).

### Consuming 5.3's classifiers (the intended join)

```python
from src.logic.assessment.classifiers import CARD_DRAW, RAMP, classify_card
```

Cheap draw+ramp count (Karsten's `0.28` term), per the 5.3 handoff contract:

```python
cheap = 0
for dc in deck_cards:
    if _is_land(dc.card):          # lands are never spell slots
        continue
    if dc.card.cmc <= CHEAP_DRAW_RAMP_CMC_MAX and (
        classify_card(dc.card) & {RAMP, CARD_DRAW}
    ):
        cheap += dc.quantity        # one spell slot even if tagged both (AC3)
```

`classify_card` is pure and unmemoized — calling it once per deck card here is fine (the
deferred 5.3 memoization note only concerns callers invoking multiple deck-level detectors
back-to-back; you make one pass).

### Decide-once policies (document each at its code site)

- **Land detection = `"land" in type_line.lower()`** — the `classifiers.py` / `mana_curve.py`
  convention. Consequence: an MDFC "Creature // Land" counts as a land and is excluded from
  the curve/avg-MV — consistent with 5.3's conservative "land-slot material" reading of the
  `//`-joined `type_line` (`classifiers.py:273-277`). Accept it for v1; note it.
- **`cmc` semantics:** `Card.cmc` is `float` and, per Scryfall, is the **front face's** value
  for multi-face cards; bucket with `int(cmc)` (floor — fractional cmc exists only on un-set
  cards). `cmc` is non-nullable in the schema; no None-guard needed.
- **`mana_cost` traps (verified in schema/transformers):** `Card.mana_cost` is never `None`
  (schema coerces NULL → `""`, `src/data/schemas/card.py:72`) but IS `""` for lands and most
  multi-face cards, and split cards store `"{1}{G} // {2}{U}"`-style joined costs. Policy
  (recommended): when top-level `mana_cost` is empty and `card_faces` exist, parse the **first
  face's** `mana_cost` (`face.get("mana_cost") or ""` — the 5.3 null-face lesson: Scryfall
  face fields can be explicitly `null`, so `or ""`, never a `.get(..., "")` default); a joined
  " // " cost parses as written (mild double-count on split cards, accepted v1).
- **Hybrid `{G/U}`, Phyrexian `{G/P}`, twobrid `{2/W}`:** recommend excluding from hard pip
  demand in v1 — each is payable without that color's source, so counting them as hard pips
  overstates the requirement. Monocolor pips `{W}`…`{G}` only. Document; 5.9 tunes.
- **Colored-source detection (no `produced_mana` field exists — verified):** the `Card`
  schema/DB has no produced-mana column, so derive from Land-typed cards:
  1. **basic land types in `type_line`** — `Plains→W, Island→U, Swamp→B, Mountain→R,
     Forest→G` (catches basics, snow basics, and typed nonbasics like shocks
     "Land — Island Mountain"; use the subtype word, not the card name);
  2. **`add {w}`/`{u}`/`{b}`/`{r}`/`{g}` symbols in lowercased oracle text** (pain lands,
     duals without basic types). Use the **raw** lowercased `oracle_text` — do NOT re-use
     5.3's reminder-stripping `_match_text` here: a basic's entire mana ability is reminder
     text ("({T}: Add {G}.)") and stripping it is harmless only because rule 1 covers
     basics, while for other lands reminder text about mana is accurate, not a
     false-positive source;
  3. **"add one mana of any color"** → counts as a source for all five colors (Command
     Tower-style "of any color in your commander's color identity" also matches this
     substring — acceptable).
  Accepted v1 undercounts (document): fetchlands (produce nothing themselves), lands whose
  production text uses other wordings, and **non-land sources** (dorks/rocks — Karsten's
  primary tables count lands; extending to rocks is a 5.9 calibration option).
- **Sideboard rows are NOT filtered** — the 5.3 policy: deck-composition belongs to the
  caller/edge. Add the same one-line caveat 5.3's review added to its detectors: a caller
  wanting played-cards-only signals filters `sideboard=False` first.
- **Karsten source anchors:** 60-card values from the research doc (1 pip ≈ 14, 2 pips ≈ 18,
  `docs/deck-assess.md:155`); define a provisional 3+-pip anchor (recommend ≈ 20) and a
  provisional Commander scaling (recommend `× deck_size_factor` derived from 99/60, i.e.
  ~23/30/33 — Karsten's real Commander tables differ, but a documented linear scale is an
  honest v1 the benchmark pass can replace). Mark all of these provisional-5.9-tunes.

### Recommended shape (guidance, not a straitjacket)

```python
# mana_base.py — sketch
CHEAP_DRAW_RAMP_CMC_MAX: Final = 2          # Karsten: "cheap" = MV <= 2 (addendum §C)
KARSTEN_TOLERANCE_LANDS: Final = 2.0        # provisional flood/screw band; 5.9 tunes

@dataclass(frozen=True, slots=True)
class CurveSignals:
    distribution: tuple[tuple[int, int], ...]   # (cmc_bucket, count), sorted by bucket
    average_mana_value: float                   # 0.0 when no spells
    land_count: int
    spell_count: int

@dataclass(frozen=True, slots=True)
class KarstenLandSignal:
    recommended_lands: float
    actual_lands: int
    delta: float                                # actual - recommended
    cheap_draw_ramp_count: int                  # the 0.28-term input, surfaced for NFR2
    mana_screw_risk: bool                       # delta < -tolerance
    mana_flood_risk: bool                       # delta > +tolerance

@dataclass(frozen=True, slots=True)
class ColorPipSignal:
    color: str                                  # "W" | "U" | "B" | "R" | "G" (WUBRG order)
    pip_count: int                              # quantity-weighted total pips in costs
    max_pips_single_card: int                   # Karsten requirement determinant
    source_count: int                           # lands producing this color
    recommended_sources: int                    # 0 when no demand
    deficit: int                                # max(0, recommended - actual)

def compute_curve(deck_cards: Sequence[DeckCard]) -> CurveSignals: ...
def karsten_land_delta(
    deck_cards: Sequence[DeckCard], *, formula: Literal["commander", "sixty_card"]
) -> KarstenLandSignal: ...
def compute_pip_signals(
    deck_cards: Sequence[DeckCard], *, formula: Literal["commander", "sixty_card"]
) -> tuple[ColorPipSignal, ...]: ...
    # always all five colors, WUBRG order — fixed closed shape, AD-7 spirit;
    # `formula` selects the source-anchor table (60-card anchors vs the scaled
    # Commander anchors, AC4) exactly like karsten_land_delta's selector
```

Why this shape: `distribution` as a sorted tuple (not a dict) keeps the output hashable and
order-deterministic; surfacing `cheap_draw_ramp_count` and `recommended_lands` gives Epic 7
the explainability payload (`karsten_recommended` in the deck-assess schema sketch) without
recomputation; the fixed five-color tuple mirrors AD-7's fixed-shape discipline (no
colors-present-conditional keys). WUBRG order matches the project convention
(project-context: color codes sorted WUBRG). Emitting both the raw delta and the booleans
lets 5.7 map graded severity while FR8's flags stay available as-is.

### Determinism discipline (AD-8 spirit, applied early)

Sorted/fixed-order tuples everywhere, no set/dict-ordering in outputs, floats computed by the
same expression path every time (pure arithmetic on the same inputs is deterministic — no
`random`, no clock). Note 5.7 will eventually round to int 0–100; you keep raw floats.

### Layer & purity rules (AD-2, project-context)

- Allowed imports: stdlib (`re`, `dataclasses`, `typing`, `collections.abc`) +
  `src.data.schemas.card` / `src.data.schemas.deck` + `src.logic.assessment.classifiers`.
  Forbidden: `src/search`, `src/mcp_server`, `src/data/repositories`, `src/logic/mana_curve`,
  Pydantic models of your own (frozen dataclasses, the package convention).
- Python 3.12 syntax (`X | None`, builtin generics, `Final`, `Literal`); compiled regexes as
  module constants; Google docstrings on module + every public function; module docstring
  required.
- Pure functions — no logging needed.

### Previous-story intelligence (5.3, just completed)

- The classifier surface you consume: `classify_card(card) -> frozenset[str]` (tags include
  `RAMP`, `CARD_DRAW`), `classify_deck` (don't need it here), tokens re-exported from
  `src.logic.assessment`. Land-typed cards already never get `RAMP`.
- **Null-face lesson (5.3 review patch):** `card_faces` entries can carry an explicit
  `oracle_text: null` / `mana_cost: null` — always `face.get(key) or ""`, never
  `face.get(key, "")`.
- **Verify-by-shape lesson (5.1→5.3):** exact-value asserts are right for *published*
  constants (Karsten coefficients — that's the AC6 carve-out) and wrong for *provisional*
  tunables (tolerance, anchors, scaling) — test those by referencing the module constant so
  5.9 tuning doesn't shred tests.
- **Plugin mirror:** `.git/hooks/pre-commit` is absent in this checkout — run
  `uv run python -m scripts.build_plugin` explicitly and stage
  `plugin/server/src/logic/assessment/` in the same commit. Line-ending-only `plugin/*.json`
  diffs are noise; don't chase them.
- **Fast-suite baseline: 777 passed** (verified at story-creation time, post-5.3-review).
- 5.3's deferred findings (detector memoization, `classify_card` frozenset ordering) are not
  yours to fix.

### Testing standards

- pytest config in `pyproject.toml`: `asyncio_mode="auto"`, `--strict-markers`, `--tb=short`;
  these tests are synchronous, no markers, run in the `-m "not integration"` fast subset.
- Flat placement `tests/unit/logic/test_assessment_mana_base.py` beside the two existing
  assessment test modules (three flat files is still fine; the `tests/unit/logic/assessment/`
  subdir move remains deferred until the layout gets unwieldy — if you do move, move all
  three in the same commit).
- **Factory promotion (Task 6):** `make_card` / `make_deck_card` currently live inside
  `test_assessment_classifiers.py:37-67`. Move them to a shared fixtures module
  (`tests/fixtures/` is the established home — see `tests/fixtures/card_data.py`,
  `tests/fixtures/embedder.py` from the G1 consolidation) and update the 5.3 test module's
  imports in the same commit. Do not import from another test module and do not duplicate.
- `tests.*` is mypy-exempt but write full hints anyway (matches siblings).
- Useful pinned-math cases: Commander formula at avgMV 3.0 / cheap 10 → 38.01; 60-card →
  22.49 (`pytest.approx`); a 24-land 36-spell 60-card deck around avgMV 2.5 lands near the
  Karsten-recommended range (sanity, not exact).

## Project Structure Notes

**New/changed files:**

```text
src/
  logic/
    assessment/
      __init__.py       # MODIFIED: extend __all__ with mana-base exports (additive)
      mana_base.py      # NEW: FR5/FR8 signals — curve, Karsten land delta, pip/source math
tests/
  fixtures/
    assessment.py       # NEW: make_card / make_deck_card promoted from the 5.3 test module
  unit/
    logic/
      test_assessment_classifiers.py  # MODIFIED: import factories from tests/fixtures
      test_assessment_mana_base.py    # NEW: offline curve/Karsten/pip behavior tests
plugin/                               # REGENERATED mirror (commit the diff)
```

- Module name `mana_base.py` matches the epic's "Mana-base & curve signals" title; filenames
  are seed, the boundary (pure, in `assessment/`) is the invariant (AD-9).
- No changes to `src/logic/__init__.py`, `profiles.py`, `classifiers.py`, `mana_curve.py`,
  `synergy.py`, or any `src/mcp_server` file.

## References

- [Source: _bmad-output/planning-artifacts/epics-deck-power-assessment.md#Story 2.4] — the
  three binding ACs (FR5 curve/avgMV/lands, FR8 Karsten delta → flags, pip consistency).
- [Source: epics-deck-power-assessment.md#Additional Requirements "Implementation constants
  (addendum §C)"] — the exact Karsten coefficients this story encodes.
- [Source: epics-deck-power-assessment.md#Story 2.5, #Story 2.7] — downstream consumers
  (hypergeometric/structural in 5.5; mana_efficiency + speed mapping in 5.7) whose needs fix
  this story's output shapes.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-11/ARCHITECTURE-SPINE.md#AD-2, #AD-3, #AD-8, #AD-10] —
  purity, profile-as-passive-data (why no profiles.py edit), deterministic outputs, one
  shared taxonomy (why classifiers are imported, never re-matched).
- [Source: docs/deck-assess.md:125] — Karsten land formulas + flag-on-deviation intent;
  [docs/deck-assess.md:155] — colored-source anchors (14/1-pip, 18/2-pip, 60-card) and
  per-format land baselines; [docs/deck-assess.md:269] — the output-schema sketch showing
  `land_count`/`karsten_recommended`/flood-risk surfaced under mana_efficiency.
- [Source: src/logic/assessment/classifiers.py] — `classify_card`, `RAMP`/`CARD_DRAW` tokens,
  the land-in-type_line policy (`:273-277`), the null-face `or ""` lesson (`:95-114`).
- [Source: src/logic/assessment/profiles.py] — the frozen-dataclass conventions and the AD-3
  bump rule this story must not trigger.
- [Source: src/logic/mana_curve.py] — the legacy curve engine deliberately NOT reused (Dev
  Notes rationale: duplicate-expansion input shape, ValueError on empty, prose output).
- [Source: src/data/schemas/card.py:26-88] — `mana_cost`/`cmc`/`type_line` types + NULL
  coercions (`mana_cost` never None, may be `""`); no produced-mana field exists.
- [Source: src/data/schemas/deck.py:14-35] — `DeckCard.quantity` (≥1) / `sideboard` / nested
  `card`.
- [Source: tests/unit/logic/test_assessment_classifiers.py:37-67] — the `make_card` /
  `make_deck_card` factories to promote; [tests/fixtures/embedder.py precedent] — the G1
  "consolidate before the second copy" lesson (deferred-work.md, pre-epic-3 gate).
- [Source: _bmad-output/implementation-artifacts/5-3-shared-oracle-text-classifiers.md] —
  previous-story conventions: package exports, plugin mirror, verify-by-shape, sideboard
  policy, cheap-cutoff handoff ("The cheap-cmc cutoff constant is 5.4's").
- [Source: _bmad-output/project-context.md#Language-Specific Rules, #Testing Rules, #Code
  Quality] — mypy --strict / ruff / Google docstrings / pytest gates / WUBRG ordering.

## Dev Agent Record

### Agent Model Used

Claude Fable 5 (claude-fable-5) via Claude Code

### Implementation Plan

Three TDD red-green cycles, one per signal family, each test-first against the shared
promoted factories:

1. **Factory promotion first** (Task 6 prerequisite): moved `make_card`/`make_deck_card`
   verbatim from `test_assessment_classifiers.py` to `tests/fixtures/assessment.py`, updated
   the 5.3 module's imports, re-ran its 48 tests green before any new code.
2. **Cycle 1 — curve (Tasks 1+2):** wrote `TestComputeCurve` (8 tests) → RED (ImportError) →
   implemented `_is_land`, `CurveSignals`, `compute_curve` + `__init__.py` exports → GREEN.
3. **Cycle 2 — Karsten delta (Task 3):** wrote `TestKarstenLandDelta` (8 tests, including the
   pinned 38.01/22.49 arithmetic and tolerance-boundary flips computed FROM
   `KARSTEN_TOLERANCE_LANDS`) → RED → implemented coefficient constants,
   `_cheap_draw_ramp_count` (the `classify_card` join), `karsten_land_delta` → GREEN.
4. **Cycle 3 — pips/sources (Tasks 4+5):** wrote `TestPipDemand`/`TestColoredSources`/
   `TestPipAdequacy` (21 tests) → RED → implemented `_MANA_SYMBOL_RE` pip parser,
   `_pip_cost` front-face fallback, `_land_source_colors` (basic types + `add {c}` symbols +
   any-color phrase), anchor tables, `compute_pip_signals` → GREEN.

Key decisions (all documented at their code sites): exact-symbol-match pip counting makes
hybrid/Phyrexian/twobrid exclusion structural (they contain `/`, so `symbol == color` never
matches); source-text detection reuses 5.3's join-all-faces fallback but deliberately WITHOUT
reminder-stripping (a basic's whole mana ability is reminder text); Commander anchors are the
60-card anchors linearly scaled by 99/60 (23/30/33), marked provisional for 5.9.

### Debug Log References

No debugging required — every RED failed for the expected reason (missing import/function)
and every GREEN passed on first run after implementation. One test fixture was corrected
during the pip RED phase before implementation: the front-face-cost test initially used an
`Instant // Land` type line, which the land-detection policy correctly excludes from pip
demand — replaced with a transform DFC (non-land) and added a companion test pinning the
land-MDFC exclusion as documented behavior.

### Completion Notes List

- `src/logic/assessment/mana_base.py` delivers all three FR5/FR8 signal families as pure
  functions over `Sequence[DeckCard]`: `compute_curve` → `CurveSignals`,
  `karsten_land_delta(…, formula=…)` → `KarstenLandSignal`, `compute_pip_signals(…,
  formula=…)` → fixed five-tuple of `ColorPipSignal` in WUBRG order. All result shapes are
  frozen slots dataclasses; empty/all-land input degrades to zeroed signals, never raises.
- Karsten coefficients encoded verbatim from addendum §C and asserted exactly
  (31.42/3.13/0.28 and 19.59/1.90/0.28); pinned-math tests verify 38.01 (Commander) and
  22.49 (60-card) via `pytest.approx`.
- Provisional tunables (`KARSTEN_TOLERANCE_LANDS = 2.0`, 3+-pip anchor 20, Commander anchor
  scaling 23/30/33) are `Final` constants commented as 5.9-owned; tests reference the
  constants rather than hard-coding values (verify-by-shape).
- Cheap draw/ramp count joins 5.3's `classify_card` tags to `cmc <= CHEAP_DRAW_RAMP_CMC_MAX`
  (2); dual-tagged cards count once per copy; lands never count. No pattern re-implementation.
- No changes to `profiles.py`, `src/logic/__init__.py`, `classifiers.py`, `mana_curve.py`,
  or any MCP-server file. `assessment/__init__.py` extended additively.
- Factories promoted to `tests/fixtures/assessment.py`; both assessment test modules import
  from it (no second copy).
- Gates: `ruff check`/`format` clean, `mypy --strict` clean (58 files), fast suite
  **814 passed** (777 baseline + 37 new), plugin mirror regenerated and staged.

### File List

- `src/logic/assessment/mana_base.py` (NEW)
- `src/logic/assessment/__init__.py` (MODIFIED — additive exports)
- `tests/fixtures/assessment.py` (NEW — promoted factories)
- `tests/unit/logic/test_assessment_classifiers.py` (MODIFIED — import factories from fixtures)
- `tests/unit/logic/test_assessment_mana_base.py` (NEW)
- `plugin/server/src/logic/assessment/mana_base.py` (NEW — regenerated mirror)
- `plugin/server/src/logic/assessment/__init__.py` (MODIFIED — regenerated mirror)
- `_bmad-output/implementation-artifacts/5-4-mana-base-curve-signals.md` (MODIFIED — story tracking)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (MODIFIED — status transitions)

## Change Log

- 2026-07-12: Story 5.4 implemented — FR5 curve signals, FR8 Karsten land delta +
  flood/screw flags, FR8 per-color pip/source adequacy signals; shared test factories
  promoted to `tests/fixtures/assessment.py`; 37 new offline tests (fast suite 814 passed);
  status → review.
