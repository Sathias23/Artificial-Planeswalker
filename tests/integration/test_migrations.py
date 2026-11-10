"""The ``scripts/migrate_*.py`` migrations are safe to run, and to re-run, on a populated database.

``CHANGELOG.md`` sends users with saved decks to run these scripts on their only database, so each
one is driven here through its real coroutine against a database this test builds: the current
schema from :func:`~src.data.database.init_database`, populated with one deck, two cards and one
``deck_cards`` row, then stripped back to the migration's pre-change shape with raw ``sqlite3``.
Every migration runs twice: the first run adds its column(s) and leaves every existing value
alone, the second changes nothing at all (schema and rows identical).

``migrate_add_card_vec.py`` is deliberately absent: it is due for deletion (story 5.1).

The database lives under the test's own ``tmp_path``: the root ``isolated_data_dir`` fixture points
``PLANESWALKER_DATA_DIR`` there and clears ``CARDS_DATABASE_URL``, so ``create_engine()`` with no
argument (the path every migration takes) opens ``tmp_path/cards.db`` and never the real data dir.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Awaitable, Callable
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

import scripts.migrate_add_deck_card_commander as commander_migration
import scripts.migrate_add_deck_strategy as strategy_migration
import scripts.migrate_add_game_changer as game_changer_migration
import scripts.migrate_add_power_toughness as power_toughness_migration
import scripts.migrate_deck_fields as deck_fields_migration
from src.data.database import create_engine, create_session_factory, init_database
from src.data.models.card import CardModel
from src.data.models.deck import DeckModel
from src.data.models.deck_card import DeckCardModel
from src.paths import database_path

_TABLES = ("decks", "cards", "deck_cards")
_STRATEGY_INDEX = "ix_decks_strategy"


@dataclass(frozen=True)
class Scenario:
    """One migration and the pre-change state it is run against."""

    run: Callable[[], Awaitable[Any]]
    table: str
    #: Columns removed from the current schema to make the pre-change database; each is one the
    #: migration must add back.
    missing: tuple[str, ...]
    #: What an existing row reads in each re-added column (``DEFAULT 0`` for ``commander``).
    defaults: dict[str, Any]


async def _run_deck_fields() -> None:
    # The one migration that reports failure by return value rather than ``sys.exit(1)``.
    assert await deck_fields_migration.migrate_deck_fields() is True


SCENARIOS = [
    pytest.param(
        Scenario(strategy_migration.migrate, "decks", ("strategy",), {"strategy": None}),
        id="deck_strategy",
    ),
    pytest.param(
        Scenario(
            _run_deck_fields,
            "decks",
            ("color_identity", "tags"),
            {"color_identity": None, "tags": None},
        ),
        id="deck_fields",
    ),
    pytest.param(
        Scenario(commander_migration.migrate, "deck_cards", ("commander",), {"commander": 0}),
        id="deck_card_commander",
    ),
    pytest.param(
        Scenario(
            game_changer_migration.migrate, "cards", ("game_changer",), {"game_changer": None}
        ),
        id="game_changer",
    ),
    pytest.param(
        Scenario(
            power_toughness_migration.migrate,
            "cards",
            ("power", "toughness"),
            {"power": None, "toughness": None},
        ),
        id="power_toughness",
    ),
    # Partial states: one of the migration's two columns already exists and holds a value.
    pytest.param(
        Scenario(_run_deck_fields, "decks", ("tags",), {"tags": None}),
        id="deck_fields_partial_color_identity_present",
    ),
    pytest.param(
        Scenario(power_toughness_migration.migrate, "cards", ("toughness",), {"toughness": None}),
        id="power_toughness_partial_power_present",
    ),
]


def _card(card_id: str, name: str, colour: str) -> CardModel:
    return CardModel(
        id=card_id,
        name=name,
        oracle_id=f"oracle-{card_id}",
        mana_cost=f"{{1}}{{{colour}}}",
        cmc=2.0,
        type_line="Creature — Test",
        oracle_text="A test creature.",
        rarity="common",
        set_code="TST",
        set_name="Test Set",
        collector_number=card_id,
        colors=[colour],
        color_identity=[colour],
        legalities={"commander": "legal"},
        games=["paper"],
        power="2",
        toughness="3",
        game_changer=True,
    )


async def _build_current_database() -> Path:
    """Create the current schema at the default database path and populate it.

    Every column a migration adds holds a non-default value here, so a migration that rewrote an
    existing value, rather than only adding a missing column, is visible in the row comparison.
    """
    engine = create_engine()
    try:
        await init_database(engine)
        async with create_session_factory(engine)() as session:
            session.add_all([_card("card-1", "Test Bear", "B"), _card("card-2", "Test Elk", "R")])
            deck = DeckModel(name="Populated Deck", format="commander", strategy="aristocrats")
            deck.color_identity_list = ["B", "R"]
            deck.tags_list = ["sacrifice", "tokens"]
            session.add(deck)
            await session.flush()
            session.add(
                DeckCardModel(
                    deck_id=deck.id, card_id="card-1", quantity=1, sideboard=False, commander=True
                )
            )
            await session.commit()
    finally:
        await engine.dispose()
    return database_path()


def _strip(path: Path, table: str, columns: tuple[str, ...]) -> None:
    """Return a current database to a migration's pre-change schema by dropping its columns."""
    with closing(sqlite3.connect(path)) as conn:
        if "strategy" in columns:
            # SQLite refuses to drop an indexed column, and the pre-change schema had no index.
            conn.execute(f"DROP INDEX {_STRATEGY_INDEX}")
        for column in columns:
            conn.execute(f"ALTER TABLE {table} DROP COLUMN {column}")
        conn.commit()


