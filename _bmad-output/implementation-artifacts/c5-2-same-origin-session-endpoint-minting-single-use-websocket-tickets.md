---
epic: c5
story: c5-2
work_branch: feat/companion-c5
story_branch: feat/companion-c5-2-session-endpoint-and-ws-tickets
depends_on: >-
  c1-4 (merged) — the typed REST error contract, the closed ten-token `ErrorReason` set and
  `error_responses(...)`. This story adds **no** token; see AC 12. c1-5 (merged) — the
  `HostValidationMiddleware` this endpoint inherits for free, the deliberate **no-CORS** ruling, and
  the `Origin`-on-REST open question homed **on this story by name** (`c1-5:357-358`, `:625-631`).
  c1-7 (merged) — the discovery file and `mint_token()`, which this story must **not** reuse.
  c3-4 (merged) — `ActiveDeckSlot`, `state.py`, the module-accessor idiom, and the two AD-5
  structural guards at `test_routes_active_deck.py:724-786` that were written pointing at this
  story. c3-6/c3-7 (merged) — `Pacer` and `NegativeCache`: the injected-monotonic-clock idiom and
  the `FakeClock` fixture that make a 30 s TTL testable without spending 30 seconds. c2-3 (merged) —
  the OpenAPI → TypeScript pipeline. c5-1 (merged, PR #53) — `contracts.py` as it now stands, and
  the probe harness this story's new guards must be proven through.
baseline_commit: 2df2461
---

# Story C5.2: Same-origin session endpoint minting single-use WebSocket tickets

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As the browser UI,
I want a short-lived ticket before I open a socket,
so that the WebSocket upgrade is authenticated by something CORS alone cannot protect.

**✅ BRANCH PRECONDITION — CLEAN.** `feat/companion-c5` is at `2df2461`; working tree clean, plugin
mirror sha256-identical on all four files this story touches (all verified 2026-08-08). Cut
`feat/companion-c5-2-session-endpoint-and-ws-tickets` from `2df2461`. Verify with
`git log --oneline -1 origin/feat/companion-c5` **before** `checkout -b`, not after.

**What this story really is.** About 120 lines: one holder class with a TTL, one 8-line route, one
response model, one lifespan line. And then four things that are not.

---

1. **THE SHIPPED CODE ALREADY TELLS YOU WHERE THIS GOES — IN TWO PLACES THAT DISAGREE.**
   `state.py:18` says *"c5-2's WebSocket tickets … join this module rather than inventing a third
   home."* `security.py:16` says *"c5-2's WebSocket ticket is the third member and **joins here**."*
   Both are forward-looking claims written by earlier stories from the spine's own module map, which
   splits it — `state.py # active deck, connections, tickets — in memory` and
   `security.py # Host validation, token, ticket mint/consume` (`ARCHITECTURE-SPINE:448-449`). A
   single-use consume is a **compare-and-set over the storage**, so the split cannot survive
   contact: whichever module holds the dict holds the consume. **One of those two shipped docstrings
   becomes false in this story and must be corrected in the same commit** — that is c3-9's rule, and
   c5-1 discharged the identical obligation against `dump_openapi.py:133`. See **Q3**; the
   recommendation is `state.py`, and the reason is item 2.

2. **TWO STRUCTURAL GUARDS WERE WRITTEN AIMED AT THIS STORY, AND ONE OF THEM BANS THE WORD
   `ticket`.** `test_routes_active_deck.py:724-735` AST-walks `state.py` and asserts
   `{"token","agent_token","credential","secret","mint_token","ticket"} & identifiers == ∅`. Its own
   docstring says it exists *"so c5-2 inherits a rule rather than a coincidence."* A `TicketStore` in
   `state.py` with a `consume(ticket)` parameter **reds it on the identifier `ticket`**. Its sibling
   at `:737-786` asserts `security.py` holds **no module-level mutable container at all** — probed
   against four planted violations — so a ticket dict cannot live at `security.py` module level
   either. Neither guard may be silently deleted (C4 retro action item 13: *review-added mechanisms
   re-enter review*). AC 14–16 replace the crude name-ban with an assertion that survives a
   legitimate ticket store while still proving AD-5's real property.

3. **THIS STORY PRODUCES A REAL SCHEMA DIFF — THE INVERSE OF c5-1.** c5-1's headline was a confirmed
   negative: sixteen new models, zero schema change, because a model no route references never
   reaches `components.schemas`. c5-2 puts its model on a route, so it lands. **7 paths → 8, 12
   components → 13**, and both `ui/src/api/openapi.json` and `ui/src/api/types.d.ts` must be
   regenerated and committed. Three pins go red on purpose:
   `test_committed_schema.py:66-81` (paths), `:187-207` (components), and `test_spa.py:315-319`'s
   hand-mirrored router list — the last being the ledgered router tax that names **c5-2** by key
   (`deferred-work.md:1905-1930`).

4. **"SAME-ORIGIN" IS IN THE STORY TITLE AND NOTHING IN THIS CODEBASE ENFORCES IT.** c1-5 installs
   **no `CORSMiddleware` at all** — deliberately, ruled at AC 9 / Decide-once #3, pinned by
   `test_security.py::TestCorsIsDeliberatelyAbsent`, on the reasoning that AD-13 serves the SPA from
   this same backend so the empty grant *is* "restricted to the app's own origin". And AD-5 homes
   `Origin` validation **on the upgrade only** (c5-3), which is where review finding S-6 put it
   (`review-adversarial-seam.md:84-88`). So a malicious local page **can** issue
   `GET /api/session` today; it cannot read the response (no `ACAO`), so it cannot steal a ticket —
   it can only burn them. c1-5 flagged this and homed the ruling **on this story by name**. **Q1 is
   the one question that must be answered before code is written.**

---

## Dev Notes

### Task 0 — verify before writing code, do not believe this file

Measured on `2df2461`, 2026-08-08. Re-run every line; a mismatch is a finding, not a rounding error.

| Fact | Measured value | Command |
|---|---|---|
| Python tests | **2,551 collected / 54 deselected** (2,605 total) | `uv run pytest --collect-only -q -m "not integration" \| tail -1` |
| Frontend tests | **1,694 passed / 65 files** (inherited, re-measure) | `cd ui && npx vitest run` |
| OpenAPI schema | **12 components, 7 paths** | `python -c` over `ui/src/api/openapi.json` |
| `gen:api` at baseline | expect a **clean no-op** | `cd ui && npm run gen:api` then `git status --porcelain` |
| Plugin mirror | **sha256-identical** on `contracts.py`, `app/{state,security,main}.py` | `shasum -a 256 src/companion/X plugin/server/src/companion/X` |
| `ui/node_modules` | **PRESENT** (376 entries) — changed since c5-1, which measured it absent | `test -d ui/node_modules` |
| Local Node | **v25.8.1**; CI pins **20**, `engines.node >=20.19.0` | `node --version` |

⚠️ Local Node is five majors above the CI floor. Codegen is version-insensitive, but **do not run
`npm install` or let `package-lock.json` move** — `@types/node` and `@testing-library/jest-dom` are
pinned against the floor on purpose (`ui/package.json:31,34`), and a moved lockfile reds `npm ci`.

**Grep your own key (C4 retro action item 6) — run 2026-08-08, 8 hits, every one an obligation:**

```
src/companion/app/security.py:16   "c5-2's WebSocket ticket is the third member and joins here"
src/companion/app/security.py:420  "still to come and is genuinely middleware-shaped"
src/companion/app/state.py:18      "c5-2's WebSocket tickets … join this module"
src/companion/app/main.py:503      "c5-2 and c5-5 add their pieces inside install_security, not here"
src/companion/app/main.py:510      "c5-2 and c5-5 add theirs there too" (the router include)
src/companion/app/spa.py:375       "c3-1, c5-2 and c5-5 all add [routes above the mount]"
tests/unit/companion/test_routes_active_deck.py:727,729  the guard aimed at this story
```

Three are **predictions this story falsifies** and must be corrected, not worked around:

- `security.py:420` — *"genuinely middleware-shaped (it gates a handshake, not an endpoint), so this
  remains the one wiring call and `build_app()` never grows a second security line."* Half right:
  the **consume** gates a handshake (c5-3), but the **mint** is an endpoint, and `build_app()` does
  grow a line — an `include_router`, not a security line.
- `main.py:503` — *"c5-2 and c5-5 add their pieces inside `install_security`, not here."* c5-2 adds
  a router include at ~`main.py:495`, above `install_spa`. c5-3 is the story that line was really
  describing.
- `state.py:18` or `security.py:16` — whichever loses **Q3**.

These are `#` comments and module/class docstrings in non-wire positions, so correcting them costs
**zero** regeneration diff (c3-9's measured rule). `spa.py:375` and `main.py:510` are already
correct and need no edit.

### Where each piece goes — the shape to build

| Piece | File | Why |
|---|---|---|
| `SessionTicket` response model | `src/companion/contracts.py` | AD-3 leaf: stdlib + `pydantic` + `httpx` + `src.paths` only. Every route response model lives here (`routes/__init__.py:1-7`). |
| `TicketStore` holder | `src/companion/app/state.py` (**Q3**) | Spine names `state.py` for in-memory tickets. Inert, construction cannot fail, created by the lifespan. |
| accessor `ticket_store(app)` | same module as the holder | One `getattr(app.state, …, None)` into an **annotated local** — the `warn_return_any` idiom repeated verbatim at `state.py:105-107`, `deps.py:230-232`, `main.py:246-248`. |
| lifespan line | `src/companion/app/main.py` beside `:203` | AD-10: `build_app()` has zero side effects; everything external belongs to the lifespan. A dict + a clock cannot fail, so it is a plain assignment and adds **nothing** to `_shutdown`. |
| `GET /api/session` route | new `src/companion/app/routes/session.py` | New router. Copy `routes/health.py` (28 lines) for shape and `routes/active_deck.py` for a route with an in-memory holder and no database. |
| router include | `main.py`, above `install_spa(app)` | `install_spa` **must stay last** (`main.py:507-534`); `spa.py:59` already reserves the `api` prefix. |

### The house idiom — follow it, do not invent

**The holder.** `ActiveDeckSlot` (`state.py:38-88`) and `NegativeCache` (`images.py:1391-1635`) are
the two precedents; the ticket store is `NegativeCache`'s shape with `ActiveDeckSlot`'s wiring.

- Bare `class`, no dataclass; `__init__` keyword-only with defaults drawn from **module-level named
  constants**, each with its own docstring. Private storage `self._…`; read-only `@property` where a
  test needs to see inside (`NegativeCache.entry_count`, `images.py:1491-1500`, exists *only* so a
  test can tell pruning from ignoring — you need the same).
- **`clock: Callable[[], float] = time.monotonic`, injected.** Non-negotiable and already ruled at
  `images.py:1448-1453`: *"**Monotonic, never** `time.time`: a wall clock steps backwards on an NTP
  correction and across a DST boundary."* The route never passes it; only tests do.
  (`contracts.py`'s `datetime.now(UTC)` is for a **wire timestamp**, a different job — do not borrow
  it for expiry.)
- **Prune on insert, not on read** (`images.py:1586-1618`), and take **one clock reading per public
  call**, passing `now` down — `record_failure` does this at `:1547` explicitly *"so one call cannot
  straddle two readings"*.
- **Make the expiry boundary half-open and assert both sides of it.** `is_backing_off` spells it
  `self._clock() < remembered.retry_after` and the tests pin at-boundary and past-boundary
  separately (`images.py:1512-1513`).
- **Raise `ValueError` on a nonsense injected parameter** (`images.py:1477-1480`) — a guard against a
  mis-injected test value, not a startup risk, since the lifespan constructs with no arguments.

**The route.** `@router.get("/session", response_model=SessionTicket, responses=…)` on a
`router = APIRouter(prefix="/api")`. **No `status_code=`, no `summary=`, no `tags=`, no
`operation_id=`** — zero occurrences of any of them across all four shipped route modules; the
summary comes from the handler docstring. Reach the holder through a module-private `_store(request)`
helper with a **deliberately unguarded** `AttributeError`, exactly as `_slot` does at
`routes/active_deck.py:42-64`: a missing holder can only mean the lifespan never ran, and
`500 internal_error` is the right answer.

**Docstring truncation is load-bearing.** `_CompanionFastAPI.openapi()` cuts every description at
the first Google-style section header (`main.py:294-315`; `Note:`/`Warning:` deliberately survive).
Everything **above** `Args:` ships into `/docs` and `types.d.ts`; everything below is repo-internal.
Put the TTL and single-use semantics **above** it — a client author needs them. Put story ids and
`deferred-work.md` pointers **below** it. `routes/active_deck.py:116-121` is the worked precedent,
and it makes exactly this argument about a credential.

**Never `HTTPBearer` / `APIKeyHeader` / `Annotated[str, Header()]`.** c3-4's Q4 ruling
(`security.py:213-229`): a security class adds a `securitySchemes` component and reds
`test_committed_schema.py:218-224`, and raises its own `HTTPException` bypassing the typed contract.
Not that c5-2 needs one — the mint is credential-free — but c5-3 will read this module.

### AD-5, stated as the property the code must have

> The **agent token** lives in the discovery file, authorises `POST /agent/events`, and **never
> reaches the browser** — no HTML embed, no REST response, no WS frame. The **WS ticket** is minted
> by same-origin `GET /api/session`, is **single-use with a 30 s TTL**, and is consumed and destroyed
> at the WebSocket upgrade; every reconnect attempt mints a fresh one. **The two share no storage and
> no code path.** — `ARCHITECTURE-SPINE:150-154`

Concretely, "sharing a code path" here means any of: calling `discovery.mint_token()`; reading
`main.agent_token(app)` or `app.state.agent_token`; routing ticket validation through
`presented_credential` / `agent_token_is_valid` / `require_agent_token` / the `AgentToken`
annotation; reusing `_AUTHORIZATION_HEADER` or the `Bearer` channel; or writing the ticket anywhere
`write_discovery` reaches. Mint with your **own** `secrets.token_urlsafe(...)` call under your own
constant. (`import secrets` is safe against the `state.py` name-ban: the identifiers it contributes
are `secrets` and `token_urlsafe`, neither of which is in the banned set — the collision is on the
word `ticket`, see AC 14.)

### No UX surface, and no new libraries

**Nothing in the UX artefacts mentions the ticket, the TTL, or a session-endpoint failure.** The
only line touching this endpoint is `EXPERIENCE.md:118` — *"on reconnect, re-mint the ticket via
`GET /api/session`"* — and that is **c5-6's** behaviour, not this story's. The connection pill reads
`/health` for port and instance id (`EXPERIENCE.md:97`), never `/api/session`. So: **do not invent a
state panel, a banner or a copy string.** Ticket churn is designed to be invisible, which is also
why AC 12 adds no `ErrorReason` token — AD-16's rule is that a token exists to drive a UI state, and
there is no state here to drive.

**No new dependency, and no version research is owed.** Everything this story needs is already
pinned and in use: `secrets` and `time` from the stdlib, `pydantic` v2 and FastAPI via the existing
`_CompanionFastAPI`, `openapi-typescript@7.13.0` in `ui/node_modules`. If you find yourself reaching
for a library, you have left the shape described above.

### The generated artefacts — a real diff this time

One command does both halves: `cd ui && npm run gen:api` (`ui/package.json:19`) →
`uv run python -m scripts.dump_openapi` then `openapi-typescript`. **Commit both**
`ui/src/api/openapi.json` and `ui/src/api/types.d.ts`; both are in `ui/.prettierignore` and must
never be hand-edited. `test_openapi_contract.py:151-167` compares **bytes**.

Three pins to edit, and each will go red first — that red is the mechanism working:

| Pin | Current | After |
|---|---|---|
| `test_committed_schema.py:73-81` | 7 paths | + `/api/session` (**8**); update the "SEVEN as of c3-5" comment |
| `test_committed_schema.py:194-207` | 12 components | + `SessionTicket` (**13**); update the "TWELVE as of c3-5" comment |
| `test_spa.py:315-319` | 4 routers | + `without_spa.include_router(session.router)` |

`scripts/dump_openapi.py:19-141` is the running ledger of what each schema-changing story did to
these counts — append yours, and note the docstring convention that a `#` comment near a wire model
costs no diff (`:88-94`).

### Inherited deferrals — R1 trigger-gated

**TRIGGERED (3)**

1. **The router tax** — `deferred-work.md:1905-1930`. *"Every future router-adding story (**c5-2**,
   c5-5 …) must add one line there or get a red."* The tax is on adding a **router**, not a route
   (`test_spa.py:306-314`). `routes/session.py` is a new router ⇒ you owe the line. Covered by AC 22.
2. **A body-less `GET` publishes an unreachable `413`** — `deferred-work.md:2324-2340`, homed on
   c5-5, *"doubled by every new GET route."* Do **not** put `payload_too_large` in this router's
   `error_responses(...)`; c3-4 set the precedent at `main.py:495-497` (*"declaring either here would
   promise a `types.d.ts` consumer a branch that can never answer"*). Record the disposition so c5-5
   does not re-litigate. Covered by AC 12.
3. **`Origin` on REST** — `c1-5:357-358`, `:625-631`, homed on **c5-2 and c5-3**. This is **Q1**, and
   it is the only one that gates writing code.

**NOT TRIGGERED (5)** — one line each, ledger anchor only:

- Pre-parse request-body cap (`deferred-work.md:2586-2601`) — home c5-5; a body-less `GET`.
- Body-parsed-before-auth ordering (`:2660-2666`) — home c5-5; credential-free `GET`.
- `errors.supported_methods` under a non-root `Mount` (`:2626-2643`) — home is *the story that adds a
  non-root mount*. c5-2 adds a **router**, not a `Mount`. Confirm in the record.
- The vitest half of the probe harness (c5-1 §) — home *the first C5 story that plants a frontend
  guard*, i.e. c5-6. c5-2 regenerates `ui/src/api/*` but plants no frontend guard.
- `tsc -b` cross-project import cascade / T2 (`:2144-2169`) — re-homed by c5-1 to c5-5/c6-x; fires
  only if `ui/tests` imports an app module with relative imports of its own. c5-2 adds no `ui/tests`.

**DON'T-BREAK (5)** — scoped to this diff's own files:

- `test_routes_active_deck.py:724-735` and `:737-786` — the two AD-5 guards. See AC 14–16.
- `test_security.py::TestCorsIsDeliberatelyAbsent` — three assertions. **Do not add CORS** (Q1).
- `test_committed_schema.py:218-224` — no `securitySchemes` component.
- `test_committed_schema.py:275-279` — the active-deck routes declare **no `503` at all**. Mirror the
  ruling for `/api/session`: no database dependency, so no `503` to promise, and it must **not** join
  `TestTheDatabaseTokensAreDeclared.DATABASE_BACKED`.
- `test_import_boundary.py:536-552` — a new top-level `src/companion/*.py` is an immediate red.
  Everything new goes under `app/`, or into the existing `contracts.py` leaf.

⚠️ **The AD-1 construction-limit guard.** `test_routes_format_check.py:645` bans the bare literals
`{60, 15}` **anywhere** in any `src/companion/**` file, in any position — it has now fired twice
unpredicted (c3-6's `FETCH_CONCURRENCY = 4`, c5-1's `_MAX_ITEMS = 60`). `30` is **safe**: it is not
in the set, and `images.py:303` already ships `NEGATIVE_CACHE_BASE_SECONDS = 30.0` green under the
same scan. But `_LIMIT_FAMILY_EXEMPT` (`:686-688`) names **only `contracts.py`** — so a store cap of
`60`, a sweep interval of `15`, or any other `60`/`15` in `state.py`, `security.py` or
`routes/session.py` **will** red it. Pick other numbers.

### Testing standards

`asyncio_mode = "auto"` — bare `async def test_…`, no `@pytest.mark.asyncio`. Test files mirror
`src/`: **new `tests/unit/companion/test_routes_session.py`**, plus the ticket-store unit tests
(same file, or a new `test_state.py` if the store lands there). `tests/integration/companion/` does
not exist and this story does not create it — the one real-socket test is **c5-8** (AD-10).

- **Client:** the `lifespan_client` fixture (`conftest.py:162-172`), `httpx.ASGITransport`, no
  socket. It stamps `app.state.bound_port = 54321` and derives `base_url` from it
  (`conftest.py:45-51`), so **every test flows through the real `Host` envelope** rather than around
  it — which is how AC 5 gets proven for free.
- **The 30-second TTL costs zero wall clock.** `FakeClock` (`conftest.py:483-535`) is the house
  answer. For unit tests inject `clock=clock.time` directly; for a route-level test monkeypatch the
  **constructor** so the lifespan builds a clock-injected instance —
  `test_routes_card_image.py:1946` and `:2258` are the worked pattern
  (`lambda **kwargs: real(clock=clock.time, **kwargs)`). **A test that sleeps is a defect.**
- **Assert through the wire, never through `app.state`** — `test_routes_active_deck.py:14-15`: *"a
  test that inspected `app.state.active_deck` would pass with the routes deleted."*
- **Every rejection is paired with an acceptance from the same call** (non-vacuity): fresh ticket
  accepted / consumed ticket rejected; at-TTL accepted / past-TTL rejected; unknown ticket rejected.
- **Compare sets, never counts** (`test_errors.py:282`). Classes are `Test*` with a docstring naming
  **the AC and the AD**.
- **Doctests run.** Any `Example:` block you write must be executed — c5-1 folded
  `doctest.testmod(module)` into an ordinary test (`test_contracts.py:661-673`) because `testpaths`
  is scoped to `tests/`. Note `state.py:57-59` and `security.py:97,116` already carry `Example:`
  blocks that **nothing currently runs**; wiring yours is enough, widening to theirs is optional and
  should be a stated decision either way.
- **R2 — every new guard ships a firing proof.** Plant the violation and show it **RED through the
  full suite** via `uv run python -m scripts.probe_harness --expect-red '<node::id>'`, then revert.
  Plus one line per guard stating what the assertion actually compares (read against the code, not
  its own comment) and what it cannot see. The harness owns its argv so a run cannot be narrowed, and
  it refuses to score a run that did not complete — it caught exactly that lie in its own proof run
  at c5-1.

### Source tree — what this story touches

```
src/companion/contracts.py                    UPDATE  + SessionTicket
src/companion/app/state.py                    UPDATE  + TicketStore + ticket_store() (Q3)
src/companion/app/security.py                 UPDATE  docstring correction (:16 or :420)
src/companion/app/main.py                     UPDATE  import, lifespan line, include_router, :503 comment
src/companion/app/routes/session.py           NEW     GET /api/session
tests/unit/companion/test_routes_session.py   NEW     route + store behaviour
tests/unit/companion/test_routes_active_deck.py UPDATE the two AD-5 guards (AC 14-16)
tests/unit/companion/test_committed_schema.py UPDATE  7→8 paths, 12→13 components
tests/unit/companion/test_spa.py              UPDATE  + session.router in the differential list
ui/src/api/openapi.json                       REGEN   commit
ui/src/api/types.d.ts                         REGEN   commit
plugin/server/**                              REGEN   uv run python -m scripts.build_plugin
scripts/dump_openapi.py                       UPDATE  append this story to the running ledger
_bmad-output/implementation-artifacts/deferred-work.md  UPDATE  same commit as any re-homing
```

### References

- [ARCHITECTURE-SPINE.md](../planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md) — AD-5 (`:143-157`), AD-4 (`:127-141`), AD-10 (`:227-240`), AD-12 (`:272-290`), AD-16 (`:329-352`), CM-3 (`:360`), module map (`:438-475`)
- [epics-companion-app.md](../planning-artifacts/epics-companion-app.md) — Story 5.2 (`:2417-2448`), 5.3 (`:2450-2477`), 5.6 (`:2545-2576`), 5.8 (`:2611-2644`), NFR-01 (`:137-142`), AD-5 inventory bullet (`:246-249`)
- [prd.md](../planning-artifacts/prds/prd-Artificial-Planeswalker-2026-07-22/prd.md) — NFR-01 (`:160`), NFR-04 (`:163`), CM-3 (`:193-195`); [addendum.md](../planning-artifacts/prds/prd-Artificial-Planeswalker-2026-07-22/addendum.md) `:87-88` — the delegated ticket-lifecycle item, discharged by AD-5
- [review-adversarial-seam.md](../planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/reviews/review-adversarial-seam.md) `:84-88` — S-6, the finding that put `Origin` on the upgrade
- [review-edge-case-hunter.md](../planning-artifacts/prds/prd-Artificial-Planeswalker-2026-07-22/review-edge-case-hunter.md) `:123-126` — EC-19; note its mint-then-expire-mid-handshake clause is **client-side and still open at c5-6**
- [c1-5 story record](c1-5-localhost-only-security-envelope-host-validation-and-cors.md) `:340-358`, `:625-635` — the Host/Origin split and the two open questions homed here
- [c3-4 story record](c3-4-the-active-deck-readable-by-the-glass-settable-by-the-agent.md) — `ActiveDeckSlot`, the no-lock ruling, the router tax
- [deferred-work.md](deferred-work.md) `:1905-1930`, `:2324-2340`, `:2586-2601`, `:2626-2643`
- [project-context.md](../project-context.md) — `%`-style lazy logging, ruff/mypy strict, Google docstrings, function-local imports for real cycles

---

## Acceptance Criteria

### The endpoint

1. `GET /api/session` exists on a **new** `APIRouter(prefix="/api")` in
   `src/companion/app/routes/session.py`, included in `build_app()` **above** `install_spa(app)`, and
   answers `200` with a freshly minted ticket. (NFR-01, AD-5)
2. Each call mints a **distinct** ticket — two consecutive calls never return the same value, and the
   value is generated by this story's own `secrets.token_urlsafe(...)` call, **not** by
   `discovery.mint_token()`. (AD-5)
3. The response model is a named Pydantic model in `src/companion/contracts.py` used as
   `response_model=`, so it reaches `components.schemas`. No inline dict, no hand-built shape.
   (AD-12, `test_errors.py:832`)
4. The endpoint requires **no credential** — the browser holds none and never will (AD-5), the same
   ruling `GET /api/active-deck` already ships under.
5. A request with a `Host` header outside `127.0.0.1:{port}` / `localhost:{port}` is refused by the
   inherited `HostValidationMiddleware` with `400 invalid_request` — asserted, not assumed, and
   asserted **without** duplicating the check in this route. (c1-5, AD-5)

### The ticket lifecycle

6. A ticket is **single-use**: the first `consume` of a valid, unexpired ticket succeeds; the second
   consume of that same ticket fails. Destruction happens **at consume**, not at some later sweep.
   (AD-5)
7. A ticket expires **30 seconds** after minting. The boundary is half-open and both sides are
   pinned: at exactly the TTL the ticket is still valid *or* already expired — pick one, state it in
   the docstring, and assert **both** sides of the line. (AD-5, `images.py:1512-1513`)
8. An expired ticket is rejected by `consume`, and an unknown ticket is rejected — with a fresh
   ticket accepted in the same test as the non-vacuity pair.
9. Expired entries are actually **removed** from the store, not merely ignored on read. Proven
   through a read-only size property, the way `NegativeCache.entry_count` exists solely to make this
   distinguishable. (`images.py:1491-1500`)
10. The store is bounded (**Q2**), and the eviction policy is stated in the class docstring with its
    cost — an unauthenticated mint endpoint is unbounded-callable by any local page.
11. The store holds tickets **in process memory only**: nothing is written to disk, to
    `companion.json`, or to any cache. A restart begins with an empty store, and the store is created
    by the **lifespan** (not `build_app()`, not at import), so `build_app()` keeps its zero-side-effect
    property. (CM-3, AD-10)

### The two credentials that never touch (AD-5)

12. This story adds **no** new `ErrorReason` token — the set stays closed at ten. The router's
    `error_responses(...)` declares `invalid_request` and `internal_error` only: **no `503`** (no
    database) and **no `413`** (no body).
13. The agent token appears **nowhere** in this response, in any HTML, or in any log line this story
    writes. Asserted positively over a real response and real captured logs, in the shape
    `test_routes_active_deck.py:788-814` uses.
14. `test_routes_active_deck.py:724-735` is **updated, not deleted**. The identifier `ticket` leaves
    the ban list because a ticket store legitimately uses the word; the agent-token-specific names
    (`agent_token`, `mint_token`, `credential`, `secret`, `token`) stay. The AC-13 docstring is
    rewritten to describe what the guard now proves.
15. The coverage lost from AC 14 is replaced by a stronger assertion in the same class: the module
    holding the ticket store **never imports `src.companion.discovery`**, never references
    `agent_token` / `app.state.agent_token`, and never calls `presented_credential`,
    `agent_token_is_valid` or `require_agent_token` — i.e. AD-5's "no shared code path" asserted
    structurally rather than by banning a noun. Non-vacuity: the same walk finds the ticket store's
    own identifiers.
16. `test_routes_active_deck.py:737-786` (`security.py` holds no module-level mutable container)
    **still passes unchanged**. If Q3 lands the store in `security.py`, it lands as an *instance*
    reached through one accessor, and the guard is extended to prove that rather than weakened.
17. Whichever of `state.py:18` / `security.py:16` Q3 falsifies is **corrected in this commit**, along
    with `security.py:420` and `main.py:503`. Each correction is verified to produce **no** schema
    diff (c3-9's rule).

### Locking, argued rather than assumed

18. `state.py:25-32` rules that a compare-and-set is *"the change that earns a lock, and it should
    say so at the same time."* A single-use consume **is** a compare-and-set. Either take a lock, or
    write down why `dict.pop(key, None)` with no `await` between the read and the delete is atomic on
    single-threaded asyncio — and amend that paragraph either way so the next author reads a decision
    rather than an omission.

### Cache semantics

19. The `200` carries `Cache-Control: no-store` (**Q5**), or the decision not to is written down. A
    single-use credential that a browser, an extension or an intermediary may store is a
    single-use credential in name only. Note only `error_response` sets `no-store` today
    (`errors.py:161`); this would be the first success path to do so, so it needs a ruling, not a
    reflex.

### The generated artefacts — a real diff

20. `cd ui && npm run gen:api` is run and **both** `ui/src/api/openapi.json` and
    `ui/src/api/types.d.ts` are regenerated and committed. `git status --porcelain -- ui/src/api/` is
    clean afterwards.
21. `test_committed_schema.py`'s two whole-artifact pins are updated in place — **8** paths, **13**
    components — including their "SEVEN/TWELVE as of c3-5" comments, and nowhere else.
22. `test_spa.py:315-319`'s differential router list gains `session.router`. The red it produces
    first is recorded in the Debug Log as evidence the mechanism fired.
    (`deferred-work.md:1905-1930`)
23. `/api/session` declares **no `503`** and does not join
    `TestTheDatabaseTokensAreDeclared.DATABASE_BACKED`; a per-route pin asserts it, mirroring
    `test_committed_schema.py:275-279`.
24. `scripts/dump_openapi.py`'s running ledger gains this story's measured before/after.

### Tests, record and gates

25. New `tests/unit/companion/test_routes_session.py`. Every test is in-process over
    `httpx.ASGITransport` via `lifespan_client`; **no test sleeps**, and the TTL is proven with
    `FakeClock`. (AD-10)
26. Every new guard is proven RED through the **full** suite via `scripts/probe_harness.py`, with the
    planted violation and the harness output pasted into the Debug Log, plus one line per guard
    saying what it actually compares and what it cannot see. (C4 retro R2)
27. Any `Example:` block added ships under a test that runs it (`doctest.testmod`), following
    `test_contracts.py:661-673`.
28. `uv run python -m scripts.build_plugin` is run and `plugin/` committed, verified by
    `shasum -a 256` on **every** file this story touched — and re-verified after any later edit. c5-1
    shipped a sha256-match claim that all three review layers independently falsified; do not repeat
    it. (Note: the `build-plugin-sync` hook is **not installed on this machine**.)
29. All gates green and pasted: `uv run ruff check .` · `ruff format --check .` · `mypy src/` ·
    `mypy src/ --platform win32` · `uv run pytest -m "not integration"` · and in `ui/`:
    `npm run lint` · `format:check` · **`typecheck`** · `test` · `build`. `npm run typecheck` is the
    real gate for `ui/src/api/*` — `expectTypeOf` erases at runtime, so `npm test` can be green while
    `tsc -b` exits 2.
30. Dev Notes self-check reported in KB against C4's 41 KB average, with the disposition of every
    triggered/not-triggered item accounted for. (R1)

---

## Tasks / Subtasks

- [x] **Task 0 — verify the baseline** (AC: all)
  - [x] Confirm `origin/feat/companion-c5` is at `2df2461`, then cut the story branch
  - [x] Re-run every row of the Task 0 table; report mismatches as findings
  - [x] Re-run the `c5-2` key grep; confirm the 8 hits and the 3 falsified predictions
- [x] **Task 1 — answer the blocking questions** (AC: 1, 5, 10, 17, 19)
  - [x] **Q1** (`Origin` on the mint) before any code · **Q3** (module) · **Q2**, **Q4**, **Q5**
- [x] **Task 2 — the ticket store** (AC: 2, 6–11, 18)
  - [x] `TicketStore` with injected monotonic clock, named constants, bound, prune-on-insert
  - [x] `mint()` / `consume()` / size property; `ValueError` on nonsense injected params
  - [x] Accessor + lifespan line beside `main.py:203`; nothing added to `_shutdown`
  - [x] Amend `state.py:25-32`'s lock paragraph with the ruling
- [x] **Task 3 — the wire model and the route** (AC: 1, 3, 4, 12, 19)
  - [x] `SessionTicket` in `contracts.py`; leaf imports only
  - [x] `routes/session.py` copying `health.py`'s shape and `active_deck.py`'s `_slot` helper
  - [x] `include_router` above `install_spa`; correct `main.py:503`
- [x] **Task 4 — the AD-5 guards** (AC: 13–17)
  - [x] Update `test_routes_active_deck.py:724-735`; add the structural no-shared-code-path assertion
  - [x] Confirm `:737-786` still passes unchanged; correct the falsified docstrings
- [x] **Task 5 — tests** (AC: 5–9, 13, 25, 27)
  - [x] `test_routes_session.py`: mint, distinctness, Host rejection, no-credential, no token leak
  - [x] Store tests with `FakeClock`: single-use, TTL both sides, unknown, pruning, bound
  - [x] Per-route committed-schema pins (AC 23)
- [x] **Task 6 — the generated artefacts** (AC: 20–24)
  - [x] Watch the three pins go red, then update them; record the reds
  - [x] `npm run gen:api`; commit both files; append to `dump_openapi.py`'s ledger
- [x] **Task 7 — proofs, mirror, gates, record** (AC: 26, 28–30)
  - [x] Probe every new guard RED through the full suite; paste output
  - [x] `build_plugin` + `shasum` verification, **after** the last edit
  - [x] All Python and frontend gates; ledger entries in `deferred-work.md` in the same commit
  - [x] Dev Notes KB self-check

### Review Findings

<!-- Code review 2026-08-08: three layers (Blind Hunter, Edge Case Hunter, Acceptance Auditor), all completed. 16 raw findings, 1 merged duplicate, 3 dismissed as noise. -->

**All 10 patches applied 2026-08-08** (the decision resolved as a patch): TTL number stripped from
the wire description and both generated artifacts regenerated (`openapi.json` +
`types.d.ts` no longer carry "30 seconds"); eviction prose now states the repeatable-flood bound
honestly; test-module docstring declares its two forced store-read exceptions; eviction policy
added to the `TicketStore` class docstring (AC 10 literal placement met); `math.isfinite` guard
with NaN/inf tests (+2, suite 2,594 → 2,596); `resident_count` docstring warns resident ≠ live;
no-lock argument keeps only the suspension-point reasoning; Host/Origin scan strips all docstrings
via AST; `_store`'s "unguarded" claim corrected; route TTL test moved strictly past the boundary.
Gates: full suite 2,596 passed / 54 deselected; `mypy src/` clean; ruff clean; frontend typecheck
clean, 1,694 tests passed; plugin mirror rebuilt and sha256-verified on all five files after the
last edit.

- [x] [Review][Decision] **RESOLVED (Brad, 2026-08-08): option (a) — reword and regenerate.** The TTL is published on the wire, contradicting Q4's "deliberately unpublished" ruling — `SessionTicket`'s docstring leading paragraph ("expires **30 seconds** after it was issued", `src/companion/contracts.py:293-295`) ships in `components.schemas.SessionTicket.description` (verified in the committed `ui/src/api/openapi.json`). Q4 is honoured for the *field* but violated as a prose wire commitment: a client author reading the generated types will treat 30 s as contract, and changing `TICKET_TTL_SECONDS` silently breaks a published number. Options: (a) reword the leading paragraph to "within seconds"/"short-lived" and regenerate both artefacts, or (b) rule the prose mention acceptable and amend Q4's record to say the *number* may appear as guidance while the *field* stays unpublished.
- [x] [Review][Patch] Eviction prose overstates the bound — "one recoverable re-mint" is actually repeatable starvation under a sustained mint flood; a hostile local page looping the unauthenticated mint evicts every legitimate ticket within the flood's period, so the legitimate client can lose the mint→upgrade race indefinitely, not once [src/companion/app/routes/session.py:14-16]
- [x] [Review][Patch] Test-module docstring overclaims "``app.state.ticket_store`` is never read to make an assertion" — contradicted in the same file by `test_the_shipped_ttl_reaches_the_route` (asserts via direct `store.consume(...)`) and `TestTheStoreIsCreatedByTheLifespan`; the consume-side exception is forced (no wire surface until c5-3) but undeclared [tests/unit/companion/test_routes_session.py:21-23]
- [x] [Review][Patch] AC 10 literal placement not met — the eviction policy and its cost live on the `MAX_TICKETS` constant docstring, while the `TicketStore` class docstring never states the policy [src/companion/app/state.py:401-421]
- [x] [Review][Patch] Non-finite `ttl` passes the positivity guard — `float("nan")`/`float("inf")` compare `False` against `<= 0`; NaN deadlines refuse every consume and never prune. Guard: `if not math.isfinite(ttl) or ttl <= 0` [src/companion/app/state.py:261]
- [x] [Review][Patch] `resident_count` reads expired-but-unpruned residue as resident — expired tickets are pruned only on `mint()`, never on `consume()` or by time, so after a mint burst with no further mints the count reports garbage as live; at minimum the property docstring should warn any future metrics consumer [src/companion/app/state.py:272-282, 342]
- [x] [Review][Patch] The no-lock argument cites CPython bytecode atomicity it does not need — "single CPython operation" is fragile (free-threaded builds, a future `to_thread`) while "synchronous method, no `await`, single-threaded event loop" is sufficient alone; keep only the durable argument [src/companion/app/state.py module docstring]
- [x] [Review][Patch] The Host/Origin source-scan test strips only the module docstring — `_store`'s and `mint_session_ticket`'s docstrings are scanned as "executable" text, so a purely editorial doc edit mentioning "Host" or "Origin" reddens a structural security test; strip docstrings via `ast` instead [tests/unit/companion/test_routes_session.py]
- [x] [Review][Patch] `_store`'s "Deliberately unguarded" claim is literally false — the code *is* a guard (`if store is None: raise AttributeError(...)`) manufacturing the exception type the accessor just suppressed; correct the docstring (and consider `RuntimeError` for honest intent — both reach the 500 middleware) [src/companion/app/routes/session.py:44-63]
- [x] [Review][Patch] Exact-boundary float equality in the route-level TTL test is brittle — `clocked.now += TICKET_TTL_SECONDS` lands bit-identical to the stored deadline and relies on float coincidence; the unit tests own the boundary, so this test should advance strictly past it [tests/unit/companion/test_routes_session.py:404-421]
- [x] [Review][Defer] `consume()` has zero production callers, so "single-use" is unproven on any production path — c5-3 wires it into the upgrade handler, where the no-await compare-and-set argument must be re-made against the real handshake code (e.g. no `await` slipped between validation steps) [src/companion/app/state.py:312-340] — deferred, declared story scoping; homed on c5-3
- [x] [Review][Defer] The Q3/AD-5 ruling is narrated in ≥5 shipped prose locations (state.py, security.py ×2, main.py "CORRECTED AT c5-2" block, test_routes_active_deck.py) with no consistency guard — this diff itself corrected three guessed-wrong paragraphs and answered them with more forward-looking prose about c5-3/c5-5/c5-6 — deferred, process debt; candidate for the C5 retro
- [x] [Review][Defer] `scripts/dump_openapi.py`'s docstring is becoming a dated changelog — two more paragraphs of measurement narrative this story, nothing tests the claims, and it has already contradicted itself once (corrected here) — deferred, process debt; candidate for the C5 retro

---

## Open questions for Brad

**Q1 and Q3 block code. The rest can be ruled at the point they are reached.**

1. **🔴 BLOCKING — Does `GET /api/session` validate `Origin`?** Homed here by name at
   `c1-5:357-358`. Facts: there is **no CORS middleware** and c1-5 ruled there never will be
   (`TestCorsIsDeliberatelyAbsent`); AD-5 and review S-6 both put `Origin` on the **upgrade** only;
   `Host` validation already applies here. A malicious local page can therefore *issue* the GET but
   cannot *read* the response, so it cannot steal a ticket — it can only burn them, which AC 10's
   bound contains. **Recommendation: no `Origin` check on the mint.** It would duplicate c5-3's
   decision, and it would break any future Vite dev-proxy that rewrites `Host` but not `Origin`
   (`c1-5:632-635`; `deferred-work.md:3539` records that path as still unexercised). Ruling either
   way closes the c1-5 open question — say so in the record.
2. **How is the ticket store bounded, and what is evicted?** No artefact says. **Recommendation:** a
   `_MAX_TICKETS` cap with earliest-expiry eviction, mirroring `NegativeCache._evict_earliest_expiry`
   (`images.py:1620-1635`). Suggested value **256** — not 60, not 15 (the AD-1 literal guard), and
   far above any plausible legitimate concurrency of one browser reconnecting.
3. **🔴 BLOCKING — `state.py` or `security.py`?** Both shipped docstrings claim it; the spine splits
   storage from mint/consume and a compare-and-set cannot be split. **Recommendation: `state.py`.**
   `security.py`'s single proven structural property is *"stores nothing"* (`:737-786`, probed
   against four plants) and that is the strongest guard in the package — putting a mutable ticket map
   behind it, even as an instance, spends the clearest thing AD-5 has. `state.py` is also where the
   spine puts in-memory tickets and where c5-4's connection registry is already booked. Cost:
   `security.py:16`'s sentence is corrected, and the `state.py` name-ban loses the word `ticket`
   (AC 14–15 replace it with something stronger).
4. **What is the model called and what does it carry?** **Recommendation:** `SessionTicket` with a
   single field `ticket: str`. Note `HealthResponse` is the codebase's only `*Response` suffix and
   c3-4 recorded it as predating the convention. **Do not publish `expires_in`**: c5-6 mints a fresh
   ticket per attempt and never inspects the TTL, and a published field is a wire commitment Story
   8.3 would owe an amendment for (`epics:3272-3302` — `GET /api/session` is currently *not* on its
   list precisely because NFR-01 already names the endpoint and nothing else).
5. **`Cache-Control: no-store` on the `200`?** **Recommendation: yes.** It would be the first success
   path in the app to set it, so it is a deliberate novel construct rather than copied hygiene — but
   a single-use credential a browser is free to cache is not single-use. Note the response is already
   unreadable cross-origin; this is about the *client's own* storage layers.
6. **Does c5-2 ship `consume()`, or only `mint()`?** Epic AC 3 (*a consumed ticket is rejected on
   replay*) requires consume to exist and be tested, but the WebSocket upgrade that calls it is c5-3.
   **Recommendation: c5-2 ships the complete mint/consume/expire API and unit-tests it directly;
   c5-3 only wires it into the upgrade.** Stated here so it does not read as scope creep in review,
   and so c5-3 does not re-implement it.
7. **Ticket entropy.** **Recommendation:** `secrets.token_urlsafe(32)` — the same strength as
   `discovery.mint_token()`, under this story's own constant and its own call site, so "no shared
   code path" holds without also making the ticket weaker than the token it stands beside.

---

## Dev Agent Record

### Agent Model Used

claude-opus-5 (Amelia, `bmad-dev-story`), 2026-08-08.

### Debug Log References

**Task 0 — baseline, measured on `2df2461` before any edit.** Every row of the story's table
re-run; **one drift, immaterial**:

| Fact | Story claimed | Measured | Verdict |
|---|---|---|---|
| Python tests | 2,551 / 54 deselected | 2,551 / 54 deselected (2,605) | match |
| OpenAPI schema | 12 components, 7 paths | 12 components, 7 paths | match |
| `gen:api` at baseline | clean no-op | clean no-op, whole tree clean | match |
| Plugin mirror | sha256-identical on 4 files | identical on all 4 | match |
| Local Node | v25.8.1 | v25.8.1 | match |
| `ui/node_modules` | PRESENT (376 entries) | PRESENT (**369** entries) | **drift, immaterial** |
| `c5-2` key grep | 8 hits | 8 hits, all as listed | match |

`origin/feat/companion-c5` confirmed at `2df2461` **before** `checkout -b`.

**The three predicted reds, in the order they actually fired.** Recorded because the *ordering* is
itself a finding (see the last bullet of R2 below).

1. **Router tax** (`deferred-work.md:1905-1930`, which names c5-2 by key) — fired immediately on
   adding `session.router` to `build_app()`:
   ```
   tests/unit/companion/test_spa.py:321: in test_the_schema_is_unchanged_by_installing_the_mount
   E   AssertionError: Extra items in the left set: '/api/session'
   ```
2. **The `ticket` name-ban** (`test_routes_active_deck.py:724-735`, written by c3-4 *"so c5-2
   inherits a rule rather than a coincidence"*) — fired on the same run:
   ```
   E   AssertionError: the slot reached for {'ticket'}
   ```
3. **The two committed-schema pins** — did **not** fire on that run, and correctly so: they read
   the *committed* `ui/src/api/openapi.json`, which had not been regenerated yet. They fired the
   moment `npm run gen:api` ran:
   ```
   test_committed_schema.py:73  E   Extra items in the left set: '/api/session'
   test_committed_schema.py:194 E   Extra items in the left set: 'SessionTicket'
   ```

**R2 — thirteen plants, every one PROVEN RED through the FULL 2,594-test suite** via
`uv run python -m scripts.probe_harness --expect-red '<node-id>'`, each reverted after. The harness
owns its argv, so none of these runs could have been narrowed; the collected count is printed with
every result and stayed at 2,594 throughout.

| # | Guard | Plant | Result |
|---|---|---|---|
| G1 | `test_the_state_module_names_no_agent_credential` | `agent_token` identifier in `state.py` | RED (also caught G2) |
| G2 | `test_the_ticket_store_shares_no_code_path_with_the_agent_token` | `from src.companion import discovery` | RED |
| G3 | `test_the_session_route_declares_neither_a_503_nor_a_413` | `payload_too_large` on the include | RED *(after regen — see below)* |
| G4 | `test_the_schema_is_unchanged_by_installing_the_mount` | deleted the new router line | RED |
| G5 | `test_the_paths_are_exactly_these` | renamed the route path | RED *(after regen)* |
| G5b | `test_the_component_names_are_exactly_these` | renamed the model | RED *(after regen)* |
| G6 | `test_the_route_module_contains_no_host_or_origin_check_of_its_own` | read `Origin` in the handler | RED |
| G7 | `test_expired_tickets_are_removed_rather_than_merely_ignored` | removed the prune from `mint` | RED (+ the eviction-ordering test) |
| G8 | `test_a_ticket_exactly_at_the_deadline_is_already_expired` | `<=` for `<` in `consume` | RED (+ the route-level TTL test) |
| G9 | `test_the_200_carries_no_store` | deleted the header line | RED |
| G10 | `test_a_fresh_ticket_is_accepted_and_its_replay_is_refused` | `.get` for `.pop` in `consume` | RED (+ 2 more) |
| G11 | `test_the_earliest_expiring_ticket_is_the_one_evicted` | evict newest instead | RED |
| G12 | `test_the_state_module_examples_all_pass` | broke a doctest expectation | RED |

**⚠️ A FINDING THE STORY DID NOT PREDICT, and it cost two failed probe attempts.** G3 and G5 were
first planted in *source only* and the harness correctly reported they **did not fire** — the
committed-schema pins stayed green while `test_openapi_contract.py::
test_committed_schema_matches_the_live_app` went red instead. That is not a broken guard; it is the
file's design. `test_committed_schema.py` asserts against the committed `openapi.json` on disk, so
it pins **what was shipped**, and `test_openapi_contract.py` is the separate guard pinning
**shipped equals live**. The pair is complete and correct — but nothing in either file says so, so
the next R2 pass will plant in source, see green, and reasonably conclude the guard is broken.
Re-proved with a real `npm run gen:api` between plant and run; all three then fired. Ledgered.

**What each new guard actually compares, and what it cannot see** (R2's one-line-per-guard rule,
read against the code rather than against its own comment):

- **G1** compares `state.py`'s AST identifier set against five agent-token spellings. **Cannot
  see:** the credential reached indirectly — `getattr(app.state, "agent_" + "token")`, or an import
  aliased to another name. That hole is precisely why G2 exists.
- **G2** compares the same identifier set against the *call graph* of AD-5's forbidden shared paths
  (the `discovery` module, the three token functions, the `Bearer` channel). **Cannot see:** a
  shared path built from names it does not know, or anything the *route* module does — which is why
  `test_routes_session.py` re-asserts the property over the wire on a real response and real logs.
- **G3** compares `/api/session`'s declared response keys against `{200, 400, 500}` and asserts
  non-membership of `DATABASE_BACKED`. **Cannot see:** a 503 that is *reachable* but undeclared —
  it reads the contract, not the code.
- **G4** compares two path sets built from the same router objects. **Cannot see:** a router added
  to *both* lists but registered below `install_spa` — `TestMountOrdering` is what covers that.
- **G5/G5b** compare the committed artifact's path and component sets against literals. **Cannot
  see:** any source change until `gen:api` runs (measured above).
- **G6** compares the route module's executable lines against the two header names. **Cannot see:**
  a check spelled without either literal, or one delegated to a helper.
- **G7** compares `resident_count` after a mint that should have pruned. **Cannot see:** a prune
  that runs but drops the wrong entries — G7's sibling
  `test_pruning_does_not_take_live_tickets_with_it` is the non-vacuity for exactly that.
- **G8** compares acceptance at `TTL - 0.001` against rejection at exactly `TTL`. **Cannot see:**
  a clock that is wall-time rather than monotonic — nothing in the suite can, since `FakeClock`
  replaces it; the defence there is the injected-`clock` parameter and the docstring.
- **G9** compares one response header. **Cannot see:** whether an intermediary honours it.
- **G10** compares two consecutive consumes of one ticket. **Cannot see:** a genuine concurrent
  double-consume — single-threaded asyncio has no interleaving point inside `dict.pop`, which is
  the AC 18 argument, so there is nothing to race in-process.
- **G11** compares which of four tickets survive a cap overflow. **Cannot see:** the eviction cost
  to a legitimate client, which is prose in `MAX_TICKETS`' docstring rather than an assertion.
- **G12** compares `doctest.testmod`'s failure count, with `attempted > 0` as its non-vacuity.
  **Cannot see:** `security.py`'s two `Example:` blocks — deliberately out of scope, ledgered.

**Gates, all green and all re-run after the final edit.**

```
uv run ruff check .              All checks passed!
uv run ruff format --check .     313 files already formatted
uv run mypy src/                 Success: no issues found in 90 source files
uv run mypy src/ --platform win32  Success: no issues found in 90 source files
uv run pytest -m "not integration"  2594 passed, 54 deselected in 20.58s
probe_harness --expect-green     2594 collected, 0 failed, exit 0

ui/  npm run lint          eslint + stylelint clean
ui/  npm run format:check  All matched files use Prettier code style!
ui/  npm run typecheck     tsc -b, exit 0
ui/  npx vitest run        1694 passed (65 files)
ui/  npm run build         built in 49ms — no diff in the committed static bundle
```

**Plugin mirror (AC 28), verified after the LAST edit and not before it.** c5-1 shipped a
sha256-match claim that all three review layers falsified; this one was re-run at the end:

```
MATCH  contracts.py          MATCH  app/main.py
MATCH  app/state.py          MATCH  app/routes/session.py
MATCH  app/security.py
ALL FIVE sha256-IDENTICAL after the final edit
```

### Completion Notes List

**All seven open questions were ruled by Brad before code was written**, every one on the story's
own recommendation: **Q1** no `Origin` check on the mint · **Q2** `MAX_TICKETS = 256` with
earliest-expiry eviction · **Q3** `state.py` · **Q4** `SessionTicket { ticket: str }`, TTL not
published · **Q5** `Cache-Control: no-store` on the 200 · **Q6** full mint/consume/expire API
shipped and unit-tested here · **Q7** `secrets.token_urlsafe(32)`.

**The four headlines, and how each resolved.**

1. **The two disagreeing docstrings — resolved, and the loser corrected in this commit.**
   `security.py:16` claimed the ticket *"joins here"*; Q3 sent the store to `state.py`, so that
   sentence is now a recorded correction naming what it got wrong and why. `state.py:18`'s claim
   became true and was updated to past tense. Two further predictions this story falsified were
   corrected alongside: `security.py:420` (*"genuinely middleware-shaped … `build_app()` never grows
   a second security line"* — half right; the consume gates a handshake, but the **mint is an
   endpoint** and `build_app()` did grow an `include_router`) and `main.py:503` (*"c5-2 and c5-5 add
   their pieces inside `install_security`"* — that sentence was describing **c5-3**). All are `#`
   comments or docstrings in non-wire positions, and **all three were verified to cost zero
   regeneration diff** by re-running `gen:api` and hashing both artifacts: byte-identical. c3-9's
   rule holds for a fourth story.
2. **The guard c3-4 aimed at this story — narrowed, not deleted, and the lost coverage replaced by
   something strictly stronger.** `ticket` left the ban list because a ticket store legitimately
   uses the word; the five agent-token names stayed. In its place, AC 15's new sibling asserts
   AD-5's actual requirement — that the ticket module never imports `discovery`, never reads
   `agent_token`, and never calls the three token functions or touches the `Bearer` channel. The
   old guard proved a noun was absent; the new one proves a **code path** is. Its sibling at
   `:737-786` (`security.py` stores nothing) **passed unchanged**, which was the whole reason Q3
   chose `state.py`.
3. **The real schema diff landed exactly as predicted: 7 → 8 paths, 12 → 13 components.** Both
   `ui/src/api/openapi.json` and `types.d.ts` regenerated and committed; `git status --porcelain --
   ui/src/api/` clean after a re-run. All three pins went red first and the reds are pasted above.
4. **"Same-origin" is enforced by nothing, and that is now a written ruling rather than a gap.**
   Q1 closed the `Origin`-on-REST question c1-5 homed here by name; the reasoning, the residual
   exposure (a local page can burn tickets, not steal them) and the bound that contains it are in
   `routes/session.py`'s docstring, in `deferred-work.md`, and asserted structurally.

**AC 18 — the lock argument, which this story was set up to have to make.** `state.py:25-32` named
*"a compare-and-set"* as the change that earns a lock, and `consume` **is** one. The lock is still
declined, and the paragraph was amended to say why rather than left as an omission: the
compare-and-set is spelled as **one synchronous `dict.pop`**, so there is no `await` between the
read and the delete and therefore no interleaving point at which a second caller could observe the
ticket still present. Two concurrent consumes are two `pop` calls — the first wins, the second gets
`None`, which is exactly what a lock would produce, at the cost of making `consume` awaitable and
pulling `async` into c5-3's handshake path. **The three changes that would break that argument are
written down** (splitting the pop; making `consume` async; moving the store off the event loop),
so the next author checks their change against a stated premise rather than a conclusion.

**⚠️ A SECOND UNPREDICTED FINDING — a shipped ledger claim in `dump_openapi.py` is false, and it
was corrected in this commit.** Since c3-8 that file has stated: *"a Pydantic model's `description`
is the whole docstring"* and that Google-section truncation *"applies to **route** docstrings"*.
It does not. `_CompanionFastAPI.openapi()`'s normaliser walks **every** description in the document.
Measured across all four wire models carrying a Google section — `HealthResponse`, `ErrorResponse`,
`ActiveDeck` and `SessionTicket` all have `Attributes:` **and** `Example:` in source, and **none of
the four ships either on the wire**. What c3-8 actually observed is still true and is the useful
half: its `ErrorResponse` edit sat *above* that model's `Attributes:` header, which is why it
crossed in full. The corrected rule is one rule, not two: **everything above the first Google
section ships, on models and routes alike.** c5-2 relied on it deliberately in both places.

**Two declared deviations from the story text, both stated rather than glossed:**

1. **The doctest wiring covers `state.py` only.** The story offered widening to `security.py:97,116`
   as optional *"and should be a stated decision either way"*. **Not taken**: a story that starts
   executing another module's untested examples owns whatever they turn out to say, and c5-2 has no
   other reason to touch that module. Ledgered with a fix shape (the honest generalisation is one
   test walking every `src/companion` module, not a per-module opt-in) and homed on c5-3, which
   edits `security.py` anyway.
2. **The 413 wart was not doubled.** `deferred-work.md` warned it is *"doubled by every new GET
   route"*. `/api/session` declines it, mirroring c3-4. So the count of body-less GETs publishing an
   unreachable 413 stays at **six**, and two consecutive route-adding stories have now declined —
   which narrows c5-5's job from a survey to a single edit at two call sites. Recorded so c5-5 does
   not re-litigate it.

**Inherited deferrals, every disposition accounted for (R1).** *Triggered (3):* router tax —
**PAID**, one line, red pasted. Body-less-`GET` 413 — **DISPOSITION RECORDED**, not doubled.
`Origin` on REST — **RULED and CLOSED** (Q1). *Not triggered (5), each confirmed rather than
assumed:* pre-parse body cap (body-less `GET`); body-parsed-before-auth (credential-free `GET`);
`errors.supported_methods` under a non-root `Mount` — **c5-2 adds an `APIRouter`, not a `Mount`**,
and `TestTheMethodSemantics` passed unedited; the vitest half of the probe harness (no frontend
guard planted); `tsc -b` cross-project cascade (no `ui/tests` added — and `npm run typecheck`
exits 0 regardless). *Don't-break (5):* both AD-5 guards handled per AC 14–16;
`TestCorsIsDeliberatelyAbsent` untouched — **no CORS added**; no `securitySchemes` component; no
`503` on `/api/session` and it is **not** in `DATABASE_BACKED`; no new top-level
`src/companion/*.py` — everything landed under `app/` or in the existing `contracts.py` leaf.

**The AD-1 construction-limit guard was cleared deliberately, not by luck.** `30.0`, `256` and `32`
are all outside the banned `{60, 15}` set, and `_LIMIT_FAMILY_EXEMPT` still names only
`contracts.py`. The story predicted a store cap of 60 or a sweep of 15 would be the **third**
unpredicted collision; picking 256 avoided it, and `test_routes_format_check.py` stayed green.

**AC 30 — Dev Notes self-check.** 19.3 KB, against C4's 41 KB average and c5-1's 20.5 KB — **the
third consecutive story under half the C4 average**, with every triggered/not-triggered disposition
above accounted for. R1 is holding.

**Suite: 2,551 → 2,594** (+43: 41 in the new `test_routes_session.py`, 1 new committed-schema pin,
1 new AD-5 structural guard). No test sleeps; the 30-second TTL is proven at zero wall clock.

### File List

**New**
- `src/companion/app/routes/session.py`
- `tests/unit/companion/test_routes_session.py`
- `plugin/server/src/companion/app/routes/session.py` *(generated mirror)*

**Modified**
- `src/companion/contracts.py` — `SessionTicket`
- `src/companion/app/state.py` — `TICKET_TTL_SECONDS`, `MAX_TICKETS`, `_TICKET_ENTROPY_BYTES`,
  `TicketStore`, `ticket_store()`; module docstring (Q3 ruling, AC 18 lock argument)
- `src/companion/app/security.py` — two falsified docstrings corrected (`:16`, `:420`)
- `src/companion/app/main.py` — import, lifespan line, `include_router`, two corrected comments
- `tests/unit/companion/test_routes_active_deck.py` — AD-5 guards (AC 14, 15)
- `tests/unit/companion/test_committed_schema.py` — 8 paths, 13 components, new per-route pin
- `tests/unit/companion/test_spa.py` — router tax line
- `scripts/dump_openapi.py` — ledger entry + the c3-8 truncation correction
- `ui/src/api/openapi.json` *(regenerated)*
- `ui/src/api/types.d.ts` *(regenerated)*
- `_bmad-output/implementation-artifacts/deferred-work.md` — 5 entries
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `plugin/server/src/companion/{contracts,app/state,app/security,app/main}.py` *(generated mirror)*

### Change Log

| Date | Change |
|---|---|
| 2026-08-08 | Q1–Q7 ruled by Brad, all on the story's recommendations. Q1 closes c1-5's `Origin`-on-REST question; Q3 sends the ticket store to `state.py`. |
| 2026-08-08 | `TicketStore` + `SessionTicket` + `GET /api/session` implemented; lifespan wiring; `build_app()` keeps zero side effects. |
| 2026-08-08 | Three shipped docstrings corrected as falsified predictions (`security.py:16`, `:420`, `main.py:503`) — verified to cost zero schema diff. |
| 2026-08-08 | AD-5 guard narrowed (`ticket` un-banned) and replaced with a structural no-shared-code-path assertion; its `security.py` sibling passed unchanged. |
| 2026-08-08 | Schema 7→8 paths, 12→13 components; three pins reddened first, then updated; both generated artifacts committed. |
| 2026-08-08 | R2: thirteen guards each planted and proven RED through the full 2,594-test suite, then reverted. |
| 2026-08-08 | Corrected a false claim `dump_openapi.py` has carried since c3-8 about wire-model docstring truncation, measured across all four models. |
| 2026-08-08 | 5 `deferred-work.md` entries: router tax paid, 413 disposition, `Origin` closed, `Mount` not triggered, 2 new items. |
| 2026-08-08 | All Python and frontend gates green; plugin mirror rebuilt and sha256-verified after the final edit. |
