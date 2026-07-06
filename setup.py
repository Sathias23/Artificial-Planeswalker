#!/usr/bin/env python3
"""
Setup script for Artificial-Planeswalker.

Performs one-time initialization:
1. Validates Python version and uv installation
2. Creates .env file from template
3. Initializes database and imports Scryfall data
4. Installs pre-commit hooks
"""

import asyncio
import subprocess
import sys
from pathlib import Path


def check_python_version() -> None:
    """Verify Python 3.12+ is installed."""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 12):
        msg = f"❌ Python 3.12+ required (current: {version.major}.{version.minor})"
        print(msg)
        sys.exit(1)
    print(f"✓ Python {version.major}.{version.minor}.{version.micro}")


def check_uv_installed() -> bool:
    """Check if uv is installed."""
    import shutil

    return shutil.which("uv") is not None


def install_uv() -> None:
    """Install uv package manager."""
    print("\n📦 Installing uv package manager...")
    try:
        curl_result = subprocess.run(
            ["curl", "-LsSf", "https://astral.sh/uv/install.sh"],
            stdout=subprocess.PIPE,
            check=True,
            text=True,
        )
        subprocess.run(
            ["sh", "-s", "--"],
            input=curl_result.stdout,
            check=True,
        )
        print("✓ uv installed successfully")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install uv: {e}")
        print("Please install manually: https://github.com/astral-sh/uv")
        sys.exit(1)


def sync_dependencies() -> None:
    """Install project dependencies using uv."""
    print("\n📦 Installing dependencies...")
    try:
        subprocess.run(["uv", "sync"], check=True)
        print("✓ Dependencies installed")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        sys.exit(1)


def setup_environment() -> None:
    """Create .env file from template if it doesn't exist."""
    env_path = Path(".env")
    env_example = Path(".env.example")

    if env_path.exists():
        print("✓ .env file exists")
        return

    if not env_example.exists():
        print("❌ .env.example not found")
        sys.exit(1)

    print("\n🔧 Creating .env file...")
    env_path.write_text(env_example.read_text())
    print("✓ .env created from template")
    print("   Defaults work out of the box (SQLite in the central OS data dir, stdio transport);")
    print("   editing .env is optional — no API key is required for the MCP server.")


def initialize_database() -> None:
    """Run the DB bootstrap inside the uv-managed environment.

    This script is invoked with the *system* interpreter (`python3 setup.py`), where the
    project's dependencies are not importable — `uv sync` provisions a project venv, not
    the invoking Python. Re-exec the DB step through `uv run` so the imports resolve.
    """
    try:
        subprocess.run(["uv", "run", "python", "setup.py", "--init-db"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to initialize database: {e}")
        sys.exit(1)


async def _init_db() -> None:
    """Initialize the database and import Scryfall card data if not already present.

    Idempotent: creating the schema is a no-op when it exists, and the (multi-minute)
    Scryfall import is skipped when the cards table is already populated. No API key is
    involved — the Scryfall bulk endpoint is public.
    """
    print("\n💾 Initializing database...")

    from sqlalchemy import func, select

    from src.data import create_engine, create_session_factory, init_database
    from src.data.importers.scryfall import import_scryfall_bulk_data
    from src.data.models.card import CardModel

    engine = create_engine()
    await init_database(engine)
    print("✓ Database initialized")

    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        existing = await session.scalar(select(func.count()).select_from(CardModel))
        if existing:
            print(f"✓ Database already has {existing:,} cards — skipping Scryfall import")
            return

        print("\n📥 Importing Scryfall card data (this may take 2-3 minutes)...")
        stats = await import_scryfall_bulk_data(session, bulk_type="oracle_cards")

    print(f"✓ Imported {stats.total_inserted:,} cards in {stats.elapsed_time():.1f}s")
    print(f"  ({stats.cards_per_second():.0f} cards/second)")


def install_git_hooks() -> None:
    """Install pre-commit git hooks."""
    print("\n🪝 Installing git hooks...")
    try:
        subprocess.run(["uv", "run", "pre-commit", "install"], check=True)
        print("✓ Git hooks installed")
    except subprocess.CalledProcessError as e:
        print(f"⚠️  Warning: Failed to install git hooks: {e}")


def print_next_steps() -> None:
    """Print post-setup instructions."""
    print("\n" + "=" * 60)
    print("🎉 Setup complete!")
    print("=" * 60)
    print("\nThis project is a stateless MCP server, consumed by an MCP client")
    print("(e.g. Claude Code) — the client is the LLM; the server makes no LLM calls.")
    print("\nRun it directly (stdio transport by default):")
    print("   uv run python -m src.mcp_server")
    print("\nOr let an MCP client launch it: .mcp.json already points at that command,")
    print("so a client opened in this directory exposes the tools automatically.")
    print("\nRun the test suite:")
    print("   uv run pytest")
    print()


def main() -> None:
    """Run the setup process."""
    if "--init-db" in sys.argv:
        # Child process re-exec'd by initialize_database(): runs inside the uv venv,
        # where the project imports resolve. Do only the DB step.
        asyncio.run(_init_db())
        return

    print("=" * 60)
    print("Artificial-Planeswalker Setup")
    print("=" * 60)

    # 1. Check Python version
    check_python_version()

    # 2. Install uv if needed
    if not check_uv_installed():
        install_uv()
    else:
        print("✓ uv package manager")

    # 3. Install dependencies
    sync_dependencies()

    # 4. Create .env file
    setup_environment()

    # 5. Initialize database and import card data (idempotent: skips if already populated)
    initialize_database()

    # 6. Install git hooks
    install_git_hooks()

    # 7. Print next steps
    print_next_steps()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Setup interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
