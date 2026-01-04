# Implementation Tasks

## 1. Add Rich Dependency

- [ ] 1.1 Add `rich>=13.0.0` to pyproject.toml dependencies
- [ ] 1.2 Run `uv sync` to install rich
- [ ] 1.3 Verify rich import works: `uv run python -c "from rich.console import Console; Console().print('[green]✓ Rich works!')"`

## 2. Implement SetupValidator Class

- [ ] 2.1 Create `setup.py` in project root with basic structure
- [ ] 2.2 Implement `SetupValidator.check_env_file()` - Path.exists()
- [ ] 2.3 Implement `SetupValidator.check_api_key()` - parse .env file, check non-empty
- [ ] 2.4 Implement `SetupValidator.check_database()` - check file exists and query card count
- [ ] 2.5 Implement `SetupValidator.validate_all()` - run all checks, return summary dict

## 3. Implement SetupUI Class

- [ ] 3.1 Implement `SetupUI.display_welcome()` - rich Panel with app title
- [ ] 3.2 Implement `SetupUI.display_validation_results()` - rich Table with check results
- [ ] 3.3 Implement `SetupUI.display_step()` - rich Progress spinner for current step
- [ ] 3.4 Implement `SetupUI.display_success()` - green checkmark with message
- [ ] 3.5 Implement `SetupUI.display_error()` - red X with remediation steps
- [ ] 3.6 Implement `SetupUI.display_summary()` - final Panel with next steps
- [ ] 3.7 Implement `SetupUI.prompt_yes_no()` - interactive confirmation prompt
- [ ] 3.8 Implement `SetupUI.display_api_key_instructions()` - rich Panel with OpenRouter setup instructions

## 4. Implement SetupOrchestrator Class

- [ ] 4.1 Implement `__init__(args)` - store CLI arguments, initialize UI and validator
- [ ] 4.2 Implement `create_env_file()` - copy .env.example, display API key instructions
- [ ] 4.3 Implement `install_dependencies()` - subprocess.run(["uv", "sync"])
- [ ] 4.4 Implement `install_pre_commit_hooks()` - subprocess.run(["uv", "run", "pre-commit", "install"]) (DEV MODE ONLY)
- [ ] 4.5 Implement `import_scryfall_data()` - ALWAYS prompt user, show current DB state, subprocess.run import script
- [ ] 4.6 Implement `verify_setup()` - run health checks (database query, .env validation)
- [ ] 4.7 Implement `start_app()` - subprocess.run(["uv", "run", "chainlit", "run", "src/ui/app.py"])
- [ ] 4.8 Implement `run_check_mode()` - validation-only, no modifications
- [ ] 4.9 Implement `run_refresh_data_mode()` - re-download and import Scryfall data
- [ ] 4.10 Implement `run_start_mode()` - validate then start app
- [ ] 4.11 Implement `run_standard_setup()` - user mode (deps, env, data)
- [ ] 4.12 Implement `run_dev_setup()` - standard setup + pre-commit hooks

## 5. Implement CLI Argument Parsing

- [ ] 5.1 Create argparse.ArgumentParser with script description
- [ ] 5.2 Add `--dev` flag (install pre-commit hooks for contributors)
- [ ] 5.3 Add `--check` flag (validation only, no changes)
- [ ] 5.4 Add `--refresh-data` flag (re-download Scryfall data)
- [ ] 5.5 Add `--start` flag (start Chainlit app)
- [ ] 5.6 Add `--skip-data` flag (skip data import during setup)
- [ ] 5.7 Add `--non-interactive` flag (CI mode, no prompts)
- [ ] 5.8 Add `--help` documentation with examples and mode descriptions

## 6. Implement Error Handling

- [ ] 6.1 Add try/except around subprocess calls with clear error messages
- [ ] 6.2 Add specific error messages for missing API key (with OpenRouter link and edit instructions)
- [ ] 6.3 Add specific error messages for dependency installation failures (with uv troubleshooting)
- [ ] 6.4 Add network error handling for data import (retry suggestions)
- [ ] 6.5 Add non-interactive mode detection (sys.stdin.isatty())
- [ ] 6.6 Add graceful degradation for all prompts in non-interactive mode

## 7. Implement Data Import Logic

- [ ] 7.1 Check if database exists and query card count
- [ ] 7.2 ALWAYS prompt user for data import (unless --skip-data or --refresh-data)
- [ ] 7.3 Display current database state in prompt (e.g., "Database has 35,847 cards")
- [ ] 7.4 Indicate if database is required (e.g., "Required for app to work") if empty
- [ ] 7.5 Display progress during import (forward subprocess output)
- [ ] 7.6 Handle import failures gracefully (suggest retry or skip)
- [ ] 7.7 Skip prompt in non-interactive mode (default to skip)

## 8. Write Unit Tests

- [ ] 8.1 Create `tests/unit/test_setup_validator.py`
- [ ] 8.2 Test `check_env_file()` - mock Path.exists
- [ ] 8.3 Test `check_api_key()` - mock .env file contents (empty, missing, valid)
- [ ] 8.4 Test `check_database()` - mock database queries
- [ ] 8.5 Test `validate_all()` - verify summary dict format
- [ ] 8.6 Create `tests/unit/test_setup_orchestrator.py`
- [ ] 8.7 Test `create_env_file()` - mock file I/O (no prompts, just instructions)
- [ ] 8.8 Test data import always prompts (regardless of DB state)
- [ ] 8.9 Test error handling for each failure mode

## 9. Manual Integration Testing

- [ ] 9.1 Test standard setup on fresh clone (Linux/WSL) - verify NO pre-commit hooks installed
- [ ] 9.2 Test --dev flag setup on fresh clone - verify pre-commit hooks ARE installed
- [ ] 9.3 Test --check flag (validation only, no modifications)
- [ ] 9.4 Test --refresh-data flag (re-import data)
- [ ] 9.5 Test --start flag (start app after validation)
- [ ] 9.6 Test --skip-data flag (setup without data import)
- [ ] 9.7 Test --non-interactive flag (CI mode)
- [ ] 9.8 Test error scenarios (missing API key, network failure, uv failure)
- [ ] 9.9 Test idempotency (run setup twice, should be safe)
- [ ] 9.10 Test on macOS (if available)

## 10. Update Documentation

- [ ] 10.1 Update README.md "Quick Start" section to feature `setup.py`
- [ ] 10.2 Keep manual setup instructions in "Advanced Setup" section
- [ ] 10.3 Add troubleshooting section for common setup errors
- [ ] 10.4 Document all CLI flags with examples
- [ ] 10.5 Add data refresh instructions for quarterly MTG set releases
- [ ] 10.6 Update CLAUDE.md build commands to reference `setup.py`

## 11. Polish and Final Validation

- [ ] 11.1 Run `uv run ruff check setup.py --fix` (linting)
- [ ] 11.2 Run `uv run ruff format setup.py` (formatting)
- [ ] 11.3 Run `uv run mypy setup.py --strict` (type checking)
- [ ] 11.4 Verify all pre-commit hooks pass
- [ ] 11.5 Run `openspec validate add-setup-script --strict`
- [ ] 11.6 Final manual test on clean environment
- [ ] 11.7 Update proposal.md with any design changes discovered during implementation

## Notes

- Mark each task complete only after testing
- Update design.md if implementation reveals better approaches
- Document any blockers or open questions in proposal.md
