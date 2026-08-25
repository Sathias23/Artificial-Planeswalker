---
baseline_commit: 0e71117
---

# Story 1.5: Deck Management Tools

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a player using Claude Code,
I want to create, list, load, and delete decks and add/remove cards via the MCP server,
so that I can build and persist Standard decks, with the active deck tracked by my client (a `deck_id`) and no server-side state.

## Decisions Locked (resolved with Brad, 2026-06-20)

> These resolve the open forks before the story was finalized. They shape the ACs/Tasks below — **do not re-litigate**.
>
> - **D-1.5a — `add_card_to_deck` / `remove_card_from_deck` accept EITHER `card_id` OR `name` (exactly one required).** The `card_id` path is the thin wrapper over `DeckRepository`; the `name` path resolves the card internally (exact → partial), returning `status="ambiguous"` (with candidate `matches`) when a partial name hits >1 card, mirroring `lookup_card_by_name`'s buckets. Providing both or neither → `status="invalid"`.
> - **D-1.5b — Pure CRUD; NO construction-rule validation in this story.** `add_card_to_deck` only persists the association. **Standard-legality, the 4-copy limit, and deck-size checks are explicitly deferred to `validate_deck` (Story 1.6, FR11).** Do **not** port the legacy `validate_card_addition` guardrails here. The legacy `src/logic` validators stay unused until 1.6.
> - **D-1.5c — Duplicate add is graceful, NOT an upsert.** Adding a card already present in that `(deck_id, card_id, sideboard)` location hits the composite-PK `IntegrityError`; catch it and return `status="exists"` with a "already in this deck; adjust quantity instead" message. Do **not** silently merge quantities (`update_card_quantity` is out of FR8 scope).
> - **D-1.5d — `load_deck` and `delete_deck` take a required `deck_id` only (no name lookup).** The client gets ids from `list_decks`/`create_deck`. This is the safest contract for the destructive `delete_deck` (a partial-name match could delete the wrong deck) and the cleanest stateless one. A missing id → graceful `not_found`. **No `confirmed=` flag** — confirmation is the client's (the LLM's) responsibility, not server state.
> - **D-1.5e — Results use NEW lightweight deck projections (mirrors the 1.4 `CardSummary` decision).** The full `Deck` schema nests `DeckCard` → **full `Card`**, far too heavy for the LLM client. This story **adds** `DeckSummary` (metadata + counts, **no** nested cards — for `list_decks`), `DeckCardSummary` (`quantity`/`sideboard` + a `CardSummary`), and `DeckDetail` (metadata + counts + `cards: list[DeckCardSummary]` — for `create_deck`/`load_deck`) to `src/data/schemas/deck.py`. They **reuse the existing `CardSummary`** (added in 1.4 explicitly "intended for reuse by ... Story 1.5 deck listings"). These projections are also reusable by Story 1.6 analysis tools.
> - **D-1.5f — ONE additive `src/data` behavior change: `CardRepository.get_by_id`.** The `card_id` path needs to confirm a card exists (FK enforcement is OFF — see Dev Notes), and there is **no** card-by-id repository method today (only name/color/type/keyword finders). Add a small read-only `get_by_id(card_id) -> Card | None` to `CardRepository`. This is additive and behavior-preserving; **do not** modify any existing repository method or model.
> - **D-1.5g — Color-identity recompute and quantity-update are OUT of scope.** `add_card_to_deck` does **not** call `update_deck_color_identity` (returned `color_identity` reflects the stored value, which stays as-is for tool-built decks — a known, documented limitation; a future story/skill can refresh it). `update_card_quantity`, `update_deck`/`update_deck_strategy`, `merge_decks`, and `view_deck` are **not** exposed (not in FR8's six-tool list).

## Acceptance Criteria

> Source: [epics.md#Story-1.5](../planning-artifacts/epics.md) (BDD as authored), with the locked decisions above and implementation-critical clarifications folded in. **All seven must hold simultaneously.** This story adds the **fourth–ninth Epic-1 tools** on top of the Story-1.3 server skeleton + Story-1.4 patterns; it reuses the server builder, the closure-injected `session_factory`, the structured-`*Result` convention, and the in-memory harness already in place.

**AC1 — `create_deck` / `list_decks` / `load_deck` / `delete_deck` operate via `DeckRepository` and return structured results (FR8)**
- **Given** the four deck tools
- **When** invoked
- **Then** `create_deck` wraps `DeckRepository.create_deck(...)` and returns the new deck as a `DeckDetail` (empty `cards`); `list_decks` wraps `DeckRepository.list_decks(format_filter=...)` and returns a list of lightweight `DeckSummary`; `load_deck` wraps `DeckRepository.get_deck_with_cards(deck_id)` and returns a `DeckDetail`; `delete_deck` wraps `DeckRepository.delete_deck(deck_id)` and returns a confirmation — **all with no SQL re-implemented in the tools** (the established D-1.4a pattern).
- **And** `list_decks` on an empty DB returns `status="empty"` (graceful), and `delete_deck`/`load_deck` on a missing `deck_id` return `status="not_found"` (graceful) — **not** exceptions.

**AC2 — `add_card_to_deck` / `remove_card_from_deck` accept `card_id` OR `name`, and the change persists to SQLite (FR8, D-1.5a, D-1.5c)**
- **Given** `add_card_to_deck`/`remove_card_from_deck` with a `deck_id` and **exactly one** of `card_id` or `name`
- **When** invoked
- **Then** the deck-card association is created/removed via `DeckRepository.add_card_to_deck(...)` / `remove_card_from_deck(...)` and **persists** to SQLite (verified by re-reading via the same session factory)
- **And** a `name` that hits one card resolves to it; a partial `name` hitting >1 card returns `status="ambiguous"` with candidate `matches` (as `CardSummary`); adding a card already in that location returns `status="exists"` (graceful, no upsert); removing a card not in that location returns `status="not_in_deck"`.

**AC3 — Statelessness; pure CRUD (FR3, D5, D-1.5b)**
- **Given** the deck tools run
- **When** any sequence of calls is made
- **Then** the "active deck" is **only** the client-supplied `deck_id` — there is **no** server-side active-deck, format-filter, or session state (the legacy `_session_manager.set_active_deck_id` / `set_format_filter` behavior is **dropped**)
- **And** `add_card_to_deck` performs **no** Standard-legality or 4-copy-limit validation — it is pure persistence; those checks belong to `validate_deck` (Story 1.6).

**AC4 — Graceful errors for every bad input; no orphan rows (D-1.5a/d, FK-off safety)**
- **Given** a missing deck, a missing/ambiguous card, or invalid input (both `card_id` **and** `name` given, neither given, or `quantity < 1`)
- **When** a deck tool is invoked
- **Then** it returns a structured result (`status` ∈ `deck_not_found` / `card_not_found` / `ambiguous` / `not_in_deck` / `not_found` / `invalid`) with a message naming the problem — **no raw exception is surfaced** to the MCP client
- **And** because SQLite **foreign-key enforcement is OFF** on the async engine, `add_card_to_deck` **must pre-validate** that the deck exists (else a bogus `deck_id` would silently insert an **orphan** `deck_cards` row) and that the card exists (else the repo's post-insert reload would raise a `ValidationError` on the missing nested `Card`). A bogus `deck_id` returns `deck_not_found` and writes **no** row.

**AC5 — Bounded, lightweight payloads via deck projections (D-1.5e)**
- **Given** `list_decks` and `load_deck`
- **When** they return
- **Then** `list_decks` returns `DeckSummary` rows (metadata + `mainboard_count`/`sideboard_count`/`distinct_cards`, **no** nested card list) and `load_deck` returns a `DeckDetail` whose `cards` are `DeckCardSummary` (each nesting a lightweight `CardSummary`, **not** the full `Card`) — so neither call dumps `legalities`/`image_uris`/`card_faces` at the LLM client.

**AC6 — Exactly one additive `src/data` change; existing behavior unchanged (D-1.5f, NFR7)**
- **Given** the data layer
- **When** this story lands
- **Then** the **only** behavior addition is the read-only `CardRepository.get_by_id(card_id) -> Card | None` (plus the additive deck-projection schemas) — **no** existing repository method, model, or the `Deck`/`DeckCard` schema is modified
- **And** the existing `tests/unit` + `tests/integration/data` suites for data/logic still pass (no regression).

**AC7 — In-memory MCP client harness drives full deck CRUD end-to-end (no subprocess) (FR8, NFR6, spec §8)**
- **Given** the in-process MCP client harness against the file-backed seeded DB
- **When** it drives the full lifecycle — `create_deck` → `add_card_to_deck` (by `name` **and** by `card_id`) → `load_deck` → `list_decks` → `remove_card_from_deck` → `delete_deck`
- **Then** integration assertions pass **without spawning a subprocess**, reusing the Story-1.3 wiring (`build_server(session_factory=...)` + `create_connected_server_and_client_session`)
- **And** the writes are correct under the async/aiosqlite path (the repositories' existing commit/rollback transaction discipline guarantees this; WAL-mode tuning is the sync-`ConnectionFactory`'s concern in Epic 2, **not** changed here).

## Tasks / Subtasks

- [x] **Task 1 — Additive deck projection schemas** (AC: 1, 5) — *pure schemas in `src/data/schemas/deck.py`; reuse `CardSummary`*
  - [x] In [src/data/schemas/deck.py](../../src/data/schemas/deck.py) add three classes **alongside** `Deck`/`DeckCard` (do **not** modify those). Import `CardSummary` from `src.data.schemas.card`.
    - `DeckCardSummary(BaseModel)` — `model_config = ConfigDict(from_attributes=True)`; fields `card_id: str`, `quantity: int`, `sideboard: bool`, `card: CardSummary`. The lightweight counterpart to `DeckCard` (which nests the full `Card`).
    - `DeckSummary(BaseModel)` — `model_config = ConfigDict(from_attributes=True)`; fields `id: str`, `name: str`, `format: FormatType`, `strategy: str | None = None`, `color_identity: list[str] = []`, `tags: list[str] = []`, `mainboard_count: int = 0`, `sideboard_count: int = 0`, `distinct_cards: int = 0`, `created_at: datetime`, `updated_at: datetime`. **No** nested card list (for `list_decks`).
    - `DeckDetail(BaseModel)` — `model_config = ConfigDict(from_attributes=True)`; same metadata + counts as `DeckSummary` **plus** `cards: list[DeckCardSummary] = []` (for `create_deck`/`load_deck`).
  - [x] Google-style class docstrings noting each is the lightweight projection for deck-returning tools (reused by Story 1.6). **NOTE:** the count fields are **computed by the tool helper**, not by `model_validate` (a source `Deck` has no `mainboard_count` attribute — `model_validate` would silently use the `0` default). Build these via explicit constructors in Task 3, not `DeckSummary.model_validate(deck)`.
  - [x] **Do NOT** modify `Deck`, `DeckCard`, `DeckModel`, or `DeckCardModel`.

- [x] **Task 2 — Additive `CardRepository.get_by_id`** (AC: 2, 4, 6) — *the only `src/data` behavior change (D-1.5f)*
  - [x] In [src/data/repositories/card.py](../../src/data/repositories/card.py) add `async def get_by_id(self, card_id: str) -> Card | None:` — `select(CardModel).where(CardModel.id == card_id)`, `scalar_one_or_none()`, return `Card.model_validate(model)` if found else `None`. Mirror the existing finder style + Google-style docstring. Read-only; no transaction handling needed.
  - [x] Add a unit test (extend [tests/unit/data/test_card_repository.py](../../tests/unit/data/test_card_repository.py)) asserting a found id returns the `Card` and a bogus id returns `None`.
  - [x] **Do NOT** modify any other repository method.

- [x] **Task 3 — `deck_management` tool helpers + result schemas** (AC: 1, 2, 3, 4, 5) — *new module, mirror [card_search.py](../../src/mcp_server/tools/card_search.py)*
  - [x] Create `src/mcp_server/tools/deck_management.py` with a module docstring (purpose: wraps `DeckRepository` 1:1, returns lightweight deck projections, stateless `deck_id`-keyed, drops legacy session/active-deck/format-filter machinery).
  - [x] **Result schemas** (Google-style docstrings):
    - `DeckListResult` — `status: Literal["ok", "empty"]`; `decks: list[DeckSummary] = []`; `count: int = 0`; `message: str`.
    - `DeckResult` — `status: Literal["ok", "not_found", "invalid"]`; `deck: DeckDetail | None = None`; `message: str`. (Shared by `create_deck` + `load_deck`.)
    - `DeckDeleteResult` — `status: Literal["ok", "not_found"]`; `deck_id: str`; `message: str`.
    - `DeckCardResult` — `status: Literal["ok", "exists", "not_in_deck", "deck_not_found", "card_not_found", "ambiguous", "invalid"]`; `deck_id: str | None = None`; `card_id: str | None = None`; `matches: list[CardSummary] = []` (populated on `ambiguous`); `message: str`. (Shared by `add_card_to_deck` + `remove_card_from_deck`.)
  - [x] **Private builders** (compute counts; do not `model_validate` for counts): `_deck_summary(deck: Deck) -> DeckSummary` and `_deck_detail(deck: Deck) -> DeckDetail`. Both compute `mainboard_count = sum(dc.quantity for dc in deck.deck_cards if not dc.sideboard)`, `sideboard_count = sum(... if dc.sideboard)`, `distinct_cards = len(deck.deck_cards)`; `_deck_detail` also builds `cards=[DeckCardSummary(card_id=dc.card_id, quantity=dc.quantity, sideboard=dc.sideboard, card=CardSummary.model_validate(dc.card)) for dc in deck.deck_cards]`.
  - [x] **Private card resolver** (shared by add/remove): `async def _resolve_card(card_repo, *, card_id, name) -> tuple[Card | None, str | None, list[Card]]` returning `(card, error_status, matches)`. `card_id` path → `await card_repo.get_by_id(card_id)`; `None` → `(None, "card_not_found", [])`. `name` path → `find_by_name_exact(name)`; else `find_by_name_partial(name)`: 0 → `card_not_found`; 1 → that card; >1 → `(None, "ambiguous", matches[:10])`. (Caller validates exactly-one BEFORE calling.)
  - [x] **Helpers** (each takes `session: AsyncSession`, keyword-only domain args, returns the matching `*Result`; validate-first, never raise):
    - `async def list_decks(session, *, format: str | None = None) -> DeckListResult` — `DeckRepository(session).list_decks(format_filter=format)`; empty → `status="empty"` + helpful message; else `status="ok"`, `decks=[_deck_summary(d) ...]`, `count=len`. (`format` kept as param name — project convention; ruff `N` allowed.)
    - `async def create_deck(session, *, name: str, format: str = "standard", strategy: str | None = None, tags: list[str] | None = None) -> DeckResult` — validate `name.strip()` non-empty (else `status="invalid"`); call `repo.create_deck(name=name, format=format, strategy=strategy, tags=tags)`; return `status="ok"`, `deck=_deck_detail(created)` (cards empty). **Note:** deck `name` is **NOT** unique (see Dev Notes) — do **not** add duplicate-name handling.
    - `async def load_deck(session, *, deck_id: str) -> DeckResult` — `repo.get_deck_with_cards(deck_id)`; `None` → `status="not_found"`; else `status="ok"`, `deck=_deck_detail(deck)`.
    - `async def delete_deck(session, *, deck_id: str) -> DeckDeleteResult` — `repo.delete_deck(deck_id)`; `False` → `status="not_found"`; `True` → `status="ok"` confirmation.
    - `async def add_card_to_deck(session, *, deck_id: str, card_id: str | None = None, name: str | None = None, quantity: int = 1, sideboard: bool = False) -> DeckCardResult` — see flow in Dev Notes (validate exactly-one + `quantity >= 1` → `invalid`; `get_deck(deck_id)` None → `deck_not_found`; `_resolve_card` → `card_not_found`/`ambiguous`; `repo.add_card_to_deck(...)` **wrapped in `try/except IntegrityError`** → `exists`; else `ok`).
    - `async def remove_card_from_deck(session, *, deck_id: str, card_id: str | None = None, name: str | None = None, sideboard: bool = False) -> DeckCardResult` — validate exactly-one → `invalid`; `get_deck(deck_id)` None → `deck_not_found`; `_resolve_card` → `card_not_found`/`ambiguous`; `repo.remove_card_from_deck(deck_id, card.id, sideboard)` → `True`=`ok`, `False`=`not_in_deck`.
  - [x] Google-style docstrings on each helper = **the LLM-facing tool description** (filters/params, statelessness, that `card_id` OR `name` is required, that decks/cards are summaries — use `lookup_card_by_name` for full card detail, `load_deck` for full deck contents).

- [x] **Task 4 — Register the six tools in `build_server`** (AC: 1, 2, 3, 7) — *closure registration, transport-agnostic; mirror the `search_cards` wrapper*
  - [x] In [src/mcp_server/server.py](../../src/mcp_server/server.py) add six `@mcp.tool()` `async def` wrappers — `list_decks`, `create_deck`, `load_deck`, `delete_deck`, `add_card_to_deck`, `remove_card_from_deck` — each closing over `session_factory`, opening `async with session_factory() as session:`, delegating to the corresponding helper. Param surface = the helper's domain args (keep `format`/`name`/`deck_id`/`card_id`/`quantity`/`sideboard`).
  - [x] Import the result schemas + helpers from `src.mcp_server.tools.deck_management`; import the helpers under **private aliases** (e.g. `add_card_to_deck as _add_card_to_deck_helper`) to avoid the wrapper/helper name clash (the `_search_cards_helper` precedent).
  - [x] **No** change to `__main__.py`, `.mcp.json`, transport selection, or `src/mcp_server/__init__.py`. The wrappers are `async def` awaiting the async repos directly (D-1.4c) — **not** the sync `ConnectionFactory` (that is Epic 2).

- [x] **Task 5 — Helper-level integration tests** (AC: 1, 2, 3, 4, 5, 6) — *new file, mirror [test_card_search_tool.py](../../tests/integration/mcp_server/test_card_search_tool.py)*
  - [x] `tests/integration/mcp_server/test_deck_management_tool.py` — own file-backed (**not** `:memory:`) engine + a single `session` fixture, seeding cards via the `test_deck_repository.py` card pattern (Lightning Bolt `card-bolt` R, Counterspell `card-counterspell` U, Forest `card-forest`; add a second "bolt"-substring card, e.g. `card-thunderbolt` "Thunderbolt", so the **ambiguous** name path is exercised). *(Helper tests share **one** session, so a single in-memory session would also work for the helpers — but because the repo `add_card_to_deck` commits and re-selects, a file-backed engine + one shared session is the safe mirror of the existing deck-repo tests.)*
  - [x] Cover, asserting `status` + structured fields + lightweight projections:
    - `create_deck`: ok; with `strategy`+`tags`; **duplicate name allowed** (two distinct ids); blank name → `invalid`.
    - `list_decks`: `empty` on fresh DB; `ok` after creating (assert `DeckSummary` fields + counts; **no** `cards`/`deck_cards` key); `format` filter narrows results.
    - `load_deck`: `ok` (after adding cards — assert `DeckDetail.cards` are `DeckCardSummary` with a `CardSummary` inside, correct `mainboard_count`/`sideboard_count`); `not_found` for a bogus id.
    - `add_card_to_deck`: by `card_id` (ok, persists); by exact `name` (ok); by partial `name` → single (ok); by partial `name` → **`ambiguous`** with `matches`; `card_not_found` (bogus id **and** unknown name); `deck_not_found` (bogus deck) **+ assert no `deck_cards` row was created** (query the table — the FK-off orphan guard); duplicate add → `exists`; `sideboard=True` path; invalid (both `card_id`+`name`; neither; `quantity=0`).
    - `remove_card_from_deck`: by `card_id` (ok); by `name` (ok); `not_in_deck` (never added); `deck_not_found`; `card_not_found`; `ambiguous`; invalid (neither/both).
  - [x] At the harness/serialized level assert the deck-card cards omit heavy keys (`"legalities" not in ...`, `"image_uris" not in ...`); at the helper level assert the `DeckCardSummary`/`CardSummary` types.

- [x] **Task 6 — End-to-end MCP harness lifecycle test** (AC: 7) — *extend [test_mcp_tools.py](../../tests/integration/test_mcp_tools.py)*
  - [x] Add deck-CRUD tests using the shared **file-backed** `seeded_card_db` fixture (3 cards: Lightning Bolt `card-lightning-bolt`, Thunderbolt `card-thunderbolt`, Counterspell `card-counterspell`). Drive via `create_connected_server_and_client_session(build_server(session_factory=seeded_card_db))`.
  - [x] Full lifecycle through the **client**: `create_deck("My Deck")` → capture `deck_id` from `structuredContent["deck"]["id"]` → `add_card_to_deck(deck_id, name="Lightning Bolt", quantity=4)` (name path) → `add_card_to_deck(deck_id, card_id="card-counterspell")` (id path) → `load_deck(deck_id)` (assert 2 distinct cards, `mainboard_count == 5`, cards are summaries) → `list_decks()` (assert the deck appears with counts; **assert by set membership / id, NOT order** — `list_decks` ties on `created_at`, a known flake) → `remove_card_from_deck(deck_id, card_id="card-lightning-bolt")` → `delete_deck(deck_id)` (status `ok`) → `load_deck(deck_id)` again returns `not_found`.
  - [x] Add a graceful smoke: `add_card_to_deck("bogus-deck", card_id="card-counterspell")` → `structuredContent["status"] == "deck_not_found"`, `isError is False`.
  - [x] **Avoid editing** the shared `seeded_card_db` fixture (Story-1.3/1.4 tests depend on its exact 3-card contents). Build decks **through the tools**, not by seeding deck rows.

- [x] **Task 7 — Verify (run the commands, capture output)** (AC: all)
  - [x] `uv run pytest tests/integration/mcp_server/test_deck_management_tool.py tests/integration/test_mcp_tools.py tests/unit/data/test_card_repository.py -v` → new tests pass.
  - [x] `uv run pytest tests/` → full suite green except the **known-flaky** `test_deck_repository.py::test_list_decks` family (`created_at` tie; passes in isolation — see Previous Story Intelligence / [deferred-work.md](./deferred-work.md)). Confirm no **new** failures.
  - [x] `uv run ruff check .` / `uv run ruff format --check .` → all Story-1.5 files clean.
  - [x] `uv run mypy src/` → clean (strict). New `src/` code is fully typed.
  - [x] Optional smoke: confirm all six deck tools register on `build_server()` (the Task 6 harness test is the authoritative check).

## Dev Notes

### What this story IS — and is NOT

- **IS:** the **deck-management tool surface** (FR8) — six `async def` `@mcp.tool()` wrappers (`list_decks`, `create_deck`, `load_deck`, `delete_deck`, `add_card_to_deck`, `remove_card_from_deck`) that wrap the **existing** `DeckRepository` 1:1, return structured lightweight deck projections, validate inputs gracefully, and are stateless (`deck_id` is client-supplied). Plus **additive** projection schemas (`DeckSummary`/`DeckCardSummary`/`DeckDetail`), **one** additive read-only repo method (`CardRepository.get_by_id`), and integration tests (helper-level + in-memory MCP harness).
- **IS NOT:** analysis tools (`analyze_mana_curve`/`detect_synergies`/`validate_deck` — Story 1.6), **any** legality/4-copy/deck-size validation (deferred to 1.6 — D-1.5b), or **anything RAG/semantic** (Epic 2 — no `Embedder`, `card_vec`, sync `ConnectionFactory`). **No** `update_card_quantity`/`update_deck`/`update_deck_strategy`/`merge_decks`/`view_deck` tools (not in FR8 — D-1.5g). **No** color-identity recompute on add (D-1.5g). **No** changes to `Deck`/`DeckCard`/`DeckModel`/`DeckCardModel` or any existing repository method (the only behavior addition is `CardRepository.get_by_id`).

### Reuse map — what already exists (DO NOT reinvent)

| Need | Use this | Location |
|---|---|---|
| Create / get / list / delete decks, add / remove deck-cards | `DeckRepository.*` (`create_deck`, `get_deck`, `get_deck_with_cards`, `list_decks`, `delete_deck`, `add_card_to_deck`, `remove_card_from_deck`) | [deck.py](../../src/data/repositories/deck.py) |
| Resolve a card by exact / partial name (the `name` path) | `CardRepository.find_by_name_exact` / `find_by_name_partial` | [card.py:126](../../src/data/repositories/card.py#L126), [card.py:174](../../src/data/repositories/card.py#L174) |
| Lightweight card projection (nested in deck cards + `ambiguous` matches) | `CardSummary` (already added in 1.4 for this reuse) | [schemas/card.py:66](../../src/data/schemas/card.py#L66) |
| Full deck data shape (source for the projections) | `Deck` / `DeckCard` schemas (nest the full `Card`) | [schemas/deck.py](../../src/data/schemas/deck.py) |
| Tool wiring pattern (closure over `session_factory`, `async with`, private-alias helper import) | `search_cards` wrapper + `_search_cards_helper` | [server.py:83](../../src/mcp_server/server.py#L83), [card_search.py:109](../../src/mcp_server/tools/card_search.py#L109) |
| Structured-result-with-`status`+`message` convention + graceful validate-first | `CardSearchResult` / `_validation_error` | [card_search.py:28](../../src/mcp_server/tools/card_search.py#L28), [card_search.py:53](../../src/mcp_server/tools/card_search.py#L53) |
| Exact→partial→ambiguous bucketing (the `name` resolver) | `lookup_card` helper | [card_lookup.py:41](../../src/mcp_server/tools/card_lookup.py#L41) |
| In-memory MCP harness | `create_connected_server_and_client_session` + `build_server(session_factory=...)` | [test_mcp_tools.py:10](../../tests/integration/test_mcp_tools.py#L10) |
| File-backed seeded DB fixture (3 cards, no decks) | `seeded_card_db` | [conftest.py:81](../../tests/integration/conftest.py#L81) |
| Helper-level test pattern (own engine + seeded cards + repo) | `test_deck_repository.py` fixtures | [test_deck_repository.py:13-95](../../tests/integration/data/test_deck_repository.py#L13) |
| Legacy deck tools (logic/wording only — **drop** UI/session/active-deck/legality) | `legacy/agent/tools/deck_tools.py` | [deck_tools.py](../../legacy/agent/tools/deck_tools.py) |

### The deck projections (D-1.5e) — bound the payload, reuse `CardSummary`

The full `Deck` schema nests `deck_cards: list[DeckCard]`, and each `DeckCard.card` is the **full `Card`** (with `legalities`, `image_uris`, `card_faces`). A 60-card deck through `load_deck` would dump ~60 full cards at the LLM — far too heavy. Mirror the 1.4 `CardSummary` decision: add deck projections to `src/data/schemas/deck.py` (reusable by Story 1.6), and build them in the tool helper:

```python
# src/data/schemas/deck.py  (add alongside Deck / DeckCard; import CardSummary)
class DeckCardSummary(BaseModel):
    """Lightweight deck-card entry: quantity + sideboard + a CardSummary."""
    model_config = ConfigDict(from_attributes=True)
    card_id: str
    quantity: int
    sideboard: bool
    card: CardSummary

class DeckSummary(BaseModel):
    """Lightweight deck projection (no card list) for list_decks. Counts computed by the helper."""
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    format: FormatType
    strategy: str | None = None
    color_identity: list[str] = []
    tags: list[str] = []
    mainboard_count: int = 0
    sideboard_count: int = 0
    distinct_cards: int = 0
    created_at: datetime
    updated_at: datetime

class DeckDetail(DeckSummary):     # or a sibling — same metadata + counts
    """Deck metadata + counts + its cards as DeckCardSummary (for create_deck / load_deck)."""
    cards: list[DeckCardSummary] = []
```

```python
# in the deck_management helper — counts are COMPUTED, not model_validate'd
def _deck_summary(deck: Deck) -> DeckSummary:
    main = sum(dc.quantity for dc in deck.deck_cards if not dc.sideboard)
    side = sum(dc.quantity for dc in deck.deck_cards if dc.sideboard)
    return DeckSummary(
        id=deck.id, name=deck.name, format=deck.format, strategy=deck.strategy,
        color_identity=deck.color_identity, tags=deck.tags,
        mainboard_count=main, sideboard_count=side, distinct_cards=len(deck.deck_cards),
        created_at=deck.created_at, updated_at=deck.updated_at,
    )
```

> **Gotcha:** do **not** write `DeckSummary.model_validate(deck)` for the counts — a `Deck` has no `mainboard_count` attribute, so `from_attributes` silently fills the `0` default. Compute counts explicitly. (If you make `DeckDetail` subclass `DeckSummary`, that's fine; just keep building both via explicit constructors.)

### FK enforcement is OFF — pre-validate, or get orphan rows / a ValidationError (AC4)

The async engine ([database.py:30](../../src/data/database.py#L30)) creates a plain `create_async_engine` with **no** `PRAGMA foreign_keys=ON`. SQLite defaults foreign-key enforcement **OFF per connection**, so the `deck_cards` FKs (`deck_id → decks.id`, `card_id → cards.id`) are **not** enforced here. Consequences the tool must defend against:

- **Bogus `deck_id`:** `repo.add_card_to_deck` would happily `INSERT` an **orphan** `deck_cards` row (no FK error, and `DeckCard.model_validate` succeeds because it only needs `deck_id` as a string + the nested card). → **Pre-validate** with `repo.get_deck(deck_id)`; `None` ⇒ `deck_not_found`, write nothing. *(Task 5 asserts no orphan row is created.)*
- **Bogus `card_id`:** the `INSERT` succeeds, but `repo.add_card_to_deck` then re-selects with `selectinload(DeckCardModel.card)` and calls `DeckCard.model_validate(...)`, where `card: Card` is required — a missing card makes `.card` `None` and raises a **`ValidationError`** (ugly, surfaced as a tool error). → **Pre-validate** the card via `_resolve_card` (`get_by_id` / name lookup); missing ⇒ `card_not_found`.

Do **not** "fix" this by enabling `PRAGMA foreign_keys` on the engine — that is a broad, cross-cutting change outside this story's scope and risks altering existing delete/cascade behavior. Localized pre-validation in the tool is the correct, minimal fix.

### `add_card_to_deck` flow (the canonical one)

```
1. exactly one of {card_id, name}? and quantity >= 1?      -> else status="invalid" (+ which rule)
2. deck = DeckRepository(session).get_deck(deck_id)
   if deck is None:                                        -> status="deck_not_found"  (NO row written)
3. card, err, matches = await _resolve_card(card_repo, card_id=card_id, name=name)
   if err == "card_not_found":                             -> status="card_not_found"
   if err == "ambiguous":                                  -> status="ambiguous", matches=[CardSummary...]
4. try:
       await deck_repo.add_card_to_deck(deck_id, card.id, quantity, sideboard)
   except IntegrityError:                                  -> status="exists" (graceful, no upsert)  [D-1.5c]
5. status="ok": "Added {quantity} {copy/copies} of '{card.name}' to the {mainboard|sideboard}."
```

`remove_card_from_deck` is the same shape minus the quantity check: validate exactly-one → `get_deck` (`deck_not_found`) → `_resolve_card` (`card_not_found`/`ambiguous`) → `repo.remove_card_from_deck(...)` returns `bool` (`True`→`ok`, `False`→`not_in_deck`). The repo already does `rollback()` on `DatabaseError`; you only need the `except IntegrityError` on the **add** path.

### `add_card_to_deck` / `remove_card_from_deck` accept `card_id` OR `name` (D-1.5a)

Exactly one is required (both → `invalid`, neither → `invalid`). The `name` path reuses the `lookup_card` bucketing (exact → partial → 0/1/2+) but returns it through `DeckCardResult` (`card_not_found` / `ambiguous` with `matches`). The `card_id` path uses the new `CardRepository.get_by_id`. Keep the resolver in one private `_resolve_card` shared by both add and remove so the behavior is identical.

### Statelessness & "active deck" (FR3 / D5 / D-1.5d)

There is **no** server-side active deck, format filter, or session. The client supplies `deck_id` on every call (it learns ids from `create_deck`/`list_decks`). Everything the legacy tools did via `_session_manager` — `set_active_deck_id`, `set_format_filter`, `sidebar_needs_update`, the `confirmed=` delete handshake, auto-feedback — is **dropped**. `delete_deck` has **no** confirmation flag (the LLM client confirms with the user before calling).

### `create_deck` — deck name is NOT unique (gotcha)

`DeckModel.name` is `index=True` but **NOT** `unique=True` ([deck.py:32](../../src/data/models/deck.py#L32)). The `DeckRepository.create_deck` docstring claims *"Raises IntegrityError: If deck name already exists (UNIQUE constraint)"* — **that is wrong/aspirational**; there is no such constraint. The legacy tool docstring is correct: *"Duplicate deck names are allowed since deck IDs are unique."* So **do not** add duplicate-name detection or expect an `IntegrityError` on create — two decks named "My Deck" coexist, distinguished by `id`. The only realistic `create_deck` failure is a genuine DB-level error (disk, corruption), which the repo already rolls back; validating `name` non-empty in the helper is the only input guard needed.

### Async-def tools + data access (D-1.3a / D-1.4c — the Epic-1 pattern)

`src/data` is async SQLAlchemy + `aiosqlite`. All six deck tools are `async def` and `await` the async `DeckRepository`/`CardRepository` **directly** on FastMCP's event loop — **no** bridge, `asyncio.run()`, thread, or sync `ConnectionFactory`. Keep tool bodies thin: validate → call repo → project to summaries → shape `*Result`. The real work is already in the repository.

### Providing the session factory (closure registration) — mirror `search_cards`

```python
# src/mcp_server/server.py  (add alongside search_cards)
from src.mcp_server.tools.deck_management import (
    DeckCardResult, DeckDeleteResult, DeckListResult, DeckResult,
    add_card_to_deck as _add_card_to_deck_helper,
    create_deck as _create_deck_helper,
    delete_deck as _delete_deck_helper,
    list_decks as _list_decks_helper,
    load_deck as _load_deck_helper,
    remove_card_from_deck as _remove_card_from_deck_helper,
)

    @mcp.tool()
    async def add_card_to_deck(
        deck_id: str,
        card_id: str | None = None,
        name: str | None = None,
        quantity: int = 1,
        sideboard: bool = False,
    ) -> DeckCardResult:
        """Add a card (by card_id OR name) to a deck. ... (LLM-facing description)"""
        async with session_factory() as session:
            return await _add_card_to_deck_helper(
                session, deck_id=deck_id, card_id=card_id, name=name,
                quantity=quantity, sideboard=sideboard,
            )
    # ... five more wrappers, same shape ...
```

`Literal`, `str | None`, `list[str] | None`, `int`, `bool` all serialize cleanly into the FastMCP tool schema (verified in 1.3/1.4). Keep `format`/`name`/`deck_id`/`card_id` param names as the helper exposes them.

### Testing — patterns and traps (carried from Stories 1.3/1.4)

- **Helper tests** (`test_deck_management_tool.py`): own file-backed engine + a single shared `session`, seed cards like [test_deck_repository.py](../../tests/integration/data/test_deck_repository.py#L37). This is where the deep coverage lives. (The repo's `add_card_to_deck` commits then re-selects on the **same** session — fine within one session.)
- **End-to-end harness** (`test_mcp_tools.py`): the seeding session and each tool's `async with session_factory()` are **separate** connections → **must** use the **file-backed** `seeded_card_db` fixture (`:memory:` gives each connection its own empty DB). Build decks **through the tools** (don't seed deck rows; don't edit the shared fixture — 1.3/1.4 tests depend on its exact 3 cards).
- **`list_decks` is known-flaky on order:** it orders by `created_at desc` with **no secondary tie-breaker** ([deck.py:260](../../src/data/repositories/deck.py#L260)); rapidly-created decks tie and SQLite resolves arbitrarily ([deferred-work.md](./deferred-work.md)). **Assert by id / set membership, never strict order.** If `test_list_decks` flakes during the full-suite verify, it is **not** your regression.
- pytest config ([pyproject.toml](../../pyproject.toml)): `asyncio_mode = "auto"` → write `async def test_...`, **no** `@pytest.mark.asyncio`. `tests.*` is exempt from `mypy --strict` but must stay ruff-clean. Layout mirrors `src/`.

### Anti-patterns (do NOT do these)

- ❌ Re-implement deck SQL in the tools — call `DeckRepository`. The tool layer holds **no** SQLAlchemy queries (the only new query is the additive `CardRepository.get_by_id`, which lives in the **repository**, not the tool).
- ❌ Validate Standard-legality / 4-copy / deck-size on add — that is `validate_deck` (Story 1.6). 1.5 add is pure persistence (D-1.5b). Don't import `src/logic` validators.
- ❌ Upsert on duplicate add — return `status="exists"`; do **not** call `update_card_quantity` (D-1.5c).
- ❌ Skip deck/card pre-validation — FK enforcement is OFF; a bogus `deck_id` silently writes an orphan row and a bogus `card_id` raises `ValidationError` on reload (AC4). Pre-validate.
- ❌ Enable `PRAGMA foreign_keys` on the engine to "fix" the above — out of scope, cross-cutting. Pre-validate in the tool instead.
- ❌ Add duplicate-name handling / expect an `IntegrityError` from `create_deck` — `DeckModel.name` is **not** unique.
- ❌ Return full `Deck`/`DeckCard` (nested full `Card`) — return `DeckSummary`/`DeckDetail`/`DeckCardSummary` with `CardSummary` (D-1.5e).
- ❌ `DeckSummary.model_validate(deck)` for the counts — compute `mainboard_count`/`sideboard_count`/`distinct_cards` explicitly.
- ❌ Reintroduce server state — no active-deck, format-filter, session, or `confirmed=` handshake (FR3/D5/D-1.5d). `deck_id` is the only "active deck".
- ❌ Recompute color identity on add, or expose `update_*`/`merge_decks`/`view_deck` (D-1.5g).
- ❌ Surface raw exceptions to the client — every failure path returns a structured `status` + message.
- ❌ Use the sync `ConnectionFactory`/raw `sqlite3` — Epic 2's vector seam. These tools `async def`-await the async repos.
- ❌ Import `legacy.ui.formatters` / `legacy.agent.*` (pulls `pydantic_ai`, absent from the lean core) or return HTML.
- ❌ Edit the shared `seeded_card_db` fixture or assert against a `:memory:` DB across separate sessions in the harness test.
- ❌ `print()` in library code; naive `datetime` (use `datetime.now(UTC)` if you ever stamp a time — though the repo handles timestamps).

### Previous Story Intelligence (Stories 1.1–1.4 — done)

- **1.3** stood up the server skeleton: `build_server(session_factory)` with closure-registered `async def` tools, the `tools/<name>.py` helper + structured-`*Result` convention, the file-backed `seeded_card_db` fixture, and the `create_connected_server_and_client_session` harness. **Reuse all of it.**
- **1.4** added the patterns this story leans on hardest: the **validate-first, never-raise** helper shape (`_validation_error` → `status="invalid"`), the **`CardSummary` projection** (built explicitly here for deck cards + ambiguous matches), the private-alias helper import in `server.py`, the helper-level + harness two-tier test split, and the "additive-only `src/data`, strict scope discipline" ethos. 1.4 also confirmed `Literal`/union param types serialize cleanly and that graceful `empty`/`invalid` paths keep `isError=False`.
- **1.4 review heeded here:** normalize degenerate inputs **before** validating/calling the repo (1.4 caught `rarity=[]` → empty `or_()` and `format=""` → malformed JSON path). For 1.5, the analogue is the exactly-one-of `{card_id, name}` guard and `quantity >= 1` — validate up front so the repo never sees a degenerate call.
- **Known-flaky (out of scope):** `test_deck_repository.py::test_list_decks` ties on `created_at` ordering — intermittent in full-suite runs, passes in isolation ([deferred-work.md](./deferred-work.md)). Don't "fix" it here; just don't assert order in the new tests.
- **Deferred items relevant here:** the repo `updated_at onupdate` lambda doesn't fire via the ORM unit-of-work, and there's no card-`name`/`games` LIKE-escaping — both pre-existing, **out of scope** for 1.5.
- Team patterns to match: thorough Dev Notes, **run-and-capture** verification, strict scope discipline, additive-only data-layer changes.

### Git Intelligence

- HEAD **`0e71117`** "feat: add search_cards MCP tool + CardSummary projection (Story 1.4)" — the **baseline** for 1.5 (working tree clean). Branch `feat/mcp-server-architecture`; **Conventional Commits**, one focused `feat:`/`fix:` per story.
- Recent cadence (`0e71117` 1.4 · `d2e7d32` 1.3 · `02d8d40` 1.1+1.2 close · `4a77364` ConnectionFactory · `e73fa7b` restructure) confirms: scope-disciplined, additive, test-backed. Suggested message: `feat: add deck-management MCP tools + deck projections + CardRepository.get_by_id (Story 1.5)`.

### Latest Tech / Versions (verified during Stories 1.3/1.4 — reconfirm only if something breaks)

| Item | Value | Source / Action |
|---|---|---|
| MCP SDK | installed **`mcp 1.28.0`** (pin `mcp>=1.27.0`) | [pyproject.toml](../../pyproject.toml) |
| Server / tool API | `from mcp.server.fastmcp import FastMCP`; `@mcp.tool()`; `async def` tools awaited on the server loop | in use ([server.py](../../src/mcp_server/server.py)) |
| Structured output | typed/Pydantic return → `CallToolResult.structuredContent` (the model dict); `isError=False` on graceful `not_found`/`invalid`/`empty`/`ambiguous` paths | verified 1.3/1.4 |
| In-memory client | `mcp.shared.memory.create_connected_server_and_client_session(server)` (accepts a `FastMCP`) | in use ([test_mcp_tools.py:10](../../tests/integration/test_mcp_tools.py#L10)) |
| Param typing | `str`, `int`, `bool`, `list[str] | None`, `str | None` serialize into the tool schema | matches `search_cards` |

> No new dependency is needed.

### Project Structure Notes

Target additions/edits (everything else unchanged):

```
src/
  data/
    schemas/deck.py             # MODIFIED — additive DeckSummary / DeckCardSummary / DeckDetail (pure, no behavior)
    repositories/card.py        # MODIFIED — additive read-only get_by_id (the only data-layer behavior change)
  mcp_server/
    server.py                   # MODIFIED — register 6 async deck tools (closures over session_factory)
    tools/deck_management.py    # NEW — 6 helpers + 4 *Result schemas + _resolve_card/_deck_* builders
tests/
  unit/
    data/test_card_repository.py        # MODIFIED — get_by_id found / not-found coverage
  integration/
    mcp_server/test_deck_management_tool.py  # NEW — helper-level CRUD / resolution / projection / orphan-guard coverage
    test_mcp_tools.py                        # MODIFIED — end-to-end deck lifecycle via the in-memory MCP client
```

- **Alignment:** matches spec §4 (`src/mcp_server` = server + tools; tools import core repositories directly) and §5 (`list_decks`/`create_deck`/`load_deck`/`delete_deck`/`add_card_to_deck`/`remove_card_from_deck` = FR8). Import direction stays `data → mcp_server` (no upward imports). Projection schemas stay in `src/data/schemas` per the layer contract. [Source: [design spec §4/§5](../../docs/architecture.md)]
- **Variances to record (Dev Agent Record):** (a) the six tools return **lightweight deck projections** (`DeckSummary`/`DeckDetail`) not the full `Deck` — D-1.5e; (b) add/remove accept **`card_id` OR `name`** — D-1.5a; (c) **`CardRepository.get_by_id`** is added (the one additive data-layer behavior) to enable graceful card pre-validation under FK-off — D-1.5f; (d) **no** construction-rule validation, color-identity recompute, quantity-update, or delete-confirmation — deferred/dropped per D-1.5b/d/g; (e) the misleading `create_deck` "UNIQUE constraint" docstring is **not** relied on (deck names aren't unique).

### References

- [epics.md — Epic 1 / Story 1.5](../planning-artifacts/epics.md) — user story + ACs (FR8, FR3, NFR6).
- [design spec §4 / §5 / §8](../../docs/architecture.md) — tool catalog, statelessness (D5), in-process MCP test approach.
- [project-context.md](../project-context.md) — MCP rules (structured returns, wrap repositories, sync-vs-async, `format`-as-param), schema-layer contract (repos return schemas not ORM), testing layout, ruff/mypy gates, `report_bug`/user-input-untrusted note.
- [src/data/repositories/deck.py](../../src/data/repositories/deck.py) — the methods to wrap. [src/data/repositories/card.py](../../src/data/repositories/card.py) — `find_by_name_*` + where `get_by_id` is added. [src/data/schemas/deck.py](../../src/data/schemas/deck.py) — `Deck`/`DeckCard` (add projections here). [src/data/schemas/card.py:66](../../src/data/schemas/card.py#L66) — `CardSummary` (reuse). [src/data/database.py:30](../../src/data/database.py#L30) — async engine (FK enforcement OFF). [src/data/models/deck.py:32](../../src/data/models/deck.py#L32) / [deck_card.py](../../src/data/models/deck_card.py) — non-unique name, composite-PK.
- [src/mcp_server/server.py](../../src/mcp_server/server.py) / [tools/card_search.py](../../src/mcp_server/tools/card_search.py) / [tools/card_lookup.py](../../src/mcp_server/tools/card_lookup.py) — the exact wrapper/helper/result + name-resolution patterns to mirror.
- [legacy/agent/tools/deck_tools.py](../../legacy/agent/tools/deck_tools.py) — source behavior to port (logic/wording only; **drop** UI/session/active-deck/legality/confirmation).
- [tests/integration/test_mcp_tools.py](../../tests/integration/test_mcp_tools.py) / [mcp_server/test_card_search_tool.py](../../tests/integration/mcp_server/test_card_search_tool.py) / [data/test_deck_repository.py](../../tests/integration/data/test_deck_repository.py) / [conftest.py](../../tests/integration/conftest.py) — harness, helper-test, deck-seed, and fixture patterns.
- [Story 1.4](./1-4-advanced-card-search-tool.md) — `CardSummary`, validate-first helper, private-alias import, two-tier tests, review patches. [deferred-work.md](./deferred-work.md) — `list_decks` flaky-order note.

## Dev Agent Record

### Agent Model Used

claude-opus-4-8[1m] (Claude Opus 4.8, 1M context) — BMad Dev Story workflow.

### Debug Log References

- TDD red gate (Task 2): `CardRepository.get_by_id` tests failed first with `AttributeError: 'CardRepository' object has no attribute 'get_by_id'`, then passed after the additive read-only method was added.
- Verification (Task 7): `uv run pytest tests/` → **388 passed** (the known-flaky `test_deck_repository.py::test_list_decks` — `created_at` tie, [deferred-work.md](./deferred-work.md) — passed this run; no new failures). `uv run mypy src/` → clean (39 files). `uv run ruff check`/`format --check` → all Story-1.5 files clean (pre-existing format drift in unrelated files `_bmad/scripts/*`, `src/mcp_server/tools/card_lookup.py`, and a pre-existing `test_entry_point.py` lint nit were left untouched — out of scope).

### Completion Notes List

- **Six deck tools (FR8)** registered in `build_server` as `async def` closures over `session_factory` (mirrors the `search_cards`/`_search_cards_helper` wiring): `list_decks`, `create_deck`, `load_deck`, `delete_deck`, `add_card_to_deck`, `remove_card_from_deck`. Each opens `async with session_factory()` and delegates to a thin helper in `src/mcp_server/tools/deck_management.py`; the tools hold **no SQL** — they wrap `DeckRepository` 1:1 and project to lightweight summaries.
- **Lightweight deck projections (D-1.5e):** added `DeckCardSummary`, `DeckSummary`, and `DeckDetail(DeckSummary)` to `src/data/schemas/deck.py`, reusing the existing `CardSummary`. Counts (`mainboard_count`/`sideboard_count`/`distinct_cards`) are **computed by helper builders** (`_deck_summary`/`_deck_detail`), never `model_validate`'d (a source `Deck` has no count attributes). `Deck`/`DeckCard`/`DeckModel`/`DeckCardModel` are untouched.
- **`card_id` OR `name` (D-1.5a):** add/remove share one `_resolve_card` helper — `card_id` → `CardRepository.get_by_id`; `name` → exact→partial bucketing returning `card_not_found` / single hit / `ambiguous` (matches as `CardSummary`, capped at 10). Exactly-one-of is validated up front (both/neither → `invalid`), blank strings normalized to `None`, and `quantity >= 1` enforced (the 1.4 "normalize-degenerate-inputs-first" lesson).
- **FK-off pre-validation (AC4):** because the async engine has no `PRAGMA foreign_keys=ON`, add/remove pre-validate the deck via `get_deck` (bogus `deck_id` → `deck_not_found`, **no orphan row** — asserted) and the card via `_resolve_card` (bogus `card_id` → `card_not_found`, avoiding the post-insert `ValidationError`). Duplicate add is caught as `IntegrityError` → `status="exists"` (graceful, **no upsert**, D-1.5c).
- **Statelessness & pure CRUD (AC3, D5/D-1.5b/d/g):** no server-side active-deck/format-filter/session, no delete-confirmation handshake, no Standard-legality/4-copy/deck-size validation (deferred to Story 1.6 `validate_deck`), no color-identity recompute, no `update_*`/`merge`/`view_deck` tools. Legacy `src/logic` validators stay unused.
- **Tests:** 31 helper-level integration tests (`test_deck_management_tool.py`, file-backed engine + shared session) cover full CRUD, all resolution buckets, every graceful status, the orphan guard, and the lightweight-projection types/heavy-key omission; 2 end-to-end harness tests (`test_mcp_tools.py`) drive the full lifecycle through the in-process MCP client (no subprocess) + a `deck_not_found` smoke; 2 unit tests for `get_by_id`. `list_decks` assertions use id/set membership, never order (the known `created_at`-tie flake).
- **Variances recorded (per Project Structure Notes):** (a) tools return lightweight `DeckSummary`/`DeckDetail` not full `Deck` (D-1.5e); (b) add/remove accept `card_id` OR `name` (D-1.5a); (c) the single additive data-layer behavior is read-only `CardRepository.get_by_id` (D-1.5f); (d) no construction-rule validation / color-identity recompute / quantity-update / delete-confirmation (D-1.5b/d/g); (e) the misleading `DeckRepository.create_deck` "UNIQUE constraint" docstring is **not** relied on — deck names are not unique, so no duplicate-name handling.

### File List

- `src/data/schemas/deck.py` — MODIFIED: import `CardSummary`; add additive `DeckCardSummary` / `DeckSummary` / `DeckDetail` projections (pure schemas; `Deck`/`DeckCard` unchanged).
- `src/data/repositories/card.py` — MODIFIED: add additive read-only `get_by_id(card_id) -> Card | None` (the only data-layer behavior change).
- `src/mcp_server/tools/deck_management.py` — NEW: 6 helpers + 4 `*Result` schemas + `_resolve_card` / `_deck_summary` / `_deck_detail` / `_selector_error` / `_blank_to_none` builders.
- `src/mcp_server/server.py` — MODIFIED: import the helpers (private aliases) + result schemas; register the 6 `@mcp.tool()` async wrappers; refresh the `build_server` docstring.
- `tests/unit/data/test_card_repository.py` — MODIFIED: `TestGetById` (found / bogus-id coverage).
- `tests/integration/mcp_server/test_deck_management_tool.py` — NEW: 31 helper-level CRUD / resolution / projection / orphan-guard tests.
- `tests/integration/test_mcp_tools.py` — MODIFIED: end-to-end deck lifecycle through the in-memory MCP client + `deck_not_found` smoke.

### Review Findings

> Source: code review run 2026-06-20. Blind Hunter · Edge Case Hunter · Acceptance Auditor. 14 dismissed as noise.

- [x] [Review][Patch] `distinct_cards` counts `(card_id, sideboard)` rows, not unique card IDs [`src/mcp_server/tools/deck_management.py:_deck_summary, _deck_detail`] — `len(deck.deck_cards)` counts association rows; a card added to both mainboard and sideboard gives `distinct_cards=2` for one card. Fix: `len({dc.card_id for dc in deck.deck_cards})`.
- [x] [Review][Patch] Dead-code unreachable branch in `_resolve_card` [`src/mcp_server/tools/deck_management.py:_resolve_card`] — `if name is None: return None, "card_not_found", []` is unreachable: `_selector_error` already guarantees exactly one selector is set before this helper is called. Remove the branch; it masks future contract violations with a misleading status.
- [x] [Review][Patch] `create_deck` does not normalize `format` with `_blank_to_none` [`src/mcp_server/tools/deck_management.py:create_deck`] — Blank `format=""` or `"  "` is passed raw to `repo.create_deck`, storing an invalid format value. Inconsistent with how `list_decks` normalizes `format`. Fix: apply `_blank_to_none` and fall back to `"standard"` if None.
- [x] [Review][Patch] Task 6 harness test missing assertion that `card_faces` is absent from nested card summaries [`tests/integration/test_mcp_tools.py:test_deck_lifecycle_through_client`] — AC5 / spec anti-pattern list prohibit `legalities`/`image_uris`/`card_faces` in DeckCardSummary.card. The test checks `legalities` and `image_uris` but not `card_faces`. Add `assert "card_faces" not in nested_card`.
- [x] [Review][Patch] `DatabaseError` not caught at tool-helper layer for 5 of 6 helpers [`src/mcp_server/tools/deck_management.py`] — `create_deck`, `list_decks`, `load_deck`, `delete_deck`, `remove_card_from_deck` have no try/except around their repo calls. A disk-full or connection error surfaces as a raw unhandled exception rather than a structured `status`+message. Project context: "tool/UI layer converts [DB exceptions] to user-facing messages." Only `add_card_to_deck` has an `except IntegrityError`.
- [x] [Review][Patch] `deck_id` not normalized with `_blank_to_none` [`src/mcp_server/tools/deck_management.py:add_card_to_deck, remove_card_from_deck`] — `card_id` and `name` are normalized at the top of both helpers; `deck_id` is not. A whitespace-only `deck_id` proceeds to repo lookup and returns `deck_not_found` with message `"No deck found with id '   '."`. Minor inconsistency with the blank-normalization discipline applied elsewhere.

- [x] [Review][Defer] `DeckSummary.from_attributes=True` footgun [`src/data/schemas/deck.py:DeckSummary, DeckDetail`] — deferred, documented design limitation; `DeckSummary.model_validate(deck)` would silently give zero counts (no `mainboard_count` on `Deck`). Docstring warns; helpers always use explicit constructors. Could remove `from_attributes=True` from `DeckSummary`/`DeckDetail` (only `DeckCardSummary` actually needs it), but risk/reward favours leaving for now.
- [x] [Review][Defer] `CardSummary.model_validate(dc.card)` where `dc.card` is a Pydantic `Card`, not an ORM model [`src/mcp_server/tools/deck_management.py:_deck_detail`] — deferred, works in Pydantic v2 via attribute inspection; fragile but functional. A more explicit pattern (`CardSummary(**dc.card.model_dump())`) is safer but out of Story 1.5 scope.
- [x] [Review][Defer] Non-deterministic card ordering in `_deck_detail` [`src/mcp_server/tools/deck_management.py:_deck_detail`] — deferred, depends on `DeckRepository.get_deck_with_cards` sort order not visible in this diff. If the repo returns cards in non-deterministic order, `load_deck` response card order is unstable. Address in a future story when consistent card ordering matters.
- [x] [Review][Defer] `not_in_deck` message does not hint card exists in the other sideboard/mainboard location [`src/mcp_server/tools/deck_management.py:remove_card_from_deck`] — deferred, UX improvement. Removing a mainboard card when it's in the sideboard returns `"... is not in the mainboard"` with no hint. Improve messaging in a future polish story.
- [x] [Review][Defer] `_deck_detail` crashes if `dc.card` is `None` after FK-off orphan insert + card deletion [`src/mcp_server/tools/deck_management.py:_deck_detail`] — deferred, pre-existing FK-off risk; `CardSummary.model_validate(None)` raises. Defended in practice by the add-path pre-validation (AC4), but not structurally guaranteed. Covered by the broader FK-enforcement-off risk noted in project context.
- [x] [Review][Defer] No `format` string validation in `create_deck` (any string accepted) [`src/mcp_server/tools/deck_management.py:create_deck`] — deferred, by design per D-1.5b (validation deferred to Story 1.6). Invalid formats are stored silently; `list_decks(format="potato")` would return an empty result rather than an error.

## Change Log

| Date | Change |
|---|---|
| 2026-06-20 | Created Story 1.5 (Deck Management Tools). Locked 7 decisions with Brad (card_id-OR-name, pure-CRUD/defer-validation, graceful-duplicate, deck_id-only load/delete, lightweight deck projections, additive `get_by_id`, color-identity/quantity-update out of scope). Status → ready-for-dev. |
| 2026-06-20 | Implemented Story 1.5: 6 deck-management MCP tools + `DeckSummary`/`DeckCardSummary`/`DeckDetail` projections + additive `CardRepository.get_by_id`. Added 35 tests (31 helper + 2 harness + 2 unit). Full suite 388 passed; mypy + ruff (Story-1.5 files) clean. Status → review. |
