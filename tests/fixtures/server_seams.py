"""Stand-ins installed at the MCP server's seams, shared by every suite that drives the tools.

Two suites kept a private copy of the ``deck_changed`` notifier stand-in, and
``test_mcp_tools.py`` imported the fake Scryfall importer from another test module. Both live
here now, so a test imports a fixture module rather than a test module.
"""

from collections.abc import Awaitable, Callable

from src.companion.client import PushOutcome
from src.data.importers.importer import ImportStatistics
from src.data.models.card import CardModel


class RecordingNotifier:
    """Stands in for c7-1's notifier at server.py's import seam, recording every emit.

    Recording the deck ids rather than a call count is deliberate: "nothing was emitted" and "the
    wrong deck was announced" are different failures, and only a recorded argument list tells them
    apart. The optional ``observer`` runs *at notify time*; the after-commit proofs use it to read
    the database through their own session while the emit is in flight.

    Args:
        outcome: What every call returns; a ``displayed`` push to one client by default.
        observer: Awaited with the deck id on every call; its results land in
            :attr:`observations`.
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


def importer_card(card_id: str, name: str) -> CardModel:
    """Build the minimal red instant the fake importer seeds (``keywords`` an empty list)."""
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
        keywords=[],  # real Scryfall data uses an empty array, not null, for no keywords
        legalities={"standard": "legal"},
    )


async def fake_importer(session, *, bulk_type: str = "oracle_cards") -> ImportStatistics:
    """Stand-in for the Scryfall importer: inserts Lightning Bolt and Counterspell, no network."""
    session.add(importer_card("c-1", "Lightning Bolt"))
    session.add(importer_card("c-2", "Counterspell"))
    await session.commit()
    stats = ImportStatistics()
    stats.total_processed = 2
    stats.total_inserted = 2
    return stats
