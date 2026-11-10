---
title: 'Snow basics and restricted cards get the right verdict'
type: 'bugfix'
ticket: '1'
created: '2026-11-10'
status: 'review'
baseline_revision: '6f6322335427d80d69feb3331d0ed81bf48d57e6'
route: 'full'
route_source: 'auto'
risk: 'medium'
review: ''
review_source: ''
lenses_ran: []
review_loop_iteration: 0
context:
  - '{project-root}/AGENTS.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `is_basic_land` tests the substring `"basic land"`, so "Basic Snow Land — Forest" is held to the copy limit and five or more snow basics make a deck illegal (`M2` / `B4-P1`). A card whose legality is `restricted` falls through to `format_legality` ("is not legal in vintage"), so one Black Lotus makes a legal Vintage deck read illegal in `validate_deck` and on the companion's format-check panel (`B4-D1`). `_KNOWN_FORMATS` is pinned only by size and a subset check, so a Scryfall key rename would silently make a format unvalidatable (`B4-P12`).

**Approach:** Review option (a) for `B4-D1`: in a known format a `restricted` card is legal at one copy, counted across both boards, and a violation above one, reported on the copy-limit row. `is_basic_land` reads the supertypes before the dash: `Basic` and `Land` both present. A committed fixture holding real Scryfall legality dicts pins `_KNOWN_FORMATS` by equality.

**Decisions (Brad, 2026-11-10):** The over-limit restricted card gets a new `DeckViolationRule` member, `restricted_card`, mapped in `CHECK_FOR_RULE` to the `copy_limit` row (option a; mirrors `banned_card`, so quick-wins 1.4 reports the restricted rule from the vocabulary alone). The plan is kept whole despite exceeding the token guide.

## Boundaries & Constraints

**Always:** One copy-count violation per card at most; the tightest applicable limit wins. Tests drive the real entry points: the `validate_deck` tool helper against a tmp-path database, and `GET /api/deck/{id}/format-check` through `build_app()`. Each new test fails with its fix reverted, proved through `scripts.probe_harness`. Every consumer of the rule vocabulary is updated in this PR: `CHECK_FOR_RULE`, both `validate_deck` docstrings (`src/mcp_server/server.py`, `src/mcp_server/tools/deck_analysis.py`), the format-legality and magic-deckbuilding skills, and the UI comments that state restricted cards land on the legality row. `plugin/` rebuilt and committed.

