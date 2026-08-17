# Epic 15 Context: Release Readiness

<!-- Generated from planning artifacts. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Turn a working companion app into something Brad would put in front of strangers. The old HTML deck
renderer is formally deprecated and points at its replacement without breaking anyone still calling
it; the documentation tells a user what the companion is, how to launch it, what it needs, where the
image cache lives on disk and how to remove it; the requirements documents stop contradicting the
architecture on the three points where they diverged during the build; the plugin install arrives
complete rather than as a second-class copy missing its UI; and Brad personally judges the finished
app against the UX contract and records the verdict. This epic closes the last open success
criterion — that the deck view and agent panel read as a deliberate product rather than a debug
dashboard — and that judgement is human, cannot be automated, and cannot be delegated.

## Stories

- Story 15.1: Deprecate `view_deck` and freeze `src/viewer`
- Story 15.2: Image cache stewardship — documented location, inspection and removal
- Story 15.3: Reconcile the PRD with what was built
- Story 15.4: Release documentation for the companion app
- Story 15.5: Plugin distribution parity
- Story 15.6: The SC-5 gate

## Requirements & Constraints

- **The companion is optional and nothing depends on it.** Every agent workflow must still complete
  with the app closed — the documentation has to say so plainly, and the deprecated HTML renderer
  must keep working unchanged through this phase and the next so that guarantee holds through the
  transition. The companion never replaces chat output.
- **One documented launch command.** `uv run artificial-planeswalker companion` is the single
  documented way to start the backend, and the same string must appear in every document that quotes
  it. A fresh install must reach a running app with no additional configuration, and the docs must
  say Node is never required at install or runtime.
- **A fresh install with no card database still starts.** The docs describe first run as the app
  coming up anyway and guiding the user to initialize the database — never an error.
- **Image cache stewardship is a documented choice, not a surprise.** The README must name the
  exact cache location under the project data dir, explain the two-character sharding, note that
  the location follows the data-dir environment override, give a copy-pasteable inspect/clear
  command, and state plainly that there is no eviction — with the expected footprint (roughly 12 MB
  per 100-card deck at one size) and the note that any eviction policy will be sized against a real
  measured footprint rather than guessed. The accepted staleness behaviour when a data refresh
  changes a card's image URIs (the old entry keeps being served, because the cache key is id + size
  + face) is stated rather than left to be discovered.
- **Uninstall leaves two things behind** and the docs must say which: the image cache, and the
  discovery file if the process did not exit cleanly.
- **Attribution is a condition of public release.** The Scryfall attribution and the Wizards of the
  Coast Fan Content Policy notice must appear in the project documentation as well as in the app
  footer, and the footer line must be present and visible without scrolling on every surface.
- **Port and discovery behaviour must be self-diagnosable** from the docs alone: the default port,
  the ephemeral fallback, the single-instance rule, and the "already running" message.
- **The CHANGELOG records** the companion app, the deprecation, the deferred removal of the old
  renderer, and the new dependencies with their version floors — including why the TypeScript
  version is pinned below 6.1.
- **The release gate's anti-patterns** are explicit: no raw JSON views, no log panes, no dense
  tables of ids, no error pages, no toast storms, no alert colours. The gate outcome is written
  down with its date and any conditions.

## Technical Decisions

- **Three requirement amendments are owed and are deliverables, not observations.** Read-only access
  is enforced by a CI import-boundary test, not by read-only connection strings (that recipe drags
  in a Windows landmine, and the immutable variant would foreclose a later phase's out-of-band change
  detection). The discovery file lives under the project data dir, not a home-directory dotfolder.
  Card face handling is driven by the presence of per-face image URIs, not by a Scryfall layout
  string — the card table has no layout column.
- **Six additions made during story work must also be recorded** in the requirements document or its
  addendum: the unknown-card reason token, the format-check endpoint, the active-deck read/write
  endpoints, the active-deck-changed envelope kind, deck-not-found as a set-active-deck outcome, and
  the ruling that all four agent payload shapes were fixed in this phase.
- **The four UX rulings are confirmed, not pending.** The UX behaviour spine and the 2026-07-25
  validation report must record them as settled decisions.
- **Two copies of the built SPA, both generated.** The bundle is committed under the backend's static
  directory and mirrored into the plugin tree by the existing rebuild + drift-check machinery. Neither
  copy is ever hand-edited; the drift check must cover the mirrored copy. This is forced by the
  distribution model — the project ships as a cloned tree, so build-time compilation would leave
  plugin users with no UI. Node stays dev/CI-only.
- **The MCP entry points must not have changed.** Both MCP config files still invoke the server
  module directly; the console script is a subcommand dispatcher whose bare invocation runs the MCP
  server exactly as before. Verify this rather than assume it.
- **Only product skills ship in the plugin** — the authoring/workflow skills must not leak into it.
- **The old renderer is frozen, not removed.** No new capability lands in it, its removal is scheduled
  for the next minor release once the companion is proven, and the deferral is written into the
  release notes so it is not forgotten. The companion never reuses the old renderer's HTML template —
  two renderers of one entity would diverge.

## UX & Interaction Patterns

- **The release judgement is against the visual and behavioural design contracts** (the Voltglass
  identity document and the experience document), performed by Brad, recorded with a date.
- **The "not a debug dashboard" tension is acknowledged rather than dodged:** four analytical panels
  sit permanently on screen, so the answer has to be carried by typography, spacing and restraint,
  not by sparseness.
- **The deferred arrow-key grid navigation carries a revisit flag** that must be consciously actioned
  or re-accepted at this gate, because the footer's Fan Content Policy links sit behind the card grid
  in the Tab order.
- **The reduced-motion inventory is audited against the shipped app:** every motion present has an
  entry with a named fallback, and any motion added during implementation was added to the list.
  Nothing pulses or loops under any setting.
- **Footer attribution styling is load-bearing:** secondary-tier text (a passing contrast tier, not a
  muted one), links persistently underlined rather than underlined on hover, opening in a new tab,
  each with an adequate hit area.

## Cross-Story Dependencies

- This epic depends on the deck-view, agent-push and deck-refetch epics being complete — the release
  gate judges the finished Phase-1 app, and the plugin-parity story mirrors the finished SPA bundle.
- 15.6 is last: it judges what 15.1–15.5 have finished documenting and packaging, and its footer,
  reduced-motion and Tab-order checks all run against the shipped app.
- 15.3 and 15.4 overlap on the launch command and the fresh-install story — the amended requirements
  document and the README must end up quoting the same strings.
- 15.5 depends on the committed SPA bundle produced by the frontend epic and on the existing
  plugin rebuild + drift-check machinery.
- 15.1's deferral note lands in the same release notes / CHANGELOG that 15.4 owns.
