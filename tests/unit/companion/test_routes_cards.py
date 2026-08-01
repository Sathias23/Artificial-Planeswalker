"""Story c3-2: ``GET /api/cards/{card_id}``, driven end to end.

The pattern ``test_routes_decks.py`` established: every test builds a **real** ``build_app()`` and
drives it through the ``lifespan_client`` seam against a **real** temporary SQLite file. The route
itself is four lines, so what is actually under test is everything it *consumes* — the session
dependency, both ``503`` paths, the new ``404`` token, the id-shape constraint routing into the
app-wide validation handler, and the SPA mount ordering — and consumption can only be proved by
letting the shipped wiring answer.

**The fixtures moved to ``conftest.py`` at c3-5** and nothing about them changed in the move.
They were always shared in spirit — c3-5's ``GET /api/card-image/…`` is driven against the same
six cards, and the alternative was a second hand-seeded set claiming to model the same measured
corpus. Two such sets drift the moment one is corrected, which this one already has been once, by
a code review. The names below are imported from there; read the fixture docstrings in
``conftest.py`` for the census they encode.

**Fixture card ids are canonical uuids, and that is not cosmetic.** ``test_routes_decks.py``'s
``_card()`` helper mints ids like ``"card-anchor"``, which this route's shape constraint rejects
with ``400`` before the handler runs. That helper therefore cannot be reused verbatim for anything
addressed through this endpoint, and ``conftest._uuid`` exists to make the distinction visible
rather than accidental.

**Every fixture card differs from every other on more than one asserted field** — c3-1's review
found 28 green tests over identical fixtures, where a mis-paired projection was invisible. The
three image-shape cards here differ in their images *and* their names, type lines and rarities.
"""

import json
from pathlib import Path

import pytest

from src.companion.app.main import build_app
from src.data.database import create_engine, init_database
from src.data.repositories.deck import DeckRepository
from tests.unit.companion.conftest import (
    _TOP_LEVEL_IMAGES,
    ABSENT_ID,
    ANCHOR_ID,
    MANY_FACE_ID,
    MULTI_FACE_ID,
    NO_IMAGE_ID,
    SCHEMA_ONLY_ID,
    SINGLE_FACE_ID,
    SPLIT_FACE_ID,
    _card,
    _point_at,
    _seed,
    _uuid,
)

# --------------------------------------------------------------------------------------------
# Paths under test. Literals, not built from the router — a test that imported the prefix would
# still pass if the prefix were wrong. Plural `/api/cards/`, matching deps.py, dump_openapi.py,
# EXPERIENCE.md:86 and the epic.
# --------------------------------------------------------------------------------------------

_CARD_PATH = "/api/cards/{card_id}"
_DECK_DETAIL_PATH = "/api/deck/{deck_id}"


# --------------------------------------------------------------------------------------------
# AC 1, AC 2: the full Card on the wire, unwrapped, from one repository call
# --------------------------------------------------------------------------------------------


