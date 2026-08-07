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
        # EIGHT as of c5-2 (`/api/session`). A story adding a route edits this line — here, and
        # nowhere else. Note the two deck spellings are not a typo: the list is plural
        # `/api/decks`, the detail is singular `/api/deck/{deck_id}`, and c3-3's format check
        # hangs off the singular one. c3-5's path parameter is spelled `scryfall_id` where its
        # sibling spells the same identifier `card_id`, because the epic names the path that way;
        # both publish the same constraint, which `test_routes_card_image.py` asserts.
        #
        # c5-2's `/api/session` is the first path added since c3-5, and it INVERTS c5-1's
        # headline: c5-1 shipped sixteen models and moved neither count, because a model no route
        # references never reaches the document at all. c5-2 puts one model on one route, so both
        # counts move together — 7 → 8 here and 12 → 13 below — which is the ordinary case the
        # confirmed-negative shape was the exception to.
        assert set(schema["paths"]) == {
            "/api/active-deck",
            "/api/card-image/{scryfall_id}",
            "/api/cards/{card_id}",
            "/api/deck/{deck_id}",
            "/api/deck/{deck_id}/format-check",
            "/api/decks",
            "/api/session",
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
        # THIRTEEN as of c5-2. `Card` is c3-2's, the two `FormatCheck*` models are c3-3's, and
        # `ActiveDeck` / `ActiveDeckRequest` are c3-4's — the latter being the first REQUEST body
        # in the whole document; every shape before it described a response.
        #
        # `CardFace` is c3-5's, and it is the first component that is not a shape this shell
        # invented: it types a JSON column `Card` already carried as `list[dict[str, Any]]`. It is
        # ALSO the first component with an open index signature — `extra="allow"`, because the
        # 6,455 stored face objects carry 24 distinct keys and a strict model would silently
        # truncate shipped MCP tool output. That is not an AD-1 breach: there is still exactly one
        # card shape and exactly one face shape, both in `src/data/schemas`.
        #
        # `SessionTicket` is c5-2's, and it is the first component this shell has added since
        # c3-5. It is ALSO the only one of the SEVENTEEN models c5-1 defined plus this one that
        # reaches the document: c5-1's sixteen are all still absent, because none is referenced by
        # a route yet and an unreferenced model never lands here. That asymmetry is the rule
        # working, not a gap — c5-5 declares the event union as `POST /agent/events`'s request
        # body and the rest arrive together at that point.
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
            "SessionTicket",
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


class TestTheDatabaseTokensAreDeclared:
    """Which operations promise which ``503``, pinned as a whole-artifact fact (c3-9, Q4).

    ``database_not_initialized`` was reachable on six routes and declared on none of them, while
    ``TestDatabaseStates`` asserted it by name in three test modules. The gap was a property of
    :func:`~src.companion.app.deps.get_session`, not of any route, so every data route inherited
    it by construction and the count only ever rose — c3-1 raised it, c3-2 re-confirmed it on a
    third route, and c3-9 ruled it because it is the story that renders the state.

    A whole-artifact pin rather than five per-route ones, deliberately: the declaration is made
    **per include** in :func:`~src.companion.app.main.build_app`, so "which routers carry it" is
    one decision with five consequences, and splitting it across five modules would be the
    hand-synchronised duplication this file exists to have stopped.
    """

    #: Every operation whose session comes from ``get_session`` and can therefore answer both.
    DATABASE_BACKED = (
        ("/api/decks", "get"),
        ("/api/deck/{deck_id}", "get"),
        ("/api/deck/{deck_id}/format-check", "get"),
        ("/api/cards/{card_id}", "get"),
        ("/api/card-image/{scryfall_id}", "get"),
    )

    @staticmethod
    def _reasons(schema, path: str, method: str, status: str) -> set[str]:
        """The tokens a declared response names, read out of its description."""
        description = schema["paths"][path][method]["responses"][status]["description"]
        assert description.startswith("reason: "), description
        return {token.strip() for token in description.removeprefix("reason: ").split("|")}

    @pytest.mark.parametrize(("path", "method"), DATABASE_BACKED)
    def test_every_database_backed_operation_declares_both_503_tokens(self, schema, path, method):
        # ONE entry naming each, not two entries — `error_responses` collapses tokens that share a
        # status, a documented behaviour that had never fired before this story because
        # `database_not_initialized` had never been declared anywhere.
        assert self._reasons(schema, path, method, "503") == {
            "database_not_initialized",
            "database_unavailable",
        }

    def test_health_keeps_the_narrower_inherited_declaration(self, schema):
        # `/health` takes no session and can answer NEITHER 503 token; its 503 is inherited from
        # c1-2 and deliberately not narrowed since (`main.py`). Widening an over-declaration it
        # structurally cannot honour would turn an inherited wart into a fresh lie, so c3-9 left
        # it alone — pinned here so that "left alone" is a decision rather than an oversight.
        assert self._reasons(schema, "/health", "get", "503") == {"database_unavailable"}

    def test_the_active_deck_routes_declare_no_503_at_all(self, schema):
        # c3-4's ruling, unchanged: no database dependency, so no 503 to promise. The narrowing
        # that made `responses` per-include rather than app-wide is what this asserts still holds.
        for method in ("get", "put"):
            assert "503" not in schema["paths"]["/api/active-deck"][method]["responses"]

    def test_the_session_route_declares_neither_a_503_nor_a_413(self, schema):
        # AC 23. c5-2 mirrors c3-4's ruling on both counts rather than inheriting either: no
        # database dependency means no 503 to promise, and a body-less GET means no 413. It is
        # therefore deliberately ABSENT from DATABASE_BACKED above — asserted below rather than
        # left as a silent omission, because a list a route quietly fails to join looks identical
        # to a list a route was forgotten from.
        #
        # The 413 half is the ledgered wart `deferred-work.md` homes on c5-5: a body-less GET that
        # declares one promises a `types.d.ts` consumer a branch that can never answer, and every
        # new GET route doubles it wherever it is declared. /health and the four database-backed
        # operations still carry theirs by inheritance; /api/session and /api/active-deck do not,
        # which is the direction the wart is being unwound in.
        responses = schema["paths"]["/api/session"]["get"]["responses"]

        # Non-vacuity: the operation really was found and really declares its typed failures, so
        # the two absences below are about a populated mapping rather than an empty one.
        assert set(responses) == {"200", "400", "500"}
        assert self._reasons(schema, "/api/session", "get", "400") == {"invalid_request"}
        assert self._reasons(schema, "/api/session", "get", "500") == {"internal_error"}
        assert ("/api/session", "get") not in self.DATABASE_BACKED

    def test_the_scan_can_tell_the_two_apart(self, schema):
        # Non-vacuity, and it is a real one: `_reasons` returns a SET parsed out of prose, so a
        # parser that silently returned everything or nothing would satisfy the equalities above
        # only by accident. This proves the two shapes it reads are genuinely different.
        assert self._reasons(schema, "/api/decks", "get", "503") != self._reasons(
            schema, "/health", "get", "503"
        )
        assert self._reasons(schema, "/api/deck/{deck_id}", "get", "404") == {"deck_not_found"}
