"""Unit tests for the pure oracle-identity reconcile decision logic (no DB)."""

from src.data.importers.aggregate import OracleAggregate
from src.data.importers.importer import ImportStatistics, ReconcileStatistics
from src.data.importers.scryfall import plan_identity_dedup


def _aggregate(canonical_id: str, games: set[str] | None = None) -> OracleAggregate:
    return OracleAggregate(games=games or set(), canonical_id=canonical_id)


def test_plan_remaps_stale_rows_to_canonical():
    """Duplicate rows with the canonical present remap every non-canonical id."""
    aggregates = {"oracle-1": _aggregate("new-id")}
    rows = {"oracle-1": ["old-id", "new-id"]}

    remap, skipped = plan_identity_dedup(aggregates, rows)

    assert remap == {"old-id": "new-id"}
    assert skipped == set()


def test_plan_remaps_multiple_stale_rows():
    """Three printings collapse onto the single canonical survivor."""
    aggregates = {"oracle-1": _aggregate("c")}
    rows = {"oracle-1": ["a", "b", "c"]}

    remap, skipped = plan_identity_dedup(aggregates, rows)

    assert remap == {"a": "c", "b": "c"}
    assert skipped == set()


def test_plan_skips_identity_when_canonical_absent():
    """Canonical row missing from the DB (rejected printing): touch nothing, count it."""
    aggregates = {"oracle-1": _aggregate("rejected-id")}
    rows = {"oracle-1": ["old-id", "older-id"]}

    remap, skipped = plan_identity_dedup(aggregates, rows)

    assert remap == {}
    assert skipped == {"oracle-1"}


def test_plan_leaves_out_of_snapshot_identities_untouched():
    """Rows whose oracle id has no aggregate are neither remapped nor counted."""
    aggregates = {"oracle-1": _aggregate("keep-id")}
    rows = {"oracle-1": ["keep-id"], "oracle-legacy": ["ancient-a", "ancient-b"]}

    remap, skipped = plan_identity_dedup(aggregates, rows)

    assert remap == {}
    assert skipped == set()


def test_plan_single_canonical_row_is_a_noop():
    """An already-clean identity (one row, and it is the canonical) plans no work."""
    aggregates = {"oracle-1": _aggregate("only-id")}
    rows = {"oracle-1": ["only-id"]}

    remap, skipped = plan_identity_dedup(aggregates, rows)

    assert remap == {}
    assert skipped == set()


def test_plan_ignores_aggregate_without_canonical_id():
    """An aggregate carrying no canonical id (defensive) plans no deletes and no skip."""
    aggregates = {"oracle-1": _aggregate("")}
    rows = {"oracle-1": ["a", "b"]}

    remap, skipped = plan_identity_dedup(aggregates, rows)

    assert remap == {}
    assert skipped == set()


def test_import_statistics_defaults_carry_empty_diagnostics():
    """Fresh statistics expose empty rejects and all-zero reconcile counters."""
    stats = ImportStatistics()

    assert stats.rejects == []
    assert stats.reconcile == ReconcileStatistics()
    assert stats.reconcile.stale_remaining == 0
    assert stats.reconcile.stale_sample == ()
    assert stats.reconcile.failed is False
