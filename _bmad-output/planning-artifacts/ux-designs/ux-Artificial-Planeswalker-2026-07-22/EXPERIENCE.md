---
name: Artificial-Planeswalker Companion
status: approved
updated: 2026-07-25
composition-reference: imports/claude-design/Planeswalker Companion.dc.html
sources:
  - _bmad-output/planning-artifacts/prds/prd-Artificial-Planeswalker-2026-07-22/prd.md
  - _bmad-output/planning-artifacts/prds/prd-Artificial-Planeswalker-2026-07-22/addendum.md
  - DESIGN.md (peer — visual identity, Voltglass)
  - imports/claude-design/ (design as-built, 2026-07-25)
---

# Artificial-Planeswalker Companion — Experience Spine

> **Revised 2026-07-25** to match the design developed directly in Claude Design. The screen architecture changed materially from the previous draft: the agent drawer became full-window agent views, the modal Detail view became a persistent detail panel, and the grid/list view toggle disappeared because both views are now on screen simultaneously. Rulings that this revision had to commit are tagged `[RULING 2026-07-25]` and are listed together at the foot under **Rulings introduced by the redesign** — they need Brad's confirmation.

## Foundation

Desktop browser SPA served by the Companion backend at `localhost:8765` (discovery file is source of truth for the port). The canonical posture: the browser window snapped beside a terminal chat agent. The layout targets **~1100px to ~2560px**; below ~1100px the right column drops beneath the left rather than compressing. Design reference width is **1720px**. Dark mode only, Voltglass.

UI system: **Vite + React**, client state in a **zustand** store (`activeDeck`, `agentViews`, `inspection`, `connectionStatus` slices) fed by exactly two inputs — REST responses and WebSocket messages. `DESIGN.md` is the visual identity reference; this spine is the behavior contract.

The governing principle, verbatim from the PRD: **"The browser is read-only glass: his only clicks are to inspect — flip a card, open the detail view — while everything that changes state flows through the agent. The agent drives, the app shows."** No deck editing from the UI (NG1). No LLM calls from the app (NG2).

The redesign puts pressure on this principle in one place: agent content is now reachable from a header nav, not only from an arriving push. The principle is preserved by the arrival ruling below — **the agent still opens the view; the nav re-opens it.** The user's clicks remain inspection and navigation-to-what-the-agent-already-said. Nothing on the glass mutates the deck.

## Information Architecture