class TestCardDetail:
    """AC 1: every field of ``Card``, unwrapped, hydrated from the local database."""

    async def test_returns_the_full_card_unwrapped(self, image_shapes, lifespan_client):
        async with lifespan_client(build_app()) as client:
            response = await client.get(_CARD_PATH.format(card_id=SINGLE_FACE_ID))

        assert response.status_code == 200
        body = response.json()
        # Unwrapped (AD-16): the card IS the body — no {"status": ...}, no {"card": {...}}.
        assert body["id"] == SINGLE_FACE_ID
        assert "card" not in body
        assert "status" not in body

        assert body["name"] == "Single Face"
        assert body["oracle_id"] == f"oracle-{SINGLE_FACE_ID}"
        assert body["type_line"] == "Creature — Human Wizard"
        assert body["oracle_text"] == "Single Face does something."
        assert body["mana_cost"] == "{1}"
        assert body["cmc"] == 11.0
        assert body["power"] == "2"
        assert body["toughness"] == "3"
        assert body["rarity"] == "rare"
        assert body["set_code"] == "TST"
        assert body["set_name"] == "Test Set"
        assert body["collector_number"] == "1"
        assert body["colors"] == ["R"]
        assert body["color_identity"] == ["R"]
        assert body["keywords"] == ["Flying"]
        assert body["legalities"] == {"standard": "legal", "commander": "legal"}
        assert body["games"] == ["paper", "arena", "mtgo"]
        assert body["image_uris"] == _TOP_LEVEL_IMAGES

    async def test_every_declared_field_is_present_on_the_wire(self, image_shapes, lifespan_client):
        """AC 1 names twenty-odd fields; assert the SET, so a dropped one cannot hide.

        The assertions above read fields by name and would not notice a field vanishing from the
        schema entirely — the response would simply stop being asked about it.
        """
        async with lifespan_client(build_app()) as client:
            body = (await client.get(_CARD_PATH.format(card_id=SINGLE_FACE_ID))).json()

        assert set(body) == {
            "id",
            "name",
            "printed_name",
            "oracle_id",
            "mana_cost",
            "cmc",
            "type_line",
            "oracle_text",
            "power",
            "toughness",
            "game_changer",
            "rarity",
            "set_code",
            "set_name",
            "collector_number",
            "colors",
            "color_identity",
            "color_indicator",
            "keywords",
            "legalities",
            "card_faces",
            "image_uris",
            "games",
        }

    async def test_no_price_field_is_served(self, image_shapes, lifespan_client):
        """AC 15: the epic's price AC is satisfied BY ABSENCE, and absence is asserted.

        The measurement that matters is the **data layer**: ``PRAGMA table_info(cards)`` lists 23
        columns and none of them is a price, and no ``Card``/``CardSummary`` field, importer path
        or UI consumer exists. A ``prices: null`` field on 100% of responses would be a permanently
        dead branch in the wire contract that c4-5 must handle for nothing.

        **Do not re-run "grep for ``price`` and expect nothing" as the check** — this story made
        that self-falsifying (review, 2026-07-31). Before c3-2 it returned one hit, a forward-
        looking CSS comment; after c3-2 it also returns this docstring, the two rewritten wire
        docstrings that say prices are absent, and the generated ``types.d.ts`` carrying them. The
        durable check is the column list and the absence of a field, not the word count.
        """
        async with lifespan_client(build_app()) as client:
            body = (await client.get(_CARD_PATH.format(card_id=SINGLE_FACE_ID))).json()

        assert not [key for key in body if "price" in key.lower()]
        # Non-vacuity: the body genuinely parsed and carries the fields it should.
        assert body["name"] == "Single Face"

    async def test_game_changer_survives_as_null_rather_than_false(
        self, image_shapes, lifespan_client
    ):
        """AD-4: three-state. ``None`` means "not yet backfilled" and must never coerce to False."""
        async with lifespan_client(build_app()) as client:
            body = (await client.get(_CARD_PATH.format(card_id=SINGLE_FACE_ID))).json()

        assert body["game_changer"] is None
        assert body["game_changer"] is not False


# --------------------------------------------------------------------------------------------
# AC 16: both image shapes, plus the card with neither
# --------------------------------------------------------------------------------------------


