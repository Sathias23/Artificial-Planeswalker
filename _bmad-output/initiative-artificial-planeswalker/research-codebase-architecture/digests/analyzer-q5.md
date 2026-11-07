# Analyzer Q5 — card resolution paths @ ee0263d

(15 files. LB = load-bearing.)

## Entry points
- lookup_card_by_name server.py:200-220 -> src/mcp_server/tools/card_lookup.py:43-112 (lookup_card). Blank -> not_found (:67-71), name checked for blankness but not stripped before queries; uninitialised -> database_not_initialized (:73-76). LB find_by_name_exact(card_name, format_filter, games) (:80) then find_by_name_partial same filters (:84).
- add/set/remove src/mcp_server/tools/deck_management.py:623-627, :743, :872-878: strip + blank-to-None (:186-191 _blank_to_none); _selector_error (:194-204) invalid unless exactly one of card_id/name; deck check get_deck (:649, :890) or get_deck_with_cards (:766); resolve_card (:657, :774, :898).
- LB resolve_card deck_management.py:239-270: id -> get_by_id (:255), no id-shape check; name -> find_by_name_exact(name) (:261) then find_by_name_partial(name) (:265), no format/games; 0 -> card_not_found, 1 -> card, >1 -> ambiguous matches[:10] (:266-270, _MAX_MATCHES=10 :50).
- import_decklist src/mcp_server/tools/deck_import.py:343-530: get_deck_with_cards (:427); _CARD_LINE_RE (:46-49); strip (:199); resolve_card(name) per line (:455-457); statuses ambiguous, card_not_found, exists (occupied set :446, :480), ok; one add_cards_to_deck (:511); set code / collector number parsed but unused for resolution (:357-359).
- find_similar_cards src/mcp_server/tools/find_similar.py:354-391: strip (:354-357), init check (:376), index check (:384), _resolve_seed(conn, ...) (:387) on sync sqlite, not CardRepository. LB id: SELECT ... FROM cards WHERE id = ? (:226-238).
- assess/compare take no card input: assess_deck_power.py:709 get_deck_with_cards; unresolved_count dc.card is None (:754); combos by name get_variants_for_names (:360) using name_keys src/data/schemas/combo.py:34-52 (str.lower + split " // " adds front face) — a fourth normalisation. compare_deck_power.py:356-357 calls assess twice.
- companion_*: only set_active_deck touches DB via DeckRepository (src/mcp_server/tools/companion.py:177); push tools (:322, :412, :558, :660) make no repo call. src/companion/contracts.py card_id (:629), out/in (:687-688), card_ids (:743, :790) typed _CardId: length cap, no shape check, deliberate per docstring :601-605 (AD-7, AD-3).
- REST: GET /api/cards/{card_id} src/companion/app/routes/cards.py:116-173 get_by_id (:169); GET /api/card-image (:244-340) disk cache first (:334-338) then get_by_id (:340). LB _CARD_ID_PATTERN (:63, lowercase canonical uuid) as Path(pattern) (:102) -> 400 invalid_request; well-formed missing -> 404 card_not_found (:170-171, :341-342). Deck routes routes/decks.py:84, :129 get_deck_with_cards, cards embedded. No route accepts a name.
- UI: cache keyed by printing uuid ui/src/state/cards.ts:106-110; seedDeckCards (:194-208) no request; hydrateCard (:247-) -> readCard ui/src/api/client.ts:432-441 GET /api/cards/ + encodeURIComponent (:65-66); cardOf (:225-232) id + name non-blank. No name resolution.

## Three name resolvers
| | CardRepository (card.py) | find_similar._resolve_seed |
|---|---|---|
| Exact | name COLLATE NOCASE = ? OR printed_name COLLATE NOCASE = ? (:196-201) | lower(name) = lower(?) OR lower(printed_name) = lower(?) (:241-246) |
| Exact pick | ORDER BY id LIMIT 1 (:204) | ORDER BY id LIMIT 1 |
| Partial | ilike('%q%') on name OR printed_name (:246-248) | lower(name) LIKE lower(?) OR lower(printed_name) LIKE lower(?) (:253-258) |
| Collapse | SQL CTE min(id) GROUP BY oracle_id (:116-124, :251) | Python first row per oracle_id, ordered by id (:260-267) |
| Partial order | no ORDER BY (unspecified) | ORDER BY id |
| Rows fetched | all distinct oracle cards, no LIMIT | every matching printing, no LIMIT, then collapsed |
| Wildcards | % and _ live in partial; exact literal (:165-167) | same; accepted at :252 |
- NOCASE folds ASCII only (docstring :168-170 calls it equivalent to the lower()/LIKE path it replaced); SQLite lower() ASCII-only, so same results. Inference: ilike renders lower() LIKE lower() on SQLite.
- Neither exact prefers name over printed_name (OR, lowest id wins). Both collapse to lowest id per oracle; order differs so [:10] may differ. Exact never goes ambiguous.

| | lookup_card | resolve_card | _resolve_seed |
|---|---|---|---|
| format/games | both (card_lookup.py:80, :84) | none (:261, :265) | none |
| returned | matches[:10] | matches[:10] | distinct[:10] |
| statuses | found/not_found/ambiguous | ok/card_not_found/ambiguous | found/not_found/ambiguous internal; surfaced not_found/ambiguous |
| ambiguous message | 2-5 vs 6+ buckets (:99-111) | one ambiguous_message (:211-216) | same 2-5/6+ as lookup_card + "re-call with a specific card_id" (:282-298) |
- Filters: _apply_format_filter card.py:56-67, _apply_games_filter :86-96.
- Not in board: set_card_quantity answers card_not_found (deck_management.py:795-800), remove_card_from_deck answers not_in_deck (:928-930).
- LB(inferred, no EXPLAIN) lower(name) = lower(?) cannot use NOCASE index: only name/printed_name COLLATE NOCASE indexes src/data/models/card.py:26-29 + binary index=True :35-38; nothing indexes lower(name); OR optimisation needs an index per term (card.py:194-195 comment). _resolve_seed exact scans cards; repo exact uses indexes. Partial %q% unindexable on both.

## DFCs
- Transform card name stored as joined "Front // Back" src/data/importers/transformers.py:164-171, :246; printed_name normally null (:248-250). Full joined name exact hit in all three. Front face alone misses exact, partial %Delver of Secrets% collapses to one oracle -> found via 1-match bucket (data-dependent). name_keys indexes front face explicitly (combo.py:38-51).

## Same resolution, different code
1. CardRepository exact/partial vs _resolve_seed raw SQL (NOCASE vs lower(), SQL vs Python collapse, order, index use).
2. Bucketing: card_lookup.py:86-112 vs deck_management.py:265-270 vs find_similar.py:269-300; constants card_lookup.py:21-23, find_similar.py:58-59, deck_management.py:50.
3. Id lookup: card.py:145 vs find_similar.py:227. Id shape validated only on companion routes (cards.py:63); MCP deck tools, find_similar, push contracts accept any string.
4. remove_card_from_deck inline messages deck_management.py:904-915 duplicate ambiguous_message / card_not_found_message (:211-222).
5. Front face: SQL match in all three vs name_keys split (combo.py:49-52).
6. Trimming: lookup_card does not strip (card_lookup.py:67, :80); deck tools (deck_management.py:625), import (deck_import.py:199), find_similar (:354) strip.

## Not covered
- database.py connect hook body; get_variants_for_names body; routes/active_deck.py; push functions beyond grep; UI hydrateCard consumers; no EXPLAIN.
