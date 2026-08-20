---
title: 'The SC-5 gate'
type: 'chore'
created: '2026-08-20'
status: 'done'
baseline_revision: '58372f9e9a77b9e0dc21e6ccc0663a2606acf7f7'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-15-context.md'
warnings: ['oversized']
deferred: []
---

<intent-contract>

## Intent

**Problem:** SC-5 — "the deck view and agent panel look like a deliberate product, not a debug
dashboard" — is the last open success criterion of Phase 1, and it is the one criterion no test can
close. Three artefacts independently reserve it to Brad in the same words (`epics-companion-app.md:726-730`
UX-DR49, `architecture/…/EPIC-SPLIT.md:121`, `sprint-status.yaml:716`): *it cannot be automated or
delegated*. Six stories have handed findings forward to this gate and none of them have an owner
until it runs; if it is never written down with a date, a later reader cannot tell whether the gate
was run or merely assumed.

**Approach:** Run the gate the way this project has run every prior human gate (the pre-Epic-7
real-deck gate, `pre-epic-7-real-deck-gate-report-2026-07-17.md`): assemble the evidence
mechanically into a dated report, leave an **unchecked review sheet** carrying one line per
criterion, and let the named human check the boxes and write the ruling line. The machine half is
the dossier and the sheet; the verdict half is Brad's and is the only thing that closes the gate.

## Boundaries & Constraints

**Always:**
- The verdict is Brad's, recorded as a blockquote ruling line carrying his name and an ISO date,
  in the shape `pre-epic-7-real-deck-gate-report-2026-07-17.md:874-878` established.
- Every finding carries **both anchors** — the artefact anchor and the code anchor — the discipline
  c4-12 set for the SC-5 conformance list (`c4-12-…md:1533-1570`).
- Findings are offered without a verdict attached. c4-12's rule holds: a story makes SC-5
  *answerable*; it does not answer it.
- Every inherited entry in scope gets an **explicit disposition, including refusals** — C2 retro
  ruling R2, `deferred-work.md:4924`: an inherited entry is *declined by name rather than left
  unmentioned*.
- `sprint-status.yaml` is edited **surgically, never regenerated** — `sprint_plan.py generate`
  rebuilds `development_status` and would destroy 67 inline story comments and 8 gate keys
  (`sprint-status.yaml:329`).

**Block If:**
- **The SC-5 judgement itself.** AC 1 requires a human, named as Brad, and forbids delegation. No
  unattended run may write, infer, predict or pre-empt the verdict.
- **The arrow-key grid-navigation revisit flag** (`EXPERIENCE.md:144`) — "actioned or re-accepted"
  is a product decision. *Actioning* it is not a component change: `onKeyDown`/`onKeyUp`/`onKeyPress`
  sit in `A11Y_INTERACTION_HANDLERS` (`ui/eslint.config.js:17-24`), so a roving-tabindex grid is an
  ESLint **error** today (`c4-11-…md:231-234`) and adopting it means changing a lint rule.
- **The agent-view footer occlusion** (Code Map, finding F1) — the ruling is either "an open modal
  is not a surface" or a scrim cut-out, and both are Brad's.
- **The three reduced-motion inventory deltas** (findings M1–M3) — M2 and M3 contradict rulings
  already recorded in shipped source (`SuggestionsView.css:113-118`, `c6-7-…md:186`); overturning a
  recorded ruling is not a mechanical fix.
- **Prerequisites.** 15.3, 15.4 and 15.5 are `backlog` with no spec on disk. The epic orders this
  story last because it judges what they finish (`epic-15-context.md:111-115`). Running the gate
  against unfinished release documentation and an unmirrored plugin produces a verdict that has to
  be re-run.

**Never:**
- Never record a verdict, a pass, a fail, or a condition on Brad's behalf.
- Never check a review-sheet box. The pre-Epic-7 harness refuses to overwrite a report containing
  `- [x]` (`pre-epic-7-real-deck-gate-report-2026-07-17.md:952+`); honour the same sentinel.
- Never build arrow-key grid traversal, alter the Tab order, or relax
  `A11Y_INTERACTION_HANDLERS` under this story.
- Never delete inventory row 10 ("Detail-panel content swap"). It is a prohibition that closes
  validation finding L7 (`validation-report-2026-07-25.md:77`), not a motion with a missing subject.
- Never file the report in `docs/`. `docs/release-readiness-review.md` is the outlier written for an
  audience outside the BMAD pipeline; every gate tied to a story lives in `implementation-artifacts/`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|---|---|---|---|
