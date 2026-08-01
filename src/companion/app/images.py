"""Face resolution and the outbound CDN fetch behind ``GET /api/card-image/…`` (AD-11, FR-04).

**This module is where the companion backend stops being self-contained.** Every byte it had
served until story c3-5 came out of a SQLite file on the same disk; this one reaches a machine on
the internet, and everything awkward about it follows from that: a response that is not JSON, an
answer for "the card is fine but the picture isn't", and a dependency that can be slow, absent or
hostile.

Two halves, deliberately separable:

* :func:`resolve_face_images` is **pure** — no session, no client, no I/O. It answers *which of
  this card's image maps does face N mean?*, and it is the single piece of code in the app that
  must never get the face shape wrong. It is unit-tested without a request
  (``tests/unit/companion/test_images.py``) because a rule stated in four docstrings needs one
  place that actually implements it.
* :func:`fetch_image` is the outbound call: allow-list, request, and the mapping of every
  upstream outcome onto one of this story's two answers.

**Why this is a second Scryfall client and not a reuse of the existing one.**
``src/data/importers/scryfall_api.py`` already talks to Scryfall, and
``tests/unit/companion/test_import_boundary.py`` **bans** ``src.data.importers`` from
``src/companion`` outright (AD-2: the bulk write path has no business inside a read model). That
guard is what forces the duplication to be a decision rather than an oversight. The existing
client is prior art to read; the answer to the guard firing is different code, never a wider
allow-list.

**What is deliberately NOT here**, so the absence reads as a decision rather than an omission:

* **no pacer, no concurrency cap** — story **c3-6**. Between this story and that one the route
  fetches unpaced. That window closes inside the same epic, **before any UI client exists**: no
  code under ``ui/`` fetches an image until **c4-4**. The route itself is live from today — an
  agent, ``curl`` or ``/docs`` can drive it — so the window is small and UI-less, not closed
  (review 2026-08-01: the earlier "before any client exists" overclaimed).
* **no disk cache** — story **c3-7**, which also owns the cache directory under ``data_dir()``.
  Nothing here writes a file, and ``build_app()`` creates no directory (AD-10).
* **no negative cache and no backoff** — story **c3-8**. A failure is answered and forgotten;
  the wire vocabulary it needs (``image_fetch_failed``) is already paid for, so c3-8 is pure
  behaviour with no schema change.

Building **any** hook, registry, no-op semaphore or placeholder for those three is out of scope on
c3-4's precedent: *an unused hook is a design decision made by a story that cannot see the
requirements.*
"""

import asyncio
import logging
from collections.abc import Mapping, Sequence
from importlib.metadata import PackageNotFoundError, version
from typing import Literal
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI

from src.companion.app.errors import CompanionError
from src.data.schemas.card import CardFace

logger = logging.getLogger(__name__)

ImageSize = Literal["small", "normal", "large", "png", "art_crop", "border_crop"]
"""The sizes a caller may ask for — a closed set, generated into the schema as an ``enum``.

**Exactly one key-set exists across all 40,960 stored** ``image_uris`` **objects** (35,404
top-level + 5,556 per-face, measured over the shipped corpus): these six, always, never a subset.
So a card that has an image has it in every size, and there is no per-card size negotiation to
model. Note the honest limit of that measurement, which c3-2's review earned the hard way: it is
a true count of *this corpus*, not a guarantee Scryfall makes — so it justifies the absence of a
negotiation branch, and it is not published to the wire as a promise.

``normal`` is the grid's size and the default (FR-19); ``large`` and ``png`` are the detail
panel's; ``art_crop`` is what the legacy viewer used. A value outside the set is
``400 invalid_request`` from the app-wide validation handler, with no code in the route.
"""

DEFAULT_IMAGE_SIZE: ImageSize = "normal"
"""What ``GET /api/card-image/{scryfall_id}`` with no query means: the normal-size front face."""

