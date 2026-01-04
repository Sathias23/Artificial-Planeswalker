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
import os
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
    import subprocess

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
    import subprocess

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
    print("\n⚠️  IMPORTANT: Edit .env and add your OPENROUTER_API_KEY")
    print("   Get your key at: https://openrouter.ai/keys")


def check_api_key() -> bool:
    """Check if OPENROUTER_API_KEY is set in .env."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        # dotenv not installed yet, will be installed by uv sync
        return False

    load_dotenv()
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()

    # Check if key exists and is not the placeholder
    if not api_key or api_key == "your-key-here":
        return False
    return True


async def initialize_database() -> None:
    """Initialize database and import Scryfall data."""
    print("\n💾 Initializing database...")

    # Import here to avoid dependency issues before sync
    from src.data import create_engine, create_session_factory, init_database
    from src.data.importers.scryfall import import_scryfall_bulk_data

    engine = create_engine()
    await init_database(engine)
    print("✓ Database initialized")

    print("\n📥 Importing Scryfall card data (this may take 2-3 minutes)...")
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        stats = await import_scryfall_bulk_data(session, bulk_type="oracle_cards")

    print(f"✓ Imported {stats.total_inserted:,} cards in {stats.elapsed_time():.1f}s")
    print(f"  ({stats.cards_per_second():.0f} cards/second)")


def install_git_hooks() -> None:
    """Install pre-commit git hooks."""
    import subprocess

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
    print("\nNext steps:")
    print("1. Edit .env and add your OPENROUTER_API_KEY")
    print("   Get your key at: https://openrouter.ai/keys")
    print("\n2. Start the application:")
    print("   uv run chainlit run src/ui/app.py")
    print("\n3. Open your browser to the URL shown (usually http://localhost:8000)")
    print("\nFor development with auto-reload:")
    print("   uv run chainlit run src/ui/app.py -w")
    print()


async def main() -> None:
    """Run the setup process."""
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

    # 5. Check API key
    has_api_key = check_api_key()
    if not has_api_key:
        print("\n⚠️  Skipping database import - OPENROUTER_API_KEY not configured")
        print("   Run this script again after adding your API key to .env")
    else:
        # 6. Initialize database and import data
        await initialize_database()

    # 7. Install git hooks
    install_git_hooks()

    # 8. Print next steps
    print_next_steps()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Setup interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
