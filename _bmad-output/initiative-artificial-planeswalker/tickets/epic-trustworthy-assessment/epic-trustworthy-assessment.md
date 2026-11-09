---
type: epic
title: "Trustworthy assessment: honest Brawl support and real combo credit"
parent: initiative-artificial-planeswalker
covers: [R14, R15, R16, R20, R21]
sources:
  - _bmad-output/initiative-artificial-planeswalker/archive-v6/spec-deck-workflow-reliability/SPEC.md
  - _bmad-output/initiative-artificial-planeswalker/archive-v6/epics-deck-workflow-reliability.md
companions: []
after: []
refined: false
risk: medium
---

# Trustworthy assessment: honest Brawl support and real combo credit

## Description

Assessing a Brawl deck with a Commander profile produced a misleading score, and incomplete combo variants earned functioning-combo credit. This epic lets users tell unsupported Brawl scoring from a supported assessment and functioning combos from missing-card suggestions, without misleading strength labels (spec CAP-3). The v6 breakdown approved this grouping but wrote no stories for it.

## Outcome

A Brawl player gets an honest account of what the assessor supports and what their combos really do; the measure is the spec's Success signal ("assessed without an unsupported numeric rating").

## Requirements

1. R1 (parent R14): Report Brawl numerical scoring as unsupported without silently substituting a Commander score or strength label.
2. R2 (parent R15): Separate complete combos from missing-card suggestions; incomplete variants contribute no credit as functioning combos.
3. R3 (parent R16): Preserve supported Commander/Standard assessment behaviour except for the intended incomplete-combo correction.
4. R4 (parent R20): Assessment stays observational and stateless.
5. R5 (parent R21): Verify behaviour through real entry points, including the zero-complete / 18-missing-one-card regression case.

## Constraints

- Assessment remains observational, stateless MCP behaviour over stdio.
- No calibrated Brawl model is introduced.

## Done when

- A Brawl request returns an explicit unsupported-scoring outcome with no Commander score or strength label.
- The zero-complete / 18-missing-one-card combo case cannot receive maximum functioning-combo credit.
- Existing Commander and Standard assessments are unchanged apart from the combo correction.

## Boundaries

- Not here: calibrating a Brawl power model; complete Brawl legality validation.
- Belongs to a sibling: lookup, import and export (epic-reliable-deck-workflows). Existing saved decks get honest outcomes without it.

## References

- parent — `_bmad-output/initiative-artificial-planeswalker/initiative-artificial-planeswalker.md`, Requirements R14–R16, R20, R21
- breakdown — `_bmad-output/initiative-artificial-planeswalker/archive-v6/epics-deck-workflow-reliability.md`, Epic List, Epic 2
- spec — `_bmad-output/initiative-artificial-planeswalker/archive-v6/spec-deck-workflow-reliability/SPEC.md`, CAP-3

## Notes

- Assumption: the first Brawl deliverable is explicit unsupported scoring.
- Source conflict: R3 (initiative R16) keeps supported Commander and Standard scores unchanged apart from the incomplete-combo correction; epic-codebase-quality-pass stories 38-40 (review Q17) change them. Settle before story 38 is built.
- Handoff: epic-codebase-quality-pass story 39 credits each Spellbook variant once in scoring (B5-D3 option a); this epic's R15 owns the combo list itself.
- Assumption: Done when was written by the v6-to-v7 migration from the breakdown's Epic 2; confirm with Sofia when refining and planning its stories.
