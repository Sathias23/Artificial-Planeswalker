---
epic: c3
story: c3-1
work_branch: feat/companion-c3
story_branch: feat/companion-c3-1-deck-endpoints
depends_on: none — Epic C2 shipped to master at a52d6f8 (PR #28); the C3 umbrella is cut off it
baseline_commit: 02b2c45
---

# Story C3.1: Deck list and deck detail endpoints

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As the browser UI,
I want to read the deck list and any full decklist over REST,
so that I can render a deck without knowing anything about the database schema.

**What this story really is.** It is the **first production route in `src/`** — nineteen stories of
scaffolding have been built for it and every one of them named it by number. `deps.py`, `errors.py`,
`spa.py`, `dump_openapi.py`, `wire-contract.test.ts` and `ui/README.md` all contain a sentence
beginning "c3-1". So the dominant risk here is **not** writing an endpoint; it is writing an endpoint
that re-derives something already decided, or that quietly breaks one of the six gates holding the
seam open.

Three things make it different from every C2 story:

1. **Almost nothing is new.** The session, the 404/503 tokens, the status mapping, the error
   middleware, the type pipeline, the SPA route reservation and the CI drift checks all exist and are
   all already gated. The route bodies are a handful of lines each. **What this story mostly does is
   consume — and prove it consumed rather than reimplemented.**
2. **It is the first C3 story and therefore the first to touch `src/data` schemas from the companion
   side.** AD-1 says the backend "consumes existing repositories and their Pydantic schemas and
   defines **no second card or deck shape**". The shapes exist. The *projection* that builds them
   currently lives in `src/mcp_server/tools/deck_management.py`, which the companion may not import —
   that is landmine 1 and the single biggest decision in this story.
3. **It changes generated artifacts on both sides of the wire.** `ui/src/api/openapi.json` and
   `ui/src/api/types.d.ts` are committed, gated per-file in two different CI jobs, and go from **two
   component schemas to six**. Getting the regeneration wrong is a red build, not a subtle bug.

**Nineteen things were measured on this machine at `02b2c45` — do not rediscover them.** They are
listed below roughly in the order they will bite.

### The seam that already exists (do not rebuild any of it)

1. **The session dependency is written and named.** `src/companion/app/deps.py:282` —
   `DbSession = Annotated[AsyncSession, Depends(get_session)]`. Its own docstring (`deps.py:285`)
   names c3-1 as its first caller and says the caller "annotates a parameter with this and inherits
   the whole contract: the lazy engine, the readiness probe, the `503` tokens and the shared recipe.
   None of them re-derives any of it." **Annotate. Do not construct an engine, do not call
   `create_async_engine`, do not call `is_database_initialized` in a handler.**

2. **`deps.py:285` names the wrong route and must be corrected here.** It says
   `` c3-1 (``GET /api/decks``, ``GET /api/decks/{id}``) ``. The detail route is **singular** —
   `GET /api/deck/{id}` — per PRD FR-02 (`prd.md:110`), `EPIC-SPLIT.md:61`,
   `ARCHITECTURE-SPINE.md:435`, `EXPERIENCE.md:103` and c3-3's own AC
   (`GET /api/deck/{id}/format-check`). Five artefacts against one docstring. Landmine: a dev who
   reads only `deps.py` ships `/api/decks/{id}` and c3-3, c4-2 and every UX doc are then wrong.

3. **The 404 token already exists, already has a status, and already has a raise class.**
   `ErrorReason` (`src/companion/contracts.py:46-53`) is closed at six and **`deck_not_found` is
   already one of them**; `STATUS_BY_REASON` (`errors.py:45-52`) maps it to 404. So this story adds
   **no token** — it is the first *raiser* of one that already ships. `raise
   CompanionError("deck_not_found")` and stop. Never build a `JSONResponse`, never pass a status.
   (Contrast c3-2, which *does* add `card_not_found` and is under retro ruling R1 to ship the copy
   row with it. **That constraint is c3-2's, not this story's** — do not add a token here.)

4. **The 503 half is already wired and needs no code at all.** `install_error_handling`
   (`errors.py:390-422`) registers `DatabaseError → 503 database_unavailable` app-wide, and
   `get_session` raises `CompanionError("database_not_initialized")` when the SQLite file is absent
   or the `cards` table is empty. The C1 retro closed that item in its strongest form: *"c1-6
   registered `DatabaseError→503 database_unavailable` inside `install_error_handling` **before any
   data route existed**, so c3-1 onward inherit the guard with no per-route ceremony."* **A
   `try/except DatabaseError` in a route body is a regression, not defence** — it would swallow the
   exception the handler exists to type.

5. **`error_responses(...)` is the per-route declaration helper** (`errors.py:122-154`), and its
   docstring names c3-1 as one of three per-route callers. Use `responses=error_responses(
   "deck_not_found")` on the **detail** route only. `build_app()` already declares
   `invalid_request | payload_too_large | database_unavailable | internal_error` app-wide
   (`main.py:381-384`) — do not repeat those per route, and do not add `database_not_initialized`
   app-wide as a side effect of this story.

6. **The router must be registered ABOVE `install_spa(app)`.** `main.py:394-400` carries a
   `MUST STAY LAST` comment explaining that a mount at `/` matches every path and Starlette matches
   in list order, so *"`GET /api/decks` would answer 200 with index.html instead of running the
   endpoint"*. `test_spa.py::TestMountOrdering` fails with instructions if the line moves.

7. **`/api` is already reserved, and the comment that reserves it is now stale.**
   `spa.py:59-66`: `_RESERVED_SEED = frozenset({"api"})` with *"`/api` has no routes until c3-1, but
   the reservation must hold now"*. After this story `/api` is derived from the live route table
   anyway — the seed becomes belt-and-braces. Update the comment (standing agreement:
   forward-dated-comment homing); **do not delete the seed** — `_reserved_prefixes` is derived, and
   removing the seed changes behaviour for any future state where no `/api` route is registered.

8. **The in-process test seam is `lifespan_client`** (`tests/unit/companion/conftest.py:158-168`),
   used as `async with lifespan_client(app) as client`. It enters `lifespan(app)` directly, stamps
   `app.state.bound_port = 54321` and derives a matching `Host`, so **every companion test flows
   through the real security envelope**. `httpx.ASGITransport` never sends lifespan messages — a
   test that skips the seam finds no `instance_id`, no `Database` holder, and gets
   `500 internal_error`.

9. **`isolated_data_dir` is autouse** in that conftest and sets `PLANESWALKER_DATA_DIR` to `tmp_path`
   for every test in the package. Steer the *database* separately with
   `monkeypatch.setenv("CARDS_DATABASE_URL", f"sqlite+aiosqlite:///{path.as_posix()}")` — the
   `_point_at` pattern at `test_deps.py:143-158`. `CARDS_DATABASE_URL` wins over everything, so a
   developer's own environment cannot hijack the resolution.

### The one real decision: where the projection lives

10. **`DeckSummary` and `DeckDetail` cannot be built with `model_validate`, and the code that builds
    them correctly is in a package the companion may not import.** The schemas
    (`src/data/schemas/deck.py`) say so in their own docstrings: *"The count fields
    (`mainboard_count`/`sideboard_count`/`distinct_cards`) are **computed by the tool helper** from a
    source `Deck`'s `deck_cards` — a `Deck` has no such attributes, so `model_validate` would
    silently use the `0` defaults."* The helpers are `_counts` / `_deck_summary` / `_deck_detail` at
    `src/mcp_server/tools/deck_management.py:129-184`, and `src/companion` is a **sibling** of
    `src/mcp_server` (AD-1), not a consumer of it.

    Three options, and only one satisfies AD-1:

    | Option | Verdict |
    | --- | --- |
    | Import from `src.mcp_server.tools.deck_management` | **Banned.** Siblings over the same core (AD-1); it would also drag the MCP tool module and its `mcp` import into the web process |
    | Re-implement the projection in `src/companion` | **Banned in spirit.** Same shape, second implementation — `distinct_cards` semantics would drift the first time anyone changes them, which is exactly the "second truth" AD-1 exists to prevent |
    | **Move the projection down to `src/data/schemas/deck.py`** and have both shells call it | **This story's ruling.** Import direction `data → logic → shells` holds; the counts live with the fields they compute; there is one implementation and both shells prove it |

    **The counts are silently wrong on the `0` default, not loudly wrong** — a deck rendering as
    "0 cards" with a populated `cards[]` array is the failure mode, and no type checker sees it. A
    test must assert a non-zero count against a seeded deck, or this AC is decoration.

11. **The move has exactly three call sites and no test touches the private helpers.** Verified:
    `deck_management.py:270` (`list_decks`), `:322` (`create_deck`), `:357` (`load_deck`). A repo-wide
    grep for `_deck_summary|_deck_detail|_counts(` returns those three plus two unrelated test names
    containing the substring "counts". The MCP suite is the proof the move is behaviour-preserving —
    it must stay green with **zero test edits**.

### The gates that will fire, and what they want

12. **Two generated files, two CI jobs, per-file drift checks.** `ui/src/api/openapi.json` is
    gated Python-side by `tests/unit/companion/test_openapi_contract.py` (byte comparison, both
    matrix Pythons); `ui/src/api/types.d.ts` is gated Node-side by `npm run gen:types` plus a
    `git status --porcelain` check (`.github/workflows/ci.yml:180-210`). **The one command is
    `npm run gen:api`** (from `ui/`): it runs `uv run python -m scripts.dump_openapi` then
    `npm run gen:types`. Commit both files in the same commit — `ui/README.md:146-149` says a commit
    with a fresh `openapi.json` and a stale `types.d.ts` is red in CI and poisons a bisect.

13. **The committed schema goes from 2 component schemas to 6.** Measured now: `paths` = `['/health']`,
    `components.schemas` = `['ErrorResponse', 'HealthResponse']`. After this story it must contain
    `/api/decks`, `/api/deck/{deck_id}`, and `CardSummary`, `DeckCardSummary`, `DeckDetail`,
    `DeckSummary`.

14. **`ui/tests/wire-contract.test.ts` grows on its own, and that is deliberate.** It reads
    `components.schemas` keys out of the committed `openapi.json` and bans any TypeScript outside
    `src/api/` from declaring a type of the same name. Its own docstring (line 12) says it *"picks up
    **c3-1**'s deck models … on the day those routes land, with no edit here."* **Do not edit that
    test to list names.** After this story, a hand-written `interface DeckSummary` anywhere in
    `ui/src`, `ui/tests` or `ui/config` is a failing build — which is the point.

15. **Model docstrings become JSDoc on the wire.** `_CompanionFastAPI.openapi()`
    (`main.py:350-361`) truncates every `description` at the first Google-style section header
    (`Args:`, `Attributes:`, `Example:`, `Returns:`, … — twelve headers, `main.py:218-233`), then
    `openapi-typescript` emits what survives as JSDoc into `types.d.ts` and `/docs` shows it.
    **`Note:` and `Warning:` are deliberately NOT truncated.** The four schemas this story exposes
    have prose-only leading paragraphs written for an MCP reader — they mention *"keeping `load_deck`
    payloads small for LLM clients"*, *"Build via the helper's explicit constructor, not
    `model_validate`"* and *"the Story 1.6 deck-analysis tools"*. All of that will cross the wire
    verbatim unless the leading summary is rewritten and the Python detail pushed below a truncating
    header. **`test_openapi_contract.py` already asserts `Args:` / `Attributes:` / `>>> ` never
    appear** (`PYTHON_INTERNALS`) — it does **not** catch MCP-internal prose, so this is a look, not
    a gate that will tell you.

16. **The list endpoint's ordering has a documented flake, and this story inherits it.**
    `DeckRepository.list_decks` (`src/data/repositories/deck.py:239-267`) orders by
    `created_at DESC, id` — but `id` is a UUID, so decks created in the same microsecond come back in
    UUID order, which is effectively random.
    `tests/integration/data/test_deck_repository.py::test_list_decks_with_strategy_field` is
    order-flaky for exactly this reason and is **pre-existing and ledgered twice** in
    `deferred-work.md` (c1-5 and c2-1 entries). **Do not assert strict newest-first ordering over
    decks seeded back-to-back** — either assert set membership, or seed with distinct `created_at`
    values. And do not "fix" the repository ordering here: it is a `src/data` change with MCP blast
    radius and it is not this story's.

17. **`list_decks` eagerly loads every deck's full cards just to count them.**
    `deck.py:263` — `selectinload(DeckModel.deck_cards).selectinload(DeckCardModel.card)`. For
    `GET /api/decks` that means the whole corpus of every deck is materialised and then discarded
    down to three integers. **Accepted, not fixed here**: it is existing `src/data` behaviour that
    `list_decks` (MCP) already pays, the deck count is small (single digits on a real machine), and
    NFR-05's budget is the deck *view*, not the deck list. Record it in `deferred-work.md` with
    **c10-3** (latency hardening) as the named home. Do not add a count-only query in this story —
    that is a second read path over one shape.

18. **`is_database_initialized` requires a non-empty `cards` table**, not just the file
    (`src/data/database.py:125-155`), and a `import_state.in_progress` marker also reads as *not*
    initialized. So a test database for these routes must have the **full schema plus at least one
    card row plus deck rows** — `test_deps.py`'s `_ready_database` helper builds a two-column `cards`
    table with plain `sqlite3` and is **not sufficient** here. Build the fixture with
    `init_database(create_engine(url))` and seed through `DeckRepository` (writes in `tests/` are
    fine — `tests/**` is not scanned by the import-boundary guard, and its docstring says so
    explicitly).

19. **`Deck.created_at` / `updated_at` carry a custom `field_serializer`** that coerces naive SQLite
    datetimes to UTC-offset RFC 3339 (`src/data/schemas/deck.py`). `DeckSummary` repeats it;
    `DeckDetail` inherits it. That is why the wire value is a string with an offset — an assertion
    expecting a bare ISO string with no `+00:00` will fail. Keep the serializer when moving code
    around it.

---

## Acceptance Criteria

### The routes

1. **`GET /api/decks` returns every saved deck as a bare JSON array of `DeckSummary`**, newest-first
   as `DeckRepository.list_decks()` orders them — **unwrapped**: no `{"status": …}`, no
   `{"decks": […]}` wrapper, no `count` field (FR-02, AD-16). A database with no decks answers
   `200 []`, never 404 and never an error state.

2. **`GET /api/deck/{deck_id}` returns the deck as a `DeckDetail`** — id, name, format, strategy,
   colour identity, tags, `mainboard_count`, `sideboard_count`, `distinct_cards`, `created_at`,
   `updated_at`, and `cards[]` of `DeckCardSummary` (each carrying `card_id`, `quantity`,
   `sideboard`, `commander` and a nested `CardSummary`) — **matching `load_deck`'s output shape
   field-for-field** (FR-02).

3. **The counts are computed, not defaulted.** A test seeds a deck with a known mainboard quantity, a
   known sideboard quantity and a known distinct-card count, and asserts all three on the wire. A
   response carrying a populated `cards[]` and `mainboard_count: 0` fails this AC.

4. **The paths are exactly `/api/decks` (plural) and `/api/deck/{deck_id}` (singular).** A test
   asserts both literal paths appear in the committed `openapi.json`. `deps.py:285`'s
   `` ``GET /api/decks/{id}`` `` is corrected to `` ``GET /api/deck/{id}`` `` in the same commit.

5. **An unknown deck id answers `404 {"reason": "deck_not_found"}`.** The handler raises
   `CompanionError("deck_not_found")`; it does not construct a response, does not pass a status, and
   does not import `JSONResponse`. Asserted on both the status and the exact body.

6. **The detail route declares its token to OpenAPI** via `responses=error_responses("deck_not_found")`.
   The committed schema shows a `404` on `/api/deck/{deck_id}` referencing `ErrorResponse`, and
   `/api/decks` does **not** declare a 404 it cannot produce. `build_app()`'s app-level `responses`
   is unchanged.

### Reuse, and proving it is reuse

7. **The handlers consume `DeckRepository` and nothing else.** `list_decks()` for the list route,
   `get_deck_with_cards()` for the detail route. No `select(...)`, no `text(...)`, no second query,
   no `session.execute` in `src/companion`.

8. **No second deck shape is declared.** The response models are
   `src.data.schemas.deck.DeckSummary` / `DeckDetail`; `src/companion/contracts.py` gains **nothing**
   (AD-1). A test asserts the committed schema's four new component names are exactly
   `CardSummary`, `DeckCardSummary`, `DeckDetail`, `DeckSummary` — so an accidentally-declared
   companion-local mirror fails loudly.

9. **The `Deck → DeckSummary` / `Deck → DeckDetail` projection has exactly one implementation in the
   repository, and both shells call it.** It moves from
   `src/mcp_server/tools/deck_management.py:129-184` down to `src/data/schemas/deck.py` as public
   constructors on the schemas themselves (`DeckSummary.from_deck(deck)` /
   `DeckDetail.from_deck(deck)`), the three MCP call sites (`deck_management.py:270`, `:322`, `:357`)
   are rewritten to call them, and **the MCP test suite passes with zero test-file edits**. A
   repo-wide grep proves no second implementation of the count arithmetic survives.

10. **The session comes from `DbSession` and nothing else.** No engine construction, no
    `create_session_factory`, no `is_database_initialized` call, no `request.app.state` read in a
    handler.

11. **No write path is opened.** `tests/unit/companion/test_import_boundary.py` passes unchanged.
    Explicitly absent from the `src/companion` diff: `create_deck`, `update_deck`, `delete_deck`,
    `add_card_to_deck`, `remove_card_from_deck`, `update_card_quantity`,
    `update_deck_color_identity`, `merge_decks`, `session.add`, `session.commit`, `session.delete`,
    `init_database`, `create_all`, `src.data.importers` (AD-2, NFR-02).

12. **No error-handling ceremony is added.** No `try`/`except DatabaseError` and no
    `add_exception_handler` call anywhere in the diff. Both 503 paths are proved **through the real
    routes**, not through a test-local route: a missing database file answers
    `503 {"reason": "database_not_initialized"}`, and a present-but-corrupt file answers
    `503 {"reason": "database_unavailable"}` — on **both** endpoints.

13. **The router is registered above `install_spa(app)`** and a test proves it: `GET /api/decks`
    against a real `build_app()` returns JSON, not `index.html`, and its `content-type` is
    `application/json`. `test_spa.py::TestMountOrdering` and the reserved-prefix tests stay green.

### The type pipeline

14. **`npm run gen:api` is run and both generated files are committed together.**
    `ui/src/api/openapi.json` and `ui/src/api/types.d.ts` are regenerated from the live app; neither
    is hand-edited; neither is passed through prettier (both stay in `.prettierignore`).

15. **Both drift gates are green from the same commit**, output pasted into the Dev Agent Record:
    `uv run pytest tests/unit/companion/test_openapi_contract.py` (Python half) and, from `ui/`,
    `npm run gen:types && git status --porcelain` producing no output (Node half).

16. **`ui/tests/wire-contract.test.ts` picks up the four new shapes with no edit to that file**, and
    a non-vacuity assertion proves it: the test's `wireShapes` list now contains `DeckSummary`, and a
    planted `type DeckSummary = { x: 1 }` in a scratch `ui/src` file makes it red (probe run, then
    reverted — evidence in the Dev Agent Record, per *probe your own guard before review does*).

17. **No Python-internal or MCP-internal prose crosses the wire.** After regeneration, `types.d.ts`
    is searched for `Args:`, `Attributes:`, `>>> `, `model_validate`, `LLM client`, `Story 1.6` and
    `lookup_card_by_name`. Anything found is fixed by rewriting that schema's **leading summary
    paragraph** for a TypeScript reader and moving the Python/MCP detail below a truncating Google
    header (`Attributes:` is the natural one) — never by editing the generated file. The result is
    recorded as measured output, not asserted.

### Boundaries, records and forward-dated comments

18. **No frontend behaviour ships.** `ui/src/App.tsx`, `ui/src/components/**` and
    `ui/src/api/schema.ts` are unchanged; **no `fetch` layer, no store, no alias export.** c4-1 owns
    the card cache and the fetch/dedupe design, c4-2 owns the deck bootstrap, c3-9 owns the
    fresh-install transition — pre-empting any of them here is scope creep against three named
    owners. The only `ui/` changes permitted by this story are the two generated files and
    `ui/README.md`.

19. **The bundle and the plugin mirror are re-measured, not assumed.** `types.d.ts` is type-only and
    erased at build, so `src/companion/app/static/` and the `plugin/` mirror are expected to be
    **byte-identical**. Measure and state it; if either changed, that is a finding, not a rebuild.

20. **The forward-dated-comment inventory is repaired** (standing agreement, promoted at the C1
    retro). Each of these either becomes true, is re-homed to its real owner, or is recorded with a
    judgement:

    | # | Location | What it says | Action |
    | --- | --- | --- | --- |
    | 1 | `src/companion/app/deps.py:285` | `` GET /api/decks/{id} `` | **Correct** to `/api/deck/{id}` (AC 4) |
    | 2 | `src/companion/app/spa.py:59-66` | "`/api` has no routes until c3-1" | **Update** — it does now; the seed stays |
    | 3 | `src/companion/app/main.py:396` | "c3-1 (and c5-2, c5-5) add their routers ABOVE this line" | **Update** — c3-1 done, c5-2/c5-5 remain |
    | 4 | `src/companion/app/errors.py:64-66` | "Nothing in `src/` raises it yet — c1-6, c3-1, c5-5 are the first callers" | **Update** — c1-6 and c3-1 now raise |
    | 5 | `src/companion/app/errors.py:128` | "c3-1 / c3-2 / c5-5 use it per-route" | **Update** — c3-1 done |
    | 6 | `scripts/dump_openapi.py:21` | "Story **c3-1** (`/api/decks`) is the first to do it" | **Update** — done, name the next |
    | 7 | `ui/src/api/schema.ts:18` and `ui/tests/wire-contract.test.ts:12` | "grows on its own as **c3-1** adds deck models" | **Update the prose only** — the mechanism is untouched (AC 16) |
    | 8 | `ui/README.md:912` | "The runtime `fetch` layer is **c3-1**'s first real consumer" | **Re-home to c4-1/c4-2** — this story ships no fetch layer (AC 18) |
    | 9 | `ui/src/App.tsx:40` and `ui/src/components/StatePanel/StatePanel.tsx:60` | "`GET /api/decks` is c3-1's" | **Re-home to c4-2** — the endpoint exists; the *wiring* does not, and is not this story's |

21. **`ui/README.md` gains the "what the gates cannot see" section** — C2 retro action item 5, owned
    by *"Brad (c3-1 or the first C3 frontend story)"*. One section enumerating every declared blind
    spot with a link to the guard that owns it: cascade-blindness in the numeric-pairing guard and in
    the companion guard it spawned; `git ls-files`-keyed guards that cannot see untracked
    stylesheets; block-local parsers; the `REVIEWED_HOSTS` deliberately-brittle baseline;
    runtime-composed class lists; `var()` indirection; UX-DR47/UX-DR7's unstacked-curve-bar half; the
    copy guard's second-person/blameless half. Each entry names its guard file. (See Q3 — Brad may
    defer this to c3-9.)

