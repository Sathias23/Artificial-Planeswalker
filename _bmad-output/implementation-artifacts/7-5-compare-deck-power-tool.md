---
baseline_commit: bbb87e6
---

# Story 7.5: The `compare_deck_power` tool

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a deck tuner,
I want one call that tells me what changed between two decks,
so that the comparison arithmetic is deterministic and never delegated to the calling agent.

## Acceptance Criteria

1. **Registration & statelessness (AD-1/NFR7/FR26).** `compare_deck_power(deck_id_a, deck_id_b,
   format?)` is registered in `src/mcp_server/server.py` as an **`async def`** tool, sibling to
   `assess_deck_power` — same pattern exactly: helper imported aliased
   (`compare_deck_power as _compare_deck_power_helper` from a new
   `src/mcp_server/tools/compare_deck_power.py`), one
   `async with session_factory() as session` per call, no server-side state, `deck_id_a` /
   `deck_id_b` / `format` are the only params. The registration docstring is the LLM-facing tool
   description (match the sibling docstrings' shape: what it does, delta semantics, statuses,
   Args, Returns).

2. **Same pipeline, no second scoring path (FR26/AD-1).** The helper composes **two calls to the
   existing `assess_deck_power(session, deck_id=..., format=...)` helper** (same session, sequential
   awaits) and computes every delta by **subtracting the two returned `Assessment` blocks**. It
   never re-implements or re-enters format resolution, commander resolution, combo provisioning,
   `score()`, or serialization — zero scoring/resolution logic exists in the new module. The e2e
   test proves it: the compare deltas equal the field-wise subtraction of two separate
   `assess_deck_power` tool results on the same decks.

