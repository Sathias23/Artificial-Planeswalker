---
title: 'c7-5: The change is announced once, and motion is never the only signal'
type: 'feature'
created: '2026-08-15'
status: 'done'
review_loop_iteration: 0
followup_review_recommended: true
baseline_revision: '9f10b2491bdad11e0b586d1fe0732f4b4e149cef'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-c7-context.md'
warnings: ['oversized']
deferred:
  - summary: 'Format-check pass→violation flip after first paint still announces nothing (deferred-work.md:4782-4789 homes it on c7-5)'
    evidence: 'UX-DR45 licenses exactly one refetch announcement string ("Deck updated — N cards"); announcing a check flip would be a SECOND per-refetch announcement arriving later (the check is a separate async request keyed on detail identity, App.tsx:342-346), in direct tension with the announce-once AC, and no artefact specifies its copy or region. Needs a human UX ruling before any story can build it.'
    location: 'ui/src/state/formatCheck.ts; _bmad-output/implementation-artifacts/deferred-work.md:4782'
    severity: 'medium'
  - summary: 'Panel `live`-state transition animation (Panel.tsx:52-56 homes it on c7-5) not built — the state has zero producers'
    evidence: 'No production caller passes `live={true}` (grep: only Panel.test.tsx and CardGrid''s bare `<Panel>`). Animating a transition nothing enters is unverifiable at any surface (READY standard: surface-anchored). Re-homed to the story that first sets `live` — the Panel.tsx comment is amended in this story to record that ruling.'
    location: 'ui/src/components/Panel/Panel.tsx:52-56'
    severity: 'low'
---

<intent-contract>

## Intent

