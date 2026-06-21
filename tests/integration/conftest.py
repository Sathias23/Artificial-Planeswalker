"""Shared fixtures for core integration tests.

The Chainlit/UI mock fixtures (``mock_user_session``, ``mock_action``, ``action_message``)
were relocated to ``legacy/tests/conftest.py`` when the UI layer was archived to ``legacy/``
(Story 1.1).
"""

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.data.database import create_engine, create_session_factory, init_database
from src.data.models.card import CardModel
from src.search import ConnectionFactory, build_card_embeddings, compose_card_text
from src.search.embedder import EMBEDDING_DIM


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


# --- Semantic-search (card_vec-populated) fixture, Story 2.4 --------------------------------
#
# The shared ``seeded_card_db`` above builds ``cards`` via the async engine only and has NO
# ``card_vec`` (that needs the sync ``ConnectionFactory`` + sqlite-vec). Semantic-search tests
# need a DB with BOTH the relational rows AND a populated vector index, plus the SAME deterministic
# fake embedder used for the build so a query embeds to a known card's vector offline.


class _FakeVecEmbedder:
    """Deterministic offline embedder: each distinct composite text -> a distinct one-hot vector.

    Used for BOTH the index build (``encode_batch``) and the query path (``encode``) so that a
    query whose text equals a card's composed text embeds to that card's exact vector (distance 0)
    — KNN ranking is meaningful with no ~80 MB model download.
    """

    def __init__(self) -> None:
        self.dim = EMBEDDING_DIM
        self._assigned: dict[str, int] = {}

    def _vector_for(self, text: str) -> NDArray[np.float32]:
        if text not in self._assigned:
            self._assigned[text] = len(self._assigned) % EMBEDDING_DIM
        vec = np.zeros(EMBEDDING_DIM, dtype=np.float32)
        vec[self._assigned[text]] = 1.0
        return vec

    def encode(self, text: str) -> NDArray[np.float32]:
        return self._vector_for(text)

    def encode_batch(self, texts: list[str]) -> list[NDArray[np.float32]]:
        return [self._vector_for(t) for t in texts]


def _sample_vec_cards() -> list[CardModel]:
    """A richer card set for semantic-search tests: distinct texts spanning colours/mana/games.

    Distinct enough for deterministic one-hot ranking, and deliberately includes ``games`` (the
    3-card ``seeded_card_db`` omits them) and a **modern-only** red card so the format filter has a
    card to exclude from Standard.
    """
    return [
        CardModel(
            id="vec-dragon",
            name="Inferno Dragon",
            printed_name=None,
            oracle_id="oracle-inferno-dragon",
            mana_cost="{3}{R}{R}",
            cmc=5.0,
            type_line="Creature — Dragon",
            oracle_text="Flying. When Inferno Dragon attacks, it deals 3 damage to any target.",
            rarity="mythic",
            set_code="TST",
            set_name="Test Set",
            collector_number="1",
            colors=["R"],
            color_identity=["R"],
            keywords=["Flying"],
            legalities={"standard": "legal", "modern": "legal"},
            games=["arena", "paper"],
        ),
        CardModel(
            id="vec-goblin",
            name="Backstreet Goblin",
            printed_name=None,
            oracle_id="oracle-backstreet-goblin",
            mana_cost="{3}{R}",
            cmc=4.0,
            type_line="Creature — Goblin Rogue",
            oracle_text="Haste. Whenever Backstreet Goblin deals combat damage, draw a card.",
            rarity="rare",
            set_code="TST",
            set_name="Test Set",
            collector_number="2",
            colors=["R"],
            color_identity=["R"],
            keywords=["Haste"],
            legalities={"modern": "legal"},  # NOT standard-legal: the format filter excludes it
            games=["arena"],
        ),
        CardModel(
            id="vec-counter",
            name="Mind Dissolve",
            printed_name=None,
            oracle_id="oracle-mind-dissolve",
            mana_cost="{U}{U}",
            cmc=2.0,
            type_line="Instant",
            oracle_text="Counter target spell.",
            rarity="common",
            set_code="TST",
            set_name="Test Set",
            collector_number="3",
            colors=["U"],
            color_identity=["U"],
            keywords=[],  # real Scryfall data uses an empty array, not null, for no keywords
            legalities={"standard": "legal", "modern": "legal"},
            games=["arena", "paper"],
        ),
        CardModel(
            id="vec-elf",
            name="Verdant Elf",
            printed_name=None,
            oracle_id="oracle-verdant-elf",
            mana_cost="{G}",
            cmc=1.0,
            type_line="Creature — Elf Druid",
            oracle_text="{T}: Add {G}.",
            rarity="common",
            set_code="TST",
            set_name="Test Set",
            collector_number="4",
            colors=["G"],
            color_identity=["G"],
            keywords=[],  # real Scryfall data uses an empty array, not null, for no keywords
            legalities={"standard": "legal", "modern": "legal"},
            games=["paper"],
        ),
    ]


@dataclass
class SeededVecDB:
    """Bundle yielded by :func:`seeded_vec_db`: the async + sync seams plus the fake embedder.

    ``query_text`` composes the exact text a seeded card was indexed under, so a test can pass it
    as the ``query`` and have that card rank at distance 0 (the offline fake-embedder analogue of
    semantic similarity).
    """

    session_factory: async_sessionmaker[AsyncSession]
    connection_factory: ConnectionFactory
    embedder: _FakeVecEmbedder
    cards: list[CardModel]

    def query_text(self, name: str) -> str:
        """Return the composed embedding text for the seeded card named ``name``."""
        card = next(c for c in self.cards if c.name == name)
        return compose_card_text(
            card.name, card.type_line, card.mana_cost, card.oracle_text, card.keywords or []
        )


@pytest.fixture
async def seeded_vec_db(tmp_path: Path) -> AsyncGenerator[SeededVecDB, None]:
    """Yield a DB seeded with ``cards`` AND a populated ``card_vec`` (built by the fake embedder).

    Steps (WAL cross-connection visibility requires committing the seed BEFORE building vectors):

    1. File-backed DB; seed the richer ``_sample_vec_cards`` via the async engine; **commit**.
    2. On a sync ``ConnectionFactory(db_path=<same file>)``, run ``build_card_embeddings`` (which
       self-bootstraps ``card_vec`` + ``card_embedding_meta``) with the deterministic fake embedder.
    3. Yield the async ``session_factory``, the sync ``connection_factory``, the fake ``embedder``
       (the SAME instance, so ``build_server(embedder=…)`` query embeddings match the index), and
       the seed cards.
    """
    db_path = tmp_path / "vec_test.db"
    engine = create_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    await init_database(engine)
    session_factory = create_session_factory(engine)

    cards = _sample_vec_cards()
    async with session_factory() as session:
        for card in cards:
            session.add(card)
        await session.commit()  # commit before building vectors (WAL visibility on the sync conn)

    connection_factory = ConnectionFactory(db_path=str(db_path))
    embedder = _FakeVecEmbedder()
    build_card_embeddings(connection_factory.get_connection(), embedder)

    try:
        yield SeededVecDB(
            session_factory=session_factory,
            connection_factory=connection_factory,
            embedder=embedder,
            cards=cards,
        )
    finally:
        connection_factory.close()
        await engine.dispose()