async def _pre_change_database(scenario: Scenario) -> Path:
    path = await _build_current_database()
    _strip(path, scenario.table, scenario.missing)
    return path


def _snapshot(path: Path) -> dict[str, dict[str, Any]]:
    """The schema (``table_info`` + ``index_list``) and every row of the three tables."""
    snapshot: dict[str, dict[str, Any]] = {}
    with closing(sqlite3.connect(path)) as conn:
        for table in _TABLES:
            columns = conn.execute(f"PRAGMA table_info({table})").fetchall()
            names = [column[1] for column in columns]
            rows = conn.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()
            snapshot[table] = {
                "columns": columns,
                "indexes": sorted(conn.execute(f"PRAGMA index_list({table})").fetchall()),
                "rows": [dict(zip(names, row, strict=True)) for row in rows],
            }
    return snapshot


def _column_names(snapshot: dict[str, dict[str, Any]], table: str) -> set[str]:
    return {column[1] for column in snapshot[table]["columns"]}


def _index_names(snapshot: dict[str, dict[str, Any]], table: str) -> set[str]:
    return {index[1] for index in snapshot[table]["indexes"]}


@pytest.mark.parametrize("scenario", SCENARIOS)
async def test_a_migration_adds_its_columns_and_a_rerun_changes_nothing(
    scenario: Scenario,
) -> None:
    """First run: the columns appear and existing values survive. Second run: nothing moves."""
    path = await _pre_change_database(scenario)
    before = _snapshot(path)
    assert not set(scenario.missing) & _column_names(before, scenario.table)

    await scenario.run()
    first = _snapshot(path)

    assert set(scenario.missing) <= _column_names(first, scenario.table)
    if "strategy" in scenario.missing:
        assert _STRATEGY_INDEX in _index_names(first, "decks")
    for table in _TABLES:
        assert len(first[table]["rows"]) == len(before[table]["rows"]) > 0
        for old, new in zip(before[table]["rows"], first[table]["rows"], strict=True):
            # Every pre-existing column keeps its value; only the re-added ones are new.
            assert {key: new[key] for key in old} == old
            if table == scenario.table:
                assert {key: new[key] for key in scenario.missing} == scenario.defaults

    await scenario.run()

    assert _snapshot(path) == first


async def test_a_failed_strategy_index_step_is_completed_by_a_rerun() -> None:
    """A run whose index step failed must not leave ``ix_decks_strategy`` uncreatable.

    The failure is real, not mocked: SQLite refuses ``CREATE INDEX`` while a table holds the
    index's name. The ``ALTER TABLE`` before it has already been committed (SQLite's driver
    autocommits DDL), so a re-run that keys only on the column would see it and stop short.
    """
    path = await _pre_change_database(
        Scenario(strategy_migration.migrate, "decks", ("strategy",), {"strategy": None})
    )
    with closing(sqlite3.connect(path)) as conn:
        conn.execute(f"CREATE TABLE {_STRATEGY_INDEX} (placeholder INTEGER)")
        conn.commit()

    with pytest.raises(SystemExit) as excinfo:
        await strategy_migration.migrate()
    assert excinfo.value.code == 1
    assert _STRATEGY_INDEX not in _index_names(_snapshot(path), "decks")

    with closing(sqlite3.connect(path)) as conn:
        conn.execute(f"DROP TABLE {_STRATEGY_INDEX}")
        conn.commit()

    await strategy_migration.migrate()

    after = _snapshot(path)
    assert "strategy" in _column_names(after, "decks")
    assert _STRATEGY_INDEX in _index_names(after, "decks")
