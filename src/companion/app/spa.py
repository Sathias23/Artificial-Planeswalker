"""Serve the committed SPA bundle that ships inside this package (AD-13, FR-01, SC-4).

The bundle at :data:`STATIC_DIR` is **generated output, committed to the repository**. Vite writes
it there from ``ui/``; CI rebuilds it and fails on drift; ``scripts/build_plugin.py`` mirrors it
into ``plugin/``. Nothing here builds anything — that is the whole point of AD-13, and it is what
makes SC-4 ("a fresh install launches with a single ``uv`` command and no build step") true rather
than aspirational.

Three decisions hold this module together, and later stories inherit rather than re-make them:

* **The fallback is decided by the request, not by a wildcard.** A ``GET``/``HEAD`` whose path has
  no file extension and whose first segment is not a registered route prefix gets ``index.html``;
  everything else keeps the typed error contract (AD-16). Each third of that rule buys something —
  see :meth:`_SpaFiles._should_fall_back`.

* **StaticFiles is subclassed, not replaced.** ETag, ``Last-Modified``, conditional requests, range
  support and ``HEAD`` all stay Starlette's. A hand-rolled ``@app.get("/{path:path}")`` file server
  would re-implement four RFCs badly and would be the first one in a repo that has none.

* **The mount goes last in** ``build_app()``. Starlette matches routes in list order and a mount at
  ``/`` matches every path, so anything registered after it is silently shadowed — ``GET
  /api/decks`` would quietly answer ``200`` with an HTML document. ``test_spa.py`` guards the
  ordering with an instructive failure message; see :func:`install_spa`.

**Why the mimetypes are registered here.** Starlette's ``FileResponse`` derives its media type
from ``mimetypes.guess_type(...)[0] or "text/plain"``, and ``mimetypes`` consults the **Windows
registry** — which any installed application can rewrite. A ``.js`` served as ``text/plain`` makes
a module script refuse to execute and the page render blank, behind a ``200`` in the network tab.
Declaring the types this bundle actually contains removes the machine from the equation.
"""

import logging
import mimetypes
from collections.abc import Iterable, Iterator
from pathlib import Path, PurePath

from fastapi import FastAPI
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response
from starlette.routing import BaseRoute, Match, Mount
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"
"""The committed SPA bundle, inside the Python package (AD-13).

Inside ``src/companion/app/`` on purpose: the project also ships as a cloned plugin tree, so a
wheel-build hook that compiled the SPA at install time would leave plugin users with nothing.
"""

_INDEX_NAME = "index.html"

_ASSETS_DIR_NAME = "assets"
"""Vite's content-hashed output directory. The hash in each filename is what makes the immutable
cache header below safe: a changed file is a changed name."""

_RESERVED_SEED = frozenset({"api"})
"""Path prefixes reserved before any route claims them.

``/api`` has no routes until c3-1, but the reservation must hold *now* — otherwise a typo like
``GET /api/deckz`` would answer ``200`` with the index today and ``404`` after c3-1 lands, and the
UI would have been written against the wrong one. Every other prefix is derived from the live route
table (:func:`_reserved_prefixes`), so c3-1's ``/api/decks`` reserves ``api`` on its own.
"""

_IMMUTABLE_CACHE_CONTROL = "public, max-age=31536000, immutable"
_REVALIDATE_CACHE_CONTROL = "no-cache"

_ALLOWED_METHODS = "GET, HEAD"
"""What a static document surface supports, for the ``Allow`` header a 405 must carry."""

# Declared, not guessed — see the module docstring. `.woff2` is the one that is already wrong on
# this machine (mimetypes resolves it to None, so Starlette would ship a font as text/plain);
# story c2-5 self-hosts Space Grotesk into this same directory and needs it correct.
_MEDIA_TYPES: tuple[tuple[str, str], ...] = (
    (".js", "text/javascript"),
    (".mjs", "text/javascript"),
    (".css", "text/css"),
    (".svg", "image/svg+xml"),
    (".json", "application/json"),
    (".map", "application/json"),
    (".woff2", "font/woff2"),  # c2-5
    (".woff", "font/woff"),  # c2-5
)

