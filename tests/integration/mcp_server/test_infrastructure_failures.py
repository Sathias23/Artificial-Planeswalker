"""Every tool answers an infrastructure failure as a status, through a real MCP session.

"Never raise" is every tool's contract, and until the edge guard (``src/mcp_server/tools/
failures.py``) the readiness probe, the sqlite-vec connection and the embedder load all ran outside
each tool's own ``try``. This file drives **all 28 tools** through an in-process MCP client under
four injected failures and asserts that none answers ``isError`` and that each status is one its
result model declares (read from the tool's own advertised ``outputSchema``, so a status the model
does not declare cannot pass):

* **corrupt file** — ``cards.db`` holds bytes that are not a SQLite database;
* **locked file** — another connection holds an exclusive lock (the engine's and the connection
  factory's busy-timeout seams keep the wait to milliseconds);
* **missing vector extension** — ``sqlite_vec.load`` fails the way a missing DLL does;
* **offline first model load** — fastembed cannot load the model from any source.

Then the other half of the contract — a non-infrastructure exception still surfaces as
``isError`` — and one test per behaviour bug the guard work fixed: compare's side B runs after a
side-A probe failure, a deck deleted between the check and the write is ``deck_not_found``, the
semantic tool never loads the model for an unbuilt index, and ``initialize_database`` blames the
network only when the network failed.

**Nothing here can reach the network or the real data directory.** Every database is a ``tmp_path``
file; ``CARDS_DATABASE_URL`` points ``initialize_database`` at the scenario's file; the Scryfall
importer and the fastembed loader are replaced in every test by stubs that record a call and raise;
``FASTEMBED_CACHE_DIR`` is a ``tmp_path`` folder; and the autouse ``isolated_data_dir`` fixture
keeps the companion tools from finding a live companion.

Despite living under ``tests/integration/``, these run in the ordinary ``-m "not integration"`` set:
a directory is not a marker (AD-10), and nothing here opens a socket.
"""

import functools
import sqlite3
from collections.abc import AsyncGenerator, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import pytest
import sqlite_vec
from mcp.shared.memory import create_connected_server_and_client_session
from sqlalchemy import delete
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import ProgrammingError as SQLAlchemyProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import src.mcp_server.server as server_module
import src.search.embedder as embedder_module
from src.data.database import create_engine, create_session_factory, init_database
from src.data.importers.scryfall import ScryfallImportError
from src.data.importers.scryfall_api import ScryfallAPIError
from src.data.models.card import CardModel
from src.data.models.deck import DeckModel
from src.data.repositories.card import CardRepository
from src.data.repositories.deck import DeckRepository
from src.mcp_server.tools import assess_deck_power as assess_module
from src.mcp_server.tools import initialize_database as initialize_database_module
from src.mcp_server.tools.failures import DETAIL_LIMIT
from src.mcp_server.tools.initialize_database import initialize_database
from src.search import ConnectionFactory
from src.search.embedder import MODEL_NAME, reset_embedder
from tests.integration.conftest import SeededVecDB, _sample_vec_cards

#: No busy wait at all: a locked file answers "database is locked" at once instead of after the
#: production 5 s (and each connect hook pays that wait again). Even 10 ms costs ~0.2 s per tool on
#: Windows, whose sleep granularity rounds every busy-handler nap up.
_NO_BUSY_WAIT = 0

_COMPANION_PUSH_TOOLS = (
    "companion_show_suggestions",
    "companion_show_swaps",
    "companion_show_tier_list",
    "companion_show_groups",
)

#: The three tools that reach the database through the sync sqlite-vec connection.
_VECTOR_TOOLS = ("semantic_search_cards", "find_similar_cards", "build_search_index")

_ABSENT_DECK = "deck-that-does-not-exist"


