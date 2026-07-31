"""The committed OpenAPI schema matches what the live app produces (AD-12, story c2-3, AC 5).

This is the **Python half** of the type-generation drift gate. ``ui/src/api/openapi.json`` is a
committed hand-off artifact: ``scripts/dump_openapi.py`` writes it from ``build_app().openapi()``,
and ``openapi-typescript`` turns it into ``ui/src/api/types.d.ts`` in the ``frontend`` CI job. If a
Pydantic model changes and nobody regenerates, this test is what goes red — before the TypeScript
side ever sees the change.

**Why a test rather than the epic's "CI regenerates and runs ``git diff --exit-code``".** A
deliberate deviation, flagged rather than silently taken (the c1-9 / c2-1 / c2-2 precedent). The
coverage is identical — this renders from the live app in CI, which is exactly what regenerating
does — and a test buys three things a workflow step cannot: it runs inside a gate that already
exists, on **both** matrix Pythons; it runs locally for every developer with no CI round trip; and
its failure can *name the fix*, where ``git diff`` can only report that something differs.

The comparison is on **bytes**, not on parsed JSON, because the file's exact formatting is the
contract: the Node half re-reads these bytes, and ``ui/.prettierignore`` exists precisely so no
other tool reformats them. Byte equality also catches a CRLF write, which parsed-JSON equality
would wave through and which would make this test red on Windows and green on ubuntu from one
commit.
"""

import inspect
import json
import re
from typing import Any

from scripts.dump_openapi import OUTPUT_PATH, render_schema
from src.companion import contracts
from src.companion.app.main import build_app, without_python_docstring_sections
from src.companion.app.routes import health

REGENERATE = "uv run python -m scripts.dump_openapi"

#: Markers that must never cross the wire: two Google-style section headers and a doctest prompt.
PYTHON_INTERNALS = ("Args:", "Attributes:", ">>> ")

WIRE_VISIBLE_SECTIONS = frozenset({"Note:", "Warning:"})
"""The two section headers a wire description may legitimately keep (c2-3, Q1).

``main._DOCSTRING_SECTIONS`` deliberately does not truncate at these — they are ordinary prose a
reader of the generated types or ``/docs`` wants. Every other header of that shape is
Python-internal, which is what :data:`PYTHON_INTERNAL_FAMILIES` keys on. Stated as an allowlist
of two rather than a ban list of twelve, so an unlisted header (``Parameters:``,
``Keyword Args:`` misspelled, a numpy-style section) is caught rather than waved through.
"""

PYTHON_INTERNAL_FAMILIES: dict[str, re.Pattern[str]] = {
    "Sphinx role markup": re.compile(r":[a-z]+:`"),
    "a Google-style section header": re.compile(
        r"(?m)^[ \t]*([A-Z][A-Za-z]*(?: [A-Za-z]+)*:)[ \t]*$"
    ),
    "a doctest prompt": re.compile(r"(?m)^[ \t]*>>> "),
}
"""Shapes of Python-internal prose, keyed by FAMILY (story c3-2, Q5; standing agreement).

The predecessor :data:`PYTHON_INTERNALS` names three literal markers, which is the shape this
project has repeatedly measured to be evadable: it catches ``Args:`` and ``Attributes:`` and is
blind to ``Returns:``, ``Raises:``, ``Parameters:`` and every role marker
(``:class:`X```, ``:mod:`Y```, ``:data:`Z```) — the last of which c3-1 found in its own new
docstring, having shipped past a seven-member scan.

**What this does NOT decide, declared** (``deferred-work.md``, homed on review): whether a
sentence that is structurally clean actually *addresses a TypeScript reader*. "Supports
conversion from SQLAlchemy CardModel instances" trips no pattern here and is exactly the prose
c3-2 had to rewrite. That half is not statically decidable — the same limit
``copy-rules.test.ts`` declares for UX-DR33's second-person rule — and belongs to a human
reviewer, with a blind-spot row in ``ui/README.md`` saying so.
"""


