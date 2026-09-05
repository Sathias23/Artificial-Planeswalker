---
id: SPEC-quality-review-fixes
companions:
  - batches.md
sources:
  - ../../../docs/quality-review-2026-09-06.md
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate. Source documents listed in frontmatter are for traceability only — consult them only if you need narrative rationale or prose color this contract intentionally omits.

# Quality Review Fixes (2026-09-06)

## Why

A **pain to solve**. An external review of the repo at `5f302f4` found six correctness gaps that
the full green gate does not cover, and every one was confirmed against the code. The database
engine never enables SQLite foreign-key enforcement, so deleting a deck leaves its card rows
behind. The companion can miss an active-deck switch in the window between its first snapshot and
its first socket subscription, and can strand on the updating panel when a transient refusal lands
after the poll has already recovered. Deck colour identity and modification time are never
maintained by ordinary card mutations. The incremental search index skips a card whose filter
metadata changed but whose text did not. And the project context that every bmad skill loads on
every run still describes the June 2026 Chainlit monolith as the current codebase. Affected: the
single operator (stale panels, stale identity) and every agent run in this repo (stale context).
All work is `[Unreleased]` toward 0.6.0.

## Capabilities

- **CAP-1** — Referential integrity enforced
  - **intent:** Every SQLite connection the project opens enforces foreign keys; deleting a deck
    removes its card associations; an existing database is cleared of orphaned association rows.
  - **success:** `PRAGMA foreign_keys` reads 1 on a fresh connection from both the MCP and the
    companion engine; after `delete_deck` on a populated deck no `deck_cards` row carries that id;
    inserting an association for a missing deck or a missing card raises `IntegrityError`; a
    database seeded with
    orphan rows has none after the migration path runs; the Scryfall bulk import and the
    integration suite pass with enforcement on.

- **CAP-2** — Companion first-connect reconciliation
  - **intent:** The companion's deck view reflects the active deck as of the moment the socket
    goes live, not only as of the initial HTTP snapshot.
  - **success:** A test that switches the active deck between the snapshot response and the
    first socket open ends with the new deck on the glass; the reconnect re-drive is unchanged;
    a re-render never boots.

- **CAP-3** — Transient deck refusal recovers
  - **intent:** A deck request refused with `database_unavailable` while the poll is healthy or
    stopped recovers without user action and without a socket frame.
  - **success:** Tests for both orderings (poll recovers before, and after, the deck refusal) end
    with the deck loaded; an id that refuses permanently still does not loop; a superseded request
    never overwrites newer state.

- **CAP-4** — Deck metadata maintained
  - **intent:** A deck's reported colour identity and modification time reflect its cards after
    every mutation path: add, bulk add, remove, quantity update, import, merge. Identity derives
    from card colour identity.
  - **success:** After each path the deck's `updated_at` has advanced and `color_identity` equals
    the WUBRG-sorted union of its cards' `color_identity`; a card with empty `colors` and a blue
    identity yields `["U"]`.

- **CAP-5** — Search-filter metadata refreshed
  - **intent:** An incremental index build refreshes a card's colour flags and mana value when
    only those changed, without re-embedding unchanged text.
  - **success:** After changing only `colors` or `cmc`, an incremental build followed by a
    filtered search reflects the new values, and the embedder is not called for that card.

- **CAP-6** — Agent-facing project context current
  - **intent:** Every agent session in this repo, Claude Code and Codex alike, loads one
    project context that describes the current architecture (MCP server, companion app, data and
    search layers), entry points, gates, and commands; nothing loaded describes the
    Chainlit/PydanticAI monolith as current.
  - **success:** `AGENTS.md` exists at the repo root with the `bmad-project-context` block;
    `CLAUDE.md` exists and imports it; `_bmad-output/project-context.md` is gone and no file
    matched by any skill's `persistent_facts` glob mentions Chainlit or PydanticAI as current; the
    block names the uv, ruff, mypy, pytest, and npm gates and the plugin rebuild rule; any retained
    history sits under a heading that says it is history.

## Constraints

- Order: CAP-6 merges first. CAP-1 lands before CAP-4 and CAP-5 (same repository file, and
  enforcement changes what the metadata tests may insert). CAP-2 and CAP-3 ship together.
- Two Greptile runs: a backend PR (CAP-1, CAP-4, CAP-5) and a companion PR (CAP-2, CAP-3). CAP-6
  goes straight to master with no Greptile. The full local gate in `batches.md` runs before the
  first push of each Greptile PR.
- The foreign-key pragma and the orphan cleanup ride the existing connect-hook path and never fail
  a connection. The companion engine (read-only shell, AD-2) gets the pragma but never the cleanup
  write.
- CAP-2 must not boot on re-render. CAP-3 must not add a level-triggered retry that loops against
  an id that refuses forever.
- CAP-1 enforces both foreign keys: an association whose card is missing from `cards.db` is
  rejected, not only one whose deck is missing.
- CAP-6 edits no `customize.toml` entry. The retired `project-context.md` is deleted, not left as
  a pointer, so no skill loads a stale fact.
- Deck identity derives from card `color_identity`. Search filters keep using `colors`.
- CAP-5 never re-encodes a card whose embedding text is unchanged.
- Regression tests are behaviour tests through real entry points, never source scans. The
  docs-drift ban from `spec-quality-audit-p1` stands.
- Generated artifacts (`plugin/`, companion static, `openapi.json`, `types.d.ts`) are rebuilt and
  committed in the PR that moves them. Layering, `mypy --strict` on both platforms, and no new UI
  runtime dependency stay.

## Non-goals

- Reproducing CAP-2 or CAP-3 in a live browser; harness tests are the evidence.
- Reworking the poll and socket architecture or adding a general retry layer to the companion.
- Foreign-key behaviour on any backend other than SQLite.
- Re-running the review's full validation matrix as a new gate; CI is the gate.
- Any defect the review did not list.

## Success signal

Deleting a populated deck leaves no association rows; switching the active deck during the
companion's first second shows the new deck; a database that recovers mid-request unsticks the
panel on its own; and a fresh `bmad-build` run loads a project context that names the MCP server
and the companion, not Chainlit.

## Assumptions

- Batching CAP-4 and CAP-5 into the CAP-1 PR trades the strict 6, 1, 2, 3, 4, 5 order for one
  fewer Greptile run. A third run buys the strict order.
- Orphan cleanup runs once from the MCP engine's connect path, guarded like the NOCASE index
  migration, so an existing database is repaired without `initialize_database`.
- The stored deck `color_identity` and `updated_at` columns stay because the companion OpenAPI
  contract carries them. Deriving on read is acceptable if the contract is unchanged.
- Claude Code auto-loads `CLAUDE.md` and honours `@AGENTS.md` imports, so a one-line `CLAUDE.md`
  is enough for every Claude session, `bmad-build` included, to carry the block. Codex reads
  `AGENTS.md` natively.
- Strict card enforcement is free for the MCP path because `add_card_to_deck` already answers
  `card_not_found` before touching the session; any test fixture that inserts associations with
  invented card ids must seed the card first.
