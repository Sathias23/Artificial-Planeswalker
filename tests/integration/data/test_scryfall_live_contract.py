"""The live-contract canary: does Scryfall still serve what the importer reads?

**Why this file exists.** On 2026-08-02 Scryfall replaced ``download_uri`` with
``jsonl_download_uri`` and ``size`` with ``compressed_size``, and changed the payload from a
top-level JSON array to gzip'd newline-delimited JSON. Every data path in the product died at once,
on a released version — and the entire 2,472-test suite stayed green, because **every test that
touches the importer monkeypatches** :func:`~src.data.importers.scryfall_api.fetch_bulk_data_list`.
Nothing had ever called ``api.scryfall.com/bulk-data``. The contract was asserted only against our
own fixture of it.

**What it asserts, and what it deliberately does not.** It reads the metadata endpoint only — a
single small JSON document — and checks that the fields the importer depends on are present and
usable. It does **not** download a bulk file: the point is an early warning, not a rehearsal, and
the smallest bulk file is tens of megabytes.

**Where it runs.** Marked ``integration``, because the push-triggered ``quality`` jobs run
``pytest -m "not integration"`` and a network dependency there would trade a real failure mode for
a flaky one. (CI's one integration-running job, ``companion-integration``, is scoped by path to
``tests/integration/companion/`` and so never collects this file — which is what keeps that job's
"no network beyond loopback" property true.) A third-party contract changes on the vendor's
release schedule, not on ours, so a push trigger is the wrong axis entirely — the scheduled
``live-contract`` workflow is what makes this fire. Run it by hand with::

    uv run pytest tests/integration/data/test_scryfall_live_contract.py -m integration
"""

import pytest

from src.data.importers.scryfall import (
    _DOWNLOAD_URI_KEYS,
    _SIZE_KEYS,
    _first_present,
    _resolve_download_uri,
    _validate_download_uri,
)
from src.data.importers.scryfall_api import fetch_bulk_data_list

pytestmark = pytest.mark.integration

#: The bulk types this product actually imports (the `--type` choices of the import script).
_REQUIRED_TYPES = ("oracle_cards", "default_cards", "unique_artwork")


@pytest.fixture(scope="module")
async def live_entries() -> list[dict]:
    """One real call to ``api.scryfall.com/bulk-data``, shared by every test in the module."""
    try:
        return await fetch_bulk_data_list()
    except Exception as exc:  # pragma: no cover - network conditions, not a contract failure
        pytest.skip(f"Scryfall metadata endpoint unreachable: {exc}")


async def test_the_bulk_types_we_import_still_exist(live_entries):
    """A renamed or withdrawn type strands `--type` on a value Scryfall no longer serves."""
    available = {entry.get("type") for entry in live_entries}

    missing = [t for t in _REQUIRED_TYPES if t not in available]
    assert not missing, f"Scryfall no longer serves {missing}. Available: {sorted(available)}"


@pytest.mark.parametrize("bulk_type", _REQUIRED_TYPES)
async def test_every_imported_type_carries_a_resolvable_download_url(live_entries, bulk_type):
    """THE canary. If this reds, the importer is dead until a key spelling is added.

    Asserts through the production resolver rather than by indexing the dict, so the test and the
    importer can never disagree about which spellings are acceptable.
    """
    entry = next(e for e in live_entries if e.get("type") == bulk_type)

    uri = _resolve_download_uri(entry, bulk_type)

    assert uri.startswith("https://"), uri
    _validate_download_uri(uri)  # raises if the host ever moves off scryfall.io/.com


@pytest.mark.parametrize("bulk_type", _REQUIRED_TYPES)
async def test_every_imported_type_advertises_a_size(live_entries, bulk_type):
    """A missing size is not fatal — it falls back to DEFAULT_MAX_DOWNLOAD_BYTES — but it silently
    widens the disk-exhaustion ceiling from ~1.5x the real file to a flat 4 GiB, so it is worth
    knowing about rather than absorbing."""
    entry = next(e for e in live_entries if e.get("type") == bulk_type)

    size = _first_present(entry, _SIZE_KEYS)

    assert isinstance(size, int) and size > 0, (
        f"'{bulk_type}' advertises no size under any of {list(_SIZE_KEYS)}; "
        f"the download ceiling silently falls back to 4 GiB. Keys: {sorted(entry)}"
    )


async def test_the_payload_is_still_a_shape_the_parser_handles(live_entries):
    """`stream_cards` detects gzip and array-vs-JSONL from the bytes, so it needs no warning for a
    format flip *within* those two. A third encoding (zstd, parquet, a wrapped envelope) is what
    would break it, and the URL suffix is the cheapest early signal of one."""
    entry = next(e for e in live_entries if e.get("type") == "oracle_cards")
    uri = _resolve_download_uri(entry, "oracle_cards")

    assert uri.endswith((".json", ".jsonl", ".jsonl.gz", ".json.gz")), (
        f"oracle_cards is served as an unrecognised artefact: {uri}. "
        f"stream_cards handles JSON arrays and JSONL, plain or gzip'd — anything else needs code."
    )


async def test_the_keys_we_prefer_are_the_keys_upstream_leads_with(live_entries):
    """A soft signal, not a hard contract: if the NEW spelling disappears and only the OLD one is
    left, everything still works, but the preference order in `_DOWNLOAD_URI_KEYS` has gone stale
    and the next reader will be misled about which is current."""
    entry = next(e for e in live_entries if e.get("type") == "oracle_cards")

    assert _DOWNLOAD_URI_KEYS[0] in entry, (
        f"Upstream no longer carries the preferred key '{_DOWNLOAD_URI_KEYS[0]}'. "
        f"The importer still works via the fallback, but reorder _DOWNLOAD_URI_KEYS. "
        f"Keys: {sorted(entry)}"
    )
