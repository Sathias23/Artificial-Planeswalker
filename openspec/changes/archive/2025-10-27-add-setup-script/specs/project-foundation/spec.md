## MODIFIED Requirements

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
