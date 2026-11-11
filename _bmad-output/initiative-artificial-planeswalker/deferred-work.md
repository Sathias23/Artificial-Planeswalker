# Deferred Work

Real findings that were not worth doing when they were raised. `bmad-build` and `bmad-code-review` append entries here (`{initiative_folder}/deferred-work.md`). The v6 ledger, `implementation-artifacts/deferred-work.md`, stays on the orphan `process` branch.

## Deferred from: codebase review consolidation of review-codebase-2026-11 (2026-11-09)

Ids are those stamped in `review-codebase-2026-11/review-codebase-2026-11.md` (step 4, `## Summary` → Deferred).

- source_plan: `_bmad-output/initiative-artificial-planeswalker/review-codebase-2026-11/review-codebase-2026-11.md`
  summary: "`M15` (`B2-D3`, `R-F10`): `search_advanced` re-evaluates its filter set in the unique-oracle CTE, the outer query and the count, over unindexable `%…%` LIKEs and an unindexed `GROUP BY oracle_id`, and no `deck_cards` index starts with the foreign-key child column `card_id`. Any rewrite or index waits for a measured case."
  evidence: 'B2 code review and research F10, 2026-11-07/08, `src/data/repositories/card.py:115-124`, `:577`; `src/data/models/card.py`, `src/data/models/deck_card.py`. Settled by `EXPLAIN QUERY PLAN` plus timings on the real `cards.db` for `search_advanced(unique_oracle=True)`, `find_by_name_partial` and a `deck_cards` delete by `card_id` (research §Open questions).'

- source_plan: `_bmad-output/initiative-artificial-planeswalker/review-codebase-2026-11/review-codebase-2026-11.md`
  summary: "`T1-2-D1`: the assessment client tests in `tests/integration/test_mcp_tools.py:984-2016` repeat checks the helper suites already pin (shape parity, byte determinism, sorted lists, delta-equals-subtraction, the four degradation paths). Kept for now: once the data-dir isolation fix (`M47`) lands each costs about 0.2 s, and the wire-text and edit-driven checks have no helper twin. Revisit option (b), moving the structured `confidence` assertions into the helper twins, when the assessment contract next changes."
  evidence: 'T1-2 code review, 2026-11-09; T1-0 durations (the top 30 Python tests, about 146 s, are almost all in this file).'

- source_plan: `_bmad-output/initiative-artificial-planeswalker/review-codebase-2026-11/review-codebase-2026-11.md`
  summary: "`B4-D3` option (b): let Kindred non-creature spells count as tribe members in synergy detection. It changes what \"tribal density\" means, so it is Brad's call the next time synergy detection is extended. The narrow parsing fixes, option (a), are in the fix list (Q15)."
  evidence: 'B4 code review, 2026-11-08, `src/logic/synergy.py:135`, `:150-154`, `:569-573`.'

- source_plan: `_bmad-output/initiative-artificial-planeswalker/review-codebase-2026-11/review-codebase-2026-11.md`
  summary: "`B5-D5` option (b): replace the provisional Commander pip anchors (23/30/33, a linear scale of the 60-card values) with Karsten's published Commander tables. It waits for a benchmark case, since `mana_efficiency` weighs 0.05 in Commander. The comment fix and fetchland source counting, option (a), are in the fix list (Q17)."
  evidence: 'B5 code review, 2026-11-08, `src/logic/assessment/mana_base.py:266`, `:330-338`; `src/logic/assessment/profiles.py:143-144`.'

- source_plan: `_bmad-output/initiative-artificial-planeswalker/review-codebase-2026-11/review-codebase-2026-11.md`
  summary: "`B5-D3` option (b): also drop Spellbook superset variants from the `combos` list that `assess_deck_power` returns. That is a tool-output change and a separate call. Skipping them in scoring, option (a), is in the fix list (Q17)."
  evidence: 'B5 code review, 2026-11-08, `src/logic/assessment/combos.py:181-198`; `src/logic/assessment/dimensions.py:594-621` (205 two-card pairs have supersets, up to 237 for one pair).'

- source_plan: `_bmad-output/initiative-artificial-planeswalker/review-codebase-2026-11/review-codebase-2026-11.md`
  summary: "A colour-identity search filter (follows decision D2, 2026-11-09): `search_cards`' `at_most` and the semantic tools filter card colours, so a Commander search returns off-identity cards (Golgari Signet under mono-white) unless the agent checks identity itself. D2 kept the colour semantics and corrects the docstrings and skills. An identity filter is a new tool parameter, and on the semantic path it also needs new vec0 metadata columns and a `--rebuild`."
  evidence: 'B2 code review (`B2-D1`), 2026-11-08, `src/data/repositories/card.py:435`, `:463`, `:517-524`; `src/search/index_builder.py:372-375` stores `cards.colors`, deliberately not `color_identity`.'

## Deferred from: board review of epic-codebase-quality-pass (2026-11-09)