class TestImageShapes:
    """AC 16: every image shape the corpus contains, including the one the story denied existed.

    The two image *sources* (top-level ``image_uris`` and per-face ``image_uris``) are mutually
    exclusive — that count is real. What is NOT true, and what the first version of this class
    asserted, is that a card with a top-level image has no ``card_faces``: 368 split cards have
    both. See the `image_shapes` fixture for the corrected census.
    """

    async def test_a_single_faced_card_carries_top_level_images_and_no_faces(
        self, image_shapes, lifespan_client
    ):
        async with lifespan_client(build_app()) as client:
            body = (await client.get(_CARD_PATH.format(card_id=SINGLE_FACE_ID))).json()

        assert body["image_uris"] == _TOP_LEVEL_IMAGES
        assert set(body["image_uris"]) == {
            "art_crop",
            "border_crop",
            "large",
            "normal",
            "png",
            "small",
        }
        # `null`, not `{}` and not omitted — the UI branches on exactly this.
        assert body["card_faces"] is None
        assert "card_faces" in body

    async def test_a_multi_faced_card_carries_per_face_images_and_no_top_level(
        self, image_shapes, lifespan_client
    ):
        """The half a top-level-only fixture would never reach — 2,778 real cards look like this."""
        async with lifespan_client(build_app()) as client:
            body = (await client.get(_CARD_PATH.format(card_id=MULTI_FACE_ID))).json()

        assert body["image_uris"] is None
        assert "image_uris" in body  # null, not omitted
        assert len(body["card_faces"]) == 2
        assert [face["name"] for face in body["card_faces"]] == [
            "Two Faced",
            "Two Faced, Unleashed",
        ]
        # c3-5's rule depends on this and c3-2 is where it first crosses the wire: decide by the
        # PRESENCE OF PER-FACE image_uris, never by a layout string — `cards` has no layout column.
        #
        # `.get("image_uris")` rather than `["image_uris"]`: 447 real cards carry faces with NO
        # per-face images, so subscripting is the exact mistake this rule exists to prevent, and
        # writing it here would have made the test crash on the shape it is teaching about.
        assert all(face.get("image_uris", {}).get("normal") for face in body["card_faces"])
        assert body["card_faces"][0]["image_uris"] != body["card_faces"][1]["image_uris"]

    async def test_a_split_card_carries_faces_and_a_top_level_image(
        self, image_shapes, lifespan_client
    ):
        """368 real cards, and the shape the first version of this file asserted cannot exist.

        This is the case that breaks a consumer branching on ``card_faces !== null``: the faces
        are real (names, costs, type lines) but carry no images, and the artwork is the top-level
        ``image_uris`` the two halves share. Both docstrings on the wire now say so explicitly.
        """
        async with lifespan_client(build_app()) as client:
            response = await client.get(_CARD_PATH.format(card_id=SPLIT_FACE_ID))

        assert response.status_code == 200
        body = response.json()
        # Both fields populated at once — the combination the story's prose ruled out.
        assert body["image_uris"] == _TOP_LEVEL_IMAGES
        assert len(body["card_faces"]) == 2
        # …and not one face carries an image of its own, which is what makes per-face presence
        # the correct discriminator and `card_faces` presence the wrong one.
        #
        # ASSERTED ON THE VALUE, NOT ON KEY ABSENCE, and the change is c3-5's (Q4). Typing
        # `card_faces` as `CardFace` means the named fields are always serialised, so a face that
        # carries no artwork now says `"image_uris": null` where it used to omit the key. That is
        # additive on the wire — no key is lost and no value changes — and it makes "presence"
        # mean exactly one thing everywhere: a NON-EMPTY map, which is what `resolve_face_images`
        # implements. A key-presence test would now read every face as imaged and pass a split
        # card straight into the bug this assertion exists to catch.
        assert all(not face["image_uris"] for face in body["card_faces"])
        assert [face["name"] for face in body["card_faces"]] == ["Split Halves", "Other Half"]

    async def test_the_discriminator_is_per_face_images_not_card_faces_presence(
        self, image_shapes, lifespan_client
    ):
        """The rule c3-5 and c4-3 will code against, asserted as a rule rather than per-fixture.

        Across every seeded shape: a card has per-face images XOR a top-level image, and
        ``card_faces`` presence predicts neither. Written as a sweep so a future shape added to
        the fixture is covered without a new test — and so the wrong discriminator is visibly
        wrong rather than merely undocumented.
        """
        async with lifespan_client(build_app()) as client:
            bodies = {
                name: (await client.get(_CARD_PATH.format(card_id=cid))).json()
                for name, cid in (
                    ("single", SINGLE_FACE_ID),
                    ("split", SPLIT_FACE_ID),
                    ("dfc", MULTI_FACE_ID),
                    ("no-image", NO_IMAGE_ID),
                    ("neither", SCHEMA_ONLY_ID),
                    ("five-face", MANY_FACE_ID),
                )
            }

        def has_per_face(body) -> bool:
            # Truthiness, not key presence — see the comment in the split-card test above: c3-5's
            # `CardFace` typing serialises `"image_uris": null` on an unimaged face, so `in` would
            # answer True for all six shapes and this sweep would assert nothing. This spelling is
            # what `src/companion/app/images.py:resolve_face_images` actually does.
            return any(face["image_uris"] for face in body["card_faces"] or [])

        for name, body in bodies.items():
            assert not (has_per_face(body) and body["image_uris"] is not None), (
                f"{name} carries both image sources; they are mutually exclusive"
            )

        # `card_faces` presence predicts NOTHING about where the image is — proved in both
        # directions from real shapes, which is the whole finding.
        assert bodies["split"]["card_faces"] is not None
        assert bodies["split"]["image_uris"] is not None  # faces, yet top-level image
        assert bodies["dfc"]["card_faces"] is not None
        assert bodies["dfc"]["image_uris"] is None  # faces, and no top-level image
        assert bodies["single"]["card_faces"] is None
        assert bodies["single"]["image_uris"] is not None  # no faces, top-level image

    async def test_a_card_with_no_image_data_anywhere_is_an_ordinary_answer(
        self, image_shapes, lifespan_client
    ):
        """79 real cards. Not an error, not a 404 — a 200 with no image reachable anywhere.

        **All 79 carry a ``card_faces`` array**; "no image anywhere" does not mean "no faces".
        The first version of this test seeded ``card_faces: None`` for this case, a combination
        that matches zero rows in the corpus — see `SCHEMA_ONLY_ID` for that shape, kept and
        labelled separately.
        """
        async with lifespan_client(build_app()) as client:
            response = await client.get(_CARD_PATH.format(card_id=NO_IMAGE_ID))

        assert response.status_code == 200
        body = response.json()
        assert body["image_uris"] is None
        assert body["card_faces"] is not None
        # Value, not key presence — c3-5's `CardFace` typing serialises the null. See the split
        # card test above for why that distinction is now load-bearing.
        assert all(not face["image_uris"] for face in body["card_faces"])
        assert body["name"] == "No Image At All"

    async def test_the_schema_permitted_both_null_shape_round_trips(
        self, image_shapes, lifespan_client
    ):
        """Zero rows in the corpus, but the schema allows it — so its wire behaviour is known.

        Kept deliberately: `Card` types both fields nullable, so a future importer change or a
        hand-written row could produce this, and "we never checked" is a worse answer than a
        pinned one. The nulls must survive as ``null`` — not ``{}``, not omitted.
        """
        async with lifespan_client(build_app()) as client:
            body = (await client.get(_CARD_PATH.format(card_id=SCHEMA_ONLY_ID))).json()

        assert body["image_uris"] is None
        assert body["card_faces"] is None
        assert "image_uris" in body and "card_faces" in body

    async def test_card_faces_is_not_always_two(self, image_shapes, lifespan_client):
        """Measured histogram: 2 -> 3,222 cards, 3 -> 2, 5 -> 1. A `[front, back]` read is wrong."""
        async with lifespan_client(build_app()) as client:
            body = (await client.get(_CARD_PATH.format(card_id=MANY_FACE_ID))).json()

        assert len(body["card_faces"]) == 5

    async def test_the_null_image_assertions_are_not_vacuous(self, image_shapes, lifespan_client):
        """AC 25's pairing: a card that genuinely HAS images, from the same seeded database.

        Without this, a projection that returned ``None`` for every image field would satisfy
        every ``is None`` assertion above by coincidence.
        """
        async with lifespan_client(build_app()) as client:
            with_images = (await client.get(_CARD_PATH.format(card_id=SINGLE_FACE_ID))).json()
            without = (await client.get(_CARD_PATH.format(card_id=NO_IMAGE_ID))).json()

        assert with_images["image_uris"] is not None
        assert without["image_uris"] is None
        # And the two shapes are genuinely different cards, not one row read twice.
        assert with_images["id"] != without["id"]
        assert with_images["name"] != without["name"]
        assert with_images["type_line"] != without["type_line"]


