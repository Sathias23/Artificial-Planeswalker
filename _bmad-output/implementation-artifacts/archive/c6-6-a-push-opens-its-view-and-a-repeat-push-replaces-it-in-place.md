---
baseline_commit: 3274db02518dddfd049a2313156669b02426f16a
---

<!--
  Story context created 2026-08-11 by create-story (ultimate context engine analysis).
  Sources: epics-companion-app.md (Story 6.6 :2850-2883, Epic 6 :2664-2669, UX-DR catalogue
  :543-690), EXPERIENCE.md (:71, :90, :122-126, :130, :146, :153-159), DESIGN.md (:122, :471),
  shipped ui/ source at 3274db0, c6-5 story record + its review findings, deferred-work.md
  (:22-40, :186-187, :4070-4075, :4879-4891), composition reference (no timestamp exists in
  the agent-view header — checked; the two "ago" grep hits are the letters inside "Dragons").
-->

# Story c6-6: A push opens its view, and a repeat push replaces it in place

Status: done

## Story

As Brad who just asked a question,
I want the answer to appear without me clicking anything,
So that the agent driving the glass is something I see rather than something I have to go and find.

## The story in one paragraph

c6-5 built the shell and left three letters addressed here by name: `socket.ts:411-420` still
drops the four view kinds ("c6-6 adds the wiring"), `agentView.ts` still has no production
writer ("c6-6 is what turns a `suggestions` envelope into one of these"), and the shell's
`aria-live` heading annotates itself as existing *for c6-6's replacement*. This story closes the
loop the whole feature exists for: a `suggestions` frame off the WebSocket becomes an open agent
view with no click (the confirmed 2026-07-25 ruling), and a second push while the view is open
**replaces the content in place** — crossfade over `--motion-glide`, focus back to the heading,
a real live-region announcement — without re-running the entry bloom and without disturbing the
return-focus contract. It also ships the empty-push state with its verbatim copy, refines the
disconnected-focus-restore arm so closing over a state panel lands on the state panel, and
retains enough in the store (`ts`, `kind`, items) that c6-7 can render rows and c6-8 can build
pills without reshaping anything. It does **not** render suggestion rows (c6-7), build nav pills
or unread markers (c6-8), or measure the 250 ms budget (c6-9). Python is untouched: the tool
(c6-4), the wire (c5-1/c5-5) and the broadcast (c5-4) are all shipped — this is a frontend-only
story.

## Acceptance Criteria

*(Verbatim from `epics-companion-app.md:2856-2883`, numbered for citation.)*

1. **Given** no agent view is open **When** a push arrives **Then** its view **opens
   automatically** (UX-DR34 — confirmed ruling, 2026-07-25).
2. **Given** a Suggestions view is open **When** another suggestions push arrives **Then** the
   content is replaced **in place** with a brief crossfade over the glide duration (FR-08,
   UX-DR34) **And** focus moves to the heading, whose live region announces the new push
   (UX-DR45, UX-DR46) **And** under `prefers-reduced-motion` the swap is instant (UX-DR42).
3. **Given** a push carrying an unknown card id **When** the view renders **Then** that entry
   alone degrades to the unknown-card placeholder and the rest of the push renders normally — a
   push never fails wholesale (FR-13, AD-7).
4. **Given** an empty push **When** the view opens **Then** it renders the deliberate empty
   state with its verbatim copy, rather than rejecting (UX-DR33, AD-7).
5. **Given** a state panel occupies the left column while an agent view is open **When** the
   deck is lost or the database becomes unavailable **Then** the view **stays open and stays
   valid** — agent content is about cards, not about the deck's presence, so a lost deck does
   not invalidate it (UX-DR37) **And** on close the user lands on the state panel, with the
   skip link and grid Tab stops withdrawn.
6. **Given** a push arrives **When** the announcement fires **Then** motion is never the sole
   signal — the heading, its timestamp and the nav pill's marker all update (UX-DR43).

**Scope boundaries (the epic's own split — build none of these):** suggestion rows, their
inspection contract and per-row alt text are **c6-7** (:2885-2920) — which is where AC 3's
subject (a rendered entry) first exists, see Open Question 2; nav pills, unread markers, re-open
and kind switching are **c6-8** (:2922-2957) — which is where AC 6's pill marker and timestamp
display first exist, see Open Question 3; the 250 ms budget measurement is **c6-9** (:2959).
`swaps`/`tier_list`/`groups` views are Epic 9 (P1) — those three kinds stay dropped.

## Tasks / Subtasks

- [x] **Task 0 — Baselines, branch, and grep dispositions** (protects everything)
  - [x] Branch `feat/companion-c6-6-push-opens-view` cut from `feat/companion-c6` at or after
        `3274db0` (the c6-5 merge record).
  - [x] Frontend baseline: `npm test` from an **uppercase** drive path; expect
        **1,937 passed / 71 files**; validate the collected count before trusting any run
        (two distinct flakes are on record — Landmines 10/11).
  - [x] Python baseline: `uv run pytest -m "not integration"` — expect **2,907 passed /
        1 skipped / 55 deselected**; this story must leave it **unmoved** (no backend change).
  - [x] `grep -rn "c6-6"` across `ui/src/`, `ui/tests/`, `src/`, `docs/`, `ui/README.md`,
        `deferred-work.md` — ~30 known sites (list in Dev Notes); build the dispositions
        table. Most are contract prose this story *fulfils* and must then re-verify for
        truthfulness (Task 6). Expect to find more than predicted — four stories running.
- [x] **Task 1 — Store: the envelope becomes content** (AC 1, AC 4, AC 6)
  - [x] Extend `AgentViewContent` in `ui/src/state/agentView.ts` to carry what c6-7/c6-8 need
        read-only: the push's `kind`, its `ts`, its envelope `id` (the replace key), and the
        suggestion items — typed **only** via `ui/src/api/schema.ts` aliases (`SuggestionsEvent`
        / its payload item type; add a schema alias if one is missing — never a hand-written
        wire shape). Exact field names dev's choice; the principle is that retained content must
        be sufficient for c6-8's re-open ("re-hydrated against current card data" — ids and
        reasons retained; art is always re-fetched).
  - [x] Add the builder + open verb (e.g. `openSuggestionsPush(event)`) in `agentView.ts` — the
        store module stays the one writer (`store-writes.test.ts`). Construction is
        **defensive** (Open Question 6): `items = payload?.items ?? []`,
        `count = items.length`, `title` = payload title if non-blank else the fallback constant
        (Open Question 7) — this closes the dw:30-32 dialog-accessible-name defer at the point
        content is constructed, exactly where that entry says to.
  - [x] Store tests: builder rows for absent payload, absent items, blank/absent title, empty
        items; the retained `ts`/`id`/`kind`; every assert paired non-vacuously (house style).
- [x] **Task 2 — Socket dispatch and the connection seam** (AC 1)
  - [x] `socket.ts`: add the view-push callback to `AgentSocketOptions` (it carries the full
        typed event — the payload is the content); the dispatch switch routes `suggestions` to
        it; `swaps`/`tier_list`/`groups` **stay dropped**, comment re-homed to Epic 9. The
        switch stays total (`never` arm untouched).
  - [x] `connection.ts`: wire the callback to the store verb — this module still contains no
        `setState` and names no store (its own header rule; calling an exported verb is the
        `redriveDeckBoot` precedent).
  - [x] Move the pins **in the same commit**: `socket.test.ts:639` (four-kinds-dropped becomes
        three-dropped + suggestions-delivered-with-payload) and `App.test.tsx:2472` (the AC-11
        ignore test splits the same way). `frame()` / `push()` helpers already exist in both.
