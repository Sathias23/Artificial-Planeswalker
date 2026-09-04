"""The card-addressed routes: ``GET /api/cards/{card_id}`` and ``GET /api/card-image/…``.

The companion's card-reading routes. Its own module rather than a section of :mod:`.decks`
because the two operations here are siblings — **same identifier, same corpus** — while
``decks.py``'s docstring is written entirely about deck reads. c3-2's docstring predicted this
placement by name, and c3-5 confirmed it (Q1, Brad 2026-08-01): they share the uuid constraint,
the repository call and the row, so splitting them would publish two names for one thing. The
measurement that made it free: adding a route to an **existing** router owes nothing to
``build_app()``'s ordering block and nothing to ``test_spa.py``'s differential router list — both
verified unchanged.

**They do not share a cache story.** The image route caches bytes on disk and serves them with a
year-long immutable lifetime; the card route caches nothing of its own and instead tells the
browser it may hold a card row for an hour (``Cache-Control: private, max-age=3600`` on the ``200``
and on nothing else). ``private`` because the companion is a single-operator loopback app and no
shared cache should ever hold this; an hour because a card row only changes when the local database
is re-imported. Conditional requests (``ETag``/``If-None-Match``) are deliberately **not** added:
they would trade a cheap SQLite read for a round trip, which is the opposite of what the cold open
needs.

**This module holds a lookup and a proxy**, which is a change from c3-2, where it held only a
lookup — the sentence *"there is deliberately nothing here but a lookup"* stopped being true the
moment ``read_card_image`` landed and has been rewritten rather than left to mislead. What is
still true is why: ``CardRepository.get_by_id`` already returns the exact ``Card`` schema **both**
routes need, so AD-1's "no second card shape in this shell" is satisfied by writing no projection
at all — no ``from_deck``-style constructor, no counts, no ``select``, and no image-specific
query. The cost of that, stated rather than optimised: an image request that has to *fetch* reads
the whole card row. A warm disk-cache hit no longer does — see ``read_card_image``.

The **mechanism** behind the image route is not here. Face resolution and the outbound fetch live
in :mod:`src.companion.app.images`, which is where the spine's Structural Seed draws them and
which is what lets the resolver be unit-tested without a request. This module holds the wire
contract: the path, the parameters, the status vocabulary and the cache headers.

The session and both ``503`` paths arrive with :data:`~src.companion.app.deps.DbSession`, and
every token's status lives in :mod:`src.companion.app.errors`.

Bodies are unwrapped (AD-16): the card itself, or the image bytes themselves — no
``status``/``card`` envelope, and emphatically no ``{"image": "base64…"}``.
"""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Path, Query, Request, Response

from src.companion.app.deps import DbSession
from src.companion.app.errors import CompanionError, error_responses
from src.companion.app.images import (
    DEFAULT_IMAGE_SIZE,
    IMAGE_CACHE_CONTROL,
    ImageSize,
    fetch_image,
    image_cache,
    image_client,
    image_pacer,
    negative_cache,
    resolve_face_images,
)
from src.data.repositories.card import CardRepository
from src.data.schemas.card import Card

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

_CARD_ID_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
"""The canonical Scryfall printing uuid, and nothing else (Q2, Brad 2026-07-31).

**Why a pattern and not** ``uuid.UUID``. Typing the parameter ``uuid.UUID`` would accept
32-hex-without-dashes, ``{braced}``, ``urn:uuid:`` and uppercase spellings — and *normalise* them,
turning a malformed id into a **found** card, which is the opposite of what the route promises.
The pattern is the precise instrument: it is exact, it generates a ``pattern`` into the OpenAPI
document the UI can read, and a failure routes through the existing ``validation_error_handler``
as ``400 invalid_request`` with no code here at all.

**Why lowercase-only.** All 38,261 ids in the shipped corpus are canonical lowercase hyphenated
uuids — zero exceptions, measured. Nothing is reachable by normalising an uppercase id that is not
also reachable by sending the id as stored, so accepting one would only ever quietly serve a client
bug. Unlike a deck id — which c3-1 correctly ruled has no declared shape, making every unknown deck
id simply *not found* — a card id has a declared shape, so "malformed" is decidable and gets its
own answer.

**One measured dependency, because it is invisible and it bites.** ``$`` does not mean the same
thing in every engine: Python's ``re`` matches ``$`` *before a trailing newline*, so under
``re`` a request for ``<canonical-id>%0A`` would validate, miss, and answer ``404
card_not_found`` instead of ``400``. Pydantic 2.12 defaults to the Rust engine, where ``$`` is
end-of-input and that spelling is correctly refused (measured both ways, 2026-07-31). Anything
that changes the engine — a ``regex_engine="python-re"`` config, a major-version change in how
Pydantic compiles patterns — silently reopens it, which is why
``test_routes_cards.py`` pins the trailing-newline spelling by name rather than trusting the
anchor. ``\\A``/``\\z`` would state it unambiguously but are not valid ECMA regex, and this
pattern is published into the OpenAPI document for the UI to read.
"""