# --------------------------------------------------------------------------------------------
# AC 4: the seventh token
# --------------------------------------------------------------------------------------------


class TestUnknownCard:
    """AC 4: a well-formed but unknown uuid answers the token, and only the token."""

    async def test_unknown_uuid_is_card_not_found(self, ready_db, lifespan_client):
        async with lifespan_client(build_app()) as client:
            response = await client.get(_CARD_PATH.format(card_id=ABSENT_ID))

        assert response.status_code == 404
        assert response.json() == {"reason": "card_not_found"}

    async def test_it_is_not_the_deck_token(self, ready_db, lifespan_client):
        """Two tokens share 404 as of this story, so the BODY is what distinguishes them.

        A status-only assertion would pass with ``deck_not_found`` at the raise site — probe (b).
        """
        async with lifespan_client(build_app()) as client:
            card = await client.get(_CARD_PATH.format(card_id=ABSENT_ID))
            deck = await client.get(_DECK_DETAIL_PATH.format(deck_id="no-such-deck"))

        assert card.status_code == deck.status_code == 404
        assert card.json() == {"reason": "card_not_found"}
        assert deck.json() == {"reason": "deck_not_found"}

    async def test_a_known_card_is_not_404(self, ready_db, lifespan_client):
        """AC 25's pairing: the same database answers 200 for the card it does hold."""
        async with lifespan_client(build_app()) as client:
            response = await client.get(_CARD_PATH.format(card_id=ANCHOR_ID))

        assert response.status_code == 200
        assert response.json()["name"] == "Anchor Card"


# --------------------------------------------------------------------------------------------
# AC 5: the malformed-id FAMILY (standing agreement: ban the family, never enumerate members)
# --------------------------------------------------------------------------------------------


_WELL_FORMED = _uuid("a0")

