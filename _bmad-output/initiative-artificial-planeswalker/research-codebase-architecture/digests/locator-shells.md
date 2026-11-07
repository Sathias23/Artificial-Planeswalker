# Locator digest — src/mcp_server, src/companion (no app/static), src/viewer @ ee0263d

## Q1
- mcp_server -> companion: src/mcp_server/server.py:48-50 (aclose_shared_client, notify_deck_changed, contracts); :66-79 companion tool helpers; src/mcp_server/tools/companion.py:40-45 (base_url, live_instance, probe_health, push_event, set_active_deck from src.companion.client; contracts); src/mcp_server/__main__.py:243 lazy `from src.companion.app.server import run` (subcommand dispatcher).
- mcp_server -> data/logic/search/viewer: server.py:56, :122; tools/assess_deck_power.py:30-35; compare_deck_power.py:32-34; deck_analysis.py:25-32; deck_management.py:40-44 (DeckRepository and the private `_UNSET`); deck_import.py:12-17 (+ deck_management helpers); card_lookup.py:15-17; card_search.py:19-21; find_similar.py:29-36; semantic_search.py:21-28; build_search_index.py:18-27; initialize_database.py:31-38; view_deck.py:31-34.
- companion -> data/logic/paths: app/deps.py:55-56; app/images.py:31 (CardFace); app/routes/cards.py:56-57; app/routes/decks.py:25-27 (DeckRepository, DeckDetailFull, DeckSummary, src.logic.deck_validator.format_check — only src.logic import); app/singleton.py:52, discovery.py:46 (src.paths); lazy in-function imports of src.companion.app.main at app/security.py:117,201, app/ws.py:251.
- viewer imports only src.data.schemas.card/deck: present.py:20, render.py:6, view_model.py:14-15.
- companion -> mcp_server: none (docstrings only: companion/__init__.py:1,5; client.py:23,433). app/deps.py:32-35 names test_import_boundary.py.

## Q2
- File writes: discovery.py:115 (write_discovery) mkstemp :152, fsync :166-167, os.replace :169; :211 (remove_discovery); app/main.py:37 (_publish_discovery) called :63, :82 (_shutdown); app/images.py:401 (_write_atomically) mkdir :422, mkstemp :423, unlink displaced siblings :436, os.replace :445, no fsync; path images.py:335 (_cache_path), :307 (cache_root), :107; :606 (build_image_cache) :618 mkdir; :532 (DiskCache.write) via to_thread :569; app/singleton.py:97 (acquire_instance_lock) os.open O_CREAT companion.lock (:127, :65), never unlinked.
- DB: app/deps.py:157 (Database._create) create_engine(url, ensure_indexes=False) :182 (comment :176: skips NOCASE DDL and orphan sweep); :240 get_session read-only by convention, no mode=ro (:32).
- In-memory state: main.py:95 lifespan; state.py:25 ActiveDeckSlot, :75 TicketStore, :197 ConnectionRegistry.add.
- mcp_server mutable state: server.py:184-187 (build_server) closure captures session_factory, connection_factory, embedder; :1074-1076 get_embedder process singleton; :188-195 (_lifespan) aclose_shared_client; src/companion/client.py:135 (_shared) module global (loop, httpx.AsyncClient) written :151-158, :164, :170-174 via global, read via _shared_client (:202, :278). Read-only constants: tools/companion.py:128 (_MESSAGES), :312, :408, :497, :651; :712 (_INSTALL_ROOT); assess_deck_power.py:57 (_FORMAT_PROFILES).

## Q3
- src/viewer/__init__.py:1-21 FROZEN (AD-15) exports; present.py:39 (present_deck) write_text :55 to temp path (present.py:30 deck_viewer_path), webbrowser.open :58; render.py:13 (render_html) reads template.html :31; view_model.py:282 (build_view_model); template.html.
- Callers: src/mcp_server/tools/view_deck.py:61 get_deck_with_cards :84, to_thread(present_deck) :97, DEPRECATED :3; server.py:601 wrapper; scripts/view_deck.py:35; tests (tests/unit/viewer/test_viewer_freeze.py, test_present.py, test_deck_view_model.py, tests/integration/...test_view_deck_tool.py, test_mcp_tools.py:58).
- Viewer imports nothing from src/logic or src/companion; own colour/pip/land/bucket helpers (Q6).

