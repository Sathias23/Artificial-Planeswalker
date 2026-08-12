---
baseline_commit: f390a46
---

<!--
  Story context created 2026-08-12 by create-story (ultimate context engine analysis).
  Sources: epics-companion-app.md (Story 6.8 :2926-2961, Epic 6 :2668-2673/:895-907, UX-DR28
  :492-495, UX-DR33 :547-551, UX-DR34 :555-559, UX-DR37 :574-578, UX-DR39 :585-591, UX-DR40
  :593-640, UX-DR43 :666-668, UX-DR44 :670-675, UX-DR45 :677-681, UX-DR46 :683-686, UX-DR47
  :688-689, confirmed rulings :704-726, Story 9.1 :3475-3477, kind enum :2401), DESIGN.md
  (components.nav-pill :260-269, prose :522, accent doctrine :437/:503, label type :66-72/:472,
  spacing-drift ban :484, header layout :486, mock scope :515), EXPERIENCE.md (:38-42, :73, :89,
  :113, :125, :131-132, :139-147, :154-156, :207-212, :227), the composition reference
  (Planeswalker Companion.dc.html :33-51), shipped ui/ source at f390a46 (agentView.ts, socket.ts,
  connection.ts, App.tsx, AppShell.tsx/.css, AgentView.tsx/.css, SuggestionsView.tsx, cards.ts,
  guard suites), c6-7 story record (plants, review, Greptile P1s), c6-6/c6-5 records,
  deferred-work.md (:49, :45, :76, :4906-4916), review-accessibility.md:32, sprint-status F1
  action item, src/companion/contracts.py (kind Literals :1054-1271).
-->

# Story c6-8: Agent views nav — unread markers, re-open, and kind switching

Status: done

## Story

As Brad who dismissed a view and wants it back,
I want a pill in the header for each kind of thing my agent has sent,
So that nothing the agent showed me is ever more than one click away.

## The story in one paragraph

