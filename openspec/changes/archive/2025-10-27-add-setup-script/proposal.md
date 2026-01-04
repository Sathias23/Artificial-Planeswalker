# Add Setup Script for Public Release

## Why

The repository is approaching public release, but currently lacks a central entry point for setup and maintenance tasks. New contributors must manually execute multiple commands across different documentation sections to get started. This creates friction for first-time users and increases the risk of incomplete setups.

As MTG sets release quarterly, we also need a simple way for users to refresh their local Scryfall data without manually re-running import scripts.

## What Changes

Add a comprehensive `setup.py` script in the project root that automates:
- **Pre-flight validation**: Checks Python 3.12+, uv, .env file, and API key
- **Initial setup**: Installs dependencies, creates .env with clear instructions for API key
- **Developer mode**: Optional `--dev` flag installs pre-commit hooks (contributors only)
- **Data management**: Always prompts user about Scryfall data import with current DB state
- **Health verification**: Validates database and configuration
- **Professional UX**: Rich terminal output with progress indicators and clear error messages

The script supports multiple modes:
- `uv run python setup.py` - Standard setup (users wanting to run the app)
- `uv run python setup.py --dev` - Developer setup (contributors, adds pre-commit hooks)
- `uv run python setup.py --check` - Validation only (dry-run)
- `uv run python setup.py --refresh-data` - Re-download Scryfall data
- `uv run python setup.py --start` - Start Chainlit app
- `uv run python setup.py --skip-data` - Skip data import during setup

This introduces a new capability `project-setup` separate from `project-foundation`:
- `project-foundation`: What the project structure/tooling IS (current state)
- `project-setup`: How to automate getting from zero to running (process/automation)

## Impact

**Affected specs:**
- **NEW**: `project-setup` - New capability for setup automation
- **MODIFIED**: `project-foundation` - Add `rich` dependency for terminal output

**Affected code:**
- **NEW**: `setup.py` - Main setup orchestration script (~300-400 lines)
- **MODIFIED**: `README.md` - Update setup instructions to reference `setup.py`
- **MODIFIED**: `pyproject.toml` - Add `rich` dependency for beautiful terminal output
- **REUSED**: `scripts/import_scryfall_data.py` - Called as subprocess, not modified

**User experience improvements:**
- Reduces onboarding time from ~10-15 minutes (manual steps) to ~5 minutes (automated)
- Eliminates common setup errors (missing .env, wrong Python version, skipped hooks)
- Provides clear error messages with remediation steps
- Enables quarterly data refreshes with single command

**Non-breaking:**
- All existing setup methods continue to work
- Script is additive, doesn't modify existing functionality
- Manual setup still documented in README for advanced users
