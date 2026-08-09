"""Integration tests for the ``companion_set_active_deck`` helper (c6-2, FR-07, AD-16).

Drives :func:`src.mcp_server.tools.companion.set_active_deck` against a **real seeded session** and
a **stubbed client verb**. That split is Q4's ruling and it is the whole point of the file: every
wire behaviour — the retry, the token, the receipt parsing, the five outcome tokens — is proven in
``tests/unit/companion/test_client.py`` against real loopback sockets, and re-proving any of it here
through a second harness would duplicate the cost and halve the meaning. What belongs here is what
only this layer can be wrong about:

* the database read happens **first**, and a missing deck means the companion is **never contacted**
  (AC 3's "without contacting the backend", made mechanical — the stub records its calls, and the
  assertion is that the list is empty);
* the request handed to the client is built from the deck the database returned;
* every one of the client's five tokens maps 1:1 onto a tool ``status``, with the count passed
  through;
* the two database-layer statuses this package's convention requires; and
* the result stays compact (CM-1).

The stub is monkeypatched at **this module's** import boundary —
``companion._client_set_active_deck`` — rather than on the leaf. Patching the leaf would also
silence ``push_event``'s neighbours and would not prove that *this* module reaches the client
through the name it imported.

Despite living under ``tests/integration/``, these run in the ordinary ``-m "not integration"`` set:
a directory is not a marker (AD-10), and nothing here touches a socket.
"""

from pathlib import Path

import pytest

from src.companion.client import PushOutcome
from src.companion.contracts import ActiveDeckRequest
from src.data.database import create_engine, create_session_factory, init_database
from src.data.models.card import CardModel
from src.mcp_server.tools import companion
from src.mcp_server.tools.companion import set_active_deck
from src.mcp_server.tools.deck_management import create_deck
from src.mcp_server.tools.messages import DATABASE_NOT_INITIALIZED_MESSAGE

_MISSING_DECK = "deck-that-is-definitely-not-in-any-database-00000"


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
async def session(tmp_path: Path):
    """File-backed engine + a shared session seeded with one card (no decks)."""
    db_path = tmp_path / "companion.db"
    engine = create_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    await init_database(engine)
    session_factory = create_session_factory(engine)
    async with session_factory() as db_session:
        db_session.add(_card("card-bolt", "Lightning Bolt"))
        await db_session.commit()
        yield db_session
    await engine.dispose()


class _ClientStub:
    """Stands in for the leaf verb, recording every request it was handed.

    Recording the *requests* rather than a call count is deliberate: "the companion was not
    contacted" and "the companion was contacted with the wrong deck" are different failures, and
    only a recorded argument list distinguishes them.
    """

    def __init__(self, outcome: PushOutcome) -> None:
        self.outcome = outcome
        self.calls: list[ActiveDeckRequest] = []

    async def __call__(self, request: ActiveDeckRequest, **kwargs: object) -> PushOutcome:
        self.calls.append(request)
        return self.outcome


@pytest.fixture
def client_stub(monkeypatch):
    """Yield a factory that installs a :class:`_ClientStub` answering a chosen outcome."""

    def install(outcome: PushOutcome) -> _ClientStub:
        stub = _ClientStub(outcome)
        monkeypatch.setattr(companion, "_client_set_active_deck", stub)
        return stub

    return install


