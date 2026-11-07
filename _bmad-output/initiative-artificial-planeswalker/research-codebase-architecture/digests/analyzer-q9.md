# Analyzer Q9 — image route and read routes @ ee0263d

(~13 of 15 files. LB = load-bearing.)

## 1. GET /api/card-image/{scryfall_id}
- LB DbSession -> get_session completes before handler body src/companion/app/deps.py:240-283. No holder -> internal_error deps.py:268-278. session_factory lazily builds engine under per-instance lock; absent file -> database_not_initialized deps.py:134-193. Opens a session and runs is_database_initialized every request, never cached deps.py:249-252, 280-283: up to four SELECTs (sqlite_master cards, EXISTS cards, sqlite_master import_state, in_progress) src/data/database.py:369-381; src/data/import_state.py:36-37, 57-66. Runs even for a warm image hit src/companion/app/routes/cards.py:332-333.
- Engine create_async_engine(url, connect_args={"timeout": 5}), no pool args; companion ensure_indexes=False src/data/database.py:254-269; deps.py:181. Docstring: default AsyncAdaptedQueuePool 5 + 10 overflow (15), pool_timeout 30 s deps.py:303-305.
- Param checks (uuid pattern, six sizes, face ge=0) -> 400 only after the dependency, so a bad param against an unusable DB answers 503 cards.py:63, 102, 244-249, 275-280; images.py:35.
- LB Disk-cache read before card-row read: readiness SELECTs -> disk read -> card SELECT on miss only cards.py:312-338. DiskCache.read via to_thread, .jpg then .png at <root>/<id[:2]>/<id>/<size>_<face>.<ext>; empty, >16 MiB, OSError = miss images.py:358-398, 509-530, 335-350, 72. Hit -> _image_response, no card read, no negative cache, no pacer cards.py:336-338.
- Miss: get_by_id full row; none -> card_not_found cards.py:340-342; card.py:145-152. resolve_face_images -> no_image_data cards.py:350-359; images.py:144-164. Negative cache is_backing_off -> image_fetch_failed cards.py:385-399. Wiring guard cards.py:401-413.
- fetch_image: allow-list https, no port, cards.scryfall.io / errors.scryfall.com, before permit images.py:42, 167-186, 855-859; async with pacer.slot() then _fetch_within_deadline images.py:861-862; 20 s whole-exchange, connect 5/read 10/write 5/pool 5, no redirects, UA + Accept images.py:63-67, 189-210, 882-919; rejects non-200, non-image or SVG, Content-Length > 16 MiB, body > 16 MiB, empty, Timeout/HTTPError/InvalidURL images.py:885-919.
- Failure: record_failure, INFO log, re-raise cards.py:440-457. Success: negative_cache.clear, await cache.write before returning cards.py:467-496; to_thread(_write_atomically) mkstemp, write, unlink siblings, os.replace, Windows PermissionError = lost race images.py:401-465, 532-576; ext only jpeg/png, else served uncached images.py:119, 319-332, 554-561; write failures swallowed, 5 in a row latch writes off images.py:112, 578-603.
- Pacer, cache, negative cache created once per app in lifespan src/companion/app/main.py:132-135.

## 2. Pacer and a cold 100-printing deck
- LB slot(): Semaphore(4) then a turnstile asyncio.Lock held across the sleep (FIFO); _next_start = now + 0.1 between starts; first immediate images.py:77, 82, 253-290 (Pacer). Throughput min(1/0.1, 4/latency) images.py:83-85.
- Inference: 100 keys -> 99 intervals -> last fetch starts ~9.9 s at latency <= 0.4 s; code comments say ~9.8 s for 99 tiles cards.py:418-419; at 2 s latency ~2/s; dead CDN ~124 s at 0.8/s per comment cards.py:375-378.
- LB A request waiting in the pacer holds its DB session and connection: yield dependency closes after the endpoint returns; docstring measured checkedout() == 1 during fetch_image deps.py:295-312. At most 15 requests inside the handler; the rest wait for pool checkout in get_session; > 30 s -> sqlalchemy TimeoutError -> 500 internal_error, not 503 deps.py:306-311.
- Inference, unverified: dead-CDN rate (~1.25 s/tile) is slower than the "~0.3 s per tile" threshold that docstring names, so a 100-key burst could exceed the pool timeout unless the browser's per-origin connection limit throttles arrivals.
- No server-side cap on incoming requests, no in-flight coalescing ("Deliberately absent: in-flight coalescing … a ceiling on queueing") images.py:10-11. Each tile an <img src={cardImageUrl(...)}> ui/src/containers/CardTile/CardTile.tsx:451, 493; ui/src/containers/CardTile/imageUrl.ts:101-111.

## 3. Cache bounds
- LB Disk cache unbounded: no TTL, eviction, index; key id+size+face; only 16 MiB per-entry read check and write latch images.py:10-11, 468-473 (DiskCache).
- Negative cache in memory, keyed (id,size,face) images.py:659-698; max 2048, evicts earliest retry_after images.py:102, 747-748, 780-784; prune on record_failure images.py:736-739, 764-778; 30 s x2 to 300 s, success clears images.py:87-100, 742-762; is_backing_off one lookup images.py:706-721.

## 4. Headers
- Image 200: Cache-Control public, max-age=31536000, immutable + nosniff; no ETag, no Last-Modified cards.py:198-233 (_image_response); images.py:47 (IMAGE_CACHE_CONTROL).
- Typed errors no-store src/companion/app/errors.py:145-165 (error_response).
- Images load through <img>, so the browser HTTP cache applies (inference).

## 5. Other read routes
- All take DbSession -> same readiness probe deps.py:286-293.
- GET /api/decks -> list_deck_summaries single grouped SELECT, no card rows src/companion/app/routes/decks.py:32-54; deck.py:374-433.
- GET /api/deck/{id} and /format-check -> get_deck_with_cards selectinload x2 decks.py:57-87, 90-134; deck.py:973-1002; detail embeds full card record per entry (acts as the batch path).
- GET /api/cards/{id} get_by_id; 200 sets private, max-age=3600; ETag deliberately out cards.py:10-17, 91, 116-173.
- Deck routes set no Cache-Control on success (no header assignment in decks.py); errors no-store.
- /api/session no-store src/companion/app/routes/session.py:95. SPA files: index no-cache, hashed immutable, StaticFiles ETag src/companion/app/spa.py:16, 339-362.
- No batch card route: routes are /decks, /deck/{id}, /deck/{id}/format-check, /cards/{id}, /card-image/{id}, /active-deck, /health, /session, POST /agent/events.

## 6. Card-route Cache-Control vs UI
- LB Never takes effect for the UI: the only fetch request() always passes cache: 'no-store'; comment says deliberate ("a card read wants determinism against the route's Cache-Control: private, max-age=3600") ui/src/api/client.ts:373-398 (request); readCard goes through it client.ts:432-441.

## Not looked at
- DeckDetailFull, ui/src/state/cards.ts in full; ui/src/api/schema.ts:71 says detail embeds cards so the UI no longer makes 99 /api/cards requests. Pool figures from docstring. Browser connection limits.
