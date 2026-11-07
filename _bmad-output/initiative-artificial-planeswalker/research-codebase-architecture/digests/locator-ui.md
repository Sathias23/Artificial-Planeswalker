# Locator digest — ui/src (types.d.ts, openapi.json, tests excluded) @ ee0263d

## Q4
- ui/src/api/schema.ts:455 (ErrorReason) from generated ErrorResponse['reason']; :234 (AgentEventKind); :259 (AgentViewKind) Exclude<...,'deck_changed'|'active_deck_changed'>; SystemEvent ~:366.
- ui/src/api/client.ts:288 (AGENT_EVENT_KINDS) satisfies Record<AgentEventKind,true>, checked Object.hasOwn :317 (agentEventOf); :47,72,85,106,131,148 outcome unions (payload | 'error' with reason: string|null | 'unreachable'); reasonOf :195 copies token unchecked.
- ui/src/state/socket.ts:460 only switch (event.kind) with never default (:465-466 system cases); :170 ConnectionStatus.
- ui/src/state/connection.ts:157 second `event.kind === 'deck_changed'` test.
- ui/src/components/StatePanel/copy.ts:53 (StateKey); StatePanel/states.ts :7-16 header lists ten tokens; :69 PANEL_FOR_REASON satisfies Record<ErrorReason, StateKey|null>; :145 PLACEHOLDER_FOR_REASON; :161 NO_UI_RESPONSE; :202 CLIENT_ONLY_STATES; :234 RETRIES_QUIETLY.
- ui/src/state/panel.ts:68 (panelFor) fallback 'internal-error', membership :55.
- ui/src/state/cards.ts:65 (CARD_READ_IS_RETRYABLE) all ten tokens re-listed; :93 PLACEHOLDER_FOR_CARD_REFUSAL.
- ui/src/state/deck.ts:125 (PANEL_FOR_DECK_REFUSAL); literal 'deck_not_found' :319.
- ui/src/state/poller.ts:237 literal 'database_unavailable'.
- formatCheck.ts:96; deck.ts:53; cards.ts:39 state unions.
- FormatCheck: containers/FormatCheck/copy.ts:89 (CHECK_LABELS), :140 (STATUS_WORDS); FormatCheck.tsx:147 (TONE_FOR_STATUS); :182-200 type-level Asserts both directions.
- Confidence tokens twice: containers/SuggestionsView/SuggestionsView.tsx:126, containers/SwapsView/SwapsView.tsx:85. Tier letters TierListView.tsx:93. agentView.ts:34 (AGENT_VIEW_LABELS).

## Q5
- UI resolves by id only; no name lookup. client.ts:65 (cardPath), :432 (readCard), :225 (cardOf).
- state/cards.ts:110 (useCardStore), :194 (seedDeckCards), :247 (hydrateCard) cache, in-flight join, refuses '', attempts.
- Callers: CardDetail.tsx:368; SuggestionsView.tsx:421; SwapsView.tsx:284; TierListView.tsx:299,430; GroupsView.tsx:324.
- Id extractors per view: SuggestionsView.tsx:153, SwapsView.tsx:105, GroupsView.tsx:136, TierListView.tsx:146.
- isUnknownCard x5: CardDetail.tsx:231, GroupsView.tsx:150, SuggestionsView.tsx:198, SwapsView.tsx:134, TierListView.tsx:160; state/inspection.ts:178 (inspectable) same question ("inspectable()'s question, unshared"); renderableOf x4 (GroupsView:144, SuggestionsView:185, SwapsView:128, TierListView:154).

## Q6
- components/ManaCost/parse.ts:44 (MANA_COLOUR_ORDER), :76 (COLOUR_LETTERS), :163 (parseManaCost), :92 (classify), :246 (describeManaCost); ManaPip.tsx:77; containers/ColourDistribution/colours.ts:218,222,248 (coloursOf counts from pips). Nothing in ui/src reads colors/color_identity.
- Type line twice: state/deckGroups.ts:111 (TYPE_GROUPS), :152 (frontFace), :176 (groupOf); containers/ManaCurve/curve.ts:121 (isLand) whole-word 'Land', used by colours.ts:230. Artifact Land: groupOf -> Artifact, isLand -> true.
- containers/frontFaceCost.ts:98 (frontFaceName), :149 (frontFaceCost), separate from deckGroups.frontFace (DeckList.tsx:208 says why); CardGrid.tsx:136 raw mana_cost; CardDetail.tsx:203-204 (fromCard).
- Sorting/curve: deckGroups.ts:238 (byManaValueThenName), :280 (boardsOf); curve.ts:157 (bucketOf), :222 (curveOf) 1..7+.
- Quantity sums x4: deckGroups.ts:216 (quantityOf); deck.ts:537 (useDeckCardQuantity); curve.ts:235; DeckAnnouncer/copy.ts:50.
- MULTIPLICATION_SIGN x3: CardTile.tsx:177 (badge only when copies > 1, :294, :503); DeckList.tsx:128 (always, :205); GroupsView.tsx:159 (:262). SwapsView.tsx:117 (qtyOf).
- DeckBadges.tsx:60 shows backend counts; no UI legality/size checks; FormatCheck draws backend report (client.ts:485).

