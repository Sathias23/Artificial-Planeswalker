# Companion App PRD — Addendum

This addendum holds material that belongs downstream (architecture, UX spec) or that
earned preservation without a place in the PRD narrative. OQ-2/3/4 labels below use
the source brief's numbering; the PRD's own open questions are OQ-A/OQ-B.

## Key technical decisions (from the feature brief, for architecture)

- **Web page first, not Electron.** The companion backend serves the SPA at
  `localhost:8765`; OS window snapping provides side-by-side. Electron/Tauri would add
  only always-on-top and a launcher icon, and since a wrapper would load the same URL,
  wrapping later requires no architecture change. **Tauri preferred over Electron** if
  wrapped later.
- **FastAPI backend** sharing the existing Python codebase, DB access layer, and
  Pydantic models with the FastMCP server. Console-script entry point alongside the MCP
  server (`uv run artificial-planeswalker companion` or similar).
- **Transport: localhost HTTP + WebSocket**, not file-watching, for agent-pushed
  content — lower latency, simpler payload semantics. Decks are DB rows, not files, so
  file-watching doesn't apply anyway; the out-of-band fallback (FR-16) polls SQLite
  `PRAGMA data_version` instead.
- **zustand store is client-side only.** Suggested slices: `activeDeck`, `agentPanel`
  (latest push + session history), `connectionStatus`. WebSocket handlers call
  `store.setState`; the agent never touches the store directly.
- **Frontend packaging:** the built Vite bundle ships as static assets inside the
  Python package (package data), so a fresh install needs no Node toolchain (SC-4). CI
  builds the SPA and drift-checks the committed build output, mirroring the existing
  `plugin/` tree pattern.
- **Distribution nicety:** consider a plugin skill instructing the agent how and when
  to use companion tools.

## Full-card-art availability (verified 2026-07-22)

The local snapshot already stores everything needed for full card faces:

- `cards.image_uris` (`src/data/models/card.py`) holds the Scryfall size map — `small`,
  `normal`, `large`, `png`, `art_crop`, `border_crop` — as JSON. `png` is the full
  card face with transparent corners; `normal`/`large` are JPG full faces.
- Double-faced cards have `image_uris` per entry in `card_faces`, not at top level
  (`src/data/importers/transformers.py`) — the FR-04 image endpoint needs a `face`
  parameter and per-face cache keys.
- Implication: the image proxy resolves CDN URLs from stored data; no live Scryfall
  API metadata calls are ever needed.

## Open-question parking

### OQ-A: payload-schema constraints for design

Resolved product-side inputs the schema design must honor:

- Cards are referenced by Scryfall printing UUID only (FR-13); payloads carry no names.
- Suggestions: card ID + reason (short text) + optional category. Swaps: out-ID /
  in-ID pairs + rationale. Tier list: ordered tiers (label + card IDs + optional note).
- Payloads must stay small enough that CM-1 holds (compact text returns; no payload
  echo into chat). Max-size limits are a design decision.
- Agent panel history (FR-18) is client-side: schemas need no history semantics, but
  each push should carry a `kind` and a timestamp so the history list can label
  entries.
- Empty-payload semantics (zero suggestions, all-empty tiers): schema design decides
  reject-at-schema vs. render-empty-state.
- ID-validation locus: the schema/endpoint design decides whether the companion
  backend validates card IDs at ingest; either way, the UI renders unknown-ID entries
  degraded ("unknown card" placeholder), never failing the whole push.

### OQ-B: TS type generation options

Candidates: datamodel-code-gen (Python-side), json-schema-to-typescript (from
Pydantic-emitted JSON Schema), or manual types with drift tests. The choice belongs
to architecture; the CI drift-check requirement (NFR-03, risk table) stands
regardless of tool.

## Delegated design checklist

Architecture and the UX spec must decide each of these deliberately. They are edge
cases confirmed during the reviewer gate as downstream decisions, not PRD
requirements (full analysis in `review-edge-case-hunter.md`):

- **Backend restarted onto a different port while the UI is open** — the disconnected
  state should guide the user to the terminal/relaunch URL (UX spec).
- **Corrupt/partially written discovery file** — tools treat parse failure as "app not
  running"; discovery-file writes are atomic (temp + rename).
- **Refetch racing a second mutation** — NFR-04 implies latest-wins; use coalescing,
  in-flight cancellation, or a version check.
- **Mutation persists but event POST fails** — emission failure is swallowed (the
  mutation result must not degrade); the staleness window is accepted until FR-16.
- **Invalid `size`/`face` params on the image endpoint** — suggested contract: unknown
  size → 400; missing face → 404; single-faced + `face=0` → the image.
