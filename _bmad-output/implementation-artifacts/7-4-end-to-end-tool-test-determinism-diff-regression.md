---
baseline_commit: 8178fe6
---

# Story 7.4: End-to-end tool test + determinism & diff regression

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As the maintainer,
I want the tool proven end-to-end,
so that determinism and diff-sensitivity are guarded against regressions.

## Acceptance Criteria

1. **Format coverage through the in-process MCP client (`tests/integration/test_mcp_tools.py`).**
   Driven via `create_connected_server_and_client_session(build_server(...))` — no
   subprocess, no live DB, no network:
   - A **Commander deck** (built purely through the tools: `create_deck(format="commander")`
     + `add_card_to_deck(..., commander=True)`) returns `status="ok"` with
     `assessment.bracket ∈ {2, 3, 4}`, all seven vector keys
     (`speed, consistency, resilience, interaction, mana_efficiency, card_advantage,
     combo_potential`) as ints 0–100, and a tier label from `TIER_LABELS`.
   - A **Standard deck** returns `status="ok"` with the for-format 0–100 score, the same
     seven vector keys, the tier label, and `bracket: null` — and the two formats'
     `structuredContent["assessment"]` key sets are identical at every nesting level
     (fixed shape at the wire, AD-7). The existing Standard happy-path test
     (`test_assess_deck_power_through_client`) stays green — extend the suite, don't
     rewrite it.

2. **Client-level determinism regression (NFR1/AD-8).** Two `call_tool("assess_deck_power", ...)`
   invocations on the same deck + card snapshot + combo snapshot produce **byte-identical
   serialized JSON at the wire level** — assert string equality on the serialized payload
   (the `TextContent` text of each result, falling back to
   `json.dumps(result.structuredContent)` if a probe shows the text content isn't the
   JSON projection — see Dev Notes), NOT dict equality (dict equality passes even with
   unstable ordering). This is the client-level byte test 7.3 explicitly deferred here;
   the model-level `model_dump_json()` test already exists and is not a substitute.

3. **Diff-sensitivity through real tool edits.** Deck mutations made through
   `add_card_to_deck` between two assessments produce correctly-directioned deltas:
   - **Adding a `game_changer=True` card** to a 0-GC Commander deck: `bracket` rises
     2 → 3 (GC gate: 1–3 confirmed GCs floor at Bracket 3), never lowers, and
     `flags.game_changers` gains exactly that card's name.
   - **Adding the completing piece** of a seeded 2-card snapshot variant (deck holds one
     piece → `almost_included`): the variant's `bucket` flips to `included`,
     `combo_potential` **strictly** increases, and `bracket` never lowers.
   Directions mirror the core-level properties in
   `tests/unit/logic/test_assessment_scorer.py` (`TestMonotonicityProperties`,
   `test_diff_sensitivity_second_piece`) — assert the same directions at the client
   level; do NOT invent new expected magnitudes.

