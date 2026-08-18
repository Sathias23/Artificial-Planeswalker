"""Drift guard over the companion PRD, keyed on the shipped symbols (story 15.3).

Story 15.3 corrected three requirements that had become factually false, recorded six capabilities
that shipped without ever reaching the requirements, and answered two open questions the build had
already closed. **Correcting them is worth less than gating them.** Seven planning sites carried an
image-cache figure the C3 retrospective disproved on 2026-08-02 and it kept spreading for sixteen
days, across an epic file, an architecture spine and an HTML projection, because nothing could see
it. Both ``src/companion/contracts.py`` and ``src/companion/app/deps.py`` say *in shipped
docstrings* that a PRD amendment is owed — the code knew, and the documents drifted anyway. This
module is the thing that can see it.

Every closed-set assertion reads the **imported symbol** through :func:`typing.get_args`, never a
list retyped here: :data:`src.companion.contracts.ErrorReason`,
:data:`src.companion.contracts.EventKind`, and ``SetActiveDeckResult``'s ``status`` literal. The
route assertion reads ``build_app().openapi()`` rather than string literals. A rename or an added
member therefore turns this red and names the member, instead of quietly leaving the PRD one
generation behind. The idiom is Story 15.2's ``test_image_cache_docs.py``: extract the section by
heading, fail on the anchor first so nothing can pass vacuously, and put both sides of the drift in
the message.

**Declared residue — what this guard does NOT prove:**

1. **It gates the PRD, and only the PRD.** The addendum, ``EXPERIENCE.md``, the 2026-07-25
   validation report, ``DESIGN.md``, ``epics-companion-app.md``, ``ARCHITECTURE-SPINE.md`` and its
   ``walkthrough.html`` were all amended by story 15.3 and none of them is read here. The UX files
   have their own frontend guards for the rows that matter; the epic, the spine and the addendum
   are gated by nothing, which is a known hole rather than an oversight.
2. **Presence is not correctness.** That the PRD contains the token ``payload_rejected`` does not
   prove the sentence around it says something true about when that status is returned. This module
   checks that every shipped member is *recorded*, that the retired claims are *gone*, and that the
   documented routes *exist* — three mechanical properties. Whether the prose is right is a
   reviewer's judgement.
3. **The retired-claim scan is literal.** ``mode=ro`` and the dotted application directory name are
   banned as strings anywhere in the document, which is why the amendments describe both in words
   rather than reproducing the spelling. A paraphrase that reintroduced the *claim* without either
   spelling — ``file:…?immutable=1``, a per-OS dotfolder written out longhand — would pass here.
   FR-04 is the exception and is checked structurally, because ``layout`` legitimately appears in
   that row: the clause after "driven by" must *begin* with the shipped driver and must not name a
   layout at all. That two-part shape is not decoration — a reviewer defeated the single-substring
   version with *"driven by the card's Scryfall ``layout``, not by the presence of per-face
   ``image_uris``"*, which is the banned claim reintroduced verbatim.
4. **Route paths, not route behaviour, and only paths the PRD writes as code.** The shipped side is
   the whole route table — ``APIRoute`` *and* ``APIWebSocketRoute``, walked recursively, with no
   allowlist of first path segments — so a route on a novel prefix fails here rather than vanishing
   from both sides of the comparison. ``app.openapi()`` is deliberately **not** the source: it omits
   WebSockets entirely, and ``/ws`` is a real endpoint the browser holds open for a whole session.
   The documented side reads only paths written inside a code span and anchored at its start, which
   is what keeps the glossary's per-OS filesystem paths from being read as endpoints; an endpoint
   named in bare prose would be invisible here. Nothing about methods, status codes, auth or
   payloads is checked — the read/write asymmetry on ``/api/active-deck`` is prose here and is
   pinned by ``tests/unit/companion/test_active_deck.py`` in code.
5. **The footprint figures are outside this module.** The six ~12 MB sites story 15.3 corrected
   live in the epic, the spine and the walkthrough, none of which is a PRD — and ``prd.md`` never
   carried a footprint figure at all, so this guard could not have caught that drift and will not
   catch the next one of its shape. ``README.md``'s copy is gated by ``test_image_cache_docs.py``;
   ``ui/README.md``'s and every planning copy are gated by nothing.
"""

