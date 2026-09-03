---
epic: c5
story: c5-4
work_branch: feat/companion-c5
story_branch: feat/companion-c5-4-broadcast
depends_on: >-
  c5-3 (merged, PR #55) — the authenticated upgrade whose drained socket is exactly the connection
  this story registers, the `_close_quietly` idiom, the `drive_handshake` ASGI test helper, and the
  G7 guard this story must retire through review. c5-2 (merged, PR #54) — the `TicketStore`
  conventions (`state.py` home, inert lifespan construction, one accessor, no-lock argument) the
  registry copies. c5-1 (merged, PR #53) — the frozen `ActiveDeckChangedEvent` contract this story
  puts on the wire for the first time, and the probe harness every new guard is proven through.
  c3-4 (merged) — the `PUT /api/active-deck` route carrying the marked insertion point.
baseline_commit: 51570c9
---

# Story C5.4: Broadcast to every connected client

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As Brad with the app open,
I want anything the backend learns to reach my browser immediately,
so that the glass reflects what the agent just did without me refreshing.

**✅ BRANCH PRECONDITION.** `feat/companion-c5` is at `51570c9` (the c5-3 merge — the
"record c5-3 merged" docs commit may land above it; either is a valid base). Cut
`feat/companion-c5-4-broadcast` from it. Verify `git log --oneline -1 origin/feat/companion-c5`
**before** `checkout -b`, not after.

**What this story really is.** A connection registry in `state.py`, a fan-out in `ws.py`, and one
call at a marked line in `routes/active_deck.py` — and five things that are not obvious from that.

---

1. **EVERY HOME IS PRE-BOOKED BY SHIPPED PROSE, AND FULFILLING IT IS AN OBLIGATION.**
   `state.py:19`: *"c5-4's connection registry joins them, rather than inventing a third home."*
   `ws.py:42-46`: *"What is deliberately absent: the connection registry and the broadcast …
   c5-4 owns the registry … and the fan-out."* `routes/active_deck.py:132`: *"c5-4 adds its
   active_deck_changed broadcast on the line below, after the store and before the return."*
   The spine agrees (`ARCHITECTURE-SPINE:448` state, `:451` `ws.py # upgrade + ticket consume +
   broadcast`). **No new module is sanctioned by any artifact.** Each of those prose sites is a
   shipped prediction: fulfil it and rewrite its "absent/joins/adds" wording in the same commit
   (c3-9's rule) — all three go stale the moment the code lands.

2. **A SHIPPED GUARD NAMES THIS STORY AND MUST GO THROUGH REVIEW, NOT `git rm`.**
   `test_ws.py:431-441` `test_no_connection_registry_was_scaffolded` bans the identifiers
   `{broadcast, connections, ConnectionRegistry}` in `ws.py` and asserts
   `not hasattr(state, "ConnectionRegistry")` — it reddens on this story's first real line, by
   design. C4 retro action item 13: a review-added mechanism is not silently deleted; its removal
   and its replacement guard set re-enter review. Its sibling `test_ws.py:421-429`
   (sent types == `["websocket.accept"]`, docstring *"c5-4 owns the first message this app ever
   sends"*) survives **revised**: still true for a socket that connects and disconnects with no
   broadcast in between.

3. **THE PAYLOAD QUESTION IS ALREADY ANSWERED — BY THE FROZEN CONTRACT, NOT THE LEDGER.**
   `deferred-work.md:2636` (written pre-c5-1) says the broadcast carries "the same `ActiveDeck`
   shape"; the epic AC says "carrying the new deck id". c5-1 settled it:
   `ActiveDeckChangedEvent` with `ActiveDeckChangedPayload{deck_id: str | None}`
   (`contracts.py:882-909`), pinned by `test_contracts.py` and the committed `.d.ts`. The two
   shapes are structurally identical (`{deck_id}`), which is why nothing ripples — but the wire
   object is the **envelope union member**, wrapped `{kind, id, ts, payload}`. And the payload
   docstring carries a ruling this story must not re-litigate: **it fires on every set, including
   a same-id rewrite** — "only broadcast if it changed" is a read-modify-write and is exactly what
   the no-lock slot design forbids (Q10, Brad 2026-08-07, `contracts.py:890-894`).

4. **THE FAILURE POLICY IS THE ONLY GENUINELY UNDESIGNED SURFACE.** The artifacts specify:
   fire-and-forget (NFR-04), zero clients succeeds silently, a disconnected client "is removed from
   the connection set without error, and other clients are unaffected", never block the event loop
   (AD-11's discipline), no detached tasks (AD-9: *"`create_task` is banned here"* — stated for the
   leaf notifier, but it is the spine's only definition of fire-and-forget), and no DB read on the
   push path (AD-7). They say **nothing** about a send that raises mid-broadcast, slow-client
   backpressure, or delivery ordering — AD-6 is explicit that ordering is `ts`'s job, not the
   transport's. Q1–Q3 rule the mechanism; do not invent requirements beyond them (the epics file
   author confirmed: no slow-client/backpressure AC exists anywhere — adding one would be scope
   creep).

5. **THIS STORY IS BACKEND-ONLY, AND THREE LEDGER ENTRIES HOMED ON "c5-4" ASSUMED OTHERWISE.**
   `ui/src` makes no WebSocket connection today (verified at c5-3); c5-6 owns the browser's
   connect/reconnect loop and c5-7 the pill. But `deferred-work.md:3584-3592` ("c5-4 (the event
   handlers) owns the transition" — the card-cache terminal-after-three), `:3591-3595` (orphaned
   hydration residue) and `:3680-3684` (404-clears-client loop) were written expecting c5-4 to
   build client event handlers. There are none to build here. Q6 rules their re-homing; whatever
   the ruling, the ledger is edited **in the same commit** that disposes of them (C4 standing
   agreement: a disposition lives in the ledger, not only the story record).

---

## Dev Notes

### Task 0 — verify before writing code, do not believe this file

Measured on `51570c9`, 2026-08-08. Re-run every line; a mismatch is a finding, not a rounding error.

| Fact | Measured value | Command |
|---|---|---|
| Python tests | **2,670 passed / 54 deselected** at c5-3 close | `uv run pytest -q` (or `--collect-only -q \| tail -1` first) |
| Frontend tests | **1,694 passed / 65 files** — expect unchanged all story | `cd ui && npx vitest run` |
| OpenAPI schema | **8 paths / 13 components** — must not move | `python -c` over `ui/src/api/openapi.json` |
| `gen:api` at baseline | clean no-op | `cd ui && npm run gen:api` then `git status --porcelain` |
| Plugin mirror | in sync — sha256 every file this story touches, before AND after | `shasum -a 256 src/companion/… plugin/server/src/companion/…` |
| starlette / fastapi / websockets | **0.48.0 / 0.140.0 / 16.1.1** | `uv run python -c "import starlette, fastapi; …"` |
| `ui/node_modules` | re-measure presence; do NOT `npm install` | `test -d ui/node_modules` |

**Grep your own key (C4 retro action item 6) — run 2026-08-08 on `51570c9`, 9 src/ui/tests hits,
all obligations, none falsified:** `routes/active_deck.py:24` (+`:132`, the insertion point),
`state.py:19` (registry joins), `ws.py:44` (fan-out owned), `ws.py:240` (the drained socket "is
precisely the connection c5-4 is about to want"), `ui/src/state/deck.ts:75` (the re-homed
terminal-id entry — Q6), `test_routes_active_deck.py:151` ("the read, the write, and c5-4's change
notification"), `test_ws.py:424` ("c5-4 owns the first message this app ever sends"),
`test_ws.py:432` (G7, headline item 2). Every prose site the diff touches is corrected in the same
commit; re-run the grep after implementation.

### Where each piece goes — the shape to build

**`state.py` — `ConnectionRegistry`, beside `TicketStore`, copying its conventions.** Bare class,
keyword-only `__init__`, inert construction (no I/O, no clock unless a design need appears — the
registry has no TTL, so probably none), **no lock, with the argument stated in the docstring** the
way `state.py:36-68` does for the store: add/discard/snapshot are single synchronous dict/set
operations on the one event loop; name the changes that would earn a lock. Storage is backend
memory only, gone on restart (CM-3). Recommended surface (Q1): `add(connection)`,
`discard(connection)` (idempotent — the fan-out and the handler's `finally` may both remove),
`snapshot()` returning an iteration-safe copy, and a count (`connected_count` property or
`len`-like) — **story 5.5 returns that count from `POST /agent/events` (AD-8, FR-06), so it must
be queryable, cheap, and read no DB**. Type the stored connection as a minimal structural
`Protocol` (an object with `async send_text(str)`) rather than importing Starlette into
`state.py` — keeps the module "a dict and a clock", and lets registry unit tests register fakes
with no ASGI machinery. **Identifier bans live here**: nothing in `state.py` may be named
`token`, `agent_token`, `credential`, `secret`, or `mint_token`
(`test_routes_active_deck.py:724-752`), and no integer literal `60` or `15` anywhere under
`src/companion/**` outside `contracts.py` (`test_routes_format_check.py`; `MAX_TICKETS` chose 256
for exactly this reason — if the registry needs any numeric constant, pick outside `{60, 15}`).

**`main.py` — one lifespan line, nothing in `_shutdown`.** `app.state.connections =
state.ConnectionRegistry()` beside the ticket store (`main.py:204-210` — same reasoning: a
container, no `build_*` factory, so AD-15's "publishing the discovery file is the ONLY startup
step that may fail a launch" stays literally true). Accessor `connection_registry(app) ->
ConnectionRegistry | None` in `state.py` mirroring `ticket_store(app)` (`state.py:402-418`): one
`getattr` into an annotated local, `None` = lifespan never ran. `build_app()` stays
side-effect-free (AD-10).

**`ws.py` — register around the drain, fan-out beside it.** The accepted socket currently goes
straight to `_drain_until_disconnect` (`ws.py:229-248`); this story wraps that call:
register after `accept()` succeeds, unregister in a `finally` covering **every** exit path — the
normal disconnect return, and the 1011 fault path. The drain loop is the authoritative disconnect
detector (Starlette 0.48 verified at c5-3: raw `receive()` **returns** the disconnect message, it
does not raise — only the `receive_*` wrappers raise `WebSocketDisconnect`). The broadcast helper
lives here too (spine `:451`): recommended shape (Q4) — `async def broadcast(app, event) -> int`
(serialise once via the event's own `model_dump_json()`, iterate a registry snapshot, per-socket
`try/except`, return delivered count) plus a thin
`async def broadcast_active_deck_changed(app, deck_id)` that builds the envelope, so the route
adds literally one awaited call. Envelope construction: backend mints `id` (opaque, dedupe-only —
`uuid.uuid4()` hex is fine; ordering is `ts`'s job, AD-6) and `ts = datetime.now(UTC)` (project
rule: aware UTC, never naive). **`ws.py` landmines**: no new string literal containing `"host"`
(case-insensitive — `test_ws.py:346-374` scans code with docstrings stripped); no identifier from
`{socket, uvicorn, serve, bind, listen}` (`test_ws.py:518-522`) — name variables `connection`/
`client`, never `socket`; no agent-credential name (`test_ws.py:632-657`); `_handshake_is_authorised`
stays a plain `def` with zero `Await` nodes and `consume` keeps its single `.pop(`
(`TestTheConsumeStaysSynchronous`, `test_ws.py:682-739`).

**`routes/active_deck.py` — one call, replacing the comment at `:132`.** After `slot.set(...)`,
before the return; read the broadcast's `deck_id` **from the slot**, not from `body`, for the same
echo-what-was-stored reason the return does (`:135-136`). The broadcast must never affect the
PUT's own 200 — fire-and-forget means a failure inside it is caught and logged, and the mutation's
result is untouched (AD-9's principle). A refused credential or failed store broadcasts nothing
(the call sits after the store on the success path only). Check `:104-106` ("one shape serves the
read, the write and the change notification") against the shipped wire object — the payload is
`ActiveDeckChangedPayload`, not `ActiveDeck`; if you judge the prose falsified, correct it in the
same commit (c3-9), at zero regeneration cost only if the edit stays below the first Google
section header (the docstring's leading paragraphs SHIP — anything above `Args:` lands in
`components.schemas` descriptions; verify with `gen:api` byte-diff before assuming).

**`contracts.py` — read-only.** `ActiveDeckChangedEvent` exists, frozen, tested; there is **no
wire-serialisation helper anywhere** — each event is a `BaseModel`, `model_dump_json()` is the
path. Do not add one to `contracts.py` (leaf; any edit risks the wire) — if a shared constructor
is wanted it lives in `ws.py`.

### The house idiom — follow it, do not invent

- **Fire-and-forget ≠ detached.** Sequential per-socket awaits inside one handler-context
  coroutine; `create_task` is banned (AD-9). No per-send timeout in this story (Q3) — localhost
  sockets, OS buffers; AD-9's ~1 s bounded-await is the named escalation shape if evidence ever
  demands one.
- **Send-failure = that socket's problem only** (Q2): catch `Exception` per socket, log at DEBUG
  (a dying tab is routine, not an event), `registry.discard(...)`, best-effort
  `_close_quietly(connection, 1011)`, continue with the rest. The handler's own `finally` remains
  the authoritative unregister; `discard` being idempotent is what makes the race harmless.
- **No DB round-trip on the broadcast path** (AD-7) — the deck id comes from the in-memory slot;
  nothing on this path may touch `deps.py`/the engine. Protects NFR-05's 250 ms budget before
  c5-5 enforces it.
- **The agent token never enters a frame** (AD-5) — `TestTheTwoCredentialsNeverTouch` already
  scans `ws.py` identifiers; the new code inherits it for free, keep it green.
- **Docstrings**: Google style; any `Example:` block must be a runnable doctest — the
  package-wide walker (`test_ws.py:742-801`) auto-covers new code with no edit.
- **A test that sleeps is a defect** — broadcasts are awaited in-process; nothing here needs a
  clock. If a test wants "later", it drives the ASGI messages, it does not wait.

### Testing the broadcast — the harness gap is real

`drive_handshake` (`conftest.py:172-257`) runs **one handshake to completion** — its `receive`
exhausts frames then repeats `websocket.disconnect`, so no socket stays open concurrently. A
broadcast test needs sockets that are open **while** an event is pushed. Two layers (Q5):

1. **Registry unit tests** (the bulk): fake connections (the `Protocol` above — an object
   recording `send_text` calls, optionally raising) drive every AC cheaply: every-client delivery,
   zero-client silence, discard-on-failure, count. No ASGI involved.
2. **One route-driven proof through the real machinery**: extend `conftest.py` with a
   task-based helper (e.g. an async context manager that starts `app(scope, receive, send)` as an
   `asyncio.Task` with a controllable receive queue, yields a handle exposing sent messages, and
   feeds `websocket.disconnect` on exit) — then: two open handshakes, one
   `PUT /api/active-deck`, both handles hold one text frame that parses via
   `TypeAdapter(AgentEvent)` to an `ActiveDeckChangedEvent` with the stored id. That single test
   is the multi-tab AC on the wire. The real-socket version belongs to **c5-8, not here** (AD-10:
   exactly one integration-marked socket test in the feature).

**R2 applies to every new guard**: planted violation, red through the FULL suite via
`uv run python -m scripts.probe_harness --expect-red '<node-id>'`, reverted, plus one line on what
the assertion compares and what it cannot see. G7's replacement set re-enters review with the
story (headline item 2).

### Inherited deferrals — R1 trigger-gated

**Triggered (dispositions owed in this diff):**
- `deferred-work.md:2632-2638` — **the broadcast seam itself**: "Nothing broadcasts the change …
  Home: c5-4, which adds one call after the store, to a handler that will exist." This story IS
  the closure; annotate closed, and note the payload landed as the c5-1 contract shape (the
  entry's "same `ActiveDeck` shape" line predates c5-1 — see headline item 3).
- `deferred-work.md:3676-3679` — **no re-drive after boot**: "A deck the agent sets while the tab
  is open does not appear until Epic 5's `deck_changed` … Home: c5-4." The backend half (the
  signal exists on the wire) is discharged here; the browser half needs a connected client —
  re-home the remainder to c5-6 with the closure note (Q6).
- `deferred-work.md:3584-3592`, `:3591-3595`, `:3680-3684` — the three UI-side entries of
  headline item 5. Q6 rules; edit the ledger either way.

**Not triggered (one line + anchor each):** Vite dev-proxy Origin mismatch (`:5122-5138` —
c5-6's, first story to proxy `/ws`); `errors.supported_methods` under a non-root Mount
(`:5045-5050` — no new Mount here); committed-schema vs `gen:api` ordering (`:5073-5085` —
informational; no component moves here, but any schema-adjacent R2 plant must run `gen:api`
between plant and probe); AD-1 exemption-shape revisit (`:4980-4983` — C5 retro's); Q3/AD-5
prose-narration debt (`:5105-5112` — C5 retro's; **do not add new cross-module forward-looking
prose that widens it**); `dump_openapi.py` docstring-as-changelog (`:5113-5118` — C5 retro's; this
story owes it nothing, no schema diff); vitest probe-harness half (`:4995-4999` — first C5 story
planting a *frontend* guard; this story plants none).

**Don't-break, scoped to this diff's files:** `test_ws.py` G1–G6, G8–G14 minus the two revised
above (notably: refusals byte-identical `TestEveryRejectionLooksTheSame`; error middleware
http-only; route-above-SPA `_reserved_prefixes` pin; Origin-before-consume by effect);
`test_routes_active_deck.py` identifier bans + stores-nothing + shared-code-path guards (`:724-844`);
`test_committed_schema.py` 8/13 pins; `test_spa.py:297-330` hand-mirrored router list (**no edit
owed — no new HTTP router**) and `:442` reserved-prefix set; `test_contracts.py` (read-only
contract). The plugin mirror is rebuilt (`uv run python -m scripts.build_plugin`) and
sha256-verified **after the last edit** — c5-1's falsified mid-story claim is the cautionary tale.

### No UX surface, and no new libraries

No `ui/src` change: frontend suite stays 1,694 / 65 and `tsc -b --force` clean, both re-measured
not assumed. No new dependency: everything needed ships with starlette 0.48 / uvicorn[standard]
(websockets 16.1.1 already present). No new `ErrorReason` token (closed at ten); no new close
code beyond the shipped 1008/1011. This is a confirmed-negative schema story (c5-1/c5-3's shape):
AC is `gen:api` byte-identical, pins unmoved.

### Source tree — what this story touches

`src/companion/app/state.py` (registry + accessor + docstring fulfilment) ·
`src/companion/app/ws.py` (register/unregister, fan-out, docstring rewrite) ·
`src/companion/app/main.py` (one lifespan line) ·
`src/companion/app/routes/active_deck.py` (one call at `:132`, prose check) ·
`tests/unit/companion/test_ws.py` (G7 retirement + revisions + new guards) ·
`tests/unit/companion/test_routes_active_deck.py` (PUT-broadcast tests) ·
`tests/unit/companion/conftest.py` (concurrent-socket helper) ·
`_bmad-output/implementation-artifacts/deferred-work.md` (5 dispositions) ·
`plugin/server/**` (rebuilt mirror) · `sprint-status.yaml` (record).
`src/companion/contracts.py`, `security.py`, `errors.py`: **read-only.**

### References

- Story + ACs: `epics-companion-app.md:2479-2509`; Epic 5 preamble `:2357-2362`; 5.5's
  count expectation `:2521`; 6.3's every-tab `:2754-2756`.
- FR-06 `prd.md:126`; NFR-04 `prd.md:163`; flow `prd.md:90-92`; OQ-4 replay rejection
  `addendum.md:135-137`; EC-09 count origin `review-edge-case-hunter.md:59-62`;
  cross-tab rule `EXPERIENCE.md:131` (UX-DR37).
- AD-6 envelope `ARCHITECTURE-SPINE:159-171`; AD-7 no-DB push path `:173-196`; AD-8 count
  `:197-209`; AD-9 fire-and-forget definition `:218-222`; AD-10 testing `:227-240`; CM-3
  conventions `:359-360`; module map `:448-461`.
- Contract: `contracts.py:882-909` (payload + Q10), `:913-930` (envelope base), `:1210-1218`
  (`AgentEvent` union — validate with `TypeAdapter`).
- Shipped seams: `ws.py:42-46`, `:229-248`, `:251-271`; `state.py:17-23`, `:36-68`, `:402-418`;
  `main.py:204-210`; `routes/active_deck.py:104-137`.
- Ledger: `deferred-work.md:2632-2638`, `:3584-3595`, `:3676-3684`.

---

## Acceptance Criteria

### The registry (CM-3)

1. `ConnectionRegistry` lives in `src/companion/app/state.py` beside `TicketStore`, following its
   conventions: bare class, keyword-only init, inert construction, storage in backend memory only
   — nothing persisted, gone on restart (CM-3).
2. The registry carries **no lock, and its docstring makes the argument** the way
   `state.py:36-68` does: every operation is a single synchronous container mutation on the one
   event loop, and the changes that would earn a lock are named.
3. The lifespan creates it (`build_app()` stays side-effect-free, AD-10); nothing is added to
   `_shutdown`; a `connection_registry(app) -> ConnectionRegistry | None` accessor in `state.py`
   mirrors `ticket_store(app)` — one `getattr`, `None` means the lifespan never ran.
4. The registry exposes a queryable connected-client count reading no database — story 5.5
   returns it from `POST /agent/events` (AD-8, FR-06) and must find it waiting.
5. `discard` of an absent connection is a silent no-op (the fan-out's failure path and the
   handler's `finally` may both remove the same socket).

### Register/unregister in the socket lifecycle

6. A connection joins the registry only after `accept()` succeeds, and leaves it on **every**
   exit path — normal disconnect and the 1011 fault path — via `try/finally` around the drain.
7. A socket that connects and disconnects with no broadcast in between receives nothing after
   `websocket.accept` (the revised form of `test_ws.py:421-429`; registration sends no frames).
8. Given a client disconnects, when the next broadcast occurs, it is removed from the connection
   set without error, and other clients are unaffected (epic AC, verbatim).

### The broadcast (FR-06, NFR-04, AD-6, AD-7)

9. Given one or more connected clients, when an envelope is broadcast, every connected client
   receives it (FR-06) — proven with multiple concurrently open sockets: **every tab** receives
   it, and nothing synchronises cross-tab state (UX-DR37).
10. The envelope is serialised **once** per broadcast via the event model's own
    `model_dump_json()`; every client receives byte-identical text; no second serialiser exists
    anywhere in the diff.
11. Given no clients are connected, a broadcast succeeds silently — fire-and-forget (NFR-04).
12. A send failure on one socket is contained: caught per-socket, logged at DEBUG, the socket
    discarded from the registry and closed best-effort via `_close_quietly`; remaining clients
    still receive; no exception escapes the broadcast to its caller.
13. The broadcast path contains no `create_task` (AD-9's ban) and no database access (AD-7) —
    both pinned structurally, not just by prose.
14. The fan-out lives in `ws.py` (spine `:451`); the registry vocabulary guard G7 is retired and
    its replacement guard set covers the new surface (see AC 21).
15. The agent token appears in no frame and no broadcast code path —
    `TestTheTwoCredentialsNeverTouch` stays green over the grown `ws.py`.

### The `active_deck_changed` wire-up (AD-6)

16. Given the active deck is set through `PUT /api/active-deck` and the store succeeds, an
    `ActiveDeckChangedEvent` is broadcast carrying the deck id **read from the slot** (not from
    the request body), with backend-minted opaque `id` and aware-UTC `ts` under the c5-1 contract;
    on the wire it parses via `TypeAdapter(AgentEvent)` to kind `active_deck_changed`.
17. It fires on **every** successful set, including a same-id rewrite (Q10 ruling,
    `contracts.py:890-894`) — no only-if-changed suppression.
18. A refused credential or failed store broadcasts nothing; and a fault inside the broadcast
    never affects the PUT's own 200-with-body response.
19. The insertion-point comment at `routes/active_deck.py:132` is replaced by the call it
    predicted.

### The confirmed negative (schema)

20. `npm run gen:api` leaves `ui/src/api/openapi.json` and `types.d.ts` byte-identical;
    `test_committed_schema.py` pins stay at 8 paths / 13 components; `test_spa.py`'s router list
    and reserved-prefix set need no edit (no new HTTP router, no new first segment).

### Guards, prose and record

21. G7 (`test_no_connection_registry_was_scaffolded`) is removed **and replaced** — the removal
    and the replacement guards re-enter review (C4 item 13); every new guard ships an R2 firing
    proof: planted violation red through the FULL suite via the probe harness, reverted, one line
    on what it compares and what it cannot see.
22. All shipped predictions the diff touches are corrected in the same commit (c3-9):
    `ws.py:42-46` and `:239-242`, `state.py:19`, `routes/active_deck.py:23-24` — and the
    `:104-106` "one shape serves…" claim is checked against the shipped payload and corrected if
    judged false, with any wire-visible docstring edit proven zero-diff by `gen:api`.
23. The five ledger dispositions land in this diff (triggered list above), each edited in
    `deferred-work.md` itself.
24. Existing guard families stay green unmodified except where an AC names the change:
    identifier bans (`state.py`: no `token`/`agent_token`/`credential`/`secret`/`mint_token`;
    `ws.py`: no `socket`/`uvicorn`/`serve`/`bind`/`listen`, no `"host"` string literal, no
    agent-credential name), `{60, 15}` construction-literal ban, sync-consume family,
    stores-nothing, refusals-indistinguishable, error-middleware-http-only.
25. No test sleeps; the concurrent-socket helper drives ASGI messages, never wall clock; every
    new `Example:` block passes under the package doctest walker with no walker edit.
26. Full Python suite green (expect ≥ 2,670 + this story's additions), `mypy src/` and
    `mypy src/ --platform win32` clean, ruff clean; frontend 1,694 / 65 and `tsc -b --force`
    unchanged, re-measured; plugin mirror rebuilt and sha256-verified after the last edit;
    Dev Notes KB self-check recorded against C4's 41 KB average.

---

## Tasks / Subtasks

- [x] **Task 0 — verify the baseline** (Dev Notes table + key grep; a mismatch is a finding).
- [x] **Task 1 — `ConnectionRegistry` in `state.py`** (AC 1–5): class + no-lock argument +
      accessor + docstring fulfilment; registry unit tests with fake connections (delivery,
      silence, discard, count, idempotent discard).
- [x] **Task 2 — lifespan wiring in `main.py`** (AC 3): one line beside the ticket store;
      `test_app.py`-style assertions that `build_app()` grew no side effect.
- [x] **Task 3 — register/unregister + fan-out in `ws.py`** (AC 6–15): try/finally around the
      drain; `broadcast(app, event)` + `broadcast_active_deck_changed(app, deck_id)`;
      serialise-once; per-socket failure containment; docstring rewrites.
- [x] **Task 4 — the one call in `routes/active_deck.py`** (AC 16–19): replace the `:132`
      comment; slot-read id; failure isolation from the 200; route tests incl. the same-id
      rewrite case.
- [x] **Task 5 — test harness + guards** (AC 7–9, 21, 24–25): concurrent-socket conftest helper;
      the two-tabs-one-PUT wire proof; G7 retirement + replacement guard set, each R2-proven red
      through the full suite.
- [x] **Task 6 — confirmed negative, ledger, mirror, record** (AC 20, 22–23, 26): `gen:api`
      byte-diff; five ledger dispositions; prose corrections; rebuild + sha256 the mirror after
      the last edit; measurements + Dev Notes KB into the record; set status `review` and STOP
      (Brad runs the three-layer review and raises the PR).

### Review Findings

- [x] [Review][Patch] Concurrent broadcasts are not serialised per connection — two overlapping calls into `broadcast()` (e.g. two overlapping `PUT /api/active-deck` requests, or a future c5-5 broadcast racing this one) each independently snapshot the registry and `await connection.send_text(...)` on the same shared `Connection`. Starlette's `WebSocket` has no internal send-serialisation, so a genuinely concurrent pair of sends on one socket can raise, which `broadcast()`'s per-connection `except Exception` interprets as "the client is gone" — spuriously discarding and 1011-closing a perfectly healthy tab. **Resolved (Brad 2026-08-08): accept as a documented residual**, the same shape as Q3's slow-client stall — no locking added. Fix: add a paragraph to `broadcast()`'s docstring naming this residual explicitly (two overlapping broadcasts can race a shared connection's send and cause a spurious evict-and-close of a healthy tab), alongside the existing Q3 slow-client note, so it's a stated tradeoff rather than a silent gap. [`src/companion/app/ws.py:364-385`]
- [x] [Review][Patch] `PUT /api/active-deck`'s response can echo a different deck than the one this request itself stored — `slot.deck_id` is read once for the broadcast argument and again for the return, with the broadcast's sequential awaited sends in between; a second concurrent `PUT` can rewrite the slot in that window, so the first request's `200` body can disagree with both what it stored and what it just broadcast. Fix: capture `slot.deck_id` once into a local and reuse it for both the broadcast call and the return. [`src/companion/app/routes/active_deck.py:156-165`]
- [x] [Review][Patch] `broadcast()`'s per-client failure containment can be defeated by an unguarded property read: `_close_quietly`'s `connection.client_state` access (its first line) is not wrapped in `try`/`except`, and it is called from *inside* `broadcast()`'s per-connection `except` block rather than inside the `try` that block belongs to — so if `client_state` ever raises on a registered `Connection`, the exception escapes the `for` loop into the outer `except Exception`, silently ending delivery to every client not yet visited in that snapshot. Low likelihood with a real Starlette `WebSocket` today, but it contradicts AC 12's "every other client still receives the event" as a structural guarantee. Fix: guard the `client_state` read (or move the `_close_quietly` call inside the same `try` as `send_text`). [`src/companion/app/ws.py:299-328`, `:374-381`]
- [x] [Review][Patch] The corrected docstring claim that `ActiveDeck` and `ActiveDeckChangedPayload` share "the same nullability, same `_MAX_DECK_ID_LENGTH` bound" is false, not true as the Completion Notes assert: `ActiveDeck.deck_id` is a bare `str | None` with no `Field`, no length cap and no blank-refusal (`src/companion/contracts.py:243`), while `ActiveDeckChangedPayload.deck_id` uses `_NullableDeckId` (`contracts.py:471-473`, used at `:907`), which caps at `_MAX_DECK_ID_LENGTH` and refuses blank strings via `_refuse_blank_text`. Not wire-visible (it sits below `Args:`, `gen:api` stays byte-identical) so there's no schema/runtime impact, but it's a shipped-false correction under AC 22 and is repeated in the ledger closure note. Fix: rewrite both sites to state the actual relationship (same field name and nullability; `ActiveDeckChangedPayload` additionally bounds length and refuses blanks, `ActiveDeck` does not). [`src/companion/app/routes/active_deck.py:144-149`; `_bmad-output/implementation-artifacts/deferred-work.md` (the `:2632` closure note)]
- [x] [Review][Patch] `open_socket`'s cleanup calls `waiter.cancel()` twice (once right after `asyncio.wait(...)` returns, again in `finally`) and never awaits or collects the cancellation, which can produce a "Task was destroyed but it is pending" warning if teardown races the cancellation. Harmless to test correctness today but worth tightening given this file's own discipline about task lifecycle. Fix: await `waiter` (suppressing `CancelledError`) before returning, or gather it alongside `served`. [`tests/unit/companion/conftest.py:352-367`]

**Dismissed as noise / already handled / no consequence (8):** ticket-cap reasoning in the registry's "unbounded" docstring somewhat overstates what `MAX_TICKETS` bounds (only concurrently-outstanding tickets, not lifetime registrations) — true imprecision, but the actual ruling (no cap, fd-limit backstop) was already made by Brad at Q7 and doesn't change · no per-send timeout / a slow client can add latency to the whole broadcast — explicitly ruled at Q3 (sequential awaited sends, no timeout, accepted as a documented residual) · reusing close code `1011` for an ordinary client-caused disconnect blurs the module's stated "a caller cannot cause this branch" distinction — explicitly constrained by Q2's send-failure policy and AC 20's "no new close code beyond 1008/1011" · `ConnectionRegistry.add`'s after-`accept()`-only invariant has no runtime assertion, only dedicated tests — consistent with how every other invariant in this package is enforced, not a defect · `test_the_broadcast_helpers_are_total`'s AST guard can't see a fallible call made from inside an `except` handler itself — already disclosed in the guard's own docstring, not a hidden gap · the diff reviewed excludes `plugin/server/**` — deliberate review scoping after confirming the mirror is byte-identical to `src/companion/**`, not an omission · AC 18's judgement call (containment lives in the helpers being total, not a route-level `try`) was flagged for verification and checked out as written — confirmation, not a defect · no real-socket test drives a mid-broadcast send failure on a still-"connected" socket — intentionally out of scope per Q5/AD-10 (the one real-socket integration test is c5-8's).

---

## Open questions for Brad

Rule before code (recommendations first, per c5-1…c5-3 precedent):

1. **Registry surface & typing (AC 1, 4, 5).** Recommend: `add` / `discard` (idempotent) /
   `snapshot()` / a count property, storing connections behind a minimal structural `Protocol`
   (`async send_text(str)`) so `state.py` imports no web framework and unit tests use fakes.
2. **Send-failure policy (AC 12).** Recommend: per-socket catch-log-DEBUG-discard +
   best-effort `_close_quietly(…, 1011)`, handler `finally` remains the authoritative
   unregister. Nothing in any artifact specifies this; it must be a written ruling either way.
3. **Sequential sends, no per-send timeout.** Recommend: sequential awaited sends (localhost, OS
   buffers; `create_task` banned by AD-9); accept the theoretical slow-client stall as a
   documented residual, with AD-9's ~1 s bounded-await named as the escalation shape if evidence
   ever demands one.
4. **Where envelope construction lives (AC 16).** Recommend: both helpers in `ws.py`
   (`broadcast` generic — c5-5 will reuse it — plus `broadcast_active_deck_changed`), the route
   adding exactly one awaited line; `id` = `uuid.uuid4()`-derived opaque string; nothing added to
   `contracts.py`.
5. **Test harness shape (AC 9).** Recommend: fakes for the bulk + one task-based
   concurrent-socket conftest helper for the single route-driven wire proof; the real-socket
   version stays c5-8's (AD-10).
6. **Re-homing the three UI-side ledger entries (headline item 5, AC 23).** Recommend: re-home
   `dw:3584-3592`, `:3591-3595`, `:3680-3684` to **c5-6** (the story that builds the client event
   handlers), with `dw:3676-3679`'s browser half following; c5-4 closes only the backend halves.
7. **Registry cap.** Recommend: **none** — connections are ticket-gated (same-origin mint,
   single-use consume) and OS fd limits bound the pathological case; a cap would need an eviction
   policy that kicks a legitimate tab. Argued in the registry docstring, not silently.

---

## Dev Agent Record

### Agent Model Used

Claude Opus 5 (1M context) — `claude-opus-5[1m]`, via the `bmad-dev-story` workflow, 2026-08-08.

### Rulings (all seven open questions, Brad 2026-08-08)

Every question was answered **as recommended**. Recorded here because the code cites them by
number:

| Q | Ruling |
|---|---|
| Q1 | `add` / `discard` (idempotent) / `snapshot()` / `connected_count`, behind a structural `Protocol` so `state.py` imports no web framework |
| Q2 | Per-socket catch → log DEBUG → `discard` → best-effort `_close_quietly(…, 1011)`; the handler's `finally` stays authoritative |
| Q3 | Sequential awaited sends, no per-send timeout; AD-9's ~1 s bounded await named as the escalation shape |
| Q4 | Both helpers in `ws.py`; the route adds exactly one awaited line; `id` from `uuid.uuid4()`; nothing added to `contracts.py` |
| Q5 | Fakes for the bulk + one task-based concurrent-socket conftest helper for the wire proof; the real socket stays c5-8's |
| Q6 | Re-home `dw:3584-3592`, `:3591-3595`, `:3680-3684` to **c5-6**; c5-4 closes only backend halves |
| Q7 | **No registry cap** — connections are ticket-gated and fd-bounded; a cap would need an eviction that kicks a legitimate tab |

**One refinement of Q1 the ruling forced, flagged for review.** The recommendation described the
protocol as *"an object with `async send_text(str)`"*. Q2 then ruled that a failed send closes that
socket — so the fan-out needs `close` and the connection state as well, and
`state.Connection` ships **three** members, not one. `client_state` is typed `object` deliberately:
this module never interprets it (it is compared by identity against `WebSocketState.DISCONNECTED`,
a sentinel the *caller* owns), so naming Starlette's enum would import a web framework for a value
`state.py` has no opinion about. `_close_quietly`'s annotation widened from `WebSocket` to
`Connection` — a type change only; behaviour, call sites and every existing guard are untouched.

### Debug Log References

**Task 0 baseline, re-measured on `51570c9` — two mismatches against the Dev Notes table, both
explained, neither a defect:**

| Fact | Story said | Measured | Verdict |
|---|---|---|---|
| Python tests | 2,670 passed / 54 deselected | `pytest -q`: **2,723 passed / 1 skipped** (2,724 collected); `probe_harness`: **2,670** | ✅ agree — the story's figure is the probe-harness run (`-m 'not integration'`), and 2,670 + 54 = 2,724 = the full collection |
| Frontend | 1,694 passed / 65 files | **first run 1,693 passed / 1 FAILED**; **re-run 1,694 / 65 green** | ⚠️ **one flaky frontend test**, detail lost to a `tail` pipe; green on immediate re-run and on the closing re-measure. Recorded, not chased — but the suite is not reliably green on a single run |
| OpenAPI | 8 paths / 13 components | 8 / 13 | ✅ |
| `gen:api` at baseline | clean no-op | clean no-op | ✅ |
| Plugin mirror | in sync | sha256 identical on all 5 touched files | ✅ |
| starlette / fastapi / websockets | 0.48.0 / 0.140.0 / 16.1.1 | identical | ✅ |
| `ui/node_modules` | re-measure | present | ✅ |
| Key grep | 9 src/ui/tests hits, all obligations | 9 hits, exactly the listed sites, none falsified | ✅ |

Branch precondition verified **before** `checkout -b`: `origin/feat/companion-c5` at `51570c9`.

**R2 firing proofs — 13 full-suite probe runs via `scripts.probe_harness`.** Collection was 2,715
→ 2,716 after the run-5 finding below; every run reverted cleanly (`git diff` confirmed free of
plant residue afterwards).

| Plant | Guards proven RED | Result |
|---|---|---|
| `create_task` + `select` + `json.dumps` in `ws.py`, `serialise_envelope` in `contracts.py`, `asyncio.Lock` in `state.py` | no-create-task, no-DB-on-push, one-serialiser, no-contracts-helper, no-lock | 5 red, **exactly 5 failed** |
| registry backed by a `list`, `discard`→`remove` | idempotent-add, silent-discard | 2 red |
| `snapshot()` returns the live set + fan-out reaches only the first client | snapshot-is-a-copy, every-client, both-tabs | 9 red |
| `finally` around the drain becomes `if False:` | registered-during-drain, two-sockets, 1011-unregisters, refused-origin, closed-tab | 5 red |
| `registry.add` moved above `accept()` | accept-failure-never-registers | 1 red — **see the finding below** |
| serialise inside the loop + per-socket `try` removed | serialise-outside-loop, containment ×2, dead-client-keeps-200 | 4 red |
| `except Exception` → `except ValueError`; helper `try` → `if` | helpers-are-total | 1 red |
| route reads `body.deck_id` + only-if-changed suppression | slot-not-body, same-id-rewrite | 2 red |
| lifespan line removed + `ws.py` self-heals a registry | lifespan-creates-one, ws-builds-no-registry | red (broad blast radius — a lazily-created registry aliases differently per handshake) |
| `ConnectionRegistry` class defined in `ws.py` | fan-out-here-membership-there | 1 red |
| accessor returns a fresh registry + fixed event `id` | no-registry-before-lifespan, build_app-side-effect-free, opaque-id/aware-ts | red |
| insertion-point comment restored in place of the call | comment-was-replaced | red |
| module-level shared set + positional `__init__` + reversed wire text + WARNING on empty | fresh-registry-empty, keyword-only-init, registries-share-nothing, silent-empty-broadcast, frame-parses-back | red |
| `ConnectionRegistry` docstring gutted via AST + `select` in `state.py` | no-lock-argument-is-written-down, count-reads-no-DB | 2 red |

**THE PROBE FOUND A REAL GAP IN MY OWN GUARD SET, which is the entire point of R2.** The plant
"register before `accept()`" left the **whole suite green**. The reason:
`test_nothing_is_registered_before_accept` drove an *unauthorised* handshake, which returns at the
policy gate — above the accept block entirely — so it never reaches either the old or the new
registration line. The guard could not tell "registers after accept" from "refuses early". Fixed by
splitting it: `test_a_refused_handshake_never_joins` keeps the (true, weaker) claim with its
blindness written into the docstring, and a new
`test_a_socket_that_failed_to_accept_is_never_registered` drives an *authorised* handshake whose
`accept()` raises — which is the case that actually discriminates. Re-probed: 1 red, on the nose.

**Two more findings came from my own new tests failing on first run:**

1. A blank `deck_id` body answers **400**, not 422 — AD-16 superseded the auto-422 and
   `test_committed_schema.py` asserts FastAPI's 422 components are stripped. My expectation was
   wrong; the shipped behaviour is right.
2. `test_the_broadcast_helpers_are_total` initially failed on `broadcast_active_deck_changed`'s
   bare `return await broadcast(app, event)`. That call is genuinely safe *because `broadcast`
   is itself total* — so the guard now encodes the composition rule explicitly (a call is allowed
   outside a `try` only if it targets a helper the same test proves total), rather than being
   relaxed into vagueness.

**One guard is deliberately NOT probe-proven, and it is stated rather than glossed:**
`test_a_broadcast_before_the_lifespan_ran_is_a_no_op` cannot be reddened by any source plant,
because `broadcast`'s outer catch-all makes "returns 0" true for every fault it could contain. It
is true by construction, and `test_the_broadcast_helpers_are_total` is what protects the
construction. `test_a_rejected_body_broadcasts_nothing` is likewise a coverage test rather than a
guard: the body is rejected by FastAPI before the handler runs, so there is no in-handler line a
plant could move.

### Completion Notes List

**What shipped.** A `ConnectionRegistry` beside `TicketStore` in `state.py` (bare class, no-arg
init, no lock with the argument and its three breakers written down, unbounded with Q7's reasoning
stated, `connected_count` waiting for c5-5), one lifespan line in `main.py`, a `broadcast` /
`broadcast_active_deck_changed` pair plus register-around-the-drain in `ws.py`, and exactly one
awaited call in `routes/active_deck.py` where the marked comment stood. **No new module, no new
dependency, no new route, no new `ErrorReason`, no new close code, no `ui/src` behaviour change.**

**The confirmed negative held.** `npm run gen:api` left `openapi.json` and `types.d.ts`
byte-identical — nothing appears in `git status --porcelain ui/src/api/` — and the pins stayed at
**8 paths / 13 components**. `test_spa.py`'s hand-mirrored router list and reserved-prefix set
needed no edit: no new HTTP router, no new first path segment. The `:104-106` "one shape serves the
read, the write and the change notification" claim was **checked and judged TRUE as written** —
it is a claim about the *shape*, and `ActiveDeckChangedPayload` is `{deck_id: string | null}` with
the same bound and nullability as `ActiveDeck`. It is **not** a claim that one Pydantic class is
reused, and the precision now lives below `Args:` (which is truncated out of the wire), so
correcting a true sentence cost no schema regeneration.

**G7 retired and replaced (C4 retro item 13).** `test_no_connection_registry_was_scaffolded`
reddened on this story's first real line, by design. It is removed rather than weakened — its
subject, a not-yet-designed registry, no longer exists — and
`TestTheRegistryVocabularyGuardIsReplaced` takes over the surface with six guards that assert the
*shape of the presence* G7 could only assert the absence of: the fan-out/membership split, no
second registry in `ws.py`, the `create_task` ban across the whole package, the no-DB ban, one
serialiser, and that serialisation sits outside the loop. Its sibling at `:421-429` survives
**revised**: the docstring's "c5-4 owns the first message this app ever sends" is spent, but the
assertion — a socket that connects and disconnects with no broadcast sees exactly one
`websocket.accept` — is still true and now guards against a future story greeting new clients.

**The harness gap was real and is closed.** `drive_handshake` runs one handshake to completion, so
no socket is ever open concurrently with anything else — it structurally cannot prove FR-06. Added
`conftest.open_socket`: an async context manager that runs the app as a task with a controllable
receive queue, waits on the accept *and* the task (so a handler that dies fails the test with its
own traceback instead of hanging the suite), and feeds a disconnect on exit. `drive_handshake` was
refactored onto a shared `_websocket_scope` builder rather than having the scope hand-copied, and
`FakeConnection` lives in `conftest.py` because two test modules need it — c3-7 already taught this
package what two hand-synchronised fakes cost. **No test sleeps**; nothing waits on wall clock.

**Judgement call flagged for review — where AC 18's containment lives.** The route adds *one*
awaited call and no `try` (Q4 and AC 19 both say one line), so "a fault inside the broadcast never
affects the PUT's own 200" holds because the two helpers **cannot raise**, not because the route
defends against them. `test_the_broadcast_helpers_are_total` pins that structurally. A reviewer who
prefers belt-and-braces at the route would be adding a second net over a proven-total call; the
alternative is stated here rather than left implicit.

**Ledger — five dispositions, all edited in `deferred-work.md` itself.** `:2632` closed (with the
pre-c5-1 "same `ActiveDeck` shape" line corrected); `:3676` backend half closed, browser half
re-homed to c5-6; `:3584`, `:3591` and `:3680` re-homed from "c5-4 / c5-6" to **c5-6 alone** —
c5-4 turned out to be backend-only, so there are no client event handlers here for them to attach
to. `ui/src/state/deck.ts:75`, which named "c5-4 / c5-6" in shipped prose, was narrowed in the same
commit (comment only; frontend suite and `tsc` both re-measured unchanged).

**Dev Notes KB self-check.** Dev Notes section **14.4 KB**, whole story file 29.6 KB — against C4's
41 KB average for the whole file. This was the smallest-contexted story of the epic and the context
held: every one of the five headline items was load-bearing, and the two the diff would have got
wrong without them are item 2 (G7 reddens by design — otherwise it reads as a broken test to
delete) and item 5 (three ledger entries assuming client handlers that do not exist here).

### Closing measurements

| | Baseline (`51570c9`) | After |
|---|---|---|
| Python suite (`pytest -q`) | 2,723 passed / 1 skipped | **2,769 passed / 1 skipped** (+46) |
| Python suite (probe harness, `-m 'not integration'`) | 2,670 | **2,716** (+46) |
| Frontend (`vitest run`) | 1,694 / 65 files | **1,694 / 65 files** (unchanged) |
| `tsc -b --force` | clean | **clean** |
| `ruff check .` / `ruff format --check` | clean | **clean** |
| `mypy src/` and `mypy src/ --platform win32` | clean | **clean, 91 files, both** |
| OpenAPI pins | 8 paths / 13 components | **8 / 13, `gen:api` byte-identical** |
| Plugin mirror | sha256 in sync | **rebuilt and sha256-verified after the last edit** |

### File List

**Source**
- `src/companion/app/state.py` — `Connection` protocol, `ConnectionRegistry`,
  `connection_registry()` accessor, module-docstring prediction fulfilled
- `src/companion/app/ws.py` — `_registry()`, `broadcast()`,
  `broadcast_active_deck_changed()`, register/unregister around the drain, `_close_quietly`
  widened to the protocol, module and handler docstrings rewritten
- `src/companion/app/main.py` — one lifespan line (`app.state.connections`)
- `src/companion/app/routes/active_deck.py` — the one awaited call replacing the `:132` comment;
  module docstring rewritten; the `:104-106` claim checked and its precision added below `Args:`

**Tests**
- `tests/unit/companion/conftest.py` — `_websocket_scope()`, `FakeConnection`, `OpenSocket`,
  `open_socket()`; `drive_handshake` refactored onto the shared scope builder
- `tests/unit/companion/test_ws.py` — G7 retired; `TestTheConnectionRegistry`,
  `TestTheRegistryAccessor`, `TestTheRegistryVocabularyGuardIsReplaced`, `TestTheFanOut`,
  `TestTheSocketLifecycle`; `:421-429`'s sibling revised
- `tests/unit/companion/test_routes_active_deck.py` — `TestThePutBroadcasts`,
  `TestTwoTabsOnePut`, `_mint_ticket()`; the `:151` comment corrected

**Frontend (comment only)**
- `ui/src/state/deck.ts` — the "c5-4 / c5-6" re-homing narrowed to c5-6

**Artifacts**
- `_bmad-output/implementation-artifacts/deferred-work.md` — five dispositions
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — status record
- `_bmad-output/implementation-artifacts/c5-4-broadcast-to-every-connected-client.md` — this file

**Mirror (generated)**
- `plugin/server/src/companion/app/{state,ws,main,routes/active_deck}.py`

### Change Log

| Date | Change |
|---|---|
| 2026-08-08 | Branch `feat/companion-c5-4-broadcast` cut from `feat/companion-c5` at `51570c9`; baseline verified (two mismatches recorded in the Debug Log, neither a defect). |
| 2026-08-08 | All seven open questions ruled as recommended (Brad); Q1's protocol widened to three members as a consequence of Q2's close ruling. |
| 2026-08-08 | Tasks 1–4: registry, lifespan line, fan-out and register/unregister, the one route call. |
| 2026-08-08 | Task 5: `open_socket` harness, two-tabs-one-PUT wire proof, G7 retired and replaced, 13 full-suite R2 probe runs — one of which found a real gap in the guard set and produced an extra test. |
| 2026-08-08 | Task 6: `gen:api` confirmed byte-identical (8/13); five ledger dispositions; plugin mirror rebuilt and sha256-verified; suite 2,723 → 2,769; status set to `review`. |

## Sprint journal (moved verbatim from sprint-status.yaml, 2026-08-25)

MERGED via PR #56 into feat/companion-c5 at `503899b` (2026-08-08). PREVIOUSLY — CODE-REVIEWED 2026-08-08 -> done. Three layers (Blind Hunter, Edge Case Hunter, Acceptance Auditor), run blind to each other; 11 raw findings after dedup, 5 patch, 1 decision-needed (resolved by Brad), 0 defer, 8 dismissed. HEADLINE, found independently by the Auditor and confirmed against contracts.py: the diff's own "corrected" claim that ActiveDeck and ActiveDeckChangedPayload share "the same _MAX_DECK_ID_LENGTH bound" was itself false — ActiveDeck.deck_id has no length cap and no blank-refusal at all, while ActiveDeckChangedPayload's does; corrected in routes/active_deck.py and the deferred-work.md closure note. FOUR MORE PATCHES: PUT /api/active-deck read slot.deck_id twice across the awaited broadcast, so a concurrent second PUT could make a request's own 200 body disagree with what it stored and broadcast — fixed by capturing the value once before the await; _close_quietly's client_state read was unguarded and called from outside broadcast()'s per-connection try, so a raise there could have escaped the fan-out loop and silently ended delivery to every remaining client — guarded; conftest.py's open_socket cancelled its waiter task twice without awaiting it, a latent "Task was destroyed" hazard — now awaited with CancelledError suppressed. DECISION RESOLVED (Brad, accept as documented residual): two overlapping broadcasts (e.g. two concurrent PUTs) are not serialised per connection and can race a shared socket's send, spuriously evicting a healthy tab — no artifact ruled on this; accepted the same way as Q3's slow-client stall, documented in broadcast()'s docstring rather than adding a lock. Dismissed 8: mostly already-ruled design choices (Q2's 1011 reuse, Q3's no-timeout, Q7's no registry cap) or meta-observations already disclosed in the code's own comments (the totality guard's except-handler blind spot, the plugin-mirror scoping artifact of the review itself). Verified after patches: full suite 1265 passed / 1 skipped (companion package), gen:api byte-identical, ruff and mypy src/ clean, plugin mirror rebuilt and sha256-identical. Next: raise the PR. PREVIOUSLY — IMPLEMENTED 2026-08-08 off `51570c9` -> review. All 7 open questions ruled AS RECOMMENDED (Brad). SHIPPED: state.ConnectionRegistry (bare class, no lock with the argument and its three breakers written down, UNBOUNDED per Q7, connected_count waiting for c5-5's AD-8 count) behind a structural Connection Protocol so state.py still imports no web framework; one lifespan line; ws.broadcast + broadcast_active_deck_changed with register-around-the-drain; ONE awaited call in routes/active_deck.py where the marked comment stood. No new module, dependency, route, ErrorReason or close code. THE CONFIRMED NEGATIVE HELD: gen:api byte-identical, pins unmoved at 8 paths / 13 components, test_spa.py untouched. G7 (test_no_connection_registry_was_scaffolded) RETIRED AND REPLACED by six guards that assert the shape of the presence rather than the absence (C4 item 13); its sibling at :421-429 survives REVISED. THE HEADLINE: R2's 13 full-suite probe runs FOUND A REAL GAP IN THE STORY'S OWN GUARD SET — the plant 'register before accept()' left the WHOLE SUITE GREEN, because test_nothing_is_registered_before_accept drove an UNAUTHORISED handshake, which returns at the policy gate above the accept block and so never reaches either registration line; the guard could not distinguish 'registers after accept' from 'refuses early'. Split into a renamed weaker guard with its blindness documented plus a new test_a_socket_that_failed_to_accept_is_never_registered driving an AUTHORISED handshake whose accept() raises; re-probed, 1 red on the nose (+1 test, 2715 -> 2716 collected). Two more findings came from my own tests failing first: a blank deck_id answers 400 not 422 (AD-16 superseded the auto-422), and the totality guard correctly rejected 'return await broadcast(...)' until it encoded the composition rule explicitly. TWO GUARDS DELIBERATELY NOT PROBE-PROVEN AND SAID SO: broadcast-before-lifespan cannot be reddened by any plant (the outer catch-all makes 'returns 0' true for every fault it could contain), and rejected-body is a coverage test since FastAPI refuses before the handler runs. JUDGEMENT CALL FLAGGED FOR REVIEW: AC 18's containment lives in the HELPERS (proven total structurally) rather than in a route-level try, because Q4/AC 19 both say the route adds exactly one line. The :104-106 'one shape serves the read, the write and the change notification' claim was CHECKED AND JUDGED TRUE as written — it claims a SHAPE, and ActiveDeckChangedPayload is {deck_id: string|null} with the same bound; the precision that it is a different CLASS lives below Args:, which is truncated out of the wire, so a true sentence cost no regeneration. Ledger: 5 dispositions — :2632 closed (its pre-c5-1 'same ActiveDeck shape' line corrected), :3676 backend half closed / browser half to c5-6, and :3584/:3591/:3680 re-homed from 'c5-4 / c5-6' to c5-6 ALONE (Q6: c5-4 is backend-only, there are no client handlers here); ui/src/state/deck.ts:75 narrowed in the same commit. Suite 2,723 -> 2,769 passed (+46), probe harness 2,670 -> 2,716; frontend 1,694 / 65 UNCHANGED and tsc clean; ruff and mypy src/ (both platforms) clean; plugin mirror rebuilt and sha256-verified after the last edit. BASELINE MISMATCH WORTH KNOWING: the frontend suite failed ONE test on its first baseline run and was green on re-run and at close — one flaky frontend test exists, detail lost to a tail pipe, recorded not chased. Dev Notes 14.4 KB (file 29.6 KB) vs C4's 41 KB average — the smallest-contexted story of the epic, and the context held. Next: three-layer review.  # CONTEXTED 2026-08-08 off `51570c9` -> ready-for-dev. 26 ACs, 7 open questions (Q1-Q3 rule the only undesigned surface: the registry API, the send-failure policy, and sequential-vs-timed sends — nothing in any artefact specifies what a broadcast does when one socket's send raises). Dev Notes ~9 KB, the smallest yet under R1. HEADLINE: EVERY HOME IS PRE-BOOKED BY SHIPPED PROSE — `state.py:19` ("c5-4's connection registry joins them"), `ws.py:42-46` ("deliberately absent... c5-4 owns the registry and the fan-out"), and `routes/active_deck.py:132`'s marked insertion-point comment; no new module is sanctioned, and all three prose sites go stale the moment code lands (c3-9 same-commit corrections owed). SECOND: guard G7 (`test_ws.py:431-441` test_no_connection_registry_was_scaffolded) reddens BY DESIGN on this story's first real line and per C4 retro item 13 its removal + replacement guard set re-enter review, never `git rm`; its sibling at `:421-429` ("c5-4 owns the first message this app ever sends") survives revised. THIRD: the payload question is ALREADY ANSWERED by the frozen contract, not the ledger — dw:2636's "same ActiveDeck shape" predates c5-1; the wire object is `ActiveDeckChangedEvent{kind,id,ts,payload{deck_id}}` validated via `TypeAdapter(AgentEvent)`, and `contracts.py:890-894` carries Brad's Q10 ruling this story must not re-litigate: the signal fires on EVERY set including a same-id rewrite, because "only broadcast if it changed" is a read-modify-write and the slot's no-lock design forbids it. FOURTH: the story is BACKEND-ONLY (ui/src makes no WS connection until c5-6) yet three ledger entries homed on "c5-4 (the event handlers)" assumed client handlers exist here — dw:3584/3591/3680 need Q6's re-homing ruling to c5-6, edited in deferred-work.md in the same commit. Five ledger dispositions total (dw:2632 the broadcast seam CLOSES here; dw:3676's backend half discharges, browser half re-homes). Testing gap named: `drive_handshake` runs ONE handshake to completion, so the multi-tab AC needs a task-based concurrent-socket conftest helper plus registry fakes behind a structural Protocol — the real-socket proof stays c5-8's (AD-10). Confirmed-negative schema story (c5-1/c5-3's shape): gen:api byte-identical, 8 paths / 13 components pinned, no test_spa.py edit owed. Landmines pre-gripped: no `"host"` string literal and no {socket,uvicorn,serve,bind,listen} identifier in ws.py, no {token,agent_token,credential,secret,mint_token} identifier in state.py, no {60,15} literal (MAX_TICKETS chose 256 for this), no create_task (AD-9), no DB read on the push path (AD-7), agent token in no frame (AD-5). Key-grep: 9 hits, all obligations, none falsified yet. Baselines: Python 2,670 passed / 54 deselected, frontend 1,694 / 65, starlette 0.48.0 / fastapi 0.140.0 / websockets 16.1.1. Next: answer Q1-Q7, then dev-story c5-4.
