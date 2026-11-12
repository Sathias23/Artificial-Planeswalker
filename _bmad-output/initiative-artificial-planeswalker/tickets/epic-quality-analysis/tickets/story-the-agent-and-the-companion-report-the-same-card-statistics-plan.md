---
title: 'The agent and the companion report the same card statistics'
type: 'bugfix'
ticket: '5'
created: '2026-11-12'
status: 'review'
baseline_revision: '06190977325b2e3c3c47868e328c29054e1aef45'
route: 'full'
route_source: 'auto'
risk: 'high'
review: 'quick'
review_source: 'pinned'
lenses_ran: ['quick']
review_loop_iteration: 0
context:
  - '{project-root}/AGENTS.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The same deck gets different land counts, curves and colour counts from the agent and the companion (`M1` = `B4-D2` + `F6-P7`). Python has four land rules (`mana_curve.py:74`/`:277` case-sensitive `"Land"` anywhere; `mana_base._is_land` and `classifiers.py:280` lowercase substring), the UI a fifth (`curve.ts::isLand`, front-face whole word). So a `Sorcery // Land` MDFC is a land to the agent and a spell to the companion. A 0-cost spell is bucket 0 for the agent and bucket 1 for the companion. A 9-drop is bucket 9 for the agent and `7+` for the companion. Hybrid pips count for nothing in Python and for both colours in `colours.ts::coloursOf`. Two UI headers (`curve.ts`, `colours.ts`) claim the panel and the tool "cannot answer the same question differently". `F6-P8`: `curveOf`'s `as unknown as` cast lets an eighth `BUCKETS` entry compile against the seven-tuple type.

**Approach:** D1 (a). A new framework-free `src/logic/card_statistics.py` owns the front-face type rule, land detection, mana-value bucketing and colour-pip counting, and `deck_statistics()` computes them over commander + mainboard (sideboard excluded). `analyze_mana_curve` and a new `statistics` field on the companion's deck-detail payload both come from it. The UI draws the payload's figures and deletes `isLand`, `bucketOf` and `coloursOf`. Tests pin today's behaviour first, so the diff shows what moved.

**Decisions (Brad, 2026-11-12):** (1) `analyze_mana_curve`'s `distribution` becomes the shared seven buckets (`"1"`…`"7"`, always all seven, `"7"` = 7 or more, 0-cost spells in `"1"`); its issues read it, and `playable_cards_by_turn` and `average_cmc` stay on the exact `cmc`. (2) `analyze_mana_curve` gains `colour_pips` (docstrings and skills updated). (3) The classifier's ramp/tutor exclusion uses a separate, named `has_land_face` (any face, whole word) in `card_statistics.py`; MDFCs stay out of ramp and tutors as today. The plan is kept whole despite exceeding the token guide.

## Boundaries & Constraints

**Always:** One land rule: the word `land` in the type half (before `—`) of the **front face**, where the front face is `card_faces[0].type_line` when present, else the top-level `type_line` before ` // `. Buckets are `CURVE_BUCKETS = (1, …, 7)`: round half up, `≤1` folds into 1, `≥7` folds into 7 (UX-DR17). Colour pips follow `parse.ts`'s symbol rules (a hybrid credits each colour; Phyrexian is a modifier; a generic-hybrid credits its colour; generic and `{X}` credit nothing; `{C}` is colourless), read from the front-face cost (split shape first, then top-level, then `card_faces[0]`), non-land rows only, quantity-aware. Tests drive the MCP client, `build_app()` routes and UI component tests, over `tmp_path` databases built by `create_engine` + `init_database`. Each new guard is proved red through `scripts.probe_harness` / `scripts.vitest_probe_harness`. Ripple in this PR: `npm run gen:api` (`openapi.json`, `types.d.ts`), `npm run build` (static bundle), `scripts.build_plugin` (`plugin/`), tool docstrings, the five skills and `docs/companion.md`. `src/companion/` stays read-only (AD-2).