| Surface | Phase | Reached from | Purpose |
|---|---|---|---|
| Deck header | P0 | Always, top of window | Deck name, format/size badges, agent-view nav |
| Deck view — card grid | P0 | Default surface, left column | Active deck as full card faces (`normal`), with quantity badges |
| Mana curve panel | P0 | Left column, below grid | Curve 1–7+, non-land, DFCs by front face |
| Color distribution panel | P0 | Left column, below grid | Pip distribution, source counts, deck value |
| Card detail panel | P0 | Right column, always present | Full face + name, cost, type, price, note for the card under inspection |
| Deck list panel | P0 | Right column, always present | Text list of the deck grouped by card type (FR-05 — satisfied as a permanent second column rather than a toggled alternate view) |
| Format check panel | P0 | Right column, always present | Legality, size, copy limit, sideboard, **banned cards**, rotation exposure — the wire's own `CHECK_ORDER`, which the panel renders without re-sorting. Amended 2026-08-06 (story c4-10, Q3): the row was "banned", and the mock's label for it was **"Banned or restricted"**, which is a **false label**. `deck_validator.py:433-452` reports a `restricted` card through the *legality* row deliberately and pinned (`test_restricted_is_unchanged_by_the_banned_split`): the `banned_card` rule splits off only for a legality of exactly `banned`, because "a restricted card is legal with a 1-copy limit, which this validator does not model". A row so labelled could therefore never fire for a restricted card, in any format, ever. The shipped label is **"Banned cards"**, which matches what the row reports and what the backend's own unanswerable sentence says ("…so banned cards could not be checked") |
| Agent views nav | P0 | Deck header, right | One pill per agent view; unread marker; re-opens a dismissed view |
| Agent view — Suggestions | P0 | `companion_show_suggestions(payload)` | Suggestion list: card + one-line reason + optional category |
| Agent view — Card groups | P1 | `companion_show_groups(payload)` (FR-23) | Titled groups of cards with a rationale paragraph each; groups may include cards **not** in the active deck |
| Agent view — Swaps | P1 | `companion_show_swaps(payload)` | Out-card / in-card pairs with rationale and metrics |
| Agent view — Tier list | P1 | `companion_show_tier_list(payload)` | S/A/B/C/D buckets of cards with notes |
| Connection pill | P1 | Always visible, bottom-left | Backend reachable / WebSocket live + active deck name |
| No-active-deck state | P0 | Before first `companion_set_active_deck`; after backend restart; deck deleted | Lists available decks; points to the agent |
| "Database not initialized" state | P0 | Fresh install, SQLite DB missing | Guidance, never an error page |
| "Database updating" state | P0 | Transient read failures during bulk refresh | Calm wait state |
| Disconnected / backend-gone state | P0 | WS retries exhausted / backend unreachable | Terminal / relaunch-URL guidance |
| Footer attribution | P0 | Pinned to window bottom | Scryfall attribution + WotC Fan Content Policy notice (NFR-08) |
| Deck power panel | P2 | Future `assess_deck_power` push | 7-dimension vector + bracket visual (Phase 3; out of this spine's spec) |

Overlay stack is **one level deep**: an agent view covers the window; nothing opens over it. The card detail panel is a persistent column, not a modal, so it neither stacks nor traps.

**Two surfaces from the previous draft are gone by design:** the *view toggle* and the *text list view as an alternate mode*. Grid and text list are now simultaneously visible in the two columns, which resolves the previous gate's one high finding by deletion rather than by specification.

## Voice and Tone

Calm, second-person, terminal-literate. The user lives in a terminal; the app may name commands and tools without apology. Never blame ("something went wrong" is banned); always give the concrete next action. No exclamation marks, no emoji, no mascot.

Second person is the contract. The design-system readme's "second person absent" note is superseded — panels label, but guidance addresses the user.

| State | Copy |
|---|---|
| No-active-deck | Headline: "No deck on the glass." Body: "Ask your agent to set an active deck — it will appear here the moment it does." Below: the available-deck list from `GET /api/decks` (names only, non-clickable — the agent drives). |
| Database not initialized | Headline: "Card database not set up yet." Body: "In your agent session, ask it to initialize the database (`initialize_database`). First build takes a few minutes — this page will come alive on its own when it's ready." |
| Database updating | Headline: "Card database is updating." Body: "Reads will resume automatically — nothing to do here." |
| Database updating, stalled | Headline: "Card database still updating." Body: "Reads haven't resumed for a while. Check your agent session — if no import is running, ask it to rebuild the database (`initialize_database`)." The escalation from the row above; the client decides when "a while" has passed (c3-9 owns the threshold). |
| Disconnected / backend restarted | Headline: "Lost the companion backend." Body: "Check your terminal. If the backend restarted, it printed a fresh URL — open that. If it moved ports, this tab can't follow it automatically." Retrying-quietly note in the connection pill. |
| Internal error | Headline: "The companion hit a bug." Body: "Restart the companion in your terminal (`artificial-planeswalker companion`). The traceback is in that terminal — it's what a bug report needs." Deterministic: this state never retries itself. |
| Unknown card in a view | Placeholder label: "Unknown card" + truncated ID. No banner, no apology — the rest of the view renders normally. |
| Empty active deck (0 cards) | Deck name and header render normally. In-grid line: "This deck is empty — ask your agent to add cards." No panel, no error styling. Curve, color distribution and format check panels are hidden until the deck has cards. |
| Empty push | In-view: "The agent sent an empty {kind}. Nothing to show — ask it for another pass." |
| Image loading | No copy. Wells stay silent. |
| Nav pill, no push yet this session | Pill renders disabled-quiet (`text-tertiary`, no hover glow), tooltip "Your agent hasn't sent this yet." |

## Component Patterns

Behavioral. Visual specs live in `DESIGN.md` Components under the same names.

**Presentation-only primitives.** Five components in `DESIGN.md` — Panel, Badge, StatChip, Group header, and ManaPip/ManaCost — have no row below and no behavior of their own: they render what they are given, respond to nothing, and hold no state. Their visual spec is their whole contract. This is deliberate, not an omission.

| Component | Use | Behavioral rules |
|---|---|---|
| Card tile | Deck grid, agent-view tile rows | Hover **or keyboard focus** sets the inspection target — the card detail panel updates in place. Click **pins** the inspection (see Card detail panel). Hover pop is presentation only; it never changes hit targets. Tiles are focusable and sit in the Tab order in visual order. |
| DFC flip control | Double-faced cards only (FR-19) | Its own click target with a ≥32px hit area, `stopPropagation` from the tile: a click **only** flips (front ⇄ back via the image endpoint's `face` parameter) and never sets, pins or clears the inspection. Sits in the Tab order **immediately after its own tile** — never as a trailing group divorced from the cards. Enter/Space flips. Flip state is keyed by Scryfall printing UUID and **persists across `deck_changed` re-renders** (a snap-back reads as a bug); it is per-tab, in-memory, and resets on refresh. A flipped tile is flipped everywhere it appears — grid, agent-view thumbnail, and the detail panel — because the state is keyed by printing, not by location. While a DFC tile is showing its back face, hovering or pinning it targets **that face**: the detail panel shows the back, its name, and its oracle text. Rendered only where per-face `image_uris` exist (FR-04): split, adventure and flip layouts serve a single image and get no control. |
| Quantity badge | Card tiles | Displays "×N" from decklist quantities. On refetch, a changed quantity flashes the accent glow once — garnish; the accessible signals are the group-header count text and the coalesced live-region announcement. |
| Card detail panel | Right column, always present | Shows the **inspection target**. Two modes: *transient* — hover/focus over any card tile, thumbnail or deck row updates it live; and *pinned* — a click (or Enter) fixes the target, marks the panel with `{components.card-detail.pinned-ring}`, and hover no longer overrides it. Click the same card again, press Esc, or click the panel's unpin control to release. On cold open the target is the first card of the first type group; the panel is never empty while a deck is loaded. Content hydrates from `GET /api/cards/{card_id}` + `GET /api/card-image/{scryfall_id}?size=large`; name and cost are known at hover time and render immediately, the rest fills in place — no spinner. Prices render only when present in local data. |
| Deck row | Deck list panel | Same inspection contract as a Card tile: hover/focus sets, click pins. Rows are focusable. DFC rows show the front face's name and cost. Unknown or imageless cards render identically here — the list is text-first. |
| Agent views nav | Deck header | One pill per view kind. A pill is quiet until its kind has received a push this session; thereafter it is active and shows the last push's time. A pill whose view has an **unread** push carries the accent unread dot until that view is opened. Click (or Enter) opens that view. Pills are the *re-open* path, never the only path — see the arrival ruling below. |
| Agent view | All agent pushes | A push arrives → its view **opens automatically** over `{components.agent-view.enter}` `[RULING 2026-07-25 — see Rulings]`. A push of the **same kind** while that view is open replaces the content in place with a brief crossfade over `{components.motion.glide}` (FR-08 replace semantics). A push of a **different kind** while a view is open switches to the new kind and marks the previous pill unread — a push is never silently swallowed (SC-1). Dismiss: the "Close · esc" pill, Esc, or a click on the scrim outside the shell. Dismissal never clears content — the view is re-openable from its pill for the rest of the session. Focus: on open, focus moves to the view's heading; on in-place replacement, focus moves to the heading (whose `aria-live` region announces the new push); on dismiss, focus returns to the element focused before the view took it. The view **is** modal — Tab cycles within it while open. |
| Suggestion row | Suggestions view | Card thumbnail + action badge + name + one-line reason + optional category chip. Hover/focus/click follow the standard inspection contract; the pinned target survives closing the view, so dismissing a suggestion view leaves that card in the detail panel. Unknown-ID entries render the Card placeholder unknown variant in the thumbnail slot; the row still renders its reason text. |
| Swap row | Swaps view (P1) | Out/in pair + rationale + metric chips. Either tile follows the inspection contract. Tints appear on the labels per `DESIGN.md` — never on art. A swap whose "in" card has 0 copies available renders normally with its count label reading "0 copies"; the rationale carries the explanation. |
| Tier row | Tier-list view (P1) | S/A/B/C/D buckets in payload order; empty buckets are skipped, not rendered as empty shells. Tiles follow the inspection contract; the note renders under the row. The tier letter is always accompanied by its name in text — color never carries rank alone. |
| Group section | Card-groups view (P1, FR-23) | Title + count + rationale paragraph + tile row. Tiles follow the inspection contract. Groups routinely contain cards the deck does not run (budget substitutes, sideboard options, answers not yet included), so a tile here carries **no quantity badge** unless the card is in the active deck — the badge means "copies in this deck", and rendering "×0" would be a lie. Empty groups are skipped. |
| Mana curve | Left column | Recomputed from the decklist on every refetch; buckets 1–7+; lands excluded; DFCs bucket by front face. Bars are display-only (no click). Each bar exposes an accessible name carrying its count ("3 drops: 8 cards"), and the curve as a whole is backed by a visually-hidden table for screen readers. If bars are stacked by color, multicolor cards bucket into one `mana-gold` segment and the painted segments are `aria-hidden` decoration. Height transitions animate; under reduced motion they jump. |
| Color distribution | Left column | Segments proportional to pip count across the deck's colors. The bar is `aria-hidden`; the legend beneath (pip + count + percentage) is the accessible data path, so color is never the sole carrier. |
| Format check | Right column | One row per check from local validation. Tone maps: pass → positive, advisory → caution, violation → negative. Rows are display-only. |
| Connection pill | Always visible (P1) | States: live (WS open) · reconnecting (backoff in progress) · backend gone (retries exhausted → the Disconnected state panel takes the main surface). The pill text names the state — the dot color never carries it alone, and the dot never animates. Also shows the active deck name. The pill is focusable; hover **or keyboard focus** reveals port and instance ID from `GET /health` in a tooltip tied to the pill via `aria-describedby`. |
| State panel | All system states | One state panel at a time, centered in the left column area; the right column, nav and footer remain functional around it. Every panel names its next action; none is styled as an error. |
| Card placeholder | Missing art, unknown IDs, CDN failure | Deliberate card-shaped render (name + mana pips + type line) per `DESIGN.md` — never a broken-image glyph. Placeholder tiles behave like normal tiles (inspection contract) except the unknown-card variant, which cannot be inspected — there is nothing to show. |
| Skip link | First Tab stop **wherever it is present** (see the condition at the end of this cell) | "Skip past the deck grid" — visually hidden until keyboard focus (`DESIGN.md` spec). Enter moves focus to the card detail panel heading, i.e. past the grid to the right column. It exists because the grid sits between the header nav and the deck list, connection pill and footer; without it the entire right column is unreachable in practice. **Measured at c4-11 over all 40 real decks: 206 Tab stops max / 78 median / 102.0 mean from the header to the first footer link — not the "100+" this cell used to claim, because c4-7's deck list added a second focusable row per card. The link removes only the first 105, leaving 101; 19 of 40 decks stay >50 from the footer and 36 of 40 stay >20.** The shipped control is a real **`<button>`**, not an `<a href="#…">` (c4-11 Q5; recorded here at the 2026-08-07 code review): no router means a hash would be a navigation the app never reads, and focus must be moved imperatively either way. Present on a loaded deck **with at least one card, on any board including the sideboard** (a sideboard-only deck still renders a corridor of focusable rows — amended at the same review); absent when a State panel occupies the left column, and absent on an **empty deck** — which satisfies neither branch of the original rule and where there is **nothing to skip**: zero tiles and zero rows between the link and the right column. (An earlier form of this cell claimed the link's *target* would not exist on an empty deck; false — `CardDetail` renders its frame and heading unconditionally, and UX-DR20's "first card" fills the panel's *content*, not its heading. Corrected at the c4-11 code review.) ⚠️ This cell's *Use* column previously read "First Tab stop on **every** surface", contradicting its own body one sentence later; corrected at c4-11 (Q3). |
| Footer attribution | Every surface (NFR-08) | Static. Scryfall + WotC Fan Content Policy lines always visible; links persistently underlined (identifiable at rest) and open in a new tab. |

**Deck view refetch** — on `deck_changed` matching the active deck (and on WS reconnect), refetch `GET /api/deck/{id}`. During refetch the current deck stays on screen with a subtle shimmer on the deck header — never a blank or skeleton teardown of a populated view. Refetch racing a second mutation: latest-wins — coalesce to one in-flight request, cancel-and-restart on a newer event. A 404 on refetch (deck deleted) clears to the No-active-deck state. A pinned inspection target that survives the refetch stays pinned; one that no longer exists in the deck falls back to transient with the first card of the first group.

**Placeholder-then-fill imagery** — render layout immediately with cached art where available and silent image wells elsewhere; images fade in over `{components.motion.pulse}` as they arrive. Layout never reflows on image arrival (fixed 63:88 slots). **All card imagery is routed through the backend proxy** (`GET /api/card-image/{scryfall_id}`) with caching, negative-caching on failure and a placeholder response — never hotlinked from the Scryfall API.

## State Patterns

| State | Surface | Treatment |
|---|---|---|
| Cold open, backend live, deck set | Deck view | Layout within 1 s (NFR-05): header, grid, curve, color distribution, deck list and format check render from deck data; art fills placeholder-then-fill. Detail panel targets the first card. |
| Cold open, no active deck | Left column | No-active-deck State panel + available-deck list. Right column panels hidden; nav pills quiet; footer and connection pill remain. |
| Empty active deck (0 cards) | Deck view | Deck header + name render normally; the grid area shows the calm in-grid line (Voice and Tone) in `{typography.body}` `{colors.text-secondary}`; curve, color distribution and format check panels hidden until the deck has cards. |
| Fresh install, DB missing | Left column | "Database not initialized" State panel (FR-22). Backend polls; when the DB appears the app transitions on its own — no manual refresh required. |
| Bulk data refresh | Any read failing transiently | "Database updating" State panel replaces only the failing surface; retry silently on backoff until reads succeed (NFR-02). |
| Deck refetch in flight | Deck view | Current content + header shimmer; no blank. Latest-wins on races. |
| WS live | Connection pill | Positive dot; no other chrome. |
| WS reconnecting | Connection pill | Caution dot (static — no pulse; pill text names the state); exponential backoff; on reconnect, re-mint the ticket via `GET /api/session` and refetch the active deck (NFR-04). Deck content stays rendered (possibly stale) during reconnection. |
| Backend gone (retries exhausted) | Left column + pill | Disconnected State panel with terminal / relaunch-URL guidance; pill shows negative dot. If the backend restarted, active deck is gone with it — a successful reconnect lands on No-active-deck (FR-07). |
| Deck deleted | Deck view | Refetch 404 → No-active-deck state (FR-11). |
| A state panel takes the left column while an agent view is open | Agent view + left column | The view stays open and stays valid — agent content is about cards, not about the deck's presence, so a lost deck does not invalidate a tier list. On close, the user lands on the state panel. The skip link and the grid's Tab stops are withdrawn while the grid is gone. |
| Deck refetch completes while an agent view is open | Agent view | The view is untouched; the deck view updates behind it. The pin, if any, survives (see refetch rules). No announcement fires from behind a modal. |
| Push arrives while a view is open, same kind | Agent view | Content replaces in place with a crossfade (FR-08); focus moves to the heading; `aria-live` announces. |
| Push arrives while a view is open, different kind | Agent view | View switches to the new kind; the previous kind's pill is marked unread. |
| Push arrives while no view is open | Agent view | The view opens (see arrival ruling). |
| Unknown card in a push | Agent view | Unknown-card placeholder for that entry only; the push never fails wholesale (FR-13). |
| Card with no image data | Any surface | Named Card placeholder (FR-19). |
| CDN fetch failure | Any image | Backend serves the placeholder response (FR-04); UI renders the named Card placeholder; negative-cached with backoff — no request storms, no per-image retry UI. |
| Empty push | Agent view | The view opens and renders the deliberate empty state (Voice and Tone) rather than rejecting (confirmed ruling 2026-07-22 — keeps FR-12's never-hard-error posture symmetric in the UI). |
| Nav pill before its first push | Deck header | Quiet/disabled with explanatory tooltip; not focusable. |
| Cross-tab | All | Every open tab receives every push and every `deck_changed` (FR-06 broadcast); view state and unread markers are per-tab; no cross-tab sync or leader election [ASSUMPTION — addendum-delegated ruling; divergent state between tabs is accepted]. |
| Stale/corrupt discovery file | (tool-side) | Agent-side text outcome ("app not running"); no UI surface — listed for completeness. |

## Interaction Primitives

Mouse-first tool; the keyboard gets a floor, not a surface.

- **Hover** — sets the inspection target (tiles, thumbnails, deck rows); nav pill and connection pill affordances. **Hover is never the only way to reach information** — every hover behavior has focus parity.
- **Click** — inspect and navigate only: pin/unpin an inspection, open an agent view, dismiss a view, reveal pill detail. Nothing on the glass mutates the deck.
- **Esc** — closes the topmost thing: an open agent view first, then an active pin. Never navigates or clears deck state.
- **Tab / Shift-Tab** — traverses every interactive element in reading order. **The enumeration below is the order the shipped DOM produces (corrected at c4-11, Q2); unbuilt stops are marked rather than listed as if they existed:** skip link → *(deck header nav pills — **c6-8**, and non-focusable until their kind has received a push, so absent on a cold-open session)* → card tiles in visual order, **each DFC's flip control immediately after its own tile** → **card detail: the unpin control (while pinned), the panel's own flip control (when the target is flippable), the oracle scroller** → deck-row list → *(connection pill — **c5-7**; its DOM position is that story's to decide, and `DESIGN.md:445` places it bottom-left, in the other column from the deck rows)* → footer links. While an agent view is open, Tab cycles inside it only (focus trap). ⚠️ The previous version named three stops that could not exist and omitted four that already shipped.

  **Arrow-key grid navigation is deferred out of MVP [DEFERRED 2026-07-25 — gate H3].** The consequence is stated rather than hidden, and **measured at c4-11 over all 40 real decks rather than estimated: the corridor from the header to the first footer link is 206 Tab stops on the largest deck, median 78, mean 102.0** — the earlier "100+" figure predates **c4-7**, whose deck list turned every card into a *second* focusable row in the very column the skip link jumps into. **The skip link removes only the first 105 of the 206: after using it the footer is still 101 stops away, 19 of 40 decks stay more than 50 stops from it and 36 of 40 stay more than 20.** It is the only way past the grid, and it is a partial one. That is a real cost borne by keyboard-only users, accepted for MVP on the product's mouse-first posture (PRD §3, Interaction Primitives). The mitigation is the skip link; the fix, when it comes, is to make the grid a single composite Tab stop with arrow-key traversal inside it. **Revisit before public release**, since the footer's Fan Content Policy links sit behind the grid in the Tab order.
- **Enter / Space** — activates the focused element: card tile / deck row / thumbnail → pin the inspection; nav pill → open that view; "Close · esc" → close; footer link → open in new tab.
- **Focus management** — view open → focus to the view heading; in-place push replacement → focus to the heading; view close → focus returns to the previously focused element (the nav pill, if the pill opened it). Focus is never dropped to `document.body`.
- **Focus-visible** — `{components.focus-ring}` (2px `accent-bright`, 2px offset) on every focusable element, keyboard-triggered only. Every interactive element is a real `<button>` or `<a>` — never a `<div>` with a click handler.
- **Banned:** drag-and-drop, right-click menus, double-click semantics, hover-only disclosures of unique information, any control that edits the deck.

## Accessibility Floor

- **Contrast** — all body text on dark surfaces ≥ 4.5:1; large text (≥ 18.66px bold / 24px) ≥ 3:1; non-text indicators ≥ 3:1. Verified pairs live in `DESIGN.md` Colors. Two constraints from that table are behavioral: `text-tertiary` on `surface-overlay` is the tightest pair at 4.8:1 with no headroom, and **`accent-dim` is banned on `surface-overlay`** (2.70:1) — live/selected markers on overlay-backed rows use `accent`.
- **`prefers-reduced-motion`** — exhaustive inventory, each motion with its fallback: agent-view bloom (fade + rise) → appears in place; push-replace crossfade → instant content swap; card-tile hover pop → no scale, shadow only; image fade-in → instant appearance; curve bar height animation → instant jump; deck-row live tint transition → instant; accent glow fade → glow omitted (the count text and live-region announcement carry the signal); refetch header shimmer → static "Updating…" text in `{typography.micro}` `{colors.text-secondary}`; **DFC flip 3D Y-rotation → instant face swap**; **card detail panel content swap on a changed inspection target → instant, no crossfade** (it changes on every hover, so it must never animate). No element pulses or loops under any setting. Any motion added later must be added to this list with a fallback.
- **Motion is never the sole signal** — a deck change updates the group-header counts and fires the coalesced live-region announcement; the quantity-badge glow is garnish on top. A new push updates the view heading, its timestamp, and the nav pill's unread marker.
- **Semantic structure** — deck name = `h1`; panel titles and type-group headers = `h2`; agent view = `role="dialog" aria-modal="true"` labeled by its heading (`h2`); card grid, deck list and agent-view lists = `ul`/`li`; state panel = `role="region"` with its headline as `h2`; footer = `<footer>` (`contentinfo`); mana curve and color distribution = `figure`s whose accessible alternatives are the visually-hidden table and the legend respectively. The card detail panel = `role="region"` labeled "Card detail". **It is not a live region.** Transient (hover/focus) target changes must not announce — sweeping a cursor or arrowing across a 60-card grid would otherwise fire one polite announcement per card and flood the queue. Only a **pin** announces, once, via a separate polite region: "Pinned — Adeline, Resplendent Cathar." Keyboard users reach the same content by focusing a tile and pressing Enter.
- **Hit targets** — every interactive element has a ≥ 24×24px hit box (padding counts): nav pills, the close pill, footer links, deck rows, the connection pill.
- **Focus-visible always** — no `outline: none` without the `{components.focus-ring}` replacement.
- **Alt text** — every card image's alt is the card name (face-specific for DFCs). Placeholders expose the same name to assistive tech. Thumbnails in rows that already show the card name as text (suggestion, swap, tier rows) use `alt=""` — the name is announced once, from the row text; grid tiles and the detail panel keep name alt because there the image is the only carrier.
- **Live regions** — the connection pill, the agent-view heading, and the pin announcement region announce changes via `aria-live="polite"`. The card detail panel itself is *not* live (see Semantic structure). Deck refetches announce **once per coalesced refetch**, on completion: "Deck updated — 62 cards" — the refetch-coalescing machinery is the debounce, so a burst of `deck_changed` events yields exactly one announcement.

## Latency & Freshness Contract

NFR-04/NFR-05 rendered as UX rules:

- **250 ms push-to-render** — a push must reach painted view layout within 250 ms of tool-call completion (SC-1). "Rendered" = view layout + text + cached-or-placeholder art; first-fetch image paint is excluded. **The clock stops at first paint of the laid-out content, not at animation settle** — the agent view's `{components.motion.bloom}` entry (480 ms) runs *on top of* an already-complete layout, so the entry animation is never inside the budget. Under `prefers-reduced-motion` the two coincide. Consequence: the view never blocks on image fetches, and hydration calls happen concurrently with the open animation.
- **1 s deck render** — a 100-card Commander deck reaches full layout within 1 s warm-cache (SC-2/NFR-05).
- **Skeleton vs. placeholder policy** — skeletons (shimmer) are only for *populated surfaces awaiting a refresh* (deck header shimmer during refetch). Placeholders (silent wells, named cards) are for *content whose identity is known but whose art isn't*. The same rule extends to detail-panel text: fields known at hover time render immediately; hydrated fields fill in place, no spinner. Blank screens are never shown after first paint.
- **Refetch coalescing** — one in-flight deck fetch at a time; newer `deck_changed` cancels and restarts; last response wins; out-of-order responses discarded.
- **Freshness posture** — "something changed, refetch" (no diffs/patches). Reconnect always refetches the active deck. Staleness from a swallowed event POST is accepted until FR-16 (Phase 3) — the UI shows no staleness warning.

## Inspiration & Anti-patterns

- **Lifted from MTG Arena:** the hand-hover card pop (in-place scale + lift, neighbors undisturbed); art-forward density.
- **Lifted from Untapped.gg:** the dark data-companion posture — a game-adjacent tool that sits beside play without pretending to be the game. The redesign leans further into this than the previous draft did: curve, color distribution, format check and deck value are now permanent surfaces rather than a docked summary.
- **Rejected — WotC trade dress:** no Beleren-like type, card-frame chrome, or symbol lookalikes anywhere. Non-negotiable for a public release under the Fan Content Policy.
- **Rejected — debug dashboard:** no raw JSON views, no log panes, no dense tables of IDs. SC-5 is the gate. Note the tension the redesign introduces: with four analytical panels always on screen, "deliberate product, not debug dashboard" is now carried by typography, spacing and restraint rather than by sparseness.
- **Rejected — interactive deckbuilding UI:** no drag-to-add, no buy buttons, no editing. The moment the glass grows write affordances, the product premise collapses.

## Key Flows

### Flow 1 — UJ-1 — Brewing session (Brad, tuning a brew)

1. Brad starts the backend once (`uv run artificial-planeswalker companion`), opens `localhost:8765`, snaps the browser beside his terminal.
2. He asks the agent to load the deck → agent calls `companion_set_active_deck` → the deck view fills: grid on the left, curve and color distribution beneath, detail/list/format-check on the right — full layout within 1 s (SC-2/NFR-05).
3. He runs his eye over the grid; the detail panel tracks his cursor, so reading the deck is one continuous motion with no clicks.
4. He asks: "what would make the token engine more resilient?"
5. The agent calls `companion_show_suggestions` → the Suggestions view blooms open within 250 ms of tool-call completion (SC-1): six cards, art-forward, each with a one-line reason.
6. He hovers down the list, reading each card in the detail panel behind the pattern he already knows. He clicks one to pin it, then presses Esc to dismiss the view — the pinned card is still in the detail panel.
7. He decides against two others — no clicks needed; he just tells the agent.
8. He tells the agent to add the one he liked.
9. **Climax:** the mutation lands, `deck_changed` fires, and the deck view **updates by itself within a second** — the new card appears in its type group, the curve bar for its mana value grows, the color distribution shifts, its quantity badge flashes. Brad never touched the app. The loop closes: agent drives, glass shows.

Failure paths: a suggestion references an ID not in the local DB → that row renders the unknown-card placeholder, the other five render normally (FR-13). The event POST fails after the mutation persists → the deck view is stale until the next event or reconnect; no error surfaces (accepted staleness window).

### Flow 2 — Cold start (Brad, fresh install on a new machine)

1. Brad installs the package and runs the single command: `uv run artificial-planeswalker companion` (SC-4 — no config, no Node).
2. The backend starts despite the missing SQLite DB (FR-22) and prints the URL; Brad opens it.
3. **The app greets him with the "Database not initialized" State panel** — headline, guidance naming `initialize_database`, no error styling. The nav pills are quiet; the footer attribution is already there.
4. In his terminal session he asks the agent to initialize the database; the build runs for a few minutes. The page waits calmly — no spinner theatrics.
5. The DB lands → the app transitions on its own to the No-active-deck state, listing his decks.
6. He asks the agent to import and set a deck → the deck view fills.
7. **Climax:** from `pip`-fresh machine to full card art on the glass without touching a config file or seeing a single error page.

Failure path: he opens the browser before running the backend → nothing at `localhost:8765`; the terminal command's output is the recovery path. Backend restarts mid-session onto a new port → the tab exhausts reconnect backoff and shows the Disconnected panel pointing him at the terminal's fresh URL.

### Flow 3 — Revisiting a push (Brad, mid-session)

1. Two pushes ago the agent sent a tier list; Brad dismissed it to look at the grid.
2. The Tier list pill in the header is active and shows its timestamp.
3. He clicks it → the view re-opens with the same content, re-hydrated against current card data (stale IDs degrade to unknown-card placeholders).
4. He closes it. The pill stays active. Nothing was lost, and nothing was re-requested from the agent.

## Rulings introduced by the redesign

Four decisions this revision had to commit because the as-built design left them open. Each is tagged in place. **These want Brad's confirmation before the spine is treated as settled.**

1. **`[RULING 2026-07-25]` A push opens its agent view automatically.** The as-built design has no other push affordance — no drawer, no notification — so without this the PRD's SC-1 (250 ms push-to-render) is unobservable and UJ-1's climax has no surface. The nav pills therefore become the *re-open/switch* path rather than the primary one, and carry an unread marker. **Alternative if rejected:** a push only lights its pill, and SC-1 needs restating as time-to-pill rather than time-to-render.
2. **`[RULING 2026-07-25]` Inspection is hover-transient plus click-to-pin.** The mock is hover-only, which the accessibility floor bans (hover-only disclosure) and which gives keyboard users no route to the detail panel. Pinning also makes the panel survive closing an agent view, which is what makes step 6 of Flow 1 work.
3. **`[RULING 2026-07-25]` The detail panel is not a modal.** It is a persistent region, so it needs no focus trap and no return-focus contract — only the agent view is modal. This simplifies the keyboard floor considerably versus the previous draft.
4. **`[RULING 2026-07-25]` Tier D is part of the vocabulary.** The design added it; the tool payload contract should be S/A/B/C/D, and empty buckets are skipped.

## Residuals — carried forward, not yet designed

Specs the previous draft carried that the Voltglass design does not yet answer. Listed so they are not lost by omission:

- **Session history strip** (FR-18, P1). The previous draft docked it at the agent drawer's foot; with no drawer, the nav pill's last-push timestamp is a partial substitute that covers "re-open the latest of each kind" but not "the last ~20 pushes". Needs a decision: extend the nav, or add a strip inside each view's header.
*(The skip link was briefly listed here as a residual; the 2026-07-25 gate found the Tab order already depended on it, so it is specified in both spines rather than deferred.)*
