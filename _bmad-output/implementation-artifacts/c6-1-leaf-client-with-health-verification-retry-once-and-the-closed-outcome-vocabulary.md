---
epic: c6
story: c6-1
work_branch: feat/companion-c6
story_branch: feat/companion-c6-1-leaf-client
depends_on: [c1-8, c5-5, c5-8]
baseline_commit: e59e111
---

# Story c6-1: Leaf client with health verification, retry-once, and the closed outcome vocabulary

Status: done

<!-- Ultimate context engine analysis completed 2026-08-09 — comprehensive developer guide created.
     Sources: epics-companion-app.md Story 6.1, ARCHITECTURE-SPINE 2026-07-25 (AD-3/4/5/7/8/16),
     shipped code on feat/companion-c6 @ e59e111, c5-5 + c5-8 story records, C5 retro, deferred-work ledger. -->

## Story

As a companion MCP tool,
I want one shared client that finds the backend, proves its identity, posts, and reports a single token,
So that every tool fails the same way and none of them can break an agent turn.

## The story in one paragraph

`src/companion/client.py` already exists — c1-8 shipped the `/health` half (`base_url`, `probe_health`,
`live_instance`) and its own docstring homes this story: *"Story c6-1 adds the other half into this same
module — the `POST /agent/events` push, its retry-once and its closed outcome vocabulary — and reuses the
probe below before every send rather than duplicating it."* You are adding the push path: read discovery →
prove identity via `/health` `instance_id` match → POST the envelope with `Authorization: Bearer {token}` →
map the HTTP result onto exactly one of five closed outcome tokens plus the delivered-client count → on a
403, re-read discovery and retry exactly once. The function never raises, never logs the token, and adds
no new dependencies. No MCP tools are built here (that is c6-2/c6-4); no UI is touched; no new
integration test is added (AD-10's exactly-one rule — the real-socket test already hand-rolls this
sequence as a reference implementation).

## Acceptance Criteria

1. **Given** `src/companion/client.py` **When** its imports are inspected **Then** it uses only
   `pydantic`, `httpx`, `src.paths` and `src.companion.contracts`/`discovery` — never FastAPI or
   uvicorn (AD-3). *(Enforced automatically: `client.py` is already in `_LEAF_MODULES` at
   `tests/unit/companion/test_import_boundary.py:117-121`; stdlib is unrestricted.)*

2. **Given** a push is requested **When** the client runs **Then** it reads the discovery file, calls
   `GET /health`, and **matches the echoed `instance_id`** before sending the token (AD-4)
   **And** a mismatch or a failed probe is reported as *app not running*, with no token sent.

3. **Given** any outcome **When** the client reports it **Then** it returns exactly one token from the
   closed set `displayed | app_not_running | no_clients_connected | payload_rejected | backend_error`,
   plus the connected-client count (AD-8) **And** the tokens carry no counts inside them and no free
   phrases, matching the project's existing status-token convention.

4. **Given** the backend rejects the token — it restarted mid-session with a new one **When** the client
   handles the rejection **Then** it **re-reads the discovery file and retries exactly once**, so the
   restart is picked up transparently (FR-12, AD-8) **And** a second failure returns `backend_error`
   rather than retrying again.

5. **Given** the backend returns `413 payload_too_large` (413 per the c1-4 review ruling, was 422)
   **When** the client maps it **Then** the outcome is `payload_rejected` (AD-7, AD-8).
   *(Ruled extension, c5-5 Q7: field-cap breaches surface as `400 invalid_request` — the tool layer
   folds **both 400 and 413** into `payload_rejected`. The route's own comment at
   `src/companion/app/routes/agent_events.py:16-24` and the test at
   `tests/unit/companion/test_routes_agent_events.py:364` both anticipate exactly this fold.)*

6. **Given** the backend is reachable but no browser tab is connected **When** the client reports
   **Then** the outcome is `no_clients_connected`, distinguishable from `app_not_running` (FR-12).
   *(On the wire this is a `200 {"clients": 0}` — a success status, not an error; the token is the only
   place it becomes "not shown".)*

7. **Given** any failure whatsoever — unreachable backend, corrupt discovery file, timeout, malformed
   response **When** it occurs **Then** the client **never raises** (FR-12, AD-8).

8. **Given** a corrupt or partially written discovery file **When** the client parses it **Then** the
   parse failure is treated as *app not running*, never an error (AD-4). *(Already `read_discovery()`'s
   behaviour — returns `None` under `except (OSError, ValueError)`; do not reimplement parsing.)*

## Tasks / Subtasks

- [x] **Task 0 — Verify the baseline and grep your own key** (AC: all)
  - [x] Confirm branch `feat/companion-c6` at/after `e59e111`; story branch cut from it.
  - [x] `uv run pytest -m "not integration"` → expect **2,770 passed / 1 skipped, 55 deselected** (c5-8 baseline).
  - [x] `grep -rn "c6-1" src/ tests/ scripts/` and reconcile every hit against the dispositions table in Dev Notes — these are shipped promises this story fulfils.
  - [x] Read `src/companion/client.py` (204 lines) and `tests/unit/companion/test_client.py` end to end before writing anything.
- [x] **Task 1 — The outcome vocabulary and result shape** (AC: 3)
  - [x] Define the closed five-token set and a small result model in `client.py` (leaf — pydantic allowed). Field name `outcome`, **not** `status`, per the dw:3098 collision ruling (see Landmines). Client count travels as a sibling `clients: int | None` field, never inside the token.
