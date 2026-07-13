---
baseline_commit: 9d2e5f9 # 5.5 review-patch commit (review -> done)
---

# Story 5.6: `ComboRecord` + combo→bracket mapping

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

> **Sprint/feature numbering:** this is sprint key
> `5-6-combo-record-combo-bracket-mapping` (`epic-5`), which is **feature Epic 2, Story 2.6**
> in `_bmad-output/planning-artifacts/epics-deck-power-assessment.md`. Sprint Epic 5 = feature
> Epic 2 "Deterministic scoring core".
>
> **Ordering constraint (sprint-status.yaml):** 5.6 MUST precede 6.2 / 6.3 — the Spellbook
> import script and the snapshot repository consume the record shape this story defines.

## Story

As the scorer,
I want one canonical combo shape and a fixed bracket mapping,
so that snapshot, core, and output never diverge on combo data.

## Context & why this story exists

This story defines the **combo seam** of the whole feature (AD-11): the one frozen
`ComboRecord` shape that the snapshot repository (Story 6.3) returns, the pure core matches
and derives from, and Epic 7's `flags.combos` serializes verbatim — plus the **pure matcher**
that assigns the `included | almost_included` bucket, and the **closed combo→bracket map**
that turns Spellbook's `bracket_tag` into a Bracket-floor input. Three consumers hang off it:

- **FR13 matching** — the matcher itself lives HERE, in the pure core (AD-9: "a deterministic
  subset / missing-one computation belongs in the core, not behind I/O"). Epic 6 only delivers
  the data (import script 6.2, read-only repo 6.3); it performs **no matching**.
- **FR15 / FR18 feed** — matched combos feed the two-card-infinite Bracket trigger and the
  `combo_potential` dimension. **5.7** computes the actual Bracket floor and the 0–100
  dimension; this story provides the raw material (matched records with buckets, derived
  `type`, `earliest_turn_estimate`, and the `bracket_tag→int` map).
- **Epic 6 contract** — the import script (6.2) normalizes wire data into exactly this shape
  (an unknown `bracket_tag` fails the import loudly), and the repo (6.3) returns it as
  Pydantic. Both stories are written against what you ship here.

Like 5.3–5.5, you emit **raw signals** (records, tokens, ints), never 0–100 scores — mapping
curves are 5.7/5.8's, the aggregate is 5.8's, and serialization/degradation policy is Epic 7's.

## Acceptance Criteria

1. **One canonical frozen `ComboRecord`, placed where every consumer can legally import it.**
   Given AD-11 ("used verbatim by snapshot repo, scorer, and `flags.combos`"), AD-5 ("the
   repository returns Pydantic schemas, never ORM"), and the strict `data → logic` import
   direction (lower layers never import upward), when the shape is defined, then it is a
   **frozen Pydantic model** in **`src/data/schemas/combo.py`** (`model_config =
   ConfigDict(frozen=True)`) — NOT a dataclass in `src/logic` (the data-layer repo could
   never return it without an upward import) and NOT a second shape per layer. It carries
   exactly the AD-11 fields:
   - `spellbook_id: str` — Spellbook variant id (e.g. `"1234-5678"`);
   - `cards: tuple[str, ...]` — piece names, **normalized to sorted ascending bytewise on
     construction** (a `field_validator` sorts; immutable tuple, never list);
   - `commander_required: bool`;
   - `bucket: ComboBucket | None = None` — `None` in stored/repo rows; assigned **only** by
     the core matcher (AC3);
   - `bracket_tag: ComboBracketTag` (AC2);
   - `produces: tuple[str, ...]` — produced results, normalized sorted like `cards`;
   - `popularity: int | None` — EDHREC deck count, nullable.
   Derived `type` and `earliest_turn_estimate` are **NOT fields** — they are computed in the
   pure core (AC5) and never stored (AD-11: single owner for the heuristic; re-tuning never
   forces a re-import). The model is re-exported from `src/data/schemas/__init__.py` and from
   `src/logic/assessment/__init__.py` (additive). [epics 2.6; AD-5; AD-9; AD-11;
   project-context#Framework rules]

2. **Closed enums with a hard-error surface — never a silent wrong floor.** Given AD-11's
   closed-enum rule, when the types are defined (in `src/data/schemas/combo.py`, beside the
   model), then:
   - `ComboBucket = Literal["included", "almost_included"]`;
   - `ComboBracketTag = Literal["CASUAL", "ODDBALL", "POWERFUL", "PRECON_APPROPRIATE",
     "RUTHLESS", "SPICY"]` — exactly the six spine tokens, no others;
   - constructing a `ComboRecord` with an unknown `bracket_tag` or `bucket` raises a Pydantic
     `ValidationError` — this is the runtime hard-error surface at the repo/core boundary
     (import-time normalization is Story 6.2's; if wire vocabulary ever drifts, it must fail
     there or here, never silently map). [epics 2.6; AD-11]

3. **The pure matcher assigns `bucket` — multiplicity-aware, commander-aware, deterministic.**
   Given AD-2/AD-9, when `match_combos` is added to a new pure module
   `src/logic/assessment/combos.py`, then
   `match_combos(deck_cards, *, commanders, variants) -> tuple[ComboRecord, ...]`:
   - takes `Sequence[DeckCard]` (quantity-aware), `commanders: Sequence[str]` (resolved
     commander **names**, passed in as data per AD-13 — the core never resolves or queries
     for them), and `variants: Sequence[ComboRecord]` (bucket `None`, from the repo);
   - **name normalization (decide-once, documented at the code site):** deck cards are
     indexed under their **lowercased full name AND lowercased front face** (split on
     `" // "` — the pre-phase-2 DFC lesson: Spellbook names single faces, `Card.name` may be
     the joined `"A // B"`); variant piece names and commander names are compared lowercased;
   - **multiplicity-aware:** deck availability is a name→total-quantity count; a variant
     needing the same name twice needs quantity ≥ 2. Missing = total shortfall across the
     variant's pieces: `0` → `bucket="included"`, exactly `1` → `bucket="almost_included"`,
     `≥ 2` → the variant is **excluded from the output entirely**;
   - **commander requirement (decide-once, documented):** when `commander_required` is
     `True` — if `commanders` is empty the variant is **excluded entirely** (FR25: "assess
     without commander-required variants"; the `commander_unidentified` confidence token is
     the edge's job, not yours); if `commanders` is non-empty the requirement is satisfied
     iff ≥ 1 of the variant's `cards` is among the resolved commander names (lowercased) —
     unsatisfied → **excluded** (a command-zone requirement cannot be drawn into; this is a
     documented v1 proxy — the bool cannot say WHICH piece must command, 6.2 may refine wire
     mapping later, the shape is fixed);
   - matched records are produced with `model_copy(update={"bucket": ...})` — inputs are
     never mutated (frozen anyway) and the output records are the SAME shape (AD-11, no
     parallel "MatchedCombo" type);
   - output ordering is **deterministic: sorted ascending bytewise by `spellbook_id`**
     (AD-8 spirit), regardless of input order; identical inputs yield identical output.
   [epics 2.6; FR13; AD-2; AD-9; AD-13]

4. **The combo→bracket map keys on the closed enum exactly.** Given AD-11 and addendum §C,
   when defined in `src/logic/assessment/combos.py`, then
   `BRACKET_TAG_TO_BRACKET: Final[dict[ComboBracketTag, int]]` maps exactly
   `RUTHLESS→4, SPICY→3, POWERFUL→3, ODDBALL→2, PRECON_APPROPRIATE→2, CASUAL→1` — a
   Literal-keyed dict (the 5.4 review lesson: an invalid key is a mypy error at call sites),
   with a test asserting its key set equals the `ComboBracketTag` Literal's values (total
   over the enum — a future seventh tag cannot be silently unmapped). No other bracket
   arithmetic lives here: the WotC decision tree / Bracket floor is Story 5.7's. [epics 2.6;
   AD-11; addendum §C]

5. **Derived values computed in the core, never stored.** Given AD-11's derived-field rule,
   when the derived helpers are added to `combos.py`, then:
   - a **closed derived-type token vocabulary** is defined as `Final` constants plus a fixed
     tuple (the `classifiers.CATEGORIES` / `STRUCTURAL_GAP_TOKENS` precedent), recommended
     v1 (snake_case, count-free, provisional — 5.9 may tune): `two_card_infinite`,
     `multi_card_infinite`, `non_infinite`;
   - `combo_type(combo) -> str` returns one token; **infinite policy (decide-once,
     documented):** `"infinite"` substring in any lowercased `produces` entry;
     **two-card = `len(combo.cards) == 2`** (the stored, multiplicity-inclusive piece list);
   - `earliest_turn_estimate(...)` returns a deterministic **`int >= 1`** from the combo's
     piece mana values (joined from the deck's `Card.cmc` by the AC3 name normalization).
     The heuristic method is implementation-owned (spine "Deferred") — the hard requirements
     are: pure (no clock/random/IO), deterministic, integer, documented at the code site,
     and marked provisional (5.9 tunes). Recommended v1 (naive one-land-per-turn model):
     smallest turn `T` with `T >= ceil(max piece mv)` and `T*(T+1)/2 >= ceil(total mv)` —
     see Dev Notes for worked examples. Pieces not resolvable in the deck (the missing
     `almost_included` piece) are skipped from the sum, documented as an optimistic
     undercount; a combo with zero resolvable pieces returns `1` (floor), never raises.
   [epics 2.6; AD-11; spine#Deferred]

6. **FR15 feed is complete — and nothing more.** Given Story 5.7's needs, when the module is
   done, then 5.7 can compute the two-card-infinite Bracket trigger
   (`bucket == "included"` and `combo_type == two_card_infinite`) and the `combo_potential`
   inputs (matched records, buckets, `BRACKET_TAG_TO_BRACKET`, popularity, earliest turns)
   **entirely from this module's public API** — and this story ships **no** 0–100 mapping,
   no Bracket floor, no `FormatProfile` read/edit, no confidence tokens, no serialization.
   [epics 2.6; FR15; AD-3]

7. **One vocabulary, no forked shapes, no scope creep.** Given AD-10/AD-11, when reviewed,
   then: no edits to `classifiers.py`, `mana_base.py`, `consistency.py`, `profiles.py`,
   `src/logic/synergy.py`, or any `src/mcp_server` / `src/data/repositories` /
   `src/data/models` / `scripts/` file; no DB table, no importer, no downloader (6.2/6.3
   own those); `classifiers.WINCON_COMBO_PIECE` remains an independent **text-level
   pre-signal** — this module supersedes it *for combo purposes* but does not touch it
   (note the relationship in the module docstring); every numeric/token constant is `Final`
   with a source comment, provisional values marked 5.9-owned. [epics 2.6; AD-10; AD-11]

8. **Offline unit tests prove the seam.** Given the project's testing rules, when
   `tests/unit/logic/test_assessment_combos.py` runs (no `integration` marker, no DB), then
   with a `make_combo_record` factory added to `tests/fixtures/assessment.py` (G1: one home,
   never a second copy) it verifies at minimum:
   - **shape:** frozen (assignment raises), `cards`/`produces` normalized sorted on
     construction, unknown `bracket_tag`/`bucket` → `ValidationError`, `bucket` defaults
     `None`;
   - **matcher buckets:** all pieces present → `included`; exactly one missing →
     `almost_included`; two+ missing → excluded; quantity-aware (needs 2×, deck has 1 →
     `almost_included`; has 2 → `included`);
   - **name normalization:** case-insensitive match; a deck `"A // B"` DFC matches a
     variant naming just `"A"`;
   - **commander policy:** `commander_required=True` + empty `commanders` → excluded;
     + commanders containing a piece → matched; + commanders NOT containing any piece →
     excluded; `commander_required=False` ignores `commanders` entirely;
   - **determinism/ordering:** shuffled variant input → output sorted by `spellbook_id`;
     two calls on equal input → equal output; inputs not mutated;
   - **map:** exact six pairs pinned; key set == the Literal's args
     (`typing.get_args(ComboBracketTag)`);
   - **derived:** `combo_type` on 2-piece-infinite / 3-piece-infinite / non-infinite
     fixtures; `earliest_turn_estimate` pinned on small worked examples **referencing the
     module's own documented model** (verify-by-shape: the heuristic is provisional — pin
     the examples the docstring derives, plus monotonicity: adding a more expensive piece
     never lowers the estimate) and the zero-resolvable-pieces floor;
   - **edges:** empty `variants` → `()`; empty deck → 1-piece variant `almost_included`,
     2-piece variant excluded, no crash; a `sideboard=True` `DeckCard` **counts** toward
     availability (the documented 5.3/5.4/5.5 not-filtered policy — the edge passes
     mainboard-only rows; pin it so a filtering regression is caught);
   - assertions carry failure messages naming the variant/signal **or** the task claim is
     dropped (the 5.5 review lesson: don't claim messages you didn't write).
   Runs green under `uv run pytest -m "not integration"` (baseline at story creation:
   **875 passed**). [project-context#Testing Rules; 5-5 review findings]

9. **Quality gates pass — including the `src/`-touch plugin mirror.** Given this story adds
   files under `src/`, when committed, then `mypy --strict` passes (full hints, Google
   docstrings on module + every public name), `ruff check` + `ruff format` are clean, and
   the regenerated `plugin/` mirror is staged in the same commit (the pre-commit hook is
   installed in this checkout and rebuilds it — verify `plugin/server/src/logic/assessment/`
   and `plugin/server/src/data/schemas/` diffs are staged; never `--no-verify`).
   [project-context#Code Quality; epic-4 retro]

## Tasks / Subtasks

- [x] **Task 0 — Confirm baseline** (AC: —)
  - [x] Verify you start from `9d2e5f9` (the 5.5 review→done commit) with a clean working
        tree apart from this story file.
- [x] **Task 1 — `ComboRecord` schema** (AC: 1, 2)
  - [x] `src/data/schemas/combo.py`: `ComboBucket` + `ComboBracketTag` Literals,
        frozen `ComboRecord` with sorted-normalizing validators for `cards`/`produces`,
        Google docstrings stating the AD-11 single-shape contract and who sets `bucket`.
  - [x] Re-export from `src/data/schemas/__init__.py` (additive `__all__`).
- [x] **Task 2 — Pure matcher** (AC: 3)
  - [x] `src/logic/assessment/combos.py` module docstring: FR13/FR15 seam, derived-not-
        stored rule, the `WINCON_COMBO_PIECE` relationship, decide-once policies.
  - [x] Name-availability index (lowercased full + front-face names → quantity) and
        `match_combos` per AC3 (shortfall buckets, commander policy, `model_copy`,
        `spellbook_id`-sorted output).
- [x] **Task 3 — Bracket map** (AC: 4)
  - [x] `BRACKET_TAG_TO_BRACKET: Final[dict[ComboBracketTag, int]]` with the six pinned
        pairs + source comment (addendum §C / spine AD-11).
- [x] **Task 4 — Derived helpers** (AC: 5)
  - [x] Type tokens + `COMBO_TYPE_TOKENS` tuple (defined already bytewise-sorted, the 5.5
        tip); `combo_type`; `earliest_turn_estimate` with the documented v1 model + worked
        examples in the docstring, marked provisional/5.9-owned.
- [x] **Task 5 — Package exports** (AC: 1, 6)
  - [x] Extend `src/logic/assessment/__init__.py` `__all__` additively (matcher, map,
        tokens, helpers, and re-export `ComboRecord`/`ComboBucket`/`ComboBracketTag` for
        core consumers).
- [x] **Task 6 — Offline unit tests** (AC: 8)
  - [x] `make_combo_record` factory in `tests/fixtures/assessment.py`;
        `tests/unit/logic/test_assessment_combos.py` covering the full AC8 matrix.
- [x] **Task 7 — Quality gates + plugin mirror** (AC: 9)
  - [x] `uv run ruff check . --fix && uv run ruff format .`
  - [x] `uv run mypy src/` (strict) clean.
  - [x] `uv run pytest -m "not integration"` green (baseline: **875 passed**).
  - [x] Commit with the regenerated `plugin/` mirror staged (hook rebuilds it — verify both
        the `assessment/` and `data/schemas/` mirror paths are staged). Never `--no-verify`.

## Dev Notes

### What this story is — and is NOT

- **IS:** one frozen Pydantic `ComboRecord` (+ its two Literal enums) at the schema layer;
  one new pure module `src/logic/assessment/combos.py` (matcher, bracket map, derived
  type + earliest-turn helpers, closed token tuple); exports; offline tests; factory.
- **IS NOT:** the Bracket floor or WotC decision tree (5.7), the `combo_potential` /
  `speed` 0–100 mappings (5.7), aggregate weights or confidence tokens (5.8), the
  Spellbook downloader/import script/DB tables (6.2), the snapshot repository (6.3),
  commander *resolution* (Epic 7 edge, AD-13 — commanders arrive here as a name list),
  `FormatProfile` edits (`combos_enabled` already exists; Epic 7 branches on it), any
  serialization (Epic 7, AD-8), or `classifiers.py` pattern edits. If a function needs a
  `FormatProfile`, a DB, the clock, or the network — it belongs to a later story.

### Baseline note (story-creation snapshot, 2026-07-13)

The 5.5 review patches are committed as `9d2e5f9` (the `baseline_commit`) — the
`consistency.py` behavior documented below is the **post-review** state. Fast-suite
baseline **875 passed** was measured with those patches applied. The pre-commit hook
(ruff + mypy + plugin rebuild) IS installed in this checkout.

### The load-bearing placement decision (read this before writing any code)

The epics text says the record is "defined in the core", but three binding constraints
triangulate its real home:

1. AD-11: ONE shape "used verbatim by snapshot repo, scorer, and `flags.combos`".
2. AD-5 / Story 6.3: the repository "returns Pydantic schemas (never ORM)".
3. project-context layering: `data → logic → mcp_server` — **`src/data` may never import
   from `src/logic`**, so a shape defined in `src/logic/assessment` can never be returned
   by a `src/data/repositories` repo.

The only placement satisfying all three is a **frozen Pydantic model in
`src/data/schemas/combo.py`** (the established cross-layer contract home — `Card`,
`DeckCard` live there and the pure core already consumes them). The core still **owns the
semantics** — bucket assignment, bracket map, derived fields all live in
`src/logic/assessment/combos.py` — which is what "the record shape the core defines" means
in practice. Do NOT define a frozen dataclass in the core and a "mirror" Pydantic model in
data — that is exactly the divergence AD-11 exists to prevent. Note the deviation-with-
rationale in the module docstrings (both files).

Pydantic-frozen specifics: `model_config = ConfigDict(frozen=True)`; use `tuple[str, ...]`
(not `list`) for `cards`/`produces` so contents are immutable too; `model_copy(update=...)`
is the sanctioned way to produce the bucket-assigned records. The package convention of
frozen slots **dataclasses** (5.2–5.5) applies to shapes the core creates for itself; this
shape crosses layers, so Pydantic wins here.

### Decide-once policies (document each at its code site)

- **Name normalization:** compare lowercased. Index each deck card under its lowercased
  full `Card.name` AND, when the name contains `" // "`, the lowercased front face
  (`name.split(" // ")[0]`). Spellbook names individual faces; `Card.name` for DFCs is the
  joined form (the pre-phase-2 `detect_synergies` '//' fix is the precedent). Variant piece
  names are used as imported (6.2 normalizes wire → canonical Scryfall names).
- **Multiplicity:** availability = `sum(dc.quantity)` per normalized name;
  need = `Counter(lowercased combo.cards)`; shortfall = `sum(max(0, need - have))`.
  Commander singleton makes >1-need rare, but the shape is format-generic — implement it
  once, correctly.
- **Commander requirement is a zone requirement, not a draw requirement:** unsatisfiable →
  excluded, never `almost_included` (you cannot draw into the command zone). Empty
  `commanders` + `commander_required=True` → excluded (FR25); the edge (Story 7.2) is who
  adds `commander_unidentified` to confidence — emit nothing about confidence here (AD-6
  tokens are 5.8's vocabulary, edge-assembled).
- **Sideboard rows are NOT filtered** — the standing 5.3/5.4/5.5 policy: deck-composition
  belongs to the caller/edge; Epic 7 passes mainboard-only rows (+ commanders per AD-13).
  Same one-line caveat in the public docstrings; pin with a test.
- **Ordering:** output tuple sorted ascending bytewise by `spellbook_id`. Don't sort by
  bucket first — one key, stated once; Epic 7 re-sorts its serialized lists per AD-8 anyway.
- **Infinite detection:** `any("infinite" in p.lower() for p in produces)`. Conservative,
  provisional; Spellbook `produces` entries are feature names like "Infinite mana".
- **Earliest-turn v1 model (recommended, provisional):** assume one land drop per turn and
  nothing else: mana available on turn `T` is `T`, cumulative `T*(T+1)/2`. The estimate is
  the smallest `T` with `T >= ceil(max piece mv)` (you must be able to cast the biggest
  piece) and `T*(T+1)/2 >= ceil(total mv)` (you must have paid for all pieces). Worked
  examples to put in the docstring and pin in tests: pieces (2, 2) → total 4, max 2 →
  T=3 (T=2: 3 < 4); pieces (1, 1) → T=2 (T=1: 1 < 2); pieces (6,) → T=6; pieces () → 1
  (floor). Ramp/tutor acceleration deliberately ignored here — 5.7 combines this with ramp
  density for `speed`; don't double-count acceleration in two places.
- **`earliest_turn_estimate` inputs:** recommended signature
  `earliest_turn_estimate(combo: ComboRecord, deck_cards: Sequence[DeckCard]) -> int` —
  join piece names to `Card.cmc` via the same normalization as the matcher (front-face cmc
  semantics, cite 5.4's `CurveSignals` wording). Unresolvable pieces are skipped
  (documented optimistic undercount for `almost_included`); all-unresolvable → 1.
- **Float→int:** `cmc` is float; `ceil` before comparison; result is `int`. No division
  determinism concerns (pure integer comparisons after ceil).

### Recommended shape (guidance, not a straitjacket)

```python
# src/data/schemas/combo.py — sketch
ComboBucket = Literal["included", "almost_included"]
ComboBracketTag = Literal[
    "CASUAL", "ODDBALL", "POWERFUL", "PRECON_APPROPRIATE", "RUTHLESS", "SPICY"
]

class ComboRecord(BaseModel):
    model_config = ConfigDict(frozen=True)
    spellbook_id: str
    cards: tuple[str, ...]            # sorted ascending bytewise (validator normalizes)
    commander_required: bool
    bucket: ComboBucket | None = None # None in stored rows; the core matcher assigns it
    bracket_tag: ComboBracketTag
    produces: tuple[str, ...]         # sorted ascending bytewise (validator normalizes)
    popularity: int | None = None

# src/logic/assessment/combos.py — sketch
BRACKET_TAG_TO_BRACKET: Final[dict[ComboBracketTag, int]] = {
    "CASUAL": 1, "ODDBALL": 2, "PRECON_APPROPRIATE": 2,
    "POWERFUL": 3, "SPICY": 3, "RUTHLESS": 4,
}
MULTI_CARD_INFINITE: Final = "multi_card_infinite"
NON_INFINITE: Final = "non_infinite"
TWO_CARD_INFINITE: Final = "two_card_infinite"
COMBO_TYPE_TOKENS: Final[tuple[str, ...]] = (...)  # define already bytewise-sorted

def match_combos(
    deck_cards: Sequence[DeckCard],
    *,
    commanders: Sequence[str],
    variants: Sequence[ComboRecord],
) -> tuple[ComboRecord, ...]: ...
def combo_type(combo: ComboRecord) -> str: ...
def earliest_turn_estimate(
    combo: ComboRecord, deck_cards: Sequence[DeckCard]
) -> int: ...
```

Why this shape: keyword-only matcher params make call sites self-documenting and stop a
commanders/variants swap from type-checking; returning the same `ComboRecord` type (bucket
set) is the literal AD-11 rule; `Final` Literal-keyed map = mypy-total (5.4 lesson);
tokens-as-constants mirrors `CATEGORIES`/`STRUCTURAL_GAP_TOKENS` so Epic 7 can serialize
the vocabulary it already knows how to handle.

### Spellbook wire-format caveat (do NOT chase it here)

The six `bracket_tag` tokens and the tag→bracket map are **normative from the spine/
addendum** (verified against secondary sources at story creation; exact wire casing, e.g.
`PRECON` vs `PRECON_APPROPRIATE`, varies by source). Story 6.2 verifies the live bulk
export and normalizes wire→`ComboBracketTag`, failing loudly on anything unknown. Your
Pydantic Literal is the second line of defense. Do not add speculative aliases or a
"fuzzy tag" fallback — an unknown tag must be an error, never a silent wrong floor.

### Layer & purity rules (AD-2, project-context)

- `src/data/schemas/combo.py`: pydantic + `typing` only; no imports from `src/logic`.
- `src/logic/assessment/combos.py` allowed imports: stdlib (`math`, `collections`,
  `typing`, `collections.abc`) + `src.data.schemas.card` / `src.data.schemas.deck` /
  `src.data.schemas.combo`. Forbidden: `src/search`, `src/mcp_server`,
  `src/data/repositories`, `src/data/models`, `src/logic/mana_curve`, `src/logic/synergy`,
  and — for this story — even the sibling assessment modules (`classifiers`, `mana_base`,
  `consistency`): the matcher needs none of them, and importing `classifiers` here would
  invite exactly the text-heuristic/Spellbook conflation the docstring must warn against.
- Pure functions, no logging, no clock, no `random`. Python 3.12 syntax (`X | None`,
  builtin generics, `Final`, `Literal`); Google docstrings on module + every public name.

### Previous-story intelligence (5.5, just completed)

- **Review findings to apply proactively here** (each was a review round-trip):
  1. If a task claims "failure messages name the X", the asserts must actually carry
     messages — bare `assert expr` with a checked-off claim got flagged.
  2. One owner per fact: don't compute deck size / availability two ways in one module
     (the `redundancy_signals` recompute finding). Build the availability index once,
     use it for matching and for `earliest_turn_estimate`'s name→cmc join.
  3. Documented-but-only-in-one-place gaps get flagged: if a baseline/heuristic constant
     has a surprising consequence (like the unreachable `ramp_below_baseline` for
     sixty_card), say so in the PUBLIC docstring, not just an inline comment.
  4. Keep AC prose and pinned test values in sync — if you correct a number mid-
     implementation, amend the story file too (the 0.8085→0.8094 finding).
- **Standing lessons still in force:** Literal-keyed dicts from the start (5.4);
  sideboard-row test per public function (5.4/5.5); both/all enum branches exercised
  (5.4); shared factories in `tests/fixtures/assessment.py`, never a second copy (G1);
  verify-by-shape for provisional values, exact pins only for derived math (5.1→5.5);
  `face.get(key) or ""` if you ever touch `card_faces` (you shouldn't — `name`/`cmc` are
  top-level).
- **Deferred-work items that brush this story** (context, not scope): the
  `probability_at_least` [0,1] property test mentions "future 5.6/5.7 combo-probability
  call sites" — v1 combo math here needs NO hypergeometrics (the earliest-turn model is
  mana-only); if you find yourself importing `consistency.probability_at_least`, you've
  drifted into 5.7's consistency/speed mapping. `classify_card`'s `WINCON_COMBO_PIECE` is
  a text pre-signal only (its own docstring already defers to this story for real combo
  matching).
- **Fast-suite baseline: 875 passed** (measured at story creation, 5.5 review patches
  applied).

### Testing standards

- pytest config in `pyproject.toml`: `asyncio_mode="auto"`, `--strict-markers`,
  `--tb=short`; these tests are synchronous, no markers, in the `-m "not integration"`
  fast subset.
- Flat placement `tests/unit/logic/test_assessment_combos.py` beside the four existing
  assessment test modules (the `tests/unit/logic/assessment/` subdir move remains
  deferred; if you do it, move all five in one commit).
- Use `tests/fixtures/assessment.py::make_card/make_deck_card` and add
  `make_combo_record(**overrides)` there (defaults: 2 sorted cards, `CASUAL`,
  `commander_required=False`, `bucket=None`, `produces=("Infinite mana",)`,
  `popularity=None`). `tests.*` is mypy-exempt but write full hints anyway.
- `typing.get_args(ComboBracketTag)` / `get_args(ComboBucket)` give you the enum values
  for totality assertions without hardcoding a second copy of the vocabulary in tests.
- Schema tests for `ComboRecord` live in the combos test module (it's this story's seam),
  not in `tests/unit/data/test_schemas.py` — keep the story's surface in one file.

## Project Structure Notes

**New/changed files:**

```text
src/
  data/
    schemas/
      combo.py            # NEW: frozen ComboRecord + ComboBucket/ComboBracketTag Literals
      __init__.py         # MODIFIED: additive re-export
  logic/
    assessment/
      combos.py           # NEW: pure matcher, BRACKET_TAG_TO_BRACKET, combo_type,
                          #      earliest_turn_estimate, COMBO_TYPE_TOKENS
      __init__.py         # MODIFIED: additive re-exports (incl. ComboRecord + enums)
tests/
  fixtures/
    assessment.py         # MODIFIED: + make_combo_record factory
  unit/
    logic/
      test_assessment_combos.py   # NEW: AC8 matrix
plugin/                   # REGENERATED mirror (hook rebuilds; verify staged — note the
                          # data/schemas mirror path is new to this story's diff)
```

- No changes to `src/logic/__init__.py`, any repository/model/importer, `scripts/`, or
  `src/mcp_server`. No DB objects of any kind — the snapshot table is 6.2's.
- Downstream consumers to keep in mind while naming things: 5.7 (floor + dimensions),
  6.2 (import normalizes INTO `ComboRecord`), 6.3 (repo returns `ComboRecord`), 7.2/7.3
  (edge passes variants in, serializes `flags.combos`).

## References

- [Source: _bmad-output/planning-artifacts/epics-deck-power-assessment.md#Story 2.6] — the
  binding ACs (frozen record, matcher buckets, closed bracket_tag enum + map, FR15 feed).
- [Source: epics-deck-power-assessment.md#Additional Requirements AD-11] — field list,
  derived-not-stored rule, tag→bracket pairs, import-time normalization split (6.2).
- [Source: _bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-11/ARCHITECTURE-SPINE.md#AD-5, #AD-9, #AD-11, #AD-13] —
  repo-returns-Pydantic, matching-is-pure-core, single-shape rule, commanders-as-data;
  #Deferred — the earliest-turn heuristic is implementation-owned.
- [Source: _bmad-output/planning-artifacts/sprint-change-proposal-2026-07-12.md#P1–P4] —
  why combos are a local snapshot, `included`/`almost_included` definitions, FR25
  commander policy, AD-12 withdrawal (no cache key anywhere in this story).
- [Source: docs/deck-assess.md:140-150] — Spellbook variant fields (`produces`,
  `popularity`, `bracket_tag`, id form `1234-5678`); [:275-278] — the output sketch this
  record ultimately serializes into; [:329] — the published tag→power pairs.
- [Source: src/data/schemas/deck.py; src/data/schemas/card.py] — schema-layer conventions
  (`ConfigDict`, validators, docstring style); `DeckCard.quantity/sideboard/card` you
  consume.
- [Source: src/logic/assessment/classifiers.py:46-49] — `WINCON_COMBO_PIECE`'s own
  docstring deferring real combo matching to this story.
- [Source: src/logic/assessment/consistency.py] — the frozen-shapes / closed-token-tuple /
  decide-once-policy house style this module mirrors (and its deliberate non-import here).
- [Source: src/logic/assessment/profiles.py:97] — `combos_enabled` already exists; no
  profile edit in this story.
- [Source: _bmad-output/implementation-artifacts/5-5-consistency-interaction-structural-coverage-signals.md#Review Findings, #Dev Notes] —
  the four proactive lessons + standing policies (sideboard, verify-by-shape, G1 factory).
- [Source: _bmad-output/implementation-artifacts/deferred-work.md#Deferred from: code review of story-5.5] —
  the adjacent deferred items and why none of them are picked up here.
- [Source: _bmad-output/project-context.md#Framework rules, #Testing Rules, #Code Quality] —
  layering, mypy --strict / ruff / Google docstrings / pytest gates.

## Dev Agent Record

### Agent Model Used

claude-fable-5 (Claude Fable 5)

### Debug Log References

- RED: `tests/unit/logic/test_assessment_combos.py` written first — collection error
  confirmed (modules absent) before any implementation.
- GREEN: all 47 new tests passed on first run after implementation; no fix cycles.
- Gates: `ruff check` clean (format joined a few long call lines), `mypy src/` strict
  clean (61 files), `pytest -m "not integration"` → **922 passed, 5 deselected**
  (875 baseline + 47 new, zero regressions).

### Completion Notes List

- **Task 1:** `src/data/schemas/combo.py` — frozen `ComboRecord`
  (`ConfigDict(frozen=True)`, `tuple[str, ...]` collections) + closed `ComboBucket` /
  `ComboBracketTag` Literals. A shared `field_validator` normalizes `cards`/`produces`
  to ascending bytewise order on construction (duplicates preserved). Module docstring
  documents the AD-11 placement deviation (schema layer, not core — the AD-5/layering
  triangle) and that only the core matcher sets `bucket`. Additively re-exported from
  `src/data/schemas/__init__.py`.
- **Task 2:** `src/logic/assessment/combos.py` — `_name_keys` is the single owner of
  the name-normalization policy (lowercased full name + DFC front face split on
  `" // "`); `_availability` (name→quantity) and `_cmc_by_name` (name→cmc, for the
  earliest-turn join) both delegate to it (the 5.5 one-owner lesson). `match_combos`
  implements the AC3 shortfall buckets (0→included, 1→almost_included, ≥2→excluded),
  the availability-neutral commander zone gate (empty commanders or no piece among
  commanders → excluded; documented v1 proxy), `model_copy(update={"bucket": ...})`
  outputs, and `spellbook_id`-sorted deterministic ordering. Sideboard rows are NOT
  filtered (standing 5.3–5.5 policy, documented + pinned).
- **Task 3:** `BRACKET_TAG_TO_BRACKET: Final[dict[ComboBracketTag, int]]` — six pinned
  pairs (RUTHLESS→4, SPICY/POWERFUL→3, ODDBALL/PRECON_APPROPRIATE→2, CASUAL→1) with
  addendum §C source comment; totality over the Literal pinned by test.
- **Task 4:** `TWO_CARD_INFINITE`/`MULTI_CARD_INFINITE`/`NON_INFINITE` +
  `COMBO_TYPE_TOKENS` (defined already bytewise-sorted); `combo_type` (lowercased
  `"infinite"` substring over `produces`; two-card = `len(cards) == 2`);
  `earliest_turn_estimate` implements the documented v1 one-land-per-turn model
  (`T >= ceil(max mv)` and `T*(T+1)/2 >= ceil(total mv)`), skips unresolvable pieces
  (documented optimistic undercount), floor 1, pure integer arithmetic after ceil —
  all marked provisional/5.9-owned.
- **Task 5:** `src/logic/assessment/__init__.py` — additive `__all__` (kept
  bytewise-sorted) exporting the matcher, map, tokens, helpers, and re-exporting
  `ComboRecord`/`ComboBucket`/`ComboBracketTag` for core consumers.
- **Task 6:** `make_combo_record` factory added to `tests/fixtures/assessment.py` (G1:
  one home) with the story-specified defaults; `test_assessment_combos.py` covers the
  full AC8 matrix in 47 tests (shape/frozen/validators/closed enums, all bucket +
  quantity branches, case-insensitive + DFC normalization, all four commander-policy
  branches + case-folded commander compare + the availability-neutral-gate pin,
  determinism/ordering/no-mutation, map exactness + `get_args` totality, `combo_type`
  on 2/3-piece infinite + non-infinite + case-insensitivity, earliest-turn docstring
  worked examples + fractional-cmc ceil + monotonicity + unresolvable-skip + floor +
  DFC cmc join, empty-variants/empty-deck edges, sideboard-counts pin, and both
  packages' re-export surface). Every assert carries a failure message naming the
  variant/signal.
- **AC6 verified:** 5.7 can compute the two-card-infinite trigger and the
  `combo_potential` inputs entirely from the public API; no 0–100 mapping, no Bracket
  floor, no profile read, no confidence tokens, no serialization shipped.
- **AC7 verified:** no edits to `classifiers.py`, `mana_base.py`, `consistency.py`,
  `profiles.py`, `synergy.py`, `src/mcp_server`, repositories, models, or `scripts/`;
  no DB objects; `WINCON_COMBO_PIECE` relationship noted in the module docstring
  without importing any sibling assessment module.

### File List

- `src/data/schemas/combo.py` (new)
- `src/data/schemas/__init__.py` (modified — additive re-export)
- `src/logic/assessment/combos.py` (new)
- `src/logic/assessment/__init__.py` (modified — additive re-exports)
- `tests/fixtures/assessment.py` (modified — + `make_combo_record`)
- `tests/unit/logic/test_assessment_combos.py` (new)
- `plugin/server/src/data/schemas/combo.py` (regenerated mirror)
- `plugin/server/src/data/schemas/__init__.py` (regenerated mirror)
- `plugin/server/src/logic/assessment/combos.py` (regenerated mirror)
- `plugin/server/src/logic/assessment/__init__.py` (regenerated mirror)

## Change Log

- 2026-07-13: Story 5.6 created (ready-for-dev) — ultimate context engine analysis
  completed: comprehensive developer guide covering the AD-11 placement triangle
  (Pydantic-at-schema-layer decision), matcher decide-once policies, closed enums,
  bracket map totality, derived-value ownership, and the full offline test matrix.
- 2026-07-13: Story 5.6 implemented (Tasks 0–7) — frozen `ComboRecord` + closed enums
  at the schema layer, pure matcher / bracket map / derived helpers in
  `src/logic/assessment/combos.py`, additive exports, `make_combo_record` factory,
  47 offline tests. Gates: ruff + mypy --strict clean, fast suite 922 passed
  (875 baseline + 47 new, 0 regressions). Status → review.
