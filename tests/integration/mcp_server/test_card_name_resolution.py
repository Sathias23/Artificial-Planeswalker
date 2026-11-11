"""Card-name resolution, driven through a real MCP session on every tool that takes a name.

Six tools resolve a card name: ``lookup_card_by_name``, ``add_card_to_deck``, ``set_card_quantity``,
``remove_card_from_deck``, ``import_decklist`` and ``find_similar_cards``. This file pins what they
share: an exact match on ``name`` or ``printed_name`` in any case, a substring fallback on either,
one candidate per Oracle card, the candidate cap and its wording, the blank-name guard and the
``games`` pass-through.

Every database is a ``tmp_path`` file built by the production engine and ``init_database`` (real
schema, connect hooks, the NOCASE name indexes); the vector index, where a test needs one, is built
by the deterministic fake embedder. Despite living under ``tests/integration/`` these run in the
ordinary ``-m "not integration"`` set: nothing here opens a socket or reads the real database.
"""

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

import src.mcp_server.server as server_module
from src.data.database import create_engine, create_session_factory, init_database
from src.data.models.card import CardModel
from src.data.repositories.deck import DeckRepository
from src.search import ConnectionFactory, build_card_embeddings
from tests.fixtures.embedder import FakeEmbedder


def _card(
    card_id: str,
    name: str,
    *,
    printed_name: str | None = None,
    oracle_id: str | None = None,
    oracle_text: str | None = None,
    games: Sequence[str] = ("paper", "arena"),
    legalities: dict[str, str] | None = None,
) -> CardModel:
    """A minimal valid card; ``oracle_text`` defaults to one naming the card (distinct vectors)."""
    return CardModel(
        id=card_id,
        name=name,
        printed_name=printed_name,
        oracle_id=oracle_id if oracle_id is not None else f"oracle-{card_id}",
        mana_cost="{1}{R}",
        cmc=2.0,
        type_line="Creature — Test",
        oracle_text=oracle_text if oracle_text is not None else f"{name} does a thing.",
        rarity="common",
        set_code="TST",
        set_name="Test Set",
        collector_number="1",
        colors=["R"],
        color_identity=["R"],
        keywords=[],
        legalities=legalities if legalities is not None else {"standard": "legal"},
        games=list(games),
    )


@dataclass
class World:
    """One ``tmp_path`` card database and the two seams the server reaches it through."""

    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    connection_factory: ConnectionFactory
    db_path: Path

    async def seed(self, cards: list[CardModel], *, index: bool = False) -> None:
        """Commit ``cards``; with ``index``, also build ``card_vec`` with the fake embedder."""
        async with self.session_factory() as session:
            session.add_all(cards)
            await session.commit()
        if index:
            build_card_embeddings(self.connection_factory.get_connection(), FakeEmbedder())

    async def deck(self, *card_ids: str) -> str:
        """Create a deck holding one copy of each card in ``card_ids``; return its id."""
        async with self.session_factory() as session:
            repo = DeckRepository(session)
            deck = await repo.create_deck(name="Resolver", format="standard")
            for card_id in card_ids:
                await repo.add_card_to_deck(deck.id, card_id, 1)
            return deck.id

    def server(self, connection_factory: Any = None) -> Any:
        return server_module.build_server(
            session_factory=self.session_factory,
            connection_factory=connection_factory or self.connection_factory,
        )


@pytest.fixture
async def world(tmp_path: Path) -> AsyncIterator[World]:
    db_path = tmp_path / "cards.db"
    engine = create_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    await init_database(engine)
    connection_factory = ConnectionFactory(db_path=str(db_path))
    try:
        yield World(engine, create_session_factory(engine), connection_factory, db_path)
    finally:
        connection_factory.close()
        await engine.dispose()


async def _call(server: Any, tool: str, args: dict[str, Any]) -> dict[str, Any]:
    """Call one tool in its own MCP session and return its structured answer."""
    (answer,) = await _call_many(server, [(tool, args)])
    return answer


async def _call_many(server: Any, calls: list[tuple[str, dict[str, Any]]]) -> list[dict[str, Any]]:
    """Call each ``(tool, args)`` in one MCP session; none may answer ``isError``."""
    answers = []
    async with create_connected_server_and_client_session(server) as client:
        for tool, args in calls:
            result = await client.call_tool(tool, args)
            assert not result.isError, (tool, result.content)
            assert result.structuredContent is not None, tool
            answers.append(result.structuredContent)
    return answers


