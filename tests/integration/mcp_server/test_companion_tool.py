"""Integration tests for the companion MCP tool helpers (c6-2 control, c6-4 push).

Five tools, two shapes. :func:`src.mcp_server.tools.companion.set_active_deck` (FR-07, AD-16) is
driven against a **real seeded session** and a **stubbed client verb**; the four push tools —
:func:`src.mcp_server.tools.companion.show_suggestions` (FR-08, AD-7) and its swaps, tier-list
and groups siblings — need no session at all: they validate nothing against the corpus, so the
stub is the entire harness. That asymmetry is the contract under test as much as anything else
here: a push tool that grew a database read would be a different tool.

That split is Q4's ruling and it is the whole point of the file: every
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
``companion._client_set_active_deck`` and ``companion._client_push_event`` — rather than on the
leaf. Patching the leaf would silence both verbs at once and would not prove that *this* module
reaches the client through the name it imported.

Despite living under ``tests/integration/``, these run in the ordinary ``-m "not integration"`` set:
a directory is not a marker (AD-10), and nothing here touches a socket.
"""

from pathlib import Path
from typing import get_args

import pytest

from src.companion.client import PUSH_OUTCOMES, PushOutcome
from src.companion.contracts import (
    ActiveDeckRequest,
    AgentEvent,
    GroupItem,
    GroupsPayload,
    HealthResponse,
    SuggestionItem,
    SuggestionsPayload,
    SwapItem,
    SwapsPayload,
    TierItem,
    TierListPayload,
)
from src.companion.discovery import COMPANION_FILENAME, DiscoveryRecord, read_discovery
from src.data.database import create_engine, create_session_factory, init_database
from src.data.models.card import CardModel
from src.mcp_server.tools import companion
from src.mcp_server.tools.companion import (
    CompanionStatusResult,
    ShowGroupsResult,
    ShowSuggestionsResult,
    ShowSwapsResult,
    ShowTierListResult,
    companion_status,
    set_active_deck,
    show_groups,
    show_suggestions,
    show_swaps,
    show_tier_list,
)
from src.mcp_server.tools.deck_management import create_deck
from src.mcp_server.tools.messages import DATABASE_NOT_INITIALIZED_MESSAGE

# The loopback toolkit, imported rather than rebuilt — `test_deck_changed_wiring.py`'s precedent,
# on the same terms: `test_client.py` owns the only real HTTP stubs in the repo, and a second
# implementation here would be a fake of a fake.
from tests.unit.companion.test_client import StubFleet, health_bytes, plant_discovery

_MISSING_DECK = "deck-not-in-database-00000"
"""Short enough to stay under ``_ECHO_LIMIT`` (48) unmangled, so ``deck_id == _MISSING_DECK``
assertions pin an exact match rather than a truncated one; the oversized-id case has its own
test."""

_SENTINEL_CARD_ID = "9f3c2b1a-sentinel-card-id-0000-000000000001"
_SENTINEL_REASON = "Sentinel rationale: patches the two-drop hole this deck keeps stumbling into."
_SENTINEL_TITLE = "Sentinel header for the suggested cards"
"""Three distinctive strings planted in a payload so a result that echoed any part of it would say
so by name. Chosen to be unmistakable: none of them can appear in a result by coincidence."""


def _payload(*, title: str | None = _SENTINEL_TITLE, items: int = 2) -> SuggestionsPayload:
    """A payload carrying the sentinels, with *items* suggestions in a deliberate order."""
    return SuggestionsPayload(
        title=title,
        items=[
            SuggestionItem(
                card_id=f"{_SENTINEL_CARD_ID}-{index}",
                reason=f"{_SENTINEL_REASON} ({index})",
                category="Curve" if index == 0 else None,
                confidence="high" if index == 0 else None,
            )
            for index in range(items)
        ],
    )


_SENTINEL_OUT_ID = "9f3c2b1a-sentinel-out-id-0000-000000000001"
_SENTINEL_IN_ID = "9f3c2b1a-sentinel-in-id-0000-000000000002"
_SENTINEL_RATIONALE = "Sentinel rationale: same role one turn earlier, and it dodges the removal."
_SENTINEL_SWAPS_TITLE = "Sentinel header for the proposed swaps"
"""The swaps twins of the suggestion sentinels above, for the same reason: a result that echoed
any part of a swaps payload would name itself."""


def _swaps_payload(*, title: str | None = _SENTINEL_SWAPS_TITLE, items: int = 2) -> SwapsPayload:
    """A swaps payload carrying the sentinels, with *items* swap pairs in a deliberate order."""
    return SwapsPayload(
        title=title,
        items=[
            SwapItem(
                out_card_id=f"{_SENTINEL_OUT_ID}-{index}",
                in_card_id=f"{_SENTINEL_IN_ID}-{index}",
                rationale=f"{_SENTINEL_RATIONALE} ({index})",
                out_qty=2,
                # Zero is a LEGAL in-quantity (`contracts.py`: "0 copies" is a designed case),
                # so the fixture exercises it rather than steering around it.
                in_qty=0 if index == 0 else 2,
                confidence="medium" if index == 0 else None,
            )
            for index in range(items)
        ],
    )


_SENTINEL_TIER_CARD_ID = "9f3c2b1a-sentinel-tier-card-0000-000000000001"
_SENTINEL_TIER_NAME = "Sentinel auto-include rank"
_SENTINEL_TIER_NOTE = "Sentinel note: these four never leave the deck whatever the matchup."
_SENTINEL_TIER_TITLE = "Sentinel header for the ranked tiers"
"""The tier-list twins of the suggestion sentinels above, for the same reason: a result that
echoed any part of a tier-list payload would name itself."""

_TIER_LETTERS = ("S", "A", "B", "C", "D")


def _tier_payload(*, title: str | None = _SENTINEL_TIER_TITLE, items: int = 2) -> TierListPayload:
    """A tier-list payload carrying the sentinels, with *items* tiers in a deliberate order.

    Every tier carries TWO card ids, so any assertion equating ``items_pushed`` with a card count
    is off by a factor of two rather than coincidentally right — the swaps fixture's own trick.
    """
    return TierListPayload(
        title=title,
        items=[
            TierItem(
                letter=_TIER_LETTERS[index % len(_TIER_LETTERS)],
                name=f"{_SENTINEL_TIER_NAME} ({index})",
                note=_SENTINEL_TIER_NOTE if index == 0 else None,
                card_ids=[f"{_SENTINEL_TIER_CARD_ID}-{index}-{position}" for position in range(2)],
            )
            for index in range(items)
        ],
    )


_SENTINEL_GROUP_CARD_ID = "9f3c2b1a-sentinel-group-card-0000-000000000001"
_SENTINEL_GROUP_TITLE = "Sentinel ramp package heading"
_SENTINEL_GROUP_RATIONALE = "Sentinel rationale: these accelerate into the six-drops a turn early."
_SENTINEL_GROUPS_TITLE = "Sentinel header for the card groups"
"""The groups twins of the suggestion sentinels above, for the same reason: a result that
echoed any part of a groups payload would name itself."""