for _suffix, _media_type in _MEDIA_TYPES:
    mimetypes.add_type(_media_type, _suffix)


def _route_paths(routes: Iterable[BaseRoute], prefix: str = "") -> Iterator[str]:
    """Yield the full path of every route in *routes*, descending through every nesting shape.

    Three shapes exist and all three are load-bearing here:

    * a plain ``Route`` / ``WebSocketRoute`` carries ``.path``;
    * a ``Mount`` carries ``.path`` **and** ``.routes`` for its children;
    * FastAPI's ``include_router`` wraps the included router in an ``_IncludedRouter``, which
      carries **neither** — its routes hang off ``.original_router`` and its prefix off
      ``.include_context``. Missing this shape is not a crash, it is a silently empty reservation:
      every prefix a story registers via ``include_router`` (c3-1's ``/api``, c5-5's ``/agent``)
      would fall through to the SPA index instead of a typed 404.

    Those last two attributes are FastAPI internals, so every read is a ``getattr`` with a
    fallback — and ``test_spa.py::test_the_reserved_prefixes_are_derived_from_the_route_table``
    fails loudly if a FastAPI upgrade moves them, rather than letting the reservation quietly
    empty out.

    Args:
        routes: The routes to walk.
        prefix: Path prefix accumulated from enclosing mounts and router includes.

    Yields:
        Each route's full path, with every enclosing prefix applied.
    """
    for route in routes:
        path = getattr(route, "path", None)
        own = path if isinstance(path, str) else ""
        if own:
            yield prefix + own
        nested = getattr(route, "routes", None)
        if nested:
            yield from _route_paths(nested, prefix + own)
        included = getattr(route, "original_router", None)
        if included is not None:
            context = getattr(route, "include_context", None)
            yield from _route_paths(
                getattr(included, "routes", ()), prefix + (getattr(context, "prefix", "") or "")
            )


def _reserved_prefixes(app: FastAPI) -> frozenset[str]:
    """Collect the first path segment of every route already registered on *app*.

    Derived from the live route table rather than hand-typed, so a story that adds ``/api/decks``
    or ``/agent/events`` reserves its own prefix with no edit here. This is the other half of why
    the mount must be installed last: at install time the route table has to be complete.

    Args:
        app: The application whose routes are being read, immediately before the mount is added.

    Returns:
        The reserved first segments, including :data:`_RESERVED_SEED`.
    """
    prefixes = set(_RESERVED_SEED)
    for path in _route_paths(app.routes):
        segments = [segment for segment in path.split("/") if segment]
        if segments:
            prefixes.add(segments[0])
    return frozenset(prefixes)


def _route_path(scope: Scope) -> str:
    """Return the request path with any mounted ``root_path`` removed.

    Reimplemented rather than imported: Starlette keeps ``get_route_path`` in a private module,
    and the whole body is these four lines.

    Args:
        scope: The ASGI connection scope.

    Returns:
        The path this router should match against.
    """
    path: str = scope.get("path", "")
    root_path: str = scope.get("root_path", "")
    if root_path and path.startswith(root_path):
        return path[len(root_path) :]
    return path


