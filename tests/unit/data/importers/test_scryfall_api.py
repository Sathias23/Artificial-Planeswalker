"""Behaviour tests for the Scryfall bulk-data client's retry and ceiling arms.

Every request is routed through an ``httpx.MockTransport`` (the ``test_spellbook_download.py``
shape) and the backoff sleep is recorded rather than slept, so the retry schedule is asserted at
zero wall clock. No live network.
"""

import httpx
import pytest

from src.data.importers.scryfall_api import (
    SCRYFALL_BULK_DATA_URL,
    ScryfallAPIError,
    download_bulk_data,
    fetch_bulk_data_list,
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
    """A transport-level response stream, so the body is streamed rather than pre-read."""

    def __init__(self, *chunks: bytes) -> None:
        self._chunks = chunks

    async def __aiter__(self):
        for chunk in self._chunks:
            yield chunk


def _streaming_response(
    *chunks: bytes, headers: dict[str, str] | None = None, status: int = 200
) -> httpx.Response:
    return httpx.Response(status, headers=headers, stream=_AsyncBody(*chunks))


@pytest.fixture
def sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Neutralise the backoff and record every delay the client asked for."""
    recorded: list[float] = []

    async def fake_sleep(delay: float) -> None:
        recorded.append(delay)

    monkeypatch.setattr("src.data.importers.scryfall_api.asyncio.sleep", fake_sleep)
    return recorded


class TestFetchBulkDataList:
    async def test_a_200_returns_the_data_list(self, monkeypatch, sleeps):
        seen: list[str] = []

        def handler(request):
            seen.append(str(request.url))
            return httpx.Response(200, json={"data": [{"type": "default_cards"}]})

        _mock_http(monkeypatch, handler)

        assert await fetch_bulk_data_list() == [{"type": "default_cards"}]
        assert seen == [SCRYFALL_BULK_DATA_URL]
        assert sleeps == []

    async def test_a_body_without_data_defaults_to_an_empty_list(self, monkeypatch, sleeps):
        _mock_http(monkeypatch, lambda request: httpx.Response(200, json={"object": "list"}))

        assert await fetch_bulk_data_list() == []

    async def test_a_5xx_then_200_succeeds_after_one_backoff(self, monkeypatch, sleeps):
        statuses = iter([503, 200])

        def handler(request):
            status = next(statuses)
            if status == 200:
                return httpx.Response(200, json={"data": [{"type": "default_cards"}]})
            return httpx.Response(status)

        _mock_http(monkeypatch, handler)

        result = await fetch_bulk_data_list(max_retries=3, retry_delay=0.5)

        assert result == [{"type": "default_cards"}]
        assert sleeps == [0.5], "exactly one backoff, at the base delay"

    async def test_exhausted_retries_raise_naming_the_attempt_count(self, monkeypatch, sleeps):
        _mock_http(monkeypatch, lambda request: httpx.Response(503))

        with pytest.raises(ScryfallAPIError, match="after 3 attempts"):
            await fetch_bulk_data_list(max_retries=3, retry_delay=1.0)

        assert sleeps == [1.0, 2.0], "exponential backoff between the three attempts"

    async def test_a_timeout_is_retried_like_a_5xx(self, monkeypatch, sleeps):
        calls = 0

        def handler(request):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise httpx.ReadTimeout("slow", request=request)
            return httpx.Response(200, json={"data": []})

        _mock_http(monkeypatch, handler)

        assert await fetch_bulk_data_list(retry_delay=0.25) == []
        assert calls == 2
        assert sleeps == [0.25]


class TestDownloadBulkData:
    async def test_a_streamed_body_lands_on_disk(self, tmp_path, monkeypatch, sleeps):
        _mock_http(monkeypatch, lambda request: _streaming_response(b"abc", b"def"))
        out = tmp_path / "nested" / "bulk.json"

        result = await download_bulk_data("https://data.example/bulk.json", out)

        assert result == out
        assert out.read_bytes() == b"abcdef"
        assert sleeps == []

    async def test_an_advertised_size_over_the_ceiling_aborts_without_retry(
        self, tmp_path, monkeypatch, sleeps
    ):
        calls = 0

        def handler(request):
            nonlocal calls
            calls += 1
            return _streaming_response(b"x" * 8, headers={"content-length": "8"})

        _mock_http(monkeypatch, handler)
        out = tmp_path / "bulk.json"

        with pytest.raises(ScryfallAPIError, match="Advertised download size"):
            await download_bulk_data("https://data.example/bulk.json", out, max_bytes=4)

        assert calls == 1
        assert not out.exists()
        assert sleeps == []

    async def test_a_body_over_the_ceiling_with_no_content_length_aborts_without_retry(
        self, tmp_path, monkeypatch, sleeps
    ):
        calls = 0

        def handler(request):
            nonlocal calls
            calls += 1
            return _streaming_response(b"x" * 5)  # no content-length header

        _mock_http(monkeypatch, handler)
        out = tmp_path / "bulk.json"

        with pytest.raises(ScryfallAPIError, match="exceeded the 4-byte ceiling"):
            await download_bulk_data("https://data.example/bulk.json", out, max_bytes=4)

        assert calls == 1, "a ceiling breach is never retried"
        assert not out.exists(), "the partial file is unlinked"
        assert sleeps == []

    async def test_a_transport_error_mid_stream_unlinks_the_partial_file_then_retries(
        self, tmp_path, monkeypatch, sleeps
    ):
        out = tmp_path / "bulk.json"
        calls = 0
        partial_seen: list[bool] = []

        class _Breaks(httpx.AsyncByteStream):
            async def __aiter__(self):
                yield b"partial"
                raise httpx.ReadError("connection reset")

        def handler(request):
            nonlocal calls
            calls += 1
            if calls == 1:
                return httpx.Response(200, stream=_Breaks())
            partial_seen.append(out.exists())
            return _streaming_response(b"whole")

        _mock_http(monkeypatch, handler)

        result = await download_bulk_data(
            "https://data.example/bulk.json", out, max_retries=3, retry_delay=0.5
        )

        assert result == out
        assert out.read_bytes() == b"whole"
        assert calls == 2
        assert partial_seen == [False], "the partial file was removed before the second attempt"
        assert sleeps == [0.5]

    async def test_a_non_2xx_is_retried_then_raised_after_the_last_attempt(
        self, tmp_path, monkeypatch, sleeps
    ):
        _mock_http(monkeypatch, lambda request: _streaming_response(b"", status=502))
        out = tmp_path / "bulk.json"

        with pytest.raises(ScryfallAPIError, match="after 2 attempts"):
            await download_bulk_data(
                "https://data.example/bulk.json", out, max_retries=2, retry_delay=1.0
            )

        assert not out.exists()
        assert sleeps == [1.0]

    async def test_a_disk_error_is_retried_like_a_transport_error(
        self, tmp_path, monkeypatch, sleeps
    ):
        _mock_http(monkeypatch, lambda request: _streaming_response(b"payload"))
        out = tmp_path / "bulk.json"
        real_open = type(out).open
        failures = 0

        def flaky_open(self, *args, **kwargs):
            nonlocal failures
            if self == out and failures == 0:
                failures += 1
                raise OSError("disk full")
            return real_open(self, *args, **kwargs)

        monkeypatch.setattr(type(out), "open", flaky_open)

        assert await download_bulk_data("https://data.example/bulk.json", out) == out
        assert out.read_bytes() == b"payload"
        assert sleeps == [2.0], "one backoff at download_bulk_data's default base delay"