def _match_names(answer: dict[str, Any]) -> list[str]:
    return [match["name"] for match in answer["matches"]]


# --- B2-P5: printed-name matching, on all six name tools --------------------------------------
#
# "Oracle Wanderer" is printed as "Printed Pilgrim", and a second card's *name* contains that
# printed name, so the exact query resolves only if the exact step matches ``printed_name`` (the
# substring step alone would be ambiguous). "Oracle Hermit" is printed as "Velvet Saint", and the
# substring query hits that printed name and nothing else.

_PRINTED_CARDS = (
    ("c-wanderer", "Oracle Wanderer", "Printed Pilgrim"),
    ("c-guide", "Printed Pilgrim Guide", None),
    ("c-hermit", "Oracle Hermit", "Velvet Saint"),
)

_PRINTED_QUERIES = [
    pytest.param("pRINTED pILGRIM", "c-wanderer", id="exact-printed-name-any-case"),
    pytest.param("elvet sain", "c-hermit", id="substring-of-printed-name"),
]


async def _printed_world(world: World) -> None:
    await world.seed(
        [_card(cid, name, printed_name=printed) for cid, name, printed in _PRINTED_CARDS],
        index=True,
    )


@pytest.mark.parametrize(("query", "expected_id"), _PRINTED_QUERIES)
async def test_lookup_resolves_a_printed_name(world: World, query: str, expected_id: str) -> None:
    await _printed_world(world)

    answer = await _call(world.server(), "lookup_card_by_name", {"card_name": query})

    assert answer["status"] == "found", answer["message"]
    assert answer["card"]["id"] == expected_id


@pytest.mark.parametrize(("query", "expected_id"), _PRINTED_QUERIES)
async def test_add_card_resolves_a_printed_name(world: World, query: str, expected_id: str) -> None:
    await _printed_world(world)
    deck_id = await world.deck()

    answer = await _call(world.server(), "add_card_to_deck", {"deck_id": deck_id, "name": query})

    assert answer["status"] == "ok", answer["message"]
    assert answer["card_id"] == expected_id


@pytest.mark.parametrize(("query", "expected_id"), _PRINTED_QUERIES)
async def test_set_quantity_resolves_a_printed_name(
    world: World, query: str, expected_id: str
) -> None:
    await _printed_world(world)
    deck_id = await world.deck("c-wanderer", "c-guide", "c-hermit")

    answer = await _call(
        world.server(), "set_card_quantity", {"deck_id": deck_id, "name": query, "quantity": 3}
    )

    assert answer["status"] == "ok", answer["message"]
    assert answer["card_id"] == expected_id
    assert answer["quantity"] == 3


@pytest.mark.parametrize(("query", "expected_id"), _PRINTED_QUERIES)
async def test_remove_card_resolves_a_printed_name(
    world: World, query: str, expected_id: str
) -> None:
    await _printed_world(world)
    deck_id = await world.deck("c-wanderer", "c-guide", "c-hermit")

    answer = await _call(
        world.server(), "remove_card_from_deck", {"deck_id": deck_id, "name": query}
    )

    assert answer["status"] == "ok", answer["message"]
    assert answer["card_id"] == expected_id


@pytest.mark.parametrize(("query", "expected_id"), _PRINTED_QUERIES)
async def test_import_resolves_a_printed_name(world: World, query: str, expected_id: str) -> None:
    await _printed_world(world)
    deck_id = await world.deck()

    answer = await _call(
        world.server(),
        "import_decklist",
        {"deck_id": deck_id, "arena_export": f"Deck\n2 {query} (TST) 1"},
    )

    assert answer["status"] == "ok", answer["message"]
    (line,) = answer["results"]
    assert line["status"] == "ok", line["message"]
    assert line["card_id"] == expected_id


@pytest.mark.parametrize(("query", "expected_id"), _PRINTED_QUERIES)
async def test_find_similar_resolves_a_printed_name_seed(
    world: World, query: str, expected_id: str
) -> None:
    await _printed_world(world)

    answer = await _call(world.server(), "find_similar_cards", {"card_name": query})

    assert answer["status"] == "ok", answer["message"]
    assert answer["seed"]["id"] == expected_id


# --- B9-P14: lookup's cap, blank-name guard and games pass-through ----------------------------