## Q4
- REST reason: src/companion/contracts.py:76 (ErrorReason) 10 tokens; app/errors.py:46-56 (STATUS_BY_REASON) second spelling, checked via get_args :114. Raised: deps.py:175,278,282; routes/cards.py:171,342,352,359,399,413; routes/decks.py:86,131; images.py:859-919; security.py:145,215; body_cap.py:232; errors.py:299,432,478,543. Per-router token lists in main.py:322-351 and error_responses(...) at cards.py:114,241, decks.py:60,93, active_deck.py:107.
- Push outcomes: client.py:85 (PushOutcomeToken), :105 PUSH_OUTCOMES; emitted client.py:290,293,320-328,339,380,383,466,493-501,508. Respelled in tools/companion.py:112 (SetActiveDeckResult adds deck_not_found, database_not_initialized, error), :253, :396, :485, :639 (five tokens each); message dict keys :128-139, :265; matched :206/216/220, :542/551/554; CompanionStatusResult running/not_running/error :765 (emitted :798, :834).
- MCP status Literals: card_lookup.py:37; card_search.py:50; deck_management.py:72,91,105,133; deck_import.py:31, :78, :553; deck_analysis.py:65,98,122; assess_deck_power.py:253; compare_deck_power.py:200; find_similar.py:91, :111 (_SeedResolution mirrors card_lookup found/not_found/ambiguous); semantic_search.py:79; build_search_index.py:45; initialize_database.py:67; view_deck.py:53. database_not_initialized / error / deck_not_found recur.
- Other: contracts.py:48, :527 (EventKind), :554 (TierLetter), :567 (Confidence); kind Literals :1020,1068,1115,1162,1199,1237; ws.py:129,138 close codes.

## Q5
- lookup_card_by_name: server.py:200 -> tools/card_lookup.py:43 (lookup_card) find_by_name_exact :80 then find_by_name_partial :84, with format_filter/games; _MAX_MATCHES :21, _REFINE_THRESHOLD :23.
- add/set/remove: tools/deck_management.py:239 (resolve_card) get_by_id :255 or find_by_name_exact :261 then find_by_name_partial :265, no format/games filter; _MAX_MATCHES :50; callers :657, :774, :898 after get_deck (:649, :890) or get_deck_with_cards (:766); writes :675, :814, :920, :816.
- import_decklist: tools/deck_import.py:343 resolve_card per line (:449-456, name only), one bulk add_cards_to_deck :511.
- find_similar_cards: tools/find_similar.py:206 (_resolve_seed) raw SQL on sync sqlite connection: id :227; exact lower(name)=lower(?) OR lower(printed_name)=lower(?) :241-243; partial LIKE :252-255 collapsed per oracle_id :260-263; comment :252 says it mirrors CardRepository; _MAX_MATCHES/_REFINE_THRESHOLD respelled :58-59.
- assess_deck_power: get_deck_with_cards (assess_deck_power.py:709); get_variants_for_names :360. compare_deck_power: assess twice (compare_deck_power.py:356-357). companion_set_active_deck: tools/companion.py:179 get_deck. companion_show_*: card ids unvalidated (contracts.py:601,629, :687-688, :743, :790).
- REST: routes/cards.py:116 (read_card) get_by_id :169; :244 (read_card_image) get_by_id :340; _CARD_ID_PATTERN :63, CardId :102. routes/decks.py:62 (read_deck), :95 (read_deck_format_check) get_deck_with_cards :84, :129.
- Three resolutions: card_lookup.lookup_card (filters), deck_management.resolve_card (no filters), find_similar._resolve_seed (raw SQL).

## Q6
- Colour: src/viewer/view_model.py:22 (_COLOR_ORDER), :131 (classify_color) uses card.colors; _VALID_COLORS frozenset in tools/card_search.py:26, find_similar.py:48, semantic_search.py:40; find_similar.py:119 (_decode_colors).
- _VALID_GAMES in card_search.py:28, deck_analysis.py:38, find_similar.py:49, semantic_search.py:41.
- Mana: viewer/view_model.py:98 (parse_mana_pips), :110 (map_pips), :149 (card_bucket); tools/card_search.py:59 (mana_bounds_error) shared by find_similar.py:30, semantic_search.py:22.
- Type line: viewer/view_model.py:166 (is_land) split "//"; tools/assess_deck_power.py:465 (_is_legendary_creature) split " // ".
- Legality: tools/deck_analysis.py:272 -> logic.deck_validator (:29, :331); companion routes/decks.py:95 -> format_check; assess_deck_power.py:414 (_resolve_format).
- Quantity: deck_management.py:55 (MAX_CARD_QUANTITY=250) checks :630 (1..250), :746 (0..250); limits :56-59, :318 (_metadata_bounds_error); deck_import.py:45 (_MAX_QUANTITY) checks :215, :247, :261; contracts.py:384-390 wire list bound.
- Formatting: viewer/view_model.py:282; deck_management.py:207-235 message helpers, copy/copies at :803, :838; deck_analysis.py:198,352; assess_deck_power.py:596 (_build_summary); compare_deck_power.py:285 (_build_summary); contracts.py:1305 (DEFAULT_TITLE_BY_KIND).

