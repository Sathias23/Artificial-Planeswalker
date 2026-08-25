---
title: 'Story 17.2: Session history'
type: 'feature'
created: '2026-08-22'
status: 'done'
baseline_revision: '5972b79982f30beabc5a0273e91d4402e998f7c3'
review_loop_iteration: 0
followup_review_recommended: true
context: []
warnings: ['oversized']
deferred: []
---

<intent-contract>

## Intent

**Problem:** Brad can only revisit the *latest* push of each kind — anything older is gone the moment a newer push of the same kind lands (FR-18). The retention store keeps one slot per kind.

**Approach:** Widen the existing retention store from "latest per kind" to "last 20 pushes overall", and surface it as the ruled FR-18 home (2026-08-22): a fifth "History" nav pill after the four kind pills that toggles a **non-modal popover** listing the session's pushes newest-first; activating an entry closes the popover, then opens that push's agent view through the existing `openAgentView` path.

## Boundaries & Constraints

**Always:**
- All history writes stay inside `ui/src/state/agentView.ts` (one-writer rule); the append happens inside `openAgentView`'s single existing `setState`. Capacity 20; at the cap the oldest entry drops silently. Per-tab, in-memory, clears on refresh — no persistence of any kind.
- Entries are ordered newest-first by envelope `ts` — **never by `id`** (`id` is opaque identity/dedupe only). Unparseable `ts` falls back to arrival position (a malformed `ts` must never silently reorder the list); record this ruling in a code comment. If an arriving push carries an `id` already in history, replace that entry in place (id = identity) rather than duplicating.
- The pill is `components.nav-pill` verbatim (reuse `.agent-views-nav-pill`) plus a stroke-based clock glyph — a plain UI glyph, never anything set-symbol-shaped. It **never carries an unread dot**. Quiet/disabled until the first push of **any** kind this session, using the kind pills' exact quiet pattern (disabled + `title` tooltip + `aria-describedby` visually-hidden sibling outside the button) with its own copy string authored in `copy.ts`: `Nothing to revisit yet — your agent hasn't sent anything this session.`
- The pill is a real `<button aria-expanded aria-haspopup>` toggle — the app's first disclosure control. The popover is **not** a modal, landmark, or live region: no scrim, no focus trap, no roving focus, no `aria-live`, open/close announce nothing; a push arriving while it is open simply appears at the top, unannounced.
- Popover and agent-view modal never coexist: entry activation closes the popover **first**, then opens the view; a push auto-opening its view also closes the popover first. The overlay stack stays one level deep.
- Entries are real `<button>`s (kind label + push title when present + time) with ≥24×24 px hit areas, standard focus ring, ordinary document-order Tab stops withdrawn on dismiss. Reopening never re-requests anything from the agent; content re-hydrates through the existing view mount path (stale printing UUIDs already degrade to unknown-card placeholders there).
- Focus contract: popover open → focus to the first (newest) entry; popover close → focus returns to the History pill; focus is never dropped to `document.body`. Dismiss: entry activation, Esc, outside click, or toggling the pill. Esc order is view → popover → pin: the popover's Esc is a document-level **bubble**-phase keydown (the modal's capture listener pre-empts it), registered in the keyboard-floor listener census with a written reason. Outside-click uses native document pointer listeners per the `AgentView` scrim convention.
- Visuals per DESIGN.md `{components.history-popover}` (surface-overlay, hairline border, `--radius-md`, glow shadow, `max-height: 480px` with the documented-literal citation, entry type roles incl. tabular `{typography.numeric}` time in `text-tertiary`). Enter is an **opacity-only fade** over the glide motion tokens — no rise, no transform, no new motion-inventory entry.
- Anchoring: `position: relative` wrapper inside `AgentViewsNav`'s own markup; the popover must not trip the full-window-fixed-layer detector. **Do not edit `AppShell.tsx`** (c2-9 displacement ruling).
- Guard registrations ship in the same commit: `shell.test.ts` CONTAINERS entries for every new module, copy↔artefact gate rows, `DECLARES_MIN`/`WELL_CLEAR` for the entry class, listener-census entries, store-writes `why` update, `App.test.tsx` corridor-pin recomputation, EXPERIENCE/DESIGN amendments if any wording is touched.

**Block If:** an EXPERIENCE.md `[ASSUMPTION]` sub-treatment proves unimplementable while keeping an existing pin green (e.g. focus-return vs. the corridor pins), or keeping `retained` and `history` consistent forces a second writer or a derived-array selector that breaks zustand referential-equality discipline.

**Never:** No backend or wire changes (the envelope already carries `id`+`ts`); no touching `socket.ts`/`connection.ts`; no new store; no keying the History pill off `AgentViewKind` (keep `PILL_ORDER` pure); no `localStorage`/`sessionStorage`/cross-tab sync; no per-view header strip (the un-chosen option); no unread semantics on History; no 17.3 profiling work.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| First push of session | any kind arrives | history `[entry]`; History pill activates (was quiet) | No error expected |
| 21st push | history at cap 20 | oldest drops silently; length stays 20 | No error expected |
| Same-`id` push re-arrives | id already in history | entry replaced in place, no duplicate | No error expected |
| Entry activated | popover open, view closed | popover closes (focus → pill), then that push's view opens via `openAgentView` | No error expected |
| Push arrives, popover open | any kind | new entry at top, unannounced; popover closes; view auto-opens | No error expected |
| Esc, popover open, no view | keydown Escape | popover closes; focus → History pill | No error expected |
| Outside click | pointer down outside popover+pill | popover closes | No error expected |
| Unparseable `ts` | malformed envelope `ts` | entry keeps arrival position; time label omitted (`pushTimeLabel` → null) | Never throws |
| Reopened entry, stale card ids | cards no longer resolve | view renders unknown-card placeholders per entry; revisit never fails wholesale | No error expected |
| Refresh / reset | new tab or `resetAgentView()` | history empty; pill quiet | No error expected |

</intent-contract>

## Code Map

- `ui/src/state/agentView.ts` -- the retention store. `AgentViewState` (`:231-280`): `retained: Partial<Record<AgentViewKind, AgentViewContent>>` (`:262`) is the slot to widen — add `history: readonly AgentViewContent[]` (newest-first). `openAgentView` (`:349-367`) is the **single** `setState` — append/replace-by-id + cap here. `reopenAgentView` (`:403-407`) is the four-line shape to mirror as `reopenPush(id: string)` (find in history → delegate to `openAgentView`). `INITIAL_AGENT_VIEW` (`:283`) — adding the field there makes `resetAgentView` (`:304`) cover it. `AGENT_VIEW_LABELS` (`:108-113`) — pill labels live here, NOT container copy (c6-6). `AgentViewContentBase` (`:145-164`): `id` = replace key, `ts` = raw ISO **string**. Selector hooks are primitive-narrowed (`:636-641` argument): new hooks must be `useAgentViewHistory()` returning the **stored array reference** (rebuilt only inside `openAgentView`) plus a primitive `useAgentViewHistoryCount()` for the pill's quiet bit.
- `ui/src/state/agentView.test.ts` -- colocated store tests; extend for cap/order/replace/reset rows.
- `ui/src/containers/AgentViewsNav/AgentViewsNav.tsx` -- `AgentViewsNav()` (`:67-87`) maps `PILL_ORDER` (`:107`) inside `.agent-views-nav-pills`; History pill renders after the map as a module-local component mirroring `AgentViewPill` (`:139-229`). Quiet pattern `:152-179`: `disabled` + `title` + `aria-describedby` → visually-hidden `<span>` sibling **outside** the button, `useId()` for the id. No `onKeyDown` on pills (`:130-137`).
- `ui/src/containers/AgentViewsNav/copy.ts` -- copy owner (already in `COPY_MODULES`); `imports: []` is load-bearing. Add the quiet-tooltip string, pill label "History", any popover heading-less entry copy.
- `ui/src/containers/AgentViewsNav/pushTime.ts` -- `pushTimeLabel(ts): string | null` (`:53-56`) — reuse verbatim for entry times; never assert formatted bytes in tests (host TZ/ICU).
- `ui/src/containers/AgentViewsNav/AgentViewsNav.css` -- class conventions `.agent-views-nav-*`; pill declares 24px mins (`:76-77`); header comment (`:17-22`) says no transition in this file — the popover fade either amends that header with the story citation or lives in a new registered stylesheet. `.agent-views-nav-time` deliberately lacks tabular numerals (`:157-160`) but DESIGN.md wants `{typography.numeric}` for **entry** time — `font-variant-numeric` may only be `var(--type-numeric-features)` per stylelint.
- `ui/src/containers/AgentView/AgentView.tsx` -- precedents: document Esc capture listener (`:344-359`, stops propagation — pre-empts the popover's bubble listener while a view is open); native-listener outside-interaction pattern (`:406-479`); `FOCUSABLE_SELECTOR` (`:108-115`).
- `ui/src/App.tsx` -- `nav={<AgentViewsNav />}` (`:731`); overlay mount `:748-787`; `useOpenAgentView` (`:189`). No changes expected beyond none — history opens views through the store.
- `ui/src/api/schema.ts` -- `AgentEvent` (`:253`), `AgentViewKind` (`:289`); wire untouched.
- `ui/tests/keyboard-floor.test.ts` -- listener census `DOCUMENT_KEY_LISTENERS` (`:713-730`, currently 3 entries; add popover Esc with `{entry, capture:false}` + reason); `DECLARES_MIN` (`:501-507`) for the entry class; tabindex ban (`:788-830` — quiet pill uses `disabled`, never `tabindex="-1"`).
- `ui/tests/shell.test.ts` -- CONTAINERS exhaustive-import registry (`:1516-1568`, nav entries `:1738-1763`) — register every new module; full-window fixed-layer detector (`:975-981`) — popover must be content-sized/absolute; geometry-literal citation rule (`:994-1044`) for `max-height: 480px`.
- `ui/tests/agent-views-nav-copy.test.ts` -- copy↔artefact gate skeleton (labels gate `:177-189`, DESIGN token-name assertions `:192-208`); extend (or sibling file on the 17.1 `connection-pill-copy` pattern, `ROW_LABEL` filter) for rows `History pill + popover` and `History pill before the first push`.
- `ui/tests/copy-rules.test.ts:131` -- `COPY_MODULES`; nav copy.ts already a member — no new entry needed unless a new copy file is added.
- `ui/tests/store-writes.test.ts:109-128` -- `useAgentViewStore` writer table; update the `why` string for the widened slice.
- `ui/src/App.test.tsx` -- corridor Tab-stop pins (`:1815-1830`, `:1900-1903`) move when the active History pill adds a stop — recompute from the DOM, don't hand-derive; live-region census (`:2105-2138`) — popover adds none; composed seams (push → pill → reopen → focus) get a new `describe` near `:5986`, reusing `bootedDeck()`/`push()`/`escape()` helpers (`:6000-6031`); `USER_EVENT_TYPES` (`:4777-4790`) before choosing the outside-click event type.
- `ui/tests/token-usage.test.ts` -- motion inventory: opacity is already a permitted transition property (`:2865`); no new `tokens.css` registration needed for an opacity-only fade; any transform would require one — don't.
- `ui/.stylelintrc.json` -- spacing/radius/shadow/type/motion token rules; per-file widenings go in `overrides` (TierListView precedent) only if genuinely needed.
- `_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/DESIGN.md:309-338` + `EXPERIENCE.md` (IA `:43`, Component Patterns `History pill + popover`, State Patterns `:134-135`, Interaction Primitives `:145-150`) -- the ruled authorities; `[ASSUMPTION]` sub-treatments are drafted-pending-confirmation — implement them as written; if implementation confirms them, strike the `[ASSUMPTION]` tags in the same commit (amendment-with-story precedent).

## Tasks & Acceptance

**Execution:**
- `ui/src/state/agentView.ts` + `agentView.test.ts` -- add `history` field (INITIAL + state), append/replace-by-id/cap-20/ts-order logic inside `openAgentView`'s setState, `reopenPush(id)`, `useAgentViewHistory` + `useAgentViewHistoryCount` -- one writer, referential-equality-safe selectors.
- `ui/src/containers/AgentViewsNav/copy.ts` -- author History pill label, quiet-tooltip string (byte-match EXPERIENCE.md), and popover-entry ancillary copy -- single copy owner.
- `ui/src/containers/AgentViewsNav/AgentViewsNav.tsx` (+ new popover module if split) -- History pill (quiet pattern, `aria-expanded`/`aria-haspopup`, clock glyph) + non-modal popover (entries, focus-to-newest on open, focus-to-pill on close, Esc bubble listener, outside-click pointer listener, close-before-open sequencing incl. on push arrival) -- the ruled FR-18 home.
- `ui/src/containers/AgentViewsNav/AgentViewsNav.css` (or new registered stylesheet) -- popover material per `{components.history-popover}` tokens, opacity-only fade, entry hit areas/focus ring, 480px documented literal -- token discipline.
- `ui/src/containers/AgentViewsNav/AgentViewsNav.test.tsx` -- amend four-pill pins to five; pill quiet/active, aria wiring, popover markup/dismissal/focus unit coverage incl. I/O matrix rows -- container-level seam.
- `ui/src/App.test.tsx` -- composed seam describe (push → history → reopen → focus return; popover-closes-on-push); recompute corridor pins from the DOM -- App owns composition.
- `ui/tests/keyboard-floor.test.ts` + `ui/tests/shell.test.ts` + `ui/tests/store-writes.test.ts` -- census/registry entries (listener, CONTAINERS imports, writer `why`) -- guards ship with the change.
- `ui/tests/agent-views-nav-copy.test.ts` (or sibling gate) -- copy↔EXPERIENCE.md byte gate + DESIGN.md token-name assertions for `history-popover` -- copy-ships-with-artefact precedent.
- `EXPERIENCE.md` / `DESIGN.md` -- strike confirmed `[ASSUMPTION]` tags / record any implementation-forced wording deltas, story-cited -- artefact truth.

**Acceptance Criteria:**
- Given four earlier pushes of mixed kinds, when the History pill is activated, then the popover lists all four newest-first by `ts`, and activating the second entry closes the popover and opens that exact push's view with its retained content.
- Given a session with no pushes, when the nav renders, then the History pill is quiet/disabled with its tooltip + programmatic description, is not focusable, and the Tab corridor matches the recomputed pins.
- Given the popover open, when a push arrives, then the popover closes, the push's view auto-opens (arrival ruling intact), and the new entry is at the top on next open — nothing announced beyond the view's own heading announcement.
- Given the full suite, when run, then every existing pin stays green (accname, live-region census, banner census, motion inventory, posture, store-writes) with only deliberate, story-cited amendments.

## Spec Change Log

- 2026-08-22 (implementation): the "no new motion-inventory entry" clause could not hold beside the M5 completeness gate (`token-usage.test.ts` keys EVERY shipped visual-class transition to a named inventory row in tokens.css — "a new entry owes an inventory row first"). Resolved in the open rather than by claiming the fade under a wrong family row or evading the gate with a `@keyframes` animation: the fade ships with its own row ("History-popover fade -> appears in place", tokens.css) and an `INVENTORY_CLAIMS` entry; the no-new-motion-TOKEN and no-reduced-motion-REGISTRATION halves hold exactly as drafted (opacity-only over `--motion-glide` self-neutralises). EXPERIENCE.md's row and DESIGN.md's block comment carry the story-cited amendment.
- 2026-08-22 (implementation): the popover's styles live in a NEW registered stylesheet (`HistoryPopover.css`, the spec's own "or new registered stylesheet" arm) rather than in `AgentViewsNav.css`, forced by a guard: the popover paints `--surface-overlay`, the pill hover uses `--accent-dim`, and `token-usage.test.ts`'s UX-DR6 rule is FILE-scoped — the two tokens may never share a stylesheet.
- 2026-08-22 (implementation): the Esc layering (view → popover → pin) needed one mechanism beyond the specified document bubble listener: a node-level keydown on the pill+popover WRAPPER (the `AgentView` attach-through-refs pattern; moved from the popover root to the wrapper at review finding 3, so an Esc with focus on the pill is consumed too) that `preventDefault()`s, because CardDetail's always-mounted bubble listener registers FIRST and would otherwise release the pin on the same keystroke. The document bubble listener ships as specified (census entry, written reason) and covers Esc with focus outside the wrapper — where the pin release still co-fires, the accepted residual of entries being ordinary Tab stops, pinned in App.test.tsx and carried in EXPERIENCE.md's Esc bullet (review finding 4).

## Review Triage Log

### 2026-08-22 — Review pass
- intent_gap: 0
- bad_spec: 0
- patch: 13: (high 0, medium 2, low 11)
- defer: 0
- reject: 8: (high 0, medium 0, low 8)
- addressed_findings:
  - `[medium]` `[patch]` Popover could spring back open when a view closed before the rAF that reset the open flag — replaced with a synchronous store-subscription settle (also hardening the focus hand-off to the pill); new fake-timer container test goes red on the old form.
  - `[medium]` `[patch]` Popover had no viewport clamp (`width: max-content`, `left: 0`, fixed 480px max-height) — both axes now clamp viewport-relatively via the documented state-panel literal; entry titles wrap (`overflow-wrap: anywhere`).
  - `[low]` `[patch]` Node-level Esc consumer covered only the popover root — moved to the pill+popover wrapper so Esc on the focused pill no longer co-releases a pin; tests extended (`defaultPrevented` asserted).
  - `[low]` `[patch]` The accepted Esc residual (focus on an unrelated control + active pin → one keystroke closes popover AND pin) was recorded only as a comment — now pinned by an App test and carried as a story-cited caveat in EXPERIENCE.md's Esc bullet.
  - `[low]` `[patch]` `instantOf` sent runtime-null/numeric `ts` through `new Date` (epoch 0 → sorts ancient, bypassing the arrival-position fallback) — `typeof` guard added, store tests cover both shapes.
  - `[low]` `[patch]` The cap arm where the arrival itself is older than all twenty held entries was untested — store test added (arrival absent from history; `content`/`retained` still hold it).
  - `[low]` `[patch]` The enter-fade `data-entering` flip was unasserted (a broken rAF effect would ship an invisible popover green) — bloom-idiom test added mirroring `AgentView.test.tsx`.
  - `[low]` `[patch]` `closePopover`'s wandered-focus guard was mutation-survivable — App test added: outside pointerdown with focus on a card tile leaves focus on the tile.
  - `[low]` `[patch]` The push-arrival focus-settle path was deletable with green tests — AC-3 App test now escapes the auto-opened view and asserts focus returns to the History pill, never body.
  - `[low]` `[patch]` No programmatic pill↔popover association — `aria-controls` added while mounted (resolves via `getElementById`; absent when closed, dangling-reference rationale commented).
  - `[low]` `[patch]` The re-open no-re-request guard whitelisted only `/api/cards/` and passed on empty fixtures — widened to `/api/(cards|card-image)/`, fixtures now push a real card id, non-vacuity assertion requires observed hydration traffic.
  - `[low]` `[patch]` EXPERIENCE.md's fade sentence drifted from tokens.css's inventory row (casing + arrow) and read self-contradictory — row quoted byte-identically; no-CSS-registration vs documentation-inventory obligations separated explicitly.
  - `[low]` `[patch]` The cold-open focusables selector was wrong (`:disabled` no-op on `<a>`/bare `[tabindex]`; `tabindex="-1"` included) and triplicated — corrected and hoisted to one module-scope helper; corridor pins re-verified from the DOM, none hand-adjusted.

### 2026-08-22 — Greptile round (PR #97)
- patch: 5: (high 0, medium 3, low 2)
- addressed_findings:
  - `[medium]` `[patch]` Greptile P1 (the ONE real finding): the popover's viewport width clamp never engaged — the box was LEFT-anchored to a pill sitting at the viewport's right edge, so a long title grew rightward off-screen on anchor offset, not box width. Re-anchored `right: 0` (grows leftward across the header, where the clamp's arithmetic is true); comment records the reasoning.
  - `[medium]` `[patch]` Greptile round 2 P1 (the symmetric flaw): the VERTICAL clamp subtracted only gutters from `100vh` — blind to the popover's own top offset below a content-sized header (tail past a short window's bottom) and to `vh` overshooting under retracting browser chrome. Fixed with `100dvh` (AppShell's own argument) plus a measured anchor term: `--history-popover-top`, set once before paint via the ManaCurve/ColourDistribution runtime-channel escape hatch — registered as the THIRD exact-name channel in `eslint.config.js` and `token-usage.test.ts`'s `RUNTIME_CUSTOM_PROPERTIES`, `0px` jsdom fallback, wiring pinned by a container test (suite 2560 → 2561).
  - `[medium]` `[patch]` Greptile round 4 P1 (the width clamp's own anchor blindness — round 1's lesson on the other side): the pill row wraps at narrow windows (`flex-wrap: wrap`, the declared honest failure mode), and a wrapped anchor leaves the viewport's right edge — the `100vw`-based cap then let a long title run past the LEFT edge. The width budget is now measured too: `--history-popover-right` (the right-anchored edge's viewport-X, written beside the top term by the same effect, re-measured on resize), the FOURTH runtime channel; `max-width: min(480px, calc(var(--history-popover-right, 100vw) - gutter))`. Both anchor tests extended to both properties.
  - `[low]` `[patch]` Greptile round 3 P1: the anchor measurement was mount-only, going stale if the window resizes while the popover stays open — now re-measured on window `resize` (the only thing that can move the anchor mid-open; not a key listener, so no census stake), pinned by a spied-rect test (suite 2561 → 2562).
  - `[low]` `[patch]` CI's Prettier check (not part of local `npm run lint`) flagged 4 files — formatted; repo-wide `prettier --check` now clean.

Rejected as noise: same-`id` replace keeping its position (the contract mandates in-place); a malformed `ts` at the front freezing order to arrival (defensible construction of "never silently reorder", tested); suppressing a title equal to the kind label (rendering the word twice is worse); history surviving `deck_changed` (by design — stale-UUID degradation is the safety); a UI-level cap/scroll rendering test (store owns the cap; jsdom cannot observe scroll); `escape()` helper style; the review diff appearing truncated (unified-diff context artifact); `aria-haspopup` value semantics beyond adding `aria-controls` (the attribute is contract-mandated).

## Auto Run Result

**Summary:** Story 17.2 shipped — the retention store is widened from "latest per kind" to the last 20 pushes overall (per-tab, in-memory, clears on refresh; ordered newest-first by envelope `ts`, never `id`; same-`id` replaces in place; oldest drops silently at the cap), surfaced as the ruled FR-18 home: a fifth "History" nav pill (nav-pill spec + clock glyph, quiet until the first push of any kind, never an unread dot, `aria-expanded`/`aria-haspopup`/`aria-controls`) toggling a non-modal popover of real entry buttons (kind + authored title + tabular time). Entry activation closes the popover, then reopens that exact push via `reopenPush(id)` — popover and modal never coexist; reopening re-hydrates without ever re-requesting from the agent. Focus: newest entry on open, pill on close, never `document.body`; dismissal via activation, Esc (wrapper-consumed; document bubble half census-registered), outside pointerdown, or pill toggle. Opacity-only fade over glide, viewport-clamped geometry per `{components.history-popover}`.

**Files changed:**
- `ui/src/state/agentView.ts` / `agentView.test.ts` — `history` field + `historyWith` (ts-order, arrival fallback, replace-by-id, cap 20) inside `openAgentView`'s single setState; `reopenPush`; `useAgentViewHistory`/`useAgentViewHistoryCount`; `instantOf` type guard.
- `ui/src/containers/AgentViewsNav/AgentViewsNav.tsx` / `.test.tsx` / `copy.ts` / `AgentViewsNav.css` / `HistoryPopover.css` (new) — History pill + popover, quiet pattern, focus/dismissal machinery, authored copy, token-compliant clamped styles (new stylesheet forced by the file-scoped UX-DR6 guard).
- `ui/src/App.test.tsx` — 17.2 composed-seam describe (flagship four-push loop, popover-closes-on-push, accepted-residual pin, wandered-focus, no-re-request guard), shared `focusablesNow` helper, corridor pins re-verified.
- `ui/tests/keyboard-floor.test.ts`, `shell.test.ts`, `store-writes.test.ts`, `token-usage.test.ts`, `attribution.test.ts`, `agent-views-nav-copy.test.ts` — census/registry/gate registrations shipped with the change.
- `ui/src/styles/tokens.css` — History-popover fade inventory row (see Spec Change Log entry 1).
- `EXPERIENCE.md` / `DESIGN.md` — confirmed `[ASSUMPTION]` tags struck, Esc-caveat and fade-inventory amendments, all story-cited.

**Review findings breakdown:** 13 patches applied (0 high, 2 medium, 11 low), 0 deferred, 8 rejected. No intent gaps, no spec repairs (three implementation deviations recorded openly in the Spec Change Log).

**Follow-up review recommendation:** true — patched counts: high 0, medium 2, low 11; score 3×2 + 1×11 = 17 ≥ 5.

**Verification:** coordinator re-ran after patches: `cd ui && npx tsc -b` clean; `npm run lint` (eslint + stylelint) clean; `npm test` → **85 files / 2560 tests green** (2551 pre-patch), covering posture, store-writes, keyboard-floor, token-usage, shell, copy gates, corridor pins. Probe proof (implementation round): planted RED (cap removed in `historyWith`) caught by name — `RED |dom| src/state/agentView.test.ts > … > caps at 20, dropping the oldest silently` — control GREEN at 2551 before and after; matrix test audit passed (all 10 rows covered by tests that ran).

**Residual risks:** browser eye-check owed — popover anchoring/fade/scroll/focus movement and exact geometry (now bounded by the viewport clamps) are CSS jsdom cannot observe. Accepted, pinned residual: Esc with focus on an unrelated control while the popover is open co-releases an active pin (CardDetail's earlier-registered document listener). The SPA was rebuilt into the committed static tree at finalization (17.1 precedent; the pre-commit hook mirrors `plugin/`).

## Design Notes

- Append in `openAgentView`, not in the four `open*Push` verbs: re-opens also route through `openAgentView`, so guard against re-appending — only a push **new to history** (or a same-id replace) mutates the array; a `reopenPush`/`reopenAgentView` of an existing entry must not duplicate it. Simplest: treat "id already present with identical content" as a no-op for the array.
- History entries hold the same `AgentViewContent` references as `retained` — no payload copy, no divergence; art is never retained (hydration owns it), so a 20-entry history is a few KB.
- The popover Esc listener registers unconditionally-while-open in bubble phase and does **not** stop propagation; while a view is open the popover is already closed by invariant, so the census table stays honest.

## Verification

**Commands:**
- `cd ui && npm test` -- expected: full suite green (posture, store-writes, keyboard-floor, token-usage, copy gates, corridor pins).
- `cd ui && npx tsc -b && npm run lint` -- expected: clean (eslint + stylelint).
- `uv run python -m scripts.vitest_probe_harness --control` (warm) then a planted RED per Testing Rules -- expected: pasteable proof line; suggested plant: break the cap (21 retained) or the close-before-open sequencing assertion.

**Manual checks (if no CLI):**
- Eye-check in a real browser: popover anchoring under the header, opacity-only fade, scroll inside at >20-entry height, outside-click and Esc dismissal, focus visibly moving to the newest entry and back to the pill.
