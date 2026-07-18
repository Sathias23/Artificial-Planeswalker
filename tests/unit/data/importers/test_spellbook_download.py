"""Download-hardening tests for the Spellbook bulk-export downloader (Story 6.2, AC 1/9).

Mirrors ``test_download_hardening.py``: every request is routed through an
``httpx.MockTransport`` — no live network. Pins the AD-9 hardening contract
(explicit headers, byte ceiling with no-retry abort + partial-file cleanup, manual
exponential backoff) plus the httpx decoding trap: the ``.gz`` object is served with
``Content-Encoding: gzip`` and must land on disk as the WIRE bytes (``aiter_raw``),
never the auto-decompressed stream.
"""

import gzip

import httpx
import pytest

from src.data.importers.spellbook_api import (
    SPELLBOOK_VARIANTS_URL,
    SpellbookAPIError,
    download_variants_export,
)


def _mock_http(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    """Route every httpx.AsyncClient in the module under test through a MockTransport."""
    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient

    def patched(**kwargs):
        kwargs["transport"] = transport
        return real_client(**kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", patched)


class _AsyncBody(httpx.AsyncByteStream):
    """A transport-level response stream for MockTransport handlers.

    ``httpx.Response(content=...)`` pre-reads its body in ``__init__`` and marks the
    stream consumed, so ``aiter_raw()`` (which the downloader must use — see the
    decoding-trap test) raises ``StreamConsumed``. Handing the body as a ``stream=``
    mirrors how a real transport delivers it.
    """

    def __init__(self, body: bytes) -> None:
        self._body = body

    async def __aiter__(self):
        yield self._body


def _streaming_response(body: bytes, headers: dict[str, str] | None = None) -> httpx.Response:
    return httpx.Response(200, headers=headers, stream=_AsyncBody(body))


def test_variants_url_is_the_pinned_bulk_export():
    assert SPELLBOOK_VARIANTS_URL == "https://json.commanderspellbook.com/variants.json.gz"


async def test_request_sends_user_agent_and_accept_headers(tmp_path, monkeypatch):
    """AD-9: an explicit descriptive User-Agent AND an Accept header on the request."""
    seen: dict = {}

    def handler(request):
        seen["user-agent"] = request.headers.get("user-agent")
        seen["accept"] = request.headers.get("accept")
        return _streaming_response(b"payload")

    _mock_http(monkeypatch, handler)
    out = tmp_path / "variants.json.gz"

    await download_variants_export(out)

    assert seen["user-agent"] is not None
    assert "Artificial-Planeswalker" in seen["user-agent"]
    assert "github.com" in seen["user-agent"], "UA must carry the repo contact URL"
    assert seen["accept"] == "application/json"


async def test_download_aborts_over_max_bytes_without_retry(tmp_path, monkeypatch):
    """A body larger than max_bytes aborts, removes the partial file, and does not retry."""
    attempts: list[int] = []

    def handler(request):
        attempts.append(1)
        # No content-length header: the RUNNING ceiling must trigger mid-stream.
        return _streaming_response(b"x" * 4096)

    _mock_http(monkeypatch, handler)
    out = tmp_path / "variants.json.gz"

    with pytest.raises(SpellbookAPIError, match="exceed"):
        await download_variants_export(out, max_bytes=1024)

    assert not out.exists(), "partial file must be removed on abort"
    assert len(attempts) == 1, "a ceiling violation must not be retried"


async def test_advertised_content_length_over_ceiling_aborts_before_streaming(
    tmp_path, monkeypatch
):
    """An oversized content-length header aborts immediately (no body bytes written)."""

    def handler(request):
        return _streaming_response(b"", headers={"content-length": "9999999"})

    _mock_http(monkeypatch, handler)
    out = tmp_path / "variants.json.gz"

    with pytest.raises(SpellbookAPIError, match="exceed"):
        await download_variants_export(out, max_bytes=1024)

    assert not out.exists()


async def test_transport_error_backs_off_then_succeeds(tmp_path, monkeypatch):
    """Manual exponential backoff on httpx transport errors, mirroring scryfall_api."""
    calls: list[int] = []
    sleeps: list[float] = []

    def handler(request):
        calls.append(1)
        if len(calls) < 3:
            raise httpx.ConnectError("boom", request=request)
        return _streaming_response(b"payload")

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    _mock_http(monkeypatch, handler)
    monkeypatch.setattr("src.data.importers.spellbook_api.asyncio.sleep", fake_sleep)
    out = tmp_path / "variants.json.gz"

    result = await download_variants_export(out, max_retries=3, retry_delay=2.0)

    assert result == out
    assert out.read_bytes() == b"payload"
    assert len(calls) == 3
    assert sleeps == [2.0, 4.0], "backoff must double per attempt (retry_delay * 2**attempt)"


async def test_all_retries_exhausted_raises_api_error(tmp_path, monkeypatch):
    def handler(request):
        raise httpx.ConnectError("down", request=request)

    async def fake_sleep(delay: float) -> None:
        return None

    _mock_http(monkeypatch, handler)
    monkeypatch.setattr("src.data.importers.spellbook_api.asyncio.sleep", fake_sleep)
    out = tmp_path / "variants.json.gz"

    with pytest.raises(SpellbookAPIError, match="3 attempts"):
        await download_variants_export(out, max_retries=3)

    assert not out.exists(), "no partial file may survive a failed download"


async def test_gzip_content_encoding_lands_as_wire_bytes(tmp_path, monkeypatch):
    """The httpx decoding trap: the server marks the .gz object Content-Encoding: gzip.

    httpx auto-decompresses encoded responses, so a naive ``aiter_bytes`` download
    would write the DECODED stream (plain JSON, ceiling measured against the wrong
    size). The downloader must stream ``aiter_raw`` so the compressed wire bytes land
    on disk and ``gzip.open`` reads what it expects.
    """
    payload = b'{"timestamp": "t", "version": "v", "variants": []}'
    wire = gzip.compress(payload)

    def handler(request):
        return _streaming_response(
            wire, headers={"content-encoding": "gzip", "content-type": "application/json"}
        )

    _mock_http(monkeypatch, handler)
    out = tmp_path / "variants.json.gz"

    await download_variants_export(out)

    assert out.read_bytes() == wire, "disk file must be the compressed wire bytes"
    with gzip.open(out, "rb") as fh:
        assert fh.read() == payload


async def test_ceiling_measures_wire_bytes_not_decoded_bytes(tmp_path, monkeypatch):
    """The ceiling applies to compressed wire bytes (matching content-length)."""
    payload = b"a" * 100_000  # highly compressible: tiny wire, large decoded
    wire = gzip.compress(payload)
    assert len(wire) < 2048 < len(payload)

    def handler(request):
        return _streaming_response(wire, headers={"content-encoding": "gzip"})

    _mock_http(monkeypatch, handler)
    out = tmp_path / "variants.json.gz"

    # Would abort if the decoded stream were measured; must succeed on wire size.
    await download_variants_export(out, max_bytes=2048)

    assert out.read_bytes() == wire
