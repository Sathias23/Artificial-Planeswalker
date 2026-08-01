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

from src.data.schemas.card import IMAGE_DISCRIMINATOR

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
        # SEVEN as of c3-5 (`/api/card-image/{scryfall_id}`). A story adding a route edits this
        # line — here, and nowhere else. Note the two deck spellings are not a typo: the list is
        # plural `/api/decks`, the detail is singular `/api/deck/{deck_id}`, and c3-3's format
        # check hangs off the singular one. c3-5's path parameter is spelled `scryfall_id` where
        # its sibling spells the same identifier `card_id`, because the epic names the path that
        # way; both publish the same constraint, which `test_routes_card_image.py` asserts.
        assert set(schema["paths"]) == {
            "/api/active-deck",
            "/api/card-image/{scryfall_id}",
            "/api/cards/{card_id}",
            "/api/deck/{deck_id}",
            "/api/deck/{deck_id}/format-check",
            "/api/decks",
            "/health",
        }

    def test_the_spa_mount_leaks_no_path(self, schema):
        # The mount is installed at "/" and must never appear as an API path (c2-2).
        assert "/" not in schema["paths"]


def _descriptions(node: object) -> list[str]:
    """Every ``description`` string anywhere in the document, at any depth.

    Args:
        node: Any parsed fragment of the OpenAPI document.

    Returns:
        The descriptions found beneath it, in traversal order.
    """
    found: list[str] = []
    if isinstance(node, dict):
        value = node.get("description")
        if isinstance(value, str):
            found.append(value)
        for child in node.values():
            found.extend(_descriptions(child))
    elif isinstance(node, list):
        for child in node:
            found.extend(_descriptions(child))
    return found


class TestTheImageDiscriminatorIsStatedOnce:
    """c3-5, Q6: the rule has one source, and a fourth paraphrase cannot appear silently.

    The same three paragraphs used to live in ``Card``'s docstring and in ``read_card``'s, and
    regenerated into two places here with **no gate between the copies** — ``deferred-work.md``
    homed the repair on c3-5 by name, because its image route would otherwise have made a third.
    The fix is a single constant attached to the fields it describes; this is what holds it.

    **A family, not a member** (C2 retro, standing). The check is not "the constant appears
    somewhere". It is: *any description that talks about this rule must BE the constant* — so a
    reworded copy fails, which is the failure mode a membership test cannot see.
    """

    def test_every_description_that_states_the_rule_is_the_one_source(self, schema):
        restatements = [
            text
            for text in _descriptions(schema)
            if "per-face" in text and "image_uris" in text and IMAGE_DISCRIMINATOR not in text
        ]

        assert not restatements, (
            "A description states the image discriminator in its own words:\n"
            + "\n".join(f"  - {text[:160]}…" for text in restatements)
            + "\nThe rule has exactly one source — `IMAGE_DISCRIMINATOR` in "
            "src/data/schemas/card.py. Attach it with `description=`; do not retell it."
        )

    def test_the_one_source_really_did_reach_the_document(self, schema):
        # Non-vacuity, and it is not implied by the test above: an absence check passes over a
        # document that lost the rule entirely, which would be a worse outcome than a paraphrase.
        carriers = [text for text in _descriptions(schema) if IMAGE_DISCRIMINATOR in text]

        # Three fields carry it: `Card.image_uris`, `Card.card_faces` and `CardFace.image_uris`.
        assert len(carriers) == 3, f"expected 3 fields to carry the rule, found {len(carriers)}"

    def test_the_family_scan_would_see_a_reworded_copy(self):
        # The guard's own firing case, proved rather than assumed (standing agreement: probe your
        # own guard before review does). Deliberately spelled UNLIKE the constant — a scan keyed
        # on the constant's own phrasing is the c3-3 failure, where a family caught 0 of 12
        # planted evasions because each was written the way its firing test wrote it.
        planted = {
            "components": {
                "schemas": {
                    "Something": {
                        "properties": {
                            "art": {
                                "description": (
                                    "Check for per-face image_uris to decide where the art is."
                                )
                            }
                        }
                    }
                }
            }
        }

        restatements = [
            text
            for text in _descriptions(planted)
            if "per-face" in text and "image_uris" in text and IMAGE_DISCRIMINATOR not in text
        ]

        assert len(restatements) == 1


class TestTheComponentSet:
    """Every named shape the backend describes, and nothing else.

    This is the pin that was duplicated across two files until c3-4. A **companion-local mirror**
    of a shape that already exists — a second card model, a hand-rolled deck summary — would show
    up here as an unexpected name, which is the AD-1 violation the pin was written to catch.
    """

    def test_the_component_names_are_exactly_these(self, schema):
        # TWELVE as of c3-5. `Card` is c3-2's, the two `FormatCheck*` models are c3-3's, and
        # `ActiveDeck` / `ActiveDeckRequest` are c3-4's — the latter being the first REQUEST body
        # in the whole document; every shape before it described a response.
        #
        # `CardFace` is c3-5's, and it is the first component that is not a shape this shell
        # invented: it types a JSON column `Card` already carried as `list[dict[str, Any]]`. It is
        # ALSO the first component with an open index signature — `extra="allow"`, because the
        # 6,455 stored face objects carry 24 distinct keys and a strict model would silently
        # truncate shipped MCP tool output. That is not an AD-1 breach: there is still exactly one
        # card shape and exactly one face shape, both in `src/data/schemas`.
        assert set(schema["components"]["schemas"]) == {
            "ActiveDeck",
            "ActiveDeckRequest",
            "Card",
            "CardFace",
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