class TestAnExistingDeckIsDelegated:
    """AC 2: the deck is looked up, then the companion is told about it."""

    async def test_the_request_carries_the_id_the_database_returned(self, session, client_stub):
        """Not the caller's string — the deck's own id, read back from the row that matched.

        The two are equal today, and the assertion is written against ``deck.id`` on purpose: a
        helper that echoed its argument straight into the request would pass this, and would keep
        passing the day the repository normalises ids. What it pins is the *source*.
        """
        stub = client_stub(PushOutcome(outcome="displayed", clients=1))
        created = await create_deck(session, name="Burn")

        result = await set_active_deck(session, deck_id=created.deck.id)

        assert [request.deck_id for request in stub.calls] == [created.deck.id]
        assert isinstance(stub.calls[0], ActiveDeckRequest), (
            "the leaf takes a concrete, already-valid instance and re-validates nothing (c6-1 Q5)"
        )
        assert result.status == "displayed"

    async def test_the_result_names_the_deck_so_the_agent_can_confirm_it(
        self, session, client_stub
    ):
        client_stub(PushOutcome(outcome="displayed", clients=2))
        created = await create_deck(session, name="Mono-Red Burn")

        result = await set_active_deck(session, deck_id=created.deck.id)

        assert result.deck_id == created.deck.id
        assert result.deck_name == "Mono-Red Burn"
        assert result.clients == 2
        assert "Mono-Red Burn" in result.message

    async def test_one_open_tab_is_described_in_the_singular(self, session, client_stub):
        """A tiny thing the agent reads aloud; "in 1 tabs" is the kind of seam nothing else pins."""
        client_stub(PushOutcome(outcome="displayed", clients=1))
        created = await create_deck(session, name="Burn")

        result = await set_active_deck(session, deck_id=created.deck.id)

        assert "1 tab." in result.message
        assert "tabs" not in result.message

    @pytest.mark.parametrize(
        ("outcome", "clients"),
        [
            pytest.param("displayed", 3, id="displayed"),
            pytest.param("no_clients_connected", 0, id="no-clients"),
            pytest.param("app_not_running", None, id="app-not-running"),
            pytest.param("payload_rejected", None, id="payload-rejected"),
            pytest.param("backend_error", None, id="backend-error"),
        ],
    )
    async def test_every_client_token_maps_onto_a_status_of_the_same_name(
        self, session, client_stub, outcome, clients
    ):
        """AD-8's set, 1:1, with the count carried through and never invented.

        All five in one parametrization because the mapping is the contract: a tool that translated
        four of them and swallowed the fifth would look correct in any single-row test.
        """
        client_stub(PushOutcome(outcome=outcome, clients=clients))
        created = await create_deck(session, name="Burn")

        result = await set_active_deck(session, deck_id=created.deck.id)

        assert result.status == outcome
        assert result.clients == clients
        assert result.deck_id == created.deck.id
        assert result.message, "every status carries a sentence a human can read"

    async def test_no_status_leaks_a_raw_outcome_token_into_the_message(self, session, client_stub):
        """The token is for a caller to switch on; the sentence is for a person to read."""
        client_stub(PushOutcome(outcome="app_not_running"))
        created = await create_deck(session, name="Burn")

        result = await set_active_deck(session, deck_id=created.deck.id)

        assert "app_not_running" not in result.message
        assert "companion" in result.message.lower()


class TestAMissingDeckNeverReachesTheCompanion:
    """AC 3: the existence check is this layer's, and it short-circuits the network."""

    async def test_a_missing_deck_is_deck_not_found_and_the_client_is_never_called(
        self, session, client_stub
    ):
        """The mechanism assertion for AC 3, and the one the planted red was aimed at.

        The stub is armed with a **success**, so a helper that called the client anyway would
        return ``displayed`` and the status assertion alone would catch it — but a helper that
        called the client and *then* returned ``deck_not_found`` would pass a status-only test
        while having already told the companion to display a deck that does not exist. The empty
        call list is what makes "without contacting the backend" a fact rather than a description.
        """
        stub = client_stub(PushOutcome(outcome="displayed", clients=1))

        result = await set_active_deck(session, deck_id=_MISSING_DECK)

        assert result.status == "deck_not_found"
        assert stub.calls == [], "AD-16: a deck that does not exist is answered without any HTTP"
        assert result.deck_id == _MISSING_DECK
        assert result.deck_name is None
        assert result.clients is None

    async def test_it_is_not_passing_because_every_deck_looks_missing(self, session, client_stub):
        """The non-vacuity pairing: the same session, a real deck, and a call that does happen."""
        stub = client_stub(PushOutcome(outcome="displayed", clients=1))
        created = await create_deck(session, name="Burn")

        missing = await set_active_deck(session, deck_id=_MISSING_DECK)
        found = await set_active_deck(session, deck_id=created.deck.id)

        assert missing.status == "deck_not_found"
        assert found.status == "displayed"
        assert len(stub.calls) == 1, "exactly the found one reached the companion"

    async def test_the_message_points_at_the_agent_s_recovery_move(self, session, client_stub):
        client_stub(PushOutcome(outcome="displayed", clients=1))

        result = await set_active_deck(session, deck_id=_MISSING_DECK)

        assert "list_decks" in result.message


