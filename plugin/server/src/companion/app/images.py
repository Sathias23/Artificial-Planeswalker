"""Face resolution, the paced CDN fetch and its caches behind ``GET /api/card-image/…`` (AD-11).

The one companion module that reaches a machine on the internet (FR-04). :func:`resolve_face_images`
is pure and decides which image map face N means; :func:`fetch_image` collapses every upstream
outcome onto one failure token; :class:`Pacer` queues it, with an injectable clock and sleep because
a rate is only testable on a fake clock; :class:`DiskCache` and :class:`NegativeCache` sit in front
of the pacer, so a warm tile costs no permit and a known-failed key costs no request. It is a second
Scryfall client because ``test_import_boundary.py`` bans ``src.data.importers`` from
``src/companion`` (AD-2); the answer to that guard is different code, never a wider allow-list.
Deliberately absent: in-flight coalescing (the disk cache bounds the cost of a duplicate fetch), any
eviction or TTL on the disk cache, a ceiling on queueing, and a per-cause backoff policy."""

import asyncio
import logging
import os
import tempfile
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI

from src import paths
from src.companion.app.errors import CompanionError
from src.data.schemas.card import CardFace

logger = logging.getLogger(__name__)

ImageSize = Literal["small", "normal", "large", "png", "art_crop", "border_crop"]
"""The closed set of sizes a caller may ask for, generated into the schema as an ``enum``. Every
stored ``image_uris`` object carries exactly these six keys; ``normal`` is the default (FR-19)."""

DEFAULT_IMAGE_SIZE: ImageSize = "normal"
"""What ``GET /api/card-image/{scryfall_id}`` with no query means: the normal-size front face."""

ALLOWED_IMAGE_HOSTS = frozenset({"cards.scryfall.io", "errors.scryfall.com"})
"""The only hosts this backend will fetch from: an explicit set, because a suffix match fails open
if the corpus changes. The row is third-party data, so "the database said so" is no reason to fetch
an arbitrary URL from inside the user's network, where loopback and link-local hosts live."""

IMAGE_CACHE_CONTROL = "public, max-age=31536000, immutable"
"""What a successfully served image is stamped with; Starlette sets no ``Cache-Control`` at all.
``immutable`` adds no staleness class, because :class:`DiskCache` already serves a stale image when
a data refresh moves the URL (AD-11). ``test_routes_card_image.py`` pins it to ``spa.py``'s."""

_ALLOWED_SCHEME = "https"

_ACCEPT = "image/avif,image/webp,image/png,image/jpeg,image/*;q=0.8"
"""What this route wants back. Scryfall expects consumers to send one."""

_IMAGE_CONTENT_TYPE_PREFIX = "image/"

_SVG_MEDIA_TYPE = "image/svg+xml"
"""The one ``image/*`` type refused: SVG can carry script, and this route serves upstream bytes
from the SPA's own origin under a year-long ``immutable`` stamp. No stored URL is an SVG."""

_FETCH_TIMEOUT = httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0)
"""A short connect so an unreachable CDN costs a fraction of a second; a longer read so a large
``png`` on a slow link is not mistaken for a dead one."""

_FETCH_TOTAL_SECONDS = 20.0
"""The whole-exchange deadline ``httpx`` cannot provide (its ``read`` deadline caps the gap between
chunks, so a dripping server would hold a :data:`FETCH_CONCURRENCY` permit forever). The queue wait
is deliberately outside it: it bounds a conversation with an upstream; a queued request has none."""

_MAX_IMAGE_BYTES = 16 * 1024 * 1024
"""An upper bound on what this backend will buffer from an upstream it does not control (the
largest stored size is ~1 MB). Enforced while streaming: a declared ``Content-Length`` over it is
refused before a byte is read, and the running total abandons the fetch at the ceiling."""

FETCH_SPACING_SECONDS = 0.1
"""The minimum gap between two outbound fetch **starts**, process-wide (AD-11): a good-citizen and
NFR-05 budget choice (99 tiles x 0.1 s meets the ~10 s target), not compliance. Measured between
starts, never completions, or spacing degrades into serialisation when the CDN slows."""

FETCH_CONCURRENCY = 4
"""How many image fetches may be open at once, process-wide (AD-11). Throughput is
``min(1/spacing, cap/latency)``: at normal latency the spacing wins and this is inert; at a degraded
2 s the cap wins, so a struggling upstream receives less traffic, not more connections."""

