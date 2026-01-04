# Switch to default_cards Bulk Data Type

## Why

**Priority 2 Bug**: Marvel's Spider-Man Villain cards are missing from the database, breaking card lookup and deck building for Arena players.

**Root cause**: The database uses Scryfall's `oracle_cards` bulk data type, which includes only ONE card per Oracle ID (canonical version). When a Magic card has multiple printings with different names but the same Oracle ID (e.g., Marvel's Spider-Man Villains and "Through the Omenpaths" Universe Within versions), Scryfall chooses one as canonical and excludes the others.

**Specific impact**:
- All 188 "Through the Omenpaths" (OM1) digital-only cards are missing
- OM1 cards are available on Arena/MTGO but marked as `games=["paper"]` in database (wrong)
- Users cannot find Arena-legal cards like "Ultimate Green Goblin" (OM1 version)
- Database has 187 Marvel's Spider-Man (SPM) paper-only cards instead

**User pain point**: "I found Ultimate Green Goblin on Scryfall (https://scryfall.com/card/om1/153/ultimate-green-goblin), but the agent says it can't find it when I search by name. This breaks deck building for Arena Standard."

**Context**: This affects all "Universes Within" sets where WotC creates digital-only versions of licensed IP sets (e.g., Marvel, Warhammer 40K) with different names/art but identical mechanics.

## What Changes

**MODIFIED**: Switch default bulk data type from `oracle_cards` to `default_cards` in the Scryfall import system.

**Key differences**:
- **oracle_cards**: 30,557 cards (~70MB), one per Oracle ID, canonical version only
- **default_cards**: ~60,000 cards (~200MB), all printings including reprints and alternate names

**Why this fixes the bug**:
- `default_cards` includes ALL printings regardless of Oracle ID conflicts
- OM1 and SPM cards both imported (different sets, same Oracle IDs)
- `games` field correctly reflects platform availability (Arena, paper, MTGO)
- Enables format filtering (`format_filter="standard"`) AND platform filtering (`games=["arena"]`)

**Implementation changes**:
1. Change default bulk data type in `scripts/import_scryfall_data.py` (line 44): `oracle_cards` → `default_cards`
2. Update CLAUDE.md documentation to reflect new default and trade-offs
3. Re-import database with new bulk data type (one-time operation)
4. Update user-facing documentation about supported sets and platforms

**Trade-offs**:
- ✅ Fixes OM1 card availability bug (all 188 cards now available)
- ✅ Future-proofs for Universes Within sets automatically
- ✅ Enables platform filtering (`games=["arena"]`, `games=["paper"]`)
- ✅ Better user experience for Arena/MTGO players
- ⚠️ Database size: 79MB → 200MB (2.5x increase)
- ⚠️ Import time: 2-3 minutes → 6-9 minutes (3x slower)
- ⚠️ Card search results may include multiple printings (same card, different sets)

**Why NOT unique_artwork**:
- `unique_artwork` (~486MB, 123,000+ cards) is overkill for this use case
- Includes multiple versions of same art (promos, alternate frames, etc.)
- Would make search results confusing (10+ versions of "Lightning Bolt")
- `default_cards` strikes the right balance (all printings, not all artwork variants)

## Impact

### Affected Specs
- **scryfall-import** (MODIFIED): Change default bulk data type and update requirements
- **card-queries** (unchanged): No API changes, queries work identically
- **project-setup** (MODIFIED): Update Quick Start import command documentation

### Affected Code
- `scripts/import_scryfall_data.py` (line 44): Change default bulk data type
- `CLAUDE.md` (Database Management section): Update documentation
- `.env.example` (if exists): Document bulk data type options

### User Impact
- **Positive**: OM1 cards now searchable (fixes Priority 2 bug)
- **Positive**: Arena/MTGO platform filtering works correctly
- **Positive**: Future Universes Within sets automatically supported
- **Neutral**: Database file size increases from 79MB → 200MB (acceptable for local SQLite)
- **Neutral**: Initial import takes 6-9 minutes instead of 2-3 minutes (one-time operation)
- **Potential confusion**: Search results may show multiple printings (e.g., "Lightning Bolt" from 15+ sets)
  - Mitigation: UI can group by Oracle ID or filter by set/format

### Performance Characteristics
- **Import time**: ~6-9 minutes (30k → 60k cards, same batch size)
- **Database size**: ~200MB (vs 79MB for oracle_cards)
- **Query performance**: No significant change (<500ms target maintained)
  - Indexes on `name`, `oracle_id`, `set`, `games` maintain performance
  - `default_cards` has ~2x rows but queries use same indexes

### Dependencies
- **None new**: Uses existing import infrastructure
- **Backward compatible**: Existing decks, queries, and tools work identically
- **Data migration**: Users must re-run import script (one-time, ~9 minutes)

### Migration Plan
1. **Update code**: Change default bulk data type in import script
2. **Update docs**: CLAUDE.md and user-facing documentation
3. **Re-import database**:
   - Backup existing `data/cards.db` (optional)
   - Run `uv run python scripts/import_scryfall_data.py --type default_cards`
   - Verify OM1 cards are now present (test query: `lookup_card_by_name("Ultimate Green Goblin")`)
4. **Communicate to users**: Announce fix in release notes, mention database size increase

## Open Questions

1. **Should we provide a migration command or just document re-import?**
   - Proposal: Document re-import in CLAUDE.md and release notes (simple, no code needed)
   - Alternative: Add `--migrate` flag to import script that backs up old DB automatically
   - **Decision**: Document re-import (keep it simple for single-user local app)

2. **Should we add UI grouping for multiple printings of same card?**
   - Proposal: Defer to future UI enhancement (not blocking for bug fix)
   - Context: Search results may show "Lightning Bolt" from 15+ sets
   - Mitigation: Format filtering reduces duplicates (Standard has fewer reprints)
   - **Decision**: Not blocking for this change, can address in future UI improvement

3. **Should we keep oracle_cards as an option?**
   - Proposal: Yes, keep both options available via `--type` flag
   - Rationale: Some users may prefer smaller database size for disk-constrained environments
   - Documentation should clearly explain trade-offs (oracle_cards = smaller, default_cards = complete)
   - **Decision**: Keep both options, change default to default_cards

4. **Should we add printed_name column to database schema?**
   - Context: OM1 cards have `printed_name` field (e.g., "Ruzic, Booed but Victorious") separate from oracle name
   - Proposal: Defer to future enhancement (not blocking for bug fix)
   - Current behavior: Oracle name used everywhere (correct for gameplay/rules)
   - Future: Could display printed_name in UI for flavor/aesthetics
   - **Decision**: Not blocking, can add in future schema migration if users request it

## Success Criteria

1. **Bug fixed**: `lookup_card_by_name("Ultimate Green Goblin")` returns OM1 card
2. **Platform filtering works**: `search_advanced(games=["arena"])` includes OM1 cards
3. **All OM1 cards present**: Database contains all 188 Through the Omenpaths cards
4. **Performance maintained**: Import completes in <10 minutes, queries remain <500ms
5. **Documentation updated**: CLAUDE.md reflects new default and trade-offs
6. **Backward compatible**: Existing decks and queries work without modification