_MALFORMED_IDS = {
    "too-short": _WELL_FORMED[:-1],
    "too-long": _WELL_FORMED + "0",
    "wrong-hyphen-positions": "00000000-00000-400-8000-0000000000a0",
    "non-hex-characters": "zzzzzzzz-0000-4000-8000-0000000000a0",
    "empty-segment": "00000000--4000-8000-0000000000a0",
    "free-text": "not a uuid at all",
    # The four spellings `uuid.UUID` would have accepted AND NORMALISED, turning a malformed id
    # into a FOUND card — Q2's whole reason for rejecting that option. (The bare "no-hyphens"
    # entry that used to sit above was byte-identical to this one — 14 ids over 13 distinct
    # inputs. Removed in review: an enumeration that double-counts overstates its own coverage.)
    "uuid-32-hex-no-dashes": _WELL_FORMED.replace("-", ""),
    "uuid-braced": "{" + _WELL_FORMED + "}",
    "uuid-urn": "urn:uuid:" + _WELL_FORMED,
    "uuid-uppercase": _WELL_FORMED.upper(),
    # `$` means "end of input" in Pydantic 2.12's Rust engine but "before a trailing newline" in
    # Python's `re`. Pinned by name so a change of regex engine is a named failure rather than a
    # silent downgrade of this 400 to a 404 (measured both ways, 2026-07-31).
    "trailing-newline": _WELL_FORMED + "%0A",
}


class TestMalformedCardId:
    """AC 5: a malformed id is ``400 invalid_request``, produced by the existing handler."""

    @pytest.mark.parametrize(
        "card_id", list(_MALFORMED_IDS.values()), ids=list(_MALFORMED_IDS.keys())
    )
    async def test_a_malformed_id_is_invalid_request(self, ready_db, lifespan_client, card_id):
        async with lifespan_client(build_app()) as client:
            response = await client.get(_CARD_PATH.format(card_id=card_id))

        assert response.status_code == 400
        assert response.json() == {"reason": "invalid_request"}

    async def test_the_trailing_newline_canary_is_measuring_what_it_claims(
        self, ready_db, lifespan_client
    ):
        """The `%0A` entry above is a regex-ENGINE canary, and a 400 alone does not prove it fired.

        It exists because Python's ``re`` matches ``$`` before a trailing newline while Pydantic's
        Rust engine does not. But if the transport ever stopped percent-decoding the path, the
        handler would see a literal ``%0A``, which the pattern rejects for containing ``%`` — the
        same 400, and the canary would be green while testing nothing (review, 2026-07-31).

        So the decode is asserted positively instead: ``%61`` decodes to ``a``, completing a
        canonical id that MUST be found — a 200 only percent-decoding can explain. If the
        transport stopped decoding, that request would carry a literal ``%``, fail the pattern,
        and turn the first assertion below red. Given decoding is proven, the ``%0A`` request is
        genuinely exercising the ``$`` anchor. (An earlier draft of this docstring described a
        discarded ``%41``/uppercase design the code never implemented; review round 2,
        2026-07-31.)
        """
        async with lifespan_client(build_app()) as client:
            # %61 is 'a' — decodes into a canonical id that MUST be found.
            decoded_ok = await client.get(
                _CARD_PATH.format(card_id=ANCHOR_ID.replace("a", "%61", 1))
            )
            # The same id with a real trailing newline byte, percent-encoded.
            newline = await client.get(_CARD_PATH.format(card_id=ANCHOR_ID + "%0A"))

        # THE TEETH: percent-decoding is provably happening, because %61 reached the handler as
        # 'a' and found the card. Without decoding this would be a 400 like everything else.
        assert decoded_ok.status_code == 200, (
            "%61 did not decode to 'a' — the transport stopped percent-decoding, so the "
            "trailing-newline canary above is no longer testing the regex engine"
        )
        assert decoded_ok.json()["id"] == ANCHOR_ID
        # …and given decoding happens, the newline case is genuinely exercising the `$` anchor.
        assert newline.status_code == 400
        assert newline.json() == {"reason": "invalid_request"}

    async def test_the_uppercase_spelling_is_refused_rather_than_normalised(
        self, ready_db, lifespan_client
    ):
        """The sub-decision Q2 forced, asserted directly rather than inferred from the family.

        The point is not merely that uppercase is a 400 — it is that the SAME id in lowercase is a
        200. A pattern that rejected everything would satisfy the parametrised family above.
        """
        async with lifespan_client(build_app()) as client:
            upper = await client.get(_CARD_PATH.format(card_id=ANCHOR_ID.upper()))
            lower = await client.get(_CARD_PATH.format(card_id=ANCHOR_ID))

        assert upper.status_code == 400
        assert upper.json() == {"reason": "invalid_request"}
        assert lower.status_code == 200
        assert lower.json()["id"] == ANCHOR_ID

    async def test_a_well_formed_id_reaches_the_handler(self, ready_db, lifespan_client):
        """AC 25's pairing for the whole family: the constraint does not reject everything.

        Both live outcomes are proved from one fixture — a known id reaches the handler and gets
        its card; an unknown-but-well-formed id reaches the handler and gets the token. Neither
        is a 400, so the pattern is discriminating rather than closed.
        """
        async with lifespan_client(build_app()) as client:
            known = await client.get(_CARD_PATH.format(card_id=ANCHOR_ID))
            unknown = await client.get(_CARD_PATH.format(card_id=ABSENT_ID))

        assert known.status_code == 200
        assert unknown.status_code == 404
        assert unknown.json() == {"reason": "card_not_found"}

    async def test_an_encoded_slash_is_rejected_by_routing_not_by_the_handler(
        self, ready_db, lifespan_client
    ):
        """``%2F`` is decoded before matching, so the two-segment result matches no card route.

        c3-1 measured this on the deck route; pinned here rather than asserted in prose, because
        the answer comes from a different branch (the reserved prefix) than the 400 above.
        """
        async with lifespan_client(build_app()) as client:
            response = await client.get("/api/cards/a%2Fb")

        assert response.status_code == 404
        assert response.json() == {"reason": "invalid_request"}

    async def test_a_trailing_slash_redirects_to_the_canonical_spelling(
        self, ready_db, lifespan_client
    ):
        async with lifespan_client(build_app()) as client:
            response = await client.get(_CARD_PATH.format(card_id=ANCHOR_ID) + "/")

        assert response.status_code == 307
        assert response.headers["location"].endswith(_CARD_PATH.format(card_id=ANCHOR_ID))


