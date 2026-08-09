---
epic: c6
story: c6-2
work_branch: feat/companion-c6
story_branch: feat/companion-c6-2-set-active-deck
depends_on: [c6-1, c3-4, c5-4]
baseline_commit: 38d5b3f
---

# Story c6-2: `companion_set_active_deck` — the agent chooses what the glass shows

Status: done

<!-- Ultimate context engine analysis completed 2026-08-09 — comprehensive developer guide created.
     Sources: epics-companion-app.md Story 6.2 + Stories 3.4/5.1/5.4/6.1/6.3/6.4, ARCHITECTURE-SPINE
     2026-07-25 (AD-1/2/3/4/5/7/8/9/10/15/16 + Consistency Conventions), EPIC-SPLIT E5, PRD 2026-07-22
     (FR-07/12/13/14, CM-1, CM-3), shipped code on feat/companion-c6 @ 38d5b3f, c6-1 + c3-4 + c5-4
     story records, deferred-work ledger (c6-1 block + dw:2792), C5 retro. -->

## Story

As Brad,
I want to tell my agent which deck to put on the glass,
So that the browser follows the conversation instead of me managing it.

## The story in one paragraph

This is the **first companion MCP tool** — the wiring story c6-1 deliberately left out. A new
`async def companion_set_active_deck(deck_id)` registers in `build_server()`
(`src/mcp_server/server.py`) beside the Epic-1 tools, validates deck existence **itself** against the
database (`DeckRepository.get_deck`), and only for a deck that exists sends
`PUT /api/active-deck` through the c6-1 leaf machinery: `live_instance()` identity proof →
`_send(method="PUT", ...)` with `Authorization: Bearer {token}` → retry exactly once on 403 → one
closed outcome token. A missing deck returns `deck_not_found` **without contacting the backend**
(AD-16 — the backend deliberately stores whatever it is given and has no DB at all on that route).
The tool keeps no state (CM-3 — the active deck lives in backend memory only), never raises (FR-12),
and returns a compact result under ~200 tokens (CM-1). The backend's own `active_deck_changed`
broadcast (c5-4) fires on the PUT — this story emits nothing itself and touches no `ui/` code
(the glass following the choice is c6-3). Known contract gap needing a ruling before code: the epic
AC wants `displayed` **plus the client count**, but the shipped PUT answers `200 ActiveDeck
{"deck_id"}` with no count — see Open Question 1.

## Acceptance Criteria

*(Verbatim from `epics-companion-app.md` Story 6.2, lines 2714-2746; annotations in italics.)*

