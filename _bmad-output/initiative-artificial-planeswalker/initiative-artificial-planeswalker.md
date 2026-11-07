---
type: initiative
title: "Artificial-Planeswalker gives an LLM dependable, honest MTG deckbuilding tools"
sources:
  - _bmad-output/initiative-artificial-planeswalker/archive-v6/spec-quick-wins/SPEC.md
  - _bmad-output/initiative-artificial-planeswalker/archive-v6/spec-deck-workflow-reliability/SPEC.md
  - _bmad-output/initiative-artificial-planeswalker/archive-v6/epics-deck-workflow-reliability.md
companions:
  - docs/architecture.md
  - _bmad-output/initiative-artificial-planeswalker/architecture-Artificial-Planeswalker-2026-07-25/architecture-Artificial-Planeswalker-2026-07-25.md
  - _bmad-output/initiative-artificial-planeswalker/ux-Artificial-Planeswalker-2026-07-22/ux-Artificial-Planeswalker-2026-07-22.md
after: []
status: in-progress
risk: medium
---

# Artificial-Planeswalker gives an LLM dependable, honest MTG deckbuilding tools

## Description

Artificial-Planeswalker is a local, stateless MCP server that gives an LLM Magic: The Gathering deckbuilding tools over a Scryfall card database, plus a read-only companion web app that shows the active deck. The MCP pivot, semantic search, the deckbuilding skills, deck power assessment and the companion app (Epics 1–17) have shipped; their plans are archived unchanged in `archive-v6/`. This initiative carries the open work: closing the gaps in ordinary deck workflows (edit, clone, export, provenance, legality coverage) and making lookup, import, export and assessment dependable and honest for real Arena decks.

## Outcome

An agent operator can build, copy, move and judge a real Arena deck end to end without database workarounds, manual name repairs or misleading results; the success signals are the two sources' own (quick-wins Success signal, deck-workflow-reliability Success signal).

## Requirements

1. R1 (spec-quick-wins CAP-1): The caller can rename a deck and set or clear its strategy and tags through one MCP tool, with "omitted" and "cleared" kept distinct.
2. R2 (spec-quick-wins CAP-2): The caller can set the exact number of copies of a card in a board, by card id or name, in one call; quantity 0 removes the row.
3. R3 (spec-quick-wins CAP-3): The caller can copy a deck into a new deck, optionally renamed, preserving every card row and the deck's metadata, in one transaction.
4. R4 (spec-quick-wins CAP-4): The caller can export a deck as Arena text or plain `<qty> <name>` text, sectioned, from MCP and from the companion; Arena export round-trips through `import_decklist`.
5. R5 (spec-quick-wins CAP-5): Every suggestions, swaps, tier-list or groups push names the deck it was made for; the companion labels it and marks it stale when its deck changed or is not displayed.
6. R6 (spec-quick-wins CAP-6): `validate_deck` and `format_check` report per format which known rules were not checked, so a pass never implies coverage the validator lacks.
7. R7 (spec-deck-workflow-reliability FR1): Resolve an entire deck in one bulk request, accepting names and optional printing qualifiers with existing format/platform filters.
8. R8 (spec-deck-workflow-reliability FR2): Preserve input order, original text, indices and duplicates; return one attributable found, ambiguous-with-candidates, missing, failed or explicitly unfinished result per input, plus batch completeness.
9. R9 (spec-deck-workflow-reliability FR3): Return actionable outcomes for oversized requests and expired deadlines, cancel unfinished work, release resources and permit successful subsequent requests.
10. R10 (spec-deck-workflow-reliability FR4): Use consistent card resolution in bulk lookup and import; resolve unambiguous front-face names to playable identities, exclude art cards, and explicitly report qualifier mismatch or fallback.
11. R11 (spec-deck-workflow-reliability FR5): Import name-only and printing-qualified lists while preserving additive behaviour, reporting each rejected line, imported totals and partial success.
12. R12 (spec-deck-workflow-reliability FR6): Export verified Arena-compatible names and printing identifiers; substitute only verified printings of the same playable identity and report unexportable cards explicitly.
13. R13 (spec-deck-workflow-reliability FR7): Preserve playable identities, quantities and supported sections across import/export round trips, including split and double-faced cards.
14. R14 (spec-deck-workflow-reliability FR8): Report Brawl numerical scoring as unsupported without substituting a Commander score or strength label.
15. R15 (spec-deck-workflow-reliability FR9): Separate complete combos from missing-card suggestions; incomplete variants contribute no functioning-combo credit.
16. R16 (spec-deck-workflow-reliability FR10): Preserve supported Commander/Standard assessment behaviour except for the intended incomplete-combo correction.
17. R17 (spec-deck-workflow-reliability NFR1): Bound lookup work, concurrency and response size; set batch limits and deadlines from measurements.
18. R18 (spec-deck-workflow-reliability NFR2): Measure orchestration separately from server/database execution for 1-, 3-, 15-, ~90- and 100-card workloads before attributing stalls.
19. R19 (spec-deck-workflow-reliability NFR3): Verify cancellation, resource cleanup and recovery through injected queued/running stalls and subsequent requests.
20. R20 (spec-deck-workflow-reliability NFR4): Keep lookup, export and analysis observational and MCP calls stateless; mutations need explicit deck-management intent; the companion stays read-only.
21. R21 (spec-deck-workflow-reliability NFR5): Verify behaviour through real entry points; parser-only round trips do not establish Arena compatibility.
22. R22 (spec-deck-workflow-reliability NFR6): Do not treat platform availability aggregated across printings as proof that a stored printing is Arena-compatible.

