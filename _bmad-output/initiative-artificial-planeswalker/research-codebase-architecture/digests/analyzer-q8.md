# Analyzer Q8 — blocking work on async paths; sqlite-vec end to end @ ee0263d

(15 of 15 files. LB = load-bearing.)

## MCP server loop
- LB initialize_database awaited with no to_thread: `return await _initialize_database_helper(update=update)` src/mcp_server/server.py:1192; neighbours use to_thread (server.py:1090, 1158, 1217). Helper builds its own engine, init_database, counts, importer on aiosqlite src/mcp_server/tools/initialize_database.py:161-193; raw DELETE on failure via aiosqlite initialize_database.py:119-123 (_clear_cards).
- Scryfall import src/data/importers/scryfall.py:344-509 (import_scryfall_bulk_data):
  - metadata fetch async; response.json() small payload src/data/importers/scryfall_api.py:42-53 (fetch_bulk_data_list).
  - download: async aiter_bytes(10 MB) but sync output_path.open("wb") + f.write(chunk) on the loop, ~50 x 10 MB writes for ~500 MB scryfall_api.py:97-131 (download_bulk_data); max_bytes ceiling :111-130.
  - mkdtemp scryfall.py:413, rmtree of ~500 MB dir scryfall.py:495-496 on loop.
  - pass 1 to_thread(build_oracle_aggregates) scryfall.py:432; pass 2 to_thread(_next_chunk) 1,000 at a time src/data/importers/importer.py:118-121.
  - batch insert on loop: 23-key dict per card + compile of 1,000-row sqlite_insert upsert importer.py:167-200 (_insert_batch).
  - reconcile on loop: reads every cards row (id, oracle_id, games), Python plan_identity_dedup + games-union diff, linear in ~60k rows scryfall.py:230-284 (reconcile_oracle_identities).
  - Net: minutes-long tool call; loop stalls during each 10 MB write, each batch dict build/compile, reconcile pass.
- import_decklist _parse_arena_export sync on loop deck_import.py:397, input capped 50,000 chars deck_import.py:43, :376-380.
- Companion client on MCP loop: read_discovery() sync on every live_instance/push/active-deck attempt src/companion/client.py:232, :337, :506; discovery_path() mkdir + read_bytes + model_validate_json src/companion/discovery.py:199-208; tiny file.
- Off loop: view_deck tools/view_deck.py:97; semantic/find-similar/build-index server.py:1074-1090, 1143-1158, 1217-1219.
- __main__.py:78-100 sync sqlite3 startup diagnostic before server starts.

## Companion loop
- Startup lifespan: _publish_discovery -> write_discovery sync (mkstemp, write, fsync, chmod, os.replace) src/companion/app/main.py:63, :136; discovery.py:152-169; build_image_cache mkdir main.py:134, images.py:606-618 — before yield, no requests yet.
- Shutdown remove_discovery main.py:82.
- First request Database._create: database_url() mkdir + path.exists() under asyncio.Lock src/companion/app/deps.py:123, :150-181; raises database_not_initialized when absent (:173-175); factory cached only on success (:154), so while DB missing every request repeats mkdir+exists under the lock (microseconds).
- Image cache via to_thread images.py:521, :569; sync work in workers images.py:376, :422-463.

## Scripts loop
- Spellbook import only from scripts/import_spellbook_combos.py:96 under asyncio.run (:132); no MCP/companion caller. Inside import_snapshot (src/data/importers/spellbook.py:265-404) everything on that loop: mkdtemp :300; sync f.write over aiter_raw src/data/importers/spellbook_api.py:105-115; gzip+ijson header pass :220-232; full parse of ~579 MB JSON into ~100k records :257-258, :310-317; json.dumps :336-353; executemany :362-376; rmtree :400. Rejections :227-239, :327-332.

## sqlite-vec end to end
1. LB tool -> asyncio.to_thread(_run) server.py:1074-1090, 1143-1158.
2. ConnectionFactory.get_connection threading.local, one per thread, check_same_thread True, closed only by close() on that thread src/search/connection.py:98, :105-118; process keeps up to one connection per executor thread. _build_connection connect, enable_load_extension, sqlite_vec.load, disable, WAL, busy_timeout=5000, foreign_keys=ON connection.py:134-146.
3. get_embedder process singleton double-checked threading.Lock src/search/embedder.py:199-220; first call mkdir cache, import fastembed, load/download TextEmbedding embedder.py:110-120, in the worker. find_similar never embeds (server.py:1141-1142).
4. limit 1.._MAX_LIMIT=50 semantic_search.py:45, :128-131; find_similar.py:54, :198-201; is_database_initialized query.py:220-251; index_is_populated semantic_search.py:203, :213; find_similar.py:376, :384.
5. encode one ONNX pass semantic_search.py:220, embedder.py:156-164. Seed: id lookup find_similar.py:227; exact LIMIT 1 :241-244; fuzzy lower(name) LIKE lower(?) ORDER BY id, no LIMIT, fetchall :252-258. get_card_vector WHERE card_id = ? query.py:181-187.
6. LB hybrid_search query.py:254-399: limit=10, over_fetch_k=200; neither caller passes over_fetch_k so k=200 always. CTE `embedding MATCH ? AND k = ?` + mana bounds + colour flags inside KNN (:320-331, :346-351). Outside on JOIN cards: json_extract legality + cast(games) LIKE OR (:333-343, :356); ORDER BY distance, fetchall (:357-360). Python skips exclude_oracle_id and repeat oracle ids, decodes colors JSON, stops at limit (:364-390).
- LB When post-JOIN filters reject most of 200: no widening, no second pass; result is whatever of the 200 nearest passes legality/games/seed/de-dupe, capped at limit; matches ranked 201+ never considered; can be short or empty -> status="empty" (semantic_search.py:235; find_similar.py:427). Legality and games filters can starve; colour/mana cannot (inside KNN).

## Outside the question
- initialize_database result tells caller to re-run "build_search_index with prune=true" initialize_database.py:199-202; MCP tool takes only build_search_index(rebuild: bool = False) server.py:1195 and passes no prune server.py:1217-1219; helper accepts prune build_search_index.py:58, :94.

## Not checked
- Bodies of semantic_search.py / find_similar.py beyond grepped lines; index_builder.py beyond grep; companion routes and WS handlers (grep hit deps.py, images.py, server.py:224 webbrowser.open, singleton.py); aiosqlite and MCP SDK internals.
