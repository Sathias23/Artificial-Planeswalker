# Deferred Work

## Deferred from: code review of story-7.4 (2026-07-17)

> Test-hardening gaps in the `assess_deck_power` e2e suite (tests-only story; all 7 ACs met, suite green). Neither is a product defect — both are e2e-coverage extensions whose behavior is already guarded at the unit/model level.

- source_spec: `_bmad-output/implementation-artifacts/7-4-end-to-end-tool-test-determinism-diff-regression.md`
  summary: 'Bracket-4 floor (≥4 confirmed Game Changers) is unreachable through the e2e client — the `_assessment_cards` fixture seeds only two `game_changer=True` cards and Commander singleton rules cap each at quantity 1, so a `bracket == 4` result (and the GC ≥4 gate in dimensions.py) is never exercised end-to-end. Future hardening: add ≥4 distinct GC cards to reach the floor-4 gate through the tools.'
  evidence: 'Edge Case Hunter trace: dimensions.py GC gate GC_BRACKET_FOUR_MIN=4, count is quantity-aware; fixture exposes e2e-gc-bolas + e2e-gc-aura only. The ≥4 gate is covered by unit scorer tests (test_assessment_scorer.py), not this client suite.'

- source_spec: `_bmad-output/implementation-artifacts/7-4-end-to-end-tool-test-determinism-diff-regression.md`
  summary: 'The populated `data_vintage` combo values are never positively asserted at the e2e/wire level — the absent-snapshot test pins the null path (`combo_snapshot_imported_at`/`export_version is None`), but no seeded e2e test asserts the present path equals the fixture''s seeded `export_version="5.6.0"` / `imported_at="2026-07-16T09:07:00+00:00"`. A passthrough bug that dropped or garbled the vintage on the present path is caught only at model level (7.3 helper tests). Future hardening: assert the populated vintage in the commander happy-path test.'
  evidence: 'Blind Hunter + Acceptance Auditor: null-vs-present vintage contract is half-covered e2e; seeded values live in tests/fixtures/combo_snapshot.py:63-65.'

## Deferred from: code review of spec-pre-epic-7-real-deck-gate (2026-07-17)

- source_spec: `_bmad-output/implementation-artifacts/spec-pre-epic-7-real-deck-gate.md`
  summary: '`combo_potential` counts `almost_included` variants whose single missing piece is not legal in the deck''s format, inflating the dimension for constructed decks — the matcher (`match_combos`) and the dimension scoring are format-blind on the missing piece.'
  evidence: 'G-R2 gate run 2026-07-17: Abzan Dragons and Prismatic Dragon (both Standard) each scored combo_potential=100 from Betor-anchored almost_included variants whose missing partners (e.g. Archfiend of Despair, Mycosynth Lattice, Wound Reflection) are not Standard-legal — the combo can never be completed in-format. Pre-existing product behavior (5.6/6.3 design), surfaced by the Blind Hunter review of the gate report; a natural Epic 7 calibration input.'

- source_spec: `_bmad-output/implementation-artifacts/spec-pre-epic-6-importer-gate.md`
  status: ✅ RESOLVED (2026-07-16, commit 18880dc)
  summary: 'Transformer rejects all 33 reversible_card printings ("Name // Name") with `missing required field(s): type_line` — Scryfall''s reversible layout carries type_line (and cmc) only on card_faces. Fix = derive required fields from faces in transform_scryfall_card (a transform-contract change held back by the gate spec''s Ask-First boundary); until then those 33 oracle identities keep pre-existing rows and are surfaced by the stale-remaining warning each run.'
  resolution: 'Shape-gated face derivation in transform_scryfall_card: cards with NO top-level type_line (the reversible signature) derive name (deduped, so "Anje Falkenrath // Anje Falkenrath" -> "Anje Falkenrath" for exact decklist lookups), type_line, mana_cost, cmc, colors (WUBRG-ordered face union) and all-faces-agree power/toughness from card_faces; ijson Decimal face values sanitized to float so the card_faces JSON column serializes. Cards WITH a top-level type_line transform byte-identically (transform/MDFC/split untouched). Test-pinned (4 new unit tests); next import run should show 0 rejects and clear the 33-identity stale warning.'
  evidence: 'Live acceptance run 2026-07-15 (b74-successor): all 33 rejects share the doubled-name + type_line-missing signature (Reckoner Bankbuster, Anje Falkenrath, Zndrsplt, …); the gate''s G-I2 diagnostics made the reason string visible for the first time. Parallels the resolved oracle_id face-fallback fix (resolve_oracle_id, 0.3.0).'

- source_spec: `_bmad-output/implementation-artifacts/spec-pre-epic-6-importer-gate.md`
  summary: 'TOCTOU window in reconcile_oracle_identities: a deck_cards row committed by a concurrent connection (e.g. import_decklist via the live MCP server) between the reconcile''s deck_cards plan-scan and its write phase is never repointed, and the stale cards row is then deleted with FK enforcement OFF — a silently dangling deck_cards.card_id. Fix candidates: re-scan deck_cards after acquiring the write lock (BEGIN IMMEDIATE / first-write upgrade), or verify-and-repoint residual references just before the delete.'
  evidence: 'Edge Case Hunter trace over scryfall.py plan-scan vs execute+delete phases; SQLite deferred transactions take no lock until the first write, and the central DB is shared with a live MCP server. Window is narrow (scan-to-write span) and requires a concurrent deck write during a bulk import.'
- source_spec: `_bmad-output/implementation-artifacts/spec-pre-epic-6-importer-gate.md`
  summary: 'Reconcile deletions orphan card_vec/card_embedding_meta rows until a build_search_index run with prune=true (prune defaults to False): KNN over-fetch returns deleted ids that vanish at the cards JOIN, thinning semantic results. Consider auto-pruning vectors for deleted card ids at reconcile time, or defaulting prune=true when the importer reports rows_deleted > 0.'
  evidence: 'Both reviewers; src/search/index_builder.py orphan cleanup only runs during index builds, and build_search_index.prune defaults False. Mitigated in-gate by the result message now recommending prune=true after deletions.'

## Deferred from: dev of story-5.9 (2026-07-14)

> Live-DB data-quality issues discovered while closing the 5.9 benchmark gate. Out of the
> story's frozen scope (AC10: no `src/data/**` / `scripts/` edits); the operational damage was
> repaired by hand on Brad's machine (documented in the 5.9 Completion Notes) but the root
> causes live in the importer.

- source_spec: 5-9-pure-score-entry-point-benchmark-validation.md
  summary: 'Re-running `import_scryfall_data.py` accumulates duplicate rows per card name: Scryfall''s default_cards "preferred printing" per oracle identity changes between bulk snapshots, so each refresh inserts rows under NEW printing ids while the old printing rows persist (observed 2026-07-14: 51,189 rows for ~38k cards; 12,992 stale rows with `game_changer` NULL because the upsert only touches the new ids). Consequences: `find_by_name_exact` (ORDER BY id LIMIT 1) resolves 4,711 names to an arbitrary STALE printing, and any new backfilled column stays NULL on stale rows. Fix candidates: reconcile/delete rows whose oracle_id gained a fresh printing (mind deck_cards FK references), key the upsert by oracle_id, or propagate oracle-level fields (like game_changer) across all rows of the same oracle_id post-import.'
  evidence: 'Central cards.db state 2026-07-14 pre-repair; epic-4 retro recorded 0 NULL on 2026-07-12, the Jul-14 refresh reintroduced 12,992. Hand-repair applied: copy game_changer across same-oracle_id rows, then set the 36 residual NULLs FALSE (none on the GC list).'
- source_spec: 5-9-pure-score-entry-point-benchmark-validation.md
  summary: 'The bulk import reports "Errors: 36" with no per-card diagnostics reaching the operator log tail, and those 36 cards (incl. Blood Crypt, Hallowed Fountain, Reckoner Bankbuster) silently keep stale data — likely the new printing id colliding with a uniqueness constraint while a different-id row for the same oracle identity already exists. Surface the failing card names + exception class in the import summary, and count them against a "stale rows remaining" warning.'
  evidence: 'b74hepj01 import run 2026-07-14: 38,197 inserted / 36 errors; the 36 error cards exactly matched the 36 names left game_changer-NULL after the oracle_id repair.'

## Deferred from: code review of story-5.8 (2026-07-14)

> Both are Story 5.9 (calibration / threshold + weight tuning) concerns surfaced during the 5.8 review — neither is a correctness defect in the shipped code (all inputs are frozen, type-pinned, and test-pinned). Parallels the 5.7 `win_turn_band` defer directly below.

- source_spec: 5-8-for-format-aggregate-tier-label-standard-fork-confidence-vocabulary.md
  status: ✅ RESOLVED (Story 5.9, 2026-07-14)
  summary: '`tier_label`/`aggregate_score` trust their frozen profile''s shape & weight validity: `tier_label` (aggregate.py:146) assumes exactly 4 strictly-ascending `tier_thresholds` (a 5+-tuple → IndexError; non-ascending → silent mislabel), and `aggregate_score` (aggregate.py:116) assumes non-negative + finite weights (NaN → ValueError; negative → silent monotonicity break). Unreachable with the shipped frozen+tested profiles, but 5.9 hand-tunes both `weights` and `tier_thresholds` — optional cheap defense-in-depth for the tuning workflow.'
  evidence: 'aggregate.py:146 `TIER_LABELS[bisect_right(profile.tier_thresholds, score)]`; aggregate.py:116 weighted sum. Invariants pinned by profiles type `tuple[int,int,int,int]` + test_assessment_profiles.py (non_negative, sum-to-1.0, ascending). Same class as the 5.7 `win_turn_band` guard defer.'
  resolution: '`aggregate_score` now raises `ValueError` on a negative or non-finite weight; `tier_label` raises on cuts not strictly ascending within `(0, 100)`. Test-pinned (`TestStory59Guards` in test_assessment_aggregate.py, incl. a shipped-profiles-pass check).'
- source_spec: 5-8-for-format-aggregate-tier-label-standard-fork-confidence-vocabulary.md
  status: ✅ RESOLVED (Story 5.9, 2026-07-14)
  summary: '`tier_thresholds` domain `(0, 100]` permits a cut of exactly 100, making the top band (`Competitive`) a degenerate single-point band reachable only by an exact score of 100. Harmless for the shipped `(20, 40, 60, 80)`; add a guardrail when 5.9 re-cuts per-format anchors.'
  evidence: profiles.py:126 field type + test_assessment_profiles.py in-domain check `0 < cut <= 100`.
  resolution: 'Domain tightened to `(0, 100)`: `tier_label` guards it and the aggregate profile-shape test now asserts `0 < cut < 100` (a cut at exactly 100 is a tuning mistake, never a meaningful configuration).'

## Deferred from: code review of story-5.7 (2026-07-14)

> All three are Story 5.9 (calibration / benchmark tuning) concerns surfaced during the 5.7 review — none is a correctness defect in the shipped code.

- source_spec: 5-7-dimension-vector-commander-bracket-floor-cedh-candidacy.md
  status: ✅ RESOLVED — KEPT AS-IS, documented (Story 5.9, 2026-07-14)
  summary: '`card_advantage` dimension structurally caps at 98 (80 count-weight + 18 max tutor bonus), never reaching 99/100 — revisit the ceiling during 5.9 calibration.'
  evidence: dimensions.py:562 `_card_advantage_score`; provisional/5.9-owned mapping by design.
  resolution: 'Keep-decision documented in `_card_advantage_score`''s docstring after the calibration pass: the 2-point headroom is invisible under the aggregate weights and benchmark cuts, and re-normalizing the two terms would change every deck''s score for zero benchmark benefit.'
- source_spec: 5-7-dimension-vector-commander-bracket-floor-cedh-candidacy.md
  status: ✅ RESOLVED (Story 5.9, 2026-07-14)
  summary: '`sixty_card` curve targets (interaction 8 / draw 6 / instant-cheap 4) are self-labelled provisional guesses, and mana_efficiency shares one land-delta penalty slope across 99- and 60-card decks — Standard vs Commander vectors are not on a comparable scale until 5.9 anchors them.'
  evidence: dimensions.py:177-201 target dicts; only Commander targets trace to the Command Zone template.
  resolution: 'Closed by per-format `tier_thresholds` anchoring: Standard cuts (28, 45, 65, 85) are anchored against the four Standard benchmark bands independently of Commander''s (20, 40, 60, 80), and raw 0-100 aggregates are never compared across formats — stated in the STANDARD_PROFILE tier_thresholds comment. The sixty_card curve-target VALUES stay provisional (the Standard benchmark orders cleanly without touching them).'
- source_spec: 5-7-dimension-vector-commander-bracket-floor-cedh-candidacy.md
  status: ✅ RESOLVED (Story 5.9, 2026-07-14)
  summary: '`_speed_score` has no guard for a malformed `win_turn_band` (`lo > hi`) — unreachable with the shipped frozen+tested profiles, but a future 5.9 band edit of the form `hi = lo-4` divides by zero and `hi < lo` inverts the mapping. Optional cheap defense-in-depth for the band-editing workflow.'
  evidence: dimensions.py:484 (`slowest - fastest = band_hi - band_lo + 4`); invariant documented at profiles.py:86-87.
  resolution: '`_speed_score` now raises `ValueError` on `lo > hi` (a `lo == hi` pinpoint band stays valid — the ±2 pad keeps the divisor non-zero). Test-pinned (`TestStory59WinTurnBandGuard` in test_assessment_dimensions.py).'

## Deferred by scope-split: Kotis session plugin-improvement leads (2026-07-10)

> Source: `temp/kotis-fangkeeper-brawl.md` §"Plugin improvement leads" (live Brawl sessions
> 2026-07-05). Brad ran `bmad-quick-dev` on all 8 leads and chose **Split** at the multi-goal
> gate: leads 1 (games union) + 3 (brawl singleton) are the current run; the six below are
> deferred, each an independently shippable quick-dev run. Full observed evidence for each is in
> the source file.

- source_spec: none
  summary: Add a saboteur/combat-damage-trigger pattern to `detect_synergies` (rated the Kotis deck "low cohesion").
  evidence: Split from the 8-lead Kotis improvement intent; isolated synergy-logic change, independent of the validator/import work chosen first.
- source_spec: none
  summary: Bulk deck-import MCP tool accepting an Arena export blob (per-line resolve, per-line ok/ambiguous/not-found report).
  evidence: Split from the 8-lead Kotis improvement intent; a new standalone tool (saving the 60-card deck took ~50 `add_card_to_deck` calls, the 100-card port 75 more).
- source_spec: none
  summary: Import-time legality-snapshot sanity check for pool-superset invariants (e.g. Pym Particles `standardbrawl: legal` but `brawl: not_legal` is impossible).
  evidence: Split from the 8-lead Kotis improvement intent; import-script validation, standalone. Natural pairing with the games-union import work if the import script is revisited.
- source_spec: none
  summary: Strip parenthetical reminder text from oracle text before embedding (menace cards pollute "unblockable" queries, convoke pollutes "ramp"); requires index rebuild.
  evidence: Split from the 8-lead Kotis improvement intent; embedding-pipeline change with a rebuild cost — batch with other re-embed work if possible.
