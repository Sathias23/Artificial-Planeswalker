# Epic C5 Retrospective — The Agent's Channel

**Date:** 2026-08-09
**Facilitator:** Amelia (Developer) · **Participants:** Brad (Project Lead), Mary (Analyst), John (PM), Sally (UX), Winston (Architect), Paige (Tech Writer)
**Scope:** Stories c5-1 … c5-8, merged into `feat/companion-c5` via PRs #53–#60 (2026-08-07 → 2026-08-09)
**Mode note:** Brad delegated the docket ("continue"); every ruling below was adopted on its recommended disposition and is **overridable until the integration PR merges**.

---

## 1. Epic summary and metrics

| Metric | Value |
|---|---|
| Stories completed | **8/8 (100%)** — none reopened, no scope dropped |
| Branch vs master | 32 commits · **106 files · +25,106 / −511** |
| Python tests | 2,502 → **2,824** unfiltered (+322); filtered 2,770 passed / 1 skipped, **byte-stable across the last four stories**; c5-8 moved only `deselected 54 → 55` |
| Frontend tests | 1,694 → **1,868** (+174); 65 → 69 files |
| Diff composition (git, per the C4 practice) | tests ~8.7k added · src ~6.6k · story-docs ~6.7k · plugin mirror ~3.1k. Extremes: c5-5 largest src story (~2.0k); **c5-8 = 11 src lines / 551 test lines** |
| Reviews | **8/8 same-day three-layer reviews** before every PR; two chunked variants (c5-6 Groups 1/2/3, c5-7 Groups A/B/C) when the diff outgrew one pass; c5-1 needed two full rounds |
| Pre-code rulings | **60 open questions, all ruled before code**; 53 as-recommended; the last four stories were clean as-recommended sweeps |
| Falsification probes | ~90 planted violations, all run through FULL suites; **4 probes came back GREEN and each exposed a real hole** |
| Escapes past local review | c5-6 CI bundle-drift; c5-7 Greptile P1 (footer clearance, verified in a real browser); c5-8 Greptile P1/P2 |
| Dev Notes (R1 measure) | **10.4–20.5 KB per story vs C4's 41 KB average** — every measured story under half |
| Tracked intermittents | 2 — `test_list_decks_with_strategy_field` (sightings at c5-5, c5-6) and the vitest single-file collection loss (c5-6, twice, then 26 clean runs) |
| Business outcome | C5 closes no SC directly by design — the enabling epic. The authenticated agent→glass pipe exists, reconnects itself, and has one real-process proof (`1 passed in 5.09s` on Windows). C6 spends it to close SC-1/SC-3 |
| Deployment | Merge ≠ release; integration PR to master **not yet raised**; nothing tags until c8-4 |

---

## 2. What went well