def _groups_payload(*, title: str | None = _SENTINEL_GROUPS_TITLE, items: int = 2) -> GroupsPayload:
    """A groups payload carrying the sentinels, with *items* groups in a deliberate order.

    Every group carries TWO card ids, so any assertion equating ``items_pushed`` with a card
    count is off by a factor of two rather than coincidentally right — the tier fixture's own
    trick, inherited from the swaps one.
    """
    return GroupsPayload(
        title=title,
        items=[
            GroupItem(
                title=f"{_SENTINEL_GROUP_TITLE} ({index})",
                rationale=f"{_SENTINEL_GROUP_RATIONALE} ({index})",
                card_ids=[f"{_SENTINEL_GROUP_CARD_ID}-{index}-{position}" for position in range(2)],
            )
            for index in range(items)
        ],
    )


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


class _PushStub:
    """Stands in for ``push_event``, recording every envelope it was handed.

    The envelopes rather than a call count, for the same reason as above: "nothing was pushed" and
    "the wrong thing was pushed" are different failures, and this is the only place in the suite
    that can tell them apart for this tool.
    """

    def __init__(self, outcome: PushOutcome) -> None:
        self.outcome = outcome
        self.events: list[AgentEvent] = []

    async def __call__(self, event: AgentEvent, **kwargs: object) -> PushOutcome:
        self.events.append(event)
        return self.outcome


@pytest.fixture
def push_stub(monkeypatch):
    """Yield a factory that installs a :class:`_PushStub` answering a chosen outcome."""

    def install(outcome: PushOutcome) -> _PushStub:
        stub = _PushStub(outcome)
        monkeypatch.setattr(companion, "_client_push_event", stub)
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

    async def test_a_database_not_initialized_result_stays_compact_for_an_oversized_id(
        self, tmp_path: Path, client_stub
    ):
        """The database-layer guard runs *before* the miss check, so it needs the same bound."""
        client_stub(PushOutcome(outcome="displayed", clients=1))
        oversized_id = "x" * 5000
        engine = create_engine(f"sqlite+aiosqlite:///{(tmp_path / 'empty.db').as_posix()}")
        await init_database(engine)
        session_factory = create_session_factory(engine)
        async with session_factory() as empty_session:
            result = await set_active_deck(empty_session, deck_id=oversized_id)
        await engine.dispose()

        assert result.status == "database_not_initialized"
        assert len(result.model_dump_json()) < 400, result.model_dump_json()

    async def test_a_database_error_result_stays_compact_for_an_oversized_id(
        self, session, client_stub, monkeypatch
    ):
        """The ``DatabaseError`` branch reads ``deck_id`` before the lookup ever resolves."""
        from sqlalchemy.exc import DatabaseError

        from src.data.repositories.deck import DeckRepository

        client_stub(PushOutcome(outcome="displayed", clients=1))
        oversized_id = "x" * 5000

        async def boom(self, deck_id: str):
            raise DatabaseError("select", {}, Exception("disk I/O error"))

        monkeypatch.setattr(DeckRepository, "get_deck", boom)

        result = await set_active_deck(session, deck_id=oversized_id)

        assert result.status == "error"
        assert len(result.model_dump_json()) < 400, result.model_dump_json()

    async def test_a_displayed_result_stays_compact_for_an_oversized_deck_name(
        self, session, client_stub
    ):
        """``deck.name`` is unbounded in storage — ``create_deck`` only refuses a blank one."""
        client_stub(PushOutcome(outcome="displayed", clients=1))
        created = await create_deck(session, name="B" * 5000)

        result = await set_active_deck(session, deck_id=created.deck.id)

        assert result.status == "displayed"
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


class TestTheSuggestionsPushIsDelegated:
    """AC 2: the payload becomes one envelope, and the envelope reaches the leaf unchanged."""

    async def test_one_suggestions_envelope_carries_the_payload_through_untouched(self, push_stub):
        """The whole of this tool's job, and the only thing only this layer can get wrong.

        The comparison is against a **freshly built equal payload** rather than against the
        argument object, so an implementation that posted a different payload fails even though the
        argument it was handed is still sitting in the caller's hands, unmodified.
        """
        stub = push_stub(PushOutcome(outcome="displayed", clients=1))

        result = await show_suggestions(payload=_payload())

        assert len(stub.events) == 1, "one call is one push; nothing at this layer retries"
        event = stub.events[0]
        assert event.kind == "suggestions"
        assert event.payload == _payload(), "the payload crosses to the leaf untouched"
        assert result.status == "displayed"
        assert result.items_pushed == 2

    async def test_payload_order_is_preserved_because_it_is_render_order(self, push_stub):
        """Nothing here sorts, dedupes or reorders — the agent's order is the screen's order."""
        stub = push_stub(PushOutcome(outcome="displayed", clients=1))
        payload = _payload(items=3)

        await show_suggestions(payload=payload)

        assert [item.card_id for item in stub.events[0].payload.items] == [
            item.card_id for item in payload.items
        ]

    async def test_the_envelope_timestamp_is_timezone_aware(self, push_stub):
        """A naive ``ts`` is refused on the live wire (``AwareDatetime``) and is invisible here.

        Nothing else in this file touches a socket, so a helper that used ``utcnow()`` would pass
        every other assertion in the class and turn into ``payload_rejected`` in production. This
        is the assertion that stands in for the wire.
        """
        stub = push_stub(PushOutcome(outcome="displayed", clients=1))

        await show_suggestions(payload=_payload())

        assert stub.events[0].ts.tzinfo is not None

    async def test_each_call_mints_its_own_opaque_event_id(self, push_stub):
        """``id`` is identity and dedupe (AD-6): two pushes must not collide on it."""
        stub = push_stub(PushOutcome(outcome="displayed", clients=1))

        await show_suggestions(payload=_payload())
        await show_suggestions(payload=_payload())

        first, second = (event.id for event in stub.events)
        assert first.strip(), "a blank id is refused by the envelope and useless for dedupe"
        assert first != second, "a reused id would let a reader collapse two distinct pushes"

    async def test_no_title_is_injected_when_the_agent_did_not_write_one(self, push_stub):
        """The fallback header belongs to the reader; a tool-supplied one is not agent-authored."""
        stub = push_stub(PushOutcome(outcome="displayed", clients=1))

        await show_suggestions(payload=_payload(title=None))

        assert stub.events[0].payload.title is None


