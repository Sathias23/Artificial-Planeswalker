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
from typing import Any

from scripts.dump_openapi import OUTPUT_PATH, render_schema
from src.companion import contracts
from src.companion.app.main import build_app, without_python_docstring_sections
from src.companion.app.routes import health

REGENERATE = "uv run python -m scripts.dump_openapi"

#: Markers that must never cross the wire: two Google-style section headers and a doctest prompt.
PYTHON_INTERNALS = ("Args:", "Attributes:", ">>> ")


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
            "without_python_docstring_sections() on _CompanionFastAPI.openapi() is what "
            "truncates them; if it was removed or reordered, the generated TypeScript now "
            "carries Python's Args:/Attributes:/doctests as JSDoc."
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