1. **Contract-first paid out completely.** c5-1 froze all four payload kinds plus the two system signals before any consumer existed; five consecutive stories shipped against `contracts.py` with **zero contract changes**. This is also why Epic 9 stays cheap (AD-6's stated bet, now evidenced).
2. **R1 trigger-gated inheritance is proven, not promised.** Adopted at the C4 retro on a measurement with no worked example; C4's stated risk (c5-1 as heaviest story) did not materialise (20.5 KB). Range 10.4–20.5 KB vs 41 KB baseline, largest frontend story at ~14.5 KB — and verification did not thin: +496 tests across the epic.
3. **The probe discipline (R2) became the epic's best bug-finder — via its greens.** ~90 planted reds proved the guards; the four greens changed the product: c5-5's refusal-body test passed under the exact planted failure it existed to catch ("the test claiming to prove it was decorative"); c5-5's delivered-vs-connected discriminator did not discriminate (closed structurally with an AST guard); c5-4's register-before-accept guard couldn't tell "registers after accept" from "refuses early"; **c5-7's P15** — dot pointed at the wrong colour token — sailed past 1,866 green tests because jsdom evaluates no stylesheet.
4. **c5-8's F5** proved the restart case non-vacuous: without the `replacing=` guard the wait returned the **corpse's** discovery record (same instance_id, same port). The pytest probe harness (built c5-1) also caught a `SyntaxError` plant masquerading as "0 failed" — only the collected count (1,450 vs 2,526) revealed the suite never ran; that check is now in the harness.
5. **No-lock concurrency by construction.** `TicketStore.consume` as one synchronous `dict.pop` with its three named breakers written down, then **enforced by the language** at c5-3 (a plain `def` cannot contain an `await`); copied wholesale by `ConnectionRegistry`.
6. **The pre-code ruling protocol matured.** 60/60 ruled before code; deviations from epic ACs handled in daylight (c5-5 Q7 ruled the literal 413-for-everything AC down to byte-cap-only, flagged loudly per precedent). Story prep now reliably produces decisions rather than puzzles.
7. **The pill resolved a three-artefact standoff** (UX-DR40 / c10-1 / DESIGN.md were never in conflict — two describe Tab order, one describes the screen); voice reading discharged explicitly; typography split protected deck names from uppercasing with DESIGN.md amended same-commit.
8. **Ledger honesty is self-correcting.** Two of the ledger's own proposed fix shapes were falsified by measurement (c5-6's ordering-pin red that never came; c5-8's `port: 0` Vite fix — "the file's own original comment was right and the ledger's suggested fix was wrong") and recorded rather than worked around.

## 3. Where we struggled

1. **The plugin mirror is the epic's most-repeated failure mode — and it was a known open action item.** c5-1 shipped a sha256-match claim the diff contradicted (all three review layers caught it independently; cost a second full review round); c5-6's SPA bundle drift got past local review and was caught by CI post-push. C4 item 7 (mirror check reachable from `ui/`) was scoped to C5, never built, and predicted exactly this. **Second epic running for this defect class.** → R7.
2. **Shipped forward-looking prose is systematically wrong.** Every story corrected falsified predictions in shipped docstrings; c5-2 corrected three and added new forward-looking prose in the same breath; c5-7's prose *fix* introduced a second inaccurate claim. The Q3/AD-5 ruling is narrated in 5+ locations with no consistency guard. → R2 + standing rule.
3. **AC text drifted from rulings twice** (c5-7 AC 6 vs Q3; c5-8 AC 12 vs the shipped fix) — both caught by review, not by the dev; and the same class of drift sat live in C6's path (story 6.4's stale 422, amended in-retro).
4. **The ledger's source is still unreduced.** 458 top-level entries, ~338 without closure markers; C5 closed/paid ~20 with written reasons, but the ~26-entry `unowned` `src/logic`/`src/data` cluster (c3 era) has no legitimate companion owner and no agenda. Named, not actioned (see §6).
5. **Manual-checklist residue has homes but no evidence of runs.** Block I's leftover (`internal-error` first render) rode to "the C5 checklist"; story files show homing, not execution. → Block J (§8) before the integration PR.

## 4. C4 retro follow-through (13 items)

**8 completed · 2 partial · 3 not addressed** — on par with C4's own rate vs C3.

| # | Item | Verdict |
|---|---|---|
| 1 | R1 trigger-gated inheritance | ✅ Success criterion met on every measured story (no KB self-check found in c5-5/c5-8 — minor) |
| 2 | R2 firing proofs | ✅ Enforced as an AC in all 8; no review found a vacuous assertion in a story's own new guard |
| 3 | R3 ledger F4 → c8-4 | ✅ Done in-retro at C4 |
| 4 | Committed probe harness | ⚠️ Python half shipped (c5-1) and used by every story; **vitest half still owed** → re-homed R5 |
| 5 | DESIGN.md citation guard | ❌ The one item C5 never referenced — while adding new citations against the blind guard → re-homed R6 with termination clause |
| 6 | Grep-your-own-key in Task 0 | ✅ 7 of 8 stories (no section found in c5-5) |
| 7 | Plugin-mirror check from `ui/` | ❌ Not built; produced exactly the predicted failure (c5-6 CI drift) → re-homed R7 |
| 8 | R5 four ledger closures | ✅ Done in-retro at C4 |
| 9 | Block I | ✅ Run at C4 retro; residue homed to C5 checklist (execution owed → Block J) |
| 10 | `.gitignore` sync | ✅ Done (`319a966`) |
| 11 | F1 story-key gate | ➖ Correctly deferred to c8-5; note: **c5-7 added a container rendering on every surface**, widening what the gate must scan |
| 12 | Same-day three-layer review | ✅ 8 for 8; chunked variant ratified below as a process evolution |
| 13 | Review-added mechanisms re-enter review | ⚠️ Held 7 of 8; c5-8's Greptile P2 was in a review-added **test assertion** — ruled not a violation of the rule as written; rule amended going forward → R8 |

## 5. Docket rulings (all recorded inline in `deferred-work.md`; grep `RULED at the C5 retro`)