CARD_CACHE_CONTROL = "private, max-age=3600"
"""How long a browser may hold one card row, and who may hold it.

``private`` keeps the row out of any shared cache: the companion binds to loopback for one
operator, so a proxy caching a card row is never a case this app wants to be correct for.
``max-age=3600`` because the only thing that changes a card row is a local database re-import,
which is a deliberate operator action measured in minutes, not seconds. Stamped on the ``200``
alone — a ``404`` or a ``503`` carries nothing, so a card that arrives with the next import is
never hidden behind a remembered miss.
"""

CardId = Annotated[str, Path(pattern=_CARD_ID_PATTERN)]
"""The path parameter's type: a string, constrained, never parsed into a ``uuid.UUID``.

``str`` rather than ``UUID`` keeps the value byte-identical to the database key all the way to the
``WHERE`` clause. Any conversion is a chance to normalise, and normalising is what
:data:`_CARD_ID_PATTERN` exists to refuse.
"""


@router.get(
    "/cards/{card_id}",
    response_model=Card,
    responses=error_responses("card_not_found"),
)
async def read_card(card_id: CardId, session: DbSession, response: Response) -> Card:
    """Return everything known about one card printing.

    The canonical record behind a printing id: its name, mana cost, converted mana cost, type
    line, oracle text, power and toughness, rarity, set, collector number, colours, keywords,
    format legalities, and its images. Views that were given only an id use this to fill
    themselves in.

    This operation returns the image **URLs** and nothing else about them; where they live on the
    record is stated on the ``image_uris`` and ``card_faces`` fields themselves, and it is not the
    obvious rule. A view that wants pixels asks ``GET /api/card-image/{scryfall_id}`` instead,
    which applies that rule for you.

    ``prices`` is absent from this response, not empty: the local database holds no price data of
    any kind.

    A found card is cacheable by the browser for an hour (``Cache-Control: private, max-age=3600``);
    a card row only changes when the local database is re-imported. Every other answer — including
    ``404 card_not_found`` — carries no cache header at all, so a card that appears after an import
    is never hidden by a remembered miss.

    Warning:
        The ``400`` for a malformed id is not unconditional. Dependencies resolve before
        parameter validation is reported, so a malformed id sent while the database is unusable
        answers ``503`` (``database_not_initialized`` or ``database_unavailable``), not ``400``.
        A caller that retries on 503 must not assume the request can ever succeed: a malformed id
        stays malformed whatever the database does.

    Args:
        card_id: The Scryfall printing uuid — the value in ``cards.id``, and the same value a
            deck's entries carry in ``card_id`` (FR-13). Constrained to the canonical lowercase
            hyphenated spelling by :data:`CardId`; anything else is ``400 invalid_request``,
            answered by the app-wide validation handler rather than by anything here. (A value
            that is not a single well-formed path segment — one containing an encoded ``/``, say
            — never reaches routing's card branch at all.)

            **The mechanism behind the Warning above, measured.** FastAPI solves dependencies and
            collects parameter-validation errors in one pass, raising ``RequestValidationError``
            only afterwards — so ``DbSession`` resolves first and its 503s outrank the 400. Both
            orders are pinned in ``test_routes_cards.py``. (The consumer-facing half moved up
            into the wire-visible ``Warning:`` section at review round 2, 2026-07-31, precisely
            because this ``Args:`` section is truncated off the wire.)
        session: The request-scoped database session (see ``DbSession``).
        response: FastAPI's injected response object, used to stamp ``Cache-Control`` on the
            success path only. Stamped **after** the lookup, so the ``CompanionError`` raised for
            a miss is answered by the app-wide handler's own response, which never sees this one.

    Returns:
        The card, unwrapped.

    Raises:
        CompanionError: ``card_not_found`` when the id is well-formed but no card carries it.
    """
    card = await CardRepository(session).get_by_id(card_id)
    if card is None:
        raise CompanionError("card_not_found")
    response.headers["Cache-Control"] = CARD_CACHE_CONTROL
    return card