class TestEveryPushOutcomeBecomesTheStatusOfTheSameName:
    """AC 2/6: AD-8's five tokens, 1:1, with the count carried and never invented."""

    def test_the_result_vocabulary_is_the_client_s_five_and_nothing_more(self):
        """A push tool has no database to be wrong about, so it layers no status above the wire.

        Set equality against the client's own tuple, so widening either side without the other
        fails here rather than in a review comment (AD-8, AD-16).
        """
        annotation = ShowSuggestionsResult.model_fields["status"].annotation
        assert set(get_args(annotation)) == set(PUSH_OUTCOMES)

    @pytest.mark.parametrize(
        ("outcome", "clients"),
        [
            pytest.param("displayed", 2, id="displayed"),
            pytest.param("no_clients_connected", 0, id="no-clients"),
            pytest.param("app_not_running", None, id="app-not-running"),
            pytest.param("payload_rejected", None, id="payload-rejected"),
            pytest.param("backend_error", None, id="backend-error"),
        ],
    )
    async def test_the_token_and_the_count_both_pass_through(self, push_stub, outcome, clients):
        """All five in one parametrization: a tool that swallowed the fifth would look correct in
        any single-row test. ``0`` and ``None`` are distinguished deliberately — ``0`` is a wire
        success (nobody watching), ``None`` is "the backend never told us"."""
        push_stub(PushOutcome(outcome=outcome, clients=clients))

        result = await show_suggestions(payload=_payload())

        assert result.status == outcome
        assert result.clients == clients
        assert result.items_pushed == 2
        assert result.message, "every status carries a sentence a human can read"

    async def test_no_clients_connected_is_pushed_once_and_never_re_sent(self, push_stub):
        """c5-5's ruling: the backend will not re-send, so a retry duplicates at the first tab."""
        stub = push_stub(PushOutcome(outcome="no_clients_connected", clients=0))

        result = await show_suggestions(payload=_payload())

        assert result.status == "no_clients_connected"
        assert result.clients == 0
        assert len(stub.events) == 1, "a success with nobody watching is still one push"

    async def test_no_status_leaks_a_raw_outcome_token_into_the_message(self, push_stub):
        """The token is for a caller to switch on; the sentence is for a person to read."""
        for outcome in PUSH_OUTCOMES:
            push_stub(PushOutcome(outcome=outcome, clients=1 if outcome == "displayed" else None))

            result = await show_suggestions(payload=_payload())

            assert outcome not in result.message
            assert "companion" in result.message.lower()


class TestAnEmptySuggestionsPayloadIsStillPushed:
    """AC 4: "I looked and found nothing" is expressible, so it must reach the wire."""

    async def test_an_empty_payload_is_posted_rather_than_short_circuited(self, push_stub):
        stub = push_stub(PushOutcome(outcome="displayed", clients=1))

        result = await show_suggestions(payload=_payload(items=0))

        assert len(stub.events) == 1, "AD-7: an empty push is a legal push, not a skipped one"
        assert stub.events[0].payload.items == []
        assert result.status == "displayed"
        assert result.items_pushed == 0

    async def test_it_is_not_passing_because_every_payload_is_pushed_empty(self, push_stub):
        """The non-vacuity pairing: the same stub, both sizes, and the counts told apart."""
        stub = push_stub(PushOutcome(outcome="displayed", clients=1))

        empty = await show_suggestions(payload=_payload(items=0))
        filled = await show_suggestions(payload=_payload(items=2))

        assert [len(event.payload.items) for event in stub.events] == [0, 2], (
            "the envelope carries whatever the caller sent, empty and non-empty alike"
        )
        assert (empty.items_pushed, filled.items_pushed) == (0, 2)


class TestTheSuggestionsResultIsCompact:
    """AC 5: under roughly 200 tokens, and echoing not one word of the payload."""

    @pytest.mark.parametrize("outcome", PUSH_OUTCOMES)
    async def test_the_serialised_result_stays_well_inside_the_budget(self, push_stub, outcome):
        """Every branch, not the happy one: the 400-character bound and its rationale are the same
        ones documented for the control tool above, and a push result has more reason to grow —
        the thing it is reporting on is a list."""
        push_stub(PushOutcome(outcome=outcome, clients=2 if outcome == "displayed" else None))

        result = await show_suggestions(payload=_payload(items=60))

        assert len(result.model_dump_json()) < 400, result.model_dump_json()

    @pytest.mark.parametrize("outcome", PUSH_OUTCOMES)
    async def test_not_one_planted_string_comes_back_out(self, push_stub, outcome):
        """The guard that stays behind: the agent already holds this content, so a result that
        repeated it would cost the conversation twice for nothing (CM-1)."""
        push_stub(PushOutcome(outcome=outcome, clients=2 if outcome == "displayed" else None))

        result = await show_suggestions(payload=_payload())

        dumped = result.model_dump_json()
        for sentinel in (_SENTINEL_CARD_ID, _SENTINEL_REASON, _SENTINEL_TITLE, "Curve"):
            assert sentinel not in dumped, f"{sentinel!r} was echoed back into the result"

    async def test_the_result_carries_counts_and_nothing_else(self, push_stub):
        push_stub(PushOutcome(outcome="displayed", clients=1))

        result = await show_suggestions(payload=_payload())

        assert set(result.model_dump()) == {"status", "clients", "items_pushed", "message"}


class TestTheAppBeingClosedIsReportedAndNothingMore:
    """AC 6: the companion is a second channel, never a condition on the first (NG5, SC-3)."""

    async def test_a_closed_app_is_named_as_such(self, push_stub):
        push_stub(PushOutcome(outcome="app_not_running"))

        result = await show_suggestions(payload=_payload())

        assert result.status == "app_not_running"
        assert result.clients is None
        assert "isn't running" in result.message
        assert result.items_pushed == 2, "what was attempted is reported even when nothing was sent"

    @pytest.mark.parametrize("outcome", PUSH_OUTCOMES)
    async def test_no_message_tells_the_agent_to_change_its_written_answer(
        self, push_stub, outcome
    ):
        """The glass is additive. A sentence here that offered chat as a *fallback* would imply the
        normal reply had been conditional on the push succeeding, which it never was."""
        push_stub(PushOutcome(outcome=outcome, clients=1 if outcome == "displayed" else None))

        result = await show_suggestions(payload=_payload())

        lowered = result.message.lower()
        for directive in ("instead", "skip", "no need to", "don't"):
            assert directive not in lowered, f"the message steers the reply with {directive!r}"


class TestTheSwapsPushIsDelegated:
    """16-1 AC 2: one swaps payload becomes one envelope, and it reaches the leaf unchanged."""

    async def test_one_swaps_envelope_carries_the_payload_through_untouched(self, push_stub):
        """The structural clone of the suggestions delegation test, and the same trap: the
        comparison is against a freshly built equal payload rather than the argument object."""
        stub = push_stub(PushOutcome(outcome="displayed", clients=1))

        result = await show_swaps(payload=_swaps_payload())

        assert len(stub.events) == 1, "one call is one push; nothing at this layer retries"
        event = stub.events[0]
        assert event.kind == "swaps"
        assert event.payload == _swaps_payload(), "the payload crosses to the leaf untouched"
        assert result.status == "displayed"
        assert result.items_pushed == 2

    async def test_payload_order_is_preserved_because_it_is_render_order(self, push_stub):
        """Nothing here sorts, dedupes or reorders — the agent's order is the screen's order."""
        stub = push_stub(PushOutcome(outcome="displayed", clients=1))
        payload = _swaps_payload(items=3)

        await show_swaps(payload=payload)

        assert [(item.out_card_id, item.in_card_id) for item in stub.events[0].payload.items] == [
            (item.out_card_id, item.in_card_id) for item in payload.items
        ]

    async def test_the_envelope_timestamp_is_timezone_aware(self, push_stub):
        """The wire refuses a naive ``ts`` (``AwareDatetime``) and no socket exists here to say
        so — this assertion stands in for it, exactly as the suggestions twin does."""
        stub = push_stub(PushOutcome(outcome="displayed", clients=1))

        await show_swaps(payload=_swaps_payload())

        assert stub.events[0].ts.tzinfo is not None

    async def test_each_call_mints_its_own_opaque_event_id(self, push_stub):
        """``id`` is identity and dedupe (AD-6): two pushes must not collide on it."""
        stub = push_stub(PushOutcome(outcome="displayed", clients=1))

        await show_swaps(payload=_swaps_payload())
        await show_swaps(payload=_swaps_payload())

        first, second = (event.id for event in stub.events)
        assert first.strip(), "a blank id is refused by the envelope and useless for dedupe"
        assert first != second, "a reused id would let a reader collapse two distinct pushes"

    async def test_no_title_is_injected_when_the_agent_did_not_write_one(self, push_stub):
        """The fallback header belongs to the reader; a tool-supplied one is not agent-authored."""
        stub = push_stub(PushOutcome(outcome="displayed", clients=1))

        await show_swaps(payload=_swaps_payload(title=None))

        assert stub.events[0].payload.title is None


