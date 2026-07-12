# Story 5.3: Shared oracle-text classifiers

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

> **Sprint/feature numbering:** this is sprint key `5-3-shared-oracle-text-classifiers`
> (`epic-5`), which is **feature Epic 2, Story 2.3** in
> `_bmad-output/planning-artifacts/epics-deck-power-assessment.md`. Sprint Epic 5 = feature Epic 2
> "Deterministic scoring core".

## Story

As the scorer,
I want one oracle-text taxonomy,
so that ramp/draw/removal/tutor counts, win-conditions, and hard triggers share vocabulary rather
than forking it.

## Context & why this story exists

This story adds the **first behavior** to the pure core: the shared oracle-text classifiers
(AD-10) in `src/logic/assessment/`. Story 5.2 created the package and its frozen `FormatProfile`
constants; 5.3 turns cards into **raw categorical signals** that everything downstream consumes:

- **5.4 (Karsten mana math)** subtracts "cheap card draw + ramp" in the land formulas — it will
  filter *this story's* ramp/draw classifications by `cmc`. The cheap-cmc cutoff constant is
  **5.4's**, not yours; you provide per-card classification joined to the `Card` (so `cmc` is
  reachable), not a pre-filtered "cheap" count.
- **5.5 (consistency/interaction/structural signals)** computes the instant-speed ratio and
  interaction-CMC distribution (FR7) **over this story's interaction set**, and the rule-of-8 /
  8×8 structural gaps (FR9) over these category counts. The `structural_gaps[]` closed enum is
  **5.5's**, not yours.
- **5.7 (Bracket floor)** consumes the FR12 booleans (mass land denial, extra-turn chains) as two
  of the three WotC hard triggers, and the win-condition tags for the vector.
- **Epic 7's `flags` block** surfaces `mass_land_denial` / `extra_turn_chains` booleans and the
  cards that drove results (FR23, NFR2 explainability) — which is why classifications must carry
  **card names**, not bare counts.

AD-10's whole point is **one vocabulary, defined once**: the deckbuilding skills and tools must
call these functions, never re-implement pattern lists in the tool layer. The precedent for *how*
to match is `src/logic/synergy.py` — lowercased substring/regex matching over `Card.oracle_text`
+ `Card.keywords`, quantity-aware counting over `DeckCard`s.

## Acceptance Criteria

1. **A pure classifier module exists in `src/logic/assessment/` following the `synergy.py`
   conventions.** Given AD-10 and AD-2, when the module (recommended: `classifiers.py`) is added,
   then it contains only pure functions over already-loaded Pydantic schemas (`Card` /
   `DeckCard`) — matching is lowercased over `Card.oracle_text` + `Card.keywords` (+ `type_line`
   where the category demands it); **no network, DB, clock, file I/O, or imports from
   `src/search` / `src/mcp_server`** (stdlib `re`/`dataclasses`/`typing` + `src.data.schemas`
   only, the `synergy.py` import precedent). [epics 2.3; AD-2; AD-10]

2. **FR6 categories: ramp, card-draw/advantage, removal/interaction, tutors.** Given a deck's
   cards, when classified, then per-card classification identifies membership in each of the four
   FR6 categories via oracle-text + `type_line` patterns, and deck-level results provide, per
   category, a **quantity-aware count** plus the **sorted list of card names** (explainability,
   NFR2/FR23). Guardrails that MUST hold (each pinned by a test, AC6):
   - a **Land** `type_line` never counts as ramp (lands produce mana; ramp *accelerates* it);
   - land-fetch ("search your library for a … land … put … onto the battlefield", à la Rampant
     Growth / Cultivate) counts as **ramp, not tutor**; generic library search to hand (Demonic /
     Mystical / Vampiric Tutor) counts as **tutor**;
   - one card may hold multiple categories (e.g. a draw-plus-removal modal spell) — categories
     are independent tags, not exclusive buckets. [epics 2.3; FR6]

