---
epic: c5
story: c5-5
work_branch: feat/companion-c5
story_branch: feat/companion-c5-5-agent-events-ingest
depends_on: >-
  c5-4 (merged, PR #56) — `ws.broadcast(app, event) -> int` and
  `ConnectionRegistry.connected_count`, the two halves of this story's response number, plus the
  accepted no-locking residual this story must not "fix". c5-1 (merged, PR #53) — the frozen
  `AgentEvent` union this story finally puts on a route, and `_MAX_ENVELOPE_BYTES`, the constant
  whose enforcement was ruled (Q9) to be this story's. c3-4 (merged) — the `AgentToken` seam whose
  docstring names this story as its second caller, and the pre-parse body-cap deferral homed here.
  c5-2 (merged, PR #54) — the worked pattern for a real schema diff (gen:api between plant and
  probe; router-tax line).
baseline_commit: 9b944a6
---

# Story C5.5: Token-authenticated event ingest that reports who is listening

Status: review

<!-- Context engine analysis completed 2026-08-08: epics + SPINE + PRD + EXPERIENCE + c5-1..c5-4
records + deferred-work + live source all mined; five ledger deferrals homed here are carried in
full under "Inherited deferrals". Validation is optional: run validate-create-story before dev-story. -->

## Story

As a companion MCP tool,
I want one authenticated endpoint that validates my payload and tells me how many browsers saw it,
so that I can report to Brad whether his content was actually displayed.

**✅ BRANCH PRECONDITION.** `feat/companion-c5` is at `9b944a6` (the "record c5-4 merged" docs
commit above the `503899b` PR #56 merge — either is a valid base). Cut
`feat/companion-c5-5-agent-events-ingest` from it. Verify
`git log --oneline -1 origin/feat/companion-c5` **before** `checkout -b`, not after.

**What this story really is.** One new route module (`routes/agent_events.py`), one new response
model in `contracts.py`, the feature's first *pre-parse* body cap, and a schema regeneration —
plus five things that are not obvious from that.

---

1. **EVERY HOME IS PRE-BOOKED BY SHIPPED PROSE, AND FULFILLING IT IS AN OBLIGATION.**
   `security.py:477`'s `AgentToken` docstring: *"c5-5's `POST /agent/events` is the second
   [caller] and inherits the whole contract — the header spelling, the fail-closed comparison and
   the `forbidden` token — rather than writing a second check."*
   `state.py:523` `connected_count`: *"the number story 5.5 answers with."*
   `errors.py:91` (`CompanionError` docstring): *"c5-5's oversized push is still to come."*
   `contracts.py:412-427` (`_MAX_ENVELOPE_BYTES` docstring): the enforcement spec, written at
   c5-1's Q9 ruling — pre-parse, 413, never truncated, one mechanism for both endpoints.
   `test_committed_schema.py:202-207`: *"c5-5 declares the event union as POST /agent/events's
   request body and the rest arrive together."*
   Fulfil each and rewrite its forward-looking wording in the same commit (c3-9's rule). Your
   Task 0 grep of `c5-5` across `src/ ui/ tests/ scripts/` is the authoritative list — c5-3
   already had to correct one of these predictions once (`main.py`/`security.py` used to claim
   "c5-5 adds its piece inside `install_security`"; the correction stands: this story is a route
   + dependency + a fourth `include_router`, NOT a security wiring line — except that the
   pre-parse cap, if middleware-shaped, genuinely does live in the middleware stack; see item 2).

2. **THE 64 KB CAP IS THE REAL ENGINEERING IN THIS STORY — EVERYTHING ELSE IS ASSEMBLY.**
   `payload_too_large` has been a declared token with **no producer since c1-4**, and
   `_MAX_ENVELOPE_BYTES = 64 * 1024` (`contracts.py:412`) is a constant nothing reads. A pydantic
   validator runs *after* parsing and cannot bound what the process buffers, so the cap must be
   **pre-parse** (Content-Length check plus a counted-bytes bound on the actual stream — a liar's
   Content-Length must not win). Three shipped constraints box the design in:
   - **One mechanism for both body endpoints** (`deferred-work.md:2604-2620`, homed here from
     c3-4 Q4): it must also bound `PUT /api/active-deck`, not just the new POST.
   - **Middleware sends, never raises** (`errors.py:99-104`, c1-5 ruling): if the cap is a
     middleware, it answers by calling `error_response("payload_too_large")` and sending — a
     raised `CompanionError` from user middleware surfaces as a false 500.
   - **The ordering pin** (`deferred-work.md:2686-2692`):
     `test_routes_active_deck.py::test_a_malformed_body_without_a_credential_is_still_forbidden`
     pins FastAPI 0.140's measured behaviour (body read/parsed at `routing.py:423-448`, deps
     solved at `:473`). A middleware-level cap changes that observable order for oversized
     bodies and **reds the pin**. You must consciously decide contract-or-snapshot (Q3 below),
     and a revised pin goes through review, never `git rm` (C4 retro item 13).
   Note what auth does and does not give you: a wrong token means the handler never runs, so
   *nothing is broadcast* — but the body is still buffered before the dependency is solved. The
   cap is what closes the buffering hole, and it protects both endpoints unauthenticated.

3. **THIS IS THE FIRST REAL SCHEMA DIFF SINCE c5-2 — c5-1/c5-3/c5-4 WERE ALL CONFIRMED-NEGATIVE.**
   Declaring `AgentEvent` as the request body is the whole AD-12 mechanism ("no dummy endpoint
   and no second generator" — the dummy endpoint is explicitly banned at c2-3). Expect and
   welcome these reds; they are the pins working:
   - `test_committed_schema.py` path set 8 → **9** (`/agent/events`) and component set 13 →
     ~30 (six envelope classes, six payloads, four item models, `TierLetter`/`Confidence`
     enums, plus your new response model). **These tests read the COMMITTED file — run
     `npm run gen:api` (from `ui/`) between any schema-visible change and the probe**, or the
     red/green tells you nothing (bit c5-2's R2 twice; `deferred-work.md:5058-5085`).
   - `test_spa.py`'s hand-mirrored differential router list (~line 324-328): **"c5-5 remains
     outstanding" — this story is the last one that ledger entry names** (`deferred-work.md:
     1905-1937`). One line: `without_spa.include_router(agent_events.router)`.
   - `spa._reserved_prefixes` derives the new first segment (`agent`) from the route table
     automatically (the `/ws` precedent, `deferred-work.md:5168-5175`); `_RESERVED_SEED` is
     belt-and-braces for `/api` only — rely on derivation, don't extend the seed.
   - `test_openapi_contract.py` byte-snapshot red until regen; CI porcelain check on
     `ui/src/api/`; commit `openapi.json` + `types.d.ts` in the same commit.
   No `securitySchemes` may appear (`test_committed_schema.py::test_no_security_scheme_is_
   documented` pins zero): `require_agent_token` reads the header by hand precisely so the
   schema stays clean — the c3-4 PUT is your route-shape precedent. c5-1's `json_schema_extra`
   examples reach `openapi.json` for the first time here; the `_DATA_KEYS` truncator fix is
   already shipped and tested, so this is exercise, not work.

4. **THIS STORY MAKES 413 REAL AND MUST CURATE WHO DECLARES IT.** Six body-less GETs currently
   publish an unreachable 413 through the two shared include sets in `build_app()`
   (`main.py:479-500`) — a ledgered wart re-homed here by name (`deferred-work.md:2333-2358`,
   also recorded in `scripts/dump_openapi.py:127-137`). c5-2 and c3-4 both declined to extend it
   (per-include narrowing is now a two-instance pattern), which narrows your job to **a single
   edit at two call sites**: drop `payload_too_large` from the shared/database include sets so
   only operations that can actually answer 413 declare it — the new POST, and
   `PUT /api/active-deck` if (as Q2 recommends) the one-mechanism cap now genuinely bounds it
   (declare at route level, the PUT's existing `forbidden` precedent).

5. **THE RESPONSE MODEL DOES NOT EXIST YET, AND TWO SHIPPED DOCSTRINGS DISAGREE ABOUT ITS
   NUMBER.** `contracts.py` has no ingest-receipt model — you mint one (Q1). The SPINE's
   sequence diagram shows `B-->>M: 200 {clients: 1}`; FR-06 and the epic AC say
   "connected-client count"; `connected_count`'s docstring claims to be "the number story 5.5
   answers with" — but `broadcast()` returns the **delivered** count (clients that actually
   received the frame; a mid-broadcast send failure evicts and is not counted). The two differ
   only in failure races, but the response can only carry one. Q1 rules it; whichever loses gets
   its docstring corrected in the same commit (item 1's rule). Contracts-side conventions that
   bit before: class docstrings above `Attributes:` ship **verbatim onto the wire** (mark
   `# WIRE-VISIBLE, IN FULL.`), never publish internal numbers in wire prose (c5-2's TTL
   lesson — say "small", not "64 KB", in anything wire-visible; the cap number lives in the
   constant's docstring, which `without_python_docstring_sections` keeps off the wire only
   below the first Google header — check what actually lands in `openapi.json`).

---

## Dev Notes

### Task 0 — verify the baseline before writing anything

| What | Expected at `9b944a6` |
|---|---|
| Python suite (`uv run pytest -m "not integration"`) | **2,769 passed / 1 skipped** |
| Frontend (`cd ui && npm test`) | **1,694 / 65 files** (one flake seen at the c5-4 baseline — re-run before believing a red) |
| Committed schema | **8 paths / 13 components**; `npm run gen:api` is a clean no-op |
| Stack | fastapi 0.140.0, starlette 0.48.0, websockets 16.1.1 |
| `grep -rn "c5-5" src/ ui/src ui/tests tests/ scripts/` | Reconcile EVERY hit (C4 retro item 6); each is either fulfilled+rewritten this story or explicitly not yours |
| Read before designing | `test_routes_active_deck.py::test_a_malformed_body_without_a_credential_is_still_forbidden` (the ordering pin); `contracts.py:412-427`; `ws.py:340-408`; `state.py:464-530`; `security.py:423-490`; `main.py:452-580` |

A mismatch in Task 0 is a finding, not a nuisance — record it.

### Where each piece goes

- **`src/companion/app/routes/agent_events.py` (NEW)** — the SPINE's Structural Seed names this
  file (`app/routes/ # decks, cards, session, health, agent_events`). `router = APIRouter()`
  with the path spelled `/agent/events` (or `prefix="/agent"`; Q5). Handler shape mirrors
  `active_deck.py:106-170`: `async def ingest_event(request: Request, body: AgentEvent,
  _credential: AgentToken) -> <ReceiptModel>` — FastAPI validates the discriminated union as a
  request-body annotation natively (standalone validation would need `TypeAdapter(AgentEvent)`;
  you don't need it in the route). One awaited `ws.broadcast(request.app, body)` call, no
  route-level try — `broadcast()` is proven total (`test_the_broadcast_helpers_are_total`).
  Registry accessor idiom when the lifespan never ran: copy `session.py`'s `_store(request)`
  hand-raised-`AttributeError` → 500 `internal_error` pattern (or answer count 0; Q6 note —
  `broadcast()` already returns 0 for a never-ran lifespan, which is the simpler truth).
- **`src/companion/contracts.py` (UPDATE, minimal)** — the receipt model only (Q1). The leaf is
  frozen otherwise: stdlib+pydantic only, no helpers, `extra="forbid"`, caps by named constant.
  `ErrorReason` stays at **ten** — this story adds NO token, so the eight-site ripple
  (`contracts.py:118-124`) does not apply.
- **The pre-parse cap (NEW mechanism, home per Q2)** — pure-ASGI, http scopes with bodies only,
  wraps `receive` to enforce Content-Length AND counted bytes against
  `contracts._MAX_ENVELOPE_BYTES`; on breach, **send** `error_response("payload_too_large")`
  (413) and stop — never raise, never truncate, never pass a partial body through. Must sit so
  it covers both `POST /agent/events` and `PUT /api/active-deck`. It sees `websocket` scopes
  pass through untouched.
- **`src/companion/app/main.py` (UPDATE)** — fourth `include_router` for the new router, above
  `install_security(app)`, with per-include `responses=error_responses("invalid_request",
  "forbidden", "payload_too_large", "internal_error")` — **no 503**: the route has no DB
  dependency and must NOT join `TestTheDatabaseTokensAreDeclared.DATABASE_BACKED`. `/agent` is a
  novel prefix protected only by registration order (`main.py:577-579`'s own warning) — the SPA
  mount stays last (`keep_spa_mount_last` fixture exists for tests that re-install).
- **The 413 curation (UPDATE, two call sites)** — item 4. Also update `scripts/dump_openapi.py`'s
  wart paragraph (`:127-137`) to record the wart closed.
- **`tests/unit/companion/test_routes_agent_events.py` (NEW)** + pin updates:
  `test_committed_schema.py` (paths 8→9, component set), `test_spa.py` router list, possibly the
  ordering pin (Q3, through review). `test_contracts.py` already covers union validation
  exhaustively — do NOT re-test payload shape validation; test the *route's* behaviour.
- **Generated artifacts** — `ui/src/api/openapi.json` + `types.d.ts` via `npm run gen:api`;
  append this story's before/after to `scripts/dump_openapi.py`'s running ledger; rebuild the
  plugin mirror (`uv run python -m scripts.build_plugin`) and **sha256-verify after the LAST
  edit** (c5-1's falsified-sha headline — review patches count as edits).

### The house idiom (the parts this story exercises)

- Auth is `_credential: AgentToken` — nothing else. No Header declaration, no security class, no
  second comparison. Wrong/missing/malformed token → 403 `{"reason": "forbidden"}`,
  indistinguishable to the caller; the one-word distinction goes to the log only.
- Every non-2xx body is `{"reason": token}` built by `errors.error_response`; modelled failures
  in route/dependency code raise `CompanionError(reason)`; middleware sends.
- Field-cap violations inside the envelope (61 items, 201-char reason, blank id, naive ts,
  unknown `kind`) are pydantic `RequestValidationError` → **400 `invalid_request`** (the shipped
  AD-16 handler; FastAPI's auto-422 is stripped from the schema and stays banned). Only the
  byte-size breach answers **413**. Keep the two failure classes distinct in tests.
- Success bodies are Pydantic schemas directly, unwrapped (AD-16). No payload echo (CM-1).
- `datetime.now(UTC)`, mypy --strict, ruff 100 cols, Google docstrings, `%`-lazy logging, module
  docstring, no `print`. `Example:` blocks in `src/companion/**` docstrings auto-run as doctests.

### Testing this story

`lifespan_client` (in-process httpx over ASGITransport, real Host envelope, `bound_port=54321`)
is the primary tool; `open_socket()`/`OpenSocket` holds real upgraded sockets open so the relay
proof is wire-level: two open sockets + one authenticated POST → both frame lists gain the
serialised envelope AND the response reports the count. `FakeConnection(fails=True)` registered
directly on `connection_registry(app)` drives the delivered-vs-connected divergence for Q1's
chosen semantics. No test sleeps, ever. Every rejection test pairs with an acceptance
(non-vacuity); assert through the wire, never `app.state`. R2: every new guard/assertion of
consequence gets a planted red through the full suite via
`uv run python -m scripts.probe_harness --expect-red '<node-id>'`, reverted, with one line on
what it compares and cannot see — and remember c5-4's lesson: drive the probe through the case
that actually discriminates.

Structural guards live on files you touch — don't trip them: `state.py`/`ws.py` identifier bans
(no `token`/`agent_token`/`credential`/`secret` names in either; the route module is where auth
and broadcast legitimately meet, as `active_deck.py` already does); bare literals `60` and `15`
banned under `src/companion/**` outside `contracts.py`; no `create_task` on the push path
(sequential awaited sends are the AD-9 ruling); no new top-level `src/companion/*.py`; no CORS;
no DB imports in the new route (AD-2 AST guard); refusal bodies byte-identical.

**The one real-socket integration test is c5-8's** — everything here is in-process. Do not add
an integration-marked test.

### Inherited deferrals — R1 trigger-gated

**Triggered (full text lives in `deferred-work.md`; disposition owed there in the same commit):**
1. **Pre-parse body cap** (`dw:2604-2620`, from c3-4 Q4) — this story's item 2. Owed: the
   mechanism, both endpoints, and the entry closed.
2. **Body-before-credential ordering pin** (`dw:2686-2692`) — contract-or-snapshot, Q3. Owed: the
   decision recorded and, if snapshot, the pin revised through review.
3. **Unreachable-413 wart** (`dw:2333-2358`) — item 4. Owed: two call-site edits + the
   `dump_openapi.py` paragraph updated + entry closed.
4. **Router tax** (`dw:1905-1937`) — one line in `test_spa.py`; this story is the last named
   debtor. Owed: the line, and note in the entry that the tax is paid out.
5. **gen:api-between-plant-and-probe R2 ordering** (`dw:5058-5085`) — first story since it was
   ledgered with a real schema diff. Owed: obey it; no ledger edit needed.

**Not triggered (one line + anchor each):** `tsc -b` cascade (`dw:2144-2197`) fires only if a
new `ui/tests` file imports a src module with relative imports — this story adds none; prove
with `npx tsc -b --force` exiting 0 and move on. Example-payload truncator (`dw:2303-2331`) —
fix already shipped with tests; first live exercise only. Broadcast overlap race (c5-4 record) —
accepted residual, do NOT add locking. Slow-client stall (c5-4 Q3) — accepted, no per-send
timeout. Browser reconnect family → c5-6; connection pill → c5-7; real-socket test → c5-8;
250 ms concurrent-push measurement → c10-3; Q3/AD-5 prose-narration debt + `dump_openapi.py`
changelog shape → C5 retro.

**Don't-break (scoped to this diff's files):** `test_errors.py` token/status pins (set stays at
ten); `test_committed_schema.py` no-securitySchemes + stripped-auto-422 pins;
`TestTheTwoCredentialsNeverTouch` (ws.py/state.py credential-name scans); `_handshake_is_
authorised` stays sync; `consume` keeps a single `.pop(`; SPA mount last; `PUT /api/active-deck`
behaviour byte-identical except the now-real 413 and its declaration; `GET /api/session`
declarations unchanged; the six existing routes' schema entries unchanged except the curated 413
removal.

### No UX surface

Backend + generated-types only. No `ui/src` edits beyond the two generated api files; no new
frontend deps; do not touch the lockfile. The MCP tool that calls this endpoint is **c6-1's**
(`client.py`'s docstring already homes the push half there — do not add it now). No skill files
ripple: `payload_too_large` and `/agent/events` appear in no `skills/*/SKILL.md` (verified).

### References

- Epic AC: `_bmad-output/planning-artifacts/epics-companion-app.md:2511-2543` (Story 5.5)
- SPINE: AD-5 (:150s), AD-7 (no-DB push path, caps), AD-8 (:197-209, count + outcome tokens),
  AD-12 (:272-290, no dummy endpoint), AD-16 (:329-352, 413 supersession); sequence diagram
  (`{clients: 1}`)
- PRD 2026-07-22: FR-06, FR-12, FR-13, NFR-01, NFR-03, NFR-05 (250 ms), CM-1
- EXPERIENCE.md: empty-push accepted; unknown-card degrades per entry; cross-tab all-clients
- `deferred-work.md`: the five triggered anchors above
- Manual-testing item **C6** (C3 retro, homed here): the token-auth surface exercised by hand —
  `GET /api/active-deck` 200, `PUT` without token 403; extend with `POST /agent/events` no-token
  403 / with-token 200 `{count}` against a running backend. Goes on the epic manual checklist,
  not dev-verified.

---

## Acceptance Criteria

**The endpoint (epic Story 5.5, verbatim intent)**
1. `POST /agent/events` exists in `src/companion/app/routes/agent_events.py`, registered in
   `build_app()` above `install_security`, declaring exactly
   `invalid_request | forbidden | payload_too_large | internal_error` (no 503).
2. A request carrying the agent token from the discovery file with a valid envelope is relayed
   to all connected clients via **`ws.broadcast()`** (no second fan-out loop) and the 200
   response reports the client count (FR-06; number semantics per Q1 ruling).
3. The response body is a new typed model in `contracts.py`, in the committed schema, with no
   payload echo.
4. Missing, wrong, or malformed token → 403 `{"reason": "forbidden"}` via the `AgentToken`
   dependency — no second auth check anywhere in the diff — and **nothing is broadcast**
   (proven with open sockets whose frame lists stay empty).
5. Over-cap handling per Q7's ruling — default recommendation: an envelope exceeding a c5-1
   **field** cap → 400 `invalid_request` (existing AD-16 handler); a body exceeding
   **`_MAX_ENVELOPE_BYTES`** → **413 `{"reason": "payload_too_large"}`** — rejected before full
   buffering, never truncated, nothing broadcast in either case.
6. An empty payload (zero suggestions, all-empty tiers) is accepted (200) and relayed.
7. The full six-kind union is the request body; card ids are never validated against the
   database — the route has no `DbSession`, no `src.data` import (AD-7; NFR-05).

**The cap mechanism**
8. The pre-parse cap bounds `POST /agent/events` AND `PUT /api/active-deck` with one mechanism;
   a lying Content-Length is caught by counted bytes; websocket scopes pass through.
9. If middleware-shaped, it sends `error_response(...)` — never raises (c1-5 ruling).
10. The ordering pin (`test_a_malformed_body_without_a_credential_is_still_forbidden`) is
    consciously dispositioned per Q3's ruling; any revision goes through review, not deletion.

**Schema & generation (AD-12)**
11. `app.openapi()` gains `/agent/events` with the `AgentEvent` union as request body; all
    envelope/payload/item models land in `components.schemas`; no dummy endpoint, no second
    generator, no `securitySchemes`.
12. `npm run gen:api` run; `openapi.json` + `types.d.ts` committed together;
    `test_committed_schema.py` pins updated (9 paths, new component set);
    `test_spa.py`'s differential router list gains its one line (the last named router tax);
    `dump_openapi.py` ledger appended.
13. `payload_too_large` is declared ONLY by operations that can answer it — the shared include
    sets curated (two call sites), the wart paragraph in `dump_openapi.py` updated.
14. Plugin mirror rebuilt and sha256-verified after the last edit of the story.

**Discipline**
15. Every `c5-5` prose prediction found in Task 0's grep is fulfilled and rewritten, or recorded
    as explicitly not this story's, in the same commit that lands the code.
16. Every rejection test has a paired acceptance; new guards carry R2 planted-red probes through
    the full suite; broadcast/count proofs are wire-level (open sockets), not `app.state` reads.
17. Suites green: Python from 2,769, frontend from 1,694, both strictly larger; mypy --strict,
    ruff, pre-commit clean; no integration-marked test added.

## Tasks / Subtasks

- [x] **Task 0 — verify the baseline** (AC: 15, 17): branch precondition; baseline table above;
  grep own key and list every hit with its disposition; read the ordering pin test and the five
  named source regions; confirm `gen:api` is a clean no-op before touching anything.
- [x] **Task 1 — the receipt model** (AC: 3): new wire model in `contracts.py` per Q1 ruling;
  WIRE-VISIBLE docstring discipline; doctest-safe `Example:`.
- [x] **Task 2 — the route** (AC: 1, 2, 4, 6, 7): `routes/agent_events.py`; `AgentToken` +
  `AgentEvent` body + one awaited `broadcast()`; include in `build_app()` with per-include
  `responses=`; no DB anywhere near it.
- [x] **Task 3 — the pre-parse cap** (AC: 5, 8, 9, 10): mechanism per Q2 ruling; both endpoints;
  Content-Length + counted bytes; 413 via send; disposition the ordering pin per Q3.
- [x] **Task 4 — 413 curation** (AC: 13): two call-site edits; PUT gains its route-level
  declaration if Q2's mechanism makes its 413 real; `dump_openapi.py` wart paragraph.
- [x] **Task 5 — tests** (AC: 4, 5, 6, 10, 16): `test_routes_agent_events.py` (auth trio →
  forbidden + nothing-broadcast; field-cap 400 vs byte-cap 413; empty-payload relay; two-socket
  relay + count; never-ran-lifespan behaviour); pin updates (`test_committed_schema.py`,
  `test_spa.py`); R2 probes planted, reverted, recorded.
- [x] **Task 6 — regenerate, reconcile, record** (AC: 11, 12, 14, 15, 17): `gen:api` + commit
  both artifacts; `dump_openapi.py` ledger before/after; plugin mirror + sha256 AFTER the last
  edit; rewrite every fulfilled prose prediction; deferred-work dispositions for the five
  triggered entries; full suites + gates; Dev Agent Record (incl. Dev Notes KB self-check);
  **set status `review` and STOP** — Brad runs the three-layer review and raises the PR.

## Open questions for Brad (recommendations first — rule before code)

1. **Which number does the response report, and under what name?** Recommend: **`broadcast()`'s
   delivered count**, field name `clients` (matches the SPINE sequence diagram `{clients: 1}`),
   model name `EventIngestReceipt`. Delivered is the truthful "how many browsers saw it" (the
   story's own want-clause); `connected_count` sampled around the awaited fan-out is racy in
   exactly the window c5-4's accepted residual lives in. Consequence: `connected_count`'s
   "number story 5.5 answers with" docstring gets corrected this story (item 1's rule); the
   property itself stays — c5-7's pill and future tooling still want it.
2. **Cap mechanism and home.** Recommend: a small pure-ASGI middleware (`install_security`'s
   module or its own `install_body_cap` beside it — inside the error middleware, outside the
   routers), enforcing Content-Length + counted-bytes against `contracts._MAX_ENVELOPE_BYTES`
   on http scopes with bodies, sending 413 itself. One mechanism, both endpoints, zero
   per-route code. Alternative (dependency-shaped, per-route `Request.stream()` reading) keeps
   the ordering pin green but duplicates per endpoint and leaves the buffering hole open on any
   future body route by default — recommend against.
3. **The ordering pin: contract or snapshot?** Recommend: **snapshot**. The pin recorded a
   measured FastAPI behaviour, not a designed promise; under Q2's middleware the observable
   order for oversized unauthenticated bodies becomes 413-before-403, which is the correct
   fail-cheap order. Revise the pin to assert the new total ordering (oversized → 413 even
   unauthenticated; well-sized malformed → the measured 400-vs-403 status quo), through review.
4. **413 curation shape.** Recommend: remove `payload_too_large` from both shared include sets;
   declare it per-route on the two body-bearing operations. Closes `dw:2333-2358` exactly as
   its own fix-shape describes.
5. **Route spelling.** Recommend: `router = APIRouter()` with the literal path `"/agent/events"`
   in the decorator (mirrors `ws.py`'s literal `/ws`; a one-route prefix object buys nothing).
   `agent` enters reserved prefixes by derivation automatically.
6. **Never-ran-lifespan behaviour.** Recommend: no hand-raised guard — `broadcast()` already
   returns 0 when the registry accessor finds nothing, and a 200 `{clients: 0}` from an
   unstarted app is unreachable in production (no port is bound). Copying `session.py`'s
   AttributeError idiom is defensible but adds a branch no test can reach through the wire.
7. **The epic AC vs the shipped error architecture — "any cap → 413" cannot both hold.** The
   epic (`epics-companion-app.md:2527-2530`) literally demands 413 for a payload exceeding
   *any* Story 5.1 cap. But field caps are pydantic constraints, a violation is a
   `RequestValidationError`, and the shipped AD-16 handler maps that to **400
   `invalid_request` app-wide** (confirmed empirically at c5-4). Making a 61-item list answer
   413 would mean introspecting pydantic error internals per-route to reclassify — brittle,
   and invisible to the end user anyway: AD-8's tool layer folds 400 and 413 into one
   `payload_rejected` token. Recommend: **ruled deviation** — field caps stay 400, 413 is the
   envelope byte cap; the epic AC's real teeth ("rejected, never truncated; a partial render
   is impossible") hold in both arms. If ruled the other way, the reclassification must key on
   constraint *class* (max_length/max_items/max bytes), never on message text, and needs its
   own R2 probes. Either ruling gets recorded against the epic AC in the story record (the
   "flag the impossible AC loudly" precedent, c1-9/c2-1).

## Dev Agent Record

### Agent Model Used

### Rulings

All seven open questions ruled by Brad on **2026-08-08**, before any code was written.

| Q | Ruling | Consequence carried into the diff |
|---|---|---|
| **Q1** — which number, under what name | **`broadcast()`'s delivered count**, field `clients`, model `EventIngestReceipt` | Matches the SPINE sequence diagram `{clients: 1}` and the story's own want-clause ("how many browsers saw it"). `connected_count`'s "the number story 5.5 answers with" line in `state.py` is **corrected this commit**; the property itself stays for c5-7's pill. |
| **Q2** — cap mechanism and home | **Pure-ASGI middleware**, its own `install_body_cap`, inside the error middleware and outside the routers | Content-Length + counted-bytes against `contracts._MAX_ENVELOPE_BYTES`; **sends** `error_response("payload_too_large")`, never raises (c1-5). One mechanism, both body endpoints, zero per-route code. Rejected alternative: per-route `Request.stream()` reading — duplicates per endpoint and leaves the buffering hole open by default on any future body route. |
| **Q3** — the ordering pin | **Snapshot** — revise the pin, through review | The pin recorded measured FastAPI 0.140 behaviour, not a designed promise. Under Q2 the observable order for oversized unauthenticated bodies becomes 413-before-403, which is the correct fail-cheap order. Pin revised to assert the new *total* ordering; never `git rm` (C4 retro item 13). |
| **Q4** — 413 curation shape | **Remove `payload_too_large` from both shared include sets**, declare per-route on the two body-bearing operations | Closes `dw:2333-2358` exactly as its own fix-shape describes. |
| **Q5** — route spelling | **`APIRouter()` with the literal path `"/agent/events"`** in the decorator | Mirrors `ws.py`'s literal `/ws`; a one-route prefix object buys nothing. `agent` enters `spa._reserved_prefixes` by derivation. |
| **Q6** — never-ran-lifespan behaviour | **No hand-raised guard** | `broadcast()` already returns 0 when the registry accessor finds nothing; a 200 `{clients: 0}` from an unstarted app is unreachable in production (no port bound). Copying `session.py`'s `AttributeError` idiom would add a branch no wire test can reach. |
| **Q7** — epic's "any cap → 413" vs shipped AD-16 | **Ruled deviation: field caps stay 400 `invalid_request`; 413 is the envelope byte cap alone** | The epic AC (`epics-companion-app.md:2527-2530`) literally demands 413 for a violation of *any* Story 5.1 cap, but field caps are pydantic constraints and the shipped AD-16 handler maps `RequestValidationError` to 400 app-wide. Honouring it literally would mean per-route introspection of pydantic error internals — brittle, and invisible to the end user anyway, since AD-8's tool layer folds 400 and 413 into one `payload_rejected` token. **The epic AC's real teeth hold in both arms**: rejected, never truncated; a partial render is impossible. Recorded loudly against the epic AC per the c1-9/c2-1 precedent. |

### Agent Model Used

claude-opus-5[1m] (Claude Code, VS Code extension)

### Debug Log References

**Task 0 baseline — one mismatch, recorded as a finding.** The Task 0 table pairs the full-suite
figure with the filtered command. Measured at `9b944a6`: `uv run pytest -q` gives **2,769 passed /
1 skipped** (2,770 collected); `uv run pytest -m "not integration"` deselects 54 and gives **2,715
passed / 1 skipped**. Both numbers are real and both appear in c5-4's record; the table attaches
the former to the latter's command. Frontend **1,694 / 65** and `gen:api` a clean no-op, both as
stated. No flake seen on the frontend at this baseline.

**R2 planted-red probes — five planted, all driven through the full suite via
`scripts.probe_harness`, all reverted, closing run `--expect-green` at 2,771 collected / 0 failed.**
Two of the five changed the diff, which is the point of doing them.

| # | Planted | Result | What it compares, and cannot see |
|---|---|---|---|
| 1 | Counted-bytes bound removed from `BodyCapMiddleware` (`Content-Length` check left intact) | **RED**, exactly 1 test — `test_a_lying_content_length_does_not_get_through` | Proves the bound that actually holds the ceiling is load-bearing and is not shadowed by the courtesy check. Cannot see whether the *byte count itself* is right, only that some counting happens. |
| 2 | `connected_count` sampled **after** the awaited broadcast | **GREEN — the probe falsified my test.** | See finding 2 below. Led to probe 2b and a new structural guard. |
| 2b | `connected_count` sampled **before** the broadcast | **RED**, exactly 1 test — `test_a_client_that_cannot_be_written_to_is_not_counted` | Proves the behavioural test discriminates against the *pre*-sample. Provably cannot see the post-sample; that arm is now closed by an AST guard instead. |
| 3 | `payload_too_large` restored to the shared `health_responses` set | **RED**, 3 curation tests + `test_openapi_contract.py`'s shipped-equals-live snapshot | Proves the curation is asserted document-wide, not just on the new route. Cannot see a declaration added directly at a route. |
| 4 | `raise CompanionError("payload_too_large")` in place of the send | **GREEN on the test I named**, red on 6 others | See finding 3 below. The named test was strengthened, then probe 4b re-run: **RED**, 7 tests. |
| 5 | `_credential: AgentToken` removed from the handler signature | **RED**, 6 tests including `test_nothing_is_broadcast_when_the_credential_is_refused` | Proves the gate is wired, not merely written, and that the nothing-broadcast proof is socket-level. Cannot see a *second* auth check added elsewhere; the AST scan covers that. |

`grep -rn "PROBE R2" src/ tests/ scripts/` → no residue.

**Frontend R2 not run** — `probe_harness` owns a pytest argv and cannot see vitest, as its own
docstring states; the frontend half stays ledgered and unowned.

### Completion Notes List

**Five findings, in descending order of how much they changed the work.**

1. **A fully valid envelope can exceed the byte cap — the two caps are not nested.** Measured while
   building the 413 tests: a `groups` envelope with every string at its field limit and every list
   at its length serialises to **104,067 bytes**, 1.6x the 64 KB ceiling, and violates no field cap
   at all. (`suggestions` maxes out at 28,940 — my first test fixture, which is why the assertion
   failed and the measurement happened.) So the byte cap can refuse a payload pydantic would
   accept; the two rejection classes overlap rather than partitioning the input, and the byte cap
   wins when both apply because it runs first. This made the 413 tests genuinely discriminating —
   a rejection of that body cannot be a field cap in disguise — and is recorded in
   `_MAX_ENVELOPE_BYTES`'s and `_MAX_CARD_ID_LENGTH`'s docstrings and in the ledger.
2. **My delivered-vs-connected discriminator did not discriminate, and the probe caught it.**
   Sampling `connected_count` *after* the awaited broadcast leaves the whole suite green — because
   `broadcast()` `discard`s each client it fails to write to, so by the time it returns the registry
   has already been pruned to exactly the delivered set. The two numbers genuinely agree there. The
   divergence Q1 is actually about is the *pre*-sample (planted, red, reverted). The post-sample arm
   cannot be closed behaviourally at all, so it is closed structurally: an AST guard refusing
   `connected_count` and `connection_registry` in the route module. Both wrong implementations are
   now closed, by two different mechanisms, and the test says why.
3. **`test_the_refusal_body_is_byte_identical_to_every_other_typed_error` passed under the exact
   failure it was written to catch.** Probe 4 planted a `raise` in place of the send; a raised
   `CompanionError` from user middleware becomes `500 {"reason": "internal_error"}` — which is
   *also* `no-store`, *also* `application/json`, and *also* a single-key `reason` body. Every
   assertion the test carried was satisfied. Asserting the **status and token** is what closes it;
   probe 4b then reddened it. Six other tests caught the plant regardless, so the c1-5 ruling was
   never unguarded — but the test claiming to prove it was decorative.
4. **Q3's predicted red never happened, so the disposition cost an addition rather than a
   revision.** `deferred-work.md` and the story both expected `BodyCapMiddleware` to redden
   `test_a_malformed_body_without_a_credential_is_still_forbidden`. It did not: the cap only
   reorders *oversized* bodies and both bodies that pin drives are a few dozen bytes. Both original
   assertions hold untouched; a third was added pinning that an oversized body answers 413 with no
   credential, so the total ordering (size → body → credential) is legible in one test. Nothing was
   deleted and nothing needed review as a revision. The pin *does* fire — probes 4 and 4b both red
   it — so it is doing real work, not merely surviving.
5. **`TierLetter` and `Confidence` did not become named components**, contrary to the story's
   prediction of "plus `TierLetter`/`Confidence` enums". Both are `Literal` aliases rather than
   `Enum` classes, so pydantic inlines each as a `const`/`enum` on the field that uses it. The
   generated TypeScript still gets a closed union at every use site; what it does not get is a
   reusable named type. Left alone — promoting them means reshaping two contract aliases to satisfy
   a schema-shape preference, which is not this story's call. The component count still landed on
   the predicted **30**. Related measurement: pydantic emits a single-valued `Literal` as `const`,
   not `enum`, which is what the frontend narrowing test asserts.

**Two AC deviations, both ruled by Brad before code (see Rulings).**

- **AC 5 / epic AC (Q7): field caps stay 400, not 413.** The epic
  (`epics-companion-app.md:2527-2530`) demands 413 for a payload exceeding *any* Story 5.1 cap.
  Field caps are pydantic constraints and the shipped AD-16 handler maps `RequestValidationError`
  to 400 app-wide. Honouring it literally means per-route introspection of pydantic error internals,
  keyed on constraint class, for a distinction AD-8's tool layer folds back into one
  `payload_rejected` token before an agent ever sees it. **Ruled deviation**; the AC's real teeth —
  *rejected, never truncated; a partial render is impossible* — hold in both arms, and both arms are
  proved side by side in `TestFieldCapsAnswerFourHundred` / `TestTheByteCapAnswersFourHundredAnd
  Thirteen`. Flagged loudly per the c1-9/c2-1 precedent.
- **AC 17's "frontend strictly larger" conflicts with the story's own "no UX surface".** A
  backend-only story has no reason to add frontend tests, and padding to satisfy a count would be
  the worse failure. Resolved honestly instead: `ui/tests/event-union-contract.test.ts` (12 tests)
  pins the one property that **only became checkable today** — that the generated union narrows in
  a single step, which is the entire justification c5-1's Q1 gave for choosing envelope-level
  discriminators over an envelope-over-payload-union. That claim was unverifiable for four stories
  because an unreferenced model never reaches `components.schemas`. It reads the committed JSON and
  imports no `ui/src` module, so it adds nothing to the `tsc -b` graph. Frontend 1,694 → **1,706**.

**Inherited deferrals — all five triggered entries dispositioned in `deferred-work.md`.**
(1) Pre-parse body cap — **closed**, built as `BodyCapMiddleware`, one mechanism, both endpoints.
(2) Ordering pin — **closed**, ruled snapshot, extended not revised (finding 4).
(3) Unreachable-413 wart — **closed**, two call-site edits exactly as c5-2's narrowing predicted;
zero body-less GETs now publish an unreachable 413, down from six. (4) Router tax — **paid out**;
c5-5 was the last story the entry named, and no key remains outstanding. (5) gen:api-between-plant
-and-probe ordering — **obeyed and confirmed**; it is why the four route-level schema assertions
were red until regeneration, and the R2 pass re-confirmed the pair from the other direction.
Not-triggered, one line each: `tsc -b` cascade — `npx tsc -b --force` exits **0**, and the one new
`ui/tests` file imports no src module; example-payload truncator — first live exercise, asserted in
both suites; broadcast overlap race and slow-client stall — accepted residuals, **no locking and no
per-send timeout added**.

**Unrelated pre-existing flake, recorded not fixed.** During probe 3's full-suite run,
`tests/integration/data/test_deck_repository.py::test_list_decks_with_strategy_field` failed. It
passes in isolation and stayed green across the other four full-suite probe runs and every full
suite this story ran. Nothing in this diff touches deck repositories. Intermittent and pre-existing;
flagged for the C5 retro rather than chased here.

**Discipline.** All 36 `c5-5` source hits from Task 0's grep reconciled — each either fulfilled and
rewritten in this commit, or explicitly recorded as falsified. Two were **falsified rather than
fulfilled** and say so: `errors.py:91` predicted c5-5 as the next `CompanionError` caller (it is the
opposite — a middleware that must send), and `main.py`'s "c5-5 adds its piece inside
`install_security`" was half right (a middleware, yes; a *security* line, no — `install_body_cap` is
its own call). Every rejection test has a paired acceptance; all relay and count proofs are
wire-level through real open sockets, never `app.state` reads.

**Manual-testing item C6** (from the C3 retro, homed here) goes on the epic checklist, not
dev-verified: against a running backend, `GET /api/active-deck` 200; `PUT` without token 403;
`POST /agent/events` without token 403; with token 200 `{"clients": N}`; and an over-64 KB body 413.

### File List

**New**
- `src/companion/app/body_cap.py`
- `src/companion/app/routes/agent_events.py`
- `tests/unit/companion/test_routes_agent_events.py`
- `ui/tests/event-union-contract.test.ts`

**Modified — source**
- `src/companion/contracts.py` (EventIngestReceipt; five prose reconciliations)
- `src/companion/app/main.py` (import, 4th include_router, `install_body_cap`, 413 curation at two call sites, prose)
- `src/companion/app/routes/active_deck.py` (route-level `payload_too_large` declaration, prose)
- `src/companion/app/security.py` (prose only — three predictions reconciled)
- `src/companion/app/state.py` (prose only — `connected_count` correction per Q1)
- `src/companion/app/ws.py` (prose only — two predictions reconciled)
- `src/companion/app/errors.py` (prose only — three predictions, one falsified)
- `src/companion/app/spa.py` (prose only — three predictions reconciled)

**Modified — tests**
- `tests/unit/companion/test_committed_schema.py` (paths 8→9, components 13→30, wart note)
- `tests/unit/companion/test_spa.py` (router list +1 line, reserved prefixes +`agent`)
- `tests/unit/companion/test_security.py` (middleware stack pin +`BodyCapMiddleware`)
- `tests/unit/companion/test_errors.py` (413 structural pin re-homed, prose)
- `tests/unit/companion/test_routes_active_deck.py` (ordering pin extended; Q3 disposition)
- `tests/unit/companion/test_routes_decks.py`, `test_routes_format_check.py` (413 dropped from non-vacuity sets)
- `tests/unit/companion/test_contracts.py` (TestTheIngestReceipt; prose)
- `tests/unit/companion/test_ws.py`, `test_routes_card_image.py` (prose only)

**Modified — generated / mirrored / docs**
- `ui/src/api/openapi.json`, `ui/src/api/types.d.ts` (regenerated together)
- `ui/src/api/schema.ts`, `ui/tests/wire-contract.test.ts`, `ui/src/components/StatePanel/states.ts` (prose only)
- `scripts/dump_openapi.py` (wart closed; ledger appended)
- `plugin/` (mirror rebuilt, sha256-verified after the last source edit)
- `_bmad-output/implementation-artifacts/deferred-work.md` (five dispositions)
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

### Change Log

| Date | Entry |
|---|---|
| 2026-08-08 | Branch `feat/companion-c5-5-agent-events-ingest` cut from `feat/companion-c5` at `9b944a6`. All seven open questions ruled by Brad before code. |
| 2026-08-08 | Task 0: baseline verified; table mismatch recorded (2,769 is the unfiltered figure, 2,715 the filtered one). 36 `c5-5` prose hits enumerated for reconciliation. |
| 2026-08-08 | Tasks 1–2: `EventIngestReceipt` minted; `POST /agent/events` shipped with `AgentToken` + the `AgentEvent` union + one awaited `broadcast()`; fourth `include_router`. |
| 2026-08-08 | Task 3: `BodyCapMiddleware` — pre-parse, Content-Length + counted bytes, sends never raises, both body endpoints. Q3 dispositioned: ordering pin extended, not revised (it never went red). |
| 2026-08-08 | Task 4: 413 curated to the two operations that can answer it; six body-less GETs stopped publishing an unreachable branch; `dump_openapi.py` wart paragraph closed. |
| 2026-08-08 | Task 5: five R2 probes through the full suite; two falsified my own tests and led to a new AST guard and a strengthened status assertion. All reverted; closing `--expect-green` clean. |
| 2026-08-08 | Task 6: `gen:api` regenerated and verified idempotent; schema 8→9 paths, 13→30 components; five deferred-work dispositions; plugin mirror rebuilt and sha256-verified after the last edit. |
| 2026-08-08 | Suites: Python **2,769 → 2,824** passed / 1 skipped (unfiltered); **2,715 → 2,770** with `-m "not integration"`. Frontend **1,694 → 1,706** across 65 → 66 files. mypy --strict, ruff, eslint, stylelint, `tsc -b --force`, pre-commit (incl. the plugin-sync hook) all clean; `gen:api` verified idempotent by hash. Status set to `review` — Brad runs the three-layer review and raises the PR. |