| Item (dw anchor) | Ruling | Owner |
|---|---|---|
| Windows integration CI lane (dw:5668, medium) | **YES** — scoped `tests/integration/companion/` lane in `ci.yml` | R1 |
| AD-1 limit-literal family shape (dw:5104) | **Presence-keyed stands**; per-file exemption is the standing remedy; third collision reopens | R10 — **closed by ruling** |
| Q3/AD-5 prose-sync (dw:5244) | Canonical home = the ledger; prose sites become one-line pointers; **standing rule: no new forward-looking cross-module prose in docstrings** | R2 |
| `dump_openapi.py` changelog (dw:5252) | Delete the changelog paragraphs (content already lives in ledger + story records) | R2 |
| Flake, two sightings (dw:5476) | One bounded repro attempt; annotate-and-monitor; third sighting escalates | R4 |
| `-m integration` scope trap (dw:5678) | Companion marker / scoped alias | R4 |
| Repo-wide class→token guard (dw:5617) | **YES** — one derived source-reading guard (Badge, ManaPip, deck-row tint, pill dot) before Epic 6's first view story | R3 |
| *(untagged)* vitest probe-harness half (dw:5115) | Re-homed from C4 item 4; build before Epic 6's first frontend story | R5 |
| *(untagged)* item-13 scope question | Review-added **test assertions** now re-enter review too; c5-8 not retroactively a violation | R8 |
| *(untagged)* chunked three-layer review | **Ratified** as the standing variant when a diff exceeds the single-pass threshold (c5-6/c5-7 precedent) | standing |
| *(executed in-retro)* story 6.4's stale 422 | Amended to 413 `payload_too_large` in `epics-companion-app.md` (5.5/6.1 were fixed at c5-5; 6.4 had been missed). AD-6/AD-7 spine amendments stay at Epic 8 | done |

## 6. Named, not actioned

