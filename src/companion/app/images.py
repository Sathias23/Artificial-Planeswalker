"""Face resolution and the outbound CDN fetch behind ``GET /api/card-image/…`` (AD-11, FR-04).

**This module is where the companion backend stops being self-contained.** Every byte it had
served until story c3-5 came out of a SQLite file on the same disk; this one reaches a machine on
the internet, and everything awkward about it follows from that: a response that is not JSON, an
answer for "the card is fine but the picture isn't", and a dependency that can be slow, absent or
hostile.

Four parts, deliberately separable:

* :func:`resolve_face_images` is **pure** — no session, no client, no I/O. It answers *which of
  this card's image maps does face N mean?*, and it is the single piece of code in the app that
  must never get the face shape wrong. It is unit-tested without a request
  (``tests/unit/companion/test_images.py``) because a rule stated in four docstrings needs one
  place that actually implements it.
* :func:`fetch_image` is the outbound call: allow-list, request, and the mapping of every
  upstream outcome onto one of this story's two answers.
* :class:`Pacer` (c3-6) is the queue in front of it — one semaphore plus request spacing, held
  by the app and passed to every fetch. It is a *rate*, which is the one thing in this module
  whose correctness is timing, and it is why the clock and the sleep are constructor parameters.
* :class:`DiskCache` (c3-7) sits in front of **both** — checked before the pacer is entered, so a
  warm tile costs neither a permit nor a spacing turn. It is the **first code in**
  ``src/companion`` **that writes to the user's disk**, and everything that follows from that is
  on the class itself.

**Why this is a second Scryfall client and not a reuse of the existing one.**
``src/data/importers/scryfall_api.py`` already talks to Scryfall, and
``tests/unit/companion/test_import_boundary.py`` **bans** ``src.data.importers`` from
``src/companion`` outright (AD-2: the bulk write path has no business inside a read model). That
guard is what forces the duplication to be a decision rather than an oversight. The existing
client is prior art to read; the answer to the guard firing is different code, never a wider
allow-list.

**The unpaced window is closed** (c3-6, 2026-08-01). Between c3-5 and c3-6 this route fetched with
no queue in front of it; that window is shut, it was never reached by a browser, and the paragraph
that used to describe it as *"small and UI-less, not closed"* has been replaced by this one rather
than left to read as a live caveat. No code under ``ui/`` fetches an image until **c4-4**, so the
first client this module ever serves will find the pacer already there.

**The disk cache is here, and the epic's CM-2 criterion is satisfied** (c3-7, 2026-08-01). *"An
image fetched once is not fetched again within the cache lifetime"* — the one acceptance criterion
in this epic that another story had been waiting on. c3-6's docstring homed it here by name and
recorded plainly that it did not satisfy it; :class:`DiskCache` now does, and
``test_routes_card_image.py`` asserts it on the recorded fetch count rather than on a second
``200``. The cache directory under ``data_dir()`` is created by the **lifespan**, never by
``build_app()``, which still creates no directory and resolves no data path (AD-10) — see
:func:`cache_root` for why that distinction survives being obvious.

**What is deliberately NOT here**, so the absence reads as a decision rather than an omission:

* **no in-flight coalescing** — **declined a second time and re-homed on c3-8** (Q5, Brad
  2026-08-01). Two *simultaneous* requests for the same key each get their own fetch and each
  write; on Windows the loser's ``os.replace`` may raise ``PermissionError``, which is a log line
  rather than a failed request. c3-6 declined it for a reason this story resolved — *"whether that
  result is bytes, a disk path or a ``Future`` depends entirely on what c3-7 builds"* — and the
  answer is bytes on disk, so the question was genuinely open here for the first time. **It is
  declined on a different ground than c3-6's**: c3-8 needs the same structure for a different
  purpose (*"is a fetch for this key already in flight, or already known-failed?"*), so building
  the in-flight half here would leave c3-8 either inheriting a map shaped only for successes or
  replacing it. One mechanism, built once, by the story that can see both halves. Measured cost of
  declining, today: **zero extra fetches** on both 99-distinct-id decks, because duplicate
  printings collapse in ``deck_cards`` before they reach the route. **c6-4**'s suggestion rows
  beside the deck grid are the first surface that renders one card id twice on one screen, and
  that is the trigger that flips the answer.
* **no eviction, no size accounting, no TTL and no index** — the cache is unbounded in MVP
  (AD-11); the documented location and the removal command are **c8-2**'s. See :class:`DiskCache`.
* **no negative cache and no backoff** — story **c3-8**. A failure is answered and forgotten;
  the wire vocabulary it needs (``image_fetch_failed``) is already paid for, so c3-8 is pure
  behaviour with no schema change.

Building **any** hook, registry or placeholder for those is out of scope on c3-4's precedent: *an
unused hook is a design decision made by a story that cannot see the requirements.*
"""

import asyncio
import logging
import os
import tempfile
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from contextlib import asynccontextmanager, suppress
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