- **Ticket lifecycle** — expiry and single-use vs. reusable; WS reconnect must mint a
  fresh ticket per attempt.
- **Read-only open of a WAL DB** — `mode=ro` needs the `-shm` file present (or
  `immutable`, which would break FR-16); architecture picks the concrete open recipe
  (Windows-relevant; don't discover as a Story-1 bug).
  **ANSWERED 2026-08-18 (story 15.3) — by rejecting the premise.** Architecture did not pick a
  connection recipe: it picked a different *kind* of enforcement. Both horns of this item turned
  out to be real (`mode=ro` does need the `-shm` sidecar; `immutable` does foreclose FR-16), so
  AD-2 made read-only a **structural** property instead — `tests/unit/companion/test_import_boundary.py`
  fails CI if any file under `src/companion/**` can reach a write path, and the engine in
  `src/companion/app/deps.py` carries no read-only flag at all. NFR-02 in the PRD body was amended
  to match; this parking entry is kept as the record of why the recipe was never chosen.
- **Image cache integrity/staleness** — atomic temp-file writes; accepted staleness
  when a data refresh changes `image_uris` (cache keyed by id+size+face).
- **DFC flip-state persistence** — whether flip state survives `deck_changed`
  re-renders (a snap-back reads as a bug); cross-tab history divergence (FR-06
  broadcasts to all tabs, FR-18 history is per-tab) (UX spec).

## 2026-07-25 — deltas from the Voltglass UX design

The companion UX was designed directly in Claude Design rather than from the handoff
prompts, and the resulting screen architecture differs from what the PRD assumed. The
UX reviewer gate (`ux-designs/…/validation-report-2026-07-25.md`) surfaced four items
that reach back into this PRD. Recorded here; the PRD body carries only the new FR.

- **FR-23 added** (`companion_show_groups`, P1, Feature D / Phase 2). The design
  introduced a fourth agent view — titled card groups with a rationale paragraph each —
  that no existing tool produced. The UX spine had invented a tool name to fill the
  gap; this makes it real. Note the payload shape is *not* covered by OQ-A's parked
  constraints: groups carry a title and a prose rationale per group, and may reference
  cards **outside** the active deck (budget substitutes, sideboard options, answers the
  deck doesn't yet run). OQ-A's schema work must extend to cover it.
  **DISCHARGED 2026-08-18 (story 15.3).** It did extend to cover it: story c5-1 defined all four
  payload shapes at once rather than incrementally, and `groups` landed with the other three as
  `{title, rationale, card_ids[]}` over a bare card reference, with the group-level title and
  rationale this note demanded. OQ-A is recorded as resolved in the PRD body (§12).
- **FR-19's flip control is unchanged and still required.** The Voltglass design ships
  no flip affordance, so the gate raised it as a missing design, not a missing
  requirement — FR-19 already mandates "a dedicated flip control — distinct from
  clicking the card". The control is now specified in `DESIGN.md` and `EXPERIENCE.md`;
  no PRD change was needed, and no duplicate FR was created.
- **FR-17's "opens a detail view" is now satisfied by a persistent panel.** The design
  replaced the modal detail overlay with an always-present right-column panel that
  tracks hover/focus, with click *pinning* it. The requirement's intent — click any card
  in any panel, get full face + oracle text + prices — holds; the wording assumes a view
  that opens. No change made; flagged so nobody reads the FR as mandating a modal.
- **FR-05 is satisfied differently.** Grid and text list are now simultaneous columns
  rather than a toggled pair, which removes the view toggle the previous UX draft
  specified. The requirement says "renders … a card-art grid and a text list view" and
  does not mandate a toggle, so this is compliant as written.
- **Read-only-glass pressure.** The design reaches agent content from a header nav, not
  only from an arriving push. The UX spine preserves the premise by ruling that a push
  still opens its own view and the nav only re-opens a dismissed one — but this is the
  one place where the design and §5's non-goals rub. If the ruling is reversed (nav
  becomes the primary path), SC-1's "250 ms push-to-render" needs restating as
  time-to-notification, because nothing would render on a push.

## Rejected alternatives (rationale preserved)

- **Full persistent push history** (OQ-4): rejected — requires the backend to retain
  events, cutting against the stateless fire-and-forget event model; session-only
  client history delivers the revisit value.
- **Generic `companion_display(kind, payload)` tool** (OQ-2): rejected in favor of
  separate tools — per-tool docstrings give the agent sharper affordances, and payload
  validation stays a plain model per tool instead of a discriminated union.
- **Power panel in MVP** (OQ-3): deferred — MVP proves the push pipe with suggestions;
  the radar-chart panel lands in Phase 3 once the core loop is solid.
- **Electron in MVP**: rejected (see the web-first decision above).
