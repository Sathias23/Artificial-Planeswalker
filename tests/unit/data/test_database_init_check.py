"""Unit tests for the async ``is_database_initialized`` guard (``src/data/database.py``).

Verifies the three first-run states the relational tools rely on: the ``cards`` table missing
entirely (fresh install — no schema), present-but-empty (schema created, import not run), and
populated. All three must resolve without raising so the tools can return a graceful
``database_not_initialized`` instead of leaking an ``OperationalError``.
"""

from pathlib import Path

from src.data.database import (
    create_engine,
    create_session_factory,
    init_database,
    is_database_initialized,
)
from src.data.models.card import CardModel


def _card() -> CardModel:
    return CardModel(
        id="c-1",
        name="Lightning Bolt",
        printed_name=None,
        oracle_id="oracle-c-1",
        mana_cost="{R}",
        cmc=1.0,
        type_line="Instant",
        oracle_text="Deals 3 damage.",
        rarity="common",
        set_code="TST",
        set_name="Test Set",
        collector_number="1",
        colors=["R"],
        color_identity=["R"],
        legalities={"standard": "legal"},
    )


async def test_returns_false_when_cards_table_missing(tmp_path: Path) -> None:
    # Fresh DB file, no schema created at all.
    engine = create_engine(f"sqlite+aiosqlite:///{(tmp_path / 'fresh.db').as_posix()}")
    try:
        async with create_session_factory(engine)() as session:
            assert await is_database_initialized(session) is False
    finally:
        await engine.dispose()


async def test_returns_false_when_cards_table_empty(tmp_path: Path) -> None:
    # Schema created (init_database) but no rows imported.
    engine = create_engine(f"sqlite+aiosqlite:///{(tmp_path / 'empty.db').as_posix()}")
    await init_database(engine)
    try:
        async with create_session_factory(engine)() as session:
            assert await is_database_initialized(session) is False
    finally:
        await engine.dispose()


async def test_returns_true_when_cards_present(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite+aiosqlite:///{(tmp_path / 'full.db').as_posix()}")
    await init_database(engine)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            session.add(_card())
            await session.commit()
        async with factory() as session:
            assert await is_database_initialized(session) is True
    finally:
        await engine.dispose()