## Q10
- client.ts:382 (request) only fetch (:394) cache:'no-store'; READ_TIMEOUT_MS 10_000 (:41); mergedSignal :356; only new WebSocket :538; readers make no retries.
- state/poller.ts:160 (createPoller) setTimeout backoff 2 s (:63) x2 (:72) ceiling 30 s (:84); reset on outcome change (:230); stalled after 60 s + 4 refusals (:102, :118); polls only while unreachable or RETRIES_QUIETLY[panel] (:311); emit dedupe (:281); generation guard (:293/305). Mounted state/systemState.ts:230 (useSystemState) returning selector-less useSystemStore() (:247); restartPoll :260, restartPollIfStopped :295.
- state/deck.ts:202 (createDeckBoot) readActiveDeck -> readDeck (:244/262) -> seedDeckCards (:278); refetch AbortController (:378) + generation; only deck_not_found clears (:319); :594 (useDeckState), :631; :512 (driveDeckChanged).
- state/cards.ts:116 inFlight Map; :119 attempts, MAX_ATTEMPTS_PER_CARD=3 (:32); :125 generation; :142 resetCardAttempts on reconnect (connection.ts:136).
- state/formatCheck.ts:185 (loadFormatCheck); App.tsx:100 effect [detail, emptyDeck] with clearFormatCheck cleanup.
- state/socket.ts:347 (createAgentSocket) mint then open; backoff 2 s (:94) x2 (:104) 30 s (:118); 'down' after 60 s (:133) + 4 failures (:150); connection.ts:113 (useAgentConnection) on 'live' calls refreshInstanceId + reconcileDeckBoot (:125-127).
- state/identity.ts:52 (refreshInstanceId) one /health read per live.
- Images: containers/CardTile/imageUrl.ts:101 (cardImageUrl); <img> in CardTile.tsx:451/493, CardDetail.tsx:496/516, GroupsView:246, SuggestionsView:339, SwapsView:227, TierListView:245/345; browser HTTP cache; containers/useCardArt.ts:129.
- Selectors: narrow — deck.ts:529, :537 (useDeckCardQuantity loops detail.cards in the selector, per tile), cards.ts:315, faces.ts:150, inspection.ts:380, agentView.ts:387-434, systemState.ts:168/180, formatCheck.ts:228, ConnectionPill.tsx:139, DeckAnnouncer.tsx:84-93. Whole-map: ColourDistribution.tsx:135 (state.cards) with coloursOf in render (:136). Manual: AgentViewsNav.tsx:367. Render-derived without memo: ManaCurve.tsx:102, ColourDistribution.tsx:136, CardGrid.tsx:100, DeckList.tsx:239.
- Keys: card_id CardGrid.tsx:132, DeckList.tsx:297; id/text+index SuggestionsView.tsx:447, SwapsView.tsx:299, TierListView.tsx:411/459, GroupsView.tsx:307/350; index-only ManaCost.tsx:74/81, StatePanel.tsx:91/142, Footer.tsx:45; FormatCheck.tsx:241 row.check; App.tsx:241 no key on purpose.
- Stale comments: ColourDistribution.tsx:51 and CardTile.tsx:159 say App.tsx owns a hydrateCard sweep; App.tsx has none at ee0263d (seeding in deck.ts:278/325).

## Q9 (UI)
- imageUrl.ts:101; client.ts:376-380 notes card route Cache-Control private max-age=3600 bypassed by no-store.

## Found nothing @ ee0263d
- setInterval, useShallow, zustand/shallow, useMemo, color_identity, .colors, WUBRG (outside CSS comments), visibilitychange, localStorage/sessionStorage, fetch( outside client.ts:394, new WebSocket outside client.ts:538, card lookup by name.