def _tool_calls(deck_id: str) -> dict[str, dict[str, Any]]:
    """Valid arguments for all 28 tools, in a call order that keeps every one meaningful.

    The destructive pair is defanged: ``delete_deck`` and ``view_deck`` target an absent deck (no
    deletion, no file, no browser), ``initialize_database`` runs with ``update`` off and
    ``build_search_index`` without ``rebuild``.
    """
    return {
        "lookup_card_by_name": {"card_name": "Inferno Dragon"},
        "search_cards": {"colors": ["R"]},
        "list_decks": {},
        "create_deck": {"name": "Probe"},
        "clone_deck": {"deck_id": deck_id},
        "load_deck": {"deck_id": deck_id},
        "update_deck": {"deck_id": deck_id, "changes": {"name": "Renamed"}},
        "delete_deck": {"deck_id": _ABSENT_DECK},
        "add_card_to_deck": {"deck_id": deck_id, "card_id": "vec-elf"},
        "set_card_quantity": {"deck_id": deck_id, "card_id": "vec-dragon", "quantity": 3},
        "import_decklist": {"deck_id": deck_id, "arena_export": "Deck\n1 Verdant Elf (TST) 4"},
        "remove_card_from_deck": {"deck_id": deck_id, "card_id": "vec-counter"},
        "view_deck": {"deck_id": _ABSENT_DECK, "open_browser": False},
        "companion_status": {},
        "companion_set_active_deck": {"deck_id": deck_id},
        "companion_show_suggestions": {"payload": {"items": []}},
        "companion_show_swaps": {"payload": {"items": []}},
        "companion_show_tier_list": {"payload": {"items": []}},
        "companion_show_groups": {"payload": {"items": []}},
        "analyze_mana_curve": {"deck_id": deck_id},
        "detect_synergies": {"deck_id": deck_id},
        "validate_deck": {"deck_id": deck_id},
        "assess_deck_power": {"deck_id": deck_id},
        "compare_deck_power": {"deck_id_a": deck_id, "deck_id_b": deck_id},
        "semantic_search_cards": {"query": "flying red dragon"},
        "find_similar_cards": {"card_name": "Inferno Dragon"},
        "initialize_database": {},
        "build_search_index": {},
    }


@dataclass
class Answer:
    """One tool's answer: the wire flag, its status and its human-facing text."""

    is_error: bool
    status: str | None
    text: str
    declared: frozenset[str]


@dataclass
class OfflineStubs:
    """What the network stubs saw: Scryfall import attempts and fastembed model constructions."""

    imports: list[str] = field(default_factory=list)
    model_loads: list[str] = field(default_factory=list)


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[OfflineStubs]:
    """Stub the two network-reaching loaders for every test in this file, and record their use.

    The importer stub raises (a scenario that reached it would answer ``error`` instead of its
    expected status) and the model stub raises fastembed's own offline ``ValueError``. Both record
    first, so a test can also assert they were never reached.
    """
    stubs = OfflineStubs()

    async def no_scryfall(session: AsyncSession, *, bulk_type: str = "default_cards") -> None:
        stubs.imports.append(bulk_type)
        raise AssertionError("the Scryfall importer must never run in this file")

    class OfflineTextEmbedding:
        def __init__(self, model_name: str, cache_dir: str) -> None:
            stubs.model_loads.append(model_name)
            raise ValueError(f"Could not load model {model_name} from any source.")

    monkeypatch.setattr(initialize_database_module, "import_scryfall_bulk_data", no_scryfall)
    monkeypatch.setattr(embedder_module, "_load_text_embedding", lambda: OfflineTextEmbedding)
    monkeypatch.setenv("FASTEMBED_CACHE_DIR", str(tmp_path / "fastembed"))
    # initialize_database builds its own engine; the short busy wait keeps the locked file fast.
    monkeypatch.setattr(
        initialize_database_module,
        "create_engine",
        functools.partial(create_engine, busy_timeout=_NO_BUSY_WAIT),
    )
    reset_embedder()
    yield stubs
    reset_embedder()


def _point_initialize_database_at(monkeypatch: pytest.MonkeyPatch, db_path: Path) -> None:
    monkeypatch.setenv("CARDS_DATABASE_URL", f"sqlite+aiosqlite:///{db_path.as_posix()}")


def _text_of(structured: dict[str, Any] | None) -> str:
    if not structured:
        return ""
    return str(structured.get("message") or structured.get("summary") or "")


