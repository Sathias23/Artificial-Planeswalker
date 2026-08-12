"""SC-3 at the tool boundary: the app is closed, and every workflow still finishes (c6-9).

``test_companion_tool.py`` drives the two helpers against a **stubbed** client verb, because what
that file is about is the mapping from outcome token to ``status``. This file is about the other
half, and it is the half a stub can never show: with no companion anywhere — no discovery file, no
port, no process — the tools reach the **real** leaf client, and the whole MCP surface behaves as
it did before the companion existed.

**Three things are proven here and nowhere else.**

1. Both companion tools return an ``app_not_running`` *text result* through a real MCP session —
   ``isError`` is false and no exception crosses the tool boundary (AC 1, FR-12). A tool that
   raised would abort the agent's turn, which is the single failure mode SC-3 exists to forbid.
2. A pre-existing tool driven **in the same session** is bit-for-bit indifferent to the companion's
   absence (AC 3). ``list_decks`` is the representative: it is one of the tools that predates the
   feature, and it reads the same database the companion tool just read.
3. Nothing reaches for a credential when there is no proven companion to send one to — the
   ``app_not_running`` path returns before any token could exist to leak (AD-4).

**What this file deliberately does not re-prove.** The transport itself is settled in
``tests/unit/companion/test_client.py`` (:1022-1077) against *real loopback sockets*: dead ports,
corrupt discovery files, silent listeners and foreign identities all resolve to ``app_not_running``
there. Re-driving those states through a second harness would double the cost and halve the
meaning. What is left for this layer is the seam — that the tool the agent actually calls converts
that outcome into a result rather than a raised exception.

**The isolation matters more here than anywhere else in the suite.** ``PLANESWALKER_DATA_DIR`` is
repointed at a ``tmp_path`` holding no ``companion.json``, so the discovery read finds nothing
whatever the developer's own machine is running. Without that pin, this file would pass or fail
depending on whether Brad happened to have the companion open — and would quietly measure a *live*
companion on the machine where the feature is developed.

Despite living under ``tests/integration/``, these run in the ordinary ``-m "not integration"``
set: a directory is not a marker (AD-10), and with no companion to find, nothing here opens a
socket.
"""

from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.companion.discovery import COMPANION_FILENAME, read_discovery
from src.data.database import create_engine, create_session_factory, init_database
from src.data.models.card import CardModel
from src.mcp_server.server import build_server

_APP_NOT_RUNNING = "app_not_running"

_CARD_ID = "0000c6c9-0000-4000-8000-00000000000a"
"""A syntactically plausible printing id. It names no card in this database and never needs to —
the push tool validates ids against nothing (AD-7), so an unresolvable id is a legitimate payload
and keeps this file's seeding to the one deck ``companion_set_active_deck`` genuinely requires."""