3. **FR10 win-condition tagging.** Given the deck's cards, when tagged, then win-condition
   detection identifies (as distinct, per-card tags with names surfaced as in AC2):
   - **explicit wincons** — "you win the game" / "each opponent loses the game"-style text;
   - **combo-piece heuristics** — text-level signals only at this stage (e.g. untap/copy/
     "any number of times" loop enablers); real combo matching is 5.6's against the Spellbook
     snapshot — do NOT reach for combo data here;
   - **evasive/haymaker finishers** — large-body threats (parse `Card.power`, guarding
     non-numeric `"*"`-style values) carrying evasion (Flying/Menace/Trample/"can't be blocked"
     via `keywords` + oracle text) or game-ending haymaker text (à la Craterhoof's team pump +
     trample). [epics 2.3; FR10]

4. **FR12 hard-trigger booleans.** Given the deck's cards, when scanned, then **mass-land-denial**
   and **extra-turn-chain** detection each return a deck-level boolean *and* the contributing card
   names (5.7 needs the boolean for the Bracket floor; FR23's flags need the names). Symmetric
   destruction still counts (Armageddon is the canonical MLD card); a single extra-turn spell
   (Time Warp) sets the extra-turn signal — chain refinement beyond presence-detection is 5.7's
   concern, not yours. [epics 2.3; FR12]

5. **One taxonomy, defined once, deterministic.** Given AD-10, when the module is reviewed, then
   the category vocabulary (pattern lists) exists **only** in this module as module-level frozen
   constants (compiled regexes / frozensets, the `synergy.py` `COMMON_KEYWORDS` style); category
   identifiers form a **closed set** the module owns; identical input always yields identical
   output with **deterministically ordered** (sorted) name lists; and nothing in
   `src/mcp_server/` or the skills duplicates any pattern (this story adds no tool-layer code at
   all). [epics 2.3; AD-10; AD-8 spirit]

6. **Offline unit tests prove the taxonomy on canonical cards — positives, negatives, and traps.**
   Given the project's testing rules, when the test module runs (no `integration` marker, no DB),
   then hand-built `Card`/`DeckCard` fixtures verify at minimum:
   - canonical positives per category (e.g. Sol Ring/Rampant Growth → ramp; Divination/Rhystic
     Study → draw; Swords to Plowshares/Counterspell/Wrath of God → removal/interaction;
     Demonic Tutor → tutor; Thassa's Oracle-style "you win the game" → explicit wincon;
     Armageddon → MLD; Time Warp → extra turn);
   - the AC2 negative guardrails (basic land ≠ ramp; fetch-to-battlefield ≠ tutor; vanilla
     creature ≠ anything);
   - **quantity-awareness** (a 4-of counts 4, the Standard case);
   - **multi-face handling** (a card whose top-level `oracle_text` is `""` with text in
     `card_faces` — see Dev Notes trap #1 — classifies from its faces, or the chosen documented
     behavior);
   - **determinism** (two calls on the same input produce equal results, sorted lists).
   Tests verify **behavior on synthetic cards**, not exact pattern-list contents — pattern lists
   will be tuned by 5.9's benchmark pass without rewriting tests. Runs green under
   `uv run pytest -m "not integration"`. [project-context#Testing Rules; 5-1/5-2 verify-by-shape lesson]

7. **Quality gates pass — including the `src/`-touch plugin mirror.** Given this story adds files
   under `src/`, when committed, then `mypy --strict` passes (full hints, Google docstrings on
   module + public functions — the docstrings double as the taxonomy's documentation), `ruff
   check` + `ruff format` are clean, and the regenerated `plugin/` mirror is staged in the same
   commit (run `uv run python -m scripts.build_plugin` explicitly if the pre-commit hook is
   absent — epic-4 action item). [project-context#Code Quality; epic-4 retro]

## Tasks / Subtasks

- [ ] **Task 1 — Design the classification surface** (AC: 1, 2, 5)
  - [ ] Add `src/logic/assessment/classifiers.py` with a module docstring naming it the single
        AD-10 oracle-text taxonomy (one vocabulary; tools/skills call it, never fork it).
  - [ ] Define the closed category-token set as a module-level constant (e.g.
        `CATEGORY_*` string constants or a `Literal` alias — see Dev Notes "Recommended shape").
  - [ ] Define one internal text-access helper (e.g. `_match_text(card) -> str`) that lowercases
        `oracle_text` **and falls back to joining `card_faces[*]["oracle_text"]` when the
        top-level text is empty** (trap #1), plus reminder-text stripping (trap #2) — every
        classifier matches through this one helper so the policy has a single owner.
  - [ ] Per-card entry point (e.g. `classify_card(card: Card) -> frozenset[str]`) + deck-level
        aggregation over `Sequence[DeckCard]` returning quantity-aware counts and sorted
        card-name tuples per category (the `synergy.py` quantity idiom).

- [ ] **Task 2 — FR6 pattern vocabulary** (AC: 2, 5)
  - [ ] Ramp: mana-producing artifacts/creatures (`"add {"` mana abilities on non-Land
        `type_line`s), land-fetch-to-battlefield, cost-reduction is OUT of scope (keep v1 tight).
  - [ ] Card draw/advantage: "draw a card/cards/that many cards", impulse-style exile-to-play is
        optional; document what's in/out at the pattern site.
  - [ ] Removal/interaction: "destroy target", "exile target", "counter target", damage-to-target
        removal, mass wipes ("destroy all/each"); consider a `board_wipe` sub-tag only if free —
        5.5 can add it if its 8×8 math needs it.
  - [ ] Tutors: "search your library for a card / a … card" to hand or top of library, EXCLUDING
        the land-fetch patterns already claimed by ramp (order the checks or make patterns
        disjoint).
  - [ ] Comment each pattern group with 1–2 canonical card examples (they become the test cases).

- [ ] **Task 3 — FR10 win-condition tags** (AC: 3, 5)
  - [ ] Explicit wincon: "you win the game" / "loses the game" (opponent-facing) patterns.
  - [ ] Combo-piece heuristics: conservative text signals (untap-other-permanents, copy-spell/
        ability, "any number of times"); document that this is a heuristic pre-signal, superseded
        for combo purposes by 5.6's Spellbook matching.
  - [ ] Evasive/haymaker finisher: numeric-power parse with `"*"`/`None` guard + evasion from
        `keywords` (case-insensitive — Scryfall stores `"Flying"`) and oracle text; haymaker text
        patterns (mass pump/overrun-style).

- [ ] **Task 4 — FR12 hard triggers** (AC: 4, 5)
  - [ ] Mass land denial: destroy/exile/return-all-lands, "each player sacrifices … lands",
        lands-don't-untap stax patterns; per-card tag → deck boolean + contributing names.
  - [ ] Extra turns: "take an extra turn" (self-directed); per-card tag → deck boolean + names.

- [ ] **Task 5 — Package exports** (AC: 1, 5)
  - [ ] Re-export the public names from `src/logic/assessment/__init__.py` (extend the existing
        `__all__` additively; do not touch `src/logic/__init__.py`).
  - [ ] No `profiles.py` change is expected — classifiers are profile-independent raw signals; if
        you find yourself adding a threshold to `FormatProfile`, stop (that's 5.4/5.5/5.8).

- [ ] **Task 6 — Offline unit tests** (AC: 6)
  - [ ] Add `tests/unit/logic/test_assessment_classifiers.py` (flat, beside
        `test_assessment_profiles.py` — see Project Structure Notes).
  - [ ] Build a small local `Card`-factory helper (or reuse the `tests/fixtures/card_data.py`
        style) producing minimal valid `Card`s — note `Card` requires many fields; a
        `make_card(**overrides)` helper keeps tests readable.
  - [ ] Cover the AC6 matrix: per-category positives, negatives/traps, quantity math, multi-face
        fallback, determinism/sorting. Failure messages name the card and category.

- [ ] **Task 7 — Quality gates + plugin mirror** (AC: 7)
  - [ ] `uv run ruff check . --fix && uv run ruff format .`
  - [ ] `uv run mypy src/` (strict) — full hints on all new functions.
  - [ ] `uv run pytest -m "not integration"` green (baseline: 729 passing after 5.2 review fix).
  - [ ] Commit with the regenerated `plugin/` mirror staged (`uv run python -m
        scripts.build_plugin` if the hook is missing). Never `--no-verify`.

## Dev Notes

### What this story is — and is NOT

- **IS:** one new pure module of oracle-text/type-line classification functions + its offline
  tests + `assessment/__init__.py` re-exports. Raw categorical signals with names attached.
- **IS NOT:** any signal→0–100 mapping, dimension math, count thresholds (cheap-cmc cutoffs,
  8×8 baselines), `structural_gaps[]` enum (5.5), combo matching against real data (5.6),
  Bracket-floor logic (5.7), confidence tokens (5.8), profile edits, or tool/skill-layer code.
  If a function needs `FormatProfile`, a DB, or the combo snapshot — it belongs to a later story.

### Trap #1 — multi-face cards store `oracle_text=""` (verified)

`transform_scryfall_card` stores `oracle_text = card_json.get("oracle_text") or ""`
(`src/data/importers/transformers.py:67`), and Scryfall omits top-level `oracle_text` for
split/DFC/MDFC layouts — their text lives in `Card.card_faces` (list of dicts, each with its own
`oracle_text` key, possibly absent on vanilla faces). Commander decks routinely play MDFCs.
**Classify over a joined text of all faces when the top-level text is empty** (or always join —
document the choice), via the single text-access helper (Task 1). `synergy.py` already handles
the analogous `//` face problem for `type_line` (`_extract_creature_types`); `type_line` itself
IS joined with `//` at the top level, so substring checks like `"Land" in type_line` see all
faces — be deliberate about whether that's what you want per category (a "Creature // Land" MDFC
should probably not be excluded from finisher checks just because "Land" appears).

### Trap #2 — reminder text is a false-positive source

Parenthetical reminder text restates mechanics in classifier-triggering vocabulary (Menace's
"(…can't be blocked except by two or more creatures.)" trips evasion; some reminder texts contain
"draw a card", "sacrifice", "search your library"). The search layer already strips it
(`strip_reminder_text`, `src/search/index_builder.py:128`) — but **`src/logic` must not import
`src/search`** (layer direction is `data → logic → mcp_server`; `search` is a peer, and pulling
it in would drag its import surface into the pure core). Re-implement the small fixed-point
regex locally in `classifiers.py` with a comment cross-referencing `index_builder.strip_reminder_text`
(deliberate, documented duplication of ~10 lines beats a new cross-package edge). Strip inside
the single text-access helper so every classifier gets the same policy.

### Trap #3 — vocabulary judgment calls (decide once, comment at the pattern site)

- **Tutors do NOT feed the Bracket floor.** WotC removed tutor restrictions from Brackets in
  Oct 2025 — tutors inform the soft score/consistency only (`docs/deck-assess.md:119`). Nothing
  in this story routes tutors toward Bracket logic, but put this note in the tutor pattern's
  docstring so 5.7 doesn't misuse the count.
- **Lands that tap for mana are not ramp** — exclude on `type_line` before the `"add {"` check
  (Sol Ring: artifact, ramp; Forest: land, not ramp).
- **Opponent-facing draw** ("each opponent draws…", punisher effects) — acceptable as v1 false
  positives; don't gold-plate. The 5.9 benchmark pass is the calibration gate for pattern
  quality; your tests pin *canonical* behavior, not exhaustive corner cards.
- **`Card.keywords` casing:** Scryfall stores capitalized keywords (`["Flying"]` — see
  `tests/fixtures/card_data.py`); lowercase both sides when matching (AD-10's "lowercased
  matching" convention). `keywords` may also be `None` — guard it.
- **`Card.oracle_text` / `mana_cost` are never `None`** — the schema coerces NULL → `""`
  (`src/data/schemas/card.py:72`), so `.lower()` is always safe on them. `power` is
  `str | None` and can be `"*"` / `"1+*"` — parse defensively (AC3).

### Recommended shape (guidance, not a straitjacket)

```python
# classifiers.py — sketch
RAMP: Final = "ramp"                     # closed category-token set, this module owns it
CARD_DRAW: Final = "card_draw"
INTERACTION: Final = "interaction"       # spot removal + wipes + counters (FR6's removal/interaction)
TUTOR: Final = "tutor"
WINCON_EXPLICIT: Final = "wincon_explicit"
WINCON_COMBO_PIECE: Final = "wincon_combo_piece"
WINCON_FINISHER: Final = "wincon_finisher"
MASS_LAND_DENIAL: Final = "mass_land_denial"
EXTRA_TURN: Final = "extra_turn"

def classify_card(card: Card) -> frozenset[str]: ...   # per-card tags, the joinable primitive

@dataclass(frozen=True, slots=True)
class CategoryCount:
    count: int                      # quantity-aware (a 4-of counts 4)
    card_names: tuple[str, ...]     # unique names, sorted — NFR2/FR23 explainability

def classify_deck(deck_cards: Sequence[DeckCard]) -> Mapping[str, CategoryCount]: ...
```

Why this shape: `classify_card` gives 5.4/5.5 the per-card join they need (filter by `cmc`,
compute CMC distributions) without this story pre-computing their thresholds; `classify_deck`
gives 5.5/5.7 the counts and Epic 7 the names. String tokens (not an Enum class) match the
project's closed-token style (AD-6's reasons, `structural_gaps`) — but a `StrEnum` is equally
acceptable if you prefer; keep whichever you pick consistent and exported. Frozen dataclass
precedent: `search/query.py:54`, `profiles.py`.

`DeckCard` input (not bare `Card`) is the `synergy.py` precedent and carries `quantity` — the
Standard 4-of case makes quantity-blind counting simply wrong. The spine's
`score(cards, …)` seed doesn't fix the element type ("exact filenames are seed; the boundary is
the invariant" — AD-9); keep whatever you choose consistent for 5.4/5.5 to build on. Note
`DeckCard.sideboard` exists — classifiers should not filter it; deck-composition policy (what's
"in the deck") belongs to the caller/edge, not the taxonomy.

### Determinism discipline (AD-8 spirit, applied early)

AD-8 formally binds Epic 7's serialization, but building sorted-output habits here is free:
return sorted `tuple`s (not lists/sets) for name collections, iterate patterns in fixed order,
no dict-ordering dependencies in outputs. Identical input → identical output is testable now
(AC6) and keeps 5.9's byte-identical goal from fighting upstream nondeterminism.

### Layer & purity rules (AD-2, project-context)

- Allowed imports: stdlib (`re`, `dataclasses`, `typing`, `collections.abc`) +
  `src.data.schemas.card` / `src.data.schemas.deck` (the `synergy.py` precedent — logic may
  import data schemas). Forbidden: `src/search`, `src/mcp_server`, `src/data/repositories`,
  Pydantic model definitions of your own (plain frozen dataclasses suffice; `synergy.py`'s
  Pydantic result models predate the assessment package's `search/query.py`-style convention).
- No I/O of any kind, no `datetime`, no logging side effects needed (pure functions; if you log,
  module-level `logger` + `%`-lazy args per project-context — but pure classifiers shouldn't need
  to).
- Python 3.12: `X | None`, builtin generics, `Final`; compiled regexes as module constants
  (`_RAMP_RE: Final = re.compile(...)`), matching `synergy.py` / `index_builder.py` style.
- Google docstrings on module + every public function; the docstrings are the taxonomy's
  human-facing definition (what counts as ramp?) — write them as such.

### Previous-story intelligence (5.2, just completed)

- The package + `__init__.py` re-export pattern is established — extend `__all__` additively;
  `DIMENSIONS`, `FormatProfile`, profiles are already exported. Don't touch `profiles.py` (any
  value change there requires a version bump; you have no reason to change values).
- **Verify by shape/behavior, not tunables** (5.1→5.2 lesson, applied): AC6 pins canonical-card
  behavior; it does NOT assert pattern-list lengths or exact regex strings, so 5.9-era pattern
  tuning doesn't shred tests.
- **Plugin mirror:** 5.2 hit this — `.git/hooks/pre-commit` may be absent (epic-4 action item);
  5.2 ran `uv run python -m scripts.build_plugin` explicitly and staged
  `plugin/server/src/logic/assessment/`. Your new `classifiers.py` will mirror the same way;
  `plugin/*.json` diffs that are line-ending-only are noise (5.2 dev record) — don't chase them.
- **Fast-suite baseline:** 728 passed at 5.2 completion, +1 review-added test
  (`test_combos_enabled_per_format`) = 729 expected before your additions.
- 5.2's deferred review finding (`__post_init__` validation on `FormatProfile`) is not yours.

### Testing standards

- pytest config in `pyproject.toml`: `asyncio_mode="auto"`, `--strict-markers`, `--tb=short`.
  These tests are synchronous, no markers (they run in the fast `-m "not integration"` subset).
- Flat placement `tests/unit/logic/test_assessment_classifiers.py` beside
  `test_assessment_profiles.py` (5.2 anticipated a `tests/unit/logic/assessment/` subdir "when
  volume warrants"; two files don't warrant it yet — introduce it only if this story's test file
  gets unwieldy, and then move `test_assessment_profiles.py` in the same commit so the layout
  stays coherent).
- `tests.*` is mypy-exempt but write full hints anyway (matches the sibling test modules).
- Building fixture `Card`s: the schema has many required fields (`id`, `name`, `oracle_id`,
  `mana_cost`, `cmc`, `type_line`, `oracle_text`, `rarity`, `set_code`, `set_name`,
  `collector_number`, `colors`, `color_identity`, `legalities`) — a local `make_card(**kw)`
  factory with sensible defaults keeps each test case to the fields that matter
  (`tests/fixtures/card_data.py` shows the full-construction style but builds `CardModel`s for
  integration use; for these unit tests build Pydantic `Card`s directly).

## Project Structure Notes

**New/changed files:**

```text
src/
  logic/
    assessment/
      __init__.py       # MODIFIED: extend __all__ with classifier exports (additive)
      classifiers.py    # NEW: the AD-10 taxonomy — category tokens, patterns,
                        #      classify_card, classify_deck, FR12 trigger scans
tests/
  unit/
    logic/
      test_assessment_classifiers.py   # NEW: offline canonical-card behavior tests
plugin/                                # REGENERATED mirror (commit the diff)
```

- Module name `classifiers.py` matches the spine's Structural Seed wording ("oracle-text
  classifiers" inside `logic/assessment/`); filenames are seed, the boundary (pure, in
  `assessment/`) is the invariant (AD-9).
- No changes to `src/logic/__init__.py`, `profiles.py`, `synergy.py`, or any `src/mcp_server`
  file. `synergy.py` keeps its own patterns — it serves a different feature (synergy detection)
  and consolidating it into this taxonomy is explicitly NOT in scope (AD-10 governs the
  *assessment* vocabulary; refactoring the legacy skill surface is not this story).

## References

- [Source: _bmad-output/planning-artifacts/epics-deck-power-assessment.md#Story 2.3] — the four
  binding ACs (FR6 counts, FR10 tagging, FR12 booleans, AD-10 no-duplication).
- [Source: epics-deck-power-assessment.md#Story 2.4, #Story 2.5, #Story 2.7; #Epic 4 Story 4.3
  (flags)] — the downstream consumers whose needs fix this story's output shape.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-11/ARCHITECTURE-SPINE.md#AD-10]
  — one shared taxonomy, `synergy.py` conventions, never duplicated into the tool layer.
- [Source: ARCHITECTURE-SPINE.md#AD-2, #AD-8, #AD-9] — purity (no network/DB/clock), sorted
  deterministic outputs, layer placement.
- [Source: docs/deck-assess.md#3.1] — the FR6/FR10/FR12 signal definitions (Command Zone / 8×8
  category framing, win-condition identification, hard bracket triggers) and the Oct-2025
  tutor-restriction removal note (line 119).
- [Source: src/logic/synergy.py] — the matching conventions to follow: lowercased oracle text,
  compiled/raw regex patterns, quantity-aware counting over `DeckCard`, `_extract_creature_types`
  face handling.
- [Source: src/data/importers/transformers.py:67] — verified: multi-face cards persist
  `oracle_text=""`; faces carry the text (Dev Notes trap #1).
- [Source: src/data/schemas/card.py; src/data/schemas/deck.py:14] — `Card` field inventory +
  NULL-coercion validators (`oracle_text`/`mana_cost` never None); `DeckCard.quantity`/`sideboard`.
- [Source: src/search/index_builder.py:122-165] — the reminder-text stripping approach to
  replicate locally (do not import; layer rule in Dev Notes trap #2).
- [Source: src/logic/assessment/profiles.py; _bmad-output/implementation-artifacts/5-2-format-profile-frozen-data-module.md]
  — package conventions, verify-by-shape testing lesson, plugin-mirror handling, 729-test baseline.
- [Source: _bmad-output/project-context.md#Language-Specific Rules, #Testing Rules, #Code Quality]
  — mypy --strict / ruff / Google docstrings / pytest gates.

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
