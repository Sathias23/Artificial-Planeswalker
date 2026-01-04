# Implementation Tasks: Story 1.1 Project Initialization

## 1. Core Project Setup
- [x] 1.1 Create project directory structure (`src/data/`, `src/logic/`, `src/agent/`, `src/ui/`, `tests/`)
- [x] 1.2 Add `__init__.py` files to all source directories
- [x] 1.3 Initialize git repository with `git init` (if not already initialized)
- [x] 1.4 Create Python .gitignore file (exclude `__pycache__/`, `*.pyc`, `.venv/`, `.env`, `.mypy_cache/`, `.ruff_cache/`, `*.db`)

## 2. UV and Dependency Management
- [x] 2.1 Create pyproject.toml with project metadata (`[project]` section: name, version, description, requires-python=">=3.12")
- [x] 2.2 Add runtime dependencies via `uv add`: pydantic-ai, sqlalchemy, chainlit, httpx, python-dotenv
- [x] 2.3 Add development dependencies via `uv add --dev`: pytest, mypy, ruff, pre-commit, pytest-asyncio
- [x] 2.4 Verify uv.lock is generated and commit it to git
- [x] 2.5 Test environment setup by running `uv sync` in a clean clone

## 3. Ruff Configuration
- [x] 3.1 Add `[tool.ruff]` section to pyproject.toml with `line-length = 100`
- [x] 3.2 Configure Ruff linting rules (`select = ["E", "F", "I"]` for pycodestyle, pyflakes, isort)
- [x] 3.3 Configure Ruff formatting settings (consistent with Black defaults)
- [x] 3.4 Run `uv run ruff check .` to verify configuration
- [x] 3.5 Run `uv run ruff format .` to verify formatting works

## 4. Mypy Configuration
- [x] 4.1 Add `[tool.mypy]` section to pyproject.toml with `strict = true`
- [x] 4.2 Add `ignore_missing_imports = true` for packages without type stubs
- [x] 4.3 Configure mypy to check `src/` directory
- [x] 4.4 Run `uv run mypy src/` to verify configuration (should pass with empty src/)

## 5. Pytest Configuration
- [x] 5.1 Add `[tool.pytest.ini_options]` section to pyproject.toml
- [x] 5.2 Configure test paths (`testpaths = ["tests"]`)
- [x] 5.3 Configure asyncio mode (`asyncio_mode = "auto"`)
- [x] 5.4 Create `tests/__init__.py` and basic test structure
- [x] 5.5 Run `uv run pytest` to verify configuration (should pass with no tests or skip)

## 6. Pre-commit Hooks Setup
- [x] 6.1 Create `.pre-commit-config.yaml` file
- [x] 6.2 Add Ruff pre-commit hook (repo: `https://github.com/astral-sh/ruff-pre-commit`, hooks: `ruff` with `--fix`, `ruff-format`)
- [x] 6.3 Add mypy pre-commit hook (repo: `https://github.com/pre-commit/mirrors-mypy`, args: `[--strict, --ignore-missing-imports]`)
- [x] 6.4 Run `uv run pre-commit install` to register git hooks
- [x] 6.5 Run `uv run pre-commit run --all-files` to verify hooks work

## 7. Documentation
- [x] 7.1 Create README.md with project description and goals
- [x] 7.2 Add prerequisites section (UV installation, Python 3.12+, Git)
- [x] 7.3 Add setup instructions (`git clone`, `uv sync`, `pre-commit install`)
- [x] 7.4 Add development workflow section (how to run tests, how to run linting/formatting)
- [x] 7.5 Add placeholder for "How to run the application" (to be filled in Epic 3)

## 8. Validation and Testing
- [x] 8.1 Create a simple test file (`tests/test_setup.py`) with a passing test to verify pytest works
- [x] 8.2 Create a simple module (`src/__init__.py`) with type hints to verify mypy works
- [x] 8.3 Verify all pre-commit hooks pass on the initial commit
- [x] 8.4 Test the setup by cloning into a new directory and running `uv sync` + `pre-commit install`
- [x] 8.5 Create initial git commit with message: "chore: initialize project structure and development environment"

## 9. Acceptance Criteria Verification
- [x] 9.1 Verify project structure matches modular monolith architecture (four layers)
- [x] 9.2 Verify UV dependency management works (`uv add`, `uv sync` commands successful)
- [x] 9.3 Verify all core and dev dependencies installed
- [x] 9.4 Verify pre-commit hooks are registered and run automatically on commit
- [x] 9.5 Verify all pre-commit hooks pass (ruff, mypy)
- [x] 9.6 Verify git repository initialized with appropriate .gitignore
- [x] 9.7 Verify README.md documents project setup and UV usage