_IMAGE_OK: dict[int | str, dict[str, Any]] = {
    200: {
        "content": {"image/*": {"schema": {"type": "string", "format": "binary"}}},
        "description": "The image bytes, in whatever format the CDN served them.",
    }
}
"""The first non-``application/json`` success body in this document, declared by hand.

Four coordinated decisions make a binary 200 work, and FastAPI's default is wrong for all four:
there must be **no** ``response_model`` (one would emit a JSON ``$ref`` for a body that is bytes),
the ``response_class`` must be a plain ``Response`` (``JSONResponse`` would happily serialise the
bytes into a JSON string), this ``content`` block must be declared (without it the document claims
``application/json`` for the success case and the generated TypeScript lies to c4-4), and the
handler's return annotation must be ``Response`` so ``mypy --strict`` is satisfied without FastAPI
inferring a model from it.

``image/*`` rather than an enumeration of media types, because the served type is **the upstream's
own** and is not derivable from the request: the ``png`` size key resolves to a ``.jpg`` URL on
three real cards.
"""


def _image_response(body: bytes, content_type: str) -> Response:
    """Build the one success response both the cold and the warm path answer with.

    **One constructor, so cold and warm cannot drift** (c3-7 AC 8). A cache hit is the same
    success response as a fetch — same status, same ``Cache-Control``, same
    ``X-Content-Type-Options`` — and the way to make that true is to have one place that says so,
    rather than two call sites that happen to agree today.

    ``nosniff`` because the body and its declared type are an upstream's word, not ours: without
    it a browser may sniff a mislabelled body into something executable on this app's own origin.
    ``fetch_image`` already refuses SVG — the one image type that carries script — and this header
    is the belt to that brace (review 2026-08-01).

    The **one** field where the two paths can legitimately differ is ``content_type``, and the
    divergence is bounded to *parameters*: the cold path echoes the upstream's header verbatim
    (``image/jpeg; charset=binary`` and all), while a warm hit derives it from the stored
    extension through ``images.CACHE_MEDIA_TYPES`` and therefore carries the bare media type.
    "Bounded to parameters" is true **by construction**, not by luck: ``cache_extension`` derives
    the stored spelling from the same ``Content-Type`` the cold path served, and from nothing
    else (review D1, 2026-08-01 — the URL suffix used to win, which left a header/suffix
    disagreement free to flip the whole media type between cold and warm; Greptile P1,
    2026-08-02 — the suffix then survived as a fallback, which re-opened the identical flip for
    an accepted-but-unmapped type like ``image/webp``, so the URL is now not consulted at all).
    Named and tested rather than left for c4-4 to discover (Q4, Brad 2026-08-01); no measured
    Scryfall response actually sends a parameter, and no browser behaves differently for one.

    Args:
        body: The image bytes, from the CDN or from disk.
        content_type: The media type to serve them as.

    Returns:
        The success response.
    """
    return Response(
        content=body,
        media_type=content_type,
        headers={"Cache-Control": IMAGE_CACHE_CONTROL, "X-Content-Type-Options": "nosniff"},
    )