Fix findings Brad dropped at the board review; ids are those stamped in `review-codebase-2026-11/review-codebase-2026-11.md`. The ruling and its reason are in the epic's Notes (`tickets/epic-codebase-quality-pass/epic-codebase-quality-pass.md`).

- source_plan: `_bmad-output/initiative-artificial-planeswalker/review-codebase-2026-11/review-codebase-2026-11.md`
  summary: "Story 33 (`B4-P10`, `B4-P13`, `B4-P16`, `B4-P18`), mana-curve polish: assert the land recommendations as exact strings rather than substrings; name the repeated curve thresholds (35/45/40/3.5/0.25 and the early-play count) once; stop a deck under three cards being told \"Add ~0 lands (target: 0 lands)\"; split lands from spells in one pass instead of a pairwise Pydantic comparison, dropping the dead `cmc is None` arms. Dropped because the only visible effect is the tiny-deck message and story 36 rewrites land detection in the same file; revisit if `mana_curve.py` is touched for its own sake."
  evidence: 'B4 code review, 2026-11-08, `src/logic/mana_curve.py:74-88`, `:146-234`, `:203-206`; `tests/unit/logic/test_mana_curve.py:125`, `:136`.'

- source_plan: `_bmad-output/initiative-artificial-planeswalker/review-codebase-2026-11/review-codebase-2026-11.md`
  summary: "`B6-D3` option (a): fold `MODEL_NAME` and `EMBEDDING_DIM` into the index's content hash, so a model swap that keeps 384 dimensions re-embeds every card instead of ranking new query vectors against old card vectors. Deferred because it forces one full re-embed on every user's machine to guard a swap nobody has planned; add it in the PR that changes the embedding model."
  evidence: 'B6 code review, 2026-11-08, `src/search/index_builder.py:225-244`, `src/search/embedder.py:39-40`.'

## Deferred from: story 4.2 (Python tests are hermetic), 2026-11-10

- source_plan: `_bmad-output/initiative-artificial-planeswalker/tickets/epic-codebase-quality-pass/tickets/story-python-tests-are-hermetic-and-share-one-fixture-set-plan.md`
  summary: "With the per-test data dir removed (every test sharing one data dir, so one `image_cache`), the suite spins at 100% CPU after `tests/unit/companion/test_routes_card_image.py::TestARepeatRequestMakesNoCdnRequest::test_the_second_request_is_served_from_a_file_that_actually_exists` and never finishes, instead of failing. The root `isolated_data_dir` fixture prevents the state today, but an isolation regression would hang CI rather than go red (no pytest-timeout, no job timeout until story 4.4)."
  evidence: "Observed during story 4.2's isolation probe (literal fixture deletion, `PLANESWALKER_DATA_DIR` pointed at one scratch dir): 30+ min at 100% CPU, killed. Pre-existing code; medium, the spinning loop not yet located. Settle by running that class with a pre-populated shared `image_cache` and finding the loop."

## Deferred from: story 4.4 (CI runs the recall eval, the Windows halves and bounded jobs), 2026-11-10

- source_plan: `_bmad-output/initiative-artificial-planeswalker/tickets/epic-codebase-quality-pass/tickets/story-ci-runs-the-recall-eval-the-windows-halves-and-bounded-jobs-plan.md`
  summary: "The pre-commit `mypy` hook (`files: ^src/`, filenames passed) skips a commit that only deletes a `src/` module, the same `--diff-filter=ACMRTUXB` gap T2-P8 fixed for `build-plugin-sync`, so a deletion that breaks an import elsewhere passes locally and fails CI's mypy step. For story 4.65, whose D10 rewrite makes it a `pass_filenames: false` `uv run mypy src/` hook: give it `always_run: true` too."
  evidence: "Found grepping the T2-P8 pattern across `.pre-commit-config.yaml` in story 4.4. Costs a CI round, not a bad merge (CI runs mypy on both platforms). Left to 4.65 because that story replaces the hook; ruff, ruff-format, no-local-machine-paths and ui-prettier-check cannot fail on a deletion."

## Deferred from: story 7.6 (Assessment dimensions are pinned before they change), 2026-11-12

- source_plan: `_bmad-output/initiative-artificial-planeswalker/tickets/epic-quality-analysis/tickets/story-assessment-dimensions-are-pinned-before-they-change-plan.md`
  summary: "`dimension_vector`'s docstring (`src/logic/assessment/dimensions.py`) still says the curves' tests \"verify shape, clamps, and the monotone directions only\"; since 7.6 the suite pins exact `mana_efficiency`, `resilience`, `card_advantage` and `combo_potential` values. Fix the sentence with the next story that edits `dimensions.py` (7.5 or 7.8), rebuilding `plugin/` in that PR."
  evidence: "Found by 7.6's quick review lens; verified against the docstring at baseline `fb82633`. 7.6 is tests-only by intent (no `src/` or docstring change), so the stale sentence could not be corrected there. Low: it misleads a contributor about which pins exist, it does not change behaviour."
