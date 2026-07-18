"""Benchmark validation for the Story 5.9 ``score()`` entry point (NFR6, AC6/AC7).

The deferred Story 5.1 resolution gate: every committed benchmark card name is resolved
against the LOCAL Scryfall snapshot (unfiltered ``find_by_name_exact`` — a format filter
would hide non-legal printings as not-found), the real ``score()`` runs per entry, and
the 5.1 categorical expectations are asserted under the decide-once tolerance policy
(:func:`_assert_expected_outcome`).

Environment policy (the RAG-eval precedent — integration tests may depend on
operator-local data but must skip LOUDLY, never fail cryptically):

- no/uninitialized central ``cards.db`` (fresh checkout, CI) → the whole module SKIPS;
- an UNRESOLVED name → hard ``pytest.fail`` naming the entry + names (5.1 guaranteed
  resolvability, so a miss is a fixture regression, not an environment gap);
- a resolved card with ``game_changer is None`` → per-entry skip for COMMANDER entries
  only, citing the backfill re-import (the AD-4 window; the Atraxa Bracket-3 expectation
  needs real GC data). Standard scores are ``heuristic_only`` and never read
  ``game_changer``, so their FR20 exact-tier gate stays live even during a backfill window.

Combo variants are hand-built fixtures verified against the committed decklists (Epic
6's snapshot does not exist yet — the epic-2 overview mandates fixture-validated, no
live dependency). Non-cEDH and Standard entries pass ``variants=()``, which also proves
empty combo data scores without crashing (NFR3 core side).
"""

import asyncio
from dataclasses import dataclass
from typing import Final

import pytest

from src.data.database import create_engine, create_session_factory, is_database_initialized
from src.data.repositories.card import CardRepository
from src.data.schemas.combo import ComboRecord
from src.data.schemas.deck import DeckCard
from src.logic.assessment import (
    BRACKET_FLOOR_MAX,
    COMMANDER_PROFILE,
    STANDARD_PROFILE,
    TIER_LABELS,
    CoreAssessment,
    score,
)
from tests.fixtures.assessment import make_combo_record, make_deck_card
from tests.fixtures.benchmark_decks import BenchmarkEntry, load_benchmark

pytestmark = pytest.mark.integration

#: Hand-built cEDH combo-variant fixtures (AC6), keyed by benchmark entry. Every piece
#: is verified present in the committed decklist (add the variant to match the list,
#: never the other way around); ``produces`` contains "infinite" (``combo_type`` keys on
#: that substring) and piece mana values are cheap enough that
#: ``earliest_turn_estimate <= CEDH_COMBO_TURN_MAX`` (4). The ids are explicit fixture
#: ids, not real Spellbook variant ids — Epic 6 delivers those.
_CEDH_VARIANTS: Final[dict[str, tuple[ComboRecord, ...]]] = {
    # Dramatic Reversal + Isochron Scepter ("Dramatic Scepter"): both pieces in the
    # committed 4c Blue Farm list, cmc 2 + 2 -> earliest turn 3.
    "cedh_tymna_thrasios": (
        make_combo_record(
            spellbook_id="fixture-dramatic-scepter",
            cards=("Dramatic Reversal", "Isochron Scepter"),
            commander_required=False,
            bracket_tag="RUTHLESS",
            produces=("Infinite mana", "Infinite storm count"),
        ),
    ),
    # Kinnan (command zone) + Basalt Monolith (in-deck): commander_required, the
    # command zone supplies Kinnan; cmc 2 + 3 -> earliest turn 3.
    "cedh_kinnan_bonder_prodigy": (
        make_combo_record(
            spellbook_id="fixture-kinnan-basalt",
            cards=("Basalt Monolith", "Kinnan, Bonder Prodigy"),
            commander_required=True,
            bracket_tag="RUTHLESS",
            produces=("Infinite colorless mana",),
        ),
    ),
}

_ENTRIES: Final[dict[str, BenchmarkEntry]] = {entry.key: entry for entry in load_benchmark()}