class TestEverySwapsOutcomeBecomesTheStatusOfTheSameName:
    """16-1 AC 2: AD-8's five tokens, 1:1, with the count carried and never invented."""

    def test_the_result_vocabulary_is_the_client_s_five_and_nothing_more(self):
        """A push tool has no database to be wrong about, so it layers no status above the wire —
        set equality against the client's own tuple, exactly as the suggestions result pins."""
        annotation = ShowSwapsResult.model_fields["status"].annotation
        assert set(get_args(annotation)) == set(PUSH_OUTCOMES)

    @pytest.mark.parametrize(
        ("outcome", "clients"),
        [
            pytest.param("displayed", 2, id="displayed"),
            pytest.param("no_clients_connected", 0, id="no-clients"),
            pytest.param("app_not_running", None, id="app-not-running"),
            pytest.param("payload_rejected", None, id="payload-rejected"),
            pytest.param("backend_error", None, id="backend-error"),
        ],
    )
    async def test_the_token_and_the_count_both_pass_through(self, push_stub, outcome, clients):
        """All five in one parametrization: a tool that swallowed the fifth would look correct in
        any single-row test. ``0`` and ``None`` stay distinguishable on purpose."""
        push_stub(PushOutcome(outcome=outcome, clients=clients))

        result = await show_swaps(payload=_swaps_payload())

        assert result.status == outcome
        assert result.clients == clients
        assert result.items_pushed == 2
        assert result.message, "every status carries a sentence a human can read"

    async def test_no_status_leaks_a_raw_outcome_token_into_the_message(self, push_stub):
        """The token is for a caller to switch on; the sentence is for a person to read."""
        for outcome in PUSH_OUTCOMES:
            push_stub(PushOutcome(outcome=outcome, clients=1 if outcome == "displayed" else None))

            result = await show_swaps(payload=_swaps_payload())

            assert outcome not in result.message
            assert "companion" in result.message.lower()


class TestAnEmptySwapsPayloadIsStillPushed:
    """16-1 edge row: "I found no trade worth proposing" is expressible, so it reaches the wire."""

    async def test_an_empty_payload_is_posted_rather_than_short_circuited(self, push_stub):
        stub = push_stub(PushOutcome(outcome="displayed", clients=1))

        result = await show_swaps(payload=_swaps_payload(items=0))

        assert len(stub.events) == 1, "AD-7: an empty push is a legal push, not a skipped one"
        assert stub.events[0].payload.items == []
        assert result.status == "displayed"
        assert result.items_pushed == 0

    async def test_it_is_not_passing_because_every_payload_is_pushed_empty(self, push_stub):
        """The non-vacuity pairing: the same stub, both sizes, and the counts told apart."""
        stub = push_stub(PushOutcome(outcome="displayed", clients=1))

        empty = await show_swaps(payload=_swaps_payload(items=0))
        filled = await show_swaps(payload=_swaps_payload(items=2))

        assert [len(event.payload.items) for event in stub.events] == [0, 2], (
            "the envelope carries whatever the caller sent, empty and non-empty alike"
        )
        assert (empty.items_pushed, filled.items_pushed) == (0, 2)

    async def test_items_pushed_counts_swap_pairs_and_not_cards(self, push_stub):
        """One trade carries two card ids and is ONE item — the count the result reports."""
        push_stub(PushOutcome(outcome="displayed", clients=1))

        result = await show_swaps(payload=_swaps_payload(items=3))

        assert result.items_pushed == 3


class TestTheSwapsResultIsCompact:
    """16-1: under the same ~400-char bound, and echoing not one word of the payload."""

    @pytest.mark.parametrize("outcome", PUSH_OUTCOMES)
    async def test_the_serialised_result_stays_well_inside_the_budget(self, push_stub, outcome):
        """Every branch, at the payload cap — the same bound and rationale the suggestions
        result documents, and a swaps result has the same reason to grow."""
        push_stub(PushOutcome(outcome=outcome, clients=2 if outcome == "displayed" else None))

        result = await show_swaps(payload=_swaps_payload(items=60))

        assert len(result.model_dump_json()) < 400, result.model_dump_json()

    @pytest.mark.parametrize("outcome", PUSH_OUTCOMES)
    async def test_not_one_planted_string_comes_back_out(self, push_stub, outcome):
        """The agent already holds this content; a result that repeated it would cost the
        conversation twice for nothing (CM-1)."""
        push_stub(PushOutcome(outcome=outcome, clients=2 if outcome == "displayed" else None))

        result = await show_swaps(payload=_swaps_payload())

        dumped = result.model_dump_json()
        for sentinel in (
            _SENTINEL_OUT_ID,
            _SENTINEL_IN_ID,
            _SENTINEL_RATIONALE,
            _SENTINEL_SWAPS_TITLE,
        ):
            assert sentinel not in dumped, f"{sentinel!r} was echoed back into the result"

    async def test_the_result_carries_counts_and_nothing_else(self, push_stub):
        push_stub(PushOutcome(outcome="displayed", clients=1))

        result = await show_swaps(payload=_swaps_payload())

        assert set(result.model_dump()) == {"status", "clients", "items_pushed", "message"}