async def test_lookup_caps_an_eleven_match_query_at_ten(world: World) -> None:
    await world.seed([_card(f"c-{i:02d}", f"Zq Beast {i:02d}") for i in range(11)])

    answer = await _call(world.server(), "lookup_card_by_name", {"card_name": "zq beast"})

    assert answer["status"] == "ambiguous"
    assert answer["card"] is None
    assert len(answer["matches"]) == 10
    assert _match_names(answer) == [f"Zq Beast {i:02d}" for i in range(10)]
    assert "refine" in answer["message"].lower()
    assert "more than 10" in answer["message"]


async def test_a_blank_name_is_refused_without_a_like_query(world: World) -> None:
    """Every name tool refuses a whitespace name, and no tool sends a LIKE for it."""
    await world.seed([_card("c-elf", "Verdant Elf")], index=True)
    deck_id = await world.deck("c-elf")
    statements: list[str] = []

    def capture(conn, cursor, statement, parameters, context, executemany) -> None:
        statements.append(statement)

    event.listen(world.engine.sync_engine, "before_cursor_execute", capture)
    try:
        lookup, add, set_quantity, remove, similar = await _call_many(
            world.server(),
            [
                ("lookup_card_by_name", {"card_name": "   "}),
                ("add_card_to_deck", {"deck_id": deck_id, "name": "   "}),
                ("set_card_quantity", {"deck_id": deck_id, "name": "   ", "quantity": 2}),
                ("remove_card_from_deck", {"deck_id": deck_id, "name": "   "}),
                ("find_similar_cards", {"card_name": "   "}),
            ],
        )
    finally:
        event.remove(world.engine.sync_engine, "before_cursor_execute", capture)

    assert lookup["status"] == "not_found"
    assert "must not be empty" in lookup["message"]
    assert [add["status"], set_quantity["status"], remove["status"]] == ["invalid"] * 3
    assert similar["status"] == "invalid"
    assert not [sql for sql in statements if "LIKE" in sql.upper()], statements


async def test_lookup_passes_games_through(world: World) -> None:
    """A paper-only card is ``not_found`` for an Arena-only lookup, and found without one."""
    await world.seed([_card("c-paper", "Paperbound Relic", games=("paper",))])

    arena, unfiltered = await _call_many(
        world.server(),
        [
            ("lookup_card_by_name", {"card_name": "Paperbound Relic", "games": ["arena"]}),
            ("lookup_card_by_name", {"card_name": "Paperbound Relic"}),
        ],
    )

    assert arena["status"] == "not_found"
    assert unfiltered["status"] == "found"
    assert unfiltered["card"]["id"] == "c-paper"


# --- B9-P16: find_similar's seed branches ----------------------------------------------------


async def test_find_similar_caps_an_eleven_oracle_partial_at_ten(world: World) -> None:
    """Eleven Oracle cards, two printings each: ten candidates, one per Oracle card."""
    cards = []
    for i in range(11):
        for printing in ("a", "b"):
            cards.append(
                _card(
                    f"c-{i:02d}{printing}",
                    f"Zq Seed {i:02d}",
                    oracle_id=f"oracle-zq-{i:02d}",
                    oracle_text=f"Zq Seed {i:02d} printing {printing}.",
                )
            )
    await world.seed(cards, index=True)

    answer = await _call(world.server(), "find_similar_cards", {"card_name": "zq seed"})

    assert answer["status"] == "ambiguous"
    assert answer["seed"] is None
    assert len(answer["matches"]) == 10
    assert _match_names(answer) == [f"Zq Seed {i:02d}" for i in range(10)]
    assert "refine" in answer["message"].lower()
    assert "more than 10" in answer["message"]


async def test_find_similar_collapses_printings_to_one_candidate_per_oracle(world: World) -> None:
    cards = [
        _card(
            f"c-{oracle}-{n}",
            f"Goblin {oracle.title()}",
            oracle_id=f"oracle-{oracle}",
            oracle_text=f"Goblin {oracle} printing {n}.",
        )
        for oracle in ("raider", "chief")
        for n in range(3)
    ]
    await world.seed(cards, index=True)

    answer = await _call(world.server(), "find_similar_cards", {"card_name": "goblin"})

    assert answer["status"] == "ambiguous"
    assert sorted(_match_names(answer)) == ["Goblin Chief", "Goblin Raider"]
    assert "which one" in answer["message"].lower()


