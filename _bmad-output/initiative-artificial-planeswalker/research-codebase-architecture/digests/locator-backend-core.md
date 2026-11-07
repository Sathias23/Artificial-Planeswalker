# Locator digest — src/data, src/logic, src/search, src/paths.py, src/__init__.py @ ee0263d

## Q1
- No import of src.mcp_server / src.companion / src.viewer / fastapi / starlette / mcp / uvicorn in the area; names appear only in docstrings: src/data/database.py:92 (enable_foreign_keys), :246 (create_engine), src/data/schemas/card.py:5-27, src/data/schemas/deck.py:234 (DeckSummary.from_deck), src/data/importers/transformers.py:274, src/paths.py:3-4 (states data -> logic -> mcp_server).
- httpx is imported: src/data/importers/scryfall_api.py:8, src/data/importers/spellbook_api.py:23.
- Third party: sqlalchemy (database.py:10-16, import_state.py:22-23, importers, models, repositories; deck.py:9-13 joinedload/selectinload); pydantic (schemas, src/logic/deck_validator.py:22, src/logic/synergy.py:13); ijson (parser.py:27, spellbook.py:31); sqlite_vec (search/connection.py:9, index_builder.py:11, query.py:32); numpy (embedder.py:10, query.py:31); fastembed lazy (embedder.py:16,29 _load_text_embedding); platformdirs (paths.py:18); logfire lazy (database.py:274).
- src/logic imports only src.data.schemas.* and src.logic.* (deck_validator.py:24-25, mana_curve.py:10, synergy.py:15, assessment/classifiers.py:25-26, assessment/combos.py:40-42, assessment/__init__.py:8).
- src/search/query.py:35 imports src.data.import_state.is_import_in_progress_sync (only src.data import in search); search/connection.py:11, embedder.py:13 import src.paths; database.py:35 imports src.paths.database_url.

## Q2 (area part)
- src/data/database.py:238 (create_engine) ensure_indexes flag; False skips ensure_nocase_indexes and remove_orphan_deck_cards; enable_foreign_keys registered on every engine (:265-269). :108 PRAGMA foreign_keys=ON. :39-42,80 CREATE INDEX DDL. :165-233 (remove_orphan_deck_cards) raw DELETE + _repair_deck_metadata (:145) + commit.
- src/data/import_state.py:40-52 raw-SQL writes to import_state.
- src/search/connection.py:134-146 (ConnectionFactory._build_connection) sqlite3.connect, sqlite_vec.load, PRAGMA WAL/busy_timeout/foreign_keys.
- Mutable state: src/search/embedder.py:195-196,215,231 (_embedder, _lock, get_embedder, reset_embedder) global singleton; src/search/connection.py:98 threading.local per-thread connections.

## Q3
- Only a comment: src/data/importers/transformers.py:274.

## Q4
- Assessment: src/logic/assessment/aggregate.py:48-54 reason constants, :61 CONFIDENCE_REASON_TOKENS, :71,74 ConfidenceLevel Literal + CONFIDENCE_LEVELS tuple (spelled twice); consistency.py:302 STRUCTURAL_GAP_TOKENS; combos.py:77 COMBO_TYPE_TOKENS; profiles.py:49,55 TierLabel Literal + TIER_LABELS tuple; profiles.py:122; mana_base.py:57; assessment/__init__.py:14,40,53 re-exports.
- Validator: src/logic/deck_validator.py:233-241 DeckViolationRule; :475 FormatCheckStatus; :484,487-493 FormatCheckName Literal + CHECK_ORDER tuple; :502 CHECK_FOR_RULE; :546.
- src/data/schemas/combo.py:58 ComboBucket, :63 ComboBracketTag.
- Colour mode twice: src/data/repositories/card.py:399 (search_advanced color_mode), src/search/query.py:47 (ColorMode).
- src/data/repositories/deck.py:1008 merge_decks strategy Literal alongside MergeStrategy enum; src/logic/mana_curve.py:28; src/logic/synergy.py:47,51,72 and strength Literal repeated at :177,278,376,444,508,588; src/search/connection.py:89.
- Importer reasons: spellbook.py:76,145,320-324; transformers.py:21-32,229 free-form.
- src/data/database.py:350 docstring names database_not_initialized.

## Q5
- src/data/repositories/card.py:126 (get_by_id); :154-205 (find_by_name_exact) NOCASE equality on name/printed_name, order_by(id).limit(1); :213-253 (find_by_name_partial) ilike('%q%'), no limit.
- src/data/repositories/deck.py:435-452 (find_deck_by_name) ilike; :521 (add_card_to_deck) session.get(CardModel); :616-627 (add_cards_to_deck) batched IN.
- src/data/models/card.py:10-15,27-28 and database.py:39-42 NOCASE indexes.
- src/search/query.py:145 (get_card_vector).
- src/data/schemas/combo.py:34 (name_keys) used by combo_snapshot.py:108-166 (get_variants_for_names) and logic/assessment/combos.py:41; piece.lower() at combos.py:185-187,256.