class _SpaMount(Mount):
    """A mount at ``/`` that **declines** every path belonging to the API surface.

    Declining matters more than it looks. Starlette's router takes the first ``Match.FULL`` and
    returns immediately, so a mount at ``/`` — which matches everything — beats the
    ``Match.PARTIAL`` a real route reports when the path matches but the method does not. That
    partial is exactly how Starlette produces ``405`` with the RFC-mandated ``Allow`` header, and
    ``errors.py`` deliberately preserves those headers because dropping them "would make the typed
    body a downgrade". Without this class, ``POST /health`` answers ``405`` with no ``Allow``, and
    once c5-5 adds a POST-only ``/agent/events`` a plain ``GET`` of it would answer ``404``
    instead of ``405 Allow: POST``.

    Returning ``Match.NONE`` for reserved prefixes hands those paths back to the router, which
    knows each route's real method set. Everything else still falls through to the SPA.

    Args:
        app: The static-files application to serve.
        reserved_prefixes: First path segments this mount must not claim.
    """

    def __init__(self, *, app: StaticFiles, reserved_prefixes: frozenset[str]) -> None:
        super().__init__("/", app=app, name="spa")
        self._reserved_prefixes = reserved_prefixes

    def matches(self, scope: Scope) -> tuple[Match, Scope]:
        """Match *scope* unless its first path segment is reserved for the API.

        Args:
            scope: The ASGI connection scope.

        Returns:
            Starlette's ``(match, child_scope)`` pair; ``Match.NONE`` for a reserved path.
        """
        segments = [segment for segment in _route_path(scope).split("/") if segment]
        if segments and segments[0] in self._reserved_prefixes:
            return Match.NONE, {}
        return super().matches(scope)


class _SpaFiles(StaticFiles):
    """``StaticFiles`` whose 404 falls back to the SPA index for client-side routes.

    Args:
        directory: The bundle directory to serve.
        reserved_prefixes: First path segments that must never fall back — the API surface.
    """

    def __init__(self, *, directory: Path, reserved_prefixes: frozenset[str]) -> None:
        # html=False deliberately. html=True would serve `index.html` for a directory request, but
        # it also makes Starlette look for a `404.html` before raising — and if a later story ever
        # adds one to the bundle, every client route would silently start answering with a 404
        # status and that document instead of the index. With html=False the only path to the index
        # is the explicit rule below, which is the behaviour the tests pin. check_dir stays at its
        # default: a missing bundle must fail loudly (install_spa gets there first with a better
        # message), never degrade into a 404 on every page load.
        super().__init__(directory=directory, html=False)
        self._reserved_prefixes = reserved_prefixes

    async def get_response(self, path: str, scope: Scope) -> Response:
        """Serve *path*, falling back to the SPA index for a client-side route.

        Args:
            path: The OS-separated relative path Starlette resolved from the request.
            scope: The ASGI connection scope.

        Returns:
            The file response, or the index document for a client-side route.

        Raises:
            starlette.exceptions.HTTPException: Propagated unchanged for anything that is not a
                fallback-eligible 404 — which is what keeps the typed error contract intact
                (``errors.py``'s ``http_exception_handler`` turns it into
                ``{"reason": "invalid_request"}`` at the framework's own status).
        """
        served = path
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 405:
                # RFC 9110 requires a 405 to name the methods it does allow, and StaticFiles
                # raises a bare one. For a path the API has not reserved, the honest answer is
                # that this surface serves documents and nothing else.
                raise StarletteHTTPException(405, headers={"Allow": _ALLOWED_METHODS}) from exc
            if exc.status_code != 404 or not self._should_fall_back(path, scope):
                raise
            served = _INDEX_NAME
            response = await super().get_response(served, scope)
        self._apply_cache_headers(response, served)
        return response

    def _should_fall_back(self, path: str, scope: Scope) -> bool:
        """Decide whether a missing *path* is a client-side route rather than a broken deployment.

        Each condition earns its place:

        * **GET or HEAD only.** A ``POST`` to a client route is never a document request; letting
          it answer ``200`` with HTML would make a mistyped API call look like a success. (In
          practice Starlette raises ``405`` before we get here, so this is defence in depth.)
        * **No file extension.** ``/assets/index-abc123.js`` that does not exist is a *broken
          deployment*. It must say ``404`` loudly rather than return an HTML document with a
          ``200`` that the browser then fails to parse as JavaScript.
        * **First segment not reserved.** ``/api/deckz`` — a typo, no extension — must not answer
          with the index.
        * **No parent traversal.** A path that climbed out of the bundle is not a client route.

        The query string is deliberately absent from all of this: an ASGI ``scope["path"]`` never
        contains one. (Vite's dev proxy *does* match the full URL including the query, which is the
        bug c2-1's round-2 review found — the two matchers do not share the hazard, and
        ``test_spa.py`` pins that rather than assuming it.)

        Args:
            path: The OS-separated relative path Starlette resolved from the request.
            scope: The ASGI connection scope.

        Returns:
            ``True`` if the index should be served for this request.
        """
        if scope.get("method") not in ("GET", "HEAD"):
            return False
        parts = PurePath(path).parts
        if ".." in parts:
            return False
        # normpath renders the site root as "." — an empty tuple of meaningful segments, and the
        # one case that is unambiguously a document request.
        meaningful = tuple(part for part in parts if part != ".")
        if not meaningful:
            return True
        if meaningful[0] in self._reserved_prefixes:
            return False
        return "." not in meaningful[-1]

    def _apply_cache_headers(self, response: Response, served: str) -> None:
        """Stamp the cache policy appropriate to the file that was actually served.

        Starlette sets **no** ``Cache-Control`` at all, which leaves the browser free to
        heuristically cache ``index.html``. Combined with Vite's ``emptyOutDir`` — which *deletes*
        the previous hashed assets — a stale cached index after a ``git pull`` references files
        that no longer exist: a blank page that a reload does not fix. ``no-cache`` means
        *revalidate*, not *do not store*, so the common case is still a cheap ``304``.

        Everything under ``assets/`` is content-hashed by Vite, so its name changes whenever its
        bytes do and a year-long immutable lifetime is safe.

        Keyed on the *served* file rather than the requested path: a fallback request for
        ``/decks/42`` serves the index and must get the index's policy.

        Args:
            response: The response about to be returned.
            served: The bundle-relative path of the file that was served.
        """
        parts = PurePath(served).parts
        is_hashed_asset = len(parts) > 1 and parts[0] == _ASSETS_DIR_NAME
        response.headers["cache-control"] = (
            _IMMUTABLE_CACHE_CONTROL if is_hashed_asset else _REVALIDATE_CACHE_CONTROL
        )


