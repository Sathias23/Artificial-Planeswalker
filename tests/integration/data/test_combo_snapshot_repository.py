"""Integration tests for ComboSnapshotRepository (Story 6.3).

Seeds the snapshot tables directly through the ORM models (the importer pipeline is
already e2e-tested in 6.2) and proves the read path offline: in-memory SQLite, no live
DB, no network.
"""

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.database import create_engine, create_session_factory, init_database
from src.data.models.combo import (
    ComboSnapshotMetaModel,
    ComboVariantModel,
    ComboVariantPieceModel,
)
from src.data.repositories.combo_snapshot import ComboSnapshotRepository
from src.data.schemas.combo import name_keys

pytestmark = pytest.mark.integration


@pytest.fixture
async def in_memory_engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_engine("sqlite+aiosqlite:///:memory:")
    await init_database(engine)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(in_memory_engine):
    """Create a test session."""
    session_factory = create_session_factory(in_memory_engine)
    async with session_factory() as session:
        yield session


@pytest.fixture
async def repo(session: AsyncSession):
    """Create a ComboSnapshotRepository instance."""
    return ComboSnapshotRepository(session)


def _variant(
    spellbook_id: str,
    cards: list[str],
    *,
    commander_required: bool = False,
    bracket_tag: str = "POWERFUL",
    produces: list[str] | None = None,
    popularity: int | None = None,
) -> tuple[ComboVariantModel, list[ComboVariantPieceModel]]:
    """Build one variant row plus its piece-index rows via the shared ``name_keys``."""
    variant = ComboVariantModel(
        spellbook_id=spellbook_id,
        commander_required=commander_required,
        bracket_tag=bracket_tag,
        popularity=popularity,
    )
    variant.cards_list = cards
    variant.produces_list = produces or ["Infinite mana"]
    keys = {key for name in cards for key in name_keys(name)}
    pieces = [
        ComboVariantPieceModel(spellbook_id=spellbook_id, name_key=key) for key in sorted(keys)
    ]
    return variant, pieces


@pytest.fixture
async def seeded_snapshot(session: AsyncSession):
    """Seed a small snapshot: meta row + three variants with piece-index rows.

    - ``1-1``: duplicate-piece variant (multiplicity-inclusive ``cards``).
    - ``2-2``: two-piece variant stored in non-sorted order, ``popularity`` set.
    - ``3-3``: DFC piece indexed under both of its ``name_keys``.
    - ``9-9``: zero-overlap decoy — its pieces are never queried.
    """
    meta = ComboSnapshotMetaModel(
        imported_at="2026-07-16T09:07:00+00:00",
        export_timestamp="2026-07-16T07:28:23+00:00",
        export_version="5.6.0",
        variant_count=4,
    )
    session.add(meta)

    for variant, pieces in (
        _variant(
            "1-1",
            ["Basalt Monolith", "Basalt Monolith"],
            produces=["Infinite colorless mana"],
        ),
        _variant(
            "2-2",
            ["Zealous Conscripts", "Kiki-Jiki, Mirror Breaker"],
            commander_required=True,
            bracket_tag="RUTHLESS",
            produces=["Infinite hasty tokens"],
            popularity=1234,
        ),
        _variant("3-3", ["Alive // Well"], bracket_tag="ODDBALL"),
        _variant("9-9", ["Thassa's Oracle", "Demonic Consultation"], bracket_tag="SPICY"),
    ):
        session.add(variant)
        session.add_all(pieces)

    await session.commit()


class TestSchemaInvariants:
    """DDL-level guarantees mirroring the ``ComboRecord`` application invariants."""

    async def test_null_cards_rejected_at_schema_level(self, session: AsyncSession):
        """``cards`` is semantically required (``ComboRecord`` min_length=1): a row
        written without it must fail loudly AT THE WRITE SITE (IntegrityError on
        flush), not later as a surprising ValidationError in the repository."""
        variant = ComboVariantModel(
            spellbook_id="null-cards",
            commander_required=False,
            bracket_tag="POWERFUL",
            popularity=None,
        )
        session.add(variant)
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()


class TestSnapshotIsAvailable:
    """The edge's ``combo_data_unavailable`` probe (AD-6)."""

    async def test_seeded_snapshot_is_available(self, repo, seeded_snapshot):
        assert await repo.snapshot_is_available() is True

    async def test_initialized_but_empty_tables_read_as_unavailable(self, repo):
        assert await repo.snapshot_is_available() is False


