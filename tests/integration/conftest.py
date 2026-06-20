"""Shared fixtures for core integration tests.

The Chainlit/UI mock fixtures (``mock_user_session``, ``mock_action``, ``action_message``)
were relocated to ``legacy/tests/conftest.py`` when the UI layer was archived to ``legacy/``
(Story 1.1).
"""

from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.data.database import create_engine, create_session_factory, init_database
from src.data.models.card import CardModel


def _sample_cards() -> list[CardModel]:
    """Build a small set of cards exercising each lookup bucket.

    Includes two cards sharing the substring "bolt" (Lightning Bolt, Thunderbolt)
    so a partial query for "bolt" lands in the ambiguous bucket, plus a uniquely
    named card (Counterspell) for the single-match path.
    """
    return [
        CardModel(
            id="card-lightning-bolt",
            name="Lightning Bolt",
            printed_name=None,
            oracle_id="oracle-lightning-bolt",
            mana_cost="{R}",
            cmc=1.0,
            type_line="Instant",
            oracle_text="Lightning Bolt deals 3 damage to any target.",
            rarity="common",
            set_code="LEA",
            set_name="Limited Edition Alpha",
            collector_number="161",
            colors=["R"],
            color_identity=["R"],
            legalities={"standard": "legal", "modern": "legal"},
        ),
        CardModel(
            id="card-thunderbolt",
            name="Thunderbolt",
            printed_name=None,
            oracle_id="oracle-thunderbolt",
            mana_cost="{2}{R}",
            cmc=3.0,
            type_line="Instant",
            oracle_text="Choose one — Thunderbolt deals 3 damage to target attacking creature; or "
            "Thunderbolt deals 4 damage to target creature with flying.",
            rarity="common",
            set_code="POR",
            set_name="Portal",
            collector_number="143",
            colors=["R"],
            color_identity=["R"],
            legalities={"modern": "legal"},
        ),
        CardModel(
            id="card-counterspell",
            name="Counterspell",
            printed_name=None,
            oracle_id="oracle-counterspell",
            mana_cost="{U}{U}",
            cmc=2.0,
            type_line="Instant",
            oracle_text="Counter target spell.",
            rarity="common",
            set_code="LEA",
            set_name="Limited Edition Alpha",
            collector_number="54",
            colors=["U"],
            color_identity=["U"],
            legalities={"standard": "legal", "modern": "legal"},
        ),
    ]


@pytest.fixture
async def seeded_card_db(
    tmp_path: Path,
) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    """Yield a session factory bound to a file-backed SQLite DB seeded with cards.

    File-backed (not ``:memory:``) so that separately-opened sessions — the
    seeding session here and each tool's own ``async with session_factory()``
    block — all share the same database. Both ``cards`` and ``bug_reports``
    tables are created. Reusable across the Epic-1 MCP tool stories (1.3-1.6).
    """
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    await init_database(engine)
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        for card in _sample_cards():
            session.add(card)
        await session.commit()

    try:
        yield session_factory
    finally:
        await engine.dispose()
