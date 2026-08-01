"""The whole-artifact pins on the committed OpenAPI document — in **one** place (c3-4, Q5).

**Why this file exists.** Two route test modules each pinned the exact ``components.schemas`` key
set — ``test_routes_decks.py`` (c3-1's, updated by c3-2 and c3-3) and ``test_routes_cards.py``
(c3-2's). One fact, two hand-synchronised copies, so every schema-adding story had to edit both.
c3-2 found the second copy by running the suite rather than by reading its story; c3-3 did exactly
the same thing; and ``deferred-work.md`` homed the consolidation on c3-4 by name, predicting it
"will otherwise inherit the same surprise a third time". It did — both copies went red together
when c3-4 regenerated the schema — and Brad ruled *take it* (Q5, 2026-08-01).

**The division of labour this establishes**, and the rule a later story should follow:

* **Whole-artifact facts live here.** The complete path set and the complete component-schema key
  set. A story that adds a route or a model edits *this* file, in one place.
* **Per-route facts stay in the per-route module.** ``test_routes_decks.py`` asserts its own two
  paths and its own declared tokens; ``test_routes_cards.py`` asserts its own path and its own;
  ``test_routes_active_deck.py`` likewise. Those assertions are about the route under test and
  belong beside it.

The pins stay **hand-written and exact**. Deriving either set from the document would assert
nothing at all — the point is that a human decided the artifact should contain exactly these
things, so an unexpected addition or a silent removal both fail and name themselves.

Read from the **committed** ``ui/src/api/openapi.json`` rather than a live ``app.openapi()``: the
committed file is what ``npm run gen:types`` consumes and what the drift gates compare, so it is
the copy whose correctness the frontend actually depends on. (``test_openapi_contract.py`` is what
holds the committed copy and the live app to each other; this file is about what that agreed
document should *say*.)
"""

import json
from pathlib import Path

import pytest

_COMMITTED_SCHEMA = Path(__file__).resolve().parents[3] / "ui" / "src" / "api" / "openapi.json"


@pytest.fixture(scope="module")
def schema():
    """The committed OpenAPI document, parsed once for this module."""
    return json.loads(_COMMITTED_SCHEMA.read_text(encoding="utf-8"))


class TestTheDocumentIsReal:
    """Non-vacuity for everything below, asserted **first** so the pins cannot pass on nothing."""

    def test_the_fixture_parsed_a_populated_document(self, schema):
        # Asserted BEFORE the equalities rather than after (c3-1 review): read after, every one of
        # these is logically implied by the equality and can never fail independently. Read first,
        # they establish that the fixture is looking at a real document — an empty or wrong-shaped
        # parse gives empty sets, which would satisfy nothing here but would satisfy any
        # "X not in names" absence check.
        assert schema["paths"], "no paths parsed — the fixture is not reading a real document"
        assert schema["components"]["schemas"], "no component schemas parsed"
        assert "HealthResponse" in schema["components"]["schemas"], (
            "the oldest shape in the document is missing; this is not the companion schema"
        )


class TestThePathSet:
    """Every path the companion serves, and nothing else."""

    def test_the_paths_are_exactly_these(self, schema):
        # SIX as of c3-4 (`/api/active-deck`). A story adding a route edits this line — here, and
        # nowhere else. Note the two deck spellings are not a typo: the list is plural
        # `/api/decks`, the detail is singular `/api/deck/{deck_id}`, and c3-3's format check
        # hangs off the singular one.
        assert set(schema["paths"]) == {
            "/api/active-deck",
            "/api/cards/{card_id}",
            "/api/deck/{deck_id}",
            "/api/deck/{deck_id}/format-check",
            "/api/decks",
            "/health",
        }

    def test_the_spa_mount_leaks_no_path(self, schema):
        # The mount is installed at "/" and must never appear as an API path (c2-2).
        assert "/" not in schema["paths"]


class TestTheComponentSet:
    """Every named shape the backend describes, and nothing else.

    This is the pin that was duplicated across two files until c3-4. A **companion-local mirror**
    of a shape that already exists — a second card model, a hand-rolled deck summary — would show
    up here as an unexpected name, which is the AD-1 violation the pin was written to catch.
    """

    def test_the_component_names_are_exactly_these(self, schema):
        # ELEVEN as of c3-4. `Card` is c3-2's, the two `FormatCheck*` models are c3-3's, and
        # `ActiveDeck` / `ActiveDeckRequest` are c3-4's — the latter being the first REQUEST body
        # in the whole document; every shape before it described a response.
        assert set(schema["components"]["schemas"]) == {
            "ActiveDeck",
            "ActiveDeckRequest",
            "Card",
            "CardSummary",
            "DeckCardSummary",
            "DeckDetail",
            "DeckSummary",
            "ErrorResponse",
            "FormatCheckReport",
            "FormatCheckRow",
            "HealthResponse",
        }

    def test_the_auto_generated_validation_shapes_are_absent(self, schema):
        # `without_auto_validation_schema` strips FastAPI's auto-422 components on the schema-build
        # path. They would otherwise document a response the app can never emit — validation
        # failures answer `400 invalid_request` — straight into the generated TypeScript.
        names = set(schema["components"]["schemas"])

        assert "HTTPValidationError" not in names
        assert "ValidationError" not in names

    def test_no_security_scheme_is_documented(self, schema):
        # c3-4 Q4: the agent credential is read from `request.headers` inside a dependency, NOT
        # declared via a FastAPI security class. Had a security class been used, it would have
        # added a `securitySchemes` component here and a `security` block to the operation — and,
        # worse, raised its own HTTPException, answering `invalid_request` at its own status and
        # bypassing the `forbidden` token entirely. This asserts the choice held.
        assert "securitySchemes" not in schema.get("components", {})