NEGATIVE_CACHE_BASE_SECONDS = 30.0
"""How long the first failure for one key is remembered (AD-11). It must exceed one cold deck
paint (98 spacing intervals, 9.8 s), or a second paint would find every window expired and re-admit
the storm; ``test_images.py`` asserts the inequality. Unlike a disk entry, a failure expires."""

NEGATIVE_CACHE_MULTIPLIER = 2.0
"""What each consecutive failure multiplies the previous delay by: five steps from base to ceiling
(30, 60, 120, 240, 300), where a flat cooldown treats a blip and a week-long outage identically.
Computed as ``previous x multiplier``; ``base * multiplier ** failures`` would overflow."""

NEGATIVE_CACHE_CEILING_SECONDS = 300.0
"""The longest a failure is ever remembered: a dead CDN settles at one attempt per tile per five
minutes, and without a ceiling a tile that failed a dozen times is broken for the session. Published
in ``ui/README.md`` because the SPA has no per-image retry; also the retention horizon."""

NEGATIVE_CACHE_MAX_ENTRIES = 2048
"""The hard bound on remembered failures: the key space is 245,760 (one per stored URL), and 2,048
is roughly twice a 40-deck library's 1,061 distinct card ids, so eviction is reached only by a
pattern no real session produces and then costs exactly one extra fetch (``test_images.py``)."""

CACHE_DIRECTORY_NAME = "image_cache"
"""The cache's one directory under :func:`src.paths.data_dir` (AD-11, NFR-09): a name, never a
resolved path (see :func:`cache_root`). ``README.md`` documents the location and the inspect/clear
commands; ``test_images.py`` pins ``docs/companion.md``'s example path to this constant."""

DISK_CACHE_WRITE_FAILURE_LIMIT = 5
"""How many consecutive failed writes disable :class:`DiskCache`'s writes for the process, so an
unwritable root does not warn ~99 times per cold paint forever. Five stops the shouting within the
first paint; a ~6 s transient during a paint (an AV scanner) also latches writes off, accepted
because only caching is lost and ``README.md`` names a restart as the remedy. Only writes stop:
NFR-06's offline operation depends on reading what a previous session cached."""

CACHE_MEDIA_TYPES: dict[str, str] = {".jpg": "image/jpeg", ".png": "image/png"}
"""Extension → media type, the closed map a warm hit answers from; an unknown header is served and
not cached, never raised on. Never ``mimetypes.guess_type``: on Windows it consults the registry.
The extension is not part of the cache key, so this is also the read's candidate list."""

_EXTENSION_BY_MEDIA_TYPE: dict[str, str] = {media: ext for ext, media in CACHE_MEDIA_TYPES.items()}
"""The reverse of :data:`CACHE_MEDIA_TYPES`, derived rather than written twice."""


def _user_agent() -> str:
    """Build the descriptive ``User-Agent`` Scryfall asks for (NFR-08); generic agents get blocked.

    Returns:
        A ``name/version (+url)`` string, the version read from installed metadata.
    """
    try:
        pkg_version = version("artificial-planeswalker")
    except PackageNotFoundError:  # pragma: no cover - editable installs always resolve
        pkg_version = "unknown"
    return (
        f"Artificial-Planeswalker/{pkg_version} "
        "(+https://github.com/Sathias23/Artificial-Planeswalker)"
    )


def resolve_face_images(
    image_uris: Mapping[str, str] | None,
    card_faces: Sequence[CardFace] | None,
) -> list[dict[str, str]]:
    """Return this card's image maps, in face order: what the ``face`` parameter indexes.

    Keys on the presence of per-face ``image_uris``, never on a layout string (AD-11, FR-04):
    split, adventure and flip cards have faces **and** one top-level image. Per-face wins.

    Args:
        image_uris: The card's top-level image map, or ``None``. An empty map resolves to nothing.
        card_faces: The card's faces, or ``None``.

    Returns:
        A new list of copied image maps, one per servable face; empty when the card has no images.
    """
    faces = list(card_faces or ())
    per_face = [dict(face.image_uris) for face in faces if face.image_uris]
    if per_face:
        return per_face
    return [dict(image_uris)] if image_uris else []


def is_fetchable(url: str) -> bool:
    """Return whether *url* is ``https`` with a parsed hostname in :data:`ALLOWED_IMAGE_HOSTS`.

    Never a substring test, which ``https://cards.scryfall.io.evil.example/x`` and
    ``https://cards.scryfall.io@evil.example/x`` both defeat. Any explicit port is refused.

    Args:
        url: The URL stored on the card row.

    Returns:
        True when the URL may be fetched; False for anything else, including an unparseable one.
    """
    try:
        parts = urlsplit(url)
    except ValueError:
        # A stored value that will not even parse is a refusal, not an exception in a handler.
        return False
    if parts.scheme != _ALLOWED_SCHEME or parts.port is not None:
        return False
    return (parts.hostname or "") in ALLOWED_IMAGE_HOSTS


