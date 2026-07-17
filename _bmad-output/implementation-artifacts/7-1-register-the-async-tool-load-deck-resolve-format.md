---
baseline_commit: e2b03ff
---

# Story 7.1: Register the async tool; load deck & resolve format

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an agent,
I want to call `assess_deck_power(deck_id, format?)` and have it load the right deck data and format,
so that assessment starts from correct, complete inputs.

## Acceptance Criteria

1. **Async tool registered, stateless.** `assess_deck_power` is registered in
   `src/mcp_server/server.py` as an **`async def`** tool, a sibling to `analyze_mana_curve` /
   `detect_synergies` / `validate_deck` — same shape: `@mcp.tool()` nested in `build_server`,
   thin wrapper opening `async with session_factory() as session:` and delegating to a helper in
   the new `src/mcp_server/tools/assess_deck_power.py` (the spine's seed filename, AD-1/AD-9).
   Inputs are exactly `deck_id: str` and `format: str | None = None` — no per-session state
   (FR1, NFR7). The docstring is the LLM-facing tool description (Google style, like siblings).

2. **Deck loads via the full-Card path.** The helper loads the deck with
   `DeckRepository.get_deck_with_cards(deck_id)` — full nested `Card` rows incl. `legalities`,
   `keywords`, `oracle_text`, `game_changer`, `cmc`, `type_line` — never the
   `CardSummary`/`load_deck` projection (FR1). Assessment consumes **mainboard only**
   (`sideboard=False` rows), matching the benchmark + G-R2 harness wiring.

3. **Format resolution, graceful when unsupported (FR2).** `format` accepts
   `commander | standard` (after `.strip().lower()`). When omitted/None it is inferred
   deterministically from the deck's stored `Deck.format` (and the commander flag as a
   structural signal — see Dev Notes ladder). Any unsupported/unrecognized outcome (explicit
   param or stored value — e.g. `brawl`, `standardbrawl`, `historic`, `modern`, `None`) returns
   a graceful `unsupported_format` result that **names the supported formats** and the
   `format=` override workaround — never a crash, never a guessed profile. The resolved format
   selects the profile: `commander → COMMANDER_PROFILE`, `standard → STANDARD_PROFILE` (a new
   explicit map — none exists yet).

4. **Status enum + graceful error paths (AD-7 subset).** A new Pydantic
   `AssessDeckPowerResult` carries `status: Literal["ok", "deck_not_found",
   "unsupported_format", "database_not_initialized", "error"]`, an always-present
   `schema_version`, a human `summary: str`, `deck_id` echo, and `assessment: None = None`
   (placeholder — 7.3 widens it to the full assessment block). Behavior mirrors the
   `validate_deck` 4-step pattern exactly: param normalize → `is_database_initialized(session)`
   check → `database_not_initialized`; missing deck → `deck_not_found`; `DatabaseError` →
   `status="error"` (message, no traceback). No exception ever reaches the MCP client.

5. **Card resolution count captured (FR3).** Every deck card is resolved against the local
   snapshot through the `get_deck_with_cards` join; the helper counts unresolved/ambiguous rows
   (a `DeckCard` whose nested `card` is missing/unloadable) into an `unresolved_count: int`
   carried on the resolved-inputs seam for 7.2's `cards_unresolved` confidence reason. The
   count is structural (FK join ⇒ normally 0) — do not invent a name-matching pipeline.