4. **Degradation-path e2e matrix (NFR3/AD-6).** Each reachable degradation, driven
   through the client, returns a **scored** `status="ok"` result (`isError is False`,
   `/100` present, `assessment` populated) carrying exactly the right closed-enum
   confidence reason — no crash, no silent zero:
   - **Combo snapshot absent** (no snapshot seeded) → `combo_data_unavailable` in
     `assessment.confidence.reasons`, `data_vintage` combo keys `null`.
   - **NULL `game_changer` card** in the deck → `game_changer_data_unavailable`.
   - **Unidentifiable commander** (Commander-format deck, no flags, no sole legendary)
     → `commander_unidentified`; a Standard deck never carries that token.
   - **`cards_unresolved` is documented as structurally unreachable end-to-end and is
     NOT forced** (decide-once #2, Dev Notes): `DeckCard.card` is a required field, so
     an orphaned row fails validation inside `get_deck_with_cards` before the tool ever
     sees it — and downstream code (`_provision_combos`, `score()`) dereferences
     `dc.card` unconditionally. Ladder-level coverage
     (`test_derive_confidence_full_matrix`) stands as the token's guard; the e2e test
     module documents the gap with a pointer to the deferred data-layer orphan story.

5. **Shared-fixture isolation.** `tests/integration/conftest.py::_sample_cards` is NOT
   extended — its card counts are pinned by existing assertions
   (`test_search_cards_by_color` asserts `total_count == 2`, `test_lookup_card_ambiguous`
   pins the "bolt" ambiguity set, `test_deck_analysis_through_client` pins curve counts).
   New e2e tests get their own richer seeded fixture; the combo-snapshot seeding helpers
   are shared, not copy-pasted a third time (decide-once #1).

6. **Tests only — zero product-code change expected.** No edits to `src/logic/`,
   `src/data/`, `src/mcp_server/` or profiles; the G-R2 named calibration inputs
   (card_advantage saturation, interaction railing, Brawl mana_efficiency floor,
   almost_included dominance/inflation) are later Epic-7 calibration work and must NOT
   be "fixed" here. If an e2e test exposes a real determinism/shape bug, STOP and
   surface it (fix belongs in a scoped patch, reviewed against 7.3's ACs), don't
   silently patch the core.

7. **Type + lint gates pass.** `uv run pytest` full suite green (baseline **1,313**
   + new tests, 0 regressions), `mypy --strict` over `src/` clean (no `src/` diff means
   trivially clean), `ruff check` + `ruff format` clean, pre-commit passes without
   `--no-verify` (the `build-plugin-sync` hook should produce **no plugin diff** —
   tests aren't mirrored; a plugin diff means `src/` was touched, revisit AC 6).

## Tasks / Subtasks

- [x] Task 0: Story-start state verification (standing team agreement) (AC: all)
  - [x] `git status` — clean tree expected on `feat/deck-power-assessment` at `8178fe6`
        (7.3 review patches committed). If dirty, stop and reconcile first.
  - [x] `uv run pytest --collect-only -q | tail -1` — confirm full-suite baseline
        **1,313**; record actual in Dev Agent Record.
  - [x] **Wire-format probe (AC 2 pre-req):** run the existing
        `test_assess_deck_power_through_client` under a debugger or add a throwaway
        print — confirm what `result.content` holds (expected: one `TextContent` whose
        `.text` is the JSON projection of the result) and that
        `result.structuredContent` key order matches model declaration order. Record
        which byte-comparison surface you chose and why.
  - [x] Probe imports resolve:
        `from src.mcp_server.tools.assess_deck_power import MULTIPLAYER_VARIANCE_CAVEAT`
        and `from src.logic.assessment import CONFIDENCE_REASON_TOKENS, TIER_LABELS`.
- [x] Task 1: Shared combo-snapshot seeding helpers + e2e fixture (AC: 1, 5)
  - [x] Promote `_snapshot_variant` / `_seed_snapshot` (currently local to
        `tests/integration/mcp_server/test_assess_deck_power_tool.py:667-706`) into a
        new `tests/fixtures/combo_snapshot.py` (the `FakeEmbedder` consolidation
        precedent); update the 7.3 file's imports mechanically — zero assertion changes.
  - [x] New fixture in `tests/integration/test_mcp_tools.py` (local, NOT conftest):
        file-backed engine + `init_database` + session factory, seeded with an
        assessment-grade card set — at minimum: a legendary creature
        (commander candidate), a second legendary (combo partner), filler creatures +
        an instant, basic lands, two `game_changer=True` cards, one
        `game_changer=None` card, everything else `game_changer=False` (the shared
        3-card fixture defaults `game_changer` to NULL — unusable for
        high-confidence paths). Reuse the `_card` builder shape from
        `test_assess_deck_power_tool.py:64-97` (commander+standard legal, unique
        oracle_ids).
- [x] Task 2: Format coverage + wire shape parity (AC: 1)
  - [x] Commander-deck client test: build via tools (`format="commander"`, flagged
        commander), seed a healthy snapshot, assert bracket/vector/tier/confidence high
        + `summary.endswith(MULTIPLAYER_VARIANCE_CAVEAT)` (constant was made a module
        `Final` in 7.3 precisely for this).
  - [x] Standard-deck client test (or extend the existing one): score + vector + tier +
        `bracket is None` + no caveat.
  - [x] Wire-level shape parity: recursive key-set equality of the two formats'
        `structuredContent["assessment"]` (top level, `vector`, `data_vintage`,
        `confidence`, `flags`).
- [x] Task 3: Client-level determinism byte test (AC: 2)
  - [x] Seed snapshot (2 variants, ids deliberately out of insert order) + a deck using
        GC + NULL-GC + combo cards (maximally exercised payload); call the tool twice
        through the same client; assert byte equality on the chosen wire surface;
        also assert the sorted-emission facts survive the wire
        (`reasons`/`game_changers` sorted, combos by `spellbook_id`).
- [x] Task 4: Diff-sensitivity tests (AC: 3)
  - [x] GC-add test: assess → `add_card_to_deck` a `game_changer=True` card → assess;
        assert bracket 2→3, `flags.game_changers` delta, score/`for_format_score`
        comparisons only where direction is guaranteed (bracket + GC list are; total
        score is NOT — don't over-assert).
  - [x] Combo-completion test: seed 2-card variant, deck holds piece A
        (`almost_included`) → add piece B → `included` + strict `combo_potential`
        increase + bracket never lowers.
- [x] Task 5: Degradation e2e matrix (AC: 4)
  - [x] Absent snapshot / NULL-GC / unidentified-commander client tests per AC 4
        (assert token in `structuredContent["assessment"]["confidence"]["reasons"]`,
        `isError is False`, `/100` in summary).
  - [x] Standard-deck negative: `commander_unidentified` never fires.
  - [x] Module-docstring note documenting the `cards_unresolved` e2e gap + pointer to
        the ladder test and the deferred data-layer orphan story (decide-once #2).
- [x] Task 6: Quality gates + story wrap-up (AC: 6, 7)
  - [x] `uv run ruff check . --fix && uv run ruff format .`; `uv run pytest` full suite
        green; confirm zero `src/` + zero `plugin/` diff.
  - [x] Update this story file (Dev Agent Record, File List, Change Log); status →
        review. Conventional Commit suggestion:
        `test: assess_deck_power e2e client suite — determinism + diff regression (story 7.4)`.

### Review Findings

_Adversarial code review 2026-07-17 (Blind Hunter + Edge Case Hunter + Acceptance Auditor). All 7 ACs + all 4 decide-once decisions verified MET; new e2e suite re-run green (11/11). Findings are test-hardening only — no product defect, no AC violation._

- [x] [Review][Decision] E2E suite doesn't guard against a globally-zero scorer — every vector value is asserted `int, 0–100` but never `> 0` (only `combo_potential` gets a relative check); a scorer regressed to emit all-zeros would pass the whole e2e suite. Add a calibration-free liveness assertion (e.g. `sum(vector.values()) > 0` on the healthy commander deck), or leave non-degeneracy to the unit scorer tests per decide-once #4? [tests/integration/test_mcp_tools.py:646] — **RESOLVED 2026-07-18:** added `assert sum(assessment["vector"].values()) > 0` to `test_assess_commander_deck_through_client` (the healthy, fully-known deck). Calibration-free — asserts non-degeneracy only, no magnitude (AC 6 / decide-once #4 respected).
- [x] [Review][Patch] Determinism test's wire surface not tied to the payload — `block_a.text == block_b.text` passes vacuously if `.text` were empty/constant on both calls; assert `.text` truthy and `json.loads(block_a.text) == result_a.structuredContent` to enforce the exact probe invariant the docstring claims (decide-once #3) [tests/integration/test_mcp_tools.py:801] — **RESOLVED 2026-07-18:** added `assert block_a.text` + `assert json.loads(block_a.text) == result_a.structuredContent` before the byte-equality assertion (`import json` added).
- [x] [Review][Patch] `_VECTOR_KEYS` has two sources of truth — `test_assess_deck_power_through_client` still hard-codes the 7-key list inline while the new `_VECTOR_KEYS` constant exists; replace the inline literal with the constant [tests/integration/test_mcp_tools.py:415] — **RESOLVED 2026-07-18:** inline 7-key literal replaced with `_VECTOR_KEYS`; single source of truth.
- [x] [Review][Defer] Bracket-4 floor (≥4 confirmed GCs) unreachable e2e — fixture has only two `game_changer=True` cards and Commander singleton caps each at qty 1, so `bracket == 4` is never exercised through the client (unit scorer covers the ≥4 gate) [tests/integration/test_mcp_tools.py:494] — deferred, follow-up hardening
- [x] [Review][Defer] Present-path `data_vintage` values never positively asserted e2e — the null path is pinned but no e2e test asserts the populated vintage equals the seeded `export_version="5.6.0"` / `imported_at`; passthrough bug on the present path caught only at model level [tests/fixtures/combo_snapshot.py:63] — deferred, follow-up hardening

_Dismissed as noise (9): parity `_shape` list-collapse (documented AD-7 design; combo keys pinned at wire by the determinism/diff tests); single-element `reasons == sorted(reasons)` (inert but harmless — the multi-element game_changers/combos sort checks carry the guard); `isinstance(v, int)` accepts bool (implausible regression, values are arithmetic); determinism test narrowness / same-process (explicit sort assertions are the real guard, cross-process out of scope for in-process harness); standard-never-fires-token fixture can't fire it (correct — positive case covered by the sibling unidentified-commander test); no standard matched-combo e2e (covered at tool-function level); non-ok statuses not client-driven here (deck_not_found + unsupported_format ARE; error/db-not-init covered at tool level); fixture color/cost incoherence (no dimension keys off it); Dev Record "73 tests" (FALSE POSITIVE — 73 is pytest's collected count incl. parametrization, verified; 55 is the `def` count)._

## Dev Notes

### What this story is (and is NOT)

The **end-to-end proof slice** of the `assess_deck_power` tool (feature Story 4.4,
sprint key `7-4`): a client-level regression suite pinning the full 7.1+7.2+7.3
stack — wire-level byte determinism, fixed-shape parity, correctly-directioned
diff-sensitivity, and the degradation ladder — through the same in-process MCP harness
every other tool uses. It is a **tests-only story**. It does NOT include:

- **`compare_deck_power`** — Story 7.5 (it will reuse this story's fixtures and the
  delta directions pinned here; name test helpers with that consumer in mind).
- **Any calibration/tuning** — the G-R2 cross-deck observations
  (card_advantage saturation at 80, interaction railing 0/100, Brawl mana_efficiency
  floor, almost_included dominance, format-blind almost_included inflation) are named
  Epic 7 calibration inputs owned by later work. A diff-sensitivity test that "looks
  wrong" because of one of these is NOT a bug to fix here.
- **Data-layer orphan handling** — the `cards_unresolved` e2e gap (decide-once #2) is
  deferred to its own data-layer story (7.1 review disposition).
- **Any `src/` change at all** — if the suite finds a real defect, stop and surface it.

### Critical code facts (verified 2026-07-17 at `8178fe6`)

- **The tool under test** (`src/mcp_server/tools/assess_deck_power.py`, 829 lines):
  `assess_deck_power(session, *, deck_id, format=None) -> AssessDeckPowerResult`.
  Result: `status` (`ok | deck_not_found | unsupported_format |
  database_not_initialized | error`), `schema_version="1"`, `summary`, `deck_id`,
  `assessment: Assessment | None`. `Assessment` fields in emission order:
  `format` (`Literal["commander","standard"]`), `vector` (7 ints), `for_format_score`,
  `tier`, `bracket` (`Literal[2,3,4] | None` — tightened by the 7.3 review patch),
  `data_vintage`, `confidence{level, reasons}`, `flags{game_changers, combos,
  structural_gaps, mass_land_denial, extra_turn_chains, cedh_candidate}`.
- **Registration** (`src/mcp_server/server.py:474-512`): `async def
  assess_deck_power(deck_id: str, format: str | None = None)` opens
  `async with session_factory() as session` per call — so a client test's own writes
  (via a separate session from the same factory) are visible to the tool as long as
  they're committed (file-backed DB, WAL).
- **Client harness pattern** (`tests/integration/test_mcp_tools.py`):
  `server = build_server(session_factory=...)` +
  `async with create_connected_server_and_client_session(server) as client` →
  `await client.call_tool(name, args)`. Every existing assertion uses
  `result.structuredContent` — **no test anywhere reads `result.content` yet**; hence
  the Task 0 wire-format probe before writing AC 2.
- **The existing client test to extend, not duplicate**
  (`test_mcp_tools.py:355-411`, `test_assess_deck_power_through_client`): Standard
  happy path via `seeded_card_db` (asserts vector keys, `bracket is None`,
  `cedh_candidate is False`, `standard-v4`, `/100`, `confidence `) + graceful
  `unsupported_format`. `test_analysis_tools_on_bogus_deck_are_graceful`
  (`test_mcp_tools.py:337-352`) already covers client-level `deck_not_found`.
- **The shared `seeded_card_db` fixture** (`tests/integration/conftest.py:84-108`)
  seeds exactly 3 cards (Lightning Bolt, Thunderbolt, Counterspell) with
  **`game_changer` unset → NULL**: every deck built from it fires
  `game_changer_data_unavailable` (that's why the existing happy-path test asserts
  `confidence ` generically). Useful fact — but Commander/high-confidence e2e paths
  need a new fixture (Task 1). **Do not add cards to `_sample_cards`** — pinned
  assertions break (AC 5).
- **Tool surface for deck building:** `create_deck(name, format="standard", ...)`
  (`server.py:218-223`) and `add_card_to_deck(deck_id, card_id | name, quantity=1,
  sideboard=False, commander=False)` (`server.py:278-285`) — a Commander deck with a
  flagged commander is fully buildable through the client.
- **Snapshot seeding pattern to promote** (Task 1, from
  `test_assess_deck_power_tool.py:667-706`): `ComboVariantModel(spellbook_id,
  commander_required, bracket_tag, popularity)` + `variant.cards_list = [...]` +
  `variant.produces_list = [...]` + `ComboVariantPieceModel(spellbook_id,
  name_key=...)` per `name_keys(name)` key, plus one `ComboSnapshotMetaModel(
  imported_at, export_timestamp, export_version, variant_count)` row. Commit before
  calling the tool. Use `commander_required=False` variants unless a test targets
  commander gating.
- **GC → bracket math** (`src/logic/assessment/dimensions.py:105-111,369-374`):
  baseline Commander floor 2; `known_count >= 1` → floor 3; `>= 4` → floor 4. NULL
  (`None`) never counts either way (AD-4). So the AC 3 GC-add test needs a 0-GC,
  combo-free baseline deck (floor exactly 2) → +1 confirmed GC → floor exactly 3.
- **Combo direction precedent**
  (`tests/unit/logic/test_assessment_scorer.py:465-487`): one piece →
  `almost_included`; add completing piece → `included`, `combo_potential` strictly
  rises, `bracket_floor` never lowers. Mirror exactly at client level.
- **Degradation-path fixtures already proven at helper level**
  (`test_assess_deck_power_tool.py:709-919`) — the e2e matrix re-drives the same
  scenarios through the client, asserting on `structuredContent` instead of the model.
  Confidence ladder: 0 reasons → high, 1 → medium, ≥2 → low.
- **`MULTIPLAYER_VARIANCE_CAVEAT`** (`assess_deck_power.py:76-80`) is a module `Final`
  created in 7.3 explicitly "so Stories 7.4/7.5 can assert against the exact
  sentence" — import it; never retype the prose.
- **Determinism scope:** the tool never writes (read-only path); two sequential
  `call_tool` invocations against unchanged fixtures are the regression pair. Deck
  `updated_at` only changes on deck writes — don't interleave `add_card_to_deck`
  between the two determinism calls (that's the diff test's job).
- **mcp SDK:** `mcp>=1.27.0`; harness import is
  `from mcp.shared.memory import create_connected_server_and_client_session`.

### Decide-once decisions this story owns (document each in code)

1. **Combo-snapshot seeding helpers are promoted to `tests/fixtures/combo_snapshot.py`.**
   Two copies would already exist after this story (7.3's file + the new e2e suite);
   the epic-2 retro's `_FakeEmbedder` consolidation (→ `tests/fixtures/embedder.py`)
   is the precedent. The 7.3 test file's import lines change mechanically; its 55
   tests must pass untouched. (Fallback if the move surprises: local copies are
   acceptable but must be flagged in the story record as debt.)
2. **`cards_unresolved` is NOT forced end-to-end.** `DeckCard.card` is required
   (`src/data/schemas/deck.py:28`) — an orphaned row fails `Deck.model_validate`
   inside `get_deck_with_cards` before the tool runs (documented at
   `assess_deck_power.py:748-755`), and forcing a `card=None` row via
   `model_construct` would crash `_provision_combos`
   (`[dc.card.name for dc in mainboard]`) and `score()` anyway — the injection would
   test a state the system cannot produce. The token's guard remains the pure-ladder
   matrix (`test_derive_confidence_full_matrix`); the e2e module docstring names the
   gap and the deferred data-layer orphan story. The story's AC 4 wording (not the
   epic's shorthand) is the acceptance contract.
3. **Byte-comparison surface is chosen by probe, recorded in the test.** Preferred:
   `result.content[0].text` (the wire text). If the probe shows FastMCP's text content
   is not the full JSON projection, compare
   `json.dumps(result.structuredContent, separators=(",", ":"))` — parsed-JSON dicts
   preserve wire key order, so serialization instability still fails the test. Either
   way the assertion is **string equality**, and the chosen surface + rationale goes
   in the test docstring (7.5 reuses it).
4. **Diff-sensitivity asserts directions, not magnitudes.** Guaranteed-direction facts
   only: bracket floor transitions, `flags.game_changers` membership, bucket flips,
   strict `combo_potential` increase. `for_format_score` movement is weight-dependent
   and calibration-owned — asserting its direction would couple the suite to tuning
   this story is forbidden from touching.

### Previous-story intelligence (7.3 + review)

- **7.3 deliberately deferred to here:** the client-level byte test ("the client-level
  byte test is Story 7.4's"), and pinned at model level everything this story
  re-verifies at the wire — if a wire test fails where the model test passes, suspect
  FastMCP serialization, not the models.
- **7.3's edge emits producer order as-is, re-sorting nothing** — "a re-sort would
  mask a producer regression 7.4 wants to catch" (`assess_deck_power.py` /
  `CoreAssessment` contract). The sorted-emission wire assertions (Task 3) are that
  catch: if they fail, a producer (core/matcher/ladder) regressed.
- **7.3 review patch tightened `bracket` to `Literal[2,3,4] | None`** specifically so
  "a producer regression becomes a loud ValidationError (which 7.4's determinism suite
  catches)" — the e2e suite IS that tripwire; don't wrap tool calls in try/except.
- **Summary-fragment stability:** MCP-level assertions pin `/100`, `confidence `,
  `no degradations`, `N combo variant(s)` fragments. New tests may pin the same
  fragments; do not invent new phrasing assertions that 7.5's summary work would break
  gratuitously.
- **7.2/7.3 seeding lessons:** commit fixture writes before calling the tool
  (file-backed WAL visibility); seed GC names in reverse bytewise order when testing
  sorted emission ("Aura Shards" < "Bolas's Citadel" precedent); an `almost_included`
  fixture = 2-card variant with exactly one piece in-deck.
- **Task 0 state verification is a standing team agreement** — it has caught real
  traps in five consecutive stories (httpx decoding 6.2, baseline off-by-one 6.3,
  7.1 import confirmations, 7.2 uncommitted-patch warning, 7.3's construction-site
  count correction).

### Architecture compliance checklist

- **AD-1/NFR7:** tests drive the registered `async def` tool through FastMCP —
  stateless, per-call `deck_id`/`format`, no session state anywhere in the suite.
- **AD-7:** wire shape parity (fixed closed key set, `bracket: null` + `false`
  booleans for Standard, `cedh_candidate` homed in `flags`) asserted on
  `structuredContent`, both formats.
- **AD-8/NFR1:** byte-identical wire JSON; sorted lists survive the wire; no
  clock-derived content (the only timestamp strings are the seeded vintage values).
- **AD-6/NFR3:** every degradation e2e test asserts `isError is False` +
  `status="ok"` + a scored result + the exact closed-enum token — never a crash,
  never a silent zero, tokens never embed counts.
- **AD-2/AD-9:** the suite treats the core as a black box — no imports from
  `src/logic/assessment` internals beyond the public re-exports already used by the
  7.3 tests (`CONFIDENCE_REASON_TOKENS`, `TIER_LABELS`, token constants).
- **NFR6:** this suite is the tool-level complement of the committed benchmark — it
  guards the contract, not the calibration.

### Testing standards summary

- pytest config in `pyproject.toml`; `asyncio_mode = "auto"` (plain
  `async def test_...`, no marker); `--strict-markers`; `tests.*` exempt from
  `mypy --strict` (ruff/naming still apply); Google docstrings on test helpers.
- New client tests live in `tests/integration/test_mcp_tools.py` (the epic AC names
  this file; it is the established in-process-client home). The new fixture is
  module-local; promoted seeding helpers go to `tests/fixtures/combo_snapshot.py`
  (decide-once #1).
- Baseline **1,313** tests at `8178fe6`; 7.3's 55-test helper-level suite
  (`tests/integration/mcp_server/test_assess_deck_power_tool.py`) must pass untouched
  except for the mechanical helper-import change.
- TDD order per task: write the client assertion first (RED against a stub fixture if
  useful), then wire the fixture (GREEN). No live DB, no network, no subprocess.

### Project Structure Notes

- Modified: `tests/integration/test_mcp_tools.py` (new fixture + ~8-10 new tests),
  `tests/integration/mcp_server/test_assess_deck_power_tool.py` (helper-import lines
  only).
- New: `tests/fixtures/combo_snapshot.py` (promoted seeding helpers).
- **No changes** to `src/**`, `plugin/**`, `scripts/**`, profiles, or
  `tests/integration/conftest.py::_sample_cards`.
- Branch: stays on `feat/deck-power-assessment` (no master merge until Epic 7
  completes — "experimental" release policy).

### References

- [Source: _bmad-output/planning-artifacts/epics-deck-power-assessment.md#Story 4.4] —
  story + ACs (sprint key `7-4`); Epic 4 preamble; NFR1/NFR3 texts.
- [Source: _bmad-output/implementation-artifacts/7-3-assess-deck-power-result-assembly-deterministic-serialization-human-summary.md]
  — the deferred client-level byte test; `Assessment` field facts; review patches
  (closed `bracket`/`format` Literals); seeding patterns; summary fragments.
- [Source: src/mcp_server/tools/assess_deck_power.py:53-80,222-266,748-755] — result
  contract, caveat constant, and the structural-zero `unresolved_count` note behind
  decide-once #2.
- [Source: src/mcp_server/server.py:218-223,278-285,474-512] — `create_deck` /
  `add_card_to_deck(commander=)` / `assess_deck_power` registrations (per-call
  session from the factory).
- [Source: tests/integration/test_mcp_tools.py:1-18,337-411] — harness pattern; the
  existing assess client tests this story extends.
- [Source: tests/integration/conftest.py:21-108] — `_sample_cards` (3 cards,
  `game_changer` NULL) + `seeded_card_db`; the count-pinned assertions behind AC 5.
- [Source: tests/integration/mcp_server/test_assess_deck_power_tool.py:64-97,667-706]
  — `_card` builder + `_snapshot_variant`/`_seed_snapshot` (promotion source).
- [Source: tests/unit/logic/test_assessment_scorer.py:426-487] — monotonicity +
  diff-sensitivity direction precedents (AC 3 mirrors these).
- [Source: src/logic/assessment/dimensions.py:105-111,369-374] — GC bracket gate
  (1 GC → floor 3) behind the AC 3 expected transition.
- [Source: src/data/schemas/deck.py:28] — required `DeckCard.card` (decide-once #2).
- [Source: _bmad-output/implementation-artifacts/pre-epic-7-real-deck-gate-report-2026-07-17.md#Cross-deck observations]
  — the named calibration inputs this story must NOT fix (AC 6).
- [Source: tests/fixtures/embedder.py] — the shared-test-helper consolidation
  precedent behind decide-once #1.

## Dev Agent Record

### Agent Model Used

Claude Fable 5 (claude-fable-5) via Claude Code

### Debug Log References

- Task 0 state verification (2026-07-17): tree clean at `8178fe6` on
  `feat/deck-power-assessment` except the story-creation artifacts themselves
  (this story file + sprint-status.yaml) — no code dirt, proceeded.
  `uv run pytest --collect-only -q` → **1,313 tests collected** (matches the
  recorded baseline exactly). Both import probes resolved
  (`MULTIPLAYER_VARIANCE_CAVEAT`, `CONFIDENCE_REASON_TOKENS`, `TIER_LABELS`).
- **Wire-format probe result (AC 2 surface decision):** a throwaway script drove
  `assess_deck_power` through `create_connected_server_and_client_session` and
  inspected the raw result. `result.content` holds exactly **one `TextContent`**
  whose `.text` IS the JSON projection of the result — it parses back equal to
  `result.structuredContent`, with model-declaration key order preserved at every
  level (top-level, `assessment`, `vector`). **Chosen byte-comparison surface:
  `result.content[0].text`** (the preferred wire text from decide-once #3);
  rationale recorded in the determinism test's docstring.

### Completion Notes List

- **Tests-only story delivered as specified: zero `src/`, zero `plugin/`, zero
  `scripts/` changes.** `git status` shows only the two test files, the new
  fixtures module, and the story artifacts.
- **Decide-once #1 (helper promotion):** `_snapshot_variant`/`_seed_snapshot`
  promoted to `tests/fixtures/combo_snapshot.py` as public `snapshot_variant`/
  `seed_snapshot`. The 7.3 file imports them **aliased to the old local names**
  (`import … as _snapshot_variant`), so the change is literally import-lines-only —
  zero call-site or assertion changes; its full suite (73 tests) passes untouched.
- **Decide-once #3 (byte surface):** probe confirmed `result.content[0].text` is
  the full JSON projection → string-equality assertion on that wire text in
  `test_assess_deck_power_wire_bytes_deterministic`, with the surface + rationale
  in the test docstring for 7.5 reuse.
- **Decide-once #2 (`cards_unresolved`):** NOT forced e2e; documented in the
  `test_mcp_tools.py` module docstring with pointers to
  `test_derive_confidence_full_matrix` (the token's standing guard) and the
  deferred data-layer orphan story.
- **Decide-once #4 (directions, not magnitudes):** diff tests assert only
  guaranteed-direction facts — bracket 2→3 on GC add (exact, per the
  `dimensions.py` GC gate), `flags.game_changers` membership delta, bucket flip
  `almost_included`→`included`, strict `combo_potential` increase, bracket never
  lowers. No `for_format_score` direction assertions (calibration-owned).
- New module-local `assessment_card_db` fixture (8 cards: commander candidates,
  combo partner, filler, basics, 2 confirmed GCs seeded in reverse bytewise
  order, 1 NULL-GC) — the shared `_sample_cards` was NOT touched (AC 5).
- 10 new client tests: commander/standard format coverage, recursive wire shape
  parity (`_shape` helper — dicts recurse, lists collapse by design since combo
  list contents legitimately differ), determinism byte test with sorted-emission
  wire assertions, 2 diff-sensitivity tests, 4 degradation-matrix tests. The
  `_build_deck` helper is named/shaped for Story 7.5 reuse.
- No determinism/shape defect surfaced — the suite passed against the 7.1–7.3
  stack as-built; no scoped patch needed (AC 6 stop-condition never triggered).
- Gates: full suite **1,323 passed** (1,313 baseline + 10 new, 0 regressions);
  `mypy --strict` over `src/` clean (no `src/` diff); `ruff check` + `ruff format`
  clean; pre-commit run via the story commit (no `--no-verify`), plugin sync hook
  produced no plugin diff.

### File List

- `tests/fixtures/combo_snapshot.py` (new — promoted `snapshot_variant`/`seed_snapshot`)
- `tests/integration/test_mcp_tools.py` (modified — module docstring note, e2e
  fixture + card builder, `_build_deck`/`_shape` helpers, 10 new client tests)
- `tests/integration/mcp_server/test_assess_deck_power_tool.py` (modified —
  mechanical import swap to the promoted helpers; zero assertion changes)
- `_bmad-output/implementation-artifacts/7-4-end-to-end-tool-test-determinism-diff-regression.md`
  (this story file)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (status tracking)

## Change Log

- 2026-07-17: Story 7.4 implemented — assess_deck_power e2e client suite:
  combo-snapshot helpers promoted to `tests/fixtures/combo_snapshot.py`; new
  `assessment_card_db` fixture; 10 new in-process MCP client tests covering
  format coverage + AD-7 wire shape parity, AD-8/NFR1 wire-level byte
  determinism (surface: `result.content[0].text`), diff-sensitivity (GC add
  bracket 2→3, combo completion bucket flip + strict combo_potential rise), and
  the NFR3/AD-6 degradation matrix (absent snapshot / NULL GC / unidentified
  commander / standard negative). Tests-only: no product code touched. Full
  suite 1,323 green. Status → review.
- 2026-07-18: Resolved the three open review findings (test-hardening only,
  no product change): (1) calibration-free liveness guard
  `sum(vector.values()) > 0` on the healthy commander deck; (2) determinism test
  wire surface pinned to the payload (`block_a.text` truthy +
  `json.loads(block_a.text) == structuredContent`) so byte-equality can't pass
  vacuously; (3) collapsed the duplicated 7-key vector literal to `_VECTOR_KEYS`.
  Full suite 1,323 green, ruff/format clean, zero `src/`/`plugin/` diff.
  Status → done.
