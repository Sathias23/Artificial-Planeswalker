---
epic: c5
story: c5-3
work_branch: feat/companion-c5
story_branch: feat/companion-c5-3-websocket-upgrade
depends_on: >-
  c5-2 (merged, PR #54) — the `TicketStore` this story consumes from, the Q1 ruling that homes
  `Origin` on this upgrade, and the three ledgered obligations named on this story. c1-5 (merged) —
  the `HostValidationMiddleware` that already validates `websocket` scopes and closes 1008
  pre-accept; this story reuses it, never duplicates it (AD-5). c5-1 (merged, PR #53) — the probe
  harness every new guard must be proven through. c3-6/c3-7 (merged) — the injected-monotonic-clock
  idiom and `FakeClock` that make a 30 s TTL testable in zero wall-clock. c2-3 (merged) — the
  OpenAPI → TypeScript pipeline this story must prove it does NOT move.
baseline_commit: 5113478
---

# Story C5.3: Authenticated WebSocket upgrade with Host and Origin validation

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As Brad with other tabs open,
I want the companion's socket to refuse connections that didn't come from its own page,
so that a malicious local page cannot attach to my session and read what my agent is doing.

**✅ BRANCH PRECONDITION.** `feat/companion-c5` is at `5113478`, tree clean. Cut
`feat/companion-c5-3-websocket-upgrade` from it. Verify `git log --oneline -1
origin/feat/companion-c5` **before** `checkout -b`, not after.

**What this story really is.** One new module (`ws.py`), one pure predicate, one registration line —
and five things that are not.

---

1. **HALF THE STORY IS ALREADY SHIPPED.** `HostValidationMiddleware` is pure ASGI *specifically* so
   it sees `websocket` scopes (`security.py:154-157` names this story: *"c5-3's upgrade reuses this
   check rather than duplicating it, AD-5"*). A disallowed Host on a websocket scope already gets
   `{"type": "websocket.close", "code": 1008}` **before accept** — "the ASGI-legal denial; uvicorn
   renders it as an HTTP 403 handshake failure" (`security.py:217-221`), and
   `test_security.py:295-327` already pins both branches at the ASGI level because *"the `websocket`
   and `lifespan` branches have no route to drive them yet"* (`test_security.py:9`). This story does
   NOT write a Host check. It gives those branches a real route, and adds the two things the
   middleware cannot do: **Origin** and **consume**.

2. **THREE LEDGERED OBLIGATIONS ARE HOMED ON THIS STORY BY NAME.**
   (a) `deferred-work.md:5024-5036` — Brad's Q1 ruling at c5-2: the mint does NOT validate Origin;
   *"Home: c5-3 for the upgrade half, which is now the only half left open."*
   (b) `deferred-work.md:5074-5081` — `TicketStore.consume` has **zero production callers**; *"the
   story that calls consume must show the call sits in synchronous code and add a guard or test for
   it"* — an `await` slipped between validation steps would quietly break the no-lock argument
   (`state.py:43-61` spells out the three changes that break it: splitting the pop, making `consume`
   async, moving the store off the event loop).
   (c) `deferred-work.md:5041-5056` — `security.py:97,116` carry two `Example:` blocks executed by
   nothing; *"Home: unowned, most naturally c5-3, which edits `security.py`."* The prescribed honest
   fix is **one test that walks every `src/companion` module**, not two more bespoke lines.
   All three ledger entries are edited (closed or re-homed) **in the same commit** that discharges
   them — a disposition lives in the ledger, not only the story record (C4 retro standing agreement).

3. **THE EPIC SPECIFIES NO MECHANICS — Q1–Q3 MUST BE RULED BEFORE CODE.** Story 5.3's ACs
   (`epics-companion-app.md:2450-2477`) say "the upgrade is rejected" and nothing else: **no endpoint
   path** (the spine names only the module, `ws.py # upgrade + ticket consume + broadcast`,
   `ARCHITECTURE-SPINE:451`), **no ticket carriage** (query param vs subprotocol — nowhere in any
   artefact), **no close code**. Recommendations are in Open Questions; the shipped 1008-pre-accept
   precedent and the store's own indistinguishability rule (`state.py:349-351`: *"a caller that
   could tell them apart could probe the store"*) do most of the arguing.

4. **THIS IS A CONFIRMED-NEGATIVE SCHEMA STORY — c5-1's SHAPE, NOT c5-2's.** A FastAPI WebSocket
   route never reaches `app.openapi()` (OpenAPI does not model WS). `test_committed_schema.py` pins
   stay at **8 paths / 13 components**, and AC 17 is the inverse proof used at c5-1 and c3-6/7/8:
   run `npm run gen:api`, show both committed artifacts byte-identical. The `test_spa.py:324-328`
   hand-mirrored router list compares OpenAPI paths, so a WS-only router owes it **no** edit — but
   the registration still pays `main.py`'s ordering block (`:548-553`): the route must land **above
   `install_spa`'s catch-all mount**, because `test_spa.py:455-461` proves a websocket handshake
   that falls through to the mount dies on StaticFiles' `assert scope["type"] == "http"`.

5. **TWO GAPS THE SHIPPED CODE NAMES AS THIS STORY'S.** (a) The error net covers `http` scopes only
   — `UnhandledErrorMiddleware` passes `websocket` straight through (`errors.py:521-528`), so *"a
   fault while validating a handshake escapes raw — acceptable while nothing on the ws path can
   raise, and c5-3 owns the question when it adds the upgrade"* (`security.py:419-423`,
   `main.py:518-519`). Q6. (b) The agent token *"must not enter … a WebSocket frame (AD-5). … The
   WebSocket frame is c5-3's to pin when the socket exists — nothing guards it yet"*
   (`main.py:279-281`). AC 13 pins it structurally.

---

## Dev Notes

### Task 0 — verify before writing code, do not believe this file

Measured on `5113478`, 2026-08-08. Re-run every line; a mismatch is a finding, not a rounding error.

| Fact | Measured value | Command |
|---|---|---|
| Python tests | **2,650 collected** total (c5-2 record: 2,596 passed / 54 deselected) | `uv run pytest --collect-only -q \| tail -1` |
| Frontend tests | **1,694 passed / 65 files** (inherited from c5-2 — re-measure) | `cd ui && npx vitest run` |
| OpenAPI schema | **13 components, 8 paths** | `python -c` over `ui/src/api/openapi.json` |
| `gen:api` at baseline | expect a **clean no-op** | `cd ui && npm run gen:api` then `git status --porcelain` |
| Plugin mirror | **in sync today** — verify sha256 on every file this story touches | `shasum -a 256 src/companion/… plugin/server/src/companion/…` |
| starlette / fastapi / websockets | **0.48.0 / 0.140.0 / 16.1.1** installed; `wsproto` absent | `uv run python -c "import starlette, fastapi; …"` |
| `ui/node_modules` | re-measure presence; do NOT `npm install` or move the lockfile | `test -d ui/node_modules` |

**Grep your own key (C4 retro action item 6) — run 2026-08-08, 13 src/ui hits, all obligations,
none yet falsified:** `security.py:29` (imports the accessor, does not move the store), `:156`
(reuse the middleware), `:423` + `main.py:519` (the ws error gap — Q6), `security.py:436` +
`main.py:524` (the consume gates a handshake — **check after implementation whether the
route-handler shape falsifies the "inside install_security" framing; if so correct the prose in the
same commit, c3-9's rule, zero regeneration diff**), `errors.py:521` + `test_errors.py:565`
(websocket scopes pass through), `main.py:280` (agent-token-in-frame unguarded — AC 13 discharges),
`state.py:55` (don't pull async into the handshake), `:146` (c5-2 mints, c5-3 consumes),
`routes/session.py:21,38` (Origin homed here; c5-3 calls consume), `ui/README.md:52`, and
`test_routes_session.py:214-217` (the source-scan docstring naming this story).

### Where each piece goes — the shape to build

- **NEW `src/companion/app/ws.py`** — the spine's module (`ARCHITECTURE-SPINE:451`): an `APIRouter`
  with one `@router.websocket(...)` endpoint. Handler order: read Origin from headers → validate
  via the pure predicate → **then** consume the ticket → `await websocket.accept()` → drain loop
  until disconnect. Origin **before** consume: a rejected foreign handshake must not burn a ticket
  it happened to carry — burning is the residual exposure Q1 accepted at the *mint*; the upgrade
  should not add a second burner. Broadcast and the connection registry are **c5-4's**
  (`state.py:19-20` already reserves the registry's home) — do not scaffold them.
- **UPDATE `src/companion/app/security.py`** — one **pure** predicate beside `host_is_allowed`
  (e.g. `origin_is_allowed(origin: str | None, port: int | None) -> bool`): fail-closed on `None`
  (matching `host_is_allowed:111`'s shape), exact match after `.strip().lower()` against
  `http://127.0.0.1:{port}` / `http://localhost:{port}`, **actual bound port** from app state
  (c1-5's rule: never the configured default). NO module-level mutable state — the guard at
  `test_routes_active_deck.py:796-844` AST-walks this module for any mutable container and was
  probed against four plants; it must stay green untouched.
- **UPDATE `src/companion/app/main.py`** — include the ws router **above `install_spa`** (the
  ordering block at `:548-553`); correct any prose this story falsifies.
- **`state.py` — DO NOT TOUCH the mechanism.** `consume` stays synchronous (`state.py:43-61`);
  the store is reached via `ticket_store(app)` (`state.py:392`), imported — never moved, never
  wrapped in a second holder. Identifier bans still apply if you edit it at all:
  `{token, agent_token, credential, secret, mint_token}` (`test_routes_active_deck.py:724-752`).
- **NEW `tests/unit/companion/test_ws.py`** — no `tests/integration/companion/` exists and none
  may be created here: the one real-socket test is **c5-8** (AD-10, `epics:2611-2642`).
- **Mirror**: every touched `src/companion/**` file has a `plugin/server/src/companion/**` twin;
  the sync hook is NOT installed on this machine — run `uv run python -m scripts.build_plugin` and
  sha256-verify **after the last edit** (c5-1's falsified sha claim; c5-2 verified clean).

### The house idiom — follow it, do not invent

- **Rejection is send-don't-raise, pre-accept, code 1008**, exactly the shipped middleware's shape
  (`security.py:217-221`). Middleware and handshake gates never raise `CompanionError`
  (`errors.py:99-104`); there is no JSON body and **no new `ErrorReason` token** — the set is
  closed at ten and a token exists only to drive a UI state; ticket churn is designed to be
  invisible (`main.py:509-510`).
- **All rejections indistinguishable.** `consume` already refuses to say why (`state.py:349-351`).
  The upgrade must not leak more: same close code for no-ticket / unknown / expired / replayed /
  bad-Origin.
- **No security classes** — `HTTPBearer` / `APIKeyHeader` / `Annotated[str, Header()]` add
  `securitySchemes` and red `test_committed_schema.py:233`. Read headers from
  `websocket.headers`/scope by hand, as the middleware does.
- **AD-1 literal ban**: bare `60` and `15` are banned in `src/companion/**` outside `contracts.py`
  and have fired twice unpredicted. `1008`/`1011` are fine.
- **The TTL number stays off the wire and out of client-visible prose** (c5-2 review headline —
  "short-lived", never "30 seconds", in anything that ships).
- **Docstring truncation rule**: everything above the first Google section header ships to the wire
  on models AND routes alike. A WS endpoint has no OpenAPI surface, so ws.py's docstrings are free —
  but if you edit any wire-visible docstring elsewhere, regenerate both artifacts in the same
  commit.
- **Doctests**: any `Example:` block you write must be executed — AC 19's module walker makes that
  automatic.

### Testing the handshake — the idiom decision (Q7)

`httpx.ASGITransport` **cannot drive a websocket scope** (documented at `conftest.py:3-10`; it
speaks the ASGI request protocol only). Two candidates:
(a) **ASGI-level handshake helper** (recommended): a small conftest helper that runs a
`{"type": "websocket", …}` scope against the lifespan'd app and collects sent messages —
`test_security.py:295-327` already does exactly this against the middleware; the helper generalises
it through the real router. Stays async, stays in-process, keeps the single lifespan-entry idiom
(`async with lifespan(app)` + `app.state.bound_port = 54321` stamp).
(b) Starlette's `TestClient.websocket_connect` — works, but introduces a thread portal and a second
lifespan-entry idiom into a suite that deliberately has one.
Whichever is ruled, TTL-expiry tests use `FakeClock` (`conftest.py:483-535`) via the
constructor-monkeypatch pattern (`test_routes_card_image.py:1946`) — **a test that sleeps is a
defect**; both sides of the half-open boundary (`now < deadline`, at-deadline = expired) are
already pinned by unit tests and are not this story's to re-litigate.

### Inherited deferrals — R1 trigger-gated

**Triggered (full text above, headline item 2):** the Origin-on-upgrade half (dw:5024-5036), the
consume-atomicity guard (dw:5074-5081), the doctest walker (dw:5041-5056).

**Not triggered (one line + anchor each):** `errors.supported_methods` under a non-root Mount
(dw:5037-5040 — this story adds a route, not a Mount; adding a Mount would trigger it);
committed-schema/gen:api ordering sentence (dw:5058-5070 — informational; this story adds no
component, but its R2 pass must still run `gen:api` between plant and probe for any schema-visible
guard); EC-19 mint-then-expire-mid-handshake residue (c5-2:343 — client-side, **c5-6's**);
reconnect/refetch entries (dw:3386, 3397, 3483 — all homed **c5-6**); Q3-prose-sync and
dump_openapi-changelog (dw:5082-5091 — **C5 retro's**).

**Don't-break, scoped to this diff's files:** `test_security.py` scope tests (`:295-327`) and
`TestCorsIsDeliberatelyAbsent` (`:353-384` — no CORS middleware, ever); the four guards in
`test_routes_active_deck.py:724-844` (state.py identifier bans, shared-code-path ban, security.py
stores-nothing); `test_routes_session.py` in full — especially the Host/Origin source-scan
(`:211-249`): **do not touch `routes/session.py` at all** (nothing in this story needs to); the
`test_spa.py` reserved-prefix walk and `:455-461`; `test_committed_schema.py` 8/13 pins;
`test_openapi_contract.py` byte-compare; `test_app.py::test_startup_failure_propagates`.

### No UX surface, and no new libraries

No UI work: the epic splits the channel at the security seam — c5-6 owns the browser's
connect/reconnect loop, c5-7 owns the pill (`epics:778-780, 867-868`; `EXPERIENCE.md:141` tags the
pill c5-7). `ui/src` makes no WebSocket connection today (verified) and still won't after this
story. No new dependencies: `websockets>=12.0` is already declared (pyproject:61-63, present via
`uvicorn[standard]`), and the in-process tests need none of it.

### Source tree — what this story touches

NEW: `src/companion/app/ws.py` · `tests/unit/companion/test_ws.py` · mirror
`plugin/server/src/companion/app/ws.py`.
UPDATE: `src/companion/app/security.py` (pure predicate + prose) · `src/companion/app/main.py`
(include + ordering-block comment + prose corrections) · possibly `errors.py`/`state.py`
**prose only** (Q6/falsified predictions) · `tests/unit/companion/conftest.py` (handshake helper)
· `tests/unit/companion/test_routes_active_deck.py` **only if** extending the shared-code-path
guard family to ws.py is ruled to live there (AC 13; a fresh class in `test_ws.py` is equally
valid) · `deferred-work.md` (3 closures + any new entries) · `sprint-status.yaml` · mirrors of all
touched app files.

### References

- Story + ACs: `epics-companion-app.md:2450-2477`; epic header `:856-871`; NFR-01 `:137-142`.
- AD-5 verbatim: `ARCHITECTURE-SPINE.md:143-157`; module map `:448-462`; AD-10 `:227-240`;
  S-6 origin finding: `reviews/review-adversarial-seam.md:84-88`.
- Ledger: `deferred-work.md:5024-5036, 5041-5056, 5074-5081` (this story's three), `:5037-5040,
  5058-5070` (not triggered).
- Shipped code: `security.py:85, 91-135, 152-222, 419-439` · `state.py:36-61, 146-200, 286-392` ·
  `main.py:279-281, 446-559` · `errors.py:99-104, 500-528` · `routes/session.py:9-49`.
- Prior story: `c5-2-…md` — Dev Notes (idioms), AC 18 (the lock argument this story re-makes),
  Review Findings (the TTL-on-the-wire headline).

## Acceptance Criteria

### The upgrade

1. **Given** a WebSocket handshake at the ruled path (Q1) carrying a valid, unexpired ticket (Q2
   carriage) from an allowed Origin and Host, **when** it is processed, **then** the socket is
   established (`websocket.accept`) and the ticket is consumed and destroyed (AD-5): a second
   handshake replaying the same ticket is rejected.
2. **Given** a handshake with no ticket, an unknown ticket, an expired ticket (proven with
   `FakeClock`, zero wall-clock), or an already-consumed ticket, **when** it is processed, **then**
   the upgrade is rejected **pre-accept** with the ruled close code (Q3), and all four rejections
   are indistinguishable on the wire (same messages, same code).
3. **Given** a handshake from a disallowed Origin that carries a **valid** ticket, **when** it is
   rejected, **then** the ticket is **still alive** — a foreign page cannot burn tickets at the
   upgrade (Origin is checked before consume, and a test pins the ordering by observing the ticket
   still consumable afterwards).
4. **Given** an accepted socket, **when** the client sends frames, **then** the ruled Q5 behavior
   holds (recommendation: drained and ignored — the channel is one-way, AD-6) and the handler
   returns cleanly on client disconnect. No connection registry, no broadcast — c5-4's.
5. The endpoint is registered **above `install_spa`'s mount**; a websocket handshake to the ruled
   path no longer reaches StaticFiles. `test_spa.py:455-461`'s pin of the fall-through behavior for
   *unreserved* paths stays green; the plain-HTTP behavior of the ruled path is pinned by a test
   (whatever it is — SPA fallback or typed 404 — it must be deliberate, not discovered).

### Host and Origin (AD-5, NFR-01)

6. Host validation on the upgrade **is the c1-5 middleware, reused not duplicated**: neither ws.py
   nor any new code re-checks Host, and a disallowed-Host handshake **through the real route** is
   closed 1008 pre-accept — the first route-driven proof of `test_security.py:9`'s promise.
7. The `Origin` header is validated against the app's own origin: exactly
   `http://127.0.0.1:{bound_port}` and `http://localhost:{bound_port}`, actual bound port from app
   state (never the configured default), match after `.strip().lower()`.
8. A missing `Origin` header is ruled by Q4 (recommendation: **rejected, fail-closed**, matching
   `host_is_allowed`'s `None` handling; c5-8's real client can set the header explicitly).
9. The Origin decision is a **pure predicate in `security.py`** beside `host_is_allowed`, with no
   module-level state — `test_routes_active_deck.py:796-844` (stores-nothing) passes unmodified.
10. Both checks are required and independent: tests prove a good-Origin/bad-Host handshake and a
    good-Host/bad-Origin handshake are each rejected (Host identifies what was addressed, Origin
    identifies the calling page — `epics:2466-2469`).
11. The socket's bind address is `127.0.0.1` only (NFR-01): this story adds **no** bind surface —
    the endpoint rides the existing server (c1-3's bind), and a test or Task 0 check verifies the
    existing pin still holds rather than adding code.

### The two credentials that never touch (AD-5)

12. The ticket reaches the handler through `ticket_store(app)` — the store is not moved, not
    wrapped, not duplicated; `state.py`'s mechanism is untouched.
13. A structural guard proves `ws.py` shares no code path with the agent token: its identifiers are
    disjoint from `{discovery, mint_token, agent_token, presented_credential,
    agent_token_is_valid, require_agent_token, AgentToken, _AUTHORIZATION_HEADER}` — the same shape
    as `test_routes_active_deck.py:754-794` — discharging `main.py:279-281`'s "nothing guards it
    yet". Non-vacuous: asserts the ws module's own expected identifiers are present.

### Atomicity, argued against the real handshake (dw:5074-5081)

14. The `consume` call sits in **synchronous code**: no `await` between the Origin decision and the
    pop, `consume` is not awaited, and `TicketStore.consume` remains a plain function. A guard
    pins this (at minimum: `not inspect.iscoroutinefunction(TicketStore.consume)` plus an AST
    assertion that ws.py's consume call is not inside an `Await` node), and the handler's own
    docstring re-makes the no-lock argument against the real code, citing `state.py:43-61`.
15. The `deferred-work.md:5074-5081` entry is closed in the same commit.

### The error gap (Q6 — the question this story owns)

16. The ruled disposition of the raw-escape gap is implemented (recommendation: the handler is
    fail-closed — an unexpected exception closes 1011 pre- or post-accept rather than escaping;
    `UnhandledErrorMiddleware` stays http-only). Whatever is ruled, the three prose sites that
    describe the gap as open (`security.py:419-423`, `main.py:518-519`, `errors.py:521-523`) are
    corrected in the same commit (c3-9's rule), at zero regeneration cost.

### The confirmed negative (schema)

17. `npm run gen:api` leaves `ui/src/api/openapi.json` and `types.d.ts` **byte-identical**;
    `test_committed_schema.py` stays at 8 paths / 13 components untouched; no `securitySchemes`
    appears. The WS endpoint has no OpenAPI surface, proven not assumed.

### Prose kept honest

18. Every shipped prediction this story fulfils or falsifies is reconciled in the same commit:
    `state.py:146`'s banner ("c5-3 consumes") now true; `security.py:29-30, 436` and
    `main.py:524`'s framing checked against the real shape and corrected if wrong; no
    forward-looking claim about c5-4/c5-5 is added that this story cannot verify.
19. The doctest walker lands: **one test that runs doctests over every `src/companion` module**
    (`doctest.testmod`, non-vacuity `attempted > 0` where blocks exist), executing `security.py`'s
    two `Example:` blocks; `deferred-work.md:5041-5056` closed in the same commit.
20. The Origin ruling's ledger entry (`dw:5024-5036`) is annotated closed — both halves now ruled.

### Tests, record and gates

21. New coverage includes, at minimum: accept+consume happy path; replay rejected; expired via
    `FakeClock`; missing/unknown ticket; bad Origin with live-ticket proof (AC 3); missing Origin
    per Q4; bad Host through the real route; both AC 10 cross-pairings; post-accept Q5 behavior;
    every rejection test paired with an acceptance from the same call site (non-vacuity).
22. **R2**: every NEW guard is planted red and proven through the FULL suite via
    `uv run python -m scripts.probe_harness --expect-red '<node-id>'`, reverted, with one line per
    guard on what it compares and what it cannot see. Schema-visible plants run `gen:api` between
    plant and probe.
23. Gates, all green before review: `uv run ruff check . && uv run ruff format --check .`;
    `uv run mypy src/` and `uv run mypy src/ --platform win32`; `uv run pytest -m "not
    integration"`; `cd ui && npm run typecheck && npx vitest run && npm run build` (no TS changes
    expected — the run is the proof).
24. Plugin mirror rebuilt (`uv run python -m scripts.build_plugin`) and sha256-verified on every
    touched file **after the last edit**.
25. **R1 self-check**: Dev Notes measured in KB against C4's 41 KB average and recorded in the
    completion notes; every inherited disposition accounted for (triggered / not-triggered /
    don't-break).
26. `sprint-status.yaml` updated with the story record; new deferrals (if any) ledgered with homes.

## Tasks / Subtasks

- [x] **Task 0 — verify** (AC: all): branch precondition; re-measure every Task 0 row; grep
  `c5-3` and reconcile the 13 hits; confirm rulings on Q1–Q7 are recorded below before any code.
- [x] **Task 1 — Origin predicate** (AC: 7, 8, 9): pure function in `security.py`, unit tests
  beside the `host_is_allowed` ones, stores-nothing guard untouched.
- [x] **Task 2 — `ws.py` handler** (AC: 1, 2, 3, 4, 14, 16): Origin → consume → accept → drain;
  pre-accept 1008 rejections, indistinguishable; fail-closed per Q6 ruling; no-lock argument in
  the docstring.
- [x] **Task 3 — registration** (AC: 5, 6, 11): include above `install_spa`; ordering-block
  comment; route-driven Host tests; bind-address check.
- [x] **Task 4 — handshake test helper** (AC: 21, per Q7 ruling): conftest helper generalising
  `test_security.py:295-327`; `FakeClock` wiring for expiry.
- [x] **Task 5 — guards** (AC: 13, 14, 22): agent-token disjointness for ws.py; sync-consume
  guard; probe-harness proof for each, full suite, plant lines recorded.
- [x] **Task 6 — doctest walker** (AC: 19): one module-walking test; delete nothing.
- [x] **Task 7 — confirmed negative** (AC: 17): `gen:api`, byte-identical proof pasted.
- [x] **Task 8 — prose + ledger** (AC: 15, 16, 18, 19, 20): correct falsified/fulfilled
  predictions; close the three ledger entries; same commit as the code that discharges each.
- [x] **Task 9 — mirror + gates + record** (AC: 23, 24, 25, 26): build_plugin + sha verify after
  last edit; all gates; R1 KB self-check; sprint-status.

### Review Findings

Three layers (Blind Hunter, Edge Case Hunter, Acceptance Auditor) run blind to each other. 15 raw
findings; the top defect was independently caught by all three, one of them via a live repro
(monkeypatched `accept()` to raise, drove a real handshake through `build_app()`, watched the
exception escape uncaught).

- [x] [Review][Patch] `websocket.accept()` and the plain 1008 rejection close are the only close
  paths in `websocket_upgrade` not wrapped for exception-safety, contradicting the module's own
  "Both phases are wrapped" claim and AC 16's fail-closed requirement [src/companion/app/ws.py:300-304]
  — fixed: `accept()` now has its own try/except closing 1011 via `_close_quietly`, and the plain
  1008 reject now goes through `_close_quietly` too. New regression test
  `test_a_fault_accepting_the_socket_closes_1011_pre_accept` in `test_ws.py`.
- [x] [Review][Patch] `except WebSocketDisconnect` around the drain loop is unreachable, and its
  justifying comment misstates Starlette 0.48's actual `receive()` behavior (verified against
  installed source: raw `receive()` returns the disconnect message rather than raising; only the
  `receive_text`/`receive_bytes`/`receive_json` wrappers raise `WebSocketDisconnect`)
  [src/companion/app/ws.py:307-311] — fixed: dead branch removed, folded into the single
  `except Exception` fault path; unused `WebSocketDisconnect` import dropped.
- [x] [Review][Patch] `Origin` header ambiguity (a duplicated header) is read via `.get()`
  (silently takes the first), unlike `Host`'s explicit "reject if more than one" handling in the
  same module family — no live exploit path since browsers cannot send a duplicate `Origin`
  header, but a real inconsistency against the docstring's claimed Host/Origin symmetry
  [src/companion/app/ws.py:196; src/companion/app/security.py origin_is_allowed] — fixed:
  `_handshake_is_authorised` now reads `websocket.headers.getlist(_ORIGIN_HEADER)` and refuses
  ambiguity, mirroring `security.py::_host_headers`.
- [x] [Review][Patch] `conftest.py`'s `drive_handshake` test helper silently builds a
  `127.0.0.1:None` host/origin header when `bound_port` isn't stamped before use, which would mask
  a test-setup mistake as an unrelated rejection result [tests/unit/companion/conftest.py:211-218]
  — fixed: asserts `port is not None` before building headers.

## Open questions for Brad

Rule before dev-story; recommendations follow the code's own precedents.

- **Q1 — endpoint path.** Nothing specifies it. **Recommend `/ws`**: matches the spine's module
  name, stays out of `/api`'s REST namespace (this is not a REST endpoint and has no OpenAPI
  surface). Cost: a plain HTTP `GET /ws` falls through to the SPA mount and serves index.html —
  harmless, but AC 5 pins whichever behavior falls out. Alternative `/api/ws` would give plain-GET
  a typed 404 instead; pick one.
- **Q2 — ticket carriage.** Nothing specifies it. **Recommend query parameter** (`/ws?ticket=…`):
  the browser `WebSocket` API cannot set arbitrary headers; the subprotocol hack abuses
  `Sec-WebSocket-Protocol` and echoes the ticket back in the response header. Residual: uvicorn's
  access log records the path+query — argued acceptable because the ticket is single-use, so a
  logged ticket is by construction a spent one (and the agent token's no-log rule is about the
  token, not the ticket). If ruled unacceptable, subprotocol carriage is the fallback.
- **Q3 — close code.** **Recommend 1008 (policy violation), pre-accept, for every rejection** —
  the shipped Host-middleware precedent (`security.py:217-221`), indistinguishable across reasons.
  1011 only for the Q6 fail-closed internal-error path.
- **Q4 — missing Origin.** **Recommend reject (fail-closed)**, matching `host_is_allowed`'s `None`
  handling. Browsers always send Origin on WS; c5-8's real-socket client sets it explicitly;
  anything else has no business here.
- **Q5 — client→server frames after accept.** **Recommend drain and ignore** until disconnect: the
  channel is one-way (AD-6), closing on chatter would turn an innocent client bug into a reconnect
  storm, and c5-4 owns what the connection does next.
- **Q6 — the raw-escape gap.** **Recommend fail-closed in the handler** (unexpected exception →
  close 1011), keeping `UnhandledErrorMiddleware` http-only — extending it to ws scopes would give
  it a second shape for one caller. The three prose sites are corrected either way.
- **Q7 — handshake test idiom.** **Recommend the ASGI-level helper** (generalising
  `test_security.py:295-327` through the real router) over Starlette's `TestClient` — keeps the
  suite's single lifespan-entry idiom and stays portal-free.

## Dev Agent Record

### Agent Model Used

claude-opus-5 (Claude Code, `bmad-dev-story`)

### Rulings — Q1–Q7 (Brad, 2026-08-08, before any code)

**All seven ruled on the story's own recommendation.**

| Q | Ruling |
|---|---|
| Q1 endpoint path | **`/ws`** — the spine's module name, outside `/api`'s REST namespace. |
| Q2 ticket carriage | **Query parameter `?ticket=…`** — the browser `WebSocket` API cannot set headers; a logged ticket is by construction a spent one. |
| Q3 close code | **1008 pre-accept for every rejection**, indistinguishable across reasons. |
| Q4 missing `Origin` | **Reject, fail-closed**, matching `host_is_allowed`'s `None` handling. |
| Q5 client→server frames | **Drain and ignore** until disconnect (one-way channel, AD-6). |
| Q6 raw-escape gap | **Fail-closed in the handler** — unexpected exception closes 1011; `UnhandledErrorMiddleware` stays http-only. |
| Q7 handshake test idiom | **ASGI-level helper** generalising `test_security.py:295-327`, not Starlette's `TestClient`. |

### Debug Log References

**Task 0 — every row re-measured on `5113478`, all matched.** 2,650 Python collected · 1,694
frontend / 65 files · 13 components / 8 paths / no `securitySchemes` · `gen:api` a clean no-op ·
plugin mirror sha256-identical · starlette 0.48.0 / fastapi 0.140.0 / websockets 16.1.1, `wsproto`
absent · `ui/node_modules` present · branch precondition confirmed (`origin/feat/companion-c5` at
`5113478`, checked **before** `checkout -b`). One correction: the `c5-3` grep returns **14** src/ui
hits, not 13 — `test_routes_session.py:24` ("no wire surface until c5-3") is the extra. All 14
reconciled; two falsified (below), the rest fulfilled or unaffected.

**R2 — 14 new guards, each planted red through the FULL 2,669-test suite via
`scripts/probe_harness.py --expect-red`, every plant reverted.**

| # | Guard | What it compares | What it cannot see |
|---|---|---|---|
| G1 | `test_ws_py_contains_no_host_check_of_its_own` | ws.py's AST against `host_is_allowed` / `allowed_authorities` / `HostValidationMiddleware`, plus a bare `"host"` string constant | a check spelled in names it does not know — hence the behavioural pair beside it |
| G2 | `test_the_ws_module_names_no_agent_credential` | ws.py's AST against the eight agent-token reachability names | `getattr(app.state, "agent_" + "token")`-style indirection (the residual its `state.py` sibling also carries) |
| G3 | `test_the_upgrade_reaches_the_store_through_the_one_accessor` | that ws.py never *calls* `TicketStore(...)` | a store reached through a helper in another module |
| G4 | `test_the_consume_call_site_is_not_inside_an_await` | the gate is an `ast.FunctionDef`, not `AsyncFunctionDef`, and holds no `Await` node | a suspension *outside* the gate — impossible only because both decisions are inside it, which its non-vacuity sibling pins |
| G5 | `test_consume_is_still_a_plain_function` | `inspect.iscoroutinefunction(TicketStore.consume)` | a synchronous `consume` that delegates to an async helper |
| G6 | `test_the_pop_is_still_one_statement` | `consume`'s source: exactly one `.pop(`, no `del ` | a split expressed without the word `del` |
| G7 | `test_no_connection_registry_was_scaffolded` | ws.py's `Name` nodes against registry vocabulary + `state.ConnectionRegistry` absent | a registry under a name nobody would guess |
| G8 | `test_ws_py_opens_no_socket_of_its_own` | ws.py's AST against `socket`/`uvicorn`/`serve`/`bind`/`listen` | a bind reached through a third module |
| G9 | `test_the_route_is_registered_before_the_spa_mount` | the mount's **frozen** `_reserved_prefixes` contains `ws` — which it can only do if the include ran above `install_spa` | nothing about *which* route claimed the prefix |
| G10 | `test_every_example_in_every_companion_module_passes` | `doctest.testmod` over every discovered `src/companion` module | examples marked `# doctest: +SKIP` |
| G11 | `test_the_error_middleware_is_still_http_only` | the literal scope test in `UnhandledErrorMiddleware.__call__`'s source | a websocket branch added elsewhere in the class |
| G12 | `test_the_origin_set_is_the_authority_set_with_a_scheme` | `allowed_origins(p)` equals `allowed_authorities(p)` prefixed, on three ports | a divergence in the *comparison* rather than the set — which its predicate-level sibling covers |
| G13 | `test_the_refusals_are_byte_identical_to_one_another` | the whole sent-message list of five refusals, `repr`-compared | anything about the log, deliberately |
| G14 | `test_a_rejected_foreign_handshake_leaves_the_ticket_alive` | the ticket is still consumable after a foreign-Origin refusal | the *reason* the ordering holds — it observes the effect only |

**G13's first plant did not fire, and the miss is the useful part.** The plant added a distinct
`logger.warning` for the no-ticket case and nothing else. The harness correctly reported green:
the guard compares the **wire**, and the log is not the wire — which is exactly the property the
module docstring claims ("the *log* may distinguish, and does"). Re-planted as a genuine violation
(close `1003` for the no-ticket case instead of `1008`) and it fired, reddening
`test_all_five_are_refused` alongside it. Recorded rather than quietly re-run: a plant that fails
to fire is evidence about the plant when the guard is measuring something the plant did not touch.

**Honest collateral in the probe output**, all expected: G2 also reddened the pre-accept-1011 test
(reading `agent_token` on an unstarted app returns `None` and short-circuits before the fault);
G4 and G14 each reddened their own non-vacuity sibling; G5 reddened six tests because an `async`
`consume` breaks the handshake outright; G9 reddened four mount-ordering pins across three modules,
which is `main.py`'s ordering block being right; G12 reddened the two port-80 assertions.

### Completion Notes List

**All seven open questions ruled by Brad before any code, every one on the story's own
recommendation** (table above): `/ws`, query-param carriage, 1008 for every rejection, missing
`Origin` rejected, drain-and-ignore, fail-closed 1011 in the handler, ASGI-level test helper.

**The story's own headline held: half the security was already shipped, and none of it was
rewritten.** `ws.py` contains no `Host` check, proven structurally (G1) and behaviourally — a
rebound-Host handshake **through the real route** is closed 1008 pre-accept and the handler never
runs, which is the first route-driven proof of the promise `test_security.py:9` recorded when it
said *"the `websocket` and `lifespan` branches have no route to drive them yet"*.

**TWO PREDICTIONS FALSIFIED, both corrected in this commit (c3-9's rule).**

1. **`main.py:524` and `security.py:436` predicted c5-3 would be a *security line*.** It is not.
   The upgrade is a plain `@router.websocket` route, so c5-3 added a **third** `include_router`
   above the ordering block, exactly as c5-2 did — and `install_security` is *still* the one
   security wiring call, now two stories past the one that was supposed to grow it. The correction
   states the lesson rather than just the fact, because c5-5 still holds the same prediction:
   *gating a handshake* describes what a check does, *middleware* describes where it must live, and
   they are independent. Only the `Host` check — which must see scopes no route claims — genuinely
   needs a middleware position. Zero regeneration diff (both are `#`/docstring in non-wire
   positions), c3-9's rule holding for a fifth story.
2. **Q1 predicted a plain `GET /ws` would fall through to the SPA and serve `index.html`. It
   answers the typed 404 instead** — and this is the finding worth carrying forward.
   `spa._reserved_prefixes` derives reservations from the live **route table** and `_route_paths`
   descends into `WebSocketRoute` exactly as into `Route`, so registering the router reserved the
   segment `ws` and the mount declines it. The consequence: **the story's claim that a WS-only
   router owes `test_spa.py` no edit is half wrong.** True of the hand-mirrored router list
   (`test_the_schema_is_unchanged_by_installing_the_mount` compares `openapi()["paths"]` and was
   genuinely untouched); **false** of `test_the_reserved_prefixes_are_derived_from_the_route_table`,
   which went red naming `ws` — the mechanism working as its own failure message describes. The
   behaviour that fell out is the better one and is pinned deliberately per AC 5.

**THE ATOMICITY OBLIGATION IS DISCHARGED STRUCTURALLY, NOT BY PROMISE.** `state.py` argued
`consume` needs no lock because the compare-and-set is one `dict.pop` with no `await` between read
and delete; that argument had **zero production callers** until this story. The one caller is
`_handshake_is_authorised`, a **plain `def`** holding the *entire* handshake decision — read
`Origin`, evaluate, reach the store, pop. A plain `def` cannot contain an `await`, so the property
is enforced by the language: reintroducing a suspension point requires changing the `def` to
`async def`, which is one of the three breakers `state.py` already names. Four guards pin it, plus
a fifth on the first breaker (the pop is still one statement).

**ORIGIN BEFORE CONSUME, PINNED BY EFFECT RATHER THAN BY LINE NUMBER.** A refused foreign
handshake carrying a *valid* ticket leaves that ticket **still consumable** — asserted twice, once
on the wire (the same ticket then gets a socket) and once on `resident_count`. Burning is the
residual exposure c5-2's Q1 accepted at the mint; the upgrade declines to add a second burner.

**Q6's gap is closed locally and the middleware did not grow.** Both sides of `accept` are wrapped:
a fault while validating closes 1011 pre-accept (driven by *real code* — an app whose lifespan
never ran has no store, and `_store` raises exactly as `routes/session.py`'s does), a fault after
accept closes 1011 on the live socket. `UnhandledErrorMiddleware` stays http-only, guarded (G11).
All three prose sites that described the gap as open are corrected.

**THE DOCTEST LEDGER ENTRY IS CLOSED IN THE GENERALISED SHAPE IT ASKED FOR**, not the two-line one:
one test **discovers** every module under `src/companion` from the tree and runs `doctest.testmod`
over all of them, so a module added tomorrow is covered with no edit. `security.py`'s two blocks
now execute; c5-1's and c5-2's per-module tests are **not deleted** (a passing guard is not removed
for being redundant). Non-vacuity on both halves: the walk found >10 modules, and `attempted > 0`.

**Confirmed negative, proven not assumed:** `npm run gen:api` leaves `openapi.json` and `types.d.ts`
byte-identical (re-run after the last edit), `test_committed_schema.py` stays at 8 paths / 13
components untouched, no `securitySchemes`, and the SPA bundle is unchanged (`npm run build`
produced a zero-diff tree). A WebSocket route has no OpenAPI operation, which is also why the
include carries no `responses=`.

**ONE NEW DEFERRAL, homed and Medium.** The Vite dev proxy rewrites `Host` but not `Origin`, so once
c5-6 adds `/ws` to `PROXIED_PATTERNS` a proxied handshake will arrive with a passing `Host` and a
failing `Origin`. **Nothing is broken today, measured rather than assumed** — `/ws` is deliberately
absent from the proxy. Ledgered with three candidate fixes (the worst of which, a dev-flag widening
of `allowed_origins`, is named as worst) and recorded in `ui/README.md` beside the `changeOrigin`
explanation so it is found by someone reading the proxy. A second, informational entry records the
`test_spa.py` prediction correction for c5-4/c5-5.

**Deviations: none.** Every AC discharged. `routes/session.py` untouched as instructed; the four
`test_routes_active_deck.py` guards, `TestCorsIsDeliberatelyAbsent`, `test_routes_session.py` in
full, and `test_spa.py:455-461` all pass **unmodified**.

**Measurements.** Python 2,596 → **2,669 passed** (+73), 54 deselected, zero regressions; no test
sleeps — the 30 s TTL costs zero wall clock via `FakeClock`, asserted by `clock.slept == []`.
Frontend **1,694 passed / 65 files, unchanged** (no `ui/src` change, and the run is the proof);
`tsc -b --force` clean. `ruff check` + `ruff format --check` clean; `mypy src/` and
`mypy src/ --platform win32` both clean. Plugin mirror rebuilt and sha256-verified on all 21
package files **after the last edit** — all five touched files identical.

**R1 self-check: Dev Notes 10.4 KB against C4's 41 KB average — a quarter, and the smallest of the
five C5-era stories.** Inherited dispositions all accounted for: **3 triggered** (Origin-on-upgrade
dw:5024-5036, consume-atomicity dw:5074-5081, doctest walker dw:5041-5056) — all three closed in
this commit; **5 not-triggered** (`supported_methods` under a non-root Mount — this story adds a
route, not a Mount; committed-schema/`gen:api` ordering — informational, and no schema-visible
guard was planted so no `gen:api` was needed between plant and probe; EC-19 mint-then-expire — c5-6's;
reconnect/refetch — c5-6's; Q3-prose-sync and dump_openapi-changelog — C5 retro's); **all
don't-breaks green and unmodified.**

### File List

**New**
- `src/companion/app/ws.py`
- `tests/unit/companion/test_ws.py`
- `plugin/server/src/companion/app/ws.py` *(mirror)*

**Modified**
- `src/companion/app/security.py` — `_ORIGIN_SCHEME`, `allowed_origins`, `origin_is_allowed`; two
  prose corrections (the Q6 gap; the twice-wrong middleware-shape prediction)
- `src/companion/app/main.py` — `ws_router` import + `include_router` above `install_spa`;
  ordering-block correction
- `src/companion/app/state.py` — prose only (the banner is now true; the no-lock argument records
  its production caller)
- `src/companion/app/errors.py` — prose only (the websocket passthrough is permanent, not a gap)
- `tests/unit/companion/conftest.py` — `drive_handshake` ASGI handshake helper, `_OMIT`,
  `_NORMAL_CLOSURE`
- `tests/unit/companion/test_security.py` — `_ORIGIN_MATRIX`, `TestTheAllowedOrigins`,
  `TestOriginIsAllowed`
- `tests/unit/companion/test_spa.py` — `ws` added to the reserved-prefix set, with the correction
  recorded
- `ui/README.md` — the `Origin`/dev-proxy consequence, homed on c5-6
- `_bmad-output/implementation-artifacts/deferred-work.md` — 3 entries closed, 2 added
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — story record
- `plugin/server/src/companion/app/{security,main,state,errors}.py` *(mirrors)*

### Change Log

| Date | Change |
|---|---|
| 2026-08-08 | Q1–Q7 ruled by Brad, all on the story's recommendation; recorded before any code. |
| 2026-08-08 | Task 1: `origin_is_allowed` + `allowed_origins` in `security.py`, derived from `allowed_authorities` so the two checks cannot drift. |
| 2026-08-08 | Task 2: `ws.py` — Origin → consume → accept → drain; 1008 pre-accept for every rejection, indistinguishable; fail-closed 1011 both sides of accept. |
| 2026-08-08 | Task 3: registered above `install_spa`; ordering-block prose corrected (c5-3 is a route, not a security line). |
| 2026-08-08 | Task 4: `drive_handshake` ASGI helper in conftest (Q7), keeping the suite's single lifespan-entry idiom. |
| 2026-08-08 | Task 5: 14 new guards, each planted red through the full suite and reverted; G13 re-planted after its first plant proved to be a non-violation. |
| 2026-08-08 | Task 6: package-wide doctest walker; `security.py`'s two `Example:` blocks now execute. |
| 2026-08-08 | Task 7: confirmed negative — `gen:api` byte-identical, 8/13 pins untouched, no `securitySchemes`. |
| 2026-08-08 | Task 8: three ledger entries closed, two added; five prose sites reconciled (two falsified, three fulfilled). |
| 2026-08-08 | Task 9: mirror rebuilt + sha256-verified on 21 files after the last edit; all Python and frontend gates green. |

## Sprint journal (moved verbatim from sprint-status.yaml, 2026-08-25)

CODE-REVIEWED 2026-08-08 -> done. Three layers (Blind Hunter, Edge Case Hunter, Acceptance Auditor), run blind to each other; 15 raw findings, 4 patch, 0 decision-needed, 0 defer, 11 dismissed. HEADLINE, and all three layers independently converged on it (one via a live repro — monkeypatched `accept()` to raise and drove a real handshake through `build_app()`, watched the exception escape uncaught): `websocket.accept()` and the plain 1008 rejection close were the only two close paths in `websocket_upgrade` not wrapped for exception-safety, contradicting the module's own "Both phases are wrapped" claim and AC 16's fail-closed requirement. FIXED: `accept()` now has its own try/except closing 1011 via `_close_quietly`, and the 1008 reject now goes through `_close_quietly` too; new regression test `test_a_fault_accepting_the_socket_closes_1011_pre_accept`. Three more patches applied: the `except WebSocketDisconnect` drain-loop handler was dead code with a comment that misstated Starlette 0.48's actual `receive()` behavior (verified against installed source: raw `receive()` never raises it) — removed, folded into the general `except Exception` path; `Origin` header ambiguity was unguarded via `.get()` (silently takes the first), unlike `Host`'s explicit reject-if-more-than-one in the same module — now mirrors `_host_headers` via `.getlist()`; `conftest.py`'s `drive_handshake` silently built a "127.0.0.1:None" host/origin header when `bound_port` wasn't stamped — now asserts. Suite 2,669 -> 2,670 (+1), ruff and `mypy src/` both clean, plugin mirror rebuilt via `build_plugin.py`. Dismissed 11: mostly cases already covered by an explicit, documented design decision in the diff itself (1011 deliberately distinguishable from 1008, ticket-vs-Origin logging asymmetry, the no-TLS scheme assumption matching the rest of the codebase) or meta-critiques of the epic's established prose/ledger conventions rather than defects in this diff. Next: c5-4. PREVIOUSLY — DEVVED 2026-08-08 -> review. All seven open questions ruled by Brad BEFORE any code, every one on the story's own recommendation: `/ws`, query-param ticket carriage, 1008 pre-accept for EVERY rejection, missing Origin REJECTED (fail-closed), client frames drained and ignored, fail-closed 1011 in the handler with UnhandledErrorMiddleware staying http-only, and an ASGI-level handshake helper rather than Starlette's TestClient. THE HEADLINE HELD: half the security was already shipped and NONE of it was rewritten — ws.py contains no Host check (proven structurally AND behaviourally), and a rebound-Host handshake THROUGH THE REAL ROUTE is closed 1008 pre-accept, which is the first route-driven proof of the promise `test_security.py:9` recorded two epics ago. TWO PREDICTIONS FALSIFIED, both corrected in the same commit at zero regeneration cost (c3-9's rule, fifth story). (1) `main.py:524` and `security.py:436` predicted c5-3 would be a SECURITY LINE. It is not — the upgrade is a plain @router.websocket route, so it added a THIRD include_router above the ordering block exactly as c5-2 did, and install_security is STILL the one security wiring call, two stories past the one that was supposed to grow it. The correction states the LESSON rather than the fact, because c5-5 still holds the same prediction: 'gates a handshake' describes what a check does, 'middleware' describes where it must live, and they are independent. (2) Q1 predicted a plain `GET /ws` would serve index.html. IT ANSWERS THE TYPED 404 — `spa._route_paths` descends into WebSocketRoute exactly as into Route, so registering the router RESERVED the segment `ws`. Consequence: the story's 'a WS-only router owes test_spa.py no edit' is HALF WRONG — true of the hand-mirrored router list (which compares openapi paths and was genuinely untouched), FALSE of the reserved-prefix walk, which went red naming `ws`. The behaviour that fell out is the better one and is pinned deliberately. THE ATOMICITY OBLIGATION IS DISCHARGED STRUCTURALLY: the consume's one production caller is a PLAIN `def` holding the entire handshake decision, so 'no await between read and delete' is enforced by the LANGUAGE, not by a paragraph — reintroducing a suspension point requires changing that def to async def, which is one of the three breakers state.py already names. ORIGIN BEFORE CONSUME is pinned by EFFECT, not by line number: a refused foreign handshake carrying a VALID ticket leaves it still consumable (asserted on the wire and on resident_count) — the upgrade declines to add a second ticket-burner beside the one c5-2's Q1 knowingly accepted at the mint. Q6's raw-escape gap CLOSED LOCALLY, both sides of accept, with the pre-accept case driven by REAL CODE (an app whose lifespan never ran has no store) rather than a monkeypatch; all three prose sites that called it open are corrected. THE DOCTEST LEDGER ENTRY CLOSED IN THE GENERALISED SHAPE IT ASKED FOR — one test DISCOVERS every src/companion module from the tree, so a module added tomorrow is covered with no edit; c5-1's and c5-2's per-module tests were NOT deleted. R2: FOURTEEN new guards each planted red through the FULL 2,669-test run and reverted, one line per guard on what it compares and what it cannot see. G13's FIRST PLANT DID NOT FIRE and the miss is the useful part — it changed only the LOG, and the guard measures the WIRE, which is exactly the property the module claims; re-planted as a real violation (close 1003 for the no-ticket case) and it fired. Confirmed negative proven not assumed: gen:api byte-identical re-run after the last edit, 8 paths / 13 components untouched, no securitySchemes, SPA bundle zero-diff. Python 2,596 -> 2,669 passed (+73), 54 deselected, no regressions; NO TEST SLEEPS (30 s TTL via FakeClock, asserted by clock.slept == []). Frontend 1,694 / 65 files UNCHANGED as expected for a story with no ui/src change; tsc -b --force clean. ruff, mypy src/ and mypy --platform win32 all clean. Mirror rebuilt and sha256-verified on all 21 package files AFTER the last edit. ONE NEW DEFERRAL, Medium, homed on c5-6: the Vite dev proxy rewrites Host but not Origin, so a proxied handshake will fail once c5-6 adds /ws to PROXIED_PATTERNS — nothing is broken today (measured: /ws is deliberately absent from the proxy), three candidate fixes ledgered with the worst one named as worst, and recorded in ui/README.md beside the changeOrigin explanation. R1 self-check: Dev Notes 10.4 KB vs C4's 41 KB average — a quarter, and the smallest of the five C5-era stories; 3 inherited deferrals triggered (all closed), 5 not-triggered, all don't-breaks green and unmodified. Deviations: none. Next: code-review c5-3. PREVIOUSLY — CONTEXTED 2026-08-08 off `5113478` -> ready-for-dev. 26 ACs, 7 open questions (Q1-Q3 BLOCKING: endpoint path, ticket carriage, close code — the epic specifies NONE of the mechanics, only "the upgrade is rejected"). Dev Notes 10.7 KB — the smallest yet under R1 (c5-2 was 19.3, C4 averaged 41). HEADLINE: HALF THE STORY IS ALREADY SHIPPED — HostValidationMiddleware is pure ASGI precisely so it sees websocket scopes and already closes disallowed Hosts 1008 pre-accept (security.py:154-157 names c5-3 reusing it; test_security.py:295-327 pins both branches at the ASGI level "because no route drives them yet"). This story writes NO Host check: it adds the two things the middleware cannot do — Origin and consume — in NEW ws.py (the spine's module, ARCHITECTURE-SPINE:451), with the Origin decision a pure predicate in security.py beside host_is_allowed (the stores-nothing guard must pass unmodified). THREE LEDGERED OBLIGATIONS homed on this story by name are ACs: the Origin-on-upgrade half of c5-2's Q1 ruling (dw:5024), the consume-atomicity argument re-made against the real handshake with a guard (dw:5074 — no await between Origin check and the pop, consume stays sync), and the doctest walker over every src/companion module (dw:5041). SHAPE INVERTS c5-2 back to c5-1's confirmed negative: a FastAPI WS route never reaches openapi(), so 8 paths / 13 components stay pinned and AC 17 is the byte-identical gen:api proof. Ordering constraint measured, not assumed: the route must register ABOVE install_spa because test_spa.py:455-461 proves a WS handshake falling through to the mount dies on StaticFiles' assert scope=="http". Origin-before-consume is an AC with a live-ticket proof: a foreign page must not burn a ticket at the upgrade. Two owned gaps discharged: the error middleware passes websocket scopes raw (Q6, recommend fail-closed 1011 in the handler) and agent-token-in-a-WS-frame gets its structural guard (main.py:280 "nothing guards it yet"). Key-grep: 13 src/ui hits, all obligations, none falsified yet — but security.py:436/main.py:524's "inside install_security" framing may fall to the route-handler shape and must be corrected same-commit if so (c3-9's rule). Next: answer Q1-Q7, then dev-story c5-3.