**Never:** No change to `src/viewer/` (AD-15) or `groupOf` (10.11 owns `Card // Card` grouping). No change to the assessment's scoring math, pip anchors (the 23-source Commander target), resilience weights or bare-pip Karsten demand. No change to the internal score inputs `CurveSignals.distribution` and `InteractionSignals.cmc_distribution`. No mana-curve polish from `deferred-work.md`. No source-text scanning.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Verify deck | MDFC `Sorcery // Land` ×1, 0-cost artifact ×1, 7-drop ×1, 9-drop ×1, Forest ×2, `{G/W}` creature ×2, 1 commander, 1 sideboard card | tool `total_lands` = payload `land_count` = 2; tool `distribution` = payload `curve` = panel bars (`1`: 2 incl. the 0-cost, `7+`: 2); colour pips equal on all three; the sideboard card is counted nowhere | none |
| Land face behind a spell | `Creature — Elemental // Land` | a spell: front-face pips count, no land source | none |
| `Card // Card` printing | top `type_line` `Card // Card`, `card_faces[0].type_line` `Land` | a land | none |
| `Lander` subtype, Dryad Arbor | `Artifact Creature — Lander`; `Land Creature — Forest Dryad` | spell; land | none |
| Fractional / huge MV | cmc 0.5, cmc 1000000 | bucket 1; bucket 7 | none |
| All lands / empty deck | lands only; no cards | `curve` all zeros, colour pips all zero; panels render nothing; tool answers `empty` for no mainboard, as today | none |

</frozen-after-approval>

## Code Map

- `src/logic/mana_curve.py:74`, `:277` -- the two `"Land" in type_line` rules; `:86` and the `int(cmc)` sites build `distribution`. `test_zero_cmc_spells_in_distribution` pins bucket 0.
- `src/logic/assessment/mana_base.py:69-78` `_is_land` (used at `:125`, `:181`, `:364`); `:318` `_source_text` joins every face (the 7.6 spell-face note); `_pip_cost` stays (Karsten demand, unchanged).
- `src/logic/assessment/classifiers.py:280` -- the ramp/tutor exclusion `is_land` ("land-slot material": any face).
- `src/mcp_server/tools/deck_analysis.py:41-75`, `:128-200` -- `ManaCurveResult` and its docstring; `src/mcp_server/server.py:1009` -- the LLM-facing docstring.
- `src/data/schemas/deck.py` `DeckDetailFull` -- the companion-only deck detail. `src/data` cannot import `src/logic`, so the payload model is a logic-side subclass (Design Notes).
- `src/companion/app/routes/decks.py:61` -- `read_deck`'s `response_model`.
- `ui/src/containers/ManaCurve/curve.ts` -- `BUCKETS`, `LAST_BUCKET` (kept), `isLand`, `bucketOf`, `curveOf` and the `:250` cast; header `:43-51` is the parity claim.
- `ui/src/containers/ColourDistribution/colours.ts` -- `coloursOf`; header `:110-134` is the parity claim plus the five-axis divergence note. `ColourDistribution.tsx:134` holds the card-store subscription that becomes unneeded.
- `ui/src/App.tsx:182-183` -- panel mounts (`boards` → `deck.detail.statistics`). `ui/src/api/schema.ts:88`, `:103` -- aliases.
- `ui/src/state/deckGroups.ts` header `:23-50`, `:230` -- stale land-policy and `bucketOf` notes.
- Tests that move: `test_assessment_mana_base.py::test_mdfc_with_land_face_counts_as_land`, `::test_land_mdfc_is_excluded_from_pip_demand`; `test_mana_curve.py::test_zero_cmc_spells_in_distribution`; `ui/.../curve.test.ts` and `colours.test.ts` (their rule cases move to Python); the `ManaCurve`/`ColourDistribution` component tests and every `DeckDetail` fixture in `App.test.tsx`, `deck.test.ts`, `deckGroups.test.ts`, `client.test.ts`, `ConnectionPill`, `DeckAnnouncer`, `GroupsView` (they gain `statistics`).
- Precedents: `tests/integration/mcp_server/test_deck_analysis_tool.py` (tool helper over a tmp DB), `tests/unit/companion/test_routes_decks.py::TestDeckDetail` (route), `ui/src/api/schema.test.ts` (`expectTypeOf` is typecheck-gated).
- Skills: `mana-curve-analysis/SKILL.md:110-119` (MDFC and `cmc` caveats), `:136-176` (sparse `distribution`, string keys), `:155` (contract row); `magic-deckbuilding/SKILL.md:78`, `:193`.

## Tasks & Acceptance

