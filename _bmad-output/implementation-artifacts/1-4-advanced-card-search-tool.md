---
baseline_commit: 02d8d40
---

# Story 1.4: Advanced Card Search Tool

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a player using Claude Code,
I want to search cards by relational filters (colors, type, mana value, rarity, format-legality) with format/games passed per call,
so that I can find Standard-legal cards matching color/type/mana criteria without any server-side state.

## Decisions Locked (resolved with Brad, 2026-06-20)

> These resolve the open forks before the story was finalized. They shape the ACs/Tasks below — **do not re-litigate**.
>
> - **D-1.4a — `search_cards` wraps the existing `CardRepository.search_advanced` 1:1.** The tool contains **no SQL**; it validates inputs, calls `search_advanced(...)`, and shapes a structured result. This is the established Epic-1 pattern ("tools wrap the existing repositories directly").
> - **D-1.4b — NO "set" filter (Brad: "no need for Set parameter at this time").** The epic AC lists `set`, but it is **out of scope** for this story and **not** implemented. Consequence: **`search_advanced` is NOT modified** — there is **zero change to `src/data/repositories`**. (A future story can add an additive `set_code` filter if needed.)
> - **D-1.4c — Repo-backed tool is `async def` (carries D-1.3a).** `search_cards` is an `async def` `@mcp.tool()` that `await`s the async repo directly on the FastMCP loop. The sync `def` + `ConnectionFactory` model remains **reserved for Epic 2** vector tools.
> - **D-1.4d — Statelessness, no pagination cursor (FR3/D5).** `format`, `games`, and `page`/`page_size` are **tool parameters**; **no** `search_context`/`session_id`/active-deck state is stored server-side (the legacy `_session_manager.set_search_context` behavior is **dropped**). "Next page" = the client calls again with `page+1`.
> - **D-1.4e — Results use a NEW lightweight `CardSummary` schema (Brad-confirmed).** Search returns up to 50 cards/page, so a full `Card` payload (with `legalities`, `image_uris`, `card_faces`) is too heavy for the LLM client. There is **no existing summary schema today** (the only card schema is the full `Card`; `DeckCard` even nests the full `Card`), so this story **adds** `CardSummary` to `src/data/schemas/card.py`. It **keeps `oracle_text`** (needed for relevance) and **drops** `legalities`, `image_uris`, `card_faces`. Field set: `id, name, mana_cost, cmc, type_line, oracle_text, colors, rarity, set_code`. The client calls `lookup_card_by_name` for full detail on a chosen card. This `CardSummary` is intended for reuse by later list-returning tools (Story 1.5 deck listings, Epic 2 semantic search).

## Acceptance Criteria

