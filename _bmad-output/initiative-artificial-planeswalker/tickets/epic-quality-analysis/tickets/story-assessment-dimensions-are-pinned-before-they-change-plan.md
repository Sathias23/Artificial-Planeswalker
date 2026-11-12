---
title: 'Assessment dimensions are pinned before they change'
type: 'chore'
ticket: '6'
created: '2026-11-12'
status: 'review'
baseline_revision: 'fb82633053eacd091e47996b6e5c7c3ad1d01d35'
route: 'full'
route_source: 'auto'
risk: 'low'
review: 'quick'
review_source: 'pinned'
lenses_ran: ['quick']
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Six assessment rules can move without a test noticing: `mana_efficiency`, `resilience` and `card_advantage` are only range-checked (B5-P8); speed's average-mana-value term has no direction test (B5-P9); `almost_included` half credit is unpinned (B5-P10); multi-face land source counting is untested (B5-P11); `structural_gaps_added` / `_removed` are never asserted on a real difference (B9-P13); and the wire-byte determinism tests compare two calls in one interpreter, so hash-seed ordering cannot fail them (T1-2-P6). The accuracy fixes that follow (7.5 next) would land unguarded.

**Approach:** Tests only. Pin today's behaviour, each to a value or a strict direction, through the analysis functions and the MCP tools, and prove every new test goes red when its rule is inverted, through the committed probe harness.

## Boundaries & Constraints

**Always:** Drive tests through real entry points (`dimension_vector`, `compute_pip_signals`, `compare_deck_power`, the MCP client); fixture databases are `tmp_path` files built through `create_engine` + `init_database` (the real schema and connect hook), never the real data directory. New DB-backed tests stay unmarked like their neighbours in `tests/integration/mcp_server/`, so they run in CI's `quality` job (`-m "not integration"`); the `integration` mark is for the real card DB, network and model. Pin what the code does today; a value that looks wrong is pinned as-is and recorded under Implementation Notes "For 7.5". Stage the tree before planting a probe; revert each plant and check it with `git diff --exit-code <file>`.

**Never:** No change under `src/`, no docstring, skill or `plugin/` change. No range assertions for the new pins. No source-text scanning. No edits to the existing in-process determinism tests.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Range-only value pins | fixed decks under both profiles | exact `mana_efficiency`, `resilience`, `card_advantage` values (Design Notes) | none |
| Speed avgMV | ten cmc-4 fillers swapped for ten cmc-1, no combo, deck size fixed | speed strictly rises, both values inside (0, 100) | none |
| Half credit | one two-card infinite record, pieces cmc 1 | `almost_included` alone = 25, `included` = 66 | none |
| Multi-face land | `Land // Land`, top-level `oracle_text=""`, faces `{T}: Add {W}.` / `{T}: Add {U}.`; and one face `oracle_text=None` | W and U each count the land's quantity; the `None` face reads as empty, no raise | none |
| Gap direction | deck A draw-rich and no interaction, deck B interaction-rich and no draw | `structural_gaps_added == ("card_draw_below_baseline",)`, `_removed == ("interaction_below_baseline",)`, both equal the set differences of two direct assessments | none |
| Hash-seed determinism | two child processes, `PYTHONHASHSEED` 1 and 2, same fixture DB, 8 confirmed Game Changers | byte-identical `assess_deck_power` and `compare_deck_power` wire text | child non-zero exit fails the test with its stderr |

</frozen-after-approval>

## Code Map

- `src/logic/assessment/dimensions.py` -- read only. `_speed_score:469` (`average_mana_value - _SPEED_AVG_MV_PIVOT`), `_resilience_score:527`, `_mana_efficiency_score:568` (`abs(land_delta)`, `_PIP_DEFICIT_PENALTY`), `_card_advantage_score:580` (tutor bonus), `_combo_potential_score:595` (`else: credit / 2.0`), `game_changer_signal:268` (`tuple(sorted(names))` over a `set`), `dimension_vector:625` (the `_resilience_score(...)` call). Speed is profile-independent for these decks (same score under both).
- `src/logic/assessment/mana_base.py:318` -- `_source_text` face fallback (`face.oracle_text or ""`).
- `src/mcp_server/tools/compare_deck_power.py:259-260` -- the two gap set differences.
- `tests/unit/logic/test_assessment_dimensions.py` -- local builders `_vanilla`, `_land` (colourless), `_draw`, `_tutor`, `_interaction(type_line=)`, `_wincon`, `_filler_rows`, `_piece_rows`; `profile` fixture parametrised over both profiles; `TestMonotoneDirections:567`. Module docstring says exact pins are reserved for derived facts: amend it to name the 7.6 value pins.
- `tests/unit/logic/test_assessment_mana_base.py` -- `TestColoredSources:395`, `by_color`, `forest()`; `make_card(card_faces=[{...}])` takes face dicts.
- `tests/integration/mcp_server/test_compare_deck_power_tool.py` -- `session` fixture (tmp file DB, `assessment_core_cards("card-")`), `_BASE_ROWS`, `make_deck`, `assessment_card` (in `tests/fixtures/assessment_db.py`) to seed the draw and interaction cards in the test.
- `tests/integration/test_mcp_tools.py:1195`, `:1795` -- the in-process byte-determinism tests and the wire surface (`result.content[0].text`); left unchanged.
- `tests/unit/test_script_imports.py:41` -- the repo's `subprocess.run([sys.executable, ...], cwd=_REPO_ROOT, ...)` pattern. The autouse `isolated_data_dir` sets `PLANESWALKER_DATA_DIR` in `os.environ`, so a child inherits the hermetic data dir.

