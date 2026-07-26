# Epic C1 Retrospective — Launch the Companion

**Date:** 2026-07-26
**Facilitator:** Amelia (Developer)
**Participant:** Brad (Project Lead)
**Epic scope:** The companion backend's process layer, end to end — CI-enforced import boundaries
(c1-1), a side-effect-free ASGI app with a lifespan and `/health` (c1-2), port selection with
ephemeral fallback (c1-3), the typed REST error contract (c1-4), the localhost-only security
envelope (c1-5), the lazy database engine (c1-6), the discovery-file rendezvous (c1-7),
single-instance enforcement with verified identity (c1-8), and the console-script dispatcher plus
the held instance lock (c1-9). First epic of the 10-epic / 76-story companion feature; nothing
released.

---

## Delivery Summary

| Metric | Result |
|---|---|
| Stories | **9 / 9 done** — 2026-07-25 → 2026-07-26, two days wall-clock |
| PRs | **8 merged** (#9–#16) into `feat/companion-app`. #15 carried two stories (c1-7 + c1-8) by Brad's ruling when Greptile held it at 3/5 over the `remove_discovery` TOCTOU |
| Test suite | 1,310 → **1,683 passed / 1 skipped / 45 deselected** (+373). Companion sub-suite: 0 → ~330 |
| Code | 26 files changed under `src/` + `tests/`, **+8,310 / −16**. `src/companion/` = 3 leaf modules (`contracts`, `discovery`, `client`) + 7 app modules (`main`, `server`, `errors`, `security`, `deps`, `singleton`, `routes/health`) |
| Review load | ~**77 patches applied**, **9 decisions escalated to Brad**, ~40 findings dismissed with recorded rationale. **0 Critical / 0 Major across nine reviews** |
| Greptile | 3 P1s caught post-review — #9 (`from sqlalchemy import *` DML bypass), #12 (auto-`HTTPValidationError` resurrected by the 413 ruling), #16 (repeated `--port` last-won). **#13 scored 5/5 with zero findings** |
| Deferred ledger | 13 items opened; **5 closed inside the epic** — c1-2 seam, c1-3 `SO_EXCLUSIVEADDRUSE`, c1-4 CORS ordering, c1-8 launch race, c1-7 `remove_discovery` TOCTOU (by unreachability) |
| Gates | ruff, `mypy src/`, `mypy src/ --platform linux` and the pre-commit mypy hook green at every story boundary; plugin mirror rebuilt and committed 9 times |
| Production incidents | 0 — `feat/companion-app` has not touched master; nothing released |

---

## What Went Well

- **Guards-first was the highest-leverage decision in the epic, exactly as EPIC-SPLIT predicted.**
  c1-1 landed two AST import boundaries against a package containing nothing but two docstrings.
  Across the following eight stories `tests/unit/companion/test_import_boundary.py` was **never
  edited once** — every new module classified itself, and three stories recorded "if you find
  yourself wanting to edit the guard, a file is in the wrong place" as a working rule. AD-2 and AD-3
  are structural, not aspirational.

- **Measure, don't assume — applied to every load-bearing claim.** Each story's *Latest technical
  information* is probe output from this machine, not documentation quotes. c1-3 read
  `uvicorn/server.py:104` in the venv to prove lifespan precedes the listener (which is *why* the
  runner pre-binds). c1-4 probed Starlette's `ServerErrorMiddleware` re-raise before choosing
  middleware over an `Exception` handler. c1-8 measured a dead loopback port at ~2.03 s and derived
  the split connect/read timeout from it. c1-9 reproduced the launch race — two live companions,
  6 ms apart — before writing a line of the fix, then pasted the before/after.

- **Mutation testing became a habit, and it caught real dead guards three times.** c1-6's review
  found AC 7's concurrency test was **vacuous** (removing the lock left it green, because the
  creation body has no `await`); rather than ship a dead guard, two assertions with teeth were
  added. c1-7's `os.rename`-explodes test goes red the instant someone "simplifies" `os.replace`.
  c1-9 ran the specified mutation and found it **hung** (591 s) instead of failing — and added a
  2 s deadline so the `LK_NBLCK` primitive choice is actually guarded.