``immutable`` is safe here for a reason that is no longer a forward reference: :class:`DiskCache`
keys on id + size + face and **accepts serving a stale image** when a data refresh changes the URL
(AD-11), so a browser cache adds no new staleness class — it only removes repeat traffic. The
stored URLs carry a ``?<timestamp>`` cache-buster which is deliberately *not* part of that key, and
``test_routes_card_image.py`` now measures that end to end rather than describing it: a stored
row's ``image_uris`` are moved to a new ``?<timestamp>`` between two requests and the second still
hits the existing entry with zero fetches (review 2026-08-01 — the earlier unit-level assertion
was true by ``DiskCache.read``'s own signature, which takes no URL and so could not fail on one).
The two caches therefore accept **the same** staleness for the same reason, which is what makes
stacking them free.

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
one tile twenty seconds rather than holding a connection — **and, since c3-6, a pacer slot** —
open indefinitely. That is now the sharper of the two reasons: a stuck fetch holds one of only
:data:`FETCH_CONCURRENCY` permits, so without this bound a handful of pathological responses could
close the whole choke point rather than merely leak sockets.

**The queue wait is deliberately OUTSIDE this deadline** (Q4, Brad 2026-08-01). It bounds *a
conversation with an upstream*, and a request still waiting its turn has no conversation to bound.
Inside it, the last tile of a cold 99-tile deck would queue for ~9.8 s and then be given ~10 s to
complete a fetch it had not started — failing its own budget for a reason that has nothing to do
with the upstream. :func:`fetch_image` enters the pacer first and this deadline second, and the
nesting is visible in the code rather than resting on a reader counting indentation.
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

FETCH_SPACING_SECONDS = 0.1
"""The minimum gap between two outbound fetch **starts**, process-wide (AD-11, c3-6).

**This number is a good-citizen and NFR-05 budget choice, not compliance, and the distinction is
the point.** Scryfall asks consumers for sustained traffic under 10 requests/second with 50-100 ms
between calls — but that guidance covers ``api.scryfall.com``, and the ``*.scryfall.io`` file
origins this route actually fetches from are **explicitly exempt from it**. Presenting 0.1 s as
adherence to a rule that does not apply here would be documentation asserting a protection the
situation never required.

So the justification is arithmetic, twice over:

* it is the **conservative end** of the band Scryfall publishes for the endpoints it does govern —
  a deliberate posture toward a host this project does not own and does not pay for; and
* it **is** the epic's own acceptance observation. A real 100-card deck resolves to 67-99 distinct
  card ids (measured over the 18 saved decks with >=90 cards; basic lands collapse), the grid asks
  for face 0 only, and 99 tiles x 0.1 s = **9.9 s** against the epic's *"roughly 12 MB over roughly
  10 seconds"*. The 12 MB half is the same arithmetic from the other side: 12 MB / 99 tiles is
  ~124 KB, a Scryfall ``normal`` JPEG.

Spacing is measured between **starts**, never between completions. Completion-based spacing
degrades into serialisation the instant the CDN slows down, which is the opposite of what
:data:`FETCH_CONCURRENCY` is for.

Not configurable by environment: nothing needs it in MVP, and a knob is a supported interface.
"""

FETCH_CONCURRENCY = 4
"""How many image fetches may be open against the CDN at once, process-wide (AD-11, c3-6).

**This is the half the spacing structurally cannot do**, and at ordinary latency it never binds at
all. Steady-state throughput for spacing ``S``, cap ``N`` and per-fetch latency ``L`` is
``min(1/S, N/L)``:

* at a normal ``L`` of ~0.2 s, ``min(1/0.1, 4/0.2)`` is ``min(10, 20)`` — the **spacing** wins and
  this constant is inert;
* at a degraded ``L`` of 2 s, ``min(10, 2)`` — the **cap** wins, the rate falls to 2/s, and at most
  four sockets are held. Uncapped, the same 99-tile burst would hold roughly twenty.

That asymmetry is the entire justification: **a struggling upstream should receive less traffic,
not the same traffic spread over more connections.** The two constants therefore bind under
different conditions and neither substitutes for the other — collapsing them into one number
satisfies neither.
"""

CACHE_DIRECTORY_NAME = "image_cache"
"""The cache's one directory, directly under :func:`src.paths.data_dir` (AD-11, NFR-09).

A **name**, never a resolved path — see :func:`cache_root` for why that distinction is
load-bearing. The documented location, the removal command and the uninstall notes that quote it
are **c8-2**'s (epic ``:3185-3212``); what this story owes that one is a measured footprint, which
is recorded on :class:`DiskCache`.
"""

CACHE_MEDIA_TYPES: dict[str, str] = {".jpg": "image/jpeg", ".png": "image/png"}
"""Extension → media type: the closed two-member map a warm hit answers from (Q4).

**Measured, and the measurement is the whole justification.** Across all **245,760** stored image
URLs in the shipped 38,261-card corpus exactly two extensions occur — ``.jpg`` and ``.png`` — so a
two-entry map covers the corpus completely. Note the honest limit of that, which c3-2's review
earned the hard way: it is a true count of *this* corpus, not a promise Scryfall makes. So it
justifies an explicit map; it does **not** justify code that raises or corrupts on a third
extension, and it is not published to the wire. A pair this map cannot name is simply **not
cached** — see :func:`cache_extension`.

**Never** ``mimetypes.guess_type``. ``spa.py``'s docstring documents why in this project's own
words: on Windows it consults the **registry**, which any installed application can rewrite, and
``mimetypes.init()`` discards prior ``add_type`` calls. A media type that varies by what the user
installed is not a media type this app can stand behind.

This map is also the read's candidate list. The cache key is id + size + face and the extension is
*not* part of it, so a read does not know which spelling its entry landed under and tries each in
turn — which is the second reason the set has to be small, closed and stated here.
"""

_EXTENSION_BY_MEDIA_TYPE: dict[str, str] = {media: ext for ext, media in CACHE_MEDIA_TYPES.items()}
"""The reverse of :data:`CACHE_MEDIA_TYPES`, derived rather than written twice."""


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

    This is **not** the pacer and it did not grow into one. c3-6 shipped :class:`Pacer` as a
    separate object that wraps *calls to* this client — :func:`fetch_image` enters a pacer slot and
    then issues the request — so nothing about the client's construction, transport or timeouts
    knows the rate exists. That separation is what keeps the ``transport=`` seam below meaning
    exactly one thing, and it is why a test can substitute a fictional socket layer without
    substituting the pacing, or vice versa. Keep it: a transport-level pacer would silently pace
    anything else this client is ever used for.

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


class Pacer:
    """The one choke point every outbound image fetch passes through (AD-11, c3-6).

    **Two mechanisms, not one, because they bind under different conditions** — see
    :data:`FETCH_SPACING_SECONDS` and :data:`FETCH_CONCURRENCY` for the arithmetic. A semaphore
    caps how many fetches are *open*; a turnstile spaces how often one may *start*. A design that
    collapses them into a single number satisfies neither requirement.

    **Order matters and is the easy thing to get backwards.** The permit is taken **first** and the
    spacing turn **second**, so the turn is claimed immediately before the request goes out. The
    other order looks identical and paces nothing under load: turns would be consumed by tasks
    still queuing for a permit, and by the time one started, its spacing had long expired. (c3-5's
    review theme in this story's costume — a check that runs after the thing it was meant to
    prevent reads exactly like one that works.)

    **What is defence and what is necessity**, in the manner of
    :class:`~src.companion.app.deps.Database`'s lock docstring, because the two mechanisms are not
    equally load-bearing today:

    * The **turnstile lock is necessity.** It is what makes the spacing *global*: without it, two
      concurrent callers would read the same cursor, both conclude they may start now, and both
      start now.
    * The **semaphore is defence, and is measurably inert under the shipped constants.** At the
      normal latency this route sees it never blocks — the spacing admits work more slowly than
      four concurrent fetches can retire it. It exists for the degraded case the spacing cannot
      see, and it is kept because that case is exactly when restraint matters and exactly when
      nobody is watching. ``test_images.py`` pins both the inertness (as arithmetic) and the
      binding (against a stalled CDN).

    **Constructing one is free and cannot fail**: ``asyncio.Semaphore`` and ``asyncio.Lock`` no
    longer bind an event loop at construction on Python 3.10+, which this repo already relies on —
    ``deps.Database`` creates its lock outside any running loop for the same reason. So a pacer can
    be created in the lifespan beside the client without widening the startup surface that
    ``test_app.py::test_startup_failure_propagates`` pins.

    **One per app, which is not literally one per process, and that is deliberate.** AD-11 says
    *one backend-global semaphore*; a module-level singleton would be the literal reading and is
    rejected on ``Database``'s own shipped ruling against globals that *"would serialise unrelated
    apps in a test run and hide a real double-creation bug behind a global"*. A test suite that
    builds forty apps gets forty pacers and no cross-test timing debt. What AC 2 actually gates is
    that ``src/companion`` contains exactly **one construction site**, which is the property that
    makes "no caller can route around it" true.

    Nothing here needs closing, so :func:`~src.companion.app.main._shutdown` is untouched by it.

    Args:
        spacing: Seconds between fetch starts. Defaults to :data:`FETCH_SPACING_SECONDS`.
        limit: Simultaneous fetches allowed. Defaults to :data:`FETCH_CONCURRENCY`.
        clock: The monotonic time source, in seconds. Injected so a test can assert **exact**
            start offsets at zero wall-clock cost (c3-6 AC 9) — a rate proved by measuring elapsed
            real time is slow when it passes and mysterious when it fails on a loaded box. The
            route never passes this; only tests do.
        sleep: The awaitable delay. Injected alongside *clock* and for the same reason. It must be
            asynchronous: a synchronous sleep here would pace correctly and stall every other
            request in the process while it did.

    Example:
        >>> Pacer().available_permits == FETCH_CONCURRENCY
        True
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
        # None rather than a number: a cold process must paint its first tile immediately, and
        # any sentinel drawn from the clock's own scale would be a guess about its epoch.
        self._next_start: float | None = None

    @property
    def available_permits(self) -> int:
        """How many fetches could start right now without waiting for one to finish.

        Exposed for the cancellation tests, which assert the count returns to where it started —
        a permit leaked per cancelled request is a pacer that narrows over a session of scrolling
        until it serves nothing.
        """
        # `_value` is asyncio.Semaphore's own counter. Read-only, and read here rather than
        # tracked separately so the assertion cannot drift from the thing it claims to measure.
        return self._capacity._value

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        """Hold one fetch's place: a permit for its duration, and a spaced start.

        The permit is held for the **whole exchange**, which is what makes
        :data:`FETCH_CONCURRENCY` a bound on simultaneously open requests rather than on how fast
        they are issued.

        ``async with`` on both primitives is what makes cancellation safe (AC 7): a manual
        ``acquire()``/``release()`` pair around an ``await`` leaks a permit on ``CancelledError``,
        and a browser navigating away from a deck view is exactly that cancellation, ~99 times.

        Yields:
            None — the caller may issue its request for the duration of the block.
        """
        async with self._capacity:
            await self._wait_for_turn()
            yield

    async def _wait_for_turn(self) -> None:
        """Block until this caller may start, then claim the next slot in the queue.

        The lock is held **across** the wait on purpose, and that is what makes the queue
        first-come-first-served: ``asyncio.Lock`` wakes waiters in arrival order, so callers take
        their turns in the order they asked for them rather than racing on a shared cursor.

        The cursor is advanced **after** the wait, never before. A caller cancelled mid-wait
        therefore surrenders the turnstile without having moved the cursor: the next caller still
        spaces itself from the last start that actually happened, but no slot is claimed for the
        start that never did — cancellations cannot accumulate dead air. (Not "starts
        immediately", as an earlier version of this sentence said: the mid-cancellation test
        asserts exactly one spacing from the last real start; review 2026-08-01.)
        """
        async with self._turnstile:
            now = self._clock()
            if self._next_start is not None and self._next_start > now:
                await self._sleep(self._next_start - now)
                # Re-read rather than assume: a real sleep may overshoot, and pacing from the
                # actual start keeps the gaps honest instead of accumulating drift.
                now = self._clock()
            self._next_start = now + self._spacing


def image_pacer(app: FastAPI) -> Pacer | None:
    """Return the pacer the lifespan created for *app*, or ``None`` if it never ran.

    Mirrors :func:`image_client` exactly, including what absence means: *the lifespan did not run*,
    which is a wiring bug rather than a served state, and the caller reports it as
    ``internal_error`` rather than fetching unpaced.

    Args:
        app: The application to read.

    Returns:
        The shared pacer, or ``None``.
    """
    # Annotated local rather than `return getattr(...)`: app.state is Any, and warn_return_any
    # would flag returning it directly.
    pacer: Pacer | None = getattr(app.state, "image_pacer", None)
    return pacer


def cache_root() -> Path:
    """Return the image cache's root directory, resolved **at call time**.

    Resolved at call time and **never at import, never as a default argument** — the same rule,
    and the same reason, as :func:`src.companion.discovery.discovery_path`:
    :func:`src.paths.data_dir` ends in ``mkdir(parents=True, exist_ok=True)``, so a module-level
    ``_CACHE_ROOT = paths.data_dir() / CACHE_DIRECTORY_NAME`` would create the user's data
    directory merely by **importing** this module — and ``build_app()`` imports it. That would
    break AD-10's inertness guarantee from a line that looks like a constant.
    ``test_images.py::TestNoDataPathIsResolvedAtImportTime`` gates both spellings.

    Calling through ``src.paths`` rather than ``platformdirs`` or a hardcoded ``~/…`` is also what
    makes ``PLANESWALKER_DATA_DIR`` work here, which is what gives every test in this package a
    private cache for free (``conftest.py``'s autouse ``isolated_data_dir``).

    Returns:
        ``src.paths.data_dir() / CACHE_DIRECTORY_NAME``. The **data** directory is created as a
        side effect of resolving it; this directory itself may or may not exist yet.
    """
    return paths.data_dir() / CACHE_DIRECTORY_NAME


def cache_extension(content_type: str) -> str | None:
    """Decide which extension a fetched image is stored under — **never from the size key**.

    The size key is not available to this function *by construction*: it takes the response's
    ``Content-Type`` and nothing else, so the defect this rule exists to prevent cannot be
    written here. That defect is silent rather than loud: ``png`` resolves to a ``.jpg`` URL on
    **three real cards** (Sparkspitter, Ondu Champion and Gorehorn Minotaurs, whose ``png`` entry
    is ``https://errors.scryfall.com/soon.jpg``, served as ``image/jpeg``), so a filename of
    ``png_0.png`` holding JPEG bytes would be served with the wrong media type forever and would
    corrupt a cache rather than fail one.

    **The header is the only source, and the URL is deliberately not consulted** (review D1 +
    Greptile P1, 2026-08-01/02). The header, because the cold path serves it verbatim (c3-5's
    ruling: *what the upstream said about its own bytes is more accurate than anything derived
    elsewhere*) — deriving the stored spelling from the same source is what makes a warm hit
    agree with the cold answer on the media type, always. The URL not even as a fallback, because
    every response that reaches the cache has already passed ``_is_servable_image_type`` and
    therefore carries an ``image/*`` header — so a header outside the two-entry map is never
    ``application/octet-stream`` noise, it is a **different image format** (``image/webp``), and
    a ``.jpg`` suffix under it would store webp bytes to be re-served as ``image/jpeg`` under
    ``nosniff`` + ``immutable`` for a year. The first shipped version let the URL win and the
    review inverted it; the fallback then re-opened the same hole one branch deeper, and Greptile
    caught it. A header this map cannot name means *served, not cached*.

    Args:
        content_type: The ``Content-Type`` the upstream sent, parameters and all.

    Returns:
        A member of :data:`CACHE_MEDIA_TYPES`, or ``None`` when the header names none — in which
        case the image is **served and not cached**. Not an error and not a guess: a third
        format is a fact about the corpus changing, not a request failure, and writing it under an
        invented extension is how a cache starts lying about its own contents.

    Example:
        >>> cache_extension("image/jpeg")
        '.jpg'
    """
    media_type = content_type.split(";", 1)[0].strip().lower()
    return _EXTENSION_BY_MEDIA_TYPE.get(media_type)


def _cache_path(root: Path, card_id: str, size: str, face: int, extension: str) -> Path:
    """Build AD-11's cache path: ``<root>/<id[0:2]>/<id>/<size>_<face>.<ext>``.

    **The two-hex shard is measured, not chosen.** Card ids are Scryfall uuid v4s, so their first
    two hex characters are uniform: all **256** shards are used by the shipped corpus, at
    **107-218** cards each (mean 149.5), against a flat **38,261** card directories — the
    "roughly 60,000 entries in one directory" problem AD-11 names.

    The filename is only ever **constructed, never parsed back**, and that is a rule rather than a
    coincidence: ``art_crop`` and ``border_crop`` contain underscores, so ``<size>_<face>`` yields
    ``art_crop_0.jpg`` and a naive ``rsplit("_")`` on it is ambiguous. Nothing in this module
    attempts the reverse, and nothing should.

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


# ---------------------------------------------------------------------------------------------
# The two synchronous file-I/O primitives.
#
# Both are deliberately plain `def`, and both are reached from the async path ONLY through
# `asyncio.to_thread` (Q2, Brad 2026-08-01). AD-11 says the image path is "async throughout — it
# must never block the event loop", and a synchronous file call satisfies every functional test
# in this repository while contradicting that sentence, which is exactly why the rule is
# structural here and gated in `test_images.py::TestFileIoNeverRunsOnTheLoop` rather than trusted.
#
# The numbers, measured on this machine (Task 0, 200 iterations, 124 KB): a read is **4.97 ms**
# and an atomic write **0.46 ms**, against an `asyncio.to_thread` hop of **0.13 ms**. The READ is
# the expensive half — 11x the write — so a warm 99-tile deck paint would block the loop for
# ~0.49 s inline, twice NFR-05's whole 250 ms push budget, from the path the cache exists to make
# fast. The thread hop costs ~38x less than the read it moves.
# ---------------------------------------------------------------------------------------------


def _read_cached(root: Path, card_id: str, size: str, face: int) -> tuple[bytes, str] | None:
    """Read this key's entry off disk, trying each known extension in turn.

    The key is id + size + face — the extension is *not* part of it — so a reader does not know
    which spelling the writer chose and asks for each member of :data:`CACHE_MEDIA_TYPES`.

    **Every failure is a miss**, which is the whole failure posture of this cache in one function:
    a missing file, an unreadable one, a cache root that turns out to be a *file*, an entry of
    zero bytes and an entry over :data:`_MAX_IMAGE_BYTES` all return ``None`` and cost the caller
    one ordinary fetch. Zero bytes is not a picture (c3-5's Greptile P1 in the cache's costume) —
    served, it would be stamped immutable for a year as a permanently broken tile. The ceiling is
    the same one the fetch path enforces on the wire: nothing this cache's own writer stores can
    exceed it, so an oversized file is by definition not this app's work and is not trusted with
    a year-long ``immutable`` stamp either (review 2026-08-01).

    An ordinary miss is silent; anything else logs, because "the cache is quietly doing nothing"
    is a state a user should be able to find in a log rather than infer from a slow app.

    Args:
        root: The cache root.
        card_id: The printing uuid.
        size: The requested rendition.
        face: Which of the card's images was asked for.

    Returns:
        The stored bytes and the media type implied by the extension they were found under, or
        ``None`` for a miss.
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


def _write_atomically(target: Path, payload: bytes, *, displaces: tuple[Path, ...] = ()) -> None:
    """Write *payload* to *target* so no reader can ever observe a partial file.

    ``discovery.write_discovery`` is the template and its reasoning is **inherited rather than
    re-derived** — read that docstring for the full argument. In brief:
    :func:`tempfile.mkstemp` rather than a fixed ``.tmp`` name, so two writers cannot splice one
    file; the temp file in **the target's own directory**, because ``os.replace`` is atomic only
    within one filesystem; ``os.replace`` rather than ``os.rename``, because the latter raises
    ``FileExistsError`` over an existing file on Windows; :func:`os.fdopen` under a
    ``BaseException`` guard, because ``fdopen`` takes ownership of the descriptor only on success
    and a leaked one would also hold the temp file against the unlink on Windows; and cleanup
    under ``contextlib.suppress(OSError)``, so a cleanup failure never displaces the real error.

    **Two of that function's decisions are deliberately NOT copied, and the difference is the
    point in both cases:**

    * **No** ``os.fsync``\\ **.** *Atomic* means a reader never sees a partial file, and temp +
      ``os.replace`` delivers that on its own — the rename is what makes the bytes visible under
      the real name. *Durable* means the file survives a power cut, which is what ``fsync`` buys,
      and a cache entry lost to a power cut costs exactly one refetch. The discovery file is
      different in precisely the way that matters: it is a rendezvous whose loss leaves a running
      app unreachable, and it is written once per process rather than ~99 times per deck. The
      cost is measured, not asserted: ``fsync`` is **2.909 ms** against this write's **0.460 ms**
      (Task 0, 200 iterations, 124 KB) — 6.3x, or 0.288 s of forced flushes on a cold 99-tile
      deck. The ruling would stand at any price; the number is corroboration, not the reason.
      **"Atomically written" is routinely read as "fsynced", so it is said here in both
      directions** rather than left for a reader to assume the stronger one (c3-4's review theme:
      prose outrunning code, in the direction that flatters).
    * **No** ``os.chmod``\\ **.** That call protects a *credential* — discovery's file holds the
      agent token. These are public card images from a public CDN; the per-user
      ``%LOCALAPPDATA%`` directory they sit in is the whole protection they need, and a
      POSIX-only permission call on 99 files per deck would be ceremony rather than defence.

    The per-card directory is created here rather than at startup, and that is the *incidental*
    ``mkdir`` — AD-11's acceptance criterion names the **root**, created once by the lifespan
    (:func:`build_image_cache`). Conflating the two makes the AC look either unsatisfied or
    over-satisfied.

    Any *displaced* sibling entries are removed **before the replace, not after** (review
    2026-08-01, ordering per Greptile P1 2026-08-02): the key excludes the extension, so one key
    can legitimately hold ``normal_0.jpg`` **and** ``normal_0.png`` across a format change — and
    :func:`_read_cached` probes extensions in fixed order, so without this step a stale entry
    under the earlier extension would permanently shadow the fresh one just written. The ordering
    is what makes two concurrent writers of *different* extensions safe: each writer's unlink
    precedes its own replace, so for **both** fresh entries to end deleted would need each
    replace to precede the other — a contradiction. At least one committed entry always
    survives; unlink-after-replace allowed an interleaving that deleted both. The cost of the
    ordering is one narrow branch — siblings unlinked, then the write itself fails — which
    degrades to the standard one-refetch miss. A failed unlink is logged and not raised: the
    shadowing it leaves behind is the pre-existing degrade, not a new failure.

    Args:
        target: The final path, from :func:`_cache_path`.
        payload: The image bytes to store.
        displaces: Sibling paths this write supersedes — the same key under the other extensions.

    Raises:
        OSError: The directory could not be created, the temp file could not be written, or the
            replace failed. The caller — :meth:`DiskCache.write` — swallows and logs it: a cache
            failure is never a request failure (AC 9).
    """
    directory = target.parent
    directory.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(dir=directory, prefix=f"{target.name}.", suffix=".tmp")
    temp_path = Path(temp_name)
    try:
        try:
            handle = os.fdopen(descriptor, "wb")
        except BaseException:
            # fdopen only takes ownership of the descriptor on success; without this close the
            # descriptor leaks, and on Windows it would also hold the temp file against the unlink.
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
        os.replace(temp_path, target)
    except BaseException:
        # The cleanup itself can fail (Windows: an AV/indexer briefly holding the fresh temp file
        # open) — that must not displace the original exception, which names the real problem.
        with suppress(OSError):
            temp_path.unlink(missing_ok=True)
        raise


class DiskCache:
    """The sharded, atomically written, unbounded disk cache behind the image route (AD-11).

    **This is the first code in** ``src/companion`` **that writes to the user's disk**, and that
    fact deserves to be stated where a reader will find it rather than inferred. AD-2 makes
    ``src/mcp_server`` the sole writer and ``tests/unit/companion/test_import_boundary.py``
    enforces it — but that guard is about the **database**: it bans repository write methods,
    session mutators, DML constructs and schema creation, and it *explicitly permits* file I/O
    (its own clean case is named ``file-flush-in-atomic-write``, added for ``discovery.py``'s
    temp+rename). So the one test whose name promises the companion never writes stays green while
    this class writes roughly 12 MB per deck viewed. The boundary is real and it is a different
    boundary; nothing here opens a database write path.

    **What it satisfies.** The epic's **CM-2** — *"an image fetched once is not fetched again
    within the cache lifetime"* — which c3-6 homed here by name and which is the only one of this
    epic's acceptance criteria another story had been waiting on.

    **The key is id + size + face, and the URL is deliberately not part of it** (AD-11). Two
    consequences, both intended:

    * three different cards that happen to share one URL are three entries and three fetches —
      true today of the ``errors.scryfall.com`` placeholder trio; and
    * a data refresh that changes a card's stored ``image_uris`` (Scryfall's ``?<timestamp>``
      cache-buster moves) still **hits the existing entry and serves the older picture**. That
      staleness is *accepted* by AD-11, not overlooked: keying on the URL would make every data
      refresh a total cache miss, ~130 MB re-fetched to correct artwork that almost never
      changes. It is asserted and documented here; it is not solved, and there is no TTL.

    **Scryfall asks consumers to cache what they download for at least 24 hours.** An unbounded,
    never-evicting local cache satisfies that by a wide margin — so the absence of a TTL is not an
    oversight of that guidance but a consequence of the key above.

    **No eviction, no size accounting, no TTL, no index** (AD-11, epic ``:1768-1770``). The cache
    is unbounded in MVP and building any hook, counter, manifest or sweep for a future one is out
    of scope on c3-4's ruling: *an unused hook is a design decision made by a story that cannot
    see the requirements.* The documented location and the removal command are **c8-2**'s (epic
    ``:3185-3212``); what this story owes that one is a **measured footprint** rather than
    documentation, so: this user's whole 40-deck library is **1,061 distinct card ids**, roughly
    **130 MB** at one size — where 130 MB is arithmetic over the epic's ~124 KB average, and the
    real-bytes measurement belongs to **c10-3**.

    **Nothing here needs closing**, exactly like :class:`Pacer` — so
    :func:`~src.companion.app.main._shutdown` is untouched by it. Unlike the pacer, **creating one
    can fail**, which is what :func:`build_image_cache` is for.

    Args:
        root: The directory entries live under, already created. Held rather than resolved
            per-call so :func:`src.paths.data_dir` is consulted once at startup rather than on
            the hot path of every image request.

    Example:
        >>> DiskCache(Path("cache")).path_for("00ab", "normal", 0, ".jpg").as_posix()
        'cache/00/00ab/normal_0.jpg'
    """

    def __init__(self, root: Path) -> None:
        self._root = root

    @property
    def root(self) -> Path:
        """The directory this cache's entries live under."""
        return self._root

    def path_for(self, card_id: str, size: str, face: int, extension: str) -> Path:
        """Return where one entry lives — AD-11's path, character for character.

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
        """Return this key's cached image, or ``None`` for a miss.

        The read runs in a worker thread (:func:`asyncio.to_thread`, Q2) so a 124 KB file read —
        measured at **4.97 ms** on this machine, ~11x the cost of the write — never stalls the
        event loop. Measured, because the alternative was defensible on the *assumption* that a
        local read is sub-millisecond and it is not: 99 warm tiles inline is ~0.49 s of blocked
        loop, twice NFR-05's whole push budget.

        Args:
            card_id: The printing uuid.
            size: The requested rendition.
            face: Which of the card's images was asked for.

        Returns:
            The bytes and the media type implied by the extension the entry was found under, or
            ``None`` when there is nothing usable — which the caller answers by fetching.
        """
        try:
            return await asyncio.to_thread(_read_cached, self._root, card_id, size, face)
        except Exception:
            # `_read_cached` already answers every file-layer failure with a miss; this catches
            # the layer above it — `asyncio.to_thread` itself refusing to schedule (interpreter
            # shutdown, a closed default executor). AC 9 does not distinguish: a cache failure of
            # ANY provenance is a fetch, never a failed request (review 2026-08-01).
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
        """Store one fetched image, atomically — and never fail the request for it (AC 9).

        Keyword-only on purpose: five parameters of which three are strings that would silently
        transpose, and a cache written under a transposed key is wrong in a way no test of *this*
        function can see. The URL is deliberately **not** a parameter (Greptile P1, 2026-08-02):
        it is not part of the key, and after D1 it is not part of the extension derivation
        either — an argument a function ignores is a lie in its contract.

        **Every failure is swallowed and logged.** An unwritable directory, a ``PermissionError``
        from ``os.replace`` (the realistic Windows case — another handle open on the target, which
        Q5's declined coalescing makes reachable rather than theoretical), a cache root that is a
        *file*: all of them mean the picture was served and simply not kept. None of them adds a
        reason token — :class:`~src.companion.contracts.ErrorReason` is closed at ten and this
        story adds none.

        Args:
            card_id: The printing uuid.
            size: The requested rendition.
            face: Which of the card's images was asked for.
            content_type: The upstream's own ``Content-Type``, the sole extension source
                (review D1 + Greptile P1): it is what the cold path serves, so deriving the
                stored spelling from it is what keeps warm and cold agreeing on the media type.
            body: The image bytes to store.
        """
        extension = cache_extension(content_type)
        if extension is None:
            # A format outside the measured two. Served, not stored: writing it under a guessed
            # extension would make the cache lie about its own contents, and refusing to serve it
            # would turn a fact about the corpus into a broken tile.
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
            await asyncio.to_thread(_write_atomically, target, body, displaces=displaced)
        except Exception as exc:
            # Broader than `OSError` on purpose: `asyncio.to_thread` itself can refuse to
            # schedule (interpreter shutdown), and AC 9's posture does not depend on which layer
            # failed — the picture was served either way (review 2026-08-01).
            logger.warning(
                "Could not cache the image at %s (%s); it was served but not stored",
                target,
                type(exc).__name__,
            )


def build_image_cache() -> DiskCache | None:
    """Create the cache root and return a cache over it, or ``None`` if that failed (Q6).

    **The lifespan creates the root — never** ``build_app()`` (AD-11, AD-10). This is the
    ``mkdir`` the acceptance criterion names; the per-card ``<id[0:2]>/<id>`` directories are
    necessarily created at write time and are *incidental* (see :func:`_write_atomically`).

    **A failure disables the cache for the process; it does not fail the launch.** That is a
    ruling, and the discriminator is AD-15's own reasoning. Publishing the discovery file stays
    the **only** startup step that may abort a launch, because a half-launched rendezvous leaves
    every agent tool reporting ``app_not_running`` while the app visibly runs, with nothing on
    either surface explaining the contradiction. A missing cache leaves an app that is **fully
    functional** and slower — every request simply fetches, exactly as it did at c3-6. Failing the
    launch over that would be disproportionate in a way the discovery file's failure is not, and
    it would mean editing the ruling ``test_app.py::test_startup_failure_propagates`` exists to
    protect.

    The failure is not merely theoretical, which is why it is caught rather than argued away:
    ``data_dir()`` itself already ``mkdir``\\ s, so a data directory this unwritable would fail
    ``write_discovery`` two lines later anyway — *but* a **file** named ``image_cache`` sitting in
    the data directory is a ``FileExistsError``/``NotADirectoryError`` that discovery sails past
    entirely.

    Returns:
        A cache over a directory that exists, or ``None`` meaning *this process has no cache*.
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

    **This accessor mirrors** :func:`image_client` **and** :func:`image_pacer` **in shape and
    diverges from them in meaning, deliberately.** For those two, ``None`` means *the lifespan did
    not run* — a wiring bug, reported as ``internal_error`` rather than laundered into a fetch
    failure. Here ``None`` is an ordinary served state: either the lifespan did not run, **or** it
    ran and could not create the cache root (Q6). The caller must not distinguish them, because
    the correct response to both is identical and unremarkable — *fetch the image* — and a route
    that answered ``internal_error`` for a missing cache would turn a degradation into an outage.

    Args:
        app: The application to read.

    Returns:
        The shared disk cache, or ``None`` meaning *serve without one*.
    """
    # Annotated local rather than `return getattr(...)`: app.state is Any, and warn_return_any
    # would flag returning it directly.
    cache: DiskCache | None = getattr(app.state, "image_cache", None)
    return cache


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


async def fetch_image(client: httpx.AsyncClient, url: str, pacer: Pacer) -> tuple[bytes, str]:
    """Fetch one image through the pacer, or raise the token that says why not (AC 11-14).

    **Async throughout and never blocking the event loop** (AD-11): no ``requests``, no
    ``httpx.Client``, no ``run_in_executor``, no synchronous socket or file call anywhere on this
    path.

    **Every outbound image byte in this application passes through this function, and since c3-6
    through the :class:`Pacer` it is handed.** The pacer is a required parameter rather than a
    default precisely so that is structural: there is no signature here that fetches unpaced, so a
    future caller cannot forget one (Q1, Brad 2026-08-01).

    Every upstream outcome collapses to the same answer, because they mean the same thing to a
    caller — *the picture is not available right now, and it might be later*: a refused URL, a
    connect or read failure, a whole-exchange timeout, any non-2xx status (which since the
    review ruling includes a redirect — the client does not follow them), a body that is not a
    servable image (foreign markup, or SVG — the one image type that can carry script), a body
    larger than this backend will hold, and a body with no bytes at all — zero bytes is not a
    picture, and served it would be cached immutable as one (Greptile P1, PR #33).
    **Nothing here ever returns a substitute image** (AD-11): no grey rectangle, no 1×1 pixel,
    no generic card back. The client draws UX-DR22's
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

    **The queue wait sits OUTSIDE the whole-exchange deadline** (Q4, Brad 2026-08-01).
    :data:`_FETCH_TOTAL_SECONDS` bounds a *conversation with an upstream*, and a request that has
    not started has no conversation to bound. Inside it, the 99th tile of a cold deck would burn
    its entire 20 s budget queueing and then time out on a fetch that never sent a byte. There is
    deliberately **no ceiling on queueing** in MVP: the natural bound is the caller, since a client
    that disconnects cancels the request and releases the slot, and a ceiling would need either a
    new reason token for a state no consumer can act on differently or a false reuse of the
    transient one.

    The allow-list is checked **before** the pacer is entered, so a refused URL costs neither a
    permit nor a spacing turn: it issues no request, so it owes the rate nothing.

    Args:
        client: The shared outbound client from :func:`build_image_client`.
        url: The absolute URL taken from the card row — never one this app assembled.
        pacer: The application's one :class:`Pacer`. Required, never defaulted — see above.

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

    async with pacer.slot():
        return await _fetch_within_deadline(client, url)


async def _fetch_within_deadline(client: httpx.AsyncClient, url: str) -> tuple[bytes, str]:
    """Run one already-paced exchange under the whole-exchange deadline.

    Split out of :func:`fetch_image` so the pacer's ``async with`` wraps the deadline rather than
    the other way round (Q4) — and so the nesting is visible in the shape of the code instead of
    resting on a reader counting indentation levels.

    Args:
        client: The shared outbound client.
        url: An allow-listed URL, already checked by the caller.

    Returns:
        The image bytes and the upstream's own ``Content-Type``.

    Raises:
        CompanionError: ``image_fetch_failed``, for every outcome documented on
            :func:`fetch_image`.
    """
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
                if not body:
                    # A 200 with an image type and NO bytes passes every check above and would
                    # be served — and then cached IMMUTABLE for a year: a permanently broken
                    # tile arriving through the success door (Greptile P1, PR #33). Zero bytes
                    # is not a picture, so it is honestly a fetch failure, not a success.
                    logger.warning("Card image at %s returned an empty body", url)
                    raise CompanionError("image_fetch_failed")
                return bytes(body), content_type
    except (TimeoutError, httpx.HTTPError, httpx.InvalidURL) as exc:
        logger.info("Card image fetch failed for %s (%s)", url, type(exc).__name__)
        raise CompanionError("image_fetch_failed") from exc