## Tasks & Acceptance

**Execution:**
- [x] `tests/unit/logic/test_assessment_dimensions.py` -- add `TestRangeOnlyDimensionPins` (mana_efficiency four cases, resilience and card_advantage per profile, values in Design Notes), the speed avgMV swap test in `TestMonotoneDirections`, and the half-credit value test; amend the module docstring.
- [x] `tests/unit/logic/test_assessment_mana_base.py` -- two multi-face land source tests in `TestColoredSources`.
- [x] `tests/integration/mcp_server/test_compare_deck_power_tool.py` -- the gap-direction test.
- [x] `tests/fixtures/assessment_wire_dump.py` (new) -- child entry `python -m tests.fixtures.assessment_wire_dump <db_path> <deck_id_a> <deck_id_b>`: opens the DB through `create_engine`, runs `assess_deck_power` (deck B) and `compare_deck_power` (A, B) through `build_server` + `create_connected_server_and_client_session`, writes each call's `content[0].text` to stdout.
- [x] `tests/integration/mcp_server/test_assessment_wire_determinism.py` (new) -- builds the fixture DB and both decks in the parent, disposes the engine, runs the child under `PYTHONHASHSEED=1` and `=2`, asserts both exit 0, status `ok`, eight Game Changers in the assess payload, and equal stdout bytes.
- [x] Probe proofs -- one plant per rule (Design Notes), each through `uv run python -m scripts.probe_harness --expect-red '<node id>'`, proof line and exit code recorded in Implementation Notes.

**Acceptance Criteria:**
- Given each plant in Design Notes applied alone, when the probe harness runs, then the named new test is red and the run exits as the harness reports; after the revert `git diff --exit-code` on the planted file is clean.
- Given the finished branch, when the full Python gate runs, then it is green and `git diff --stat fb82633 -- src/ plugin/` is empty.

## Design Notes

Today's values (prototyped at baseline; re-confirm before pinning). Mana deck = `n` colourless 2-drop fillers + one `{G}` cmc-1 creature + `f` Forests + `b` colourless lands:

| Case | profile | f, b, n | delta, pip deficit | mana_efficiency |
|------|---------|---------|--------------------|-----------------|
| screw | commander | 20, 13, 60 | −4.63, 3 | 75 |
| screw | standard | 12, 6, 30 | −5.33, 2 | 74 |
| flood | commander | 24, 18, 60 | +4.37, 0 | 86 |
| flood | standard | 20, 15, 60 | +11.64, 0 | 42 |

Resilience / card-advantage deck: 1 wincon, 1 instant + 2 sorcery interaction, 3 draw, 2 tutors, 10 vanilla, 10 colourless lands → resilience 38 (commander) / 46 (standard), card_advantage 30 / 46. Speed: 10 cmc-4 + 10 cmc-2 fillers + 15 lands → 50; cmc-4s swapped for cmc-1 → 71.

Plants (one rule inverted each): pip penalty dropped; `abs(land_delta)` → `land_delta` (flood-only penalty, the screw cases go red); `abs(land_delta)` → `-land_delta` (screw-only penalty, the flood cases go red); resilience call passes `counts[CARD_DRAW].count` and `win_route_count` swapped; tutor bonus dropped from card_advantage; speed avgMV sign flipped; half-credit `else` branch deleted; `_source_text` → `card.oracle_text.lower()`; `or ""` dropped from the face join; compare's two gap differences swapped; `sorted` dropped in `game_changer_signal` (and, second plant, in compare's `game_changers_added`).

## Verification