22. **`deferred-work.md` gains this story's residue with named homes**, at minimum: landmine 17's
    over-fetch in `list_decks` → **c10-3**; the `list_decks` same-tick ordering flake re-confirmed as
    still open → **unowned, ledgered**; and anything the review turns up. No residue in prose only.

### Testing

23. **Tests live at `tests/unit/companion/test_routes_decks.py`** and drive the real `build_app()`
    through `lifespan_client` against a real temporary SQLite file with the full schema, at least one
    card row and seeded decks. Coverage: populated list; empty list (`200 []`); detail happy path
    with non-zero counts and a nested `CardSummary`; sideboard and commander flags surviving the
    projection; unknown id → 404 token; missing file → 503 `database_not_initialized`; corrupt file →
    503 `database_unavailable`; both routes not shadowed by the SPA mount.

24. **Non-vacuity pairing** (standing agreement): every guard-shaped assertion in this story proves it
    *fires* and proves it *stays silent* from the same invocation. Concretely — the schema-key
    assertion is paired with a check that the list is non-empty and contains `HealthResponse` (so a
    wrong path cannot pass by finding nothing), and the count assertion is paired with a deck whose
    counts are genuinely different from each other (so `0`, `0`, `0` cannot pass by coincidence).

25. **Every Python gate is re-run and its output pasted**: `uv run pytest`, `uv run ruff check .`,
    `uv run ruff format --check .`, `uv run mypy src/`, plus the six frontend gates from `ui/`
    (`npm run lint`, `format:check`, `typecheck`, `test`, `build`, and the two drift checks). Suite
    counts are stated as *before → after*, measured at Task 0 and again at the end.

