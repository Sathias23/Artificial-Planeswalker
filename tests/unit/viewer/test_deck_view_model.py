"""Unit tests for the pure deck -> viewer view-model transform.

Covers the spec's I/O & edge-case matrix (bucketing, land split, colour
classification, art selection, empty mainboard) with in-memory schemas — no DB.
"""

from datetime import UTC, datetime
from typing import Any

import pytest

from src.data.schemas.card import Card
from src.data.schemas.deck import Deck, DeckCard
from src.viewer.render import render_html
from src.viewer.view_model import (
    build_view_model,
    card_bucket,
    classify_color,
    is_land,
    map_pips,
    parse_mana_pips,
    pick_art,
)


def make_card(
    card_id: str,
    name: str,
    *,
    cmc: float = 1.0,
    mana_cost: str = "{R}",
    type_line: str = "Creature — Human",
    oracle_text: str = "Text.",
    rarity: str = "rare",
    colors: list[str] | None = None,
    color_identity: list[str] | None = None,
    image_uris: dict[str, str] | None = None,
    card_faces: list[dict[str, Any]] | None = None,
    power: str | None = None,
    toughness: str | None = None,
) -> Card:
    """Build a minimal valid Card for tests."""
    return Card(
        id=card_id,
        name=name,
        oracle_id=f"oracle-{card_id}",
        mana_cost=mana_cost,
        cmc=cmc,
        type_line=type_line,
        oracle_text=oracle_text,
        rarity=rarity,
        set_code="TST",
        set_name="Test Set",
        collector_number="1",
        colors=colors if colors is not None else ["R"],
        color_identity=color_identity if color_identity is not None else ["R"],
        legalities={},
        image_uris=image_uris,
        card_faces=card_faces,
        power=power,
        toughness=toughness,
    )


def make_deck(
    cards: list[tuple[Card, int, bool]], *, name: str = "Test Deck", fmt: str | None = "standard"
) -> Deck:
    """Build a Deck from (card, quantity, sideboard) tuples."""
    now = datetime.now(UTC)
    deck_cards = [
        DeckCard(deck_id="d1", card_id=c.id, quantity=qty, sideboard=sb, card=c)
        for c, qty, sb in cards
    ]
    return Deck(
        id="d1",
        name=name,
        format=fmt,
        created_at=now,
        updated_at=now,
        deck_cards=deck_cards,
    )


# --- helpers -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("cost", "expected"),
    [("{2}{R}{R}", ["2", "R", "R"]), ("{R}", ["R"]), ("", []), ("{X}{B}", ["X", "B"])],
)
def test_parse_mana_pips(cost: str, expected: list[str]) -> None:
    assert parse_mana_pips(cost) == expected


def test_map_pips_colored_vs_generic() -> None:
    pips = map_pips(["2", "R", "W"])
    assert pips[0]["label"] == "2"  # generic shows the number
    assert pips[1]["label"] == "" and "e23a1e" in pips[1]["bg"]  # red pip, no label
    assert pips[2]["label"] == "" and "e8d28a" in pips[2]["bg"]  # white pip


@pytest.mark.parametrize(
    ("colors", "expected"),
    [(["R"], "R"), ([], "C"), (["W", "U"], "M"), (["G"], "G")],
)
def test_classify_color(colors: list[str], expected: str) -> None:
    assert classify_color(make_card("c", "C", colors=colors)) == expected


@pytest.mark.parametrize(
    ("cmc", "expected"),
    [(0, "1"), (1, "1"), (2, "2"), (5, "5"), (6, "6+"), (7, "6+")],
)
def test_card_bucket(cmc: float, expected: str) -> None:
    assert card_bucket(cmc) == expected


def test_is_land() -> None:
    assert is_land(make_card("l", "Mountain", type_line="Basic Land — Mountain"))
    assert not is_land(make_card("c", "Bear", type_line="Creature — Bear"))