**Commands:**
- `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src/`, `uv run mypy src/ --platform win32`, `uv run pytest` -- all green
- `uv run python -m scripts.probe_harness --expect-red '<node id>'` per plant -- proof lines in Implementation Notes
- `git diff --stat fb82633 -- src/ plugin/` -- empty

## Implementation Notes

Commit `476a63a` on `test/quality-7-6-pin-assessment-dimensions` (tests only; `git diff --stat fb82633 -- src/ plugin/` empty). All Design Notes values re-confirmed at baseline before pinning.

- `test_assessment_dimensions.py`: `TestRangeOnlyDimensionPins` (mana_efficiency screw/flood x commander/standard = 75/74/86/42; resilience 38/46; card_advantage 30/46; `almost_included` 25 vs included 66 under both profiles) and `TestMonotoneDirections::test_lower_average_mana_value_strictly_raises_speed` (50 -> 71, both off the clamps). Module docstring names the 7.6 value pins.
- `test_assessment_mana_base.py`: two `Land // Land` source tests (W and U count the quantity; a `None` face text reads as empty).
- `test_compare_deck_power_tool.py::test_structural_gap_diffs_point_the_right_way`: deck A 8 draw, deck B 8 removal over `_BASE_ROWS`; added `("card_draw_below_baseline",)`, removed `("interaction_below_baseline",)`, both equal to the direct assessments' set differences.
- `tests/fixtures/assessment_wire_dump.py` (child entry) and `test_assessment_wire_determinism.py`: parent builds the tmp DB (core cards + 6 extra Game Changers, one combo variant, decks A and B), disposes the engine, runs the child under `PYTHONHASHSEED=1` and `=2`; asserts exit 0, both statuses `ok`, 8 `flags.game_changers` and 8 `game_changers_added`, equal stdout bytes (~2.6 s). The child concatenates indented JSON documents; the parent splits them with `raw_decode`.
- Marks: every new DB-backed test is unmarked like its neighbours, so it runs in CI's `quality` job (`-m "not integration"`) and in the default `uv run pytest`.

Probe proofs. Tree staged first; each plant applied alone by a driver that restores the original bytes, then `git diff --exit-code <file>`. Each run is `uv run python -m scripts.probe_harness --expect-red '<node id>' ...` (substring match on the parametrised ids):

| # | Plant (file) | Proof line | RED | harness exit | `git diff --exit-code` |
|---|--------------|------------|-----|--------------|------------------------|
| 1 | pip-deficit penalty dropped (`dimensions.py`) | `full suite (-m 'not integration'): 3555 collected, 2 failed, 0 errored, exit 1` | `test_mana_efficiency_value[screw-commander]`, `[screw-standard]` | 0 | 0 |
| 2 | `abs(land_delta)` -> `land_delta` (`dimensions.py`) | `full suite (-m 'not integration'): 3555 collected, 2 failed, 0 errored, exit 1` | `test_mana_efficiency_value[screw-commander]`, `[screw-standard]` | 0 | 0 |
| 3 | `abs(land_delta)` -> `-land_delta` (`dimensions.py`) | `full suite (-m 'not integration'): 3555 collected, 2 failed, 0 errored, exit 1` | `test_mana_efficiency_value[flood-commander]`, `[flood-standard]` | 0 | 0 |
| 4 | resilience call: draw count and win-route count swapped (`dimensions.py`) | `full suite (-m 'not integration'): 3555 collected, 2 failed, 0 errored, exit 1` | `test_resilience_value[COMMANDER_PROFILE-38]`, `[STANDARD_PROFILE-46]` | 0 | 0 |
| 5 | tutor bonus dropped from card_advantage (`dimensions.py`) | `full suite (-m 'not integration'): 3555 collected, 2 failed, 0 errored, exit 1` | `test_card_advantage_value[COMMANDER_PROFILE-30]`, `[STANDARD_PROFILE-46]` | 0 | 0 |
| 6 | speed avgMV sign flipped (`dimensions.py`) | `full suite (-m 'not integration'): 3555 collected, 2 failed, 0 errored, exit 1` | `test_lower_average_mana_value_strictly_raises_speed[COMMANDER_PROFILE]`, `[STANDARD_PROFILE]` | 0 | 0 |
| 7 | half-credit `else` branch deleted (`dimensions.py`) | `full suite (-m 'not integration'): 3555 collected, 2 failed, 0 errored, exit 1` | `test_almost_included_earns_half_credit[COMMANDER_PROFILE]`, `[STANDARD_PROFILE]` | 0 | 0 |
| 8 | `_source_text` -> `card.oracle_text.lower()` (`mana_base.py`) | `full suite (-m 'not integration'): 3555 collected, 2 failed, 0 errored, exit 1` | `test_multi_face_land_reads_each_face_for_sources`, `test_multi_face_land_with_a_null_face_text_reads_it_as_empty` | 0 | 0 |
| 9 | `or ""` dropped from the face join (`mana_base.py`) | `full suite (-m 'not integration'): 3555 collected, 2 failed, 0 errored, exit 1` | `test_multi_face_land_with_a_null_face_text_reads_it_as_empty` (plus existing `TestPipDemand::test_land_mdfc_is_excluded_from_pip_demand`) | 0 | 0 |
| 10 | compare's two gap differences swapped (`compare_deck_power.py`) | `full suite (-m 'not integration'): 3555 collected, 1 failed, 0 errored, exit 1` | `test_structural_gap_diffs_point_the_right_way` | 0 | 0 |
| 11 | `sorted` dropped in `game_changer_signal` (`dimensions.py`) | `full suite (-m 'not integration'): 3555 collected, 5 failed, 0 errored, exit 1` | `test_wire_bytes_identical_across_hash_seeds` (plus existing `test_lists_are_emitted_sorted`, `test_assess_deck_power_wire_bytes_deterministic`, `TestDeterminism::test_input_order_irrelevant[x2]`) | 0 | 0 |
| 12 | `sorted` dropped in compare's `game_changers_added` (`compare_deck_power.py`) | `full suite (-m 'not integration'): 3555 collected, 1 failed, 0 errored, exit 1` | `test_wire_bytes_identical_across_hash_seeds` only | 0 | 0 |

