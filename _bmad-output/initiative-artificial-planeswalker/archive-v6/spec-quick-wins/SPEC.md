---
id: SPEC-quick-wins
companions: []
sources:
  - ../../../docs/future-ideas.md
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate. Source documents listed in frontmatter are for traceability only — consult them only if you need narrative rationale or prose color this contract intentionally omits.

# Quick Wins (future-ideas 2026-09-06, delivery step 1)

## Why

An **opportunity to capture**. The 2026-09-06 feature review found that the repository already
holds the pieces of a propose → preview → apply → compare → export workflow but does not connect
them. Five of its fifteen items are small enough to ship before the core investment: the
repository can already rename a deck and set a card's quantity, yet no MCP tool exposes either;
there is no way to copy a deck, so the power-comparison tool tells callers to re-import a list to
freeze a "before"; there is no export, so a finished deck cannot travel back to Arena; a
recommendation pushed to the companion never says which deck it was about, so history entries go
silent after a deck switch; and a legality pass reads as full coverage when the validator
deliberately skips Commander sizing, colour identity and restricted-card rules. Affected: the
agent operator doing ordinary edits, and anyone trusting a green legality panel. All work is
`[Unreleased]` toward 0.6.0.

## Capabilities

- **CAP-1** — Deck metadata edit tool
  - **intent:** The caller can rename a deck and set or clear its strategy and tags through one
    MCP tool, with "omitted" and "cleared" kept distinct.
  - **success:** A rename changes only the name; omitting `strategy` leaves it; passing null
    clears it; an unknown deck answers `not_found`; the companion receives `deck_changed`; the
    deck's `updated_at` advances.

- **CAP-2** — Set card quantity tool
  - **intent:** The caller can set the exact number of copies of a card in a board (by card id or
    name, mainboard or sideboard) in one call.
  - **success:** Quantity N reloads as N; a card absent from that board answers `card_not_found`
    and is not added; quantity 0 removes the row; colour identity and `updated_at` are refreshed;
    `deck_changed` is emitted.

- **CAP-3** — Clone deck tool
  - **intent:** The caller can copy a deck into a new deck, optionally renamed, preserving every
    card row and the deck's metadata, so experiments and before/after comparison need no
    re-import.
  - **success:** The clone's card rows equal the source's row for row (quantity, board, commander
    flag) and its format, strategy, tags and colour identity match; it has a new id and
    `created_at`; the source is untouched; a failure mid-copy leaves no partial deck; the
    `compare_deck_power` description points at the clone tool instead of re-importing.

- **CAP-4** — Decklist export
  - **intent:** The caller can export a deck as Arena text (the shape `import_decklist` accepts)
    or as plain `<qty> <name>` text, sectioned commander / mainboard / sideboard, from MCP and
    from the companion.
  - **success:** Arena export followed by import into a fresh deck round-trips every row
    (quantity, board, commander); the plain shape carries no set or collector suffix; the
    companion serves the same text from a GET route with a copy control; an empty deck exports
    section headers only.

- **CAP-5** — Recommendation provenance
  - **intent:** Every suggestions, swaps, tier-list or groups push names the deck it was made
    for, and the companion shows that name on the view and in history, marking a push stale when
    its deck has changed since the push or is not the displayed deck.
  - **success:** Each payload accepts an optional `deck_id`; a push for deck A viewed while B is
    active is labelled with A's name; a push whose timestamp precedes its deck's current
    `updated_at` is marked stale; a push without `deck_id` renders as today (no label, never
    stale); history entries keep their label after a deck switch; the confidence indicator's copy
    says it is the agent's confidence.

- **CAP-6** — Visible legality coverage
  - **intent:** `validate_deck` and `format_check` report, per format, which rules were checked
    and which known rules were not, so a pass never implies coverage the validator lacks.
  - **success:** A commander report lists commander size (100 exact), colour identity and
    commander eligibility as unchecked; a vintage report lists restricted cards as unchecked; a
    standard report lists nothing beyond rotation; the companion format panel renders the
    unchecked list; the `format-legality` skill states the same coverage; no verdict changes.

## Constraints

- Every deck write (CAP-1 to CAP-4) lives in `src/mcp_server`; the companion export route and the
  coverage panel are read-only (AD-2) and the import-boundary tests stay green.
- New or extended tools are stateless (`deck_id` supplied), emit `deck_changed` after a
  successful write, and update the five shipped skills, `plugin/` and the OpenAPI/types artifacts
  in the same PR.
- No schema change and no migration: CAP-5 uses `updated_at` as its revision marker; CAP-6
  reports coverage from a per-format table in `src/logic` pinned by a test over every
  `FormatType` member.
- CAP-6 enforces no new rule; CAP-4 export never mutates; analysis stays observational.
- Repository write semantics stay: `_UNSET` for omitted, `None` for clear, commit-and-refresh,
  rollback on `IntegrityError`; the clone is one transaction. The repository's `quantity >= 1`
  contract stands; the CAP-2 tool routes 0 to removal.
- CAP-4's Arena shape uses the section headers the importer already understands (Commander, Deck,
  Sideboard) and never emits a Companion section.
- Order: CAP-1 and CAP-2 ship together, then CAP-3, CAP-4, CAP-6, CAP-5 last. CAP-1 to CAP-4 are
  MCP-only; CAP-5 and CAP-6 cross the contract boundary and need `npm run gen:api`.
- Regression tests are behaviour tests through real entry points, never source scans.

## Non-goals

- Format-specific rule enforcement (Commander size, colour identity, restricted, copy
  exceptions): rank 1 of the source, core investment.
- Transactional change preview and apply with expected revision (rank 2).
- Plain-text `4 Card Name` import (the import half of rank 5).
- A durable revision id, saved revisions, diffs or undo (rank 12); a computed-evidence field on
  swaps distinct from agent confidence.
- Any companion write path, download endpoint beyond a text GET, or new display mode; the frozen
  viewer is untouched.
- Ranks 7 to 15 of the source in general.

## Success signal

An operator renames a deck, sets a card to three copies, clones it, exports the clone to Arena
text and re-imports it into an empty deck to get an identical list; the companion shows a
week-old swap suggestion labelled with its deck name and marked stale; and a commander deck's
legality panel says in words that commander size and colour identity were not checked.

## Assumptions

- The companion export is a GET returning `text/plain` with a copy-to-clipboard control; a
  download link is optional because the sandboxed browser may block it.
- The default clone name is `<source name> (copy)`; deck names need not be unique.
- The unchecked-rule table is hand-maintained beside the validator's rule set.

## Open Questions

- CAP-2: should quantity 0 remove the card, or be rejected? The spec assumes it removes.
- CAP-5: should `deck_id` become required on the `companion_show_*` payloads, or stay optional for
  older callers? The spec assumes optional.
- CAP-4: is a companion download button wanted, or is copy-to-clipboard enough?
- CAP-6: should the unchecked-rule list also appear in `validate_deck`'s LLM-facing summary text,
  or only in the structured result?