**Problem:** A c7-3 coalesced refetch completes silently — a sighted user sees the card appear, its group count move and its curve bar grow, while a screen-reader user is told nothing (UX-DR45's "Deck updated — 62 cards" region does not exist; the App live-region census still pins 2). And a changed quantity has no visible moment on the tile: UX-DR16's one-shot accent glow was deferred to this story (`CardTile.tsx:155`, `tokens.css:333` both name c7-5).

**Approach:** Expose "a coalesced refetch settled successfully" as store truth (a monotonic counter beside c7-4's `updating` flag, incremented only in `refetchSequence`'s success arm) and render it through a new props-free `DeckAnnouncer` container: one polite visually-hidden live region, ConnectionPill's mount-silence idiom plus AgentView's keyed-Fragment re-announce idiom, copy from a registered copy module. Give the quantity badge a per-tile one-shot glow: render-time detection of a changed `quantity` prop flips `data-flashed` on, a rAF flips it off, and the base transition fades `var(--glow)` out over `--motion-glide` — instant-on, eased-off, no keyframes, no loop. Under reduced motion the glow is omitted entirely by an explicit `!important` registration in the tokens media block (duration-zeroing alone would leave an instant glow, not an absent one). Curve bars already jump instantly (mechanical four-token zeroing, pinned) — cite, don't build.

## Boundaries & Constraints

**Always:** `useDeckStore` written only by `src/state/deck.ts` (`store-writes.test.ts`); the counter is a sibling key with its own writer (`applyUpdating` shape, c7-4 precedent), incremented ONLY beside the settle in `refetchSequence`'s success arm — synchronous with the `:537` guard, so no second guard is needed. The announced count is `detail.mainboard_count + detail.sideboard_count` (all cards on the glass; by the conservation identity `deckGroups.ts:240-241` this equals the sum of every group-header count — the sibling signal UX-DR43 names). Copy verbatim per UX-DR45: `Deck updated — {N} cards`, spaced em dash U+2014, `card` when N is 1 (ManaCurve `copy.ts:109-111` pluralization precedent); the string lives in a copy module registered in `COPY_MODULES` and gets its own byte-level copy gate. The region is `aria-live="polite"`, class `deck-announcement`, `visually-hidden`, empty at rest and empty mid-flight; both App censuses move 2→3 and stay exhaustive (count + class + politeness + empty-at-rest). Repeat announcements with identical text must still mutate the DOM (keyed `<Fragment key={counter}>`, `AgentView.tsx:530` precedent). Glow spelling is bounded by the gates: `box-shadow` may only be `none` or `var(--glow)` (stylelint allowed-list), durations only `var(--motion-*)`, no `@keyframes`, no `animation`, no `transform` (the 5-entry pin at `token-usage.test.ts:2576-2602` must not move), no new token (70-pin), reduced-motion rules ONLY inside `tokens.css`'s media block. Motion never sole carrier: group-header counts (shipped) + the announcement are the accessible signals; the glow is garnish. All firing proofs through `scripts/vitest_probe_harness` (warm control first; stage the tree before planting; revert via `git diff --exit-code`). Runtime `ui/` diff → rebuild `src/companion/app/static/` and `plugin/`, commit both.

**Block If:** The exhaustive live-region censuses cannot admit a third region without weakening their shape (count+class+politeness must all survive); the glow cannot be expressed inside the box-shadow allowed-list without a new token or a DESIGN.md amendment; or a fourth polite region beyond UX-DR45's inventory turns out to be required (UX-DR45 licenses the deck-refetch announcement itself, so `deck-announcement` is its named channel — if review of the artefacts contradicts that reading, stop).

**Never:** No suppression-behind-a-modal logic and no deletion-UX changes — c7-6 owns both (its AC: "no announcement fires from behind a modal"); today the region simply announces on completion regardless of an open view. No announcement on the 404-clear, on any dropped outcome, on a cold boot, on a reconnect re-drive, or on a deck switch (`active_deck_changed` re-drives the boot through `runSequence` — its settle at `deck.ts:486` is not the refetch arm; the c6-3 recorded gap resolves to "switches are silent" as a structural consequence, argued in Design Notes). No timers, no debounce machinery (the c7-3 supersession IS the coalescing — `deck.test.ts:594-598` pins one settle per burst). No DeckList-row glow (UX-DR16 is the tile badge). No change to the tile's accessible name shape (`aria-labelledby` keeps the badge id — the "worth re-checking" note at `CardTile.tsx:471-477` is answered KEEP: the delegated carriers now exist, but removing the badge from the name would change every named-tile assertion for zero user gain; amend that comment to record the ruling). No format-check announcement and no Panel `live` animation (both in frontmatter `deferred`). No backend or wire changes. No new AppShell prop and no landmark change — the announcer rides an existing slot as a fragment beside `<ConnectionPill />`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Refetch completes | Settled deck; `deck_changed` → refetch success settle | Region text = "Deck updated — {main+side} cards", exactly once, on completion (not during flight) | N/A |
| Burst of events | N `deck_changed` frames coalesced to one settle | Exactly one announcement (counter +1 per settle, supersession pinned at store level) | N/A |
| Same total twice | Two sequential refetches ending at the same N | Second announcement still fires (keyed Fragment forces DOM mutation on identical text) | N/A |
| Singular | Deck totals exactly 1 card | "Deck updated — 1 card" | N/A |
| Cold boot | `start()` two-request sequence settles | Silent (boot settle `:486` is not the refetch arm); region empty | N/A |
| Deck switch | `active_deck_changed` → `redriveDeckBoot()` | Silent — re-drive is a boot; region unchanged | N/A |
| Reconnect re-drive | WS reconnect → `redriveDeckBoot()` | Silent (same path) | N/A |
| 404-clear / drops / abort / stop | Refetch non-success outcomes | Counter untouched; no announcement | N/A |
| Quantity changed | Tile re-renders with different `quantity` prop | `data-flashed` set, rAF clears it, glow fades out over `--motion-glide`; group-header count already updated | N/A |
| Quantity unchanged | Refetch re-renders tile, same quantity | No flash | N/A |
| New tile mounts | Card added to deck (new card_id) | No flash (seen-sentinel initialized at mount; the new tile is itself the signal) | N/A |
| Badge threshold | Quantity 2→1 (badge unrenders) / 1→2 (badge appears) | 2→1: nothing to glow; 1→2: badge appears flashed once | N/A |
| Reduced motion | `prefers-reduced-motion: reduce` | Glow omitted entirely (`box-shadow: none !important` registration, asserted at CSS source); curve bars jump instantly (existing four-token zeroing, cited) | N/A |
| Open agent view | Refetch completes behind a view | Announcement fires (today's behavior; suppression is c7-6's AC) — no test may pin silence | N/A |

</intent-contract>

## Code Map

- `ui/src/state/deck.ts` -- sole `useDeckStore` writer. Add `refetchSettles: number` to `DeckSlice` :174-189 (initial 0) + sibling writer beside `applyUpdating` :204; increment in `refetchSequence`'s success arm only, adjacent to `settle(...)` :548-549 (the `:537` guard is synchronous with it — no await between). `resetDeckState` :213 must reset it. Do NOT touch `settleFor` :410-416, the boot arm :486, the 404-clear :541, or any dropped path. New primitive selector `useDeckRefetchSettles` beside `useDeckUpdating` :816. Routing evidence: `driveDeckChanged` :780-789 (row 3 sends unsettled/none/refused to re-drive → silent), `redriveDeckBoot` :730-734 (switch + reconnect → boot arm → silent), `connection.ts:137-149` (`deck_changed` vs `active_deck_changed` verbs).
- `ui/src/containers/DeckAnnouncer/DeckAnnouncer.tsx` + `copy.ts` -- NEW props-free container (ConnectionPill's posture: reads its store itself, `App.tsx:628` rationale). Render-time `{seen, text}` state adjustment with `seen: null` mount-silence sentinel (`ConnectionPill.tsx:86-109` is the template — `useEffect`+`setState` is rejected by `react-hooks/set-state-in-effect`); announce when the counter advances AND `deck.status === 'deck'`. Render `<p className="visually-hidden deck-announcement" aria-live="polite"><Fragment key={counter}>{text}</Fragment></p>` (keyed-Fragment re-announce: `AgentView.tsx:506-532`). `copy.ts` exports the template builder; em dash precedent `ConnectionPill/copy.ts:67-72` (`DECK_SEPARATOR`), pluralization precedent `ManaCurve/copy.ts:109-111`.
- `ui/src/App.tsx` -- mount point: `connectionPill={<><ConnectionPill /><DeckAnnouncer /></>}` at :619 (no new AppShell prop; a visually-hidden `<p>` adds no landmark, banner census 3 holds). Do not reorder the measured effect blocks :194-198.
- `ui/src/containers/CardTile/CardTile.tsx` -- per-tile flash state (per-tile state is the ruled shape, header :49-60; lifting would re-render 99 tiles). Track `seen` quantity initialized from the mount prop (no mount flash); on render-time change detection set flash + update seen; a plain `useEffect` + `requestAnimationFrame` drops it (`AgentView.tsx:143-175` data-entering idiom — its `useEffect`, exactly; after-paint is the right ordering for the flashed frame; corrected from "layout effect" at review pass 1, finding 7). Attribute `data-flashed='true'` on the badge span :478-481. Amend the Q6 comment :467-477 (carriers now exist; naming KEPT — record the ruling). Badge renders only when `copies > 1` :297.
- `ui/src/containers/CardTile/QuantityBadge.css` -- glow rules: base gains `transition: box-shadow var(--motion-glide) var(--ease-glide)`; `[data-flashed='true']` sets `box-shadow: var(--glow); transition: none` (instant-on, fade-off = the flash). File is deliberately NOT in `CARD_SHAPED` (header :3-13). `var(--glow)` is the ONLY legal inline glow (stylelint box-shadow allowed-list; `--glow` composite at `tokens.css:196`).
- `ui/src/styles/tokens.css` -- reduced-motion media block :352-524 (the ONLY home): add `.card-tile-quantity[data-flashed='true'] { box-shadow: none !important; }` — the c7-5 inventory row at :333 already exists verbatim (owner list asserted at `token-usage.test.ts:2661`). No new token (70-pin: `tokens.test.ts:346`, `token-usage.test.ts:1177`); no transform (5-entry pin :2576-2602 unchanged); block structural assertions :2404-2456 must keep passing.
- `ui/src/App.test.tsx` -- BOTH censuses move 2→3 naming `deck-announcement`: at-rest :2105-2151 and mid-flight :3576-3582 (its "not.toContain('Updating')" and empty-mid-flight shape extend to the new region). New c7-5 describe hosted on the c7-3/c7-4 harnesses: `bootedDeck()` :3194-3202 / :3511-3519, `push('deck_changed', …)`, `withholdDeckRead` :3525-3536 (empty mid-flight, text on release), fixture counts from `deckDetail()` (assert the computed main+side sum, e.g. mainboard_count 101 case :3584-3595). Switch-silent test drives `push('active_deck_changed', …)` (:2540-2560 precedent). The c6-6 view-behind tests :4107+ must not be contradicted (announcement MAY fire behind a view — do not pin silence).
- `ui/src/state/deck.test.ts` -- c7-3 harness `buildBoot()` :493-511 (manually-resolvable `readDetail`); counter lifecycle unit tests: +1 on refetch success only; 0 through boot settle, 404-clear, each dropped outcome, abort, `stop()`; burst → exactly +1 (the settle-count pin :594-598 is the same claim); superseded refetch's late response adds nothing.
- `ui/src/containers/CardTile/CardTile.test.tsx` -- flash describe: no `data-flashed` on mount; set on quantity-change re-render then cleared after rAF; absent when quantity unchanged; 1→2 mounts the badge flashed. Codepoint pin precedent :863 area.
- `ui/tests/updating-marker.test.ts` -- the TEMPLATE for the new CSS-source suite `ui/tests/quantity-glow.test.ts` (node project): QuantityBadge.css halves (base transition token'd; flash rule = `var(--glow)` + `transition: none`; no `@keyframes`/`animation`/`transform` — reuse the lookbehind `(?<![\w-])transform\s*:`), tokens.css registration present inside the extracted media block with raw `!important`, and one citation-assertion that `ManaCurve.css` still carries `transition: height var(--motion-glide)` (the curve-bar AC's mechanism, :122-128).
- `ui/tests/copy-rules.test.ts` -- register `src/containers/DeckAnnouncer/copy.ts` in `COPY_MODULES` with reason (UX-DR45 verbatim string). New `ui/tests/deck-announcement-copy.test.ts` (precedent: `pin-announcement-copy.test.ts`): template prefix "Deck updated — " byte-for-byte, em dash U+2014 by codepoint, singular/plural rows, count-semantics row (main+side).
- `ui/src/components/Panel/Panel.tsx` :52-56 -- prose amendment only: `live` transition animation re-homed to the first producer (frontmatter `deferred`).
- `ui/tests/store-writes.test.ts` -- deck-row why-prose gains the counter's writer name (prose only; scan semantics untouched).
- `scripts/vitest_probe_harness.py` -- firing proofs: `--control` warm → `--expect-total N --expect-red '<substring>'` per plant → revert (`git diff --exit-code`) → `--expect-green`.

## Tasks & Acceptance

**Execution:**
- Task 0: baseline -- `cd ui && npm test` warm, then `uv run python -m scripts.vitest_probe_harness --control`; record `--expect-total` here. **DONE 2026-08-15: control `vitest: 76 files / 2183 tests, 0 failed, exit 0` — `--expect-total 2183` pre-story; the story lands at 78 files / 2226 tests (+43).**
- `ui/src/state/deck.ts` + `ui/src/state/deck.test.ts` -- `refetchSettles` counter (sibling key, writer, success-arm increment, reset, selector) + lifecycle unit tests per the matrix rows (burst, boot, 404, drops, stop, superseded).
- `ui/src/containers/DeckAnnouncer/DeckAnnouncer.tsx` + `copy.ts` + `ui/src/App.tsx` -- announcer container (mount-silence sentinel, keyed Fragment, polite hidden region) mounted beside ConnectionPill; copy module with the UX-DR45 template.
- `ui/src/App.test.tsx` -- both censuses 2→3; c7-5 describe: announce-on-completion with computed count, empty mid-flight, exactly-once per coalesced refetch, same-text re-announce, cold-boot/switch/404/drop silence.
- `ui/src/containers/CardTile/CardTile.tsx` + `QuantityBadge.css` + `ui/src/styles/tokens.css` + `ui/src/containers/CardTile/CardTile.test.tsx` -- per-tile one-shot flash (`data-flashed` + instant-on/fade-off transition), reduced-motion `box-shadow: none !important` registration, Q6 comment amended (naming kept), flash behavior tests.
- `ui/tests/quantity-glow.test.ts` (new) + `ui/tests/deck-announcement-copy.test.ts` (new) + `ui/tests/copy-rules.test.ts` + `ui/tests/store-writes.test.ts` -- CSS-source halves incl. ManaCurve mechanism citation; copy gate; COPY_MODULES registration; why-prose amendment.
- `ui/src/components/Panel/Panel.tsx` -- prose amendment re-homing the `live` animation (deferred).
- Firing proofs -- plant (a): remove the success-arm counter increment → announcement + counter tests RED; plant (b): remove the flash trigger (unconditional no-flash) → CardTile flash tests RED. Both through the harness, reverted, final `--expect-green`; paste proof lines here. **DONE 2026-08-15:**
  - Plant (a) — `applyRefetchSettles(...)` removed from `refetchSequence`'s success arm: harness exit 0 (CAUGHT) on `--expect-total 2226 --expect-red "c7-5"`, proof `vitest: 78 files / 2226 tests, 9 failed, exit 1` — 5 App.test announce tests + 4 deck.test counter tests RED by name (increments-by-one, burst-counts-one, superseded-late-success, reset).
  - Plant (b) — flash trigger made unconditionally no-flash in `CardTile.tsx`: harness exit 0 (CAUGHT) on `--expect-total 2226 --expect-red "quantity badge flashes"`, proof `vitest: 78 files / 2226 tests, 2 failed, exit 1` — the change-then-clear test and the 1 -> 2 threshold-mount test RED by name.
  - Both plants reverted (`git diff` confirmed the lines restored); final `--expect-green` proof `vitest: 78 files / 2226 tests, 0 failed, exit 0`, harness exit 0.
  - (Incidental: one CardTile test name originally used U+2192, which the harness's cp1252 console cannot encode when redirected — the harness itself crashed printing the RED line. Renamed to ASCII `1 -> 2`; no harness change.)
- Artifacts -- `cd ui && npm run build` + `uv run python -m scripts.build_plugin`; commit `src/companion/app/static/` + `plugin/` with the story; `uv run pytest -m "not integration"` green.

**Acceptance Criteria:**
- Given a settled deck and a coalesced refetch that completes successfully, when the settle lands, then the polite `deck-announcement` region announces exactly once "Deck updated — {N} card(s)" with N = mainboard_count + sideboard_count, and a burst of `deck_changed` events yields exactly one announcement.
- Given a cold boot, a deck switch (`active_deck_changed`), a reconnect re-drive, a 404-clear, or any dropped refetch outcome, when it runs to its end, then the region stays empty and the counter does not move.
- Given two sequential refetches ending at the same total, when the second completes, then the announcement fires again (DOM mutation via keyed Fragment).
- Given a tile whose `quantity` prop changed across a refetch re-render, when it re-renders, then its badge carries `data-flashed` for one frame and the accent glow fades out over `--motion-glide` — and a tile with unchanged quantity, a freshly mounted tile, and a DeckList row never flash.
- Given `prefers-reduced-motion: reduce`, when a quantity changes, then the glow is omitted entirely (CSS-source-asserted `box-shadow: none !important` inside the tokens media block) and the curve bars' instant jump stays covered by the existing four-token-zeroing pin.
- Given the accessibility tree at rest and mid-refetch, when the censuses run, then exactly three polite regions exist (`card-detail-announcement`, `connection-pill-announcement`, `deck-announcement`), all empty at rest; mid-flight, no region carries the marker text and the `deck-announcement` region stays empty (the pill's region may legitimately speak a connection transition during a refetch — tightened at review pass 1, finding 8), with banner census (3), h1 census, and zero-region shell census unchanged.
- Given the guard suites (store-writes, shell, posture, tokens, token-usage, lint-gates, copy-rules, wire-contract, updating-marker), when the suite runs, then all pass with only the declared prose amendments (store-writes why-row, copy-rules registration) and no token-count or transform-pin movement.

## Spec Change Log

## Review Triage Log

### 2026-08-15 — Review pass
- intent_gap: 0
- bad_spec: 0
- patch: 8: (high 0, medium 1, low 7)
- defer: 0
- reject: 14: (high 0, medium 0, low 14)
- addressed_findings: the 8 patches below (four layers: blind hunter, edge-case hunter, verification-gap, intent-alignment; post-dedup), all applied and committed as `a98ee7d`; test total moved 2226 → 2228. Rejected as noise: the announcer "reset announces stale text" claim (misread — the guard's `settles > seen` conjunction sets `''` on a decrease); the counter-advances-by-two-between-renders scenario (structurally one refetch in flight; sequential settles are separated by network round-trips); the App-level reconnect-silence and mid-boot-supersession counter tests (redundant composition — the shared re-drive/generation mechanisms are each pinned; the same argument c7-4 recorded); the announcer remount-silence test (unreachable — one production mount, the slot renders on every surface); artifacts-missing-from-diff (deliberate review-diff exclusion; drift verified zero and the commit inspected); NaN/negative copy-input guards (typed wire; DeckBadges renders the same counts raw); the hidden-tab rAF fallback timer (consequence benign — nothing is seen while hidden, the clear fires on the next painted frame; a timeout is a timer the repo avoids); the undefined→finite quantity flash (unreachable through CardGrid, which always passes wire numbers); the withhold/release helper triplication and bare `release!` diagnostics (block-scoped harnesses are the file's convention — c7-4 rejected the same); empty spec bookkeeping sections (workflow-designed structure); and the intent-alignment auditor's descriptive notes (perceptual residue — AT speech, painted pixels, evaluated media queries — is the repo's established jsdom boundary, delegated to the epic's manual checklist; AC 4 "motion never the sole carrier" is a review property satisfied by the shipped group-header counts + announcement).

1. (medium) App-level flash-through-refetch test added — the only assertion that the flash survives CardGrid's card_id-keyed instance persistence across a settle; badge lookup scoped by accessible name (c7-4 DFC lesson).
2. (low) `DeckAnnouncer` now tracks WHICH deck the sentence is about (`about` in the sentinel) and empties the region at render time when the settled id departs (404-clear, switch) — CardDetail's pin-region precedent. Both silence tests strengthened to announce first, then assert the emptied region; a dropped 503 after an announcement deliberately leaves the sentence standing (the deck it describes is still on the glass).
3. (low) CardTile's clear effect re-keyed from `flash.flashed` to the whole `flash` object so a second change while a flash is pending cancels the stale rAF and re-arms; unit test added.
4. (low) `quantity-glow.test.ts` specificity comment corrected (0,3,0) → (0,2,0), agreeing with tokens.css.
5. (low) `DeckAnnouncer` docstring harmonised with the census inventory: third polite region at rest, fourth while an agent view is open.
6. (low) Switch-silence test's deck-b fixture given a distinct id + name so the heading assertion proves the switch landed.
7. (low) Code Map corrected: the flash clear is a plain `useEffect` + rAF (the AgentView idiom actually cited), not a layout effect.
8. (low) AC 6 tightened: all regions empty at rest; mid-flight no region carries the marker text and the deck-announcement region stays empty (the pill may legitimately announce a connection transition mid-refetch).

Patch-pass verification (2026-08-15): lint + format:check + `tsc -b` clean; `vitest: 78 files / 2228 tests, 0 failed, exit 0` (harness `--expect-total 2228 --expect-green`, exit 0 — +2 tests over the story's 2226: the flash-through-refetch case and the re-arm case); `npm run build` + `build_plugin` rebuilt and committed with zero residual drift; `pytest -m "not integration"` green (3020 passed, 1 skipped).

## Design Notes

- **Why the counter and not the `updating` falling edge or `detail` identity:** the falling edge fires on every terminal path including drops (announcing a dropped 503 would lie), and `detail` identity changes on boot settles and switches too (announcing a switch contradicts c6-3's recorded gap and UX-DR45's refetch-only wording). The success arm of `refetchSequence` is the ONE seam that means "a coalesced refetch completed with a new deck" — a store-side counter makes that truth readable without re-deriving it downstream.
- **Why switches and re-drives are silent, resolving c6-3's open question:** `active_deck_changed` and reconnect both run `redriveDeckBoot()` → `runSequence` → the boot settle arm; a mid-boot `deck_changed` falls to the same re-drive (decision-table row 3). UX-DR45 legislates the announcement for "deck refetches… per coalesced refetch"; no artefact legislates a switch announcement, and the structural split in `connection.ts:137-149` makes the silent outcome the mechanical default rather than a special case.
- **Which count "62" is:** total on the glass = `mainboard_count + sideboard_count`. UX-DR43 names group-header counts as the sibling accessible signal, and by the conservation identity (`deckGroups.ts:240-241`) their sum equals exactly this total — the announcement and the headers can never disagree. A sideboard-only mutation still moves the announced number.
- **Why instant-on/fade-off, not keyframes:** ruled twice already (c6-5, c7-4): `@keyframes` bodies read as `from`/`to` rules to the reduced-motion CSS reader, and `!important` is spec-ignored inside keyframes, so the accessibility override would parse and do nothing. A transition out of a state attribute is neutralizable and honest. `transition: none` on the flashed state makes the glow appear instantly (a fade-IN reversed after one rAF frame would never reach full glow); the base transition carries the fade-out.
- **Why the explicit reduced-motion registration:** duration-zeroing makes a transition INSTANT, not ABSENT — an instant glow that never fades is a persistent glow, the opposite of "omitted". Hence `box-shadow: none !important` on the flashed selector inside the media block (the c4-4 hover-pop precedent, `tokens.css:373-380`).
- **Behind-a-modal:** the region announces today even with a view open; c7-6's AC ("no announcement fires from behind a modal") gates it there. Building the gate now would be scope theft and would need agent-view state the announcer deliberately doesn't read.
- Known flake context: frontend cold-run eslint timeout — run the harness control warm. Python suite: R3's fix is on this branch; any red is new information.
- Branch process: story branch `feat/companion-c7-5-announce-once` off umbrella `feat/companion-c7`; PR targets the umbrella (Greptile per story).

## Verification

**Commands:**
- `cd ui && npm run lint && npm run format:check && npm test` -- expected: eslint + stylelint clean (box-shadow allowed-list, motion rules), prettier clean, `tsc -b` clean, all vitest files green including guard suites with only the declared prose amendments.
- `uv run python -m scripts.vitest_probe_harness --control` (warm), then per-plant `--expect-total N --expect-red '<substring>'`, revert, `--expect-green` -- expected: both plants RED on named tests, reverts clean, final green; proof lines pasted into Tasks.
- `cd ui && npm run build && git status --porcelain -- src/companion/app/static/ plugin/` -- expected: rebuilt bundle + `plugin/` mirror committed, zero residual drift.
- `uv run pytest -m "not integration"` -- expected: green (no backend file touched).

## Auto Run Result

Status: done

**Summary.** The glass finally speaks: a `refetchSettles` counter beside c7-4's `updating` flag — incremented only in `refetchSequence`'s success arm, so cold boots, deck switches, reconnect re-drives, the 404-clear and every dropped outcome are silent by construction — drives a new props-free `DeckAnnouncer` riding the connectionPill slot as a fragment. One polite visually-hidden `deck-announcement` region announces exactly once per coalesced refetch, on completion: "Deck updated — {N} card(s)" with N = mainboard + sideboard (equal to the sum of every group-header count by the conservation identity), keyed-Fragment re-announce on identical text, mount-silence sentinel, and (review patch 2) the sentence empties when the deck it describes leaves the glass. The quantity badge gets UX-DR16's one-shot glow: per-tile seen-quantity detection flips `data-flashed` for one rAF frame, `var(--glow)` paints instantly (`transition: none` on the flashed state) and the base transition fades it out over `--motion-glide` — no keyframes, no transform, no new token. Under reduced motion the glow is omitted entirely (`box-shadow: none !important` in the tokens media block); curve bars stay on their existing mechanical zeroing, pinned by citation. Both App live-region censuses moved 2→3 and stayed exhaustive. The c6-3 open question (announce on a deck switch?) is resolved structurally: switches re-drive the boot and are silent.

**Files changed** (commits `134cd48` feat + `a98ee7d` review patches, on `feat/companion-c7-5-announce-once` off umbrella `feat/companion-c7`):
- `ui/src/state/deck.ts` — `refetchSettles` sibling key + writer, success-arm increment, reset, `useDeckRefetchSettles` selector.
- `ui/src/containers/DeckAnnouncer/DeckAnnouncer.tsx` + `copy.ts` — NEW: the polite region, mount-silence + deck-identity sentinel, keyed Fragment; UX-DR45 template with the invented-in-the-open singular.
- `ui/src/App.tsx` — announcer mounted beside `<ConnectionPill />` in the existing slot (no AppShell edit, no landmark change).
- `ui/src/containers/CardTile/CardTile.tsx` + `QuantityBadge.css` — per-tile flash state (re-armed per change, prior rAF cancelled), `data-flashed` on the badge; instant-on/fade-off glow rules; Q6 naming comment amended (KEEP recorded).
- `ui/src/styles/tokens.css` — reduced-motion `box-shadow: none !important` registration for the flashed badge (inventory row :333 already named c7-5).
- `ui/src/components/Panel/Panel.tsx` — prose amendment re-homing the `live` animation to its first producer (frontmatter deferred).
- Tests: `ui/src/App.test.tsx` (both censuses 2→3; c7-5 describe: announce-once/computed-sum/singular/burst/same-text-MutationObserver/switch/404+drop silence with post-announcement emptying/behind-a-view observed for c7-6/flash-through-real-refetch), `ui/src/state/deck.test.ts` (counter lifecycle), `ui/src/containers/CardTile/CardTile.test.tsx` (flash one-shot, re-arm, mount/threshold rows), new `ui/tests/quantity-glow.test.ts` (CSS-source halves + ManaCurve citation), new `ui/tests/deck-announcement-copy.test.ts` (byte-level gate against both artefacts).
- Guard-suite amendments: `ui/tests/copy-rules.test.ts` (COPY_MODULES registration), `ui/tests/store-writes.test.ts` (why-prose), `ui/tests/shell.test.ts` (CONTAINERS 34→36).
- `src/companion/app/static/` + `plugin/` — rebuilt committed mirrors (`assets/index-DpbZ6wJA.js`), zero drift.
- This spec file — record, firing proofs, triage log.

**Review findings breakdown.** Four layers, post-dedup: 8 patched (1 medium — the flash never verified through the real refetch path / tile-instance persistence unpinned; 7 low), 0 deferred from review, 14 rejected (see triage log). No intent gaps, no bad-spec loopbacks.

**Follow-up review recommendation: true** — patched severities: 0 high, 1 medium, 7 low → score 3×1 + 7 = 10 ≥ 5.

**Verification performed.** Firing proofs through the committed vitest harness: control at 2183 (pre-story); plant (a) success-arm counter increment removed → 9 expected REDs (5 App announce tests + 4 counter tests); plant (b) flash trigger neutered → 2 expected REDs; both reverts proven; green-certified at 2226 and re-certified at 2228 after the patch pass (`vitest: 78 files / 2228 tests, 0 failed, exit 0`, harness exit 0). Full gate independently re-run by the orchestrator at both checkpoints: eslint + stylelint + prettier + `tsc -b` clean; `npm test` 78 files / 2228 tests green; SPA rebuild + `plugin/` mirror with zero residual drift; `uv run pytest -m "not integration"` 3020 passed, 1 skipped. Matrix test audit: all 14 rows covered by tests that ran in the green suite (the reconnect-re-drive row via the shared re-drive mechanism pins).

**Residual risks.**
- The glow's on-pixel look (instant `var(--glow)`, 240 ms eased fade) and the real reduced-motion omission are asserted at the CSS-source surface only (jsdom applies no stylesheets, evaluates no media queries — repo convention); real-frame paint ordering of the one-rAF flash and actual screen-reader speech are likewise perceptual residue. All belong on the epic's manual-testing checklist for an eye/ear check.
- The count semantics (mainboard + sideboard) and the singular "1 card" are extensions beyond the epic's worked example, chosen with recorded rationale — flag for Brad's review.
- "Exactly three live regions" prose in `AgentView.tsx:506`, the c6-7 App.test comment, and `AgentViewsNav` comment/copy now reads one short of the four-channel inventory — undeclared prose amendments deliberately left untouched (AC 7 allows only the declared ones); a candidate for the next prose sweep (R7).
- The announcement fires behind an open agent view today — observed by a test written so c7-6 has a red test to flip when it builds the suppression its AC legislates.
