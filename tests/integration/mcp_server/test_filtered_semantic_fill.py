"""Filtered semantic searches come back full, and say so when they cannot.

Drives both sync tool helpers (``semantic_search_cards`` and ``find_similar_cards``) over a
``tmp_path`` database built by ``init_database`` (the shared ``empty_card_db`` fixture), with cards
placed at chosen distances from one query vector by
:class:`~tests.fixtures.embedder.RankedEmbedder`. A ``format="standard"`` filter that keeps none of
the nearest 200 vectors must still fill ``limit`` from further out; one whose matches lie past the
4,096-vector cap must say, in ``message``, that ``search_cards`` filters the whole database.

The orphan vectors that crowd the window (a ``card_vec`` row whose card an update removed) go on
every build: through the ``build_search_index`` helper and the ``build_card_embeddings.py`` CLI
alike, except while a first-run import is still in progress.
"""

import logging
import sqlite3
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import scripts.build_card_embeddings as build_cli
from src.data.import_state import mark_import_started
from src.mcp_server.tools.build_search_index import build_search_index
from src.mcp_server.tools.find_similar import find_similar_cards
from src.mcp_server.tools.messages import semantic_cap_note
from src.mcp_server.tools.semantic_search import semantic_search_cards
from src.search import (
    CARD_EMBEDDING_META_TABLE,
    CARD_VEC_TABLE,
    ConnectionFactory,
    build_card_embeddings,
)
from tests.fixtures.embedder import RankedEmbedder, seed_ranked_cards

#: The seed sits on the query vector (rank 0) and is not standard-legal, so both tools look for the
#: same legal cards: ``find_similar_cards`` excludes the seed, the format filter drops it from
#: ``semantic_search_cards``.
_SEED = "seed"


@pytest.fixture
def factory(
    empty_card_db: async_sessionmaker[AsyncSession], card_db_path: Path
) -> Iterator[ConnectionFactory]:
    """A sync connection factory on the ``init_database``-built file ``empty_card_db`` made."""
    connection_factory = ConnectionFactory(db_path=str(card_db_path))
    try:
        yield connection_factory
    finally:
        connection_factory.close()


def _index(factory: ConnectionFactory, *, last_rank: int, legal: list[int]) -> RankedEmbedder:
    """Seed ranks 1..``last_rank`` (standard-legal at the ``legal`` ranks) plus the seed; index."""
    conn = factory.get_connection()
    ranks = {_SEED: 0}
    for rank in range(1, last_rank + 1):
        ranks[f"{'ok' if rank in legal else 'bad'}-{rank:04d}"] = rank
    embedder = seed_ranked_cards(conn, ranks, standard_legal=[f"ok-{rank:04d}" for rank in legal])
    build_card_embeddings(conn, embedder)
    return embedder


def test_starved_standard_filter_fills_limit_in_both_tools(factory: ConnectionFactory) -> None:
    """300 nearer illegal cards: both tools still return all ten legal ones, and no cap note."""
    legal = list(range(301, 311))
    embedder = _index(factory, last_rank=310, legal=legal)
    conn = factory.get_connection()
    expected = [f"ok-{rank:04d}" for rank in legal]

    search = semantic_search_cards(conn, embedder, "query", format="standard", limit=10)
    similar = find_similar_cards(conn, card_id=_SEED, format="standard", limit=10)

    assert search.status == "ok"
    assert [hit.card.id for hit in search.cards] == expected
    assert "search_cards" not in search.message
    assert similar.status == "ok"
    assert [hit.card.id for hit in similar.cards] == expected
    assert "search_cards" not in similar.message


