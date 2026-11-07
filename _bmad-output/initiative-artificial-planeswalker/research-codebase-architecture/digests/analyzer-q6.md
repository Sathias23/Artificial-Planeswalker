# Analyzer Q6 — duplicated classification, parsing and validation @ ee0263d

(16 files, one over budget: ui/src/containers/frontFaceCost.ts. LB = load-bearing.)

## 1. Land detection: five rules
| Site | Rule | Feeds |
|---|---|---|
| LB src/logic/mana_curve.py:74,277 (analyze_mana_curve, generate_contextual_feedback) | "Land" in type_line, case-sensitive, whole joined line | MCP analyze_mana_curve (src/mcp_server/tools/deck_analysis.py:173,184) |
| LB src/logic/assessment/mana_base.py:69-78 (_is_land) | "land" in type_line.lower(), whole line; docstring 73-76 MDFC "Creature // Land" counts as land | compute_curve, karsten_land_delta, compute_pip_signals -> assess_deck_power |
| src/logic/assessment/classifiers.py:280 (classify_card) | same lowercase inline | ramp/tutor exclusion |
| LB src/viewer/view_model.py:166-174 (is_land) | front face only split("//")[0], lowercase substring | viewer columns, curve, pie, avg, land list (296-298) |
| LB ui/src/containers/ManaCurve/curve.ts:121-122 (isLand) | front face (deckGroups.ts:152), before em-dash, whole-word case-sensitive 'Land' | UI curve (231), colour bar (colours.ts:230) |
| ui/src/state/deckGroups.ts:111-121,176-181 (TYPE_GROUPS, groupOf) | first whole word in TYPE_GROUPS order; Creature before Land | UI group headers |
- MDFC spell // land ("Sorcery // Land"): land in MCP analyze_mana_curve and assess (land count, Karsten, avg MV); nonland in viewer and UI curve. Land count and curve differ between MCP output and UI/viewer.
- "Legendary Artifact Creature — Lander Rogue" / "Token Artifact — Lander" (curve.ts:100-101): land in mana_curve.py:74 ("Lander"), _is_land, classify_card, viewer; not land in UI isLand. curve.ts:103 records 0 live rows.
- Dryad Arbor "Land Creature — Forest Dryad": land everywhere; UI groupOf files under Creature (deckGroups.ts:97-99, 0 rows in decks).
- Case only (mana_curve.py:74 vs mana_base.py:78): differ only for lowercase "land" without "Land"; no real card found.

## 2. Mana-value buckets
| Site | Rounding | Bottom | Top |
|---|---|---|---|
| src/logic/mana_curve.py:86 | int() floor; None -> 0 | 0 bucket | unbounded; per expanded copy (deck_analysis.py:173) |
| src/logic/assessment/mana_base.py:130 (compute_curve) | int() | 0 bucket | unbounded; weighted |
| LB src/viewer/view_model.py:149-163 (card_bucket) | int() | <=1 -> "1" | >=6 -> "6+" |
| LB ui/src/containers/ManaCurve/curve.ts:157-161 (bucketOf) | Math.round | <=1 -> 1 | >=7 -> "7+" |
- cmc 0: MCP 0, viewer/UI 1. cmc 6: viewer 6+, UI 6, MCP 6. cmc >=7: viewer 6+, UI 7+, MCP exact. cmc 0.5 (Little Girl): MCP 0, viewer/UI 1 (curve.ts:146: only non-integer cmc).
- All drop sideboard, keep commander: deck_analysis.py:173,248, assess_deck_power.py:729, view_model.py:296, curve.ts:228.

## 3. Colour counts
- LB MCP pips src/logic/assessment/mana_base.py:228,303-315,362-373 (compute_pip_signals, _pip_cost): bare {W}..{G} only; hybrid, Phyrexian, twobrid, {C} count nothing; split card joined cost parsed whole (223-227); empty cost falls back to card_faces[0].
- LB UI colour bar ui/src/containers/ColourDistribution/colours.ts:218-256 (coloursOf) + ui/src/components/ManaCost/parse.ts:76-148 (COLOUR_LETTERS, classify): every colour a symbol carries once per copy (hybrid both, Phyrexian its colour, twobrid W); {C} as 'c' (parse.ts:44); front face only ui/src/containers/frontFaceCost.ts:149-178; unhydrated empty-cost contributes nothing.
- LB Viewer pie src/viewer/view_model.py:131-146,326-328 (classify_color, build_view_model): counts cards by card.colors class (W/U/B/R/G, M, C) x quantity.
- Kitchen Finks {1}{G/W}{G/W} x4: MCP 0 G 0 W; UI G+8 W+8; viewer M+4. Split {1}{R} // {1}{U}: MCP R1 U1; UI R only; viewer M (unverified).

## 4. Copy limits and quantity
- LB src/logic/deck_validator.py:41-65 (is_basic_land) "basic land" in lower(): "Basic Snow Land — Forest" fails -> held to 4 (1 singleton) by validate_deck line 406.
- LB deck_validator.py:392-406 (validate_deck): copies per card_id (printing) across main+side (397); 3+3 Lightning Bolt from two sets = no copy_limit; 1 for _SINGLETON_FORMATS (185-197), else _MAX_COPIES=4 (181); _MIN_MAINBOARD=60, _MAX_SIDEBOARD=15 (179-180) regardless of format (comment 172-178).
- deck_validator.py:92-160 (validate_card_addition): mainboard only (get_current_card_count :89), always 4, no caller in src/, re-exported src/logic/__init__.py:11.
- MAX_CARD_QUANTITY=250 once (src/mcp_server/tools/deck_management.py:55), imported by deck_import.py:18,45; add <1 or >250 (630); set <0 or >250 (746); import digit length (215), <1 (247), >250 (261). src/data/schemas/deck.py:31-37 and 56-62 same >=1 validator twice.

## 5. Same result, duplicated
- Board counts: schemas/deck.py:129-133 (_counts), :224; repositories/deck.py:397-405 (SQL); deck_validator.py:347-348; all split on sideboard flag; UI ui/src/state/deckGroups.ts:248-257 matches.
- Colour identity: repositories/deck.py:863-872 (_refresh_deck_metadata) union of CardModel.color_identity, _WUBRG_ORDER (28); src/data/database.py:132-162 (_DECK_COLOURS_SQL, _repair_deck_metadata) same union via json_each, _WUBRG (139), NULL when empty. Same set.
- WUBRG written separately: repositories/deck.py:28, database.py:139, mana_base.py:33, view_model.py:22 (+M, C), parse.ts:44 (lowercase + c).

## Not opened
- transformers.py:47,150; search/schema.py:17; _VALID_COLORS/_VALID_GAMES; colour-mode Literals; index_builder.py:136-173 (pairing evidenced only by classifiers.py:74-78 comment: deliberate copy to keep aligned); _coerce_json_list; two is_database_initialized; legality filters; deck.ts:537, DeckAnnouncer copy.ts:50, MULTIPLICATION_SIGN sites; src/companion.