- source_spec: none
  summary: Intersection mode (or rerank/decompose guidance) for compound semantic queries, plus a playability prior on ranking (Llanowar Elves absent from a ramp top-40 Prismite topped).
  evidence: Split from the 8-lead Kotis improvement intent; the largest, most design-heavy lead — benefits from the reminder-text fix landing first. Overlaps the existing "Compound-intent dilution" Epic-3 candidate below.
- source_spec: none
  summary: '`capture_arena_window` tool — screenshot the MTGA window (Win32 `PrintWindow`/`mss`) for board reads; opt-in, graceful `window_not_found`.'
  evidence: Split from the 8-lead Kotis improvement intent; first tool touching the local machine rather than the card DB, so it needs its own opt-in design pass.

## Deferred from: code review of spec-games-union-brawl-singleton (2026-07-10)

- source_spec: `_bmad-output/implementation-artifacts/spec-games-union-brawl-singleton.md`
  status: ✅ RESOLVED (0.3.0, 2026-07-11)
  summary: Face-keyed aggregation (`card_faces[0].oracle_id` fallback in `src/data/importers/aggregate.py`) is inert — `transform_scryfall_card` hard-requires a top-level `oracle_id`, so reversible-layout cards are still rejected downstream, and `reconcile_games` matches aggregates by `CardModel.oracle_id` only.
  evidence: Blind Hunter traced the pass-2 path — cards grouped by the face/self fallbacks reach the transformer and are error-counted there (pre-existing transformer limitation, parity with the old oracle_cards import). Fix belongs in a transformer pass (accept face-level oracle_id) plus a reconcile lookup keyed the same way as `group_key`.
  resolution: Extracted `resolve_oracle_id` (top-level → `card_faces[0].oracle_id`) as the single oracle-identity source shared by `group_key` and `transform_scryfall_card`; the transformer no longer hard-requires a top-level `oracle_id`, so reversible cards import with `oracle_id == group_key` — which makes the `reconcile_games` lookup-by-`oracle_id` align with `group_key` automatically. Verified end-to-end: a reversible card dedupes to one row with unioned games (was dropped entirely).
- source_spec: `_bmad-output/implementation-artifacts/spec-games-union-brawl-singleton.md`
  status: ✅ RESOLVED (0.3.0, 2026-07-11)
  summary: '`reconcile_games` failure after `import_cards` has committed leaves the DB populated but `initialize_database` reports `status="error"`, and a plain retry short-circuits `already_initialized` with games left stale.'
  evidence: Edge Case Hunter, `src/data/importers/scryfall.py` reconcile stage — the import commits per batch, so a reconcile-stage DatabaseError (lock/disk) can't roll it back. Narrow failure window; remedy is `update=true` (re-runs reconcile). Consider catching reconcile errors as a warning or surfacing a "re-run with update=true" hint in the error message.
  resolution: The orchestrator now catches `IntegrityError`/`DatabaseError` from the reconcile stage and logs a warning instead of failing the run (the cards already committed), so the import reports success and stale pre-existing rows refresh on the next `update=true`. The first-run half is additionally covered by the 0.3.0 `import_state` marker (a first-run failure leaves the DB flagged partial, so a retry re-imports rather than short-circuiting).

## Deferred from: code review of first-run-data-initialization (2026-06-28)

> Surfaced by the 3-reviewer adversarial pass on `spec-first-run-data-initialization.md`. The
> contract gap (uncaught `init_database` failure) and two real robustness items (partial-import
> *exception* path now clears the truncated `cards`; `build_search_index(rebuild=True)` now resolves
> the embedder before the destructive drop) were patched in-branch. The items below are real but
> either pre-existing config or narrow/concurrency edges left for a focused later pass.

- **✅ RESOLVED (0.3.0, 2026-07-11).** No `busy_timeout` → `SQLITE_BUSY` on concurrent writers (Edge Case Hunter, HIGH). Neither the
  async engine (`src/data/database.py::create_engine`) nor the sync `ConnectionFactory`
  (`src/search/connection.py`) sets `busy_timeout`/`connect_args={"timeout": …}`, so SQLite's
  default-0 timeout makes a second writer fail immediately with `database is locked` rather than
  waiting. Pre-existing config, but the new `initialize_database` (bulk write) + `build_search_index`
  (index write) tools make concurrent-writer collisions more likely. Fix project-wide: set
  `PRAGMA busy_timeout=5000` on the sync factory and `connect_args={"timeout": 5}` on the async
  engine (matches the documented WAL topology).
- **✅ RESOLVED (0.3.0, 2026-07-11) — `import_state` in-progress marker.** Process-kill mid-import leaves a partial DB mistaken for complete (Edge Case Hunter, HIGH —
  *exception* half patched). The importer commits per 1000-card batch; the in-branch fix clears the
  partial `cards` when the import raises, so a *failed* import retries cleanly. But a hard process
  kill between batches can't run that cleanup, leaving e.g. 1000 of ~30k cards — which the ≥1-row
  idempotency check then reports as `already_initialized`, permanently. Full fix: write an
  `import_complete` sentinel (meta row) only after the final commit and gate `already_initialized`
  on it, or make the import a single transaction.
- **Corrupt/malformed DB file raises out of the "never raises" guards** (Edge Case Hunter, MED). A
  truncated `-wal` / malformed header makes even the `sqlite_master` probe in either
  `is_database_initialized` raise `DatabaseError`/`OperationalError`; because the guard runs *above*
  each tool's `try/except`, that propagates as a raw error instead of a graceful status. Fix: wrap
  the probes in `try/except (OperationalError, DatabaseError): return False`, or add a distinct
  `database_corrupt` status.
- **Concurrent `initialize_database` double-imports** (Edge Case Hunter, MED). The idempotency check
  and the import aren't atomic/locked, so two concurrent invocations both download + import (the
  upsert importer keeps data correct, but wastes a ~3-min download and contends on the write lock —
  near-certain to fail one of them until `busy_timeout` above is set). Fix: an app-level
  `asyncio.Lock` around the tool, or rely on `busy_timeout` so the loser re-checks and returns
  `already_initialized`.

## ✅ Resolved by first-run-data-initialization (2026-06-28)

> Closed by `spec-first-run-data-initialization.md` — the in-client `initialize_database` /
> `build_search_index` tools plus a graceful `database_not_initialized` status across every
> card/deck tool. The items below are closed; they remain listed in their original sections for
> traceability.

- **MCPB bundle has no first-run data bootstrap or guidance** (mcpb-bundle review, High-for-UX). A
  fresh `.mcpb` now bootstraps in-client: the assistant runs `initialize_database` (Scryfall card
  import) and `build_search_index` (embedding index), and every card/deck tool returns
  `database_not_initialized` with a run-`initialize_database` hint instead of the opaque "A database
  error occurred". No prebuilt DB is shipped (license held — build-on-first-run only).
- **`README.md` overclaimed Claude-Desktop first-run + that `setup.py` builds the index**
  (mcpb-bundle review `README.md:68`; licensing-repo-health review `README.md:38`/`:44`). The Quick
  start and Claude Desktop sections now describe the real flow: `setup.py` (or `initialize_database`)
  downloads the cards; the semantic index is a separate `build_search_index` step.
