"""Every deck-mutation tool emits ``deck_changed`` after its commit — and nothing else does (c7-2).

Two halves, one file.

**The behavioural half** drives the seven mutation tools — ``create_deck`` / ``update_deck`` /
``delete_deck`` / ``add_card_to_deck`` / ``set_card_quantity`` / ``import_decklist`` /
``remove_card_from_deck`` — through an in-process MCP client against a real file-backed database,
with a recording stub monkeypatched at **server.py's own import seam**
(``server._notify_deck_changed``). Patching there rather than on the leaf is the same reasoning
``test_companion_tool.py`` documents: the property under test is that *this* module reaches the
notifier through the name it imported. What is proven:

* every persisted write emits exactly once, carrying that deck's id — including a multi-line
  import, whose helper delegates per line and commits N times but must sound like one change;
* the emit happens **after the commit is visible**: the stub opens its own session from the same
  factory at notify time and sees the created row present / the deleted row gone — the "the view
  can never show something the database doesn't have" guarantee, made mechanical;
* every no-write outcome (``invalid`` / ``exists`` / ``unchanged`` / ``not_in_deck`` /
  ``*_not_found`` / ``ambiguous`` / ``error`` / ``database_not_initialized`` / an import landing
  zero lines) emits nothing;
* a failure ``PushOutcome`` leaves the tool's structured result byte-identical — the notification
  outcome never becomes a status, a field or a changed message;
* with no companion anywhere (``PLANESWALKER_DATA_DIR`` repointed at an empty directory, the
  **real** client on the path), a mutation still returns ``ok`` — the notifier degrades to a
  cheap ``app_not_running`` that the tool result never mentions;
* **and, since c7-7, the same promise against a real backend that really fails.** Every failure row
  above stubs either the notifier or the whole companion away, so until this story *no test anywhere
  had driven a mutation tool through a genuine HTTP failure*: a live loopback listener whose
  ``/health`` is valid — so the identity gate passes and the credential really leaves the process —
  and whose ``POST /agent/events`` answers ``500``, plus a wedged listener that accepts the
  connection and never answers, paying c7-1's real ~1 s bound. What those two rows add over a
  stubbed ``PushOutcome`` is the **non-vacuity that separates "swallowed" from "never attempted"**:
  the stub records the POST it received, so the emit is proven to have genuinely happened and
  genuinely failed, and the wedged row's elapsed time proves the budget was really paid rather than
  short-circuited.

**The enumeration half** is the guard the epic asked for: a future mutation tool cannot be
forgotten silently. It *derives* the set of mutating tools rather than trusting a hand-kept list —
sweeping every module under ``src/mcp_server/tools/`` (recursively, ``__init__.py`` included) for
references to the pinned deck-write repository methods (``_REPO_WRITE_METHODS``, imported from
``test_import_boundary.py`` where ``TestRepositorySurfaceIsPinned`` cross-checks it against the
live repositories), then closing over delegation in every call shape a repo module can legally
write: from-imported names (aliased, absolute or **relative** — ``deck_import``'s
``_add_card_to_deck`` is the absolute-alias case that demands resolution, and the project's import
convention permits the relative twin), same-module names, and attribute calls through
module-object bindings (``import ... as dm; dm.helper(...)``). The derived set, mapped through
``server.py``'s own imports to the wrappers that call them, must equal the five wired tool names;
a sixth deck-write surface fails here **by name** until it is wired. Sibling guards pin the
wiring's shape: server.py itself never touches a repository write method (the inline-mutation
bypass), only the five wrappers reference the emit path, no emit reference sits inside an ``async
with`` session block (the connection-held-across-HTTP hazard ``companion.py:181-186`` documents),
and every reference in ``server.py`` sits under a plain ``await`` — the local half of the
detached-task ban (``create_task``/``ensure_future``/``TaskGroup``/``gather``), which
``test_ws.py`` enforces for ``src/companion`` and this file enforces for the new sites without
extending that package sweep.

Despite living under ``tests/integration/``, these run in the ordinary ``-m "not integration"``
set: a directory is not a marker (AD-10).

**They boot no server process** — which is the property AD-10 actually constrains, and the reason
this file stays unmarked. Until c7-7 the stronger sentence was also true ("nothing here opens a
socket"), and c7-7's two real-HTTP-failure rows end that: they bind loopback listeners on ephemeral
ports *inside the test process* and really speak HTTP to them. That is not a widening of AD-10 and
needs no marker — ``tests/unit/companion/test_client.py`` has done exactly this for the whole
client suite since c1-8, in the ordinary set, for the ruled reason that the failures a client
absorbs live in the transport and a mocked one would prove only that a mock was called. What
remains true, and is what AD-10 is about, is that **no test outside
``tests/integration/companion/test_live_backend.py`` starts a companion**.
"""

import json
import sqlite3
import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from pathlib import Path

import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from sqlalchemy import event, select
from sqlalchemy.exc import DatabaseError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.companion.client import PUSH_OUTCOMES, PushOutcome
from src.companion.discovery import COMPANION_FILENAME, read_discovery
from src.data.database import create_engine, create_session_factory, init_database
from src.data.models.card import CardModel
from src.data.models.deck_card import DeckCardModel
from src.data.repositories.deck import DeckRepository
from src.data.schemas.deck import DeckDetail
from src.mcp_server import server as server_module
from src.mcp_server.server import build_server

# The loopback toolkit, imported rather than rebuilt (c7-7). `test_client.py` owns the only real
# HTTP stubs in the repo — an ephemeral-port server with per-verb answer scripts and a request log,
# and a bare listening socket that never answers — and rebuilding either here would be a second
# implementation of a thing whose whole value is that it is the real transport. The cross-test
# import precedent is this file's own: `_REPO_WRITE_METHODS` below comes from
# `test_import_boundary.py` on exactly the same terms.
from tests.unit.companion.test_client import (
    StubFleet,
    _Sockets,
    health_bytes,
    plant_discovery,
)

