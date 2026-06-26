"""Unit tests for the build-embeddings CLI bootstrap guard (cold-start ``cards`` table check).

Covers ``scripts/build_card_embeddings.py::_cards_table_populated`` — the probe that turns a deep
``no such table: cards`` failure into an actionable "import the corpus first" message (the bootstrap
cliff found in the semantic-tool live test).
"""

from scripts.build_card_embeddings import _cards_table_populated
from src.search import ConnectionFactory


def _make_factory(tmp_path) -> ConnectionFactory:
    return ConnectionFactory(db_path=str(tmp_path / "cards.db"))


def test_cards_table_populated_false_when_missing(tmp_path) -> None:
    """A fresh DB with no ``cards`` table reads as not-populated (no OperationalError)."""
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    assert _cards_table_populated(conn) is False
    factory.close()


def test_cards_table_populated_false_when_empty(tmp_path) -> None:
    """An existing but row-less ``cards`` table reads as not-populated."""
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    conn.execute("CREATE TABLE cards (id TEXT PRIMARY KEY, name TEXT NOT NULL)")
    conn.commit()
    assert _cards_table_populated(conn) is False
    factory.close()


def test_cards_table_populated_true_with_rows(tmp_path) -> None:
    """A ``cards`` table holding at least one row reads as populated."""
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    conn.execute("CREATE TABLE cards (id TEXT PRIMARY KEY, name TEXT NOT NULL)")
    conn.execute("INSERT INTO cards (id, name) VALUES ('x', 'Lightning Bolt')")
    conn.commit()
    assert _cards_table_populated(conn) is True
    factory.close()