> Source: [epics.md#Story-1.4](../planning-artifacts/epics.md) (BDD as authored), with the locked decisions above and implementation-critical clarifications folded in. **All five must hold simultaneously.** This story adds the **third Epic-1 tool** on top of the Story-1.3 server skeleton; it reuses the server builder, the closure-injected session factory, and the in-memory harness already in place.

**AC1 — `search_cards` returns matching cards via the existing repository query (FR5)**
- **Given** `search_cards` with any combination of filters (colors + `color_mode`, types, keywords, oracle-text phrases, mana-value min/max, rarity, format-legality)
- **When** invoked
- **Then** it returns **structured** matching cards (a list of `CardSummary` schemas + pagination metadata) by reusing `CardRepository.search_advanced(...)`, awaited directly (D-1.4a, D-1.4c) — **no SQL re-implemented in the tool** (FR5)
- **And** results are bounded to one page and reflect the repo's sort order (mana value, then name).

**AC2 — `format` & `games` are per-call parameters; no server state persists (FR3, D5)**
- **Given** `format` and `games` passed as tool parameters
- **When** invoked
- **Then** they filter results (format-legality via `legalities.{format} == "legal"`; games via availability)
- **And** **no** format/games/search-context state persists on the server between calls — a subsequent call with different params is unaffected by a prior call (FR3, D-1.4d).

**AC3 — Over-broad results are bounded and the bound is communicated clearly**
- **Given** a query whose total matches exceed one page
- **When** returned
- **Then** the result is limited to `page_size` items (default 20, capped at 50) and **clearly reports** `total_count`, `page`, `total_pages`, and how to get more (call again with the next `page`) in the human-facing `message`
- **And** a no-match query returns a graceful **empty** result (status `empty`) with a helpful "relax/adjust filters" message — **not** an exception.

**AC4 — Invalid filter values return a clear validation message rather than raising**
- **Given** an invalid filter value (e.g. a color code outside `W/U/B/R/G`, an unknown `rarity`, a game outside `paper/arena/mtgo`, `mana_value_min > mana_value_max`, or `page`/`page_size` < 1)
- **When** invoked
- **Then** the tool returns a structured result with status `invalid` and a message naming the bad value — **no raw exception is surfaced** to the MCP client.
- *(Note: `color_mode` is a `Literal` and is validated at the MCP boundary; the free-form filters above are validated inside the helper so the failure is graceful and unit-testable.)*

**AC5 — In-memory MCP client harness drives filter combinations (no subprocess)**
- **Given** the in-process MCP client harness against a seeded test DB
- **When** it drives `search_cards` across filter combinations (single filter, multi-filter AND, `color_mode` variants, format filter, pagination, empty, invalid)
- **Then** integration assertions pass **without spawning a subprocess** (spec §8), reusing the Story-1.3 wiring (`build_server(session_factory=...)` + `create_connected_server_and_client_session`).

## Tasks / Subtasks

- [x] **Task 1 — `CardSummary` schema** (AC: 1) — *additive, pure schema; the only `src/data` change*
  - [x] In [src/data/schemas/card.py](../../src/data/schemas/card.py) add `class CardSummary(BaseModel)` with `model_config = ConfigDict(from_attributes=True)` and fields: `id: str`, `name: str`, `mana_cost: str`, `cmc: float`, `type_line: str`, `oracle_text: str`, `colors: list[str]`, `rarity: str`, `set_code: str`. (Subset of `Card`; **keeps `oracle_text`**, **drops** `legalities`/`image_uris`/`card_faces` and the other detail fields. `from_attributes=True` ⇒ `CardSummary.model_validate(card)` works directly from a `Card`.) Google-style class docstring noting it is the lightweight projection for list-returning tools; `set_name` may be added later if display needs it.
  - [x] Add a small unit test (`tests/unit/data/test_card_schema.py` or mirror existing schema-test layout) asserting `CardSummary.model_validate(<a full Card>)` populates the kept fields and the type round-trips. (`tests.*` is mypy-exempt but stays ruff-clean.)
  - [x] **Do NOT** modify `Card`, `CardModel`, `search_advanced`, or any repository. This task adds a schema and nothing else.
- [x] **Task 2 — `search_cards` tool helper + result schema** (AC: 1, 2, 3, 4) — *mirror [card_lookup.py](../../src/mcp_server/tools/card_lookup.py)*
  - [x] `src/mcp_server/tools/card_search.py` — module docstring (purpose, "wraps `search_advanced`, returns `CardSummary`, drops UI/session" note like `card_lookup.py`).
  - [x] Define `class CardSearchResult(BaseModel)` with: `status: Literal["ok", "empty", "invalid"]`; `cards: list[CardSummary] = []`; `total_count: int = 0`; `page: int = 1`; `page_size: int = 20`; `total_pages: int = 0`; `message: str`. Google-style docstring on the class.
  - [x] `async def search_cards(session, *, colors=None, color_mode="any", types=None, keywords=None, oracle_text=None, mana_value_min=None, mana_value_max=None, rarity=None, format=None, games=None, page=1, page_size=20) -> CardSearchResult`. Signature mirrors the legacy `CardSearchFilters` field set (minus `set`/`max_results`); `color_mode: Literal["any","all","exact","at_most"]`.
  - [x] **Validate first (AC4)** — return `status="invalid"` + a specific message (no raise) when: any `colors` entry ∉ `{"W","U","B","R","G"}`; any `rarity` ∉ `{common,uncommon,rare,mythic,special,bonus}` (case-insensitive); any `games` entry ∉ `{paper,arena,mtgo}`; `mana_value_min`/`mana_value_max` < 0; `mana_value_min > mana_value_max`; `page < 1` or `page_size < 1`.
  - [x] **Then call the repo** — `repo = CardRepository(session)`; `result = await repo.search_advanced(colors=colors, types=types, keywords=keywords, oracle_text_phrases=oracle_text, mana_value_min=..., mana_value_max=..., rarity=rarity, page=page, page_size=page_size, format_filter=format, games=games, color_mode=color_mode)`. **Map tool param `oracle_text` → repo param `oracle_text_phrases`.** (No `set_code` argument — D-1.4b.)
  - [x] **Shape the result (AC3)** — convert each `result.items` (`Card`) → `CardSummary.model_validate(card)`. Empty `result.items` ⇒ `status="empty"` + a "no cards matched; try relaxing/adjusting filters" message. Otherwise `status="ok"`; build a `message` reporting `total_count`, `page`/`total_pages`, the displayed range, and (when `page < total_pages`) "call again with page={page+1} for more". Populate `cards`/counts from the `PaginatedResult`.
  - [x] Google-style docstring on `search_cards` = **the LLM-facing tool description**: summarize each filter, AND-logic across filters, the four `color_mode` semantics (any/all/exact/at_most), statelessness, pagination, and that results are summaries (use `lookup_card_by_name` for full detail). Condense from the legacy `card_search.py` docstrings — **do not** copy the HTML/formatting/“say next page” conversational bits.
- [x] **Task 3 — Register the tool in `build_server`** (AC: 1, 2, 5) — *closure registration, transport-agnostic*
  - [x] In [src/mcp_server/server.py](../../src/mcp_server/server.py) add a third `@mcp.tool()` `async def search_cards(...)` wrapper that closes over `session_factory`, opens `async with session_factory() as session:`, and delegates to the `search_cards` helper. Mirror the existing `lookup_card_by_name`/`report_bug` wrappers exactly (param surface = the helper's; keep `format` as a param name — project convention, ruff `N` intentionally allows it).
  - [x] Import `CardSearchResult` + the `search_cards` helper from `src.mcp_server.tools.card_search` (avoid the wrapper/helper name clash — e.g. import the helper under a private alias). **No** change to `__main__.py`, `.mcp.json`, transport selection, or `src/mcp_server/__init__.py`.
- [x] **Task 4 — Helper-level integration tests** (AC: 1, 2, 3, 4) — *mirror [test_card_lookup_tool.py](../../tests/integration/mcp_server/test_card_lookup_tool.py)*
  - [x] `tests/integration/mcp_server/test_card_search_tool.py` — own in-memory engine + a **richer** seed (≥ ~25 cards spanning colors W/U/B/R/G + multicolor + colorless, multiple types, a range of `cmc`, ≥2 rarities, and ≥2 formats) so pagination, `color_mode`, rarity, and format filters are all meaningfully exercised. Use the `_card(...)` builder + in-memory engine/session fixture pattern from `test_card_lookup_tool.py`. (Direct-helper tests share **one** session, so `:memory:` is fine here.)
  - [x] Cover: single-filter (colors), multi-filter AND (colors+types+mana_value_max), each `color_mode` (`any`/`all`/`exact`/`at_most`), `rarity` (single + list), `format` filter excludes non-legal, **pagination** (page 1 vs page 2 with small `page_size`; assert `total_count`/`total_pages`/`page`), **empty** (status `empty`), and **invalid** (bad color, bad rarity, bad game, `min>max`, `page<1` → status `invalid`, no raise). Assert returned items are `CardSummary` (e.g. no `legalities`/`image_uris` keys in `structuredContent`'s cards at the harness level; at the helper level assert the type/fields).
- [x] **Task 5 — End-to-end MCP harness test** (AC: 5) — *extend [test_mcp_tools.py](../../tests/integration/test_mcp_tools.py)*
  - [x] Add `search_cards` test(s) to `tests/integration/test_mcp_tools.py` using the shared **file-backed** `seeded_card_db` fixture (separate sessions → must be file-backed, see Dev Notes). Drive via `create_connected_server_and_client_session(build_server(session_factory=seeded_card_db))`; assert `result.isError is False`, `result.structuredContent["status"]`, and `structuredContent["cards"]` contents (e.g. `colors=["R"]` ⇒ Lightning Bolt + Thunderbolt; `format="standard"` ⇒ excludes Thunderbolt).
  - [x] The current `seeded_card_db` ([conftest.py](../../tests/integration/conftest.py)) has 3 cards (Lightning Bolt R/cmc1/standard+modern, Thunderbolt R/cmc3/modern, Counterspell U/cmc2/standard+modern) — enough for an end-to-end smoke. Keep deep coverage in Task 4; keep this a smoke test. **Avoid** editing the shared fixture (Story-1.3 tests depend on its exact contents); if you truly need more rows here, **additively** widen `_sample_cards()` without removing existing cards.
- [x] **Task 6 — Verify (run the commands, capture output)** (AC: all)
  - [x] `uv run pytest tests/integration/test_mcp_tools.py tests/integration/mcp_server/test_card_search_tool.py -v` → new tests pass.
  - [x] `uv run pytest tests/` → full suite green except the **known-flaky** `test_list_decks` family (`created_at` tie; passes in isolation — see Previous Story Intelligence). Confirm no **new** failures.
  - [x] `uv run ruff check .` / `uv run ruff format --check .` → all Story-1.4 files clean. (Pre-existing findings in `_bmad/scripts/tests/...` are out of scope.)
  - [x] `uv run mypy src/` → clean.
  - [x] Optional smoke: confirm `search_cards` registers on `build_server()` (the harness test in Task 5 is the authoritative check; FastMCP `list_tools()` is async if you probe it directly).

## Dev Notes

### What this story IS — and is NOT

- **IS:** the **third Epic-1 tool** — a `search_cards` `async def` `@mcp.tool()` that wraps the **existing** `CardRepository.search_advanced`, returns a structured `CardSearchResult` of lightweight `CardSummary` rows, validates inputs gracefully, and is stateless (format/games/page are params). Plus one **additive, pure** `CardSummary` schema, and integration tests (helper-level + in-memory MCP harness).
- **IS NOT:** deck tools (1.5), analysis tools (1.6), or **anything RAG/semantic** (Epic 2 — no `Embedder`, `card_vec`, `semantic_search_cards`, or use of the sync `ConnectionFactory`). **Do not** scaffold ahead. **No** "set" filter (D-1.4b). **No** changes to `Card`, `CardModel`, `search_advanced`/any repository, the async engine, or the server entry point/`.mcp.json`/transport. The **only** `src/data` change is the additive `CardSummary` schema.

### Reuse map — what already exists (DO NOT reinvent)

| Need | Use this | Location |
|---|---|---|
| Advanced relational search (colors/types/keywords/oracle-text/mana/rarity, format/games, pagination, `color_mode`) | `CardRepository.search_advanced(...)` → `PaginatedResult[Card]` | [card.py:346](../../src/data/repositories/card.py#L346) |
| Full card data shape (source for the summary projection) | `Card` schema | [schemas/card.py](../../src/data/schemas/card.py) |
| Pagination metadata shape | `PaginatedResult[Card]` (`items, total_count, page, page_size, total_pages`) | [schemas/pagination.py](../../src/data/schemas/pagination.py) |
| Tool wiring pattern (closure over `session_factory`, `async with`) | `lookup_card_by_name` wrapper + `lookup_card` helper | [server.py:38](../../src/mcp_server/server.py#L38), [card_lookup.py:41](../../src/mcp_server/tools/card_lookup.py#L41) |
| Structured-result-with-message convention | `CardLookupResult` / `BugReportResult` | [card_lookup.py:24](../../src/mcp_server/tools/card_lookup.py#L24), [bug_report.py:20](../../src/mcp_server/tools/bug_report.py#L20) |
| In-memory MCP harness | `create_connected_server_and_client_session` + `build_server(session_factory=...)` | [test_mcp_tools.py:10](../../tests/integration/test_mcp_tools.py#L10) |
| File-backed seeded DB fixture | `seeded_card_db` | [conftest.py:81](../../tests/integration/conftest.py#L81) |
| Helper-level test pattern (own engine + seed) | `test_card_lookup_tool.py` | [test_card_lookup_tool.py](../../tests/integration/mcp_server/test_card_lookup_tool.py) |
| Logic to port (filter set, `color_mode` semantics) — **logic/wording only, drop UI** | legacy `CardSearchFilters` / `search_cards_advanced` | [legacy/agent/tools/card_search.py](../../legacy/agent/tools/card_search.py) |

### `CardSummary` — the lightweight result projection (D-1.4e)

There is **no** summary schema today — `Card` is the only card schema and `DeckCard` nests the **full** `Card`. Add `CardSummary` to `src/data/schemas/card.py` (next to `Card`) so it's reusable by Story 1.5 (deck listings) and Epic 2 (semantic results). With `model_config = ConfigDict(from_attributes=True)`, the helper builds each summary straight from a repo-returned `Card`:

```python
# src/data/schemas/card.py  (add alongside Card)
class CardSummary(BaseModel):
    """Lightweight card projection for list-returning tools (search, etc.).

    Keeps oracle_text for relevance; omits the heavy fields (legalities,
    image_uris, card_faces). Use lookup_card_by_name for full detail.
    """
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    mana_cost: str
    cmc: float
    type_line: str
    oracle_text: str
    colors: list[str]
    rarity: str
    set_code: str
```

```python
# in the search_cards helper
cards = [CardSummary.model_validate(c) for c in result.items]
```

This keeps the search payload small even at `page_size=50`, while `lookup_card_by_name` still returns the full `Card`.

### Async-def tools + data access (D-1.3a / D-1.4c — the Epic-1 pattern)

`src/data` is **async** SQLAlchemy + `aiosqlite`. `search_cards` is an `async def` tool that `await`s `search_advanced` **directly** on FastMCP's event loop — **no** bridge, `asyncio.run()`, background thread, or sync `ConnectionFactory`. `aiosqlite` is non-blocking, so it won't stall the loop. Keep the tool body thin (validate → call repo → project to summaries → shape result); the real query work is already in `search_advanced`.

### Providing the session factory (closure registration)

Register inside `build_server` so each server binds its own factory (test-injectable). Mirror the existing wrappers:

```python
# src/mcp_server/server.py  (add alongside lookup_card_by_name / report_bug)
from src.mcp_server.tools.card_search import CardSearchResult
from src.mcp_server.tools.card_search import search_cards as _search_cards_helper

    @mcp.tool()
    async def search_cards(
        colors: list[str] | None = None,
        color_mode: Literal["any", "all", "exact", "at_most"] = "any",
        types: list[str] | None = None,
        keywords: list[str] | None = None,
        oracle_text: list[str] | None = None,
        mana_value_min: float | None = None,
        mana_value_max: float | None = None,
        rarity: str | list[str] | None = None,
        format: str | None = None,        # kept as a param name by project convention (ruff N allowed)
        games: list[str] | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> CardSearchResult:
        """Search MTG cards by relational filters ... (LLM-facing description)"""
        async with session_factory() as session:
            return await _search_cards_helper(session, colors=colors, color_mode=color_mode, ...)
```

- Keep the matching/validation logic in the `tools/card_search.py` helper that takes a `session` (unit-testable); the registered tool is a thin wrapper closing over `session_factory`.
- `Literal` is in the SDK's supported param-type set; FastMCP turns it into an enum in the tool schema. Keep `color_mode` as a `Literal` (boundary-validated); validate the free-form filters in the helper (AC4).

### `search_cards` — port the logic, drop the UI/session

From legacy [card_search.py](../../legacy/agent/tools/card_search.py): **keep** the filter set + the four `color_mode` semantics (the docstring there is the canonical explanation — condense it). **Drop**: `RunContext`/`AgentDependencies`, `format_card_list`/`format_card_with_image`/`format_mana_symbols`, `ui_elements`, the `auto_filter` + session `format_filter`/`games_filter` (now explicit `format`/`games` params, default `None` = no filter — FR3/D5), the `_session_manager.set_search_context` pagination cursor (stateless — D-1.4d), and the `max_results` deprecated alias (new tool, no back-compat baggage — use `page`/`page_size`). Return **structured** `CardSummary`s, never HTML.

### Statelessness & pagination (FR3 / D-1.4d)

No server-side search context. Each call is self-contained: the client supplies `page`/`page_size` to advance. The result `message` should tell the client how to get the next page (e.g. "showing 1–20 of 245 (page 1/13) — call again with page=2 for more"). `search_advanced` caps `page_size` at 50 internally; the result echoes the effective `page_size`.

### Bounded payloads (D-1.4e / AC3)

`CardSummary` rows (no `legalities`/`image_uris`/`card_faces`) plus a modest default `page_size` (20, capped 50) keep a single call from dumping heavy data at the LLM. The structured pagination metadata is how "bounded & clearly communicated" is satisfied — not truncated text. A downstream skill (Epic 3) decides presentation.

### Testing — the `:memory:` multi-connection trap (carried from Story 1.3)

- **Helper tests** (`test_card_search_tool.py`): seed and query in **one** session → `:memory:` is fine (mirror [test_card_lookup_tool.py:38-67](../../tests/integration/mcp_server/test_card_lookup_tool.py#L38)). This is where the deep filter/pagination/validation coverage lives.
- **End-to-end harness** (`test_mcp_tools.py`): the seeding session and each tool's `async with session_factory()` are **separate** connections → **must** use the **file-backed** `seeded_card_db` fixture (`:memory:` would give each connection its own empty DB). Do **not** assert against `:memory:` across sessions.
- pytest config ([pyproject.toml](../../pyproject.toml)): `asyncio_mode = "auto"` → write `async def test_...`, **no** `@pytest.mark.asyncio`. `tests.*` is exempt from `mypy --strict` but must stay ruff-clean. Layout mirrors `src/`.
- `search_advanced` runs a `COUNT(*)` over a subquery then the paginated query — both execute fine on a single in-memory session. Seed enough rows that `total_count > page_size` to exercise pagination honestly.

### Anti-patterns (do NOT do these)

- ❌ Re-implement search SQL in the tool — call `search_advanced`. The tool layer holds **no** SQLAlchemy queries.
- ❌ Add a "set"/`set_code` filter or otherwise modify `search_advanced` — out of scope (D-1.4b). The only `src/data` change is the additive `CardSummary` schema.
- ❌ Use the sync `ConnectionFactory`/raw `sqlite3` here — that's Epic 2's vector seam. This tool is `async def` awaiting the async repo.
- ❌ Return HTML-blob strings or full `Card` objects from `search_cards`, or import `legacy.ui.formatters` / `legacy.agent.*` (pulls `pydantic_ai`, absent from the lean core). Return `CardSummary`s.
- ❌ Reintroduce per-session state — no `format_filter`/`games_filter`/`search_context`/`session_id`/`active_deck` between calls (FR3/D5/D-1.4d). No `max_results` back-compat alias.
- ❌ Surface raw exceptions to the client — invalid filters → `status="invalid"` + message; no matches → `status="empty"` + message (AC3, AC4).
- ❌ Edit `Card`, `CardModel`, the async engine, or any repository. (`CardSummary` is a **new** additive class — it touches nothing existing.)
- ❌ Rename the `format` parameter (project keeps `format` for MTG-domain clarity; ruff `N` is intentionally allowed to pass it).
- ❌ Assert against a `:memory:` DB across separate sessions in the harness test — use the file-backed `seeded_card_db`.
- ❌ `print()` in library code; naive `datetime`.

### Previous Story Intelligence (Stories 1.1–1.3 — done)

- **1.3** stood up the server skeleton this story builds on: `build_server(session_factory)` with closure-registered `async def` tools, the `tools/<name>.py` helper + structured-`*Result` convention, the file-backed `seeded_card_db` fixture, and the `create_connected_server_and_client_session` harness. **Reuse all of it** — do not re-create the server, fixture, or harness.
- **1.3 review patches worth heeding here:** an empty/whitespace name once hit `ilike('%%')` and matched everything — for `search_cards`, an **all-`None`** filter set legitimately matches everything, so rely on **pagination** to bound it (don't special-case "no filters" as an error). Tests must run from project root (a 1.3 patch fixed a relative-`Path('.mcp.json')` test) — keep test file paths CWD-independent.
- **Known-flaky (out of scope):** `tests/integration/data/test_deck_repository.py::test_list_decks` ties on `created_at` ordering — intermittent in full-suite runs, passes in isolation ([deferred-work.md](./deferred-work.md)). If it flakes during verify, it's **not** your regression.
- **`PaginatedResult` has no field validators** (deferred, [deferred-work.md](./deferred-work.md)) — don't rely on it to reject `page=0`; that's why AC4 validates `page`/`page_size` in the **tool** before calling the repo.
- Team patterns to match: thorough Dev Notes, **run-and-capture** verification, strict scope discipline, additive-only data-layer changes.

### Git Intelligence

- HEAD **`02d8d40`** "fix: harden ConnectionFactory error handling; close Stories 1.1 + 1.2". Story 1.3's files are present in the working tree (implemented; commit pending) — that's the **baseline** for 1.4. Branch `feat/mcp-server-architecture`; **Conventional Commits**. Suggested message: `feat: add search_cards MCP tool + CardSummary projection (Story 1.4)`.
- Recent commits confirm the cadence: one focused `feat:`/`fix:` per story, scope-disciplined.

### Latest Tech / Versions (verified during Story 1.3 — reconfirm only if something breaks)

| Item | Value | Source / Action |
|---|---|---|
| MCP SDK | installed **`mcp 1.28.0`** (pin `mcp>=1.27.0`) | [pyproject.toml:18](../../pyproject.toml#L18) |
| Server / tool API | `from mcp.server.fastmcp import FastMCP`; `@mcp.tool()`; `async def` tools awaited on the server loop | already in use ([server.py](../../src/mcp_server/server.py)) |
| Structured output | typed/Pydantic return → `CallToolResult.structuredContent` (the model dict); `isError=False` on graceful empty/invalid paths | verified in Story 1.3 |
| In-memory client | `mcp.shared.memory.create_connected_server_and_client_session(server)` (accepts a `FastMCP`) | already in use ([test_mcp_tools.py:10](../../tests/integration/test_mcp_tools.py#L10)) |
| Param typing | `Literal[...]`, `list[str] | None`, `float | None`, `str | list[str] | None` all serialize into the tool schema | matches `lookup_card_by_name` |

> No new dependency is needed. If the `rarity` union (`str | list[str] | None`) produces an awkward tool schema or an SDK validation hiccup, fall back to `list[str] | None` and accept a single value as a one-element list — note the variance in the Dev Agent Record.

### Project Structure Notes

Target additions/edits (everything else unchanged):

```
src/
  data/
    schemas/card.py             # MODIFIED — additive CardSummary schema (only src/data change; pure, no behavior)
  mcp_server/
    server.py                   # MODIFIED — register async search_cards tool (closure over session_factory)
    tools/card_search.py        # NEW — search_cards helper + CardSearchResult (+ input validation)
tests/
  unit/
    data/test_card_schema.py            # NEW/MODIFIED — CardSummary.model_validate(Card) coverage
  integration/
    mcp_server/test_card_search_tool.py # NEW — helper-level filter/pagination/validation coverage
    test_mcp_tools.py                   # MODIFIED — end-to-end search_cards via in-memory MCP client
```

- **Alignment:** matches spec §4 (`src/mcp_server` = server + tools) and §5 (tools import core repositories directly; `search_cards` = FR5). Import direction stays `data → mcp_server` (no upward imports). Schemas stay in `src/data/schemas` per the layer contract. [Source: [design spec §4/§5](../../docs/superpowers/specs/2026-06-20-mcp-server-architecture-design.md)]
- **Variances to record (Dev Agent Record):** (a) `search_cards` returns the new lightweight `CardSummary` (not full `Card`) to bound list payloads — D-1.4e; (b) the legacy `max_results` alias and the session-stored pagination cursor are intentionally **not** ported (FR3/D-1.4d); (c) the epic's "set" filter is intentionally **out of scope** (D-1.4b).

### References

- [epics.md — Epic 1 / Story 1.4](../planning-artifacts/epics.md) — user story + ACs (FR5, FR3).
- [design spec §4 / §5 / §8](../../docs/superpowers/specs/2026-06-20-mcp-server-architecture-design.md) — tool catalog, statelessness (D5), in-process MCP test approach.
- [project-context.md](../project-context.md) — MCP rules (structured returns, wrap repositories, sync-vs-async, `format`-as-param), schema-layer contract, testing layout, ruff/mypy gates.
- [src/data/repositories/card.py](../../src/data/repositories/card.py#L346) — `search_advanced` (the method to wrap). [src/data/schemas/card.py](../../src/data/schemas/card.py) — `Card` (add `CardSummary` here). [pagination.py](../../src/data/schemas/pagination.py) — `PaginatedResult`.
- [src/mcp_server/server.py](../../src/mcp_server/server.py) / [tools/card_lookup.py](../../src/mcp_server/tools/card_lookup.py) / [tools/bug_report.py](../../src/mcp_server/tools/bug_report.py) — the exact tool/result patterns to mirror.
- [legacy/agent/tools/card_search.py](../../legacy/agent/tools/card_search.py) — source logic + `color_mode` semantics to port (logic/wording only; drop UI/session/`max_results`).
- [tests/integration/test_mcp_tools.py](../../tests/integration/test_mcp_tools.py) / [mcp_server/test_card_lookup_tool.py](../../tests/integration/mcp_server/test_card_lookup_tool.py) / [conftest.py](../../tests/integration/conftest.py) — harness, helper-test, and fixture patterns.
- [Story 1.3](./1-3-fastmcp-server-with-card-lookup-bug-report.md) — server skeleton, async-tool pattern, review patches, known-flaky note.

## Dev Agent Record

### Agent Model Used

claude-opus-4-8[1m] (Opus 4.8, 1M context) — via the BMad `dev-story` workflow.

### Debug Log References

- TDD red→green ran clean: the `CardSummary` unit test and all 16 helper-level
  tests failed first on the missing import (RED), then passed on first
  implementation (GREEN) — no logic iteration was needed; the seed-count
  arithmetic matched repository behavior on the first run.
- Quality gates required only mechanical fixes: `ruff format` rewrapped two long
  lines in `card_search.py` and the test seed builder (one E501); no code logic
  changed. `mypy --strict` over `src/` was clean on the first run.
- Full suite: **353 passed** (4.64s). The known-flaky
  `test_deck_repository.py::test_list_decks` (created_at tie — see
  deferred-work.md) passed this run; no new failures introduced.

### Completion Notes List

Implemented the third Epic-1 tool, `search_cards`, plus the additive
`CardSummary` projection. All five ACs satisfied:

- **AC1** — `search_cards` wraps `CardRepository.search_advanced` 1:1 (no SQL in
  the tool), awaits it directly (D-1.4a/D-1.4c), and returns a structured
  `CardSearchResult` of lightweight `CardSummary` rows ordered by the repo's
  (mana value, name) sort.
- **AC2** — `format`/`games` are per-call parameters; the helper holds no state,
  and a subsequent call with different params is unaffected by a prior one
  (verified by the harness `format="standard"` test excluding the modern-only
  card). No session `format_filter`/`games_filter`/search-context was ported.
- **AC3** — results are bounded to `page_size` (default 20, repo caps at 50);
  the `ok` message reports `total_count`, `page`/`total_pages`, the displayed
  range, and a `Call again with page=N` hint when more pages exist. A no-match
  query returns `status="empty"` with an adjust-your-filters message (not an
  exception).
- **AC4** — free-form filters are validated in the helper before the repo call:
  bad color (∉ WUBRG), unknown rarity, bad game (∉ paper/arena/mtgo),
  negative/`min>max` mana value, and `page`/`page_size` < 1 all return
  `status="invalid"` with a message naming the bad value — no raw exception.
  `color_mode` stays a `Literal`, boundary-validated by FastMCP.
- **AC5** — driven via the in-process `create_connected_server_and_client_session`
  harness over `build_server(session_factory=...)`; no subprocess. Helper-level
  depth lives in `test_card_search_tool.py` (own in-memory engine, 26-card seed).

**Variances recorded (per story Project Structure Notes):**
- (a) `search_cards` returns the new lightweight `CardSummary` (not the full
  `Card`) to bound list payloads — **D-1.4e**.
- (b) The legacy `max_results` alias and the session-stored pagination cursor are
  intentionally **not** ported — **FR3 / D-1.4d**.
- (c) The epic's `set` filter is intentionally **out of scope**; `search_advanced`
  and every repository are **unchanged** — **D-1.4b**. The only `src/data` change
  is the additive `CardSummary` schema.
- The `rarity: str | list[str] | None` union serialized into the FastMCP tool
  schema cleanly — no fallback to `list[str] | None` was needed.

### File List

**Implementation (src/):**
- `src/data/schemas/card.py` — MODIFIED: added additive `CardSummary` projection
  (no change to `Card`/`CardModel`/any repository).
- `src/mcp_server/tools/card_search.py` — NEW: `search_cards` helper +
  `CardSearchResult` schema + `_validation_error` input validation.
- `src/mcp_server/server.py` — MODIFIED: registered the `async search_cards`
  `@mcp.tool()` wrapper (closure over `session_factory`); added `Literal` +
  `card_search` imports.

**Tests:**
- `tests/unit/data/test_schemas.py` — MODIFIED: `CardSummary.model_validate(Card)`
  field/round-trip + lightweight-projection coverage.
- `tests/integration/mcp_server/test_card_search_tool.py` — NEW: helper-level
  filter / `color_mode` / rarity / format / pagination / empty / invalid coverage
  (16 tests; 26-card in-memory seed).
- `tests/integration/test_mcp_tools.py` — MODIFIED: end-to-end `search_cards`
  smoke tests via the in-memory MCP client (color filter + projection, format
  filter, graceful invalid).

**Workflow tracking (non-code):**
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — story status
  `ready-for-dev` → `in-progress` → `review`.

## Change Log

| Date | Change |
|---|---|
| 2026-06-20 | Implemented Story 1.4: added `search_cards` MCP tool wrapping `CardRepository.search_advanced`, the additive `CardSummary` projection, input validation, and helper-level + in-memory-harness integration tests. All 5 ACs met; full suite 353 passed; ruff + mypy clean. Status → review. |

### Review Findings

- [x] [Review][Patch] `rarity=[]` passes validation but produces `or_()` with no arguments in the repo, silently filtering out all results [src/mcp_server/tools/card_search.py:69-81] — Fixed: normalize `rarity=[]` to `None` before validation and repo call.
- [x] [Review][Patch] `format=""` (empty string) bypasses `format_filter is None` guard in `_apply_format_filter`, producing a malformed JSON path and a silent empty result [src/mcp_server/tools/card_search.py:121] — Fixed: normalize empty/whitespace `format` to `None` before the repo call.
- [x] [Review][Defer] `CardSummary.mana_cost`/`oracle_text` declared `str` (non-nullable) — pre-existing pattern from `Card` schema; risk inherited not introduced [src/data/schemas/card.py:84,87] — deferred, pre-existing
- [x] [Review][Defer] `CardSummary.colors: list[str]` has no `None`-coercion validator (unlike `Card.games`) — same pre-existing pattern from `Card`; fix belongs to Card schema story [src/data/schemas/card.py:88] — deferred, pre-existing
- [x] [Review][Defer] `page_size > 50` silently capped by repo with no caller notification — working as designed per spec; `CardSearchResult.page_size` echoes the effective (capped) value [src/data/repositories/card.py] — deferred, pre-existing
- [x] [Review][Defer] `games` validation is case-sensitive while `rarity` is case-insensitive — inconsistent but error messages name the correct casing; no correctness impact [src/mcp_server/tools/card_search.py:83-86] — deferred, pre-existing
- [x] [Review][Defer] `page` beyond `total_pages` returns generic `status="empty"` with no out-of-bounds signal — graceful per AC3; no specific AC violation [src/mcp_server/tools/card_search.py:178-189] — deferred, pre-existing
- [x] [Review][Defer] `colors=[]` silently applies no color filter for non-"exact" modes — inherited behavior from `search_advanced`; out of scope for this story [src/data/repositories/card.py] — deferred, pre-existing