@dataclass(frozen=True, slots=True)
class _ResolvedEntry:
    """One benchmark entry resolved against the local snapshot.

    Attributes:
        deck_cards: ``make_deck_card`` rows for ALL parsed cards — commander rows are
            INCLUDED in ``deck_cards`` (the benchmark harness's decide-once convention;
            the matcher additionally credits command-zone availability itself).
        commanders: The ``is_commander`` card names, in decklist order.
        missing: Names ``find_by_name_exact`` could not resolve (fixture regression).
        unknown_gc: Resolved names whose ``game_changer is None`` (AD-4 window).
    """

    deck_cards: tuple[DeckCard, ...]
    commanders: tuple[str, ...]
    missing: tuple[str, ...]
    unknown_gc: tuple[str, ...]


async def _resolve_all() -> dict[str, _ResolvedEntry] | None:
    """Resolve every benchmark entry via the central DB; ``None`` if uninitialized."""
    engine = create_engine()
    try:
        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            if not await is_database_initialized(session):
                return None
            repo = CardRepository(session)
            resolved: dict[str, _ResolvedEntry] = {}
            for entry in _ENTRIES.values():
                deck_cards: list[DeckCard] = []
                missing: list[str] = []
                unknown_gc: list[str] = []
                for bench_card in entry.cards:
                    # Unfiltered on purpose: a format filter hides non-legal cards
                    # as not-found (the MTGA legality-lookup lesson).
                    card = await repo.find_by_name_exact(bench_card.name)
                    if card is None:
                        missing.append(bench_card.name)
                        continue
                    if card.game_changer is None:
                        unknown_gc.append(bench_card.name)
                    deck_cards.append(make_deck_card(card, quantity=bench_card.quantity))
                resolved[entry.key] = _ResolvedEntry(
                    deck_cards=tuple(deck_cards),
                    commanders=tuple(
                        bench_card.name for bench_card in entry.cards if bench_card.is_commander
                    ),
                    missing=tuple(missing),
                    unknown_gc=tuple(unknown_gc),
                )
            return resolved
    finally:
        await engine.dispose()


@pytest.fixture(scope="module")
def resolved_entries() -> dict[str, _ResolvedEntry]:
    """Module-scoped central-DB resolution pass (one engine, one sweep, then pure tests).

    Synchronous on purpose: resolution runs once under ``asyncio.run`` and yields plain
    Pydantic objects, so the per-entry tests stay pure/sync and no module-scoped event
    loop is needed.
    """
    resolved = asyncio.run(_resolve_all())
    if resolved is None:
        pytest.skip("cards.db not initialized — run initialize_database (fresh checkout has no DB)")
    return resolved


@pytest.fixture(params=sorted(_ENTRIES), ids=sorted(_ENTRIES))
def entry(request: pytest.FixtureRequest) -> BenchmarkEntry:
    """Parametrize over every benchmark entry by key."""
    return _ENTRIES[str(request.param)]


