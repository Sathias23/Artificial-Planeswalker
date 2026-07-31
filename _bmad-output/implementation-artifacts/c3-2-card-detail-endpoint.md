---
epic: c3
story: c3-2
work_branch: feat/companion-c3
story_branch: feat/companion-c3-2-card-endpoint
depends_on: c3-1 (PR #29, merged into the umbrella at b0fd39b) — the routes package, the wire pipeline and the DbSession pattern all exist
baseline_commit: b0fd39b
---

# Story C3.2: Card detail endpoint

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As the browser UI,
I want canonical card data for any printing id,
so that I can hydrate names, costs, type lines, oracle text and prices for cards a payload
referenced only by id.

**What this story really is.** The route itself is four lines — `CardRepository.get_by_id` already
returns the exact schema the AC asks for, so there is no projection to move and no second shape to
resist (contrast c3-1's landmine 10, which was the whole story). **What makes this story is that it
is the first since c1-4 to extend a closed set.** `ErrorReason` goes from six tokens to seven, and
that single `Literal` edit ripples into **seven** places across two languages — four of them fail a
gate if missed, and **two of those four `npm test` will not show you**, because they fail under
`tsc` only.

Three things follow from that, and they are the story:

1. **The seventh token has a retro ruling attached.** C2 retro **R1** (Brad, 2026-07-30): *"c3-2
   does not merge with the token alone."* AD-16's extension rule is that a token and the UI state
   it drives land together; C1 shipped `internal_error` alone and it cost c2-9 a repair AC. R1's
   success criterion is that this story's record carries a **verbatim `EXPERIENCE.md` row** for
   `card_not_found` and that the token and its copy land in **one commit**.
2. **The copy that row names is not a state panel, and the copy gate cannot see it.** The row
   exists already, and it excludes itself from `copy.test.ts` **by structure** — deliberately.
   Satisfying R1 therefore cannot mean "add a `STATE_COPY` entry"; see landmines 11 and 12, and Q3.
3. **Two convention decisions are homed here by name** in `deferred-work.md` — the
   `Attributes:`-as-truncation-marker hazard and the "`openapi.json` gate cannot see meaning"
   question — both filed with *"Home: c3-2, the next story to add a schema to
   `components.schemas`"*. This is that story. It exposes `Card`, whose docstring is the exact
   Python-internal prose c3-1 had to rewrite four times.

**Twenty things were measured on this machine at `b0fd39b` — do not rediscover them.** Nine of
them are counts taken from the real 38,261-row card database.

### The seam that already exists (do not rebuild any of it)

1. **There is no projection to write.** `CardRepository.get_by_id(card_id)`
   (`src/data/repositories/card.py:126-151`) already returns `Card | None` via
   `Card.model_validate(card_model)`, and `src/mcp_server/tools/card_lookup.py:17,38` already
   returns that same `Card` verbatim to the MCP shell. **One repository call, one response model,
   no `from_deck`-style constructor, no counts.** AD-1 is satisfied by doing nothing.

2. **The response model is `src.data.schemas.card.Card`** — not `CardSummary`. The AC requires
   `image_uris` and `card_faces`, and `CardSummary` (`card.py:91-133`) omits exactly those plus
   `legalities` "so a response carrying many cards stays small". `CardSummary` is already on the
   wire from c3-1; `Card` is the **seventh** component schema.

3. **`RequestValidationError → 400 invalid_request` is already registered.**
   `validation_error_handler` (`errors.py:222-247`) replaces FastAPI's 422 and logs the detail
   instead of returning it. A path-param constraint failure lands there **automatically**. Do not
   write a manual 400, do not `raise HTTPException`, do not `try`/`except`.

4. **The auto-422 cannot resurrect itself in the schema.** `without_auto_validation_schema`
   (`errors.py:163-198`) strips FastAPI's `HTTPValidationError` response at schema-build time for
   every current and future route — added precisely because *"the first validated route silently
   resurrected the auto-422"* (Greptile, PR #12). **This story is that first validated route in
   `/api`.** Assert the 422 is absent from the generated path; do not re-solve it.

5. **`DbSession` is the only session source** (`deps.py:282`). Annotate. No engine construction, no
   `is_database_initialized` call, no `request.app.state` read. Both 503 paths — `503
   database_not_initialized` from `get_session` and `503 database_unavailable` from
   `install_error_handling` — are inherited with **no per-route ceremony**. A `try/except
   DatabaseError` in a route body is a regression, not defence.

6. **`error_responses(...)` is the per-route declaration helper** (`errors.py:122-154`), and its
   docstring at `:130` already names c3-2 as a caller. Use
   `responses=error_responses("card_not_found")`. Do **not** re-declare `invalid_request` per route
   — `build_app()` declares it app-wide (`main.py:381-384`), so the 400 is already documented, and
   c3-1's AC 6 established that a route declares only what it uniquely produces.

7. **The router must be registered ABOVE `install_spa(app)`** (`main.py:394-408`, `MUST STAY
   LAST`). `/api` is additionally covered by `spa.py`'s `_RESERVED_SEED`, but `main.py:400-404`
   states explicitly that the belt-and-braces **does not generalise** and the ordering rule is
   stated for every router. `test_spa.py::TestMountOrdering` fails with instructions if the line
   moves.

8. **`tests/unit/companion/test_spa.py:305` carries a hand-synchronised router list** and
   `deferred-work.md` names **c3-2 first** in the list of stories that must add a line to it:
   *"Every future route-adding story (c3-2, c3-3, c3-4, c3-5, c5-2, c5-5) must add one line there
   or get a red."* The differential test builds a mount-free app that must mirror `build_app()`'s
   routers by hand. Forgetting it is a named red, not a silent pass.

9. **The test seam is `lifespan_client` + `isolated_data_dir` + `_point_at`**
   (`tests/unit/companion/conftest.py:158-168`, `test_routes_decks.py:41-49`). Every companion test
   flows through the real security envelope; `httpx.ASGITransport` alone sends no lifespan messages
   and yields `500 internal_error`. `is_database_initialized` needs the **full schema plus at least
   one card row**, so build fixtures with `init_database(create_engine(url))`.

### The one real theme: extending a closed set

10. **The token edit touches seven places. Four fail a gate; two of those fail under `tsc` only.**
    Work them as one list, in one commit:

    | # | Location | What must change | How it fails if missed |
    | --- | --- | --- | --- |
    | 1 | `src/companion/contracts.py:46-53` | `ErrorReason` gains `"card_not_found"` | Nothing — this is the source |
    | 2 | `src/companion/contracts.py:61` | *"Story c3-2 adds `card_not_found` the same way; nothing else does"* → past tense, closed at **seven** | No gate. A stale prediction, and this repo repairs those |
    | 3 | `src/companion/contracts.py:88-103` | `ErrorResponse`'s "what each token means on the glass" bullet list gains a seventh bullet | No gate. The list is the *reason the set is closed*; a token with no bullet is the `internal_error` mistake again |
    | 4 | `src/companion/app/errors.py:45-52` | `STATUS_BY_REASON["card_not_found"] = 404` | `test_errors.py::test_every_token_has_a_status_and_no_token_is_invented` — **red** |
    | 5 | `tests/unit/companion/test_errors.py:120-131` | `test_the_token_set_is_exactly_these_six` → seven; the comment at `:123` (*"c3-2's `card_not_found` is the only remaining planned addition"*) becomes "closed at seven, nothing planned" | **Red** — deliberately, that is AD-16's "failing test attached" |
    | 6 | `ui/src/api/schema.test.ts:41-49` | The seven-token `expectTypeOf` union; the comment at `:40` says this line is edited by exactly this story | **`npm run typecheck` only.** `npm test` stays green — the file's own header says so in bold |
    | 7 | `ui/src/components/StatePanel/states.ts:44-72` | `PANEL_FOR_REASON` gains a `card_not_found` entry, or `satisfies Record<ErrorReason, StateKey \| null>` fails | **`npm run typecheck` only.** This is c2-9's probe 4 coming true |

    **`npm test` green is not evidence for rows 6 and 7.** `expectTypeOf` erases to an empty test
    body (`schema.test.ts:6-14`, with a measured example), and `satisfies` is compile-time. Run
    `npm run typecheck` and paste it.

11. **`card_not_found` maps to no state panel — and that is a THIRD meaning of `null`, not the
    existing one.** `PANEL_FOR_REASON` currently uses `null` for `invalid_request` and
    `payload_too_large` under the caption **"NO PANEL, BY DESIGN"**, and the comments say why: for
    one there is nothing the user can do, for the other the *agent* is the audience. `card_not_found`
    is neither. It has a **named UI destination** — `EXPERIENCE.md`'s Card placeholder, unknown
    variant, owned by **c4-3** — it is just not a *panel*. Writing `card_not_found: null` beside
    those two with no distinction discards exactly the pairing R1 exists to force. See Q3.

12. **R1's copy row already exists, and the verbatim gate deliberately cannot see it.**
    `EXPERIENCE.md:69`, quoted here byte-for-byte because R1's success criterion is that this record
    carries it:

    > `| Unknown card in a view | Placeholder label: "Unknown card" + truncated ID. No banner, no apology — the rest of the view renders normally. |`

    And the adjacent State-Patterns row (`EXPERIENCE.md:126`): *"Unknown card in a push | Agent view
    | Unknown-card placeholder for that entry only; the push never fails wholesale (FR-13)."*

    `ui/tests/copy.test.ts`'s `readArtefact` selects a row as *"any table line that writes both a
    quoted `Headline:` and a quoted `Body:`"*, and its docstring at `:66` **names this row** as one
    of the three that *"exclude themselves without a skip list"*. So the c2-9 mechanism is
    structurally unavailable here: this copy is a placeholder **label**, not a two-field panel. A
    `STATE_COPY` entry would be wrong twice over — `StateKey` is the panel vocabulary, and
    `EveryPanelHasASource` would then demand a source for a panel that does not exist.

13. **There are no price fields anywhere in this project, and there never have been.** Measured:
    `CardModel` (`src/data/models/card.py`) declares no price column; `Card`
    (`src/data/schemas/card.py:8-88`) declares no price field; a repo-wide grep for `price` over
    `src/`, `tests/`, `ui/src` and `scripts/` returns **zero** hits; and the 2026-07-11 PRD recon
    memlog records it directly — *"ABSENT: game_changer, edhrec_rank, saltiness, prices"*. FR-17 and
    `EXPERIENCE.md:86` both say **"prices if present in local data"**, and they are never present.

    So the epic's price AC is satisfied **by absence**, and the honest deliverable is a recorded
    measurement — **not** a nullable `prices` field that would be `null` on 100 % of responses
    (wire noise the UI must branch on for nothing), and **not** a Scryfall price import (a `src/data`
    column + importer + hand-written migration, i.e. its own story). See Q4.

### What the real data says (measured on the 38,261-row database, read-only)

14. **Every card id is a canonical lowercase hyphenated UUID. Zero exceptions in 38,261 rows.** So
    "malformed card id → 400" is genuinely decidable — unlike a deck id, which c3-1 correctly ruled
    has no declared shape. **But `uuid.UUID` as a path-parameter type is the wrong gate**: Python's
    `uuid.UUID` accepts 32-hex-without-dashes, `{braced}`, `urn:uuid:` and uppercase, and
    *normalises* them — so typing the parameter `UUID` converts a malformed id into a **found** card,
    which is the opposite of the AC. A canonical-shape `Path(pattern=…)` constraint is the precise
    instrument. See Q2.

15. **`image_uris` is `null` for 7.5 % of the corpus, and it is not an error.** Measured:
    | Fact | Count |
    | --- | --- |
    | Total cards | 38,261 |
    | `image_uris` JSON-`null` (stored as the text `'null'`; never SQL `NULL`, never `''`) | **2,857** |
    | Of those, carrying per-face `image_uris` inside `card_faces` instead | **2,778** |
    | Cards carrying **both** top-level and per-face `image_uris` | **0** |
    | Cards with **no image anywhere** | **79** |

    The two image sources are **mutually exclusive in this corpus**. A test seeded only with a
    top-level-image card proves half the contract; the AC says *"including `image_uris` **and any**
    `card_faces`"*. This is also the data c3-5's rule depends on (*"key on the presence of per-face
    `image_uris`, never on a layout string — `cards` has no `layout` column"*), and c3-2 is where it
    first crosses the wire. Size keys, for the record:
    `art_crop, border_crop, large, normal, png, small`.

16. **`card_faces` is not always two.** Measured face-count histogram: **2 → 3,222 cards · 3 → 2 ·
    5 → 1** (3,225 total). The schema types it `list[dict[str, Any]] | None`, which generates
    `Record<string, unknown>[] | null` — **no per-face typing on the wire at all**. State that as a
    known limit; do **not** invent a `CardFace` model here. Typing untyped Scryfall JSON would be a
    second shape over data this project does not control, and c4-6's DFC flip control is the story
    that actually needs a face contract.

17. **`Card`'s NULL-coercion validators change what the wire promises, and they answer a live
    forward-dated comment.** `oracle_text`/`mana_cost` coerce `None → ""`, `colors`/`games` → `[]`,
    `legalities` → `{}` (`card.py:68-88`). So those fields generate **non-nullable** TypeScript.
    `ui/src/components/ManaCost/ManaCost.tsx:41-43` and `ui/src/components/ManaCost/parse.ts:155-157`
    both predict *"the wire type c3-2 generates may still be nullable"* — **measured false, and
    already false**: `CardSummary.mana_cost` crossed as a non-null `string` at c3-1
    (`types.d.ts:103-104`). Keep the four-spelling totality (it is defence against an untyped
    runtime value), repair the **stated reason** (AC 19).

### The wire, the docstrings and the gates

18. **`Card`'s docstring is Python-internal prose with no truncating header, so all of it crosses
    the wire.** Today: *"Pydantic schema for Magic: The Gathering card data. / Provides type-safe
    data transfer between application layers. Supports conversion from SQLAlchemy CardModel
    instances."* `_CompanionFastAPI.openapi()` (`main.py:350-361`) truncates at the first Google
    header — and there is none — so `openapi-typescript` will emit "SQLAlchemy CardModel" as JSDoc
    into `types.d.ts` and `/docs`. This is exactly what c3-1 rewrote four times, and
    `test_openapi_contract.py` **will not catch it**: the deferred entry homed here says the gate
    bans the *marker*, not the prose.

19. **Two convention decisions are homed on this story by name** (`deferred-work.md`):
    - *"The `openapi.json` byte-comparison gate cannot see meaning … Whether a gate is worth
      building (ban the role-markup family; the prose half is not statically decidable) is open.
      **Home: c3-2**, the next story to add a schema to `components.schemas` — it will face the same
      question with `Card`."*
    - *"The `Attributes:` sections in the four wire-facing schemas hold prose, not attributes, and
      nothing says why … **Home: c3-2**, which will do the same thing to `Card` and should decide
      the convention for all of them."*

    Both are Q5. Note the second one's sharp edge: **the shared core's docstring *structure* is
    load-bearing for a companion-only rule that `src/data` never mentions.** An editor who deletes
    a header that plainly documents no attributes silently republishes MCP prose into `/docs` with
    no gate going red.

20. **Two generated files, two CI jobs, and the plugin mirror.** `npm run gen:api` from `ui/` runs
    `uv run python -m scripts.dump_openapi` then `npm run gen:types`; commit both in the same
    commit (`ui/README.md:146-149` — a fresh `openapi.json` beside a stale `types.d.ts` is red in
    CI and poisons a bisect). Committed baseline **measured now**: `paths = ['/health',
    '/api/decks', '/api/deck/{deck_id}']`, `components.schemas = ['CardSummary', 'DeckCardSummary',
    'DeckDetail', 'DeckSummary', 'ErrorResponse', 'HealthResponse']` — 3 paths and 6 schemas, going
    to **4 and 7**. And `plugin/**` is **not** "not touched": CI's *"Plugin tree in sync with
    `src/`"* step (`.github/workflows/ci.yml:76-84`) re-runs `scripts.build_plugin` and fails on
    drift — c3-1's finding 1, learned the hard way. This story edits `contracts.py`, `errors.py`,
    `main.py`, `routes/`, `schemas/card.py`, all mirrored. **Rebuild and commit the mirror.**

---

## Acceptance Criteria

### The route

1. **`GET /api/cards/{card_id}` returns the full `Card` schema unwrapped** — id, name, oracle_id,
   mana_cost, cmc, type_line, oracle_text, power/toughness, game_changer, rarity, set_code,
   set_name, collector_number, colors, color_identity, color_indicator, keywords, legalities,
   **`card_faces`**, **`image_uris`** and games — with no `{"status": …}` or `{"card": …}` envelope
   (FR-03, AD-16). The path is **plural `/api/cards/{card_id}`**, matching `deps.py:285`,
   `scripts/dump_openapi.py:23`, `EXPERIENCE.md:86` and the epic.

2. **The handler consumes `CardRepository.get_by_id()` and nothing else** (AD-1). No `select(...)`,
   no `text(...)`, no `session.execute`, no second card shape anywhere in `src/companion`, and
   **no new model in `src/companion/contracts.py`**. A test asserts the committed schema's new
   component names are exactly `{"Card"}` beyond c3-1's six, so a companion-local mirror fails
   loudly.

3. **The identifier is the Scryfall printing uuid** — the value in `cards.id` and
   `deck_cards.card_id` (FR-13). A test proves the join: a card id read out of a seeded
   `GET /api/deck/{id}` response hydrates successfully through `GET /api/cards/{card_id}`, so the
   two endpoints are shown to speak the same identifier rather than asserted to.

4. **An unknown-but-well-formed uuid answers `404 {"reason": "card_not_found"}`.** The handler
   raises `CompanionError("card_not_found")`; it does not construct a response, does not pass a
   status, and does not import `JSONResponse`. Asserted on status **and** exact body.

5. **A malformed card id answers `400 {"reason": "invalid_request"}`** (AD-16), produced by the
   existing `validation_error_handler` — **no manual 400, no `HTTPException`, no `try`/`except` in
   the diff**. Probed across a spelling family, not a list: too short, too long, wrong hyphen
   positions, non-hex characters, empty segment, and (per Q2's ruling) the non-canonical UUID
   spellings `uuid.UUID` would otherwise silently normalise — 32-hex-without-dashes, `{braced}`,
   `urn:uuid:` and uppercase.

6. **The route declares its own token and nothing else** via
   `responses=error_responses("card_not_found")`. The committed schema shows `404` on
   `/api/cards/{card_id}` referencing `ErrorResponse`; `build_app()`'s app-level `responses` is
   **unchanged**; and **`422` is absent** from the path (AC 4's `without_auto_validation_schema`
   holding for the first validated route), paired with a non-vacuity check that the path's response
   set is non-empty and contains `200` and `400`.

7. **The session comes from `DbSession`**, and both 503 paths are proved **through the real route**:
   a missing database file answers `503 {"reason": "database_not_initialized"}` and a
   present-but-corrupt file answers `503 {"reason": "database_unavailable"}`. No
   `add_exception_handler` and no `try`/`except DatabaseError` anywhere in the diff.

8. **No write path is opened.** `tests/unit/companion/test_import_boundary.py` passes unchanged with
   **no exclusions added**. Explicitly absent from the `src/companion` diff: every deck/card
   mutation method, `session.add`, `session.commit`, `session.delete`, `init_database`,
   `create_all`, `src.data.importers` (AD-2, NFR-02).

9. **The router is registered above `install_spa(app)`**, and a test proves the route is not
   shadowed by asserting **status and body** — not merely content-type (c3-1 review finding R1: the
   content-type-only version passed with the router deleted, because `/api` is reserved and answers
   JSON `invalid_request` either way). `test_spa.py::TestMountOrdering` and the reserved-prefix
   tests stay green, and **`test_spa.py:305`'s differential router list gains its line** (landmine 8).

### The seventh token, and its copy (retro R1)

10. **`ErrorReason` is extended to seven and every one of landmine 10's seven rows is worked in the
    same commit.** `STATUS_BY_REASON["card_not_found"] = 404`; `test_errors.py`'s closed-set pin is
    updated to seven with its comment re-stated; `contracts.py:61`'s prediction becomes past tense;
    and `ErrorResponse`'s per-token "what it means on the glass" list gains its seventh bullet,
    naming the **placeholder** (not a panel) and its owner.

11. **`ui/src/api/schema.test.ts` pins all seven by name**, and `npm run typecheck` is run and pasted
    — because `npm test` passing proves nothing about that file (its own header, measured).

12. **`states.ts` records `card_not_found`'s destination in a way that distinguishes it from
    "nothing to do".** The two existing `null` entries mean *no UI response at all*;
    `card_not_found` has a named UI destination that is simply not a panel. Per Q3's ruling, the
    distinction is **typed and gated**, not left to a comment, and the entry names **c4-3** as the
    owner of the render. `EveryPanelHasASource` and `PanelSourcesAreDisjoint` still hold, and
    `StateKey` gains **no** seventh member.

13. **The `EXPERIENCE.md` copy row ships with the token, and this record quotes it verbatim**
    (retro R1's literal success criterion — landmine 12 carries the quotation). A test asserts the
    label string the placeholder will render (`"Unknown card"`) against the artefact **read from
    disk**, in the `copy.test.ts` spirit, so the token cannot ship with copy that does not exist —
    and the test states in its own source why it cannot use `copy.test.ts`'s row parser (the row is
    single-field by design and excludes itself, `copy.test.ts:66`).

14. **No component, no fetch, no store, no placeholder renderer.** `ui/src/App.tsx`,
    `ui/src/components/StatePanel/**`, `ui/src/components/Panel/**` and every other component's
    **behaviour** are unchanged. c4-1 owns the hydration cache, **c4-3 owns the unknown-card
    placeholder**, c4-5 the detail panel — pre-empting any of them is scope creep against three
    named owners. Permitted `ui/` changes: the two generated files, `src/api/schema.test.ts`,
    `src/components/StatePanel/states.ts`, the AC 19 comment repairs, `ui/README.md`, and the new
    copy test.

### Prices, images and faces — what the data actually is

15. **No price field is added, and the absence is recorded as a measurement, not an assumption.**
    The story states, with the grep pasted, that no price column, field, importer path or UI
    consumer exists; the epic's price AC is satisfied by absence; and `deferred-work.md` gains an
    entry naming what adding prices would actually cost (a `cards` column + importer change +
    hand-written migration + re-import) with a named home. A `prices: null` field on 100 % of
    responses is **not** an acceptable substitute.

16. **Both image shapes are tested, because the corpus contains both and never both at once.**
    Fixtures cover: a card with top-level `image_uris` and `card_faces: null`; a card with
    `image_uris: null` and per-face `image_uris` inside `card_faces`; and a card with **neither**
    (the 79-card case). All three round-trip on the wire with the nulls surviving as `null` — not
    as `{}`, not omitted. A test seeded only with the first shape does not satisfy this AC.

17. **The generated `Card` type is inspected and its shape recorded** — specifically that
    `mana_cost`, `oracle_text`, `colors`, `games` and `legalities` are **non-nullable** (the
    coercion validators), while `image_uris`, `card_faces`, `keywords`, `color_indicator`,
    `printed_name`, `power`, `toughness` and `game_changer` are nullable. Recorded as measured
    output; it is what c4-1/c4-3/c4-5 will code against.

### The wire contract

18. **`npm run gen:api` is run and both generated files are committed together** — neither
    hand-edited, neither prettier-formatted (both stay in `.prettierignore`). Measured before →
    after: **3 paths → 4**, **6 component schemas → 7** (`Card` added; nothing removed). Both drift
    gates green from the same commit, output pasted:
    `uv run pytest tests/unit/companion/test_openapi_contract.py` and, from `ui/`,
    `npm run gen:types && git status --porcelain` (no output).

19. **No Python-internal or MCP-internal prose crosses the wire, scanned by FAMILY not by member**
    (c3-1's re-keyed scan; standing agreement *ban the family, never enumerate members*). After
    regeneration, `types.d.ts` is scanned for: Sphinx role markup (`:[a-z]+:` before a backtick), any
    Google-style section header, `>>> `, `model_validate`, `SQLAlchemy`, `CardModel`, `pydantic`,
    `src/mcp_server`, `LLM client`, `lookup_card_by_name`. Every hit is fixed **at the Python
    docstring** — rewriting `Card`'s leading summary for a TypeScript reader and pushing the Python
    detail below a truncating header — never by editing the generated file.

20. **`ui/tests/wire-contract.test.ts` picks up `Card` with no edit to its ban mechanism**, and the
    pickup is proven non-vacuously: a planted `type Card = { x: 1 }` in a **staged** scratch
    `ui/src` file makes it red, then is reverted (the guard is keyed on `git ls-files`, so an
    untracked plant passes vacuously — that is its own declared limit, already in the README
    blind-spot map). Probe output and revert both pasted. A `toContain('Card')` anchor may be added
    beside the existing ones (c3-1 review R7 settled that the anchor is not the ban list).

### Boundaries, comments and records

21. **The plugin mirror is rebuilt and committed** (`uv run python -m scripts.build_plugin`), and
    the SPA bundle is **re-measured, not assumed**: `src/companion/app/static/` and
    `plugin/server/src/companion/app/static/` are expected byte-identical (`types.d.ts` is
    type-only; `states.ts`/`schema.test.ts` reach no runtime import). If either changed, that is a
    finding to explain, not a rebuild to wave through.

22. **The forward-dated-comment inventory is repaired** (standing agreement). Each row either
    becomes true, is re-homed, or is recorded with a judgement:

    | # | Location | What it says | Action |
    | --- | --- | --- | --- |
    | 1 | `src/companion/contracts.py:61` | "Story c3-2 adds `card_not_found` the same way; nothing else does" | **Becomes true** — rewrite to past tense, closed at seven |
    | 2 | `src/companion/app/errors.py:130` | "c3-2 and c5-5 follow" | **Update** — c3-2 done, c5-5 remains |
    | 3 | `src/companion/app/deps.py:285` | "c3-2 (`GET /api/cards/{id}`)" | **Verify + update** — the plural spelling is correct; mark it shipped |
    | 4 | `scripts/dump_openapi.py:23` | "story **c3-2** (`/api/cards/{card_id}`) is next" | **Update** — done; 6 → 7 recorded; name the next (c3-3) |
    | 5 | `tests/unit/companion/test_errors.py:123` and `:178`, `:197` | "c3-2's `card_not_found` is the only remaining planned addition"; "c3-1/c3-2/c5-5 reuse it" | **Update** — the set is closed at seven with nothing planned |
    | 6 | `ui/src/api/schema.test.ts:40` | "Adding a seventh token (c3-2's `card_not_found`) is a deliberate act that edits this line" | **Becomes true** — edit the line, restate the rule for an eighth |
    | 7 | `ui/src/components/StatePanel/states.ts:22` | "`satisfies` is what makes c3-2's seventh token fail typecheck" | **Becomes true** — record that it *did* fail, then was answered |
    | 8 | `ui/src/components/ManaCost/ManaCost.tsx:41-43` and `parse.ts:155-157` | "the wire type c3-2 generates may still be nullable" | **Correct** — measured false (and already false at c3-1). Keep the totality, fix the reason |
    | 9 | `ui/src/components/StatePanel/copy.ts:194` and `StatePanel.tsx:82` | "what will keep c3-2's … needing no bespoke renderer" | **Re-home to c4-3** — c3-2 ships no renderer at all |

23. **`deferred-work.md` gains this story's residue with named homes**, at minimum: the price-data
    absence (AC 15); whatever Q5 does *not* take (the meaning gate and/or the `Attributes:`
    convention) re-homed rather than dropped; the untyped `card_faces` element shape → **c4-6**;
    the 79 no-image-anywhere cards as the first concrete `Card placeholder` population → **c4-3**;
    and anything the review turns up. No residue in prose only.

### Testing

24. **Tests live at `tests/unit/companion/test_routes_cards.py`** and drive the real `build_app()`
    through `lifespan_client` against a real temporary SQLite file. **Fixture card ids must be
    canonical UUIDs** — `test_routes_decks.py`'s `_card()` helper mints ids like `"card-anchor"`,
    which AC 5's shape gate would reject, so that helper cannot be reused verbatim. Coverage: happy
    path with every field on the wire; all three image shapes (AC 16); a multi-face card; unknown
    uuid → 404 token; the malformed-id family → 400; both 503 paths; the not-shadowed-by-SPA check
    asserting status and body; the deck→card identifier join (AC 3); and the committed schema's
    path and component names.

25. **Non-vacuity pairing on every guard-shaped assertion** (standing agreement): each proves it
    **fires** and proves it **stays silent** from the same invocation. Concretely — the malformed-id
    family is paired with a well-formed id that reaches the handler (so the pattern cannot pass by
    rejecting everything); the "422 absent" assertion is paired with a check that the path declares
    `200` and `400` (so a wrong path key cannot pass by finding nothing); and the null-image
    assertions are paired with a card that genuinely has images (so `null` everywhere cannot pass by
    coincidence).

26. **At least four mutation probes are run, verified on disk before the verdict and reverted after**
    (standing agreement — *probe your own guard before review does*): (a) the router silently
    unregistered; (b) `card_not_found` swapped for `deck_not_found` at the raise site; (c) the id
    pattern loosened to `.+`; (d) AC 20's planted `type Card`. Paste each result.

27. **Every gate is re-run and its output pasted**: `uv run pytest`, `uv run ruff check .`,
    `uv run ruff format --check .`, `uv run mypy src/`, `uv run mypy src/ --platform win32`, plus the
    six frontend gates from `ui/` (`lint`, `format:check`, **`typecheck`**, `test`, `build`) and both
    drift checks. Suite counts stated as *before → after*, measured at Task 0 and again at the end.
    Baseline to beat: **Python 1836 passed / 1 skipped · frontend 549 passed (28 files)**.

---

## Tasks / Subtasks

- [x] **Task 0 — Baseline, measured not assumed** (standing agreement)
  - [x] `git rev-parse --short HEAD` (expect `b0fd39b`); confirm `feat/companion-c3`; cut
        `feat/companion-c3-2-card-endpoint`
  - [x] Run and record: `uv run pytest` (count + duration), `ruff check`, `ruff format --check`,
        `mypy src/`, `mypy src/ --platform win32`
  - [x] From `ui/`: `npm run lint`, `format:check`, **`typecheck`**, `npm test` (count), `npm run build`
  - [x] Record the pre-change SHA-256 of `src/companion/app/static/assets/*` and the `plugin/` mirror
        (AC 21)
  - [x] Record the committed `paths` and `components.schemas` keys (expect 3 and 6 — landmine 20)

- [x] **Task 1 — The seventh token, all seven rows** (AC 10, 11, 12, 22)
  - [x] `contracts.py`: `ErrorReason` + the `:61` prediction + `ErrorResponse`'s seventh glass bullet
  - [x] `errors.py`: `STATUS_BY_REASON["card_not_found"] = 404`
  - [x] `test_errors.py`: closed-set pin → seven, comments restated
  - [x] `ui/src/api/schema.test.ts`: seven-token union
  - [x] `ui/src/components/StatePanel/states.ts`: the destination entry per Q3
  - [x] Run `npm run typecheck` **before** `npm test` — rows 6 and 7 only fail there

- [x] **Task 2 — The route** (AC 1, 2, 4, 5, 6, 7, 9)
  - [x] Create `src/companion/app/routes/cards.py` (Q1) with a module docstring and
        `router = APIRouter(prefix="/api")`
  - [x] `@router.get("/cards/{card_id}", response_model=Card, responses=error_responses("card_not_found"))`
        → `CardRepository(session).get_by_id(card_id)`; `None` → `raise CompanionError("card_not_found")`
  - [x] Apply Q2's id-shape constraint; confirm the 400 arrives via `validation_error_handler`
  - [x] Google-style docstring; the **leading paragraph is what crosses the wire** (landmine 18)
  - [x] Register in `build_app()` **above** `install_spa(app)`; add the line to `test_spa.py:305`

- [x] **Task 3 — The `Card` docstring and the convention decisions** (AC 19, Q5)
  - [x] Rewrite `Card`'s leading summary for a TypeScript reader; push Python/MCP detail below a
        truncating header
  - [x] Apply Q5's ruling on the `Attributes:` convention and on whether a meaning gate ships
  - [x] Re-home to `deferred-work.md` whatever Q5 declines

- [x] **Task 4 — Regenerate the wire types** (AC 17, 18, 19, 20)
  - [x] From `ui/`: `npm run gen:api`; diff both files; confirm 4 paths and 7 schemas
  - [x] Run the family scan over `types.d.ts`; fix at the docstring and regenerate on any hit
  - [x] Record the generated `Card` shape's nullability (AC 17)
  - [x] Probe the wire-contract guard: **stage** a planted `type Card` in a scratch `ui/src` file,
        `npm test` → red, revert → green; paste both

- [x] **Task 5 — Tests and probes** (AC 3, 8, 13, 16, 24, 25, 26)
  - [x] `tests/unit/companion/test_routes_cards.py` with **canonical-UUID** fixtures; all three image
        shapes; a multi-face card; the malformed-id family; both 503 paths; the deck→card join
  - [x] The `EXPERIENCE.md` copy assertion (AC 13), with its own source stating why the `copy.test.ts`
        row parser cannot be reused
  - [x] Re-run `test_import_boundary.py` and `test_spa.py` explicitly
  - [x] Four mutation probes (AC 26), each verified on disk and reverted

- [x] **Task 6 — Comments, docs, records** (AC 15, 21, 22, 23)
  - [x] Work the nine-row forward-dated-comment table
  - [x] Rebuild + commit the plugin mirror; re-measure the bundle against Task 0
  - [x] `deferred-work.md` entries with named homes; add any new `ui/README.md` blind-spot row
  - [x] Fill the Dev Agent Record; update `sprint-status.yaml`

- [x] **Task 7 — Same-day three-layer review before the PR** (C2 retro action item 6, standing)
  - [x] `bmad-code-review` (Blind Hunter + Edge Case Hunter + Acceptance Auditor) before raising the PR
  - [x] Apply patches, then re-run every gate and paste the output
  - [x] Raise the PR into `feat/companion-c3`

---

## Dev Notes

### Decide-once rulings this story inherits (do not re-derive)

| Ruling | Source | What it means here |
| --- | --- | --- |
| REST is HTTP-native; success bodies are existing Pydantic schemas **unwrapped** | AD-16 | `response_model=Card`; no envelope, no wrapper key |
| Adding a UI state means adding a **token** first, and the token + its copy land together | AD-16, C2 retro **R1** | This is the story that pays it. The copy is a placeholder label, not a panel — landmine 12 |
| The status is derived from the token, never chosen at the call site | `errors.py` module docstring | `raise CompanionError(...)`; never `JSONResponse`, never `status_code=` |
| The engine is lazy and its absence is a served UI state | AD-10, c1-6 | Annotate `DbSession`; do not probe readiness |
| `DatabaseError → 503 database_unavailable` is registered app-wide | c1-6, C1 retro | No `try/except` in a route body |
| The backend consumes existing repositories and defines no second card shape | AD-1 | `CardRepository.get_by_id` → `Card`. Nothing to build |
| `src/companion` is a sibling of `src/mcp_server`, not a consumer | AD-1, AD-3 | Never import `src.mcp_server.*` |
| Read-only is enforced by the CI import-boundary test, not `mode=ro` | AD-2 | The guard stays green with **no exclusions added** |
| One generator, from the backend's own `app.openapi()` | AD-12 | `npm run gen:api`; no second codegen, no hand-written TS shape |
| `install_spa(app)` stays last in `build_app()` | c2-2 | Register the router above it |
| Ban the family, never enumerate members | C2 retro, standing | AC 5's malformed-id probe and AC 19's scan are both family-keyed |
| Probe your own guard before review does | C2 retro, standing | AC 26's four probes are not optional |
| Claims require verification | standing | Paste real gate output; measure the bundle, do not assume it |

### The five things this story must not break

1. **`tests/unit/companion/test_import_boundary.py`** — both guards, AST-only, sees modules no test
   imports. Its docstring forbids routing around it by convention: *"a guard satisfied by
   obfuscation is theatre"* — no `getattr`, no dynamic import.
2. **`test_spa.py`** — `TestMountOrdering`, the reserved-prefix pins, **and** the hand-synchronised
   differential router list at `:305` (landmine 8).
3. **`test_errors.py`** — the closed-set pin and the status-mapping pin are supposed to go red here.
   Update them *deliberately*, in the same commit, with their comments restated. A red you silence
   without restating the comment is how the next story inherits a lie.
4. **`test_openapi_contract.py`'s byte comparison** — including LF line endings and
   `ensure_ascii=False`. Never hand-edit `openapi.json`; always regenerate.
5. **The MCP card tools** — `lookup_card` returns the same `Card`. Rewriting `Card`'s docstring is
   safe; changing a field, a validator or a default is not, and would land on `lookup_card_by_name`,
   `search_cards`, the deck tools and the power-assessment stack at once.

### Source tree — what exists, what this story adds

```
src/companion/
  contracts.py            EDIT — ErrorReason 6 -> 7; the :61 prediction; the glass bullet list
  app/
    main.py               EDIT — include the cards router ABOVE install_spa(app)
    deps.py               EDIT (docstring only) — c3-2 shipped
    errors.py             EDIT — STATUS_BY_REASON + the :130 docstring
    routes/
      decks.py            UNCHANGED — the pattern to copy
      cards.py            NEW — the only new module in src/companion (Q1)
src/data/schemas/
  card.py                 EDIT (docstring only) — Card's leading summary for a TS reader
scripts/dump_openapi.py   EDIT (docstring only)
tests/unit/companion/
  test_routes_cards.py    NEW
  test_errors.py          EDIT — the closed set is seven
  test_spa.py             EDIT — one line in the differential router list
ui/src/api/
  openapi.json            REGENERATED (committed)   3 paths -> 4
  types.d.ts              REGENERATED (committed)   6 schemas -> 7
  schema.test.ts          EDIT — the seven-token pin
ui/src/components/StatePanel/
  states.ts               EDIT — card_not_found's destination (Q3)
ui/src/components/ManaCost/
  ManaCost.tsx, parse.ts  EDIT (comment only) — the nullability prediction, measured false
ui/tests/
  <copy assertion>        NEW or EDIT — the EXPERIENCE.md label gate (AC 13, Q3)
plugin/**                 REBUILT — required by CI's drift gate (landmine 20)
```

**Not touched, deliberately:** `ui/src/App.tsx`, `ui/src/components/StatePanel/StatePanel.tsx` and
`copy.ts` (beyond the AC 22 comment re-homing), every other component's behaviour,
`src/companion/app/security.py`, `src/companion/client.py`, `src/companion/discovery.py`,
`src/data/models/**`, `src/data/repositories/**`, `src/mcp_server/**`.

### Previous story intelligence (c3-1, and its two review passes)

- **Eleven of eleven stories have answered their open questions "as proposed."** The questions below
  are written to be answerable the same way; Q2, Q3 and Q5 are genuine forks.
- **The round-1 5/5 Greptile cause is four-times confirmed:** the same-day three-layer
  `bmad-code-review` before raising the PR. Standing action item. Task 7.
- **c3-1's review theme was that the story's own evidence contained the refutation of two of its
  claims, and the author read past both.** Probe 1's "19 failed, 9 passed" hid three vacuous tests;
  an AC-9 grep showing two line ranges was captioned "the one implementation". **Applied here:**
  read your own probe output before filing it, and count what survived.
- **c3-1's R1 finding is this story's most likely repeat.** `TestNotShadowedBySpa` passed with the
  router *deleted*, because `/api` is reserved and answers JSON either way. AC 9 is written to
  assert status **and** body for exactly that reason.
- **c3-1's R3 finding is the second most likely.** Nothing tied a nested card to its entry because
  every seeded card was identical on the asserted fields. **Every fixture card here must be
  distinguishable from every other**, and AC 16's three image shapes must differ in more than one
  field.
- **c3-1's finding 1: `plugin/**` is not "not touched".** A stale mirror is a guaranteed red build.
- **c3-1's R14: a fix can put internal detail on the wire.** `Note:` and `Warning:` are the two
  Google headers `main.py` deliberately does **not** truncate — so a `Note:` is a wire-visible
  paragraph. Use a code comment for anything a UI author should not read.

### Git intelligence

- `b0fd39b` — PR #29 merged c3-1 into `feat/companion-c3`; `02b2c45` — the C2 ship record;
  `a52d6f8` — integration PR #28 on master. Working tree clean.
- The C2/C3 rhythm holds: **story branch off the umbrella, story PR into the umbrella with a
  Greptile pass per story**, one integration PR to master after the retro with **no** Greptile pass
  (OSS free-tier budget, standing rule). Merge ≠ release — no tag, no CHANGELOG until c8-4.
- Commit style: Conventional Commits, `feat(companion): …`.
- c3-1's shape is the model to copy: one small `feat` commit, then a separate review-patch commit,
  then the records commit.

### Gotchas specific to this story

- **Versions installed on this machine, measured:** FastAPI **0.140.0**, Starlette **0.48.0**,
  Pydantic **2.12.0** (`pyproject.toml` floors: `fastapi>=0.139.2`, `pydantic>=2.0.0`,
  `uvicorn[standard]>=0.51.0`). Two consequences for Q2's constraint: the Pydantic-v1 spelling
  `Path(..., regex=...)` **was removed** — it is `pattern=` — and the modern form is
  `Annotated[str, Path(pattern=...)]` on the parameter, not a default value. Adding no dependency
  is also part of this story: nothing here needs one.
- **`format` is a field name, not a builtin misuse** — the project deliberately shadows it for MTG
  clarity (project-context.md). Ruff `N` is on; keep it.
- **Async everywhere in `src/data`.** The route handler is `async def` (FastAPI); the MCP tools are
  sync `def` by design. Do not copy the sync pattern across.
- **`mypy --strict` and `--platform win32`** are both gates. Every function in `src/` needs full hints.
- **`uvicorn`'s request-line limit bounds the path segment**, so no explicit length cap is needed —
  but Q2's pattern gives an exact length anyway.
- **`%2F` in a path segment is decoded by Starlette before matching**, so `/api/cards/a%2Fb` is a
  routing-level `404 invalid_request`, not a handler answer (c3-1 review R12 measured this on the
  deck route). Trailing slashes `307`-redirect. Pin the spellings you claim rather than asserting
  them in a docstring.
- **`Card.game_changer` is three-state (`None` = not backfilled) and must never coerce to `False`**
  (AD-4). It crosses the wire as `boolean | null`. Do not "tidy" it.
- **`image_uris` is stored as the text `'null'`, never SQL `NULL` and never `''`** — SQLAlchemy's
  JSON type decodes it to `None`. A fixture that writes SQL `NULL` is testing a state the real
  importer never produces.

### Testing standards

- `pytest` config is in `pyproject.toml`; `asyncio_mode = "auto"` — write `async def test_…` with
  **no** `@pytest.mark.asyncio`.
- Layout mirrors `src/`: `tests/unit/companion/` for anything driven in-process over
  `httpx.ASGITransport`. This story adds **no** `integration`-marked test — AD-10 rules that exactly
  one such test exists in the whole feature and it belongs to **c5-8**.
- Reuse `lifespan_client` and `keep_spa_mount_last` from `tests/unit/companion/conftest.py`. Do not
  write a second seam.
- `tests.*` is exempt from `mypy --strict` but not from ruff or the naming rules.
- Paste real gate output. **`npm run typecheck` is a separate claim from `npm test`** and this story
  has two assertions that live only in the former.

### Architecture rules this story implements

- **FR-03** — `GET /api/cards/{card_id}` returns canonical card data hydrated from the local SQLite
  database.
- **FR-13** — the canonical id everywhere is the Scryfall printing UUID (`cards.id`, the value in
  `deck_cards.card_id`); the unknown-card placeholder is a UI state and therefore needs a token.
- **AD-1** — sibling shells over one core; existing repositories and schemas; no second card shape.
- **AD-2 / NFR-02** — read-only, enforced by the CI import boundary.
- **AD-10** — lazy engine, absence is a served state; in-process testing over `ASGITransport`.
- **AD-12 / NFR-03** — one generator from the backend's own `app.openapi()`; committed, drift-checked.
- **AD-16** — HTTP-native REST, unwrapped bodies, closed reason tokens (**now seven**), one typed
  error body, and the rule that a token arrives with its UI state.

### References

- [epics-companion-app.md § Story 3.2](../planning-artifacts/epics-companion-app.md) — the ACs this
  story expands (lines 1582-1606); the C3 epic framing (1541-1546); **AD-16's REST semantics
  including `card_not_found` by name** (255-267); AD-11's image rules (279-289)
- [prd.md:111,127](../planning-artifacts/prds/prd-Artificial-Planeswalker-2026-07-22/prd.md) — FR-03
  and FR-13 verbatim
- [EXPERIENCE.md:69](../planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md) —
  the "Unknown card in a view" copy row (quoted in landmine 12); `:86` the card detail panel's
  hydration contract and "prices render only when present in local data"; `:126` the push variant
- [epic-c2-retro-2026-07-30.md](epic-c2-retro-2026-07-30.md) — **R1** (lines 202-204) and action
  item 1 (line 350); the C3 preview (167-196); the standing agreements
- [c3-1 story record](c3-1-deck-list-and-deck-detail-endpoints.md) — the seam, the two review passes,
  the six probes, and findings 1-5
- [c1-4 story record](c1-4-typed-rest-error-contract-with-closed-reason-tokens.md) — the token set,
  `error_responses`, and the `internal_error` precedent this story must not repeat
- [c2-9 story record](c2-9-the-shared-state-panel-and-every-system-state-message.md) — `states.ts`,
  the copy module, the verbatim gate, and **probe 4** (a seventh token failing typecheck in four
  places while `npm test` stayed green)
- [deferred-work.md](deferred-work.md) — the two entries homed on **c3-2** by name (the meaning gate;
  the `Attributes:` convention) and `test_spa.py`'s router-list tax
- [project-context.md](../project-context.md) — layer boundaries, async rules, docstring style,
  `CARDS_DATABASE_URL`, ruff/mypy gates

---

## Open questions for Brad — answer before `dev-story`

**Q1 — A new `routes/cards.py`, or add to `routes/decks.py`?** Proposed: **a new module**, because
c3-5's `GET /api/card-image/{scryfall_id}` is this route's natural sibling and will want the same
file, while `decks.py`'s module docstring is written entirely about deck reads. The cost is one more
line in `main.py` and one more in `test_spa.py:305`'s differential list. *Recommendation: as
proposed.*

**Q2 — How is a malformed card id rejected?** Measured: all 38,261 ids are canonical lowercase
hyphenated UUIDs, so the shape is decidable. Three options:

| Option | Verdict |
| --- | --- |
| Type the parameter `uuid.UUID` | **Rejected.** `uuid.UUID` accepts 32-hex-without-dashes, `{braced}`, `urn:uuid:` and uppercase, and *normalises* them — turning a malformed id into a **found** card, the opposite of the AC |
| No validation; anything unknown is `card_not_found` | **Rejected.** The AC requires a 400, and unlike a deck id (c3-1's ruling) a card id has a declared shape |
| **`Annotated[str, Path(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")]`** | **Proposed.** Exact, generates a `pattern` into the OpenAPI document the UI can read, and routes through the existing `validation_error_handler` with no new code |

The sub-decision the pattern forces: **an uppercase UUID is `400`, not a lowercase-normalised
lookup.** Since zero rows are non-canonical, normalising would only ever quietly serve a client bug.
*Recommendation: as proposed, strict and lowercase-only.*

**Q3 — What exactly satisfies retro R1, given the copy is a placeholder label and not a panel?**
The row exists in `EXPERIENCE.md:69` and excludes itself from `copy.test.ts` by structure, on
purpose. A `STATE_COPY` entry would be wrong (`StateKey` is the panel vocabulary, and
`EveryPanelHasASource` would then demand a source for a panel nobody renders). Proposed, three
parts:

1. this record quotes the row **verbatim** (landmine 12 — done above);
2. `states.ts` gains a small **typed** declaration that `card_not_found`'s destination is the
   unknown-card **placeholder** owned by c4-3 — distinct from the two `null`s that mean *no UI
   response at all* — so the pairing is machine-readable rather than a comment;
3. a test asserts the label string `"Unknown card"` against `EXPERIENCE.md` **read from disk**, in
   `copy.test.ts`'s spirit, stating in its own source why the row parser cannot be reused.

The cost is one small new structure in `states.ts` that nothing reads until c4-3. The alternative —
a `card_not_found: null` entry with a prose comment — is cheaper and is what the file does today for
two other tokens, but it is exactly the "token ships alone, comment promises the rest" shape R1 was
written to stop. *Recommendation: as proposed.*

**Q4 — Prices.** There is no price data anywhere: no column, no field, no importer path, no UI
consumer, and the PRD's own recon recorded the absence in 2026-07-11. The epic's price AC is
therefore satisfied **by absence**. Proposed: **ship no price field**, record the measurement with
the grep pasted, and ledger what adding prices would actually cost (a `cards` column + importer
change + hand-written migration + full re-import) with a named home. The alternative — a
`prices: null` field on every response — puts a permanently-null branch into the wire contract that
c4-5 must handle for nothing. *Recommendation: as proposed; ship no price field.*

**Q5 — Does c3-2 take both convention decisions homed on it, and does a meaning gate ship?**
`deferred-work.md` homes two here by name. Proposed split:

- **`Attributes:`-as-truncation-marker:** keep the convention (it works, and c3-1 used it four
  times), apply it to `Card`, and **add one explicit comment in `src/data/schemas/`** stating that
  the header position is load-bearing for a companion-only truncation rule. That closes the sharpest
  edge — an editor deleting a header that documents no attributes — without a new gate.
- **The meaning gate:** ship the **statically decidable half only** — a test banning the Sphinx
  role-markup family (`:[a-z]+:` before a backtick) and any Google-section header from
  `types.d.ts`, keyed on the family per the standing agreement. The prose half ("does this sentence
  address a TypeScript reader") is not statically decidable, like UX-DR33's second-person half, and
  is re-homed to review with a `ui/README.md` blind-spot row.

The cost is one new small test file and one comment; the alternative is deferring both again, which
makes c3-3 inherit them one story later with `Card` already shipped. *Recommendation: as proposed.*

---

## Dev Agent Record

### Agent Model Used

Claude Opus 5 (1M context) — `claude-opus-5[1m]`.

### Open questions — Brad's answers

All five **as proposed** (12 of 12 stories running).

| Q | Ruling |
| --- | --- |
| **Q1** | A **new** `src/companion/app/routes/cards.py` — c3-5's card-image route is its natural sibling |
| **Q2** | `Annotated[str, Path(pattern=...)]`, **strict and lowercase-only**. An uppercase uuid is `400`, not a normalised lookup |
| **Q3** | The **typed destination** in `states.ts` (`PLACEHOLDER_FOR_REASON` + `NO_UI_RESPONSE` + three type-level asserts), plus the `EXPERIENCE.md`-read-from-disk label test |
| **Q4** | Ship **no price field**; record the absence as a measurement and ledger what adding prices would cost |
| **Q5** | The proposed split — keep the `Attributes:` convention and state why it is load-bearing; ship only the **statically decidable** half of the meaning gate, re-home the prose half to review with a blind-spot row |

### Baseline (Task 0, measured — not assumed)

Branch `feat/companion-c3-2-card-endpoint` cut from `b0fd39b` on `feat/companion-c3`. Working tree
clean apart from the story artefacts.

| Gate | Baseline |
| --- | --- |
| `uv run pytest` | **1836 passed, 1 skipped** in 82.65s |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 289 files already formatted |
| `uv run mypy src/` | no issues, 85 source files |
| `uv run mypy src/ --platform win32` | no issues, 85 source files |
| `npm run lint` / `format:check` / `typecheck` | clean |
| `npm test` | **549 passed (28 files)** |
| `npm run build` | ok — `index-DE70muY2.js` 195.14 kB |

Committed schema before: `paths = ['/api/deck/{deck_id}', '/api/decks', '/health']` (**3**),
`components.schemas = ['CardSummary', 'DeckCardSummary', 'DeckDetail', 'DeckSummary',
'ErrorResponse', 'HealthResponse']` (**6**). SPA bundle and `plugin/` mirror hashed: **5 files,
byte-identical across both trees** (`index-DE70muY2.js` = `FAEEEA47…`).

**The story's twenty measurements were re-verified, not inherited.** All nine DB counts confirmed
read-only against the live 38,261-row database: `image_uris='null'` **2,857** (SQL `NULL` **0**,
`''` **0**), of those carrying per-face images **2,778**, carrying both **0**, no image anywhere
**79**, non-canonical ids **0**, face histogram **2→3,222 · 3→2 · 5→1**. `PRAGMA table_info(cards)`
lists 23 columns and **no price column**.

**One correction to the story's own text.** Landmine 13 says a repo-wide grep for `price` returns
"**zero** hits". Measured: **one** — `ui/src/components/StatChip/StatChip.css:87`, a forward-looking
comment about a future micro-role. Restricted to code files (`.py/.ts/.tsx/.sql`) it is genuinely
zero. The conclusion is unaffected; the number was wrong, and this is the story's own "read your
own probe output before filing it" lesson applied to its own prose.

### Debug Log References

**Three things the implementation measured that contradicted an assumption — mine or the story's.**

1. **`503` outranks `400`.** I wrote a test asserting a malformed id is a `400` even with no
   database, "because FastAPI resolves path constraints before dependencies". It failed:
   `assert 503 == 400`. FastAPI's `solve_dependencies` solves sub-dependencies *and* collects
   parameter-validation errors in one pass, raising `RequestValidationError` only afterwards, so
   `get_session`'s `CompanionError` wins. The **assertion** was wrong, not the code. Both outcomes
   are now pinned (`test_the_database_state_wins_over_a_malformed_id` and its
   `..._is_a_400_once_the_database_is_ready` pair) and the consequence is ledgered for c3-9/c4-1: a
   UI that treats 503 as "retry quietly" will retry a request whose id can never succeed.

2. **The `$` anchor is only airtight because of the regex engine.** Python's `re` matches `$`
   *before a trailing newline*, so under `re` a request for `<id>%0A` would validate, miss, and
   answer `404` instead of `400`. Pydantic 2.12 defaults to the Rust engine, where it is correctly
   refused — measured both ways. Recorded in `_CARD_ID_PATTERN`'s docstring and pinned by name in
   the malformed-id family, so a future engine change is a named failure rather than a silent
   downgrade.

3. **A third structural pin was supposed to go red and the story did not predict it.** Landmine 10
   lists seven rows and names two Python pins (`test_errors.py`). There is a **third**:
   `test_routes_decks.py::TestCommittedSchema::test_the_component_names_are_exactly_these` asserts
   the component set is exactly c3-1's six. Adding `Card` reddens it. Found by running the full
   companion suite during probe (b) — it had been failing since Task 4 and the per-file runs never
   showed it. Updated deliberately, with its reason restated, exactly like the two the story named.

4. **A `ui/tests` file cannot import `states.ts`, and the failure points at the wrong file.**
   `unknown-card-copy.test.ts` originally imported `PLACEHOLDER_FOR_REASON` directly. That pulled
   `states.ts` into `tsconfig.node.json`'s graph (`tests/**/*.ts`, `module: nodenext`), where its
   own extensionless `../../api/schema` and `./copy` imports are `TS2835` — correct for
   `tsconfig.app.json`'s `moduleResolution: bundler`, illegal for the node project. It then
   **cascaded**: `ErrorReason` failed to resolve and all three of `states.ts`'s type-level asserts
   collapsed to `Type 'false' does not satisfy the constraint 'true'`, naming the asserts rather
   than the import — three errors that read exactly like the classification gate being broken.
   `copy.test.ts` imports `copy.ts` safely only because that module has **no relative imports at
   all**; that is a property of the module, not a permission.

   **Two things nearly let it ship.** `npm test` stayed green throughout (558 passed) — vitest
   resolves it fine, so this is a `tsc`-only failure. And `tsc -b` is **incremental**: an earlier
   `npm run typecheck` reported clean from cache, and only `npx tsc -b --force` surfaced it.
   Resolved by reading `states.ts` as source text in `ui/tests` and keeping the runtime value pin
   in `states.test.ts` (the app project, which imports the real binding) — both halves stated in
   the test's own source. Ledgered with three candidate proper fixes, plus a `ui/README.md`
   blind-spot row.

**One more:** `PLACEHOLDER_FOR_REASON` deliberately holds a destination **slug**, never the copy.
`"Unknown card"` is prose, and `copy-rules.test.ts`'s `COPY_MODULES` already homes that string on
**c4-3**; putting the literal in `states.ts` would have failed the copy-location gate. The label is
asserted in `ui/tests/`, which the file half does not scan.

### Probe outputs

Four mutation probes, each verified on disk before the verdict and reverted after
(`grep -rn PROBE src/ tests/ ui/` afterwards returns only pre-existing `PROBE_TIMEOUT` hits).

| # | Mutation | Verified on disk | Result |
| --- | --- | --- | --- |
| **a** | `app.include_router(cards.router)` commented out | `main.py:387` reads `# PROBE-A …` | **CAUGHT — 39 failed, 466 passed.** Includes both `TestNotShadowedBySpa` body assertions (the c3-1 R1 shape), `test_spa.py`'s differential router list, and the committed-schema pins |
| **b** | `card_not_found` → `deck_not_found` at the raise site | `cards.py:106` reads `raise CompanionError("deck_not_found")` | **CAUGHT — 5 failed.** Including `test_it_is_not_the_deck_token`, written for exactly this: both tokens are 404, so only the **body** distinguishes them |
| **c** | `_CARD_ID_PATTERN` → `r".+"` | `cards.py:29` reads `_CARD_ID_PATTERN = r".+"  # PROBE-C` | **CAUGHT — 15 failed.** All twelve malformed spellings, the uppercase ruling, and — independently — `test_committed_schema_matches_the_live_app`, because the published pattern is part of the wire contract |
| **d** | `type Card = { x: 1 }` planted in a **staged** `ui/src/__probe_card.ts` | `git ls-files src` lists it | **CAUGHT — `AssertionError: expected [ 'src/__probe_card.ts declares Card' ] to deeply equal []`.** The ban grew to cover `Card` with **no edit to its mechanism**. Reverted → 551 passed |
| **e** | `card_not_found` moved out of `PLACEHOLDER_FOR_REASON` and into `NO_UI_RESPONSE` — the exact drift Q3 exists to stop | `states.ts:117` reads `// PROBE-E moved out`; `:131` reads `'card_not_found',` inside `NO_UI_RESPONSE` | **CAUGHT — `is the destination states.ts records for card_not_found` failed.** Added after the source-read rewrite (Debug Log 4), because a regex assertion that has never been seen to fail is not evidence. Reverted → 7 passed |

**The typecheck-only failure, reproduced deliberately (AC 11, AC 22 row 7).** After Task 1 and
before regenerating, with the generated `ErrorReason` still six tokens:

```
$ npm test      -> Test Files 28 passed | Tests 549 passed     (GREEN)
$ npm run typecheck
src/api/schema.test.ts(49,7): error TS2344: ... 'card_not_found' ...
src/components/StatePanel/states.ts(81,3):  error TS2353: 'card_not_found' does not exist in type 'Record<...>'
src/components/StatePanel/states.ts(117,3): error TS2353: 'card_not_found' does not exist in type 'Partial<Record<...>>'
src/components/StatePanel/states.ts(247,3): error TS2344: Type 'false' does not satisfy the constraint 'true'
```

c2-9's probe 4, come true exactly as predicted: **four** compile-time failures under a fully green
`npm test`. The fourth is the new `EveryPanellessReasonIsClassified` assert — the classification
gate refusing an unclassified token, which is Q3's whole point working before it shipped.

### Completion Notes List

**The route is four lines and the story is everything around it**, as contexted. `read_card` calls
`CardRepository.get_by_id`, raises `CompanionError("card_not_found")` on `None`, and returns the
repository's own `Card`. No projection, no `select`, no `try/except`, no `JSONResponse`, no
`add_exception_handler`, no second card shape. Both `503` paths are inherited and proved through
the real route; `test_import_boundary.py` passes **with no exclusions added**.

**The seventh token, all seven rows in one commit** (retro **R1**). `ErrorReason` 6→7,
`STATUS_BY_REASON["card_not_found"] = 404`, the `contracts.py:61` prediction rewritten to past
tense and closed at seven, `ErrorResponse`'s glass-bullet list gaining a seventh bullet that names
the **placeholder** and c4-3, `test_errors.py`'s closed-set pin restated, `schema.test.ts`'s union,
and `states.ts`. Two new `test_errors.py` cases cover what the seventh token created and nothing
else did: **two tokens now share a status**.

**R1's copy pairing, given that the copy is not a panel.** `EXPERIENCE.md:69` is quoted verbatim in
landmine 12 above. `states.ts` gained `PLACEHOLDER_FOR_REASON` (a *slug*, not the copy),
`NO_UI_RESPONSE`, and three type-level asserts making the third meaning of `null` a compile error
if unclassified — plus semantic pins in `states.test.ts`, because `satisfies` proves totality and
never values (the c2-9 review's own lesson). `ui/tests/unknown-card-copy.test.ts` asserts the label
`"Unknown card"` against the artefact **read from disk**, and states in its own source why
`copy.test.ts`'s row parser cannot be reused — then **measures** that claim rather than asserting
it, by running that parser against this row (no match) and against a real panel row (match).

**Q5's split shipped both halves honestly.** The `Attributes:`-as-truncation-marker convention is
kept and its load-bearing-ness is now stated in `src/data/schemas/card.py`'s **module** docstring —
the sharpest edge was an editor deleting a header that documents no attributes and silently
republishing MCP prose to `/docs` with no gate going red. The meaning gate ships as
`PYTHON_INTERNAL_FAMILIES`: three families (Sphinx role markup, any line-anchored Google section
header with `Note:`/`Warning:` as a declared **two-member allowlist** rather than a twelve-member
ban list, doctest prompts), each with a non-vacuity test proving it fires. The prose half is
re-homed to review with a `ui/README.md` blind-spot row.

**Prices: no field, and the absence is a measurement.** `PRAGMA table_info(cards)` → 23 columns,
none a price. `test_no_price_field_is_served` asserts no response key contains "price", paired with
a non-vacuity check that the body genuinely parsed. What adding prices would cost is ledgered.

**Deviations from the story text, all deliberate and all flagged:**

1. **`states.test.ts` edited**, which AC 14's permitted-file list omits. It is the semantic-pin
   sibling of `states.ts` (a file AC 14 *does* permit) and exists precisely because `satisfies`
   proves totality and not values. Adding `card_not_found: null` with no semantic pin would repeat
   the defect that file was created to catch. No behaviour changed.
2. **`test_routes_decks.py`'s component-name pin updated** — see Debug Log 3. Unavoidable: the
   committed schema gained `Card`.
3. **The story's "zero grep hits" for `price` is one hit** — see Baseline.
4. **`test_openapi_contract.py` gained the family gate** rather than the scan living only in the
   record. Q5 asked for a gate; this is where the enumeration it replaces already lived.

**Not shipped, deliberately:** no component, no fetch, no store, no placeholder renderer. `App.tsx`,
`StatePanel.tsx`/`copy.ts` (beyond the AC 22 comment re-homing), `security.py`, `client.py`,
`discovery.py`, `src/data/models/**`, `src/data/repositories/**` and `src/mcp_server/**` are
untouched in behaviour. c4-1 owns the hydration cache, **c4-3** the unknown-card placeholder, c4-5
the detail panel, c4-6 the face contract.

### File List

**New**

- `src/companion/app/routes/cards.py`
- `tests/unit/companion/test_routes_cards.py`
- `ui/tests/unknown-card-copy.test.ts`

**Modified — backend**

- `src/companion/contracts.py` — `ErrorReason` 6→7; the `:61` prediction; the seventh glass bullet
- `src/companion/app/errors.py` — `STATUS_BY_REASON`; the `error_responses` and `CompanionError` docstrings
- `src/companion/app/main.py` — import + `include_router(cards.router)` above `install_spa`; the ordering comment
- `src/companion/app/deps.py` — `DbSession` docstring (c3-2 shipped; the two path spellings)
- `src/data/schemas/card.py` — the module docstring (Q5's load-bearing-header statement) and `Card`'s docstring
- `scripts/dump_openapi.py` — module docstring: 6→7 components, c3-3 next

**Modified — tests**

- `tests/unit/companion/test_errors.py` — closed set → seven, comments restated, two new cases
- `tests/unit/companion/test_openapi_contract.py` — `PYTHON_INTERNAL_FAMILIES` + two tests
- `tests/unit/companion/test_spa.py` — the differential router list
- `tests/unit/companion/test_routes_decks.py` — the component-name pin

**Modified — frontend**

- `ui/src/api/openapi.json`, `ui/src/api/types.d.ts` — **regenerated together**, neither hand-edited
- `ui/src/api/schema.test.ts` — the seven-token pin
- `ui/src/components/StatePanel/states.ts` — the classification and its three asserts
- `ui/src/components/StatePanel/states.test.ts` — semantic pins for the classification
- `ui/src/components/StatePanel/copy.ts`, `StatePanel.tsx` — comment re-homing to c4-3
- `ui/src/components/ManaCost/ManaCost.tsx`, `parse.ts` — the nullability prediction, measured false
- `ui/tests/wire-contract.test.ts` — the `Card` non-vacuity anchor
- `ui/README.md` — the wire-prose blind-spot row

**Modified — records**

- `_bmad-output/implementation-artifacts/deferred-work.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `_bmad-output/implementation-artifacts/c3-2-card-detail-endpoint.md`

**Rebuilt**

- `plugin/**` (the CI drift gate re-runs `scripts.build_plugin` and fails on stale mirror)

### The generated `Card` shape (AC 17, measured from `ui/src/api/types.d.ts`)

What c4-1 / c4-3 / c4-5 will code against. The split is exactly the coercion validators:

| Non-nullable | Nullable (`?: T \| null`) |
| --- | --- |
| `id`, `name`, `oracle_id`, `cmc: number`, `type_line`, `rarity`, `set_code`, `set_name`, `collector_number` | `printed_name`, `power`, `toughness` |
| **`mana_cost: string`**, **`oracle_text: string`** (NULL → `""`) | **`game_changer?: boolean \| null`** — three-state, AD-4 |
| **`colors: string[]`**, **`games: string[]`** (NULL → `[]`), `color_identity: string[]` | `color_indicator`, `keywords` |
| **`legalities: { [key: string]: string }`** (NULL → `{}`) | `image_uris?: { [key: string]: string } \| null` |
| | `card_faces?: { [key: string]: unknown }[] \| null` — **untyped per face**, ledgered to c4-6 |

`games` also carries `@default []`. The five bolded rows are the measured refutation of AC 22
row 8's prediction that `mana_cost` "may still be nullable" — it is not, and was not at c3-1.

### Review record (Task 7 — three layers, same day, before the PR)

Ran `bmad-code-review` with all three layers in parallel as independent subagents against the
2,019-line hand-written diff (the plugin mirror and the two generated files excluded — byte-copies
and generator output). **~40 findings → 20 patches applied, 6 ledgered, 3 rejected.**

**The headline, and both hunters found it independently.** The wire docstrings stated an image
invariant that **368 real printings violate**: *"a single-faced card carries `image_uris` and a
null `card_faces`"*. The story measured "cards carrying both top-level **and per-face**
`image_uris`: 0" — true — and I generalised it from *image sources* to *`card_faces` nullness*,
which is false for every split card. That prose was **published into `types.d.ts` and `/docs`**, so
c3-5 and c4-3 would have read it as the branch rule and rendered nothing for 368 cards that have a
perfectly good image. Re-measured census:

| Shape | Rows | Fixture |
| --- | --- | --- |
| `image_uris` + `card_faces` NULL | 35,036 | `SINGLE_FACE_ID` |
| `image_uris` + faces present, **no per-face images** | **368** | `SPLIT_FACE_ID` — **had no fixture** |
| `image_uris` NULL + per-face images | 2,778 | `MULTI_FACE_ID` |
| `image_uris` NULL + faces present, no per-face images | 79 | `NO_IMAGE_ID` |
| `image_uris` NULL + `card_faces` NULL | **0** | `SCHEMA_ONLY_ID` — *the shape my "79 real cards" test seeded* |

Two more errors fell out of it: the "no image anywhere" test modelled a combination that **matches
zero rows**, and `assert all(face["image_uris"]["normal"] …)` would `KeyError` on the **447** real
cards whose faces carry no images — the exact mistake the rule it was teaching exists to prevent.
Both docstrings rewritten to make **per-face `image_uris` presence** the stated discriminator, two
new fixtures, and a sweep test asserting the rule across every shape rather than per-fixture.

**Patches applied (20).** Grouped:

- *The image contract* — both wire docstrings, two new fixtures, the crash-prone face assertion,
  a discriminator sweep test, and two new shape tests.
- *Guards that could not fail for their stated reason* — the `states.ts` pairing regex matched
  inside the ~60 lines of comment c3-2 added about that very pairing (now matched against
  comment-stripped source); its `NO_UI_RESPONSE` half used `[^\]]*` over raw text, which any
  bracket disarmed (now a parsed member list); the artefact row parser silently kept the last of a
  duplicate label where its sibling `copy.test.ts` **throws** (now collects all rows and refuses to
  guess — `EXPERIENCE.md` already repeats eight labels legitimately, so throwing outright would be
  wrong here); `WIRE_VISIBLE_SECTIONS` had only subset checks, so adding `Returns:` to silence a
  build passed every test (now pinned to exactly two, plus a disjointness check against the
  truncator's own set); the family scan never proved its corpus was non-empty; one non-vacuity
  assertion was itself subset-vacuous.
- *Claims that were not true* — the docstrings said `COPY_MODULES` "already homes" `"Unknown card"`
  on c4-3; it does not, c4-3 appears there only in a **prose comment**, which is the
  `internal_error` failure mode R1 exists to stop, restated precisely in both files. The family
  gate's docstring claimed it would catch `Returns:`/`Raises:`; the truncator already strips those,
  so the real added coverage is Sphinx roles and headers the truncator does not know — stated
  honestly. `CardSummary` was called a `response_model`; it is not, it reaches the schema nested.
  The route's `Args:` said a malformed id is answered "before this function runs", contradicting
  this story's own measured 503-precedence finding 15 lines away.
- *Coverage* — the malformed-id family ran 14 ids over **13 distinct inputs** (two entries were
  byte-identical); the `%0A` regex-engine canary asserted only a 400, which a transport that
  stopped percent-decoding would also produce, so it now proves decoding is happening first; the
  section-header family missed `Args :`, `Keyword  Args:` and `Non-standard:`; a
  `PLACEHOLDER_FOR_REASON` entry could be an explicit `undefined` and satisfy all three asserts
  while meaning nothing (fourth assert added); `parse.test.ts:116` was a **third** copy of the
  falsified nullability prediction that AC 22 row 8's inventory did not name; `schema.ts:48` said
  `schema.test.ts` "pins all six".

**Two more probes, run after the patches** (a rewritten guard that has never been seen to fail is
not evidence): **(e)** the token reclassified into `NO_UI_RESPONSE` → the pairing test fired;
**(f)** the real entry deleted but left spelled in a comment → fired on the comment-stripped
match, which is the evasion the rewrite was for. Both verified on disk and reverted; seven probes
total, all seven caught.

**Ledgered rather than fixed (6)**, each with a named home: a data-sourced malformed card id
renders nothing at all rather than the placeholder (**c4-1**/c4-3, latent — 0 of 2,027 `deck_cards`
rows are non-canonical today); `Card` is now a banned type name with no alias in `schema.ts`
(**c4-1**); no cache headers on an immutable resource (**c3-7**/c4-1); `_descriptions` does not
mirror the truncator's `_DATA_KEYS` skip (**c5-1**, latent); the undocumented
`database_not_initialized` in `responses` — already ledgered at c3-1, now **re-confirmed on a
third route** and inherited by every future data route by construction (**c3-9**); and the three
entries the auditor caught with "unowned" homes now name **c4-5**, **c4-1** and **c3-3**.

**Rejected (3).** `card_faces` crossing as `unknown` — real, already ledgered to c4-6, and typing
untyped Scryfall JSON here would be the second shape AD-1 bans. The 503-outranks-400 precedence —
a finding about the spec, not the code; both orders are pinned and ledgered. The auditor's note
that `deferred-work.md` was uncommitted — true of the *feature* commit by design (c3-1's shape:
feat → review patches → records); it lands in the records commit.

**Every gate re-run after the patches, output pasted (AC 27).**

| Gate | Before → After |
| --- | --- |
| `uv run pytest` | 1836 passed / 1 skipped → **1892 passed / 1 skipped** (103s) |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 292 files already formatted |
| `uv run mypy src/` | no issues, 85 → **86** source files |
| `uv run mypy src/ --platform win32` | no issues, 86 source files |
| `npm run lint` (eslint + stylelint) | clean |
| `npm run format:check` | All matched files use Prettier code style |
| **`npx tsc -b --force`** | **exit 0** — forced, because `tsc -b` caches and hid a real failure once already |
| `npm test` | 549 passed / 28 files → **558 passed / 29 files** |
| `npm run build` | ok, `index-DE70muY2.js` 195.14 kB — unchanged |
| `test_openapi_contract.py` (drift, Python half) | 14 passed |
| `npm run gen:types` (drift, Node half) | byte-identical, no output |

AC 19's family scan re-run over the regenerated `types.d.ts`: **0 hits** for all ten markers, and 0
whole-line section headers. SPA bundle and plugin mirror re-measured **byte-identical** across all
five files, and `diff -r src/companion plugin/server/src/companion` (and `src/data`) is empty.
Schema still 4 paths / 7 component schemas.

**One correction to this very table, and it is the story's own lesson landing on me twice.** The
first version of it said "1897 passed" — a number I wrote from arithmetic before the run finished.
The run then went red on the `list_decks` tie-order flake, and the clean re-run measured **1892**.
Both numbers were wrong to state when I stated them. The flake firing a **second time** in one
afternoon is itself recorded in `deferred-work.md` and is why I raised it to Medium-High and
recommended it as the next standalone chore: at ~1,890 tests it is no longer rare, and it now
costs every story a diagnosis it has nothing to do with.

### Change Log

| Date | Change |
| --- | --- |
| 2026-07-31 | Story contexted off `b0fd39b`; 20 landmines, 27 ACs, 5 open questions |
| 2026-07-31 | Implemented (`79010dd`): the seventh token with its UI destination in one commit, the route, Q5's conventions, regenerated wire types, 5 probes |
| 2026-07-31 | Three-layer review: 20 patches, 6 ledgered, 3 rejected. Headline — a wire-published image invariant that 368 real cards violate, from a true count read as a false rule. Suites 1888 → 1897 Python, 558 frontend |
| 2026-07-31 | All five open questions answered **as proposed**; branch cut; baseline measured (1836 Python / 549 frontend) and all nine DB counts re-verified |
| 2026-07-31 | Implemented: the seventh reason token with its UI destination in one commit, `GET /api/cards/{card_id}`, Q5's two convention rulings, regenerated wire types (3→4 paths, 6→7 schemas), 4 mutation probes all caught |