class TestTheDatabaseLayerStatuses:
    """The convention every tool in this package carries, and never raising past it."""

    async def test_an_un_imported_database_is_guarded_before_anything_else(
        self, tmp_path: Path, client_stub
    ):
        """The shared message, and no companion call: an empty database is not a missing deck."""
        stub = client_stub(PushOutcome(outcome="displayed", clients=1))
        engine = create_engine(f"sqlite+aiosqlite:///{(tmp_path / 'empty.db').as_posix()}")
        await init_database(engine)
        session_factory = create_session_factory(engine)
        async with session_factory() as empty_session:
            result = await set_active_deck(empty_session, deck_id="deck-anything")
        await engine.dispose()

        assert result.status == "database_not_initialized"
        assert result.message == DATABASE_NOT_INITIALIZED_MESSAGE
        assert stub.calls == []

    async def test_a_database_error_is_a_graceful_error_not_a_raise(
        self, session, client_stub, monkeypatch
    ):
        """A tool must never break an agent turn; ``DatabaseError`` is the one it converts."""
        from sqlalchemy.exc import DatabaseError

        from src.data.repositories.deck import DeckRepository

        stub = client_stub(PushOutcome(outcome="displayed", clients=1))

        async def boom(self, deck_id: str):
            raise DatabaseError("select", {}, Exception("disk I/O error"))

        monkeypatch.setattr(DeckRepository, "get_deck", boom)

        result = await set_active_deck(session, deck_id="deck-anything")

        assert result.status == "error"
        assert stub.calls == []

    async def test_an_unknown_exception_is_deliberately_not_swallowed(
        self, session, client_stub, monkeypatch
    ):
        """``except DatabaseError``, never ``except Exception`` — a bug must crash loudly.

        The neighbouring half of the promise above: "never raises" is about the failures this tool
        models, and turning an arbitrary bug into ``status="error"`` would hide it behind a message
        that says the database is at fault when it is not (``view_deck.py`` shows the same split).
        """
        from src.data.repositories.deck import DeckRepository

        client_stub(PushOutcome(outcome="displayed", clients=1))

        async def boom(self, deck_id: str):
            raise MemoryError("out of memory mid-lookup")

        monkeypatch.setattr(DeckRepository, "get_deck", boom)

        with pytest.raises(MemoryError):
            await set_active_deck(session, deck_id="deck-anything")


class TestTheResultIsCompact:
    """CM-1: under roughly 200 tokens, and echoing nothing back into the chat."""

    @pytest.mark.parametrize(
        "outcome",
        ["displayed", "no_clients_connected", "app_not_running", "payload_rejected"],
    )
    async def test_the_serialised_result_stays_well_inside_the_budget(
        self, session, client_stub, outcome
    ):
        """Bounded in **characters**, which is the thing a test can measure honestly.

        ~200 tokens is roughly 800 characters at the usual 4-chars-per-token rule of thumb; the
        400-character bound below is half of that, so the assertion has headroom against the
        estimate itself and would still fail loudly the day someone interpolates a decklist.
        """
        client_stub(PushOutcome(outcome=outcome, clients=1 if outcome == "displayed" else None))
        created = await create_deck(session, name="Burn")

        result = await set_active_deck(session, deck_id=created.deck.id)

        assert len(result.model_dump_json()) < 400, result.model_dump_json()

    async def test_a_missing_deck_result_stays_compact_even_for_an_oversized_id(
        self, session, client_stub
    ):
        """A miss must not blow the budget just because the caller's id string is huge.

        No real stored id is ever this long — ``ActiveDeckRequest`` caps a found deck's id at 256
        chars (``contracts.py``) — but nothing validates the *tool's* ``deck_id`` argument before
        the database lookup, so an oversized string reaches ``deck_not_found`` unfiltered. The
        result must still echo something bounded rather than the whole input back into chat.
        """
        client_stub(PushOutcome(outcome="displayed", clients=1))
        oversized_id = "x" * 5000

        result = await set_active_deck(session, deck_id=oversized_id)

        assert result.status == "deck_not_found"
        assert len(result.model_dump_json()) < 400, result.model_dump_json()

    async def test_nothing_about_the_deck_s_contents_is_echoed(self, session, client_stub):
        """The agent already has what it sent; a result that repeated it would cost twice."""
        client_stub(PushOutcome(outcome="displayed", clients=1))
        created = await create_deck(
            session, name="Burn", strategy="Curve out and point everything at the face."
        )

        result = await set_active_deck(session, deck_id=created.deck.id)

        dumped = result.model_dump_json()
        assert "Curve out" not in dumped, "the strategy blob has no business in a control result"
        assert set(result.model_dump()) == {
            "status",
            "deck_id",
            "deck_name",
            "clients",
            "message",
        }
