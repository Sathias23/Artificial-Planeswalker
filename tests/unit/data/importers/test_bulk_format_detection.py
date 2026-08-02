"""The 2026-08-02 Scryfall bulk-data break, and the format detection that closes it.

Scryfall replaced ``download_uri``/``size`` with ``jsonl_download_uri``/``compressed_size`` and
moved the payload from a top-level JSON array (``.json``) to gzip-compressed newline-delimited
JSON (``.jsonl.gz``). Every import path in the product broke at once, on a released version, and
no test saw it because every test in the suite monkeypatches ``fetch_bulk_data_list``.

These tests cover the two halves of the repair:

* :func:`~src.data.importers.parser.stream_cards` decides the payload shape **by reading the
  bytes**, so the array fixtures keep working, the new gzip'd JSONL works, and neither depends on
  a filename.
* :func:`~src.data.importers.scryfall._resolve_download_uri` accepts either key spelling and, when
  neither is present, raises an error that **names the keys that actually arrived** rather than the
  bare ``KeyError: 'download_uri'`` that made the live break undiagnosable.

The canary that would have caught the change in the first place lives in
``tests/integration/data/test_scryfall_live_contract.py``.
"""

import gzip
import json
from pathlib import Path

import pytest

from src.data.importers.parser import JSONParseError, stream_cards
from src.data.importers.scryfall import (
    _SIZE_KEYS,
    ScryfallImportError,
    _first_present,
    _resolve_download_uri,
)

CARDS = [
    {"id": "a", "name": "Lightning Bolt"},
    {"id": "b", "name": "Black Lotus"},
    {"id": "c", "name": "Westvale Abbey // Ormendahl, Profane Prince"},
]


def _write(path: Path, data: bytes, *, compress: bool) -> Path:
    path.write_bytes(gzip.compress(data) if compress else data)
    return path


def _as_array(cards) -> bytes:
    return json.dumps(cards).encode()


def _as_jsonl(cards) -> bytes:
    return ("\n".join(json.dumps(c) for c in cards) + "\n").encode()


class TestTheShapeIsReadFromTheBytes:
    """Every combination of {array, JSONL} x {plain, gzip} parses, regardless of filename."""

    @pytest.mark.parametrize("compress", [False, True], ids=["plain", "gzip"])
    @pytest.mark.parametrize("encode", [_as_array, _as_jsonl], ids=["json-array", "jsonl"])
    def test_all_four_shapes_yield_the_same_cards(self, tmp_path, encode, compress):
        path = _write(tmp_path / "bulk.bin", encode(CARDS), compress=compress)

        assert list(stream_cards(path)) == CARDS

    def test_the_live_upstream_shape_parses(self, tmp_path):
        """The exact shape Scryfall serves today: gzip'd JSONL with a trailing newline."""
        path = _write(tmp_path / "oracle-cards-20260801.jsonl.gz", _as_jsonl(CARDS), compress=True)

        assert [c["name"] for c in stream_cards(path)] == [c["name"] for c in CARDS]

    def test_a_gzip_stream_named_json_still_decompresses(self, tmp_path):
        """Detection is the magic number, not the suffix — the filename may lie."""
        path = _write(tmp_path / "definitely_not_compressed.json", _as_jsonl(CARDS), compress=True)

        assert list(stream_cards(path)) == CARDS

    def test_a_plain_array_named_gz_does_not_explode(self, tmp_path):
        """The inverse claim, so the rule is symmetric rather than a one-way special case."""
        path = _write(tmp_path / "not_really.jsonl.gz", _as_array(CARDS), compress=False)

        assert list(stream_cards(path)) == CARDS

    def test_leading_whitespace_does_not_change_the_verdict(self, tmp_path):
        path = _write(tmp_path / "bulk.json", b"\n\n  " + _as_array(CARDS), compress=False)

        assert list(stream_cards(path)) == CARDS

    def test_blank_lines_in_jsonl_are_skipped_not_fatal(self, tmp_path):
        body = b"\n".join(
            [json.dumps(CARDS[0]).encode(), b"", b"   ", json.dumps(CARDS[1]).encode()]
        )
        path = _write(tmp_path / "gappy.jsonl", body, compress=False)

        assert list(stream_cards(path)) == CARDS[:2]

    def test_an_empty_file_yields_nothing_rather_than_raising(self, tmp_path):
        path = _write(tmp_path / "empty.jsonl.gz", b"", compress=True)

        assert list(stream_cards(path)) == []


class TestMalformedInputStillFailsLoudly:
    """Detection must not turn a broken file into a silently short read."""

    def test_a_bad_jsonl_line_names_its_line_number(self, tmp_path):
        body = b'{"id": "a"}\n{"id": "b"\n{"id": "c"}\n'
        path = _write(tmp_path / "broken.jsonl", body, compress=False)

        with pytest.raises(JSONParseError, match="line 2"):
            list(stream_cards(path))

    def test_a_truncated_array_still_raises(self, tmp_path):
        path = _write(tmp_path / "broken.json", b'[{"id": "a"}, {"id":', compress=False)

        with pytest.raises(JSONParseError):
            list(stream_cards(path))

    def test_a_missing_file_still_raises_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            list(stream_cards(tmp_path / "nope.json"))


class TestMetadataKeyResolution:
    """Either spelling works; neither is a diagnosis, not a KeyError."""

    def test_the_new_spelling_is_preferred(self):
        entry = {
            "jsonl_download_uri": "https://data.scryfall.io/oracle-cards/x.jsonl.gz",
            "download_uri": "https://data.scryfall.io/oracle-cards/x.json",
        }

        assert _resolve_download_uri(entry, "oracle_cards").endswith(".jsonl.gz")

    def test_the_old_spelling_still_resolves(self):
        """A restored `download_uri`, or any fixture written before 2026-08-02."""
        entry = {"download_uri": "https://data.scryfall.io/oracle-cards/x.json"}

        assert _resolve_download_uri(entry, "oracle_cards").endswith(".json")

    def test_neither_key_names_what_actually_arrived(self):
        """The failure that made the live break undiagnosable, turned into a diagnosis."""
        entry = {"object": "bulk_data", "type": "oracle_cards", "some_future_uri": "https://x"}

        with pytest.raises(ScryfallImportError) as exc:
            _resolve_download_uri(entry, "oracle_cards")

        message = str(exc.value)
        assert "jsonl_download_uri" in message, "must name the keys it wanted"
        assert "some_future_uri" in message, "must name the keys that arrived"
        assert "oracle_cards" in message, "must name which bulk type failed"

    def test_an_empty_uri_is_treated_as_absent(self):
        with pytest.raises(ScryfallImportError):
            _resolve_download_uri({"jsonl_download_uri": ""}, "oracle_cards")

    @pytest.mark.parametrize(
        ("entry", "expected"),
        [
            ({"compressed_size": 24_406_614, "size": 999}, 24_406_614),
            ({"size": 141_000_000}, 141_000_000),
            ({}, None),
        ],
        ids=["prefers-compressed_size", "falls-back-to-size", "absent"],
    )
    def test_size_key_resolution(self, entry, expected):
        assert _first_present(entry, _SIZE_KEYS) == expected