class TestTheTierListPushIsDelegated:
    """16-2 AC: one tier-list payload becomes one envelope, and it reaches the leaf unchanged."""

    async def test_one_tier_list_envelope_carries_the_payload_through_untouched(self, push_stub):
        """The structural clone of the suggestions delegation test, and the same trap: the
        comparison is against a freshly built equal payload rather than the argument object."""
        stub = push_stub(PushOutcome(outcome="displayed", clients=1))

        result = await show_tier_list(payload=_tier_payload())

        assert len(stub.events) == 1, "one call is one push; nothing at this layer retries"
        event = stub.events[0]
        assert event.kind == "tier_list"
        assert event.payload == _tier_payload(), "the payload crosses to the leaf untouched"
        assert result.status == "displayed"
        assert result.items_pushed == 2

    async def test_payload_order_is_preserved_because_it_is_render_order(self, push_stub):
        """Nothing here sorts, dedupes or reorders — the agent's order is the screen's order,
        and for a tier list that includes NOT re-sorting tiers by letter."""
        stub = push_stub(PushOutcome(outcome="displayed", clients=1))
        payload = _tier_payload(items=3)

        await show_tier_list(payload=payload)

        assert [(item.letter, item.name) for item in stub.events[0].payload.items] == [
            (item.letter, item.name) for item in payload.items
        ]

    async def test_the_envelope_timestamp_is_timezone_aware(self, push_stub):
        """The wire refuses a naive ``ts`` (``AwareDatetime``) and no socket exists here to say
        so — this assertion stands in for it, exactly as the suggestions twin does."""
        stub = push_stub(PushOutcome(outcome="displayed", clients=1))

        await show_tier_list(payload=_tier_payload())

        assert stub.events[0].ts.tzinfo is not None

    async def test_each_call_mints_its_own_opaque_event_id(self, push_stub):
        """``id`` is identity and dedupe (AD-6): two pushes must not collide on it."""
        stub = push_stub(PushOutcome(outcome="displayed", clients=1))

        await show_tier_list(payload=_tier_payload())
        await show_tier_list(payload=_tier_payload())

        first, second = (event.id for event in stub.events)
        assert first.strip(), "a blank id is refused by the envelope and useless for dedupe"
        assert first != second, "a reused id would let a reader collapse two distinct pushes"

    async def test_no_title_is_injected_when_the_agent_did_not_write_one(self, push_stub):
        """The fallback header belongs to the reader (``DEFAULT_TITLE_BY_KIND`` says "Tier
        list"); a tool-supplied one is not agent-authored."""
        stub = push_stub(PushOutcome(outcome="displayed", clients=1))

        await show_tier_list(payload=_tier_payload(title=None))

        assert stub.events[0].payload.title is None


class TestEveryTierListOutcomeBecomesTheStatusOfTheSameName:
    """16-2 AC: AD-8's five tokens, 1:1, with the count carried and never invented."""

    def test_the_result_vocabulary_is_the_client_s_five_and_nothing_more(self):
        """A push tool has no database to be wrong about, so it layers no status above the wire —
        set equality against the client's own tuple, exactly as its two siblings pin."""
        annotation = ShowTierListResult.model_fields["status"].annotation
        assert set(get_args(annotation)) == set(PUSH_OUTCOMES)

    @pytest.mark.parametrize(
        ("outcome", "clients"),
        [
            pytest.param("displayed", 2, id="displayed"),
            pytest.param("no_clients_connected", 0, id="no-clients"),
            pytest.param("app_not_running", None, id="app-not-running"),
            pytest.param("payload_rejected", None, id="payload-rejected"),
            pytest.param("backend_error", None, id="backend-error"),
        ],
    )
    async def test_the_token_and_the_count_both_pass_through(self, push_stub, outcome, clients):
        """All five in one parametrization: a tool that swallowed the fifth would look correct in
        any single-row test. ``0`` and ``None`` stay distinguishable on purpose."""
        push_stub(PushOutcome(outcome=outcome, clients=clients))

        result = await show_tier_list(payload=_tier_payload())

        assert result.status == outcome
        assert result.clients == clients
        assert result.items_pushed == 2
        assert result.message, "every status carries a sentence a human can read"

    async def test_no_status_leaks_a_raw_outcome_token_into_the_message(self, push_stub):
        """The token is for a caller to switch on; the sentence is for a person to read."""
        for outcome in PUSH_OUTCOMES:
            push_stub(PushOutcome(outcome=outcome, clients=1 if outcome == "displayed" else None))

            result = await show_tier_list(payload=_tier_payload())

            assert outcome not in result.message
            assert "companion" in result.message.lower()


class TestAnEmptyTierListPayloadIsStillPushed:
    """16-2 edge row: "I found nothing worth tiering" is expressible, so it reaches the wire."""

    async def test_an_empty_payload_is_posted_rather_than_short_circuited(self, push_stub):
        stub = push_stub(PushOutcome(outcome="displayed", clients=1))

        result = await show_tier_list(payload=_tier_payload(items=0))

        assert len(stub.events) == 1, "AD-7: an empty push is a legal push, not a skipped one"
        assert stub.events[0].payload.items == []
        assert result.status == "displayed"
        assert result.items_pushed == 0

    async def test_it_is_not_passing_because_every_payload_is_pushed_empty(self, push_stub):
        """The non-vacuity pairing: the same stub, both sizes, and the counts told apart."""
        stub = push_stub(PushOutcome(outcome="displayed", clients=1))

        empty = await show_tier_list(payload=_tier_payload(items=0))
        filled = await show_tier_list(payload=_tier_payload(items=2))

        assert [len(event.payload.items) for event in stub.events] == [0, 2], (
            "the envelope carries whatever the caller sent, empty and non-empty alike"
        )
        assert (empty.items_pushed, filled.items_pushed) == (0, 2)

    async def test_items_pushed_counts_tiers_and_not_cards(self, push_stub):
        """One tier carries two card ids in this fixture and is ONE item — the count the result
        reports is ``len(payload.items)``, the swaps "pairs, not cards" precedent applied."""
        push_stub(PushOutcome(outcome="displayed", clients=1))

        payload = _tier_payload(items=3)
        cards_carried = sum(len(item.card_ids) for item in payload.items)
        assert cards_carried == 6, "the fixture must carry more cards than tiers to prove this"

        result = await show_tier_list(payload=payload)

        assert result.items_pushed == 3


class TestTheTierListResultIsCompact:
    """16-2: under the same ~400-char bound, and echoing not one word of the payload."""

    @pytest.mark.parametrize("outcome", PUSH_OUTCOMES)
    async def test_the_serialised_result_stays_well_inside_the_budget(self, push_stub, outcome):
        """Every branch, at the payload cap — 12 tiers is ``TierListPayload``'s own maximum."""
        push_stub(PushOutcome(outcome=outcome, clients=2 if outcome == "displayed" else None))

        result = await show_tier_list(payload=_tier_payload(items=12))

        assert len(result.model_dump_json()) < 400, result.model_dump_json()

    @pytest.mark.parametrize("outcome", PUSH_OUTCOMES)
    async def test_not_one_planted_string_comes_back_out(self, push_stub, outcome):
        """The agent already holds this content; a result that repeated it would cost the
        conversation twice for nothing (CM-1)."""
        push_stub(PushOutcome(outcome=outcome, clients=2 if outcome == "displayed" else None))

        result = await show_tier_list(payload=_tier_payload())

        dumped = result.model_dump_json()
        for sentinel in (
            _SENTINEL_TIER_CARD_ID,
            _SENTINEL_TIER_NAME,
            _SENTINEL_TIER_NOTE,
            _SENTINEL_TIER_TITLE,
        ):
            assert sentinel not in dumped, f"{sentinel!r} was echoed back into the result"

    async def test_the_result_carries_counts_and_nothing_else(self, push_stub):
        push_stub(PushOutcome(outcome="displayed", clients=1))

        result = await show_tier_list(payload=_tier_payload())

        assert set(result.model_dump()) == {"status", "clients", "items_pushed", "message"}