class TestGetSnapshotState:
    """The merged single-read probe consumed by the edge's ``_provision_combos``.

    One consistent read: ``available=True`` structurally implies the vintage row is
    present (both derive from the same meta fetch), so the edge can never emit
    ``combo_data_unavailable=False`` alongside a ``None`` vintage.
    """

    async def test_seeded_returns_vintage_and_available(self, repo, seeded_snapshot):
        vintage, available = await repo.get_snapshot_state()
        assert available is True
        assert vintage is not None
        assert vintage.export_version == "5.6.0"

    async def test_meta_without_variants_carries_vintage_but_unavailable(self, repo, session):
        session.add(
            ComboSnapshotMetaModel(
                imported_at="2026-07-16T09:07:00+00:00",
                export_timestamp="2026-07-16T07:28:23+00:00",
                export_version="5.6.0",
                variant_count=0,
            )
        )
        await session.commit()

        vintage, available = await repo.get_snapshot_state()
        assert available is False
        assert vintage is not None

    async def test_empty_tables_return_none_and_unavailable(self, repo):
        assert await repo.get_snapshot_state() == (None, False)


class TestGetMetadata:
    """The ``data_vintage`` source (AD-5/AD-7)."""

    async def test_seeded_metadata_round_trips_exactly(self, repo, seeded_snapshot):
        meta = await repo.get_metadata()
        assert meta is not None
        assert meta.imported_at == "2026-07-16T09:07:00+00:00"
        assert meta.export_timestamp == "2026-07-16T07:28:23+00:00"
        assert meta.export_version == "5.6.0"
        assert meta.variant_count == 4

    async def test_empty_table_returns_none(self, repo):
        assert await repo.get_metadata() is None


class TestGetVariantsForNames:
    """The relevance filter — shared ``name_keys`` over the piece index (AC 3)."""

    async def test_overlapping_name_returns_record_with_bucket_none(self, repo, seeded_snapshot):
        records = await repo.get_variants_for_names(["Basalt Monolith"])
        assert [record.spellbook_id for record in records] == ["1-1"]
        assert records[0].bucket is None

    async def test_multiplicity_inclusive_cards_survive_round_trip(self, repo, seeded_snapshot):
        (record,) = await repo.get_variants_for_names(["Basalt Monolith"])
        assert record.cards == ("Basalt Monolith", "Basalt Monolith")

    async def test_cards_and_produces_are_sorted_tuples(self, repo, seeded_snapshot):
        (record,) = await repo.get_variants_for_names(["Zealous Conscripts"])
        assert record.cards == ("Kiki-Jiki, Mirror Breaker", "Zealous Conscripts")
        assert record.produces == ("Infinite hasty tokens",)

    async def test_stored_fields_are_preserved(self, repo, seeded_snapshot):
        (record,) = await repo.get_variants_for_names(["Kiki-Jiki, Mirror Breaker"])
        assert record.spellbook_id == "2-2"
        assert record.commander_required is True
        assert record.bracket_tag == "RUTHLESS"
        assert record.popularity == 1234

    async def test_zero_overlap_variant_is_not_returned(self, repo, seeded_snapshot):
        records = await repo.get_variants_for_names(["Lightning Bolt"])
        assert records == ()

    async def test_results_ordered_by_spellbook_id(self, repo, seeded_snapshot):
        records = await repo.get_variants_for_names(["Zealous Conscripts", "Basalt Monolith"])
        assert [record.spellbook_id for record in records] == ["1-1", "2-2"]

    async def test_full_dfc_deck_name_matches_front_face_piece_row(self, repo, seeded_snapshot):
        records = await repo.get_variants_for_names(["Alive // Well"])
        assert [record.spellbook_id for record in records] == ["3-3"]

    async def test_front_face_only_deck_name_matches_dfc_piece(self, repo, seeded_snapshot):
        records = await repo.get_variants_for_names(["Alive"])
        assert [record.spellbook_id for record in records] == ["3-3"]

    async def test_empty_names_returns_empty_tuple(self, repo, seeded_snapshot):
        assert await repo.get_variants_for_names([]) == ()

    async def test_corrupt_bracket_tag_raises_validation_error(
        self, repo, session, seeded_snapshot
    ):
        variant, pieces = _variant("5-5", ["Dark Ritual"], bracket_tag="BOGUS")
        session.add(variant)
        session.add_all(pieces)
        await session.commit()

        with pytest.raises(ValidationError):
            await repo.get_variants_for_names(["Dark Ritual"])


class TestMissingTables:
    """A pre-6.2 ``cards.db`` that never created the snapshot tables (AC 5)."""

    @pytest.fixture
    async def bare_repo(self):
        """A repository over an engine that never ran ``init_database``."""
        engine = create_engine("sqlite+aiosqlite:///:memory:")
        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            yield ComboSnapshotRepository(session)
        await engine.dispose()

    async def test_snapshot_is_available_returns_false(self, bare_repo):
        assert await bare_repo.snapshot_is_available() is False

    async def test_get_metadata_returns_none(self, bare_repo):
        assert await bare_repo.get_metadata() is None

    async def test_get_snapshot_state_returns_none_and_unavailable(self, bare_repo):
        assert await bare_repo.get_snapshot_state() == (None, False)

    async def test_get_variants_for_names_returns_empty(self, bare_repo):
        assert await bare_repo.get_variants_for_names(["Basalt Monolith"]) == ()
