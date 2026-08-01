---
epic: c3
story: c3-4
work_branch: feat/companion-c3
story_branch: feat/companion-c3-4-active-deck
depends_on: c3-3 (PR #31, merged into the umbrella at 737ce76) — the routes package, the wire pipeline, the error contract, the two schema pins and the wire-prose gate all exist
baseline_commit: 737ce76
---

# Story C3.4: The active deck — readable by the glass, settable by the agent

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As the browser UI on cold open,
I want to ask which deck is active,
so that a fresh tab, or one that reconnected, shows the right deck instead of assuming there isn't one.

**What this story really is.** c3-1 was a projection that had to move down. c3-2 was a closed set
that had to be extended. c3-3 was a specification asking for six checks over a validator that
produced four. **This one is the story where the companion backend stops being a pure read model.**

Four firsts land together, and every one of them is a mechanism that has never run in this codebase:

1. **The first state the backend owns.** Everything served so far was a projection of `cards.db`.
   This is a slot in process memory whose whole contract is that it is *ephemeral* — the epic's own
   AC says a restart must report none (FR-07, CM-3).
2. **The first non-`GET` route.** All five committed paths are `get` (measured below). `PUT` brings
   405 semantics, the SPA mount's method handling, and a request body into play at once.
3. **The first request body.** FastAPI's validation path, the auto-422 stripper and the
   `invalid_request` handler are all built and all unexercised by a body — c1-4 built them for a
   route that would come later, and this is that route.
4. **The first authenticated endpoint — two stories before the story that was going to build the
   authentication.** `security.py`'s own docstring says *"Stories c5-2 and c5-5 add the WebSocket
   ticket and the agent token here beside it"* (`security.py:3-5`). The token is minted
   (`main.py:151`), published (`_publish_discovery`) and readable (`main.agent_token`), and
   **nothing in the codebase verifies it against a request.** c3-4 builds that seam; c5-5 inherits
   it.

The consequence to internalise before writing code: **this story's biggest risk is not the
happy path, it is the rejection path.** `agent_token(app)` returns `None` before the lifespan runs
(`main.py:192-215`), and a naive `if presented == agent_token(request.app)` is an **open door** the
moment both sides are `None` (landmine 11). The security envelope this app already has fails *closed*
on exactly this shape — `host_is_allowed(host, None)` returns `False` and says so in its docstring —
and the new check must match it.

**Fifteen things were measured on this machine at `737ce76`. Do not rediscover them.**

### The seam that already exists (do not rebuild any of it)

1. **The token is minted, published and accessible — and unverified.** `main.py:150-153`: the
   lifespan sets `app.state.instance_id`, `app.state.agent_token = discovery.mint_token()` and
   `app.state.database`. `main.agent_token(app) -> str | None` (`:192-215`) is the **single reader**,
   mirroring `bound_port` and `deps.database`. Its docstring already names the production consumer:
   *"Story c5-5 is the production consumer … and nothing else may."* **That sentence becomes false
   with this story** and is a forward-dated comment this story must repair (AC 20).

2. **`mint_token()` is `secrets.token_urlsafe(32)`** (`discovery.py:101-111`) — URL-safe base64, so
   always ASCII. That matters for landmine 10 (`compare_digest` and non-ASCII input); the *presented*
   value is attacker-controlled and carries no such guarantee.

3. **`DiscoveryRecord.token` carries `repr=False`** (`discovery.py:81`) and the module docstring
   states the token *"reaches exactly two places — this file and `app.state`"*. This story adds a
   third reader (the dependency) and **no new writer**. `test_discovery.py` pins the four surfaces
   the token must not reach: response body, headers, logs, schema. All four gain a new route to
   cover (AC 12).

4. **`CompanionError` + `STATUS_BY_REASON` is the only way to answer non-2xx** (`errors.py:45-93`).
   The status is derived from the token, never chosen at the call site. **A raise site cannot attach
   headers**: `companion_error_handler` calls `error_response(exc.reason)` with no `headers=`
   (`errors.py:227`), while `error_response` *can* take them (`:96-122`) — the parameter exists for
   the `HTTPException` path only. This is load-bearing for Q2: **RFC 9110 requires a `401` to carry
   `WWW-Authenticate`, and this app's raise path cannot carry it** without widening `CompanionError`.
   `403` carries no such requirement.

5. **`ErrorReason` is closed at seven** (`contracts.py:46-54`), and the extension rule is AD-16's:
   *"a new token and the UI state it drives are added together — never a token alone."* The rule has
   teeth on the TypeScript side (landmine 11), and `payload_too_large` is the precedent for a token
   whose "UI state" is **deliberately no panel at all**.

6. **`validation_error_handler` already answers `400 invalid_request` for a bad body**
   (`errors.py:230-253`) and logs `exc.errors()` rather than returning it. `_CompanionFastAPI.openapi`
   strips the auto-422 for every route (`main.py:171-207` / `:335-361`). So a malformed `PUT` body
   needs **no new code** — but it does need a test, because nothing has ever sent one.

7. **`install_spa(app)` MUST STAY LAST, and the ordering comment now argues with itself about who
   owes an edit** (`main.py:396-414`). c3-3 added a route to an existing router and edited nothing.
   **A story adding a *router* still owes both the `build_app()` line and the `test_spa.py`
   differential line** (`test_spa.py:~296-317`, whose comment now spells the router/route
   distinction out). Which of the two this story is depends on Q1's sub-decision — decide it, then
   pay the tax deliberately or record that it does not apply.

8. **The SPA mount already handles methods correctly, and the mechanism is `_SpaMount.matches`**
   (`spa.py:191-235`): a reserved first segment returns `Match.NONE` so the *router* answers, which
   is what produces `405` with the RFC-mandated `Allow`. The class docstring predicts this story's
   neighbour by name — *"once c5-5 adds a POST-only `/agent/events` a plain `GET` of it would answer
   `404` instead of `405 Allow: POST`"*. c3-4 is the **first chance to actually exercise that
   claim**: `POST /api/active-deck` must answer `405` with `Allow` naming `GET` and `PUT`. Measure
   it; do not assume it (AC 8).

9. **`test_import_boundary.py` bans *database* writes, not memory writes.** Its guard is repository
   write methods, `session.add/commit/delete`, DML constructs, `init_database`/`create_all` and
   `src.data.importers`. This route touches no session at all. It must pass **unchanged with no
   exclusions** — and the reason is worth stating in the record rather than discovering: AD-2 is
   about `cards.db`, and an in-memory display slot is not a write path (AC 11).

10. **The test seam is `lifespan_client` + `isolated_data_dir`** (`tests/unit/companion/conftest.py`).
    Every companion test flows through the real security envelope; `httpx.ASGITransport` alone sends
    no lifespan messages, so `app.state.agent_token` would be **absent** — which is precisely the
    fail-closed case this story must prove, so it needs the *bare* `build_app()` path too, not only
    the seam. `_lifespan_client` accepts `headers=` per client (`conftest.py:122`), which is how a
    test presents a credential.

### The four firsts, and what each one costs

11. **The credential comparison is the one place a bug is a security hole, and it has three
    distinct traps.**

    - **Fail-open on `None`.** `agent_token(app)` is `None` before startup. `presented == None` is
      `False` for any string — but `None == None` is `True`, and a caller can present *no* header,
      which is also naturally modelled as `None`. Any implementation where "absent header" and
      "no minted token" are both `None` and are then compared **authenticates every request against
      an unstarted app**. `host_is_allowed` (`security.py:105-107`) is the shipped precedent: it
      refuses when *either* side is missing, and its docstring says why. Match it, and pin it with a
      test that drives a `build_app()` whose lifespan never ran.
    - **`secrets.compare_digest` raises on non-ASCII `str`.** It accepts `str` **only if both
      arguments are ASCII-only**; a header value containing `ü` raises `TypeError`, which
      `UnhandledErrorMiddleware` turns into `500 internal_error` — a caller-controlled input
      producing a false backend-bug report, and a trivially reachable one (headers decode as
      latin-1). Compare **bytes**, or guard before comparing. A test must present a non-ASCII
      credential and assert the rejection token, not a 500.
    - **`==` leaks timing.** Localhost-only and low-value, but `compare_digest` costs nothing and
      the alternative is explaining the choice in a review.

12. **An eighth reason token is not a one-line change, and the machinery is the point.** If Q2 adds
    one, the ripple is **measured, not estimated**:

    | Site | What breaks |
    | --- | --- |
    | `src/companion/contracts.py:46-54` | the `Literal` and its "Closed at **seven**, with nothing planned" docstring |
    | `src/companion/app/errors.py:45-58` | `STATUS_BY_REASON`; a test pins the two sets **equal**, so a token with no status fails loudly |
    | `tests/unit/companion/test_errors.py` | the closed-set pins |
    | `ui/src/api/schema.ts:42-52` | the alias docstring says "**Seven** as of c3-2 … that file is the one place the count is written" |
    | `ui/src/api/schema.test.ts:37-50` | *"All seven named explicitly"* — an exact union pin, edited by name |
    | `ui/src/components/StatePanel/states.ts:98-100` | `PANEL_FOR_REASON … satisfies Record<ErrorReason, StateKey \| null>` — **`tsc` fails** until the new token is mapped |
    | `ui/src/components/StatePanel/states.ts:140` + `states.test.ts:60` | `NO_UI_RESPONSE` is pinned to **exactly** `['invalid_request', 'payload_too_large']` |

    That is AD-16's pairing rule working exactly as designed — the frontend **cannot compile** until
    somebody decides what the new token means on the glass. It is also why Q2 is a genuine fork and
    not a formality: the answer "no panel, agent-facing only" is available (`payload_too_large` has
    already taken it), but it must be *chosen*, in the same commit, with the `NO_UI_RESPONSE` pin
    edited by name.

13. **A `PUT` body is read before the dependency that would reject it.** In FastAPI's request
    handler the body is read and parsed *before* dependencies are solved, so a token dependency does
    **not** protect the process from an unauthenticated caller posting an enormous body. There is no
    body-size cap anywhere in the app today: `payload_too_large` (413) exists as a token but has no
    producer — c5-5 owns the 64 KB envelope cap (AD-7). **Verify the ordering at Task 0 against the
    installed FastAPI 0.140.0** (read `fastapi/routing.py`'s `get_request_handler`) rather than
    trusting this paragraph, then answer Q4 with the measurement in hand. Note the mitigations that
    already exist and are real: the `Host` envelope refuses any request that did not address the app
    as loopback on the bound port, and a cross-origin `PUT` with a JSON content type is preflighted
    — and this app installs **no CORS middleware at all** (C1's no-CORS ruling), so the preflight
    `OPTIONS` gets a `405` and the browser never sends the request.

14. **Deck-existence validation is forbidden here, and that is a ruling, not an omission.** AD-16:
    *"Deck-existence validation for `companion_set_active_deck` belongs to the MCP tool — it has DB
    access and it is the one that must report `deck_not_found` to the agent; the backend stores what
    it is given"* (spine `:349-352`; epic AC at `:1658`). Concretely: this route takes **no
    `DbSession`**, imports no repository, and can answer neither `503` — it is the first route since
    `/health` with no database dependency at all. `deps.py:282-302`'s `DbSession` docstring
    enumerates its callers as c3-1/c3-2/c3-3; c3-4 deliberately does not join that list, and saying
    so is cheaper than a reviewer asking.

15. **Two later stories consume this and neither is this story's to build.**
    - **c5-4** broadcasts `active_deck_changed` when the store succeeds (epic `:2441-2443`).
      Build **no** hook, no callback registry, no placeholder — c5-4 adds one call after the store,
      to a handler that will exist. Record the decision so it reads as deliberate.
    - **c6-2** is `companion_set_active_deck`, which validates the deck exists, calls this `PUT`
      with the agent token, and reports `displayed` plus the client count (epic `:2638-2669`).
      The client half it uses is c6-1's, in the leaf. **The MCP server package must hold no
      active-deck state of any kind** (CM-3, epic AC `:1668-1670`) — that is an assertable property
      of this story, not a promise deferred to Epic 6.

### What the committed artifacts say right now (measured at `737ce76`)

- `ui/src/api/openapi.json`: `paths` = `['/api/cards/{card_id}', '/api/deck/{deck_id}',
  '/api/deck/{deck_id}/format-check', '/api/decks', '/health']` (**5**), and **every operation is
  `get`** — the method list across all five paths is `['get','get','get','get','get']`.
  `components.schemas` = `['Card', 'CardSummary', 'DeckCardSummary', 'DeckDetail', 'DeckSummary',
  'ErrorResponse', 'FormatCheckReport', 'FormatCheckRow', 'HealthResponse']` (**9**). There is **no
  `requestBody` anywhere in the document** — this story adds the first one, and with it the first
  `openapi-typescript` request-body rendering in `types.d.ts`.
- `scripts/dump_openapi.py` names **c3-4** in its docstring as the next story. Make that true, restate
  the counts, name c3-5.
- **Two files pin the exact component-name set** — `test_routes_decks.py:695` and
  `test_routes_cards.py:960`. This duplication is the `deferred-work.md` entry **homed on c3-4 by
  name**: c3-2 found the second pin by running the suite, c3-3 did it again, and the entry says c3-4
  *"will otherwise inherit the same surprise a third time."* **Q5.**
- Suites at the baseline, to be **re-measured not inherited**: Python **2044 passed / 1 skipped**;
  frontend **558 passed (29 files)**.

---

## Acceptance Criteria

### The read

1. **`GET /api/active-deck` answers `200` with a defined body in both states, and the body is
   unwrapped** (AD-16, FR-07): no `status` envelope. With nothing set it reports "none" through the
   shape Q3 rules; with a deck set it reports that deck id. **The same response model in both
   cases** — no union, no `X | None` response model — so c4-1 has one shape to render and
   `test_errors.py::_is_ref_rooted` is not tripped (c3-3's Q4 precedent).

2. **The read requires no credential and no session** (epic AC `:1649`). Asserted positively: a
   client presenting **no** headers beyond `Host` gets `200`. Explicitly absent from the handler:
   `DbSession`, any repository import, any credential read.

3. **A restart reports none** (FR-07, CM-3). Proved through the real seam: enter the lifespan, `PUT`
   a deck id, read it back, exit the lifespan, enter a **fresh** `build_app()`'s lifespan, and assert
   `GET` reports none. Not a unit test of the holder — the whole point is that the state dies with
   the process.

### The write

4. **`PUT /api/active-deck` with a valid credential stores the id and answers per Q3**, and a
   following `GET` returns it. Asserted as a **sequence through the wire**, never by reading the
   holder directly.

5. **No deck-existence check is performed** (AD-16, epic AC `:1658`). A `PUT` naming an id that is
   not in the database **succeeds**, and a following `GET` returns it. Explicitly absent from the
   diff: any `DeckRepository`, any `DbSession`, any `src.data` import in the route module. This is a
   *positive* test of an absence — the id used must be one the fixtures prove is not a real deck.

6. **A missing credential and a wrong credential are both rejected, the active deck is unchanged,
   and the rejection is the vocabulary Q2 rules** (NFR-01). Asserted on status **and** exact body.
   Four cases, each with a `GET` afterwards proving the slot did not move: no header at all; a header
   with an empty value; a wrong token; and **a token that is a prefix of the real one** (so a
   comparison that is doing something other than full equality fails here rather than in production).

7. **The check fails closed when no token has been minted** (landmine 11). A `build_app()` whose
   lifespan never ran rejects every `PUT`, including one presenting no credential and one presenting
   the literal string the accessor would return. The test drives the real ASGI app; a unit test of
   the comparison function alone does not satisfy this AC.

8. **The route table's method semantics are measured, not assumed** (landmine 8):
   `POST /api/active-deck` answers **`405`** carrying an `Allow` header that names `GET` and `PUT`;
   the typed body is `{"reason": "invalid_request"}` (`http_exception_handler`'s 4xx arm). The
   measurement is pasted in the record, because `spa.py`'s docstring makes this claim about a route
   that did not exist until now.

9. **A malformed body answers `400 {"reason": "invalid_request"}`** through the shipped
   `validation_error_handler`, with **no new handler and no `try`/`except` in the route**. Cases:
   not JSON at all; JSON that is not an object; the object missing the id field; the id field of the
   wrong type; and whatever Q3's shape constraint rejects. The auto-422 does **not** appear in the
   regenerated schema for this operation (`without_auto_validation_schema` covers it — verify on the
   real artifact).

10. **The credential never leaks.** After a `PUT` — accepted *and* rejected — the token value appears
    in **none** of: the response body, any response header, the regenerated `openapi.json`,
    `types.d.ts`, or any log record emitted during the request. The rejection log names the fact and
    the path, never the presented value or the expected one. `test_discovery.py`'s four-surface pin
    is extended to cover this route rather than duplicated.

### Boundaries

11. **No write path is opened.** `tests/unit/companion/test_import_boundary.py` passes **unchanged
    with no exclusions added**, and the record states why an in-memory slot is not an AD-2 write
    (landmine 9). Explicitly absent from the diff: every repository mutation method, `session.add`,
    `session.commit`, `session.delete`, `init_database`, `create_all`, `src.data.importers`.

12. **The MCP server holds no active-deck state** (CM-3, epic AC `:1668-1670`) — asserted, not
    asserted-by-absence-of-thought: a test greps `src/mcp_server/**` for any active-deck symbol and
    for any import of the new state module, and the leaf/app import guard proves `src/mcp_server`
    cannot reach `src.companion.app` at all.

13. **The two credentials share no storage and no code path** (AD-5). c5-2's ticket does not exist
    yet, so the assertable half is: the token check reads `main.agent_token` and nothing else, stores
    nothing, and the active-deck holder holds no credential. State the property so c5-2 inherits a
    rule rather than a coincidence.

14. **The route is not shadowed by the SPA mount**, proved by asserting **status and body** — not
    content-type (c3-1 review R1: the content-type-only version passed with the router deleted,
    because `/api` is reserved and answers JSON either way). `test_spa.py::TestMountOrdering` and the
    reserved-prefix tests stay green. If Q1 adds a **router**, the differential list at
    `test_spa.py:~296-317` gains its line **and** `build_app()` gains its `include_router` above
    `install_spa`; if Q1 joins an existing router, the record states that measurement instead.

### The wire contract

15. **`npm run gen:api` is run and both generated files are committed together** — neither
    hand-edited, neither prettier-formatted (both stay in `.prettierignore`). Measured before →
    after: **5 paths → 6**, **9 component schemas → N** with N stated and every added name listed and
    justified (nothing removed). Both drift gates green from the same commit, output pasted:
    `uv run pytest tests/unit/companion/test_openapi_contract.py` and, from `ui/`,
    `npm run gen:types && git status --porcelain` (no output).

16. **The first `requestBody` in the document is inspected and recorded** (landmine "measured
    artifacts"): what `openapi-typescript` generates for it, whether the field is optional or
    required in the generated TypeScript, and whether the operation carries a `security` block. If a
    FastAPI security class was used anywhere, that is a deviation to justify — see Q4.

17. **No Python-internal or credential-shaped prose crosses the wire, scanned by FAMILY not by
    member.** After regeneration, `types.d.ts` is scanned with c3-2's `PYTHON_INTERNAL_FAMILIES`
    plus the literal markers (`>>> `, `model_validate`, `SQLAlchemy`, `pydantic`, `src/mcp_server`),
    **plus** the credential markers `companion.json`, `agent_token`, `mint_token` and `Bearer`.
    Every hit is fixed **at the Python docstring** — rewriting the leading summary for a TypeScript
    reader and pushing the detail below a truncating header — never by editing the generated file.
    Rationale, and it is a judgement to record rather than a rule to obey silently: `/docs` is served
    to the browser, and the wire description of an agent-only endpoint is the wrong place to teach a
    page where the credential is kept.

18. **`ui/tests/wire-contract.test.ts` picks up the new component names with no edit to its ban
    mechanism**, proven non-vacuously by a **staged** planted declaration of one of the new type
    names in a scratch `ui/src` file — red, then reverted. Probe output and revert both pasted.
    `toContain` anchors may be added beside the existing ones (c3-1 review R7).

19. **If Q2 adds a token, every ripple site in landmine 12's table is worked in the same commit** —
    including the two frontend pins that fail by name (`schema.test.ts`'s explicit union and
    `states.test.ts:60`'s exact `NO_UI_RESPONSE` array) and the `satisfies Record<ErrorReason, …>`
    that fails `tsc`. Each red is updated **deliberately with its comment restated**; a red silenced
    without restating its comment is how the next story inherits a lie (c3-2's lesson). If Q2
    declines the token, the table is stated as *not applicable* with the reason.

### Records, comments and the mirror

20. **The forward-dated-comment inventory is repaired** (standing agreement). Each row either becomes
    true, is re-homed, or is recorded with a judgement. At minimum:

    | # | Location | What it says | Action |
    | --- | --- | --- | --- |
    | 1 | `src/companion/app/main.py:192-215` (`agent_token`) | "Story c5-5 is the production consumer … and nothing else may" | **Becomes false** — c3-4 is the first consumer; restate, and keep the never-serialize rule intact |
    | 2 | `src/companion/app/security.py:3-5` and `:197-211` (`install_security`) | "Stories c5-2 and c5-5 add the WebSocket ticket and the agent token here beside it" | **Update** — the token half lands now; c5-2's ticket and c5-5's ingest still to come |
    | 3 | `src/companion/app/errors.py:61-68` (`CompanionError` callers) and `:125-140` (`error_responses` callers) | enumerate c1-6/c3-1/c3-2/c3-3, "c5-5 follows" | **Update** — a fourth and fifth caller, and the first non-`GET` one |
    | 4 | `src/companion/app/deps.py:282-302` (`DbSession` callers) | names c3-1/c3-2/c3-3 as the callers | **Verify + state** — c3-4 deliberately does **not** join the list (landmine 14). Say so, or leave it untouched and say why |
    | 5 | `src/companion/app/main.py:396-414` (the ordering block) | "c5-2 and c5-5 add theirs there too"; c3-3's route-vs-router note | **Update per Q1** — either a new router joins the list, or the route-not-router case gains a second instance |
    | 6 | `src/companion/app/spa.py:191-201` (`_SpaMount`) | predicts c5-5's POST-only route as the first method-mismatch case | **Restate** — c3-4 gets there first, with a measurement (AC 8) |
    | 7 | `scripts/dump_openapi.py` | "Story c3-4 … is next" + the counts | **Becomes true** — restate both counts, name c3-5 |
    | 8 | `deferred-work.md`'s c3-4-homed entry | the duplicated component-name pin | **Resolve or re-home by name** per Q5 |

21. **The plugin mirror is rebuilt and committed** (`uv run python -m scripts.build_plugin`), and the
    SPA bundle is **re-measured, not assumed**: `src/companion/app/static/` and
    `plugin/server/src/companion/app/static/` are expected byte-identical (this story ships no
    runtime frontend code). If either changed, that is a finding to explain, not a rebuild to wave
    through.

22. **`deferred-work.md` gains this story's residue with named homes**, at minimum: whatever Q4
    declines on the body cap (homed on **c5-5**, which owns `payload_too_large`); the absence of a
    clear-the-active-deck path if Q3 declines one; the `active_deck_changed` broadcast seam (homed on
    **c5-4**); whatever Q5 declines; and anything the review turns up. No residue in prose only.

23. **No frontend behaviour ships.** `ui/src/App.tsx` and every component are unchanged in behaviour;
    **c4-1 owns the fetch and the store**, c4-2 the deck view. Permitted `ui/` changes: the two
    generated files, AC 18's anchors, `ui/README.md`, and — **only if Q2 adds a token** — the four
    pin/alias sites in landmine 12's table. Any deviation is recorded as a deviation **at the time it
    is made** (c3-2's round-2 lesson; c3-3 booked three deviations at review time and that is the
    standard).

### Testing

24. **Tests live at `tests/unit/companion/test_routes_active_deck.py`** and drive the real
    `build_app()` through `lifespan_client`. Coverage: the none state; the set state; the
    set-then-read sequence; restart-forgets (AC 3); the unknown-deck-id acceptance (AC 5); all four
    rejection cases (AC 6); fail-closed with no lifespan (AC 7); the non-ASCII credential (landmine
    11); `405` with `Allow` (AC 8); the five malformed-body cases (AC 9); the four leak surfaces
    (AC 10); not-shadowed-by-SPA on status **and** body (AC 14); and the committed schema's new path,
    new operation and new component names.

25. **Non-vacuity pairing on every guard-shaped assertion** (standing agreement): each proves it
    **fires** and proves it **stays silent** from the same invocation. Concretely — every rejection
    case is paired with the accepted case in the same test class so "rejects everything" cannot pass;
    AC 5's no-existence-check is paired with a real deck id so it is not passing because the route
    accepts nothing; and AC 10's leak scan is paired with a planted occurrence of the token proving
    the scanner can see one.

26. **At least four mutation probes are run, verified on disk before the verdict and reverted after**
    (standing agreement — *probe your own guard before review does*): (a) the credential comparison
    replaced with `True`; (b) the fail-closed guard removed, so `None == None` authenticates; (c) the
    route silently unregistered or renamed; (d) AC 18's planted type name. Paste each result, and
    **read the output before filing it** — c3-1's review found three vacuous tests hiding inside a
    "19 failed" probe result.

27. **Every gate is re-run and its output pasted**: `uv run pytest`, `uv run ruff check .`,
    `uv run ruff format --check .`, `uv run mypy src/`, `uv run mypy src/ --platform win32`, plus the
    frontend gates from `ui/` (`lint`, `format:check`, **`npx tsc -b --force`**, `test`, `build`) and
    both drift checks. Suite counts stated as *before → after*, measured at Task 0 and again at the
    end. Baseline to beat, **to be re-measured not inherited**: **Python 2044 passed / 1 skipped** ·
    **frontend 558 passed (29 files)**.

---

## Tasks / Subtasks

- [x] **Task 0 — Baseline, measured not assumed** (standing agreement)
  - [x] `git fetch origin feat/companion-c3`; confirm the umbrella tip is `737ce76`; cut
        `feat/companion-c3-4-active-deck` from it
  - [x] Run and record: `uv run pytest` (count + duration), `ruff check`, `ruff format --check`,
        `mypy src/`, `mypy src/ --platform win32`
  - [x] From `ui/`: `npm run lint`, `format:check`, **`npx tsc -b --force`**, `npm test` (count),
        `npm run build`
  - [x] Record the pre-change SHA-256 of `src/companion/app/static/assets/*` and the `plugin/` mirror
        (AC 21)
  - [x] Record the committed `paths`, operations and `components.schemas` keys (expect 5 / all-`get`
        / 9)
  - [x] **Verify landmine 13 against the installed FastAPI 0.140.0**: read `fastapi/routing.py`'s
        request handler and record whether the body is read before dependencies are solved. Q4
        depends on the answer

- [x] **Task 1 — The state slot** (AC 3, 12, 13; Q1)
  - [x] Place the holder where Q1 rules, with the accessor convention `deps.database` /
        `main.bound_port` / `main.agent_token` already establish
  - [x] No lock, and say why in the code: the slot is a single assignment with no read-modify-write,
        unlike `Database._create`'s multi-step build — do not cargo-cult the lock
  - [x] Wire it in the lifespan beside `app.state.database`; nothing may be created in `build_app()`
        (AD-10)

- [x] **Task 2 — The credential check** (AC 6, 7, 10, 13; Q2, Q4)
  - [x] Add the dependency to `src/companion/app/security.py` — the module its own docstring says
        this belongs in; function-local import of `main.agent_token` per the shipped precedent at
        `security.py:154-159`
  - [x] Fail closed on a missing minted token **and** a missing presented credential; compare with
        `secrets.compare_digest` over **bytes**; never log either value
  - [x] Raise `CompanionError(<Q2's token>)`; construct no response, pass no status, import no
        `JSONResponse`

- [x] **Task 3 — The routes** (AC 1, 2, 4, 5, 8, 9, 11, 14; Q1, Q3)
  - [x] The wire models where Q3 rules (`contracts.py` is the leaf and the precedent — `HealthResponse`
        lives there); `response_model=` on both operations
  - [x] `GET` — no credential, no session; `PUT` — the credential dependency, the request body
  - [x] `responses=error_responses(...)` declaring only what these routes uniquely produce
  - [x] Google-style docstrings; the **leading paragraph is what crosses the wire** (AC 17)
  - [x] Register per Q1's module sub-decision, above `install_spa(app)`; pay or disclaim the
        `test_spa.py` line, **measured**

- [x] **Task 4 — If Q2 adds a token, work every ripple site as one list** (AC 19)
  - [x] `contracts.py`, `errors.py`, `test_errors.py`, `schema.ts`, `schema.test.ts`, `states.ts`,
        `states.test.ts` — landmine 12's table, in one commit, each comment restated

- [x] **Task 5 — Regenerate the wire types** (AC 15, 16, 17, 18)
  - [x] From `ui/`: `npm run gen:api`; diff both files; confirm 6 paths and the new component count
  - [x] Record what the first `requestBody` generates (AC 16)
  - [x] Run the family scan **plus the credential markers** over `types.d.ts`; fix at the Python
        docstring and regenerate on any hit
  - [x] Probe the wire-contract guard: **stage** a planted type name in a scratch `ui/src` file,
        `npm test` → red, revert → green; paste both

- [x] **Task 6 — Tests and probes** (AC 24, 25, 26)
  - [x] `tests/unit/companion/test_routes_active_deck.py` with the full coverage list
  - [x] Re-run `test_import_boundary.py`, `test_spa.py`, `test_discovery.py` and `test_security.py`
        explicitly, and paste the counts
  - [x] Four mutation probes (AC 26), each verified on disk and reverted

- [x] **Task 7 — The homed housekeeping item** (Q5)
  - [x] Apply Q5's ruling on the duplicated component-name pin, or re-home it by name

- [x] **Task 8 — Comments, docs, records** (AC 20, 21, 22, 23)
  - [x] Work the eight-row forward-dated-comment table
  - [x] Rebuild + commit the plugin mirror; re-measure the bundle against Task 0
  - [x] `deferred-work.md` entries with named homes; add any new `ui/README.md` blind-spot row
  - [x] Fill the Dev Agent Record; update `sprint-status.yaml`

- [ ] **Task 9 — Same-day three-layer review before the PR** (C2 retro action item 6, standing)
  - [x] `bmad-code-review` (Blind Hunter + Edge Case Hunter + Acceptance Auditor) before raising the PR
  - [x] Apply patches, then re-run every gate and paste the output
  - [x] Raise the PR into `feat/companion-c3` — PR #32 (2026-08-01)

### Review Findings

Round 1, 2026-08-01 (Blind Hunter + Edge Case Hunter + Acceptance Auditor, this working tree at baseline `737ce76`):

- [x] [Review][Decision] **Both active-deck operations wire-declare `503`/`413` they can never produce** — `ui/src/api/openapi.json` / `types.d.ts` advertise `database_unavailable`, `database_not_initialized` and `payload_too_large` on the first DB-free, (for GET) body-less routes, while `deps.py`'s new paragraph states "neither operation can answer 503". The app-wide `responses=` default in `build_app()` is a decide-once ruling ("leave it"), but c3-4 is the first story where the declaration and reality diverge — a `types.d.ts` consumer (c6-1, the SPA) builds dead retry branches. Options: (a) prune per-route via `responses=` overrides + regen, (b) keep the app-wide default and document the divergence on the operations' wire descriptions, (c) accept as-is and ledger for c6-1.
- [x] [Review][Decision] **Whitespace-only `deck_id` (`" "`, `"\t"`) is accepted and stored** — `contracts.py:226`'s `min_length=1` counts characters, not content, yet the docstring's own rationale for refusing `""` ("reported as the active deck forever while resolving to no deck at all") applies identically. The credential parser one module over strips whitespace for exactly this reason. Options: (a) refuse whitespace-only via a validator (consistent with "a bound, not a shape" — it is still non-emptiness), (b) retreat the docstring and accept it as just another unknown id. No test covers it either way.
- [x] [Review][Decision] **`ActiveDeckRequest` claims "the deck id and nothing else" but ignores extra fields** — Pydantic's default drops unknown keys, so `{"deck_id": "x", "persist": true}` gets a 200 instead of the 400 that would correct a wrong agent-side mental model. `extra="forbid"` would make the sentence enforced; it is a wire-behaviour change on a route with no clients yet. Recommend forbid.
- [x] [Review][Patch] **New README blind-spot row is a detached, headerless one-row table** [ui/README.md:931-934] — the credential-vocabulary row is separated from the table by blank lines on both sides, so it renders as a literal pipe paragraph, not a table row. Remove the blank line.
- [x] [Review][Patch] **The "credential check stores nothing" guard is satisfied by trivial evasions and was never probed** [tests/unit/companion/test_routes_active_deck.py:704-714] — bans only `ast.Assign` with `Dict`/`List`/`Set` *literals*; `_seen = set()` (a `Call`), any `AnnAssign`, or a class-level attribute all pass. The MCP-side test four screens up already handles `AnnAssign`. Violates both standing agreements (ban-the-family; probe-your-own-guard). Strengthen + plant an evasion and record it going red.
- [x] [Review][Patch] **AC 25's planted-token probe of the leak scan was not run** [tests/unit/companion/test_discovery.py] — the one guard that shipped unprobed, on the story whose spec named c3-3's scan-that-caught-nothing as the most likely repeat. Plant an occurrence, watch the scan fire, revert, record.
- [x] [Review][Patch] **`PUT` echoes the request body, not the slot** [src/companion/app/routes/active_deck.py:134] — docstring promises "echo back what was stored"; `return ActiveDeck(deck_id=_slot(request).deck_id)` makes it true by construction before c5-4's broadcast can diverge them.
- [x] [Review][Patch] **"Byte-identical … handed straight to `GET /api/deck/{deck_id}`" is false for path-reserved characters** [src/companion/contracts.py:189, src/companion/app/state.py] — an id containing `/`, `?`, `#` or `%` cannot be a raw path segment; soften the round-trip prose (URL-encoding caveat) since Q4 rules the shape stays unconstrained.
- [x] [Review][Patch] **A presented-but-malformed credential is logged as "no agent credential"** [src/companion/app/security.py:367] — `presented_credential` collapses `Basic xyz` / bare-token / empty-Bearer to `None`, so the one diagnostic bit the docstring sells (c6-1's header-construction bug case) lands in the wrong bucket. Distinguish header-absent from header-unparseable.
- [x] [Review][Patch] **Three AST-guard tests use CWD-relative paths** [tests/unit/companion/test_routes_active_deck.py:409, :685, :699 region] — inconsistent with the `Path(__file__)`-anchored style used in the same file; fail from any other cwd.
- [x] [Review][Patch] **Bare `data`/`deps` in the banned-identifier set is a noise trap** [tests/unit/companion/test_routes_active_deck.py:409] — `code_identifiers` collects every `Name`; a legitimate `data = response.model_dump()` local reds a database-layering guard, the exact failure mode the module's own MCP-side test argues against. Also `node.module or ""` seeds `""` into every identifier set.
- [x] [Review][Patch] **The defended unstarted-app `GET` 500 has zero measured executions** [src/companion/app/routes/active_deck.py:42-64] — fourteen docstring lines defend `AttributeError → 500 internal_error`, and no test drives GET on a lifespan-less app. Add one.
- [x] [Review][Patch] **The valid-credential 405 test under-asserts** [tests/unit/companion/test_routes_active_deck.py, `test_the_405_precedes_the_credential_check`] — asserts only the status; the class exists because `Allow` was silently wrong, so assert `Allow: GET, PUT` and the body token on the closest thing to c6-1's real retry path.
- [x] [Review][Patch] **`supported_methods` matches nested-mount children against the un-stripped path** [src/companion/app/errors.py:302-349] — correct today only because every mount sits at `/`; a future non-root `Mount` silently degrades (or wrongly inflates) the `Allow` union, a *different* hole from the ledgered attribute-walk soft failure. Document in the docstring + extend the existing ledger entry.
- [x] [Review][Patch] **Record-evidence gaps: AC 16/26/27 "recorded/pasted" is summarized** [Dev Agent Record] — the generated-TS optionality of the first `requestBody` is never stated, and probe/gate output is tabulated rather than pasted. Paste the missing blocks.
- [x] [Review][Defer] **Unauthenticated callers get unbounded body buffering + a validation oracle on the first authenticated endpoint** [src/companion/contracts.py:200-226] — deferred, already ledgered to c5-5 (AD-7's 64 KB cap); note added that `test_a_malformed_body_without_a_credential_is_still_forbidden` *pins* the body-before-credential ordering, so c5-5 must decide whether that pin is contract or snapshot.
- [x] [Review][Defer] **A future hand-raised 405's deliberate headers are overridden or case-split** [src/companion/app/errors.py:405-handler] — deferred, unreachable today (no code raises 405 manually); the recompute would replace an author's `Allow`, and a lowercase `"allow"` key survives the merge as a second header.

---

## Dev Notes

### Decide-once rulings this story inherits (do not re-derive)

| Ruling | Source | What it means here |
| --- | --- | --- |
| REST is HTTP-native; success bodies are Pydantic schemas **unwrapped** | AD-16 | `response_model=`; no envelope, no wrapper key, on both operations |
| The active deck lives in the **backend**, never in the MCP server | project-context D5, PRD CM-3, spine inherited-constraints table | The slot is `src/companion/app` memory; AC 12 asserts the MCP side stays clean |
| Deck-existence validation belongs to the **MCP tool**, not the backend | AD-16 (`:349-352`) | No `DbSession`, no repository, no 503 on either operation |
| The agent token authorises pushing and **never reaches the browser** | AD-5 | The `GET` is credential-free; the token is never serialised, logged or documented on the wire |
| The two credentials share no storage and no code path | AD-5 | c5-2's ticket must be able to land beside this without touching it |
| The status is derived from the token, never chosen at the call site | `errors.py` module docstring | `raise CompanionError(...)`; never `JSONResponse`, never `status_code=` |
| A route declares only the tokens it uniquely produces | c3-1 AC 6 | `error_responses(...)` per route; `build_app()`'s app-level `responses` unchanged |
| One generator, from the backend's own `app.openapi()` | AD-12 | `npm run gen:api`; no second codegen, no hand-written TS shape |
| `install_spa(app)` stays last in `build_app()` | c2-2 | Register above it — or reuse a router already above it |
| One response shape always; no union response model | c3-3 Q4 | The "none" state is a value in the shape, never a different shape |
| Ban the family, never enumerate members | C2 retro, standing | AC 17's scan is family-keyed; the credential markers are additions to it, not a replacement |
| Probe your own guard before review does | C2 retro, standing | AC 26's four probes are not optional |
| Claims require verification | standing | Paste real gate output; measure the bundle and the FastAPI body ordering, do not assume them |
| Copy lives in `EXPERIENCE.md` and is gated | c2-9 | Nothing here is copy: the "none" state is a **value**, and the no-active-deck panel's prose already shipped in c2-9 |

### The six things this story must not break

1. **`tests/unit/companion/test_import_boundary.py`** — both guards, AST-only, sees modules no test
   imports. Its docstring forbids routing around it by convention: *"a guard satisfied by
   obfuscation is theatre"* — no `getattr`, no dynamic import.
2. **`tests/unit/companion/test_discovery.py`'s token-leak pins** — the four surfaces (body, headers,
   logs, schema). This story adds the first route that *reads* the token, so those pins gain a case
   rather than a duplicate.
3. **`test_spa.py`** — `TestMountOrdering`, the reserved-prefix pins, and the differential router
   list. Landmine 7: measure whether it needs a line; the answer depends on Q1.
4. **`test_openapi_contract.py`'s byte comparison** — including LF line endings and
   `ensure_ascii=False`, plus c3-2's `PYTHON_INTERNAL_FAMILIES`. Never hand-edit `openapi.json`;
   always regenerate.
5. **Both component-name pins** — `test_routes_decks.py:695` **and** `test_routes_cards.py:960`.
   **Two stories in a row found the second one by running the suite instead of by reading the story.**
   This story names both in advance; there is no excuse for finding either during a probe. Q5 decides
   whether that stops being true for c3-5.
6. **`ui/src/components/StatePanel/states.ts`'s `satisfies Record<ErrorReason, StateKey | null>`** —
   if Q2 adds a token, this fails `tsc`, not a test. That is the frontend refusing to compile until
   somebody decides what the token means on the glass, and it is working as designed.

### Source tree — what exists, what this story adds

```
src/companion/
  contracts.py            EDIT — the active-deck wire models (Q3); the ErrorReason Literal (only if Q2)
src/companion/app/
  state.py                NEW  — the in-memory active-deck slot, if Q1 rules the spine's module
  security.py             EDIT — the agent-token dependency (the module its own docstring names)
  routes/
    active_deck.py        NEW  — both operations, if Q1 rules a separate router (then main.py +
                                 test_spa.py too), or:
    decks.py              EDIT — if Q1 rules the routes join the existing router instead
  main.py                 EDIT — the lifespan creates the holder; the ordering block; agent_token's
                                 docstring (row 1 of AC 20)
  errors.py               EDIT — STATUS_BY_REASON (only if Q2); docstrings either way
scripts/dump_openapi.py   EDIT (docstring only) — c3-4 shipped; counts; c3-5 next
tests/unit/companion/
  test_routes_active_deck.py    NEW
  test_state.py                 NEW — only if Q1's holder has behaviour worth isolating
  test_security.py        EDIT — the credential-check matrix as a pure function
  test_discovery.py       EDIT — the leak pins gain this route
  test_routes_decks.py    EDIT — the component-name pin
  test_routes_cards.py    EDIT — the second component-name pin (both, or Q5's consolidation)
  test_errors.py          EDIT — only if Q2 adds a token
  test_spa.py             VERIFY — edit only if Q1 adds a router
ui/src/api/
  openapi.json            REGENERATED (committed)   5 paths -> 6
  types.d.ts              REGENERATED (committed)   9 schemas -> N
  schema.ts, schema.test.ts     EDIT — only if Q2 adds a token
ui/src/components/StatePanel/
  states.ts, states.test.ts     EDIT — only if Q2 adds a token
ui/tests/
  wire-contract.test.ts   EDIT — the new toContain anchors (AC 18)
ui/README.md              EDIT — any new blind-spot row
plugin/**                 REBUILT — required by CI's drift gate
```

**Not touched, deliberately:** `ui/src/App.tsx`, every `ui/src/components/**` except the two
`StatePanel` files above and only under Q2, `src/companion/client.py` (**c6-1 owns the sending
half**), `src/companion/discovery.py`, `src/companion/app/deps.py` (landmine 14 — this route takes no
session), `src/data/**`, `src/logic/**`, `src/mcp_server/**` (**c6-2 owns the tool**).

### Previous story intelligence (c3-1, c3-2 and c3-3, and their six review passes)

- **Fourteen of fourteen stories have answered their open questions "as proposed"** (one partial).
  The questions below are written to be answerable the same way, but **Q2 and Q4 are genuine forks** —
  they change what ships, not just where it lives.
- **The round-1 5/5 Greptile cause is six-times confirmed:** the same-day three-layer
  `bmad-code-review` before raising the PR. Standing action item. Task 9.
- **c3-3's headline finding is this story's most likely repeat, in a new costume.** Its AC 5 guard
  caught **0 of 12** planted evasions because every family was keyed on the syntax its own firing
  tests happened to use. The guard-shaped things here are AC 10's leak scan and AC 12's MCP-state
  grep. **Plant an evasion against each before trusting it** — a token embedded in a nested log
  argument, an active-deck symbol reached by a different spelling.
- **c3-3's second finding: a shipped product artifact consumed the vocabulary it extended.**
  `.claude/skills/format-legality/SKILL.md` enumerated `validate_deck`'s rules and went stale, and
  the story had not named it as a ripple site. **Applied here:** if Q2 adds a reason token, grep
  `.claude/skills/**` and `plugin/skills/**` for the error vocabulary before declaring the ripple
  list complete. Nothing in the test suite pins skill prose against the wire.
- **c3-2's finding: a true count read as a false rule, published to the wire.** Applied here: every
  general claim in a docstring that crosses the wire must be re-derived from the measurement, not
  from a neighbouring one — especially anything about *when* the active deck is `null`, which c4-1
  will code against.
- **c3-1's R1 finding.** `TestNotShadowedBySpa` passed with the router *deleted*, because `/api` is
  reserved and answers JSON either way. AC 14 asserts status **and** body for exactly that reason.
- **c3-1's R3 finding.** Nothing tied a nested value to its source because every fixture was
  identical on the asserted fields. **Every deck id in these tests must be distinguishable** — the
  set-then-read sequence proves nothing if the id is the same string everywhere.
- **c3-1's finding 1: `plugin/**` is not "not touched".** A stale mirror is a guaranteed red build.
- **c3-2's `Warning:` ruling.** `Note:` and `Warning:` are the two Google headers `main.py`
  deliberately does **not** truncate — so a `Warning:` is a wire-visible paragraph, and c3-3 used one
  to warn c4-1 about a real trap. Use a code comment for anything a UI author should not read, and a
  `Warning:` deliberately when they must. **A credential's location is the first kind, not the second.**
- **c3-3 booked three deviations at review time and named them in the record.** That is now the
  standard: record a deviation from the permitted-file list **when you make it**.

### Git intelligence

- `737ce76` — PR #31 merged c3-3 into `feat/companion-c3` (the local branch may be stale; fetch before
  cutting). `2a787ac` — PR #30, c3-2. `a52d6f8` — integration PR #28 on master.
- The C2/C3 rhythm holds: **story branch off the umbrella, story PR into the umbrella with a Greptile
  pass per story**, one integration PR to master after the retro with **no** Greptile pass (OSS
  free-tier budget, standing rule). Merge ≠ release — no tag, no CHANGELOG until c8-4.
- Commit style: Conventional Commits, `feat(companion): …`.
- c3-1's, c3-2's and c3-3's shape is the model to copy: one small `feat` commit, then a separate
  review-patch commit, then the records commit.

### Gotchas specific to this story

- **`PUT`, not `POST`.** The epic names `PUT` and it is right: setting the same deck twice is the same
  state, so the operation is idempotent. Do not "improve" it to `POST`.
- **A deck id has no declared shape** (c3-1's ruling), so there is **no** `Path`/`Field(pattern=...)`
  here and no malformed-deck-id answer. Do not import c3-2's card-id uuid pattern by analogy. A
  *minimum length* is a different claim from a *shape* — see Q3.
- **Reading the credential from `request.headers` keeps it out of the schema**; declaring it as an
  `Annotated[str, Header()]` parameter would document the header name in `types.d.ts` and `/docs`.
  Both are defensible; Q4 rules, and the choice must be recorded either way.
- **FastAPI's `HTTPBearer`/`APIKeyHeader` security classes raise their own `HTTPException` with their
  own body shape.** That lands in `http_exception_handler` and becomes `invalid_request` at *their*
  status, silently bypassing the token Q2 chooses. They also add a `securitySchemes` component and a
  `security` block to the artifact. If one is used, that is a decision with consequences, not a
  convenience.
- **`secrets.compare_digest` on `str` requires both sides ASCII-only** and raises `TypeError`
  otherwise — a caller-controlled 500. Compare bytes.
- **Async everywhere in `src/data`; this route touches none of it.** Both handlers are `async def`
  because FastAPI wants them so, and neither awaits anything but the framework.
- **`mypy --strict` and `--platform win32`** are both gates. `app.state` is `Any` — the accessor
  pattern (`holder: X | None = getattr(app.state, "…", None)`) exists because `warn_return_any` flags
  returning it directly. Copy it; do not re-derive it.
- **`format` is a field name, not a builtin misuse** (project-context.md) — irrelevant here, but ruff
  `N` is on and the naming rules apply to the new module.
- **Versions installed on this machine, measured at c3-2:** FastAPI **0.140.0**, Starlette **0.48.0**,
  Pydantic **2.12.0**. This story needs **no new dependency**; adding none is part of it.

### Testing standards

- `pytest` config is in `pyproject.toml`; `asyncio_mode = "auto"` — write `async def test_…` with
  **no** `@pytest.mark.asyncio`.
- Layout mirrors `src/`: `tests/unit/companion/` for anything driven in-process over
  `httpx.ASGITransport`. This story adds **no** `integration`-marked test — AD-10 rules that exactly
  one such test exists in the whole feature and it belongs to **c5-8**.
- Reuse `lifespan_client` and `keep_spa_mount_last` from `tests/unit/companion/conftest.py`. Do not
  write a second seam. `_lifespan_client(app, headers=...)` is how a test presents a credential; the
  **no-lifespan** case (AC 7) deliberately bypasses the seam and drives `ASGITransport` directly.
- `tests.*` is exempt from `mypy --strict` but not from ruff or the naming rules.
- Paste real gate output. **`npx tsc -b --force` is a separate claim from `npm test`** — c3-2 measured
  `tsc -b` caching a clean result over a real failure, and Q2's ripple is a `tsc` failure, not a test
  failure.

### Architecture rules this story implements

- **FR-07** — `companion_set_active_deck` switches which deck the UI displays; the **companion
  backend owns the active-deck ID in memory**; before any set-active call, and after a restart, the
  UI shows the no-active-deck state.
- **AD-5** — two credentials that never touch; the agent token authorises writing and never reaches
  the browser.
- **AD-16** — HTTP-native REST, unwrapped bodies, closed reason tokens, one typed error body; and the
  explicit ruling that deck-existence validation belongs to the MCP tool.
- **AD-2 / NFR-02** — read-only *with respect to the database*, enforced by the CI import boundary.
  Memory is not the database, and the record says so.
- **AD-10** — `build_app()` has zero side effects; the lifespan owns everything with an effect.
- **AD-12 / NFR-03** — one generator from the backend's own `app.openapi()`; committed,
  drift-checked.
- **CM-3** — ephemeral state lives in the backend, never in the MCP server, and dies with the process.
- **NFR-01** — the write is credential-gated; the socket is loopback-only; the `Host` envelope is
  already installed.
- **UX-DR30 / UX-DR33** — the no-active-deck panel's copy and deck list shipped in c2-9. This story
  supplies the **signal**, not the copy.

### References

- [epics-companion-app.md § Story 3.4](../planning-artifacts/epics-companion-app.md) — the ACs this
  story expands (lines 1638-1670); the endpoint's own justification (275-277); **Story 5.4's
  broadcast AC** (2441-2443); **Story 6.2, the tool that calls this** (2638-2669); Story 5.5's
  token-authenticated ingest (2453-2486)
- [ARCHITECTURE-SPINE.md](../planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md) —
  AD-3 (114-125), AD-4 (127-141), **AD-5 (143-157)**, AD-6 (159+), AD-10, AD-12, **AD-16 (329-352)**,
  and the Structural Seed's `app/state.py` line (448)
- [EXPERIENCE.md:44,63,112,119](../planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md) —
  the no-active-deck state, its verbatim copy, the cold-open layout and the restart behaviour
- [c3-3 story record](c3-3-format-check-endpoint-over-the-existing-validators.md) — the one-shape
  ruling, the guard-evasion finding, the three booked deviations, and the review that produced them
- [c3-2 story record](c3-2-card-detail-endpoint.md) — the closed-set extension precedent, the
  wire-prose gate and the `Warning:` ruling
- [c3-1 story record](c3-1-deck-list-and-deck-detail-endpoints.md) — the projection ruling, the
  deck-id-has-no-shape ruling, and review findings R1/R3/R7/R12
- [deferred-work.md](deferred-work.md) — the entry **homed on c3-4 by name** (the duplicated
  component-name pin) and the corrected `test_spa.py` router-list tax
- [epic-c2-retro-2026-07-30.md](epic-c2-retro-2026-07-30.md) — the standing agreements (ban the
  family; probe your own guard) and action item 6 (same-day three-layer review)
- [project-context.md](../project-context.md) — layer boundaries, async rules, docstring style,
  ruff/mypy gates

---

## Open questions for Brad — answer before `dev-story`

**Q1 — Where does the slot live, and which module holds the two routes?**

The spine's Structural Seed already names a module: `app/state.py # active deck, connections,
tickets — in memory (AD-5)`. Nothing has needed it until now.

| Option | Verdict |
| --- | --- |
| **`src/companion/app/state.py`** — a small holder class created by the lifespan beside `deps.Database`, with a `main`-style accessor | **Proposed.** It is the module the spine names, c5-2's tickets and c5-4's connections join it rather than inventing a third home, and it matches the shipped convention exactly: an inert holder built in the lifespan, one accessor, no `build_app()` effect |
| A bare `app.state.active_deck_id` with an accessor in `main.py` | **Not proposed.** Cheaper today, but it puts display state in the module that owns identity and wiring, and c5-2/c5-4 would then either follow it there or split the state across two homes |
| `deps.py` | **Rejected.** That module is the database engine and its session dependency; the docstring says so twice |

**No lock, deliberately.** `Database` holds one because engine creation is a multi-step
check-then-assign whose next `await` would reintroduce double-creation. Setting a `str | None` is a
single assignment with no interleaving point on single-threaded asyncio. Say that in the code, so the
absence reads as a decision rather than an oversight.

*Sub-decision — the route module.* Proposed: **a new `src/companion/app/routes/active_deck.py` with
its own router**, paid for with the two hand-synchronised edits (`build_app()`'s `include_router`
above `install_spa`, and `test_spa.py`'s differential list). The alternative is joining
`decks.router`, which costs nothing — but `decks.py`'s docstring is *"Reading saved decks … a
repository call apiece"* and every route in it takes `DbSession`. An authenticated in-memory write
with no database at all is not a deck read, and hiding it there would make that module's docstring
false. c3-3 correctly avoided the tax because its route genuinely was a deck sub-resource; this one
is not. *Recommendation: as proposed, both parts — and pay the tax visibly.*

---

**Q2 — How is a rejected credential reported?** *(genuine fork)*

`ErrorReason` is closed at seven and none of them means "your credential was refused". AD-16's
extension rule is that a new token and the UI state it drives are added **together**.

| Option | Verdict |
| --- | --- |
| **Add an eighth token — `forbidden`, at `403`** — mapped to **no panel**, joining `payload_too_large` in `NO_UI_RESPONSE` | **Proposed.** AD-8 requires the agent-side client to *distinguish* an auth rejection ("re-read the discovery file and **retry exactly once**") from a malformed request, which it cannot do if both are `invalid_request` at 400 — it would retry the wrong failure, or not retry the right one. `payload_too_large` is the precedent for an agent-facing token with no glass destination, so the pairing rule is satisfied by a *decision*, not by a panel |
| Reuse `invalid_request` at `400` | **Fallback.** Zero ripple, and defensible while nothing consumes the distinction — c6-1 does not exist yet. But it hands c6-1 a retry rule it cannot implement without a wire change, and a wire change is exactly what this epic is meant to settle before Epic 5 freezes the union |
| `401` with a new token | **Not proposed.** RFC 9110 requires a `401` to carry `WWW-Authenticate`, and the `CompanionError` path **cannot attach headers** (landmine 4) — so this option silently widens `CompanionError`, or ships a non-conformant 401. `403` carries no header requirement and is the honest status for "a credential was presented and refused", with no challenge-response scheme to advertise |

**The cost, stated honestly.** Option 1 ripples into **seven** sites (landmine 12's table), two of
which are frontend pins that fail by name and one of which is a `tsc` failure, not a test failure.
It is a bigger diff than the routes. It also freezes a token into the generated union that this epic
cannot demonstrate a consumer for until c6-1 — which is the same bet c1-4 made with `internal_error`
and the same one c3-2 made with `card_not_found`, both of which the retro judged correct.
*Recommendation: option 1, with the token mapped to no panel and `NO_UI_RESPONSE` extended by name.*

---

**Q3 — The two wire shapes: what is "none", and what does `PUT` accept and return?**

Proposed, four parts:

1. **`ActiveDeck` in `src/companion/contracts.py`, carrying `deck_id: str | None`** — one response
   model for **both** operations. `null` **is** the "none" response the epic asks for (`:1648`); there
   is no separate empty shape and no `404` for "nothing set", because nothing is missing — the
   resource exists and its value is "no deck". `contracts.py` is the right home by precedent
   (`HealthResponse` lives there) and by AD-3 (it is a leaf, so c6-2 can import it without dragging in
   FastAPI).
2. **A separate request model requiring a non-empty id** — `deck_id: str` with `min_length=1`. A
   *minimum length* is not a *shape*: c3-1 ruled a deck id has no declared shape, and this does not
   declare one. It only refuses the value that would otherwise be stored and then reported forever as
   an id no `GET /api/deck/{id}` can resolve. Rejection is `400 invalid_request` through the shipped
   validation handler, with no new code.
3. **No clearing.** The request model does **not** accept `null`, so there is no way to un-set the
   active deck over the wire. Nothing in the epic asks for one: FR-11's "deck deleted → no-active-deck"
   is a *client* transition (`EXPERIENCE.md:120` — a refetch 404), and a restart clears it anyway.
   Ledger it with a named home rather than building an unused verb.
4. **`PUT` answers `200` with the same `ActiveDeck` body**, echoing what was stored, rather than
   `204`. It costs nothing, it gives c6-2 something to assert beyond a status code, and it is the same
   value c5-4's `active_deck_changed` envelope will carry — one shape, three consumers.

*Recommendation: as proposed, all four parts.*

---

**Q4 — How is the credential presented, and does this story cap the request body?** *(genuine fork
on the second half)*

*Presentation.* Proposed: **`Authorization: Bearer <token>`**, read from `request.headers` inside the
dependency rather than declared as a `Header()` parameter or via a FastAPI security class. Standard
spelling for c6-1 to send; no `securitySchemes` block and no `security` operation key in the
artifact; no auto-422; and — the reason that decides it — a FastAPI security class raises its **own**
`HTTPException`, which lands in `http_exception_handler` and answers `invalid_request` at that
class's status, silently bypassing whatever Q2 rules. Reading the header ourselves keeps the one
rejection vocabulary intact and keeps the credential's *name* out of the browser-facing types.

*The body cap.* This is the fork, and landmine 13 must be measured before it is answered: FastAPI
reads and parses the body **before** solving dependencies, so the token dependency does not stop an
unauthenticated caller from making this process buffer an arbitrarily large body. Nothing in the app
caps a body today.

| Option | Verdict |
| --- | --- |
| **`max_length` on the id field, and ledger the pre-parse cap to c5-5** | **Proposed.** The pydantic cap is honest about what it is (a field constraint, applied after parsing) and costs one line. The *real* cap belongs to the story that owns `payload_too_large` and the 64 KB envelope limit, and it should be one mechanism for both endpoints rather than two |
| Build the pre-parse cap here (a `Content-Length` check producing `413 payload_too_large`) | **The real alternative.** It gives the app its first producer for a token that has been declared since c1-4 and has never fired, and c5-5 would inherit it. But it is a middleware-shaped mechanism designed against one story's requirements, built in a story whose scope is a 40-byte body |
| Nothing | **Rejected.** Not because the risk is high — it is a loopback port behind `Host` validation, reachable only by local software that could do worse directly — but because "the first endpoint with a body shipped with no thought about body size" is exactly the sentence a review writes |

*Recommendation: as proposed — the field cap here, the mechanism homed on c5-5 by name — unless the
Task 0 measurement shows the body is read* after *dependencies, in which case say so and the ledger
entry gets smaller.*

---

**Q5 — Does c3-4 take the housekeeping item homed on it by name?**

`deferred-work.md` homes one here: **two files each pin the exact `components.schemas` key set**
(`test_routes_decks.py:695`, `test_routes_cards.py:960`), so every schema-adding story edits both —
and the last two stories each found the second one by running the suite rather than by reading the
story. The entry names c3-4 as the story that *"will otherwise inherit the same surprise a third
time."*

Proposed: **take it**, following c3-2's and c3-3's precedent that a story takes the convention
decisions filed against it rather than passing them on. The fix shape is already written in the
entry: one whole-artifact pin in one place — a `tests/unit/companion/test_committed_schema.py` that
owns the component-set and path-set assertions — leaving each per-route file asserting only its own
path and its own operation. This story adds components either way, so it pays the edit once instead
of twice and c3-5 inherits one pin.

The alternative is deferring it a second time, which is defensible only if you would rather not have
this story move two existing test files. *Recommendation: as proposed, take it.*

---

## Dev Agent Record

### Agent Model Used

Claude Opus 5 (1M context) — `claude-opus-5[1m]`

### Open questions — Brad's answers

**All five answered "as proposed" (2026-08-01). Fifteen of fifteen stories now.** Q2 and Q4b were the
genuine forks and both took the larger option.

| Q | Answer | What it means for the diff |
| --- | --- | --- |
| **Q1** | **As proposed, both parts** | New `src/companion/app/state.py` holder (the module the spine's Structural Seed names at `:448`), created in the lifespan beside `app.state.database`, one `main`-style accessor, **no lock with the reason stated in code**. New `src/companion/app/routes/active_deck.py` with **its own router** — so the tax is owed and paid visibly: `build_app()`'s `include_router` above `install_spa`, **and** `test_spa.py`'s differential router list |
| **Q2** | **Add the eighth token — `forbidden` at `403`**, mapped to **no panel** | The full landmine-12 ripple lands in this commit: `contracts.py`, `errors.py`, `test_errors.py`, `schema.ts`, `schema.test.ts`, `states.ts` (a **`tsc`** failure, not a test failure), `states.test.ts:60`'s exact `NO_UI_RESPONSE` array — **plus** a grep of `.claude/skills/**` and `plugin/skills/**` for the error vocabulary (c3-3's shipped-artifact lesson). Chosen so c6-1 can implement AD-8's "re-read discovery and retry exactly once" without a later wire change |
| **Q3** | **As proposed, all four parts** | One `ActiveDeck` response model (`deck_id: str \| None`) for **both** operations — `null` **is** the none state, no union, no `404`. A separate request model with `min_length=1` (a minimum length is not a shape). **No clearing verb** — ledgered. `PUT` answers `200` echoing the same body, not `204` |
| **Q4** | **As proposed** — `Authorization: Bearer <token>` read from `request.headers` **inside** the dependency; `max_length` on the id field; the pre-parse cap **homed on c5-5** | No FastAPI security class, so no `securitySchemes` component, no `security` operation key, no auto-422, and the credential's *name* never reaches `types.d.ts` or `/docs`. **The Task 0 measurement did not shrink the ledger entry** — see below |
| **Q5** | **Take it** | New `tests/unit/companion/test_committed_schema.py` owns the whole-artifact component-set and path-set pins; `test_routes_decks.py:695` and `test_routes_cards.py:960` are reduced to their own path and their own operation. c3-5 inherits one pin, not two |

**Q4's dependency, measured not assumed** (landmine 13, Task 0). In the installed **FastAPI 0.140.0**
(`.venv/Lib/site-packages/fastapi/routing.py`), `get_request_handler`'s inner `async def app(request)`
reads and parses the body at **lines 423-448** and calls `solve_dependencies` at **line 473**.
**The body is read before dependencies are solved**, so the token dependency does *not* protect this
process from an unauthenticated caller posting a large body. The Q4 recommendation's escape hatch
("unless the measurement shows the body is read *after* dependencies") **did not apply** — the ledger
entry homed on c5-5 stands at full size.

Two useful side-effects of the same read, which is why AC 9 needs no new code:
`json.JSONDecodeError` at `:449` is re-raised as `RequestValidationError` → the shipped
`validation_error_handler` → `400 invalid_request`; any *other* body-parse exception at `:467`
becomes `HTTPException(status_code=400)` → `http_exception_handler` → the same token.

### Debug Log References

**Five findings, three of which corrected this story's own text.**

1. **`POST /api/active-deck` answered `Allow: GET`, not `Allow: GET, PUT`** — AC 8 was wrong to
   assume, and right to demand the measurement. Starlette 0.48.0's router keeps only the **first**
   partially-matching route (`routing.py:738`, `elif match == Match.PARTIAL and partial is None`)
   and `Route.handle` builds the header from *that one route's* method set (`:283`). Two
   single-method routes on one path therefore advertise one method. Unreachable before this story:
   every path in the app had exactly one method, so the first partial match was also the only one.
   RFC 9110 §15.5.6 requires the field to list *the resource's* methods, so the answer was wrong,
   not merely terse — and the client it would mislead is c6-1, the one that exists to write here.
   **Repaired in `errors.supported_methods`**, the module that already owns "keep the framework's
   headers". Verified across every path: two-method paths report both, single-method paths are
   unchanged.

2. **FastAPI 0.140 does not flatten included routers into `app.routes`.** Discovered while fixing
   (1): the first recomputation returned an empty union because `app.routes` holds four lazy
   `_IncludedRouter` wrappers, which answer `Match.PARTIAL` for the whole branch and carry no
   `methods`. `_leaf_routes` walks them **by attribute**, so an upstream change degrades to "found
   nothing" and the caller keeps Starlette's header rather than raising inside an error handler.
   Ledgered.

3. **A guard of mine tripped on its own docstring** — c3-3's headline finding, in a new costume.
   `test_the_route_module_imports_no_data_layer` scanned raw source for `DbSession` and failed on
   the paragraph in `active_deck.py` explaining why the route deliberately does **not** take one.
   Rewritten AST-only (`code_identifiers`), matching `test_import_boundary.py`'s stance. The same
   fix was applied to the other three source-scanning guards in the file **before** they had a
   chance to fail the same way.

4. **`agent_token_is_valid("", "")` returned `True`.** Found by my own matrix. Unreachable through
   the route — `presented_credential` collapses an empty credential to `None`, and a minted token is
   never empty — but it is the `None`/`None` fail-open shape wearing a different spelling, and
   c5-5 inherits this function. The guard is now `if not presented or not expected`.

5. **The story's ripple table for an eighth token named seven sites; there are eight.**
   `ui/tests/unknown-card-copy.test.ts:206` holds a **third** pin on `NO_UI_RESPONSE` (it parses
   `states.ts` and asserts the exact member list as its own non-vacuity anchor). Found by running
   the suite. Ledgered as informational — the pin is correct and caught a real omission; it is the
   *count* that was folklore.

**Measurements taken and not assumed.**

* **FastAPI body-vs-dependency ordering** (landmine 13, Q4's fork): body read and parsed at
  `fastapi/routing.py:423-448`, `solve_dependencies` at `:473`. **Body first.** Q4's escape hatch
  did not apply; the c5-5 ledger entry stands at full size. Two useful consequences: a
  `json.JSONDecodeError` at `:449` becomes `RequestValidationError` → `400 invalid_request`, and any
  other parse failure at `:467` becomes `HTTPException(400)` → the same token. AC 9 needed no code.
* **`httpx` will not send a non-ASCII header string** (`UnicodeEncodeError` from its own ascii
  encode), so the landmine-11 test sends raw latin-1 **bytes**. Written the obvious way, that test
  never reaches the server and proves nothing.
* **The SPA bundle is byte-identical to the Task 0 baseline and to the plugin mirror** — this story
  ships no runtime frontend code, re-measured rather than assumed (AC 21).
* **Regeneration is a no-op**: `npm run gen:api` twice produces identical hashes.

**Six mutation probes, each verified on disk and reverted** (AC 26 asked for four):

| # | Mutation | Result |
| --- | --- | --- |
| A | credential comparison replaced with `return True` | **31 failed** across 3 files — the pure matrix, every wire rejection, *and* the token-leak test |
| B | fail-closed guard removed (`return presented == expected`) | **4 failed**, precisely the `None`/empty cases — including `TestFailsClosedWithNoToken[presenting no credential]`, which is the actual hole |
| C | `include_router(active_deck.router)` deleted | **40 failed** across 4 files, including `test_spa.py`'s differential list and the drift gate |
| D | `type ActiveDeckRequest = { x: 1 }` staged in `ui/src` | red, naming it: `"src/__c34probe.ts declares ActiveDeckRequest"` |
| E | `Allow` recomputation disabled | **exactly 1 failed** — AC 8's assertion, proving it is not vacuous |
| F | `forbidden` deleted from `PANEL_FOR_REASON` | **`tsc` 5 errors** (`TS1360` naming the property, `TS2344` ×2 from the classification asserts) vs **`vitest` 1** — the ratio that justifies `typecheck` being the gate for that file |

### Completion Notes List

* **All 27 ACs met.** All five open questions answered "as proposed" — fifteen of fifteen stories.
  Q2 and Q4b were the genuine forks and both took the larger option.
* **Four firsts landed:** the first backend-owned state, the first non-`GET`, the first request body
  (and so the first `requestBody` in the document), and the first authenticated endpoint — two
  stories ahead of the c5-5 that was scheduled to build the credential seam. c5-5 now inherits
  `AgentToken` rather than writing a second check.
* **The eighth reason token `forbidden` (403) shipped with its UI decision in the same commit**, per
  AD-16's pairing rule: mapped to no panel, classified in `NO_UI_RESPONSE` by name, across all
  **eight** ripple sites. `.claude/skills/**` and `plugin/skills/**` were grepped for the error
  vocabulary (c3-3's lesson) and are **clean** — every hit is the separate MCP tool status
  vocabulary (`validate_deck`'s `ok`/`deck_not_found`/`invalid`/`error`), not `ErrorReason`.
* **Q5 taken:** `test_committed_schema.py` now owns the whole-artifact path and component pins; the
  two per-route files assert only their own shapes. Both duplicated pins did go red together on
  regeneration, exactly as the deferred-work entry predicted for a third time. c3-5 edits one pin.
* **One repair beyond the story's scope, and it is disclosed as such:** the `Allow` header union
  (finding 1). It was required by AC 8, it is a correctness fix to a shipped module, and it is the
  only change in this diff that touches behaviour on paths other than `/api/active-deck` — although
  no other path's header changes, because every other path has one method.
* **Deviations from the permitted-file list, booked as made** (c3-3's standard):
  1. `src/companion/app/errors.py` — beyond "STATUS_BY_REASON only": gained `supported_methods`,
     `_leaf_routes` and the 405 branch in `http_exception_handler` (finding 1, AC 8).
  2. `src/companion/app/spa.py` — not in the source-tree list at all; docstring only, AC 20 row 6.
  3. `tests/unit/companion/test_committed_schema.py` — a new file the source tree did not name; it
     is Q5's fix shape, quoted from the deferred-work entry.
  4. `ui/tests/unknown-card-copy.test.ts` — not in the ripple table; finding 5.
  5. `tests/unit/companion/test_routes_active_deck.py` gained `code_identifiers`, a module-level
     helper the story did not anticipate (finding 3).
* **`test_state.py` was not written.** The source tree offered it "only if Q1's holder has behaviour
  worth isolating". It does not: `ActiveDeckSlot` is a single assignment behind a property, and
  every meaningful claim about it (restart forgets, the write lands, no lock is needed) is only
  true *through the wire*. A unit test of the holder would pass with the routes deleted.
* **Suite counts, measured before → after:** Python **2044 → 2136 passed** / 1 skipped (+92);
  frontend **558 → 558 passed** (29 files — assertions were added to existing tests, no new file).
  Schema **5 → 6 paths**, **9 → 11 components** (`ActiveDeck`, `ActiveDeckRequest`).
* **Every gate green**, output pasted in the Debug Log above and re-run after the last edit:
  `ruff check` (All checks passed), `ruff format --check` (300 files), `mypy src/` and
  `mypy src/ --platform win32` (88 source files, no issues), `pytest` (2136/1), and from `ui/`:
  `lint`, `format:check`, `npx tsc -b --force` (exit 0), `test` (558), `build`. Both drift gates
  green from the same tree.

### File List

**New**

- `src/companion/app/state.py`
- `src/companion/app/routes/active_deck.py`
- `tests/unit/companion/test_routes_active_deck.py`
- `tests/unit/companion/test_committed_schema.py`
- `plugin/server/src/companion/app/state.py` *(mirror)*
- `plugin/server/src/companion/app/routes/active_deck.py` *(mirror)*

**Modified — backend**

- `src/companion/contracts.py` — `ActiveDeck`, `ActiveDeckRequest`, `_MAX_DECK_ID_LENGTH`, the
  eighth `ErrorReason` and its `ErrorResponse` glass-meaning row
- `src/companion/app/security.py` — `presented_credential`, `agent_token_is_valid`,
  `require_agent_token`, `AgentToken`; module and `install_security` docstrings (AC 20 row 2)
- `src/companion/app/errors.py` — `forbidden: 403`; `supported_methods`, `_leaf_routes` and the 405
  `Allow` recomputation; `CompanionError` and `error_responses` caller lists (AC 20 row 3)
- `src/companion/app/main.py` — the slot in the lifespan, `include_router`, the ordering block
  (row 5), `agent_token`'s docstring (row 1)
- `src/companion/app/deps.py` — `DbSession` caller list: c3-4 deliberately absent (row 4)
- `src/companion/app/spa.py` — `_SpaMount`'s prediction restated with the measurement (row 6)
- `scripts/dump_openapi.py` — counts restated, c3-5 named, the pin consolidation noted (row 7)

**Modified — tests**

- `tests/unit/companion/test_errors.py` — the closed set at eight, `_EXPECTED_STATUS`
- `tests/unit/companion/test_security.py` — `TestPresentedCredential`, `TestAgentTokenIsValid`
- `tests/unit/companion/test_discovery.py` — the leak pin gains the route that reads the token
- `tests/unit/companion/test_spa.py` — the differential router list (the Q1 tax, paid)
- `tests/unit/companion/test_routes_decks.py`, `test_routes_cards.py` — reduced to their own shapes

**Modified — frontend** *(no runtime behaviour; bundle byte-identical)*

- `ui/src/api/openapi.json`, `ui/src/api/types.d.ts` — regenerated, committed together
- `ui/src/api/schema.ts`, `ui/src/api/schema.test.ts` — the count and the explicit union
- `ui/src/components/StatePanel/states.ts`, `states.test.ts` — `forbidden` mapped and classified
- `ui/tests/wire-contract.test.ts` — the two new anchors
- `ui/tests/unknown-card-copy.test.ts` — the third `NO_UI_RESPONSE` pin
- `ui/README.md` — the blind-spot row and the `Allow`-walk note

**Modified — records / mirror**

- `_bmad-output/implementation-artifacts/deferred-work.md` — Q5's entry closed; five new entries
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `plugin/server/src/companion/**` — rebuilt mirror (7 files)

### Change Log

| Date | Change |
| --- | --- |
| 2026-08-01 | **Review round 1 → `done`.** Three layers (Blind Hunter, Edge Case Hunter, Acceptance Auditor) over the working tree: 17 findings → 3 decisions (all ruled as recommended: per-include `responses=` pruning the active-deck ops' 503/413, blank-id refusal, `extra="forbid"`), 12 patches applied, 2 ledgered, 1 dismissed. Auditor: no AC violations in shipped code. Both probes run and reverted: four planted evasions all red under the rewritten stores-nothing guard, and AC 25's planted 'expected X, got Y' log leak caught by the scanner. Python 2136 → 2140, frontend 558, schema regen'd (only the two active-deck operations changed), bundle + mirror byte-identical. |
| 2026-08-01 | **Implemented → `review`.** All 5 questions as proposed (15/15 stories). The active deck ships: an in-memory slot that dies with the process, a credential-free `GET`, a token-gated `PUT`, and the eighth reason token `forbidden` at 403 with its no-panel decision in the same commit across **eight** ripple sites (the story's table named seven). Five findings, three correcting the story's own text — headline: **`POST` answered `Allow: GET`, not `GET, PUT`**, because Starlette builds the header from the first partially-matching route alone and `/api/active-deck` is the first path in this app with two methods; repaired in `errors.supported_methods`. Also: FastAPI 0.140 does not flatten included routers, so the repair walks by attribute and degrades softly; a guard of mine tripped on its own docstring (c3-3's finding in a new costume) and all four source scans were moved to the AST; `agent_token_is_valid("", "")` returned `True` and now fails closed. Q5 taken — both duplicated component pins went red together for the predicted third time and were consolidated into `test_committed_schema.py`. Six mutation probes (four asked for), all verified on disk and reverted. Python 2044 → 2136, frontend 558 unchanged, schema 5 → 6 paths / 9 → 11 components, bundle + mirror byte-identical. |
| 2026-08-01 | Story contexted off `737ce76`; 15 landmines, 27 ACs, 5 open questions (Q2 and Q4's second half are genuine forks). Headlines: this is the first backend state, the first non-`GET`, the first request body and the first authenticated route — and the authentication was scheduled for c5-5, two stories away; `agent_token(app)` returns `None` before startup, so a naive equality check is an open door; and an eighth reason token fails `tsc` on the frontend until somebody decides what it means on the glass |

### Review record — round 1 (2026-08-01, three-layer + triage)

Blind Hunter + Edge Case Hunter + Acceptance Auditor over the full working-tree diff at `737ce76`.
17 raw findings → 3 decisions (Brad ruled all three), 12 patches (all applied), 2 deferred
(ledgered), 1 dismissed. The auditor confirmed **no acceptance-criteria violations in shipped
code**; both of its record-level gaps are closed below.

**Brad's rulings (all three chosen as recommended):**

| Decision | Ruling | Landed as |
| --- | --- | --- |
| The wire declared `503`/`413` on operations that cannot produce them | **Prune per-route** | `build_app()` now declares `responses=` per **include**; DB-backed routers and `/health` keep the historical four, the active-deck include declares `invalid_request` + `internal_error` only. Schema regen'd: GET `[200,400,500]`, PUT `[200,400,403,500]`, every other path byte-unchanged |
| Whitespace-only `deck_id` accepted by `min_length=1` | **Refuse blank** | `ActiveDeckRequest._refuse_blank` field validator (`" \t "` → 400 `invalid_request` through the shipped handler; stored value still verbatim — no trim) |
| Extra fields silently dropped | **`extra="forbid"`** | `model_config = ConfigDict(extra="forbid")`; wire-visible as `additionalProperties: false` and pinned in `TestTheCommittedSchema` |

**The 12 patches, applied:** README blind-spot row rejoined to its table (it rendered as a detached
pipe paragraph) and prettier-formatted; the stores-nothing guard rewritten to ban the *family*
(both assignment node shapes + constructor calls + BinOp) and probed; the AC 25 planted-token probe
run (below); `PUT` answers from the slot rather than echoing `body`; the round-trip prose in
`contracts.py`/`state.py` now says URL-encode (an id may contain `/`); the rejection log's one word
is now three-way (`invalid`/`malformed`/`no` — a `Basic` header is no longer "no credential");
all four source-scanning guards anchored to `_REPO_ROOT` instead of the CWD; bare `data`/`deps`
dropped from the layering ban (noise trap — replaced by dotted `src.data`) and the `node.module or
""` empty-string artifact fixed; the defended unstarted-app `GET` 500 got its one measured
execution (`test_the_credential_free_read_answers_the_documented_500`); the authenticated 405 test
now asserts `Allow: GET, PUT` and the body token; the mount-prefix hole in `supported_methods`
documented in its docstring and appended to the existing ledger entry.

**Probe A — the strengthened stores-nothing guard, four planted evasions (all previously green
under the shipped version, all red now, file restored byte-identical):**

```
call-constructed set (_seen = set()):            RED (caught)
AnnAssign dict literal (_cache: dict = {}):      RED (caught)
defaultdict call (collections.defaultdict):      RED (caught)
BinOp frozenset union (frozenset() | set()):     RED (caught)
reverted; file restored byte-identical: True
```

**Probe B — AC 25's planted-token probe of the leak scan (closes the auditor's one substantive
gap).** Planted the exact temptation the test's docstring names — the rejection branch logging
"expected X, got Y" — and the scanner fired on the first record:

```
E   AssertionError: token leaked into a log message: src.companion.app.security
E   assert 'RRdD3GVYpVe...Y0lLzMvPKlPg' not in "Refusing PU...dD3GVYpVek')"
WARNING  src.companion.app.security:security.py:372 Refusing PUT /api/active-deck:
  invalid agent credential (expected 'RRdD3GVYpVek0uwO7TLGFKsmOUqn4gaY0lLzMvPKlPg',
  got 'RRdD3GVYpVek')
reverted; restored byte-identical: True
```

**AC 16, stated for the record (closes the auditor's other gap):** the first `requestBody` in the
generated TypeScript renders **non-optional** — `set_active_deck_api_active_deck_put.requestBody:`
(no `?`, `ui/src/api/types.d.ts:995`), referencing `components["schemas"]["ActiveDeckRequest"]`,
matching `test_the_request_body_is_required_and_refers_to_the_request_model`.

**Gates after patches (AC 26/27, pasted):**

```
uv run ruff check .                 → All checks passed!
uv run ruff format --check .        → 300 files already formatted
uv run mypy src                     → Success: no issues found in 88 source files
uv run pytest -q                    → 2140 passed, 1 skipped in 152.36s   (was 2136/1: +4 —
                                      whitespace + extra-field body cases, unstarted-GET 500,
                                      additionalProperties pin)
npx tsc -b --force                  → clean
npm test                            → Test Files 29 passed (29), Tests 558 passed (558)
npm run lint                        → clean (eslint + stylelint)
npm run format:check                → All matched files use Prettier code style!
npm run build                       → bundle byte-identical (git status clean on static/)
uv run python scripts/build_plugin.py → mirror rebuilt; diff -r … → MIRROR IDENTICAL
```

**Regenerated schema, per-operation declared statuses (the D1 verification):**

```
/health GET                          [200, 400, 413, 500, 503]   (unchanged)
/api/decks GET                       [200, 400, 413, 500, 503]   (unchanged)
/api/deck/{deck_id} GET              [200, 400, 404, 413, 500, 503] (unchanged)
/api/deck/{deck_id}/format-check GET [200, 400, 404, 413, 500, 503] (unchanged)
/api/cards/{card_id} GET             [200, 400, 404, 413, 500, 503] (unchanged)
/api/active-deck GET                 [200, 400, 500]
/api/active-deck PUT                 [200, 400, 403, 500]
```

**Deferred (both in `deferred-work.md` under "code review of c3-4"):** the pre-auth body-buffering
entry gains the note that `test_a_malformed_body_without_a_credential_is_still_forbidden` *pins*
the ordering, so c5-5 must rule pin-as-contract vs pin-as-snapshot; and the hand-raised-405
header-override/case-split latency, homed on the first story that raises a 405 manually.
**Dismissed (1):** the recompute *replacing* an author's `Allow` — that is the repair working as
designed.