## Constraints

- Every deck write lives in `src/mcp_server`; the companion is read-only and the import-boundary tests stay green (AD-2; spec-quick-wins Constraints).
- New or extended tools are stateless (`deck_id` supplied), emit `deck_changed` after a successful write, and update the five shipped skills, `plugin/` and the OpenAPI/types artifacts in the same PR (spec-quick-wins Constraints; AGENTS.md Policy).
- Analysis stays observational; export never mutates (spec-quick-wins Constraints; spec-deck-workflow-reliability Constraints).
- stdio is the only MCP transport (spec-deck-workflow-reliability Constraints; AGENTS.md).
- Repository write semantics stay: `_UNSET` for omitted, `None` for clear, commit-and-refresh, rollback on `IntegrityError` (spec-quick-wins Constraints).
- A schema change needs a hand-written `scripts/migrate_*.py` that preserves existing deck and card references (epics-deck-workflow-reliability Additional Requirements; AGENTS.md).
- Behaviour is tested through real entry points, never by scanning source (both sources).

## Done when

- The quick-wins success signal holds on master: rename, set to three copies, clone, Arena export, re-import into an identical list; a week-old swap labelled and stale; a commander legality panel naming the unchecked rules.
- A representative 100-card Arena Brawl deck resolves in one request, imports and exports without manual database access or name repairs, and is assessed without an unsupported numeric rating.
- The mixed-failure and injected-stall cases in `acceptance.md` pass with no disappearing inputs or lingering resource exhaustion.
- Each change ships in a released version with skills, `plugin/` and generated API artifacts in step.

## Boundaries

- Not here: format-specific rule enforcement, transactional preview/apply, durable revisions or undo (spec-quick-wins Non-goals); calibrated Brawl scoring, complete Brawl legality, atomic swaps, broad synergy expansion, companion launch diagnostics (spec-deck-workflow-reliability Non-goals).
- Must not change: the frozen viewer and `view_deck` (AD-15).
- Tracer path: a deck edited and cloned (epic-quick-wins), resolved and exported for Arena (epic-reliable-deck-workflows), then assessed honestly (epic-trustworthy-assessment).

## References

- spec — `_bmad-output/initiative-artificial-planeswalker/archive-v6/spec-quick-wins/SPEC.md`, Capabilities, Constraints, Non-goals
- spec — `_bmad-output/initiative-artificial-planeswalker/archive-v6/spec-deck-workflow-reliability/SPEC.md`, Capabilities, Constraints
- breakdown — `_bmad-output/initiative-artificial-planeswalker/archive-v6/epics-deck-workflow-reliability.md`, Requirements Inventory, FR Coverage Map
- architecture — `docs/architecture.md`, the MCP pivot design of record
- architecture — `_bmad-output/initiative-artificial-planeswalker/architecture-Artificial-Planeswalker-2026-07-25/architecture-Artificial-Planeswalker-2026-07-25.md`, the companion's AD-n decisions
- design — `_bmad-output/initiative-artificial-planeswalker/ux-Artificial-Planeswalker-2026-07-22/ux-Artificial-Planeswalker-2026-07-22.md`

## Notes

- Decision: 2026-11-07, Brad: shipped Epics 1–17 and the finished specs (deck power assessment, quality audit P1, quality review fixes) are archived in `archive-v6/` unchanged rather than rebuilt as done tickets; their sprint status stays on the `process` branch.
- Source conflict: R4 (spec-quick-wins CAP-4) never emits a Companion section on export; R13 (spec-deck-workflow-reliability FR7) preserves a Companion section across round trips. Sofia to settle before epic-quick-wins entry 3 or epic-reliable-deck-workflows entry 5 is built.
- Open question: epic-quick-wins entry 3 (decklist export) and epic-reliable-deck-workflows entry 5 (verified Arena export) build overlapping export paths; whether one subsumes the other is unsettled.
