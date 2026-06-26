# Artificial Planeswalker

An intelligent Magic: The Gathering Arena (MTG:A) deck-building assistant, exposed as an [MCP](https://modelcontextprotocol.io) server over a local Scryfall card database.

## Overview

Artificial-Planeswalker provides fast, accurate card lookups, validates decks across multiple formats, and surfaces mana-curve and synergy analysis. Built with type-safe Pydantic models, it runs as a **stateless MCP server**: an MCP client (e.g. Claude Code) drives the tools and supplies the LLM — the server itself makes no LLM calls, so no API key is required.

## Features

- **Card Lookup**: Fast searches using Scryfall API with local caching
- **Deck Validation**: Format-specific validation (Standard, Modern, Commander, etc.)
- **AI Recommendations**: Intelligent card suggestions based on deck synergy
- **Deck Analysis**: Performance insights and improvement suggestions
- **Markdown Export**: Export decks in standard MTG formats

## Quick Start

**Automated Setup (Recommended):**
```bash
# Clone the repository
git clone <repository-url>
cd Artificial-Planeswalker

# Run automated setup script
python3 setup.py
```

The setup script will:
- Verify Python 3.12+ is installed
- Install uv package manager (if needed)
- Install project dependencies
- Create `.env` file from template
- Initialize database and import Scryfall card data (~2-3 minutes)
- Install git pre-commit hooks

After setup completes, run the MCP server (stdio transport by default):

```bash
uv run python -m src.mcp_server
```

`.mcp.json` already points at that command, so an MCP client (e.g. Claude Code) opened in this directory exposes the tools automatically. No API key is required.

**Manual Setup (Alternative):**

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd Artificial-Planeswalker
   ```

2. **Install uv (if not installed)**
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

3. **Install dependencies**
   ```bash
   uv sync
   ```

4. **(Optional) Set up environment variables**
   ```bash
   cp .env.example .env
   ```
   Defaults work out of the box (SQLite at `./data/cards.db`, stdio transport). The MCP
   server needs no API key — `.env` is only required for the archived `legacy/` stack.

5. **Initialize the database** (downloads public Scryfall bulk data — no API key)
   ```bash
   uv run python scripts/import_scryfall_data.py
   ```

6. **Install git hooks**
   ```bash
   uv run pre-commit install
   ```

## Development

### Running Tests

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_data.py

# Run with coverage
uv run pytest --cov=src --cov-report=html
```

### Code Quality

```bash
# Run linting (with auto-fix)
uv run ruff check . --fix

# Run formatting
uv run ruff format .

# Run type checking
uv run mypy src/

# Run all pre-commit hooks manually
uv run pre-commit run --all-files
```

### Project Structure

```
src/
├── data/         # Data layer: SQLAlchemy models, Scryfall importers, repositories
│   ├── models/         # SQLAlchemy ORM models (CardModel, DeckModel, ...)
│   ├── schemas/        # Pydantic schemas for type-safe data transfer
│   ├── repositories/   # Repository pattern for data access
│   ├── importers/      # Scryfall bulk-data import pipeline
│   └── database.py     # Database engine and session management
├── logic/        # Business logic: deck validation, mana curve, synergy detection
├── search/       # SQLite ConnectionFactory (sqlite-vec load-extension seam, for Epic 2 RAG)
└── mcp_server/   # FastMCP server: tool definitions + entry point (python -m src.mcp_server)
    └── tools/          # MCP tool implementations (card lookup, search, deck mgmt, analysis)
legacy/           # Archived PydanticAI agent + Chainlit UI (reference only; uv sync --group legacy)
tests/            # Test suite mirroring src/ structure
├── unit/               # Unit tests (fast, no I/O)
└── integration/        # Integration tests (database, in-memory MCP client)
```

### MCP Server

The server is built on FastMCP and exposes the card/deck tools over stdio (the default
transport). It is stateless — every call carries its own arguments; there is no
server-side session or "active deck".

**Run it:**
```bash
uv run python -m src.mcp_server          # stdio (default)
MCP_TRANSPORT=streamable-http uv run python -m src.mcp_server   # serve over HTTP instead
```

An MCP client (e.g. Claude Code) typically launches it for you via `.mcp.json`:
```json
{
  "mcpServers": {
    "artificial-planeswalker": { "command": "uv", "args": ["run", "python", "-m", "src.mcp_server"] }
  }
}
```

**Tools exposed:** `lookup_card_by_name`, `search_cards`; deck management
(`create_deck`, `list_decks`, `load_deck`, `delete_deck`, `add_card_to_deck`,
`remove_card_from_deck`); deck analysis (`analyze_mana_curve`, `detect_synergies`,
`validate_deck`); and `report_bug`.

> **Legacy:** the previous PydanticAI + OpenRouter agent and Chainlit UI are archived under
> `legacy/` (install with `uv sync --group legacy`). They are reference-only and not part of
> the supported app.

### Semantic Search (RAG)

Two further tools — `semantic_search_cards` (natural-language query) and `find_similar_cards`
(alternatives to a seed card) — search a local vector index over the card corpus. The index is a
`sqlite-vec` virtual table (`card_vec`) living in the **same** SQLite file as the relational data,
embedded locally with `fastembed` (`bge-small-en-v1.5` — no API key, no network).

**Build the index first (one-time, ~minutes):**
```bash
uv run python scripts/build_card_embeddings.py
```

The `card_vec` index is **not** committed, so it is absent on a fresh checkout / CI — until it is
built, both semantic tools return a graceful `status="index_unavailable"` (no error) telling you to
run the build. The build is idempotent and incremental: re-running embeds only new or changed cards.

> **Backups:** the database runs in WAL mode. **Checkpoint the WAL before copying the DB file**
> (`PRAGMA wal_checkpoint(TRUNCATE);`), or the copy may miss un-checkpointed pages. A change to the
> embedding model or its dimension requires rebuilding `card_vec` (treat it as a migration).

### Database Configuration

The data layer uses SQLAlchemy 2.0 with async support and SQLite:

- **CARDS_DATABASE_URL**: Configure via environment variable (default: `sqlite+aiosqlite:///./data/cards.db`). Named `CARDS_DATABASE_URL` (not `DATABASE_URL`) to avoid clashing with Chainlit's data layer.
- **Models**: SQLAlchemy ORM models with type hints and async support
- **Schemas**: Pydantic schemas for validation and type-safe data transfer
- **Repository Pattern**: Clean separation between database and business logic

Example usage:
```python
from src.data import create_engine, create_session_factory, init_database, CardRepository

# Initialize database
engine = create_engine()
await init_database(engine)

# Create session and repository
session_factory = create_session_factory(engine)
async with session_factory() as session:
    repo = CardRepository(session)
    # Use repository for database operations
```

## Usage

(Documentation will be updated as features are implemented)

## Contributing

1. Create a feature branch
2. Make your changes
3. Ensure all tests pass and pre-commit hooks succeed
4. Submit a pull request

## License

(To be determined)

## Acknowledgments

- [Scryfall API](https://scryfall.com/docs/api) for comprehensive MTG card data
- [Model Context Protocol](https://modelcontextprotocol.io) and the FastMCP server framework
- [PydanticAI](https://ai.pydantic.dev) and [Chainlit](https://docs.chainlit.io) — powered the archived `legacy/` agent + UI