# ---------------------------------------------------------------------------------------------
# Repository layout — resolved from __file__, never from the runner's working directory.
# ---------------------------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _card(card_id: str, name: str) -> CardModel:
    return CardModel(
        id=card_id,
        name=name,
        printed_name=None,
        oracle_id=f"oracle-{card_id}",
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


@pytest.fixture
async def deck_db(tmp_path: Path) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    """A file-backed, initialised database seeded with two cards sharing the substring "bolt".

    Two rather than one so the ``ambiguous`` no-write path is drivable; file-backed rather than
    in-memory so the after-commit observer's *separate* session genuinely re-reads storage.
    """
    engine = create_engine(f"sqlite+aiosqlite:///{(tmp_path / 'cards.db').as_posix()}")
    await init_database(engine)
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        session.add(_card("card-bolt", "Lightning Bolt"))
        session.add(_card("card-thunderbolt", "Thunderbolt"))
        await session.commit()
    yield session_factory
    await engine.dispose()


@pytest.fixture
async def uninitialized_db(
    tmp_path: Path,
) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    """A schema that exists but holds no cards — ``database_not_initialized`` territory."""
    engine = create_engine(f"sqlite+aiosqlite:///{(tmp_path / 'empty.db').as_posix()}")
    await init_database(engine)
    yield create_session_factory(engine)
    await engine.dispose()


class _RecordingNotifier:
    """Stands in for c7-1's notifier at server.py's import seam, recording every emit.

    Recording the deck ids rather than a call count is deliberate: "nothing was emitted" and "the
    wrong deck was announced" are different failures, and only a recorded argument list tells them
    apart. The optional ``observer`` runs *at notify time* — the after-commit proofs use it to
    read the database through their own session while the emit is in flight.
    """

    def __init__(
        self,
        outcome: PushOutcome | None = None,
        observer: Callable[[str | None], Awaitable[object]] | None = None,
    ) -> None:
        if outcome is None:
            outcome = PushOutcome(outcome="displayed", clients=1)
        self.outcome = outcome
        self.observer = observer
        self.deck_ids: list[str | None] = []
        self.observations: list[object] = []

    async def __call__(self, deck_id: str | None = None, *, timeout: object = None) -> PushOutcome:
        self.deck_ids.append(deck_id)
        if self.observer is not None:
            self.observations.append(await self.observer(deck_id))
        return self.outcome


@pytest.fixture
def notifier(monkeypatch: pytest.MonkeyPatch):
    """Yield a factory installing a :class:`_RecordingNotifier` as ``server._notify_deck_changed``.

    The wrappers close over the module-level ``_emit_deck_changed``, which resolves
    ``_notify_deck_changed`` as a module global at call time — so patching the server module's
    binding intercepts every emit without touching the leaf client.
    """

    def install(
        outcome: PushOutcome | None = None,
        observer: Callable[[str | None], Awaitable[object]] | None = None,
    ) -> _RecordingNotifier:
        stub = _RecordingNotifier(outcome=outcome, observer=observer)
        monkeypatch.setattr(server_module, "_notify_deck_changed", stub)
        return stub

    return install


@pytest.mark.parametrize("name", [None, "Named copy"])
async def test_clone_empty_and_long_default(deck_db, notifier, name):
    stub = notifier()
    server = build_server(session_factory=deck_db)
    async with create_connected_server_and_client_session(server) as client:
        created = await client.call_tool("create_deck", {"name": "a" * 100})
        source_id = created.structuredContent["deck"]["id"]
        stub.deck_ids.clear()
        result = await client.call_tool("clone_deck", {"deck_id": source_id, "name": name})
        clone = result.structuredContent["deck"]
        assert result.structuredContent["status"] == "ok"
        assert clone["name"] == (name or "a" * 100 + " (copy)")
        assert clone["cards"] == []
        assert clone["tags"] == clone["color_identity"] == []
        assert clone["strategy"] is None
        assert stub.deck_ids == [clone["id"]]


@pytest.mark.parametrize(
    "name,status", [(" ", "invalid"), ("x" * 101, "invalid"), (None, "not_found")]
)
async def test_clone_invalid_or_missing_is_silent(deck_db, notifier, name, status):
    stub = notifier()
    async with create_connected_server_and_client_session(
        build_server(session_factory=deck_db)
    ) as client:
        result = await client.call_tool("clone_deck", {"deck_id": "missing", "name": name})
    assert result.structuredContent["status"] == status
    assert stub.deck_ids == []
    async with deck_db() as session:
        assert await DeckRepository(session).list_decks() == []


async def test_clone_uninitialized_is_silent(uninitialized_db, notifier):
    stub = notifier()
    async with create_connected_server_and_client_session(
        build_server(session_factory=uninitialized_db)
    ) as client:
        result = await client.call_tool("clone_deck", {"deck_id": "missing"})
    assert result.structuredContent["status"] == "database_not_initialized"
    assert stub.deck_ids == []


@pytest.mark.parametrize("postcommit", [False, True])
async def test_clone_database_fault_preserves_atomic_outcome(
    deck_db, notifier, monkeypatch, caplog, postcommit
):
    stub = notifier()
    async with deck_db() as session:
        repo = DeckRepository(session)
        source = await repo.create_deck("Source", "commander", strategy="Burn", tags=["burn"])
        await repo.add_card_to_deck(source.id, "card-bolt", 3, commander=True)
        await repo.add_card_to_deck(source.id, "card-bolt", 2, sideboard=True)
        before = await repo.get_deck_with_cards(source.id)

    original_commit = AsyncSession.commit
    staged = []
    staged_rows = []

    async def fail_commit(session):
        # Flush all staged cards, then fail before commit: rollback must remove real rows.
        await session.flush()
        staged.extend(await DeckRepository(session).list_decks())
        staged_rows.extend((await session.scalars(select(DeckCardModel))).all())
        raise DatabaseError("clone failure", {}, Exception("injected"))

    async def fail_refresh(self, model):
        raise DatabaseError("refresh failure", {}, Exception("injected"))

    if postcommit:
        monkeypatch.setattr(DeckRepository, "_reload_after_commit", fail_refresh)
    else:
        monkeypatch.setattr(AsyncSession, "commit", fail_commit)
    async with create_connected_server_and_client_session(
        build_server(session_factory=deck_db)
    ) as client:
        result = await client.call_tool("clone_deck", {"deck_id": source.id})
    monkeypatch.setattr(AsyncSession, "commit", original_commit)
    assert not result.isError
    assert result.structuredContent["status"] == ("ok" if postcommit else "error")
    async with deck_db() as session:
        repo = DeckRepository(session)
        assert await repo.get_deck_with_cards(source.id) == before
        decks = await repo.list_decks()
        assert len(decks) == (2 if postcommit else 1)
        if postcommit:
            clone = result.structuredContent["deck"]
            assert clone["mainboard_count"] == 3
            assert clone["sideboard_count"] == 2
            assert len(clone["cards"]) == 2
            assert stub.deck_ids == [clone["id"]]
            persisted = await repo.get_deck_with_cards(clone["id"])
            assert DeckDetail.from_deck(persisted).model_dump(mode="json") == clone
            expected = DeckDetail.from_deck(before).model_dump(mode="json")
            for field in ("format", "strategy", "tags", "color_identity", "cards"):
                assert clone[field] == expected[field]
        else:
            assert len(staged) == 2
            assert len(staged_rows) == 4
            assert stub.deck_ids == []
    assert any(record.args and "clone_deck" in record.getMessage() for record in caplog.records)


async def test_clone_readiness_database_error_is_structured_and_silent(
    deck_db, notifier, monkeypatch
):
    stub = notifier()

    async def fail_execute(self, *args, **kwargs):
        raise DatabaseError("readiness failure", {}, Exception("database is locked"))

    monkeypatch.setattr(AsyncSession, "execute", fail_execute)
    async with create_connected_server_and_client_session(
        build_server(session_factory=deck_db)
    ) as client:
        result = await client.call_tool("clone_deck", {"deck_id": "source"})
    assert not result.isError
    assert result.structuredContent["status"] == "error"
    assert stub.deck_ids == []


async def test_clone_source_snapshot_survives_concurrent_edit(deck_db, notifier):
    """A second connection commits after the source SELECT starts, before eager reads finish."""
    notifier()
    async with deck_db() as session:
        repo = DeckRepository(session)
        source = await repo.create_deck("Before", "commander", strategy="Before strategy")
        await repo.add_card_to_deck(source.id, "card-bolt", 3, commander=True)
        before = DeckDetail.from_deck(await repo.get_deck_with_cards(source.id)).model_dump(
            mode="json"
        )

    engine = deck_db.kw["bind"]
    edits = []

    def edit_after_source_select(connection, cursor, statement, parameters, context, executemany):
        if edits or "FROM decks" not in statement or source.id not in parameters:
            return
        edits.append(True)
        # The actual SQLite reader has started. WAL lets this independent writer
        # commit while that statement retains its original snapshot.
        with sqlite3.connect(engine.url.database) as writer:
            writer.execute(
                "UPDATE decks SET strategy = ? WHERE id = ?", ("After strategy", source.id)
            )
            writer.execute("UPDATE deck_cards SET quantity = 7 WHERE deck_id = ?", (source.id,))

    event.listen(engine.sync_engine, "after_cursor_execute", edit_after_source_select)
    try:
        async with create_connected_server_and_client_session(
            build_server(session_factory=deck_db)
        ) as client:
            result = await client.call_tool("clone_deck", {"deck_id": source.id})
    finally:
        event.remove(engine.sync_engine, "after_cursor_execute", edit_after_source_select)
    assert edits == [True]
    assert not result.isError
    assert result.structuredContent["status"] == "ok"
    clone = result.structuredContent["deck"]
    assert clone["strategy"] == before["strategy"]
    assert clone["cards"] == before["cards"]
    async with deck_db() as session:
        repo = DeckRepository(session)
        after = await repo.get_deck_with_cards(source.id)
        assert after.strategy == "After strategy"
        assert after.deck_cards[0].quantity == 7
        persisted = await repo.get_deck_with_cards(clone["id"])
        assert DeckDetail.from_deck(persisted).model_dump(mode="json") == clone


class TestEachPersistedWriteEmitsExactlyOnce:
    """The matrix's write rows: one emit, the right id, after the commit is visible."""

    async def test_create_deck_emits_the_new_id_and_the_row_is_already_visible(
        self, deck_db, notifier
    ):
        """The after-commit proof for creation: a *separate* session sees the row at notify time.

        An emit fired inside the transaction would announce a deck a refetching UI cannot load
        yet; the observer reading through its own connection is what makes "after the commit"
        a measured fact rather than a description of where the call sits in the source.
        """

        async def row_exists(deck_id: str | None) -> bool:
            assert deck_id is not None
            async with deck_db() as session:
                return await DeckRepository(session).get_deck(deck_id) is not None

        stub = notifier(observer=row_exists)
        server = build_server(session_factory=deck_db)
        async with create_connected_server_and_client_session(server) as client:
            created = await client.call_tool("create_deck", {"name": "Burn"})

        assert created.isError is False
        assert created.structuredContent is not None
        assert created.structuredContent["status"] == "ok"
        deck_id = created.structuredContent["deck"]["id"]
        assert stub.deck_ids == [deck_id], "exactly one emit, carrying the new deck's id"
        assert stub.observations == [True], "the created row was visible at notify time"

    async def test_delete_deck_emits_the_now_absent_id_after_the_row_is_gone(
        self, deck_db, notifier
    ):
        """Deletion emits too (the UI's refetch 404s and clears, by design) — after the row is
        gone, so a refetch racing the emit can never resurrect the deck."""

        async def row_exists(deck_id: str | None) -> bool:
            assert deck_id is not None
            async with deck_db() as session:
                return await DeckRepository(session).get_deck(deck_id) is not None

        stub = notifier(observer=row_exists)
        server = build_server(session_factory=deck_db)
        async with create_connected_server_and_client_session(server) as client:
            created = await client.call_tool("create_deck", {"name": "Doomed"})
            deck_id = created.structuredContent["deck"]["id"]
            deleted = await client.call_tool("delete_deck", {"deck_id": deck_id})

        assert deleted.structuredContent["status"] == "ok"
        assert stub.deck_ids == [deck_id, deck_id], "the create emitted, then the delete emitted"
        assert stub.observations == [True, False], (
            "at the delete's notify time the row was already gone"
        )

    async def test_add_card_emits_the_deck_id_once(self, deck_db, notifier):
        stub = notifier()
        server = build_server(session_factory=deck_db)
        async with create_connected_server_and_client_session(server) as client:
            created = await client.call_tool("create_deck", {"name": "Burn"})
            deck_id = created.structuredContent["deck"]["id"]
            added = await client.call_tool(
                "add_card_to_deck", {"deck_id": deck_id, "card_id": "card-bolt", "quantity": 4}
            )

        assert added.structuredContent["status"] == "ok"
        assert stub.deck_ids == [deck_id, deck_id], "one for the create, one for the add"

    async def test_remove_card_emits_the_deck_id_once(self, deck_db, notifier):
        stub = notifier()
        server = build_server(session_factory=deck_db)
        async with create_connected_server_and_client_session(server) as client:
            created = await client.call_tool("create_deck", {"name": "Burn"})
            deck_id = created.structuredContent["deck"]["id"]
            await client.call_tool("add_card_to_deck", {"deck_id": deck_id, "card_id": "card-bolt"})
            removed = await client.call_tool(
                "remove_card_from_deck", {"deck_id": deck_id, "card_id": "card-bolt"}
            )

        assert removed.structuredContent["status"] == "ok"
        assert stub.deck_ids == [deck_id] * 3, "create, add, remove — one emit each"

    async def test_update_deck_emits_the_deck_id_once_after_the_rename_is_visible(
        self, deck_db, notifier
    ):
        """The after-commit proof for a metadata write: the observer's own session already reads
        the new name at notify time."""

        async def name_now(deck_id: str | None) -> str | None:
            assert deck_id is not None
            async with deck_db() as session:
                deck = await DeckRepository(session).get_deck(deck_id)
            return None if deck is None else deck.name

        stub = notifier(observer=name_now)
        server = build_server(session_factory=deck_db)
        async with create_connected_server_and_client_session(server) as client:
            created = await client.call_tool("create_deck", {"name": "Burn"})
            deck_id = created.structuredContent["deck"]["id"]
            updated = await client.call_tool(
                "update_deck", {"deck_id": deck_id, "changes": {"name": "Sligh"}}
            )

        assert updated.structuredContent["status"] == "ok"
        assert stub.deck_ids == [deck_id, deck_id], "one for the create, one for the update"
        assert stub.observations == ["Burn", "Sligh"], "the rename was visible at notify time"

    @pytest.mark.parametrize("quantity", [2, 0])
    async def test_set_card_quantity_emits_the_deck_id_once(self, deck_db, notifier, quantity):
        """Both write branches — a real quantity and the ``0`` that routes to removal — emit once,
        after the new count is visible."""

        async def bolt_quantity(deck_id: str | None) -> int:
            assert deck_id is not None
            async with deck_db() as session:
                deck = await DeckRepository(session).get_deck_with_cards(deck_id)
            assert deck is not None
            return sum(e.quantity for e in deck.deck_cards if e.card_id == "card-bolt")

        stub = notifier(observer=bolt_quantity)
        server = build_server(session_factory=deck_db)
        async with create_connected_server_and_client_session(server) as client:
            created = await client.call_tool("create_deck", {"name": "Burn"})
            deck_id = created.structuredContent["deck"]["id"]
            await client.call_tool(
                "add_card_to_deck", {"deck_id": deck_id, "card_id": "card-bolt", "quantity": 4}
            )
            result = await client.call_tool(
                "set_card_quantity",
                {"deck_id": deck_id, "card_id": "card-bolt", "quantity": quantity},
            )

        assert result.structuredContent["status"] == "ok"
        assert stub.deck_ids == [deck_id] * 3, "create, add, set — one emit each"
        assert stub.observations[-1] == quantity, "the new count was visible at notify time"

    async def test_a_multi_line_import_emits_exactly_once(self, deck_db, notifier):
        """The helper delegates per line and commits N times; the glass hears one change.

        Per-line emits are precisely what wrapper-level wiring exists to prevent — this is the
        assertion that fails if the emit ever migrates into ``deck_import.py``'s loop.
        """
        stub = notifier()
        server = build_server(session_factory=deck_db)
        export = "Deck\n2 Lightning Bolt (TST) 1\n1 Thunderbolt (TST) 2\n1 Counterspell (TST) 3"
        async with create_connected_server_and_client_session(server) as client:
            created = await client.call_tool("create_deck", {"name": "Imported"})
            deck_id = created.structuredContent["deck"]["id"]
            imported = await client.call_tool(
                "import_decklist", {"deck_id": deck_id, "arena_export": export}
            )

        sc = imported.structuredContent
        assert sc["status"] == "partial", "two lines land, the unseeded Counterspell does not"
        assert sc["imported_lines"] == 2, "a real multi-line import, or the count proves nothing"
        assert stub.deck_ids == [deck_id, deck_id], (
            "the create emitted once and the whole import emitted once — never once per line"
        )


class TestANoWriteOutcomeEmitsNothing:
    """The matrix's zero-emit rows: every status that persisted nothing announces nothing."""

    async def test_every_drivable_no_write_status_is_silent(self, deck_db, notifier):
        """One server, every no-write status the tool surface can produce, zero new emits.

        Each case asserts its expected status first — a case that drifted into ``ok`` would be a
        write, and the final count would be measuring the wrong thing.
        """
        stub = notifier()
        server = build_server(session_factory=deck_db)
        async with create_connected_server_and_client_session(server) as client:
            created = await client.call_tool("create_deck", {"name": "Quiet"})
            deck_id = created.structuredContent["deck"]["id"]
            await client.call_tool(
                "add_card_to_deck", {"deck_id": deck_id, "card_id": "card-thunderbolt"}
            )
            baseline = len(stub.deck_ids)

            cases = [
                ("create_deck", {"name": "   "}, "invalid"),
                ("update_deck", {"deck_id": "no-such-deck", "changes": {"name": "x"}}, "not_found"),
                ("update_deck", {"deck_id": deck_id, "changes": {}}, "invalid"),
                ("update_deck", {"deck_id": deck_id, "changes": {"name": " "}}, "invalid"),
                ("delete_deck", {"deck_id": "no-such-deck"}, "not_found"),
                (
                    "add_card_to_deck",
                    {"deck_id": "no-such-deck", "card_id": "card-bolt"},
                    "deck_not_found",
                ),
                (
                    "add_card_to_deck",
                    {"deck_id": deck_id, "name": "No Such Card"},
                    "card_not_found",
                ),
                ("add_card_to_deck", {"deck_id": deck_id, "name": "bolt"}, "ambiguous"),
                ("add_card_to_deck", {"deck_id": deck_id}, "invalid"),
                (
                    "remove_card_from_deck",
                    {"deck_id": deck_id, "card_id": "card-bolt"},
                    "not_in_deck",
                ),
                (
                    "set_card_quantity",
                    {"deck_id": "no-such-deck", "card_id": "card-thunderbolt", "quantity": 1},
                    "deck_not_found",
                ),
                (
                    # Stored 1, asked for 1: the near-miss that must read as no write.
                    "set_card_quantity",
                    {"deck_id": deck_id, "card_id": "card-thunderbolt", "quantity": 1},
                    "unchanged",
                ),
                (
                    # A known card that is not in the board — quantity 0 included — is never a
                    # removal, so it is never an emit.
                    "set_card_quantity",
                    {"deck_id": deck_id, "card_id": "card-bolt", "quantity": 0},
                    "card_not_found",
                ),
                (
                    "set_card_quantity",
                    {"deck_id": deck_id, "name": "No Such Card", "quantity": 2},
                    "card_not_found",
                ),
                (
                    "set_card_quantity",
                    {"deck_id": deck_id, "name": "bolt", "quantity": 2},
                    "ambiguous",
                ),
                (
                    "set_card_quantity",
                    {"deck_id": deck_id, "card_id": "card-thunderbolt", "quantity": -1},
                    "invalid",
                ),
                ("import_decklist", {"deck_id": deck_id, "arena_export": "   "}, "invalid"),
                (
                    # Every line parses, no line lands: `partial` with imported_lines == 0 — the
                    # one import status the emit predicate must read past the status to refuse.
                    "import_decklist",
                    {"deck_id": deck_id, "arena_export": "Deck\n1 No Such Card (TST) 9"},
                    "partial",
                ),
            ]
            for tool, args, expected in cases:
                result = await client.call_tool(tool, args)
                assert result.structuredContent["status"] == expected, (tool, args)
                if tool == "import_decklist" and expected == "partial":
                    assert result.structuredContent["imported_lines"] == 0

        assert len(stub.deck_ids) == baseline, (
            f"a no-write outcome emitted: {stub.deck_ids[baseline:]}"
        )

    async def test_an_exists_answer_is_not_a_write(self, deck_db, notifier):
        """The near-miss case: the same call that just emitted, repeated, must not emit again."""
        stub = notifier()
        server = build_server(session_factory=deck_db)
        async with create_connected_server_and_client_session(server) as client:
            created = await client.call_tool("create_deck", {"name": "Burn"})
            deck_id = created.structuredContent["deck"]["id"]
            first = await client.call_tool(
                "add_card_to_deck", {"deck_id": deck_id, "card_id": "card-bolt"}
            )
            emits_after_first = len(stub.deck_ids)
            second = await client.call_tool(
                "add_card_to_deck", {"deck_id": deck_id, "card_id": "card-bolt"}
            )

        assert first.structuredContent["status"] == "ok"
        assert second.structuredContent["status"] == "exists"
        assert emits_after_first == 2, "the non-vacuity twin: the first add really did emit"
        assert len(stub.deck_ids) == 2, "the exists answer added nothing and announced nothing"

    @pytest.mark.parametrize(
        ("tool", "args"),
        [
            ("create_deck", {"name": "Too Early"}),
            ("update_deck", {"deck_id": "any", "changes": {"name": "Too Early"}}),
            ("set_card_quantity", {"deck_id": "any", "card_id": "card-bolt", "quantity": 2}),
        ],
    )
    async def test_an_uninitialized_database_is_silent(
        self, uninitialized_db, notifier, tool, args
    ):
        stub = notifier()
        server = build_server(session_factory=uninitialized_db)
        async with create_connected_server_and_client_session(server) as client:
            result = await client.call_tool(tool, args)

        assert result.structuredContent["status"] == "database_not_initialized"
        assert stub.deck_ids == []

    async def test_a_database_error_mid_write_is_silent(self, deck_db, notifier, monkeypatch):
        """``status="error"`` means nothing persisted — the rolled-back mutation emits nothing."""
        stub = notifier()
        server = build_server(session_factory=deck_db)
        async with create_connected_server_and_client_session(server) as client:
            created = await client.call_tool("create_deck", {"name": "Sturdy"})
            deck_id = created.structuredContent["deck"]["id"]

            async def boom(self, deck_id: str) -> bool:
                raise DatabaseError("delete", {}, Exception("disk I/O error"))

            monkeypatch.setattr(DeckRepository, "delete_deck", boom)
            result = await client.call_tool("delete_deck", {"deck_id": deck_id})

        assert result.structuredContent["status"] == "error"
        assert stub.deck_ids == [deck_id], "only the create emitted; the failed delete was silent"

    @pytest.mark.parametrize(
        ("tool", "args", "repo_method"),
        [
            ("update_deck", {"changes": {"name": "Renamed"}}, "update_deck"),
            ("set_card_quantity", {"card_id": "card-bolt", "quantity": 2}, "update_card_quantity"),
            ("set_card_quantity", {"card_id": "card-bolt", "quantity": 0}, "remove_card_from_deck"),
        ],
    )
    async def test_a_database_error_in_the_new_tools_is_silent_and_leaves_the_deck_alone(
        self, deck_db, notifier, monkeypatch, tool, args, repo_method
    ):
        """Each write branch of the two quick-wins tools: a ``DatabaseError`` from the repository
        method it delegates to is ``status="error"``, nothing is emitted, and the deck reads back
        through a separate session exactly as it was. The patched method counts its calls, so a
        misspelt ``repo_method`` cannot pass by never being reached."""
        calls: list[str] = []

        async def boom(self, *a, **kw):
            calls.append(repo_method)
            raise DatabaseError(repo_method, {}, Exception("disk I/O error"))

        result, emitted, deck = await self._drive_after_patching(
            deck_db, notifier, monkeypatch, tool, args, repo_method, boom
        )

        assert calls == [repo_method], "the planted failure was really reached"
        assert result.isError is False
        assert result.structuredContent["status"] == "error"
        assert emitted == [], "the failed write was silent"
        assert deck.name == "Sturdy"
        assert [(e.card_id, e.quantity) for e in deck.deck_cards] == [("card-bolt", 4)]

    async def test_a_committed_update_deck_whose_reload_fails_still_answers_ok_and_emits(
        self, deck_db, notifier, monkeypatch
    ):
        """The write landed, then reloading the deck for the response raised: that is a reporting
        failure, not a failed mutation. The status stays ``ok`` (with ``deck`` absent and a message
        pointing at ``load_deck``), ``deck_changed`` is emitted once, and the rename is on disk —
        so a caller is never told to retry a write that already succeeded."""
        calls: list[str] = []
        real_reload = DeckRepository.get_deck_with_cards

        async def reload_boom(self, *a, **kw):
            # Fail only the tool's own post-commit reload; the observing read that follows in
            # ``_drive_after_patching`` goes through the real method.
            if not calls:
                calls.append("get_deck_with_cards")
                raise DatabaseError("get_deck_with_cards", {}, Exception("disk I/O error"))
            return await real_reload(self, *a, **kw)

        result, emitted, deck = await self._drive_after_patching(
            deck_db,
            notifier,
            monkeypatch,
            "update_deck",
            {"changes": {"name": "Renamed"}},
            "get_deck_with_cards",
            reload_boom,
        )

        assert calls == ["get_deck_with_cards"]
        assert result.isError is False
        assert result.structuredContent["status"] == "ok"
        assert result.structuredContent["deck"] is None
        assert "load_deck" in result.structuredContent["message"]
        assert len(emitted) == 1, "a committed write announces itself even if the reload failed"
        assert deck.name == "Renamed"

    @pytest.mark.parametrize(
        ("tool", "args", "expect_rows"),
        [
            ("set_card_quantity", {"card_id": "card-bolt", "quantity": 2}, [("card-bolt", 2)]),
            ("set_card_quantity", {"card_id": "card-bolt", "quantity": 0}, []),
            ("update_deck", {"changes": {"name": "Renamed"}}, [("card-bolt", 4)]),
        ],
    )
    async def test_a_failed_repository_reread_after_the_commit_still_answers_ok_and_emits(
        self, deck_db, notifier, monkeypatch, tool, args, expect_rows
    ):
        """The repository's own post-commit re-read (``_reload_after_commit``) raises once, after
        the write has landed. The tool still answers ``ok`` with the written state, emits exactly
        once, and a separate session reads the write back — the quantity, the removal and the
        rename each through their own repository branch."""
        calls: list[str] = []
        real_reload = DeckRepository._reload_after_commit

        async def reload_boom(self, *a, **kw):
            if not calls:
                calls.append("_reload_after_commit")
                raise DatabaseError("refresh", {}, Exception("disk I/O error"))
            return await real_reload(self, *a, **kw)

        result, emitted, deck = await self._drive_after_patching(
            deck_db, notifier, monkeypatch, tool, args, "_reload_after_commit", reload_boom
        )

        assert calls == ["_reload_after_commit"], "the planted re-read failure really fired"
        assert result.isError is False
        assert result.structuredContent["status"] == "ok"
        assert len(emitted) == 1, "a committed write announces itself once, re-read or not"
        assert [(e.card_id, e.quantity) for e in deck.deck_cards] == expect_rows
        if tool == "update_deck":
            assert result.structuredContent["deck"]["name"] == "Renamed"
            assert deck.name == "Renamed"
        else:
            assert result.structuredContent["quantity"] == args["quantity"]

    @pytest.mark.parametrize(
        ("args", "repo_method", "answer"),
        [
            ({"card_id": "card-bolt", "quantity": 2}, "update_card_quantity", None),
            ({"card_id": "card-bolt", "quantity": 0}, "remove_card_from_deck", False),
        ],
    )
    async def test_a_row_that_vanishes_after_the_pre_read_is_card_not_found_and_silent(
        self, deck_db, notifier, monkeypatch, args, repo_method, answer
    ):
        """The race the helper guards: the pre-read saw the row, the write found nothing (the
        repository answers ``None`` / ``False``). That is ``card_not_found``, not ``ok``, so it
        emits nothing — and the deck is untouched."""
        calls: list[str] = []

        async def vanished(self, *a, **kw):
            calls.append(repo_method)
            return answer

        result, emitted, deck = await self._drive_after_patching(
            deck_db, notifier, monkeypatch, "set_card_quantity", args, repo_method, vanished
        )

        assert calls == [repo_method]
        assert result.isError is False
        assert result.structuredContent["status"] == "card_not_found"
        assert emitted == [], "a write that landed nothing announces nothing"
        assert [(e.card_id, e.quantity) for e in deck.deck_cards] == [("card-bolt", 4)]

    @staticmethod
    async def _drive_after_patching(
        deck_db, notifier, monkeypatch, tool, args, repo_method, replacement
    ):
        """Seed a deck with 4 Bolt, patch ``DeckRepository.<repo_method>`` with *replacement*,
        call *tool*, and return ``(result, emits after the patch, the deck re-read separately)``."""
        stub = notifier()
        server = build_server(session_factory=deck_db)
        async with create_connected_server_and_client_session(server) as client:
            created = await client.call_tool("create_deck", {"name": "Sturdy"})
            deck_id = created.structuredContent["deck"]["id"]
            await client.call_tool(
                "add_card_to_deck", {"deck_id": deck_id, "card_id": "card-bolt", "quantity": 4}
            )
            emits_before = len(stub.deck_ids)

            monkeypatch.setattr(DeckRepository, repo_method, replacement)
            result = await client.call_tool(tool, {"deck_id": deck_id, **args})

        async with deck_db() as observing:
            deck = await DeckRepository(observing).get_deck_with_cards(deck_id)
        assert deck is not None
        return result, stub.deck_ids[emits_before:], deck


class TestANotifyOutcomeNeverTouchesTheResult:
    """The matrix's failure row: the emit is an aside, never a participant in the result."""

    @pytest.mark.parametrize("outcome", [o for o in PUSH_OUTCOMES if o != "displayed"])
    async def test_the_structured_result_is_identical_across_outcome_tokens(
        self, deck_db, notifier, outcome
    ):
        """The same mutation under a success outcome and under *outcome* answers byte-identically.

        Byte-identical, not merely both ``ok``: a wrapper that leaked the outcome into a message,
        a count or a new field would still pass a status-only assertion. Nothing raises either —
        the real client guarantees that; here the guarantee is that the wrapper adds no seam
        where an outcome could become an error.
        """
        stub = notifier(PushOutcome(outcome="displayed", clients=1))
        server = build_server(session_factory=deck_db)
        async with create_connected_server_and_client_session(server) as client:
            created = await client.call_tool("create_deck", {"name": "Steady"})
            deck_id = created.structuredContent["deck"]["id"]
            baseline = await client.call_tool(
                "add_card_to_deck", {"deck_id": deck_id, "card_id": "card-bolt"}
            )
            assert baseline.structuredContent["status"] == "ok"

            await client.call_tool(
                "remove_card_from_deck", {"deck_id": deck_id, "card_id": "card-bolt"}
            )
            stub.outcome = PushOutcome(outcome=outcome)
            again = await client.call_tool(
                "add_card_to_deck", {"deck_id": deck_id, "card_id": "card-bolt"}
            )

        assert again.isError is False
        assert again.structuredContent == baseline.structuredContent, (
            f"a {outcome!r} notify outcome altered the mutation's own result"
        )


class TestAClosedCompanionCostsTheMutationNothing:
    """The degradation row, with the real client on the path and no companion anywhere."""

    async def test_a_mutation_still_persists_and_reports_ok(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, deck_db
    ):
        """No stub: the emit reaches the real ``notify_deck_changed``, which finds no discovery
        file and returns ``app_not_running`` cheaply. The tool result neither fails nor mentions
        the companion — SC-3's promise carried into the mutation tools."""
        data_dir = tmp_path / "no-companion-here"
        data_dir.mkdir()
        monkeypatch.setenv("PLANESWALKER_DATA_DIR", str(data_dir))
        assert not (data_dir / COMPANION_FILENAME).exists()
        assert read_discovery() is None, (
            "something published a discovery record into the isolated data dir — this would be "
            "measuring a live companion instead of a closed one"
        )

        server = build_server(session_factory=deck_db)
        async with create_connected_server_and_client_session(server) as client:
            created = await client.call_tool("create_deck", {"name": "Offline"})
            assert created.isError is False
            assert created.structuredContent["status"] == "ok"
            deck_id = created.structuredContent["deck"]["id"]

            added = await client.call_tool(
                "add_card_to_deck", {"deck_id": deck_id, "card_id": "card-bolt"}
            )

        assert added.isError is False
        sc = added.structuredContent
        assert sc["status"] == "ok"
        assert "companion" not in sc["message"].lower(), (
            "the mutation's own message must not surface the notification's fate"
        )


@pytest.fixture
def stub_server():
    """Yield :meth:`StubFleet.start` and tear down every loopback stub it handed out.

    A four-line fixture over an imported helper, exactly as ``test_client.py`` and
    ``test_server.py`` each keep their own: the fixture cannot simply be imported, because a
    module-level ``stub_server`` binding and a test parameter of the same name are a redefinition
    (ruff F811). One implementation, one more fixture.
    """
    fleet = StubFleet()
    yield fleet.start
    fleet.close_all()


@pytest.fixture
def sockets():
    """Yield the raw-socket helper (a port that accepts and never answers) and close what it opens.

    A leaked listener on Windows surfaces as a failure in some *later* test, which is why teardown
    is the fixture's job rather than each test's.
    """
    helper = _Sockets()
    yield helper
    helper.close_all()


async def _add_twice_across_a_planted_failure(session, plant) -> tuple[object, object, str, float]:
    """Add the same card to the same deck twice: once with no companion, once against *plant*'s.

    The comparison this file's byte-identical claim needs, made on **one** deck rather than two:
    ``DeckCardResult`` carries the deck id, so two different decks would differ for a reason that
    has nothing to do with the notifier. The card is added, removed, and added again — the removal
    is what makes the second add a real write rather than an ``exists``.

    The first add runs while ``read_discovery()`` finds nothing, so it is the **no-companion
    baseline** the story's AC names. *Then* the discovery record is planted, so the second add is
    the only call that reaches a backend at all.

    Args:
        session: A connected in-process MCP client session.
        plant: Called between the two adds; writes the discovery record pointing at the failure.

    Returns:
        ``(baseline_result, failing_result, deck_id, failing_elapsed_seconds)``.
    """
    created = await session.call_tool("create_deck", {"name": "Half A Loop"})
    assert created.structuredContent["status"] == "ok"
    deck_id = created.structuredContent["deck"]["id"]

    baseline = await session.call_tool(
        "add_card_to_deck", {"deck_id": deck_id, "card_id": "card-bolt"}
    )
    assert baseline.structuredContent["status"] == "ok", "the baseline leg must be a real write"
    removed = await session.call_tool(
        "remove_card_from_deck", {"deck_id": deck_id, "card_id": "card-bolt"}
    )
    assert removed.structuredContent["status"] == "ok"

    plant()
    started = time.monotonic()
    failing = await session.call_tool(
        "add_card_to_deck", {"deck_id": deck_id, "card_id": "card-bolt"}
    )
    return baseline, failing, deck_id, time.monotonic() - started


class TestARealHttpFailureCostsTheMutationNothing:
    """The failure rows with a **real backend on the wire**, not a stubbed outcome (c7-7, AC 3).

    Every other failure row in this file replaces something: ``TestANotifyOutcomeNeverTouchesThe
    Result`` hands the wrapper a fabricated :class:`PushOutcome`, and
    ``TestAClosedCompanionCostsTheMutationNothing`` deletes the companion entirely. Both are worth
    having and neither can fail the way production fails — with the identity gate **passed**, the
    credential **sent**, and the backend answering something the client has to absorb. These two
    rows are that case: a live loopback listener, a real POST over a real socket, and a mutation
    that must come back byte-identical to the baseline anyway.
    """

    @pytest.fixture(autouse=True)
    def isolated_data_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        """Point the real client at an empty data dir, and prove it starts empty.

        The proof matters as much as the isolation: a discovery record left by a companion the
        developer actually has running would make the baseline leg talk to it, and both rows would
        then be measuring a live backend instead of the failure they name.
        """
        data_dir = tmp_path / "companion-data"
        data_dir.mkdir()
        monkeypatch.setenv("PLANESWALKER_DATA_DIR", str(data_dir))
        assert not (data_dir / COMPANION_FILENAME).exists()
        assert read_discovery() is None, (
            "something published a discovery record into the isolated data dir — the baseline leg "
            "would be talking to a real companion"
        )
        return data_dir

    async def test_a_real_500_after_the_commit_leaves_the_result_byte_identical(
        self, deck_db, stub_server
    ):
        """The port accepts the POST and answers 500 — and the tool never notices.

        The planted record names a live stub, so the client genuinely sends the token in its one
        request, and it is that request the backend fails. That is the whole point: a failure
        planted *before* the send (no file, a refused port) would be a second spelling of
        ``app_not_running`` and would never exercise the swallow at all.
        """
        stub = stub_server(
            status=200,
            body=health_bytes("live-but-broken"),
            post_script=[(500, b'{"detail": "the backend fell over"}')],
        )

        server = build_server(session_factory=deck_db)
        async with create_connected_server_and_client_session(server) as session:
            baseline, failing, deck_id, _ = await _add_twice_across_a_planted_failure(
                session,
                lambda: plant_discovery(port=stub.port, instance_id="live-but-broken"),
            )

        # Nothing raised (we are past the call), nothing failed, and nothing about the answer moved.
        assert failing.isError is False
        assert failing.structuredContent == baseline.structuredContent, (
            "a real 500 from a real backend altered the mutation's own structured result"
        )
        assert "companion" not in failing.structuredContent["message"].lower()

        # THE MUTATION PERSISTED — read back through a *separate* session, so this is storage
        # answering rather than the result object repeating itself.
        async with deck_db() as observing:
            deck = await DeckRepository(observing).get_deck_with_cards(deck_id)
        assert deck is not None
        assert [entry.card_id for entry in deck.deck_cards] == ["card-bolt"]

        # THE NON-VACUITY: the POST was really sent. Without this the row is indistinguishable from
        # one where the emit never happened — which is the failure mode a swallow makes silent.
        assert len(stub.posts) == 1, (
            f"expected exactly one POST (a 500 is terminal — FR-12's retry is spent on a refused "
            f"CREDENTIAL alone), got {len(stub.posts)}"
        )
        assert stub.posts[0].request_line.startswith("POST /agent/events "), stub.posts[0]
        body = json.loads(stub.posts[0].body)
        assert body["kind"] == "deck_changed"
        assert body["payload"]["deck_id"] == deck_id, (
            "the emit that failed was still the right one — a swallowed wrong event would look "
            "identical from the tool's side"
        )
        # …and it was the only request: one round trip per notify, no ``/health`` probe in front.
        assert [r.request_line.split(" ", 1)[0] for r in stub.requests] == ["POST"]

    async def test_a_wedged_backend_pays_the_bound_and_the_mutation_still_returns_ok(
        self, deck_db, sockets
    ):
        """A listener that answers and then never finishes: the mutation waits ~1 s, then shrugs.

        This is AD-9's ~1 s bound as a **measured** fact rather than a constant read out of the
        source, and it is the one row in this file whose evidence is an elapsed time.

        ⚠️ **The socket is ``drip()``, and ``silent()`` was tried first and rejected — measured.**
        A silent listener (accepts into the kernel's backlog, never calls ``accept()``) is the
        obvious spelling of "wedged", and it cannot tell the notify budget from the *absence* of
        one: ``PROBE_TIMEOUT``'s own ``read=2.0`` ends that exchange, so dropping
        ``_NOTIFY_TOTAL_SECONDS`` moves the call from ~1 s to ~2 s and any ceiling loose enough not
        to flake is loose enough to miss it. The firing probe for this row proved exactly that —
        the planted regression stayed green. ``drip()`` answers headers and then feeds body bytes
        every 20 ms forever, so **no per-read deadline can ever fire** and only a whole-operation
        deadline can end it: ~1 s with the notify budget, ~10 s
        (``client._PUSH_TOTAL_SECONDS``) without. A ten-fold separation instead of a two-fold
        one, which is what makes the ceiling below both safe and meaningful.
        """
        port = sockets.drip()

        server = build_server(session_factory=deck_db)
        async with create_connected_server_and_client_session(server) as session:
            baseline, failing, deck_id, elapsed = await _add_twice_across_a_planted_failure(
                session, lambda: plant_discovery(port=port, instance_id="wedged")
            )

        assert failing.isError is False
        assert failing.structuredContent == baseline.structuredContent, (
            "a wedged backend altered the mutation's own structured result"
        )

        async with deck_db() as observing:
            deck = await DeckRepository(observing).get_deck_with_cards(deck_id)
        assert deck is not None
        assert [entry.card_id for entry in deck.deck_cards] == ["card-bolt"]

        # THE BOUND, FROM BOTH SIDES, and the two numbers tell three outcomes apart:
        #   * below the floor -> the client never really dialled (a short-circuit, and the row
        #     would be proving nothing about the swallow);
        #   * inside the window -> `_NOTIFY_TOTAL_SECONDS` (1.0 s) ended it, which is the claim;
        #   * above the ceiling -> the notify budget was bypassed and `_PUSH_TOTAL_SECONDS`
        #     (10.0 s) is what stopped the wait — the exact regression AD-9 forbids, since a
        #     mutation tool's answer is held up by this await.
        # 3 s rather than 1.1 s so a loaded CI runner's scheduling jitter can never flake the row,
        # and still seven full seconds clear of the 10 s regression.
        assert elapsed >= 0.9, (
            f"the mutation returned in {elapsed:.3f}s — too fast to have dialled the wedged port "
            "at all, so this row proves nothing about the swallow"
        )
        assert elapsed < 3.0, (
            f"the mutation took {elapsed:.3f}s; AD-9's ~1 s notify bound did not apply and the "
            "10 s push deadline is what ended it"
        )
