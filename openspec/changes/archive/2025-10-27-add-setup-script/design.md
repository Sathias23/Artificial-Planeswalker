# Setup Script Design

## Context

The Artificial-Planeswalker repository is preparing for public release. Currently, new contributors must:
1. Manually check Python version
2. Install uv (if not present)
3. Run `uv sync`
4. Copy `.env.example` to `.env`
5. Manually edit `.env` to add `OPENROUTER_API_KEY`
6. Run `uv run pre-commit install`
7. Optionally run `uv run python scripts/import_scryfall_data.py`
8. Understand how to start the app

This multi-step process is error-prone and creates a poor first impression. Additionally, quarterly MTG set releases require users to manually refresh Scryfall data.

**Constraints:**
- Must work on Unix-like systems (Linux, macOS) - Windows support nice-to-have
- Must integrate with existing scripts (don't duplicate `import_scryfall_data.py`)
- Must be runnable via `uv run` (no global Python requirement)
- Must handle missing API key gracefully (can't run without it)
- Must be idempotent (safe to run multiple times)

**Stakeholders:**
- New contributors (first-time setup)
- Existing contributors (data refresh, validation)
- Maintainers (debugging setup issues)

## Goals / Non-Goals

**Goals:**
- Single-command setup from fresh clone to running app
- Clear distinction between user mode (run the app) and dev mode (contribute code)
- Clear, actionable error messages for common issues
- Professional terminal UX with progress indicators
- Support for data refresh when new MTG sets release
- Validation-only mode for CI/diagnostics
- Interactive API key collection (better UX than manual .env edit)

**Non-Goals:**
- Docker/containerization (out of scope for MVP)
- Production deployment automation (local development only)
- Windows batch file (Python script is cross-platform enough)
- GUI installer (CLI is appropriate for developer tools)
- Auto-start app after setup (give users time to review results)

## Decisions

### User Experience: Standard vs Developer Modes

**Decision:** Default mode is for end users who just want to run the app. Developers opt-in to dev tooling with `--dev` flag.

**Standard Mode** (default):
- Install runtime dependencies (`uv sync`)
- Create .env and prompt for API key
- Optionally import Scryfall data
- Ready to run: `uv run chainlit run src/ui/app.py`

**Developer Mode** (`--dev` flag):
- Everything in standard mode
- Additionally install pre-commit hooks
- Verify git hooks configured

**Rationale:**
- Most users just want to use the tool, not contribute code
- Pre-commit hooks are irrelevant for users (slow down workflow for no benefit)
- Clear opt-in keeps default experience simple
- Developers explicitly signal intent to contribute

**Alternatives considered:**
- **Auto-detect git presence**: Rejected - user might have forked without wanting to contribute
- **Always install hooks**: Rejected - forces development workflow on casual users
- **Separate dev setup script**: Rejected - one script with modes is simpler

### Architecture: Three-Class Design

**Decision:** Separate concerns into `SetupValidator`, `SetupOrchestrator`, and `SetupUI` classes.

**Rationale:**
- `SetupValidator`: Pure validation logic (no side effects) - easy to test
- `SetupOrchestrator`: Stateful setup execution - tracks progress
- `SetupUI`: Terminal output formatting - isolated for future enhancement

**Alternatives considered:**
- **Single monolithic script**: Rejected - hard to test, poor separation of concerns
- **Multiple small scripts**: Rejected - more complexity for users to understand
- **Click/Typer CLI framework**: Rejected - overkill for simple arg parsing, extra dependency

### Output Formatting: Rich Library

**Decision:** Add `rich` as a runtime dependency for terminal output.

**Rationale:**
- Professional progress bars and spinners (better UX)
- Colored output for success/error states (scannable results)
- Table formatting for validation results (clear summary)
- Wide adoption in Python ecosystem (37k+ GitHub stars, well-maintained)
- Small footprint (~500KB, pure Python, no binary dependencies)

**Alternatives considered:**
- **Plain print statements**: Rejected - poor UX, unprofessional for public release
- **colorama**: Rejected - only handles colors, no progress bars or tables
- **tqdm**: Rejected - only progress bars, no rich formatting or colors

### API Key Configuration: Instructional Approach

**Decision:** Create `.env` from template and display clear instructions for adding the API key. Do NOT prompt interactively.

**Rationale:**
- Avoids security concerns (no terminal history, no getpass complexity)
- Works consistently in all environments (interactive, CI, SSH)
- Gives users control over when/how they add the key
- Simpler implementation (no input validation, no edge cases)
- Industry standard pattern (see create-react-app, Next.js, etc.)

**Instructions displayed:**
```
✓ Created .env file from template

⚠ ACTION REQUIRED: Add your OpenRouter API key
  1. Sign up at https://openrouter.ai/keys
  2. Copy your API key
  3. Edit .env file and set: OPENROUTER_API_KEY=your-key-here
  4. Re-run setup to verify configuration
```

**Alternatives considered:**
- **Interactive prompt with getpass**: Rejected - complexity, security concerns, doesn't work in all environments
- **Auto-open browser to get key**: Rejected - too magical, may not work in all environments
- **Environment variable only**: Rejected - doesn't persist across sessions

### Data Import: Always Prompt

**Decision:** Always prompt user whether to import data during setup, regardless of database state.

**Rationale:**
- User explicitly decides what they want
- No "magic" behavior (transparent and predictable)
- Database might be corrupted even if populated
- User might want to skip for testing or re-import for refresh
- Clear prompt provides context on size and time commitment

**Logic:**
```python
if args.skip_data:
    skip_import = True
elif args.refresh_data:
    skip_import = False  # Force re-import
elif args.non_interactive:
    skip_import = True  # Default to skip in CI
else:
    # ALWAYS prompt (even if database exists)
    skip_import = not prompt_yes_no(
        "Import Scryfall card data (~70MB, 2-3 min)? "
        "(Database has 35,847 cards)" if database_exists()
        else "(Required for app to work)"
    )
```

**Alternatives considered:**
- **Auto-skip if populated**: Rejected - too magical, user loses control
- **Always import**: Rejected - wastes time on re-runs without user consent
- **Never import**: Rejected - app is useless without cards
- **Separate script only**: Rejected - extra step for users to discover

### Subprocess Integration: Call Existing Scripts

**Decision:** Invoke `scripts/import_scryfall_data.py` via `subprocess.run()` rather than importing and calling functions.

**Rationale:**
- Avoids code duplication
- Maintains script's existing error handling and logging
- Allows script to evolve independently
- Easier to redirect output for progress display

**Implementation:**
```python
result = subprocess.run(
    ["uv", "run", "python", "scripts/import_scryfall_data.py"],
    capture_output=True,
    text=True,
)
if result.returncode != 0:
    display_error(f"Data import failed: {result.stderr}")
    return False
```

**Alternatives considered:**
- **Import and call directly**: Rejected - creates tight coupling, complicates error handling
- **Duplicate import logic**: Rejected - violates DRY principle
- **Refactor import to library**: Rejected - over-engineering for current needs

### Validation Strategy: Assume Prerequisites, Validate Configuration

**Decision:** Assume Python 3.12+ and uv are already installed (required to run the script). Validate/auto-create configuration.

**Assumed prerequisites (no validation):**
- Python 3.12+ (required to run `uv run python setup.py`)
- uv installed (required for `uv run` command)

**Validated/auto-fixed:**
- .env file (auto-create from `.env.example`)
- API key presence (check and instruct if missing)
- Dependencies (install via `uv sync`)
- Pre-commit hooks (install in dev mode only)
- Database (optionally import data)

**Rationale:**
- If they can run `uv run python setup.py`, they already have both
- Checking for them is redundant and adds complexity
- Better to assume and fail naturally if missing
- Focus validation on configuration, not tools
- Simpler error messages (Python/uv errors are already clear)

### Error Handling: Context-Aware Messages

**Decision:** Provide specific remediation steps for failure modes we can detect.

**Examples:**
```python
# Missing API key
"""
✗ OPENROUTER_API_KEY not set in .env

To fix:
  1. Sign up at https://openrouter.ai/keys
  2. Copy your API key
  3. Edit .env file and set: OPENROUTER_API_KEY=your-key-here
  4. Re-run setup
"""

# Network error during data import
"""
✗ Failed to download Scryfall data (network error)

Troubleshooting:
  • Check internet connection
  • Retry in a few minutes (Scryfall may be down)
  • Or skip data import: uv run python setup.py --skip-data
"""

# Dependency installation failure
"""
✗ Failed to install dependencies

Error from uv:
  [uv error output]

Troubleshooting:
  • Check internet connection
  • Try: uv sync --reinstall
  • Check for conflicting Python versions
"""
```

**Rationale:**
- Focus on errors we can actually detect and help with
- Python/uv errors already have good messages from the tools
- Reduces support burden (users self-service)
- Professional impression (well-polished tool)

## Risks / Trade-offs

### Risk: Subprocess Complexity
**Issue:** Calling `uv run python scripts/import_scryfall_data.py` adds subprocess overhead and complicates output capture.

**Mitigation:**
- Accept trade-off (simplicity of reuse > complexity of subprocess)
- Test thoroughly on Linux and macOS
- Document known limitations if Windows support is problematic

### Risk: Interactive Prompts in CI
**Issue:** Interactive prompts may hang in non-interactive environments (CI/CD).

**Mitigation:**
- Detect non-interactive terminal (`not sys.stdin.isatty()`)
- Fall back to non-interactive mode (skip prompts, require manual .env)
- Add `--non-interactive` flag for explicit CI usage

### Risk: API Key Security
**Issue:** Prompting for API key in terminal may expose it in shell history.

**Mitigation:**
- Use `getpass.getpass()` for hidden input (no echo to terminal)
- Validate key format before saving (basic sanity check)
- Document key rotation in README

### Trade-off: Rich Dependency
**Issue:** Adding `rich` increases dependency count and installation time.

**Benefit vs Cost:**
- Installation overhead: ~500KB, <1 second
- UX improvement: Significant (professional vs amateur appearance)
- Maintenance burden: Low (stable, widely used library)

**Conclusion:** UX benefit outweighs minimal cost.

## Migration Plan

**Prerequisites:**
- None (new feature, no existing code to migrate)

**Rollout:**
1. Implement `setup.py` script
2. Add unit tests for validation logic
3. Manual testing on Linux (WSL) and macOS
4. Update README.md with new setup instructions
5. Keep old manual setup instructions (advanced users section)
6. Announce in repository description/release notes

**Rollback:**
- Simple: Delete `setup.py`, revert README changes
- No breaking changes to existing workflows

**Data Migration:**
- None required (setup script creates new data, doesn't modify existing)

## Open Questions

1. **Should we add a `--all` flag for setup + data import + start app?**
   - Pros: Ultimate convenience for impatient users
   - Cons: Less visibility into what's happening, may not want auto-start
   - **Recommendation**: Skip for now, users can run two commands if needed

2. **Should we validate OpenRouter API key by making a test API call?**
   - Pros: Catches invalid keys immediately
   - Cons: Costs money (small amount), slower setup, requires network
   - **Recommendation**: Skip for now, just check if variable is non-empty

3. **Should we add telemetry to track setup success/failure rates?**
   - Pros: Helps identify common setup issues
   - Cons: Privacy concerns, requires backend infrastructure
   - **Recommendation**: No (out of scope for MVP, revisit post-launch)

## Summary

The setup script provides a critical improvement to the onboarding experience by automating tedious manual steps and providing clear guidance for common errors. The three-class architecture balances simplicity with testability, while the rich library investment delivers a professional UX appropriate for public release.

Key success criteria:
- New contributor can run `uv run python setup.py` and have a working environment in <5 minutes
- Error messages are self-documenting (95% of users self-service without asking for help)
- Data refresh is trivial (`uv run python setup.py --refresh-data`)
- Validation mode enables debugging (`uv run python setup.py --check`)