import re
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any, get_args

from fastapi.routing import APIRoute, APIWebSocketRoute

from src.companion import contracts
from src.companion.app.main import build_app
from src.mcp_server.tools.companion import SetActiveDeckResult

# ---------------------------------------------------------------------------------------------
# Repository layout — resolved from __file__, never from the current working directory, exactly as
# tests/unit/companion/test_import_boundary.py and test_image_cache_docs.py do it.
# ---------------------------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[3]
PRD_PATH = (
    REPO_ROOT
    / "_bmad-output"
    / "planning-artifacts"
    / "prds"
    / "prd-Artificial-Planeswalker-2026-07-22"
    / "prd.md"
)
"""The PRD **of record**. The 2026-07-11 PRD directory is a different feature (deck power
assessment) and carries none of these requirements — naming the path in full here is what stops a
future reader gating the wrong document."""

# The four headings this module anchors on. Each is a non-vacuity anchor: `_section` fails by name
# when one is renamed, so a restructured PRD can never let the assertions below pass over nothing.
FUNCTIONAL_HEADING = "## 7. Functional Requirements"
NON_FUNCTIONAL_HEADING = "## 8. Non-Functional Requirements"
OPEN_QUESTIONS_HEADING = "## 12. Open Questions"
GLOSSARY_HEADING = "## 13. Glossary"
ANCHORS = (
    FUNCTIONAL_HEADING,
    NON_FUNCTIONAL_HEADING,
    OPEN_QUESTIONS_HEADING,
    GLOSSARY_HEADING,
)

# Any ATX heading at any level: a `### Feature C` sub-heading must terminate a `##` section, or a
# section would swallow prose it does not own and every presence check would read the wrong text.
_ATX_HEADING = re.compile(r"#{1,6} ")

# Endpoint paths **as the PRD writes them**: inside a code span, at its start, optionally after an
# HTTP method. Anchoring at the span's start is what keeps filesystem paths out — the glossary's
# `~/Library/Application Support/artificial-planeswalker` and
# `~/.local/share/artificial-planeswalker` are code spans containing slashes, and a bare
# slash-hunting family reported `/Library/Application` as an endpoint the app fails to serve. The
# class stops at `?`, so FR-04's `?size=&face=` query string drops off on its own.
#
# There is deliberately **no allowlist of first path segments** here or on the shipped side (review
# 2026-08-18): an `/api|/agent|/health` filter made a route on a novel segment — `/metrics`, `/ws`,
# `/debug/state` — vanish from BOTH sets, so the parity assertion passed by not looking.
_ROUTE = re.compile(
    r"`(?:(?:GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS|WS|WSS)\s+)?(?P<path>/[A-Za-z0-9_\-{}][A-Za-z0-9_\-{}/]*)"
)
_PATH_PARAM = re.compile(r"\{[^}]*\}")

# Paths the app serves that are NOT product surface and are deliberately undocumented: FastAPI's
# own interactive docs, and the SPA mount, which is a `StaticFiles` app rather than a route.
_NON_PRODUCT_PATHS = frozenset({"/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"})