- The **~26-entry `unowned` cluster** of `src/logic`/`src/data` rule questions (ledger `:2400`–`:3410` band) — no companion story can own it; candidate for a between-epic ledger closing pass. Deliberately left off the C6 prep list to keep it honest.
- **Broadcast concurrency residuals** (overlapping-send race, slow-client stall, ticket-flood starvation) remain accepted, documented tradeoffs — reconfirmed; if the real socket ever surfaces them, record, don't fix (c5-8's standing instruction).
- **Tab-corridor +1 stale figures** (pill added a stop; c4-11's 40-deck sweep not re-run) — flag confirmed carried on **c8-6**.

## 7. Epic C6 readiness

**No epic-invalidating discovery. C6's plan is sound as written**, with the 6.4 amendment executed and one coverage-map defect open (UX-DR46 assigned to both Epic 4 and Epic 5 → R9).

C6 consumes every C5 deliverable: the envelope (`contracts.py`), ticket mint + WS upgrade, broadcast (incl. `active_deck_changed` on `PUT /api/active-deck`), the ingest endpoint + 413 cap + client count, the reconnect loop (underpins 6.1's retry-once), the pill, and c5-8's restart proof. Known C6 landmines already ledgered: the c6-4 image-coalescing family (close as "not wanted" if declined a fourth time), the c6-1 MCP-status vs `ErrorReason` vocabulary collision, `agentEventOf` narrowing `kind` only (actionable when 6.x reads `payload`), and the `c6-8` placeholder at `AppShell.tsx:117` being the F1 gate's live survivor.

**Critical path before c6-1** *(amended after Brad's Block-J ruling — see §8)*:
1. **Integration PR `feat/companion-c5` → master** — no Greptile, per the standing rule.
2. **R1** (CI lane), **R5** (vitest harness), **R3** (class→token guard), **R2** (prose sweep) as C6 prep; **R9** (UX-DR46) before c6 story creation.
3. Block J rides the Epic C6 manual-testing checklist (c8-6 backstop).

## 8. Manual-testing checklist — Block J

> **RULED NOT RUN — Brad, 2026-08-09 (after the retro closed).** The whole block is CARRIED
> wholesale to the **Epic C6 manual-testing checklist**, with **c8-6 (the SC-5 human-judgement
> gate) as the terminal backstop**. Rationale: merge ≠ release (nothing reaches a user until
> c8-4), and C6's own stories put real eyes on most of these surfaces in the normal course of
> development — 6.3 drives active-deck switching (absorbing J2 and J1's loaded-deck half), 6.9
> owns the degradation matrix (absorbing J1/J7's reconnect walk), and every C6 frontend story
> works through the dev proxy daily (absorbing J5). Named consequence, accepted: the integration
> PR merges with **zero eyes-on-pixels verification of the C5 surface** — the pill's colours
> (J3, the P15 class no automated test can see), the sub-1100px floor (J4), and the exhaustion
> announcement (J7) have never been observed by a human. **`internal-error`'s first render (J6)
> is hereby carried a THIRD time** (Block I → C5 checklist → C6), which the Block-I precedent
> requires be an explicit ruling — this is that ruling. R11 in sprint-status closes as
> ruled-and-carried.

Derived from what every C5 test deliberately isolated away (no real network, fake timers, jsdom without stylesheets, single-handshake harnesses):

| # | Item | What no automated test can see |
|---|---|---|
| J1 | **Full reconnect walk**: app open → kill backend → pill walks Connected → Reconnecting → Backend gone → restart backend → pill returns to Connected **without a manual refresh**, the surface recovers (the c5-6 family fix, felt live). *Amended 2026-08-09: with J2 carried, no deck view renders during Block J (the active-deck slot is in-memory and agent-set only), so displacement/recovery is observed against the `no-active-deck` panel; the loaded-deck half rides with J2.* | The whole loop ran on fake timers and injected sockets; A6's defect was "worse than recorded" at Block I |
| J2 | **CARRIED, not run — Brad's ruling 2026-08-09**: the two-tab active-deck broadcast requires hand-rolling the token PUT that `companion_set_active_deck` (c6-2) exists to make; ruled too costly by hand. **Re-homed to c6-2/c6-3 manual testing**, where it becomes "open two tabs, ask the agent to switch decks" — and c6-3's ACs assert the all-tabs switch anyway. Mechanism note for that run: C5's `connection.ts` already re-drives the deck boot on `active_deck_changed`, so the observation is due, just deferred to when it costs one sentence | Broadcast fan-out was proven in-process + one real socket; never two real browsers |
| J3 | **Pill colours by eye**: green / amber / red per state | The P15 class — jsdom evaluates no stylesheet; the source-reading guard checks tokens, not rendered pixels |
| J4 | **Sub-1100 px window**: horizontal scroll appears at the floor; pill never covers the footer attribution | The Greptile P1 fix; verified once in headless Chrome, never by hand |
| J5 | **Dev proxy**: `npm run dev`, WS connects through Vite (Origin rewrite) from a real browser | `devProxyRoundTrip.test.ts` drives node `http.request`, not a browser |
| J6 | **`internal-error` first render** by a real engine | Carried from Block I — the last state panel never seen live |
| J7 | **Exhaustion announcement**: block the backend past both gates (60 s AND 4 failures) → disconnected panel displaces the deck via `surfaceOf`; screen-reader announcement fires on transitions only, not on mount | Live region + timing composed from fakes end to end |
| J8 | **Ticket TTL at the backoff ceiling**: leave the tab disconnected past 30 s intervals → reconnect still succeeds (mint-inside-attempt) | `FakeClock` made all TTL tests zero-wall-clock; the 30 s TTL vs 30 s ceiling collision was designed around, never observed |

## 9. Key takeaways

1. **Defects live in the guard layer, not the components** — the epic's dominant lesson, operationalised: the probes that come back green are the payoff, and R2's next frontier is the observation *mechanism* (jsdom, in-process harnesses, bounding boxes), not more assertions.
2. **R1 + pre-code rulings turned context weight into a solved problem** — 60/60 ruled before code, Dev Notes at a quarter-to-half of C4's, verification unthinned.
3. **Known-open action items convert into predicted failures** — item 7 cost exactly the CI escape it predicted; item 5's debt population grew during the epic meant to fix it. Re-homed items now carry termination clauses (R6) so a second carry is a decision, not a drift.
4. **Some claims are only true in a real process** — AD-10's thesis, proven by F2/F5; its corollary (a test with no automated home rots silently) is now R1.

## 10. Commitments

**11 action items (R1–R11)** appended to `sprint-status.yaml` under `action_items` (epic c5). C4 items 1, 2, 6 closed as met; items 4, 5, 7 closed as **re-keyed** into R5, R6, R7; the stale epic-5 real-deck survivor closed (its G-R2 successor closed 2026-07-17). Retrospective key `epic-c5-retrospective` → done. `epic-c5` → done.

**Next steps, in order** *(amended after Brad's Block-J and R9 rulings)*:
1. ~~Address R9 (UX-DR46)~~ **RULED 2026-08-09: deliberate split, annotated** — Epic 4 = focus floor, Epic 5 = connection-state half; UX-DR40's Epic 4/Epic 8 pair stamped the same way. Coverage map amended, defect note converted to a resolved ruling.
2. Integration PR `feat/companion-c5` → master (no Greptile). Merge ≠ release.
3. C6 prep: R1, R2, R3, R5 (R4, R6, R7 may ride alongside early C6 stories).
4. Begin c6-1 context under the amended 6.4 text. Block J rides the C6 checklist.