---

## Tasks / Subtasks

- [x] **Task 0 — Baseline, measured not assumed** (standing agreement)
  - [x] `git rev-parse --short HEAD`; confirm `feat/companion-c3` off `02b2c45`; cut
        `feat/companion-c3-1-deck-endpoints`
  - [x] Run and record: `uv run pytest` (count + duration), `uv run ruff check .`,
        `uv run ruff format --check .`, `uv run mypy src/`
  - [x] From `ui/`: `npm run lint`, `npm run format:check`, `npm run typecheck`, `npm test` (count),
        `npm run build`
  - [x] Record the pre-change SHA-256 (or byte size) of `src/companion/app/static/assets/*` and the
        `plugin/` mirror, for AC 19
  - [x] Record the current `paths` and `components.schemas` keys of `ui/src/api/openapi.json`
        (expected: `['/health']` and `['ErrorResponse', 'HealthResponse']`) — **matched exactly**
  - [x] Note whether `test_list_decks_with_strategy_field` passed this run (landmine 16) — **passed**

- [x] **Task 1 — Move the projection down** (AC 9)
  - [x] Add `DeckSummary.from_deck(deck: Deck) -> DeckSummary` and
        `DeckDetail.from_deck(deck: Deck) -> DeckDetail` to `src/data/schemas/deck.py`, carrying the
        count arithmetic verbatim from `deck_management.py:129-184`
  - [x] Rewrite `deck_management.py:270`, `:322`, `:357` to call them; delete `_counts`,
        `_deck_summary`, `_deck_detail`
  - [x] Update the schema docstrings that say "computed by the tool helper" to name the constructor
  - [x] Run the full Python suite — **zero test-file edits permitted**; a red MCP test means the move
        was not behaviour-preserving — **1798 passed / 1 skipped, identical to baseline**
  - [x] Grep the repo to prove no second implementation of the count arithmetic survives

- [x] **Task 2 — The routes** (AC 1, 2, 5, 6, 7, 10)
  - [x] Create `src/companion/app/routes/decks.py` with a module docstring and
        `router = APIRouter(prefix="/api")`
  - [x] `@router.get("/decks", response_model=list[DeckSummary])` → `DeckRepository(session).list_decks()`
        → `[DeckSummary.from_deck(d) for d in decks]`
  - [x] `@router.get("/deck/{deck_id}", response_model=DeckDetail, responses=error_responses("deck_not_found"))`
        → `get_deck_with_cards(deck_id)`; `None` → `raise CompanionError("deck_not_found")`
  - [x] Google-style docstrings on both; the **leading paragraph is what crosses the wire** (landmine 15)
  - [x] Register in `build_app()` **above** `install_spa(app)`; check `main.py:394-400` first

- [x] **Task 3 — Regenerate the wire types** (AC 14, 15, 17)
  - [x] From `ui/`: `npm run gen:api`
  - [x] Diff both generated files; confirm two new paths and four new component schemas
  - [x] Search `types.d.ts` for `Args:`, `Attributes:`, `>>> `, `model_validate`, `LLM client`,
        `Story 1.6`, `lookup_card_by_name`; fix at the Python docstring and regenerate if any hit —
        **all clean; one extra family found and fixed (Sphinx role markup), see Completion Notes**
  - [x] `uv run pytest tests/unit/companion/test_openapi_contract.py` and, from `ui/`,
        `npm run gen:types && git status --porcelain` — paste both

- [x] **Task 4 — Tests** (AC 3, 11, 12, 13, 16, 23, 24)
  - [x] `tests/unit/companion/test_routes_decks.py`: fixture building a real file DB via
        `init_database` + seeded card/deck rows; `_point_at`-style `CARDS_DATABASE_URL`
  - [x] Happy paths, empty list, counts, sideboard/commander, 404 token, both 503 paths, SPA
        non-shadowing, path literals in the committed schema
  - [x] **Do not** assert strict ordering over same-tick decks (landmine 16)
  - [x] Re-run `test_import_boundary.py` and `test_spa.py` explicitly
  - [x] Probe the wire-contract guard: plant `type DeckSummary = { x: 1 }` in a scratch `ui/src`
        file, run `npm test`, confirm red, revert, confirm green — paste both