**Never:** No change to the dead `validate_card_addition` rule beyond what the shared `is_basic_land` fix gives it (5.1 owns it). No per-format deck-size work, no commander-eligibility modelling (Duel's "restricted as commander" stays read as a 1-copy limit, which singleton already enforces). No import-time key check. No test reads or writes the real data directory; the real database was read only with `mode=ro`, to build the fixture.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Snow basics | 60-card Standard-legal deck with 10 Snow-Covered Forest | legal; copy-limit row passes | none |
| Snow Wastes, Wastes | "Basic Snow Land", "Basic Land" (no subtype), 10 each | exempt | none |
| Basic non-land | Omnipresent Impostor ("Basic Creature — Shapeshifter") × 5 | `copy_limit` violation | none |
| Restricted, one copy | Vintage deck, 1 Black Lotus | legal; legality, banned and copy-limit rows pass | none |
| Restricted, two copies | Vintage, 1 main + 1 side Black Lotus | one restricted violation on the copy-limit row: "2 copies of 'Black Lotus'; it is restricted in vintage (max 1 copy)." | none |
| Restricted, five copies | Vintage, 5 Black Lotus | the restricted violation only, no `copy_limit` | none |
| Restricted in a singleton format | competitivebrawl, 2 copies of a card restricted there | `singleton` only | none |
| Unknown format | `potato`, restricted card | `unknown_format`; no restricted check | none |
| Key drift | a fixture key missing from `_KNOWN_FORMATS`, or a stale entry | the pin fails naming the difference | none |

</frozen-after-approval>

## Code Map

- `src/logic/deck_validator.py:41-65` `is_basic_land` -- substring test. Replace with: the part of `type_line` before the first `—` (front face; fall back to the whole line), lowercased and split into words, contains both `basic` and `land`. Update the docstring examples (add snow).
- `src/logic/deck_validator.py:199-230` `_KNOWN_FORMATS` -- comment says it "mirrors the keys present in every card's legalities"; point it at the fixture pin.
- `src/logic/deck_validator.py:233-254` `DeckViolationRule` and its docstring ("`restricted` is deliberately not a member") -- add `restricted_card`, rewrite the paragraph. `DeckViolation.card_name` docstring lists card-specific rules; add it.
- `src/logic/deck_validator.py:294-343` `validate_deck` docstring -- the Copy limit and Format legality bullets; `restricted` now counts as legal for the legality check.
- `src/logic/deck_validator.py:400-454` -- copy-limit loop over `combined_counts`: per card, `restricted = known_format and card.legalities.get(format) == "restricted"`; limit is 1 if singleton or restricted, else 4; rule is `singleton` if singleton, else `restricted_card` if restricted, else `copy_limit`. Legality loop: `legality not in ("legal", "restricted")` for `format_legality`; drop the "known, unmodelled limitation" comment.
- `src/logic/deck_validator.py:502-517` `CHECK_FOR_RULE` -- `"restricted_card": "copy_limit"`. `TestRuleCoverage` forces this.
- `src/logic/deck_validator.py:691-699` -- copy_limit pass sentence "No card exceeds the copy limit; basic lands are exempt." stays true; leave it (UI fixtures quote it).
- `src/mcp_server/tools/deck_analysis.py:278-292`, `src/mcp_server/server.py:912-925` -- `validate_deck` docstrings (LLM-facing): replace the "restricted ... reported as format_legality" clause with the 1-copy rule and token; mention snow basics are exempt.
- `.claude/skills/format-legality/SKILL.md:108-113,141-150,242-250,316-321` -- rule table (copy_limit's `"basic land" in type_line` text, `format_legality` "and restricted"), the "still collapses restricted" bullet (restricted counts measured 2026-11-10: vintage 52, duel 27, competitivebrawl 12, tlr 12, timeless 4 of 107), the "false positive" playbook line, the vocabulary list (card_name for six rules), and the basics line. `.claude/skills/magic-deckbuilding/SKILL.md:77-81` -- add restricted to the violation list.
- `ui/src/containers/FormatCheck/copy.ts:70-79`, `ui/src/containers/FormatCheck/FormatCheck.test.tsx:115-121` -- comments that say a restricted card reports on the legality row and cite the removed test name. Rewrite: an over-limit restricted card lands on the copy-limit row, so "Banned or restricted" stays false. Comments only; no behaviour change.
- `tests/fixtures/scryfall_legalities.json` (new) -- the real `legalities` of Black Lotus and Snow-Covered Forest, read `mode=ro` from `cards.db` on 2026-11-10 (all 39,503 cards share one 23-key set, equal to `_KNOWN_FORMATS`), wrapped as minimal raw Scryfall objects; a sibling note says how to refresh it.
- `tests/unit/logic/test_format_check.py:347-363,668-674` -- replace `test_a_restricted_card_is_still_a_plain_legality_violation`; replace `len == 23` with equality against the fixture keys after `transform_scryfall_card` (`src/data/importers/transformers.py:177`). Module docstring paragraph on restricted.
- `tests/unit/logic/test_deck_validator.py:107-183,660-670` -- `TestIsBasicLand` rows (snow, Snow-Covered Wastes, Wastes, Omnipresent Impostor); restricted rows.
- `tests/integration/mcp_server/test_deck_analysis_tool.py` (not integration-marked; runs in CI and the harness) -- `_seed_cards`/`_make_deck` pattern: the verify-line cases through the tool helper.
- `tests/unit/companion/test_routes_format_check.py` -- `_legal_card`/`_basic`/`_deck_seeder`: the verify-line cases through the route, asserting row statuses.

## Tasks & Acceptance

**Execution:**
- [x] `tests/fixtures/scryfall_legalities.json`, `tests/unit/logic/test_format_check.py` -- fixture and the key-equality pin (tests first; passes on baseline, proved red by planting a 24th fixture key and by dropping one from `_KNOWN_FORMATS`).
- [x] `tests/unit/logic/test_deck_validator.py`, `tests/unit/logic/test_format_check.py`, `tests/integration/mcp_server/test_deck_analysis_tool.py`, `tests/unit/companion/test_routes_format_check.py` -- matrix tests, seen red on the baseline.
- [x] `src/logic/deck_validator.py` -- basic-land fix, restricted rule, token, docstrings.
- [x] `src/mcp_server/tools/deck_analysis.py`, `src/mcp_server/server.py` -- docstrings.
- [x] `.claude/skills/format-legality/SKILL.md`, `.claude/skills/magic-deckbuilding/SKILL.md` -- vocabulary and playbook.
- [x] `ui/src/containers/FormatCheck/copy.ts`, `FormatCheck.test.tsx` -- comments; full UI gate.
- [x] `plugin/` -- `uv run python -m scripts.build_plugin`, commit.

**Acceptance Criteria:**
- Given the verify line's three decks, when checked through `validate_deck` and the format-check route, then ten Snow-Covered Forests are legal, one Black Lotus in Vintage is legal, and two are one violation on the copy-limit row.
- Given the gate, when it runs, then Python and UI gates are green and each new guard is proved red through the probe harness with its fix reverted.

## Implementation Notes

- **Fixture.** `tests/fixtures/scryfall_legalities.json` is `{"_note": ..., "cards": [...]}`: the sibling `_note` key holds the refresh instructions, `cards` holds Black Lotus and Snow-Covered Forest as minimal raw Scryfall objects (`id`, `oracle_id`, `name`, `type_line`, `set`, `collector_number`, `legalities`). Read with `mode=ro` from `%LOCALAPPDATA%/artificial-planeswalker/cards.db` on 2026-11-10: 39,503 cards, one 23-key set across all of them, equal to `_KNOWN_FORMATS`; restricted entries vintage 52, duel 27, competitivebrawl 12, tlr 12, timeless 4 (107).
- **Pin.** `test_format_check.py::TestKnownFormatsMatchScryfall` runs each fixture card through `transform_scryfall_card` and asserts key-set equality with `_KNOWN_FORMATS`, naming the missing and stale keys in the message; `test_the_fixture_is_not_vacuous` pins the two names and non-empty dicts. The old `len(_KNOWN_FORMATS) == 23` line became `len(_KNOWN_FORMATS) > len(_SINGLETON_FORMATS)` (non-vacuity only); the equality lives in the new class.
- **Synthetic legalities in the matrix tests.** The real Snow-Covered Forest is `standard: not_legal` today, so the "Standard-legal deck with 10 Snow-Covered Forest" rows use a synthetic `{"standard": "legal", "vintage": "legal"}` dict on the real type line; the Black Lotus rows use `{"vintage": "restricted", "legacy": "banned", ...}`.
- **`is_basic_land`.** `type_line.split("—", 1)[0].lower().split()` must contain `basic` and `land`. A `//` double-faced line is not split on `//` (the plan reads the part before the first dash only); no real card has a basic-land back face, so no test pins that case.
- **Scenario rows that pass on baseline.** The unknown-format row (`potato`) and the Omnipresent Impostor rows pass before and after the fix; they lock behaviour rather than guard the change. The `known_format and` clause in the restricted test is not separately probed: `legalities.get("potato")` is `None` for every real card, so dropping the clause changes no verdict.
- **Not touched.** `format-legality/SKILL.md`'s format table line "Restricted (Vintage only)" and its "checks exactly six rules" sentence were outside the listed line ranges and are left as they were.

### Probe-harness proofs (2026-11-10, tree staged before each plant, restore checked with `git diff --exit-code`)

1. `is_basic_land` reverted to `"basic land" in card.type_line.lower()`: `full suite (-m 'not integration'): 3375 collected, 10 failed, 0 errored, exit 1` -- red: `TestIsBasicLand::test_every_basic_land_spelling_is_basic[snow-basic]`, `[snow-basic-without-subtype]`, `test_basic_and_land_must_both_be_supertypes[basic-land-only-after-the-dash]`, `TestValidateDeck::test_ten_snow_basics_are_copy_limit_exempt`, `test_deck_analysis_tool.py::test_validate_deck_ten_snow_basics_are_legal` (+ the two restricted tool tests, whose filler is snow basics), `TestSnowBasicsAndRestrictedCards::test_ten_snow_basics_pass_the_copy_limit` (+ the two Lotus route tests, same reason).
2. Legality arm reverted (`elif legality != "legal":`): `full suite (-m 'not integration'): 3375 collected, 10 failed, 0 errored, exit 1` -- red: all five `TestValidateDeckRestricted` rows except unknown-format and legacy, both `TestRestrictedCard` row tests, both Lotus tool tests, both Lotus route tests.
3. Copy-limit arm reverted (`restricted = False`): `full suite (-m 'not integration'): 3375 collected, 5 failed, 0 errored, exit 1` -- red: `test_two_copies_across_boards_are_one_restricted_violation`, `test_five_copies_report_the_restricted_rule_only`, `TestRestrictedCard::test_a_second_copy_in_the_sideboard_is_one_copy_limit_violation`, `test_validate_deck_two_restricted_copies_are_one_violation`, `test_two_black_lotus_are_one_violation_on_the_copy_limit_row`.
4. 24th key (`brandnewformat`) planted in the fixture's Black Lotus: `full suite (-m 'not integration'): 3375 collected, 1 failed, 0 errored, exit 1` -- red: `TestKnownFormatsMatchScryfall::test_known_formats_equal_the_scryfall_keys[Black Lotus]`.
5. `premodern` dropped from `_KNOWN_FORMATS`: `full suite (-m 'not integration'): 3375 collected, 2 failed, 0 errored, exit 1` -- red: `test_known_formats_equal_the_scryfall_keys[Black Lotus]` and `[Snow-Covered Forest]`.

The pin passed on the baseline before any `src/` change; every other new matrix test was seen red on the baseline (11 in the logic suites, 6 in the tool and route suites).

### Gate (2026-11-10)

- `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src/`, `uv run mypy src/ --platform win32`: clean. `uv run pytest`: 3400 passed, 2 skipped.
- `ui/` (after `npm ci` in this worktree): `lint`, `format:check`, `typecheck` clean; `npm test` 1786 passed; `test:gates` 39 passed; `build` and `gen:types` left no diff under `src/companion/app/static/` or `ui/src/api/`.
- `uv run python -m scripts.build_plugin`: `plugin/server/src/...` (validator, both docstrings) and `plugin/skills/{format-legality,magic-deckbuilding}` regenerated and committed.

## Plan Change Log

## Review Triage Log

## Verification

**Commands:**
- `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src/`, `uv run mypy src/ --platform win32`, `uv run pytest` -- clean / green
- `uv run python -m scripts.probe_harness --expect-red '<node>'` per planted revert -- expected nodes red
- from `ui/`: `npm run lint`, `npm run format:check`, `npm run typecheck`, `npm test`, `npm run test:gates`, `npm run build`, `npm run gen:types` -- clean, no diff
- `uv run python -m scripts.build_plugin` then `git status --porcelain plugin/` -- rebuilt tree committed
