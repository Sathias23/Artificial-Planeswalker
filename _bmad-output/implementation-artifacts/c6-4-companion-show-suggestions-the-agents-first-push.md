---
epic: c6
story: c6-4
work_branch: feat/companion-c6
story_branch: feat/companion-c6-4-show-suggestions
depends_on: [c6-1, c6-2, c5-1, c5-5]
baseline_commit: cb7814c
---

# Story c6-4: `companion_show_suggestions` — the agent's first push

Status: done

<!-- Ultimate context engine analysis completed 2026-08-10 — comprehensive developer guide created.
     Sources: epics-companion-app.md Story 6.4 (lines 2776-2806) + Stories 5.1/5.5/6.1/6.2/6.6/6.9,
     ARCHITECTURE-SPINE 2026-07-25 (AD-3/6/7/8/16, Consistency Conventions, sequence diagram),
     PRD 2026-07-22 (FR-08/12/13, NG5, SC-1/SC-3, CM-1/CM-3, OQ-2 addendum ruling),
     EXPERIENCE.md/DESIGN.md (UX-DR24/28/34 — consumed-by context only), shipped code on
     feat/companion-c6 @ cb7814c (contracts.py suggestions models, client.py both verbs,
     tools/companion.py, server.py registration, agent_events route, both test homes read end to
     end), c6-1/c6-2/c6-3 story records, C5 retro, deferred-work ledger. -->

## Story

As Brad asking for card suggestions,
I want them on the glass as cards rather than as a wall of text in my terminal,
So that I can evaluate six cards by looking at them.

## The story in one paragraph

**The entire wire already exists and is tested end to end.** The `suggestions` envelope
(`SuggestionsEvent` / `SuggestionsPayload` / `SuggestionItem`) shipped at c5-1 and is one of the
six closed kinds; `POST /agent/events` accepts it, caps it (400 field / 413 byte), and relays it
without a database read (c5-5); the leaf client's `push_event` posts any `AgentEvent`, retries
once on 403, and returns the closed five-token `PushOutcome` (c6-1); `companion_set_active_deck`
established the tool pattern, registration shape, and result-compactness conventions (c6-2). What
c6-4 owes is the **thin tool layer only**: a `show_suggestions` helper + `ShowSuggestionsResult`
in `src/mcp_server/tools/companion.py`, a `@mcp.tool()` registration in `src/mcp_server/server.py`
whose docstring is the LLM-facing description (AD-8/OQ-2), tests on the established `_ClientStub`
pattern, the tool-count ripple (20 → 21), and a rebuilt `plugin/` tree. **No change to
`contracts.py`, `client.py`, or anything under `src/companion/app/`** — a diff touching those is
scope creep. Unlike c6-2 this is a *push* tool: it validates nothing against the database (AD-7:
card ids are not validated; AD-16 scopes deck-existence validation to the control tool), so it
needs **no DB session** and no `deck_not_found` / `database_not_initialized` statuses — its result
vocabulary is exactly the client's five tokens. One known expectation-setter: the shipped SPA
currently receives and **deliberately drops** the `suggestions` kind (the views are c6-5/6/7), so
a real push renders nothing yet — `displayed` is still honest because the count is WS *delivery*,
counted at the socket write, not at render.

## Acceptance Criteria

*(Verbatim from `epics-companion-app.md` Story 6.4, lines 2776-2806; annotations in italics.)*

1. **Given** the tool is defined **When** its signature and docstring are inspected **Then** it is
   `async def` and its docstring is written as the LLM-facing description, since per-tool
   docstrings are why OQ-2 rejected a generic `companion_display` (AD-8). *(Match c6-2's
   registration shape at `server.py:416-441`: use-when sentence, running-app requirement,
   statelessness note, `Args:`, and a `Returns:` paragraph enumerating every status token.)*

2. **Given** a valid payload of card ids with reasons and optional categories **When** the agent
   calls the tool **Then** the envelope is posted to `/agent/events` and the result carries
   `displayed` plus the connected-client count (FR-08, AD-8). *(The envelope is a
   `SuggestionsEvent` minted by the tool — `id` = fresh UUID4 string, `ts` = `datetime.now(UTC)`,
   payload passed through untouched — handed to the shipped `push_event`. `displayed` requires
   receipt `clients >= 1`.)*

3. **Given** a payload exceeding a cap **When** the tool posts it **Then** the backend returns 413
   `payload_too_large`, the tool returns `payload_rejected`, and the agent presents the content in
   chat as usual — nothing is lost (AD-7 as amended by the c1-4 review ruling; FR-12). *(Amended
   at the C5 retro: over-cap byte breaches are 413; field-cap breaches remain 400 per c5-5 Q7 —
   the client maps **both** to `payload_rejected`. Satisfied compositionally, per Q1's ruling:
   over-cap arguments are refused by pydantic at the tool-argument layer before any wire call
   (nothing lost — the agent still holds the content); the wire-level 400/413 →
   `payload_rejected` mapping is already pinned at the client (c6-1) and the route (c5-5), and
   this story's tool tests pin the `payload_rejected` → status passthrough via the stub. A
   field-valid suggestions payload maxes out near ~30 KB, under the 64 KB byte cap, so the live
   413 path exists for version skew, not for well-formed calls.)*

4. **Given** an empty suggestions payload **When** it is posted **Then** it is accepted and the
   view renders its deliberate empty state (AD-7). *(Tool half: an empty `items` list is legal on
   `SuggestionsPayload` and must be **posted, never short-circuited** — "I looked and found
   nothing" is expressible. The empty-state *render* is c6-6/c6-7's surface; this story proves the
   tool posts the empty envelope and reports the outcome honestly.)*

5. **Given** the tool returns **When** its result is inspected **Then** the payload is **never
   echoed back into chat** and the result stays under roughly 200 tokens (CM-1). *(Pinned the
   c6-2 way: `len(result.model_dump_json()) < 400` on **every** status branch, plus an assertion
   that planted payload strings — a reason, a card id, the title — appear nowhere in the result
   JSON.)*

