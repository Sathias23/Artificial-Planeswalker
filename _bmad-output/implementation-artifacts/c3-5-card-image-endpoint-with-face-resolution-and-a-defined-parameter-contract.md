---
epic: c3
story: c3-5
work_branch: feat/companion-c3
story_branch: feat/companion-c3-5-card-image
depends_on: c3-4 (PR #32, merged into the umbrella at 3bfe95f) — the routes package, the wire pipeline, the eight-token error contract, the single whole-artifact schema pin and the lifespan's holder convention all exist
baseline_commit: 3bfe95f
---

# Story C3.5: Card image endpoint with face resolution and a defined parameter contract

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As the browser UI rendering a grid of card faces,
I want one endpoint that serves any card's face at any size,
so that every image in the app comes from the app's own origin and never from a hotlink.

**What this story really is.** c3-1 was a projection that had to move down. c3-2 was a closed set
that had to be extended. c3-3 was a specification asking for six checks over a validator that
produced four. c3-4 was the story where the backend stopped being a pure read model. **This one is
the story where the backend stops being self-contained.** Every byte it has served so far came out
of a SQLite file on the same disk. This route reaches a machine on the internet, and everything
awkward about it follows from that one fact: a response that is not JSON, an answer for "the card
is fine but the picture isn't", and a dependency that can be slow, absent or hostile.

Three firsts land together:

1. **The first non-JSON response in the document.** All six committed paths answer
   `application/json` and every one has a `response_model`. A binary 200 means no `response_model`,
   an explicit `response_class`, a hand-declared `content` block, and a first look at what
   `openapi-typescript` makes of an operation whose success body is bytes. **Nothing in this repo
   has ever exercised that path** — measure it, do not predict it.
2. **The first outbound network call from the backend.** `src/companion/client.py` talks to
   *localhost*; `src/data/importers/scryfall_api.py` talks to Scryfall and is **banned** from
   `src/companion` by `test_import_boundary.py`'s `_BANNED_MODULES`. So this story writes a second
   Scryfall client, deliberately, and the boundary test is what forces that to be a decision.
3. **The first answer that is neither "here it is" nor "you asked wrong".** A card that exists,
   whose id is well-formed, whose size is valid — and there is no picture, either because the data
   carries none (79 cards, measured) or because the CDN did not answer. AD-11 forbids papering over
   either with a substitute image, and EXPERIENCE.md already says what the glass does with both.

The consequence to internalise before writing code: **this story's risk is not the fetch, it is the
resolution.** The fetch is thirty lines of `httpx`. The resolution is a four-shape rule over a JSON
column with no schema, where getting it wrong means a split card silently serves the wrong half or
a transform card's back face 404s — and the four shapes are already measured below, so there is no
excuse for discovering them in review.

**Everything numeric in this story was measured on this machine at `3bfe95f` against the shipped
38,261-card database, read-only. Do not rediscover it.**

### The seam that already exists (do not rebuild any of it)

1. **The route has a home that already claims it by name.** `src/companion/app/routes/cards.py`'s
   module docstring says this module exists as its own file *"because c3-5's
   `GET /api/card-image/{scryfall_id}` is this route's natural sibling — same identifier, same
   corpus, same cache story"*. The spine's Structural Seed agrees on the split: `routes/` is
   "decks, cards, session, health, agent_events" and the **mechanism** lives at
   `app/images.py # proxy: pacer, disk cache, negative cache (AD-11)` (spine `:450-452`). Q1 rules;
   note that the docstring's other sentence — *"There is deliberately nothing here but a lookup"* —
   becomes false the moment the route lands, and a false shipped docstring is a review finding
   whichever way Q1 goes.

2. **The path parameter is already written, tested and published.** `cards.py:29`'s
   `_CARD_ID_PATTERN` is the canonical lowercase hyphenated uuid, with a measured note about
   Pydantic's regex engine and `$` matching before a trailing newline; `CardId` (`cards.py:58`) is
   the `Annotated[str, Path(pattern=...)]` alias. **Import the constant, do not retype the regex** —
   two copies of a uuid pattern is exactly the drift this epic keeps finding. A malformed id routes
   through the shipped `validation_error_handler` as `400 invalid_request` with no code in the route.

3. **`CardRepository(session).get_by_id(card_id)` already returns everything this route needs** —
   `Card | None`, with `image_uris` and `card_faces` on it (`src/data/repositories/card.py:126-151`).
   AD-1 is satisfied by writing no query: no second card shape, no narrow projection, no `select`.
   The cost is a full row read per image request; ledger it rather than optimising it.

4. **`DbSession` brings both 503s with it** (`deps.py:282`). This route reads the database, so it is
   a `DbSession` consumer and joins the list in that docstring — unlike c3-4, which deliberately did
   not. `database_not_initialized` and `database_unavailable` need no code here.

5. **The status is derived from the token, never chosen at the call site** (`errors.py:5-9`). A route
   raises `CompanionError(<token>)` and is done; it cannot pick a status and **cannot attach
   headers** (`companion_error_handler` calls `error_response(exc.reason)` with no `headers=`).
   Consequence for Q2: *distinguishable signalling means distinguishable tokens.* There is no
   supported way to answer two different statuses under one token.

6. **`ErrorReason` is closed at eight** (`contracts.py:65-74`), and `contracts.py:77-102` enumerates
   the **eight edit sites** a ninth costs. That list is reproduced in landmine 12 below with its
   current values; it is accurate as of `3bfe95f` and it is the price tag on Q2.

7. **`error_responses(...)` is per route, and `build_app()` declares the shared four per include.**
   `cards.router` is included with `("invalid_request", "payload_too_large", "database_unavailable",
   "internal_error")`. c3-4's review ruled the declaration is about *what the operation can answer*
   and pruned the DB-free router's phantom rows — so a route added to `cards.router` inherits that
   include's four, of which **`payload_too_large` is a known wart on a body-less GET**
   (`deferred-work.md`, homed on *"the next story that touches `error_responses`'s declaration
   helper, else c3-9"*). Q6 decides whether this story touches it.

8. **The wire pipeline needs no work for an ordinary route and this is not an ordinary route.**
   `scripts/dump_openapi.py:20-27` says *"Adding an endpoint or a model needs no work here. Declare
   the route with a `response_model` and `error_responses(...)`"* — and **names c3-5 as next**. This
   story has no `response_model` on its 200, so that sentence is about to acquire an exception. Fix
   the docstring, restate the counts, name c3-6.

9. **One pin owns the whole artifact now.** c3-4 took the housekeeping item: paths and component
   names are pinned once, in `tests/unit/companion/test_committed_schema.py` (`:64-76` and
   `:91-107`), and `test_routes_decks.py` / `test_routes_cards.py` assert only their own shapes.
   **c3-5 edits one pin, not two** — the entry says so by name. The path set goes 6 → 7; the
   component set moves only if Q4 adds `CardFace`.

10. **`test_import_boundary.py` bans `src.data.importers` outright** (`_BANNED_MODULES`, `:104`). The
    existing Scryfall client (`scryfall_api.py`, `httpx.AsyncClient(timeout=30.0)` plus a
    retry/backoff loop) is **prior art to read, not code to import**. The guard must pass **unchanged
    with no exclusions added**; if it fires, the answer is different code, not a wider allow-list.

11. **The httpx idiom is already in the tree, in the leaf.** `src/companion/client.py:146-164`:
    a split `httpx.Timeout(connect=, read=, write=, pool=)` **plus** an outer
    `asyncio.timeout(...)`, because httpx's `read` deadline caps the gap *between chunks*, not the
    whole exchange — a slow-drip response has no bound without it. Narrow `except (TimeoutError,
    httpx.HTTPError, ValueError)`. `trust_env=False` is deliberate there (proxy env vars, and
    `.netrc` silently attaching `Authorization` to a *localhost* probe); **for an outbound CDN fetch
    that decision points the other way** — a user behind a corporate proxy needs it — so it is an
    explicit call to make and record, not a line to copy.

12. **`httpx>=0.28.1` is already a top-level runtime dependency** (`pyproject.toml:26`). This story
    adds **no** dependency, and adding none is part of it.

13. **The lifespan is where anything with an effect is created** (AD-10). `main.py:110-168` mints the
    instance id and token, builds the inert `deps.Database()` and `state.ActiveDeckSlot()`, then
    publishes discovery; `_shutdown` retracts discovery and disposes the engine, in reverse order,
    swallowing its own exceptions. **`build_app()` may create nothing.** If Q5 puts an
    `httpx.AsyncClient` on the app, that is the shape to follow — created beside the others, closed
    in `_shutdown` beside `holder.dispose()`.

14. **Cache headers have a shipped precedent, in `spa.py`.** `_IMMUTABLE_CACHE_CONTROL =
    "public, max-age=31536000, immutable"` and `_REVALIDATE_CACHE_CONTROL = "no-cache"`
    (`spa.py:71-72`), applied keyed on *what was actually served* (`:344-367`). Starlette sets no
    `Cache-Control` at all, which is why that method exists. Q5 rules what this route stamps.

15. **The test seam is `lifespan_client` + `isolated_data_dir`** (`tests/unit/companion/conftest.py`),
    and `test_routes_cards.py` already contains **the fixture this story needs**: `image_shapes`
    (`:169-293`), which seeds one card of every measured image shape, plus
    `test_the_discriminator_is_per_face_images_not_card_faces_presence` (`:479-517`), written in
    c3-2 and labelled in its own comment as *"The rule c3-5 and c4-3 will code against"*. Reuse the
    fixture; do not seed a sixth set of cards.

### The three firsts, and what each one costs

16. **A binary 200 is four coordinated decisions, and FastAPI defaults are wrong for all four.**

    | Decision | What happens if you leave the default |
    | --- | --- |
    | `response_model=` | Omit it. Leaving it produces a JSON `$ref` for a body that is bytes |
    | `response_class=` | Default `JSONResponse` will happily serialise your bytes as a base64-ish JSON string. Use `Response` (or `StreamingResponse`) |
    | `responses={200: {"content": {...}}}` | Without it the document claims `application/json` for the success case, and the generated TS lies to c4-4 |
    | the handler's return annotation | `-> Response` under `mypy --strict`; FastAPI must not infer a model from it |

    **None of this is exercised anywhere in the repo.** `test_openapi_contract.py` compares the
    committed artifact byte-for-byte and `without_python_docstring_sections` walks the document
    generically (a binary content block carries no `description`, so it is untouched) — but what
    `openapi-typescript` *emits* for a non-JSON 200 is unmeasured. AC 15 makes recording it a
    deliverable, not a footnote.

17. **The failure vocabulary is the design work, and EXPERIENCE.md has already done half of it.**
    Two rows exist in the gated artefact today:

    - `| Card with no image data | Any surface | Named Card placeholder (FR-19). |`
      (`EXPERIENCE.md:127`)
    - `| CDN fetch failure | Any image | Backend serves the placeholder response (FR-04); UI renders
      the named Card placeholder; negative-cached with backoff — no request storms, no per-image
      retry UI. |` (`EXPERIENCE.md:128`)

    So AD-16's pairing rule — *a new token and the UI state it drives are added together* — is
    unusually cheap here: **the UI state is already written, gated and shipped.** Both cases render
    UX-DR22's **named** variant (name + mana pips + type line), which is a *different* variant from
    c3-2's `unknown-card`; `PlaceholderKey` is currently the single member `'unknown-card'`
    (declared immediately above `PLACEHOLDER_FOR_REASON` in `states.ts`) and would gain one. Note the asymmetry that makes Q2 a real question and not a
    formality: the two cases render **identically**, and differ only in whether a retry could ever
    help. That is a distinction the *wire* must carry (AD-11 says "distinguishably") even though the
    pixels do not.

18. **The ninth and tenth tokens cost eight sites each, measured at `3bfe95f`:**

    | Site | Current state |
    | --- | --- |
    | `src/companion/contracts.py:65-74` | the `Literal`, and `:79-80`'s *"Closed at **eight**, with nothing planned"* |
    | `src/companion/app/errors.py:46-55` | `STATUS_BY_REASON`; a test pins the two sets **equal** |
    | `tests/unit/companion/test_errors.py:214-241` | `test_the_token_set_is_exactly_these_eight` + the `_EXPECTED_STATUS` mirror |
    | `ui/src/api/schema.ts:48` | *"**Eight** as of c3-4"* — the one place the count is written |
    | `ui/src/api/schema.test.ts` | the explicit union, every member named |
    | `ui/src/components/StatePanel/states.ts:98-100` | `PANEL_FOR_REASON … satisfies Record<ErrorReason, StateKey \| null>` — **`tsc` fails**, not a test |
    | `states.ts:144` / `:158` | classification into `PLACEHOLDER_FOR_REASON` or `NO_UI_RESPONSE` — plus `PlaceholderKey` itself if the named variant joins |
    | `states.test.ts` | the exact `NO_UI_RESPONSE` array (`['invalid_request','forbidden','payload_too_large']`) and a per-token assertion |

    Plus c3-3's shipped-artifact lesson: **grep `.claude/skills/**` and `plugin/skills/**` for the
    error vocabulary** before calling the ripple list complete. Nothing in either test suite pins
    skill prose against the wire.

19. **What this story does NOT build, stated so the absence reads as a decision.** No pacer
    (**c3-6**), no disk cache (**c3-7**), no negative cache and no backoff (**c3-8**), no cache
    directory in the lifespan (**c3-7**, AD-10), no SPA consumer (**c4-4**). Build **no** hook,
    registry, no-op semaphore or placeholder for any of them — c3-4's ruling on the
    `active_deck_changed` broadcast is the precedent: *"an unused hook is a design decision made by a
    story that cannot see the requirements."* The AC that says "SPA points at this endpoint" (epic
    `:1706-1708`) is satisfied **negatively** here — no `ui/` code fetches an image yet, and the
    assertable half is that nothing in `ui/src` contains a Scryfall host.

    The honest consequence to state rather than discover: **between this story and c3-6, the route
    fetches unpaced.** That window closes inside the same epic, before any client exists — the only
    caller is a test. Say so in the module docstring, with the story number that closes it.

### What the real data says (measured read-only against the shipped 38,261-card database)

**The four shapes, and they are exhaustive:**

| # | Shape | Rows | Serves |
| --- | --- | --- | --- |
| A | top-level `image_uris`, `card_faces` JSON-null | **35,036** | the top-level image |
| B | top-level `image_uris` **+** faces present, **no** per-face images (split · adventure · flip) | **368** | the top-level image — "falls out as single-image automatically" |
| C | `image_uris` null **+ every** face carries its own `image_uris` (transform · MDFC · battle) | **2,778** | the requested face |
| D | `image_uris` null + faces present, no images anywhere (reversible printings) | **79** | nothing — the no-image answer |
| — | `image_uris` null **and** `card_faces` null | **0** | does not exist |

35,036 + 368 + 2,778 + 79 = 38,261. **Zero** cards carry both a top-level and per-face images, and
**zero** cards are partially imaged (a card's faces either all have images or none do). Do not *rely*
on the second invariant — read `face.get("image_uris")` per face — but know that it holds today.

- **Face-count histogram:** 2 → 3,222 · 3 → 2 · 5 → 1. The three >2-face cards (`Smelt // Herd //
  Saw`, `There // They're // Their`, `Who // What // When // Where // Why`) all carry **zero**
  per-face images, so they are shape B and a `[front, back]` destructuring would be wrong on them.
- **Size keys:** exactly one key-set exists across all 40,960 `image_uris` objects (35,404 top-level
  + 5,556 per-face): `art_crop`, `border_crop`, `large`, `normal`, `png`, `small` — **all six,
  always, never a subset.** So a present `image_uris` guarantees the requested size resolves; there
  is no per-card size negotiation and no "this card has no `png`" branch.
- **Hosts:** 245,742 of 245,760 stored URLs are `https://cards.scryfall.io`. The other **18 are
  `https://errors.scryfall.com/soon.jpg`** — 3 cards × 6 keys: `Sparkspitter`
  (`0070bbf6-fdee-44ec-bfb8-3e99d6338e6e`), `Ondu Champion`
  (`7206cdd5-3f86-4415-a236-9b331b4ac42a`), `Gorehorn Minotaurs`
  (`7dc76d47-e9c1-4bcf-9134-70052aafa67f`). A host allow-list of `cards.scryfall.io` alone
  **refuses three real cards**; an allow-list is still right, and its membership is a decision (Q5).
- **The extension is not derivable from the size key.** `png` → `.png` for 40,957 objects and
  **`.jpg` for 3** (those same placeholders); every other size is `.jpg`. c3-7's cache filename
  (`<size>_<face>.<ext>`) must take `ext` from the resolved URL or the response `Content-Type`,
  never from the size name — record that finding for c3-7 even though this story writes no file.
- **Every URL carries a `?<timestamp>` cache-buster** (245,742 / 245,742). Do not strip it. It is
  *not* part of AD-11's cache key, which is deliberate: a data refresh that changes the URL still
  hits the same cache entry, and AD-11 accepts that staleness explicitly.
- **Face index ↔ URL path segment is perfectly consistent** — of 5,556 imaged faces, face 0 is
  always `/front/` and face ≥1 always `/back/`, **0 mismatches**. Which confirms the rule that
  matters: always *read* the stored URL, never *construct* one.
- **The face object has 24 distinct keys** across 6,455 stored face objects. Present on all:
  `object`, `name`, `mana_cost`, `oracle_text` · near-all: `type_line` (6,445) · **`image_uris`
  (5,556)** · then `artist`, `colors`, `power`/`toughness` (935), `flavor_text`, `color_indicator`,
  `loyalty`, `defense`, `printed_name`… and **`layout` on 66 face objects only**. That last number
  is the empirical form of AD-11's rule: there is no usable layout signal, at the row level or the
  face level.
- **`cards` has no `layout` column** — 23 columns, verified against the live DDL. Branching on a
  layout string is not merely discouraged, it is impossible.
- **SQLAlchemy's `JSON` type stores Python `None` as the literal text `'null'`, not SQL `NULL`.**
  `SELECT COUNT(*) FROM cards WHERE image_uris IS NOT NULL` returns **38261** — all of them. Any
  hand-written SQL against these columns is wrong by default; read through the ORM and the schema.

### What the committed artifacts say right now (measured at `3bfe95f`)

- `ui/src/api/openapi.json`: **6 paths** — `/api/active-deck`, `/api/cards/{card_id}`,
  `/api/deck/{deck_id}`, `/api/deck/{deck_id}/format-check`, `/api/decks`, `/health` — and
  **11 components**: `ActiveDeck`, `ActiveDeckRequest`, `Card`, `CardSummary`, `DeckCardSummary`,
  `DeckDetail`, `DeckSummary`, `ErrorResponse`, `FormatCheckReport`, `FormatCheckRow`,
  `HealthResponse`. Every operation is `get` except `put /api/active-deck`. **Every success response
  in the document is `application/json`.**
- `ui/src/api/types.d.ts:333-340` today: `card_faces?: { [key: string]: unknown }[] | null` and
  `image_uris?: { [key: string]: string } | null`. Q4 decides whether that first line survives this
  story.
- `Card` is a **banned type name in `ui/`** (`wire-contract.test.ts` derives its ban from
  `components.schemas`), and `ui/src/api/schema.ts` exports no alias for it. `CardFace` would join
  the ban the moment it ships. That is the mechanism working; the alias is homed on **c4-1**.
- Suites at the baseline, **to be re-measured not inherited**: Python **2140 passed / 558 frontend**
  (from c3-4's closing note).
- Versions on this machine: **FastAPI 0.140.0 · Starlette 0.48.0 · Pydantic 2.12.0 · httpx ≥0.28.1**.

---

## Acceptance Criteria

### The route and its parameter contract

1. **`GET /api/card-image/{scryfall_id}` serves image bytes from the app's own origin**, with a
   `Content-Type` that matches what was actually served (AD-11, FR-04, UX-DR36). No
   `response_model`; an explicit `response_class`; the 200's `content` block hand-declared so the
   generated TypeScript describes bytes, not JSON (landmine 16). The handler's return annotation
   satisfies `mypy --strict` without FastAPI inferring a model from it.

2. **The path parameter reuses c3-2's constant, imported — not a second copy of the uuid regex**
   (landmine 2). A malformed id answers `400 {"reason": "invalid_request"}` through the shipped
   `validation_error_handler` with **no new code**, and the trailing-newline spelling
   (`<canonical-id>%0A`) is pinned by name here as it is in `test_routes_cards.py`, because the
   guarantee comes from Pydantic's regex engine, not from the anchor.

3. **`size` is a closed set generated into the schema as an enum, defaulting to `normal`** (FR-19:
   the grid uses `normal`, the detail panel `large`/`png`; EXPERIENCE.md:86). Membership is the six
   measured keys per Q3. An unrecognised value answers **`400 invalid_request`** through the same
   shipped handler, with no code in the route (epic AC `:1698-1700`).

4. **`face` is a non-negative integer defaulting to `0`**, and a negative or non-integer value is
   `400 invalid_request` from the same handler. Q3 rules the type and any upper bound.

5. **The 503-before-400 precedence is re-measured for this route, not inherited by argument**
   (`cards.py:92-97`): FastAPI solves dependencies before reporting parameter validation, so
   `?size=bogus` against an unusable database answers **503**, not 400. Both orders pinned, and the
   consumer-facing half stated in a wire-visible `Warning:` as c3-2's round-2 review ruled.

### Face resolution — the rule this story exists to write

6. **Resolution is a pure function with no I/O, unit-tested independently of the route**, and it
   keys on **the presence of per-face `image_uris`, never on a layout string** (AD-11, FR-04). It
   takes the card's `image_uris` and `card_faces` and returns an **ordered list of image maps**:
   shape A and B → exactly one entry (the top-level map); shape C → one entry per face, in face
   order; shape D → empty.

7. **`face` indexes the resolved list, not `card_faces`.** This is the single sentence that makes
   the epic's "falls out as single-image automatically" literally true, and it decides every
   awkward case at once: a split card has two faces and **one** resolved image, so `face=1` on
   `Wear // Tear` is out of range; a single-faced card serves at `face=0` (epic AC `:1694-1696`) and
   is out of range at `face=1`; the three 5-face and 3-face shape-B cards behave the same as any
   other split. An out-of-range face answers **404** (epic AC `:1702-1704`) with the token Q2 rules.

8. **Each of the four measured shapes has a named test using a real fixture card** — reusing
   `test_routes_cards.py`'s `image_shapes` fixture (landmine 15), not a sixth hand-seeded set:
   shape A serves the top-level image at `face=0`; shape B serves the **top-level** image at
   `face=0` and 404s at `face=1`; shape C serves face 0 and face 1 from **different** URLs, asserted
   distinguishably (c3-1's R3 finding: identical fixtures prove nothing); shape D returns the
   no-image answer.

9. **The no-image case takes precedence over the out-of-range face case, and the order is stated.**
   A shape-D card asked for `face=7` reports "this card has no image data", not "no such face" — the
   card's whole image story is the more useful and more stable signal, and the client renders the
   same placeholder either way. **No fetch is ever attempted** for a card with no image data
   (AD-11, epic `:1793-1795`), asserted with a transport that records every outbound call.

10. **No live Scryfall metadata call is ever made** (AD-11, epic AC `:1683`). Asserted two ways: a
    source-level guard that the module reaches for no `api.scryfall.com` and imports nothing from
    `src.data.importers`; and a behavioural test that the **only** URL the transport is ever asked
    for is one that came out of the local row.

### The fetch

11. **Outbound fetches are `async` throughout and never block the event loop** (AD-11). No
    `requests`, no `httpx.Client`, no `run_in_executor`, no synchronous file or socket call in the
    request path.

12. **The URL is validated before it is fetched.** Scheme must be `https` and the host must be in an
    allow-list (Q5) — the row is data imported from a third party, and "the database said so" is not
    a reason to fetch an arbitrary URL from inside the user's network. A row whose URL fails the
    check is answered as a fetch failure and **logged with the host**, never fetched. The three
    measured `errors.scryfall.com` cards make this a real case, not a hypothetical one: whatever Q5
    rules, those three ids get a named test.

13. **The request identifies this application.** A descriptive `User-Agent` naming the project and
    its version, and an `Accept` header for images. Scryfall blocks generic clients (see § Latest
    technical information), and "the CDN started 403ing" is a failure nobody would diagnose from a
    stack trace.

14. **A fetch failure and a card with no image data are signalled distinguishably, and neither
    serves a substitute image** (AD-11, epic `:1784-1787`, EXPERIENCE.md:127-128). The vocabulary is
    Q2's. Both answers carry enough for the client to draw UX-DR22's named placeholder — which it
    can, because it already holds the card's name, cost and type line from `GET /api/cards/{id}`.
    **Non-negotiable regardless of Q2: the backend never returns a grey rectangle, a 1×1 pixel, or a
    generic card back.**

15. **Caching headers are stamped deliberately and differ between success and failure** (Q5): a
    successful image is cacheable by the browser; a failure answer is **not** cached, or a transient
    CDN blip becomes a permanently broken tile in one tab. `spa.py`'s constants are the precedent to
    reuse or to consciously diverge from (landmine 14).

16. **No pacer, no disk cache, no negative cache, and no `image_cache` directory** (landmine 19).
    Explicitly absent from the diff: any semaphore, any `asyncio.Semaphore`, any sleep-based
    spacing, any write under `data_dir()`, any mkdir in `build_app()` or the lifespan for image
    storage. The module docstring names c3-6/c3-7/c3-8 as the owners and states that the unpaced
    window closes before any client exists.

### The wire contract

17. **`npm run gen:api` is run and both generated files are committed together** — neither
    hand-edited, neither prettier-formatted. Measured before → after: **6 paths → 7**; components
    **11 → N** with N stated and every added name justified (nothing removed).
    `tests/unit/companion/test_committed_schema.py`'s path set gains its line — **one pin, not two**
    (landmine 9). Both drift gates green from the same commit, output pasted:
    `uv run pytest tests/unit/companion/test_openapi_contract.py` and, from `ui/`,
    `npm run gen:types && git status --porcelain` (no output).

18. **What `openapi-typescript` generates for the first non-JSON 200 is recorded verbatim in the
    story record** — the emitted `content` member and its TypeScript type, whether the operation
    still type-checks as a `paths` member, and whether anything about it would mislead c4-4's fetch
    layer. This is a **measurement deliverable**, not a footnote: it is the first of its kind in the
    document and c4-4 will build against it.

19. **No Python-internal prose crosses the wire, scanned by FAMILY not by member** (standing
    agreement). c3-2's `PYTHON_INTERNAL_FAMILIES` plus the literal markers, **plus** — new for this
    story — a scan for any Scryfall host string reaching `types.d.ts` or `openapi.json`. Every hit
    is fixed **at the Python docstring**, never in the generated file.

20. **`ui/tests/wire-contract.test.ts` picks up any new component name with no edit to its ban
    mechanism**, proven non-vacuously by a **staged** planted declaration in a scratch `ui/src` file
    — red, then reverted, both pasted. If Q4 ships `CardFace`, note in the record that it joins the
    banned-name list and that the alias is homed on c4-1.

21. **If Q2 adds tokens, every ripple site in landmine 18's table is worked in the same commit** —
    including `states.ts`'s `satisfies` clause (a **`tsc`** failure, not a test failure),
    `PlaceholderKey` if the named variant joins, `states.test.ts`'s exact arrays, `schema.ts`'s count
    sentence, and the grep of `.claude/skills/**` + `plugin/skills/**`. Each red is updated
    **deliberately with its comment restated** — a red silenced without restating its comment is how
    the next story inherits a lie. If Q2 declines, the table is stated as *not applicable* with the
    reason.

22. **If Q4 types `CardFace`, no MCP tool output changes shape.** `Card` lives in `src/data/schemas`
    and is returned by shipped MCP tools; a face model that drops unknown keys would silently
    truncate `lookup_card_by_name`'s output. Asserted directly: a **real 24-key face object**
    round-trips through `Card.model_validate` → `model_dump` with **no key lost and no value
    changed**, and the existing MCP tool tests pass unchanged.

### Boundaries, records and the mirror

23. **No write path is opened and no banned module is imported.**
    `tests/unit/companion/test_import_boundary.py` passes **unchanged with no exclusions added** —
    including its ban on `src.data.importers`, which is what forces this story's client to be its
    own code (landmine 10).

24. **The forward-dated-comment inventory is repaired.** Each row either becomes true, is re-homed,
    or is recorded with a judgement. At minimum:

    | # | Location | What it says | Action |
    | --- | --- | --- | --- |
    | 1 | `src/companion/app/routes/cards.py:1-12` | "c3-5's `GET /api/card-image/…` is this route's natural sibling"; "There is deliberately **nothing here but a lookup**" | **Becomes half-false** — restate per Q1, whichever way it goes |
    | 2 | `scripts/dump_openapi.py:20-27` | "Story **c3-5**'s card-image endpoint is next"; "Adding an endpoint needs no work here… declare a `response_model`"; the counts | **Becomes true, with an exception** — this endpoint has no `response_model`. Restate counts, name c3-6 |
    | 3 | `src/companion/app/deps.py:283-310` (`DbSession` callers) | names c3-1/c3-2/c3-3, records that c3-4 takes none | **Update** — c3-5 joins the list |
    | 4 | `src/companion/app/errors.py:148-156` (`error_responses` callers) | enumerates callers, "c5-5 follows" | **Update** |
    | 5 | `src/companion/app/main.py:434-441` (the ordering block) | the route-vs-router tax | **Update per Q1** |
    | 6 | `src/data/schemas/card.py` + `routes/cards.py` | the discriminator prose, duplicated with no drift gate | **Q6** — this story makes it a third copy if unaddressed |
    | 7 | `deferred-work.md`'s two c3-5-homed entries | the prose duplication; `CardFace` typing | **Resolve or re-home by name** per Q4/Q6 |

25. **The plugin mirror is rebuilt and committed** (`uv run python -m scripts.build_plugin`), and the
    SPA bundle is **re-measured, not assumed**: `src/companion/app/static/` and its mirror expected
    byte-identical (this story ships no runtime frontend code). If either changed, that is a finding
    to explain, not a rebuild to wave through. Note `src/data/schemas/card.py` is mirrored too if Q4
    lands.

26. **`deferred-work.md` gains this story's residue with named homes**, at minimum: the unpaced
    window (**c3-6**); the extension-from-URL finding and the cache-key/`?timestamp` note
    (**c3-7**); the negative-cache and backoff behaviour (**c3-8**); the full-row read per image
    request (**c4-1**, beside the hydration cache); `HEAD`/`Range` support if declined; whatever
    Q2/Q4/Q5/Q6 decline. No residue in prose only.

27. **No frontend behaviour ships.** `ui/src/App.tsx` and every component unchanged in behaviour;
    **c4-4 owns the tile that fetches an image.** Permitted `ui/` changes: the two generated files,
    AC 20's anchors, `ui/README.md`, and — only under Q2/Q4 — the named pin/alias sites. Any
    deviation is recorded **at the time it is made** (c3-3's standard).

    The epic's *"the SPA never contacts Scryfall directly"* AC (`:1706-1708`, AD-11, UX-DR36) is
    satisfied **negatively** here and its positive half is homed on **c4-4** by name. The assertable
    half now: **no file under `ui/src` contains a Scryfall host**, tested, and paired with a planted
    occurrence proving the scan can see one (AC 29).

### Testing

28. **Tests live at `tests/unit/companion/test_routes_card_image.py`** and drive the real
    `build_app()` through `lifespan_client`. **No test makes a real network call**; the outbound
    transport is substituted (`httpx.MockTransport` or the equivalent seam Q5 creates) and every
    test asserts on what it was asked to fetch as well as on what came back. Coverage: the four
    shapes (AC 8); face out of range; the no-image precedence (AC 9); every `size` value accepted and
    one rejected; malformed id; the 503-before-400 ordering (AC 5); a fetch timeout; a CDN 404; a
    CDN 500; a non-image content type; a disallowed host (AC 12); the `User-Agent` actually sent
    (AC 13); the cache headers on success and on failure (AC 15); the committed schema's new path.

29. **Non-vacuity pairing on every guard-shaped assertion** (standing agreement): each proves it
    **fires** and proves it **stays silent** from the same invocation. Concretely — the
    "no metadata call" guard is paired with a planted `api.scryfall.com` reference proving the scan
    can see one; the host allow-list test is paired with an allowed host; the "no fetch for a
    no-image card" assertion is paired with a card that *does* fetch, from the same transport
    recorder.

30. **At least five mutation probes are run, verified on disk before the verdict and reverted
    after** (standing agreement — *probe your own guard before review does*): (a) the resolver made
    to always return the top-level image, so shape C's back face silently serves the front;
    (b) `face` made to index `card_faces` instead of the resolved list, so a split card's `face=1`
    stops 404ing; (c) the host allow-list bypassed; (d) the route silently unregistered;
    (e) AC 20's planted type name. Paste each result, and **read the output before filing it** —
    c3-1's review found three vacuous tests hiding inside a "19 failed" probe result.

31. **Every gate is re-run and its output pasted**: `uv run pytest`, `uv run ruff check .`,
    `uv run ruff format --check .`, `uv run mypy src/`, `uv run mypy src/ --platform win32`, plus the
    frontend gates from `ui/` (`lint`, `format:check`, **`npx tsc -b --force`**, `test`, `build`) and
    both drift checks. Suite counts stated as *before → after*, measured at Task 0 and again at the
    end. Baseline to beat, **to be re-measured not inherited**: **Python 2140 passed** ·
    **frontend 558 passed**.

---

## Tasks / Subtasks

- [x] **Task 0 — Baseline, measured not assumed** (standing agreement)
  - [x] `git fetch origin feat/companion-c3`; confirm the umbrella tip is `3bfe95f`; cut
        `feat/companion-c3-5-card-image` from it
  - [x] Run and record: `uv run pytest` (count + duration), `ruff check`, `ruff format --check`,
        `mypy src/`, `mypy src/ --platform win32`
  - [x] From `ui/`: `npm run lint`, `format:check`, **`npx tsc -b --force`**, `npm test` (count),
        `npm run build`
  - [x] Record the pre-change SHA-256 of `src/companion/app/static/assets/*` and the `plugin/` mirror
        (AC 25)
  - [x] Record the committed `paths` (expect 6) and `components.schemas` keys (expect 11)
  - [x] **Verify the shapes against the local database yourself** — the four counts in § What the
        real data says, read-only. If your machine's corpus differs, the story's numbers are the
        claim and yours are the truth; record the difference

- [x] **Task 1 — The resolver** (AC 6, 7, 8, 9; Q3)
  - [x] A pure function, no I/O, no session: `(image_uris, card_faces) -> list[dict[str, str]]`
  - [x] Keys on per-face `image_uris` presence; never a layout string; never a face count
  - [x] Unit tests over the four shapes **before** the route exists (TDD — the rule is the story)

- [x] **Task 2 — The route** (AC 1, 2, 3, 4, 5, 10; Q1, Q3)
  - [x] Place it per Q1; import `CardId`/`_CARD_ID_PATTERN` rather than retyping the regex
  - [x] `size`/`face` as `Annotated[…, Query(...)]` so validation is the framework's, not the
        route's
  - [x] `DbSession` + `CardRepository.get_by_id`; no new query, no projection (AD-1)
  - [x] Google-style docstring; **the leading paragraph is what crosses the wire**; the 503/400
        ordering goes in a wire-visible `Warning:`

- [x] **Task 3 — The fetch** (AC 11, 12, 13, 14, 15, 16; Q5)
  - [x] The client per Q5 (lifespan-owned or per-request), with the split `httpx.Timeout` **and** an
        outer `asyncio.timeout` — landmine 11
  - [x] Scheme + host allow-list before the request; descriptive `User-Agent`; narrow `except`
  - [x] Map upstream outcomes to this story's answers; **never** serve a substitute image
  - [x] Cache headers per Q5, different on success and failure
  - [x] State in the docstring what is *not* here and which story owns each (c3-6/c3-7/c3-8)

- [x] **Task 4 — The failure vocabulary, if Q2 adds tokens** (AC 21)
  - [x] Landmine 18's eight sites in one commit, each comment restated
  - [x] `PlaceholderKey`'s named variant + `PLACEHOLDER_FOR_REASON` entries; `states.test.ts` arrays
  - [x] Grep `.claude/skills/**` and `plugin/skills/**` for the error vocabulary

- [x] **Task 5 — `CardFace`, if Q4 takes it** (AC 22)
  - [x] The model in `src/data/schemas/card.py`, `extra="allow"` per Q4, with the 24-key census in
        its docstring as the reason
  - [x] The lossless round-trip test over a real face object; run the MCP tool tests explicitly
  - [x] Regenerate; component set 11 → 12; the single pin edited

- [x] **Task 6 — Regenerate the wire types** (AC 17, 18, 19, 20)
  - [x] From `ui/`: `npm run gen:api`; diff both files; confirm 7 paths and the component count
  - [x] **Record the first non-JSON 200's generated TypeScript verbatim** (AC 18)
  - [x] Family scan + the Scryfall-host scan over `types.d.ts`; fix at the Python docstring
  - [x] Probe the wire-contract guard: stage a planted type name, `npm test` → red, revert → green

- [x] **Task 7 — Tests and probes** (AC 28, 29, 30)
  - [x] `tests/unit/companion/test_routes_card_image.py` with the full coverage list
  - [x] Re-run `test_import_boundary.py`, `test_spa.py`, `test_committed_schema.py` and
        `test_routes_cards.py` explicitly, and paste the counts
  - [x] Five mutation probes (AC 30), each verified on disk and reverted

- [x] **Task 8 — Comments, docs, records** (AC 24, 25, 26, 27; Q6)
  - [x] Work the seven-row forward-dated-comment table; apply Q6's ruling on the duplicated
        discriminator prose
  - [x] Rebuild + commit the plugin mirror; re-measure the bundle against Task 0
  - [x] `deferred-work.md` entries with named homes; any new `ui/README.md` blind-spot row
  - [x] Fill the Dev Agent Record; update `sprint-status.yaml`; set status to `review`

- [x] **Task 9 — Same-day three-layer review before the PR** *(Brad runs this — `dev-story` stops at
      Task 8 with status `review`)*
  - [x] `bmad-code-review` (Blind Hunter + Edge Case Hunter + Acceptance Auditor) before the PR
  - [x] Apply patches, re-run every gate, paste the output — all 11 patches applied 2026-08-01;
        gates: `uv run pytest -m "not integration"` **2240 passed, 1 skipped**; `ruff check` +
        `ruff format --check` clean; `mypy src/` + `--platform win32` clean; ui `npm test`
        **568 passed (31 files)**, `lint`, `format:check`, `npx tsc -b --force` clean; plugin
        mirror rebuilt (4 companion files re-mirrored)
  - [x] Raise the PR into `feat/companion-c3` — **PR #33**, 2026-08-01

### Review Findings

Three-layer review run 2026-08-01 (Blind Hunter, Edge Case Hunter, Acceptance Auditor), scoped to
production code (tests and the generated `ui/src/api` mirror excluded from the diff; the auditor
verified test-side ACs on the branch). 2 decision-needed, 10 patch, 0 defer, 4 dismissed.

- [x] [Review][Patch] *(was Decision 1; Brad ruled 1a, 2026-08-01)* Redirects bypass the host
      allow-list (AC 12) — `follow_redirects=True` while `is_fetchable` is checked once, on the
      stored URL only; a 3xx from an allowed host is followed to *any* host. **Ruling:**
      `follow_redirects=False` — a redirect answers `image_fetch_failed`, failing closed like the
      allow-list itself; stored CDN URLs are terminal against the measured corpus. All three
      layers found this. [src/companion/app/images.py:416]
- [x] [Review][Defer] *(was Decision 2; Brad ruled 2a, 2026-08-01)* A refused or unparseable
      *stored* URL wears the transient token (`image_fetch_failed`, "may be retried") though the
      refusal is a permanent fact of the row — deferred, homed on **c3-8**: the negative-cache/
      backoff story decides retry semantics for permanently-failing URLs; the wire needs no
      change now.
- [x] [Review][Patch] `_MAX_IMAGE_BYTES` is checked after `client.get()` has already buffered the
      whole body — the docstring's "can make the companion buffer until the machine swaps"
      protection is not delivered; stream with an incremental cap and reject on status/type/
      `Content-Length` before reading [src/companion/app/images.py:487-507]
- [x] [Review][Patch] `image/svg+xml` passes the `image/*` check and is served from the app's own
      origin with a one-year `immutable` cache and no `X-Content-Type-Options: nosniff` — a
      scripted SVG from a misbehaving CDN executes same-origin as the SPA; deny SVG and stamp
      `nosniff` [src/companion/app/images.py:493, src/companion/app/routes/cards.py:317]
- [x] [Review][Patch] The refusal log line calls `urlsplit(url)` again *outside* the try — a URL
      that made `is_fetchable` return False by raising `ValueError` re-raises from the logging
      call: 500 `internal_error` instead of the modelled answer [src/companion/app/images.py:481]
- [x] [Review][Patch] `httpx.InvalidURL` is not an `httpx.HTTPError` (verified: inherits
      `Exception` directly) and escapes the narrow except as a 500
      [src/companion/app/images.py:501]
- [x] [Review][Patch] `_shutdown` has no try/finally — a raising `client.aclose()` strands the
      engine dispose below it, the exact stranding the docstring certifies step 1 against
      [src/companion/app/main.py:550-555]
- [x] [Review][Patch] The documented `Cache-Control` override merges by exact dict key — a caller
      passing `cache-control` yields two conflicting headers on the wire
      [src/companion/app/errors.py:86]
- [x] [Review][Patch] `https://cards.scryfall.io:443/…` is refused while the docstring's
      rationale ("a different port is a different endpoint") is false for the default port —
      fix the docstring (behaviour is fail-closed and fine) [src/companion/app/images.py:379]
- [x] [Review][Patch] "That window closes … before any client exists" overclaims — the unpaced
      route is live to an agent, `curl` or `/docs` today; soften the sentence
      [src/companion/app/images.py:146-148]
- [x] [Review][Patch] AC 27/29 not delivered as a committed gate — no test scans `ui/src` for a
      Scryfall host, and no planted-occurrence pairing exists; note the literal wording is
      already falsified by `ui/src/components/Footer/copy.ts:66`'s attribution href, so the scan
      must scope to CDN/image hosts [tests — auditor verified absent on the branch]
- [x] [Review][Patch] AC 19's new scan — no Scryfall host string reaching `types.d.ts` or
      `openapi.json` — was measured once by hand but not landed as a gate beside
      `PYTHON_INTERNAL_FAMILIES` [tests/unit/companion/test_openapi_contract.py]

- [x] [Review][Patch] *(Greptile round 1, PR #33 — 4/5, one P1, judged accurate and applied
      2026-08-01)* A `200` with an `image/*` type and a ZERO-byte body passed the status, type
      and size checks and was served — then cached `immutable` for a year: a permanently broken
      tile through the success door. Fixed with an empty-body guard raising
      `image_fetch_failed` after the stream completes, paired test added
      [src/companion/app/images.py:477]

Dismissed (4): face-index compaction on a partially-imaged card (ordering pinned as a decision in
`resolve_face_images`'s own docstring); `errors.scryfall.com/soon.jpg` as a substitute image
(covered by Q5's ruling admitting the host); `internal_error` undeclared on the operation (false
positive — declared at include level, `main.py:424`); `CardFace` hard-failing wrong-typed values
(consistent with `Card`'s existing posture; the Epic-1 gate is null-coercion, not shape).

---

## Dev Notes

### Decide-once rulings this story inherits (do not re-derive)

| Ruling | Source | What it means here |
| --- | --- | --- |
| Face handling keys on **per-face `image_uris` presence**, never a layout string | AD-11, FR-04 | The resolver's whole contract; `cards` has no `layout` column and 66 face objects have one |
| CDN urls resolve from **locally stored** `image_uris`; no live metadata call | AD-11 | One repository read, then a fetch of a URL the row already held |
| The backend **never serves a substitute image** | AD-11 | No grey card, no 1×1, no card back — the client draws the named placeholder |
| Fetching is **lazy**; the backend never pre-fetches a deck | AD-11 | One request, one image; nothing warms the cache |
| REST is HTTP-native; success bodies are unwrapped | AD-16 | Here the "body" is bytes — the same rule, no envelope, no `{"image": "base64…"}` |
| The status is derived from the token, never chosen at the call site | `errors.py` | `raise CompanionError(...)`; never `JSONResponse`, never `status_code=` |
| A route declares only the tokens it uniquely produces | c3-1 AC 6, c3-4 review | `error_responses(...)` per route |
| One generator, from the backend's own `app.openapi()` | AD-12 | `npm run gen:api`; no second codegen, no hand-written TS shape |
| `build_app()` has zero side effects; the lifespan owns effects | AD-10 | No client, directory or socket created at import or build time |
| `install_spa(app)` stays last in `build_app()` | c2-2 | Register above it — or reuse a router already above it |
| Consume existing repositories; define no second shape | AD-1 | `CardRepository.get_by_id`; no image-specific projection |
| Ban the family, never enumerate members | C2 retro, standing | AC 19's scans are family-keyed |
| Probe your own guard before review does | C2 retro, standing | AC 30's five probes are not optional |
| Claims require verification | standing | Paste real output; measure the generated TS, do not predict it |
| Copy lives in `EXPERIENCE.md` and is gated | c2-9 | This story ships **no copy** — the two placeholder rows already exist there |

### The seven things this story must not break

1. **`tests/unit/companion/test_import_boundary.py`** — both guards, AST-only. Its ban on
   `src.data.importers` is the one most likely to fire here, and the answer is different code, never
   a wider allow-list. *"A guard satisfied by obfuscation is theatre."*
2. **`tests/unit/companion/test_committed_schema.py`** — now the **single** whole-artifact pin
   (paths + components + auto-422 absence + `securitySchemes` absence). Edit the path set; edit the
   component set only if Q4 lands.
3. **`test_openapi_contract.py`'s byte comparison** — including LF endings and `ensure_ascii=False`,
   plus the description-hygiene family scan over every new docstring. Never hand-edit
   `openapi.json`; always regenerate.
4. **`test_routes_cards.py`** — its `image_shapes` fixture and the discriminator test are this
   story's foundation. Extend, do not fork; if a fixture card is reused across two files, that is a
   shared fixture, not a copy.
5. **`test_spa.py`** — `TestMountOrdering`, the reserved-prefix pins, and the differential router
   list. A route on an existing router owes nothing here; a **new router** owes both this line and
   `build_app()`'s.
6. **`ui/src/components/StatePanel/states.ts`'s `satisfies Record<ErrorReason, StateKey | null>`** —
   if Q2 adds tokens, this fails **`tsc`**, not a test. The frontend refusing to compile until
   somebody decides what a token means on the glass is the mechanism working.
7. **Shipped MCP tool output** — `Card` is `src/data/schemas`, not companion-local. Q4's change is
   visible to `lookup_card_by_name` and every tool that returns a card. AC 22 is why.

### Source tree — what exists, what this story adds

```
src/companion/app/
  images.py               NEW  — the resolver + the fetch (the module the spine's seed names,
                                 :452); no pacer, no cache, no negative cache
  routes/
    cards.py              EDIT — the route, if Q1 joins the sibling router (then main.py and
                                 test_spa.py owe nothing), or:
    card_image.py         NEW  — its own router, if Q1 rules that instead (then main.py +
                                 test_spa.py both owe a line)
  main.py                 EDIT — the lifespan's httpx client + its teardown (only under Q5);
                                 the ordering block (only under Q1's router option)
  errors.py               EDIT — STATUS_BY_REASON + docstrings (only under Q2)
src/companion/contracts.py  EDIT — the ErrorReason Literal (only under Q2)
src/data/schemas/card.py    EDIT — CardFace, and the discriminator prose's single source
                                 (only under Q4 / Q6)
scripts/dump_openapi.py   EDIT (docstring only) — c3-5 shipped; counts; the response_model
                                 exception; c3-6 next
tests/unit/companion/
  test_routes_card_image.py   NEW
  test_images.py              NEW — the resolver as a pure function, if it earns its own file
  test_committed_schema.py    EDIT — the path set (6 -> 7); components only under Q4
  test_errors.py              EDIT — only under Q2
  test_routes_cards.py        VERIFY — the shared fixture still serves both files
ui/src/api/
  openapi.json            REGENERATED (committed)   6 paths -> 7
  types.d.ts              REGENERATED (committed)   11 schemas -> N
  schema.ts, schema.test.ts       EDIT — only under Q2
ui/src/components/StatePanel/
  states.ts, states.test.ts       EDIT — only under Q2
ui/tests/wire-contract.test.ts    EDIT — new toContain anchors (AC 20)
ui/README.md              EDIT — any new blind-spot row
plugin/**                 REBUILT — required by CI's drift gate
```

**Not touched, deliberately:** `ui/src/App.tsx` and every component (**c4-4 owns the tile**),
`src/companion/client.py` (**c6-1 owns the sending half**; it is a *localhost* client and its
`trust_env=False` reasoning does not transfer), `src/companion/discovery.py`,
`src/companion/app/security.py` (this route is browser-facing and takes **no** credential — AD-5),
`src/companion/app/state.py`, `src/data/importers/**` (banned), `src/logic/**`, `src/mcp_server/**`,
`src/viewer/**` (the legacy hotlinking viewer is frozen until c8-1).

### Previous story intelligence (c3-1 … c3-4, and their seven review passes)

- **Fifteen of fifteen stories have answered their open questions "as proposed"** (one partial).
  The questions below are written to be answerable the same way, but **Q2, Q4 and Q5 are genuine
  forks** — they change what ships.
- **The round-1 5/5 Greptile cause is confirmed again at c3-4 — the third straight round-1 5/5**:
  the same-day three-layer `bmad-code-review` before raising the PR. Task 9.
- **c3-4's review theme was *prose outrunning code*** — docstrings that promised behaviour the code
  did not have (`PUT` echoing the body, "byte-identical" ids that break on `/`). This story is
  unusually exposed to it: it writes a *rule* in prose (the discriminator) that four docstrings
  already state and that the resolver must actually implement. **Every sentence about face
  resolution must be re-derived from the resolver's code, not from a neighbouring docstring.**
- **c3-3's headline finding**: a guard caught **0 of 12** planted evasions because every family was
  keyed on the syntax its own firing tests used. The guard-shaped things here are AC 10's
  no-metadata-call scan and AC 12's host allow-list. **Plant an evasion against each before trusting
  it.**
- **c3-3's second finding**: a shipped product artifact consumed a vocabulary that changed —
  `.claude/skills/format-legality/SKILL.md` went stale. Applied here: if Q2 adds tokens, grep the
  skills trees before declaring the ripple list complete.
- **c3-2's finding**: a true count read as a false rule, published to the wire. Applied here:
  "all six sizes always present" is **true of this corpus**, not a Scryfall guarantee — do not write
  it into a wire description as a promise to c4-4.
- **c3-1's R1 finding**: `TestNotShadowedBySpa` passed with the router *deleted*, because `/api` is
  reserved and answers JSON either way. Assert status **and** body — and for this route, assert the
  **bytes**, since a wrong-but-JSON answer is exactly the shape that slips through.
- **c3-1's R3 finding**: nothing tied a nested value to its source because every fixture was
  identical on the asserted fields. **Face 0 and face 1 must resolve to visibly different URLs and
  different bytes**, or AC 8's shape-C test proves nothing.
- **c3-1's finding 1**: `plugin/**` is not "not touched". A stale mirror is a guaranteed red build.
- **c3-2's `Warning:` ruling**: `Note:` and `Warning:` are the two Google headers `main.py` does not
  truncate, so a `Warning:` is a **wire-visible** paragraph. Use one for the 503/400 ordering (c4-4
  must know); use a code comment for anything a UI author should not read.
- **c3-4 booked its deviations at review time and named them.** That is the standard.

### Git intelligence

- `3bfe95f` — PR #32 merged c3-4 into `feat/companion-c3`. `737ce76` — PR #31, c3-3. `2a787ac` —
  PR #30, c3-2. `a52d6f8` — integration PR #28 on master.
- The C2/C3 rhythm holds: **story branch off the umbrella, story PR into the umbrella with a
  Greptile pass per story**, one integration PR to master after the retro with **no** Greptile pass
  (OSS free-tier budget, standing rule). Merge ≠ release — no tag, no CHANGELOG until c8-4.
- Commit style: Conventional Commits, `feat(companion): …`. The shape to copy: one small `feat`
  commit, then a separate review-patch commit, then the records commit.

### Gotchas specific to this story

- **`image_uris IS NOT NULL` is always true in SQL.** SQLAlchemy's `JSON` column stores `None` as
  the text `'null'`. Read through the ORM; if a diagnostic query is unavoidable, test `<> 'null'`.
- **Never construct a CDN url.** The `/front/`–`/back/` pattern is perfectly consistent in the data
  *and* is not yours to depend on; the `?<timestamp>` suffix alone makes construction impossible.
- **Do not strip the query string** from the stored URL — it is Scryfall's cache-buster and the URL
  404s without it.
- **`png` does not imply `.png`.** Three cards' `png` entries end `.jpg`. Any extension logic reads
  the resolved URL or the response `Content-Type`.
- **A card with `card_faces` is not a double-faced card.** 368 split/adventure/flip cards have faces
  and one image. Branching on `card_faces is not None` is the single most likely bug in this story
  and c3-2 already wrote the test that catches it.
- **`face=1` on a split card is *out of range*, not "the other half".** AC 7's rule.
- **The 503-before-400 ordering** (`cards.py:92-97`) applies to this route too: dependencies resolve
  before parameter validation is reported.
- **`secrets`, credentials and tokens have nothing to do with this route.** It is browser-facing and
  takes no `AgentToken` — the browser never holds the agent credential (AD-5).
- **`mypy --strict` and `--platform win32`** are both gates. `card_faces` is `list[dict[str, Any]]`
  today, so every face read needs narrowing (`isinstance(v, dict)`) unless Q4 types it — the legacy
  viewer's `pick_art` (`src/viewer/view_model.py:208-232`) shows the narrowing idiom, and also shows
  the two limitations this story removes (face 0 only, `art_crop` only).
- **`format` is a field name, not a builtin misuse** (project-context.md) — irrelevant here, but
  ruff `N` is on and applies to the new module.
- **No new dependency.** `httpx` is already top-level.
- **The `data` and `deps` bare-identifier trap** (c3-4 review): an AST guard that bans bare names
  like `data` reds on a legitimate local. Ban imports and attributes, not every `Name`.

### Testing standards

- `pytest` config is in `pyproject.toml`; `asyncio_mode = "auto"` — write `async def test_…` with
  **no** `@pytest.mark.asyncio`.
- Layout mirrors `src/`: `tests/unit/companion/` for anything driven in-process over
  `httpx.ASGITransport`. This story adds **no** `integration`-marked test — AD-10 rules that exactly
  one such test exists in the whole feature and it belongs to **c5-8**.
- Reuse `lifespan_client`, `isolated_data_dir` and `test_routes_cards.py`'s `image_shapes`,
  `_point_at`, `_seed`, `_ready_database`. Do not write a second seam.
- **No unit test may touch the network.** The outbound transport is substituted at the seam Q5
  creates; a test that would otherwise reach `cards.scryfall.io` is a bug in the seam, not a slow
  test.
- `tests.*` is exempt from `mypy --strict` but not from ruff or the naming rules.
- Paste real gate output. **`npx tsc -b --force` is a separate claim from `npm test`** — c3-2
  measured `tsc -b` caching a clean result over a real failure, and Q2's ripple is a `tsc` failure.

### Architecture rules this story implements

- **FR-04** — the endpoint, its parameters, CDN fetch on first request, per-face-`image_uris` face
  handling, distinguishable failures, a stable no-image response.
- **FR-19** — the sizes the UI actually asks for: `normal` in the grid, `large`/`png` in the detail
  panel; DFCs get a flip control only where per-face images exist.
- **AD-11** — every rule in § Decide-once above; the parts this story defers are named with owners.
- **AD-1 / AD-2 / NFR-02** — existing repositories, no second shape, read-only w.r.t. the database.
- **AD-10** — `build_app()` has zero side effects; the lifespan owns anything with an effect.
- **AD-12 / NFR-03** — one generator from the backend's own `app.openapi()`, committed and
  drift-checked — including whatever it makes of a binary response.
- **AD-16** — HTTP-native REST, unwrapped bodies, closed reason tokens, one typed error body; a new
  token ships with its UI state.
- **NFR-08** — rate-spacing is c3-6's, but the polite-citizen posture starts here with a descriptive
  `User-Agent` and a validated host.
- **UX-DR22 / UX-DR36** — the named placeholder and placeholder-then-fill; this story supplies the
  **signal**, c4-3/c4-4 supply the pixels.

### Latest technical information (external, checked 2026-08-01)

From Scryfall's published API guidance:

- **Sustained traffic under 10 requests/second, 50–100 ms between calls**; excess earns `429` and a
  ~30-second lockout. This is c3-6's number, recorded here so c3-6 does not re-research it.
- **A descriptive `User-Agent` identifying the application is required, and generic agents
  (`curl`, default `python-requests`) are routinely blocked.** An `Accept` header is expected.
  Corroborating measurement: fetching `https://scryfall.com/docs/api` with a generic tool from this
  machine returned **403 Forbidden**. AC 13 exists because of this.
- **The `*.scryfall.io` file origins are not rate limited** — the image CDN this route talks to is
  explicitly exempt from the 10/second guidance. This does **not** relax AD-11: the pacer is an
  architectural decision about being a good citizen and about not letting a 100-card burst eat the
  250 ms push budget (NFR-05), and AD-11 is the design of record. Record the fact for c3-6 so its
  spacing constant is chosen knowingly rather than copied from the API rules.
- **Scryfall asks consumers to cache what they download, for at least 24 hours** — which is what
  c3-7's unbounded disk cache does, and an argument for AC 15's browser cache headers meanwhile.
- Image URLs carry a cache-busting query and change when a printing's scan is updated; **AD-11
  accepts serving a stale image** rather than keying the cache on the URL.

Sources: [Scryfall API rate limits](https://scryfall.com/docs/api/rate-limits) ·
[Scryfall API docs](https://scryfall.com/docs/api) ·
[Scryfall FAQ — blocked API access](https://scryfall.com/docs/faqs/i-m-having-trouble-accessing-the-scryfall-api-or-i-m-blocked-17)

### References

- [epics-companion-app.md § Story 3.5](../planning-artifacts/epics-companion-app.md) — the ACs this
  story expands (1672-1708); **Story 3.6's pacer** (1710-1739), **3.7's disk cache** (1741-1774),
  **3.8's failure signalling** (1776-1803) — the three stories whose scope this one must not absorb;
  FR-04 (47-53), FR-19 (113-116), NFR-06/08/09 (162-176); UX-DR22 (453-458), UX-DR36 (541-545)
- [ARCHITECTURE-SPINE.md](../planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md) —
  **AD-11 (242-270)**, AD-1, AD-2, AD-10, AD-12, AD-16 (329-352), the Structural Seed's
  `app/images.py` line (452) and the capability map's row C (470)
- [EXPERIENCE.md:84,86,99,105,127,128](../planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md) —
  the flip control's use of `face`, the detail panel's `size=large`, the card placeholder component,
  placeholder-then-fill, and **the two failure rows that pre-decide Q2's UI half**
- [c3-2 story record](c3-2-card-detail-endpoint.md) — the image-shape census, the discriminator
  test written *for this story*, the closed-set extension precedent and the `Warning:` ruling
- [c3-4 story record](c3-4-the-active-deck-readable-by-the-glass-settable-by-the-agent.md) — the
  single-pin consolidation, the per-include `responses=` ruling, and the review's prose-outruns-code
  theme
- [deferred-work.md](deferred-work.md) — the **two entries homed on c3-5 by name** (the duplicated
  discriminator prose; `CardFace` typing) and the 413-on-body-less-GET wart
- [epic-c2-retro-2026-07-30.md](epic-c2-retro-2026-07-30.md) — the standing agreements (ban the
  family; probe your own guard) and action item 6 (same-day three-layer review)
- [project-context.md](../project-context.md) — layer boundaries, async rules, docstring style,
  ruff/mypy gates

---

## Open questions for Brad — answer before `dev-story`

**Q1 — Where does the code live, and does the route join `cards.router`?**

| Option | Verdict |
| --- | --- |
| **Mechanism in a new `src/companion/app/images.py`; the route added to `cards.router` in `routes/cards.py`** | **Proposed.** It is exactly what the spine's Structural Seed draws (`routes/` lists "decks, cards…", `images.py` sits beside it as the proxy), and `cards.py`'s shipped docstring already claims this route as its sibling by name and by reason — *"same identifier, same corpus, same cache story"*. It costs no `build_app()` edit and no `test_spa.py` differential line. The one honest cost: `cards.py`'s *"deliberately nothing here but a lookup"* sentence must be rewritten, because the module now holds a lookup **and** a proxy |
| A new `routes/card_image.py` with its own router | **The real alternative**, on c3-4's logic: a route that opens a socket to the internet is not a database read, and c3-4 paid the two-line tax rather than hide a write in `decks.py`. Rejected only because the seam here is genuinely the *same resource* — the same uuid, the same row, the same repository call — and because a shipped docstring already predicted this placement and would be made false by moving it |
| Everything in one `routes/card_image.py`, no `images.py` | **Rejected.** The resolver must be unit-testable without a request, and the spine names the module |

*Recommendation: as proposed. Rewrite `cards.py`'s docstring in the same commit, and record the
measurement that `test_spa.py` needed no edit.*

---

**Q2 — What vocabulary answers "no image data" and "the fetch failed"?** *(genuine fork)*

AD-11 requires the two to be **distinguishable**, and `errors.py` derives status from token — so
distinguishable means *different tokens*. `ErrorReason` is closed at eight and a ninth costs the
eight sites in landmine 18.

| Option | Verdict |
| --- | --- |
| **Two new tokens now — one for "this card has no image data" (permanent, 404) and one for "the CDN fetch failed" (transient, 502 or 503)** — both classified as `PLACEHOLDER_FOR_REASON` → a new `PlaceholderKey` for UX-DR22's **named** variant | **Proposed.** The UI half of AD-16's pairing rule is *already written and gated*: `EXPERIENCE.md:127-128` names both cases and both render the named placeholder. Both cases are reachable the instant this route ships — 79 no-image cards measured, and a CDN failure is one flight-mode away. And the cost is paid **once**: c3-8 then adds negative caching and backoff as pure *behaviour*, with zero wire change and no second regeneration |
| One new token for both, distinguished by status code | **Rejected.** `STATUS_BY_REASON` maps one token to one status; this option requires either widening `CompanionError` or bypassing it with a raw `Response`, and the second is precisely what `errors.py`'s docstring forbids |
| Reuse `card_not_found` for both, defer the vocabulary to c3-8 | **Fallback.** Zero ripple, and no consumer exists until c4-4. But it ships a wire answer that is *false* (the card was found), it makes the epic's own AC 3.8 a breaking wire change instead of an additive one, and it puts a lie in the generated types that c4-4 would code against if the ordering ever slipped |
| Answer `204 No Content` for the no-image case | **Worth considering and not proposed.** It is honest HTTP and needs no token — but it is a *success*, so it lands in the 200-family branch of the generated types and c4-4 would have to special-case an empty body. A token keeps every non-image outcome in one shape |

**The cost, stated honestly.** Option 1 ripples into eight sites **twice over** (two tokens, one
commit), one of which is a `tsc` failure rather than a test failure, plus the skills-tree grep.
It also freezes two tokens into the generated union before a consumer exists — the same bet c1-4
made with `internal_error`, c3-2 with `card_not_found` and c3-4 with `forbidden`, all three of which
the retros judged correct. *Recommendation: option 1. Exact token spellings are yours to pick;
`no_image_data` and `image_fetch_failed` read unambiguously and neither collides with the existing
eight.*

---

**Q3 — The parameter contract: how wide is `size`, and how is `face` typed?**

Proposed, three parts:

1. **`size` is a `Literal` of all six measured keys** — `small`, `normal`, `large`, `png`,
   `art_crop`, `border_crop` — **defaulting to `normal`**. All six are present on every card
   (measured, 40,960 objects), so none is a broken promise; `normal` is FR-19's grid size and the
   most-requested value; `large`/`png` are the detail panel's; `art_crop` is what the legacy viewer
   used and c4-5 may want. A `Literal` generates an `enum` into the schema, so c4-4's TypeScript
   can't misspell one, and an unrecognised value is `400 invalid_request` from the shipped handler.
2. **`face` is `int` with `ge=0`, defaulting to `0`** — not `Literal[0, 1]`. Two faces is the
   overwhelming case but not the only one (3,222 two-face cards, 2 three-face, 1 five-face), and a
   `Literal[0,1]` would answer `400` where AC 7 says `404` for a card that simply has fewer faces.
   No upper bound in the type: the bound is the resolved list's length, and exceeding it is
   information (`404`), not malformation.
3. **The parameters are query parameters with defaults, so `GET /api/card-image/{id}` alone is
   valid** and means "the normal-size front face" — the request c4-4 makes 100 times per deck.

*Recommendation: as proposed, all three parts.*

---

**Q4 — Does this story take the `CardFace` typing homed on it?** *(genuine fork)*

`deferred-work.md` homes it on *"c3-5 or c4-3, whichever consumes a face first"*, with the fix shape
already written: a typed `CardFace` Pydantic model regenerated into the component set. c3-5 is the
first consumer — in Python, not TypeScript, which is what makes it a question.

| Option | Verdict |
| --- | --- |
| **Take it, with `model_config = ConfigDict(extra="allow")`** and named fields `name`, `mana_cost`, `type_line`, `oracle_text`, `image_uris` | **Proposed.** The resolver is the one piece of code in this app that must never get the face shape wrong, and `list[dict[str, Any]]` means every read is an `isinstance` narrowing that `mypy` cannot check the *meaning* of. `extra="allow"` is what makes it safe: the 24-key census means a strict model would silently truncate `lookup_card_by_name`'s output for every shipped MCP tool — AC 22 is the test that proves it does not. c4-3 and c4-6 then inherit a checked type instead of a hand-cast |
| Defer to c4-3 | **Fallback**, and defensible: the deferral's stated concern is TypeScript-side (*"every face access in the UI will be a hand-cast"*), and this story's consumption is Python. But it leaves three stories reasoning about `dict[str, Any]`, and c4-3 would then change a shared `src/data` schema **and** the wire while also building a component |
| Take it strictly (`extra="forbid"` or default) | **Rejected.** Default Pydantic behaviour drops unknown keys, which silently changes shipped MCP tool output for 6,455 face objects carrying up to 24 keys. c3-4 chose `extra="forbid"` for a *request* model with no clients; this is a *response* model with live consumers, and the two situations are opposites |

*Recommendation: as proposed — take it, `extra="allow"`, with the lossless round-trip test and the
MCP tool suite run explicitly. Component set 11 → 12; one pin; the plugin mirror covers
`src/data/schemas/card.py` too.*

---

**Q5 — The fetch seam: who owns the client, what hosts are allowed, and what does the browser
cache?** *(genuine fork on the first part)*

Three sub-decisions.

*The client.* Proposed: **one `httpx.AsyncClient` created in the lifespan beside
`app.state.database`, closed in `_shutdown`.** Three reasons: connection reuse (a per-request client
means a fresh TLS handshake for each of ~100 tiles, which is the difference between a polite trickle
and a self-inflicted stampede); AD-10 symmetry (created where every other effectful thing is
created, torn down in reverse order); and **testability** — a lifespan-owned client is the seam a
test replaces with `httpx.MockTransport`, which is what makes AC 28's "no unit test touches the
network" cheap rather than a monkeypatching exercise. It is **not** the pacer and must not grow into
one: c3-6 adds the semaphore *around* it. The alternative — a client per request, consolidated by
c3-6 — is smaller today and pays for it twice.

*The host allow-list.* Proposed: **`https` scheme only, host in `{cards.scryfall.io,
errors.scryfall.com}`**, with the second member justified by measurement rather than by generosity —
3 real cards (`Sparkspitter`, `Ondu Champion`, `Gorehorn Minotaurs`) store
`https://errors.scryfall.com/soon.jpg` in all six size keys, and refusing them would report a
fetch failure for cards whose data is exactly as Scryfall shipped it. Those three ids get a named
test whichever way you rule. A suffix match on `.scryfall.io`/`.scryfall.com` is the looser
alternative; an explicit two-host set is the one that fails safely if the corpus changes under us.

*The cache headers.* Proposed: **`public, max-age=31536000, immutable` on a served image**, reusing
`spa.py`'s constant, and **`no-store` on every failure answer**. The success case is safe because
AD-11 has *already* accepted serving a stale image — the cache key is id + size + face and a data
refresh does not invalidate it — so an immutable browser cache adds no new staleness class while
removing repeat traffic entirely, which is what NFR-05's 1-second warm render wants. The failure
case must never be cached, or one flaky fetch leaves a permanently broken tile in that tab.

*Recommendation: as proposed, all three parts.*

---

**Q6 — Does this story take the discriminator-prose item homed on it by name?**

`deferred-work.md` homes one here: the same three paragraphs about the image discriminator live in
`routes/cards.py`'s route docstring and `src/data/schemas/card.py`'s `Card` docstring, regenerate
into two places in `openapi.json`, and have **no drift gate between them** — *"Home: c3-5, which
re-tells this rule for the image route and will make it three copies if unaddressed."*

Proposed: **take it**, following c3-2/c3-3/c3-4's precedent that a story takes the convention
decisions filed against it. The fix shape the entry offers is a single source: **the rule is stated
once, where the data lives** (`src/data/schemas/card.py` — and under Q4 it belongs on `CardFace`'s
`image_uris` field, which is the most precise home it will ever have), and the two route docstrings
state only what their own operation does with it, pointing at the source. Add the gate the entry
suggests — one test asserting the wire descriptions agree on the discriminator sentence — so the
third copy cannot appear silently later.

The related 413-on-a-body-less-GET wart is homed on *"the next story that touches `error_responses`'s
declaration helper, else c3-9"*. This story does not need to touch that helper, so the proposal is
to **leave it** and let c3-9 take it as written — but say so in the record rather than letting a
third GET quietly inherit it unremarked.

*Recommendation: take the prose item; leave the 413 wart to c3-9 with a note.*

---

## Dev Agent Record

### Agent Model Used

Claude Opus 5 (1M context) — `claude-opus-5[1m]`, via `bmad-dev-story`.

### Open questions — Brad's answers

**All six answered "as proposed", 2026-08-01 — the sixteenth story running.** Q2, Q4 and Q5 were
the genuine forks; each was presented with its real alternatives and its cost before being ruled.

| Q | Ruling | What shipped |
| --- | --- | --- |
| Q1 | As proposed | Mechanism in a new `src/companion/app/images.py`; the route joined **`cards.router`** in `routes/cards.py`. Measured rather than assumed: `build_app()`'s ordering block and `test_spa.py`'s differential router list both needed **no edit**, and `test_spa.py` passes unchanged (56 tests). `cards.py`'s "deliberately nothing here but a lookup" sentence was rewritten in the same commit, as the question required |
| Q2 | As proposed, spellings as suggested | **Two** new tokens: `no_image_data` (404, permanent) and `image_fetch_failed` (502, transient). All eight ripple sites worked, twice over, in one commit |
| Q3 | As proposed, all three parts | `size` = `Literal` of the six measured keys, default `normal`, generated as an `enum`; `face` = `int` with `ge=0`, default `0`, **no upper bound in the type**; both query parameters with defaults, so a bare `GET` means "the normal-size front face" |
| Q4 | As proposed | `CardFace` with `model_config = ConfigDict(extra="allow")`. Components 11 → 12. Two consequences the question did not price — see § Deviations |
| Q5 | As proposed, all three parts | One lifespan-owned `httpx.AsyncClient`; `https` + `{cards.scryfall.io, errors.scryfall.com}`; `public, max-age=31536000, immutable` on success and `no-store` on every failure |
| Q6 | As proposed | Prose item **taken**: the rule is `IMAGE_DISCRIMINATOR`, stated once, with a family-keyed gate. The 413-on-a-body-less-GET wart **left to c3-9** with a note, as recommended — this story never touched `error_responses`'s declaration helper signature |

### Baseline (Task 0, measured — not assumed)

Branch `feat/companion-c3-5-card-image` cut from the umbrella tip **`3bfe95f`**, confirmed by
`git rev-parse origin/feat/companion-c3`.

| Gate | Baseline | Final |
| --- | --- | --- |
| `uv run pytest` | **2140 passed**, 1 skipped, 110.52s | **2275 passed**, 1 skipped, 115.04s |
| `uv run ruff check .` | All checks passed! | All checks passed! |
| `uv run ruff format --check .` | 300 files already formatted | 305 files already formatted |
| `uv run mypy src/` | no issues in 88 files | no issues in **89** files |
| `uv run mypy src/ --platform win32` | no issues in 88 files | no issues in **89** files |
| `npm run lint` (ui) | clean | clean |
| `npm run format:check` (ui) | All matched files use Prettier code style! | same |
| `npx tsc -b --force` | exit 0 | exit 0 |
| `npm test` (ui) | **558 passed**, 29 files | **565 passed**, 30 files |
| `npm run build` | ✓ built | ✓ built |
| committed `paths` / `components` | **6 / 11** | **7 / 12** |

SPA bundle SHA-256 at Task 0 and again at the end — **byte-identical**, source and mirror, after a
real `npm run build` rather than an assumption (`index-DE70muY2.js` `FAEEEA472ADD5078`,
`index-DmxBiI94.css` `0A3C142D84B5A98D`, `index.html` `8E65C0615CF66044`, the Space Grotesk
`.woff2` `0640890476FC1198`, `favicon.svg` `9BE16EA2FE3670DE`). This story ships no runtime
frontend code, and the two `states.ts` maps it edits are still referenced by nothing at runtime —
c3-9 wires them — so they tree-shake exactly as before.

**The four shapes, re-measured on this machine, read-only, against the live 38,261-card database.**
Every number in the story reproduced exactly; nothing was inherited.

| # | Shape | Story's claim | Measured |
| --- | --- | --- | --- |
| A | top-level `image_uris`, `card_faces` JSON-null | 35,036 | **35,036** |
| B | top-level `image_uris` + faces, no per-face images | 368 | **368** |
| C | `image_uris` null + every face imaged | 2,778 | **2,778** |
| D | faces present, no images anywhere | 79 | **79** |
| — | both fields null | 0 | **0** |
| — | cards carrying **both** sources | 0 | **0** |
| — | partially imaged cards | 0 | **0** |

Also confirmed: face-count histogram 2 → 3,222 · 3 → 2 · 5 → 1; **exactly one** size key-set across
all 40,960 image maps (all six, always); hosts 245,742 `cards.scryfall.io` + **18**
`errors.scryfall.com` on the three named cards; `png` → `.jpg` on exactly **3** objects; face 0 →
`/front/` and face ≥1 → `/back/` with **0 mismatches** over 5,556 imaged faces; 6,455 face objects
carrying **24 distinct keys** with `layout` on only **66**; `cards` has **23 columns and no
`layout`**; and the SQL trap — `COUNT(*) WHERE image_uris IS NOT NULL` returns **38261** while
`<> 'null'` returns **35404**.

### Debug Log References

**The generated TypeScript for the first non-JSON 200 (AC 18 — a measurement deliverable).**
Recorded verbatim, because nothing in this repo had ever exercised the path and c4-4 builds
against it:

```ts
200: {
    headers: {
        [name: string]: unknown;
    };
    content: {
        "image/*": string;
    };
};
```

Four things worth carrying forward:

1. **The body is typed `string`, not `Blob` or `ArrayBuffer`.** `openapi-typescript` renders
   `{"type": "string", "format": "binary"}` as `string` and there is no option that would render
   it otherwise. **This is the one genuinely misleading thing in the generated file**: a fetch
   layer that trusts the type will reach for `.text()` or `.json()` on an image. c4-4 must read
   the response as a blob and must not derive its handling from this type. Filed as a
   `ui/README.md` blind-spot row and named in `scripts/dump_openapi.py`'s docstring.
2. **The operation still type-checks as an ordinary `paths` member.** `npx tsc -b --force` is
   clean, `wire-contract.test.ts` reads the operation without special-casing it, and nothing about
   the binary content block needed a schema exception.
3. **FastAPI did not add an `application/json` alongside it.** The hand-declared `content` block
   *replaces* the default rather than merging with it — measured, not predicted, and the reason
   `test_routes_card_image.py` asserts `"application/json" not in content` explicitly.
4. **`without_python_docstring_sections` leaves the block alone**, as the story predicted: a
   binary content block carries no `description`, so the walker never touches it.

**`CardFace`'s generated type**, the other thing worth recording, since `extra="allow"` had no
precedent in the document:

```ts
CardFace: {
    name?: string | null;
    mana_cost?: string | null;
    type_line?: string | null;
    oracle_text?: string | null;
    /** @description Images live in one of two places, and which one is decided by … */
    image_uris?: { [key: string]: string } | null;
} & {
    [key: string]: unknown;
};
```

An intersection with an open index signature — c4-3 gets the five named fields typed *and* keeps
access to the other nineteen.

**The 503-before-400 ordering, re-measured for this route** rather than inherited by argument:
`?size=bogus` against an absent database answers **503 `database_not_initialized`**; the identical
request against a ready database answers **400 `invalid_request`**. Both pinned, and the
consumer-facing half is a wire-visible `Warning:` per c3-2's round-2 ruling.

**Probe outputs — five mutation probes (AC 30), each verified on disk before the verdict and
reverted after.** Each was checked for the *right* failure, not merely for a red.

| # | Mutation | Result |
| --- | --- | --- |
| (a) | resolver made to always return the top-level image | **CAUGHT** — `test_images.py::TestResolveFaceImages::test_shape_c_resolves_one_entry_per_face_in_face_order`. The face-level test, not a route test, which is the point of the resolver being a pure unit |
| (b) | `face` made to index `card_faces` instead of the resolved list | **CAUGHT** — `test_routes_card_image.py::TestTheFourShapes::test_shape_b_has_no_face_one`. A split card's `face=1` stopped 404ing, exactly as designed to |
| (c) | host allow-list bypassed (`is_fetchable` → `return True`) | **CAUGHT** — `test_images.py::TestUrlAllowList::test_a_disallowed_origin_is_refused[http://…]`, on the scheme case first |
| (d) | the route silently unregistered (path renamed) | **CAUGHT twice.** With `-x`: `test_openapi_contract.py::test_committed_schema_matches_the_live_app`. Re-run **without** `-x` against the route file alone: **48 failed, 14 passed** — so the behavioural half catches it too, not only the drift gate. (Worth the second run: c3-1's review found `TestNotShadowedBySpa` passing with the router *deleted*.) The 14 that still pass are the committed-schema readers and the AST scans, which read files rather than the app — consistent, not a hole |
| (e) | `CardFace` made strict (`extra="ignore"`) | **CAUGHT** — `test_card_face_schema.py::test_a_real_face_round_trips_with_no_key_lost_and_no_value_changed` |

Each probe script verified its patch was on disk before running the suite, and asserted the file
was byte-identical to the original afterwards. All five reverted cleanly.

**AC 20's planted type name, staged.** A scratch `ui/src/__probe_planted.ts` declaring
`interface CardFace` was written and `git add`ed, then `npm test`:

```
- []
+ [
+   "src/__probe_planted.ts declares CardFace",
+ ]
 ❯ tests/wire-contract.test.ts:145:23
 Test Files  1 failed | 29 passed (30)
      Tests  1 failed | 564 passed (565)
```

**With no edit to the ban mechanism** — it derived the new name from the regenerated
`components.schemas`. Reverted (`git rm --cached` + delete); `npm test` back to **565 passed**.
`CardFace` therefore joins the banned-name list in `ui/`, and its alias is homed on **c4-1**
alongside `Card`'s.

**Two guards caught their own author before review did**, which is the standing agreement working:

* The Q6 discriminator family gate went red on its **first** run — on the `CardFace` class
  docstring I had just written, which restated the rule in its own words. Reworded to point at the
  field rather than retell it.
* The AC 16 "nothing this story does not own" scan went red on `images.py`'s **own module
  docstring**, which names the pacer, the disk cache and `data_dir()` deliberately. Rewritten as an
  AST walk over identifiers and non-documentation string literals, and then paired **both ways**: a
  planted breach spelled to evade (an aliased `asyncio as aio` semaphore, a split f-string host, a
  `.mkdir` on a local) is caught, and a module that merely *documents* the banned things stays
  green. That second direction is the one the first version would have failed.

**The skills-tree grep (c3-3's lesson) was run and found nothing stale.** `.claude/skills/**` and
`plugin/skills/**` mention `card_not_found` and `deck_not_found` **only as MCP tool `status`
values** — a separate, older vocabulary that predates the wire contract. Neither new token appears
anywhere, and no skill documents the companion's HTTP error contract at all. The spelling collision
is itself a trap for **c6-1** and is ledgered for it by name.

### Probe outputs

See § Debug Log References above — the five mutation probes and AC 20's planted type name are
recorded there with their output, so the evidence sits beside the measurement it belongs to.

### Completion Notes List

**What this story actually is.** The backend stopped being self-contained. Everything awkward
follows from one fact — it now reaches a machine on the internet — and the story was right that the
risk is the **resolution**, not the fetch. The fetch is about forty lines of `httpx`. The resolver
is nine lines and every one of them is load-bearing.

**Tasks 0–8 complete; Task 9 is Brad's** (`dev-story` stops at `review`, per the standing ruling).

1. **The resolver** (`images.resolve_face_images`) — pure, no I/O, no session, unit-tested before
   the route existed. Keys on the presence of per-face `image_uris` and on nothing else; it could
   not key on a layout string if it wanted to, because `cards` has no such column. Two orderings
   are pinned rather than left to the order of the `if`s: per-face wins over top-level (0 rows
   carry both, but the specific answer is the right one), and a partially imaged card keeps only
   its imaged faces in face order (0 rows, and the signature cannot represent a hole).

2. **`face` indexes the resolved list, not `card_faces`** — the one sentence that decides every
   awkward case at once, and the one probe (b) exists to protect. A split card has two faces and
   one image; the three >2-face cards in the corpus are all shape B and behave identically.

3. **The route** joined `cards.router` and reuses `CardId` — the constant imported, not a second
   copy of the uuid regex. The trailing-newline spelling (`<canonical-id>%0A`) is pinned by name
   here as it is next door, because the guarantee comes from Pydantic's Rust regex engine and not
   from the `$`.

4. **The no-image precedence is structural, not an ordered pair of checks.** A card with no images
   resolves to an empty list, so every face is out of range and one comparison answers both. A
   shape-D card asked for `face=7` therefore reports "no image data" by construction.

5. **The fetch** validates scheme and host **before** opening a socket, sends a descriptive
   `User-Agent` and an image `Accept`, bounds the exchange on both axes (a split `httpx.Timeout`
   **plus** an outer `asyncio.timeout`, because httpx's read deadline caps the gap between chunks
   and not the exchange), caps the buffered body at 16 MB, and maps every upstream outcome —
   refused URL, connect failure, timeout, non-2xx, non-image content type, oversized body — onto
   `image_fetch_failed`. **It never returns a substitute image.**

6. **`trust_env` is left at httpx's default `True`**, a deliberate divergence from
   `client.py`'s `trust_env=False` rather than an inconsistency: that module probes *loopback*,
   where a proxy env var would misroute a health check and `.netrc` could attach an
   `Authorization` header to a local probe. This one crosses the public internet, where a user
   behind a corporate proxy has no other way out, and it carries no credential.

7. **The allow-list is a parsed-hostname comparison**, not a substring test, and the test file
   plants every cheap evasion: `cards.scryfall.io.evil.example` (suffix), `evilcards.scryfall.io`
   (prefix), `cards.scryfall.io@evil.example` (userinfo), plus `127.0.0.1:8765` — the port the
   companion itself serves on — and `169.254.169.254`.

8. **Both new tokens shipped with their UI state** (AD-16's pairing rule), and the UI half was
   unusually cheap because `EXPERIENCE.md` already carried both rows. `PlaceholderKey` gained
   `'named-card'`, which is a genuinely different destination from c3-2's `'unknown-card'`:
   *unknown* means the app cannot name the card, *named* means it can and only lacks the picture.
   `ui/tests/named-card-copy.test.ts` gates that pairing against the artefact, and asserts
   specifically that neither token points at `'unknown-card'` — the copy-paste mistake that would
   type-check perfectly and put "Unknown card" under a card the app can name.

9. **`error_response` now stamps `Cache-Control: no-store` on every typed error**, feature-wide.
   AC 15 needs a failure not to be cached, and a route structurally **cannot** attach a header —
   that is the whole point of deriving the status from the token. Saying it once in the one place
   that can say it was better than widening `CompanionError`. It is not defensive: RFC 9111 §4.2.2
   lets a cache store a 404 heuristically with no explicit freshness, and this story answers 404
   for a card whose image is momentarily unavailable.

10. **The `image_shapes` fixture moved to `conftest.py`** rather than being copied. Nothing about
    the seeded data changed except that every URL is now on an origin the route will actually fetch
    from and every size URL is distinct — without that, a route that ignored `size` entirely would
    have passed all six size tests.

**What is deliberately absent, and it is a decision rather than an omission:** no pacer (c3-6), no
disk cache (c3-7), no negative cache or backoff (c3-8), no cache directory in the lifespan, no SPA
consumer (c4-4). No hook, registry, no-op semaphore or placeholder was built for any of them —
c3-4's ruling that *"an unused hook is a design decision made by a story that cannot see the
requirements"*. `test_routes_card_image.py::TestNothingThisStoryDoesNotOwn` asserts the absence
over the AST, in both directions.

**The epic's "the SPA never contacts Scryfall directly" AC is satisfied negatively here**, and its
positive half is homed on **c4-4** by name. Measured: **no file under `ui/src` contains a Scryfall
host**, and neither generated file does either — `openapi.json` and `types.d.ts` were both scanned.

#### Deviations, booked at the time they were made

Three, all under Q4, and none of them is a shortcut:

1. **`src/viewer/view_model.py` was edited, and the story's "not touched, deliberately" list says
   it is frozen until c8-1.** Typing `Card.card_faces` as `CardFace` made `mypy --strict` red at
   five call sites that read faces with `.get(...)` — `classifiers.py:113`, `mana_base.py:315` and
   `:326`, `view_model.py:180` and `:226`. Every one is a mechanical conversion to attribute
   access; `view_model.py:180` reads a caller-supplied key and became `getattr(face, key, None)`,
   which still reaches `power` and `toughness` because `extra="allow"` exposes extras as
   attributes. **This is the type system doing its job**, and the alternative was declining a
   ruling Brad had just made. The story's not-touched list was written assuming Q4 had no ripple
   outside the companion; it has one, it is five lines, and it is now on the record. "Frozen" was
   read as *do not develop it*, not as *let the repo fail its own gate*.

2. **Face objects now serialise explicit `null`s for named fields the source omitted.** A face
   dict that carried no `type_line` used to reach the wire without the key; it now carries
   `"type_line": null`. Additive, never a truncation — `test_card_face_schema.py` pins exactly
   which keys can be added and that nothing the source *did* carry is touched. The consequence
   that mattered: three assertions in `test_routes_cards.py` tested **key presence** and had to
   become **value truthiness**. That is the better test — "presence of per-face `image_uris`" now
   means the same thing in the resolver, in the tests and in `IMAGE_DISCRIMINATOR` — but it is a
   wire-shape change to `card_faces` entries and is stated as one rather than buried in a diff.

3. **The path parameter is spelled `scryfall_id` while its sibling spells the same identifier
   `card_id`.** The epic and this story both name the path `/api/card-image/{scryfall_id}` three
   times over, so the published path follows the spec; the route docstring says out loud that it is
   the same identifier and the same constraint as `GET /api/cards/{card_id}`, and
   `test_routes_card_image.py` asserts the two operations publish an identical `pattern`. The
   alternative — quietly renaming it to `card_id` for internal tidiness — would have made the
   committed artifact disagree with the epic.

**One declined item, ledgered rather than silently skipped:** a distinct "no such face" token. An
out-of-range face answers `404 no_image_data`, the same token as a card with no artwork at all.
AD-11 asks for *permanent* vs *transient* to be distinguishable, not for two flavours of permanent,
and `EXPERIENCE.md` draws the same placeholder for both — so a third token would have cost eight
ripple sites to express a distinction no consumer acts on. AC 9's precedence is honoured
structurally instead, and the reasoning is in `deferred-work.md` under c3-5.

**The seven-row forward-dated-comment inventory (AC 24), all worked:**

| # | Location | Action taken |
| --- | --- | --- |
| 1 | `routes/cards.py:1-12` | **Rewritten.** The module now says it holds "a lookup and a proxy", names the sentence that stopped being true, and records that joining an existing router cost no `build_app()` or `test_spa.py` edit |
| 2 | `scripts/dump_openapi.py:20-27` | **Restated with its exception.** Counts updated to twelve components / seven paths; the `response_model` sentence now carries the binary-body exception in full; **c3-6 named next** |
| 3 | `deps.py` (`DbSession` callers) | **Updated.** c3-5 joins the list, with the note that a `DbSession` consumer is no longer necessarily a pure read and that its outbound client is a separate app-state resource |
| 4 | `errors.py` (`error_responses` callers) | **Updated.** c3-5 declares three tokens — the most any route has — and is the first with a non-JSON success body |
| 5 | `main.py:434-441` (the ordering block) | **Updated.** Records c3-5 as the second route-on-an-existing-router case, both files verified unchanged, and names the 413 it therefore inherits |
| 6 | the duplicated discriminator prose | **Resolved** (Q6): one constant, three field descriptions, one family-keyed gate |
| 7 | `deferred-work.md`'s two c3-5-homed entries | **Both resolved by name**, each with what the entry did not price |

**AC-by-AC:** all 31 satisfied. The two whose evidence is easiest to lose: **AC 18** is the
generated-TypeScript measurement above (recorded verbatim, including the misleading `string`), and
**AC 25**'s bundle re-measurement was done by actually rebuilding rather than by assuming a
frontend-free story leaves it alone.

### File List

**New**

- `src/companion/app/images.py`
- `tests/unit/companion/test_images.py`
- `tests/unit/companion/test_routes_card_image.py`
- `tests/unit/data/test_card_face_schema.py`
- `ui/tests/named-card-copy.test.ts`

**Modified**

- `src/companion/app/routes/cards.py`
- `src/companion/app/main.py`
- `src/companion/app/errors.py`
- `src/companion/app/deps.py`
- `src/companion/contracts.py`
- `src/data/schemas/card.py`
- `src/logic/assessment/classifiers.py`
- `src/logic/assessment/mana_base.py`
- `src/viewer/view_model.py`
- `scripts/dump_openapi.py`
- `tests/unit/companion/conftest.py`
- `tests/unit/companion/test_committed_schema.py`
- `tests/unit/companion/test_errors.py`
- `tests/unit/companion/test_routes_cards.py`
- `tests/unit/data/test_card_repository.py`
- `tests/unit/data/test_schemas.py`
- `ui/src/api/openapi.json` (regenerated, committed)
- `ui/src/api/types.d.ts` (regenerated, committed)
- `ui/src/api/schema.ts`
- `ui/src/api/schema.test.ts`
- `ui/src/components/StatePanel/states.ts`
- `ui/src/components/StatePanel/states.test.ts`
- `ui/README.md`
- `plugin/**` (rebuilt mirror, incl. the new `images.py`)
- `_bmad-output/implementation-artifacts/deferred-work.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- this story file

### Change Log

| Date | Change |
| --- | --- |
| 2026-08-01 | Story created — context engine analysis over the epic, spine, UX artefacts, the four prior C3 records, seven review passes, the shipped code and the live 38,261-card database |
| 2026-08-01 | Q1–Q6 answered by Brad, all six as proposed (the sixteenth story running); Q2, Q4 and Q5 were genuine forks |
| 2026-08-01 | Tasks 0–8 implemented. `GET /api/card-image/{scryfall_id}` — the first non-JSON response, the first outbound network call and the first "neither here-it-is nor you-asked-wrong" answer in the feature. Two new reason tokens across eight ripple sites twice over; `CardFace` typed with `extra="allow"`; the image discriminator reduced to one source with a family gate. Suites 2140 → 2275 Python and 558 → 565 frontend; paths 6 → 7, components 11 → 12. Five mutation probes all caught; two of this story's own guards caught their author before review. Status → `review` |
