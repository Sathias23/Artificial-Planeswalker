# Quality audit — 2026-09-03

Master at `9a0cb4e`, v0.5.0 tagged. Six read-only reviews (Python quality, security, performance, Python tests, UI code and tests, repo hygiene), each verified against code; SQL timings via EXPLAIN QUERY PLAN on the real `cards.db` (38,626 cards, 52 decks); import time via `python -X importtime`. No P0 findings.

## Headline numbers

| Metric | Value |
|---|---|
| Python unit tests | 3,340 passed in 247 s; 93% line coverage of `src/` |
| UI tests | 2,616 passed in 78 s; 0 act warnings |
| Comment share | 53% of `src/` (15k of 28.5k lines); 74% of `ui/src/` (14k of 19k) |
| Exact card-name lookup | 67–72 ms (full scan) vs 0.01 ms indexed |
| Deck-list route | 117–160 ms, hydrates 2,730 card rows |
| MCP import time | 1.37 s, of which fastembed/onnxruntime/PIL ~250 ms |
| JS bundle | 254 KB raw / 77 KB gzip; hero.jpg 420 KB |
| Clone pack | 22.95 MiB; `_bmad-output/` 249 files, ~10 MB |

## P1

1. **Exact name lookup is a full-table scan; import pays it per line.** `src/data/repositories/card.py:187` `ilike(name)` compiles to `lower(name) LIKE lower(?)`, unindexable. `deck_import.py:414` → `_resolve_card` per line, then `deck.py:341` commit (fsync, `synchronous=FULL`) and reload. 100-line import ≈ 7–10 s. Unmatched lines also pay `find_by_name_partial` (96 ms). Fix: `COLLATE NOCASE` index on `name`/`printed_name`, `.collate("NOCASE") ==`; single-transaction import with one commit and one `selectinload` reload.
2. **Sync MCP tools block the event loop.** `server.py:8` claims FastMCP threadpools sync tools; mcp 1.27 `func_metadata.py:96` calls them inline. `semantic_search_cards` (:931), `find_similar_cards` (:989), `build_search_index` (:1085) freeze pings/cancellation/companion pushes; first call also loads the ONNX model on-loop. `initialize_database`: `scryfall.py:428` `build_oracle_aggregates` sync full pass, `importer.py:107` sync ijson generator between awaits. Fix: `asyncio.to_thread`; ConnectionFactory is thread-local, embedder lock-guarded.
3. **Companion cold open ≈ 200 requests.** `routes/decks.py:58` → `list_decks` with `selectinload(deck_cards).selectinload(card)` (117–160 ms) on the UI poller at mount (`systemState.ts:240`). `cards.ts:621` fans out one `GET /api/cards/{id}` per card; route sends no Cache-Control/ETag. Image route (`routes/cards.py:298`) does `get_by_id` before the disk-cache read (:330). Initial panel `'no-active-deck'` (`systemState.ts:96`) renders `<Welcome>` → `/hero.jpg` (420 KB, unhashed, `no-cache`) during the transient frame. Budget baseline 529 ms median (cdp_harness `budget`).
4. **Narrative comments dominate.** Markers in `src/*.py`: `AD-nn` 484, dates 157, `Story N` 126, `AC n` 112, maintainer name 90, Greptile 15. Highest-ratio files: `state.py` ~81%, `security.py` 76%, `images.py` 74%, `main.py` 70%, `client.py` 69%, `server.py` 68%. UI: 366 comment lines with dates/name/ruling/Greptile/round, 1,635 story tokens. Examples: `App.tsx:558-597` (40 lines on a two-child fragment), `images.py:37-40` (comment about a previous comment), `server.py:122-155` (30-line docstring on a 6-line function), `eslint.config.js` (~120 comment lines for a 2-selector rule incl. a retracted prediction), `ci.yml` 48% comment, `ui/README.md` 192 KB, `ui/package.json` `"//"` block ~3 KB.
5. **Lint-as-tests.** Python: 114 source-text/AST assertions in 29 files (`test_ws.py` 25 ast + 13 read_text; `test_images.py` 24 + 9; `test_viewer_freeze.py` 23 read_text). Examples: `test_ws.py:378,503,923,1127`; `test_images.py:1023-1212,2532`; `test_routes_card_image.py:834-1035`. Docstring-prose asserts: `test_images.py:561-585,2186`, `test_ws.py:1142`. Constant pins: `test_client.py:547-605`, `test_images.py:537-546`. Scanner meta-tests: 127 (`test_viewer_freeze.py:1056-1350`, `test_import_boundary.py:828-1230`). Docs-drift suites ~2,300 lines: `test_companion_docs.py`, `test_prd_reconciliation.py`, `test_image_cache_docs.py` (executes an `rm -rf` from a fenced block). `test_companion_tool.py` is 4× copy-paste (16 classes, ~800 lines). `test_viewer_freeze.py` 1,747 lines freezes a deprecated package. UI: 29 of 33 `ui/tests/` files `readFileSync` source; `shell.test.ts` (73 tests) and `token-usage.test.ts` regex-parse CSS and assert property values (`:680-691,744,762`), incl. a test forbidding CSS nesting because the reader cannot parse it (`:1649`); `lint-gates.test.ts` runs ESLint 13× (cold `projectService` ~100 s, `testTimeout: 180_000`); `devProxyRoundTrip.test.ts` boots a real Vite server. Keep: `test_import_boundary.py` boundary gates, `test_openapi_contract.py`, `tokens.test.ts`, `package-contract.test.ts`, `no-scryfall-hosts.test.ts`.
6. **Import layer under-tested; MCP wire unproven for 9 tools.** `spellbook.py` 49% (`import_spellbook_snapshot` :295-404 zero coverage), `scryfall_api.py` 55% (:42-67, :136-172), `combo_snapshot.py` 55% (`get_snapshot_state`, `get_metadata`, `get_variants_for_names`). Never called via `client.call_tool`: `import_decklist`, `initialize_database`, `remove_card_from_deck`, `compare_deck_power`, `companion_show_{suggestions,swaps,tier_list,groups}` (happy path). Also `mana_curve.py` 83% (:418-432, :484-507, :579-590), `deck.py` 80% (:95-117, :714-736).
7. **Version/support metadata.** `src/__init__.py:3` `0.1.0`; `ui/package.json` `0.0.0`; pyproject and plugin manifests `0.5.0`. `SECURITY.md:9` supports `0.2.x` only; no mention of the companion HTTP/WS surface.
8. **Process artifacts.** `_bmad-output/` 249 files / 10 MB (173 closed stories under `implementation-artifacts/archive/`); `sprint-status.yaml` 233 commits, `deferred-work.md` 143 commits at 604 KB (~9 MB of pack). 20 tracked files contain `C:\Users\brads`; one in `scripts/vitest_probe_harness.py:116`.

