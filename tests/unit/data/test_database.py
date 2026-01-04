"""Unit tests for database configuration."""

from src.data.database import create_engine, create_session_factory


def test_create_engine_default_url() -> None:
    """Test engine creation with default DATABASE_URL."""
    engine = create_engine()

    assert engine is not None
    assert "sqlite" in str(engine.url)


def test_create_engine_custom_url() -> None:
    """Test engine creation with custom database URL."""
    custom_url = "sqlite+aiosqlite:///:memory:"
    engine = create_engine(custom_url)

    assert engine is not None
    assert str(engine.url) == custom_url


def test_create_session_factory() -> None:
    """Test session factory creation."""
    engine = create_engine("sqlite+aiosqlite:///:memory:")
    session_factory = create_session_factory(engine)

    assert session_factory is not None
    assert session_factory.kw["expire_on_commit"] is False
    assert session_factory.kw["autoflush"] is False
    assert session_factory.kw["autocommit"] is False


def test_session_factory_creates_sessions() -> None:
    """Test that session factory can create AsyncSession instances."""
    engine = create_engine("sqlite+aiosqlite:///:memory:")
    session_factory = create_session_factory(engine)

    # Verify factory can create a session (don't actually use it in sync test)
    assert callable(session_factory)