| Gate sheet generated | Report file absent | `sc-5-gate-report-<date>.md` written with every finding, both anchors each, and an unchecked review sheet | No error expected |
| Gate sheet re-generated | Report already contains `- [x]` | Refuse to overwrite — the human has begun the walk | Abort with the sentinel message, exit non-zero |
| Verdict recorded | Brad checks every box and writes the ruling line | Gate CLOSED; `sprint-status.yaml` `15-6-…` flipped with the PR/date, dispositions appended to `deferred-work.md` | No error expected |
| Verdict withheld | One or more boxes unchecked | Gate stays open; status is not `done` and the epic does not close | Not an error — the open sheet *is* the record |
| Motion delta ruled | Brad accepts or rejects M1–M3 | Accepted → row added to `tokens.css:326-338` inventory + guard extended; rejected → ruling recorded in place beside the existing counter-ruling | No error expected |
| Footer occlusion ruled | Brad rules F1 | "Not a surface" → ruling written into `EXPERIENCE.md`/`DESIGN.md`; "cut-out" → a new story, not this one | No error expected |

</intent-contract>

## Code Map

Investigated 2026-08-20 at `58372f9`. This is the gate's evidence dossier — the auditing is done;
what remains is the judgement.

### The criteria and their sources

- `_bmad-output/planning-artifacts/epics-companion-app.md:3433-3468` -- story 15.6's seven ACs.
  The judgement `:3441-3444`; anti-patterns `:3446-3448`; the four-panel tension `:3450-3452`; the
  revisit flag `:3454-3456`; reduced motion `:3458-3460`; footer `:3462-3464`; the record `:3466-3468`.
- `epics-companion-app.md:726-730` -- **UX-DR49**, the ruling that makes this human. `:544-549`
  UX-DR32 (footer, *"a condition of public release, not a design choice"*). `:510-514` UX-DR30
  (state panel — *"no red alert fills, no toast color-coding"*). `:685-692` UX-DR42 (the motion
  inventory). `:535-542` the measured Tab corridor, ending *"the residue is homed on 15-6"*.
- `…/prds/prd-Artificial-Planeswalker-2026-07-22/prd.md:183-185` -- SC-5. `:167` NFR-08 (the
  Wizards sentence was added by adversarial review, `review-adversarial-general.md:36`). `:153` FR-20.
- `…/ux-designs/ux-Artificial-Planeswalker-2026-07-22/DESIGN.md:563` -- the footer sentence,
  verbatim source. `:478`, `:605-606` the anti-pattern do/don't rows. `:120-126` the motion tokens.
- `…/EXPERIENCE.md:176` -- *"Rejected — debug dashboard … Note the tension … carried by typography,
  spacing and restraint rather than by sparseness."* `:45` *"Guidance, never an error page."*
  `:48`, `:102` footer P0. `:150-153` the Accessibility Floor. `:137` *"Mouse-first tool; the
  keyboard gets a floor, not a surface."*
- `…/validation-report-2026-07-25.md:8` -- the standing independence caveat: that gate was
  self-reviewed, and *"the four rulings in EXPERIENCE.md … need Brad."* `:45` H3; `:131` its
  disposition; `:77` L7.

### The gate's inbox — findings already handed forward, with both anchors

- `c4-12-…md:1533-1570` -- **the SC-5 conformance findings list**, 12 landed items plus three
  buckets. Explicitly closes with *"No verdict is offered."* Still open and named as this story's:
  the UX-DR20 empty-panel contradiction, `StatChip` without a surface, the 10px ALL-CAPS legal text,
  the `rem` basis, **the skip link not reaching the footer**.
- `c4-12-…md:1663-1666` -- the eye-check finding *"the two empty right-column panel shells beside
  it do not [look intentional] — the UX-DR20 contradiction rendered, and precisely `DESIGN.md`'s own
  'reads as a loading failure' failure mode. Recorded, not repaired, and handed to the SC-5 gate."*
- `epic-14-retro-2026-08-16.md:250-267` -- **the C7 manual-testing checklist L1–L10, unrun**, plus
  *"Carried in from C6, still unrun: K3, K5, J4, J5, **J6 (fifth home)**"*. `:310` states plainly
  that the checklist has not been run.
- `epic-c3-retro-2026-08-02.md:459` -- **D1**, agent `validate_deck` vs REST `format-check`,
  *"AD-1's promise, owned by nobody"* — newly homed here.