class TestTheGroupsPushIsDelegated:
    """16-3 AC: one groups payload becomes one envelope, and it reaches the leaf unchanged."""

    async def test_one_groups_envelope_carries_the_payload_through_untouched(self, push_stub):
        """The structural clone of the suggestions delegation test, and the same trap: the
        comparison is against a freshly built equal payload rather than the argument object."""
        stub = push_stub(PushOutcome(outcome="displayed", clients=1))

        result = await show_groups(payload=_groups_payload())

        assert len(stub.events) == 1, "one call is one push; nothing at this layer retries"
        event = stub.events[0]
        assert event.kind == "groups"
        assert event.payload == _groups_payload(), "the payload crosses to the leaf untouched"
        assert result.status == "displayed"
        assert result.items_pushed == 2

    async def test_payload_order_is_preserved_because_it_is_render_order(self, push_stub):
        """Nothing here sorts, dedupes or merges — the agent's order is the screen's order."""
        stub = push_stub(PushOutcome(outcome="displayed", clients=1))
        payload = _groups_payload(items=3)

        await show_groups(payload=payload)

        assert [item.title for item in stub.events[0].payload.items] == [
            item.title for item in payload.items
        ]

    async def test_the_envelope_timestamp_is_timezone_aware(self, push_stub):
        """The wire refuses a naive ``ts`` (``AwareDatetime``) and no socket exists here to say
        so — this assertion stands in for it, exactly as the suggestions twin does."""
        stub = push_stub(PushOutcome(outcome="displayed", clients=1))

        await show_groups(payload=_groups_payload())

        assert stub.events[0].ts.tzinfo is not None

    async def test_each_call_mints_its_own_opaque_event_id(self, push_stub):
        """``id`` is identity and dedupe (AD-6): two pushes must not collide on it."""
        stub = push_stub(PushOutcome(outcome="displayed", clients=1))

        await show_groups(payload=_groups_payload())
        await show_groups(payload=_groups_payload())

        first, second = (event.id for event in stub.events)
        assert first.strip(), "a blank id is refused by the envelope and useless for dedupe"
        assert first != second, "a reused id would let a reader collapse two distinct pushes"

    async def test_no_title_is_injected_when_the_agent_did_not_write_one(self, push_stub):
        """The fallback header belongs to the reader (``DEFAULT_TITLE_BY_KIND`` says
        "Groups"); a tool-supplied one is not agent-authored."""
        stub = push_stub(PushOutcome(outcome="displayed", clients=1))

        await show_groups(payload=_groups_payload(title=None))

        assert stub.events[0].payload.title is None


class TestEveryGroupsOutcomeBecomesTheStatusOfTheSameName:
    """16-3 AC: AD-8's five tokens, 1:1, with the count carried and never invented."""

    def test_the_result_vocabulary_is_the_client_s_five_and_nothing_more(self):
        """A push tool has no database to be wrong about, so it layers no status above the wire —
        set equality against the client's own tuple, exactly as its three siblings pin."""
        annotation = ShowGroupsResult.model_fields["status"].annotation
        assert set(get_args(annotation)) == set(PUSH_OUTCOMES)

    @pytest.mark.parametrize(
        ("outcome", "clients"),
        [
            pytest.param("displayed", 2, id="displayed"),
            pytest.param("no_clients_connected", 0, id="no-clients"),
            pytest.param("app_not_running", None, id="app-not-running"),
            pytest.param("payload_rejected", None, id="payload-rejected"),
            pytest.param("backend_error", None, id="backend-error"),
        ],
    )
    async def test_the_token_and_the_count_both_pass_through(self, push_stub, outcome, clients):
        """All five in one parametrization: a tool that swallowed the fifth would look correct in
        any single-row test. ``0`` and ``None`` stay distinguishable on purpose."""
        push_stub(PushOutcome(outcome=outcome, clients=clients))

        result = await show_groups(payload=_groups_payload())

        assert result.status == outcome
        assert result.clients == clients
        assert result.items_pushed == 2
        assert result.message, "every status carries a sentence a human can read"

    async def test_no_status_leaks_a_raw_outcome_token_into_the_message(self, push_stub):
        """The token is for a caller to switch on; the sentence is for a person to read."""
        for outcome in PUSH_OUTCOMES:
            push_stub(PushOutcome(outcome=outcome, clients=1 if outcome == "displayed" else None))

            result = await show_groups(payload=_groups_payload())

            assert outcome not in result.message
            assert "companion" in result.message.lower()


class TestAnEmptyGroupsPayloadIsStillPushed:
    """16-3 edge row: "I found no grouping worth drawing" is expressible, so it reaches the
    wire."""

    async def test_an_empty_payload_is_posted_rather_than_short_circuited(self, push_stub):
        stub = push_stub(PushOutcome(outcome="displayed", clients=1))

        result = await show_groups(payload=_groups_payload(items=0))

        assert len(stub.events) == 1, "AD-7: an empty push is a legal push, not a skipped one"
        assert stub.events[0].payload.items == []
        assert result.status == "displayed"
        assert result.items_pushed == 0

    async def test_it_is_not_passing_because_every_payload_is_pushed_empty(self, push_stub):
        """The non-vacuity pairing: the same stub, both sizes, and the counts told apart."""
        stub = push_stub(PushOutcome(outcome="displayed", clients=1))

        empty = await show_groups(payload=_groups_payload(items=0))
        filled = await show_groups(payload=_groups_payload(items=2))

        assert [len(event.payload.items) for event in stub.events] == [0, 2], (
            "the envelope carries whatever the caller sent, empty and non-empty alike"
        )
        assert (empty.items_pushed, filled.items_pushed) == (0, 2)

    async def test_items_pushed_counts_groups_and_not_cards(self, push_stub):
        """One group carries two card ids in this fixture and is ONE item — the count the result
        reports is ``len(payload.items)``, the tiers "not cards" precedent applied: a
        counts-cards bug is off by 2× here rather than coincidentally right."""
        push_stub(PushOutcome(outcome="displayed", clients=1))

        payload = _groups_payload(items=3)
        cards_carried = sum(len(item.card_ids) for item in payload.items)
        assert cards_carried == 6, "the fixture must carry more cards than groups to prove this"

        result = await show_groups(payload=payload)

        assert result.items_pushed == 3


class TestTheGroupsResultIsCompact:
    """16-3: under the same ~400-char bound, and echoing not one word of the payload."""

    @pytest.mark.parametrize("outcome", PUSH_OUTCOMES)
    async def test_the_serialised_result_stays_well_inside_the_budget(self, push_stub, outcome):
        """Every branch, at the payload cap — 12 groups is ``GroupsPayload``'s own maximum."""
        push_stub(PushOutcome(outcome=outcome, clients=2 if outcome == "displayed" else None))

        result = await show_groups(payload=_groups_payload(items=12))

        assert len(result.model_dump_json()) < 400, result.model_dump_json()

    @pytest.mark.parametrize("outcome", PUSH_OUTCOMES)
    async def test_not_one_planted_string_comes_back_out(self, push_stub, outcome):
        """The agent already holds this content; a result that repeated it would cost the
        conversation twice for nothing (CM-1)."""
        push_stub(PushOutcome(outcome=outcome, clients=2 if outcome == "displayed" else None))

        result = await show_groups(payload=_groups_payload())

        dumped = result.model_dump_json()
        for sentinel in (
            _SENTINEL_GROUP_CARD_ID,
            _SENTINEL_GROUP_TITLE,
            _SENTINEL_GROUP_RATIONALE,
            _SENTINEL_GROUPS_TITLE,
        ):
            assert sentinel not in dumped, f"{sentinel!r} was echoed back into the result"

    async def test_the_result_carries_counts_and_nothing_else(self, push_stub):
        push_stub(PushOutcome(outcome="displayed", clients=1))

        result = await show_groups(payload=_groups_payload())

        assert set(result.model_dump()) == {"status", "clients", "items_pushed", "message"}