def _assert_expected_outcome(entry: BenchmarkEntry, assessment: CoreAssessment) -> None:
    """Assert one entry's categorical expectations — the 5.1 tolerance contract, once.

    Restates the policy documented in ``tests/fixtures/benchmark_decks.py`` (module
    docstring + Story 5.1 tolerance notes) so re-cuts cannot silently drift it:

    - precons (``expected_bracket=2``): floor within ``[expected, expected + 1]``
      ("bracket up when in doubt");
    - the upgraded middle anchor (3): floor within ``[3, 4]``;
    - cEDH entries (4): floor ``== BRACKET_FLOOR_MAX`` (4 — Bracket 5 is never asserted
      and cannot be emitted) AND ``cedh_candidate is True``;
    - Commander tier labels: within +/- 1 band index of expected (informative);
    - Standard anchors: ``bracket_floor is None``, ``cedh_candidate is False``, tier
      label EXACT — the FR20 acceptance signal the thresholds are tuned against.
    """
    if entry.format == "standard":
        assert assessment.bracket_floor is None, (
            f"{entry.key}: Standard must carry bracket_floor=None, got {assessment.bracket_floor!r}"
        )
        assert assessment.cedh_candidate is False, (
            f"{entry.key}: Standard must never flag cedh_candidate"
        )
        assert assessment.tier == entry.expected_tier_label, (
            f"{entry.key}: tier {assessment.tier!r} != expected "
            f"{entry.expected_tier_label!r} EXACT (FR20; for_format_score="
            f"{assessment.for_format_score}, vector={assessment.vector})"
        )
        return

    expected_bracket = entry.expected_bracket
    assert expected_bracket is not None, f"{entry.key}: Commander entry missing expected_bracket"
    if entry.expected_cedh_candidate:
        assert assessment.bracket_floor == BRACKET_FLOOR_MAX, (
            f"{entry.key}: cEDH entry must floor at exactly {BRACKET_FLOOR_MAX}, "
            f"got {assessment.bracket_floor!r}"
        )
        assert assessment.cedh_candidate is True, (
            f"{entry.key}: cEDH entry must flag cedh_candidate "
            f"(floor={assessment.bracket_floor}, vector={assessment.vector})"
        )
    else:
        assert assessment.bracket_floor in {expected_bracket, expected_bracket + 1}, (
            f"{entry.key}: floor {assessment.bracket_floor!r} outside "
            f"[{expected_bracket}, {expected_bracket + 1}] (bracket up when in doubt)"
        )
        assert assessment.cedh_candidate is False, (
            f"{entry.key}: non-cEDH Commander entry must not flag cedh_candidate"
        )

    expected_band = TIER_LABELS.index(entry.expected_tier_label)  # type: ignore[arg-type]
    actual_band = TIER_LABELS.index(assessment.tier)
    assert abs(actual_band - expected_band) <= 1, (
        f"{entry.key}: tier {assessment.tier!r} (band {actual_band}) not within +/-1 of "
        f"expected {entry.expected_tier_label!r} (band {expected_band}; "
        f"for_format_score={assessment.for_format_score}, vector={assessment.vector})"
    )


class TestBenchmark:
    """AC7: every entry through the REAL score() against the local snapshot."""

    def test_entry_resolves_and_meets_expected_outcome(
        self, entry: BenchmarkEntry, resolved_entries: dict[str, _ResolvedEntry]
    ) -> None:
        resolved = resolved_entries[entry.key]
        if resolved.missing:
            pytest.fail(
                f"{entry.key}: unresolved card names {sorted(resolved.missing)} — 5.1 "
                f"guaranteed resolvability, so this is a fixture regression, not a skip"
            )
        # GC data feeds ONLY the commander bracket path (heuristic_only Standard scores
        # never read game_changer), so an open backfill window must not skip the Standard
        # FR20 exact-tier gate for an unrelated reason (code review 2026-07-15).
        if entry.format == "commander" and resolved.unknown_gc:
            pytest.skip(
                f"{entry.key}: game_changer is None for {len(resolved.unknown_gc)} cards "
                f"(e.g. {sorted(resolved.unknown_gc)[:5]}) — run the game_changer backfill "
                f"re-import (scripts/import_scryfall_data.py) to close the AD-4 window"
            )

        profile = COMMANDER_PROFILE if entry.format == "commander" else STANDARD_PROFILE
        variants = _CEDH_VARIANTS.get(entry.key, ())
        first = score(
            resolved.deck_cards,
            commanders=resolved.commanders,
            variants=variants,
            profile=profile,
        )
        second = score(
            resolved.deck_cards,
            commanders=resolved.commanders,
            variants=variants,
            profile=profile,
        )
        assert first == second, (
            f"{entry.key}: two consecutive score() calls must return equal objects "
            f"(determinism on real data)"
        )
        _assert_expected_outcome(entry, first)


class TestComboFixtureIntegrity:
    """AC6: every hand-built variant's pieces really are in its committed decklist."""

    @pytest.mark.parametrize("key", sorted(_CEDH_VARIANTS), ids=sorted(_CEDH_VARIANTS))
    def test_variant_pieces_present_in_decklist(self, key: str) -> None:
        entry = _ENTRIES[key]
        deck_names = {card.name.lower() for card in entry.cards}
        commander_names = {card.name.lower() for card in entry.cards if card.is_commander}
        for variant in _CEDH_VARIANTS[key]:
            for piece in variant.cards:
                assert piece.lower() in deck_names, (
                    f"{key}: combo fixture piece {piece!r} is not in the committed "
                    f"decklist — add the variant to match the list, never the reverse"
                )
            if variant.commander_required:
                assert any(piece.lower() in commander_names for piece in variant.cards), (
                    f"{key}: commander_required variant must name a commander piece"
                )
