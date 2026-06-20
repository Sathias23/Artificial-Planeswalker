# Artificial Planeswalker

An intelligent Magic: The Gathering Arena (MTG:A) deck-building assistant powered by PydanticAI and the Scryfall API.

## Overview

Artificial-Planeswalker provides fast, accurate card lookups, explains game mechanics, validates decks across multiple formats, and delivers intelligent synergy-based card recommendations. Built with type-safe Pydantic models, it offers a Streamlit-based interface for intuitive deck building and analysis.

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

After setup completes:
1. Edit `.env` and add your `OPENROUTER_API_KEY` (get one at [openrouter.ai/keys](https://openrouter.ai/keys))
2. Start the application: `uv run chainlit run src/ui/app.py`
3. Open your browser to the URL shown (usually http://localhost:8000)

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

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env and add your OpenRouter API key
   ```

   **Obtaining an OpenRouter API Key:**
   1. Visit [openrouter.ai](https://openrouter.ai/)
   2. Sign up or log in to your account
   3. Navigate to [API Keys](https://openrouter.ai/keys)
   4. Create a new API key
   5. Add credits to your account (pay-as-you-go pricing)
   6. Copy the API key and add it to your `.env` file:
      ```
      OPENROUTER_API_KEY=your_api_key_here
      ```

5. **Initialize the database**
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
├── data/       # Data layer: Database models, Scryfall API client, repositories
│   ├── models/       # SQLAlchemy ORM models (CardModel)
│   ├── schemas/      # Pydantic schemas for type-safe data transfer
│   ├── repositories/ # Repository pattern for data access
│   └── database.py   # Database engine and session management
├── logic/      # Business logic: Deck validation, card filtering, recommendations
├── agent/      # AI agent: PydanticAI agent with OpenRouter integration
│   ├── config.py     # Agent configuration with environment variables
│   ├── core.py       # Agent initialization and factory functions
│   ├── errors.py     # Custom exception hierarchy
│   └── retry.py      # Retry logic with exponential backoff
└── ui/         # User interface: Chainlit/Streamlit UI components
tests/          # Test suite mirroring src/ structure
├── unit/             # Unit tests (fast, no I/O)
└── integration/      # Integration tests (database, API)
```

### AI Agent Configuration

The agent uses PydanticAI with OpenRouter for accessing multiple LLM providers:

**Environment Variables:**
- `OPENROUTER_API_KEY`: Your OpenRouter API key (required)
- `AGENT_MODEL`: Model to use (default: `anthropic/claude-sonnet-4.5`)
  - Recommended: `anthropic/claude-sonnet-4.5` - Best for coding/reasoning (77.2% SWE-bench)
  - Alternative: `openai/gpt-5` - Faster, cheaper (74.9% SWE-bench)
  - Budget: `google/gemini-2.5-flash` - Cost-effective with good performance
- `AGENT_TEMPERATURE`: Sampling temperature 0.0-2.0 (default: 0.7)
- `AGENT_MAX_TOKENS`: Maximum response tokens (default: 2000)

**Basic Usage:**
```python
from legacy.agent import create_agent, run_agent_with_retry

# Create agent (loads config from environment)
agent = create_agent()

# Run with automatic retry on rate limits
response = await run_agent_with_retry(
    agent,
    "Show me red creatures with haste under 4 mana"
)
```

**Testing the Agent:**
```bash
# Manual test with simple prompt (requires OPENROUTER_API_KEY)
uv run python scripts/test_agent.py

# Run unit tests (no API key needed)
uv run pytest tests/unit/agent/ -v

# Run integration tests (requires OPENROUTER_API_KEY)
uv run pytest tests/integration/agent/ -v -m integration
```

**Error Handling:**
The agent includes comprehensive error handling:
- `AuthenticationError`: Invalid or missing API key
- `RateLimitError`: Too many requests (automatic retry with exponential backoff)
- `ModelUnavailableError`: Model service unavailable

### Database Configuration

The data layer uses SQLAlchemy 2.0 with async support and SQLite:

- **DATABASE_URL**: Configure via environment variable (default: `sqlite+aiosqlite:///./data/cards.db`)
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
- [PydanticAI](https://ai.pydantic.dev) for the AI agent framework
- [Chainlit](https://docs.chainlit.io) for the conversational UI