def _descriptions(node: Any) -> list[str]:
    """Collect every ``description`` string in a decoded schema, at any depth.

    Args:
        node: Any part of the schema document.

    Returns:
        Every description found, in traversal order.
    """
    found: list[str] = []
    if isinstance(node, dict):
        description = node.get("description")
        if isinstance(description, str):
            found.append(description)
        for value in node.values():
            found.extend(_descriptions(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_descriptions(item))
    return found


def test_committed_schema_matches_the_live_app() -> None:
    """The committed schema is byte-identical to what the current app renders."""
    # Guarded so a deleted (or never-generated) file fails with the fix, not a bare
    # FileNotFoundError traceback — the instructive message is this test's whole point.
    assert OUTPUT_PATH.exists(), (
        f"{OUTPUT_PATH} is missing entirely — run `{REGENERATE}` and commit the result"
    )
    committed = OUTPUT_PATH.read_bytes()
    rendered = render_schema().encode("utf-8")

    assert committed == rendered, (
        f"{OUTPUT_PATH.name} is stale: the committed schema no longer matches what the app "
        f"produces. A companion contract, route or docstring changed without regenerating. "
        f"Fix: run `{REGENERATE}`, then `cd ui && npm run gen:types`, and commit BOTH files "
        f"(`npm run gen:api` does the pair in one command). Committing a fresh schema with a "
        f"stale types.d.ts reddens the frontend CI job instead."
    )


def test_committed_schema_is_not_empty() -> None:
    """The non-vacuity pair: the snapshot above is comparing a populated schema.

    A renderer that produced ``{}`` — a broken ``build_app()``, a schema hook that swallowed its
    input — would make the byte comparison pass the moment someone committed the empty output, and
    the whole generated pipeline downstream would be guarding nothing.
    """
    schema: dict[str, Any] = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))

    assert "/health" in schema["paths"], "the health route is missing from the committed schema"
    schemas = schema["components"]["schemas"]
    # Both models reach components only because build_app() declares the app-level
    # responses=error_responses(...) — a model no route references never lands there at all.
    assert "HealthResponse" in schemas
    assert "ErrorResponse" in schemas


def test_render_schema_is_the_writers_own_rendering() -> None:
    """``render_schema`` produces exactly one trailing newline and no CR bytes.

    The writer opens the file with ``newline="\\n"``; this pins the other half of that bargain, so
    a future edit that switches to ``json.dump(...)`` or drops the trailing newline is caught here
    rather than as a mystery cross-platform drift failure in CI.
    """
    rendered = render_schema()

    assert rendered.endswith("}\n")
    assert not rendered.endswith("}\n\n")
    assert "\r" not in rendered