def build_image_client(*, transport: httpx.AsyncBaseTransport | None = None) -> httpx.AsyncClient:
    """Construct the shared outbound client (AD-10; created by the lifespan, never at build time).

    One client per process, or ~100 tiles per deck view each pay a TLS handshake; constructing one
    opens no socket, and only the lifespan has a teardown to close it. ``follow_redirects`` is
    False: the allow-list is checked on the stored URL, and following would fetch whatever
    ``Location`` an allowed host answered, including loopback and link-local addresses; a 3xx is an
    ordinary fetch failure. ``trust_env`` stays True, unlike the loopback probe in
    ``src/companion/client.py``: a user behind a corporate proxy has no other way out.

    Args:
        transport: Replaces the network transport; the seam every unit test uses.

    Returns:
        An ``httpx.AsyncClient``, not yet connected to anything.
    """
    return httpx.AsyncClient(
        timeout=_FETCH_TIMEOUT,
        follow_redirects=False,
        transport=transport,
        headers={"User-Agent": _user_agent(), "Accept": _ACCEPT},
    )


def image_client(app: FastAPI) -> httpx.AsyncClient | None:
    """Return the client the lifespan created for *app*, or ``None`` if it never ran.

    Args:
        app: The application to read.

    Returns:
        The shared client, or ``None``: a wiring bug reported as ``internal_error``.
    """
    # Annotated local: app.state is Any, and warn_return_any would flag returning it directly.
    client: httpx.AsyncClient | None = getattr(app.state, "image_client", None)
    return client