def install_spa(app: FastAPI, *, static_dir: Path | None = None) -> None:
    """Mount the committed SPA bundle at ``/``.

    **Call this last in** ``build_app()``. A mount at ``/`` matches every path, and Starlette
    matches routes in list order, so any router registered *after* this call is shadowed — its
    endpoints answer ``200`` with ``index.html`` instead of running. c3-1, c5-2 and c5-5 all add
    routers and must add them above the ``install_spa(app)`` line.

    Construction stays inert (AD-10): this stats two paths and builds an in-process object. It
    creates no directory, binds no port and opens no database.

    Args:
        app: The application to mount onto, with every other route already registered.
        static_dir: Override for the bundle location. Exists for tests that need a directory that
            is missing or empty; production always takes :data:`STATIC_DIR`.

    Raises:
        RuntimeError: The bundle is missing or has no ``index.html``. Raised here, at construction,
            with the rebuild command in the message — rather than letting ``StaticFiles`` say
            ``Directory 'static' does not exist``, or (worse) degrading into a 404 on every page
            load, which is the same class of quiet failure as a script served as ``text/plain``.
    """
    directory = STATIC_DIR if static_dir is None else static_dir
    if not directory.is_dir() or not (directory / _INDEX_NAME).is_file():
        raise RuntimeError(
            f"The companion UI bundle is missing from {directory}. It is a committed build "
            f"artifact, not something the installer produces — rebuild it with: "
            f"cd ui && npm run build"
        )
    logger.debug("Serving the SPA bundle from %s", directory)
    reserved = _reserved_prefixes(app)
    # Appended directly rather than via app.mount(), which would build a plain Mount and lose the
    # reserved-prefix decline that keeps 405-with-Allow working (see _SpaMount).
    app.router.routes.append(
        _SpaMount(
            app=_SpaFiles(directory=directory, reserved_prefixes=reserved),
            reserved_prefixes=reserved,
        )
    )