The "proof line" `exit 1` is pytest's (tests failed, as planted); "harness exit 0" means every `--expect-red` expectation was met. Plant 12 is the T1-2-P6 gap: no existing test catches it, the new one does.

Gate (finished branch): `ruff check .` and `ruff format --check .` clean; `mypy src/` and `mypy src/ --platform win32` no issues (96 files); `uv run pytest` 3580 passed, 2 skipped, exit 0.

For 7.5 (pinned as-is, not fixed here):
- A single one-pip card sets the Commander source requirement to 23 sources of that colour (`PIP_SOURCE_ANCHORS_COMMANDER[1]`), at 3 points a missing source; in the screw-commander case one `{G}` 1-drop is the whole 9-point pip penalty, and with no green sources it alone would cost 69 points. Provisional scale already documented; worth a look when mana scoring changes (7.8's B5-D5 territory).
- `_source_text` joins every face of a multi-face card, so a `Creature // Land` MDFC whose spell face has a mana ability also counts that face's colours as land sources. Pinned only for `Land // Land`; 7.5 moves land detection and decides the MDFC rule.
- Resilience's instant-speed and draw weights are equal (30/30), so swapping those two terms is invisible to any value pin; the pinned plant swaps win-route and draw counts instead. Not a defect, a blind spot to keep in mind.

## Plan Change Log

## Review Triage Log

Pass 1 (lens `quick`, 2026-11-12): 3 findings — high 0, medium 0, low 3, false 0, maybe-false 0. One **patch**, one **defer**, one rejected; no loopback. The lens found no unmet acceptance criterion, broken rule or bug.

| # | Finding | Verdict | Route | Evidence / action |
|---|---------|---------|-------|-------------------|
| 1 | `dimension_vector`'s docstring (`dimensions.py`) still says tests verify "shape, clamps, and the monotone directions only", now false | low | defer | Verified at baseline. The intent's Never excludes any `src/` or docstring change, so it cannot be fixed here; appended to `deferred-work.md` for the next story editing `dimensions.py` (7.5 or 7.8). |
| 2 | `TestRangeOnlyDimensionPins` class docstring names three dimensions but the class also pins `combo_potential` half credit | low | patch | Verified: `test_almost_included_earns_half_credit` sits in the class and its docstring omits it. Action: name the half-credit pin in the docstring. |
| 3 | The hash-seed test does not check that seeds 1 and 2 iterate the eight names in different orders, so a future CPython hash change could make it vacuous | low | rejected | Real in principle; plants 11 and 12 prove the two seeds differ on today's interpreter. Two SipHash seeds giving the same order for eight strings is about 1 in 40,320, and the fix adds a self-check subprocess pair (a new guard), so per triage rules a low finding unlikely in everyday use with a non-trivial fix is rejected. |

Review patch (docstring only, no new guard): `TestRangeOnlyDimensionPins` now names all four pinned dimensions and the half-credit rule. After the patch: `ruff check .`, `ruff format --check .`, `mypy src/` and `mypy src/ --platform win32` clean; `uv run pytest` 3580 passed, 2 skipped, exit 0; `git diff --stat fb82633 -- src/ plugin/` empty.