def test_short_at_the_cap_ok_message_names_search_cards(factory: ConnectionFactory) -> None:
    """Three legal cards inside the nearest 4,096, the rest past it: ``ok`` plus the cap note."""
    embedder = _index(factory, last_rank=4110, legal=[1000, 2000, 3000, *range(4101, 4111)])
    conn = factory.get_connection()
    expected = ["ok-1000", "ok-2000", "ok-3000"]

    search = semantic_search_cards(conn, embedder, "query", format="standard", limit=10)
    similar = find_similar_cards(conn, card_id=_SEED, format="standard", limit=10)

    assert search.status == "ok"
    assert [hit.card.id for hit in search.cards] == expected
    assert search.message.endswith(semantic_cap_note(3))
    assert similar.status == "ok"
    assert [hit.card.id for hit in similar.cards] == expected
    assert similar.message.endswith(semantic_cap_note(3))


def test_nothing_inside_the_cap_empty_message_names_search_cards(
    factory: ConnectionFactory,
) -> None:
    """Every legal card lies past the nearest 4,096: ``empty`` plus the cap note."""
    embedder = _index(factory, last_rank=4110, legal=list(range(4101, 4111)))
    conn = factory.get_connection()

    search = semantic_search_cards(conn, embedder, "query", format="standard", limit=10)
    similar = find_similar_cards(conn, card_id=_SEED, format="standard", limit=10)

    assert search.status == "empty"
    assert search.message.endswith(semantic_cap_note(0))
    assert similar.status == "empty"
    assert similar.message.endswith(semantic_cap_note(0))


# --- Orphan vectors go on every build ---------------------------------------------------------

#: The cards an update's reconcile "removed" in these tests: their vectors become orphans.
_DELETED = [f"bad-{rank:04d}" for rank in range(1, 6)]


def _delete_cards(conn: sqlite3.Connection) -> None:
    conn.executemany("DELETE FROM cards WHERE id = ?", [(card_id,) for card_id in _DELETED])
    conn.commit()


def _orphans(conn: sqlite3.Connection) -> set[str]:
    """``card_vec`` ids with no ``cards`` row, after checking the hash table holds the same ids."""
    vec_ids = {row[0] for row in conn.execute(f"SELECT card_id FROM {CARD_VEC_TABLE}")}
    meta_ids = {row[0] for row in conn.execute(f"SELECT card_id FROM {CARD_EMBEDDING_META_TABLE}")}
    assert vec_ids == meta_ids
    return vec_ids - {row[0] for row in conn.execute("SELECT id FROM cards")}


def test_default_build_search_index_drops_vectors_of_removed_cards(
    factory: ConnectionFactory,
) -> None:
    embedder = _index(factory, last_rank=20, legal=[])
    conn = factory.get_connection()
    _delete_cards(conn)
    assert _orphans(conn) == set(_DELETED)

    result = build_search_index(factory, embedder=embedder)

    assert result.status == "ok"
    assert result.cards_pruned == len(_DELETED)
    assert "Removed 5 vectors of cards no longer in the database." in result.message
    assert _orphans(conn) == set()


def test_default_cli_build_drops_vectors_of_removed_cards(
    factory: ConnectionFactory, card_db_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    embedder = _index(factory, last_rank=20, legal=[])
    conn = factory.get_connection()
    _delete_cards(conn)
    monkeypatch.setenv("CARDS_DATABASE_URL", f"sqlite+aiosqlite:///{card_db_path.as_posix()}")
    monkeypatch.setattr(sys, "argv", ["build_card_embeddings.py"])
    monkeypatch.setattr(build_cli, "get_embedder", lambda: embedder)

    assert build_cli.main() == 0

    assert _orphans(conn) == set()


async def test_build_skips_the_prune_while_a_first_run_import_is_in_progress(
    empty_card_db: async_sessionmaker[AsyncSession],
    factory: ConnectionFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A half-imported ``cards`` table makes every not-yet-imported card look gone: keep them."""
    embedder = _index(factory, last_rank=20, legal=[])
    conn = factory.get_connection()
    _delete_cards(conn)
    async with empty_card_db() as session:
        await mark_import_started(session)

    with caplog.at_level(logging.INFO, logger="src.search.index_builder"):
        stats = build_card_embeddings(conn, embedder)

    assert stats.pruned == 0
    assert _orphans(conn) == set(_DELETED)
    assert "Skipped the orphan-vector prune" in caplog.text