# --------------------------------------------------------------------------------------------
# AC 3: the deck -> card identifier join
# --------------------------------------------------------------------------------------------


class TestIdentifierJoin:
    """AC 3: the two endpoints speak the same identifier — shown, not asserted."""

    async def test_a_card_id_read_from_a_deck_response_hydrates(self, ready_db, lifespan_client):
        """Take an id out of ``GET /api/deck/{id}`` and feed it to ``GET /api/cards/{id}``.

        This is the FR-13 claim end to end. Nothing here constructs the id: it is read from the
        deck response's own ``card_id``, so a mismatch between what deck entries carry and what
        the card route accepts fails here rather than in c4-1's fetch layer.
        """
        holder: dict[str, str] = {}

        async def seeder(session):
            repo = DeckRepository(session)
            session.add(_card(SINGLE_FACE_ID, "Joined Card", image_uris=_TOP_LEVEL_IMAGES))
            await session.commit()
            deck = await repo.create_deck(name="Joiner", format="standard")
            holder["id"] = deck.id
            await repo.add_card_to_deck(deck.id, SINGLE_FACE_ID, quantity=2)

        await _seed(ready_db, seeder)

        async with lifespan_client(build_app()) as client:
            deck_body = (await client.get(_DECK_DETAIL_PATH.format(deck_id=holder["id"]))).json()
            # Read the id out of the deck payload — do NOT reuse the constant.
            card_id = deck_body["cards"][0]["card_id"]
            card_response = await client.get(_CARD_PATH.format(card_id=card_id))

        assert card_response.status_code == 200
        card_body = card_response.json()
        assert card_body["id"] == card_id
        assert card_body["name"] == "Joined Card"
        # The nested summary and the full card agree — same row, two endpoints, one identifier.
        assert deck_body["cards"][0]["card"]["name"] == card_body["name"]
        # …and the full card carries what the summary deliberately omits (c3-1's CardSummary).
        assert "image_uris" not in deck_body["cards"][0]["card"]
        assert card_body["image_uris"] == _TOP_LEVEL_IMAGES


# --------------------------------------------------------------------------------------------
# AC 7: both 503 paths, inherited with no per-route ceremony
# --------------------------------------------------------------------------------------------