- The semantic tools' `index_unavailable` message now points at the `build_search_index` **tool**
  rather than the `scripts/build_card_embeddings.py` terminal command (which a GUI client can't run).

> Still open from those reviews (out of this spec's scope): `setup.py:87` prints the stale
> `./data/cards.db` path; `project-context.md`'s "all MCP tools sync `def`" drift; the `report_bug`
> tool is **intentionally not** guarded (it is card-data-independent and already graceful — see the
> spec's Change Log).

## Public-release goals deferred by scope-split (2026-06-27)

> Source: `RELEASE-STRATEGY.md`. Brad ran `bmad-quick-dev` to "execute RELEASE-STRATEGY.md" and
> chose **Split — DB centralization first** at the multi-goal gate. This run (branch
> `feat/central-data-dir`) implements **only §3 (central OS data dir)**. The remaining
> independently-shippable deliverables below are deferred and should each be picked up as their
> own quick-dev run, in roughly the strategy's §7 order. Each links back to the strategy section.
>
> **Two cross-cutting constraints carried forward:**
> 1. **The prune only _untracks_ the workflow's framework + skills** (`_bmad/`, `.claude/skills/bmad-*`)
>    via `git rm --cached` + gitignore — removed from the public repo but kept on disk, so the workflow
>    still runs locally — and **`_bmad-output/` stays tracked** (Brad, 2026-06-28). No mid-run ordering
>    hazard anymore, since nothing bmad-related is hard-deleted from the working tree.
> 2. **Outward-facing / irreversible steps stay manual.** Secret scan, `git tag v0.1.0`, cutting
>    the GitHub Release, and flipping the repo public are Brad's call — automate the prep, stop
>    at that line.

- **Prune legacy + dev tooling (§1, §2).** Three distinct treatments (Brad, 2026-06-28):
  - **Hard delete (`git rm`):** the legacy PydanticAI/Chainlit stack (`legacy/`, `public/`),
    superseded root docs, scratch `scripts/test_*.py`, `examples/`, internal `docs/` files; curate
    `docs/` down to architecture/bug-report/performance.
  - **Untrack but keep on disk (`git rm --cached`) + gitignore:** the BMAD **framework + dev skills**
    (`_bmad/`, `.claude/skills/bmad-*`) — gone from the public repo but kept locally so the workflow
    still runs.
  - **KEEP tracked:** `_bmad-output/` (planning + implementation artifacts = public design record).
  Then edit `.gitignore`: un-ignore `.github/`, add `/_bmad/` + `.claude/skills/bmad-*/`, but **not**
  `/_bmad-output/`. Mechanical; no logic.
- **Trim deps & package metadata (§6).** `pyproject.toml`: drop orphaned `anthropic`/`openai`/
  `asyncpg`, move `logfire` to an optional `observability` group, verify-and-likely-drop
  `tenacity`/`python-dotenv`, add `platformdirs` (already added by the §3 run — reconcile), remove
  the `[dependency-groups] legacy` block, rewrite the "built with PydanticAI" description, set a
  real `authors` email (sathias@slopstudio.net), add `[project.scripts]` console entry points.
  (**`.env.example` cleanup — including deleting the `LEGACY ONLY` section and adding the
  `PLANESWALKER_DATA_DIR` note — was pulled into the `feat/central-data-dir` run at Brad's
  request, so it's done; only the `pyproject.toml` work remains under §6.**)
- **Licensing & repo-health docs (§6).** Add `LICENSE` (MIT, Copyright (c) 2026 Brad Sprigg),
  `NOTICE` (Scryfall/WotC attribution + Fan Content Policy), `SECURITY.md`, `CONTRIBUTING.md`,
  `CHANGELOG.md` (start 0.1.0, record the central-DB migration note), and the README attribution/
  disclaimer block. (README body was already rewritten in commit d1dc5a2.)
- **CI workflow (§6).** `.github/workflows/ci.yml`: `uv sync` → `ruff check` → `ruff format
  --check` → `mypy src/` → `pytest -m "not integration"`, matrix on 3.12/3.13; plus issue/PR
  templates.
- **MCPB bundle for Claude Desktop (§4).** Add `manifest.json` (manifest_version 0.4, `uv`
  runtime, `PLANESWALKER_DATA_DIR` user_config — **depends on the §3 env var**); `npx
  @anthropic-ai/mcpb pack`; smoke-test install. Attach the `.mcpb` to the GitHub Release.
- **Release mechanics (§7.1, §8 — MANUAL).** Run the full-history secret scan
  (`uvx gitleaks detect --source . --log-opts="--all"`), tag `v0.1.0`, cut the GitHub Release with
  the `.mcpb` attached, flip the repo public. Brad executes these.

## Deferred from: code review of licensing-repo-health-docs (2026-06-28)

> Surfaced by the 3-reviewer adversarial pass on the §6 licensing/repo-health docs run
> (`spec-licensing-repo-health-docs.md`). The doc-accuracy issues in the *new* files
> (CONTRIBUTING/CHANGELOG over-claiming that `setup.py` builds the search index; the "all MCP
> tools are sync `def`" overstatement) were patched in-branch. The items below are real but
> pre-existing or outside this run's frozen scope (no README/code edits).

- **README claims `setup.py` builds the search index (it doesn't).** [`README.md:38`](../../README.md#L38)
  (`# installs deps, builds the card DB + index`) and [`README.md:44`](../../README.md#L44)
  ("builds the local search index") both assert the one-time `setup.py` run produces the semantic
  index. Verified false: `setup.py` only runs `initialize_database()` (Scryfall card import) — no
  `build_card_embeddings` / `card_vec` reference anywhere in it. The index must be built separately
  via `uv run python scripts/build_card_embeddings.py`. So a user who follows the README Quick start
  and immediately calls `semantic_search_cards` gets `status="index_unavailable"`. Out of scope here
  (the spec froze "no README edits"); fix in a focused README-accuracy pass — either correct the two
  lines, or have `setup.py` actually build the index after import.
- **`setup.py` post-`.env` message hard-codes the old `./data/cards.db` path.**
  [`setup.py:87`](../../setup.py#L87) prints `Defaults work out of the box (SQLite at ./data/cards.db…)`,
  stale since the central-OS-data-dir change (the engine now resolves via `paths.database_url()` to the
  OS data dir). Cosmetic only — the DB still lands in the central dir — but the printed path misleads.
  Update the string to reference the central dir (or drop the concrete path).
- **`project-context.md` MCP-tool rule ("Define tools as sync `def`") drifted from the shipped code.**
  The Framework rules state MCP tools are sync `def` threadpooled by FastMCP, but the Epic-1 tools
  (`lookup_card_by_name`, `report_bug`, `search_cards`, deck CRUD/analysis) are `async def`; only the
  two Epic-2 semantic tools (`semantic_search_cards`, `find_similar_cards`) are sync `def`. The doc
  describes the Phase-1 *design target*, not the implementation — and it's what led the docs run to
  over-generalize. Reconcile the project-context MCP-tool rule with the actual async/sync split.

## Deferred from: code review of spec-central-os-data-dir (2026-06-27)

> Surfaced by the 3-reviewer adversarial pass on the `feat/central-data-dir` work. The HIGH/MED
> findings (broken `migrate_add_bug_reports.py` import, empty-env sync/async divergence, relative
> `PLANESWALKER_DATA_DIR` not absolute) were patched in-branch; the items below are real but
> pre-existing or exotic, left for a focused later pass.

- **Bare-path `CARDS_DATABASE_URL` (no SQLAlchemy prefix) crashes the async engine** —
  `src/paths.py::database_url` returns the env value verbatim, so `CARDS_DATABASE_URL=/data/cards.db`
  (without `sqlite+aiosqlite:///`) makes `create_async_engine` raise `ArgumentError`, while the sync
  `ConnectionFactory` happily uses the bare path — a half-works/half-crashes split. Pre-existing (the
  old `os.getenv("CARDS_DATABASE_URL", default)` had the same risk) and it fails loudly. Fix later by
  validating/normalising the URL form, or document that the `sqlite+aiosqlite:///` prefix is mandatory.
  - **HOMED (not fixed) by story c1-6, 2026-07-25** — per the epic-7 gate-output-homing rule. On the
    companion's REST side the crash now has a **defined behaviour instead of an undefined one**: the
    bare path reaches `sqlalchemy.engine.make_url` inside
    `src/companion/app/deps.py::database_file`, which raises `ArgumentError`; AD-16 rules that
    deterministic, so it falls through to `UnhandledErrorMiddleware` and answers
    `500 internal_error` rather than taking the process down. Pinned by
    `test_deps.py::TestTransientFailureIsDatabaseUnavailable::
    test_a_deterministic_argument_error_is_internal_error_not_unavailable`. Note the raise site moved
    one step earlier than this item's original wording predicted (`make_url`, not
    `create_async_engine`) because the companion parses the URL to derive the file path before
    building an engine. The **underlying** half-works/half-crashes split between the async engine and
    the sync `ConnectionFactory` is untouched and still owned here; a fix belongs in `src/paths.py`,
    which story c1-6 is forbidden from editing.
- **UNC `PLANESWALKER_DATA_DIR` yields a malformed async URL** — for `\\server\share\pw`,
  `database_path().as_posix()` collapses the leading `\\` to a single `/`, so the async URL drops the
  UNC authority while the sync factory keeps the native UNC path → divergence. Exotic (SQLite over a
  network share is discouraged anyway); document "use a local absolute data dir" or reject UNC paths.
- **✅ RESOLVED by the prune (2026-06-28) — Repo-wide `ruff check .` / `ruff format --check .` now clean.**
  The pre-existing drift was in `_bmad/scripts/*` and `src/mcp_server/tools/card_lookup.py`. The prune
  untracked + gitignored `_bmad/` (ruff now skips it) and the pre-commit formatter normalized one
  f-string in `card_lookup.py`. Verified: `ruff format --check .` (120 files) + `ruff check .` both pass.

## Deferred from: code review of trim-deps-package-metadata (2026-06-28)

> Surfaced by the 3-reviewer adversarial pass on the `chore/trim-deps-package-metadata` work
> (§6 deps/metadata cleanup). No HIGH/MED findings against the change itself — every blind-hunter
> "risk-to-confirm" item (entry-point `main` exists, removed deps unreferenced anywhere, mypy hook
> still clean without `logfire`) was verified false. The one real item below is pre-existing.

- **`setup.py` creates a `.env` that nothing actually loads (orphaned onboarding artifact)** —
  `setup.py::setup_environment` writes `.env` from `.env.example`, but no code path loads it: there
  is no `load_dotenv` call and no `pydantic-settings` `BaseSettings(env_file=...)` anywhere — all
  config is read via bare `os.getenv(...)` (`src/paths.py`, `src/search/connection.py`,
  `src/search/embedder.py`, `src/mcp_server/__main__.py`), and `uv run` does not auto-load `.env`.
  So edits to the generated `.env` silently have no effect unless the user exports the vars or the
  MCP client injects them. Pre-existing (predates this chore; confirmed while verifying the
  `python-dotenv` removal). Fix later by either wiring up `.env` loading (a `BaseSettings` config
  object, or `uv run --env-file`) or trimming `setup_environment` + `.env.example` to match the
  "env vars are optional, defaults work out of the box" reality. (Source: Edge Case Hunter; Severity: Low.)

## ✅ Resolved by the Pre-Epic-3 Targeted Gate (2026-06-27)

> Cleared via `spec-pre-epic-3-targeted-gate.md` before starting Epic 3. The items below are closed;
> they remain listed in their original sections for traceability.

- **G1 — `_FakeEmbedder`/`_FakeVecEmbedder` duplication (was 5 copies).** Consolidated into one
  `tests/fixtures/embedder.py::FakeEmbedder` (union of `encode`/`encode_batch`/`total_embedded`);
  all call sites import it. (Closes the 2-4 and 2-5 "`_FakeEmbedder` in N test files" items.)
- **G2 — `limit` upper bound / `limit > over_fetch_k` starvation.** `semantic_search_cards` and
  `find_similar_cards` now reject `limit > 50` (`_MAX_LIMIT`, kept under `over_fetch_k=200`).
  (Closes the 2-4 "`limit > over_fetch_k` silently truncates" and 2-5 "silently starves" /
  "`limit` has no upper bound" items.)
- **G3 — graceful "index not built".** New `src/search/query.py::index_is_populated` gates both
  semantic tools, returning `status="index_unavailable"` (with a build-the-index hint, `isError=False`)
  for a missing **or** empty `card_vec`, instead of a raw `OperationalError`. (Closes the
  "index not built" half of the 2-4 "Unhandled exceptions propagating from sync tool" item; the
  ONNX/`RuntimeError`/`JSONDecodeError` halves remain deferred — infra concerns.)
- **Nullability audit (1-4 / 1-6).** Confirmed the `Card`/`CardSummary` `@field_validator(mode="before")`
  coercions (`None → ""`/`[]`/`{}`) already protect `mana_cost`/`oracle_text`/`colors`/`games`/`legalities`;
  added a `validate_deck` NULL-legalities/NULL-games regression test. Closes the 1-4
  "CardSummary.mana_cost/oracle_text non-nullable" + "colors no None-coercion" items and the 1-6
  "`card.legalities` potentially None" + "`card.games` potentially None" items.

## Epic-3 design candidates (from TOOL_PERFORMANCE_REPORT.md, 2026-06-27)

> Surfaced by Brad's live test of the semantic tools (R1). Not bugs — enhancement candidates to weigh
> during Epic 3.

- **Compound-intent dilution — handle in the orchestrator, not the tools.** "A **and** B" queries
  (e.g. "removal that also reanimates") rank by topical proximity, so cards matching *either* effect
  blend in and can outrank true "both" cards (`Betrayal of Flesh` ranked 14th). Treat the semantic
  tools as **high-recall candidate generators**: over-fetch, then have the Story 3.1 orchestrator /
  LLM filter for the logical intersection and present ranked candidates **with reasons** (confirms
  retro design-input I1). An optional in-tool re-rank rewarding multi-clause matches is a possible
  later refinement.
- **`find_similar_cards` cross-color leakage.** With no `colors` filter, off-color cards surface
  (`src/mcp_server/tools/find_similar.py`). Consider defaulting `colors` to the seed card's colour
  identity (overridable) to cut leakage. Tool already supports the filter; only the default is open.

## Deferred from: code review of 2-6-rag-sanity-eval (2026-06-24)

- **`evaluate_hit_rate([])` produces confusing "0 miss(es)" failure message** — `tests/integration/search/test_rag_eval.py`. If `_QUERY_FIXTURE` is ever emptied (module-level constant; only via code edit), `evaluate_hit_rate([])` returns `(0.0, [])`, which trips the `>= TARGET_HIT_RATE` assert but `format_failure` prints "0 miss(es)" with no per-miss lines — self-contradictory. Add `assert case_results, "Query fixture is empty"` before the hit-rate assert as a defensive guard in a future maintenance pass.
- **`reset_embedder()` teardown ordering hazard across modules** — `tests/integration/search/test_rag_eval.py`. Module-scoped `rag_eval_index` fixture calls `reset_embedder()` in teardown. If another module's session-scoped fixture loaded the embedder, this reset destroys the shared singleton mid-session. Pre-existing pattern in `test_embedder.py` and `test_semantic_search_tool.py`; a session-scoped coordinator would fix it project-wide.
- **Yield-fixture setup failure leaves `ConnectionFactory` unclosed** — `tests/integration/search/test_rag_eval.py:rag_eval_index`. If `get_embedder()` raises during fixture setup (model download failure, ONNX error), pytest does not run the teardown, so `factory.close()` is never called. Tmp files are cleaned by `tmp_path_factory` at session end; no functional impact. Fix with `try/finally` around setup if file-lock issues surface on Windows.

## Deferred from: code review of 2-5-find-similar-cards-tool (2026-06-22)

- **LIKE wildcard injection in `card_name`** — `src/mcp_server/tools/find_similar.py`. Characters `%` and `_` in seed card names are not escaped before the `LIKE lower(?)` partial-match fallback, silently broadening or changing the match set. Acknowledged in code comment as "accepted LIKE-wildcard risk, mirroring CardRepository (deferred-work)". Pre-existing in `card_lookup.py` and `card.py` (1-3 review).
- **`limit > over_fetch_k` silently starves results (find_similar path)** — `src/search/query.py:hybrid_search`. `find_similar_cards` never passes `over_fetch_k`, so callers requesting `limit > 200` receive fewer alternatives than requested with no warning. Also, seed cards with many printings (e.g. Lightning Bolt ~50 printings) consume KNN slots before exclusion, further reducing the effective result count. Related: noted in 2-4 review.
- **`np.frombuffer` returns read-only array in `get_card_vector`** — `src/search/query.py`. The returned `NDArray` is backed by the SQLite buffer object and is read-only; any future caller that attempts in-place mutation will get a `ValueError`. Current code path (via `hybrid_search → serialize_float32`) only reads the array. Guard with `.copy()` if mutating callers are ever added.
- **Empty/corrupted BLOB in `get_card_vector` raises ValueError** — `src/search/query.py`. If the `card_vec` BLOB is zero-length or not a multiple of 4 bytes (data corruption), `np.frombuffer` raises `ValueError` uncaught. Controlled data written by `serialize_float32` always produces 1536 bytes; treat as infrastructure concern.
- **`_FakeEmbedder` now in four test files** — Previously tracked (2-4 review). `test_find_similar_tool.py` adds a fourth copy. Consolidate to `tests/conftest.py` or `tests/fixtures/embedder.py` in a future housekeeping pass.
- **`color_mode` not runtime-validated in `find_similar_cards` helper** — `src/mcp_server/tools/find_similar.py:_validation_error`. Invalid strings reach `hybrid_search._color_predicates` unchecked. FastMCP's `Literal["any", "all", "exact", "at_most"]` annotation rejects invalid values at the wire level; direct helper calls bypass this. Mirrors Story 2.4 pattern.
- **`limit` has no upper bound in `_validation_error`** — `src/mcp_server/tools/find_similar.py`. Only `limit < 1` is rejected. `over_fetch_k=200` provides a natural cap on results. Also noted in 2-4 review.
- **`_resolve_seed` LIKE fallback fetches all matching rows without SQL LIMIT** — `src/mcp_server/tools/find_similar.py`. On 60k cards, a common substring like `"a"` loads thousands of rows into Python memory before `_MAX_MATCHES` capping. Mirrors `CardRepository.find_by_name_partial`'s unbounded fetch. Add `LIMIT _MAX_MATCHES * 20` to the SQL in a future performance pass.
- **`_decode_colors` does not guard against non-list JSON or `JSONDecodeError`** — `src/mcp_server/tools/find_similar.py:_decode_colors`. If `cards.colors` contains valid JSON but not a JSON array (e.g. a string scalar `"R"`), `json.loads` returns a non-list that bypasses the `value is not None` check and reaches `CardSummary(colors=...)` as the wrong type; malformed JSON raises `JSONDecodeError` uncaught. Same pattern as `_coerce_json_list` in `query.py`; Scryfall always writes a valid JSON array — infrastructure concern.
- **Disambiguation "showing first N" message branch is unreachable for 6–10 distinct matches** — `src/mcp_server/tools/find_similar.py:253`. `shown = distinct[:_MAX_MATCHES]` equals `distinct` when `len(distinct) ≤ 10`, so the inner `if len(shown) < len(distinct)` branch (which emits "showing the first N") is dead code for that range. For 6–10 matches, the message says "Please refine" without the count sub-clause, even though all matches are returned in `matches`. Cosmetic phrasing gap; `matches` list is correct.

## Deferred from: code review of 2-4-semantic-search-cards-tool-hybrid-query (2026-06-22)

- **Unhandled exceptions propagating from sync tool** — `src/mcp_server/server.py:440`. `OperationalError` (DB unavailable / index not built), `RuntimeError` (ONNX failure), and `json.JSONDecodeError` (malformed DB column) all propagate uncaught through the sync tool, resulting in `isError=True` FastMCP responses. Matches the existing Epic-1 async tool pattern; a `status="error"` enum extension would be needed to handle these gracefully. Defer until infra errors surface in practice.
- **`_FakeEmbedder` duplicated in three test files** — `tests/unit/search/test_query.py`, `tests/integration/mcp_server/test_semantic_search_tool.py`, and `tests/integration/conftest.py` each define an identical `_FakeEmbedder` / `_FakeVecEmbedder` class. Move to a shared `tests/integration/conftest.py` or a dedicated `tests/fixtures/embedder.py` helper to avoid triple-maintenance on `Embedder` interface changes.
- **`limit > over_fetch_k` silently truncates results** — `src/search/query.py:hybrid_search`. Callers passing `limit > 200` (default `over_fetch_k`) receive fewer results than requested with no indication. Spec says "sane max ~50"; add an upper-bound validation in `_validation_error` (e.g. `limit > 50 → status="invalid"`) in a future polish pass.

## Deferred from: code review of 1-1-repository-restructure-dependency-reshape (2026-06-20)

- **`legacy/tests/conftest.py` module-level chainlit import** — `import chainlit` at the top of `legacy/tests/conftest.py` (line 8) causes `ModuleNotFoundError` if someone runs `pytest legacy/tests/` on a lean env (without `--group legacy`). `testpaths = ["tests"]` protects the default run. Fix: add a note to `legacy/` documentation or add a root-level `conftest.py` `collect_ignore_glob` guard to make the failure message clearer.

- **`mock_user_session` fixture state leak** — `legacy/tests/conftest.py` patches `cl.user_session.get/.set` at fixture setup time with no teardown/restore. If a test using this fixture fails mid-run, subsequent tests in the same session inherit the patched session. Fix: rewrite using pytest's `monkeypatch` fixture or a `yield`-based restore. Applies to the legacy test tree only (excluded from active CI).

- **Legacy tests' `tests.fixtures.card_data` import** — Files like `legacy/tests/integration/agent/test_agent_card_search.py` import `from tests.fixtures.card_data`. This works when pytest sets the project root on `sys.path` (standard `uv run pytest` from root) but may fail in IDEs or when running `pytest legacy/tests/` in isolation. Fix: either copy shared fixtures into `legacy/tests/fixtures/` or add a `conftest.py` `sys.path` adjustment to `legacy/tests/`.

- **`PaginatedResult[T]` missing field validators** — `src/data/schemas/pagination.py` has no validators to enforce `page >= 1`, `page_size >= 1`, or `total_pages` consistency with `total_count`. A caller constructing `PaginatedResult(page=0, ...)` silently passes validation; a caller reading `page=1, total_pages=0` has an impossible state. Fix: add `Field(ge=1)` to `page`, `page_size`, `total_pages` and optionally a `model_validator` for `total_pages` consistency.

- **Task 0 out-of-scope changes** — Story 1.1 also shipped three pre-existing-defect fixes (explicitly approved by user): recreated `src/data/schemas/pagination.py`, fixed `CardModel.printed_name` default, and updated test contract assertions for `PaginatedResult`. These were correctness-restoring fixes needed to unblock AC4 (100 tests were failing at baseline). No follow-up action required; noted here for traceability.

## Deferred from: code review of 1-2-sqlite-connectionfactory-with-wal-extension-loading (2026-06-20)

- **Empty string `CARDS_DATABASE_URL` not guarded** — `_resolve_db_path` returns `""` if the env var is set to an empty string, which `sqlite3.connect("")` will fail on (OperationalError). This is an operator misconfiguration that fails loudly; not worth defensive handling given project rules against unnecessary validation. If it becomes a user-facing pain point, add a guard in `_resolve_db_path` to fall back to the default when the stripped URL is empty.

## Deferred from: code review of 1-3-fastmcp-server-with-card-lookup-bug-report (2026-06-20)

- **`updated_at` onupdate lambda silent in ORM** — `src/data/models/bug_report.py:43-47`. SQLAlchemy `mapped_column(onupdate=callable)` does not fire via the ORM unit-of-work; `updated_at` will always equal `created_at`. Matches the pre-existing `DeckModel` pattern. Only matters when a future story adds an update operation.
- **No CHECK constraint on status column** — `src/data/models/bug_report.py:32-34`. Any raw string can be written to `status` bypassing enum validation; reading it back via `BugReport.model_validate` would raise `ValueError`. Currently only triggered by manual DB manipulation. Address when an update story is implemented.
- **CardLookupResult.matches=[] on found status** — `src/mcp_server/tools/card_lookup.py`. An empty list rather than `None` for `matches` when `status="found"` is ambiguous for callers. Design preference; no functional bug.
- **LIKE wildcard injection in card_name/games** — `src/data/repositories/card.py`. Characters `%` and `_` in the card name or games list are passed un-escaped to SQLite LIKE. Pre-existing issue in `CardRepository`; out of scope for Story 1.3.
- **Non-DatabaseError exceptions skip explicit rollback in BugReportRepository** — `src/data/repositories/bug_report.py:50-69`. Exceptions that aren't `IntegrityError` or `DatabaseError` propagate without explicit `rollback()`. The session context manager handles cleanup on exit; low practical risk in current call paths.
- **migrate_add_bug_reports.py CWD-sensitive** — `scripts/migrate_add_bug_reports.py:20`. Default `DATABASE_URL` uses `./data/cards.db`; if the script is run from a non-root directory it silently targets the wrong file. Convention (run via `uv run` from project root) guards this; a doc comment would help.
- **Transport cast is runtime no-op** — `src/mcp_server/__main__.py:20`. `cast(_Transport, os.getenv(...))` provides no runtime validation. FastMCP raises on an invalid transport string anyway, but an explicit guard would give a clearer error message.

## Deferred from: code review of 1-4-advanced-card-search-tool (2026-06-20)

- **`CardSummary.mana_cost`/`oracle_text` non-nullable** — `src/data/schemas/card.py:84,87`. Both fields are `str` (not `str | None`), matching the pre-existing `Card` schema pattern. Scryfall has null mana_cost for tokens/land faces and null oracle_text for split cards. If the DB stores these as NULL, `CardSummary.model_validate(card)` will raise `ValidationError`. Needs to be addressed as part of a broader Card/CardSummary schema nullability audit; this story explicitly prohibits modifying `Card`.
- **`CardSummary.colors: list[str]` no None-coercion** — `src/data/schemas/card.py:88`. `Card.games` has `@field_validator` coercing `None → []`; `colors` has no equivalent in either `Card` or `CardSummary`. If a `CardModel.colors` is NULL in SQLite, `model_validate` raises `ValidationError`. Pre-existing in `Card`; should be addressed alongside the mana_cost/oracle_text audit.
- **`page_size > 50` silently capped with no caller notification** — `src/data/repositories/card.py`. The repository clamps `page_size = min(page_size, 50)` and reflects the effective value in `CardSearchResult.page_size`. The tool-level `_validation_error` only rejects `page_size < 1`. Consider adding an upper-bound check (return `status="invalid"` for `page_size > 50`) in a future polish pass.
- **`games` validation case-sensitive vs `rarity` case-insensitive inconsistency** — `src/mcp_server/tools/card_search.py:83-86`. `rarity` values are normalised with `.lower()` before checking; `games` are compared directly. Callers passing `"Paper"` or `"MTGO"` get `status="invalid"` with a clear message naming the expected casing. Inconsistent but not harmful; could be unified in a future polish story.
- **`page` beyond `total_pages` gives generic empty message** — `src/mcp_server/tools/card_search.py:178-189`. Requesting `page=999` on a 1-page result set returns `status="empty"` with the standard "try adjusting filters" hint, giving no indication the page number exceeded the range. A future polish pass could detect `page > result.total_pages` after the repo call and return a more specific message.
- **`colors=[]` applies no filter for non-"exact" modes** — `src/data/repositories/card.py`. `search_advanced` treats `colors=[]` (empty list) the same as `colors=None` for `any`/`all`/`at_most` modes because `if colors:` is falsy. A caller expecting "empty list = colorless only" gets "no filter" instead. Pre-existing behavior in `search_advanced`; out of scope for this story.

## Deferred from: code review of 1-5-deck-management-tools (2026-06-20)

- **`DeckSummary.from_attributes=True` footgun** — `src/data/schemas/deck.py`. `DeckSummary.model_validate(deck)` silently gives zero counts because `Deck` has no `mainboard_count` attribute. Docstring warns; helpers always use explicit constructors. Could remove `from_attributes=True` from `DeckSummary`/`DeckDetail` (only `DeckCardSummary` actually needs it) to prevent future misuse.
- **`CardSummary.model_validate(dc.card)` on a Pydantic model** — `deck_management.py:_deck_detail`. Works in Pydantic v2 via attribute inspection on `Card` instances. A more explicit pattern (`CardSummary(**dc.card.model_dump())`) is safer but out of Story 1.5 scope.
- **Non-deterministic card ordering in `_deck_detail`** — `deck_management.py`. Order of `load_deck` card list depends on `DeckRepository.get_deck_with_cards` sort; if non-deterministic, card order in responses is unstable. Address when consistent ordering is required.
- **`not_in_deck` message does not hint card exists in other location** — `deck_management.py:remove_card_from_deck`. Removing from mainboard when card is in sideboard returns "not in the mainboard" with no hint the card is present elsewhere. UX improvement for a future polish story.
- **`_deck_detail` crash risk if `dc.card` is `None`** — `deck_management.py`. FK enforcement is OFF; if a card row is deleted after a `deck_cards` row was inserted, `get_deck_with_cards` may return a `DeckCard` with a null `card`. `CardSummary.model_validate(None)` would raise. Defended by add-path pre-validation (AC4) but not structurally guaranteed.
- **No `format` validation in `create_deck`** — `deck_management.py`. Invalid format strings (e.g., `"potato"`) are stored silently; deferred to Story 1.6 `validate_deck` by D-1.5b.

## Deferred from: dev of 1-2-sqlite-connectionfactory-with-wal-extension-loading (2026-06-20)

- **`test_list_decks` flaky ordering (pre-existing)** — `tests/integration/data/test_deck_repository.py::test_list_decks` asserts three rapidly-created decks come back newest-first, but `DeckRepository.list_decks` orders by `created_at.desc()` with **no secondary tie-breaker** ([`src/data/repositories/deck.py:260`](../../src/data/repositories/deck.py#L260)). When the three `create_deck` calls land on identical `created_at` timestamps (common under full-suite timing), SQLite resolves the tie arbitrarily and the assertion fails non-deterministically. Verified: the test passes 5/5 in isolation but fails intermittently in the full run. Unrelated to Story 1.2 (which only adds `src/search`); left untouched per scope discipline. Fix: add a deterministic secondary sort key to `list_decks` (e.g. `.order_by(DeckModel.created_at.desc(), DeckModel.id)`) **and** make the test's creation-order intent explicit (e.g. distinct/controlled `created_at` values), since UUID `id` is not time-ordered.

## Deferred from: code review of 2-1-embedder-port-fastembed-singleton-persistent-cache (2026-06-21)

- **Double-checked locking portability for non-CPython/free-threaded Python** — `src/search/embedder.py:1038`. The outer `if _embedder is None` read has no lock and relies on CPython's GIL for visibility. Correct on CPython 3.12 (project target), but not portable to free-threaded builds (PEP 703, opt-in in Python 3.13+) or other implementations. Revisit if/when free-threaded Python is targeted.
- **encode_batch large-batch memory ceiling** — `src/search/embedder.py:encode_batch`. No `batch_size` passthrough; a ~60k-item call materializes all output vectors in memory (~88 MB for float32 alone) plus fastembed's internal buffers. Spec explicitly deferred `batch_size` to Story 2.3's index builder.
- **reset_embedder() dual ONNX sessions under concurrent use** — `src/search/embedder.py:reset_embedder`. If called while a thread holds a reference from `get_embedder()` and is mid-encode, the next `get_embedder()` loads a second ONNX session, doubling RAM transiently. Test-only function; production FastMCP never calls it; GC reclaims the old Embedder when callers release their reference. Docstring should note the hazard.
- **test_resolve_cache_dir_never_temp assertion style** — `tests/unit/search/test_embedder.py:1197`. `startswith("./data")` check is correct for the current relative default. If the P1 absolute-path patch is ever applied, this test will need updating to match the resolved absolute path.
- **README.md and setup.py changes bundled in story commit** — Not in the spec File List; spec's Git Intelligence note acknowledges these as pre-existing MCP-pivot cleanup. Noted for traceability.

## Deferred from: code review of 2-2-card-vec-schema-with-metadata-columns (2026-06-21)

- **Tests call `factory.close()` without try/finally** — `tests/unit/search/test_schema.py`. Every test leaves `factory.close()` outside a `try/finally`, so connections are not released on assertion failure. On Windows, leaked WAL connections can cause file-lock errors. Pre-existing pattern mirrored from `test_connection.py`; fix the pattern project-wide when refactoring the test helpers.
- **Migration CWD-relative DB path** — `scripts/migrate_add_card_vec.py`. Default `./data/cards.db` is CWD-relative; running from a non-root directory silently targets the wrong file. Pre-existing `ConnectionFactory` behavior; convention is `uv run` from project root. Same issue exists in `migrate_add_bug_reports.py`.
- **`mana_value integer` column accepts Python float inputs without coercion** — `src/search/schema.py`. SQLite's dynamic typing allows storing a Python `float` in an `integer`-affinity column without error, so `WHERE mana_value = 2` could silently miss cards stored as `2.0`. The `int(cmc)` cast is Story 2.3's responsibility at insert time.

## Deferred from: code review of 1-6-deck-analysis-tools (2026-06-20)

- **`dc.quantity` zero or negative can undercount mainboard cards** — `validate_deck` in `src/logic/deck_validator.py` accumulates `dc.quantity` without clamping. A zero or negative quantity (bypassing the DeckCard schema validator) would undercount the mainboard, potentially letting an illegal deck pass the 60-card check. Fix at insert time in `DeckRepository.add_card_to_deck` with `quantity >= 1` enforcement.
- **`card.legalities` potentially `None` from DB NULL** — `card.legalities.get(format)` in `validate_deck` (`src/logic/deck_validator.py`) raises `AttributeError` if `legalities` is `None`. The `Card` schema types this as `dict[str, str]` (non-nullable), but SQLite does not enforce NOT NULL for JSON columns without a CHECK constraint. Address in a broader Card schema nullability audit (related: deferred in 1-4 review).
- **`card.games` potentially `None` from DB NULL** — `set(card.games)` in `validate_deck` raises `TypeError` if `card.games` is `None`. Same root cause as `legalities`; `Card.games` has a `@field_validator` coercing `None → []` for ORM-loaded instances but not for in-memory `Card` objects constructed directly. Confirm the validator fires for all construction paths.
- **Unexpected exceptions from logic functions propagate unhandled** — `_logic_analyze_mana_curve`, `_logic_detect_synergies`, and `_logic_validate_deck` in `src/mcp_server/tools/deck_analysis.py` are called with only `DatabaseError` caught around the repo load. If any logic function raises an unexpected exception (e.g., a malformed `cmc` field in `analyze_mana_curve`), it propagates to the MCP caller as an unstructured error. Accepted risk for Phase-1; revisit if unexpected failures surface in practice.
- **Quantity expansion OOM for adversarial large `dc.quantity`** — `analyze_mana_curve` in `deck_analysis.py` expands `dc.card` by `range(dc.quantity)` into `all_cards`. A corrupted/adversarial record with `quantity=1_000_000` would allocate a million-element list. Cap at the repository level (or add a defensive `min(dc.quantity, 250)` expansion cap) when productionising.
- **`format` normalization absent from pure `validate_deck` logic** — The tool helper normalises `format.strip() or "standard"`, but the pure function in `src/logic/deck_validator.py` accepts any string, including `""`. Direct callers (e.g., future logic-layer callers) passing an empty format will get all cards flagged as format-illegally. Consider adding the normalization to the pure function as a defensive guard.
- **`seeded_card_db` omits `games` field on seed cards** — The three shared fixture cards (Lightning Bolt, Thunderbolt, Counterspell) default to `games=[]`. The `games` filter path in `validate_deck` is therefore not exercised end-to-end through the MCP harness (`test_mcp_tools.py`). Covered at the helper level in `test_deck_analysis_tool.py`. Acceptable Phase-1 gap; extend the harness test when the fixture is enriched for Epic-2 work.

## Deferred from: code review of story-3.4 (2026-06-27)

- **`validate_deck` skips `dc.card is None` rows from copy/legality checks while still counting them in `mainboard_count`** — `src/logic/deck_validator.py` does `if dc.card is None: continue` before tallying copies/legality, but `mainboard_count` sums quantity unconditionally. A saved deck with an orphaned card join (a `card_id` no longer in the DB) passes copy/legality vacuously while still counting toward the 60-card size — a "legal" result can hide un-validated phantom cards. Pre-existing tool/data edge; obscure. Could add a one-line caveat to the format-legality skill's "what the tool can't see" section. (Source: Edge Case Hunter; Severity: Low.)

## Deferred from: code review of mcpb-bundle (2026-06-28)

> Surfaced by the 3-reviewer adversarial pass on the `chore/mcpb-bundle` work (§4 MCPB bundle).
> The one HIGH that mattered (`.mcpbignore`'s unanchored `data/` also excluding `src/data/`, which
> would have shipped a server unable to import its own data layer) was caught by re-verification and
> patched in-branch by anchoring the rule to `/data/`. Most blind-hunter findings were verified false
> (`server.type: "uv"` IS valid in the MCPB v0.4 schema; blank `data_dir` is handled by
> `paths.py`'s `(getenv() or "").strip()` fallback; `uv run` honours `requires-python`). The two
> real items below are pre-existing or out-of-this-run's-scope-by-design.

- **MCPB bundle has no first-run data bootstrap or guidance.** A freshly-installed `.mcpb` launches
  the server, but the shared OS data dir has no `cards.db` yet — the ~250 MB data set is excluded from
  the bundle **by design** (§3/§4; spec "Never: no DB shipped"). The server never calls
  `init_database`, so the first relational tool call fails (`no such table: cards`); the two semantic
  tools degrade gracefully to `status="index_unavailable"`. Net end-user experience: "every deck/card
  tool errors with no guidance." Out of scope here (the bundle correctly ships data-excluded), but a
  real UX gap. Follow-up: either add a first-run auto-init / friendly "run the one-time data build"
  response, or document the manual bootstrap (`uv run python setup.py`, then
  `scripts/build_card_embeddings.py` — both write to the shared OS data dir the bundle reads) in the
  install docs. (Source: Edge Case Hunter; Severity: High-for-UX.)
- **`README.md:68` overclaims the Claude-Desktop first-run behavior.** The "Claude Desktop
  (one-click)" section says *"(First launch prompts you to run the one-time data build.)"* — but the
  shipped `manifest.json` has no prompt/hook to do that (coupled to the bootstrap-gap item above).
  Out of this run's frozen scope (no README edits). Fix in the focused README-accuracy pass already
  tracked (the `setup.py`-builds-the-index claim) — either implement the prompt or reword to a manual
  build step. (Source: Edge Case Hunter; Severity: Med.)
- **MCPB GUI data-dir override removed (smoke-test fix 2026-06-28).** The optional
  `user_config.data_dir` field was dropped from `manifest.json` because Claude Desktop passes the
  **unsubstituted `${user_config.data_dir}` placeholder** when the optional field is left blank,
  repointing the server at a bogus relative dir → empty DB → `no such table: decks`. The bundle now
  always uses the shared central OS dir (zero-config). If the GUI override is ever re-added, also
  harden `src/paths.py::data_dir` to ignore an override that still contains an unsubstituted `${...}`
  placeholder (defense-in-depth), with a unit test — otherwise the bug returns. (Source: Brad live
  smoke-test; Severity: was High, now fixed.)

## Deferred from: code review of story-4.2 (2026-07-12)

> 3-reviewer adversarial pass on the `scripts/migrate_add_game_changer.py` diff (Story 4.2). The
> Blind Hunter's headline finding — the documented backfill re-import can't actually populate
> `game_changer` because `src/data/importers/importer.py` never lists the column — is a
> decision-needed item logged in the story file's Review Findings, not deferred here (it blocks
> the story's own AC5/AC6, so it isn't "not actionable now"). The items below are real but
> pre-existing/inherited-template gaps out of this story's scope.

- **Pre-`try` engine/session-factory failures + rollback()/dispose() masking secondary exceptions** — `scripts/migrate_add_game_changer.py:42-46,67-72`. `create_engine()`/`create_session_factory()` calls sit outside the `try` block, and neither `session.rollback()` in `except` nor `engine.dispose()` in `finally` is itself guarded — a secondary exception there would mask the original error or an unhandled traceback if session-factory setup fails. Verbatim structure copied from `scripts/migrate_add_power_toughness.py` per this story's own template mandate; not introduced by this diff. (Source: Edge Case Hunter; Severity: Low.)
- **TOCTOU race between the idempotency check and the `ALTER TABLE`** — `scripts/migrate_add_game_changer.py:50-57`. Two concurrent runs can both pass the `PRAGMA table_info` check before either commits, so the loser hits a raw "duplicate column name" `OperationalError` dressed up as a generic migration failure instead of a benign no-op. Identical race exists in the precedent script. (Source: Edge Case Hunter; Severity: Low.)
- **`PRAGMA table_info(cards)` on a missing `cards` table silently returns empty rather than erroring** — `scripts/migrate_add_game_changer.py:47-55`. A pre-bootstrap DB (never run through `initialize_database`) makes the script proceed straight to `ALTER TABLE` on a nonexistent table, surfacing a raw "no such table: cards" error with no bootstrap hint. Same gap in `migrate_add_power_toughness.py`; same class as the previously-resolved G3 `index_unavailable` bootstrap gap, but this migration template was never given the equivalent fix. (Source: Blind Hunter + Edge Case Hunter; Severity: Low.)
- **Upsert-based backfill only touches rows present in the current Scryfall bulk export** — `src/data/importers/importer.py`. A card absent from a freshly-downloaded bulk file keeps its prior (NULL) `game_changer` value indefinitely; the migration docstring's "overwrites every card" framing overstates actual coverage. Inherent to the importer's existing upsert design, not introduced by this diff. (Source: Blind Hunter; Severity: Low.)
- **Idempotency guard checks column presence only, not type/nullability** — `scripts/migrate_add_game_changer.py:50-53`. A differently-typed partial/failed prior migration attempt would be silently treated as already-satisfied. Identical guard shape in the precedent script. (Source: Blind Hunter; Severity: Low.)

## Deferred from: code review of story-4.1 (2026-07-11)

- **Untyped `game_changer` value could reach the `Boolean` column unchecked** — `src/data/importers/transformers.py:79`. `card_json.get("game_changer")` performs no type/shape validation; a non-bool value (string/int) would flow straight into a `Boolean` SQLAlchemy column with no coercion or error. Pre-existing pattern: no field in `transform_scryfall_card` has type validation beyond null-coalescing, and Scryfall is a trusted, documented source for this field. (Source: Edge Case Hunter + Blind Hunter; Severity: Low.)
- **No cross-printing `game_changer` reconciliation in oracle aggregation** — `src/data/importers/aggregate.py`. Unlike `games` (unioned across all printings of an oracle identity), `game_changer` is taken from whichever printing happens to be canonical, with no explicit cross-printing reconciliation. Mirrors the identical, deliberate gap already present for `power`/`toughness`; out of this story's scope per its own Dev Notes (extraction only, not aggregation semantics). (Source: Edge Case Hunter; Severity: Low.)
- **`tests/fixtures/scryfall_sample.json` not updated with a realistic `game_changer` key** — the three new unit tests use a hand-built minimal `card_json` dict rather than the shared Scryfall fixture, so a real-world schema drift in the live field (e.g. Scryfall renaming/nesting it) wouldn't be caught. Story Dev Notes explicitly scope this story to synthetic-input unit tests only ("no live Scryfall data or re-import is required"). (Source: Blind Hunter; Severity: Low.)
- **No DB round-trip test for `game_changer`** — only the in-memory `CardModel` object returned by `transform_scryfall_card` is asserted; nothing proves `False` survives an actual SQLite INSERT/SELECT rather than being coerced to `NULL` on the real dialect. Identical gap already exists for the `power`/`toughness` precedent — no such round-trip test exists anywhere in the suite today. Somewhat more load-bearing here than a typical gap, since defending against exactly this `None`/`False` conflation is this field's whole purpose. (Source: Blind Hunter; Severity: Medium, but pre-existing pattern.)
- **No Pydantic schema-layer test for `game_changer`** — nothing constructs/validates a `Card` (via `model_validate`/`model_dump`) with `game_changer=False` to prove the "no coercion validator" claim rather than merely asserting it in a comment. Identical gap already exists for `power`/`toughness` in `tests/unit/data/test_schemas.py`. (Source: Blind Hunter; Severity: Low.)
- **Sprint-status prose doesn't note the feature isn't usable end-to-end until Story 4.2's migration ships** — `epic-4` flips to `in-progress` and `4-1` to `done` while `4-2-migrate-and-backfill-existing-databases` stays `backlog`; a reader of `sprint-status.yaml` alone can't tell "done" here means "additive schema only, unusable on existing DBs until 4.2 ships." Already documented clearly in this story's own Dev Notes ("What this story is (and is NOT)"). (Source: Blind Hunter; Severity: Low.)

## Deferred from: code review of story-5.1 (2026-07-12)

> 3-reviewer adversarial pass on Story 5.1's calibration benchmark set (`tests/fixtures/benchmark_decks.py` + 7 decklist fixtures + offline self-validation test). The headline finding — a rules-illegal duplicate "Kinnan, Bonder Prodigy" card in `cedh_kinnan_bonder_prodigy.txt`, rooted in the Dev Agent's admitted departure from AC3/Task 2's "copy verbatim from source" mandate — is a decision-needed item logged in the story file's Review Findings, not deferred here (it's a defect in the acceptance-gate data itself, not a pre-existing/out-of-scope gap). The items below are real but low-severity hardening gaps, not blocking.

- **Parser silently drops cards under an unrecognized/misspelled section header** — `tests/fixtures/benchmark_decks.py:120-147`. A future manifest refresh with a typo'd header (e.g. "Deck:" or "Side Board") would silently lose every card line under it with no diagnostic, undermining the "actionable failures" intent behind AC7. No occurrence in the current 7 entries. (Source: Edge Case Hunter; Severity: Low.)
- **Missing/unreadable `decklist_file` raises an unlabeled `FileNotFoundError`** — `tests/fixtures/benchmark_decks.py:174-182`. `load_benchmark()` doesn't wrap the read with the offending entry's `key` in the error message. No current occurrence. (Source: Edge Case Hunter; Severity: Low.)
- **Parser accepts a zero-quantity card line with no guard** — `tests/fixtures/benchmark_decks.py:149-158`. `BenchmarkCard.quantity`'s docstring claims `>= 1` but nothing enforces it; a `0 Foo (SET) 1` line would parse as a phantom zero-quantity card. No current occurrence. (Source: Edge Case Hunter; Severity: Low.)
- **No guard against split-quantity duplicate non-commander cards** — `tests/fixtures/benchmark_decks.py:149-158`. Generalizes the Kinnan bug class beyond commanders; `_mainboard_total` sums by line, not by distinct name, so the same card split across two lines would inflate the total silently. No current occurrence outside Kinnan; would be caught by the same duplicate-name-check patch tracked in the story file, once implemented. (Source: Blind Hunter; Severity: Low.)

## Deferred from: code review of story-5.2 (2026-07-12)

- **No construction-time (`__post_init__`) validation for weight-sum / win-turn-band ordering / rubric domain / non-empty version invariants** — `src/logic/assessment/profiles.py:43,69` (`DimensionWeights`, `FormatProfile`). AC3 permits (doesn't require) `__post_init__` validation on the frozen dataclasses; the two hardcoded module constants are already exhaustively covered by `tests/unit/logic/test_assessment_profiles.py`, so this is only a gap for hypothetical future dynamic construction (e.g., an Epic 7 `PROFILES` lookup or a 5.9 tuning script constructing profiles outside this module). Revisit if/when `FormatProfile`/`DimensionWeights` are ever constructed anywhere else. (Source: Blind Hunter + Edge Case Hunter, independently; Severity: Low.)

## Deferred from: code review of story-5.3 (2026-07-12)

> 3-reviewer adversarial pass on Story 5.3's shared oracle-text classifiers
> (`src/logic/assessment/classifiers.py`). No decision-needed items — AC5/AC6 explicitly state
> pattern-list content is provisional v1 vocabulary owned by Story 5.9's benchmark pass ("tests
> pin canonical-card behavior, not pattern contents"), which pre-answers most of what the review
> layers surfaced. The real, unambiguous code/doc gaps are logged as `[Review][Patch]` items in
> the story file instead. The two items below are real but have no current consumer to be harmed
> by them yet.

- **`_detect_hard_trigger`-based functions (`detect_mass_land_denial`, `detect_extra_turn_cards`) each call `classify_deck` independently, with no memoization** — `src/logic/assessment/classifiers.py:364-396`. Checking both FR12 hard triggers back-to-back reclassifies every card in the deck twice (full 9-category classification each time). No current caller does this — Story 5.7 (Bracket floor) is the first consumer and hasn't been built yet. Revisit there: call `classify_deck` once and read both buckets, or cache within a request scope. (Source: Blind Hunter; Severity: Low.)
- **`classify_card`'s `frozenset[str]` return has no deterministic ordering**, unlike the sorted-tuple discipline (`CategoryCount.card_names`, `HardTriggerFlag.card_names`) used everywhere else in the module for its stated AD-8-spirit determinism goal — `src/logic/assessment/classifiers.py:252-304`. Only matters if a future caller serializes per-card output directly instead of routing through `classify_deck` (which does sort). No such direct consumer exists yet. (Source: Blind Hunter; Severity: Low.)

Also surfaced but explicitly out of scope per AC5/AC6 (pattern-content tuning is Story 5.9's job,
not logged as action items — candidate regression fixtures for that story's benchmark pass):
Isochron Scepter's copy-effect text doesn't match any `WINCON_COMBO_PIECE` pattern despite being
the module's own implied canonical combo example; MDFC spell-face tutors get excluded from
`TUTOR` via the joined `type_line`'s land check when the back face is a land (e.g. a
to-hand/top-of-library tutor printed on a modal DFC); single-target "target player loses the
game" wincons (Door to Nothingness) don't match `_WINCON_EXPLICIT_RES`; untap-enabler wordings
like "untap it" / "untap enchanted creature" (Freed from the Real) don't match
`_COMBO_PIECE_RES`; plural/numeric extra-turn phrasing (Alrund's Epiphany's "takes two extra
turns") doesn't match `_EXTRA_TURN_RE`; `_HAYMAKER_RE` has no pump-magnitude threshold (any
"creatures you control get +1/+1"-style anthem matches identically to Craterhoof Behemoth);
graveyard-hate cards (Tormod's Crypt) get the generic `INTERACTION` tag via the mass-wipe
`(?:destroy|exile) (?:all|each)` branch. (Sources: Blind Hunter + Edge Case Hunter, batched;
Severity: n/a — explicitly deferred by the story's own ACs.)

## Deferred from: code review of story-5.5 (2026-07-13)

> 3-reviewer adversarial pass on Story 5.5's consistency/interaction/structural-coverage
> signals (`src/logic/assessment/consistency.py`). No decision-needed items. The Edge Case
> Hunter's one formal finding (`structural_gaps[formula]` unguarded `KeyError`) was dismissed
> on triage, not deferred — it matches the exact accepted precedent already shipped in
> `mana_base.py`'s `karsten_land_delta`/`compute_pip_signals` (mypy's `Literal` enforces the
> contract at call sites, same as every sibling function in the module).

- **`classify_card` (Story 5.3) doesn't exclude land-typed cards from the
  `INTERACTION`/`CARD_DRAW`/`WINCON_*` tags** (only from `RAMP`/`TUTOR`) —
  `src/logic/assessment/consistency.py:259`. A land whose oracle text matches an interaction
  pattern (e.g. a "destroy target artifact" land) is silently folded into
  `interaction_signals`'s count and CMC-0 bucket. Pre-existing Story 5.3 classifier behavior,
  not caused by this change — revisit if a downstream consumer (5.7/5.8) needs a
  nonland-only interaction read. (Source: Blind Hunter; Severity: Low.)
- **`STRUCTURAL_GAP_BASELINES` is `dict[KarstenFormula, dict[str, int]]`** — the outer
  `KarstenFormula` key is Literal-checked (the 5.4 review lesson), but the inner category
  keys (`CARD_DRAW`/`INTERACTION`/`RAMP`) remain plain `str`, so a future typo'd/missing key
  is a runtime `KeyError` inside `structural_gaps`, not a mypy error —
  `src/logic/assessment/consistency.py:310`. Root cause is `classifiers.py`'s untyped
  category constants from Story 5.3; fixing it properly means Literal-typing those constants
  upstream, out of this story's scope. (Source: Blind Hunter; Severity: Low.)
- **`probability_at_least` has no property/invariant test** asserting output always stays in
  `[0.0, 1.0]` for arbitrary valid inputs — `src/logic/assessment/consistency.py:59`. It's the
  shared primitive every other function in the module (and future 5.6/5.7 combo-probability
  call sites) delegates to; only pinned exact-value/edge-case tests exist today. Optional
  hardening beyond AC8's required test matrix — revisit if a future refactor touches the
  summation/clamp logic. (Source: Blind Hunter; Severity: Low.)

## Deferred from: code review of story-6-1 (2026-07-16)

> Story 6.1 is the schema/migration/write-path slice of commander identity. Its Dev Notes
> explicitly scope **all commander validation/inference to Epic 7 / Story 7.1** ("Do not add
> inference logic anywhere"). These two items are the validation surface that slice will need.

- **No commander-identity validation anywhere on the write paths** — the deck can hold any number
  of `commander=True` rows (the "two flagged rows = partners" invariant is unguarded and could be
  exceeded via repeated `add_card_to_deck(commander=True)` or a `merge_decks` that stacks
  source-flagged cards onto an already-two-commander target); a card can be flagged
  `commander=True` **and** `sideboard=True` simultaneously (a semantically impossible mainboard-only
  concept — no cross-field guard in `DeckRepository.add_card_to_deck` `src/data/repositories/deck.py:294`
  or the tool helper `src/mcp_server/tools/deck_management.py:408`); and `merge_decks`' exists-branch
  keeps the target's flag, so merging a commander source deck whose commander is already an unflagged
  card in the target silently yields a "commander deck" with zero flagged commanders
  (`src/data/repositories/deck.py:648`). All spec-accepted for this slice; Epic 7's edge-resolution
  should add the count cap, the mainboard-only guard, and a zero/over-count warning.
  (Source: Blind Hunter + Edge Case Hunter; Severity: Medium; deferred to Epic 7 / Story 7.1.)
- **No API path to change an existing row's commander flag** — once a card is in the mainboard,
  `add_card_to_deck` returns `status="exists"` (via `IntegrityError`) and never updates the flag;
  `update_card_quantity` and the Arena `import_decklist` "exists" path likewise never touch it. So
  promoting/demoting a commander requires remove-then-re-add. Fine for this slice (matches the
  established additive-import contract), but Epic 7 (or a deck-edit story) will need an explicit
  set-commander path. (Source: Blind Hunter; Severity: Low; deferred.)

## Deferred from: code review of 7-2-combo-provisioning-the-degradation-ladder (2026-07-17)

- **Transient `OperationalError` during combo provisioning is reported as
  `combo_data_unavailable`** — `ComboSnapshotRepository`'s three read methods catch
  `OperationalError` broadly and return "absent" (`src/data/repositories/combo_snapshot.py:59,72,124`),
  so a momentary "database is locked" / "disk I/O error" is indistinguishable from a genuinely
  missing snapshot: a healthy snapshot gets mislabeled unavailable and confidence is lowered.
  Graceful (never crashes) and rooted in the Story 6.3 repo contract, not Story 7.2's diff.
  Fix would narrow the repo's `except OperationalError` to the missing-table case (edits
  `src/data`, out of 7.2 scope). (Source: Blind Hunter; Severity: Low; deferred — data-layer.)
- **Deck power summary counts `almost_included` variants as "combo variants matched"** —
  `combos_matched = len(scored.core.combos)` (`src/mcp_server/tools/assess_deck_power.py:524`)
  includes both the `included` (shortfall 0) and `almost_included` (shortfall 1) buckets, so a
  deck one card short of a single combo reads "1 combo variant matched", implying a live combo.
  AC 6 only requires a "combos matched count" and the 7.2 summary is explicitly provisional;
  Story 7.3 (human-summary serialization) should disambiguate assembled vs one-away in the
  client-facing projection. (Source: Blind Hunter; Severity: Low; deferred to Story 7.3.)

## Deferred from: code review of c1-2-side-effect-free-asgi-app-with-a-lifespan-and-a-health-endpoint (2026-07-25)

- **`lifespan_client` seam is not parameterizable for its named inheritors** — the conftest helper
  hardcodes `BASE_URL = "http://testserver"` and accepts no headers/base-url kwargs
  (`tests/unit/companion/conftest.py:26-43`), but c1-5's Host-validation/CORS/token tests must vary
  exactly those. Extending the signature with optional kwargs is backward-compatible, so the
  extension belongs to c1-5 when the need is concrete rather than speculative here.
  (Source: Blind Hunter; Severity: Low; deferred to c1-5.)
  **CLOSED 2026-07-25 by c1-5 (AC 11).** `_lifespan_client` now takes `base_url=`, `headers=` and
  `bound_port=` kwargs and stamps `app.state.bound_port` when the app has none, deriving a matching
  loopback `base_url` from it. The acceptance signal was that all 149 pre-existing companion tests
  pass **unedited** — which also means the whole suite now flows through the real `Host` envelope
  rather than around it.
- **mypy pre-commit hook `additional_dependencies` drift from `uv.lock`** — the hook's isolated env
  resolves `fastapi>=0.139.2` (and the pre-existing pydantic/sqlalchemy entries) independently at
  hook-install time (`.pre-commit-config.yaml:9`), so pre-commit mypy may check a different FastAPI
  than the locked 0.140.0 CI/runtime uses. Pre-existing pattern extended, not introduced, by c1-2.
  (Source: Blind Hunter; Severity: Low; deferred — pre-existing tooling pattern.)
  *Update 2026-07-25: re-flagged by the c1-3 review (dismissed as this known item) and by Greptile
  as the sole P2 on PR #11 (`uvicorn>=0.51.0`, same pattern). Brad's ruling: merge as-is, leave
  deferred — the hook is a fast local smoke; CI's `uv sync --locked` + `mypy src/` is the
  authoritative typed gate against the real locked versions. Pinning one dep would be inconsistent
  with the other seven floors; pinning all seven would go stale against `uv.lock` unchecked.*

## Deferred from: code review of c1-3-port-selection-with-ephemeral-fallback-and-a-printed-launch-url (2026-07-25)

- **No `SO_EXCLUSIVEADDRUSE` on the Windows bind** — `_new_socket` correctly omits `SO_REUSEADDR`
  on Windows (`src/companion/app/server.py:109-124`), but does not set `SO_EXCLUSIVEADDRUSE`, so
  another local process binding with `SO_REUSEADDR` can still bind over the companion's held port —
  weakening AD-4's single-instance premise at the socket layer. c1-3's ruling was "mirror asyncio's
  own reuse policy", and c1-8's instance_id probe detects a wrong server downstream; deciding
  whether the socket itself should be hardened belongs to c1-5's security envelope.
  (Source: Edge Case Hunter + Blind Hunter; Severity: Low; deferred to c1-5.)
  **CLOSED 2026-07-25 by c1-5 (AC 10).** `_new_socket()` now sets `SO_EXCLUSIVEADDRUSE` on Windows,
  as the complement of (not a replacement for) the POSIX-only `SO_REUSEADDR`, pinned by
  `test_exclusiveaddruse_is_set_on_windows_only`. The platform branch is written against
  `sys.platform == "win32"` rather than `os.name == "nt"`: the two are runtime-identical here, but
  only `sys.platform` is narrowed by mypy, and CI type-checks on ubuntu where typeshed has no such
  constant (verified: the `os.name` form fails `mypy src/ --platform linux` with
  `Module has no attribute "SO_EXCLUSIVEADDRUSE"`).
- **`free_port()` bind-close-reuse TOCTOU in the c1-3 test helper** — between releasing the probe
  socket and the test re-binding the returned port (`tests/unit/companion/test_server.py:52-65`),
  another process can take it; latent flake class for the four tests asserting on `wanted`. The
  suite runs without xdist and the window is tiny — recorded so a future flake on these tests is
  instantly diagnosable (fix = retry loop in `free_port`). (Source: Edge Case Hunter + Blind
  Hunter; Severity: Low; deferred — act on first flake.)

## Deferred from: code review of c1-4-typed-rest-error-contract-with-closed-reason-tokens (2026-07-25)

- **Outermost error middleware vs c1-5's CORS: unhandled-503s will carry no CORS headers** — c1-4
  pins `UnhandledErrorMiddleware` outermost (`src/companion/app/main.py`, install-last comment) so
  it can type the failures of every inner middleware, and directs c1-5 to insert *inside* it. The
  flip side: a 503 minted by the error middleware never passes back through an inner
  `CORSMiddleware`, so a cross-origin caller sees an opaque network error for exactly the failure
  class c1-4 exists to type. c1-5 must weigh the ordering trade (typed failures of the security
  middleware vs CORS-visible unhandled errors) with its actual CORS scope in hand — the tension is
  recorded here so it is inherited explicitly, not discovered. (Source: Blind Hunter; Severity:
  Low; deferred to c1-5.)
  **CLOSED 2026-07-25 by c1-5 (AC 9, Decide-once #3) — resolved by the no-CORS ruling, not by an
  ordering change.** c1-5 installs no `CORSMiddleware` at all: AD-13 serves the SPA from this same
  backend, so every legitimate request is same-origin and the empty grant *is* "restricted to the
  app's own origin". With no inner CORS middleware there is no trade left to make — the
  "outer-503 never passes back through inner CORS" tension cannot arise. Pinned by three
  assertions in `test_security.py::TestCorsIsDeliberatelyAbsent`, so a later story that wants CORS
  must revisit this ruling first.

## Deferred from: story c1-5-localhost-only-security-envelope-host-validation-and-cors (2026-07-25)

- **`test_list_decks_with_strategy_field` is order-flaky on a same-tick tie** — observed failing
  once in a full-suite run during c1-5 and passing in isolation and on two subsequent full runs;
  **pre-existing and unrelated to c1-5**, which touches nothing under `src/data`. The test creates
  three decks back-to-back and asserts a strict newest-first ordering
  (`tests/integration/data/test_deck_repository.py:320-333`), but `list_decks` orders by
  `DeckModel.created_at.desc(), DeckModel.id` (`src/data/repositories/deck.py:262`) — so when two
  `created_at` values land in the same clock tick the tie-breaker is a **random UUID**, which does
  not correlate with insertion order. Fix = tie-break on something monotonic, or have the test
  space its creations. Recorded rather than fixed because it is outside c1-5's AC 16 scope
  boundary. (Source: c1-5 full-suite gate run; Severity: Low; needs a home in the data-layer work —
  natural fit is `data-layer-orphan-handling`, the other open `src/data` item.)

## Deferred from: code review of c1-6-lazy-database-engine-so-a-fresh-install-starts-instead-of-erroring (2026-07-25)

- **Cached-engine path never re-runs the existence check** — once an engine is cached, deleting
  `cards.db` while the companion runs means the next request's connection re-plants a zero-byte
  file (the response is still a correct `503 database_not_initialized`, via the empty-file probe).
  Includes the narrower exists→connect TOCTOU window on first creation. AC 3's no-plant guarantee
  is scoped to before-first-engine by design; a per-request re-stat would restore it at all times
  but is machinery with no failing user story behind it. Natural revisit point is c10-3 (latency
  work touches the same per-request path). (Source: Edge Case Hunter; Severity: Low.)
- **A durably corrupt `cards.db` is classified transient forever** — "file is not a database"
  answers `database_unavailable`, the quiet-retry "Database updating" state, on every request with
  no path to the fresh-install/repair panel. Decide-once #4 rules it transient because it might be
  mid-import, but nothing distinguishes 200 ms of mid-import from a month of garbage. A UX ruling
  for c2-9 to make with the state designs in hand. (Source: Blind Hunter; Severity: Low.)
- **URI-form SQLite `CARDS_DATABASE_URL` is misclassified as a file path** — `database_file` handles
  `:memory:` and empty-database, but `sqlite+aiosqlite:///file::memory:?cache=shared` (or
  `?uri=true` forms) falls through to `Path(parsed.database)`, which never exists → permanent 503
  for a valid in-memory URL. Same family and same channel as the bare-path item above (line ~268):
  an exotic explicit env override, not a supported configuration. Fold into that item's eventual
  fix (early validation of `CARDS_DATABASE_URL` shapes). (Source: Edge Case Hunter + Blind Hunter;
  Severity: Low.)
- **`UnhandledErrorMiddleware`'s full-traceback logging can carry `[SQL]`/`[parameters]`** — a
  SQLAlchemy `StatementError` that is not a `DatabaseError` (e.g. a wrapped `InterfaceError`)
  falls through to the 500 path, whose `logger.exception` prints the full traceback including the
  statement and bound parameters — the exact strings AC 9 scrubs on the 503 path. Pre-existing
  c1-4 middleware behavior (deliberate: full tracebacks on unhandled bugs), surfaced now that DB
  paths can route through it. Candidate: scrub `[parameters: ...]` from tracebacks, or accept as
  local-log-only. (Source: Blind Hunter; Severity: Low.)

## Deferred from: story c1-7-discovery-file-as-the-sole-rendezvous (2026-07-26)

- **`os.replace` fails with `PermissionError [WinError 5]` while another process holds the target
  open** — measured on this machine during story writing and re-confirmed in implementation. The
  window is microseconds (a reader does one `read_bytes()` and closes), and the write happens once
  per process start, so no retry machinery was added. The consequence to inherit: under c1-7's
  Decide-once #3 a publish failure **aborts the launch**, so a companion started at the exact
  instant an agent tool was reading the file could fail to start with a permissions error that has
  nothing to do with permissions. No failing user story stands behind it today — startup contends
  with an existing file for the first time in **c1-8**, whose entire subject is a second launch
  meeting a file it did not write, which is why that story is the natural home. Candidate fix if it
  ever bites: a bounded retry (2–3 attempts, short sleep) around the `os.replace` alone, or
  narrowing Decide-once #3 so a *transient* replace failure degrades where an unwritable directory
  still aborts. Windows-only. (Source: c1-7 story-writing probe 3, re-verified at implementation;
  Severity: Low; deferred to c1-8.)

  **Ruling (c1-8, 2026-07-26): still accepted, re-homed to c6-1.** c1-8 did not make this more
  likely, and it is worth being precise about why. The startup check reads `companion.json` through
  `read_discovery` — once before the probe is dialled, and (on the reclaim path only) once more in
  `_note_reclaimed_entry` to decide whether the INFO line has anything to say; each read is a single
  `read_bytes()` whose handle closes immediately — and it does so in a launch that either *returns
  without publishing* (a live instance was found) or publishes much later, from the lifespan, long
  after both handles are gone. **A process
  therefore cannot collide with itself**, which was the one new self-inflicted way this could have
  started firing. The only concurrent reader of the file in production still arrives with **c6-1**,
  whose client reads the rendezvous before every push — that is the first code that will hold the
  file open at an arbitrary moment while some other process starts. Re-homed there; nothing to do
  in c1-8.

- **TOCTOU in `remove_discovery`'s ownership guard** — the read → compare-`instance_id` → `unlink`
  sequence in `src/companion/discovery.py::remove_discovery` is check-then-act: a second instance
  that `os.replace`s its own record in between our read and our unlink loses its live rendezvous to
  our deletion — the exact scenario the guard exists to prevent, in a microsecond window on a path
  that runs once per process lifetime. No code fix wanted now: an atomic verify-and-delete has no
  clean cross-platform shape (Windows cannot unlink-by-open-handle portably from Python), and until
  c1-8 lands there is never a second live instance to collide with. Acknowledged in the function's
  docstring. Candidate fixes if it ever bites: open-with-`O_RDWR`-verify-then-unlink on POSIX with a
  documented Windows residual, or serializing shutdown/startup around a lock file. (Source: c1-7
  code review 2026-07-26, Blind Hunter + Edge Case Hunter; Severity: Low; deferred to c1-8, which
  owns the contending-instances design.)

  **Ruling (c1-8, 2026-07-26): accepted, and materially narrowed — entry kept.** The window needs a
  *second live instance* to be harmful: our shutdown must unlink a record that some other running
  companion published in between our read and our unlink. That second instance is now precisely the
  case c1-8 refuses — a launch that finds a verified-live companion prints its URL and returns
  without ever publishing, so the ordinary route to two contending writers is closed. What remains
  is the narrow residual recorded in the c1-8 section below: two launches racing inside the same
  startup window (a couple of seconds at the outside) can still both start, and only then can this
  unlink hit a foreign live record. So the guard is not redundant and the entry stays open, but its reachability now depends
  on a race that is itself deferred, not on ordinary use. No code change; `remove_discovery`'s
  docstring was reworded (c1-8 AC 16) because it previously pointed forward to c1-8 as the story
  that "first makes two instances contend for this file", which is stale in both halves now that
  c1-8 has landed and *prevents* the ordinary second instance.

  **Ruling (c1-9, 2026-07-26): CLOSED by unreachability — no code change to `remove_discovery`.**
  The harm scenario requires a second *live* instance inside one data directory, and c1-9's held
  advisory lock (`src/companion/app/singleton.py`) makes that state unconstructible: `run()` takes
  the lock before it resolves a port, binds or builds an app, and holds it until the process dies,
  so the launch that would have become the second live writer refuses instead. The check-then-act
  sequence in `remove_discovery` is unchanged and still not atomic — the entry is closed because
  nothing can reach it, not because the code was made safe. Its docstring was corrected accordingly
  (c1-9 AC 16), replacing c1-8's "two launches colliding within the same fraction of a second"
  wording.

  **What would reopen it, stated plainly rather than discovered later:** two companions run
  deliberately under *different* `PLANESWALKER_DATA_DIR` values. That is a supported configuration
  and it is not a defect — each instance then gets its own lock file, its own `companion.json` and
  no shared state, so the two never contend over one record and the TOCTOU still has no reachable
  harm. The residual would only return if a future story reintroduced two live instances sharing a
  single data directory, which the lock is specifically there to prevent. (This is the c1-8-review
  lesson about `trust_env=False` applied in advance: an environment variable that legitimately
  partitions the guard's scope must be *stated*, not left to be found.)

## Deferred from: story c1-8-single-instance-enforcement-with-verified-identity (2026-07-26)

- **Two launches started within the same startup window can both start** — the
  single-instance check is **check-then-act**, and nothing makes the check and the publish one
  atomic step. `run()` asks `client.live_instance()`, gets "nothing there", and only much later
  does the lifespan write `companion.json`; a second process entering that same gap reads the same
  "nothing there" and starts too, publishing over the first. That is the *baseline* failure this
  story was written to fix — two live companions with one rendezvous, the first still running and
  unreachable through the file — surviving in a window narrowed from **forever** to **startup**.
  Deliberately not fixed here: a real fix needs an OS-level mutex, and the shapes on the table
  (an `O_EXCL` lock file with the stale-lock-after-crash problem AD-15 guarantees will happen, or
  treating the bound port itself as the lock, which inverts the story's ordering by moving the
  check *after* the bind) are a design decision rather than a tweak — and the port option would
  need c1-3's ephemeral fallback rethought, since falling back to a different port is exactly how
  a second instance currently succeeds. The window is wider than it first looks (review finding,
  c1-8): it runs from the first launch's check to its lifespan publish, and with production
  timeouts the probe alone can spend up to ~3 s against a stale entry (1 s connect on a dead port,
  2 s read on a silent one, now also bounded overall at 5 s) — so a human double-launching a
  couple of seconds apart after a crash can hit it, no script required. Still a deliberate,
  repeated human act against an unlucky interleaving, not ordinary use.

  **Ruling (Brad, 2026-07-26, post-#15-merge): c1-9 builds the fix — a process-lifetime held
  lock.** Not a candidate any more: Story 1.9's ACs in `epics-companion-app.md` now carry it. The
  shape is the held-advisory-lock design, not an `O_EXCL` create-and-delete lock file: hold
  `msvcrt.locking`/`fcntl.flock` on an open handle for the process's lifetime, and the kernel
  releases it on any death — so AD-15's guaranteed crashes leave no stale lock and need no
  PID-liveness heuristics. This also collapses the `remove_discovery` TOCTOU's reachability to
  zero (its harm scenario needs a second live instance, which the lock makes impossible), which
  is the substance of Greptile's 3/5 hold on PR #15. Close this entry when c1-9 lands.
  (Source: c1-8 AC 15, homed at implementation; Severity: Low → fix scheduled c1-9.)

  **CLOSED (c1-9, 2026-07-26) — shipped as `src/companion/app/singleton.py`.** What landed, rather
  than what was planned:

  - **The primitive.** `os.open(lock_path(), O_RDWR | O_CREAT, 0o600)` then
    `msvcrt.locking(fd, LK_NBLCK, 1)` on Windows / `fcntl.flock(fd, LOCK_EX | LOCK_NB)` on POSIX,
    behind a module-level `sys.platform` branch. `LK_NBLCK` not `LK_LOCK` (which blocks ten times
    over ten seconds) and `flock` not `lockf` (record locks are process-owned, so a second `lockf`
    on another descriptor in the same process succeeds — it would have weakened the guarantee *and*
    made the same-process contention test silently vacuous). The lock file is `companion.lock`,
    separate from the rendezvous, zero-length, and **never unlinked** — on POSIX `flock` binds to
    the inode, so unlink-and-recreate would hand two processes "the lock".
  - **Where it sits in `run()`.** Probe first, lock second: the acquire is below c1-8's refusal and
    above `_note_reclaimed_entry`, the port resolution and the bind, with the release in `run()`'s
    outermost `finally` so the lock outlives the socket. Probing first keeps all fourteen of c1-8's
    `TestSingleInstanceCheck` cases passing **unedited**, and leaves the informative refusal (the
    one that can name a URL) as the common path. A contended launch prints one line naming no URL
    and returns `0`; there is deliberately no second probe, which would have cost up to five
    seconds on the one path whose job is to get out of the way.
  - **Release-on-death, measured.** Re-confirmed on this machine at implementation time (win32,
    py3.12.13): a second descriptor *in the same process* is refused (`PermissionError`, errno 13),
    closing the holder releases it, another process holding it refuses this one, and after a **hard
    kill** of the holder the lock is immediately available again with the file still present at
    0 bytes. That is the property that makes the held design correct under AD-15 — a crash is
    ordinary, and there is no stale-lock state to recover from and no PID-liveness heuristic.
  - **The race, before and after.** The baseline probe at `8bfc909` spawned two `run(0)` launches
    6 ms apart and left **two** live companions with one rendezvous. Re-run against the fix, one
    process survives, its port is the one `companion.json` names, and the loser prints a refusal
    line (see the c1-9 story record's live check 1 for the pasted before/after).

  Because contention reports as `PermissionError` — indistinguishable from a genuine permission
  problem — only the *lock* call is guarded; the `os.open` sits outside it, so an unwritable data
  directory fails loudly instead of being misreported as "someone else has it".
  (Severity: Low → **CLOSED**; no residual carried forward.)

- **A live instance whose event loop is blocked for longer than the read timeout is judged dead**
  — `PROBE_TIMEOUT` gives the read 2 s, and a companion wedged past that (a pathological request,
  a stop-the-world pause, a debugger breakpoint) answers `/health` too late. The probe then reports
  *app not running*, the launch proceeds, and the machine ends up in the two-instance state above.
  The 2 s read was chosen against a measured ~15 ms live response, so the margin is ~130×, and
  lengthening it has a real cost on the far more common path: every post-crash launch would stall
  for whatever the new deadline is. Accepted as the right side of the trade rather than fixed. If
  it ever bites, the fix is not a longer timeout but a different question — retry the probe once
  before concluding *dead*, which is machinery c6-1 is already building for its push path and
  could share. (Source: c1-8 AC 15, homed at implementation; Severity: Low.)

## Raised by Brad, outside a story (2026-07-26)

- **`assess_deck_power` ignores mana *quality* — it only counts mana** — the `mana_efficiency`
  dimension is built from two count-based signals and nothing else: Karsten land-**count** delta
  (`mana_base.karsten_land_delta`) and per-colour **source-count** deficits
  (`mana_base.compute_pip_signals` → `dimensions._mana_efficiency_score`, which starts at 100 and
  subtracts a penalty per land outside the tolerance band and per missing colour source). A source
  is any Land whose type line or "add {X}" text names the colour, and **every source counts the
  same**. Concretely, today's scorer cannot tell apart:
  - a **shockland from a Guildgate** — enters-tapped is invisible, so the tempo cost of a slow
    mana base is unscored, and this is the single biggest quality gap in Commander and 60-card
    alike;
  - a **fetchland or triome from a basic** — fixing depth and land-type synergy are unmodelled;
  - **painlands / filters / bounce lands** from clean duals — the *cost* of fixing is unmodelled;
  - a **mana dork or Signet from nothing at all** — `compute_pip_signals` `continue`s on every
    non-land, so **non-land colour sources contribute zero** to the deficit calculation. A
    rock-heavy or dork-heavy deck is scored as though its colours were unsupported, which is a
    correctness gap and not merely a missing refinement;
  - a **utility/colourless land** (Ancient Tomb, creature-lands, Cabal Coffers) beyond its
    non-contribution to colour — the upside is uncredited and the colour cost is only implicit.

  So two decks with identical curve and identical colour-source *counts* score identically on
  `mana_efficiency` even when one is an optimised mana base and the other is all taplands and
  basics — which is exactly the distinction an experienced player makes first. Weighting makes it
  matter: `mana_efficiency` is 0.20 of the 60-card profile (0.05 in Commander,
  `profiles.py:154/187`), so on the Standard/Modern fork this is a fifth of the score resting on a
  signal that is blind to mana quality.

  **Not a defect against any shipped AC** — Epic 5 scoped 5.4 to "raw numeric mana signals" and the
  Karsten regressions deliberately, and the benchmark passed on that basis. This is a **missing
  signal**, not a mistuned one, which is why it likely wants its **own story** (a
  `mana_quality`-style signal in `mana_base.py` + a dimension term) rather than a coefficient tweak.
  Feasibility is good: enters-tapped and produced-mana are both derivable from data already
  imported (oracle text / type line, the same inputs `_land_source_colors` reads), so no schema
  change or re-import is implied — the non-land-source fix in particular is close to free.

  **Homed against `post-epic-7-calibration-gate`** (sprint-status, currently `backlog`), which is
  the open bucket for scoring-quality inputs C1–C5; this joins them as a sixth, distinguished by
  being additive rather than corrective. Per the epic-7 gate-output homing rule it gets a key
  rather than a label. (Source: Brad, unprompted during story c1-7; Severity: Medium — it is
  weighted at 0.20 on the 60-card fork; no user-visible failure, but a systematic blind spot.)

## Deferred from: story c1-9-one-console-script-that-dispatches-without-disturbing-the-mcp-server (2026-07-26)

- **Windows Ctrl-Break ends the companion with exit status `3`, and interactive Ctrl-C is
  unverified** — live check 3 (real `CTRL_BREAK_EVENT` to a detached child) confirmed everything
  the AC names: no traceback, graceful uvicorn shutdown, `companion.json` removed,
  `companion.lock` retained, lock released for the next launch. But the observed exit status is
  `3`, not the dispatcher's `0` — traced, not assumed: uvicorn completes its graceful shutdown and
  the Windows console-control path then terminates the process before `main()` can return
  (`MAIN RETURNED` never prints under instrumentation), so the `3` is imposed outside our code.
  Interactive `CTRL_C_EVENT` could not be verified in the harness (it cannot be delivered to a
  detached child without also signalling the driver); `CTRL_BREAK_EVENT` is the proxy the story
  specifies. **Check during manual testing:** what an interactive Ctrl-C in a real terminal
  yields. Deliberately not "fixed" by trapping the signal, which would be new behaviour outside
  c1-9's ACs; if the exit status matters, c8-4's documentation story is where the observed
  behaviour gets written down. (Source: story c1-9 live check 3 / Completion Notes deviation 3;
  Severity: Low — Decide-once #5's exit vocabulary is about statuses *we* mint, and AD-15 rules
  out any supervisor that would read this one.)

  **CLOSED 2026-07-26 by Brad's C1-retro manual testing — real Ctrl-C exits `0`.** Observed in a
  real PowerShell terminal (venv-activated, `uv run artificial-planeswalker companion`, interrupt
  from the keyboard, `$LASTEXITCODE` read in the same window):

  ```
  INFO:     Shutting down
  INFO:     Waiting for application shutdown.
  INFO:     Application shutdown complete.
  INFO:     Finished server process [39616]
  $LASTEXITCODE -> 0
  data dir after -> cards.db, fastembed_cache, companion.lock (0 bytes); companion.json GONE
  ```

  So the `3` is an artifact of delivering `CTRL_BREAK_EVENT` to a **detached** child in the probe
  harness, **not** user-visible behaviour — the console-control path that imposed it is not the
  one a foreground Ctrl-C takes. On the real path `main()` does return and its value survives:
  Decide-once #5's exit vocabulary (0 = intent satisfied) holds end to end, with no signal
  trapping and no code change. c8-4 documents `0`. Every other condition the AC named also held:
  no traceback, graceful uvicorn shutdown, the lifespan retraction removed `companion.json`, and
  `companion.lock` was retained at 0 bytes for the kernel to release.
- **`test_entry_point.py`'s autouse `isolated_data_dir` fixture also re-points the two
  pre-existing transport tests** — the story said "leave the two old ones alone", and the
  documented deviation 1 covers only the forced `main()` → `main([])` edit. The new autouse
  fixture additionally moves `PLANESWALKER_DATA_DIR` to `tmp_path` for those two old tests, so
  they no longer exercise the real-data-dir path they did at baseline. Their assertions are
  unaffected and the change is an isolation *improvement* (they previously opened the developer's
  real card database); recorded here so the departure is stated rather than silent. Reopen only
  if a future story wants a test that deliberately exercises the real-data-dir diagnostics path.
  (Source: c1-9 code review, Acceptance Auditor; Severity: Low.)

## Deferred from: code review of c1-9 (2026-07-26)

- ~~**The "both mypy runs are mandatory" comment is enforced by no gate**~~ — **CLOSED by c2-1
  (2026-07-26).** `singleton.py`'s platform branch declares `uv run mypy src/` and
  `uv run mypy src/ --platform linux` both mandatory, but no pre-commit hook or CI step passed
  either `--platform`: the POSIX (`fcntl`) half was strict-checked only because CI happens to run
  on ubuntu, and the Windows (`msvcrt`) half only by Brad's local runs. A POSIX contributor could
  merge a type-broken Windows branch through a green CI. Fixed in `ci.yml`'s `quality` job, which
  was unfrozen for c2-1 (c1-9's AC 19 was what froze it).

  **What shipped is `--platform win32`, not the `--platform linux` the epic text asked for**, and
  the difference is the whole point. CI runs on `ubuntu-latest`, where the bare `mypy src/` **is**
  the linux run — adding `--platform linux` there would have been a pure no-op that satisfied the
  epic's letter while leaving the gap exactly as described above. The epic's wording was written
  from Brad's Windows machine, where the bare run is the win32 run; the retrospective's success
  criterion ("a deliberately Windows-broken `singleton.py` branch fails CI") is the one that
  identifies the real gap, and it is the one that was satisfied.

  Proven rather than assumed, per AC 17: with `msvcrt.locking(fd, msvcrt.LK_NBLCK)` (one argument
  short) temporarily substituted in the `sys.platform == "win32"` branch,
  `uv run mypy src/ --platform win32` reported
  `singleton.py:130: error: Too few arguments for "locking"  [call-arg]` and exited 1, while
  `uv run mypy src/ --platform linux` still reported `Success: no issues found in 83 source files`.
  The break was reverted; `git status --porcelain -- src/` is empty in the shipped commit.
  (Source: c1-9 code review, Blind Hunter; closed by story c2-1, C1 retro action item 3.)

## Deferred from: Epic C1 retrospective manual testing (2026-07-26)

Brad ran blocks A–D and G–H and declared himself satisfied; two blocks were not run. Homed here per
the gate-output rule rather than left as "we meant to".

- ~~**The renamed `COMPANION_PORT` env var has no live confirmation**~~ — **CLOSED by c2-1
  (2026-07-26)**, incidentally, by Task 10's second live check. With `$env:COMPANION_PORT = "9125"`
  set in a real shell before launch, the companion printed
  `[planeswalker] companion running at http://127.0.0.1:9125`, published
  `companion.json` for port 9125, and answered `GET /health` there with
  `{"status":"ok","instance_id":"9be64dcd-…"}` — while 8765 refused connections. So a real shell
  environment variable under the new name does reach `resolve_preferred_port`. **c8-4 may now
  describe `COMPANION_PORT` as hand-verified.**

  *Originally recorded as:* ruling R4 renamed `PLANESWALKER_COMPANION_PORT` → `COMPANION_PORT`
  during the manual-testing pass, and the checklist block that would have exercised it end to end
  was not run afterwards. Coverage was otherwise good — the unit suite reads `server.PORT_ENV_VAR`
  so it followed the rename automatically (1,684 passed), and the *malformed*-input paths were
  hand-verified in block A — leaving only "does a real shell variable under the new name reach
  `resolve_preferred_port`" unconfirmed.

  **Still not hand-run:** the other half of that checklist block, `--port` beating the env var.
  That precedence has unit coverage and was not exercised live here, so c8-4 should describe the
  *variable* as hand-verified but not the *precedence*. (Severity: Low.)

- **FR-22's fresh-install start has no live confirmation** — the checklist block pointing
  `PLANESWALKER_DATA_DIR` at an empty directory to prove the companion *starts* rather than crashing
  with no `cards.db` present was not run. Unit coverage is strong and deliberate (c1-2's inertness
  tests fresh-import with the data dir pointed at a non-existent path; c1-6's laziness tests assert
  no engine, no file planted, and a 503 through a test-local route), and the *observable* half — a
  data endpoint answering `503 database_not_initialized` — has no shipped route until c3-1, so there
  is genuinely less to see today than there will be. **Natural home: c3-9** ("fresh install guides
  instead of erroring and comes alive on its own"), which owns that loop in the UI and cannot be
  accepted without a real empty-data-dir run. Recorded so c3-9 inherits it as a known-unverified
  precondition rather than assuming Epic C1 closed it. (Severity: Low.)

## Deferred from: story c2-1 (2026-07-26)

- **`npm audit` reports 8 high-severity advisories in the `ui/` dev toolchain, and no gate looks at
  it.** All 8 are transitive and dev-only: `brace-expansion`/`minimatch` (a DoS via unbounded
  expansion) reached through `eslint`, `@eslint/eslintrc`, `@eslint/config-array` and
  `eslint-plugin-jsx-a11y`, plus `js-yaml` (quadratic CPU on merge-key chains) reached through
  `@redocly/openapi-core`, a dependency of `openapi-typescript`. Nothing here ships: Node is
  dev/CI-only (AD-13), `ui/dist` contains none of it, and the Python package never sees it — the
  realistic exposure is a contributor running `npm run lint` on hostile input.

  **Not fixed here, deliberately.** `npm audit fix --force` resolves it by installing
  `eslint-plugin-jsx-a11y@6.4.1` — a downgrade across a major boundary, which is the plugin that
  carries the entire UX-DR47 gate (AC 8). Trading a working accessibility gate for a DoS advisory in
  a linter is the wrong trade. The non-`--force` fix only reaches the `js-yaml` half. The real
  resolution is upstream: `eslint-plugin-jsx-a11y` publishing an `^10` peer range would let the
  `eslint ^9` pin lift and carry a patched `minimatch` with it — the same exit condition already
  recorded against the pin in `ui/package.json`.

  **Natural home: c8-5** (plugin distribution parity) or c8-4, whichever first has to make a
  statement about what the release contains. Re-check with `npm audit` then; if jsx-a11y has shipped
  an `^10` peer by that point this closes itself. Recorded so that the first person to run
  `npm audit` finds a decision rather than a surprise. (Severity: Low — dev-only, no runtime
  exposure; the *reporting* gap is the point, not the advisories.)

- **`ui/package.json` declares `engines.node: ">=20.19.0"` but the epic and PRD say "Node >= 20".**
  The measured floor is higher than the copy: `vite@8.1.5` declares
  `engines: ^20.19.0 || >=22.12.0` and `stylelint@17` declares `>=20.19.0`, so a literal Node 20.0
  cannot build `ui/`. `>=20.19.0` is the honest form of the same requirement and is what shipped;
  CI's `node-version: 20` resolves to the latest 20.x, which satisfies it. **This is a copy fix for
  c8-4** (release documentation), not a scope change — nothing needs rebuilding, the prose needs to
  stop saying "20". (Severity: Low.)

- **A third load-bearing version pin exists that no planning document predicts:
  `@testing-library/jest-dom` at `~6.9.1`.** The story predicted two pins (`typescript`, `eslint`);
  this one was found at install time. Both `latest` (7.0.0) and 6.10.0 declare
  `engines.node: ">=22"`, above this project's `>=20.19.0` floor and above CI's `node-version: 20`;
  6.10.0 is additionally deprecated upstream as an incorrect minor release. 6.9.1 is the last
  release declaring `>=14`. Unlike the other two pins, npm does **not** fail on this — `engines` is
  advisory by default, so an unpinned bump would install cleanly and then break only on the Node 20
  CI job. The reason is recorded in `ui/package.json` beside the dependency. **Relevant to c8-4**
  (which documents the Node floor) and to whoever eventually proposes raising it: lifting this pin
  is a Node-floor decision (AC 2 / AC 15), not a dependency bump. (Severity: Low — pinned and
  documented; recorded because the Spine's stack table now lags reality by two entries, `eslint ^9`
  being the other.)

- **`tests/integration/data/test_deck_repository.py::test_list_decks_with_strategy_field` is
  order-flaky under full-suite load.** Observed failing once during c2-1's Task 0 baseline run
  (`assert 'Control' is None`), then passing 5/5 in isolation and passing on an immediate full-suite
  re-run at the identical commit — so it is pre-existing at `50dddc3` and unrelated to this story,
  which adds no Python. Cause: the test creates three decks in immediate succession and asserts
  `list_decks()` returns them newest-first, but `created_at` can tie at the same microsecond, and the
  ordering has no secondary tie-breaker — so the two decks created in the same tick can come back in
  either order. Fix is a deterministic secondary sort key (`id`, or a monotonic sequence) in
  `list_decks`, or distinct timestamps in the fixture. Not patched here because AC 21 forbids this
  story touching `tests/` or `src/`. Note this is the *same class* of defect as the flaky-test
  tie-breaker closed at the Epic 1 retro, in a different query. **Natural home:
  `data-layer-orphan-handling`** (already keyed in sprint-status as the data-layer catch-all) or any
  story that next opens `DeckRepository.list_decks`. (Severity: Low — a false red, never a false
  green; but it will keep costing someone a re-run.)

## Deferred from: code review of c2-2-the-backend-serves-the-built-spa-as-a-committed-artifact (2026-07-26)

- **`sprint-status.yaml`'s `last_updated` comment is a single ever-growing line, thousands of
  characters long.** Each story appends its entire narrative onto one line chained behind
  "Previously:", making it unreadable, undiffable, and unbounded. The pattern predates c2-2 (this
  story merely doubled down on it). Natural fix: keep `last_updated` to a date + one clause and let
  the story records carry the narrative — a process/tooling nit for the epic retro, not any story's
  code. (Severity: Low — cosmetic, but it degrades every future diff of the file.)
  **Upgraded 2026-07-26 while contexting c2-3, and it is no longer only cosmetic: the file does not
  parse as YAML.** Measured on the committed tree at `9b612eb` — `yaml.safe_load` raises
  `ScannerError: mapping values are not allowed here` at **line 49**, the `last_updated` mega-line,
  because a YAML plain scalar may not contain `": "` and that line now contains dozens of them
  ("ruled by Brad: AC 5's…"). Every BMad workflow reads and rewrites this file textually, which is
  why nothing has noticed. Consequence if that ever changes — a status dashboard, a script, a future
  workflow using a real parser — is a hard failure on the whole sprint file, not a degraded read.
  Fix is the same fix (date + one clause), or quote/block-scalar the value; either way it is one
  edit, and it should land before something starts parsing it.

- **AC 17's browser-render half of c2-2 is Brad's, deferred to the C2 epic manual-testing
  checklist (ruled at review, 2026-07-26).** Every machine-checkable probe passed from a Node-less
  worktree (status codes, content types, byte-identical served bundle, cache headers, 405+Allow);
  what remains is opening `uv run artificial-planeswalker companion`'s printed URL in a browser and
  confirming the placeholder app paints. Reason for deferral: only a human can close SC-4's render
  half, and the epic retro checklist is its established home. (Severity: Low — every proxy signal
  is green; this is the eyes-on-pixels confirmation.)

## Deferred from: code review of c2-3 (2026-07-27)

- **`_truncate_descriptions`'s drop-the-key branch can void a Response Object's required
  `description` (spec-invalid OpenAPI).** `del node["description"]` at
  `src/companion/app/main.py:304` applies to every node, but the OpenAPI spec *requires*
  `description` on Response Objects. A route/response docstring consisting only of a Google-style
  section header would render a schema `openapi-typescript` (exit non-zero on a bad schema) may
  reject in the `frontend` job with a message pointing nowhere near the cause. Trigger is
  pathological today — every current response description is real prose — and the drop-the-key
  behavior is deliberately test-pinned
  (`test_a_description_that_is_only_a_section_loses_the_key`), so changing it is a design edit,
  not a patch. Natural fix when it matters: keep `""` (or skip the delete) when the parent context
  is a `responses` entry. (Severity: Low — unreachable without a degenerate docstring, and the
  failure is loud in CI.)

- **The sprint-status `last_updated` mega-line grew again in the same c2-3 diff that documented
  the file no longer parsing as YAML.** The upgraded entry above (2026-07-26) already homes the
  fix at the epic retro; recording here that c2-3's own bookkeeping commit lengthened the
  offending unquoted scalar rather than taking the one-edit quote fix — the retro fix should also
  re-check that nothing started parsing the file in the meantime. (Severity: Low — pre-existing,
  fix already homed.)

## Deferred from: code review of c2-4-the-voltglass-token-layer (2026-07-27)

- **Typography literals are the ungated family in the "every value is a token" set.** The c2-4
  literal bans cover colour/shadow/radius/spacing, but no rule keys `font`, `font-size`,
  `font-weight`, `line-height` or `letter-spacing`, so a component can hard-code type off the
  seven `--type-*` roles with no lint or guard firing. Deferred to c2-5, which owns type-role
  enforcement (the numeric-pairing lint); widening that to a full font-literal ban family — same
  shape as c2-4's four — is c2-5's scope decision. (Severity: Low — no components exist yet;
  c2-5 lands before the first one.)

  **CLOSED by c2-5 (2026-07-28).** Widened to the full family, per Brad's Q4 ruling: the ban is
  keyed on a property-name family regex covering `font`, every `font-*` longhand and
  `line-height`/`letter-spacing`, allowing only `var(--type-*)`, `var(--font-*)`,
  `var(--tracking-*)`, `0` and the CSS-wide keywords, with each property tied to its OWN token
  family so `font-weight: var(--space-1)` fails too. `font-variant-numeric` is deliberately
  excluded — its one legal value is already required by the numeric-pairing guard. Proven with
  `font-stretch`, `font-optical-sizing`, `font-size-adjust`, `font-synthesis` (never enumerated)
  and an invented `font-hyperkerning`. "Every value is a token" is now true.

## Deferred from: implementation of c2-5-self-hosted-space-grotesk (2026-07-28)

- **AC 4's render half is Brad's, deferred to the C2 epic manual-testing checklist.** The
  machine-verifiable half is fully closed: the committed binary is a real WOFF2 by signature,
  exact byte length and WOFF2 header (`tests/fonts.test.ts`), `git check-attr` resolves it as
  binary so a `core.autocrlf=true` Windows checkout cannot normalise it, it is emitted
  content-hashed into `assets/` and served `font/woff2`, the `@font-face` reaches it by a
  relative url the bundler rewrites, and nothing in the committed bundle names another origin.
  What remains is **opening the app in a browser with the network throttled to offline and
  confirming the glyphs are Space Grotesk rather than `system-ui`.** Reason for deferral: jsdom
  does not load fonts, does not apply `@font-face`, and reports whatever family string it was
  handed — a `getComputedStyle` assertion here would pass on a corrupt font, a missing font and
  a 404 alike, which is worse than no assertion. Same precedent as c2-2's AC 17. (Severity: Low
  — every mechanical signal is green; this is the eyes-on-glyphs confirmation. Worth checking in
  the same pass: that no flash of fallback text is visible on load, which is what `font-display:
  swap` plus the `index.html` preload is for.)

- **The numeric-pairing guard cannot see the cascade.** `findUnpairedNumericRole` fails a rule
  block that applies `font: var(--type-numeric)` without
  `font-variant-numeric: var(--type-numeric-features)` in the SAME block. What it cannot see is a
  correct pair undone by a later rule — `.is-compact { font-variant-numeric: normal; }` on an
  element that also carries the paired class. Resolving that needs specificity, source order and
  the element's real class list, which live in TSX and are chosen at runtime. **Review owns that
  half** for c7-2's StatChip and c6-8's curve axis, the first components that will apply the role.
  Documented at the guard, in `ui/README.md`, and asserted as a deliberate blind spot so it fails
  loudly if the guard ever grows a cross-block reader. (Severity: Low — no component applies the
  role yet.)

- **The offline guard's JS layer is a reviewed-host baseline, and it is deliberately brittle.**
  `.css` and `.html` in the bundle carry a TOTAL ban on external URLs; `.js` cannot, because
  React's DOM code legitimately contains `http://www.w3.org/…` namespace identifiers and a
  `https://react.dev/errors/` string, and a guard that fired on those is one someone switches
  off. So JS is covered by three family rules (font-CDN hosts, fetchable asset extensions) plus a
  snapshot of the reviewed host set. A React or Vite bump that introduces a new URL string will
  turn `tests/fonts.test.ts` red and require a human to add it to `REVIEWED_HOSTS` with a reason.
  That is the intent — under AD-13 a dependency bump already means committing a new bundle — but
  it is a maintenance cost worth naming rather than discovering. A runtime-constructed URL
  (`fetch('htt' + 'ps://…')`) is invisible to all four rules, as it is to every static check.
  (Severity: Low — the thing being prevented is a build-time CDN import, which the total ban on
  `.css`/`.html` covers absolutely.)