- [x] **Task 5 — Comments, docs and records** (AC 18, 19, 20, 21, 22)
  - [x] Work the nine-row forward-dated-comment table
  - [x] Add the "what the gates cannot see" section to `ui/README.md` (or record Brad's deferral)
  - [x] Re-measure the bundle and the `plugin/` mirror against Task 0 and state the result
  - [x] `deferred-work.md` entries with named homes
  - [x] Fill the Dev Agent Record; update `sprint-status.yaml`

- [x] **Task 6 — Same-day three-layer review before the PR** (C2 retro action item 6, standing)
  - [x] `bmad-code-review` (Blind Hunter + Edge Case Hunter + Acceptance Auditor) before raising the PR
  - [x] Apply patches, then re-run every gate and paste the output
  - [x] Raise the PR into `feat/companion-c3` — **PR #29, raised 2026-07-31 after the post-commit
        review pass** (Brad's go-ahead via the review workflow's apply-and-PR choice)

### Review Findings

Post-commit three-layer review, 2026-07-31 (Blind Hunter + Edge Case Hunter + Acceptance Auditor
over `feat/companion-c3-1-deck-endpoints` vs `feat/companion-c3`, both commits):

- [x] [Review][Patch] Strip committed tool-call residue (`</content>`, `</invoke>`) and the duplicated Change Log row from the story record tail [_bmad-output/implementation-artifacts/c3-1-deck-list-and-deck-detail-endpoints.md:1110-1119]
- [x] [Review][Patch] Update `wire-contract.test.ts`'s forward-dated docstring — AC 20 row 7's second location was never worked, and "with no edit here" is false since review patch R7 edited the file [ui/tests/wire-contract.test.ts:12-13]
- [x] [Review][Patch] Reconcile the Dev Agent Record: the File List omits `ui/tests/wire-contract.test.ts` (which R7 modified), the probe-6 narrative ("deliberately not added") contradicts R7 adding exactly that assertion, and the AC-16 horn taken ("mechanism untouched" over "no edit to that file") is nowhere stated [story record §File List, §Review probe outputs]
- [x] [Review][Patch] Rewrite `sprint-status.yaml`'s c3-1 narrative — it asserts an AC-21 correction the story record explicitly withdrew, and carries pre-review numbers (1827 / 4 deferred entries) where the post-review truth is 1829 / 12 [_bmad-output/implementation-artifacts/sprint-status.yaml:280]
- [x] [Review][Patch] Qualify the wire-visible "newest first" promise — the same-tick UUID-order tie caveat sits below the truncation header, so `/docs`, `openapi.json` and `types.d.ts` show an unconditional ordering guarantee the ledger says is not real [src/companion/app/routes/decks.py:26; regenerate both wire files]
- [x] [Review][Patch] Move SQLAlchemy internals ("declares no `order_by`", "composite primary key's order") out of `DeckDetail`'s leading paragraph — same AC-17 failure shape R4 reintroduced; keep "order is not meaningful; sort it yourself" in the summary, push ORM detail below `Attributes:` [src/data/schemas/deck.py:240-244; regenerate both wire files]
- [x] [Review][Patch] Ledger the `_is_ref_rooted` misfire family with c3-3 as home: a legitimate `response_model=X | None` generates a top-level `anyOf` and is refused as a "hand-built envelope"; a 3.1 `$ref`-with-sibling-keys is a false red; `prefixItems` is a false green [tests/unit/companion/test_errors.py; deferred-work.md]
- [x] [Review][Patch] Pin the trailing-slash and encoded-slash spellings with tests — `GET /api/decks/`, `/api/deck/`, `/api/deck/{id}/` and `/api/deck/a%2Fb`; the handler docstring's routing-rejects-it claim is asserted, never tested [tests/unit/companion/test_routes_decks.py]
- [x] [Review][Patch] Cover the legitimate-zero and null-metadata wire cases: a sideboard-only deck (`mainboard_count: 0` beside populated `cards[]`), a card-less deck detail, and `format`/`strategy` `None` crossing the wire [tests/unit/companion/test_routes_decks.py]
- [x] [Review][Defer] `from_deck` on a non-eager-loaded `Deck` silently yields 0/0/0 with empty `cards` — already ledgered "unowned"; the keyed `data-layer-orphan-handling` story is the natural home [src/data/schemas/deck.py:220-226] — deferred, pre-existing `lazy="noload"` trap; the move widened its reach
- [x] [Review][Defer] `strategy?: string \| null` vs `format: string \| null` optionality asymmetry and the advertised `@default 0` on counts in generated types — pre-existing schema shape first put on the wire here; natural home c4-1/c4-2 [ui/src/api/types.d.ts] — deferred, pre-existing

All nine patches applied 2026-07-31. Two measured surprises while applying: the trailing-slash
spellings **redirect (`307`) rather than falling to the reserved-prefix branch** — Starlette's
`redirect_slashes` partial-match wins over the SPA mount for a route that exists, so the tests pin
the redirect, and only the empty-id `/api/deck/` answers `invalid_request`; and **`decks.format` is
a `NOT NULL` column**, so the wire's `format: string | null` null half is unreachable through the
repository — the story's own gotcha ("a deck can genuinely have no format") is half-false, ledgered
in `deferred-work.md` homed at c3-3. Post-patch gates, all green: `ruff check` clean, `ruff format
--check` 289 files, `mypy src/` (both platforms) clean, `uv run pytest` **1836 passed / 1 skipped**
(+7 tests), all six frontend gates green (549), `test_openapi_contract.py` 11 passed, `gen:types`
hash-stable through regeneration. Both wire files regenerated (the tie caveat now crosses; the ORM
prose no longer does) and the plugin mirror rebuilt.

Dismissed as handled elsewhere or noise (7): 503 `database_not_initialized` wire documentation
(ledgered, c3-9); orphaned `deck_card` → `ValidationError` 500 (pre-existing, keyed story
`data-layer-orphan-handling`); `Attributes:`-as-truncation-marker malformed Google style (ledgered,
c3-2); line-number-keyed cross-references (ledgered, unowned); the `test_spa.py` path-pin weakening
(acknowledged trade-off with a compensating differential test); `_summary_fields` dict-splat rename
drift (guarded by value-asserting wire/MCP tests); AC 18's letter violation (resolved by Brad's
recorded comment-only-repairs ruling).

---

## Dev Notes

### Decide-once rulings this story inherits (do not re-derive)

| Ruling | Source | What it means here |
| --- | --- | --- |
| REST is HTTP-native; success bodies are existing Pydantic schemas **unwrapped** | AD-16 | A bare JSON array for the list; no `status`/`count`/`decks` wrapper |
| Adding a UI state means adding a **token** first, and the token + its copy land together | AD-16, retro R1 | c3-1 adds **no** token — `deck_not_found` already ships. c3-2 owns `card_not_found` |
| The status is derived from the token, never chosen at the call site | `errors.py` module docstring | `raise CompanionError(...)`; never `JSONResponse`, never `status_code=` |
| The engine is lazy and its absence is a served UI state | AD-10, c1-6 | Annotate `DbSession`; do not probe readiness |
| `DatabaseError → 503 database_unavailable` is registered app-wide | c1-6, C1 retro | No `try/except` in a route body |
| The backend consumes existing repositories and defines no second deck shape | AD-1 | `src.data.schemas.deck` is the response model; the projection moves down, it does not get copied |
| `src/companion` is a sibling of `src/mcp_server`, not a consumer | AD-1, AD-3 | Never import `src.mcp_server.*` |
| Read-only is enforced by the CI import-boundary test, not `mode=ro` | AD-2 | The guard must stay green with no exclusions added |
| One generator, from the backend's own `app.openapi()` | AD-12 | `npm run gen:api`; no second codegen, no hand-written TS shape |
| `install_spa(app)` stays last in `build_app()` | c2-2 | Register the router above it |
| Ban the family, never enumerate members | C2 retro, standing | If a new guard is needed, key it on a family |
| Probe your own guard before review does | C2 retro, standing | AC 16's plant-and-revert probe is not optional |

### The five things this story must not break

1. **`tests/unit/companion/test_import_boundary.py`** — both guards. It is AST-only and sees modules
   no test imports. Its own docstring forbids routing around it by convention: *"a guard satisfied by
   obfuscation is theatre"* — no `getattr(repo, "create_deck")`, no dynamic import.
2. **`test_spa.py::TestMountOrdering` and the reserved-prefix tests** — the mount reads the route
   table at install time, so a router registered after `install_spa` is silently shadowed.
3. **The MCP deck tools** (`list_decks`, `create_deck`, `load_deck`) — Task 1 rewires their three call
   sites. The whole point of the move is that their behaviour is unchanged, and the MCP suite passing
   with zero test edits is the proof.
4. **`test_openapi_contract.py`'s byte comparison** — including the LF line endings and
   `ensure_ascii=False`. Never hand-edit `openapi.json`; always regenerate.
5. **The C2 frontend gates** — six of them, all green today. This story adds no `.tsx` and no CSS, so
   any frontend gate that reddens is a real regression from the regenerated types, not noise.

### Source tree — what exists, what this story adds

```
src/companion/
  contracts.py            UNCHANGED — HealthResponse, ErrorReason (6 tokens), ErrorResponse
  app/
    main.py               EDIT — include the decks router ABOVE install_spa(app); comment repairs
    deps.py               EDIT (docstring only) — the /api/deck/{id} correction
    errors.py             EDIT (docstrings only) — c3-1 is no longer "not yet a caller"
    spa.py                EDIT (comment only) — /api now has routes
    routes/
      health.py           UNCHANGED — the pattern to copy (router, response_model, Google docstring)
      decks.py            NEW — the only new module in src/companion
src/data/schemas/
  deck.py                 EDIT — DeckSummary.from_deck / DeckDetail.from_deck move down here
src/mcp_server/tools/
  deck_management.py      EDIT — three call sites rewired; three private helpers deleted
scripts/dump_openapi.py   EDIT (docstring only)
tests/unit/companion/
  test_routes_decks.py    NEW
ui/src/api/openapi.json   REGENERATED (committed)
ui/src/api/types.d.ts     REGENERATED (committed)
ui/README.md              EDIT — the blind-spot map; the c3-1 fetch-layer sentence re-homed
```

**Not touched, deliberately:** `ui/src/App.tsx`, `ui/src/components/**`, `ui/src/api/schema.ts`,
`ui/tests/**`, `src/companion/app/security.py`, `src/companion/client.py`,
`src/companion/discovery.py`, `src/companion/app/static/**`, `plugin/**`.

### Previous story intelligence (c2-9 and c2-10, and the C2 retro)

- **Ten of ten C2 stories answered their open questions "as proposed."** The questions below are
  written to be answerable the same way — but landmine 10 (the projection move) is a genuine fork and
  is Q1.
