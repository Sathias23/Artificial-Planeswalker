# Analyzer Q7 — repository reads, indexes, per-item loops @ ee0263d

(14 of 15 files. * = load-bearing.)

## CardRepository (src/data/repositories/card.py)
- Format filter `json_extract(legalities,'$.<fmt>') = 'legal'` card.py:66 (_apply_format_filter); games filter OR of `CAST(games AS TEXT) LIKE '%"<g>"%'` card.py:93-96 (_apply_games_filter); unique-oracle CTE group by oracle_id min(id), id IN (subquery), predicates evaluated twice card.py:116-124 (_apply_unique_oracle_filter).
- get_by_id PK card.py:145. find_by_name_exact NOCASE OR, filters, ORDER BY id LIMIT 1 card.py:196-204.
- *find_by_name_partial ilike('%q%') name OR printed_name + filters + unique-oracle, no LIMIT, leading wildcard unindexable card.py:246-253; resolve_card fetches all and slices [:_MAX_MATCHES] deck_management.py:265,270; _MAX_MATCHES=10 deck_management.py:50.
- find_by_colors card.py:284-294, find_by_type card.py:331, search_by_keywords card.py:371-376: no LIMIT, unique-oracle; no caller in src/mcp_server, src/companion, src/logic; only scripts/validate_data_layer.py:294,320.
- search_advanced filters card.py:494-574; count(*) over the statement as subquery (second evaluation) card.py:577-578; ORDER BY cmc, name OFFSET LIMIT page_size capped 50 card.py:489,585.

## DeckRepository (src/data/repositories/deck.py)
- get_deck PK deck.py:211. get_deck_with_cards PK + selectinload x2 = 3 SELECTs deck.py:991-996.
- *list_decks optional format filter, ORDER BY created_at DESC, id, selectinload(deck_cards).selectinload(card), no LIMIT: loads every deck_cards row and every full card row of every deck deck.py:362-370.
- list_deck_summaries one SELECT decks LEFT JOIN deck_cards SUM(CASE) per board + count(DISTINCT card_id), group by deck id, no LIMIT, no card rows deck.py:397-416.
- *find_deck_by_name ilike no LIMIT scalar_one_or_none(): two matches raise MultipleResultsFound, not "first match" its docstring promises (:439) deck.py:451-453; scripts/view_deck.py:47 notes it; no caller in src.
- clone_deck one SELECT joinedload + populate_existing deck.py:151-157.
- combo_snapshot.py:52-58 (snapshot_is_available) two LIMIT 1 probes; :79-87,100 meta (single row, CHECK models/combo.py:123); :141-152 (get_variants_for_names) IN (SELECT DISTINCT spellbook_id ... name_key IN keys) no LIMIT.
- *Relationship loading: DeckModel.deck_cards lazy="noload" models/deck.py:60-67; DeckCardModel.deck and .card declare no lazy (default lazy select) models/deck_card.py:43-46; Base sets no default models/base.py:6. Comments at deck.py:520 and :621 call card "noload" — mismatch.

## Statements per mutation call (autoflush=False database.py:300)
- create_deck deck.py:98-130: INSERT + refresh, 1 commit.
- clone_deck :151-196: joined SELECT, deck INSERT, deck_cards INSERTs, refresh; skips _refresh_deck_metadata, copies color_identity; 1 commit.
- update_deck :263-307: SELECT, UPDATE, refresh; 1.
- delete_deck :329-331: bulk DELETE, DB cascade; 1.
- add_card_to_deck :517-570: INSERT, metadata refresh (get deck + colour JOIN SELECT), get card, UPDATE decks, deck refresh + deck_cards SELECT with selectinload card; ~6-8 statements; 1.
- add_cards_to_deck :608-677: INSERT batch, metadata refresh, cards IN read, UPDATE, refresh + deck_cards IN with selectinload; constant in N; 1.
- remove_card_from_deck :717-745: DELETE (rollback if 0), refresh, UPDATE, refresh; 1.
- update_card_quantity :786-834: SELECT + selectinload (2), rollback if unchanged, UPDATE, metadata refresh, UPDATE decks, refresh; 1.
- update_deck_color_identity :949-970; 1.
- *merge_decks :1056-1168: 2x get_deck_with_cards (6 SELECTs), per source row a full add_card_to_deck/update_card_quantity each committing, final refresh+commit, expire_all, third get_deck_with_cards: N+1 commits; not atomic; no caller in src or scripts.
- _refresh_deck_metadata deck.py:859-873: session.get(DeckModel), SELECT cards.color_identity JOIN deck_cards WHERE deck_id, no commit.

## Indexes
- cards: PK id; index=True name, printed_name models/card.py:35-37; NOCASE ix_cards_name_nocase, ix_cards_printed_name_nocase models/card.py:26-29. decks: PK; name/format/strategy models/deck.py:32-36. deck_cards: composite PK (deck_id, card_id, sideboard) models/deck_card.py:26-35. combo_variants PK models/combo.py:32; combo_variant_pieces PK + ix name_key models/combo.py:101-104; combo_snapshot_meta PK.
- NOCASE indexes: create_all on fresh DB; connect hook on existing DB database.py:39-43,46-85, registered only with ensure_indexes=True database.py:267-269; companion passes False src/companion/app/deps.py:181.
- Unindexed filter/sort columns: cards.oracle_id (every unique-oracle query), type_line, oracle_text, cmc, rarity, colors, keywords, games, legalities; decks.created_at (list ORDER BY); no index starting with deck_cards.card_id (FK child to cards.id).

## Per-item loops
- *import_decklist deck_import.py:449-457 resolve_card per line: find_by_name_exact, on miss find_by_name_partial (scan, no LIMIT); N to 2N queries; then one bulk add_cards_to_deck :511 and one deck load :427.
- merge_decks internal loop deck.py:1078-1117.
- None elsewhere: compare_deck_power calls assess twice compare_deck_power.py:356-357; each assessment get_deck_with_cards (assess_deck_power.py:709), get_snapshot_state (:356), get_variants_for_names with all mainboard names (:360). deck_management tools one resolve + one write (:649-675, :766-816, :890-920); set_card_quantity uses get_deck_with_cards (3 SELECTs) as existence check. Companion routes one repo call per request decks.py:54,84,129, cards.py:169,340. src/logic no repo calls (docstring deck_validator.py:660).

## Which list method
- *MCP list_decks tool server.py:283-297 -> deck_management.list_decks -> repo.list_decks deck_management.py:297, then reduced to DeckSummary.from_deck (:309): eager-loaded cards discarded.
- Companion list route -> list_deck_summaries routes/decks.py:54.

## Not found
- Callers of merge_decks, find_deck_by_name, find_by_colors, find_by_type, search_by_keywords, update_deck_color_identity in src/mcp_server, src/companion, src/logic. LIMIT on list_decks, list_deck_summaries, find_by_name_partial, get_variants_for_names. Index on cards.oracle_id, decks.created_at, or leading deck_cards.card_id.