# The two retired claims that can be banned as literals. FR-04's is checked structurally instead.
_RETIRED_LITERALS = {
    "mode=ro": (
        "NFR-02 used to specify a read-only connection string. Nothing in src/ has ever opened "
        "one: src/companion/app/deps.py calls a plain create_engine(url). Read-only is enforced "
        "structurally by tests/unit/companion/test_import_boundary.py, whose module docstring "
        "records the two reasons the recipe was rejected (the WAL -shm Windows landmine; the "
        "immutable variant would foreclose FR-16)."
    ),
    ".artificial-planeswalker": (
        "The discovery file and the image cache used to be specified in a home-directory "
        "dotfolder. No code has ever created one: src/companion/discovery.py resolves "
        "src.paths.data_dir() / COMPANION_FILENAME, and src/paths.py documents the per-OS "
        "defaults and the PLANESWALKER_DATA_DIR override that moves the whole location. The "
        "banned form is the bare DOT-DIRECTORY NAME, not the tilde spelling: `~/.artificial-"
        "planeswalker`, `$HOME/.artificial-planeswalker` and "
        "`%LOCALAPPDATA%\\.artificial-planeswalker` are one claim in three costumes, and a ban on "
        "the tilde alone is defeated by dropping two characters (review 2026-08-18). The "
        "undotted application directory name is legitimate — it is what `src/paths.py` uses — so "
        "only the dotted form is banned."
    ),
}

# Non-greedy and bounded, so the capture is the DRIVER and not the rest of the row. The first cut
# used `[^;.]+`, which ran to the end of the sentence: a row reading "driven by the card's Scryfall
# `layout`, not by the presence of per-face `image_uris`" satisfied a substring check and PASSED,
# reintroducing verbatim the one claim this module exists to ban (proven at review, 2026-08-18).
_FR04_DRIVER = re.compile(r"face handling is driven by\s+(?P<clause>[^;.,]+)")
_EXPECTED_DRIVER = "the presence of per-face `image_uris`"
_EMPHASIS = re.compile(r"[*_`]+")


def _prd() -> str:
    """Return the PRD's text, read from the repository root rather than the working directory."""
    assert (REPO_ROOT / "pyproject.toml").exists(), f"{REPO_ROOT} is not the repository root"
    assert PRD_PATH.exists(), (
        f"the PRD of record is missing at {PRD_PATH.relative_to(REPO_ROOT)}. Every assertion in "
        "this module reads it, so its absence fails here rather than passing vacuously. If the "
        "document moved, update PRD_PATH — do not delete this guard."
    )
    return PRD_PATH.read_text(encoding="utf-8")


def _section(prd: str, heading: str) -> str:
    """Return one section, from *heading* to the next ATX heading of any level.

    **The non-vacuity anchor.** A renamed or deleted heading has to fail here, by name, rather than
    yield an empty string that every substring check would then pass over.

    Args:
        prd: The full text of the PRD.
        heading: The exact heading line to extract from.

    Returns:
        The section's lines, heading included, joined with newlines.
    """
    lines = prd.splitlines()
    starts = [i for i, line in enumerate(lines) if line.strip() == heading]
    assert len(starts) == 1, (
        f"the PRD has {len(starts)} lines equal to {heading!r}; this guard needs exactly one to "
        "know which prose it is reading. Restore the heading, or — if the section was deliberately "
        f"renamed — update the anchor in {Path(__file__).name}."
    )
    start = starts[0]
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if _ATX_HEADING.match(lines[i]):
            end = i
            break
    return "\n".join(lines[start:end])


def _row(prd: str, requirement_id: str) -> str:
    """Return the one requirement table row for *requirement_id* (e.g. ``FR-04``)."""
    rows = [line for line in prd.splitlines() if line.startswith(f"| {requirement_id} |")]
    assert len(rows) == 1, (
        f"the PRD has {len(rows)} table rows beginning '| {requirement_id} |'; this guard needs "
        "exactly one to know which requirement it is reading."
    )
    return rows[0]


def _walk_routes(routes: Iterable[Any]) -> Iterator[Any]:
    """Yield every leaf route, descending through router wrappers.

    This FastAPI version does not flatten ``include_router`` into the app's own route list: each
    inclusion appears as a ``_IncludedRouter`` wrapper carrying its own ``.routes``. A flat scan of
    ``app.routes`` therefore finds only Starlette's four docs endpoints and the SPA mount — zero
    product routes — which is exactly the empty-set-comparison this module's non-vacuity assertion
    exists to catch, and did (2026-08-18). Descending is version-tolerant: it works whether the
    wrapper is present or the routes are flattened.
    """
    for route in routes:
        nested = getattr(route, "routes", None)
        if not nested:
            # This FastAPI's `_IncludedRouter` keeps its children on `original_router` rather than
            # on `routes`. Reached through `getattr` so a version that flattens, or renames the
            # attribute, degrades to "no children" and is caught by the non-vacuity assertion
            # below rather than by an AttributeError three frames deep.
            nested = getattr(getattr(route, "original_router", None), "routes", None)
        if nested:
            yield from _walk_routes(nested)
        else:
            yield route


