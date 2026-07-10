"""Download-hardening regression tests (release-review findings M1/M2/L3).

* M1 — the bulk download must land in a fresh private per-run directory, never a fixed,
  world-shared ``/tmp/scryfall_<type>.json`` path (symlink-overwrite / pre-seed window).
* M2 — the download must enforce a byte ceiling derived from the size Scryfall advertises,
  so a hostile/buggy source can't exhaust the disk.
* L3 — the API-supplied ``download_uri`` must be https on a Scryfall host before we fetch it.
"""

import tempfile
from pathlib import Path

import httpx
import pytest

from src.data.importers import scryfall
from src.data.importers.importer import ImportStatistics
from src.data.importers.scryfall import ScryfallImportError, import_scryfall_bulk_data
from src.data.importers.scryfall_api import ScryfallAPIError, download_bulk_data


class _NullSession:
    """Minimal async session for the download-focused tests.

    The DB layer is faked (``import_cards``/``reconcile_games`` are patched out), so the only
    real session calls the orchestrator now makes are the empty-``cards`` count probe (returns 0,
    which short-circuits the in-progress check) and the first-run marker writes — all of which
    just need to be swallowed here.
    """

    async def scalar(self, *args, **kwargs) -> int:
        return 0

    async def execute(self, *args, **kwargs) -> None:
        return None

    async def commit(self) -> None:
        return None


def _mock_http(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    """Route every httpx.AsyncClient in the module under test through a MockTransport."""
    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient

    def patched(**kwargs):
        kwargs["transport"] = transport
        return real_client(**kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", patched)


# --- M2: byte ceiling in download_bulk_data -------------------------------------------


async def test_download_aborts_when_body_exceeds_max_bytes(tmp_path, monkeypatch):
    """A body larger than max_bytes aborts, removes the partial file, and does not retry."""
    attempts = []

    def handler(request):
        attempts.append(1)
        return httpx.Response(200, content=b"x" * 4096)

    _mock_http(monkeypatch, handler)
    out = tmp_path / "bulk.json"

    with pytest.raises(ScryfallAPIError, match="exceed"):
        await download_bulk_data("https://data.scryfall.io/x.json", out, max_bytes=1024)

    assert not out.exists(), "partial file must be removed on abort"
    assert len(attempts) == 1, "an oversized download must not be retried"


async def test_download_succeeds_under_max_bytes(tmp_path, monkeypatch):
    body = b'{"ok": true}'
    _mock_http(monkeypatch, lambda request: httpx.Response(200, content=body))
    out = tmp_path / "bulk.json"

    result = await download_bulk_data("https://data.scryfall.io/x.json", out, max_bytes=1024)

    assert result == out
    assert out.read_bytes() == body


async def test_download_without_cap_keeps_working(tmp_path, monkeypatch):
    """max_bytes stays optional — existing callers without a cap are unaffected."""
    body = b"[]"
    _mock_http(monkeypatch, lambda request: httpx.Response(200, content=body))
    out = tmp_path / "bulk.json"

    result = await download_bulk_data("https://data.scryfall.io/x.json", out)

    assert result.read_bytes() == body


# --- M1 + M2 wiring + L3: import_scryfall_bulk_data ------------------------------------


def _bulk_list(download_uri: str, size: int = 100):
    async def fake_list():
        return [{"type": "oracle_cards", "download_uri": download_uri, "size": size}]

    return fake_list


def _wire_import(monkeypatch: pytest.MonkeyPatch, download_uri: str, seen: dict) -> None:
    """Stub the import pipeline around the orchestrator, capturing the download call."""

    async def fake_download(uri, output_path, **kwargs):
        seen["uri"] = uri
        seen["path"] = output_path
        seen["kwargs"] = kwargs
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("[]")
        return output_path

    async def fake_import(session, cards_iterator, **kwargs):
        return ImportStatistics()

    monkeypatch.setattr(scryfall, "fetch_bulk_data_list", _bulk_list(download_uri))
    monkeypatch.setattr(scryfall, "download_bulk_data", fake_download)
    monkeypatch.setattr(scryfall, "stream_cards", lambda path: iter(()))
    monkeypatch.setattr(scryfall, "import_cards", fake_import)


async def test_import_downloads_into_fresh_private_dir_and_cleans_up(monkeypatch):
    """M1: no temp_dir given -> a fresh per-run directory, removed after the import."""
    seen: dict = {}
    _wire_import(monkeypatch, "https://data.scryfall.io/oracle.json", seen)

    await import_scryfall_bulk_data(session=_NullSession())

    downloaded = seen["path"]
    assert downloaded.parent != Path(tempfile.gettempdir()), (
        "download must not land directly in the shared, world-writable temp root"
    )
    assert not downloaded.exists()
    assert not downloaded.parent.exists(), "the per-run temp directory must be cleaned up"


async def test_import_passes_size_derived_byte_ceiling(monkeypatch):
    """M2 wiring: the orchestrator caps the download relative to the advertised size."""
    seen: dict = {}
    _wire_import(monkeypatch, "https://data.scryfall.io/oracle.json", seen)

    await import_scryfall_bulk_data(session=_NullSession())

    max_bytes = seen["kwargs"].get("max_bytes")
    assert max_bytes is not None, "orchestrator must enforce a byte ceiling"
    assert max_bytes >= 100, "ceiling must not be tighter than the advertised size"


@pytest.mark.parametrize(
    "bad_uri",
    [
        "https://evil.example.com/cards.json",
        "http://data.scryfall.io/cards.json",
        "https://scryfall.io.evil.example.com/cards.json",
    ],
)
async def test_import_rejects_untrusted_download_uri(monkeypatch, bad_uri):
    """L3: a download_uri that isn't https on a Scryfall host is refused before download."""
    seen: dict = {}
    _wire_import(monkeypatch, bad_uri, seen)

    with pytest.raises(ScryfallImportError, match="download_uri"):
        await import_scryfall_bulk_data(session=None)

    assert "uri" not in seen, "nothing may be fetched from an untrusted URI"
