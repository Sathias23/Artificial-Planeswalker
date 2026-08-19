# Epic 15 Context: Release Readiness

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Turn a working companion app into something Brad would put in front of strangers. The old HTML deck
renderer is deprecated and points at its replacement without breaking anyone still calling it; the
docs say what the companion is, how to launch it, and where the image cache lives and how to remove
it; the requirement documents stop contradicting the architecture where they diverged during the
build; the plugin install arrives complete rather than missing its UI; and Brad judges the finished
app against the UX contract and records the verdict. This closes the last open success criterion —
that the deck view and agent panel read as a deliberate product, not a debug dashboard — a
judgement that is human and cannot be delegated.

## Stories

- Story 15.1: Deprecate `view_deck` and freeze `src/viewer`
- Story 15.2: Image cache stewardship — documented location, inspection and removal
- Story 15.3: Reconcile the PRD with what was built
- Story 15.4: Release documentation for the companion app
- Story 15.5: Plugin distribution parity
- Story 15.6: The SC-5 gate

## Requirements & Constraints

- **The companion is optional and nothing depends on it.** Every agent workflow must still complete
  with the app closed — the docs say so plainly, and the deprecated HTML renderer keeps working
  unchanged through this phase and the next so that guarantee holds through the transition. The
  companion adds a visual channel; it never replaces chat output.
- **One documented launch command**, `uv run artificial-planeswalker companion`, quoted identically
  wherever it appears. A fresh install reaches a running app with one command and no configuration;
  the docs must state that Node is never required at install or runtime, and must describe first run
  on an empty database as the app coming up anyway and guiding the user to initialize it.
- **Image cache stewardship is a documented choice, not a surprise.** The README names the exact
  cache location under the per-user project data dir, explains the two-character sharding, notes
  that the location moves wholesale with the data-dir environment override, gives a copy-pasteable
  inspect/clear command, and says plainly that there is no eviction. The footprint quoted is the
  **measured** one — roughly 8.5 MB per 100-card deck at one size, about 90 KB per `normal` tile,
  over roughly 10 seconds; the earlier ~12 MB estimate was disproved by measurement and is labelled
  as disproved rather than dropped, so the two numbers do not disagree in silence. Also documented:
  that an eviction policy will be sized against a real footprint rather than guessed, and the
  accepted staleness when a data refresh changes a card's image URIs (the old entry is still served;
  the key is id + size + face).
- **Uninstall leaves two things behind** and the docs must name both: the image cache, and the
  discovery file if the process did not exit cleanly. Port and discovery behaviour must likewise be
  self-diagnosable from the docs alone — default port, ephemeral fallback, single-instance rule, and
  the "already running" message.
- **Attribution is a condition of public release.** The Scryfall attribution and the Wizards of the
  Coast Fan Content Policy notice appear in the project documentation as well as in the app footer,
  and the footer line is present and visible without scrolling on every surface — secondary-tier
  text (a passing contrast tier, not a muted one), links persistently underlined rather than on
  hover, opening in a new tab, each with an adequate hit area.
- **The CHANGELOG records** the companion app, the deprecation, the deferred removal of the old
  renderer, and the new dependencies with their version floors — including why the TypeScript
  version is pinned below its next major.
- **The release gate's anti-patterns are explicit:** no raw JSON views, log panes, dense id tables,
  error pages, toast storms or alert colours. The outcome is written down with its date and any
  conditions, so a later reader knows the gate was actually run.

## Technical Decisions

- **The requirements/architecture reconciliation is already done and is now the authority** the
  remaining release docs must match. Read-only database access is enforced structurally, by a CI
  import-boundary test over the companion package, not by a read-only connection string — that
  recipe needs a WAL sidecar file (a Windows landmine) and its immutable variant would foreclose
  out-of-band change detection later. The discovery file lives in the per-user project data dir, not
  a home-directory dotfolder. Face handling is driven by the presence of per-face image URIs, never
  by a Scryfall layout string — the card table has no layout column.
- **Six behaviours added during the build are now part of the recorded contract:** the unknown-card
  reason token; the deck format-check endpoint; the active-deck read/write pair (credential-free
  read, token-gated write); the `active_deck_changed` envelope kind, making the closed event set six
  rather than five; deck-not-found as a set-active-deck outcome; and the ruling that all four agent
  payload shapes were fixed in Phase 1. The two original open questions and the four UX rulings are
  answered and confirmed, not pending.
- **Two copies of the built SPA, both generated.** The bundle is committed under the backend's
  static directory and mirrored into the plugin tree by the existing rebuild + drift-check
  machinery; the drift check must cover the mirrored copy and neither copy is ever hand-edited. The
  plugin ships as a cloned tree, so build-time compilation would leave plugin users with no UI.
  Node stays dev/CI-only.
- **The MCP entry points must not have changed.** Both MCP config files still invoke the server
  module directly; the console script is a subcommand dispatcher whose bare invocation runs the MCP
  server exactly as before. Verify rather than assume.
- **Only product skills ship in the plugin** — the authoring/workflow skills must not leak into it.
- **The old renderer is frozen, not removed.** No new capability lands in it, removal is scheduled
  for the next minor release once the companion is proven, and the deferral is written into the
  release notes so it is not forgotten. The companion never reuses its HTML template — two renderers
  of one entity would diverge.

## UX & Interaction Patterns

- **The release judgement is against the visual and behavioural design contracts** (the Voltglass
  identity document and the experience document), performed by Brad, recorded with a date. The
  "not a debug dashboard" tension is acknowledged rather than dodged: four analytical panels sit
  permanently on screen, so the answer is carried by typography, spacing and restraint, not by
  sparseness.
- **The deferred arrow-key grid navigation carries a revisit flag** to be consciously actioned or
  re-accepted at this gate, because the footer's Fan Content Policy links sit behind the card grid
  in the Tab order. The measured stop counts predate the connection pill — every figure gains one
  and the sweep was not re-run — so the decision is made against numbers known to be one light.
- **The reduced-motion inventory is audited against the shipped app:** every motion has an entry
  with a named fallback, any motion added during implementation was added to the list, and nothing
  pulses or loops under any setting.

## Cross-Story Dependencies

- Depends on the deck-view, agent-push and deck-refetch epics being complete — the gate judges the
  finished Phase-1 app, and 15.5 mirrors the finished SPA bundle produced by the frontend epic
  through the existing plugin rebuild + drift-check machinery.
- 15.6 is last: it judges what 15.1–15.5 finished documenting and packaging, and its footer,
  reduced-motion and Tab-order checks all run against the shipped app.
- 15.3 (already reconciled) fixes the strings and facts 15.4's README and CHANGELOG must quote: the
  launch command, the data-dir location, the fresh-install story, the measured cache footprint.
- 15.1's deferral note lands in the same release notes / CHANGELOG that 15.4 owns.