- [x] **Task 3 — Replace-in-place in the shell** (AC 2)
  - [x] `AgentView.tsx` gains a push-identity prop (the envelope `id`). An effect keyed on it —
        **skipping the mount run** — re-fires `focusHome(headingRef.current)` and drives the
        crossfade. The shell must **stay mounted** across a replace: no `key` on `<AgentView>`
        in `App.tsx` (Dev Notes, "Why replace must not remount").
  - [x] The crossfade: opacity-only, over `var(--motion-glide) var(--ease-glide)`, on the body
        (and heading if dev chooses) — the `[data-entering]`-style attribute-flip-in-a-frame
        pattern the bloom already uses, for the same gate reason (a `@keyframes` block reads as
        two rules named `from`/`to` to the motion gate's CSS reader). Opacity is not a
        `MOTION_PROPERTIES` member and the duration is a token the reduced-motion block zeroes
        (`tokens.css:323`), so UX-DR42's "instant content swap" is satisfied mechanically and
        the shipped-motion enumeration should not need a new entry; `tokens.css:294`'s
        inventory line "(c6-6)" is *fulfilled* by this task and stays as written.
  - [x] The announcement (AC 2's live-region half): make the replace a **real DOM mutation** of
        the `aria-live` heading per Open Question 4's ruling — a byte-identical title
        re-rendered in place mutates nothing and announces nothing.
  - [x] Shell tests: on replace — focus re-fires to the heading, the bloom does **not** re-run
        (`data-entering` stays false), the captured restore target **survives** (close after a
        replace still returns focus to the pre-open element), the crossfade attribute cycles,
        the heading mutation happens. On open-from-closed — mount runs bloom + focus + capture
        exactly as today (regression pins already exist; keep them green).
- [x] **Task 4 — The empty-push state** (AC 4)
  - [x] The view body for this story (per Open Question 1's ruling): a small container module
        that renders the **verbatim** empty-push line when items are empty and nothing (yet)
        when they are not — c6-7 replaces the nothing with rows. Copy in a copy module;
        interpolate `{kind}` with the wire kind (`suggestions`).
  - [x] EXPERIENCE.md:71 is the artefact: *"The agent sent an empty {kind}. Nothing to show —
        ask it for another pass."* Gate it byte-for-byte with a per-site verbatim test reading
        the artefact (`empty-deck-copy.test.ts` is the model; `copy-rules.test.ts:127` names
        this story's empty push as the next entry).
  - [x] Record the copy READING in the Debug Log — second-person, blameless, concrete next
        action — the permanently-open dw judgement (`dw:4070-4075`, `dw:4879-4891`: *"c6-6
        still owes it"*). The reading is the deliverable; no assertion pretends to make it.
  - [x] Move the pins **in the same commit**: `copy-rules.test.ts` `COPY_MODULES` (+1 with
        reason > 40 chars), `shell.test.ts` `CONTAINERS` (currently 29; +1 per new module,
        with import sets — the pin c6-5 did not predict and this story does).
- [x] **Task 5 — State panel behind the view, and the AC-6 signals** (AC 5, AC 6)
  - [x] Refine restore ARM 3 in `AgentView.tsx:208-215` per Open Question 5's ruling: when the
        remembered element is disconnected, prefer the state panel's headline
        (`.state-panel-headline`, via `focusHome`) when a state panel is showing, else the
        `h1` as today. Update the arm's comment (it names c6-6) and `AppShell.test.tsx:66`'s
        one-`h1` dependency note if touched.
  - [x] App-level tests: push opens the view end-to-end through the real socket seam (mock
        socket `push('suggestions', {...})` → dialog present, title/count real); repeat push
        replaces in place (same dialog DOM node — identity assert — new content, focus on
        heading); push while closed-with-retained-content re-opens (fresh mount, bloom+capture);
        deck lost / `database_unavailable` behind an open view → view stays open and valid
        (AC 5); close over a state panel → focus lands per Q5, and the skip link + grid stops
        are absent (already-shipped withdrawals, now pinned in this composed state); reset
        `agentView` in the nested `beforeEach` (c6-3's discipline — the shared block misses
        newer stores).
  - [x] AC 6 disposition (per Open Question 3's ruling): assert the non-motion signals this
        story owns — heading text + count update, live-region mutation — and that the store
        retains `ts` for c6-8's pill time. The pill marker/timestamp *display* is recorded as
        structurally homed on c6-8 (the c6-5 Q7 pattern).
- [x] **Task 6 — Planted red, gates, artifacts, ripple, ledger**
  - [x] Planted red 1: the builder ignores its argument (mints empty items regardless — c6-4's
        passthrough regression, verbatim). Predict the delegation and empty-vs-non-empty tests
        red, confined to this story's blocks. Planted red 2: remove the push-identity effect's
        body (replace no longer re-fires focus/announce). Full runs, uppercase drive,
        collected count validated before scoring; revert, `git diff --exit-code` clean.
  - [x] `npm run lint`, `npm run typecheck`, `npm run format:check`, `npm test` strictly
        > 1,937; Python unmoved at 2,907/1/55.
  - [x] Runtime diff ⇒ rebuild: `npm run build` (→ `src/companion/app/static/`, never
        hand-edit) then `uv run python -m scripts.build_plugin`; sha256-verify mirrors;
        rebuild AFTER the last edit including review patches.
  - [x] Ripple sweep — grep the CLAIM, not the sentence (four-times-learned): the fulfilled
        prose sites in Dev Notes → update to past tense/truth (R2: no forward-looking prose
        added; fulfilled contracts corrected); expect >30 sites.
  - [x] Ledger reconciliation in `deferred-work.md`: dw:30-32 (title guard) CLOSED by Task 1;
        dw:186-187 (`agentEventOf` kind-only) annotated per Open Question 6's ruling —
        PARTIALLY TRIGGERED here (this story is the first reader of `payload.title`/`items`;
        the builder's defensive construction covers the fields it reads; item-field validation
        stays c6-7's); dw:4070-4075/4879-4891 (copy reading) annotated HONOURED-and-stays-open;
        c6-5's residual trap-escape and `FOCUSABLE_SELECTOR` defers untouched (c6-7's).
  - [x] Dev Notes KB self-check (10–20 KB band); record suite arithmetic before/after.

*(Per the standing workflow: implement Tasks 0–6, set status `review`, STOP — Brad runs the
three-layer review and raises the PR into `feat/companion-c6`.)*

### Review Findings

*(bmad-code-review, 2026-08-11 — Blind Hunter, Edge Case Hunter, Acceptance Auditor, run in
parallel against the uncommitted diff at baseline `3274db0`.)*

- [x] [Review][Decision] Q7's fallback-title copy module lives in `ui/src/state/agentView.ts`,
  not a container's `copy.ts` — confirm the location precedent before c6-8 inherits it.
  `SUGGESTIONS_VIEW_TITLE` is correctly registered in `COPY_MODULES` (satisfying the letter of
  Q7's ruling), but every other `COPY_MODULES` entry is a `containers/*/copy.ts` file, and this
  is the first `src/state/` entry in that map. The code's own docstring justifies the choice at
  length (a store can't import a container's copy module; c6-8's nav pill needs the same
  constant, so a container-owned copy would be the wrong address for the second reader) — a
  defensible engineering call, but a literal deviation from Q7's recommended pattern that Brad
  did not explicitly bless when ruling it. `agentView.ts:76`. **RESOLVED (Brad, 2026-08-11):
  keep it in `agentView.ts` — the code's own rationale stands as the precedent for c6-8.**
- [x] [Review][Patch] `suggestionsViewOf` doesn't defend against wrong-typed payload fields,
  contradicting Q6's ruling ("absent/malformed payload constructs the empty view"). If
  `payload.title` is present but non-string (e.g. a number), `title?.trim()` throws a
  `TypeError` — `agentEventOf` validates only `kind`, so this is reachable from a
  version-skewed or malformed backend frame, not merely theoretical. If `payload.items` is
  present but not an array, `items ?? []` passes it through unchanged, and `count: items.length`
  becomes `undefined` instead of a real count. Fix: guard both fields by type
  (`typeof title === 'string'`, `Array.isArray(items)`) before use.
  `ui/src/state/agentView.ts:226-227`. **APPLIED (2026-08-11)** — `rawTitle`/`rawItems` typed
  `unknown`, gated with `typeof`/`Array.isArray` before use; `agentView.test.ts` (23 tests) and
  `tsc -b` both clean after the patch.
- [x] [Review][Defer] `id`/`ts` on the envelope are trusted without validation — a backend
  violating that required-field contract can silently defeat the replace-in-place announcement.
  `suggestionsViewOf` copies `event.id`/`event.ts` straight through with no presence check. Two
  distinct malformed pushes both missing `id` would make `AgentView.tsx`'s
  `showingPushRef.current === pushId` comparison (`undefined === undefined`) treat them as the
  same push, skipping the re-focus/live-region/crossfade — the store still overwrites `content`
  unconditionally, so the visible text updates via ordinary reconciliation with no accessible
  announcement. This is a consequence of the kind-only `agentEventOf` narrower, which Q6 scoped
  to defending `payload`/`title`/`items` only — `id`/`ts` validation was out of this story's
  ruled scope, and the same trust applies uniformly to `deck_changed`/`active_deck_changed`
  already shipped. `ui/src/state/agentView.ts:229-230`, `ui/src/containers/AgentView/AgentView.tsx:312`
  — deferred, pre-existing narrower design, requires a backend contract violation to trigger.
- [x] [Review][Defer] `AgentView.test.tsx`'s new ARM 3 fixtures hand-roll a `<section
  className="state-panel">` markup fragment rather than rendering the real `StatePanel`
  component, so if `StatePanel.tsx`'s role/label/headline-class ever changes, these focus-restore
  tests would keep passing against a fixture that no longer matches production.
  `ui/src/containers/AgentView/AgentView.test.tsx:81-82` — deferred, test-quality only, no
  functional impact.

## Dev Notes

### What is already shipped (verified at story creation — the letters this story answers)

- **The whole pipe exists except one segment.** `companion_show_suggestions` (c6-4) posts a
  `SuggestionsEvent` to `/agent/events`; `ws.py` broadcasts it verbatim to every connected tab
  (c5-4/c5-5); `client.ts:1007` narrows each frame through `agentEventOf` and hands it to
  `socket.ts`'s one total dispatch switch — where `suggestions` is **received and deliberately
  dropped** (`socket.ts:406-430`, with a comment naming Epic 6). `AgentSocketOptions`
  (`socket.ts:181-225`) has `onStatus` / `onReconnected` / `onSystemEvent(kind)` and **no view
  callback**. `connection.ts` is the composition seam that wires callbacks to store verbs — it
  contains no `setState` and names no store (its header explains why; `redriveDeckBoot` is the
  call-an-exported-verb precedent this story's wiring copies).
- **The store is a scalar with retained content and no production writer.**
  `agentView.ts`: `AgentViewContent {title, count}` (deliberately not a wire shape — *"c6-6 is
  what turns a `suggestions` envelope into one of these"*, `:57`), `openAgentView` /
  `closeAgentView` (writes `status` only — the whole of UX-DR34), `useOpenAgentView` selector.
  `close()` never touches content; `resetAgentView` is tests-only. AC 5 of c6-5 (dismissal
  never clears) is already pinned — do not weaken it.
- **The shell is content-agnostic and all its open-time effects are mount-only.**
  `AgentView.tsx`: props `{title, count, onClose, children}`. On mount: capture restore target
  (`:186-192`), `focusHome(heading)` (`:197`), bloom via `[data-entering]` flipped in a
  `requestAnimationFrame` (`:147-151`); document-capture Esc (`:237-252`); trap + scrim guards
  as native listeners (`:299-372`). The heading carries `aria-live="polite"` and its comment
  says what it is for: *"c6-6's replacement — one view swapped for another under a reader who
  is already inside it"* (`:398-403`). **No announcement fires on first open** (ruled at c6-5;
  focus-to-heading is the open signal).
- **App wiring**: `App.tsx:178` reads `useOpenAgentView()`; `:607-610` passes
  `overlay={agentView === null ? undefined : <AgentView title count onClose={closeAgentView}/>}`
  — no `key`, no children yet. The comment at `:173-176` (*"Nothing WRITES that store in
  production yet"*) is falsified by this story — prose-sync it.
- **The wire shape** (`types.d.ts:1038-1111`, aliased in `schema.ts`):
  `SuggestionsEvent {id, ts, kind: 'suggestions', payload}` where
  `payload.title?: string | null` and `payload.items?: SuggestionItem[]` are **both optional**
  in the generated type, and `SuggestionItem {card_id, reason, category?, confidence?}`. `id`
  is *"opaque — identity and de-duplication, no ordering"*; `ts` is the ordering key,
  timezone-aware. **`agentEventOf` validates only `kind`** (`client.ts:701-716`) — a frame
  `{"kind":"suggestions"}` with no payload at all reaches the switch typed as a full event.
  This story is the first code to read payload fields; see Open Question 6.
- **Motion tokens**: `--motion-glide: 240ms` + `--ease-glide` (`tokens.css:184,188`) — DESIGN.md
  `:122` `glide: 240ms` is the crossfade's duration by name (EXPERIENCE.md:90 *"a brief
  crossfade over `{components.motion.glide}`"*). The reduced-motion block zeroes
  `--motion-glide` (`:323`), and the UX-DR42 inventory line for this story already exists:
  *"Push-replace crossfade → instant content swap (c6-6)"* (`:294`).
  `token-usage.test.ts:2581` requires the inventory to keep naming `c6-6` — the line stays.
  `ui/tests/fixtures/css/clean.css:76` notes the crossfade may legally compose a two-animation
  list — available if dev needs it, but the attribute-flip transition pattern is the shipped
  precedent and dodges the keyframes/gate interaction entirely.
- **Copy machinery**: per-site verbatim gates read EXPERIENCE.md itself (`copy.test.ts`
  header; `empty-deck-copy.test.ts` is the closest model — it handles a copy row whose label
  appears twice in the artefact). `copy-rules.test.ts:127` already says: *"c6-6's empty push —
  ADDS AN ENTRY HERE with its reason"*. The empty-push row is EXPERIENCE.md:71:
  **"The agent sent an empty {kind}. Nothing to show — ask it for another pass."**
- **State panel + withdrawals (AC 5's substrate is already shipped)**: `StatePanel.tsx:115-116`
  renders `<section className="state-panel" role="region" aria-label={headline}>` with
  `<h2 className="state-panel-headline">`. The skip link is already absent when a state panel
  occupies the left column (c4-11), and the grid's Tab stops vanish with the grid. Nothing in
  the overlay path reads deck state, so "view stays open" is true by construction — this
  story's job is to **pin the composed behaviour** and refine the focus-restore arm
  (`AgentView.tsx:208-215`: *"until c6-6 refines the state-panel arm"*).
- **Store governance**: seven stores, one writer module each (`store-writes.test.ts:77-115`);
  types only from `schema.ts` aliases over generated `types.d.ts`; containers never call
  `setState`.

### Why replace must NOT remount the shell (the c6-5 review finding, resolved here)

The c6-5 review's decision 2 recorded that `<AgentView>` carries no `key`, so a content
replace is a prop update and the mount-only focus/bloom effects don't re-fire — *"the remount
mechanics are still owed to c6-6."* The owed mechanics are the **re-fires**, not a remount.
A `key={pushId}` remount is the wrong fix three ways, all load-bearing:

1. **It plays the wrong animation.** Remounting re-runs the entry bloom (480 ms fade + 8px
   rise). AC 2 specifies a *crossfade over the glide duration* (240 ms, opacity only) — a
   different motion with its own UX-DR42 inventory line.
2. **It corrupts the return-focus contract.** The mount effect captures
   `document.activeElement` as the restore target. At replace time focus is *inside the view*
   (usually the heading), so a remount would capture the heading and AC 4-of-c6-5's "focus
   returns to the element focused before the view took it" would silently return focus to the
   view's own corpse.
3. **It runs the restore cleanup mid-open** — the unmount handler would fire and try to restore
   focus while the view is conceptually still open.

So: shell stays mounted; a push-identity prop (the envelope `id`) keys an effect that re-fires
`focusHome(heading)` + the crossfade + the announcement, **skipping its mount run** (mount is
handled by the existing effects). The closed→open transition is still a real mount (overlay
absent → present), so auto-open from a closed state gets bloom + focus + capture exactly as
shipped — including a push arriving while the view is closed with retained content (that is an
open, not a replace).

One residue to note in code: `id` exists for de-duplication, so a repeat frame carrying the
**same** id will not re-key the effect. That is arguably the correct reading of AD-6 (it *is* a
duplicate) — state it in the effect's comment rather than leaving it to be discovered.

### Ruled — settled, do not re-derive

1. **Push auto-opens its view** — confirmed UX ruling 2026-07-25 (EXPERIENCE.md:218). The nav
   pills are the re-open path (c6-8), never the primary one.
2. **The overlay stack is one level deep, permanently** (UX-DR38). The scalar store is that
   fact in the type; a second view has nowhere to go. Opening over an open view replaces.
3. **No announcement from behind a modal** (EXPERIENCE.md:123) — deck refetches completing
   behind an open view announce nothing. Already true (the deck live region is elsewhere);
   don't create a path that violates it.
4. **Entry animation is never inside any latency budget** (EXPERIENCE.md:165) — same for the
   crossfade: presentation on top of committed content, nothing waits on it. c6-9 measures.
5. **The four wire kinds vs the tool name**: the envelope kind is `suggestions` (the MCP tool
   name `companion_show_suggestions` is c6-4's Python-side name, not the discriminant).
6. **`swaps`/`tier_list`/`groups` stay dropped** — their views are Epic 9 (P1); c6-8 owns
   kind-switching infrastructure. Re-home the drop comment, don't widen this story.
7. **Esc-layering contract is shipped and tested** (c6-5) — one Esc closes the view, the pin
   survives. This story's socket wiring must not add any keyboard listener (keyboard-floor's
   listener table should not move).
8. **R2 standing rule**: no forward-looking cross-module prose in docstrings/comments; the
   fulfilled c6-6-addressed comments are the opposite case — update them to stay truthful.
9. **The static/plugin rebuild rule**: runtime `ui/src` diff ⇒ rebuild
   `src/companion/app/static/` AND `plugin/**`, sha256-verified, after the last edit. CI drift
   checks use `git status --porcelain`.
10. **Merge ≠ release**: story PR targets `feat/companion-c6` (Greptile per story); dev stops
    at `review`; Brad reviews and raises the PR. No tag/CHANGELOG until c8-4.

### Landmines specific to this story

1. **Guard pins move with the code, same commit** — this story's set: `socket.test.ts:639`
   (drop pin splits), `App.test.tsx:2472` (same split at App level), `copy-rules.test.ts`
   `COPY_MODULES` (+1), `shell.test.ts` `CONTAINERS` (29 → +N, with import sets — the pin
   c6-5 did not predict), and any `store-writes` reason strings whose prose changes tense.
   `keyboard-floor` and the `token-usage` shipped-motion enumeration should **not** need to
   move (no new listener; opacity is not a motion property) — if either goes red, stop and
   understand why before amending it.
2. **`agentEventOf` is kind-only, and this story is the first payload reader.** Every read of
   `payload`/`title`/`items` must survive their absence — the generated type marks both fields
   optional even for honest wires, so defensive construction is required regardless of the
   malformed-frame case (Open Question 6). A `TypeError` thrown inside the dispatch path is an
   uncaught exception in a socket message handler — it won't close the socket, but it kills
   that dispatch and any store write behind it.
3. **A byte-identical title announces nothing.** `aria-live` regions announce on DOM mutation;
   re-rendering the same string is not a mutation. The common case IS the identical title
   (the fallback constant when agents omit `payload.title`). Open Question 4 rules the
   mechanism; whatever ships, the test must assert a real mutation, and the
   screen-reader-dedupe half is jsdom-unverifiable — home it on the C6 manual checklist
   (Block J backstop, c8-6), not on a vacuous assert.
4. **Do not capture the restore target on replace** — see "Why replace must not remount". The
   replace effect must not touch `restoreTargetRef`.
5. **The crossfade must not use transform** — a rise/slide would make it a `MOTION_PROPERTIES`
   member and demand a reduced-motion registration + shipped-motion pin entry the inventory
   line doesn't promise. Opacity + tokenized duration self-neutralizes.
6. **jsdom evaluates no stylesheet, media query, layout, or sequential focus navigation**
   (P15; R3 declined). Crossfade asserts = attribute emission + source-reading; focus asserts
   = `document.activeElement` inside `act()`; `fireEvent` only (`user-event` deliberately not
   installed); vitest globals OFF — import `describe/it/expect/vi` in every new file.
7. **`filled(overlay)` gates the wrapper** — App must keep passing `undefined` when closed.
   The body children this story adds ride inside `<AgentView>`; don't move the conditional.
8. **The store's one-writer rule**: the builder lives in `agentView.ts`. `connection.ts` calls
   the verb and must not gain a `setState` or a store name (`store-writes.test.ts:112-113`
   flags any module holding both).
9. **`AgentViewContent` stays `schema.ts`-typed** — extending it with items means importing
   the alias types (type-only; the store imports no React and should import no runtime code).
   If `SuggestionItem` has no alias yet, add it in `schema.ts` in the commit that gives it a
   consumer (that file's standing rule).
10. **Windows false-red**: `npm test` from a lowercase drive letter resolves no vitest config
    (~67 failed suites). Uppercase drive; validate the **collected count** before scoring any
    run — especially the plants.
11. **Two recorded flakes**: the cold-start `lint-gates.test.ts` timeout (~125 s setup,
    re-run warm), and the vitest worker-fork crash that **silently drops a whole test file**
    (`70 passed (71)` — why collected-count validation exists). Record occurrences, don't
    hide them.
12. **`pre-commit run` stashes unstaged changes** — stage probes before believing a hook run;
    `git ls-files` blindness makes un-added files invisible to every registry guard.
13. **Don't touch**: `src/**` Python (no backend change — the wire is complete),
    `ui/src/api/**` generated files (no wire change ⇒ no `gen:api`), `AppShell.tsx`,
    `test-setup.ts` (13 lines, stays), the nav placeholder string (c6-8's), CardDetail/
    inspection modules (the pin contract is shipped).

### Testing requirements

- **Store suite** (`agentView.test.ts`): builder defensive rows (absent payload / items /
  title; blank title; empty items → count 0); retained `ts`/`id`/`kind`; the existing
  AC 5/AC 6 pins stay green; the `:77` "arriving for free" comment gets prose-synced (the
  replace contract is now real, not free).
- **Socket suite** (`socket.test.ts`): `suggestions` delivered **with its payload** to the new
  callback; the three Epic-9 kinds still dropped without fault; the six-kind switch still
  total; emit-on-change untouched by pushes.
- **Shell suite** (`AgentView.test.tsx`): the replace matrix (focus re-fires; bloom does not;
  restore target survives; crossfade attribute cycles; heading mutation) + mount behaviour
  unchanged; empty-body vs children rendering.
- **App suite** (`App.test.tsx`, the established harness — fake timers, `push()` helper,
  request-log asserts, nested `beforeEach` resets incl. `resetAgentView`): end-to-end
  push→open, repeat→replace-in-place (DOM node identity), closed-with-content→re-open,
  state-panel-behind-view (AC 5 both halves), empty push verbatim line, AC 6 signals.
- **Copy gate**: new per-site verbatim test against EXPERIENCE.md:71 (model:
  `empty-deck-copy.test.ts`); `COPY_MODULES` entry.
- Every behavioural assert pairs with a non-vacuity guard and a *why* message naming the AC
  (house style, c5-8 F5). Suite arithmetic recorded; frontend strictly > 1,937; Python
  unmoved.

### Previous-story intelligence

- **c6-5** (PR #67): the shell's mount-only effects are the load-bearing fact this story
  designs around (see "Why replace must not remount"). Its review also proved the ripple
  lesson a fourth time (41 sites vs ~28 predicted) and moved an unpredicted fifth pin
  (`CONTAINERS`) — this story predicts that one up front. Its planted red went *more* red
  than predicted because a guard was stronger than the story assumed — record what fires,
  don't assume.
- **c6-4** (PR #66, Greptile 5/5): the passthrough plant (envelope minted with empty payload
  regardless of argument) is this story's Task 6 plant, verbatim — it fired 3/3 there.
  Echo hygiene: nothing payload-sourced is interpolated into any user-facing string this
  story ships except the empty-push `{kind}` interpolation, which is a closed wire literal
  (`suggestions`), not user data.
- **c6-3** (PR #65, tests-only, cleanest review): the App.test harness discipline — nested
  `beforeEach` for stores the shared block misses; request-log sweeps on every new test.
- **The C5 retro standing items**: R2 (prose-sync) applies via Tasks 0/6; R5 (vitest probe
  harness) stays open — manual plants per the c6-5 Q6 precedent; R1-a/R1-b don't gate this
  story. Block J (eyes-on-pixels) remains ruled NOT RUN — the crossfade and announcement
  behaviour ship with zero human rendering until the C6 manual checklist (c8-6); say so in
  the PR description.

### The ~30 known `c6-6` ripple sites (Task 0's starting list)

Fulfilled-by-this-diff (prose-sync to truth): `agentView.ts` module header (*"from c6-6 the
writer is a WebSocket message"* — becomes present tense) + `:42` (*"c6-6 is the story that
wires"*) + `openAgentView` docstring (*"still owed to c6-6"*); `agentView.test.ts:77`;
`App.tsx:173-176`; `AgentView.tsx:211` (ARM 3) + `:402` (live-region purpose);
`socket.ts:411-420` (drop comment — reworded, Epic 9 keeps the three); `store-writes.test.ts:115`
+ `copy-rules.test.ts:351` (reason-string tense); `copy-rules.test.ts:127` (the entry arrives);
`ui/README.md:966` + `:1164` (mechanism rows). Stays-true (verify, don't touch):
`tokens.css:294`; `clean.css:76`; `token-usage.test.ts:2581` (inventory must keep naming c6-6);
`CardGrid/copy.ts:24-27` (historical citations). Ledger: the dw entries in Task 6. Plus
whatever the grep finds beyond these — expect more.

### Project structure notes

- **Expected diff**: `ui/src/state/agentView.ts` (+test) — content shape, builder, verb ·
  `ui/src/state/socket.ts` (+test) — callback + dispatch · `ui/src/state/connection.ts` —
  wiring · `ui/src/containers/AgentView/AgentView.tsx` (+test, +css) — replace mechanics,
  crossfade · new body/empty-state container module(s) under `ui/src/containers/` (+copy,
  +tests) · `ui/src/App.tsx` — children wiring + prose-sync · `ui/src/App.test.tsx` — new
  describe · possibly `ui/src/api/schema.ts` — a type alias with its first consumer · guard
  pins: `socket.test.ts`, `copy-rules.test.ts`, `shell.test.ts`, `store-writes.test.ts` ·
  new `ui/tests/empty-push-copy.test.ts` · rebuilt `src/companion/app/static/**` +
  `plugin/**` · records (this file, `deferred-work.md`, `sprint-status.yaml`).
- **Never**: `src/**` Python, generated `types.d.ts`/`openapi.json`, `AppShell.tsx`,
  hand edits under `static/` or `plugin/`.
- Containers: `src/containers/<Name>/{tsx,css,test.tsx}`, flat kebab-case classes (BEM is a
  stylelint error), no barrels, colocated tests; `src/components/` is CLOSED.
- No new dependency and no version change — React 19.2 / zustand 5 / the shipped toolchain
  pins cover everything; anything `npm install`-shaped in this story is a wrong turn.

### References

- Story + epic: `epics-companion-app.md` — Story 6.6 (:2850-2883), Epic 6 header (:2664-2669),
  6.7 boundary (:2885-2920), 6.8 (:2922-2957), 6.9 (:2959-2995); UX-DR33 (:543), UX-DR34
  (:551), UX-DR37 (:570), UX-DR38 (:576), UX-DR39 (:581), UX-DR42 (:653), UX-DR43 (:662),
  UX-DR44 (:666), UX-DR45 (:673), UX-DR46 (:679).
- UX: `EXPERIENCE.md` — agent-view behavioural row (:90), empty-push copy (:71), state
  patterns (:122-131 — state-panel-behind-view :122, no-announce-behind-modal :123,
  same-kind replace :124, empty push :130), focus management (:146), reduced motion (:153),
  motion-never-sole-signal (:154), live regions (:159), budget exclusion (:165), arrival
  ruling (:218). `DESIGN.md` — glide 240ms (:122), agent-view shell (:471), typography.micro
  timestamps (:402). Composition reference: **no timestamp exists in the agent-view header**
  (checked at story creation — the "ago" grep hits are inside "Dragons").
- Shipped code: `agentView.ts` (whole file), `AgentView.tsx` (:102-223 effects, :237-252 Esc,
  :299-372 trap/scrim, :396-416 markup), `AgentView/copy.ts`, `App.tsx` (:168-190, :601-610),
  `socket.ts` (:179, :181-225, :402-430), `connection.ts` (whole file), `client.ts`
  (:662-716), `types.d.ts` (:1038-1111), `schema.ts` (:231-264), `tokens.css` (:184, :188,
  :286-304, :323), `StatePanel.tsx` (:115-126), `focusHome.ts`.
- Guards: `socket.test.ts` (:117 frame, :506-524, :639-654), `App.test.tsx` (:100-128
  helpers, :2472-2488), `copy-rules.test.ts` (:55, :127, :306, :351), `store-writes.test.ts`
  (:77-115), `shell.test.ts` (CONTAINERS), `token-usage.test.ts` (:2573-2584),
  `copy.test.ts` + `empty-deck-copy.test.ts` (copy-gate models), `clean.css` (:70-82).
- Records: `c6-5-…md` (review findings 1-2 = this story's design constraints; Q5/Q7
  precedents), `c6-4-…md` (passthrough plant, echo hygiene), `c6-3-…md` (harness discipline),
  `deferred-work.md` (:22-40, :186-187, :4070-4075, :4879-4891),
  `epic-c5-retro-2026-08-09.md` (P15, R2/R5, Block J).

## Open questions for Brad (recommendations first — rule before code)

1. **What does the view body render for a NON-empty push, before c6-7's rows exist?**
   **Recommend: title + count are real; the body renders nothing for non-empty pushes** (the
   empty-push state ships real, Task 4) — an interim state on the umbrella branch, the
   c6-4/c6-5 precedent (pushes were dropped entirely until now; merge ≠ release). Alternative:
   throwaway text rows (name-less `card_id` + reason) — visible progress, but work c6-7
   deletes and a surface that would trigger the image/inspection questions early.
2. **AC 3 (unknown card id degrades to the placeholder) — dispose as homed on c6-7?** No row
   renders in this story, so the AC's subject does not exist yet; c6-7's own AC 4 covers it
   verbatim, and the store retains the ids either way. **Recommend: record AC 3 as
   structurally deferred to c6-7** — the c6-5 Q7/AC-8 pattern. Alternative: pull minimal row
   rendering forward, which is Q1's alternative by another name.
3. **AC 6's "its timestamp and the nav pill's marker" — the pill does not exist until c6-8.**
   The composition reference has no timestamp in the view header (checked); UX-DR28 puts the
   push time on the *pill*. **Recommend: this story's AC-6 signals are the heading update,
   the count, and the live-region announcement; the store retains the envelope `ts` so c6-8
   can render the pill time; the pill marker + timestamp display are recorded as c6-8's**
   (structural disposal, the c6-5 Q7 pattern). Alternative: add a timestamp element to the
   shell header now — un-specced chrome DESIGN.md:471 doesn't list.
4. **Replace announcement mechanics — a byte-identical title mutates nothing and announces
   nothing** (the common case: agents omitting `payload.title` hit the same fallback
   constant). **Recommend: key the heading's content on the envelope `id`** so every replace
   replaces the text node — a real DOM mutation — with the screen-reader-dedupe residue
   homed on the C6 manual checklist (jsdom-unverifiable). Alternative: announce only when
   the title text actually changes — spec-literal, but "announces the new push" would then
   be false for most pushes.
5. **The state-panel focus-restore refinement (AC 5's "on close the user lands on the state
   panel").** ARM 3 currently falls back to `focusHome(h1)` and names this story.
   **Recommend: when the remembered element is disconnected, prefer the state panel's
   headline (`.state-panel-headline`, via `focusHome`) when one is showing, else the `h1` as
   today.** A restore target that is still connected keeps winning — "lands on the state
   panel" is then the visual truth plus the fallback, not a focus override. Alternative:
   always land on the state panel headline when one is showing (overrides a connected
   restore target — contradicts UX-DR46's "returns to the previously focused element").
6. **Payload defence: harden `agentEventOf` or build defensively at the builder?** The
   narrower validates only `kind` (dw:186-187 says the trigger is "the story that reads those
   fields" — this story reads `title`/`items`, so it is at least partially triggered here).
   **Recommend: keep `agentEventOf` kind-only (its documented register) and make the builder
   total** — absent/malformed payload constructs the empty view (items `?? []`, fallback
   title), which the optional generated types force anyway; annotate the dw entry PARTIALLY
   TRIGGERED with item-field validation staying c6-7's. Alternative: widen `agentEventOf` to
   per-kind payload checks now — a bigger change to a shipped, pinned narrower than this
   story needs.
7. **The fallback title when `payload.title` is absent or blank — word and home.**
   **Recommend: `Suggestions`, in a copy module registered in `COPY_MODULES`** (this also
   closes dw:30-32's dialog-accessible-name defer, and becomes the pill label vocabulary
   c6-8 inherits — decide once). Alternative: interpolate from the wire kind
   (`suggestions` capitalised) — one mechanism for all four kinds later, but a
   runtime-assembled string is exactly what the copy guard's declared residues warn about.

## Dev Agent Record

### Agent Model Used

claude-opus-5 (Claude Code, `/bmad-dev-story`), 2026-08-11.

### Debug Log References

**Pre-code rulings.** All seven open questions were put to Brad before any code was written and
all seven were **adopted as recommended** (2026-08-11): Q1 non-empty body renders nothing until
c6-7; Q2 AC 3 structurally deferred to c6-7; Q3 AC 6's pill/timestamp halves structurally
deferred to c6-8 with `ts` retained; Q4 the heading's content is keyed on the envelope `id`; Q5
the disconnected-restore arm prefers the state-panel headline; Q6 `agentEventOf` stays kind-only
and the builder is total; Q7 the fallback title is `Suggestions`, in a registered copy module.

**Baselines (Task 0).** Frontend `npm test` from an uppercase drive path: first run reported
`1 failed | 1936 passed (1937)`, `70 passed (71)` files — the **known cold-start
`lint-gates.test.ts` timeout** (Landmine 11), recorded rather than hidden; the collected count
was validated at 1,937/71 before scoring, and a warm re-run was `1937 passed (1937)` / `71
passed (71)` in 6.31 s. Python `uv run pytest -m "not integration"`: `2907 passed, 1 skipped, 55
deselected`. The second recorded flake (the worker-fork crash that silently drops a file) did not
occur in any of this story's ~12 full runs.

**Grep dispositions (Task 0).** 30 known `c6-6` sites at baseline — 24 in `ui/`, 6 in
`deferred-work.md` — plus one in `ui/eslint.config.js` the story's list did not predict. After
the diff the count is 71, the growth being this story's own citations. Dispositions actually
taken:

- **Fulfilled → prose-synced (8):** `agentView.ts` module header, `:32`, and `openAgentView`'s
  docstring; `agentView.test.ts:77`; `App.tsx:173-176`; `AgentView.tsx:211` (ARM 3) and `:402`
  (live-region purpose); `socket.ts:411-420` (the drop comment, re-homed to Epic 9);
  `store-writes.test.ts:115`; `copy-rules.test.ts:127`.
- **Fulfilled and left as written (3):** `tokens.css:294`'s inventory line (this story's rule
  fulfils it rather than amending it), `token-usage.test.ts:2581` (must keep naming `c6-6`),
  `ui/README.md:966` and `:1164` (both still true — the empty push *did* join the mechanism, and
  the copy-reading residue is still reviewed at c6-6).
- **STALE PREDICTIONS, CORRECTED (2) — the sites the sweep was actually for.** Both were claims
  about what this story would do, made by earlier stories, and both were WRONG:
  `tests/fixtures/css/clean.css:76` said *"c6-6's push-replace crossfade composes two"*
  animations — the shipped crossfade is a `transition` on `opacity` driven by an attribute, not
  an `animation` at all; and `eslint.config.js:134` predicted *"a grid template in c6-6"* setting
  a CSS custom property through the `style` attribute — this story sets no inline style anywhere.
  Both comments now record what happened instead of what was expected. Neither fixture or rule
  changed; only the citation did. **This is the fifth time the ripple lesson has been proved, and
  the first time the sweep's value was a false PREDICTION rather than a stale tense.**
- **Quoted history, deliberately untouched (2):** `CardGrid/copy.ts:24-27` quotes the ledger's
  *"c4-12 and c6-6 owe the same reading"* from c4-12's vantage point. It is a quotation of what
  the disposition said at the time; the discharge is recorded in the ledger, not by editing
  another story's quote of it.

**THE COPY READING (Task 4 — the permanently-open ledger judgement, `dw:4070-4075`,
`dw:4879-4891`: *"c6-6 still owes it"*).** The one authored sentence this story puts on the glass
is `EXPERIENCE.md:71`, shipped byte for byte: **"The agent sent an empty {kind}. Nothing to show
— ask it for another pass."** It was read, and the reading is this:

- **Second person, and it addresses the reader rather than the machine.** *"ask it"* — the
  reader is the one who acts, and the pronoun points at the agent they are already talking to.
- **Blameless, and the sentence is careful about WHO did what.** *"The agent sent an empty
  suggestions"* attributes the empty push to the agent, which is where it came from, and treats
  it as a report rather than a fault. That is correct rather than generous: `types.d.ts:1103-1105`
  says an empty `items` list is legal precisely so that *"I looked and found nothing"* is
  expressible. There is no apology, no exclamation mark, and nothing that reads as an error.
- **Concrete, and the next action names its mechanism.** *"ask it for another pass"* is a thing
  the reader can do in the next sentence they type, and it names the only mechanism that can
  change the state. It does not promise a result, which would be a claim the app cannot honour.
- **One residue, and the reading is where it was found.** Filling the placeholder with the wire
  kind produces *"The agent sent an empty suggestions."* — ungrammatical, and worse for Epic 9's
  `tier_list` and `groups`. Shipping the artefact's bytes was still the right call (inventing a
  per-kind display noun would be authoring copy no artefact carries, one story before the second
  kind that needs it), but the residue is real, is declared in the copy module itself, and is
  carried to the ledger for the story that adds the second view kind. **The gate cannot see
  this** — it compares bytes, and the bytes are right.

**Planted red (Task 6).** Three plants, each run against the full suite from an uppercase drive
with the collected count validated at 1,994/1,995 before scoring, each reverted and confirmed
absent afterwards.

1. **The builder ignores its argument** (c6-4's passthrough regression, verbatim — mints an empty
   view regardless of the payload). Predicted: the delegation and empty-vs-non-empty rows.
   **Fired 11 tests across 2 files** — 6 store rows and 5 App-level rows — i.e. wider than
   predicted, in the same direction c6-5's plant went. All 11 inside this story's own blocks.
2. **The replace effect's body removed** (a new push no longer re-fires focus, the crossfade or
   the announcement). **Fired 3 tests**: the focus re-fire, the crossfade attribute cycle, and
   the App-level replace composite.
3. **A plant this story added because plant 2 revealed a coverage question, and it found a real
   hole.** Plant 2 left the live-region tests GREEN, because the announcement is render-driven
   (the heading's keyed `Fragment`) rather than effect-driven — correct by design, but it meant
   the announcement mechanism had no plant of its own. Removing the `key` **fired exactly one
   test**: the unit-level *"MUTATES the live region even when the new title is byte-identical"*.
   The App-level AC-6 test stayed green, because it replaces *"First look"* with *"Second look"*
   and two different titles mutate the region whatever mechanism is used. **A second App-level
   test was added in response** — a replace whose title is byte-identical (both pushes omit
   `payload.title`, so both get the fallback word), which is the COMMON case and the one the
   whole keyed-Fragment mechanism exists for. Suite 1,994 → 1,995.

**Gates.** `npm run lint` (eslint + stylelint), `npm run typecheck` (`tsc -b`),
`npm run format:check`, `npm test` — all clean. One real stylelint finding en route, fixed rather
than suppressed: `no-descending-specificity` on the crossfade rule, which has to follow both
`.agent-view-title` and `.agent-view-body`; the rule moved to the foot of `AgentView.css` with
the reason recorded beside it. Prettier reformatted three files.

**Suite arithmetic.** Frontend **1,937 / 71 files → 1,995 / 73 files** (+58 tests, +2 files: the
new `SuggestionsView.test.tsx` and `tests/empty-push-copy.test.ts`). Python **2,907 passed /
1 skipped / 55 deselected → unmoved**, as a frontend-only story requires.

**Rebuild.** `npm run build` → `src/companion/app/static/`, then
`uv run python -m scripts.build_plugin`. Run twice (once mid-story, once after the last edit
including the ripple sweep) and both produced identical asset hashes; the two static trees were
sha256-compared file by file and are identical across all 5 files.

**Guard pins moved, against prediction.** Predicted and moved: `socket.test.ts`'s
four-kinds-dropped pin (split into a delivery test and a three-kinds-dropped test),
`App.test.tsx:2472`'s AC-11 ignore test (same split), `COPY_MODULES`, `CONTAINERS` (29 → 31).
Predicted NOT to move and did not: `keyboard-floor.test.ts` (no new listener), the
`token-usage.test.ts` shipped-motion enumeration (opacity is not a `MOTION_PROPERTIES` member and
the duration is a token the reduced-motion block already zeroes). One unpredicted pin: the
`store-writes.test.ts` reason string, moved for tense as Landmine 1 warned it might be.

### Completion Notes List

**What shipped.** The loop the feature exists for is closed: a `suggestions` frame off the
WebSocket becomes an open agent view with no click, and a second push while the view is open
replaces the content in place.

- **Store (`agentView.ts`).** `AgentViewContent` grew from `{title, count}` to
  `{id, ts, kind, title, count, items}`, every field `schema.ts`-typed. `suggestionsViewOf` is
  the builder and it is **total** — an absent payload, absent items, and an absent/null/blank
  title all construct a valid view — and `openSuggestionsPush` is the one verb `connection.ts`
  calls. `SUGGESTIONS_VIEW_TITLE` is the fallback name, and the store is the first `src/state/`
  module in `COPY_MODULES`.
- **Wire (`schema.ts`, `socket.ts`, `connection.ts`).** Two new aliases (`SuggestionsEvent` via
  `Extract` over the union, `SuggestionItem`); `AgentSocketOptions` gained `onSuggestions`
  carrying the WHOLE event (the payload is the content — the deliberate difference from
  `onSystemEvent`, which carries a discriminant because the payload is never read); the dispatch
  switch routes `suggestions` and still drops the three Epic-9 kinds. `connection.ts` gained one
  line and still holds no `setState` and names no store.
- **Shell (`AgentView.tsx`, `AgentView.css`).** A `pushId` prop keys a replace effect that skips
  its mount run and re-fires `focusHome(heading)` plus a one-frame `[data-replacing]` flip; the
  crossfade is opacity-only over `--motion-glide`. The shell stays MOUNTED across a replace and
  `App.tsx` deliberately carries no `key` — the three reasons are written out at the effect.
  The announcement is the heading's keyed `Fragment`, which makes every replace a real DOM
  mutation even when the title is byte-identical.
- **Body (`SuggestionsView/`).** A new container, its copy module, its stylesheet and its tests.
  It renders the empty-push line for an empty push and `null` otherwise — Q1's interim shape,
  named for the view so c6-7 extends it rather than creating one.
- **Restore arm.** ARM 3 now prefers `.state-panel-headline` over the `h1` when a panel is
  showing, and only for a DISCONNECTED target — a still-connected restore target keeps winning,
  which is what keeps UX-DR46 intact.

**Acceptance criteria.** AC 1, AC 2, AC 4, AC 5 and AC 6 are implemented and pinned at unit and
App level. **AC 3 is structurally deferred to c6-7 by Brad's Q2 ruling** — its subject (a rendered
entry) does not exist in this story, c6-7's own AC 4 covers it verbatim, and the store retains the
`card_id`s either way. **AC 6's timestamp and nav-pill-marker halves are structurally deferred to
c6-8 by Q3** — the pill does not exist yet and the composition reference carries no timestamp in
the view header; what this story owns (heading, count, live-region mutation) is asserted, and the
envelope's `ts` is retained and pinned so c6-8 can render the pill time.

**Two artefact gaps declared rather than filled**, both on the ledger with homes: the empty-push
line is ungrammatical once `{kind}` is substituted (home: the story that adds the second view
kind), and `DESIGN.md` specifies a treatment for the empty-DECK line and none for the empty-PUSH
line (home: c6-7, which has to amend that artefact anyway).

**Nothing human has looked at any of this.** Block J remains ruled NOT RUN, so the crossfade, the
bloom-vs-crossfade distinction, the empty-push line's appearance and the screen-reader
de-duplication of two identical announcements all ship with **zero eyes on pixels** until the C6
manual checklist (c8-6 backstop). The announcement's jsdom-unverifiable half — whether a reader
actually HEARS the second push — is homed there by name.

### File List

**Runtime (`ui/src/`)**

- `ui/src/api/schema.ts` — modified: `SuggestionsEvent` and `SuggestionItem` aliases.
- `ui/src/state/agentView.ts` — modified: content shape, `SUGGESTIONS_VIEW_TITLE`,
  `suggestionsViewOf`, `openSuggestionsPush`, prose sync.
- `ui/src/state/socket.ts` — modified: `onSuggestions` option, dispatch arm, drop comment re-homed.
- `ui/src/state/connection.ts` — modified: the callback wired to the verb.
- `ui/src/containers/AgentView/AgentView.tsx` — modified: `pushId` prop, replace effect, keyed
  heading content, ARM 3 refinement, prose sync.
- `ui/src/containers/AgentView/AgentView.css` — modified: crossfade transitions + starting state.
- `ui/src/containers/SuggestionsView/SuggestionsView.tsx` — **new**.
- `ui/src/containers/SuggestionsView/SuggestionsView.css` — **new**.
- `ui/src/containers/SuggestionsView/copy.ts` — **new**.
- `ui/src/App.tsx` — modified: `pushId` + `SuggestionsView` children, prose sync.

**Tests**

- `ui/src/state/agentView.test.ts` — modified: builder/verb block, fixtures widened.
- `ui/src/state/socket.test.ts` — modified: delivery test, drop pin split, harness callback.
- `ui/src/containers/AgentView/AgentView.test.tsx` — modified: replace matrix, panel arm.
- `ui/src/containers/SuggestionsView/SuggestionsView.test.tsx` — **new**.
- `ui/src/App.test.tsx` — modified: c6-6 describe, `push()` id parameter, AC-11 pin split,
  fixture widened.
- `ui/tests/empty-push-copy.test.ts` — **new** (verbatim copy gate).
- `ui/tests/copy-rules.test.ts` — modified: two `COPY_MODULES` entries, header sync.
- `ui/tests/shell.test.ts` — modified: two `CONTAINERS` entries, count 29 → 31.
- `ui/tests/store-writes.test.ts` — modified: reason-string tense.
- `ui/tests/fixtures/css/clean.css` — modified: stale c6-6 prediction corrected.
- `ui/eslint.config.js` — modified: stale c6-6 prediction corrected (comment only).

**Built artefacts (never hand-edited)**

- `src/companion/app/static/**` — rebuilt (`index.html`, `assets/index-B_GTIEW2.css`,
  `assets/index-CXCA8wci.js`; the two previous asset files removed).
- `plugin/server/src/companion/app/static/**` — rebuilt mirror, sha256-verified identical.

**Records**

- `_bmad-output/implementation-artifacts/c6-6-…md` (this file).
- `_bmad-output/implementation-artifacts/deferred-work.md` — three inherited entries reconciled
  (one CLOSED, one PARTIALLY TRIGGERED, one HONOURED-and-open) + two new residues.
- `_bmad-output/implementation-artifacts/sprint-status.yaml`.

## Change Log

- 2026-08-11 — **Implemented, Tasks 0–6, status `review` (dev-story).** All 7 open questions
  ruled by Brad AS RECOMMENDED before any code. Frontend suite **1,937/71 → 1,995/73**; Python
  **2,907/1/55 unmoved** (frontend-only, as specified). The push pipe's missing segment is
  closed: `socket.ts` delivers `suggestions` with its payload to a new `onSuggestions` callback,
  `connection.ts` calls `openSuggestionsPush`, and the store's total builder turns any payload
  the wire admits into content. Replace-in-place ships as keyed RE-FIRES on a shell that stays
  mounted — the `App.tsx` element deliberately carries no `key` — with an opacity-only crossfade
  over `--motion-glide` (no new reduced-motion registration needed; `tokens.css:294`'s inventory
  line is fulfilled as written) and a keyed heading `Fragment` so a byte-identical title still
  mutates the live region. The empty-push state ships with `EXPERIENCE.md:71` byte for byte and a
  new verbatim gate; the copy READING is recorded in the Debug Log, discharging the
  permanently-open ledger judgement that named this story. Guard pins moved: the four-kinds-drop
  pin split at both socket and App level, `COPY_MODULES` +2 (incl. the first `src/state/` entry),
  `CONTAINERS` 29→31; `keyboard-floor` and the shipped-motion enumeration did not move, as
  predicted. **Three plants, and the third was added mid-run because the second revealed a real
  hole** — the announcement is render-driven, so removing the replace effect left the
  live-region tests green; a dedicated plant found that the App-level AC-6 test could not see a
  broken announcement either (it used two different titles), and a byte-identical-title test was
  added end to end in response. Ripple sweep found **2 STALE PREDICTIONS about this story made by
  earlier ones** (`clean.css` claimed the crossfade would compose two animations; `eslint.config.js`
  predicted a grid template through the `style` attribute) — neither happened, both corrected.
  Ledger: dialog-accessible-name entry **CLOSED**, `agentEventOf` kind-only **PARTIALLY
  TRIGGERED** (shape defended at the builder; item validation stays c6-7's), copy-reading entry
  **HONOURED and permanently open**, plus **two new artefact-gap residues** (the `{kind}`
  substitution is ungrammatical; `DESIGN.md` has no empty-push block). AC 3 → c6-7 and AC 6's
  timestamp/pill halves → c6-8, both structurally, per Q2/Q3. Block J still NOT RUN: zero eyes on
  pixels for the crossfade, the empty-push line or the announcement until the C6 manual checklist.
- 2026-08-11 — Story context created (create-story). 7 open questions await Brad's pre-code
  ruling. Key findings: the full push pipe exists except the dispatch segment (`socket.ts`
  drops `suggestions`; the store has no production writer); the c6-5 review's "remount
  mechanics owed to c6-6" resolves as keyed re-fires, NOT a remount (a `key` would replay the
  wrong animation, corrupt the restore target, and run the restore cleanup mid-open); both
  `SuggestionsPayload` fields are optional in the generated types so defensive construction
  is mandatory independent of the malformed-frame case; a byte-identical fallback title
  announces nothing without a real DOM mutation; the composition reference has no timestamp
  in the agent-view header, so AC 6's timestamp/pill halves belong to c6-8. ~30 `c6-6`
  ripple sites enumerated up front.
