"""Streaming parser for large Scryfall bulk data files.

Two on-disk shapes are supported, and **which one a file is, is decided by reading the file** —
never by its name or by the URL it came from:

* a **JSON array** — one top-level ``[...]`` of card objects. Scryfall's historic ``download_uri``
  format, and the shape of every fixture in this repository.
* **JSONL**, optionally **gzip-compressed** — one card object per line. Scryfall's
  ``jsonl_download_uri`` format, which is what the live API serves as of 2026-08.

**Why detection is content-based.** The 2026-08-02 break that motivated this module's rewrite was
found when Scryfall replaced ``download_uri``/``size`` with
``jsonl_download_uri``/``compressed_size`` and changed the payload from an array to gzip'd JSONL.
Keying the parser on a ``.gz`` suffix would
put the same class of assumption back in a new place — a filename is a claim *about* bytes, and the
bytes are available. This is the same rule c3-7's D1 ruling settled for the image cache (*the
``Content-Type`` header wins over the URL suffix*), applied to the importer, and it is why the
existing array fixtures keep working with no edit and no flag.
"""

import gzip
import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import IO, Any, cast

import ijson

logger = logging.getLogger(__name__)

#: gzip's magic number (RFC 1952 §2.3.1). Two bytes, at offset 0, in every member header.
_GZIP_MAGIC = b"\x1f\x8b"


class JSONParseError(Exception):
    """Raised when JSON parsing fails."""

    pass


def _open_maybe_gzip(file_path: Path) -> IO[bytes]:
    """Open *file_path* for binary reading, transparently decompressing a gzip stream.

    Detection reads the first two bytes and compares them to :data:`_GZIP_MAGIC`, so a gzip file
    named ``.json`` decompresses and a plain file named ``.gz`` does not explode.
    """
    with file_path.open("rb") as probe:
        header = probe.read(2)
    if header == _GZIP_MAGIC:
        logger.info(f"Detected gzip stream: {file_path.name}")
        # `GzipFile` is a `BufferedIOBase` and supports every operation this module asks of it
        # (`read`, `seek(0)`, iteration, context management); typeshed simply does not declare it
        # as `IO[bytes]`. The cast records that, rather than widening the signature and pushing a
        # union onto three call sites.
        return cast(IO[bytes], gzip.open(file_path, "rb"))
    return file_path.open("rb")


def _first_nonspace_byte(stream: IO[bytes]) -> bytes:
    """Return the first non-whitespace byte of *stream*, leaving it positioned at that byte.

    Works on a ``gzip`` stream as well as a real file: both support ``seek`` back to 0, which is
    all this needs. Returns ``b""`` for an empty or all-whitespace stream.
    """
    while chunk := stream.read(4096):
        stripped = chunk.lstrip()
        if stripped:
            stream.seek(0)
            return stripped[:1]
    stream.seek(0)
    return b""


def _stream_json_array(stream: IO[bytes]) -> Iterator[dict[str, Any]]:
    """Yield each element of a top-level JSON array, incrementally."""
    yield from ijson.items(stream, "item")


def _stream_jsonl(stream: IO[bytes]) -> Iterator[dict[str, Any]]:
    """Yield each object of a newline-delimited JSON stream, one line at a time.

    Blank lines are skipped rather than raising — Scryfall's files end with a trailing newline,
    and a blank line carries no card either way.
    """
    for line_number, raw in enumerate(stream, start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError as e:
            raise JSONParseError(f"Malformed JSON on line {line_number:,}: {e}") from e


def stream_cards(file_path: Path) -> Iterator[dict[str, Any]]:
    """Stream card objects from a Scryfall bulk file incrementally.

    Neither shape is ever loaded into memory whole: a JSON array is parsed with ``ijson`` and JSONL
    is read a line at a time, so peak memory is one card either way. A gzip stream is decompressed
    on the fly.

    **The file is re-read per call, and the import makes two passes** (aggregate, then transform),
    so a compressed file is decompressed twice. That is deliberate: decompressing once to disk would
    add a second temp artefact and a new partial-write failure mode to save a few seconds of CPU on
    a step already bounded by a multi-hundred-megabyte download.

    Args:
        file_path: Path to the Scryfall bulk file — JSON array, JSONL, or gzip'd either.

    Yields:
        Dictionary representing a single card object.

    Raises:
        JSONParseError: If the file is malformed or cannot be parsed.
        FileNotFoundError: If the file does not exist.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"JSON file not found: {file_path}")

    logger.info(f"Starting streaming parse: {file_path}")
    cards_count = 0

    try:
        with _open_maybe_gzip(file_path) as stream:
            # Decide the shape from the bytes, never from the filename. `[` is an array;
            # anything else is treated as JSONL, whose first byte is `{`.
            leading = _first_nonspace_byte(stream)
            if leading == b"[":
                logger.info(f"Parsing {file_path.name} as a JSON array")
                cards = _stream_json_array(stream)
            else:
                logger.info(f"Parsing {file_path.name} as JSONL")
                cards = _stream_jsonl(stream)

            for card in cards:
                cards_count += 1
                yield card

                # Log progress every 5,000 cards during parsing
                if cards_count % 5000 == 0:
                    logger.debug(f"Parsed {cards_count:,} cards")

        logger.info(f"Completed parsing {cards_count:,} cards from {file_path.name}")

    except JSONParseError:
        raise

    except ijson.JSONError as e:
        error_msg = f"Malformed JSON in {file_path.name}: {e}"
        logger.error(error_msg)
        raise JSONParseError(error_msg) from e

    except Exception as e:
        error_msg = f"Unexpected error parsing {file_path.name}: {e}"
        logger.error(error_msg)
        raise JSONParseError(error_msg) from e