class Pacer:
    """The one choke point every outbound image fetch passes through (AD-11).

    A semaphore caps how many fetches are open; a turnstile spaces how often one may start. The
    permit is taken first and the turn second, so the turn is claimed immediately before the request
    goes out; the other order paces nothing under load. One per app rather than a module global,
    which would serialise unrelated apps in a test run; constructing one cannot fail.

    Args:
        spacing: Seconds between fetch starts. Defaults to :data:`FETCH_SPACING_SECONDS`.
        limit: Simultaneous fetches allowed. Defaults to :data:`FETCH_CONCURRENCY`.
        clock: Monotonic seconds, injected so tests assert exact start offsets on a fake clock.
        sleep: The awaitable delay; a synchronous sleep would stall every other request.
    """

    def __init__(
        self,
        *,
        spacing: float = FETCH_SPACING_SECONDS,
        limit: int = FETCH_CONCURRENCY,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._spacing = spacing
        self._clock = clock
        self._sleep = sleep
        self._capacity = asyncio.Semaphore(limit)
        self._turnstile = asyncio.Lock()
        # None rather than a clock-derived sentinel: a cold process paints its first tile at once.
        self._next_start: float | None = None

    @property
    def available_permits(self) -> int:
        """How many fetches could start right now; the cancellation tests assert it is restored."""
        # asyncio.Semaphore's own counter, read rather than tracked so the assertion cannot drift.
        return self._capacity._value

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        """Hold one fetch's place: a permit for the whole exchange, and a spaced start.

        ``async with`` on both primitives is what makes cancellation safe: a manual
        ``acquire()``/``release()`` around an ``await`` leaks a permit on ``CancelledError``.

        Yields:
            None; the caller may issue its request for the duration of the block.
        """
        async with self._capacity:
            await self._wait_for_turn()
            yield

    async def _wait_for_turn(self) -> None:
        """Block until this caller may start, then claim the next slot in the queue.

        The lock is held across the wait so the queue is first-come-first-served; the cursor is
        advanced after the wait, so a caller cancelled mid-wait claims no slot.
        """
        async with self._turnstile:
            now = self._clock()
            if self._next_start is not None and self._next_start > now:
                await self._sleep(self._next_start - now)
                # Re-read: a real sleep may overshoot, and pacing from the actual start avoids drift
                now = self._clock()
            self._next_start = now + self._spacing


def image_pacer(app: FastAPI) -> Pacer | None:
    """Return the pacer the lifespan created for *app*, or ``None`` if it never ran.

    Args:
        app: The application to read.

    Returns:
        The shared pacer, or ``None``: a wiring bug reported as ``internal_error``, never unpaced.
    """
    # Annotated local: app.state is Any, and warn_return_any would flag returning it directly.
    pacer: Pacer | None = getattr(app.state, "image_pacer", None)
    return pacer


def cache_root() -> Path:
    """Return the image cache's root directory, resolved at call time.

    Never at import and never as a default argument: :func:`src.paths.data_dir` ends in ``mkdir``,
    so a module-level path would create the user's data directory on import, breaking AD-10.

    Returns:
        ``src.paths.data_dir() / CACHE_DIRECTORY_NAME``; this directory itself may not exist yet.
    """
    return paths.data_dir() / CACHE_DIRECTORY_NAME


def cache_extension(content_type: str) -> str | None:
    """Decide which extension a fetched image is stored under, never from the size key.

    ``png`` resolves to a ``.jpg`` URL on three real cards, so the header is the only source. Nor
    is the URL a fallback: an unknown ``image/*`` header is a different format (``image/webp``).

    Args:
        content_type: The ``Content-Type`` the upstream sent, parameters and all.

    Returns:
        A member of :data:`CACHE_MEDIA_TYPES`, or ``None`` meaning served and not cached.
    """
    media_type = content_type.split(";", 1)[0].strip().lower()
    return _EXTENSION_BY_MEDIA_TYPE.get(media_type)


def _cache_path(root: Path, card_id: str, size: str, face: int, extension: str) -> Path:
    """Build AD-11's cache path: ``<root>/<id[0:2]>/<id>/<size>_<face>.<ext>``.

    Only ever constructed, never parsed back: ``art_crop_0.jpg`` is ambiguous to ``rsplit("_")``.

    Args:
        root: The cache root.
        card_id: The Scryfall printing uuid, already validated by the route's path constraint.
        size: The requested rendition.
        face: Which of the card's images was asked for.
        extension: A member of :data:`CACHE_MEDIA_TYPES`, from :func:`cache_extension`.

    Returns:
        The full path this entry lives at. Nothing is created.
    """
    return root / card_id[:2] / card_id / f"{size}_{face}{extension}"


# The two synchronous file-I/O primitives, reached from the async path only through
# `asyncio.to_thread`: AD-11 says the image path must never block the event loop, and a 124 KB read
# measures 4.97 ms, so a warm 99-tile paint inline would block it for ~0.49 s (NFR-05).


def _read_cached(root: Path, card_id: str, size: str, face: int) -> tuple[bytes, str] | None:
    """Read this key's entry off disk, trying each known extension in turn.

    Every failure is a miss costing one ordinary fetch, including an empty entry (served, it would
    be stamped immutable for a year) and one over :data:`_MAX_IMAGE_BYTES`.

    Args:
        root: The cache root.
        card_id: The printing uuid.
        size: The requested rendition.
        face: Which of the card's images was asked for.

    Returns:
        The stored bytes and the media type implied by the extension, or ``None`` for a miss.
    """
    for extension, media_type in CACHE_MEDIA_TYPES.items():
        candidate = _cache_path(root, card_id, size, face, extension)
        try:
            payload = candidate.read_bytes()
        except FileNotFoundError:
            continue
        except OSError as exc:
            logger.warning(
                "Could not read the cached image at %s (%s); fetching it instead",
                candidate,
                type(exc).__name__,
            )
            continue
        if not payload:
            logger.warning("Cached image at %s is empty; fetching it instead", candidate)
            continue
        if len(payload) > _MAX_IMAGE_BYTES:
            logger.warning(
                "Cached image at %s is %d bytes, over the %d-byte ceiling; fetching it instead",
                candidate,
                len(payload),
                _MAX_IMAGE_BYTES,
            )
            continue
        return payload, media_type
    return None


def _write_atomically(target: Path, payload: bytes, *, displaces: tuple[Path, ...] = ()) -> bool:
    """Write *payload* to *target* so no reader can ever observe a partial file.

    Follows ``discovery.write_discovery`` minus ``os.fsync`` (a cache entry lost to a power cut
    costs one refetch) and ``os.chmod`` (public images, not a credential). Displaced siblings are
    unlinked **before** the replace: :func:`_read_cached` probes extensions in fixed order, so a
    stale ``normal_0.jpg`` would otherwise permanently shadow a fresh ``normal_0.png``.

    Args:
        target: The final path, from :func:`_cache_path`.
        payload: The image bytes to store.
        displaces: Sibling paths this write supersedes: the same key under the other extensions.

    Returns:
        True when this call's own replace landed; False when it lost a same-key race to a servable
        entry, which the caller counts as neither a failure nor a success.

    Raises:
        OSError: The directory, temp file or replace failed; :meth:`DiskCache.write` swallows it.
    """
    directory = target.parent
    directory.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(dir=directory, prefix=f"{target.name}.", suffix=".tmp")
    temp_path = Path(temp_name)
    try:
        try:
            handle = os.fdopen(descriptor, "wb")
        except BaseException:
            # fdopen takes ownership only on success; a leaked descriptor pins the temp file too.
            os.close(descriptor)
            raise
        with handle:
            handle.write(payload)
        for stale in displaces:
            try:
                stale.unlink(missing_ok=True)
            except OSError as exc:
                logger.warning(
                    "Could not remove the superseded cache entry at %s (%s); the older spelling "
                    "will shadow the one being written",
                    stale,
                    type(exc).__name__,
                )
        try:
            os.replace(temp_path, target)
        except PermissionError:
            # The Windows same-key race: the loser's replace over the winner's open file raises,
            # and a lost race must not feed the failure counter. SERVABLE, not merely present:
            # `_read_cached` treats a zero-byte or unreadable file as a miss, so a locked empty
            # target swallowed as a race would refetch forever with the latch never announcing it.
            try:
                with target.open("rb") as existing:
                    stored_by_winner = existing.read(1) != b""
            except OSError:
                stored_by_winner = False
            if not stored_by_winner:
                raise
            with suppress(OSError):
                temp_path.unlink(missing_ok=True)
            return False
    except BaseException:
        with suppress(OSError):
            temp_path.unlink(missing_ok=True)
        raise
    return True


class DiskCache:
    """The sharded, atomically written, unbounded disk cache behind the image route (AD-11).

    The key is id + size + face and the URL is deliberately not part of it: a data refresh that
    moves the ``?<timestamp>`` cache-buster still serves the older picture, accepted (AD-11)
    because keying on the URL would make every refresh a total miss. No TTL, eviction or index.
    AD-2's write boundary is the database and explicitly permits this file I/O.

    Containment is the caller's, restated here rather than validated: :meth:`path_for` builds a
    path from an id it does not check, so ``path_for("../../..", …)`` escapes this root. The guard
    is ``routes/cards.py``'s ``_CARD_ID_PATTERN`` (a canonical lowercase uuid), the closed
    :data:`ImageSize` ``Literal``, and a bounded ``face`` integer.

    Args:
        root: The directory entries live under, already created by :func:`build_image_cache`.
    """

    def __init__(self, root: Path) -> None:
        self._root = root
        self._consecutive_write_failures = 0
        self._writes_disabled = False

    @property
    def root(self) -> Path:
        """The directory this cache's entries live under."""
        return self._root

    def path_for(self, card_id: str, size: str, face: int, extension: str) -> Path:
        """Return where one entry lives: AD-11's path, character for character.

        Args:
            card_id: The Scryfall printing uuid.
            size: The requested rendition.
            face: Which of the card's images was asked for.
            extension: A member of :data:`CACHE_MEDIA_TYPES`.

        Returns:
            ``<root>/<id[0:2]>/<id>/<size>_<face>.<ext>``. Nothing is created.
        """
        return _cache_path(self._root, card_id, size, face, extension)

    async def read(self, card_id: str, size: str, face: int) -> tuple[bytes, str] | None:
        """Return this key's cached image, or ``None`` for a miss; the read runs in a worker thread.

        Args:
            card_id: The printing uuid.
            size: The requested rendition.
            face: Which of the card's images was asked for.

        Returns:
            The bytes and the media type implied by the extension, or ``None`` meaning fetch.
        """
        try:
            return await asyncio.to_thread(_read_cached, self._root, card_id, size, face)
        except Exception:
            # `to_thread` itself refusing to schedule: a cache failure at any layer is a fetch.
            logger.warning(
                "Reading the cached image for %s failed outside the file layer; fetching it "
                "instead",
                card_id,
                exc_info=True,
            )
            return None

    async def write(
        self,
        *,
        card_id: str,
        size: str,
        face: int,
        content_type: str,
        body: bytes,
    ) -> None:
        """Store one fetched image, atomically, and never fail the request for it.

        Keyword-only because three string parameters would silently transpose into a wrong key.

        Args:
            card_id: The printing uuid.
            size: The requested rendition.
            face: Which of the card's images was asked for.
            content_type: The upstream's own ``Content-Type``, the sole extension source.
            body: The image bytes to store.
        """
        if self._writes_disabled:
            return
        extension = cache_extension(content_type)
        if extension is None:
            logger.info(
                "Not caching the image for %s: %r is outside the two extensions this cache stores",
                card_id,
                content_type,
            )
            return
        target = _cache_path(self._root, card_id, size, face, extension)
        displaced = tuple(
            _cache_path(self._root, card_id, size, face, other)
            for other in CACHE_MEDIA_TYPES
            if other != extension
        )
        try:
            stored = await asyncio.to_thread(_write_atomically, target, body, displaces=displaced)
        except Exception as exc:
            # Broader than `OSError`: `to_thread` itself can refuse to schedule.
            self._note_write_failure(target, exc)
        else:
            # Only a landed replace resets the count; a lost same-key race proves nothing.
            if stored:
                self._consecutive_write_failures = 0

    def _note_write_failure(self, target: Path, exc: Exception) -> None:
        """Log one failed write, and give up once they pass :data:`DISK_CACHE_WRITE_FAILURE_LIMIT`.

        Args:
            target: Where the entry would have been written.
            exc: The failure, used for its type name only.
        """
        self._consecutive_write_failures += 1
        if self._consecutive_write_failures < DISK_CACHE_WRITE_FAILURE_LIMIT:
            logger.warning(
                "Could not cache the image at %s (%s); it was served but not stored",
                target,
                type(exc).__name__,
            )
            return
        self._writes_disabled = True
        # It must SAY it is giving up, or a silently stopped cache looks like a working one.
        logger.warning(
            "Could not cache the image at %s (%s), and that is %d consecutive write failures — "
            "disabling this cache's writes for the rest of this process. Images will still be "
            "served, and anything already cached will still be read; check that %s is writable",
            target,
            type(exc).__name__,
            self._consecutive_write_failures,
            self._root,
        )


def build_image_cache() -> DiskCache | None:
    """Create the cache root and return a cache over it, or ``None`` if that failed.

    The lifespan creates the root, never ``build_app()`` (AD-11, AD-10). A failure disables the
    cache but does not fail the launch: publishing the discovery file stays the only startup step
    that may (AD-15), because a missing cache leaves a fully functional, slower app.

    Returns:
        A cache over a directory that exists, or ``None`` meaning this process has no cache.
    """
    try:
        root = cache_root()
        root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning(
            "Could not create the image cache directory (%s: %s); images will be fetched from the "
            "CDN every time this process serves one",
            type(exc).__name__,
            exc,
        )
        return None
    return DiskCache(root)


def image_cache(app: FastAPI) -> DiskCache | None:
    """Return the cache the lifespan created for *app*, or ``None`` when there is none.

    Args:
        app: The application to read.

    Returns:
        The shared disk cache, or ``None`` meaning serve without one: unlike :func:`image_client`,
        an ordinary state, since ``internal_error`` here would turn a degradation into an outage.
    """
    # Annotated local: app.state is Any, and warn_return_any would flag returning it directly.
    cache: DiskCache | None = getattr(app.state, "image_cache", None)
    return cache


@dataclass(frozen=True, slots=True)
class _RememberedFailure:
    """One key's failure state. The delay is stored rather than a count, because
    ``base * multiplier ** count`` overflows after a few thousand failures against a dead CDN.

    Attributes:
        delay: The backoff this key is currently serving, already clamped to the ceiling.
        retry_after: The clock reading at which this key becomes fetchable again.
    """

    delay: float
    retry_after: float


class NegativeCache:
    """The map of recently-failed image keys, and the backoff they are serving (AD-11).

    Its correctness is forgetting: a negative cache that never forgets is a permanently broken
    tile and an unbounded map, so ``test_images.py`` proves expiry and bounds on an injected clock.
    It removes every paint **after** the first against a failing CDN. Nothing is persisted, because
    ``image_fetch_failed`` is defined as transient and a restart must remain a remedy. Not
    ``functools.lru_cache``: it cannot express a TTL, and ``cache_clear()`` cannot clear one key.

    Args:
        base: The first failure's window, in seconds; :data:`NEGATIVE_CACHE_BASE_SECONDS`.
        multiplier: Applied to the previous delay per failure; :data:`NEGATIVE_CACHE_MULTIPLIER`.
        ceiling: The longest window ever applied; :data:`NEGATIVE_CACHE_CEILING_SECONDS`.
        max_entries: The bound on resident entries; :data:`NEGATIVE_CACHE_MAX_ENTRIES`.
        clock: Monotonic seconds, never ``time.time``: a wall clock stepping back frees every entry.

    Raises:
        ValueError: ``max_entries`` or ``multiplier`` below one, a guard for mis-injected tests.
    """

    def __init__(
        self,
        *,
        base: float = NEGATIVE_CACHE_BASE_SECONDS,
        multiplier: float = NEGATIVE_CACHE_MULTIPLIER,
        ceiling: float = NEGATIVE_CACHE_CEILING_SECONDS,
        max_entries: int = NEGATIVE_CACHE_MAX_ENTRIES,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_entries < 1:
            raise ValueError(f"max_entries must be at least 1, got {max_entries}")
        if multiplier < 1:
            raise ValueError(f"multiplier below 1 decays instead of backing off: {multiplier}")
        self._base = base
        self._multiplier = multiplier
        self._ceiling = ceiling
        self._max_entries = max_entries
        self._clock = clock
        # The same id + size + face key AD-11 gives the disk cache, never the URL.
        self._entries: dict[tuple[str, str, int], _RememberedFailure] = {}

    @property
    def entry_count(self) -> int:
        """Resident failures: the only observable separating pruning expired entries from ignoring
        them, since a map that only ignores expiry fills with garbage and evicts live ones."""
        return len(self._entries)

    def is_backing_off(self, card_id: str, size: str, face: int) -> bool:
        """Return whether this key is inside a backoff window and must not be fetched.

        The hot path, free of side effects: one lookup and one comparison, no pruning, because it
        runs on every disk-cache miss. The window is half-open: exactly at ``retry_after`` fetches.

        Args:
            card_id: The printing uuid.
            size: The requested rendition.
            face: Which of the card's images was asked for.

        Returns:
            True when the caller should answer from memory instead of fetching.
        """
        remembered = self._entries.get((card_id, size, face))
        return remembered is not None and self._clock() < remembered.retry_after

    def record_failure(self, card_id: str, size: str, face: int) -> float:
        """Remember that this key just failed, and return the backoff now applied to it.

        A failure inside an open window still escalates, because the count measures the outage.

        Args:
            card_id: The printing uuid.
            size: The requested rendition.
            face: Which of the card's images was asked for.

        Returns:
            The delay applied, in seconds, so a caller can assert the schedule.
        """
        now = self._clock()
        key = (card_id, size, face)
        # Pruned on EVERY insert, or the map fills with stale garbage and evicts live entries.
        self._forget_stale(now)
        previous = self._entries.get(key)
        # BOTH branches clamp, so an injected `base > ceiling` cannot exceed the maximum.
        delay = (
            min(self._base, self._ceiling)
            if previous is None
            else min(previous.delay * self._multiplier, self._ceiling)
        )
        if previous is None and len(self._entries) >= self._max_entries:
            self._evict_earliest_expiry()
        self._entries[key] = _RememberedFailure(delay=delay, retry_after=now + delay)
        return delay

    def clear(self, card_id: str, size: str, face: int) -> None:
        """Forget this key's failure history entirely: recovery, completed.

        Ending the window is only half of recovery; the next failure must start at the base delay.

        Args:
            card_id: The printing uuid.
            size: The requested rendition.
            face: Which of the card's images was asked for.
        """
        self._entries.pop((card_id, size, face), None)

    def _forget_stale(self, now: float) -> None:
        """Drop every entry that has gone a full ceiling past its window without failing again.

        The horizon is ``retry_after + ceiling``, not ``retry_after``: a window closing means the
        key may be fetched again, not that it never failed, and discarding at ``retry_after`` would
        reset the escalation on every attempt while every "consecutive failures" test still passed.

        Args:
            now: The clock reading, passed in so one :meth:`record_failure` takes exactly one.
        """
        stale = [
            key for key, entry in self._entries.items() if now >= entry.retry_after + self._ceiling
        ]
        for key in stale:
            del self._entries[key]

    def _evict_earliest_expiry(self) -> None:
        """Drop the entry closest to expiring: it discards the least information, at the cost of
        one extra fetch for that key (or an early escalation reset if it was retained history)."""
        earliest = min(self._entries, key=lambda key: self._entries[key].retry_after)
        del self._entries[earliest]


def negative_cache(app: FastAPI) -> NegativeCache | None:
    """Return the negative cache the lifespan created for *app*, or ``None`` if it never ran.

    Args:
        app: The application to read.

    Returns:
        The shared negative cache, or ``None``, answered by fetching: refusing to serve an image
        for want of a remembered *failure* would turn a degradation into an outage.
    """
    # Annotated local: app.state is Any, and warn_return_any would flag returning it directly.
    cache: NegativeCache | None = getattr(app.state, "negative_cache", None)
    return cache


def _refused_host(url: str) -> str:
    """Name the host of a refused URL for the log, surviving the ``ValueError`` ``urlsplit`` raises.

    Args:
        url: The URL that was refused.

    Returns:
        The lower-cased hostname, or ``"<unparseable>"``.
    """
    try:
        return urlsplit(url).hostname or "<unparseable>"
    except ValueError:
        return "<unparseable>"


def _is_servable_image_type(content_type: str) -> bool:
    """Return whether an upstream ``Content-Type`` is ``image/*`` and not :data:`_SVG_MEDIA_TYPE`.

    Args:
        content_type: The header value as the upstream sent it, possibly with parameters.

    Returns:
        True for a servable raster type; False for anything else.
    """
    media_type = content_type.split(";", 1)[0].strip().lower()
    return media_type.startswith(_IMAGE_CONTENT_TYPE_PREFIX) and media_type != _SVG_MEDIA_TYPE


async def fetch_image(client: httpx.AsyncClient, url: str, pacer: Pacer) -> tuple[bytes, str]:
    """Fetch one image through the pacer, or raise the token that says why not.

    Async throughout and never blocking the event loop (AD-11). Every outbound image byte passes
    through this function and the :class:`Pacer` it is handed, a required parameter so no
    signature fetches unpaced. Every upstream outcome (a refused URL, a transport failure, the
    deadline, any non-2xx status including a redirect, a non-image or SVG body, an oversized or
    empty body) collapses to one token, and nothing here returns a substitute image (AD-11).

    The queue wait sits **outside** the whole-exchange deadline: :data:`_FETCH_TOTAL_SECONDS`
    bounds a conversation with an upstream, and a request that has not started has none. The
    allow-list is checked before the pacer is entered, so a refused URL costs no permit or turn.

    Args:
        client: The shared outbound client from :func:`build_image_client`.
        url: The URL taken from the card row, used verbatim (the query is a cache-buster).
        pacer: The application's one :class:`Pacer`. Required, never defaulted.

    Returns:
        The image bytes and the upstream's ``Content-Type``, echoed unchanged: the size key does
        not imply the type (``png`` resolves to a ``.jpg`` URL on three real cards).

    Raises:
        CompanionError: ``image_fetch_failed``, for every reason above.
    """
    if not is_fetchable(url):
        logger.warning(
            "Refusing to fetch a card image from a disallowed origin: %s", _refused_host(url)
        )
        raise CompanionError("image_fetch_failed")

    async with pacer.slot():
        return await _fetch_within_deadline(client, url)


async def _fetch_within_deadline(client: httpx.AsyncClient, url: str) -> tuple[bytes, str]:
    """Run one already-paced exchange under the whole-exchange deadline.

    Split out so the pacer's ``async with`` visibly wraps the deadline. The ``except`` is narrow:
    ``httpx.InvalidURL`` is not under ``httpx.HTTPError``, and ``except Exception`` would report a
    ``MemoryError`` as a blip.

    Args:
        client: The shared outbound client.
        url: An allow-listed URL, already checked by the caller.

    Returns:
        The image bytes and the upstream's own ``Content-Type``.

    Raises:
        CompanionError: ``image_fetch_failed``, for every outcome listed on :func:`fetch_image`.
    """
    try:
        async with asyncio.timeout(_FETCH_TOTAL_SECONDS):
            async with client.stream("GET", url) as response:
                if response.status_code != httpx.codes.OK:
                    logger.info("Card image fetch answered %d for %s", response.status_code, url)
                    raise CompanionError("image_fetch_failed")
                content_type = response.headers.get("content-type", "")
                if not _is_servable_image_type(content_type):
                    logger.warning(
                        "Card image fetch returned %r, not a servable image, for %s",
                        content_type,
                        url,
                    )
                    raise CompanionError("image_fetch_failed")
                declared = response.headers.get("content-length", "")
                if declared.isdigit() and int(declared) > _MAX_IMAGE_BYTES:
                    logger.warning(
                        "Card image at %s declares %s bytes; refusing to read it", url, declared
                    )
                    raise CompanionError("image_fetch_failed")
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > _MAX_IMAGE_BYTES:
                        logger.warning(
                            "Card image at %s exceeded %d bytes mid-stream; abandoning it",
                            url,
                            _MAX_IMAGE_BYTES,
                        )
                        raise CompanionError("image_fetch_failed")
                if not body:
                    # Zero bytes is not a picture; served, it would be cached immutable for a year.
                    logger.warning("Card image at %s returned an empty body", url)
                    raise CompanionError("image_fetch_failed")
                return bytes(body), content_type
    except (TimeoutError, httpx.HTTPError, httpx.InvalidURL) as exc:
        logger.info("Card image fetch failed for %s (%s)", url, type(exc).__name__)
        raise CompanionError("image_fetch_failed") from exc