- `deferred-work.md:4977` (skip link / footer corridor, Medium, with the alternative costed),
  `:5150` (**NOT TOUCHED**), `:6038` (the connection pill's +1, Low), `:4820` and `:5110`
  (*"Home: c7-3 or 15-6"*), `:1926-1936` (the 10px ALL-CAPS legal text, first item on the manual
  checklist), `:1599-1601` (*"On a long deck, the footer stays visible without scrolling"* — the
  eye-check c2-10 deferred).

### AC 6 — footer attribution. **Two findings; the first is the gate's hardest.**

- `ui/src/components/Footer/Footer.tsx:34-61` -- no props, no state, no landmark of its own.
  Copy at `ui/src/components/Footer/copy.ts:64-73`, gated **byte-for-byte against `DESIGN.md` read
  at test time** by `ui/tests/attribution.test.ts:147-156`. Two links, `target="_blank"`,
  `rel="noopener noreferrer"` (`Footer.tsx:52-53`).
- `ui/src/components/Footer/Footer.css:50-59` -- `--text-secondary` (9.3:1, the *passing* tier);
  `:91-97` underline **at rest**, `display: inline-block` load-bearing (text-decoration does not
  propagate into flex items — a 2026-07-30 review find that would have made the release-condition
  underline true in source and false on screen).
- `ui/src/App.tsx:729` renders `footer={<Footer />}` **ungated**; `AppShell.tsx:269-271` renders the
  slot unconditionally; there is no router (react, react-dom, zustand only). Presence on every
  surface is therefore **structural**, and c2-10 deliberately refused an enumerated surface list
  (`App.tsx:161-174`). Pinned by `App.test.tsx:1614-1643`, `:1706-1718`, and the four-slot
  never-blank census `:2196-2367`.
- **F1 — the agent view occludes the attribution.** `AppShell.css:65-72` gives `.app-shell`
  `height: 100dvh; padding: var(--space-gutter)`; `AppShell.css:282-286` gives `.app-shell-overlay`
  `position: fixed; inset: var(--space-gutter)` — *the same box*, by design and by its own comment
  (`AgentView.css:3-18`). `.agent-view-scrim` (`AgentView.css:46-51`) fills it with
  `--scrim: rgb(8 9 18 / 75%)` (`tokens.css:92`) plus `backdrop-filter: blur(16px)`. The footer sits
  inside that padding box, so **while an agent view is open the attribution is behind a 75 % scrim**.
  `App.tsx:170-174` claims the footer "survives it by construction" — structurally true, visually
  not. No test covers it: jsdom paints nothing.
- **F2 — the connection pill overlaps the attribution below 1100 px.** Clearance was measured
  against a single-line 37 px `.footer-attribution`; below 1100 px the paragraph wraps.
  *Mitigated, not fixed*, by `min-width: 1100px` (`AppShell.css:52-64`, which records the finding
  and the reasoning in place).
- **"Visible without scrolling" is proved nowhere.** What is proved is the *mechanism*, read from
  CSS source: `ui/tests/shell.test.ts:742-765` (`100dvh`, the single `overflow-y:auto` scroller,
  `flex-shrink: 0` on header and footer). `App.test.tsx:2191-2194` says so itself — *"not blank
  here means the DOM carries text … strictly weaker than a human sees something."*
- **Citation drift:** the code comments cite the footer sentence as `DESIGN.md:375`; it is now
  `DESIGN.md:563`. `attribution.test.ts` is immune (it selects by structure), so nothing goes red.

### AC 5 — the reduced-motion inventory. **Three deltas, one non-subject, one guard gap.**

- `ui/src/styles/tokens.css:314-351` -- **the registration point**; the inventory table at
  `:326-338` (10 entries, each with a named fallback and an owning story); the no-pulse/no-loop
  clause at `:340-348`; the `@media (prefers-reduced-motion: reduce)` block at `:352-545`.
  Peer copies: `epics-companion-app.md:685-692` (source of truth), `EXPERIENCE.md:153`.
  **`DESIGN.md` carries no inventory** — do not look for one there.
- Shipped motion is **12 transitions, zero `@keyframes`, zero `animation:`, zero `infinite`**,
  across all 32 tracked stylesheets and the built bundle. "Nothing pulses or loops" is therefore
  satisfiable by inspection, and is double-guarded: `ui/.stylelintrc.json:39-43,71-78,112-120` and
  `ui/tests/token-usage.test.ts:1331-1333` (engine `:325-372`, which handles scientific notation and
  comma-list segments). The connection pill — the component the ban exists to protect — ships no
  motion at all (`ConnectionPill.css:28-31`).
- **M1 — `ui/src/containers/FlipControl/FlipControl.css:98`**: flip-control chrome opacity fade
  0.65 → 1.0 over `--motion-glide`, on every tile hover. `FlipControl.css:27-31` argues it needs no
  *registration* (true — duration-only, so token zeroing works), but UX-DR42 demands an **inventory
  row**, which is a separate obligation. No row names it. The cleanest finding.
- **M2 — `ui/src/containers/SuggestionsView/SuggestionsView.css:119-121`**: suggestion-row live
  tint, structurally identical to inventory row 6 ("Deck-row live tint → instant") on a different
  component in a different epic. `SuggestionsView.css:113-118` and `c6-7-…md:186` *already record a
  ruling* that no new row is needed. That is a ruling, not a row — accept it or add the row.
- **M3 — `SuggestionsView.css:211`**: suggestion-row thumbnail fade-in, claiming coverage under
  row 4 ("Image fade-in", stamped `(c4-4)`) at `SuggestionsView.css:200-203`. Defensible if row 4
  reads as a class rather than one element; wants an explicit ruling.
- **M4 — row 10 has no subject.** "Detail-panel content swap → instant, no crossfade (c4-5)":
  `CardDetail.css:28-35`, `:80-83` ship *no transition at any setting*. The row is a **prohibition**
  that closes validation L7 (`validation-report-2026-07-25.md:77`). Record as intentionally
  satisfied by absence; do not delete it.
- **M5 — the completeness guard is a substring check.** `token-usage.test.ts:2653-2664` asserts only
  that eight story-id strings appear somewhere in `tokens.css`. The real pin,
  `token-usage.test.ts:2544-2605` (list at `:2588-2596`, five entries, non-vacuity at `:2551-2554`,
  probe at `:2607-2650`), covers **`transform`/`scale`/`rotate`/`translate` only** — blind by
  construction to `opacity`, `height`, `background-color` and `box-shadow`, which is exactly the
  class M1–M3 fall into. **This is the mechanical reason three motions slipped through a green
  suite**, and the strongest candidate for remediation once M1–M3 are ruled.

### AC 2 — the anti-patterns. **All six clean; two caveats worth eyeballing.**

- Raw JSON views: zero `JSON.stringify` in non-test `ui/src`; the only `JSON.parse` is in the fetch
  layer (`ui/src/api/client.ts:706`) and is never rendered; no `<pre>` anywhere. The only `<code>`
  is `StatePanel.tsx:95`, the monospace command chip UX-DR30 asks for.
- Log panes: no `console.*` in shipped `src`; no log component; the only scroll containers are
  `.app-shell-columns`, the oracle scroller and the agent-view body.
- Dense id tables: exactly one `<table>` in the SPA — `ManaCurve.tsx:196-212`,
  `className="visually-hidden mana-curve-table"`, the a11y alternative to the bar chart, never
  visible. Identifiers appear only as React keys and image-route params, never as text.
  `ConnectionPill.tsx:42` deliberately ships no port/instance-id tooltip.
- Error pages: no router, no `ErrorBoundary`, no error route. Every failure is a calm `StatePanel`
  in the left column, chosen from a **reason token** (`state/states.ts:91-136` `PANEL_FOR_REASON`),
  with nav and footer live around it. `StatePanel.test.tsx:61` pins "no illustration, icon or
  image"; `copy-rules.test.ts:805` bans exclamation marks, emoji and blame across `src`.
- Toast storms: **no toast, snackbar, notification component or queue exists.** The only "toast"
  hits in the repo are negative fixtures (`ui/tests/fixtures/css/shell-violation.css:311`).
  The three live regions are single and polite, deliberately not stacked.
- Alert colours: the semantic layer is three desaturated tokens (`tokens.css:120-123`), never a
  fill — `Badge.css:141-165` uses border + text at full token and background as a **12 % wash**,
  always beside a status **word** (`FormatCheck.tsx:275`); `StatChip.css:96-107` has a deliberate
  third neutral branch so "no change" is not red; the dot is `aria-hidden` and static beside its
  word. The state panel referencing `--negative`/`--caution` is a **build-breaking** gate
  (`token-usage.test.ts:1002-1082`).
- ⚠️ **Caveat A1 — `FormatCheck.tsx:162-165` says it in its own comment**: `caution` is *furniture,
  not a signal*; rotation is advisory on 40 of 40 real decks, so a caution badge appears on ~100 % of
  decks. The one place a semantic colour risks reading as noise.
- ⚠️ **Caveat A2** — the 10px ALL-CAPS legal text (`Footer.css:50-59`, micro role + uppercase from
  the token layer), spec-as-written, ruled "ship as written" 2026-07-30, ledgered at
  `deferred-work.md:1926-1936`.

### AC 4 — the revisit flag. **No ledger row exists; it lives in the UX spine.**

- `EXPERIENCE.md:144` -- the canonical entry. Format: `**[DEFERRED 2026-07-25 — gate H3]**` inline,
  closing with **"Revisit before public release"** and the reason. `grep -n '\barrow'` over
  `deferred-work.md` returns **zero hits** — every apparent match is "n*arrow*". There is nothing
  to close in the ledger.
- Peer copies that must stay consistent: `validation-report-2026-07-25.md:45`, `:108`, `:131`;
  `epics-companion-app.md:659-662`, `:542`, `:2367-2369`, `:3454-3456`;
  `architecture/…/ARCHITECTURE-SPINE.md:492-493`; `epic-15-context.md:95-97`.
- **The consequence is true today and pinned numerically.** `AppShell.tsx:189,242-257,116-131` set
  document order and nothing carries `tabindex`, so Tab order == DOM order and the two footer links
  are the last two focusables (`App.test.tsx:1680-1703`). On a 99-card deck
  (`App.test.tsx:1795-1830`): **209 focusables**, **206 stops** header → first footer link, the skip
  link removes only the first **105**, leaving **101**. The 1-card twin (`:1897-1903`) is 7/4/3 —
  proportionally worst where the corridor is shortest.
- **Stale-number trap:** `EXPERIENCE.md:144` carries its own ⚠️ — every figure gains **+1** as of
  c5-7 (207/79/103.0; 102 left) and *"a derived +1 is not a measurement."* The suite pins were
  recomputed from the DOM; the 40-deck corpus sweep was not.
- **Actioning is not a component change:** `ui/eslint.config.js:17-24` puts `onKeyDown`/`onKeyUp`/
  `onKeyPress` in `A11Y_INTERACTION_HANDLERS`, making a roving-tabindex grid an ESLint **error**
  (`c4-11-…md:231-234`).

### AC 7 — how a gate is recorded here

- `pre-epic-7-real-deck-gate-report-2026-07-17.md` -- **the precedent to transplant.** Title carries
  the gate ID; `:5-7` a metadata bullet block (**Run date**, **Baseline commit**, scope counts);
  `:9` snapshot metadata (what version of the world was judged); `:20` Summary table; `:47` per-item
  detail; `:849` standing caveats; `:859` findings that are explicitly *not* blockers; `:872`
  **Review sheet (Sathias)** — the verdict surface; `:941` a named-divergence template with a
  mandatory `Disposition:` field; `:952` the harness appendix and the **`- [x]` sentinel** that
  refuses to clobber a begun walk.
- `:874-878` -- the transplantable ruling shape: a blockquote **`> Gate ruling (<name>, <ISO date>):`**,
  what was accepted, an explicit sentence naming what was *deferred rather than resolved* (the
  conditions), then **`<GATE-ID> is CLOSED; <what unblocks>`** — over a per-item checkbox sheet, so
  the record shows the gate was walked item by item rather than asserted wholesale.
- `spec-pre-epic-7-real-deck-gate.md:67,72` -- the verdict is mirrored back onto the spec's own task
  line and stated as a testable AC.
- `docs/release-readiness-review.md:3-7,13,76-176,181` -- the second pattern, worth borrowing one
  thing from: a **graded** verdict over explicit buckets (blockers / should-fix / nice-to-have /
  verified good), with conditions discharged in an **appended, dated resolution log** rather than by
  editing the original verdict.
- `deferred-work.md` closing conventions (there is no documented format; four emergent shapes):
  in-place dated **`CLOSED <date>: <what shipped> (PR #N, merged at <sha>) — <the named test>`**
  (`:83`, 94 instances); a `## ✅ Resolved by <thing> (<date>)` section that keeps the originals for
  traceability and names its own residue (`:480-502`, `:635` — **a gate has closed ledger entries
  under this heading before**); `###` disposition sub-headings for a graded batch (`:5736`, `:5798`,
  `:5819`, `:5837`); and the non-closing vocabulary — `NOT TRIGGERED`, `PARTIALLY TRIGGERED`,
  `DECLINED with the reason, re-homed to <X>`, `RE-ACCEPTED`. Newest section heading to model:
  `## Deferred from: story 15-2 (image cache stewardship, 2026-08-18)` (`:6333`).

### Prerequisite state (read-only evidence)

- `sprint-status.yaml:712-724` -- `15-1` done, `15-2` done, **`15-3`, `15-4`, `15-5`, `15-6` all
  `backlog`**; `:716` *"c8-6 is the SC-5 human gate — Brad only, cannot be automated or delegated"*;
  `:327` *"Next recommended story is 15-3."* The `epic-15` inline comment is stale — it still says
  "15-2..15-6 remain" while `15-2` is `done` on the next line.
- No `spec-15-3-*`, `spec-15-4-*`, `spec-15-5-*` and no partial artefacts exist. `epic-15-context.md:111-115`
  orders 15.6 last: *"it judges what 15.1–15.5 have finished documenting and packaging."*
- Working tree clean at `58372f9` on `claude/hello-7v0acf`, one commit ahead of
  `feat/companion-epic-15`.

## Tasks & Acceptance

**Execution:**

- `_bmad-output/implementation-artifacts/sc-5-gate-report-YYYY-MM-DD.md` (the date of the walk,
  matching `pre-epic-7-real-deck-gate-report-2026-07-17.md`'s convention) -- create the gate sheet
  on the pre-Epic-7 skeleton: title with the gate ID, a **Run date / Baseline commit / Scope**
  bullet block, a Summary table (one row per AC), a per-criterion detail section carrying the
  findings from this Code Map with **both anchors each**, a standing-caveats section (jsdom paints
  nothing; the 07-25 validation gate was self-reviewed), a *not-blockers* section, and an
  **unchecked** `## Review sheet (Brad)` with one checkbox pair per criterion plus the
  named-divergence template. -- the record AC 7 demands, in the shape this project already uses.
- the same gate-sheet file -- carry the inherited
  inbox forward as its own section, one line per item with its disposition left blank: c4-12's five
  still-open conformance items, the UX-DR20 empty-panel finding, C7 checklist L1–L10, the five items
  carried from C6 (K3, K5, J4, J5, **J6 on its fifth home**), C3 retro D1, and the six
  `deferred-work.md` entries homed here. -- `deferred-work.md:4924`: an inherited entry is declined
  by name rather than left unmentioned.
- **Brad** -- walk the app against `DESIGN.md` and `EXPERIENCE.md`, check every box, rule F1, M1–M3
  and the arrow-key revisit flag, and write the ruling line with its ISO date and any conditions.
  -- AC 1; cannot be delegated.
- `ui/src/styles/tokens.css` -- **only after M1–M3 are ruled**: add the accepted rows to the
  inventory at `:326-338`, each with its named fallback and owning story. -- UX-DR42's inventory is
  declared exhaustive; three shipped motions are currently outside it.
- `ui/tests/token-usage.test.ts` -- **only after M1–M3 are ruled**: extend the completeness guard so
  a shipped `opacity`/`height`/`background-color`/`box-shadow` transition must have an inventory
  row, with a non-vacuity anchor and a planted probe, in the idiom of `:2544-2650`. -- closes M5,
  the reason a green suite missed three motions.
- `_bmad-output/implementation-artifacts/deferred-work.md` -- append
  `## Dispositions from: the SC-5 gate (15-6, <date>)` with `### Actioned` / `### RE-ACCEPTED, with
  the reason recorded` / `### DECLINED, re-homed` sub-headings, one entry per inherited item.
  -- the emergent convention at `:480-502` / `:5736-5850`; do not modify existing entries in place
  except to add the dated `CLOSED …` annotation the file's own precedent uses.
- `…/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md:144` -- record the flag's
  disposition beside the existing `[DEFERRED 2026-07-25 — gate H3]` marker: either
  `[RE-ACCEPTED <date> — SC-5 gate]` with the reason, or the adoption decision. Mirror it into
  `validation-report-2026-07-25.md:131`. -- AC 4 requires the flag be *consciously* actioned or
  re-accepted, which means a written disposition, not silence.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` -- flip `15-6-the-sc-5-gate` with the
  gate date, the verdict and the report filename, **surgically**. -- `:329`: `sprint_plan.py generate`
  would destroy 67 inline comments and 8 gate keys.
- `docs/release-readiness-review.md` -- append a dated resolution-log section recording that SC-5
  closed (or did not) and under what conditions. -- the release-facing document is where a reader
  outside the pipeline looks; its own convention is append, never edit the original verdict.

**Acceptance Criteria:**

- Given the gate sheet is generated, when a reader opens it cold, then it names the run date, the
  baseline commit, every criterion, and every inherited item, and offers **no verdict**.
- Given the gate sheet is regenerated while a walk is in progress, when the file already contains a
  checked box, then generation refuses and exits non-zero rather than overwriting the human's work.
- Given Brad has walked the app, when every review-sheet box carries exactly one mark, then the
  report holds a blockquote ruling line with his name, an ISO date and any conditions, and states
  what the gate closes or blocks.
- Given the report records a verdict, when `sprint-status.yaml`, `deferred-work.md` and
  `EXPERIENCE.md:144` are read afterwards, then each carries the same disposition and date, and no
  inherited item in scope is left unmentioned.
- Given the reduced-motion deltas are ruled accepted, when `npm test` runs in `ui/`, then the
  extended completeness guard is green with the new rows present and reports RED when a row is
  removed (planted probe).
- Given the gate is not run to completion, when the epic is reviewed, then story 15.6 is not `done`
  and Epic 15 does not close — an open review sheet is the honest record, not a failure.

## Spec Change Log

## Review Triage Log

## Design Notes

**Why this run stops at the sheet.** SC-5 is reserved to Brad by three independent artefacts in the
same words, and this workflow is unattended. The project has already solved this exact shape once:
the pre-Epic-7 real-deck gate generated its report mechanically, left `## Review sheet (Sathias)`
unchecked, and closed only when the human filled it in. That precedent is what makes "the machine
builds the dossier, the human rules" a faithful reading of the story rather than a narrowing of it —
and it is also why the machine half must not creep into the ruling half.

**Why the gate should not run before 15.3–15.5.** Four criteria (footer, motion, anti-patterns, Tab
order) judge the *app*, which those three stories do not touch — so the dossier above is already
valid. But AC 1 judges the release, and 15.4 rewrites the README, 15.5 mirrors the SPA into the
plugin, and 15.3 amends the requirements the gate judges against. A verdict recorded now is a
verdict that has to be re-run, and a gate re-run is a gate whose date means nothing.

**The three hardest findings, stated plainly so they are not softened later.**
F1 is the only one that touches a *release condition*: NFR-08 says the attribution must be visible
on every surface, and there is a surface where it is behind a 75 % scrim. It is defensible — an open
modal is arguably not a surface — but it is a ruling, and it has never been made.
M1–M3 are the inventory's first real gap since UX-DR42 was written, and M5 explains why a fully
green suite did not see them: the guard reads `transform` and nothing else.
The Tab corridor is the one the epic itself flags, and its cost is known to the stop: 206 stops on
the largest deck, 101 still remaining after the only mitigation the app has.

**What "no verdict is offered" costs, and why it is still right.** It would be cheap to write
"the app looks deliberate" — every anti-pattern is clean, the token layer is disciplined, and the
evidence leans that way. It would also be exactly the thing UX-DR49 exists to prevent: a judgement
someone else recorded, which is the failure mode the story's own user story names in its first line.

## Verification

**Commands:**
- `uv run ruff check . --fix && uv run ruff format .` -- expected: clean (only if Python changes).
- `uv run python -m scripts.probe_harness --expect-green` -- expected: full suite green; paste the
  proof line into the record.
- `uv run python -m scripts.vitest_probe_harness --control` (warm — run one `npm test` first)
  then `… --expect-total N --expect-red '<the new completeness-guard node>'` after removing a
  planted inventory row -- expected: RED for that node and no other. Revert with
  `git diff --exit-code ui/src/styles/tokens.css`.
- `uv run python -m scripts.build_plugin && git status --porcelain -- plugin/` -- expected: empty.

**Manual checks (the gate itself — Brad):**
- Open the app on a real deck and read it as a product, against `DESIGN.md` and `EXPERIENCE.md`.
- Open an agent view and look at the footer. That is finding F1, and it needs a word from you.
- Turn reduced motion on and hover a double-faced card's flip control, then a suggestion row.
  Those are M1 and M2.
- Tab from the header to the Fan Content Policy link on the biggest deck you own, and again after
  using the skip link. That is the number this gate is being asked to re-accept.
- Walk C7 checklist L1–L10 and the five items carried from C6; J6 is on its fifth home and deserves
  a decision rather than a sixth.


## Auto Run Result

Status: blocked
Blocking condition: **the SC-5 judgement cannot be produced unattended, and the story's
prerequisites have not started.** Both arms of the spec's own `Block If` fired before implementation.

**Run:** `bmad-build-auto`, 2026-08-20, baseline `58372f9` on `claude/hello-7v0acf` (clean tree, one
commit ahead of `feat/companion-epic-15`). Planning completed; step-03 was not entered.

**Why blocked — arm 1, the judgement.** Story 15.6's first acceptance criterion reads *"this
judgement is human, performed by Brad, and cannot be automated or delegated."* Three independent
artefacts say it in the same words — `epics-companion-app.md:726-730` (UX-DR49),
`architecture/…/EPIC-SPLIT.md:121`, `sprint-status.yaml:716` — and `c4-12-…md:1564` already declined
to answer it on exactly this ground. An unattended run that recorded a verdict would be producing
the artefact UX-DR49 exists to prevent.

**Why blocked — arm 2, the prerequisites.** `sprint-status.yaml:720-723` has 15.3, 15.4 and 15.5 at
`backlog`, with no spec or partial artefact on disk for any of them; `:327` records *"Next
recommended story is 15-3."* `epic-15-context.md:111-115` orders 15.6 last because it judges what
those three finish documenting and packaging. A verdict recorded before 15.4 rewrites the README and
15.5 mirrors the SPA into the plugin is a verdict that has to be re-run.

**READY FOR DEVELOPMENT verdict:** fails **Sufficient** — a known acceptance gap (the verdict) and a
known dependency gap (15.3–15.5) remain unresolved, and neither is resolvable by this workflow. The
other six criteria pass: the spec is actionable, dependency-ordered, Given/When/Then throughout,
anchored on the shipped app and the recorded gate document, free of placeholders, and internally
consistent.

**What this run did deliver.** The gate's audit is done, so the human half is all that remains. Three
parallel investigations were run against the shipped app at `58372f9` and drained into the Code Map:

- **AC 2 (anti-patterns) — all six clean, with evidence.** Zero `JSON.stringify` in shipped `ui/src`;
  no log component and no `console.*` in `src`; exactly one `<table>` in the SPA, and it is the
  `visually-hidden` a11y alternative to the mana-curve chart; no router, no `ErrorBoundary` and no
  error route — every failure is a calm `StatePanel` chosen by reason token; **no toast, snackbar or
  queue exists at all**; the semantic colour layer is three desaturated tokens never used as a fill
  and never without an accompanying word, with `--negative`/`--caution` in the state panel a
  build-breaking gate. Two caveats worth an eye: `caution` is furniture rather than a signal on ~100 %
  of real decks (`FormatCheck.tsx:162-165`), and the legal notice renders 10px ALL-CAPS.
- **AC 5 (reduced motion) — three real deltas the green suite could not see.** The flip-control
  chrome fade (`FlipControl.css:98`), the suggestion-row live tint
  (`SuggestionsView.css:119-121`) and the suggestion thumbnail fade (`:211`) ship without an
  inventory row; inventory row 10 is a prohibition with no subject; and the mechanical reason is
  `token-usage.test.ts:2544-2605`, whose pin covers `transform`/`scale`/`rotate`/`translate` only and
  is blind by construction to `opacity`, `height`, `background-color` and `box-shadow` — the exact
  class all three fall into. Nothing pulses or loops: zero `@keyframes` and zero `animation:` across
  all 32 stylesheets, double-guarded by stylelint and by `findLoopingAnimation`.
- **AC 6 (footer) — one finding that touches a release condition.** `.app-shell-overlay` is
  `position: fixed; inset: var(--space-gutter)` (`AppShell.css:282-286`) — the same box as
  `.app-shell`'s own padding box (`:65-72`) — and `.agent-view-scrim` fills it with a 75 % scrim plus
  a 16 px blur. **While an agent view is open, the attribution NFR-08 requires on every surface sits
  behind that scrim.** `App.tsx:170-174` claims the footer "survives it by construction": structurally
  true, visually not, and no test can see it because jsdom paints nothing. Secondary: the connection
  pill overlaps the wrapped attribution below 1100 px, mitigated (not fixed) by `min-width: 1100px`.
- **AC 4 (Tab order) — the flag has no ledger row.** `grep '\barrow'` over `deferred-work.md` returns
  zero hits; the deferral lives only at `EXPERIENCE.md:144` as `[DEFERRED 2026-07-25 — gate H3]` with
  a bolded *"Revisit before public release"*. The consequence is verified and pinned:
  `App.test.tsx:1795-1830` holds 209 focusables, **206 stops** header → first footer link, **101 still
  remaining** after the skip link. Actioning it is not a component change — a roving-tabindex grid is
  an ESLint error today (`eslint.config.js:17-24`).
- **AC 7 (the record) — the precedent is transplantable.**
  `pre-epic-7-real-deck-gate-report-2026-07-17.md` is this project's own worked example of a *human*
  gate run mechanically: a dated metadata block, per-item detail, an unchecked
  `## Review sheet (Sathias)`, a `> Gate ruling (<name>, <ISO date>)` blockquote, and a `- [x]`
  sentinel that refuses to clobber a walk in progress. The Tasks section transplants that shape.
- **The gate's inbox is enumerated** — c4-12's five still-open conformance items and its UX-DR20
  empty-panel eye-check finding, the unrun C7 checklist L1–L10, the five items carried from C6
  (K3, K5, J4, J5, and **J6 on its fifth home**), C3 retro D1, and six `deferred-work.md` entries
  homed at 15-6.

**To unblock:** land 15.3, 15.4 and 15.5, then generate the gate sheet from this spec and hand it to
Brad. No verdict is offered here, by design.

---

## Resumption 2026-08-20 — both arms unblocked; gate RUN and CLOSED. Status: done

Both Block-If arms dissolved after the 2026-08-20 planning run: 15.3/15.4/15.5 all merged
(PRs #87/#88/#89), and the human judgement arrived — Brad walked the live app the same day
(`sc-5-preliminary-ruling-2026-08-20.md`) and then ruled the four open forks interactively.
Executed per Tasks, on umbrella `feat/companion-epic-15`:

- **Gate sheet**: `sc-5-gate-report-2026-08-20.md` on the pre-Epic-7 skeleton — metadata block,
  summary table, findings with anchors, inherited inbox, standing caveats, not-blockers, review
  sheet. All seven boxes marked from Brad's walk + interactive rulings (transcribed, not
  inferred); the blockquote ruling line carries his name and the date. **SC-5 CLOSED; the 0.5.0
  release cut unblocked.**
- **Rulings**: F1 = an open modal is not a surface (written into `EXPERIENCE.md` +
  `DESIGN.md`); arrow-key flag RE-ACCEPTED (`EXPERIENCE.md:144` + `validation-report` H3
  mirrored); M1 row added to the tokens.css inventory; M2/M3 accepted on their recorded rulings,
  the two rows now read as classes (noted at the registration point); M4 recorded
  satisfied-by-absence.
- **M5 guard**: `token-usage.test.ts` "keys every visual-class transition to an inventory row" —
  opacity/height/background-color/box-shadow + `all`, paren-aware segment reader, 13-entry
  enumerated claims map, non-vacuity anchor, inline probes (unclaimed transition, `all`
  smuggling, var-comma, out-of-class invisibility). Suite 2305 → 2307.
- **Firing proof** (committed harness): control `vitest: 80 files / 2307 tests, 0 failed` →
  planted (M1 row removed) `RED |node| tests/token-usage.test.ts > … > keys every visual-class
  transition to an inventory row (SC-5 gate, M5)` at `--expect-total 2307` (first planted run
  refused on the known worker-fork crash signature; clean on re-run) → revert
  `git diff --exit-code` clean.
- **Ledger**: `deferred-work.md` §"Dispositions from: the SC-5 gate (15-6, 2026-08-20)" — every
  inherited item by name (Actioned / RE-ACCEPTED / DECLINED); J6 DECLINED on its fifth home; D1
  refused, stays unowned. `sprint-status.yaml` 15-6 → done, surgically.
  `docs/release-readiness-review.md` resolution log appended.