def _shipped_routes() -> set[str]:
    """Return every product path the app serves, WebSocket routes included.

    Read from the route table rather than from ``app.openapi()``, and that is the whole point:
    **OpenAPI does not model WebSockets**, so ``src/companion/app/ws.py``'s ``WS_PATH`` — a real,
    registered, security-relevant endpoint — is invisible to the schema. A parity test built on the
    schema would have reported "the PRD documents everything the app serves" while silently
    excluding the one endpoint the browser holds open for its whole session (review 2026-08-18).

    Returns:
        The paths, with ``{...}`` parameter names erased and FastAPI's own docs endpoints dropped.
    """
    app: Any = build_app()
    paths = {
        route.path
        for route in _walk_routes(app.routes)
        if isinstance(route, APIRoute | APIWebSocketRoute) and route.path not in _NON_PRODUCT_PATHS
    }
    assert paths, (
        "the app exposes no APIRoute or APIWebSocketRoute at all. Either it stopped registering "
        "routers or FastAPI's route classes changed; either way this guard would otherwise "
        "compare two empty sets and pass."
    )
    return {_PATH_PARAM.sub("{}", path.rstrip("/")) for path in paths}


def _normalised_routes(text: str) -> set[str]:
    """Return the endpoint paths in *text*, with path-parameter names erased.

    The PRD writes ``/api/deck/{id}`` where the app declares ``/api/deck/{deck_id}``. Those are the
    same endpoint, and a guard that called them different would be reporting a spelling preference
    as a contract breach — so every ``{...}`` collapses to ``{}`` on both sides.
    """
    return {
        _PATH_PARAM.sub("{}", match.group("path").rstrip("/")) for match in _ROUTE.finditer(text)
    }


