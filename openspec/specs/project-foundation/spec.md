# project-foundation Specification

## Purpose
TBD - created by archiving change story-1-1-project-init. Update Purpose after archive.
## Requirements
### Requirement: Project Directory Structure

The project SHALL follow a modular monolith architecture with four distinct layers organized under the `src/` directory.

#### Scenario: Layer separation maintained

- **GIVEN** the project repository exists
- **WHEN** developers navigate the codebase
- **THEN** they SHALL find `src/data/`, `src/logic/`, `src/agent/`, and `src/ui/` directories
- **AND** each directory contains an `__init__.py` file
- **AND** tests are organized in a parallel `tests/` directory structure

### Requirement: UV Dependency Management

The project SHALL use UV as the package and environment manager with configuration in pyproject.toml.

#### Scenario: Installing dependencies

- **GIVEN** a developer clones the repository
- **WHEN** they run `uv sync`
- **THEN** UV SHALL create a virtual environment
- **AND** UV SHALL install all dependencies from pyproject.toml
- **AND** UV SHALL generate/update uv.lock with pinned versions

#### Scenario: Adding new dependencies

- **GIVEN** a developer needs to add a new package
- **WHEN** they run `uv add <package>` for runtime dependencies
- **OR** they run `uv add --dev <package>` for development dependencies
- **THEN** UV SHALL update pyproject.toml automatically
- **AND** UV SHALL update uv.lock with resolved versions

### Requirement: Core Dependencies Declaration

The project SHALL declare all required core dependencies in pyproject.toml with appropriate version constraints.

#### Scenario: Runtime dependencies installed

- **GIVEN** pyproject.toml is configured
- **WHEN** `uv sync` is executed
- **THEN** the following packages SHALL be installed:
  - pydantic-ai (>=0.0.14)
  - sqlalchemy (>=2.0)
  - chainlit (>=1.3)
  - httpx (>=0.27)
  - python-dotenv (for environment variable management)
  - rich (>=13.0.0) (for terminal UI in setup script)

#### Scenario: Development dependencies installed

- **GIVEN** pyproject.toml is configured
- **WHEN** `uv sync` is executed
- **THEN** the following dev packages SHALL be installed:
  - pytest (>=8.3)
  - mypy (>=1.11)
  - ruff (>=0.6)
  - pre-commit (>=3.8)

### Requirement: Ruff Linting and Formatting

The project SHALL use Ruff for code linting and formatting with configuration in pyproject.toml.

#### Scenario: Ruff configuration applied

- **GIVEN** pyproject.toml contains `[tool.ruff]` configuration
- **WHEN** a developer runs `ruff check .`
- **THEN** Ruff SHALL lint all Python files
- **AND** Ruff SHALL enforce line length of 100 characters
- **AND** Ruff SHALL sort imports (isort compatibility)

#### Scenario: Ruff formatting applied

- **GIVEN** Python files exist in the project
- **WHEN** a developer runs `ruff format .`
- **THEN** Ruff SHALL format all Python files consistently
- **AND** Ruff SHALL respect the 100-character line length

### Requirement: Mypy Strict Type Checking

The project SHALL enforce strict type checking using mypy with configuration in pyproject.toml.

#### Scenario: Strict type checking enabled

- **GIVEN** pyproject.toml contains `[tool.mypy]` configuration
- **WHEN** a developer runs `mypy src/`
- **THEN** mypy SHALL run in strict mode
- **AND** mypy SHALL require type hints for all functions
- **AND** mypy SHALL fail on type errors

#### Scenario: Type checking exceptions for third-party packages

- **GIVEN** some dependencies lack type stubs
- **WHEN** mypy encounters imports from these packages
- **THEN** mypy SHALL ignore missing imports for specific packages
- **AND** mypy configuration SHALL document which packages are ignored

### Requirement: Pre-commit Quality Gates

The project SHALL use pre-commit hooks to enforce code quality standards before commits.

#### Scenario: Pre-commit hooks installed

- **GIVEN** .pre-commit-config.yaml exists
- **WHEN** a developer runs `pre-commit install`
- **THEN** pre-commit SHALL register git hooks
- **AND** hooks SHALL run automatically before each commit

#### Scenario: Ruff pre-commit hook execution

- **GIVEN** pre-commit hooks are installed
- **WHEN** a developer attempts to commit Python files
- **THEN** Ruff linting SHALL run with `--fix` flag
- **AND** Ruff formatting SHALL run after linting
- **AND** commit SHALL proceed only if all checks pass

#### Scenario: Mypy pre-commit hook execution

- **GIVEN** pre-commit hooks are installed
- **WHEN** a developer attempts to commit Python files
- **THEN** mypy SHALL run in strict mode
- **AND** commit SHALL be blocked if type errors are found

### Requirement: Python Gitignore Configuration

The project SHALL maintain a .gitignore file that excludes Python-specific files and directories from version control.

#### Scenario: Development artifacts ignored

- **GIVEN** .gitignore is configured for Python
- **WHEN** developers work on the project
- **THEN** the following SHALL be excluded from git:
  - `__pycache__/` directories
  - `*.pyc` bytecode files
  - `.venv/` virtual environment
  - `uv.lock` is tracked (lockfile should be committed)
  - `.env` files (containing secrets)
  - `.mypy_cache/` and `.ruff_cache/`
  - `*.db` SQLite database files (for development databases)

### Requirement: README Documentation

The project SHALL provide a README.md with setup instructions and usage guide.

#### Scenario: New developer onboarding

- **GIVEN** a new developer clones the repository
- **WHEN** they read README.md
- **THEN** they SHALL find:
  - Project description and goals
  - Prerequisites (UV, Python 3.12+, Git)
  - Setup instructions (`uv sync`, `pre-commit install`)
  - How to run the application (placeholder for future)
  - How to run tests (`uv run pytest`)
  - Development workflow guidelines

### Requirement: Pytest Configuration

The project SHALL use pytest for testing with configuration in pyproject.toml.

#### Scenario: Pytest configuration applied

- **GIVEN** pyproject.toml contains `[tool.pytest.ini_options]` section
- **WHEN** a developer runs `uv run pytest`
- **THEN** pytest SHALL discover tests in `tests/` directory
- **AND** pytest SHALL support async tests (asyncio mode)
- **AND** pytest SHALL generate test coverage reports

#### Scenario: Test directory structure

- **GIVEN** the project uses modular monolith architecture
- **WHEN** tests are organized
- **THEN** `tests/` directory SHALL mirror `src/` structure
- **AND** unit tests SHALL be separated from integration tests

