# Epic C6 Retrospective — The Agent Pushes to the Glass

**Date:** 2026-08-13
**Facilitator:** Amelia (Developer) · **Participants:** Brad (Project Lead), Mary (Analyst), John (PM), Sally (UX), Winston (Architect), Paige (Tech Writer)
**Scope:** Stories c6-1 … c6-9, merged into `feat/companion-c6` via PRs #63–#71 (2026-08-09 → 2026-08-12)
**Mode note:** Brad delegated the docket ("delegated"); every ruling below was adopted on its recommended disposition and is **overridable until the integration PR merges** (the C5 precedent).

---

## 1. Epic summary and metrics

| Metric | Value |
|---|---|
| Stories completed | **9/9 (100%)** — none reopened, no scope dropped |
| Branch vs master | 28 commits · **106 files · +20,247 / −350** |
| Python tests | 2,770 → **2,921** (+151); 1 skipped / 55 deselected unchanged |
| Frontend tests | 1,868 → **2,123** (+255); 69 → 75 files · design tokens 69 → 70 |
| Diff composition (git, per the C4 practice) | tests ~7.4k added (4.9k frontend · 2.5k Python) · src ~4.2k (3.2k frontend · 1.0k Python) · story-docs ~7.2k · plugin mirror ~1.0k. Test:src ≈ **1.8:1** |
| Reviews | **9/9 same-day three-layer reviews** before every PR; 26 patches · 27 defers · 63 dismissals; no in-layer finding labelled High |
| Pre-code rulings | **53 open questions, 53 ruled as-recommended, all before code** — a clean sweep, zero overrides, across all nine stories |
| Greptile | 3 real post-merge catches (c6-2's 4-branch echo gap; c6-7's null-item dialog crash + settle-to-unknown race / 0-height collapse) — then **three 5/5-zero stories** (c6-4, c6-8, c6-9); c6-8 was the first Auditor-zero AND Greptile-zero on one story |
| Planted reds | ~20+ plants, all hand-run (R5 harness unbuilt), all reverted-verified; the greens were again the payoff: c6-6's live-region hole, c6-7's absence-only vacuity, c6-8's disproved blast-radius prediction |
| Dev Notes (R1 measure) | 13.4–20.8 KB per story; only c6-7 marginally over the 10–20 KB band (story-creation artefact, left as authored) |
| Tracked intermittents | `lintBothFixtures` cold-start timeout (**5 sightings**: c6-2/3/5/8/9); vitest worker-fork silent file drop (**2 sightings**, c6-5, ledgered); `test_list_decks_with_strategy_field` (**3rd sighting** at c6-7, root-caused: same-microsecond `created_at` ordering) |
| Business outcome | **SC-1 and SC-3 CLOSED.** Push budget observed: **15/21/36 ms warm-art (n=5)** vs 250 ms — ~12× headroom; 26/28/50 ms at the 60-item cap; literal SC-1 reading negative (−2/−1/−1 ms — broadcast completes inside the route). Token cost measured: ~30 tokens ordinary success, ~92 worst case, zero payload echo |
| Deployment | Merge ≠ release; integration PR `feat/companion-c6` → master **not yet raised** (no Greptile on it, standing rule); nothing tags until c8-4 |

---

## 2. What went well