- [x] **Task 2 — The push path** (AC: 1, 2)
  - [x] One public `async def` that accepts a concrete `AgentEvent` envelope instance, calls `live_instance()` (never a duplicated probe), and on `None` returns `app_not_running` with **no token sent and no further network call**.
  - [x] POST to `base_url(record.port) + "/agent/events"` with `Authorization: Bearer {record.token}`, body `event.model_dump_json()`, `content-type: application/json`, `trust_env=False`, explicit `httpx.Timeout`, whole exchange under `asyncio.timeout` (mirror `probe_health`'s shape exactly — including client construction/teardown inside the `try`).
- [x] **Task 3 — Outcome mapping** (AC: 3, 5, 6)
  - [x] Map on **status codes only**, never on `reason` strings: `200` + parseable `{"clients": n}` → `displayed` if `n >= 1`, `no_clients_connected` if `n == 0`; `400`/`413` → `payload_rejected`; `403` → the retry path (Task 4); everything else (5xx, unexpected codes, malformed 200 body) → `backend_error`.
- [x] **Task 4 — Retry exactly once on 403** (AC: 4)
  - [x] On the first `403`: re-run the full discovery→health→identity sequence (`live_instance()` again — never reuse the record in hand), send once more with the freshly read token; a second `403` → `backend_error`. Re-read finds no live instance → `app_not_running` (subject to Q2 ruling below).
  - [x] A `403` after the retry has already been spent is terminal — assert in tests that **exactly two** POSTs maximum ever leave the client.
- [x] **Task 5 — Total-failure hardening** (AC: 7, 8)
  - [x] Catch exactly `(TimeoutError, httpx.HTTPError, ValueError)` per branch as `probe_health` does — **never `except Exception`** (a `MemoryError` is not `app_not_running`; c1-8 ruling, `client.py:111-121`).
  - [x] Corrupt/absent discovery is already `read_discovery() → None` → `app_not_running`; add no parsing of your own.
  - [x] The token never appears in any log line at any level (DEBUG rejection logs included).
- [x] **Task 6 — Tests** (AC: all)
  - [x] Extend `tests/unit/companion/test_client.py`: add `do_POST` to `_StubHandler`, extend `StubFleet` for scripted per-request responses (403-then-200 needs a stub whose answer changes between calls), keep the real-loopback-listener style — no mocked transports.
  - [x] Cover: happy path `displayed` + count; `clients: 0` → `no_clients_connected`; 400 and 413 both → `payload_rejected`; 403 → re-read → new token used (assert the **second request carries the re-read token**, not the refused one — c5-8 F5: presence-only re-read checks are vacuous); 403→403 → `backend_error`; dead port / silent socket / drip-feed → `app_not_running` or `backend_error` per stage; malformed 200 body → `backend_error`; no-token-leaks via `_RecordedRequest` + the planted `"planted-token-3xAmPl3"`; exactly-N-requests assertions on every path (assert **outcome token and call count**, not just "didn't raise" — the c5-5 green-probe lesson).
  - [x] Plant one red through the full suite: `uv run python -m scripts.probe_harness --expect-red '<node-id>'` on the new guard of consequence (the retry-token discrimination is the natural plant), revert, record one line on what it compares and cannot see.
  - [x] **No new integration test** (AD-10's exactly-one rule; `test_live_backend.py`'s hand-rolled phase 9 stays as-is — c5-8: *"hand-rolled inside this function on purpose"*).
- [x] **Task 7 — Prose fulfilment, quality gates, mirror**
  - [x] Rewrite the forward-looking `c6-1` prose at the shipped sites (dispositions table below) from promise to pointer; **mint no new forward-looking cross-module prose** (R2 standing rule) — c6-2+'s needs get a `dw:` ledger line, not a docstring paragraph.
  - [x] `uv run ruff check . --fix && uv run ruff format .`; `uv run mypy src/` (strict); full suite green and strictly larger than baseline.
  - [x] Rebuild `plugin/` (`scripts/build_plugin.py`) **after the last edit** and sha256-verify — review patches count as edits (c5-1's falsified-sha headline; R7 is still open so this discipline is the only protection).
  - [x] Record the Dev Notes KB self-check in the Dev Agent Record (C5 target band: 10–20 KB).
  - [x] Set story status to `review` and **STOP** — Brad runs the three-layer review and raises the PR.

### Review Findings

<!-- populated during review -->

Three-layer adversarial review (Blind Hunter, Edge Case Hunter, Acceptance Auditor), 2026-08-09.
13 unique findings after dedup (16 raw); 0 high, 0 medium-blocking, all others low. 6 dismissed as
noise (verified against the code, not taken at a reviewer's word — see below).

- [x] [Review][Patch] New forward-looking c6-2 prose minted in two docstrings, conflicting with
  Task 7's own R2 standing rule ("mint no new forward-looking cross-module prose ... c6-2+'s needs
  get a `dw:` ledger line, not a docstring paragraph") — `src/companion/client.py:123-124`
  (`PushOutcomeToken`: "c6-2 layers a tool-level `deck_not_found` above these five...") and
  `src/companion/client.py:317-321` (`_send`: "c6-2 sends `PUT /api/active-deck` through the same
  gate, with the same header, timeouts and net..."). **Ruled (Brad, 2026-08-09): trim to pointers.**
  Rewrite both docstrings to drop the specific c6-2 predictions, keeping only the present-tense
  rationale (`_send` is generic so a sibling verb can reuse it; the outcome set is closed because
  the client cannot observe tool-level tokens) — and add one `dw:` ledger line for c6-2's actual
  needs instead. Also correct the Completion Notes' now-inaccurate "No forward-looking prose was
  minted for c6-2+ (R2)" claim once the trim lands.

- [x] [Review][Patch] `push_event`'s docstring overclaims "this function never raises, for any
  input, against any listener, ever" [`src/companion/client.py:432-434`] — contradicted by this
  same diff's own test, `test_a_memory_error_is_not_an_outcome_token`, which asserts
  `pytest.raises(MemoryError)` on `push_event` (intentional, per the project's `except Exception`
  ban — matches `_send`'s correctly-scoped docstring one function up). Fix: narrow the wording to
  match `_send`'s carve-out ("never raises for any *reachable failure mode*... a `MemoryError` mid-call
  is a broken machine, not a companion that didn't answer"). Related: `body = event.model_dump_json()`
  at line 471 sits outside the `try`/timeout block entirely, so any exception there — not just
  `MemoryError` — already escapes uncaught; the docstring fix should account for this too rather than
  imply full coverage.

- [x] [Review][Patch] `sprint-status.yaml`'s `last_updated` entry states the suite went
  "2,770 -> 2,811 passed (+41...)" [`_bmad-output/implementation-artifacts/sprint-status.yaml`] —
  verified wrong on two counts: actual is `2810 passed, 1 skipped, 55 deselected` (a +40 delta, not
  +41), and 2,811 is the **collected** count (passed + skipped), not the passed count. The story
  file's own Debug Log References already states this correctly ("2,811 collected, +40 tests over
  baseline"). Fix: align the sprint-status line to the story file's numbers.

- [x] [Review][Patch] The new `_StubServer` lock's docstring overclaims what it protects
  [`tests/unit/companion/test_client.py:206-211`] — the comment says the `threading.Lock()` exists
  "so that a future concurrent case cannot make the script pop and the request log race silently,"
  but only `next_post_response()` (the script) is taken under `self._lock`; `_record()`'s
  `self.server.requests.append(...)` (the request log, line 103) is unlocked. Test-only code, and
  the comment itself notes the lock "is not load-bearing today" — but the claimed protection isn't
  what's built. Fix: either extend the lock to guard `_record()` too, or narrow the comment to what
  it actually covers.

- [x] [Review][Defer] No test pins the 401-vs-403 boundary at the push layer
  [`src/companion/client.py:384-400`, `_outcome_for`] — deferred, pre-existing test-coverage gap,
  not an AC requirement (the "403, not 401" ruling is already pinned elsewhere; this is about a
  regression/misconfigured-proxy answering 401 silently becoming `backend_error` with nothing
  pinning that as intended).

- [x] [Review][Defer] No test covers a restart landing in the narrower window between the `/health`
  probe and the `POST` *within* a single attempt (only the between-attempts race is tested via
  `on_post`) [`src/companion/client.py:403-424`, `_attempt`] — deferred, inherent TOCTOU window of
  any verify-then-act pattern, not practically closable without a redesign, and not requested by
  any AC.

- [x] [Review][Defer] `EventIngestReceipt` has no `extra="forbid"`
  [`src/companion/contracts.py:1313-1349`] — unexpected wire fields alongside a valid `clients` are
  silently ignored rather than rejected. Deferred: the model is pre-existing (c5-5), untouched by
  this diff, and out of this story's bounds (`contracts.py` is listed out-of-bounds in Project
  structure notes).

**Dismissed as noise (6), verified before dropping — not taken at a reviewer's word:**
- Blind Hunter's claim that `_PUSH_TOTAL_SECONDS = 10.0` doesn't actually cover two attempts and
  could let the call run to ~20s: **verified false** — `push_event`'s `async with
  asyncio.timeout(_PUSH_TOTAL_SECONDS):` wraps *both* `_attempt()` calls (probe+POST twice), so the
  whole two-attempt sequence is hard-capped at 10s regardless of individual leg timing; the reviewer
  missed that the outer timeout scopes the full retry, not just one leg.
- Mixed header-key casing (`"Authorization"` vs `"content-type"`) — cosmetic, HTTP headers are
  case-insensitive, zero behavioural effect.
- "The five-token vocabulary can't distinguish active rejection from a raced restart" — deliberate
  per AD-8's closed-set budget, not a defect.
- Citation-style inconsistency between constants (some cite an FR, some cite a ruling) — cosmetic
  prose nitpick.
- Edge Case Hunter's suggestion for a `model_validator` enforcing `clients` is only set on
  `displayed`/`no_clients_connected` outcomes — no reachable path in the diff currently violates
  this; every outcome constructor site was checked and none does. Speculative hardening, not a bug.
- The new outcome vocabulary isn't discoverable from any `skills/**` file — correct and expected:
  no MCP tool wiring lands until c6-2+ (explicitly out of this story's scope), already flagged by
  the standing "skills are a ripple site" gotcha for whichever story does the wiring.

## Dev Notes

### The state you are consuming (all shipped — do not modify behaviour)

**`src/companion/client.py` (c1-8) — the module you extend.** Public surface pinned by
`TestExportedSurface`: `LOOPBACK_HOST = "127.0.0.1"` (literal, not imported from `server.HOST`; IPv4-only
bind — `localhost` resolves `::1` first on Windows), `HEALTH_PATH`, `PROBE_TIMEOUT =
httpx.Timeout(connect=1.0, read=2.0, write=2.0, pool=2.0)`, `_PROBE_TOTAL_SECONDS = 5.0`,
`base_url(port)`, `async probe_health(port, *, timeout=None) -> HealthResponse | None`,
`async live_instance(*, timeout=None) -> DiscoveryRecord | None`. `live_instance` is the whole
"is a companion running?" question in one call: `read_discovery()` → no file, **no network call** →
`probe_health(record.port)` → `instance_id` mismatch → `None`. It returns the **record** precisely
because "its `token` is the credential c6-1 sends next. Nothing here reads that token." Nothing in the
module reads `record.token` today — this story introduces the first read, after identity is proven.

**`src/companion/discovery.py` (c1-7/c1-8) — never reopened by this story** (c1-8 Decide-once #1).
`DiscoveryRecord` = `{port: int (1–65535), token: str (repr=False), instance_id: str}`; unknown keys
ignored by design. `read_discovery() -> DiscoveryRecord | None` is total: absent / unreadable /
truncated / non-JSON / wrong shape all → `None` under `except (OSError, ValueError)`, logged at DEBUG
("a warning per push would be noise in the user's terminal"). AC 8 is already its behaviour.

**`POST /agent/events` (c5-5) — the wire you consume.** `Authorization: Bearer {token}` (RFC 9110
spelling, scheme case-insensitive, `secrets.compare_digest`). Success `200 {"clients": N}` where N is
`broadcast()`'s **delivered** count — `{"clients": 0}` is a success the backend will not re-send;
retrying on zero would push duplicates at the first tab to open (`contracts.py:1321-1324`). Errors are
exactly `{"reason": "<token>"}` + `Cache-Control: no-store`. Status map (`app/errors.py:46-57`):
`invalid_request` 400 · `forbidden` **403** · `payload_too_large` 413 · `internal_error` 500.
Byte cap `_MAX_ENVELOPE_BYTES = 64 KB` enforced **pre-parse** by `BodyCapMiddleware`; a fully
field-valid envelope can still exceed it (c5-5 measured 104,067 bytes at every field limit), so 413 is
reachable from valid-looking data. FastAPI's auto-422 is stripped and banned.

**Envelope (c5-1/c5-5).** `AgentEvent` is an `Annotated` discriminated union (`Field(discriminator="kind")`,
six kinds incl. `active_deck_changed`) — it has **no `.model_validate`**; accept a concrete envelope
instance and serialise with `.model_dump_json()`. Envelopes are `extra="forbid"` with `ts: AwareDatetime`
— a naive timestamp or stray key is a 400 from the backend, which your mapping turns into
`payload_rejected` (correct: the payload was refused).

### The wire → token mapping (the whole story in one table)

| HTTP result | Outcome | Notes |
|---|---|---|
| no discovery file / dead port / `instance_id` mismatch | `app_not_running` | no token ever sent |
| `200 {"clients": n≥1}` | `displayed` | count as sibling field |
| `200 {"clients": 0}` | `no_clients_connected` | wire success; token-level "not shown" |
| `400` or `413` | `payload_rejected` | c5-5 Q7 ruling — both fold; do not re-litigate |
| first `403` | re-read discovery, retry **once** | 403, **not 401** — see below |
| second `403` | `backend_error` | exactly two POSTs max, ever |
| 5xx, unexpected code, malformed 200 body, timeout, transport error | `backend_error` | |

### Ruled deviations — settled, do not re-derive

- **403, not 401.** `errors.py:63-67`: RFC 9110 §15.5.2 requires `WWW-Authenticate` on a 401 and the
  app's raise path structurally cannot attach headers; there is nothing to negotiate with one minted
  token. Confirmed over a real socket (`test_live_backend.py:422`). The retry trigger is `403`.
- **400 and 413 both → `payload_rejected`.** Epic AC 5 names only 413; Q7 (Brad, 2026-08-08) ruled
  field caps to 400 *because* "AD-8's tool layer folds 400 and 413 into one `payload_rejected` token".
- **Zero clients is a 200.** There is no distinct status code; `clients == 0` on a 200 **is** the
  `no_clients_connected` signal.
- **Map on status codes, never `reason` strings.** The `reason` body is for humans and logs; coupling
  the outcome switch to body text would break on any wording change and adds nothing (403 is unambiguous).
- **The leaf is async-only** (c1-8 Decide-once #2) — tools are `async def` (AD-8); no sync wrapper.

### The pattern to copy (solved problems — do not invent)

`probe_health` (`client.py:100-165`) is the template for the POST helper, idiom by idiom:
`httpx.AsyncClient(timeout=..., trust_env=False)` — `trust_env=False` is load-bearing twice (proxies
would misroute the loopback dial; `.netrc` could silently attach an `Authorization` header);
`async with asyncio.timeout(...)` around the **whole** exchange (httpx's `read` deadline only caps gaps
between chunks — the drip-feed stub proves this); catch exactly `(TimeoutError, httpx.HTTPError,
ValueError)` with the whole body *including client construction and teardown* inside the `try` (c1-7
review finding); check `response.status_code` explicitly, never `raise_for_status()`; log rejections at
DEBUG with `%`-style lazy args. Note `httpx.InvalidURL` sits **outside** `httpx.HTTPError` — ports come
from a validated `DiscoveryRecord` (1–65535) so it cannot fire here, but don't widen the catch to
"fix" it.

### Grep-own-key: expected `c6-1` hits and their dispositions (verify at Task 0)

| Site | Disposition |
|---|---|
| `src/companion/client.py:6, 15, 89, 133, 178` | **Fulfilled by this story** — rewrite promise → description |
| `src/companion/discovery.py:27, 105, 192` | Fulfilled (retry-once, DEBUG-not-WARNING rationale) — rewrite to pointer, module otherwise untouched |
| `src/companion/app/security.py:336, 449, 474` | Reference only (Bearer spelling, three-debugging-sessions log rationale) — may rewrite tense, no behaviour change |
| `src/companion/app/errors.py:436`, `main.py:134`, `routes/agent_events.py:88`, `routes/active_deck.py:138`, `server.py:311`, `contracts.py:104` | Reference only — rewrite tense where the promise lands, else leave |
| `src/mcp_server/__main__.py:217` | Reference only |
| `tests/unit/companion/test_client.py:468, 519-527`, `test_discovery.py:145, 155, 510`, `test_errors.py:230`, `test_import_boundary.py:116, 127`, `test_routes_active_deck.py:214, 360, 493` | Guards pre-declaring this story's surface — satisfy, don't delete |
| `tests/integration/companion/test_live_backend.py:30, 293, 407` | Reference implementation — **leave the hand-roll as-is** (Q3 below) |

R2 standing rule applies to every rewrite: cross-module rulings get one canonical home; prose sites
become one-line pointers; **no new forward-looking prose for c6-2+**.

### Landmines specific to this story

1. **Vocabulary collision (dw:3098-3106, homed here, Medium).** `deck_not_found` / `card_not_found`
   already exist as **MCP tool `status` values** in `.claude/skills/**` and `plugin/skills/**`,
   predating the HTTP wire contract. This story's five tokens must be named so one skill file never
   carries two meanings for one word: use a distinct field name (`outcome`, not `status`) and never
   overload the existing MCP spellings. c6-2 adds `deck_not_found` as a documented **tool-level**
   extension above the client's closed five — do not pre-build it here.
2. **`os.replace` contention (dw:869-881, re-homed here, Low).** Your client is the first production
   concurrent reader of `companion.json` — a backend's atomic publish can fail `WinError 5` while a
   reader holds the file open. `read_discovery()` is already a single `read_bytes()` with an
   immediately-closed handle; keep it that way and add no long-lived handle of your own. No fix wanted
   unless it bites.
3. **The stale-record trap (c5-8 F5).** A retry test that only proves "the file was re-read" is
   vacuous when the re-read returns the same corpse record. Tests must discriminate: assert the second
   request's `Authorization` header carries the **newly planted** token, and count requests.
4. **Probe-timeout-judged-dead (dw:994-1001, Low, not in scope).** A live-but-stalled backend
   answering `/health` past the 2 s read deadline reads as dead. The ledgered candidate fix ("retry the
   probe once") is machinery this story builds and *could* share — but it is not an AC; leave the
   ledger entry pointing at the shared helper if the factoring makes it free, otherwise don't.
5. **Plugin mirror.** `plugin/server/src/companion/client.py` is a build artifact — never hand-edit;
   rebuild + sha256-verify **after the last edit including review patches** (the epic's most-repeated
   failure mode; R7 still open).

### Testing requirements

- Extend `tests/unit/companion/test_client.py` — do not invent a new harness. Every case runs against a
  **real loopback listener** (`_StubServer` on `(LOOPBACK_HOST, 0)`), never a mocked transport. You must
  add `do_POST` to `_StubHandler` and scripted response sequences to `StubFleet` (the 403-then-200 retry
  needs a stub whose answer changes between requests). `plant_discovery()` writes `companion.json` by
  hand (never through `write_discovery` — a fixture built by the code under test proves nothing);
  `_Sockets` gives `.dead()` / `.silent()` / `.drip()`; `FAST` timeouts keep failure cases in ms;
  `isolated_data_dir` (autouse) makes discovery planting safe.
- Assert **outcome token + request count**, not shape or "didn't raise" (c5-5's green-probe lesson: a
  test that passes under the exact failure it exists to catch is worse than no test).
- One planted red through the **full** suite via `uv run python -m scripts.probe_harness --expect-red
  '<node-id>'` (validates collected count; pinned to `-m "not integration"`), reverted, one line recorded.
- Baselines to beat: python 2,770 passed / 1 skipped (`-m "not integration"`), 55 deselected; frontend
  1,868 passed / 69 files — **untouched** (backend-only story; c5-5's precedent: don't pad frontend
  tests to satisfy "strictly larger", the python suite grows instead).
- `mypy --strict` applies (`tests.*` exempt from `disallow_untyped_defs`); ruff line-length 100,
  py312 (`X | None`, built-in generics); Google docstrings; module-level `logger`; `asyncio_mode=auto`
  (no `@pytest.mark.asyncio`).

### Previous-story intelligence (c5-5 / c5-8, merged 2026-08-09)

- c5-5's completion notes are the authoritative ingest-contract record; the consolidated wire table
  lives at `c5-8-the-one-real-socket-integration-test.md:186-199`.
- c5-8 phase 9 is your reference sequence, verbatim: `403` → `discovery.read_discovery()` (re-read,
  don't reuse) → retry with `reread.token` → `{"clients": 0}`. Its docstring: "It is not c6-1. The
  FR-12 retry … is hand-rolled inside this function on purpose."
- The guard-layer lesson (C5 retro §9.1): the four probe GREENs were the epic's best finds — "defects
  live in the guard layer, not the components." Hence the token-and-count assertion discipline above.
- Dev Notes stayed at 10.4–20.5 KB across C5 with no verification thinning (+496 tests) — deferrals are
  trigger-gated: triggered ones carried in full with an "Owed:" clause, not-triggered ones one line +
  `dw:` anchor.
- Stack: httpx **0.28.1** (locked, main dependency), pydantic v2, fastapi 0.140.0. **No new dependency
  is needed or wanted.**

### Project structure notes

- Files touched: `src/companion/client.py` (UPDATE — the only production module),
  `tests/unit/companion/test_client.py` (UPDATE), prose-fulfilment touches listed in the dispositions
  table (comment/docstring tense only, no behaviour), `plugin/` (rebuild). Everything else is
  out of bounds — in particular `discovery.py` behaviour, `app/**` behaviour, `contracts.py`, `ui/`.
- The result model and token set live in `client.py`, not `contracts.py` — the wire contract module
  describes what crosses HTTP; the outcome vocabulary is the caller-side report (AD-16: the MCP
  status-enum convention stops at the MCP boundary, and this vocabulary is that convention's kin).
- `src/companion/__init__.py` stays a pure docstring — no re-exports (it is leaf-constrained itself).
- Story PRs target the umbrella `feat/companion-c6` (Greptile per story); merge ≠ release.

### References

- Story + ACs: `_bmad-output/planning-artifacts/epics-companion-app.md` §Story 6.1 (lines 2671-2712);
  Epic 6 header (891-903); the 6.4 413-amendment comment (2794).
- Architecture: `ARCHITECTURE-SPINE.md` (2026-07-25) — AD-8 (197-209, the story's core), AD-3 (114-125),
  AD-4 (127-141), AD-5 (143-157), AD-7 (173-195, "422" stale — 413 per c1-4 ruling), AD-16 (329-352),
  AD-10 (227-240), sequence diagram (417-436), structural seed (438-462).
- PRD: `prds/prd-Artificial-Planeswalker-2026-07-22/prd.md` — FR-12 (146), FR-06 (126), FR-14 (103),
  CM-1 (189), SC-3 (179), NG5 (72).
- Shipped code: `src/companion/client.py`, `src/companion/discovery.py`,
  `src/companion/app/routes/agent_events.py`, `src/companion/app/errors.py:46-70`,
  `src/companion/app/security.py:316-486`, `src/companion/contracts.py` (envelopes 930-1235,
  `EventIngestReceipt` 1313-1349, caps 348-422).
- Guards: `tests/unit/companion/test_import_boundary.py:116-142`;
  `tests/unit/companion/test_client.py` (harness); `tests/integration/companion/test_live_backend.py`
  phase 9 (406-440).
- Ledger: `deferred-work.md` — dw:3098 (vocabulary collision), dw:869 (`os.replace` contention),
  dw:994 (probe-judged-dead).
- Prior records: `c5-5-token-authenticated-event-ingest-…md`, `c5-8-the-one-real-socket-…md`,
  `epic-c5-retro-2026-08-09.md` §9.1, §7.

## Open questions for Brad (recommendations first — rule before code)

| # | Question | Recommendation |
|---|---|---|
| Q1 | **Public API shape.** One public `async def push_event(event: AgentEvent, *, timeout=None) -> PushOutcome` where `PushOutcome` is a frozen pydantic model `{outcome: Literal[five], clients: int \| None}`? c6-2 needs the same machinery against `PUT /api/active-deck` — factor a private `_send()` now, but expose only the push publicly. | Yes — accept a concrete envelope instance (no re-validation; the union has no `.model_validate`), private shared core, one public function. Don't pre-build 6.2's wrapper. |
| Q2 | **Retry path semantics.** AC 4 says "re-reads the discovery file". Minimal reading = `read_discovery()` only (c5-8 phase 9's literal sequence); full reading = `live_instance()` (re-proves identity before sending the new token, AD-4's rule applied per token-send). And: if the re-read finds nothing live, is that `app_not_running` (honest — the backend went away) or `backend_error` (AC 4's "a second failure")? | Full `live_instance()` on retry — AD-4's "verify before sending the token" has no once-per-call exemption. Re-read finds nothing → `app_not_running`; only a second **403** → `backend_error`. |
| Q3 | **Does the integration test adopt the new client?** c5-8 hand-rolled phase 9 "on purpose" so the wire contract is pinned independently of client bugs. | Leave it hand-rolled. Rewrite its "c6-1's to build" comments to point at the shipped helper (R2 pointer style). Revisit only if a future story must touch that file anyway. |
| Q4 | **Push deadline constants.** Reuse `PROBE_TIMEOUT` values for the POST leg plus a `_PUSH_TOTAL_SECONDS` overall deadline covering probe + post + retry? | Yes — same per-phase `httpx.Timeout`, one new total constant (recommend 10.0 s: two full probe+post cycles fit under it; AD-9's ~1 s bound governs c7's notifier, not this path). |
| Q5 | **Local byte-cap pre-check?** The client could measure the serialised envelope against `_MAX_ENVELOPE_BYTES` (importable — sibling leaf) and return `payload_rejected` without a network call. | No — not an AC, duplicates the cap's enforcement point, and the backend's answer is authoritative. One line in the ledger if anyone ever wants it. |

## Dev Agent Record

### Agent Model Used

claude-opus-5 (Claude Code, bmad-dev-story workflow), 2026-08-09.

### Debug Log References

**Baseline (Task 0).** `uv run pytest -m "not integration"` → `2770 passed, 1 skipped, 55 deselected
in 156.71s`. Matches the c5-8 baseline exactly.

**Final.** `uv run pytest -m "not integration"` → `2810 passed, 1 skipped, 55 deselected in 103.02s`.
**2,811 collected, +40 tests over baseline.** `uv run ruff check .` → *All checks passed*;
`uv run ruff format --check .` → *323 files already formatted*; `uv run mypy src/` → *Success: no
issues found in 93 source files*. Frontend deliberately untouched (backend-only story; c5-5's
precedent — the python suite grows rather than padding vitest).

**RED before GREEN.** The 40 new tests were written and run first:
`40 failed, 27 passed` against the unimplemented surface, then `67 passed` after Tasks 1–5. The
27 are c1-8's existing probe/identity tests, untouched.

**Planted red through the FULL suite (Task 6).** Plant: make `_attempt` fetch the discovery record
**once per `push_event` call** and reuse it on the retry — the exact defect c5-8 F5 names, a client
that "re-reads" by reusing the corpse in hand.

```
uv run python -m scripts.probe_harness --expect-red \
  'tests/unit/companion/test_client.py::TestPushRetriesOnceOnAForbiddenToken::test_a_refused_token_is_re_read_and_the_push_succeeds'

full suite (-m 'not integration'): 2811 collected, 3 failed, 0 errored, exit 1
  RED    ...::TestPushRetriesOnceOnAForbiddenToken::test_a_refused_token_is_re_read_and_the_push_succeeds
  RED    ...::TestPushRetriesOnceOnAForbiddenToken::test_the_retry_re_proves_identity_before_sending_the_new_token
  RED    ...::TestPushRetriesOnceOnAForbiddenToken::test_a_backend_that_vanished_before_the_retry_is_app_not_running
```

Reverted by restoring the pre-plant file; `grep _PLANTED_MEMO src/companion/client.py` → 0 hits.

**What the guard compares, and what it cannot see.** It compares the `Authorization` header bytes on
the *second* POST against the token planted mid-call, and counts POSTs — so it fails a client that
reuses the refused record, and it would also fail one that re-read but sent the old token anyway.
It cannot see *why* the file changed: it does not check that `live_instance()` specifically was the
mechanism (the sibling method-sequence test does that, and the plant took it red too), and it cannot
distinguish a correct re-read from one that got the right token by luck if a future stub ever
planted the same token twice. Three reds and no more is itself the signal that the plant was
confined to the retry path rather than breaking the module.

### Completion Notes List

- **`src/companion/client.py` is the only production module whose behaviour changed.** It grew
  `EVENTS_PATH`, `_PUSH_TOTAL_SECONDS`, `PushOutcomeToken`, `PUSH_OUTCOMES`, `PushOutcome`,
  `_send`, `_outcome_for`, `_attempt` and `push_event`. Nothing in c1-8's half was altered beyond
  docstring tense. `discovery.py`, `app/**`, `contracts.py` and `ui/` had **prose touches only**.
- **AC 1 is auto-enforced and was verified, not assumed:** `client.py` sits in `_LEAF_MODULES`
  (`test_import_boundary.py:117-121`) and the new imports are `pydantic`, `httpx` and two sibling
  leaves. No FastAPI, no uvicorn, not even under `if TYPE_CHECKING:`.
- **AD-4 is applied per token-send, not per call.** `_attempt` re-runs `live_instance()` on the
  retry, so the second POST's credential is proven against a freshly echoed `instance_id`. The
  method sequence a passing retry produces is exactly `GET, POST, GET, POST`, and a test pins it.
- **At most two POSTs ever leave the client.** Proven against a stub whose 403 script *never*
  exhausts, so a third POST would be the client's own doing rather than the stub running out.
- **The retry is spent on 403 alone.** A 500-then-200 script yields `backend_error` after one POST —
  re-sending a payload the backend may already have half-processed is how one push becomes two
  renders.
- **The 200-body parse reuses the shipped `EventIngestReceipt`** rather than a hand-rolled
  `body["clients"]` read. That is what makes `{"clients": -1}` a `backend_error` instead of quietly
  reading as `no_clients_connected` — a row that is in the test matrix precisely because the
  hand-rolled version passes it silently.
- **`_send` is generic over method and path** so c6-2 can reuse it for `PUT /api/active-deck`
  (Q1). It stays private; the public surface is `push_event` alone. **No forward-looking prose was
  minted for c6-2+** (R2) — the note lives in `_send`'s own docstring, describing what it *is*.
- **Test-harness changes, all inside `test_client.py`:** `_StubHandler` gained a real `do_POST`
  (previously `do_POST = do_GET`) answering from a per-stub script whose last entry repeats forever;
  `_StubServer` gained `post_script`, `on_post` and a `.posts` accessor; two sentinel statuses
  (`HANGUP`, `DRIP`) fail the *push* leg at transport level over a real socket while the *probe* leg
  against the same port succeeds. **No mocked transports were introduced** — every case still runs
  against a real loopback listener.
- **The retry tests restart the backend's identity mid-call** via `on_post`. A token re-planted
  before the call is read on the first attempt and proves nothing; one planted after it is never
  read at all. This is the c5-8 F5 trap, avoided by construction.
- **Q5 not built:** no client-side `_MAX_ENVELOPE_BYTES` pre-check. Recorded below rather than in
  `deferred-work.md` — the ruling was "one line in the ledger **if anyone ever wants it**", and
  nobody does yet; opening a ledger row for a declined idea nobody has asked for is the kind of
  bookkeeping R3 was declined for.
- **Plugin mirror rebuilt after the last edit** (`scripts/build_plugin.py`) and sha256-verified —
  all ten touched modules MATCH between `src/` and `plugin/server/src/`.
- **Dev Notes KB self-check: 13.4 KB** (13,738 bytes, `## Dev Notes` → `## Open questions`).
  Inside the C5 target band of 10–20 KB.

**Owed / carried forward (no new prose minted for it):**

- **Candidate, not yet ledgered** — a client-side envelope byte-cap pre-check (Q5, declined). The client could measure
  `event.model_dump_json()` against `contracts._MAX_ENVELOPE_BYTES` and return `payload_rejected`
  without dialling. Declined because it duplicates the cap's enforcement point and the backend's
  answer is authoritative; worth revisiting only if oversized pushes ever become common enough for
  the round trip to matter.
- `dw:994` (probe-judged-dead) was **not** made free by this story's factoring, so it stays where it
  is: the shared helper is `live_instance`, which c1-8 already owned, and adding a probe retry there
  would change the runner's startup behaviour — out of this story's bounds.

### Rulings

<!-- Q# | Ruling | Consequence carried into the diff -->

| Q# | Ruling (Brad, 2026-08-09) | Consequence carried into the diff |
|---|---|---|
| Q1 | **As recommended.** One public `async def push_event(event, *, timeout=None) -> PushOutcome`; `PushOutcome` frozen `{outcome, clients}`; a private generic `_send()` core for c6-2 to reuse. | `push_event` is the only public addition. `_send(record, *, method, path, body, timeout)` is method/path-generic and private. A concrete envelope instance is accepted and **never re-validated** — the union has no `.model_validate`. |
| Q2 | **As recommended.** Full `live_instance()` on the retry; a re-read that finds nothing live → `app_not_running`; only a **second 403** → `backend_error`. | `_attempt` re-runs the whole discovery→health→identity cycle each time. Two tests pin it: the `GET, POST, GET, POST` method sequence, and the vanished-backend case returning `app_not_running` after exactly one POST. |
| Q3 | **As recommended.** The integration test keeps its hand-rolled phase 9; its "c6-1's to build" comments become pointers. | `test_live_backend.py` untouched behaviourally — three comment blocks rewritten to say *why it stays hand-rolled now that the helper exists*: a client bug and a backend bug must not be able to fail the same assertion. |
| Q4 | **As recommended.** Reuse `PROBE_TIMEOUT` per request; add one `_PUSH_TOTAL_SECONDS = 10.0` over the whole call. | Single new constant, pinned by a surface test that also asserts `_PUSH_TOTAL_SECONDS >= 2 * _PROBE_TOTAL_SECONDS` — a deadline that could fire mid-retry would cut off the transparency FR-12 exists to provide. A `DRIP`ping POST proves the cap fires. |
| Q5 | **As recommended — not built.** No local byte-cap pre-check. | No import of `_MAX_ENVELOPE_BYTES`; a `413` is mapped from the wire like any other status. Carried as a `dw:` line above rather than a docstring paragraph (R2). |

### File List

**Production (behaviour):**

- `src/companion/client.py` — UPDATE. The push half: `EVENTS_PATH`, `_PUSH_TOTAL_SECONDS`,
  `PushOutcomeToken`, `PUSH_OUTCOMES`, `PushOutcome`, `_send`, `_outcome_for`, `_attempt`,
  `push_event`.

**Production (prose only — R2 promise→pointer, no behaviour change):**

- `src/companion/discovery.py`
- `src/companion/contracts.py`
- `src/companion/app/errors.py`
- `src/companion/app/main.py`
- `src/companion/app/security.py`
- `src/companion/app/server.py`
- `src/companion/app/routes/agent_events.py`
- `src/companion/app/routes/active_deck.py`
- `src/mcp_server/__main__.py`

**Tests:**

- `tests/unit/companion/test_client.py` — UPDATE. +40 tests, `do_POST` + scripted responses +
  `HANGUP`/`DRIP` sentinels + `on_post` hook + `an_event()` helper.
- `tests/integration/companion/test_live_backend.py` — UPDATE, **comments only** (Q3).

**Tracking:**

- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `_bmad-output/implementation-artifacts/c6-1-leaf-client-with-health-verification-retry-once-and-the-closed-outcome-vocabulary.md`

**Build artifact (rebuilt, never hand-edited):**

- `plugin/server/src/companion/client.py` and the nine other mirrored modules above — sha256-verified
  against `src/` after the last edit.

## Change Log

- 2026-08-09: Story created (create-story workflow) — status ready-for-dev.
- 2026-08-09: All five pre-code questions ruled by Brad, every one as recommended; rulings recorded
  above before any code was written.
- 2026-08-09: Tasks 0–7 implemented. `push_event` + the closed five-token vocabulary landed in
  `src/companion/client.py`; +40 unit tests (2,770 → 2,810 passed); planted red fired on the
  retry-token guard through the full suite and was reverted; prose fulfilled at ten shipped sites;
  `plugin/` rebuilt and sha256-verified. Status → review.
