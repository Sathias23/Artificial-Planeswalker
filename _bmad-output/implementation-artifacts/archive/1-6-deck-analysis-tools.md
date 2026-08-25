---
baseline_commit: 2f812f8
---

# Story 1.6: Deck Analysis Tools

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a player using Claude Code,
I want mana-curve, synergy, and format-legality analysis tools,
so that I can evaluate a deck's curve, internal synergies, and Standard legality on demand — by passing only a `deck_id` (and `format`/`games` where relevant), with no server-side state.

## Decisions Locked (approved with Brad, 2026-06-20)

> These resolve the open forks before dev. They shape the ACs/Tasks below — **do not re-litigate**.
>
> - **D-1.6a — `validate_deck` whole-deck logic is an ADDITIVE pure function in `src/logic/deck_validator.py`.** The existing module only has the per-add `validate_card_addition` (4-copy guard on a single addition) + `is_basic_land` + `get_current_card_count`. There is **no** whole-deck validator and **no** legacy `validate_deck` tool to port. Add `validate_deck(deck, *, format="standard", games=None) -> DeckValidationReport` (plus `DeckValidationReport` / `DeckViolation` Pydantic models) to `src/logic/deck_validator.py`, **reusing `is_basic_land`**. This is the **one** logic-layer behavior ADD for this story (directly analogous to Story 1.5's additive `CardRepository.get_by_id`). **Do NOT modify** `validate_card_addition`, `is_basic_land`, or `get_current_card_count` — existing logic stays byte-for-byte (NFR7).
> - **D-1.6b — `validate_deck` implements constructed (60-card) rules; Standard is the default/only fully-modelled format.** Checks: mainboard **≥ 60**; sideboard **≤ 15**; **≤ 4 copies** of each non-basic card counted **across mainboard + sideboard combined** (basics exempt via `is_basic_land`); each distinct card **legal in `format`** (`card.legalities.get(format) == "legal"`). `format` (default `"standard"`) and `games` are **parameters** (FR3/D5), never server state. Commander/Brawl singleton + 100-card and other format-specific minima are **OUT of scope** — documented Phase-1 limitation (the 60-card rule is applied regardless of the `format` string; only the per-card legality check is format-aware).
> - **D-1.6c — `games` is an OPTIONAL availability check.** When provided, validate each value against `{"paper", "arena", "mtgo"}` (mirror `card_search`'s `_VALID_GAMES`); a bad value → `status="invalid"`. When valid, flag any distinct card whose `card.games` does not intersect the requested platforms (`game_availability` violation, e.g. "X is not available on arena"). When omitted (`None`), skip the check entirely. This keeps statelessness parity with the spec (§5.2 lists `games` as a `validate_deck` parameter) without over-building.
> - **D-1.6d — analysis consumes the FULL deck (full `Card`), mainboard-only, sideboard excluded; the lightweight deck projections are NOT inputs.** Load via `DeckRepository.get_deck_with_cards(deck_id)` (eager `selectinload` of full `Card` — has `oracle_text`/`type_line`/`cmc`/`legalities`). `analyze_mana_curve` gets the mainboard **expanded by quantity** into `list[Card]`; `detect_synergies` gets the mainboard `list[DeckCard]` **un-expanded** (it weights by `quantity` itself). This mirrors the legacy wrappers exactly. `CardSummary`/`DeckCardSummary` are **unusable** here (they drop `oracle_text`/`legalities`).
> - **D-1.6e — result serialization: reuse the logic's Pydantic models; flatten the dataclass.** `detect_synergies`/`validate_deck` return Pydantic → nest/reuse directly in the `*Result`. `analyze_mana_curve` returns a stdlib **`@dataclass`** (`ManaCurveAnalysis`) → **flatten its 8 fields** onto `ManaCurveResult` via an explicit constructor (do **not** nest the dataclass — don't rely on Pydantic-v2-dataclass interop in FastMCP schema-gen). **Gotcha:** `SynergyAnalysis.total_count` is a `@property`, **not** a field — it will **not** appear in `structuredContent`; surface it as an explicit `synergy_count` field on `SynergyResult`.
> - **D-1.6f — every bad/empty input is graceful; never raise (AC4).** Bogus `deck_id` → `deck_not_found`. Curve/synergy on an **empty mainboard** → `status="empty"` (pre-check; do **not** call the logic — `analyze_mana_curve` raises `ValueError` on `[]`). `validate_deck` on an empty deck → `status="ok"` with `report.is_legal=False` + a `min_deck_size` violation (an empty deck's legality answer **is** "illegal 0/60", which is the useful result — not "empty"). Wrap every repo call in `try/except DatabaseError → status="error"` (the Story 1.5 review lesson — all helpers, not just one).
> - **D-1.6g — NOT ported / explicitly out of scope.** `generate_contextual_feedback` (the throttled per-add coaching in `mana_curve.py`) is the **dropped** auto-feedback UI behavior (D5) — **not** exposed; contextual coaching is the Epic-3 `mana-curve-analysis` skill's job. **No** HTML/markdown report strings (legacy `format_synergies`/`format_deck_*` formatters) — structured returns only. **No** RAG/semantic (Epic 2). **No** new deck CRUD or `update_*` tools. **No** modification of any existing `src/logic` function, repository method, or schema (the sole ADD is `validate_deck` in the logic layer).

## Acceptance Criteria

> Source: [epics.md#Story-1.6](../planning-artifacts/epics.md) (BDD as authored: FR9, FR10, FR11, FR3, NFR7), with the locked decisions above folded in. **All seven must hold simultaneously.** This story adds the **tenth–twelfth Epic-1 tools** on top of the Story-1.3 server skeleton and the Story-1.4/1.5 patterns; it reuses the server builder, the closure-injected `session_factory`, the structured-`*Result` convention (with the `"error"` status), and the in-memory harness already in place.

**AC1 — `analyze_mana_curve` returns the curve distribution via the existing `src/logic` curve logic (FR9)**
- **Given** `analyze_mana_curve` with a `deck_id`
- **When** invoked
- **Then** it loads the deck via `DeckRepository.get_deck_with_cards`, expands the **mainboard** cards by `quantity` into a `list[Card]` (sideboard excluded), calls the **unchanged** `src.logic.mana_curve.analyze_mana_curve(...)`, and returns a `ManaCurveResult` (`status="ok"`) carrying the flattened analysis (`distribution`, `total_lands`, `total_spells`, `average_cmc`, `playable_cards_by_turn`, `land_ratio`, `issues`, `recommendations`) — **no curve math re-implemented in the tool**.

**AC2 — `detect_synergies` returns detected synergies via the existing `src/logic` synergy logic (FR10)**
- **Given** `detect_synergies` with a `deck_id`
- **When** invoked
- **Then** it passes the **mainboard** `list[DeckCard]` (un-expanded — full `Card` nested) to the **unchanged** `src.logic.synergy.detect_synergies(...)` and returns a `SynergyResult` (`status="ok"`) with `synergies` (the logic's `SynergyPattern` list), `synergy_count` (explicit — the `total_count` property does **not** serialize), and `deck_cohesion`.

**AC3 — `validate_deck` with `format`/`games` parameters returns legality/validation results (FR11, FR3)**
- **Given** `validate_deck` with a `deck_id` and `format`/`games` as **parameters**
- **When** invoked
- **Then** it returns a `ValidateDeckResult` (`status="ok"`) whose `report` (the new `src.logic.deck_validator.DeckValidationReport`) reports `is_legal`, the `mainboard_count`/`sideboard_count`, and a `violations` list covering **60+ mainboard cards**, **≤15 sideboard**, **≤4 copies** of non-basic cards (combined boards), and **per-card format legality** (D-1.6b) — with **no** server-side format/games state persisting between calls.

**AC4 — Invalid or empty inputs return a clear structured message rather than raising (AC: epics #4, D-1.6f)**
- **Given** a missing deck (bogus `deck_id`), an empty deck, or an invalid parameter (`games` value not in `{paper, arena, mtgo}`)
- **When** any of the three tools is invoked
- **Then** it returns a structured result (`status` ∈ `deck_not_found` / `empty` / `invalid` / `error`) with a message naming the problem — **no raw exception is surfaced** to the MCP client. Specifically: bogus `deck_id` → `deck_not_found` (all three); empty mainboard → `empty` (curve & synergy) while `validate_deck` returns `status="ok"` with `is_legal=False` + a `min_deck_size` violation; a bad `games` value → `validate_deck` `status="invalid"`; any `DatabaseError` → `status="error"`.

**AC5 — Exactly one additive `src/logic` change; all existing logic-layer behavior unchanged (NFR7)**
- **Given** the logic layer
- **When** this story lands
- **Then** the **only** behavior addition is `validate_deck(...)` + `DeckValidationReport`/`DeckViolation` in `src/logic/deck_validator.py` — **no** existing function (`analyze_mana_curve`, `detect_synergies`, `validate_card_addition`, `is_basic_land`, `get_current_card_count`, `generate_contextual_feedback`) or any schema is modified
- **And** the existing `tests/unit/logic/` suites (`test_mana_curve.py`, `test_synergy.py`, `test_deck_validator.py`) still pass (no regression).

**AC6 — Bounded, structured payloads (no full-`Card` dumps; reuse logic models)**
- **Given** the three tools
- **When** they return
- **Then** each returns a typed Pydantic `*Result` whose payload is the **analysis** (counts, distributions, named violations, synergy patterns with card **names** as strings) — never a list of full `Card` objects, HTML, or markdown report strings. (The analysis models are already lightweight: curve/validate carry numbers + short strings; synergy carries `affected_cards` as `list[str]`.)

**AC7 — In-memory MCP client harness drives the three tools end-to-end (no subprocess) (FR9–FR11, NFR6, spec §8)**
- **Given** the in-process MCP client harness against the shared file-backed `seeded_card_db`
- **When** it builds a small deck **through the existing tools** and then calls `analyze_mana_curve`, `detect_synergies`, and `validate_deck`
- **Then** integration assertions pass **without spawning a subprocess**, reusing the Story-1.3 wiring (`build_server(session_factory=...)` + `create_connected_server_and_client_session`)
- **And** the `deck_not_found` smoke (each tool on a bogus `deck_id`) returns its graceful status with `isError is False`.

## Tasks / Subtasks

- [x] **Task 1 — Additive whole-deck validator in `src/logic/deck_validator.py`** (AC: 3, 5) — *the ONE logic-layer behavior add (D-1.6a/b/c); existing functions untouched*
  - [x] In [src/logic/deck_validator.py](../../src/logic/deck_validator.py) add two Pydantic models **alongside** the existing dataclass `ValidationResult` (do **not** modify it). Import `BaseModel`, `ConfigDict`, `Literal`.
    - `DeckViolation(BaseModel)` — `rule: Literal["min_deck_size", "max_sideboard_size", "copy_limit", "format_legality", "game_availability"]`; `card_name: str | None = None`; `detail: str`. Google-style docstring.
    - `DeckValidationReport(BaseModel)` — `is_legal: bool`; `format: str`; `mainboard_count: int`; `sideboard_count: int`; `violations: list[DeckViolation] = []`. Docstring noting `is_legal == (violations == [])`.
  - [x] Add `def validate_deck(deck: Deck, *, format: str = "standard", games: list[str] | None = None) -> DeckValidationReport:` (pure, sync, no DB/UI). Logic:
    - `mainboard = [dc for dc in deck.deck_cards if not dc.sideboard]`, `sideboard = [dc for dc in deck.deck_cards if dc.sideboard]`; `mainboard_count = sum(dc.quantity for dc in mainboard)`, `sideboard_count = sum(dc.quantity for dc in sideboard)`.
    - **Size:** `mainboard_count < 60` → `min_deck_size` violation; `sideboard_count > 15` → `max_sideboard_size` violation.
    - **Copy limit (combined boards, basics exempt):** sum `quantity` per `card_id` across **both** boards; for each non-basic (`not is_basic_land(dc.card)`) card with combined `> 4` → `copy_limit` violation (`card_name=dc.card.name`, detail names the count). **Note:** reuse `is_basic_land`; do **not** reuse `get_current_card_count` (it counts mainboard-only — wrong for the combined-deck rule).
    - **Format legality (per distinct card):** for each distinct `card`, if `card.legalities.get(format) != "legal"` → `format_legality` violation. (Anything that isn't exactly `"legal"` — `not_legal`/`banned`/`restricted`/missing — is illegal in `format` for Phase-1 Standard scope.)
    - **Game availability (only if `games`):** for each distinct `card`, if `not (set(card.games) & set(games))` → `game_availability` violation.
    - `is_legal = not violations`; return `DeckValidationReport(...)`.
  - [x] **Do NOT** modify `ValidationResult`, `is_basic_land`, `get_current_card_count`, or `validate_card_addition`.

- [x] **Task 2 — `src/logic` unit tests for `validate_deck`** (AC: 3, 5) — *extend [tests/unit/logic/test_deck_validator.py](../../tests/unit/logic/test_deck_validator.py); build `Deck`/`DeckCard` schemas in-memory (no DB)*
  - [x] Add a `TestValidateDeck` class covering: a **legal** 60-card Standard deck (no violations, `is_legal=True`); **under-60** mainboard → `min_deck_size`; **>15** sideboard → `max_sideboard_size`; **5 copies** of a non-basic → `copy_limit`; **20 basic lands** → **no** `copy_limit` (basic exemption); a **non-`standard`-legal** card → `format_legality`; combined main+side copies (3 main + 2 side of the same non-basic = 5) → `copy_limit`; `games=["arena"]` with a paper-only card → `game_availability`; `games=None` → no availability check.
  - [x] Build `Card`/`DeckCard`/`Deck` Pydantic objects directly (mirror [tests/unit/data/schemas/test_deck.py](../../tests/unit/data/schemas/test_deck.py) construction) — pure unit test, no session.

- [x] **Task 3 — `deck_analysis` tool helpers + `*Result` schemas** (AC: 1, 2, 3, 4, 6) — *new module, mirror [deck_management.py](../../src/mcp_server/tools/deck_management.py)*
  - [x] Create `src/mcp_server/tools/deck_analysis.py` with a module docstring (purpose: wraps `src/logic` curve/synergy/validator over a `DeckRepository`-loaded full deck; structured returns; stateless `deck_id`-keyed; mainboard-only; drops legacy session/active-deck/format-filter/HTML machinery and the dropped auto-feedback).
  - [x] Import: `Literal` from `typing`; `BaseModel` from `pydantic`; `DatabaseError` from `sqlalchemy.exc`; `AsyncSession`; `DeckRepository`; `Card` (for typing the expanded list); the logic functions **under aliases** — `from src.logic.mana_curve import analyze_mana_curve as _logic_analyze_mana_curve`, `from src.logic.synergy import detect_synergies as _logic_detect_synergies, SynergyPattern`, `from src.logic.deck_validator import validate_deck as _logic_validate_deck, DeckValidationReport`. Add `_VALID_GAMES = frozenset({"paper", "arena", "mtgo"})` (mirror [card_search.py:25](../../src/mcp_server/tools/card_search.py#L25)). Module `logger = logging.getLogger(__name__)`.
  - [x] **Result schemas** (Google-style docstrings; include `"error"` in every `status`):
    - `ManaCurveResult` — `status: Literal["ok","empty","deck_not_found","error"]`; `deck_id: str | None = None`; `deck_name: str | None = None`; `distribution: dict[int,int] = {}`; `total_lands: int = 0`; `total_spells: int = 0`; `average_cmc: float = 0.0`; `playable_cards_by_turn: dict[int,int] = {}`; `land_ratio: float = 0.0`; `issues: list[str] = []`; `recommendations: list[str] = []`; `message: str`.
    - `SynergyResult` — `status: Literal["ok","empty","deck_not_found","error"]`; `deck_id: str | None = None`; `deck_name: str | None = None`; `synergies: list[SynergyPattern] = []`; `synergy_count: int = 0`; `deck_cohesion: Literal["low","moderate","high"] = "low"`; `message: str`.
    - `ValidateDeckResult` — `status: Literal["ok","deck_not_found","invalid","error"]`; `deck_id: str | None = None`; `report: DeckValidationReport | None = None`; `message: str`.
  - [x] **Helpers** (each `async def`, takes `session: AsyncSession` + keyword-only `deck_id`/params, returns the matching `*Result`; load-validate-first, never raise):
    - `async def analyze_mana_curve(session, *, deck_id: str) -> ManaCurveResult` — `deck_id.strip()`; `try: deck = await DeckRepository(session).get_deck_with_cards(deck_id) except DatabaseError: status="error"`; `None` → `deck_not_found`; `all_cards = [dc.card for dc in deck.deck_cards if not dc.sideboard for _ in range(dc.quantity)]`; `if not all_cards: status="empty"`; `analysis = _logic_analyze_mana_curve(all_cards)`; build `ManaCurveResult(status="ok", deck_id, deck_name=deck.name, distribution=analysis.distribution, ...)`.
    - `async def detect_synergies(session, *, deck_id: str) -> SynergyResult` — load (same error/`deck_not_found`); `mainboard = [dc for dc in deck.deck_cards if not dc.sideboard]`; `if not mainboard: status="empty"`; `analysis = _logic_detect_synergies(mainboard)`; `SynergyResult(status="ok", synergies=analysis.synergies, synergy_count=analysis.total_count, deck_cohesion=analysis.deck_cohesion, ...)`.
    - `async def validate_deck(session, *, deck_id: str, format: str = "standard", games: list[str] | None = None) -> ValidateDeckResult` — `deck_id.strip()`; normalize `format = (format.strip() or "standard")`; **validate `games`** (if any value `not in _VALID_GAMES` → `status="invalid"` naming it); load (same error/`deck_not_found`); `report = _logic_validate_deck(deck, format=format, games=games)`; message = legal vs `f"{len(report.violations)} issue(s)"`; `status="ok"`.
  - [x] Google-style docstrings on each helper = **the LLM-facing tool description** (what it analyzes, that it's mainboard-only, that `format`/`games` are per-call params, that it returns structured analysis — use `load_deck` for contents / `lookup_card_by_name` for full card detail).

- [x] **Task 4 — Register the three tools in `build_server`** (AC: 1, 2, 3, 7) — *closure registration; mirror the deck-management wrappers*
  - [x] In [src/mcp_server/server.py](../../src/mcp_server/server.py) add three `@mcp.tool()` `async def` wrappers — `analyze_mana_curve(deck_id)`, `detect_synergies(deck_id)`, `validate_deck(deck_id, format="standard", games=None)` — each closing over `session_factory`, opening `async with session_factory() as session:`, delegating to the corresponding helper.
  - [x] Import the result schemas + helpers from `src.mcp_server.tools.deck_analysis` under **private aliases** (e.g. `analyze_mana_curve as _analyze_mana_curve_helper`) to avoid the wrapper/helper name clash (the `_search_cards_helper`/`_add_card_to_deck_helper` precedent).
  - [x] **No** change to `__main__.py`, `.mcp.json`, transport selection, or `src/mcp_server/__init__.py`. Wrappers are `async def` awaiting the async repo + calling sync logic (D-1.3a/1.4c) — **not** the sync `ConnectionFactory` (Epic 2).

- [x] **Task 5 — Helper-level integration tests** (AC: 1, 2, 3, 4, 5, 6) — *new file, mirror [test_deck_management_tool.py](../../tests/integration/mcp_server/test_deck_management_tool.py)*
  - [x] `tests/integration/mcp_server/test_deck_analysis_tool.py` — own file-backed (**not** `:memory:`) engine + a single shared `session` fixture, seeding a **richer** card set than the 3-card shared fixture so each analysis path is exercised: e.g. a basic land `Mountain` (`type_line="Basic Land — Mountain"`, `legalities={"standard":"legal"}`, `games=["paper","arena"]`), several Goblins (`type_line="Creature — Goblin"`, oracle text referencing "other Goblins" for a tribal payoff → synergy), a couple of Standard-legal spells at varied CMC (curve), one **non-standard-legal** card (`legalities={"modern":"legal"}` → `format_legality`), and a paper-only card (`games=["paper"]` → `game_availability` when `games=["arena"]`). Build decks **via `DeckRepository`** in the test.
  - [x] Cover, asserting `status` + structured fields:
    - `analyze_mana_curve`: `ok` (assert `distribution`, `total_lands`/`total_spells`, `average_cmc`, `land_ratio`, sideboard cards **excluded**, quantities **expanded**); `deck_not_found` (bogus id); `empty` (deck with only sideboard cards, or no cards).
    - `detect_synergies`: `ok` with a **tribal** Goblin synergy detected (assert a `SynergyPattern` with `pattern_type="tribal"`, `subtype="Goblin"`, names in `affected_cards`, and `synergy_count >= 1`); `ok` with **no** synergies on a vanilla deck (`synergies == []`, `deck_cohesion="low"`); `deck_not_found`; `empty`.
    - `validate_deck`: a **legal** 60-card Standard deck → `is_legal=True`, no violations; **under-60** → `min_deck_size`; **5 copies** non-basic → `copy_limit`; non-standard-legal card present → `format_legality`; `format="modern"` flips a modern-only card to legal (assert format is a real parameter, no persisted state); `games=["arena"]` with a paper-only card → `game_availability`; bad `games=["xbox"]` → `status="invalid"`; `deck_not_found`.
  - [x] Assert **no full-`Card`/HTML** leakage: results carry counts/strings/`SynergyPattern` only (e.g. `affected_cards` are `str`; no `"legalities"`/`"image_uris"` blobs).

- [x] **Task 6 — End-to-end MCP harness tests** (AC: 7) — *extend [test_mcp_tools.py](../../tests/integration/test_mcp_tools.py)*
  - [x] Build a deck through the **client** from the shared `seeded_card_db` 3 cards (Lightning Bolt `card-lightning-bolt`, Thunderbolt `card-thunderbolt` (modern-only), Counterspell `card-counterspell`): `create_deck` → capture `deck_id` → `add_card_to_deck(name="Lightning Bolt", quantity=4)` → `add_card_to_deck(card_id="card-counterspell")` → `add_card_to_deck(card_id="card-thunderbolt")`.
  - [x] Drive the three tools through the client and assert on `structuredContent`:
    - `analyze_mana_curve(deck_id)` → `status="ok"`, `total_spells == 6` (4+1+1), `distribution` present (**note:** JSON object keys are **strings** — assert `sc["distribution"]["1"] == 4` for the four CMC-1 Bolts).
    - `detect_synergies(deck_id)` → `status="ok"` (3 simple cards → likely `synergies == []`, `deck_cohesion="low"` — assert it runs & is structured, not specific synergies).
    - `validate_deck(deck_id, format="standard")` → `status="ok"`, `report["is_legal"] is False` with a `min_deck_size` violation (6 < 60) **and** a `format_legality` violation for Thunderbolt (modern-only). Assert `validate_deck(deck_id, format="modern")` drops the Thunderbolt legality violation (parameter, not state).
  - [x] Graceful smoke: each of the three tools on `{"deck_id": "bogus-deck"}` → `structuredContent["status"] == "deck_not_found"`, `isError is False`.
  - [x] **Avoid editing** the shared `seeded_card_db` fixture (Stories 1.3–1.5 depend on its exact 3 cards). Build the deck **through the tools**.

- [x] **Task 7 — Verify (run the commands, capture output)** (AC: all)
  - [x] `uv run pytest tests/integration/mcp_server/test_deck_analysis_tool.py tests/integration/test_mcp_tools.py tests/unit/logic/test_deck_validator.py -v` → new tests pass.
  - [x] `uv run pytest tests/` → full suite green except the **known-flaky** `test_deck_repository.py::test_list_decks` family (`created_at` tie; passes in isolation — see [deferred-work.md](./deferred-work.md)). Confirm **no new** failures, and that the existing `tests/unit/logic/` suites still pass (NFR7).
  - [x] `uv run ruff check .` / `uv run ruff format --check .` → all Story-1.6 files clean.
  - [x] `uv run mypy src/` → clean (strict). New `src/` code is fully typed.
  - [x] Optional smoke: confirm all three analysis tools register on `build_server()` (the Task 6 harness test is the authoritative check).

### Review Findings

- [x] [Review][Patch] `dc.card` not guarded for `None` in `validate_deck` logic [`src/logic/deck_validator.py` — combined_counts loop] — `card_by_id[dc.card_id] = dc.card` without a None check. If FK enforcement is off and a card row was deleted after the deck_card row was inserted (same risk noted in 1-5 deferred), `AttributeError` on `dc.card.name` / `.legalities` crashes the pure function. Fix: `if dc.card is None: continue` in both loops. ✅ Applied.
- [x] [Review][Patch] `games` list items not stripped of whitespace before `_VALID_GAMES` lookup [`src/mcp_server/tools/deck_analysis.py` — `validate_deck` helper games validation loop] — `" arena"` (leading space) fails `_VALID_GAMES` and returns `status="invalid"` when the caller's intent is valid. `deck_id` and `format` are stripped; `games` items should be too. Fix: use `game.strip() not in _VALID_GAMES`. ✅ Applied.
- [x] [Review][Defer] `dc.quantity` zero or negative can undercount mainboard cards [`src/logic/deck_validator.py`] — deferred, data integrity at insert time
- [x] [Review][Defer] `card.legalities` potentially `None` from DB NULL — `card.legalities.get(format)` raises `AttributeError`; schema should enforce non-null [`src/logic/deck_validator.py`] — deferred, pre-existing schema gap
- [x] [Review][Defer] `card.games` potentially `None` from DB NULL — `set(card.games)` raises `TypeError`; schema should enforce non-null [`src/logic/deck_validator.py`] — deferred, pre-existing schema gap
- [x] [Review][Defer] Logic functions (`_logic_analyze_mana_curve`, `_logic_detect_synergies`, `_logic_validate_deck`) can raise unexpected exceptions beyond the guarded `ValueError`/`DatabaseError` — adding a broad catch would mask bugs [`src/mcp_server/tools/deck_analysis.py`] — deferred, accept risk in pure logic layer
- [x] [Review][Defer] Quantity expansion in `analyze_mana_curve` can OOM for adversarially large `dc.quantity` values [`src/mcp_server/tools/deck_analysis.py:162`] — deferred, production hardening out of scope
- [x] [Review][Defer] `format` normalization (empty→"standard") absent from pure logic `validate_deck` in `deck_validator.py` — only the tool helper normalizes; direct callers must pass a non-empty format [`src/logic/deck_validator.py`] — deferred, caller's responsibility per function contract
- [x] [Review][Defer] `seeded_card_db` fixture omits `games` field on seed cards — `games` filter path not tested end-to-end through the MCP harness [`tests/integration/conftest.py`] — deferred, covered at helper level; acceptable Phase-1 coverage

## Dev Notes

### What this story IS — and is NOT

- **IS:** the **deck-analysis tool surface** (FR9/FR10/FR11) — three `async def` `@mcp.tool()` wrappers (`analyze_mana_curve`, `detect_synergies`, `validate_deck`) that load the **full deck** via `DeckRepository.get_deck_with_cards`, call the **existing** `src/logic` curve/synergy logic + the **new** logic-layer `validate_deck`, and return **structured** analysis. Plus **one** additive logic function (`validate_deck` + `DeckValidationReport`/`DeckViolation`), and integration tests (helper-level + in-memory MCP harness) + logic unit tests.
- **IS NOT:** anything that **modifies** existing `src/logic` (only an additive `validate_deck`), any **RAG/semantic** work (Epic 2 — no `Embedder`/`card_vec`/sync `ConnectionFactory`), the **deckbuilding skills** (Epic 3 — the analyze→suggest→explain loop, throttled coaching), the dropped **`generate_contextual_feedback`** auto-feedback, **HTML/markdown report strings** (legacy formatters), any **new deck CRUD**/`update_*` tools, or per-session **format/games/active-deck state** (FR3/D5).

### Reuse map — what already exists (DO NOT reinvent)

| Need | Use this | Location |
|---|---|---|
| Curve analysis (CMC distribution, lands/spells, issues, recommendations) | `analyze_mana_curve(cards: list[Card]) -> ManaCurveAnalysis` (**raises `ValueError` on `[]`**) | [mana_curve.py:58](../../src/logic/mana_curve.py#L58) |
| Synergy detection (tribal/keyword/mechanic; weights by `quantity`) | `detect_synergies(deck_cards: list[DeckCard]) -> SynergyAnalysis` (returns empty analysis on `[]`, does **not** raise) | [synergy.py:80](../../src/logic/synergy.py#L80) |
| Synergy result models (reuse directly in `SynergyResult`) | `SynergyPattern` / `SynergyAnalysis` (`total_count` is a **property**) | [synergy.py:36](../../src/logic/synergy.py#L36), [synergy.py:62](../../src/logic/synergy.py#L62) |
| Basic-land exemption for the 4-copy rule | `is_basic_land(card) -> bool` | [deck_validator.py:30](../../src/logic/deck_validator.py#L30) |
| Load a deck with **full** cards (eager `selectinload`) | `DeckRepository.get_deck_with_cards(deck_id) -> Deck \| None` | [deck.py:521](../../src/data/repositories/deck.py#L521) |
| Tool wiring (closure over `session_factory`, `async with`, private-alias import) | `search_cards` / deck-management wrappers | [server.py:97](../../src/mcp_server/server.py#L97), [server.py:234](../../src/mcp_server/server.py#L234) |
| Structured-`*Result` convention (`status`+`message`, `"error"` on `DatabaseError`, validate-first) | `DeckCardResult` / the deck-mgmt helpers | [deck_management.py:85](../../src/mcp_server/tools/deck_management.py#L85), [deck_management.py:230](../../src/mcp_server/tools/deck_management.py#L230) |
| `games` validation vocabulary | `_VALID_GAMES` | [card_search.py:25](../../src/mcp_server/tools/card_search.py#L25) |
| Legacy wrappers (logic/scoping/wording only — **drop** RunContext/active-deck/HTML/auto-feedback) | `analyze_deck_mana_curve` / `detect_deck_synergies` | [mana_curve.py](../../legacy/agent/tools/mana_curve.py), [synergy_detection.py](../../legacy/agent/tools/synergy_detection.py) |
| In-memory MCP harness + file-backed seed | `create_connected_server_and_client_session` + `seeded_card_db` | [test_mcp_tools.py:10](../../tests/integration/test_mcp_tools.py#L10), [conftest.py:81](../../tests/integration/conftest.py#L81) |

### The validate_deck gap — why a new logic function (D-1.6a)

`src/logic/deck_validator.py` ships **only** the per-add `validate_card_addition` (a 4-copy guard on *one* addition) plus `is_basic_land` and `get_current_card_count` (**mainboard-only**). There is **no** whole-deck validator, and there is **no** legacy `validate_deck` tool to port — the legacy app validated legality *inline during `add_card_to_deck`* (`card.legalities.get("standard") != "legal"` + `validate_card_addition`), never as a standalone whole-deck pass. So the Story-1.6 `validate_deck` requires a **new** pure function. Per the layer contract (`src/logic` is the reusable domain core; tools wrap logic and hold no domain logic), it belongs in `src/logic/deck_validator.py`, not in the tool. `synergy.py` already proves Pydantic models live happily in `src/logic`, so `validate_deck` returning a Pydantic `DeckValidationReport` is consistent and lets the tool nest it directly. This is **additive** — existing functions are untouched, so NFR7 ("logic-layer behavior unchanged, unit tests pass") holds.

```python
# src/logic/deck_validator.py  (ADD below the existing functions — DO NOT touch them)
from typing import Literal
from pydantic import BaseModel

class DeckViolation(BaseModel):
    """A single deck-construction rule violation."""
    rule: Literal["min_deck_size", "max_sideboard_size", "copy_limit",
                  "format_legality", "game_availability"]
    card_name: str | None = None
    detail: str

class DeckValidationReport(BaseModel):
    """Whole-deck legality report. ``is_legal`` iff ``violations`` is empty."""
    is_legal: bool
    format: str
    mainboard_count: int
    sideboard_count: int
    violations: list[DeckViolation] = []

_MIN_MAINBOARD = 60          # constructed (Standard) — Phase-1 scope (D-1.6b)
_MAX_SIDEBOARD = 15
_MAX_COPIES = 4

def validate_deck(deck: Deck, *, format: str = "standard",
                  games: list[str] | None = None) -> DeckValidationReport:
    mainboard = [dc for dc in deck.deck_cards if not dc.sideboard]
    sideboard = [dc for dc in deck.deck_cards if dc.sideboard]
    mainboard_count = sum(dc.quantity for dc in mainboard)
    sideboard_count = sum(dc.quantity for dc in sideboard)
    violations: list[DeckViolation] = []

    if mainboard_count < _MIN_MAINBOARD:
        violations.append(DeckViolation(rule="min_deck_size",
            detail=f"Mainboard has {mainboard_count} cards; {format} requires at least {_MIN_MAINBOARD}."))
    if sideboard_count > _MAX_SIDEBOARD:
        violations.append(DeckViolation(rule="max_sideboard_size",
            detail=f"Sideboard has {sideboard_count} cards; the maximum is {_MAX_SIDEBOARD}."))

    # 4-copy limit — combined across both boards, basics exempt.
    combined: dict[str, tuple[int, str, bool]] = {}   # card_id -> (qty, name, is_basic)
    for dc in deck.deck_cards:
        qty, _, _ = combined.get(dc.card_id, (0, dc.card.name, is_basic_land(dc.card)))
        combined[dc.card_id] = (qty + dc.quantity, dc.card.name, is_basic_land(dc.card))
    for _cid, (qty, name, basic) in combined.items():
        if not basic and qty > _MAX_COPIES:
            violations.append(DeckViolation(rule="copy_limit", card_name=name,
                detail=f"{qty} copies of '{name}' (max {_MAX_COPIES} for non-basic cards)."))

    # Per-distinct-card legality + optional game availability.
    seen: set[str] = set()
    for dc in deck.deck_cards:
        if dc.card_id in seen:
            continue
        seen.add(dc.card_id)
        card = dc.card
        if card.legalities.get(format) != "legal":
            violations.append(DeckViolation(rule="format_legality", card_name=card.name,
                detail=f"'{card.name}' is not legal in {format}."))
        if games and not (set(card.games) & set(games)):
            violations.append(DeckViolation(rule="game_availability", card_name=card.name,
                detail=f"'{card.name}' is not available on {', '.join(games)}."))

    return DeckValidationReport(is_legal=not violations, format=format,
        mainboard_count=mainboard_count, sideboard_count=sideboard_count, violations=violations)
```

> The `_MIN_MAINBOARD`/`_MAX_SIDEBOARD` constants encode the **constructed 60-card** rule and apply regardless of the `format` string (only the per-card legality check is format-aware). Commander (100, singleton) and format-specific minima are a documented Phase-1 limitation (D-1.6b) — call it out in the Dev Agent Record's Variances.

### Feeding the logic — full deck, mainboard-only, the two shapes (D-1.6d)

Both logic functions need the **full `Card`** (`oracle_text`, `type_line`, `cmc`, `legalities`), so load via `get_deck_with_cards` (eager full cards) — **not** the lightweight `DeckCardSummary`/`CardSummary` projections (they drop `oracle_text`/`legalities`). The two functions want **different shapes** (mirror the legacy wrappers exactly):

```python
# analyze_mana_curve — mainboard expanded by quantity into list[Card]; sideboard excluded
all_cards = [dc.card for dc in deck.deck_cards if not dc.sideboard for _ in range(dc.quantity)]
if not all_cards:                     # pre-check: analyze_mana_curve raises ValueError on []
    return ManaCurveResult(status="empty", deck_id=deck_id, deck_name=deck.name,
                           message=f"Deck '{deck.name}' has no mainboard cards to analyze.")
analysis = _logic_analyze_mana_curve(all_cards)   # @dataclass ManaCurveAnalysis

# detect_synergies — mainboard list[DeckCard], NOT expanded (it weights by quantity itself)
mainboard = [dc for dc in deck.deck_cards if not dc.sideboard]
if not mainboard:
    return SynergyResult(status="empty", deck_id=deck_id, deck_name=deck.name,
                         message=f"Deck '{deck.name}' has no mainboard cards to analyze.")
analysis = _logic_detect_synergies(mainboard)      # Pydantic SynergyAnalysis
```

### Serialization — flatten the dataclass, reuse the Pydantic models (D-1.6e)

`ManaCurveAnalysis` is a stdlib `@dataclass`; **flatten** its 8 fields onto `ManaCurveResult` (don't nest a dataclass in a Pydantic return — keep FastMCP schema-gen predictable):

```python
return ManaCurveResult(
    status="ok", deck_id=deck_id, deck_name=deck.name,
    distribution=analysis.distribution, total_lands=analysis.total_lands,
    total_spells=analysis.total_spells, average_cmc=analysis.average_cmc,
    playable_cards_by_turn=analysis.playable_cards_by_turn, land_ratio=analysis.land_ratio,
    issues=analysis.issues, recommendations=analysis.recommendations,
    message=(f"Curve analyzed: {analysis.total_spells} spells / {analysis.total_lands} lands, "
             f"avg CMC {analysis.average_cmc:.2f}."),
)
```

`SynergyAnalysis`/`SynergyPattern` and `DeckValidationReport` are already Pydantic → reuse/nest directly. **Gotcha:** `SynergyAnalysis.total_count` is a `@property`, so it is **absent** from `model_dump()`/`structuredContent` — copy it into an explicit `synergy_count` field (`synergy_count=analysis.total_count`). **Gotcha:** `distribution`/`playable_cards_by_turn` are `dict[int, int]`; JSON object keys are **strings**, so the harness/client sees `{"1": 4, ...}` — assert string keys in Task-6 client tests (the helper-level tests see the typed model with int keys).

### Async-def tools + sync logic (the Epic-1 pattern — D-1.3a/1.4c)

All three tools are `async def` and `await` the async `DeckRepository.get_deck_with_cards` on FastMCP's event loop, then call the **pure sync** logic functions (no I/O) — **no** bridge, `asyncio.run()`, thread, or sync `ConnectionFactory` (that is Epic 2). Keep tool bodies thin: load → (pre-check empty) → call logic → shape `*Result`. Server registration mirrors deck-management:

```python
# src/mcp_server/server.py  (add alongside the deck tools)
from src.mcp_server.tools.deck_analysis import ManaCurveResult, SynergyResult, ValidateDeckResult
from src.mcp_server.tools.deck_analysis import analyze_mana_curve as _analyze_mana_curve_helper
from src.mcp_server.tools.deck_analysis import detect_synergies as _detect_synergies_helper
from src.mcp_server.tools.deck_analysis import validate_deck as _validate_deck_helper

    @mcp.tool()
    async def validate_deck(
        deck_id: str, format: str = "standard", games: list[str] | None = None
    ) -> ValidateDeckResult:
        """Validate a deck's construction legality (size, copy limits, format legality). ..."""
        async with session_factory() as session:
            return await _validate_deck_helper(session, deck_id=deck_id, format=format, games=games)
    # ... analyze_mana_curve(deck_id) and detect_synergies(deck_id), same shape ...
```

`Literal`, `str`, `list[str] | None`, `dict[int, int]`, nested Pydantic models all serialize into the FastMCP tool schema (verified across 1.3–1.5). Keep `deck_id`/`format`/`games` param names.

### Graceful paths (AC4 / D-1.6f) — the matrix

| Input | `analyze_mana_curve` | `detect_synergies` | `validate_deck` |
|---|---|---|---|
| bogus `deck_id` | `deck_not_found` | `deck_not_found` | `deck_not_found` |
| empty mainboard | `empty` | `empty` | `ok` + `is_legal=False` (`min_deck_size`) |
| bad `games` value | n/a | n/a | `invalid` |
| `DatabaseError` | `error` | `error` | `error` |
| normal | `ok` | `ok` | `ok` |

`isError` stays `False` on **every** structured path (verified 1.3–1.5 — graceful `not_found`/`empty`/`invalid`/`error` results are normal returns, not MCP errors).

### Testing — patterns and traps (carried from Stories 1.3–1.5)

- **Logic unit tests** (`tests/unit/logic/test_deck_validator.py`): build `Card`/`DeckCard`/`Deck` Pydantic objects in-memory (no DB/session) — the existing logic tests already do this; `tests.*` is exempt from `mypy --strict` but must stay ruff-clean.
- **Helper tests** (`test_deck_analysis_tool.py`): own file-backed engine + one shared `session`, seed a **richer** card set (lands/Goblins/varied-CMC/non-legal/paper-only) and build decks via `DeckRepository`. This is where the deep coverage lives.
- **End-to-end harness** (`test_mcp_tools.py`): separate connections → **must** use the **file-backed** `seeded_card_db` (`:memory:` gives each connection its own empty DB). Build the deck **through the tools**; **do not edit** the shared 3-card fixture (1.3–1.5 depend on it). Remember **string dict keys** in `structuredContent` (`distribution["1"]`).
- pytest config ([pyproject.toml](../../pyproject.toml)): `asyncio_mode = "auto"` → write `async def test_...`, **no** `@pytest.mark.asyncio`. Layout mirrors `src/`.
- **Known-flaky (out of scope):** `test_deck_repository.py::test_list_decks` ties on `created_at` ordering — intermittent in full-suite runs, passes in isolation ([deferred-work.md](./deferred-work.md)). Don't "fix" it.

### Anti-patterns (do NOT do these)

- ❌ Re-implement curve/synergy/legality math in the tool — call `src/logic`. The tool layer holds **no** domain logic; the only new logic is the additive `validate_deck` in the **logic** module.
- ❌ Modify any existing `src/logic` function (`analyze_mana_curve`/`detect_synergies`/`validate_card_addition`/`is_basic_land`/`get_current_card_count`/`generate_contextual_feedback`) — the change is **purely additive** (`validate_deck`). NFR7.
- ❌ Feed the logic the lightweight projections — `CardSummary`/`DeckCardSummary` drop `oracle_text`/`legalities`; load the **full** deck via `get_deck_with_cards`.
- ❌ Call `analyze_mana_curve([])` — it **raises `ValueError`**; pre-check the empty mainboard → `status="empty"`.
- ❌ Expect `total_count` in `structuredContent` — it's a **property**; surface `synergy_count` explicitly.
- ❌ Nest the `ManaCurveAnalysis` dataclass in a Pydantic result — **flatten** its fields.
- ❌ Reintroduce server state — no active-deck, format-filter, or session; `deck_id`/`format`/`games` are per-call (FR3/D5).
- ❌ Port `generate_contextual_feedback` / auto-feedback — dropped (D5); it's the Epic-3 skill's job.
- ❌ Return HTML/markdown report strings or import `legacy.ui.formatters` / `legacy.agent.*` (pulls `pydantic_ai`, absent from the lean core).
- ❌ Surface raw exceptions — every failure path returns a structured `status` + message (wrap repo calls in `try/except DatabaseError → "error"`).
- ❌ Count the 4-copy limit mainboard-only via `get_current_card_count` — the whole-deck rule is **combined** main+side; compute directly.
- ❌ Use the sync `ConnectionFactory`/raw `sqlite3` — Epic 2's vector seam; these tools `async def`-await the async repo.
- ❌ Edit the shared `seeded_card_db` fixture or assert against a `:memory:` DB across separate sessions in the harness test.
- ❌ `print()` in library code; naive `datetime` (these tools don't stamp time, but keep the rule).

### Previous Story Intelligence (Stories 1.1–1.5 — done)

- **1.3** stood up the server skeleton: `build_server(session_factory)` with closure-registered `async def` tools, the `tools/<name>.py` helper + structured-`*Result` convention, the file-backed `seeded_card_db` fixture, and the `create_connected_server_and_client_session` harness. **Reuse all of it.**
- **1.4** added the **validate-first, never-raise** helper shape, the `_VALID_GAMES`/`_VALID_RARITIES` validation vocabularies (reuse `_VALID_GAMES`), the private-alias helper import in `server.py`, and the two-tier (helper + harness) test split. Confirmed `Literal`/union param types serialize cleanly and graceful paths keep `isError=False`.
- **1.5** is the closest template: six `async def` deck tools wrapping `DeckRepository`, the **`"error"` status on `DatabaseError`** in *every* helper (a 1.5 review fix — do this here too), `_blank_to_none` input normalization, the additive-only `src/data` discipline (1.6's analogue is the additive-only `src/logic` `validate_deck`), and the harness test that builds decks **through the tools** against the shared fixture. The deck **projections** it added (`DeckSummary`/`DeckDetail`) are **not** reused here — 1.6 needs full cards, so it loads `Deck` directly.
- **1.4/1.5 review lessons heeded here:** normalize degenerate inputs **before** validating/calling (here: `deck_id.strip()`, `format` blank→`"standard"`, `games` value check); catch `DatabaseError` in **all** helpers, not just one.
- **Known-flaky (out of scope):** `test_deck_repository.py::test_list_decks` `created_at`-tie ([deferred-work.md](./deferred-work.md)).
- Team patterns to match: thorough Dev Notes, **run-and-capture** verification, strict scope discipline, additive-only domain-layer changes.

### Git Intelligence

- HEAD **`2f812f8`** "feat: add deck-management MCP tools + deck projections + CardRepository.get_by_id (Story 1.5)" — the **baseline** for 1.6 (working tree clean). Branch `feat/mcp-server-architecture`; **Conventional Commits**, one focused `feat:` per story.
- Cadence (`2f812f8` 1.5 · `0e71117` 1.4 · `d2e7d32` 1.3 · `02d8d40` 1.1+1.2 close · `4a77364` ConnectionFactory) confirms: scope-disciplined, additive, test-backed. Suggested message: `feat: add deck-analysis MCP tools (analyze_mana_curve / detect_synergies / validate_deck) + logic.validate_deck (Story 1.6)`. **Story 1.6 closes Epic 1** — after `done`, the optional `epic-1-retrospective` and Epic 2 become available.

### Latest Tech / Versions (verified during Stories 1.3–1.5 — reconfirm only if something breaks)

| Item | Value | Source / Action |
|---|---|---|
| MCP SDK | installed **`mcp 1.28.0`** (pin `mcp>=1.27.0`) | [pyproject.toml](../../pyproject.toml) |
| Server / tool API | `from mcp.server.fastmcp import FastMCP`; `@mcp.tool()`; `async def` tools awaited on the server loop | in use ([server.py](../../src/mcp_server/server.py)) |
| Structured output | typed/Pydantic return → `CallToolResult.structuredContent`; `isError=False` on graceful paths; **`dict[int,int]` keys serialize as strings**; **`@property` fields are omitted** | verified 1.3–1.5 + this story's gotchas |
| In-memory client | `mcp.shared.memory.create_connected_server_and_client_session(server)` | in use ([test_mcp_tools.py:10](../../tests/integration/test_mcp_tools.py#L10)) |

> **No new dependency** is needed — pure logic + the existing async repository. `pydantic` (already a core dep, already imported by `src/logic/synergy.py`) backs the new `DeckValidationReport`/`DeckViolation`.

### Project Structure Notes

Target additions/edits (everything else unchanged):

```
src/
  logic/
    deck_validator.py            # MODIFIED — additive validate_deck() + DeckValidationReport/DeckViolation (existing fns unchanged)
  mcp_server/
    server.py                    # MODIFIED — register 3 async analysis tools (closures over session_factory)
    tools/deck_analysis.py       # NEW — 3 helpers + 3 *Result schemas
tests/
  unit/
    logic/test_deck_validator.py            # MODIFIED — validate_deck unit coverage (TestValidateDeck)
  integration/
    mcp_server/test_deck_analysis_tool.py   # NEW — helper-level curve/synergy/legality coverage
    test_mcp_tools.py                       # MODIFIED — end-to-end analysis via the in-memory MCP client
```

- **Alignment:** matches spec §5 (Analysis tools = `analyze_mana_curve`/`detect_synergies`/`validate_deck`, FR9–FR11; tools wrap `src/logic`) and §5.2 (format/games as **parameters**, statelessness D5). Import direction stays `logic → mcp_server` and `data → mcp_server` (no upward imports). The new validator stays in `src/logic` per the layer contract. [Source: [design spec §5](../../docs/architecture.md)]
- **Variances to record (Dev Agent Record):** (a) `validate_deck` is a **new** logic-layer function (no legacy whole-deck validator existed to port) — the one additive `src/logic` change, D-1.6a; (b) it implements the **constructed 60-card** rule generically (Commander/singleton out of scope — D-1.6b); (c) `games` is an **optional advisory** availability check (D-1.6c); (d) the throttled `generate_contextual_feedback` auto-feedback is **not** ported (D-1.6g); (e) `ManaCurveResult` **flattens** the dataclass while `SynergyResult` reuses the logic Pydantic models + an explicit `synergy_count` (the `total_count` property is non-serializing — D-1.6e).

### References

- [epics.md — Epic 1 / Story 1.6](../planning-artifacts/epics.md) — user story + ACs (FR9, FR10, FR11, FR3, NFR7).
- [design spec §5 / §5.2 / §8](../../docs/architecture.md) — analysis tool catalog, statelessness (format/games as params, D5), in-process MCP test approach.
- [project-context.md](../project-context.md) — MCP rules (structured returns, wrap logic/repos, sync-vs-async, `format`-as-param), layer contract (`src/data`/`src/logic` are the framework-free core; repos return schemas), testing layout, ruff/mypy gates.
- Logic to wrap: [mana_curve.py:58](../../src/logic/mana_curve.py#L58) (`analyze_mana_curve`, raises on `[]`), [synergy.py:80](../../src/logic/synergy.py#L80) (`detect_synergies`) + [synergy.py:36](../../src/logic/synergy.py#L36) (`SynergyPattern`/`SynergyAnalysis`, `total_count` property), [deck_validator.py:30](../../src/logic/deck_validator.py#L30) (`is_basic_land`; where `validate_deck` is added).
- Data: [deck.py:521](../../src/data/repositories/deck.py#L521) (`get_deck_with_cards`, eager full cards), [schemas/deck.py:14](../../src/data/schemas/deck.py#L14) (`DeckCard` nests full `Card`), [schemas/card.py:47](../../src/data/schemas/card.py#L47) (`legalities: dict[str,str]`) + [schemas/card.py:57](../../src/data/schemas/card.py#L57) (`games: list[str]`).
- Tool patterns to mirror: [server.py](../../src/mcp_server/server.py) (wrappers/private-alias imports), [tools/deck_management.py](../../src/mcp_server/tools/deck_management.py) (`*Result`+`"error"` convention, helper shape), [tools/card_search.py:25](../../src/mcp_server/tools/card_search.py#L25) (`_VALID_GAMES`).
- Legacy behavior (logic/scoping/wording only — **drop** RunContext/active-deck/HTML/auto-feedback): [mana_curve.py](../../legacy/agent/tools/mana_curve.py), [synergy_detection.py](../../legacy/agent/tools/synergy_detection.py); legacy inline legality lives in [deck_tools.py:194](../../legacy/agent/tools/deck_tools.py#L194) (`card.legalities.get("standard") != "legal"`).
- Tests: [test_mcp_tools.py](../../tests/integration/test_mcp_tools.py) (harness + deck-lifecycle), [test_deck_management_tool.py](../../tests/integration/mcp_server/test_deck_management_tool.py) (helper-test pattern), [conftest.py:81](../../tests/integration/conftest.py#L81) (`seeded_card_db`), [tests/unit/logic/test_deck_validator.py](../../tests/unit/logic/test_deck_validator.py) (logic-unit pattern).
- [Story 1.5](./1-5-deck-management-tools.md) — `"error"`-on-`DatabaseError`, validate-first, private-alias import, two-tier tests, additive-only ethos. [deferred-work.md](./deferred-work.md) — `list_decks` flaky-order note.

## Dev Agent Record

### Agent Model Used

claude-opus-4-8[1m] (Claude Opus 4.8, 1M context) — BMAD dev-story workflow.

### Debug Log References

No HALT conditions or blocking failures. Verification commands run clean (Task 7):

- `uv run pytest tests/integration/mcp_server/test_deck_analysis_tool.py tests/integration/test_mcp_tools.py tests/unit/logic/test_deck_validator.py -v` → **63 passed**.
- `uv run pytest tests/` → **417 passed**, 0 failed (the known-flaky `test_list_decks` `created_at`-tie also passed this run; no new failures; existing `tests/unit/logic/` suites green → NFR7).
- `uv run ruff check .` / `uv run ruff format --check .` → all **Story-1.6 files clean**. Pre-existing, out-of-scope non-conformance remains only in untouched files (`_bmad/scripts/tests/test_resolve_customization.py` import sort; `_bmad/scripts/*` + `src/mcp_server/tools/card_lookup.py` formatting) — not introduced or modified by this story.
- `uv run mypy src/` → **Success: no issues found in 40 source files** (strict).

One in-flight fix: the `copy_limit` violation detail f-string exceeded the 100-char line limit (E501); wrapped across two concatenated f-strings (no behavior change).

### Completion Notes List

- **AC1 (analyze_mana_curve / FR9):** `deck_analysis.analyze_mana_curve` loads via `DeckRepository.get_deck_with_cards`, expands the **mainboard** by quantity into `list[Card]` (sideboard excluded), calls the **unchanged** `src.logic.mana_curve.analyze_mana_curve`, and returns a `ManaCurveResult` with the **flattened** 8 analysis fields. No curve math in the tool. ✅
- **AC2 (detect_synergies / FR10):** passes the **un-expanded** mainboard `list[DeckCard]` to the **unchanged** `src.logic.synergy.detect_synergies`; `SynergyResult` reuses `SynergyPattern` and surfaces `synergy_count` explicitly (the `total_count` `@property` does not serialize — D-1.6e). ✅
- **AC3 (validate_deck / FR11, FR3):** `format`/`games` are per-call **parameters**; the report covers 60+ mainboard, ≤15 sideboard, ≤4 non-basic copies (combined boards), and per-card format legality — no server-side state (verified by the standard→modern same-deck assertion). ✅
- **AC4 (graceful inputs):** bogus `deck_id` → `deck_not_found` (all three); empty mainboard → `empty` (curve & synergy) while `validate_deck` returns `status="ok"` + `is_legal=False` with a `min_deck_size` violation; bad `games` value → `invalid`; `DatabaseError` → `error` (every helper wraps the repo call). `isError` stays `False` on every structured path. ✅
- **AC5 (one additive logic change / NFR7):** the **only** logic-layer addition is `validate_deck(...)` + `DeckValidationReport`/`DeckViolation` in `src/logic/deck_validator.py`; `analyze_mana_curve`, `detect_synergies`, `validate_card_addition`, `is_basic_land`, `get_current_card_count`, `generate_contextual_feedback` are byte-for-byte unchanged. Existing `test_mana_curve.py` / `test_synergy.py` / `test_deck_validator.py` suites pass. ✅
- **AC6 (bounded payloads):** each tool returns a typed `*Result` carrying counts/distributions/named violations/synergy patterns (with card **names** as strings) — no full-`Card` dumps, HTML, or markdown (asserted via `model_dump_json` containing no `legalities`/`image_uris`/`oracle_text`). ✅
- **AC7 (in-memory harness):** `test_mcp_tools.py` builds a deck **through the tools** against the shared file-backed `seeded_card_db` and drives all three analysis tools via `create_connected_server_and_client_session` (no subprocess), including the `deck_not_found` smoke for each. Remembered the **string** dict keys in `structuredContent` (`distribution["1"]`). ✅
- **Variances recorded (per Project Structure Notes):** (a) `validate_deck` is a **new** logic-layer function — no legacy whole-deck validator existed to port (D-1.6a); (b) it implements the **constructed 60-card** rule generically — Commander/singleton/100-card minima are out of Phase-1 scope (D-1.6b); (c) `games` is an **optional advisory** availability check (D-1.6c); (d) the throttled `generate_contextual_feedback` auto-feedback is **not** ported (D-1.6g); (e) `ManaCurveResult` **flattens** the `ManaCurveAnalysis` dataclass while `SynergyResult`/`ValidateDeckResult` reuse the logic Pydantic models, with `synergy_count` surfaced explicitly (D-1.6e).
- **Story 1.6 closes Epic 1.** After it reaches `done`, the optional `epic-1-retrospective` and Epic 2 become available.

### File List

- `src/logic/deck_validator.py` — MODIFIED (additive `validate_deck()` + `DeckValidationReport`/`DeckViolation`; existing functions untouched).
- `src/mcp_server/tools/deck_analysis.py` — NEW (3 helpers + `ManaCurveResult`/`SynergyResult`/`ValidateDeckResult`).
- `src/mcp_server/server.py` — MODIFIED (registered 3 async analysis tool wrappers + private-alias imports).
- `tests/unit/logic/test_deck_validator.py` — MODIFIED (added `TestValidateDeck` + builder helpers).
- `tests/integration/mcp_server/test_deck_analysis_tool.py` — NEW (helper-level curve/synergy/legality coverage).
- `tests/integration/test_mcp_tools.py` — MODIFIED (end-to-end analysis via the in-memory MCP client + graceful smoke).
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — MODIFIED (Story 1.6 → in-progress → review).

## Change Log

| Date | Change |
|---|---|
| 2026-06-20 | Created Story 1.6 (Deck Analysis Tools). Locked 7 decisions with Brad (D-1.6a–g): additive logic-layer `validate_deck`, constructed-60-card rules / Standard default, optional `games` availability check, full-deck mainboard-only inputs, flatten-dataclass/reuse-Pydantic serialization, graceful empty/error handling, drop auto-feedback. Status → ready-for-dev. |
| 2026-06-20 | Implemented Story 1.6: additive `src.logic.deck_validator.validate_deck` (+ `DeckValidationReport`/`DeckViolation`); new `src/mcp_server/tools/deck_analysis.py` (3 helpers + `*Result` schemas); registered `analyze_mana_curve` / `detect_synergies` / `validate_deck` in `build_server`. Added logic unit tests (`TestValidateDeck`), helper-level integration tests, and end-to-end MCP-harness tests. All ACs satisfied; 417/417 tests pass, mypy/ruff clean on Story-1.6 files. Status → review. |