async def test_find_similar_treats_a_blank_format_as_no_filter(world: World) -> None:
    """A whitespace ``format`` is no filter: a modern-only alternative still comes back."""
    await world.seed(
        [
            _card("c-seed", "Seed Dragon"),
            _card("c-modern", "Modern Wyrm", legalities={"modern": "legal"}),
        ],
        index=True,
    )

    blank, standard = await _call_many(
        world.server(),
        [
            ("find_similar_cards", {"card_name": "Seed Dragon", "format": "   "}),
            ("find_similar_cards", {"card_name": "Seed Dragon", "format": "standard"}),
        ],
    )

    assert blank["status"] == "ok", blank["message"]
    assert [hit["card"]["id"] for hit in blank["cards"]] == ["c-modern"]
    assert standard["status"] == "empty", "control: a real format filter excludes the card"


# --- The bounded read: "more than 10", and at most 11 rows ever read ---------------------------
#
# Thirty cards contain "zq". Their ids run opposite to their names, so name order (the resolver's)
# and id order (the old seed resolver's) give different first tens.

_THIRTY_NAMES = [f"Zq Beast {i:02d}" for i in range(30)]


def _thirty_cards() -> list[CardModel]:
    return [_card(f"c-{29 - i:02d}", name) for i, name in enumerate(_THIRTY_NAMES)]


class _LoadCounter:
    """Counts ``CardModel`` instances the ORM builds from rows (one per row read)."""

    def __init__(self) -> None:
        self.loads = 0

    def __call__(self, target: Any, context: Any) -> None:
        self.loads += 1


async def test_a_two_letter_lookup_says_more_than_ten_and_reads_at_most_eleven_rows(
    world: World,
) -> None:
    await world.seed(_thirty_cards())
    counter = _LoadCounter()

    event.listen(CardModel, "load", counter)
    try:
        answer = await _call(world.server(), "lookup_card_by_name", {"card_name": "zq"})
    finally:
        event.remove(CardModel, "load", counter)

    assert answer["status"] == "ambiguous"
    assert _match_names(answer) == _THIRTY_NAMES[:10]
    assert answer["message"] == (
        "Found more than 10 cards matching 'zq'. Please refine your search; showing the first 10."
    )
    assert counter.loads <= 11, f"read {counter.loads} card rows for ten candidates"


async def test_a_deck_tool_says_more_than_ten_for_a_cut_candidate_list(world: World) -> None:
    await world.seed(_thirty_cards())
    deck_id = await world.deck()

    answer = await _call(world.server(), "add_card_to_deck", {"deck_id": deck_id, "name": "zq"})

    assert answer["status"] == "ambiguous"
    assert _match_names(answer) == _THIRTY_NAMES[:10]
    assert answer["message"] == (
        "'zq' matches more than 10 cards. Re-call with a specific card_id, or refine the name."
    )


@dataclass
class _Statement:
    sql: str
    params: Any
    rows: int = 0


class _CountingCursor:
    """A cursor that adds every row it hands back to its statement's count."""

    def __init__(self, cursor: Any, statement: _Statement) -> None:
        self._cursor = cursor
        self._statement = statement

    def fetchone(self) -> Any:
        row = self._cursor.fetchone()
        if row is not None:
            self._statement.rows += 1
        return row

    def fetchall(self) -> list[Any]:
        rows = self._cursor.fetchall()
        self._statement.rows += len(rows)
        return rows

    def __iter__(self) -> Any:
        for row in self._cursor:
            self._statement.rows += 1
            yield row

    def __getattr__(self, name: str) -> Any:
        return getattr(self._cursor, name)


class _TracingConnection:
    """A sqlite3 connection stand-in that records each statement and the rows it returned."""

    def __init__(self, conn: Any, log: list[_Statement]) -> None:
        self._conn = conn
        self._log = log

    def execute(self, sql: str, params: Any = ()) -> _CountingCursor:
        statement = _Statement(sql, params)
        self._log.append(statement)
        return _CountingCursor(self._conn.execute(sql, params), statement)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._conn, name)


class _TracingFactory:
    """Hands the server traced connections over a real :class:`ConnectionFactory`."""

    def __init__(self, real: ConnectionFactory) -> None:
        self._real = real
        self.log: list[_Statement] = []

    def get_connection(self) -> _TracingConnection:
        return _TracingConnection(self._real.get_connection(), self.log)


def _seed_statements(log: list[_Statement]) -> list[_Statement]:
    """The seed resolver's name reads, in order: the statements on ``cards`` that compare names."""
    return [s for s in log if "FROM cards" in s.sql and "name" in s.sql.lower().split("where")[-1]]