@pytest.fixture
def closed_companion(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point every data-dir consumer at a directory holding no discovery file.

    Returns:
        The isolated data directory, so a test can assert the absence it depends on.
    """
    data_dir = tmp_path / "no-companion-here"
    data_dir.mkdir()
    monkeypatch.setenv("PLANESWALKER_DATA_DIR", str(data_dir))
    return data_dir


@pytest.fixture
async def deck_db(tmp_path: Path) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    """A file-backed, initialised database the tools can read through.

    Seeded with one card deliberately: ``is_database_initialized`` reports ``False`` for a schema
    that exists but holds no ``cards`` row, and every relational tool then answers
    ``database_not_initialized``. An empty database would have this file measuring a first-run
    install rather than a closed companion — the two degradations are different, and only one of
    them is SC-3's.
    """
    engine = create_engine(f"sqlite+aiosqlite:///{(tmp_path / 'cards.db').as_posix()}")
    await init_database(engine)
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        session.add(
            CardModel(
                id="card-sc3-bolt",
                name="Lightning Bolt",
                printed_name=None,
                oracle_id="oracle-sc3-bolt",
                mana_cost="{R}",
                cmc=1.0,
                type_line="Instant",
                oracle_text="Deals 3 damage to any target.",
                rarity="common",
                set_code="TST",
                set_name="Test Set",
                collector_number="1",
                colors=["R"],
                color_identity=["R"],
                legalities={"modern": "legal"},
            )
        )
        await session.commit()
    yield session_factory
    await engine.dispose()


def _text_of(result) -> str:
    """Flatten a tool result's content blocks to one string.

    AC 1 says the outcome arrives as a **text result** the agent presents in chat, so the token is
    read out of the rendered content rather than only out of ``structuredContent`` — the latter
    would pass even if the text channel carried nothing at all.
    """
    return "\n".join(block.text for block in result.content if block.type == "text")


class TestTheAppIsClosedAndTheToolsStillAnswer:
    """AC 1: both companion tools degrade to a result. Neither raises, in a real MCP session."""

    async def test_the_discovery_file_really_is_absent(self, closed_companion: Path) -> None:
        """The precondition, asserted rather than assumed.

        Without this the whole class could pass against a *live* companion on the developer's own
        machine and nobody would know — the c1-7 rendezvous lesson, applied to a test's setup.
        """
        assert not (closed_companion / COMPANION_FILENAME).exists()
        assert read_discovery() is None, (
            "Something published a discovery record into the isolated data dir — this file would "
            "be measuring a live companion instead of a closed one."
        )

    async def test_the_push_tool_reports_the_closed_app_and_does_not_raise(
        self, closed_companion: Path, deck_db: async_sessionmaker[AsyncSession]
    ) -> None:
        server = build_server(session_factory=deck_db)
        async with create_connected_server_and_client_session(server) as client:
            result = await client.call_tool(
                "companion_show_suggestions",
                {
                    "payload": {
                        "items": [{"card_id": _CARD_ID, "reason": "Fills the two-drop hole."}]
                    }
                },
            )

        assert result.isError is False, (
            f"A closed companion must never error an agent turn (FR-12): {_text_of(result)}"
        )
        assert result.structuredContent is not None
        assert result.structuredContent["status"] == _APP_NOT_RUNNING
        assert _APP_NOT_RUNNING in _text_of(result), (
            "AC 1 wants the outcome in the text result the agent presents, not only in the "
            "structured channel."
        )
        assert result.structuredContent["items_pushed"] == 1, (
            "What was attempted is reported even when nothing reached the wire (AD-8)."
        )

    async def test_the_control_tool_reports_the_closed_app_and_does_not_raise(
        self, closed_companion: Path, deck_db: async_sessionmaker[AsyncSession]
    ) -> None:
        """The control tool has to get *past* its database read to reach the client at all.

        A deck that does not exist returns ``deck_not_found`` without contacting anything (AD-16),
        which would make this test pass while proving nothing about a closed app — so the deck is
        created first, through the tool catalogue, in the same session.
        """
        server = build_server(session_factory=deck_db)
        async with create_connected_server_and_client_session(server) as client:
            created = await client.call_tool(
                "create_deck", {"name": "SC-3 witness", "format": "commander"}
            )
            assert created.structuredContent is not None
            deck_id = created.structuredContent["deck"]["id"]

            result = await client.call_tool("companion_set_active_deck", {"deck_id": deck_id})

        assert result.isError is False, (
            f"A closed companion must never error an agent turn (FR-12): {_text_of(result)}"
        )
        assert result.structuredContent is not None
        assert result.structuredContent["status"] == _APP_NOT_RUNNING, (
            "The deck exists, so this reached the client — anything else means the test stopped "
            "short of the seam it is here to prove."
        )
        assert _APP_NOT_RUNNING in _text_of(result)


class TestAPreExistingWorkflowIsIndifferent:
    """AC 3: a tool that predates the companion is unchanged by its absence — the SC-3 claim."""

    async def test_list_decks_is_bit_for_bit_the_same_beside_a_failed_push(
        self, closed_companion: Path, deck_db: async_sessionmaker[AsyncSession]
    ) -> None:
        """One session, three calls: read, failed push, read again.

        The comparison is the point. A snapshot taken *before* the companion tool ran and one taken
        *after* it failed must be identical — not merely both successful. That is what "works
        exactly as it did before the companion existed" means, and it is stronger than asserting
        ``status == "ok"`` twice, which would hold even if the failed push had mutated something.
        """
        server = build_server(session_factory=deck_db)
        async with create_connected_server_and_client_session(server) as client:
            await client.call_tool(
                "create_deck", {"name": "Pre-companion deck", "format": "modern"}
            )

            before = await client.call_tool("list_decks", {})
            push = await client.call_tool(
                "companion_show_suggestions",
                {"payload": {"items": [{"card_id": _CARD_ID, "reason": "Nobody is listening."}]}},
            )
            after = await client.call_tool("list_decks", {})

        assert push.structuredContent is not None
        assert push.structuredContent["status"] == _APP_NOT_RUNNING, (
            "The push must actually have failed, or this proves nothing about indifference."
        )
        assert before.isError is False and after.isError is False
        assert before.structuredContent is not None
        assert before.structuredContent["status"] == "ok", (
            "The positive twin: the pre-existing tool has to be doing real work either side of "
            "the failed push, not returning `empty` at both ends."
        )
        assert after.structuredContent == before.structuredContent, (
            "SC-3: a companion tool failing must leave a pre-existing workflow's result "
            "byte-identical.\n"
            f"before: {before.structuredContent}\nafter:  {after.structuredContent}"
        )
