# Deferred Work

> **Epic renumbering (2026-08-16):** the companion epics, formerly `c1`..`c10`, are now
> **Epics 8..17** (c1=8, c2=9, c3=10, c4=11, c5=12, c6=13, c7=14, c8=15, c9=16, c10=17),
> continuing the project's integer sequence (BMAD v6.11 requires integer epics). Historical
> `cN-M` story ids in prose, filenames, PR titles and branch names are unchanged records of
> merged work. See `sprint-change-proposal-2026-08-16.md`.

## Deferred from: code review of c6-7-suggestions-view (2026-08-11)

> Findings from the bmad-code-review three-layer pass (Blind Hunter, Edge Case Hunter,
> Acceptance Auditor) against the uncommitted c6-7 diff, deferred rather than patched — either
> low observed harm today, or needing UX input rather than a mechanical fix.

- source_spec: `_bmad-output/implementation-artifacts/c6-7-suggestions-view.md`
  summary: "Screen-reader users hear the row's badge, name, mana cost and confidence as one
  run-on phrase with no separating punctuation or labeling, since all four are sibling `<span>`s
  inside the same `<button>` as the reason line — e.g. 'ramp Llanowar Elves high Fills the
  one-drop ramp slot.' Unlike the story's other pixel-only claims, which were explicitly carried
  to the C6 manual checklist, this AX-tree structure question is testable in principle (via an
  accessible-name/description assertion) but was not raised as an open question anywhere the
  review found. Needs UX input on how the four pieces should group or be labeled for assistive
  tech before a fix is unambiguous."
  evidence: 'bmad-code-review Blind Hunter, 2026-08-11; `ui/src/containers/SuggestionsView/SuggestionsView.tsx` (`SuggestionRow`'"'"'s head line, badge/name/cost/confidence spans).'

- source_spec: `_bmad-output/implementation-artifacts/c6-7-suggestions-view.md`
  summary: "`renderableOf`'s own docstring names a fourth hydration tier as \"the interesting
  one\": a suggested card that happens to already be in the open deck, pre-seeded via
  `seedCardSummaries`, painting a name and mana cost at first frame with nothing in flight. No
  test in `SuggestionsView.test.tsx` exercises that tier for the head line — the one seed that
  populates `entry.summary` without hydrating is asserted only for placeholder text and
  inspectability, never for `.suggestion-row-name`/`.suggestion-row-cost` actually rendering.
  Test-coverage gap, not a runtime defect."
  evidence: 'bmad-code-review Blind Hunter, 2026-08-11; `ui/src/containers/SuggestionsView/SuggestionsView.tsx` (`renderableOf`'"'"'s docstring); `ui/src/containers/SuggestionsView/SuggestionsView.test.tsx`.'

- source_spec: `_bmad-output/implementation-artifacts/c6-7-suggestions-view.md`
  summary: "Every item whose `card_id` is present but not a string (`42`, `{id:'c-1'}`, etc.)
  maps through `cardIdOf` to the same `''` value, so several distinct malformed suggestions in
  one push share one `CardEntry`, one flip-index entry, and would share one hover/focus/pin
  target if `inspectable()` ever admitted `''`. Harmless today — the inspection store refuses
  `''` uniformly, so none of them can be hovered, focused or pinned — but nothing in the design
  distinguishes N different malformed rows from each other should that refusal ever narrow."
  evidence: 'bmad-code-review Edge Case Hunter, 2026-08-11; `ui/src/containers/SuggestionsView/SuggestionsView.tsx` (`cardIdOf`).'

## Deferred from: c6-8-agent-views-nav-unread-markers-re-open-and-kind-switching (2026-08-12)

> Observations recorded during implementation, before the three-layer review. One is an ARTEFACT
> contradiction the story repaired in CODE and could not repair in the artefacts it does not own;
> the other extends a standing declaration to a new surface.
>
> **Inherited entries reconciled by this story** (each annotated in place): the
> `FOCUSABLE_SELECTOR` gap is **NOT TRIGGERED in the trap — and was found LIVE in a second copy
> of the same shape**, `App.test.tsx`'s corridor helper, which counted disabled buttons as Tab
> stops and is now repaired; the Esc `stopPropagation` starvation is **HEEDED AND NOT TRIGGERED**
> (the pills ship no `onKeyDown`, and a behavioural test pins the absence); the `{kind}` article
> grammar entry is **RE-HOMED TO STORY 9.1** by Brad's Q7, with c6-8's vocabulary table recorded
> as its first data point; and the C3-retro **F1 count is DISPLACED to zero** — the gate itself
> stays 15-5's.

- source_spec: `_bmad-output/implementation-artifacts/c6-8-agent-views-nav-unread-markers-re-open-and-kind-switching.md`
  summary: "**The artefacts describe the quiet nav pill's copy as a \"tooltip\", singular, and that is a contradiction the system has already repaired once in the other direction.** UX-DR28 and AC 1 require the pill be NOT focusable and carry a tooltip; UX-DR39 bans hover-only disclosure of unique information and requires focus parity — and a non-focusable element cannot disclose on focus, so the two rules cannot both be satisfied by a `title` alone. The identical shape was caught on the connection pill by the 2026-07-22 accessibility review and repaired by amending UX-DR29 to focusable + `aria-describedby`; the nav pill never got that amendment. **c6-8 repaired it in code** under Brad's Q2 ruling — the pill stays `disabled` (UX-DR28 and UX-DR40's cold-open enumeration are explicit and load-bearing) and the sentence ships as BOTH a `title` and a visually-hidden `aria-describedby` target, so the information is in the accessibility tree and never hover-only in substance. EXPERIENCE.md's nav-pill row was amended in the same commit to record the mechanism and the reason. **What remains is the residue this story cannot fix from inside a story:** UX-DR28 itself, and the epic's AC 1, still say \"tooltip\" as though a pointer affordance were the whole requirement, so the next reader of those rules meets the contradiction again with no pointer to its resolution. ~~**Home: Story 8.3's PRD reconciliation**, which is where peer-artefact disagreements of exactly this shape are collected — the repair is to amend UX-DR28 the way UX-DR29 was amended, naming the dual mechanism, rather than to change any code.~~ **CLOSED by story 15-3, 2026-08-18, exactly as prescribed** (Story 8.3 was renumbered 15-3). UX-DR28 in `epics-companion-app.md` now states that the quiet pill's sentence ships as a `title` **and** a visually-hidden `aria-describedby` target, that the pill deliberately stays `disabled` because UX-DR28's own non-focusability and UX-DR40's cold-open Tab enumeration are load-bearing, and that this is the repair UX-DR29 already received for the connection pill. The epic's c6-8 AC 1 carried the same stale \"the tooltip\" and was amended in the same commit. No code changed; the rule now describes what c6-8 shipped."
  evidence: '`review-accessibility.md:32` (the connection-pill repair this mirrors); UX-DR28 (`epics-companion-app.md:492`), UX-DR39 (`:585`), UX-DR29; the shipped dual mechanism in `ui/src/containers/AgentViewsNav/AgentViewsNav.tsx` and its reasoning in that directory''s `copy.ts`; the amended nav-pill row in `EXPERIENCE.md`, gated by `ui/tests/agent-views-nav-copy.test.ts` (which asserts the row still carries both the UX-DR39 clause and the "programmatic description" wording, so the reason cannot be quietly dropped).'

- source_spec: `_bmad-output/implementation-artifacts/c6-8-agent-views-nav-unread-markers-re-open-and-kind-switching.md`
  summary: "**The header nav pills join the app's unviewed-pixels surface, extending c6-7's declaration to a component that is on EVERY screen rather than inside an overlay.** jsdom evaluates no stylesheet, resolves no layout and renders no tooltip, so every visual claim this story makes is asserted as SOURCE: that the quiet pill is `text-tertiary` and not an opacity dim, that the dot is 8px `--accent`, that both type roles ship with their companion declarations, that the hover arm excludes `:disabled`, that the pill declares 24px on both axes. Five specific things remain unchecked by anything. (1) Whether four uppercase `--type-label` pills plus a kicker plus the identity block and badges actually FIT the header at 1100px — the row wraps by design, and nobody has seen whether it does. (2) Whether the quiet `text-tertiary` reads as *\"nothing here yet\"* rather than as *\"broken\"* when three of the four pills are quiet, which is the ordinary production state until Epic 9. (3) Whether the 8px accent dot is findable at a glance beside 11px uppercase text — the connection pill's dot sits beside 14px body text, which is the sibling it cites. (4) Whether the `--type-micro` timestamp after a `--type-label` name reads as one control or as two. (5) Whether the browser renders a `title` tooltip on a `disabled` button at all, which varies by engine and is the pointer half of Q2's dual mechanism (the accessibility-tree half is asserted). **Home: the C6 manual checklist (15-6)**, which already carries C5's un-run Block J and c6-7's rows."
  evidence: 'The "WHAT THIS SUITE CANNOT CARRY" header in `ui/src/containers/AgentViewsNav/AgentViewsNav.test.tsx`; P15 (the jsdom class-vs-token hole) from `epic-c5-retro-2026-08-09.md`; R11 (Block J ruled NOT RUN); the c6-7 entry below, which this one extends rather than duplicates — that surface is inside an overlay the user opens, this one is on the glass permanently.'

## Deferred from: c6-7-suggestions-view (2026-08-11)

> Observations recorded during implementation of the suggestion rows, before the three-layer
> review. One is a BOUNDARY question ruled to belong to the story that builds the machinery it
> concerns (Brad's Q7); the other is a residue this story declares rather than repairs.
>
> **Inherited entries reconciled by this story** (each annotated in place, below): the
> empty-push-line `DESIGN.md` block is **CLOSED**; `agentEventOf`'s item half is **CLOSED** at
> the row, which is where the entry said it belonged; the `FOCUSABLE_SELECTOR` roving-tabindex
> gap and the Esc `stopPropagation` starvation are both **NOT TRIGGERED** (the rows carry no
> `tabindex` and no `onKeyDown`, and the second was heeded by name); and the image in-flight
> coalescing entry is **CLOSED as "not wanted"** by Brad's ruling, which is the deliberate close
> its own terms asked for after three declines and one mis-homing.

- source_spec: `_bmad-output/implementation-artifacts/c6-7-suggestions-view.md`
  summary: "**A pinned suggestion is usually a card that is NOT in the open deck, and Epic 7's eviction rule was written as though every pin were.** UX-DR35 says a pinned target *\"that no longer exists in the deck falls back to transient\"* — written for deck cards, before any surface could pin a non-deck one. Read literally against c6-7's rows, the next `deck_changed` refetch would evict every pinned suggestion the moment the deck's card list changed, which reads as a bug against this story's own AC 2 (*\"a pinned target survives closing the view\"*) and against UJ-1 step 6: the user pins a suggested card precisely BECAUSE it is not in the deck yet. Nothing evicts today — refetch coalescing is Epic 7's and unbuilt — so there is no live defect and this story writes no code for it. **Home: Epic 7's refetch story**, which is where the decision has the eviction machinery in front of it: rule either that eviction applies only to pins whose card was in the DEPARTING deck's list, or that a pin on a non-deck card always survives. c6-7's `App.test.tsx` pin-survives-close test stands as the regression tripwire in the meantime. **RULED (Brad, 2026-08-14 — C6 R9): the FIRST option, eviction is a membership transition.** A pin is evicted only when its card was in the DEPARTING deck's list and is absent from the new one — a pin on a card that was never in the deck (every pinned suggestion) survives as a natural consequence, statelessly, with no pin-time classification (the second option's grandfathering edge: a suggestion pinned, then added to the deck, then removed, would have survived a removal it shouldn't). UX-DR35's wording amended in `epics-companion-app.md` at the DR itself and at Story 7.4's ACs, which also gained the suggestion-pin-survives AC — the real regression test this entry was owed. **Home discharged to c7-4's ACs; entry CLOSES when that AC's test ships.** **CLOSED 2026-08-15: c7-4 shipped the test (PR #78, merged at `0bfaf57`) — `App.test.tsx` \"keeps a pinned SUGGESTION — a card in neither list — through a completed refetch\" drives a real `deck_changed` refetch against a pin on `id-Birds of Paradise` (verified absent from every deck fixture), plus the `inspection.test.ts` absent→absent truth-table row; the R9 membership rule itself ships as `evictDepartedPin` and the pin-survival half is firing-proof-planted (unconditional `clearPin()` → 3 RED).**"
  evidence: 'Recorded at story creation and confirmed during implementation; UX-DR35; `EXPERIENCE.md:188` (UJ-1 step 6); `ui/src/state/inspection.ts` (nothing in the slice reads the deck); `ui/src/App.test.tsx`, "ESC CLOSES THE VIEW AND THE PIN SET FROM A ROW SURVIVES". Brad ruled Q7 as recommended (2026-08-11): file the boundary note, write no code here. **Citation corrected by code review (2026-08-11):** the named App test covers only the PIN-SURVIVES-CLOSE half of AC 2 — it never drives a `deck_changed` event, so it is not itself a tripwire for the eviction question this entry is about. The "nothing evicts today" claim rests on Epic 7''s refetch/eviction machinery being unbuilt (confirmed by `inspection.ts` reading no deck state), not on any shipped test exercising that path — Epic 7''s refetch story is still the one that owes a real regression test for whichever way it rules.'

- source_spec: `_bmad-output/implementation-artifacts/c6-7-suggestions-view.md`
  summary: "**The suggestion row is the app's first surface whose pixels no human has seen, and the guards that cover it are all source reads.** `DESIGN.md:444` lists the Suggestion row among the components *\"specified here without a visual precedent\"* — there are no composition-reference pixels to compare against — and Block J of the C5 manual checklist was RULED NOT RUN by Brad, so the whole agent-view surface has shipped unviewed. jsdom evaluates no stylesheet, resolves no layout and loads no images, so every visual claim this story makes is asserted as SOURCE: that the stylesheet spends no `--accent-dim`, no `--radius-card` and no `aspect-ratio`; that the type roles ship with their companion declarations; that the one `px` literal carries its citation. Four specific things remain unchecked by anything: whether `--accent` at 5.5:1 reads as a live marker over the row's own `--accent-glow` tint; whether the content-driven row height produces a thumbnail of a sensible WIDTH at the view's real measure (the height derives from two text lines, and the width from 63:88, so a tighter line height makes a narrower card); whether a 200-character reason ellipsizes at a useful point; and whether the badge, name, pips and confidence sit on one optical line given three different type roles. **Home: the C6 manual checklist (15-6)**, carrying C5's Block J with it."
  evidence: '`DESIGN.md:444` (no-visual-precedent list) and the amended `components.suggestion-row`; `epic-c5-retro-2026-08-09.md` (R11, Block J ruled NOT RUN); the "WHAT THIS SUITE CANNOT CARRY" header in `ui/src/containers/SuggestionsView/SuggestionsView.test.tsx`; P15 (the jsdom class-vs-token hole) from the same retro.'

## Deferred from: c6-6-a-push-opens-its-view-and-a-repeat-push-replaces-it-in-place (2026-08-11)

> Observations recorded during implementation, before the three-layer review. Both are ARTEFACT
> gaps rather than code defects: the story shipped the artefact's own words and its own values
> and declared what the artefact does not say, rather than inventing the missing half.
>
> **Inherited entries reconciled by this story** (each annotated in place, above): the
> dialog-accessible-name guard (`AgentViewContent.title`) is **CLOSED**; `agentEventOf`'s
> kind-only narrowing is **PARTIALLY TRIGGERED** — the payload SHAPE is now defended at the
> builder by Brad's Q6 ruling, item-field validation stays c6-7's; and the permanently-open
> copy-guard entry is **HONOURED AND STAYS OPEN** (c4-12's disposition recorded that *"c6-6 still
> owes it"* — the reading was performed and is recorded in this story's Debug Log, which is the
> deliverable; the entry never closes, by its own terms).

- source_spec: `_bmad-output/implementation-artifacts/c6-6-a-push-opens-its-view-and-a-repeat-push-replaces-it-in-place.md`
  summary: "**The empty-push line is ungrammatical once its placeholder is filled, and the artefact is what says so.** `EXPERIENCE.md`'s Voice and Tone row writes *\"The agent sent an empty {kind}. Nothing to show — ask it for another pass.\"* — a template — and the story's own task list rules the substitution to be the WIRE kind. That renders *\"The agent sent an empty suggestions.\"*, which reads wrong, and gets worse for Epic 9's kinds: *\"an empty tier_list\"*, *\"an empty groups\"*. c6-6 shipped the artefact's bytes verbatim rather than inventing a per-kind display noun (\"suggestions list\", \"tier list\"), because authoring copy no artefact carries — one story before the second kind that would need it — is exactly what the copy guard's registration rule exists to prevent, and a runtime-assembled user-facing string is residue 3 of `copy-rules.test.ts`'s own header. **Home: the story that adds the SECOND view kind** (c6-8 for kind switching, or Epic 9's first view), which is the first point at which the decision has two data points instead of one. The repair is either a per-kind display-noun table registered in `COPY_MODULES`, or an `EXPERIENCE.md` amendment rewording the sentence so no article precedes the placeholder."
  evidence: '`ui/src/containers/SuggestionsView/copy.ts` (the residue is declared in the module itself); `EXPERIENCE.md:71`; the byte-for-byte pin in `ui/tests/empty-push-copy.test.ts` asserts the placeholder SURVIVES, so the day someone hard-codes a kind that gate fires. **RE-HOMED TO STORY 9.1 BY c6-8 (Brad''s Q7, 2026-08-12), with this story''s contribution recorded rather than the entry closed.** This entry named "c6-8 for kind switching" as one of two candidate homes, and c6-8 did build kind switching — but under Q1 it added no second RENDERABLE kind: the socket still drops `swaps`/`tier_list`/`groups`, so the only kind that can reach the empty-push line is still `suggestions`, and the sentence it renders is the one already shipped. Rewording byte-gated Voice-and-Tone copy in a story whose only reachable kind renders the current sentence anyway is an amendment nobody''s acceptance criterion asks for — the exact move this entry''s own history warns against. What c6-8 DID contribute is **the first of the entry''s two repair shapes, in part**: `AGENT_VIEW_LABELS` in `src/state/agentView.ts` is a per-kind display-noun table, registered in `COPY_MODULES`, covering all four kinds ("Suggestions" / "Swaps" / "Tier list" / "Card groups"). It is not yet the repair, because those are NAV LABELS and the empty-push line needs a noun that reads after an article — "an empty Tier list" is better than "an empty tier_list" and still not right, and "a Card groups" is worse. So Story 9.1 inherits a real data point and a decided home for whatever noun it needs: either extend that table with a second per-kind form, or amend `EXPERIENCE.md:71` so no article precedes the placeholder. **Home: Story 9.1** (Epic 9''s first view), which is the first story with a second reachable kind in front of it.'

- source_spec: `_bmad-output/implementation-artifacts/c6-6-a-push-opens-its-view-and-a-repeat-push-replaces-it-in-place.md`
  summary: "**`DESIGN.md` specifies a treatment for the empty-DECK line and none for the empty-PUSH line, which are the same kind of thing.** `components.empty-deck-line` carries `type: '{typography.body}'`, `foreground: '{colors.text-secondary}'` and the note that it *\"spends no length of its own\"* because its container's padding is already its inset. Nothing equivalent exists for the empty push, and the two states are structurally identical: one calm sentence standing in for absent content inside a surface that supplies its own padding. c6-6 shipped the empty-deck block's values, CITED in `SuggestionsView.css`, and did not amend the artefact — c4-12 amended `DESIGN.md` because an acceptance criterion of its own (AC 26) required the artefact to specify the treatment, and c6-6 has no such AC. Amending an artefact nobody asked to be amended is not a diff a story makes quietly. **Home: c6-7**, which renders the rest of this view and therefore has to put real values in front of a `DESIGN.md` that describes none of them — at which point the empty line's block is one line of the same amendment. **CLOSED BY c6-7 (2026-08-11), exactly as predicted.** That story amended `components.suggestion-row` first (Brad's Q2 ruling — the block carried four values and no padding, gap, row height or live marker, while the component description below the frontmatter already promised all of them), and `components.empty-push-line` was one entry of the same amendment: `type: '{typography.body}'`, `foreground: '{colors.text-secondary}'`, and a `container` note recording that the agent view body's own `{spacing.4}` is the whole of its inset. Pinned in `ui/tests/tokens.test.ts` by a SIBLING comparison against `empty-deck-line` rather than against retyped constants, so the day one of the two is amended and the other is not, the test names it."
  evidence: '`ui/src/containers/SuggestionsView/SuggestionsView.css` (the gap is declared in the stylesheet header); `DESIGN.md`, `components.empty-deck-line`; `ui/src/containers/CardGrid/CardGrid.css:42-64` for the shape the amendment took at c4-12.'

## Deferred from: c6-5-agent-view-shell-with-focus-management-and-dismissal (2026-08-10)

> Observations recorded during implementation of the agent view shell, before the three-layer
> review. Neither is caused by this story's code; both were found by it.

- source_spec: `_bmad-output/implementation-artifacts/c6-5-agent-view-shell-with-focus-management-and-dismissal.md`
  summary: "**A SECOND, DISTINCT WINDOWS TEST FLAKE: an intermittent vitest worker-fork crash with no test attached.** Twice in roughly a dozen full `npm test` runs, the suite ended `Unhandled Error — [vitest-pool]: Worker forks emitted error / Worker exited unexpectedly`, with one test FILE silently dropped (`70 passed (71)`, `1929 passed (1934)` — five tests never run and never reported as failures). It is NOT the known cold-start `lint-gates.test.ts` timeout (Landmine 12, recorded at c6-2, c6-3 and again at this story's baseline): that one reports a named failing test with a ~125 s setup, while this reports no test at all. It did not reproduce in seven consecutive runs afterwards, and every clean run collected exactly 1,934. **Why it matters more than its frequency suggests: the failure mode is a suite that silently gets SMALLER.** A run that drops a file exits non-zero today, but the count is what a reader scores, and 1,929 reads as green to anyone not comparing it against 1,934 — which is precisely why this repo validates the collected count before scoring a run. Unowned; recorded so the next person to see it has the shape and does not re-derive it."
  evidence: 'Observed 2026-08-10 during c6-5 implementation: once on the planted-red run (alongside its 5 genuine failures) and once on a clean gate run at 19:11:54. Seven consecutive full runs immediately after were 1,934/1,934 with no error. Windows 11, vitest 4.1.10, forks pool.'

- source_spec: `_bmad-output/implementation-artifacts/c6-5-agent-view-shell-with-focus-management-and-dismissal.md`
  summary: "**The running \"Nth copy module in the app\" ordinals in `shell.test.ts`'s CONTAINERS list contradict each other, and have since Epic 4.** c4-8's entry says its copy module is \"the tenth in the app\", c4-10's says \"the twelfth\", c4-11's also says \"the twelfth\", and c4-12's says \"the SIXTH in this tree\" where c4-10's already claimed sixth. They are prose ordinals with no gate behind them, so nothing has ever objected. c6-5 declined to add a fifth guess: its entry states the two counts that are checkable from `git ls-files` (tenth under `src/containers/`, thirteenth in the app) and names the inconsistency in place. Repairing five other stories' comments was out of this story's diff. **Home: unowned** — a one-line sweep for whoever next adds a copy module, or a decision to drop the app-wide ordinal entirely, which is what makes the tree-local one honest."
  evidence: '`ui/tests/shell.test.ts` — CONTAINERS entries for `CardGrid/copy.ts`, `ManaCurve/copy.ts`, `FormatCheck/copy.ts`, `SkipLink/copy.ts`. `git ls-files "ui/src/**/copy.ts"` returns 13 modules, 10 of them under `src/containers/`.'

## Deferred from: code review of c6-5-agent-view-shell-with-focus-management-and-dismissal (2026-08-10)

> Three-layer adversarial review (Blind Hunter, Edge Case Hunter, Acceptance Auditor) of the
> `feat/companion-c6-5-agent-view-shell` diff. Entries below are real but not caused by this
> change's reachable behaviour, or are pre-existing drift this diff only inherits.

- source_spec: `_bmad-output/implementation-artifacts/c6-5-agent-view-shell-with-focus-management-and-dismissal.md`
  summary: "`FOCUSABLE_SELECTOR` (the focus trap's boundary query) doesn't exclude natively-focusable elements carrying `tabindex=\"-1\"` — only the catch-all `[tabindex]` branch excludes programmatically-detached elements; `button:not([disabled])` etc. admit a roving-tabindex control unconditionally. Unreachable today (no such content exists inside the shell — it renders an arbitrary fixture child in tests, nothing production-real yet), but c6-7's suggestion rows are a plausible place for a roving-tabindex composite control to appear, and if one does, the trap's wrap logic would silently treat it as a real boundary stop the browser's own Tab sequence skips."
  evidence: 'Blind Hunter; `ui/src/containers/AgentView/AgentView.tsx:85-92`. **NOT TRIGGERED BY c6-7 (checked 2026-08-11), and the named risk did not materialise.** That story is the one this entry predicted — it mounts the first production-real content inside the shell — and its rows carry NO `tabindex` in any spelling: each row is a plain `<button>` in document order, which UX-DR40 requires ("nothing in the app carries one") and which the unit suite asserts by name. A view of six suggestions therefore puts six ordinary focusables between the close pill''s two ends, which is exactly the shape the trap was written against. STAYS OPEN for the first story that ships a roving-tabindex composite; c6-8''s nav pills sit OUTSIDE the shell and are not it. **NOT TRIGGERED BY c6-8 either (checked 2026-08-12) — but that story found this entry''s EXACT SHAPE in a second place, and it was live rather than hypothetical.** The pills carry no `tabindex` (quiet ones ship `disabled`, which is what keeps UX-DR40''s "nothing carries a tabindex" true), so the trap is untouched. However `App.test.tsx`''s corridor helper selected `''a[href], button, [tabindex]''` — a selector that models the MARKUP rather than the focus behaviour, which is this entry''s whole subject — and it counted four disabled buttons as Tab stops, which would have moved the pinned corridor numbers 209 -> 213 and 7 -> 11 while the real corridor did not move at all. Until c6-8 the app contained no disabled control, so that selector and "the Tab order" had been the same set by accident. Repaired in that story (`:not(:disabled)` on all three branches, with the reasoning in the helper''s docstring). The lesson generalises and is the reason this annotation is here rather than in the story record alone: **a focusable-element selector is a model of focus behaviour, and every copy of one in this repo is a place this entry can come true.** There are two — the trap''s and the corridor helper''s.'

- source_spec: `_bmad-output/implementation-artifacts/c6-5-agent-view-shell-with-focus-management-and-dismissal.md`
  summary: "The document-capture Esc listener's `event.stopPropagation()` suppresses Escape for React's own synthetic event delegation app-wide while a view is open, not only for `CardDetail`'s document-bubble listener — React 17+ delegates its own listeners (including any `onKeyDown`/`onKeyDownCapture` prop anywhere in the tree) at the root DOM container, which sits below `document` in the capture path, so a capture-phase `stopPropagation()` at `document` prevents the event from ever reaching it. No `onKeyDown`/`onKeyDownCapture` prop exists anywhere in `ui/src` today, so there is zero live impact, but future content mounted inside an open agent view (c6-7 rows, c6-8 pills) should not add an Escape-consuming `onKeyDown` and expect it to fire while a view is open."
  evidence: 'Blind Hunter; `ui/src/containers/AgentView/AgentView.tsx:237-252`; confirmed no `onKeyDown`/`onKeyDownCapture` usage exists elsewhere in `ui/src` via repo-wide grep. **NOT TRIGGERED BY c6-7 (checked 2026-08-11), and the warning was heeded rather than merely survived.** This entry names "c6-7 rows" as future content that should not add an Escape-consuming `onKeyDown`; those rows shipped with no keyboard handler at all, because they are real `<button>`s and Enter/Space are already the browser''s own click (UX-DR39). The component header records this entry by number as one of the two reasons. The repo-wide grep still returns nothing. **HEEDED AND NOT TRIGGERED BY c6-8 (checked 2026-08-12), which is the other story this entry names by name.** The nav pills ship no `onKeyDown` in any spelling: they are real `<button>`s, so Enter and Space are the browser''s own click (UX-DR39), and the component header records this entry as one of three reasons the absence is deliberate. The pills are in fact dead to keyboard handlers three times over while a view is open — this starvation, the scrim covering the header, and the focus trap holding Tab inside the dialog — which is why a pill click can only ever start from a closed view. A behavioural test pins the absence rather than a comment claiming it: a synthetic `keydown` of Enter on a pill changes nothing, while a click on the same pill opens the view. The repo-wide grep still returns nothing. STAYS OPEN for Epic 9''s views.'

- source_spec: `_bmad-output/implementation-artifacts/c6-5-agent-view-shell-with-focus-management-and-dismissal.md`
  summary: "`AgentViewContent.title` (the store's content shape) has no non-empty guard. An empty-string title would render an `<h2>` with no visible text, and since `aria-labelledby` points at that heading, the dialog's accessible name would resolve to nothing — failing the basic requirement that every `role=\"dialog\"` have a discernible name. Not reachable until c6-6 wires a real `suggestions` push into `openAgentView`; c6-6 should validate or fall back to a non-empty title at the point content is constructed."
  evidence: 'Blind Hunter; `ui/src/state/agentView.ts:62-71`. **CLOSED BY c6-6 (2026-08-11), at exactly the point this entry asked for.** `suggestionsViewOf` — the builder that turns an envelope into content — trims `payload.title` and falls back to `SUGGESTIONS_VIEW_TITLE` (the word "Suggestions") when the result is absent, null or empty, so no code path can construct content with a blank title. `.trim()` rather than a truthiness check, because a title of three spaces renders nothing while passing a non-empty-string check. The fallback word is a Q7 ruling (Brad, 2026-08-11) and is registered in `COPY_MODULES` as authored copy. Pinned two ways: an `it.each` over absent/null/empty/whitespace-only in `ui/src/state/agentView.test.ts`, and an end-to-end `toHaveAccessibleName` assertion in `ui/src/App.test.tsx` driven through the real socket — the second is the one that checks the property this entry is actually about, since the accessible name is computed by the DOM rather than by the store.'

- source_spec: `_bmad-output/implementation-artifacts/c6-5-agent-view-shell-with-focus-management-and-dismissal.md`
  summary: "Restates and confirms the ordinal-drift item already logged in this file's `c6-5-agent-view-shell...` dev-time section above (c4-8/c4-10/c4-12's \"Nth copy module\" comments disagreeing) — surfaced independently by the code review's Blind Hunter layer as well. No new information; cross-referenced here so the review record doesn't read as having missed it."
  evidence: 'Blind Hunter; `ui/tests/shell.test.ts:1562`. See the dev-time entry above for the full history and the four disagreeing sites (c4-8, c4-10, c4-11, c4-12).'

- source_spec: `_bmad-output/implementation-artifacts/c6-5-agent-view-shell-with-focus-management-and-dismissal.md`
  summary: "Residual focus-trap-escape gap after the scrim `preventDefault()` patch (Brad's ruling, 2026-08-10, on the review's trap-escape decision item): non-interactive content INSIDE the panel — the kicker text, the summary count, any body prose — still has no `mousedown` guard, so clicking it blurs focus to `<body>` exactly as the scrim used to, and a forward Tab can still fall through the trap's forward-Tab branch (`active === last` only, no `!inTrap` catch-all) into native tab order. The heavier fix (a document-level `focusin` recovery listener, WAI-ARIA APG pattern) was declined for this story in favour of the minimal scrim-only patch."
  evidence: 'Edge Case Hunter + Blind Hunter (independently, merged in review); `ui/src/containers/AgentView/AgentView.tsx:294-353`.'

## Deferred from: code review of c6-4-companion-show-suggestions-the-agents-first-push (2026-08-10)

> Three-layer adversarial review (Blind Hunter, Edge Case Hunter, Acceptance Auditor) of the
> `feat/companion-c6-4-show-suggestions` diff. Entries below are coverage gaps and a latent
> unguarded pattern pre-existing across the companion MCP tool suite (shared with `set_active_deck`,
> c6-2) — real, but not caused by this change and not required by any AC.

- source_spec: `_bmad-output/implementation-artifacts/c6-4-companion-show-suggestions-the-agents-first-push.md`
  summary: "`show_suggestions`'s `displayed` branch interpolates `outcome.clients` directly into the result message and its `tab`/`tabs` pluralization with no `None`-guard. `PushOutcome.clients: int | None` does not statically forbid a `displayed` outcome paired with `clients=None`, so a hypothetical `PushOutcome(outcome=\"displayed\")` would render as \"...in None tabs.\" Unreachable through the shipped wire today — `_outcome_for` only ever emits `displayed` paired with `receipt.clients >= 1` — and this diff faithfully mirrors the identical unguarded pattern already shipped in `set_active_deck` (c6-2), so it is not novel to this story."
  evidence: 'Blind Hunter + Edge Case Hunter, independently; `src/mcp_server/tools/companion.py:313,320` (this story) and `src/mcp_server/tools/companion.py:192,198` (c6-2, pre-existing). No test in either tool exercises `displayed` with `clients=None` or `clients=0`.'

- source_spec: `_bmad-output/implementation-artifacts/c6-4-companion-show-suggestions-the-agents-first-push.md`
  summary: "No test drives the suggestions payload through the real FastMCP `call_tool` invocation path — every delegation test in `test_companion_tool.py` calls `show_suggestions()` as a bare coroutine with an already-constructed `SuggestionsPayload`. This story's central technical claim (the repo's first BaseModel-typed `@mcp.tool()` parameter actually gets coerced from wire JSON and cap-enforced at the FastMCP boundary before the tool body runs, not just published in the schema) is verified only by a schema-shape inspection test and by citing `mcp==1.28.0`'s library source in the story's Q1 ruling — never by an executing end-to-end call through a real MCP client/server pair."
  evidence: 'Blind Hunter; `tests/integration/mcp_server/test_companion_tool.py` (whole file) and `tests/integration/test_build_plugin.py::test_companion_show_suggestions_publishes_its_payload_shape_to_the_agent` (schema-shape only, never calls the tool).'

- source_spec: `_bmad-output/implementation-artifacts/c6-4-companion-show-suggestions-the-agents-first-push.md`
  summary: "The \"never raises\" contract, asserted in three separate docstrings (`show_suggestions`, and by convention across the companion tool module), has no test that forces `_client_push_event` to raise and confirms the exception actually propagates uncaught rather than being swallowed somewhere upstream. A gap shared with `set_active_deck` (c6-2), not unique to this diff."
  evidence: 'Blind Hunter; `src/mcp_server/tools/companion.py:292-295` states the convention; no test in `test_companion_tool.py` makes either stub raise.'

- source_spec: `_bmad-output/implementation-artifacts/c6-4-companion-show-suggestions-the-agents-first-push.md`
  summary: "`show_suggestions`'s docstring claims \"nothing here sorts, dedupes or trims\" — only the ordering half is tested (`test_payload_order_is_preserved_because_it_is_render_order`). No test drives a payload with duplicate `card_id`s to prove nothing collapses them, so a future \"helpful\" dedup added upstream would not turn any test red."
  evidence: 'Blind Hunter; `tests/integration/mcp_server/test_companion_tool.py` — no duplicate-`card_id` test exists in `TestTheSuggestionsPushIsDelegated`.'

## Deferred from: code review of c6-3-the-glass-follows-the-agents-active-deck-choice (2026-08-09)

> Three-layer adversarial review (Blind Hunter, Edge Case Hunter, Acceptance Auditor) of the
> `feat/companion-c6` diff (tests-only: `ui/src/App.test.tsx` +3 tests). Entries below are coverage
> gaps not required by any AC and pre-existing behaviour out of this story's bounds — real, but not
> caused by this change.

- source_spec: `_bmad-output/implementation-artifacts/c6-3-the-glass-follows-the-agents-active-deck-choice.md`
  summary: "The new AC-4 test (404 clears to no-active-deck) only exercises the `deck_not_found` refusal reason from a mounted App receiving a live `active_deck_changed` envelope. A mid-session re-drive that 404s or refuses with a different reason — e.g. `database_not_initialized`, whose `RETRIES_QUIETLY` entry is `true` (opposite of `no-active-deck`'s `false`) — is untested end to end; only its store-level mapping is pinned (`deck.test.ts:311`) and its `RETRIES_QUIETLY` entry (`states.ts:262-272`). AC 4 is worded specifically around the 404/`deck_not_found` case, so this is out of the story's literal scope, not a regression it introduced."
  evidence: 'Edge Case Hunter; confirmed by reading `ui/src/components/StatePanel/states.ts:262-272` (RETRIES_QUIETLY mapping) and `ui/src/state/deck.test.ts:311` (store-level refusal-reason coverage) — no App-level test drives a live push through a non-`deck_not_found` refusal reason.'

- source_spec: `_bmad-output/implementation-artifacts/c6-3-the-glass-follows-the-agents-active-deck-choice.md`
  summary: "The Q2 none-interlude test (a pin that outlives a no-active-deck interlude, self-heals on the next deck) asserts pin release and healing but includes no request-log sweep for stray fetches of the abandoned deck during the interlude — unlike Task 1's switch test, which explicitly sweeps the whole log (the c6-2 Greptile lesson: grep for the whole pattern, not just the cited line). Not required by AC 2's wording, which Task 1's test already proves; this is optional hardening the story applied asymmetrically across its own three new tests."
  evidence: 'Blind Hunter + Edge Case Hunter, independently; `ui/src/App.test.tsx:2978-3030` — no `pathsSince`/`detailReadsOf`/`activeDeckReads` assertion anywhere in the test.'

## Deferred from: code review of c6-2-companion-set-active-deck-the-agent-chooses-what-the-glass-shows (2026-08-09)

> Three-layer adversarial review (Blind Hunter, Edge Case Hunter, Acceptance Auditor) of the
> `feat/companion-c6-2-set-active-deck` diff. Entry below is a coverage gap pre-existing across the
> MCP tool suite and out of this story's bounds — real, but not caused by this change.

- source_spec: `_bmad-output/implementation-artifacts/c6-2-companion-set-active-deck-the-agent-chooses-what-the-glass-shows.md`
  summary: "`companion_set_active_deck`'s `deck_id` parameter is passed to `DeckRepository.get_deck()` without `.strip()`, so a deck id with stray leading/trailing whitespace reports `deck_not_found` even when the trimmed id exists. `deck_analysis.py` (`analyze_mana_curve`, `detect_synergies`, the swap-suggestion helper) and `deck_management.py` (`delete_deck`, the rename/tag helper) all strip; `view_deck.py` — the skeleton this story was explicitly told to copy — does not. The inconsistency is project-wide, not introduced by c6-2."
  evidence: 'Edge Case Hunter, confirmed by reading every MCP tool helper: `src/mcp_server/tools/companion.py:128` has no `.strip()`; `src/mcp_server/tools/view_deck.py:56-78` likewise has none; `deck_analysis.py:147,223,310` and `deck_management.py:379,487` do call it.'

## Deferred from: code review of c6-1 (2026-08-09)

> Three-layer adversarial review (Blind Hunter, Edge Case Hunter, Acceptance Auditor) of the
> `feat/companion-c6-1-leaf-client` diff. Entries below are coverage gaps not required by any AC and
> pre-existing behaviour out of this story's bounds — real, but not caused by this change.

- source_spec: `_bmad-output/implementation-artifacts/c6-1-leaf-client-with-health-verification-retry-once-and-the-closed-outcome-vocabulary.md`
  summary: "c6-2's two concrete needs against this module's machinery, moved here from docstring prose per Task 7's R2 rule (review finding, decision-needed, ruled by Brad 2026-08-09: trim to pointers): (1) a tool-level `deck_not_found` outcome layered above client.py's closed five-token PushOutcomeToken set — the client cannot observe it, so it belongs at the MCP tool layer, not in PushOutcomeToken. (2) `_send()` is already generic over method and path specifically so c6-2's `PUT /api/active-deck` push can reuse it — same Authorization header, same PROBE_TIMEOUT-based timeouts, same trust_env=False net — rather than a duplicated implementation."
  evidence: 'Acceptance Auditor: PushOutcomeToken and _send''s docstrings in src/companion/client.py named c6-2''s specific endpoint/outcome, which the story''s own Task 7 forbids ("mint no new forward-looking cross-module prose ... c6-2+''s needs get a dw: ledger line, not a docstring paragraph") and which the diff''s own Completion Notes had incorrectly claimed compliance with. Trimmed from client.py and re-homed here in the same review pass.'
  resolution: '**CLOSED by c6-2 (2026-08-09).** Both needs met as ledgered. (1) `deck_not_found` is a `status` on `SetActiveDeckResult` in `src/mcp_server/tools/companion.py`, returned from the database read before any HTTP; `PushOutcomeToken` is still exactly five and `TestOutcomeVocabulary` still pins that by set equality. (2) `_send()` was reused verbatim — `method="PUT", path=ACTIVE_DECK_PATH` — with no change to its signature or body. What the ledger did NOT predict, and what the story found: `_outcome_for` could not be reused, because a `PUT /api/active-deck` 200 is an `ActiveDeckSetReceipt` and not an `EventIngestReceipt`. `_active_deck_outcome_for` is its sibling, and the `event-receipt-instead` row in `test_client.py` pins that the wrong receipt shape does not parse.'

- source_spec: `_bmad-output/implementation-artifacts/c6-1-leaf-client-with-health-verification-retry-once-and-the-closed-outcome-vocabulary.md`
  summary: "No test pins the 401-vs-403 boundary at the push layer. `_outcome_for` folds every status outside {200,400,403,413} into `backend_error`, including 401 — the one code most easily confused with the retry-triggering 403. A regression or misconfigured proxy answering 401 would silently become a non-retried `backend_error` with nothing pinning that as intended."
  evidence: 'Blind Hunter. `src/companion/client.py:384-400` (`_outcome_for`) — the sole "unexpected status" test uses 418, not 401.'
  resolution: '**CLOSED by c6-2 (2026-08-09, Q5 ruled yes by Brad).** A 401 row now sits in the unexpected-status parametrization of **both** matrices: `TestPushEvent::test_an_unexpected_status_is_backend_error_unretried` (widened from a single 418 case) and `TestSetActiveDeck::test_every_other_status_is_backend_error_unretried`. Each pins 401 → `backend_error` **and** a request count of exactly one, so "not retried" is asserted rather than assumed.'

- source_spec: `_bmad-output/implementation-artifacts/c6-1-leaf-client-with-health-verification-retry-once-and-the-closed-outcome-vocabulary.md`
  summary: "No test covers a backend restart landing in the narrower window between the /health probe and the POST within a single attempt — only the between-attempts race (via on_post) is exercised. AD-4's 'verify before you send' principle is satisfied per-attempt, but the gap between live_instance() returning and _send() reading record.token inside one attempt is an inherent TOCTOU window of any verify-then-act pattern and isn't practically closable without a redesign."
  evidence: 'Blind Hunter. `src/companion/client.py:403-424` (`_attempt`).'

- source_spec: `_bmad-output/implementation-artifacts/c6-1-leaf-client-with-health-verification-retry-once-and-the-closed-outcome-vocabulary.md`
  summary: "EventIngestReceipt has no extra=\"forbid\" (src/companion/contracts.py:1313-1349), so unexpected wire fields alongside a valid `clients` are silently ignored rather than rejected — inconsistent with PushOutcome's own extra=\"forbid\" tightness. Pre-existing (c5-5), untouched by c6-1, and contracts.py is out of this story's bounds."
  evidence: 'Blind Hunter, confirmed by reading the model: `clients: int = Field(ge=0)` with no `model_config` overriding pydantic v2''s default extra="ignore".'

## Deferred from: R3 declined (2026-08-09)

- source_spec: `_bmad-output/implementation-artifacts/spec-r3-derived-class-token-guard.md`
  summary: "THE SWAP ROW IS THE UNGUARDED CASE THAT MATTERS, and the story that builds it is the only one that can close it. DESIGN.md:283-284 gives it `out-tint: '{colors.negative}'` and `in-tint: '{colors.positive}'` — red means 'cut this card', green means 'add this card'. Transposing them is semantically INVERTED (the UI confidently recommends the opposite of the truth), invisible to jsdom (which applies no CSS), and invisible to a name-matching guard (the classes are named by role, not by tone). One source-read assertion in that story — out binds negative, in binds positive — is the whole fix."
  evidence: 'Found during R3''s review 2026-08-09, and it is why R3 was declined: R3 covered class names ending in a tone (Badge, StatChip only) and would never have seen this. Precedent for the cost: c5-7 probe P15 pointed the connection dot at the wrong status token and all 1,866 tests passed. R3''s own plant re-measured it — `.badge-positive` repointed to var(--negative) gave 1 failed / 1,872 passed. Not homed on a prep item by ruling; home is the swap-row story itself.'

## Deferred from: code review of R1 (Windows integration CI lane) — 2026-08-09

> Two-layer adversarial review (Blind Hunter, Edge Case Hunter) of the `chore/c6-prep-r1-windows-ci-lane`
> diff. The factual errors the review found in the new workflow comments were patched in-branch; the
> entries below are the findings NOT caused by this change, or deliberately out of its scope.

- source_spec: `_bmad-output/implementation-artifacts/spec-r1-windows-integration-ci-lane.md`
  summary: "The C5 retro and this ledger both state that a bare `-m integration` sweeps in the twice-sighted test_list_decks_with_strategy_field flake. MEASURED FALSE 2026-08-09: tests/integration/data/test_deck_repository.py carries no marker anywhere, so the flake is in the `not integration` set and already runs in both ubuntu `quality` jobs on every push. R4's stated premise (\"a bare `-m integration` red says something — today it sweeps in the flake\") inherits the error and should be re-derived before R4 is actioned."
  evidence: 'Blind Hunter, verified independently: `grep -c integration tests/integration/data/test_deck_repository.py` returns 0; the flake is at :320. The claim originated at deferred-work.md:5728 and propagated into the retro, the R1 spec, and (until patched) a shipped ci.yml comment — a worked example of the very failure mode R2 exists to fix.'

- source_spec: `_bmad-output/implementation-artifacts/spec-r1-windows-integration-ci-lane.md`
  summary: "_BOOT_DEADLINE = 30.0 in test_live_backend.py was calibrated on the maintainer's warm dev box and has never been measured on a cold windows-latest runner. Every companion boot imports the full MCP tool tree plus fastembed/onnxruntime (src/mcp_server/__main__.py:39 -> tools/find_similar.py:35 -> src/search/embedder.py:10), measured at ~2.8 s warm locally; a cold Defender-scanning runner plus backend_two's ~2 s dead-port probe could plausibly approach the deadline. If the new lane flakes, this is the first thing to measure — do NOT reflexively tighten or loosen the constant."
  evidence: 'Both reviewers, independently. Confirmed locally: importing src.mcp_server.__main__ pulls fastembed, onnxruntime and sqlite_vec into sys.modules. No model is DOWNLOADED (that needs TextEmbedding() instantiation), so the job stays "no model, no secrets"; the cost is import and DLL scanning, not a fetch. Deliberately not pre-emptively changed — the R1 spec forbids touching the test timeouts, and the honest measurement only exists after the first CI runs.'

- source_spec: `_bmad-output/implementation-artifacts/spec-r1-windows-integration-ci-lane.md`
  summary: "The new lane's vacuity floor covers only a vanished path (exit 4) or an empty one (exit 5). A @pytest.mark.skip on the test, the walk being gutted while the file remains, or unrelated files landing in tests/integration/companion/ all leave the job GREEN with zero real-socket coverage. A `--collect-only` count assertion in the workflow step would close this and is neither the ci.yml source-reading guard ruled out at the C5 retro nor R4's marker work — it was simply never considered."
  evidence: 'Both reviewers. Edge Case Hunter notes the same file already carries explicit non-vacuity guards on the SPA-bundle and generated-types steps (ci.yml:166-174, :206-217), written on the reasoning that "it would go red" was insufficient THERE — so the new job is inconsistent with its own file. The overclaiming comment was patched in-branch; the missing guard is the open question.'

- source_spec: `_bmad-output/implementation-artifacts/spec-r1-windows-integration-ci-lane.md`
  summary: "Adding the job does not make it a gate: until `companion-integration` is added to branch protection as a required check, a red lane does not block a merge, and R1's stated purpose (a test with no automated home rots silently) is only half delivered. This is a GitHub settings change with no repo-tree representation, so nothing in the tree can track it."
  evidence: 'Blind Hunter. The R1 spec defers it to Brad by ruling ("that is Brad''s call after the lane is green") but records it nowhere durable — ledgering it here so the follow-up survives the branch.'

- source_spec: `_bmad-output/implementation-artifacts/spec-r1-windows-integration-ci-lane.md`
  summary: "Every PR — including docs-only ones — now pays a windows-latest runner (billed at 2x minutes) to install onnxruntime/fastembed/numpy from scratch in order to run a ~4 s test. The C5 retro authorised the lane on the \"the file runs in ~4-5 s\" framing; the dependency install is the actual cost and was not in that reasoning. A `paths-ignore` filter or a narrower dependency install would cut it."
  evidence: 'Blind Hunter. The repo is public so Actions minutes are free, which is why this is a note rather than a defect — but the retro''s cost premise was measured on the wrong thing and should be re-stated honestly if the lane is ever questioned.'

- source_spec: `_bmad-output/implementation-artifacts/spec-r1-windows-integration-ci-lane.md`
  summary: "src/companion/app/singleton.py:58-59 states that both `mypy src/` and `mypy src/ --platform linux` are mandatory, while ci.yml:67-68 runs `--platform win32` and the comment above it records why `--platform linux` was explicitly REJECTED as a no-op on an ubuntu runner. The generated mirror plugin/server/src/companion/app/singleton.py repeats the stale sentence. Pre-existing; natural R2 sweep material."
  evidence: 'Blind Hunter. Not caused by the R1 change — the contradiction predates it — but it is the same class of falsified cross-module prose R2 owns, and the mirror means the fix is a two-site edit plus a plugin rebuild.'

- source_spec: `_bmad-output/implementation-artifacts/spec-r1-windows-integration-ci-lane.md`
  summary: "test_live_backend.py phase 2 calls client.live_instance() exactly once against a 1 s connect / 2 s read / 5 s total budget (src/companion/client.py), with probe_health swallowing every cause — unlike _await_record, it does not poll. On a loaded runner one slow first request fails the whole test with the uninformative message \"live_instance() found nothing\". Also, websockets.connect is not given proxy=None, so an HTTP_PROXY/ALL_PROXY set without no_proxy would route the handshakes off-box (the httpx sibling already sets trust_env=False)."
  evidence: 'Edge Case Hunter. Both are pre-existing properties of the c5-8 test rather than anything R1 changed — but R1 is what moves this test onto shared CI hardware where a slow first request and a proxied environment are both more likely than on the maintainer''s box.'

- source_spec: `_bmad-output/implementation-artifacts/spec-r1-windows-integration-ci-lane.md`
  summary: "Job topology is now asserted in prose in five uncounted places (ci.yml's header, ci.yml's job comment, ui/README.md, ui/tests/fonts.test.ts, both .gitattributes files) with no drift check, in a repo that drift-checks plugin/, the SPA bundle and generated types. A second Windows job or a fourth job silently falsifies several at once — the same N-way prose-sync obligation R2 was created for, now with CI topology as its subject."
  evidence: 'Edge Case Hunter, and directly demonstrated by this very change: the R1 sweep had to touch six prose sites across four directories to keep one fact true, and the first attempt missed three of them.'

## Deferred from: C6-prep scope split (2026-08-09)

> The C6-prep intent named four action items (R1, R2, R3, R5). Split to a single goal — **R1**,
> the Windows integration CI lane — because each of the four is an independently reviewable and
> mergeable deliverable. The three below are NOT new findings: each is already an open `epic: c5`
> action item in `sprint-status.yaml` with a ruling recorded at its own entry in this file. These
> rows exist only so the split is traceable; the action item stays the record of truth.

- source_spec: none
  summary: 'R2 — the standalone prose-sync sweep: cross-module rulings get ONE canonical home (this ledger), the 5+ Q3/AD-5 narration sites become one-line pointers, scripts/dump_openapi.py''s changelog paragraphs are deleted, and dw:5197''s twice-confirmed test_committed_schema.py docstring sentence is absorbed. Standing rule rides with it: no new forward-looking cross-module prose in docstrings.'
  evidence: 'Split from the C6-prep intent 2026-08-09 (Brad chose R1 first). Independently shippable: touches docstrings and one deleted paragraph only, zero behaviour change, reviewable alone. Ruled at the C5 retro — see the dw:5244 and dw:5252 regions and epic-c5 action item R2.'

- source_spec: none
  summary: 'R3 — one repo-wide derived class→token source-reading guard covering every status-semantic binding (Badge tones, ManaPip colours, deck-row live tint, connection-pill dot), generalising c5-7 probe P15''s fix. Existing per-component guards are kept, not deleted. Owed BEFORE Epic 6''s first view story adds more surfaces of the same shape.'
  evidence: 'Split from the C6-prep intent 2026-08-09 (Brad chose R1 first). Independently shippable: a new derived guard, natural home ui/tests/token-usage.test.ts, merges alone. Sequencing affinity only with R5 (R5''s harness is what would plant against this guard) — not a dependency. Ruled at the C5 retro — see the dw:5617 region and epic-c5 action item R3.'

- source_spec: none
  summary: 'R5 — the vitest half of the probe harness (re-keyed from C4 item 4): full `npm test` with a validated collected-test count before a run is scored, native uppercase-drive path, vitest crash-signature refusal, do-nothing negative controls. Owed BEFORE Epic 6''s first frontend story.'
  evidence: 'Split from the C6-prep intent 2026-08-09 (Brad chose R1 first). Independently shippable: a new harness capability with its own negative controls; the Python half already ships at scripts/probe_harness.py. Three of the five recorded harness lies are frontend-specific and c5-7 ran fifteen frontend plants by hand — that is the measured cost of leaving it. Ruled at the C5 retro — see the dw:5115 region and epic-c5 action item R5.'

## Deferred from: code review of c5-6-client-reconnection, Group 3 (2026-08-08)

> UI shell/API/dev-proxy diff (App.tsx, api/client.ts, api/schema.ts, components/StatePanel/states.ts,
> config/devProxy.ts + tests) — third of a chunked review; 0 patch findings survived (one attempted
> patch on devProxy.ts's WEBSOCKET_PATTERNS typing was reverted after testing showed it broke real
> compilation).

- source_spec: `_bmad-output/implementation-artifacts/c5-6-client-reconnection-with-backoff-and-a-fresh-ticket-per-attempt.md`
  summary: "agentEventOf only validates the `kind` discriminant, not `id`/`ts`/`payload` — a frame like {\"kind\":\"deck_changed\"} with no id/ts/payload passes through typed as a full AgentEvent. Not exercised today (system-event kinds are dispatched by kind alone; the four agent-view kinds are dropped unread), becomes actionable when Epic 6 builds the agent views and reads those fields."
  evidence: 'Blind Hunter + Edge Case Hunter, independently; ui/src/api/client.ts:701-716. NOT TRIGGERED BY c6-3 (checked 2026-08-09): that story is Epic 6''s first frontend story, but it reads no payload field at all — by ruling, the `active_deck_changed` handler ignores both the kind and `payload.deck_id` and re-drives the boot, which asks `GET /api/active-deck` first (connection.ts:96-108). Its tests drive frames through `push()` with a payload present and assert only surface and request-log outcomes, so nothing here is exercised or closed. STAYS OPEN for the first story that actually reads those fields — c6-4 onwards, when the agent views land. NOT TRIGGERED BY c6-4 (checked 2026-08-10) either: that story is Python-only — an MCP push tool with no `ui/` diff at all — so `agentEventOf` is neither called nor changed by it, and the SPA still drops the `suggestions` kind unread. The trigger is c6-7, the story that renders suggestion payload fields. **PARTIALLY TRIGGERED BY c6-6 (2026-08-11), and the ruling is recorded rather than the entry closed.** c6-6 is the first code in the app to READ an agent-view payload: `suggestionsViewOf` reads `payload.title` and `payload.items`. Brad ruled Q6 as recommended — **`agentEventOf` stays kind-only** (its documented register; widening a shipped, pinned narrower is a bigger change than this story needs) and the defence lives at the builder, which is TOTAL: `event.payload?.items ?? []` and a trimmed-title fallback construct a valid empty view for a bare `{"kind":"suggestions"}` frame. That is mandatory independent of the malformed-frame case, because `SuggestionsPayload.title` and `.items` are both OPTIONAL in the generated types even for honest wires. Pinned by three builder rows in `ui/src/state/agentView.test.ts` (absent payload / absent items / blank title) and one end-to-end test in `ui/src/App.test.tsx` that serialises a frame with no `payload` key at all and asserts the view opens empty with the socket still open. **What remains open is the half c6-6 does not reach: no ITEM field is validated** — a `card_id` that is not a string, or a missing `reason`, still passes through untouched, because this story renders no row. That stays c6-7''s, at the row that renders it (FR-13/AD-7: one bad entry degrades to the placeholder, the push never fails wholesale). **CLOSED BY c6-7 (2026-08-11), at exactly the point this entry names.** `SuggestionsView.tsx` types the row''s prop as `UntrustedItem` — every field of the store''s item type remapped to `unknown` — so the compiler REQUIRES a gate rather than calling one redundant, which is what stops a later tidy-up deleting it on the strength of the generated types. Four readers, four gates: a non-string `card_id` becomes `''''` (the app''s own value for "an id it cannot render": `hydrateCard` refuses it terminally with `placeholder: ''unknown-card''` and issues NO request, so a malformed item lands on AC 4''s degradation through shipped machinery rather than a new refusal invented at the row); a missing or non-string `reason` renders an empty line with the row otherwise normal (the element is unconditional, because dropping it would change the row height and therefore the derived width of the thumbnail beside it); a non-string `category` renders no badge; and `confidence` is checked for MEMBERSHIP of the three wire tokens rather than merely for being a string, because that slot is a chrome token in a 10px uppercase role. Pinned by four unit rows and one App-level row, all of which assert the NEIGHBOURS still render. `agentEventOf` remains kind-only — the c6-6 ruling stands, and this entry is now closed on both halves.'

- source_spec: `_bmad-output/implementation-artifacts/c5-6-client-reconnection-with-backoff-and-a-fresh-ticket-per-attempt.md`
  summary: "The equivalence between the agent's outbound POST /agent/events body shape and the WebSocket frame the browser actually receives is asserted only in a comment (ws.py broadcasts the ingested event verbatim), with no cross-language contract test pinning it."
  evidence: 'Blind Hunter; ui/src/api/schema.ts, ui/src/api/client.ts:662-669.'

## Deferred from: code review of c5-6-client-reconnection, Group 1 (2026-08-08)

> UI reconnection-core diff (`connection.ts`, `socket.ts`, `deck.ts`, `cards.ts`, `systemState.ts`,
> `poller.ts` + tests) — first of a chunked review; Groups 2 (backend) and 3 (UI shell/API/dev-proxy)
> still queued.

- source_spec: `_bmad-output/implementation-artifacts/c5-6-client-reconnection-with-backoff-and-a-fresh-ticket-per-attempt.md`
  summary: "useAgentConnection's socket does not reconcile the shared `connection` field on `stop()`/remount — if the component were ever unmounted and remounted while status was `down` or `live`, the store would show a stale value until the new socket's status next changes."
  evidence: 'Blind Hunter + Edge Case Hunter, both independently; ui/src/state/socket.ts:491-497 (stop()) and ui/src/state/connection.ts (useAgentConnection). Pre-existing pattern: App is documented as the sole, permanently-mounted consumer of useSystemState, useDeckState and now useAgentConnection alike; none of the three defends against a remount all three explicitly disclaim as unsupported.'

- source_spec: `_bmad-output/implementation-artifacts/c5-6-client-reconnection-with-backoff-and-a-fresh-ticket-per-attempt.md`
  summary: 'Two independent triggers (redriveDeckBoot() fired directly on a system event, and the pre-existing subscribeSystemState edge-trigger in useDeckState) can both re-drive the same DeckBoot instance in quick succession around one event, costing a redundant fetch.'
  evidence: 'Blind Hunter; ui/src/state/deck.ts:559-565, ui/src/state/connection.ts:352-364. Idempotent and generation-guarded — low impact, narrow timing window.'

- source_spec: `_bmad-output/implementation-artifacts/c5-6-client-reconnection-with-backoff-and-a-fresh-ticket-per-attempt.md`
  summary: 'Whether restartPollIfStopped/restartPoll actually close dw:3472/3544 and dw:3463 depends on backend behaviour outside this diff slice (does a DB rebuild or later DB death produce a deck_changed/active_deck_changed frame, or drop the socket?). Needs confirmation in the Group 2 (backend) review pass.'
  evidence: 'Acceptance Auditor; ui/src/state/systemState.ts:186-216.'

- source_spec: `_bmad-output/implementation-artifacts/c5-6-client-reconnection-with-backoff-and-a-fresh-ticket-per-attempt.md`
  summary: 'connection.ts (wiring restartPoll -> resetCardAttempts -> redriveDeckBoot on reconnect, and redriveDeckBoot -> restartPollIfStopped on a system event) has no dedicated unit test in this slice, nor does AgentSocketOptions.initialStatus. Needs confirmation in the Group 2 pass that App.test.tsx actually pins this call order rather than merely observing an eventual refetch.'
  evidence: 'Acceptance Auditor + Blind Hunter; ui/src/state/connection.ts (whole file), ui/src/state/socket.ts:223 (initialStatus).'

## Deferred from: code review of story-7.4 (2026-07-17)

> Test-hardening gaps in the `assess_deck_power` e2e suite (tests-only story; all 7 ACs met, suite green). Neither is a product defect — both are e2e-coverage extensions whose behavior is already guarded at the unit/model level.

- source_spec: `_bmad-output/implementation-artifacts/7-4-end-to-end-tool-test-determinism-diff-regression.md`
  summary: 'Bracket-4 floor (≥4 confirmed Game Changers) is unreachable through the e2e client — the `_assessment_cards` fixture seeds only two `game_changer=True` cards and Commander singleton rules cap each at quantity 1, so a `bracket == 4` result (and the GC ≥4 gate in dimensions.py) is never exercised end-to-end. Future hardening: add ≥4 distinct GC cards to reach the floor-4 gate through the tools.'
  evidence: 'Edge Case Hunter trace: dimensions.py GC gate GC_BRACKET_FOUR_MIN=4, count is quantity-aware; fixture exposes e2e-gc-bolas + e2e-gc-aura only. The ≥4 gate is covered by unit scorer tests (test_assessment_scorer.py), not this client suite.'

- source_spec: `_bmad-output/implementation-artifacts/7-4-end-to-end-tool-test-determinism-diff-regression.md`
  summary: 'The populated `data_vintage` combo values are never positively asserted at the e2e/wire level — the absent-snapshot test pins the null path (`combo_snapshot_imported_at`/`export_version is None`), but no seeded e2e test asserts the present path equals the fixture''s seeded `export_version="5.6.0"` / `imported_at="2026-07-16T09:07:00+00:00"`. A passthrough bug that dropped or garbled the vintage on the present path is caught only at model level (7.3 helper tests). Future hardening: assert the populated vintage in the commander happy-path test.'
  evidence: 'Blind Hunter + Acceptance Auditor: null-vs-present vintage contract is half-covered e2e; seeded values live in tests/fixtures/combo_snapshot.py:63-65.'

## Deferred from: code review of spec-pre-epic-7-real-deck-gate (2026-07-17)

- source_spec: `_bmad-output/implementation-artifacts/spec-pre-epic-7-real-deck-gate.md`
  summary: '`combo_potential` counts `almost_included` variants whose single missing piece is not legal in the deck''s format, inflating the dimension for constructed decks — the matcher (`match_combos`) and the dimension scoring are format-blind on the missing piece.'
  evidence: 'G-R2 gate run 2026-07-17: Abzan Dragons and Prismatic Dragon (both Standard) each scored combo_potential=100 from Betor-anchored almost_included variants whose missing partners (e.g. Archfiend of Despair, Mycosynth Lattice, Wound Reflection) are not Standard-legal — the combo can never be completed in-format. Pre-existing product behavior (5.6/6.3 design), surfaced by the Blind Hunter review of the gate report; a natural Epic 7 calibration input.'

- source_spec: `_bmad-output/implementation-artifacts/spec-pre-epic-6-importer-gate.md`
  status: ✅ RESOLVED (2026-07-16, commit 18880dc)
  summary: 'Transformer rejects all 33 reversible_card printings ("Name // Name") with `missing required field(s): type_line` — Scryfall''s reversible layout carries type_line (and cmc) only on card_faces. Fix = derive required fields from faces in transform_scryfall_card (a transform-contract change held back by the gate spec''s Ask-First boundary); until then those 33 oracle identities keep pre-existing rows and are surfaced by the stale-remaining warning each run.'
  resolution: 'Shape-gated face derivation in transform_scryfall_card: cards with NO top-level type_line (the reversible signature) derive name (deduped, so "Anje Falkenrath // Anje Falkenrath" -> "Anje Falkenrath" for exact decklist lookups), type_line, mana_cost, cmc, colors (WUBRG-ordered face union) and all-faces-agree power/toughness from card_faces; ijson Decimal face values sanitized to float so the card_faces JSON column serializes. Cards WITH a top-level type_line transform byte-identically (transform/MDFC/split untouched). Test-pinned (4 new unit tests); next import run should show 0 rejects and clear the 33-identity stale warning.'
  evidence: 'Live acceptance run 2026-07-15 (b74-successor): all 33 rejects share the doubled-name + type_line-missing signature (Reckoner Bankbuster, Anje Falkenrath, Zndrsplt, …); the gate''s G-I2 diagnostics made the reason string visible for the first time. Parallels the resolved oracle_id face-fallback fix (resolve_oracle_id, 0.3.0).'

- source_spec: `_bmad-output/implementation-artifacts/spec-pre-epic-6-importer-gate.md`
  summary: 'TOCTOU window in reconcile_oracle_identities: a deck_cards row committed by a concurrent connection (e.g. import_decklist via the live MCP server) between the reconcile''s deck_cards plan-scan and its write phase is never repointed, and the stale cards row is then deleted with FK enforcement OFF — a silently dangling deck_cards.card_id. Fix candidates: re-scan deck_cards after acquiring the write lock (BEGIN IMMEDIATE / first-write upgrade), or verify-and-repoint residual references just before the delete.'
  evidence: 'Edge Case Hunter trace over scryfall.py plan-scan vs execute+delete phases; SQLite deferred transactions take no lock until the first write, and the central DB is shared with a live MCP server. Window is narrow (scan-to-write span) and requires a concurrent deck write during a bulk import.'
- source_spec: `_bmad-output/implementation-artifacts/spec-pre-epic-6-importer-gate.md`
  summary: 'Reconcile deletions orphan card_vec/card_embedding_meta rows until a build_search_index run with prune=true (prune defaults to False): KNN over-fetch returns deleted ids that vanish at the cards JOIN, thinning semantic results. Consider auto-pruning vectors for deleted card ids at reconcile time, or defaulting prune=true when the importer reports rows_deleted > 0.'
  evidence: 'Both reviewers; src/search/index_builder.py orphan cleanup only runs during index builds, and build_search_index.prune defaults False. Mitigated in-gate by the result message now recommending prune=true after deletions.'

## Deferred from: dev of story-5.9 (2026-07-14)

> Live-DB data-quality issues discovered while closing the 5.9 benchmark gate. Out of the
> story's frozen scope (AC10: no `src/data/**` / `scripts/` edits); the operational damage was
> repaired by hand on Brad's machine (documented in the 5.9 Completion Notes) but the root
> causes live in the importer.

- source_spec: 5-9-pure-score-entry-point-benchmark-validation.md
  summary: 'Re-running `import_scryfall_data.py` accumulates duplicate rows per card name: Scryfall''s default_cards "preferred printing" per oracle identity changes between bulk snapshots, so each refresh inserts rows under NEW printing ids while the old printing rows persist (observed 2026-07-14: 51,189 rows for ~38k cards; 12,992 stale rows with `game_changer` NULL because the upsert only touches the new ids). Consequences: `find_by_name_exact` (ORDER BY id LIMIT 1) resolves 4,711 names to an arbitrary STALE printing, and any new backfilled column stays NULL on stale rows. Fix candidates: reconcile/delete rows whose oracle_id gained a fresh printing (mind deck_cards FK references), key the upsert by oracle_id, or propagate oracle-level fields (like game_changer) across all rows of the same oracle_id post-import.'
  evidence: 'Central cards.db state 2026-07-14 pre-repair; epic-4 retro recorded 0 NULL on 2026-07-12, the Jul-14 refresh reintroduced 12,992. Hand-repair applied: copy game_changer across same-oracle_id rows, then set the 36 residual NULLs FALSE (none on the GC list).'
- source_spec: 5-9-pure-score-entry-point-benchmark-validation.md
  summary: 'The bulk import reports "Errors: 36" with no per-card diagnostics reaching the operator log tail, and those 36 cards (incl. Blood Crypt, Hallowed Fountain, Reckoner Bankbuster) silently keep stale data — likely the new printing id colliding with a uniqueness constraint while a different-id row for the same oracle identity already exists. Surface the failing card names + exception class in the import summary, and count them against a "stale rows remaining" warning.'
  evidence: 'b74hepj01 import run 2026-07-14: 38,197 inserted / 36 errors; the 36 error cards exactly matched the 36 names left game_changer-NULL after the oracle_id repair.'

## Deferred from: code review of story-5.8 (2026-07-14)

> Both are Story 5.9 (calibration / threshold + weight tuning) concerns surfaced during the 5.8 review — neither is a correctness defect in the shipped code (all inputs are frozen, type-pinned, and test-pinned). Parallels the 5.7 `win_turn_band` defer directly below.

- source_spec: 5-8-for-format-aggregate-tier-label-standard-fork-confidence-vocabulary.md
  status: ✅ RESOLVED (Story 5.9, 2026-07-14)
  summary: '`tier_label`/`aggregate_score` trust their frozen profile''s shape & weight validity: `tier_label` (aggregate.py:146) assumes exactly 4 strictly-ascending `tier_thresholds` (a 5+-tuple → IndexError; non-ascending → silent mislabel), and `aggregate_score` (aggregate.py:116) assumes non-negative + finite weights (NaN → ValueError; negative → silent monotonicity break). Unreachable with the shipped frozen+tested profiles, but 5.9 hand-tunes both `weights` and `tier_thresholds` — optional cheap defense-in-depth for the tuning workflow.'
  evidence: 'aggregate.py:146 `TIER_LABELS[bisect_right(profile.tier_thresholds, score)]`; aggregate.py:116 weighted sum. Invariants pinned by profiles type `tuple[int,int,int,int]` + test_assessment_profiles.py (non_negative, sum-to-1.0, ascending). Same class as the 5.7 `win_turn_band` guard defer.'
  resolution: '`aggregate_score` now raises `ValueError` on a negative or non-finite weight; `tier_label` raises on cuts not strictly ascending within `(0, 100)`. Test-pinned (`TestStory59Guards` in test_assessment_aggregate.py, incl. a shipped-profiles-pass check).'
- source_spec: 5-8-for-format-aggregate-tier-label-standard-fork-confidence-vocabulary.md
  status: ✅ RESOLVED (Story 5.9, 2026-07-14)
  summary: '`tier_thresholds` domain `(0, 100]` permits a cut of exactly 100, making the top band (`Competitive`) a degenerate single-point band reachable only by an exact score of 100. Harmless for the shipped `(20, 40, 60, 80)`; add a guardrail when 5.9 re-cuts per-format anchors.'
  evidence: profiles.py:126 field type + test_assessment_profiles.py in-domain check `0 < cut <= 100`.
  resolution: 'Domain tightened to `(0, 100)`: `tier_label` guards it and the aggregate profile-shape test now asserts `0 < cut < 100` (a cut at exactly 100 is a tuning mistake, never a meaningful configuration).'

## Deferred from: code review of story-5.7 (2026-07-14)

> All three are Story 5.9 (calibration / benchmark tuning) concerns surfaced during the 5.7 review — none is a correctness defect in the shipped code.

- source_spec: 5-7-dimension-vector-commander-bracket-floor-cedh-candidacy.md
  status: ✅ RESOLVED — KEPT AS-IS, documented (Story 5.9, 2026-07-14)
  summary: '`card_advantage` dimension structurally caps at 98 (80 count-weight + 18 max tutor bonus), never reaching 99/100 — revisit the ceiling during 5.9 calibration.'
  evidence: dimensions.py:562 `_card_advantage_score`; provisional/5.9-owned mapping by design.
  resolution: 'Keep-decision documented in `_card_advantage_score`''s docstring after the calibration pass: the 2-point headroom is invisible under the aggregate weights and benchmark cuts, and re-normalizing the two terms would change every deck''s score for zero benchmark benefit.'
- source_spec: 5-7-dimension-vector-commander-bracket-floor-cedh-candidacy.md
  status: ✅ RESOLVED (Story 5.9, 2026-07-14)
  summary: '`sixty_card` curve targets (interaction 8 / draw 6 / instant-cheap 4) are self-labelled provisional guesses, and mana_efficiency shares one land-delta penalty slope across 99- and 60-card decks — Standard vs Commander vectors are not on a comparable scale until 5.9 anchors them.'
  evidence: dimensions.py:177-201 target dicts; only Commander targets trace to the Command Zone template.
  resolution: 'Closed by per-format `tier_thresholds` anchoring: Standard cuts (28, 45, 65, 85) are anchored against the four Standard benchmark bands independently of Commander''s (20, 40, 60, 80), and raw 0-100 aggregates are never compared across formats — stated in the STANDARD_PROFILE tier_thresholds comment. The sixty_card curve-target VALUES stay provisional (the Standard benchmark orders cleanly without touching them).'
- source_spec: 5-7-dimension-vector-commander-bracket-floor-cedh-candidacy.md
  status: ✅ RESOLVED (Story 5.9, 2026-07-14)
  summary: '`_speed_score` has no guard for a malformed `win_turn_band` (`lo > hi`) — unreachable with the shipped frozen+tested profiles, but a future 5.9 band edit of the form `hi = lo-4` divides by zero and `hi < lo` inverts the mapping. Optional cheap defense-in-depth for the band-editing workflow.'
  evidence: dimensions.py:484 (`slowest - fastest = band_hi - band_lo + 4`); invariant documented at profiles.py:86-87.
  resolution: '`_speed_score` now raises `ValueError` on `lo > hi` (a `lo == hi` pinpoint band stays valid — the ±2 pad keeps the divisor non-zero). Test-pinned (`TestStory59WinTurnBandGuard` in test_assessment_dimensions.py).'

## Deferred by scope-split: Kotis session plugin-improvement leads (2026-07-10)

> Source: `temp/kotis-fangkeeper-brawl.md` §"Plugin improvement leads" (live Brawl sessions
> 2026-07-05). Brad ran `bmad-quick-dev` on all 8 leads and chose **Split** at the multi-goal
> gate: leads 1 (games union) + 3 (brawl singleton) are the current run; the six below are
> deferred, each an independently shippable quick-dev run. Full observed evidence for each is in
> the source file.

- source_spec: none
  summary: Add a saboteur/combat-damage-trigger pattern to `detect_synergies` (rated the Kotis deck "low cohesion").
  evidence: Split from the 8-lead Kotis improvement intent; isolated synergy-logic change, independent of the validator/import work chosen first.
- source_spec: none
  summary: Bulk deck-import MCP tool accepting an Arena export blob (per-line resolve, per-line ok/ambiguous/not-found report).
  evidence: Split from the 8-lead Kotis improvement intent; a new standalone tool (saving the 60-card deck took ~50 `add_card_to_deck` calls, the 100-card port 75 more).
- source_spec: none
  summary: Import-time legality-snapshot sanity check for pool-superset invariants (e.g. Pym Particles `standardbrawl: legal` but `brawl: not_legal` is impossible).
  evidence: Split from the 8-lead Kotis improvement intent; import-script validation, standalone. Natural pairing with the games-union import work if the import script is revisited.
- source_spec: none
  summary: Strip parenthetical reminder text from oracle text before embedding (menace cards pollute "unblockable" queries, convoke pollutes "ramp"); requires index rebuild.
  evidence: Split from the 8-lead Kotis improvement intent; embedding-pipeline change with a rebuild cost — batch with other re-embed work if possible.
- source_spec: none
  summary: Intersection mode (or rerank/decompose guidance) for compound semantic queries, plus a playability prior on ranking (Llanowar Elves absent from a ramp top-40 Prismite topped).
  evidence: Split from the 8-lead Kotis improvement intent; the largest, most design-heavy lead — benefits from the reminder-text fix landing first. Overlaps the existing "Compound-intent dilution" Epic-3 candidate below.
- source_spec: none
  summary: '`capture_arena_window` tool — screenshot the MTGA window (Win32 `PrintWindow`/`mss`) for board reads; opt-in, graceful `window_not_found`.'
  evidence: Split from the 8-lead Kotis improvement intent; first tool touching the local machine rather than the card DB, so it needs its own opt-in design pass.

## Deferred from: code review of spec-games-union-brawl-singleton (2026-07-10)

- source_spec: `_bmad-output/implementation-artifacts/spec-games-union-brawl-singleton.md`
  status: ✅ RESOLVED (0.3.0, 2026-07-11)
  summary: Face-keyed aggregation (`card_faces[0].oracle_id` fallback in `src/data/importers/aggregate.py`) is inert — `transform_scryfall_card` hard-requires a top-level `oracle_id`, so reversible-layout cards are still rejected downstream, and `reconcile_games` matches aggregates by `CardModel.oracle_id` only.
  evidence: Blind Hunter traced the pass-2 path — cards grouped by the face/self fallbacks reach the transformer and are error-counted there (pre-existing transformer limitation, parity with the old oracle_cards import). Fix belongs in a transformer pass (accept face-level oracle_id) plus a reconcile lookup keyed the same way as `group_key`.
  resolution: Extracted `resolve_oracle_id` (top-level → `card_faces[0].oracle_id`) as the single oracle-identity source shared by `group_key` and `transform_scryfall_card`; the transformer no longer hard-requires a top-level `oracle_id`, so reversible cards import with `oracle_id == group_key` — which makes the `reconcile_games` lookup-by-`oracle_id` align with `group_key` automatically. Verified end-to-end: a reversible card dedupes to one row with unioned games (was dropped entirely).
- source_spec: `_bmad-output/implementation-artifacts/spec-games-union-brawl-singleton.md`
  status: ✅ RESOLVED (0.3.0, 2026-07-11)
  summary: '`reconcile_games` failure after `import_cards` has committed leaves the DB populated but `initialize_database` reports `status="error"`, and a plain retry short-circuits `already_initialized` with games left stale.'
  evidence: Edge Case Hunter, `src/data/importers/scryfall.py` reconcile stage — the import commits per batch, so a reconcile-stage DatabaseError (lock/disk) can't roll it back. Narrow failure window; remedy is `update=true` (re-runs reconcile). Consider catching reconcile errors as a warning or surfacing a "re-run with update=true" hint in the error message.
  resolution: The orchestrator now catches `IntegrityError`/`DatabaseError` from the reconcile stage and logs a warning instead of failing the run (the cards already committed), so the import reports success and stale pre-existing rows refresh on the next `update=true`. The first-run half is additionally covered by the 0.3.0 `import_state` marker (a first-run failure leaves the DB flagged partial, so a retry re-imports rather than short-circuiting).

## Deferred from: code review of first-run-data-initialization (2026-06-28)

> Surfaced by the 3-reviewer adversarial pass on `spec-first-run-data-initialization.md`. The
> contract gap (uncaught `init_database` failure) and two real robustness items (partial-import
> *exception* path now clears the truncated `cards`; `build_search_index(rebuild=True)` now resolves
> the embedder before the destructive drop) were patched in-branch. The items below are real but
> either pre-existing config or narrow/concurrency edges left for a focused later pass.

- **✅ RESOLVED (0.3.0, 2026-07-11).** No `busy_timeout` → `SQLITE_BUSY` on concurrent writers (Edge Case Hunter, HIGH). Neither the
  async engine (`src/data/database.py::create_engine`) nor the sync `ConnectionFactory`
  (`src/search/connection.py`) sets `busy_timeout`/`connect_args={"timeout": …}`, so SQLite's
  default-0 timeout makes a second writer fail immediately with `database is locked` rather than
  waiting. Pre-existing config, but the new `initialize_database` (bulk write) + `build_search_index`
  (index write) tools make concurrent-writer collisions more likely. Fix project-wide: set
  `PRAGMA busy_timeout=5000` on the sync factory and `connect_args={"timeout": 5}` on the async
  engine (matches the documented WAL topology).
- **✅ RESOLVED (0.3.0, 2026-07-11) — `import_state` in-progress marker.** Process-kill mid-import leaves a partial DB mistaken for complete (Edge Case Hunter, HIGH —
  *exception* half patched). The importer commits per 1000-card batch; the in-branch fix clears the
  partial `cards` when the import raises, so a *failed* import retries cleanly. But a hard process
  kill between batches can't run that cleanup, leaving e.g. 1000 of ~30k cards — which the ≥1-row
  idempotency check then reports as `already_initialized`, permanently. Full fix: write an
  `import_complete` sentinel (meta row) only after the final commit and gate `already_initialized`
  on it, or make the import a single transaction.
- **Corrupt/malformed DB file raises out of the "never raises" guards** (Edge Case Hunter, MED). A
  truncated `-wal` / malformed header makes even the `sqlite_master` probe in either
  `is_database_initialized` raise `DatabaseError`/`OperationalError`; because the guard runs *above*
  each tool's `try/except`, that propagates as a raw error instead of a graceful status. Fix: wrap
  the probes in `try/except (OperationalError, DatabaseError): return False`, or add a distinct
  `database_corrupt` status.
- **Concurrent `initialize_database` double-imports** (Edge Case Hunter, MED). The idempotency check
  and the import aren't atomic/locked, so two concurrent invocations both download + import (the
  upsert importer keeps data correct, but wastes a ~3-min download and contends on the write lock —
  near-certain to fail one of them until `busy_timeout` above is set). Fix: an app-level
  `asyncio.Lock` around the tool, or rely on `busy_timeout` so the loser re-checks and returns
  `already_initialized`.

## ✅ Resolved by first-run-data-initialization (2026-06-28)

> Closed by `spec-first-run-data-initialization.md` — the in-client `initialize_database` /
> `build_search_index` tools plus a graceful `database_not_initialized` status across every
> card/deck tool. The items below are closed; they remain listed in their original sections for
> traceability.

- **MCPB bundle has no first-run data bootstrap or guidance** (mcpb-bundle review, High-for-UX). A
  fresh `.mcpb` now bootstraps in-client: the assistant runs `initialize_database` (Scryfall card
  import) and `build_search_index` (embedding index), and every card/deck tool returns
  `database_not_initialized` with a run-`initialize_database` hint instead of the opaque "A database
  error occurred". No prebuilt DB is shipped (license held — build-on-first-run only).
- **`README.md` overclaimed Claude-Desktop first-run + that `setup.py` builds the index**
  (mcpb-bundle review `README.md:68`; licensing-repo-health review `README.md:38`/`:44`). The Quick
  start and Claude Desktop sections now describe the real flow: `setup.py` (or `initialize_database`)
  downloads the cards; the semantic index is a separate `build_search_index` step.
- The semantic tools' `index_unavailable` message now points at the `build_search_index` **tool**
  rather than the `scripts/build_card_embeddings.py` terminal command (which a GUI client can't run).

> Still open from those reviews (out of this spec's scope): `setup.py:87` prints the stale
> `./data/cards.db` path; `project-context.md`'s "all MCP tools sync `def`" drift; the `report_bug`
> tool is **intentionally not** guarded (it is card-data-independent and already graceful — see the
> spec's Change Log).

## Public-release goals deferred by scope-split (2026-06-27)

> Source: `RELEASE-STRATEGY.md`. Brad ran `bmad-quick-dev` to "execute RELEASE-STRATEGY.md" and
> chose **Split — DB centralization first** at the multi-goal gate. This run (branch
> `feat/central-data-dir`) implements **only §3 (central OS data dir)**. The remaining
> independently-shippable deliverables below are deferred and should each be picked up as their
> own quick-dev run, in roughly the strategy's §7 order. Each links back to the strategy section.
>
> **Two cross-cutting constraints carried forward:**
> 1. **The prune only _untracks_ the workflow's framework + skills** (`_bmad/`, `.claude/skills/bmad-*`)
>    via `git rm --cached` + gitignore — removed from the public repo but kept on disk, so the workflow
>    still runs locally — and **`_bmad-output/` stays tracked** (Brad, 2026-06-28). No mid-run ordering
>    hazard anymore, since nothing bmad-related is hard-deleted from the working tree.
> 2. **Outward-facing / irreversible steps stay manual.** Secret scan, `git tag v0.1.0`, cutting
>    the GitHub Release, and flipping the repo public are Brad's call — automate the prep, stop
>    at that line.

- **Prune legacy + dev tooling (§1, §2).** Three distinct treatments (Brad, 2026-06-28):
  - **Hard delete (`git rm`):** the legacy PydanticAI/Chainlit stack (`legacy/`, `public/`),
    superseded root docs, scratch `scripts/test_*.py`, `examples/`, internal `docs/` files; curate
    `docs/` down to architecture/bug-report/performance.
  - **Untrack but keep on disk (`git rm --cached`) + gitignore:** the BMAD **framework + dev skills**
    (`_bmad/`, `.claude/skills/bmad-*`) — gone from the public repo but kept locally so the workflow
    still runs.
  - **KEEP tracked:** `_bmad-output/` (planning + implementation artifacts = public design record).
  Then edit `.gitignore`: un-ignore `.github/`, add `/_bmad/` + `.claude/skills/bmad-*/`, but **not**
  `/_bmad-output/`. Mechanical; no logic.
- **Trim deps & package metadata (§6).** `pyproject.toml`: drop orphaned `anthropic`/`openai`/
  `asyncpg`, move `logfire` to an optional `observability` group, verify-and-likely-drop
  `tenacity`/`python-dotenv`, add `platformdirs` (already added by the §3 run — reconcile), remove
  the `[dependency-groups] legacy` block, rewrite the "built with PydanticAI" description, set a
  real `authors` email (sathias@slopstudio.net), add `[project.scripts]` console entry points.
  (**`.env.example` cleanup — including deleting the `LEGACY ONLY` section and adding the
  `PLANESWALKER_DATA_DIR` note — was pulled into the `feat/central-data-dir` run at Brad's
  request, so it's done; only the `pyproject.toml` work remains under §6.**)
- **Licensing & repo-health docs (§6).** Add `LICENSE` (MIT, Copyright (c) 2026 Brad Sprigg),
  `NOTICE` (Scryfall/WotC attribution + Fan Content Policy), `SECURITY.md`, `CONTRIBUTING.md`,
  `CHANGELOG.md` (start 0.1.0, record the central-DB migration note), and the README attribution/
  disclaimer block. (README body was already rewritten in commit d1dc5a2.)
- **CI workflow (§6).** `.github/workflows/ci.yml`: `uv sync` → `ruff check` → `ruff format
  --check` → `mypy src/` → `pytest -m "not integration"`, matrix on 3.12/3.13; plus issue/PR
  templates.
- **MCPB bundle for Claude Desktop (§4).** Add `manifest.json` (manifest_version 0.4, `uv`
  runtime, `PLANESWALKER_DATA_DIR` user_config — **depends on the §3 env var**); `npx
  @anthropic-ai/mcpb pack`; smoke-test install. Attach the `.mcpb` to the GitHub Release.
- **Release mechanics (§7.1, §8 — MANUAL).** Run the full-history secret scan
  (`uvx gitleaks detect --source . --log-opts="--all"`), tag `v0.1.0`, cut the GitHub Release with
  the `.mcpb` attached, flip the repo public. Brad executes these.

## Deferred from: code review of licensing-repo-health-docs (2026-06-28)

> Surfaced by the 3-reviewer adversarial pass on the §6 licensing/repo-health docs run
> (`spec-licensing-repo-health-docs.md`). The doc-accuracy issues in the *new* files
> (CONTRIBUTING/CHANGELOG over-claiming that `setup.py` builds the search index; the "all MCP
> tools are sync `def`" overstatement) were patched in-branch. The items below are real but
> pre-existing or outside this run's frozen scope (no README/code edits).

- **README claims `setup.py` builds the search index (it doesn't).** [`README.md:38`](../../README.md#L38)
  (`# installs deps, builds the card DB + index`) and [`README.md:44`](../../README.md#L44)
  ("builds the local search index") both assert the one-time `setup.py` run produces the semantic
  index. Verified false: `setup.py` only runs `initialize_database()` (Scryfall card import) — no
  `build_card_embeddings` / `card_vec` reference anywhere in it. The index must be built separately
  via `uv run python scripts/build_card_embeddings.py`. So a user who follows the README Quick start
  and immediately calls `semantic_search_cards` gets `status="index_unavailable"`. Out of scope here
  (the spec froze "no README edits"); fix in a focused README-accuracy pass — either correct the two
  lines, or have `setup.py` actually build the index after import.
- **`setup.py` post-`.env` message hard-codes the old `./data/cards.db` path.**
  [`setup.py:87`](../../setup.py#L87) prints `Defaults work out of the box (SQLite at ./data/cards.db…)`,
  stale since the central-OS-data-dir change (the engine now resolves via `paths.database_url()` to the
  OS data dir). Cosmetic only — the DB still lands in the central dir — but the printed path misleads.
  Update the string to reference the central dir (or drop the concrete path).
- **`project-context.md` MCP-tool rule ("Define tools as sync `def`") drifted from the shipped code.**
  The Framework rules state MCP tools are sync `def` threadpooled by FastMCP, but the Epic-1 tools
  (`lookup_card_by_name`, `report_bug`, `search_cards`, deck CRUD/analysis) are `async def`; only the
  two Epic-2 semantic tools (`semantic_search_cards`, `find_similar_cards`) are sync `def`. The doc
  describes the Phase-1 *design target*, not the implementation — and it's what led the docs run to
  over-generalize. Reconcile the project-context MCP-tool rule with the actual async/sync split.

## Deferred from: code review of spec-central-os-data-dir (2026-06-27)

> Surfaced by the 3-reviewer adversarial pass on the `feat/central-data-dir` work. The HIGH/MED
> findings (broken `migrate_add_bug_reports.py` import, empty-env sync/async divergence, relative
> `PLANESWALKER_DATA_DIR` not absolute) were patched in-branch; the items below are real but
> pre-existing or exotic, left for a focused later pass.

- **Bare-path `CARDS_DATABASE_URL` (no SQLAlchemy prefix) crashes the async engine** —
  `src/paths.py::database_url` returns the env value verbatim, so `CARDS_DATABASE_URL=/data/cards.db`
  (without `sqlite+aiosqlite:///`) makes `create_async_engine` raise `ArgumentError`, while the sync
  `ConnectionFactory` happily uses the bare path — a half-works/half-crashes split. Pre-existing (the
  old `os.getenv("CARDS_DATABASE_URL", default)` had the same risk) and it fails loudly. Fix later by
  validating/normalising the URL form, or document that the `sqlite+aiosqlite:///` prefix is mandatory.
  - **HOMED (not fixed) by story c1-6, 2026-07-25** — per the epic-7 gate-output-homing rule. On the
    companion's REST side the crash now has a **defined behaviour instead of an undefined one**: the
    bare path reaches `sqlalchemy.engine.make_url` inside
    `src/companion/app/deps.py::database_file`, which raises `ArgumentError`; AD-16 rules that
    deterministic, so it falls through to `UnhandledErrorMiddleware` and answers
    `500 internal_error` rather than taking the process down. Pinned by
    `test_deps.py::TestTransientFailureIsDatabaseUnavailable::
    test_a_deterministic_argument_error_is_internal_error_not_unavailable`. Note the raise site moved
    one step earlier than this item's original wording predicted (`make_url`, not
    `create_async_engine`) because the companion parses the URL to derive the file path before
    building an engine. The **underlying** half-works/half-crashes split between the async engine and
    the sync `ConnectionFactory` is untouched and still owned here; a fix belongs in `src/paths.py`,
    which story c1-6 is forbidden from editing.
- **UNC `PLANESWALKER_DATA_DIR` yields a malformed async URL** — for `\\server\share\pw`,
  `database_path().as_posix()` collapses the leading `\\` to a single `/`, so the async URL drops the
  UNC authority while the sync factory keeps the native UNC path → divergence. Exotic (SQLite over a
  network share is discouraged anyway); document "use a local absolute data dir" or reject UNC paths.
- **✅ RESOLVED by the prune (2026-06-28) — Repo-wide `ruff check .` / `ruff format --check .` now clean.**
  The pre-existing drift was in `_bmad/scripts/*` and `src/mcp_server/tools/card_lookup.py`. The prune
  untracked + gitignored `_bmad/` (ruff now skips it) and the pre-commit formatter normalized one
  f-string in `card_lookup.py`. Verified: `ruff format --check .` (120 files) + `ruff check .` both pass.

## Deferred from: code review of trim-deps-package-metadata (2026-06-28)

> Surfaced by the 3-reviewer adversarial pass on the `chore/trim-deps-package-metadata` work
> (§6 deps/metadata cleanup). No HIGH/MED findings against the change itself — every blind-hunter
> "risk-to-confirm" item (entry-point `main` exists, removed deps unreferenced anywhere, mypy hook
> still clean without `logfire`) was verified false. The one real item below is pre-existing.

- **`setup.py` creates a `.env` that nothing actually loads (orphaned onboarding artifact)** —
  `setup.py::setup_environment` writes `.env` from `.env.example`, but no code path loads it: there
  is no `load_dotenv` call and no `pydantic-settings` `BaseSettings(env_file=...)` anywhere — all
  config is read via bare `os.getenv(...)` (`src/paths.py`, `src/search/connection.py`,
  `src/search/embedder.py`, `src/mcp_server/__main__.py`), and `uv run` does not auto-load `.env`.
  So edits to the generated `.env` silently have no effect unless the user exports the vars or the
  MCP client injects them. Pre-existing (predates this chore; confirmed while verifying the
  `python-dotenv` removal). Fix later by either wiring up `.env` loading (a `BaseSettings` config
  object, or `uv run --env-file`) or trimming `setup_environment` + `.env.example` to match the
  "env vars are optional, defaults work out of the box" reality. (Source: Edge Case Hunter; Severity: Low.)

## ✅ Resolved by the Pre-Epic-3 Targeted Gate (2026-06-27)

> Cleared via `spec-pre-epic-3-targeted-gate.md` before starting Epic 3. The items below are closed;
> they remain listed in their original sections for traceability.

- **G1 — `_FakeEmbedder`/`_FakeVecEmbedder` duplication (was 5 copies).** Consolidated into one
  `tests/fixtures/embedder.py::FakeEmbedder` (union of `encode`/`encode_batch`/`total_embedded`);
  all call sites import it. (Closes the 2-4 and 2-5 "`_FakeEmbedder` in N test files" items.)
- **G2 — `limit` upper bound / `limit > over_fetch_k` starvation.** `semantic_search_cards` and
  `find_similar_cards` now reject `limit > 50` (`_MAX_LIMIT`, kept under `over_fetch_k=200`).
  (Closes the 2-4 "`limit > over_fetch_k` silently truncates" and 2-5 "silently starves" /
  "`limit` has no upper bound" items.)
- **G3 — graceful "index not built".** New `src/search/query.py::index_is_populated` gates both
  semantic tools, returning `status="index_unavailable"` (with a build-the-index hint, `isError=False`)
  for a missing **or** empty `card_vec`, instead of a raw `OperationalError`. (Closes the
  "index not built" half of the 2-4 "Unhandled exceptions propagating from sync tool" item; the
  ONNX/`RuntimeError`/`JSONDecodeError` halves remain deferred — infra concerns.)
- **Nullability audit (1-4 / 1-6).** Confirmed the `Card`/`CardSummary` `@field_validator(mode="before")`
  coercions (`None → ""`/`[]`/`{}`) already protect `mana_cost`/`oracle_text`/`colors`/`games`/`legalities`;
  added a `validate_deck` NULL-legalities/NULL-games regression test. Closes the 1-4
  "CardSummary.mana_cost/oracle_text non-nullable" + "colors no None-coercion" items and the 1-6
  "`card.legalities` potentially None" + "`card.games` potentially None" items.

## Epic-3 design candidates (from TOOL_PERFORMANCE_REPORT.md, 2026-06-27)

> Surfaced by Brad's live test of the semantic tools (R1). Not bugs — enhancement candidates to weigh
> during Epic 3.

- **Compound-intent dilution — handle in the orchestrator, not the tools.** "A **and** B" queries
  (e.g. "removal that also reanimates") rank by topical proximity, so cards matching *either* effect
  blend in and can outrank true "both" cards (`Betrayal of Flesh` ranked 14th). Treat the semantic
  tools as **high-recall candidate generators**: over-fetch, then have the Story 3.1 orchestrator /
  LLM filter for the logical intersection and present ranked candidates **with reasons** (confirms
  retro design-input I1). An optional in-tool re-rank rewarding multi-clause matches is a possible
  later refinement.
- **`find_similar_cards` cross-color leakage.** With no `colors` filter, off-color cards surface
  (`src/mcp_server/tools/find_similar.py`). Consider defaulting `colors` to the seed card's colour
  identity (overridable) to cut leakage. Tool already supports the filter; only the default is open.

## Deferred from: code review of 2-6-rag-sanity-eval (2026-06-24)

- **`evaluate_hit_rate([])` produces confusing "0 miss(es)" failure message** — `tests/integration/search/test_rag_eval.py`. If `_QUERY_FIXTURE` is ever emptied (module-level constant; only via code edit), `evaluate_hit_rate([])` returns `(0.0, [])`, which trips the `>= TARGET_HIT_RATE` assert but `format_failure` prints "0 miss(es)" with no per-miss lines — self-contradictory. Add `assert case_results, "Query fixture is empty"` before the hit-rate assert as a defensive guard in a future maintenance pass.
- **`reset_embedder()` teardown ordering hazard across modules** — `tests/integration/search/test_rag_eval.py`. Module-scoped `rag_eval_index` fixture calls `reset_embedder()` in teardown. If another module's session-scoped fixture loaded the embedder, this reset destroys the shared singleton mid-session. Pre-existing pattern in `test_embedder.py` and `test_semantic_search_tool.py`; a session-scoped coordinator would fix it project-wide.
- **Yield-fixture setup failure leaves `ConnectionFactory` unclosed** — `tests/integration/search/test_rag_eval.py:rag_eval_index`. If `get_embedder()` raises during fixture setup (model download failure, ONNX error), pytest does not run the teardown, so `factory.close()` is never called. Tmp files are cleaned by `tmp_path_factory` at session end; no functional impact. Fix with `try/finally` around setup if file-lock issues surface on Windows.

## Deferred from: code review of 2-5-find-similar-cards-tool (2026-06-22)

- **LIKE wildcard injection in `card_name`** — `src/mcp_server/tools/find_similar.py`. Characters `%` and `_` in seed card names are not escaped before the `LIKE lower(?)` partial-match fallback, silently broadening or changing the match set. Acknowledged in code comment as "accepted LIKE-wildcard risk, mirroring CardRepository (deferred-work)". Pre-existing in `card_lookup.py` and `card.py` (1-3 review).
- **`limit > over_fetch_k` silently starves results (find_similar path)** — `src/search/query.py:hybrid_search`. `find_similar_cards` never passes `over_fetch_k`, so callers requesting `limit > 200` receive fewer alternatives than requested with no warning. Also, seed cards with many printings (e.g. Lightning Bolt ~50 printings) consume KNN slots before exclusion, further reducing the effective result count. Related: noted in 2-4 review.
- **`np.frombuffer` returns read-only array in `get_card_vector`** — `src/search/query.py`. The returned `NDArray` is backed by the SQLite buffer object and is read-only; any future caller that attempts in-place mutation will get a `ValueError`. Current code path (via `hybrid_search → serialize_float32`) only reads the array. Guard with `.copy()` if mutating callers are ever added.
- **Empty/corrupted BLOB in `get_card_vector` raises ValueError** — `src/search/query.py`. If the `card_vec` BLOB is zero-length or not a multiple of 4 bytes (data corruption), `np.frombuffer` raises `ValueError` uncaught. Controlled data written by `serialize_float32` always produces 1536 bytes; treat as infrastructure concern.
- **`_FakeEmbedder` now in four test files** — Previously tracked (2-4 review). `test_find_similar_tool.py` adds a fourth copy. Consolidate to `tests/conftest.py` or `tests/fixtures/embedder.py` in a future housekeeping pass.
- **`color_mode` not runtime-validated in `find_similar_cards` helper** — `src/mcp_server/tools/find_similar.py:_validation_error`. Invalid strings reach `hybrid_search._color_predicates` unchecked. FastMCP's `Literal["any", "all", "exact", "at_most"]` annotation rejects invalid values at the wire level; direct helper calls bypass this. Mirrors Story 2.4 pattern.
- **`limit` has no upper bound in `_validation_error`** — `src/mcp_server/tools/find_similar.py`. Only `limit < 1` is rejected. `over_fetch_k=200` provides a natural cap on results. Also noted in 2-4 review.
- **`_resolve_seed` LIKE fallback fetches all matching rows without SQL LIMIT** — `src/mcp_server/tools/find_similar.py`. On 60k cards, a common substring like `"a"` loads thousands of rows into Python memory before `_MAX_MATCHES` capping. Mirrors `CardRepository.find_by_name_partial`'s unbounded fetch. Add `LIMIT _MAX_MATCHES * 20` to the SQL in a future performance pass.
- **`_decode_colors` does not guard against non-list JSON or `JSONDecodeError`** — `src/mcp_server/tools/find_similar.py:_decode_colors`. If `cards.colors` contains valid JSON but not a JSON array (e.g. a string scalar `"R"`), `json.loads` returns a non-list that bypasses the `value is not None` check and reaches `CardSummary(colors=...)` as the wrong type; malformed JSON raises `JSONDecodeError` uncaught. Same pattern as `_coerce_json_list` in `query.py`; Scryfall always writes a valid JSON array — infrastructure concern.
- **Disambiguation "showing first N" message branch is unreachable for 6–10 distinct matches** — `src/mcp_server/tools/find_similar.py:253`. `shown = distinct[:_MAX_MATCHES]` equals `distinct` when `len(distinct) ≤ 10`, so the inner `if len(shown) < len(distinct)` branch (which emits "showing the first N") is dead code for that range. For 6–10 matches, the message says "Please refine" without the count sub-clause, even though all matches are returned in `matches`. Cosmetic phrasing gap; `matches` list is correct.

## Deferred from: code review of 2-4-semantic-search-cards-tool-hybrid-query (2026-06-22)

- **Unhandled exceptions propagating from sync tool** — `src/mcp_server/server.py:440`. `OperationalError` (DB unavailable / index not built), `RuntimeError` (ONNX failure), and `json.JSONDecodeError` (malformed DB column) all propagate uncaught through the sync tool, resulting in `isError=True` FastMCP responses. Matches the existing Epic-1 async tool pattern; a `status="error"` enum extension would be needed to handle these gracefully. Defer until infra errors surface in practice.
- **`_FakeEmbedder` duplicated in three test files** — `tests/unit/search/test_query.py`, `tests/integration/mcp_server/test_semantic_search_tool.py`, and `tests/integration/conftest.py` each define an identical `_FakeEmbedder` / `_FakeVecEmbedder` class. Move to a shared `tests/integration/conftest.py` or a dedicated `tests/fixtures/embedder.py` helper to avoid triple-maintenance on `Embedder` interface changes.
- **`limit > over_fetch_k` silently truncates results** — `src/search/query.py:hybrid_search`. Callers passing `limit > 200` (default `over_fetch_k`) receive fewer results than requested with no indication. Spec says "sane max ~50"; add an upper-bound validation in `_validation_error` (e.g. `limit > 50 → status="invalid"`) in a future polish pass.

## Deferred from: code review of 1-1-repository-restructure-dependency-reshape (2026-06-20)

- **`legacy/tests/conftest.py` module-level chainlit import** — `import chainlit` at the top of `legacy/tests/conftest.py` (line 8) causes `ModuleNotFoundError` if someone runs `pytest legacy/tests/` on a lean env (without `--group legacy`). `testpaths = ["tests"]` protects the default run. Fix: add a note to `legacy/` documentation or add a root-level `conftest.py` `collect_ignore_glob` guard to make the failure message clearer.

- **`mock_user_session` fixture state leak** — `legacy/tests/conftest.py` patches `cl.user_session.get/.set` at fixture setup time with no teardown/restore. If a test using this fixture fails mid-run, subsequent tests in the same session inherit the patched session. Fix: rewrite using pytest's `monkeypatch` fixture or a `yield`-based restore. Applies to the legacy test tree only (excluded from active CI).

- **Legacy tests' `tests.fixtures.card_data` import** — Files like `legacy/tests/integration/agent/test_agent_card_search.py` import `from tests.fixtures.card_data`. This works when pytest sets the project root on `sys.path` (standard `uv run pytest` from root) but may fail in IDEs or when running `pytest legacy/tests/` in isolation. Fix: either copy shared fixtures into `legacy/tests/fixtures/` or add a `conftest.py` `sys.path` adjustment to `legacy/tests/`.

- **`PaginatedResult[T]` missing field validators** — `src/data/schemas/pagination.py` has no validators to enforce `page >= 1`, `page_size >= 1`, or `total_pages` consistency with `total_count`. A caller constructing `PaginatedResult(page=0, ...)` silently passes validation; a caller reading `page=1, total_pages=0` has an impossible state. Fix: add `Field(ge=1)` to `page`, `page_size`, `total_pages` and optionally a `model_validator` for `total_pages` consistency.

- **Task 0 out-of-scope changes** — Story 1.1 also shipped three pre-existing-defect fixes (explicitly approved by user): recreated `src/data/schemas/pagination.py`, fixed `CardModel.printed_name` default, and updated test contract assertions for `PaginatedResult`. These were correctness-restoring fixes needed to unblock AC4 (100 tests were failing at baseline). No follow-up action required; noted here for traceability.

## Deferred from: code review of 1-2-sqlite-connectionfactory-with-wal-extension-loading (2026-06-20)

- **Empty string `CARDS_DATABASE_URL` not guarded** — `_resolve_db_path` returns `""` if the env var is set to an empty string, which `sqlite3.connect("")` will fail on (OperationalError). This is an operator misconfiguration that fails loudly; not worth defensive handling given project rules against unnecessary validation. If it becomes a user-facing pain point, add a guard in `_resolve_db_path` to fall back to the default when the stripped URL is empty.

## Deferred from: code review of 1-3-fastmcp-server-with-card-lookup-bug-report (2026-06-20)

- **`updated_at` onupdate lambda silent in ORM** — `src/data/models/bug_report.py:43-47`. SQLAlchemy `mapped_column(onupdate=callable)` does not fire via the ORM unit-of-work; `updated_at` will always equal `created_at`. Matches the pre-existing `DeckModel` pattern. Only matters when a future story adds an update operation.
- **No CHECK constraint on status column** — `src/data/models/bug_report.py:32-34`. Any raw string can be written to `status` bypassing enum validation; reading it back via `BugReport.model_validate` would raise `ValueError`. Currently only triggered by manual DB manipulation. Address when an update story is implemented.
- **CardLookupResult.matches=[] on found status** — `src/mcp_server/tools/card_lookup.py`. An empty list rather than `None` for `matches` when `status="found"` is ambiguous for callers. Design preference; no functional bug.
- **LIKE wildcard injection in card_name/games** — `src/data/repositories/card.py`. Characters `%` and `_` in the card name or games list are passed un-escaped to SQLite LIKE. Pre-existing issue in `CardRepository`; out of scope for Story 1.3.
- **Non-DatabaseError exceptions skip explicit rollback in BugReportRepository** — `src/data/repositories/bug_report.py:50-69`. Exceptions that aren't `IntegrityError` or `DatabaseError` propagate without explicit `rollback()`. The session context manager handles cleanup on exit; low practical risk in current call paths.
- **migrate_add_bug_reports.py CWD-sensitive** — `scripts/migrate_add_bug_reports.py:20`. Default `DATABASE_URL` uses `./data/cards.db`; if the script is run from a non-root directory it silently targets the wrong file. Convention (run via `uv run` from project root) guards this; a doc comment would help.
- **Transport cast is runtime no-op** — `src/mcp_server/__main__.py:20`. `cast(_Transport, os.getenv(...))` provides no runtime validation. FastMCP raises on an invalid transport string anyway, but an explicit guard would give a clearer error message.

## Deferred from: code review of 1-4-advanced-card-search-tool (2026-06-20)

- **`CardSummary.mana_cost`/`oracle_text` non-nullable** — `src/data/schemas/card.py:84,87`. Both fields are `str` (not `str | None`), matching the pre-existing `Card` schema pattern. Scryfall has null mana_cost for tokens/land faces and null oracle_text for split cards. If the DB stores these as NULL, `CardSummary.model_validate(card)` will raise `ValidationError`. Needs to be addressed as part of a broader Card/CardSummary schema nullability audit; this story explicitly prohibits modifying `Card`.
- **`CardSummary.colors: list[str]` no None-coercion** — `src/data/schemas/card.py:88`. `Card.games` has `@field_validator` coercing `None → []`; `colors` has no equivalent in either `Card` or `CardSummary`. If a `CardModel.colors` is NULL in SQLite, `model_validate` raises `ValidationError`. Pre-existing in `Card`; should be addressed alongside the mana_cost/oracle_text audit.
- **`page_size > 50` silently capped with no caller notification** — `src/data/repositories/card.py`. The repository clamps `page_size = min(page_size, 50)` and reflects the effective value in `CardSearchResult.page_size`. The tool-level `_validation_error` only rejects `page_size < 1`. Consider adding an upper-bound check (return `status="invalid"` for `page_size > 50`) in a future polish pass.
- **`games` validation case-sensitive vs `rarity` case-insensitive inconsistency** — `src/mcp_server/tools/card_search.py:83-86`. `rarity` values are normalised with `.lower()` before checking; `games` are compared directly. Callers passing `"Paper"` or `"MTGO"` get `status="invalid"` with a clear message naming the expected casing. Inconsistent but not harmful; could be unified in a future polish story.
- **`page` beyond `total_pages` gives generic empty message** — `src/mcp_server/tools/card_search.py:178-189`. Requesting `page=999` on a 1-page result set returns `status="empty"` with the standard "try adjusting filters" hint, giving no indication the page number exceeded the range. A future polish pass could detect `page > result.total_pages` after the repo call and return a more specific message.
- **`colors=[]` applies no filter for non-"exact" modes** — `src/data/repositories/card.py`. `search_advanced` treats `colors=[]` (empty list) the same as `colors=None` for `any`/`all`/`at_most` modes because `if colors:` is falsy. A caller expecting "empty list = colorless only" gets "no filter" instead. Pre-existing behavior in `search_advanced`; out of scope for this story.

## Deferred from: code review of 1-5-deck-management-tools (2026-06-20)

- **`DeckSummary.from_attributes=True` footgun** — `src/data/schemas/deck.py`. `DeckSummary.model_validate(deck)` silently gives zero counts because `Deck` has no `mainboard_count` attribute. Docstring warns; helpers always use explicit constructors. Could remove `from_attributes=True` from `DeckSummary`/`DeckDetail` (only `DeckCardSummary` actually needs it) to prevent future misuse.
- **`CardSummary.model_validate(dc.card)` on a Pydantic model** — `deck_management.py:_deck_detail`. Works in Pydantic v2 via attribute inspection on `Card` instances. A more explicit pattern (`CardSummary(**dc.card.model_dump())`) is safer but out of Story 1.5 scope.
- **Non-deterministic card ordering in `_deck_detail`** — `deck_management.py`. Order of `load_deck` card list depends on `DeckRepository.get_deck_with_cards` sort; if non-deterministic, card order in responses is unstable. Address when consistent ordering is required.
- **`not_in_deck` message does not hint card exists in other location** — `deck_management.py:remove_card_from_deck`. Removing from mainboard when card is in sideboard returns "not in the mainboard" with no hint the card is present elsewhere. UX improvement for a future polish story.
- **`_deck_detail` crash risk if `dc.card` is `None`** — `deck_management.py`. FK enforcement is OFF; if a card row is deleted after a `deck_cards` row was inserted, `get_deck_with_cards` may return a `DeckCard` with a null `card`. `CardSummary.model_validate(None)` would raise. Defended by add-path pre-validation (AC4) but not structurally guaranteed.
- **No `format` validation in `create_deck`** — `deck_management.py`. Invalid format strings (e.g., `"potato"`) are stored silently; deferred to Story 1.6 `validate_deck` by D-1.5b.

## Deferred from: dev of 1-2-sqlite-connectionfactory-with-wal-extension-loading (2026-06-20)

- **`test_list_decks` flaky ordering (pre-existing)** — `tests/integration/data/test_deck_repository.py::test_list_decks` asserts three rapidly-created decks come back newest-first, but `DeckRepository.list_decks` orders by `created_at.desc()` with **no secondary tie-breaker** ([`src/data/repositories/deck.py:260`](../../src/data/repositories/deck.py#L260)). When the three `create_deck` calls land on identical `created_at` timestamps (common under full-suite timing), SQLite resolves the tie arbitrarily and the assertion fails non-deterministically. Verified: the test passes 5/5 in isolation but fails intermittently in the full run. Unrelated to Story 1.2 (which only adds `src/search`); left untouched per scope discipline. Fix: add a deterministic secondary sort key to `list_decks` (e.g. `.order_by(DeckModel.created_at.desc(), DeckModel.id)`) **and** make the test's creation-order intent explicit (e.g. distinct/controlled `created_at` values), since UUID `id` is not time-ordered.

## Deferred from: code review of 2-1-embedder-port-fastembed-singleton-persistent-cache (2026-06-21)

- **Double-checked locking portability for non-CPython/free-threaded Python** — `src/search/embedder.py:1038`. The outer `if _embedder is None` read has no lock and relies on CPython's GIL for visibility. Correct on CPython 3.12 (project target), but not portable to free-threaded builds (PEP 703, opt-in in Python 3.13+) or other implementations. Revisit if/when free-threaded Python is targeted.
- **encode_batch large-batch memory ceiling** — `src/search/embedder.py:encode_batch`. No `batch_size` passthrough; a ~60k-item call materializes all output vectors in memory (~88 MB for float32 alone) plus fastembed's internal buffers. Spec explicitly deferred `batch_size` to Story 2.3's index builder.
- **reset_embedder() dual ONNX sessions under concurrent use** — `src/search/embedder.py:reset_embedder`. If called while a thread holds a reference from `get_embedder()` and is mid-encode, the next `get_embedder()` loads a second ONNX session, doubling RAM transiently. Test-only function; production FastMCP never calls it; GC reclaims the old Embedder when callers release their reference. Docstring should note the hazard.
- **test_resolve_cache_dir_never_temp assertion style** — `tests/unit/search/test_embedder.py:1197`. `startswith("./data")` check is correct for the current relative default. If the P1 absolute-path patch is ever applied, this test will need updating to match the resolved absolute path.
- **README.md and setup.py changes bundled in story commit** — Not in the spec File List; spec's Git Intelligence note acknowledges these as pre-existing MCP-pivot cleanup. Noted for traceability.

## Deferred from: code review of 2-2-card-vec-schema-with-metadata-columns (2026-06-21)

- **Tests call `factory.close()` without try/finally** — `tests/unit/search/test_schema.py`. Every test leaves `factory.close()` outside a `try/finally`, so connections are not released on assertion failure. On Windows, leaked WAL connections can cause file-lock errors. Pre-existing pattern mirrored from `test_connection.py`; fix the pattern project-wide when refactoring the test helpers.
- **Migration CWD-relative DB path** — `scripts/migrate_add_card_vec.py`. Default `./data/cards.db` is CWD-relative; running from a non-root directory silently targets the wrong file. Pre-existing `ConnectionFactory` behavior; convention is `uv run` from project root. Same issue exists in `migrate_add_bug_reports.py`.
- **`mana_value integer` column accepts Python float inputs without coercion** — `src/search/schema.py`. SQLite's dynamic typing allows storing a Python `float` in an `integer`-affinity column without error, so `WHERE mana_value = 2` could silently miss cards stored as `2.0`. The `int(cmc)` cast is Story 2.3's responsibility at insert time.

## Deferred from: code review of 1-6-deck-analysis-tools (2026-06-20)

- **`dc.quantity` zero or negative can undercount mainboard cards** — `validate_deck` in `src/logic/deck_validator.py` accumulates `dc.quantity` without clamping. A zero or negative quantity (bypassing the DeckCard schema validator) would undercount the mainboard, potentially letting an illegal deck pass the 60-card check. Fix at insert time in `DeckRepository.add_card_to_deck` with `quantity >= 1` enforcement.
- **`card.legalities` potentially `None` from DB NULL** — `card.legalities.get(format)` in `validate_deck` (`src/logic/deck_validator.py`) raises `AttributeError` if `legalities` is `None`. The `Card` schema types this as `dict[str, str]` (non-nullable), but SQLite does not enforce NOT NULL for JSON columns without a CHECK constraint. Address in a broader Card schema nullability audit (related: deferred in 1-4 review).
- **`card.games` potentially `None` from DB NULL** — `set(card.games)` in `validate_deck` raises `TypeError` if `card.games` is `None`. Same root cause as `legalities`; `Card.games` has a `@field_validator` coercing `None → []` for ORM-loaded instances but not for in-memory `Card` objects constructed directly. Confirm the validator fires for all construction paths.
- **Unexpected exceptions from logic functions propagate unhandled** — `_logic_analyze_mana_curve`, `_logic_detect_synergies`, and `_logic_validate_deck` in `src/mcp_server/tools/deck_analysis.py` are called with only `DatabaseError` caught around the repo load. If any logic function raises an unexpected exception (e.g., a malformed `cmc` field in `analyze_mana_curve`), it propagates to the MCP caller as an unstructured error. Accepted risk for Phase-1; revisit if unexpected failures surface in practice.
- **Quantity expansion OOM for adversarial large `dc.quantity`** — `analyze_mana_curve` in `deck_analysis.py` expands `dc.card` by `range(dc.quantity)` into `all_cards`. A corrupted/adversarial record with `quantity=1_000_000` would allocate a million-element list. Cap at the repository level (or add a defensive `min(dc.quantity, 250)` expansion cap) when productionising.
- **`format` normalization absent from pure `validate_deck` logic** — The tool helper normalises `format.strip() or "standard"`, but the pure function in `src/logic/deck_validator.py` accepts any string, including `""`. Direct callers (e.g., future logic-layer callers) passing an empty format will get all cards flagged as format-illegally. Consider adding the normalization to the pure function as a defensive guard.
- **`seeded_card_db` omits `games` field on seed cards** — The three shared fixture cards (Lightning Bolt, Thunderbolt, Counterspell) default to `games=[]`. The `games` filter path in `validate_deck` is therefore not exercised end-to-end through the MCP harness (`test_mcp_tools.py`). Covered at the helper level in `test_deck_analysis_tool.py`. Acceptable Phase-1 gap; extend the harness test when the fixture is enriched for Epic-2 work.

## Deferred from: code review of story-3.4 (2026-06-27)

- **`validate_deck` skips `dc.card is None` rows from copy/legality checks while still counting them in `mainboard_count`** — `src/logic/deck_validator.py` does `if dc.card is None: continue` before tallying copies/legality, but `mainboard_count` sums quantity unconditionally. A saved deck with an orphaned card join (a `card_id` no longer in the DB) passes copy/legality vacuously while still counting toward the 60-card size — a "legal" result can hide un-validated phantom cards. Pre-existing tool/data edge; obscure. Could add a one-line caveat to the format-legality skill's "what the tool can't see" section. (Source: Edge Case Hunter; Severity: Low.)

## Deferred from: code review of mcpb-bundle (2026-06-28)

> Surfaced by the 3-reviewer adversarial pass on the `chore/mcpb-bundle` work (§4 MCPB bundle).
> The one HIGH that mattered (`.mcpbignore`'s unanchored `data/` also excluding `src/data/`, which
> would have shipped a server unable to import its own data layer) was caught by re-verification and
> patched in-branch by anchoring the rule to `/data/`. Most blind-hunter findings were verified false
> (`server.type: "uv"` IS valid in the MCPB v0.4 schema; blank `data_dir` is handled by
> `paths.py`'s `(getenv() or "").strip()` fallback; `uv run` honours `requires-python`). The two
> real items below are pre-existing or out-of-this-run's-scope-by-design.

- **MCPB bundle has no first-run data bootstrap or guidance.** A freshly-installed `.mcpb` launches
  the server, but the shared OS data dir has no `cards.db` yet — the ~250 MB data set is excluded from
  the bundle **by design** (§3/§4; spec "Never: no DB shipped"). The server never calls
  `init_database`, so the first relational tool call fails (`no such table: cards`); the two semantic
  tools degrade gracefully to `status="index_unavailable"`. Net end-user experience: "every deck/card
  tool errors with no guidance." Out of scope here (the bundle correctly ships data-excluded), but a
  real UX gap. Follow-up: either add a first-run auto-init / friendly "run the one-time data build"
  response, or document the manual bootstrap (`uv run python setup.py`, then
  `scripts/build_card_embeddings.py` — both write to the shared OS data dir the bundle reads) in the
  install docs. (Source: Edge Case Hunter; Severity: High-for-UX.)
- **`README.md:68` overclaims the Claude-Desktop first-run behavior.** The "Claude Desktop
  (one-click)" section says *"(First launch prompts you to run the one-time data build.)"* — but the
  shipped `manifest.json` has no prompt/hook to do that (coupled to the bootstrap-gap item above).
  Out of this run's frozen scope (no README edits). Fix in the focused README-accuracy pass already
  tracked (the `setup.py`-builds-the-index claim) — either implement the prompt or reword to a manual
  build step. (Source: Edge Case Hunter; Severity: Med.)
- **MCPB GUI data-dir override removed (smoke-test fix 2026-06-28).** The optional
  `user_config.data_dir` field was dropped from `manifest.json` because Claude Desktop passes the
  **unsubstituted `${user_config.data_dir}` placeholder** when the optional field is left blank,
  repointing the server at a bogus relative dir → empty DB → `no such table: decks`. The bundle now
  always uses the shared central OS dir (zero-config). If the GUI override is ever re-added, also
  harden `src/paths.py::data_dir` to ignore an override that still contains an unsubstituted `${...}`
  placeholder (defense-in-depth), with a unit test — otherwise the bug returns. (Source: Brad live
  smoke-test; Severity: was High, now fixed.)

## Deferred from: code review of story-4.2 (2026-07-12)

> 3-reviewer adversarial pass on the `scripts/migrate_add_game_changer.py` diff (Story 4.2). The
> Blind Hunter's headline finding — the documented backfill re-import can't actually populate
> `game_changer` because `src/data/importers/importer.py` never lists the column — is a
> decision-needed item logged in the story file's Review Findings, not deferred here (it blocks
> the story's own AC5/AC6, so it isn't "not actionable now"). The items below are real but
> pre-existing/inherited-template gaps out of this story's scope.

- **Pre-`try` engine/session-factory failures + rollback()/dispose() masking secondary exceptions** — `scripts/migrate_add_game_changer.py:42-46,67-72`. `create_engine()`/`create_session_factory()` calls sit outside the `try` block, and neither `session.rollback()` in `except` nor `engine.dispose()` in `finally` is itself guarded — a secondary exception there would mask the original error or an unhandled traceback if session-factory setup fails. Verbatim structure copied from `scripts/migrate_add_power_toughness.py` per this story's own template mandate; not introduced by this diff. (Source: Edge Case Hunter; Severity: Low.)
- **TOCTOU race between the idempotency check and the `ALTER TABLE`** — `scripts/migrate_add_game_changer.py:50-57`. Two concurrent runs can both pass the `PRAGMA table_info` check before either commits, so the loser hits a raw "duplicate column name" `OperationalError` dressed up as a generic migration failure instead of a benign no-op. Identical race exists in the precedent script. (Source: Edge Case Hunter; Severity: Low.)
- **`PRAGMA table_info(cards)` on a missing `cards` table silently returns empty rather than erroring** — `scripts/migrate_add_game_changer.py:47-55`. A pre-bootstrap DB (never run through `initialize_database`) makes the script proceed straight to `ALTER TABLE` on a nonexistent table, surfacing a raw "no such table: cards" error with no bootstrap hint. Same gap in `migrate_add_power_toughness.py`; same class as the previously-resolved G3 `index_unavailable` bootstrap gap, but this migration template was never given the equivalent fix. (Source: Blind Hunter + Edge Case Hunter; Severity: Low.)
- **Upsert-based backfill only touches rows present in the current Scryfall bulk export** — `src/data/importers/importer.py`. A card absent from a freshly-downloaded bulk file keeps its prior (NULL) `game_changer` value indefinitely; the migration docstring's "overwrites every card" framing overstates actual coverage. Inherent to the importer's existing upsert design, not introduced by this diff. (Source: Blind Hunter; Severity: Low.)
- **Idempotency guard checks column presence only, not type/nullability** — `scripts/migrate_add_game_changer.py:50-53`. A differently-typed partial/failed prior migration attempt would be silently treated as already-satisfied. Identical guard shape in the precedent script. (Source: Blind Hunter; Severity: Low.)

## Deferred from: code review of story-4.1 (2026-07-11)

- **Untyped `game_changer` value could reach the `Boolean` column unchecked** — `src/data/importers/transformers.py:79`. `card_json.get("game_changer")` performs no type/shape validation; a non-bool value (string/int) would flow straight into a `Boolean` SQLAlchemy column with no coercion or error. Pre-existing pattern: no field in `transform_scryfall_card` has type validation beyond null-coalescing, and Scryfall is a trusted, documented source for this field. (Source: Edge Case Hunter + Blind Hunter; Severity: Low.)
- **No cross-printing `game_changer` reconciliation in oracle aggregation** — `src/data/importers/aggregate.py`. Unlike `games` (unioned across all printings of an oracle identity), `game_changer` is taken from whichever printing happens to be canonical, with no explicit cross-printing reconciliation. Mirrors the identical, deliberate gap already present for `power`/`toughness`; out of this story's scope per its own Dev Notes (extraction only, not aggregation semantics). (Source: Edge Case Hunter; Severity: Low.)
- **`tests/fixtures/scryfall_sample.json` not updated with a realistic `game_changer` key** — the three new unit tests use a hand-built minimal `card_json` dict rather than the shared Scryfall fixture, so a real-world schema drift in the live field (e.g. Scryfall renaming/nesting it) wouldn't be caught. Story Dev Notes explicitly scope this story to synthetic-input unit tests only ("no live Scryfall data or re-import is required"). (Source: Blind Hunter; Severity: Low.)
- **No DB round-trip test for `game_changer`** — only the in-memory `CardModel` object returned by `transform_scryfall_card` is asserted; nothing proves `False` survives an actual SQLite INSERT/SELECT rather than being coerced to `NULL` on the real dialect. Identical gap already exists for the `power`/`toughness` precedent — no such round-trip test exists anywhere in the suite today. Somewhat more load-bearing here than a typical gap, since defending against exactly this `None`/`False` conflation is this field's whole purpose. (Source: Blind Hunter; Severity: Medium, but pre-existing pattern.)
- **No Pydantic schema-layer test for `game_changer`** — nothing constructs/validates a `Card` (via `model_validate`/`model_dump`) with `game_changer=False` to prove the "no coercion validator" claim rather than merely asserting it in a comment. Identical gap already exists for `power`/`toughness` in `tests/unit/data/test_schemas.py`. (Source: Blind Hunter; Severity: Low.)
- **Sprint-status prose doesn't note the feature isn't usable end-to-end until Story 4.2's migration ships** — `epic-4` flips to `in-progress` and `4-1` to `done` while `4-2-migrate-and-backfill-existing-databases` stays `backlog`; a reader of `sprint-status.yaml` alone can't tell "done" here means "additive schema only, unusable on existing DBs until 4.2 ships." Already documented clearly in this story's own Dev Notes ("What this story is (and is NOT)"). (Source: Blind Hunter; Severity: Low.)

## Deferred from: code review of story-5.1 (2026-07-12)

> 3-reviewer adversarial pass on Story 5.1's calibration benchmark set (`tests/fixtures/benchmark_decks.py` + 7 decklist fixtures + offline self-validation test). The headline finding — a rules-illegal duplicate "Kinnan, Bonder Prodigy" card in `cedh_kinnan_bonder_prodigy.txt`, rooted in the Dev Agent's admitted departure from AC3/Task 2's "copy verbatim from source" mandate — is a decision-needed item logged in the story file's Review Findings, not deferred here (it's a defect in the acceptance-gate data itself, not a pre-existing/out-of-scope gap). The items below are real but low-severity hardening gaps, not blocking.

- **Parser silently drops cards under an unrecognized/misspelled section header** — `tests/fixtures/benchmark_decks.py:120-147`. A future manifest refresh with a typo'd header (e.g. "Deck:" or "Side Board") would silently lose every card line under it with no diagnostic, undermining the "actionable failures" intent behind AC7. No occurrence in the current 7 entries. (Source: Edge Case Hunter; Severity: Low.)
- **Missing/unreadable `decklist_file` raises an unlabeled `FileNotFoundError`** — `tests/fixtures/benchmark_decks.py:174-182`. `load_benchmark()` doesn't wrap the read with the offending entry's `key` in the error message. No current occurrence. (Source: Edge Case Hunter; Severity: Low.)
- **Parser accepts a zero-quantity card line with no guard** — `tests/fixtures/benchmark_decks.py:149-158`. `BenchmarkCard.quantity`'s docstring claims `>= 1` but nothing enforces it; a `0 Foo (SET) 1` line would parse as a phantom zero-quantity card. No current occurrence. (Source: Edge Case Hunter; Severity: Low.)
- **No guard against split-quantity duplicate non-commander cards** — `tests/fixtures/benchmark_decks.py:149-158`. Generalizes the Kinnan bug class beyond commanders; `_mainboard_total` sums by line, not by distinct name, so the same card split across two lines would inflate the total silently. No current occurrence outside Kinnan; would be caught by the same duplicate-name-check patch tracked in the story file, once implemented. (Source: Blind Hunter; Severity: Low.)

## Deferred from: code review of story-5.2 (2026-07-12)

- **No construction-time (`__post_init__`) validation for weight-sum / win-turn-band ordering / rubric domain / non-empty version invariants** — `src/logic/assessment/profiles.py:43,69` (`DimensionWeights`, `FormatProfile`). AC3 permits (doesn't require) `__post_init__` validation on the frozen dataclasses; the two hardcoded module constants are already exhaustively covered by `tests/unit/logic/test_assessment_profiles.py`, so this is only a gap for hypothetical future dynamic construction (e.g., an Epic 7 `PROFILES` lookup or a 5.9 tuning script constructing profiles outside this module). Revisit if/when `FormatProfile`/`DimensionWeights` are ever constructed anywhere else. (Source: Blind Hunter + Edge Case Hunter, independently; Severity: Low.)

## Deferred from: code review of story-5.3 (2026-07-12)

> 3-reviewer adversarial pass on Story 5.3's shared oracle-text classifiers
> (`src/logic/assessment/classifiers.py`). No decision-needed items — AC5/AC6 explicitly state
> pattern-list content is provisional v1 vocabulary owned by Story 5.9's benchmark pass ("tests
> pin canonical-card behavior, not pattern contents"), which pre-answers most of what the review
> layers surfaced. The real, unambiguous code/doc gaps are logged as `[Review][Patch]` items in
> the story file instead. The two items below are real but have no current consumer to be harmed
> by them yet.

- **`_detect_hard_trigger`-based functions (`detect_mass_land_denial`, `detect_extra_turn_cards`) each call `classify_deck` independently, with no memoization** — `src/logic/assessment/classifiers.py:364-396`. Checking both FR12 hard triggers back-to-back reclassifies every card in the deck twice (full 9-category classification each time). No current caller does this — Story 5.7 (Bracket floor) is the first consumer and hasn't been built yet. Revisit there: call `classify_deck` once and read both buckets, or cache within a request scope. (Source: Blind Hunter; Severity: Low.)
- **`classify_card`'s `frozenset[str]` return has no deterministic ordering**, unlike the sorted-tuple discipline (`CategoryCount.card_names`, `HardTriggerFlag.card_names`) used everywhere else in the module for its stated AD-8-spirit determinism goal — `src/logic/assessment/classifiers.py:252-304`. Only matters if a future caller serializes per-card output directly instead of routing through `classify_deck` (which does sort). No such direct consumer exists yet. (Source: Blind Hunter; Severity: Low.)

Also surfaced but explicitly out of scope per AC5/AC6 (pattern-content tuning is Story 5.9's job,
not logged as action items — candidate regression fixtures for that story's benchmark pass):
Isochron Scepter's copy-effect text doesn't match any `WINCON_COMBO_PIECE` pattern despite being
the module's own implied canonical combo example; MDFC spell-face tutors get excluded from
`TUTOR` via the joined `type_line`'s land check when the back face is a land (e.g. a
to-hand/top-of-library tutor printed on a modal DFC); single-target "target player loses the
game" wincons (Door to Nothingness) don't match `_WINCON_EXPLICIT_RES`; untap-enabler wordings
like "untap it" / "untap enchanted creature" (Freed from the Real) don't match
`_COMBO_PIECE_RES`; plural/numeric extra-turn phrasing (Alrund's Epiphany's "takes two extra
turns") doesn't match `_EXTRA_TURN_RE`; `_HAYMAKER_RE` has no pump-magnitude threshold (any
"creatures you control get +1/+1"-style anthem matches identically to Craterhoof Behemoth);
graveyard-hate cards (Tormod's Crypt) get the generic `INTERACTION` tag via the mass-wipe
`(?:destroy|exile) (?:all|each)` branch. (Sources: Blind Hunter + Edge Case Hunter, batched;
Severity: n/a — explicitly deferred by the story's own ACs.)

## Deferred from: code review of story-5.5 (2026-07-13)

> 3-reviewer adversarial pass on Story 5.5's consistency/interaction/structural-coverage
> signals (`src/logic/assessment/consistency.py`). No decision-needed items. The Edge Case
> Hunter's one formal finding (`structural_gaps[formula]` unguarded `KeyError`) was dismissed
> on triage, not deferred — it matches the exact accepted precedent already shipped in
> `mana_base.py`'s `karsten_land_delta`/`compute_pip_signals` (mypy's `Literal` enforces the
> contract at call sites, same as every sibling function in the module).

- **`classify_card` (Story 5.3) doesn't exclude land-typed cards from the
  `INTERACTION`/`CARD_DRAW`/`WINCON_*` tags** (only from `RAMP`/`TUTOR`) —
  `src/logic/assessment/consistency.py:259`. A land whose oracle text matches an interaction
  pattern (e.g. a "destroy target artifact" land) is silently folded into
  `interaction_signals`'s count and CMC-0 bucket. Pre-existing Story 5.3 classifier behavior,
  not caused by this change — revisit if a downstream consumer (5.7/5.8) needs a
  nonland-only interaction read. (Source: Blind Hunter; Severity: Low.)
- **`STRUCTURAL_GAP_BASELINES` is `dict[KarstenFormula, dict[str, int]]`** — the outer
  `KarstenFormula` key is Literal-checked (the 5.4 review lesson), but the inner category
  keys (`CARD_DRAW`/`INTERACTION`/`RAMP`) remain plain `str`, so a future typo'd/missing key
  is a runtime `KeyError` inside `structural_gaps`, not a mypy error —
  `src/logic/assessment/consistency.py:310`. Root cause is `classifiers.py`'s untyped
  category constants from Story 5.3; fixing it properly means Literal-typing those constants
  upstream, out of this story's scope. (Source: Blind Hunter; Severity: Low.)
- **`probability_at_least` has no property/invariant test** asserting output always stays in
  `[0.0, 1.0]` for arbitrary valid inputs — `src/logic/assessment/consistency.py:59`. It's the
  shared primitive every other function in the module (and future 5.6/5.7 combo-probability
  call sites) delegates to; only pinned exact-value/edge-case tests exist today. Optional
  hardening beyond AC8's required test matrix — revisit if a future refactor touches the
  summation/clamp logic. (Source: Blind Hunter; Severity: Low.)

## Deferred from: code review of story-6-1 (2026-07-16)

> Story 6.1 is the schema/migration/write-path slice of commander identity. Its Dev Notes
> explicitly scope **all commander validation/inference to Epic 7 / Story 7.1** ("Do not add
> inference logic anywhere"). These two items are the validation surface that slice will need.

- **No commander-identity validation anywhere on the write paths** — the deck can hold any number
  of `commander=True` rows (the "two flagged rows = partners" invariant is unguarded and could be
  exceeded via repeated `add_card_to_deck(commander=True)` or a `merge_decks` that stacks
  source-flagged cards onto an already-two-commander target); a card can be flagged
  `commander=True` **and** `sideboard=True` simultaneously (a semantically impossible mainboard-only
  concept — no cross-field guard in `DeckRepository.add_card_to_deck` `src/data/repositories/deck.py:294`
  or the tool helper `src/mcp_server/tools/deck_management.py:408`); and `merge_decks`' exists-branch
  keeps the target's flag, so merging a commander source deck whose commander is already an unflagged
  card in the target silently yields a "commander deck" with zero flagged commanders
  (`src/data/repositories/deck.py:648`). All spec-accepted for this slice; Epic 7's edge-resolution
  should add the count cap, the mainboard-only guard, and a zero/over-count warning.
  (Source: Blind Hunter + Edge Case Hunter; Severity: Medium; deferred to Epic 7 / Story 7.1.)
- **No API path to change an existing row's commander flag** — once a card is in the mainboard,
  `add_card_to_deck` returns `status="exists"` (via `IntegrityError`) and never updates the flag;
  `update_card_quantity` and the Arena `import_decklist` "exists" path likewise never touch it. So
  promoting/demoting a commander requires remove-then-re-add. Fine for this slice (matches the
  established additive-import contract), but Epic 7 (or a deck-edit story) will need an explicit
  set-commander path. (Source: Blind Hunter; Severity: Low; deferred.)

## Deferred from: code review of 7-2-combo-provisioning-the-degradation-ladder (2026-07-17)

- **Transient `OperationalError` during combo provisioning is reported as
  `combo_data_unavailable`** — `ComboSnapshotRepository`'s three read methods catch
  `OperationalError` broadly and return "absent" (`src/data/repositories/combo_snapshot.py:59,72,124`),
  so a momentary "database is locked" / "disk I/O error" is indistinguishable from a genuinely
  missing snapshot: a healthy snapshot gets mislabeled unavailable and confidence is lowered.
  Graceful (never crashes) and rooted in the Story 6.3 repo contract, not Story 7.2's diff.
  Fix would narrow the repo's `except OperationalError` to the missing-table case (edits
  `src/data`, out of 7.2 scope). (Source: Blind Hunter; Severity: Low; deferred — data-layer.)
- **Deck power summary counts `almost_included` variants as "combo variants matched"** —
  `combos_matched = len(scored.core.combos)` (`src/mcp_server/tools/assess_deck_power.py:524`)
  includes both the `included` (shortfall 0) and `almost_included` (shortfall 1) buckets, so a
  deck one card short of a single combo reads "1 combo variant matched", implying a live combo.
  AC 6 only requires a "combos matched count" and the 7.2 summary is explicitly provisional;
  Story 7.3 (human-summary serialization) should disambiguate assembled vs one-away in the
  client-facing projection. (Source: Blind Hunter; Severity: Low; deferred to Story 7.3.)

## Deferred from: code review of c1-2-side-effect-free-asgi-app-with-a-lifespan-and-a-health-endpoint (2026-07-25)

- **`lifespan_client` seam is not parameterizable for its named inheritors** — the conftest helper
  hardcodes `BASE_URL = "http://testserver"` and accepts no headers/base-url kwargs
  (`tests/unit/companion/conftest.py:26-43`), but c1-5's Host-validation/CORS/token tests must vary
  exactly those. Extending the signature with optional kwargs is backward-compatible, so the
  extension belongs to c1-5 when the need is concrete rather than speculative here.
  (Source: Blind Hunter; Severity: Low; deferred to c1-5.)
  **CLOSED 2026-07-25 by c1-5 (AC 11).** `_lifespan_client` now takes `base_url=`, `headers=` and
  `bound_port=` kwargs and stamps `app.state.bound_port` when the app has none, deriving a matching
  loopback `base_url` from it. The acceptance signal was that all 149 pre-existing companion tests
  pass **unedited** — which also means the whole suite now flows through the real `Host` envelope
  rather than around it.
- **mypy pre-commit hook `additional_dependencies` drift from `uv.lock`** — the hook's isolated env
  resolves `fastapi>=0.139.2` (and the pre-existing pydantic/sqlalchemy entries) independently at
  hook-install time (`.pre-commit-config.yaml:9`), so pre-commit mypy may check a different FastAPI
  than the locked 0.140.0 CI/runtime uses. Pre-existing pattern extended, not introduced, by c1-2.
  (Source: Blind Hunter; Severity: Low; deferred — pre-existing tooling pattern.)
  *Update 2026-07-25: re-flagged by the c1-3 review (dismissed as this known item) and by Greptile
  as the sole P2 on PR #11 (`uvicorn>=0.51.0`, same pattern). Brad's ruling: merge as-is, leave
  deferred — the hook is a fast local smoke; CI's `uv sync --locked` + `mypy src/` is the
  authoritative typed gate against the real locked versions. Pinning one dep would be inconsistent
  with the other seven floors; pinning all seven would go stale against `uv.lock` unchecked.*

## Deferred from: code review of c1-3-port-selection-with-ephemeral-fallback-and-a-printed-launch-url (2026-07-25)

- **No `SO_EXCLUSIVEADDRUSE` on the Windows bind** — `_new_socket` correctly omits `SO_REUSEADDR`
  on Windows (`src/companion/app/server.py:109-124`), but does not set `SO_EXCLUSIVEADDRUSE`, so
  another local process binding with `SO_REUSEADDR` can still bind over the companion's held port —
  weakening AD-4's single-instance premise at the socket layer. c1-3's ruling was "mirror asyncio's
  own reuse policy", and c1-8's instance_id probe detects a wrong server downstream; deciding
  whether the socket itself should be hardened belongs to c1-5's security envelope.
  (Source: Edge Case Hunter + Blind Hunter; Severity: Low; deferred to c1-5.)
  **CLOSED 2026-07-25 by c1-5 (AC 10).** `_new_socket()` now sets `SO_EXCLUSIVEADDRUSE` on Windows,
  as the complement of (not a replacement for) the POSIX-only `SO_REUSEADDR`, pinned by
  `test_exclusiveaddruse_is_set_on_windows_only`. The platform branch is written against
  `sys.platform == "win32"` rather than `os.name == "nt"`: the two are runtime-identical here, but
  only `sys.platform` is narrowed by mypy, and CI type-checks on ubuntu where typeshed has no such
  constant (verified: the `os.name` form fails `mypy src/ --platform linux` with
  `Module has no attribute "SO_EXCLUSIVEADDRUSE"`).
- **`free_port()` bind-close-reuse TOCTOU in the c1-3 test helper** — between releasing the probe
  socket and the test re-binding the returned port (`tests/unit/companion/test_server.py:52-65`),
  another process can take it; latent flake class for the four tests asserting on `wanted`. The
  suite runs without xdist and the window is tiny — recorded so a future flake on these tests is
  instantly diagnosable (fix = retry loop in `free_port`). (Source: Edge Case Hunter + Blind
  Hunter; Severity: Low; deferred — act on first flake.)

## Deferred from: code review of c1-4-typed-rest-error-contract-with-closed-reason-tokens (2026-07-25)

- **Outermost error middleware vs c1-5's CORS: unhandled-503s will carry no CORS headers** — c1-4
  pins `UnhandledErrorMiddleware` outermost (`src/companion/app/main.py`, install-last comment) so
  it can type the failures of every inner middleware, and directs c1-5 to insert *inside* it. The
  flip side: a 503 minted by the error middleware never passes back through an inner
  `CORSMiddleware`, so a cross-origin caller sees an opaque network error for exactly the failure
  class c1-4 exists to type. c1-5 must weigh the ordering trade (typed failures of the security
  middleware vs CORS-visible unhandled errors) with its actual CORS scope in hand — the tension is
  recorded here so it is inherited explicitly, not discovered. (Source: Blind Hunter; Severity:
  Low; deferred to c1-5.)
  **CLOSED 2026-07-25 by c1-5 (AC 9, Decide-once #3) — resolved by the no-CORS ruling, not by an
  ordering change.** c1-5 installs no `CORSMiddleware` at all: AD-13 serves the SPA from this same
  backend, so every legitimate request is same-origin and the empty grant *is* "restricted to the
  app's own origin". With no inner CORS middleware there is no trade left to make — the
  "outer-503 never passes back through inner CORS" tension cannot arise. Pinned by three
  assertions in `test_security.py::TestCorsIsDeliberatelyAbsent`, so a later story that wants CORS
  must revisit this ruling first.

## Deferred from: story c1-5-localhost-only-security-envelope-host-validation-and-cors (2026-07-25)

- **`test_list_decks_with_strategy_field` is order-flaky on a same-tick tie** — observed failing
  once in a full-suite run during c1-5 and passing in isolation and on two subsequent full runs;
  **pre-existing and unrelated to c1-5**, which touches nothing under `src/data`. The test creates
  three decks back-to-back and asserts a strict newest-first ordering
  (`tests/integration/data/test_deck_repository.py:320-333`), but `list_decks` orders by
  `DeckModel.created_at.desc(), DeckModel.id` (`src/data/repositories/deck.py:262`) — so when two
  `created_at` values land in the same clock tick the tie-breaker is a **random UUID**, which does
  not correlate with insertion order. Fix = tie-break on something monotonic, or have the test
  space its creations. Recorded rather than fixed because it is outside c1-5's AC 16 scope
  boundary. (Source: c1-5 full-suite gate run; Severity: Low; needs a home in the data-layer work —
  natural fit is `data-layer-orphan-handling`, the other open `src/data` item.)

## Deferred from: code review of c1-6-lazy-database-engine-so-a-fresh-install-starts-instead-of-erroring (2026-07-25)

- **Cached-engine path never re-runs the existence check** — once an engine is cached, deleting
  `cards.db` while the companion runs means the next request's connection re-plants a zero-byte
  file (the response is still a correct `503 database_not_initialized`, via the empty-file probe).
  Includes the narrower exists→connect TOCTOU window on first creation. AC 3's no-plant guarantee
  is scoped to before-first-engine by design; a per-request re-stat would restore it at all times
  but is machinery with no failing user story behind it. Natural revisit point is 17-3 (latency
  work touches the same per-request path). (Source: Edge Case Hunter; Severity: Low.)
- **A durably corrupt `cards.db` is classified transient forever** — ~~a UX ruling for c2-9 to
  make with the state designs in hand~~. **RULED AND HALF-SHIPPED, c2-9 (Q5, Brad 2026-07-29.)**
  The backend stays as it is: it genuinely cannot distinguish 200 ms of mid-import from a month
  of garbage, which is why decide-once #4 ruled the condition transient, so the distinguisher is
  **elapsed time on the client**. A sixth state was added — *Database updating, stalled* — with
  its copy written into `EXPERIENCE.md`'s table ("Reads haven't resumed for a while. Check your
  agent session — if no import is running, ask it to rebuild the database (`initialize_database`).")
  and its panel shipped in `src/components/StatePanel/`. It is declared `RETRIES_QUIETLY: false`
  in `states.ts` — the escalation of a quiet retry that has not worked.
  ~~**What remains, homed at c3-9** (which owns the polling): the "for a while" threshold and the
  switch from `database-updating` to `database-updating-stalled`.~~ **CLOSED, c3-9 (Q3,
  2026-08-02).** `STALLED_AFTER_MS = 60_000` in `ui/src/state/poller.ts` — 60 s of *continuous*
  `database_unavailable`, which at the 2 s / x2 / 30 s schedule is at least six consecutive
  refusals with the last two a full ceiling apart, so a single slow write burst cannot escalate.
  Armed by that token and by nothing else, and reset by every other outcome including a `200`;
  `database_not_initialized` NEVER escalates at any elapsed time, because a multi-minute first
  build is its normal case and its own copy promises the wait. Both directions are asserted from
  one fake clock, and mutation probe (e) — arming the clock on any error — turns the
  never-escalates assertion red. Historical note: The reason the ruling was not "leave it transient": for a durably corrupt
  file, "Reads will resume automatically — nothing to do here" is simply **false**, and c2-9 is
  the one story in the feature whose whole subject is whether the words are true.
  (Source: Blind Hunter; Severity: Low → **ruled**, implementation residue at c3-9.)
- **URI-form SQLite `CARDS_DATABASE_URL` is misclassified as a file path** — `database_file` handles
  `:memory:` and empty-database, but `sqlite+aiosqlite:///file::memory:?cache=shared` (or
  `?uri=true` forms) falls through to `Path(parsed.database)`, which never exists → permanent 503
  for a valid in-memory URL. Same family and same channel as the bare-path item above (line ~268):
  an exotic explicit env override, not a supported configuration. Fold into that item's eventual
  fix (early validation of `CARDS_DATABASE_URL` shapes). (Source: Edge Case Hunter + Blind Hunter;
  Severity: Low.)
- **`UnhandledErrorMiddleware`'s full-traceback logging can carry `[SQL]`/`[parameters]`** — a
  SQLAlchemy `StatementError` that is not a `DatabaseError` (e.g. a wrapped `InterfaceError`)
  falls through to the 500 path, whose `logger.exception` prints the full traceback including the
  statement and bound parameters — the exact strings AC 9 scrubs on the 503 path. Pre-existing
  c1-4 middleware behavior (deliberate: full tracebacks on unhandled bugs), surfaced now that DB
  paths can route through it. Candidate: scrub `[parameters: ...]` from tracebacks, or accept as
  local-log-only. (Source: Blind Hunter; Severity: Low.)

## Deferred from: story c1-7-discovery-file-as-the-sole-rendezvous (2026-07-26)

- **`os.replace` fails with `PermissionError [WinError 5]` while another process holds the target
  open** — measured on this machine during story writing and re-confirmed in implementation. The
  window is microseconds (a reader does one `read_bytes()` and closes), and the write happens once
  per process start, so no retry machinery was added. The consequence to inherit: under c1-7's
  Decide-once #3 a publish failure **aborts the launch**, so a companion started at the exact
  instant an agent tool was reading the file could fail to start with a permissions error that has
  nothing to do with permissions. No failing user story stands behind it today — startup contends
  with an existing file for the first time in **c1-8**, whose entire subject is a second launch
  meeting a file it did not write, which is why that story is the natural home. Candidate fix if it
  ever bites: a bounded retry (2–3 attempts, short sleep) around the `os.replace` alone, or
  narrowing Decide-once #3 so a *transient* replace failure degrades where an unwritable directory
  still aborts. Windows-only. (Source: c1-7 story-writing probe 3, re-verified at implementation;
  Severity: Low; deferred to c1-8.)

  **Ruling (c1-8, 2026-07-26): still accepted, re-homed to c6-1.** c1-8 did not make this more
  likely, and it is worth being precise about why. The startup check reads `companion.json` through
  `read_discovery` — once before the probe is dialled, and (on the reclaim path only) once more in
  `_note_reclaimed_entry` to decide whether the INFO line has anything to say; each read is a single
  `read_bytes()` whose handle closes immediately — and it does so in a launch that either *returns
  without publishing* (a live instance was found) or publishes much later, from the lifespan, long
  after both handles are gone. **A process
  therefore cannot collide with itself**, which was the one new self-inflicted way this could have
  started firing. The only concurrent reader of the file in production still arrives with **c6-1**,
  whose client reads the rendezvous before every push — that is the first code that will hold the
  file open at an arbitrary moment while some other process starts. Re-homed there; nothing to do
  in c1-8.

- **TOCTOU in `remove_discovery`'s ownership guard** — the read → compare-`instance_id` → `unlink`
  sequence in `src/companion/discovery.py::remove_discovery` is check-then-act: a second instance
  that `os.replace`s its own record in between our read and our unlink loses its live rendezvous to
  our deletion — the exact scenario the guard exists to prevent, in a microsecond window on a path
  that runs once per process lifetime. No code fix wanted now: an atomic verify-and-delete has no
  clean cross-platform shape (Windows cannot unlink-by-open-handle portably from Python), and until
  c1-8 lands there is never a second live instance to collide with. Acknowledged in the function's
  docstring. Candidate fixes if it ever bites: open-with-`O_RDWR`-verify-then-unlink on POSIX with a
  documented Windows residual, or serializing shutdown/startup around a lock file. (Source: c1-7
  code review 2026-07-26, Blind Hunter + Edge Case Hunter; Severity: Low; deferred to c1-8, which
  owns the contending-instances design.)

  **Ruling (c1-8, 2026-07-26): accepted, and materially narrowed — entry kept.** The window needs a
  *second live instance* to be harmful: our shutdown must unlink a record that some other running
  companion published in between our read and our unlink. That second instance is now precisely the
  case c1-8 refuses — a launch that finds a verified-live companion prints its URL and returns
  without ever publishing, so the ordinary route to two contending writers is closed. What remains
  is the narrow residual recorded in the c1-8 section below: two launches racing inside the same
  startup window (a couple of seconds at the outside) can still both start, and only then can this
  unlink hit a foreign live record. So the guard is not redundant and the entry stays open, but its reachability now depends
  on a race that is itself deferred, not on ordinary use. No code change; `remove_discovery`'s
  docstring was reworded (c1-8 AC 16) because it previously pointed forward to c1-8 as the story
  that "first makes two instances contend for this file", which is stale in both halves now that
  c1-8 has landed and *prevents* the ordinary second instance.

  **Ruling (c1-9, 2026-07-26): CLOSED by unreachability — no code change to `remove_discovery`.**
  The harm scenario requires a second *live* instance inside one data directory, and c1-9's held
  advisory lock (`src/companion/app/singleton.py`) makes that state unconstructible: `run()` takes
  the lock before it resolves a port, binds or builds an app, and holds it until the process dies,
  so the launch that would have become the second live writer refuses instead. The check-then-act
  sequence in `remove_discovery` is unchanged and still not atomic — the entry is closed because
  nothing can reach it, not because the code was made safe. Its docstring was corrected accordingly
  (c1-9 AC 16), replacing c1-8's "two launches colliding within the same fraction of a second"
  wording.

  **What would reopen it, stated plainly rather than discovered later:** two companions run
  deliberately under *different* `PLANESWALKER_DATA_DIR` values. That is a supported configuration
  and it is not a defect — each instance then gets its own lock file, its own `companion.json` and
  no shared state, so the two never contend over one record and the TOCTOU still has no reachable
  harm. The residual would only return if a future story reintroduced two live instances sharing a
  single data directory, which the lock is specifically there to prevent. (This is the c1-8-review
  lesson about `trust_env=False` applied in advance: an environment variable that legitimately
  partitions the guard's scope must be *stated*, not left to be found.)

## Deferred from: story c1-8-single-instance-enforcement-with-verified-identity (2026-07-26)

- **Two launches started within the same startup window can both start** — the
  single-instance check is **check-then-act**, and nothing makes the check and the publish one
  atomic step. `run()` asks `client.live_instance()`, gets "nothing there", and only much later
  does the lifespan write `companion.json`; a second process entering that same gap reads the same
  "nothing there" and starts too, publishing over the first. That is the *baseline* failure this
  story was written to fix — two live companions with one rendezvous, the first still running and
  unreachable through the file — surviving in a window narrowed from **forever** to **startup**.
  Deliberately not fixed here: a real fix needs an OS-level mutex, and the shapes on the table
  (an `O_EXCL` lock file with the stale-lock-after-crash problem AD-15 guarantees will happen, or
  treating the bound port itself as the lock, which inverts the story's ordering by moving the
  check *after* the bind) are a design decision rather than a tweak — and the port option would
  need c1-3's ephemeral fallback rethought, since falling back to a different port is exactly how
  a second instance currently succeeds. The window is wider than it first looks (review finding,
  c1-8): it runs from the first launch's check to its lifespan publish, and with production
  timeouts the probe alone can spend up to ~3 s against a stale entry (1 s connect on a dead port,
  2 s read on a silent one, now also bounded overall at 5 s) — so a human double-launching a
  couple of seconds apart after a crash can hit it, no script required. Still a deliberate,
  repeated human act against an unlucky interleaving, not ordinary use.

  **Ruling (Brad, 2026-07-26, post-#15-merge): c1-9 builds the fix — a process-lifetime held
  lock.** Not a candidate any more: Story 1.9's ACs in `epics-companion-app.md` now carry it. The
  shape is the held-advisory-lock design, not an `O_EXCL` create-and-delete lock file: hold
  `msvcrt.locking`/`fcntl.flock` on an open handle for the process's lifetime, and the kernel
  releases it on any death — so AD-15's guaranteed crashes leave no stale lock and need no
  PID-liveness heuristics. This also collapses the `remove_discovery` TOCTOU's reachability to
  zero (its harm scenario needs a second live instance, which the lock makes impossible), which
  is the substance of Greptile's 3/5 hold on PR #15. Close this entry when c1-9 lands.
  (Source: c1-8 AC 15, homed at implementation; Severity: Low → fix scheduled c1-9.)

  **CLOSED (c1-9, 2026-07-26) — shipped as `src/companion/app/singleton.py`.** What landed, rather
  than what was planned:

  - **The primitive.** `os.open(lock_path(), O_RDWR | O_CREAT, 0o600)` then
    `msvcrt.locking(fd, LK_NBLCK, 1)` on Windows / `fcntl.flock(fd, LOCK_EX | LOCK_NB)` on POSIX,
    behind a module-level `sys.platform` branch. `LK_NBLCK` not `LK_LOCK` (which blocks ten times
    over ten seconds) and `flock` not `lockf` (record locks are process-owned, so a second `lockf`
    on another descriptor in the same process succeeds — it would have weakened the guarantee *and*
    made the same-process contention test silently vacuous). The lock file is `companion.lock`,
    separate from the rendezvous, zero-length, and **never unlinked** — on POSIX `flock` binds to
    the inode, so unlink-and-recreate would hand two processes "the lock".
  - **Where it sits in `run()`.** Probe first, lock second: the acquire is below c1-8's refusal and
    above `_note_reclaimed_entry`, the port resolution and the bind, with the release in `run()`'s
    outermost `finally` so the lock outlives the socket. Probing first keeps all fourteen of c1-8's
    `TestSingleInstanceCheck` cases passing **unedited**, and leaves the informative refusal (the
    one that can name a URL) as the common path. A contended launch prints one line naming no URL
    and returns `0`; there is deliberately no second probe, which would have cost up to five
    seconds on the one path whose job is to get out of the way.
  - **Release-on-death, measured.** Re-confirmed on this machine at implementation time (win32,
    py3.12.13): a second descriptor *in the same process* is refused (`PermissionError`, errno 13),
    closing the holder releases it, another process holding it refuses this one, and after a **hard
    kill** of the holder the lock is immediately available again with the file still present at
    0 bytes. That is the property that makes the held design correct under AD-15 — a crash is
    ordinary, and there is no stale-lock state to recover from and no PID-liveness heuristic.
  - **The race, before and after.** The baseline probe at `8bfc909` spawned two `run(0)` launches
    6 ms apart and left **two** live companions with one rendezvous. Re-run against the fix, one
    process survives, its port is the one `companion.json` names, and the loser prints a refusal
    line (see the c1-9 story record's live check 1 for the pasted before/after).

  Because contention reports as `PermissionError` — indistinguishable from a genuine permission
  problem — only the *lock* call is guarded; the `os.open` sits outside it, so an unwritable data
  directory fails loudly instead of being misreported as "someone else has it".
  (Severity: Low → **CLOSED**; no residual carried forward.)

- **A live instance whose event loop is blocked for longer than the read timeout is judged dead**
  — `PROBE_TIMEOUT` gives the read 2 s, and a companion wedged past that (a pathological request,
  a stop-the-world pause, a debugger breakpoint) answers `/health` too late. The probe then reports
  *app not running*, the launch proceeds, and the machine ends up in the two-instance state above.
  The 2 s read was chosen against a measured ~15 ms live response, so the margin is ~130×, and
  lengthening it has a real cost on the far more common path: every post-crash launch would stall
  for whatever the new deadline is. Accepted as the right side of the trade rather than fixed. If
  it ever bites, the fix is not a longer timeout but a different question — retry the probe once
  before concluding *dead*, which is machinery c6-1 is already building for its push path and
  could share. (Source: c1-8 AC 15, homed at implementation; Severity: Low.)

## Raised by Brad, outside a story (2026-07-26)

- **`assess_deck_power` ignores mana *quality* — it only counts mana** — the `mana_efficiency`
  dimension is built from two count-based signals and nothing else: Karsten land-**count** delta
  (`mana_base.karsten_land_delta`) and per-colour **source-count** deficits
  (`mana_base.compute_pip_signals` → `dimensions._mana_efficiency_score`, which starts at 100 and
  subtracts a penalty per land outside the tolerance band and per missing colour source). A source
  is any Land whose type line or "add {X}" text names the colour, and **every source counts the
  same**. Concretely, today's scorer cannot tell apart:
  - a **shockland from a Guildgate** — enters-tapped is invisible, so the tempo cost of a slow
    mana base is unscored, and this is the single biggest quality gap in Commander and 60-card
    alike;
  - a **fetchland or triome from a basic** — fixing depth and land-type synergy are unmodelled;
  - **painlands / filters / bounce lands** from clean duals — the *cost* of fixing is unmodelled;
  - a **mana dork or Signet from nothing at all** — `compute_pip_signals` `continue`s on every
    non-land, so **non-land colour sources contribute zero** to the deficit calculation. A
    rock-heavy or dork-heavy deck is scored as though its colours were unsupported, which is a
    correctness gap and not merely a missing refinement;
  - a **utility/colourless land** (Ancient Tomb, creature-lands, Cabal Coffers) beyond its
    non-contribution to colour — the upside is uncredited and the colour cost is only implicit.

  So two decks with identical curve and identical colour-source *counts* score identically on
  `mana_efficiency` even when one is an optimised mana base and the other is all taplands and
  basics — which is exactly the distinction an experienced player makes first. Weighting makes it
  matter: `mana_efficiency` is 0.20 of the 60-card profile (0.05 in Commander,
  `profiles.py:154/187`), so on the Standard/Modern fork this is a fifth of the score resting on a
  signal that is blind to mana quality.

  **Not a defect against any shipped AC** — Epic 5 scoped 5.4 to "raw numeric mana signals" and the
  Karsten regressions deliberately, and the benchmark passed on that basis. This is a **missing
  signal**, not a mistuned one, which is why it likely wants its **own story** (a
  `mana_quality`-style signal in `mana_base.py` + a dimension term) rather than a coefficient tweak.
  Feasibility is good: enters-tapped and produced-mana are both derivable from data already
  imported (oracle text / type line, the same inputs `_land_source_colors` reads), so no schema
  change or re-import is implied — the non-land-source fix in particular is close to free.

  **Homed against `post-epic-7-calibration-gate`** (sprint-status, currently `backlog`), which is
  the open bucket for scoring-quality inputs C1–C5; this joins them as a sixth, distinguished by
  being additive rather than corrective. Per the epic-7 gate-output homing rule it gets a key
  rather than a label. (Source: Brad, unprompted during story c1-7; Severity: Medium — it is
  weighted at 0.20 on the 60-card fork; no user-visible failure, but a systematic blind spot.)

## Deferred from: story c1-9-one-console-script-that-dispatches-without-disturbing-the-mcp-server (2026-07-26)

- **Windows Ctrl-Break ends the companion with exit status `3`, and interactive Ctrl-C is
  unverified** — live check 3 (real `CTRL_BREAK_EVENT` to a detached child) confirmed everything
  the AC names: no traceback, graceful uvicorn shutdown, `companion.json` removed,
  `companion.lock` retained, lock released for the next launch. But the observed exit status is
  `3`, not the dispatcher's `0` — traced, not assumed: uvicorn completes its graceful shutdown and
  the Windows console-control path then terminates the process before `main()` can return
  (`MAIN RETURNED` never prints under instrumentation), so the `3` is imposed outside our code.
  Interactive `CTRL_C_EVENT` could not be verified in the harness (it cannot be delivered to a
  detached child without also signalling the driver); `CTRL_BREAK_EVENT` is the proxy the story
  specifies. **Check during manual testing:** what an interactive Ctrl-C in a real terminal
  yields. Deliberately not "fixed" by trapping the signal, which would be new behaviour outside
  c1-9's ACs; if the exit status matters, 15-4's documentation story is where the observed
  behaviour gets written down. (Source: story c1-9 live check 3 / Completion Notes deviation 3;
  Severity: Low — Decide-once #5's exit vocabulary is about statuses *we* mint, and AD-15 rules
  out any supervisor that would read this one.)

  **CLOSED 2026-07-26 by Brad's C1-retro manual testing — real Ctrl-C exits `0`.** Observed in a
  real PowerShell terminal (venv-activated, `uv run artificial-planeswalker companion`, interrupt
  from the keyboard, `$LASTEXITCODE` read in the same window):

  ```
  INFO:     Shutting down
  INFO:     Waiting for application shutdown.
  INFO:     Application shutdown complete.
  INFO:     Finished server process [39616]
  $LASTEXITCODE -> 0
  data dir after -> cards.db, fastembed_cache, companion.lock (0 bytes); companion.json GONE
  ```

  So the `3` is an artifact of delivering `CTRL_BREAK_EVENT` to a **detached** child in the probe
  harness, **not** user-visible behaviour — the console-control path that imposed it is not the
  one a foreground Ctrl-C takes. On the real path `main()` does return and its value survives:
  Decide-once #5's exit vocabulary (0 = intent satisfied) holds end to end, with no signal
  trapping and no code change. 15-4 documents `0`. Every other condition the AC named also held:
  no traceback, graceful uvicorn shutdown, the lifespan retraction removed `companion.json`, and
  `companion.lock` was retained at 0 bytes for the kernel to release.
- **`test_entry_point.py`'s autouse `isolated_data_dir` fixture also re-points the two
  pre-existing transport tests** — the story said "leave the two old ones alone", and the
  documented deviation 1 covers only the forced `main()` → `main([])` edit. The new autouse
  fixture additionally moves `PLANESWALKER_DATA_DIR` to `tmp_path` for those two old tests, so
  they no longer exercise the real-data-dir path they did at baseline. Their assertions are
  unaffected and the change is an isolation *improvement* (they previously opened the developer's
  real card database); recorded here so the departure is stated rather than silent. Reopen only
  if a future story wants a test that deliberately exercises the real-data-dir diagnostics path.
  (Source: c1-9 code review, Acceptance Auditor; Severity: Low.)

## Deferred from: code review of c1-9 (2026-07-26)

- ~~**The "both mypy runs are mandatory" comment is enforced by no gate**~~ — **CLOSED by c2-1
  (2026-07-26).** `singleton.py`'s platform branch declares `uv run mypy src/` and
  `uv run mypy src/ --platform linux` both mandatory, but no pre-commit hook or CI step passed
  either `--platform`: the POSIX (`fcntl`) half was strict-checked only because CI happens to run
  on ubuntu, and the Windows (`msvcrt`) half only by Brad's local runs. A POSIX contributor could
  merge a type-broken Windows branch through a green CI. Fixed in `ci.yml`'s `quality` job, which
  was unfrozen for c2-1 (c1-9's AC 19 was what froze it).

  **What shipped is `--platform win32`, not the `--platform linux` the epic text asked for**, and
  the difference is the whole point. CI runs on `ubuntu-latest`, where the bare `mypy src/` **is**
  the linux run — adding `--platform linux` there would have been a pure no-op that satisfied the
  epic's letter while leaving the gap exactly as described above. The epic's wording was written
  from Brad's Windows machine, where the bare run is the win32 run; the retrospective's success
  criterion ("a deliberately Windows-broken `singleton.py` branch fails CI") is the one that
  identifies the real gap, and it is the one that was satisfied.

  Proven rather than assumed, per AC 17: with `msvcrt.locking(fd, msvcrt.LK_NBLCK)` (one argument
  short) temporarily substituted in the `sys.platform == "win32"` branch,
  `uv run mypy src/ --platform win32` reported
  `singleton.py:130: error: Too few arguments for "locking"  [call-arg]` and exited 1, while
  `uv run mypy src/ --platform linux` still reported `Success: no issues found in 83 source files`.
  The break was reverted; `git status --porcelain -- src/` is empty in the shipped commit.
  (Source: c1-9 code review, Blind Hunter; closed by story c2-1, C1 retro action item 3.)

## Deferred from: Epic C1 retrospective manual testing (2026-07-26)

Brad ran blocks A–D and G–H and declared himself satisfied; two blocks were not run. Homed here per
the gate-output rule rather than left as "we meant to".

- ~~**The renamed `COMPANION_PORT` env var has no live confirmation**~~ — **CLOSED by c2-1
  (2026-07-26)**, incidentally, by Task 10's second live check. With `$env:COMPANION_PORT = "9125"`
  set in a real shell before launch, the companion printed
  `[planeswalker] companion running at http://127.0.0.1:9125`, published
  `companion.json` for port 9125, and answered `GET /health` there with
  `{"status":"ok","instance_id":"9be64dcd-…"}` — while 8765 refused connections. So a real shell
  environment variable under the new name does reach `resolve_preferred_port`. **15-4 may now
  describe `COMPANION_PORT` as hand-verified.**

  *Originally recorded as:* ruling R4 renamed `PLANESWALKER_COMPANION_PORT` → `COMPANION_PORT`
  during the manual-testing pass, and the checklist block that would have exercised it end to end
  was not run afterwards. Coverage was otherwise good — the unit suite reads `server.PORT_ENV_VAR`
  so it followed the rename automatically (1,684 passed), and the *malformed*-input paths were
  hand-verified in block A — leaving only "does a real shell variable under the new name reach
  `resolve_preferred_port`" unconfirmed.

  **Still not hand-run:** the other half of that checklist block, `--port` beating the env var.
  That precedence has unit coverage and was not exercised live here, so 15-4 should describe the
  *variable* as hand-verified but not the *precedence*. (Severity: Low.)

- **FR-22's fresh-install start has no live confirmation** — the checklist block pointing
  `PLANESWALKER_DATA_DIR` at an empty directory to prove the companion *starts* rather than crashing
  with no `cards.db` present was not run. Unit coverage is strong and deliberate (c1-2's inertness
  tests fresh-import with the data dir pointed at a non-existent path; c1-6's laziness tests assert
  no engine, no file planted, and a 503 through a test-local route), and the *observable* half — a
  data endpoint answering `503 database_not_initialized` — has no shipped route until c3-1, so there
  is genuinely less to see today than there will be. **Natural home: c3-9** ("fresh install guides
  instead of erroring and comes alive on its own"), which owns that loop in the UI and cannot be
  accepted without a real empty-data-dir run. Recorded so c3-9 inherits it as a known-unverified
  precondition rather than assuming Epic C1 closed it. **CLOSED (backend half), c3-9 hand-run
  2026-08-02.** `PLANESWALKER_DATA_DIR` pointed at a genuinely empty directory: the companion
  STARTED, printed `http://127.0.0.1:8765`, published its discovery file, and planted **no**
  `cards.db` — c1-6's no-plant guarantee, confirmed live for the first time (the directory held
  only `companion.json`, `companion.lock` and `image_cache/`). `GET /health` answered `200`;
  `GET /api/decks` answered `503 {"reason":"database_not_initialized"}` with
  `cache-control: no-store`; `GET /` served the SPA. A populated `cards.db` was then copied in
  **with the server still running**, and the very next `GET /api/decks` answered `200` with real
  deck names — no restart, no cache-busting. FR-22's backend half is now confirmed rather than
  inferred. **What is still not confirmed is the PAGE doing it in a browser** — see c3-9's own
  residue below. (Severity: Low.)

## Deferred from: story c2-1 (2026-07-26)

- **`npm audit` reports 8 high-severity advisories in the `ui/` dev toolchain, and no gate looks at
  it.** All 8 are transitive and dev-only: `brace-expansion`/`minimatch` (a DoS via unbounded
  expansion) reached through `eslint`, `@eslint/eslintrc`, `@eslint/config-array` and
  `eslint-plugin-jsx-a11y`, plus `js-yaml` (quadratic CPU on merge-key chains) reached through
  `@redocly/openapi-core`, a dependency of `openapi-typescript`. Nothing here ships: Node is
  dev/CI-only (AD-13), `ui/dist` contains none of it, and the Python package never sees it — the
  realistic exposure is a contributor running `npm run lint` on hostile input.

  **Not fixed here, deliberately.** `npm audit fix --force` resolves it by installing
  `eslint-plugin-jsx-a11y@6.4.1` — a downgrade across a major boundary, which is the plugin that
  carries the entire UX-DR47 gate (AC 8). Trading a working accessibility gate for a DoS advisory in
  a linter is the wrong trade. The non-`--force` fix only reaches the `js-yaml` half. The real
  resolution is upstream: `eslint-plugin-jsx-a11y` publishing an `^10` peer range would let the
  `eslint ^9` pin lift and carry a patched `minimatch` with it — the same exit condition already
  recorded against the pin in `ui/package.json`.

  **Natural home: 15-5** (plugin distribution parity) or 15-4, whichever first has to make a
  statement about what the release contains. Re-check with `npm audit` then; if jsx-a11y has shipped
  an `^10` peer by that point this closes itself. Recorded so that the first person to run
  `npm audit` finds a decision rather than a surprise. (Severity: Low — dev-only, no runtime
  exposure; the *reporting* gap is the point, not the advisories.)

- **`ui/package.json` declares `engines.node: ">=20.19.0"` but the epic and PRD say "Node >= 20".**
  The measured floor is higher than the copy: `vite@8.1.5` declares
  `engines: ^20.19.0 || >=22.12.0` and `stylelint@17` declares `>=20.19.0`, so a literal Node 20.0
  cannot build `ui/`. `>=20.19.0` is the honest form of the same requirement and is what shipped;
  CI's `node-version: 20` resolves to the latest 20.x, which satisfies it. **This is a copy fix for
  15-4** (release documentation), not a scope change — nothing needs rebuilding, the prose needs to
  stop saying "20". (Severity: Low.)

- **A third load-bearing version pin exists that no planning document predicts:
  `@testing-library/jest-dom` at `~6.9.1`.** The story predicted two pins (`typescript`, `eslint`);
  this one was found at install time. Both `latest` (7.0.0) and 6.10.0 declare
  `engines.node: ">=22"`, above this project's `>=20.19.0` floor and above CI's `node-version: 20`;
  6.10.0 is additionally deprecated upstream as an incorrect minor release. 6.9.1 is the last
  release declaring `>=14`. Unlike the other two pins, npm does **not** fail on this — `engines` is
  advisory by default, so an unpinned bump would install cleanly and then break only on the Node 20
  CI job. The reason is recorded in `ui/package.json` beside the dependency. **Relevant to 15-4**
  (which documents the Node floor) and to whoever eventually proposes raising it: lifting this pin
  is a Node-floor decision (AC 2 / AC 15), not a dependency bump. (Severity: Low — pinned and
  documented; recorded because the Spine's stack table now lags reality by two entries, `eslint ^9`
  being the other.)

- **`tests/integration/data/test_deck_repository.py::test_list_decks_with_strategy_field` is
  order-flaky under full-suite load.** Observed failing once during c2-1's Task 0 baseline run
  (`assert 'Control' is None`), then passing 5/5 in isolation and passing on an immediate full-suite
  re-run at the identical commit — so it is pre-existing at `50dddc3` and unrelated to this story,
  which adds no Python. Cause: the test creates three decks in immediate succession and asserts
  `list_decks()` returns them newest-first, but `created_at` can tie at the same microsecond, and the
  ordering has no secondary tie-breaker — so the two decks created in the same tick can come back in
  either order. Fix is a deterministic secondary sort key (`id`, or a monotonic sequence) in
  `list_decks`, or distinct timestamps in the fixture. Not patched here because AC 21 forbids this
  story touching `tests/` or `src/`. Note this is the *same class* of defect as the flaky-test
  tie-breaker closed at the Epic 1 retro, in a different query. **Natural home:
  `data-layer-orphan-handling`** (already keyed in sprint-status as the data-layer catch-all) or any
  story that next opens `DeckRepository.list_decks`. (Severity: Low — a false red, never a false
  green; but it will keep costing someone a re-run.)

## Deferred from: code review of c2-2-the-backend-serves-the-built-spa-as-a-committed-artifact (2026-07-26)

- **`sprint-status.yaml`'s `last_updated` comment is a single ever-growing line, thousands of
  characters long.** Each story appends its entire narrative onto one line chained behind
  "Previously:", making it unreadable, undiffable, and unbounded. The pattern predates c2-2 (this
  story merely doubled down on it). Natural fix: keep `last_updated` to a date + one clause and let
  the story records carry the narrative — a process/tooling nit for the epic retro, not any story's
  code. (Severity: Low — cosmetic, but it degrades every future diff of the file.)
  **Upgraded 2026-07-26 while contexting c2-3, and it is no longer only cosmetic: the file does not
  parse as YAML.** Measured on the committed tree at `9b612eb` — `yaml.safe_load` raises
  `ScannerError: mapping values are not allowed here` at **line 49**, the `last_updated` mega-line,
  because a YAML plain scalar may not contain `": "` and that line now contains dozens of them
  ("ruled by Brad: AC 5's…"). Every BMad workflow reads and rewrites this file textually, which is
  why nothing has noticed. Consequence if that ever changes — a status dashboard, a script, a future
  workflow using a real parser — is a hard failure on the whole sprint file, not a degraded read.
  Fix is the same fix (date + one clause), or quote/block-scalar the value; either way it is one
  edit, and it should land before something starts parsing it.

- **AC 17's browser-render half of c2-2 is Brad's, deferred to the C2 epic manual-testing
  checklist (ruled at review, 2026-07-26).** Every machine-checkable probe passed from a Node-less
  worktree (status codes, content types, byte-identical served bundle, cache headers, 405+Allow);
  what remains is opening `uv run artificial-planeswalker companion`'s printed URL in a browser and
  confirming the placeholder app paints. Reason for deferral: only a human can close SC-4's render
  half, and the epic retro checklist is its established home. (Severity: Low — every proxy signal
  is green; this is the eyes-on-pixels confirmation.)

## Deferred from: code review of c2-3 (2026-07-27)

- **`_truncate_descriptions`'s drop-the-key branch can void a Response Object's required
  `description` (spec-invalid OpenAPI).** `del node["description"]` at
  `src/companion/app/main.py:304` applies to every node, but the OpenAPI spec *requires*
  `description` on Response Objects. A route/response docstring consisting only of a Google-style
  section header would render a schema `openapi-typescript` (exit non-zero on a bad schema) may
  reject in the `frontend` job with a message pointing nowhere near the cause. Trigger is
  pathological today — every current response description is real prose — and the drop-the-key
  behavior is deliberately test-pinned
  (`test_a_description_that_is_only_a_section_loses_the_key`), so changing it is a design edit,
  not a patch. Natural fix when it matters: keep `""` (or skip the delete) when the parent context
  is a `responses` entry. (Severity: Low — unreachable without a degenerate docstring, and the
  failure is loud in CI.)

- **The sprint-status `last_updated` mega-line grew again in the same c2-3 diff that documented
  the file no longer parsing as YAML.** The upgraded entry above (2026-07-26) already homes the
  fix at the epic retro; recording here that c2-3's own bookkeeping commit lengthened the
  offending unquoted scalar rather than taking the one-edit quote fix — the retro fix should also
  re-check that nothing started parsing the file in the meantime. (Severity: Low — pre-existing,
  fix already homed.)

## Deferred from: code review of c2-4-the-voltglass-token-layer (2026-07-27)

- **Typography literals are the ungated family in the "every value is a token" set.** The c2-4
  literal bans cover colour/shadow/radius/spacing, but no rule keys `font`, `font-size`,
  `font-weight`, `line-height` or `letter-spacing`, so a component can hard-code type off the
  seven `--type-*` roles with no lint or guard firing. Deferred to c2-5, which owns type-role
  enforcement (the numeric-pairing lint); widening that to a full font-literal ban family — same
  shape as c2-4's four — is c2-5's scope decision. (Severity: Low — no components exist yet;
  c2-5 lands before the first one.)

  **CLOSED by c2-5 (2026-07-28).** Widened to the full family, per Brad's Q4 ruling: the ban is
  keyed on a property-name family regex covering `font`, every `font-*` longhand and
  `line-height`/`letter-spacing`, allowing only `var(--type-*)`, `var(--font-*)`,
  `var(--tracking-*)`, `0` and the CSS-wide keywords, with each property tied to its OWN token
  family so `font-weight: var(--space-1)` fails too. `font-variant-numeric` is deliberately
  excluded — its one legal value is already required by the numeric-pairing guard. Proven with
  `font-stretch`, `font-optical-sizing`, `font-size-adjust`, `font-synthesis` (never enumerated)
  and an invented `font-hyperkerning`. "Every value is a token" is now true.

## Deferred from: implementation of c2-5-self-hosted-space-grotesk (2026-07-28)

- **AC 4's render half is Brad's, deferred to the C2 epic manual-testing checklist.** The
  machine-verifiable half is fully closed: the committed binary is a real WOFF2 by signature,
  exact byte length and WOFF2 header (`tests/fonts.test.ts`), `git check-attr` resolves it as
  binary so a `core.autocrlf=true` Windows checkout cannot normalise it, it is emitted
  content-hashed into `assets/` and served `font/woff2`, the `@font-face` reaches it by a
  relative url the bundler rewrites, and nothing in the committed bundle names another origin.
  What remains is **opening the app in a browser with the network throttled to offline and
  confirming the glyphs are Space Grotesk rather than `system-ui`.** Reason for deferral: jsdom
  does not load fonts, does not apply `@font-face`, and reports whatever family string it was
  handed — a `getComputedStyle` assertion here would pass on a corrupt font, a missing font and
  a 404 alike, which is worse than no assertion. Same precedent as c2-2's AC 17. (Severity: Low
  — every mechanical signal is green; this is the eyes-on-glyphs confirmation. Worth checking in
  the same pass: that no flash of fallback text is visible on load, which is what `font-display:
  swap` plus the `index.html` preload is for.)

- **The numeric-pairing guard cannot see the cascade.** `findUnpairedNumericRole` fails a rule
  block that applies `font: var(--type-numeric)` without
  `font-variant-numeric: var(--type-numeric-features)` in the SAME block. What it cannot see is a
  correct pair undone by a later rule. *(Review round 2026-07-28 narrowed this: the literal
  spelling — `.is-compact { font-variant-numeric: normal; }` — is now caught by stylelint, whose
  `font-variant-numeric` entry admits only the token; the spelling that remains invisible is a
  later block applying a different role — `.is-compact { font: var(--type-micro); }` — where
  every declaration is legal and the `font` shorthand resets `font-variant-numeric` as a side
  effect.)* Resolving that needs specificity, source order and the element's real class list,
  which live in TSX and are chosen at runtime. **Review owns that half.** Documented at the
  guard, in `ui/README.md`, and asserted as a deliberate blind spot so it fails loudly if the
  guard ever grows a cross-block reader.

  **Updated 2026-07-29 (story c2-7): the blind spot now has real consumers.** The role is
  applied by `.panel-count`, `.group-header-count` and `.stat-chip-delta`, and the label/micro
  companion guard added in the same story (`findRoleWithoutCompanions`) inherits the identical
  block-local limit — its own cascade case is a later `font` shorthand in another rule, which
  is asserted as a declared blind spot beside it. Reviewing a story that composes these
  primitives means checking the composed class list rather than assuming the gate did.
  (Severity: Low → **Low-Med** — three components apply the role now, and every later story
  that stacks a modifier class onto one of them is in the guard's blind spot.)

- **The offline guard's JS layer is a reviewed-host baseline, and it is deliberately brittle.**
  `.css` and `.html` in the bundle carry a TOTAL ban on external URLs; `.js` cannot, because
  React's DOM code legitimately contains `http://www.w3.org/…` namespace identifiers and a
  `https://react.dev/errors/` string, and a guard that fired on those is one someone switches
  off. So JS is covered by three family rules (font-CDN hosts, fetchable asset extensions) plus a
  snapshot of the reviewed host set. A React or Vite bump that introduces a new URL string will
  turn `tests/fonts.test.ts` red and require a human to add it to `REVIEWED_HOSTS` with a reason.
  That is the intent — under AD-13 a dependency bump already means committing a new bundle — but
  it is a maintenance cost worth naming rather than discovering. A runtime-constructed URL
  (`fetch('htt' + 'ps://…')`) is invisible to all four rules, as it is to every static check.
  (Severity: Low — the thing being prevented is a build-time CDN import, which the total ban on
  `.css`/`.html` covers absolutely.)

## Deferred from: code review of c2-5-self-hosted-space-grotesk (2026-07-28)

- **`git ls-files`-keyed guards cannot see untracked stylesheets.** `shippedStylesheets` in
  `ui/tests/fonts.test.ts` and `ui/tests/token-usage.test.ts` builds its file list from
  `git ls-files '*.css'`, so a not-yet-staged component stylesheet carrying a stray `@font-face`
  or an unpaired numeric role passes the local vitest run and is only caught once staged
  (stylelint's filesystem glob still catches value-level violations). This is the deliberate,
  comment-owned trade-off c2-4 established; if it ever bites, the fix is one sweep appending
  `git ls-files --others --exclude-standard '*.css'` to every such guard at once, not a
  per-story patch. (Severity: Low — the window closes at `git add`, and CI never has it.)

- **`:root { font: var(--type-body) }` pins the document rem basis to 14px and overrides the
  browser's default-font-size preference.** Before c2-5, `:root` set no `font-size`, so `1rem`
  tracked the user's browser setting; now it is 14px document-wide. Latent — nothing in `ui/`
  uses `rem`, and the whole token layer is px-based per DESIGN.md, so user font-size preferences
  were already inert for component text. If an accessibility pass ever revisits px-vs-rem, this
  root declaration is where the document basis is set. (Severity: Low — design-system-level,
  pre-dates this story in effect; the 14px change itself is recorded in the c2-5 Completion
  Notes.)

## Deferred from: implementation of c2-6-the-two-column-application-shell (2026-07-28)

- **AC 4's and AC 5's render halves are Brad's, deferred to the C2 epic manual-testing
  checklist.** This is the third story to split an AC this way (c2-2 AC 17, c2-5 AC 4), so it is
  now a pattern rather than an exception. jsdom has no layout engine — it resolves no grid
  tracks, evaluates no media queries and returns no box geometry — so every geometry assertion
  in this story reads CSS source. What is mechanically pinned by `ui/tests/shell.test.ts`: the
  gutter and panel-gap come from tokens, the right column is exactly `452px`, the breakpoint is
  exactly `1100px` in the context range form, the fluid track is `minmax(0, 1fr)`, and both the
  track and the grid item are floored at zero. What a browser still owes:

  1. Open at **1720px** and compare against the composition reference — header, fluid left
     column, 452px right column, footer, panels floating with visible canvas between them.
  2. Sweep **~1100px → ~2560px**: no horizontal scrollbar at any width, and below 1100px the
     right column drops beneath the left rather than compressing.
  3. On a **long deck**, the footer stays visible without scrolling, and the scrollbar sits at
     the content region's edge rather than the window's — the intended app-shell appearance and
     the accepted consequence of Q2.

  (Severity: Medium — the composition is the story's whole point, and no gate can see it.)

- **The shell's guards are static CSS readers, so the cross-file and runtime halves are
  review's.** `ui/tests/shell.test.ts` decides "is this a full-window fixed layer", "is this a
  root element" and "does this track floor at min-content" by reading declarations in one rule
  block at a time. Invisible to all of them: a full-window layer composed at runtime from two
  classes on one element; a root reached through a class the guard does not recognise as root
  (it knows `html`, `body`, `:root`, `#root`, the universal `*`, functional pseudo-class
  wrappers of those, `.app-shell` in any compound, and `.app-shell-columns` — but not an
  arbitrary class that happens to be styled onto a root element); any `overflow`, `position`
  or grid template set from JavaScript; and `var()` indirection, where the banned keyword
  lives in a custom property declared elsewhere (review round, 2026-07-28 — declared in the
  guard header alongside the runtime half). This is the same division of labour
  `tests/token-usage.test.ts` declares for its contrast and numeric-pairing guards, and it is
  stated in the guard file's own header. When reviewing c6-5's agent view in particular, check
  the composed result rather than assuming the confinement guard did. (Severity: Low — the
  static half covers the shape every story is actually likely to write.)
  **STILL OPEN AT c6-5 (2026-08-10) — this is review guidance, not a task, and c6-5 is the story
  it was aimed at.** The agent view shipped declaring no `position: fixed` and no `z-index` at
  all (the slot owns both; `AgentView.css`'s header records the reading), so the confinement
  guard has nothing to miss on the value level — but that is exactly the claim this entry says a
  static reader cannot settle, and the composed result has been seen by NO human eye: Block J
  (eyes-on-pixels) remains ruled NOT RUN until the C6 manual checklist. Carried into c6-5's PR
  description rather than closed.

- **`z-index: 20` is a geometry literal that the AC 18 documentation guard does not cover.**
  The guard is derived from the code — every `\d+px` literal in every tracked stylesheet under
  `src/components/` must carry a `DESIGN.md` citation within a sentence of it (widened from
  `AppShell.css` alone in the 2026-07-28 review round) — and a bare unitless number cannot be
  told apart from the ones in `minmax(0, 1fr)`, `flex: 1` and `min-width: 0`. The value is documented
  in prose beside its rule (it comes from the composition reference, and UX-DR38 fixes the stack
  at one level deep so there is nothing to order it against), but that documentation is
  review-enforced rather than gate-enforced. If a later story introduces a second stacking
  level, the right repair is a `--z-*` token family, not a wider regex. (Severity: Low — one
  value, one level, and the epic's design says there will never be a second.)

## Deferred from: c2-6 AC 7 amendment (2026-07-28)

- **`DESIGN.md` line 328 still names `{spacing.6}` for the agent-view overlay inset; the shipped
  shell uses `--space-gutter`.** Story c2-6's AC 7 was amended to `var(--space-gutter)` by Brad's
  ruling on 2026-07-28, after review round 1 ruled the implementation that way: the two tokens
  are both 32px today, but the overlay's contract is that its inset **coincides with the shell's
  own frame**, and a later retune of the gutter would silently break that alignment while every
  assertion kept passing. The epic's Story 2.6 block and UX-DR8 both say plain "32px" and needed
  no change; DESIGN.md is the only artefact still naming the scale step.

  ~~Left alone deliberately — DESIGN.md is the UX artefact, not an implementation record, and
  nothing renders differently since both values are 32px. **Homed against Story 8.3**, which
  already owns folding implementation-surfaced corrections back into the planning artefacts (it
  carries the six spine gaps and the EXPERIENCE.md "unconfirmed" stamps). The fix is one word,
  and the reason to make it is that the next component to reach for a "window frame" distance
  should find one name, not two.~~ **CLOSED by story 15-3, 2026-08-18** (Story 8.3 was renumbered
  15-3). **Three** sites, not the one the entry named and not the two the first pass found (review
  2026-08-18): the frontmatter token `components.agent-view.inset` is now `'{spacing.gutter}'` with
  the reasoning beside it; the `empty-push-line.container` comment 120 lines below it, which cites
  the shell's token in passing, was corrected with it — a comment left naming the old token is the
  same two-names-for-one-distance trap in miniature; and the Layout & Spacing prose reads *"inset by `{spacing.gutter}` — the same token that frames the
  window, because the overlay's inset must coincide with the shell's own frame rather than merely
  equal it today"*. The shipped `var(--space-gutter)` is unchanged and nothing renders differently;
  what changed is that there is now one name for the distance. No test read either site (verified:
  `ui/tests/tokens.test.ts` derives its inventory from the `colors`/`rounded`/`spacing` blocks and
  hand-lists only the composite shadows, and nothing reads
  `design.components['agent-view']`). (Severity: Low — cosmetic today, a real trap only if the
  gutter is ever retuned.) Two `ui/tests` comments describing DESIGN.md as "the one artefact
  still saying `{spacing.6}`" were updated in the same commit; three `ui/src` comments quoting the
  old wording were not, and are recorded as residue under story 15-3 below.

## Deferred from: c2-7 — presentation-only primitives (2026-07-29)

- **The four primitives' APPEARANCE is not dev-verified, and cannot be in this story.** `Panel`,
  `Badge`, `StatChip` and `GroupHeader` ship with **no on-screen consumer** — nothing imports
  them, deliberately (AC 24: the header badge slot stays empty and keeps naming c4-2/c4-10 as
  its fillers). jsdom applies no stylesheet and has no layout engine, so every visual claim in
  the story — the overlay level being one step up the ramp, `--shadow-rest` against
  `--shadow-raise`, the live dot's `var(--glow)`, and above all **whether the pseudo-element
  tone wash actually renders behind the badge's text rather than over it** — is read from CSS
  source or not at all. A `getComputedStyle` assertion here would return the empty string and
  pass for the wrong reason; this is the fourth story to split an AC this way (c2-2 AC 17, c2-5
  AC 4, c2-6 AC 4/5) and faking it was explicitly declined.

  **Homed at each primitive's first consuming story**, which is where a real screen can show it:
  `Panel` **RE-HOMED by c2-9 to c4-5** (card detail, the first real `level="overlay"` panel) and
  **c4-7** (the deck list) — this entry assumed the state panel would *be* a `Panel`, and Q6
  ruled that it is not: `DESIGN.md` declares a separate `components.state-panel.*` block, and the
  two differ where it matters (a Panel's title is `--type-label`, 11px uppercase tracked; a state
  panel's headline is `--type-heading`, 17px sentence case). Rendering one through the other
  would have meant threading a second title role through `Panel`, which is how a primitive stops
  being one. So `Panel` still has no on-screen consumer. `GroupHeader` at **c4-7** (the deck list),
  `Badge` at **c4-10** (the format check) and **c4-2** (the header badges), `StatChip` at the
  first surface that carries one. Carried on the **epic manual-testing checklist** as well, so
  it is not only findable from this file. (Severity: **Medium** — the wash's stacking behaviour
  is the one mechanism in the story with no static proof available, and the failure mode is a
  solid blank pill with invisible text, which reads as a content bug rather than a CSS one.
  Check it first.)

  **Extended by the 2026-07-29 review: the tone-over-wash CONTRAST is also unmeasured.**
  UX-DR6's table covers `--accent-dim` on `--surface-overlay` only; nobody has measured
  `--accent-bright` over a 12% `--accent` wash, nor positive/negative/caution text over their
  own washes, on any surface or under the four alternate themes. `Badge.css`'s accent comment
  now says so plainly instead of asserting the floors are cleared. Same home, same first
  consumers: eyeball the wash's stacking AND run the contrast numbers at c4-2 / c4-10.

- **`findRoleWithoutCompanions` derives its uppercase half by reading `DESIGN.md` from a second
  test file.** `tests/tokens.test.ts` already calls its copy of that path "the ONE place this
  path is written"; `tests/token-usage.test.ts` now writes it too, because no token NAME encodes
  case the way `--tracking-X` encodes tracking, and reading the contract beat hand-typing "label
  and micro". Both copies carry a loud anchor that turns a stale path into a named failure
  rather than a guard asserting nothing over an empty map, and `tests/package-contract.test.ts`
  pins the exhaustive list of `yaml` importers so a third one cannot appear quietly. The clean
  repair is a shared `tests/design-contract.ts` exporting the path and the parsed frontmatter,
  which was declined here as out of scope for a story that ships components. (Severity: Low —
  two copies, both anchored, and the UX artefacts are re-exported rarely.)

## Deferred from: code review of c2-7 (2026-07-29)

- **StatChip `signed()` renders raw `String(delta)`** — a fractional delta shows
  `+0.30000000000000004` and a magnitude ≥ 1e21 shows `+1e+21` as user-facing text
  (`ui/src/components/StatChip/StatChip.tsx:45`). Q6 already homes delta *formatting* at the
  first consuming story; that entry now also covers fractional and huge numbers — the consumer
  either formats before passing or adds the sibling formatted-delta prop Q6 anticipated.
  (Severity: Low — no current caller passes a non-integer delta.)

## Deferred from: c2-8 — ManaPip / ManaCost and the Scryfall cost parser (2026-07-29)

- **`ManaPip` and `ManaCost` APPEARANCE is not dev-verified, and cannot be in this story.**
  Both ship with **no on-screen consumer** — nothing imports them, deliberately (AC 24:
  `AppShell.tsx` is untouched) — and jsdom applies no stylesheet and has no layout engine. So
  every visual claim in the story is read from CSS **source** or not at all: the pip being a
  **circle** at all (`min-width: 1.25em` + `height: 1.25em` + `--radius-pill`), the **hard-stop
  two-colour gradient** on the fifteen hybrid classes actually reading as a split rather than a
  blur, the 13px numeric glyph sitting **legibly** in a 16.25px circle (a 0.8 glyph-to-pip ratio,
  tighter than the mock's 0.62 — this is the value most likely to want a nudge), the **wide
  case** (`{1000000}`, `{HW}`) growing into a pill instead of clipping, and the **row wrapping**
  when fifteen B.F.M. pips meet the 452px right column. A `getComputedStyle` assertion here
  would return the empty string and pass for the wrong reason; this is the **fifth** story to
  split an AC this way (c2-2 AC 17, c2-5 AC 4, c2-6 AC 4/5, c2-7 AC 21) and faking it was
  explicitly declined.

  **Homed at the first consuming stories**, which are where a real screen can show it: **c4-3**
  (card placeholders — the first render of a cost anywhere), **c4-7** (deck rows, the densest
  use and the one where the wrap matters), **c4-9** (the colour-distribution legend, which is
  also where the optional `label` prop gets its first caller). Carried on the **epic
  manual-testing checklist** as well, so it is not only findable from this file. (Severity:
  **Medium** — the glyph-to-pip ratio and the gradient's hard stop are the two values with no
  static proof available, and both fail *legibly-but-wrongly* rather than loudly. Check the
  `{1000000}` and `{W/U}` cases first.)

  > **RESOLVED at c4-3 (2026-08-04). All five claims hold; nothing needed a nudge.** Paid on a
  > throwaway harness — the BUILT stylesheet served to Edge against hand-written markup, the same
  > instrument c4-2 used for `Badge` — and screenshotted at 6x. **The pip is a circle.** **The
  > hybrid gradient's hard stop reads as a clean 45 degree split with no blur.** **The 13px glyph
  > sits centred and legible in the 16.25px circle** at the 0.8 ratio this entry flagged as most
  > likely to want a nudge — `0 2 X T P S` all checked, none crowded. **The wide case GROWS into a
  > pill rather than clipping** (`{1000000}`, `{HW}`, `{100}`). **Row wrapping works**: fifteen
  > B.F.M. pips wrap to a second row inside a **176px** card — narrower than the 452px column this
  > entry worried about, so the harder case was the one measured. The two named-first cases
  > (`{1000000}`, `{W/U}`) were checked first, as instructed. **c4-7 and c4-9 inherit nothing from
  > this entry**; what remains for them is composition, which a harness cannot show.

- **The `--mana-*` data-ink rule's "unstacked curve bar" half is REVIEW'S, not the gate's.**
  UX-DR7 bans a WUBRG token on "an unstacked curve bar", and whether a given bar is genuinely
  stacked is a property of the data bound to it and the elements composed at runtime — both in
  TSX, neither in CSS. The guard says so in its own comment (the same division of labour
  `surfaces.ts`'s `stepsExactlyOne()` declares), and `ui/README.md` says so where c4-8's author
  will be reading. **c4-8's reviewer must look**; the gate will not have looked for them.
  (Severity: Low — one story owns it, and it is named in three places.)

- **The ` // ` split-card separator is spoken as the literal characters.** `describeManaCost`
  renders `{2}{B} // {B}` as _"2 generic, black // black"_, so a screen reader says "slash
  slash". A friendlier reading ("or", "split with") was declined as an invention — nothing in
  DESIGN.md, EXPERIENCE.md or the epic rules on it, and guessing would put unsourced words in a
  user's ear. Homed at **c4-3/c4-7**, where a split card first renders and the phrasing can be
  decided against something real. (Severity: Low — 338 of 32,318 costs, and the literal reading
  is honest rather than wrong.)

  > **c4-3 disposition (2026-08-04): CONFIRMED LIVE, RE-HOMED to c4-7 unchanged.** A split card
  > does now render here — `Heaven // Earth` is a fixture in `CardPlaceholder.test.tsx`, and its
  > cost `{X}{G} // {X}{R}{R}` renders five pips and the literal ` // ` text run. So the entry's
  > condition ("where a split card first renders") is met and the reading was heard against
  > something real. **The phrasing is unchanged, deliberately**: the placeholder is a fallback
  > slot, not a reading surface, and c4-3 also sharpened the population — **all 79** cards that
  > permanently need the named placeholder are split-named, but **all 79 have a BLANK mana cost**,
  > so `describeManaCost` is never called for them and the separator is never spoken on this
  > surface at all. The decision belongs where a cost is read aloud in prose: **c4-7's deck rows**.

- **For sighted colour-vision-deficient users, a pip's colour IS its sole carrier** (added at
  c2-8's code review). A `{W}` pip and a `{G}` pip differ in nothing but fill — no letter, no
  pattern — so the `role="img"` accessible name serves AT users while a sighted CVD user cannot
  read any cost. DESIGN.md's ruled shape ("a plain circle filled with the mana token") compels
  this, and UX-DR7's no-lookalikes rule closes the obvious escape of drawing symbols; the entry
  exists so the trade-off is a **decision on record, not an omission**. Homed at the **c4-3
  eye-check** with the other visual claims: if the plain circles read as indistinguishable in
  practice, the available levers are a glyph-slot letter (the mechanism Phyrexian already uses,
  and plain text is not a lookalike) or a DESIGN.md amendment — Brad's call, made against a real
  screen. (Severity: **Medium** — an accessibility gap for a real user class, but one the design
  contract currently mandates.)

  > **c4-3 disposition (2026-08-04): MEASURED, and the levers are NOT needed — pending Brad's
  > acceptance against a real screen, which this entry reserves to him.** The six shipped
  > `--mana-*` colours were pushed through the Machado severity-1.0 dichromacy matrices in linear
  > RGB and compared pairwise as CIE Lab dE. Worst pair per vision type: **normal B/C 24.5**,
  > **protanopia U/B 10.0**, **deuteranopia R/G 14.1**, **tritanopia B/C 10.9**. Every pair stays
  > above dE 10 under every simulated deficiency — roughly 4x the just-noticeable difference for
  > large flat patches — so the plain circles do NOT read as indistinguishable and neither lever
  > (a glyph-slot letter, a DESIGN.md amendment) is called for. **Two limits, stated rather than
  > glossed:** a simulation is not a person, and this measures *distinguishability* (telling two
  > pips apart) rather than *identifiability* (knowing WHICH colour a pip is) — the latter stays a
  > real gap for a sighted CVD reader that only a glyph would close, and it is the gap the
  > `role="img"` name closes for AT users. **Stays OPEN at Medium until Brad accepts the numbers;
  > it is no longer waiting on an eye-check that has not happened.**

- **`{Y}`, `{Z}`, `{S}`, `{L}`, `{D}` and `{HW}` are deliberately NOT in the parser's symbol
  table.** Each is real in the shipped database and each renders correctly today — as a
  colourless pip showing its own letter, which is exactly what the totality contract promises
  and what AC 3 requires. Adding them as recognised families would buy a *colour* for snow and
  a *name* for the un-set symbols, and neither has a DESIGN.md or epic ruling to source it
  from. Revisit only if a consuming story shows one of them reading badly. (Severity: Low — the
  current behaviour is correct, not a gap; this entry exists so a later author knows the
  omission was a decision.)

## Story c2-9 — the shared state panel and every system-state message

- **The state panel's appearance is dev-verified for the first time in this epic, and only
  partly.** `App.tsx` renders the no-active-deck panel into the shell's `left` slot (Q1), so
  unlike c2-7 and c2-8 there IS a screen. What that screen proves is what a browser draws; what
  it does not prove is everything jsdom is blind to *in the test suite*, which is the same list
  as ever: **centring, the 480px measure, the hairline border, the large radius, the chip's
  recessed `--surface-well` material and its mono family, and the accent colour and weight of
  the next-action line.** jsdom applies no stylesheet and has no layout engine, so there is no
  `getComputedStyle` assertion in `StatePanel.test.tsx` — one would report the defaults back and
  pass over a stylesheet that was never linked. This is the **sixth** story to split an AC this
  way (c2-2 AC 17, c2-5 AC 4, c2-6 AC 4/5, c2-7 AC 21, c2-8 AC 21) and faking it was again
  declined. What IS statically proven: the token families spent (an allowlist guard), the
  absence of `--negative`/`--caution`, the absence of `transition`/`animation`, and the
  DESIGN.md citation beside the one px literal. **On the epic manual-testing checklist.**
  (Severity: Low — every claim has a static half; the visual half is a first-look, not a risk.)

- **The five states nobody can see yet.** Only `no-active-deck` is on screen, because it is the
  only one that is TRUE with no fetch layer. `database-not-initialized`, `database-updating`,
  `database-updating-stalled`, `disconnected` and `internal-error` render correctly in the test
  suite and have never been looked at in a browser — in particular the **command chip**, which
  only appears in three of them, and the **two-paragraph** guidance/action stack, which
  `no-active-deck` does not exercise (it has no guidance). Homed at **c3-9**, which wires the
  states and is the first story able to show them. **PARTLY CLOSED, c3-9 (2026-08-02).** Four of
  the five are now REACHABLE in the running app — `database-not-initialized`, `database-updating`,
  `database-updating-stalled` and `internal-error` are each selected by the poll from a wire
  token, and the first is what a genuine fresh install shows (confirmed live at the HTTP layer).
  `disconnected` stays **c5-6's** and is selected by nothing, per Q10. **The browser look-at was
  NOT performed**: this environment has no browser automation installed and adding one would be a
  new dependency, so the VISUAL half is unchanged and moves to the epic manual-testing checklist
  with a recipe — run `PLANESWALKER_DATA_DIR=<empty dir> uv run artificial-planeswalker
  companion` and open the printed URL for `database-not-initialized`, then hand-edit `App.tsx`'s
  `left` prop to a literal `<StatePanel state="..." />` for each of the other four. What to look
  at is unchanged: the **command chip** (three states have one) and the **two-paragraph
  guidance/action stack**. (Severity: Low.)

- ~~**`states.ts` has no runtime consumer.**~~ **CLOSED, c3-9 (2026-08-02).**
  `PANEL_FOR_REASON` is consumed by `ui/src/state/panel.ts` — which also uses its KEY SET as the
  runtime membership test for `ErrorReason`, so there is still no second list anywhere — and
  `RETRIES_QUIETLY` by `ui/src/state/poller.ts`, indexed at runtime rather than paraphrased
  (probe (b) replaces the consult with "always retry" and five assertions go red).
  `CLIENT_ONLY_STATES` stays a declaration and that is correct: `disconnected` is **c5-6's**, and
  `database-updating-stalled` is produced by elapsed time on the client rather than selected from
  a list. The original entry, for the record: `PANEL_FOR_REASON`, `CLIENT_ONLY_STATES` and
  `RETRIES_QUIETLY` are total maps written for **c3-9** to read; nothing imports them today, so
  they are tree-shaken out of the bundle. This is deliberate — the alternative was leaving the
  wire-token→panel mapping and the retry contract as prose in a story record, which is where
  `internal_error` was left in c1-4 and what cost this story an AC to repair. Their correctness
  is proven by `npm run typecheck` (a seventh `ErrorReason` fails to compile), not by `npm test`.
  (Severity: Low — a declaration with a named owner and a compile-time gate.)

- **`--font-mono` has exactly one consumer and one job.** The command chip. If a later story
  reaches for it anywhere else, that is a UX-DR2 conversation (hierarchy never comes from a
  second family), not a free reuse — the whole argument for admitting the token was that a
  command literal is *data* the user retypes. No guard enforces the scope today; it is stated in
  `tokens.css`, in `DESIGN.md`'s Typography section and here. (Severity: Low.)

- **The copy guard cannot decide the half that matters most.** Whether a sentence is
  second-person, blameless and gives a concrete next action is not statically decidable, and it
  is the substance of UX-DR33. Declared in `tests/copy-rules.test.ts`'s own header alongside two
  narrower residues: copy assembled from single words at runtime (`describeManaCost`), and a
  string reaching `aria-label` through an expression rather than a literal. **Review owns all
  three** — the same division of labour `surfaces.ts` and `findAccentDimOnOverlay` declare for
  theirs. A reviewer of c2-10, c4-3, c4-12 and c6-6 must READ the copy. (Severity: Low, but
  permanent — this does not get closed, it gets honoured.)

## Deferred from: code review of c2-9 (2026-07-29)

- **A runtime-unknown `state` key crashes the StatePanel.** `STATE_COPY[state]` at
  `StatePanel.tsx:92` has no fallback branch: a value arriving through untyped wiring (a stale
  enum, a JS caller, a mis-parsed wire token) yields `undefined` and `copy.headline` throws — an
  unhandled render exception, which is the error screen the story exists to ban. TypeScript
  guards it today and no runtime caller exists (`App.tsx` passes a literal). ~~**c3-9 owns
  runtime validation of wire values before they reach this prop.**~~ **CLOSED, c3-9 (Q5,
  2026-08-02).** `ui/src/state/panel.ts`'s `panelFor` is the one place a wire value becomes a
  `StateKey`: total by construction over every string and over `null`, clamping to
  `internal-error`. `StatePanel` gained **no** fallback branch and stays presentation-only. Three
  inputs reach the clamp — a token this build does not know, a token `states.ts` maps to `null`
  (`invalid_request` and `payload_too_large` are both DECLARED on `GET /api/decks`, so this is
  reachable rather than theoretical), and no token at all. Also closed here, and not in the
  original entry: indexing a plain object with `__proto__` or `constructor` returns an INHERITED
  value rather than `undefined`, which a bare `?? 'internal-error'` would have passed through to
  the prop as an object; `Object.hasOwn` is what stops it and it is asserted.
  **Two corrections to this entry's own text, both measured at c3-9.** The line is
  `StatePanel.tsx:104`, not `:92`. And the throw is one line EARLIER than described: probe (d)
  removes the clamp and the crash is `TypeError: Cannot read properties of undefined (reading
  'body')` from `guidanceOf(copy)`, not from `copy.headline`.
  (Severity: Low today; Medium once wiring exists.)

- **The un-quoted tails of EXPERIENCE.md's copy rows are contract nobody gates.** The verbatim
  gate captures `Headline:` and `Body:` only; the no-active-deck row's deck-list clause and both
  retry clauses ("Deterministic: this state never retries itself", the stalled row's threshold
  note) live outside the captures and can be edited or deleted with every gate green while their
  TypeScript mirrors (`RETRIES_QUIETLY`, the `decks` prop) drift undetected. ~~Extending the gate
  is new scope; candidate home is **c3-9**, beside the wiring those clauses constrain.~~
  **CLOSED, c3-9 (Q6, 2026-08-02).** `ui/tests/copy-tails.test.ts` gates the three tails that
  constrain c3-9, each against its TypeScript mirror in BOTH directions: the no-active-deck
  deck-list clause against `DECKS_PATH`, the stalled row's *"the client decides when 'a while' has
  passed (c3-9 owns the threshold)"* against `STALLED_AFTER_MS` and
  `RETRIES_QUIETLY['database-updating-stalled']`, and the internal-error row's *"Deterministic:
  this state never retries itself"* against `RETRIES_QUIETLY['internal-error']`. Deleting a clause
  fails the gate; flipping a mirror fails the gate. A NEW FILE rather than an edit to
  `copy.test.ts`, so that suite's "passes unchanged" prediction stays literally checkable, and the
  mirrors are read out of SOURCE rather than imported — see the file header for the twelve `tsc`
  errors the import version produced, which is `ui/README.md`'s cross-project-import blind-spot
  row earning its place. **The fourth tail — the disconnected row's connection-pill note — is
  DECLINED and re-homed on c5-6 by name**, which owns the pill, its backoff and the state; there
  is nothing in this repository for it to be checked against today, so a gate on it would assert
  prose against prose. (Severity: Low.)

## Deferred from: story c2-10 (footer attribution, 2026-07-30)

Every entry here is a **visual claim jsdom cannot decide** (AC 22). The source-read half of each
is asserted in `ui/tests/shell.test.ts` against `Footer.css`; what is deferred is only what the
CSS *does on screen*. None of these is claimed anywhere as verified.

- **10px ALL-CAPS legal text — is it actually readable?** THIS IS THE FIRST THING TO LOOK AT.
  `DESIGN.md` assigns footer attribution to `{typography.micro}` (`400 10px/1.3`, `0.08em`
  tracking) and declares that role uppercase, and the companion guard derives the requirement
  from the artefact's own `textTransform:` key — so three sentences of legally load-bearing text
  render at 10px in capitals. Brad ruled **ship the spec as written** (Q1, 2026-07-30): it is
  what the artefact says, the DOM text is untouched by `text-transform` so nothing about the
  contract or the screen reader changes, and deviating means amending a UX artefact on a
  frontend story. The contrast AC exists because this text must be readable — and case and size
  are the other two halves of readability, which no AC covers. **If it reads badly by eye, the
  correction is a `DESIGN.md` amendment in Epic 8's release-readiness pass**, made with the
  rendered page in hand rather than from the spec. (Severity: Medium — it is the one string in
  the app that has to be readable.)

- **The 24px hit box as laid out.** `min-height: 24px` + `min-width: 24px` with
  `display: inline-block` is asserted in source (the review of 2026-07-30 changed the display
  from `inline-flex` — see the underline entry below — and added the width axis), and the
  display mode is asserted beside the minimums because they do nothing on a plain inline box —
  but jsdom has no layout engine, so the *measured* box of each link is unverified. Worth a
  specific look: an `inline-block` box 24px tall inside a 13px line box will grow that line, so
  the two footer link runs may sit on a visibly taller line than the plain text around them, and
  the box extends below the baseline rather than centring the text the way the flex version
  would have. Check with a devtools box inspection, not by eye alone. (Severity: Low.)

- **The persistent underline and the hover brightening — NOW FIRST ON THE CHECKLIST, above the
  10px readability question.** The code review of 2026-07-30 found `display: inline-flex` was
  plausibly rendering AC 5's release-condition underline as *no underline at all* — text
  decoration does not propagate into flex items — and every automated gate reads source, so
  nothing could see it. The fix is `display: inline-block`, under which the decoration applies
  to the link's own text; **the browser check is the proof the fix needs**, since the failure
  mode is exactly "true in source, false on screen". `text-decoration: underline` at rest and
  `color: var(--text-primary)` on `:hover` *and* `:focus-visible` (the review added the focus
  half) are read from source, and the guard proves no hover rule introduces the decoration
  (UX-DR47). Also still unverified by any gate: that the underline is *visible* at 10px against
  `--text-secondary`, and that the rest→hover step reads as a brightening rather than as a
  flicker. (Severity: Medium until the eye check — it is the release-condition affordance.)

- **The focus ring's appearance.** These are the **first focusable elements in the codebase**,
  so this is the first time `--focus-ring` / `--focus-ring-width` / `--focus-ring-offset` have
  ever been rendered — they shipped in c2-1 with nothing to point at. `outline` was chosen over
  `box-shadow` so an ancestor's overflow cannot clip it, but whether a 2px ring at 2px offset is
  clearly visible around a 24px inline-flex box at the very bottom edge of the window is a
  browser check. **Tab to both links.** (Severity: Medium — it is the token layer's focus
  contract getting its first real exercise, and c4-11 inherits whatever is learned here.)

  📐 **c4-11 (2026-08-07) supplies the NUMBER this entry never had, which is the half no browser
  check was needed for** — `c4-6:1155-1157` left it as an open composite question and no figure
  existed anywhere. Computed by WCAG 2.x relative luminance against `--focus-ring` `#b3baff`:
  **`--surface-well` 10.35:1 · `--surface-base` 9.94:1 · `--surface-panel` 9.16:1 ·
  `--surface-overlay` 8.11:1** — every authored surface clears 1.4.11's 3:1 non-text floor by more
  than 2.5×. **Against white card art it is 1.84:1, and against mid-grey art 2.14:1 — both FAIL.**
  That measurement **proves the design rather than questioning it**: it is precisely why
  `--shadow-focus-ring-over-art` exists, because the composite's outer `--surface-base` band
  measures **9.94:1 against the ring and 18.33:1 against white art**, so what carries 1.4.11 over a
  painting is the *adjacent-pair* contrast, not the ring against the art.

  **The rendered half is the eye-check's and it is discharged there** (c4-11 Task 7): whether the
  ring is legible around the footer links at the very bottom edge of the window, and whether the
  over-art band is ACTUALLY PAINTED — because if it is ever dropped, the indicator silently fails
  on every light card face and no jsdom test in this repo can see it.

- **The border and the surface.** `border-top: 1px solid var(--border-hairline)` over
  `background: var(--surface-base)` is `DESIGN.md`'s frontmatter verbatim. Note that the
  background is the same token as the page canvas, so the *only* visible separation is the
  hairline — and the footer sits inside the shell's `var(--space-gutter)` padding, so the rule
  spans the content width rather than bleeding to the window edge. That is the shell's existing
  layout decision (c2-6), not this story's; if the full-bleed rule DESIGN.md's "full width"
  implies is wanted, it is a shell change and belongs to whoever owns that, not to a footer
  story. (Severity: Low — a deliberate reading, recorded so it is a decision and not a drift.)
  **RATIFIED (Brad, 2026-07-30, c2-10 code review): the content-width reading stands** — the
  hairline aligns with the header and columns inside the gutter frame. No longer a unilateral
  call; a full-bleed rule would now be a new decision, not a correction.

## Deferred from: story c3-1 (deck list and deck detail endpoints, 2026-07-31)

- **`list_decks` materialises every deck's full card list just to count it.**
  `src/data/repositories/deck.py:263` eager-loads
  `selectinload(DeckModel.deck_cards).selectinload(DeckCardModel.card)`, so `GET /api/decks`
  loads the whole corpus of every saved deck and then discards it down to three integers per
  deck. **Accepted here, not fixed**: it is existing `src/data` behaviour that the `list_decks`
  MCP tool already pays, the deck count is single digits on a real machine, and NFR-05's budget
  is the deck *view*, not the deck list. Adding a count-only query in c3-1 would have been a
  second read path over one shape, which is exactly what AD-1 exists to prevent.
  **Home: 17-3** (latency hardening). If it is fixed there, the fix belongs in the repository —
  an aggregate query behind the same method — so both shells inherit it. (Severity: Low now;
  scales with deck count and deck size.)

- **`DeckRepository.list_decks` ties on `created_at` and falls back to UUID order.**
  Re-confirmed still open at c3-1. `deck.py:262` orders by `created_at DESC, id`; `id` is a UUID,
  so decks created within the same clock tick come back in effectively random order.
  `tests/integration/data/test_deck_repository.py::test_list_decks_with_strategy_field` is
  order-flaky for exactly this reason and is ledgered twice already (c1-5 and c2-1 entries) —
  this is the third confirmation, not a new finding. c3-1 did **not** fix it: it is a `src/data`
  change with MCP blast radius. What c3-1 did instead is make the endpoint's own contract honest
  — `read_decks`' docstring says a tie is arbitrary, and `test_routes_decks.py` asserts ordering
  only against seeds whose `created_at` is genuinely distinct. **Home: unowned, ledgered.** Any
  UI that promises "newest first" to a user (c4-7's deck-list panel) is the first story that
  actually needs this fixed. (Severity: Low.)

  **FOURTH confirmation, c3-2 (2026-07-31), and it FIRED.** `test_list_decks_with_strategy_field`
  failed once in a full-suite run (`assert 'Control' is None` — the three same-tick decks came back
  in UUID order) and passed 56/56 in isolation immediately after, and green on the re-run. Nothing
  in c3-2 touches `DeckRepository`, deck seeding or that test; what c3-2 changed is that the suite
  is ~50 tests longer, which shifts the timing that decides whether the three `create_deck` calls
  land in one clock tick. **This is now the only test in the repo that fails for reasons unrelated
  to the code under change, and it has cost four stories a diagnosis each.** The fix is two lines
  (distinct `created_at` values in the test, or a deterministic tie-breaker in the repository) and
  is being deferred purely on `src/data`-blast-radius grounds — but the cost of the deferral is now
  larger than the fix. Recommend closing it in the next story that touches `src/data`, or as a
  standalone chore. (Severity: raised to **Medium** — a flaky gate teaches people to re-run.)

  **It fired a SECOND time during the same story**, in the post-review full-suite run (a different
  deck id, same `assert 'Control' is None`). Two failures in one afternoon, both on a branch that
  touches no deck code. That is no longer "intermittent under full-suite timing" — at ~1,890 tests
  the three `create_deck` calls land in one clock tick often enough to be a routine occurrence, and
  every future story now inherits a suite that goes red for reasons unrelated to its diff. **Raised
  to Medium-High, and recommended as the next standalone chore rather than waiting for a story that
  happens to touch `src/data`.** Fix: `.order_by(DeckModel.created_at.desc(), DeckModel.id)` is
  already the repository's order — the test is what needs distinct `created_at` values, exactly as
  `test_routes_decks.py::test_orders_newest_first_when_the_timestamps_differ` does it.

- **`GET /api/decks` and `GET /api/deck/{id}` have never been called by a browser.**
  c3-1 ships no frontend (AC 18), so both endpoints are proven only through `httpx.ASGITransport`
  in-process. Not yet exercised: a real `fetch` from the served SPA origin through the security
  envelope, the Vite dev proxy path (`changeOrigin`, c2-1), and CORS behaviour under a real
  browser preflight. Nothing suggests a problem — the envelope is gated and `/health` already
  crosses it — but "a real browser has fetched this" is not yet true of any companion route.
  **Home: c4-2** (the deck bootstrap, the first real consumer). Worth Brad's eye on the C3
  manual-testing checklist: open the companion and hit `/api/decks` in the browser address bar.
  (Severity: Low.)

- **The `openapi.json` byte-comparison gate cannot see *meaning*.**
  `tests/unit/companion/test_openapi_contract.py` asserts that Python internals (`Args:`,
  `Attributes:`, `>>> `) never cross the wire, and c3-1 confirmed that is where it stops: the four
  schemas it exposed carried MCP-internal prose ("keeping `load_deck` payloads small for LLM
  clients", "Build via the helper's explicit constructor, not `model_validate`", "the Story 1.6
  deck-analysis tools") straight into `types.d.ts` and `/docs`, and **Sphinx role markup**
  (`` :class:`DeckSummary` ``) did too — a family the gate's list does not name and which appears
  in neither already-shipped description. c3-1 fixed its own four by rewriting the leading summary
  and pushing the Python detail below `Attributes:`, and recorded the scan it used. It did **not**
  add a gate. Whether one is worth building (ban the role-markup family; the prose half is not
  statically decidable, like UX-DR33's second-person half) is open. **Home: c3-2**, the next story
  to add a schema to `components.schemas` — it will face the same question with `Card`.
  (Severity: Low — cosmetic on the wire, but it is documentation the UI author reads.)

  **RESOLVED (partly) at c3-2, 2026-07-31 — Q5's split ruling.** The statically decidable half
  shipped: `test_openapi_contract.py` gained `PYTHON_INTERNAL_FAMILIES`, keyed on three shapes
  (Sphinx role markup `:[a-z]+:` before a backtick; any line-anchored Google-style section header,
  with `Note:`/`Warning:` as a declared two-member allowlist rather than the old twelve-member ban
  list; a doctest prompt) plus a non-vacuity test proving each family fires. It catches what
  c3-1 found by hand and what the three-member `PYTHON_INTERNALS` never could. **The prose half is
  re-homed to REVIEW, not dropped**: whether a structurally clean sentence actually addresses a
  TypeScript reader ("Supports conversion from SQLAlchemy CardModel instances" trips nothing) is
  not statically decidable, and now carries a `ui/README.md` blind-spot row saying so.

## Deferred from: code review of c3-1 (2026-07-31)

- **A `pydantic.ValidationError` escaping `DeckRepository` has no handler anywhere in the companion
  stack, and `GET /api/decks` gives it a whole-list blast radius.** `install_error_handling` types
  `CompanionError`, `RequestValidationError`, `DatabaseError` and `HTTPException`; a
  `ValidationError` raised inside `Deck.model_validate` matches none of them and lands in
  `UnhandledErrorMiddleware` as `500 internal_error`. Measured triggers, all live: an orphaned
  `deck_cards` row (FK enforcement is OFF, so `dc.card` is `None`), a stored `quantity` of `0` or
  negative (`DeckCard.validate_quantity` rejects `<1` on **read**, and only the repository *write*
  path enforces it), and `tags`/`color_identity` holding well-formed JSON whose elements are not
  strings (`[1,2]`, `["W",null]`). On the detail route the deck is permanently unopenable; on the
  **list** route one bad row in one deck makes *every* deck unreachable.
  **Pre-existing, not introduced here** — this is the same crash already ledgered as the
  `data-layer-orphan-handling` backlog item (epic-7 retro action item 3), which names
  `get_deck_with_cards` and the four MCP tools that share it. c3-1 adds a web surface to it and one
  new fact: the list-route blast radius. **Not fixed here** because AC 12 forbids error-handling
  ceremony in a route body and the fix belongs at the data layer for both shells at once.
  **Home: `data-layer-orphan-handling`** (already in `sprint-status.yaml`, status `backlog`) — this
  entry adds the blast-radius finding and the two non-orphan triggers to its scope.
  (Severity: Medium — needs a corrupted row to fire, but degrades ungracefully when it does.)

- **Both new routes can answer `503 database_not_initialized`, and the OpenAPI document says only
  `database_unavailable`.** `build_app()`'s app-level `error_responses("invalid_request",
  "payload_too_large", "database_unavailable", "internal_error")` never passes
  `database_not_initialized`, so the committed schema's `503` on `/api/decks` and
  `/api/deck/{deck_id}` reads `"description": "reason: database_unavailable"` — while
  `TestDatabaseStates` asserts the *undocumented* token six times. On a fresh install this is the
  **most common** 503 the UI will ever see. `error_responses`' own docstring advertises the
  collapse behaviour ("tokens sharing a status ... a single entry whose description names each of
  them") and it has never fired. **Not fixed unilaterally**: AC 5 explicitly says "do not add
  `database_not_initialized` app-wide as a side effect of this story", and declaring it per-route
  deviates from AC 6's text. **Flagged to Brad as a decision** — see the story's Review section.
  **Home: c3-9** (the fresh-install story, which owns this state end to end) unless ruled sooner.
  (Severity: Medium — the wire contract under-documents the state the UI most needs to switch on.)

  **RE-CONFIRMED at c3-2 (2026-07-31), now on a THIRD route.** `GET /api/cards/{card_id}` answers
  the undocumented token too, asserted twice in `test_routes_cards.py::TestDatabaseStates`, and
  c3-2's AC 6 repeats c3-1's constraint ("`build_app()`'s app-level `responses` is **unchanged**"),
  so it was again not fixed unilaterally. Every data route added from here inherits the gap by
  construction — it is a property of `get_session`, not of any route — so the count will keep
  rising until c3-9 rules on it. ~~Severity stands at Medium.~~
  **RULED AND CLOSED, c3-9 (Q4, 2026-08-02): DECLARE IT.** `build_app()` now passes
  `database_not_initialized` to the database-backed includes (`decks`, `cards`) and to those only.
  Five operations changed in the committed schema — `/api/decks`, `/api/deck/{deck_id}`,
  `/api/deck/{deck_id}/format-check`, `/api/cards/{card_id}`, `/api/card-image/{scryfall_id}` —
  each `503` description going from `"reason: database_unavailable"` to
  `"reason: database_not_initialized | database_unavailable"`. **`error_responses`' documented
  collapse fired for the first time**: both tokens share status 503 and land in ONE entry naming
  each, a behaviour advertised in that helper's docstring since c1-4 and never before exercised.
  `/health` and both active-deck operations are byte-identical and deliberately so — neither can
  answer the token, and widening a declaration a route cannot honour turns an inherited wart into
  a fresh lie. Both artifacts were regenerated together via `npm run gen:api` and never
  hand-edited; the whole-artifact pins live in
  `tests/unit/companion/test_committed_schema.py::TestTheDatabaseTokensAreDeclared`, which also
  pins `/health`'s narrower set and the active-deck routes' absence of any 503 so that "left
  alone" is a decision rather than an oversight.

- **`DeckSummary.from_deck` / `DeckDetail.from_deck` return zero counts, silently, for any `Deck`
  that was not eager-loaded.** `DeckModel.deck_cards` is `lazy="noload"`, so a `Deck` from
  `get_deck`, `find_deck_by_name` or `update_deck` arrives with `deck_cards == []` and the
  projection reports `0 / 0 / 0` with an empty `cards` list — measured: a 4-card deck reads
  `main=4 side=0 distinct=1` via `get_deck_with_cards` and `0 0 0` via `get_deck`. As module-private
  helpers in `deck_management.py` this trap had three known callers; as **public classmethods on a
  shared `src/data` schema** it is now reachable by every future story, and pairing it with the
  cheaper `get_deck()` yields an HTTP 200 describing a 60-card deck as empty. Mitigated here by
  documenting it in both constructors' `Args:` (naming which repository methods are safe), which is
  the honest floor; **the structural fix** is a `Deck`-side marker distinguishing "loaded and empty"
  from "never loaded" — e.g. `deck_cards: list[DeckCard] | None` — so `from_deck` can raise instead
  of guessing. That is a `src/data` schema change with MCP blast radius and needs its own story.
  **Home: unowned, ledgered.** The first consumer to pair a non-eager-loading repository method with
  `from_deck` is the one that needs it. (Severity: Medium — silent wrongness, no type error.)

- **`HEAD` on either new route answers `405 Allow: GET`.** Measured. FastAPI's `@router.get`
  registers `methods=["GET"]` only, and unlike Starlette's static-file handling it does not
  auto-add `HEAD`. RFC 9110 says a server SHOULD support `HEAD` wherever it supports `GET`, and
  `spa.py` already declares `GET, HEAD` for the static surface — so the API routes are the
  inconsistent ones. **Pre-existing convention, not a c3-1 regression**: `/health` uses the same
  decorator and behaves identically, so fixing it here would either leave the two inconsistent or
  silently change a c1-2 route. **Home: unowned, ledgered** — worth one decision covering every
  companion route at once (add `methods=["GET", "HEAD"]` to the routers, or record that the
  companion deliberately serves GET only). (Severity: Low — no known consumer sends HEAD.)

- **`get_session` holds a SQLite SHARED lock for the whole request, and this is the first route
  long enough for it to matter.** `is_database_initialized(session)` autobegins a transaction and
  `get_session` yields without commit or rollback, so the read lock is held from the readiness probe
  through every route query until the `async with` closes. There is no WAL pragma on the companion's
  engine. Combined with the `list_decks` over-fetch above, a `GET /api/decks` over a large
  collection blocks a concurrent `initialize_database` writer — which is exactly the concurrency
  FR-22 presumes ("a database created while the backend runs is picked up with no restart").
  ~~**Home: c3-9** (which owns the fresh-install/coming-alive transition) or **17-3** (latency
  hardening), whichever reaches it first.~~ **MEASURED AND RE-HOMED ON 17-3, c3-9 (Q7,
  2026-08-02)** — a re-home with a number attached, which is worth more than a fix without one.
  Measured against a real running companion serving `GET /api/decks` (~0.16-0.31 s per request,
  the over-fetch above), with a writer taking `BEGIN IMMEDIATE` five times, quiet and then under
  four saturating reader threads:

  | Journal mode | writer QUIET (median / max) | writer CONTENDED (median / max) |
  | --- | --- | --- |
  | `wal` | 0.0097 s / 0.0125 s | **0.0080 s / 0.0092 s** (no effect at all) |
  | `delete` | 0.0079 s / 0.0093 s | 0.0079 s / **0.2131 s** (one read's worth of wait) |

  Three findings, and the second is the one nobody had written down:

  1. **The companion's engine genuinely has no WAL pragma** — `src/data/database.py`'s
     `create_engine` sets only `connect_args={"timeout": 5}`. Confirmed.
  2. **WAL is a PERSISTENT file property, and something else sets it.**
     `src/search/connection.py:136` (the sync `ConnectionFactory`, for sqlite-vec) runs
     `PRAGMA journal_mode=WAL`, so any database this project has built an embedding index over is
     WAL forever and the companion inherits it without asking. The shipped 250 MB `cards.db` on
     this machine reads `wal`.
  3. **But a freshly created one does not.** Measured directly: a database created by
     `src/data/database.init_database` reads `journal_mode: delete`. So the FRESH-INSTALL case —
     exactly the one FR-22 is about — is the non-WAL row of that table.

  **It still does not bite, and the reason is arithmetic rather than luck.** The worst measured
  effect is a single 0.21 s wait on one write, under four threads saturating the endpoint, absorbed
  by a 5 s busy timeout that is 20x larger. This story's poll issues ONE request every 2-30 s, not
  four continuously — so a writer meets an in-flight read for a small fraction of wall-clock, and
  the wait it inherits is one read. Adding a WAL pragma to the companion's engine is still the
  right eventual fix (NFR-02 calls for WAL reads and it would make the fresh-install case match the
  post-index case), but it is latency hardening rather than an FR-22 failure. **Home: 17-3**, with
  the numbers above. (Severity: Low-Medium -> **Low**, measured.)

- **The `Attributes:` sections in the four wire-facing schemas hold prose, not attributes, and
  nothing says why.** `src/data/schemas/deck.py` (`DeckCardSummary`, `DeckSummary`, `DeckDetail`)
  and `src/data/schemas/card.py` (`CardSummary`) use `Attributes:` purely as a truncation marker,
  because `_CompanionFastAPI.openapi()` cuts every description at the first Google-style header
  (AC 17's suggested mechanism). Two consequences worth knowing: a napoleon/Sphinx render of these
  four classes now emits a malformed attribute list; and — the one that bites — **the shared core's
  docstring *structure* is load-bearing for a companion-only rule that `src/data` never mentions**.
  `test_openapi_contract.py` bans the literal markers from crossing the wire, i.e. it gates the
  *marker*, not the prose, so an editor who removes a header that plainly documents no attributes
  silently republishes "keeping `load_deck` payloads small for LLM clients" into `/docs` and
  `types.d.ts` with no gate going red. **Home: c3-2**, which will do the same thing to `Card` and
  should decide the convention for all of them (a `Note:`-style marker that reads honestly, an
  explicit comment in `src/data`, or a gate keyed on the prose). (Severity: Low.)

  **RESOLVED at c3-2, 2026-07-31 — Q5: keep the convention, state why it is load-bearing.** The
  `Attributes:` header stays (it works, and c3-1 used it four times), was applied to `Card`, and
  the sharpest edge is now closed by the middle option: **`src/data/schemas/card.py`'s MODULE
  docstring** carries an explicit statement that the first paragraph of every class docstring is
  published to the outside world, that the header position is the truncation marker, that a header
  documenting no attributes is still load-bearing, and that **no gate goes red** if it is deleted.
  Chosen over a gate on the prose (not decidable — see the entry above) and over renaming the
  marker (would churn four already-shipped schemas and both generated files for a cosmetic gain).

- **`ui/README.md`'s "What the gates cannot see" index is keyed on line numbers with nothing keeping
  it accurate.** Twenty-one `file:line` references across nine test files; all verified correct at
  the time of writing (17 spot-checked by the Acceptance Auditor, 8 by the Blind Hunter, all
  resolving). But the section is written as a durable index a reviewer consults instead of reading
  fourteen test files, and the first comment inserted near the top of `token-usage.test.ts`
  invalidates every reference below it. Every other load-bearing claim in that README is gated; this
  one is not. **Fix shape**: anchor on a searchable marker string (the guard function name, or the
  declared-limit sentence itself) rather than a line number, and add a test that every cited anchor
  still resolves. **Home: unowned, ledgered** — cheap to do, and the next story to add a row is the
  natural one. (Severity: Low-Medium — a stale index is worse than no index, because it is trusted.)

- **`tests/unit/companion/test_spa.py`'s completeness now rests on a hand-synchronised router
  list.** The two schema pins that hardcoded `{"/health"}` were repaired (see the c3-1 story record,
  finding 4), and the differential test `test_the_schema_is_unchanged_by_installing_the_mount` now
  builds a mount-free app that must mirror `build_app()`'s routers by hand. Every future
  router-adding story (c5-2, c5-5 — **not** c3-2/c3-3/c3-4/c3-5 if their routes join an existing
  router; see the correction below, which supersedes the original list) must add one line there or get a red.
  That is deliberate and the code says so — a forgotten line is a cheap named failure, versus a
  mount silently swallowing a route — but it *is* a standing tax, and it is the opposite of the
  repair's stated motive ("a hardcoded set makes every story that adds a route edit a SPA test for
  no reason"). **Recorded so it is a decision, not a drift.** If it becomes annoying, the fix is to
  derive the router list from `build_app()` itself rather than restating it. **Home: unowned.**
  (Severity: Low.)
  **Correction (c3-3, 2026-08-01): the story list above is wrong, and the tax is narrower than
  stated.** The tax falls on adding a **router**, not on adding a **route**. Both sides of the
  differential build their path sets from the same router objects, so a new path on an
  already-listed router appears on both and needs no line. Measured, not reasoned: c3-3 added
  `/api/deck/{deck_id}/format-check` to the existing decks router and `test_spa.py` passed
  unedited — **56 passed**. So c3-3 never owed a line, and neither will c3-4/c3-5 if their routes
  join an existing router. The comment in `test_spa.py` now says this, so the next author does not
  go looking for an edit they do not owe.
  **Tax paid, c5-2 (2026-08-08).** `routes/session.py` is a new router, so c5-2 was the first of
  the two stories this entry names by key to come due — and it came due exactly as advertised:
  adding `session.router` to `build_app()` reddened
  `test_the_schema_is_unchanged_by_installing_the_mount` with *"Extra items in the left set:
  '/api/session'"* before the line existed, and the harness re-proved it red through the full
  2,594-test suite with the line deleted again. One line added. **c5-5 remains outstanding** and is
  now the only story this entry still names. The "derive the list from `build_app()`" fix is still
  not taken: at three consecutive paid taxes the named-failure trade is still winning, and c5-2 has
  no more standing to change a shared test's design than c3-3 did.
  **TAX PAID OUT — ENTRY CLOSED, c5-5 (2026-08-08).** `routes/agent_events.py` is a new router, so
  the last story this entry named by key came due and paid: adding `agent_events.router` to
  `build_app()` reddened `test_the_schema_is_unchanged_by_installing_the_mount` with *"Extra items
  in the left set: '/agent/events'"* before the line existed. One line added, exactly as advertised.
  **No story key remains outstanding on this entry.** The "derive the list" fix is *still* not
  taken, and after four consecutive paid taxes that is now a settled preference rather than a
  deferral: each tax cost one line and produced a named failure naming the missing path, which is
  the trade the design was chosen for. Anyone reopening this should bring a story that got it wrong,
  not a story that found it tedious. A second observation worth keeping, because it was measured
  four times and never stated: **the tax has never once caught a real bug** — every red was the
  author's own new router, seen immediately. Its value is the shape of the failure it would produce
  for the author who *doesn't* notice, which no amount of paid tax can evidence.

## Deferred from: code review of c3-1-deck-list-and-deck-detail-endpoints (2026-07-31, post-commit pass)

- **`from_deck` on a non-eager-loaded `Deck` silently yields 0/0/0 counts and an empty `cards`** —
  re-confirmed by the post-commit review as the sharpest edge the projection move created:
  `DeckModel.deck_cards` is `lazy="noload"`, so a `Deck` from `get_deck` / `find_deck_by_name` /
  `update_deck` feeds the public constructors an HTTP-200-shaped lie, guarded only by a docstring
  caveat. Already ledgered "unowned" by the story; this pass names a home candidate: the keyed
  `data-layer-orphan-handling` story (sprint-status.yaml), which already owns the sibling
  get_deck_with_cards ValidationError crash. (Severity: Medium if a future caller mis-sources;
  no current caller does.)

- **Generated-type optionality asymmetry: `strategy?: string | null` vs `format: string | null`,
  plus `@default 0` advertised on the count fields** — the server always serializes every field, so
  the `?` (a Python-default artifact) forces the UI into a spurious `undefined` branch, and the
  documented `0` default is exactly the silently-wrong value AC 3 exists to catch, now presented on
  the wire as normal. Pre-existing schema shape; this story merely put it on the wire. **Home:
  c4-1/c4-2**, the first real consumers of these types. (Severity: Low.)

  **Not triggered at c4-1 (2026-08-02); the whole entry is c4-2's.** c4-1 consumed `Card`,
  `CardSummary` and `DeckCardSummary` and hit neither half: no `strategy`, no `format` and none of
  the three count fields appears on any of them — they live on `DeckSummary` / `DeckDetail`, and
  c4-1 deliberately did not alias `DeckDetail`, having no consumer for it. **Home: c4-2**,
  unshared, which reads exactly those fields when it renders the deck header.

- **`_is_ref_rooted` will misfire on the first legitimate union response model.**
  **✅ RESOLVED at c3-3 (2026-08-01, Q5 — Brad took this half of the question).**
  `tests/unit/companion/test_errors.py` puts `anyOf`/`oneOf`/`allOf` in `_OBJECT_SHAPE_KEYS`, so a
  future `response_model=X | None` — plausibly c3-3's "no format to check against" answer —
  generates a top-level `anyOf` and is refused as a "hand-built envelope", which it is not: the
  guard's family conflates *object-shaping* with *union-forming*. Two smaller 3.1 edges in the same
  helper: a `$ref` carrying legal sibling annotation keys fails `set(schema) == {"$ref"}` (false
  red), and `prefixItems` is absent from the key set (false green for a tuple-shaped array). Fix
  shape when it fires: admit a union whose every branch is itself ref-rooted or `{"type": "null"}`,
  and add `prefixItems` to the object-shape keys — extending the family, not enumerating members.
  **Home: c3-3**, the first story likely to hit it; until then the failure is a red test with a
  misleading message, not a shipped defect. (Severity: Low.)
  **Resolution**: all three edges fixed exactly as the fix shape describes. `anyOf`/`oneOf` moved
  out of `_OBJECT_SHAPE_KEYS` into a new `_UNION_KEYS`, with a union admitted only when **every**
  branch is itself ref-rooted or the bare null type; `prefixItems` added to the object-shape keys;
  and a `$ref` now tolerates annotation-only siblings via a named `_ANNOTATION_KEYS` set. Ten new
  rows in the helper's own accept/reject table, including the three ways the union arm could have
  become a hole — one inline branch among refs, an all-scalar union, and an **empty** `anyOf`
  (`all([])` is `True`, which is how a vacuous guard is born). Note the fix shipped *before*
  anything needed it: c3-3's own response is one shape in every case by ruling (Q4), so no union
  crosses the wire yet. Taken anyway, because the alternative was leaving the next story a red
  test whose message named the wrong problem.

- **`format: string | null` on the wire is unreachable at the data layer — `decks.format` is a
  `NOT NULL` column.** Measured while writing the review's null-metadata test:
  `create_deck(format=None)` raises `IntegrityError` (`NOT NULL constraint failed: decks.format`),
  so the `null` half of the generated type can never be served from a repository-written deck. The
  c3-1 story's own gotcha ("a deck can genuinely have no format, and c3-3's 'no format to check
  against' response depends on it") is therefore half-false as stated: the *schema* allows null,
  the *database* forbids it. **Home: c3-3**, which must decide whether "no format to check
  against" is keyed on a null format (then the column constraint is the bug) or on an
  unrecognised format string (then the wire type is merely wider than the data and can stay).
  (Severity: Low-Medium — a UI `format === null` branch written against the generated type is
  dead code today.)
  **✅ RESOLVED at c3-3 (2026-08-01, Q4 — Brad ruled "as proposed").** The wire type is merely
  wider than the data, and it stays. "No format to check against" is keyed on the validator's
  existing `unknown_format` outcome, which already covers an unrecognised **or empty** format
  string and already refuses to flag every card illegal — so no schema change, no migration and no
  new mechanism. `format_check` coalesces a null format to `""`, which lands in the same branch;
  the report carries `format: ""` and `format_recognized: false`, and its legality and banned rows
  go `advisory`. Re-verified at c3-3 before ruling: the column is still `NOT NULL` and **0 of 40**
  rows are null or blank. **Re-homed residue: c4-10** writes the UI's "no format" branch, and if it
  writes `format === null` against the generated type that branch is dead code — it should key on
  `format_recognized` instead, which c3-3 added for exactly this.

## Deferred from: story c3-2 (2026-07-31)

- **There is no price data anywhere in this project, and FR-17's "prices if present in local data"
  is therefore never satisfied.** Measured at c3-2: `PRAGMA table_info(cards)` lists 23 columns and
  none of them is a price; `Card` and `CardSummary` declare no price field; a case-insensitive grep
  for `price` across `src/`, `tests/`, `ui/src` and `scripts/` returns **one** hit, a forward-looking
  comment in `StatChip.css` about a future micro-role — no column, no field, no importer path, no UI
  consumer. (The c3-2 story text claimed *zero* hits over those roots; the one CSS-comment hit is
  the correction, and it changes nothing about the conclusion.) The 2026-07-11 PRD recon recorded
  the same absence ("ABSENT: game_changer, edhrec_rank, saltiness, prices"). The epic's price AC is
  therefore satisfied **by absence**, ruled by Brad at Q4, and `GET /api/cards/{card_id}` ships **no
  price field** rather than a `prices: null` that would be null on 100% of responses — a permanently
  dead branch c4-5 would have to handle for nothing. **What adding prices would actually cost**: a
  new `cards` column (or a side table, since Scryfall prices are per-printing and volatile), an
  `import_scryfall_data.py` change to populate it, a hand-written migration script (this project has
  no Alembic), a full re-import of 38,261 rows, plus a staleness story — Scryfall prices change
  daily and a locally cached price with no fetched-at timestamp is a number that lies. **Home:
  c4-5**, the card detail panel — it is the only surface `EXPERIENCE.md` promises prices on
  (`:86`, "Prices render only when present in local data"), so it is the story that must either
  render nothing there deliberately or raise the import work as its own brief. (AC 15 asks for a
  *named* home; "unowned" was the first draft and the review was right to call it.) The artefact
  already reads correctly against absence, so nothing is broken today. (Severity: Low.)

- **`503` outranks `400`: a malformed card id sent to a backend with no database answers
  `database_not_initialized`, not `invalid_request`.** Measured at c3-2 (the test asserting the
  opposite failed, and the assertion — not the code — was wrong). FastAPI's `solve_dependencies`
  solves sub-dependencies *and* collects parameter-validation errors in one pass, raising
  `RequestValidationError` only after the dependencies have run; `get_session`'s `CompanionError`
  therefore propagates first. Both outcomes are now pinned in `test_routes_cards.py`. Defensible —
  the backend genuinely cannot serve the request for a reason that outranks the client's spelling —
  but **invisible from the route source**, and it matters to two named stories: **c3-9** polls the
  503 states and **c4-1** owns the fetch layer, and a UI that treats `database_unavailable` /
  `database_not_initialized` as "retry quietly" will retry a request whose id can never succeed.
  ~~**Home: c3-9**, which owns the polling and the transition.~~ **CLOSED, c3-9 (2026-08-02),
  and closed structurally rather than carefully.** The one route c3-9 polls, `GET /api/decks`, has
  **no path parameter**, so there is no id to be malformed and no `503` it sees can be masking a
  `400`. That is asserted rather than merely written down — `decks.test.ts` pins
  `DECKS_PATH` free of `{`, `}` and `:`, because the safety argument evaporates the moment somebody
  parameterises the constant, which is exactly what **c4-1** will be tempted to do when it copies
  this module for `GET /api/cards/{card_id}`. The warning for c4-1 is written in three places it
  will actually read: `ui/src/api/decks.ts`'s header, that assertion's comment, and `ui/README.md`'s
  *"Not here yet"* section. **c4-1's per-card fetches are NOT immune and need a bound on attempts
  per id.** (Severity: Low-Medium.)

- **`card_faces` crosses the wire completely untyped.** `Card.card_faces` is
  `list[dict[str, Any]] | None`, generating `{ [key: string]: unknown }[] | null` — no per-face
  contract at all, so a consumer reading `face.image_uris.normal` gets no help from the compiler.
  Deliberately not fixed here: typing untyped Scryfall JSON would be a second shape over data this
  project does not control, and it would land on the MCP tools too. Measured face-count histogram
  (real corpus): **2 → 3,222 cards · 3 → 2 · 5 → 1** — so a `[front, back]` destructuring is wrong
  for three real cards. **Home: c4-6**, the DFC flip control, which is the story that actually needs
  a face contract. (Severity: Low.)

- **79 cards carry no image data anywhere — the first concrete population for the Card placeholder.**
  Measured: of 38,261 rows, 2,857 have a JSON-null `image_uris`; 2,778 of those carry per-face
  `image_uris` inside `card_faces` instead; **zero** carry both; **79 carry neither**. `c3-2` proves
  all three shapes round-trip with the nulls surviving as `null`. `EXPERIENCE.md`'s "Card with no
  image data | Any surface | Named Card placeholder (FR-19)" row has, until now, had no measured
  population. **Home: c4-3**, which owns the placeholder — and which now knows the unknown-card
  variant and the no-image variant are different populations reached by different routes (a 404
  token versus a 200 with null images). (Severity: Low.)

  > **RESOLVED at c4-3 (2026-08-04) — the 79 re-verified, and their SHAPE measured for the first
  > time.** Re-counted read-only against the live DB: 38,261 rows, **79** with no image data
  > anywhere. What this entry did not know is what those 79 LOOK like, and it changes the layout
  > the placeholder had to survive: **all 79 have `type_line` exactly `'Card // Card'`**, **all 79
  > have a BLANK `mana_cost`**, and **all 79 have a doubled `X // X` name** (longest 66 chars,
  > `Asmoranomardicadaistinaculdacar // Asmoranomardicadaistinaculdacar`). So UX-DR22's three-part
  > composition degrades, MEASURED, to a name and nothing else for every card that permanently
  > needs this variant — which is not a reason to change the design but is why AC 7 is about being
  > correct when two of three parts are empty. Two of the 79 are now fixtures in
  > `CardPlaceholder.test.tsx`. **And 0 of 2,027 live deck rows are such a printing**, so in a deck
  > view the named placeholder is only ever reached transiently, through `image_fetch_failed`.

- **The `states.ts` classification of panel-less tokens is gated by the compiler but read by
  nothing.** c3-2 added `PLACEHOLDER_FOR_REASON`, `NO_UI_RESPONSE` and three type-level asserts so
  the third meaning of `null` is machine-readable rather than a comment (Q3, satisfying retro R1).
  Three asserts prove every panel-less token is classified as exactly one of {placeholder, nothing}
  and that nothing with a panel is classified — but **no runtime code consumes any of it yet**, the
  same declared state `PANEL_FOR_REASON` itself has been in since c2-9. **Home: c4-3** (the
  placeholder render) and **c3-9** (the panel wiring). If neither consumes it, that is a signal the
  structure was over-built and it should be deleted rather than maintained.
  **HALF CLOSED, c3-9 (2026-08-02).** The PANEL half is consumed: `panelFor` reads
  `PANEL_FOR_REASON` and, notably, uses its key set as the runtime membership test for
  `ErrorReason` — so the map is load-bearing twice over and cannot be deleted without inventing a
  second list. The CLASSIFICATION half — `PLACEHOLDER_FOR_REASON`, `NO_UI_RESPONSE` and the three
  type-level asserts — is still consumed by nothing, and **stays c4-3's**, stated explicitly here
  because this entry's own text makes non-consumption a delete signal and c3-9 was one of its two
  named consumers. c3-9 does read the `null`s, but only to clamp them: a panel-less token on a
  whole-screen poll means a client bug, so it renders `internal-error` rather than consulting which
  KIND of `null` it was. **If c4-3 does not consume the classification, delete it.**
  (Severity: Low.)

  > **✅ CLOSED at c4-3 (2026-08-04): the classification is CONSUMED, not deleted.** This entry
  > made the delete conditional and c4-3 is the condition, so the answer is stated plainly.
  > `src/components/CardPlaceholder/CardPlaceholder.tsx` imports `PlaceholderKey` (type-only) and
  > builds its variant union FROM it — `PlaceholderKey | 'loading'` — and the coupling is enforced
  > in BOTH directions by two type-level asserts in the component: `EveryPlaceholderKeyHasProps`
  > fails if a third key is added to `states.ts` with no props member, and `NoVariantIsUnknownToStates`
  > fails if the union is widened to a bare `string` (the evasion the first assert alone would pass,
  > because every key still has a member). Both were PROBED: probes (d) and (g) of c4-3 are `tsc`
  > failures with `npm test` staying green — the c4-1 asymmetry again, and why `npx tsc -b --force`
  > is a gate of its own. `PLACEHOLDER_FOR_REASON` also gets a RUNTIME consumer, in
  > `CardPlaceholder.test.tsx`, which renders every variant its values name rather than trusting
  > the type. **Nothing in `states.ts` was edited to make consumption work**, which was the design
  > smell this entry was watching for. `NO_UI_RESPONSE` remains consumed by nothing at runtime and
  > stays where c3-9 left it.

- **`ui/README.md`'s blind-spot map now carries the "does this prose address a TypeScript reader"
  residue, which is a REVIEW obligation with no gate.** Added at c3-2 alongside the family-keyed
  wire-prose gate. It inherits the pre-existing weakness recorded above at c3-1 — the index is keyed
  on line numbers with nothing keeping them accurate. **Home: c3-3**, the next story to add a
  schema to `components.schemas` and therefore the next to owe this review pass; it is also the
  natural point to anchor the README's citations on marker strings rather than line numbers, as
  the c3-1 entry proposes. (Severity: Low.)
  **⛔ DECLINED at c3-3 (2026-08-01, Q5 — Brad took the `_is_ref_rooted` half of the question and
  left this one).** c3-3 *did* pay the review-pass half: it added its blind-spot row and, after
  the adversarial review found that row under-declared its own guard's holes, rewrote it to
  enumerate five families and three declared limits. The **re-anchoring** was not done.
  Re-ledgered in the c3-3 section below as "Home: unowned" — see *"`ui/README.md`'s blind-spot
  map is still keyed on line numbers"*. Do not read this entry's `Home: c3-3` as outstanding
  work against a completed story.

- **A `ui/tests/` file may import an app module only if that module has no relative imports of its
  own — and the failure is reported at the wrong place.** Measured at c3-2. `tsconfig.node.json`
  owns `tests/**/*.ts` with `module: nodenext` (extension required on relative imports);
  `tsconfig.app.json` owns `src` with `moduleResolution: bundler` (extension forbidden). Importing
  `states.ts` from `ui/tests/unknown-card-copy.test.ts` pulled it into the node project, where its
  own extensionless `../../api/schema` and `./copy` imports became `TS2835` — and then **cascaded**:
  `ErrorReason` failed to resolve, and all three of `states.ts`'s type-level asserts collapsed to
  `Type 'false' does not satisfy the constraint 'true'`, pointing at the asserts rather than at the
  import. `copy.test.ts` gets away with importing `copy.ts` only because that module happens to have
  no relative imports; that is a property of the module, not a general permission. **Two aggravating
  factors**: `npm test` stays fully green throughout (vitest resolves fine — this is a `tsc`-only
  failure), and `tsc -b` is incremental, so the error can hide behind a cached build until an
  unrelated later run surfaces it. `npx tsc -b --force` is what makes it deterministic.
  **Fix shapes**, none taken here: add explicit extensions in `states.ts` (breaks the app project's
  convention), exclude `src` from the node project's graph, or keep the current workaround — a
  source read, with the runtime value pinned in the app-project test beside the module.
  ~~**Home: c4-1**, the first story that will want to import real app modules into `ui/tests` at any
  scale (a fetch layer is exactly the thing whose tests reach across).~~ Until then the workaround
  is documented in `unknown-card-copy.test.ts` and in `ui/README.md`'s blind-spot map.
  (Severity: Medium — the symptom points at the wrong file, and CI runs `tsc -b` without
  `--force`, so a cached-clean result can ship.)

  **NOT TRIGGERED at c4-1 (2026-08-02) — re-homed by name, with the reason.** The prediction was
  reasonable and it did not hold: c4-1's fetch layer and cache are tested **inside the app
  project** (`src/api/client.test.ts`, `src/state/cards.test.ts`), which is where AC 24 puts them —
  jsdom, no configuration, no cross-project import. What c4-1 added under `ui/tests/` is a change
  to `posture.test.ts`'s door list, and that guard reads source as **text** via
  `readFileSync` + `git ls-files`; it imports no app module and therefore cannot trip the cascade.
  `npx tsc -b --force` was run and is green, so this is a measured "did not fire", not an
  assumption. **Home: the first story that actually imports a real `src/` module into `ui/tests/`.**
  Nothing in C4 obviously does — the epic's remaining guards are file-reading guards of the same
  shape — so the realistic candidate is **c5-1**'s event envelope or whichever story first wants a
  runtime value from `src/` inside a node-project test. (Severity: unchanged, Medium.)

  > **✅ TRIGGERED AND CLOSED at c4-3 (2026-08-04) — by the story c4-1 said probably would not.**
  > `tests/unknown-card-copy.test.ts` now imports a real `src/` module: `UNKNOWN_CARD_LABEL` from
  > `src/components/CardPlaceholder/copy.ts`, so the shipped label can be asserted BYTE-FOR-BYTE
  > against `EXPERIENCE.md` — the assertion that file has promised since c3-2 would land "the day
  > c4-3 lands". **It does not fire, and the rule is now stated precisely rather than
  > approximately.** The constraint was never "a `ui/tests` file may not import an app module"; it
  > is **"may not import an app module that has RELATIVE imports of its own"**, because those are
  > what `nodenext` demands extensions for. `copy.ts` has `imports: []` — pinned exhaustively by
  > `shell.test.ts`'s `PRIMITIVES`, so an import added there is a red test before it is a `tsc`
  > cascade — which is the same property `copy.test.ts` relies on for `StatePanel/copy.ts`, and it
  > is now a property two guards protect rather than a coincidence. **`npx tsc -b --force` was run
  > and is green**, so this is a measured "did not fire". The MEDIUM half of the entry stands
  > unchanged and un-fixed: the symptom still points at the wrong file, and CI still runs `tsc -b`
  > without `--force`. **Home for the fix shapes: unchanged.**

  > **NOT TRIGGERED at c5-1 (2026-08-07) — the candidate c4-1 named by name, and it was the wrong
  > guess for a structural reason worth writing down.** c4-1 predicted "**c5-1**'s event envelope"
  > as the realistic candidate. c5-1 shipped the whole envelope and **added no `ui/` code at all**:
  > the union is Python, it is unreferenced by any route, and it therefore produces no TypeScript
  > for a `ui/tests/` file to import. That is not an accident of scheduling — it is the same fact
  > that inverted the epic's own AC 8 into a confirmed negative. **The candidate was mis-identified
  > because "the story that defines the wire types" and "the story that first imports them into a
  > node-project test" are different stories whenever the defining story adds no route.**
  >
  > **Proven, not asserted:** `npx tsc -b --force` was run in `ui/` and exits **0** (2026-08-07) —
  > `--force` specifically, because CI runs `tsc -b` without it and a cached-clean result can ship.
  >
  > **Re-homed with the reason: the first story that puts the event union on a route AND asserts a
  > generated type from `ui/tests/`.** That is **c5-5** at the earliest (it declares
  > `POST /agent/events`, so the union first reaches `types.d.ts` there), and more likely **c6-x**,
  > where a view actually consumes the narrowed payload. The narrowed c4-3 rule still governs what
  > would fire: not "a `ui/tests` file may not import an app module" but "may not import an app
  > module that has **relative imports of its own**". (Severity: unchanged, Medium.)



## Deferred from: code review of c3-2 (2026-07-31)

- **A malformed card id reaching the UI from DATA renders nothing at all — no placeholder, no
  state.** `card_not_found` is the token wired to the unknown-card placeholder; a card id that
  fails the route's shape gate produces `invalid_request`, which `states.ts` classifies as
  `NO_UI_RESPONSE` — "nothing on the glass, anywhere". Those two answers are one character of
  input apart. `deck_cards.card_id` carries no shape constraint, FK enforcement is off on the async
  engine (`CardRepository.get_by_id`'s own docstring says so), and the planned Arena
  `arena_card_map` work will introduce ids from a second source. Measured today: **0 of 2,027
  `deck_cards` rows are non-canonical**, so this is latent, not live — but it is not structurally
  prevented, and the failure mode is the exact one FR-13 exists to stop ("one unknown card must
  never fail a whole view") wearing a different token. **Fix shape**: either the hydration layer
  treats a 400 on a card fetch as a placeholder case, or the id shape is validated where deck rows
  are read. ~~**Home: c4-1** (the hydration cache) with **c4-3** (the placeholder) as its consumer.~~
  (Severity: Medium if it ever fires, Low probability today.)

  **✅ RESOLVED at c4-1 (2026-08-02, Q5) — and closed on BOTH fix shapes, not one.** The ruling:
  **a `400 invalid_request` on a per-card read IS the unknown-card case.**
  `PLACEHOLDER_FOR_CARD_REFUSAL` in `src/state/cards.ts` maps it to `states.ts`'s own
  `'unknown-card'` `PlaceholderKey`, beside `card_not_found`, whose value is read OUT of
  `PLACEHOLDER_FOR_REASON` rather than re-typed. The argument, written in the code: `states.ts`
  classifies that token `NO_UI_RESPONSE` on the premise *"the SPA never generates a malformed
  request"*, and that premise is **exactly what fails here** — an id the app cannot render is an id
  the app cannot render, whichever token says so. `states.ts` is untouched, because the
  destination is context-dependent rather than a property of the token, and adding
  `invalid_request` to `PLACEHOLDER_FOR_REASON` would break `ReasonClassificationsAreDisjoint`.
  The second fix shape landed too: `cardPath()` runs the id through `encodeURIComponent`, so an id
  carrying `/`, `?` or `#` can no longer change WHICH route is addressed — it stays one path
  segment and the route's uuid pattern refuses it. Both halves are test-pinned. ~~**c4-3 renders the
  placeholder**; the token and the destination are waiting for it.~~
  **✅ THE RENDER ARRIVED at c4-3 (2026-08-04).** `CardPlaceholder variant="unknown-card"` draws the
  label and the truncated id, and `CardPlaceholder.test.tsx` drives the whole path for real —
  `hydrateCard` with an injected reader returning `card_not_found`, then the rendered placeholder
  read out of the DOM. The consumer branches on `entry.placeholder`, never on `entry.reason`, so
  the c4-1 ruling is what selects the variant rather than a second map in a component. **This
  entry is fully closed: token, destination and render.**

- **`Card` is now a banned type name across all of `ui/`, and there is no sanctioned alias to
  import instead.** `wire-contract.test.ts` derives its ban from `components.schemas`, so `Card`
  joined it automatically at c3-2 — correct, and the mechanism working as designed. But
  `ui/src/api/schema.ts` re-exports only `HealthResponse`, `ErrorResponse` and `ErrorReason`; it
  exports no `Card` and no deck aliases either. So the first component that needs the card type
  (c4-3, c4-5) hits a ban with no signposted alternative, and the obvious local workaround —
  declaring a local `interface Card` — is precisely what the gate rejects. **Fix shape**: add the
  aliases to `schema.ts` in the story that first needs them (one line each; the barrel is the
  sanctioned single reader). Not done here because c3-2 ships no component and an unused export
  would be dead code. ~~**Home: c4-1**, the first frontend story to consume a wire shape.~~
  (Severity: Low — a five-minute detour, but an unsignposted one.)

  **✅ RESOLVED at c4-1 (2026-08-02).** `src/api/schema.ts` now exports **seven** aliases:
  `HealthResponse`, `ErrorResponse`, `DeckSummary`, `ErrorReason` and — new here — `Card`,
  `CardSummary` and `DeckCardSummary`, each with a docstring naming its consumer (`readCard`, the
  cache's `hydrated` tier; the cache's `summary` tier; `seedCardSummaries`, which **c4-2** calls).
  **`CardFace` and `DeckDetail` were deliberately NOT added**: nothing in this commit consumes
  them, and c3-2's own reason for declining — an unused export is dead code — applies to c4-1
  exactly as it applied to c3-2. c4-2 adds `DeckDetail` when its fetch needs it; whichever story
  renders a flip control (**c4-6**) adds `CardFace`. `ui/README.md:154` claimed three aliases when
  four already shipped; corrected in the same commit.

- **`GET /api/cards/{card_id}` sets no cache headers on a resource that is immutable between
  database refreshes.** `cards.py`'s module docstring claims c3-5's image route shares "the same
  cache story"; today there is no cache story on this side to share. No `ETag`, no
  `Cache-Control`, no conditional-request handling — while `spa.py` has a whole
  `_apply_cache_headers` mechanism for static files. A c4-x deck view hydrating 60–100 cards
  re-fetches every full record on every render. Low impact today (localhost, SQLite, one user),
  and deliberately not fixed in a story whose scope is one lookup. ~~**Home: c3-7** (the sharded
  disk cache) or **c4-1** (the hydration cache), whichever lands first~~ — **c3-7 landed first and
  answered it (Brad, Q1's sub-question, 2026-08-01): it CORRECTED the docstring rather than
  implementing the shared story.** The reasoning is that "the same cache story" was never one
  story: a card row's cache story is `ETag`/conditional requests over a database read, which
  shares nothing with a file on disk but the word, and implementing it inside c3-7 would have been
  a second mechanism smuggled in under a docstring's phrasing. `cards.py`'s module docstring now
  says so explicitly, in the past tense, so the sentence cannot be read as a live claim again.
  ~~**The route still sets no cache headers, and that half stays homed on c4-1** beside the
  hydration cache it belongs with.~~ (Severity: Low. **Status: half closed** — the false claim is
  gone.)

  **RE-HOMED at c4-1 (2026-08-02, Q7) — declined here, with the measurement that makes it a
  decision rather than a dodge.** The theory this was homed on was that the hydration cache is the
  layer that makes the missing headers moot, and **measured, that theory holds**: the cache issues
  **one request per id per tab** and never re-requests a hydrated id, so the population an `ETag`
  would serve is *page reloads*, not renders. The entry's own worst case — *"a c4-x deck view
  hydrating 60–100 cards re-fetches every full record on every render"* — is now structurally
  impossible, and the sentence is superseded rather than merely unfixed. Two further facts: the
  client sends `cache: 'no-store'` on card reads (deliberately, so that a header-less response
  cannot be heuristically cached into staleness across a database refresh), which would make an
  `ETag` inert until that decision were revisited; and implementing it would be a **backend** change
  in a story whose whole product is a store slice, making AC 27's "the Python side is unchanged"
  false for no measured gain. **Home: the C4 retrospective**, which is where "close this as
  superseded, or do it with the cache in view" should actually be decided — the epic's twelve
  stories are the ones that will have exercised the cache on real decks by then.
  (Severity: Low, and lower than when it was written.)

- **`test_openapi_contract._descriptions()` does not mirror the truncator's `_DATA_KEYS` skip.**
  `without_python_docstring_sections` deliberately does not descend into `example`/`examples`/
  `default`/`const`/`enum` subtrees, because a `description` key there is payload data reproduced
  byte-for-byte. `_descriptions` descends everywhere. Measured: **zero** descriptions under a data
  key in the committed schema today, so nothing fires. The first example payload carrying a
  `description` whose value contains a colon-terminated line makes the family scan an
  **unsatisfiable red** — its message says "fix at the Python docstring" and there is no docstring
  to fix. **Fix shape**: give `_descriptions` the same `_DATA_KEYS` skip, ideally by importing the
  constant rather than re-declaring it. **Home: c5-1**, the first story expected to add example
  payloads (the event-envelope union). (Severity: Low, latent.)

  > **✅ TRIGGERED AND CLOSED at c5-1 (2026-08-07) — fix taken, in the prescribed shape.** c5-1 did
  > add example payloads: `json_schema_extra={"examples": [...]}` on all four item models and all
  > six envelope classes, ruled in by Brad (Q8) precisely because this entry is homed here and this
  > is the story that should pay for it. `_descriptions()` now takes `_DATA_KEYS` **imported from
  > `main`**, not re-declared, and mirrors the truncator's walk exactly — including the inverse
  > `in_properties` care, so a model with a field genuinely called `example` still has its
  > description read. **MEASURED before and after: 65 descriptions both ways, and the two lists are
  > element-for-element identical** — zero descriptions sit under a data key in the committed schema
  > today, exactly as this entry predicted, so the fix moved nothing and is pre-emptive.
  >
  > **One nuance this entry could not have known, recorded because it changes when the trap could
  > next have fired.** c5-1's examples do **not** reach the committed schema at all: the models are
  > unreferenced by any route, and a model no route references never lands in `components.schemas`.
  > So the trap would not have fired here even with examples added — the first schema-reachable
  > example payload arrives at **c5-5**, when `POST /agent/events` declares the union as its request
  > body. The fix is taken early rather than exactly-in-time, which is the cheap direction.
  >
  > **Three tests ship with it** (`TestTheCollectorMirrorsTheTruncator`), because a fix with no
  > firing proof is the class this epic's R2 exists to stop: a description inside an `example`
  > payload is not collected while the schema's own description on the same document is (the
  > non-vacuity pair, in one call); a property literally named `example` is still descended into;
  > and the committed schema still yields an identical list under both walks, so the reader learns
  > the moment that stops being true. **Firing proof: deleting the `_DATA_KEYS` skip reddens
  > `test_a_description_inside_an_example_payload_is_not_collected` through the full 2,526-test
  > run** (not a single-file run — verified through `scripts/probe_harness.py`). **CLOSED.**

## Deferred from: code review of c3-2-card-detail-endpoint, round 2 (2026-07-31)

- **A body-less GET publishes `413 payload_too_large` in its client contract.** The app-wide
  `error_responses` wiring from `build_app()` lands the 413 row on `GET /api/cards/{card_id}`
  (and the deck GETs before it), so the generated contract tells c4-1's fetch layer to handle a
  response the same document describes as "surfaced to the *agent*… The glass never sees it."
  Pre-existing, inherited, and doubled by every new GET route. **Fix shape**: either curate the
  app-wide set per-method (drop 413 from body-less GETs at declaration time) or record it as a
  known wart in the contract docs. ~~**Home: the next story that touches `error_responses`'s
  declaration helper**, else c3-9.~~ **RULED, c3-9 (Q8, 2026-08-02): RECORDED AND RE-HOMED ON
  c5-5.** c3-9 declined to curate per method. The reason is scope with blast radius, stated so it
  can be argued with: Q4 touched the *caller* (`build_app`'s per-include sets), not the helper, so
  the trigger condition in this entry was never actually met; and changing `error_responses`'
  per-status grouping into per-method curation is a real change to a shared declaration site with
  six routes downstream, made in a story whose frontend half is already the largest in the epic.
  It is now written down as a known wart in `scripts/dump_openapi.py` — the contract-docs home —
  with the consequence spelled out for a client author (*a 413 on a body-less GET is unreachable;
  ignore it*). **Home: c5-5**, which adds the ingest cap, makes the 413 real, and cannot avoid
  deciding which operations answer it. (Severity: Low.)
  **c5-2's disposition, recorded so c5-5 does not re-litigate it (2026-08-08).** This entry warned
  the wart is *"doubled by every new GET route"*, and c5-2 added one. It did **not** double it:
  `/api/session` declares `invalid_request` and `internal_error` only, mirroring the per-include
  narrowing c3-4 already applied to `/api/active-deck` rather than inheriting the shared set. So
  the count of body-less GETs publishing an unreachable 413 is **unchanged at six**, not seven, and
  the two most recent route-adding stories have both declined to add to it. That is now a
  two-instance pattern rather than one story's choice, and it narrows c5-5's job: the six are all
  *pre-existing* declarations on the `shared`/`database_responses` includes, so curating them is a
  single edit at two call sites — not a survey. **Home: still c5-5.**
  **CLOSED, c5-5 (Q4, Brad 2026-08-08), and c5-2's narrowing was exactly right.** The fix was a
  single edit at two call sites, as predicted: `payload_too_large` removed from `health_responses`
  and `database_responses` in `build_app()`, and declared per-route on the two operations that can
  answer it — `POST /agent/events` (its own include) and `PUT /api/active-deck` (beside its
  existing `forbidden`). `error_responses` itself needed no change, which is what Q4 touching the
  *caller* rather than the helper was preserving.
  **Zero body-less GETs now publish an unreachable 413**, down from six. Pinned two ways, because
  an absence is easy to reintroduce: `test_routes_agent_events.py::
  TestTheCapIsDeclaredOnlyWhereItCanAnswer::test_exactly_the_two_body_bearing_operations_declare_it`
  walks the whole document and asserts the declaring set is exactly those two operations, and
  `test_errors.py`'s structural pin now asserts the `ErrorResponse` ref on the 413 where it is
  reachable instead of on `/health`. An R2 probe restoring the token to the shared health set
  reddened three tests plus the byte-snapshot guard.
  **What made it safe now and not at c3-9**: until c5-5 the token had no producer anywhere, so
  *every* declaration was unreachable and "which operations can answer it" had the empty set as its
  honest answer. Because the cap is middleware rather than a per-route dependency, the declaring
  set and the enforcing set are now the same two operations by construction. (Severity: closed.)

- **The image-discriminator prose is maintained by hand in two Python docstrings with no drift
  gate between them.** The same three paragraphs (split-card trap, per-face `image_uris`
  mutual-exclusivity, no-image-is-ordinary) live in `routes/cards.py`'s route docstring and
  `src/data/schemas/card.py`'s `Card` docstring, and regenerate into two places in the wire
  document. The byte-drift gates check Python↔generated only — a future correction applied to one
  docstring leaves the other confidently wrong on the same `openapi.json`. **Fix shape**: single
  source (one docstring states the rule, the other points at it), or a gate asserting the two
  descriptions agree on the discriminator sentence. **Home: c3-5**, which re-tells this rule for
  the image route and will make it three copies if unaddressed. (Severity: Low.)
  **RESOLVED by c3-5 (Q6, Brad 2026-08-01) — both halves of the fix shape, not one.** The rule is
  now the single constant `IMAGE_DISCRIMINATOR` in `src/data/schemas/card.py`, attached as the
  `description=` of `Card.image_uris`, `Card.card_faces` and `CardFace.image_uris`; both route
  docstrings state only what their own operation does and point at the fields. The gate is
  `test_committed_schema.py::TestTheImageDiscriminatorIsStatedOnce`, keyed on the **family** — any
  wire description mentioning both "per-face" and "image_uris" must *be* the constant, so a
  reworded fourth copy fails rather than a missing one. It caught the author's own `CardFace` class
  docstring on its first run, which is the guard working before review saw it.

- **`card_faces` is untyped on the wire — the discriminator rule has no `tsc` support.**
  `Card.card_faces` is `list[dict[str, Any]] | None`, generating `{ [key: string]: unknown }[] |
  null` in `types.d.ts`, while four docstrings teach "decide by the presence of per-face
  `image_uris`". Every face access in the UI will be a hand-cast `tsc` cannot check. Ruled at the
  c3-2 round-2 review (Brad, 2026-07-31): the wire schema stays frozen as reviewed with PR #30
  open. **Fix shape**: a typed `CardFace` Pydantic model (`name`, `mana_cost`, `type_line`,
  `oracle_text`, `image_uris`), regenerated into the component set (pins move 7→8, now **9→10**
  after c3-3). **Home: c3-5 or c4-3, whichever consumes a face first** — and it must land with the
  regenerated types in the same commit. (Severity: Medium for c4-3's type safety, zero runtime
  impact today.)
  **RESOLVED by c3-5 (Q4, Brad 2026-08-01), with two consequences the entry did not price.**
  `CardFace` ships with `model_config = ConfigDict(extra="allow")` — a strict model would have
  truncated `lookup_card_by_name`'s output for 6,455 face objects carrying 24 distinct keys, and
  `tests/unit/data/test_card_face_schema.py` proves the round-trip loses no key and changes no
  value (plus a counterfactual showing a strict model *does* truncate). Components 11 → 12; the
  generated type is an intersection with an open index signature, so c4-3 gets both the named
  fields and the unnamed ones. The two unpriced consequences: (1) five call sites outside the
  companion read faces with `.get(...)` and `mypy --strict` forced them to attribute access —
  `classifiers.py`, `mana_base.py` ×2 and `view_model.py` ×2, the last inside `src/viewer`, which
  c3-5's story text listed as not-touched; (2) named fields are now always serialised, so a face
  that omitted one carries an explicit `null` where it previously omitted the key. Additive, never
  a truncation — and it made "presence of per-face `image_uris`" mean *truthiness* everywhere,
  which three assertions in `test_routes_cards.py` were updated to say.

## Deferred from: story c3-3 (format check endpoint, 2026-08-01)

- **Rotation exposure cannot be computed from local data at all, and the panel now says so
  permanently.** Q3 (Brad, 2026-07-31) ruled that the row ships with status `advisory` rather than
  being omitted, so the gap is visible instead of silent — but it is a row a user can never
  resolve. Measured read-only against the shipped 38,261-card database, not assumed:
  `PRAGMA table_info(cards)` returns **23 columns** and none is a release date (`released_at`
  absent, `set_type` absent); `sqlite_master` contains **no sets table** of any kind; and
  `src/data/importers/aggregate.py:113-134` **does** read `released_at` — to pick the canonical
  printing by greatest date, ties by min id — and then discards it without ever writing a column.
  **Fix shape, priced honestly**: a `released_at` (or `set_type`) column on `cards` *or* a new
  sets table; an importer change to persist it; a hand-written `scripts/migrate_*.py` (this
  project has no Alembic); a full re-import of ~38k cards; **and** a rotation-schedule source —
  Scryfall's bulk data does not say "this set rotates in 2027-09", so the schedule has to come
  from somewhere else or be hard-coded and maintained. That is comfortably its own story.
  **Home: unowned** — a dedicated data story, not a companion one. Until it exists, the advisory
  row is the honest answer and must not be quietly promoted to `pass`. (Severity: Low — a
  permanent shrug in a P0 panel, but an accurate one.)

- **A `restricted` card is reported as "not legal", which is wrong.** `deck_validator.py`'s
  legality branch splits `banned` off (c3-3, Q2) but leaves `restricted` falling through to
  `format_legality`, so a Vintage deck running one Black Lotus is told the card is not legal in
  vintage when it is legal with a **1-copy limit**. Deliberately unchanged by the split and
  pinned by `test_deck_validator.py::test_restricted_is_unchanged_by_the_banned_split` so a later
  change is a decision rather than a side effect. Latent today: measured 89 `restricted` legality
  entries corpus-wide (vintage 51 · duel 24 · tlr 10 · timeless 4) and **zero** restricted cards
  across all 40 real saved decks, with no vintage deck among them. **Fix shape**: a per-card copy
  limit that varies by legality value — which is a change to the copy-limit rule, not to the
  legality branch, and needs its own row vocabulary decision (does a restricted card over its
  limit report `copy_limit`, or a new `restricted` rule?). **Home: unowned** — its own story.
  (Severity: Low while no vintage deck exists; Medium the day one does.)

- **`_MIN_MAINBOARD = 60` applies regardless of format, and c4-10 put that in front of a person.**
  A deliberately documented Phase-1 limitation (D-1.6b) that until c3-3 was reported only to an
  agent, which could caveat it. The format-check panel renders the size row directly.

  ⚠️ **THIS ENTRY'S MEASUREMENT WAS BACKWARDS AND IS CORRECTED HERE (c4-10, Q13).** It read:
  *"brawl and standardbrawl are genuinely 60-card formats, so the **20** brawl-family decks in the
  real deck table are correct and only Commander is affected — and there are currently **0**
  commander decks saved, which is why nothing looks wrong today."* Every clause of that is wrong
  except the last. `deck_validator.py`'s own comment carried the same claim and is corrected in the
  same commit. **All four numbers, re-measured read-only at `4e31ea7` by driving the real ASGI app
  against the shipped database:**

  1. **This repo's own shipped skill contradicts the code comment.**
     `plugin/skills/format-legality/SKILL.md:76-78` — `Brawl (Historic) | **100 (exact)**` and
     `Standard Brawl | **60**`. They are two different formats; "brawl-family" conflated them.
  2. **The database agrees with the skill.** All **18** `brawl` decks have a mainboard of exactly
     **100** — min 100, max 100 — and 16 of them carry a `commander=1` row. There are **2**
     `standardbrawl` decks, genuinely 60.
  3. **There are 0 commander decks**, so the entry's named at-risk population is **empty**.
  4. **The actually-affected population is the largest single format in the table**: 18 of 40
     decks, **45%**, each shown `Mainboard has 100 cards; the minimum is 60.` for a format that is
     exact-100 rather than a minimum at all.

  No verdict changes today, because all 18 sit at exactly 100 — **the defect is in the sentence,
  not the badge**. A 61-card Brawl deck would be told `pass`; a 99-card one would be told the
  minimum is 60. c4-10 pins the sentence in its suite
  (`formatCheck.fixtures.test.ts`, AC 28) so the measurement survives outside this file.

  **Fix shape**: a per-format minimum (a dict beside `_SINGLETON_FORMATS`, keyed the same way),
  plus a vocabulary decision for EXACT-vs-MINIMUM formats — `the minimum is 100` is still wrong for
  Brawl, which wants exactly 100 — plus the "any number of copies" exemption cards the same scope
  note defers. **Declined at c4-10** with the MCP blast radius as the reason: `validate_deck` serves
  the agent tools as well as this panel, so the rule change moves `assess_deck_power`'s inputs too.
  **Home: unowned** — a `src/logic` rule story. (Severity: **upgraded to Medium** — it was Low
  while only an agent read it; from c4-10 it is on the glass for 45% of the deck table.)

- **The component-name set is pinned in TWO hand-synchronised places, and the story text named
  one.** `tests/unit/companion/test_routes_decks.py` and `test_routes_cards.py` each assert the
  exact `components.schemas` key set, so every schema-adding story edits both. c3-2's Debug Log
  recorded finding the second one by running the suite rather than by reading the story; **c3-3
  hit exactly the same thing again** — its own "must not break" list named the decks pin and not
  the cards pin. Twice is a pattern, not bad luck. **Fix shape**: one pin, in one place, imported
  by both — or a single `test_committed_schema.py` that owns every whole-artifact assertion and
  leaves the per-route files asserting only their own paths. **Home: c3-4**, the next
  schema-adding story, which will otherwise inherit the same surprise a third time.
  (Severity: Low — it fails loudly and names the fix.)
  → **CLOSED by c3-4 (Q5, Brad 2026-08-01).** It did inherit the surprise a third time — both pins
  went red together on regeneration — and then took the fix as written: the second fix shape.
  `tests/unit/companion/test_committed_schema.py` now owns the whole-artifact path set, component
  set, auto-422 absence and `securitySchemes` absence; `test_routes_decks.py` and
  `test_routes_cards.py` assert only that their **own** shapes are present. c3-5 edits one pin.

- **`ui/README.md`'s blind-spot map is still keyed on line numbers.** Homed on c3-3 by name and
  **declined by Brad at Q5 (2026-07-31)**, who took the `_is_ref_rooted` repair from the same
  question and left this one. Unchanged in substance from the c3-1 entry that raised it: the
  section is written as a durable index a reviewer consults instead of reading fourteen test
  files, and the first comment inserted near the top of a cited file invalidates every reference
  below it. c3-3 added its row keyed the existing way, so the map is one entry larger and no more
  durable. **Fix shape** (unchanged): anchor on a searchable marker string — the guard function
  name, or the declared-limit sentence itself — rather than a line number, and add a test that
  every cited anchor still resolves. **Home: unowned, re-ledgered.** Twice deferred now; a third
  story owing this README a review pass is the natural moment. (Severity: Low-Medium — a stale
  index is worse than no index, because it is trusted.)

- **`format_recognized` and the six-row shape are declared but unread until c4-10.** c3-3 ships a
  boolean the UI can branch on for "no format to check against" rather than making c4-10 parse
  the advisory row's prose, and a `CHECK_ORDER` a panel can rely on. No runtime code consumes
  either yet — the same declared-but-unread state c3-2's `states.ts` classification is in.
  **Home: c4-10** (the format check panel). If c4-10 renders the panel without ever reading
  `format_recognized`, that is a signal the field was over-built and it should be deleted rather
  than maintained. (Severity: Low.)

  ⚠️ **ANSWERED AT c4-10 (Q8), AND THE DELETE-SIGNAL FIRED — recorded rather than dressed up.**
  `CHECK_ORDER` is **consumed**: the panel renders the payload's order and re-sorts nothing, pinned
  by a test that feeds it a *reversed* payload and asserts the render follows it. **`FormatCheck.tsx`
  does NOT read `format_recognized`**, and the reason is a fact about the backend rather than an
  oversight here: the same function that sets it `false` also rewrites the `legality` and `banned`
  rows to `advisory` with `_unanswerable`'s sentence, so by the time a renderer sees the report
  *"this could not be checked"* is **already on the glass twice, in words**. A branch on the boolean
  could only re-state those two rows, and the layout deliberately does not change
  (`deck_validator.py:550-556`) — a class or `data-` attribute with no styling and no consumer
  would be decoration dressed as a read. The behaviour under that state IS pinned, against a
  declared-synthetic formatless report driven through the real component: six rows, both advisory
  sentences rendered, three `caution` badges, three `positive`, and **nothing negative**.
  **Disposition: the field is NOT deleted** (Python is untouched this story) and the question is
  re-homed — its real consumer is a **non-rendering** one (an agent, or the header pill Q4b
  declined). **Home: the C4 retro**, with the delete-signal recorded as fired for the panel.

- **`format_recognized: true` does not mean the format key is present in the card data.**
  `_KNOWN_FORMATS` is a hand-maintained frozenset in source; `legalities` comes from a separately
  imported database. If the two skew — `_KNOWN_FORMATS` updated for a new Scryfall format ahead of
  a user's re-import, which the upgrade notes acknowledge users defer — every card misses the key,
  `.get()` returns `None`, and every card is reported not legal. That is the exact "legality
  storm" `_KNOWN_FORMATS` was introduced to prevent, now rendered as a confident panel with
  `format_recognized: true` and no advisory. **Not reachable against a synchronised snapshot**:
  measured 2026-08-01, all 38,261 cards carry all 23 keys, and `set(keys) == _KNOWN_FORMATS`
  exactly. A second edge in the same area: a *present-but-null* legality value
  (`{"standard": null}`) fails `Card` validation — `legalities: dict[str, str]` coerces only a
  wholly-null dict — so the route answers `500 internal_error` rather than a report. **Fix shape**:
  derive the known-format set from the data (a `SELECT DISTINCT` over the keys) instead of
  hard-coding it, or gate `format_recognized` on the key being present in at least one card.
  **Home: unowned** — it belongs with whatever story next touches `_KNOWN_FORMATS`.
  (Severity: Low today, Medium on version skew.)

- **The format-check report's `format` is the normalised value; the deck detail route's is the
  stored one.** `GET /api/deck/{id}` serves `deck.format` verbatim while
  `GET /api/deck/{id}/format-check` serves `format.strip().lower()`, because the report should
  name what was actually checked. Latent: measured **0 of 40** real decks store a format that
  differs from its own normalisation, so the two endpoints agree on every deck that exists today.
  A UI comparing the two strings would nonetheless be comparing two different things. **Fix
  shape**: either normalise at write time in `create_deck` (making the divergence impossible), or
  document the asymmetry where c4-1's store holds both. **Home: c4-10 or c4-1**, whichever first
  holds both values at once. (Severity: Low.)

  ⚠️ **THE HOME CONDITION IS NOW MET, AND c4-10 CLOSED IT BY CONSTRUCTION (Q14).** That story is
  the first thing in the app to hold both values at once — `DeckBadges` renders the **stored**
  format in the header and the format-check panel holds the **normalised** one 24px away. **The
  panel renders no format string in its own chrome at all**: it has no headline (Q4) and its six
  labels are format-independent, so the two values are never compared and the divergence never
  reaches a comparison. Asserted by test over the panel's title and its six labels. Re-measured:
  still **0 of 40**. Note the one place the normalised value *does* reach the glass — the `detail`
  sentences interpolate it (`Every card is legal in brawl.`), which is DATA arriving from the wire,
  beside the stored value in the header. On today's corpus they read identically. **The underlying
  asymmetry is re-homed unchanged** (normalise at write time in `create_deck`): closing it by
  construction in one consumer is not the same as fixing it. **Home: unowned** — a `src/data`
  story. (Severity: Low.)

## Deferred from: code review of c3-3-format-check-endpoint-over-the-existing-validators (round 2, 2026-08-01)

- **`is_legal: false` above six non-violation rows is a live UI trap, mitigated only by prose.**
  The report deliberately carries no honest headline field (Q4: one shape always, mirrors the
  validator); a renderer must synthesize the verdict from `format_recognized` plus a row scan,
  guided only by the `Warning:` docstring block on the wire. Nothing machine-checkable stops
  c4-10 from binding `is_legal` straight to the panel headline — a formatless deck would then
  render a red headline over six rows none of which is a violation. **Home: c4-10** (the format
  check panel), plus a named line on the epic C3 manual-testing checklist. (Severity: Low here,
  Medium if c4-10 binds it unread.)

  ✅ **CLOSED AT c4-10 (Q4, AC 19), AND THE "nothing machine-checkable" CLAUSE IS NO LONGER TRUE.**
  `is_legal` is bound to **nothing**: no headline, no summary badge, no `Panel` `count`, and no use
  of `Panel`'s own `badges` slot — that third venue ruled against explicitly rather than overlooked,
  because no component in the app has ever used it and nothing currently exercises it. The prose
  `Warning:` block is now a **guard**: `tests/format-check-source.test.ts` walks `git ls-files` over
  `src/`, strips comments, and asserts the identifier `is_legal` appears nowhere outside
  `src/api/types.d.ts` and the test files — with a non-vacuity half proving the scan can see the
  identifier where one really is, and proving that `schema.ts`'s doc comment about the trap is
  exempted by comment-stripping rather than by skipping the file. The trap itself is a **passing
  test**: the declared-synthetic formatless report carries `is_legal: false` with zero violation
  rows, and the panel renders three `caution` badges, three `positive`, and no `badge-negative`.
  Live exposure remains **zero** (the trap needs an unrecognised format; all 40 real decks have
  one), which is exactly why the guard rather than the corpus is what protects it. Verified by
  probe (c): binding the field reddens the suite, closed by that named test.

- **The copy-limit row answers definitively under the 4-copy fallback for a format it cannot
  interpret.** Greptile P1 on PR #31, ruled ledger-not-fix (Brad, 2026-08-01). For an
  unrecognized format (`edh`, `explorer`), `validate_deck` falls back to the ordinary 4-copy
  rule — an unknown key is never in `_SINGLETON_FORMATS`, pinned by `TestFormatSetInvariant` —
  and `format_check` renders that as a definitive `copy_limit` pass/violation, though the format
  the user *meant* may be singleton (edh → commander caps at 1). Mitigations already on the wire:
  the same report carries an `unknown_format` violation, `format_recognized: false`,
  `is_legal: false`, and advisory legality/banned rows, so the panel is loudly not-a-verdict.
  **Fix shape**: when `format_recognized` is false, the copy_limit row goes advisory like
  legality/banned ("could not be checked against an unrecognized format") — a one-branch change
  in `format_check` plus its firing/silent pair. **Home: the same unowned `src/logic` rule story
  as the per-format-minimum entry above** — the two are one "format-aware structural rules"
  decision. (Severity: Low — reachable only by a deck whose stored format is invalid, and the
  report already refuses to be a verdict.)

## From story c3-4 (the active deck), 2026-08-01

- **No pre-parse request-body cap anywhere in the app.** Measured at c3-4 Task 0 against the
  installed FastAPI **0.140.0**: `get_request_handler`'s inner `app(request)` reads and parses the
  body at `fastapi/routing.py:423-448` and calls `solve_dependencies` at `:473` — **body first,
  dependencies second**. So c3-4's agent-token dependency does *not* stop an unauthenticated caller
  from making the process buffer an arbitrarily large body on `PUT /api/active-deck`. What c3-4
  shipped instead is a **field** constraint (`ActiveDeckRequest.deck_id`, `max_length=256`), which
  is honest about being applied *after* parsing and bounds only what is stored. Q4 weighed building
  the real cap here and declined: it is a middleware-shaped mechanism, it would be designed against
  one story's requirements in a story whose body is ~40 bytes, and it should be **one** mechanism
  covering both endpoints. Mitigations that genuinely exist today and are worth not re-deriving:
  the `Host` envelope refuses anything that did not address the app as loopback on the bound port,
  and the app installs **no CORS middleware at all** (C1's no-CORS ruling), so a cross-origin `PUT`
  with a JSON content type is preflighted, the `OPTIONS` gets a `405`, and the browser never sends
  the body. **Home: c5-5**, which owns `payload_too_large` — a token declared since c1-4 that still
  has **no producer** — and AD-7's 64 KB envelope limit. (Severity: Low — a loopback port behind
  `Host` validation, reachable only by local software that could do worse directly. But "the first
  endpoint with a body shipped with no thought about body size" is a sentence worth never writing.)
  **CLOSED, c5-5 (Q2, Brad 2026-08-08).** Built as `src/companion/app/body_cap.py`'s
  `BodyCapMiddleware` — pure ASGI, installed by `install_body_cap(app)` before `install_security`
  so it ends up innermost of the three middlewares. It enforces `Content-Length` first (a courtesy
  that refuses an honest client without a transfer) and a **counted-bytes** bound second (the one
  that actually holds, since a caller controls its own headers), sends `error_response(
  "payload_too_large")` rather than raising — the c1-5 ruling, and an R2 probe confirmed a raise
  here surfaces as a false `500` on six tests — and never calls the inner application for an
  over-cap request, so no route can ever receive a partial body.
  **Every requirement this entry set was met:** one mechanism, both endpoints (`POST /agent/events`
  *and* `PUT /api/active-deck`, neither containing a line about size); middleware-shaped as Q4
  predicted; and designed against the 64 KB envelope rather than against one story's ~40-byte body.
  `payload_too_large` has a producer for the first time since c1-4.
  **One measurement the entry could not have anticipated, recorded because it changes how the two
  caps relate.** They are **not nested**: a `groups` envelope with every string at its field limit
  and every list at its length serialises to **104,067 bytes**, 1.6x the ceiling, while violating no
  field cap at all. So the byte cap can refuse a payload pydantic would accept, and the two
  rejection classes overlap rather than partitioning the input. The byte cap wins when both apply,
  because it runs first.

- **There is no way to clear the active deck over the wire.** `ActiveDeckRequest.deck_id` is
  required and does not accept `null`, so the only transitions are *set* and *process restart*
  (Q3 part 3, Brad 2026-08-01). Nothing in the epic asks for a clear verb: FR-11's "deck deleted →
  no-active-deck" is a **client-side** transition (`EXPERIENCE.md:120` — the refetch 404s and the
  SPA clears to the panel), and a restart clears the slot anyway. Building an unused verb now would
  freeze a wire shape with no consumer. **Home: unowned** — whichever story first has a *caller*
  that needs it. **The shape it should take if wanted**: a `DELETE /api/active-deck`, not a nullable
  request field — the request model staying non-null is what keeps `PUT` unambiguous.
  (Severity: Low.)
  **c6-2 did NOT trigger it (2026-08-09).** The entry named this story as the most plausible
  candidate; it shipped `companion_set_active_deck` with no "stop displaying" mode because nothing
  asked for one, and touching `ActiveDeckRequest` was explicitly out of scope. The entry stays open
  and unowned, one candidate poorer.

- ~~**Nothing broadcasts the change.**~~ **✅ CLOSED by c5-4 (2026-08-08).** `PUT /api/active-deck`
  now awaits `ws.broadcast_active_deck_changed(request.app, slot.deck_id)` after the store and
  before the return — one line, exactly where the comment reserved it, and the comment is gone. The
  seam cost no scaffolding to remove, which is the entry's own prediction confirmed.
  **One correction to this entry, which predated c5-1**: it says the value broadcast is "the same
  `ActiveDeck` shape". The wire object is an `ActiveDeckChangedEvent` — the `{kind, id, ts,
  payload}` envelope AD-6 specifies — whose `payload` is an `ActiveDeckChangedPayload`, a
  *different class* sharing the same field and nullability (`{deck_id: string | null}`) but **not**
  the same bound — `ActiveDeck.deck_id` is a bare `str | None` with no length cap and no
  blank-refusal, while `ActiveDeckChangedPayload.deck_id` caps at `_MAX_DECK_ID_LENGTH` and refuses
  a blank string (review finding, 2026-08-08 — an earlier version of this correction claimed "same
  bound", which was itself wrong). So the entry's reasoning holds and its noun does not; c5-1
  minted the separate payload class deliberately, so a later deck-agnostic signal can diverge in
  validation without touching this endpoint's contract — which is exactly what happened. Nothing
  rippled, and the schema pins did not move (8 paths / 13 components, `gen:api` byte-identical).

- **`errors.supported_methods` walks framework internals to repair the `Allow` header.** c3-4
  found that Starlette 0.48.0 builds a 405's `Allow` from the **first** partially-matching route
  alone (`routing.py:738` keeps `partial` only if it is `None`; `Route.handle` at `:283` joins
  *that* route's methods), so `/api/active-deck` — the first path in this app served by more than
  one method — answered `Allow: GET`, omitting the `PUT`. RFC 9110 §15.5.6 requires the field to
  list the *resource's* methods, so this was wrong and not merely terse. The repair recomputes the
  union, which needs a flattened route list, and FastAPI 0.140 does **not** flatten included routers
  into `app.routes` — it stores lazy `_IncludedRouter` wrappers. `_leaf_routes` therefore walks
  `original_router`/`routes` **by attribute**, so an upstream structural change degrades to "found
  nothing" and the caller keeps Starlette's own header rather than raising inside an error handler.
  That is a deliberate soft failure, and it means **a FastAPI upgrade could silently restore the
  incomplete header**. `test_routes_active_deck.py::TestTheMethodSemantics` is what would catch it.
  **Home: unowned** — revisit if FastAPI ever exposes a public flattened route list, or if a third
  multi-method path appears. (Severity: Low — the failure mode is a less-informative header, never
  a wrong status or a leaked body.)
  **Second hole, found at review (2026-08-01):** the flattened children are matched against the
  **un-stripped** scope, and Starlette strips a mount's prefix into `child_scope` before children
  match — so the walk is correct only while every mount sits at `/`, which is true today and
  asserted by nothing. A future non-root `Mount` (c5-x static assets, an `/agent` sub-app) makes
  children silently never match (or a child at `/` match paths it does not serve). Different hole
  from the soft failure above: that one finds no leaves; this one finds them and asks the wrong
  question. Documented in `supported_methods`'s docstring. **Home: the story that adds a non-root
  mount.** (Severity: Low — latent until such a mount exists.)

- **A third pin on `NO_UI_RESPONSE` was not in c3-4's ripple table.** The story's landmine-12 table
  named seven ripple sites for an eighth reason token and listed two frontend pins on the
  panel-less classification (`states.ts`'s `satisfies` clause and `states.test.ts:60`'s exact
  array). There is a **third**: `ui/tests/unknown-card-copy.test.ts` parses `states.ts`'s source and
  asserts `noUiResponseMembers()` equals the exact list, as a non-vacuity anchor for its own
  card_not_found pin. It went red on `forbidden` and was edited by name. Not a defect — the pin is
  correct and caught a real omission — but the **count** is folklore that a story text got wrong,
  which is exactly the shape c3-2's "a true count read as a false rule" lesson warns about.
  **Fix shape**: nothing to build; the next story adding a reason token should grep for
  `NO_UI_RESPONSE` rather than trusting any enumerated list, and the comment added at that line now
  says so. **Home: unowned, informational.** (Severity: Low — it fails loudly and names itself.)

## Deferred from: code review of c3-4 (2026-08-01)

- **The pre-auth body-buffering deferral now has a test pinning the ordering.** The c5-5 body-cap
  entry above stands, with one addendum the review surfaced: `test_routes_active_deck.py::
  test_a_malformed_body_without_a_credential_is_still_forbidden` pins that FastAPI parses the body
  *before* solving the credential dependency (400-vs-403 is observable unauthenticated). c5-5's cap
  must consciously decide whether that pin is a contract or a snapshot — a middleware-level cap
  changes the observable order and would red the pin. **Home: c5-5.** (Severity: Low on loopback;
  it is also a free validation oracle for unauthenticated callers until the cap lands.)
  **DISPOSITIONED — ENTRY CLOSED, c5-5 (Q3, Brad 2026-08-08). Ruled: SNAPSHOT.** Nothing designed
  that order; FastAPI did, and the pin recorded a measurement of 0.140.0. So the story was free to
  change it, and the fail-cheap order (refuse on size before buffering or authenticating) is the
  right one.
  **What the ruling predicted did not happen, and the difference is the useful part.** The entry —
  and the story's own Q3 — expected the middleware to redden this pin. **It did not** (measured
  2026-08-08, full suite). The cap only reorders *oversized* bodies, and both bodies the pin drives
  are a few dozen bytes, so both original assertions held untouched. The disposition therefore cost
  an **addition** rather than a revision: a third assertion pinning that an oversized body answers
  `413` with no credential at all, so the whole total ordering (size, then body, then credential) is
  legible in one test rather than split across two files. No assertion was deleted and nothing went
  through review as a revision, because there was nothing to revise.
  **The free validation oracle this entry mentions is now narrower but not gone**: an
  unauthenticated caller still learns 400-vs-403 for well-sized bodies. That is unchanged by c5-5
  and remains unowned.
- **A future hand-raised 405's deliberate headers are overridden or case-split by the `Allow`
  recompute.** `errors.py`'s 405 branch replaces any author-supplied `Allow` with the
  partial-match union — which, for a request that *fully* matched the raising route, excludes that
  route's own method — and a case-mismatched `"allow"` key survives the `{**headers, "Allow": …}`
  merge as a second header. Unreachable today: no code raises 405 manually. **Home: unowned,
  ledgered** — the first story that hand-raises a 405 owns it. (Severity: Low — latent.)

## Deferred from: story c3-6 (the image pacer, 2026-08-01)

- **The epic's CM-2 acceptance criterion is not satisfied by c3-6 and is not paraphrased into
  something adjacent.** *"An image fetched once is not fetched again within the cache lifetime"*
  (epic :1728-1730) is the **disk cache**. There is no cache in c3-6, so a repeat request repeats
  the fetch — the pacer changes the *rate* of fetches, never their *number*. Recorded in
  `images.py`'s module docstring and in the story record as well as here, because an unsatisfiable
  claim gets an owner rather than a rewording. ~~**Home: c3-7.**~~ **CLOSED by c3-7, 2026-08-01.**
  `images.DiskCache` ships and `test_routes_card_image.py::TestARepeatRequestMakesNoCdnRequest`
  asserts it on `Recorder.requested` — one recorded URL for two requests — rather than on a second
  `200`, which c3-1's R1 finding showed passes with the mechanism deleted. Two things the entry
  did not price, both now measured: the warm path also had to skip the **pacer** (a cache checked
  inside `pacer.slot()` satisfies CM-2 and still takes 9.9 s to paint a warm deck), which is
  asserted on c3-6's injected clock as **98 spacing intervals cold, zero warm**; and the claim
  needed a **file on disk** asserted beside the fetch count, because a route that answered twice
  from one in-memory value would satisfy the fetch count alone. (Severity: Medium → **resolved**.)

- **In-flight coalescing is declined on ownership, not on merit** (Q5, Brad 2026-08-01). Two
  *simultaneous* requests for the same URL each get their own fetch; a semaphore does not prevent
  that shape and ~15 lines would. Declined because the thing being shared is a **result**, and
  whether that result is bytes, a disk path or a `Future` depends entirely on what c3-7 builds —
  building an in-flight map here means c3-7 inherits a second cache or deletes one (c3-4's ruling:
  *an unused hook is a design decision made by a story that cannot see the requirements*).
  **Measured cost today: zero extra fetches** on both 99-distinct-id decks, because duplicate
  printings collapse in `deck_cards` before they reach the route. **The trigger that flips this
  answer is c6-4** — suggestion rows beside the deck grid are the first surface that would render
  the same card id twice on one screen. ~~**Home: c3-7**~~ — **c3-7 DECLINED IT AGAIN and re-homed
  it on c3-8** (Q5, Brad 2026-08-01), **and the reason changed**, which is the part worth
  recording. c3-6 declined it for not knowing the result's shape; c3-7 built that shape (bytes on
  disk) and declined it anyway, because **c3-8 needs the same structure for a different question**
  — *"is a fetch for this key already in flight, or already known-failed?"* — so an in-flight map
  built here for successes only would be inherited wrong or replaced. One mechanism, built once,
  by the story that can see both halves. What declining costs, stated rather than glossed: two
  simultaneous requests for one key both fetch and both write, and on Windows the loser's
  `os.replace` raises `PermissionError` — **observed live** during c3-7's implementation, when a
  99-request burst over one id logged exactly that, and it is a log line rather than a failed
  request (c3-7 AC 9). ~~**Home: c3-8**~~ — **c3-8 DECLINED IT A THIRD TIME and re-homed it on
  c6-4** (Q6, Brad 2026-08-02), **and the reason changed AGAIN — this time because its predecessor's
  reason did not survive contact.** c3-7 re-homed it here on the expectation that *"c3-8 needs the
  same structure for a different question — is a fetch for this key already in flight, or already
  known-failed?"*. **It does not.** A negative cache needs no in-flight state to be correct: a
  request whose fetch is in flight simply also fetches, and the failure is recorded when it fails.
  Nothing in c3-8's AC 4-11 asks otherwise, and the shipped mechanism has no in-flight concept at
  all. *"Is a fetch already in flight"* was c3-7's phrasing of a hypothetical, not a requirement of
  anything. What coalescing actually shares is a **124 KB payload across two awaiting requests** —
  a `Future` holding bytes, with a cancelled leader and an exception fanned out to followers, each
  needing its own tests — which is a **different mechanism** from a small expiring failure record,
  not the same one. So the "one mechanism, built once, by the story that can see both halves"
  argument dissolves: there were never two halves. **Home: c6-4**, unchanged as the forcing
  function and now the sole owner. Recorded plainly because three consecutive declines is a pattern
  worth a human's eye: c3-6 declined for not knowing the result's shape, c3-7 because the shape was
  shared with c3-8's, and c3-8 because that sharing turned out not to be real. If c6-4 also
  declines it, the entry should be closed as "not wanted" rather than moved a fourth time.
  (Severity: Low today; Medium at c6-4.) — **NOT TRIGGERED BY c6-4 (checked 2026-08-10), and the
  home looks mis-aimed by one story.** Every re-homing above describes c6-4 as *"suggestion rows
  beside the deck grid"*, i.e. a rendered surface. The epic split did not put that surface here:
  c6-4 is the **push tool only** — a Python `@mcp.tool()` that mints an envelope and POSTs it —
  and the shipped SPA deliberately drops the `suggestions` kind, so this story causes **zero image
  requests** and cannot render one card id at all, let alone twice. The first surface matching the
  trigger's own words is **c6-7**'s suggestions view (c6-5/6 build the shell and the open/replace
  behaviour). Not re-homed unilaterally, because the entry says a fourth move should be a
  deliberate close instead: **STAYS OPEN**, and whether to re-aim it at c6-7 or close it as "not
  wanted" is a ruling for Brad, not an implementation detail of this story.
  **CLOSED AS "NOT WANTED" — Brad's ruling at c6-7 (2026-08-11), as recommended.** The entry
  asked for a deliberate close rather than a fifth move, and c6-7 is the surface its own trigger
  words named, so this is the decision made where it was owed rather than deferred again. Three
  things settle it. **The harm is a log line**: with a cold backend cache, two *concurrent*
  fetches of one key make the Windows loser's `os.replace` raise `PermissionError` — observed
  live at c3-7 — and the request still succeeds, so nothing reaches the glass. **The single-tab
  trigger is impossible by construction**: `companion_show_suggestions` de-duplicates item ids
  (c6-4), and c6-7's view hydrates and draws one request per UNIQUE id, so one tab asks for each
  picture once; only two tabs racing a cold cache can collide at all. **The cost is a backend
  single-flight `Future` with cancelled-leader and exception-fan-out semantics plus its own test
  matrix**, in a story that is otherwise frontend-only and whose Python suite is pinned unmoved.
  Three previous owners (c3-6, c3-7, c3-8) each declined it on the same reasoning. If a future
  story makes concurrent same-key fetches ORDINARY rather than incidental — a warm-cache
  prefetch sweep, or a multi-tab session that is designed for rather than tolerated — it should
  be raised fresh against that story's own evidence, not reopened from here.
  **Annotated by code review (2026-08-11), ruling not reopened.** "The single-tab trigger is
  impossible by construction" is true of requests originating from `companion_show_suggestions`
  alone, but misses one narrower case this story's own code names: `renderableOf`'s docstring
  in `SuggestionsView.tsx` calls out "a suggested card that happens to be IN the open deck" as a
  reachable render tier — for that card, the DECK's own image sweep and THIS VIEW's hydration
  effect could both address the same `card_id` in the same tab, which is the same concurrent-
  same-key shape as the two-tab case. The closure still holds: the residual harm at this
  trigger is the identical benign log line (a `PermissionError` on the losing `os.replace`, with
  the request still succeeding), so the cost/benefit that declined a single-flight `Future` for
  the two-tab case declines it here too. Flagged for whichever future story is the one that
  finally reopens this ledger entry, so the fuller trigger surface is on record.

- **The `DbSession` is held across the pacer's queue wait, and it works by arithmetic rather than
  by design** (Q6, Brad 2026-08-01 — accept, pin, ledger). **Measured, not assumed** (Task 0):
  FastAPI runs a `yield`-dependency's teardown *after* the endpoint returns, so the pool reports
  `checkedout() == 1` while `fetch_image` is awaited and `0` after the response. The pool is
  SQLAlchemy's default `AsyncAdaptedQueuePool`, **size 5 + overflow 10 = 15 connections,
  `pool_timeout` 30 s** — all four values read off the live pool object. At the shipped constants a
  99-tile burst drains in ~9.9 s, so at most 15 requests sit inside the route and the rest wait
  outside it: a second queue in front of the first, inefficient and harmless. **A pacer slower than
  roughly 0.3 s per tile would push the burst past the 30 s pool timeout**, raising
  `sqlalchemy.exc.TimeoutError` — which is **not** a `DatabaseError` and would therefore surface as
  `500 internal_error`, **not** `503`. Pinned by
  `test_routes_card_image.py::TestTheBurstDoesNotOutlastTheConnectionPool` so a later story that
  slows the pacer sees the cliff. The clean fix is to read the row, release the session, *then*
  queue — rejected here because it takes this one route off `DbSession`, the annotation c3-1…c3-5
  standardised on, for a problem that does not bite at these constants. ~~**Home: c4-1**, beside the
  hydration cache, which already carries this route's whole-row-read entry.~~ (Severity: Low at the
  shipped constants; High for whichever story changes them without reading this.)

  **RE-HOMED at c4-1 (2026-08-02, Q7) → c4-4.** This is a property of the **image** route's pacer
  and connection pool, and c4-1 touches neither: it ships a store slice and a JSON reader, adds no
  Python, and issues **no image request at all** (art reaches the screen through `<img>` and the
  browser's HTTP cache — there is no `fetch` for image bytes in `ui/src`). Homing it here on
  "beside the hydration cache" was a filing convenience, not a technical relationship. The story
  that will actually produce the burst this entry describes is **c4-4, the card-art grid** — the
  first surface that mounts ~99 `<img src="/api/card-image/…">` at once and therefore the first
  thing that can push the pacer queue past the pool timeout. **Home: c4-4**, and it should be read
  before that story changes any pacer constant.

- **`4` was declared out of c3-3's deck-construction-limit family, and that is a ruling made by
  c3-6 rather than a discovery.** `TestNoRuleInTheShell` bans the literals `60`/`15`/`4` anywhere
  in `src/companion`; `images.FETCH_CONCURRENCY = 4` is a CDN concurrency cap with no deck
  vocabulary near it, and the guard flagged it — **a structural pin this story did not name, the
  third consecutive story to hit one** (c3-2 Debug Log 3, c3-3 finding 2). The alternative was
  renaming a ruled production constant to appease a guard, which is precisely the obfuscation that
  guard's own docstring says to treat as a violation. `4` therefore joins `1` and the adjacent
  spellings (`3`, `5`, `16`) that were **already** declared out on exactly the ubiquity argument
  that applies to it; keeping it in was the order of discovery, not a stance. The copy limit stays
  covered by the `.quantity` family (enforcing it means counting copies). **Residual hole, stated:**
  a shell that counts copies without reading `quantity` — `len(rows) > 4`. **Home: unowned,
  ledgered**; declared in `ui/README.md`'s blind-spot table and probed in both directions.
  (Severity: Low — same class as the four holes the guard already declares.)

- **Both halves of the "never blocks the loop" AC that c3-6 could not satisfy have owners.** The
  epic's AC (`:1723-1726`) names a concurrent push through **`POST /agent/events`** meeting its
  250 ms budget while images are queued; **that endpoint does not exist until c5-1/c5-5**. c3-6
  proves the property against `/health` — five interleaved probes completing while every image
  fetch is parked upstream, with the *count* asserted so a serialised loop fails it — and records
  the substitution rather than passing it off as the same test. The literal AC is **17-3's**,
  whose own AC (`:3580-3582`) already says exactly that. Likewise the **real-bytes and
  real-latency** half of the cold-deck observation: c3-6 asserts ~9.8 s of modelled start offsets
  on an injected clock and states the 12 MB as arithmetic on a measured 124 KB average; measuring
  actual bytes over an actual network is **17-3's** (`:3588-3590`). **Home: 17-3** (both).
  (Severity: Low — deliberate scope, both named in the epic already.)

- **No ceiling on how long a request may queue, and no wire vocabulary for one** (Q4, Brad
  2026-08-01). The natural bound is the caller: a client that disconnects cancels the request and
  releases its slot immediately (pinned two ways). A ceiling would need either a **new reason
  token** — eight ripple sites, for a state no consumer can act on differently from
  `image_fetch_failed` — or a false reuse of the transient one. The fallback if a real queue ever
  misbehaves is to answer `image_fetch_failed` after N seconds queued, which only becomes
  meaningful once **c3-8** owns the retry semantics that would make a caller do something different
  with it. ~~**Home: c3-8**, if ever.~~ **DECLINED by c3-8, 2026-08-02 (Q7, Brad) — and the "if
  ever" now has a real argument against it rather than an absence of one.** The entry's own
  condition was met: c3-8 owns the retry semantics. The answer got *clearer* rather than closer.
  A queue ceiling would answer `image_fetch_failed` for a request that **never reached the CDN** —
  and the negative cache would then remember that non-event for 30 seconds, escalating on repeats.
  So a queue that is merely *long* would start **manufacturing remembered failures**, blanking
  tiles over congestion the CDN had no part in, which is strictly worse than the queue it was
  meant to bound. That is a new argument the entry did not have, and it is why this is recorded as
  a reason rather than as another "no measured symptom". The natural bound remains the caller: a
  client that disconnects cancels the request and releases its slot, pinned two ways. Written into
  `images.py`'s module docstring. **Home: none — closed on the merits.** Reopen only if a real
  queue misbehaves, and note that any reopening must also decide how the ceiling avoids poisoning
  the negative cache. (Severity: closed.)

## Deferred from: story c3-5 (card image endpoint, 2026-08-01)

- ~~**Between this story and c3-6 the image route fetches unpaced.**~~ **RESOLVED 2026-08-01 by
  c3-6.** `images.Pacer` ships: one semaphore (`FETCH_CONCURRENCY = 4`) plus request spacing
  (`FETCH_SPACING_SECONDS = 0.1`), constructed in the lifespan beside the client and passed to
  `fetch_image` as a **required** parameter, so no signature exists that fetches unpaced. The
  window was never reached by a browser — nothing under `ui/src` fetches an image until c4-4.
  The exemption this entry banked was carried through as instructed and is now written into the
  spacing constant's own docstring, gated by a test: the numbers are a good-citizen and NFR-05
  choice, **not** compliance with guidance that exempts `*.scryfall.io`.
  **What the entry did not price**, and c3-6 found by measuring: (a) a "hundred-tile deck view" is
  **67–99 distinct fetches, not 100** — basic lands collapse, median ~78 across the 18 saved decks
  with ≥90 cards; (b) the epic's "~12 MB over ~10 s" is not an independent observation but the
  **same arithmetic** that names the spacing constant (99 × 0.1 s = 9.9 s; 12 MB / 99 ≈ 124 KB, a
  `normal` JPEG); and (c) the database connection pool is a **second, invisible choke point** in
  front of the first — see the new c3-6 entries below.

- **The file extension is not derivable from the size key.** Measured over 40,960 stored image
  maps: `png` resolves to a `.png` URL 40,957 times and to a **`.jpg`** three times (the
  `errors.scryfall.com/soon.jpg` placeholders on Sparkspitter, Ondu Champion and Gorehorn
  Minotaurs); every other size is `.jpg`. c3-7's cache filename (`<size>_<face>.<ext>`) must take
  `ext` from the **resolved URL or the response `Content-Type`**, never from the size name. c3-5
  writes no file, and its route already echoes the upstream `Content-Type` for the same reason.
  ~~**Home: c3-7.**~~ **CLOSED by c3-7, 2026-08-01.** `images.cache_extension(url, content_type)`
  takes the URL suffix first and the header second, and **cannot consult the size key because it is
  not given one** — the signature is the guard, pinned by a test. Re-measured independently at
  implementation time: 245,760 URLs, `png` → `.jpg` exactly **3** times, all three cards named.
  Two things the entry did not price: **a third extension had to be decided**, and the ruling is
  *serve it, do not cache it* — not a raise and emphatically not a guessed filename (c3-2's "a true
  count read as a false rule"); and the **read** needs the same map as a candidate list, because
  the key excludes the extension, so a reader does not know which spelling its own writer chose.
  (Severity: Medium → **resolved**.)

- **Every stored URL carries a `?<timestamp>` cache-buster, and AD-11's cache key excludes it.**
  245,742 of 245,742 URLs carry one. c3-5 sends the URL verbatim (stripping it 404s upstream) but
  the AD-11 cache key is id + size + face, so a data refresh that changes the URL still hits the
  same cache entry. AD-11 **accepts that staleness explicitly**; recorded so c3-7 does not
  "improve" it by keying on the URL, which would silently make every refresh a full cache miss.
  ~~**Home: c3-7.**~~ **CLOSED by c3-7, 2026-08-01 — it did not "improve" it.** The key is id +
  size + face and the accepted staleness is now **asserted** in two directions rather than
  described: a refreshed row carrying a new `?<timestamp>` hits the existing entry
  (`test_images.py`), and three different cards sharing one URL produce **three** entries and
  three fetches (`test_routes_card_image.py`). The second was the entry's real content and it was
  a *prediction* — the shipped `errors.scryfall.com` test was expected to pass **unchanged** under
  a correct key, and it did, which is what makes "the key is not the URL" a measurement rather
  than an intention. What the entry did not price: `IMAGE_CACHE_CONTROL`'s docstring was written
  in the forward tense about this key and had to become present tense, and it is now worth saying
  that **both** caches accept the same staleness for the same reason — which is what makes
  stacking a browser cache on a disk cache free. (Severity: Low → **resolved**.)

- ~~**A fetch failure is answered and forgotten.**~~ **CLOSED by c3-8, 2026-08-02 — this story's
  headline.** `images.NegativeCache` remembers a failed key for 30 s, doubling per consecutive
  failure to a 300 s ceiling, bounded at 2,048 entries, cleared entirely on recovery. The
  prediction that it needed **no schema change** was half right and was **measured rather than
  assumed**: no path, no component and no reason token changed (7 and 12, before and after), but
  regenerating did produce a diff, because the story edited `ErrorResponse`'s class docstring to
  describe the new behaviour and a Pydantic model's docstring is published in full. Both generated
  files were regenerated and committed. The UI half needed nothing — `named-card-copy.test.ts`
  passed **unchanged**, so `EXPERIENCE.md`'s forward-dated promise became true without either side
  being edited.

- **An image request reads the whole card row.** AD-1 is satisfied by writing no query at all —
  `CardRepository.get_by_id` returns the `Card` the sibling route already answers with — so an
  image request pays for oracle text, legalities and every other column to read one URL. Ledgered
  rather than optimised: a narrow projection would be the second card shape AD-1 exists to
  prevent. ~~**Home: c4-1**, beside the hydration cache, which is the layer that could make this
  free.~~ (Severity: Low — local SQLite, one row.)

  **RE-HOMED at c4-1 (2026-08-02, Q7) → c4-4.** The theory — that the hydration cache is the layer
  that could make this free — does **not** hold, and saying so is the honest move. The cache holds
  the JSON record from `GET /api/cards/{card_id}`; the wasted read is on `GET
  /api/card-image/{scryfall_id}`, a route c4-1 never calls and whose consumer is an `<img>` tag the
  browser drives. No amount of caching card ROWS in the SPA changes how the image route reads one.
  **Home: c4-4** (the card-art grid), the first story that issues these requests in bulk and
  therefore the first that could measure whether the whole-row read is worth a projection.

- **`HEAD` and `Range` are not supported on the image route.** `GET` only. A browser will not ask
  for either on an `<img>`, and nothing in the feature needs them; `HEAD` would additionally
  require deciding whether to fetch upstream to answer it (which would defeat the point of a cheap
  probe). Declined deliberately. **Home: unowned, informational** — the story that gives an image
  a download or share affordance owns it. (Severity: Low — latent.)

- **A distinct "no such face" token was declined.** An out-of-range `face` answers
  `404 no_image_data`, the same token as a card with no artwork at all. AD-11 asks for *permanent*
  and *transient* to be distinguishable, not for two flavours of permanent to be, and
  `EXPERIENCE.md` draws the same named-Card placeholder for both — so a third token would cost
  eight ripple sites to express a distinction no consumer acts on. The **precedence** AC 9 asks for
  is structural rather than ordered: a card with no images resolves to an empty list, so every face
  is out of range and one comparison answers both. **Home: unowned, ledgered** — revisit only if a
  client is ever built that would act differently on the two. (Severity: Low.)

- **A partially imaged card would shift face indices.** `resolve_face_images` returns only the
  faces that carry images, in face order, so a card with an unimaged face 0 and an imaged face 1
  would serve that image at `face=0`. **Zero such rows exist** (a card's faces either all carry
  images or none do, measured across 38,261 rows) and the return type cannot represent a hole. The
  behaviour is pinned by a test so it is a decision on the record. **Home: unowned, latent** — the
  story that meets a real partially-imaged card owns it. (Severity: Low — unreachable today.)

- **A missing size key answers `no_image_data`.** Unreachable against the shipped corpus: exactly
  one key-set exists across all 40,960 image maps (`small`, `normal`, `large`, `png`, `art_crop`,
  `border_crop` — all six, always, never a subset), so a present map always resolves the requested
  size. That is a **true count of this corpus, not a Scryfall guarantee** (c3-2's lesson), so it
  justifies the absence of a size-negotiation branch and is deliberately **not** published to the
  wire as a promise. **Home: unowned, informational.** (Severity: Low.)

- **The MCP tool status vocabulary and the companion `ErrorReason` vocabulary share spellings and
  are different contracts.** The c3-3 skills-tree grep was run for this story and found no stale
  prose: `.claude/skills/**` and `plugin/skills/**` mention `card_not_found` and `deck_not_found`
  only as **MCP tool `status` values**, which predate the wire contract and are unrelated to it;
  neither of c3-5's new tokens appears anywhere, and no skill documents the companion's HTTP error
  contract at all. Recorded because the collision is a trap for **c6-1**, which introduces MCP
  tools that *do* consume the HTTP tokens: the same two words will then mean two things in one
  skill file unless the tool's outcome vocabulary is named deliberately. **Home: c6-1.**
  (Severity: Low now, Medium at c6-1.)

- **`error_response` now stamps `Cache-Control: no-store` on every typed error, feature-wide.**
  Added by c3-5 because a route structurally cannot attach a header — the point of deriving the
  status from the token — and RFC 9111 §4.2.2 lets a cache store a 404 heuristically with no
  explicit freshness, which would turn one transient image failure into a permanently broken tile.
  Applied to every token rather than the two that motivated it, since no modelled failure in this
  app is worth re-serving from a cache. Recorded as a **behaviour change to a shared helper** so a
  later story that wants a cacheable error knows it must argue for it. **Home: unowned,
  informational.** (Severity: Low.)

## Deferred from: code review of c3-5-card-image-endpoint (2026-08-01)

- **A refused or unparseable *stored* image URL answers `image_fetch_failed` — the transient,
  retryable token — though the refusal is a permanent fact of the row.** `contracts.py` defines
  the token as "transient … only this one may ever be retried", and c3-8's backoff will act on
  that; a disallowed origin or an unparseable URL cannot succeed on any retry. Brad ruled (2a,
  2026-08-01): keep the token, no wire change — c3-8, which owns the negative cache and backoff,
  decides retry semantics for permanently-failing URLs (e.g. an unbounded/permanent negative-cache
  entry for `is_fetchable` refusals). ~~**Home: c3-8.**~~ **DECIDED by c3-8, 2026-08-02 (Q3,
  Brad): ONE UNIFORM POLICY — no permanent entries, and the decision is closed rather than
  deferred again.** Three reasons, in order of weight. (1) **The class is unreachable against this
  corpus, re-measured read-only at Task 0**: all **245,760** stored image URLs are on the two
  allow-listed hosts and every one is `https`, so **zero** would be refused — a permanent-entry
  branch would be c3-4's unused hook exactly. (2) `fetch_image` deliberately collapses all eight
  failure causes into one token; distinguishing here means either widening that closed contract or
  re-implementing `is_fetchable` at the call site, which is a second truth about which URLs are
  fetchable and the thing AD-1 exists to prevent. (3) The error is asymmetric — a permanent entry
  for a URL that was *not* permanently bad is a tile broken until restart, while a 300 s ceiling on
  one that *is* costs one request per five minutes against a host that answers instantly. The
  corpus measurement is the evidence and is recorded as a fact about *this* corpus today (c3-2's
  "a true count read as a false rule"); it justifies the absence of a branch and is **not**
  published as a wire promise. Written into `images.py`'s module docstring. (Severity: closed.)

## Deferred from: code review of c3-6-paced-concurrency-capped-cdn-fetching-at-one-global-choke-point (2026-08-01)

- **httpx's closed-client `RuntimeError` escapes `_fetch_checked`'s `except` tuple as a raw 500**
  (`src/companion/app/images.py:751`). A request still queued in the pacer when lifespan teardown
  closes `image_client` gets `RuntimeError("client has been closed")` from `client.stream`, which
  is not in `(TimeoutError, httpx.HTTPError, httpx.InvalidURL)` and so surfaces as an unhandled
  500 traceback rather than `image_fetch_failed`. The window pre-exists from c3-5 (any fetch in
  flight at teardown); c3-6's queue widens it by the queue wait (~10 s on a cold deck). Uvicorn's
  graceful drain covers the normal shutdown path, and catching `RuntimeError` wholesale would
  reclassify programming errors as fetch failures — so the fix wants a narrower discriminator
  (message match or a shutdown flag), decided by whichever story next touches teardown.
  **Home: unowned.** (Severity: Low.)
- **Two hand-synchronised stall-able CDN fakes** (`tests/unit/companion/test_images.py:588`
  `Upstream`; `tests/unit/companion/test_routes_card_image.py:889` `StallableCdn`) — near-identical
  recorders (requested / in_flight / peak_in_flight / release `asyncio.Event`) maintained in two
  files; the ledgered two-copies defect class (c3-2 Debug Log 3, c3-3 finding 2), this time in test
  scaffolding. Consolidate into `tests/unit/companion/conftest.py` when a third consumer appears —
  c3-7's disk cache and c3-8's negative cache both stall CDNs and are candidates.
  ~~**Home: c3-7.**~~ **CLOSED by c3-7, 2026-08-01 — it was the third consumer, as predicted.**
  Both classes are gone; `conftest.StallableUpstream` replaces them, with `FakeClock` moved
  alongside it so a test module can reach either without importing another test module. What the
  entry did not price: **the two fakes had already drifted**, which is the whole hazard rather
  than the duplication itself — one recorded start times off a virtual clock and had no
  `completed` counter, the other counted completions and had no clock. The merged class carries
  the union with the clock **optional**, so a test that does not care about time does not build
  one. It also had to change a default: `StallableCdn` held every request unconditionally while
  `Upstream` took `hold=`, so the consolidated class defaults to *releasing* and its one stalling
  fixture now asks for `hold=True` explicitly — caught by three reds on the first run, and worth
  naming because "same class, different default" is how a consolidation reintroduces the drift it
  removed. (Severity: Low → **resolved**.)


## Deferred from: story c3-7 (the sharded, atomically written disk cache, 2026-08-01)

- ~~**The cache is unbounded: no eviction, no size accounting, no TTL, no index**~~ **DISCLOSED
  BY 15-2, 2026-08-18 — the eviction question itself stays open, in its own entry below.** (AD-11,
  epic :1768-1770 — deliberate in MVP, and no hook was built for a future one on c3-4's ruling). What
  15-2 inherits is a **measured footprint rather than a guess**: this user's whole 40-deck library
  is **1,061 distinct card ids**, and a single deck resolves to **67–99** of them; at one size and
  the epic's ~124 KB average that is roughly **130 MB** for the entire library, ~12 MB per deck.
  The 130 MB is *arithmetic over an average*, not a byte measurement — see the next entry. 15-2
  owns the documented location, the removal command and the uninstall notes; the cache root is
  `src.paths.data_dir()/image_cache` and it is safe to delete wholesale at any time, because every
  entry is reconstructible by refetching and nothing indexes it. ~~**Home: 15-2.**~~ **CLOSED by
  15-2, 2026-08-18 — the disclosure half.** `README.md`'s *Where the data lives → Image cache
  (companion app)* section now states the location, the two-character shard, the
  `PLANESWALKER_DATA_DIR` override, copy-pasteable inspect and clear commands for bash and
  PowerShell, the no-eviction ruling with the **measured** footprint (~90 KB per `normal` tile,
  8.5 MB per 99-tile deck, ~95 MB for the 1,061-id library) beside the epic's ~12 MB arithmetic
  estimate, the accepted staleness and the uninstall leftovers.
  `tests/unit/companion/test_image_cache_docs.py` keys every load-bearing claim on the shipped
  constants and executes the documented one-liner, so the prose cannot outlive the code. **No
  mechanism was built and none was in scope** — see the two lifecycle entries below, which stay
  open. (Severity: Low — a disclosure and stewardship gap, not a defect.)

- **Whether the cache should ever be bounded is still unanswered — only the disclosure closed.**
  Split out at 15-2's review (2026-08-18) because closing the entry above on its documentation half
  would otherwise have retired the substantive half with it: AD-11 declined eviction *in MVP* for
  want of a measured footprint, and that footprint now exists (~90 KB per `normal` tile, 8.5 MB per
  99-tile deck, ~95 MB for a ~1,000-printing library). The two lifecycle entries below are about
  the cache disabling *itself*, not about size, so neither of them inherits this question. Nothing
  is proposed here: at ~95 MB for an entire library, a policy would cost more in complexity than
  the disk it reclaims, and `README.md` now tells the user the one thing that actually bounds it —
  delete the directory. **Home: unowned**; the forcing function is a real report of the cache
  becoming inconveniently large, or a second rendition size shipping (which multiplies every figure
  above by the number of sizes cached). (Severity: Low.)

- ~~**The ~124 KB average tile size is arithmetic, never measured.**~~ **MEASURED AT THE C3
  RETROSPECTIVE, 2026-08-02 — and the epic's figure is a 38 % overestimate.** It was 12 MB ÷ 99
  tiles from the epic's own acceptance observation, and every footprint figure in this story
  (including the 130 MB above) inherited it. Measured by fetching all 99 distinct ids of
  `813d0434-…` (*Atraxa Counter Cabinet v2*) through the real route against the real CDN:

  | | Epic's arithmetic | **Measured** |
  |---|---|---|
  | per tile, `normal` | ~124 KB | **~90 KB** |
  | a 99-tile deck | ~12 MB | **8.5 MB** |
  | whole 1,061-id library | ~130 MB | **~95 MB** |

  Also measured for the first time, and the numbers c4-4 actually needs: **real Scryfall CDN
  latency ≈ 99 ms per image**, and a **warm read from the disk cache ≈ 10.3 ms per tile**
  (1.02 s for 99 sequential requests). The consequence for c3-6's constants is that they are now
  *vindicated by measurement rather than modelled*: throughput is
  `min(1/spacing, concurrency/latency)` = `min(1/0.1, 4/0.099)` = `min(10, 40.6)`, so **the spacing
  turnstile binds with 4× headroom on the semaphore** — exactly the regime the constants were
  chosen for. The `png`-vs-`small` variance this entry raises is untouched and remains real.
  **Home: 17-3** for the per-size profile; the grid-size figures above are now facts, not
  estimates. (Severity: Low → **resolved for `normal`**.)

- **A cache entry is never revalidated, so a corrected artwork is served indefinitely.** The key is
  id + size + face and AD-11 **accepts** that; a data refresh that changes a card's `image_uris`
  hits the existing entry. Today the only remedy is deleting the cache directory, which nothing
  documents (see the 15-2 entry above) and no tool offers. The shape that would fix it without
  reopening the key is a **generation stamp** — a cache subdirectory named for the database's own
  refresh marker — which costs nothing at read time and invalidates wholesale. Not built, because
  nothing in MVP knows when a refresh happened and inventing a marker for one consumer is the
  unused-hook mistake. **Home: unowned**; the forcing function is the first user-visible complaint
  about stale art, or whichever story gives the database a refresh timestamp. (Severity: Low.)

- **`os.fsync` is deliberately not called, so the cache is atomic but not durable** (Q3, Brad
  2026-08-01). A reader can never observe a partial file — that is temp + `os.replace` — but a
  power cut can lose a just-written entry, costing one refetch. Measured on this machine at Task 0
  (200 iterations, 124 KB): `fsync` costs **2.909 ms** against the whole write's **0.460 ms**, a
  6.3× multiplier, or 0.288 s of forced flushes on a cold 99-tile deck. **The ruling is the
  semantics and would stand at any price**; the number is corroboration. Recorded so that "the
  cache is atomically written" is never read as "fsynced" by a later story deciding what it can
  rely on. **Home: unowned** — nothing is expected to need this. (Severity: Low.)

- **Two simultaneous requests for one key both fetch and both write, and on Windows the loser's
  `os.replace` raises `PermissionError`.** The direct consequence of declining in-flight
  coalescing (see the re-homed c3-6 entry above). **Observed live** during implementation: a
  99-request burst over a single card id logged exactly that, and the request it belonged to was
  served normally — which is AC 9 working rather than a defect. It costs one duplicate fetch and
  one wasted write per collision. ~~**Home: c3-8**, which builds the in-flight map for its own
  reasons.~~ **RE-HOMED on c6-4 by c3-8, 2026-08-02, because the premise was wrong: c3-8 did NOT
  build an in-flight map, and needed none** (Q6 — see the coalescing entry above for why the
  shared-structure argument dissolved). This entry has always been a *consequence* of declining
  coalescing rather than an independent item, so it travels with it. **Home: c6-4**, which is the
  first surface that renders one card id twice on one screen and therefore the first that makes
  the collision ordinary rather than incidental. (Severity: Low.)

- **The one-write-site scan covers `src/companion` only, and it counts by module rather than by
  intent.** `TestExactlyOneImageWriteSite` asserts that rename-into-place happens in exactly two
  modules — `discovery.py` and `images.py` — once each. It would **not** notice a second write
  path that used a different mechanism entirely (`Path.write_bytes` straight to the target, a
  `shutil.copy` over it), because those are not renames; the *atomicity* claim is what the scan
  protects, not "nothing else writes". The complementary guard is
  `TestFileIoNeverRunsOnTheLoop`'s family, which does see `write_bytes` — but only inside an
  `async def`, and only in `images.py`. **A declared blind spot is still a claim**, so it is
  declared here rather than left to be discovered. **Home: unowned.** (Severity: Low.)
  **Updated by the 2026-08-01 review:** two rename-shaped spellings that were *inside* the
  claimed territory and undeclared — `Path.replace`/`Path.rename` (the pathlib rename-into-place
  the retired identifier ban did catch) and a call through a rebound local (`handler =
  os.replace`) — are now **caught by the scan**, discriminated from `str.replace`/
  `datetime.replace` by the one-bare-positional-argument signature. The declared blind spot is
  now genuinely limited to non-rename mechanisms, as this entry always said.

- **`_FILE_IO_CALLS` is a member list, not a module ban, and that is a knowingly weaker shape.**
  The C2 retro's standing agreement is *ban the family, never enumerate members* — but there is no
  module to ban here: the offenders live in `os`, `pathlib`, `tempfile` and the builtins at once,
  and `os` and `pathlib` are both needed on the sanctioned path. Import aliases are resolved, so
  the spellings that evade a member list are caught; what is **not** caught is a filesystem call
  whose name is not in the list (`os.truncate`, `os.link`, an `io.open`). **Home: unowned**;
  revisit if a later story adds a fourth file-touching mechanism. (Severity: Low.)

- **`images.py` now holds three mechanisms and is ~1,100 lines.** The spine draws the pacer, the
  disk cache and the negative cache inside `app/images.py` (`# proxy: pacer, disk cache, negative
  cache`), so c3-8 lands here too and makes it three. Splitting it is deliberately **not** this
  story's decision — that belongs to whoever finds the module unmanageable with all three shipped,
  not to the story that adds the second. Recorded so the growth is a noticed fact rather than a
  drift. ~~**Home: c3-8 or the C3 retro.**~~ **c3-8 DECLINED THE SPLIT and re-homed it on the C3
  retro, 2026-08-02 (Q8, Brad) — with the final number measured so the retro inherits a fact rather
  than an impression: `images.py` is now ~~1,475~~ lines** (1,307 at `3aef5d1`; the third mechanism
  and its docstrings added 168). All three mechanisms the spine's Structural Seed names are now in
  it (`app/images.py  # proxy: pacer, disk cache, negative cache`), so **splitting is now a decision
  to diverge from the spine** rather than a tidy-up — and that belongs to a retro with all three
  shipped and c4-1's hydration cache in view, not to the story that adds the third while writing it.

  **CORRECTED AND PARKED AT THE C3 RETROSPECTIVE, 2026-08-02.** The 1,307-at-`3aef5d1` figure is
  right; **the "now" figure was never re-measured and is wrong.** At `16976c5` — c3-8's own merge
  commit — and at HEAD the file is **1,837 lines**, a 362-line (25 %) undershoot. The entry existed
  specifically to stop the retro arguing from an impression and handed it one. Measured two
  independent ways (tokenizer and AST, agreeing to within 6 lines):

  ```
  src/companion/app/images.py            1,837 lines
    ├─ docstrings + comments             1,370   (74.6%)   1,279 docstring + 91 comment
    ├─ lines containing code               377   (20.5%)
    └─ blank                               289   (15.7%)
  ```

  Largest docstrings: module header **108**, `NegativeCache` 75, `DiskCache` 69,
  `_write_atomically` 67, `fetch_image` 65, `Pacer` 59, `resolve_face_images` 54.

  **This changes the shape of the decision.** 377 lines of code across three mechanisms and 39
  callables is ~125 lines each — not an unmanageable module. A split would divide *documentation*,
  and the 108-line module header is what explains the interaction a split would destroy (the cache
  is checked **before** the pacer; the negative cache sits **outside** `pacer.slot()`). The
  counter-argument from finding density — 5 of the epic's 10 Greptile findings, and every P1 from
  c3-5 onward, are in this file — is answered by noting that c3-5/c3-7/c3-8 are the three hardest
  stories in the epic: **density tracks difficulty, not line count**.

  Two adjacent actions were identified instead of a split: a **prose-freshness pass** over the nine
  large docstrings (this entry's own wrong number is an instance of c3-4's "prose outrunning code"),
  and the **review-added-mechanisms-re-enter-review** rule (C3 retro action item 12), which is what
  would actually have caught c3-7's sibling race and c3-8's carve-out.

  **DECISION PARKED by Brad, 2026-08-02**, pending the rest of the manual-testing checklist.
  ~~**Home: re-decide with c4-1's hydration cache in view.**~~ (Severity: Low.)

  **RE-HOMED at c4-1 (2026-08-02) → the C4 retrospective.** c4-1's hydration cache is now shipped
  and it is *in view*, so the disposition this entry asked for can be given: **the cache changes
  nothing about `images.py`.** c4-1 adds no Python at all, calls no image route, and its cache holds
  card ROWS — the three mechanisms in `images.py` (pacer, disk cache, negative cache) are untouched
  and un-approached by it. So the split question is exactly as open as it was, with one fewer
  unknown. Re-deciding it inside a frontend story would be deciding it on no new evidence.
  **Home: the C4 retrospective** — by then c4-4 (the art grid) and c4-6 (the flip control) will have
  exercised all three mechanisms against real decks, which is the evidence the decision actually
  wants. (Severity: Low.)

- **This machine's full-suite runtime is too noisy to support the before→after claim AC 24 asks
  for, and that is worth knowing before the next story tries to make one.** Three consecutive runs
  of *identical* code measured **118.40 s / 119.12 s / 167.56 s** — a **49 s spread**, ~40% of the
  median. The single baseline sample was 126.10 s, which sits inside that spread, so "the suite got
  faster" and "the suite got slower" are both unsupportable from single samples. An intermediate
  reading of 143.36 s during this story was initially attributed to the cache's disk I/O; that
  attribution was **wrong and is withdrawn** — it was background load.

  What *is* measurable, and what AC 24 actually wanted, is a **targeted** comparison rather than a
  whole-suite one: probe (b) removed the cache write entirely and the companion suite ran in
  **43.38 s** against **43.02 s** with the write in place, so the write costs nothing detectable —
  which is the specific thing AC 24 predicted would show up here *"and nowhere else"* had an
  `os.fsync` been added. **The lesson for later stories: compare the narrowest suite that contains
  the change, take more than one sample, and do not read a whole-suite delta on this box as
  signal.** **Home: unowned** — a measurement-practice note, not a defect. (Severity: Low.)

## Deferred from: code review of c3-7 (2026-08-01)

- **Q4's declined alternative — a sidecar carrying the upstream's full `Content-Type` — and the
  parameter divergence it tolerates.** A warm hit derives its media type from the stored
  extension, so any *parameters* the upstream sent (`image/jpeg; charset=binary`) are dropped on
  the second render of a tile; the media type itself always matches, by construction, since the
  review flipped `cache_extension` to derive the spelling from the same header the cold path
  serves (D1). The sidecar was declined because it doubles the entries on disk and reopens the
  atomicity question for a *pair* of files, to preserve a parameter no measured Scryfall response
  actually sends. Pinned by `test_the_one_named_divergence_is_the_content_type_parameter`; the
  c4-4-facing consequence is a `ui/README.md` blind-spot row. **Home: unowned** — the forcing
  function is an upstream that starts sending a parameter browsers act on. (Severity: Low.)

- ~~**Orphaned `.tmp` files from a hard kill accumulate with no sweep, ever.**~~ **CLOSED by
  15-2, 2026-08-18 — documented, as the entry itself asked.** `_write_atomically`
  cleans its temp file on every in-process failure, but a process kill or power cut between
  `mkstemp` and `os.replace` strands `<name>.<rand>.tmp` in the card's shard directory
  permanently: `_read_cached` never matches the suffix (invisible, so it costs nothing but
  bytes), no startup or periodic sweep exists, and the 15-2 stewardship entry above covers cache
  *content*, not write debris. A `rglob("*.tmp")` sweep at startup was declined: it walks a
  potentially 38k-directory tree on every launch to reclaim litter produced only by crashes
  mid-write. The wholesale remedy is 15-2's documented `image_cache/` deletion, which removes
  debris and content alike. ~~**Home: 15-2**, as one sentence in its stewardship notes.~~ **CLOSED
  by 15-2, 2026-08-18.** The README's *Safe to delete at any time* paragraph says exactly that: the
  wholesale delete "also removes any `*.tmp` write debris that a hard kill or a power cut stranded
  mid-write — nothing sweeps for those, and this is the intended remedy." Still no sweep, declined
  for the same reason as before. (Severity: Low.)

- **A transient startup `OSError` disables the cache for the whole process, with one WARNING at
  boot.** Q6's ruling covers root *creation* failure by disabling the cache and running on —
  correct for the named case (a *file* called `image_cache`), but a transient failure (AV
  briefly locking the data directory at boot, the exact Windows class this feature names
  elsewhere) has the same permanent consequence: every image fetches from the CDN until restart,
  announced only by a log line hours before anyone notices slowness. No retry, no re-attempt on
  first write. Declined here because a retry policy is a design decision c3-8's failure
  signalling is better placed to make consistently. ~~**Home: c3-8.**~~ **c3-8 TOOK THE OTHER
  ENTRY AND RE-HOMED THIS ONE ON 15-2, 2026-08-02 (Q4, Brad), and the reason is honest rather than
  tidy.** Of the two "failure posture over time" entries homed here, c3-8 took the unwritable-root
  one (below — it closed) and declined this one, because **retrying the root means deciding
  *when*** — at the first write? on a timer? after N requests? — which is a lifecycle question
  nothing in this feature measures and which c3-8 had no requirement to answer. Taking it would
  also have made `DiskCache` mutable in a way it is not, on top of the write-disable state that
  entry did add. ~~**Home: 15-2**, which owns cache stewardship (epic `:3185-3212`) and is where a
  lifecycle policy belongs beside the documented location and the removal command.~~
  **RE-RECORDED BY 15-2, 2026-08-18: DISCLOSED, STILL UNBUILT.** 15-2's intent was disclosure, not
  mechanism, and it declined this a second time with the reason unchanged and honest: **retrying
  the root still means deciding *when***, which nothing in this feature measures, and a story that
  writes documentation is not made able to answer that by owning the entry. What it did instead is
  tell the user: `README.md`'s *Two ways the cache switches itself off* paragraph states the
  behaviour, that every image is still served and everything already cached is still read, and that
  **restarting the app is the remedy** — so the failure is no longer discoverable only from a log
  line hours before anyone notices. `DISK_CACHE_WRITE_FAILURE_LIMIT`'s docstring records the same.
  **Home: unowned.** The forcing function is a **real report of a silently disabled cache** — a
  user, or a log, showing the companion refetching everything from the CDN for a whole session.
  That report is also the first measurement of *when* a retry should happen, which is the input
  this decision has always been missing. (Severity: Low — unchanged; requests are unharmed either
  way.)

- **A root that exists but is unwritable leaves the cache "enabled" and warns on every write,
  ~99 times per cold deck paint, forever.** `build_image_cache` probes only `mkdir` of the root;
  a pre-existing read-only directory (or ACLs changed mid-run) passes it, so every subsequent
  write fails and logs at WARNING with no disable-after-N and no startup writability probe. The
  requests themselves are unharmed (AC 9). A startup write-probe was declined as an effectful
  test-file in the user's data directory on every launch; log-rate limiting is c3-8-shaped.
  ~~**Home: c3-8**, beside the transient-startup entry above.~~ **CLOSED by c3-8, 2026-08-02
  (Q4, Brad — the half that was taken).** `DiskCache` now counts **consecutive** write failures and
  disables its own writes after `DISK_CACHE_WRITE_FAILURE_LIMIT = 5`, announcing it **once** with a
  message that says it is giving up and names the unwritable root. So a 99-tile cold paint logs at
  most five warnings instead of ninety-nine, and every paint after it logs none. Three properties
  gated rather than described: **reads keep working** (a root that just became unwritable may still
  hold everything a previous session cached, and NFR-06's offline claim depends on those reads);
  **one success resets the count**, so failures spread across a session cannot accumulate into a
  disabled cache; and the state is **per-instance**, never a module global. AC 9 is untouched — the
  picture is served either way and no reason token was added. The `deferred-work` pairing this
  belonged to is now split: this one closed, the transient-startup one re-homed on 15-2 above.

- **A third image format in the corpus would be served and never cached, silently degrading CM-2
  feature-wide — and the trigger that changes this is a measurement, not an argument.**
  `CACHE_MEDIA_TYPES` is a closed two-entry map (`.jpg`/`.png`), justified by the corpus: exactly
  two formats across all 245,760 stored URLs, `image/webp`/`image/avif` measured at **zero**.
  `DiskCache.write` therefore treats an accepted-but-unmapped `image/*` header as *served, not
  stored* — the ruled posture (Q4 + c3-2's "a true count read as a false rule": the count
  justifies the map; it does not justify caching under a guessed extension, which Greptile's
  round-1 P1 confirmed mislabels the bytes). Greptile's round-2 P1 flagged the flip side —
  *"accepted formats bypass the cache, violating CM-2"* — **declined by Brad (2026-08-02)**:
  CM-2 is satisfied for every image this corpus can produce, and caching formats measured at
  zero is the unused-hook mistake. The real exposure is a Scryfall format migration behind
  existing URLs, which would flip every write to the serve-not-store branch and announce itself
  only as a per-request `INFO` line while the cache quietly stops growing. **The trigger is
  written down so nobody re-litigates it**: the first *measured* third format in the corpus
  widens `CACHE_MEDIA_TYPES` by exactly one entry (extension + media type, warm/cold agreement
  preserved by construction) — a two-line change plus one discrimination test. **Home: whichever
  story first measures a third format** (the c8-x data-refresh surfaces are the likeliest
  observers); until then, unowned by design. (Severity: Low.)

- **`DiskCache` trusts its callers for containment: `card_id`/`size`/`face` are validated by the
  route's own constraints, not by the class.** `path_for("../../..", ...)` escapes the root —
  demonstrated by the containment test's own firing half — and nothing in the class refuses it;
  the route's `_CARD_ID_PATTERN`, the closed `ImageSize` literal and the bounded `face` are the
  whole guard, and they live in a different module. Deliberate under c3-4's unused-hook ruling
  (today's only caller is validated), but the module's next callers are already named — c3-8's
  negative cache in this same file, c6-4's suggestion tiles — and the first one that passes an
  unvalidated id gets a traversal write. ~~**Home: c3-8**, which touches this class next and
  should either validate at the class boundary or restate the trust chain in its own record.~~
  **c3-8 RESTATED rather than validated, 2026-08-02 (Q9, Brad), and the reason it is safe is
  STRUCTURAL rather than a promise.** Of the two options the entry offered, the second was taken
  because the first would have been protecting against this story rather than because of it:
  **`NegativeCache` builds no path at all** — it is a dict keyed on a tuple — so it is
  *structurally incapable* of being the caller that turns an unvalidated id into a traversal write.
  Adding validation on its account would have been an unused hook (c3-4's ruling) justified by a
  caller that cannot trip it. The trust chain is now written into `DiskCache`'s own docstring by
  name: `routes/cards.py`'s `_CARD_ID_PATTERN` (canonical lowercase uuid or `400`), the closed
  `ImageSize` `Literal`, and the bounded `face` — three constraints, all upstream of the key.
  **Home: c6-4**, now the *sole* remaining named caller, with the instruction carried forward: if
  c6-4 reaches `DiskCache` with an id from anywhere but a validated route parameter, validate at
  the class boundary first. (Severity: Low.)

## Deferred from: story c3-8 (distinguishable failure signalling and negative caching, 2026-08-02)

- **A cold paint against a dead CDN still costs ~124 seconds and all ~99 requests, once per
  process.** This is the exposure the negative cache does **not** close, stated as a ledger entry
  rather than only as prose because it is the thing a reader will most plausibly assume was fixed.
  99 tiles resolve to 99 **distinct** keys, so on the first paint nothing is remembered and every
  request is issued. Steady-state throughput is `min(1/spacing, concurrency/latency)` =
  `min(1/0.1, 4/5.0)` = **0.8 fetches/second** at the shipped `_FETCH_TIMEOUT.connect = 5.0`, so
  the paint takes roughly **124 s** — and the user watches 99 placeholders for two minutes. The
  backoff bounds every paint *after* that one, which is what `EXPERIENCE.md`'s "no request storms"
  means here. Closing it would need something that fails a *whole host* fast rather than a key at
  a time — a circuit breaker over `ALLOWED_IMAGE_HOSTS`, which is a fourth mechanism and a
  different shape from anything AD-11 asks for. **Home: 17-3**, which owns real-latency profiling
  and is the first story positioned to say whether 124 s is a real user experience or an artefact
  of an unrealistic failure mode. (Severity: Low today — it needs a CDN that is *unreachable*
  rather than merely slow; Medium if c4-4's manual testing finds it.)

- **The retention horizon is a fifth number Q2 did not fix.** Q2 ruled the base, the multiplier,
  the ceiling and the cap. Implementing it surfaced a fifth decision neither the story nor the
  question had named: **how long a key's failure history outlives its own backoff window.** It has
  to be longer than the window, or escalation is unreachable in production — an entry dropped at
  `retry_after` resets the count on every attempt, so a key against a permanently dead CDN cycles
  at the base delay forever while every "consecutive failures escalate" unit test still passes.
  c3-8 derived it as `retry_after + ceiling` rather than declaring a constant, so it cannot drift
  from the reasoning, and asserted it from both sides. Recorded because it is a **decision made
  during implementation rather than at context time**, which is exactly the kind that later reads
  as arbitrary. **Home: unowned** — revisit only if a real backoff misbehaves. (Severity: Low.)

- **`is_backing_off` never prunes, so up to 2,048 stale entries can sit in a quiet process.**
  The hot path is deliberately side-effect free: a dict lookup and one comparison, no walk. Pruning
  happens only on `record_failure`, so a process that fails a burst of keys and then goes quiet
  keeps those entries until something else fails. Bounded by `NEGATIVE_CACHE_MAX_ENTRIES` and
  therefore harmless — at most ~2,048 small tuples — and the alternative (pruning on read) would
  put an O(n) walk on NFR-05's path to reclaim memory nobody is short of. Recorded as a declared
  limit rather than a defect. **Home: unowned.** (Severity: Low.)

- **A story that empties `_BANNED_IDENTIFIERS` now gets a red, but nothing tells it what to do.**
  c3-8 added an explicit non-emptiness assertion to the two firing halves, so the `set() == set()`
  degradation c3-7 caught by noticing is now caught by a test. What is still only prose is the
  **procedure**: c3-6 wrote it down, c3-7 followed it, c3-8 declined to apply it with a reason —
  but it lives in a frozenset's docstring rather than anywhere a story author would look before
  starting. ~~**Home: the C3 retrospective**, which is where three worked examples of the same
  procedure should become a standing agreement.~~ **CLOSED at the C3 retrospective, 2026-08-02
  (R2, Brad) — promoted to a standing team agreement, "banned-family lifecycle":** *a story that
  owns a banned identifier family must explicitly **retire it, re-key it, or keep it with a written
  reason** — and a replacement must be probed against **the spellings the retired ban caught**, not
  only against new ones. Removing a family without a replacement covering its members is a coverage
  loss disguised as a cleanup.* The two worked failures are named in the agreement (c3-6's
  `from time import sleep` and c3-7's `Path.replace` — in both cases the retired ban DID catch the
  spelling its replacement missed); c3-8 is the worked *keep*. Recorded in
  `epic-c3-retro-2026-08-02.md` § *Team agreements*. (Severity: Low → **closed**.)

- **`ErrorResponse`'s class docstring is published in full and nothing says so at the edit site.**
  c3-8 predicted "no wire diff", edited that docstring, and measured a real diff in both generated
  files — while the same commit's edit to `ErrorReason`'s attribute docstring twelve lines away did
  **not** cross the wire. The distinction is correct and now documented in `scripts/dump_openapi.py`,
  but `contracts.py` itself carries no marker at either site, so the next author has the same 50/50
  guess. A one-line comment above each would fix it; it is not done here because `contracts.py` is a
  wire module and even a comment edit is a wire decision that would want its own regeneration.
  ~~**Home: c3-9**, which already inherits wire-value work.~~ **CLOSED, c3-9 (Q9, 2026-08-02).**
  One `#` comment above `ErrorReason`'s assignment (*NOT PUBLISHED*) and one above
  `ErrorResponse`'s `class` statement (*WIRE-VISIBLE, IN FULL*), each naming the mechanism and the
  c3-8 measurement it came from. **c3-7's objection is dissolved by measurement, not by the
  regeneration this story owed anyway**: `npm run gen:api` was run after the comment edits and
  produced **no diff at all** from them — a `#` comment is not a docstring, so it never reaches
  `app.openapi()`. That is now the recorded safe way to annotate a wire module, in
  `scripts/dump_openapi.py`. (A docstring edit still is a wire change, and still needs its own
  regeneration.) (Severity: Low.)

## Deferred from: code review of c3-8-distinguishable-failure-signalling-and-negative-caching (2026-08-02)

- **Concurrent duplicate requests for one key escalate the backoff per-record, not per-outage, and
  each record slides the window forward.** Two simultaneous requests both pass `is_backing_off`
  (no entry yet), both fetch, both fail, and one outage instant lands the key at 60 s; N duplicates
  escalate N steps at once, and each `record_failure` inside an open window rewrites
  `retry_after = now + delay`. Documented as deliberate in `record_failure`'s docstring ("two
  tabs... the count measures how bad this outage is") — but N concurrent duplicates measure
  *fan-out*, not outage severity. Harmless today because duplicate printings collapse in
  `deck_cards` before reaching the route; c6-4's duplicate-tile surface (the acknowledged
  coalescing trigger) makes it the normal case. **Home: c6-4**, beside the in-flight-coalescing
  entry it shares a fix with. (Severity: Low.)

- **A short burst transient can permanently latch the disk cache's writes off.** Writes during a
  cold paint arrive back-to-back at ~0.8/s, so a ~6 s transient (an AV scanner holding a handle, a
  disk-full blip) spans `DISK_CACHE_WRITE_FAILURE_LIMIT = 5` *consecutive* writes and disables the
  cache's writes for the process — the "consecutive" reset only protects failures separated by
  successes, and Q4 declined any re-enable path. Accepted at review (Brad, 2026-08-02): the
  consequence is only lost caching, images are still served, and the docstring now states the
  exposure honestly. Any re-enable/recovery mechanism is cache stewardship.
  ~~**Home: 15-2.**~~ **RE-RECORDED BY 15-2, 2026-08-18: DISCLOSED, STILL UNBUILT** — the same
  ruling, and the same reason, as the transient-startup entry it shares a question with (they are
  one lifecycle question wearing two hats: *when* does a disabled cache try again?). 15-2
  documented the exposure in `README.md` — five *consecutive* failed writes stop writing for the
  process, every image is still served, restarting the app is the remedy — and built no re-enable
  path. **Home: unowned**, with the same forcing function: a real report of a silently disabled
  cache. (Severity: Low.)

- **The backoff 502 answers without a `Retry-After` header the server could supply.** The route
  holds `retry_after` at the moment it answers a negative hit and discards it; the SPA therefore
  has no signal for when a stuck tile (up to 300 s after CDN recovery — see `ui/README.md`'s
  blind-spot row) becomes worth one scheduled retry. A standard `Retry-After` header would give
  the tile author exactly one correct action without a new token — but it is a wire-visible change
  c3-8's rulings excluded. Declined at review (Brad, 2026-08-02) so the tile author decides with
  the UI in view. **Home: c4-4**, beside the blind-spot row it would resolve. (Severity: Low.)
## Deferred from: story c3-9 (fresh install guides instead of erroring, 2026-08-02)

Every entry here has a **named home**, per AC 23. Nothing in this section is prose-only: each one
either has an owner story or is declared inside the file it constrains.

- **The four newly-reachable panels have still not been looked at by a human, and neither has the
  transition.** This is the honest split of AC 11 and AC 25. What WAS done live: an empty
  `PLANESWALKER_DATA_DIR`, a companion that started with no `cards.db`, `GET /api/decks` answering
  `503 database_not_initialized`, a `cards.db` planted while the server ran, and the very next
  request answering `200` with real deck names — no restart. What was NOT done: opening the URL in
  a browser and watching the PAGE change, and looking at `database-not-initialized`,
  `database-updating`, `database-updating-stalled` and `internal-error` rendered by a real engine.
  This environment has no browser automation installed and adding one would be a new dependency
  the story does not call for. The DOM-level claim is gated (`App.test.tsx`'s FR-22 block asserts
  the transition from ONE mount, and probe (f) confirms a remount-driven implementation fails it);
  the VISUAL claim is not made anywhere. **Home: the epic manual-testing checklist**, with the
  recipe in the c2-9 entry above and in `ui/README.md`'s new blind-spot row. (Severity: Low — the
  behaviour is gated; the appearance is a first-look.)

- **A backend that cannot be reached at all leaves whatever panel is on screen, including on the
  very first load.** `fetch` rejecting produces no response and therefore no token, so the poller
  changes nothing and retries on the backoff. On the first load that means "No deck on the glass."
  stays up while the app quietly retries a backend that is not there — a calm panel that is not
  true. The panel that IS true for it is `disconnected` (*"Lost the companion backend. Check your
  terminal…"*), and `CLIENT_ONLY_STATES` assigns it to **c5-6**, whose condition is the WebSocket
  backoff exhausting its retries; Q10 ruled c3-9 must not claim it. Ruled rather than overlooked:
  clamping a transport failure to `internal-error` instead would have been worse, because
  `RETRIES_QUIETLY['internal-error']` is `false` and one transient blip would have stopped the poll
  permanently. **Home: c5-6.** (Severity: Low-Medium — the wrong panel, in a case a fresh install
  reaches only by starting the browser before the backend.)

- **Once a `200` arrives the poll stops, and nothing notices if the database goes away again.**
  `RETRIES_QUIETLY['no-active-deck']` is `false` — correct, because the agent sets the deck and a
  `deck_changed` event delivers it — so a tab left open through a later `initialize_database`, a
  deleted `cards.db` or a corrupted one shows a stale `no-active-deck` panel until it is reloaded.
  The signal that should replace polling here is **c5-6's** WebSocket (and its reconnect refetch,
  NFR-04). Stated because the poll deliberately does NOT become a heartbeat: making it one would
  contradict a contract written down in `states.ts` and would put two mechanisms on the same job.
  **Home: c5-6.** (Severity: Low.)

- **The stalled panel is terminal, and a database that recovers after it does not un-stall.**
  `RETRIES_QUIETLY['database-updating-stalled']` is `false`, by design — *"the quiet retry has
  already been running and has not worked, so continuing to retry silently is the behaviour this
  state exists to replace"* — and the copy's next action is a manual one. But if the user does what
  it says and the import succeeds, the page still needs a reload, which is one refresh more than
  FR-22's promise. Same resolution as the entry above: **c5-6's** reconnect is the event that
  should re-drive it. **Home: c5-6.** (Severity: Low.)

- **A first import that starves reads for 60 s continuously would escalate to stalled — unmeasured
  edge.** During a bulk import `is_database_initialized` returns `False` (the `import_state` probe),
  so the dominant answer is `database_not_initialized`, which never escalates. But if the
  importer's write batches ever hold the write lock past the engine's 5 s busy timeout, the read
  raises and the route answers `database_unavailable` instead — and 60 s of *continuous* such
  answers would show "Card database still updating. Check your agent session — if no import is
  running…" during an import that is running. The importer's batch size was not measured here, and
  the Q7 measurement above says lock waits are ~0.2 s worst case under four saturating readers, so
  this is a narrow window rather than a likely one. **Home: 17-3**, beside the lock work.
  (Severity: Low, unmeasured.)

- **`ui/tests/posture.test.ts`'s identifier layer is defeated by a computed global assembled from
  fragments, and its import layer is what actually carries the guard.** Declared in that file's own
  header. `globalThis['fetch']` is caught (the identifier is present); `globalThis['fet' + 'ch']` is
  not, and neither is an aliased hook CALL (`sync(subscribe, snapshot)`) — the alias is caught at
  the IMPORT door instead, which is why the door is the primary layer. Probe (g) planted both
  spellings in a real component file and confirmed exactly this split. The answer to the remainder
  is review, not a longer regex — the same declaration `test_import_boundary.py` makes on the
  Python side. **Home: review, permanent.** (Severity: Low, permanent.)

- **`CLIENT_ONLY_STATES` still has no runtime consumer**, and unlike its two siblings it is not
  expected to gain one from a wiring story: `database-updating-stalled` is produced by elapsed time
  rather than looked up, and `disconnected` is selected by nobody until **c5-6**. It is still worth
  keeping — `EveryPanelHasASource` and `PanelSourcesAreDisjoint` both read it at typecheck time, so
  it is load-bearing without being executed. **Home: c5-6**, which either consumes it or is the
  story that says it should stay type-level. (Severity: Low.)

- **The `no-store` request header is asserted, its EFFECT is not.** `decks.test.ts` pins
  `cache: 'no-store'` on the request options, which is a source-level claim; whether a real browser
  honours it for a same-origin `200` with no `Cache-Control` was not measured, because jsdom has no
  HTTP cache. The consequence if it were wrong is precisely FR-22 failing — a cached `503` would
  make the page never come alive — so it is worth one look during the browser pass rather than a
  test. **Home: the epic manual-testing checklist**, beside the transition look-at. (Severity:
  Low.)

## Deferred from: code review of c3-9 (2026-08-02)

- **Alternating `database_unavailable`/`database_not_initialized` pins the backoff near base.**
  `poller.ts` resets `delay` to `POLL_BASE_MS` on every outcome-identity change (Q2's own ruling:
  *"resets to base on any change of outcome"*). During an interleaved import — the exact
  interleaving this ledger already documents — each flip resets the schedule, so sustained
  alternation approaches one request per 2 s against a backend that is deliberately busy, which is
  what `POLL_CEILING_MS`'s docstring says the ceiling exists to prevent. By-design per Q2; the cost
  was not weighed there. ~~**Home: c4-1**, which copies this seam for its per-card fetches and should
  decide whether token-change resets need damping (e.g. no reset between the two database tokens).~~

  **RE-HOMED at c4-1 (2026-08-02, Q6) → c5-6, and the premise it was homed on turned out to be
  false.** c4-1 does **not** copy this seam: `readCard` has no backoff, no schedule and no timer at
  all, and AC 12's bound is a cumulative **attempt count per id**
  (`MAX_ATTEMPTS_PER_CARD = 3`) rather than a token-driven retry loop — so there is no `delay` for
  a token change to reset and nothing here to damp. Beyond that, the damping question is about
  `poller.ts`'s whole-screen poll, and **c5-6 already owns the family of sibling entries about that
  poller's re-drive behaviour** (C3 retro ruling R3: *"c5-6 resolves the family; it should not solve
  one third of it"*). **Home: c5-6.** If a later per-card path ever grows a schedule, this decision
  comes with it.
- **`database-updating-stalled` permanently forfeits FR-22's self-transition.**
  `RETRIES_QUIETLY['database-updating-stalled']` is `false` (ruled in `states.ts:233` — *"continuing
  to retry silently is the behaviour this state exists to replace"*), so once escalated the poll
  stops for the life of the page: when the user does exactly what the panel's copy tells them to and
  the rebuild succeeds, the `503→200` transition this story exists to render is invisible, and only
  a manual refresh recovers. The contract is honoured; its terminal consequence was never written
  down. A slow continued probe would need a `states.ts`/`EXPERIENCE.md` amendment, which this story
  may not make. ~~**Home: C3 retro**, as an EXPERIENCE.md amendment question.~~

  **RULED AT THE C3 RETROSPECTIVE, 2026-08-02 (R3, Brad): ACCEPTED, and re-homed on c5-6.**
  `RETRIES_QUIETLY['database-updating-stalled']` **stays `false`** — the contract in `states.ts:233`
  is right, and a slow continued probe would put two mechanisms on one job. **No `EXPERIENCE.md`
  amendment.** What the ruling adds is that the terminal consequence is now recorded rather than
  implied: *a user who does exactly what the panel's copy tells them, and whose rebuild succeeds,
  still needs a manual refresh — one refresh more than FR-22 promises.*

  The ruling is a re-home, not a dismissal: the two sibling entries above (*"Once a `200` arrives
  the poll stops"* and *"a backend that cannot be reached at all leaves whatever panel is on
  screen"*) are already homed on **c5-6**, whose WebSocket reconnect and NFR-04 refetch is the event
  that should re-drive all three. **c5-6 resolves the family; it should not solve one third of it
  and leave the rest.** **Home: c5-6.** (Severity: Low.)
- **The c4-1/c4-2 seam Q1 drew, restated where AC 23 asked for it (review patch).** Q1 ruled that
  `src/api/decks.ts` (the one network door, a total outcome union that never rejects) and the
  `src/state/` slice are the seam **c4-1 EXTENDS** — card cache, in-flight deduping, per-card
  routes, which are NOT retry-safe (they carry path parameters; `decks.ts`'s header holds the
  c3-2 measurement of why) — and that **c4-2** inherits a poll already calling `GET /api/decks`,
  its job being to read the DECK rather than the deck names. What the poller does NOT cover:
  per-card fetches and the WebSocket. The threshold is `STALLED_AFTER_MS = 60_000` with a
  `STALLED_MIN_REFUSALS = 4` observation floor. The prose homes are `ui/README.md`'s "Not here
  yet" + blind-spot row and the module headers; this entry exists so the ledger names the seam
  too. ~~**Home: c4-1 and c4-2 read this before extending.**~~

  **✅ READ AND ACTED ON at c4-1 (2026-08-02); half closed, c4-2's half stands.** Every clause was
  honoured and one was amended by ruling. The seam was **extended, not replaced**: the module is
  still the one network door and still a total outcome union that never rejects, and `readCard`
  was written to that shape. The deduping went **around** it, in `src/state/cards.ts`, exactly as
  the ruling said. The not-retry-safe warning was the operative one and it produced
  `MAX_ATTEMPTS_PER_CARD`, whose docstring carries the c3-2 measurement so the reason travels with
  the constant. **The amendment: the door is now `src/api/client.ts`, not `src/api/decks.ts`**
  (c4-1 Q1) — the guard's property was always "one door, named exhaustively", and a module named
  for decks that exports `readCard` is the "prose outrunning code" finding this epic has now made
  four times. `posture.test.ts:328`, its comment and `ui/README.md` moved in the same commit.
  **The c4-2 half is untouched and still owed**: it inherits a poll already calling
  `GET /api/decks`, its job is to read the DECK rather than the deck names, and it now also
  inherits `seedCardSummaries` — the entry point that turns the `DeckCardSummary[]` its own fetch
  already returns into the cache's summary tier for zero extra requests. **Home: c4-2.**

## Deferred from: code review of c4-1-a-single-card-hydration-cache-with-in-flight-deduping (2026-08-02)

- **Three transient failures make an id terminal for the tab's life while the whole-screen poller
  self-heals (FR-22 asymmetry).** `retryable` counts `unreachable` outcomes against
  `MAX_ATTEMPTS_PER_CARD = 3` (`ui/src/state/cards.ts:389`), so a backend restart or network blip
  during one hover sweep spends an id's three attempts forever — while `poller.ts` retries
  indefinitely and the panel "comes alive on its own". The story record declares this residue and
  names the fix: `resetCardCache()` on the `deck_changed` (or recovery) transition, which **c4-2**
  owns. Home: c4-2, with c4-5 (detail panel) as the story that would make it visible.
  **Companion question, same home (Greptile PR #40, P2, ruled option-1 "declare" by Brad
  2026-08-02):** a `hydrateCard` promise that a reset orphans still resolves with the entry it
  computed for the discarded world — the store write is generation-guarded, the return value is
  not. Harmless while resets are test-only and consumers render from `useCardEntry`; the moment
  c4-2 wires a production reset, decide whether awaiting callers need the fresh answer (widen the
  return to `CardEntry | undefined`) or the docstring's "the store is the authority" ruling
  stands. Declared in `hydrateCard`'s Returns docstring.
- **`useCardEntry` is untested.** A React render harness would be needed and no testing library is
  in the dependency set (adding one casually is banned by AC 21 / package-contract). Home: c4-3
  (first consumer) — its component tests exercise the hook for real; if c4-3 introduces a testing
  library for its own needs, add a direct `useCardEntry` subscription test then.

  > **✅ RESOLVED at c4-3 (2026-08-04) — and the stated reason was FALSE, as c4-2 already recorded.**
  > `@testing-library/react@^16.3.2` has shipped all along; no dependency was added and
  > `package-contract.test.ts` is untouched. The hook is now exercised through its real contract in
  > `CardPlaceholder.test.tsx`: a test component subscribes with `useCardEntry`, and four
  > assertions drive it — an id never seen renders the WELL rather than an unknown card (`undefined`
  > means "never seen" and only that); `seedCardSummaries` makes it **re-render** with the card's
  > name, which is the whole contract of a selector that starts nothing; a `card_not_found` refusal
  > through `hydrateCard` with an injected reader turns it into the unknown placeholder; and a
  > `database_unavailable` refusal LEAVES THE SUMMARY STANDING, because `placeholder` is `null`
  > there. **The component itself does not subscribe (c4-3 Q7)** — a listed primitive may hold no
  > hook of any family, so the subscription lives at the call site and the test component is the
  > shape c4-4's tile will take.

## Deferred from: c4-2-deck-state-bootstrap-and-the-type-grouped-decklist (2026-08-02)

### The ten inherited deferrals, each with a disposition (AC 28, C2 retro ruling R2)

1. **`GET /api/decks` and `GET /api/deck/{id}` have never been called by a browser** (`:1666`,
   Low, "Home: c4-2"). **✅ RESOLVED, and by a real browser rather than by argument.** The
   companion was launched (`src.companion.app.server.run`), a deck was set active over the real
   `PUT /api/active-deck`, and the built SPA was rendered in **Microsoft Edge (headless=new)**
   against `http://127.0.0.1:8765/`. Both boot routes were exercised through the security
   envelope by a browser, and the deck rendered. Screenshots captured for three states: a loaded
   deck, a `404` clearing to no-active-deck, and a hostile id. **The Vite dev-proxy path
   (`changeOrigin`, c2-1) is still unexercised** — the render was against the served bundle, not
   `npm run dev`. **Home for that remainder: the next story that runs `npm run dev` in anger.**
2. **Generated-type optionality asymmetry** (`:1889`, Low, "Home: c4-2, unshared"). **DECLINED,
   with the measurement that makes it a decline rather than a deferral.** The half that would have
   bitten does not exist: `openapi-typescript` renders a schema `default` as a **required**
   property, so `mainboard_count`, `sideboard_count` and `distinct_cards` are `number` in
   `types.d.ts` — **not** `number | undefined` — and there is no spurious `undefined` branch to
   absorb. Verified by reading the generated file, not assumed. What remains is genuinely
   asymmetric (`strategy?: string | null` versus `format: string | null`, a Python-default
   artifact) and is a field **this story does not read**; fixing the wire means changing a Pydantic
   default that `create_deck` and the MCP server both call. Real blast radius, no consumer.
   **Re-homed by name to the first story that reads `strategy` — c4-7 (the deck list) is the
   nearest candidate.** The `@default 0` half is CLOSED, not carried.
3. **No sanctioned `DeckDetail` alias** (`:2108`). **✅ RESOLVED.** `src/api/schema.ts` now exports
   **nine** aliases: c4-2 adds `DeckDetail` (consumer: `readDeck`, and the `deck` arm of the deck
   slice) and `ActiveDeck` (consumer: `readActiveDeck`), each with a docstring naming it.
   **`CardFace` is still declined** on c3-2's own reason — an unused export is dead code — and
   remains **c4-6's**, the story that renders a flip control.
4. **The c4-1/c4-2 seam restatement** (`:3252`, "The c4-2 half is untouched and still owed").
   **✅ READ AND ACTED ON; the entry is now fully closed.** The seam was extended, not replaced:
   `src/api/client.ts` is still the one door (`posture.test.ts:328` green with no edit), both new
   readers are total unions that never reject and never return `null`, and both go through the
   existing private `request()` rather than calling `fetch` a third and fourth time. The poll was
   inherited unchanged — its job is still the deck NAMES — and `seedCardSummaries` is called with
   the payload this story's own fetch returns, for zero extra requests.
5. **Three transient failures make an id terminal for the tab's life while the poller self-heals
   (FR-22 asymmetry)** (`:3280`, "the named fix is `resetCardCache()` on the `deck_changed` (or
   recovery) transition, which c4-2 owns"). **RE-HOMED BY NAME to c5-4 / c5-6.** The entry homed
   it here on the theory that c4-2 owns a `deck_changed` transition; **measured, it does not** —
   `deck_changed` is an Epic 5 WebSocket message, and this story boots once and never switches
   decks. A blanket reset on a deck switch is probably the wrong fix anyway: the cache is keyed by
   printing uuid and shared with Epic 6's agent views (AD-12's second sentence), so resetting on a
   deck change throws away hydration for every card the two decks share. ~~**c5-4 (the event
   handlers) owns the transition; c5-6 (reconnect/refetch) owns the recovery half.**~~
   **RE-HOMED ENTIRELY TO c5-6** (c5-4, Q6, Brad 2026-08-08). The phrase "c5-4 (the event
   handlers)" was a guess about which story would build the *client* side, and it was wrong: c5-4
   is backend-only — a registry, a fan-out and one route call — and `ui/src` is byte-unchanged by
   it. **c5-6 builds the browser's connect/reconnect loop and therefore every event handler**, so
   both halves of this entry live there.
6. **The orphaned-hydration return residue** (`:3287`, Greptile PR #40 P2, ruled *declare*).
   ~~**RE-HOMED WITH ENTRY 5, to c5-4 / c5-6**~~ **RE-HOMED WITH ENTRY 5, TO c5-6** (c5-4, Q6,
   Brad 2026-08-08 — same reason: there is no c5-4 client code to hang it on), because it was
   explicitly conditional on c4-2 wiring a production reset — *"the moment c4-2 wires a production
   reset, decide…"* — and c4-2 wires none. `resetCardCache()` remains test-only. The docstring's
   "the store is the authority" ruling stands untouched.
7. **The primitives' APPEARANCE is not dev-verified** (`:1331`, **Medium**) **and the tone-over-
   wash CONTRAST is unmeasured** (`:1357`). **✅ RESOLVED FOR `Badge`; the rest re-homed.** See
   the measurements in §"What c4-2 measured" below. `Panel` (**c4-5** / **c4-7**), `StatChip`
   (first surface that carries one) and `GroupHeader` (**c4-7**) still have no on-screen consumer
   and remain unverified — **home unchanged**.
8. **C3 retro F2 — the kicker and the `h1` say the same words** (retro `:225`). **✅ RESOLVED**,
   and confirmed on a real screen: the kicker reads `ARTIFICIAL PLANESWALKER` and the `h1` reads
   `Atraxa Counter Cabinet v2 (owned)`. `AppShell.tsx` was not edited; the swap is a prop.
9. **C3 retro action item 4 — a gate banning story-key-shaped strings from rendered text**
   (`/\bc\d+-\d+\b/`), owner *"Sathias (15-5, or earlier if a C4 story is nearer)"*. **DECLINED;
   stays 15-5 (Q8), and the reason is now measured rather than predicted.** c4-2 REMOVES two of
   the offending strings from the deck view (the `h1`'s product name and the badge placeholder
   naming `c2-7 / c4-2 / c4-10`) and **leaves six on screen**, counted off the real render:
   `c4-4`, `c4-8`, `c4-9` in the left column and `c4-5`, `c4-7`, `c4-10` in the right, plus
   `c6-8` in the nav. Every one of them is CORRECT today, so a gate built here ships either
   disabled or with an allowlist — and an allowlisted ban is the "enumerate members" anti-pattern
   this epic has now violated three times. **Home: 15-5, unchanged.**
10. **C3 retro carried manual-testing items A3/A4** (*"c4-2 renders four of the five panels for
    real; A3–A6 are its acceptance surface"*). **PARTIALLY PERFORMED, remainder fed forward.**
    Two of the five were rendered by a real engine here: `no-active-deck` (with the real deck list
    of 15 names) and the deck view that displaces it. **A3–A6's database panels
    (`database-updating`, `database-updating-stalled`, `internal-error`, `database-not-initialized`)
    still need a backend in those states**, which this story could not manufacture without
    corrupting the live database. **Home: the C4 manual-testing checklist**, with the trade the
    retro already ruled — after c4-2 a failure is ambiguous between the panel and the new wiring.

### The two corrections this ledger pass owed (AC 28)

- **`@testing-library/react` IS in the dependency set** — `^16.3.2`, with `@testing-library/dom`
  and `@testing-library/jest-dom@~6.9.1`, and `App.test.tsx` has used it since c3-9. The
  `useCardEntry` deferral's stated reason (*"no testing library is in the dependency set"*) is
  **false**; the deferral's HOME (c4-3) is still right, but for the honest reason that c4-3 is the
  first consumer rather than for a dependency that already ships. c4-2 used the library freely.
- **c4-1's "0 dangling references across 2,027 `deck_cards` rows"** is right about **card**
  references and wrong about the row count's meaning: **28 of those 2,027 rows are orphaned by
  DECK id** (2 deleted decks, no FK enforcement on the async engine), so the live population is
  **1,999**. Neither changes a decision; both are numbers later stories will quote.

### What c4-2 measured, so nobody measures it twice

- **`Badge`'s appearance, on a real screen.** Rendered in Edge against the running backend. The
  `::before` wash sits BEHIND the text — `z-index: -1` plus `isolation: isolate` behave as
  `Badge.css` argues they would — so the ledgered failure mode (*a solid blank pill with invisible
  text*) **does not occur**. This was the Medium-severity half of entry 7.
- **Contrast, all five tones, text over their own wash**: `neutral` **7.60:1**, `accent`
  **8.33:1**, `positive` **7.97:1**, `negative` **6.17:1**, `caution` **8.99:1**. Every one clear
  of 4.5:1. Washes computed as the tone at `opacity: 0.12` composited over `--surface-base`
  (`neutral`'s is opaque `--surface-overlay`).
- **One number that does NOT clear a floor, and what it constrains.** `neutral`'s
  `--border-strong` hairline is **1.89:1** on the page and **1.54:1** on its own wash, against
  WCAG 1.4.11's 3:1 non-text floor. **Accepted for `neutral`**: a badge is a static label rather
  than a UI component, and its boundary carries no information its wash does not. **A live
  constraint for c4-10**, whose format-check badge carries STATE — the four semantic borders are
  6.73:1 / 9.96:1 / 7.32:1 / 11.49:1 and fine, so a state distinguished by TONE is safe and a
  state distinguished by the neutral border would not be.
- **The URL-encoding argument, confirmed against a live backend rather than reasoned.** Raw
  `GET /api/deck/../decks` answers **`200` carrying the DECK LIST** — it does not fail, it
  succeeds against a different route, and a client interpolating raw would render `/api/decks`'s
  array as a deck. Encoded, `..%2Fdecks` answers `404 invalid_request`. Note the status/token
  split in that second answer: AD-16's "nothing keys off a bare status code" made vivid.
- **The type-group corpus facts.** 38,261 cards; 3,183 type lines containing `//`; **2,274**
  literally `'Card // Card'` (real front-face type only in `card_faces`, **0 in any live deck**);
  400 literally `'Card'` (**2 live rows**, "Pym Particles"); 88 live rows carrying more than one
  primary type on the front face; 4 corpus `Land Creature` (**0 live**).

### New residues c4-2 declares

- **The `'Card // Card'` printing cannot be grouped correctly from the deck payload.** Its real
  front-face type lives only in `card_faces[0].type_line`, which `DeckCardSummary`'s embedded
  `CardSummary` does not carry. 2,274 in the corpus, **0 in any live deck** — latent, not live.
  Fixing it means 99 extra card fetches for a case no deck contains. **Home: c4-6**, which adds
  `CardFace` and renders faces anyway; if it lands, the grouping can read the front face properly
  for the ids already hydrated. (Severity: Low.)
- **29 distinct corpus type lines discriminate the front-face rule; 0 are in any deck.** A type
  line only discriminates when its front face carries NO em-dash (so the subtype strip cannot
  remove the back face) AND the back face's group precedes the front's — e.g.
  `'Land // Legendary Creature — Demon'` (Westvale Abbey). `deckGroups.test.ts` pins six by name.
  Recorded because **the obvious fixtures do not discriminate**: a probe deleting `frontFace()`
  from `groupOf` left 27 assertions green, including all four "land policy" cards. (Severity:
  Low — the rule is right; the note is about where it can be tested.)
- **There is no re-drive after the boot.** A deck the agent sets while the tab is open does not
  appear until Epic 5's `deck_changed`. Specified, not a bug — `poller.ts` still stops after one
  `200` and `App.test.tsx` still asserts that — but it is the difference a user would notice
  between this story and a finished product. ~~**Home: c5-4.**~~ **BACKEND HALF ✅ CLOSED by c5-4
  (2026-08-08); BROWSER HALF RE-HOMED TO c5-6** (c5-4, Q6, Brad 2026-08-08). The signal now exists
  on the wire — every open socket receives an `active_deck_changed` envelope the instant the agent
  sets a deck, proven with two concurrently open sockets and one `PUT`. What is still missing is a
  browser that is *listening*: `ui/src` opens no WebSocket at all (verified at c5-3 and again
  here), so **c5-6** — the connect/reconnect loop — owns the half a user can see. (Severity: Low.)
- **A `404` clears the client while the backend still reports that deck id as active.** So the
  next cold open asks for the deleted deck again and clears again: one wasted request per boot,
  self-correcting the moment the agent sets another deck. The alternative — the client telling the
  backend to forget an id — is a `PUT` this story has no mandate to make. ~~**Home: c5-4**, with
  the `deck_changed` design.~~ **RE-HOMED TO c5-6** (c5-4, Q6, Brad 2026-08-08). This is a
  *client-loop* concern — it is about what the browser does with a `404` while a socket is open —
  and c5-4 shipped backend-only: there are no client event handlers in this diff to hang it on.
  c5-6 builds them. (Severity: Low.)
- **`src/logic/mana_curve.py` and `src/logic/assessment/mana_base.py` still use the WHOLE-STRING
  land policy**, which disagrees with FR-05/UX-DR17 and with this story's front-face grouping on
  **84 corpus cards, 4 of them in real decks** (Agadeem's Awakening, Kazandu Mammoth, Dowsing
  Dagger, Journey to Eternity). The frontend is now correct and the Python is not, so the two will
  report different land counts for the same deck. **Home: c4-8** (the mana-curve panel), where it
  is a `src/logic` change with MCP blast radius and deserves its own decision. (Severity:
  **Medium** — two surfaces of one app disagreeing about a number is the exact failure the epic's
  "the grid and the list panel cannot disagree" clause is about, one layer out.)

  > **DISPOSITION at c4-8 (2026-08-06): DECLINED for that story, RE-HOMED, and upgraded from
  > latent to OBSERVABLE.** The Python keeps the whole-string test. Changing it moves
  > `assess_deck_power`'s input for 5 of the 40 real decks, and `mana_base.py`'s land count feeds
  > the power score's frozen benchmark set — a benchmark re-validation does not belong inside a
  > seven-bar `ui/` panel. **Home: a Python story that owns the scoring surface** (Epic 5's
  > calibration set is the artefact that has to move with it).
  >
  > **What changed is that the divergence is now VISIBLE**: c4-8 ships the front-face land test,
  > so `analyze_mana_curve` and the mana curve panel now answer "how many lands" differently for
  > `Green Fury`, `Green Fury v2`, `Ayara Black Devotion`, `Ayara Black Devotion v2 (owned)` and
  > `Infinite Guideline Station v2 (owned)` — **7 live non-sideboard rows / 7 quantity**.
  >
  > ⚠️ **THE "84" ABOVE IS CORRECT AND WAS NEARLY "CORRECTED" INTO AN ERROR.** c4-8's own AC 38
  > carried it as a stale number owing a fix to 82, on the reading that c4-7 had corrected the
  > same figure in `deckGroups.ts`. Re-measured at `0fdb41b`, they are **three different
  > quantities** and only one of them is 82:
  >
  > | comparison | corpus | note |
  > |---|---:|---|
  > | whole-string vs **front-face WORD** test (what c4-8 ships) | **84** | this entry's number |
  > | whole-string vs front-face **substring** test | 82 | the shape c4-8's Q4 proposed and declined |
  > | whole-string vs `groupOf` | 116 | of which 82 carry `//` — `deckGroups.ts:37-44`'s decomposition, reproduced exactly |
  >
  > The number is left at 84 and the TEST IS NOW NAMED beside it, which is what it was missing.
  > The general lesson is the one worth carrying: *a bare number in a ledger entry is not
  > checkable, because the same defect measures differently under three tests that all sound like
  > "the front-face policy".*

## Deferred from: c4-3-card-placeholders-named-unknown-and-loading-wells (2026-08-04)

**Inherited deferrals, dispositions in one place** (C2 retro ruling R2). Twelve entries were
homed on or shared with this story; most have a disposition written beside their own entry above
— (4), (8) and (9) live only in this index, which is their disposition of record (corrected at
code review; the sentence previously claimed all twelve were annotated in place) — and this is
the index: (1) `ManaPip`/`ManaCost` appearance — **RESOLVED**, all five claims hold;
(2) the CVD question — **MEASURED**, levers not needed, open at Medium pending Brad's acceptance;
(3) the ` // ` separator spoken literally — **CONFIRMED LIVE, RE-HOMED to c4-7** with a sharpened
population; (4) whether copy is second-person and blameless — **HONOURED, does not close** (see
below); (5) the 79 no-image cards — **RESOLVED**, and their shape measured for the first time;
(6) the `states.ts` classification — **CONSUMED, not deleted**, which is the answer that entry
made conditional on this story; (7) a malformed card id renders nothing — **the render arrived**,
entry fully closed; (8) `Card` banned with no alias — **not needed** (see below); (9) `card_faces`
untyped — **no face consumed** (see below); (10) `useCardEntry` untested — **RESOLVED**;
(11) the `ui/tests` import rule — **TRIGGERED AND CLOSED**, and the rule is now stated precisely;
(12) the C3 retro's manual-testing items — this story adds its eye-check outcomes and nothing
else to that list.

- **Disposition (8), `Card` is banned with no sanctioned alias: NOT NEEDED, and the reason is
  structural rather than lucky.** `CardPlaceholder` takes four plain string props and imports no
  wire type at all — not even from `src/api/schema.ts`'s nine aliases. That is the posture
  `DeckBadges` set at c4-2 and it is the right one for a presentation primitive: a `CardSummary`
  prop would drag the wire alias into the component tree, which `posture.test.ts`'s cross-tree
  value-import ban and `wire-contract.test.ts`'s name ban both exist to prevent. **The caller does
  the reading and the component does the drawing.** No alias was added; the count stays at nine.

- **Disposition (9), `card_faces` is untyped on the wire: THIS STORY CONSUMES NO FACE, deliberately.**
  It renders `CardSummary`'s single `name` and single `type_line`, unsplit (Q5), and never touches
  `card_faces`. Face-specific rendering is **c4-6's**, where `CardFace` already ships with
  `extra="allow"`. The entry's home is unchanged.

- **Disposition (4), whether copy is second-person and blameless: HONOURED, and it does not close.**
  This story ships exactly one authored string, `"Unknown card"`, and it was read: sentence case,
  no exclamation mark, no blame, no apology, and it names a state rather than accusing the reader
  or the app. It is byte-for-byte the artefact's own label, so the judgement that matters was made
  in `EXPERIENCE.md`. The entry stays open permanently, as it says it does — c4-12 and c6-6 owe
  the same reading.

**New residues declared by this story.**

- **Whether an element carrying `card-shape` is actually a CARD is not decidable from a stylesheet
  (UX-DR4).** c4-3 made both halves of the card-radius rule a gate — nothing outside `CARD_SHAPED`
  may spend `--radius-card`, and no `CARD_SHAPED` file may spend a chrome radius — and both read
  CSS. The class list that puts the shape on an element lives in TSX and is chosen at runtime, so
  `.card-shape` on a `<nav>` reads as a perfectly clean stylesheet, and a card-shaped element given
  a chrome radius by a rule in a NON-card-shaped file (`.deck-row .card-shape { … }`) is in neither
  half. The guard says so in its own header and `ui/README.md` says so where c4-4's author will be
  reading. **Home: review, at every card-shaped story; c4-4 is the first where the cross-file case
  becomes plausible.** (Severity: Low — the gate covers the two realistic mistakes; this is the
  third.)

- **Nothing checks that the RIGHT type role was chosen for the content — MEASURED by a probe that
  PASSED.** Probe (j) of this story put the truncated card ID back into the uppercase
  `--type-micro` role, correctly paired with BOTH its companions so `findRoleWithoutCompanions` was
  satisfied, and **the whole suite stayed green at 1,021 passed**. Every typography guard in this
  repo asks whether a role travels with its companions; none asks whether the role suits the value.
  c4-3 closed the one instance — `.card-placeholder-id` is now checked against `cards.py`'s
  `_CARD_ID_PATTERN`, **read from the file**, so if the route ever accepts uppercase the guard's
  own premise fails loudly — but the general rule (*do not uppercase data the reader may type
  back*) is not statically decidable, because whether a string is retypeable lives in the product.
  **Home: review, at every story that renders an identifier, a set code or a command.**
  (Severity: Low individually, and the class is worth knowing about: it fails *legibly but
  wrongly*, which is the failure nobody looks at.)

- **Running `tests/token-usage.test.ts` ALONE crashes the runner, which can make a probe lie.**
  Measured at c4-3: `npx vitest run tests/token-usage.test.ts` fails with `TypeError: Cannot read
  properties of undefined (reading 'config')` — the file imports two `src/` modules across the
  project boundary, so resolving it standalone picks the wrong project. `npm test` runs it
  correctly and the tree is fine. **The reason this is ledgered rather than shrugged at**: the
  first run of this story's probe harness matched on exit code and reported **six guards as firing
  when the runner had merely crashed**, which is precisely the "a guard that fails for the wrong
  reason" defect this epic's reviews keep finding — in the instrument this time rather than in the
  code. All six were re-run against the full suite. **Home: anyone writing a probe against that
  file; the rule is "prove a guard fires with `npm test`, never a single-file run".**
  (Severity: Low, but it silently inverts a probe's result.)

- **The named placeholder's `overflow-wrap: anywhere` breaks long names mid-word, and it is a
  trade rather than a defect.** Measured on screen at the 176px grid floor: the 66-character
  doubled name of the largest permanent-population card renders as
  `Asmoranomardicadais / tinaculdacar // Asmoranomardicadais / tinaculdacar` across four lines. The
  alternative is a name that paints straight through the card edge, because a 31-character single
  word has nowhere legal to break at 176px. Accepted here; **c4-4 owns the grid and could revisit
  it** with a real column width in hand (a wider minimum column, or a line clamp with the full name
  still exposed to assistive tech). (Severity: Low — it is ugly for one card in 38,261, and it is
  correct for the 141-character name that motivated the rule.) **And the VERTICAL edge of the same
  trade, added at code review:** `.card-placeholder` pairs `overflow: hidden` with the fixed 63:88
  box and `justify-content: center`, so a name+pips+type stack TALLER than the box clips at both
  edges with no clamp and no ellipsis. Not reached by anything measured (the 141-char corpus name
  wraps inside the box at 176px, eye-checked), but nothing declares the limit either — same home,
  **c4-4**, same lever (a real column width, or a line clamp).

- **A whole view of loading wells is total silence to assistive technology — and nobody owns that
  question yet.** Added at c4-3's code review. Each well is `aria-hidden="true"` and
  EXPERIENCE.md:72 mandates exactly that PER TILE ("No copy. Wells stay silent") — but during
  first paint a grid is *nothing but* wells, so an AT user gets zero indication that anything is
  loading anywhere. Whether the VIEW (not the tile) should carry a single polite live-region note
  during load is a composition question this story structurally cannot answer — it mounts nothing.
  **Home: c4-4**, which owns the grid and the first composition an AT user will actually meet.
  (Severity: Low today — nothing mounts a well until c4-4 — but it should be decided there rather
  than inherited by accident.)

## Deferred from: code review of c4-3-card-placeholders-named-unknown-and-loading-wells (2026-08-04)

- **Running `ui/tests/token-usage.test.ts` standalone crashes the vitest runner** — the file
  imports two `src/` modules across the project boundary, and resolving it alone picks the wrong
  vitest project (`TypeError: Cannot read properties of undefined (reading 'config')`). The crash
  exits non-zero, which once made a probe harness report six guards as firing when nothing had
  asserted anything. Pre-existing project-resolution behaviour, not introduced by c4-3; the
  standing mitigation is the rule already ledgered above — a guard's firing is proven with the
  full `npm test`, never a standalone file run.

## Dispositions from: dev of c4-4-card-tile-and-the-card-art-grid (2026-08-04)

Every entry homed on `c4-4` gets a disposition here (C2 retro ruling **R2** — inherited deferrals
are acceptance criteria at context time). Twelve were listed in the story record; the line each
lives on is given so this section is checkable rather than merely reassuring.

1. **The pacer queue can outlive the connection-pool timeout (`:2617`)** — **NOT TRIGGERED, and
   the lever was exercised.** Q7 ruled that all ~99 `<img>` mount at once (`decoding="async"`, no
   `loading="lazy"`), which is the maximum burst this entry describes, and **no pacer constant was
   changed**. Measured live against the running backend with the 99-card deck: a fully warm paint
   is 99 requests in **0.55 s** (5.6 ms/tile) and never enters the pacer at all. The cold burst
   was not reproduced from a browser because the disk cache was already warm on this machine —
   **so the entry stands, unresolved, and `loading="lazy"` remains its one client-side lever.**
   Re-home: **17-3**, which owns real-latency profiling, or the C4 retrospective.

2. **The image route reads the whole card row to get one URL (`:2742`)** — **NOT MEASURED, and
   declined here with a reason.** This story issues the requests in bulk but has no instrument for
   the backend's per-request cost, and the measurement that would settle it (a projection versus a
   whole-row read, under load) is a backend change with its own gates. What c4-4 CAN contribute is
   the volume it actually produces: 99 distinct ids, once per deck open. **Home: unchanged, C4
   retrospective**, with that number in hand.

3. **The backoff `502` answers with no `Retry-After` header (`:3213`)** — **DECLINED, and the UI
   is now in view, which is what this entry was waiting for.** The tile cannot use a `Retry-After`
   even if it were sent: a DOM `error` event carries no headers at all, and the SPA has no
   per-image retry UI by design. A header nobody can read is not worth a wire change. **Closed.**

4. **The named placeholder's `overflow-wrap: anywhere`, and the undeclared vertical edge
   (`:3623-3636`)** — **REVISITED with a real column width, and left as it is.** Seen at the
   eye-check at the 176px floor: the named placeholder renders name + type line centred with room
   to spare, and no mid-word break occurred on any real card in the deck. The vertical half is
   unchanged and still undeclared — a very tall stack would clip at both edges with no clamp.
   **Re-home: c4-5**, which renders the same component at detail size where a clamp would be
   visible, or review.

5. **A whole view of loading wells is total silence to assistive technology (`:3638-3646`)** —
   **RESOLVED IN STRUCTURE, with two declared corners (wording tightened by review 2026-08-04;
   the first record claimed it flat).** Each well is still `aria-hidden`, but a grid of them is
   no longer silent: every tile is a `<button>` named by its caption, so a first paint announces
   "list, 99 items" and each card by name whether or not its picture has arrived. A polite load
   note is not needed and is not added. The two corners the flat claim glossed: (a) a NAMELESS
   card yields an unnamed focusable button — zero population measured (0 of 1,061), the FR-13
   totality branch, and pinned as such by test; and (b) the announcement itself is
   jsdom-unverifiable — the NAME's exact spelling is now asserted (`Black Lotus ×4`, measured),
   but how a real screen reader phrases it is the epic checklist's, per the blind-spot row.

6. **Whether an element carrying `card-shape` is actually a CARD (`:3587-3596`)** — **REVIEW'S,
   and the cross-file case is now live.** c4-4 is the first story where a rule in one stylesheet
   reaches a card-shaped element in another: `CardTile.css` gives `> .card-shape` position and
   nothing else — no radius, no border, no background — and says so at the rule. Both directions
   are a reviewer's to check, unchanged.

7. **Nothing checks that the RIGHT type role was chosen for the content (`:3598`+)** — **SECOND
   INSTANCE, ruled in the open (Q3).** Every card name in the grid renders in CAPITALS because
   `findRoleWithoutCompanions` derives that requirement from DESIGN.md's own `label.textTransform`.
   Ruled correct on its merits — a card name here is a chrome label under a picture, not
   retypeable data like c4-3's truncated uuid, and browsers copy the untransformed text anyway —
   and confirmed by eye on a real screen. Still not statically decidable; **review's, unchanged.**

8. **The first paint against a fully dead CDN takes ~124 s (`:3131`)** — **NOT REPRODUCED.** The
   manual testing this entry names as its escalation condition was performed against a live,
   warm backend, so the dead-CDN path was never entered. Severity stays **Low**; **home: the epic
   manual-testing checklist**, where killing the CDN is a deliberate step rather than an accident.

9. **The `images.py` split decision (`:2989-2997`)** — **EVIDENCE FED FORWARD, not decided.** c4-4
   exercised the route, the pacer, the disk cache and the negative cache from a real browser for
   the first time and needed no change to any of them. **Home: unchanged, C4 retrospective**, with
   c4-6 still to add the flip control.

10. **c4-3's composition eye-check, re-homed here BY NAME (`ui/README.md`)** — **DONE.** A
    placeholder beside a real card face in a real grid, at the same footprint: confirmed in Edge
    against the running backend with the 99-card deck. Recorded in `ui/README.md` under _The card
    shape_.

11. **A `ui/tests/` file may import an app module only if that module has no relative imports** —
    **NOT TRIGGERED.** c4-4's new guards read source as TEXT, the idiom every other guard uses, so
    no new cross-project import was added. Confirmed with `npx tsc -b --force`, green.

12. **C3 retro action F1 — a gate banning story-key-shaped strings from rendered UI text** —
    **ONE OF THE SIX REMOVED.** The left column's placeholder (naming `c4-4` and `c4-8`) is
    displaced by the grid, and `App.test.tsx` now asserts neither string is on a rendered deck
    view. Five remain. **The gate itself stays 15-5's**, unchanged.

### New residues declared by c4-4

- **`CardPlaceholder` renders a `<div>`, and `<button>` takes phrasing content only.** Mounting
  the placeholder inside the tile is invalid HTML by the letter of the spec. Measured: every
  engine renders it, React does not warn, and the accessible name computes normally. Every
  alternative was worse (moving the placeholder out breaks UX-DR36's same-box claim; changing the
  primitive's root is an edit c4-4 was told not to make). **Home: c4-5**, which mounts the same
  component as detail art and can re-decide with two consumers in view. (Severity: Low.)

  ⚠️ **HOME CORRECTED, and it was stale by two stories.** c4-5 did not take it; **c4-6 re-homed it
  to c4-11 — but only in the c4-6 story record, never here**, so this entry went on naming a story
  that had already passed it on. Recorded because it is the failure mode a ledger has: a
  disposition written in a story file and not in the ledger is a disposition nobody will find.

  ❌ **DECLINED at c4-11 (2026-08-07), with the reason, and re-homed to the C4 RETRO.** c4-6 had
  already measured the whole of it — every engine renders it, React does not warn, the accessible
  name computes normally — and c4-6 *closed* the harder INTERACTIVE-descendant version of the same
  seam. What remains is a spec-letter violation with **zero measured accessibility impact**, and
  the fix means changing `CardPlaceholder`'s root: the edit c4-4 was explicitly told not to make.
  Making that change for no measurable gain, in the story whose entire subject is the accessibility
  floor, would be the wrong use of this story's licence. Saying so plainly is worth more than the
  change. **Home: the C4 retro**, which can weigh it against the other primitive-root questions.

- **The reduced-motion transform guard compares SELECTOR TEXT.** A fallback whose selector differs
  from the motion's — even one the cascade would resolve correctly — reads as unregistered. False
  failure, not false pass; the repair is to write the matching selector. (Severity: Low.)

- **jsdom cannot report an accessible name's spelling.** It applies no CSS, so naming elements
  concatenate with no separator (`×4Black Lotus`). Component tests assert membership instead. The
  real announcement is **the epic manual-testing checklist's**, with a screen reader.

- **The warm-cache `onLoad` race is UNPROVEN in both directions.** `settleIfCached` reads
  `complete && naturalWidth > 0` on mount, and jsdom reports `complete: false` / `naturalWidth: 0`
  always — so the suite can only prove the guard does not fire wrongly. That it fires RIGHTLY
  needs a browser with a warm HTTP cache. **Home: the epic manual-testing checklist.**

- **A cold paint against a cold backend — OBSERVED at review, 2026-08-04 (this residue is
  closed).** Disk cache moved aside, 99-card deck active, real browser, real CDN. Two numbers,
  and they are DIFFERENT numbers: the backend's fetch window was **9.3 s for all 99 images**
  (measured from cache-file mtimes — the pacer's 0.1 s spacing turnstile binding exactly as
  modelled), while the PERCEIVED paint was **2–3 s** — the browser prioritises in-viewport
  images, so the visible screenful fills while the remaining tiles complete off-screen; on a
  fast connection each tile appears the instant the pacer releases it. No spinner, no
  broken-image glyph, no stuck tile. Net: the ~10 s figure is real but largely invisible; the
  epic's "expected observation, not a defect" framing holds, and the experienced cold paint is
  BETTER than the epic's expectation reads. What remains 17-3's is profiling (real bytes,
  real latency percentiles), and the ~124 s dead-CDN first paint remains unobserved — the CDN
  was alive. **Home: 17-3, narrowed to profiling and the dead-CDN case.**

## Deferred from: code review of c4-5-persistent-card-detail-panel-with-transient-and-pinned-inspection (2026-08-05)

- **The 21em oracle-text scroller is keyboard-unreachable.** `.card-detail-oracle` clamps at
  14 lines with `overflow-y: auto` and contains no focusable element, so a keyboard-only user
  cannot scroll the 63 corpus cards whose rules text exceeds 500 characters (WCAG 2.1.1). The
  standard fix — `tabindex="0"` plus a labelled `role="group"` on the scroller — fails the AC 25
  "not a modal" test (which asserts `[tabindex]` is absent from the panel) and adds a Tab stop
  UX-DR40's enumerated order does not contain. Both of those contracts are c4-11's to
  renegotiate: it owns the keyboard/focus story and the Tab-order additions. Ruled at review
  (Brad, 2026-08-05): defer, not fix-now. **Home: c4-11 — scope the AC 25 assertion, enumerate
  the new Tab stop, and make the scroller focusable in the same change.**

  ✅ **CLOSED at c4-11 (2026-08-07), all three parts in one change**, exactly as the mandate asked.
  `.card-detail-oracle` now carries `tabindex="0"`, `role="group"` and an `aria-label` from
  `CardDetail/copy.ts` (`ORACLE_SCROLLER_LABEL = 'Rules text'`), with the known-surface focus ring
  in `CardDetailChrome.css`; AC 25's assertion is **narrowed rather than deleted** — from "no
  `[tabindex]` anywhere in the panel" to "no `[tabindex]` outside the oracle scroller", named by
  SELECTOR rather than counted, with the reason written into the test so the not-a-modal claim it
  protects stays legible; and the stop is added to UX-DR40's rewritten enumeration.

  ⚠️ **TWO CORRECTIONS TO THIS ENTRY'S OWN NUMBERS, both re-measured read-only at c4-11.**
  (1) *"the 63 corpus cards whose rules text exceeds 500 characters"* counts **top-level
  `oracle_text` only**. Faced cards store their rules text per face and blank at top level (the
  c4-6 / c4-7 / c4-9 family, a fourth time), so counting what `CardDetail` can actually RENDER it
  is **103 of 38,261**. The 63 reproduces exactly as a top-level count, so the figure was not
  wrong — it was measuring the wrong thing. (2) The **live** exposure is **one card in one deck of
  forty**: `Ajani, Sleeper Agent`, 530 characters, in `Atraxa Counter Cabinet`. c4-6 measured the
  clamp at 294px / 14 lines and the deepest real back face at 126px, so **the clamp has never been
  observed to fire on a real deck.**

  **The cost is recorded rather than hidden**: this adds **one permanent Tab stop to the right
  column on every deck**, to serve a scroller that overflows on one live card. That is the correct
  trade under 2.1.1 — reachability is required *whenever* content can overflow, not only when it
  usually does — and the conditional alternative (focusable only when `scrollHeight > clientHeight`)
  was **considered and rejected in writing**: jsdom resolves no layout so it cannot be verified,
  and a Tab stop that appears and disappears is the defect `c4-6:507-508` priced against.

- **The MDFC pin announcement speaks the combined name; the panel renders the face name.** A
  faced card pinned before hydration announces the summary tier's `"Clearwater Pathway //
  Murkwater Pathway"` while the panel, once the record lands, renders the front face's
  `"Clearwater Pathway"` — the reader hears one name and reads another, for the ~6%-of-a-deck
  faced population. Deliberate (re-announcing on hydration is the H4/C1 flood), declared in
  `CardDetail.tsx`'s announcement comment at review 2026-08-05. **Home: the epic manual-testing
  checklist — hear it with a real screen reader beside the em-dash entry already there.**

## Deferred from: code review of c4-6-double-faced-card-flip-control (2026-08-06)

- **An in-flight hydration sweep is not cancelled on deck replacement.** `hydrateDeckCards` fires
  per `detail` identity with no abort path (`ui/src/App.tsx:213-216`), so switching decks mid-cold-
  open lets up to ~99 stale card reads compete with the new deck's ~99 images on the six-connection
  pool — the measured "+1.2 s tail" prices one sweep, not two overlapping ones. Not reachable
  today: `deck_changed` handling is Epic 5's. **Home: Epic 5 (deck switching).**
- **A failed FRONT face unmounts both stacked `<img>`s.** `CardTile`'s `art === 'failed'` arm
  replaces the whole `.card-faces` block, so a back face mid-load when the front errors never
  fires its `onLoad` and sticks at `'loading'`; flipping out of the failed face remounts both,
  re-requesting the known-failed front (answered from the backend's negative cache). Self-heals on
  remount; window is the flip-after-front-failure path only. **Home: unowned/latent — revisit if a
  partial-failure population ever appears (see the partially-imaged-card entry above).**
- **Three hand-rolled copies of the flippable wire fixture.** `CardTile.test.tsx`,
  `FlipControl.test.tsx` and `CardDetail.test.tsx` each restate the shape-C hydrated `Card`; when
  `CardFace` gains a field there are three places to drift. Test-only refactor: share one fixture
  helper. **Home: any later c4 story that touches these suites.**
- **A mid-sweep backend blip leaves cards unhydrated with no automatic re-sweep — accepted as
  designed (review ruling 2026-08-06).** c4-2's recovery re-drive fires only from `refused`/`none`,
  never while deck state is `deck` (`deck.ts:56-66`), so card reads refused during the sweep's
  ~1 s cold-open window stay unhydrated (no flip control, no hydrated panel text) until the card
  is individually inspected — which re-asks within the 3-attempt budget; one blip burns 1 of 3 —
  or the page reloads (`cards.ts:100-108` documents reload as the recovery deliberately). If this
  is ever met live, the written fix is: re-fire `hydrateDeckCards` over still-unhydrated retryable
  ids on the poll's recovery edge (the c4-2 pattern), plus a negative-space test — today no test
  exercises a failing sweep. **Home: unowned/latent, by ruling.**
- **AC 1's residue has a keyboard half the story record did not state (review 2026-08-06).** The
  flip control materialises when the sweep's record lands (~1 s window on the 99-card deck), so a
  keyboard user Tabbing during a cold open meets Tab stops appearing mid-traverse — the UX-DR40
  concern Q1 priced against the lazy alternative, present in miniature during the sweep window.
  Declared residue, not a defect: the window is one cold open per deck per tab and closes itself.
  Added to the epic manual-testing checklist (entry 5 in the c4-6 record). **Home: the epic
  manual-testing checklist.**

## Deferred from: code review of c4-7-deck-list-panel (2026-08-06)

- **`frontFaceCost` shape 2 rests on a point-in-time corpus measurement, unguarded against future
  imports.** A faced card with any non-blank, non-split top-level `mana_cost` is returned verbatim
  and never cross-checked against `card_faces[0]`, even when hydration disagrees — test-pinned as
  the deliberate posture (`frontFaceCost.test.ts`, summary-wins fixture). The invariant ("no faced
  card's top-level cost is the back face's") was **measured at `d51b467`**, not guaranteed by any
  schema; a future Scryfall import that populates top-level costs differently renders wrong pips
  silently, with no analogue of the price column's type-level absence assertion. The guard belongs
  to the importer / weekly live-contract canary layer (c3-retro precedent), not this panel.
  **Home: the Scryfall canary / importer, next time either is touched.**
- **The registry guards are structurally blind to untracked modules (the c4-7 false-green
  mechanism).** `copy-rules.test.ts`, `token-usage.test.ts` and `posture.test.ts` all walk
  `git ls-files`, so an un-`git add`ed module is invisible to every registry sweep — c4-7's first
  full run was green with no CONTAINERS entry written, and the exact same blindness let the c4-3
  and c4-7 bundle assets go missing from their diffs. The comment corrections (declared-limit
  notes per `wire-contract.test.ts:106`) and this ledger entry are the c4-7 review's patch; the
  real fix — a filesystem walk cross-checked against `ls-files`, failing on any untracked source
  file under `ui/src/` — is deferred. **Home: the guard suite, first story that touches any
  registry test.**

## Dispositions from: dev of c4-7-deck-list-panel (2026-08-06)

Written at the c4-7 review, not the story commit — the dev commit recorded all of these only in
its Dev Agent Record, and this ledger write is itself a review patch (the c4-4/5/6 precedent is
that the story commit writes its own ledger).

**The nine inherited deferrals, a disposition each (AC 38):**

- **Panel (default level) + GroupHeader appearance — RESOLVED.** Eye-checked against Chrome with
  numbers (8.59:1 label, 5.43:1 count); the warned-of tone-over-wash failure does not occur.
- **The ` // ` separator spoken as literal characters — CLOSED BY CONSTRUCTION on deck rows
  only.** `frontFaceCost` splits before rendering, so a separator never reaches `ManaCost` from a
  deck row (measured live: `anySeparatorSpoken: false`). **Still live wherever a COMBINED cost
  renders — `CardDetail` and `CardPlaceholder` both still pass an unsplit cost.** Re-homed
  unchanged for those surfaces.
- **ManaPip/ManaCost appearance — RESOLVED as composition only** (no wrap, no overflow, fixed pip
  size in the row's cost track).
- **The `'Card // Card'` grouping fix — DECLINED and re-homed with the reason (Q10).** The data
  blocker is gone; the mechanism one is not: `boardsOf` runs once at store-write time and the
  reference identity is what `deckMemory.ts` and `CardDetail`'s deck-transition effect key on, so
  re-deriving after hydration would fire a spurious transition and release the user's pin.
  2,274 corpus rows, 0 in any live deck. **Home: a story that owns the derivation's timing** (a
  hydration-aware second pass, or the `CardSummary` field c4-6's Q1 priced).
- **`strategy` wire asymmetry — NOT TRIGGERED, re-homed unchanged (Q13).** Deck-level prose with
  no row to sit in; still awaiting its first reader.
- **`DeckRepository.list_decks` ties on `created_at` — NOT TRIGGERED, re-homed unchanged.** That
  entry means the list of DECKS; this story renders the cards of one deck and never calls
  `GET /api/decks`.
- **UX-DR44's heading-level collision — MEASURED, NO CORRECTION HOMED (Q15).** Chrome reports a
  flat list of `level=2` headings with the two `region`s carrying the grouping; declined on
  evidence, not taste. The same tree confirms the phantom-`banner` jsdom blind spot from the
  other side (Chrome: exactly one banner; jsdom would report three).
- **F1 story-key strings — COUNT RECORDED.** `c4-7` displaced by its own panel (both halves
  asserted in `App.test.tsx`); **5 F1 keys remain on a rendered deck view**; the gate stays
  15-5's.
- **Panel-stacking vertical budget — FED INTO Q7 AND MEASURED.** This panel adds 3,198 px beneath
  the card-detail panel; no internal scroller (Q7) — the page scrolls and every row is a Tab stop
  the browser scrolls into view.

**New entries this story raises:**

- **The plugin bundle mirror is checked by nothing (AC 42).** Hand-copied and verified
  byte-identical this story; `src/companion/app/static/` is CI-enforced (`ci.yml:154-167`) but
  `plugin/server/src/companion/app/static/assets/` has no test, no workflow, no script.
  **Home: the C4 retro**, as a one-line workflow addition.
- **`CardTile.tsx:178` says its constant is "written as an escape" and ships the literal
  character.** Same codepoint, nothing renders differently — but the comment is untrue of the
  line beneath it. Not edited at c4-7 (don't-break file, cosmetic change). And the honest
  postscript: **`DeckList.tsx`'s own constant shipped the identical defect and was caught at the
  c4-7 review** — the escape is real only post-review. **Home: whoever next edits
  `CardTile.tsx`.**
- **Q3's three-spelling divergence — a named manual-testing-checklist residue.** One card renders
  as `Clearwater Pathway` (deck row, front face per UX-DR19), `Clearwater Pathway // Murkwater
  Pathway` (tile caption, combined per c4-6), and is announced combined (c4-5's pin
  announcement). Raised, not discovered; UX-DR19 followed as written. **Home: the epic
  manual-testing checklist, beside the MDFC announcement entry above
  (`deferred-work.md:3788-3794`).**
- *(The `CONTAINERS`/registry-guard blindness to untracked modules is ledgered in the c4-7
  review section above — one entry, not two.)*

## Dispositions from: dev of c4-9-colour-distribution-panel (2026-08-06)

Written in the STORY COMMIT rather than at review — c4-7's review raised the omission as a
finding and c4-8 wrote one disposition block while eight others lived only in its record. All
nine inherited deferrals, all eight triggered residues and the four new entries are here.

**The nine inherited deferrals, a disposition each (AC 40):**

- **`ManaPip` / `ManaCost` appearance (`:1400-1419`) — RESOLVED, as composition, and this is the
  LAST of the three homes.** The five visual claims were resolved at c4-3; what that entry
  reserved for c4-7 and c4-9 was *"composition, which a harness cannot show"*. Composition
  verdict from the CDP eye-check: the legend's pip sits on a 13px baseline beside three text
  runs, at its `1.25em`/16.25px size, with no wrap inside an entry and no overflow at either
  measured width. The entry is now fully discharged.
- **CVD — "colour is the sole carrier" (`:1447-1471`, Medium, STILL OPEN) — ADVANCED WITH A NEW
  MEASUREMENT, AND NOT CLOSED.** This is the most on-point deferral the epic has for this panel:
  a segmented colour bar is a graphic whose only channel is hue. Two halves, and this story is
  careful not to conflate them:
  - **Distinguishability** — measured fresh against the SHIPPED hexes (the only prior
    measurement, `review-accessibility.md`, carries a *"⚠ SUPERSEDED — do not action"* banner and
    predates the Voltglass palette). **All 15 adjacent `--mana-*` pairs are under the 3:1
    non-text floor**, 8 under 1.3:1, worst `--mana-b`/`--mana-colorless` at **1.03:1**, best
    `--mana-w`/`--mana-r` at **2.30:1** — slightly *worse* than the 2.73:1 on record. But every
    segment clears the `--surface-well` track at **6.62:1 to 15.20:1**, so the shipped **1px
    track-coloured hairline** turns 15 sub-3:1 boundaries into 15 at 6.62:1 or better, with no
    new token and no new colour. `DESIGN.md` amended (`components.color-bar.segment-hairline`).
  - **Identifiability** — NOT closed by the hairline, and the legend is UX-DR18's answer: every
    entry names its colour in visible TEXT. That serves a sighted CVD reader, which the
    `role="img"` name never did.
  - ⚠️ **The entry stays OPEN at Medium**, awaiting Brad's acceptance of the c4-3 dE numbers.
    Nothing here closes it; the story is explicit that a hairline is not an answer to
    identifiability and a legend is not an answer to distinguishability.
- **The two Python land policies disagree with FR-05/UX-DR17 (`:3536-3572`) — NOT RE-OPENED.**
  Declined and re-homed at c4-8, with the divergence upgraded to observable. This story asks the
  same question one axis over (pips, not lands) and answers it the same way — see Q16 below —
  so the entry is re-homed unchanged. Its home remains a Python story that owns the scoring
  surface.
- **The `'Card // Card'` grouping fix (`:3515-3520`) — DECLINED AGAIN, ON THE SAME MECHANISM,
  ONE STORY LATER.** c4-7 declined it because re-deriving `boards` after hydration would fire a
  spurious deck-transition clear and release the user's pin. **This story reads hydration results
  and does NOT re-derive `boards`** — `coloursOf` walks the existing partition along a new axis
  (colour) and rebuilds nothing — so the mechanism is untouched and the decline stands. Worth
  noting the two populations are the same one: all 2,284 `Card // Card` rows are also §C's
  *"unpippable by any route"* set, so this panel would gain nothing from the fix either.
- **F1: story-key-shaped strings on the rendered view (`:3456-3464`, `:3765`) — COUNT RECORDED.**
  `c4-9` is now displaced **by its own panel** rather than by a sibling's (both halves asserted
  in `App.test.tsx`). The left column has contributed its last: `c4-10` and `c4-11` remain, in
  the right column's placeholder and the skip-link work. The gate itself stays **15-5's**.
- **Panel-stacking vertical budget (advisory) — MEASURED, AND THIS ONE GROWS THE ROW RATHER THAN
  THE COLUMN.** Unlike c4-7 (+3,198 px beneath) and c4-8 (+168 px), this panel is a SIBLING: if
  its legend were taller than the curve, the row would grow and both panels with it. Measured on
  the eye-check — see the story record for the row's height before and after.
- **The 21em oracle scroller is keyboard-unreachable (`:3806-3814`, c4-11's) — NOT TRIGGERED, and
  the reason is structural rather than incidental**: this panel contains no scroller of any kind
  and adds **zero Tab stops**, so it neither worsens nor touches the entry. Re-homed unchanged.
- **`DeckRepository.list_decks` ties on `created_at` (`:1668-1699`, Medium-High) — NOT TRIGGERED,
  re-homed unchanged.** That entry is about the list of DECKS; this story renders one deck's
  cards and never calls `GET /api/decks`. Same disposition as c4-7's and c4-8's.
- **The registry guards are blind to untracked modules (`:3869-3877`) — TAKEN IN PART, AND THE
  REST DECLINED WITH A REASON.** This entry is homed to *"the first story that touches any
  registry test"*, and this story touches **three** (`shell.test.ts`, `copy-rules.test.ts`,
  `token-usage.test.ts`), so silence was not available. What it took: nothing about the
  `ls-files` walk, and instead the **adjacent hole the same walk has**, found by this story's own
  file move — see the new entries below. What it declined: the filesystem-walk redesign, because
  the honest fix is one guard shared by three suites and a story that adds a panel is not where a
  guard-suite refactor belongs. **Home unchanged: the guard suite.** The concrete mitigation
  remains the one c4-7's review wrote down — `git add` before believing a green run, which this
  story did (AC 44).

**The eight triggered residues, a line each:**

- **The `MANA_DATA_INK` invitation (`ui/README.md:678-681`) — ACCEPTED.**
  `ColourDistribution.css` is the allowlist's **second entry and its first joiner since c2-8
  declared it**. c4-8 declined with a measurement and wrote *"c4-9 remains invited"*; this story
  could not decline, because UX-DR18 calls its bar *"data ink used correctly"* in the artefact's
  own words. Both invitations are now answered, and they went opposite ways.
- **`--mana-gold`'s first consumer (`ui/README.md:706-710`) — THE PREDICTION WAS WRONG AND IS
  CORRECTED IN THIS DIFF.** The README predicted this story would spend gold and move the count
  6 → 7. It joined the allowlist and did **not** spend gold: UX-DR17's gold is a *multicolour
  card* contributing one segment to a stacked curve, UX-DR18 specifies a **pip count**, and a pip
  is never gold. Count stays **6 of 7**, and the absence is now **asserted by a test** rather
  than noted in prose. Gold's real first consumer is a stacked curve or a colour-identity dot,
  neither of which is in Phase 1.
- **The visually-hidden idiom's third instance — NOT TRIGGERED, stated rather than left as an
  absence.** UX-DR18 makes the legend the accessible data path and the legend is VISIBLE text, so
  no third clip-rect block ships and c4-8's promotion trigger does not fire. It remains armed for
  whoever writes the third.
- **The split-card `cmc` divergence, re-homed here by name (`curve.ts:39`, `curve.test.ts:219`)
  — DECLINED, AND THE COMMENTS THAT NAMED THIS STORY ARE CORRECTED.** See Q12 and the new entry
  below.
- **The next story that renders an identifier / picks a type role (`:3626-3637`) — ANSWERED ON
  THE RECORD.** This panel renders two numeric values. `--type-numeric` (with its mandatory
  `font-variant-numeric` companion) for the pip COUNT, `--type-micro` (with `--tracking-micro`
  and its `text-transform`) for the PERCENTAGE. `DESIGN.md`'s colour-distribution anatomy
  specifies neither; the authority is the composition reference, corroborated by `DESIGN.md:407`'s
  curve counts and `components.deck-row`'s quantity, both `{typography.numeric}`
  `{colors.text-tertiary}`. The residue's point stands — nothing CHECKS that the right role was
  chosen — and is re-homed unchanged.
- **`StatChip`'s first surface — TRIGGERED FOR THE FIRST TIME, AND DECLINED IN BOTH HALVES.** The
  composition reference ends this panel with three `StatChip`s: `Sources R 19`, `Sources W 16`,
  `Deck value {total}`. **`Deck value` is a price and there is no price anywhere in this system**
  — c4-7 measured it out of existence and amended `DESIGN.md` twice to say so. **"Sources"**
  appears in no UX-DR, no `DESIGN.md` line and no AC; it exists only in `EXPERIENCE.md:34`'s IA
  row (*"Pip distribution, source counts, deck value"*). Neither ships. `StatChip` therefore
  still has **no surface**, and `EXPERIENCE.md:34` / `:173` carry two claims the product does not
  make. **Home: the C4 retro**, with the `DESIGN.md` price amendments as the precedent for how to
  correct an artefact that promises data that does not exist.
- **The cross-file card-shape collision (`:3587-3596`) — NOT TRIGGERED.** This stylesheet styles
  only its own `.colour-*` classes, reaches into no `.card-shape` descendant, and draws no card;
  it neither joins `CARD_SHAPED` nor names `--radius-card`. Both directions asserted.
- **The hydration sweep's no-re-drive window (c4-6 review ruling 1) — TRIGGERED, AND THE
  ONE-STORY REPRIEVE c4-8 OPENED IS OVER.** This panel depends on the sweep for **+48 pips across
  16 of 40 decks**, so a backend blip *during* the sweep leaves those pips permanently missing
  with no error state, while single-faced neighbours look fine. c4-2's edge-triggered recovery
  only re-boots from `refused`/`none`, so nothing re-drives it. **Cited as the documented
  posture, not re-opened** — and this story is the first where the consequence is a moving
  PERCENTAGE rather than a missing pip, which is why `aria-live` is banned here rather than
  merely absent.

**New entries this story raises:**

- **Q16 — `compute_pip_signals` and the colour bar now answer "how much black is this deck"
  differently, on FIVE AXES AT ONCE.** `mana_base.py:343-390` feeds `_mana_efficiency_score`
  through `dimensions.py:667-702` and thence `assess_deck_power`, whose calibration benchmark set
  is Epic 5's frozen artefact — re-validating it does not belong inside a colour bar, so the
  Python is unchanged and `uv run pytest` is untouched. **The divergence is upgraded from latent
  to OBSERVABLE**, and every axis carries its own live count, because c4-8's lesson is on the
  record (*"a bare number in a ledger entry is not checkable when three tests all sound like the
  same policy"*):

  | axis | Python (`compute_pip_signals`) | the bar | live exposure |
  |---|---|---|---:|
  | hybrid `{W/U}` | counts for **nobody** (bare pips only) | credits **both** colours | **29 copies / 10 decks** |
  | Phyrexian `{U/P}` | counts for nobody | counts as its colour | **7 copies / 10 decks** |
  | generic-hybrid `{2/R}` | counts for nobody | counts as red | **0 live** (62 corpus) |
  | the sideboard | **included** by default (`:349-350`) | excluded (Q6) | **87 pips / 5 decks** |
  | split / Adventure / Omen costs | `_pip_cost` reads `card_faces[0]` when top-level is blank, and the WHOLE string otherwise | front face always | **27 rows / 53 copies** |

  The land policies also still differ (whole-string vs front-face word), which is the separate
  entry at `:3536-3572`. **Home: a Python story that owns the scoring surface**, with Epic 5's
  calibration set as the artefact that has to move with it.

- **The numeric mana-value parser has NO home in Phase 1, and the two comments that gave it one
  are corrected.** `curve.ts:36-40` and `curve.test.ts:212-236` both re-homed the split-card
  `cmc` divergence to c4-9 *"which must parse costs anyway"*. **c4-9 parses costs into PIPS**: it
  walks `ManaSymbolToken.colours` and never adds a generic cost, so nothing it wrote converts a
  cost string to a number, and the sentence turned out to describe the whole of `ui/` rather than
  a gap this story would fill. Both comments now name the real condition — *whoever writes a
  numeric mana-value parser* — and the red-in-waiting pin stays exactly as it is. Exposure is
  unchanged and still zero: **137 corpus cards, 0 live**. **Home: a story that needs a mana
  value, and there is none in Phase 1.**

- **THREE MEASUREMENT-INSTRUMENT DEFECTS, and they are the same defect in three places.** This
  epic's standing theme is coverage that reads as coverage; all three of these are in the
  instruments used to MEASURE, which is the worst place for it:
  1. **`card_faces IS NOT NULL` matches all 38,261 rows.** The column is `NOT NULL` and a
     non-faced card stores the JSON *string* `'null'` (35,036 of them). The only correct
     predicate is `json_type(card_faces)='array'` → **3,225**. Any fixture or measurement query
     using the nullable form passes vacuously over the whole corpus.
  2. **`deck_cards` has 2,027 rows but only 1,999 belong to a live deck.** **28 rows / 89 copies
     across 2 deck ids have no `decks` row at all** — orphans from deleted decks. A measurement
     that does not join `decks` over-counts by that much, and this is why §A's totals reproduce
     only with the join present. `deckGroups.ts:230` already quotes the correct 1,999.
  3. **The evasion-probe harness reported both do-nothing negative controls RED**, and the reason
     was not the controls: every one of the 57 files failed with `TypeError: Cannot read
     properties of undefined (reading 'config')` and *"Vitest failed to find the current suite"*
     — **zero assertions executed**, under which every probe reads "caught" for free. This is the
     **third time in this epic** a probe harness has been caught by its own negative controls,
     and the second time the cause was the runner rather than the guard. The harness now
     VALIDATES each run (a real `Tests N passed` line, no crash signature) and retries an invalid
     one rather than scoring it. **Home: the C4 retro** — the repair keeps being re-invented per
     story, and a shared harness is the thing that would stop it.

- **`EXPERIENCE.md:34` and `:173` promise data this product does not have.** The IA row reads
  *"Pip distribution, source counts, deck value"*. Pip distribution ships here; **source counts
  appear in no UX-DR, no `DESIGN.md` line and no AC**, and **deck value is a price, which c4-7
  measured out of existence** (23 columns in `cards`, none a price; the Scryfall importer never
  reads the `prices` object). `DESIGN.md` was amended twice for the price; `EXPERIENCE.md` was
  not. **Home: the C4 retro**, with the `DESIGN.md` amendments as the precedent.

## Deferred from: code review of c4-9-colour-distribution-panel (2026-08-06)

- **The inline-style channel allowlist is global and value-unconstrained** (`ui/eslint.config.js:230`). With two declared channels, cross-story misuse is now expressible: `--curve-bar-height` written from `ColourDistribution.tsx` (or `--colour-bar-share` from `ManaCurve.tsx`), or an absurd value (`'9999%'`), passes both ESLint and `RUNTIME_CUSTOM_PROPERTIES` — the tests-side map already records each channel's owning file, but the ESLint half ignores it. Fix shape when a third channel arrives: per-file scoping of the `:not([key.value=…])` chain, or a tests-side owner assertion walking real call sites.
- **A colour-bar segment below ~0.24% share is invisible while its legend entry remains** (`ColourDistribution.css:116-118`). The 1px `--surface-well` hairline plus global `border-box` consumes the whole resolved width of a sub-1px segment, so the bar shows N−1 colours and the legend N. Needs ~450+ total pips (Commander-scale); thinnest live segment is 15.35px. Revisit if deck scale ever grows past the current corpus.
- **Zero-total conflates "genuinely colourless deck" with "hydration not yet arrived"** (`ColourDistribution.tsx:147`). A deck whose every non-land is blank-top-level-cost renders no panel at first paint, then the panel materializes mid-sweep and snaps the curve from full width to half — an unannounced layout jump sitting inside the accepted c4-6 no-re-drive window. No corpus deck reaches the state; a fix would need a "pips possibly pending" signal distinct from `total === 0`, which is Epic-6-shaped territory (the same seam as the sweep-recovery keeper).

## Deferred from: c4-10-format-check-panel (2026-08-06)

- **A format-check refusal is SILENT, by ruling, and that is a real cost with no signal.**
  (`ui/src/state/formatCheck.ts`, Q6, AC 12.) `'refused'`, `'unreachable'` and *"a 200 that is not
  the contract"* all render `null`: the right column loses its third panel and keeps its first two,
  and **nothing anywhere tells the user a check was attempted and failed**. The ruling is right —
  the two client precedents point opposite ways (`ui/README.md:1263-1286`), and a format-check
  refusal is neither a card (one tile among a hundred) nor a deck (the surface itself), so routing
  it through `panelFor` would replace a working deck view with *"The companion hit a bug"* because
  one auxiliary read failed, which is FR-13 inverted. What is deferred is the *signal*, not the
  posture. **The panel also owns no timer and never retries**, so a transient failure persists
  until reload. **Fix shape**: an inline, calm "could not be checked" state inside the panel's own
  body — never a state panel, never a banner — which needs a vocabulary decision this story had no
  mandate to make. **Home: Epic 7's refetch (c7-3), or 15-6.** (Severity: Low — measured live
  exposure is zero on a healthy backend, and the read is a non-event at 5.2 ms median.)

- **The format check goes stale the moment the agent changes the deck** (Q7, AC 11). One read per
  active-deck id per mount, no refetch, no `deck_changed` handler — `epics-companion-app.md:698`
  puts UX-DR35's refetch wholly in Epic 7, and half-building one here would be a second coalescing
  rule to reconcile with that story's. The concrete failure: the agent adds a banned card, the deck
  view updates through Epic 5/7's path, and the legality panel keeps asserting the *old* verdict —
  which is exactly the loop UJ-1 closes. **Home: c7-3**, named in the module header so its author
  reads it there rather than here. (Severity: Medium once `deck_changed` exists; unreachable today,
  because nothing re-drives the deck except a poll-recovery edge that re-boots the same id.)

- **When a check flips `pass → violation` after first paint, nothing will announce it** (Q16,
  AC 29). No `aria-live` ships here, and the reason is that **nothing moves**: there is no refetch
  (above) and this panel derives nothing from the hydration sweep, so it is the first panel in the
  epic to escape c4-6's no-re-drive window *structurally* rather than by luck of which field it
  needed. The day c7-3 wires `deck_changed`, a silent change becomes reachable and a sighted user
  sees a red pill appear while a screen-reader user is told nothing. **Home: c7-5**, which already
  owns *"the change is announced once, and motion is never the only signal"* together with its
  reduced-motion fallback. (Severity: Low today — unreachable; Medium the day the refetch lands.)
  **STILL OPEN after c7-5 (PR #79, merged 2026-08-15 at `dac0bdc`) — the home was declined, with
  reason.** c7-3 has since wired `deck_changed`, so this is now reachable, not hypothetical: the
  check is a separate async request keyed on detail identity (`App.tsx:342-346`) and settles
  *after* the deck does. c7-5 built the one announcement UX-DR45 licenses — *"Deck updated — N
  cards"* — and announcing a check flip would be a **second** per-refetch announcement arriving
  later, in direct tension with that story's own announce-once AC; no artefact specifies its copy
  or its region, and c7-5 had no mandate to invent either. **This needs a human UX ruling before
  any story can home it** — roughly: (a) fold the verdict into the single announcement (blocks it
  on the slower request), (b) license a second, separately-worded region for legality only, or
  (c) rule the pill's own appearance sufficient and close this. Until then it is **unowned**, not
  c7-6's. (Severity: Medium — now reachable.)

- **The header legality pill was predicted twice and does not exist** (Q4b). `ui/README.md:1344`
  and `:1396` both asserted that c4-10 would add a `standard legal` pill beside the header's format
  and size badges. **It did not ship**, and both lines are corrected in the same commit — the sixth
  forward statement that file has had falsified. Reasons: it is outside story 4.10's five
  acceptance criteria, which describe only the right-column panel; its tone would have to be
  **synthesized** from `format_recognized` plus a row scan — the `is_legal` trap below, in the one
  place on screen with no rows beside it to contradict it; and it would put a second consumer of
  `GET /api/deck/{id}/format-check` in a second column with no shared state. **Home: the C4 retro**,
  or a later header story. (Severity: Low — a mock feature, not a requirement.)

- **`components.legality-row.padding` was off-scale and is amended, but the artefact's OTHER
  numbers for this panel do not exist at all.** (Q10, Q2.) `'9px 2px'` → `'{spacing.2} {spacing.1}'`
  in this commit. What remains: there is **no row-height token, no minimum and no number anywhere**
  for this component, and c4-10's second line makes row height genuinely variable (measured live:
  66.3px with a one-line detail, 86.3–87.3px with two, panel 452 × 475px all-pass and 452 × 517px
  formatless). That was fine to ship — nothing depended on a fixed row — but a later story that
  *does* need one has no artefact to read. **Home: unowned.** (Severity: Low.)

- **The story's own Dev Notes claimed the plugin bundle mirror is "checked by NOTHING", and that
  is FALSE — measured.** `tests/unit/companion/test_spa.py::TestThePluginMirror` compares
  `plugin/server/src/companion/app/static/` against `src/companion/app/static/` **byte-for-byte,
  names and bytes**, and it is what went red on this story's first `uv run pytest` after the
  rebuild. c4-7 raised the gap and homed it on the C4 retro; the gap was already closed. **Two
  entries are corrected rather than re-opened**: the mirror has a local test *and* a CI drift check
  (`.github/workflows/ci.yml`), and the residue is only that neither runs from the `ui/` side, so a
  frontend-only `npm test` still cannot see a stale mirror. **Home: the C4 retro**, downgraded from
  *"unguarded"* to *"guarded on the Python side only"*. (Severity: Low.)

## Deferred from: code review of c4-10-format-check-panel (2026-08-06)

- **The `.test.ts` exemption pair creates an unguarded fixture dead zone.** The `is_legal` scan
  (`ui/tests/format-check-source.test.ts:97`) and the copy guard both exempt every `\.test\.tsx?$`
  file under `src/`, so a `src/**/*.fixtures.test.ts` module is visible to no source-level gate —
  c4-10's `formatCheck.fixtures.test.ts` is the first file to occupy that zone deliberately (its
  header argues the classification), and there is no registry, allowlist or count pinning how many
  such files exist. The next story that wants an authored string or a bound field past a guard has
  been shown the door. **Home: the C4 retro** — decide whether fixture-library test files need a
  declared registry or the exemption needs narrowing. (Severity: Low.)

## Deferred from: c4-11-keyboard-floor-skip-link-tab-order-and-focus-management (2026-08-07)

### Dispositions of the nine inherited deferrals (C2 retro ruling R2)

1. **The 21em oracle scroller is keyboard-unreachable** — ✅ **CLOSED**, all three parts in one
   change, with two corrections to its own population figures. Written in place at the entry itself
   (`:3875`) rather than only here.
2. **The focus ring's appearance has never been looked at** (C2 retro item 4, C3 retro `:566`) —
   📐 **the missing NUMBER is supplied** at the entry itself (`:1634`), and the rendered half is
   discharged by this story's eye-check. ⚠️ The C3 retro's Block-E table (`:489`) mislabels this
   item as *"Deck-list panel with a genuinely long deck"*; `:566` is authoritative.
3. **`CardPlaceholder` renders a `<div>` inside the tile's `<button>`** — ❌ **DECLINED with the
   reason, re-homed to the C4 retro**, and this ledger's stale *"Home: c4-5"* **corrected** (c4-6
   re-homed it in its story record only, never here).
4. **F1: story-key-shaped strings on the rendered view** — ⚠️ **the forward statement was WRONG, in
   two directions.** See the new entry below.
5. **The registry guards are blind to untracked modules** (`:3938-3946`) — **declined, with the
   limit re-declared rather than claimed away.** This story touches four registry guards
   (`CONTAINERS`, `COPY_MODULES`, and its own two new files) and closes none of it: the fix is a
   redesign of how the guards enumerate files, which is a larger change than a story that merely
   *adds* entries should make. `tests/keyboard-floor.test.ts` states the limit in its own header,
   where the next author will read it. **Home: unchanged** — the guard suite.
6. **AC 1's residue has a keyboard half** (`:3919-3925`) — **re-homed unchanged to the epic
   manual-testing checklist, with the exposure re-stated.** Flip controls materialise inside the
   cold-open hydration sweep (~1 s), so a keyboard user Tabbing during a cold open meets Tab stops
   appearing mid-traverse. **This story cannot fix it**: the control's existence depends on hydrated
   data, and the alternatives were priced and declined at c4-6 Q1. Re-measured here: **42 flip
   controls across the 40 real decks, 6 on each Atraxa deck, and 20 of 40 decks have none** — so on
   half the corpus the defect has no exposure at all. (Severity: Low.)
7. **jsdom cannot report an accessible name's spelling** (`:3851-3853`) and **the MDFC pin
   announcement speaks the combined name** (`:3885-3891`) — **confirmed not this story's, re-homed
   unchanged to the epic manual-testing checklist.** Neither is a keyboard-reachability question;
   both need a real screen reader.
8. **The `:root { font: var(--type-body) }` rem-basis entry** (`:1254-1261`, previously **unowned**)
   — ❌ **DECLINED BY NAME rather than left unmentioned**, which is what R2 asks for. This story is
   the closest thing to an accessibility pass the epic has, and it is still the wrong home: the
   entry is about whether the document basis should be `rem` so a browser's font-size setting scales
   the UI — a **typography and layout** decision touching every token and every component, not a
   keyboard-reachability one. Nothing in this story's diff moves it either way. **The honest
   re-home is Epic 8's release-readiness pass**, where a whole-UI scaling decision can be taken with
   the rendered product in hand. (Severity: Low.)
9. **`eslint-plugin-jsx-a11y` carries a DoS advisory** (`:1074-1083`) — **confirmed NOT triggered,
   re-homed unchanged.** `npm audit fix --force` was **not** run. The plugin carries the entire
   UX-DR47 gate and the "fix" is a downgrade across a major boundary.

### Triggered "whoever ships the next X" residues

- **The visually-hidden idiom's third instance** (`ManaCurve.css:141-165`) — ✅ **IT FIRED, and the
  promotion happened in this commit.** c4-9 and c4-10 each asserted it had not. Measured at Task 0:
  exactly **two** production copies existed (`CardDetailChrome.css`, `ManaCurve.css`; the third grep
  hit is a test file). `.visually-hidden` now lives in `src/styles/visually-hidden.css`, `@import`ed
  by `src/index.css` beside `card-geometry.css` and consumed BY CLASS NAME, so no component imports
  a cross-tree stylesheet. **Scope held to the three files it named**: `pointer-events: none` stayed
  with the one consumer that wants it, and `.mana-curve-table`'s rule was removed outright because
  every declaration in it was identical to the shared one.
- **The hydration sweep's no-re-drive window** (c4-6 ruling 1) — **NOT triggered.** This story reads
  no card data, makes no network request, and derives nothing from `boards` beyond "is there at
  least one card". Stated structurally, as c4-10 did.
- **`StatChip`'s first surface** — **not triggered.**
- **The C2 retro's manual-testing items** — item 4 is discharged here (deferral 2 above); item 14
  (the footer's measured 24px box) is Epic 8's and stays there.
- **The cross-file card-shape collision** (`:3587-3596`) — **not triggered.** The skip link draws no
  card: `--radius-card` appears nowhere in `SkipLink.css` and `CARD_SHAPED` holds at four entries.

### New entries declared by c4-11

- **AC 9 is NOT fully covered, and the uncovered half is named.** The skip link's own withdrawal is
  handled — if it holds focus when it unmounts, focus is handed to the `<h1>` deck name through the
  shared `focusHome` idiom, with three arms tested (held focus; never had it; had it and lost it
  before unmounting). **The half this story cannot reach**: a *tile* or a *deck row* holding focus
  when the deck is deleted or refetched to `no-active-deck`. React unmounting the focused node drops
  focus to `<body>` and Tab restarts from the top of the page — the exact failure
  `CardDetail.tsx:385-388` records for the unpin control. The repair is a focus hand-off **at the
  transition**, which needs `deck_changed`; that signal is Epic 7's and **c7-6** is the story that
  renders the transition. **Home: c7-6**, by name, with the mechanism written down.
  (Severity: Medium.)

- **The skip link does not reach the footer, and the footer is why the story says it exists.**
  Measured over all 40 real decks at c4-11: the corridor is **206 Tab stops max / 78 median / 102.0
  mean**; the link removes only the first **105**; **19 of 40** decks remain >50 stops from the
  footer and **36 of 40** remain >20. Behind them are exactly two links, one the Wizards Fan Content
  Policy notice that NFR-08 and `DESIGN.md:419` make *"a condition of public release, not a design
  choice"*. UX-DR31 specifies ONE link and this story shipped exactly that;
  `validation-report-2026-07-25.md:45` already records the gap as gate H3's still-open half.
  **The alternative is costed rather than left to be re-derived**: a second link ("Skip to footer",
  or retargeting this one past the deck list) closes ~42 stops on the median deck and costs one more
  component plus a DESIGN.md + EXPERIENCE.md amendment. **Home: 15-6**, which actions or re-accepts
  the revisit-before-public-release flag. (Severity: Medium.)

- **The connection pill's DOM position is decided by nobody, and three stories each assume someone
  else did it.** UX-DR40 (before this story's rewrite) put it between the deck rows and the footer;
  **c5-7** cites UX-DR47 and is silent on position; **17-1** calls it *"the last stop before the
  footer"* — while `DESIGN.md:445` places it physically **bottom-left**, in the other column from
  the deck rows. c4-11 **declined to decide it without the component** and marked it unbuilt in the
  enumeration instead. **Home: c5-7**, by name. (Severity: Low.)
  **→ CLOSED BY DECISION at c5-7 (2026-08-08)** — a sibling between `</main>` and `<footer>`,
  rendered `position: fixed` bottom-left. The two readings were about different axes. See
  *Dispositions from: dev of c5-7-connection-pill* at the foot of this file.

- **F1's remaining story key is `c6-8`, not `c4-11` — and the C3 retro's count of six was itself an
  undercount.** c4-9 and c4-10 both recorded *"`c4-11` remains, in the skip-link work"*. Verified at
  c4-11: the string `c4-11` appears only in **comments** (`App.tsx`, `App.test.tsx`, and ten sites
  across five other modules) and the skip link renders no story key at all. But
  **`AppShell.tsx:117` renders `slot(nav, 'Agent-view nav pills land here — c6-8.')` and `App.tsx`
  has never passed `nav`**, so that string is on the glass on **every** surface including a fully
  loaded deck — and has been since c2-6. It was missed because every F1 assertion names a `c4-*` key
  and none ever looked for a `c6-*` one: **a count that only checked the keys someone thought of**,
  which is this epic's coverage-that-reads-as-coverage theme in a COUNT rather than in a guard. Both
  halves are now asserted in `App.test.tsx`. The gate itself stays **15-5's**; the remaining key is
  displaced by **c6-8**. (Severity: Low.)

  ✅ **DISPLACED 2026-08-12 by c6-8, and the rendered count is now ZERO** — the first time since
  c2-6 that no story-key-shaped string renders anywhere in the app. `App.tsx` passes
  `nav={<AgentViewsNav />}`, so the shell's placeholder is displaced rather than deleted:
  `AppShell.tsx` was not edited, the string is still in that file, and `AppShell.test.tsx` still
  asserts it against the component's own props. That is the eleventh and last application of
  c2-9's displacement ruling — the shell now has no unfilled slot. Both `App.test.tsx`
  assertions INVERTED rather than being removed (a presence became an absence, and a count of one
  became a count of zero), each with a positive twin proving the pills that displaced the string
  are really on the glass. **The GATE is still 15-5's and this does not discharge it**: a count on
  two rendered fixtures is not a repo-wide guard, and the correction recorded immediately above —
  a count that only checked the keys someone thought of — is exactly why that distinction is
  worth keeping. What c6-8 removes is the last known key, not the possibility of a new one.

- **A SECOND DOCUMENT-LEVEL KEY LISTENER WAS UNGUARDED, AND THE PROBE FOUND IT.** The contract —
  one `keydown` on `document`, in the **bubble** phase, with **capture reserved for c6-5's agent
  view** — is written in `CardDetail.tsx:88-101`, in UX-DR39, in `EXPERIENCE.md` and in this story's
  don't-break list, and was **enforced nowhere**. Probe (j) added a capture-phase listener, ran the
  full 1,655-test suite, and nothing went red. Closed in this commit by
  `tests/keyboard-floor.test.ts`, which asserts the listener SET (one, named by file and event) and
  the PHASE (no `true` / `capture: true` argument), each with a non-vacuity anchor. **Recorded
  rather than quietly fixed**, per the epic's standing rule. (Severity: Medium — now closed.)
  **FULFILLED AT c6-5 (2026-08-10), AND THE GUARD FIRED FOR REAL.** The reservation this entry
  describes now holds a real listener: `AgentView.tsx` registers the capture-phase Esc that closes
  the view and calls `stopPropagation()`. The guard was rewritten from "no capture anywhere" into
  an ENUMERATED two-row table — each listener named by file and event WITH the phase UX-DR39 gives
  it — which is strictly stronger than what it replaced, because it now also catches the agent
  view's own listener being demoted to bubble or CardDetail's being promoted to capture. Its
  non-vacuity anchor gained a third assertion: the capture listener's source must contain
  `stopPropagation()`. **The firing proof is this story's planted red**: removing that one call —
  the exact regression this entry was written about — turned five tests red across three files
  (the two layering tests in `AgentView.test.tsx`, the end-to-end pair in `App.test.tsx`, and this
  guard's own non-vacuity anchor), with the collected count validated at 1,934 before and after.
  Note for the record that the story predicted this guard would stay GREEN under the plant, on the
  grounds that it reads source for a listener's existence rather than its body; the added
  assertion is why it did not.

- **`tests/keyboard-floor.test.ts` cannot see specificity, and says so.** It asks whether a
  `:focus-visible` rule EXISTS for a focusable element's class, not whether a later selector
  outranks it. `CardTile.css:54-75` records a real instance of exactly that trap being found by eye
  rather than by a gate. A selector-weight model is a bigger instrument than this guard needs.
  **Home: unowned** — recorded so the next reader knows the shape of the hole. (Severity: Low.)

- **A naive JSX opening-tag regex fails SILENTLY, and it nearly shipped inside this story's own
  flagship guard.** The first draft of `keyboard-floor.test.ts` stripped JSX comments with
  `\{\s*\/\*[\s\S]*?\*\/\s*\}`; when the first `*/` is not followed by `}` the engine backtracks to
  a later one, and a single match swallowed **4,700 characters of `FlipControl.tsx` — 10,257 bytes
  in, 611 out**. The component then contained no `<button>` at all and was **excused from every rule
  in the file**. Separately, `<button[^>]*>` truncates on the `>` inside `onClick={() => …}`, which
  returned `CardTile`'s button with an EMPTY class list. **Both were caught by the guard's own
  by-FILE non-vacuity anchor rather than by review** — the fifth consecutive story in which this
  epic's coverage-that-reads-as-coverage class landed in the story's own named guard, and the first
  in which the anchor caught it first. (Severity: Low — closed, and recorded as method.)

- **A probe that produces INVALID source is not a caught probe.** First-pass probe (f) mutated
  `SkipLink.tsx` into TSX that would not parse; the run collected **1,596** tests instead of ~1,655
  and every assertion in the suite read "caught" for free. The harness's own `MIN_TESTS` validation
  flagged it as `HARNESS-BROKEN` rather than scoring it, and it was re-run with valid source. This
  is the **fifth** recorded instance in this epic of a probe harness lying, and the second cause
  beyond the ledgered lowercase-drive-letter crash (`:3708-3718`). **Home: the C4 retro**, with the
  method: validate the collected-test count on every probe run, and treat a shortfall as a broken
  harness rather than as evidence. (Severity: Low.)

## Dispositions from: dev of c4-12-empty-deck-state-and-the-cold-open-render-budget (2026-08-07)

> The last story of Epic C4. Every inherited deferral named in its context gets a written
> disposition **here**, in the ledger, rather than only in the story file — the c4-7 failure mode
> the ledger itself records: *"a disposition written in a story file and not in the ledger is a
> disposition nobody will find"*.

> ⚠️ **AND THAT FAILURE MODE IS ITSELF THIS STORY'S FINDING.** **Fifteen shipped source modules
> name `c4-12`** in their headers — `deck.ts`, `deckGroups.ts`, `CardGrid.tsx`, `AnalysisRow.css`,
> `FormatCheck.tsx`, `ManaCurve.tsx`, `ColourDistribution.tsx`, `DeckList.tsx`, `inspection.ts`,
> `App.tsx`, `App.test.tsx`, `CardGrid.test.tsx`, `copy-rules.test.ts`, `DeckBadges.test.tsx`,
> `AppShell.tsx`'s placeholder chain — while this ledger named it **twice**. The work a story
> inherits is discoverable by grepping the CODE, not by reading the ledger, which inverts what the
> ledger is for. **Home: the C4 retro**, with the shape: a story's context pass must grep the
> source tree for its own key, not only the ledger. (Severity: Medium.)

### The fifteen inherited deferrals, each with its disposition

1. **`:1539-1546` — the copy guard cannot decide the half that matters** (*"a reviewer of c2-10,
   c4-3, **c4-12** and c6-6 must READ the copy"*). **HONOURED, and it stays permanently open.** This
   story ships one authored sentence. It was read: second person (*"ask your agent"*), blameless
   (it states a fact and assigns no fault — and the fact is that an empty deck is the NORMAL state
   at creation), and it carries a concrete next action naming the one mechanism that can change the
   state. The reading is recorded in the story's Debug Log, which is the deliverable; no assertion
   was added that pretends to make it.

2. **`:3691-3696` — c4-3's disposition (4)**: the same judgement, discharged by shipping the
   artefact's own label byte-for-byte; *"c4-12 and c6-6 owe the same reading."* **HONOURED, same
   mechanism.** `EMPTY_DECK_LINE` is `EXPERIENCE.md`'s string transcribed, em dash U+2014 and
   trailing period included, and `ui/tests/empty-deck-copy.test.ts` compares the two. **c6-6 still
   owes it.**

3. **`:4247` — zero-total conflates "genuinely colourless" with "hydration not yet arrived"**, so a
   colour panel can materialise mid-sweep and snap the analysis row from full width to half.
   **READ BEFORE WRITING THE GATE, and the composition is UNCHANGED — stated rather than assumed.**
   c4-12's gate is on the format check only, and it is a function of `boards`, which is settled at
   the deck commit and never changes during hydration. So the two conditions do not compose: on an
   empty deck all three panels are absent from first paint and none can materialise later (the
   curve and colour totals cannot rise without cards, and the format check is not requested at
   all); on a non-empty deck c4-12's gate is false throughout and the entry's behaviour is exactly
   as before. **Neither better nor worse. Still open, still c4-9's shape.** (Severity: unchanged.)

4. **`:4251-4263` — a format-check refusal is silent by ruling.** **NOT ABSORBED, and the two
   `null` arms are kept distinguishable** — the state arm (`state.status !== 'report'`) lives in
   `FormatCheck.tsx` and means *no report arrived*; c4-12's arm (`emptyDeck ? null : <FormatCheck/>`)
   lives in `App.tsx` and means *the deck is empty*. Different files, different tests, so a
   reviewer can tell a hidden panel from a failed one. **Home unchanged: c7-3 or 15-6.**

5. **`:3965-3973` — the hydration sweep's no-re-drive window, accepted as designed.** **CITED, not
   re-opened. This story's panel is OUTSIDE it entirely**: Q3/Q4 remove the format check from the
   window by suppressing the request, and the empty-deck line derives from `boards`, which is
   settled before any hydration begins.

6. **`:2255-2263` — `ETag`/conditional requests, homed on the C4 retro** *"where the epic's twelve
   stories are the ones that will have exercised the cache on real decks by then"*. **c4-12 is the
   twelfth, and it feeds the measurement forward rather than deciding.** Measured 2026-08-07 in
   Chrome 151 over CDP, real 99-card deck, n=5 per arm: a **repeat visit transfers 0 bytes of image
   data for 106 image requests** (`immutable, max-age=31536000` doing its job — the browser never
   asks), while the **99 card-detail JSON reads are paid in full on every visit** (not cacheable).
   So an `ETag` would buy nothing on images and everything it could buy is on the card route.
   **Decision still the retro's.**

7. **`:3203-3216` / `:3830-3833` — the ~124 s cold paint against a dead CDN, never reproduced.**
   **Not this story; added to the epic manual-testing checklist by name.** What IS now measured is
   the healthy cold path: with the deck's 99 images moved out of the backend cache (n=3), the last
   image response lands at **~11.0 s** while **full six-surface layout is unmoved at 278–390 ms**.

8. **`:3777-3784` — the pacer queue vs the pool timeout; `loading="lazy"` as the one client-side
   lever.** **UNCHANGED — this story did not reach for it.** The Q10 work turned out not to need a
   client-side lever at all: the budget is met, and the one lever that was priced (the effect
   ordering) is not an image lever. Recorded so the pre-pricing is not read as spent.

9. **`:1672-1681` — `list_decks` materialises every deck's card list to count it.**
   **RE-MEASURED AT 42 DECKS, NOT FIXED:** `GET /api/decks` costs ~95 ms of backend CPU and repeats
   every 2 s (`poller.ts`, `POLL_BASE_MS = 2_000`). It is not on the deck surface's critical path —
   `surfaceOf` prefers the deck — but it burns one of six sockets and one core through the first
   ~100 ms of a cold open. **Home unchanged: 17-3.**

10. **`:4236-4241`, `:4161-4169` — `EXPERIENCE.md` promises source counts and deck value;
    `StatChip` still has no surface.** **CONFIRMED STILL OPEN.** Not this story. (`ui/README.md`'s
    claim that six primitives lacked a consumer was corrected here — `StatChip` is now the only
    one, which sharpens this entry rather than closing it.)

11. **`:1592-1609` — 10px ALL-CAPS legal text readability. Home: Epic 8.** **NOT TOUCHED.**

12. **`:4399-4409` — the skip link does not reach the footer (205 stops / 102.0 skipped). Home:
    15-6.** **NOT TOUCHED**, and no skip-link copy was edited. ⚠️ The corridor figure WAS corrected
    in `DESIGN.md`, which read *"100+ Tab stops"* while `EXPERIENCE.md` already carried c4-11's
    measured numbers — two peer artefacts disagreeing about the same measurement. The ledger entry
    itself is unchanged.

13. **`:4355-4362` — the `rem` basis. Declined by name at c4-11, re-homed to Epic 8.** **NOT TAKEN.**

14. **`:4313-4320` — the `.test.ts` exemption pair's unguarded fixture dead zone.**
    **DIRECTLY RELEVANT AND HONOURED IN PLACE.** Every empty-deck fixture this story adds lives in
    exactly that zone and is **declared synthetic where it is written** — `App.test.tsx`'s
    `emptyDeck()` and `CardGrid.test.tsx`'s `boardsOf([])` both carry the measurement that forces
    it: **0 of 42 decks have zero `deck_cards` rows**, so there is no verified-real row to reach
    for. **Entry unchanged; home still the C4 retro.**

15. **`:4044-4047`, `:4301-4309` — the plugin bundle mirror is guarded on the Python side only.**
    **REBUILT AND sha256-VERIFIED BY HAND** in this commit, per the story's AC. **Entry unchanged:
    a frontend-only `npm test` still cannot see a stale mirror. Home: the C4 retro.**

### New, from this story

- **⚠️ THE `decks` TABLE AND `deck_cards` DISAGREE: 28 ORPHAN ROWS ACROSS 2 DELETED DECKS.**
  Measured read-only 2026-08-07: `SELECT COUNT(DISTINCT deck_id) FROM deck_cards` returns **44**
  while `SELECT COUNT(*) FROM decks` returns **42**. Two deck ids (`136ce5b1-…`, 22 rows / 57
  cards, and `55af0ef7-…`, 6 rows / 32 cards) have card rows and no deck. So `delete_deck` leaves
  its `deck_cards` behind — the same shape as the already-recorded fact that `remove_card_from_deck`
  never touches `decks`. **No user-visible effect today** (every read path starts from a `decks`
  row, so the orphans are unreachable), and it is invisible to any frontend gate. It also means
  **any census computed from `deck_cards` alone over-counts by two decks** — the story context's
  own §F distribution did, and this ledger entry is how the next census avoids it.
  **Home: 17-3**, with the Python-side counterpart. (Severity: Low — data hygiene, not behaviour.)

- **A sideboard-only deck renders an empty grid with NO empty-deck line, and no artefact describes
  that state.** `deckIsEmpty` is sideboard-inclusive by c4-11's ruling (a deck holding a sideboard
  has cards, and *"This deck is empty"* over it would be false copy under UX-DR33), while
  `CardGrid` draws commander + mainboard only. **Unreachable from live data — 0 of 42 decks have
  zero mainboard rows and ≥1 sideboard row** — so it is recorded as a named residue rather than
  answered by inventing copy. Pinned in `CardGrid.test.tsx` so the choice is visible if it is ever
  wrong. **Home: the C4 retro.** (Severity: Low.)

- **⚠️ UX-DR20 SAYS THE DETAIL PANEL IS "NEVER EMPTY WHILE A DECK IS LOADED", AND AN EMPTY DECK IS
  A LOADED DECK — ARTEFACT DEFECT, NOT REPAIRED HERE.** `inspection.ts`'s `coldOpenTargetOf`
  returns `null` for a deck with no cards, with the comment *"which is c4-12's copy"*. c4-11's
  correction resolved only the skip-link-TARGET half (*"`CardDetail` renders its frame and heading
  unconditionally"*); **the panel's BODY on an empty deck is specified nowhere**, and neither is
  `DeckList`'s — `DeckList.tsx` records that gap verbatim and refuses to invent copy for it.
  `EXPERIENCE.md`'s two rows and this story's own ACs each name exactly THREE panels to hide and
  neither of these is among them.
  **SEEN, NOT ARGUED (eye-check, Chrome 151, 2026-08-07):** the two panels render as **57px empty
  shells** — a `CARD DETAIL` header over a blank body and a `DECK LIST` header over a blank body —
  beside a 47px grid strip, on an otherwise empty 1720×1080 canvas. That is precisely the
  *"reads as a loading failure rather than as an absent feature"* failure mode `DESIGN.md` names by
  hand. Ruled: **status quo, recorded, not repaired** — adding a fourth panel to the hide list
  invents spec and inventing an empty-state sentence puts unsourced words on the glass.
  **Home: the C4 retro**, with the DESIGN.md amendments as precedent. (Severity: Medium.)

- **The effect ordering in `App.tsx` is worth ~180 ms of cold-open layout time and nothing enforced
  it.** Measured over CDP, Chrome 151, the real 99-card deck: as shipped (sweep declared first) the
  format-check request sits at **queue position 106–107** and full six-surface layout is
  **311 / 363 / 428 ms** (min/median/max, n=5); with the two blocks swapped it is at **position 7**
  and layout is **120 / 185 / 520 ms** (n=5). **Not swapped** — NFR-05's budget is met with ~570 ms
  of headroom in every run of both cache readings, so the swap is an unrequested change to the
  cold-open path, and the swapped arm's spread is wider. **Both effect comments now name the
  other's queue position**, which is the only thing stopping the next reader reordering them by
  accident. **Home: 17-3** (NFR-05 profiling is Phase 2), where the 180 ms is already priced.
  (Severity: Low — an available improvement, not a defect.)

- **⚠️ NFR-05's OWNER CANNOT CLOSE ITS OWN GAP, AND THIS STORY IS WHERE THAT WOULD HAVE BITTEN.**
  `epics-companion-app.md` makes **Epic 4 the owner** of NFR-05 (*"the owner still holds
  acceptance"*), while the only story carrying the gap-closing clause — *"any measured gap … is
  closed, or recorded as an accepted deviation with its reason — not left ambiguous"* — is **10.3,
  which is Phase 2**. So the acceptance point ships in this release and the repair does not.
  **It did not bite: the measurement passes, so there is no gap to close.** Raised in the open
  anyway, because the structure is unchanged and the next measurement may not pass.
  **Home: the C4 retro / 17-3.** (Severity: Low today, structural.)

- **~60 stale `DESIGN.md:NNN` anchors across 25 files, and the guard that looks like it checks them
  does not.** `shell.test.ts` requires the *string* `"DESIGN.md"` within a sentence of every `px`
  literal in a component stylesheet — it **never resolves the line number**. The c4-7/c4-9/c4-10/
  c4-12 frontmatter amendments each grew the file and nothing re-based the citations; at least one
  now cites a real but **wrong** component (`FormatCheck.css` → `DESIGN.md:423`, which is the Card
  tile bullet). This is the epic's coverage-that-reads-as-coverage theme **inside a citation gate**.
  **Not fixed here** — ~60 edits and a red guard on a story that is otherwise one sentence and one
  conditional. **Home: the C4 retro**, with the guard's shape written down: resolve the anchor and
  assert the cited line names the component. (Severity: Medium.)

- **"Blank screen" has an operational definition for the first time, and it is this story's only.**
  UX-DR36 and `EXPERIENCE.md` both assert *"a blank screen is never shown after first paint"* and
  neither says what it means. Defined in `App.test.tsx` for c4-12 as: *at no point from first paint
  onward does the app render a viewport containing none of {header, left-column content,
  right-column content, footer}*. ⚠️ The criterion is a **verbatim duplicate of a story 7.4 AC**,
  and the **refetch half** — the teardown UX-DR36 is really about — is **c7-4's**, handed back by
  name. `states.ts`'s `NO_UI_RESPONSE` (three reasons that deliberately render nothing) is the one
  classification in tension with the sentence: agent-facing and unreachable from a user surface
  today, so it blanks nothing — but a story that routed one of them to a user surface would satisfy
  `NO_UI_RESPONSE` and violate UX-DR36 in the same commit. **Home: c7-4.** (Severity: Low.)

- **A newly written guard's regex was `\n`-only against CRLF artefacts, and only its non-vacuity
  anchor caught it.** `empty-deck-copy.test.ts`'s DESIGN.md frontmatter reader used `\n {2}key:\n`;
  the UX artefacts are **CRLF (485 of 485 line endings)**, so it captured the empty string and every
  assertion in that describe would have passed over nothing. Caught because the anchor was written
  FIRST and failed. **Seventh consecutive story in which this epic's coverage-that-reads-as-coverage
  class landed in the story's own new guard — and the second in which the anchor caught it before a
  reviewer did.** Recorded as method: **anchor first, then assert.** (Severity: Low — closed.)

## Deferred from: code review of c4-12-empty-deck-state-and-the-cold-open-render-budget (2026-08-07)

- **One-frame stale format-check report on a non-empty→non-empty deck switch** (`ui/src/App.tsx:350`).
  When the active deck changes from deck A to deck B, the commit frame that renders deck B's header
  precedes the effect pass that calls `clearFormatCheck`, so deck A's legality report can render
  under deck B's header for one commit. Pre-existing shape — c4-12's deps change (`emptyDeck` added)
  neither caused nor widened it. Candidate fixes if it ever matters on the glass: clear synchronously
  on `deckId` change, or key the panel (`<FormatCheck key={deckId} />`).
- **No committed CDP measurement harness behind the render-budget numbers** (`ui/src/App.tsx:244,331`).
  Both effect comments carry "⚠️ DO NOT REORDER EITHER BLOCK WITHOUT RE-MEASURING" while every
  measurement was taken with a scratchpad throwaway script (the story's own Task 4 sanctioned the
  scratchpad), so AC 18's queue positions and latencies are preserved only as prose and are
  irreproducible from the repo. Home on the **C4 retro** beside the ~60 stale `DESIGN.md:NNN`
  anchors: decide whether a minimal committed harness (or a recorded recipe) is owed before anyone
  is allowed to act on the reorder lever those comments price.

## Rulings from: the EPIC C4 RETROSPECTIVE (2026-08-07)

Eight decisions ruled by Sathias. R1/R2/R6 are process and live in
`epic-c4-retro-2026-08-07.md`'s *Team agreements*; the ledger dispositions are below.

### R5 — four entries CLOSED, each with the measurement that closes it

- ✅ **CLOSED as SUPERSEDED — `GET /api/cards/{card_id}` sets no cache headers / `ETag`
  (`:2101`, `:2255-2263`).** Homed here at c4-1 *"where the epic's twelve stories are the ones that
  will have exercised the cache on real decks by then"*. Twelve have. The entry's own worst case —
  *"a c4-x deck view hydrating 60–100 cards re-fetches every full record on every render"* — is
  **structurally impossible**: `cards.ts` issues one request per id per tab and never re-requests a
  hydrated id (measured live at c4-6, 99 reads on the 99-card deck, ceiling confirmed). The client
  also sends `cache: 'no-store'` on card reads **deliberately**, so that a header-less response
  cannot be heuristically cached into staleness across a database refresh — which would make an
  `ETag` inert until that separate decision were revisited. Population an `ETag` would serve: page
  reloads, not renders. **No further work. Re-open only if the `no-store` decision is revisited.**

- ✅ **CLOSED as DECLINED — splitting `src/companion/app/images.py` (`:2989-2997`, `:3074-3082`,
  `:3835-3838`).** Parked by Sathias at the C3 retro pending evidence; the evidence is now in and it
  argues against the split. c4-4 mounted ~99 `<img>` at once (`decoding="async"`, no
  `loading="lazy"` — the maximum burst the pacer entry describes) and c4-6 became the first `?face=`
  caller. Between them the route, the **pacer**, the **disk cache** and the **negative cache** were
  exercised from a real browser against real decks and **needed no change to any of them**: warm
  paint 99 requests in 0.55 s, `?face=1` behaves as an ordinary distinct key throughout, no pacer
  constant moved. The measured shape stands as recorded — **1,837 lines = 1,370 prose (74.6%) + 377
  code (20.5%) + 289 blank** — so a split would divide ~125 lines of code per mechanism and destroy
  the 108-line module header that explains their interaction (cache checked *before* the pacer;
  negative cache *outside* `pacer.slot()`). Winston's C3 counter stands re-confirmed: finding
  density tracked difficulty, not line count. **The adjacent action identified at C3 — a
  prose-freshness pass over the nine large docstrings — is NOT closed by this and stays available.**

- ✅ **CLOSED as ACCEPTED — `CardPlaceholder` renders a `<div>` inside the tile's `<button>`
  (`:3743-3748`, `:3859-3875`).** Declined at c4-11 with the reason and re-homed here. Every engine
  renders it; React 19.2 warns in its **development build only** (`grep -c` over both react-dom
  builds gives 1 and 0) while the invalid nesting survives into the runtime tree; the accessible
  name computes normally. c4-6 closed the **harder** version of the same seam — an *interactive*
  descendant — by making the flip control a sibling, with `CardTile.test.tsx` asserting
  `tile.querySelectorAll('button, a, input, select, textarea')` is empty. What remains is a
  spec-letter violation with **zero measured accessibility impact**, against a fix that means
  changing `CardPlaceholder`'s root — the edit c4-4 was explicitly told not to make, and one that
  would serve one consumer against the other's interest. **This entry's own history is part of the
  ruling:** its home was stale by two stories because c4-6 re-homed it in its story record and never
  here. That failure mode is now a standing agreement (see below).

- ✅ **CLOSED by AMENDING THE ARTEFACT — `EXPERIENCE.md:34` and `:173` promise data this product
  does not have (`:4236-4241`, `:4161-4169`).** Both rows amended in the same commit as this
  disposition, using the two `DESIGN.md` price amendments (c4-7) as the precedent for correcting an
  artefact that promises data that does not exist. **`deck value` is a price**, and there is no
  price anywhere in this system — 23 columns in `cards`, none a price; no schema field; and the
  Scryfall importer never reads the `prices` object, so it was never imported rather than dropped
  (with a Python test asserting the absence on purpose under the c3-2 Q4 ruling). **`source counts`**
  appear in no UX-DR, no `DESIGN.md` line and no AC; they exist only in that IA row.
  **Consequence, stated rather than left implied: `StatChip` has had NO surface since c2-7 and now
  has no pending one.** It remains a shipped, tested, zero-consumer primitive — a fact, not a
  backlog item. The `StatChip`-first-surface residue is closed with it.

### R3 — F4 ledgered, closing C3 retro action item 6

- ❗ **A failed first import leaves a schema-only `cards.db` that the companion then file-locks.**
  Found by Sathias during C3 manual testing (finding F4, 2026-08-02) and **never ledgered** — C3
  action item 6 asked for exactly this entry and it was not written, which is why it is being
  written at the next retro instead. The importer creates the schema **before** downloading, so a
  failed download leaves a rows-less database behind; the companion's next poll (≤ 30 s) opens it
  under c1-6's lazy engine, and from that moment the user **can neither delete nor replace the
  partial database** without stopping the companion — while the panel correctly instructs them to
  re-run the import command.
  **What is already right:** the *display* is correct (`is_database_initialized` returns `False` for
  present-but-empty), and the blast radius is bounded — a second process *writing into* the file is
  fine under WAL, so only wholesale file replacement is blocked.
  **This is a recovery-path defect, not an import-path one**, and it is adjacent to but distinct
  from c1-6's ledgered *"cached-engine path re-plants a zero-byte file"*.
  **Home: 15-4** (install / first-run readiness), which owns the fresh-install experience a person
  actually meets. (Severity: Medium — reachable on the public v0.4.0 today; bounded and recoverable
  by stopping the companion.)

  **CORRECTED 2026-08-19 (Greptile P2 on PR #88): "can neither delete nor replace" is TRUE ON
  WINDOWS ONLY, and the POSIX behaviour is worse.** This entry was written from F4's Windows
  manual-testing observation and story 15-4's README generalised it to every platform before the
  review caught it. On macOS and Linux the unlink SUCCEEDS — the directory entry goes, while the
  companion's pooled connections keep the old inode alive (`AsyncAdaptedQueuePool`, size 5 +
  overflow 10, no recycle, documented at `src/companion/app/deps.py:305`). A re-import then writes
  a NEW inode at the same path that those connections never see, and `Database.session_factory()`
  returns its CACHED factory without re-running `_create()`'s existence check
  (`deps.py:150-158`), so nothing notices. The per-request readiness probe cannot help: it is
  `is_database_initialized(session)`, a query down an already-open connection, not a file check.
  Net effect on Brad's own platform: the user follows the instruction, deletes, re-imports, and the
  page goes on saying the database is not set up until the companion is restarted — silently
  contradicting FR-22's "picked up with no restart". The recovery does not change (stop the app
  first) but its RATIONALE does, and the silent variant is the one worth naming. README corrected;
  `test_companion_docs.py::test_the_failed_import_recovery_says_stop_the_app_first` now pins both
  platforms and the POSIX consequence so the two cannot be collapsed back into one sentence.
  Severity unchanged at Medium; the code defect remains open and unfixed.

### R4 — the empty-deck state ships as written

- ⚖️ **RULED, status quo (`:4590-4604`).** The two empty right-column panel shells stand. Adding a
  fourth panel to the hide list invents spec; inventing an empty-state sentence puts unsourced words
  on the glass. **Entry stays open at Medium with the eye-check attached** — Chrome 151, 1720×1080:
  a `CARD DETAIL` header over a blank body and a `DECK LIST` header over a blank body, 57 px each,
  beside a 47 px grid strip — because that picture is what a revisit should decide against.
  c4-12's own warning is recorded with it: *changing it is cheap today and expensive at Epic 8.*

### New standing agreement raised by this ledger's own failures

- 📌 **A disposition lives in the ledger, not only in the story record.** c4-11's sentence,
  promoted: *"a disposition written in a story file and not in the ledger is a disposition nobody
  will find."* Three worked instances in C4 — the `<div>`-in-`<button>` home stale by two stories;
  c4-7's nine dispositions and three new entries existing only in its Dev Agent Record until review
  demanded them; and **fifteen shipped source modules naming `c4-12` in their headers while this
  file named it twice**. A story that re-homes an entry edits `deferred-work.md` in the same commit,
  and a story's context pass greps the **source tree** for its own key, not only this file.

## From: the Epic C4 manual-testing run — BLOCK I (2026-08-07)

Block I was homed on **c4-2** at the C3 retro, acknowledged there and not run, so it had been
carried across two epics. Run at the C4 retro through headless Chrome over CDP against a real
backend on an isolated `PLANESWALKER_DATA_DIR`. **All four panels are now rendered by a real
engine** and the results are in `epic-c4-retro-2026-08-07.md`. Three entries change here.

- ✅ **CLOSED — `database-updating`, `database-updating-stalled` and the state panels were never
  rendered by a real engine (`:3310-3316`).** They have been now. A3: a `cards.db` that exists but
  is not a SQLite file produces `DatabaseError` → `503 database_unavailable` → **"Card database is
  updating."**, which is the entry's whole question answered — *a different panel from the same 503
  status as A1's*. A4: the escalation fired at **t = 60.1 s on the 6th poll**, with both gates
  observed independently. The `internal-error` panel remains unrendered by a real engine and is the
  only member of the family still owed a first look; it is reachable from a malformed `200` body on
  the deck read (c4-2's caught refusal), which is a harder fixture to stage than a corrupt file.
  **Residue re-homed: `internal-error`'s first render → the Epic C5 manual-testing checklist.**

- ⚠️ **CONFIRMED, NOT CLOSED — a backend that cannot be reached at all leaves whatever panel is on
  screen, including on the very first load (`:3318-3328`).** Reproduced exactly as written: a first
  load with nothing reachable renders **"No deck on the glass. Ask your agent to set an active deck
  — it will appear here the moment it does."** and holds it while polls fail silently (4 attempts
  observed, no state change). **Tolerability judged at the C4 retro, as the checklist item asks:
  the entry undersells it by one notch.** The panel is not merely uninformative — its copy is
  **actionable and wrong**, directing the user to an agent action that cannot succeed while the
  same backend is unreachable. A1's copy is inert by comparison. **Home unchanged: c5-6**, whose
  `disconnected` panel is the true one. Severity unchanged (Low-Medium: reachable only by starting
  the browser before the backend), because the blast radius is not what moved — the copy's
  imperative is.

- 📌 **AMENDED — C3 action item 4 / F1: story-key-shaped strings on the rendered view.** The
  recorded count is **wrong, and low**. c4-11 recorded one remaining key (`c6-8`) and that is true
  **of a rendered deck view**, which is the only surface `App.test.tsx` asserts. Measured on a
  **state-panel surface**: **six** distinct keys render — `c2-7`, `c4-2`, `c4-5`, `c4-7`, `c4-10`,
  `c6-8`, seven occurrences. Both halves confirmed in one run (the deck view at the end of the
  re-drive scenario carries `c6-8` alone). The mechanism is that the placeholders are displaced
  **by the panels that replace them**, so every surface where those panels do not render still
  carries every key — and the first screen a fresh install ever sees is exactly such a surface.
  This is the epic's coverage-that-reads-as-coverage class again: the assertion's scope is narrower
  than the claim resting on it. **Home unchanged (15-5), priority raised**, and the gate's shape is
  now specified by evidence: it must scan a rendered STATE-PANEL surface, not only a deck view.

- ⚠️ **RE-OPENED — C3 retro finding F3 (vertical anchoring on an empty page) was homed on c4-12 and
  is only half closed.** c4-12 shipped the empty-*deck* state; the **state-panel** case — panel
  top-aligned with a large void beneath it, on the first screen of a fresh install — was never in
  that story's scope and is unchanged. Seen again in this run's A1 and A3 screenshots.
  **Home: unowned.** (Severity: Low — cosmetic, on a surface a healthy install passes through once.)

### What this run CONFIRMED rather than changed

- **c4-2's edge-triggered re-drive works on a real screen, and had never been seen.** Cold open
  with an active deck set and no database → the deck read refuses and the glass shows the stale
  panel; the database is then planted **while the tab is open** (no restart — with no file present
  the backend holds no handle, so this is FR-22's own scenario extended to the deck path). Deck
  reads went **1 → 3** and the panel was replaced by the full deck view in **~5 s**, with **one**
  page navigation for the whole test. That is the High c4-2's review found and fixed, observed.
- **C3 ruling R3's terminal consequence, felt rather than reasoned.** With the database restored
  and the wire answering `200`, the poll count moved by **exactly 0** across 45 s and the stalled
  panel stayed. R3 accepted this knowingly; what the run adds is that **the panel's own action line
  names `initialize_database`**, so a user who complies *and succeeds* sees no change. Recorded
  against c5-6, which owns the recovery.

## From: the Epic C4 retrospective — the CDP harness is PROMOTED (2026-08-07)

- ✅ **CLOSED — "No committed CDP measurement harness behind the render-budget numbers"
  (`:4663-4669`, from c4-12's code review).** The entry asked whether *"a minimal committed harness
  (or a recorded recipe) is owed before anyone is allowed to act on the reorder lever those comments
  price."* **A harness is owed and is now committed: `scripts/cdp_harness.py`.**

  It is the house pattern written down rather than a new one — c4-12's own Q9 specifies the shape
  (*"ad-hoc CDP in Python (websockets + httpx), Chrome `--headless=new`, fresh profile, against the
  committed SPA served by the running backend"*) and the only change is that it is no longer ad hoc.
  Three subcommands: `budget` (the NFR-05 cold-open measurement), `panels` (the state panels of
  manual-checklist Block I), `shot`.

  **It reproduces the number the `App.tsx` comments cite, independently.** Run against the same
  99-card deck (`Atraxa Counter Cabinet v2 (owned)`), n=5, fresh Chrome profile per run:

  | | c4-12's record | this harness, 2026-08-07 |
  |---|---|---|
  | format-check queue position | **106–107** | **106**, all five runs |
  | full six-surface layout | 311 / 363 / 428 ms | **382 / 403 / 453 ms** |
  | card reads · total requests | 99 · ~205 | **99 · 213** |

  The **queue position matches exactly**, and it is the structural claim the two effect comments
  actually rest on. The layout times run ~40–70 ms higher and the difference is *not* treated as a
  discrepancy: this arm ran against a data directory with **no warm backend image cache** (a fresh
  copy holding only `cards.db`), which is nearer c4-12's cold-image arm than its fresh-profile one,
  on a machine with sixteen MCP server processes resident. Both sets sit far inside NFR-05's
  1,000 ms budget. **The lever is now re-measurable before anyone pulls it**, which is what the
  entry asked for.

  Q7's clock is preserved verbatim: `performance.timeOrigin` read in-page, stop at the moment the
  **last** of the six named surfaces enters the DOM, seen by a `MutationObserver` installed at
  **document-start**.

  ⚠️ **What this does NOT close, stated because a harness that reads as covering more than it does
  is this epic's own theme.** The C4 retro's action item 4 asks for **one committed *probe*
  harness** — the thing that runs the full `npm test` for an evasion probe and validates the
  collected-test count before scoring the run. **That is a different harness and it is still owed.**
  `cdp_harness.py` drives a browser; it does not run vitest, and none of the five recorded
  probe-harness lies would have been caught by it. Item 4 stays open.

  📌 **The promotion found a real defect in its own first version, and the refusal caught it.** The
  observer attached to `document.documentElement`, which is **null at document-start**, so
  `.observe()` threw, the IIFE aborted, and every run reported "no surfaces arrived" while the page
  rendered all six perfectly. The harness **refused to report a number** (by design — every C4 probe
  harness that lied did so by scoring an empty run) but could not say *why*, so it now captures the
  install-time error and prints it with the refusal. Fixed by observing `document`, which exists at
  document-start. Recorded rather than quietly repaired: *an instrument that dies at install time
  and leaves an empty result is indistinguishable from a page that rendered nothing.*

  `websockets>=12.0` is now **declared** in the dev dependency group rather than borrowed from
  `uvicorn[standard]`'s extra, and `plugin/server/pyproject.toml` was rebuilt to match (the mirror
  copies `pyproject.toml` verbatim — caught by diffing the mirror, not by a guard, which is the
  "guarded on the Python side only" residue behaving exactly as recorded). Gates after: `ruff check .`,
  `ruff format --check .` (308 files), `mypy src/` and `mypy src/ --platform win32` (89 files) green;
  `uv run pytest` **2,501 passed / 1 skipped — unchanged**.


## Deferred from: c5-1-the-event-envelope-and-every-per-kind-payload-contract (2026-08-07)

- **AD-1's construction-limit family no longer scans `src/companion/contracts.py`, and that is a
  narrowed guard rather than a closed one.** AD-7 caps an agent push at **60** items, and
  `contracts.py` declares it as `_MAX_ITEMS = 60`. `test_routes_format_check.py`'s AD-1 scan flags
  any `60` or `15` anywhere under `src/companion/` — so the cap reddened the suite on first run.
  **This was found by the guard, not predicted by the story**: the story's DON'T-BREAK list has
  seven entries and this is not among them, and it is the **second measured collision** of this
  family after c3-6's `FETCH_CONCURRENCY = 4`. The file's own docstring had just claimed *"nothing
  in this shell has an innocent reason to write `60` or `15`"*; that sentence is now corrected in
  place rather than left standing.

  **What was done, and why not the c3-6 move.** c3-6 answered its collision by dropping `4` from
  `_LIMIT_LITERALS` entirely. Doing that to `60` would have cost the family its most distinctive
  literal **everywhere**, including in the route shell where a deck-size rule genuinely could be
  reimplemented. Instead a new `_LIMIT_FAMILY_EXEMPT` names **one file**, and exempts it from **one
  family**: a legality read, a validator import, a `.quantity` count or a rebuilt format-name set in
  `contracts.py` still flags exactly as before. The justification is structural rather than
  stylistic — `contracts.py` is the AD-3 leaf, import-constrained to stdlib and `pydantic`, so it
  cannot reach the card database, the deck repository or `src.logic`; a deck-construction rule needs
  a deck to be about, and there is none in scope. Spelling the cap as something other than `60` to
  slip past the scan was not available: that module's own docstring rules obfuscation a violation on
  sight.

  **What it costs, stated rather than glossed.** A future author could implement a deck-size rule
  inside `contracts.py` — a validator counting `card_ids` against 60 and calling it legality — and
  this family would not see it. Two things stand where it used to, and neither is this family: the
  AD-3 import boundary denies that author the card data such a rule would have to be about, and
  `test_contracts.py` pins every cap by literal value **and** by which field it bounds. Three new
  tests hold the exemption narrow (`test_the_limit_exemption_is_scoped_to_one_file`,
  `test_the_exempt_file_still_flags_every_other_family`,
  `test_the_exemption_names_only_paths_that_exist`), each with a firing proof through the full run.
  **Home for a revisit: the C5 retrospective**, which is where "is a per-file exemption the right
  shape, or should the family key on *use* rather than on *presence* of a literal?" should be
  decided — with two collisions on the record instead of one. (Severity: Low, and narrower than the
  alternative that was declined.)
  **RULED at the C5 retro (2026-08-09), ENTRY CLOSED:** the family stays PRESENCE-KEYED with narrow
  per-file exemptions — c5-1's `_LIMIT_FAMILY_EXEMPT` shape (one file, one family, held by three
  tests with firing proofs) is the standing remedy. A use-keyed redesign was declined as costing
  more than the two collisions did: both collisions were caught at zero escape cost, and the
  exemption's blind spot (a future deck-size rule written inside `contracts.py`) is stated where it
  lives. A THIRD collision reopens the question. Recorded as epic-c5 action item R10.

- **The probe harness exists for pytest and does not exist for `ui/`.** C4 retro action item 4 was
  homed on c5-1 by name and is **discharged only on the Python side** (Q11, Brad 2026-08-07):
  `scripts/probe_harness.py` owns its own pytest argv — it accepts no test paths, no `-k` and no
  `-m` — so the recorded lie of "a single-file run presented as a full run" is not something a
  caller can do wrong. It reports the collected count with every verdict and refuses to score a run
  that did not complete. **It earned that last check during this very story**: a planted violation
  that happened to be a `SyntaxError` produced "0 failed", and only the collected count (1,450
  against 2,526) and pytest's exit 2 revealed the suite had never run. That check is now in the
  harness.

  **What is still owed: the vitest half.** Three of the five recorded probe-harness lies
  (a lowercase-drive working directory, `shell=True` on Windows, an unparseable TSX file) are
  specific to the frontend toolchain and cannot occur in a Python-only story, which is why this was
  scoped rather than built whole. **Home: the first C5 story that touches `ui/` and plants a
  frontend guard** — realistically **c5-6** or the first Epic 6 view story. (Severity: Low.)
  **RE-HOMED at the C5 retro (2026-08-09) to epic-c5 action item R5 (C6 prep, before Epic 6's
  first frontend story):** c5-6 scope-declined it (Q9) and c5-7 ran FIFTEEN frontend plants by
  hand — the epic's own measurement of what the missing half costs. The C4 sprint-status item is
  closed as re-keyed; this entry stays the description of record until R5 pays it.

- **Two artefact amendments are owed and are recorded here so they are not rediscovered
  (AC 26).** Neither is c5-1's to make — both live in planning artifacts this story does not own —
  and both are now decided rather than open.

  1. **AD-6's kind enum is SIX, not five.** `ARCHITECTURE-SPINE.md` and the epic's Contracts section
     both still enumerate five, naming only `deck_changed`. Story 5.1's own acceptance criteria add
     `active_deck_changed` with its justification, and being both later and more specific it wins;
     `contracts.py` ships six and `test_contracts.py` pins the set against a hand-written literal.
     The spine amendment is **already tracked as owed at Epic 8** — this entry only records that the
     code went first and that the disagreement is a known supersession, not drift.
  2. **413 `payload_too_large`, not 422.** AD-7, `epics:237` and Story 6.4 all still say **422**;
     AD-16, Story 5.5 and Story 6.1 say **413**, *"per the c1-4 review ruling, was 422"*. **413 is
     authoritative**, and `contracts.py`'s `_MAX_ENVELOPE_BYTES` docstring now says so at the point
     of use. This is not merely a documentation tidy: `test_committed_schema.py` asserts FastAPI's
     auto-422 components are **stripped**, so a 422 answer would contradict a shipped pin.
     **Enforcement is c5-5's**; recording the supersession was c5-1's, and no `ErrorReason` token
     was added — the set stays at **ten**, because `payload_too_large` was added early and
     deliberately *"before Epic 5 freezes the union"*. **Home for the artefact edits: Epic 8**,
     alongside the spine amendment above. (Severity: Low — both are documentation drift against
     shipped, tested code.)

## Deferred from: c5-2-same-origin-session-endpoint-minting-single-use-websocket-tickets (2026-08-08)

- **`Origin` on REST: RULED, and c1-5's open question is CLOSED.** c1-5 recorded the question and
  homed it on c5-2 and c5-3 by name (`c1-5:357-358`, `:625-631`). **Ruling (Q1, Brad 2026-08-08):
  `GET /api/session` does NOT validate `Origin`.** The reasoning, so c5-3 inherits a decision rather
  than re-deriving one: there is no `CORSMiddleware` and c1-5 ruled there never will be
  (`TestCorsIsDeliberatelyAbsent`), so a page on another origin can *issue* the mint but cannot
  *read* the response — it cannot steal a ticket, only burn tickets, which `MAX_TICKETS`' hard cap
  and earliest-expiry eviction bound to one recoverable re-mint for the legitimate client. AD-5 and
  review finding S-6 both home `Origin` on the **upgrade**; putting it here too would be one
  decision maintained in two places, and would break any future Vite dev proxy that rewrites `Host`
  but not `Origin` (`:3539` records that path as still unexercised). Asserted structurally by
  `test_routes_session.py::test_the_route_module_contains_no_host_or_origin_check_of_its_own`.
  **Home: c5-3** for the upgrade half, which is now the only half left open. (Severity: none —
  this is a closed ruling, kept for the audit trail.)
  **CLOSED at c5-3 (2026-08-08) — both halves are now ruled and shipped.** The upgrade half landed
  as `security.origin_is_allowed`, a pure predicate beside `host_is_allowed` and derived from the
  same `allowed_authorities` set so the two can never drift; the handshake evaluates it **before**
  the consume, so a refused foreign page cannot burn the ticket it carried (`test_ws.py::
  TestOriginIsCheckedBeforeTheTicket`). A missing `Origin` rejects (Q4, fail-closed). The Vite
  dev-proxy consequence this entry predicted is real and is ledgered separately below, homed on
  c5-6.

- **`errors.supported_methods` under a non-root `Mount`: c5-2 is NOT the story that triggers it,
  confirmed rather than assumed.** The entry above homes that hole on *"the story that adds a
  non-root mount"*. c5-2 adds an `APIRouter` with a `prefix="/api"`, which is not a `Mount` — FastAPI
  flattens it into the route table the walk already reads, and `install_spa`'s mount at `/` is
  unchanged and still the only mount in the app. Measured: `test_routes_active_deck.py::
  TestTheMethodSemantics` passed unedited. **Home: unchanged.** (Severity: none — a confirmation.)

- **Two `Example:` blocks in `security.py` are still executed by nothing, and that is now a stated
  decision rather than an omission.** c5-1 established the house answer for this (fold
  `doctest.testmod(module)` into an ordinary test, because `testpaths` is scoped to `tests/` and
  `--doctest-modules` never reaches `src/`), and c5-2 applied it to `src/companion/app/state.py` —
  whose `ActiveDeckSlot` example had also never run. `security.py:97,116` still have not. **Not
  taken here deliberately:** a story that starts executing another module's untested examples owns
  whatever they turn out to say, and c5-2 has no other reason to touch that module's behaviour.
  **Fix shape:** two lines, in the same shape as `test_routes_session.py::TestTheDocstringExamplesRun`
  — and the honest generalisation is a single test that walks every `src/companion` module rather
  than a per-module opt-in that the next author also has to remember. **Home: unowned**, most
  naturally c5-3, which edits `security.py` for the upgrade gate. (Severity: Low — an example that
  is wrong is a docstring that lies, and nothing would say so.)
  **CLOSED at c5-3 (2026-08-08), and closed in the generalised shape this entry asked for** rather
  than the two-line one. `test_ws.py::TestTheDocstringExamplesRun::
  test_every_example_in_every_companion_module_passes` **discovers** every module under
  `src/companion` from the tree and runs `doctest.testmod` over all of them, so a module added
  tomorrow is covered with no edit and the "next author also has to remember" failure mode is gone.
  `security.py`'s two blocks now execute (and pass), pinned by name in a sibling test so the
  specific gap cannot silently lapse. The c5-1 and c5-2 per-module tests are **not deleted** — a
  passing guard is not removed for being redundant (C4 retro).

- **`test_committed_schema.py` cannot see a source change until `gen:api` has run, and this cost
  two probe attempts before it was understood.** Measured at c5-2's R2 pass: planting an extra
  `payload_too_large` on the session include, and separately renaming the route's path, left every
  pin in that file **green** while reddening `test_openapi_contract.py::
  test_committed_schema_matches_the_live_app`. The reason is the file's whole design — it asserts
  against the committed `ui/src/api/openapi.json`, not against `build_app().openapi()` — so it pins
  *what was shipped*, and `test_openapi_contract.py` is the separate guard that pins *shipped equals
  live*. Both are correct and the pair is complete; what was missing is that nothing said so, so a
  future R2 pass will plant in source, see green, and reasonably conclude the guard is broken.
  **Fix shape:** one sentence in `test_committed_schema.py`'s module docstring naming its sibling
  and the ordering between them. **Home: unowned, informational** — cheap, and the next story to
  add a component is the natural one. (Severity: Low — it costs a confused half-hour, not
  correctness.)
  **OBEYED AND CONFIRMED at c5-5 (2026-08-08) — the first story since this was ledgered with a real
  schema diff, and the warning was worth its words.** c5-5 moved the document by one path and
  seventeen components. Running `npm run gen:api` between the source change and the pin update was
  what made the two `test_committed_schema.py` reds meaningful rather than noise; the four
  route-level schema assertions in `test_routes_agent_events.py` were red for exactly this reason
  until the regeneration ran, and would have read as an authoring bug to anyone who had not read
  this entry.
  **Confirmed a second time by the R2 pass, in the direction the entry describes.** The probe that
  restored `payload_too_large` to the shared health include reddened
  `test_openapi_contract.py::test_committed_schema_matches_the_live_app` — the *shipped-equals-live*
  guard — alongside the live-app assertions, while the pins reading the committed file behaved
  exactly as this entry says they would. The pair is complete and the ordering is real.
  **The fix shape is still not taken** and is still worth a sentence: c5-5 read this entry instead
  of rediscovering it, which is the entry doing its job, but that only works for an author who
  finds the ledger. (Severity: Low, unchanged. **Home: still unowned.**)

## Deferred from: code review of c5-2-same-origin-session-endpoint-minting-single-use-websocket-tickets (2026-08-08)

- **`consume()` has zero production callers, so "single-use" is unproven on any production path.**
  Every consume/expiry/eviction property is unit-only; nothing in the running app calls
  `TicketStore.consume` until c5-3 wires it into the WebSocket upgrade handler. The no-lock
  argument (one synchronous `dict.pop`, no `await` between read and delete) must be re-made
  against the real handshake code — c5-3 can quietly break the atomicity assumption (e.g. an
  `await` slipped between validation steps) with no failing test here. **Home: c5-3** — the story
  that calls consume must show the call sits in synchronous code and add a guard or test for it.
  **CLOSED at c5-3 (2026-08-08), and the showing is structural rather than a promise.** The one
  production caller is `ws._handshake_is_authorised`, a **plain `def`** that holds the *entire*
  handshake decision — read `Origin`, evaluate it, reach the store, pop. A plain `def` cannot
  contain an `await`, so the property is enforced by the language: reintroducing a suspension point
  requires changing that `def` to `async def`, which is one of the three breakers `state.py`
  already names. Four guards pin it (`test_ws.py::TestTheConsumeStaysSynchronous`): `consume` is
  not a coroutine function, the gate is an `ast.FunctionDef` and not an `AsyncFunctionDef`, it
  contains no `Await` node, and — the non-vacuity that makes the other three mean anything — both
  decisions really are inside it. A fifth pins the first breaker: the pop is still one statement.
- **The Q3/AD-5 ruling is narrated in five or more shipped prose locations with no consistency
  guard.** `state.py`'s module docstring, `security.py:16-30` plus `install_security`'s docstring,
  `main.py`'s "CORRECTED AT c5-2" block, and `test_routes_active_deck.py`'s narrowing docstring
  all restate the same ruling. The c5-2 diff is itself the proof of the failure mode: three
  shipped forward-looking paragraphs guessed wrong about this story and had to be corrected, and
  the corrections added more forward-looking prose about c5-3/c5-5/c5-6 in the same breath. Each
  future story inherits an N-way prose-sync obligation nothing tests. **Home: C5 retro** — decide
  a single canonical home for cross-module rulings and let the other sites point at it.
  **RULED at the C5 retro (2026-08-09), RE-HOMED to epic-c5 action item R2 (C6 prep, standalone
  sweep):** the canonical home for a cross-module ruling is THIS LEDGER (the entry that records the
  ruling); every shipped prose site becomes a one-line pointer at it. Standing rule adopted with the
  sweep: no new forward-looking cross-module prose in docstrings — c5-4's "do not widen it" order
  generalised.
- **`scripts/dump_openapi.py`'s docstring is becoming a dated changelog.** c5-2 added two more
  paragraphs of measurement narrative plus an italicised correction of the script's own prior
  (false since c3-8) truncation claim. None of it affects behaviour, nothing tests it, and it has
  already contradicted itself once. The falsification-correction *content* is valuable; a dump
  script's docstring is the wrong ledger. **Home: C5 retro** — pick the right ledger and move the
  narrative there.
  **RULED at the C5 retro (2026-08-09), RE-HOMED to epic-c5 action item R2 (same sweep):** the
  right ledger is this file plus the story records, both of which already carry the narrative —
  so the sweep DELETES the docstring's changelog paragraphs rather than moving them, leaving a
  current-behaviour statement and one pointer.

## Deferred from: c5-3-authenticated-websocket-upgrade-with-host-and-origin-validation (2026-08-08)

- **The Vite dev proxy rewrites `Host` but not `Origin`, so a proxied handshake will be refused —
  and the refusal is now reachable, because c5-3 shipped the `Origin` check.** Under `vite dev` the
  page is served from Vite's port, so the browser's `Origin` names Vite; `changeOrigin: true`
  rewrites the forwarded `Host` to the backend's authority (which passes) and leaves `Origin`
  untouched (which does not). **Nothing is broken today**, measured rather than assumed: `/ws` is
  deliberately absent from `PROXIED_PATTERNS` (`ui/config/devProxy.ts`), so no handshake is proxied
  at all and the dev loop is unaffected. It becomes real the moment a `/ws` entry is added.
  **Fix shape:** three candidates, and picking between them is the deferred work, not the fix —
  (a) have the proxy rewrite `Origin` too, which is the smallest change and the one that keeps the
  backend's check strict; (b) teach the dev build to connect directly to the backend port and skip
  the proxy for the socket; (c) widen `allowed_origins` under an explicit dev flag, which is the
  worst of the three because it puts a bypass in shipped security code. **Home: c5-6**, which adds
  both the WebSocket client and the proxy entry, and is therefore the first story that can observe
  it. Recorded in `ui/README.md`'s proxy section too, next to the `changeOrigin` explanation, so it
  is found by someone reading the proxy rather than only by someone reading this file.
  (Severity: Medium — it would present as "the socket never connects in dev" with a 403 and no
  message, which is a slow thing to diagnose from the browser side.)

- **`test_spa.py` owed an edit that the c5-3 story context predicted it would not, and the
  prediction was wrong for an interesting reason.** The story reasoned that a WebSocket-only router
  owes `test_spa.py` nothing because a WS route has no OpenAPI operation. That is true of
  `test_the_schema_is_unchanged_by_installing_the_mount` (the hand-mirrored router list, which
  compares `openapi()["paths"]` and was genuinely untouched) and **false** of
  `test_the_reserved_prefixes_are_derived_from_the_route_table`, which reads the **route table**
  rather than the schema: `spa._route_paths` descends into `WebSocketRoute` exactly as into `Route`,
  so registering `/ws` reserved the segment `ws` and that test went red naming it. The red was the
  mechanism working as its own failure message describes. The consequence is a *better* behaviour
  than the one Q1 predicted — a plain `GET /ws` now answers the typed 404 instead of serving
  `index.html` — and it is pinned deliberately. **Fix shape:** none needed; recorded because the
  general rule "a WS router owes the schema tests nothing" is true and the adjacent rule "…therefore
  owes `test_spa.py` nothing" is not, and c5-4/c5-5 will be reasoning from the same file.
  **Home: none** — informational. (Severity: none.)

## Dispositions from: dev of c5-6-client-reconnection-with-backoff-and-a-fresh-ticket-per-attempt (2026-08-08)

**The story that was named as the home of a family, and closed it.** C3 retro ruling R3 said
*"c5-6 resolves the family; it should not solve one third of it and leave the rest"*, and the Dev
Notes carried ten trigger-gated anchors in full. Every one is dispositioned below — six CLOSED, two
CLOSED-BY-RULING with the reason written down, one STANDS UNCHANGED, one re-scoped.

All nine of the story's open questions were ruled by Brad **before any code**, as recommended, in
one pass — the c5-5 protocol repeated. The rulings live in the story record; only their
consequences for the ledger are here.

### CLOSED

- **dw:3451-3461 + dw:4930-4940 — first load with no backend holds "No deck on the glass." forever.**
  **CLOSED.** The panel's copy is *actionable and wrong* about a backend that is not running, which
  is why the severity was raised after Block I confirmed it live. `src/state/socket.ts` supplies the
  signal the client did not have: sixty seconds and four failed attempts after a cold open against
  nothing, the connection status reads `'down'` and `surfaceOf`'s new fourth arm puts the true
  `disconnected` panel on the glass. **The first sixty seconds are deliberately unchanged** — a
  backend restart takes a second or two, and a whole-screen panel flashing on every
  `uvicorn --reload` save would be a worse defect than the one being fixed.
  Asserted end to end in `App.test.tsx::the page reconnects on its own`, which pins BOTH halves
  (the old panel at t=0, the true one at t=60 s).

- **dw:3463-3470 — after one `200` the poll stops; a later DB death shows a stale panel until reload.**
  **CLOSED.** `restartPollIfStopped()` in `systemState.ts` re-drives the poll when a
  `deck_changed` / `active_deck_changed` frame arrives AND the panel on the glass is one
  `RETRIES_QUIETLY` says does not retry itself. The gate is the CONTRACT rather than a list of the
  three panel names, so a seventh panel decided later is covered with no edit.

- **dw:3472-3478 + dw:3544-3555 (C3 retro R3) — `database-updating-stalled` is terminal.**
  **CLOSED**, and this is the sibling that was felt live at Block I (wire `200`, poll count moved by
  exactly 0 over 45 s — dw:4968-4972). Two triggers now recover it: a reconnect success restarts the
  poll unconditionally (`restartPoll()` — a socket coming back is the strongest evidence the app
  gets that the process it was talking to is gone, so a stalled clock inherited from it is not
  evidence), and a system-kind frame restarts it via the gate above. `RETRIES_QUIETLY` is
  **untouched**: the stalled state still does not retry itself, which is correct; what changed is
  that something else can now re-drive it.

- **dw:3756-3768 — the no-re-drive-after-boot browser half (`active_deck_changed` arrives and
  nothing listens), plus the 404-clears-then-re-asks residue.**
  **BOTH CLOSED.** The first is AC 11: `socket.ts` dispatches the two system kinds through one total
  switch and `connection.ts` re-drives the boot on either. The second is dispositioned rather than
  repaired, as predicted: the event now delivers the correction, so the one wasted request per cold
  open against a deleted deck is self-correcting the moment the agent sets another deck — which the
  agent's own `PUT` now announces on the wire.
  **FIRING PROOF, 2026-08-09 (c6-3):** the closure was asserted from the code; it is now measured.
  Neutering `onSystemEvent` to a no-op — this entry's regression, verbatim — reddens 7 App-level
  tests (c6-3's 3 new switch tests plus the 4 shipped socket-event tests), collected count validated
  at 1,871. Nothing outside the event path moved.

- **dw:5221-5237 — the Vite dev proxy rewrites `Host` but not `Origin` (Medium).**
  **CLOSED by fix (a) of the three the entry enumerated** (Q7). The `/ws` entry rewrites `Origin` to
  the backend target, exactly as `changeOrigin` does for `Host`. The backend check stays strict,
  `security.py` ships no dev-time branch, and the whole accommodation lives in a file that never
  reaches the bundle. (b) — dialling the backend port directly from the dev client — was declined
  because it makes dev and prod diverge inside `client.ts`, where `agentSocketUrl` derives the whole
  authority from `window.location` precisely so that it cannot; (c) — an `allowed_origins` widening
  flag — was the entry's own *"worst of the three"*. Proven by a **real upgrade through a real Vite
  server** in `devProxyRoundTrip.test.ts`, in both directions, not by a config assertion.
  `ui/README.md:52-61`, which named c5-6 as owner, is rewritten.

- **dw:1588 — the copy-tails fourth tail, declined at c3-9 and re-homed on c5-6 by name.**
  **PAID.** `copy-tails.test.ts`'s last describe was deliberately weak *"until c5-6 arrives to
  honour it"*; it now reads the shipped backoff's constants out of `src/state/socket.ts`, holds the
  two-gate threshold to `poller.ts`'s `STALLED_AFTER_MS`, and asserts the loop READS
  `RETRIES_QUIETLY` rather than paraphrasing it. **The pill itself stays unasserted and is asserted
  to be unasserted** — it is c5-7's, and gating it now would be the prose-against-prose failure that
  file exists to prevent.
  **→ PAID IN FULL at c5-7 (2026-08-08)** — the deliberate non-assertion was CONVERTED into a real
  mirror against the pill's shipped `down` copy and against `RETRIES_QUIETLY.disconnected`, not
  deleted. See *Dispositions from: dev of c5-7-connection-pill* at the foot of this file.

### CLOSED BY RULING, with the reason recorded

- **dw:3526-3534 — the poller backoff-damping question (alternating tokens pin the backoff near
  base).** **CLOSED: NO DAMPING** (Q4). The socket loop has exactly ONE failure kind — `ws.py:29-40`
  refuses every upgrade with the same bodyless `1008`, deliberately indistinguishable — so its
  backoff resets only on a successful connection and the alternating-token scenario cannot arise
  there at all. The poller's own reset-on-flip cost was accepted at c3-9 Q2 and stays accepted,
  because the socket now supplies the recovery signal that made the poller's tail latency matter.
  No code change in `poller.ts`; its header and `cards.ts:432`'s note are rewritten to record the
  ruling rather than the question.

- **dw:3500-3505 — `CLIENT_ONLY_STATES` has no runtime consumer.** **CLOSED: it stays TYPE-LEVEL,
  and the reason is written into `states.ts`** (AC 17). A runtime consumer would have to be a
  membership test — *"is this panel client-only?"* — and nothing in the app asks that: the two
  members are produced by two different mechanisms in two different modules, each of which names
  its own panel directly because each knows which one it is producing. What c5-6 DID add is a third
  type-level reader that is no longer merely a proof: the new `ClientOnlyState` alias types the
  `DISCONNECTED_PANEL` constant in both `deck.ts` and `socket.ts`, so the two places in the app that
  choose a panel from something other than a wire token are now compile-checked against this list.
  Retarget either at a wire-sourced panel and `tsc` names it.

### CLOSED with a narrower shape than the entry proposed

- **dw:3652-3671 (entries 5 & 6, re-homed entirely to c5-6 at c5-4 Q6).**
  - **Entry 5 — three transient failures make a card id terminal for the tab's life.** **CLOSED by
    `resetCardAttempts()`** (Q6), called on reconnect success. Attempt counters only; hydrated
    entries are never touched. **A blanket `resetCardCache()` was declined and the reason is the
    entry's own**: the cache is shared with Epic 6's views, so a reset would discard hydration two
    decks hold in common to fix a per-id budget. Only entries the BOUND made terminal are re-armed —
    `card_not_found` and `invalid_request` stay terminal, because re-arming them would spend a
    request per missing card on every reconnect forever. The half-repair worth naming: clearing the
    attempt map ALONE does nothing visible, because `retryable` is recorded on the entry and
    `hydrateCard`'s gate reads the entry; `cards.test.ts` asserts the REQUEST, not the flag.
  - **Entry 6 — the orphaned-hydration declare.** **STANDS UNCHANGED, and that is its disposition.**
    `resetCardAttempts` throws nothing away and bumps no generation, so it creates no orphans; the
    declare was waiting for a ruling about whether the reset shape would make it worse, and the
    answer is that the reset shape was not taken. Asserted (`creates no orphans — the dw:3666
    declare stands unchanged`).

### Re-scoped

- **dw:5079-5083 — the probe-harness vitest half.** **SCOPED DECLINE** (Q9). This story ran its
  twelve firing proofs the way c4 and c5-5 did — the full `npm test` by hand, collected count
  checked, results pasted into the story record — and the committed vitest harness stays the
  standalone process item it already is (owner "Brad (c5-1)", unstarted). Putting it inside the
  epic's largest frontend story would have made a tool change ride a feature diff.
  **One measurement worth carrying to whoever does build it:** a subprocess `npm test` launched with
  a LOWERCASE drive letter (`c:\…`) resolves no vitest config on Windows and reports 67 failed
  suites / "no tests" — i.e. every probe reads RED for a reason that has nothing to do with the
  probe. The harness must normalise the drive letter and must validate the collected COUNT, not
  just the exit code.

### New, from this story

- **The four agent-view kinds are received and deliberately dropped.** `suggestions`, `swaps`,
  `tier_list` and `groups` reach the browser, are narrowed, and are discarded by the dispatch switch
  with a recorded home: **Epic 6** builds the views. Not an error and not a crash — treating a valid
  frame as malformed would make the agent's pushes look like a wire fault to whoever debugs c6-x.
  **Home: Epic 6** (already scheduled). (Severity: none — designed.)

- **A duplicate `active_deck_changed` costs one full boot each.** The backend fires on every `PUT`
  including a redundant re-set (`ws.py:409-444`), and the client answers each with a
  `stop()`/`start()` of the deck boot — two requests per duplicate. That is AC 12's *"one idempotent
  refetch, nothing else"* and it is cheap, but an agent that re-set the same deck in a tight loop
  would produce a request per set. No coalescing is shipped: a debounce is a second timing mechanism
  to reconcile with the backoff, and there is no measured workload that needs one.
  **Fix shape:** if it is ever needed, coalesce in `connection.ts` (one trailing re-drive per
  animation frame), never in `deck.ts`. **Home: 17-3 or whoever measures a real agent push rate.**
  (Severity: low.)

- **The connection status is written on change only, and `App` subscribes to the system store
  selector-less.** So a reconnect storm re-renders the whole tree twice per storm (down, then live)
  rather than twice per attempt. That is deliberate and measured against `poller.ts`'s identical
  rule; it is recorded because the selector-less subscription is a standing cost the pill (c5-7) and
  Epic 6 will both inherit. **Home: c5-7 if the pill wants finer granularity.** (Severity: none.)
  **→ CLOSED at c5-7 (2026-08-08)** — it did want it: `systemState.ts` exports a one-line
  `useConnection()` selector hook and the pill subscribes to that field alone. `App`'s own
  selector-less subscription is unchanged and still a standing cost for Epic 6. See
  *Dispositions from: dev of c5-7-connection-pill* at the foot of this file.

- **jsdom DOES provide `WebSocket` — the story's own Dev Notes said it does not.**
  Measured 2026-08-08 (`typeof new JSDOM().window.WebSocket === 'function'`). Recorded as a
  **falsified prediction** rather than silently worked around, because it changed the test design:
  without an explicit `vi.stubGlobal('WebSocket', …)` every one of `App.test.tsx`'s ~70 mounts would
  attempt a real TCP connection to `ws://localhost:3000`, making the retry schedule depend on how
  fast the OS refuses a connection. The stub is now installed in `beforeEach` and documented there.
  **Home: none** — informational, and a correction to the Dev Notes rather than to code.

- **`devProxyRoundTrip.test.ts` needed explicit upgraded-socket teardown.** An upgraded socket is
  detached from the server's request lifecycle and stays open by definition, so `server.close()`
  waits for it forever: the first run of the new block reported three tests "failed" with **no
  failed expectation between them** — the `afterEach` hook hit its 10 s timeout. Both ends are now
  destroyed by hand. Recorded because the failure mode is indistinguishable from a real one at a
  glance, and c5-8 adds more real-socket tests to this exact file. **Home: c5-8 inherits the
  pattern.** (Severity: none — fixed here.)
  **→ PAID at c5-8 (2026-08-09).** The pattern was inherited into Python rather than into this
  file: `test_live_backend.py` closes the websocket client by hand before the server is
  stopped, terminates **and waits** every child, and detaches its handles before teardown so a
  raising `wait()` cannot skip the log close. ⚠️ **The premise was wrong**: c5-8 adds no tests
  to `devProxyRoundTrip.test.ts` at all — its one real socket is Python-side. Recorded as a
  falsified prediction rather than quietly fulfilled.

- **Node's global `WebSocket` sends no `Origin` header.** It is not a browsing context. The first
  draft of the round-trip's negative half used it and recorded the forwarded Origin as `<absent>` —
  a negative half that cannot reproduce the header under test is not a negative half. The block now
  drives raw `http.request` upgrades with an explicit `Origin`, which is also what `security.py`'s
  docstring says c5-8's real client will have to do. **Home: c5-8** — it will need the same. (Severity: none.)
  **→ PAID at c5-8 (2026-08-09).** `test_live_backend.py` passes `origin=` to
  `websockets.connect` explicitly, for exactly the reason recorded here — the library sends no
  `Origin` of its own because it is not a browsing context. **Measured, not assumed**: a
  falsification probe removed the argument and the real handshake came back refused 403, which
  is `security.py`'s fail-closed rule observed over a real socket for the first time.

- **The pre-existing `test_list_decks_with_strategy_field` flake fired once**, during this story's
  post-prose Python run (`assert 'Control' is None`), and passed on an immediate clean re-run at the
  expected 2,770 / 1 skipped. Not chased, per the Dev Notes' instruction; recorded as a second
  sighting after c5-5's. **Home: C5 retro.** (Severity: low — two sightings now, not one.)
  **RULED at the C5 retro (2026-08-09), RE-HOMED to epic-c5 action item R4 (C6 prep):** one
  BOUNDED reproduction attempt (repeat-run the file, both alone and inside the full suite); if it
  does not reproduce, annotate the test with the two sighting dates and monitor — a third sighting
  escalates to a real investigation. Coupled with the `-m integration` marker split below, which
  makes the question answerable.

- **An intermittent vitest "unhandled error" that costs ONE test file its collection.** Seen
  **twice** during this story's verification: 66/67 files with 1,807/1,812 tests, and 66/67 with
  1,805/1,812. In both cases no failing assertion was reported — the count simply dropped by one
  file's worth of tests, with vitest's *"This might cause false positive tests"* warning. It then
  **did not recur in 26 consecutive full runs**, including six deliberate attempts to reproduce the
  exact shape both sightings had (a heavy multi-hundred-file write — `pre-commit run --all-files`
  rebuilding `plugin/`, or `gen:api` — in the same shell invocation immediately before the run) and
  three runs with a concurrent `git add -A` in flight. Unreproduced, so unfixed.

  **The leading hypothesis, and the reason this entry is not filed as "probably nothing":
  `devProxyRoundTrip.test.ts`'s declared TOCTOU, whose exposure THIS STORY TRIPLED.**
  `ephemeralPort()` probes a port, closes it, and lets Vite bind it with `strictPort: true`; that
  file's own comment accepts the probe-then-bind gap on the ground that a collision is *"a loud
  EADDRINUSE, not a silent wrong-server test"*. c5-6 added four tests to that file, each starting
  its own Vite server plus a stub backend — so the number of probe-then-bind windows per suite run
  went from 5 to 9, and the number of listening sockets roughly doubled. A `listen` error raised
  outside any test's own await is exactly an "unhandled error", and it would take its file's
  collection with it.

  **Fix shape (for whoever picks this up):** stop probing. Let Vite bind port `0` and read the real
  port back off `vite.httpServer.address()` — which this file ALREADY does for its return value, so
  the probe exists only to work around `server.port: 0` being falsy in Vite's config. Passing a
  freshly-bound listener, or retrying the bind on EADDRINUSE, removes the window entirely. Note the
  file's existing warning before changing anything: distinct ports per test are load-bearing for a
  DIFFERENT reason (undici pools keep-alive sockets by origin, and shared ports caused a ~1-in-3
  ECONNRESET flake), so the fix must keep ports distinct.
  **Home: c5-8** — it adds the one real-socket integration test and will be working in this exact
  file. (Severity: low — intermittent, loud when it fires, and it has never turned a real assertion
  green.)
  **→ PAID at c5-8 (2026-08-09), and one premise of this entry was falsified on the way.**
  The probe is gone: `ephemeralPort()` is deleted, a monotonic counter supplies a distinct
  STARTING port per Vite server, and `strictPort: false` lets Vite bind-and-retry on EADDRINUSE
  — one atomic step with no window for anyone to bind into. Distinctness, which is load-bearing
  for the *unrelated* undici keep-alive ECONNRESET flake, is preserved AND is now asserted:
  every origin passes through `recordOrigin()`, which fails loudly on a repeat. It used to be a
  property of a comment.

  ⚠️ **The suggested fix shape was re-measured rather than inherited.** This entry proposed
  "let Vite bind port 0 and read the real port back". That does not work in the installed Vite:
  `{ port: 0, strictPort: true }` treats the falsy 0 as unset and falls back to the 5173 default
  — measured directly by starting two servers, the second of which died with *"Port 5173 is
  already in use"*. The file's original comment was right and this entry's fix shape was wrong;
  the counter exists because of that measurement.

  ⚠️ **The HOMING premise was also falsified**: this entry (and dw:5451's) said c5-8 "adds more
  real-socket tests to this exact file" / "will be working in this exact file". It does not.
  c5-8's one real socket is Python-side (`tests/integration/companion/test_live_backend.py`);
  the only reason it touched `devProxyRoundTrip.test.ts` at all is that this debt was homed here
  by name and Brad ruled (Q4, 2026-08-09) to pay it rather than re-home it a fourth time.
  Verified after the change: that file green 5/5 consecutive runs, full frontend suite green.

---

## Dispositions from: dev of c5-7-connection-pill (2026-08-08)

**The story that was handed a decision nobody had made, and made it.** Three entries were homed
here by name; all three are closed below. All six of the story's open questions were ruled by Brad
**before any code**, as recommended, in one pass — the c5-5 / c5-6 protocol repeated a third time.

### CLOSED

- **dw:4595-4600 — the connection pill's DOM position is decided by nobody, and three stories each
  assume someone else did it.** **CLOSED by decision** (Q1, Brad 2026-08-08). The three artefacts
  were never actually in conflict, and naming the axis is what dissolved it: UX-DR40 and 17-1 were
  describing **Tab order**, `DESIGN.md:479` was describing the **screen**. The shipped answer
  satisfies both — a new `AppShell` prop rendered as a sibling **between `</main>` and `<footer>`**,
  which makes the pill the last Tab stop before the footer links, while `ConnectionPill.css` pins it
  `position: fixed` to the **bottom-left** corner with a `calc(var(--space-gutter) + var(--space-6))`
  inset that clears the footer strip.

  Two things make this more than a note. First, the guard layer had **already anticipated it**:
  `shell.test.ts`'s full-window-fixed-layer rule is value-aware precisely so a corner pill stays
  silent, and `fixtures/css/shell-violation.css:256` carries that exact shape as a probe — written
  in 2026-07-28's review with the reasoning *"a false positive c5-7 has to fight is the worse
  outcome"*. The prediction held byte for byte. Second, the rejected alternative is recorded because
  it is the one a later reader reaches for: an in-flow last child of the LEFT column renders
  bottom-left with no fixed positioning at all — and puts the pill *before the entire right column*
  in Tab order, contradicting UX-DR40, 17-1, and (on the five surfaces where the left column is a
  state panel) AC 1 as well.

  `epics-companion-app.md`'s UX-DR40 enumeration and `EXPERIENCE.md`'s Tab-order cell were both
  updated from their "(connection pill — c5-7)" markers to the shipped truth in the same commit.

- **dw:5349-5355 — the fourth copy tail's PILL clause, asserted-to-be-unasserted.** **PAID.**
  c3-9 declined it (*"prose checked against prose"*), c5-6 paid the backoff half and left
  `copy-tails.test.ts:284`'s deliberate non-assertion standing. c5-7 **converted** it rather than
  deleting it: the row's *"Retrying-quietly note in the connection pill"* is now mirrored against
  the pill's shipped `down` copy (`Backend gone — retrying quietly`) **and** against
  `RETRIES_QUIETLY.disconnected`, so the note cannot be softened at either end without a red test.
  The half that stands unchanged is the other one — `socket.ts` still contains no `pill` outside its
  comments, because the pill reads the loop's field and the loop knows nothing about a pill.

- **dw:5427-5431 — the selector-less system-store subscription, "Home: c5-7 if the pill wants finer
  granularity."** **CLOSED — it did** (Q5). `systemState.ts` grew a one-line `useConnection()`
  selector hook beside `useSystemState()`, so the pill re-renders when `connection` changes and at
  no other time, instead of adding a second whole-store subscription beside `App`'s.

  **What is closed is the QUESTION, not the cost.** `App`'s own subscription is deliberately
  unchanged and still selector-less: it reads all three fields, so a selector there would be
  ceremony. The entry asked whether the pill wanted finer granularity; the answer is yes, and it
  cost one line and no change to how the store is written. `STORES` in `store-writes.test.ts` is
  untouched — this added a reader, and a reader is not a writer.

### New, from this story

- **The measured Tab-corridor figures in `EXPERIENCE.md:143` and `epics-companion-app.md` are each
  one stop short as of this story, and were NOT re-measured.** c4-11 measured the corridor from the
  header to the first footer link over all 40 real decks — **206 max / 78 median / 102.0 mean**, with
  the skip link removing the first 105 and leaving 101. The pill is an always-present stop *inside*
  that corridor, so every one of those figures gains exactly **+1** on every deck (207 / 79 / 103.0;
  105 removed, 102 left). Both suite pins were recomputed from the DOM rather than relaxed
  (`App.test.tsx`: 208 → 209 focusables and a 206-stop corridor on the Atraxa shape; 6 → 7 and a
  4-stop corridor on the 1-card deck), so the arithmetic is checked — but the 40-deck sweep behind
  the artefact numbers was not re-run, and a derived +1 is not a measurement.

  Note the shape of the cost: the pill is proportionally **worst where the corridor is shortest**
  (a 1-card deck goes from 3 stops to 4), which is the opposite of where the skip link helps.
  **Home: 15-6**, which already carries the revisit-before-public-release flag for this exact
  corridor and is the story that actions or re-accepts it. (Severity: low — the direction and the
  magnitude are both known exactly; only the artefact text is stale.)

- **Two live-region prose claims were falsified by this story and are recorded rather than silently
  edited.** `SkipLink.tsx:80` and `CardGrid/copy.ts:47` each asserted that *"CardDetail's single
  polite region stays the only one in the app"* — true when written, false the moment the pill
  shipped its own. Both rewritten to the claim those modules actually make (they announce nothing),
  with the falsification named. Two more copies of the same sentence lived in `copy-rules.test.ts`'s
  registry reasons and were corrected with them. **No home** — closed here. (Severity: none.)

- **The accessible NAME and the DOM text of the pill differ by whitespace, and the test pins both.**
  `button.textContent` is `Connected — Sultai Midrange` byte for byte; the computed accessible name
  is `Connected—Sultai Midrange`, because the accname algorithm trims each contributing text node
  before joining and the separator's spaces do not survive it. Measured, not predicted. Not repaired,
  because the only repair is to give up the typography split that keeps the deck name mixed-case —
  and no screen reader voices the difference. Recorded so the next author does not read it as a bug.
  **No home.** (Severity: none.)

- **A firing proof found a real hole that 1,866 green tests did not: nothing bound the dot's
  modifier classes to their status TOKENS.** Probe P15 pointed `.connection-pill-dot.is-down` at
  `--caution` instead of `--negative` and the FULL suite stayed green. The reason is structural and
  will recur: `ConnectionPill.test.tsx` runs in jsdom, which evaluates no stylesheet, so every DOM
  assertion about the dot can only reach the CLASS — it proves that `'down'` renders `is-down` and
  stops there. The one component in the app whose entire job is to signal by colour could therefore
  ship the wrong colour on the state that matters most, and no gate would object.

  **Closed in this story** by a source-reading guard in `shell.test.ts` that binds all three
  classes to their tokens *and* asserts the dot's complete fill set is exactly the three semantics
  (a swap satisfies any per-class "is it a status token" check, and a fourth rule pointing at
  `--accent` would satisfy all three per-class assertions and still be wrong).

  **Recorded rather than merely fixed, because the general shape is unclosed**: any
  class-to-token binding in this codebase is invisible to jsdom, and only the ones somebody
  thought to read as source are checked. `Badge`'s tones, `ManaPip`'s colours and the deck row's
  live tint are the same shape. **Home: C5 retro** — worth a decision about whether a derived
  class→token guard is wanted repo-wide, rather than one per component that remembers.
  (Severity: low — one instance found and closed; the class of hole is open.)
  **RULED at the C5 retro (2026-08-09): YES — RE-HOMED to epic-c5 action item R3 (C6 prep or the
  first C6 UI story):** generalise `shell.test.ts`'s dot guard into ONE derived source-reading
  check binding every status-semantic class to its token (`Badge` tones, `ManaPip` colours, the
  deck row's live tint, the pill dot), before Epic 6's agent views add more surfaces of exactly
  this shape. Per-component guards that already exist are kept, not deleted.

## Deferred from: code review of c5-7-connection-pill (2026-08-08)

- **Empty-string deck name (`''`) is not normalized to `null` before reaching the pill's render or
  `pillText`.** `ConnectionPill.tsx:77-78`'s selector (`state.deck.status === 'deck' ?
  state.deck.detail.name : null`) and `copy.ts:102-105`'s `pillText` both treat only `null` as "no
  name" — a blank string would render a dangling em dash with nothing after it. Reachable only if
  `deck.detail.name` is itself blank, which nothing in `src/data/schemas/deck.py`'s `name: str`
  field (no `min_length`) prevents. **No home** — deferred as pre-existing: the header's own
  deck-name display (`.app-shell-deck-name`) has the identical gap, so this is a systemic deck-name
  validation question, not something specific to the pill. (Severity: low.)

- **No max-width/overflow guard on the deck name inside the fixed-position connection pill for
  unusually long names.** `ConnectionPill.css`'s `.connection-pill`/`.connection-pill-text`/
  `.connection-pill-deck` rules have no `max-width`, `overflow`, `white-space` or `text-overflow` —
  an unusually long deck name could grow the fixed pill past the viewport edge. **No home** —
  deferred as pre-existing: `.app-shell-deck-name` (`AppShell.css:88-93`, the header's own
  deck-name display) has the identical gap, so this matches an existing repo-wide pattern rather
  than a defect unique to this story. (Severity: low.)

---

## Dispositions from: dev of c5-8-the-one-real-socket-integration-test (2026-08-09)

**The story eight in-source comments had been pointing at.** All three c5-8-homed entries are
closed above (dw:5451 teardown pattern, dw:5459 explicit `Origin`, dw:5470 the vitest TOCTOU), and
two of them carried premises this story falsified — both recorded in place rather than quietly
fulfilled. All six of the story's open questions were ruled by Brad **before any code**, as
recommended: the fourth story running with a clean pre-code sweep.

### New, from this story

- **CI never runs the one test AD-10 asks for, and that is now stated somewhere it can be acted
  on.** `.github/workflows/ci.yml` runs `-m "not integration"` on ubuntu, so
  `tests/integration/companion/test_live_backend.py` is deselected on every push and will be
  deselected forever unless someone decides otherwise. AD-2 makes Windows the platform of record
  and the story's AC discharges "passes on Windows" with a pasted local run — which is honest, and
  is also exactly the arrangement that lets this test rot silently: nothing outside a developer's
  local run will ever notice it break. **Home: C5 retro**, as a decision about whether a Windows
  integration lane is worth its minutes (the whole file runs in ~4 s). (Severity: medium — not a
  defect today, but the only test covering the process boundary has no automated home.)
  **RULED at the C5 retro (2026-08-09): YES — RE-HOMED to epic-c5 action item R1 (C6 prep):** add
  a Windows lane to `ci.yml` running `uv run pytest tests/integration/companion/` (scoped, so the
  flake and the live Scryfall tests stay out of it). AD-2 makes Windows the platform of record and
  the test IS the platform-of-record evidence; ~4 s of test against the only process-boundary
  coverage is the cheapest insurance on the docket.
  **DELIVERED 2026-08-09 — PR #62, merged to master at `4cf4bd6`.** `ci.yml`'s
  `companion-integration` job (windows-latest, py3.12, path-scoped, `timeout-minutes: 15`) ran
  green on its first CI run: `collected 1 item`, `1 passed in 7.20s`, 33 s for the whole job.
  **Two claims in the ruling above are FALSE and are corrected here rather than left to propagate:**
  (1) "so the flake … stays out of it" — `-m integration` never collected
  `test_list_decks_with_strategy_field` at all; that test carries no marker and has been running in
  the `quality` jobs the whole time (see the scope-trap entry below, now retracted). The real reason
  path-scoping is right is that the marker selects tests instantiating the live fastembed model.
  (2) "AD-2 makes Windows the platform of record" — AD-2 is *"the MCP server is the only writer"*;
  no AD names a platform of record. Both errors reached a shipped workflow comment before review
  caught them.
  **NOT closed by this delivery, and deliberately not presented as if it were:** the lane's firing
  proof (a planted break red on Windows, green on ubuntu) was **not run** — R1 merged proving the
  lane *runs*, not that it *discriminates* — and `companion-integration` is **not yet a required
  check**, so a red lane does not block a merge. Both carry forward; see the R1 rows in
  `sprint-status.yaml`.

- **The `-m integration` scope trap, recorded so the next person does not rediscover it.** A bare
  `uv run pytest -m integration` collects `test_list_decks_with_strategy_field` (the twice-sighted
  flake already homed on the C5 retro) and the live Scryfall contract tests alongside this one, so
  a red run says nothing about the companion. Every local run in this story was scoped
  `tests/integration/companion/`. Worth a marker or a scoped alias eventually. **Home: C5 retro.**
  (Severity: low.)
  **PARTLY RETRACTED — MEASURED FALSE 2026-08-09 during R1's code review.** `-m integration` does
  **not** collect `test_list_decks_with_strategy_field`: `tests/integration/data/test_deck_repository.py`
  carries no marker anywhere (`grep -c integration` returns 0), so the flake is in the
  `not integration` set and has been running in **both ubuntu `quality` jobs on every push** the
  whole time. Living in `tests/integration/` is not a marker. The scope trap is REAL but for a
  different and stronger reason: `-m integration` selects the live-network Scryfall tests **and**
  several tests that instantiate the real fastembed model (`tests/integration/search/`,
  `tests/integration/mcp_server/test_semantic_search_tool.py`). **This error propagated unchecked
  into the C5 retro, into epic-c5 action item R4, and into a shipped `ci.yml` comment before an
  adversarial review measured it — R4's premise ("today it sweeps in the flake") must be re-derived
  before R4 is actioned.**
  **RULED at the C5 retro (2026-08-09), RE-HOMED to epic-c5 action item R4 (C6 prep, with the
  flake item):** the companion real-socket test gets its own marker so `-m integration` splits
  into things that mean something; the CI lane from R1 selects by path, so the marker serves
  local runs.

- **Seven falsification probes were run against real backends, and all seven went RED** — the
  story's own Dev Notes demanded at least one (*"a real-socket test that cannot fail is worse than
  none"*). Two are worth keeping in the record because they proved something the code alone does
  not state:

  **F5 — the restart wait.** Removing `replacing=record_one.instance_id` from the second boot's
  wait made the test return the *corpse's* record — same `instance_id` **and the same port** — and
  the run went red on the next assertion. That is the proof that a hard kill genuinely leaves
  `companion.json` behind, that the second backend really does walk c1-8's reclaim path, and that
  waiting on file presence alone would have made the whole restart case vacuous.

  **F2 — the explicit `Origin`.** Dropping `origin=` from the first upgrade got a real 403 from a
  real handshake. `security.py`'s fail-closed Origin rule had been asserted in-process since c5-3;
  this is the first time it has been observed over a socket. (Severity: none — all seven RED.)

## Dispositions from: the C5 retrospective (2026-08-09)

All seven entries homed on this retro were ruled; each ruling is recorded inline at its entry
(grep `RULED at the C5 retro`). Summary, with the sprint-status action item that owns each:

1. **Windows integration CI lane** (`dw:5668` region) — **YES**, scoped
   `tests/integration/companion/` lane in `ci.yml` → **R1**.
2. **AD-1 limit-literal family shape** (`dw:5104` region) — **presence-keyed stands**, per-file
   exemption is the standing remedy, third collision reopens → **R10, CLOSED by ruling**.
3. **Q3/AD-5 N-way prose-sync** (`dw:5244` region) — canonical home is THIS LEDGER; prose sites
   become one-line pointers; no new forward-looking cross-module prose in docstrings → **R2**.
4. **`dump_openapi.py` docstring-as-changelog** (`dw:5252` region) — delete the changelog
   paragraphs (content already lives here and in story records) → **R2** (same sweep).
5. **`test_list_decks_with_strategy_field` flake, two sightings** (`dw:5476` region) — one bounded
   reproduction attempt; annotate-and-monitor if it holds green; third sighting escalates → **R4**.
6. **`-m integration` scope trap** (`dw:5678` region) — companion marker/scoped alias → **R4**.
7. **Repo-wide class→token guard** (`dw:5617` region) — **YES**, one derived source-reading guard
   before Epic 6's first view story → **R3**.

Also executed or re-homed at this retro, beyond the seven:

- **The vitest probe-harness half** (`dw:5115` region) — re-homed to **R5** (C6 prep); the C4
  sprint-status item closes as re-keyed, Python half shipped at c5-1.
- **Story 6.4's stale 422** — `epics-companion-app.md`'s 6.4 cap-breach AC amended in-retro to
  413 `payload_too_large`, matching the shipped, tested contract (c1-4 ruling; 5.5 and 6.1 were
  amended at c5-5, 6.4 had been missed). The AD-6/AD-7 spine amendments stay homed on Epic 8.
- **UX-DR46 double-assignment** (Epics 4 AND 5 in the coverage map) — needs an owner decision,
  not a mechanical edit → **R9**.
- **C4 items 5 and 7** (DESIGN.md citation guard; plugin-mirror check from `ui/`) — re-homed to
  **R6** and **R7** respectively; both C4 rows close as re-keyed. R6 carries a termination clause:
  not done by the C6 retro → formally decline and demote the guard to a declared
  string-proximity check.
- **Standing-agreement amendment** — "review-added mechanisms re-enter review" widens to include
  review-added TEST ASSERTIONS (c5-8's Greptile P2 was in an assertion its own review added; ruled
  NOT a retroactive violation, the rule as written scoped to mechanisms) → **R8**.
- **Named, not actioned:** the ~26-entry `unowned` cluster of `src/logic`/`src/data` questions
  from the c3 era (`:2400`–`:3410` band) that no companion story can legitimately own. Candidate
  for a between-epic ledger closing pass; deliberately NOT given a C6-prep home to keep the prep
  list honest. Also standing: `dw:5197`'s twice-confirmed one-sentence fix
  (`test_committed_schema.py` module docstring) remains unowned and cheap — fair game for R2's
  sweep to absorb.

## Deferred from: code review of c6-6-a-push-opens-its-view-and-a-repeat-push-replaces-it-in-place (2026-08-11)

- **`id`/`ts` on the `suggestions` envelope are trusted without validation.**
  `suggestionsViewOf` (`ui/src/state/agentView.ts:229-230`) copies `event.id`/`event.ts` straight
  through with no presence check, since `agentEventOf` (`client.ts:701-716`) validates only
  `kind`. Two distinct malformed pushes both missing `id` would make
  `AgentView.tsx:312`'s `showingPushRef.current === pushId` comparison treat them as the same
  push, skipping the replace effect's re-focus/live-region/crossfade — the store still
  overwrites `content` unconditionally, so visible text updates via ordinary reconciliation with
  no accessible announcement for that specific malformed case. Consequence of the kind-only
  `agentEventOf` narrower design, which c6-6's Q6 ruling scoped to defending
  `payload`/`title`/`items` only; `id`/`ts` validation was out of that story's ruled scope, and
  the same trust already applies uniformly to the shipped `deck_changed`/`active_deck_changed`
  kinds. Requires a backend contract violation to trigger — not reachable from the shipped
  companion server today.
- **`AgentView.test.tsx`'s ARM 3 fixtures hand-roll `StatePanel` markup instead of importing it.**
  The new focus-restore tests (`ui/src/containers/AgentView/AgentView.test.tsx:81-82`) construct
  a `<section className="state-panel">`/`<h2 className="state-panel-headline">` fragment by hand
  rather than rendering the real `StatePanel` component. If `StatePanel.tsx`'s role, label, or
  headline class ever changes, these tests would keep passing against a fixture that no longer
  matches production. Test-quality only, no functional impact.

## Deferred from: code review of c6-9-degradation-with-the-app-closed-and-the-250-ms-push-budget (2026-08-12)

- **The pre-existing `outside_app` role only flags module-level companion-app imports.**
  `find_import_violations`'s `outside_app` role (`tests/unit/companion/test_import_boundary.py:491`,
  `elif imported.module_level:`) only fires on module-level `src.companion.app` imports — a
  function-local `import src.companion.app` anywhere outside `src/mcp_server` and the app package
  itself would pass silently. c6-9's own new SC-3 sweep makes exactly this "a deferred import is
  still a dependency" argument for firing on function-local imports too, but the untouched
  app-side guard keeps the identical blind spot. Pre-existing, unmodified by c6-9.
- **`_COMPANION_REFERENCE_ALLOWED` exempts whole files, not specific import sites.**
  (`tests/unit/companion/test_import_boundary.py:162-172`) The three-site allow-list is keyed by
  filename, so nothing constrains which `src.companion` symbols `server.py`/`companion.py` may
  import later — a future unrelated companion import landing in an already-exempted file would
  sail through undetected. Matches the granularity of the pre-existing `_APP_IMPORT_EXEMPT`
  idiom it sits beside; tightening to import-site-level tracking would be a larger redesign.
- **`_seeded_card_ids` reads `decks[0]` from an ordering that is not strictly guaranteed.**
  (`scripts/cdp_harness.py:498-515`) `GET /api/decks`'s own docstring says its ordering is
  "newest first… not a strict guarantee" under ties. A repeated `push` harness run against the
  same data dir could silently draw ids from a different deck than a prior run, with nothing in
  the output recording which deck was actually used. Harness usability only — does not affect
  this story's recorded 15/21/36 ms figures (a single deck, not re-created between runs).
- **`--card-ids` silently defeats the warm arm's cache-priming premise.**
  (`scripts/cdp_harness.py:946`) Passing fabricated or non-existent ids together with
  `--arm warm` bypasses `_seeded_card_ids`'s real-Scryfall-id guarantee with no validation or
  warning, turning a "warm" run into a placeholder-only run indistinguishable from "blocked".
  Not exercised by this story's own measurement (real deck ids throughout) — a future-run
  footgun only.
- **Image-warmth counters are a single point sample, unlike the polled `layout_ms`.**
  (`scripts/cdp_harness.py:660-672`) `images_requested`/`images_from_network`/`images_painted`
  are read once after a fixed `--image-settle` sleep (default 2.5 s), while `layout_ms` polls
  via `_await_surfaces` until ready or timeout. A slow machine or network could still have
  images in flight at sample time, silently under-counting the warmth metrics. Does not affect
  the reported budget verdict (`layout_ms`) — only the supplementary network/painted counts.

## Deferred from: code review of spec-c6-r2-vitest-probe-harness (2026-08-13)

> Three-layer adversarial review (Blind Hunter, Edge Case Hunter, Verification Gap) of the
> `chore/c7-prep-r2-vitest-probe-harness` diff. The entry below is real but is blocked by the
> spec's own "no git operations" boundary, so it needs a design ruling rather than a patch.

- source_spec: `_bmad-output/implementation-artifacts/spec-c6-r2-vitest-probe-harness.md`
  summary: Nothing binds an `--expect-total` to the tree that produced it, so a baseline from a
    stale checkout, another branch, or last week's control run scores a planted run as valid
    whenever both trees happen to collect the same count.
  evidence: '`--control` deliberately commits no count constant (spec Never clause: "No committed
    expected-count constant that stories must bump"), and the same clause forbids git operations,
    so the harness cannot stamp the count with a HEAD or a working-tree hash. The binding is
    therefore workflow proximity only — run the control, plant, score — which is exactly the
    "the tree under test is not the tree the baseline describes" failure the collected-count check
    exists to catch. The spec Design Notes claim "the baseline can never drift from the tree it
    describes" was softened in review to match. Closing this needs a ruling on whether the harness
    may shell out to `git rev-parse HEAD`.'

## Deferred from: code review of c7-1-one-shared-notifier-with-a-bounded-await-and-no-detached-tasks (2026-08-13)

> Three-layer adversarial review (Blind Hunter, Edge Case Hunter, Verification Gap) of the
> `feat/companion-c7-1-shared-notifier` diff. Both entries below are pre-existing, not caused by
> this story's own code — surfaced incidentally by the review.

- source_spec: `_bmad-output/implementation-artifacts/spec-c7-1-shared-notifier.md`
  summary: Two `tests/integration/data/test_deck_repository.py` tests
    (`test_update_deck_strategy`, `test_list_decks_with_strategy_field`) fail inside the full suite
    even on a clean tree, and were never formally tracked anywhere outside the story's own Task 0
    firing-proof prose.
  evidence: The story's Firing proof section (spec `## Spec Change Log` -> `### Firing proof
    (Task 0)`) shows both tests RED in the pre-plant baseline run and again, identically, after
    revert (`--expect-green`) — proving they are unrelated to `src/companion/client.py` (that file
    touches no data-layer code) and reproduce independent of any planted violation. Both pass in
    isolation per the same section. Flagged there as "for Brad, out of this story's scope" but
    never entered here, so nothing tracks it once the story record stops being read.
- source_spec: `_bmad-output/implementation-artifacts/spec-c7-1-shared-notifier.md`
  summary: The detached-task ban (`test_ws.py::test_the_push_path_creates_no_task`, mirrored
    locally in this story as `test_no_detached_task_identifier_appears_in_client_py`) flags any AST
    `Name`/`Attribute` node matching `create_task`/`ensure_future`/`TaskGroup`/`gather` anywhere in
    `src/companion/*.py`, not only `asyncio.<name>(...)` call sites.
  evidence: A future unrelated identifier in that package — a local variable, parameter, or a
    same-named method on an unrelated object (e.g. a dict/itertools-style `.gather()` helper) —
    would fail this guard with no detached task actually present. The pattern predates this story
    (the package-wide sweep in `test_ws.py` already existed; c7-1 only added a local mirror of it
    in `test_client.py` for `client.py` specifically), so narrowing it is a design change to an
    inherited guard, not something this story's own diff should do unilaterally.

## Deferred from: code review of spec-c7-6-deletion-and-views-during-refetch.md (2026-08-15)

- source_spec: `_bmad-output/implementation-artifacts/spec-c7-6-deletion-and-views-during-refetch.md`
  summary: The panel → deck mirror transition can still drop focus to `<body>` — c7-6's rescue covers only deck → panel.
  evidence: After the c7-6 rescue (or AgentView ARM 3's close-restore) parks focus on `.state-panel-headline`, a subsequent panel → deck transition — the agent creating or activating a deck, or reconnect restoring a loaded deck displaced by the `'down'` panel (`deck.ts:731`) — unmounts the StatePanel and the focused headline dies with it, dropping focus to `<body>` with no rescue firing (`App.tsx:895` early-returns when the arriving surface is `deck`). Pre-existing failure class (ARM 3 could park focus there before c7-6) but c7-6 widens its reachability; no test in the repo covers focus across a panel → deck transition. Same failure class as the half SkipLink.tsx ledgered for c7-6, at the opposite edge. Found by edge-case-hunter + verification-gap, independently.

## Deferred from: story 15-2 (image cache stewardship, 2026-08-18)

- source_spec: `_bmad-output/implementation-artifacts/spec-15-2-image-cache-stewardship-documented-location-inspection-and-removal.md`
  summary: The documented inspect/clear commands are verified only as far as their Python payload —
    the surrounding shell syntax is unverified, and the PowerShell block has never been executed
    anywhere in CI.
  evidence: `tests/unit/companion/test_image_cache_docs.py` extracts every `python -c "..."` payload
    from the README section and executes it in-process, proving it prints exactly
    `images.cache_root()` under a `PLANESWALKER_DATA_DIR` override. It never runs `du`, `find`,
    `rm -rf`, `Get-ChildItem`, `Measure-Object` or `Remove-Item`, and the runner is Linux, so the
    PowerShell block's `$Cache = ...` capture and `Remove-Item -Recurse -Force` are reviewer
    judgement rather than tested fact. The blast radius if the shell half is wrong is bounded by
    the Python half being right — the path the command names is proven correct, so a syntax error
    fails loudly rather than deleting the wrong directory — but "the documented command works on
    Windows" is not something this repository can currently assert. The honest fix is a Windows CI
    leg (nothing in this project has one) or a doctest-style shell harness; neither is worth
    building for two fenced blocks. **Home: unowned.** Forcing function: a Windows user reporting
    that a documented command errored, or this project acquiring a Windows CI runner for any other
    reason.
- source_spec: `_bmad-output/implementation-artifacts/spec-15-2-image-cache-stewardship-documented-location-inspection-and-removal.md`
  summary: The README's footprint figures (~90 KB per tile, 8.5 MB per deck, ~95 MB per library)
    are pinned by nothing and age with the corpus.
    **PARTIALLY CLOSED by story 15-3, 2026-08-18 — the planning-artefact half only.** This entry's
    second clause was that *"the epic (`epics-companion-app.md:294,888,1846,3329`) still carries
    the superseded ~12 MB with no annotation"*. All four now read the measured 8.5 MB, with the
    ~12 MB labelled as the disproved arithmetic estimate and the C3 retrospective cited once in
    full under AD-11 and by pointer at the other three; the two acceptance criteria among them
    (Story 10.6 and Story 15.2's own) are still well-formed Given/When/Then. **Two further sites
    the 15-2 spec did not know about were found and corrected with them**: `ARCHITECTURE-SPINE.md`
    (the source all four epic copies were taken from, flagged four times from `c4-12` without
    action) and `walkthrough.html` (the HTML projection of that same spine line — a rendered
    projection disagreeing with its source is how the figure spread in the first place).
    `README.md` deliberately keeps ~12 MB as a labelled superseded estimate and IS gated:
    `test_image_cache_docs.py:412` asserts the literal `12 MB` and the word `estimate` are both
    present. **`ui/README.md` is NOT gated by anything** — that guard reads `REPO_ROOT/"README.md"`
    and nothing else — and story 15-3 corrected two misattributions in it by hand (it credited the
    superseded figure to the epic in the present tense, which the correction made false).
    **What stays open is this entry's first clause, unchanged**: the measured figures are pinned by
    nothing, in `README.md`, in `ui/README.md` or in any planning artefact.
  evidence: Every other load-bearing claim in the new README section is keyed on a shipped symbol —
    `images.CACHE_DIRECTORY_NAME`, `images._cache_path`, `images.cache_root`,
    `singleton.LOCK_FILENAME`, `discovery.COMPANION_FILENAME`,
    `images.DISK_CACHE_WRITE_FAILURE_LIMIT` — so a rename that skips the prose turns the guard red.
    The measurements have no constant to key on: they are dated observations from the C3
    retrospective (2026-08-02) against one deck, one rendition and one CDN encoder.
    `test_image_cache_docs.py` asserts only that the numbers are *present and labelled measured*,
    which is exactly as much as prose can be pinned to a measurement, and the module's docstring
    declares the gap rather than implying coverage. They will drift silently as Scryfall re-encodes
    art or the library grows. **Home: unowned.** Forcing function: a re-measurement (the natural
    trigger is any future story that touches the image route's storage, or a user reporting a
    footprint far from the documented one).

## Deferred from: story 15-3 (reconcile the PRD with what was built, 2026-08-18)

- source_spec: `_bmad-output/implementation-artifacts/spec-15-3-reconcile-the-prd-with-what-was-built.md`
  summary: The new drift guard gates the PRD and only the PRD. Every other artefact this story
    amended — the addendum, the epic, the architecture spine, its HTML projection — is still gated
    by nothing.
  evidence: `tests/unit/companion/test_prd_reconciliation.py` keys the PRD's closed sets on
    `get_args(contracts.ErrorReason)`, `get_args(contracts.EventKind)` and
    `SetActiveDeckResult.status`, and its route assertion on `build_app().openapi()`, so a rename
    or an added member reds. `grep -rln "planning-artifacts" tests/ scripts/` returns that module
    and `test_openapi_contract.py` and nothing else; the frontend suite reads `EXPERIENCE.md`,
    `DESIGN.md` and (for one row) `epics-companion-app.md`, but nothing reads the addendum, the
    spine or `walkthrough.html`. This is the mechanism that let the ~12 MB figure spread from
    `ARCHITECTURE-SPINE.md:269` into four epic sites and one HTML projection over sixteen days, and
    it is unchanged for those files — only the PRD is now watched. Extending the guard is cheap for
    the spine (it names shipped constants) and expensive for the epic (5,000 lines of prose with no
    stable anchors). **Home: unowned.** Forcing function: the next figure or token that drifts in a
    document this guard cannot see.
- source_spec: `_bmad-output/implementation-artifacts/spec-15-3-reconcile-the-prd-with-what-was-built.md`
  summary: The retired-claim scan is literal, so a paraphrase of a retired claim would pass.
  evidence: `test_the_retired_claims_are_gone` bans the strings `mode=ro` and
    `~/.artificial-planeswalker` anywhere in the PRD, which is why the amendments describe both in
    words ("the read-only **connection-string** recipe this row used to specify", "the
    home-directory dotfolder this row used to name") rather than reproducing the spelling. A future
    edit that reintroduced the *claim* under a different spelling — `file:…?immutable=1`, a per-OS
    dotfolder path written out in full — would not be caught. FR-04's driver is the one claim
    checked structurally instead of literally, because `layout` legitimately appears in that row.
    The module's docstring declares this. **Home: unowned.** Forcing function: a reviewer noticing a
    paraphrase, which is the same mechanism that found these three.
- source_spec: `_bmad-output/implementation-artifacts/spec-15-3-reconcile-the-prd-with-what-was-built.md`
  summary: `docs/companion-app-feature-brief.md:104` still names the `mode=ro` recipe, deliberately
    and by ruling.
  evidence: Declared residue in this story's spec rather than an oversight: the feature brief is a
    pre-PRD intake draft that the PRD supersedes, and correcting an input artefact rewrites history
    instead of reconciling requirements. A reader who reaches it out of order will meet the
    retired claim with no pointer to NFR-02's amendment. The cheap repair, if it is ever wanted, is
    a one-line superseded-by banner at the top of the brief rather than an edit to the line.
    **Home: unowned.** Forcing function: someone reading the brief as though it were current.
- source_spec: `_bmad-output/implementation-artifacts/spec-15-3-reconcile-the-prd-with-what-was-built.md`
  summary: Three shipped source comments announce that this PRD amendment is owed and were not
    discharged, because they live under `src/` and `ui/src/` — which this story's own contract
    forbids it to touch.
  evidence: '`src/companion/app/deps.py:36` ends *"The PRD amendment is c8-3''s"*; NFR-02 is now
    amended, so the sentence is spent and should read as discharged rather than as an open promise.
    `src/companion/contracts.py:365` says *"Story 8.3''s amendment list currently omits
    ``GET /api/session``"* — that is **discharged in fact**: `/api/session` is named in NFR-01 and
    is now covered by the route-parity assertion in
    `tests/unit/companion/test_prd_reconciliation.py`, which compares the PRD''s documented paths
    against the whole shipped route table, WebSocket routes included.
    `ui/src/containers/AgentViewsNav/copy.ts:63` says the artefacts *"still describe this as
    tooltip, singular"*; UX-DR28, the c6-8 acceptance criterion and `EXPERIENCE.md:131` were all
    amended on 2026-08-18, so that sentence is now false. None was edited: this story ships no diff
    under `src/`, `ui/src/` or `plugin/`, and `ui/src` in particular risks the committed SPA bundle.
    **Home: unowned**, and cheap — three comment edits in any story that already touches those
    files. Forcing function: a reader acting on a promise that has already been kept.'
- source_spec: `_bmad-output/implementation-artifacts/spec-15-3-reconcile-the-prd-with-what-was-built.md`
  summary: Three `ui/src` comments still quote DESIGN.md as saying `{spacing.6}` for the
    agent-view overlay inset, which it no longer does.
  evidence: '`ui/src/components/AppShell/AppShell.css:270` (*"the 32px of UX-DR8''s inset by
    {spacing.6}"*), `ui/src/containers/AgentView/AgentView.tsx:41` and
    `ui/src/containers/AgentView/AgentView.css:17` (*"DESIGN.md''s own component row reads the same
    way: scrim with backdrop, inset {spacing.6}"*) all quote the pre-15-3 wording. The two
    equivalents under `ui/tests` were updated in this story''s commit; these three were not, for the
    same `ui/src` prohibition as the entry above. Nothing renders differently — both tokens are 32px
    and the CSS already uses `var(--space-gutter)` — so this is a citation that has gone stale, not
    a defect. **Home: unowned.** Forcing function: any story that edits the agent-view shell.'
- source_spec: `_bmad-output/implementation-artifacts/spec-15-3-reconcile-the-prd-with-what-was-built.md`
  summary: '"Story 8.3" is an ID COLLISION: code comments pointing there now resolve to a live,
    unrelated story.'
  evidence: 'This story was written as `c8-3` / "Story 8.3" and was renumbered to 15-3 (see
    `sprint-status.yaml`). `epics-companion-app.md:1082` is a *different*, live
    **Story 8.3: Port selection with ephemeral fallback and a printed launch URL**, so every comment
    that says "Story 8.3''s PRD reconciliation" — `src/companion/contracts.py:365`,
    `ui/src/containers/AgentViewsNav/copy.ts:63`, and previously two `ui/tests` comments and two
    `deferred-work.md` entries — sends a reader to the wrong story. The `deferred-work.md` and
    `ui/tests` occurrences were annotated with the renumbering in this story''s commit; the `src/`
    and `ui/src/` ones could not be. This is worse than a stale pointer: it resolves, plausibly, to
    the wrong place. **Home: unowned**, and it rides along with the entry above. Forcing function: a
    reader following one of those pointers.


    **CLOSED 2026-08-18, after story 15-3 merged (PR #87).** All four live pointers were corrected
    in a follow-up commit on `feat/companion-epic-15`: `src/companion/contracts.py` (the
    `/api/session` note, which was also FALSE by then — 15.3 recorded that path against NFR-01 and
    the route-parity guard now asserts it) and its AD-6 note ("owed at Epic 8" — the same
    mis-mapping, and the spine amendment had in fact been made), `src/companion/app/deps.py` (the
    `mode=ro` amendment, now discharged), and `ui/src/containers/AgentViewsNav/copy.ts` (UX-DR28,
    now amended). Each rewrite names the renumbering explicitly — `c8` became **Epic 15**, not
    Epic 8 — so a reader of the old prose can decode it rather than following it. The `ui/src`
    prohibition that blocked this in-story did not apply once 15-3 was merged; the SPA bundle was
    rebuilt and is byte-identical (the comment is stripped), and the plugin mirror was regenerated.
    **Deliberately NOT rewritten:** the historical records — the c2-6, c6-8 and c1-3 story specs,
    the C6 retro, and `sprint-status.yaml`'s dated `Previously —` lines. The 2026-08-16 renumbering
    note rules that historical prose keeps its original ids, and editing a dated record to say
    something it did not say is the drift this ledger exists to prevent.'

## Deferred from: code review of 15-4 (2026-08-19)

- source_spec: `_bmad-output/implementation-artifacts/spec-15-4-release-documentation-for-the-companion-app.md`
  summary: >-
    The single documented launch command does not work for the plugin install route, which the
    README advertises as the one needing no clone.
  evidence: |-
    Blind Hunter, 2026-08-19, verified against the tree. `README.md`'s Quick start sells the Claude
    Code plugin path as "no clone required" (`/plugin marketplace add` + `/plugin install`), and
    `plugin/.mcp.json` runs the server as `uv run --directory ${CLAUDE_PLUGIN_ROOT}/server python -m
    src.mcp_server`. `plugin/server/pyproject.toml:50` does ship the `artificial-planeswalker`
    console script, but `uv run` resolves its project from the CWD — so a plugin user, who has no
    checkout and no uv project in their shell, cannot run the documented
    `uv run artificial-planeswalker companion`. They would need
    `uv run --directory <CLAUDE_PLUGIN_ROOT>/server artificial-planeswalker companion`, which no
    document states.
    NOT 15-4's to fix, and deliberately not treated as an intent gap: Story 15.5's own acceptance
    criterion reads "**When** the two-command install is performed **and the companion is
    launched** **Then** the app serves and renders" — the plugin launch path belongs to 15.5 by
    name. 15-4's frozen intent additionally constrains it to ONE documented command spelled
    identically everywhere (epic AC, AD-14, SC-4), so documenting a second invocation here would
    have contradicted the approved contract rather than satisfied it.
    **Home: 15-5.** If 15-5 does not close it, the release ships a launch instruction that fails
    for the install route the README recommends first. (Severity: Medium — reachable by any plugin
    user on day one; bounded, since the workaround exists and only the documentation is missing.)
  resolution: '**CLOSED by 15-5 (2026-08-20, PR #89).** The anchored form the ledger predicted —
    `uv run --directory "$PLUGIN_ROOT/server" artificial-planeswalker companion` — is documented
    for BOTH plugin clients in `README.md` and in `docs/plugin-structure.md`, each route showing
    how to find its own version-keyed root first (Claude Code under `~/.claude/plugins/cache`,
    Codex under `~/.codex/plugins/cache`, POSIX and PowerShell). Not transcribed:
    `test_build_plugin.py` derives the script and subcommand from `pyproject`''s
    `[project.scripts]` and the dispatcher''s usage text, and asserts every anchor ends at
    `/server` — the directory `${CLAUDE_PLUGIN_ROOT}/server` and Codex''s `cwd: "./server"` both
    resolve to. What the ledger did NOT predict, and what the Greptile round found: documenting
    the command is not enough if the reader cannot obtain the root. The Codex block shipped
    `$PLUGIN_ROOT` with no way to get one, and the guard first written for it searched the whole
    document — where the Claude Code block''s assignment vouched for the Codex block below it —
    so it is scoped to each route''s own section. The plain `uv run artificial-planeswalker
    companion` stays correct for the clone route and is unchanged.'

- source_spec: `_bmad-output/implementation-artifacts/spec-15-4-release-documentation-for-the-companion-app.md`
  summary: >-
    `CHANGELOG.md` is read by no test, so AC 2's "spelled identically at every occurrence" is
    verified for the README occurrences only.
  evidence: |-
    Verification Gap reviewer, 2026-08-19. `test_companion_docs.py`'s launch-command assertion
    searches only the extracted README section; `CHANGELOG.md` carries a second occurrence of
    `uv run artificial-planeswalker companion` that nothing reads. A grep of `tests/`, `ui/tests/`,
    `scripts/` and `.github/` for `CHANGELOG` returns only a comment mention in
    `tests/unit/viewer/test_viewer_freeze.py` and this module's own docstring.
    The new guard's module docstring declares the CHANGELOG deliberately unguarded, so this is a
    standing ruling rather than an oversight — recorded because the AC's wording claims more
    coverage than exists. Reopening it is a design decision about whether release notes should be
    machine-gated at all, which is retrospective work, not story work. (Severity: Low.)

- source_spec: `_bmad-output/implementation-artifacts/spec-15-4-release-documentation-for-the-companion-app.md`
  summary: >-
    CI pins `node-version: 20` while the measured floor is `>=20.19.0`, so the lane's own name
    understates what it requires.
  evidence: |-
    Surfaced again by the 15-4 review's Node-floor sweep, 2026-08-19. `ui/package.json:7` declares
    `>=20.19.0`; `.github/workflows/ci.yml` requests `node-version: 20`, which resolves to the
    latest 20.x and therefore satisfies it in practice — the pin is correct today and correct by
    luck rather than by statement. Already ledgered at `deferred-work.md:1413`; re-confirmed here
    rather than duplicated, since 15-4 corrected the two live stack tables
    (`ARCHITECTURE-SPINE.md:396`, `epics-companion-app.md:333`) and this is the one remaining site
    that states a floor of "20". `epics-companion-app.md:1330` is Story c2-1's own shipped AC and
    was left alone by ruling. (Severity: Low.)
