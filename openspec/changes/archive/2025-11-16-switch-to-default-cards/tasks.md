# Tasks: Switch to default_cards Bulk Data Type

## Overview
Change default Scryfall bulk data type from `oracle_cards` to `default_cards` to fix missing OM1 cards bug (Priority 2).

**Estimated time**: 1-2 hours (excluding 9-minute database re-import)

## Implementation Tasks

### Phase 1: Code Changes (15 minutes)

- [x] **Update import script default**
  - File: `scripts/import_scryfall_data.py`
  - Change line 44: `default="oracle_cards"` → `default="default_cards"`
  - Validation: Run `uv run python scripts/import_scryfall_data.py --help` and verify default shows `default_cards`

- [x] **Update CLAUDE.md documentation**
  - Section: "Database Management" (around line 75-78)
  - Add note about default bulk data type and trade-offs
  - Document both options (`oracle_cards` vs `default_cards`) with use cases
  - Example:
    ```markdown
    # Database Management
    # Database uses default_cards bulk data type (~60k cards, 200MB, 6-9 min import)
    # For smaller database, use oracle_cards (~30k cards, 79MB, 2-3 min import)
    uv run python scripts/import_scryfall_data.py  # Import with default_cards (default)
    uv run python scripts/import_scryfall_data.py --type oracle_cards  # Smaller database
    ```
  - Validation: Read updated section and verify clarity

- [x] **Update Quick Start documentation**
  - Section: "Quick Start" (around line 41-56)
  - Update manual setup step for import command
  - Add note about import time (~6-9 minutes for default_cards)
  - Validation: Read updated section and verify accuracy

### Phase 2: Testing (30 minutes)

- [x] **Re-import database with default_cards**
  - Backup existing database: `cp data/cards.db data/cards.db.backup`
  - Run import: `uv run python scripts/import_scryfall_data.py --type default_cards`
  - Expected: ~60,000 cards imported in 6-9 minutes
  - Validation: Check import summary shows ~60k cards

- [x] **Verify OM1 cards are present**
  - Start Chainlit UI: `uv run chainlit run src/ui/app.py`
  - Test query: "Find Ultimate Green Goblin"
  - Expected: Card found with set code "om1"
  - Validation: Card details show `games=["arena", "mtgo"]` (not paper)

- [x] **Verify platform filtering works**
  - Test command: "Show me Arena-only cards from the latest set"
  - Or use tool directly: `search_advanced(games=["arena"], page_size=10)`
  - Expected: Results include OM1 cards
  - Validation: Verify at least one OM1 card in results

- [x] **Verify all 188 OM1 cards imported**
  - Query database:
    ```python
    # In Python REPL or test file
    from src.data.database import create_engine, create_session_factory
    from src.data.repositories.card import CardRepository

    engine = create_engine()
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        repo = CardRepository(session)
        # Search for OM1 cards (set code filter not exposed, use name search)
        # Or use SQL: SELECT COUNT(*) FROM cards WHERE "set" = 'om1'
    ```
  - Expected: 188 OM1 cards in database
  - Validation: Count matches expected number

- [x] **Performance regression test**
  - Test query: `search_advanced(types=["Creature"], colors=["R"], page_size=50)`
  - Measure query time (should be <500ms)
  - Expected: Performance similar to oracle_cards (indexes maintained)
  - Validation: Query completes in <500ms

### Phase 3: Validation (15 minutes)

- [x] **Run type checking**
  - Command: `uv run mypy src/`
  - Expected: No new errors
  - Validation: Clean mypy output

- [x] **Run linting**
  - Command: `uv run ruff check . --fix`
  - Expected: No new warnings
  - Validation: Clean ruff output

- [x] **Run existing tests**
  - Command: `uv run pytest tests/unit/data/importers/`
  - Expected: All import tests pass
  - Validation: 100% pass rate for import tests

- [x] **Verify database file size**
  - Command: `ls -lh data/cards.db`
  - Expected: ~200MB (vs 79MB for oracle_cards)
  - Validation: File size in expected range (180-220MB)

### Phase 4: Documentation (20 minutes)

- [x] **Update bug report status**
  - File: `data/bug_reports.jsonl`
  - Bug ID: `ded24e1c-755b-4ad9-8abe-1223e05cf98d`
  - Use management script: `uv run python scripts/manage_bug_reports.py update ded24e1c --status resolved`
  - Validation: Bug status shows "resolved"

- [x] **Add investigation findings to docs**
  - Copy `SPIDER_MAN_INVESTIGATION.md` to `docs/bugs/` (optional)
  - Or add link in CLAUDE.md to investigation report
  - Validation: Investigation findings are preserved for future reference

- [x] **Update .env.example (if exists)**
  - Add comment documenting bulk data type behavior
  - Example:
    ```bash
    # Scryfall bulk data type (default: default_cards)
    # - default_cards: ~60k cards, 200MB, all printings including Universes Within
    # - oracle_cards: ~30k cards, 79MB, canonical versions only (may miss OM1 etc.)
    # SCRYFALL_BULK_TYPE=default_cards
    ```
  - Validation: Comment accurately describes trade-offs

## Validation Checklist

After completing all tasks, verify:

- [x] **Bug fixed**: OM1 cards are searchable by name
- [x] **Platform filtering works**: `games=["arena"]` includes OM1 cards
- [x] **All 188 OM1 cards present**: Database count matches expected
- [x] **Performance maintained**: Queries complete in <500ms
- [x] **Documentation updated**: CLAUDE.md, Quick Start, and .env.example reflect changes
- [x] **Tests passing**: Type checking, linting, and unit tests pass
- [x] **Import successful**: default_cards import completes in 6-9 minutes with ~60k cards

## Rollback Plan

If issues arise after deployment:

1. **Restore oracle_cards database**:
   ```bash
   cp data/cards.db.backup data/cards.db
   # Or re-import with oracle_cards
   uv run python scripts/import_scryfall_data.py --type oracle_cards
   ```

2. **Revert code changes**:
   ```bash
   git revert <commit-hash>
   ```

3. **Alternative fix**: If default_cards causes UX issues (too many duplicate printings), consider:
   - Add UI grouping by Oracle ID (defer to future enhancement)
   - Add set filter to search tools (allows users to specify preferred printing)
   - Document workaround in CLAUDE.md (use format filter to reduce duplicates)

## Dependencies

- **Blocked by**: None (independent change)
- **Blocks**: None (bug fix, not blocking other work)
- **Related**: Investigation report in `SPIDER_MAN_INVESTIGATION.md`

## Notes

- **One-time operation**: Users must re-import database after pulling this change
- **Communication**: Add release note explaining database size increase and import time
- **Future enhancement**: Consider adding `printed_name` column for OM1 card flavor text display
- **Future enhancement**: UI grouping for multiple printings (group by Oracle ID in search results)