class TestDescriptionsAreSummaries:
    """AC 17 (Q1, Brad 2026-07-27): a description stops at the first Google-style section header."""

    def test_no_description_carries_a_python_internal_section(self) -> None:
        """Nothing the wire carries names a Python parameter, attribute or doctest."""
        offenders = [
            (marker, description)
            for description in _descriptions(build_app().openapi())
            for marker in PYTHON_INTERNALS
            if marker in description
        ]

        assert not offenders, (
            "OpenAPI descriptions must be summaries, not whole docstrings: "
            f"{[marker for marker, _ in offenders]} reached the schema. "
            "without_python_docstring_sections() truncates at the FIRST Google-style section "
            "header, so a marker got through one of two ways: the normaliser was removed or "
            "reordered on _CompanionFastAPI.openapi(), or a docstring carries the marker ABOVE "
            "any section header (e.g. a bare doctest in the opening prose — move it under "
            "Example:, where truncation cuts it)."
        )

    def test_the_source_docstrings_do_contain_them(self) -> None:
        """The non-vacuity pair: the assertion above has something to strip.

        Without this, deleting the normaliser *and* the prose from every docstring would leave the
        test green while the rule it enforces had quietly stopped existing.
        """
        sources = [
            inspect.getdoc(contracts.HealthResponse) or "",
            inspect.getdoc(contracts.ErrorResponse) or "",
            inspect.getdoc(health.read_health) or "",
        ]
        combined = "\n".join(sources)

        for marker in PYTHON_INTERNALS:
            assert marker in combined, (
                f"no source docstring contains {marker!r}, so the truncation test above proves "
                "nothing — add the marker back, or retire both tests together"
            )

    def test_no_description_matches_a_python_internal_family(self) -> None:
        """The same rule, keyed on shape rather than on three remembered spellings (c3-2, Q5).

        This is the assertion that would have caught c3-1's ``:class:`X``` and would catch a
        ``Returns:`` or a ``Parameters:`` — none of which :data:`PYTHON_INTERNALS` names.
        """
        offenders = [
            (family, match.group(0), description[:60])
            for description in _descriptions(build_app().openapi())
            for family, pattern in PYTHON_INTERNAL_FAMILIES.items()
            for match in pattern.finditer(description)
            if match.group(0).strip() not in WIRE_VISIBLE_SECTIONS
        ]

        assert not offenders, (
            f"{len(offenders)} wire description(s) carry Python-internal prose: {offenders}. "
            "Fix at the PYTHON DOCSTRING — rewrite the leading summary for a TypeScript reader "
            "and push the detail below a truncating section header — never by editing the "
            "generated file. If the header is genuinely wire-appropriate prose, it belongs in "
            "WIRE_VISIBLE_SECTIONS, which is a two-member ruling, not a convenience."
        )

    def test_each_family_catches_something_it_should(self) -> None:
        """Non-vacuity for the family scan: each pattern fires on a planted example.

        A regex that matches nothing passes the scan above for free. This proves all three
        genuinely discriminate — and that the two wire-visible headers are the *only* ones the
        section family lets through, so the allowlist is not silently absorbing the ban.
        """
        fires = {
            "Sphinx role markup": "See :class:`Card` for detail.",
            "a Google-style section header": "A summary.\n\nRaises:\n    ValueError: sometimes.",
            "a doctest prompt": "A summary.\n\n>>> Card(id='x')\n",
        }
        for family, sample in fires.items():
            assert PYTHON_INTERNAL_FAMILIES[family].search(sample), f"{family} matched nothing"

        section = PYTHON_INTERNAL_FAMILIES["a Google-style section header"]
        # Fires on an unlisted header the truncator has never heard of...
        assert section.search("A summary.\n\nParameters:\n    x: numpy style.")
        # ...and the allowlist is what spares the two ruled-permitted ones, not the pattern.
        assert section.search("A summary.\n\nNote:\n    still prose.")
        assert {m.group(0).strip() for m in section.finditer("Note:\nWarning:")} <= (
            WIRE_VISIBLE_SECTIONS
        )
        # Ordinary prose containing a colon is NOT a section header — the shape is a whole line.
        assert not section.search("Two fields answer this: images and faces.")

    def test_the_summary_itself_survives(self) -> None:
        """Truncation keeps the useful half — the prose c2-9 needs on hover.

        The point of Q1 was to cut Python's sections, not the documentation. If this goes red
        alongside a passing truncation test, the normaliser has become "strip descriptions
        entirely", which is the alternative Q1 explicitly declined.
        """
        schemas = build_app().openapi()["components"]["schemas"]

        health_description = schemas["HealthResponse"]["description"]
        assert health_description.startswith("The body of ``GET /health``")
        assert "FR-14" in health_description

        error_description = schemas["ErrorResponse"]["description"]
        # The per-token enumeration is the half c2-9's state panels are written against.
        assert "``database_not_initialized``" in error_description
        assert "``internal_error``" in error_description

    def test_a_description_that_is_only_a_section_loses_the_key(self) -> None:
        """An all-sections description drops out rather than becoming an empty string.

        A bare ``"description": ""`` would emit an empty ``@description`` block in the generated
        TypeScript — noise in a drift-checked file.
        """
        schema: dict[str, Any] = {
            "components": {
                "schemas": {
                    "OnlySections": {"description": "Attributes:\n    x: an attribute."},
                    "HasSummary": {"description": "A summary.\n\nArgs:\n    y: an argument."},
                    "NotAString": {"description": {"nested": "left alone"}},
                }
            }
        }

        result = without_python_docstring_sections(schema)["components"]["schemas"]

        assert "description" not in result["OnlySections"]
        assert result["HasSummary"]["description"] == "A summary."
        assert result["NotAString"]["description"] == {"nested": "left alone"}

    def test_example_data_is_not_documentation(self) -> None:
        """A ``description`` key inside example/default payload data is left byte-identical.

        c3-1's decks carry a ``description`` field, so example payloads will too. Truncating —
        or even whitespace-stripping — data would make the committed schema misrepresent the
        payload, and a value that *is* a bare section header would lose its key entirely.
        A property merely *named* ``example`` is still documentation, though: ``properties``
        keys are field names, not data markers.
        """
        schema: dict[str, Any] = {
            "components": {
                "schemas": {
                    "Deck": {
                        "description": "A deck.\n\nArgs:\n    gone: cut.",
                        "examples": [{"description": "Returns:"}],
                        "default": {"description": "Trailing space is data too.  "},
                        "properties": {
                            "example": {"description": "A field named example.\n\nArgs:\n    x."}
                        },
                    }
                }
            }
        }

        result = without_python_docstring_sections(schema)["components"]["schemas"]["Deck"]

        assert result["description"] == "A deck."
        assert result["examples"] == [{"description": "Returns:"}]
        assert result["default"] == {"description": "Trailing space is data too.  "}
        assert result["properties"]["example"]["description"] == "A field named example."

    def test_keyword_sections_also_terminate(self) -> None:
        """``Keyword Args:`` and its siblings are section headers too (c2-3 review)."""
        schema: dict[str, Any] = {"description": "A summary.\n\nKeyword Args:\n    x: internal."}

        assert without_python_docstring_sections(schema)["description"] == "A summary."

    def test_note_sections_are_kept(self) -> None:
        """``Note:`` is prose worth keeping, and is deliberately not a terminator."""
        schema: dict[str, Any] = {"description": "A summary.\n\nNote:\n    Worth reading."}

        assert without_python_docstring_sections(schema)["description"] == (
            "A summary.\n\nNote:\n    Worth reading."
        )


def test_schema_is_stable_across_builds() -> None:
    """Two renders of two freshly-built apps agree.

    The committed artifact is only meaningful if rendering is deterministic — a schema carrying a
    per-process value (an instance id, a timestamp, an unordered set) would redden the drift gate
    on every unrelated commit, and the response would be to weaken the gate rather than to fix the
    schema. Pinned here so the diagnosis is immediate.
    """
    assert render_schema() == render_schema()
    assert build_app().openapi() == build_app().openapi()