1. **Given** the tool is defined **When** its signature is inspected **Then** it is `async def`,
   matching the existing Epic-1 tools — a blocking POST in a sync tool would hold a FastMCP
   threadpool worker for a whole round trip (AD-8). *(17 of the 19 shipped tools are `async def`;
   `load_deck` at `server.py:248` is the canonical shape. The leaf client is async-only — c1-8
   Decide-once #2 — so there is no sync alternative anyway.)*

2. **Given** a deck id that exists **When** the agent calls `companion_set_active_deck(deck_id)`
   **Then** the tool calls `PUT /api/active-deck` with the agent token and returns a compact text
   result carrying `displayed` and the client count (FR-07). *(The client count is not on the shipped
   PUT response — Open Question 1 rules how this AC is satisfied.)*

3. **Given** a deck id that does not exist **When** the tool runs **Then** it validates existence
   **itself**, against the database, and returns `deck_not_found` without contacting the backend
   (AD-16) **And** this token is a documented addition to AD-8's set for the control tool, since
   AD-16 requires the tool — not the backend — to report it. *(Ruled twice already: the dw:10 ledger
   line — "the client cannot observe it, so it belongs at the MCP tool layer, not in
   `PushOutcomeToken`" — and `routes/active_deck.py`'s docstring: "A `PUT` naming a deck that does
   not exist therefore **succeeds**." `deck_not_found` is layered in the TOOL's vocabulary; the
   client's closed five stays closed.)*

4. **Given** the backend is not running **When** the tool runs **Then** it returns `app_not_running`
   as a text result and never raises (FR-12). *(The leaf already produces this token for
   missing/corrupt discovery, dead port, failed probe, and `instance_id` mismatch — reuse
   `live_instance()`, add no probing of your own.)*

5. **Given** the tool returns **When** its result is measured **Then** it is under roughly 200
   tokens and echoes no payload back into chat (CM-1).

6. **Given** the MCP server package after this story **When** it is inspected **Then** it holds no
   active-deck state — the state lives in backend memory only (CM-3) **And** the import-boundary
   test still passes, proving no `src.companion.app` import was introduced (AD-3). *(Both halves are
   already-shipped guards that must stay green: `tests/unit/companion/test_import_boundary.py`
   permits leaf imports from `src/mcp_server`; `tests/unit/companion/test_routes_active_deck.py:721`
   asserts the MCP side holds no active-deck state — keyed on state-holding, not on the tool's name,
   precisely so this story's correct change cannot red it.)*

## Tasks / Subtasks

- [x] **Task 0 — Verify the baseline and grep your own key** (AC: all)
  - [x] Confirm branch `feat/companion-c6` at/after `38d5b3f`; cut story branch from it.
  - [x] `uv run pytest -m "not integration"` → expect **2,810 passed / 1 skipped / 55 deselected**
        (2,811 collected — the c6-1 baseline).
  - [x] `grep -rn "c6-2" src/ tests/ scripts/ _bmad-output/implementation-artifacts/deferred-work.md`
        and reconcile every hit against the dispositions table in Dev Notes.
  - [x] Read end to end before writing anything: `src/companion/client.py`,
        `src/companion/app/routes/active_deck.py`, `src/mcp_server/server.py` (registration blocks),
        `src/mcp_server/tools/view_deck.py` (the closest tool skeleton),
        `tests/unit/companion/test_client.py` (the stub harness).
- [x] **Task 1 — The wire receipt (only if Q1 is ruled as recommended)** (AC: 2)
  - [x] `src/companion/contracts.py`: add the PUT-response receipt model (recommended
        `ActiveDeckSetReceipt`, `extra="forbid"`, `deck_id: str`, `clients: int = Field(ge=0)`),
        mirroring `EventIngestReceipt`'s tightness. Do not touch `ActiveDeck` (the GET keeps it).
  - [x] `src/companion/app/routes/active_deck.py`: capture `broadcast_active_deck_changed`'s
        already-returned `int` (today it is discarded) and return the receipt from the PUT;
        `response_model` updated; GET untouched.
  - [x] Regenerate the committed artifacts through the shipped pipeline (c2-3): the OpenAPI
        byte-snapshot (`test_committed_schema.py`) and `ui/src/api/openapi.json` → `npm run
        gen:types` → `ui/src/api/types.d.ts`. `schema.ts` (the single reader) does not change — the
        SPA never calls the token-gated PUT (AD-5).
  - [x] Update `tests/unit/companion/test_routes_active_deck.py`'s PUT-shape assertions to the
        receipt, including a clients-count row driven through a registered stub connection.
- [x] **Task 2 — The leaf client verb** (AC: 2, 3, 4)
  - [x] `src/companion/client.py`: add `ACTIVE_DECK_PATH = "/api/active-deck"` beside
        `HEALTH_PATH`/`EVENTS_PATH`, and one new **public named function** (Q1 ruling from c6-1:
        `_send` stays private; "a story that needs another verb adds another named function") —
        recommended `async def set_active_deck(request: ActiveDeckRequest, *, timeout: httpx.Timeout
        | None = None) -> PushOutcome`, accepting a concrete already-valid instance exactly as
        `push_event` accepts a concrete envelope (no re-validation inside the leaf).
  - [x] Reuse `live_instance()` + `_send(record, method="PUT", path=ACTIVE_DECK_PATH, body=...,
        timeout=timeout)` — same header, same `trust_env=False`, same `PROBE_TIMEOUT` defaults.
        **Do not reuse `_outcome_for`/`_attempt`** — both are hard-wired to the push (a 200 here
        parses as the PUT receipt, not `EventIngestReceipt`). Add sibling private helpers.
  - [x] Same whole-call deadline and retry shape as `push_event`: `asyncio.timeout(_PUSH_TOTAL_SECONDS)`,
        403 → full `live_instance()` re-read → one retry; second 403 → `backend_error`; re-read
        finding nothing live → `app_not_running`; 400/413 → `payload_rejected`; parse the 200 body
        with the shipped receipt model (its `ge=0` is the net — the c6-1 `{"clients": -1}` lesson);
        map on **status codes only**, never `reason` strings; never raises beyond the
        `(TimeoutError, httpx.HTTPError, ValueError)` carve-out.
- [x] **Task 3 — The MCP tool** (AC: 1, 2, 3, 4, 5, 6)
  - [x] New `src/mcp_server/tools/companion.py` (the module c1-8's plan note reserved): the result
        model (Q2) + `async def set_active_deck(session, *, deck_id) -> ...` helper following
        `view_deck.py`'s skeleton — `is_database_initialized` guard → `DeckRepository.get_deck(deck_id)`
        (the cheap read; **not** `get_deck_with_cards`) → `None` ⇒ `deck_not_found`, **client verb
        not called** → `except DatabaseError` ⇒ `error` with `logger.exception` → otherwise build
        `ActiveDeckRequest` and delegate to `client.set_active_deck` → map `PushOutcome` 1:1 into
        the tool result plus a compact `message`.
  - [x] Register in `build_server()` (`src/mcp_server/server.py`): `@mcp.tool()` bare decorator,
        `async def companion_set_active_deck(deck_id: str)`, Google-style docstring that is the
        LLM-facing description (say when to use it, that the id comes from `create_deck`/`list_decks`,
        and enumerate the closed `status` vocabulary under `Returns:`).
  - [x] Keep the tool stateless — no module/closure state, nothing cached between calls (CM-3).
- [x] **Task 4 — Tests** (AC: all)
  - [x] `tests/unit/companion/test_client.py`: `_StubHandler` currently implements only
        `do_GET`/`do_POST` — a PUT meets a stdlib **501**. Add `do_PUT` + a `put_script` +
        `.puts` property mirroring the POST machinery (including `on_put` for mid-call identity
        restarts and the HANGUP/DRIP sentinels where reachable).
  - [x] New client-verb classes mirroring the c6-1 push classes: happy path (receipt count ≥ 1 →
        `displayed`), `clients: 0` → `no_clients_connected`, 400 and 413 → `payload_rejected`,
        403 → mid-call re-plant → **assert the second PUT carries the newly planted token and
        exactly two PUTs left the client** (c5-8 F5: presence-only re-read checks are vacuous),
        403→403 → `backend_error` with exactly two PUTs, malformed/negative-count 200 bodies →
        `backend_error`, dead/silent/foreign-identity → `app_not_running` with **zero** PUTs and no
        token in any recorded byte, token-never-logged sweep rows for the new paths. Every test
        pairs the full-model equality with a request-count assertion.
  - [x] `TestExportedSurface`: pin `ACTIVE_DECK_PATH == "/api/active-deck"` in the established
        style (one literal assertion + story/AC citation). Do **not** widen `PUSH_OUTCOMES` —
        `TestOutcomeVocabulary` pins the closed five by set equality, and `deck_not_found` lives
        above the client by ruling.
  - [x] Tool-layer tests (new file beside the existing MCP tool tests, e.g.
        `tests/integration/mcp_server/test_companion_tool.py` — note these run in the `not
        integration` set; a directory is not a marker): real seeded `AsyncSession`, the client verb
        stubbed per Q4's ruling. Cover: existing deck → delegation with the right
        `ActiveDeckRequest` + status mapping for every `PushOutcome` token + `clients` passthrough;
        missing deck → `deck_not_found` **and the client-verb stub was never called** (this is AC 3's
        "without contacting the backend" made mechanical); DB-not-initialized → the shared message
        constant; `DatabaseError` → `error`; result compactness (serialized result bounded well
        under the ~200-token budget; no deck list, no payload echo).
  - [x] `tests/integration/test_build_plugin.py::test_server_registers_expected_tools`: the exact
        19-name set becomes 20 with `companion_set_active_deck` (red until updated — by design).
        While in the file, fix the stale "17-tool surface" claim at line 10 by **grepping the
        claim** repo-wide (`17-tool`, `19 expected`), not the sentence (the R1 sweep lesson).
  - [x] **No new integration test and no change to `test_live_backend.py`** (AD-10's exactly-one
        rule; c6-1 Q3 precedent — the real-socket test stays hand-rolled and push-shaped).
  - [x] Plant one red through the full suite (`uv run python -m scripts.probe_harness --expect-red
        '<node-id>'`): recommended plant — make the helper call the client verb even when
        `get_deck` returned `None` (the AC-3 bypass). The never-called assertion must red; record
        what the guard compares and what it cannot see, then revert.
  - [x] If Q5 is ruled yes: add the 401 row to the unexpected-status parametrization of **both**
        the push and the new verb (401 → `backend_error`, no retry, exactly one request) and mark
        the dw 401-vs-403 entry closed.
- [x] **Task 5 — Prose fulfilment, ripple sweep, quality gates, mirror**
  - [x] Reconcile every `c6-2` promise-site per the dispositions table (Dev Notes): close dw:10's
        two-need entry as CLOSED by this story; rewrite `state.py:12`'s forward-looking "(c6-2)"
        prose from promise to present-tense pointer; **mint no new forward-looking cross-module
        prose** (R2 standing rule — nothing about c6-4 in `companion.py` beyond present tense).
  - [x] Skills-are-a-ripple-site sweep: `grep -rn` the tool-surface enumerations —
        `.claude/skills/**`, `plugin/skills/**`, `README.md`, `docs/**` — for tool lists/counts that
        the new tool invalidates; update or record "no hits" in the Dev Agent Record. (c6-1's review
        explicitly flagged this story as the one the standing gotcha waits for.)
  - [x] `uv run ruff check . --fix && uv run ruff format .`; `uv run mypy src/` (strict); full
        Python suite green and strictly larger than 2,810; frontend suite untouched unless Task 1
        regenerated artifacts (then `npm test` green, `npm run format:check` green).
  - [x] Rebuild `plugin/` (`scripts/build_plugin.py`) **after the last edit** — review patches count
        as edits — and sha256-verify the mirrors (`plugin/server/src/**` is a build artifact, never
        hand-edited).
  - [x] Record the Dev Notes KB self-check in the Dev Agent Record (target band: 10–20 KB).
  - [x] Set story status to `review` and **STOP** — Brad runs the three-layer review and raises the PR.

### Review Findings

- [x] [Review][Patch] `companion_set_active_deck`'s `deck_not_found` result is unbounded and can exceed the ~200-token CM-1/AC-5 compactness budget [src/mcp_server/tools/companion.py:137-142] — fixed: added `_ECHO_LIMIT = 48`, truncates the echoed value via `_truncate_for_echo()`. **Widened after Greptile's PR review** caught that the first pass only covered the `deck_not_found` branch: `database_not_initialized` and `error` also echoed the raw unbounded `deck_id`, and the found-deck branches echoed `deck.name` (unbounded in storage — `create_deck` only refuses blank) into both the `deck_name` field and the `displayed` message. All four branches now route through the same helper; new tests cover each (oversized id on `database_not_initialized`/`error`/`deck_not_found`, oversized name on `displayed`); `_MISSING_DECK` shortened so its exact-match assertion isn't itself truncated.
- [x] [Review][Patch] `companion_set_active_deck` holds the DB session open across the full outbound HTTP round-trip to the companion (up to `_PUSH_TOTAL_SECONDS` = 10s) [src/mcp_server/server.py:440-441] — fixed: `await session.close()` added in `tools/companion.py` right after the deck-found check (the deck is already a detached schema), before the client call.
- [x] [Review][Patch] `client.py`'s module docstring and `_send`'s docstring are stale — both still describe the module as having "two halves" / `push_event` as the sole public verb, unchanged by this story's addition of `set_active_deck` as a second public verb [src/companion/client.py:1-9, 344-346] — fixed: both docstrings now name `set_active_deck` as the third wire operation / second public verb.
- [x] [Review][Defer] `companion_set_active_deck`'s `deck_id` is not `.strip()`-ed before the DB lookup, unlike `deck_analysis.py`/`deck_management.py`'s convention [src/mcp_server/tools/companion.py:128] — deferred, pre-existing inconsistency across the MCP tool suite (this story correctly followed its cited skeleton, `view_deck.py`, which also does not strip)

## Dev Notes

### The state you are consuming (all shipped — modify only where a Task says so)

**`src/companion/client.py` (490 lines) — the c6-1 leaf.** Public surface: `LOOPBACK_HOST`,
`HEALTH_PATH`, `EVENTS_PATH`, `PROBE_TIMEOUT` (connect 1.0 / read 2.0 / write 2.0 / pool 2.0),
`PushOutcomeToken` (closed five), `PUSH_OUTCOMES`, `PushOutcome` (frozen, `extra="forbid"`,
`outcome` + `clients: int | None = None`), `base_url`, `probe_health`, `live_instance`. Private:
`_PROBE_TOTAL_SECONDS = 5.0`, `_PUSH_TOTAL_SECONDS = 10.0` (whole-call, covers two attempts, pinned
`>= 2 * _PROBE_TOTAL_SECONDS`), `_send`, `_outcome_for`, `_attempt`. The pieces this story reuses
verbatim:

```python
async def _send(
    record: DiscoveryRecord, *, method: str, path: str, body: str, timeout: httpx.Timeout | None
) -> httpx.Response | None:
```

— generic over method/path **by ruling, for this story** (dw:10); one `Authorization: Bearer
{record.token}` header, `content-type: application/json`, `trust_env=False` (the c1-8 proxy lesson —
httpx grants loopback no proxy exemption), whole body inside `except (TimeoutError, httpx.HTTPError,
ValueError)` → `None`, deliberately not `except Exception`. Note `timeout` is a **required** keyword
here (no default) — pass it explicitly. `live_instance()` = discovery read → `/health` probe →
`instance_id` match; `None` means *app not running* with **no token ever sent**.

**What you cannot reuse:** `_outcome_for` parses every 200 as `EventIngestReceipt` and `_attempt` is
hard-wired to `POST /agent/events`. A `PUT /api/active-deck` 200 body is a different model — reusing
the push pair would turn every successful set-active into `backend_error`. Add siblings; do not
widen the push functions.

**`PUT /api/active-deck` (`src/companion/app/routes/active_deck.py:107`, router prefix `/api`).**
`AgentToken`-gated (`Authorization: Bearer <discovery token>` — the exact header `_send` already
sends; the route docstring names `client._send` as its intended audience). Body
`ActiveDeckRequest {"deck_id": 1..256 chars, non-blank, extra="forbid"}`. Success today: `200
ActiveDeck {"deck_id": <echoed>}` — **no client count** (Open Question 1). Wire errors: `403
{"reason":"forbidden"}` (missing/malformed/wrong credential, byte-identical all three), `413` (64 KB
pre-parse `BodyCapMiddleware`), `400 invalid_request` (validation), `500 internal_error`. **There is
no 404 on this route and no DB behind it** — "the backend stores what it is given" is AD-16's ruling,
not an oversight. Side effect: `slot.set(deck_id)` then `await
broadcast_active_deck_changed(request.app, deck_id)` — which **returns the delivered-client count as
an `int`** (`ws.py:424`) that the route currently discards, and which fires on every set including a
same-id rewrite (ruled; a duplicate costs one idempotent refetch — the tool must NOT dedupe).

**`GET /api/active-deck`** is same-origin, token-free, browser-facing — this story never calls it.

**MCP server (`src/mcp_server/`).** Tools are closures inside `build_server()` decorated bare
`@mcp.tool()` (FastMCP from `mcp>=1.27.0`; name from the function, description from the docstring),
delegating to helpers in `src/mcp_server/tools/<x>.py` that own the pydantic result models. The
canonical async shape (`server.py:248`):

```python
@mcp.tool()
async def load_deck(deck_id: str) -> DeckResult:
    """...Returns: A result whose ``status`` is ``ok`` (...) or ``not_found``."""
    async with session_factory() as session:
        return await _load_deck_helper(session, deck_id=deck_id)
```

Result convention: pydantic model with a closed `Literal` **`status`** + human `message`; tools never
raise — `DatabaseError` → `status="error"` with `logger.exception`; un-imported DB →
`status="database_not_initialized"` with the shared `DATABASE_NOT_INITIALIZED_MESSAGE`
(`tools/messages.py`). `view_deck.py` is the closest skeleton (guard → cheap read → side effect →
compact result). Deck existence read: `DeckRepository.get_deck(deck_id) -> Deck | None`
(`src/data/repositories/deck.py:119`) — schemas out, never ORM models; `get_deck_with_cards` is the
heavy read this story does not need.

**Import boundary (`tests/unit/companion/test_import_boundary.py`).** `src/mcp_server/**` may import
`src.companion.contracts | discovery | client` at module level **today, with no guard edit** — the
`mcp_server` role bans only `src.companion.app`. This story lands the first such import. If you
touch `client.py`'s own imports: leaf may import only stdlib, `pydantic`, `httpx`, `src.paths`, its
two sibling leaves — and `if TYPE_CHECKING:` counts as module-level in every role.

**Statelessness guard.** `tests/unit/companion/test_routes_active_deck.py:721` asserts the MCP side
holds no active-deck state, deliberately keyed on state-holding rather than the phrase "active deck"
so this story's correct change stays green. Keep it that way: the tool reads the DB, calls the
client, returns — nothing retained.

### The wire → token mapping for the control verb (the client half in one table)

| Wire result of `PUT /api/active-deck` | Client-verb outcome | Notes |
|---|---|---|
| no discovery / dead port / identity mismatch | `app_not_running` | zero PUTs, no token sent |
| `200` + receipt, count ≥ 1 | `displayed` | count as sibling `clients` (Q1) |
| `200` + receipt, count == 0 | `no_clients_connected` | stored fine; nobody watching |
| `400` or `413` | `payload_rejected` | c5-5 Q7 fold — do not re-litigate |
| first `403` | full `live_instance()` re-read, retry once | 403, **not** 401 (c3-4 errors.py ruling) |
| second `403` | `backend_error` | exactly two PUTs max, ever |
| re-read finds nothing live | `app_not_running` | c6-1 Q2 ruling |
| 5xx / unexpected code / malformed 200 / transport failure / whole-call timeout | `backend_error` | 401 included (no retry) |

The tool layers above it: `deck_not_found` (before any HTTP), `database_not_initialized` and `error`
(the DB read's own failures, per the repo-wide tool convention — Q2).

### Ruled — settled, do not re-derive

1. **`deck_not_found` is tool-level, never client-level** (dw:10, Brad 2026-08-09; AD-16; epic AC 3).
   The client cannot observe it — no 404 exists on the route. `PushOutcomeToken` stays exactly five;
   `TestOutcomeVocabulary` pins that by set equality.
2. **`_send` stays private; a new verb is a new named public function** (c6-1 Q1, Brad 2026-08-09).
3. **Retry semantics are fixed** (c6-1 Q2): the retry re-runs the **full** `live_instance()` —
   AD-4's verify-before-you-send has no once-per-call exemption; only a second 403 is
   `backend_error`; a failed re-read is `app_not_running`.
4. **403 triggers the retry, not 401** (c3-4: the raise path structurally cannot attach the
   `WWW-Authenticate` header a 401 requires). 401 folds into `backend_error`, unretried.
5. **400 and 413 both fold into `payload_rejected`** (c5-5 Q7, Brad 2026-08-08).
6. **Map on status codes, never `reason` strings** (c6-1).
7. **Field names: the client says `outcome`, the tool says `status`** (dw:3098). The collision ruling
   cuts the other way here: `status` IS the MCP-side result key, and `deck_not_found` is already an
   established MCP `status` spelling — the tool result aligns with both vocabularies by design.
8. **The leaf is async-only** (c1-8 Decide-once #2); companion tools are `async def` (AD-8 —
   epic AC 1 spells out why).
9. **No client-side pre-checks** (c6-1 Q5): the backend's answer is authoritative; the verb accepts
   a concrete valid `ActiveDeckRequest` instance and re-validates nothing (mirror of push_event's
   concrete-envelope ruling).
10. **AD-7's no-DB-read rule does not apply** — "`set_active_deck` is control, not a push" (AD-16).
    The tool's DB read is required, and it is a **read** (AD-2's write-ban AST guard covers
    `src/companion/**`; the tool lives in `src/mcp_server/**` but must obviously stay read-only).
11. **No clear verb** (dw:2792, Q3 part 3, Brad 2026-08-01): `ActiveDeckRequest.deck_id` is
    non-nullable; the only transitions are *set* and *process restart*. Nothing in this story builds
    a "stop displaying" mode — if ever wanted it is a `DELETE`, and the ledger entry stays unowned.
12. **Merge ≠ release**: story PR targets the `feat/companion-c6` umbrella (Greptile per story);
    no tag/CHANGELOG until c8-4.

### The pattern to copy (solved problems — do not invent)

- **Verb structure**: `push_event` is the template — serialize, `asyncio.timeout(_PUSH_TOTAL_SECONDS)`,
  attempt → 403-retry → terminal `backend_error`, `except TimeoutError` → `backend_error`. Reuse
  `_PUSH_TOTAL_SECONDS` (same two-attempt shape; a new constant would need its own pin and buys
  nothing). Whether you factor a shared retry loop or mirror the ~10 lines is your call — mirroring
  is fine at this size; factoring must not touch `push_event`'s tested behaviour.
- **Parse the 200 body with the shipped receipt model, never `body["clients"]`** — the c6-1 lesson:
  `{"clients": -1}` sails through a hand-rolled check; the model's `ge=0` makes it the
  `backend_error` it is. Put the negative-count row in the new matrix too.
- **Tool skeleton**: `view_deck.py` (guard → read → side effect → compact result). Messages:
  reuse `DATABASE_NOT_INITIALIZED_MESSAGE`; keep others one short sentence — `deck_not_found`'s
  message should point at `list_decks` (the agent's recovery move), `app_not_running`'s at launching
  the companion.
- **Test discipline**: every wire test pairs full-model equality with a request-count assertion
  carrying a *why* message; the retry test re-plants identity **mid-call** via the stub hook
  (a token planted before the call is read on attempt one; planted after, never read at all);
  discriminate by asserting **which token each PUT carried**.

### Grep-own-key: expected `c6-2` hits and their dispositions (verify at Task 0)

| Site | Disposition |
|---|---|
| `deferred-work.md:9-11` (the two-need entry) | **Fulfilled by this story** — mark ~~struck~~ ✅ CLOSED by c6-2, the c5-4 precedent shape |
| `deferred-work.md` 401-vs-403 entry | Closed only if Q5 ruled yes; otherwise leave open, untouched |
| `deferred-work.md:2798` (clear verb, "most plausibly c6-2") | **Not triggered** — no caller wants it; annotate not-triggered, stays unowned |
| `src/companion/app/state.py:12` ("`companion_set_active_deck` (c6-2) calls…") | Promise → pointer: drop the story key, keep the present-tense fact (R2) |
| `src/companion/app/routes/active_deck.py:16-20` (AD-16 prose) | Already present-tense about the tool; verify wording still true after Q1, story key absent |
| `src/companion/contracts.py` `ActiveDeck` docstring ("that is the MCP tool's job") | Present-tense, stays; verify still accurate |
| `tests/unit/companion/test_routes_active_deck.py:721-723` | Guard stays green by design — do not edit |
| Ledger/sprint prose (`_bmad-output/**`) | Records, not code — leave |

### Landmines specific to this story

1. **The stub answers PUT with 501 today.** `_StubHandler` implements only `do_GET`/`do_POST`; an
   unextended harness makes every new test see `backend_error` and prove nothing. `do_PUT` +
   `put_script` + `.puts` (+ `on_put`) come first.
2. **Two receipt models, two 200-parsers.** `EventIngestReceipt` is the push's; the PUT's is
   Task 1's (or `ActiveDeck` if Q1 is ruled the other way). Wiring the wrong parser is invisible at
   type level and turns success into `backend_error` — exactly why `_outcome_for` must not be reused.
3. **`ActiveDeck` ≠ `ActiveDeckChangedPayload`** — distinct classes with different constraints;
   don't conflate them when reading `contracts.py`.
4. **The exact-set tool pin**: `test_build_plugin.py::test_server_registers_expected_tools` is a
   19-name set equality — red until updated. Its module docstring still says "17-tool surface"
   (stale at 19 before you start); fix by grepping the **claim**, not the sentence (R1 lesson:
   the planned 3-site sweep needed 6).
5. **Registration alone is half the wiring** — the closure must go through `session_factory()` like
   `load_deck`; a helper imported but never registered, or registered without the docstring
   vocabulary, passes mypy and fails the epic's intent. The in-process
   `create_connected_server_and_client_session` pattern exists if you want one registration-level
   test beyond the set pin.
6. **R2 standing rule**: no forward-looking cross-module prose. `companion.py`'s module docstring
   describes what it *is*; c6-4's future residence there is a ledger fact, not a docstring
   paragraph.
7. **`plugin/server/src/**` is a build artifact** — never hand-edit; rebuild after the last edit and
   sha256-verify (ten mirrors matched at c6-1's merge; keep it ten-for-ten, plus any new file).
8. **`MemoryError` propagates by design** in the leaf (not `except Exception`); the tool helper
   likewise should catch `DatabaseError`, not `Exception` — an unknown bug crashing loudly is the
   convention (`view_deck.py` shows the split).
9. **Result compactness is an AC, not a style note** (CM-1): no deck list in the message, no echo of
   anything the agent already said, bounded serialized size — pin it in a test.
10. **`asyncio_mode = "auto"`** — no `@pytest.mark.asyncio`; mypy strict everywhere in `src/`
    (`tests.*` exempt); ruff line-length 100; Google docstrings; `%`-style lazy logging; UTC-aware
    datetimes only.

### Testing requirements

- Client verb: extend `tests/unit/companion/test_client.py` only — real loopback stubs, no mocked
  transports, `FAST` timeouts only for dead/silent cases. Matrix rows listed in Task 4. Planted-red
  probe via `scripts/probe_harness.py --expect-red` on the guard of consequence, reverted, with one
  recorded line on what it compares and cannot see.
- Tool helper: seeded real `AsyncSession` (the existing `tests/integration/mcp_server/` fixtures),
  client verb stubbed per Q4 — assert delegation arguments, 1:1 status mapping, `clients`
  passthrough, and above all **the stub never fires on the missing-deck path**.
- Registration: the exact-set pin (19 → 20). No new `integration`-marked test; `test_live_backend.py`
  untouched (AD-10).
- Suite arithmetic recorded before/after: Python baseline 2,810 passed / 1 skipped / 55 deselected
  (2,811 collected); frontend 1,868 / 69 files — unchanged unless Task 1 regenerates artifacts, and
  even then only committed-artifact bytes move, no `ui/src` component changes.

### Previous-story intelligence (c6-1, merged 2026-08-09 via PR #63)

- The review's four patches were all prose/proof honesty (forward-looking prose trimmed to the
  ledger; an overclaiming "never raises… ever" docstring narrowed; a wrong suite count; a stub lock
  that didn't guard what its comment claimed). Write claims the diff can prove.
- The planted red fired 3-red-and-no-more through the full suite — "confined to the path" is itself
  the signal. Aim for the same shape.
- Dev Notes 13.4 KB landed in the 10–20 KB band; keep this story's there too.
- Two lessons the c6-1 record explicitly addressed to this story: parse 200 bodies with the shipped
  model (`ge=0` net), and restart identity **mid-call** via the stub hook with token-discriminating
  assertions.

### Project structure notes

- New: `src/mcp_server/tools/companion.py`; `tests/integration/mcp_server/test_companion_tool.py`.
- Update: `src/companion/client.py` (verb + constant), `src/mcp_server/server.py` (registration),
  `tests/unit/companion/test_client.py`, `tests/integration/test_build_plugin.py`; if Q1 —
  `src/companion/contracts.py`, `src/companion/app/routes/active_deck.py`,
  `tests/unit/companion/test_routes_active_deck.py`, `tests/unit/companion/test_committed_schema.py`,
  committed `ui/src/api/openapi.json` + `ui/src/api/types.d.ts` (regenerated, not hand-written).
- Never: `src/companion/app/**` imports from `src/mcp_server`; hand edits under `plugin/`;
  `src/viewer` (deprecated, AD-15); `ui/src` components (c6-3's story).

### References

- Story + epic: `_bmad-output/planning-artifacts/epics-companion-app.md` §Epic 6 (2664-2996), Story
  6.2 (2714-2746), Story 3.4 (1714-1746), Story 5.4 (2509-2527), FR inventory (64-91), coverage map
  (737, 742).
- Architecture: `_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md`
  — AD-3 (114), AD-4 (127), AD-8 (197), AD-16 (329, incl. the set-active ownership paragraph),
  Consistency Conventions (358-360); EPIC-SPLIT.md E5 (64); reviews/review-adversarial-seam.md S-5.
- PRD: `_bmad-output/planning-artifacts/prds/prd-Artificial-Planeswalker-2026-07-22/prd.md` — FR-07
  (138), FR-12 (146), FR-14 (103), CM-1 (189), CM-3 (193).
- Prior art: `c6-1-…md` (the whole file, esp. Rulings + Landmine 1), `c3-4-…md` (the endpoint's
  firsts), deferred-work.md:9-24 + :2792; `src/companion/client.py`,
  `src/companion/app/routes/active_deck.py`, `src/companion/app/ws.py:424`,
  `src/mcp_server/server.py:248`, `src/mcp_server/tools/view_deck.py`,
  `src/data/repositories/deck.py:119`.

## Open questions for Brad (recommendations first — rule before code)

1. **The client count is not on the wire — how does AC 2 get it?** The shipped PUT answers `200
   ActiveDeck {"deck_id"}`; AD-8's count is defined by the *events* receipt, and set-active never
   touches `/agent/events`. **Recommend: extend the wire.** `broadcast_active_deck_changed` already
   returns the delivered count (`ws.py:424`) and the route discards it; add an
   `ActiveDeckSetReceipt {deck_id, clients: int >= 0}` (`extra="forbid"`) as the PUT's response
   model, GET untouched, committed OpenAPI/types artifacts regenerated through the existing gates.
   This makes `displayed` vs `no_clients_connected` real for the control verb — the agent can say
   "switched, but no tab is watching — open the printed URL" — and satisfies AC 2 literally.
   *Alternative:* keep the wire frozen, return `clients=None`, document `no_clients_connected` as
   unreachable for this verb — a recorded AC-2 deviation.
2. **Tool result shape.** A pydantic result in the repo convention: `status:
   Literal["displayed", "no_clients_connected", "deck_not_found", "app_not_running",
   "payload_rejected", "backend_error", "database_not_initialized", "error"]`, `deck_id`,
   `deck_name` (from the existence read — lets the agent confirm by name), `clients: int | None`,
   `message: str`. The last two statuses are the repo-wide DB-layer convention every tool carries —
   layered above AD-8's set exactly as `deck_not_found` is, and documented in the tool docstring.
   **Recommend yes.**
3. **Homes and signatures.** Tool helper + result in new `src/mcp_server/tools/companion.py` (the
   module c1-8's plan note reserved; c6-4 joins it later, unmentioned now per R2); client verb is
   public `async def set_active_deck(request: ActiveDeckRequest, *, timeout=None) -> PushOutcome` in
   `client.py` beside `push_event`, accepting the concrete instance (no re-validation, mirroring the
   envelope ruling), plus `ACTIVE_DECK_PATH`; reuse `_PUSH_TOTAL_SECONDS`; private sibling
   attempt/outcome helpers rather than widening the push pair. **Recommend yes.**
4. **Tool-test seam.** Tool tests stub the *client verb* (monkeypatch at the `companion.py` module
   boundary) against a real seeded session; all wire behaviour stays in `test_client.py`'s
   real-socket harness; no extraction of the stub harness into a shared `_stubs.py` (the c1-8
   third-consumer trigger is not met — the tool tests don't need sockets). **Recommend yes.**
5. **Opportunistic close of the ledgered 401-vs-403 gap** (`deferred-work.md`, c6-1 block): one
   parametrized 401 row in each unexpected-status matrix (push + new verb) pins 401 →
   `backend_error` with no retry — two cheap rows, entry closed. **Recommend yes.**

## Dev Agent Record

### Agent Model Used

Claude Opus 5 (`claude-opus-5`), via `/bmad-dev-story`.

### Debug Log References

**Baseline (Task 0).** `uv run pytest -m "not integration"` → **2,810 passed / 1 skipped / 55
deselected** on `feat/companion-c6` @ `38d5b3f`. Exactly the story's stated baseline. Story branch
`feat/companion-c6-2-set-active-deck` cut from it.

**Grep-own-key.** Five live `c6-2` hits, all matching the dispositions table: `state.py:12`,
`test_routes_active_deck.py:721/723`, `deferred-work.md:10-11`, `deferred-work.md:2798`. No
surprises.

**Planted red (Task 4).** Plant: one `await _client_set_active_deck(...)` inserted **before** the
`deck_not_found` return in `tools/companion.py` — the AC-3 bypass, i.e. a tool that tells the
companion to display a deck that does not exist and *then* reports it missing.
`uv run python -m scripts.probe_harness --expect-red '…::test_a_missing_deck_is_deck_not_found_and_the_client_is_never_called'`
→ **2,871 collected, 2 failed**, both in `TestAMissingDeckNeverReachesTheCompanion`: the named
guard and `test_it_is_not_passing_because_every_deck_looks_missing` (its non-vacuity pair, which
counts calls across a missing *and* a found deck). Confined to the path, as c6-1's record asked for.
Reverted.

- **What the guard compares:** the recorded argument list of the stubbed client verb — `stub.calls
  == []`. It sees *that the companion was contacted at all*, and (via the paired test) *which* deck
  reached it.
- **What it cannot see:** anything about the real socket. The stub is not the leaf, so a bypass that
  called the leaf under a different name, or reached `httpx` directly, would leave `stub.calls`
  empty and pass. That residual is deliberate — wire behaviour is `test_client.py`'s job — but it
  means this guard proves *this module's* discipline, not the absence of all HTTP.

**Frontend flake, recorded rather than hidden.** The first `npm test -- --run` after regenerating
`types.d.ts` reported **1 failed / 1,867 passed** in the eslint-fixture test (`lintBothFixtures`),
on a cold run whose own setup phase took 102.93 s (vs ~10 s warm). Two consecutive re-runs were
**1,868 passed / 69 files**, identical to the baseline. Read as a cold-start timeout in a test that
shells out to eslint, not a regression: nothing under `ui/src` changed except the generated
`types.d.ts`, and `schema.ts` — the single reader — is untouched because the SPA never calls the
token-gated `PUT` (AD-5).

**Gates.** `ruff check .` clean, `ruff format --check .` clean (325 files), `mypy src/` strict clean
(94 files). Python **2,870 passed / 1 skipped / 55 deselected** (+60 over baseline). Frontend
**1,868 / 69 files**, unchanged. `plugin/` rebuilt after the last edit; all 7 touched mirrors
sha256-identical to source.

**Dev Notes self-check:** 16.8 KB — inside the 10–20 KB band.

### Completion Notes List

**All five pre-code questions RULED AS RECOMMENDED by Brad (2026-08-09), before any code.** Q1
extend the wire; Q2/Q3/Q4 adopted as written; Q5 yes.

**What shipped, by task.**

- **Task 1 — the wire receipt.** New `ActiveDeckSetReceipt {deck_id, clients: int >= 0}`
  (`extra="forbid"`) in `contracts.py`; `PUT /api/active-deck` now captures
  `broadcast_active_deck_changed`'s already-returned `int` — one line, no second broadcast, no
  registry sample — and answers the receipt. `GET` untouched. Committed OpenAPI + `types.d.ts`
  regenerated through the shipped pipeline (`scripts.dump_openapi` → `npm run gen:types`);
  `schema.ts` unchanged.
- **Task 2 — the leaf verb.** `ACTIVE_DECK_PATH` + public `set_active_deck(request, *, timeout=None)
  -> PushOutcome` in `client.py`, reusing `_send` verbatim (`method="PUT"`) and
  `_PUSH_TOTAL_SECONDS`. Sibling private helpers `_active_deck_outcome_for` / `_active_deck_attempt`
  — `_outcome_for` and `_attempt` are untouched.
- **Task 3 — the tool.** New `src/mcp_server/tools/companion.py` (`SetActiveDeckResult` +
  `set_active_deck`), registered as `companion_set_active_deck` in `build_server()`. Stateless;
  `DeckRepository.get_deck` (the cheap read); `deck_not_found` before any HTTP.
- **Task 4 — tests.** Stub gained `do_PUT` / `put_script` / `on_put` / `.puts`; +38 client tests,
  +20 tool tests, tool-surface pin 19 → 20.
- **Task 5 — sweeps and gates.** Below.

**Three judgement calls worth a reviewer's eye.**

1. **The retry loop was factored, not mirrored** (the story left this to my call). `_once_then_retry`
   now owns the whole-call deadline, the one-retry budget and the terminal `backend_error`;
   `push_event` and `set_active_deck` both spend it. The subtle part lives in one place; the parser
   — where explicitness is the point — stays two named functions. **`push_event`'s behaviour is
   unchanged and its 67 shipped tests passed untouched**, which is the proof.
2. **`ActiveDeckSetReceipt.deck_id` is `str | None`, not `str`.** The story's sketch said `str`.
   Declaring it identically to `ActiveDeck.deck_id` makes the divergence between the two operations
   **purely additive** — one field, nothing else — which is far easier to justify than a second
   difference in nullability, and it needs no narrowing gymnastics against `slot.deck_id`'s
   `str | None`. There is still no clearing verb, so the write cannot answer `null` today; the
   docstring says exactly that.
3. **`extra="forbid"` on the receipt, unlike `EventIngestReceipt`.** Deliberate asymmetry, and the
   looser sibling is itself an open `deferred-work.md` entry. Both models are parsed by a leaf
   talking to a backend in the *same installed package* — there is no version skew to be forward
   compatible with — so an unexpected field means the two halves disagree, and `backend_error` is
   the honest report. (`HealthResponse` stays open for the opposite reason: it is read *before*
   identity is proven, from something that may not be this application.) An inline comment says so.

**Prose ripple Task 1 caused that the story did not list.** Extending the wire falsified c3-4's
shipped "one shape serves the read, the write and the change notification" claim in three places:
`routes/active_deck.py`'s module docstring and `PUT` docstring, and `ActiveDeck`'s class docstring.
All three rewritten to present tense, with the *reason* for the divergence recorded rather than the
story key. `test_both_operations_answer_the_same_shape` became
`test_the_two_operations_answer_two_shapes_and_why`. Two shipped guards caught what I would have
missed: `test_openapi_contract.py` refused `:class:` Sphinx markup in wire-visible prose (fixed at
the docstring, never the generated file), and `test_routes_agent_events.py`'s body-cap test held a
fourth copy of the PUT response shape.

**Ripple sweep results (skills-are-a-ripple-site).** The tool-count claim was grepped as a *claim*,
not as a sentence — **5 live sites, not the 2 the story predicted** (`test_build_plugin.py` ×2,
`README.md` ×3). The R1 lesson repeating. Fixed by removing the count from the test's module
docstring entirely (it lives once, as the name set) and updating README 19 → 20 with a capability
row for the new tool. **`.claude/skills/**` and `plugin/skills/**`: no hits requiring change** — the
four MTG skills enumerate the *deckbuilding loop's* tools (they already omit `view_deck`,
`assess_deck_power`, `initialize_database`), and a companion control verb is not part of that loop.
`docs/**`: only two `view_deck` mentions, both about the `src/viewer/` build dependency.

**Ledger.** dw:10's two-need entry **CLOSED** with a `resolution:` line that also records what it
got wrong (it predicted `_outcome_for` reuse; the receipt models differ, so a sibling was required).
The 401-vs-403 entry **CLOSED** by Q5's two rows. The clear-verb entry (`:2798`) annotated **not
triggered** — c6-2 was its named candidate and did not want it; it stays open and unowned.

**Deliberately not done:** no new `integration`-marked test and no change to `test_live_backend.py`
(AD-10's exactly-one rule, c6-1 Q3 precedent); `PUSH_OUTCOMES` not widened (`deck_not_found` is
layered above the client by ruling, and `TestOutcomeVocabulary`'s set equality still pins five);
no `ui/src` component work (c6-3's story); no forward-looking cross-module prose (R2) — nothing in
`companion.py` mentions c6-4.

### File List

**New**

- `src/mcp_server/tools/companion.py`
- `tests/integration/mcp_server/test_companion_tool.py`
- `plugin/server/src/mcp_server/tools/companion.py` *(build artifact)*

**Modified — source**

- `src/companion/contracts.py` — `ActiveDeckSetReceipt`; `ActiveDeck` docstring
- `src/companion/app/routes/active_deck.py` — PUT response model + captured count; docstrings
- `src/companion/app/state.py` — forward-looking `(c6-2)` promise → present-tense pointer
- `src/companion/client.py` — `ACTIVE_DECK_PATH`, `set_active_deck`, `_once_then_retry`,
  `_active_deck_outcome_for`, `_active_deck_attempt`; `push_event` routed through the shared retry
- `src/mcp_server/server.py` — `companion_set_active_deck` registration; module docstring

**Modified — tests**

- `tests/unit/companion/test_client.py` — `do_PUT` harness; 4 new classes; 401 row on the push
- `tests/unit/companion/test_routes_active_deck.py` — PUT-shape assertions, two-shape test,
  receipt-shape test, delivered-count row
- `tests/unit/companion/test_committed_schema.py` — component set 30 → 31
- `tests/unit/companion/test_routes_agent_events.py` — body-cap test's PUT-shape assertion
- `tests/integration/test_build_plugin.py` — tool pin 19 → 20; stale "17-tool" claim removed

**Modified — committed artifacts (regenerated, not hand-written)**

- `ui/src/api/openapi.json`, `ui/src/api/types.d.ts`

**Modified — docs / records**

- `README.md` — 19 → 20 tools (×3) + companion capability row
- `_bmad-output/implementation-artifacts/deferred-work.md` — two entries closed, one annotated
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — c6-2 → `review`; header per R4

**Modified — build mirrors (`scripts/build_plugin.py`, sha256-verified)**

- `plugin/server/README.md`, `plugin/server/src/companion/app/routes/active_deck.py`,
  `plugin/server/src/companion/app/state.py`, `plugin/server/src/companion/client.py`,
  `plugin/server/src/companion/contracts.py`, `plugin/server/src/mcp_server/server.py`

## Change Log

- 2026-08-09 — Story context created (create-story). 5 open questions await Brad's pre-code ruling.
- 2026-08-09 — All 5 open questions **ruled as recommended** by Brad before code.
- 2026-08-09 — Implemented (dev-story). Tasks 0–5 complete; status → `review`. Python suite
  2,810 → **2,870** passed (+60, 1 skipped, 55 deselected, 2,871 collected); frontend 1,868 / 69
  unchanged; ruff + `mypy --strict` clean; `plugin/` rebuilt and sha256-verified. Planted red fired
  2-red-and-no-more through the full suite and was reverted. `deferred-work.md`: dw:10's two-need
  entry and the 401-vs-403 entry closed; the clear-verb entry annotated not-triggered.
