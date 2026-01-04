# Story 1.4: Scryfall Bulk Data Download and Import

## Why

**Epic 1 Story 1.4** - Create a command-line script to download Scryfall bulk data JSON files and populate the SQLite database with card data. This completes the data infrastructure by providing the mechanism to load the ~30,000+ Magic: The Gathering cards into the local database, enabling the offline-first architecture (NFR1).

Building on Story 1.2's database models and Story 1.3's query layer, this story delivers the critical data ingestion pipeline. Without this capability, the application cannot function - the database would remain empty and unable to serve card queries to the PydanticAI agent.

**Reference**: Archon Task ID `7af48ca1-8add-4260-9bc0-5dcd8ab77234` - Story 1.4

## What Changes

- **NEW** Bulk data download module with async httpx for fetching Scryfall JSON files
- **NEW** Memory-efficient JSON streaming parser using ijson for large files (155-486 MB)
- **NEW** Data transformation layer to convert Scryfall JSON to SQLAlchemy CardModel instances
- **NEW** Batch insertion with SQLAlchemy bulk operations (1,000 row batches)
- **NEW** Progress logging with statistics (cards processed, errors, completion time)
- **NEW** Duplicate handling with upsert strategy (ON CONFLICT DO UPDATE)
- **NEW** CLI script runnable via UV: `uv run scripts/import_scryfall_data.py`
- **NEW** Unit tests for transformation logic with sample Scryfall JSON fixtures
- **NEW** Integration tests for end-to-end import with small test datasets

## Impact

### Affected Specs
- **NEW CAPABILITY:** `scryfall-import` - Bulk data download, JSON parsing, and database import

### Affected Code
- `src/data/importers/` - New module for data import logic
- `src/data/importers/scryfall.py` - Scryfall bulk data downloader and importer
- `src/data/importers/transformers.py` - JSON-to-ORM transformation functions
- `scripts/import_scryfall_data.py` - CLI entry point for import operations
- `tests/unit/data/test_scryfall_importer.py` - Unit tests for import logic
- `tests/integration/data/test_scryfall_import_e2e.py` - Integration tests with test data
- `tests/fixtures/scryfall_sample.json` - Sample Scryfall card JSON for testing

### Dependencies
- **uv add**: `ijson>=3.3.0` (streaming JSON parser for large files)
- Existing: `httpx` (async HTTP client), `sqlalchemy[asyncio]`, `aiosqlite`

## Research Summary

### Archon RAG Sources

**Scryfall API (scryfall.com)**:
- Bulk data endpoint: `GET https://api.scryfall.com/bulk-data`
- Returns list of available bulk data types with `download_uri` fields
- Oracle Cards: ~155 MB uncompressed JSON (one card per Oracle ID)
- Default Cards: ~486 MB uncompressed JSON (all printings)
- Content encoding: gzip compressed
- Updated every 12 hours
- No rate limits on bulk downloads (unlike card API endpoints)

**FastAPI/SQLAlchemy Patterns (fastapi.tiangolo.com)**:
- Async session management with proper lifecycle handling
- Repository pattern with Pydantic schemas for data transfer
- Async context managers for database operations

**PydanticAI (ai.pydantic.dev)**:
- Async HTTP retry strategies with tenacity library
- httpx AsyncClient with custom transport for retry logic
- Response validation patterns

### Web Search Findings (2025)

**JSON Streaming for Large Files**:
- **ijson library**: Industry-standard for streaming JSON parsing in Python
- Processes JSON incrementally without loading entire file into memory
- Parse arrays one item at a time: `ijson.items(file, 'item')`
- Critical for 155-486 MB Scryfall bulk files (would use 1-2 GB RAM if loaded fully)
- Use binary mode (`'rb'`) when opening files for streaming

**SQLAlchemy 2.0 Bulk Insert Performance**:
- SQLAlchemy 2.0+ uses single INSERT statement for bulk operations (major improvement)
- Recommended batch size: 1,000 rows per commit
- Use `session.add_all()` with chunked lists for ORM approach
- Use `session.execute(insert(CardModel), mappings)` for Core approach (faster but less type-safe)
- Commit between batches to avoid long-running transactions
- For SQLite: No special driver considerations (aiosqlite works well)

### Key Technical Decisions

**Decision 1: Use ijson for Streaming JSON Parsing**
- **What**: Parse Scryfall bulk JSON files incrementally with ijson, not json.load()
- **Why**: 155-486 MB files would consume 1-2 GB RAM if loaded entirely; streaming uses <50 MB
- **Alternatives**:
  - Standard json.load() (rejected: memory overflow on large files)
  - JSONL format (rejected: Scryfall uses JSON arrays, not line-delimited)

**Decision 2: Batch Size of 1,000 Rows**
- **What**: Insert cards in batches of 1,000, committing after each batch
- **Why**: SQLAlchemy 2.0 docs recommend 1,000 rows; balances performance and transaction size
- **Alternatives**:
  - Single commit at end (rejected: risks losing all progress on errors)
  - Smaller batches like 100 (rejected: slower due to commit overhead)

**Decision 3: Upsert Strategy with ON CONFLICT**
- **What**: Use SQLite `INSERT OR REPLACE` for duplicate card IDs (primary key conflicts)
- **Why**: Enables re-running script for updates without manual cleanup; idempotent operation
- **Alternatives**:
  - Skip duplicates (rejected: can't update card data on re-runs)
  - Manual duplicate checking (rejected: extra query overhead)

**Decision 4: Oracle Cards for MVP**
- **What**: Default to downloading "oracle-cards" bulk data (155 MB, ~30,000 cards)
- **Why**: Smaller file, one card per Oracle ID (sufficient for MVP deck building)
- **Alternatives**:
  - Default Cards (rejected for MVP: 486 MB, includes all printings - unnecessary overhead)
  - Unique Artwork (rejected: optimized for images, not deck building)

**Decision 5: Progress Logging with Statistics**
- **What**: Log progress every 1,000 cards, final summary with count/time/errors
- **Why**: Large imports take 30-60 seconds; users need feedback that script is working
- **Alternatives**:
  - No logging (rejected: appears hung on large imports)
  - Per-card logging (rejected: too verbose, slows import)

**Decision 6: Async HTTP with Retry Logic**
- **What**: Use httpx AsyncClient with retry wrapper for network resilience
- **Why**: Bulk downloads are large; network errors should trigger retries, not total failure
- **Alternatives**:
  - Synchronous requests (rejected: blocks event loop)
  - No retry logic (rejected: fragile to transient network issues)

## Validation Criteria

- `openspec validate story-1-4-scryfall-import --strict` passes
- All requirements have at least one scenario
- Spec deltas use proper `## ADDED Requirements` format
- Tasks checklist is comprehensive and actionable
- Script successfully imports oracle-cards bulk data (30,000+ cards) in <2 minutes
- Memory usage remains under 200 MB during import
- All unit and integration tests pass
