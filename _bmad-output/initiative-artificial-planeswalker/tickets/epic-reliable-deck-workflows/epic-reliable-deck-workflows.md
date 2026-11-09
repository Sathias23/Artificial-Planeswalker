---
type: epic
title: "Reliable deck workflows: whole-deck lookup, clear imports, verified Arena exports"
parent: initiative-artificial-planeswalker
covers: [R7, R8, R9, R10, R11, R12, R13, R17, R18, R19, R20, R21, R22]
sources:
  - _bmad-output/initiative-artificial-planeswalker/archive-v6/spec-deck-workflow-reliability/SPEC.md
  - _bmad-output/initiative-artificial-planeswalker/archive-v6/epics-deck-workflow-reliability.md
companions:
  - _bmad-output/initiative-artificial-planeswalker/tickets/epic-reliable-deck-workflows/acceptance.md
after: []
refined: false
risk: high
---

# Reliable deck workflows: whole-deck lookup, clear imports, verified Arena exports

## Description

An Arena Brawl deckbuilding session exposed stalled lookup batches and avoidable import and export failures. This epic lets users resolve a whole deck without database workarounds, understand and recover from incomplete lookups, and move supported decks into Arena without manual name repairs or silent card substitutions (spec CAP-1 and CAP-2). The five entries below are the v6 review drafts, not yet approved.

## Outcome

A deckbuilder resolves, imports and exports a representative 100-card Arena deck without manual database access or name repairs; the measure is the spec's Success signal and the cases in `acceptance.md`.

## Requirements

1. R1 (parent R7): Resolve an entire deck in one bulk request, accepting names and optional printing qualifiers with existing format/platform filters.
2. R2 (parent R8): Preserve input order, original text, indices and duplicate inputs; return one attributable found, ambiguous-with-candidates, missing, failed or explicitly unfinished result per input, plus batch completeness.
3. R3 (parent R9): Return actionable outcomes for oversized requests and expired deadlines, cancel unfinished work, release resources and permit successful subsequent requests.
4. R4 (parent R10): Use consistent card resolution in bulk lookup and import; resolve unambiguous front-face names to playable identities, exclude art cards from ordinary playable resolution, and explicitly report qualifier mismatch or fallback.
5. R5 (parent R11): Import name-only and printing-qualified lists while preserving additive behaviour, reporting each rejected line, imported totals and partial success, and documenting retry behaviour.
6. R6 (parent R12): Export verified Arena-compatible names and printing identifiers where used; substitute only verified printings of the same playable identity and explicitly report unexportable cards without silent omission.
7. R7 (parent R13): Preserve playable identities, quantities and supported Commander/Deck/Sideboard/Companion sections across import/export round trips, including split and double-faced cards.
8. R8 (parent R17): Bound lookup work, concurrency and response size; determine and document batch limits and item/batch deadlines from measurements rather than inventing thresholds.
9. R9 (parent R18): Measure orchestration separately from server/database execution for individual, 3-, 15-, approximately 90- and representative 100-card workloads; do not attribute stalls without evidence.
10. R10 (parent R19): Verify cancellation, resource cleanup and recovery through injected queued/running stalls and subsequent requests.
11. R11 (parent R20): Keep lookup, export and analysis observational and MCP calls stateless; require explicit deck-management intent for mutations and keep the companion read-only.
12. R12 (parent R21): Verify behaviour through real entry points, including mixed lookup outcomes, filters, qualifiers and duplicates; parser-only round trips do not establish Arena compatibility.
13. R13 (parent R22): Do not treat platform availability aggregated across printings as proof that a stored printing is Arena-compatible.

## Constraints

- Lookup and analysis remain observational, stateless MCP operations over stdio; only explicitly requested deck-management operations may mutate decks, and the companion remains read-only.
- Measure orchestration and server/database delays separately before attributing stalls or choosing concurrency limits; fewer calls alone do not establish reliability.
- Bulk lookup and import share resolution semantics, including explicit ambiguity and qualifier fallback reporting.
- Preserve the data, then logic, then MCP import direction and framework-free data/logic layers; reuse existing repositories and Pydantic tool contracts.
- Update affected shipped skills and regenerate `plugin/` for tool changes; never hand-edit generated files.
- Any schema extension needs a migration preserving existing deck and card references; decide the printing-data source before implementing printing interoperability.
- Resolve the strict-rejection versus explicit-fallback qualifier policy before implementation; never silently guess an identity.

## Done when

- The representative 100-card Arena Brawl deck resolves in one request, imports and exports without manual database access or name repairs.
- The mixed-failure and injected-stall cases in `acceptance.md` pass without disappearing inputs or lingering resource exhaustion.
- Measured batch, concurrency and deadline limits are documented with the measurements behind them.
- Arena acceptance, not only this project's parser, is evidenced for split and double-faced fixtures including The Emperor of Palamecia (FIN 219) and the identity associated with Commit.
- The changes ship in a tagged release with the skills, `plugin/` and generated API artifacts in step.

## Boundaries

- Not here: calibrated Brawl scoring, complete Brawl legality validation, atomic deck replacement or swaps, broad synergy-detector expansion, companion launch diagnostics.
- Belongs to a sibling: honest assessment output (epic-trustworthy-assessment). This epic needs nothing from it, and it needs nothing from this one.
- Must not change: additive import behaviour; the frozen viewer.

## References

- parent — `_bmad-output/initiative-artificial-planeswalker/initiative-artificial-planeswalker.md`, Requirements R7–R13 and R17–R22
- acceptance — `acceptance.md` beside this file, the spec's acceptance cases
- spec — `_bmad-output/initiative-artificial-planeswalker/archive-v6/spec-deck-workflow-reliability/SPEC.md`
- breakdown — `_bmad-output/initiative-artificial-planeswalker/archive-v6/epics-deck-workflow-reliability.md`, Epic 1 and its draft stories
- architecture — `docs/architecture.md`

## Notes

- Open question: which batch-size limit, concurrency bound and deadlines meet measured performance needs? (entry 3)
- Open question: which printing-data source will verify Arena printings, and should mismatched qualifiers fail strictly or permit an explicitly reported fallback? (entry 2)
- Assumption: the review's consolidated three changes supersede the source document's conflicting shortlists.
- Assumption: existing additive import behaviour remains, with partial success clearly reported.
- Source conflict: R7 preserves a Companion section across round trips; epic-quick-wins R4 never emits one on export. Settle before entry 5 or epic-quick-wins entry 3 is built.
- Handoff: quality-pass story 5.6 (epic-quality-mcp-tools, was 16) folds the three existing card-name resolvers into one indexed, bounded resolver, and story 5.9 (was 71) sums mixed-printing Arena lines in `import_decklist`; entries 1 and 4 build on the same code.
- Decision: 2026-11-09, board review, Brad: story 5.6 (was 16) lands before entry 1 and story 5.9 (was 71) before entry 4 (`after` keys `5.6` and `5.9`).
- Assumption: the five entries are v6 review drafts ("epic-1-stories-draft-awaiting-review"); refine with Sofia before building. Done when was written by the migration; confirm with Sofia.