6. **Given** the agent holds the pushed content regardless **When** the app is closed **Then** the
   agent presents the suggestions in chat as it always would — the companion adds a visual channel
   and never replaces the conversational one (NG5, SC-3). *(Tool half: `app_not_running` token +
   a one-line message; zero requests leave the machine when no discovery file or no live instance.
   The chat presentation itself is agent behaviour — the docstring must not tell the agent to skip
   or condition its normal chat answer on the tool's outcome.)*

## Tasks / Subtasks

- [x] **Task 0 — Verify the baseline and grep your own key** (AC: all)
  - [x] Confirm branch `feat/companion-c6` at/after `cb7814c`; cut `feat/companion-c6-4-show-suggestions` from it.
  - [x] `uv run pytest -m "not integration"` → expect **2,874 passed / 1 skipped / 55 deselected**
        (pytest prints `2875/2930 tests collected (55 deselected)` — 2,875 is the *selected*
        count; the c6-3 merge baseline). This story grows the Python suite; the frontend suite
        (**1,871 / 69 files**) must not move.
  - [x] `grep -rn "c6-4" src/ ui/src/ tests/ scripts/ _bmad-output/implementation-artifacts/deferred-work.md`
        — reconcile every hit against a dispositions table in the Dev Agent Record. Expected:
        zero code hits; ledger records are records. Note: the `agentEventOf` kind-only-validation
        ledger entry (~`deferred-work.md:124`) triggers on the story that **reads payload fields
        in the UI** — that is c6-7, not this story; annotate NOT TRIGGERED with that reasoning.
  - [x] Read end to end before writing anything: `src/mcp_server/tools/companion.py` (196 lines —
        the module you extend), `src/mcp_server/server.py:416-441` (registration shape),
        `src/companion/client.py` push half (`push_event`, `_attempt`, `_outcome_for`,
        `_once_then_retry`, `PushOutcome`, L123-529), `src/companion/contracts.py` suggestions
        models (`SuggestionItem` L613, `SuggestionsPayload` L826, `SuggestionsEvent` L1002,
        `AgentEvent` union L1278), `tests/integration/mcp_server/test_companion_tool.py` (fixture
        + stub pattern), `tests/unit/companion/test_client.py::TestOutcomeVocabulary` (the
        five-token pin you must not widen).
- [x] **Task 1 — `ShowSuggestionsResult` + `show_suggestions` helper** (AC: 2, 3, 5, 6)
  - [x] In `src/mcp_server/tools/companion.py`: import the leaf verb at the module boundary as
        `_client_push_event` (mirroring `_client_set_active_deck` — the monkeypatch seam), plus
        `SuggestionsEvent` / `SuggestionsPayload` from `src.companion.contracts`.
  - [x] `ShowSuggestionsResult(BaseModel)`: `status:` closed `Literal` of **exactly the client's
        five tokens** (`displayed | app_not_running | no_clients_connected | payload_rejected |
        backend_error` — no DB statuses, per Q2's ruling), `clients: int | None`,
        `items_pushed: int`, `message: str` (per Q3's ruling). Counts are not echoes; payload
        strings never appear.
  - [x] `async def show_suggestions(*, payload: SuggestionsPayload) -> ShowSuggestionsResult`:
        mint `SuggestionsEvent(kind="suggestions", id=str(uuid4()), ts=datetime.now(UTC),
        payload=payload)` (per Q4's ruling — no default-title injection; `DEFAULT_TITLE_BY_KIND`
        is the UI's fallback, not the tool's), `await _client_push_event(event)`, map
        `PushOutcome.outcome` → `status` **1:1**, pass `clients` through, set `items_pushed =
        len(payload.items)`. No try/except beyond what exists: `push_event` never raises
        (`MemoryError` carve-out propagates by design); there is no DB call to guard.
  - [x] Messages: one short sentence per token pointing at the recovery move (`app_not_running` →
        launch the companion / content is in chat regardless; `no_clients_connected` → pushed but
        no tab is watching, open the printed URL; `payload_rejected` → the backend refused the
        payload, content is in chat; `backend_error` → companion misbehaved, content is in chat).
        `displayed` interpolates only the two counts. Nothing user- or payload-sourced is
        interpolated anywhere — if that ever changes, `_truncate_for_echo()` at `_ECHO_LIMIT` 48
        is the law (the c6-2 Greptile lesson: apply it to every branch, not the cited one).
- [x] **Task 2 — Registration** (AC: 1)
  - [x] In `build_server()` (`src/mcp_server/server.py`), beside `companion_set_active_deck`:
        `@mcp.tool()` `async def companion_show_suggestions(payload: SuggestionsPayload) ->
        ShowSuggestionsResult` (per Q1's ruling — the contract model IS the argument; FastMCP
        validates it, so the tool body never sees an over-cap payload). **Do not open
        `session_factory()`** — this tool touches no database (AD-7/AD-16).
  - [x] Docstring = the LLM-facing description (Google style, matching c6-2's): when to use it
        (the user asked for card suggestions and the companion app may be open), that the payload
        wants Scryfall printing UUIDs from this server's own lookup/search tools (FR-13 — names
        don't render), that empty items is a legitimate "found nothing" push, that the tool is
        stateless and never replaces the normal chat answer (NG5), `Args:` documenting
        `payload.items[].{card_id, reason, category?, confidence?}` + optional `title`, and
        `Returns:` enumerating all five status tokens with one clause each. **R2**: no
        forward-looking prose about c6-5/6/7 views — the glass side is "the companion renders it",
        full stop.
- [x] **Task 3 — Tool tests** (AC: 2-6) — extend `tests/integration/mcp_server/test_companion_tool.py`
      (runs under `-m "not integration"`; directory ≠ marker). Stub `companion._client_push_event`
      by monkeypatch at the module boundary, per the shipped `_ClientStub` pattern (per Q5's
      ruling); the stub records the `AgentEvent` instances it is handed.
  - [x] **Delegation**: call with a two-item payload; assert the stub received exactly one
        `SuggestionsEvent` whose `kind == "suggestions"`, whose `payload` is the argument object's
        content unchanged (items order preserved — payload order is render order, nothing sorts),
        whose `ts` is timezone-aware (a naive `ts` would 400 on the live wire and be invisible to
        this stub — pin awareness here), and whose `id` is non-blank; two calls yield two distinct
        `id`s.
  - [x] **1:1 status mapping**: for each of the five `PushOutcome` tokens, script the stub and
        assert result `status` equals it and `clients` passes through untouched (`None` and `0`
        distinguished — `0` is a wire success; the tool must not treat it as failure or retry).
  - [x] **Empty payload is posted, not short-circuited** (AC 4): call with `items=[]`; assert the
        stub WAS called (non-vacuity pair: count stub calls across the empty and two-item cases),
        the envelope's payload has zero items, and `items_pushed == 0` with a `displayed` script.
  - [x] **Compactness + no echo** (AC 5): on **every** status branch,
        `len(result.model_dump_json()) < 400`; plant sentinel strings in the payload (a
        distinctive reason, card id, and title) and assert none appear in the result JSON.
  - [x] **App closed** (AC 6): stub scripted `app_not_running` → status + message mention the
        companion isn't running; no other branch's message conditions the agent's chat behaviour.
  - [x] Update the exact-name-set pin `tests/integration/test_build_plugin.py::test_server_registers_expected_tools`
        **20 → 21** (red until updated, by design).
- [x] **Task 4 — Ripple sweep: grep the claim, not the sentence** (AC: 1)
  - [x] Tool-count claims: grep for `20` tool-count assertions in `README.md` (three known sites
        from c6-2, may have grown) and any docs; c6-2's sweep found **5 live sites where 2 were
        predicted** — enumerate ALL hits before editing, record the table.
  - [x] Add the tool's capability row to `README.md` beside `companion_set_active_deck`'s.
  - [x] Skills sweep: grep `.claude/skills/**` and `plugin/skills/**` for tool enumerations. As of
        story creation neither mentions any companion tool — but a *suggestions* tool sits closer
        to the deckbuilding-loop vocabulary the four MTG skills DO enumerate; verify none of them
        claims a closed tool list that this tool falsifies, and record the grep in the Dev Agent
        Record.
  - [x] No wire change → **no** `npm run gen:api`, no `ui/src/api/*` churn, no frontend edits. If
        the diff wants to touch those, stop and re-read the story.
- [x] **Task 5 — Planted red** (AC: 2, 4)
  - [x] Plant on the guard of consequence: make `show_suggestions` mint the envelope with
        `SuggestionsPayload()` (empty) regardless of the argument — the payload-passthrough
        severed. Expected reds: the delegation test and the empty-vs-nonempty non-vacuity pair,
        confined to this story's block (2-3 reds; more means the tests overlap, fewer means
        they're vacuous).
  - [x] Run via `uv run python -m scripts.probe_harness --expect-red '<node-id>'` (full suite,
        validates the collected count before scoring). Paste the red list into the Dev Agent
        Record, revert, and record what the guard compares (the envelope handed to the leaf) and
        what it cannot see (the real wire — AD-10's one real-socket test owns that, untouched).
- [x] **Task 6 — Gates, plugin rebuild, record** (AC: all)
  - [x] `uv run ruff check . --fix && uv run ruff format .`; `uv run mypy src/` (strict) clean.
  - [x] Full `uv run pytest -m "not integration"` green; record the new totals (baseline 2,874 +
        this story's additions; collected count validated before scoring). Frontend untouched at
        1,871 — do not run it unless a gate demands it; if run, uppercase drive letter.
  - [x] Rebuild `plugin/` via `uv run python scripts/build_plugin.py` **after the last src edit**
        (review patches count as edits — rebuild again if any land); sha256-verify the mirrors
        (`plugin/server/src/mcp_server/tools/companion.py`, `plugin/server/src/mcp_server/server.py`).
  - [x] Dev Notes size self-check (band 10-20 KB), completion notes, File List, suite arithmetic.
  - [x] Set story status to `review` and **STOP** — Brad runs the three-layer review and raises
        the PR (story PR targets umbrella `feat/companion-c6`; Greptile reviews story PRs).

### Review Findings

*(Three-layer adversarial review — Blind Hunter, Edge Case Hunter, Acceptance Auditor — 2026-08-10.)*

- [x] [Review][Patch] "Displayed" docstring/message overclaims — says "on screen now" though the shipped SPA deliberately drops the `suggestions` kind until c6-5/6/7 land, so nothing actually renders from a push made today; an agent echoing that line would tell Brad something visibly false. [src/mcp_server/server.py:464] — fixed: reworded to "delivered to at least one connected browser tab now ... whether that tab currently renders suggestions on screen is its own concern, not this tool's"
- [x] [Review][Patch] `items_pushed` docstring internally contradicts itself — the `Returns:` paragraph says it "reports how many suggestions were sent on every status," but the same docstring's `app_not_running` clause says "nothing is sent," and `ShowSuggestionsResult.items_pushed`'s own attribute docstring says it describes what was "attempted," not what "arrived." [src/mcp_server/server.py:471; src/mcp_server/tools/companion.py:306-308] — fixed: reworded to "how many suggestions the call attempted to push, on every status — including the ones where nothing actually reached the wire"
- [x] [Review][Patch] `payload_rejected`/`backend_error` messages in `_PUSH_MESSAGES` omit Task 1's explicit "content is in chat regardless" reassurance clause — only `no_clients_connected`'s message matches the task's specified wording; `app_not_running`'s reassurance lives only in the tool docstring, not the per-call message. [src/mcp_server/tools/companion.py:332-335] — fixed: all three non-happy-path messages (`app_not_running`, `payload_rejected`, `backend_error`) now end with "the content is in chat regardless"
- [x] [Review][Patch] `category`'s 80-char cap is undocumented in the tool's `Args:` section, unlike `reason` (200 chars) and `title` (80 chars), which are both spelled out for the agent. [src/mcp_server/server.py:456-461] — fixed: added "up to 80 characters" to the `category` clause
- [x] [Review][Defer] `outcome.clients` is interpolated into the `displayed` message/pluralization with no `None`-guard (`PushOutcome.clients: int | None` doesn't statically forbid `displayed` + `clients=None`); purely theoretical today since `_outcome_for` only ever emits `displayed` paired with `receipt.clients >= 1`, and this diff faithfully mirrors the identical unguarded pattern already shipped in `set_active_deck` (c6-2). [src/mcp_server/tools/companion.py:313,320] — deferred, pre-existing
- [x] [Review][Defer] No test drives the payload through the real FastMCP `call_tool` invocation path — every delegation test calls `show_suggestions()` as a bare coroutine. The story's central claim (the repo's first BaseModel-typed tool argument actually gets coerced and cap-enforced at the FastMCP boundary, not just published in the schema) is verified only by schema-shape inspection and citation to `mcp`'s library source, never by an executing end-to-end call. [tests/integration/mcp_server/test_companion_tool.py] — deferred, pre-existing test-harness shape (no test in this file exercises the real MCP wire path; same gap in `set_active_deck`'s tests)
- [x] [Review][Defer] The "never raises" contract (asserted in three docstrings) has no test that forces `_client_push_event` to raise and confirms the exception propagates uncaught rather than being swallowed — a gap shared with `set_active_deck`, not unique to this diff. [src/mcp_server/tools/companion.py:292-295] — deferred, pre-existing
- [x] [Review][Defer] The docstring's claim that "nothing here sorts, dedupes or trims" is only half-tested — `test_payload_order_is_preserved_because_it_is_render_order` proves ordering, but no test drives duplicate `card_id`s to prove nothing collapses them. [tests/integration/mcp_server/test_companion_tool.py] — deferred, pre-existing test-harness shape

## Dev Notes

### The state you are consuming (all shipped — modify only where a Task says so)

- **Envelope** (`src/companion/contracts.py`): `EventKind` closed at six, `suggestions` among
  them since c5-1 — **you register no new kind**. `SuggestionItem {card_id ≤128 (shape-unvalidated),
  reason ≤200 (required, blank-refused), category? ≤80, confidence?: Literal["low","medium","high"]}`,
  `SuggestionsPayload {title? ≤80 (blank-refused), items ≤60 (empty legal)}`, `SuggestionsEvent
  {kind: Literal["suggestions"], id ≤128 non-blank opaque, ts: AwareDatetime, payload}` — all
  `extra="forbid"`. `AgentEvent` is a discriminated union with **no `.model_validate`** — build
  the concrete member, never re-validate. Card ids are Scryfall printing UUIDs, never names
  (FR-13). `category` is a badge, not a grouping; payload order is render order — nothing sorts,
  dedupes, or reorders.
- **Leaf client** (`src/companion/client.py`): `push_event(event, *, timeout=None) -> PushOutcome`
  is the one public POST path — discovery read → `GET /health` → `instance_id` match → token only
  then (AD-4, re-proven on every attempt); 403 → re-read discovery, retry exactly once; whole call
  capped by `asyncio.timeout(_PUSH_TOTAL_SECONDS = 10.0)`; at most two POSTs ever; never raises
  (except the `event.model_dump_json()` serialization carve-out and `MemoryError`, both by
  design). `trust_env=False` everywhere. **The tool needs zero client changes.**
- **Wire → token mapping** (client-side, pinned by ~67 tests — cite, don't re-test):

  | Wire condition | `PushOutcome.outcome` |
  |---|---|
  | no discovery file / dead port / `instance_id` mismatch | `app_not_running` (zero requests sent) |
  | `200`, receipt `clients >= 1` | `displayed` |
  | `200`, receipt `clients == 0` | `no_clients_connected` — a wire **success**, never retried |
  | `400` (field caps) or `413` (64 KB byte cap) | `payload_rejected` |
  | first `403` | re-read discovery, retry once; second `403` → `backend_error` |
  | `401` / 5xx / malformed 200 body / transport / timeout | `backend_error` (401 unretried, pinned) |

  Mapping is on **status codes only, never `reason` strings**. `clients=None` ("backend never
  told us") is distinguishable from `0` ("nobody watching").
- **Ingest route** (`src/companion/app/routes/agent_events.py`): validates the union natively,
  broadcasts, answers `EventIngestReceipt {clients: delivered count}`. No database anywhere on
  the push path (protects the 250 ms budget — NFR-05). Untouched by this story.
- **c6-2 tool precedent** (`src/mcp_server/tools/companion.py` + `server.py:416-441`): result
  model with closed `status` Literal + `message`; module-boundary client alias for the test seam;
  `_ECHO_LIMIT = 48` / `_truncate_for_echo()`; the 400-char compactness convention (verbatim
  rationale at `test_companion_tool.py:308-319`). **Contrast deliberately**: c6-2 is a *control*
  tool (DB session, `deck_not_found`, `database_not_initialized`, `error`, session closed before
  wire I/O); c6-4 is a *push* tool — no session, no DB statuses, exactly the five client tokens
  (AD-8's closed set verbatim).

### Ruled — settled, do not re-derive

- **AD-8**: companion tools are `async def`, never raise, return one token from the closed five
  plus the client count, no payload echo, < ~200 tokens, retry-once on auth rejection (the retry
  lives in the client — the tool adds none).
- **AD-7**: caps enforced by pydantic; over-cap **rejected, never truncated** (the tool never
  trims a payload to fit); empty payloads accepted; card ids not validated at ingest **or in the
  tool**; no DB read on the push path.
- **AD-16 boundary**: deck-existence validation belongs to the control tool alone. This tool has
  no deck, validates nothing against the corpus, and gains no `deck_not_found`.
- **AD-3**: `src/mcp_server/**` imports only `src.companion.{contracts,discovery,client}` — never
  `src.companion.app.*`. The import-boundary test guards it; keep it green.
- **OQ-2** (PRD addendum): separate per-kind tools BECAUSE per-tool docstrings give sharper
  affordances and "payload validation stays a plain model per tool" — the docstring is a
  deliverable, not decoration, and the contract model as the argument is the ruled shape.
- **CM-3 / D5**: stateless — nothing cached between calls; pass everything per call.
- **413 vs 400** (C5 retro amendment on this story's AC-3): byte cap answers 413 pre-parse
  (`BodyCapMiddleware`), field caps answer 400; both → `payload_rejected`; the tool cannot and
  need not distinguish them.
- **`status` vs `outcome`** (dw:3151): the client's field is `outcome`; the tool's is `status`.
  Do not rename either.
- **250 ms budget** (NFR-05/SC-1): owned by c6-9's measurement, not this story. The tool's whole
  obligation is already structural — build the envelope, POST, nothing else (no DB, no sleep, no
  image work).

### Landmines specific to this story

1. **The SPA drops your push today.** `ui/src/state/socket.ts:406-429` receives the four view
   kinds and deliberately discards them until c6-5/6/7. A manual push renders nothing — that is
   correct, not a bug; `displayed` counts WS delivery at the socket write. Don't chase pixels,
   and don't add UI code.
2. **`clients == 0` is a success the backend will not re-send.** Never retry, never re-post — a
   duplicate push at the first tab to open would be the bug. The message says "open the printed
   URL", nothing more.
3. **Don't widen either vocabulary.** `TestOutcomeVocabulary` pins the client's five by set
   equality; the tool's `status` Literal is those same five — adding a sixth tool status (or
   reusing c6-2's DB statuses) breaks the AD-8 contract this story exists to honour.
4. **Naive `ts` is invisible in stubbed tests** but 400s (→ `payload_rejected`) on the live wire.
   The delegation test MUST assert `event.ts.tzinfo is not None`. Use `datetime.now(UTC)` —
   never `utcnow()`.
5. **No `except Exception`, no defensive try.** `push_event` never raises by contract; envelope
   construction from a FastMCP-validated payload cannot fail; `MemoryError` propagates by design
   (c6-1 ruling). A blanket catch would hide real bugs — crash loudly.
6. **R2 standing rule**: no forward-looking cross-module prose ("c6-7 will render this…") in any
   docstring or comment. Future needs get a `dw:` ledger line.
7. **The ripple lesson, twice learned** (R1, then c6-2): grep the CLAIM (`20` as a tool count),
   not the sentence you happen to know about. c6-2 predicted 2 sites and found 5. Build the
   dispositions table before editing.
8. **`plugin/` is a build artifact** — rebuild AFTER the last edit including review patches;
   sha256-verify. The most-repeated failure mode of the companion epics.
9. **Directory ≠ marker**: `test_companion_tool.py` lives under `tests/integration/` but runs in
   the `-m "not integration"` set. Don't add an `integration` marker; don't touch
   `tests/integration/companion/test_live_backend.py` (AD-10: exactly one real-socket test,
   hand-rolled, not yours).
10. **Echo hygiene is preventive here.** The result interpolates only counts, so there is nothing
    to truncate — keep it that way. The no-echo test (planted sentinels absent from result JSON)
    is the guard that stays behind after you leave.
11. **`.strip()` deferred finding** (c6-2 review): open across the tool suite, deliberately not
    fixed. This tool takes no free-string id, so it's N/A — but don't introduce a new unstripped
    echo path either.
12. **Frontend suite must not move** (1,871 / 69). A tests-only Python diff plus plugin rebuild
    is the expected shape; `ui/` appears in the File List only if something is genuinely wrong.

### Testing requirements

- Extend `tests/integration/mcp_server/test_companion_tool.py`: real seeded session fixture
  exists but this tool doesn't need it — the stub seam is `companion._client_push_event`
  (monkeypatch at the tool module's import boundary, NOT on `src.companion.client` — the alias
  exists precisely so tests patch one name). No shared `_stubs.py` (third-consumer trigger still
  unmet — c6-2 Q4 ruling; this is consumer two).
- Assertion discipline (c5-8 F5): pair every behavioural assert with a non-vacuity guard — count
  stub calls across empty AND non-empty cases; assert the result-token mapping for ALL five, not
  a sample; carry a *why* message on count asserts.
- The 400-char convention verbatim rationale lives at `test_companion_tool.py:308-319` — reuse
  its shape for the new result model on every branch.
- Suite arithmetic: Python baseline **2,874 passed / 1 skipped / 55 deselected (2,875 collected)**;
  this story must land strictly larger with the tool-count pin updated 20 → 21. Known cold-run
  flake (`ui/tests/lint-gates.test.ts` ~100-125 s setup) is documented — record, don't hide, and
  it shouldn't appear since the frontend isn't run.
- Planted red per Task 5; R5 (vitest probe-harness half) remains open and irrelevant here
  (Python-only diff).

### Previous-story intelligence (c6-1/c6-2/c6-3, all merged)

- c6-1 (PR #63): `push_event`'s 67 tests pin the wire behaviour — the tool layer cites, never
  re-tests, the retry/identity/timeout machinery. The "never raises… ever" overclaim was already
  narrowed once in review; don't reintroduce it in the new docstring (serialization carve-out).
- c6-2 (PR #64): the Greptile lesson — its compactness patch fixed one branch of four; the
  post-merge fix (`c974e28`) routed all branches through one helper. When a review finding cites
  one line, grep for the whole pattern. Also: session-held-across-HTTP was a review patch there;
  this story avoids the class entirely by having no session.
- c6-3 (PR #65): tests-only story; its ledger annotation explicitly parks payload-field
  validation on the story that reads the fields — the UI stories, not this one.

### Project structure notes

- Files touched: `src/mcp_server/tools/companion.py` (extend), `src/mcp_server/server.py`
  (register), `tests/integration/mcp_server/test_companion_tool.py` (extend),
  `tests/integration/test_build_plugin.py` (pin 20→21), `README.md` (count + capability row),
  `plugin/server/src/**` (rebuilt artifact). Nothing else.
- Naming: tool `companion_show_suggestions` (Consistency Conventions row pins the
  `companion_show_{suggestions,swaps,tier_list,groups}` family); helper `show_suggestions`;
  result `ShowSuggestionsResult`; statuses snake_case closed tokens carrying no counts.
- Epic 9 will reuse this story's exact shape for `swaps` ("no change to contracts.py" is that
  epic's AC too) — you are building the template; keep it clean.

### References

- Story + ACs: `_bmad-output/planning-artifacts/epics-companion-app.md:2776-2806`; epic preamble
  `:2664-2669`; FR-08 `:68-70`; FR-12 `:83-87`; NFR-05 `:157-160`; AD-7 `:230-240`; AD-8
  `:241-245`; AD-16 `:257-267`.
- Spine: `_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md`
  (AD-3/6/7/8/16, Consistency Conventions, sequence diagram lines 417-436 — this tool end to end).
- PRD: `_bmad-output/planning-artifacts/prds/prd-Artificial-Planeswalker-2026-07-22/prd.md`
  (CM-1 :189-190, NG5 :72-74, SC-1 :175-177, SC-3 :179); `addendum.md:138-140` (OQ-2 ruling).
- Code: `src/companion/contracts.py` (:551 EventKind, :613 SuggestionItem, :826
  SuggestionsPayload, :1002 SuggestionsEvent, :1278 AgentEvent, :1311 DEFAULT_TITLE_BY_KIND);
  `src/companion/client.py` (:123 tokens, :173 PushOutcome, :385 `_outcome_for`, :454
  `_once_then_retry`, :495 `push_event`); `src/mcp_server/tools/companion.py` (:37 `_ECHO_LIMIT`,
  :54 `_truncate_for_echo`, :59 result precedent, :123 helper precedent);
  `src/mcp_server/server.py:416-441`; `src/companion/app/routes/agent_events.py`;
  `src/companion/app/body_cap.py`.
- Tests: `tests/integration/mcp_server/test_companion_tool.py` (:308-319 the 400-char rationale);
  `tests/unit/companion/test_client.py` (TestOutcomeVocabulary, push classes);
  `tests/unit/companion/test_import_boundary.py`; `tests/integration/test_build_plugin.py`.
- UX (consumed-by context only — no UI work here): UX-DR24 suggestion row, UX-DR28 nav pills,
  UX-DR34 push arrival (`epics-companion-app.md:460-491`).

## Open questions for Brad (recommendations first — rule before code)

**Q1 — Tool argument shape: the contract model, loose input, or force-post over-cap?**
*Recommend A: `payload: SuggestionsPayload` as the tool's one argument.* FR-08's literal
signature is `companion_show_suggestions(payload)`, and the OQ-2 addendum says "payload
validation stays a plain model per tool" — the contract model as the argument is the ruled
shape, and FastMCP publishes its full JSON schema (items, caps, per-field docs) to the agent as
the affordance OQ-2 exists for. This would be the repo's **first BaseModel-typed tool argument**
(all 20 existing `@mcp.tool()` signatures take primitives/lists/Literals) — verified supported
by the installed `mcp==1.28.0`: `mcp/server/fastmcp/utilities/func_metadata.py:382-383` handles
BaseModel parameters directly, publishes `model_json_schema`, and `pre_parse_json` accepts
clients that send the model as a JSON string. Do not balk mid-implementation and fall back to a
`dict` workaround. Consequence to rule on explicitly: an over-cap argument (61 items, a 300-char
reason) is refused by pydantic at the **argument layer** — the refusal surfaces as an MCP
protocol-level tool error carrying pydantic's validation text, NOT a `ShowSuggestionsResult`
(so it is outside the five-token vocabulary and outside AC-5's result-JSON no-echo guard — by
design, not a breach). The tool body never runs and no wire call happens, so AC-3's Given ("the
tool posts it") is satisfied
compositionally rather than literally: argument-layer refusal for malformed calls (nothing lost
— the agent still holds the content and the validation message names the cap), and the shipped
client/route tests own the live 400/413 → `payload_rejected` paths (reachable via version skew;
a field-valid suggestions payload can't exceed ~30 KB, under the 64 KB cap). Alternative B:
loose `dict` argument + tool-side `try/except ValidationError` → `payload_rejected` without
posting — keeps every breach inside the closed token set but throws away the typed schema
affordance and re-implements validation the framework does for free. Alternative C: post the
over-cap body for real via `model_construct` to make the backend 413 — matches the AC text
literally and is rejected as machinery built solely to fail.

**Q2 — Result vocabulary: exactly the client's five tokens, no DB statuses?**
*Recommend yes.* This is a push tool: AD-7 says card ids are not validated, AD-16 scopes
deck-existence to the control tool, so there is no `deck_not_found`, no session, and therefore
no `database_not_initialized` / `error` either — those exist in c6-2 only because it reads the
deck table. The result's closed set is AD-8's five, verbatim, and the registration wrapper does
not open `session_factory()`. (If ruled the other way — e.g. "every companion tool carries
`error` for symmetry" — the mapping tests change shape; rule before code.)

**Q3 — Result carries `items_pushed: int`?**
*Recommend yes.* `{status, clients, items_pushed, message}` — counts are not payload echoes
(precedent: `clients` itself), and "Pushed 6 suggestions to the glass (1 client watching)" lets
the agent confirm scope without any payload string appearing. CM-1 compactness is unaffected
(two small ints). Alternative: omit it and keep the result to c6-2's exact field shape minus the
deck fields.

**Q4 — Envelope minting: `id=str(uuid4())`, `ts=datetime.now(UTC)`, no title injection?**
*Recommend yes.* `id` is opaque identity/dedupe (never ordering — AD-6), so a fresh UUID4 per
call; `ts` is the ordering key and must be timezone-aware (naive is refused at the wire); the
tool does NOT inject `DEFAULT_TITLE_BY_KIND["suggestions"]` when `title` is absent — that
fallback is the view's job, and a tool-injected title would make "agent-authored" false.

**Q5 — Test seam: module-boundary alias `_client_push_event`, no shared stub module?**
*Recommend yes.* Mirror c6-2 exactly: `from src.companion.client import push_event as
_client_push_event` in `tools/companion.py`; tests monkeypatch `companion._client_push_event`.
This is stub consumer two — the c6-2 Q4 ruling set the shared-`_stubs.py` trigger at a third
consumer, which is Epic 9's swaps tool, not this story.

## Dev Agent Record

### Agent Model Used

claude-opus-5 (Claude Code, `bmad-dev-story` workflow), 2026-08-10.

### Rulings taken before code (Brad, 2026-08-10)

All five open questions ruled **as recommended**, in one pass, before any file was edited:

| Q | Ruling | What it fixed in the code |
|---|--------|---------------------------|
| Q1 | **A** — `payload: SuggestionsPayload` is the tool's one argument | `server.py` registers a BaseModel-typed parameter (the repo's first); FastMCP publishes the model's JSON schema as the affordance, and an over-cap call is refused at the argument layer, outside the five-token vocabulary by design |
| Q2 | Yes — result vocabulary is the client's five tokens, no DB statuses | `ShowSuggestionsResult.status` is AD-8's set verbatim; the registration opens **no** `session_factory()` |
| Q3 | Yes — result carries `items_pushed: int` | `{status, clients, items_pushed, message}`; both numerics are facts *about* the push, never pieces of it |
| Q4 | Yes — `id=str(uuid4())`, `ts=datetime.now(UTC)`, no title injection | envelope minted in `show_suggestions`; `DEFAULT_TITLE_BY_KIND` untouched |
| Q5 | Yes — module-boundary alias `_client_push_event`, no shared `_stubs.py` | `_PushStub` lives beside `_ClientStub` in the one test file; the shared-stub trigger stays at consumer three (Epic 9) |

### Debug Log References

**Baseline (Task 0).** `uv run pytest -m "not integration"` → **2,874 passed / 1 skipped /
55 deselected in 106.38s** — exactly the count the story predicted, on `feat/companion-c6-4-show-suggestions`
cut from `cb7814c`.

**Planted red (Task 5).** Plant: `show_suggestions` minted the envelope with `SuggestionsPayload()`
regardless of its argument — payload passthrough severed, everything else intact.
`uv run python -m scripts.probe_harness --expect-red …` over the full suite:

```
full suite (-m 'not integration'): 2907 collected, 3 failed, 0 errored, exit 1
  RED  …::TestTheSuggestionsPushIsDelegated::test_one_suggestions_envelope_carries_the_payload_through_untouched
  RED  …::TestTheSuggestionsPushIsDelegated::test_payload_order_is_preserved_because_it_is_render_order
  RED  …::TestAnEmptySuggestionsPayloadIsStillPushed::test_it_is_not_passing_because_every_payload_is_pushed_empty
```

Three reds, inside the story's own block and nowhere else — the story predicted 2-3. Reverted after
scoring. **What the guard compares:** the `SuggestionsEvent` handed to the leaf — its `kind`, its
payload content and order, its `ts` awareness, its `id` uniqueness. **What it cannot see:** the real
wire. No socket is touched anywhere in this file, so a naive `ts` or a malformed body would be
invisible here; `tests/integration/companion/test_live_backend.py` owns the one real-socket test
(AD-10) and was not modified. The three tests that stayed green under the plant are the ones aimed
at the client→tool mapping rather than at the envelope, which is the correct partition.

**Non-vacuity note.** `test_it_is_not_passing_because_every_payload_is_pushed_empty` is the pairing
guard for AC 4 and it fired under the plant, which is the point: the empty-payload test alone would
pass against an implementation that posts an empty payload every time.

**Gates (Task 6).**

| Gate | Result |
|------|--------|
| `uv run ruff check .` | All checks passed (one E501 on a long test signature, fixed by `ruff format`) |
| `uv run ruff format --check .` | 326 files already formatted |
| `uv run mypy src/` (strict) | Success: no issues found in 94 source files |
| `uv run pytest -m "not integration"` | **2,907 passed / 1 skipped / 55 deselected in 115.95s** |
| `scripts/build_plugin.py` | Rebuilt after the last src edit; sha256 MATCH on `tools/companion.py` (`766F3C83E3B4`), `server.py` (`7A007C077EDE`), `README.md` (`34882BD1CA40`). No src edit followed the rebuild — the one later change was a test file, which the plugin does not ship |

**Suite arithmetic.** 2,874 → **2,907 passed**, +33 selected tests. Skips and deselections unchanged
at 1 / 55. The frontend suite was **not run and not touched** — the diff contains no `ui/` file and
no regenerated API types, which is the expected shape for a story whose wire already shipped.

**One test beyond the story's task list, and why.** Q1's whole justification is that FastMCP
publishes the payload model's JSON schema to the agent, and AC 1 ("the tool is defined … its
docstring is written as the LLM-facing description") had **no mechanical coverage anywhere** — Task
2 carried no test. Verified live first: the registered tool's `inputSchema` is 3,642 characters and
carries `$defs.SuggestionItem`, every item field, the 60-item `maxItems` and the per-field
`maxLength` caps. Pinned in
`test_build_plugin.py::test_companion_show_suggestions_publishes_its_payload_shape_to_the_agent`,
beside the tool-surface pin, because a later "simplification" to a loose `dict` argument would keep
every helper test in this story green while silently reducing the agent's view of the payload to an
opaque object. It also asserts the description mentions Scryfall ids (FR-13 — names don't render).

### Completion Notes List

**What was built.** A push tool, and only a push tool. `ShowSuggestionsResult` +
`show_suggestions()` in `src/mcp_server/tools/companion.py`, `companion_show_suggestions` registered
in `build_server()`, and tests. `contracts.py`, `client.py` and everything under
`src/companion/app/` are untouched, as are `ui/**` and the generated API types — the wire already
existed and this story consumed it.

**The shape that distinguishes it from c6-2.** No `AsyncSession`, no `session_factory()`, no
`deck_not_found` / `database_not_initialized` / `error`. The module docstring now names the
control/push split explicitly so the next reader does not have to infer it from the absence of a
session. `status` is the client's five tokens, pinned by set equality against `PUSH_OUTCOMES`
(`test_the_result_vocabulary_is_the_client_s_five_and_nothing_more`) so neither vocabulary can be
widened without the other failing.

**Echo hygiene is structural, not defensive.** Nothing user- or payload-sourced is interpolated
anywhere in the result — the `displayed` message interpolates two integers and nothing else — so
`_truncate_for_echo()` has nothing to bound on this path and is deliberately not called. The
c6-2 Greptile lesson is honoured by the **test** rather than by a helper call: sentinel strings
(card id, reason, title, and the `category` badge) are asserted absent from the result JSON on
**all five** status branches, not on the branch that happened to be reviewed. Compactness is
likewise pinned on all five, with a 60-item payload — the cap — so the bound is measured at the
worst case rather than at a convenient one.

**AC-by-AC.**

| AC | Where it is satisfied |
|----|----------------------|
| 1 | `server.py` — `async def companion_show_suggestions(payload: SuggestionsPayload)`; Google-style docstring with use-when, the Scryfall-id requirement (FR-13), the empty-push affordance, the running-app requirement, statelessness, `Args:` documenting every payload field, and `Returns:` enumerating all five tokens. No forward-looking prose (R2). Mechanised by `test_companion_show_suggestions_publishes_its_payload_shape_to_the_agent` |
| 2 | `TestTheSuggestionsPushIsDelegated` (5 tests) + the 1:1 mapping parametrization |
| 3 | Compositionally, per Q1: pydantic refuses over-cap arguments before the body runs; the wire's 400/413 → `payload_rejected` mapping is c6-1's and c5-5's, and the tool's passthrough of `payload_rejected` is pinned here on the stub |
| 4 | `TestAnEmptySuggestionsPayloadIsStillPushed` — posted, not short-circuited, with the non-vacuity pairing |
| 5 | `TestTheSuggestionsResultIsCompact` — `< 400` chars and zero sentinels, on every branch, at the 60-item cap |
| 6 | `TestTheAppBeingClosedIsReportedAndNothingMore` — `app_not_running` names the companion, `items_pushed` still reports what was attempted, and no message on any branch contains a directive (`instead` / `skip` / `no need to` / `don't`) that would condition the agent's own written answer |

**Known and correct:** a real push renders nothing today. `ui/src/state/socket.ts` deliberately
drops the `suggestions` kind until the view stories land. `displayed` remains honest because the
count is WebSocket *delivery*, counted at the socket write.

### Task 0 — `c6-4` grep dispositions

`grep -rn "c6-4"` across `src/`, `ui/src/`, `tests/`, `scripts/`, `_bmad-output/`. **Zero hits in
`tests/`, `scripts/` and `ui/src/`.** Everything found is a record or a ledger entry:

| Site | Disposition |
|------|-------------|
| `sprint-status.yaml` (×6) | Status/ledger records; this story's own key moved `ready-for-dev` → `review`. No other action |
| `c6-1` / `c6-2` / `c6-3` story records (×5) | Records of prior rulings that named this story ("no tools built here — that is c6-2/c6-4"). Records stay records |
| `c3-6` / `c3-7` / `c3-8` records + `epic-c5-retro` (×9) | The image in-flight-coalescing deferral's three re-homings. Records |
| `src/companion/app/images.py` (×4) | Existing prose naming c6-4 as the coalescing trigger. **Not edited** — R2 forbids me adding forward-looking prose, and rewriting someone else's ruling record is not this story's business |
| `deferred-work.md` — in-flight coalescing entry (~:2969) | **NOT TRIGGERED, and the home is mis-aimed by one story.** Annotated in the ledger: every re-homing describes c6-4 as "suggestion rows beside the deck grid", i.e. a *rendered* surface, but the epic split made c6-4 the push tool only — it issues zero image requests and renders no card at all. The first surface matching the trigger's own words is **c6-7**. Not re-homed unilaterally: the entry itself says a fourth move should be a deliberate close instead, so it **stays open** and the re-aim-or-close call is Brad's |
| `deferred-work.md` — `agentEventOf` kind-only validation (~:125) | **NOT TRIGGERED**, annotated as the story instructed: this story has no `ui/` diff at all, so `agentEventOf` is neither called nor changed, and the SPA still drops the `suggestions` kind unread. Trigger is c6-7 |

### Task 4 — ripple sweep dispositions (grep the claim, not the sentence)

Grepped `\d+ (MCP )?tools` repo-wide rather than the literal `20`, which is what surfaced the two
docs already stale by **five** stories:

| Site | Was | Action |
|------|-----|--------|
| `README.md:91`, `:122`, `:172` | `20 tools` (×3) | → `21` |
| `README.md:28` | companion capability row, one tool | Row extended with `companion_show_suggestions` |
| `docs/plugin-structure.md:21`, `:187` | **`16 tools`** (×2) | → `21`. **Not introduced by this story** — these were already wrong by five tools (last correct before c2-x); found only because the grep was written against the *claim*. Live present-tense prose describing the shipped plugin, so it is fixed rather than left |
| `docs/release-readiness-review.md:90`, `:92`, `:162` | `16 tools` (×3) | **Left alone, deliberately.** A dated point-in-time review record — one of those lines is itself documenting a count bug as it stood then. Editing it would falsify a record |
| `plugin/server/README.md` (×3) | `20 tools` | Regenerated by `build_plugin.py`; sha256-verified against source |
| `.claude/skills/**` + `plugin/skills/**` (8 files) | — | **No edit.** All four MTG skills carry a "The tools you call" table and a "Stay inside the frozen tool surface" line, but the table is the *loop's* vocabulary, not a claim about the server: it already omits seven shipped tools (`import_decklist`, `view_deck`, `assess_deck_power`, `compare_deck_power`, `initialize_database`, `build_search_index`, and c6-2's `companion_set_active_deck`). A push tool the deckbuilding loop does not call falsifies nothing, and adding it would be the first time a companion tool entered a skill — a decision c6-2 already declined |
| `*.json` manifests | — | No hits; nothing enumerates tool names in JSON since `.mcpb` was retired |
| `ui/**`, `npm run gen:api` | — | Not run and not needed: no wire change |

Predicted sites: 3. Live sites found: **7** (README ×4 counting the capability row, plugin-structure
×2, plus the mirrors). The lesson holds a third time.

### File List

- `src/mcp_server/tools/companion.py` — modified (module docstring; `push_event` + suggestions-model imports; `ShowSuggestionsResult`; `_PUSH_MESSAGES`; `show_suggestions`)
- `src/mcp_server/server.py` — modified (imports; `companion_show_suggestions` registration)
- `tests/integration/mcp_server/test_companion_tool.py` — modified (module docstring; sentinels + `_payload`; `_PushStub` + `push_stub` fixture; 5 new test classes)
- `tests/integration/test_build_plugin.py` — modified (exact-name pin 20 → 21; published-schema test for AC 1)
- `README.md` — modified (tool count ×3; companion capability row)
- `docs/plugin-structure.md` — modified (stale tool count ×2)
- `_bmad-output/implementation-artifacts/deferred-work.md` — modified (two NOT-TRIGGERED annotations)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — modified (story status)
- `_bmad-output/implementation-artifacts/c6-4-companion-show-suggestions-the-agents-first-push.md` — modified (this record)
- `plugin/server/**` — rebuilt artifact (`scripts/build_plugin.py`); sha256-verified for `src/mcp_server/tools/companion.py`, `src/mcp_server/server.py`, `README.md`

## Change Log

- 2026-08-10: Story created (ultimate context engine analysis; sources in header comment).
- 2026-08-10: Q1-Q5 ruled as recommended by Brad before implementation.
- 2026-08-10: Implemented Tasks 0-6. `companion_show_suggestions` shipped as the first companion
  push tool (no database session, the client's five status tokens verbatim). Planted red scored
  3/3 on the payload-passthrough guard. Ripple sweep found 7 live sites against 3 predicted,
  including two docs already stale by five tools. Status → `review`.