3. **Versioned `CompareDeckPowerResult` (AD-7 sibling).** One Pydantic result with: a **closed
   `status` Literal** (see decide-once #1) that names which side failed when a side fails; an
   always-present `schema_version` (own `Final` constant, `"1"` — independent of the assess
   version); a human `summary`; `deck_id_a` + `deck_id_b` reflected back; and a `comparison` block
   (`None` on every non-ok status). `comparison` carries, fixed shape, all keys always present:
   - `format` — the shared resolved format of both assessments.
   - `vector_delta` — all 7 fixed keys (`speed, consistency, resilience, interaction,
     mana_efficiency, card_advantage, combo_potential`), each **int** in [−100, 100], computed
     **b − a** (deck_a is the baseline; decide-once #2).
   - `for_format_score_delta` — int, b − a; plus per-side `for_format_score_a/_b` and
     `tier_a`/`tier_b` (a delta without its endpoints forces the caller to re-call assess).
   - `bracket_a` + `bracket_b` — each `Literal[2, 3, 4] | None`, verbatim from the two
     assessments (Bracket "change" is the pair, not signed arithmetic — decide-once #3).
   - flags diff per decide-once #4: `game_changers_added/removed`, `structural_gaps_added/removed`,
     `combos_added/removed` (by `spellbook_id`) + `combos_bucket_changed` (same id, bucket
     flipped, with from/to), and the three booleans as per-side pairs
     (`mass_land_denial_a/_b`, `extra_turn_chains_a/_b`, `cedh_candidate_a/_b`).
   - `data_vintage_a` + `data_vintage_b` — **both** blocks verbatim (`DataVintage` reused).
   - `confidence_a` + `confidence_b` — both `Confidence` blocks verbatim (a delta consumer must
     see whether either side was degraded).

4. **Graceful failure, side named (FR26/NFR3).** Either underlying assessment not reaching
   `status="ok"` (`deck_not_found`, `unsupported_format`, `database_not_initialized`, `error`)
   yields a graceful top-level result — never a crash, never `isError=True` at the wire: the
   status names which side failed (both-fail case defined), the `summary` names the failing
   deck id(s) **and the underlying per-side status token(s)**, and `comparison` is `None`.
   `database_not_initialized` surfaces as its own top-level status (both sides fail identically —
   it's global, not a side fault).

5. **Format mismatch (FR26).** With `format` omitted and the two decks resolving to different
   formats (`assessment.format` of each side — the field 7.3 put there for exactly this check),
   the result is top-level `format_mismatch` with a summary naming both resolved formats and the
   explicit-`format` override hint; `comparison` is `None`. An explicit `format` param is passed
   verbatim to **both** assess calls (forcing both sides; an unsupported explicit value surfaces
   per AC 4 via the underlying `unsupported_format`). Cross-format comparison never proceeds
   implicitly.

6. **Deterministic serialization (AD-8/NFR1).** Two `compare_deck_power` runs on the same decks +
   card snapshot + combo snapshot produce byte-identical wire JSON: every `*_added` / `*_removed` /
   `*_bucket_changed` list emitted **sorted ascending bytewise** (computed via set difference then
   sorted — never insertion order); all deltas **int**; no call-time clock anywhere ("as of" facts
   only inside the two `data_vintage` blocks); pass-through blocks (`DataVintage`, `Confidence`,
   vector endpoints) never re-sorted or recomputed. Comparing a deck **with itself**
   (`deck_id_a == deck_id_b`, legal) yields all-zero deltas and empty diff lists.

7. **Helper-level test suite.** New `tests/integration/mcp_server/test_compare_deck_power_tool.py`
   (mirroring `test_assess_deck_power_tool.py`'s file-backed-engine + shared-session pattern) covers: ok-path delta
   arithmetic (subtraction equality against two direct assess calls), self-compare all-zero,
   each failure side (`a` fails / `b` fails / both / `database_not_initialized`),
   `format_mismatch` + explicit-`format` forcing, sorted diff lists, and model-level
   `model_dump_json()` byte determinism.

8. **End-to-end MCP client test (epic AC).** In `tests/integration/test_mcp_tools.py`, driven via
   `create_connected_server_and_client_session` reusing the 7.4 `assessment_card_db` fixture +
   `_build_deck` helper (built for this story) + `seed_snapshot` from `tests/fixtures/combo_snapshot.py`:
   - Two commander decks differing by one `game_changer=True` card → `game_changers_added` shows
     exactly that card, `bracket_a=2` / `bracket_b=3`, and **every delta equals the subtraction of
     the two `assess_deck_power` client results** (field-wise, from their `structuredContent`).
   - Combo completion across sides (deck_a holds one piece of a seeded 2-card variant, deck_b both)
     → the variant appears in `combos_bucket_changed` (or added, per the shapes in decide-once #4)
     and `vector_delta.combo_potential > 0`.
   - Wire-level byte determinism: two identical `call_tool("compare_deck_power", ...)` calls →
     string-equal `result.content[0].text` (the 7.4-probed wire surface; same rationale docstring).
   - Graceful client-level failure: bogus `deck_id_b` → `isError is False`, side-naming status,
     `comparison` null; mismatched formats (commander vs standard deck) → `format_mismatch`.

9. **Quality gates + calibration freeze.** `uv run pytest` full suite green (baseline **1,323**
   + new tests, 0 regressions); `mypy --strict` over `src/` clean; `ruff check` + `ruff format`
   clean; pre-commit passes without `--no-verify` — **this story touches `src/`, so the
   `build-plugin-sync` hook WILL produce a `plugin/` diff: commit it** (unlike 7.4's zero-diff
   expectation). No changes to `src/logic/**`, profiles, or scoring behavior — the G-R2 named
   calibration inputs (card_advantage saturation, interaction railing, almost_included inflation,
   Brawl mana_efficiency) remain later Epic-7 calibration work; a "wrong-looking" delta from one
   of these is NOT a bug to fix here.

## Tasks / Subtasks

- [x] Task 0: Story-start state verification (standing team agreement) (AC: all)
  - [x] `git status` — the tree at story-creation time carried the **uncommitted 7.4
        review-patch resolution** (`tests/integration/test_mcp_tools.py` + 7.4 story file +
        sprint-status). If still dirty, commit that first as 7.4's wrap-up
        (`test: resolve 7.4 review findings — liveness guard, wire-surface pin, _VECTOR_KEYS`)
        before any 7.5 work. Record the resulting baseline commit here.
        **Result: 7.4 wrap-up already committed as `bbb87e6` before story start — only
        story-creation artifacts (this file + sprint-status) dirty. Baseline = `bbb87e6`.**
  - [x] `uv run pytest --collect-only -q | tail -1` — confirm baseline **1,323**; record actual.
        **Result: 1323 tests collected — matches.**
  - [x] Probe imports resolve: `from src.mcp_server.tools.assess_deck_power import
        Assessment, AssessDeckPowerResult, DataVintage, Confidence, assess_deck_power` and
        `from tests.fixtures.combo_snapshot import seed_snapshot, snapshot_variant`.
        **Result: imports OK.**
- [x] Task 1: Result models in `src/mcp_server/tools/compare_deck_power.py` (AC: 3, 6)
  - [x] `COMPARE_SCHEMA_VERSION: Final = "1"`; frozen (`ConfigDict(frozen=True)`) `VectorDelta`,
        `ComboBucketChange`, `Comparison` models + `CompareDeckPowerResult` (unfrozen top-level,
        matching `AssessDeckPowerResult`). Reuse `DataVintage` / `Confidence` / `TierLabel` by
        import — do NOT redeclare them. Google docstrings; field declaration order IS emission
        order (AD-8) — document the b − a convention on every delta field.
  - [x] Write the helper-level model tests first (RED): fixed shape, Literal statuses, frozen
        blocks, `model_dump_json()` determinism (TDD per project practice).
- [x] Task 2: The compare helper (AC: 2, 4, 5, 6)
  - [x] `async def compare_deck_power(session, *, deck_id_a, deck_id_b, format=None) ->
        CompareDeckPowerResult`: two sequential `assess_deck_power` helper calls on the same
        session → status triage (decide-once #1) → mismatch check on `assessment.format` →
        pure delta assembly (a small private `_build_comparison(a: Assessment, b: Assessment)`
        + `_build_summary(...)`, both pure functions of the two blocks).
  - [x] Diff lists via set difference + `sorted()`; combos diffed on `spellbook_id` with bucket
        transitions captured (decide-once #4); booleans as per-side pairs.
  - [x] Summary: deterministic projection of the comparison block (deck names come from the two
        summaries? NO — they aren't on `Assessment`; use the ids + score/tier/bracket facts,
        decide-once #5). No multiplayer-variance caveat re-append (it's assess-summary prose;
        decide-once #5).
- [x] Task 3: Registration in `server.py` (AC: 1)
  - [x] Import block (aliased helper + result type, isort-ordered), `@mcp.tool()` registration
        directly after `assess_deck_power`'s, LLM-facing docstring covering: delta direction
        (b − a, deck_a = baseline), statuses incl. `format_mismatch` + side-failure, the
        self-compare zero case, statelessness, and the create_deck+import_decklist snapshot
        workflow hint for comparing two versions of one deck (PRD §3 usage pattern).
- [x] Task 4: Helper-level suite `tests/integration/mcp_server/test_compare_deck_power_tool.py` (AC: 7)
  - [x] File-backed engine + shared-session fixture and `_card` builder shape from
        `test_assess_deck_power_tool.py`;
        `seed_snapshot` for combo scenarios; cover the full AC 7 matrix.
- [x] Task 5: E2E client tests in `tests/integration/test_mcp_tools.py` (AC: 8)
  - [x] Reuse `assessment_card_db` + `_build_deck` + `_VECTOR_KEYS`; GC-delta test asserting
        subtraction equality against two client-level assess results; combo-completion test;
        wire byte-determinism (surface `result.content[0].text`, cite the 7.4 probe); graceful
        bogus-side + mismatch tests.
- [x] Task 6: Gates + wrap-up (AC: 9)
  - [x] `uv run ruff check . --fix && uv run ruff format .`; `uv run pytest` full green;
        `uv run mypy src/` clean; commit WITH the regenerated `plugin/` mirror diff.
        **Result: 1,348 passed / mypy clean / ruff clean; committed as `7a71d41` with the
        regenerated `plugin/` mirror (pre-commit hooks all passed, no `--no-verify`).**
  - [x] Update this story file (Dev Agent Record, File List, Change Log); status → review.
        Conventional Commit suggestion:
        `feat: compare_deck_power tool — server-side deck diff (story 7.5)`.

## Dev Notes

### What this story is (and is NOT)

The **final Epic-7 story** (feature Story 4.5, sprint key `7-5`): the thin, stateless
`compare_deck_power(deck_id_a, deck_id_b, format?)` MCP tool that answers "did my edit make it
stronger, and what changed?" server-side (FR26) — added 2026-07-12 by the sprint change proposal
precisely because delegating the arithmetic diff of two JSON blobs to the calling LLM undermined
the headline use case. It is **thin by design**: two runs of the existing assess pipeline plus
pure subtraction/set-difference. It does NOT include:

- **Any second scoring path** — the helper never touches `src/logic/assessment`, repositories,
  or `score()` directly; everything flows through the existing `assess_deck_power` helper (AC 2).
- **Any calibration/tuning** — same freeze as 7.4 (AC 9).
- **Persistence or history** — stateless, nothing written, no stored comparisons (FR26).
- **README/docs release work** — the feature ships with the epic's release pass, not here.

After this story, Epic 7's story list is complete (retrospective optional) — the
`feat/deck-power-assessment` branch merge decision happens at epic completion, not in-story.

### Critical code facts (verified 2026-07-18, post-7.4)

- **The assess helper to compose** (`src/mcp_server/tools/assess_deck_power.py:667`):
  `async def assess_deck_power(session: AsyncSession, *, deck_id: str, format: str | None = None)
  -> AssessDeckPowerResult`. Statuses: `ok | deck_not_found | unsupported_format |
  database_not_initialized | error`. On `ok`, `result.assessment` is a frozen `Assessment`.
  It strips/lowercases its own inputs — don't pre-normalize in compare beyond `.strip()` on ids.
- **`Assessment` fields** (`assess_deck_power.py:193-229`, emission order): `format`
  (`Literal["commander","standard"]` — put there for THIS story's mismatch check),
  `vector` (7 ints), `for_format_score`, `tier` (`TierLabel`), `bracket`
  (`Literal[2,3,4] | None`), `data_vintage` (`DataVintage`: `combo_snapshot_imported_at`,
  `combo_snapshot_export_version`, `format_profile_version`), `confidence` (`Confidence`:
  `level`, `reasons` tuple), `flags` (`AssessmentFlags`: `game_changers` tuple[str],
  `combos` tuple[`ComboRecord`], `structural_gaps` tuple[str], `mass_land_denial`,
  `extra_turn_chains`, `cedh_candidate` bools). Its docstring says: "Story 7.5 diffs two of
  these — the field names are its delta keys."
- **`ComboRecord`** (`src/data/schemas/combo.py`): carries `spellbook_id`, `cards`,
  `commander_required`, `bucket` (`included | almost_included`), `bracket_tag`, `produces`,
  `popularity`. `flags.combos` arrives sorted by `spellbook_id`. Diff identity = `spellbook_id`;
  the same id can appear on both sides with a **different `bucket`** (the 7.4 combo-completion
  scenario) — a plain id set-difference would report "no change" for the headline
  almost_included→included flip. Hence `combos_bucket_changed` (decide-once #4).
- **Registration pattern to copy** (`server.py:38-41` + `474-512`): result type imported
  plainly, helper imported `as _assess_deck_power_helper`; tool body is exactly
  `async with session_factory() as session: return await _helper(session, ...)`. Register
  `compare_deck_power` immediately after `assess_deck_power`.
- **Sharing one session for both assess calls is correct**: the path is read-only, awaits are
  sequential (never `asyncio.gather` two calls on one `AsyncSession` — sessions are not
  concurrency-safe), and each assess call re-checks `is_database_initialized` cheaply.
- **Determinism scope**: assess is read-only, so two compare calls against unchanged fixtures
  are the regression pair. Self-compare (`deck_id_a == deck_id_b`) is the cheapest all-zero
  proof and is legal input.
- **Wire surface for byte tests**: 7.4's probe established `result.content[0].text` IS the
  full JSON projection with model-declaration key order (see
  `test_assess_deck_power_wire_bytes_deterministic`'s docstring) — reuse that surface and
  cite the probe; also assert `.text` truthy + `json.loads(text) == structuredContent`
  (the 7.4 review-hardening pattern).
- **E2E fixtures built for this story** (`tests/integration/test_mcp_tools.py:439-603`):
  `_VECTOR_KEYS`, `_assessment_card`/`_assessment_cards` (8 cards: Krenko + Zada legendaries,
  Goblin Guide, Shock, Mountain, 2 confirmed GCs seeded in reverse bytewise order, 1 NULL-GC
  "Mystery Relic"), `assessment_card_db` (file-backed WAL session factory), and
  `_build_deck(client, *, name, format, rows=[(card_id, qty, commander)])` — its docstring
  literally says "Story 7.5 (compare_deck_power) builds its two-deck setups with this same
  shape". Snapshot seeding: `from tests.fixtures.combo_snapshot import seed_snapshot,
  snapshot_variant` (promoted in 7.4 for exactly this reuse).
- **GC → bracket math for the e2e delta test** (`src/logic/assessment/dimensions.py:105-111,
  369-374`): Commander floor 2 baseline; ≥1 confirmed GC → 3; ≥4 → 4; NULL never counts
  (AD-4). Deck_a = 0-GC commander deck (floor exactly 2), deck_b = same + 1 GC card (floor
  exactly 3) — but note the NULL-GC card must stay OUT of both decks if you want
  high-confidence sides, or IN both if you want the confidence blocks to match; either is
  fine, just be deliberate.
- **`import json` note**: `json.dumps(structuredContent)` dict comparison is NOT the byte test —
  string equality on the wire text is (7.4 decide-once #3).
- **mcp SDK**: `mcp>=1.27.0`; no new dependencies of any kind this story (web research
  decision: nothing new to research — FastMCP/Pydantic patterns are all in-repo precedent).

### Decide-once decisions this story owns (document each in code)

1. **Top-level `status` vocabulary.** Constraints: a closed `Literal`; `ok` only when both
   sides assessed `ok` AND formats agree; the failing side is nameable from the status alone;
   `database_not_initialized` is its own global status (not a side fault); `format_mismatch`
   is its own status; never `isError=True` for any of these. Recommended shape:
   `Literal["ok", "deck_a_failed", "deck_b_failed", "both_decks_failed", "format_mismatch",
   "database_not_initialized", "error"]` with the underlying per-side assess status token(s)
   named in `summary` (e.g. `"Deck A ('<id>') failed: deck_not_found."`). An alternative
   carrying explicit `status_a`/`status_b` fields is acceptable if the constraints hold —
   pick once, document in the result docstring. `error` covers a `DatabaseError`-driven
   `error` from either side (triage it as the side-failure OR the generic `error` — pick one
   and document; recommended: side-failure statuses cover it, keeping top-level `error`
   unreachable-but-reserved, mirroring how assess treats unexpected DB failure).
2. **Delta direction is b − a.** `deck_id_a` is the baseline ("before"), `deck_id_b` the
   candidate ("after") — matches the PRD §3 walkthrough (`compare_deck_power(old_id, new_id)`
   → "combo-potential up 12"). State it on every delta field docstring and in the tool
   registration docstring.
3. **Bracket change is the pair, not arithmetic.** `bracket_a` + `bracket_b` verbatim
   (`Literal[2,3,4] | None` each). No signed subtraction (None − 2 is meaningless; Standard
   sides are None). The summary may phrase it ("Bracket floor 2 → 3") — the structured block
   carries the endpoints.
4. **Flags diff semantics.** List flags (`game_changers`, `structural_gaps`): bytewise-sorted
   `*_added` / `*_removed` string lists from set difference. Combos: `combos_added` /
   `combos_removed` (spellbook_ids present on exactly one side) **plus**
   `combos_bucket_changed` (ids on both sides whose `bucket` differs, each entry
   `{spellbook_id, bucket_a, bucket_b}`) — without the third list the almost_included→included
   completion flip is invisible to a set-diff. Booleans: per-side pairs (`*_a`/`*_b`), fixed
   shape, no conditional keys (AD-7).
5. **Compare summary content.** A deterministic projection of the comparison block only:
   score movement with endpoints + tiers, bracket pair (Commander), headline diff counts
   (GCs added/removed, combos added/completed), and per-side confidence levels. Deck **names**
   are not on `Assessment` — either omit them (ids only) or thread the two deck names through
   from the assess results' `summary`... they aren't structured there either. Recommended:
   ids only; keep it short. Do NOT re-append `MULTIPLAYER_VARIANCE_CAVEAT` (it's the assess
   summary's prose; a diff is not a strength read). Document the choice.
6. **Module placement + reuse boundary.** New sibling module
   `src/mcp_server/tools/compare_deck_power.py` importing from
   `src.mcp_server.tools.assess_deck_power` (same layer — allowed; `data → logic → mcp_server`
   direction intact). It imports the helper + result/`Assessment`/`DataVintage`/`Confidence`
   models and NOTHING from `src/logic/assessment` beyond types already re-exported for the
   result contract (it shouldn't need any).

### Previous-story intelligence (7.4 + review)

- 7.4 built `_build_deck`, `assessment_card_db`, `_VECTOR_KEYS`, and the promoted
  `tests/fixtures/combo_snapshot.py` helpers explicitly for this story — reuse, don't fork.
  The 7.3 helper-level suite similarly established the in-memory-session + `_card` builder
  pattern for `test_compare_deck_power_tool.py` to mirror.
- 7.4's review added the "assert the byte surface is the payload" hardening
  (`block.text` truthy + parses back equal to `structuredContent`) — apply the same pattern
  to the new determinism test from the start, don't wait for review to catch it.
- Summary-fragment stability: 7.4's tests pin assess-summary fragments (`/100`,
  `no degradations`, `N combo variant(s)`, the caveat sentence). The compare summary is NEW
  prose — pin your own fragments in tests, and don't gratuitously re-use assess phrasing that
  would couple the two summaries.
- Seeding lessons that keep applying: commit fixture writes before calling tools (file-backed
  WAL visibility); seed sortable lists in reverse bytewise order so sorted-emission assertions
  can't pass by accident; an `almost_included` fixture = 2-card variant with exactly one piece
  in-deck.
- Task 0 has caught real traps in six consecutive stories — this story's specific trap is the
  **uncommitted 7.4 review resolution** sitting in the working tree at story-creation time.
- 7.1 review deferral still stands: `cards_unresolved` is structurally unreachable e2e
  (orphan-row handling is a deferred data-layer story) — nothing in this story changes that.
- Deferred (not this story): 7.4's two e2e-hardening defers (bracket-4 floor e2e, positive
  `data_vintage` present-path wire assertion) live in `deferred-work.md`; if the compare e2e
  tests happen to positively assert seeded vintage values through `data_vintage_a/_b`, note in
  the story record that the second defer is thereby covered — don't expand scope to chase it.

### Architecture compliance checklist

- **AD-1/NFR7:** `async def`, stateless, per-call params, registered beside the analysis
  tools; compare composes two assessments through the same pure pipeline — no second path.
- **AD-7:** sibling versioned result; fixed closed shape; `comparison: None` on non-ok;
  no format-conditional keys (Standard compare carries `bracket_a/_b = None`, empty diff
  lists, per-side booleans).
- **AD-8/NFR1:** byte-identical wire JSON for identical inputs; every new list sorted
  bytewise at creation; int deltas; no call-time clock — "as of" only via the two vintage
  blocks.
- **AD-6/NFR3:** failures degrade to graceful statuses naming the side; never an exception
  to the client, never `isError=True`, never a silent zero-delta masquerading as ok.
- **AD-2/AD-9:** the new module contains zero scoring/matching logic — orchestration and
  arithmetic on two already-serialized `Assessment` blocks only.
- **NFR4:** fully local, two in-process assess runs — effectively instant.

### Testing standards summary

- pytest config in `pyproject.toml`; `asyncio_mode = "auto"` (plain `async def test_...`);
  `--strict-markers`; `tests.*` exempt from `mypy --strict` (ruff/naming still apply);
  Google docstrings on helpers.
- Helper-level home: `tests/integration/mcp_server/test_compare_deck_power_tool.py` (new,
  mirrors `test_assess_deck_power_tool.py` — file-backed engine, shared seeded session).
  E2E home: `tests/integration/test_mcp_tools.py`
  (the epic AC names the in-process client; extend, don't rewrite — existing assess tests and
  their pinned fragments must stay green).
- Do NOT touch `tests/integration/conftest.py::_sample_cards` (count-pinned, 7.4 AC 5) or the
  7.3/7.4 suites beyond additive imports.
- Baseline **1,323** tests at story start (verify in Task 0). TDD order: models RED →
  helper GREEN → registration → e2e.

### Project Structure Notes

- New: `src/mcp_server/tools/compare_deck_power.py`,
  `tests/integration/mcp_server/test_compare_deck_power_tool.py`.
- Modified: `src/mcp_server/server.py` (imports + one registration),
  `tests/integration/test_mcp_tools.py` (new compare e2e tests reusing 7.4 fixtures).
- Regenerated: `plugin/**` mirror (pre-commit `build-plugin-sync` — a diff is EXPECTED and
  must be committed this time; the plugin's tool surface gains `compare_deck_power`).
- Untouched: `src/logic/**`, `src/data/**`, `scripts/**`, profiles, benchmark fixtures.
- Branch: stays on `feat/deck-power-assessment`; merge decision at epic completion.

### References

- [Source: _bmad-output/planning-artifacts/epics-deck-power-assessment.md#Story 4.5] — story +
  ACs (sprint key `7-5`); FR26 text; Epic 4 preamble; AD-1/AD-7/AD-8 texts.
- [Source: _bmad-output/planning-artifacts/prds/prd-Artificial-Planeswalker-2026-07-11/prd.md#§3]
  — the compare walkthrough fixing delta direction (old→new) and the snapshot-via-import_decklist
  workflow; FR26 (§4); addendum §A (caller-side comparison rejected 2026-07-12).
- [Source: src/mcp_server/tools/assess_deck_power.py:193-266,667-829] — `Assessment` /
  `AssessDeckPowerResult` contracts, helper signature, statuses, `DataVintage`/`Confidence`
  models to reuse.
- [Source: src/mcp_server/server.py:38-41,474-512] — aliased-helper import + registration
  pattern to copy; per-call session usage.
- [Source: tests/integration/test_mcp_tools.py:439-603] — `_VECTOR_KEYS`, `_assessment_cards`,
  `assessment_card_db`, `_build_deck` (built for 7.5 reuse); wire-surface docstring in
  `test_assess_deck_power_wire_bytes_deterministic`.
- [Source: tests/fixtures/combo_snapshot.py] — `seed_snapshot` / `snapshot_variant` (promoted
  in 7.4 for this story).
- [Source: tests/integration/mcp_server/test_assess_deck_power_tool.py:64-97] — `_card` builder
  + in-memory-session pattern for the new helper-level suite.
- [Source: src/logic/assessment/dimensions.py:105-111,369-374] — GC bracket gate behind the
  e2e 2→3 delta expectation.
- [Source: src/data/schemas/combo.py] — `ComboRecord` fields (`spellbook_id` diff identity,
  `bucket` values).
- [Source: _bmad-output/implementation-artifacts/7-4-end-to-end-tool-test-determinism-diff-regression.md]
  — fixtures built for 7.5; wire-surface probe; review-hardening patterns; calibration freeze.
- [Source: _bmad-output/implementation-artifacts/deferred-work.md#Deferred from: code review of story-7.4]
  — the two e2e-hardening defers this story may incidentally cover but must not chase.
- [Source: _bmad-output/implementation-artifacts/pre-epic-7-real-deck-gate-report-2026-07-17.md#Cross-deck observations]
  — the named calibration inputs frozen out of scope (AC 9).

## Dev Agent Record

### Agent Model Used

claude-fable-5 (Claude Fable 5)

### Debug Log References

- TDD RED→GREEN throughout: model tests failed on missing module, helper tests on missing
  function, e2e tests on unregistered tool — each implemented to green with no test-after code.
- Two fixture-expectation corrections during GREEN (code was correct both times):
  (1) helper ok-path scenario completes a 2-card variant, which is an included
  `two_card_infinite` — the FR15 hard trigger floors deck_b at Bracket **4**, outranking the
  1-GC floor of 3 (expectation updated, documented in-test); (2) in the wire-determinism e2e
  scenario deck_a already held one piece of EACH seeded variant, so both variants flip
  almost_included → included (`combos_bucket_changed`) rather than appearing in `combos_added`.
- `tests/integration/test_build_plugin.py::test_server_registers_expected_tools` pins the exact
  tool set — updated 18 → 19 with `compare_deck_power` (the expected plugin-surface growth).

### Completion Notes List

- Decide-once decisions, all documented in code: (1) status vocabulary = the recommended
  closed Literal (`ok | deck_a_failed | deck_b_failed | both_decks_failed | format_mismatch |
  database_not_initialized | error`), with assess-side `error` triaged as the side failure and
  top-level `error` reserved-but-defensive (proven reachable only by stubbing the composed
  helper); `database_not_initialized` checked from either side before side triage (global,
  not a side fault). (2) Delta direction b − a documented on every delta field + tool
  docstring. (3) Bracket = verbatim endpoint pair `Literal[2,3,4] | None`. (4) Flags diff =
  sorted `*_added`/`*_removed` from set difference + `combos_bucket_changed`
  (`{spellbook_id, bucket_a, bucket_b}`) + per-side boolean pairs. (5) Summary = ids-only
  deterministic projection (score movement + endpoints/tiers, bracket pair when Commander,
  headline diff counts, per-side confidence); multiplayer-variance caveat deliberately NOT
  re-appended. (6) Module = sibling `compare_deck_power.py` importing only from
  `assess_deck_power` / `messages` / schema-layer types — zero `src/logic` scoring imports.
- AC 2 proven two ways: helper test asserts field-wise equality against two direct
  `assess_deck_power` calls; e2e test asserts the same against two client-level assess
  results' `structuredContent`.
- Determinism (AC 6): model-level `model_dump_json()` byte equality, helper-run repeat-call
  byte equality, and wire-level `result.content[0].text` string equality (7.4 probe surface,
  with the review-hardening truthy + parses-back-equal pin). Self-compare all-zero verified
  (ids stripped, legal).
- **7.4 defer coverage note:** the compare GC e2e test positively asserts the SEEDED snapshot
  vintage values (`imported_at`, `export_version`) through `data_vintage_a/_b` at the wire —
  the second 7.4 e2e-hardening defer (positive present-path `data_vintage` wire assertion) is
  thereby covered incidentally. The first defer (bracket-4 floor e2e) remains open in
  deferred-work.md (not chased, per story scope).
- Gates (AC 9): full suite **1,348 passed** (baseline 1,323 + 25 new: 21 helper-level + 4
  e2e), 0 regressions; `mypy --strict src/` clean (70 files); `ruff check` + `ruff format`
  clean; no changes to `src/logic/**`, profiles, or scoring behavior (calibration freeze
  respected).

### File List

- `src/mcp_server/tools/compare_deck_power.py` (new — models + helper)
- `src/mcp_server/server.py` (modified — import block + `compare_deck_power` registration)
- `tests/integration/mcp_server/test_compare_deck_power_tool.py` (new — 21 tests)
- `tests/integration/test_mcp_tools.py` (modified — 4 compare e2e tests appended)
- `tests/integration/test_build_plugin.py` (modified — expected tool set 18 → 19)
- `plugin/**` (regenerated mirror — gains `compare_deck_power`)
- `_bmad-output/implementation-artifacts/7-5-compare-deck-power-tool.md` (this story record)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (status tracking)

## Change Log

- 2026-07-18: Story created (create-story workflow) — comprehensive context from epic Story 4.5
  (FR26), the 7.1–7.4 stack as-built, 7.4's purpose-built reusable fixtures, and the AD-7/AD-8
  determinism contract. Status: ready-for-dev.
- 2026-07-18: Story implemented (dev-story workflow, TDD) — `compare_deck_power` tool: result
  models, compose-two-assessments helper with pure b − a delta assembly, server registration,
  21 helper-level + 4 e2e tests. Full suite 1,348 green, mypy/ruff clean. Status: review.