class TestPrdRecordsWhatShipped:
    """The PRD of record, gated against the symbols the companion actually ships."""

    def test_the_prd_and_every_anchored_section_resolve(self) -> None:
        """Non-vacuity, first and by name: the document exists and each anchor is findable.

        Every other test in this class reads a section or a row out of this file. If the PRD were
        restructured — sections renumbered, headings reworded — the substring checks below would
        start passing over prose that is not there, which is the exact failure mode a prose gate is
        supposed to prevent. This test is why they cannot.
        """
        prd = _prd()
        for heading in ANCHORS:
            section = _section(prd, heading)
            assert len(section.splitlines()) > 1, (
                f"{heading!r} resolves to a heading with no body — the section this guard reads is "
                "empty, so nothing below it would be checking anything."
            )
        for requirement_id in ("FR-02", "FR-03", "FR-04", "FR-07", "FR-11", "NFR-02", "NFR-09"):
            assert _row(prd, requirement_id)

    def test_the_retired_claims_are_gone(self) -> None:
        """The two claims story 15.3 retired are absent as literals, each with its disproof.

        These are not stylistic preferences. Both named a mechanism a reader could go looking for
        and never find, which is worse than saying nothing: the search ends in a wrong conclusion
        about how the system works.
        """
        prd = _prd()
        for claim, disproof in _RETIRED_LITERALS.items():
            assert claim not in prd, (
                f"the PRD names {claim!r}, a claim story 15.3 retired as false. {disproof} Amend "
                f"{PRD_PATH.name} — the shipped code is not the thing to change here."
            )

    def test_fr04_keys_on_per_face_image_uris_and_not_on_a_layout(self) -> None:
        """FR-04's driver clause is the per-face image map, never a Scryfall ``layout`` string.

        Checked structurally rather than by banning the word: the amendment's whole point is that
        the ``cards`` table has **no** ``layout`` column, so FR-04 legitimately says ``layout`` in
        the course of saying it is not the driver. What must not return is the *claim*.

        **Two assertions, not one, and the second is the load-bearing one** (review 2026-08-18).
        A first cut asserted only that the expected driver appeared *somewhere* in the clause, and
        a reviewer defeated it in one line: *"driven by the card's Scryfall ``layout``, not by the
        presence of per-face ``image_uris``"* contains the expected substring and passed, which
        reintroduced verbatim the one claim this module exists to ban. The clause must therefore
        **begin** with the shipped driver, and must not name a layout at all before the sentence's
        first break.
        """
        row = _row(_prd(), "FR-04")
        match = _FR04_DRIVER.search(row)
        assert match, (
            "FR-04 no longer contains a 'face handling is driven by …' clause at all. This guard "
            "reads that clause to check what the driver is; restore it, or update this test with "
            "the row's new shape."
        )
        clause = _EMPHASIS.sub("", match.group("clause")).strip()
        assert clause.startswith(_EMPHASIS.sub("", _EXPECTED_DRIVER)), (
            f"FR-04 says face handling is driven by {clause!r}. The shipped rule is "
            "src.companion.app.images.resolve_face_images, which keys on the presence of per-face "
            "image_uris and nothing else — it cannot do otherwise, because the cards table has no "
            "layout column (src/data/models/card.py declares card_faces and image_uris, and no "
            "layout). Branching on card_faces instead renders nothing for the 368 printings that "
            "carry faces and a top-level image. Amend the PRD."
        )
        assert "layout" not in clause.lower(), (
            f"FR-04's driver clause names a layout: {clause!r}. A clause that leads with the "
            "layout and only then denies it — 'driven by the card's Scryfall layout, not by the "
            "presence of per-face image_uris' — is the retired claim wearing the amendment's "
            "clothes, and it is what defeated the first version of this test."
        )

    def test_every_error_reason_token_is_recorded(self) -> None:
        """Each member of the closed ``ErrorReason`` set appears in the PRD, read from the symbol.

        ``card_not_found`` is the member story 15.3 added; the other nine are pinned with it so a
        *tenth* addition, or a rename, cannot land without the document following.
        """
        reasons = get_args(contracts.ErrorReason)
        assert len(reasons) == 10, (
            f"src.companion.contracts.ErrorReason has {len(reasons)} members, not the ten AD-16 "
            "closed it at. If a Literal became an Enum or a plain str, get_args() returns an empty "
            "tuple and the loop below would iterate nothing — this count is what stops that "
            "passing silently. Update the PRD's FR-03 list and this number together."
        )
        row = _row(_prd(), "FR-03")
        for reason in reasons:
            assert f"`{reason}`" in row, (
                f"src.companion.contracts.ErrorReason has the member {reason!r} and FR-03 does "
                "not record it. AD-16's extension rule is that a new token and the UI state it "
                "drives are added together — so the document to amend is the PRD (FR-03 carries "
                "the closed list), not this test."
            )

    def test_every_event_kind_is_recorded(self) -> None:
        """Each member of the closed ``EventKind`` set appears in the PRD, read from the symbol.

        ``active_deck_changed`` is the sixth member — six, not the five AD-6 enumerated — and the
        one story 15.3 recorded. Reading ``get_args`` rather than a hand-typed list is what makes
        this survive the next rename instead of becoming another stale copy.
        """
        kinds = get_args(contracts.EventKind)
        assert len(kinds) == 6, (
            f"src.companion.contracts.EventKind has {len(kinds)} members, not six. Zero means the "
            "Literal became something get_args() cannot read, which would make the loop below "
            "iterate nothing; any other number means the closed set moved. Update FR-11's list and "
            "this count together — the same pairing test_contracts.py's kind-vocabulary test makes."
        )
        row = _row(_prd(), "FR-11")
        for kind in kinds:
            assert f"`{kind}`" in row, (
                f"src.companion.contracts.EventKind has the member {kind!r} and FR-11 does not "
                "record it. FR-11 is where the PRD enumerates the closed set — all six, the four "
                "agent views and the two system signals — so that is the row to extend."
            )

    def test_every_set_active_deck_status_is_recorded(self) -> None:
        """Each ``SetActiveDeckResult.status`` outcome appears in the PRD, read from the symbol.

        ``deck_not_found`` is the interesting one and the reason the whole set is pinned: it lives
        in the MCP tool rather than the backend, because ``PUT /api/active-deck`` has no database
        and cannot observe it — ``src/companion/client.py`` says so in as many words. A reader who
        goes looking for a backend 404 will not find one, so the PRD has to say where the token is.
        """
        statuses = get_args(SetActiveDeckResult.model_fields["status"].annotation)
        assert len(statuses) == 8, (
            f"SetActiveDeckResult.status has {len(statuses)} outcomes, not eight. Zero means "
            "get_args() could not read the annotation and the loop below would check nothing."
        )
        row = _row(_prd(), "FR-07")
        for status in statuses:
            assert f"`{status}`" in row, (
                f"src.mcp_server.tools.companion.SetActiveDeckResult.status has the outcome "
                f"{status!r} and FR-07 does not record it. Scoped to the ROW rather than the "
                "document (review 2026-08-18): `deck_not_found` and `database_not_initialized` are "
                "ErrorReason members too and are listed in FR-03, so a document-wide search would "
                "keep passing on two of the eight after FR-07's list was deleted outright."
            )

    def test_the_documented_routes_are_the_routes_the_app_serves(self) -> None:
        """The PRD's endpoint paths and the shipped app's are the same set, both ways.

        Read from ``app.routes`` rather than from a literal — and rather than from
        ``app.openapi()``, which omits WebSocket routes entirely — so a route added, removed or
        re-pathed in code fails here instead of being discovered by a reader. Both directions
        matter: an undocumented endpoint is a capability nobody agreed to, and a documented one that
        does not exist is the ``mode=ro`` failure again in a different costume.
        """
        documented = _normalised_routes(_prd())
        shipped = _shipped_routes()
        undocumented = shipped - documented
        assert not undocumented, (
            f"the app serves {sorted(undocumented)} and the PRD does not name them. Record each "
            "against the requirement it belongs to."
        )
        phantom = documented - shipped
        assert not phantom, (
            f"the PRD names {sorted(phantom)} and the app serves no such path. Either the route "
            "was removed or re-pathed in src/companion/app/routes/, or the PRD invented it."
        )

    def test_both_open_questions_read_as_resolved(self) -> None:
        """``OQ-A`` and ``OQ-B`` carry their answers, not a deferral.

        Both were answered by the build long before story 15.3: all four payload shapes were fixed
        together in ``contracts.py`` (with an import-time assertion that refuses to let a process
        start if they drift), and ``openapi-typescript`` is AD-12's one generator. They are kept
        rather than deleted — a PRD that silently loses its open questions cannot be audited — so
        what this checks is that each still appears **and** reads as resolved.
        """
        section = _section(_prd(), OPEN_QUESTIONS_HEADING)
        bullets = [line for line in section.splitlines() if line.lstrip().startswith("- ")]
        for question in ("OQ-A", "OQ-B"):
            owning = [b for b in bullets if question in b]
            assert len(owning) == 1, (
                f"§12 has {len(owning)} bullets naming {question}; this guard needs exactly one. "
                "The questions are kept with their answers rather than deleted, so a missing "
                "bullet is a PRD that lost its audit trail."
            )
            assert "RESOLVED" in owning[0], (
                f"{question} does not read as resolved. It was answered by the build: OQ-A by the "
                "four fixed payload shapes in src/companion/contracts.py, OQ-B by "
                "openapi-typescript in ui/package.json under AD-12's one-generator rule. Record "
                "the answer in §12 rather than leaving the question parked."
            )
