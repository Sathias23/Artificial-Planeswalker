# Technical Design: Scryfall Bulk Data Import

## Context

The Scryfall import system needs to download and process large JSON files (155-486 MB) containing 30,000-100,000+ Magic: The Gathering card objects, transform them into SQLAlchemy models, and insert them into a SQLite database. The system must be memory-efficient, performant, and resilient to network and data errors.

**Constraints:**
- Large JSON files cannot fit entirely in memory (would use 1-2 GB RAM)
- Import must complete in reasonable time (<2 minutes for oracle-cards)
- Must handle network failures, malformed data, and duplicate keys gracefully
- Must be runnable as a CLI script via UV for developer convenience
- Must maintain strict type safety (mypy strict mode)

**Stakeholders:**
- Developers: Need reliable data seeding for local development
- CI/CD: May need automated data setup for integration tests
- End users: (Future) May need periodic data updates without app restart

## Goals / Non-Goals

### Goals
- Download Scryfall bulk data with automatic retry and progress tracking
- Parse JSON files with <200 MB memory footprint regardless of file size
- Insert 30,000+ cards in under 2 minutes with batch operations
- Provide idempotent import (re-runnable without manual cleanup)
- Give clear error messages and progress feedback to users
- Enable easy testing with small fixture datasets

### Non-Goals
- Incremental/delta updates (always full import for MVP)
- Automated scheduling (manual script execution only)
- GUI progress bars (CLI text logging sufficient)
- Image downloads (card JSON data only)
- Multi-threaded/parallel processing (single async task sufficient)

## Research Findings

### Archon RAG Knowledge

**Scryfall Bulk Data API:**
- Metadata endpoint: `GET https://api.scryfall.com/bulk-data`
- Returns list with `download_uri`, `type`, `size`, `updated_at`
- Files are gzip-compressed (Content-Encoding: gzip)
- Oracle cards: 155 MB uncompressed, ~30,000 cards
- Default cards: 486 MB uncompressed, ~100,000 cards
- Updated every 12 hours, no rate limits

**SQLAlchemy 2.0 Async Patterns:**
- Use `AsyncSession` with proper lifecycle (acquire, use, commit/rollback, close)
- Batch inserts with `session.add_all(cards)` followed by `session.commit()`
- For upserts: Use database-specific ON CONFLICT syntax

### Web Search Findings

**Memory-Efficient JSON Parsing (2025 best practices):**
- **ijson library**: Streaming JSON parser for large files
- Uses SAX-like events to parse JSON without loading entire structure
- Pattern: `ijson.items(file, 'item')` iterates over array elements
- Opens file in binary mode (`'rb'`) for streaming
- Memory usage: O(1) per item, not O(n) for entire file

**SQLAlchemy Bulk Insert Performance:**
- SQLAlchemy 2.0 uses efficient single INSERT with multiple VALUES
- Recommended batch size: 1,000 rows (from official performance examples)
- Commit after each batch to avoid long-running transactions
- For SQLite: No multi-row insert limit concerns (unlike some RDBMS)
- Upsert with SQLite: `INSERT OR REPLACE INTO ...`

## Decisions

### Decision 1: Streaming JSON with ijson
**What:** Use ijson library to parse Scryfall JSON files incrementally, yielding one card object at a time.

**Why:**
- Scryfall bulk files (155-486 MB) would consume 1-2 GB RAM if loaded with `json.load()`
- ijson streams the file, using ~50 MB RAM regardless of file size
- Enables processing files larger than available memory
- Industry-standard solution for large JSON files in Python

**Alternatives Considered:**
- Standard json.load(): Simple but causes memory overflow on large files
- JSONL (JSON Lines): Would require Scryfall to change format (not feasible)
- Split files manually: Adds complexity, still needs streaming within splits

**Implementation:**
```python
import ijson

def stream_cards(file_path: str):
    with open(file_path, 'rb') as f:
        for card in ijson.items(f, 'item'):
            yield card
```

### Decision 2: Batch Size of 1,000 Cards
**What:** Accumulate 1,000 CardModel instances, then call `session.add_all()` and `session.commit()`.

**Why:**
- SQLAlchemy 2.0 docs recommend 1,000 rows for optimal performance
- Balances insert speed (fewer commits) with transaction size (not too large)
- Enables progress logging every 1,000 cards for user feedback
- If import fails, loses at most 1,000 cards (acceptable for idempotent re-runs)

