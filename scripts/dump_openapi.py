#!/usr/bin/env python3
"""Write the companion backend's own OpenAPI schema to ``ui/src/api/openapi.json`` (AD-12).

This is the **Python half** of the type pipeline. ``src/companion/contracts.py`` is the single
source of truth for every shape that crosses the wire; this script serialises what
``build_app().openapi()`` makes of those models, and ``npm run gen:types`` turns the result into
``ui/src/api/types.d.ts``. Nothing on the TypeScript side is hand-written::

    contracts.py ──(uv, `quality`)──> ui/src/api/openapi.json ──(npm, `frontend`)──> types.d.ts
                 pytest snapshot test                        CI git-status drift check

**Both files are committed, and both halves are gated**, so the chain from a Pydantic field to a
TypeScript property has no unguarded link. The schema is a committed hand-off artifact rather than
a temporary because CI cannot run the whole pipeline in one job: the ``quality`` job has uv and the
project's Python dependencies and no Node, while the ``frontend`` job has Node and ``npm ci`` and
never runs ``uv sync``. Splitting on that boundary adds no toolchain to either job and lets each
half fail in the gate that owns it (story c2-3, Decide-once #1).

**Adding an endpoint or a model needs no work here** — with one exception, added by c3-5 and
stated below. Declare the route with a ``response_model`` and ``error_responses(...)``, run
``npm run gen:api``, and commit both generated files — new paths and components appear in them
automatically. Story **c3-1** (``/api/decks`` and ``/api/deck/{deck_id}``) was the first to do it,
taking the schema from two components to six; story **c3-2** (``/api/cards/{card_id}``) followed,
taking it to seven and the paths to four; story **c3-3** (``/api/deck/{deck_id}/format-check``)
took it to nine components and five paths, adding the first wire shapes described by ``src/logic``
rather than ``src/data``; story **c3-4** (``/api/active-deck``) took it to eleven components and
six paths, adding ``ActiveDeck`` and ``ActiveDeckRequest``; and story **c3-5**
(``/api/card-image/{scryfall_id}``) took it to **twelve components and seven paths**, adding
``CardFace``. Story **c3-6**'s pacer **shipped and needed nothing here**, exactly as this
paragraph predicted — the prediction was settled by *running* ``npm run gen:api`` and pasting
``git status --porcelain``, not by argument: seven paths and twelve components, both generated
files byte-identical. Story **c3-7**'s disk cache **shipped and needed nothing here either**,
settled the same way and with the same result: a cache changes where bytes come from, not what the
operation promises.

So there are now **two measured instances** of what a story that adds behaviour to an existing
route — rather than a route — looks like on the wire, which is enough to state the rule rather
than the observation: **the wire describes the promise, and a change to how the promise is kept
does not touch it.**

**Story c3-8 was predicted to be the third, and the measurement says it is not — which is exactly
why the prediction was written to be run rather than argued** (2026-08-02). Its negative cache
added **no path, no component and no reason token**: seven paths and twelve components before and
after, so the *structural* half of the rule held perfectly. But ``npm run gen:api`` produced a real
diff in both generated files, because the story edited
:class:`~src.companion.contracts.ErrorResponse`'s class docstring to say what
``image_fetch_failed`` now means — and **that docstring is published in full**.

Two things were learned by measuring rather than reasoning, and both are worth keeping:

* **A class docstring on a wire model is wire-visible in its entirety**, bullet list and all — not
  merely its leading paragraph. The truncation rule that trims Google sections applies to *route*
  docstrings; a Pydantic model's ``description`` is the whole docstring.
* **An attribute docstring on a** ``Literal`` **type alias is NOT.** The same commit edited
  ``ErrorReason``'s docstring and that edit did not cross the wire at all. Two docstrings, twelve
  lines apart in one file, on opposite sides of the boundary — which is the kind of thing nobody
  gets right from first principles.

So the rule survives with its scope corrected: *a change to how a promise is kept does not touch
the wire's **shape** — but a change to how the promise is **described** does, and prose on a
wire model is part of the contract.* That was a deliberate choice here rather than an accident:
c4-4's tile author reads the 300-second recovery window in the generated JSDoc, which is the
same reasoning c3-2 used to promote its 503-retry trap and c3-3 its ``is_legal`` caveat.

**Story c3-9 was the first DELIBERATE wire change since c3-5, and it is neither of the two shapes
above** (2026-08-02). It was predicted not to be behaviour-only, and the generator confirmed which
half moved:

* **Structural: unchanged.** Seven paths, twelve components, ten reason tokens — before and after.
  c3-9 added no route and no token; it is a UI story that happened to owe the wire a correction.
* **Declarative: five operations changed.** ``build_app()`` now declares
  ``database_not_initialized`` on the database-backed includes (Q4), a token every one of those
  routes has answered since c1-6 and none had ever documented — on a fresh install it is the most
  common ``503`` the SPA sees, and it is the state c3-9 exists to render. The five diffs are the
  ``503`` descriptions on ``/api/decks``, ``/api/deck/{deck_id}``,
  ``/api/deck/{deck_id}/format-check``, ``/api/cards/{card_id}`` and
  ``/api/card-image/{scryfall_id}``:
  ``"reason: database_unavailable"`` becomes
  ``"reason: database_not_initialized | database_unavailable"``.
  ``/health`` and both active-deck operations are byte-identical, deliberately — neither can answer
  the token, and widening a declaration a route cannot honour turns an inherited wart into a fresh
  lie.
* **THE COLLAPSE FIRED FOR THE FIRST TIME.** :func:`~src.companion.app.errors.error_responses` has
  advertised since c1-4 that *"tokens sharing a status collapse into a single entry whose
  description names each of them"*, and until now no caller had ever declared two tokens under one
  status by inheritance. The one ``503`` entry naming both is that behaviour, in production, seven
  stories after it was written.
* **A third shape, and it is the useful one: a comment above a wire model costs NOTHING.** c3-9
  added the wire-visibility markers c3-8 declined (Q9) as ``#`` comments immediately above
  ``ErrorReason``'s assignment and ``ErrorResponse``'s ``class`` statement. Neither is a docstring,
  so neither crossed the wire — confirmed by running the generator, not by argument. **That is the
  safe way to annotate a wire module**: c3-8's objection was that *"even a comment edit is a wire
  decision that would want its own regeneration"*, and the measurement says a ``#`` comment is not
  one. A docstring still is.

**A KNOWN WART IN THIS DOCUMENT, recorded rather than fixed (c3-9, Q8).** Six body-less ``GET``
operations publish ``413 payload_too_large`` in their client contract, because the declaration is
made per *include* rather than per *method* and the shared set carries the 413 for the ``POST``
c5-5 will add. So the generated types tell a fetch author to handle a response the same document
elsewhere describes as *"surfaced to the agent… The glass never sees it"*. It is pre-existing,
inherited, and doubled by every new ``GET``. c3-9 declined to fix it: curating ``error_responses``
per method is a real change to a shared declaration site with six routes of blast radius, made in
a story whose frontend half is already the largest in the epic, and Q4 touched the *caller* rather
than the helper. **Re-homed on c5-5 by name** — the story that adds the cap, makes the 413 real,
and must decide which operations can actually answer it. Until then: a ``413`` on a body-less
``GET`` is unreachable, and a client may ignore it.

**The exception, and it is c3-5's.** That endpoint has **no** ``response_model``, because its
success body is image bytes: a model would emit a JSON ``$ref`` for a body that is binary. A
non-JSON success case needs four things declared at the route instead — no ``response_model``, an
explicit ``response_class=Response``, a hand-written ``responses={200: {"content": …}}`` block, and
a ``-> Response`` return annotation — and it still needs nothing here, because this script only
serialises whatever ``app.openapi()`` produces. Recorded so the paragraph above is not read as
"every route has a ``response_model``", which it no longer means. Measured for the record:
``openapi-typescript`` renders that 200 as ``content: { "image/*": string }`` — the body is typed
``string``, not ``Blob``, so **c4-4 must not derive its fetch handling from the generated type**.

c3-4 was also the first story to add anything but a ``GET``, and therefore the first to put a
``requestBody`` in the document at all — which likewise needed no change here. Its ``PUT`` is
credential-gated, and that too is invisible to this script **by design**: the credential is read
from ``request.headers`` inside a dependency rather than declared through a FastAPI security class,
so no ``securitySchemes`` component and no per-operation ``security`` block reach the artifact
(c3-4, Q4). A later story that reaches for ``HTTPBearer`` will change that, and should expect to
justify it.

One hand-synchronised pin has to be edited by a story that adds a component, and it is not here:
the component-name set in ``tests/unit/companion/test_committed_schema.py``. It goes red naming the
addition, which is the pin working — but the count above is *not* what enforces it, so do not read
this paragraph as the gate. (Until c3-4 there were **two** such pins, in the decks and cards route
tests; Q5 consolidated them into that one file, so c3-5 edits one place rather than discovering the
second by running the suite as c3-2 and c3-3 each did.)

**There is no dummy endpoint, and none is needed.** Story **c5-1**'s ``POST /agent/events`` declares
the WebSocket event-envelope union as its *request body*, so every per-kind payload lands in
``components.schemas`` from the route itself — one generator covers both the REST and the WebSocket
halves of the contract (AD-12).

Usage:
    uv run python -m scripts.dump_openapi     # -> ui/src/api/openapi.json (committed)

    npm run gen:api                           # from ui/: this script, then openapi-typescript
"""

