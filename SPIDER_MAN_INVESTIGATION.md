# Spider-Man Card Database Investigation Report

**Issue**: Marvel's Spider-Man Villain cards not appearing for Arena players  
**Priority**: P2 - Affects Arena player usability  
**Investigation Date**: 2025-11-07  
**Status**: Root cause identified, solution available

---

## Executive Summary

The Artificial-Planeswalker database is missing all 188 "Through the Omenpaths" (OM1) cards, which are the Arena/MTGO digital versions of Marvel's Spider-Man (SPM) paper cards. This affects Arena players searching for cards by availability.

**Root Cause**: Using Scryfall's `oracle_cards` bulk data type, which excludes OM1 cards because they share Oracle IDs with SPM cards.

**Solution**: Switch to `default_cards` bulk data type to import all printings.

---

## Investigation Findings

### 1. The Games Array is Correct

**Ultimate Green Goblin (OM1 #153)** - Retrieved from Scryfall API:
```json
{
  "name": "Ultimate Green Goblin",
  "printed_name": "Ruzic, Booed but Victorious",
  "set": "om1",
  "collector_number": "153",
  "games": ["arena", "mtgo"],
  "type_line": "Legendary Creature — Goblin Villain",
  "oracle_id": "b5b43d01-fce6-4a00-9c19-7a7e2a09d833"
}
```

**Comparison with SPM version**:
```json
{
  "name": "Ultimate Green Goblin",
  "set": "spm",
  "collector_number": "276",
  "games": ["paper"],
  "type_line": "Legendary Creature — Goblin Villain",
  "oracle_id": "b5b43d01-fce6-4a00-9c19-7a7e2a09d833"
}
```

**Key Insight**: OM1 and SPM versions share the SAME oracle name ("Ultimate Green Goblin"). The "Universes Within" name ("Ruzic, Booed but Victorious") appears only in the `printed_name` field.

### 2. No Mass Rename Event Occurred

Contrary to initial assumptions, OM1 cards were NOT renamed. They maintain the same `oracle_text` and `name` fields as their SPM counterparts. The alternate names (e.g., "Ruzic, Booed but Victorious") are cosmetic UI changes stored in `printed_name`.

**Example**:
- **Oracle Name** (both sets): "Ultimate Green Goblin"
- **Printed Name** (OM1 only): "Ruzic, Booed but Victorious"
- **Printed Name** (SPM): null (uses oracle name)

### 3. Oracle Cards Bulk Data Excludes OM1

**Scryfall Bulk Data Analysis**:

| Bulk Data Type | OM1 Cards | SPM Cards | Purpose |
|----------------|-----------|-----------|---------|
| `oracle_cards` | **0** | 187 | One card per Oracle ID (canonical versions) |
| `default_cards` | **188** | 286 | All English printings across all sets |

**Why OM1 is excluded from oracle_cards**:
- OM1 and SPM cards share the same Oracle IDs
- `oracle_cards` includes only ONE printing per Oracle ID
- Scryfall chose SPM (paper version) as the canonical printing
- OM1 versions are treated as "reprints" of SPM

**Evidence**: Scryfall Blog (September 12, 2025):
> "Each card in Omenpaths will be recorded as a reprint of the corresponding Spider-Man card."

### 4. Licensing Issue Background

**Official Context** (Wizards Announcement - April 2025):
- Marvel's Spider-Man set (SPM) released for **paper only** (September 26, 2025)
- Licensing restrictions prevented digital release (likely Disney digital rights not acquired)
- Wizards created "Through the Omenpaths" (OM1) as mechanically identical digital-only reskin
- OM1 released on **Arena/MTGO** (September 23, 2025)

**Key Quote** (Draftsim analysis):
> "The most likely motivator is that Hasbro didn't acquire the digital rights from Disney."

### 5. Scope of Impact

**All 50 Villain Creatures Affected**:
```sql
-- Current database state
SELECT COUNT(*) FROM cards WHERE set_code = 'spm' AND type_line LIKE '%Villain%';
-- Result: 50 (paper-only)

SELECT COUNT(*) FROM cards WHERE set_code = 'om1' AND type_line LIKE '%Villain%';
-- Result: 0 (missing)
```

**Full Set Impact**:
- **SPM cards in database**: 187 (paper-only)
- **OM1 cards in database**: 0 (all missing)
- **Total missing cards**: 188

### 6. No Alternative Printings Found

Ultimate Green Goblin appears in 3 sets, all sharing the same Oracle ID:
1. **PW25** #12 - games: `["paper"]`
2. **SPM** #276 - games: `["paper"]`
3. **OM1** #153 - games: `["arena", "mtgo"]` ← MISSING FROM DATABASE

Only OM1 version is available digitally.

---

## Recommendations

### Option 1: Switch to default_cards (RECOMMENDED)

**Advantages**:
- Comprehensive solution supporting ALL printings
- Supports future Universes Within sets automatically
- Enables platform-specific filtering via `games` array
- No custom logic needed

**Implementation**:
```bash
# Re-import with default_cards bulk data
uv run python scripts/import_scryfall_data.py --type default_cards

# Verify OM1 cards imported
uv run python -c "
import asyncio
from src.data.database import create_engine, create_session_factory
from sqlalchemy import select, func
from src.data.models import CardModel

async def verify():
    engine = create_engine()
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        stmt = select(func.count()).where(CardModel.set_code == 'om1')
        count = await session.scalar(stmt)
        print(f'OM1 cards in database: {count}')

asyncio.run(verify())
"
```

**Trade-offs**:
- Database size: ~79MB → ~200MB (2.5x increase)
- Import time: ~2-3 minutes → ~6-9 minutes (3x increase)
- Cards added: ~30,000+ additional printings

**Schema Changes** (Optional - for UI enhancement):
```python
# Add to src/data/models.py CardModel
printed_name: Mapped[str | None] = mapped_column(String, nullable=True)
```

### Option 2: Hybrid Import (oracle_cards + OM1 set)

**Advantages**:
- Minimal database size increase
- Adds only OM1 digital versions

**Disadvantages**:
- More complex import logic
- Requires duplicate handling (same Oracle IDs)
- Misses other potential digital-only sets

**Not recommended** due to added complexity.

---

## Database Fix Commands

### Quick Fix (Recommended)

```bash
# Backup current database
cp data/cards.db data/cards.db.backup

# Re-import with default_cards
uv run python scripts/import_scryfall_data.py --type default_cards

# Verify OM1 cards present
uv run python -c "
import asyncio
from src.data.database import create_engine, create_session_factory
from sqlalchemy import select, func
from src.data.models import CardModel

async def check():
    engine = create_engine()
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        # Check OM1 count
        om1_stmt = select(func.count()).where(CardModel.set_code == 'om1')
        om1_count = await session.scalar(om1_stmt)
        
        # Check OM1 Villain count
        villain_stmt = select(func.count()).where(
            CardModel.set_code == 'om1',
            CardModel.type_line.like('%Villain%')
        )
        villain_count = await session.scalar(villain_stmt)
        
        print(f'OM1 cards: {om1_count}')
        print(f'OM1 Villains: {villain_count}')
        print('✓ Fix successful!' if om1_count == 188 else '✗ Import incomplete')

asyncio.run(check())
"
```

### Testing Arena Availability

```python
# After fix, test filtering by games
from src.data.repositories.card import CardRepository

# Search for Arena-available Villain creatures
async with session_factory() as session:
    repo = CardRepository(session)
    result = await repo.search_advanced(
        types=["Villain"],
        games=["arena"],
        page_size=10
    )
    
    print(f"Arena Villain creatures: {result.total_count}")
    # Expected: 50+ (OM1 Villains now included)
```

---

## Technical Context for Developers

### Scryfall Oracle ID System

**Key Concept**: Oracle IDs link mechanically identical cards across sets.

```
Oracle ID: b5b43d01-fce6-4a00-9c19-7a7e2a09d833
├── PW25 #12: "Ultimate Green Goblin" [paper]
├── SPM #276: "Ultimate Green Goblin" [paper]
└── OM1 #153: "Ultimate Green Goblin" (printed: "Ruzic, Booed but Victorious") [arena, mtgo]
```

### Printed Name Field

**New in Universes Within sets**:
- `name`: Oracle name (canonical, used for rules/searching)
- `printed_name`: Physical card name (cosmetic, UI display only)
- `oracle_text`: Rules text (same across all printings)
- `printed_text`: Physical card text (may differ for flavor)

**UI Implications**:
- Search by oracle name: "Ultimate Green Goblin" ✓
- Display printed name in UI: "Ruzic, Booed but Victorious"
- Filter by platform: `games=["arena"]`

### Games Array Filtering

**Current agent tool support**:
All search tools accept `games` parameter:
```python
await repo.search_advanced(
    types=["Villain"],
    games=["arena"],  # Only Arena-available cards
)
```

**Auto-filter behavior**:
- Deck format filter applies automatically when deck loaded
- Games filter can be set independently via `set_games_filter` tool

---

## References

**API Endpoints**:
1. [Scryfall API - OM1 #153](https://api.scryfall.com/cards/om1/153)
2. [Scryfall Bulk Data](https://api.scryfall.com/bulk-data)
3. [Scryfall Blog - Through the Omenpaths Added](https://scryfall.com/blog/through-the-omenpaths-added-plus-english-printed-text-support-235)

**Official Announcements**:
1. [Through the Omenpaths and Digital Universes Beyond Updates](https://magic.wizards.com/en/news/announcements/through-the-omenpaths-and-digital-universes-beyond-updates) (April 2025)
2. [MTG Arena Announcements - August 25, 2025](https://magic.wizards.com/en/news/mtg-arena/announcements-august-25-2025)

**Community Analysis**:
1. [Draftsim - Through the Omenpaths vs Spider-Man](https://draftsim.com/mtg-spider-man-vs-through-the-omenpaths/)
2. [Draftsim - Through the Omenpaths Announcement](https://draftsim.com/through-the-omenpaths-announcement/)
3. [CBR - Spider-Man Replaced by Through the Omenpaths](https://www.cbr.com/mtg-spider-man-replaced-by-through-the-omenpaths/)

---

## Next Steps

1. **Immediate Fix**: Run import with `--type default_cards`
2. **Verification**: Confirm 188 OM1 cards imported
3. **Testing**: Verify games array filtering works for Arena searches
4. **Optional Enhancement**: Add `printed_name` column to schema for UI display
5. **Documentation Update**: Update CLAUDE.md to reflect default_cards as standard

---

**Investigation Completed**: 2025-11-07  
**Investigator**: Claude Code (Technical Researcher)  
**Files Analyzed**: 
- `/home/brads/Projects/Artificial-Planeswalker/scripts/import_scryfall_data.py`
- `/home/brads/Projects/Artificial-Planeswalker/src/data/importers/scryfall.py`
- Scryfall API responses and bulk data files