## Q6
- WUBRG defined in five places: src/data/database.py:139 (_WUBRG) used :158; src/data/importers/transformers.py:47 (_WUBRG) used :150; src/data/repositories/deck.py:28 (_WUBRG_ORDER) used :872; src/logic/assessment/mana_base.py:33 (WUBRG); src/search/schema.py:17 (COLOR_COLS), letters at index_builder.py:59 and query.py:51.
- Colour identity: deck.py:838-873 (_refresh_deck_metadata), :929 (update_deck_color_identity); database.py:145 (_repair_deck_metadata) raw-SQL version; schemas/deck.py:98; models/deck.py:70-85.
- Colour filtering twice: card.py:257-300 (find_by_colors), :491-529 (search_advanced) JSON LIKE; search/query.py:117 (_color_predicates) vec0 flags.
- Mana/pips: assessment/mana_base.py:228 (_MANA_SYMBOL_RE), :303 (_pip_cost), :341 (compute_pip_signals), :248.
- Type line: lowercase "land" in: mana_base.py:69 (_is_land), classifiers.py:280 (classify_card); case-sensitive "Land" in: mana_curve.py:74, :277; deck_validator.py:41-65 (is_basic_land); consistency.py:210-216; synergy.py:135,550-569 (_extract_creature_types); mana_base.py:241,330; card.py:331,534 type_line ilike.
- Legality: deck_validator.py:184-204, :294-346 (validate_deck), :644 (format_check); card.py:39-67 (_apply_format_filter) json_extract; search/query.py:336-337 second json_extract filter.
- Quantity: deck_validator.py:141 (max_copies=4) and :179,181 (_MIN_MAINBOARD=60, _MAX_COPIES=4) — 4 copies twice; schemas/deck.py:33 and :58 identical >=1 validators; schemas/deck.py:129 (_counts), :230; deck.py:374-432 (list_deck_summaries) SQL SUM/CASE counts.
- Curve: logic/mana_curve.py:58-111 and assessment/mana_base.py:107 (compute_curve) — two curves.
- Reminder-text stripping: assessment/classifiers.py:79-87 (_strip_reminder_text) and search/index_builder.py:136-173 (strip_reminder_text) same regexes. _coerce_json_list: search/query.py:99 and index_builder.py:353. is_database_initialized: async database.py:343, sync search/query.py:220.

## Q7
- CardRepository: get_by_id :145 PK; find_by_name_exact :196-204 NOCASE LIMIT 1; no LIMIT: find_by_name_partial :246-253, find_by_colors :286-300, find_by_type :331-336, search_by_keywords :371-381; search_advanced :491-589 count subquery (:577) then offset/limit (:585); _apply_unique_oracle_filter :98-124 CTE min(id) group by oracle_id; _apply_games_filter :69-96 cast + LIKE.
- DeckRepository: clone_deck :151-154 joinedload; get_deck :211, find_deck_by_name :451 no eager load; list_decks :362-370 selectinload(deck_cards).selectinload(card), no LIMIT; list_deck_summaries :407-416 outerjoin group_by no LIMIT; get_deck_with_cards :992-996 selectinload; add_card_to_deck :561-567, add_cards_to_deck :670-677, update_card_quantity :787-793 reload with selectinload; _refresh_deck_metadata :859-869.
- combo_snapshot.py :52-56, :84-85 limit(1); :142-149 name_key IN subquery.
- Indexes: models/card.py id PK :32, name index :35, printed_name index :37, NOCASE pair :27-28; database.py:39-42; models/deck.py id PK :28, name/format/strategy index :32-35; models/deck_card.py:27-35 composite PK (deck_id, card_id, sideboard) + FKs; models/combo.py :32, :101 ix_combo_variant_pieces_name_key, :103-104. No index on cards.oracle_id, type_line, cmc, legalities, games.
- Per-item loops: deck.py:1078-1117 (merge_decks) update_card_quantity/add_card_to_deck per source card (each: flush, _refresh_deck_metadata, session.get, reload); :1056-1057,1168 get_deck_with_cards three times.

## Q8
- Off-loop: importers/importer.py:121 to_thread(_next_chunk); importers/scryfall.py:432 to_thread(build_oracle_aggregates).
- Blocking inside async def: importers/spellbook.py:310-313 (import_spellbook_snapshot) _read_export_header/_stream_variants gzip+ijson (:201, :242) and transform inline; :300 mkdtemp, :400 rmtree; scryfall.py:413,496 mkdtemp/rmtree; scryfall_api.py:123-131 (download_bulk_data) sync open/f.write inside async for aiter_bytes; spellbook_api.py:105-115 same with aiter_raw.
- src/search is all sync; docstrings expect to_thread (connection.py:61, embedder.py:193).
- sqlite-vec path: connection.py:105-117 (get_connection) threading.local, check_same_thread True; :120-146 _build_connection. embedder.py:199-217 (get_embedder) singleton under lock; :120 TextEmbedding load; MODEL_NAME BAAI/bge-small-en-v1.5 dim 384 (:39-40); paths.py:53; encode :137, encode_batch :166. query.py:254-397 (hybrid_search) limit=10, over_fetch_k=200; CTE MATCH ? AND k = ? with mana/colour predicates inside vec0 (:320-331, :346-352); JOIN cards with json_extract legality + games LIKE after join (:334-343, :356); order by distance, de-dupe by oracle_id in Python, stop at limit (:363-390). query.py:190 (index_is_populated), :220-251 (is_database_initialized -> import_state.py:69). index_builder.py:247 (build_card_embeddings), _READ_CARDS_SQL :54, LIMIT ? :327 only when limit set, _process_chunk :387.

## Q9
- No route code. src/data/models/card.py:96 image_uris; schemas/card.py:35-58 IMAGE_DISCRIMINATOR, :108, :192; transformers.py:318-320; paths.py:23 data_dir.

## Q10
- Only src/data/schemas/card.py:8 (descriptions ship into ui/src/api/types.d.ts).

## Found nothing @ ee0263d
- framework or upper-layer imports; lru_cache/functools; run_in_executor; json.load( (only json.loads per line parser.py:90, plus ijson); card-image/scryfall_id/image_cache; zustand/fetch(; index on oracle_id/type_line/cmc/legalities; to_thread under src/search (docstrings only).
