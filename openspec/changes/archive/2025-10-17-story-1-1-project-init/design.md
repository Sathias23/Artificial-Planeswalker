# Design Document: Story 1.1 Project Initialization

## Context

Story 1.1 establishes the foundational project structure and development environment for Artificial-Planeswalker, an AI-powered MTG deck building assistant. This is the first story in Epic 1 (Foundation & Data Infrastructure) and must be completed before any other development work can proceed. The design must support the modular monolith architecture defined in openspec/project.md while enabling efficient development with modern Python tooling.

**Constraints**:
- Must use UV package manager (per user's global CLAUDE.md preferences)
- Must support Python 3.12+ for modern type hints
- Must enforce strict type safety (NFR2: type safety using Pydantic models)
- Must enable clean layer separation to support future UI replacement (NFR6)
- All pre-commit hooks must pass before Story 1.1 is considered complete

**Stakeholders**:
- Development team (immediate users of this setup)
- Future contributors (need clear onboarding via README)
- CI/CD pipeline (will leverage same tooling configuration)

## Goals / Non-Goals

### Goals
1. Create a reproducible development environment using UV
2. Enforce code quality and type safety from day one via pre-commit hooks
3. Establish clear project structure that maps to four-layer architecture
4. Provide excellent developer experience with fast tooling (Ruff, UV)
5. Document setup process for new developers

### Non-Goals
- CI/CD pipeline configuration (deferred to post-MVP per PRD:134)
- Docker containerization (deferred to post-MVP deployment)
- Database migrations setup (covered in Story 1.2 with Alembic)
- Application code implementation (covered in subsequent stories)
- VS Code / IDE-specific configurations (developers may configure individually)

## Research Findings

### Archon RAG Knowledge

**PydanticAI Integration**:
- Source: ai.pydantic.dev
- Key patterns: Model-agnostic design, OpenRouter as OpenAI-compatible provider
- Installation: `pydantic-ai` includes all providers, or `pydantic-ai-slim[openai]` for specific providers
- Async-first design: All tools should be async unless doing blocking I/O

**Chainlit Setup**:
- Source: docs.chainlit.io
- Installation: Simple `pip install chainlit` or `uv add chainlit`
- Runs via `chainlit run <file>.py`
- Integrates with PydanticAI through message handlers

**SQLAlchemy 2.0**:
- Source: docs.streamlit.io (indirect reference)
- Version 2.0+ provides better type safety and async support
- Will be configured in Story 1.2 with ORM models

### Web Search Findings

**UV Package Manager (2025 Best Practices)**:
- 10-100x performance improvement over pip/Poetry
- Automatic lockfile management (uv.lock)
- Simple commands: `uv add` (runtime), `uv add --dev` (development)
- Python version management via `project.requires-python` in pyproject.toml
- Verifies lockfile is up-to-date on every `uv run`

**Pre-commit + Ruff + Mypy Configuration**:
- Ruff: Single fast tool replacing Black + Flake8 + isort
- Pre-commit repo: `astral-sh/ruff-pre-commit` with `ruff` and `ruff-format` hooks
- Mypy: Use `pre-commit/mirrors-mypy` with `--strict` flag
- Configuration centralized in pyproject.toml for consistency
- Ruff linting with `--fix` must run before formatting

## Technical Decisions

### Decision 1: UV as Package Manager

**What**: Use UV exclusively for dependency management and environment setup

**Why**:
- User preference specified in CLAUDE.md
- 10-100x faster than pip/Poetry (critical for developer experience)
- Automatic lockfile management eliminates version drift
- Simpler workflow: `uv add`, `uv sync`, `uv run`
- Built-in Python version management

**Alternatives Considered**:
- Poetry: Slower, more complex, user explicitly prefers UV
- pip + pip-tools: Manual lockfile management, no virtual env management
- Conda: Overkill for pure Python project, slower

**Implementation**:
- pyproject.toml for dependency declaration
- uv.lock for pinned versions (committed to git)
- Use `uv sync` for reproducible installs

### Decision 2: Ruff for Linting and Formatting

**What**: Use Ruff as the sole linting and formatting tool

**Why**:
- 10-100x faster than Black + Flake8 + isort combined
- Single tool replaces three tools (simpler configuration)
- Modern Python support (3.12+ features)
- Built-in isort compatibility for import sorting
- Growing adoption in 2025 Python ecosystem

**Alternatives Considered**:
- Black + Flake8 + isort: Industry standard but slower, three separate configs
- Pylint: Slower, more opinionated, overlaps with mypy

**Implementation**:
- Configure in `[tool.ruff]` section of pyproject.toml
- Line length: 100 characters (per project.md:36)
- Enable isort rules for import sorting
- Pre-commit hook runs `ruff check --fix` then `ruff format`

### Decision 3: Strict Mypy from Day One

**What**: Enable mypy strict mode for all source code

**Why**:
- NFR2 requires type safety using Pydantic models throughout codebase
- Catching type errors early prevents runtime bugs
- Better IDE support with complete type information
- Python 3.12 native syntax (`list[Card]` not `List[Card]`) is cleaner
- Enforces best practices from the start

**Alternatives Considered**:
- Gradual typing: Would allow technical debt to accumulate
- Pyright: Stricter than mypy but less ecosystem adoption

**Implementation**:
- `strict = true` in `[tool.mypy]` section
- `ignore_missing_imports = true` for packages without type stubs
- Pre-commit hook enforces type checking before commits

### Decision 4: Pre-commit Hooks for Quality Gates

**What**: Use pre-commit hooks to automatically run Ruff and mypy before every commit

**Why**:
- Prevents bad code from entering version control
- Automates quality checks (developers don't forget)
- Fast feedback loop (catches issues locally, not in CI)
- Consistent code style across all contributors

**Alternatives Considered**:
- Manual running of checks: Developers would forget
- CI-only checks: Slower feedback, wastes CI resources
- Git hooks without pre-commit framework: Harder to maintain

**Implementation**:
- `.pre-commit-config.yaml` with Ruff and mypy hooks
- Developers run `pre-commit install` once after cloning
- Hooks run automatically on `git commit`
- Can skip with `git commit --no-verify` in emergencies

### Decision 5: Modular Monolith Directory Structure

**What**: Organize code into `src/data/`, `src/logic/`, `src/agent/`, `src/ui/` layers

**Why**:
- Matches architecture defined in openspec/project.md:54-81
- Clear separation of concerns enables future UI replacement (NFR6)
- Prevents circular dependencies between layers
- Makes codebase easier to understand and test
- Supports repository pattern for data access

**Alternatives Considered**:
- Flat structure: Would become messy as project grows
- Microservices: Premature for MVP, adds deployment complexity
- Feature-based structure: Doesn't align with layer separation goal

**Implementation**:
- Create four directories under `src/`: data, logic, agent, ui
- Each directory has `__init__.py` for Python package structure
- `tests/` mirrors `src/` structure
- README documents layer responsibilities and dependencies

## Risks / Trade-offs

### Risk: UV Adoption Curve
- **Risk**: UV is relatively new (2023+), some developers may be unfamiliar
- **Mitigation**: README provides clear instructions, UV commands are simpler than pip/Poetry
- **Trade-off**: Accepting modern tooling learning curve for 10-100x performance gain

### Risk: Strict Mypy May Slow Initial Development
- **Risk**: Strict type checking requires more upfront type annotations
- **Mitigation**: Python 3.12 native syntax is cleaner, type errors caught early prevent runtime bugs
- **Trade-off**: Slightly slower initial development for much higher code quality

### Risk: Pre-commit Hooks Can Be Bypassed
- **Risk**: Developers can use `--no-verify` to skip hooks
- **Mitigation**: Team discipline, future CI checks will catch issues anyway
- **Trade-off**: Developer convenience (skip in emergencies) vs enforced quality

### Risk: Ruff May Change Rapidly (Newer Tool)
- **Risk**: Ruff is actively developed, breaking changes possible
- **Mitigation**: Pin Ruff version in pyproject.toml, lockfile ensures reproducibility
- **Trade-off**: Modern fast tooling vs absolute stability

## Migration Plan

N/A - This is the initial project setup. No existing code to migrate.

## Open Questions

1. **Should we include pytest in pre-commit hooks?**
   - Pro: Prevents broken tests from being committed
   - Con: Slows down commits significantly if test suite grows large
   - **Decision**: No, not in pre-commit hooks. Run tests manually via `uv run pytest` before pushing. Consider adding to pre-push hook later if desired.

2. **Should we commit .venv directory to git?**
   - Pro: Fully reproducible environment
   - Con: Large directory, UV recreates it easily
   - **Decision**: No, exclude .venv in .gitignore. uv.lock provides reproducibility.

3. **Should we include VS Code settings in repo?**
   - Pro: Consistent editor experience
   - Con: Not all developers use VS Code
   - **Decision**: No, keep editor-agnostic. Developers configure their own editors.

4. **Should we pin exact versions or use ranges?**
   - Pro (exact): Maximum reproducibility
   - Con (exact): Harder to get security updates
   - **Decision**: Use minimum version constraints (>=) in pyproject.toml, let uv.lock pin exact versions. Best of both worlds.