## P2 riders folded into the P1 batches

- **11 (part):** `add_card_to_deck.quantity` no ceiling (`deck_management.py:386`; import caps 250 at `deck_import.py:36`); deck `name`/`strategy`/`tags` unbounded (`deck_management.py:247-259`); `page`/mana bounds accept NaN/inf (`card_search.py:92-106`, `query.py:325`). `initialize_database(update=true)` / `build_search_index` lack destructive annotations. `MCP_TRANSPORT=sse|streamable-http` (`__main__.py:122`, `.env.example:30`) listens with no auth/Host check.
- **17 (part):** tracked `node_modules/.vite/vitest/.../results.json`; root `.gitignore` lacks `node_modules/`; unanchored `lib/`, `build/`, `dist/` (`.gitignore:25,31`) — `ui/src/lib/x.ts` would be ignored; uncommitted diff removes `/graphify-out/` (dir is gone locally).
- **18:** `client.py:327` `live_instance` → `probe_health` (:285, new AsyncClient) then `_send` (:389, new client); `_emit_deck_changed` after every mutation. `embedder.py:10` imports fastembed at module top (~250 ms of boot).

## P2 / P3 not in scope here

9 UI payload validation + error boundary; 10 package named `src` + `setup.py`; 12 FTS5 + json_each; 13 duplicated helpers; 14 fixture scoping + real timers; 15 App.test.tsx split; 16 coverage gate, ruff rules, mypy on tests/scripts, dependabot, timeouts, release workflow, npm audit; 19 module splits + viewer removal; 20 docs drift + README; P3 list (LIKE escaping, init-check decorator, logging, PRAGMAs, `__all__`, UI abort signals, index keys, px literals, .gitattributes, trivial tests).

## Already good

Loopback-only bind; exact Host/Origin checks; single-use tickets; constant-time bearer compare; no CORS by design; 64 KB ASGI body cap; SSRF-restricted image proxy with 16 MB cap; bulk downloads capped on compressed bytes; strict UUID paths; no eval/pickle/shell=True; telemetry never configured; SHA-pinned actions with `contents: read`. mypy strict both platforms, 4 type-ignores, 0 explicit `any` in UI. Typed MCP envelopes. Careful async I/O in the companion. UI: 3 runtime deps, generation-guarded async, backoff reconnect, fetch timeouts, landmarks, focus management, reduced motion. 14 tools driven through a real MCP client session with byte-determinism.
