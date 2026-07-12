---
baseline_commit: 8b6ecd9
---

# Story 5.2: `FormatProfile` frozen-data module

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

> **Sprint/feature numbering:** this is sprint key `5-2-format-profile-frozen-data-module`
> (`epic-5`), which is **feature Epic 2, Story 2.2** in
> `_bmad-output/planning-artifacts/epics-deck-power-assessment.md`. Sprint Epic 5 = feature Epic 2
> "Deterministic scoring core".

## Story

As the scorer,
I want per-format constants in one passive typed data bag,
so that scoring behavior is versioned and tunable without code branching.

## Context & why this story exists

This story **creates the `src/logic/assessment/` package** — the pure functional core the entire
rest of Epic 5 lives in (AD-2) — and populates it with its first module: the `FormatProfile`
frozen-data module (AD-3, FR4). Story 5.1 deliberately did *not* create this package ("that
package is Story 5.2's to create" — 5-1 story file, Task 1). Every later Epic-5 story reads this
profile:

- **5.3–5.5** (classifiers, Karsten math, consistency) produce signals; the **per-dimension
  mapping parameters** that turn those signals into 0–100 live here.
- **5.7** (dimension vector + Bracket floor) branches on the **rubric selector**
  (`brackets | heuristic_only`) and reads the **expected-win-turn band** for `speed`.
- **5.8** (aggregate + tier label + Standard fork) reads the **aggregate weights** and will read
  label thresholds from this module (see Scope boundary below).
- **5.9** (benchmark validation) **hand-tunes the values in this module** until the benchmark
  passes — "Adjusting weights = edit module + bump version + re-run benchmark" (AD-3).
- **Epic 7's edge** selects a profile by resolved format, branches combo provisioning on
  `combos_enabled` (Story 4.2), emits `format_profile_version` in `data_vintage` (FR4/FR22), and
  emits the multiplayer-variance `summary` caveat when `multiplayer_variance_caveat` is set (AD-6).

The point of AD-3 is **no scattered magic numbers and no per-format strategy classes**: one
passive, typed, frozen, versioned data bag per format; one scorer that reads and branches on it.

## Acceptance Criteria

1. **The `src/logic/assessment/` package exists with a profile module of typed frozen constants.**
   Given AD-3, when the module is created in `src/logic/assessment` (new package: `__init__.py` +
   a `profiles.py` module — see Project Structure Notes), then it defines a typed **frozen**
   `FormatProfile` shape (stdlib `@dataclass(frozen=True, slots=True)` — the `deck_import.py:79` /
   `search/query.py:54` precedent) and exactly two module-level profile constants: a `commander`
   profile and a `standard` profile. [epics 2.2; AD-3]

2. **Each profile carries the AC-mandated fields, fully typed.** Given FR4 and AD-3, when a
   profile is defined, then it carries at minimum:
   - `rubric: Literal["brackets", "heuristic_only"]` — `"brackets"` for commander,
     `"heuristic_only"` for standard (FR18/FR20 fork selector);
   - an **expected-win-turn band** (e.g. `win_turn_band: tuple[int, int]`, lo ≤ hi) — feeds the
     `speed` dimension in 5.7;
   - **aggregate weights** covering **exactly the closed 7-dimension key set**
     `speed, consistency, resilience, interaction, mana_efficiency, card_advantage,
     combo_potential` (AD-7) — no missing key, no extra key, enforceable at type level (see Dev
     Notes for the recommended shape);
   - **per-dimension mapping parameters** — the typed *slots* for the signal→0–100 curves (NFR8);
     initial values provisional (see AC5);
   - flags `combos_enabled: bool` and `multiplayer_variance_caveat: bool` — the caveat drives a
     fixed `summary` caveat at the edge and is **never** a confidence reason (AD-3, AD-6);
   - `format_profile_version: str` — a **monotonic** version string per format (FR4), emitted
     later in `data_vintage` (AD-7).
   The profile claims **no data versions** — no Game-Changer-list version, no combo-snapshot
   version; vintage belongs to the imported snapshots (AD-3, AD-7). [epics 2.2; AD-3; AD-7]

3. **The profile is a passive data bag — no behavior.** Given AD-3, when the module is reviewed,
   then `FormatProfile` has **no methods, no properties with logic, no `__post_init__`
   computation beyond validation, no callables stored in fields** — the scorer (later stories)
   reads and branches on it; the profile never scores anything. [epics 2.2; AD-3]

4. **It is an in-repo Python constants module — and deeply immutable.** Given AD-3 and AD-2, when
   values are stored, then they are Python constants in the repo (not an external JSON/YAML data
   file, not inline literals scattered in scorer code), every container field is **immutable**
   (`tuple` / nested frozen dataclass / `Mapping` view — never a bare mutable `dict`/`list`
   field), and the module performs **no I/O, no clock, no network, no DB access** at import time
   or ever (AD-2 — this module must be importable by a pure core). [epics 2.2; AD-2; AD-3]

5. **Initial values are provisional, documented, and honest about it.** Given the spine's Deferred
   section ("actual dimension signal→0–100 mapping curves + aggregate weight values … owned by
   first-implementation/calibration"), when initial values are chosen, then each carries a short
   rationale comment citing its source where one exists (deck-assess/addendum §C — e.g.
   expected-win-turn bands from format research), weights are normalized to a documented total
   (e.g. sum to `1.0` or `100`), and the module docstring states plainly that **Story 5.9 owns
   hand-tuning these values against the calibration benchmark** (NFR8) and that any value change
   requires a `format_profile_version` bump. Do NOT attempt benchmark calibration in this story.
   [ARCHITECTURE-SPINE#Deferred; NFR8; addendum §C]

6. **An offline unit test proves shape, domains, and immutability — by shape, not magic numbers.**
   Given the project's testing rules and the 5.1 "verify by shape" lesson, when the test module
   runs (no `integration` marker, no DB/model/network), then it asserts: both profiles exist and
   are instances of `FormatProfile`; mutating any field raises (`FrozenInstanceError`); the weight
   key set equals the canonical 7 dimensions exactly; weights are non-negative and sum to the
   documented total (within float tolerance); `rubric` values are in the allowed domain and differ
   correctly per format (`commander="brackets"`, `standard="heuristic_only"`);
   `win_turn_band` lo ≤ hi; `format_profile_version` is a non-empty string;
   `multiplayer_variance_caveat` is `True` for commander and `False` for standard. **No test
   asserts a specific weight/parameter number** (those are 5.9's to tune — a hardcoded
   `weights.speed == 0.2` assertion would break every calibration pass). It runs green under
   `uv run pytest -m "not integration"`. [project-context#Testing Rules; 5-1 AC6 lesson]

7. **Quality gates pass — including the `src/`-touch plugin mirror.** Given this story adds files
   under `src/` (unlike 5.1), when committed, then `mypy --strict` passes over the new module
   (full type hints, module + class Google docstrings), `ruff check` + `ruff format` are clean,
   and the **`build-plugin-sync` pre-commit hook regenerates `plugin/`** — the rebuilt `plugin/`
   tree must be staged in the same commit (the hook fails the commit until you re-add it; do not
   bypass with `--no-verify`). [project-context#Code Quality; epic-4 retro action item 2;
   .pre-commit-config.yaml:24-33]

## Tasks / Subtasks

- [x] **Task 1 — Create the `src/logic/assessment/` package** (AC: 1)
  - [x] Add `src/logic/assessment/__init__.py` with a module docstring naming the package as the
        pure deterministic scoring core (AD-2: no network, DB, or clock) and re-exporting the
        profile public names (`FormatProfile`, `COMMANDER_PROFILE`, `STANDARD_PROFILE`, plus the
        canonical dimension tuple) — mirror `src/logic/__init__.py`'s docstring + `__all__` style.
  - [x] Do **not** modify `src/logic/__init__.py`'s existing exports (later stories may surface
        assessment names there if needed; keep this story additive).

- [x] **Task 2 — Define the canonical dimension key set** (AC: 2)
  - [x] Define the closed 7-key dimension set once, in order, as a module-level constant, e.g.
        `DIMENSIONS: tuple[str, ...] = ("card_advantage", "combo_potential", "consistency",
        "interaction", "mana_efficiency", "resilience", "speed")` — or in the AD-7 listing order;
        pick one and document it. This is the AD-7 fixed closed key set; 5.7's vector and 5.8's
        aggregate will import it from here so the key set can never fork.
  - [x] Recommended: enforce the closed set at type level with a nested
        `@dataclass(frozen=True, slots=True) class DimensionWeights` holding exactly seven
        `float` fields named after the dimensions — mypy then makes a missing/extra key a type
        error, not a runtime surprise. (A `Mapping[str, float]` is acceptable but weaker; if used,
        the frozen check in AC6 must cover it and the docstring must state the key contract.)

- [x] **Task 3 — Define `FormatProfile` and the two profile constants** (AC: 2, 3, 4, 5)
  - [x] `@dataclass(frozen=True, slots=True) class FormatProfile` with full type hints and a
        Google-style docstring documenting every field (match `search/query.py` `CardHit`'s
        attribute-docs style).
  - [x] Fields per AC2: `format_profile_version: str`, `rubric: Literal[...]`,
        `win_turn_band: tuple[int, int]`, `weights: DimensionWeights`, per-dimension mapping
        parameters (typed, immutable — a nested frozen dataclass per dimension family or a single
        flat frozen dataclass; keep it simple, it will be reshaped by 5.3–5.8 as real curves
        land), `combos_enabled: bool`, `multiplayer_variance_caveat: bool`.
  - [x] `COMMANDER_PROFILE: Final[FormatProfile]` — `rubric="brackets"`, `combos_enabled=True`,
        `multiplayer_variance_caveat=True`, provisional win-turn band (documented; deck-assess
        research suggests casual-Commander expected wins around turns 7–10),
        `format_profile_version` initial value (e.g. `"commander-v1"`).
  - [x] `STANDARD_PROFILE: Final[FormatProfile]` — `rubric="heuristic_only"`,
        `multiplayer_variance_caveat=False`, provisional win-turn band (e.g. ~turns 5–8,
        documented), `format_profile_version` initial value (e.g. `"standard-v1"`).
        For `combos_enabled` see Dev Notes ("Standard `combos_enabled`") — set `True` per the
        literal FR20 reading and document the choice at the field site.
  - [x] Provisional weights: hand-pick a documented, normalized starting spread (e.g. Commander
        weighting consistency/combo_potential/resilience meaningfully; Standard weighting
        speed/interaction/mana_efficiency per FR20's curve/interaction/Karsten-60 emphasis).
        Comment each with its rationale and the "5.9 owns tuning" pointer.
  - [x] Module docstring: state AD-3's contract (passive data bag; edit → bump version → re-run
        benchmark), the no-data-versions rule, and the 5.9 tuning ownership.

- [x] **Task 4 — Offline unit test** (AC: 6)
  - [x] Add `tests/unit/logic/test_assessment_profiles.py` (flat in the existing
        `tests/unit/logic/` dir — see Project Structure Notes). No `integration` marker.
  - [x] Assert the AC6 checks (shape, frozen-ness, weight-key closure vs `DIMENSIONS`, weight
        normalization within tolerance, rubric domain + per-format values, band ordering,
        non-empty version, caveat flags). Make failures name the offending profile/field.
  - [x] Explicitly do **not** assert exact provisional numbers (only domains/invariants).

- [x] **Task 5 — Quality gates + plugin mirror** (AC: 7)
  - [x] `uv run ruff check . --fix && uv run ruff format .`
  - [x] `uv run mypy src/` (strict) — new module fully typed.
  - [x] `uv run pytest -m "not integration"` green (currently 702 passing + your new tests).
  - [x] Commit: the `build-plugin-sync` hook rebuilds `plugin/` because `src/` changed — re-add
        the regenerated `plugin/` files and complete the commit. Never `--no-verify`.

## Dev Notes

### What this story is — and is NOT

- **IS:** the new `src/logic/assessment/` package + one frozen-constants module + its offline
  unit test. Pure data, zero behavior.
- **IS NOT:** any scoring math, classifier, Karsten/hypergeometric function, combo shape, tier
  thresholds, or edge/tool code. If you find yourself writing a function that *computes* from a
  profile, stop — that is 5.3–5.9. If you find yourself importing anything beyond stdlib
  (`dataclasses`, `typing`) into `profiles.py`, stop — this module has **no dependencies**, not
  even on `src/data` schemas.

### Scope boundary: tier-label thresholds are 5.8's

Story 2.8's AC reads the descriptive tier label "from profile thresholds" — those thresholds will
live in this module eventually, but they are **not in this story's AC** and 5.8 owns adding them
(an additive field + version bump is the AD-3-sanctioned workflow, explicitly cheap by design).
Design `FormatProfile` so an additive field is trivial (it is, for a frozen dataclass). One
consistency obligation you *do* inherit now: the label vocabulary is already fixed —
`tests/fixtures/benchmark_decks.py:39` `TIER_LABELS = {"Unfocused", "Focused", "Tuned",
"High-Power", "Competitive"}` with a docstring saying this module owns the authoritative mapping
when it lands. Do not introduce any competing label vocabulary here.

### Recommended shape (guidance, not a straitjacket)

```python
DIMENSIONS: Final[tuple[str, ...]] = (...)  # the AD-7 closed 7-key set, one canonical home

@dataclass(frozen=True, slots=True)
class DimensionWeights:
    """Aggregate weights over the closed dimension set (AD-7). Sum to 1.0."""
    speed: float
    consistency: float
    resilience: float
    interaction: float
    mana_efficiency: float
    card_advantage: float
    combo_potential: float

@dataclass(frozen=True, slots=True)
class FormatProfile:
    format_profile_version: str
    rubric: Literal["brackets", "heuristic_only"]
    win_turn_band: tuple[int, int]
    weights: DimensionWeights
    # per-dimension mapping parameters: keep minimal + typed; 5.3-5.8 reshape as real curves land
    combos_enabled: bool
    multiplayer_variance_caveat: bool

COMMANDER_PROFILE: Final[FormatProfile] = FormatProfile(...)
STANDARD_PROFILE: Final[FormatProfile] = FormatProfile(...)
```

Why a `DimensionWeights` dataclass beats `Mapping[str, float]`: mypy enforces the AD-7 closed key
set at type-check time (a typo'd or missing dimension is a red squiggle, not a runtime KeyError in
5.8), and frozen+slots gives immutability for free. If you need dict-like iteration later,
`dataclasses.fields()` / `dataclasses.asdict()` provide it without weakening the type.

**Per-dimension mapping parameters:** the spine defers the actual curves; 5.3–5.8 will define what
parameters each dimension needs. For this story, keep the slot minimal and honest — e.g. a small
frozen dataclass of the constants you can already source from addendum §C (Karsten formula
coefficients are *shared* math constants, arguably 5.4's, so don't move them here preemptively) or
simply the win-turn band + weights if nothing else is yet defensible. **Do not invent elaborate
parameter families that 5.3–5.8 would then have to work around.** An empty-but-typed placeholder
that later stories extend additively (with a version bump) is better than speculative structure.

**A `PROFILES` lookup is optional:** Epic 7's edge selects by resolved format string. A
`PROFILES: Final[Mapping[str, FormatProfile]] = MappingProxyType({"commander": …, "standard": …})`
is passive data and fine to include; equally fine to leave for Epic 7. If included, key it on the
lowercase format strings the deck layer already uses (`"commander"` / `"standard"`,
`src/data/schemas/deck.py` `format` values).

### Standard `combos_enabled` — set `True`, document why

FR20 lists Standard's heuristic inputs as "curve / interaction / Karsten-60 / **combos**", so the
literal contract includes combo signal for Standard. The Spellbook snapshot is Commander-centric
(matches for a Standard deck will usually be few/none — which is fine and unpenalized), and
commander-*required* variants can never match a deck with no commander. Set
`combos_enabled=True` for both profiles and put this rationale in a field-site comment. If Epic 7
finds Standard combo provisioning pathological in practice, flipping the flag is a data edit +
version bump — exactly the AD-3 workflow.

### Version string discipline (FR4 / AD-7 / AD-8)

- One **monotonic string per format** (spine Consistency Conventions). Suggested initial values:
  `"commander-v1"` / `"standard-v1"` (any scheme works if it sorts/reads monotonically and the
  bump rule is documented).
- **Bump rule (document it in the docstring):** ANY value change in that profile → bump that
  profile's version. The version flows into `data_vintage` (AD-7) and is part of the byte-identical
  diff surface (AD-8) — a silent value change with an unchanged version is a lie to every cached
  diff.
- The profile must NOT carry a GC-list date/version or combo-snapshot version — that vintage
  belongs to the imported snapshots and would let the profile "lie about what data was used"
  (AD-3).

### Layer & purity rules (AD-2, project-context)

- `src/logic` is the framework-free domain core; this module is pure constants — **no imports
  from `src/data`, `src/mcp_server`, or third-party libs.** (`synergy.py` uses Pydantic; that is
  fine for its result models, but a constants bag needs nothing beyond stdlib — prefer the
  `search/query.py` `CardHit` framework-free frozen-dataclass precedent.)
- No `datetime`, no `Path`, no file reads (an "external data file" is explicitly banned by AD-3;
  import-time I/O would poison AD-2 purity).
- Python 3.12 syntax: `X | None`, builtin generics, `Literal` from `typing`; `Final` on the
  module-level constants. `format` as a *name* is fine in this project (documented builtin
  shadow), but this module shouldn't need it — fields are per-profile, the format is which
  constant you hold.
- Module docstring + Google-style class docstrings are mandatory (`mypy --strict` + ruff gates;
  docstring conventions per project-context#Code Quality).

### Previous-story intelligence (5.1, just completed)

- **The vocabulary handshake:** 5.1 committed `TIER_LABELS` in `tests/fixtures/benchmark_decks.py`
  expecting *this* module (well, 5.8's extension of it) to own the authoritative mapping. Nothing
  to import from tests into src (never import test code into `src/`!) — just don't contradict it.
- **Verify by shape, not names/numbers** (5.1 AC6, epic-4 retro): applied here as "no exact
  provisional-number assertions" (AC6). The 5.9 calibration pass will change the numbers; tests
  that pin them would make tuning a test-breaking chore.
- **Plugin mirror trap now APPLIES:** 5.1 was test-only and skipped it; this story touches `src/`.
  The `build-plugin-sync` pre-commit hook (`.pre-commit-config.yaml:24-33`) reruns
  `uv run python -m scripts.build_plugin` and fails the commit if `plugin/` drifted — re-add the
  regenerated `plugin/` files and re-commit. The hook IS installed in this checkout per 5.1's dev
  record ("plugin-sync all Passed"), but epic-4's action item warns it may be absent in fresh
  checkouts — if `pre-commit run --all-files` doesn't show it, run the build manually and diff.
- **5.1 review deferrals do not block this story** — they are parser DX gaps in the benchmark
  fixture (unrecognized-section, zero-quantity, FileNotFoundError labeling), owned by future
  fixture refresh work, not by 5.2.

### Testing standards

- pytest config in `pyproject.toml`: `asyncio_mode="auto"`, `--strict-markers`, `--tb=short`.
  This story's tests are synchronous; no markers needed (omit `integration` so they run in the
  fast subset).
- Test layout mirrors `src/`: the new test goes in `tests/unit/logic/` (see structure note).
  Naming `test_*.py` / `test_*` functions. `tests.*` is mypy-exempt but write full hints anyway
  (matches `test_benchmark_decks.py`).
- Actionable failures: a failed invariant should name the profile and field
  (`f"STANDARD_PROFILE.win_turn_band …"`), mirroring 5.1's `format_failure` philosophy.

## Project Structure Notes

**New files:**

```text
src/
  logic/
    assessment/
      __init__.py       # NEW: package docstring (pure core, AD-2) + re-exports
      profiles.py       # NEW: DIMENSIONS, DimensionWeights, FormatProfile,
                        #      COMMANDER_PROFILE, STANDARD_PROFILE
tests/
  unit/
    logic/
      test_assessment_profiles.py   # NEW: offline shape/invariant test
plugin/                             # REGENERATED by build-plugin-sync (commit the diff)
```

- **Module name:** the epic says "an in-repo Python `FormatProfile` module"; `profiles.py` inside
  the new `assessment` package is the recommended concrete name (the spine's Structural Seed shows
  `logic/assessment/` containing "FormatProfile" without fixing a filename — "exact filenames are
  seed; the boundary is the invariant", AD-9).
- **Test placement — flat, not a subdir:** `tests/unit/logic/` already holds flat test files
  (`test_synergy.py`, `test_mana_curve.py`, `test_deck_validator.py`) and has **no `__init__.py`**
  (unlike `tests/unit/` and `tests/unit/fixtures/`, which do — the tree's convention is mixed).
  Adding `tests/unit/logic/test_assessment_profiles.py` flat follows the local convention and
  sidesteps the package-marker question entirely. When Epic 5's test volume warrants a
  `tests/unit/logic/assessment/` subdir (likely by 5.3+), that story can introduce it.
- **`src/logic/assessment/__init__.py` re-exports** let later stories write
  `from src.logic.assessment import FormatProfile, COMMANDER_PROFILE` — mirror the
  `src/logic/__init__.py` `__all__` style.

## References

- [Source: _bmad-output/planning-artifacts/epics-deck-power-assessment.md#Story 2.2] — the AC this
  story implements (typed frozen profiles, passive data bag, in-repo constants module).
- [Source: epics-deck-power-assessment.md#Story 2.7, #Story 2.8; #Story 4.2 (combos_enabled)] —
  the downstream readers of every field.
- [Source: architecture/…/ARCHITECTURE-SPINE.md#AD-3] — the binding invariant (passive frozen
  data, no data versions, edit→bump→re-benchmark workflow).
- [Source: ARCHITECTURE-SPINE.md#AD-2, #AD-7, #AD-8, #Deferred, #Consistency Conventions] —
  purity, the closed 7-key vector, version-in-`data_vintage`, deferred curve/weight values,
  naming/format conventions.
- [Source: _bmad-output/planning-artifacts/prds/…/addendum.md#B (output schema note), #C
  (implementation constants), #D (calibration)] — provisional-value sources + tuning ownership.
- [Source: docs/deck-assess.md#1 (format relativity), #Option D (7 dimensions), #Option F (tier
  labels), #7.2 (hand-tuned weights, calibrate offline)] — research grounding for field semantics.
- [Source: src/mcp_server/tools/deck_import.py:79; src/search/query.py:54-84] — the
  `@dataclass(frozen=True, slots=True)` + attribute-docstring precedents to copy.
- [Source: src/logic/__init__.py] — package docstring + `__all__` re-export style to mirror.
- [Source: tests/fixtures/benchmark_decks.py:36-41] — the fixed `TIER_LABELS` vocabulary this
  module must not contradict (authoritative mapping lands in 5.8).
- [Source: .pre-commit-config.yaml:24-33; _bmad-output/implementation-artifacts/epic-4-retro-2026-07-12.md]
  — the `build-plugin-sync` mirror gate that applies because `src/` is touched.
- [Source: _bmad-output/implementation-artifacts/5-1-compose-the-calibration-benchmark-set.md] —
  previous-story intelligence (package deliberately not created there; verify-by-shape testing;
  702-test green baseline).
- [Source: _bmad-output/project-context.md#Language-Specific Rules, #Testing Rules, #Code Quality]
  — mypy --strict / ruff / docstring / pytest gates.

## Dev Agent Record

### Agent Model Used

claude-fable-5 (Claude Code)

### Debug Log References

- TDD RED: `uv run pytest tests/unit/logic/test_assessment_profiles.py` failed with
  `ModuleNotFoundError: No module named 'src.logic.assessment'` (expected — module absent).
- TDD GREEN: 25 new tests pass; full fast suite `uv run pytest -m "not integration"` →
  **728 passed, 5 deselected** (703 pre-existing + 25 new, zero regressions).
- Gates: `ruff check .` clean (one E501 in the new test fixed), `ruff format .` applied,
  `uv run mypy src/` → "Success: no issues found in 56 source files".
- Plugin mirror: `.git/hooks/pre-commit` absence risk (epic-4 action item) handled by running
  `uv run python -m scripts.build_plugin` explicitly — mirror regenerated
  (`plugin/server/src/logic/assessment/`); `plugin/*.json` diffs were line-ending-only.

### Implementation Plan

- Test-first (RED): authored the AC6 shape/invariant test against the wished-for public API
  (`from src.logic.assessment import FormatProfile, COMMANDER_PROFILE, STANDARD_PROFILE,
  DIMENSIONS, DimensionWeights`), watched it fail on import.
- `DIMENSIONS` uses the AC2/AD-7 listing order (`speed, consistency, resilience, interaction,
  mana_efficiency, card_advantage, combo_potential`), documented at the constant site.
- Closed key set enforced at type level via `DimensionWeights` frozen+slots dataclass with
  exactly seven `float` fields (the story's recommended shape over `Mapping[str, float]`).
- Per-dimension mapping parameters: took the Dev-Notes-sanctioned minimal path — the typed
  slots are `win_turn_band` (the `speed` curve anchor) + `weights`; no speculative parameter
  families invented. `FormatProfile`'s docstring states 5.3–5.8 extend additively with
  version bumps. Karsten coefficients deliberately left to 5.4/5.5 (shared math, addendum §C).
- `PROFILES` lookup mapping deliberately omitted (optional per Dev Notes; Epic 7's to add).
- `combos_enabled=True` for both profiles; Standard's field-site comment carries the FR20
  literal-reading rationale + the AD-3 flip workflow.

### Completion Notes List

- Created `src/logic/assessment/` — the pure deterministic scoring core package (AD-2) — with
  `profiles.py`: `DIMENSIONS`, `DimensionWeights`, `FormatProfile` (all
  `@dataclass(frozen=True, slots=True)`), `COMMANDER_PROFILE` (`commander-v1`, brackets,
  band 7–10, caveat True) and `STANDARD_PROFILE` (`standard-v1`, heuristic_only, band 5–8,
  caveat False). Zero behavior, zero imports beyond stdlib `dataclasses`/`typing`, no I/O.
- Provisional weights sum to 1.0 per profile: Commander leans consistency/resilience/
  card_advantage/combo_potential; Standard leans speed/interaction/mana_efficiency (FR20).
  Every value carries a rationale comment + the "5.9 owns tuning" pointer; module docstring
  documents the edit → version-bump → re-benchmark rule and the no-data-versions rule.
- 25 offline unit tests verify by shape only (existence, frozen-ness incl. nested weights,
  key-set closure vs `DIMENSIONS`, weight non-negativity + sum≈1.0, rubric domain + per-format
  values, band ordering, non-empty distinct versions, caveat flags, `combos_enabled` type).
  No exact provisional number is asserted anywhere.
- `src/logic/__init__.py` untouched (story kept additive). `TIER_LABELS` vocabulary not
  contradicted — no label vocabulary introduced (5.8 owns thresholds).

### File List

- `src/logic/assessment/__init__.py` (new)
- `src/logic/assessment/profiles.py` (new)
- `tests/unit/logic/test_assessment_profiles.py` (new)
- `plugin/server/src/logic/assessment/__init__.py` (new — regenerated mirror)
- `plugin/server/src/logic/assessment/profiles.py` (new — regenerated mirror)
- `plugin/.claude-plugin/plugin.json` (modified — line-ending normalization from mirror build)
- `plugin/.codex-plugin/plugin.json` (modified — line-ending normalization from mirror build)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (modified — status tracking)
- `_bmad-output/implementation-artifacts/5-2-format-profile-frozen-data-module.md` (modified)

## Change Log

- 2026-07-12: Story 5.2 implemented — `src/logic/assessment/` package created with the
  `FormatProfile` frozen-data module (`profiles.py`) + 25 offline shape/invariant tests.
  All 7 ACs satisfied; suite 728 passed; ruff/mypy-strict clean; plugin mirror regenerated.