**Alternatives Considered:**
- Single commit at end: Fastest but loses all progress on errors; risky for large imports
- Batch size 100: Too many commits, slower due to transaction overhead
- Batch size 10,000: Transaction too large, harder to track progress

**Implementation:**
```python
batch = []
for card_json in stream_cards(file_path):
    card = transform_card(card_json)
    if card:
        batch.append(card)
        if len(batch) >= 1000:
            session.add_all(batch)
            await session.commit()
            batch.clear()
```

### Decision 3: Upsert with INSERT OR REPLACE
**What:** Use SQLite's `INSERT OR REPLACE` to handle duplicate card IDs (primary key conflicts).

**Why:**
- Enables idempotent imports: re-running script updates existing cards, inserts new ones
- No need for manual database cleanup before re-import
- Useful for periodic data updates (Scryfall updates every 12 hours)
- SQLite native syntax, no need for manual SELECT + UPDATE logic

**Alternatives Considered:**
- Skip duplicates (INSERT OR IGNORE): Can't update cards with new data
- Manual duplicate checking: SELECT before INSERT adds query overhead
- DELETE all + re-insert: Loses referential integrity if other tables depend on cards

**Implementation:**
Using SQLAlchemy Core for explicit upsert:
```python
from sqlalchemy.dialects.sqlite import insert

stmt = insert(CardModel).values(card_dicts)
stmt = stmt.on_conflict_do_update(
    index_elements=['id'],
    set_={col: stmt.excluded[col] for col in CardModel.__table__.columns.keys()}
)
await session.execute(stmt)
```

Or using ORM with `merge()`:
```python
for card in batch:
    session.merge(card)  # Upserts automatically
await session.commit()
```

### Decision 4: Oracle Cards as Default
**What:** Default to "oracle-cards" bulk data type unless user specifies otherwise.

**Why:**
- Oracle cards: 155 MB, ~30,000 cards (one per Oracle ID)
- Sufficient for MVP deck building (unique cards, not all printings)
- Faster download and import (3x smaller than default-cards)
- Matches project.md constraint: MVP focuses on Standard format deck building

**Alternatives Considered:**
- Default cards: 486 MB, all printings; unnecessary for MVP (just adds duplicate Oracle IDs)
- Unique artwork: Optimized for image quality, not deck building use case

**Implementation:**
```python
BULK_TYPES = {
    'oracle-cards': 'Oracle Cards (155 MB, unique cards)',
    'default-cards': 'Default Cards (486 MB, all printings)',
    'unique-artwork': 'Unique Artwork (221 MB, best images)'
}
DEFAULT_BULK_TYPE = 'oracle-cards'
```

### Decision 5: Async HTTP with Retry Logic
**What:** Use httpx AsyncClient with tenacity retry wrapper for network resilience.

**Why:**
- Large downloads (155-486 MB) take 10-30 seconds; network errors likely
- Exponential backoff prevents hammering Scryfall on transient failures
- Async keeps import script responsive (can log progress during download)
- Follows PydanticAI patterns from research (AsyncTenacityTransport)

**Alternatives Considered:**
- Synchronous requests: Blocks entire process during download
- No retry logic: Fragile to network blips; forces manual re-runs
- Unlimited retries: Could hang indefinitely on persistent failures

**Implementation:**
```python
import httpx
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential

async def download_with_retry(url: str, output_path: str):
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=10)
    ):
        with attempt:
            async with httpx.AsyncClient(timeout=300) as client:
                async with client.stream('GET', url) as response:
                    response.raise_for_status()
                    with open(output_path, 'wb') as f:
                        async for chunk in response.aiter_bytes():
                            f.write(chunk)
```

### Decision 6: CLI Script with Argparse
**What:** Create standalone script `scripts/import_scryfall_data.py` with argparse for command-line options.

**Why:**
- Simple invocation: `uv run scripts/import_scryfall_data.py`
- Standard Python CLI pattern (argparse in stdlib)
- Easy to test and document
- Enables automation in CI/CD pipelines

**Alternatives Considered:**
- Click library: Extra dependency, overkill for 2-3 arguments
- Environment variables: Less discoverable than `--help` flag
- Interactive prompts: Harder to automate, poor for CI/CD

**Implementation:**
```python
import argparse

parser = argparse.ArgumentParser(description='Import Scryfall bulk card data')
parser.add_argument('--type', default='oracle-cards', choices=BULK_TYPES.keys())
parser.add_argument('--db-path', default='data/cards.db')
args = parser.parse_args()
```