async def _call_every_tool(server: Any, deck_id: str) -> dict[str, Answer]:
    """Call all 28 tools in one MCP session and return each answer, keyed by tool name.

    Also pins the coverage itself: the tools called must be exactly the tools the server lists, so
    a 29th tool cannot be added without joining every scenario here.
    """
    calls = _tool_calls(deck_id)
    answers: dict[str, Answer] = {}
    async with create_connected_server_and_client_session(server) as client:
        listed = {tool.name: tool for tool in (await client.list_tools()).tools}
        assert set(listed) == set(calls), "every listed tool is driven, and nothing else"
        assert len(listed) == 28
        for name, args in calls.items():
            result = await client.call_tool(name, args)
            schema = listed[name].outputSchema or {}
            declared = frozenset(schema.get("properties", {}).get("status", {}).get("enum", ()))
            structured = result.structuredContent
            answers[name] = Answer(
                is_error=bool(result.isError),
                status=structured.get("status") if structured else None,
                text=_text_of(structured)
                or "\n".join(getattr(block, "text", "") for block in result.content),
                declared=declared,
            )
    return answers


def _contract_problems(answers: dict[str, Answer]) -> list[str]:
    """AC 1 for every tool: no ``isError``, and a status the result model declares."""
    problems = []
    for name, answer in answers.items():
        if answer.is_error:
            problems.append(f"{name}: isError ({answer.text[:200]})")
        elif answer.status not in answer.declared:
            problems.append(f"{name}: status {answer.status!r} not in {sorted(answer.declared)}")
    return problems


def _database_failure_problems(answers: dict[str, Answer]) -> list[str]:
    """Corrupt or locked: every database tool answers ``error``, the rest their usual status."""
    problems = _contract_problems(answers)
    for name, answer in answers.items():
        if name == "companion_status":
            expected = "not_running"
        elif name in _COMPANION_PUSH_TOOLS:
            expected = "app_not_running"
        elif name == "compare_deck_power":
            expected = "both_decks_failed"
        else:
            expected = "error"
        if answer.status != expected:
            problems.append(f"{name}: expected {expected!r}, got {answer.status!r}")
    return problems


async def _seed_relational(session_factory: async_sessionmaker[AsyncSession]) -> str:
    """Add the vec card set and one small Standard deck; return the deck id."""
    async with session_factory() as session:
        session.add_all(_sample_vec_cards())
        await session.commit()
        repo = DeckRepository(session)
        deck = await repo.create_deck(name="Infra", format="standard")
        await repo.add_card_to_deck(deck.id, "vec-dragon", 2)
        await repo.add_card_to_deck(deck.id, "vec-counter", 1)
        return deck.id


async def _seed_vec_deck(seeded_vec_db: SeededVecDB) -> str:
    async with seeded_vec_db.session_factory() as session:
        repo = DeckRepository(session)
        deck = await repo.create_deck(name="Infra", format="standard")
        await repo.add_card_to_deck(deck.id, "vec-dragon", 2)
        await repo.add_card_to_deck(deck.id, "vec-counter", 1)
        return deck.id


# --- the four injected failures × all 28 tools ---------------------------------------------------


@pytest.fixture
async def corrupt_db(tmp_path: Path) -> AsyncGenerator[tuple[Path, Any], None]:
    """A ``cards.db`` that is not a SQLite file, and the async session factory over it."""
    db_path = tmp_path / "cards.db"
    db_path.write_bytes(b"this is not a SQLite database, just some bytes\n" * 200)
    engine = create_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}", busy_timeout=_NO_BUSY_WAIT)
    yield db_path, create_session_factory(engine)
    await engine.dispose()


async def test_a_corrupt_file_answers_error_from_every_database_tool(
    corrupt_db, monkeypatch: pytest.MonkeyPatch, offline: OfflineStubs
) -> None:
    db_path, session_factory = corrupt_db
    _point_initialize_database_at(monkeypatch, db_path)
    server = server_module.build_server(
        session_factory=session_factory,
        connection_factory=ConnectionFactory(db_path=str(db_path), busy_timeout_ms=0),
    )

    answers = await _call_every_tool(server, "deck-anything")

    assert _database_failure_problems(answers) == []
    # The edge names the driver's own reason, not SQLAlchemy's statement echo.
    for name in ("lookup_card_by_name", "list_decks", "load_deck", "semantic_search_cards"):
        assert "not a database" in answers[name].text, (name, answers[name].text)
        assert "SELECT" not in answers[name].text
    assert "not a database" in answers["initialize_database"].text
    assert "network" not in answers["initialize_database"].text.lower()
    assert db_path.read_bytes().startswith(b"this is not a SQLite database"), "nothing wrote to it"
    assert offline.imports == [] and offline.model_loads == []