6. **Commander resolution per AD-13 (FR25 edge half) — strict order, honest degrade:**
   1. **Flagged first:** mainboard rows with `commander=True` (1 or 2 = partners). Names are
      the stored `card.name` verbatim (DFC full names included — no normalization here).
   2. **Sole-legendary inference:** if none flagged AND resolved format is `commander`, a
      **sole legendary creature** in the mainboard (exactly one distinct qualifying name) is
      inferred as commander with **no confidence penalty**.
   3. **Unknown:** otherwise commanders resolve to `()` with outcome `unidentified` —
      commander-required variants will be skipped and `commander_unidentified` added by 7.2.
   Degenerate flag states (6.1 review deferral, this story's scope) resolve **honestly, read-side
   only**: >2 flagged rows, or flagged rows only in the sideboard → treat as `unidentified`
   (log a warning; never crash, never silently pick a subset). Sideboard-flagged rows are never
   commanders (mainboard-only guard).

7. **Resolved-inputs seam for 7.2/7.3.** The helper's happy path assembles a frozen internal
   carrier (e.g. `ResolvedDeckInputs`: deck, mainboard `DeckCard`s, resolved format, profile,
   commanders tuple, commander-resolution outcome, `unresolved_count`) and returns a provisional
   `status="ok"` result whose `summary` states resolution facts (deck name, format, profile
   version, commanders or "unidentified", unresolved count) and marks scoring as pending 7.2/7.3.
   **No `score()` call, no combo provisioning, no confidence tokens, no `data_vintage` in this
   story.** (Interim shape is safe: feature branch ships only after Epic 7 completes.)

8. **Type + lint gates pass.** `mypy --strict` over `src/`, `ruff check` + `ruff format`,
   pre-commit succeeds without `--no-verify` (the `build-plugin-sync` hook re-mirrors
   `src/` → `plugin/server/`).

9. **Tests prove every path offline (no live DB, no network).** Helper-level integration tests
   (new `tests/integration/mcp_server/test_assess_deck_power_tool.py`, fixture stack copied
   from `test_deck_analysis_tool.py`) cover: format ladder (explicit param beats stored; case/
   whitespace normalization; stored `commander`/`standard`; brawl-family + unknown + `None` →
   `unsupported_format` naming supported formats; unsupported explicit param); commander
   resolution (flagged 1, flagged 2 partners, >2 flagged → unidentified, sideboard-flagged
   ignored, sole-legendary inference, multiple legendaries → unidentified, non-commander format
   never infers); mainboard-only filtering; `deck_not_found`; `database_not_initialized`
   (engine without `init_database` — a branch siblings left thin). In-process MCP client tests
   extend `tests/integration/test_mcp_tools.py`: tool listed + callable, `structuredContent`
   round-trip, and `assess_deck_power` joins `test_analysis_tools_on_bogus_deck_are_graceful`.

## Tasks / Subtasks

- [x] Task 0: Story-start state verification (standing team agreement) (AC: all)
  - [x] `uv run pytest --collect-only -q | tail -1` — confirm full-suite baseline **1,239**
        (6.3's verified count); record the actual number in Dev Agent Record.
  - [x] Confirm no `assess_deck_power` exists anywhere in `src/` yet (grep), and that
        `from src.logic.assessment import score, COMMANDER_PROFILE, STANDARD_PROFILE` imports
        cleanly (`uv run python -c ...`).
  - [x] Confirm `DeckCard.commander` exists in `src/data/schemas/deck.py` (6.1 shipped) and
        `DeckRepository.get_deck_with_cards` returns nested full `Card`s (read the method).
- [x] Task 1: Result model + module skeleton (TDD — test file first) (AC: 4)
  - [x] Create `src/mcp_server/tools/assess_deck_power.py` with module docstring;
        `AssessDeckPowerResult` (status Literal, `schema_version: str = "1"` always present,
        `summary: str`, `deck_id: str | None = None`, `assessment: None = None`).
  - [x] Enumerate **every construction site** of the result (one per early-return + happy path)
        — epic-6 retro discipline; Pydantic required fields keep omissions loud.
- [x] Task 2: Format resolution + profile map (AC: 3)
  - [x] `_FORMAT_PROFILES: Final = {"commander": COMMANDER_PROFILE, "standard": STANDARD_PROFILE}`
        (module-level, the first format→profile map in the codebase — decide-once, documented).
  - [x] Resolution ladder helper (pure, unit-testable): explicit param → stored `Deck.format`
        → commander-flag structural signal → `unsupported_format`. Document the brawl-family
        decision (G-R2 calibration input) in the docstring + the result `summary` workaround.
- [x] Task 3: Deck load + status paths (AC: 2, 4, 5)
  - [x] Mirror `validate_deck`'s helper pattern (`deck_analysis.py`): strip params,
        `is_database_initialized`, `try/except DatabaseError`, `deck is None → deck_not_found`.
  - [x] Filter `sideboard=False`; compute `unresolved_count` defensively.
- [x] Task 4: Commander resolution (AC: 6, 7)
  - [x] Legendary-creature check (none exists in `src/` — write it): `type_line` contains
        `"legendary"` and `"creature"` case-insensitively, front face only for DFC type_lines
        (split on `" // "` first, `synergy.py::_extract_creature_types` precedent).
  - [x] Strict AD-13 order + degenerate-state policy (>2 flagged / sideboard-flagged → 
        `unidentified` + `logger.warning` with lazy `%s` args).
  - [x] `ResolvedDeckInputs` frozen carrier + provisional ok-path `summary`.
- [x] Task 5: Register tool + MCP client tests (AC: 1, 9)
  - [x] `@mcp.tool()` async wrapper in `server.py` (import helper as `_assess_deck_power_helper`
        alias, matching siblings); Google-style docstring = tool description.
  - [x] Extend `test_mcp_tools.py` (bogus-deck graceful loop + happy-path structuredContent).
- [x] Task 6: Quality gates + story wrap-up (AC: 8)
  - [x] `uv run ruff check . --fix && uv run ruff format .`; `uv run mypy src/`;
        `uv run pytest` full suite green; pre-commit (plugin mirror will add
        `plugin/server/src/mcp_server/...` files — expected, commit them).
  - [x] Update this story file (Dev Agent Record, File List, Change Log); status → review.
        Conventional Commit: `feat: assess_deck_power async tool — load deck & resolve format (story 7.1)`.

## Dev Notes

### What this story is (and is NOT)

The **ingest/resolve slice** of the `assess_deck_power` edge (feature Story 4.1, sprint key
`7-1`): tool registration, deck load, format→profile resolution, card-resolution counting,
commander resolution, and the graceful non-ok statuses. It does **NOT** include:

- **Combo provisioning / degradation ladder** — reading `ComboSnapshotRepository`, the
  `combo_data_unavailable` / `cards_unresolved` / `game_changer_data_unavailable` /
  `commander_unidentified` confidence tokens, and level assembly are **Story 7.2**. This story
  only *captures the facts* (counts, resolution outcomes) on the seam 7.2 consumes.
- **`score()` invocation, `assessment` block, `data_vintage`, deterministic serialization,
  human summary projection** — **Story 7.3** (AD-7/AD-8). The `assessment: None` placeholder
  and `schema_version` land here; 7.3 widens and finalizes them.
- **`compare_deck_power`** — Story 7.5.
- **Write-path commander validation and any set-commander API** — the 6.1 review deferred a
  count cap / cross-field guard on the *write* paths and a flag-mutation API; the write-path
  guard and set-commander belong to a future deck-edit story. **This story handles degenerate
  flag states read-side only** (resolve honestly to `unidentified`, warn, never crash).
- **Any change to `src/logic/` or `src/data/`** — `score(deck_cards, *, commanders, variants,
  profile)` already takes resolved commanders (Epic 5); the repositories are done (6.3). If a
  lower layer seems wrong, stop and surface it.

### Critical code facts (verified 2026-07-17)

- **The Epic-1 deck tools are ALREADY `async def`** — the new tool is the *normal* pattern,
  not an exception. server.py module docstring: "The Epic-1 tools are `async def` and `await`
  the async `src/data` repositories directly on the FastMCP event loop (D-1.3a)." Only the
  Epic-2 vector tools are sync (sqlite-vec needs the sync connection — not applicable here).
  No asyncio bridge anywhere; just `await`.
- **Registration shape** (copy `validate_deck`, server.py:438-468): nested in
  `build_server(...)`, `@mcp.tool()`, `async with session_factory() as session: return await
  _helper(session, ...)`. Helpers live module-level in `src/mcp_server/tools/*.py`, take
  `session: AsyncSession` first, instantiate `DeckRepository(session)` themselves.
- **4-step error pattern** (deck_analysis.py:307-343): (1) `deck_id.strip()` +
  `format.strip().lower()`; (2) param validation before any DB touch; (3)
  `if not await is_database_initialized(session):` → `status="database_not_initialized"` with
  `DATABASE_NOT_INITIALIZED_MESSAGE` (from `src.mcp_server.tools.messages`); (4) repo call in
  `try/except DatabaseError` → `status="error"`; `None` → `deck_not_found` with
  `f"No deck found with id '{deck_id}'."`.
- **`get_deck_with_cards`** (deck.py:547): `async def (self, deck_id: str) -> Deck | None`;
  eager `selectinload` deck_cards→card; returns Pydantic `Deck`, `None` when missing (no
  raise). `DeckCard` has `sideboard: bool`, `commander: bool = False`, `card: Card`. `Card`
  has `cmc: float`, `type_line: str`, `oracle_text: str` (NULL→`""`), `keywords`,
  `legalities: dict[str,str]` (NULL→`{}`), `game_changer: bool | None` (never coalesce).
- **`Deck.format`** is free-text `str | None` (default `"standard"` at create; real DB holds
  `standard`, `historic`, `brawl`, `standardbrawl`). Siblings take `format` as a per-call
  param and don't read the stored value — this tool is the first to read `deck.format`.
- **Scorer API** (scorer.py:109): `score(deck_cards, *, commanders: Sequence[str],
  variants: Sequence[ComboRecord], profile: FormatProfile) -> CoreAssessment` — keyword-only;
  param name is `variants`, not `combos`. NOT called in this story, but the seam must carry
  exactly what it needs: mainboard `DeckCard`s + resolved commander **names**.
- **Profiles** (profiles.py:132, 168): `COMMANDER_PROFILE`
  (`format_profile_version="commander-v4"`, `rubric="brackets"`), `STANDARD_PROFILE`
  (`"standard-v4"`, `"heuristic_only"`). Both exported from `src.logic.assessment`.
  **No format→profile map exists anywhere — this story authors the first one.**
- **No legendary-creature helper exists** (`grep -i legendary src/` = zero hits) — write the
  check in this module. Type-line precedents are ad-hoc lowercase `in` checks
  (`mana_base.py::_is_land`, `synergy.py` splits `" // "` for DFC faces).
- **Result models are Pydantic with `status: Literal[...]`** + required message-ish string +
  `deck_id` echo (`ManaCurveResult`, `ValidateDeckResult`, …). **No `schema_version` exists
  anywhere yet — this story establishes the precedent** (AD-7 requires it always-present).
  This result uses `summary` (AD-7's field name), a deliberate divergence from siblings'
  `message` — document it in the model docstring.
- **`CoreAssessment` is a frozen dataclass, not Pydantic** — when 7.3 projects it, dataclass
  `@property` values are invisible to `structuredContent` (the `SynergyResult.synergy_count`
  precedent). Not this story's problem, but don't design the seam assuming auto-serialization.

### Format-resolution ladder (decide-once, documented)

Deterministic, produces only `commander | standard`, never crashes:

1. **Explicit `format` param** (after `.strip().lower()`): in the map → use it; non-empty but
   unsupported → `unsupported_format` naming `commander, standard`.
2. **Stored `Deck.format`** (`.strip().lower()` — it's free text): `"commander"` or
   `"standard"` → use it.
3. **Structural commander signal:** any mainboard `commander=True` row → `commander` (an
   explicitly flagged deck is a Commander-family deck; this also gives flagged Brawl decks a
   sensible default).
4. Anything else (brawl-family, `historic`, unknown, `None`) → `unsupported_format`. The
   `summary` must name the supported formats AND the workaround: pass `format="commander"` (or
   `"standard"`) explicitly to force a profile.

**Brawl-family decision (G-R2 calibration input, this story owns it):** G-R2 provisionally
mapped `brawl`/`standardbrawl` → `COMMANDER_PROFILE` in the throwaway harness and flagged the
mapping itself as provisional ("Epic 7 owns the real format→profile mapping"). The G-R2 run
also showed `mana_efficiency = 0` on **every** real Brawl deck under the Commander Karsten/pip
math — auto-mapping Brawl would bake that distortion in silently. Decision: **v1 keeps the
epic's closed `commander | standard` contract; brawl-family returns `unsupported_format` with
the explicit-override hint.** The caller can still force `format="commander"` — the choice is
then theirs and visible, not silent. Record this rationale in the ladder's docstring.

### Commander resolution (AD-13 + 6.1 review deferral)

Strict order — flagged → inferred → unidentified; each outcome is data on the seam:

- **Flagged:** mainboard rows with `commander=True`. 1 row = commander, 2 = partners
  (AD-13's invariant). Commander names = `card.name` verbatim (a flagged DFC row already
  stores the full `"Front // Back"` name — the G-R2 name_keys resolution dance existed only
  because that harness had no flags to read; with flags there is nothing to normalize).
- **Inferred:** no flags AND resolved format is `commander` → collect **distinct** mainboard
  card names whose type_line front face contains both `"legendary"` and `"creature"`
  (case-insensitive; split `" // "` and use face 0 — a back-face-only legendary creature is
  not castable from the command zone opener). Exactly one distinct name → that's the
  commander, **no penalty** (FR25). Zero or ≥2 → `unidentified`.
- **Unidentified:** commanders `()`. 7.2 emits `commander_unidentified` and skips
  commander-required variants; this story only records the outcome (e.g. a small
  `CommanderResolution` enum/Literal: `"flagged" | "inferred" | "unidentified"`).
- **Degenerate flag states** (the 6.1 deferral routed here): >2 flagged mainboard rows →
  `unidentified` + `logger.warning` (never pick a silent subset); `commander=True` rows in
  the sideboard → ignored by the mainboard-only guard (warn if they're the *only* flags).
  These states are reachable today — `add_card_to_deck(commander=True)` has no write-side cap.
- **Real-world note (G-R2):** ALL 20 live decks predate 6.1 → zero flags in the wild. The
  inference and `unidentified` paths are the *common* paths right now, not edge cases — test
  them as first-class. Note: legendary-planeswalker "can be your commander" cards are NOT
  inferred (FR25 scopes inference to legendary creatures); unflagged planeswalker-commander
  decks degrade honestly to `unidentified`.

### Previous-story intelligence (6.3 + epic-6 retro + G-R2)

- **6.3 shipped the exact seam 7.2 will consume**: `snapshot_is_available()` /
  `get_metadata()` / `get_variants_for_names()` — do not touch it here; do not pre-wire it.
- **Task 0 story-start verification is a standing team agreement** — it caught the httpx
  decompression trap (6.2) and a baseline off-by-one (6.3). Baseline: **1,239 passed / 0
  failed / 0 skipped** (verify, don't trust).
- **Construction-site enumeration** (epic-6 retro action item, first story it applies to):
  6.1's review found a flag dropped in a third, error-path constructor. `AssessDeckPowerResult`
  will be constructed at every early return — enumerate every site before claiming done;
  keep `schema_version`/`summary` required so omissions are loud.
- **Plugin mirror:** pre-commit `build-plugin-sync` re-mirrors `src/` → `plugin/server/src/`;
  expect new mirrored files for `tools/assess_deck_power.py` + the `server.py` diff in the
  commit. Tests/scripts are not mirrored.
- **G-R2 gate is CLOSED** (2026-07-17, all 20 decks accepted): calibration inputs
  (card_advantage saturation at 80, interaction railing 0/100, Brawl mana_efficiency floor,
  almost_included dominance, format-blind almost_included inflation) are **named Epic 7
  calibration inputs** — none is 7.1's to fix, but the Brawl observation feeds this story's
  format-ladder decision above. `CEDH_TUTOR_MIN=3` caveat carries over (dimensions.py:133).

### Architecture compliance checklist

- **AD-1:** async tool in `server.py` beside the analysis tools; `await`s repos on the FastMCP
  loop; stateless (`deck_id`/`format` only). Helper orchestrates only.
- **AD-7 (subset):** the status enum (`ok | deck_not_found | unsupported_format |
  database_not_initialized | error`), always-present `schema_version`, `summary`,
  `assessment` null on every non-ok status. Full assessment shape is 7.3's.
- **AD-13:** resolution order flagged → sole-legendary (Commander format only, no penalty) →
  unidentified; resolved list is plain data for the core; the core never queries for it.
- **AD-6 (respected at a distance):** no confidence tokens emitted here; facts (counts,
  outcomes) are captured for 7.2. Degradation never raises to the client.
- **AD-8 (respected at a distance):** nothing clock-derived anywhere — no `assessed_at`, no
  `now()` in the result or summary.
- **AD-9:** new logic lives in `src/mcp_server/tools/assess_deck_power.py` (edge); zero
  imports from `src/mcp_server` into `src/logic`/`src/data`; repositories return Pydantic.
- **NFR7:** no per-session server state; `format` param shadows the builtin intentionally
  (domain convention, ruff-accepted project-wide).

### Testing standards summary

- pytest config in `pyproject.toml`; `asyncio_mode = "auto"` (plain `async def test_...`);
  `--strict-markers`; `tests.*` exempt from `mypy --strict` (ruff/naming still apply).
- Helper-level: new `tests/integration/mcp_server/test_assess_deck_power_tool.py` — copy the
  fixture stack from `tests/integration/mcp_server/test_deck_analysis_tool.py` (file-backed
  `create_engine` → `init_database` → `create_session_factory` → seed `CardModel`s → decks via
  `DeckRepository.create_deck` + `add_card_to_deck(..., commander=)`).
- MCP-client-level: extend `tests/integration/test_mcp_tools.py` —
  `build_server(session_factory=seeded_card_db)` +
  `create_connected_server_and_client_session`; assert `result.isError is False` and
  `structuredContent["status"]`; add `assess_deck_power` to
  `test_analysis_tools_on_bogus_deck_are_graceful`.
- `database_not_initialized`: siblings left this branch thin — cover it (engine WITHOUT
  `init_database`, the 6.3 missing-tables test precedent).
- TDD order per task: test first (RED), implement (GREEN). No live DB, no network anywhere.

### Project Structure Notes

- New: `src/mcp_server/tools/assess_deck_power.py`,
  `tests/integration/mcp_server/test_assess_deck_power_tool.py`.
- Modified: `src/mcp_server/server.py` (import + registration),
  `tests/integration/test_mcp_tools.py`. (`src/mcp_server/tools/__init__.py` re-exports
  nothing — verified; server.py imports helpers by module path. No `__init__.py` change.)
- Generated: `plugin/server/src/mcp_server/...` mirrors (pre-commit hook).
- Naming: tool `assess_deck_power`; result `AssessDeckPowerResult`; modern 3.12 syntax
  (`X | None`, built-in generics); Google docstrings; module-level `logger` with `%`-style
  lazy args for the degenerate-state warnings.
- Branch: stays on `feat/deck-power-assessment` (no master merge until Epic 7 completes —
  epic-5 retro "experimental" release decision).

### References

- [Source: _bmad-output/planning-artifacts/epics-deck-power-assessment.md#Story 4.1] — story +
  ACs (epic file numbers this "4.1"; sprint tracks it as `7-1`); FR1/FR2/FR3/FR25 texts;
  Epic 4 preamble (FR/AD/NFR coverage).
- [Source: _bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-11/ARCHITECTURE-SPINE.md#AD-1]
  — async tool registration; #AD-7 status enum + `schema_version` + fixed shape; #AD-13
  commander resolution order; #AD-6 closed token enum (7.2); #AD-9 layer placement;
  Structural Seed (`tools/assess_deck_power.py`).
- [Source: _bmad-output/implementation-artifacts/pre-epic-7-real-deck-gate-report-2026-07-17.md]
  — G-R2 CLOSED ruling; brawl-family provisional-profile + Brawl `mana_efficiency=0`
  observation (format-ladder input); zero commander flags in the live DB; named calibration
  inputs list.
- [Source: _bmad-output/implementation-artifacts/deferred-work.md#Deferred from: code review of story-6-1]
  — the two 6.1 deferrals: degenerate commander-flag states (routed here, read-side) and
  set-commander API (NOT here — deck-edit story).
- [Source: _bmad-output/implementation-artifacts/epic-6-retro-2026-07-17.md#Action Items] —
  construction-site enumeration discipline; Task-0 standing agreement; 7.1/7.2 dependency map.
- [Source: src/mcp_server/server.py:438-468] — `validate_deck` registration, the wrapper shape
  to copy; server.py:106-107 default `session_factory` wiring.
- [Source: src/mcp_server/tools/deck_analysis.py:307-343] — the 4-step status pattern
  (`database_not_initialized` / `deck_not_found` / `DatabaseError` → error).
- [Source: src/data/repositories/deck.py:547-576] — `get_deck_with_cards` (Pydantic exit,
  `None` on missing, eager-loads full cards).
- [Source: src/data/schemas/deck.py:14-36] — `DeckCard.commander` / `sideboard` / nested
  `card`; deck.py:10,50 — `Deck.format` free-text `str | None`.
- [Source: src/logic/assessment/scorer.py:109-115] — `score()` keyword-only signature the seam
  must feed; profiles.py:132,168 — the two profile constants + `format_profile_version`.
- [Source: src/logic/synergy.py:550-566] — DFC `" // "` face-splitting precedent for the
  legendary-creature check.
- [Source: tests/integration/test_mcp_tools.py:337-347] —
  `test_analysis_tools_on_bogus_deck_are_graceful`, the graceful-tool test to extend.

## Dev Agent Record

### Agent Model Used

Claude Fable 5 (claude-fable-5) via Claude Code

### Debug Log References

- Task 0 baseline: `uv run pytest --collect-only -q` → **1,239 tests collected** (matches
  6.3's verified count exactly). Grep for `assess_deck_power` in `src/` → zero hits.
  `from src.logic.assessment import score, COMMANDER_PROFILE, STANDARD_PROFILE` imports
  cleanly (`commander-v4` / `standard-v4`). `DeckCard.commander` confirmed at
  `src/data/schemas/deck.py:27`; `get_deck_with_cards` confirmed returning nested full
  `Card`s via `selectinload` (deck.py:547-576).
- RED→GREEN: helper test file written first (collection error: module missing), then the
  module — 30/30 pass. MCP client tests written next (2 failed: tool not listed), then
  registration — 2/2 pass.
- Full-suite run surfaced one expected regression: `test_build_plugin.py::
  test_server_registers_expected_tools` pins the exact tool-registry set — added
  `assess_deck_power` (17 → 18 tools).
- Final gates: `ruff check` clean, `ruff format` applied, `mypy --strict src/` clean
  (69 files), full suite **1,270 passed / 0 failed**.

### Completion Notes List

- **Construction-site enumeration (epic-6 retro discipline):** `AssessDeckPowerResult` is
  constructed at exactly 5 sites in `assess_deck_power.py` — explicit-unsupported-format
  (pre-DB), `database_not_initialized`, `error` (DatabaseError), `deck_not_found`, and the
  ok path. `summary` is a required field (loud omission); `schema_version` defaults to the
  module `SCHEMA_VERSION = "1"` per the task spec, and every site was verified to carry it.
- **Format ladder (AC 3):** pure `_resolve_format(format, stored, *, has_flagged_commander)`
  — explicit param wins outright (unsupported never falls through), then stored
  `Deck.format`, then the mainboard commander-flag structural signal, else unresolved →
  `unsupported_format` naming `commander, standard` + the `format="..."` override hint.
  Brawl-family decision (G-R2 calibration input) recorded in the ladder docstring: v1 keeps
  the closed `commander | standard` contract because G-R2 showed `mana_efficiency = 0` on
  every real Brawl deck under Commander pip math — forcing the profile stays the caller's
  visible choice. Stored `None` is unreachable via the ORM (`DeckModel.format` is
  `nullable=False`) — covered by unit-testing the pure ladder directly.
- **Commander resolution (AC 6, AD-13):** flagged (1–2 mainboard rows, names verbatim,
  sorted for determinism) → sole-legendary inference (Commander format only, front face
  only for DFC type_lines, distinct-by-name, legendary *creatures* only — planeswalkers
  degrade honestly) → `unidentified`. Degenerate states read-side: >2 flagged →
  `unidentified` + warning (never a subset); sideboard-only flags → `unidentified` +
  warning (inference deliberately NOT applied over a degenerate flag state); sideboard
  flags alongside a valid mainboard flag are silently ignored (mainboard-only guard).
- **Seam for 7.2/7.3 (AC 7):** frozen dataclass `ResolvedDeckInputs` (deck, mainboard
  tuple, resolved format, profile, sorted commanders tuple, `commander_resolution`
  Literal, `unresolved_count`). No `score()` call, no combo provisioning, no confidence
  tokens, no `data_vintage`, nothing clock-derived. `_is_legendary_creature` is the
  codebase's first legendary-creature check (front-face `" // "` split per the synergy.py
  precedent).
- **Registration (AC 1):** `async def` `@mcp.tool()` nested in `build_server`, sibling to
  `validate_deck` — `async with session_factory() as session:` delegating to
  `_assess_deck_power_helper`. Inputs exactly `deck_id: str`, `format: str | None = None`;
  stateless. Google-style docstring doubles as the LLM-facing description and names the
  supported formats + override workaround.
- **`database_not_initialized` branch** covered with an engine that never ran
  `init_database` (the thin branch siblings left untested), asserting the exact
  `DATABASE_NOT_INITIALIZED_MESSAGE`.

### File List

- `src/mcp_server/tools/assess_deck_power.py` (new — helper, result model, ladder,
  commander resolution, `ResolvedDeckInputs` seam)
- `src/mcp_server/server.py` (modified — import + `assess_deck_power` tool registration)
- `tests/integration/mcp_server/test_assess_deck_power_tool.py` (new — 30 helper-level
  tests: ladder, commander resolution, degenerate flag states, counts, graceful statuses,
  pure-helper unit tests)
- `tests/integration/test_mcp_tools.py` (modified — `assess_deck_power` added to the
  bogus-deck graceful loop + new `test_assess_deck_power_through_client`)
- `tests/integration/test_build_plugin.py` (modified — tool-registry guard set updated
  17 → 18 with `assess_deck_power`)
- `plugin/server/src/mcp_server/tools/assess_deck_power.py` (generated — pre-commit
  `build-plugin-sync` mirror)
- `plugin/server/src/mcp_server/server.py` (generated — pre-commit `build-plugin-sync`
  mirror)
- `_bmad-output/implementation-artifacts/7-1-register-the-async-tool-load-deck-resolve-format.md`
  (this story file)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (story status tracking)

## Change Log

- 2026-07-17: Story 7.1 implemented — `assess_deck_power` async MCP tool (ingest/resolve
  slice): full-Card deck load, format→profile ladder with graceful `unsupported_format`
  (brawl-family excluded by decision), AD-13 commander resolution incl. degenerate flag
  states, `unresolved_count` capture, `ResolvedDeckInputs` seam for 7.2/7.3. 31 new tests;
  full suite 1,270 green; mypy/ruff clean. Status → review.
