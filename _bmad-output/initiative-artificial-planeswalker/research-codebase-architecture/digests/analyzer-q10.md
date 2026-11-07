# Analyzer Q10 — SPA fetch and render patterns @ ee0263d

(15 files. LB = load-bearing.)

## Transport and retry
- LB one fetch, cache:'no-store', Accept json, 10 s timeout merged with caller signal; failure -> null -> unreachable, never throws ui/src/api/client.ts:382-412 (request), :41, :356-371 (mergedSignal).
- Only readDeck takes an AbortSignal; other readers one request, no retry client.ts:467, :432, :448, :485, :501, :518.
- Images via <img src>, browser HTTP cache; useCardArt issues nothing ui/src/containers/CardTile/CardTile.tsx:451,493; ui/src/containers/useCardArt.ts:125-160.
- Retry in three places: /api/decks poll 2 s x2 cap 30 s, reschedules only for unreachable or RETRIES_QUIETLY, stops after first healthy 200, emits on change except each start() emits first answer ui/src/state/poller.ts:63,72,84,212-216, :281-289, :311, :315-331; socket reconnect 2-30 s, new ticket per attempt ui/src/state/socket.ts:94,104,118,403-408,510-552; card reads max 3 per id per tab, re-armed on reconnect ui/src/state/cards.ts:32, :142-159; ui/src/state/connection.ts:136.
- Dedupe/cancel: card reads share one in-flight promise per id cards.ts:116,251-258,301-308; boot generation guard, no abort (superseded reads run to completion) ui/src/state/deck.ts:238-283 (runSequence); refetch generation + abort deck.ts:367-381; format check generation, no abort ui/src/state/formatCheck.ts:185-216; health latest-wins ui/src/state/identity.ts:52-67; applyInstanceId skips unchanged ui/src/state/systemState.ts:139-142; socket status emits on change socket.ts:372-376.

## (a) Cold open, 100-card deck
1. GET /api/decks systemState.ts:230-237. 2. GET /api/active-deck deck.ts:629-630, :244. 3. GET /api/session connection.ts:189, socket.ts:566. (1-3 together, independent; App.tsx:57,58,66, comment :62-65.)
4. GET /api/deck/{id} after 2 deck.ts:258-262. 5. WS upgrade after 3 socket.ts:529.
6. seedDeckCards zero card requests deck.ts:278, cards.ts:194-208; then per grid tile one card-image (CardGrid.tsx:100-102,132), ?face=1 per flippable, detail size=large (+ back) CardDetail.tsx:351-369,496,516 (hydrateCard no-op), GET format-check App.tsx:100-107.
7. LB socket 'live' -> GET /health and reconcileDeckBoot(): re-drives at once if settled or after settle via redriveOnSettle -> second active-deck + second deck on every cold open connection.ts:125-128; deck.ts:485-492,616-619.
8. Second settle writes new detail -> second format-check; first only generation-discarded App.tsx:100-107. No new image requests.
- Poll stops after first 200; onReconnected not on first connect socket.ts:440-445.
- Total: 9 JSON + 1 WS + ~1 image per tile + back faces + 1-2 large ≈ 111 for 100 single-faced cards; 0 card hydrations.

## (b) Re-renders
- LB App subscribes to whole system store, no selector systemState.ts:247; also slice.deck deck.ts:674, slice.updating deck.ts:529.
- LB no memo or useShallow anywhere in ui/src (grep memo\(|useShallow): every App render re-renders all CardTiles, DeckRows, ManaCurve (curveOf in render ManaCurve.tsx:102), ColourDistribution (coloursOf :136), CardDetail. App renders on every poll emit, connection status change, instance id change, deck-state write, updating flip.
- LB seedDeckCards builds a new entry object per row cards.ts:204 -> every per-id useCardEntry (cards.ts:315-316) returns a new ref -> all tiles (imagedFaces.ts:93), all rows (DeckList.tsx:186), ColourDistribution re-render; twice per cold open, once per refetch.
- Single hydrateCard write replaces one entry cards.ts:169-171; re-renders that id's subscribers + ColourDistribution every write (whole-map :135); 2 writes per hydration.
- Hover: useIsLiveTarget boolean -> 2 tiles + 2 rows + CardDetail inspection.ts:380-381.
- useDeckCardQuantity (GroupsView tiles) loops detail.cards in selector on every deck-store write, O(tiles x rows), re-renders only on change deck.ts:537-550.
- Per deck_changed: updating true, poll emit (new decks array), deck write + seed, updating false — up to ~4 full-tree renders.

## (c) deck_changed
- socket receive -> onSystemEvent socket.ts:465-468 -> trim deck_id -> refetchOnDeckChanged connection.ts:157-170 -> driveDeckChanged deck.ts:512-520: no deck/boot unsettled -> restartBoot (active-deck + deck); different id -> nothing; same/no id -> LB boot.refetch: generation bump, abort previous, updating, one GET /api/deck/{id} with signal deck.ts:367-381. No debounce; latest wins. Only deck_not_found changes state; other errors/abort dropped deck.ts:302-336.
- Each event also restartPollIfStopped -> one GET /api/decks (in-flight not aborted) systemState.ts:295-300, poller.ts:332-337; and one format check per settle. ~3 requests per event. active_deck_changed re-drives boot (2) + poll deck.ts:465-468.

## (d) Per tile / per hover
- Per tile one image (+ face=1) CardTile.tsx:451,479-498; tiles do not hydrate. Per hover: CardDetail size=large (+ back), browser-cached; hydrateCard no request for deck cards, one for outside ids CardDetail.tsx:366-369,496,516. hydrateCard callers: CardDetail.tsx:368, GroupsView.tsx:324, SwapsView.tsx:284, TierListView.tsx:299,430, SuggestionsView.tsx:421.

## (e) Comments
- LB App.tsx neither imports nor calls hydrateCard (App.tsx:1-33); cache filled by seed deck.ts:278,325. Stale: ColourDistribution.tsx:51, CardTile.tsx:159; ColourDistribution.tsx:47-49 "~99 hydrations during a cold-open sweep" (actually two whole-map seed writes); CardTile.tsx:164-165 "re-renders only when its own card's record lands" (seed and App renders re-render all). socket.ts:190-194 says separate onReconnected avoids doubling cold-open requests; reconcileDeckBoot does re-drive every cold open, documented deliberate (CAP-2) deck.ts:470-492.

## Not checked
- Welcome, Footer, FlipControl, faces.ts, agentView.ts, agent views beyond hydrateCard lines; React batching/effect order from React docs.