def test_is_land_classifies_on_front_face() -> None:
    # MDFC with a spell front and a land back is NOT a land.
    assert not is_land(
        make_card("h", "Hagra Mauling // Hagra Broodpit", type_line="Sorcery // Land")
    )
    # MDFC with a land front IS a land.
    assert is_land(make_card("s", "Sea Gate // Sea Gate, Reborn", type_line="Land // Sorcery"))


def test_pick_art_real_image_then_gradient() -> None:
    with_art = make_card("a", "A", image_uris={"art_crop": "https://img/x.jpg"})
    assert pick_art(with_art, "R", 0).startswith("url('https://img/x.jpg')")
    without = make_card("b", "B", image_uris=None)
    assert pick_art(without, "R", 0).startswith("radial-gradient")


def test_pick_art_rejects_unsafe_url() -> None:
    # A URL that would break out of the style attribute falls back to a gradient.
    hostile = make_card("h", "H", image_uris={"art_crop": 'https://x/a.jpg") onerror=alert(1)'})
    assert pick_art(hostile, "R", 0).startswith("radial-gradient")
    # A non-http scheme is also rejected.
    scheme = make_card("j", "J", image_uris={"art_crop": "javascript:alert(1)"})
    assert pick_art(scheme, "R", 0).startswith("radial-gradient")


def test_pick_art_dfc_face_fallback() -> None:
    dfc = make_card(
        "d",
        "Front // Back",
        image_uris=None,
        card_faces=[{"image_uris": {"art_crop": "https://img/face.jpg"}}],
    )
    assert "https://img/face.jpg" in pick_art(dfc, "R", 0)


# --- build_view_model --------------------------------------------------------


def test_bucketing_and_lands_excluded() -> None:
    deck = make_deck(
        [
            (make_card("a", "Zero", cmc=0), 1, False),
            (make_card("b", "One", cmc=1), 4, False),
            (make_card("c", "Five", cmc=5), 2, False),
            (make_card("d", "Seven", cmc=7), 1, False),
            (
                make_card(
                    "m",
                    "Mountain",
                    type_line="Basic Land — Mountain",
                    colors=[],
                    color_identity=["R"],
                ),
                6,
                False,
            ),
        ]
    )
    vm = build_view_model(deck)
    counts = {col["label"]: col["count"] for col in vm["columns"]}
    assert counts["1"] == 5  # cmc 0 (×1) + cmc 1 (×4)
    assert counts["5"] == 2
    assert counts["6+"] == 1
    # Land excluded from columns, listed separately, counted in total.
    assert vm["landTotal"] == 6
    assert vm["totalCards"] == 5 + 2 + 1 + 6
    assert [c["name"] for c in vm["columns"][0]["cards"]] == ["Zero", "One"]


def test_avg_cmc_over_nonland() -> None:
    deck = make_deck(
        [
            (make_card("a", "A", cmc=2), 2, False),
            (make_card("b", "B", cmc=4), 2, False),
            (make_card("l", "Forest", type_line="Basic Land — Forest", colors=[]), 10, False),
        ]
    )
    # (2*2 + 4*2) / 4 = 3.0 — lands ignored.
    assert build_view_model(deck)["avgCmc"] == "3.0"


def test_multicolor_and_colorless_in_pie() -> None:
    deck = make_deck(
        [
            (make_card("m", "Multi", colors=["W", "U"], color_identity=["W", "U"]), 2, False),
            (
                make_card("c", "Artifact", type_line="Artifact", colors=[], color_identity=[]),
                2,
                False,
            ),
        ]
    )
    vm = build_view_model(deck)
    names = {lg["name"] for lg in vm["pieLegend"]}
    assert "Multicolour" in names
    assert "Colourless" in names
    assert "conic-gradient" in vm["pieGradient"]


def test_sideboard_excluded() -> None:
    deck = make_deck(
        [
            (make_card("a", "Main", cmc=2), 4, False),
            (make_card("s", "Side", cmc=2), 3, True),
        ]
    )
    vm = build_view_model(deck)
    assert vm["totalCards"] == 4  # sideboard not counted