- **The round-1 5/5 Greptile cause is thrice-confirmed:** the same-day three-layer
  `bmad-code-review` before raising the PR. It is a standing action item (retro #6). Task 6.
- **The recurring C2 review theme was "a guard proven only against spellings it lists, and the thing
  one layer above the tested thing unproven."** Applied here: the *thing one layer above* is
  `build_app()`'s router registration (AC 13) and the projection's **callers** (AC 9) — c2-9's own
  headline defect was wiring with no test, where reverting the wiring left 487 tests green.
- **c2-9's second self-found hole came from probing its own guard.** AC 16's plant-and-revert is that
  discipline applied to the one guard this story causes to grow.
- **c2-10 was the epic's one true-in-source/false-on-screen defect.** This story has no on-screen
  surface at all, which is why AC 18 keeps it that way rather than sneaking a render in.

### Git intelligence

- `02b2c45` — the C2 ship record; `a52d6f8` — integration PR #28 merged to master. The working tree
  is clean and `feat/companion-c3` is the umbrella.
- The C2 rhythm holds (ruled 2026-07-26, restated at the C2 retro): **story branch off the umbrella,
  story PR into the umbrella with a Greptile pass per story**, one integration PR to master after the
  retro with **no** Greptile pass (OSS free-tier budget). Merge ≠ release — no tag, no CHANGELOG
  until c8-4.
- Commit style: Conventional Commits, `feat(companion): …`.

### Gotchas specific to this story

- **`format` is a field name, not a builtin misuse.** `ruff`'s `N` rules are on and the project
  deliberately shadows `format` throughout for MTG-domain clarity (project-context.md). Keep it.
- **`FormatType = str | None`** generates `string | null` in TypeScript. That is correct — a deck can
  genuinely have no format, and c3-3's "no format to check against" response depends on it.
- **`DeckCardSummary.commander` defaults to `False`** and `DeckSummary`'s count fields default to `0`.
  Defaults are exactly what makes a silently-wrong projection possible (AC 3).
- **`Deck.color_identity` and `tags` arrive as JSON strings from the ORM** and are parsed by
  `field_validator(mode="before")`. Round-tripping through `from_deck` keeps that — do not
  reconstruct these fields by hand.
- **`uvicorn`'s request-line limit bounds the deck-id path segment**, so no explicit length cap is
  needed. Any string that is not a known deck id is simply `deck_not_found`; there is no
  `invalid_request` path on this route (c3-2's malformed-uuid 400 is c3-2's, because a card id has a
  declared shape and a deck id does not).
- **`mypy --strict` and `--platform win32`** are the gate (c2-1 closed that gap). Every function in
  `src/` needs full hints.
- **Async everywhere in `src/data`.** The route handlers are `async def` (FastAPI), unlike the MCP
  tools which are sync `def` by design. Do not copy the sync pattern across.

### Testing standards

- `pytest` config is in `pyproject.toml`; `asyncio_mode = "auto"` — write `async def test_…` with
  **no** `@pytest.mark.asyncio`.
- Layout mirrors `src/`: `tests/unit/companion/` for anything driven in-process over
  `httpx.ASGITransport`. This story adds **no** `integration`-marked test — AD-10 rules that exactly
  one such test exists in the whole feature and it belongs to **c5-8**.
- Reuse `lifespan_client` and `keep_spa_mount_last` from `tests/unit/companion/conftest.py`. Do not
  write a second seam.
- `tests.*` is exempt from `mypy --strict` but not from ruff or the naming rules.
- Paste real gate output. Claims require verification (standing agreement).

### Architecture rules this story implements

- **FR-02** — `GET /api/decks` lists decks; `GET /api/deck/{id}` returns a full decklist with card
  IDs, quantities, and metadata matching `load_deck` output.
- **AD-1** — sibling shells over one core; existing repositories and schemas; no second deck shape.
- **AD-2 / NFR-02** — read-only enforced by the CI import boundary.
- **AD-10** — lazy engine, absence is a served state; in-process testing over `ASGITransport`.
- **AD-12 / NFR-03** — one generator from the backend's own `app.openapi()`; committed, drift-checked.
- **AD-16** — HTTP-native REST, unwrapped bodies, closed reason tokens, one typed error body.

### References

- [epics-companion-app.md § Story 3.1](../planning-artifacts/epics-companion-app.md) — the ACs this
  story expands (lines 1548-1580), and the C3 epic framing (1541-1546)
- [epics-companion-app.md § Additional Requirements](../planning-artifacts/epics-companion-app.md) —
  AD-1/AD-2/AD-3 (192-205), AD-10 (207-222), AD-12 (291-302), AD-16 REST semantics (255-277)
- [ARCHITECTURE-SPINE.md:435](../planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md) ·
  [EPIC-SPLIT.md:61](../planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/EPIC-SPLIT.md) —
  the singular `/api/deck/{id}` spelling
- [prd.md:110](../planning-artifacts/prds/prd-Artificial-Planeswalker-2026-07-22/prd.md) — FR-02
  verbatim, including the "matching `load_deck` output" clause
- [EXPERIENCE.md:63](../planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md) —
  the no-active-deck panel's deck list is fed by `GET /api/decks` (**consumed by c4-2, not here**)
- [epic-c2-retro-2026-07-30.md](epic-c2-retro-2026-07-30.md) — R1/R2 (§ Rulings), action items 5 and
  6, the standing agreements, and the C3 preview (167-196)
- [c1-6 story record](c1-6-lazy-database-engine-so-a-fresh-install-starts-instead-of-erroring.md) —
  the seam this story consumes, and its Decide-once #1 ("this story ships the seam, not an endpoint")
- [c1-4 story record](c1-4-typed-rest-error-contract-with-closed-reason-tokens.md) — the token set,
  `error_responses`, and why the body carries no prose
- [c2-3 story record](c2-3-typescript-types-generated-from-the-backends-own-openapi-drift-checked-in-ci.md) —
  the type pipeline and its two-job split
- [project-context.md](../project-context.md) — layer boundaries, async rules, docstring style,
  `CARDS_DATABASE_URL`, ruff/mypy gates
- [deferred-work.md](deferred-work.md) — the `test_list_decks_with_strategy_field` flake (two entries)

---

## Open questions for Brad — answer before `dev-story`

**Q1 — The projection move (landmine 10, AC 9).** The count-computing helpers live in
`src/mcp_server/tools/deck_management.py:129-184` and the companion may not import them. Proposed:
**move them down to `src/data/schemas/deck.py` as `DeckSummary.from_deck()` / `DeckDetail.from_deck()`,
rewire the MCP's three call sites, and prove the move with the untouched MCP suite.** The cost is that
this story touches `src/mcp_server` and `src/data` — a wider blast radius than "add a route". The
alternative (a companion-local copy of the arithmetic) keeps the diff inside `src/companion` but
creates the second truth AD-1 exists to prevent. *Recommendation: as proposed.*

**Q2 — Bare array or wrapped object for `GET /api/decks`?** AC 1 proposes a **bare JSON array** —
AD-16 says success bodies are the existing schemas "unwrapped" and the AC says "no status envelope",
and a bare array is the honest HTTP-native reading. The known cost is that a top-level array leaves no
room to add pagination or a total without a breaking change. Nothing in the PRD, the UX contract or
Epic 4 asks for either (the deck count is single digits). *Recommendation: bare array; revisit only
if a real pagination need appears.*

**Q3 — Does c3-1 own the `ui/README.md` blind-spot map (AC 21)?** Retro action item 5 says *"Brad
(c3-1 or the first C3 frontend story)"*. c3-1 is backend-only and touches `ui/` for two generated
files. The first genuinely frontend C3 story is **c3-9**, which R2 already names as the epic's
heaviest and which is absorbing five deferrals. *Recommendation: c3-1 takes it — it is a docs-only
section, and putting it on c3-9 makes the heaviest story heavier for no gain.*

**Q4 — Should the four exposed schema docstrings be rewritten for a TypeScript reader (AC 17)?**
Their leading paragraphs — the part that crosses the wire as JSDoc and appears in `/docs` — currently
talk about LLM clients, `model_validate` and "the Story 1.6 deck-analysis tools". Rewriting the
summary and pushing the Python/MCP detail below an `Attributes:` header is a small change to
`src/data/schemas/deck.py` and `card.py`. The cost is touching shared schema docstrings on the same
commit as a route. *Recommendation: rewrite only the leading summary of the four schemas that
actually reach `components.schemas`; leave every other docstring alone.*

**Q5 — Is there anything the deck list should hide?** `DeckSummary` exposes `strategy` (free text the
user wrote) and `tags`. Both are the user's own data on a loopback-bound port, so there is no
disclosure concern — but the deck list is what the no-active-deck panel renders (`EXPERIENCE.md:63`,
"names only"), and shipping fields nothing renders is fine only if it is deliberate.
*Recommendation: expose the full `DeckSummary` — it is `load_deck`'s existing shape, c4-7's deck-list
panel will want more than names, and trimming it would be the second shape AD-1 forbids.*

---

## Dev Agent Record

### Agent Model Used

Claude Opus 5 (`claude-opus-5[1m]`), 2026-07-31.

### Open questions — Brad's answers

All five **as proposed** (the tenth story running). Q1 the projection moves down to
`src/data/schemas/deck.py`; Q2 bare JSON array; Q3 c3-1 takes the `ui/README.md` blind-spot map;
Q4 rewrite only the four exposed schemas' leading summaries; Q5 expose the full `DeckSummary`.

A **sixth** question was forced mid-implementation by a contradiction inside the story itself —
see Completion Notes finding 2. Brad ruled: **comment-only repairs, AC 20 wins.**

### Baseline (Task 0, measured — not assumed)

Branch `feat/companion-c3-1-deck-endpoints` cut off `feat/companion-c3` at `02b2c45`, clean tree.

| Gate | Baseline | After |
| --- | --- | --- |
| `uv run pytest` | **1798 passed, 1 skipped** (117.19s) | **1827 passed, 1 skipped** (128.27s) |
| `uv run ruff check .` | All checks passed | All checks passed |
| `uv run ruff format --check .` | 286 files already formatted | 289 files already formatted |
| `uv run mypy src/` | no issues in **84** source files | no issues in **85** source files |
| `uv run mypy src/ --platform win32` | (not in baseline) | no issues in 85 source files |
| `npm run lint` | clean | clean |
| `npm run format:check` | clean | clean |
| `npm run typecheck` | clean | clean |
| `npm test` | **549 passed** (28 files) | **549 passed** (28 files) |
| `npm run build` | green | green |

Python suite **+29** (the new `test_routes_decks.py` is 28, plus one new non-vacuity test in
`test_errors.py`). Frontend **unchanged at 549** — this story ships no frontend behaviour (AC 18);
its only `ui/` changes are the two generated files, `README.md`, and comment-only repairs.

`test_list_decks_with_strategy_field` (landmine 16's known flake) **passed** on the baseline run and
on every run since. Not hit once this session.

**Committed OpenAPI at baseline** — exactly as the story predicted:
`paths: ['/health']` · `components.schemas: ['ErrorResponse', 'HealthResponse']`.

**Bundle + `plugin/` mirror at baseline** (SHA-256, first 16):

```
0640890476FC1198  assets/space-grotesk-latin-wght-normal-BhU9QXUp.woff2
0A3C142D84B5A98D  assets/index-DmxBiI94.css
8E65C0615CF66044  index.html
9BE16EA2FE3670DE  favicon.svg
FAEEEA472ADD5078  assets/index-DE70muY2.js
```

Mirror at `plugin/server/src/companion/app/static/` measured **identical to the bundle** at
baseline, on all five files.

### Debug Log References

**AC 13 / AC 4 / AC 6 / AC 8 — the committed schema after regeneration:**

```
paths: ['/health', '/api/decks', '/api/deck/{deck_id}']
schemas: ['CardSummary', 'DeckCardSummary', 'DeckDetail', 'DeckSummary', 'ErrorResponse', 'HealthResponse']
detail responses: ['200', '400', '404', '413', '500', '503']
list   responses: ['200', '400',        '413', '500', '503']
```

Two schemas to six; the `404` is on the detail route and **not** on the list route.

**AC 15 — both drift gates, from the same tree:**

```
$ uv run pytest tests/unit/companion/test_openapi_contract.py
tests\unit\companion\test_openapi_contract.py ...........                [100%]
============================= 11 passed in 0.16s ==============================

$ npm run gen:types   # regeneration-stability, the meaningful form pre-commit
before: E881A71D44A70E2661AFBDBD4EC51AAD3F3C28D8783C86E300339002B06B1B64
after : E881A71D44A70E2661AFBDBD4EC51AAD3F3C28D8783C86E300339002B06B1B64
stable: True
```

The CI form is `npm run gen:types && git status --porcelain`. Run against an uncommitted tree it
reports this story's own edits, which is not drift — so the hash-stability form above is what was
measured pre-commit. **The CI form itself is run after the commit; its output is in the Review
section below.**

**AC 17 — what crosses the wire, scanned by family not by member:**

```
sphinx role markup family : clean
google section headers    : clean
Args:                  clean      Returns:               clean
Attributes:            clean      Raises:                clean
>>>                    clean      Yields:                clean
model_validate         clean      Example                clean
LLM client             clean      src/mcp_server         clean
Story 1.6              clean      pydantic               clean
lookup_card_by_name    clean
```

**AC 9 — no second implementation of the count arithmetic survives** (`src/` only; `plugin/` is a
generated mirror):

```
src\logic\deck_validator.py:303-304,404-405   <- DeckValidationReport, a DIFFERENT schema
src\data\schemas\deck.py:206-208, 262-264      <- TWO ranges, in ONE file
```

`deck_validator.py` is a pre-existing, unrelated shape (no `distinct_cards`) — a hit on the grep,
not a second truth. Nothing else in `src/` computes these counts.

**This evidence did not support the claim it was filed under, and the review caught it (R2).** Two
disjoint line ranges were labelled "the one implementation": `DeckSummary.from_deck` and
`DeckDetail.from_deck` each restated all eleven fields, exactly as the deleted `_deck_summary` /
`_deck_detail` pair had. The move preserved the duplication instead of collapsing it. **Repaired
during review** — the fields are now built once in `DeckSummary._summary_fields`, and
`DeckDetail.from_deck` extends that dict with `cards` rather than restating it. Re-run:

```
src\data\schemas\deck.py:198  "distinct_cards": len({dc.card_id for dc in deck.deck_cards}),
```

One line, one implementation.

**AC 11 — banned write-path and ceremony tokens across `src/companion/**.py`.** Scanned for
`create_deck`, `update_deck`, `delete_deck`, `add_card_to_deck`, `remove_card_from_deck`,
`update_card_quantity`, `update_deck_color_identity`, `merge_decks`, `session.add`,
`session.commit`, `session.delete`, `init_database`, `create_all`, `src.data.importers`,
`JSONResponse`, `status_code`, `try:`, `except`, `add_exception_handler`, `select(`, `text(`,
`session.execute`. Every hit is in a **pre-existing** file (`client.py`, `discovery.py`, `deps.py`,
`errors.py`, `main.py`, `security.py`, `server.py`, `singleton.py`, `spa.py`).
**`routes/decks.py` appears in no row** — the new module contains none of them.
`test_import_boundary.py`: **50 passed, unchanged, no exclusions added.**

### Review probe outputs

Six mutation probes. Every mutation was verified on disk before the verdict and every revert
verified after. **All six caught.**

**Probe 1 — the router silently unregistered** (c2-9's headline defect reproduced in this story's
shape: wiring with no test):

```
19 failed, 9 passed
```

The 9 that survived read the *committed schema file* rather than the app, which is correct — they
target a different artefact. Every route-driving test went red.

**Probe 2 — `DeckDetail.model_validate(deck)` instead of `from_deck`** (the silent-zero counts,
AC 3's whole reason to exist):

```
4 failed, 24 passed
FAILED ... TestDeckDetail::test_counts_are_computed_not_defaulted
FAILED ... TestDeckDetail::test_returns_the_whole_decklist
FAILED ... TestDeckDetail::test_sideboard_and_commander_flags_survive_the_projection
FAILED ... TestDeckDetail::test_each_entry_nests_a_card_summary
```

**Probe 2b — the same defect on the *list* route**, the half probe 2 left untouched:

```
tests\unit\companion\test_routes_decks.py:221: in test_the_list_carries_computed_counts_too
    assert body[0]["mainboard_count"] == 3
E   assert 0 == 3
1 failed, 27 passed
```

`assert 0 == 3` is the exact failure mode landmine 10 describes. Both routes proven independently —
probe 2 alone would have left the list route's projection unproven.

**Probe 3 — the path spelled `/api/decks/{deck_id}` (plural), without regenerating:**

```
committed-schema tests : 4 passed      <- they read the committed file, which is still right
the drift gate         : 1 failed      <- test_committed_schema_matches_the_live_app
```

**Probe 3b — the same wrong path, *with* regeneration**, closing the chain:

```
drift gate              : 11 passed    <- now consistent...
committed-schema tests  : 3 failed     <- ...and the path assertion catches it
E   KeyError: '/api/deck/{deck_id}'
```

Whichever way a wrong path is taken, something is red. Neither test alone is sufficient; together
they are complete.

**Probe 4 — `responses=error_responses("deck_not_found")` removed, regenerated:**

```
E   AssertionError: assert '404' in {'200': ..., 'description': 'reason: internal_error'}, ...}
1 failed, 3 passed
```

**Probe 5 — a companion-local second deck shape** (the AD-1 violation AC 8 exists to catch). First
attempt planted a bare `BaseModel` in a new module and **did not fire** — a Pydantic model no route
references never enters `components.schemas`. That is correct behaviour, not a hole (a shape nothing
serves is not a second truth *on the wire*), but it is a **declared limit worth knowing**: AC 8
catches a duplicate shape only once something serves it. Re-run with the model actually returned by
a route:

```
E     Extra items in the left set:
E     'DeckBlurb'
1 failed, 3 passed
```

**Probe 6 — the wire-contract guard (AC 16), plant-and-revert.** Note the guard is keyed on
`git ls-files`, so the plant had to be **staged** to be visible — an untracked file passes
vacuously, which is that guard's own declared limit (now in the README blind-spot map). Planted all
four new shapes in `ui/src/_probe_wire.ts`:

```
 ❯ tests/wire-contract.test.ts (3 tests | 1 failed)
     × declares no wire shape outside src/api/
+   "src/_probe_wire.ts declares CardSummary",
+   "src/_probe_wire.ts declares DeckCardSummary",
+   "src/_probe_wire.ts declares DeckDetail",
+   "src/_probe_wire.ts declares DeckSummary",
 Tests  1 failed | 548 passed (549)
```

All four caught **by name**, which is a stronger proof than an assertion that `wireShapes` contains
`DeckSummary` — it demonstrates the ban itself grew, with **no edit to `wire-contract.test.ts`**.
At the time of this probe, AC 16's suggested assertion was deliberately *not* added, on the
reasoning that adding it would edit the file the AC says must not be edited. **That reasoning was
later overturned by review finding R7** (the file already carries a `HealthResponse` anchor of
exactly that kind; landmine 14 bans enumerating the *ban list*, not the anchor), and the two
`toContain` anchors were added. The final state takes AC 16's mechanism-untouched horn over its
literal "no edit to that file" clause — `bannedShapes` stays derived; only non-vacuity anchors
were added.

Reverted (unstaged and deleted), then re-run:

```
 Test Files  28 passed (28)
      Tests  549 passed (549)
```

### Completion Notes List

**What shipped.** Two read-only routes in one new 71-line module, the `Deck → DeckSummary/DeckDetail`
projection moved down into `src/data/schemas/deck.py` as `from_deck` constructors shared by both
shells, 28 new tests, the regenerated wire contract (two component schemas to six), and the
`ui/README.md` blind-spot map. The route bodies are two repository calls; almost everything else was
consuming a seam nineteen stories had already built — and proving it consumed rather than
reimplemented.

**Five findings, three of them corrections to the story's own text.**

1. **`plugin/**` had to change, and the story said it must not.** The Dev Notes list
   `plugin/**` under "Not touched, deliberately". That is **wrong for this story**: CI's
   *"Plugin tree in sync with src/"* step (`.github/workflows/ci.yml:76-84`) re-runs
   `scripts.build_plugin` and fails on any drift, and Task 1 edits two mirrored `.py` files.
   Leaving the mirror stale would have been a guaranteed red build. Rebuilt and committed —
   7 modified files plus the new `routes/decks.py` under `plugin/server/`. **AC 19 is still
   satisfied and was still measured**: it is about the *static SPA bundle*, which is byte-identical
   (below); the `.py` mirror is a different artefact the AC did not contemplate.

2. **AC 18 and AC 20 contradict each other.** AC 18: *"the only `ui/` changes permitted by this
   story are the two generated files and `ui/README.md`"*. AC 20 rows 7 and 9: repair the
   forward-dated comments in `ui/src/api/schema.ts`, `ui/src/App.tsx` and
   `ui/src/components/StatePanel/StatePanel.tsx`. Raised to Brad rather than resolved silently,
   because those comments say something **false** — App.tsx and StatePanel.tsx both claim *"c3-1
   owns the fetch layer"*, which was never true (AC 18 itself says c4-1 owns it) and is now
   actively misleading to c4-1/c4-2. **Brad ruled: comment-only repairs, AC 20 wins.** No JSX, no
   imports, no behaviour — which is AC 18's real intent, and the frontend suite is unchanged at 549.

3. **Sphinx role markup crosses the wire, and AC 17's search list does not name it.** After
   regeneration, `types.d.ts` was clean on all seven strings AC 17 lists — but carried
   `` :class:`DeckSummary` `` twice, from my own new `DeckDetail` docstring. Checked against the two
   already-shipped descriptions: `HealthResponse` and `ErrorResponse` both use double-backtick
   reST (so that *is* house style) and **neither uses role markup**. Fixed at the docstring and
   regenerated. The scan was then re-keyed on the **family** (`:[a-z]+:` before a backtick, plus a
   generic Google-section-header pattern) rather than the members AC 17 lists — the standing
   *ban the family, never enumerate members* agreement. Recorded in `deferred-work.md` with **c3-2**
   as the home for deciding whether this deserves a gate.

4. **Two pre-existing structural pins broke, and both were right to break.** My routes are the
   first to exercise them:
   - `test_errors.py::test_every_success_body_is_a_component_ref_never_an_envelope` asserted
     `set(body["schema"]) == {"$ref"}`. A bare array (`list[DeckSummary]`) is
     `{"type": "array", "items": {"$ref": ...}}` and failed. The pin's own comment states its
     intent — ban a *hand-built envelope*, require a declared `response_model` — and a bare array
     satisfies that intent; the implementation was simply written when the only body was a single
     object. Replaced with `_is_ref_rooted()`, keyed on the family *"the schema bottoms out in a
     `$ref`"*, so `list[list[X]]` is admitted while an array **of** an inline envelope is still
     refused. Given its own firing/silent table (six cases) plus three named non-vacuity anchors.
   - `test_spa.py`'s two schema tests hardcoded `{"/health"}`. Repaired to their actual claims: the
     mount-leak test now asserts the mount's own path shape is absent (with a non-vacuity check that
     there *are* paths), and the differential test registers both routers. Neither now rots when a
     story adds a route — but the differential's router list is deliberately coupled to
     `build_app()`, and says why: a forgotten line there is a cheap red test, versus a mount
     silently swallowing a route.

5. **A forward-dated comment that became true on its own.** `StatePanel.tsx:135` says index keys are
   used because *"nothing in the prop contract forbids two decks sharing a name (the names are
   user-authored, c3-1 delivers them as bare strings)"*. That is now confirmed accurate — deck name
   is not unique in the schema and `DeckSummary.name` is a plain string. Left unedited: AC 20 permits
   "becomes true" as an outcome, and this is one.

**AC 19 — bundle and mirror re-measured, not assumed.** All five files byte-identical to the Task 0
hashes, and `git status --porcelain` is empty for both `src/companion/app/static/` and
`plugin/server/src/companion/app/static/`. As predicted: `types.d.ts` is type-only and erased at
build, and the `ui/src` edits were comment-only (esbuild strips comments).

**AC 20 — the nine-row forward-dated-comment table, all worked:**

| # | Location | Action taken |
| --- | --- | --- |
| 1 | `deps.py:285` | **Corrected** — `/api/decks/{id}` → `/api/deck/{id}`, with the five artefacts that agree named |
| 2 | `spa.py:59-66` | **Updated** — `/api` has routes now; the seed **stays**, and the comment now says what it is still for (a tree with no `/api` route) rather than repeating a prediction |
| 3 | `main.py:396` | **Updated** — c3-1 done, c5-2/c5-5 remain; "not hypothetical any more" |
| 4 | `errors.py:64-66` | **Updated** — c1-6 and c3-1 now named as actual callers, c5-5 still to come |
| 5 | `errors.py:128` | **Updated** — names the detail route *and* records that the list route deliberately declares nothing |
| 6 | `dump_openapi.py:21` | **Updated** — done, two-to-six recorded, **c3-2 named next** |
| 7 | `schema.ts:18` | **Prose updated** — "it did exactly that, with no edit to the test"; mechanism untouched |
| 8 | `ui/README.md:912` | **Re-homed** to c4-1 (fetch layer + store) and c4-2 (deck bootstrap) |
| 9 | `App.tsx` ×3, `StatePanel.tsx` ×2 | **Re-homed** to c4-1/c4-2 per Brad's ruling (finding 2). A sixth, `StatePanel.tsx:135`, became true — see finding 5 |

**AC 21 — the blind-spot map is in `ui/README.md` under "What the gates cannot see"**, eleven rows,
each naming its guard file and line and who owns the other half. Every entry was **verified against
the guard's own source** rather than taken from the AC's list, which surfaced **one** correction to
the AC text: the unstacked-curve-bar rule is **UX-DR7**, not UX-DR47 (UX-DR47 is an unrelated
a11y/hover-affordance rule). The section leads with c2-6's lesson — *a declared blind spot is still a
claim* — and closes with the two backend guards, including the `openapi.json` gate's inability to see
meaning (finding 3).

*(An earlier draft of this record claimed a second correction — that the AC mislocated the
cascade guards in a fonts/typography file. The review checked: AC 21 names no file for any entry,
so there was nothing to correct. The misattribution was mine, in the research prompt, not the
story's. Claim withdrawn.)*

**What this story deliberately did not do.** No error token added (`deck_not_found` already shipped;
`card_not_found` is c3-2's under retro R1). No `try`/`except` and no `add_exception_handler` in the
diff — both 503 paths are inherited and proved *through the real routes* on **both** endpoints. No
`select()`/`text()`/`session.execute` in `src/companion`. No fetch layer, no store, no alias export,
no component, no token, no dependency. The `list_decks` over-fetch was **accepted, not fixed** — a
count-only query would be a second read path over one shape.

### File List

**New**

- `src/companion/app/routes/decks.py`
- `tests/unit/companion/test_routes_decks.py`

**Modified — source**

- `src/companion/app/main.py` (router registration above `install_spa`, import, comment repair)
- `src/companion/app/deps.py` (docstring only — the `/api/deck/{id}` correction)
- `src/companion/app/errors.py` (docstrings only — c1-6/c3-1 are callers now)
- `src/companion/app/spa.py` (comment only — `/api` has routes; the seed stays, with its reason)
- `src/data/schemas/deck.py` (`_counts` + `DeckSummary.from_deck` + `DeckDetail.from_deck`; the four
  wire-facing docstrings rewritten for a TypeScript reader)
- `src/data/schemas/card.py` (`CardSummary` docstring rewritten for a TypeScript reader)
- `src/mcp_server/tools/deck_management.py` (three call sites rewired; three private helpers deleted;
  unused imports and module docstring updated)
- `scripts/dump_openapi.py` (docstring only)

**Modified — tests**

- `tests/unit/companion/test_errors.py` (`_is_ref_rooted` + its firing/silent table; three
  non-vacuity anchors)
- `tests/unit/companion/test_spa.py` (two schema pins repaired; `decks` router registered in the
  differential)
- `ui/tests/wire-contract.test.ts` (review R7 — two non-vacuity `toContain` anchors beside the
  existing `HealthResponse` anchor; the derived ban mechanism is untouched)

**Modified — generated / frontend**

- `ui/src/api/openapi.json` (regenerated — 2 schemas → 6, 1 path → 3)
- `ui/src/api/types.d.ts` (regenerated)
- `ui/README.md` (the "What the gates cannot see" section; two forward-dated re-homings)
- `ui/src/api/schema.ts`, `ui/src/App.tsx`, `ui/src/components/StatePanel/StatePanel.tsx`
  (**comment-only**, per Brad's ruling on the AC 18 / AC 20 conflict)

**Modified — plugin mirror** (generated by `scripts.build_plugin`; required by the CI drift gate)

- `plugin/server/src/companion/app/routes/decks.py` (new), `.../app/deps.py`, `.../app/errors.py`,
  `.../app/main.py`, `.../app/spa.py`, `plugin/server/src/data/schemas/card.py`,
  `.../schemas/deck.py`, `plugin/server/src/mcp_server/tools/deck_management.py`

**Modified — records**

- `_bmad-output/implementation-artifacts/deferred-work.md` (4 entries with named homes)
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `_bmad-output/implementation-artifacts/c3-1-deck-list-and-deck-detail-endpoints.md`

### Code review (three-layer, same-day, 2026-07-31)

`bmad-code-review` — Blind Hunter + Edge Case Hunter + Acceptance Auditor, launched in parallel with
no shared context, against `git diff 02b2c45`. **~40 raw findings, 14 patches applied, 8 ledgered,
1 decision for Brad.** Every disputed claim was re-measured locally before acting on it; two agent
claims were checked and one was corrected (see "not accepted" below).

**The theme, and it is uncomfortable: the story's own evidence contained the refutation of two of its
claims, and I read past both.** Probe 1's "19 failed, 9 passed" — I attributed the 9 passes to schema
tests without checking which they were. Three of them were the AC 13 tests, which passed *because
they were vacuous*. And the AC 9 grep I pasted showed two line ranges under a caption reading "the
one implementation".

**Patches applied (14):**

| # | Sev | Finding | Fix |
| --- | --- | --- | --- |
| R1 | **High** | **`TestNotShadowedBySpa` passed with the router deleted.** `/api` is in `spa.py`'s `_RESERVED_SEED`, so an unrouted `/api/decks` is refused by the mount and answered `404 application/json {"reason": "invalid_request"}` — JSON, no doctype. Both tests asserted only content-type and absence of doctype, so AC 13 had no test at all | Assert **status and body**; added a third test pinning the unrouted-`/api` outcome as the live contrast case. **Re-probed: both now fail with the router removed** |
| R2 | **High** | **AC 9's "exactly one implementation" was not achieved.** `DeckSummary.from_deck` and `DeckDetail.from_deck` each restated all eleven fields — the same duplication the deleted `_deck_summary`/`_deck_detail` pair had. Adding a `DeckSummary` field would have silently defaulted it on the detail route | Fields built once in `DeckSummary._summary_fields`; `DeckDetail.from_deck` extends that dict with `cards`. The count arithmetic is now one line |
| R3 | **High** | **Nothing tied the nested `CardSummary` to its entry.** Mutation-tested by the reviewer: every entry nesting the *wrong* card left all 28 tests green, because every seeded card was identical on the fields asserted | Fixture cards now differ per card (`mana_cost`, `type_line` derived from id); new `test_each_entry_nests_its_own_card` asserts `card.id == card_id` **and** a second independent link, with a non-vacuity check that the entries genuinely differ. **Re-probed: the mutation now fails** |
| R4 | **High** | **`DeckDetail`'s docstring claimed cards come back "in the order the deck stores them". They do not.** Measured: inserted `zzz, mmm, aaa` → returned `aaa, mmm, zzz`. The relationship declares no `order_by`, so entries arrive in composite-PK (`card_id`) order — a Scryfall UUID, i.e. arbitrary | Both docstrings corrected to state the order is not meaningful and a consumer must sort. The ordering itself is `src/data` with MCP blast radius — not changed here |
| R5 | Med | **A brand-new forward-dated comment was wrong — the exact defect this story was chartered to fix.** `dump_openapi.py` named c3-2's route `/api/card/{card_id}` (singular) while five artefacts *and `deps.py` in the same diff* say `/api/cards/{card_id}` | Corrected to plural |
| R6 | Med | **`main.py`'s new comment overclaimed.** It said the shadowing hazard is "not hypothetical any more" and cited `GET /api/decks` as proof — but `/api` is the one prefix structurally immune to it (R1) | Rewritten: names the belt-and-braces, says it does **not** generalise, and cites c5-5's novel `/agent` prefix as the real hazard |
| R7 | Med | **AC 16's non-vacuity assertion was omitted on reasoning that does not hold.** I argued adding it would edit the file the AC forbids editing — but `wire-contract.test.ts` *already* contains `expect(wireShapes).toContain('HealthResponse')` as exactly that anchor. Landmine 14 bans enumerating the **ban list**, not the anchor | Added `toContain('DeckSummary')` / `toContain('DeckDetail')` beside the existing anchor, with a comment distinguishing the two. `bannedShapes` stays derived |
| R8 | Med | **`_is_ref_rooted`'s array branch had an unprobed evasion** — it checked `type == "array"` without rejecting a sibling `properties`, so an array *of* an inline envelope passed | Keyed on an object-shaping **family** (`properties`, `additionalProperties`, `allOf`, `anyOf`, …). First attempt was too strict and broke on FastAPI's generated `title` — caught by the suite, and both cases are now in the proof table |
| R9 | Med | **The "non-vacuity" pair in `test_the_component_names_are_exactly_these` was tautological.** `"HealthResponse" in names` and `len(names) == 6` after `names == {six}` are logically implied and can never fail independently | Anchors moved **before** the equality, where they can genuinely fail, with messages |
| R10 | Low | **The `ready_db` fixture did not make anything ready** — it only set the env var, so a test that forgot `_ready_database` got `503`, which for the several tests asserting on 503/404 bodies is a plausible false green | The fixture now builds the database; the redundant per-test calls are gone |
| R11 | Low | **`test_a_healthy_database_answers_normally` accepted `200 or 404`**, so the detail half reduced to "is not one of two bodies" — a handler that 404'd unconditionally would pass | Asserts the exact expected answer per path |
| R12 | Low | **`read_deck`'s docstring claimed there is "no separate malformed-id answer". Measured false**: `GET /api/deck/a%2Fb` → `404 invalid_request`, because Starlette decodes `%2F` before matching | Docstring now states the routing-level case explicitly |
| R13 | Low | **`read_decks`' docstring said the list renders "without fetching any deck"**, which the eager-load contradicts | Reworded to "without transferring any decklist", with the cost recorded — see R14 |
| R14 | Low | **The fix for R13 put internal detail on the wire.** I wrote it as a `Note:` — and `Note:` is one of the two headers `main.py` deliberately does **not** truncate, so "deferred-work.md" and "c10-3" crossed into `types.d.ts` and `/docs`. Caught by re-running my own AC 17 scan, which flagged the new `Note:` | Moved into a code comment, which never crosses the wire. The comment says why |

**Ledgered, not fixed (8)** — all in `deferred-work.md` under "code review of c3-1", each with a
named home: the `pydantic.ValidationError` escape (no handler in the companion stack; **measured
four triggers** — orphaned row, `quantity < 1`, non-string JSON elements — with a **whole-list blast
radius** on `GET /api/decks`; pre-existing, already the `data-layer-orphan-handling` backlog item,
and AC 12 forbids fixing it in a route body); the `503 database_not_initialized` documentation gap
(**decision for Brad**, below); `from_deck`'s silent zero counts on a non-eager-loaded `Deck` (now
documented in both `Args:` blocks, but the structural fix is a `src/data` change); `HEAD` → `405`
(pre-existing — `/health` behaves identically, so it needs one decision covering every route); the
request-long SQLite SHARED lock with no WAL pragma; the `Attributes:`-as-truncation-marker hazard
(the shared core's docstring *structure* is load-bearing for a companion-only rule that `src/data`
never mentions); the README blind-spot index being line-number-keyed with no gate; and
`test_spa.py`'s new hand-synchronised router list as a standing tax on c3-2…c5-5.

**Not accepted (1).** The Acceptance Auditor reported that AC 21's own text mislocated the
cascade-blindness guards in a fonts/typography file. Checked: AC 21 names no file for any entry, so
there was nothing to correct — the misattribution was mine, in the research prompt. **My "two
corrections to the AC text" claim was overstated and is withdrawn**; the UX-DR7/UX-DR47 correction is
real and verified. The auditor also flagged AC 25's evidence as paraphrased rather than pasted, which
is fair and is why the gate output below is literal.

**Decision for Brad (1) — the undocumented 503.** Both routes can answer
`503 database_not_initialized`, and the committed schema's `503` says only `database_unavailable`,
because `build_app()`'s app-level `error_responses(...)` never passes the token. On a fresh install
this is the **most common 503 the UI will see**, and `error_responses`' advertised
tokens-sharing-a-status collapse has therefore never fired. Not fixed unilaterally: AC 5 says "do not
add `database_not_initialized` app-wide as a side effect of this story", and declaring it per-route
deviates from AC 6. Ledgered and homed at c3-9 pending a ruling.

**Post-patch gates, from commit `8c0164f`:**

```
$ uv run ruff check .                 All checks passed!
$ uv run ruff format --check .        289 files already formatted
$ uv run mypy src/                    Success: no issues found in 85 source files
$ uv run mypy src/ --platform win32   Success: no issues found in 85 source files
$ uv run pytest                       1829 passed, 1 skipped in 81.03s

ui/ $ npm run lint          (clean)
ui/ $ npm run format:check  All matched files use Prettier code style!
ui/ $ npm run typecheck     (clean)
ui/ $ npm test              Test Files 28 passed (28) / Tests 549 passed (549)
ui/ $ npm run build         built in 103ms

# AC 15, both drift gates in their CI form, from the same commit:
$ uv run pytest tests/unit/companion/test_openapi_contract.py
  11 passed in 0.13s
ui/ $ npm run gen:types && git status --porcelain
  (no output — no drift)
```

Python **1798 → 1829** (+31). Frontend unchanged at **549** — R7's two assertions joined an existing
`it` block. `test_list_decks_with_strategy_field` (landmine 16's known `created_at` tie flake) **hit
once** during the post-patch sweep and passed on re-run in isolation, as its ledger entry predicts —
the third confirmation, not a regression.

### Change Log

| Date | Change |
| --- | --- |
| 2026-07-31 | Story contexted off `02b2c45`; 19 landmines, 25 ACs, 5 open questions |
| 2026-07-31 | Implemented off `02b2c45` on `feat/companion-c3-1-deck-endpoints`. All 5 open questions "as proposed"; a 6th (AC 18 vs AC 20) raised and ruled comment-only-repairs. Python 1798 → 1827, frontend unchanged at 549, nine gates green, bundle + mirror byte-identical, plugin `.py` mirror rebuilt. Six mutation probes, all six caught |
| 2026-07-31 | Three-layer code review: ~40 findings → 14 patches, 8 ledgered, 1 decision for Brad, 1 agent claim rejected. Headlines: the AC 13 tests were vacuous (proven by re-probe), AC 9's "one implementation" was two, and nothing tied a nested card to its entry. Committed `8c0164f`; both drift gates green in CI form. Python 1829, frontend 549. Status → review |
| 2026-07-31 | Post-commit three-layer review over both commits: 0 code defects in the shipped routes; 9 patches (2 wire-docstring honesty fixes + regeneration, 4 record repairs, 3 test additions), 2 deferred, 7 dismissed as already-ledgered/ruled. See § Review Findings |