1. **The pre-code ruling protocol reached steady state.** 53/53 questions ruled as-recommended before any code, every story, zero overrides. The one ruling whose *rationale* was later disproved — c6-9 Q2's claim that a post-POST clock stamp is conservative (it flatters) — was disproved by measurement and corrected in the open with a bracket clock that over-states instead.
2. **"Measured contradiction" emerged as a named artefact type** (c6-8, adopted verbatim by c6-9): a story-spec claim about a byte, a mechanism, or a blast radius is a *prediction*, and the dev records what measurement said. Six were caught across the two stories, including a wrong load-bearing byte (the tooltip apostrophe is ASCII, not U+2019 — a gate written to the claim would have pinned the wrong character and agreed with itself forever) and a defect in the measuring instrument itself (the Tab-corridor helper matched disabled buttons; the honest fix left the pins *unchanged*).
3. **The non-vacuity discipline compounded story over story.** c6-6's plant 2 exposed that the live-region announcement had no plant of its own → a byte-identical-title test was added in-story; c6-7's plant 3 found an absence-only assert that a completely unwired row would satisfy → standing practice coined: **"absence-only asserts get their positive twin"**; c6-8 designed its plants around it and c6-9 built the `images_painted` positive control for the same reason (without it, a stone-cold cache read as perfectly warm off an empty timing buffer).
4. **Review quality visibly converged.** c6-7 took 8 patches plus two Greptile P1s; c6-8 and c6-9 took one patch each, with the Acceptance Auditor independently re-running every gate and reproducing every Dev Agent Record claim, and Greptile at 5/5 zero on both.
5. **SC-1/SC-3 closed with honest instruments.** Bracket clock reporting the conservative end; breach protocol (stop-and-diagnose, no tuning before a ruling) never triggered — no arm came near the budget; a failed push now says *why* (the review's one c6-9 patch); the absent-discovery-file precondition is asserted so the harness cannot silently measure a live companion.
6. **The c6-2 Greptile lesson operationalised, not just quoted** ("a finding cites one line; grep the whole pattern"): applied preventively at c6-4 (sentinel-absence on all five branches), structurally at c6-5 (the residual trap-escape *filed* rather than silently left), and at c6-3's request-log sweep design.
7. **Scope discipline held under pressure.** Structural AC deferral became a named device (c6-5 Q7 → c6-7; c6-6 AC 3 → c6-7, AC 6 halves → c6-8); c6-3 observed-but-refused-to-legislate c7-4's transition behaviour and deleted its throwaway probe; c6-7 Q6's coalescing close kept that story frontend-only; nothing pre-built a future story.
8. **The F1 inversion:** after c6-8, the rendered story-key count on the glass is **zero for the first time since c2-6** — the F1 gate's live survivor is gone before the gate (c8-5) exists.
9. **Ledger honesty continued self-correcting:** entries closed with what they got wrong recorded (dw:10's predicted reuse that didn't happen); a four-times-carried entry deliberately closed as "not wanted" (image coalescing, c6-7 Q6); c6-9 filed **zero** new entries.

## 3. Where we struggled

1. **Greptile kept catching what three layers missed — until late-epic.** c6-2's echo fix covered one branch of four; c6-7's exhaustive malformed-item fixtures never included a bare `null` element, and all three layers plus the fixtures missed the settle-to-unknown race and the 0-height collapse. Same shape both times: *guard the container, not just its fields* — and per-field degradation must never degrade **reachability** (c6-8's one patch: an absent `ts` made a retained push permanently unreachable via its pill, a real UX-DR34 violation). The lesson demonstrably took (three Greptile zeros to close the epic), but it cost two post-merge P1 rounds.
2. **Zero eyes on pixels — the epic's largest accumulated debt.** Block J's carry rationale ("C6's own stories put real eyes on most of these surfaces") **did not hold**: c6-3 was ruled tests-only, c6-9 measured DOM timestamps in headless Chrome. Nobody has seen the agent view shell, the crossfade, the suggestion rows, the header pills, the empty-push line, or heard a single announcement. c6-7's own ledger entry: *"this is the app's first surface whose pixels nobody has seen"*; c6-8 extended it to a permanently-visible surface. → R1.
3. **Prose honesty was the single largest review-patch category** — overclaiming docstrings (c6-1 ×2, including a false claim of R2 compliance), stale docstrings after a wire change (c6-2), self-contradicting `Returns:` clauses (c6-4), comments citing recovery mechanisms that don't exist (c6-7 P6), wrong artefact citations shipped unpinned (c6-7 P3/P4). The ripple sweep under-predicted its site count **seven consecutive stories** (7 vs 3, 41 vs ~28, 47 vs ~45 …) before c6-9 finally landed on target.
4. **Flake accumulation cost real baseline runs.** `lintBothFixtures` cold-start timeout: five stories paid a red baseline + warm re-run (~11–20× setup difference on identical code). The worker-fork crash silently dropped a whole test file twice — the exact class R5's collected-count validation exists to automate, caught only by manual discipline. → R2, R5.
5. **One real process error:** c6-7's unstaged `git checkout` revert deleted the entire component mid-story (rewritten from context). Rule coined on the spot: **"stage before you plant"** — same hazard class as the pre-commit stash landmine, through a different door. → R8 (standing).

## 4. C5 retro follow-through (11 items)

**4 completed · 1 declined-in-retro (R3) · 6 open at this retro** — of which two hit their termination clauses today.

| # | Item | Verdict |
|---|---|---|
| R1 | Windows CI lane | ✅ Shipped to master pre-C6 (PR #62), green all epic |
| R1-a | Firing proof (lane never seen red) | ❌ Not run → **termination clause EXECUTED** (§5 D1) |
| R1-b | Branch protection required check | ❌ Not done → carried as C6 R6 |
| R2 | Prose-sync sweep (standalone) | ⚠️ Standing rule held (one c6-1 violation, patched, then 8 clean); the sweep itself never executed → carried as C6 R7 with termination clause |
| R3 | Class→token guard | ➖ Formally declined at the C5 retro itself (built-and-reverted); its named hole (jsdom sees no stylesheet) is part of what R1's checklist covers |
| R4 | Flake + marker | ⚠️ Premise-corrected, not actioned — and the flake hit its **third sighting** (c6-7), which R4's own terms escalate; c6-7 also root-caused it → split into C6 R3 (fix) + R4 (marker) |
| R5 | Vitest probe harness | ❌ Its home ("before Epic 6's first frontend story") was passed **by explicit ruling twice** (c6-3 Q3, c6-5 Q6); cost measured: ~20+ hand-run plants, 2 silent file drops → re-keyed as C6 R2 with termination clause |
| R6 | DESIGN.md citation guard | ❌ Third epic, never referenced → **termination clause EXECUTED** (§5 D2) |
| R7 | Plugin-mirror check from `ui/` | ❌ Not built — but C6 produced **zero escapes** of the class (9/9 stories sha256-clean under the rebuild-after-last-edit rule) → formally declined (§5 D5) |
| R8 | Review-added assertions re-enter review | ✅ Held as standing practice through C6 → closed as adopted |
| R9 / R10 / R11 | UX-DR46 split · AD-1 ruling · Block J carry | ✅ All executed at/after the C5 retro as recorded |

## 5. Docket rulings (delegated; recorded here and in `sprint-status.yaml`; each overridable until the integration PR merges)

| D | Item | Ruling |
|---|---|---|
| D1 | **R1-a termination clause** | **DECLINE, execute the clause.** The lane's claim is downgraded from "covers the process boundary" to "runs the process-boundary test." Annotation: any future *genuine* red on the lane retroactively supplies the firing proof — record the run URL and upgrade the claim then. |
| D2 | **R6 termination clause** | **DECLINE, execute the clause.** The guard is demoted to a **declared string-proximity check**. Evidence cut both ways (c6-7's P3 was a wrong citation value a resolving guard would catch; its P4 — a missing citation — no guard of this shape would see), but three epics of carry is the drift the clause exists to stop. The demotion edit (one declaration comment in the guard) is C6 R10. |
| D3 | **R4 escalation** | The third sighting occurred **with a root cause in hand** (c6-7: same-microsecond `created_at` ordering under ties). The escalated "investigation" is therefore a deterministic ordering tiebreaker — C6 R3. The marker/alias half survives on its corrected premise (a bare `-m integration` sweeps live-Scryfall + real-fastembed tests, not the flake) — C6 R4. |
| D4 | **R5 build-or-decline** | **BUILD as C7 prep** (C6 R2). Value case, measured not guessed: ~20+ plants hand-run across C6's six frontend stories; the worker-fork flake silently dropped a test file **twice** — the exact failure class the harness's validated-collected-count and crash-signature refusal automate; C7 has five frontend-heavy stories coming. Scope fixed at the four recorded requirements; **termination clause**: not built by the C7 retro → formally decline and stop citing it. |
| D5 | **R7 third carry** | **FORMALLY DECLINE** (the R3 precedent: a decline is better than a silent carry). The mirror remains guarded three ways (Python byte-for-byte test, CI drift check, the rebuild-after-last-edit standing rule + per-story sha256 verification, 9/9 clean this epic). **Reopen trigger:** any new escape of this defect class. |
| D6 | **R1-b** | **DO** — carried as C6 R6, executed with the integration PR (a two-minute GitHub settings change; completes R1's stated purpose). |
| D7 | **C5 R2 sweep** | Carried as C6 R7, standalone, scope unchanged (~6 named sites); **termination clause** at the C7 retro. |
| D8 | **C5 R8** | **CLOSED as adopted** — held through C6 without incident. |
| D9 | **Block J + C6 surfaces** | **RUN the Epic C6 manual-testing checklist (§8) BEFORE the integration PR** — C6 R1. The C1/C2 precedent (run-before-integration caught the COMPANION_PORT rename while it was free) over the C5 precedent (carry — whose absorption premise failed). Running it also spares J6 a fourth explicit carry ruling. |
| D10 | **`lintBothFixtures` flake** | Fix by raising that one test's timeout for the cold eslint shellout (one line) — C6 R5. Five sightings is a pattern; the fix is minutes. |
| D11 | **UX-DR35 pin eviction** | The c6-7 Q7 boundary note needs a ruling **before c7-3/c7-4 context**: as written, a `deck_changed` refetch would evict every pinned suggestion — C6 R9. |
| D12 | **Standing agreements** | Adopted (C6 R8, done in-retro): **stage before you plant**; **absence-only asserts get their positive twin**; **measured-contradiction recording** (story-spec claims about bytes/mechanisms/blast radii are predictions — record what measurement said). |

## 6. Named, not actioned

- **The screen-reader run-on phrase** in suggestion rows (badge/name/cost/confidence as one unpunctuated stream) — deferred at c6-7 as needing UX judgement, not a mechanical fix; it gets that judgement live at checklist item K5 before any code is proposed.
- **The ~26-entry `unowned` `src/logic`/`src/data` ledger cluster** — unchanged since the C5 retro named it; still no companion owner, still deliberately off the prep list.
- **Story 8.3's artefact reconciliations** (UX-DR28 "tooltip" wording vs the shipped name/description mechanism; the AD-6 spine text) — homed, not due yet.
- **c6-9's five pre-existing harness defers** (function-local import blind spot in the app-side guard, file-granularity allow-list, `decks[0]` ordering, `--card-ids` warm-arm footgun, point-sampled warmth) — ledgered, none touch the recorded figures, Phase-2 adjacent (10.3).

## 7. Epic C7 readiness

**No epic-invalidating discovery. C7's plan is sound as written.** C6 pre-cut its seams deliberately: c6-3 left `connection.ts`'s `kind` parameter unread as c7-3's seam and refused the kind branch; the no-teardown switch behaviour was observed and *not* legislated so c7-4 owns it; the notifier (7.1) lives in the leaf beside c6-1's client and inherits its whole discipline (closed vocabulary, never-raises, bounded awaits); c7-2's after-commit emission rule is already spelled in the epic header.

**One decision owed before c7-3/c7-4 context:** UX-DR35's pin-eviction question (C6 R9 — the c6-7 Q7 boundary note; AC 2's Esc/pin test is the recorded tripwire, and the review corrected that citation to name the real mechanism).

**Critical path before c7-1:**
1. **Run the C6 manual-testing checklist** (§8) — R1.
2. **Integration PR `feat/companion-c6` → master** — no Greptile, per the standing rule; R6 (branch protection) executed alongside.
3. C7 prep: R2 (vitest harness), R3 (flake fix), R4 (marker), R5 (timeout), R7 (prose sweep), R10 (guard demotion edit).
4. R9 (UX-DR35) before c7-3 story context.

## 8. Epic C6 manual-testing checklist

Derived from what every C6 test deliberately isolated away (jsdom without stylesheets/layout/sequential focus, `FakeSocket` transports, headless timing harnesses, no screen reader) plus Block J carried wholesale from C5 (R11). **J6 is on its fourth home; running it here closes that chain.** Recommended run: before the integration PR (D9).

| # | Item | What no automated test can see |
|---|---|---|
| J1 | Full reconnect walk: kill backend → pill walks Connected → Reconnecting → Backend gone → restart → recovers with no refresh | The whole loop ran on fake timers and injected sockets |
| J2 | Two tabs open, ask the agent to switch decks (`companion_set_active_deck`) — both tabs follow | Broadcast fan-out proven in-process + one real socket; never two real browsers. c6-3's tests cover one jsdom instance |
| J3 | Pill colours by eye: green / amber / red per state | The P15 class — jsdom evaluates no stylesheet; R3 declined |
| J4 | Sub-1100 px window: horizontal scroll at the floor; pill never covers the footer | Verified once in headless Chrome (c5-7), never by hand |
| J5 | Dev proxy: `npm run dev`, WS connects through Vite from a real browser | `devProxyRoundTrip` drives node `http.request`, not a browser |
| J6 | `internal-error` first render by a real engine | Carried Block I → C5 → C6 → **here**; the last state panel never seen live |
| J7 | Exhaustion announcement: block backend past both gates (60 s AND 4 failures) → disconnected panel displaces; announcement on transition only | Live region + timing composed from fakes end to end |
| J8 | Ticket TTL at the backoff ceiling: disconnected past 30 s intervals → reconnect still succeeds | `FakeClock` made TTL tests zero-wall-clock; the 30 s / 30 s collision designed around, never observed |
| K1 | The push loop by eye: ask for suggestions → view blooms open (480 ms rise on complete layout); repeat push → 240 ms crossfade, heading + count update; under `prefers-reduced-motion` both are instant | Bloom/crossfade are attribute-driven CSS jsdom never evaluates; c6-9 measured layout timing, not presentation |
| K2 | The shell composed: 16 px backdrop blur, 32 px inset, raise elevation, kicker, close pill — does it *look* right | dw:1457's own words: "shell guards are static readers — check the composed result." Nobody has |
| K3 | Real-Tab focus walk: trap cycles inside the view; Esc / close pill / scrim-click dismiss; focus returns to the invoking element (never `body`); open moves focus to the heading | jsdom has no sequential focus navigation — trap tests assert the handler's logic, not browser tabbing |
| K4 | Header pills: quiet pill's tooltip on hover (**watch whether Chromium shows `title` on a disabled button** — a ledgered risk that would leave only the SR half working), unread dot, re-open with same content, timestamp renders local time | jsdom renders no tooltips; the disabled-`title` behaviour is browser-specific and undocumented in the suite |
| K5 | Screen-reader pass (Narrator/NVDA): repeat push announces **once even when the title is byte-identical** (the keyed-Fragment mechanism); judge the suggestion row's run-on phrase severity (c6-7 defer — Sally's call); empty-push line reads sensibly | The announcement's audible half is jsdom-unverifiable by name (c6-6 Q4); the run-on needs human judgement, not a fix |
| K6 | The empty-push state seen once — including judging the ungrammatical residue ("an empty suggestions") live | The gate compares bytes, and the bytes are right; only eyes can judge the sentence |
| K7 | Row art states: warm art paints; unknown card id → placeholder **with reason text still shown**; pin a row, Esc — the card stays in the detail panel | Image loads don't happen in jsdom; art-state tests drive `onLoad`/`onError` by hand |
| — | *Not testable until Epic 9:* kind-switch displacement / the unread-marker setter (only `suggestions` can arrive in Phase 1) | Proven at the store seam with a synthetic second kind; production path structurally unreachable |

## 9. Key takeaways

1. **A story-spec claim is a prediction** — the epic's dominant lesson, now standing practice: measure the byte, the mechanism, the blast radius, and record what measurement said. It caught the clock error that ran the wrong way, the wrong apostrophe, and a defective measuring instrument that had agreed with the app by accident for four epics.
2. **Guard the container, not just its fields — and never let per-field degradation degrade reachability.** The class escalated one layer per story (field → item → kind key) and cost two post-merge Greptile rounds before the discipline landed three consecutive zeros.
3. **Absorption premises need verification.** Block J was carried on "C6's stories will put eyes on these surfaces"; the stories were ruled tests-only or harness-driven, and the premise failed silently. A carry rationale is itself a claim — check it at the retro it lands on.
4. **Termination clauses worked exactly as designed.** R1-a and R6 each got a real decision today instead of a third silent carry; R7's decline is evidence-based (zero escapes under the manual discipline); R5's re-key carries its own clause so C7's retro inherits a decision, not a drift.

## 10. Commitments

**10 action items (R1–R10)** appended to `sprint-status.yaml` under `action_items` (epic c6). C5 items closed: R1-a **declined** (clause executed, claim downgraded), R6 **declined** (clause executed, demotion = C6 R10), R7 **declined** (reopen trigger recorded), R8 closed as adopted, R2/R4/R5 closed as **re-keyed** into C6 R7/R3+R4/R2, R1-b re-keyed into C6 R6. Retrospective key `epic-c6-retrospective` → done. `epic-c6` → done.

**Next steps, in order:**
1. **Run the C6 manual-testing checklist (§8)** — R1, before the integration PR.
2. **Integration PR `feat/companion-c6` → master** (no Greptile, standing rule); execute R6 (branch protection) alongside.
3. C7 prep: R2 (vitest harness, termination-claused), R3 (flake tiebreaker), R4 (marker), R5 (timeout raise), R7 (prose sweep, termination-claused), R10 (guard demotion edit).
4. **R9 (UX-DR35 pin eviction) before c7-3 story context**, then begin c7-1.