def test_empty_mainboard_does_not_crash() -> None:
    deck = make_deck([(make_card("s", "Side"), 2, True)], name="Empty")
    vm = build_view_model(deck)
    assert vm["totalCards"] == 0
    assert vm["avgCmc"] == "0.0"
    assert all(col["count"] == 0 for col in vm["columns"])
    assert vm["pieLegend"] == []


def test_meta_string_pluralization() -> None:
    one = make_deck([(make_card("a", "A", cmc=1), 1, False)], fmt="standard")
    assert build_view_model(one)["meta"] == "Standard · 1 card"
    many = make_deck([(make_card("a", "A", cmc=1), 3, False)], fmt="standard")
    assert build_view_model(many)["meta"] == "Standard · 3 cards"


def test_render_html_injects_json_and_escapes_script() -> None:
    nasty = make_card("a", "A", oracle_text="text </script> more")
    html = render_html(make_deck([(nasty, 1, False)]))
    assert "__DECK_JSON__" not in html  # placeholder replaced
    assert "</script> more" not in html  # the raw closing tag is neutralised
    assert "<\\/script>" in html


# --- power/toughness ---------------------------------------------------------


def _card_by_name(vm: dict[str, Any], name: str) -> dict[str, Any]:
    """Find a single nonland card's view-model dict by name across all columns."""
    for col in vm["columns"]:
        for card in col["cards"]:
            if card["name"] == name:
                return card
    raise AssertionError(f"card {name!r} not in view model")


def test_creature_exposes_power_toughness() -> None:
    deck = make_deck([(make_card("a", "Bear", power="2", toughness="2"), 1, False)])
    assert _card_by_name(build_view_model(deck), "Bear")["pt"] == "2/2"


def test_noncreature_has_no_pt() -> None:
    deck = make_deck(
        [(make_card("a", "Bolt", type_line="Instant", power=None, toughness=None), 1, False)]
    )
    assert _card_by_name(build_view_model(deck), "Bolt")["pt"] is None


def test_zero_power_is_not_dropped() -> None:
    # "0" is a valid power (e.g. Ornithopter 0/2); truthiness guard must keep it.
    deck = make_deck([(make_card("a", "Thopter", power="0", toughness="2"), 1, False)])
    assert _card_by_name(build_view_model(deck), "Thopter")["pt"] == "0/2"


def test_variable_power_toughness_rendered_verbatim() -> None:
    deck = make_deck([(make_card("a", "Goyf", power="*", toughness="1+*"), 1, False)])
    assert _card_by_name(build_view_model(deck), "Goyf")["pt"] == "*/1+*"


def test_dfc_falls_back_to_face_power_toughness() -> None:
    # Top-level P/T is None on DFCs; the viewer reads the front face like it does
    # for type_line / oracle_text.
    faces = [
        {"name": "Front", "type_line": "Creature — Human", "power": "3", "toughness": "2"},
        {"name": "Back", "type_line": "Creature — Werewolf", "power": "5", "toughness": "4"},
    ]
    deck = make_deck([(make_card("a", "Wolf", card_faces=faces), 1, False)])
    assert _card_by_name(build_view_model(deck), "Wolf")["pt"] == "3/2"


def test_vehicle_shows_pt_not_creature_gated() -> None:
    # Vehicles carry P/T but are not creatures; display is gated on P/T presence,
    # never on the type line, so a Vehicle must still show its P/T.
    deck = make_deck(
        [
            (
                make_card(
                    "a",
                    "Copter",
                    type_line="Artifact — Vehicle",
                    colors=[],
                    color_identity=[],
                    power="3",
                    toughness="3",
                ),
                1,
                False,
            )
        ]
    )
    assert _card_by_name(build_view_model(deck), "Copter")["pt"] == "3/3"