class TestDatabaseStates:
    """AC 7: proved THROUGH THE REAL ROUTE, not through the dependency in isolation."""

    async def test_missing_database_file(self, tmp_path, monkeypatch, lifespan_client):
        _point_at(monkeypatch, tmp_path / "absent.db")

        async with lifespan_client(build_app()) as client:
            response = await client.get(_CARD_PATH.format(card_id=ANCHOR_ID))

        assert response.status_code == 503
        assert response.json() == {"reason": "database_not_initialized"}

    async def test_schema_present_but_no_cards_is_also_not_initialized(
        self, tmp_path, monkeypatch, lifespan_client
    ):
        empty = _point_at(monkeypatch, tmp_path / "empty.db")
        engine = create_engine(f"sqlite+aiosqlite:///{empty.as_posix()}")
        try:
            await init_database(engine)
        finally:
            await engine.dispose()

        async with lifespan_client(build_app()) as client:
            response = await client.get(_CARD_PATH.format(card_id=ANCHOR_ID))

        assert response.status_code == 503
        assert response.json() == {"reason": "database_not_initialized"}

    async def test_corrupt_database_file(self, tmp_path, monkeypatch, lifespan_client):
        """A present-but-unreadable file: ``DatabaseError``, typed app-wide by c1-6's handler."""
        corrupt = _point_at(monkeypatch, tmp_path / "corrupt.db")
        corrupt.write_bytes(b"this is definitely not a sqlite database" * 8)

        async with lifespan_client(build_app()) as client:
            response = await client.get(_CARD_PATH.format(card_id=ANCHOR_ID))

        assert response.status_code == 503
        assert response.json() == {"reason": "database_unavailable"}

    async def test_a_healthy_database_answers_normally(self, ready_db, lifespan_client):
        """AC 25's pairing for all three: this path is not permanently 503."""
        async with lifespan_client(build_app()) as client:
            response = await client.get(_CARD_PATH.format(card_id=ANCHOR_ID))

        assert response.status_code == 200
        assert response.json()["id"] == ANCHOR_ID

    async def test_the_database_state_wins_over_a_malformed_id(
        self, tmp_path, monkeypatch, lifespan_client
    ):
        """MEASURED, and the opposite of what this test first asserted (2026-07-31).

        FastAPI's ``solve_dependencies`` runs sub-dependencies **and** collects parameter
        validation errors in one pass, raising ``RequestValidationError`` only *after* the
        dependencies have been solved. ``get_session`` therefore executes first, and its
        ``CompanionError`` propagates before the 400 is ever raised. So a malformed id sent to a
        backend with no database answers ``503 database_not_initialized``, not ``400``.

        Pinned rather than fixed. It is defensible — the backend genuinely cannot serve the
        request for a reason that outranks the client's spelling — and reordering would mean
        moving validation out of the framework's own pass. But it is invisible from the route
        source, and c3-9 (which polls the 503 states) and c4-1 (which owns the fetch layer) both
        need to know that ``invalid_request`` is not guaranteed for a malformed id: a UI that
        treated 503 as "retry" will retry a request that can never succeed. Ledgered in
        ``deferred-work.md``, homed at c3-9.
        """
        _point_at(monkeypatch, tmp_path / "absent.db")

        async with lifespan_client(build_app()) as client:
            response = await client.get(_CARD_PATH.format(card_id="nonsense"))

        assert response.status_code == 503
        assert response.json() == {"reason": "database_not_initialized"}

    async def test_a_malformed_id_is_a_400_once_the_database_is_ready(
        self, ready_db, lifespan_client
    ):
        """The pairing for the above: the 400 is real, it is just outranked by an unready backend.

        Without this, the test above reads as "malformed ids are 503", which is false.
        """
        async with lifespan_client(build_app()) as client:
            response = await client.get(_CARD_PATH.format(card_id="nonsense"))

        assert response.status_code == 400
        assert response.json() == {"reason": "invalid_request"}


# --------------------------------------------------------------------------------------------
# AC 9: not shadowed by the SPA mount — status AND body (c3-1 review R1)
# --------------------------------------------------------------------------------------------


class TestNotShadowedBySpa:
    """AC 9: registered above ``install_spa(app)``.

    **Content-type alone proves nothing, measured.** ``/api`` is in ``spa.py``'s
    ``_RESERVED_SEED``, so an ``/api`` path with no route behind it is refused by the mount and
    answered as ``404 application/json {"reason": "invalid_request"}`` — JSON, no doctype. An
    assertion reading only the content-type stays green with the router deleted (c3-1 review R1).
    These assert the status **and** the body: only a running endpoint produces the card or the
    ``card_not_found`` token.
    """

    async def test_the_route_is_served_by_the_endpoint_not_the_spa(
        self, image_shapes, lifespan_client
    ):
        async with lifespan_client(build_app()) as client:
            response = await client.get(_CARD_PATH.format(card_id=SINGLE_FACE_ID))

        assert response.headers["content-type"].startswith("application/json")
        assert "<!doctype html" not in response.text.lower()
        # The teeth: only the endpoint answers 200 with this card's own fields.
        assert response.status_code == 200
        assert response.json()["name"] == "Single Face"

    async def test_an_unknown_card_gives_the_token_not_the_index(self, ready_db, lifespan_client):
        async with lifespan_client(build_app()) as client:
            response = await client.get(_CARD_PATH.format(card_id=ABSENT_ID))

        assert response.status_code == 404
        # card_not_found can only come from the handler. invalid_request would mean no route.
        assert response.json() == {"reason": "card_not_found"}

    async def test_an_unrouted_api_path_is_refused_rather_than_falling_back(
        self, ready_db, lifespan_client
    ):
        """The non-vacuity pair: what the two tests above would see if the router were missing."""
        async with lifespan_client(build_app()) as client:
            response = await client.get("/api/card/does-not-exist")

        assert response.status_code == 404
        assert response.json() == {"reason": "invalid_request"}

    async def test_the_spa_mount_is_still_the_last_route(self):
        """The mechanism itself: nothing was appended after the mount."""
        routes = build_app().router.routes
        assert getattr(routes[-1], "name", None) == "spa"