The header's last placeholder — `AppShell.tsx:200`'s `'Agent-view nav pills land here — c6-8.'`,
on the glass on **every** surface since c2-6 and the last story-key-shaped string the F1 sweep can
find — is displaced by the agent-views nav: one pill per view kind, **generic over the closed
four-kind enum** (`suggestions | swaps | tier_list | groups`), because Story 9.1's own AC depends
on the Swaps pill "becoming active automatically" with no nav work (`epics:3475-3477`). A pill is
quiet (text-tertiary, not focusable, tooltip *"Your agent hasn't sent this yet."*) until its kind
receives a push this session; thereafter active, showing the last push's time, and carrying the
accent unread dot until its view is opened. Click/Enter re-opens the retained view — a real
remount, so the shell's bloom/focus/restore effects re-fire for free, hydration re-fires off the
`items`-keyed effect for free, and close returns focus to the pill for free (the mount effect
captures `document.activeElement`). The store grows the per-kind retention and unread flags its
own header says it lacks *on purpose* ("Those are c6-8's… they EXTEND this shape rather than
reshape it", `agentView.ts:44-46`), and the kind-switching state machine — a different-kind push
displaces the open view and marks the displaced kind unread, a push is never silently swallowed —
is built and proven at the store/App level with a synthetic second kind, while the socket's
dispatch switch **keeps dropping** `swaps`/`tier_list`/`groups` (Epic 9 pairs each tool with its
view precisely so a push never arrives that the UI cannot display; accepting one here would
recreate that bug from the other side). Frontend-only: Python 2,907/1/55 must not move; frontend
2,039/73 must grow; tokens hold at 70 (every nav-pill value resolves to a shipped token).

## Acceptance Criteria

*(Verbatim from `epics-companion-app.md:2932-2961`, numbered for citation.)*

1. **Given** a kind that has received no push this session **When** its pill renders **Then** it
   is quiet — `text-tertiary`, no hover glow, **not focusable** — with the tooltip "Your agent
   hasn't sent this yet." (UX-DR28, UX-DR33)
2. **Given** a kind that has received a push **When** its pill renders **Then** it is active and
   shows the last push's time (UX-DR28)
3. **Given** a view has an unread push **When** its pill renders **Then** it carries the accent
   unread dot until that view is opened (UX-DR28)
4. **Given** an active pill **When** it is clicked or activated with Enter **Then** its view
   re-opens with the same content, **re-hydrated against current card data** — stale ids degrade
   to unknown-card placeholders (UX-DR28) **And** nothing is re-requested from the agent
5. **Given** a view of one kind is open **When** a push of a **different** kind arrives **Then**
   the view switches to the new kind and the previous kind's pill is marked unread — **a push is
   never silently swallowed** (UX-DR34, SC-1)
6. **Given** the pills **When** the Tab order is walked **Then** they sit in the header nav,
   ahead of the card grid (UX-DR40)
7. **Given** several tabs are open **When** pushes arrive **Then** each tab keeps its own view
   state and unread markers — divergence between tabs is accepted, not solved (UX-DR37)

**Reachability honesty this story must record, not hide:** with the socket dispatch unchanged
(Q1), only `suggestions` can arrive in Phase 1 — so in production, exactly one pill can activate,
and AC 5's displacement (the only unread *setter*, see Dev Notes) cannot fire until Epic 9 ships
a second kind. AC 5 is therefore proven at the store/App seam with a synthetic second kind (the
c6-6 AC-3 structural-deferral precedent: the mechanism is built and tested here; its first
production traversal belongs to Story 9.1, whose own AC already banks on it). AC 2/3/4 are fully
reachable now via `suggestions`.

**Scope boundaries (build none of these):** the other three *views* and their tools are Epic 9
(`epics:3427-3435` — each story pairs tool with view); the 250 ms budget measurement is c6-9
(`epics:2963-2998`); session history (FR-18, "extend the nav, or a strip in each view's header")
is Epic 10 and explicitly undecided — build nothing that forecloses it, which the flat pill row
does not. No wire change of any kind: `contracts.py`, `openapi.json`, `types.d.ts` untouched.

## Tasks / Subtasks

- [x] **Task 0 — Baselines, branch, and grep dispositions** (protects everything)
  - [x] Branch `feat/companion-c6-8-agent-views-nav` cut from `feat/companion-c6` at or after
        `f390a46` (the c6-7 merge record).
  - [x] Frontend baseline: `npm test` from an **uppercase** drive path; expect **2,039 passed /
        73 files** (2,036 + the 3 Greptile-fix tests from `00f401f`); validate the collected
        count before trusting any run (Landmines 1).
  - [x] Python baseline: `uv run pytest -m "not integration"` — expect **2,907 passed / 1
        skipped / 55 deselected**; unmoved at the end (no ruling can move it — Q1's alternative
        is also frontend-only).
  - [x] `grep -rn "c6-8"` across `ui/src/`, `ui/tests/`, `ui/README.md`, `src/`, `docs/`,
        `_bmad-output/` — **~45 known sites** (list in Dev Notes); build the dispositions table.
        Two hits are a recorded TYPO, not this story's prose (`ui/README.md:1501` records that
        `token-usage.test.ts:400`'s "c6-8's curve axis" means **c4-8**) — disposition, don't
        fulfil. Seven stories have written toward this one; expect more sites than predicted
        (seventh story running).
- [x] **Task 1 — The DESIGN.md amendment, FIRST** (AC 1, AC 2, AC 3; c4-12/c6-7 order)
  - [x] Repair `components.nav-pill.padding: '7px 14px'` → `'{spacing.2} {spacing.3}'` —
        `DESIGN.md:484` names 14 and 7 **by name** as "drift, not spec", and Brad's c6-5 Q4
        ruling already shipped exactly these values on the close pill, *"DESIGN.md's nav pill…
        so whatever this rule settles is also c6-8's spec"* (`AgentView.css:144-150`). Verify
        whether that ruling's recorded amendment already touched the frontmatter; if not, this
        is it, annotated inline per the three shipped precedents (`legality-row`, Panel, Badge).
  - [x] Extend `components.nav-pill` with the states the component description promises and the
        block omits: `quiet-foreground: '{colors.text-tertiary}'` (quiet = base pill, no hover
        rule, per `EXPERIENCE.md:73`), `time` typography + colour (per Q4's ruling), and
        `unread-dot` size beside its existing colour (per Q6's ruling). Values are Brad's via
        Q4/Q6; the dev writes the amendment; review reads it as the citation source.
  - [x] **Touch no EXPERIENCE.md copy row** — the tooltip string is consumed byte-for-byte from
        `EXPERIENCE.md:73` (typographic apostrophe U+2019, trailing period); a new copy gate
        pins it (Task 5). If Q7 rules the empty-push-line reword in, that amendment (and its
        re-gating) happens here too, in the same commit.
- [x] **Task 2 — The store extension** (AC 2, AC 3, AC 4, AC 5; the seam `agentView.ts:44-46`
      pre-cut)
  - [x] Extend the **7th store in place** — no 8th store (`store-writes.test.ts` is set-derived:
        extending costs nothing, a new `create()` costs a registry entry nothing justifies).
        Recommended shape (dev may refine within these constraints): keep `status` + `content`
        exactly as shipped; add `retained: Partial<Record<AgentViewKind, AgentViewContent>>`
        and `unread: Partial<Record<AgentViewKind, true>>`, where `AgentViewKind` is the
        four-member view-kind union derived in `schema.ts` (the only file allowed to alias
        wire-derived names — Landmine 11). Widen `AgentViewContent['kind']` to it, discharging
        `agentView.ts:110-115`'s *"c6-8 widens it"* prediction.
  - [x] Verbs (all writers stay inside this module — the store-writes guard): `openAgentView`
        additionally records `retained[content.kind] = content`, clears `unread[content.kind]`,
        and — when a **different** kind's view is currently open — marks that displaced kind
        unread (AC 5's whole state machine; see Dev Notes for why displacement is the *only*
        unread setter). New `reopenAgentView(kind)`: no-op unless `retained[kind]` exists;
        sets it as `content`, opens, clears its unread flag. `closeAgentView()` stays
        status-only — **dismissal never sets unread and never clears retention** (UX-DR34).
  - [x] Pill vocabulary: per c6-6's review decision (Brad kept `SUGGESTIONS_VIEW_TITLE` in this
        module *"as the c6-8 precedent"*), add the four-kind label table here —
        `Suggestions / Swaps / Tier list / Card groups` (canonical sentence-case spellings,
        `EXPERIENCE.md:39-42`; `{typography.label}` uppercases at render). `SUGGESTIONS_VIEW_TITLE`
        becomes (or is re-exported from) the table's `suggestions` entry — one word, one owner.
        Update the `COPY_MODULES` entry reason; Epic 9's builders inherit the same words as
        fallback titles.
  - [x] Selectors for the pills: per-kind hooks (retained-content presence, `ts`, unread flag)
        shaped so a push re-renders only the affected pill (the `useIsLiveTarget` precedent).
  - [x] Existing tests must stay green untouched: `agentView.test.ts:135` (retains `ts`/`id`)
        and `:269-274` (re-opens the SAME content) were written for this story.
- [x] **Task 3 — The `AgentViewsNav` container** (AC 1, AC 2, AC 3, AC 4, AC 6)
  - [x] New `ui/src/containers/AgentViewsNav/{AgentViewsNav.tsx, AgentViewsNav.css,
        AgentViewsNav.test.tsx, copy.ts}` (`ui/README.md:574` homes c6-8 in containers by name;
        `src/components/` is CLOSED). Rendered into `AppShell`'s existing `nav` prop from
        `App.tsx` — **`AppShell.tsx` is not edited** (the displacement ruling, 11th
        application; the placeholder string survives in the shell for `AppShell.test.tsx`).
  - [x] Four pills, one per `AgentViewKind`, in the ruled order (Q3), each a real
        `<button type="button">` (UX-DR47). Group semantics per Q5 (recommend: fill the
        existing `<div className="app-shell-nav">` slot with the "Agent views" micro kicker +
        the pill row — no `<nav>` landmark, which UX-DR44's enumeration does not authorize).
  - [x] Quiet pill (AC 1): `disabled` — **never `tabindex="-1"`** (Landmine 2) — with the
        tooltip and its keyboard/SR parity per Q2's ruling; no click handler consequence
        (disabled buttons don't fire), no hover glow (no hover rule applies).
  - [x] Active pill (AC 2): label + `<time dateTime={ts}>` rendering the last push's time per
        Q4's ruling; Click/Enter → `reopenAgentView(kind)` (Enter/Space = the button's native
        click, UX-DR39 — **no `onKeyDown`**, dw:49 names this story's pills).
  - [x] Unread dot (AC 3): per Q6's ruling — `aria-hidden` presentational dot + "unread" in
        the button's accessible name via visually-hidden text (UX-DR29's "the dot never
        carries the state alone" precedent; UX-DR45 authorizes no new live region — the pill
        must NOT announce).
  - [x] Re-open (AC 4): `reopenAgentView(kind)` → `App.tsx` renders the overlay → `AgentView`
        MOUNTS (bloom, focus-to-heading, restore-capture all re-fire — zero new code) →
        `SuggestionsView`'s `items`-keyed hydration effect re-fires → stale ids land
        `unknown-card` via the cache's existing terminal refusal. Verify, don't re-implement.
        Close returns focus to the pill (`EXPERIENCE.md:146` — free via the shell's
        `document.activeElement` capture; test it, don't build it).
- [x] **Task 4 — Stylesheet** (AC 1, AC 2, AC 3, AC 6)
  - [x] `.agent-views-nav-pill` (flat kebab-case) mirroring the shipped close-pill rule
        (`AgentView.css:144-195` — its own comment says it IS this story's spec): base
        `surface-panel` / `border-strong` / `--radius-pill` / `--space-2 --space-3` padding /
        `--type-label` **with `letter-spacing: var(--tracking-label)` and
        `text-transform: uppercase` in the same block** (the companions gate) /
        `min-width: 24px; min-height: 24px` **both axes** — and JOIN
        `keyboard-floor.test.ts:495`'s `DECLARES_MIN` list, which names c6-8's pills verbatim.
  - [x] Hover **and** focus-visible share one rule (`border-color: var(--accent-dim)` — legal
        on `surface-panel`, 3.05:1, per the c6-5 ruling — `color: var(--accent-bright)`,
        `box-shadow: var(--glow)`), plus the standard `outline: var(--focus-ring-width) solid
        var(--focus-ring)` on focus-visible only. `keyboard-floor.test.ts:397-398` narrowed its
        ring guard *specifically so this rule could ship* — accent-bright text is legal, but
        accent-bright in `outline`/`outline-color`/`box-shadow` is red.
  - [x] Quiet state: `:disabled` arm — `color: var(--text-tertiary)` (≈5.4:1 on
        `surface-panel`, computed at story creation; verify against DESIGN.md's contrast
        method), hover/focus rule not applied. Timestamp: `--type-micro` + `--tracking-micro`
        + `uppercase` companions in one block, `--text-tertiary`. Dot: `--accent`, size per Q6.
  - [x] Transitions: duration **tokens only**, properties limited to
        color/border-color/box-shadow/background-color — mechanically reduced-motion-neutral,
        so the UX-DR42 inventory and the shipped-motion enumeration should **not** move. No
        steady-state glow (DESIGN.md:503: "glows are moments, not steady states"), no arrival
        animation (nothing specs one; adding motion costs an inventory entry — don't).
  - [x] Every value resolves to a shipped token ⇒ `tokens.test.ts:346` holds at **70**. Any px
        literal (24px min, dot size) carries its DESIGN.md citation within a sentence.
- [x] **Task 5 — App wiring + tests** (all ACs)
  - [x] `App.tsx`: pass `nav={<AgentViewsNav />}` (the container reads the store itself —
        props-free, like `ConnectionPill`); the overlay body becomes kind-keyed per Q1's
        ruling (`suggestions` → `<SuggestionsView>`, the only arm today; the comment at
        `App.tsx:626` predicted "c6-8 is where a second one makes this a switch").
  - [x] `AgentViewsNav.test.tsx`: pill-per-kind anatomy; quiet = disabled + no handler firing +
        tooltip/description per Q2; active shows the formatted `ts`; unread dot + accessible
        name; labels are the registered vocabulary; no `tabindex` in any spelling; every
        behavioural assert paired with a non-vacuity control **including an absence-only
        check's positive twin** (c6-7's plant-3 lesson, standing practice).
  - [x] `agentView.test.ts`: retention map, unread lifecycle (open-clears, displacement-sets,
        close-never-touches), `reopenAgentView` no-ops without retention, synthetic-kind
        displacement (AC 5's store half).
  - [x] `App.test.tsx` (the established harness): push → suggestions pill activates with time;
        dismiss → pill stays active, **no** unread dot (dismissal ≠ unread); pill click →
        view re-opens, same content, heading focused, **request-log shows re-hydration
        `GET /api/cards/{id}` and nothing else re-requested** (AC 4's "nothing is re-requested
        from the agent" = no new push needed, prove via socket silence + request log); close →
        focus returns to the pill; stale-id re-open degradation (evict/seed the cache between
        open and re-open); synthetic different-kind push at the store seam → view switches,
        previous pill unread (AC 5's App half); Tab-order walk: skip link index 0, pill after
        it, before the first tile (AC 6, UX-DR40); cold-open: **no focusable pill exists**
        (UX-DR40's "this stop never exists").
  - [x] **The F1 inversion**: `App.test.tsx:860`'s `toContain('c6-8')` flips to the zero-keys
        assertion its own comment (`:838-857`) was written to become; `:1968-1971`'s
        exactly-one count goes to zero. The corridor pins (`:1766/:1774/:1777/:1781/:1851`)
        hold on push-free fixtures (quiet pills are not focusable) — re-derive any fixture
        that pushes; understand every moved count before touching it.
  - [x] New copy gate (the c2-9 pattern): tooltip byte-gated against `EXPERIENCE.md:73`;
        labels gated as authored copy. `COPY_MODULES` +entries with reasons
        (`copy-rules.test.ts:123-130`'s own instruction); CONTAINERS +2 entries
        (`shell.test.ts:2119` count moves) with exhaustive import lists.
  - [x] Predicted NOT to move: `tokens.test.ts` (70), `store-writes.test.ts` (derived),
        `posture.test.ts`, `AppShell.test.tsx` (shell untouched), `socket.test.ts:675`'s
        three-kinds-dropped pin (Q1 keeps it true), every existing copy byte-gate,
        shipped-motion enumeration. If one goes red, stop and understand why first.
- [x] **Task 6 — Planted red, gates, artifacts, ripple, ledger**
  - [x] Plant 1 (passthrough, the c6-4/c6-6/c6-7 verbatim plant): pills render from a constant
        ignoring store state — predict anatomy/unread/time rows red, confined to this story's
        blocks. Plant 2: `closeAgentView` also clears retention — predict the re-open flows
        and the shipped `:269-274` re-open test red (proves the AC-4 chain is real). Plant 3:
        displacement never sets unread — predict the AC-5 store + App halves red, **with the
        non-vacuity twin proving the assert can see unread at all**. Predictions recorded
        before each run; full runs, uppercase drive, collected count validated; **stage
        everything before each plant** (c6-7 lost the component to an unstaged
        `git checkout`); revert, `git diff --exit-code` clean.
  - [x] `npm run lint`, `npm run typecheck`, `npm run format:check`; `npm test` strictly
        > 2,039; Python 2,907/1/55 unmoved.
  - [x] Runtime diff ⇒ rebuild: `npm run build` (→ `src/companion/app/static/`, never
        hand-edit) then `uv run python -m scripts.build_plugin`; sha256-verify both mirrors;
        rebuild AFTER the last edit including review patches.
  - [x] Ripple sweep — grep the CLAIM, not the sentence (seven-times-learned): the ~45 sites'
        dispositions; rewrite UX-DR40's enumeration in `epics-companion-app.md:597` (the
        c4-11/c5-7 precedent — the parenthetical unbuilt-stop note becomes a real, shipped
        stop with its conditional); `ui/README.md:1359` + `:1466` to past tense; the two
        curve-axis TYPO sites dispositioned; `App.tsx:526-530`/`:600-603` prose to truth;
        `agentView.ts` header's four non-features list updated (two of the four just shipped).
  - [x] Ledger reconciliation in `deferred-work.md`: dw:49 (capture-Esc starves synthetic
        handlers — *"STAYS OPEN for c6-8's pills"*) — annotate HEEDED (pills ship no
        `onKeyDown`; they are also under the scrim while a view is open, unreachable);
        dw:45 (`FOCUSABLE_SELECTOR` tabindex gap) — annotate NOT TRIGGERED (pills sit outside
        the shell, no roving tabindex); dw:4906-4916 (F1's last key) — annotate DISPLACED,
        rendered count now zero, gate itself stays c8-5's; dw:76 (the `{kind}` article grammar)
        — disposition per Q7's ruling. File the Q2 contradiction repair as a new entry if Brad
        rules option (a) (the artefact still says "tooltip" while the shipped mechanism is
        name/description — Story 8.3's PRD reconciliation should see it).
  - [x] Dev Notes KB self-check (10–20 KB band); record suite arithmetic before/after.

*(Per the standing workflow: implement Tasks 0–6, set status `review`, STOP — Brad runs the
three-layer review and raises the PR into `feat/companion-c6`.)*

### Review Findings

*(bmad-code-review, 2026-08-12 — Blind Hunter, Edge Case Hunter, Acceptance Auditor, run in
parallel against the uncommitted diff at baseline `f390a46`. Acceptance Auditor independently
re-ran the frontend/Python suites, lint/typecheck/format gates, and a mirror sha256 diff, and
reproduced every Dev Agent Record claim exactly — zero findings from that layer.)*

- [x] [Review][Patch] A retained push whose `ts` is `undefined` (a malformed backend frame —
  the same "absent `ts`" case `pushTime.ts`'s own docstring names as reachable, since
  `agentEventOf` validates only the `kind` discriminant) collapses the pill into the *"never
  pushed"* (quiet/disabled) render branch instead of the *"active, no time shown"* branch.
  `useAgentViewPushTime` (`ui/src/state/agentView.ts:489-490`) reads
  `state.retained[kind]?.ts ?? null`, and `AgentViewPill` (`ui/src/containers/AgentViewsNav/
  AgentViewsNav.tsx:144`) branches on `pushedAt === null` — so an entry that legitimately
  exists in `retained[kind]` but carries no `ts` is indistinguishable from a kind that has
  never pushed at all. The content is still retained and still auto-opened once on arrival,
  but once dismissed it becomes permanently unreachable via its pill for the rest of the
  session (the pill renders `disabled`), which is a real deviation from UX-DR34's *"the view
  remains re-openable for the rest of the session"* and, more narrowly, defeats the very
  defence `pushTimeLabel`'s docstring says it exists for (that function's guard against a
  `RangeError` on an absent `ts` is never even reached, because the selector already routed
  around it). `pushTimeLabel` itself already handles a present-but-unparseable `ts` string
  correctly (`new Date(...)` → `NaN` → `null` → active pill, no `<time>`) — only the
  key-entirely-absent case is mishandled, one layer up. Fix: decide quiet vs. active on
  `retained[kind]` presence (e.g. `kind in retained` or `retained[kind] !== undefined`) rather
  than on `.ts` presence, and let a missing/invalid `ts` degrade only the `<time>` rendering
  inside the active branch, consistent with the per-field degradation pattern c6-7 established.
  [`ui/src/state/agentView.ts:489-490`, `ui/src/containers/AgentViewsNav/AgentViewsNav.tsx:144`]

- [x] [Review][Defer] Native `title` tooltips are widely reported not to fire on `disabled`
  HTML buttons in Chromium — if that holds here, the quiet pill's pointer-hover channel of
  Q2's "dual mechanism" (both `title` and a visually-hidden `aria-describedby` description) is
  silently inert in the majority browser, leaving only the accessibility-tree half actually
  reachable by a sighted, non-screen-reader mouse user. Already identified and ledgered by the
  dev during this same story (`deferred-work.md`, "Deferred from: c6-8-…", item 5: *"whether
  the browser renders a `title` tooltip on a `disabled` button at all, which varies by engine
  and is the pointer half of Q2's dual mechanism"*), homed to the C6 manual checklist (c8-6).
  No new ledger entry added — this finding confirms and cross-references the existing one
  rather than duplicating it. [`ui/src/containers/AgentViewsNav/AgentViewsNav.tsx:156`]
  — deferred, pre-existing (already tracked; home: c8-6 manual checklist)

- [x] [Review][Defer] `UX-DR28` and the epic's `AC 1` still describe the quiet pill's copy as a
  single "tooltip," which is the same shape the 2026-07-22 accessibility review already caught
  once on the connection pill (repaired there by amending `UX-DR29`). This story repairs the
  *code* under Q2's ruling (both `title` and `aria-describedby`) but not the *source artefact*,
  so the next reader of `UX-DR28`/`AC 1` alone meets the same contradiction again. Already
  identified and ledgered by the dev during this same story (`deferred-work.md`, "Deferred
  from: c6-8-…", item 1), homed to Story 8.3's PRD reconciliation. No new ledger entry added —
  this finding confirms and cross-references the existing one rather than duplicating it.
  [`epics-companion-app.md` UX-DR28; `DESIGN.md:522`]
  — deferred, pre-existing (already tracked; home: Story 8.3)

*(12 findings dismissed as noise, already-mitigated-by-test, or matching an explicit ruling
already made in this story's own spec — not reproduced here. Full detail available on
request.)*

## Dev Notes

### What is already shipped (verified at story creation — every seam was cut for this story)

- **The slot**: `AppShell.tsx:89-90` declares `nav?: ReactNode` ("The agent-view nav pills,
  header far right. c6-8."); `:200` renders `slot(nav, 'Agent-view nav pills land here —
  c6-8.')`; `AppShell.css:110-126` already ships the alignment (`.app-shell-nav { display:flex;
  align-items:center; gap: var(--space-3); min-width:0; margin-left:auto }`) so this story
  **FILLS the header rather than restructuring it** — `AppShell.tsx` is not edited, and the
  placeholder string stays in the shell (displaced, not deleted), keeping `AppShell.test.tsx`
  green untouched.
- **The store retained everything on purpose.** `AgentViewContent {id, ts, kind, title, count,
  items}` — `ts` is *"c6-8's pill time"* (`agentView.ts:108`), `kind` is *"c6-8's kind-switching
  discriminant"*, and items retention is *"what makes c6-8's 're-hydrated against current card
  data' possible without a second push — the ids and reasons are here, and the ART is always
  re-fetched rather than retained"* (`:90-98`). `closeAgentView()` writes `status` only
  (`:272`); `resetAgentView()` is the ONLY content-nuller and is test-only. The kind type is
  deliberately narrow — *"c6-8 widens it"* (`:110-115`).
- **Re-open is a real mount, and everything re-fires.** `App.tsx:594-630` renders the overlay
  only while `useOpenAgentView()` is non-null, so re-opening MOUNTS `AgentView`: entry bloom,
  focus-to-heading, and restore-target capture (which grabs `document.activeElement` — the
  pill) all run again with zero new code; `agentView.ts:250-255` documents exactly this.
  `SuggestionsView.tsx:416-425`'s hydration effect is **"KEYED ON `items`, NOT ON MOUNT"** and
  fires per unique id through `hydrateCard`, whose terminal `unknown` entries and `''` refusal
  route stale ids into the shipped unknown-card degradation with zero requests re-attempted
  for terminal ids and a real re-fetch for evicted ones. AC 4 is a *verification* burden here,
  not an implementation one.
- **The socket seam is deliberately narrow.** `socket.ts:420-453` dispatches
  `suggestions → onSuggestions(event)` (the whole envelope) and **drops**
  `swaps`/`tier_list`/`groups` at `:441-443` (pinned by `socket.test.ts:675`); `:209-225` says
  *"c6-8 owns kind-switching, and widening this signature before a second view exists would be
  a shape invented for a caller nobody has written"* — see Q1 for why this story still leaves
  the dispatch untouched. `connection.ts:124` wires `onSuggestions: openSuggestionsPush`.
- **The pill's CSS already exists once.** The close pill (`AgentView.css:144-195`) implements
  DESIGN.md's nav-pill block, and its own comment says *"whatever this rule settles is also
  c6-8's spec"* — including Brad's c6-5 Q4 padding ruling (`--space-2 --space-3`, not the
  spec's 7px/14px) and the hover/focus shared rule the keyboard-floor ring guard was narrowed
  for (`keyboard-floor.test.ts:397-398` names c6-8's pills as the reason). `ConnectionPill.css`
  is the pill-with-dot structural model. Every needed token ships: `--accent` (:108),
  `--accent-bright`, `--accent-dim`, `--glow` (:196), `--radius-pill`, `--type-label`/
  `--tracking-label`, `--type-micro`/`--tracking-micro`, `--text-tertiary`. **Tokens hold
  at 70.**
- **The vocabulary precedent**: `SUGGESTIONS_VIEW_TITLE = 'Suggestions'` lives in
  `agentView.ts:63-79` because *"c6-8's nav pill needs the same word for the same kind, so a
  constant owned by any single container would be the wrong address for the second reader"* —
  Brad's c6-6 review decision kept it there **as the c6-8 precedent**. The other three labels'
  canonical spellings: `Swaps`, `Tier list`, `Card groups` (`EXPERIENCE.md:39-42`, Flow 3, the
  mock).
- **The forward tests already written for this story**: `agentView.test.ts:135` (*"retains `ts`
  and `id` unread — c6-8's pill time"*) and `:269-274` (*"re-opens the SAME content with no
  second push"*). They stay green; the file gains the retention/unread coverage.
- **The wire kinds** (`contracts.py:1054-1271`, `types.d.ts:1788`): agent-view kinds
  `suggestions | swaps | tier_list | groups`; system kinds `deck_changed |
  active_deck_changed`. `schema.ts` already aliases `AgentEventKind` (:264) and
  `SuggestionsEvent` (:284); a view-kind subset alias belongs there and nowhere else
  (Landmine 11). Every envelope is `{id, ts, kind, payload}`; `ts` is the documented ordering
  key, timezone-aware ISO.

### The visual spec, verbatim, and its declared gaps

`DESIGN.md:260-269` (`components.nav-pill`): background `{colors.surface-panel}`, border
`1px solid {colors.border-strong}`, radius `{rounded.pill}`, padding `'7px 14px'` ⚠️, foreground
`{colors.text-secondary}`, hover-border `{colors.accent-dim}`, hover-foreground
`{colors.accent-bright}`, hover-glow `{components.elevation.glow}`, unread-dot `{colors.accent}`.

`DESIGN.md:522`: *"**Agent views nav** (the nav pill) — the agent-view controls in the header,
and the 'Close · esc' control inside a view. `{components.nav-pill.padding}` at `{rounded.pill}`,
`{typography.label}`. Hover/focus: border to hover-border, text to hover-foreground, plus
hover-glow. A pill whose view has an unread push carries a `{components.nav-pill.unread-dot}` —
the accent's meaning is 'the agent put something here', so an unread push is exactly what it
marks."*

The mock (`Planeswalker Companion.dc.html:33-51`) shows the arrangement: identity block →
badges → `margin-left:auto` → an "Agent views" micro/`text-tertiary` kicker → the pill row at
8px gaps. **Read it for arrangement only** — it renders THREE pills (`Card groups`, `Swaps`,
`Tier list`), omits Suggestions (the only P0 kind), shows no timestamp, no unread dot, no quiet
variant, and its pills are `<div onClick>` (banned outright by UX-DR47). `DESIGN.md:515` lists
the nav pill among neither the demonstrated nor the caveated components.

**Declared gaps this story's Task 1 amendment + Q rulings fill:** padding is named drift
(`DESIGN.md:484` — Q-free, precedent ruled); no timestamp typography anywhere (Q4); no unread-dot
geometry or aria (Q6); no quiet-state visual beyond `EXPERIENCE.md:73`'s "text-tertiary, no hover
glow"; no tooltip component exists anywhere in the system (Q2); no landmark assigned to the
header nav by UX-DR44 (Q5); pill order differs across all three sources (Q3).

**Contrast doctrine**: the pill sits on `surface-panel`, where `accent-dim` is *legal* (3.05:1,
the c6-5 close-pill ruling — `AgentView.css:25-37`); the overlay ban does not apply here.
Quiet-state `text-tertiary` on `surface-panel` computes ≈5.4:1 (passes 4.5:1; verify with the
repo's method — the pair is not yet in DESIGN.md's verified table).

### Ruled — settled, do not re-derive

1. **The nav is generic over the closed kind enum** — Story 9.1's AC (`epics:3475-3477`): the
   Swaps pill *"becomes active automatically, because the nav is generic over the closed `kind`
   enum from Story 5.1"*. Four pills always render; quiet is a first-class state with its own
   copy (UX-DR33's ninth state).
2. **Push arrival behaviour** (UX-DR34, confirmed ruling 1 of 2026-07-25): auto-open; same-kind
   replace in place (c6-6, shipped); different-kind switch + previous pill unread; dismissal
   never clears content; pills are the re-open path, *never the only path*.
3. **Unread's one setter.** A push always auto-opens its own view ⇒ its own kind is read on
   arrival. Dismissal is Brad's act ⇒ never unread. The only way content becomes unread is
   AC 5's displacement (different-kind push while another view is open). Opened-by-pill clears
   it. This tiny state machine is the whole feature — encode it in the store, not the
   component.
4. **The pill must not announce.** UX-DR45 enumerates exactly three live regions — the
   connection pill, the agent-view heading, the pin region — and the nav pill is not one.
   UX-DR43 is satisfied by the heading + timestamp + marker *updating*, not announcing.
5. **No focusable quiet pill** (UX-DR28, UX-DR40's cold-open "this stop never exists"), and
   **quiet ≠ `tabindex="-1"`** (Landmine 2). Active pills are ordinary buttons in document
   order between the skip link and the grid.
6. **Pills are unreachable while a view is open** — the full-window scrim covers the header
   (UX-DR38's one-level stack) and Tab is trapped inside the dialog. Kind switching while a
   view is open is therefore *only* push-driven (AC 5), never pill-driven; a pill click always
   starts from a closed-view state. Tests must not pretend otherwise.
7. **Focus return to the pill on close is the shell's** (`EXPERIENCE.md:146`; the mount-time
   `document.activeElement` capture) — prove it, don't build it.
8. **R2 standing rule**: no forward-looking cross-module prose; the fulfilled `c6-8` comments
   get prose-synced to truth in this diff.
9. **The static/plugin rebuild rule** and **merge ≠ release** (story PR → `feat/companion-c6`,
   Greptile per story; dev stops at `review`; no tag/CHANGELOG until c8-4).

### Landmines specific to this story

1. **Windows false-red + the two flakes**: `npm test` from a lowercase drive letter resolves no
   vitest config (~67 failed suites); the cold-start `lint-gates.test.ts` timeout re-runs warm;
   the worker-fork crash silently drops a whole file (`72 passed (73)`) — validate the
   **collected count** before scoring any run, especially the plants.
2. **`disabled`, never `tabindex="-1"`.** `keyboard-floor.test.ts:753-780` pins exactly ONE
   named `tabindex` exception in the app (`focusHome`); a quiet pill via `tabindex="-1"` is a
   second exception and a red guard. `disabled` is also what `AgentView.tsx:110`'s trap
   selector already excludes, and what keeps UX-DR40's "nothing carries a tabindex" true.
   (A pill can never go active→quiet, so no focused element ever becomes disabled underfoot.)
3. **No `onKeyDown` on pills** (dw:49 names them): the document-capture Esc `stopPropagation()`
   starves React's synthetic delegation while a view is open. Enter/Space are the button's
   native click. Pills also sit under the scrim while a view is open — a keyboard handler
   there would be triply dead.
4. **The keyboard-floor trio for any new focusable**: join `DECLARES_MIN` (`:495` — min 24px
   BOTH axes, in the stylesheet); exactly one of the two focus treatments (`KNOWN_SURFACE`
   outline arm); real `<button>`, never a div-with-handler (`:459-473`). The ring guard
   (`:340-357`, narrowed at c6-5 *for this story*) allows accent-bright as text colour but
   bans it inside `outline`/`outline-color`/`box-shadow`.
5. **Type-role companion gates**: `--type-label` needs `letter-spacing` + `text-transform` in
   the SAME rule block; `--type-micro` likewise plus its tracking; split companions fail by
   name (`findRoleWithoutCompanions`).
6. **Timestamp determinism** (if Q4 rules a locale/timezone-sensitive format): jsdom inherits
   the host TZ/ICU — a literal `"14:32"` expectation is a machine-dependent test. Compute the
   expected string through the same formatter, or pin `TZ` for the suite; never assert bytes
   of a locale render. No ticking timer under any ruling — a "2m ago" that self-updates is a
   new re-render source and an update surface nothing specs (UX-DR43 requires updates only on
   a new push).
7. **Wire-name ban** (`wire-contract.test.ts`, bit c6-7 by name): local types may not re-spell
   backend schema names. The view-kind union derives in `schema.ts` (e.g.
   `AgentViewKind = Exclude<AgentEventKind, SystemEventKind>`-shaped) and is imported from
   there; don't spell `SwapsPayload`/`TierListEvent` in the container or store.
8. **Copy is byte-gated at the source artefact**: the tooltip must match `EXPERIENCE.md:73`
   byte-for-byte — typographic apostrophe **U+2019** ("hasn't"), trailing period. The labels
   are authored copy → `copy.ts` (zero imports) or the store's vocabulary table, registered in
   `COPY_MODULES` with reasons. Nothing user-facing may be assembled at runtime from
   fragments (copy-rules residue 3).
9. **The F1 inversion is deliberate and must be loud.** After `nav` is passed, `c6-8` leaves
   the glass and the rendered story-key count is ZERO for the first time since c2-6.
   `App.test.tsx:860` and `:1968-1971` flip to zero-assertions (their comments were written to
   be rewritten); the sprint-status F1 action item and `deferred-work.md:4906-4916` get the
   "displaced" annotation — the gate itself stays **c8-5's**, don't build it here.
10. **Corridor pins move only where a fixture pushes.** Quiet pills are not focusable, so
    cold-open/push-free fixtures keep their counts (`App.test.tsx:1766/:1774/:1777/:1781/
    :1851`); any fixture that pushes gains one focusable *before* the skip-link target.
    Re-derive, don't nudge.
11. **`schema.ts` is the only home for wire-derived aliases**; `src/api/client.ts` stays the
    one network door; the container reads the store through `src/state/` only (container
    posture, `ui/README.md:593-597`); no new dependency — anything `npm install`-shaped is a
    wrong turn.
12. **Jsdom cannot see any of this** (P15; R3 declined): no stylesheet, no layout, no tooltip
    render, no sequential focus nav. Anatomy = class/structure emission; visual truth = the
    source-reading gates + the C6 manual checklist (c8-6) — this story adds the header pills
    to the app's unviewed-pixels surface (the c6-7 declaration extends). `fireEvent` only;
    vitest globals OFF — import `describe/it/expect/vi` everywhere.
13. **`pre-commit run` stashes unstaged changes** — stage probes before believing a hook run;
    un-added files are invisible to every `git ls-files` registry guard. And **stage before
    you plant** (c6-7 lost the whole component to `git checkout` on unstaged work).
14. **Don't touch**: `AppShell.tsx`/`.css`/`.test.tsx`, `AgentView.tsx`/`.css`,
    `SuggestionsView.tsx`/`.css` (its `copy.ts` only if Q7 rules the reword in),
    `socket.ts`/`connection.ts` (per Q1 — the dispatch pin at `socket.test.ts:675` stays
    true), `inspection.ts`, `cards.ts`, generated `types.d.ts`/`openapi.json` (no `gen:api`),
    `src/**` Python, `test-setup.ts`, static/ and plugin/ by hand.
15. **The store extension must not break the scalar-slot invariant** (UX-DR38: one overlay).
    `status` + `content` stay the single source of "what is on the glass"; `retained` and
    `unread` are bookkeeping beside it, not a second open-view mechanism. `openViewOf`
    (`:287`) and `useOpenAgentView` keep their exact semantics — App's overlay conditional
    must not change shape.

### Testing requirements

- **Suite arithmetic**: frontend strictly > 2,039 / ≥ 74 files (a new container test file +
  a new copy gate); Python 2,907/1/55 unmoved; tokens 70 unmoved.
- **Unit**: the Task-5 matrices. House style: every behavioural assert pairs with a
  non-vacuity guard and a *why* message naming the AC; absence-only asserts get their positive
  twin in the same suite (c6-7's plant-3 lesson, now standing practice).
- **Integration** (`App.test.tsx`): the composed flows in Task 5 — the flagship is the full
  AC-4 loop (push → dismiss → pill re-open → same content re-hydrated → close → focus on
  pill), which is also Flow 3 of `EXPERIENCE.md:207-212` end-to-end.
- **Gates moving is expected and enumerated** (CONTAINERS, COPY_MODULES, DECLARES_MIN, the F1
  pair, pushed-fixture corridor counts); anything else red = stop and understand.
- **Plants** (Task 6): three, with predicted blast radius recorded before running, collected
  count validated, staged before planting, reverted clean.

### Previous-story intelligence

- **c6-7** (PR #69): all 7 questions ruled as recommended pre-code — same protocol here. Its
  three review layers independently found the same null-item crash (guard the ITEM, not just
  its fields — here: guard the KIND key, not just the content); Greptile then found two more
  real P1s pre-merge (a settle-to-unknown race; a content-driven 0-height collapse) — grep
  the whole pattern when a review cites one branch. Its plant 3 exposed an absence-only test;
  its `git checkout` on unstaged work deleted the component. Four guards moved that it
  predicted would not — a prediction about a guard FILE is not a prediction about every claim
  in it.
- **c6-6** (PR #68): the keyed-Fragment announcement, the no-`key` App element (re-open must
  stay a mount, replace must stay a prop update — this story touches neither mechanism), and
  the fallback-title copy ruling that pre-seeded this story's vocabulary home.
- **c6-5** (PR #67): the trap/scrim findings behind Landmines 3/6; the ring-guard narrowing
  done in its diff *for this story's pills*; the close pill as the shipped nav-pill spec.
- **c5-7** (connection pill): the pill-with-dot structural model, the aria-describedby tooltip
  precedent (on a *focusable* pill — the half Q2 must reconcile), and the corridor +1 pattern
  when a new always-present focusable lands.
- **c2-9/c2-10**: copy modules byte-gated against the artefact; probe outputs pasted, not
  summarized.

### The ~45 known `c6-8` ripple sites (Task 0's starting list)

Fulfilled-by-this-diff (prose-sync to truth): `AppShell.tsx:89,200` + `AppShell.css:111` +
`AppShell.test.tsx:199,227` (slot filled — shell files UNTOUCHED, prose there stays true as
written; verify); `App.tsx:526,603,626` (F1 note, placeholder note, switch note);
`App.test.tsx:849-860,1968-1971,3067,3130,3428-3430` (F1 pair inverts; ts/pill prose);
`agentView.ts:44,70,93-96,108,112,129` (the four non-features list, vocabulary docstring, ts/
kind/re-hydration claims); `agentView.test.ts:135,138,270` (forward tests' prose);
`socket.ts:222` (kind-switching ownership — stays true under Q1, reword to shipped);
`schema.ts:290`; `inspection.ts:46`; `AgentView.tsx:16,27` + `AgentView.css:145` (nav-beside,
spec-sharing claims); `SuggestionsView.test.tsx:142,145` (narrow-prop prediction — the widening
discharges it); `copy-rules.test.ts:367` (COPY_MODULES reason); `keyboard-floor.test.ts:398,494`
(the ring-guard and DECLARES_MIN predictions — both land); `shell.test.ts:1556,2128`;
`ui/README.md:574,1359,1466`. Dispositions, not fulfilment: `token-usage.test.ts:400` +
`ui/README.md:1501` (the recorded curve-axis TYPO — means c4-8). Ledger:
`deferred-work.md:49,45,76,4906-4916` (Task 6 dispositions) + the sprint-status F1 action item.
Epics: `epics-companion-app.md:597` (UX-DR40 enumeration rewrite), `:604-610` (placeholder
note). Plus whatever the grep finds beyond these — expect more; seven stories have written
toward this one.

### Project structure notes

- **Expected diff**: `ui/src/containers/AgentViewsNav/{AgentViewsNav.tsx, AgentViewsNav.css,
  AgentViewsNav.test.tsx, copy.ts}` (new) · `ui/src/state/agentView.ts` + `agentView.test.ts`
  (the extension) · `ui/src/api/schema.ts` (the view-kind alias) · `ui/src/App.tsx` +
  `App.test.tsx` (nav prop, kind-keyed body, composed flows, F1 inversion) ·
  `ui/tests/shell.test.ts` (CONTAINERS) · `ui/tests/copy-rules.test.ts` (COPY_MODULES) ·
  `ui/tests/keyboard-floor.test.ts` (DECLARES_MIN) · a new copy byte-gate under `ui/tests/` ·
  `DESIGN.md` (Task 1) · `epics-companion-app.md` (UX-DR40 enumeration) · `ui/README.md` ·
  rebuilt `src/companion/app/static/**` + `plugin/**` · records (this file,
  `deferred-work.md`, `sprint-status.yaml`).
- **Never**: new dependency; `src/components/` additions (CLOSED); an 8th zustand store; hand
  edits under `static/` or `plugin/`; generated api files; `AppShell.tsx` edits (pass the
  prop); wire/socket/backend changes.
- Containers: `src/containers/<Name>/{tsx,css,test.tsx}` + `copy.ts`, flat kebab-case classes
  (BEM is a stylelint error), no barrels, colocated tests, exhaustive CONTAINERS import list.

### References

- Story + epic: `epics-companion-app.md` — Story 6.8 (:2926-2961), Epic 6 (:2668, :895-907),
  Story 9.1's generic-nav AC (:3475-3477), Epic 9 pairing rule (:3427-3435), kind enum
  (:2401), UX-DR28 (:492), UX-DR33 (:547), UX-DR34 (:555), UX-DR37 (:574), UX-DR38 (:580),
  UX-DR39 (:585), UX-DR40 (:593-640), UX-DR43 (:666), UX-DR44 (:670), UX-DR45 (:677), UX-DR46
  (:683), UX-DR47 (:688), confirmed rulings (:704-726), FR map (:728-757).
- UX: `DESIGN.md` — nav-pill block (:260-269), prose (:522), label type (:66-72, :472), accent
  doctrine (:437, :503), spacing scale + drift ban (:484), header layout (:486), radius (:509),
  mock scope (:515), timestamps colour (:438). `EXPERIENCE.md` — IA rows (:38-42), tooltip row
  (:73), component row (:89), cold open (:113), different-kind row (:125), edge rows
  (:131-132), interaction rows (:139-147), hit targets (:156), motion-not-sole-signal (:154),
  Flow 3 (:207-212), FR-18 residual (:227). Composition reference: `imports/claude-design/
  Planeswalker Companion.dc.html` (:33-51, header + pills — arrangement only).
- Accessibility precedent: `review-accessibility.md:32` (the connection-pill tooltip repair
  Q2 mirrors).
- Shipped code: `agentView.ts` (whole file), `socket.ts` (:179, :209-225, :420-453),
  `connection.ts` (:124), `App.tsx` (:439-450, :523-530, :594-630), `AppShell.tsx` (:89-90,
  :149-150, :175-201) + `.css` (:80-126), `AgentView.tsx` (:56-85, :108-115, :209-262,
  :295-329, :343-358, :405-478) + `.css` (:25-37, :144-195), `SuggestionsView.tsx` (:416-425),
  `cards.ts` (:110, :342, :514-543), `ConnectionPill/*`, `schema.ts` (:253-299),
  `types.d.ts` (:1038-1111, :1788), `styles/tokens.css`.
- Guards: `keyboard-floor.test.ts` (:340-357, :397-398, :459-473, :494-511, :753-780),
  `shell.test.ts` (:1356, :1545, :2072-2076, :2119, :2128), `copy-rules.test.ts` (:123-142,
  :367), `store-writes.test.ts` (:77, :109-124, :156-170), `tokens.test.ts` (:346),
  `token-usage.test.ts` (:400, :494-520, :2585-2592), `socket.test.ts` (:675),
  `wire-contract.test.ts`, `posture.test.ts`, `event-union-contract.test.ts`,
  `empty-push-copy.test.ts`, `App.test.tsx` (:838-860, :1620-1678, :1766-1781, :1851-1854,
  :1968-1971, :3067, :3130, :3428-3430), `agentView.test.ts` (:135, :269-274).
- Records: `c6-7-suggestions-view.md` (whole record — plants, review, Greptile),
  `c6-6-…md` (Q7 vocabulary ruling), `c6-5-…md` (ring narrowing, close-pill ruling),
  `deferred-work.md` (:45, :49, :76, :4906-4916), `epic-c5-retro-2026-08-09.md` (P15, R2,
  Block J), `contracts.py` (:1054-1271).

## Open questions for Brad (recommendations first — rule before code)

> **ALL 7 RULED AS RECOMMENDED by Brad, 2026-08-12, pre-code.** No overrides. Each
> recommendation below is now the story's spec; the dev implements them verbatim and review
> reads this section as the citation source. Summary of what that settles: Q1 socket stays
> narrow / store+nav go four-kind generic · Q2 `disabled` pill + `title` AND visually-hidden
> `aria-describedby` · Q3 enum order (Suggestions, Swaps, Tier list, Card groups) · Q4 absolute
> local `Intl.DateTimeFormat` hour+minute in `<time>`, static, no timer · Q5 no `<nav>`
> landmark, kicker SHIPS · Q6 8px dot, `aria-hidden` + visually-hidden "unread" in the
> accessible name, static · Q7 dw:76 re-homed to Story 9.1, annotated.

1. **How generic is "generic", exactly — does the socket widen?** Story 9.1 requires the NAV
   generic over the four-kind enum; the socket today drops `swaps`/`tier_list`/`groups`
   (pinned at `socket.test.ts:675`), and Epic 9's own preamble rules that a kind must never
   become *acceptable* before its view exists ("a push … the UI cannot display" breaks
   never-silently-swallowed from the other side). **Recommend: store, vocabulary, and pills go
   fully four-kind generic; the socket dispatch and `onSuggestions` stay exactly as shipped.**
   Consequences owned in the open: in production, three pills are quiet until Epic 9 (honest —
   quiet is UX-DR33's named ninth state); AC 5's displacement is proven at the store/App seam
   with a synthetic second kind and its first production traversal is Story 9.1's (the c6-6
   AC-3 structural-deferral precedent); `AgentViewContent['kind']` widens per
   `agentView.ts:112`'s own prediction, and App's overlay body becomes the kind switch with
   `suggestions` its only reachable arm. Alternative: widen the dispatch too — rejected
   because it makes an undisplayable push *accepted*, moves `socket.test.ts:675`, and buys
   nothing Epic 9 doesn't rebuild properly with its views.
2. **The quiet pill's tooltip sits on a spec contradiction — how is the copy exposed?**
   UX-DR28/AC 1 demand *not focusable* + a tooltip; UX-DR39 bans *hover-only disclosure of
   unique information* and demands focus parity — and the system already repaired this exact
   shape once, the other way (the 07-22 accessibility review flagged the connection pill's
   hover disclosure; UX-DR29 was amended to focusable + `aria-describedby`). The nav pill
   never got that repair. **Recommend: keep the pill non-focusable (`disabled` — UX-DR28 and
   UX-DR40's cold-open enumeration are explicit and load-bearing), ship the copy as BOTH the
   pointer tooltip (`title`) AND a programmatic description (visually-hidden text referenced
   via `aria-describedby`), so the information is in the accessibility tree for browse-mode
   readers and never hover-only in substance.** File the residual (the artefacts still say
   just "tooltip") for Story 8.3's reconciliation. Alternatives: a focusable
   aria-disabled pill (breaks UX-DR40's "this stop never exists" and adds three dead Tab
   stops); bare `title` only (leaves the SR gap the accessibility review already called a
   violation once).
3. **Pill order — three sources, three orders.** Mock: `groups, swaps, tier_list` (and omits
   Suggestions entirely); IA table: `suggestions, groups, swaps, tier_list`; the closed enum:
   `suggestions | swaps | tier_list | groups`. **Recommend: enum order — Suggestions, Swaps,
   Tier list, Card groups** — the nav is *defined* as generic over the enum, so the order
   falls out of the contract rather than a third authored opinion; Suggestions first also
   puts the only P0 kind first. Alternative: the IA table's order, if Brad wants the mock's
   grouping feel preserved.
4. **The timestamp — format, mechanics, placement.** No artefact specs it ("shows the last
   push's time", four mentions, zero formats). **Recommend: absolute local time of the last
   push — `Intl.DateTimeFormat` with `hour`+`minute` (e.g. 14:32 / 2:32 PM by locale),
   rendered in a `<time dateTime={ts}>` inside the pill after the label, `--type-micro` +
   companions in `--text-tertiary` (DESIGN.md:438's timestamp colour + :473's micro-for-
   timestamps), static — updated only when a new push replaces `ts` (UX-DR43's exact
   wording), no ticking timer, no relative "2m ago"** (a self-updating relative clock is a new
   render loop and an update surface nothing specs; label strings must stay short at 11px).
   Formatted wire data is not authored copy — no COPY_MODULES entry for the time itself.
   Alternative: relative time with a coarse timer — costs a timer, a cadence ruling, and a
   determinism landmine, for a "glance recency" benefit the dot already carries.
5. **Group semantics and the "Agent views" kicker.** UX-DR44 assigns the header nav no
   landmark; the shipped slot is a plain `<div>`; the mock shows a micro/`text-tertiary`
   "Agent views" kicker left of the pills (arrangement, which DESIGN.md:515 says to read the
   mock for) — but the string is authored copy no EXPERIENCE.md row carries. **Recommend: no
   `<nav>` landmark (fill the slot, don't restructure; the pills open overlays — they don't
   navigate), and SHIP the kicker** as the group's visible label (registered in the
   container's `copy.ts` with a reason; the scaffold's `--space-3` gap already anticipates
   it), with the pill row a plain flex group. Alternative: drop the kicker (four uppercase
   pills self-describe; one less authored string) — cheap either way, Brad's call on the
   words being on the glass.
6. **The unread dot — geometry and accessibility.** DESIGN.md gives colour only. Siblings:
   connection pill 8px (UX-DR29), Panel live dot 6px. **Recommend: 8px, citing the
   connection-pill precedent (the other in-pill dot), `aria-hidden="true"` with "unread"
   carried in the button's accessible name via visually-hidden text** — UX-DR29's "the dot
   never carries the state alone" and UX-DR43 both point there, and UX-DR45 forbids it
   announcing. Static: no arrival glow/pulse (DESIGN.md:503 — glows are moments, not steady
   states; an arrival moment would be new motion needing an inventory entry this story
   shouldn't own). Alternative: 6px per Panel — fine, but cite whichever is chosen.
7. **The `{kind}` article grammar entry (dw:76) — this story is its named home; does it act?**
   The entry homes the ungrammatical *"The agent sent an empty suggestions."* on "the story
   that adds the SECOND view kind (c6-8 for kind switching, or Epic 9's first view)". Under
   Q1's recommendation this story adds no second *renderable* kind — but it DOES author the
   per-kind display-noun table (the pill vocabulary), which is one of the entry's own two
   repair shapes. **Recommend: re-home the entry to Epic 9's first view story (9.1), annotated
   that c6-8 shipped the vocabulary table as its first data point** — rewording byte-gated
   Voice-and-Tone copy in a story whose only reachable kind renders the current sentence
   anyway is an amendment nobody's AC asks for (the exact move dw:76's own history warns
   against). Alternative: amend `EXPERIENCE.md:71` here so no article precedes the
   placeholder, accepting the copy-gate re-pin in Task 1.

## Dev Agent Record

### Agent Model Used

Claude Opus 5 (`claude-opus-5`), dev-story workflow, 2026-08-12.

### Debug Log References

**Baselines (Task 0).** Frontend `npm test` from `C:\…` (uppercase): first run hit Landmine 1
exactly — `lint-gates.test.ts > reports a click handler on a non-interactive element` timed out at
5,000 ms on a cold start, `1 failed | 2038 passed (2039)`, **73 files collected**. Re-run warm:
**2,039 passed / 73 files, 6.76 s** — green, and the collected count matched the expected baseline
on both runs, which is what the landmine says to check before scoring anything. Python `uv run pytest -m "not integration"`: **2,907 passed, 1 skipped, 55 deselected**
(180.71 s).

**Grep sweep.** 47 `c6-8` sites outside the implementation artifacts, against the ~45 predicted —
the "expect more than predicted" note held for the seventh consecutive story.

**Plants (Task 6), predictions recorded before each run, full suite each time, collected count
validated, everything staged first, all reverted with `git diff --exit-code` clean:**

- **Plant 1** — the pill reads a constant instead of the store (`pushedAt = null`, `unread =
  false`). Predicted: anatomy/time/unread/re-open rows red in `AgentViewsNav.test.tsx` and the
  c6-8 `App.test.tsx` block; store suite untouched. **Measured: 15 failed / 2,107 passed**, in
  exactly those two files. Store suite green as predicted (it renders nothing).
- **Plant 2** — `closeAgentView` also clears `retained`. Predicted: the re-open chain red across
  all three suites, **and — against the story spec's prediction — the shipped
  `agentView.test.ts:269-274` re-open test STAYS GREEN**, because it reads `content`, which this
  plant does not touch. **Measured: 12 failed / 2,110 passed**, and `:269-274` was indeed green.
  The story predicted that shipped test would catch this; it would not have. Only the coverage
  added here does.
- **Plant 3** — displacement never sets unread. Predicted: both AC-5 store rows, the App AC-5 row
  and the two unread-dot rows red; the absence-only `adds no live region` row stays green and its
  positive twin is what catches it. **Measured: 5 failed / 2,117 passed**, exactly that set.

**Gates.** `npm run lint`, `npm run typecheck`, `npm run format:check` all clean. Frontend
**2,039/73 → 2,122/75** (+83 tests, +2 files). Python **2,907/1/55 unmoved**. Tokens **70,
unmoved** (`tokens.test.ts:346` untouched — every value resolves to a shipped token).

**Rebuild.** `npm run build` → `src/companion/app/static/`, then `uv run python -m
scripts.build_plugin`. Run twice: once after the code, once after Prettier reformatted comments in
ten files during the ripple sweep (the "rebuild AFTER the last edit" rule). Both mirrors
sha256-verified identical on all three artefacts (`index-Ldo72qv1.js` `B072E24A…`,
`index-DvMkerW6.css` `6D2F35BD…`, `index.html` `C9D55CCC…`).

**Copy read (the permanently-open copy-guard entry).** The three strings were read aloud against
UX-DR33's voice rules. *"Your agent hasn't sent this yet."* — second person, present, states a
fact about the agent rather than about the person; no blame, no exclamation, no "yet unavailable".
*"Agent views"* — a plain noun phrase naming the group. *"unread"* — one lower-case word appended
to a name, not a sentence. No runtime assembly anywhere; the formatted time is data, not copy.

### Completion Notes List

**Three findings that contradict the story spec, all measured rather than assumed:**

1. **Landmine 8 was wrong about a load-bearing byte.** It states the tooltip's apostrophe in
   `EXPERIENCE.md:73` is the typographic U+2019. It is the **ASCII U+0027** (hexdumped: `68 61 73
   6e 27 74`). A gate written to the story's claim would have pinned the wrong character and
   agreed with itself forever, which is exactly the failure mode byte-gating exists to prevent.
   The new gate compares bytes read from the artefact and pins the codepoint explicitly, so the
   dependency runs artefact → code rather than the other way round.
2. **Landmine 10's prediction was right about reality and wrong about the mechanism, and the gap
   was a real defect in the measuring instrument.** The corridor pins were predicted to hold on
   push-free fixtures "because quiet pills are not focusable". They moved by +4 on the first run —
   `App.test.tsx`'s `focusablesNow()` selected `'a[href], button, [tabindex]'`, which **matches a
   disabled button**. Until this story the app shipped no disabled control at all, so that
   selector and "the Tab order" had been the same set by accident. Bumping the pins 209 → 213 and
   7 → 11 would have recorded four Tab stops no keyboard user can reach, in the suite whose entire
   job is measuring the corridor a keyboard user walks — and in the same story that ships
   `disabled` precisely *because* UX-DR40 says the stop must not exist. Repaired the helper
   (`:not(:disabled)` on all three branches, reasoning in its docstring); the pins are unchanged,
   which is the honest measurement. This is `deferred-work.md:45`'s shape — a focusable selector
   modelling markup rather than focus behaviour — found in a **second copy** of that shape.
   Annotated there: there are two such selectors in this repo, and the entry can come true in
   either.
3. **Plant 2 disproved the story's blast-radius prediction** for the shipped re-open test — see
   the Debug Log above.

**Judgement calls made inside the rulings, each argued at its site:**

- **`AgentViewKind` is `Exclude<AgentEventKind, 'deck_changed' | 'active_deck_changed'>` in
  `schema.ts`** rather than importing `socket.ts`'s `SystemEventKind` — `src/api/` sits below
  `src/state/` and may not import upward. Two spellings of one pair, both DERIVED, in the two
  files that each own one side of the partition. `socket.ts:179` is the shipped precedent for
  spelling those two literals in a derivation; the wire-name ban is about re-declaring backend
  *shapes*, not discriminant literals.
- **The quiet pill's `aria-describedby` target sits OUTSIDE the button.** Inside, its text would
  join the button's contents and therefore its accessible name — the pill would be *named* "Swaps
  Your agent hasn't sent this yet." and then *described* with the same sentence. Outside, the name
  stays "Swaps". The unread word stays INSIDE, because that one belongs in the name.
- **`pushTimeLabel` returns `null` on an unparseable `ts`, and this is a real crash guard rather
  than defensive noise.** `agentEventOf` validates the `kind` discriminant and nothing else, so a
  frame with `ts: "yesterday"` reaches the store typed as an ISO string, and
  `Intl.DateTimeFormat.format` **throws `RangeError`** on an Invalid Date. The nav renders in the
  app shell under no error boundary, so an unguarded call would take the whole header down over
  one malformed field. The pill stays active and renders no time — c6-7's per-field degradation
  applied to a new field. Covered by a test.
- **`pushTime.ts` is a module of its own** because `react-refresh/only-export-components` fails a
  `.tsx` exporting a non-component, and the formatter must be exported (its callers' tests cannot
  assert bytes — jsdom inherits the host TZ/ICU, so expectations are computed *through* it).
  CONTAINERS moved by three rather than two, in the open.
- **The hover arm is `:enabled:hover`, the focus arm is not guarded.** A disabled button still
  matches `:hover` in every browser, so without the guard a quiet pill would glow under the
  pointer — the one thing `EXPERIENCE.md:73` forbids. A disabled button can never match
  `:focus-visible`, so guarding that arm would imply a state that cannot exist. This forced the
  quiet/focus/hover rules into ascending-specificity order (stylelint's `no-descending-specificity`),
  which is why this file's rule order differs from the close pill's — recorded inline.
- **No transition anywhere in the stylesheet**, matching the close pill (the same spec) and
  DESIGN.md, which specs none. The reduced-motion fallback is therefore vacuously satisfied rather
  than mechanically — there is nothing to neutralise, and the motion inventory did not move.
- **`App.test.tsx`'s flagship AC-4 test focuses the pill before clicking it.** jsdom's
  `HTMLElement.click()` does not focus, while both real paths do (keyboard by definition, pointer
  because browsers focus a `<button>` on mousedown). Without it the test would model an
  interaction no user can perform and then measure the return-focus contract against `<body>`.
- **The stale-id degradation half of AC 4 is NOT asserted in `App.test.tsx`, and the gap is
  recorded in the test rather than left silent.** That file's card route echoes the id back as a
  name unconditionally, so "the card is gone now" is not expressible in it. What IS asserted there
  is the re-ask (cache emptied between dismissal and re-open → both ids re-requested → rows
  return), which is the part only a composed re-open can show; the unknown-card rendering is
  covered where the cache can be driven directly.

**Predictions discharged in this diff:** `agentView.ts:112`'s *"c6-8 widens it"*;
`agentView.ts:44-46`'s *"those are c6-8's… they EXTEND this shape"*; `SuggestionsView.test.tsx:145`'s
*"the prop's type is deliberately narrow until c6-8 widens it"* (the cast is gone);
`keyboard-floor.test.ts:398`'s ring-guard narrowing and `:494`'s `DECLARES_MIN` prediction (both
landed); `AgentView.css:145`'s *"whatever this rule settles is also c6-8's spec"*; c6-6's review
ruling that `SUGGESTIONS_VIEW_TITLE` sat in the state layer *as the c6-8 precedent* (now a
four-kind table it reads from).

**Ledger:** two new entries (the Q2 artefact contradiction → Story 8.3; the header pills joining
the unviewed-pixels surface → c8-6). Four inherited entries annotated: dw:45 **NOT TRIGGERED in
the trap, found live in a second copy**; dw:49 **HEEDED AND NOT TRIGGERED**; dw:76 **RE-HOMED to
Story 9.1** (Q7) with the vocabulary table recorded as its first data point; the F1 count
**DISPLACED to zero** — the gate itself stays c8-5's.

**Not done, deliberately:** no socket/wire/backend change (Q1); `AppShell.tsx`/`.css`/`.test.tsx`,
`AgentView.tsx`, `SuggestionsView.tsx`, `connection.ts`, `inspection.ts`, `cards.ts` and all
generated api files untouched; no new dependency; no 8th store; no `<nav>` landmark; no live
region; no motion.

### File List

**New**

- `ui/src/containers/AgentViewsNav/AgentViewsNav.tsx`
- `ui/src/containers/AgentViewsNav/AgentViewsNav.css`
- `ui/src/containers/AgentViewsNav/AgentViewsNav.test.tsx`
- `ui/src/containers/AgentViewsNav/copy.ts`
- `ui/src/containers/AgentViewsNav/pushTime.ts`
- `ui/tests/agent-views-nav-copy.test.ts`

**Modified — app**

- `ui/src/App.tsx` (the `nav` prop; kind-keyed overlay body; F1 prose)
- `ui/src/api/schema.ts` (`AgentViewKind`)
- `ui/src/state/agentView.ts` (vocabulary table, `retained`, `unread`, displacement, `reopenAgentView`, two selectors)
- `ui/src/state/socket.ts` (prose only — the dispatch is unchanged)
- `ui/src/containers/AgentView/AgentView.tsx`, `AgentView.css` (prose only)

**Modified — tests and guards**

- `ui/src/App.test.tsx` (the c6-8 describe; F1 inversion ×2; the `focusablesNow` repair)
- `ui/src/state/agentView.test.ts`, `ui/src/containers/SuggestionsView/SuggestionsView.test.tsx`
- `ui/tests/shell.test.ts` (CONTAINERS 31 → 34), `ui/tests/copy-rules.test.ts` (COPY_MODULES), `ui/tests/keyboard-floor.test.ts` (DECLARES_MIN)

**Modified — artefacts and records**

- `DESIGN.md` (nav-pill block + prose row), `EXPERIENCE.md` (nav-pill row), `epics-companion-app.md` (UX-DR40)
- `ui/README.md`, `deferred-work.md`, `sprint-status.yaml`, this file

**Rebuilt (never hand-edited)**

- `src/companion/app/static/**`, `plugin/server/src/companion/app/static/**`

## Change Log

- 2026-08-12 — Story context created (create-story, ultimate context engine analysis).
  Baseline `f390a46` (frontend 2,039/73, Python 2,907/1/55, tokens 70). 7 open questions with
  recommendations await Brad's pre-code ruling — Q1 (socket stays narrow; nav/store go
  four-kind generic) is the scoping decision; Q2 repairs a genuine artefact contradiction
  (non-focusable tooltip vs the hover-only-disclosure ban the connection pill was already
  repaired for). Status → ready-for-dev.
- 2026-08-12 — **All 7 questions RULED AS RECOMMENDED by Brad, pre-code, no overrides.** Recorded
  in the questions section as the story's spec.
- 2026-08-12 — **Implemented (dev-story), Tasks 0–6. Status → review.** The agent-views nav ships:
  four pills generic over the closed kind enum, quiet pills `disabled` with the tooltip carried
  BOTH as `title` and as a programmatic description (Q2's repair of a real artefact
  contradiction), absolute static push times in `<time>`, an 8px accent unread dot whose word
  lives in the accessible name, and re-open by remount. The store grew per-kind retention and the
  one-setter unread state machine; `AppShell.tsx` was not edited, and the F1 count of rendered
  story keys is **ZERO for the first time since c2-6**. Frontend **2,039/73 → 2,122/75**; Python
  **unmoved at 2,907/1/55**; tokens **unmoved at 70**. Three plants confirmed 3/3 with predictions
  recorded first. Three story-spec claims were disproved by measurement and are recorded rather
  than smoothed over: the tooltip's apostrophe is ASCII, not U+2019; the corridor pins moved
  because `App.test.tsx`'s focusable helper counted disabled buttons as Tab stops (a real defect
  in the instrument, repaired — pins unchanged); and plant 2 showed the shipped re-open test would
  NOT have caught a retention regression. Two new ledger entries, four inherited ones annotated.
- 2026-08-12 — **Code review (bmad-code-review): Blind Hunter, Edge Case Hunter, Acceptance
  Auditor.** Acceptance Auditor independently re-ran every gate and reproduced the Dev Agent
  Record's numbers exactly — zero findings. 1 patch applied, 2 defer (both already tracked in
  `deferred-work.md` by the dev's own Task 6 ledger pass — cross-referenced, not duplicated), 12
  dismissed (mitigated by an existing test, matching an explicit Q-ruling already made in this
  story, or consistent with an established codebase convention). **Patch:** a retained push whose
  `ts` was entirely absent (the "absent, not merely unparseable" half of the malformed-frame
  threat model `pushTime.ts`'s own docstring names) collapsed its pill to the QUIET/never-pushed
  branch instead of active-with-no-time — permanently unreachable via the nav after the next
  dismissal, a real UX-DR34 violation. Split `useAgentViewPushTime` into activeness
  (`useAgentViewHasPush`, keyed on `retained[kind]` presence) and time (unchanged, still
  `.ts`-keyed), so a missing `ts` degrades only the `<time>` render, never the pill's
  reachability — the same per-field-degrades-alone shape c6-7 established. One new test (the
  absent-`ts` case, distinct from the already-covered unparseable-`ts` case). Frontend
  **2,122/75 → 2,123/75**; Python/tokens unmoved; lint/typecheck/format clean; both static
  mirrors rebuilt and sha256-verified identical.
- 2026-08-12 — **MERGED via PR #70 into `feat/companion-c6` at `980db80`.** Greptile: **5/5,
  zero findings** — no post-merge catch, matching the Acceptance Auditor's zero findings during
  the three-layer review (a first for both layers on the same story, this epic). Suite at merge:
  frontend **2,123/75**, Python **2,907/1/55 unmoved**, tokens **70 unmoved**. Next: c6-9 (the
  250 ms budget measurement) or the C6 retro, whichever Brad calls.