@pytest.fixture
async def locked_db(tmp_path: Path) -> AsyncGenerator[tuple[Path, Any, str], None]:
    """A seeded database (rollback journal, so a lock blocks readers) under ``BEGIN EXCLUSIVE``.

    Built through the async engine only: the sync connection factory would switch the file to WAL,
    under which an exclusive writer no longer blocks readers.
    """
    db_path = tmp_path / "cards.db"
    seed_engine = create_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    await init_database(seed_engine)
    deck_id = await _seed_relational(create_session_factory(seed_engine))
    await seed_engine.dispose()

    engine = create_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}", busy_timeout=_NO_BUSY_WAIT)
    holder = sqlite3.connect(db_path, isolation_level=None)
    assert holder.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
    holder.execute("BEGIN EXCLUSIVE")
    try:
        yield db_path, create_session_factory(engine), deck_id
    finally:
        holder.execute("ROLLBACK")
        holder.close()
        await engine.dispose()


async def test_a_locked_file_answers_error_from_every_database_tool(
    locked_db, monkeypatch: pytest.MonkeyPatch, offline: OfflineStubs
) -> None:
    db_path, session_factory, deck_id = locked_db
    _point_initialize_database_at(monkeypatch, db_path)
    server = server_module.build_server(
        session_factory=session_factory,
        connection_factory=ConnectionFactory(db_path=str(db_path), busy_timeout_ms=0),
    )

    answers = await _call_every_tool(server, deck_id)

    assert _database_failure_problems(answers) == []
    for name in ("lookup_card_by_name", "list_decks", "load_deck", "find_similar_cards"):
        assert "locked" in answers[name].text, (name, answers[name].text)
        assert "try again" in answers[name].text, "the lock hint tells the caller to wait and retry"
    assert offline.imports == [] and offline.model_loads == []


async def test_a_missing_vector_extension_answers_error_from_the_three_vector_tools(
    seeded_vec_db: SeededVecDB, monkeypatch: pytest.MonkeyPatch, offline: OfflineStubs
) -> None:
    deck_id = await _seed_vec_deck(seeded_vec_db)
    db_path = Path(seeded_vec_db.connection_factory.db_path)
    _point_initialize_database_at(monkeypatch, db_path)

    def missing_dll(conn: sqlite3.Connection) -> None:
        raise sqlite3.OperationalError("The specified module could not be found.")

    monkeypatch.setattr(sqlite_vec, "load", missing_dll)
    server = server_module.build_server(
        session_factory=seeded_vec_db.session_factory,
        connection_factory=ConnectionFactory(db_path=str(db_path)),
    )

    answers = await _call_every_tool(server, deck_id)

    problems = _contract_problems(answers)
    for name, answer in answers.items():
        if name in _VECTOR_TOOLS:
            if answer.status != "error" or "sqlite-vec" not in answer.text:
                problems.append(f"{name}: expected an error naming sqlite-vec, got {answer}")
        elif answer.status == "error":
            problems.append(f"{name}: a relational tool was affected ({answer.text})")
    assert problems == []
    assert offline.imports == [] and offline.model_loads == []


async def test_an_offline_first_model_load_answers_error_from_the_two_embedding_tools(
    seeded_vec_db: SeededVecDB, monkeypatch: pytest.MonkeyPatch, offline: OfflineStubs
) -> None:
    deck_id = await _seed_vec_deck(seeded_vec_db)
    db_path = Path(seeded_vec_db.connection_factory.db_path)
    _point_initialize_database_at(monkeypatch, db_path)
    # embedder=None: the production path, resolving the process singleton through the stubbed
    # loader. find_similar_cards reads stored vectors and must not care.
    server = server_module.build_server(
        session_factory=seeded_vec_db.session_factory,
        connection_factory=ConnectionFactory(db_path=str(db_path)),
    )

    answers = await _call_every_tool(server, deck_id)

    problems = _contract_problems(answers)
    for name, answer in answers.items():
        if name in ("semantic_search_cards", "build_search_index"):
            if answer.status != "error" or MODEL_NAME not in answer.text:
                problems.append(f"{name}: expected an error naming the model, got {answer}")
        elif name == "find_similar_cards":
            if answer.status != "ok":
                problems.append(f"{name}: expected ok (it never embeds), got {answer}")
        elif answer.status == "error":
            problems.append(f"{name}: a tool that never embeds was affected ({answer.text})")
    assert problems == []
    assert offline.model_loads, "the non-vacuity twin: the model load really was attempted"
    assert offline.imports == []