async def test_a_two_letter_seed_says_more_than_ten_and_reads_at_most_eleven_rows(
    world: World,
) -> None:
    await world.seed(_thirty_cards(), index=True)
    tracing = _TracingFactory(world.connection_factory)

    answer = await _call(world.server(tracing), "find_similar_cards", {"card_name": "zq"})

    assert answer["status"] == "ambiguous"
    assert _match_names(answer) == _THIRTY_NAMES[:10]
    assert answer["message"] == (
        "Found more than 10 cards matching 'zq'. Please refine your search, or re-call with a "
        "specific card_id; showing the first 10."
    )
    reads = _seed_statements(tracing.log)
    assert len(reads) == 2, [s.sql for s in tracing.log]  # the exact step, then the partial
    assert all(s.rows <= 11 for s in reads), [(s.rows, s.sql) for s in reads]


@pytest.mark.parametrize("count", [7, 10])
async def test_six_to_ten_matches_report_the_exact_count(world: World, count: int) -> None:
    await world.seed([_card(f"c-{i:02d}", f"Zq Beast {i:02d}") for i in range(count)], index=True)

    lookup, similar = await _call_many(
        world.server(),
        [
            ("lookup_card_by_name", {"card_name": "zq"}),
            ("find_similar_cards", {"card_name": "zq"}),
        ],
    )

    assert lookup["message"] == f"Found {count} cards matching 'zq'. Please refine your search."
    assert similar["message"] == (
        f"Found {count} cards matching 'zq'. Please refine your search, or re-call with a "
        "specific card_id."
    )
    assert len(lookup["matches"]) == len(similar["matches"]) == count


# --- LIKE wildcards in user text are literal ---------------------------------------------------

_WILDCARD_CARDS = (
    ("c-fifty", "Fifty 50% Off", "Pay 50% of your life, rounded up."),
    ("c-lot", "Lot 50 Gold", "You gain 50 life."),
)


async def test_a_percent_sign_in_a_name_or_phrase_is_literal(world: World) -> None:
    """``50%`` names the card containing ``50%``, not every card containing ``50``."""
    await world.seed(
        [_card(cid, name, oracle_text=text) for cid, name, text in _WILDCARD_CARDS], index=True
    )
    deck_id = await world.deck()

    lookup, add, search, similar = await _call_many(
        world.server(),
        [
            ("lookup_card_by_name", {"card_name": "50%"}),
            ("add_card_to_deck", {"deck_id": deck_id, "name": "50%"}),
            ("search_cards", {"oracle_text": ["50%"]}),
            ("find_similar_cards", {"card_name": "50%"}),
        ],
    )

    assert lookup["status"] == "found", lookup["message"]
    assert lookup["card"]["id"] == "c-fifty"
    assert add["status"] == "ok", add["message"]
    assert add["card_id"] == "c-fifty"
    assert [card["id"] for card in search["cards"]] == ["c-fifty"]
    assert similar["status"] == "ok", similar["message"]
    assert similar["seed"]["id"] == "c-fifty"


async def test_an_underscore_in_a_name_is_literal(world: World) -> None:
    await world.seed([_card("c-under", "Glyph A_Z Rune"), _card("c-any", "Glyph AQZ Rune")])

    answer = await _call(world.server(), "lookup_card_by_name", {"card_name": "a_z"})

    assert answer["status"] == "found", answer["message"]
    assert answer["card"]["id"] == "c-under"


# --- find_similar's exact seed match is index-served -----------------------------------------


async def test_find_similar_seed_exact_match_is_an_index_search(world: World) -> None:
    """The traced exact-seed statement's plan searches both NOCASE name indexes, never scans."""
    await world.seed(
        [_card("c-seed", "Seed Dragon", printed_name="Printed Dragon"), _card("c-alt", "Alt")],
        index=True,
    )
    tracing = _TracingFactory(world.connection_factory)

    answer = await _call(world.server(tracing), "find_similar_cards", {"card_name": "SEED dragon"})

    assert answer["status"] == "ok", answer["message"]
    exact = _seed_statements(tracing.log)[0]
    plan = world.connection_factory.get_connection().execute(
        "EXPLAIN QUERY PLAN " + exact.sql, exact.params
    )
    lines = [str(row[-1]) for row in plan.fetchall()]
    detail = "\n".join(lines)
    assert "SEARCH cards USING INDEX ix_cards_name_nocase" in detail, (exact.sql, detail)
    assert "SEARCH cards USING INDEX ix_cards_printed_name_nocase" in detail, (exact.sql, detail)
    assert not any(line.startswith("SCAN cards") for line in lines), (exact.sql, detail)
