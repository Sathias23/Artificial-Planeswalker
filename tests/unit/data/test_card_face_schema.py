"""Story c3-5, AC 22: typing ``card_faces`` must not truncate shipped MCP tool output.

``Card`` lives in ``src/data/schemas`` and is returned by ``lookup_card_by_name`` and every other
tool that hands back a card. Before c3-5 its ``card_faces`` was ``list[dict[str, Any]]`` — the
stored JSON, passed through byte for byte. Typing it as :class:`CardFace` puts a Pydantic model in
that path, and **Pydantic's default is to drop what it does not recognise**, which over the 6,455
face objects in the shipped corpus would silently delete up to nineteen keys per face from an
answer an agent is reading.

``extra="allow"`` is what stops that, and this file is the proof rather than the promise. The face
object below is a **real 24-key one**, spelled out from the census of the shipped 38,261-card
database: every key that appears on any stored face, with values of the types actually stored.
"""

from typing import Any

import pytest

from src.data.schemas.card import Card, CardFace

_REAL_FACE: dict[str, Any] = {
    # The four present on all 6,455 stored faces.
    "object": "card_face",
    "name": "Delver of Secrets",
    "mana_cost": "{U}",
    "oracle_text": "At the beginning of your upkeep, look at the top card of your library.",
    # Present on 6,445.
    "type_line": "Creature — Human Wizard",
    # Present on 5,556 — the one the resolver reads.
    "image_uris": {
        "small": "https://cards.scryfall.io/small/front/1/1/x.jpg?1700000000",
        "normal": "https://cards.scryfall.io/normal/front/1/1/x.jpg?1700000000",
        "large": "https://cards.scryfall.io/large/front/1/1/x.jpg?1700000000",
        "png": "https://cards.scryfall.io/png/front/1/1/x.png?1700000000",
        "art_crop": "https://cards.scryfall.io/art_crop/front/1/1/x.jpg?1700000000",
        "border_crop": "https://cards.scryfall.io/border_crop/front/1/1/x.jpg?1700000000",
    },
    # …and the eighteen this model does not name, every one of which must survive.
    "artist": "Nils Hamm",
    "artist_id": "5a5b1f2f-3d9f-4f9b-8f1a-000000000001",
    "artist_ids": ["5a5b1f2f-3d9f-4f9b-8f1a-000000000001"],
    "illustration_id": "1f4a1f2f-3d9f-4f9b-8f1a-000000000002",
    "colors": ["U"],
    "color_indicator": ["U"],
    "power": "1",
    "toughness": "1",
    "loyalty": None,
    "defense": None,
    "flavor_text": "Insanity is just a state of mind.",
    "printed_name": "Delver of Secrets",
    "printed_type_line": "Creature — Human Wizard",
    "printed_text": "At the beginning of your upkeep…",
    "watermark": "wizards",
    "layout": "transform",
    "oracle_id": "0e1e1f2f-3d9f-4f9b-8f1a-000000000003",
    "flavor_name": "Delver, Detective",
}

_CARD_ROW: dict[str, Any] = {
    "id": "00000000-0000-4000-8000-00000000c3f5",
    "name": "Delver of Secrets // Insectile Aberration",
    "oracle_id": "oracle-dfc",
    "mana_cost": "{U}",
    "cmc": 1.0,
    "type_line": "Creature — Human Wizard // Creature — Human Insect",
    "oracle_text": "",
    "rarity": "common",
    "set_code": "ISD",
    "set_name": "Innistrad",
    "collector_number": "51",
    "colors": ["U"],
    "color_identity": ["U"],
    "legalities": {"modern": "legal"},
}


def test_the_census_fixture_really_is_twenty_four_keys() -> None:
    """Non-vacuity: the round-trip below proves nothing over a three-key face."""
    assert len(_REAL_FACE) == 24


def test_a_real_face_round_trips_with_no_key_lost_and_no_value_changed() -> None:
    """AC 22 itself — the assertion the whole ``extra="allow"`` ruling rests on."""
    card = Card.model_validate({**_CARD_ROW, "card_faces": [_REAL_FACE]})

    dumped = card.model_dump()["card_faces"][0]

    # No key lost: every one of the 24 survives with its value untouched — including the two
    # explicit `None`s, which must stay `None` rather than being coerced into anything.
    for key, value in _REAL_FACE.items():
        assert key in dumped, f"CardFace dropped {key!r} — extra='allow' is not doing its job"
        assert dumped[key] == value, f"CardFace changed the value of {key!r}"


def test_the_only_added_keys_are_named_fields_the_source_omitted() -> None:
    """The one shape change c3-5 accepts, asserted rather than assumed.

    A named field the source object did not carry is serialised as an explicit ``null`` — additive
    to an MCP payload, never a truncation. Pinned so the difference is a decision on the record
    rather than something a later reader discovers in a diff.
    """
    sparse = {"object": "card_face", "name": "Half", "mana_cost": "{R}"}

    dumped = Card.model_validate({**_CARD_ROW, "card_faces": [sparse]}).model_dump()["card_faces"][
        0
    ]

    assert set(dumped) - set(sparse) == {"type_line", "oracle_text", "image_uris"}
    assert dumped["type_line"] is None
    assert dumped["oracle_text"] is None
    assert dumped["image_uris"] is None
    # …and nothing the source DID carry was touched.
    assert {k: dumped[k] for k in sparse} == sparse


def test_a_strict_model_would_have_truncated_it() -> None:
    """The counterfactual, so ``extra="allow"`` is provably load-bearing rather than decorative.

    Without this, the two tests above would pass identically under Pydantic's default and nothing
    would show that the config line is what makes them pass (c3-3's lesson: a guard whose firing
    was never observed is not a guard).
    """

    class _StrictFace(CardFace):
        model_config = {"extra": "ignore"}

    strict = _StrictFace.model_validate(_REAL_FACE).model_dump()

    assert "artist" not in strict
    assert len(strict) == 5, "the named fields, and nothing else — which is the failure mode"


@pytest.mark.parametrize("key", ["name", "mana_cost", "type_line", "oracle_text", "image_uris"])
def test_every_named_field_is_optional(key: str) -> None:
    """A required field would raise mid-read over the full corpus — the Epic 1 retro failure.

    ``type_line`` is missing from 10 of the 6,455 stored faces and ``image_uris`` from 899 of
    them, so two of these are not hypothetical. The other three are present on 100% today, and
    are optional anyway because a schema that asserts a fact about an upstream's data is a
    ``ValidationError`` waiting for that upstream to change.
    """
    face = dict(_REAL_FACE)
    del face[key]

    assert getattr(CardFace.model_validate(face), key) is None


def test_a_face_that_is_not_an_object_is_refused_rather_than_silently_kept() -> None:
    """The dict column has no schema, so the failure mode is worth pinning.

    A list or a string where a face object should be is corrupt data, and it must fail loudly at
    the read rather than reach the resolver as something with no ``image_uris`` attribute.
    """
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Card.model_validate({**_CARD_ROW, "card_faces": ["not-an-object"]})