## Architecture

### Module Structure
```
src/data/importers/
├── __init__.py
├── scryfall.py         # Main orchestrator
├── scryfall_api.py     # Bulk data API client
├── parser.py           # JSON streaming parser
├── transformers.py     # Scryfall JSON -> CardModel
└── importer.py         # Batch insert logic

scripts/
└── import_scryfall_data.py  # CLI entry point
```

### Data Flow
```
1. CLI Script (scripts/import_scryfall_data.py)
   ↓ parse arguments
   ↓ call orchestrator
2. Orchestrator (scryfall.py)
   ↓ fetch bulk data metadata
3. API Client (scryfall_api.py)
   ↓ download JSON to temp file
4. Parser (parser.py)
   ↓ stream card objects
5. Transformer (transformers.py)
   ↓ convert to CardModel
6. Importer (importer.py)
   ↓ batch insert with upserts
7. Database (cards.db)
```

### Error Handling Strategy
- **Network errors**: Retry up to 3 times with exponential backoff
- **Malformed JSON**: Log error with file position, skip to next valid object
- **Invalid card data**: Log warning with card name, skip card, continue import
- **Database errors**: Rollback current batch, log error, exit with status 1
- **Disk full**: Rollback, log clear message, exit gracefully

## Risks / Trade-offs

### Risk: Import Interruption
**Risk:** Import interrupted mid-process (Ctrl+C, power loss) leaves partial data.

**Mitigation:** Upsert strategy allows re-running without cleanup; commits every 1,000 cards limit data loss.

**Trade-off:** Small data duplication risk (last batch may be partial), but acceptable for idempotent re-runs.

### Risk: Memory Usage Spike
**Risk:** Large card objects with huge `oracle_text` or `card_faces` cause memory spike.

**Mitigation:** Batch processing ensures at most 1,000 cards in memory; ijson streams one at a time.

**Trade-off:** Cannot parallelize parsing (single iterator), but sufficient for MVP performance goals.

### Risk: Scryfall Schema Changes
**Risk:** Scryfall adds/removes fields, breaking transformer logic.

**Mitigation:** Use optional fields (CardModel allows nulls); skip invalid cards with logging.

**Trade-off:** May miss new fields until manual schema update, but import won't crash.

## Migration Plan

### Initial Deployment
1. Developer runs `uv add ijson` to install dependency
2. Run `uv run scripts/import_scryfall_data.py` to populate database
3. Verify import: query database for expected card count (~30,000 for oracle-cards)

### Re-running Imports
1. User runs script again with same or different `--type`
2. Upsert logic updates existing cards, inserts new ones
3. No manual cleanup required

### Rollback
If import causes issues:
1. Delete SQLite database file: `rm data/cards.db`
2. Re-initialize empty database: `uv run scripts/import_scryfall_data.py` will create it

### Testing Before Production
1. Test with small fixture: `tests/fixtures/scryfall_sample.json` (10-20 cards)
2. Test with full oracle-cards in dev environment
3. Verify memory usage <200 MB, time <2 minutes
4. Test re-run (upsert works)
5. Test error scenarios (network failure, malformed JSON)

## Open Questions

1. **Should we store raw JSON for future schema flexibility?**
   - Leaning NO for MVP: adds storage overhead, can always re-import
   - Revisit if Scryfall schema changes frequently

2. **Should we validate Standard legality during import?**
   - Leaning NO: store all cards, filter by `legalities` field at query time
   - MVP focuses on Standard, but keeping all cards enables future formats

3. **Should we add progress bar instead of text logging?**
   - Leaning NO for MVP: CLI text sufficient, progress bar adds dependency (e.g., tqdm)
   - Revisit if user feedback requests visual progress

4. **Should we download to temp directory or project directory?**
   - Leaning temp directory: avoids cluttering repo, auto-cleanup by OS
   - Consider configurable output path for debugging

## Performance Expectations

### Oracle Cards (155 MB, ~30,000 cards)
- Download time: 5-15 seconds (depends on network speed)
- Parse + import time: 30-60 seconds (250-500 cards/second)
- Total time: <2 minutes (meets NFR7 query performance goal)
- Memory usage: <200 MB peak

### Default Cards (486 MB, ~100,000 cards)
- Download time: 15-45 seconds
- Parse + import time: 2-4 minutes
- Total time: <5 minutes
- Memory usage: <200 MB peak (same streaming approach)
