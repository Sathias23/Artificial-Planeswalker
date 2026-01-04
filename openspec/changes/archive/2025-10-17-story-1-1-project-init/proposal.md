# Story 1.1: Project Initialization and Environment Setup

## Why

This proposal establishes the foundational Python project structure, dependency management, and development tooling for the Artificial-Planeswalker MTG deck building assistant. Without a properly configured development environment with UV package management, type safety (mypy), code quality checks (ruff), and pre-commit hooks, the team would face inconsistent development experiences, potential quality issues, and dependency management problems as the codebase grows across Epic 1-5.

**Reference**: Archon Task ID `415a9999-378b-40f4-8d22-9f06c8b1021a` - Story 1.1 from PRD docs/prd.md:161-176

## What Changes

This change introduces the complete project initialization including:

- **Project Structure**: Modular monolith architecture with `src/` containing four layers: `data/`, `logic/`, `agent/`, and `ui/`
- **UV Dependency Management**: pyproject.toml configured with all core dependencies (PydanticAI, SQLAlchemy, Chainlit, httpx, pytest, mypy, ruff)
- **Development Tooling**: Pre-commit hooks for automated quality gates (ruff linting/formatting, mypy strict type checking)
- **Git Repository**: Initialized with appropriate Python .gitignore
- **Documentation**: README.md with setup instructions and UV usage guide

## Impact

### Affected Specs
- **NEW**: `project-foundation` - Establishes the baseline project structure and tooling requirements

### Affected Code
- Creates: `pyproject.toml`, `.pre-commit-config.yaml`, `.gitignore`, `README.md`
- Creates: `src/data/`, `src/logic/`, `src/agent/`, `src/ui/` directories
- Creates: `tests/` directory structure

### Dependencies
- UV package manager (must be installed on developer machine)
- Git (for version control and pre-commit hooks)
- Python 3.12+ (per project.md requirements)

## Research Summary

### Archon RAG Knowledge Sources

**PydanticAI (ai.pydantic.dev)**:
- Supports OpenRouter integration via OpenAI-compatible API
- Model-agnostic with built-in support for multiple providers
- Requires `pydantic-ai` or `pydantic-ai-slim` installation
- Best practice: Use async functions for tool definitions unless doing blocking I/O

**Chainlit (docs.chainlit.io)**:
- Installation via `pip install chainlit` or `uv add chainlit`
- Supports PydanticAI agent integration through message handlers
- Provides chat interface with session management capabilities
- Run locally via `chainlit run app.py`

**FastAPI Testing Patterns** (applied to pytest):
- Use pytest with `@pytest.mark.anyio` for async tests
- AsyncClient pattern for testing async functions
- Configuration via pyproject.toml `[tool.pytest]` section

### Web Search Findings

**UV + pyproject.toml Best Practices (2025)**:
- Use `uv add` for runtime dependencies, `uv add --dev` for dev dependencies
- UV creates virtual environment, resolves versions, and updates pyproject.toml + uv.lock automatically
- Declare Python version in `project.requires-python` field
- UV provides 10-100x performance boost over pip/Poetry/Conda
- Use `[tool.uv]` section for UV-specific configuration
- Lockfile (uv.lock) verified on every `uv run` invocation

**Pre-commit Hooks Configuration (Ruff + Mypy)**:
- Ruff: Use `astral-sh/ruff-pre-commit` with `ruff` (linting with --fix) and `ruff-format` hooks
- Mypy: Use `pre-commit/mirrors-mypy` with `--strict` and `--ignore-missing-imports` args
- Configuration centralized in pyproject.toml for consistency across pre-commit, CI, and editors
- Ruff replaces Black + Flake8 + isort with single fast tool
- Pre-commit hooks run automatically before git commit

### Key Technical Decisions

1. **UV over Poetry/pip**: 10-100x performance, automatic lockfile management, simpler workflow
2. **Ruff over Black+Flake8+isort**: Single fast tool, modern Python support, pyproject.toml config
3. **Strict mypy from start**: Enforces type safety throughout codebase (NFR2 requirement)
4. **Pre-commit hooks**: Automated quality gates prevent bad commits, maintain consistency
5. **Modular monolith structure**: Enables clean layer separation (openspec/project.md:54-81)
