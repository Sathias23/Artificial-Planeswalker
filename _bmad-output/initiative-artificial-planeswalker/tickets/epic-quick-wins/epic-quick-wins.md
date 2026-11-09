---
type: epic
title: "Quick wins: everyday deck edits, clone, export, provenance and legality coverage"
parent: initiative-artificial-planeswalker
covers: [R1, R2, R3, R4, R5, R6]
sources:
  - _bmad-output/initiative-artificial-planeswalker/archive-v6/spec-quick-wins/SPEC.md
companions: []
after: []
status: in-progress
risk: medium
---

# Quick wins: everyday deck edits, clone, export, provenance and legality coverage

## Description

The 2026-09-06 feature review found the repository already holds the pieces of a propose, preview, apply, compare and export workflow without connecting them. This epic ships the five small items that connect them, ahead of the core investment: deck metadata and quantity tools, a clone, decklist export, recommendation provenance in the companion, and visible legality coverage. Entries 1 and 2 have shipped (PRs #114 and #115).

## Outcome

The agent operator does ordinary edits without remove-and-re-add dances, freezes a "before" deck without re-importing, takes a finished deck back to Arena, and trusts what the companion and the legality panel say; the measure is the spec's Success signal.

## Requirements

1. R1 (parent R1, CAP-1): The caller can rename a deck and set or clear its strategy and tags through one MCP tool, with "omitted" and "cleared" kept distinct. A rename changes only the name; omitting `strategy` leaves it; null clears it; an unknown deck answers `not_found`; the companion receives `deck_changed`; `updated_at` advances.
2. R2 (parent R2, CAP-2): The caller can set the exact copies of a card in a board, by card id or name, mainboard or sideboard. Quantity N reloads as N; a card absent from that board answers `card_not_found` and is not added; quantity 0 removes the row; colour identity and `updated_at` refresh; `deck_changed` is emitted.
3. R3 (parent R3, CAP-3): The caller can copy a deck into a new deck, optionally renamed. Card rows equal the source's row for row (quantity, board, commander flag) and format, strategy, tags and colour identity match; new id and `created_at`; the source is untouched; a mid-copy failure leaves no partial deck; `compare_deck_power`'s description points at the clone tool.
4. R4 (parent R4, CAP-4): The caller can export a deck as Arena text or plain `<qty> <name>` text, sectioned commander / mainboard / sideboard, from MCP and the companion. Arena export then import into a fresh deck round-trips every row; the plain shape has no set or collector suffix; the companion serves the same text from a GET route with a copy control; an empty deck exports section headers only.
5. R5 (parent R5, CAP-5): Every suggestions, swaps, tier-list or groups push names its deck. Each payload accepts an optional `deck_id`; a push for deck A viewed while B is active is labelled with A's name; a push older than its deck's `updated_at` is stale; a push without `deck_id` renders as today; history entries keep their label after a deck switch; the confidence indicator says it is the agent's confidence.
6. R6 (parent R6, CAP-6): `validate_deck` and `format_check` report per format which known rules were not checked. A commander report lists commander size, colour identity and commander eligibility as unchecked; a vintage report lists no restricted line (epic-codebase-quality-pass story 32 checks restricted cards first); a standard report lists nothing beyond rotation; the companion format panel renders the list; the `format-legality` skill states the same coverage; no verdict changes.

## Constraints

- Every deck write (R1 to R4) lives in `src/mcp_server`; the companion export route and the coverage panel are read-only (AD-2) and the import-boundary tests stay green.
- New or extended tools are stateless, emit `deck_changed` after a successful write, and update the five shipped skills, `plugin/` and the OpenAPI/types artifacts in the same PR.
- No schema change and no migration: R5 uses `updated_at` as its revision marker; R6 reports coverage from a per-format table in `src/logic` pinned by a test over every `FormatType` member.
- R6 enforces no new rule; R4 export never mutates; analysis stays observational.
- Repository write semantics stay: `_UNSET` for omitted, `None` for clear, commit-and-refresh, rollback on `IntegrityError`; the clone is one transaction. The repository's `quantity >= 1` contract stands; the R2 tool routes 0 to removal.
- R4's Arena shape uses the section headers the importer already understands (Commander, Deck, Sideboard) and never emits a Companion section.
- Order: R1 and R2 ship together, then R3, R4, R6, R5 last. R1 to R4 are MCP-only; R5 and R6 cross the contract boundary and need `npm run gen:api`.
- Regression tests are behaviour tests through real entry points, never source scans.

## Done when

- The spec's Success signal runs end to end on master: rename, set to three copies, clone, export to Arena text, re-import into an empty deck to an identical list.
- The companion shows a week-old swap suggestion labelled with its deck name and marked stale.
- A commander deck's legality panel says in words that commander size and colour identity were not checked.
- Skills, `plugin/` and generated API artifacts are in step for every shipped entry.

## Boundaries

- Not here: format-specific rule enforcement; transactional change preview and apply; plain-text `4 Card Name` import; durable revision ids, saved revisions, diffs or undo; any companion write path, download endpoint beyond a text GET, or new display mode; ranks 7 to 15 of `docs/future-ideas.md`.
- Must not change: the frozen viewer; `HISTORY_CAP` retention and revisit semantics in `ui/src/state/agentView.ts`.
- Belongs to a sibling: verified Arena printing identifiers on export and bulk resolution (epic-reliable-deck-workflows).

## References

- parent — `_bmad-output/initiative-artificial-planeswalker/initiative-artificial-planeswalker.md`, Requirements R1–R6
- spec — `_bmad-output/initiative-artificial-planeswalker/archive-v6/spec-quick-wins/SPEC.md`, the v6 contract this epic was rendered from
- source — `docs/future-ideas.md`, the 2026-09-06 feature review
- architecture — `_bmad-output/initiative-artificial-planeswalker/architecture-Artificial-Planeswalker-2026-07-25/architecture-Artificial-Planeswalker-2026-07-25.md`, AD-2 and AD-3

## Notes

- Assumption: the companion export is a GET returning `text/plain` with a copy-to-clipboard control; a download link is optional because the sandboxed browser may block it.
- Assumption: the default clone name is `<source name> (copy)`; deck names need not be unique.
- Assumption: the unchecked-rule table is hand-maintained beside the validator's rule set.
- Decision: 2026-09-06, quantity 0 removes the card rather than erroring (spec memlog).
- Open question: R5, should `deck_id` become required on the `companion_show_*` payloads, or stay optional for older callers? The spec assumes optional.
- Open question: R4, is a companion download button wanted, or is copy-to-clipboard enough?
- Open question: R6, should the unchecked-rule list also appear in `validate_deck`'s LLM-facing summary text, or only in the structured result?
- Source conflict: R4 never emits a Companion section; epic-reliable-deck-workflows R7 (initiative R13) preserves one. Settle before entry 3 is built.
- Assumption: Done when was written by the v6-to-v7 migration from the spec's Success signal; confirm with Sofia.
- Decision: 2026-11-09, board review, Brad (settles the R6 source conflict with epic-codebase-quality-pass story 32): story 32 makes restricted a checked rule and builds before entry 4 (`after`), so R6's Vintage report lists no restricted line; "no verdict changes" binds entry 4 only.
- Handoff: entry 5's `deck_id` payload field meets epic-codebase-quality-pass stories 44, 45, 50, 51, 56 and 58, which edit `contracts.py`, `agentView.ts` and `SuggestionsView`; build order is an open question in the initiative's Notes.