- **Non-vacuity pairing turned one Greptile catch into a house rule.** PR #12's displacement test
  passed *because no shipped route had validated input*. From c1-5 onward, every "returns None" case
  sits beside a populated record from the same call, every 503 beside a 200 from the same route,
  every rejection beside an acceptance. It is now an AC clause in four stories.

- **Forward-dated docstrings gave each story a landing pad already built.** c1-2 wrote `_shutdown`'s
  docstring saying *"Story c1-7 removes the discovery file here too"*; c1-3's `bound_port` named
  c1-5 and c1-7 as its callers; `resolve_preferred_port` promised c1-9's `--port`. Six stories
  arrived to find their seam described, and c1-9 treated the now-false ones as an AC rather than
  leaving them to rot.

- **Scope boundaries verified by command, nine for nine.** Every story listed its forbidden files
  and proved them untouched with `git status --porcelain -- <paths>` pasted into the Debug Log — up
  to seventeen paths in c1-9. Not one accidental edit in the epic.

- **Test isolation was treated as a product concern, not hygiene.** c1-7 made the autouse
  `PLANESWALKER_DATA_DIR` fixture an AC *and landed it first*, proving it inert at 222 passed before
  any production code existed — because ~94 existing lifespan entries were one commit away from
  overwriting the developer's real `companion.json`.

---

## Challenges & Lessons

### 1. Comments that assert a future story's state are deferred edits

Six sentences across four files said *"no root handler exists until c1-9."* Each was true when
written and each was **load-bearing** — c1-3's fallback WARNING, c1-5's rejection WARNING, c1-7's
discovery-skip WARNING and c1-8's reclaim INFO all chose their *level* around that fact. c1-9 had to
repair all six as an acceptance criterion.

It worked only because the sentences were forward-dated and greppable. That is good writing, not a
mechanism.

**Lesson → action item 1:** a comment or docstring asserting a *future* story's state is a deferred
edit and needs the same treatment as a gate output — a story key, in the same commit that writes it.

### 2. Twenty "Open questions for Brad" accumulated; five were answered

Nine stories raised 20 open questions. Five were resolved (`internal_error` as a sixth token, 413
for `payload_too_large`, exit-0 on refusal, the dispatcher exemption, the vacuous-lock signoff) —
all of them the ones a story explicitly pushed for. The remaining fifteen persisted by default, and
two of them landed directly in Epic C2's path:

- **c1-5 Q2** — a Vite dev proxy must rewrite `Host` or every proxied call gets a typed 400. Blocks
  c2-1's scaffold decision. **Ruled this retro.**
- **c1-2 Q2** — `/docs` and `/openapi.json` left at FastAPI defaults as an explicit non-decision,
  which c1-5's security envelope did not close. **Ruled this retro.**

And one is quietly ageing into the release: **c1-3's `PLANESWALKER_COMPANION_PORT` name** has been
unconfirmed since story 3 and is heading into c8-4's README unexamined.

**Lesson → action item 2:** an open question whose answer changes a *later story's* work must be
homed on that story key when it is raised, not left in the record for someone to find.

### 3. A story's own ACs can be internally impossible

c1-9's AC 15 said "leave the two old `test_entry_point.py` tests alone" while AC 1 mandated
`argv` defaulting to `sys.argv[1:]` — which, under pytest, dispatches the test file path as a
subcommand. The two could not both hold. The dev proved it with the actual failure output, fixed it
with a two-character edit (`main()` → `main([])`), and **flagged the contradiction** rather than
quietly complying or quietly deviating.

That is the behaviour we want. Worth naming, because the alternative — silently satisfying the
letter of one AC and breaking the other — is invisible in a green suite.

### 4. Windows/Linux split coverage is real, and currently accidental

`singleton.py` branches on `sys.platform`; each platform's mypy run type-checks only its own half.
CI is ubuntu-only, so the POSIX branch is checked *because CI happens to run there* and the Windows
branch only on Brad's machine. The module says "both mypy runs are mandatory" — and **no gate
enforces it**. c1-9 froze `ci.yml` and `.pre-commit-config.yaml`, so it was deferred rather than
patched.

**c2-1 is the first story since c1-2 permitted to touch `ci.yml`** — and it is adding a frontend job
anyway, which makes it the natural home. **→ action item 3.**

