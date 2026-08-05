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
- **A durably corrupt `cards.db` is classified transient forever** — ~~a UX ruling for c2-9 to
  make with the state designs in hand~~. **RULED AND HALF-SHIPPED, c2-9 (Q5, Brad 2026-07-29.)**
  The backend stays as it is: it genuinely cannot distinguish 200 ms of mid-import from a month
  of garbage, which is why decide-once #4 ruled the condition transient, so the distinguisher is
  **elapsed time on the client**. A sixth state was added — *Database updating, stalled* — with
  its copy written into `EXPERIENCE.md`'s table ("Reads haven't resumed for a while. Check your
  agent session — if no import is running, ask it to rebuild the database (`initialize_database`).")
  and its panel shipped in `src/components/StatePanel/`. It is declared `RETRIES_QUIETLY: false`
  in `states.ts` — the escalation of a quiet retry that has not worked.
  ~~**What remains, homed at c3-9** (which owns the polling): the "for a while" threshold and the
  switch from `database-updating` to `database-updating-stalled`.~~ **CLOSED, c3-9 (Q3,
  2026-08-02).** `STALLED_AFTER_MS = 60_000` in `ui/src/state/poller.ts` — 60 s of *continuous*
  `database_unavailable`, which at the 2 s / x2 / 30 s schedule is at least six consecutive
  refusals with the last two a full ceiling apart, so a single slow write burst cannot escalate.
  Armed by that token and by nothing else, and reset by every other outcome including a `200`;
  `database_not_initialized` NEVER escalates at any elapsed time, because a multi-minute first
  build is its normal case and its own copy promises the wait. Both directions are asserted from
  one fake clock, and mutation probe (e) — arming the clock on any error — turns the
  never-escalates assertion red. Historical note: The reason the ruling was not "leave it transient": for a durably corrupt
  file, "Reads will resume automatically — nothing to do here" is simply **false**, and c2-9 is
  the one story in the feature whose whole subject is whether the words are true.
  (Source: Blind Hunter; Severity: Low → **ruled**, implementation residue at c3-9.)
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
  precondition rather than assuming Epic C1 closed it. **CLOSED (backend half), c3-9 hand-run
  2026-08-02.** `PLANESWALKER_DATA_DIR` pointed at a genuinely empty directory: the companion
  STARTED, printed `http://127.0.0.1:8765`, published its discovery file, and planted **no**
  `cards.db` — c1-6's no-plant guarantee, confirmed live for the first time (the directory held
  only `companion.json`, `companion.lock` and `image_cache/`). `GET /health` answered `200`;
  `GET /api/decks` answered `503 {"reason":"database_not_initialized"}` with
  `cache-control: no-store`; `GET /` served the SPA. A populated `cards.db` was then copied in
  **with the server still running**, and the very next `GET /api/decks` answered `200` with real
  deck names — no restart, no cache-busting. FR-22's backend half is now confirmed rather than
  inferred. **What is still not confirmed is the PAGE doing it in a browser** — see c3-9's own
  residue below. (Severity: Low.)

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
  correct pair undone by a later rule. *(Review round 2026-07-28 narrowed this: the literal
  spelling — `.is-compact { font-variant-numeric: normal; }` — is now caught by stylelint, whose
  `font-variant-numeric` entry admits only the token; the spelling that remains invisible is a
  later block applying a different role — `.is-compact { font: var(--type-micro); }` — where
  every declaration is legal and the `font` shorthand resets `font-variant-numeric` as a side
  effect.)* Resolving that needs specificity, source order and the element's real class list,
  which live in TSX and are chosen at runtime. **Review owns that half.** Documented at the
  guard, in `ui/README.md`, and asserted as a deliberate blind spot so it fails loudly if the
  guard ever grows a cross-block reader.

  **Updated 2026-07-29 (story c2-7): the blind spot now has real consumers.** The role is
  applied by `.panel-count`, `.group-header-count` and `.stat-chip-delta`, and the label/micro
  companion guard added in the same story (`findRoleWithoutCompanions`) inherits the identical
  block-local limit — its own cascade case is a later `font` shorthand in another rule, which
  is asserted as a declared blind spot beside it. Reviewing a story that composes these
  primitives means checking the composed class list rather than assuming the gate did.
  (Severity: Low → **Low-Med** — three components apply the role now, and every later story
  that stacks a modifier class onto one of them is in the guard's blind spot.)

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

## Deferred from: code review of c2-5-self-hosted-space-grotesk (2026-07-28)

- **`git ls-files`-keyed guards cannot see untracked stylesheets.** `shippedStylesheets` in
  `ui/tests/fonts.test.ts` and `ui/tests/token-usage.test.ts` builds its file list from
  `git ls-files '*.css'`, so a not-yet-staged component stylesheet carrying a stray `@font-face`
  or an unpaired numeric role passes the local vitest run and is only caught once staged
  (stylelint's filesystem glob still catches value-level violations). This is the deliberate,
  comment-owned trade-off c2-4 established; if it ever bites, the fix is one sweep appending
  `git ls-files --others --exclude-standard '*.css'` to every such guard at once, not a
  per-story patch. (Severity: Low — the window closes at `git add`, and CI never has it.)

- **`:root { font: var(--type-body) }` pins the document rem basis to 14px and overrides the
  browser's default-font-size preference.** Before c2-5, `:root` set no `font-size`, so `1rem`
  tracked the user's browser setting; now it is 14px document-wide. Latent — nothing in `ui/`
  uses `rem`, and the whole token layer is px-based per DESIGN.md, so user font-size preferences
  were already inert for component text. If an accessibility pass ever revisits px-vs-rem, this
  root declaration is where the document basis is set. (Severity: Low — design-system-level,
  pre-dates this story in effect; the 14px change itself is recorded in the c2-5 Completion
  Notes.)

## Deferred from: implementation of c2-6-the-two-column-application-shell (2026-07-28)

- **AC 4's and AC 5's render halves are Brad's, deferred to the C2 epic manual-testing
  checklist.** This is the third story to split an AC this way (c2-2 AC 17, c2-5 AC 4), so it is
  now a pattern rather than an exception. jsdom has no layout engine — it resolves no grid
  tracks, evaluates no media queries and returns no box geometry — so every geometry assertion
  in this story reads CSS source. What is mechanically pinned by `ui/tests/shell.test.ts`: the
  gutter and panel-gap come from tokens, the right column is exactly `452px`, the breakpoint is
  exactly `1100px` in the context range form, the fluid track is `minmax(0, 1fr)`, and both the
  track and the grid item are floored at zero. What a browser still owes:

  1. Open at **1720px** and compare against the composition reference — header, fluid left
     column, 452px right column, footer, panels floating with visible canvas between them.
  2. Sweep **~1100px → ~2560px**: no horizontal scrollbar at any width, and below 1100px the
     right column drops beneath the left rather than compressing.
  3. On a **long deck**, the footer stays visible without scrolling, and the scrollbar sits at
     the content region's edge rather than the window's — the intended app-shell appearance and
     the accepted consequence of Q2.

  (Severity: Medium — the composition is the story's whole point, and no gate can see it.)

- **The shell's guards are static CSS readers, so the cross-file and runtime halves are
  review's.** `ui/tests/shell.test.ts` decides "is this a full-window fixed layer", "is this a
  root element" and "does this track floor at min-content" by reading declarations in one rule
  block at a time. Invisible to all of them: a full-window layer composed at runtime from two
  classes on one element; a root reached through a class the guard does not recognise as root
  (it knows `html`, `body`, `:root`, `#root`, the universal `*`, functional pseudo-class
  wrappers of those, `.app-shell` in any compound, and `.app-shell-columns` — but not an
  arbitrary class that happens to be styled onto a root element); any `overflow`, `position`
  or grid template set from JavaScript; and `var()` indirection, where the banned keyword
  lives in a custom property declared elsewhere (review round, 2026-07-28 — declared in the
  guard header alongside the runtime half). This is the same division of labour
  `tests/token-usage.test.ts` declares for its contrast and numeric-pairing guards, and it is
  stated in the guard file's own header. When reviewing c6-5's agent view in particular, check
  the composed result rather than assuming the confinement guard did. (Severity: Low — the
  static half covers the shape every story is actually likely to write.)

- **`z-index: 20` is a geometry literal that the AC 18 documentation guard does not cover.**
  The guard is derived from the code — every `\d+px` literal in every tracked stylesheet under
  `src/components/` must carry a `DESIGN.md` citation within a sentence of it (widened from
  `AppShell.css` alone in the 2026-07-28 review round) — and a bare unitless number cannot be
  told apart from the ones in `minmax(0, 1fr)`, `flex: 1` and `min-width: 0`. The value is documented
  in prose beside its rule (it comes from the composition reference, and UX-DR38 fixes the stack
  at one level deep so there is nothing to order it against), but that documentation is
  review-enforced rather than gate-enforced. If a later story introduces a second stacking
  level, the right repair is a `--z-*` token family, not a wider regex. (Severity: Low — one
  value, one level, and the epic's design says there will never be a second.)

## Deferred from: c2-6 AC 7 amendment (2026-07-28)

- **`DESIGN.md` line 328 still names `{spacing.6}` for the agent-view overlay inset; the shipped
  shell uses `--space-gutter`.** Story c2-6's AC 7 was amended to `var(--space-gutter)` by Brad's
  ruling on 2026-07-28, after review round 1 ruled the implementation that way: the two tokens
  are both 32px today, but the overlay's contract is that its inset **coincides with the shell's
  own frame**, and a later retune of the gutter would silently break that alignment while every
  assertion kept passing. The epic's Story 2.6 block and UX-DR8 both say plain "32px" and needed
  no change; DESIGN.md is the only artefact still naming the scale step.

  Left alone deliberately — DESIGN.md is the UX artefact, not an implementation record, and
  nothing renders differently since both values are 32px. **Homed against Story 8.3**, which
  already owns folding implementation-surfaced corrections back into the planning artefacts (it
  carries the six spine gaps and the EXPERIENCE.md "unconfirmed" stamps). The fix is one word,
  and the reason to make it is that the next component to reach for a "window frame" distance
  should find one name, not two. (Severity: Low — cosmetic today, a real trap only if the
  gutter is ever retuned.)

## Deferred from: c2-7 — presentation-only primitives (2026-07-29)

- **The four primitives' APPEARANCE is not dev-verified, and cannot be in this story.** `Panel`,
  `Badge`, `StatChip` and `GroupHeader` ship with **no on-screen consumer** — nothing imports
  them, deliberately (AC 24: the header badge slot stays empty and keeps naming c4-2/c4-10 as
  its fillers). jsdom applies no stylesheet and has no layout engine, so every visual claim in
  the story — the overlay level being one step up the ramp, `--shadow-rest` against
  `--shadow-raise`, the live dot's `var(--glow)`, and above all **whether the pseudo-element
  tone wash actually renders behind the badge's text rather than over it** — is read from CSS
  source or not at all. A `getComputedStyle` assertion here would return the empty string and
  pass for the wrong reason; this is the fourth story to split an AC this way (c2-2 AC 17, c2-5
  AC 4, c2-6 AC 4/5) and faking it was explicitly declined.

  **Homed at each primitive's first consuming story**, which is where a real screen can show it:
  `Panel` **RE-HOMED by c2-9 to c4-5** (card detail, the first real `level="overlay"` panel) and
  **c4-7** (the deck list) — this entry assumed the state panel would *be* a `Panel`, and Q6
  ruled that it is not: `DESIGN.md` declares a separate `components.state-panel.*` block, and the
  two differ where it matters (a Panel's title is `--type-label`, 11px uppercase tracked; a state
  panel's headline is `--type-heading`, 17px sentence case). Rendering one through the other
  would have meant threading a second title role through `Panel`, which is how a primitive stops
  being one. So `Panel` still has no on-screen consumer. `GroupHeader` at **c4-7** (the deck list),
  `Badge` at **c4-10** (the format check) and **c4-2** (the header badges), `StatChip` at the
  first surface that carries one. Carried on the **epic manual-testing checklist** as well, so
  it is not only findable from this file. (Severity: **Medium** — the wash's stacking behaviour
  is the one mechanism in the story with no static proof available, and the failure mode is a
  solid blank pill with invisible text, which reads as a content bug rather than a CSS one.
  Check it first.)

  **Extended by the 2026-07-29 review: the tone-over-wash CONTRAST is also unmeasured.**
  UX-DR6's table covers `--accent-dim` on `--surface-overlay` only; nobody has measured
  `--accent-bright` over a 12% `--accent` wash, nor positive/negative/caution text over their
  own washes, on any surface or under the four alternate themes. `Badge.css`'s accent comment
  now says so plainly instead of asserting the floors are cleared. Same home, same first
  consumers: eyeball the wash's stacking AND run the contrast numbers at c4-2 / c4-10.

- **`findRoleWithoutCompanions` derives its uppercase half by reading `DESIGN.md` from a second
  test file.** `tests/tokens.test.ts` already calls its copy of that path "the ONE place this
  path is written"; `tests/token-usage.test.ts` now writes it too, because no token NAME encodes
  case the way `--tracking-X` encodes tracking, and reading the contract beat hand-typing "label
  and micro". Both copies carry a loud anchor that turns a stale path into a named failure
  rather than a guard asserting nothing over an empty map, and `tests/package-contract.test.ts`
  pins the exhaustive list of `yaml` importers so a third one cannot appear quietly. The clean
  repair is a shared `tests/design-contract.ts` exporting the path and the parsed frontmatter,
  which was declined here as out of scope for a story that ships components. (Severity: Low —
  two copies, both anchored, and the UX artefacts are re-exported rarely.)

## Deferred from: code review of c2-7 (2026-07-29)

- **StatChip `signed()` renders raw `String(delta)`** — a fractional delta shows
  `+0.30000000000000004` and a magnitude ≥ 1e21 shows `+1e+21` as user-facing text
  (`ui/src/components/StatChip/StatChip.tsx:45`). Q6 already homes delta *formatting* at the
  first consuming story; that entry now also covers fractional and huge numbers — the consumer
  either formats before passing or adds the sibling formatted-delta prop Q6 anticipated.
  (Severity: Low — no current caller passes a non-integer delta.)

## Deferred from: c2-8 — ManaPip / ManaCost and the Scryfall cost parser (2026-07-29)

- **`ManaPip` and `ManaCost` APPEARANCE is not dev-verified, and cannot be in this story.**
  Both ship with **no on-screen consumer** — nothing imports them, deliberately (AC 24:
  `AppShell.tsx` is untouched) — and jsdom applies no stylesheet and has no layout engine. So
  every visual claim in the story is read from CSS **source** or not at all: the pip being a
  **circle** at all (`min-width: 1.25em` + `height: 1.25em` + `--radius-pill`), the **hard-stop
  two-colour gradient** on the fifteen hybrid classes actually reading as a split rather than a
  blur, the 13px numeric glyph sitting **legibly** in a 16.25px circle (a 0.8 glyph-to-pip ratio,
  tighter than the mock's 0.62 — this is the value most likely to want a nudge), the **wide
  case** (`{1000000}`, `{HW}`) growing into a pill instead of clipping, and the **row wrapping**
  when fifteen B.F.M. pips meet the 452px right column. A `getComputedStyle` assertion here
  would return the empty string and pass for the wrong reason; this is the **fifth** story to
  split an AC this way (c2-2 AC 17, c2-5 AC 4, c2-6 AC 4/5, c2-7 AC 21) and faking it was
  explicitly declined.

  **Homed at the first consuming stories**, which are where a real screen can show it: **c4-3**
  (card placeholders — the first render of a cost anywhere), **c4-7** (deck rows, the densest
  use and the one where the wrap matters), **c4-9** (the colour-distribution legend, which is
  also where the optional `label` prop gets its first caller). Carried on the **epic
  manual-testing checklist** as well, so it is not only findable from this file. (Severity:
  **Medium** — the glyph-to-pip ratio and the gradient's hard stop are the two values with no
  static proof available, and both fail *legibly-but-wrongly* rather than loudly. Check the
  `{1000000}` and `{W/U}` cases first.)

  > **RESOLVED at c4-3 (2026-08-04). All five claims hold; nothing needed a nudge.** Paid on a
  > throwaway harness — the BUILT stylesheet served to Edge against hand-written markup, the same
  > instrument c4-2 used for `Badge` — and screenshotted at 6x. **The pip is a circle.** **The
  > hybrid gradient's hard stop reads as a clean 45 degree split with no blur.** **The 13px glyph
  > sits centred and legible in the 16.25px circle** at the 0.8 ratio this entry flagged as most
  > likely to want a nudge — `0 2 X T P S` all checked, none crowded. **The wide case GROWS into a
  > pill rather than clipping** (`{1000000}`, `{HW}`, `{100}`). **Row wrapping works**: fifteen
  > B.F.M. pips wrap to a second row inside a **176px** card — narrower than the 452px column this
  > entry worried about, so the harder case was the one measured. The two named-first cases
  > (`{1000000}`, `{W/U}`) were checked first, as instructed. **c4-7 and c4-9 inherit nothing from
  > this entry**; what remains for them is composition, which a harness cannot show.

- **The `--mana-*` data-ink rule's "unstacked curve bar" half is REVIEW'S, not the gate's.**
  UX-DR7 bans a WUBRG token on "an unstacked curve bar", and whether a given bar is genuinely
  stacked is a property of the data bound to it and the elements composed at runtime — both in
  TSX, neither in CSS. The guard says so in its own comment (the same division of labour
  `surfaces.ts`'s `stepsExactlyOne()` declares), and `ui/README.md` says so where c4-8's author
  will be reading. **c4-8's reviewer must look**; the gate will not have looked for them.
  (Severity: Low — one story owns it, and it is named in three places.)

- **The ` // ` split-card separator is spoken as the literal characters.** `describeManaCost`
  renders `{2}{B} // {B}` as _"2 generic, black // black"_, so a screen reader says "slash
  slash". A friendlier reading ("or", "split with") was declined as an invention — nothing in
  DESIGN.md, EXPERIENCE.md or the epic rules on it, and guessing would put unsourced words in a
  user's ear. Homed at **c4-3/c4-7**, where a split card first renders and the phrasing can be
  decided against something real. (Severity: Low — 338 of 32,318 costs, and the literal reading
  is honest rather than wrong.)

  > **c4-3 disposition (2026-08-04): CONFIRMED LIVE, RE-HOMED to c4-7 unchanged.** A split card
  > does now render here — `Heaven // Earth` is a fixture in `CardPlaceholder.test.tsx`, and its
  > cost `{X}{G} // {X}{R}{R}` renders five pips and the literal ` // ` text run. So the entry's
  > condition ("where a split card first renders") is met and the reading was heard against
  > something real. **The phrasing is unchanged, deliberately**: the placeholder is a fallback
  > slot, not a reading surface, and c4-3 also sharpened the population — **all 79** cards that
  > permanently need the named placeholder are split-named, but **all 79 have a BLANK mana cost**,
  > so `describeManaCost` is never called for them and the separator is never spoken on this
  > surface at all. The decision belongs where a cost is read aloud in prose: **c4-7's deck rows**.

- **For sighted colour-vision-deficient users, a pip's colour IS its sole carrier** (added at
  c2-8's code review). A `{W}` pip and a `{G}` pip differ in nothing but fill — no letter, no
  pattern — so the `role="img"` accessible name serves AT users while a sighted CVD user cannot
  read any cost. DESIGN.md's ruled shape ("a plain circle filled with the mana token") compels
  this, and UX-DR7's no-lookalikes rule closes the obvious escape of drawing symbols; the entry
  exists so the trade-off is a **decision on record, not an omission**. Homed at the **c4-3
  eye-check** with the other visual claims: if the plain circles read as indistinguishable in
  practice, the available levers are a glyph-slot letter (the mechanism Phyrexian already uses,
  and plain text is not a lookalike) or a DESIGN.md amendment — Brad's call, made against a real
  screen. (Severity: **Medium** — an accessibility gap for a real user class, but one the design
  contract currently mandates.)

  > **c4-3 disposition (2026-08-04): MEASURED, and the levers are NOT needed — pending Brad's
  > acceptance against a real screen, which this entry reserves to him.** The six shipped
  > `--mana-*` colours were pushed through the Machado severity-1.0 dichromacy matrices in linear
  > RGB and compared pairwise as CIE Lab dE. Worst pair per vision type: **normal B/C 24.5**,
  > **protanopia U/B 10.0**, **deuteranopia R/G 14.1**, **tritanopia B/C 10.9**. Every pair stays
  > above dE 10 under every simulated deficiency — roughly 4x the just-noticeable difference for
  > large flat patches — so the plain circles do NOT read as indistinguishable and neither lever
  > (a glyph-slot letter, a DESIGN.md amendment) is called for. **Two limits, stated rather than
  > glossed:** a simulation is not a person, and this measures *distinguishability* (telling two
  > pips apart) rather than *identifiability* (knowing WHICH colour a pip is) — the latter stays a
  > real gap for a sighted CVD reader that only a glyph would close, and it is the gap the
  > `role="img"` name closes for AT users. **Stays OPEN at Medium until Brad accepts the numbers;
  > it is no longer waiting on an eye-check that has not happened.**

- **`{Y}`, `{Z}`, `{S}`, `{L}`, `{D}` and `{HW}` are deliberately NOT in the parser's symbol
  table.** Each is real in the shipped database and each renders correctly today — as a
  colourless pip showing its own letter, which is exactly what the totality contract promises
  and what AC 3 requires. Adding them as recognised families would buy a *colour* for snow and
  a *name* for the un-set symbols, and neither has a DESIGN.md or epic ruling to source it
  from. Revisit only if a consuming story shows one of them reading badly. (Severity: Low — the
  current behaviour is correct, not a gap; this entry exists so a later author knows the
  omission was a decision.)

## Story c2-9 — the shared state panel and every system-state message

- **The state panel's appearance is dev-verified for the first time in this epic, and only
  partly.** `App.tsx` renders the no-active-deck panel into the shell's `left` slot (Q1), so
  unlike c2-7 and c2-8 there IS a screen. What that screen proves is what a browser draws; what
  it does not prove is everything jsdom is blind to *in the test suite*, which is the same list
  as ever: **centring, the 480px measure, the hairline border, the large radius, the chip's
  recessed `--surface-well` material and its mono family, and the accent colour and weight of
  the next-action line.** jsdom applies no stylesheet and has no layout engine, so there is no
  `getComputedStyle` assertion in `StatePanel.test.tsx` — one would report the defaults back and
  pass over a stylesheet that was never linked. This is the **sixth** story to split an AC this
  way (c2-2 AC 17, c2-5 AC 4, c2-6 AC 4/5, c2-7 AC 21, c2-8 AC 21) and faking it was again
  declined. What IS statically proven: the token families spent (an allowlist guard), the
  absence of `--negative`/`--caution`, the absence of `transition`/`animation`, and the
  DESIGN.md citation beside the one px literal. **On the epic manual-testing checklist.**
  (Severity: Low — every claim has a static half; the visual half is a first-look, not a risk.)

- **The five states nobody can see yet.** Only `no-active-deck` is on screen, because it is the
  only one that is TRUE with no fetch layer. `database-not-initialized`, `database-updating`,
  `database-updating-stalled`, `disconnected` and `internal-error` render correctly in the test
  suite and have never been looked at in a browser — in particular the **command chip**, which
  only appears in three of them, and the **two-paragraph** guidance/action stack, which
  `no-active-deck` does not exercise (it has no guidance). Homed at **c3-9**, which wires the
  states and is the first story able to show them. **PARTLY CLOSED, c3-9 (2026-08-02).** Four of
  the five are now REACHABLE in the running app — `database-not-initialized`, `database-updating`,
  `database-updating-stalled` and `internal-error` are each selected by the poll from a wire
  token, and the first is what a genuine fresh install shows (confirmed live at the HTTP layer).
  `disconnected` stays **c5-6's** and is selected by nothing, per Q10. **The browser look-at was
  NOT performed**: this environment has no browser automation installed and adding one would be a
  new dependency, so the VISUAL half is unchanged and moves to the epic manual-testing checklist
  with a recipe — run `PLANESWALKER_DATA_DIR=<empty dir> uv run artificial-planeswalker
  companion` and open the printed URL for `database-not-initialized`, then hand-edit `App.tsx`'s
  `left` prop to a literal `<StatePanel state="..." />` for each of the other four. What to look
  at is unchanged: the **command chip** (three states have one) and the **two-paragraph
  guidance/action stack**. (Severity: Low.)

- ~~**`states.ts` has no runtime consumer.**~~ **CLOSED, c3-9 (2026-08-02).**
  `PANEL_FOR_REASON` is consumed by `ui/src/state/panel.ts` — which also uses its KEY SET as the
  runtime membership test for `ErrorReason`, so there is still no second list anywhere — and
  `RETRIES_QUIETLY` by `ui/src/state/poller.ts`, indexed at runtime rather than paraphrased
  (probe (b) replaces the consult with "always retry" and five assertions go red).
  `CLIENT_ONLY_STATES` stays a declaration and that is correct: `disconnected` is **c5-6's**, and
  `database-updating-stalled` is produced by elapsed time on the client rather than selected from
  a list. The original entry, for the record: `PANEL_FOR_REASON`, `CLIENT_ONLY_STATES` and
  `RETRIES_QUIETLY` are total maps written for **c3-9** to read; nothing imports them today, so
  they are tree-shaken out of the bundle. This is deliberate — the alternative was leaving the
  wire-token→panel mapping and the retry contract as prose in a story record, which is where
  `internal_error` was left in c1-4 and what cost this story an AC to repair. Their correctness
  is proven by `npm run typecheck` (a seventh `ErrorReason` fails to compile), not by `npm test`.
  (Severity: Low — a declaration with a named owner and a compile-time gate.)

- **`--font-mono` has exactly one consumer and one job.** The command chip. If a later story
  reaches for it anywhere else, that is a UX-DR2 conversation (hierarchy never comes from a
  second family), not a free reuse — the whole argument for admitting the token was that a
  command literal is *data* the user retypes. No guard enforces the scope today; it is stated in
  `tokens.css`, in `DESIGN.md`'s Typography section and here. (Severity: Low.)

- **The copy guard cannot decide the half that matters most.** Whether a sentence is
  second-person, blameless and gives a concrete next action is not statically decidable, and it
  is the substance of UX-DR33. Declared in `tests/copy-rules.test.ts`'s own header alongside two
  narrower residues: copy assembled from single words at runtime (`describeManaCost`), and a
  string reaching `aria-label` through an expression rather than a literal. **Review owns all
  three** — the same division of labour `surfaces.ts` and `findAccentDimOnOverlay` declare for
  theirs. A reviewer of c2-10, c4-3, c4-12 and c6-6 must READ the copy. (Severity: Low, but
  permanent — this does not get closed, it gets honoured.)

## Deferred from: code review of c2-9 (2026-07-29)

- **A runtime-unknown `state` key crashes the StatePanel.** `STATE_COPY[state]` at
  `StatePanel.tsx:92` has no fallback branch: a value arriving through untyped wiring (a stale
  enum, a JS caller, a mis-parsed wire token) yields `undefined` and `copy.headline` throws — an
  unhandled render exception, which is the error screen the story exists to ban. TypeScript
  guards it today and no runtime caller exists (`App.tsx` passes a literal). ~~**c3-9 owns
  runtime validation of wire values before they reach this prop.**~~ **CLOSED, c3-9 (Q5,
  2026-08-02).** `ui/src/state/panel.ts`'s `panelFor` is the one place a wire value becomes a
  `StateKey`: total by construction over every string and over `null`, clamping to
  `internal-error`. `StatePanel` gained **no** fallback branch and stays presentation-only. Three
  inputs reach the clamp — a token this build does not know, a token `states.ts` maps to `null`
  (`invalid_request` and `payload_too_large` are both DECLARED on `GET /api/decks`, so this is
  reachable rather than theoretical), and no token at all. Also closed here, and not in the
  original entry: indexing a plain object with `__proto__` or `constructor` returns an INHERITED
  value rather than `undefined`, which a bare `?? 'internal-error'` would have passed through to
  the prop as an object; `Object.hasOwn` is what stops it and it is asserted.
  **Two corrections to this entry's own text, both measured at c3-9.** The line is
  `StatePanel.tsx:104`, not `:92`. And the throw is one line EARLIER than described: probe (d)
  removes the clamp and the crash is `TypeError: Cannot read properties of undefined (reading
  'body')` from `guidanceOf(copy)`, not from `copy.headline`.
  (Severity: Low today; Medium once wiring exists.)

- **The un-quoted tails of EXPERIENCE.md's copy rows are contract nobody gates.** The verbatim
  gate captures `Headline:` and `Body:` only; the no-active-deck row's deck-list clause and both
  retry clauses ("Deterministic: this state never retries itself", the stalled row's threshold
  note) live outside the captures and can be edited or deleted with every gate green while their
  TypeScript mirrors (`RETRIES_QUIETLY`, the `decks` prop) drift undetected. ~~Extending the gate
  is new scope; candidate home is **c3-9**, beside the wiring those clauses constrain.~~
  **CLOSED, c3-9 (Q6, 2026-08-02).** `ui/tests/copy-tails.test.ts` gates the three tails that
  constrain c3-9, each against its TypeScript mirror in BOTH directions: the no-active-deck
  deck-list clause against `DECKS_PATH`, the stalled row's *"the client decides when 'a while' has
  passed (c3-9 owns the threshold)"* against `STALLED_AFTER_MS` and
  `RETRIES_QUIETLY['database-updating-stalled']`, and the internal-error row's *"Deterministic:
  this state never retries itself"* against `RETRIES_QUIETLY['internal-error']`. Deleting a clause
  fails the gate; flipping a mirror fails the gate. A NEW FILE rather than an edit to
  `copy.test.ts`, so that suite's "passes unchanged" prediction stays literally checkable, and the
  mirrors are read out of SOURCE rather than imported — see the file header for the twelve `tsc`
  errors the import version produced, which is `ui/README.md`'s cross-project-import blind-spot
  row earning its place. **The fourth tail — the disconnected row's connection-pill note — is
  DECLINED and re-homed on c5-6 by name**, which owns the pill, its backoff and the state; there
  is nothing in this repository for it to be checked against today, so a gate on it would assert
  prose against prose. (Severity: Low.)

## Deferred from: story c2-10 (footer attribution, 2026-07-30)

Every entry here is a **visual claim jsdom cannot decide** (AC 22). The source-read half of each
is asserted in `ui/tests/shell.test.ts` against `Footer.css`; what is deferred is only what the
CSS *does on screen*. None of these is claimed anywhere as verified.

- **10px ALL-CAPS legal text — is it actually readable?** THIS IS THE FIRST THING TO LOOK AT.
  `DESIGN.md` assigns footer attribution to `{typography.micro}` (`400 10px/1.3`, `0.08em`
  tracking) and declares that role uppercase, and the companion guard derives the requirement
  from the artefact's own `textTransform:` key — so three sentences of legally load-bearing text
  render at 10px in capitals. Brad ruled **ship the spec as written** (Q1, 2026-07-30): it is
  what the artefact says, the DOM text is untouched by `text-transform` so nothing about the
  contract or the screen reader changes, and deviating means amending a UX artefact on a
  frontend story. The contrast AC exists because this text must be readable — and case and size
  are the other two halves of readability, which no AC covers. **If it reads badly by eye, the
  correction is a `DESIGN.md` amendment in Epic 8's release-readiness pass**, made with the
  rendered page in hand rather than from the spec. (Severity: Medium — it is the one string in
  the app that has to be readable.)

- **The 24px hit box as laid out.** `min-height: 24px` + `min-width: 24px` with
  `display: inline-block` is asserted in source (the review of 2026-07-30 changed the display
  from `inline-flex` — see the underline entry below — and added the width axis), and the
  display mode is asserted beside the minimums because they do nothing on a plain inline box —
  but jsdom has no layout engine, so the *measured* box of each link is unverified. Worth a
  specific look: an `inline-block` box 24px tall inside a 13px line box will grow that line, so
  the two footer link runs may sit on a visibly taller line than the plain text around them, and
  the box extends below the baseline rather than centring the text the way the flex version
  would have. Check with a devtools box inspection, not by eye alone. (Severity: Low.)

- **The persistent underline and the hover brightening — NOW FIRST ON THE CHECKLIST, above the
  10px readability question.** The code review of 2026-07-30 found `display: inline-flex` was
  plausibly rendering AC 5's release-condition underline as *no underline at all* — text
  decoration does not propagate into flex items — and every automated gate reads source, so
  nothing could see it. The fix is `display: inline-block`, under which the decoration applies
  to the link's own text; **the browser check is the proof the fix needs**, since the failure
  mode is exactly "true in source, false on screen". `text-decoration: underline` at rest and
  `color: var(--text-primary)` on `:hover` *and* `:focus-visible` (the review added the focus
  half) are read from source, and the guard proves no hover rule introduces the decoration
  (UX-DR47). Also still unverified by any gate: that the underline is *visible* at 10px against
  `--text-secondary`, and that the rest→hover step reads as a brightening rather than as a
  flicker. (Severity: Medium until the eye check — it is the release-condition affordance.)

- **The focus ring's appearance.** These are the **first focusable elements in the codebase**,
  so this is the first time `--focus-ring` / `--focus-ring-width` / `--focus-ring-offset` have
  ever been rendered — they shipped in c2-1 with nothing to point at. `outline` was chosen over
  `box-shadow` so an ancestor's overflow cannot clip it, but whether a 2px ring at 2px offset is
  clearly visible around a 24px inline-flex box at the very bottom edge of the window is a
  browser check. **Tab to both links.** (Severity: Medium — it is the token layer's focus
  contract getting its first real exercise, and c4-11 inherits whatever is learned here.)

- **The border and the surface.** `border-top: 1px solid var(--border-hairline)` over
  `background: var(--surface-base)` is `DESIGN.md`'s frontmatter verbatim. Note that the
  background is the same token as the page canvas, so the *only* visible separation is the
  hairline — and the footer sits inside the shell's `var(--space-gutter)` padding, so the rule
  spans the content width rather than bleeding to the window edge. That is the shell's existing
  layout decision (c2-6), not this story's; if the full-bleed rule DESIGN.md's "full width"
  implies is wanted, it is a shell change and belongs to whoever owns that, not to a footer
  story. (Severity: Low — a deliberate reading, recorded so it is a decision and not a drift.)
  **RATIFIED (Brad, 2026-07-30, c2-10 code review): the content-width reading stands** — the
  hairline aligns with the header and columns inside the gutter frame. No longer a unilateral
  call; a full-bleed rule would now be a new decision, not a correction.

## Deferred from: story c3-1 (deck list and deck detail endpoints, 2026-07-31)

- **`list_decks` materialises every deck's full card list just to count it.**
  `src/data/repositories/deck.py:263` eager-loads
  `selectinload(DeckModel.deck_cards).selectinload(DeckCardModel.card)`, so `GET /api/decks`
  loads the whole corpus of every saved deck and then discards it down to three integers per
  deck. **Accepted here, not fixed**: it is existing `src/data` behaviour that the `list_decks`
  MCP tool already pays, the deck count is single digits on a real machine, and NFR-05's budget
  is the deck *view*, not the deck list. Adding a count-only query in c3-1 would have been a
  second read path over one shape, which is exactly what AD-1 exists to prevent.
  **Home: c10-3** (latency hardening). If it is fixed there, the fix belongs in the repository —
  an aggregate query behind the same method — so both shells inherit it. (Severity: Low now;
  scales with deck count and deck size.)

- **`DeckRepository.list_decks` ties on `created_at` and falls back to UUID order.**
  Re-confirmed still open at c3-1. `deck.py:262` orders by `created_at DESC, id`; `id` is a UUID,
  so decks created within the same clock tick come back in effectively random order.
  `tests/integration/data/test_deck_repository.py::test_list_decks_with_strategy_field` is
  order-flaky for exactly this reason and is ledgered twice already (c1-5 and c2-1 entries) —
  this is the third confirmation, not a new finding. c3-1 did **not** fix it: it is a `src/data`
  change with MCP blast radius. What c3-1 did instead is make the endpoint's own contract honest
  — `read_decks`' docstring says a tie is arbitrary, and `test_routes_decks.py` asserts ordering
  only against seeds whose `created_at` is genuinely distinct. **Home: unowned, ledgered.** Any
  UI that promises "newest first" to a user (c4-7's deck-list panel) is the first story that
  actually needs this fixed. (Severity: Low.)

  **FOURTH confirmation, c3-2 (2026-07-31), and it FIRED.** `test_list_decks_with_strategy_field`
  failed once in a full-suite run (`assert 'Control' is None` — the three same-tick decks came back
  in UUID order) and passed 56/56 in isolation immediately after, and green on the re-run. Nothing
  in c3-2 touches `DeckRepository`, deck seeding or that test; what c3-2 changed is that the suite
  is ~50 tests longer, which shifts the timing that decides whether the three `create_deck` calls
  land in one clock tick. **This is now the only test in the repo that fails for reasons unrelated
  to the code under change, and it has cost four stories a diagnosis each.** The fix is two lines
  (distinct `created_at` values in the test, or a deterministic tie-breaker in the repository) and
  is being deferred purely on `src/data`-blast-radius grounds — but the cost of the deferral is now
  larger than the fix. Recommend closing it in the next story that touches `src/data`, or as a
  standalone chore. (Severity: raised to **Medium** — a flaky gate teaches people to re-run.)

  **It fired a SECOND time during the same story**, in the post-review full-suite run (a different
  deck id, same `assert 'Control' is None`). Two failures in one afternoon, both on a branch that
  touches no deck code. That is no longer "intermittent under full-suite timing" — at ~1,890 tests
  the three `create_deck` calls land in one clock tick often enough to be a routine occurrence, and
  every future story now inherits a suite that goes red for reasons unrelated to its diff. **Raised
  to Medium-High, and recommended as the next standalone chore rather than waiting for a story that
  happens to touch `src/data`.** Fix: `.order_by(DeckModel.created_at.desc(), DeckModel.id)` is
  already the repository's order — the test is what needs distinct `created_at` values, exactly as
  `test_routes_decks.py::test_orders_newest_first_when_the_timestamps_differ` does it.

- **`GET /api/decks` and `GET /api/deck/{id}` have never been called by a browser.**
  c3-1 ships no frontend (AC 18), so both endpoints are proven only through `httpx.ASGITransport`
  in-process. Not yet exercised: a real `fetch` from the served SPA origin through the security
  envelope, the Vite dev proxy path (`changeOrigin`, c2-1), and CORS behaviour under a real
  browser preflight. Nothing suggests a problem — the envelope is gated and `/health` already
  crosses it — but "a real browser has fetched this" is not yet true of any companion route.
  **Home: c4-2** (the deck bootstrap, the first real consumer). Worth Brad's eye on the C3
  manual-testing checklist: open the companion and hit `/api/decks` in the browser address bar.
  (Severity: Low.)

- **The `openapi.json` byte-comparison gate cannot see *meaning*.**
  `tests/unit/companion/test_openapi_contract.py` asserts that Python internals (`Args:`,
  `Attributes:`, `>>> `) never cross the wire, and c3-1 confirmed that is where it stops: the four
  schemas it exposed carried MCP-internal prose ("keeping `load_deck` payloads small for LLM
  clients", "Build via the helper's explicit constructor, not `model_validate`", "the Story 1.6
  deck-analysis tools") straight into `types.d.ts` and `/docs`, and **Sphinx role markup**
  (`` :class:`DeckSummary` ``) did too — a family the gate's list does not name and which appears
  in neither already-shipped description. c3-1 fixed its own four by rewriting the leading summary
  and pushing the Python detail below `Attributes:`, and recorded the scan it used. It did **not**
  add a gate. Whether one is worth building (ban the role-markup family; the prose half is not
  statically decidable, like UX-DR33's second-person half) is open. **Home: c3-2**, the next story
  to add a schema to `components.schemas` — it will face the same question with `Card`.
  (Severity: Low — cosmetic on the wire, but it is documentation the UI author reads.)

  **RESOLVED (partly) at c3-2, 2026-07-31 — Q5's split ruling.** The statically decidable half
  shipped: `test_openapi_contract.py` gained `PYTHON_INTERNAL_FAMILIES`, keyed on three shapes
  (Sphinx role markup `:[a-z]+:` before a backtick; any line-anchored Google-style section header,
  with `Note:`/`Warning:` as a declared two-member allowlist rather than the old twelve-member ban
  list; a doctest prompt) plus a non-vacuity test proving each family fires. It catches what
  c3-1 found by hand and what the three-member `PYTHON_INTERNALS` never could. **The prose half is
  re-homed to REVIEW, not dropped**: whether a structurally clean sentence actually addresses a
  TypeScript reader ("Supports conversion from SQLAlchemy CardModel instances" trips nothing) is
  not statically decidable, and now carries a `ui/README.md` blind-spot row saying so.

## Deferred from: code review of c3-1 (2026-07-31)

- **A `pydantic.ValidationError` escaping `DeckRepository` has no handler anywhere in the companion
  stack, and `GET /api/decks` gives it a whole-list blast radius.** `install_error_handling` types
  `CompanionError`, `RequestValidationError`, `DatabaseError` and `HTTPException`; a
  `ValidationError` raised inside `Deck.model_validate` matches none of them and lands in
  `UnhandledErrorMiddleware` as `500 internal_error`. Measured triggers, all live: an orphaned
  `deck_cards` row (FK enforcement is OFF, so `dc.card` is `None`), a stored `quantity` of `0` or
  negative (`DeckCard.validate_quantity` rejects `<1` on **read**, and only the repository *write*
  path enforces it), and `tags`/`color_identity` holding well-formed JSON whose elements are not
  strings (`[1,2]`, `["W",null]`). On the detail route the deck is permanently unopenable; on the
  **list** route one bad row in one deck makes *every* deck unreachable.
  **Pre-existing, not introduced here** — this is the same crash already ledgered as the
  `data-layer-orphan-handling` backlog item (epic-7 retro action item 3), which names
  `get_deck_with_cards` and the four MCP tools that share it. c3-1 adds a web surface to it and one
  new fact: the list-route blast radius. **Not fixed here** because AC 12 forbids error-handling
  ceremony in a route body and the fix belongs at the data layer for both shells at once.
  **Home: `data-layer-orphan-handling`** (already in `sprint-status.yaml`, status `backlog`) — this
  entry adds the blast-radius finding and the two non-orphan triggers to its scope.
  (Severity: Medium — needs a corrupted row to fire, but degrades ungracefully when it does.)

- **Both new routes can answer `503 database_not_initialized`, and the OpenAPI document says only
  `database_unavailable`.** `build_app()`'s app-level `error_responses("invalid_request",
  "payload_too_large", "database_unavailable", "internal_error")` never passes
  `database_not_initialized`, so the committed schema's `503` on `/api/decks` and
  `/api/deck/{deck_id}` reads `"description": "reason: database_unavailable"` — while
  `TestDatabaseStates` asserts the *undocumented* token six times. On a fresh install this is the
  **most common** 503 the UI will ever see. `error_responses`' own docstring advertises the
  collapse behaviour ("tokens sharing a status ... a single entry whose description names each of
  them") and it has never fired. **Not fixed unilaterally**: AC 5 explicitly says "do not add
  `database_not_initialized` app-wide as a side effect of this story", and declaring it per-route
  deviates from AC 6's text. **Flagged to Brad as a decision** — see the story's Review section.
  **Home: c3-9** (the fresh-install story, which owns this state end to end) unless ruled sooner.
  (Severity: Medium — the wire contract under-documents the state the UI most needs to switch on.)

  **RE-CONFIRMED at c3-2 (2026-07-31), now on a THIRD route.** `GET /api/cards/{card_id}` answers
  the undocumented token too, asserted twice in `test_routes_cards.py::TestDatabaseStates`, and
  c3-2's AC 6 repeats c3-1's constraint ("`build_app()`'s app-level `responses` is **unchanged**"),
  so it was again not fixed unilaterally. Every data route added from here inherits the gap by
  construction — it is a property of `get_session`, not of any route — so the count will keep
  rising until c3-9 rules on it. ~~Severity stands at Medium.~~
  **RULED AND CLOSED, c3-9 (Q4, 2026-08-02): DECLARE IT.** `build_app()` now passes
  `database_not_initialized` to the database-backed includes (`decks`, `cards`) and to those only.
  Five operations changed in the committed schema — `/api/decks`, `/api/deck/{deck_id}`,
  `/api/deck/{deck_id}/format-check`, `/api/cards/{card_id}`, `/api/card-image/{scryfall_id}` —
  each `503` description going from `"reason: database_unavailable"` to
  `"reason: database_not_initialized | database_unavailable"`. **`error_responses`' documented
  collapse fired for the first time**: both tokens share status 503 and land in ONE entry naming
  each, a behaviour advertised in that helper's docstring since c1-4 and never before exercised.
  `/health` and both active-deck operations are byte-identical and deliberately so — neither can
  answer the token, and widening a declaration a route cannot honour turns an inherited wart into
  a fresh lie. Both artifacts were regenerated together via `npm run gen:api` and never
  hand-edited; the whole-artifact pins live in
  `tests/unit/companion/test_committed_schema.py::TestTheDatabaseTokensAreDeclared`, which also
  pins `/health`'s narrower set and the active-deck routes' absence of any 503 so that "left
  alone" is a decision rather than an oversight.

- **`DeckSummary.from_deck` / `DeckDetail.from_deck` return zero counts, silently, for any `Deck`
  that was not eager-loaded.** `DeckModel.deck_cards` is `lazy="noload"`, so a `Deck` from
  `get_deck`, `find_deck_by_name` or `update_deck` arrives with `deck_cards == []` and the
  projection reports `0 / 0 / 0` with an empty `cards` list — measured: a 4-card deck reads
  `main=4 side=0 distinct=1` via `get_deck_with_cards` and `0 0 0` via `get_deck`. As module-private
  helpers in `deck_management.py` this trap had three known callers; as **public classmethods on a
  shared `src/data` schema** it is now reachable by every future story, and pairing it with the
  cheaper `get_deck()` yields an HTTP 200 describing a 60-card deck as empty. Mitigated here by
  documenting it in both constructors' `Args:` (naming which repository methods are safe), which is
  the honest floor; **the structural fix** is a `Deck`-side marker distinguishing "loaded and empty"
  from "never loaded" — e.g. `deck_cards: list[DeckCard] | None` — so `from_deck` can raise instead
  of guessing. That is a `src/data` schema change with MCP blast radius and needs its own story.
  **Home: unowned, ledgered.** The first consumer to pair a non-eager-loading repository method with
  `from_deck` is the one that needs it. (Severity: Medium — silent wrongness, no type error.)

- **`HEAD` on either new route answers `405 Allow: GET`.** Measured. FastAPI's `@router.get`
  registers `methods=["GET"]` only, and unlike Starlette's static-file handling it does not
  auto-add `HEAD`. RFC 9110 says a server SHOULD support `HEAD` wherever it supports `GET`, and
  `spa.py` already declares `GET, HEAD` for the static surface — so the API routes are the
  inconsistent ones. **Pre-existing convention, not a c3-1 regression**: `/health` uses the same
  decorator and behaves identically, so fixing it here would either leave the two inconsistent or
  silently change a c1-2 route. **Home: unowned, ledgered** — worth one decision covering every
  companion route at once (add `methods=["GET", "HEAD"]` to the routers, or record that the
  companion deliberately serves GET only). (Severity: Low — no known consumer sends HEAD.)

- **`get_session` holds a SQLite SHARED lock for the whole request, and this is the first route
  long enough for it to matter.** `is_database_initialized(session)` autobegins a transaction and
  `get_session` yields without commit or rollback, so the read lock is held from the readiness probe
  through every route query until the `async with` closes. There is no WAL pragma on the companion's
  engine. Combined with the `list_decks` over-fetch above, a `GET /api/decks` over a large
  collection blocks a concurrent `initialize_database` writer — which is exactly the concurrency
  FR-22 presumes ("a database created while the backend runs is picked up with no restart").
  ~~**Home: c3-9** (which owns the fresh-install/coming-alive transition) or **c10-3** (latency
  hardening), whichever reaches it first.~~ **MEASURED AND RE-HOMED ON c10-3, c3-9 (Q7,
  2026-08-02)** — a re-home with a number attached, which is worth more than a fix without one.
  Measured against a real running companion serving `GET /api/decks` (~0.16-0.31 s per request,
  the over-fetch above), with a writer taking `BEGIN IMMEDIATE` five times, quiet and then under
  four saturating reader threads:

  | Journal mode | writer QUIET (median / max) | writer CONTENDED (median / max) |
  | --- | --- | --- |
  | `wal` | 0.0097 s / 0.0125 s | **0.0080 s / 0.0092 s** (no effect at all) |
  | `delete` | 0.0079 s / 0.0093 s | 0.0079 s / **0.2131 s** (one read's worth of wait) |

  Three findings, and the second is the one nobody had written down:

  1. **The companion's engine genuinely has no WAL pragma** — `src/data/database.py`'s
     `create_engine` sets only `connect_args={"timeout": 5}`. Confirmed.
  2. **WAL is a PERSISTENT file property, and something else sets it.**
     `src/search/connection.py:136` (the sync `ConnectionFactory`, for sqlite-vec) runs
     `PRAGMA journal_mode=WAL`, so any database this project has built an embedding index over is
     WAL forever and the companion inherits it without asking. The shipped 250 MB `cards.db` on
     this machine reads `wal`.
  3. **But a freshly created one does not.** Measured directly: a database created by
     `src/data/database.init_database` reads `journal_mode: delete`. So the FRESH-INSTALL case —
     exactly the one FR-22 is about — is the non-WAL row of that table.

  **It still does not bite, and the reason is arithmetic rather than luck.** The worst measured
  effect is a single 0.21 s wait on one write, under four threads saturating the endpoint, absorbed
  by a 5 s busy timeout that is 20x larger. This story's poll issues ONE request every 2-30 s, not
  four continuously — so a writer meets an in-flight read for a small fraction of wall-clock, and
  the wait it inherits is one read. Adding a WAL pragma to the companion's engine is still the
  right eventual fix (NFR-02 calls for WAL reads and it would make the fresh-install case match the
  post-index case), but it is latency hardening rather than an FR-22 failure. **Home: c10-3**, with
  the numbers above. (Severity: Low-Medium -> **Low**, measured.)

- **The `Attributes:` sections in the four wire-facing schemas hold prose, not attributes, and
  nothing says why.** `src/data/schemas/deck.py` (`DeckCardSummary`, `DeckSummary`, `DeckDetail`)
  and `src/data/schemas/card.py` (`CardSummary`) use `Attributes:` purely as a truncation marker,
  because `_CompanionFastAPI.openapi()` cuts every description at the first Google-style header
  (AC 17's suggested mechanism). Two consequences worth knowing: a napoleon/Sphinx render of these
  four classes now emits a malformed attribute list; and — the one that bites — **the shared core's
  docstring *structure* is load-bearing for a companion-only rule that `src/data` never mentions**.
  `test_openapi_contract.py` bans the literal markers from crossing the wire, i.e. it gates the
  *marker*, not the prose, so an editor who removes a header that plainly documents no attributes
  silently republishes "keeping `load_deck` payloads small for LLM clients" into `/docs` and
  `types.d.ts` with no gate going red. **Home: c3-2**, which will do the same thing to `Card` and
  should decide the convention for all of them (a `Note:`-style marker that reads honestly, an
  explicit comment in `src/data`, or a gate keyed on the prose). (Severity: Low.)

  **RESOLVED at c3-2, 2026-07-31 — Q5: keep the convention, state why it is load-bearing.** The
  `Attributes:` header stays (it works, and c3-1 used it four times), was applied to `Card`, and
  the sharpest edge is now closed by the middle option: **`src/data/schemas/card.py`'s MODULE
  docstring** carries an explicit statement that the first paragraph of every class docstring is
  published to the outside world, that the header position is the truncation marker, that a header
  documenting no attributes is still load-bearing, and that **no gate goes red** if it is deleted.
  Chosen over a gate on the prose (not decidable — see the entry above) and over renaming the
  marker (would churn four already-shipped schemas and both generated files for a cosmetic gain).

- **`ui/README.md`'s "What the gates cannot see" index is keyed on line numbers with nothing keeping
  it accurate.** Twenty-one `file:line` references across nine test files; all verified correct at
  the time of writing (17 spot-checked by the Acceptance Auditor, 8 by the Blind Hunter, all
  resolving). But the section is written as a durable index a reviewer consults instead of reading
  fourteen test files, and the first comment inserted near the top of `token-usage.test.ts`
  invalidates every reference below it. Every other load-bearing claim in that README is gated; this
  one is not. **Fix shape**: anchor on a searchable marker string (the guard function name, or the
  declared-limit sentence itself) rather than a line number, and add a test that every cited anchor
  still resolves. **Home: unowned, ledgered** — cheap to do, and the next story to add a row is the
  natural one. (Severity: Low-Medium — a stale index is worse than no index, because it is trusted.)

- **`tests/unit/companion/test_spa.py`'s completeness now rests on a hand-synchronised router
  list.** The two schema pins that hardcoded `{"/health"}` were repaired (see the c3-1 story record,
  finding 4), and the differential test `test_the_schema_is_unchanged_by_installing_the_mount` now
  builds a mount-free app that must mirror `build_app()`'s routers by hand. Every future
  router-adding story (c5-2, c5-5 — **not** c3-2/c3-3/c3-4/c3-5 if their routes join an existing
  router; see the correction below, which supersedes the original list) must add one line there or get a red.
  That is deliberate and the code says so — a forgotten line is a cheap named failure, versus a
  mount silently swallowing a route — but it *is* a standing tax, and it is the opposite of the
  repair's stated motive ("a hardcoded set makes every story that adds a route edit a SPA test for
  no reason"). **Recorded so it is a decision, not a drift.** If it becomes annoying, the fix is to
  derive the router list from `build_app()` itself rather than restating it. **Home: unowned.**
  (Severity: Low.)
  **Correction (c3-3, 2026-08-01): the story list above is wrong, and the tax is narrower than
  stated.** The tax falls on adding a **router**, not on adding a **route**. Both sides of the
  differential build their path sets from the same router objects, so a new path on an
  already-listed router appears on both and needs no line. Measured, not reasoned: c3-3 added
  `/api/deck/{deck_id}/format-check` to the existing decks router and `test_spa.py` passed
  unedited — **56 passed**. So c3-3 never owed a line, and neither will c3-4/c3-5 if their routes
  join an existing router. The comment in `test_spa.py` now says this, so the next author does not
  go looking for an edit they do not owe.

## Deferred from: code review of c3-1-deck-list-and-deck-detail-endpoints (2026-07-31, post-commit pass)

- **`from_deck` on a non-eager-loaded `Deck` silently yields 0/0/0 counts and an empty `cards`** —
  re-confirmed by the post-commit review as the sharpest edge the projection move created:
  `DeckModel.deck_cards` is `lazy="noload"`, so a `Deck` from `get_deck` / `find_deck_by_name` /
  `update_deck` feeds the public constructors an HTTP-200-shaped lie, guarded only by a docstring
  caveat. Already ledgered "unowned" by the story; this pass names a home candidate: the keyed
  `data-layer-orphan-handling` story (sprint-status.yaml), which already owns the sibling
  get_deck_with_cards ValidationError crash. (Severity: Medium if a future caller mis-sources;
  no current caller does.)

- **Generated-type optionality asymmetry: `strategy?: string | null` vs `format: string | null`,
  plus `@default 0` advertised on the count fields** — the server always serializes every field, so
  the `?` (a Python-default artifact) forces the UI into a spurious `undefined` branch, and the
  documented `0` default is exactly the silently-wrong value AC 3 exists to catch, now presented on
  the wire as normal. Pre-existing schema shape; this story merely put it on the wire. **Home:
  c4-1/c4-2**, the first real consumers of these types. (Severity: Low.)

  **Not triggered at c4-1 (2026-08-02); the whole entry is c4-2's.** c4-1 consumed `Card`,
  `CardSummary` and `DeckCardSummary` and hit neither half: no `strategy`, no `format` and none of
  the three count fields appears on any of them — they live on `DeckSummary` / `DeckDetail`, and
  c4-1 deliberately did not alias `DeckDetail`, having no consumer for it. **Home: c4-2**,
  unshared, which reads exactly those fields when it renders the deck header.

- **`_is_ref_rooted` will misfire on the first legitimate union response model.**
  **✅ RESOLVED at c3-3 (2026-08-01, Q5 — Brad took this half of the question).**
  `tests/unit/companion/test_errors.py` puts `anyOf`/`oneOf`/`allOf` in `_OBJECT_SHAPE_KEYS`, so a
  future `response_model=X | None` — plausibly c3-3's "no format to check against" answer —
  generates a top-level `anyOf` and is refused as a "hand-built envelope", which it is not: the
  guard's family conflates *object-shaping* with *union-forming*. Two smaller 3.1 edges in the same
  helper: a `$ref` carrying legal sibling annotation keys fails `set(schema) == {"$ref"}` (false
  red), and `prefixItems` is absent from the key set (false green for a tuple-shaped array). Fix
  shape when it fires: admit a union whose every branch is itself ref-rooted or `{"type": "null"}`,
  and add `prefixItems` to the object-shape keys — extending the family, not enumerating members.
  **Home: c3-3**, the first story likely to hit it; until then the failure is a red test with a
  misleading message, not a shipped defect. (Severity: Low.)
  **Resolution**: all three edges fixed exactly as the fix shape describes. `anyOf`/`oneOf` moved
  out of `_OBJECT_SHAPE_KEYS` into a new `_UNION_KEYS`, with a union admitted only when **every**
  branch is itself ref-rooted or the bare null type; `prefixItems` added to the object-shape keys;
  and a `$ref` now tolerates annotation-only siblings via a named `_ANNOTATION_KEYS` set. Ten new
  rows in the helper's own accept/reject table, including the three ways the union arm could have
  become a hole — one inline branch among refs, an all-scalar union, and an **empty** `anyOf`
  (`all([])` is `True`, which is how a vacuous guard is born). Note the fix shipped *before*
  anything needed it: c3-3's own response is one shape in every case by ruling (Q4), so no union
  crosses the wire yet. Taken anyway, because the alternative was leaving the next story a red
  test whose message named the wrong problem.

- **`format: string | null` on the wire is unreachable at the data layer — `decks.format` is a
  `NOT NULL` column.** Measured while writing the review's null-metadata test:
  `create_deck(format=None)` raises `IntegrityError` (`NOT NULL constraint failed: decks.format`),
  so the `null` half of the generated type can never be served from a repository-written deck. The
  c3-1 story's own gotcha ("a deck can genuinely have no format, and c3-3's 'no format to check
  against' response depends on it") is therefore half-false as stated: the *schema* allows null,
  the *database* forbids it. **Home: c3-3**, which must decide whether "no format to check
  against" is keyed on a null format (then the column constraint is the bug) or on an
  unrecognised format string (then the wire type is merely wider than the data and can stay).
  (Severity: Low-Medium — a UI `format === null` branch written against the generated type is
  dead code today.)
  **✅ RESOLVED at c3-3 (2026-08-01, Q4 — Brad ruled "as proposed").** The wire type is merely
  wider than the data, and it stays. "No format to check against" is keyed on the validator's
  existing `unknown_format` outcome, which already covers an unrecognised **or empty** format
  string and already refuses to flag every card illegal — so no schema change, no migration and no
  new mechanism. `format_check` coalesces a null format to `""`, which lands in the same branch;
  the report carries `format: ""` and `format_recognized: false`, and its legality and banned rows
  go `advisory`. Re-verified at c3-3 before ruling: the column is still `NOT NULL` and **0 of 40**
  rows are null or blank. **Re-homed residue: c4-10** writes the UI's "no format" branch, and if it
  writes `format === null` against the generated type that branch is dead code — it should key on
  `format_recognized` instead, which c3-3 added for exactly this.

## Deferred from: story c3-2 (2026-07-31)

- **There is no price data anywhere in this project, and FR-17's "prices if present in local data"
  is therefore never satisfied.** Measured at c3-2: `PRAGMA table_info(cards)` lists 23 columns and
  none of them is a price; `Card` and `CardSummary` declare no price field; a case-insensitive grep
  for `price` across `src/`, `tests/`, `ui/src` and `scripts/` returns **one** hit, a forward-looking
  comment in `StatChip.css` about a future micro-role — no column, no field, no importer path, no UI
  consumer. (The c3-2 story text claimed *zero* hits over those roots; the one CSS-comment hit is
  the correction, and it changes nothing about the conclusion.) The 2026-07-11 PRD recon recorded
  the same absence ("ABSENT: game_changer, edhrec_rank, saltiness, prices"). The epic's price AC is
  therefore satisfied **by absence**, ruled by Brad at Q4, and `GET /api/cards/{card_id}` ships **no
  price field** rather than a `prices: null` that would be null on 100% of responses — a permanently
  dead branch c4-5 would have to handle for nothing. **What adding prices would actually cost**: a
  new `cards` column (or a side table, since Scryfall prices are per-printing and volatile), an
  `import_scryfall_data.py` change to populate it, a hand-written migration script (this project has
  no Alembic), a full re-import of 38,261 rows, plus a staleness story — Scryfall prices change
  daily and a locally cached price with no fetched-at timestamp is a number that lies. **Home:
  c4-5**, the card detail panel — it is the only surface `EXPERIENCE.md` promises prices on
  (`:86`, "Prices render only when present in local data"), so it is the story that must either
  render nothing there deliberately or raise the import work as its own brief. (AC 15 asks for a
  *named* home; "unowned" was the first draft and the review was right to call it.) The artefact
  already reads correctly against absence, so nothing is broken today. (Severity: Low.)

- **`503` outranks `400`: a malformed card id sent to a backend with no database answers
  `database_not_initialized`, not `invalid_request`.** Measured at c3-2 (the test asserting the
  opposite failed, and the assertion — not the code — was wrong). FastAPI's `solve_dependencies`
  solves sub-dependencies *and* collects parameter-validation errors in one pass, raising
  `RequestValidationError` only after the dependencies have run; `get_session`'s `CompanionError`
  therefore propagates first. Both outcomes are now pinned in `test_routes_cards.py`. Defensible —
  the backend genuinely cannot serve the request for a reason that outranks the client's spelling —
  but **invisible from the route source**, and it matters to two named stories: **c3-9** polls the
  503 states and **c4-1** owns the fetch layer, and a UI that treats `database_unavailable` /
  `database_not_initialized` as "retry quietly" will retry a request whose id can never succeed.
  ~~**Home: c3-9**, which owns the polling and the transition.~~ **CLOSED, c3-9 (2026-08-02),
  and closed structurally rather than carefully.** The one route c3-9 polls, `GET /api/decks`, has
  **no path parameter**, so there is no id to be malformed and no `503` it sees can be masking a
  `400`. That is asserted rather than merely written down — `decks.test.ts` pins
  `DECKS_PATH` free of `{`, `}` and `:`, because the safety argument evaporates the moment somebody
  parameterises the constant, which is exactly what **c4-1** will be tempted to do when it copies
  this module for `GET /api/cards/{card_id}`. The warning for c4-1 is written in three places it
  will actually read: `ui/src/api/decks.ts`'s header, that assertion's comment, and `ui/README.md`'s
  *"Not here yet"* section. **c4-1's per-card fetches are NOT immune and need a bound on attempts
  per id.** (Severity: Low-Medium.)

- **`card_faces` crosses the wire completely untyped.** `Card.card_faces` is
  `list[dict[str, Any]] | None`, generating `{ [key: string]: unknown }[] | null` — no per-face
  contract at all, so a consumer reading `face.image_uris.normal` gets no help from the compiler.
  Deliberately not fixed here: typing untyped Scryfall JSON would be a second shape over data this
  project does not control, and it would land on the MCP tools too. Measured face-count histogram
  (real corpus): **2 → 3,222 cards · 3 → 2 · 5 → 1** — so a `[front, back]` destructuring is wrong
  for three real cards. **Home: c4-6**, the DFC flip control, which is the story that actually needs
  a face contract. (Severity: Low.)

- **79 cards carry no image data anywhere — the first concrete population for the Card placeholder.**
  Measured: of 38,261 rows, 2,857 have a JSON-null `image_uris`; 2,778 of those carry per-face
  `image_uris` inside `card_faces` instead; **zero** carry both; **79 carry neither**. `c3-2` proves
  all three shapes round-trip with the nulls surviving as `null`. `EXPERIENCE.md`'s "Card with no
  image data | Any surface | Named Card placeholder (FR-19)" row has, until now, had no measured
  population. **Home: c4-3**, which owns the placeholder — and which now knows the unknown-card
  variant and the no-image variant are different populations reached by different routes (a 404
  token versus a 200 with null images). (Severity: Low.)

  > **RESOLVED at c4-3 (2026-08-04) — the 79 re-verified, and their SHAPE measured for the first
  > time.** Re-counted read-only against the live DB: 38,261 rows, **79** with no image data
  > anywhere. What this entry did not know is what those 79 LOOK like, and it changes the layout
  > the placeholder had to survive: **all 79 have `type_line` exactly `'Card // Card'`**, **all 79
  > have a BLANK `mana_cost`**, and **all 79 have a doubled `X // X` name** (longest 66 chars,
  > `Asmoranomardicadaistinaculdacar // Asmoranomardicadaistinaculdacar`). So UX-DR22's three-part
  > composition degrades, MEASURED, to a name and nothing else for every card that permanently
  > needs this variant — which is not a reason to change the design but is why AC 7 is about being
  > correct when two of three parts are empty. Two of the 79 are now fixtures in
  > `CardPlaceholder.test.tsx`. **And 0 of 2,027 live deck rows are such a printing**, so in a deck
  > view the named placeholder is only ever reached transiently, through `image_fetch_failed`.

- **The `states.ts` classification of panel-less tokens is gated by the compiler but read by
  nothing.** c3-2 added `PLACEHOLDER_FOR_REASON`, `NO_UI_RESPONSE` and three type-level asserts so
  the third meaning of `null` is machine-readable rather than a comment (Q3, satisfying retro R1).
  Three asserts prove every panel-less token is classified as exactly one of {placeholder, nothing}
  and that nothing with a panel is classified — but **no runtime code consumes any of it yet**, the
  same declared state `PANEL_FOR_REASON` itself has been in since c2-9. **Home: c4-3** (the
  placeholder render) and **c3-9** (the panel wiring). If neither consumes it, that is a signal the
  structure was over-built and it should be deleted rather than maintained.
  **HALF CLOSED, c3-9 (2026-08-02).** The PANEL half is consumed: `panelFor` reads
  `PANEL_FOR_REASON` and, notably, uses its key set as the runtime membership test for
  `ErrorReason` — so the map is load-bearing twice over and cannot be deleted without inventing a
  second list. The CLASSIFICATION half — `PLACEHOLDER_FOR_REASON`, `NO_UI_RESPONSE` and the three
  type-level asserts — is still consumed by nothing, and **stays c4-3's**, stated explicitly here
  because this entry's own text makes non-consumption a delete signal and c3-9 was one of its two
  named consumers. c3-9 does read the `null`s, but only to clamp them: a panel-less token on a
  whole-screen poll means a client bug, so it renders `internal-error` rather than consulting which
  KIND of `null` it was. **If c4-3 does not consume the classification, delete it.**
  (Severity: Low.)

  > **✅ CLOSED at c4-3 (2026-08-04): the classification is CONSUMED, not deleted.** This entry
  > made the delete conditional and c4-3 is the condition, so the answer is stated plainly.
  > `src/components/CardPlaceholder/CardPlaceholder.tsx` imports `PlaceholderKey` (type-only) and
  > builds its variant union FROM it — `PlaceholderKey | 'loading'` — and the coupling is enforced
  > in BOTH directions by two type-level asserts in the component: `EveryPlaceholderKeyHasProps`
  > fails if a third key is added to `states.ts` with no props member, and `NoVariantIsUnknownToStates`
  > fails if the union is widened to a bare `string` (the evasion the first assert alone would pass,
  > because every key still has a member). Both were PROBED: probes (d) and (g) of c4-3 are `tsc`
  > failures with `npm test` staying green — the c4-1 asymmetry again, and why `npx tsc -b --force`
  > is a gate of its own. `PLACEHOLDER_FOR_REASON` also gets a RUNTIME consumer, in
  > `CardPlaceholder.test.tsx`, which renders every variant its values name rather than trusting
  > the type. **Nothing in `states.ts` was edited to make consumption work**, which was the design
  > smell this entry was watching for. `NO_UI_RESPONSE` remains consumed by nothing at runtime and
  > stays where c3-9 left it.

- **`ui/README.md`'s blind-spot map now carries the "does this prose address a TypeScript reader"
  residue, which is a REVIEW obligation with no gate.** Added at c3-2 alongside the family-keyed
  wire-prose gate. It inherits the pre-existing weakness recorded above at c3-1 — the index is keyed
  on line numbers with nothing keeping them accurate. **Home: c3-3**, the next story to add a
  schema to `components.schemas` and therefore the next to owe this review pass; it is also the
  natural point to anchor the README's citations on marker strings rather than line numbers, as
  the c3-1 entry proposes. (Severity: Low.)
  **⛔ DECLINED at c3-3 (2026-08-01, Q5 — Brad took the `_is_ref_rooted` half of the question and
  left this one).** c3-3 *did* pay the review-pass half: it added its blind-spot row and, after
  the adversarial review found that row under-declared its own guard's holes, rewrote it to
  enumerate five families and three declared limits. The **re-anchoring** was not done.
  Re-ledgered in the c3-3 section below as "Home: unowned" — see *"`ui/README.md`'s blind-spot
  map is still keyed on line numbers"*. Do not read this entry's `Home: c3-3` as outstanding
  work against a completed story.

- **A `ui/tests/` file may import an app module only if that module has no relative imports of its
  own — and the failure is reported at the wrong place.** Measured at c3-2. `tsconfig.node.json`
  owns `tests/**/*.ts` with `module: nodenext` (extension required on relative imports);
  `tsconfig.app.json` owns `src` with `moduleResolution: bundler` (extension forbidden). Importing
  `states.ts` from `ui/tests/unknown-card-copy.test.ts` pulled it into the node project, where its
  own extensionless `../../api/schema` and `./copy` imports became `TS2835` — and then **cascaded**:
  `ErrorReason` failed to resolve, and all three of `states.ts`'s type-level asserts collapsed to
  `Type 'false' does not satisfy the constraint 'true'`, pointing at the asserts rather than at the
  import. `copy.test.ts` gets away with importing `copy.ts` only because that module happens to have
  no relative imports; that is a property of the module, not a general permission. **Two aggravating
  factors**: `npm test` stays fully green throughout (vitest resolves fine — this is a `tsc`-only
  failure), and `tsc -b` is incremental, so the error can hide behind a cached build until an
  unrelated later run surfaces it. `npx tsc -b --force` is what makes it deterministic.
  **Fix shapes**, none taken here: add explicit extensions in `states.ts` (breaks the app project's
  convention), exclude `src` from the node project's graph, or keep the current workaround — a
  source read, with the runtime value pinned in the app-project test beside the module.
  ~~**Home: c4-1**, the first story that will want to import real app modules into `ui/tests` at any
  scale (a fetch layer is exactly the thing whose tests reach across).~~ Until then the workaround
  is documented in `unknown-card-copy.test.ts` and in `ui/README.md`'s blind-spot map.
  (Severity: Medium — the symptom points at the wrong file, and CI runs `tsc -b` without
  `--force`, so a cached-clean result can ship.)

  **NOT TRIGGERED at c4-1 (2026-08-02) — re-homed by name, with the reason.** The prediction was
  reasonable and it did not hold: c4-1's fetch layer and cache are tested **inside the app
  project** (`src/api/client.test.ts`, `src/state/cards.test.ts`), which is where AC 24 puts them —
  jsdom, no configuration, no cross-project import. What c4-1 added under `ui/tests/` is a change
  to `posture.test.ts`'s door list, and that guard reads source as **text** via
  `readFileSync` + `git ls-files`; it imports no app module and therefore cannot trip the cascade.
  `npx tsc -b --force` was run and is green, so this is a measured "did not fire", not an
  assumption. **Home: the first story that actually imports a real `src/` module into `ui/tests/`.**
  Nothing in C4 obviously does — the epic's remaining guards are file-reading guards of the same
  shape — so the realistic candidate is **c5-1**'s event envelope or whichever story first wants a
  runtime value from `src/` inside a node-project test. (Severity: unchanged, Medium.)

  > **✅ TRIGGERED AND CLOSED at c4-3 (2026-08-04) — by the story c4-1 said probably would not.**
  > `tests/unknown-card-copy.test.ts` now imports a real `src/` module: `UNKNOWN_CARD_LABEL` from
  > `src/components/CardPlaceholder/copy.ts`, so the shipped label can be asserted BYTE-FOR-BYTE
  > against `EXPERIENCE.md` — the assertion that file has promised since c3-2 would land "the day
  > c4-3 lands". **It does not fire, and the rule is now stated precisely rather than
  > approximately.** The constraint was never "a `ui/tests` file may not import an app module"; it
  > is **"may not import an app module that has RELATIVE imports of its own"**, because those are
  > what `nodenext` demands extensions for. `copy.ts` has `imports: []` — pinned exhaustively by
  > `shell.test.ts`'s `PRIMITIVES`, so an import added there is a red test before it is a `tsc`
  > cascade — which is the same property `copy.test.ts` relies on for `StatePanel/copy.ts`, and it
  > is now a property two guards protect rather than a coincidence. **`npx tsc -b --force` was run
  > and is green**, so this is a measured "did not fire". The MEDIUM half of the entry stands
  > unchanged and un-fixed: the symptom still points at the wrong file, and CI still runs `tsc -b`
  > without `--force`. **Home for the fix shapes: unchanged.**



## Deferred from: code review of c3-2 (2026-07-31)

- **A malformed card id reaching the UI from DATA renders nothing at all — no placeholder, no
  state.** `card_not_found` is the token wired to the unknown-card placeholder; a card id that
  fails the route's shape gate produces `invalid_request`, which `states.ts` classifies as
  `NO_UI_RESPONSE` — "nothing on the glass, anywhere". Those two answers are one character of
  input apart. `deck_cards.card_id` carries no shape constraint, FK enforcement is off on the async
  engine (`CardRepository.get_by_id`'s own docstring says so), and the planned Arena
  `arena_card_map` work will introduce ids from a second source. Measured today: **0 of 2,027
  `deck_cards` rows are non-canonical**, so this is latent, not live — but it is not structurally
  prevented, and the failure mode is the exact one FR-13 exists to stop ("one unknown card must
  never fail a whole view") wearing a different token. **Fix shape**: either the hydration layer
  treats a 400 on a card fetch as a placeholder case, or the id shape is validated where deck rows
  are read. ~~**Home: c4-1** (the hydration cache) with **c4-3** (the placeholder) as its consumer.~~
  (Severity: Medium if it ever fires, Low probability today.)

  **✅ RESOLVED at c4-1 (2026-08-02, Q5) — and closed on BOTH fix shapes, not one.** The ruling:
  **a `400 invalid_request` on a per-card read IS the unknown-card case.**
  `PLACEHOLDER_FOR_CARD_REFUSAL` in `src/state/cards.ts` maps it to `states.ts`'s own
  `'unknown-card'` `PlaceholderKey`, beside `card_not_found`, whose value is read OUT of
  `PLACEHOLDER_FOR_REASON` rather than re-typed. The argument, written in the code: `states.ts`
  classifies that token `NO_UI_RESPONSE` on the premise *"the SPA never generates a malformed
  request"*, and that premise is **exactly what fails here** — an id the app cannot render is an id
  the app cannot render, whichever token says so. `states.ts` is untouched, because the
  destination is context-dependent rather than a property of the token, and adding
  `invalid_request` to `PLACEHOLDER_FOR_REASON` would break `ReasonClassificationsAreDisjoint`.
  The second fix shape landed too: `cardPath()` runs the id through `encodeURIComponent`, so an id
  carrying `/`, `?` or `#` can no longer change WHICH route is addressed — it stays one path
  segment and the route's uuid pattern refuses it. Both halves are test-pinned. ~~**c4-3 renders the
  placeholder**; the token and the destination are waiting for it.~~
  **✅ THE RENDER ARRIVED at c4-3 (2026-08-04).** `CardPlaceholder variant="unknown-card"` draws the
  label and the truncated id, and `CardPlaceholder.test.tsx` drives the whole path for real —
  `hydrateCard` with an injected reader returning `card_not_found`, then the rendered placeholder
  read out of the DOM. The consumer branches on `entry.placeholder`, never on `entry.reason`, so
  the c4-1 ruling is what selects the variant rather than a second map in a component. **This
  entry is fully closed: token, destination and render.**

- **`Card` is now a banned type name across all of `ui/`, and there is no sanctioned alias to
  import instead.** `wire-contract.test.ts` derives its ban from `components.schemas`, so `Card`
  joined it automatically at c3-2 — correct, and the mechanism working as designed. But
  `ui/src/api/schema.ts` re-exports only `HealthResponse`, `ErrorResponse` and `ErrorReason`; it
  exports no `Card` and no deck aliases either. So the first component that needs the card type
  (c4-3, c4-5) hits a ban with no signposted alternative, and the obvious local workaround —
  declaring a local `interface Card` — is precisely what the gate rejects. **Fix shape**: add the
  aliases to `schema.ts` in the story that first needs them (one line each; the barrel is the
  sanctioned single reader). Not done here because c3-2 ships no component and an unused export
  would be dead code. ~~**Home: c4-1**, the first frontend story to consume a wire shape.~~
  (Severity: Low — a five-minute detour, but an unsignposted one.)

  **✅ RESOLVED at c4-1 (2026-08-02).** `src/api/schema.ts` now exports **seven** aliases:
  `HealthResponse`, `ErrorResponse`, `DeckSummary`, `ErrorReason` and — new here — `Card`,
  `CardSummary` and `DeckCardSummary`, each with a docstring naming its consumer (`readCard`, the
  cache's `hydrated` tier; the cache's `summary` tier; `seedCardSummaries`, which **c4-2** calls).
  **`CardFace` and `DeckDetail` were deliberately NOT added**: nothing in this commit consumes
  them, and c3-2's own reason for declining — an unused export is dead code — applies to c4-1
  exactly as it applied to c3-2. c4-2 adds `DeckDetail` when its fetch needs it; whichever story
  renders a flip control (**c4-6**) adds `CardFace`. `ui/README.md:154` claimed three aliases when
  four already shipped; corrected in the same commit.

- **`GET /api/cards/{card_id}` sets no cache headers on a resource that is immutable between
  database refreshes.** `cards.py`'s module docstring claims c3-5's image route shares "the same
  cache story"; today there is no cache story on this side to share. No `ETag`, no
  `Cache-Control`, no conditional-request handling — while `spa.py` has a whole
  `_apply_cache_headers` mechanism for static files. A c4-x deck view hydrating 60–100 cards
  re-fetches every full record on every render. Low impact today (localhost, SQLite, one user),
  and deliberately not fixed in a story whose scope is one lookup. ~~**Home: c3-7** (the sharded
  disk cache) or **c4-1** (the hydration cache), whichever lands first~~ — **c3-7 landed first and
  answered it (Brad, Q1's sub-question, 2026-08-01): it CORRECTED the docstring rather than
  implementing the shared story.** The reasoning is that "the same cache story" was never one
  story: a card row's cache story is `ETag`/conditional requests over a database read, which
  shares nothing with a file on disk but the word, and implementing it inside c3-7 would have been
  a second mechanism smuggled in under a docstring's phrasing. `cards.py`'s module docstring now
  says so explicitly, in the past tense, so the sentence cannot be read as a live claim again.
  ~~**The route still sets no cache headers, and that half stays homed on c4-1** beside the
  hydration cache it belongs with.~~ (Severity: Low. **Status: half closed** — the false claim is
  gone.)

  **RE-HOMED at c4-1 (2026-08-02, Q7) — declined here, with the measurement that makes it a
  decision rather than a dodge.** The theory this was homed on was that the hydration cache is the
  layer that makes the missing headers moot, and **measured, that theory holds**: the cache issues
  **one request per id per tab** and never re-requests a hydrated id, so the population an `ETag`
  would serve is *page reloads*, not renders. The entry's own worst case — *"a c4-x deck view
  hydrating 60–100 cards re-fetches every full record on every render"* — is now structurally
  impossible, and the sentence is superseded rather than merely unfixed. Two further facts: the
  client sends `cache: 'no-store'` on card reads (deliberately, so that a header-less response
  cannot be heuristically cached into staleness across a database refresh), which would make an
  `ETag` inert until that decision were revisited; and implementing it would be a **backend** change
  in a story whose whole product is a store slice, making AC 27's "the Python side is unchanged"
  false for no measured gain. **Home: the C4 retrospective**, which is where "close this as
  superseded, or do it with the cache in view" should actually be decided — the epic's twelve
  stories are the ones that will have exercised the cache on real decks by then.
  (Severity: Low, and lower than when it was written.)

- **`test_openapi_contract._descriptions()` does not mirror the truncator's `_DATA_KEYS` skip.**
  `without_python_docstring_sections` deliberately does not descend into `example`/`examples`/
  `default`/`const`/`enum` subtrees, because a `description` key there is payload data reproduced
  byte-for-byte. `_descriptions` descends everywhere. Measured: **zero** descriptions under a data
  key in the committed schema today, so nothing fires. The first example payload carrying a
  `description` whose value contains a colon-terminated line makes the family scan an
  **unsatisfiable red** — its message says "fix at the Python docstring" and there is no docstring
  to fix. **Fix shape**: give `_descriptions` the same `_DATA_KEYS` skip, ideally by importing the
  constant rather than re-declaring it. **Home: c5-1**, the first story expected to add example
  payloads (the event-envelope union). (Severity: Low, latent.)

## Deferred from: code review of c3-2-card-detail-endpoint, round 2 (2026-07-31)

- **A body-less GET publishes `413 payload_too_large` in its client contract.** The app-wide
  `error_responses` wiring from `build_app()` lands the 413 row on `GET /api/cards/{card_id}`
  (and the deck GETs before it), so the generated contract tells c4-1's fetch layer to handle a
  response the same document describes as "surfaced to the *agent*… The glass never sees it."
  Pre-existing, inherited, and doubled by every new GET route. **Fix shape**: either curate the
  app-wide set per-method (drop 413 from body-less GETs at declaration time) or record it as a
  known wart in the contract docs. ~~**Home: the next story that touches `error_responses`'s
  declaration helper**, else c3-9.~~ **RULED, c3-9 (Q8, 2026-08-02): RECORDED AND RE-HOMED ON
  c5-5.** c3-9 declined to curate per method. The reason is scope with blast radius, stated so it
  can be argued with: Q4 touched the *caller* (`build_app`'s per-include sets), not the helper, so
  the trigger condition in this entry was never actually met; and changing `error_responses`'
  per-status grouping into per-method curation is a real change to a shared declaration site with
  six routes downstream, made in a story whose frontend half is already the largest in the epic.
  It is now written down as a known wart in `scripts/dump_openapi.py` — the contract-docs home —
  with the consequence spelled out for a client author (*a 413 on a body-less GET is unreachable;
  ignore it*). **Home: c5-5**, which adds the ingest cap, makes the 413 real, and cannot avoid
  deciding which operations answer it. (Severity: Low.)

- **The image-discriminator prose is maintained by hand in two Python docstrings with no drift
  gate between them.** The same three paragraphs (split-card trap, per-face `image_uris`
  mutual-exclusivity, no-image-is-ordinary) live in `routes/cards.py`'s route docstring and
  `src/data/schemas/card.py`'s `Card` docstring, and regenerate into two places in the wire
  document. The byte-drift gates check Python↔generated only — a future correction applied to one
  docstring leaves the other confidently wrong on the same `openapi.json`. **Fix shape**: single
  source (one docstring states the rule, the other points at it), or a gate asserting the two
  descriptions agree on the discriminator sentence. **Home: c3-5**, which re-tells this rule for
  the image route and will make it three copies if unaddressed. (Severity: Low.)
  **RESOLVED by c3-5 (Q6, Brad 2026-08-01) — both halves of the fix shape, not one.** The rule is
  now the single constant `IMAGE_DISCRIMINATOR` in `src/data/schemas/card.py`, attached as the
  `description=` of `Card.image_uris`, `Card.card_faces` and `CardFace.image_uris`; both route
  docstrings state only what their own operation does and point at the fields. The gate is
  `test_committed_schema.py::TestTheImageDiscriminatorIsStatedOnce`, keyed on the **family** — any
  wire description mentioning both "per-face" and "image_uris" must *be* the constant, so a
  reworded fourth copy fails rather than a missing one. It caught the author's own `CardFace` class
  docstring on its first run, which is the guard working before review saw it.

- **`card_faces` is untyped on the wire — the discriminator rule has no `tsc` support.**
  `Card.card_faces` is `list[dict[str, Any]] | None`, generating `{ [key: string]: unknown }[] |
  null` in `types.d.ts`, while four docstrings teach "decide by the presence of per-face
  `image_uris`". Every face access in the UI will be a hand-cast `tsc` cannot check. Ruled at the
  c3-2 round-2 review (Brad, 2026-07-31): the wire schema stays frozen as reviewed with PR #30
  open. **Fix shape**: a typed `CardFace` Pydantic model (`name`, `mana_cost`, `type_line`,
  `oracle_text`, `image_uris`), regenerated into the component set (pins move 7→8, now **9→10**
  after c3-3). **Home: c3-5 or c4-3, whichever consumes a face first** — and it must land with the
  regenerated types in the same commit. (Severity: Medium for c4-3's type safety, zero runtime
  impact today.)
  **RESOLVED by c3-5 (Q4, Brad 2026-08-01), with two consequences the entry did not price.**
  `CardFace` ships with `model_config = ConfigDict(extra="allow")` — a strict model would have
  truncated `lookup_card_by_name`'s output for 6,455 face objects carrying 24 distinct keys, and
  `tests/unit/data/test_card_face_schema.py` proves the round-trip loses no key and changes no
  value (plus a counterfactual showing a strict model *does* truncate). Components 11 → 12; the
  generated type is an intersection with an open index signature, so c4-3 gets both the named
  fields and the unnamed ones. The two unpriced consequences: (1) five call sites outside the
  companion read faces with `.get(...)` and `mypy --strict` forced them to attribute access —
  `classifiers.py`, `mana_base.py` ×2 and `view_model.py` ×2, the last inside `src/viewer`, which
  c3-5's story text listed as not-touched; (2) named fields are now always serialised, so a face
  that omitted one carries an explicit `null` where it previously omitted the key. Additive, never
  a truncation — and it made "presence of per-face `image_uris`" mean *truthiness* everywhere,
  which three assertions in `test_routes_cards.py` were updated to say.

## Deferred from: story c3-3 (format check endpoint, 2026-08-01)

- **Rotation exposure cannot be computed from local data at all, and the panel now says so
  permanently.** Q3 (Brad, 2026-07-31) ruled that the row ships with status `advisory` rather than
  being omitted, so the gap is visible instead of silent — but it is a row a user can never
  resolve. Measured read-only against the shipped 38,261-card database, not assumed:
  `PRAGMA table_info(cards)` returns **23 columns** and none is a release date (`released_at`
  absent, `set_type` absent); `sqlite_master` contains **no sets table** of any kind; and
  `src/data/importers/aggregate.py:113-134` **does** read `released_at` — to pick the canonical
  printing by greatest date, ties by min id — and then discards it without ever writing a column.
  **Fix shape, priced honestly**: a `released_at` (or `set_type`) column on `cards` *or* a new
  sets table; an importer change to persist it; a hand-written `scripts/migrate_*.py` (this
  project has no Alembic); a full re-import of ~38k cards; **and** a rotation-schedule source —
  Scryfall's bulk data does not say "this set rotates in 2027-09", so the schedule has to come
  from somewhere else or be hard-coded and maintained. That is comfortably its own story.
  **Home: unowned** — a dedicated data story, not a companion one. Until it exists, the advisory
  row is the honest answer and must not be quietly promoted to `pass`. (Severity: Low — a
  permanent shrug in a P0 panel, but an accurate one.)

- **A `restricted` card is reported as "not legal", which is wrong.** `deck_validator.py`'s
  legality branch splits `banned` off (c3-3, Q2) but leaves `restricted` falling through to
  `format_legality`, so a Vintage deck running one Black Lotus is told the card is not legal in
  vintage when it is legal with a **1-copy limit**. Deliberately unchanged by the split and
  pinned by `test_deck_validator.py::test_restricted_is_unchanged_by_the_banned_split` so a later
  change is a decision rather than a side effect. Latent today: measured 89 `restricted` legality
  entries corpus-wide (vintage 51 · duel 24 · tlr 10 · timeless 4) and **zero** restricted cards
  across all 40 real saved decks, with no vintage deck among them. **Fix shape**: a per-card copy
  limit that varies by legality value — which is a change to the copy-limit rule, not to the
  legality branch, and needs its own row vocabulary decision (does a restricted card over its
  limit report `copy_limit`, or a new `restricted` rule?). **Home: unowned** — its own story.
  (Severity: Low while no vintage deck exists; Medium the day one does.)

- **`_MIN_MAINBOARD = 60` applies regardless of format, and c3-3 published that to a human for the
  first time.** A deliberately documented Phase-1 limitation (D-1.6b) that until now was reported
  only to an agent, which could caveat it. The format-check panel renders the size row directly,
  so a Commander deck is now told on the glass that 60 cards satisfies a format that wants 100.
  Measured: brawl and standardbrawl are genuinely 60-card formats, so the **20** brawl-family
  decks in the real deck table are correct and only Commander is affected — and there are
  currently **0** commander decks saved, which is why nothing looks wrong today. **Fix shape**: a
  per-format minimum (a dict beside `_SINGLETON_FORMATS`, keyed the same way), plus the
  "any number of copies" exemption cards the same scope note defers. **Home: unowned** — a
  `src/logic` rule story. (Severity: Low today, Medium the first time a Commander deck is saved.)

- **The component-name set is pinned in TWO hand-synchronised places, and the story text named
  one.** `tests/unit/companion/test_routes_decks.py` and `test_routes_cards.py` each assert the
  exact `components.schemas` key set, so every schema-adding story edits both. c3-2's Debug Log
  recorded finding the second one by running the suite rather than by reading the story; **c3-3
  hit exactly the same thing again** — its own "must not break" list named the decks pin and not
  the cards pin. Twice is a pattern, not bad luck. **Fix shape**: one pin, in one place, imported
  by both — or a single `test_committed_schema.py` that owns every whole-artifact assertion and
  leaves the per-route files asserting only their own paths. **Home: c3-4**, the next
  schema-adding story, which will otherwise inherit the same surprise a third time.
  (Severity: Low — it fails loudly and names the fix.)
  → **CLOSED by c3-4 (Q5, Brad 2026-08-01).** It did inherit the surprise a third time — both pins
  went red together on regeneration — and then took the fix as written: the second fix shape.
  `tests/unit/companion/test_committed_schema.py` now owns the whole-artifact path set, component
  set, auto-422 absence and `securitySchemes` absence; `test_routes_decks.py` and
  `test_routes_cards.py` assert only that their **own** shapes are present. c3-5 edits one pin.

- **`ui/README.md`'s blind-spot map is still keyed on line numbers.** Homed on c3-3 by name and
  **declined by Brad at Q5 (2026-07-31)**, who took the `_is_ref_rooted` repair from the same
  question and left this one. Unchanged in substance from the c3-1 entry that raised it: the
  section is written as a durable index a reviewer consults instead of reading fourteen test
  files, and the first comment inserted near the top of a cited file invalidates every reference
  below it. c3-3 added its row keyed the existing way, so the map is one entry larger and no more
  durable. **Fix shape** (unchanged): anchor on a searchable marker string — the guard function
  name, or the declared-limit sentence itself — rather than a line number, and add a test that
  every cited anchor still resolves. **Home: unowned, re-ledgered.** Twice deferred now; a third
  story owing this README a review pass is the natural moment. (Severity: Low-Medium — a stale
  index is worse than no index, because it is trusted.)

- **`format_recognized` and the six-row shape are declared but unread until c4-10.** c3-3 ships a
  boolean the UI can branch on for "no format to check against" rather than making c4-10 parse
  the advisory row's prose, and a `CHECK_ORDER` a panel can rely on. No runtime code consumes
  either yet — the same declared-but-unread state c3-2's `states.ts` classification is in.
  **Home: c4-10** (the format check panel). If c4-10 renders the panel without ever reading
  `format_recognized`, that is a signal the field was over-built and it should be deleted rather
  than maintained. (Severity: Low.)

- **`format_recognized: true` does not mean the format key is present in the card data.**
  `_KNOWN_FORMATS` is a hand-maintained frozenset in source; `legalities` comes from a separately
  imported database. If the two skew — `_KNOWN_FORMATS` updated for a new Scryfall format ahead of
  a user's re-import, which the upgrade notes acknowledge users defer — every card misses the key,
  `.get()` returns `None`, and every card is reported not legal. That is the exact "legality
  storm" `_KNOWN_FORMATS` was introduced to prevent, now rendered as a confident panel with
  `format_recognized: true` and no advisory. **Not reachable against a synchronised snapshot**:
  measured 2026-08-01, all 38,261 cards carry all 23 keys, and `set(keys) == _KNOWN_FORMATS`
  exactly. A second edge in the same area: a *present-but-null* legality value
  (`{"standard": null}`) fails `Card` validation — `legalities: dict[str, str]` coerces only a
  wholly-null dict — so the route answers `500 internal_error` rather than a report. **Fix shape**:
  derive the known-format set from the data (a `SELECT DISTINCT` over the keys) instead of
  hard-coding it, or gate `format_recognized` on the key being present in at least one card.
  **Home: unowned** — it belongs with whatever story next touches `_KNOWN_FORMATS`.
  (Severity: Low today, Medium on version skew.)

- **The format-check report's `format` is the normalised value; the deck detail route's is the
  stored one.** `GET /api/deck/{id}` serves `deck.format` verbatim while
  `GET /api/deck/{id}/format-check` serves `format.strip().lower()`, because the report should
  name what was actually checked. Latent: measured **0 of 40** real decks store a format that
  differs from its own normalisation, so the two endpoints agree on every deck that exists today.
  A UI comparing the two strings would nonetheless be comparing two different things. **Fix
  shape**: either normalise at write time in `create_deck` (making the divergence impossible), or
  document the asymmetry where c4-1's store holds both. **Home: c4-10 or c4-1**, whichever first
  holds both values at once. (Severity: Low.)

## Deferred from: code review of c3-3-format-check-endpoint-over-the-existing-validators (round 2, 2026-08-01)

- **`is_legal: false` above six non-violation rows is a live UI trap, mitigated only by prose.**
  The report deliberately carries no honest headline field (Q4: one shape always, mirrors the
  validator); a renderer must synthesize the verdict from `format_recognized` plus a row scan,
  guided only by the `Warning:` docstring block on the wire. Nothing machine-checkable stops
  c4-10 from binding `is_legal` straight to the panel headline — a formatless deck would then
  render a red headline over six rows none of which is a violation. **Home: c4-10** (the format
  check panel), plus a named line on the epic C3 manual-testing checklist. (Severity: Low here,
  Medium if c4-10 binds it unread.)

- **The copy-limit row answers definitively under the 4-copy fallback for a format it cannot
  interpret.** Greptile P1 on PR #31, ruled ledger-not-fix (Brad, 2026-08-01). For an
  unrecognized format (`edh`, `explorer`), `validate_deck` falls back to the ordinary 4-copy
  rule — an unknown key is never in `_SINGLETON_FORMATS`, pinned by `TestFormatSetInvariant` —
  and `format_check` renders that as a definitive `copy_limit` pass/violation, though the format
  the user *meant* may be singleton (edh → commander caps at 1). Mitigations already on the wire:
  the same report carries an `unknown_format` violation, `format_recognized: false`,
  `is_legal: false`, and advisory legality/banned rows, so the panel is loudly not-a-verdict.
  **Fix shape**: when `format_recognized` is false, the copy_limit row goes advisory like
  legality/banned ("could not be checked against an unrecognized format") — a one-branch change
  in `format_check` plus its firing/silent pair. **Home: the same unowned `src/logic` rule story
  as the per-format-minimum entry above** — the two are one "format-aware structural rules"
  decision. (Severity: Low — reachable only by a deck whose stored format is invalid, and the
  report already refuses to be a verdict.)

## From story c3-4 (the active deck), 2026-08-01

- **No pre-parse request-body cap anywhere in the app.** Measured at c3-4 Task 0 against the
  installed FastAPI **0.140.0**: `get_request_handler`'s inner `app(request)` reads and parses the
  body at `fastapi/routing.py:423-448` and calls `solve_dependencies` at `:473` — **body first,
  dependencies second**. So c3-4's agent-token dependency does *not* stop an unauthenticated caller
  from making the process buffer an arbitrarily large body on `PUT /api/active-deck`. What c3-4
  shipped instead is a **field** constraint (`ActiveDeckRequest.deck_id`, `max_length=256`), which
  is honest about being applied *after* parsing and bounds only what is stored. Q4 weighed building
  the real cap here and declined: it is a middleware-shaped mechanism, it would be designed against
  one story's requirements in a story whose body is ~40 bytes, and it should be **one** mechanism
  covering both endpoints. Mitigations that genuinely exist today and are worth not re-deriving:
  the `Host` envelope refuses anything that did not address the app as loopback on the bound port,
  and the app installs **no CORS middleware at all** (C1's no-CORS ruling), so a cross-origin `PUT`
  with a JSON content type is preflighted, the `OPTIONS` gets a `405`, and the browser never sends
  the body. **Home: c5-5**, which owns `payload_too_large` — a token declared since c1-4 that still
  has **no producer** — and AD-7's 64 KB envelope limit. (Severity: Low — a loopback port behind
  `Host` validation, reachable only by local software that could do worse directly. But "the first
  endpoint with a body shipped with no thought about body size" is a sentence worth never writing.)

- **There is no way to clear the active deck over the wire.** `ActiveDeckRequest.deck_id` is
  required and does not accept `null`, so the only transitions are *set* and *process restart*
  (Q3 part 3, Brad 2026-08-01). Nothing in the epic asks for a clear verb: FR-11's "deck deleted →
  no-active-deck" is a **client-side** transition (`EXPERIENCE.md:120` — the refetch 404s and the
  SPA clears to the panel), and a restart clears the slot anyway. Building an unused verb now would
  freeze a wire shape with no consumer. **Home: unowned** — whichever story first has a *caller*
  that needs it, most plausibly c6-2 if the tool ever grows a "stop displaying" mode. **The shape
  it should take if wanted**: a `DELETE /api/active-deck`, not a nullable request field — the
  request model staying non-null is what keeps `PUT` unambiguous. (Severity: Low.)

- **Nothing broadcasts the change.** `PUT /api/active-deck` stores and returns; no hook, callback
  registry or placeholder was built for the notification, deliberately (an unused hook is a design
  decision made by a story that cannot see the requirements). **Home: c5-4**, which adds one call
  after the store, to a handler that will exist — the insertion point is marked by a comment in
  `set_active_deck`. The value it broadcasts is the same `ActiveDeck` shape the two operations
  already answer with, which is why Q3 chose `200`-with-body over `204`. (Severity: none — this is
  a named seam, not a gap.)

- **`errors.supported_methods` walks framework internals to repair the `Allow` header.** c3-4
  found that Starlette 0.48.0 builds a 405's `Allow` from the **first** partially-matching route
  alone (`routing.py:738` keeps `partial` only if it is `None`; `Route.handle` at `:283` joins
  *that* route's methods), so `/api/active-deck` — the first path in this app served by more than
  one method — answered `Allow: GET`, omitting the `PUT`. RFC 9110 §15.5.6 requires the field to
  list the *resource's* methods, so this was wrong and not merely terse. The repair recomputes the
  union, which needs a flattened route list, and FastAPI 0.140 does **not** flatten included routers
  into `app.routes` — it stores lazy `_IncludedRouter` wrappers. `_leaf_routes` therefore walks
  `original_router`/`routes` **by attribute**, so an upstream structural change degrades to "found
  nothing" and the caller keeps Starlette's own header rather than raising inside an error handler.
  That is a deliberate soft failure, and it means **a FastAPI upgrade could silently restore the
  incomplete header**. `test_routes_active_deck.py::TestTheMethodSemantics` is what would catch it.
  **Home: unowned** — revisit if FastAPI ever exposes a public flattened route list, or if a third
  multi-method path appears. (Severity: Low — the failure mode is a less-informative header, never
  a wrong status or a leaked body.)
  **Second hole, found at review (2026-08-01):** the flattened children are matched against the
  **un-stripped** scope, and Starlette strips a mount's prefix into `child_scope` before children
  match — so the walk is correct only while every mount sits at `/`, which is true today and
  asserted by nothing. A future non-root `Mount` (c5-x static assets, an `/agent` sub-app) makes
  children silently never match (or a child at `/` match paths it does not serve). Different hole
  from the soft failure above: that one finds no leaves; this one finds them and asks the wrong
  question. Documented in `supported_methods`'s docstring. **Home: the story that adds a non-root
  mount.** (Severity: Low — latent until such a mount exists.)

- **A third pin on `NO_UI_RESPONSE` was not in c3-4's ripple table.** The story's landmine-12 table
  named seven ripple sites for an eighth reason token and listed two frontend pins on the
  panel-less classification (`states.ts`'s `satisfies` clause and `states.test.ts:60`'s exact
  array). There is a **third**: `ui/tests/unknown-card-copy.test.ts` parses `states.ts`'s source and
  asserts `noUiResponseMembers()` equals the exact list, as a non-vacuity anchor for its own
  card_not_found pin. It went red on `forbidden` and was edited by name. Not a defect — the pin is
  correct and caught a real omission — but the **count** is folklore that a story text got wrong,
  which is exactly the shape c3-2's "a true count read as a false rule" lesson warns about.
  **Fix shape**: nothing to build; the next story adding a reason token should grep for
  `NO_UI_RESPONSE` rather than trusting any enumerated list, and the comment added at that line now
  says so. **Home: unowned, informational.** (Severity: Low — it fails loudly and names itself.)

## Deferred from: code review of c3-4 (2026-08-01)

- **The pre-auth body-buffering deferral now has a test pinning the ordering.** The c5-5 body-cap
  entry above stands, with one addendum the review surfaced: `test_routes_active_deck.py::
  test_a_malformed_body_without_a_credential_is_still_forbidden` pins that FastAPI parses the body
  *before* solving the credential dependency (400-vs-403 is observable unauthenticated). c5-5's cap
  must consciously decide whether that pin is a contract or a snapshot — a middleware-level cap
  changes the observable order and would red the pin. **Home: c5-5.** (Severity: Low on loopback;
  it is also a free validation oracle for unauthenticated callers until the cap lands.)
- **A future hand-raised 405's deliberate headers are overridden or case-split by the `Allow`
  recompute.** `errors.py`'s 405 branch replaces any author-supplied `Allow` with the
  partial-match union — which, for a request that *fully* matched the raising route, excludes that
  route's own method — and a case-mismatched `"allow"` key survives the `{**headers, "Allow": …}`
  merge as a second header. Unreachable today: no code raises 405 manually. **Home: unowned,
  ledgered** — the first story that hand-raises a 405 owns it. (Severity: Low — latent.)

## Deferred from: story c3-6 (the image pacer, 2026-08-01)

- **The epic's CM-2 acceptance criterion is not satisfied by c3-6 and is not paraphrased into
  something adjacent.** *"An image fetched once is not fetched again within the cache lifetime"*
  (epic :1728-1730) is the **disk cache**. There is no cache in c3-6, so a repeat request repeats
  the fetch — the pacer changes the *rate* of fetches, never their *number*. Recorded in
  `images.py`'s module docstring and in the story record as well as here, because an unsatisfiable
  claim gets an owner rather than a rewording. ~~**Home: c3-7.**~~ **CLOSED by c3-7, 2026-08-01.**
  `images.DiskCache` ships and `test_routes_card_image.py::TestARepeatRequestMakesNoCdnRequest`
  asserts it on `Recorder.requested` — one recorded URL for two requests — rather than on a second
  `200`, which c3-1's R1 finding showed passes with the mechanism deleted. Two things the entry
  did not price, both now measured: the warm path also had to skip the **pacer** (a cache checked
  inside `pacer.slot()` satisfies CM-2 and still takes 9.9 s to paint a warm deck), which is
  asserted on c3-6's injected clock as **98 spacing intervals cold, zero warm**; and the claim
  needed a **file on disk** asserted beside the fetch count, because a route that answered twice
  from one in-memory value would satisfy the fetch count alone. (Severity: Medium → **resolved**.)

- **In-flight coalescing is declined on ownership, not on merit** (Q5, Brad 2026-08-01). Two
  *simultaneous* requests for the same URL each get their own fetch; a semaphore does not prevent
  that shape and ~15 lines would. Declined because the thing being shared is a **result**, and
  whether that result is bytes, a disk path or a `Future` depends entirely on what c3-7 builds —
  building an in-flight map here means c3-7 inherits a second cache or deletes one (c3-4's ruling:
  *an unused hook is a design decision made by a story that cannot see the requirements*).
  **Measured cost today: zero extra fetches** on both 99-distinct-id decks, because duplicate
  printings collapse in `deck_cards` before they reach the route. **The trigger that flips this
  answer is c6-4** — suggestion rows beside the deck grid are the first surface that would render
  the same card id twice on one screen. ~~**Home: c3-7**~~ — **c3-7 DECLINED IT AGAIN and re-homed
  it on c3-8** (Q5, Brad 2026-08-01), **and the reason changed**, which is the part worth
  recording. c3-6 declined it for not knowing the result's shape; c3-7 built that shape (bytes on
  disk) and declined it anyway, because **c3-8 needs the same structure for a different question**
  — *"is a fetch for this key already in flight, or already known-failed?"* — so an in-flight map
  built here for successes only would be inherited wrong or replaced. One mechanism, built once,
  by the story that can see both halves. What declining costs, stated rather than glossed: two
  simultaneous requests for one key both fetch and both write, and on Windows the loser's
  `os.replace` raises `PermissionError` — **observed live** during c3-7's implementation, when a
  99-request burst over one id logged exactly that, and it is a log line rather than a failed
  request (c3-7 AC 9). ~~**Home: c3-8**~~ — **c3-8 DECLINED IT A THIRD TIME and re-homed it on
  c6-4** (Q6, Brad 2026-08-02), **and the reason changed AGAIN — this time because its predecessor's
  reason did not survive contact.** c3-7 re-homed it here on the expectation that *"c3-8 needs the
  same structure for a different question — is a fetch for this key already in flight, or already
  known-failed?"*. **It does not.** A negative cache needs no in-flight state to be correct: a
  request whose fetch is in flight simply also fetches, and the failure is recorded when it fails.
  Nothing in c3-8's AC 4-11 asks otherwise, and the shipped mechanism has no in-flight concept at
  all. *"Is a fetch already in flight"* was c3-7's phrasing of a hypothetical, not a requirement of
  anything. What coalescing actually shares is a **124 KB payload across two awaiting requests** —
  a `Future` holding bytes, with a cancelled leader and an exception fanned out to followers, each
  needing its own tests — which is a **different mechanism** from a small expiring failure record,
  not the same one. So the "one mechanism, built once, by the story that can see both halves"
  argument dissolves: there were never two halves. **Home: c6-4**, unchanged as the forcing
  function and now the sole owner. Recorded plainly because three consecutive declines is a pattern
  worth a human's eye: c3-6 declined for not knowing the result's shape, c3-7 because the shape was
  shared with c3-8's, and c3-8 because that sharing turned out not to be real. If c6-4 also
  declines it, the entry should be closed as "not wanted" rather than moved a fourth time.
  (Severity: Low today; Medium at c6-4.)

- **The `DbSession` is held across the pacer's queue wait, and it works by arithmetic rather than
  by design** (Q6, Brad 2026-08-01 — accept, pin, ledger). **Measured, not assumed** (Task 0):
  FastAPI runs a `yield`-dependency's teardown *after* the endpoint returns, so the pool reports
  `checkedout() == 1` while `fetch_image` is awaited and `0` after the response. The pool is
  SQLAlchemy's default `AsyncAdaptedQueuePool`, **size 5 + overflow 10 = 15 connections,
  `pool_timeout` 30 s** — all four values read off the live pool object. At the shipped constants a
  99-tile burst drains in ~9.9 s, so at most 15 requests sit inside the route and the rest wait
  outside it: a second queue in front of the first, inefficient and harmless. **A pacer slower than
  roughly 0.3 s per tile would push the burst past the 30 s pool timeout**, raising
  `sqlalchemy.exc.TimeoutError` — which is **not** a `DatabaseError` and would therefore surface as
  `500 internal_error`, **not** `503`. Pinned by
  `test_routes_card_image.py::TestTheBurstDoesNotOutlastTheConnectionPool` so a later story that
  slows the pacer sees the cliff. The clean fix is to read the row, release the session, *then*
  queue — rejected here because it takes this one route off `DbSession`, the annotation c3-1…c3-5
  standardised on, for a problem that does not bite at these constants. ~~**Home: c4-1**, beside the
  hydration cache, which already carries this route's whole-row-read entry.~~ (Severity: Low at the
  shipped constants; High for whichever story changes them without reading this.)

  **RE-HOMED at c4-1 (2026-08-02, Q7) → c4-4.** This is a property of the **image** route's pacer
  and connection pool, and c4-1 touches neither: it ships a store slice and a JSON reader, adds no
  Python, and issues **no image request at all** (art reaches the screen through `<img>` and the
  browser's HTTP cache — there is no `fetch` for image bytes in `ui/src`). Homing it here on
  "beside the hydration cache" was a filing convenience, not a technical relationship. The story
  that will actually produce the burst this entry describes is **c4-4, the card-art grid** — the
  first surface that mounts ~99 `<img src="/api/card-image/…">` at once and therefore the first
  thing that can push the pacer queue past the pool timeout. **Home: c4-4**, and it should be read
  before that story changes any pacer constant.

- **`4` was declared out of c3-3's deck-construction-limit family, and that is a ruling made by
  c3-6 rather than a discovery.** `TestNoRuleInTheShell` bans the literals `60`/`15`/`4` anywhere
  in `src/companion`; `images.FETCH_CONCURRENCY = 4` is a CDN concurrency cap with no deck
  vocabulary near it, and the guard flagged it — **a structural pin this story did not name, the
  third consecutive story to hit one** (c3-2 Debug Log 3, c3-3 finding 2). The alternative was
  renaming a ruled production constant to appease a guard, which is precisely the obfuscation that
  guard's own docstring says to treat as a violation. `4` therefore joins `1` and the adjacent
  spellings (`3`, `5`, `16`) that were **already** declared out on exactly the ubiquity argument
  that applies to it; keeping it in was the order of discovery, not a stance. The copy limit stays
  covered by the `.quantity` family (enforcing it means counting copies). **Residual hole, stated:**
  a shell that counts copies without reading `quantity` — `len(rows) > 4`. **Home: unowned,
  ledgered**; declared in `ui/README.md`'s blind-spot table and probed in both directions.
  (Severity: Low — same class as the four holes the guard already declares.)

- **Both halves of the "never blocks the loop" AC that c3-6 could not satisfy have owners.** The
  epic's AC (`:1723-1726`) names a concurrent push through **`POST /agent/events`** meeting its
  250 ms budget while images are queued; **that endpoint does not exist until c5-1/c5-5**. c3-6
  proves the property against `/health` — five interleaved probes completing while every image
  fetch is parked upstream, with the *count* asserted so a serialised loop fails it — and records
  the substitution rather than passing it off as the same test. The literal AC is **c10-3's**,
  whose own AC (`:3580-3582`) already says exactly that. Likewise the **real-bytes and
  real-latency** half of the cold-deck observation: c3-6 asserts ~9.8 s of modelled start offsets
  on an injected clock and states the 12 MB as arithmetic on a measured 124 KB average; measuring
  actual bytes over an actual network is **c10-3's** (`:3588-3590`). **Home: c10-3** (both).
  (Severity: Low — deliberate scope, both named in the epic already.)

- **No ceiling on how long a request may queue, and no wire vocabulary for one** (Q4, Brad
  2026-08-01). The natural bound is the caller: a client that disconnects cancels the request and
  releases its slot immediately (pinned two ways). A ceiling would need either a **new reason
  token** — eight ripple sites, for a state no consumer can act on differently from
  `image_fetch_failed` — or a false reuse of the transient one. The fallback if a real queue ever
  misbehaves is to answer `image_fetch_failed` after N seconds queued, which only becomes
  meaningful once **c3-8** owns the retry semantics that would make a caller do something different
  with it. ~~**Home: c3-8**, if ever.~~ **DECLINED by c3-8, 2026-08-02 (Q7, Brad) — and the "if
  ever" now has a real argument against it rather than an absence of one.** The entry's own
  condition was met: c3-8 owns the retry semantics. The answer got *clearer* rather than closer.
  A queue ceiling would answer `image_fetch_failed` for a request that **never reached the CDN** —
  and the negative cache would then remember that non-event for 30 seconds, escalating on repeats.
  So a queue that is merely *long* would start **manufacturing remembered failures**, blanking
  tiles over congestion the CDN had no part in, which is strictly worse than the queue it was
  meant to bound. That is a new argument the entry did not have, and it is why this is recorded as
  a reason rather than as another "no measured symptom". The natural bound remains the caller: a
  client that disconnects cancels the request and releases its slot, pinned two ways. Written into
  `images.py`'s module docstring. **Home: none — closed on the merits.** Reopen only if a real
  queue misbehaves, and note that any reopening must also decide how the ceiling avoids poisoning
  the negative cache. (Severity: closed.)

## Deferred from: story c3-5 (card image endpoint, 2026-08-01)

- ~~**Between this story and c3-6 the image route fetches unpaced.**~~ **RESOLVED 2026-08-01 by
  c3-6.** `images.Pacer` ships: one semaphore (`FETCH_CONCURRENCY = 4`) plus request spacing
  (`FETCH_SPACING_SECONDS = 0.1`), constructed in the lifespan beside the client and passed to
  `fetch_image` as a **required** parameter, so no signature exists that fetches unpaced. The
  window was never reached by a browser — nothing under `ui/src` fetches an image until c4-4.
  The exemption this entry banked was carried through as instructed and is now written into the
  spacing constant's own docstring, gated by a test: the numbers are a good-citizen and NFR-05
  choice, **not** compliance with guidance that exempts `*.scryfall.io`.
  **What the entry did not price**, and c3-6 found by measuring: (a) a "hundred-tile deck view" is
  **67–99 distinct fetches, not 100** — basic lands collapse, median ~78 across the 18 saved decks
  with ≥90 cards; (b) the epic's "~12 MB over ~10 s" is not an independent observation but the
  **same arithmetic** that names the spacing constant (99 × 0.1 s = 9.9 s; 12 MB / 99 ≈ 124 KB, a
  `normal` JPEG); and (c) the database connection pool is a **second, invisible choke point** in
  front of the first — see the new c3-6 entries below.

- **The file extension is not derivable from the size key.** Measured over 40,960 stored image
  maps: `png` resolves to a `.png` URL 40,957 times and to a **`.jpg`** three times (the
  `errors.scryfall.com/soon.jpg` placeholders on Sparkspitter, Ondu Champion and Gorehorn
  Minotaurs); every other size is `.jpg`. c3-7's cache filename (`<size>_<face>.<ext>`) must take
  `ext` from the **resolved URL or the response `Content-Type`**, never from the size name. c3-5
  writes no file, and its route already echoes the upstream `Content-Type` for the same reason.
  ~~**Home: c3-7.**~~ **CLOSED by c3-7, 2026-08-01.** `images.cache_extension(url, content_type)`
  takes the URL suffix first and the header second, and **cannot consult the size key because it is
  not given one** — the signature is the guard, pinned by a test. Re-measured independently at
  implementation time: 245,760 URLs, `png` → `.jpg` exactly **3** times, all three cards named.
  Two things the entry did not price: **a third extension had to be decided**, and the ruling is
  *serve it, do not cache it* — not a raise and emphatically not a guessed filename (c3-2's "a true
  count read as a false rule"); and the **read** needs the same map as a candidate list, because
  the key excludes the extension, so a reader does not know which spelling its own writer chose.
  (Severity: Medium → **resolved**.)

- **Every stored URL carries a `?<timestamp>` cache-buster, and AD-11's cache key excludes it.**
  245,742 of 245,742 URLs carry one. c3-5 sends the URL verbatim (stripping it 404s upstream) but
  the AD-11 cache key is id + size + face, so a data refresh that changes the URL still hits the
  same cache entry. AD-11 **accepts that staleness explicitly**; recorded so c3-7 does not
  "improve" it by keying on the URL, which would silently make every refresh a full cache miss.
  ~~**Home: c3-7.**~~ **CLOSED by c3-7, 2026-08-01 — it did not "improve" it.** The key is id +
  size + face and the accepted staleness is now **asserted** in two directions rather than
  described: a refreshed row carrying a new `?<timestamp>` hits the existing entry
  (`test_images.py`), and three different cards sharing one URL produce **three** entries and
  three fetches (`test_routes_card_image.py`). The second was the entry's real content and it was
  a *prediction* — the shipped `errors.scryfall.com` test was expected to pass **unchanged** under
  a correct key, and it did, which is what makes "the key is not the URL" a measurement rather
  than an intention. What the entry did not price: `IMAGE_CACHE_CONTROL`'s docstring was written
  in the forward tense about this key and had to become present tense, and it is now worth saying
  that **both** caches accept the same staleness for the same reason — which is what makes
  stacking a browser cache on a disk cache free. (Severity: Low → **resolved**.)

- ~~**A fetch failure is answered and forgotten.**~~ **CLOSED by c3-8, 2026-08-02 — this story's
  headline.** `images.NegativeCache` remembers a failed key for 30 s, doubling per consecutive
  failure to a 300 s ceiling, bounded at 2,048 entries, cleared entirely on recovery. The
  prediction that it needed **no schema change** was half right and was **measured rather than
  assumed**: no path, no component and no reason token changed (7 and 12, before and after), but
  regenerating did produce a diff, because the story edited `ErrorResponse`'s class docstring to
  describe the new behaviour and a Pydantic model's docstring is published in full. Both generated
  files were regenerated and committed. The UI half needed nothing — `named-card-copy.test.ts`
  passed **unchanged**, so `EXPERIENCE.md`'s forward-dated promise became true without either side
  being edited.

- **An image request reads the whole card row.** AD-1 is satisfied by writing no query at all —
  `CardRepository.get_by_id` returns the `Card` the sibling route already answers with — so an
  image request pays for oracle text, legalities and every other column to read one URL. Ledgered
  rather than optimised: a narrow projection would be the second card shape AD-1 exists to
  prevent. ~~**Home: c4-1**, beside the hydration cache, which is the layer that could make this
  free.~~ (Severity: Low — local SQLite, one row.)

  **RE-HOMED at c4-1 (2026-08-02, Q7) → c4-4.** The theory — that the hydration cache is the layer
  that could make this free — does **not** hold, and saying so is the honest move. The cache holds
  the JSON record from `GET /api/cards/{card_id}`; the wasted read is on `GET
  /api/card-image/{scryfall_id}`, a route c4-1 never calls and whose consumer is an `<img>` tag the
  browser drives. No amount of caching card ROWS in the SPA changes how the image route reads one.
  **Home: c4-4** (the card-art grid), the first story that issues these requests in bulk and
  therefore the first that could measure whether the whole-row read is worth a projection.

- **`HEAD` and `Range` are not supported on the image route.** `GET` only. A browser will not ask
  for either on an `<img>`, and nothing in the feature needs them; `HEAD` would additionally
  require deciding whether to fetch upstream to answer it (which would defeat the point of a cheap
  probe). Declined deliberately. **Home: unowned, informational** — the story that gives an image
  a download or share affordance owns it. (Severity: Low — latent.)

- **A distinct "no such face" token was declined.** An out-of-range `face` answers
  `404 no_image_data`, the same token as a card with no artwork at all. AD-11 asks for *permanent*
  and *transient* to be distinguishable, not for two flavours of permanent to be, and
  `EXPERIENCE.md` draws the same named-Card placeholder for both — so a third token would cost
  eight ripple sites to express a distinction no consumer acts on. The **precedence** AC 9 asks for
  is structural rather than ordered: a card with no images resolves to an empty list, so every face
  is out of range and one comparison answers both. **Home: unowned, ledgered** — revisit only if a
  client is ever built that would act differently on the two. (Severity: Low.)

- **A partially imaged card would shift face indices.** `resolve_face_images` returns only the
  faces that carry images, in face order, so a card with an unimaged face 0 and an imaged face 1
  would serve that image at `face=0`. **Zero such rows exist** (a card's faces either all carry
  images or none do, measured across 38,261 rows) and the return type cannot represent a hole. The
  behaviour is pinned by a test so it is a decision on the record. **Home: unowned, latent** — the
  story that meets a real partially-imaged card owns it. (Severity: Low — unreachable today.)

- **A missing size key answers `no_image_data`.** Unreachable against the shipped corpus: exactly
  one key-set exists across all 40,960 image maps (`small`, `normal`, `large`, `png`, `art_crop`,
  `border_crop` — all six, always, never a subset), so a present map always resolves the requested
  size. That is a **true count of this corpus, not a Scryfall guarantee** (c3-2's lesson), so it
  justifies the absence of a size-negotiation branch and is deliberately **not** published to the
  wire as a promise. **Home: unowned, informational.** (Severity: Low.)

- **The MCP tool status vocabulary and the companion `ErrorReason` vocabulary share spellings and
  are different contracts.** The c3-3 skills-tree grep was run for this story and found no stale
  prose: `.claude/skills/**` and `plugin/skills/**` mention `card_not_found` and `deck_not_found`
  only as **MCP tool `status` values**, which predate the wire contract and are unrelated to it;
  neither of c3-5's new tokens appears anywhere, and no skill documents the companion's HTTP error
  contract at all. Recorded because the collision is a trap for **c6-1**, which introduces MCP
  tools that *do* consume the HTTP tokens: the same two words will then mean two things in one
  skill file unless the tool's outcome vocabulary is named deliberately. **Home: c6-1.**
  (Severity: Low now, Medium at c6-1.)

- **`error_response` now stamps `Cache-Control: no-store` on every typed error, feature-wide.**
  Added by c3-5 because a route structurally cannot attach a header — the point of deriving the
  status from the token — and RFC 9111 §4.2.2 lets a cache store a 404 heuristically with no
  explicit freshness, which would turn one transient image failure into a permanently broken tile.
  Applied to every token rather than the two that motivated it, since no modelled failure in this
  app is worth re-serving from a cache. Recorded as a **behaviour change to a shared helper** so a
  later story that wants a cacheable error knows it must argue for it. **Home: unowned,
  informational.** (Severity: Low.)

## Deferred from: code review of c3-5-card-image-endpoint (2026-08-01)

- **A refused or unparseable *stored* image URL answers `image_fetch_failed` — the transient,
  retryable token — though the refusal is a permanent fact of the row.** `contracts.py` defines
  the token as "transient … only this one may ever be retried", and c3-8's backoff will act on
  that; a disallowed origin or an unparseable URL cannot succeed on any retry. Brad ruled (2a,
  2026-08-01): keep the token, no wire change — c3-8, which owns the negative cache and backoff,
  decides retry semantics for permanently-failing URLs (e.g. an unbounded/permanent negative-cache
  entry for `is_fetchable` refusals). ~~**Home: c3-8.**~~ **DECIDED by c3-8, 2026-08-02 (Q3,
  Brad): ONE UNIFORM POLICY — no permanent entries, and the decision is closed rather than
  deferred again.** Three reasons, in order of weight. (1) **The class is unreachable against this
  corpus, re-measured read-only at Task 0**: all **245,760** stored image URLs are on the two
  allow-listed hosts and every one is `https`, so **zero** would be refused — a permanent-entry
  branch would be c3-4's unused hook exactly. (2) `fetch_image` deliberately collapses all eight
  failure causes into one token; distinguishing here means either widening that closed contract or
  re-implementing `is_fetchable` at the call site, which is a second truth about which URLs are
  fetchable and the thing AD-1 exists to prevent. (3) The error is asymmetric — a permanent entry
  for a URL that was *not* permanently bad is a tile broken until restart, while a 300 s ceiling on
  one that *is* costs one request per five minutes against a host that answers instantly. The
  corpus measurement is the evidence and is recorded as a fact about *this* corpus today (c3-2's
  "a true count read as a false rule"); it justifies the absence of a branch and is **not**
  published as a wire promise. Written into `images.py`'s module docstring. (Severity: closed.)

## Deferred from: code review of c3-6-paced-concurrency-capped-cdn-fetching-at-one-global-choke-point (2026-08-01)

- **httpx's closed-client `RuntimeError` escapes `_fetch_checked`'s `except` tuple as a raw 500**
  (`src/companion/app/images.py:751`). A request still queued in the pacer when lifespan teardown
  closes `image_client` gets `RuntimeError("client has been closed")` from `client.stream`, which
  is not in `(TimeoutError, httpx.HTTPError, httpx.InvalidURL)` and so surfaces as an unhandled
  500 traceback rather than `image_fetch_failed`. The window pre-exists from c3-5 (any fetch in
  flight at teardown); c3-6's queue widens it by the queue wait (~10 s on a cold deck). Uvicorn's
  graceful drain covers the normal shutdown path, and catching `RuntimeError` wholesale would
  reclassify programming errors as fetch failures — so the fix wants a narrower discriminator
  (message match or a shutdown flag), decided by whichever story next touches teardown.
  **Home: unowned.** (Severity: Low.)
- **Two hand-synchronised stall-able CDN fakes** (`tests/unit/companion/test_images.py:588`
  `Upstream`; `tests/unit/companion/test_routes_card_image.py:889` `StallableCdn`) — near-identical
  recorders (requested / in_flight / peak_in_flight / release `asyncio.Event`) maintained in two
  files; the ledgered two-copies defect class (c3-2 Debug Log 3, c3-3 finding 2), this time in test
  scaffolding. Consolidate into `tests/unit/companion/conftest.py` when a third consumer appears —
  c3-7's disk cache and c3-8's negative cache both stall CDNs and are candidates.
  ~~**Home: c3-7.**~~ **CLOSED by c3-7, 2026-08-01 — it was the third consumer, as predicted.**
  Both classes are gone; `conftest.StallableUpstream` replaces them, with `FakeClock` moved
  alongside it so a test module can reach either without importing another test module. What the
  entry did not price: **the two fakes had already drifted**, which is the whole hazard rather
  than the duplication itself — one recorded start times off a virtual clock and had no
  `completed` counter, the other counted completions and had no clock. The merged class carries
  the union with the clock **optional**, so a test that does not care about time does not build
  one. It also had to change a default: `StallableCdn` held every request unconditionally while
  `Upstream` took `hold=`, so the consolidated class defaults to *releasing* and its one stalling
  fixture now asks for `hold=True` explicitly — caught by three reds on the first run, and worth
  naming because "same class, different default" is how a consolidation reintroduces the drift it
  removed. (Severity: Low → **resolved**.)


## Deferred from: story c3-7 (the sharded, atomically written disk cache, 2026-08-01)

- **The cache is unbounded: no eviction, no size accounting, no TTL, no index** (AD-11, epic
  :1768-1770 — deliberate in MVP, and no hook was built for a future one on c3-4's ruling). What
  c8-2 inherits is a **measured footprint rather than a guess**: this user's whole 40-deck library
  is **1,061 distinct card ids**, and a single deck resolves to **67–99** of them; at one size and
  the epic's ~124 KB average that is roughly **130 MB** for the entire library, ~12 MB per deck.
  The 130 MB is *arithmetic over an average*, not a byte measurement — see the next entry. c8-2
  owns the documented location, the removal command and the uninstall notes; the cache root is
  `src.paths.data_dir()/image_cache` and it is safe to delete wholesale at any time, because every
  entry is reconstructible by refetching and nothing indexes it. **Home: c8-2.** (Severity: Low —
  a disclosure and stewardship gap, not a defect.)

- ~~**The ~124 KB average tile size is arithmetic, never measured.**~~ **MEASURED AT THE C3
  RETROSPECTIVE, 2026-08-02 — and the epic's figure is a 38 % overestimate.** It was 12 MB ÷ 99
  tiles from the epic's own acceptance observation, and every footprint figure in this story
  (including the 130 MB above) inherited it. Measured by fetching all 99 distinct ids of
  `813d0434-…` (*Atraxa Counter Cabinet v2*) through the real route against the real CDN:

  | | Epic's arithmetic | **Measured** |
  |---|---|---|
  | per tile, `normal` | ~124 KB | **~90 KB** |
  | a 99-tile deck | ~12 MB | **8.5 MB** |
  | whole 1,061-id library | ~130 MB | **~95 MB** |

  Also measured for the first time, and the numbers c4-4 actually needs: **real Scryfall CDN
  latency ≈ 99 ms per image**, and a **warm read from the disk cache ≈ 10.3 ms per tile**
  (1.02 s for 99 sequential requests). The consequence for c3-6's constants is that they are now
  *vindicated by measurement rather than modelled*: throughput is
  `min(1/spacing, concurrency/latency)` = `min(1/0.1, 4/0.099)` = `min(10, 40.6)`, so **the spacing
  turnstile binds with 4× headroom on the semaphore** — exactly the regime the constants were
  chosen for. The `png`-vs-`small` variance this entry raises is untouched and remains real.
  **Home: c10-3** for the per-size profile; the grid-size figures above are now facts, not
  estimates. (Severity: Low → **resolved for `normal`**.)

- **A cache entry is never revalidated, so a corrected artwork is served indefinitely.** The key is
  id + size + face and AD-11 **accepts** that; a data refresh that changes a card's `image_uris`
  hits the existing entry. Today the only remedy is deleting the cache directory, which nothing
  documents (see the c8-2 entry above) and no tool offers. The shape that would fix it without
  reopening the key is a **generation stamp** — a cache subdirectory named for the database's own
  refresh marker — which costs nothing at read time and invalidates wholesale. Not built, because
  nothing in MVP knows when a refresh happened and inventing a marker for one consumer is the
  unused-hook mistake. **Home: unowned**; the forcing function is the first user-visible complaint
  about stale art, or whichever story gives the database a refresh timestamp. (Severity: Low.)

- **`os.fsync` is deliberately not called, so the cache is atomic but not durable** (Q3, Brad
  2026-08-01). A reader can never observe a partial file — that is temp + `os.replace` — but a
  power cut can lose a just-written entry, costing one refetch. Measured on this machine at Task 0
  (200 iterations, 124 KB): `fsync` costs **2.909 ms** against the whole write's **0.460 ms**, a
  6.3× multiplier, or 0.288 s of forced flushes on a cold 99-tile deck. **The ruling is the
  semantics and would stand at any price**; the number is corroboration. Recorded so that "the
  cache is atomically written" is never read as "fsynced" by a later story deciding what it can
  rely on. **Home: unowned** — nothing is expected to need this. (Severity: Low.)

- **Two simultaneous requests for one key both fetch and both write, and on Windows the loser's
  `os.replace` raises `PermissionError`.** The direct consequence of declining in-flight
  coalescing (see the re-homed c3-6 entry above). **Observed live** during implementation: a
  99-request burst over a single card id logged exactly that, and the request it belonged to was
  served normally — which is AC 9 working rather than a defect. It costs one duplicate fetch and
  one wasted write per collision. ~~**Home: c3-8**, which builds the in-flight map for its own
  reasons.~~ **RE-HOMED on c6-4 by c3-8, 2026-08-02, because the premise was wrong: c3-8 did NOT
  build an in-flight map, and needed none** (Q6 — see the coalescing entry above for why the
  shared-structure argument dissolved). This entry has always been a *consequence* of declining
  coalescing rather than an independent item, so it travels with it. **Home: c6-4**, which is the
  first surface that renders one card id twice on one screen and therefore the first that makes
  the collision ordinary rather than incidental. (Severity: Low.)

- **The one-write-site scan covers `src/companion` only, and it counts by module rather than by
  intent.** `TestExactlyOneImageWriteSite` asserts that rename-into-place happens in exactly two
  modules — `discovery.py` and `images.py` — once each. It would **not** notice a second write
  path that used a different mechanism entirely (`Path.write_bytes` straight to the target, a
  `shutil.copy` over it), because those are not renames; the *atomicity* claim is what the scan
  protects, not "nothing else writes". The complementary guard is
  `TestFileIoNeverRunsOnTheLoop`'s family, which does see `write_bytes` — but only inside an
  `async def`, and only in `images.py`. **A declared blind spot is still a claim**, so it is
  declared here rather than left to be discovered. **Home: unowned.** (Severity: Low.)
  **Updated by the 2026-08-01 review:** two rename-shaped spellings that were *inside* the
  claimed territory and undeclared — `Path.replace`/`Path.rename` (the pathlib rename-into-place
  the retired identifier ban did catch) and a call through a rebound local (`handler =
  os.replace`) — are now **caught by the scan**, discriminated from `str.replace`/
  `datetime.replace` by the one-bare-positional-argument signature. The declared blind spot is
  now genuinely limited to non-rename mechanisms, as this entry always said.

- **`_FILE_IO_CALLS` is a member list, not a module ban, and that is a knowingly weaker shape.**
  The C2 retro's standing agreement is *ban the family, never enumerate members* — but there is no
  module to ban here: the offenders live in `os`, `pathlib`, `tempfile` and the builtins at once,
  and `os` and `pathlib` are both needed on the sanctioned path. Import aliases are resolved, so
  the spellings that evade a member list are caught; what is **not** caught is a filesystem call
  whose name is not in the list (`os.truncate`, `os.link`, an `io.open`). **Home: unowned**;
  revisit if a later story adds a fourth file-touching mechanism. (Severity: Low.)

- **`images.py` now holds three mechanisms and is ~1,100 lines.** The spine draws the pacer, the
  disk cache and the negative cache inside `app/images.py` (`# proxy: pacer, disk cache, negative
  cache`), so c3-8 lands here too and makes it three. Splitting it is deliberately **not** this
  story's decision — that belongs to whoever finds the module unmanageable with all three shipped,
  not to the story that adds the second. Recorded so the growth is a noticed fact rather than a
  drift. ~~**Home: c3-8 or the C3 retro.**~~ **c3-8 DECLINED THE SPLIT and re-homed it on the C3
  retro, 2026-08-02 (Q8, Brad) — with the final number measured so the retro inherits a fact rather
  than an impression: `images.py` is now ~~1,475~~ lines** (1,307 at `3aef5d1`; the third mechanism
  and its docstrings added 168). All three mechanisms the spine's Structural Seed names are now in
  it (`app/images.py  # proxy: pacer, disk cache, negative cache`), so **splitting is now a decision
  to diverge from the spine** rather than a tidy-up — and that belongs to a retro with all three
  shipped and c4-1's hydration cache in view, not to the story that adds the third while writing it.

  **CORRECTED AND PARKED AT THE C3 RETROSPECTIVE, 2026-08-02.** The 1,307-at-`3aef5d1` figure is
  right; **the "now" figure was never re-measured and is wrong.** At `16976c5` — c3-8's own merge
  commit — and at HEAD the file is **1,837 lines**, a 362-line (25 %) undershoot. The entry existed
  specifically to stop the retro arguing from an impression and handed it one. Measured two
  independent ways (tokenizer and AST, agreeing to within 6 lines):

  ```
  src/companion/app/images.py            1,837 lines
    ├─ docstrings + comments             1,370   (74.6%)   1,279 docstring + 91 comment
    ├─ lines containing code               377   (20.5%)
    └─ blank                               289   (15.7%)
  ```

  Largest docstrings: module header **108**, `NegativeCache` 75, `DiskCache` 69,
  `_write_atomically` 67, `fetch_image` 65, `Pacer` 59, `resolve_face_images` 54.

  **This changes the shape of the decision.** 377 lines of code across three mechanisms and 39
  callables is ~125 lines each — not an unmanageable module. A split would divide *documentation*,
  and the 108-line module header is what explains the interaction a split would destroy (the cache
  is checked **before** the pacer; the negative cache sits **outside** `pacer.slot()`). The
  counter-argument from finding density — 5 of the epic's 10 Greptile findings, and every P1 from
  c3-5 onward, are in this file — is answered by noting that c3-5/c3-7/c3-8 are the three hardest
  stories in the epic: **density tracks difficulty, not line count**.

  Two adjacent actions were identified instead of a split: a **prose-freshness pass** over the nine
  large docstrings (this entry's own wrong number is an instance of c3-4's "prose outrunning code"),
  and the **review-added-mechanisms-re-enter-review** rule (C3 retro action item 12), which is what
  would actually have caught c3-7's sibling race and c3-8's carve-out.

  **DECISION PARKED by Brad, 2026-08-02**, pending the rest of the manual-testing checklist.
  ~~**Home: re-decide with c4-1's hydration cache in view.**~~ (Severity: Low.)

  **RE-HOMED at c4-1 (2026-08-02) → the C4 retrospective.** c4-1's hydration cache is now shipped
  and it is *in view*, so the disposition this entry asked for can be given: **the cache changes
  nothing about `images.py`.** c4-1 adds no Python at all, calls no image route, and its cache holds
  card ROWS — the three mechanisms in `images.py` (pacer, disk cache, negative cache) are untouched
  and un-approached by it. So the split question is exactly as open as it was, with one fewer
  unknown. Re-deciding it inside a frontend story would be deciding it on no new evidence.
  **Home: the C4 retrospective** — by then c4-4 (the art grid) and c4-6 (the flip control) will have
  exercised all three mechanisms against real decks, which is the evidence the decision actually
  wants. (Severity: Low.)

- **This machine's full-suite runtime is too noisy to support the before→after claim AC 24 asks
  for, and that is worth knowing before the next story tries to make one.** Three consecutive runs
  of *identical* code measured **118.40 s / 119.12 s / 167.56 s** — a **49 s spread**, ~40% of the
  median. The single baseline sample was 126.10 s, which sits inside that spread, so "the suite got
  faster" and "the suite got slower" are both unsupportable from single samples. An intermediate
  reading of 143.36 s during this story was initially attributed to the cache's disk I/O; that
  attribution was **wrong and is withdrawn** — it was background load.

  What *is* measurable, and what AC 24 actually wanted, is a **targeted** comparison rather than a
  whole-suite one: probe (b) removed the cache write entirely and the companion suite ran in
  **43.38 s** against **43.02 s** with the write in place, so the write costs nothing detectable —
  which is the specific thing AC 24 predicted would show up here *"and nowhere else"* had an
  `os.fsync` been added. **The lesson for later stories: compare the narrowest suite that contains
  the change, take more than one sample, and do not read a whole-suite delta on this box as
  signal.** **Home: unowned** — a measurement-practice note, not a defect. (Severity: Low.)

## Deferred from: code review of c3-7 (2026-08-01)

- **Q4's declined alternative — a sidecar carrying the upstream's full `Content-Type` — and the
  parameter divergence it tolerates.** A warm hit derives its media type from the stored
  extension, so any *parameters* the upstream sent (`image/jpeg; charset=binary`) are dropped on
  the second render of a tile; the media type itself always matches, by construction, since the
  review flipped `cache_extension` to derive the spelling from the same header the cold path
  serves (D1). The sidecar was declined because it doubles the entries on disk and reopens the
  atomicity question for a *pair* of files, to preserve a parameter no measured Scryfall response
  actually sends. Pinned by `test_the_one_named_divergence_is_the_content_type_parameter`; the
  c4-4-facing consequence is a `ui/README.md` blind-spot row. **Home: unowned** — the forcing
  function is an upstream that starts sending a parameter browsers act on. (Severity: Low.)

- **Orphaned `.tmp` files from a hard kill accumulate with no sweep, ever.** `_write_atomically`
  cleans its temp file on every in-process failure, but a process kill or power cut between
  `mkstemp` and `os.replace` strands `<name>.<rand>.tmp` in the card's shard directory
  permanently: `_read_cached` never matches the suffix (invisible, so it costs nothing but
  bytes), no startup or periodic sweep exists, and the c8-2 stewardship entry above covers cache
  *content*, not write debris. A `rglob("*.tmp")` sweep at startup was declined: it walks a
  potentially 38k-directory tree on every launch to reclaim litter produced only by crashes
  mid-write. The wholesale remedy is c8-2's documented `image_cache/` deletion, which removes
  debris and content alike. **Home: c8-2**, as one sentence in its stewardship notes. (Severity:
  Low.)

- **A transient startup `OSError` disables the cache for the whole process, with one WARNING at
  boot.** Q6's ruling covers root *creation* failure by disabling the cache and running on —
  correct for the named case (a *file* called `image_cache`), but a transient failure (AV
  briefly locking the data directory at boot, the exact Windows class this feature names
  elsewhere) has the same permanent consequence: every image fetches from the CDN until restart,
  announced only by a log line hours before anyone notices slowness. No retry, no re-attempt on
  first write. Declined here because a retry policy is a design decision c3-8's failure
  signalling is better placed to make consistently. ~~**Home: c3-8.**~~ **c3-8 TOOK THE OTHER
  ENTRY AND RE-HOMED THIS ONE ON c8-2, 2026-08-02 (Q4, Brad), and the reason is honest rather than
  tidy.** Of the two "failure posture over time" entries homed here, c3-8 took the unwritable-root
  one (below — it closed) and declined this one, because **retrying the root means deciding
  *when*** — at the first write? on a timer? after N requests? — which is a lifecycle question
  nothing in this feature measures and which c3-8 had no requirement to answer. Taking it would
  also have made `DiskCache` mutable in a way it is not, on top of the write-disable state that
  entry did add. **Home: c8-2**, which owns cache stewardship (epic `:3185-3212`) and is where a
  lifecycle policy belongs beside the documented location and the removal command. (Severity: Low —
  unchanged; requests are unharmed either way.)

- **A root that exists but is unwritable leaves the cache "enabled" and warns on every write,
  ~99 times per cold deck paint, forever.** `build_image_cache` probes only `mkdir` of the root;
  a pre-existing read-only directory (or ACLs changed mid-run) passes it, so every subsequent
  write fails and logs at WARNING with no disable-after-N and no startup writability probe. The
  requests themselves are unharmed (AC 9). A startup write-probe was declined as an effectful
  test-file in the user's data directory on every launch; log-rate limiting is c3-8-shaped.
  ~~**Home: c3-8**, beside the transient-startup entry above.~~ **CLOSED by c3-8, 2026-08-02
  (Q4, Brad — the half that was taken).** `DiskCache` now counts **consecutive** write failures and
  disables its own writes after `DISK_CACHE_WRITE_FAILURE_LIMIT = 5`, announcing it **once** with a
  message that says it is giving up and names the unwritable root. So a 99-tile cold paint logs at
  most five warnings instead of ninety-nine, and every paint after it logs none. Three properties
  gated rather than described: **reads keep working** (a root that just became unwritable may still
  hold everything a previous session cached, and NFR-06's offline claim depends on those reads);
  **one success resets the count**, so failures spread across a session cannot accumulate into a
  disabled cache; and the state is **per-instance**, never a module global. AC 9 is untouched — the
  picture is served either way and no reason token was added. The `deferred-work` pairing this
  belonged to is now split: this one closed, the transient-startup one re-homed on c8-2 above.

- **A third image format in the corpus would be served and never cached, silently degrading CM-2
  feature-wide — and the trigger that changes this is a measurement, not an argument.**
  `CACHE_MEDIA_TYPES` is a closed two-entry map (`.jpg`/`.png`), justified by the corpus: exactly
  two formats across all 245,760 stored URLs, `image/webp`/`image/avif` measured at **zero**.
  `DiskCache.write` therefore treats an accepted-but-unmapped `image/*` header as *served, not
  stored* — the ruled posture (Q4 + c3-2's "a true count read as a false rule": the count
  justifies the map; it does not justify caching under a guessed extension, which Greptile's
  round-1 P1 confirmed mislabels the bytes). Greptile's round-2 P1 flagged the flip side —
  *"accepted formats bypass the cache, violating CM-2"* — **declined by Brad (2026-08-02)**:
  CM-2 is satisfied for every image this corpus can produce, and caching formats measured at
  zero is the unused-hook mistake. The real exposure is a Scryfall format migration behind
  existing URLs, which would flip every write to the serve-not-store branch and announce itself
  only as a per-request `INFO` line while the cache quietly stops growing. **The trigger is
  written down so nobody re-litigates it**: the first *measured* third format in the corpus
  widens `CACHE_MEDIA_TYPES` by exactly one entry (extension + media type, warm/cold agreement
  preserved by construction) — a two-line change plus one discrimination test. **Home: whichever
  story first measures a third format** (the c8-x data-refresh surfaces are the likeliest
  observers); until then, unowned by design. (Severity: Low.)

- **`DiskCache` trusts its callers for containment: `card_id`/`size`/`face` are validated by the
  route's own constraints, not by the class.** `path_for("../../..", ...)` escapes the root —
  demonstrated by the containment test's own firing half — and nothing in the class refuses it;
  the route's `_CARD_ID_PATTERN`, the closed `ImageSize` literal and the bounded `face` are the
  whole guard, and they live in a different module. Deliberate under c3-4's unused-hook ruling
  (today's only caller is validated), but the module's next callers are already named — c3-8's
  negative cache in this same file, c6-4's suggestion tiles — and the first one that passes an
  unvalidated id gets a traversal write. ~~**Home: c3-8**, which touches this class next and
  should either validate at the class boundary or restate the trust chain in its own record.~~
  **c3-8 RESTATED rather than validated, 2026-08-02 (Q9, Brad), and the reason it is safe is
  STRUCTURAL rather than a promise.** Of the two options the entry offered, the second was taken
  because the first would have been protecting against this story rather than because of it:
  **`NegativeCache` builds no path at all** — it is a dict keyed on a tuple — so it is
  *structurally incapable* of being the caller that turns an unvalidated id into a traversal write.
  Adding validation on its account would have been an unused hook (c3-4's ruling) justified by a
  caller that cannot trip it. The trust chain is now written into `DiskCache`'s own docstring by
  name: `routes/cards.py`'s `_CARD_ID_PATTERN` (canonical lowercase uuid or `400`), the closed
  `ImageSize` `Literal`, and the bounded `face` — three constraints, all upstream of the key.
  **Home: c6-4**, now the *sole* remaining named caller, with the instruction carried forward: if
  c6-4 reaches `DiskCache` with an id from anywhere but a validated route parameter, validate at
  the class boundary first. (Severity: Low.)

## Deferred from: story c3-8 (distinguishable failure signalling and negative caching, 2026-08-02)

- **A cold paint against a dead CDN still costs ~124 seconds and all ~99 requests, once per
  process.** This is the exposure the negative cache does **not** close, stated as a ledger entry
  rather than only as prose because it is the thing a reader will most plausibly assume was fixed.
  99 tiles resolve to 99 **distinct** keys, so on the first paint nothing is remembered and every
  request is issued. Steady-state throughput is `min(1/spacing, concurrency/latency)` =
  `min(1/0.1, 4/5.0)` = **0.8 fetches/second** at the shipped `_FETCH_TIMEOUT.connect = 5.0`, so
  the paint takes roughly **124 s** — and the user watches 99 placeholders for two minutes. The
  backoff bounds every paint *after* that one, which is what `EXPERIENCE.md`'s "no request storms"
  means here. Closing it would need something that fails a *whole host* fast rather than a key at
  a time — a circuit breaker over `ALLOWED_IMAGE_HOSTS`, which is a fourth mechanism and a
  different shape from anything AD-11 asks for. **Home: c10-3**, which owns real-latency profiling
  and is the first story positioned to say whether 124 s is a real user experience or an artefact
  of an unrealistic failure mode. (Severity: Low today — it needs a CDN that is *unreachable*
  rather than merely slow; Medium if c4-4's manual testing finds it.)

- **The retention horizon is a fifth number Q2 did not fix.** Q2 ruled the base, the multiplier,
  the ceiling and the cap. Implementing it surfaced a fifth decision neither the story nor the
  question had named: **how long a key's failure history outlives its own backoff window.** It has
  to be longer than the window, or escalation is unreachable in production — an entry dropped at
  `retry_after` resets the count on every attempt, so a key against a permanently dead CDN cycles
  at the base delay forever while every "consecutive failures escalate" unit test still passes.
  c3-8 derived it as `retry_after + ceiling` rather than declaring a constant, so it cannot drift
  from the reasoning, and asserted it from both sides. Recorded because it is a **decision made
  during implementation rather than at context time**, which is exactly the kind that later reads
  as arbitrary. **Home: unowned** — revisit only if a real backoff misbehaves. (Severity: Low.)

- **`is_backing_off` never prunes, so up to 2,048 stale entries can sit in a quiet process.**
  The hot path is deliberately side-effect free: a dict lookup and one comparison, no walk. Pruning
  happens only on `record_failure`, so a process that fails a burst of keys and then goes quiet
  keeps those entries until something else fails. Bounded by `NEGATIVE_CACHE_MAX_ENTRIES` and
  therefore harmless — at most ~2,048 small tuples — and the alternative (pruning on read) would
  put an O(n) walk on NFR-05's path to reclaim memory nobody is short of. Recorded as a declared
  limit rather than a defect. **Home: unowned.** (Severity: Low.)

- **A story that empties `_BANNED_IDENTIFIERS` now gets a red, but nothing tells it what to do.**
  c3-8 added an explicit non-emptiness assertion to the two firing halves, so the `set() == set()`
  degradation c3-7 caught by noticing is now caught by a test. What is still only prose is the
  **procedure**: c3-6 wrote it down, c3-7 followed it, c3-8 declined to apply it with a reason —
  but it lives in a frozenset's docstring rather than anywhere a story author would look before
  starting. ~~**Home: the C3 retrospective**, which is where three worked examples of the same
  procedure should become a standing agreement.~~ **CLOSED at the C3 retrospective, 2026-08-02
  (R2, Brad) — promoted to a standing team agreement, "banned-family lifecycle":** *a story that
  owns a banned identifier family must explicitly **retire it, re-key it, or keep it with a written
  reason** — and a replacement must be probed against **the spellings the retired ban caught**, not
  only against new ones. Removing a family without a replacement covering its members is a coverage
  loss disguised as a cleanup.* The two worked failures are named in the agreement (c3-6's
  `from time import sleep` and c3-7's `Path.replace` — in both cases the retired ban DID catch the
  spelling its replacement missed); c3-8 is the worked *keep*. Recorded in
  `epic-c3-retro-2026-08-02.md` § *Team agreements*. (Severity: Low → **closed**.)

- **`ErrorResponse`'s class docstring is published in full and nothing says so at the edit site.**
  c3-8 predicted "no wire diff", edited that docstring, and measured a real diff in both generated
  files — while the same commit's edit to `ErrorReason`'s attribute docstring twelve lines away did
  **not** cross the wire. The distinction is correct and now documented in `scripts/dump_openapi.py`,
  but `contracts.py` itself carries no marker at either site, so the next author has the same 50/50
  guess. A one-line comment above each would fix it; it is not done here because `contracts.py` is a
  wire module and even a comment edit is a wire decision that would want its own regeneration.
  ~~**Home: c3-9**, which already inherits wire-value work.~~ **CLOSED, c3-9 (Q9, 2026-08-02).**
  One `#` comment above `ErrorReason`'s assignment (*NOT PUBLISHED*) and one above
  `ErrorResponse`'s `class` statement (*WIRE-VISIBLE, IN FULL*), each naming the mechanism and the
  c3-8 measurement it came from. **c3-7's objection is dissolved by measurement, not by the
  regeneration this story owed anyway**: `npm run gen:api` was run after the comment edits and
  produced **no diff at all** from them — a `#` comment is not a docstring, so it never reaches
  `app.openapi()`. That is now the recorded safe way to annotate a wire module, in
  `scripts/dump_openapi.py`. (A docstring edit still is a wire change, and still needs its own
  regeneration.) (Severity: Low.)

## Deferred from: code review of c3-8-distinguishable-failure-signalling-and-negative-caching (2026-08-02)

- **Concurrent duplicate requests for one key escalate the backoff per-record, not per-outage, and
  each record slides the window forward.** Two simultaneous requests both pass `is_backing_off`
  (no entry yet), both fetch, both fail, and one outage instant lands the key at 60 s; N duplicates
  escalate N steps at once, and each `record_failure` inside an open window rewrites
  `retry_after = now + delay`. Documented as deliberate in `record_failure`'s docstring ("two
  tabs... the count measures how bad this outage is") — but N concurrent duplicates measure
  *fan-out*, not outage severity. Harmless today because duplicate printings collapse in
  `deck_cards` before reaching the route; c6-4's duplicate-tile surface (the acknowledged
  coalescing trigger) makes it the normal case. **Home: c6-4**, beside the in-flight-coalescing
  entry it shares a fix with. (Severity: Low.)

- **A short burst transient can permanently latch the disk cache's writes off.** Writes during a
  cold paint arrive back-to-back at ~0.8/s, so a ~6 s transient (an AV scanner holding a handle, a
  disk-full blip) spans `DISK_CACHE_WRITE_FAILURE_LIMIT = 5` *consecutive* writes and disables the
  cache's writes for the process — the "consecutive" reset only protects failures separated by
  successes, and Q4 declined any re-enable path. Accepted at review (Brad, 2026-08-02): the
  consequence is only lost caching, images are still served, and the docstring now states the
  exposure honestly. Any re-enable/recovery mechanism is cache stewardship. **Home: c8-2.**
  (Severity: Low.)

- **The backoff 502 answers without a `Retry-After` header the server could supply.** The route
  holds `retry_after` at the moment it answers a negative hit and discards it; the SPA therefore
  has no signal for when a stuck tile (up to 300 s after CDN recovery — see `ui/README.md`'s
  blind-spot row) becomes worth one scheduled retry. A standard `Retry-After` header would give
  the tile author exactly one correct action without a new token — but it is a wire-visible change
  c3-8's rulings excluded. Declined at review (Brad, 2026-08-02) so the tile author decides with
  the UI in view. **Home: c4-4**, beside the blind-spot row it would resolve. (Severity: Low.)
## Deferred from: story c3-9 (fresh install guides instead of erroring, 2026-08-02)

Every entry here has a **named home**, per AC 23. Nothing in this section is prose-only: each one
either has an owner story or is declared inside the file it constrains.

- **The four newly-reachable panels have still not been looked at by a human, and neither has the
  transition.** This is the honest split of AC 11 and AC 25. What WAS done live: an empty
  `PLANESWALKER_DATA_DIR`, a companion that started with no `cards.db`, `GET /api/decks` answering
  `503 database_not_initialized`, a `cards.db` planted while the server ran, and the very next
  request answering `200` with real deck names — no restart. What was NOT done: opening the URL in
  a browser and watching the PAGE change, and looking at `database-not-initialized`,
  `database-updating`, `database-updating-stalled` and `internal-error` rendered by a real engine.
  This environment has no browser automation installed and adding one would be a new dependency
  the story does not call for. The DOM-level claim is gated (`App.test.tsx`'s FR-22 block asserts
  the transition from ONE mount, and probe (f) confirms a remount-driven implementation fails it);
  the VISUAL claim is not made anywhere. **Home: the epic manual-testing checklist**, with the
  recipe in the c2-9 entry above and in `ui/README.md`'s new blind-spot row. (Severity: Low — the
  behaviour is gated; the appearance is a first-look.)

- **A backend that cannot be reached at all leaves whatever panel is on screen, including on the
  very first load.** `fetch` rejecting produces no response and therefore no token, so the poller
  changes nothing and retries on the backoff. On the first load that means "No deck on the glass."
  stays up while the app quietly retries a backend that is not there — a calm panel that is not
  true. The panel that IS true for it is `disconnected` (*"Lost the companion backend. Check your
  terminal…"*), and `CLIENT_ONLY_STATES` assigns it to **c5-6**, whose condition is the WebSocket
  backoff exhausting its retries; Q10 ruled c3-9 must not claim it. Ruled rather than overlooked:
  clamping a transport failure to `internal-error` instead would have been worse, because
  `RETRIES_QUIETLY['internal-error']` is `false` and one transient blip would have stopped the poll
  permanently. **Home: c5-6.** (Severity: Low-Medium — the wrong panel, in a case a fresh install
  reaches only by starting the browser before the backend.)

- **Once a `200` arrives the poll stops, and nothing notices if the database goes away again.**
  `RETRIES_QUIETLY['no-active-deck']` is `false` — correct, because the agent sets the deck and a
  `deck_changed` event delivers it — so a tab left open through a later `initialize_database`, a
  deleted `cards.db` or a corrupted one shows a stale `no-active-deck` panel until it is reloaded.
  The signal that should replace polling here is **c5-6's** WebSocket (and its reconnect refetch,
  NFR-04). Stated because the poll deliberately does NOT become a heartbeat: making it one would
  contradict a contract written down in `states.ts` and would put two mechanisms on the same job.
  **Home: c5-6.** (Severity: Low.)

- **The stalled panel is terminal, and a database that recovers after it does not un-stall.**
  `RETRIES_QUIETLY['database-updating-stalled']` is `false`, by design — *"the quiet retry has
  already been running and has not worked, so continuing to retry silently is the behaviour this
  state exists to replace"* — and the copy's next action is a manual one. But if the user does what
  it says and the import succeeds, the page still needs a reload, which is one refresh more than
  FR-22's promise. Same resolution as the entry above: **c5-6's** reconnect is the event that
  should re-drive it. **Home: c5-6.** (Severity: Low.)

- **A first import that starves reads for 60 s continuously would escalate to stalled — unmeasured
  edge.** During a bulk import `is_database_initialized` returns `False` (the `import_state` probe),
  so the dominant answer is `database_not_initialized`, which never escalates. But if the
  importer's write batches ever hold the write lock past the engine's 5 s busy timeout, the read
  raises and the route answers `database_unavailable` instead — and 60 s of *continuous* such
  answers would show "Card database still updating. Check your agent session — if no import is
  running…" during an import that is running. The importer's batch size was not measured here, and
  the Q7 measurement above says lock waits are ~0.2 s worst case under four saturating readers, so
  this is a narrow window rather than a likely one. **Home: c10-3**, beside the lock work.
  (Severity: Low, unmeasured.)

- **`ui/tests/posture.test.ts`'s identifier layer is defeated by a computed global assembled from
  fragments, and its import layer is what actually carries the guard.** Declared in that file's own
  header. `globalThis['fetch']` is caught (the identifier is present); `globalThis['fet' + 'ch']` is
  not, and neither is an aliased hook CALL (`sync(subscribe, snapshot)`) — the alias is caught at
  the IMPORT door instead, which is why the door is the primary layer. Probe (g) planted both
  spellings in a real component file and confirmed exactly this split. The answer to the remainder
  is review, not a longer regex — the same declaration `test_import_boundary.py` makes on the
  Python side. **Home: review, permanent.** (Severity: Low, permanent.)

- **`CLIENT_ONLY_STATES` still has no runtime consumer**, and unlike its two siblings it is not
  expected to gain one from a wiring story: `database-updating-stalled` is produced by elapsed time
  rather than looked up, and `disconnected` is selected by nobody until **c5-6**. It is still worth
  keeping — `EveryPanelHasASource` and `PanelSourcesAreDisjoint` both read it at typecheck time, so
  it is load-bearing without being executed. **Home: c5-6**, which either consumes it or is the
  story that says it should stay type-level. (Severity: Low.)

- **The `no-store` request header is asserted, its EFFECT is not.** `decks.test.ts` pins
  `cache: 'no-store'` on the request options, which is a source-level claim; whether a real browser
  honours it for a same-origin `200` with no `Cache-Control` was not measured, because jsdom has no
  HTTP cache. The consequence if it were wrong is precisely FR-22 failing — a cached `503` would
  make the page never come alive — so it is worth one look during the browser pass rather than a
  test. **Home: the epic manual-testing checklist**, beside the transition look-at. (Severity:
  Low.)

## Deferred from: code review of c3-9 (2026-08-02)

- **Alternating `database_unavailable`/`database_not_initialized` pins the backoff near base.**
  `poller.ts` resets `delay` to `POLL_BASE_MS` on every outcome-identity change (Q2's own ruling:
  *"resets to base on any change of outcome"*). During an interleaved import — the exact
  interleaving this ledger already documents — each flip resets the schedule, so sustained
  alternation approaches one request per 2 s against a backend that is deliberately busy, which is
  what `POLL_CEILING_MS`'s docstring says the ceiling exists to prevent. By-design per Q2; the cost
  was not weighed there. ~~**Home: c4-1**, which copies this seam for its per-card fetches and should
  decide whether token-change resets need damping (e.g. no reset between the two database tokens).~~

  **RE-HOMED at c4-1 (2026-08-02, Q6) → c5-6, and the premise it was homed on turned out to be
  false.** c4-1 does **not** copy this seam: `readCard` has no backoff, no schedule and no timer at
  all, and AC 12's bound is a cumulative **attempt count per id**
  (`MAX_ATTEMPTS_PER_CARD = 3`) rather than a token-driven retry loop — so there is no `delay` for
  a token change to reset and nothing here to damp. Beyond that, the damping question is about
  `poller.ts`'s whole-screen poll, and **c5-6 already owns the family of sibling entries about that
  poller's re-drive behaviour** (C3 retro ruling R3: *"c5-6 resolves the family; it should not solve
  one third of it"*). **Home: c5-6.** If a later per-card path ever grows a schedule, this decision
  comes with it.
- **`database-updating-stalled` permanently forfeits FR-22's self-transition.**
  `RETRIES_QUIETLY['database-updating-stalled']` is `false` (ruled in `states.ts:233` — *"continuing
  to retry silently is the behaviour this state exists to replace"*), so once escalated the poll
  stops for the life of the page: when the user does exactly what the panel's copy tells them to and
  the rebuild succeeds, the `503→200` transition this story exists to render is invisible, and only
  a manual refresh recovers. The contract is honoured; its terminal consequence was never written
  down. A slow continued probe would need a `states.ts`/`EXPERIENCE.md` amendment, which this story
  may not make. ~~**Home: C3 retro**, as an EXPERIENCE.md amendment question.~~

  **RULED AT THE C3 RETROSPECTIVE, 2026-08-02 (R3, Brad): ACCEPTED, and re-homed on c5-6.**
  `RETRIES_QUIETLY['database-updating-stalled']` **stays `false`** — the contract in `states.ts:233`
  is right, and a slow continued probe would put two mechanisms on one job. **No `EXPERIENCE.md`
  amendment.** What the ruling adds is that the terminal consequence is now recorded rather than
  implied: *a user who does exactly what the panel's copy tells them, and whose rebuild succeeds,
  still needs a manual refresh — one refresh more than FR-22 promises.*

  The ruling is a re-home, not a dismissal: the two sibling entries above (*"Once a `200` arrives
  the poll stops"* and *"a backend that cannot be reached at all leaves whatever panel is on
  screen"*) are already homed on **c5-6**, whose WebSocket reconnect and NFR-04 refetch is the event
  that should re-drive all three. **c5-6 resolves the family; it should not solve one third of it
  and leave the rest.** **Home: c5-6.** (Severity: Low.)
- **The c4-1/c4-2 seam Q1 drew, restated where AC 23 asked for it (review patch).** Q1 ruled that
  `src/api/decks.ts` (the one network door, a total outcome union that never rejects) and the
  `src/state/` slice are the seam **c4-1 EXTENDS** — card cache, in-flight deduping, per-card
  routes, which are NOT retry-safe (they carry path parameters; `decks.ts`'s header holds the
  c3-2 measurement of why) — and that **c4-2** inherits a poll already calling `GET /api/decks`,
  its job being to read the DECK rather than the deck names. What the poller does NOT cover:
  per-card fetches and the WebSocket. The threshold is `STALLED_AFTER_MS = 60_000` with a
  `STALLED_MIN_REFUSALS = 4` observation floor. The prose homes are `ui/README.md`'s "Not here
  yet" + blind-spot row and the module headers; this entry exists so the ledger names the seam
  too. ~~**Home: c4-1 and c4-2 read this before extending.**~~

  **✅ READ AND ACTED ON at c4-1 (2026-08-02); half closed, c4-2's half stands.** Every clause was
  honoured and one was amended by ruling. The seam was **extended, not replaced**: the module is
  still the one network door and still a total outcome union that never rejects, and `readCard`
  was written to that shape. The deduping went **around** it, in `src/state/cards.ts`, exactly as
  the ruling said. The not-retry-safe warning was the operative one and it produced
  `MAX_ATTEMPTS_PER_CARD`, whose docstring carries the c3-2 measurement so the reason travels with
  the constant. **The amendment: the door is now `src/api/client.ts`, not `src/api/decks.ts`**
  (c4-1 Q1) — the guard's property was always "one door, named exhaustively", and a module named
  for decks that exports `readCard` is the "prose outrunning code" finding this epic has now made
  four times. `posture.test.ts:328`, its comment and `ui/README.md` moved in the same commit.
  **The c4-2 half is untouched and still owed**: it inherits a poll already calling
  `GET /api/decks`, its job is to read the DECK rather than the deck names, and it now also
  inherits `seedCardSummaries` — the entry point that turns the `DeckCardSummary[]` its own fetch
  already returns into the cache's summary tier for zero extra requests. **Home: c4-2.**

## Deferred from: code review of c4-1-a-single-card-hydration-cache-with-in-flight-deduping (2026-08-02)

- **Three transient failures make an id terminal for the tab's life while the whole-screen poller
  self-heals (FR-22 asymmetry).** `retryable` counts `unreachable` outcomes against
  `MAX_ATTEMPTS_PER_CARD = 3` (`ui/src/state/cards.ts:389`), so a backend restart or network blip
  during one hover sweep spends an id's three attempts forever — while `poller.ts` retries
  indefinitely and the panel "comes alive on its own". The story record declares this residue and
  names the fix: `resetCardCache()` on the `deck_changed` (or recovery) transition, which **c4-2**
  owns. Home: c4-2, with c4-5 (detail panel) as the story that would make it visible.
  **Companion question, same home (Greptile PR #40, P2, ruled option-1 "declare" by Brad
  2026-08-02):** a `hydrateCard` promise that a reset orphans still resolves with the entry it
  computed for the discarded world — the store write is generation-guarded, the return value is
  not. Harmless while resets are test-only and consumers render from `useCardEntry`; the moment
  c4-2 wires a production reset, decide whether awaiting callers need the fresh answer (widen the
  return to `CardEntry | undefined`) or the docstring's "the store is the authority" ruling
  stands. Declared in `hydrateCard`'s Returns docstring.
- **`useCardEntry` is untested.** A React render harness would be needed and no testing library is
  in the dependency set (adding one casually is banned by AC 21 / package-contract). Home: c4-3
  (first consumer) — its component tests exercise the hook for real; if c4-3 introduces a testing
  library for its own needs, add a direct `useCardEntry` subscription test then.

  > **✅ RESOLVED at c4-3 (2026-08-04) — and the stated reason was FALSE, as c4-2 already recorded.**
  > `@testing-library/react@^16.3.2` has shipped all along; no dependency was added and
  > `package-contract.test.ts` is untouched. The hook is now exercised through its real contract in
  > `CardPlaceholder.test.tsx`: a test component subscribes with `useCardEntry`, and four
  > assertions drive it — an id never seen renders the WELL rather than an unknown card (`undefined`
  > means "never seen" and only that); `seedCardSummaries` makes it **re-render** with the card's
  > name, which is the whole contract of a selector that starts nothing; a `card_not_found` refusal
  > through `hydrateCard` with an injected reader turns it into the unknown placeholder; and a
  > `database_unavailable` refusal LEAVES THE SUMMARY STANDING, because `placeholder` is `null`
  > there. **The component itself does not subscribe (c4-3 Q7)** — a listed primitive may hold no
  > hook of any family, so the subscription lives at the call site and the test component is the
  > shape c4-4's tile will take.

## Deferred from: c4-2-deck-state-bootstrap-and-the-type-grouped-decklist (2026-08-02)

### The ten inherited deferrals, each with a disposition (AC 28, C2 retro ruling R2)

1. **`GET /api/decks` and `GET /api/deck/{id}` have never been called by a browser** (`:1666`,
   Low, "Home: c4-2"). **✅ RESOLVED, and by a real browser rather than by argument.** The
   companion was launched (`src.companion.app.server.run`), a deck was set active over the real
   `PUT /api/active-deck`, and the built SPA was rendered in **Microsoft Edge (headless=new)**
   against `http://127.0.0.1:8765/`. Both boot routes were exercised through the security
   envelope by a browser, and the deck rendered. Screenshots captured for three states: a loaded
   deck, a `404` clearing to no-active-deck, and a hostile id. **The Vite dev-proxy path
   (`changeOrigin`, c2-1) is still unexercised** — the render was against the served bundle, not
   `npm run dev`. **Home for that remainder: the next story that runs `npm run dev` in anger.**
2. **Generated-type optionality asymmetry** (`:1889`, Low, "Home: c4-2, unshared"). **DECLINED,
   with the measurement that makes it a decline rather than a deferral.** The half that would have
   bitten does not exist: `openapi-typescript` renders a schema `default` as a **required**
   property, so `mainboard_count`, `sideboard_count` and `distinct_cards` are `number` in
   `types.d.ts` — **not** `number | undefined` — and there is no spurious `undefined` branch to
   absorb. Verified by reading the generated file, not assumed. What remains is genuinely
   asymmetric (`strategy?: string | null` versus `format: string | null`, a Python-default
   artifact) and is a field **this story does not read**; fixing the wire means changing a Pydantic
   default that `create_deck` and the MCP server both call. Real blast radius, no consumer.
   **Re-homed by name to the first story that reads `strategy` — c4-7 (the deck list) is the
   nearest candidate.** The `@default 0` half is CLOSED, not carried.
3. **No sanctioned `DeckDetail` alias** (`:2108`). **✅ RESOLVED.** `src/api/schema.ts` now exports
   **nine** aliases: c4-2 adds `DeckDetail` (consumer: `readDeck`, and the `deck` arm of the deck
   slice) and `ActiveDeck` (consumer: `readActiveDeck`), each with a docstring naming it.
   **`CardFace` is still declined** on c3-2's own reason — an unused export is dead code — and
   remains **c4-6's**, the story that renders a flip control.
4. **The c4-1/c4-2 seam restatement** (`:3252`, "The c4-2 half is untouched and still owed").
   **✅ READ AND ACTED ON; the entry is now fully closed.** The seam was extended, not replaced:
   `src/api/client.ts` is still the one door (`posture.test.ts:328` green with no edit), both new
   readers are total unions that never reject and never return `null`, and both go through the
   existing private `request()` rather than calling `fetch` a third and fourth time. The poll was
   inherited unchanged — its job is still the deck NAMES — and `seedCardSummaries` is called with
   the payload this story's own fetch returns, for zero extra requests.
5. **Three transient failures make an id terminal for the tab's life while the poller self-heals
   (FR-22 asymmetry)** (`:3280`, "the named fix is `resetCardCache()` on the `deck_changed` (or
   recovery) transition, which c4-2 owns"). **RE-HOMED BY NAME to c5-4 / c5-6.** The entry homed
   it here on the theory that c4-2 owns a `deck_changed` transition; **measured, it does not** —
   `deck_changed` is an Epic 5 WebSocket message, and this story boots once and never switches
   decks. A blanket reset on a deck switch is probably the wrong fix anyway: the cache is keyed by
   printing uuid and shared with Epic 6's agent views (AD-12's second sentence), so resetting on a
   deck change throws away hydration for every card the two decks share. **c5-4 (the event
   handlers) owns the transition; c5-6 (reconnect/refetch) owns the recovery half.**
6. **The orphaned-hydration return residue** (`:3287`, Greptile PR #40 P2, ruled *declare*).
   **RE-HOMED WITH ENTRY 5, to c5-4 / c5-6**, because it was explicitly conditional on this story
   wiring a production reset — *"the moment c4-2 wires a production reset, decide…"* — and c4-2
   wires none. `resetCardCache()` remains test-only. The docstring's "the store is the authority"
   ruling stands untouched.
7. **The primitives' APPEARANCE is not dev-verified** (`:1331`, **Medium**) **and the tone-over-
   wash CONTRAST is unmeasured** (`:1357`). **✅ RESOLVED FOR `Badge`; the rest re-homed.** See
   the measurements in §"What c4-2 measured" below. `Panel` (**c4-5** / **c4-7**), `StatChip`
   (first surface that carries one) and `GroupHeader` (**c4-7**) still have no on-screen consumer
   and remain unverified — **home unchanged**.
8. **C3 retro F2 — the kicker and the `h1` say the same words** (retro `:225`). **✅ RESOLVED**,
   and confirmed on a real screen: the kicker reads `ARTIFICIAL PLANESWALKER` and the `h1` reads
   `Atraxa Counter Cabinet v2 (owned)`. `AppShell.tsx` was not edited; the swap is a prop.
9. **C3 retro action item 4 — a gate banning story-key-shaped strings from rendered text**
   (`/\bc\d+-\d+\b/`), owner *"Sathias (c8-5, or earlier if a C4 story is nearer)"*. **DECLINED;
   stays c8-5 (Q8), and the reason is now measured rather than predicted.** c4-2 REMOVES two of
   the offending strings from the deck view (the `h1`'s product name and the badge placeholder
   naming `c2-7 / c4-2 / c4-10`) and **leaves six on screen**, counted off the real render:
   `c4-4`, `c4-8`, `c4-9` in the left column and `c4-5`, `c4-7`, `c4-10` in the right, plus
   `c6-8` in the nav. Every one of them is CORRECT today, so a gate built here ships either
   disabled or with an allowlist — and an allowlisted ban is the "enumerate members" anti-pattern
   this epic has now violated three times. **Home: c8-5, unchanged.**
10. **C3 retro carried manual-testing items A3/A4** (*"c4-2 renders four of the five panels for
    real; A3–A6 are its acceptance surface"*). **PARTIALLY PERFORMED, remainder fed forward.**
    Two of the five were rendered by a real engine here: `no-active-deck` (with the real deck list
    of 15 names) and the deck view that displaces it. **A3–A6's database panels
    (`database-updating`, `database-updating-stalled`, `internal-error`, `database-not-initialized`)
    still need a backend in those states**, which this story could not manufacture without
    corrupting the live database. **Home: the C4 manual-testing checklist**, with the trade the
    retro already ruled — after c4-2 a failure is ambiguous between the panel and the new wiring.

### The two corrections this ledger pass owed (AC 28)

- **`@testing-library/react` IS in the dependency set** — `^16.3.2`, with `@testing-library/dom`
  and `@testing-library/jest-dom@~6.9.1`, and `App.test.tsx` has used it since c3-9. The
  `useCardEntry` deferral's stated reason (*"no testing library is in the dependency set"*) is
  **false**; the deferral's HOME (c4-3) is still right, but for the honest reason that c4-3 is the
  first consumer rather than for a dependency that already ships. c4-2 used the library freely.
- **c4-1's "0 dangling references across 2,027 `deck_cards` rows"** is right about **card**
  references and wrong about the row count's meaning: **28 of those 2,027 rows are orphaned by
  DECK id** (2 deleted decks, no FK enforcement on the async engine), so the live population is
  **1,999**. Neither changes a decision; both are numbers later stories will quote.

### What c4-2 measured, so nobody measures it twice

- **`Badge`'s appearance, on a real screen.** Rendered in Edge against the running backend. The
  `::before` wash sits BEHIND the text — `z-index: -1` plus `isolation: isolate` behave as
  `Badge.css` argues they would — so the ledgered failure mode (*a solid blank pill with invisible
  text*) **does not occur**. This was the Medium-severity half of entry 7.
- **Contrast, all five tones, text over their own wash**: `neutral` **7.60:1**, `accent`
  **8.33:1**, `positive` **7.97:1**, `negative` **6.17:1**, `caution` **8.99:1**. Every one clear
  of 4.5:1. Washes computed as the tone at `opacity: 0.12` composited over `--surface-base`
  (`neutral`'s is opaque `--surface-overlay`).
- **One number that does NOT clear a floor, and what it constrains.** `neutral`'s
  `--border-strong` hairline is **1.89:1** on the page and **1.54:1** on its own wash, against
  WCAG 1.4.11's 3:1 non-text floor. **Accepted for `neutral`**: a badge is a static label rather
  than a UI component, and its boundary carries no information its wash does not. **A live
  constraint for c4-10**, whose format-check badge carries STATE — the four semantic borders are
  6.73:1 / 9.96:1 / 7.32:1 / 11.49:1 and fine, so a state distinguished by TONE is safe and a
  state distinguished by the neutral border would not be.
- **The URL-encoding argument, confirmed against a live backend rather than reasoned.** Raw
  `GET /api/deck/../decks` answers **`200` carrying the DECK LIST** — it does not fail, it
  succeeds against a different route, and a client interpolating raw would render `/api/decks`'s
  array as a deck. Encoded, `..%2Fdecks` answers `404 invalid_request`. Note the status/token
  split in that second answer: AD-16's "nothing keys off a bare status code" made vivid.
- **The type-group corpus facts.** 38,261 cards; 3,183 type lines containing `//`; **2,274**
  literally `'Card // Card'` (real front-face type only in `card_faces`, **0 in any live deck**);
  400 literally `'Card'` (**2 live rows**, "Pym Particles"); 88 live rows carrying more than one
  primary type on the front face; 4 corpus `Land Creature` (**0 live**).

### New residues c4-2 declares

- **The `'Card // Card'` printing cannot be grouped correctly from the deck payload.** Its real
  front-face type lives only in `card_faces[0].type_line`, which `DeckCardSummary`'s embedded
  `CardSummary` does not carry. 2,274 in the corpus, **0 in any live deck** — latent, not live.
  Fixing it means 99 extra card fetches for a case no deck contains. **Home: c4-6**, which adds
  `CardFace` and renders faces anyway; if it lands, the grouping can read the front face properly
  for the ids already hydrated. (Severity: Low.)
- **29 distinct corpus type lines discriminate the front-face rule; 0 are in any deck.** A type
  line only discriminates when its front face carries NO em-dash (so the subtype strip cannot
  remove the back face) AND the back face's group precedes the front's — e.g.
  `'Land // Legendary Creature — Demon'` (Westvale Abbey). `deckGroups.test.ts` pins six by name.
  Recorded because **the obvious fixtures do not discriminate**: a probe deleting `frontFace()`
  from `groupOf` left 27 assertions green, including all four "land policy" cards. (Severity:
  Low — the rule is right; the note is about where it can be tested.)
- **There is no re-drive after the boot.** A deck the agent sets while the tab is open does not
  appear until Epic 5's `deck_changed`. Specified, not a bug — `poller.ts` still stops after one
  `200` and `App.test.tsx` still asserts that — but it is the difference a user would notice
  between this story and a finished product. **Home: c5-4.** (Severity: Low.)
- **A `404` clears the client while the backend still reports that deck id as active.** So the
  next cold open asks for the deleted deck again and clears again: one wasted request per boot,
  self-correcting the moment the agent sets another deck. The alternative — the client telling the
  backend to forget an id — is a `PUT` this story has no mandate to make. **Home: c5-4**, with the
  `deck_changed` design. (Severity: Low.)
- **`src/logic/mana_curve.py` and `src/logic/assessment/mana_base.py` still use the WHOLE-STRING
  land policy**, which disagrees with FR-05/UX-DR17 and with this story's front-face grouping on
  **84 corpus cards, 4 of them in real decks** (Agadeem's Awakening, Kazandu Mammoth, Dowsing
  Dagger, Journey to Eternity). The frontend is now correct and the Python is not, so the two will
  report different land counts for the same deck. **Home: c4-8** (the mana-curve panel), where it
  is a `src/logic` change with MCP blast radius and deserves its own decision. (Severity:
  **Medium** — two surfaces of one app disagreeing about a number is the exact failure the epic's
  "the grid and the list panel cannot disagree" clause is about, one layer out.)

## Deferred from: c4-3-card-placeholders-named-unknown-and-loading-wells (2026-08-04)

**Inherited deferrals, dispositions in one place** (C2 retro ruling R2). Twelve entries were
homed on or shared with this story; most have a disposition written beside their own entry above
— (4), (8) and (9) live only in this index, which is their disposition of record (corrected at
code review; the sentence previously claimed all twelve were annotated in place) — and this is
the index: (1) `ManaPip`/`ManaCost` appearance — **RESOLVED**, all five claims hold;
(2) the CVD question — **MEASURED**, levers not needed, open at Medium pending Brad's acceptance;
(3) the ` // ` separator spoken literally — **CONFIRMED LIVE, RE-HOMED to c4-7** with a sharpened
population; (4) whether copy is second-person and blameless — **HONOURED, does not close** (see
below); (5) the 79 no-image cards — **RESOLVED**, and their shape measured for the first time;
(6) the `states.ts` classification — **CONSUMED, not deleted**, which is the answer that entry
made conditional on this story; (7) a malformed card id renders nothing — **the render arrived**,
entry fully closed; (8) `Card` banned with no alias — **not needed** (see below); (9) `card_faces`
untyped — **no face consumed** (see below); (10) `useCardEntry` untested — **RESOLVED**;
(11) the `ui/tests` import rule — **TRIGGERED AND CLOSED**, and the rule is now stated precisely;
(12) the C3 retro's manual-testing items — this story adds its eye-check outcomes and nothing
else to that list.

- **Disposition (8), `Card` is banned with no sanctioned alias: NOT NEEDED, and the reason is
  structural rather than lucky.** `CardPlaceholder` takes four plain string props and imports no
  wire type at all — not even from `src/api/schema.ts`'s nine aliases. That is the posture
  `DeckBadges` set at c4-2 and it is the right one for a presentation primitive: a `CardSummary`
  prop would drag the wire alias into the component tree, which `posture.test.ts`'s cross-tree
  value-import ban and `wire-contract.test.ts`'s name ban both exist to prevent. **The caller does
  the reading and the component does the drawing.** No alias was added; the count stays at nine.

- **Disposition (9), `card_faces` is untyped on the wire: THIS STORY CONSUMES NO FACE, deliberately.**
  It renders `CardSummary`'s single `name` and single `type_line`, unsplit (Q5), and never touches
  `card_faces`. Face-specific rendering is **c4-6's**, where `CardFace` already ships with
  `extra="allow"`. The entry's home is unchanged.

- **Disposition (4), whether copy is second-person and blameless: HONOURED, and it does not close.**
  This story ships exactly one authored string, `"Unknown card"`, and it was read: sentence case,
  no exclamation mark, no blame, no apology, and it names a state rather than accusing the reader
  or the app. It is byte-for-byte the artefact's own label, so the judgement that matters was made
  in `EXPERIENCE.md`. The entry stays open permanently, as it says it does — c4-12 and c6-6 owe
  the same reading.

**New residues declared by this story.**

- **Whether an element carrying `card-shape` is actually a CARD is not decidable from a stylesheet
  (UX-DR4).** c4-3 made both halves of the card-radius rule a gate — nothing outside `CARD_SHAPED`
  may spend `--radius-card`, and no `CARD_SHAPED` file may spend a chrome radius — and both read
  CSS. The class list that puts the shape on an element lives in TSX and is chosen at runtime, so
  `.card-shape` on a `<nav>` reads as a perfectly clean stylesheet, and a card-shaped element given
  a chrome radius by a rule in a NON-card-shaped file (`.deck-row .card-shape { … }`) is in neither
  half. The guard says so in its own header and `ui/README.md` says so where c4-4's author will be
  reading. **Home: review, at every card-shaped story; c4-4 is the first where the cross-file case
  becomes plausible.** (Severity: Low — the gate covers the two realistic mistakes; this is the
  third.)

- **Nothing checks that the RIGHT type role was chosen for the content — MEASURED by a probe that
  PASSED.** Probe (j) of this story put the truncated card ID back into the uppercase
  `--type-micro` role, correctly paired with BOTH its companions so `findRoleWithoutCompanions` was
  satisfied, and **the whole suite stayed green at 1,021 passed**. Every typography guard in this
  repo asks whether a role travels with its companions; none asks whether the role suits the value.
  c4-3 closed the one instance — `.card-placeholder-id` is now checked against `cards.py`'s
  `_CARD_ID_PATTERN`, **read from the file**, so if the route ever accepts uppercase the guard's
  own premise fails loudly — but the general rule (*do not uppercase data the reader may type
  back*) is not statically decidable, because whether a string is retypeable lives in the product.
  **Home: review, at every story that renders an identifier, a set code or a command.**
  (Severity: Low individually, and the class is worth knowing about: it fails *legibly but
  wrongly*, which is the failure nobody looks at.)

- **Running `tests/token-usage.test.ts` ALONE crashes the runner, which can make a probe lie.**
  Measured at c4-3: `npx vitest run tests/token-usage.test.ts` fails with `TypeError: Cannot read
  properties of undefined (reading 'config')` — the file imports two `src/` modules across the
  project boundary, so resolving it standalone picks the wrong project. `npm test` runs it
  correctly and the tree is fine. **The reason this is ledgered rather than shrugged at**: the
  first run of this story's probe harness matched on exit code and reported **six guards as firing
  when the runner had merely crashed**, which is precisely the "a guard that fails for the wrong
  reason" defect this epic's reviews keep finding — in the instrument this time rather than in the
  code. All six were re-run against the full suite. **Home: anyone writing a probe against that
  file; the rule is "prove a guard fires with `npm test`, never a single-file run".**
  (Severity: Low, but it silently inverts a probe's result.)

- **The named placeholder's `overflow-wrap: anywhere` breaks long names mid-word, and it is a
  trade rather than a defect.** Measured on screen at the 176px grid floor: the 66-character
  doubled name of the largest permanent-population card renders as
  `Asmoranomardicadais / tinaculdacar // Asmoranomardicadais / tinaculdacar` across four lines. The
  alternative is a name that paints straight through the card edge, because a 31-character single
  word has nowhere legal to break at 176px. Accepted here; **c4-4 owns the grid and could revisit
  it** with a real column width in hand (a wider minimum column, or a line clamp with the full name
  still exposed to assistive tech). (Severity: Low — it is ugly for one card in 38,261, and it is
  correct for the 141-character name that motivated the rule.) **And the VERTICAL edge of the same
  trade, added at code review:** `.card-placeholder` pairs `overflow: hidden` with the fixed 63:88
  box and `justify-content: center`, so a name+pips+type stack TALLER than the box clips at both
  edges with no clamp and no ellipsis. Not reached by anything measured (the 141-char corpus name
  wraps inside the box at 176px, eye-checked), but nothing declares the limit either — same home,
  **c4-4**, same lever (a real column width, or a line clamp).

- **A whole view of loading wells is total silence to assistive technology — and nobody owns that
  question yet.** Added at c4-3's code review. Each well is `aria-hidden="true"` and
  EXPERIENCE.md:72 mandates exactly that PER TILE ("No copy. Wells stay silent") — but during
  first paint a grid is *nothing but* wells, so an AT user gets zero indication that anything is
  loading anywhere. Whether the VIEW (not the tile) should carry a single polite live-region note
  during load is a composition question this story structurally cannot answer — it mounts nothing.
  **Home: c4-4**, which owns the grid and the first composition an AT user will actually meet.
  (Severity: Low today — nothing mounts a well until c4-4 — but it should be decided there rather
  than inherited by accident.)

## Deferred from: code review of c4-3-card-placeholders-named-unknown-and-loading-wells (2026-08-04)

- **Running `ui/tests/token-usage.test.ts` standalone crashes the vitest runner** — the file
  imports two `src/` modules across the project boundary, and resolving it alone picks the wrong
  vitest project (`TypeError: Cannot read properties of undefined (reading 'config')`). The crash
  exits non-zero, which once made a probe harness report six guards as firing when nothing had
  asserted anything. Pre-existing project-resolution behaviour, not introduced by c4-3; the
  standing mitigation is the rule already ledgered above — a guard's firing is proven with the
  full `npm test`, never a standalone file run.

## Dispositions from: dev of c4-4-card-tile-and-the-card-art-grid (2026-08-04)

Every entry homed on `c4-4` gets a disposition here (C2 retro ruling **R2** — inherited deferrals
are acceptance criteria at context time). Twelve were listed in the story record; the line each
lives on is given so this section is checkable rather than merely reassuring.

1. **The pacer queue can outlive the connection-pool timeout (`:2617`)** — **NOT TRIGGERED, and
   the lever was exercised.** Q7 ruled that all ~99 `<img>` mount at once (`decoding="async"`, no
   `loading="lazy"`), which is the maximum burst this entry describes, and **no pacer constant was
   changed**. Measured live against the running backend with the 99-card deck: a fully warm paint
   is 99 requests in **0.55 s** (5.6 ms/tile) and never enters the pacer at all. The cold burst
   was not reproduced from a browser because the disk cache was already warm on this machine —
   **so the entry stands, unresolved, and `loading="lazy"` remains its one client-side lever.**
   Re-home: **c10-3**, which owns real-latency profiling, or the C4 retrospective.

2. **The image route reads the whole card row to get one URL (`:2742`)** — **NOT MEASURED, and
   declined here with a reason.** This story issues the requests in bulk but has no instrument for
   the backend's per-request cost, and the measurement that would settle it (a projection versus a
   whole-row read, under load) is a backend change with its own gates. What c4-4 CAN contribute is
   the volume it actually produces: 99 distinct ids, once per deck open. **Home: unchanged, C4
   retrospective**, with that number in hand.

3. **The backoff `502` answers with no `Retry-After` header (`:3213`)** — **DECLINED, and the UI
   is now in view, which is what this entry was waiting for.** The tile cannot use a `Retry-After`
   even if it were sent: a DOM `error` event carries no headers at all, and the SPA has no
   per-image retry UI by design. A header nobody can read is not worth a wire change. **Closed.**

4. **The named placeholder's `overflow-wrap: anywhere`, and the undeclared vertical edge
   (`:3623-3636`)** — **REVISITED with a real column width, and left as it is.** Seen at the
   eye-check at the 176px floor: the named placeholder renders name + type line centred with room
   to spare, and no mid-word break occurred on any real card in the deck. The vertical half is
   unchanged and still undeclared — a very tall stack would clip at both edges with no clamp.
   **Re-home: c4-5**, which renders the same component at detail size where a clamp would be
   visible, or review.

5. **A whole view of loading wells is total silence to assistive technology (`:3638-3646`)** —
   **RESOLVED IN STRUCTURE, with two declared corners (wording tightened by review 2026-08-04;
   the first record claimed it flat).** Each well is still `aria-hidden`, but a grid of them is
   no longer silent: every tile is a `<button>` named by its caption, so a first paint announces
   "list, 99 items" and each card by name whether or not its picture has arrived. A polite load
   note is not needed and is not added. The two corners the flat claim glossed: (a) a NAMELESS
   card yields an unnamed focusable button — zero population measured (0 of 1,061), the FR-13
   totality branch, and pinned as such by test; and (b) the announcement itself is
   jsdom-unverifiable — the NAME's exact spelling is now asserted (`Black Lotus ×4`, measured),
   but how a real screen reader phrases it is the epic checklist's, per the blind-spot row.

6. **Whether an element carrying `card-shape` is actually a CARD (`:3587-3596`)** — **REVIEW'S,
   and the cross-file case is now live.** c4-4 is the first story where a rule in one stylesheet
   reaches a card-shaped element in another: `CardTile.css` gives `> .card-shape` position and
   nothing else — no radius, no border, no background — and says so at the rule. Both directions
   are a reviewer's to check, unchanged.

7. **Nothing checks that the RIGHT type role was chosen for the content (`:3598`+)** — **SECOND
   INSTANCE, ruled in the open (Q3).** Every card name in the grid renders in CAPITALS because
   `findRoleWithoutCompanions` derives that requirement from DESIGN.md's own `label.textTransform`.
   Ruled correct on its merits — a card name here is a chrome label under a picture, not
   retypeable data like c4-3's truncated uuid, and browsers copy the untransformed text anyway —
   and confirmed by eye on a real screen. Still not statically decidable; **review's, unchanged.**

8. **The first paint against a fully dead CDN takes ~124 s (`:3131`)** — **NOT REPRODUCED.** The
   manual testing this entry names as its escalation condition was performed against a live,
   warm backend, so the dead-CDN path was never entered. Severity stays **Low**; **home: the epic
   manual-testing checklist**, where killing the CDN is a deliberate step rather than an accident.

9. **The `images.py` split decision (`:2989-2997`)** — **EVIDENCE FED FORWARD, not decided.** c4-4
   exercised the route, the pacer, the disk cache and the negative cache from a real browser for
   the first time and needed no change to any of them. **Home: unchanged, C4 retrospective**, with
   c4-6 still to add the flip control.

10. **c4-3's composition eye-check, re-homed here BY NAME (`ui/README.md`)** — **DONE.** A
    placeholder beside a real card face in a real grid, at the same footprint: confirmed in Edge
    against the running backend with the 99-card deck. Recorded in `ui/README.md` under _The card
    shape_.

11. **A `ui/tests/` file may import an app module only if that module has no relative imports** —
    **NOT TRIGGERED.** c4-4's new guards read source as TEXT, the idiom every other guard uses, so
    no new cross-project import was added. Confirmed with `npx tsc -b --force`, green.

12. **C3 retro action F1 — a gate banning story-key-shaped strings from rendered UI text** —
    **ONE OF THE SIX REMOVED.** The left column's placeholder (naming `c4-4` and `c4-8`) is
    displaced by the grid, and `App.test.tsx` now asserts neither string is on a rendered deck
    view. Five remain. **The gate itself stays c8-5's**, unchanged.

### New residues declared by c4-4

- **`CardPlaceholder` renders a `<div>`, and `<button>` takes phrasing content only.** Mounting
  the placeholder inside the tile is invalid HTML by the letter of the spec. Measured: every
  engine renders it, React does not warn, and the accessible name computes normally. Every
  alternative was worse (moving the placeholder out breaks UX-DR36's same-box claim; changing the
  primitive's root is an edit c4-4 was told not to make). **Home: c4-5**, which mounts the same
  component as detail art and can re-decide with two consumers in view. (Severity: Low.)

- **The reduced-motion transform guard compares SELECTOR TEXT.** A fallback whose selector differs
  from the motion's — even one the cascade would resolve correctly — reads as unregistered. False
  failure, not false pass; the repair is to write the matching selector. (Severity: Low.)

- **jsdom cannot report an accessible name's spelling.** It applies no CSS, so naming elements
  concatenate with no separator (`×4Black Lotus`). Component tests assert membership instead. The
  real announcement is **the epic manual-testing checklist's**, with a screen reader.

- **The warm-cache `onLoad` race is UNPROVEN in both directions.** `settleIfCached` reads
  `complete && naturalWidth > 0` on mount, and jsdom reports `complete: false` / `naturalWidth: 0`
  always — so the suite can only prove the guard does not fire wrongly. That it fires RIGHTLY
  needs a browser with a warm HTTP cache. **Home: the epic manual-testing checklist.**

- **A cold paint against a cold backend — OBSERVED at review, 2026-08-04 (this residue is
  closed).** Disk cache moved aside, 99-card deck active, real browser, real CDN. Two numbers,
  and they are DIFFERENT numbers: the backend's fetch window was **9.3 s for all 99 images**
  (measured from cache-file mtimes — the pacer's 0.1 s spacing turnstile binding exactly as
  modelled), while the PERCEIVED paint was **2–3 s** — the browser prioritises in-viewport
  images, so the visible screenful fills while the remaining tiles complete off-screen; on a
  fast connection each tile appears the instant the pacer releases it. No spinner, no
  broken-image glyph, no stuck tile. Net: the ~10 s figure is real but largely invisible; the
  epic's "expected observation, not a defect" framing holds, and the experienced cold paint is
  BETTER than the epic's expectation reads. What remains c10-3's is profiling (real bytes,
  real latency percentiles), and the ~124 s dead-CDN first paint remains unobserved — the CDN
  was alive. **Home: c10-3, narrowed to profiling and the dead-CDN case.**

## Deferred from: code review of c4-5-persistent-card-detail-panel-with-transient-and-pinned-inspection (2026-08-05)

- **The 21em oracle-text scroller is keyboard-unreachable.** `.card-detail-oracle` clamps at
  14 lines with `overflow-y: auto` and contains no focusable element, so a keyboard-only user
  cannot scroll the 63 corpus cards whose rules text exceeds 500 characters (WCAG 2.1.1). The
  standard fix — `tabindex="0"` plus a labelled `role="group"` on the scroller — fails the AC 25
  "not a modal" test (which asserts `[tabindex]` is absent from the panel) and adds a Tab stop
  UX-DR40's enumerated order does not contain. Both of those contracts are c4-11's to
  renegotiate: it owns the keyboard/focus story and the Tab-order additions. Ruled at review
  (Brad, 2026-08-05): defer, not fix-now. **Home: c4-11 — scope the AC 25 assertion, enumerate
  the new Tab stop, and make the scroller focusable in the same change.**

- **The MDFC pin announcement speaks the combined name; the panel renders the face name.** A
  faced card pinned before hydration announces the summary tier's `"Clearwater Pathway //
  Murkwater Pathway"` while the panel, once the record lands, renders the front face's
  `"Clearwater Pathway"` — the reader hears one name and reads another, for the ~6%-of-a-deck
  faced population. Deliberate (re-announcing on hydration is the H4/C1 flood), declared in
  `CardDetail.tsx`'s announcement comment at review 2026-08-05. **Home: the epic manual-testing
  checklist — hear it with a real screen reader beside the em-dash entry already there.**

## Deferred from: code review of c4-6-double-faced-card-flip-control (2026-08-06)

- **An in-flight hydration sweep is not cancelled on deck replacement.** `hydrateDeckCards` fires
  per `detail` identity with no abort path (`ui/src/App.tsx:213-216`), so switching decks mid-cold-
  open lets up to ~99 stale card reads compete with the new deck's ~99 images on the six-connection
  pool — the measured "+1.2 s tail" prices one sweep, not two overlapping ones. Not reachable
  today: `deck_changed` handling is Epic 5's. **Home: Epic 5 (deck switching).**
- **A failed FRONT face unmounts both stacked `<img>`s.** `CardTile`'s `art === 'failed'` arm
  replaces the whole `.card-faces` block, so a back face mid-load when the front errors never
  fires its `onLoad` and sticks at `'loading'`; flipping out of the failed face remounts both,
  re-requesting the known-failed front (answered from the backend's negative cache). Self-heals on
  remount; window is the flip-after-front-failure path only. **Home: unowned/latent — revisit if a
  partial-failure population ever appears (see the partially-imaged-card entry above).**
- **Three hand-rolled copies of the flippable wire fixture.** `CardTile.test.tsx`,
  `FlipControl.test.tsx` and `CardDetail.test.tsx` each restate the shape-C hydrated `Card`; when
  `CardFace` gains a field there are three places to drift. Test-only refactor: share one fixture
  helper. **Home: any later c4 story that touches these suites.**
- **A mid-sweep backend blip leaves cards unhydrated with no automatic re-sweep — accepted as
  designed (review ruling 2026-08-06).** c4-2's recovery re-drive fires only from `refused`/`none`,
  never while deck state is `deck` (`deck.ts:56-66`), so card reads refused during the sweep's
  ~1 s cold-open window stay unhydrated (no flip control, no hydrated panel text) until the card
  is individually inspected — which re-asks within the 3-attempt budget; one blip burns 1 of 3 —
  or the page reloads (`cards.ts:100-108` documents reload as the recovery deliberately). If this
  is ever met live, the written fix is: re-fire `hydrateDeckCards` over still-unhydrated retryable
  ids on the poll's recovery edge (the c4-2 pattern), plus a negative-space test — today no test
  exercises a failing sweep. **Home: unowned/latent, by ruling.**
- **AC 1's residue has a keyboard half the story record did not state (review 2026-08-06).** The
  flip control materialises when the sweep's record lands (~1 s window on the 99-card deck), so a
  keyboard user Tabbing during a cold open meets Tab stops appearing mid-traverse — the UX-DR40
  concern Q1 priced against the lazy alternative, present in miniature during the sweep window.
  Declared residue, not a defect: the window is one cold open per deck per tab and closes itself.
  Added to the epic manual-testing checklist (entry 5 in the c4-6 record). **Home: the epic
  manual-testing checklist.**