@router.get(
    "/card-image/{scryfall_id}",
    response_class=Response,
    responses={
        **_IMAGE_OK,
        **error_responses("card_not_found", "no_image_data", "image_fetch_failed"),
    },
)
async def read_card_image(
    request: Request,
    scryfall_id: CardId,
    session: DbSession,
    size: Annotated[ImageSize, Query()] = DEFAULT_IMAGE_SIZE,
    face: Annotated[int, Query(ge=0)] = 0,
) -> Response:
    """Serve one card face's artwork, from this app's own origin.

    Every image in the app comes through here: the browser never contacts Scryfall directly
    (AD-11, UX-DR36). The URL is read from the card's own row in the local database — **no live
    Scryfall metadata call is ever made** — and the bytes are proxied back with the content type
    the CDN actually sent.

    ``face`` indexes **the images this card has**, not its ``card_faces`` array, and the two are
    different for real cards. A split, adventure or flip card has two faces and **one** image,
    because its halves share one piece of artwork, so ``face=1`` on one of them is out of range
    rather than "the other half"; a single-faced card serves at ``face=0``. Which images a card
    has is decided by the rule stated on ``GET /api/cards/{card_id}``'s ``image_uris`` and
    ``card_faces`` fields — this operation applies it so a caller does not have to.

    Two failures are answered here and they are **not** interchangeable, even though both draw the
    same placeholder. ``404 no_image_data`` is permanent: this card has no artwork for what was
    asked, and asking again cannot change it. ``502 image_fetch_failed`` is transient: the URL was
    known and the fetch did not deliver. Neither ever returns a substitute image — no grey
    rectangle, no 1×1 pixel, no generic card back — because the client can draw a better one from
    the name, cost and type line it already has.

    A successful image is cacheable by the browser for a year; a failure is not cached at all, so
    one bad minute cannot leave a permanently broken tile in an open tab.

    Warning:
        The ``400`` for a malformed id or an unrecognised ``size`` is not unconditional.
        Dependencies resolve before parameter validation is reported, so ``?size=bogus`` sent
        while the database is unusable answers ``503`` (``database_not_initialized`` or
        ``database_unavailable``), not ``400``. A caller that retries on 503 must not assume the
        request can ever succeed: a bad parameter stays bad whatever the database does.

    Args:
        scryfall_id: The Scryfall printing uuid — the same identifier and the same constraint as
            ``GET /api/cards/{card_id}``'s ``card_id`` (:data:`CardId`); the spelling differs
            because the epic names this path ``/api/card-image/{scryfall_id}``. Anything outside
            the canonical lowercase hyphenated shape is ``400 invalid_request`` from the app-wide
            validation handler, with no code here.
        size: Which rendition to serve. ``normal`` is the grid's and the default (FR-19),
            ``large`` and ``png`` the detail panel's. An unrecognised value is ``400
            invalid_request``, again with no code here — the ``Literal`` becomes an ``enum`` in
            the schema, so a generated client cannot misspell one.
        face: Which of the card's images to serve, ``0`` for the first. Out of range is
            ``404 no_image_data``. Deliberately **not** a ``Literal[0, 1]``: two faces is the
            overwhelming case but not the only one, and a closed pair would answer ``400`` where
            "this card simply has fewer faces" is a ``404``. The bound is the resolved list's
            length, so it lives here rather than in the type.
        request: The live request; the shared outbound client is read from its app.
        session: The request-scoped database session (see ``DbSession``).

    Returns:
        The image bytes, with the upstream's ``Content-Type`` and a long-lived ``Cache-Control``.

    Raises:
        CompanionError: ``card_not_found`` when no card carries the id; ``no_image_data`` when the
            card has no image for the requested face and size; ``image_fetch_failed`` when the CDN
            did not deliver one **or when this key is inside the backoff window a recent failure
            opened** (c3-8 — the same token and the same response, deliberately, so a client cannot
            tell a remembered failure from a fresh one and has no reason to);
            ``internal_error`` if the lifespan never ran.
    """
    # THE DISK CACHE IS THE FIRST THING THIS ROUTE CONSULTS, ahead of the database read below.
    #
    # A key only enters the cache through the write at the bottom of this function, which is
    # reachable only after `card_not_found`, `no_image_data` and the size lookup have all passed
    # — so every cached key was validated on the way in, and re-validating it on the way out buys
    # nothing but a database read per warm tile. On a 99-tile warm deck that is 99 row reads to
    # confirm what the file on disk already proves.
    #
    # The one behaviour this trades away, stated rather than hidden: a card whose row is deleted
    # while its tile is still cached is answered `200` from disk instead of `404 card_not_found`
    # until the cache is cleared. Accepted — the row is still consulted on every MISS, so no new
    # key can enter the cache unvalidated.
    #
    # It is also read BEFORE the pacer (c3-7 AC 6, NFR-06). A check inside `pacer.slot()` would
    # cache correctly and pace a warm deck anyway: 99 tiles that never leave the machine would
    # take 9.9 seconds and would hold the CDN's rate budget against requests that issue no request
    # at all. `test_routes_card_image.py` measures that on c3-6's injected clock — a warm burst
    # advances it by ZERO spacing intervals where the cold burst advances it by 98 — rather than
    # asserting this comment.
    #
    # `DbSession` is still a dependency of this handler, so a warm hit against an unusable
    # database is still `503`: dependencies resolve before any line here runs.
    cache = image_cache(request.app)
    if cache is not None:
        cached = await cache.read(scryfall_id, size, face)
        if cached is not None:
            return _image_response(*cached)

    card = await CardRepository(session).get_by_id(scryfall_id)
    if card is None:
        raise CompanionError("card_not_found")

    # The no-image case takes precedence over the out-of-range face case, and it does so
    # STRUCTURALLY rather than by an ordered pair of checks: a card with no images resolves to an
    # empty list, so every face is out of range and this one comparison answers both. They share a
    # token deliberately — AD-11 asks for permanent and transient to be distinguishable, not for
    # two flavours of permanent to be, and the client draws the same placeholder either way. A
    # separate "no such face" token is declined and ledgered.
    resolved = resolve_face_images(card.image_uris, card.card_faces)
    if face >= len(resolved):
        raise CompanionError("no_image_data")
    url = resolved[face].get(size)
    if url is None:
        # Unreachable against today's corpus — a present image map always carries all six sizes
        # (measured over 40,960 objects) — but that is a fact about this data, not a promise
        # Scryfall makes. "No image at that size" is honestly the same answer as "no image".
        logger.info("Card %s face %d carries no %s image", scryfall_id, face, size)
        raise CompanionError("no_image_data")

    # The negative cache is consulted AFTER the disk read and BEFORE the wiring guard, and each
    # half of that placement is a decision (c3-8):
    #
    # * after the disk read (which is now the route's first act), because a key with a warm entry
    #   is served whatever its failure history — the picture is on this machine and no memory of a
    #   past outage should hide it;
    # * before the wiring guard, because a remembered failure needs neither a client nor a pacer,
    #   and asking for them first would report `internal_error` for a request that needs nothing;
    # * OUTSIDE `pacer.slot()`, for the same reason the disk read is (c3-7 AC 6): a request that
    #   issues no request owes the rate nothing. A check placed inside the slot would remember
    #   correctly and still make a remembered failure wait its turn against a CDN it never
    #   contacts — and every functional test in this file would pass. `test_routes_card_image.py`
    #   measures the injected clock rather than the bytes for exactly that reason.
    #
    # What this does NOT fix, stated where a reader will look: the FIRST paint against a dead CDN
    # still issues all ~99 requests and still takes ~124 s at min(1/0.1, 4/5.0) = 0.8 fetches/s,
    # because 99 distinct keys have nothing remembered yet. The pacer bounds that paint; this
    # bounds every one after it, which is what EXPERIENCE.md's "no request storms" means here.
    #
    # What a remembered answer still costs, also stated: everything ABOVE this line — a database
    # session, the card read and the face resolution — runs on every request that MISSES the disk
    # cache, remembered or not, because the token fidelity of `card_not_found` and `no_image_data`
    # requires the row before the failure history may speak. "Answered from memory" is true of the
    # CDN, not of the DB. A warm hit skips all of it.
    remembered = negative_cache(request.app)
    if remembered is not None and remembered.is_backing_off(scryfall_id, size, face):
        # DEBUG, not INFO, and the asymmetry with the record site below is the point (review
        # 2026-08-02): a hit costs nothing and is client-driven, so at INFO a polling SPA
        # repainting a 99-tile deck during an outage would write ~99 lines per paint, every
        # paint, unbounded — the same log-storm class Q4's write counter just closed. The
        # bounded, WORTH-a-line event is the window opening or escalating, logged once at the
        # record site, which a real (paced) fetch failure gates.
        logger.debug(
            "Card %s face %d (%s) is inside its fetch-failure backoff window; answering from "
            "memory without contacting the CDN",
            scryfall_id,
            face,
            size,
        )
        raise CompanionError("image_fetch_failed")

    client = image_client(request.app)
    pacer = image_pacer(request.app)
    if client is None or pacer is None:
        # Unreachable on every supported path — the lifespan always runs before a request is
        # served — but a missing client or pacer is a wiring bug, not a CDN failure, and must not
        # be laundered into image_fetch_failed. Same reasoning as deps.get_session's missing
        # holder. One guard for both because they are created on consecutive lifespan lines and
        # either being absent means the same thing: startup did not happen.
        logger.error(
            "No image client or pacer on the app serving %s; the lifespan did not run",
            request.url.path,
        )
        raise CompanionError("internal_error")

    # Every outbound byte in this application goes through this one call, and since c3-6 through
    # the pacer it is handed — which is what makes AD-11's "exactly one choke point" mechanically
    # true rather than aspirational: there is one call site and it cannot fetch without pacing.
    # The request may queue here; a cold 100-card deck is ~99 tiles at 100 ms apart, so the last
    # one starts ~9.8 s in. That is an EXPECTED observation (NFR-05 excludes first-fetch image
    # paint), it is deliberately not published to the wire, and it is written down for the tile
    # author in ui/README.md's blind-spot section (Q4, Brad 2026-08-01).
    #
    # **The first and only `try`/`except` in this module**, and c3-1's record names its absence as
    # a property — so it is deliberate rather than a quiet growth, and a SECOND one here would be a
    # smell. It is unavoidable under any design: the negative cache is keyed on id + size + face,
    # which `fetch_image` is not given and must not be (widening the one function whose narrow
    # signature is why no caller can fetch unpaced).
    #
    # `except CompanionError`, never `except Exception` (AC 10). Three reasons, in order of weight:
    #
    # * a browser navigating away from a deck view cancels ~99 requests, and recording those would
    #   poison the whole deck for a backoff window over a user action that failed at nothing.
    #   `CancelledError` inherits `BaseException`, so a bare `except Exception` would already miss
    #   it — and this narrower catch cannot see it at all;
    # * a broad catch would record `internal_error` (a wiring bug) as a CDN failure, and back off a
    #   key whose real problem is that the lifespan did not run;
    # * `fetch_image`'s `Raises:` names exactly one token, `image_fetch_failed`, and collapses all
    #   eight upstream causes into it deliberately. That one-token contract is what makes this
    #   catch precise without discriminating on the reason — widening it there means revisiting
    #   this.
    try:
        body, content_type = await fetch_image(client, url, pacer)
    except CompanionError:
        if remembered is not None:
            # One INFO line per RECORD, never per remembered hit (review 2026-08-02): a record
            # is gated by an actual paced fetch failing, so its rate is bounded by the fetch
            # rate — and once the window is open, repeat requests are answered at DEBUG above.
            # The delay is in the line because it is the one number an operator diagnosing a
            # "stuck placeholder" needs and cannot otherwise see.
            delay = remembered.record_failure(scryfall_id, size, face)
            logger.info(
                "Card %s face %d (%s) failed to fetch; backing off for %.0f s",
                scryfall_id,
                face,
                size,
                delay,
            )
        raise

    # One INFO line per PAID network exchange, and its gate is the `fetch_image` call itself —
    # the same gate as the failure line below, so the two lines partition every real CDN fetch
    # between them (17-3). This is CM-2's observation seam: the unit tests prove once-per-key on
    # a recorder, but a real session had no way to show it — a successful fetch logged nothing,
    # so `companion.log` could not distinguish "served warm" from "fetched again". Grouping these
    # lines per (id, face, size) per cache lifetime is how a duplicate is now observable. Warm
    # cache hits and negative-cache refusals return above and add nothing here, so the log rate
    # is bounded by the fetch rate — the failure line's own argument.
    logger.info(
        "Card %s face %d (%s) fetched from the CDN (%d bytes)",
        scryfall_id,
        face,
        size,
        len(body),
    )

    # Cleared on success, which is the half of recovery a functional test misses (AC 7): ending the
    # WINDOW is not the same as forgetting the HISTORY, and a key that failed four times and then
    # succeeded must start its next failure at the base delay rather than at the escalated one.
    if remembered is not None:
        remembered.clear(scryfall_id, size, face)

    # Written BEFORE the response is returned, not after (c3-7). A write scheduled to happen
    # "later" caches correctly under every functional test — a mocked fetch and a mocked disk are
    # both instantaneous — and in production races the next request for the same tile. That is
    # c3-6's probe (f) in this story's costume, and the reason the cache is filled on the same
    # await chain that serves the bytes.
    #
    # A cache failure is NOT a request failure and adds no reason token: `write` swallows and
    # logs, so the picture is served whether or not it was kept.
    if cache is not None:
        await cache.write(
            card_id=scryfall_id,
            size=size,
            face=face,
            content_type=content_type,
            body=body,
        )
    return _image_response(body, content_type)