class TestEveryPushToolSpeaksItsOwnNoun:
    """16-2's consolidation guard: the tables, the sentences, and each tool's own wiring.

    The consolidation promised the suggestions/swaps wording stays byte-identical, and until
    this class nothing enforced any of it: no test read a message table by name and no test
    pinned a push-tool sentence (the ``"1 tab."`` pin above belongs to the CONTROL tool).
    Measured before writing it: ``show_tier_list`` wired to ``_SWAPS_PUSH_MESSAGES`` with a
    ``"suggested cards"`` success subject passed the whole suite (review, 2026-08-21). Three
    layers close that hole — the builder against the shipped bytes, each module table against
    the builder-with-its-own-noun, and each TOOL against the sentence a person actually reads —
    because any one alone leaves a cross-wiring the other two catch.
    """

    def test_each_module_table_is_the_builder_applied_to_its_own_noun(self):
        """The tables are one builder, four nouns — not four drifting copies, and not one
        table wired to another kind's name."""
        assert companion._PUSH_MESSAGES == companion._push_messages("suggestions")
        assert companion._SWAPS_PUSH_MESSAGES == companion._push_messages("swaps")
        assert companion._TIER_LIST_PUSH_MESSAGES == companion._push_messages("tiers")
        assert companion._GROUPS_PUSH_MESSAGES == companion._push_messages("groups")

    def test_the_four_suggestions_failure_sentences_are_the_shipped_bytes(self):
        """Byte-for-byte, em dash included — the anchor that catches BUILDER drift.

        The table-equals-builder assertions above are relative and would follow a reworded
        template together; this one is absolute, so an edit to :func:`_push_messages` that moves
        one shipped byte fails here by name. One kind suffices: the previous test makes the
        other two the same bytes with a different noun.
        """
        assert companion._PUSH_MESSAGES == {
            "no_clients_connected": (
                "The companion took the suggestions, but no browser tab is open to see them — "
                "open the URL the companion printed when it started."
            ),
            "app_not_running": (
                "The companion app isn't running, so the suggestions have nowhere to appear. "
                "Offer to open it — companion_status returns the launch command, and the "
                "companion skill walks through it — the content is in chat regardless."
            ),
            "payload_rejected": (
                "The companion refused the suggestions, so none of them were displayed. The "
                "content is in chat regardless."
            ),
            "backend_error": (
                "The companion is running but the suggestions didn't land. Try again — the "
                "content is in chat regardless."
            ),
        }

    async def test_each_tool_names_its_own_content_when_the_app_is_closed(self, push_stub):
        """The wiring, at the tool: a cross-wired ``messages=`` argument fails here by noun."""
        cases = (
            (show_suggestions, _payload(), "suggestions"),
            (show_swaps, _swaps_payload(), "swaps"),
            (show_tier_list, _tier_payload(), "tiers"),
            (show_groups, _groups_payload(), "groups"),
        )
        for helper, payload, noun in cases:
            push_stub(PushOutcome(outcome="app_not_running"))

            result = await helper(payload=payload)

            assert f"the {noun} have nowhere to appear" in result.message, helper.__name__

    async def test_the_success_sentence_carries_each_kind_s_own_subject(self, push_stub):
        """Both counts per kind, so the subject AND its pluraliser are each tool's own —
        a tier-list success saying "suggested cards" fails here, as does "1 tiers"."""
        cases = (
            (show_suggestions, _payload, ("1 suggested card", "2 suggested cards")),
            (show_swaps, _swaps_payload, ("1 proposed swap", "2 proposed swaps")),
            (show_tier_list, _tier_payload, ("1 tier", "2 tiers")),
            (show_groups, _groups_payload, ("1 group", "2 groups")),
        )
        for helper, build, subjects in cases:
            for items, subject in zip((1, 2), subjects, strict=True):
                push_stub(PushOutcome(outcome="displayed", clients=1))

                result = await helper(payload=build(items=items))

                assert result.message == f"The companion is showing {subject} in 1 tab.", (
                    helper.__name__
                )


class _LiveStub:
    """Stands in for ``live_instance``, answering a chosen record and counting the asks."""

    def __init__(self, record: DiscoveryRecord | None) -> None:
        self.record = record
        self.calls = 0

    async def __call__(self, **kwargs: object) -> DiscoveryRecord | None:
        self.calls += 1
        return self.record


class _HealthStub:
    """Stands in for ``probe_health``, recording the ports it was asked about."""

    def __init__(self, health: HealthResponse | None) -> None:
        self.health = health
        self.ports: list[int] = []

    async def __call__(self, port: int, **kwargs: object) -> HealthResponse | None:
        self.ports.append(port)
        return self.health


_STATUS_TOKEN = "status-token-n3v3rSh0wn"
"""A distinctive credential planted in the stubbed record, so a leak into the result is greppable
(the token must never reach a ``companion_status`` result)."""


@pytest.fixture
def status_stubs(monkeypatch):
    """Install ``live_instance`` / ``probe_health`` stubs for :func:`companion_status` (17.4).

    Returns:
        ``install(record, health)`` -> ``(live_stub, health_stub)``.
    """

    def install(
        record: DiscoveryRecord | None, health: HealthResponse | None
    ) -> tuple[_LiveStub, _HealthStub]:
        live = _LiveStub(record)
        probe = _HealthStub(health)
        monkeypatch.setattr(companion, "_client_live_instance", live)
        monkeypatch.setattr(companion, "_client_probe_health", probe)
        return live, probe

    return install


def _record(port: int = 8765) -> DiscoveryRecord:
    return DiscoveryRecord(port=port, token=_STATUS_TOKEN, instance_id="inst-status")


