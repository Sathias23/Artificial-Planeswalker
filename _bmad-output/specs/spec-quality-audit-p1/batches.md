# Batches

PR grouping for SPEC-quality-audit-p1. Three Greptile runs total. Order is top to bottom; batch 1
must merge before batches 3 and 4.

| Batch | Capabilities | Review | Files touched | Generated artifacts to rebuild |
|---|---|---|---|---|
| 0 | CAP-7, CAP-9, CAP-10, CAP-8 | no Greptile; one or two small PRs straight to master | `src/__init__.py`, `ui/package.json`, `SECURITY.md`, `.gitignore`, `.pre-commit-config.yaml`, `src/mcp_server/tools/{deck_management,card_search,semantic_search,find_similar,initialize_database,build_search_index}.py`, `.env.example`, `_bmad-output/implementation-artifacts/` → orphan `process` branch (plus any bmad config pointing `implementation_artifacts` at the worktree) | `plugin/` (tool changes) |
| 1 | CAP-5, CAP-6 | Greptile run 1 | `tests/**`, `ui/tests/**`, `ui/.stylelintrc.json`, `ui/eslint.config.js`, `ui/vite.config.ts`, `ui/package.json` scripts, `tests/fixtures/` (spellbook fixture) | none |
| 2 | CAP-1, CAP-2, CAP-11 | Greptile run 2 | `src/data/models/card.py`, `src/data/repositories/{card,deck}.py`, `src/data/importers/{scryfall,importer}.py`, `src/mcp_server/server.py`, `src/mcp_server/tools/deck_import.py`, `src/companion/client.py`, `src/search/embedder.py`, plus a migration path for the new index (existing DBs get it on `initialize_database` or on engine connect) | `plugin/` |
| 3 | CAP-3 | Greptile run 3 | `src/companion/app/routes/{decks,cards}.py`, `src/companion/contracts.py` (deck detail embeds `Card`), `src/companion/app/images.py`, `src/data/repositories/deck.py` (count-only list), `ui/src/state/{systemState,cards,deck}.ts`, `ui/src/App.tsx`, `ui/src/containers/Welcome`, `ui/public/hero.jpg` → `ui/src/assets/`, `ui/src/api/client.ts` | `ui/src/api/openapi.json` + `types.d.ts` via `npm run gen:api`, `src/companion/app/static/`, `plugin/` |
| 4 | CAP-4 | no Greptile; one PR for `src/`, one for `ui/` and config | every file above 65% comment share first: `state.py`, `security.py`, `images.py`, `main.py`, `client.py`, `server.py`; then `App.tsx`, `agentView.ts`, `cards.ts`, `client.ts`, `deck.ts`, `eslint.config.js`, `ci.yml`, `ui/package.json`, `ui/README.md` | `plugin/` |

## Preflight gate (before the first push of batches 1, 2, 3)

```
uv run ruff check . && uv run ruff format --check . && uv run mypy src/ && uv run mypy src/ --platform win32 && uv run pytest -m "not integration" -q
cd ui && npm run lint && npm run format:check && npm run typecheck && npm test -- --run && npm run build && npm run gen:types && cd ..
uv run python -m scripts.build_plugin && git status --porcelain
```

A non-empty porcelain line means a generated artifact moved; commit it before pushing.

## Baselines to beat (measured 2026-09-03)

| Measure | Baseline | Target |
|---|---|---|
| Exact name lookup | 67–72 ms, `SCAN cards` | ~1 ms, index search |
| 100-line Commander import | 7–10 s | < 0.5 s |
| `/api/decks` on 52 decks | 117–160 ms | count-only, no card rows |
| Cold open, `cdp_harness budget` median | 529 ms (quiet), 587–798 ms (under load) | ≥ 150 ms lower, quiet run |
| MCP import time | 1.37 s incl. ~250 ms fastembed stack | fastembed absent from import |
| Python unit job | 247 s, 3,340 tests | ≥ 25% faster |
| `ui/tests` node project | needs 180 s timeout | default timeout |
| Coverage: `spellbook.py` / `scryfall_api.py` / `combo_snapshot.py` | 49% / 55% / 55% | ≥ 85% each |
| Tools with a `call_tool` round trip | 14 of 23 | 23 of 23 |
| Comment share, worst six `src/` files | 68–81% | < 50% |

## What CAP-5 deletes, by file

- `tests/unit/companion/test_ws.py`: identifier and source scans (`:378`, `:503`, `:923`, `:1127`),
  docstring assert (`:1142`), doctest runner (`:931-992`, move to `--doctest-modules` if kept).
- `tests/unit/companion/test_images.py`: construction-site and rename-site scans (`:1023-1212`,
  `:2532`), docstring-prose asserts (`:561-585`, `:2186`), constant pins (`:537-546`), planted
  scanner tests (`:1043`, `:1064`, `:1171`, `:1193`, `:1322`, `:1349`, `:1363`, `:2409`, `:2421`).
- `tests/unit/companion/test_routes_card_image.py`: `TestNothingThisStoryDoesNotOwn`
  (`:834-1035`) and its planted cases (`:902-1035`).
- `tests/unit/companion/test_client.py`: constant equality pins in `TestExportedSurface`
  (`:547-605`); keep the relational asserts.
- `tests/unit/viewer/test_viewer_freeze.py`: everything except `TestViewerIsFrozen` and
  `TestCompanionNeverReusesTheViewer`.
- `tests/unit/companion/test_import_boundary.py`: keep the boundary gates; drop
  `TestWriteGuardDetectsViolations` and `TestLeafAppGuardDetectsViolations` (`:828-1230`).
- `tests/integration/mcp_server/test_companion_tool.py`: collapse the four copy-paste class sets
  (`:582`, `:791`, `:985`, `:1185`) into one parametrised set.
- Docs-drift: delete `test_companion_docs.py`, `test_prd_reconciliation.py`,
  `test_image_cache_docs.py`; relocate only the two "documented port / cache filename equals the
  shipped constant" checks into `test_server.py` and `test_images.py`.
- `ui/tests/`: `shell.test.ts`, `token-usage.test.ts`, `keyboard-floor.test.ts` static parts,
  `copy-rules.test.ts`, `lint-gates.test.ts` (to a `test:gates` script), `devProxyRoundTrip.test.ts`
  (same script). CSS value rules become stylelint `declaration-property-value-allowed-list` entries;
  copy bans become an eslint `no-restricted-syntax` entry.

## What CAP-6 adds

- `tests/integration/data/test_spellbook_import_e2e.py`: three-variant fixture file, one malformed
  header case, skip accounting, DB write path.
- `tests/unit/data/importers/test_scryfall_api.py`: `MockTransport` cases for 200, 5xx, timeout,
  oversize, mirroring the existing spellbook download tests.
- `tests/unit/data/test_combo_snapshot_repository.py`: no snapshot, stale snapshot, empty names,
  case folding.
- `tests/integration/test_mcp_tools.py`: one round trip each for `import_decklist`,
  `initialize_database`, `remove_card_from_deck`, `compare_deck_power`,
  `companion_show_suggestions`, `companion_show_swaps`, `companion_show_tier_list`,
  `companion_show_groups`.