### 5. One behaviour no unit test can prove

Interactive Ctrl-C. c1-9 verified `CTRL_BREAK_EVENT` against a detached child and *traced* the
Windows exit-3 (uvicorn completes graceful shutdown; the console-control path terminates the process
before `main()` returns — `MAIN RETURNED` demonstrably never prints). Real-terminal `CTRL_C_EVENT`
cannot be delivered in that harness. Homed to manual testing, deliberately not "fixed" by trapping
a signal.

---

## Previous-Retro Continuity (Epic 7 — 4 action items)

| # | Item | Status |
|---|---|---|
| 1 | **Gate-output homing rule** | ✅ **Exercised in every story of the epic.** c1-7 homed the Windows replace-while-open hazard → c1-8 ruled on it and re-homed it to c6-1 → c1-9 closed the launch race and the TOCTOU *in place*, recording what shipped rather than the plan. Nothing floated. **Closed and promoted to a standing agreement.** |
| 2 | **Error-contract enumeration** | ✅ **Applied in its strongest possible form — before the routes existed.** c1-6 registered `DatabaseError → 503 database_unavailable` inside `install_error_handling`, so every data route c3-1 onward adds inherits the guard with no per-route ceremony. The epic-7 lesson (7.2's three unguarded reads) cannot recur on this path. **Closed and promoted.** |
| 3 | Key the data-layer orphan story | ✅ closed at the Epic 7 retro (`data-layer-orphan-handling`) |
| 4 | Close + promote construction-site enumeration | ✅ closed at the Epic 7 retro; visibly used here (c1-2 enumerated *three* declaration sites for one dependency: `pyproject.toml`, `uv.lock`, the pre-commit mypy hook — plus the plugin mirror) |

**Follow-through: 2 of 2 live items closed, both promoted to standing agreements.** Matches Epic 7's
record, on an epic three times the size.

---

## Epic C2 Preview — Dependencies, Inheritance, Gaps

**Epic C2: The Glass — Foundation, Identity & Honest States.** 10 stories. The only epic in the
feature that introduces a new toolchain: `ui/` on Node ≥ 20, Vite ≥ 8, React ≥ 19.2, zustand ≥ 5.0,
with the load-bearing `typescript >=5.9,<6.1` pin (`typescript-eslint`'s peer range is `<6.1.0`, so
an open floor resolves to TS 7 and breaks `npm ci` outright).

**C1 dependencies — all satisfied:**

- `app.openapi()` carries **both** `HealthResponse` and `ErrorResponse`, with FastAPI's
  auto-`HTTPValidationError` structurally stripped by `_CompanionFastAPI.openapi()`. c2-3's
  generator has real, non-drifting input from day one ✅
- All **six** reason tokens are frozen and enumeration-pinned. c2-9's state-panel switch has a
  closed set to switch on ✅
- No CORS middleware exists, by ruling (c1-5 Decide-once #3). c2-2 serves the SPA from
  `src/companion/app/static/` same-origin, with nothing to negotiate ✅
- The Host envelope already runs on every request the suite makes, so a new surface cannot
  accidentally bypass it ✅

**What C2 inherits and must not lose:**

1. **c2-9 owes an `internal_error` state panel.** The c1-4 review added the sixth token *and* homed
   the panel on Story 2.9 — but `EXPERIENCE.md` has no copy for it. AD-16 requires the token and the
   UI state to be added together; the token shipped alone. **This is a UX-copy gap, not a code gap.**
2. **c2-9 also inherits the corrupt-database ruling** (c1-6 deferral): a durably corrupt `cards.db`
   answers `database_unavailable` — the quiet-retry "Database updating" state — forever, with no
   path to a repair panel. Nothing distinguishes 200 ms of mid-import from a month of garbage.
3. **c2-1 owns the `changeOrigin` requirement** (ruled below) and is the natural home for the
   deferred `--platform` mypy gate gap, since it is the first story since c1-2 permitted to edit
   `ci.yml`.

**No blocking dependency is unmet. C2 is unblocked.**

---

## Rulings made in this retrospective (Brad, 2026-07-26)

**R1 — c2-1 commits to a Vite dev proxy, and `changeOrigin: true` is a tested requirement.**
The dev server runs on :5173 and proxies to the companion backend; without the Host rewrite every
proxied call returns c1-5's typed `400 invalid_request`. Rationale: ~40 frontend stories across
C2/C4/C6/C7 justify the HMR loop. The cost — a second origin exists in development — is accepted,
and the mitigation is that the requirement is documented *and* asserted, not left to be discovered
by a confusing 400. **Homed on c2-1** (annotated in `epics-companion-app.md` Story 2.1 and keyed as
an action item). Closes c1-5 Open Question 2.

**R2 — `/docs` and `/openapi.json` stay enabled: a deliberate keep-decision, no longer a
non-decision.** Loopback-only, Host-validated, single-user, and no state-changing endpoint is
reachable without the agent token (which never enters the browser). `/docs` is genuinely useful for
hand-testing the REST surfaces C3 and C5 add. Note that c2-3 calls `app.openapi()` **in process**,
so the HTTP route is not on the type-generation path either way. Closes c1-2 Open Question 2.
Precedent for the form of this ruling: the 5.7 `card_advantage`-ceiling keep-decision.

**R4 — `PLANESWALKER_COMPANION_PORT` is renamed to `COMPANION_PORT`** (made during the
manual-testing pass, 2026-07-26). The vendor prefix goes; the `COMPANION` disambiguator **stays**,
deliberately — `MCP_TRANSPORT` already contemplates `sse`/`streamable-http`, so an MCP server
running over HTTP would need a port of its own, and a bare `PLANESWALKER_PORT` could not tell the
two processes apart. Blast radius was one constant (`server.py:58`) plus two docstring/usage sites
in `__main__.py`; the tests read `server.PORT_ENV_VAR` and needed no edit. Gates green (1,684 passed
/ 1 skipped / 45 deselected), plugin mirror rebuilt. Free because nothing had shipped — c8-4
documents the settled name. Closes action item 5 and the last surviving c1-3 open question.

**R3 — the integration PR goes now.** `feat/companion-app` → `master` immediately, per the
per-epic rhythm ruled 2026-07-26: story PRs into the umbrella, one integration PR to master after
the retro, a fresh umbrella cut off master for C2. **Merge ≠ release** — no tag and no CHANGELOG
entry until c8-4. Manual testing runs against master afterwards; anything it surfaces is a fix on
the C2 umbrella, not a hold on the merge.

---

## Manual-Testing Outcomes — run 2026-07-26, Brad

Run against `feat/companion-app` **before** the integration PR (rather than after, as originally
planned) — which is what surfaced the R4 rename while it was still free.

| Block | Result |
|---|---|
| **A — CLI surface** | ✅ All five shapes exact: `--help` → usage on stdout / exit 0; `nonsense` → error + usage on **stderr** / exit **2**; `companion --help` → stdout / **0** (the c1-9 review ruling, live); `--port abc` → exit 2; repeated `--port` → exit 2 (Greptile #16's P1, live). Stream split holds on every path |
| **B — real launch + browser** | ✅ Launch line, the first `src.*` INFO records ever to reach a user, `/health`, `/docs`, typed 404. **Confirms R2** |
| **C — interactive Ctrl-C** | ✅ **Exit `0`**, graceful shutdown, `companion.json` retracted, `companion.lock` retained at 0 bytes, no traceback. The `3` was a `CTRL_BREAK_EVENT`-to-a-detached-child artifact, not user-visible. **Deferral closed positively** |
| **D — refusals** | ✅ Verified-live refusal, explicit-port-doesn't-help, ephemeral fallback, and stale reclaim after a hard kill — all as specified |
| **E — `--port` / env var** | 🔵 **Not run.** Superseded in substance: ruling **R4** renamed the variable to `COMPANION_PORT`, and the parse paths are covered by Block A plus the suite (which reads `server.PORT_ENV_VAR`, so it followed the rename). **Residual:** no live confirmation that the *renamed* env var is honoured end to end. Cheap to close whenever; c8-4 should not document it as hand-verified |
| **F — fresh install** | 🔵 **Not run.** **Residual:** FR-22's "starts on a machine with no `cards.db`" has no live confirmation. Unit coverage is strong (c1-2 inertness + c1-6 laziness), and the observable half — a data endpoint answering `503 database_not_initialized` — has no shipped route until c3-1 anyway. **Natural home: c3-9**, which owns the fresh-install UI loop and will need a real empty-data-dir run regardless |
| **G — MCP server in Claude Code** | ✅ **Passed.** The shipped public product connects and serves tools with the dispatcher in front of it. This was the only block whose failure would have held the integration PR |
| **H — plugin build** | ✅ Passed. `uv run --directory plugin/server python -m src.mcp_server companion` built the plugin's own environment for the first time and served on 8765, publishing a real discovery file. **First execution of a mirror rebuilt and committed nine times.** Re-mirrored after R4 |

**One incidental finding, cosmetic:** long wrapped command lines render with dropped glyphs in the
VS Code PowerShell terminal (PSReadLine wrap-redraw). Not our output — the companion's own lines
rendered intact beside the mangled ones. No action.

**Copy nit for c8-4:** the usage synopsis `[-h] [companion [--port PORT]]` implies `-h` only precedes
`companion`, but `companion --help` also works by ruling. The behaviour is right; the synopsis never
caught up.

---

## Manual-Testing Checklist — Epic C1

Everything below is either proxy-verified (subprocess, `tmp_path`, stubbed) or unverified. These
want Brad's hands.

| # | Check | Why a unit test can't close it |
|---|---|---|
| 1 | **Interactive Ctrl-C** in a real terminal → no traceback, `companion.json` gone, `companion.lock` remains at 0 bytes, the next launch is unblocked | Only `CTRL_BREAK_EVENT` was verifiable; `CTRL_C_EVENT` cannot be delivered to a detached child without also signalling the driver (c1-9 deferral, explicitly homed here) |
| 2 | **Bare `artificial-planeswalker` inside the real Claude Code MCP config** → all 20 tools load, stdout stays clean | Only ever driven as a scripted one-shot `initialize` handshake |
| 3 | **`artificial-planeswalker companion` against the real data dir** → open the printed URL, hit `/health` in a browser | Every companion test ran under an isolated `PLANESWALKER_DATA_DIR` |
| 4 | **Fresh-install path** — point `PLANESWALKER_DATA_DIR` at an empty directory, start, confirm it *starts* rather than crashing | FR-22's whole promise; the 503 side is only test-route-verified, since no data endpoint ships until c3-1 |
| 5 | **`--port N`, `--port=N`, `PLANESWALKER_COMPANION_PORT`**, plus a garbage value falling back with a visible warning | The env-var **name** is unconfirmed since c1-3 and heads into c8-4's README |
| 6 | **Occupy 8765, then launch** → the fallback line, then serving on an ephemeral port | Verified once in c1-3, accidentally (the hog script died; the occupant was a real second companion) |
| 7 | **Plugin path**: install the plugin build and run `artificial-planeswalker companion` from it | The mirror was rebuilt and committed **9 times and never once executed**. c8-5 owns parity formally, but a smoke test now is cheap and the failure would be structural |
| 8 | **Visit `/docs` and `/openapi.json`** and confirm R2 still reads correctly with the surfaces in front of you | A keep-decision is worth a look before C3 doubles the route count |

---

## Action Items

| # | Action | Owner | Success criteria |
|---|---|---|---|
| 1 | **Forward-dated-comment homing.** A comment or docstring asserting a *future* story's state (a level chosen around an absent handler, a promised flag, a "story X does this here") is a deferred edit — give it a story key in the same commit that writes it, the way gate outputs get keys. | Brad (story authoring, standing) | The next story that invalidates such a comment finds it already listed in its own ACs, not by grep |
| 2 | **Open-question homing.** An "Open question for Brad" whose answer changes a *later story's* work is homed on that story key when raised — not left in the story record. Questions with no downstream consumer stay in the record as today. | Brad (story authoring), from c2-1 | No C2 story discovers a C1 question mid-implementation |
| 3 | **Close the `--platform` mypy gate gap in c2-1.** Add the opposite-platform mypy invocation to `ci.yml` (or `.pre-commit-config.yaml`) while c2-1 is adding the frontend job. Today the POSIX half is checked only because CI happens to run on ubuntu, and the Windows half only on Brad's machine. | Brad (c2-1) | A deliberately Windows-broken `singleton.py` branch fails CI |
| 4 | **c2-9 must ship the `internal_error` panel copy.** The sixth token shipped without a UI state; AD-16 requires them together. c2-9 also inherits the corrupt-database ruling (c1-6 deferral). Both need `EXPERIENCE.md` copy before the panels are built. | Brad (c2-9) | `EXPERIENCE.md` carries verbatim copy for all six tokens, and c2-9's ACs name both |
| 5 | **Confirm `PLANESWALKER_COMPANION_PORT` during manual testing** (checklist #5) so c8-4 documents a settled name rather than an unexamined one. | Brad (manual testing) | The name is either confirmed or changed before c8-4 |
| 6 | **Annotate c2-1 with the `changeOrigin` requirement (R1)** in `epics-companion-app.md`, per the gate-output homing rule. | Amelia — **done in this retro** | The annotation exists on Story 2.1 |

### Team agreements (standing, updated)

- **Claims require verification** — stands; nine stories pasted actual gate output.
- **Task 0 story-start verification** — stands; 9-for-9, and it caught a real baseline delta twice.
- **Construction-site enumeration** — stands; exercised on dependency declaration sites in c1-2.
- **Gate-output homing** — *promoted this retro:* anything a gate, review or story produces that
  another story must honour gets a key in the same commit.
- **Error-contract enumeration** — *promoted this retro:* when a story adds awaited I/O to an
  existing path, enumerate every call against the guard that covers it — and prefer registering the
  guard before the callers exist.
- **Non-vacuity pairing** — *new, promoted this retro:* every structural assertion must be shown to
  be non-vacuous. Pair each refusal with an acceptance from the same call, and where an AC names a
  *mechanism*, add an assertion that goes red when the mechanism is removed.

---

## Readiness Assessment

- **Testing & quality:** ✅ 1,683 passed / 1 skipped; zero known defects in `src/companion/`. One
  known pre-existing flake (`test_list_decks_with_strategy_field`, same-tick `created_at` tie broken
  by a random UUID) lives in `src/data` and is ledgered.
- **Deployment:** ⏳ integration PR `feat/companion-app` → `master` is the next action (R3). Not a
  release — no tag, no CHANGELOG until c8-4.
- **Stakeholder acceptance:** ⏳ the 8-item manual-testing checklist, run after the merge. Findings
  are fixes on the C2 umbrella, not a hold on the merge.
- **Technical health:** ✅ strong. Two AST guards never needed an edit; every scope boundary verified
  by command; 13 deferrals opened but every one of them written down, and 5 closed within the epic.
- **Unresolved blockers for C2:** none. R1 and R2 removed the two that existed.

---

## Significant Discovery Alert

**None requiring a plan update.** Every architectural decision C1 tested held: AD-2's CI-enforced
read-only boundary, AD-3's leaf/app split (including the one narrow dispatcher exemption AD-14
required), AD-4's rendezvous-and-identity design, AD-10's inert construction, AD-15's
crash-is-ordinary stance — which is exactly what made the *held* lock the right shape over an
`O_EXCL` file — and AD-16's closed token set, which absorbed a sixth member cleanly because the
enumeration pins forced the addition to be deliberate.

The two spine deltas are additive and recorded: `server.py` and `errors.py` are additions to the
Structural Seed (both stated deliberately in their stories), and `app/singleton.py` is new surface
introduced by Brad's 2026-07-26 held-lock ruling. Nothing was moved or renamed. **c8-3 owes the PRD
its amendments** (NFR-02's `mode=ro`, FR-14's path, FR-04's layout) plus the AD-3 sibling-leaf
clarification from c1-1 Decide-once #2 — all already on that story.

---

## Commitments

- Action items: **6** (1 executed in-retro) + 6 standing team agreements
- Rulings: **4** (R1 dev-proxy `changeOrigin`, R2 `/docs` keep-decision, R3 integration PR now,
  R4 `COMPANION_PORT` rename)
- Manual-testing checklist: **8 items**, run after the merge
- Epic 7 continuity: **2 of 2 closed, both promoted**
- Critical path to C2: integration PR → fresh C2 umbrella off master → c2-1 (carrying R1 and action
  items 3)