class TestCompanionStatusIsReadOnlyAndNamesTheNextStep:
    """17.4: the agent's read-only answer — running / URL / tabs / the exact launch command."""

    async def test_not_running_offers_the_launch_command_and_no_url(self, status_stubs):
        live, probe = status_stubs(None, None)

        result = await companion_status()

        assert result.status == "not_running"
        assert result.url is None
        assert result.clients is None
        assert result.launch_command == companion.launch_command()
        assert "isn't running" in result.message
        assert probe.ports == [], "nothing proven live means nothing further is probed"

    async def test_running_with_a_tab_says_there_is_nothing_to_do(self, status_stubs):
        status_stubs(
            _record(8765), HealthResponse(status="ok", instance_id="inst-status", clients=1)
        )

        result = await companion_status()

        assert result.status == "running"
        assert result.url == "http://127.0.0.1:8765"
        assert result.clients == 1
        assert "1 tab open" in result.message
        assert "nothing to do" in result.message

    async def test_running_with_no_tab_points_at_the_url_and_the_launch_command(self, status_stubs):
        status_stubs(
            _record(9000), HealthResponse(status="ok", instance_id="inst-status", clients=0)
        )

        result = await companion_status()

        assert result.status == "running"
        assert result.url == "http://127.0.0.1:9000"
        assert result.clients == 0
        assert "no browser tab is open" in result.message
        assert "launch_command" in result.message
        assert result.launch_command == companion.launch_command()

    async def test_a_companion_that_vanishes_between_probes_is_not_running(self, status_stubs):
        """The second probe is held to the first's proof: no health body, no ``running``."""
        status_stubs(_record(8765), None)

        result = await companion_status()

        assert result.status == "not_running"
        assert result.url is None
        assert result.clients is None
        assert result.launch_command == companion.launch_command()

    async def test_a_foreign_instance_on_the_port_is_not_running(self, status_stubs):
        """A body whose ``instance_id`` is not the proven record's is a different process."""
        status_stubs(
            _record(8765), HealthResponse(status="ok", instance_id="someone-else", clients=1)
        )

        result = await companion_status()

        assert result.status == "not_running"
        assert result.url is None

    async def test_a_negative_count_is_clamped_to_none(self, status_stubs):
        status_stubs(_record(), HealthResponse(status="ok", instance_id="inst-status", clients=-1))

        result = await companion_status()

        assert result.status == "running"
        assert result.clients is None
        assert "-1" not in result.message
        # A malformed count is UNKNOWN, not zero: the message must never claim no tab is open.
        assert "no browser tab is open" not in result.message
        assert "tab count" in result.message

    async def test_an_older_companion_without_the_count_reads_as_count_unknown(self, status_stubs):
        """A ``/health`` body from before 17.4 carries no ``clients``: ``None`` is *unknown*, not
        ``0`` — a tab may already be open, so the message hands over the URL rather than claiming
        nobody is looking (pre-cut R2)."""
        status_stubs(_record(), HealthResponse(status="ok", instance_id="inst-status"))

        result = await companion_status()

        assert result.status == "running"
        assert result.clients is None
        assert "no browser tab is open" not in result.message
        assert "tab count" in result.message
        assert "may already be open" in result.message
        assert result.url is not None and result.url in result.message

    async def test_the_health_probe_asks_the_proven_port(self, status_stubs):
        _, probe = status_stubs(
            _record(4321), HealthResponse(status="ok", instance_id="inst-status", clients=2)
        )

        result = await companion_status()

        assert probe.ports == [4321]
        assert result.clients == 2
        assert "2 tabs open" in result.message

    @pytest.mark.parametrize("clients", [None, 0, 1])
    async def test_the_token_never_appears_in_the_result(self, status_stubs, clients):
        status_stubs(
            _record(), HealthResponse(status="ok", instance_id="inst-status", clients=clients)
        )

        result = await companion_status()

        assert _STATUS_TOKEN not in result.model_dump_json()

    async def test_the_result_carries_exactly_the_five_fields(self, status_stubs):
        status_stubs(None, None)

        result = await companion_status()

        assert set(result.model_dump()) == {"status", "url", "clients", "launch_command", "message"}

    async def test_every_status_fits_the_budget(self, status_stubs):
        for record, health in (
            (None, None),
            (_record(65535), HealthResponse(status="ok", instance_id="inst-status", clients=0)),
            (_record(65535), HealthResponse(status="ok", instance_id="inst-status", clients=12)),
        ):
            status_stubs(record, health)
            result = await companion_status()
            assert len(result.model_dump_json()) <= 400 + len(result.launch_command), (
                result.model_dump_json()
            )

    def test_the_launch_command_uses_the_directory_form_with_open(self):
        """The ``--directory`` form works for a plugin install (deferred-work.md:6516); ``--open``
        is what makes the page appear without a second step."""
        command = companion.launch_command()
        root = companion._INSTALL_ROOT

        assert command == f'uv run --directory "{root}" artificial-planeswalker companion --open'
        assert (root / "pyproject.toml").is_file(), "the root must be the uv project directory"
        assert root == Path(companion.__file__).resolve().parents[3]

    def test_the_status_vocabulary_is_closed(self):
        assert set(get_args(CompanionStatusResult.model_fields["status"].annotation)) == {
            "running",
            "not_running",
            "error",
        }


@pytest.fixture
def stub_server():
    """Yield :meth:`StubFleet.start` and tear down every loopback stub it handed out.

    A four-line fixture over an imported helper, exactly as ``test_client.py``,
    ``test_server.py`` and ``test_deck_changed_wiring.py`` each keep their own: the fixture
    cannot simply be imported, because a module-level ``stub_server`` binding and a test
    parameter of the same name are a redefinition (ruff F811).
    """
    fleet = StubFleet()
    yield fleet.start
    fleet.close_all()


class TestCompanionStatusOverARealSocket:
    """Pre-cut R7: the ``clients`` fold proven against a real health body on a real socket.

    Every test in the class above stubs ``_client_live_instance`` / ``_client_probe_health``, so
    none of them can catch the tool and the client disagreeing about what a ``/health`` body
    means. Here nothing is monkeypatched: a loopback stub serves the JSON a real companion
    would, a hand-planted discovery record points at it, and the tool's real client calls do
    the whole proof — identity match included.
    """

    @pytest.fixture(autouse=True)
    def isolated_data_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        """Point the real client at an empty data dir, and prove it starts empty."""
        data_dir = tmp_path / "companion-data"
        data_dir.mkdir()
        monkeypatch.setenv("PLANESWALKER_DATA_DIR", str(data_dir))
        assert not (data_dir / COMPANION_FILENAME).exists()
        assert read_discovery() is None, (
            "something published a discovery record into the isolated data dir — this test "
            "would be measuring a live companion"
        )
        return data_dir

    async def test_a_real_health_body_with_one_client_reports_the_tab(self, stub_server):
        """``clients: 1`` parsed off the wire — no monkeypatched client functions anywhere."""
        stub = stub_server(body=health_bytes("inst-real-parse", clients=1))
        plant_discovery(port=stub.port, instance_id="inst-real-parse")

        result = await companion_status()

        assert result.status == "running"
        assert result.url == f"http://127.0.0.1:{stub.port}"
        assert result.clients == 1
        assert "1 tab open" in result.message
        assert "nothing to do" in result.message
        assert stub.requests, "the stub was never dialled — this proved nothing"

    async def test_a_real_health_body_without_the_count_reads_as_unknown(self, stub_server):
        """The unknown arm, off the wire: an older companion's body carries no ``clients``."""
        stub = stub_server(body=health_bytes("inst-real-parse"))
        plant_discovery(port=stub.port, instance_id="inst-real-parse")

        result = await companion_status()

        assert result.status == "running"
        assert result.clients is None
        assert "no browser tab is open" not in result.message
        assert "tab count" in result.message
        assert stub.requests, "the stub was never dialled — this proved nothing"