ALLOWED_IMAGE_HOSTS = frozenset({"cards.scryfall.io", "errors.scryfall.com"})
"""The only hosts this backend will fetch an image from (Q5, Brad 2026-08-01).

An explicit two-member set rather than a suffix match on ``.scryfall.io``/``.scryfall.com``: a
suffix rule fails *open* if the corpus changes under us, and this one fails closed. Both members
are justified by measurement rather than by generosity — of the 245,760 image URLs stored,
**245,742** are ``cards.scryfall.io`` and the other **18** are ``https://errors.scryfall.com/
soon.jpg``, held by exactly three real cards in all six size keys (``Sparkspitter``,
``Ondu Champion``, ``Gorehorn Minotaurs``). Refusing the second host would report a fetch failure
for cards whose data is exactly as Scryfall shipped it.

The row is **data imported from a third party**, so "the database said so" is not a reason to
fetch an arbitrary URL from inside the user's network — the companion runs on the user's machine,
where ``https://127.0.0.1:8765`` and ``https://169.254.169.254`` are both reachable and neither is
an image.
"""

IMAGE_CACHE_CONTROL = "public, max-age=31536000, immutable"
"""What a **successfully served** image is stamped with (Q5, Brad 2026-08-01).

Starlette sets no ``Cache-Control`` at all, which is why this has to be said out loud: without it
every tile is re-requested on every render, and NFR-05's one-second warm render pays for a
hundred round trips it does not need.

``immutable`` is safe here for a reason that was already decided: AD-11 keys the cache on id +
size + face and **accepts serving a stale image** when a data refresh changes the URL, so a
browser cache adds no new staleness class — it only removes repeat traffic. (The stored URLs carry
a ``?<timestamp>`` cache-buster which is deliberately *not* part of that key.)

Byte-identical to ``spa.py``'s ``_IMMUTABLE_CACHE_CONTROL`` and pinned equal to it by
``test_routes_card_image.py``, rather than imported from it: that constant is private to the
static-file surface and the two answer for different things — a fingerprinted asset is immutable
because its name changes, an image is immutable because AD-11 says staleness is acceptable. Same
value, two reasons, one gate so a divergence is visible.

**Failures carry no long-lived caching at all.** ``error_response`` stamps ``no-store`` on every
typed error body feature-wide, so a transient CDN blip cannot become a permanently broken tile in
an open tab.
"""

_ALLOWED_SCHEME = "https"

_ACCEPT = "image/avif,image/webp,image/png,image/jpeg,image/*;q=0.8"
"""What this route wants back. Scryfall expects consumers to send one."""

_IMAGE_CONTENT_TYPE_PREFIX = "image/"

_SVG_MEDIA_TYPE = "image/svg+xml"
"""The one ``image/*`` type that is refused (review 2026-08-01).

SVG is the single member of the image family that can carry script, and this route serves
upstream bytes from the companion's **own origin** — the SPA's origin. A scripted SVG from a
misbehaving or compromised CDN, navigated to directly, would execute there and then be held for a
year by :data:`IMAGE_CACHE_CONTROL`. The corpus makes the refusal free: all 245,760 stored URLs
end in ``.jpg`` or ``.png``, so no real card loses its picture. The success response also carries
``X-Content-Type-Options: nosniff`` (see ``routes/cards.py``) so a browser cannot second-guess a
raster type into something executable.
"""

_FETCH_TIMEOUT = httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0)
"""Per-axis deadlines for one image fetch.

The split is deliberate and follows ``src/companion/client.py``'s measured reasoning: a short
connect so an unreachable CDN costs a fraction of a second, a longer read so a large ``png`` on a
slow link is not mistaken for a dead one. It is **not** copied from that module's values — those
are for a *loopback* probe, where a 1-second connect is generous; this crosses the internet.
"""

_FETCH_TOTAL_SECONDS = 20.0
"""The whole-exchange deadline that :data:`_FETCH_TIMEOUT` structurally cannot provide.

``httpx``'s ``read`` deadline caps the gap **between chunks**, not the duration of the exchange —
a server dripping one byte every second beats it forever. Comfortably above ``connect + read`` so
it never fires on an ordinary slow response, and small enough that a pathological upstream costs
one tile twenty seconds rather than holding a connection (and, from c3-6, a pacer slot) open
indefinitely.
"""

_MAX_IMAGE_BYTES = 16 * 1024 * 1024
"""An upper bound on what this backend will buffer from an upstream it does not control.

The largest stored size is ``png`` at roughly 1 MB, so 16 MB is well over an order of magnitude of
headroom. It exists because the *response* is not ours: without a ceiling, one hostile or broken
upstream can make the companion buffer until the machine swaps, and AD-11's "no substitute image"
rule means the honest answer to an oversized body is a fetch failure, not a truncated picture.

Enforced **while streaming**, not after the fact (review 2026-08-01): the body is read in chunks
and the fetch is abandoned the moment the running total crosses the ceiling — a declared
``Content-Length`` over it is refused before a byte is read. The first cut of this check ran
``len()`` on a body ``client.get()`` had already buffered whole, which made the constant
documentation rather than a defence.
"""