## Q7
- Per-item loop: tools/deck_import.py:449-456 resolve_card per line (up to two queries each). Batched: assess_deck_power.py:360. compare runs two full assessments sequentially (compare_deck_power.py:356-357). app/deps.py:182 ensure_indexes=False.

## Q8
- to_thread: server.py:1090, :1158, :1217; tools/view_deck.py:97; app/images.py:521, :569.
- Sync in async def: client.py:232 (live_instance), :337 (_attempt), :506 (_active_deck_attempt) call read_discovery -> sync read_bytes (discovery.py:205); app/main.py:63 write+fsync in lifespan; :82; :134 build_image_cache mkdir; app/deps.py:173 path.exists(); server.py:1192 calls tools/initialize_database.py:126 directly on loop (importer :183, own engine :162-166); tools/deck_import.py:144 (_parse_arena_export) CPU on loop, capped 50,000 chars (:43).
- sqlite-vec: server.py:1075 get_connection inside worker; :1076 get_embedder lazily. semantic_search.py :203, :213, :220 encode, :221 hybrid_search, _MAX_LIMIT=50 :45. find_similar.py :376, :384, :387 _resolve_seed, :401 get_card_vector, :412 hybrid_search(exclude_oracle_id), _MAX_LIMIT=50 :54. build_search_index.py:87, :94.

## Q9
- routes/cards.py:236-244 (read_card_image): DbSession dep (deps.py:240) re-checks readiness, session held for the handler (deps.py:287-324); disk cache read (cards.py:335-338; images.py:509, :358); get_by_id (:340); resolve_face_images (images.py:144), size check (cards.py:350-359); negative cache (cards.py:384; images.py:659, :706; constants :87-102 30s base x2 300s ceiling 2048 entries); wiring guard (:395-413); fetch_image (images.py:830) via Pacer.slot asyncio.Semaphore(4) (:253) + 0.1s turnstile (:254, :278, :77, :82); _fetch_within_deadline (:865), allowed host (:42), 20s (:67), 16 MB (:72); record_failure/clear; disk write before response; _image_response (cards.py:198, :232) Cache-Control public, max-age=31536000, immutable (images.py:47) + nosniff; no ETag.
- /api/cards/{id}: cards.py:169, CARD_CACHE_CONTROL "private, max-age=3600" (:91) set :172; docstring :15 ETag deliberately not used. /api/decks: decks.py:32-54 list_deck_summaries, no cache header. /api/deck/{id} + /format-check: decks.py:57-131 get_deck_with_cards, no cache header. Errors no-store (errors.py:158). /api/session no-store (session.py:95). /api/active-deck active_deck.py:77,104 no session. /health health.py:11. No batch route.

## Q10
- spa.py:69-70,361 hashed assets immutable, index no-cache, StaticFiles ETag (:16); session.py:69; state.py:55 TICKET_TTL_SECONDS=30, :62 MAX_TICKETS; ws.py:449, :103, :341 broadcast; health.py:11.

## Found nothing @ ee0263d
- In src/companion: session .add/.add_all/.delete/.merge/.flush/.commit (only set/registry .add); insert(/update(/delete( constructs; text(; sqlite3/sqlite_vec/PRAGMA; imports of src.mcp_server.
- In src/mcp_server: lru_cache, functools.cache, global (one docstring hit compare_deck_power.py:180).
- ETag on any companion route; batch card route; viewer imports of src.logic/src.companion; run_in_executor.
- Seen in passing: tools/initialize_database.py:116,122-123 raw text("SELECT count(*)"), text("DELETE FROM cards"), commit; assess_deck_power.py:716,782 session.rollback.
