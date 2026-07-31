---
epic: c3
story: c3-3
work_branch: feat/companion-c3
story_branch: feat/companion-c3-3-format-check-endpoint
depends_on: c3-2 (PR #30, merged into the umbrella at 2a787ac) — the routes package, the wire pipeline, the DbSession pattern and the wire-prose gate all exist
baseline_commit: 2a787ac
---

# Story C3.3: Format check endpoint over the existing validators

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As Brad glancing at the right column,
I want the app to tell me whether my deck is legal and where it isn't,
so that I see the same verdict the agent would give me, without asking for it.

**What this story really is.** c3-1 was a projection that had to move down a layer. c3-2 was a
closed set that had to be extended. **This one is a specification that asks for six checks over a
validator that produces four of them** — and the gap is the story.

`src/logic/deck_validator.validate_deck` already exists, is already Pydantic, and is already the
rule the `validate_deck` MCP tool applies, so AD-1's "call the existing validators, reimplement
nothing" is nearly free. But three things do not line up, and none of them can be papered over in
the route:

1. **The validator reports only what is wrong. UX-DR21 wants a row per *check*, passing or not.**
   `DeckValidationReport` carries `violations: list[DeckViolation]` and nothing else. A panel that
   renders "one row per check, tone-mapped pass → positive" needs a row for a check that *passed*,
   and there is nowhere in the current output for one to come from. Something must project
   violations-plus-silence into rows. **Where that projection lives is Q1**, and c3-1's Q1 ruling
   (the projection moves *down* into the shared core so both shells share one implementation) is
   the precedent it has to answer to.

2. **"Banned" is a check UX-DR21 names and `src/logic` does not distinguish.** A banned card and a
   card that simply is not in the format both come out as one `format_legality` violation, because
   the test is `card.legalities.get(format) != "legal"`. Deriving the split *in the endpoint* is
   exactly what this story's own AC forbids ("no deck-construction rule is reimplemented in this
   endpoint"). **Q2.**

3. **"Rotation exposure" has no local data at all** — and this is c3-2's prices finding again, in a
   different column. Measured below: 23 columns on `cards`, no `released_at`, no `set_type`, no set
   table. `released_at` is read by the importer to pick a canonical printing and then **thrown
   away**. There is nothing in this database from which rotation can be computed. **Q3.**

Everything else this story touches is already built and already gated. There is **no new reason
token** (`deck_not_found` has shipped since c3-1), so unlike c3-2 there is no closed-set extension
and no retro ruling attached — the wire's error vocabulary is untouched.

**Nineteen things were measured on this machine at `2a787ac` — do not rediscover them.** Several
are counts taken from the real 38,261-row card database and the real 40-deck deck table.

### The seam that already exists (do not rebuild any of it)

1. **The validator is done and it is already Pydantic.** `src/logic/deck_validator.py:262-407`
   exports `validate_deck(deck, *, format=..., games=...) -> DeckValidationReport`, a `BaseModel`
   carrying `is_legal`, `format`, `mainboard_count`, `sideboard_count` and
   `violations: list[DeckViolation]`. `DeckViolation.rule` is a closed `Literal` of **seven**
   members: `min_deck_size`, `max_sideboard_size`, `copy_limit`, `singleton`, `format_legality`,
   `game_availability`, `unknown_format`. It is pure — no session, no I/O.

2. **The MCP tool is the reference caller, and this route must look like it.**
   `src/mcp_server/tools/deck_analysis.py:272-351` loads with `get_deck_with_cards`, calls
   `_logic_validate_deck(deck, format=format, games=games)`, and nests the report verbatim in
   `ValidateDeckResult.report` (`:110` — *"Nests the logic's `DeckValidationReport` directly
   (already Pydantic)"*). AD-1 is satisfied by doing the same thing: load, call, project. **No
   `select`, no `text`, no rule.**

3. **`DeckRepository.get_deck_with_cards` is the only correct loader** (`deck.py:547-576`). It
   `selectinload`s `deck_cards` *and* each entry's `card`, which the validator needs: it reads
   `card.type_line` (basic-land exemption), `card.legalities` (format legality) and `card.games`.
   `get_deck` / `find_deck_by_name` / `update_deck` do **not** eager-load, and
   `DeckModel.deck_cards` is `lazy="noload"`, so a `Deck` from any of those arrives with an **empty
   list** and the validator answers "mainboard has 0 cards, standard requires at least 60" for a
   perfectly legal deck. **This is c3-1's landmine 10 in a new costume** — a silent zero, not a
   crash. AC 4 pins non-zero counts for exactly this reason.

   The cost is real and is **accepted, not optimised**: eager-loading a 100-card deck means 100 full
   `Card` rows (including `oracle_text`, `image_uris`, `card_faces`) materialised to compute a
   handful of booleans. There is no cheaper path that AD-1 permits — a count-and-legality-only query
   here would be a second read path over one shape, which is exactly c3-1's ruling on the
   `list_decks` over-fetch (ledgered, homed at c10-3). If it is worth ledgering again, ledger it;
   do not solve it in this shell.

4. **`CardSummary` cannot feed the validator.** `src/data/schemas/deck.py:111-133`'s
   `DeckCardSummary` nests `CardSummary`, which omits `legalities` (and `image_uris` /
   `card_faces`) "so a response carrying many cards stays small". The validator needs
   `legalities`. So this route reads the **`Deck`** the repository returns (whose `DeckCard.card`
   is the full `Card`) and must **not** be tempted to reuse `DeckDetail`.

5. **`DbSession` is the only session source** (`deps.py`). Annotate it. Both 503 paths — `503
   database_not_initialized` from `get_session` and `503 database_unavailable` from
   `install_error_handling` — arrive with no per-route ceremony. A `try/except DatabaseError` in a
   route body is a regression, not defence (c1-6, C1 retro).

6. **`error_responses("deck_not_found")` is the per-route declaration** (`errors.py:124-162`), and
   `errors.py:130` already names c3-1's deck route as its caller. Do **not** re-declare
   `invalid_request` — `build_app()` declares it app-wide (`main.py`), and c3-1's AC 6 established
   that a route declares only what it uniquely produces.

7. **The route belongs on `decks.router` and therefore costs no `test_spa.py` line.**
   `deferred-work.md` names c3-3 in the list of stories that must hand-add a line to
   `tests/unit/companion/test_spa.py:305-307`'s differential router list. **That tax does not apply
   here if the route joins `decks.py`'s existing router** — the differential test compares *path
   sets* built from the same routers, and a new path on an already-included router appears on both
   sides. Measured, not assumed: verify it, and if the route lands in a new module the line is
   mandatory. See Q1's sub-decision.

8. **`install_spa(app)` must stay last** (`main.py`, `MUST STAY LAST`). If Q1 puts the route on
   `decks.router`, `build_app()` needs **no edit at all** — the router is already included above the
   mount. That is the cheapest possible answer to the ordering rule and it should be stated rather
   than discovered.

9. **The test seam is `lifespan_client` + `isolated_data_dir` + `_point_at`**
   (`tests/unit/companion/conftest.py:158-168`, `test_routes_decks.py:41-49`). Every companion test
   flows through the real security envelope; `httpx.ASGITransport` alone sends no lifespan messages
   and yields `500 internal_error`. `is_database_initialized` needs the **full schema plus at least
   one card row**, so build fixtures with `init_database(create_engine(url))`.
   `test_routes_decks.py`'s `_card()` helper mints ids like `"card-anchor"` — fine here, since this
   route's path parameter is a **deck** id, which c3-1 correctly ruled has no declared shape.

### The three-way gap between UX-DR21 and the validator

10. **The spec asks for six checks. Map them yourself before writing code.** `EXPERIENCE.md:37`,
    quoted byte-for-byte:

    > `| Format check panel | P0 | Right column, always present | Legality, size, copy limit, sideboard, banned, rotation exposure |`

    and `EXPERIENCE.md:96`:

    > `| Format check | Right column | One row per check from local validation. Tone maps: pass → positive, advisory → caution, violation → negative. Rows are display-only. |`

    | UX-DR21 check | `src/logic` today | Status |
    | --- | --- | --- |
    | Legality | `format_legality` | **Exists** (but see banned, below) |
    | Size | `min_deck_size` | **Exists** — and is 60-cards-always, see landmine 13 |
    | Copy limit | `copy_limit` / `singleton` | **Exists**, format-aware |
    | Sideboard | `max_sideboard_size` | **Exists** |
    | Banned | — collapsed into `format_legality` | **Q2** |
    | Rotation exposure | — no data source at all | **Q3** |
    | *(unmapped)* | `game_availability` | Not requested by UX-DR21; this route passes no `games` |
    | *(unmapped)* | `unknown_format` | The mechanism behind "no format to check against" — Q4 |

11. **A banned card and an out-of-format card are the same violation today.**
    `deck_validator.py:384` is `if known_format and card.legalities.get(format) != "legal"`. Scryfall's
    legality vocabulary is four values, **measured across all 38,261 cards** (880,003 legality
    entries, zero cards with a null or empty `legalities`; the 23 keys present match
    `_KNOWN_FORMATS`'s 23 members exactly — verified, not assumed):

    | Value | Entries |
    | --- | --- |
    | `not_legal` | 516,401 |
    | `legal` | 362,238 |
    | `banned` | **1,275** |
    | `restricted` | 89 |

    Banned counts per format, top of the list: `duel` 250 · `oathbreaker` 210 · `legacy` 170 ·
    `vintage` 101 · `commander` 83 · `historic` 77 · `pauper` 74 · `tlr` 62 · `modern` 52 ·
    `predh` 48 · `brawl` 35 · `standard` **10**. `restricted` exists only in `vintage` 51 ·
    `duel` 24 · `tlr` 10 · `timeless` 4.

    So the data supports the split cleanly. What it does **not** support is deriving it in the
    endpoint: re-reading `card.legalities[format]` in `src/companion` is a deck-construction rule
    living in the shell, which this story's own AC bans in the same sentence it bans a TypeScript
    reimplementation. **Q2.**

    Note the second edge in the same branch: a **`restricted`** card is *legal* in Vintage with a
    1-copy limit, and today it is reported as "not legal in vintage" — wrong, but latent (see
    landmine 15). Do not fix it silently while in the neighbourhood; ledger it or rule on it.

12. **Rotation exposure has no data source, and this is a measurement, not an opinion.** Measured
    on the real database:

    - `PRAGMA table_info(cards)` → **23 columns**: `id, name, printed_name, oracle_id, mana_cost,
      cmc, type_line, oracle_text, rarity, set_code, set_name, collector_number, colors,
      color_identity, color_indicator, keywords, legalities, card_faces, image_uris, games, power,
      toughness, game_changer`. **No `released_at`. No `set_type`. No release date of any kind.**
    - There is **no sets table**. `sqlite_master` holds `cards`, `decks`, `deck_cards`,
      `bug_reports`, `combo_variants`, `combo_variant_pieces`, `combo_snapshot_meta`, the
      `card_vec*` vector tables and `card_embedding_meta`. Nothing else.
    - `released_at` **is** read during import — `src/data/importers/aggregate.py:113-134` uses it to
      pick the canonical printing (greatest `released_at`, ties by min id) — and is then
      **discarded**. It is never written to a column.

    So rotation cannot be computed locally, at any cost short of a schema change. This is exactly
    c3-2's prices finding: a P0 spec line naming data this project has never held. Unlike prices,
    though, the epic AC names rotation **inside the list of checks the response must cover**, which
    is a stronger claim than FR-17's "prices if present". **Q3** is a genuine fork, not a formality.

13. **The size check is wrong for Commander and Brawl, and this story publishes it to the glass for
    the first time.** `_MIN_MAINBOARD = 60` is applied **regardless of format**
    (`deck_validator.py:158-165`, `:281-285`: *"The 60-card / 15-sideboard limits apply regardless of
    `format` (Phase-1 scope, D-1.6b) … Commander/Brawl 100-card minima remain out of scope, as do
    'any number of copies' exemption cards"*). Brawl is genuinely 60, so the 18 brawl and 2
    standardbrawl decks in the real table are unaffected — but a Commander deck would be told 60 is
    enough when it needs 100. **This is a pre-existing, deliberately documented limitation of
    `src/logic`; it is not this story's to fix.** It *is* this story's to state, because c3-3 is the
    story that puts it in front of a user rather than an agent. Record it; do not widen scope into a
    Commander-size rule.

    **And do not invent an empty-deck branch.** A 0-card deck validates to a `min_deck_size`
    violation, which is correct and needs no special case here, because the *client* already
    suppresses the panel: `EXPERIENCE.md:70` and `:113` both say curve, colour distribution **and
    format check are hidden until the deck has cards**, and the epic pins it as an AC of its own
    (UX-DR33). So the honest backend behaviour is "answer normally"; a bespoke "deck is empty"
    response would be a state c4-10 never renders and a shape nobody asked for.

### What the real data says (measured read-only at `2a787ac`)

14. **The whole deck table, validated against its own format.** 40 decks; **35 legal, 5 not**.
    Violations across all 40: `min_deck_size` **4**, `format_legality` **1**. Formats present:
    `standard` 19 · `brawl` 18 · `standardbrawl` 2 · `historic` 1.

15. **Zero banned cards and zero restricted cards across all 40 real decks.** The single
    `format_legality` violation is a plain `not_legal`. Two consequences, both load-bearing:
    Q2's split **changes no verdict on any real deck today** (it changes which *row* the verdict
    appears in), and the banned row can only be tested against a **synthetic fixture** — say
    Standard's 10 banned printings, or a fixture card whose `legalities` is written by hand. A test
    that seeds a real deck and expects a banned row will pass vacuously by finding nothing.

16. **`decks.format` is `VARCHAR NOT NULL`, and zero of 40 rows are null or blank.** DDL confirmed
    (`CREATE TABLE decks (… format VARCHAR NOT NULL …)`). `DeckRepository.create_deck(name, format:
    str, …)` takes `format` as a **required positional-or-keyword `str`** with no default and no
    emptiness check, so `""` is reachable through the repository even though nothing has ever
    written one. Meanwhile `src/data/schemas/deck.py:12` declares `FormatType = str | None`, so
    `Deck.format` — and the `format` on the wire since c3-1 — is `string | null`.

    This is the deferred entry homed here by name: *"the schema allows null, the database forbids
    it … c3-3 must decide whether 'no format to check against' is keyed on a null format (then the
    column constraint is the bug) or on an unrecognised format string (then the wire type is merely
    wider than the data and can stay)."* **Q4.**

17. **`unknown_format` is already the mechanism, and it is already careful.**
    `deck_validator.py:307-321`: an unrecognised format emits one `unknown_format` violation and
    **skips the per-card legality check**, deliberately — *"a bad format has no key in any card's
    `legalities` dict, so the per-card check would flag every card illegal with no hint the format
    **name** was the problem"*. Structural rules (size, copy limits) still run. `""` is not in
    `_KNOWN_FORMATS`, so an empty format already lands here. `_KNOWN_FORMATS` has **23** members and
    exactly matches the 23 legality keys measured on the corpus — verified, not assumed.

### The wire, the docstrings and the gates

18. **This is the first story to put a `src/logic` model on the wire, and c3-2's gate is watching.**
    `test_openapi_contract.py`'s `PYTHON_INTERNAL_FAMILIES` (shipped by c3-2's Q5) bans, by family:
    Sphinx role markup, any line-anchored Google-style section header outside the two-member
    `Note:`/`Warning:` allowlist, and doctest prompts — scanned over the regenerated `types.d.ts`.
    `_CompanionFastAPI.openapi()` (`main.py`) truncates each description at the first Google header,
    so **only the leading paragraph of a response model's docstring crosses the wire**.

    Whatever Q1 rules, read the docstrings of every model that ends up in `components.schemas`
    before regenerating. `DeckViolation`'s and `DeckValidationReport`'s leading paragraphs are short
    and reST-double-backticked (house style, allowed); their `Attributes:` sections are truncated
    off. But `src/logic/deck_validator.py`'s **module** docstring and `validate_deck`'s own
    docstring are MCP-facing prose — neither crosses the wire (module docstrings and function
    docstrings on non-route functions do not), and that should be **verified after regeneration**,
    not assumed.

19. **Two generated files, two CI jobs, and the plugin mirror.** `npm run gen:api` from `ui/` runs
    `uv run python -m scripts.dump_openapi` then `npm run gen:types`; commit both in the same commit
    (`ui/README.md` — a fresh `openapi.json` beside a stale `types.d.ts` is red in CI and poisons a
    bisect). Committed baseline **measured now**: `paths = ['/health', '/api/decks',
    '/api/deck/{deck_id}', '/api/cards/{card_id}']` (**4**), `components.schemas = ['Card',
    'CardSummary', 'DeckCardSummary', 'DeckDetail', 'DeckSummary', 'ErrorResponse',
    'HealthResponse']` (**7**). Both counts go up. `scripts/dump_openapi.py:24` says *"Story
    **c3-3**'s format check is next"* — this is that story; update it, and update `:23`'s
    "seven components / four paths" sentence with the new counts, and name c3-4.

    And `plugin/**` is **not** "not touched": CI's *"Plugin tree in sync with `src/`"* step
    (`.github/workflows/ci.yml:76-84`) re-runs `scripts.build_plugin` and fails on drift. This story
    edits files under `src/logic/` and `src/companion/`, both mirrored. **Rebuild and commit the
    mirror.**

### Two housekeeping items are homed on this story by name

Both from `deferred-work.md`, both naming c3-3 explicitly. **Q5.**

- **`_is_ref_rooted` will misfire on the first union response model** —
  `tests/unit/companion/test_errors.py:44` puts `anyOf`/`oneOf`/`allOf` in `_OBJECT_SHAPE_KEYS`, so
  a `response_model=X | None` generates a top-level `anyOf` and is refused as a hand-built envelope,
  which it is not: *"the guard's family conflates object-shaping with union-forming."* Two smaller
  3.1 edges in the same helper: a `$ref` carrying legal sibling annotation keys fails
  `set(schema) == {"$ref"}`, and `prefixItems` is absent from the key set. The entry names c3-3 as
  *"the first story likely to hit it"* — plausibly through Q4's "no format to check against" answer.
  **Q4's proposal is written so it does not fire** (one response shape, never a union); that makes
  fixing the guard a choice rather than a forced repair.
- **`ui/README.md`'s blind-spot map is keyed on line numbers with nothing keeping them accurate** —
  *"Home: c3-3, the next story to add a schema to `components.schemas` and therefore the next to owe
  this review pass; it is also the natural point to anchor the README's citations on marker strings
  rather than line numbers."*

---

## Acceptance Criteria

### The route

1. **`GET /api/deck/{deck_id}/format-check` returns a defined report body, unwrapped** (AD-16): no
   `{"status": …}` and no `{"report": …}` wrapper. The path uses **singular `/api/deck/`**, matching
   c3-1's detail route and the epic, and the parameter is named `deck_id`, matching
   `/api/deck/{deck_id}`.

2. **The body carries one row per check, and every row carries a status and a human-readable
   detail** (UX-DR21, `EXPERIENCE.md:96`). The status vocabulary is a **closed `Literal` of exactly
   three**: `pass`, `advisory`, `violation` — the three UX-DR21 tone-maps, and no fourth. Row order
   is **deterministic and declared**, so c4-10 renders a stable panel rather than a set that
   reshuffles between refetches; the order is asserted, not left to a dict.

3. **Every check UX-DR21 names is covered, and any it names that this project cannot answer is
   handled by Q2/Q3's rulings rather than silently dropped.** The mapping table in landmine 10 is
   worked row by row and the outcome for **each of the six** is stated in the record — including
   which rows exist, which do not, and why.

4. **The deck is loaded with `get_deck_with_cards` and the counts on the wire are non-zero for a
   seeded deck.** A test asserts a seeded deck's `mainboard_count` matches the seeded quantity sum
   — not merely that the field is present — because a non-eager-loaded `Deck` yields a silent
   `0`-card report that looks like a legitimate `min_deck_size` violation (landmine 3, c3-1's
   landmine 10 restated). Paired for non-vacuity with a deck seeded to a **different** count.

5. **No deck-construction rule is reimplemented in `src/companion` or in TypeScript** (AD-1, the
   epic AC). Explicitly absent from the `src/companion` diff: any reading of `card.legalities`, any
   copy counting, any comparison against 60 / 15 / 4 / 1, any format-name set. A test greps the
   companion diff's new module for those shapes, or asserts the route module imports the validator
   and nothing rule-shaped — stated as a mechanism, not a comment.

6. **A deck id that does not exist answers `404 {"reason": "deck_not_found"}`.** The handler raises
   `CompanionError("deck_not_found")`; it does not construct a response, does not pass a status, and
   does not import `JSONResponse`. Asserted on status **and** exact body. The route declares
   `responses=error_responses("deck_not_found")` and nothing else; `build_app()`'s app-level
   `responses` is unchanged.

7. **A deck whose format cannot be checked answers `200` with a defined report**, not an error
   (the epic AC), per Q4's ruling. The response shape is **the same object** in every case — no
   union, no `X | None` response model — so c4-10 has one shape to render and
   `test_errors.py::_is_ref_rooted` is not tripped (landmine's Q5 entry). A test drives the
   unknown-format path end to end and asserts the status is `200`, the body is the report shape, and
   the affected rows carry the status Q4 rules.

8. **The session comes from `DbSession`**, and both 503 paths are proved **through the real route**:
   a missing database file answers `503 {"reason": "database_not_initialized"}` and a
   present-but-corrupt file answers `503 {"reason": "database_unavailable"}`. No
   `add_exception_handler` and no `try`/`except DatabaseError` anywhere in the diff.

9. **No `games` query parameter is added.** UX-DR21 asks for six checks and platform availability is
   not one of them; the validator's `games` argument stays `None` from this route, so
   `game_availability` never fires. Stated in the record as a deliberate omission with the reason,
   and the absence of the parameter is asserted against the committed schema.

10. **No write path is opened.** `tests/unit/companion/test_import_boundary.py` passes unchanged with
    **no exclusions added**. Explicitly absent from the `src/companion` diff: every deck/card
    mutation method, `session.add`, `session.commit`, `session.delete`, `init_database`,
    `create_all`, `src.data.importers` (AD-2, NFR-02).

11. **The route is not shadowed by the SPA mount**, proved by asserting **status and body** — not
    merely content-type (c3-1 review R1: the content-type-only version passed with the router
    deleted, because `/api` is reserved and answers JSON `invalid_request` either way).
    `test_spa.py::TestMountOrdering` and the reserved-prefix tests stay green, and landmine 7's
    claim — that the differential router list at `test_spa.py:305-307` needs **no** new line when the
    route joins `decks.router` — is **measured** (run the test, paste it), not asserted. If Q1 puts
    the route in a new module, the line is added.

### The projection, and the two gaps

12. **The row projection has exactly one implementation and it lives where Q1 rules** (AD-1). No
    second copy in `src/companion`, none in TypeScript. If Q1 places it in `src/logic`, a test proves
    the MCP side is unaffected — the existing `validate_deck` tool suite passes with **zero test-file
    edits**, which is how c3-1 proved its own projection move was behaviour-preserving.

13. **Q2's banned ruling is implemented where it belongs and probed with a synthetic fixture.** Zero
    of the 40 real decks contain a banned or restricted card (landmine 15), so the fixture must be
    constructed: a card whose `legalities` says `banned` in the deck's format, alongside a card that
    is plainly `not_legal`, alongside a `legal` card — three distinguishable cards in one deck, so
    a test cannot pass by treating them alike. Paired for non-vacuity: the legal card produces
    **no** violation row.

14. **Q3's rotation ruling is implemented and the underlying absence is recorded as a measurement,
    not an assumption.** The record states, with the output pasted, that `cards` has 23 columns and
    none carries a release date; that there is no sets table; and that `released_at` is read by
    `aggregate.py` and discarded. `deferred-work.md` gains an entry naming what adding rotation
    would actually cost (a `cards` column or a sets table, an importer change, a hand-written
    migration, a full re-import, **plus** a rotation-schedule source Scryfall's bulk data does not
    directly provide) with a named home.

15. **If Q2's ruling extends `DeckViolation.rule`, every ripple site is worked in the same commit**
    — the `Literal`, `DeckViolation`'s `Attributes:` docstring (which enumerates which rules are
    card-specific), `validate_deck`'s own docstring bullet list, `src/mcp_server/tools/
    deck_analysis.py`'s tool docstring (it enumerates the rules for the agent), and every test in
    `tests/unit/logic/test_deck_validator.py` and `tests/integration/` that asserts
    `v.rule == "format_legality"` (grep measured: `test_deck_validator.py:626-633`,
    `test_deck_analysis_tool.py:339,345,402,425`, `test_mcp_tools.py:355,363`). A red there is
    **expected** and must be updated deliberately with its comment restated — never silenced.
    Worked as one list, in one commit, in the c3-2 seven-row style.

### The wire contract

16. **`npm run gen:api` is run and both generated files are committed together** — neither
    hand-edited, neither prettier-formatted (both stay in `.prettierignore`). Measured before →
    after: **4 paths → 5**, **7 component schemas → N** with N stated and every added name listed
    and justified (nothing removed). Both drift gates green from the same commit, output pasted:
    `uv run pytest tests/unit/companion/test_openapi_contract.py` and, from `ui/`,
    `npm run gen:types && git status --porcelain` (no output).

17. **No Python-internal or MCP-internal prose crosses the wire, scanned by FAMILY not by member.**
    After regeneration, `types.d.ts` is scanned with c3-2's `PYTHON_INTERNAL_FAMILIES` plus the
    literal markers (`>>> `, `model_validate`, `SQLAlchemy`, `pydantic`, `src/mcp_server`,
    `validate_deck` **as an MCP tool name**, `ValidateDeckResult`). Every hit is fixed **at the
    Python docstring** — rewriting the leading summary for a TypeScript reader and pushing Python or
    MCP detail below a truncating header — never by editing the generated file. Any docstring edited
    in `src/logic` must keep the MCP tool's meaning intact (landmine 18).

18. **`ui/tests/wire-contract.test.ts` picks up the new component names with no edit to its ban
    mechanism**, and the pickup is proven non-vacuously by a **staged** planted declaration of one
    of the new type names in a scratch `ui/src` file — red, then reverted. Probe output and revert
    both pasted. `toContain` anchors may be added beside the existing ones (c3-1 review R7).

19. **The generated report type's shape is inspected and recorded** — which fields are nullable,
    which optional, and what the row status union generates as. It is what c4-10 will code against,
    and c3-1's ledgered `?`-vs-`| null` asymmetry (`strategy?: string | null` vs
    `format: string | null`) is a known trap: record whether it repeats here.

20. **No frontend behaviour ships.** `ui/src/App.tsx`, every component, `ui/src/api/schema.ts`,
    `states.ts` and `copy.ts` are unchanged in behaviour. **c4-10 owns the format check panel**;
    c4-1 owns the fetch/store. Permitted `ui/` changes: the two generated files, the AC 18 anchors,
    `ui/README.md`, and nothing else. Any deviation is recorded as a deviation at the time it is
    made (c3-2's review round-2 lesson — two comment-only edits shipped outside the permitted list
    with no entry).

### Boundaries, comments and records

21. **The plugin mirror is rebuilt and committed** (`uv run python -m scripts.build_plugin`), and
    the SPA bundle is **re-measured, not assumed**: `src/companion/app/static/` and
    `plugin/server/src/companion/app/static/` are expected byte-identical (this story ships no
    runtime frontend code). If either changed, that is a finding to explain, not a rebuild to wave
    through.

22. **The forward-dated-comment inventory is repaired** (standing agreement). Each row either
    becomes true, is re-homed, or is recorded with a judgement. At minimum:

    | # | Location | What it says | Action |
    | --- | --- | --- | --- |
    | 1 | `scripts/dump_openapi.py:23-24` | "…taking it to **seven** and the paths to four. Story **c3-3**'s format check is next" | **Becomes true** — done; both counts restated; name c3-4 |
    | 2 | `src/companion/app/errors.py:130-132` | names c3-1 and c3-2 as `error_responses` callers, "c5-5 follows" | **Update** — c3-3 reuses `deck_not_found` on a third route |
    | 3 | `src/companion/app/main.py`'s ordering comment | "c3-1's decks router and c3-2's cards router are registered above this line" | **Verify** — either it still reads true unchanged (Q1's `decks.router` answer) or it gains a line |
    | 4 | `tests/unit/companion/test_spa.py:300-307` | the differential list's "a story that adds a router and forgets this line gets a red test" | **Measure + record** — landmine 7: a route on an existing router costs no line. Say so in the comment so the next story is not misled |
    | 5 | `src/logic/deck_validator.py:158-165, 281-285` | the D-1.6b Phase-1 scope note (60 cards regardless of format) | **Restate** — this story publishes that limitation to a human for the first time (landmine 13) |
    | 6 | `deferred-work.md`'s three c3-3-homed entries | `_is_ref_rooted`; the `format: string \| null` question; the README anchors | **Resolve or re-home by name** per Q4 and Q5 — none may be silently dropped |

23. **`deferred-work.md` gains this story's residue with named homes**, at minimum: rotation data
    absence (AC 14); the `restricted`-is-not-illegal edge (landmine 11); the Commander/Brawl
    100-card size limitation now visible to a user (landmine 13); whatever Q5 declines; and anything
    the review turns up. No residue in prose only.

### Testing

24. **Tests live at `tests/unit/companion/test_routes_format_check.py`** and drive the real
    `build_app()` through `lifespan_client` against a real temporary SQLite file. Coverage: a legal
    deck (every row passes); a deck with each violation family present and distinguishable; the
    unknown/blank-format path (AC 7); Q2's banned fixture (AC 13); Q3's rotation ruling; an unknown
    deck id → 404 token asserted on status and body; both 503 paths; the not-shadowed-by-SPA check
    asserting status and body; the non-zero-counts pin (AC 4); row order (AC 2); and the committed
    schema's new path and component names.

25. **Non-vacuity pairing on every guard-shaped assertion** (standing agreement): each proves it
    **fires** and proves it **stays silent** from the same invocation. Concretely — the all-pass deck
    is paired with a deck that violates, so "every row is pass" cannot pass by producing no rows; the
    banned fixture is paired with a legal card in the same deck; the row-order assertion is paired
    with a check that the row set is non-empty and complete; and the "no rule in the shell" gate (AC
    5) proves it can fire by being run against a planted violation.

26. **At least four mutation probes are run, verified on disk before the verdict and reverted after**
    (standing agreement — *probe your own guard before review does*): (a) the route silently
    unregistered / renamed; (b) `get_deck_with_cards` swapped for `get_deck`, which must produce the
    silent-zero report AC 4 exists to catch; (c) the projection's pass/violation status inverted for
    one check; (d) AC 18's planted type name. Paste each result, and **read the output before filing
    it** — c3-1's review found three vacuous tests hiding inside a "19 failed" probe result.

27. **Every gate is re-run and its output pasted**: `uv run pytest`, `uv run ruff check .`,
    `uv run ruff format --check .`, `uv run mypy src/`, `uv run mypy src/ --platform win32`, plus the
    frontend gates from `ui/` (`lint`, `format:check`, **`npx tsc -b --force`**, `test`, `build`) and
    both drift checks. Suite counts stated as *before → after*, measured at Task 0 and again at the
    end. Baseline to beat, **to be re-measured not inherited**: approximately **Python 1893 passed /
    1 skipped** full (**1848 passed / 1 skipped / 45 deselected** under `-m "not integration"`) ·
    **frontend 558 passed (29 files)**.

---

## Tasks / Subtasks

- [x] **Task 0 — Baseline, measured not assumed** (standing agreement)
  - [x] `git fetch origin feat/companion-c3`; confirm the umbrella tip is `2a787ac`; cut
        `feat/companion-c3-3-format-check-endpoint` from it
  - [x] Run and record: `uv run pytest` (count + duration), `ruff check`, `ruff format --check`,
        `mypy src/`, `mypy src/ --platform win32`
  - [x] From `ui/`: `npm run lint`, `format:check`, **`npx tsc -b --force`**, `npm test` (count),
        `npm run build`
  - [x] Record the pre-change SHA-256 of `src/companion/app/static/assets/*` and the `plugin/`
        mirror (AC 21)
  - [x] Record the committed `paths` and `components.schemas` keys (expect 4 and 7 — landmine 19)
  - [x] Re-verify landmines 12, 14, 15, 16 against the live database (the column list, the 40-deck
        validation run, the zero banned/restricted count, the `NOT NULL` DDL)

- [x] **Task 1 — The projection** (AC 2, 3, 12, 15; Q1, Q2, Q3)
  - [x] Place the row model + projection where Q1 rules; closed three-member status `Literal`
  - [x] Apply Q2's banned ruling, working every ripple site from AC 15 as one list
  - [x] Apply Q3's rotation ruling
  - [x] Declare and pin the row order (AC 2)
  - [x] Prove the MCP side is behaviour-preserving: run the `validate_deck` tool suites and record
        whether any test file needed an edit and why

- [x] **Task 2 — The route** (AC 1, 4, 5, 6, 7, 8, 9, 10, 11)
  - [x] Add the handler per Q1's module sub-decision; `response_model=` the report;
        `responses=error_responses("deck_not_found")`
  - [x] `get_deck_with_cards` → `None` → `raise CompanionError("deck_not_found")`; otherwise call
        the validator and project
  - [x] Google-style docstring; the **leading paragraph is what crosses the wire** (landmine 18)
  - [x] Confirm `build_app()` and `test_spa.py:305-307` need no edit — **measured** (AC 11) — or add
        the line if Q1 says a new module

- [x] **Task 3 — Regenerate the wire types** (AC 16, 17, 18, 19)
  - [x] From `ui/`: `npm run gen:api`; diff both files; confirm 5 paths and the new schema count
  - [x] Run the family scan over `types.d.ts`; fix at the Python docstring and regenerate on any hit
  - [x] Record the generated report shape's nullability/optionality (AC 19)
  - [x] Probe the wire-contract guard: **stage** a planted type name in a scratch `ui/src` file,
        `npm test` → red, revert → green; paste both

- [x] **Task 4 — Tests and probes** (AC 13, 24, 25, 26)
  - [x] `tests/unit/companion/test_routes_format_check.py` with the full coverage list
  - [x] Q2's synthetic banned/not-legal/legal three-card fixture
  - [x] Re-run `test_import_boundary.py` and `test_spa.py` explicitly
  - [x] Four mutation probes (AC 26), each verified on disk and reverted

- [x] **Task 5 — The two homed items** (AC 22 row 6; Q5)
  - [x] Apply Q5's ruling on `_is_ref_rooted` and on `ui/README.md`'s anchoring
  - [x] Re-home to `deferred-work.md` whatever Q5 declines

- [x] **Task 6 — Comments, docs, records** (AC 14, 20, 21, 22, 23)
  - [x] Work the six-row forward-dated-comment table
  - [x] Rebuild + commit the plugin mirror; re-measure the bundle against Task 0
  - [x] `deferred-work.md` entries with named homes; add any new `ui/README.md` blind-spot row
  - [x] Fill the Dev Agent Record; update `sprint-status.yaml`

- [x] **Task 7 — Same-day three-layer review before the PR** (C2 retro action item 6, standing)
  - [x] `bmad-code-review` (Blind Hunter + Edge Case Hunter + Acceptance Auditor) before raising the PR
  - [x] Apply patches, then re-run every gate and paste the output
  - [ ] Raise the PR into `feat/companion-c3`

---

## Dev Notes

### Decide-once rulings this story inherits (do not re-derive)

| Ruling | Source | What it means here |
| --- | --- | --- |
| REST is HTTP-native; success bodies are Pydantic schemas **unwrapped** | AD-16 | `response_model=<the report>`; no envelope, no wrapper key |
| The backend consumes existing repositories and logic, and defines no second truth | AD-1, the epic AC | Call `validate_deck`; reimplement no rule in the shell or in TS |
| A projection shared by two shells lives **down** in the core, not in one shell | c3-1 Q1 (Brad, 2026-07-31) | The precedent Q1 must answer to |
| The status is derived from the token, never chosen at the call site | `errors.py` module docstring | `raise CompanionError(...)`; never `JSONResponse`, never `status_code=` |
| The engine is lazy and its absence is a served UI state | AD-10, c1-6 | Annotate `DbSession`; do not probe readiness |
| `DatabaseError → 503 database_unavailable` is registered app-wide | c1-6, C1 retro | No `try/except` in a route body |
| A route declares only the tokens it uniquely produces | c3-1 AC 6 | `error_responses("deck_not_found")`, nothing else |
| One generator, from the backend's own `app.openapi()` | AD-12 | `npm run gen:api`; no second codegen, no hand-written TS shape |
| `install_spa(app)` stays last in `build_app()` | c2-2 | Register above it — or reuse a router already above it |
| Ban the family, never enumerate members | C2 retro, standing | AC 17's scan and AC 5's rule-shape gate are both family-keyed |
| Probe your own guard before review does | C2 retro, standing | AC 26's four probes are not optional |
| Claims require verification | standing | Paste real gate output; measure the bundle, do not assume it |
| Copy lives in `EXPERIENCE.md` and is gated | c2-9 | **Exception, and it is the epic's:** the AC mandates a server-authored `detail` string per row, exactly as `DeckViolation.detail` already is. Note it; do not invent a copy gate for it |

### The five things this story must not break

1. **`tests/unit/companion/test_import_boundary.py`** — both guards, AST-only, sees modules no test
   imports. Its docstring forbids routing around it by convention: *"a guard satisfied by
   obfuscation is theatre"* — no `getattr`, no dynamic import.
2. **The `validate_deck` MCP tool and its suites** — `tests/unit/logic/test_deck_validator.py`,
   `tests/integration/mcp_server/test_deck_analysis_tool.py`, `tests/integration/test_mcp_tools.py`.
   If Q2 extends the rule vocabulary, reds there are **expected**; update them deliberately with
   their comments restated. A red you silence without restating the comment is how the next story
   inherits a lie (c3-2's lesson).
3. **`test_spa.py`** — `TestMountOrdering`, the reserved-prefix pins, and the differential router
   list at `:305-307` (landmine 7 — measure whether it needs a line, do not guess).
4. **`test_openapi_contract.py`'s byte comparison** — including LF line endings and
   `ensure_ascii=False`, plus c3-2's `PYTHON_INTERNAL_FAMILIES`. Never hand-edit `openapi.json`;
   always regenerate.
5. **`test_routes_decks.py::TestCommittedSchema::test_the_component_names_are_exactly_these`
   (`:695`)** — the pin c3-2 discovered the hard way (its Debug Log 3: *"a third structural pin was
   supposed to go red and the story named only two"*). It asserts the component set is **exactly**
   the current seven. Adding any schema reddens it. This story names it in advance; there is no
   excuse for finding it during a probe.

### Source tree — what exists, what this story adds

```
src/logic/
  deck_validator.py       EDIT — Q1's row projection and/or Q2's rule split (both, if ruled so)
src/companion/app/
  routes/
    decks.py              EDIT — the format-check handler (Q1 sub-decision), or:
    format_check.py       NEW  — only if Q1 rules a separate module (then main.py + test_spa.py too)
  main.py                 LIKELY UNCHANGED — decks.router is already included above install_spa
  errors.py               EDIT (docstring only) — a third error_responses caller
src/mcp_server/tools/
  deck_analysis.py        EDIT (docstring only) — only if Q2 extends the rule vocabulary
scripts/dump_openapi.py   EDIT (docstring only) — c3-3 shipped; counts; c3-4 next
tests/unit/companion/
  test_routes_format_check.py   NEW
  test_routes_decks.py    EDIT — the component-name pin (:695)
  test_errors.py          EDIT — only if Q5 takes the _is_ref_rooted repair
  test_spa.py             VERIFY — landmine 7; edit only if a new module ships
tests/unit/logic/
  test_deck_validator.py  EDIT — only if Q2 extends the rule vocabulary
tests/integration/        EDIT — same condition (three named assertion sites, AC 15)
ui/src/api/
  openapi.json            REGENERATED (committed)   4 paths -> 5
  types.d.ts              REGENERATED (committed)   7 schemas -> N
ui/tests/
  wire-contract.test.ts   EDIT — the new toContain anchors (AC 18)
ui/README.md              EDIT — Q5's anchoring; any new blind-spot row
plugin/**                 REBUILT — required by CI's drift gate (landmine 19)
```

**Not touched, deliberately:** `ui/src/App.tsx`, every `ui/src/components/**`, `ui/src/api/schema.ts`
(c4-1 owns the aliases), `src/companion/contracts.py` (**no new reason token** — `deck_not_found`
already ships), `src/companion/app/security.py`, `src/companion/client.py`,
`src/companion/discovery.py`, `src/data/models/**`, `src/data/repositories/**`,
`src/data/schemas/**`.

### Previous story intelligence (c3-1 and c3-2, and their four review passes)

- **Twelve of twelve stories have answered their open questions "as proposed."** The questions below
  are written to be answerable the same way, but **Q2 and Q3 are genuine forks** — they change what
  ships, not just where it lives.
- **The round-1 5/5 Greptile cause is five-times confirmed:** the same-day three-layer
  `bmad-code-review` before raising the PR. Standing action item. Task 7.
- **c3-2's headline review finding was a true count read as a false rule**, published to the wire:
  "cards carrying both top-level and per-face `image_uris`: 0" (true) generalised into "a
  single-faced card carries a null `card_faces`" (false for 368 printings), and the false version
  went into `types.d.ts` and `/docs`. **Applied here:** this story's docstrings will state legality
  rules to a UI author. Every general claim in one must be re-derived from the measurement, not
  from a neighbouring measurement — especially anything about *banned vs not-legal vs restricted*,
  where the three-value split is exactly the kind of thing a summary flattens.
- **c3-2's second finding: a guard that could not fail for its stated reason.** Several of its
  regexes matched inside the very comments describing them. Any gate this story adds (AC 5's
  rule-shape check especially) must be run against a planted violation before it is trusted.
- **c3-1's R1 finding is this story's most likely repeat.** `TestNotShadowedBySpa` passed with the
  router *deleted*, because `/api` is reserved and answers JSON either way. AC 11 asserts status
  **and** body for exactly that reason.
- **c3-1's R3 finding is the second most likely.** Nothing tied a nested card to its entry because
  every seeded card was identical on the asserted fields. **Every fixture card here must be
  distinguishable from every other** — AC 13's three-card fixture is written for that.
- **c3-1's finding 1: `plugin/**` is not "not touched".** A stale mirror is a guaranteed red build.
- **c3-1's R14 / c3-2's `Warning:` ruling: a fix can put internal detail on the wire.** `Note:` and
  `Warning:` are the two Google headers `main.py` deliberately does **not** truncate — so a `Note:`
  is a wire-visible paragraph. Use a code comment for anything a UI author should not read, and use
  a `Warning:` deliberately when they must (c3-2's 503-retry-trap precedent).
- **c3-2 shipped two comment-only edits outside its permitted-file list with no deviation entry**,
  caught at review round 2. Record deviations **when you make them**, not when a reviewer finds them.

### Git intelligence

- `2a787ac` — PR #30 merged c3-2 into `feat/companion-c3` (the local `feat/companion-c3` was stale at
  `b0fd39b` when this story was written; fetch before cutting). `02b2c45` — the C2 ship record;
  `a52d6f8` — integration PR #28 on master.
- The C2/C3 rhythm holds: **story branch off the umbrella, story PR into the umbrella with a
  Greptile pass per story**, one integration PR to master after the retro with **no** Greptile pass
  (OSS free-tier budget, standing rule). Merge ≠ release — no tag, no CHANGELOG until c8-4.
- Commit style: Conventional Commits, `feat(companion): …`.
- c3-1's and c3-2's shape is the model to copy: one small `feat` commit, then a separate
  review-patch commit, then the records commit.

### Gotchas specific to this story

- **`format` is a field name, not a builtin misuse** — the project deliberately shadows it for MTG
  clarity (project-context.md). Ruff `N` is on; keep it. It appears as a field on the report, a
  parameter on the validator and a column on `decks`.
- **`validate_deck` lowercases and strips `format` itself** (`deck_validator.py:300-302`) — the
  route must not do it again, and the report's `format` field is the **normalised** value, which may
  differ from `deck.format` as stored. Decide which one the wire carries and say so.
- **`deck_validator.py:347` skips entries where `dc.card is None`** — dead at the schema level
  (`DeckCard.card: Card` is required, not optional), so it cannot mask a missing card from a
  validated `Deck`. Do not read it as a tolerance you can rely on.
- **Async everywhere in `src/data`.** The route handler is `async def` (FastAPI); `validate_deck` is
  **sync and pure** — call it directly, do not `await` it, do not wrap it in a threadpool.
- **`mypy --strict` and `--platform win32`** are both gates. Every function in `src/` needs full
  hints, including the projection.
- **A deck id has no declared shape** (c3-1's ruling), so there is **no** `Path(pattern=...)` here
  and **no** 400 for a malformed deck id — an unknown id is simply `deck_not_found`. Do not import
  c3-2's card-id pattern by analogy.
- **`%2F` in a path segment is decoded by Starlette before matching**, so a deck id containing an
  encoded `/` is a routing-level `invalid_request`, never a handler answer (c3-1 review R12).
  Trailing slashes `307`-redirect. Pin the spellings you claim.
- **Versions installed on this machine, measured at c3-2:** FastAPI **0.140.0**, Starlette
  **0.48.0**, Pydantic **2.12.0**. This story needs **no new dependency**; adding none is part of it.

### Testing standards

- `pytest` config is in `pyproject.toml`; `asyncio_mode = "auto"` — write `async def test_…` with
  **no** `@pytest.mark.asyncio`.
- Layout mirrors `src/`: `tests/unit/companion/` for anything driven in-process over
  `httpx.ASGITransport`; `tests/unit/logic/` for anything Q1 puts in `src/logic`. This story adds
  **no** `integration`-marked test — AD-10 rules that exactly one such test exists in the whole
  feature and it belongs to **c5-8**.
- Reuse `lifespan_client` and `keep_spa_mount_last` from `tests/unit/companion/conftest.py`. Do not
  write a second seam.
- `tests.*` is exempt from `mypy --strict` but not from ruff or the naming rules.
- Paste real gate output. **`npx tsc -b --force` is a separate claim from `npm test`** — c3-2
  measured `tsc -b` caching a clean result over a real failure.

### Architecture rules this story implements

- **UX-DR21** — one row per local validation check, tone-mapped pass → positive, advisory → caution,
  violation → negative; display-only. `EXPERIENCE.md:37` and `:96` are the contract.
- **AD-1** — sibling shells over one core; the existing `src/logic` validators; no second truth in
  the shell or in TypeScript.
- **AD-2 / NFR-02** — read-only, enforced by the CI import boundary.
- **AD-10** — lazy engine, absence is a served state; in-process testing over `ASGITransport`.
- **AD-12 / NFR-03** — one generator from the backend's own `app.openapi()`; committed,
  drift-checked.
- **AD-16** — HTTP-native REST, unwrapped bodies, closed reason tokens (**unchanged at seven**),
  one typed error body.
- **No FR backs this endpoint, and that is recorded rather than assumed.** Measured: the PRD
  (2026-07-22, incl. the addendum) mentions legality and format-checking **nowhere**. The endpoint
  exists solely because `EXPERIENCE.md` made the panel P0 — the epic says so at its own
  "Endpoints added beyond the spine's route list" section: *"the format check panel is P0 in
  EXPERIENCE.md but had no data source. Reuses the existing `src/logic` validators; a TypeScript
  reimplementation would be the second truth AD-1 exists to prevent."* So **UX-DR21 is the
  requirement**, and where UX-DR21 and the validator disagree, that is a decision for Brad (Q2, Q3),
  not a defect to route around.

### References

- [epics-companion-app.md § Story 3.3](../planning-artifacts/epics-companion-app.md) — the ACs this
  story expands (lines 1608-1636); the C3 epic framing (1541-1546); the endpoint's own justification
  (272-274); **Story 4.10, the panel that consumes this** (2189-2216)
- [EXPERIENCE.md:37,96](../planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md) —
  the six checks and the three-tone map, quoted verbatim in landmine 10
- [DESIGN.md:388](../planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/DESIGN.md) —
  the legality row's visual spec (label + right-aligned `Badge` over a hairline rule); `:341` the
  right column
- [ARCHITECTURE-SPINE.md](../planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md) —
  AD-1, AD-2, AD-10, AD-12, AD-16
- [c3-2 story record](c3-2-card-detail-endpoint.md) — the wire-prose gate, the `Warning:` ruling, the
  five probes, and the four findings that were corrections to its own assumptions
- [c3-1 story record](c3-1-deck-list-and-deck-detail-endpoints.md) — the projection-moves-down
  ruling, the silent-zero-counts landmine, and review findings R1/R3/R7/R12
- [deferred-work.md](deferred-work.md) — the **three** entries homed on c3-3 by name (`_is_ref_rooted`;
  `format: string | null` vs the `NOT NULL` column; the `ui/README.md` anchors) and `test_spa.py`'s
  router-list tax
- [epic-c2-retro-2026-07-30.md](epic-c2-retro-2026-07-30.md) — the standing agreements (ban the
  family; probe your own guard) and action item 6 (same-day three-layer review)
- [project-context.md](../project-context.md) — layer boundaries, async rules, docstring style,
  ruff/mypy gates

---

## Open questions for Brad — answer before `dev-story`

**Q1 — Where does the row projection live, and which module holds the route?**

The validator reports violations; UX-DR21 wants a row per check including the ones that passed.
Something must turn one into the other.

| Option | Verdict |
| --- | --- |
| **`src/logic/deck_validator.py`** — a `format_check(deck, *, format) -> FormatCheckReport` (or a `to_rows(report)`) beside the validator it projects | **Proposed.** It is where the rules and `DeckValidationReport` already live; it keeps `src/companion` free of anything rule-shaped, which is what AC 5 has to prove; and it matches c3-1's Q1 ruling that a projection moves *down* so both shells share one implementation |
| `src/companion/contracts.py` — a companion-only wire model | **Not proposed.** The honest counter *for* it: no MCP consumer wants rows today, so `src/logic` gains a function only the companion calls. But `contracts.py` is a **leaf** (AD-3) that may not import `src.logic`, so the projection would have to be hand-fed — and the row vocabulary would then live one import away from the rules it summarises |
| `src/data/schemas/` | **Rejected.** It is logic output, not a persistence shape |

Two notes on the proposed answer. **`pass`/`advisory`/`violation` is domain vocabulary, not UI
vocabulary** — the *tone map* (positive/caution/negative) is the UI half and stays in TypeScript at
c4-10 — so putting the status enum in `src/logic` does not leak presentation into the framework-free
core. And **the `detail` string** is already `src/logic`'s job: `DeckViolation.detail` is
server-authored prose today and the epic AC asks for exactly that.

*Sub-decision — the route module.* Proposed: **add the handler to `src/companion/app/routes/decks.py`**
and reuse `decks.router`. `/api/deck/{deck_id}/format-check` is a deck sub-resource; `decks.py`'s
docstring is written about deck reads and this is one; and the payoff is concrete — `build_app()`
needs no edit and `test_spa.py:305-307`'s hand-synchronised router list needs no line (landmine 7,
to be *measured*). The alternative, a `routes/format_check.py`, buys separation this route does not
need and costs two hand-synchronised edits. *Recommendation: as proposed, both parts.*

---

**Q2 — Does `src/logic` learn to distinguish `banned` from "not in this format"?** *(genuine fork)*

UX-DR21 names **banned** as its own check. Today both come out as one `format_legality` violation
(`deck_validator.py:384`: `card.legalities.get(format) != "legal"`). Measured: the corpus carries
1,275 `banned` entries (10 in Standard) and 89 `restricted`, so the data supports the split — but
**zero** of the 40 real decks contain either, so no verdict on any real deck changes.

| Option | Verdict |
| --- | --- |
| **Extend `DeckViolation.rule` with a `banned_card` member in `src/logic`**, and split the branch: `banned` → `banned_card`, anything else non-legal → `format_legality` | **Proposed.** It is the only place the split can live without breaking AC 5. The agent-facing `validate_deck` tool gets more precise at the same time, which is a benefit, not a side effect |
| Derive the banned row in the endpoint by re-reading `card.legalities[format]` | **Rejected.** That is a deck-construction rule in the shell — banned by this story's own AC in the same sentence that bans a TypeScript version |
| Ship no banned row; fold "banned" into the legality row and record it | **Fallback.** Cheapest, and defensible since the legality row *does* catch banned cards. But UX-DR21 lists six checks and this drops one, so the panel silently under-delivers against a P0 spec |

**The cost, stated honestly.** Option 1 is a closed-set extension in the *shared core*, so it ripples
the way c3-2's token did: the `Literal`, two docstrings in `deck_validator.py`, the MCP tool's
docstring, and **six named assertion sites** across three test files (AC 15 lists them). It is a
bigger diff than the route. It also does not touch the wire's `ErrorReason` set — this is a
different closed set, with no AD-16 pairing rule attached.

**`restricted` is deliberately out of scope either way.** A restricted card is *legal* with a 1-copy
limit in Vintage, and today it is reported as illegal — wrong, but latent (0 vintage decks, 0
restricted cards in the deck table). Fixing it properly means a copy-limit rule that varies per
card, which is its own story. Proposed: **ledger it, do not fix it**, and do not let the banned split
quietly change its behaviour. *Recommendation: option 1, with `restricted` ledgered.*

---

**Q3 — Rotation exposure, which has no data source at all.** *(genuine fork)*

Measured: `cards` has 23 columns and none is a release date; there is no sets table; `released_at` is
read by the importer and discarded. Rotation is **not computable locally**, full stop.

| Option | Verdict |
| --- | --- |
| **Ship the row, status `advisory`**, with a detail saying rotation cannot be determined from the local card data | **Proposed.** It satisfies the epic AC as literally written ("one row per check covering … rotation exposure"), it makes the gap **visible instead of silent**, and "advisory" is precisely the tone for *I cannot tell you this* |
| Ship no rotation row; record the absence as a measurement and ledger the cost (c3-2's prices precedent) | **The real alternative.** Cheaper and cleaner, and it avoids a row the user can never resolve. But c3-2's prices AC said "absent or null rather than zero"; this AC says the response must **cover** rotation, which is a stronger claim to satisfy by omission |

**What it would actually take to answer rotation properly**, so the ledger entry is accurate rather
than hand-waved: a `released_at` (or set-type) column on `cards` *or* a new sets table; an importer
change; a hand-written `scripts/migrate_*.py` (no Alembic); a full re-import of ~38k cards; **and** a
rotation-schedule source — Scryfall's bulk data does not directly say "this set rotates in
2027-09". That is comfortably its own story, and it is not this one.

**Note this either way:** `advisory` still has a population without rotation, via Q4's
"no format to check against" answer — so the tone map's third branch is reachable for c4-10 under
both options. Do not choose option 1 *in order to* populate `advisory`.

*Recommendation: option 1 — ship the advisory row — but this is the question most worth overruling
me on, and option 2 is a perfectly good answer if you would rather the panel show five honest rows
than six with one permanent shrug.*

---

**Q4 — What triggers "no format to check against", and does the response shape change?**

The deferred entry homed here asks it precisely: is it keyed on a **null format** (then `decks.format
NOT NULL` is the bug) or on an **unrecognised format string** (then the wire type is merely wider
than the data)? Measured: the column is `NOT NULL`, zero of 40 rows are null or blank,
`create_deck(format: str)` requires it, and `Deck.format` is nonetheless typed `str | None` and
crosses the wire as `string | null`.

Proposed, three parts:

1. **Key it on the validator's existing `unknown_format` outcome** — an unrecognised *or empty*
   format string, which `deck_validator.py:307-321` already handles carefully and already refuses to
   let flag every card illegal. No schema change, no migration, no new mechanism.
2. **Resolve the deferred entry as "the wire type is wider than the data; leave it"**, and record
   that a UI `format === null` branch written against the generated type is dead code today —
   re-homed to **c4-10**, which will write exactly that branch.
3. **One response shape, always.** No `response_model=X | None`, no union: the report is the same
   object whether the format is checkable or not, with the legality/banned rows carrying the status
   Q3's and Q2's rulings imply. This is deliberate on two counts — c4-10 renders one shape, and
   `test_errors.py::_is_ref_rooted` (which refuses a top-level `anyOf`) never fires.

*Recommendation: as proposed.*

---

**Q5 — Does c3-3 take the two housekeeping items homed on it by name?**

`deferred-work.md` homes two here. Proposed: **take both**, following c3-2's Q5 precedent (a story
takes the convention decisions filed against it rather than passing them on with the subject already
shipped).

- **`_is_ref_rooted`'s union blindness.** Q4's proposal means no union ships, so this is a choice.
  Take it anyway: the fix shape is already written down in the entry (admit a union whose every
  branch is itself ref-rooted or `{"type": "null"}`; add `prefixItems` to the object-shape keys;
  admit a `$ref` carrying legal sibling annotation keys), it is a handful of lines with a
  firing/silent pair each, and leaving it means the next story inherits **a red test with a
  misleading message** rather than a clean failure.
- **`ui/README.md`'s line-number-anchored blind-spot map.** Re-anchor the citations on marker
  strings (the guard function name, or the declared-limit sentence) rather than line numbers, and
  add a test that every cited anchor still resolves. This story owes the README a review pass and a
  new row anyway, so it is the cheapest moment it will ever have.

The alternative is deferring both a third time. *Recommendation: as proposed, take both.*

---

## Dev Agent Record

### Agent Model Used

Claude Opus 5 (`claude-opus-5[1m]`) via Claude Code / `bmad-dev-story`.

### Open questions — Brad's answers

Answered 2026-07-31, before any implementation. **Thirteen of thirteen stories have now answered
"as proposed"** — with one partial: Q5 took one of its two items.

| Q | Ruling |
| --- | --- |
| **Q1** | **As proposed, both parts.** The row projection lives in `src/logic/deck_validator.py` beside the validator it projects (c3-1's "a projection moves *down* into the shared core" precedent); the route handler joins `src/companion/app/routes/decks.py` and reuses `decks.router`, so `build_app()` needs no edit and `test_spa.py:305-307` needs no line — **to be measured, not assumed** (AC 11, landmine 7) |
| **Q2** | **As proposed — option 1.** `DeckViolation.rule` gains a `banned_card` member in `src/logic`; the branch splits `banned` → `banned_card`, anything else non-`legal` → `format_legality`. Every ripple site in AC 15 worked as one list in one commit. **`restricted` is ledgered, not fixed** — and the banned split must not quietly change its behaviour |
| **Q3** | **As proposed — option 1, ship the row as `advisory`.** A sixth row whose detail says rotation cannot be determined from the local card data. Chosen over the (explicitly offered) five-honest-rows alternative: the epic AC says the response must *cover* rotation, and an advisory row makes the gap visible instead of silent. AC 14's measurement and the ledger entry are still owed in full |
| **Q4** | **As proposed, all three parts.** Keyed on the validator's existing `unknown_format` outcome (unrecognised *or* empty format string) — no schema change, no migration; the deferred `format: string \| null` entry resolves as "the wire type is wider than the data, leave it", re-homed to **c4-10**; and **one response shape always** — no union, no `X \| None` response model |
| **Q5** | **Partial — take the `_is_ref_rooted` union fix, decline the `ui/README.md` re-anchoring.** The guard repair ships here (admit a union whose every branch is ref-rooted or `{"type": "null"}`; add `prefixItems` to the object-shape keys; admit a `$ref` carrying legal sibling annotation keys — each with a firing/silent pair). The README's line-number-anchored blind-spot map is **re-homed to `deferred-work.md`** with a named home; this story still adds its new blind-spot row, keyed the existing way |

### Baseline (Task 0, measured — not assumed)

Branch `feat/companion-c3-3-format-check-endpoint` cut from **`2a787ac`**. The story's prediction
held: the local `feat/companion-c3` was stale at `b0fd39b`, `origin/feat/companion-c3` was
`2a787ac`; both are now at `2a787ac`.

**Gates, all green at the baseline:**

| Gate | Result |
| --- | --- |
| `uv run pytest` | **1893 passed, 1 skipped** in 111.01s |
| `uv run pytest -m "not integration"` | **1848 passed, 1 skipped, 45 deselected** in 64.95s |
| `uv run ruff check .` | `All checks passed!` |
| `uv run ruff format --check .` | `292 files already formatted` |
| `uv run mypy src/` | `Success: no issues found in 86 source files` |
| `uv run mypy src/ --platform win32` | `Success: no issues found in 86 source files` |
| `ui/ npm run lint` | clean (eslint + stylelint) |
| `ui/ npm run format:check` | `All matched files use Prettier code style!` |
| `ui/ npx tsc -b --force` | exit 0, no output |
| `ui/ npm test` | **29 files / 558 tests passed** |
| `ui/ npm run build` | built in 134ms |

Every figure matches the story's "baseline to beat" exactly.

**SPA bundle, SHA-256 (first 16), both sides — byte-identical at the baseline:**

```
0640890476FC1198  assets/space-grotesk-latin-wght-normal-BhU9QXUp.woff2
0A3C142D84B5A98D  assets/index-DmxBiI94.css
8E65C0615CF66044  index.html
9BE16EA2FE3670DE  favicon.svg
FAEEEA472ADD5078  assets/index-DE70muY2.js
```
(identical set under `src/companion/app/static/` and `plugin/server/src/companion/app/static/`)

**Committed schema:** `paths` = `['/api/cards/{card_id}', '/api/deck/{deck_id}', '/api/decks',
'/health']` (**4**); `components.schemas` = `['Card', 'CardSummary', 'DeckCardSummary',
'DeckDetail', 'DeckSummary', 'ErrorResponse', 'HealthResponse']` (**7**).

**Landmines 12, 14, 15, 16 re-verified read-only against the live database**
(`C:/Users/brads/AppData/Local/artificial-planeswalker/cards.db`) — every number in the story
reproduced, none corrected:

- **Landmine 12** — `PRAGMA table_info(cards)` → **23 columns**, `released_at` absent, `set_type`
  absent. `sqlite_master` holds no table whose name contains `set` — there is no sets table.
- **Landmine 16** — `CREATE TABLE decks (… format VARCHAR NOT NULL …)`; **0 of 40** rows null or
  blank; formats `standard` 19 · `brawl` 18 · `standardbrawl` 2 · `historic` 1.
- **Landmine 11** — 38,261 cards, **880,003** legality entries, **0** cards with null/empty
  `legalities`, **23** distinct keys, and `set(keys) == set(_KNOWN_FORMATS)` is `True`. Vocabulary:
  `not_legal` 516,401 · `legal` 362,238 · **`banned` 1,275** · `restricted` 89. Banned by format
  led by `duel` 250 · `oathbreaker` 210 · `legacy` 170 · `vintage` 101 · `commander` 83, with
  `standard` **10**; `restricted` only in `vintage` 51 · `duel` 24 · `tlr` 10 · `timeless` 4.
- **Landmines 14 + 15** — all 40 real decks validated against their own stored format:
  **35 legal / 5 not**, violations `min_deck_size` **4** and `format_legality` **1**, and
  **0 banned + 0 restricted card entries anywhere in the deck table**. Q2's split therefore
  changes no verdict on any real deck, and the banned row can only be probed synthetically.

### Debug Log References

**1. AC 15's central prediction was wrong, and it was wrong in the safe direction.** The AC says
extending `DeckViolation.rule` will redden six named assertion sites across three test files and
that "a red there is **expected** and must be updated deliberately". Measured: **zero reds, zero
test-file edits.** `tests/unit/logic/test_deck_validator.py`,
`tests/integration/mcp_server/test_deck_analysis_tool.py` and `tests/integration/test_mcp_tools.py`
ran **103 passed** against the split, untouched.

The reason is decidable and worth writing down, because it is the *same* measurement the story
already made and did not carry through: **no test anywhere seeds a card whose legality is
`"banned"`.** A grep for the literal across all three files returns nothing, and every
`format_legality` fixture uses either `{"modern": "legal"}` (a missing `standard` key) or
`legalities=None`. Both still route to `format_legality` after the split, because the new branch
fires only on the exact string `"banned"`. So the ripple was real but landed entirely on
*docstrings*: `DeckViolation`'s `Attributes:`, `validate_deck`'s bullet list, the module docstring
and the MCP tool's own docstring — four prose edits, no assertion edits.

The story's landmine 15 measured "zero banned cards in the deck table" and drew the right
conclusion for *fixtures*; it did not extend the same reasoning to *test fixtures already in the
tree*, which is where the false prediction came from. Coverage for the new rule was therefore
**added** rather than repaired: two tests in `test_deck_validator.py` (the split discriminating
between two cards in one deck; `restricted` pinned as unchanged) plus the projection suite.

**2. A structural pin went red that the story did not name — and it is the same miss as c3-2's.**
The story's "five things this story must not break" names
`test_routes_decks.py::test_the_component_names_are_exactly_these` and says *"This story names it
in advance; there is no excuse for finding it during a probe."* It was found by running the suite,
because the pin that failed was the **other** one:
`test_routes_cards.py::test_the_component_names_gained_exactly_the_card_schema`. c3-2's Debug Log 3
recorded exactly this shape (*"a third structural pin was supposed to go red and the story named
only two"*). Twice is a pattern: two hand-synchronised copies of one fact, and the story text
tracks one of them. Both updated deliberately with their comments restated; ledgered with a fix
shape and homed on **c3-4**, which would otherwise inherit it a third time.

**3. I destroyed `src/logic/deck_validator.py` mid-probe and restored it from a backup taken
seconds earlier.** Applying probe C through PowerShell, a `.Replace()` call raised a
`MethodException` that did **not** terminate the script; `$t2` stayed `$null`, the guard `if ($t2
-eq ...)` compared against null and did not throw, and `Set-Content` wrote the null — truncating
the file to **0 bytes**. Caught immediately (the next `Read` reported "the file has 1 lines"),
restored from `%TEMP%\deck_validator.py.bak`, and verified byte-identical by SHA-256 before
continuing. Recorded rather than quietly fixed because the lesson is general: **PowerShell
non-terminating errors do not stop a script**, so a `Set-Content` downstream of a failed
computation writes whatever the variable happens to hold. Both remaining probes were applied with
the `Edit` tool instead. No committed file was affected.

**4. Landmine 7 measured, and it corrects a standing `deferred-work.md` entry.** The entry naming
the `test_spa.py` router-list tax lists c3-3 among the stories that "must add one line there or get
a red". Measured: `test_spa.py` **56 passed** with no edit. The tax falls on adding a **router**,
not a **route** — both sides of the differential build their path sets from the same router
objects, so a new path on an already-listed router appears on both. `build_app()` likewise needed
no edit. The entry is corrected in place and the `test_spa.py` comment now says so, so c3-4 and
c3-5 do not go looking for an edit they may not owe.

**5. The wire-prose gate found nothing, and that is a claim I checked rather than assumed.** The
family scan (`PYTHON_INTERNAL_FAMILIES`) plus seven literal markers were run over the regenerated
`types.d.ts`: **0 hits across all three families**, and `0` occurrences of `>>> `,
`model_validate`, `SQLAlchemy`, `pydantic`, `src/mcp_server`, `ValidateDeckResult` and
`validate_deck`. The last is the one that mattered — this is the first story to put a `src/logic`
model on the wire, and `validate_deck` is both a function here and an MCP tool name. It does not
appear because `format_check`'s docstring names it nowhere and the `Attributes:` sections that
enumerate rules are truncated before the wire.

### Completion Notes List

**What shipped.** `GET /api/deck/{deck_id}/format-check`, a six-line handler on the existing
`decks.router`, over a new `format_check()` projection in `src/logic/deck_validator.py` and a
`banned_card` split inside `validate_deck` itself. Two new wire shapes (`FormatCheckReport`,
`FormatCheckRow`) — **the first components in the schema described by `src/logic` rather than
`src/data`**. No new reason token, no new router, no new dependency, no `build_app()` edit.

**All five questions answered as proposed, with one partial (Q5), making it thirteen of thirteen
stories.** Q1 put the projection in `src/logic` and the route on `decks.py`; Q2 extended the rule
vocabulary; Q3 shipped the permanent `advisory` rotation row; Q4 keyed "no format" on
`unknown_format` with one response shape always; Q5 took the `_is_ref_rooted` repair and declined
the README re-anchoring, which was re-homed.

**The six checks, worked row by row (AC 3).** Every one is covered; none was silently dropped.

| UX-DR21 check | Row | Fed by | Outcome |
| --- | --- | --- | --- |
| Legality | `legality` | `format_legality` | Answerable; `advisory` when the format is unrecognised |
| Size | `size` | `min_deck_size` | Answerable — and 60-cards-always, see the ledger |
| Copy limit | `copy_limit` | `copy_limit` **and** `singleton` | Answerable; two rules, one row |
| Sideboard | `sideboard` | `max_sideboard_size` | Answerable |
| Banned | `banned` | **`banned_card`** (new) | Answerable; `advisory` when the format is unrecognised |
| Rotation exposure | `rotation` | *nothing* | **Never** answerable — permanent `advisory` (Q3) |
| *(unmapped)* | — | `game_availability` | Deliberately no row: not a UX-DR21 check, and this route passes no `games` |
| *(unmapped)* | — | `unknown_format` | Not a row: it makes two rows advisory rather than failing anything |

`CHECK_FOR_RULE` maps **every** member of `DeckViolationRule`, and a test pins its key set equal to
the `Literal`'s members — so a rule added later without a row decision fails by name rather than
vanishing from the panel.

**Three decisions I made that the story did not specify, each stated rather than slipped in.**

1. **`format_recognized: bool` on the report.** The epic asks for "a defined response the UI can
   render as *no format to check against*"; without a flag, c4-10 would have to key that state off
   prose or off an indirect signal (the legality row happening to be advisory). One statically
   decidable boolean instead. Ledgered as declared-but-unread until c4-10, with the instruction to
   delete it rather than maintain it if c4-10 never reads it.
2. **A multi-violation row summarises as `"<first detail> (+N more)"`.** The panel is one row per
   *check*, so N faults have to become one sentence somewhere. Doing it in `src/logic` keeps the
   prose beside the rules — which is already `DeckViolation.detail`'s job — instead of joining 60
   sentences or inventing the collapse in a shell.
3. **The report carries the *normalised* format, not the stored one.** It names what was actually
   checked. Measured: 0 of 40 real decks store a format that differs from its normalisation, so the
   two endpoints agree today; ledgered anyway, because a UI comparing the two strings would be
   comparing two different things.

**AC 5's gate is a mechanism, not a comment.** `find_rule_violations` is a pure AST function over
`src/companion/**` banning four families: any `.legalities` read, any import from the validator
module outside a declared projection surface, any comparison against `60`/`15`/`4`, and any
rebuilt set of Scryfall format names. Nine firing cases and six silent cases are parametrised, so
each family is proven to discriminate. **`1` is deliberately outside the comparison family** — the
singleton limit is 1, but `> 1` and `== 1` are ubiquitous, so banning it would be noise rather than
signal. That is a declared limit, written into the `_LIMIT_LITERALS` docstring and into
`ui/README.md`'s blind-spot map, not a hole found later.

**Four mutation probes, all four caught, each verified on disk before the verdict and reverted
after** (both mutated source files re-hashed identical to their pre-probe backups):

| Probe | Mutation | Result |
| --- | --- | --- |
| a | Route decorator commented out (silently unregistered) | **27 failed**, including `TestNotShadowedBySpa` — c3-1's R1 defect in this story's shape — and the schema drift gate |
| b | `get_deck_with_cards` → `get_deck` on this handler only | **9 failed**, headline `assert 0 == 60` and `assert 0 == 23`. The route answered `200` with a plausible report about a 0-card deck; nothing raised |
| c | `pass`/`violation` inverted for the `size` row only | **5 failed** across *both* layers, including `test_the_all_pass_claim_is_not_vacuous` — the exact pair AC 25 exists for |
| d | Staged `type FormatCheckReport` planted in `ui/src` | **1 failed**: `"src/planted-probe.ts declares FormatCheckReport"`, with **no edit to the ban mechanism** |

Probe (b) is the load-bearing one: it is the story's landmine 3 reproduced exactly — a silent zero,
not a crash, dressed as a legitimate `min_deck_size` violation. Probe (a)'s output was read rather
than counted: the `TestCommittedSchema` tests correctly did **not** fail (they read the committed
artifact, which the drift gate covers separately), and
`test_an_unrouted_sibling_path_is_refused_rather_than_falling_back` correctly did not fail either,
since it names a path that never had a route.

**AC 19 — the generated shape, recorded.** Every field on both models is **required and
non-nullable**: no `?`, no `| null`, no `@default`. c3-1's ledgered `strategy?: string | null` vs
`format: string | null` asymmetry does **not** repeat, and the reason is structural — those came
from Python-side defaults, and nothing here declares one. Both enums generate as inline closed
unions: `"legality" | "size" | "copy_limit" | "sideboard" | "banned" | "rotation"` and
`"pass" | "advisory" | "violation"`, not named types, which is what c4-10 will code against.

**AC 20 — no frontend behaviour shipped, and the permitted-file list was honoured.** `ui/` changes
are exactly: the two generated files, two `toContain` anchors in `wire-contract.test.ts`, and
`ui/README.md` (a new blind-spot row, plus a prettier reformat the gate demanded). `App.tsx`, every
component, `schema.ts`, `states.ts` and `copy.ts` are untouched. **No deviation from the permitted
list was needed** — c3-2's round-2 lesson did not have to be applied.

**AC 21 — the bundle re-measured, not assumed.** All five SPA files are byte-identical to the Task
0 baseline *and* to the plugin mirror, exactly as predicted for a story shipping no runtime
frontend code. Six mirrored `.py` files were rebuilt and are committed.

**Suite counts, before → after.** Python **1893 → 1987** passed (1 skipped throughout), +94.
Frontend **558 → 558** — unchanged by design, since this story ships no frontend behaviour. Schema
**4 paths → 5**, **7 components → 9** (`FormatCheckReport`, `FormatCheckRow`; nothing removed).

### Same-day three-layer review (Task 7, 2026-08-01)

Blind Hunter + Edge Case Hunter + Acceptance Auditor, run in parallel against `2a787ac..11a0750`.
**~40 findings; 18 patches applied, 4 dismissed with reasons, 3 ledgered.** The three layers
overlapped heavily on the two biggest items, which is the signal they exist to give.

**The finding I would not have found: a shipped product artifact consumes the vocabulary I
extended.** `.claude/skills/format-legality/SKILL.md` is the user-facing skill that reads
`validate_deck`'s structured output, and it *enumerates the rules*. Adding `banned_card` made
three of its statements false — the rule table, the flat claim *"The tool treats **all** non-legal
as the same `format_legality` violation"*, and the `violation.rule` is-one-of list. Worse than
stale: the skill's playbook routes `format_legality` to a "look up why" step, so with a banned
card it would have found **no** `format_legality` violation for that card and reported the deck
legal-except-size. AC 15 said "every ripple site is worked in the same commit" and the story
enumerated the ripple sites — **the skill was not among them**, and nothing in the test suite
pins skill prose against the tool's vocabulary. Fixed: the rule table gains `banned_card` *and*
`unknown_format` (the latter was **already** missing before this story), the false claim is
rewritten, the playbook gains a `banned_card` entry, and the `restricted` over-flag is stated as
the skill's remaining value-add. `plugin/skills/` rebuilt from it. (`.agents/skills/` is
gitignored dev tooling regenerated by the installer — out of scope, noted not edited.)

**The headline correctness finding: `is_legal: false` with no row saying why.** A formatless deck
answers `is_legal: false` while **every row is a pass or an advisory and not one is a violation**
— because `unknown_format` is a violation to the validator but feeds no row. A panel rendering
`is_legal` as its verdict shows "Not legal" above six non-faults. The behaviour is right (it
mirrors the validator, so panel and agent cannot disagree); the *documentation* was the defect —
the explanation sat in an `Attributes:` block, which the schema builder truncates before the wire.
Promoted to a **`Warning:`**, one of the two headers `main.py` deliberately preserves, so c4-1's
fetch author reads it in the JSDoc. This is c3-2's 503-retry-trap precedent applied to a second
case. Verified in `types.d.ts` after regeneration. Three new tests pin the pair.

**The guard I wrote was theatre, and it was measured to be.** The adversarial layer ran twelve
plants through `find_rule_violations`; **all twelve returned `[]`**, including a seven-line
composite reimplementing the size rule, the singleton rule, the format set *and* the legality read
at once. Every family was keyed on the syntax my own firing tests happened to use — so the guard's
only proven property was that it caught its own four examples. This is c2-3's review theme
("every regex/list guard had an unprobed evasion") and c3-2's ("a guard that could not fail for
its stated reason") arriving for a third time. Rewritten to key on the *name* and the *value*
rather than the syntax: `legalities` in any position, all four validator-import spellings, the
limits as any number in any position (`int` or `float`), format names in any container including
dict keys, and a fifth family for `.quantity` (AC 5 names "any copy counting" and I had no family
for it). Re-probed: **11/11 evasions caught, 0/6 false positives**, each pinned as a case.

**Two false greens I introduced into `_is_ref_rooted`** — the Q5 repair re-opened a hole the c3-1
review had closed. My union arm runs *before* the array arm and returned unconditionally, so
`{"type": "array", "items": {inline envelope}, "anyOf": [$ref]}` was waved through: a decorative
union key smuggling an envelope past the array guard. And `{"anyOf": [{"type": "null"}]}` returned
`True` — "rooted in zero component references", because `all()` over a null-only list is vacuously
true. I had added `({"anyOf": []}, False)` specifically to avoid that vacuity and left the
one-branch case, which is the same hole shifted by one element. Both fixed, plus a false *red*
(`{"type": ["null"]}`, the equally legal 3.1 spelling), with five new table rows.

**Server-authored prose that was false rather than merely awkward.** The size row read
`"Mainboard has 60 cards; {format} requires at least 60."` — but `_MIN_MAINBOARD` is applied
*regardless* of format (D-1.6b). So it rendered a gap with no format (`"…cards;  requires…"`),
contradicted the row above it for an unrecognised one (`"'potato' is not a recognized format"` /
`"potato requires at least 60"`), and was **simply false for Commander**, stated affirmatively
beside `is_legal: true`, on a panel a person reads. Three findings, one root cause: the structural
rows were attributing limits to a format nobody consulted. Now they never name a format —
`"the minimum is 60"`, true everywhere — and the same repair was applied to `validate_deck`'s own
violation detail, so the agent surface stops saying it too. The format-*specific* rows (legality,
banned) still name the format, pinned by a non-vacuity pair. This also deleted the
`normalised in _SINGLETON_FORMATS` read that made `format_check`'s "reimplements no rule"
docstring untrue.

**Smaller patches:** the advisory arm now carries `and not by_check[name]`, so a violation on an
unanswerable row can never be silently swallowed (unreachable today, but the projection was
*assuming* a guarantee that lives in another function); `_summarise` sorts on card name, because
`deck_cards` order is documented as not meaningful, so `"(+N more)"` was headlining a
UUID-sort accident — pinned by a test that reverses the entries and demands the same sentence;
the route docstring's *"the two surfaces can never disagree"* is false as written (the MCP tool
takes `format` as a parameter defaulting to `"standard"`) and now says the rules are shared while
the inputs need not be; `_unanswerable` stopped blaming the deck for a caller's blank input; a new
test pins `_SINGLETON_FORMATS <= _KNOWN_FORMATS`, an invariant that was load-bearing and held only
by coincidence of two frozensets; `validate_deck`'s docstring scope note (AC 22 row 5's *second*
cited location, which I had missed) is restated; and `ui/README.md`'s blind-spot row was rewritten
after the review found it **under-declared its own guard's holes** — the section's rule is "a
declared blind spot is still a claim".

**Dismissed, with reasons.** (1) *"An empty deck reports three confident passes"* — vacuously
true, and the story explicitly forbids an empty-deck branch (UX-DR33 hides the panel client-side;
a bespoke response would be a state c4-10 never renders). (2) *"`{"$ref": …, "default": {...}}`
is a false green"* — `default` is metadata; the response body is still the referenced component.
(3) *A card missing the format key entirely reports "No card is banned"* — the legality row
already reports that card, and measured, 0 of 38,261 cards miss any of the 23 keys; the
version-skew variant is ledgered instead. (4) *"`1` should be in the limit family"* — AC 5 names
it, but `> 1` / `== 1` are ubiquitous; kept as a declared limit in three places rather than
quietly dropped.

**Two record defects the Auditor caught, both fixed:** `src/companion/app/deps.py` was edited
(docstring only) outside the story's declared source-tree list with no deviation entry — booked
below; and the `test_spa.py` router-list correction was *appended* to the `deferred-work.md` entry
rather than applied to the wrong list itself, so a reader stopping at the list still got the wrong
answer. The list is now corrected in place.

**Deviations, booked at review time rather than left for a reviewer:**

| File | Why it is outside the declared list |
| --- | --- |
| `src/companion/app/deps.py` | Docstring only. `DbSession`'s caller list named c3-3 in the future tense and claimed "c3-1 and c3-2 are both shipped and did exactly that"; both became false on merge. A forward-dated-comment repair of exactly the kind AC 22 mandates, on a file AC 22's six-row table did not list. |
| `.claude/skills/format-legality/SKILL.md` | Not in the story's source tree at all. Forced by Q2: the skill enumerates the rule vocabulary the story extended. See the headline finding above. |
| `tests/unit/companion/test_routes_cards.py` | The second component-name pin. The story named only the `test_routes_decks.py` one. |

**A fourth undeclared decision, booked late:** `format_check` takes an optional `format=` keyword
the route never passes. It exists so a what-if caller can ask about a different format without
mutating a deck, and it keeps the function's signature parallel to `validate_deck`'s. It should
have been in the three-decisions list above; it is a public surface with one caller and no
consumer, and if nothing ever passes it, it should be deleted rather than maintained.

**Gate output, post-review, from the same tree** (AC 16, AC 27 — the Auditor correctly noted the
first pass recorded only baseline output):

```
uv run pytest                     2032 passed, 1 skipped in 143.87s
uv run ruff check .               All checks passed!
uv run ruff format --check .      294 files already formatted
uv run mypy src/                  Success: no issues found in 86 source files
uv run mypy src/ --platform win32 Success: no issues found in 86 source files
ui: npm run lint                  clean (eslint + stylelint)
ui: npm run format:check          All matched files use Prettier code style!
ui: npx tsc -b --force            exit 0, no output
ui: npm test                      29 files / 558 tests passed
ui: npm run build                 built in 106ms
drift 1: test_openapi_contract    15 passed
drift 2: npm run gen:api          NO DRIFT — both generated files reproduce byte-for-byte
bundle:  src vs Task-0 baseline   byte-identical (5 files)
bundle:  plugin mirror vs src     byte-identical (5 files)
```

Suites **1987 → 2032** Python across the review pass (baseline 1893, so **+139** for the story);
frontend **558**, unchanged throughout.

**One flake, named rather than absorbed.** The Auditor's independent full run hit
`tests/integration/data/test_deck_repository.py::test_list_decks_with_strategy_field` — the
long-standing `list_decks` `created_at` tie-order flake, unrelated to this diff, already ledgered
at Medium after firing during c3-2. That is now its **fifth** confirmation across five stories.
It did not fire in either of my runs.

### File List

**Source (7)**
- `src/logic/deck_validator.py` — the `banned_card` split, `DeckViolationRule`, and the whole
  `format_check` projection (`FormatCheckStatus`, `FormatCheckName`, `CHECK_ORDER`,
  `CHECK_FOR_RULE`, `FormatCheckRow`, `FormatCheckReport`, `_ROTATION_DETAIL`, `_summarise`,
  `_unanswerable`, `format_check`); D-1.6b scope note restated
- `src/companion/app/routes/decks.py` — the `read_deck_format_check` handler and the module
  docstring
- `src/companion/app/errors.py` — docstrings only (two forward-dated comment repairs)
- `src/companion/app/main.py` — comment only (the ordering block)
- `src/companion/app/deps.py` — docstring only (`DbSession`'s caller list)
- `src/mcp_server/tools/deck_analysis.py` — docstring only (the tool's rule enumeration)
- `scripts/dump_openapi.py` — docstring only (counts; c3-4 named)

**Tests (6)**
- `tests/unit/logic/test_format_check.py` — **NEW**, 40 tests
- `tests/unit/companion/test_routes_format_check.py` — **NEW**, 52 tests incl. the AC 5 gate
- `tests/unit/logic/test_deck_validator.py` — two tests added for the new rule
- `tests/unit/companion/test_errors.py` — Q5's `_is_ref_rooted` repair + 10 table rows
- `tests/unit/companion/test_routes_decks.py` — the component-name pin
- `tests/unit/companion/test_routes_cards.py` — the second component-name pin
- `tests/unit/companion/test_spa.py` — comment only (the router-list tax, corrected)

**Generated / frontend (4)**
- `ui/src/api/openapi.json` — regenerated, committed
- `ui/src/api/types.d.ts` — regenerated, committed
- `ui/tests/wire-contract.test.ts` — two non-vacuity anchors
- `ui/README.md` — one blind-spot row

**Plugin mirror (6)** — `plugin/server/src/{logic/deck_validator,companion/app/routes/decks,
companion/app/errors,companion/app/main,companion/app/deps,mcp_server/tools/deck_analysis}.py`,
rebuilt by `scripts.build_plugin`

**Records (3)** — this story file, `deferred-work.md`, `sprint-status.yaml`

### Change Log

| Date | Change |
| --- | --- |
| 2026-07-31 | Story contexted off `2a787ac`; 19 landmines, 27 ACs, 5 open questions (Q2 and Q3 are genuine forks) |
| 2026-08-01 | All 5 questions ruled (Q5 partial). Implemented: the `format_check` projection + `banned_card` split in `src/logic`, the route on `decks.router`, Q5's `_is_ref_rooted` repair. Schema 4→5 paths / 7→9 components, both generated files committed together. Four mutation probes, all caught. Python 1893→1987, frontend 558 unchanged. Five findings recorded, two of them corrections to the story's own text (AC 15's expected reds did not happen; the router-list tax does not apply to this story) |
| 2026-08-01 | Same-day three-layer review: ~40 findings → **18 patches**, 4 dismissed, 3 ledgered. Headlines: the shipped `format-legality` skill enumerates the rule vocabulary and was left stale by Q2 (a ripple site the story never named); `is_legal: false` with no violation row, promoted to a wire-visible `Warning:`; the AC 5 guard missed **12 of 12** planted evasions and was rewritten to key on names and values rather than syntax (now 11/11 caught, 0 false positives); two false greens I introduced into `_is_ref_rooted`; and the structural rows were attributing the 60-card minimum to a format nobody consulted — false for Commander, on a panel. Suites 1987 → **2032**; all fourteen gates re-run green from the same tree |