async def test_a_failed_fastembed_import_answers_error_naming_the_model(
    seeded_vec_db: SeededVecDB, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fastembed / ONNX Runtime import itself fails (a Windows "DLL load failed"): the
    semantic tool on a built index answers ``error`` naming the model, not an ``isError``."""

    def broken_import() -> type:
        raise ImportError("DLL load failed while importing onnxruntime_pybind11_state")

    monkeypatch.setattr(embedder_module, "_load_text_embedding", broken_import)
    server = server_module.build_server(
        session_factory=seeded_vec_db.session_factory,
        connection_factory=ConnectionFactory(db_path=seeded_vec_db.connection_factory.db_path),
    )
    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool("semantic_search_cards", {"query": "flying red dragon"})

    assert result.isError is False
    assert result.structuredContent["status"] == "error"
    assert MODEL_NAME in result.structuredContent["message"]
    assert "DLL load failed" in result.structuredContent["message"]


async def test_an_offline_model_with_an_unbuilt_index_is_index_unavailable_without_a_load(
    seeded_card_db: async_sessionmaker[AsyncSession], card_db_path: Path, offline: OfflineStubs
) -> None:
    """The embedder is resolved after both guards: an unbuilt index never loads the model."""
    server = server_module.build_server(
        session_factory=seeded_card_db,
        connection_factory=ConnectionFactory(db_path=str(card_db_path)),
    )
    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool("semantic_search_cards", {"query": "burn spell"})

    assert result.isError is False
    assert result.structuredContent["status"] == "index_unavailable"
    assert offline.model_loads == [], "the model was never loaded (nor downloaded)"


# --- the guard swallows nothing else -------------------------------------------------------------


def _raise(exc: BaseException):
    def helper(*args: object, **kwargs: object) -> object:
        raise exc

    async def async_helper(*args: object, **kwargs: object) -> object:
        raise exc

    return helper, async_helper


@pytest.mark.parametrize(
    ("tool", "args", "helper_name", "exc", "is_async"),
    [
        pytest.param(
            "list_decks", {}, "_list_decks_helper", TypeError("a bug"), True, id="TypeError"
        ),
        pytest.param(
            "load_deck",
            {"deck_id": "d-1"},
            "_load_deck_helper",
            SQLAlchemyProgrammingError("SELECT", {}, sqlite3.ProgrammingError("bad binding")),
            True,
            id="sqlalchemy-ProgrammingError",
        ),
        pytest.param(
            "find_similar_cards",
            {"card_name": "Lightning Bolt"},
            "_find_similar_helper",
            sqlite3.ProgrammingError("Cannot operate on a closed database."),
            False,
            id="sqlite3-ProgrammingError",
        ),
        pytest.param(
            "semantic_search_cards",
            {"query": "burn"},
            "_semantic_search_helper",
            ValueError("an unwrapped third-party ValueError"),
            False,
            id="ValueError",
        ),
    ],
)
async def test_a_non_infrastructure_exception_still_surfaces_as_an_mcp_error(
    seeded_card_db, card_db_path: Path, monkeypatch, tool, args, helper_name, exc, is_async
) -> None:
    """AC 2: the guard catches exactly the infrastructure set; a bug still reaches the client."""
    sync_helper, async_helper = _raise(exc)
    monkeypatch.setattr(server_module, helper_name, async_helper if is_async else sync_helper)
    server = server_module.build_server(
        session_factory=seeded_card_db,
        connection_factory=ConnectionFactory(db_path=str(card_db_path)),
    )
    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool(tool, args)

    assert result.isError is True
    assert result.structuredContent is None


async def test_the_edge_message_is_the_driver_text_capped_with_a_lock_hint(
    seeded_card_db, monkeypatch
) -> None:
    """The message carries ``exc.orig``'s text (never the SQL echo), capped, with the retry hint."""
    long_reason = "database is locked " + "x" * 400

    async def locked(*args: object, **kwargs: object) -> object:
        raise OperationalError(
            "SELECT secret_column FROM decks",
            ("bound-value",),
            sqlite3.OperationalError(long_reason),
        )

    monkeypatch.setattr(server_module, "_list_decks_helper", locked)
    server = server_module.build_server(session_factory=seeded_card_db)
    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool("list_decks", {})

    assert result.isError is False
    message = result.structuredContent["message"]
    assert result.structuredContent["status"] == "error"
    assert "database is locked" in message
    assert "secret_column" not in message and "bound-value" not in message
    assert "x" * DETAIL_LIMIT not in message, "the driver text is capped"
    assert "try again" in message


# --- the behaviour bugs ---------------------------------------------------------------------------


async def test_a_side_a_probe_failure_still_assesses_side_b(
    seeded_card_db, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Compare's side A probe raises; the arm rolls back and side B is assessed on the session."""
    async with seeded_card_db() as session:
        repo = DeckRepository(session)
        deck_a = (await repo.create_deck(name="A", format="standard")).id
        deck_b = (await repo.create_deck(name="B", format="standard")).id
        await repo.add_card_to_deck(deck_a, "card-lightning-bolt", 4)
        await repo.add_card_to_deck(deck_b, "card-counterspell", 4)

    real_probe = assess_module.is_database_initialized
    probes: list[str] = []

    async def fail_first_probe(session: AsyncSession) -> bool:
        probes.append("probe")
        if len(probes) == 1:
            raise OperationalError("SELECT", {}, sqlite3.OperationalError("disk I/O error"))
        return await real_probe(session)

    monkeypatch.setattr(assess_module, "is_database_initialized", fail_first_probe)
    server = server_module.build_server(session_factory=seeded_card_db)
    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool(
            "compare_deck_power", {"deck_id_a": deck_a, "deck_id_b": deck_b}
        )

    assert result.isError is False
    assert result.structuredContent["status"] == "deck_a_failed"
    assert f"'{deck_a}'" in result.structuredContent["summary"]
    assert probes == ["probe", "probe"], "side B was assessed after side A's probe failed"


async def test_a_deck_deleted_between_the_check_and_the_write_is_deck_not_found(
    seeded_card_db, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The deck passes the pre-check, is gone at the insert: ``deck_not_found``, not ``exists``."""
    async with seeded_card_db() as session:
        deck_id = (await DeckRepository(session).create_deck(name="Doomed", format="standard")).id

    real_get_deck = DeckRepository.get_deck
    reads: list[str] = []

    async def vanish_after_first_read(self: DeckRepository, wanted: str) -> object:
        found = await real_get_deck(self, wanted)
        reads.append(wanted)
        if len(reads) == 1:
            # Another writer deletes the deck right after the tool's existence check.
            await self.session.execute(delete(DeckModel).where(DeckModel.id == wanted))
            await self.session.commit()
        return found

    monkeypatch.setattr(DeckRepository, "get_deck", vanish_after_first_read)
    server = server_module.build_server(session_factory=seeded_card_db)
    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool(
            "add_card_to_deck", {"deck_id": deck_id, "card_id": "card-lightning-bolt"}
        )

    assert result.isError is False
    assert result.structuredContent["status"] == "deck_not_found"
    assert reads == [deck_id, deck_id], "the integrity failure re-read the deck"


async def test_a_card_removed_between_resolution_and_the_write_is_card_not_found(
    seeded_card_db, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The card resolves, then an update's reconcile removes it before the insert: the card
    foreign key refuses the row, and the answer is ``card_not_found``, not ``exists``."""
    async with seeded_card_db() as session:
        deck_id = (await DeckRepository(session).create_deck(name="Kept", format="standard")).id

    real_get_by_id = CardRepository.get_by_id
    reads: list[str] = []

    async def vanish_after_first_read(self: CardRepository, wanted: str) -> object:
        found = await real_get_by_id(self, wanted)
        reads.append(wanted)
        if len(reads) == 1:
            await self.session.execute(delete(CardModel).where(CardModel.id == wanted))
            await self.session.commit()
        return found

    monkeypatch.setattr(CardRepository, "get_by_id", vanish_after_first_read)
    server = server_module.build_server(session_factory=seeded_card_db)
    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool(
            "add_card_to_deck", {"deck_id": deck_id, "card_id": "card-lightning-bolt"}
        )

    assert result.isError is False
    assert result.structuredContent["status"] == "card_not_found"
    assert "card-lightning-bolt" in result.structuredContent["message"]
    assert reads == ["card-lightning-bolt", "card-lightning-bolt"], "the card was re-read"


async def test_a_true_duplicate_add_still_answers_exists(seeded_card_db) -> None:
    """The twin of the vanished-deck row: the same integrity failure on a live deck is a dup."""
    async with seeded_card_db() as session:
        deck_id = (await DeckRepository(session).create_deck(name="Kept", format="standard")).id
    server = server_module.build_server(session_factory=seeded_card_db)
    args = {"deck_id": deck_id, "card_id": "card-lightning-bolt"}
    async with create_connected_server_and_client_session(server) as client:
        first = await client.call_tool("add_card_to_deck", args)
        second = await client.call_tool("add_card_to_deck", args)

    assert first.structuredContent["status"] == "ok"
    assert second.structuredContent["status"] == "exists"


@pytest.mark.parametrize(
    "failure",
    [
        pytest.param(ValueError("the bulk file is truncated at byte 4096"), id="bad-bulk-file"),
        pytest.param(
            ScryfallImportError("Scryfall import failed: the bulk file is truncated at byte 4096"),
            id="wrapped-bad-bulk-file",
        ),
    ],
)
async def test_a_non_network_import_failure_names_its_cause_without_a_network_hint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: Exception
) -> None:
    _point_initialize_database_at(monkeypatch, tmp_path / "init.db")

    async def importer(session: AsyncSession, *, bulk_type: str = "default_cards") -> None:
        raise failure

    result = await initialize_database(import_fn=importer)

    assert result.status == "error"
    assert "truncated at byte 4096" in result.message
    assert "connection" not in result.message.lower()
    assert "network" not in result.message.lower()


@pytest.mark.parametrize(
    "failure",
    [
        pytest.param(httpx.ConnectError("Name or service not known"), id="httpx"),
        pytest.param(ScryfallAPIError("Failed to download bulk data after 3 attempts"), id="api"),
    ],
)
async def test_a_network_import_failure_keeps_the_network_hint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: Exception
) -> None:
    """Raised the way the real importer raises it: wrapped in ``ScryfallImportError``."""
    _point_initialize_database_at(monkeypatch, tmp_path / "init.db")

    async def importer(session: AsyncSession, *, bulk_type: str = "default_cards") -> None:
        try:
            raise failure
        except Exception as exc:
            raise ScryfallImportError(f"Scryfall import failed: {exc}") from exc

    result = await initialize_database(import_fn=importer)

    assert result.status == "error"
    assert str(failure) in result.message
    assert "network" in result.message.lower()
    assert ".." not in result.message


async def test_a_database_error_cleaning_up_after_a_network_failure_blames_the_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A first-run download fails, then the cleanup's ``DELETE`` meets a lock: the raised error is
    the database's (the network failure is only its context), so the message says so."""
    _point_initialize_database_at(monkeypatch, tmp_path / "init.db")

    async def importer(session: AsyncSession, *, bulk_type: str = "default_cards") -> None:
        try:
            raise ScryfallAPIError("Failed to download bulk data after 3 attempts")
        except ScryfallAPIError as exc:
            raise ScryfallImportError(f"Scryfall import failed: {exc}") from exc

    async def locked_cleanup(session: AsyncSession) -> None:
        raise OperationalError(
            "DELETE FROM cards", {}, sqlite3.OperationalError("database is locked")
        )

    monkeypatch.setattr(initialize_database_module, "_clear_cards", locked_cleanup)

    result = await initialize_database(import_fn=importer)

    assert result.status == "error"
    assert "database is locked" in result.message
    assert "try again" in result.message
    assert "network" not in result.message.lower()
    assert "Failed to download" not in result.message
    assert "DELETE FROM" not in result.message