def _user_agent() -> str:
    """Build the descriptive ``User-Agent`` Scryfall asks consumers to send (AC 13, NFR-08).

    Generic agents — ``curl``, a default ``python-httpx``/``python-requests`` — are routinely
    blocked, and "the CDN started 403ing" is a failure nobody would diagnose from a stack trace.
    The version is read from installed metadata rather than hardcoded so a release cannot ship a
    ``User-Agent`` naming the previous one.

    Returns:
        A ``name/version (+url)`` agent string identifying this application.
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
    """Return this card's image maps, in face order — the rule the whole story turns on.

    **Keys on the presence of per-face** ``image_uris``, **never on a layout string** (AD-11,
    FR-04). It cannot do otherwise even if it wanted to: the ``cards`` table has no ``layout``
    column at all (23 columns, verified against the live DDL), and only 66 of the 6,455 stored
    face objects carry one.

    The four shapes the shipped 38,261-card corpus actually contains, and they are exhaustive:

    ==== ================================================================ ======= ==============
    #    Shape                                                              Rows   Resolves to
    ==== ================================================================ ======= ==============
    A    top-level ``image_uris``, ``card_faces`` null                     35,036  one entry
    B    top-level ``image_uris`` **+** faces carrying **no** images          368  one entry
    C    ``image_uris`` null **+ every** face carrying its own map          2,778  one per face
    D    ``image_uris`` null + faces present, no images anywhere               79  nothing
    \\-   ``image_uris`` null **and** ``card_faces`` null                        0  nothing
    ==== ================================================================ ======= ==============

    Shape B is why this function exists and why *"a split card falls out as single-image
    automatically"* is literally true rather than a hopeful phrase: a split, adventure or flip
    card has faces **and** one top-level image, because its halves share one piece of artwork.
    Branching on ``card_faces is not None`` renders nothing for 368 real printings, and the three
    cards with more than two faces are all shape B — so a ``[front, back]`` destructuring is wrong
    on them too.

    The returned list is what the ``face`` parameter indexes, and that single sentence decides
    every awkward case at once: a split card has two faces and **one** image, so ``face=1`` on it
    is out of range rather than "the other half"; a single-faced card serves at ``face=0`` and is
    out of range at ``face=1``.

    Two orderings are pinned here rather than left to the order of the ``if`` statements:

    * **Per-face wins over top-level.** No card carries both (measured: 0), but the per-face map
      is the more specific answer, so if one ever appears it is the one served.
    * **A partially imaged card keeps only its imaged faces, in face order.** No card is partially
      imaged today (a card's faces either all carry images or none do), and this signature cannot
      represent a hole, so the honest reading of "the images this card has, in face order" is the
      one implemented. Recorded because it is unmeasurable rather than because it is likely.

    Args:
        image_uris: The card's top-level image map, or ``None``. An **empty** map resolves to
            nothing rather than to an entry — it can serve no size, so treating it as an image
            would turn a missing picture into a ``KeyError``.
        card_faces: The card's faces, or ``None``.

    Returns:
        A new list of image maps, one per servable face, in face order. Empty when the card has
        no image data anywhere. The maps are copies, so a caller cannot mutate the card's row.

    Example:
        >>> resolve_face_images({"normal": "https://cards.scryfall.io/a.jpg"}, None)
        [{'normal': 'https://cards.scryfall.io/a.jpg'}]
    """
    faces = list(card_faces or ())
    per_face = [dict(face.image_uris) for face in faces if face.image_uris]
    if per_face:
        return per_face
    return [dict(image_uris)] if image_uris else []


def is_fetchable(url: str) -> bool:
    """Return whether *url* is one this backend is willing to request (AC 12).

    Two conditions, both necessary: the scheme is ``https``, and the host is a member of
    :data:`ALLOWED_IMAGE_HOSTS`. Comparison is on the parsed **hostname** — never on a substring
    of the URL — because every cheap spelling of this check is bypassable:
    ``https://cards.scryfall.io.evil.example/x`` ends the right way for a prefix test,
    ``https://evilcards.scryfall.io/x`` for a suffix test, and
    ``https://cards.scryfall.io@evil.example/x`` contains the allowed host verbatim while
    addressing another machine entirely. ``urlsplit().hostname`` lower-cases the host and drops
    userinfo and the port, so **any** explicit port is refused — including a spelled-out ``:443``,
    which does address the same endpoint. That is fail-closed on an unmeasured spelling rather
    than a claim about ports: zero of the 245,760 stored URLs carry one (review 2026-08-01 —
    the earlier "a different port is a different endpoint" was false for the default port).

    Args:
        url: The URL stored on the card row.

    Returns:
        True when the URL may be fetched; False for anything else, including an unparseable one.
    """
    try:
        parts = urlsplit(url)
    except ValueError:
        # A malformed IPv6 literal is the realistic case; a stored value that will not even parse
        # is a refusal, not an exception escaping into a request handler.
        return False
    if parts.scheme != _ALLOWED_SCHEME or parts.port is not None:
        return False
    return (parts.hostname or "") in ALLOWED_IMAGE_HOSTS


def build_image_client(*, transport: httpx.AsyncBaseTransport | None = None) -> httpx.AsyncClient:
    """Construct the shared outbound client (AD-10; created by the lifespan, never at build time).

    **One client for the process, not one per request** (Q5). A deck view asks for ~100 tiles; a
    client per request means a fresh TLS handshake for each of them, which is the difference
    between a polite trickle and a self-inflicted stampede against a host this app does not own.
    It is created in the lifespan beside ``app.state.database`` — the same place every other
    effectful thing is created — and closed in ``_shutdown`` in reverse order. Constructing one
    opens no socket, so ``build_app()`` stays free of side effects either way; what makes the
    lifespan the right home is that **something must close it**, and only the lifespan has a
    teardown.

    This is **not** the pacer and must not grow into one: c3-6 adds its semaphore *around* this
    client, not inside it.

    ``follow_redirects`` is **False** (Brad, review ruling 2026-08-01). The allow-list is checked
    on the *stored* URL; a client that follows redirects would fetch whatever ``Location`` an
    allowed host answered — including ``http://`` or the loopback and link-local addresses
    :data:`ALLOWED_IMAGE_HOSTS` exists to keep this backend away from — with no check at all on
    the hop. Refusing to follow fails closed, exactly as the allow-list itself does, and costs
    nothing against the measured corpus: stored CDN URLs are terminal, and a 3xx therefore
    answers as an ordinary non-200 fetch failure in :func:`fetch_image`.

    ``trust_env`` is left at httpx's default of ``True``, which is a deliberate divergence from
    ``src/companion/client.py``'s ``trust_env=False`` rather than an inconsistency. That module
    probes *loopback*, where honouring ``HTTP_PROXY`` would send a health check to a proxy and
    ``.netrc`` could silently attach an ``Authorization`` header to a local probe. This client
    crosses the public internet, where a user behind a corporate proxy has no other way out — and
    it sends no credential of its own for a ``.netrc`` entry to compete with.

    Args:
        transport: Replaces the network transport. The seam every unit test uses
            (``httpx.MockTransport``), so no test in this package can touch the network — a test
            that would otherwise reach ``cards.scryfall.io`` is a bug in the seam, not a slow test.

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

    Mirrors :func:`src.companion.app.deps.database`: absence means *the lifespan did not run*,
    which is a wiring bug rather than a served state, and the caller reports it as
    ``internal_error`` rather than laundering it into a fetch failure.

    Args:
        app: The application to read.

    Returns:
        The shared outbound client, or ``None``.
    """
    # Annotated local rather than `return getattr(...)`: app.state is Any, and warn_return_any
    # would flag returning it directly.
    client: httpx.AsyncClient | None = getattr(app.state, "image_client", None)
    return client


def _refused_host(url: str) -> str:
    """Name the host of a refused URL for the log, without trusting the URL to parse.

    ``is_fetchable`` returns False for a URL ``urlsplit`` raises on, so this path must survive
    the same ``ValueError`` — the first cut called ``urlsplit`` bare inside the log line and
    turned an unparseable stored value into a 500 (review 2026-08-01).

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
    """Return whether an upstream ``Content-Type`` is one this route will echo.

    The media type (parameters stripped) must be ``image/*`` and must not be
    :data:`_SVG_MEDIA_TYPE` — the one image type that can carry script.

    Args:
        content_type: The header value as the upstream sent it, possibly with parameters.

    Returns:
        True for a servable raster type; False for anything else.
    """
    media_type = content_type.split(";", 1)[0].strip().lower()
    return media_type.startswith(_IMAGE_CONTENT_TYPE_PREFIX) and media_type != _SVG_MEDIA_TYPE


async def fetch_image(client: httpx.AsyncClient, url: str) -> tuple[bytes, str]:
    """Fetch one image, or raise the token that says why not (AC 11-14).

    **Async throughout and never blocking the event loop** (AD-11): no ``requests``, no
    ``httpx.Client``, no ``run_in_executor``, no synchronous socket or file call anywhere on this
    path.

    Every upstream outcome collapses to the same answer, because they mean the same thing to a
    caller — *the picture is not available right now, and it might be later*: a refused URL, a
    connect or read failure, a whole-exchange timeout, any non-2xx status (which since the
    review ruling includes a redirect — the client does not follow them), a body that is not a
    servable image (foreign markup, or SVG — the one image type that can carry script), and a
    body larger than this backend will hold. **Nothing here ever returns a substitute image**
    (AD-11): no grey rectangle, no 1×1 pixel, no generic card back. The client draws UX-DR22's
    named placeholder, which it can, because it already holds the card's name, cost and type line
    from ``GET /api/cards/{card_id}``.

    The body is **streamed against the ceiling**: status, ``Content-Type`` and any declared
    ``Content-Length`` are judged before a byte of body is read, and the running total abandons
    the exchange the moment it crosses :data:`_MAX_IMAGE_BYTES` — an oversized body costs this
    process 16 MB, never the upstream's patience.

    The URL is used **verbatim**, query string and all. Scryfall's ``?<timestamp>`` is a
    cache-buster the URL 404s without, and the ``/front/``–``/back/`` path segment — perfectly
    consistent across all 5,556 imaged faces, measured — is read, never constructed.

    The ``except`` is narrow on purpose. ``httpx.HTTPError`` is the transport family's root;
    ``httpx.InvalidURL`` is **not** under it (it inherits ``Exception`` directly) and is listed
    for the URL that satisfies ``urlsplit`` but not httpx's stricter parser; ``TimeoutError`` is
    what ``asyncio.timeout`` raises and belongs to neither. ``except Exception`` would swallow a
    ``MemoryError`` or a programming error and report it as a CDN blip.

    Args:
        client: The shared outbound client from :func:`build_image_client`.
        url: The absolute URL taken from the card row — never one this app assembled.

    Returns:
        The image bytes, and the ``Content-Type`` the upstream actually sent (which is what the
        route echoes: the stored size key does not imply the extension — ``png`` resolves to a
        ``.jpg`` URL on three real cards). It may carry parameters (``image/jpeg;
        charset=binary``); echoed unchanged, since what the upstream said about its own bytes is
        more accurate than anything derived from the size key.

    Raises:
        CompanionError: ``image_fetch_failed``, for every reason above.
    """
    if not is_fetchable(url):
        # Logged with the host so an operator can see WHICH origin was refused; the host is the
        # actionable part and the rest of the URL is noise.
        logger.warning(
            "Refusing to fetch a card image from a disallowed origin: %s", _refused_host(url)
        )
        raise CompanionError("image_fetch_failed")

    try:
        async with asyncio.timeout(_FETCH_TOTAL_SECONDS):
            async with client.stream("GET", url) as response:
                if response.status_code != httpx.codes.OK:
                    logger.info("Card image fetch answered %d for %s", response.status_code, url)
                    raise CompanionError("image_fetch_failed")
                content_type = response.headers.get("content-type", "")
                if not _is_servable_image_type(content_type):
                    # A captive portal, an upstream error page, an HTML placeholder — or an SVG,
                    # refused by name. Passing any of them through would serve foreign, possibly
                    # scriptable content from the companion's own origin.
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
                return bytes(body), content_type
    except (TimeoutError, httpx.HTTPError, httpx.InvalidURL) as exc:
        logger.info("Card image fetch failed for %s (%s)", url, type(exc).__name__)
        raise CompanionError("image_fetch_failed") from exc