import json
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent

# Anchored to REPO_ROOT, never to the cwd: `npm run gen:api` invokes this from `ui/` while a
# developer runs it from the repo root, and a cwd-relative path would quietly plant a second
# schema file in a directory nothing reads.
OUTPUT_PATH = REPO_ROOT / "ui" / "src" / "api" / "openapi.json"


def render_schema() -> str:
    """Render the companion's OpenAPI schema exactly as it is committed.

    The formatting is part of the contract, not a preference: the snapshot test in
    ``tests/unit/companion/test_openapi_contract.py`` compares the committed file's **bytes**
    against this function's output, so both sides must agree on indentation, non-ASCII handling and
    the trailing newline. That is also why the rendering lives here rather than inline in
    :func:`main` — the test imports this function, so it cannot drift from the writer.

    ``ensure_ascii=False`` keeps a non-ASCII character in a docstring readable rather than
    ``\\uXXXX``-escaped; the file is written UTF-8 with LF endings (``ui/.gitattributes`` pins the
    latter for the checkout, this function for the write).

    Returns:
        The full schema document as text, ending in exactly one newline.
    """
    # Function-local by AD-3, not by accident: nothing outside src/companion/app/ may import
    # src.companion.app at MODULE level, and tests/unit/companion/test_import_boundary.py scans
    # scripts/ for exactly that. Function-local is the form the guard deliberately permits (see
    # its `outside_app` role), and it is also honest here — this is a build-time generator, so
    # importing the module (as the snapshot test does) should not pull a web framework in with it.
    from src.companion.app.main import build_app

    schema = build_app().openapi()
    return json.dumps(schema, indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    """Write the rendered schema to ``ui/src/api/openapi.json``.

    Returns:
        ``0`` — the process exit code. The render itself raises rather than returning a failure
        code, so a broken schema surfaces as a traceback naming the offending model.
    """
    # Configured here, not at module level: the snapshot test imports this module, and a
    # module-level basicConfig would install a root stdout handler as an import side effect —
    # for the entire pytest process (c2-3 review, 2026-07-27).
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    # newline="\n" is load-bearing: the default translates "\n" to os.linesep, which on Windows
    # would write CRLF and make the byte-comparing snapshot test red locally and green in CI from
    # the very same commit.
    with OUTPUT_PATH.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(render_schema())
    logger.info("Wrote OpenAPI schema to %s", OUTPUT_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
