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
