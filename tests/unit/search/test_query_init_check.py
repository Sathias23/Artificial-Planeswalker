"""Unit tests for the sync ``is_database_initialized`` guard (``src/search/query.py``).

The sync counterpart used by the sqlite-vec tools (``semantic_search_cards`` /
``find_similar_cards`` / ``build_search_index``). Mirrors the async variant's three-state contract
(missing table, empty table, populated) and must never raise (parallels ``index_is_populated``).
"""

import sqlite3

from src.search.query import is_database_initialized


def test_returns_false_when_cards_table_missing() -> None:
    conn = sqlite3.connect(":memory:")
    try:
        assert is_database_initialized(conn) is False
    finally:
        conn.close()


def test_returns_false_when_cards_table_empty() -> None:
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE TABLE cards (id TEXT PRIMARY KEY, name TEXT)")
        conn.commit()
        assert is_database_initialized(conn) is False
    finally:
        conn.close()


def test_returns_true_when_cards_present() -> None:
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE TABLE cards (id TEXT PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO cards (id, name) VALUES ('c-1', 'Lightning Bolt')")
        conn.commit()
        assert is_database_initialized(conn) is True
    finally:
        conn.close()
