# project-setup Specification

## Purpose
TBD - created by archiving change add-setup-script. Update Purpose after archive.
## Requirements
### Requirement: Configuration Validation

The setup script SHALL validate configuration state before proceeding with setup operations.

#### Scenario: Environment file validation

- **GIVEN** the setup script is invoked
- **WHEN** validation runs
- **THEN** the script SHALL check if .env file exists
- **AND** SHALL check if OPENROUTER_API_KEY is set
- **AND** SHALL display validation status for each check

#### Scenario: Database validation

- **GIVEN** the setup script is invoked
- **WHEN** validation runs
- **THEN** the script SHALL check if database file exists
- **AND** SHALL query card count if database exists
- **AND** SHALL display database status (e.g., "35,847 cards" or "empty")

#### Scenario: Validation-only mode

- **GIVEN** the setup script is invoked with `--check` flag
- **WHEN** validation runs
- **THEN** the script SHALL display results of all validation checks
- **AND** SHALL NOT modify any files or install any packages
- **AND** SHALL exit with status code 0 if all checks pass, non-zero otherwise

### Requirement: Environment Configuration Management

The setup script SHALL create the .env file from the template and provide clear instructions for API key configuration.

#### Scenario: Create .env from template

- **GIVEN** no .env file exists in the project root
- **WHEN** setup runs in standard mode
- **THEN** the script SHALL copy .env.example to .env
- **AND** SHALL display a prominent message with instructions for adding the OpenRouter API key
- **AND** SHALL include the sign-up URL (https://openrouter.ai/keys)
- **AND** SHALL explain how to edit .env to add the key

#### Scenario: Preserve existing .env

- **GIVEN** an .env file already exists
- **WHEN** setup runs
- **THEN** the script SHALL NOT overwrite the existing .env
- **AND** SHALL validate that OPENROUTER_API_KEY is set
- **AND** SHALL display instructions to add key if missing

#### Scenario: API key validation

- **GIVEN** .env file exists
- **WHEN** setup validates configuration
- **THEN** the script SHALL check if OPENROUTER_API_KEY variable is present
- **AND** SHALL check if the value is non-empty
- **AND** SHALL display validation result (✓ API key configured / ✗ API key missing)

### Requirement: Dependency Installation

The setup script SHALL install all required dependencies using uv.

#### Scenario: Standard mode dependency installation

- **GIVEN** setup runs in standard mode (default)
- **WHEN** dependency installation runs
- **THEN** the script SHALL execute `uv sync`
- **AND** SHALL display progress during installation
- **AND** SHALL verify installation succeeded before proceeding

#### Scenario: Development mode dependency installation

- **GIVEN** setup runs with `--dev` flag
- **WHEN** dependency installation runs
- **THEN** the script SHALL execute `uv sync` (installs runtime + dev dependencies)
- **AND** SHALL install pre-commit hooks via `uv run pre-commit install`
- **AND** SHALL verify both installations succeeded

#### Scenario: Dependency installation failure

- **GIVEN** dependency installation fails (network error, version conflict)
- **WHEN** installation error occurs
- **THEN** the script SHALL display the error message from uv
- **AND** SHALL provide troubleshooting suggestions
- **AND** SHALL exit with non-zero status code

### Requirement: Scryfall Data Management

The setup script SHALL always prompt the user about card data import.

#### Scenario: Data import prompt

- **GIVEN** setup runs in standard mode (interactive)
- **WHEN** data import phase is reached
- **THEN** the script SHALL always prompt user whether to import card data
- **AND** SHALL display expected download size (~70MB) and time estimate (2-3 minutes)
- **AND** SHALL indicate current database state if database exists (e.g., "Database has 35,847 cards")
- **AND** SHALL indicate if database is required (e.g., "Required for app to work") if database is empty
- **AND** SHALL execute `scripts/import_scryfall_data.py` if user confirms
- **AND** SHALL display import progress

#### Scenario: Force data refresh

- **GIVEN** setup runs with `--refresh-data` flag
- **WHEN** data import runs
- **THEN** the script SHALL re-download Scryfall bulk data without prompting
- **AND** SHALL re-import all cards (replacing existing data)
- **AND** SHALL display progress throughout the process

#### Scenario: Skip data import

- **GIVEN** setup runs with `--skip-data` flag
- **WHEN** data import phase is reached
- **THEN** the script SHALL skip data import entirely without prompting
- **AND** SHALL display "Skipping data import" message
- **AND** SHALL continue with remaining setup steps

#### Scenario: Non-interactive data handling

- **GIVEN** setup runs with `--non-interactive` flag or in a non-TTY environment
- **WHEN** data import phase is reached
- **THEN** the script SHALL skip data import by default (no prompt)
- **AND** SHALL display message explaining data import was skipped
- **AND** SHALL provide instructions for running data import manually

### Requirement: Setup Verification

The setup script SHALL verify that the environment is correctly configured after setup.

#### Scenario: Health check execution

- **GIVEN** setup has completed all installation steps
- **WHEN** verification runs
- **THEN** the script SHALL verify database file exists
- **AND** SHALL verify .env file contains required variables
- **AND** SHALL display summary of verification results

#### Scenario: Verification failure

- **GIVEN** one or more verification checks fail
- **WHEN** verification completes
- **THEN** the script SHALL display which checks failed
- **AND** SHALL provide remediation suggestions for each failure
- **AND** SHALL exit with non-zero status code

### Requirement: Professional User Interface

The setup script SHALL provide clear, visually appealing terminal output using the rich library.

#### Scenario: Welcome message display

- **GIVEN** setup script starts
- **WHEN** script begins execution
- **THEN** the script SHALL display a welcome panel with app name and description
- **AND** SHALL display validation results in a formatted table

#### Scenario: Progress indication

- **GIVEN** setup is executing a long-running task
- **WHEN** task is in progress
- **THEN** the script SHALL display a progress spinner or bar
- **AND** SHALL show current step number and description
- **AND** SHALL update progress as task proceeds

#### Scenario: Error message display

- **GIVEN** an error occurs during setup
- **WHEN** error is encountered
- **THEN** the script SHALL display error in red with clear icon (✗)
- **AND** SHALL provide specific remediation steps
- **AND** SHALL format error details for easy reading

#### Scenario: Success message display

- **GIVEN** setup completes successfully
- **WHEN** all tasks finish
- **THEN** the script SHALL display success summary in a panel
- **AND** SHALL show next steps for running the application
- **AND** SHALL use green checkmarks (✓) for completed tasks

### Requirement: Multiple Operation Modes

The setup script SHALL support different modes of operation via command-line flags.

#### Scenario: Standard setup mode

- **GIVEN** script runs with no flags (default)
- **WHEN** setup executes
- **THEN** the script SHALL validate prerequisites
- **AND** SHALL install dependencies
- **AND** SHALL create .env file if missing
- **AND** SHALL optionally import card data
- **AND** SHALL verify setup succeeded

#### Scenario: Development setup mode

- **GIVEN** script runs with `--dev` flag
- **WHEN** setup executes
- **THEN** the script SHALL perform all standard setup steps
- **AND** SHALL additionally install pre-commit hooks
- **AND** SHALL verify git hooks are configured

#### Scenario: Start application mode

- **GIVEN** script runs with `--start` flag
- **WHEN** setup executes
- **THEN** the script SHALL validate environment is ready
- **AND** SHALL start Chainlit UI via `uv run chainlit run src/ui/app.py`
- **AND** SHALL forward app output to terminal

#### Scenario: Check-only mode

- **GIVEN** script runs with `--check` flag
- **WHEN** script executes
- **THEN** the script SHALL run all validation checks
- **AND** SHALL NOT modify any files or install packages
- **AND** SHALL display validation report

#### Scenario: Refresh data mode

- **GIVEN** script runs with `--refresh-data` flag
- **WHEN** script executes
- **THEN** the script SHALL validate prerequisites
- **AND** SHALL force re-download and re-import of Scryfall data
- **AND** SHALL verify data import succeeded

### Requirement: Idempotent Operation

The setup script SHALL be safe to run multiple times without breaking existing configuration.

#### Scenario: Re-running full setup

- **GIVEN** environment is already fully configured
- **WHEN** setup script runs again
- **THEN** the script SHALL detect existing configuration
- **AND** SHALL skip steps that are already complete
- **AND** SHALL display "already configured" messages for skipped steps
- **AND** SHALL NOT fail or overwrite working configuration

#### Scenario: Partial setup completion

- **GIVEN** setup was previously interrupted (e.g., network error during data import)
- **WHEN** setup script runs again
- **THEN** the script SHALL detect which steps completed successfully
- **AND** SHALL resume from the first incomplete step
- **AND** SHALL complete remaining setup tasks

### Requirement: Error Recovery Guidance

The setup script SHALL provide actionable guidance for common error scenarios.

#### Scenario: Missing API key

- **GIVEN** .env file exists but OPENROUTER_API_KEY is empty or missing
- **WHEN** validation detects missing key
- **THEN** the script SHALL display error message with key icon (✗)
- **AND** SHALL provide step-by-step instructions to add the key
- **AND** SHALL include link to https://openrouter.ai/keys
- **AND** SHALL instruct user to re-run setup after adding key

#### Scenario: Dependency installation failure

- **GIVEN** `uv sync` command fails
- **WHEN** dependency installation is attempted
- **THEN** the script SHALL display the error output from uv
- **AND** SHALL provide troubleshooting suggestions (check network, try --reinstall)
- **AND** SHALL exit with non-zero status code

#### Scenario: Network failure during data import

- **GIVEN** Scryfall data download fails (timeout, connection error)
- **WHEN** import fails
- **THEN** the script SHALL display network error message
- **AND** SHALL suggest retrying in a few minutes
- **AND** SHALL provide `--skip-data` option to continue without data