# --------------------------------------------------------------------------------------------
# AC 2, AC 6: what the committed schema says
# --------------------------------------------------------------------------------------------


class TestCommittedSchema:
    """Read from the **committed** ``ui/src/api/openapi.json`` — the copy the UI depends on."""

    @pytest.fixture(scope="class")
    def schema(self):
        path = Path(__file__).resolve().parents[3] / "ui" / "src" / "api" / "openapi.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def test_the_literal_path_is_present_and_plural(self, schema):
        assert _CARD_PATH in schema["paths"]
        # The singular spelling, which is the deck detail route's shape and not this one's.
        assert "/api/card/{card_id}" not in schema["paths"]
        assert "/api/cards/{id}" not in schema["paths"]

    def test_this_routes_own_shape_is_described(self, schema):
        """AC 2: the ``Card`` shape this route answers with reaches the document.

        **The whole-artifact component pin moved out at c3-4** (Q5, Brad 2026-08-01), to
        ``test_committed_schema.py``. This was the *second* of the two hand-synchronised copies —
        the tax that c3-2 and c3-3 each paid by discovering it in a suite run rather than reading
        it in a story, and that ``deferred-work.md`` homed on c3-4 by name for exactly that reason.
        The consolidation is why c3-5 edits one pin instead of two.

        What stays here is this module's own fact: the card shape is present. The
        "and nothing else" half — where a companion-local mirror of a card would surface as an
        unexpected name — lives with the exact set, in one place.
        """
        names = set(schema["components"]["schemas"])

        # Non-vacuity first (c3-1 review): an empty parse gives an empty set.
        assert names, "no component schemas parsed — the fixture is not reading a real document"

        assert "Card" in names

    def test_the_route_declares_its_own_token_and_no_422(self, schema):
        """AC 6: the 404 is declared; the auto-422 stays stripped on the first validated route."""
        responses = schema["paths"][_CARD_PATH]["get"]["responses"]

        # Non-vacuity BEFORE the absence check (AC 25): a wrong path key would make "422 absent"
        # pass by finding nothing at all.
        assert responses, "no responses parsed for the card path"
        assert "200" in responses
        assert "400" in responses

        assert "422" not in responses
        assert "HTTPValidationError" not in json.dumps(schema)

        assert "404" in responses
        assert responses["404"]["description"] == "reason: card_not_found"
        assert (
            responses["404"]["content"]["application/json"]["schema"]["$ref"]
            == "#/components/schemas/ErrorResponse"
        )

    def test_the_app_level_responses_are_unchanged(self, schema):
        """AC 6: the route declares only what it uniquely produces.

        ``deck_not_found`` must NOT appear on the card path, and the app-wide tokens must not have
        been re-declared per route.
        """
        responses = schema["paths"][_CARD_PATH]["get"]["responses"]

        assert "deck_not_found" not in json.dumps(responses)
        # The app-level declarations are still the app's, and still reach this path.
        assert responses["400"]["description"] == "reason: invalid_request"
        assert responses["503"]["description"] == "reason: database_unavailable"

    def test_the_id_constraint_is_published_for_the_ui_to_read(self, schema):
        """Q2: the pattern lands in the document, so a client can validate before calling."""
        parameters = schema["paths"][_CARD_PATH]["get"]["parameters"]
        card_id = next(p for p in parameters if p["name"] == "card_id")

        assert card_id["in"] == "path"
        assert card_id["required"] is True
        assert (
            card_id["schema"]["pattern"]
            == r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        )
        # Lowercase-only is the ruling, so the published pattern must not carry A-F.
        assert "A-F" not in card_id["schema"]["pattern"]

    def test_the_response_body_is_the_card_component_unwrapped(self, schema):
        """AD-16: no envelope. The 200 is a bare ``$ref``, not an object wrapping one."""
        content = schema["paths"][_CARD_PATH]["get"]["responses"]["200"]["content"]
        body = content["application/json"]["schema"]

        assert set(body) == {"$ref"}
        assert body["$ref"] == "#/components/schemas/Card"