**Execution:**
- [x] Pin first (commit 1, passes on baseline): `tests/unit/logic/test_card_statistics_baseline.py`, which records the current tool figures and `compute_curve` / `compute_pip_signals` for the matrix decks. Rewrite each pin in the commit that moves it.
- [x] `src/logic/card_statistics.py` (new) -- `front_face_type_line`, `is_land`, `has_land_face`, `CURVE_BUCKETS`, `mana_value_bucket`, `front_face_mana_cost`, `colour_pips`, the `DeckStatistics` model and `deck_statistics()`, plus `DeckDetailWithStatistics` (Design Notes).
- [x] `src/logic/mana_curve.py` -- both land rules → `is_land`; `distribution` → all seven `CURVE_BUCKETS` keys; `playable_cards_by_turn` and `average_cmc` stay on the exact `cmc`.
- [x] `src/logic/assessment/mana_base.py` -- `_is_land` → `is_land`; `_source_text` reads land faces only (each face's `type_line` when faces carry one). `classifiers.py:280` → `has_land_face` (whole word, any face; MDFC behaviour unchanged).
- [x] `src/mcp_server/tools/deck_analysis.py`, `server.py` -- `ManaCurveResult` gains `colour_pips` (Decision 2). The figures come from `deck_statistics`; docstrings name the seven buckets, the front-face land rule and the pips.
- [x] `src/companion/app/routes/decks.py` -- `response_model=DeckDetailWithStatistics`.
- [x] Python tests: `tests/unit/logic/test_card_statistics.py` (matrix rules; `CURVE_BUCKETS` tied to the schema's tuple arity and to `deck_statistics` output); `tests/integration/mcp_server/test_card_statistics_parity.py` (verify deck through the MCP client and `GET /api/deck/{id}`, and both against the committed `ui/src/test-fixtures/deck-statistics.json`).
- [x] `ui/` -- `npm ci`; `npm run gen:api`; `curve.ts`/`colours.ts` draw the payload (delete the three functions; `curveOf` takes `statistics.curve` with no cast; rewrite both headers); panels take `statistics`; drop the `ColourDistribution` store subscription; `schema.ts` alias; fixtures gain `statistics`; `deck-statistics.json` (loaded with `import.meta.glob`) drives a panel test whose rendered bars and legend equal its tool figures; `expectTypeOf` ties `DeckStatistics['curve']['length']` to `BUCKETS`, plus a runtime length check; prune `deckGroups.ts` stale notes.
- [x] Skills, `docs/companion.md`, `plugin/` (`scripts.build_plugin`), static bundle (`npm run build`).
- [x] Probe proofs (Design Notes) recorded in Implementation Notes.

**Acceptance Criteria:**
- Given the verify deck, when `analyze_mana_curve` runs through the MCP client and `GET /api/deck/{id}` through `build_app()`, then `total_lands`, `total_spells`, `distribution` and `colour_pips` equal the payload's `statistics`, and both equal `deck-statistics.json`.
- Given `deck-statistics.json`, when the two panels render it, then the seven bar counts equal its `distribution` and the legend's counts equal its non-zero `colour_pips`.
- Given the finished branch, when `grep` runs for land, bucket and pip rules across `src/` and `ui/src/`, then the only hits outside `card_statistics.py` are the frozen viewer, `is_basic_land`, `groupOf`, the bare-pip Karsten demand, and display-only `frontFaceCost`.
- Given the 7.6 pins, when the suite runs, then each passes unchanged (prediction: none use a spell-front MDFC or a land with a non-land face). If one moves, it is updated in the same commit and the reason recorded.

## Implementation Notes

Commits on `fix/quality-7-5-shared-card-statistics` over baseline `0619097`: `63bfbad` (pins, green on baseline), `8f1b164` (shared rules, tool, route, Python tests, pins rewritten with `MOVED` notes, `openapi.json`/`types.d.ts`, the JSON fixture, `plugin/`), `4d3ad4e` (UI draws the payload, static bundle, `plugin/`), `9aba875` (skills, `docs/companion.md`, `plugin/skills`), `02bd71a` (stale `deckGroups` notes), `38c71b2` (synthetic em-dash case added for plant 2).

What was built:
- `src/logic/card_statistics.py`: `front_face_type_line`, `type_line_is_land` (whole word `land`, case-insensitive, in the type half before `—`), `is_land`, `has_land_face`, `CURVE_BUCKETS`, `mana_value_bucket` (`floor(cmc + 0.5)` clamped to 1..7, which matches `Math.round`), `front_face_mana_cost`, `colour_pips` (a Python port of `parse.ts`'s `classify`), `ColourPips`, `DeckStatistics`, `deck_statistics()`, `curve_distribution()`, `DeckDetailWithStatistics`. Its published docstring keeps `DeckDetailFull`'s "order of `cards` is not meaningful" sentence.
- `analyze_mana_curve`: `total_lands`, `total_spells`, `distribution` (all seven keys) and the new `colour_pips` (a list of `{colour, count}`, the same shape as the payload) come from `deck_statistics(deck.deck_cards)`. The logic's own `ManaCurveAnalysis.distribution` uses the same buckets, so the issues read it. `average_cmc` and `playable_cards_by_turn` now use the exact `cmc`; before, both used `int(cmc)`.
- `mana_base.py`: three `_is_land(card.type_line)` sites become `is_land(card)`. `_source_text` now joins land faces only: a face's own `type_line`, else the matching `" // "` half, else kept. `classifiers.py` uses `has_land_face`.
- UI: `curveOf(statistics.curve)` builds the seven-tuple position by position, with no cast. `segmentsOf(statistics.colour_pips)` replaces `coloursOf` and maps the wire letters through a typed `Record`. Both panels take a `statistics` prop. `App.tsx` passes `surface.detail.statistics`. `ColourDistribution` no longer reads `useCardStore`. `readDeck`'s `deckOf` now refuses a body with no `statistics.curve` or `statistics.colour_pips` array; without that, a malformed body would throw in render. Three new `client.test.ts` cases cover it. Every `DeckDetail` fixture gained `statistics`. In `App.test.tsx`, `deckDetail()` defaults to the default deck's figures, gives all-zero statistics when a test overrides `cards`, and the five Bears refetch fixtures carry explicit figures.
- Tests: `test_card_statistics.py` (74 cases), `test_card_statistics_parity.py` (3 tests: tool against payload, both against `ui/src/test-fixtures/deck-statistics.json`, and the fixture read by hand), `curve.test.ts` (an `expectTypeOf` tie plus a runtime tie against the fixture), and fixture-driven panel tests in `ManaCurve.test.tsx` and `ColourDistribution.test.tsx`. The fixture file holds both the tool-shaped figures (`analyze_mana_curve`) and the payload shape (`statistics`). The panel tests render `statistics` and compare the result with the tool figures.

What moved (all pinned in `test_card_statistics_baseline.py` with `MOVED` notes; the diff of `63bfbad..8f1b164` on that file is the record):
- Verify deck, tool: lands 3 -> 2, spells 6 -> 7, `distribution` `{0:1,3:2,4:1,7:1,9:1}` -> `{1:2,2:0,3:2,4:1,5:0,6:0,7:2}`, `average_cmc` 26/6 -> 27/7.
- Verify deck, assessment: `compute_curve` lands 3 -> 2. `compute_pip_signals` G demand 5 -> 6 (the MDFC's front `{G}`) and W sources 1 -> 0 (the MDFC's back-face "Add {W}" no longer counts). This is the score shift the Design Notes predicted; benchmark deltas belong to 7.7.
- Edge cards: Florahedron becomes a spell; the `Card // Card` land becomes a land; the Lander becomes a spell; fractional/huge mana values become bucket 1 and bucket 7 in the tool only (the assessment's internal floor buckets do not move).
- Classifier: the `Card // Card` land loses `ramp`, because it is now excluded by its land face. The Lander gains `ramp`: its land search reads as ramp once "Lander" is not the word "land". Neither is an MDFC, and MDFC behaviour is unchanged.
- Existing tests rewritten: `test_mana_curve.py` (`test_basic_distribution`, `test_lands_excluded_from_distribution`, `test_zero_cmc_spells_in_distribution`, plus two new tests), `test_assessment_mana_base.py` (`test_mdfc_with_land_face_counts_as_land` -> `test_mdfc_with_spell_front_face_counts_as_spell`, `test_land_mdfc_is_excluded_from_pip_demand` -> `test_spell_front_mdfc_contributes_its_front_face_pips`, plus `test_land_front_face_counts_as_land` and `test_front_face_land_reads_only_its_land_faces_for_sources`), `test_deck_analysis_tool.py::test_analyze_mana_curve_ok` (seven keys), `test_committed_schema.py` (component set 31 -> 33: `+ColourPips`, `+DeckStatistics`, `+DeckDetailWithStatistics`, `-DeckDetailFull`), `test_routes_decks.py` (schema refs, plus a `statistics` ref assertion).
- AC 4: every 7.6 pin passes unchanged (`test_assessment_dimensions.py`, `test_compare_deck_power_tool.py`, `test_assessment_wire_determinism.py`, the two `Land // Land` source tests). The prediction held.

Probe proofs. The tree was committed before planting. A driver applied each plant alone, ran `uv run python -m scripts.probe_harness --expect-red '<node id>'`, restored the original bytes, then ran `git diff --exit-code <file>`.

| # | Plant (file) | Proof line | Expected RED (substring) | harness exit | `git diff --exit-code` |
|---|--------------|------------|--------------------------|--------------|------------------------|
| 1 | `is_land` reads the whole top-level `type_line` (`card_statistics.py`) | `full suite (-m 'not integration'): 3649 collected, 11 failed, 0 errored, exit 1` | `test_is_land_reads_the_front_face_type_half[Sorcery // Land-False]` (also `test_card_card_printing_is_a_land_by_its_first_face`, the verify-deck tests, the parity fixture test) | 0 | 0 |
| 2 | em-dash split dropped from `type_line_is_land` | `full suite (-m 'not integration'): 3649 collected, 1 failed, 0 errored, exit 1` | `[Enchantment Creature — Land Spirit-False]` (only that case) | 0 | 0 |
| 3 | `<=1` fold removed from `mana_value_bucket` | `full suite (-m 'not integration'): 3649 collected, 10 failed, 0 errored, exit 1` | `test_mana_value_bucket_rounds_half_up_and_folds_both_ends[0.0-1]` (also both parity tests, `test_zero_cmc_spells_in_distribution`) | 0 | 0 |
| 4 | `>=7` cap removed from `mana_value_bucket` | `full suite (-m 'not integration'): 3649 collected, 16 failed, 0 errored, exit 1` | `[9.0-7]`, `[12.0-7]`, `[1000000.0-7]` (also both parity tests, `test_seven_or_more_shares_the_last_bucket`, three companion route tests whose deck carries cmc > 7) | 0 | 0 |
| 5 | a hybrid credits one colour (`_symbol_colours`) | `full suite (-m 'not integration'): 3649 collected, 7 failed, 0 errored, exit 1` | `test_colour_pips_follow_the_ui_symbol_rules[{W/U}` (also `{G/W}{G/W}`, `{G/W/P}`, the parity fixture test) | 0 | 0 |
| 6 | sideboard rows counted (`deck_statistics`) | `full suite (-m 'not integration'): 3649 collected, 6 failed, 0 errored, exit 1` | `TestVerifyDeck::test_the_sideboard_is_counted_nowhere` (also the parity fixture test, `test_analyze_mana_curve_ok`) | 0 | 0 |
| 7 | `_source_text` reads every face (`mana_base.py`) | `full suite (-m 'not integration'): 3649 collected, 1 failed, 0 errored, exit 1` | `test_front_face_land_reads_only_its_land_faces_for_sources` | 0 | 0 |
| 8 | tool `distribution` from exact `int(cmc)` (`deck_analysis.py`) | `full suite (-m 'not integration'): 3649 collected, 2 failed, 0 errored, exit 1` | `test_tool_and_payload_report_the_same_figures`, `test_both_equal_the_committed_ui_fixture` | 0 | 0 |
| 9 | route drops `statistics` (`DeckDetailFull` as `response_model` and return) | `full suite (-m 'not integration'): 3649 collected, 3 failed, 0 errored, exit 1` | both parity tests (plus `test_committed_schema_matches_the_live_app`) | 0 | 0 |
| 10 | `CURVE_BUCKETS` gains an 8th entry | `full suite (-m 'not integration'): 3649 collected, 23 failed, 0 errored, exit 1` | `test_curve_buckets_match_the_payload_tuple_arity` (also `test_curve_buckets_are_one_to_seven`, the cap cases, both parity tests, the curve pins) | 0 | 0 |
| 11 | `BUCKETS` gains an 8th entry (`ui/.../curve.ts`) | `vitest: 59 files / 1826 tests, 4 failed, exit 1` (control: `vitest: 59 files / 1826 tests, 0 failed, exit 0`, `--expect-total 1826`) | `RUNTIME` (`curve.test.ts` "has exactly as many buckets as the server sends counts — at RUNTIME", also the bucket-name tests and the fixture-driven `ManaCurve` test) | 0 | 0 |

Plant 11, typecheck half (`npx tsc -b` with the plant in): `src/containers/ManaCurve/curve.test.ts(38,51): error TS2344: Type '8' does not satisfy the constraint '"Expected: literal number: 8, Actual: literal number: 7"'.`

Plant 1 does not redden `test_tool_and_payload_report_the_same_figures`. Both sides share the broken rule, so they still agree, and the committed-fixture test is the one that catches it. That split between the two tests is by design.

AC 3 grep (land, bucket and pip rules across `src/` and `ui/src/`, outside `card_statistics.py`): the frozen `src/viewer/view_model.py::is_land`, `deck_validator.py::is_basic_land`, `deckGroups.ts::groupOf`, the bare-pip `mana_base._MANA_SYMBOL_RE` demand with `_pip_cost`, display-only `frontFaceCost`/`ManaCost`, and the internal `int(cmc)` floors behind `CurveSignals.distribution` and `InteractionSignals.cmc_distribution` (kept by the Never clause). One more hit the AC list does not name: `mana_curve.generate_contextual_feedback` still builds its private throttling distribution with `int(cmc)`. It is not exposed by any tool (only `test_mana_curve.py` calls it), it prints the card's mana value in its messages, and changing it would be the "mana-curve polish" the Never clause excludes. Its land rule did move to `is_land`. It was left alone deliberately and is flagged for review.

Gates (finished branch, `38c71b2`): `ruff check .` and `ruff format --check .` clean; `mypy src/` and `mypy src/ --platform win32` no issues (97 files); `uv run pytest` 3674 passed, 2 skipped. From `ui/`: `npm run lint`, `format:check`, `typecheck` clean; `npm test` 1826 passed; `npm run test:gates` 39 passed; `npm run build` and `npm run gen:types` then `scripts.build_plugin` give no drift (`git status` clean apart from this plan file).

Residue and risks for review:
- A true split card's `cmc` is Scryfall's sum of both halves, and both sides now bucket by that sum (the old `curve.test.ts` pin of that wrongness moved with the rule; it is noted in `curve.ts` and the skill).
- `_land_source_colors` still reads basic land types from the whole top-level `type_line`, so a front-face land whose back face has a basic-type subtype would gain that colour. No such card was checked; it is outside this rule set.
- Lander-subtype artifacts with land-search text are now tagged `ramp` (whole-word `has_land_face`). That is a classifier change outside MDFCs, recorded above.

## Plan Change Log

## Review Triage Log

Pass 1 (lens `quick`, 2026-11-12): 7 findings — high 0, medium 1, low 4, false 1, maybe-false 0. Three **patch**, one **defer**, three rejected; no loopback. The lens read the diff without `plugin/` and the minified static bundle (generated copies, drift-checked).

| # | Finding | Verdict | Route | Evidence / action |
|---|---------|---------|-------|-------------------|
| 1 | Tool docstrings, both skills and `docs/companion.md` say the companion shows the same land count, but no UI code reads `statistics.land_count`; the visible "Lands" group header comes from `groupOf` (Artifact Land under Artifacts, Dryad Arbor under Creatures) | medium | patch | Verified: `ui/src` reads only `statistics.curve` and `statistics.colour_pips`. An agent citing `total_lands` beside a different "Lands" header contradicts the docs. Fixed in `dce3170`: the claim is now only that `distribution` and `colour_pips` are what the panels draw, `total_lands`/`total_spells` share the payload's rule, and type-group headers can differ; double blank line removed; `plugin/` rebuilt. |
| 2 | AC 3 grep: `generate_contextual_feedback` and its helpers keep `int(cmc)` buckets | low | defer | Verified; pre-existing, and the function has no caller in `src/` (its land rule did move to `is_land`). Routing it through `mana_value_bucket` would print bucket numbers as mana values in its messages. Appended to `deferred-work.md`. |
| 3 | `analyze_mana_curve`'s one-pass land/spell split and dropped `cmc is None` arms build story 33's deferred mana-curve polish, which the Never clause forbids | low | patch | Verified against `deferred-work.md` (story 33 entry). Fixed in `dce3170`: baseline shape restored with only the rule swapped (`lands = [... is_land(c)]`, `c not in lands`, the `cmc is None` arms back), also in `generate_contextual_feedback`; behaviour unchanged. |
| 4 | Decision 1 says `average_cmc` and `playable_cards_by_turn` "stay" on the exact `cmc`, but the baseline used `int(cmc)` | low | rejected | Verified the baseline floored. The code matches the decision as written (exact `cmc`); the two differ only for fractional `cmc` (Little Girl, 0.5, the corpus's only one). Exact `cmc` is needed for `playable_cards_by_turn` once `distribution` caps at 7. Reported to Brad rather than changed. |
| 5 | `has_land_face` moves the classifier on two non-MDFC shapes (`Card // Card` first-face land loses `ramp`; a `Lander` card with land-search text gains it) | false | rejected | Decision 3 specifies `has_land_face` as "any face, whole word", which entails both moves, and both are corrections (a land is never ramp; "Lander" is not "land"). Pinned by `test_card_statistics_baseline.py::test_classifier_land_exclusion`. Scoring math is unchanged; only its inputs follow the rule. |
| 6 | `colours.test.ts` header claims the Python file holds every deleted UI case (Omen, Pathway, `{2/W}`, Land//Adventure), but it did not | low | patch | Verified. Fixed in `dce3170`: the four cases plus an `Artifact — Equipment // Land` row added to `test_card_statistics.py`; both UI headers now list exactly what it holds. |
| 7 | `readDeck`'s new guard accepts a `curve` array of any length, so a short one would draw `NaN` heights | low | rejected | Verified in principle, but the bundle ships with its own backend, whose schema pins `minItems`/`maxItems` 7, so a short curve is unlikely in everyday use and the fix adds a guard. |

After the patches: `ruff check .`, `ruff format --check .`, `mypy src/` and `mypy src/ --platform win32` clean; `uv run pytest` 3679 passed, 2 skipped; UI lint, format:check, typecheck, `npm test` 1826 passed, `test:gates` 39 passed, build, `gen:api`/`gen:types` and `scripts.build_plugin` leave no drift.

## Design Notes

**Payload model.** `class DeckDetailWithStatistics(DeckDetailFull)` in `card_statistics.py` adds `statistics: DeckStatistics` and overrides `from_deck`. It lives in logic because `src/data` may not import logic. It is not a second deck shape (AD-1): it reuses `DeckDetailFull`'s fields and adds only logic's figures, as `FormatCheckReport` does.

```python
class DeckStatistics(BaseModel):
    land_count: int
    spell_count: int
    curve: tuple[int, int, int, int, int, int, int]  # counts for CURVE_BUCKETS, 7 = "7 or more"
    colour_pips: tuple[ColourPips, ...]              # six entries, W U B R G C, zeros kept
```

openapi-typescript 7 emits `prefixItems` as a TS tuple, so the UI's tuple comes from the server. If it does not, `curve` falls back to a list and the tie becomes the runtime check alone.

**The 7.6 inputs.** *Spell-face mana:* once the front face decides, a `Creature // Land` MDFC is no longer a land, so its spell face is never read for sources. Restricting `_source_text` to land faces closes the rest (a front-face land whose other face has mana text). The 7.6 `Land // Land` pins read two land faces and do not move. *Commander source targets and resilience weights:* the shared colour pips feed only the UI and the tool. `compute_pip_signals` keeps bare-pip demand, so neither is touched. *Score shift:* decks with spell-front MDFCs now count them as spells in the Karsten land count, pip demand and sources. That is D1's single rule; benchmark deltas are 7.7's to record. *`dimension_vector` docstring:* `dimensions.py` is not edited, so the `deferred-work.md` entry stays open.

**Plants** (one rule broken each, all reverted): land rule reads the whole `type_line`; drop the `—` split; `≤1` fold removed; `≥7` cap removed; hybrid credits one colour; sideboard rows counted; `_source_text` reads every face; tool `distribution` from exact `cmc`; route drops `statistics` (parity test); `BUCKETS` gains an 8th entry (vitest runtime tie; typecheck red also recorded); `CURVE_BUCKETS` gains an 8th (Python tie).


## Verification

**Commands:**
- `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src/`, `uv run mypy src/ --platform win32`, `uv run pytest` -- all green
- from `ui/`: `npm run lint`, `npm run format:check`, `npm run typecheck`, `npm test`, `npm run test:gates`, `npm run build`, `npm run gen:types` -- green, and `git diff --exit-code` on the generated files after the commit
- `uv run python -m scripts.build_plugin` -- `plugin/` committed, no drift
- the probe harness commands per plant -- proof lines in Implementation Notes
