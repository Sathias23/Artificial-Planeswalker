# Implementation Tasks

## 1. Setup and Dependencies
- [x] 1.1 Add ijson dependency: `uv add ijson>=3.3.0`
- [x] 1.2 Create `src/data/importers/` module directory with `__init__.py`
- [x] 1.3 Create `scripts/` directory for CLI scripts if not exists
- [x] 1.4 Create `tests/fixtures/` directory for sample Scryfall JSON test data

## 2. Bulk Data API Client
- [x] 2.1 Create `src/data/importers/scryfall_api.py` module
- [x] 2.2 Implement `async fetch_bulk_data_list()` function with httpx
- [x] 2.3 Add retry logic with exponential backoff (3 retries)
- [x] 2.4 Implement `async download_bulk_data(download_uri, output_path)` with streaming
- [x] 2.5 Add download progress logging (every 10 MB)
- [x] 2.6 Write unit tests for API client with mocked httpx responses

## 3. JSON Streaming Parser
- [x] 3.1 Create `src/data/importers/parser.py` module
- [x] 3.2 Implement `stream_cards(file_path)` generator using ijson
- [x] 3.3 Add error handling for malformed JSON with file position context
- [x] 3.4 Write unit tests with sample JSON files (valid, malformed, empty)

## 4. Data Transformation Layer
- [x] 4.1 Create `src/data/importers/transformers.py` module
- [x] 4.2 Implement `transform_scryfall_card(card_json: dict) -> CardModel | None`
- [x] 4.3 Handle all required fields: id, name, oracle_id, mana_cost, cmc, type_line, oracle_text
- [x] 4.4 Handle optional fields: keywords, card_faces, color_indicator
- [x] 4.5 Handle empty mana costs (lands) and default values
- [x] 4.6 Add validation and skip invalid cards with logging
- [x] 4.7 Write unit tests with Scryfall JSON fixtures covering all scenarios

## 5. Batch Import Logic
- [x] 5.1 Create `src/data/importers/importer.py` module
- [x] 5.2 Implement `async import_cards(session, cards_iterator, batch_size=1000)`
- [x] 5.3 Add batch accumulation and commit logic (every 1,000 cards)
- [x] 5.4 Implement upsert with SQLite INSERT OR REPLACE
- [x] 5.5 Add progress logging (every 1,000 cards)
- [x] 5.6 Track statistics: total inserted, errors, elapsed time
- [x] 5.7 Write unit tests with in-memory SQLite database

## 6. Main Orchestrator
- [x] 6.1 Create `src/data/importers/scryfall.py` main module
- [x] 6.2 Implement `async import_scryfall_bulk_data(bulk_type, db_path)` orchestrator
- [x] 6.3 Coordinate: fetch metadata → download → parse → transform → import
- [x] 6.4 Add error handling for each stage with clear error messages
- [x] 6.5 Log final summary statistics on completion
- [x] 6.6 Write integration tests with small test datasets

## 7. CLI Script
- [x] 7.1 Create `scripts/import_scryfall_data.py` CLI entry point
- [x] 7.2 Add argparse for `--type`, `--db-path`, `--help` arguments
- [x] 7.3 Set default values: `--type oracle-cards`, `--db-path data/cards.db`
- [x] 7.4 Initialize database if not exists (call database.init_db())
- [x] 7.5 Call orchestrator with parsed arguments
- [x] 7.6 Handle exceptions and exit with appropriate status codes (0 success, 1 error)
- [x] 7.7 Add logging configuration (INFO level to stdout)
- [x] 7.8 Test manually: `uv run scripts/import_scryfall_data.py --help`

## 8. Testing
- [x] 8.1 Create `tests/fixtures/scryfall_sample.json` with 10-20 realistic card objects
- [x] 8.2 Include edge cases: multi-face cards, empty mana costs, null keywords
- [x] 8.3 Write unit tests for each module (80%+ coverage)
- [x] 8.4 Write integration test: end-to-end import with sample JSON
- [x] 8.5 Test memory usage with profiling (ensure <200 MB)
- [x] 8.6 Test error scenarios: network errors, malformed JSON, disk full
- [x] 8.7 Verify all tests pass: `uv run pytest tests/`

## 9. Documentation
- [x] 9.1 Add docstrings to all public functions and classes
- [x] 9.2 Update README.md with import script usage instructions
- [x] 9.3 Document environment requirements (UV, Python 3.12+)
- [x] 9.4 Add example commands for common use cases

## 10. Validation
- [x] 10.1 Run mypy strict type checking: `uv run mypy src/`
- [x] 10.2 Run ruff linting and formatting: `uv run ruff check src/`
- [x] 10.3 Run full test suite with coverage: `uv run pytest --cov=src tests/`
- [x] 10.4 Manually test import with real oracle-cards bulk data
- [x] 10.5 Verify import completes in <2 minutes for 30,000+ cards
- [x] 10.6 Verify database contains expected card count
- [x] 10.7 Verify memory usage stays under 200 MB (use `memory-profiler` or `htop`)
- [x] 10.8 Test re-running import (verify upsert works without errors)
- [x] 10.9 Run openspec validation: `openspec validate story-1-4-scryfall-import --strict`
