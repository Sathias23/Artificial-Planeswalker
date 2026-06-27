"""Pure deck -> viewer view-model transform (no I/O, no DB).

Turns a :class:`~src.data.schemas.deck.Deck` into the JSON-serialisable object
the read-only viewer template renders. Kept framework-free and side-effect-free
so it is unit-testable without a database. Mirrors the data contract documented
in ``temp/design_handoff_deck_builder/README.md`` (the ``Deck``/``Card`` shape)
and the derivations in ``Deck Viewer.dc.html``'s ``renderVals()``, generalised
from the Rakdos-only palette to all WUBRG + multicolour + colourless.
"""

import re
from typing import Any

from src.data.schemas.card import Card
from src.data.schemas.deck import Deck, DeckCard

# Column order for the mana-value buckets (matches the design).
_BUCKETS: tuple[str, ...] = ("1", "2", "3", "4", "5", "6+")
_CURVE_HEIGHT_PX = 72

# WUBRG ordering for deterministic colour tallies/legends.
_COLOR_ORDER: tuple[str, ...] = ("W", "U", "B", "R", "G", "M", "C")
_COLOR_NAMES: dict[str, str] = {
    "W": "White",
    "U": "Blue",
    "B": "Black",
    "R": "Red",
    "G": "Green",
    "M": "Multicolour",
    "C": "Colourless",
}
# Solid accents for the colour pie + legend swatches.
_PIE_COLORS: dict[str, str] = {
    "W": "#e8d28a",
    "U": "#2a7fd6",
    "B": "#6a2fa0",
    "R": "#e23a1e",
    "G": "#3fa83f",
    "M": "#c52a55",
    "C": "#9a93a4",
}
# Card border tint by colour identity (keeps the design's R/B/BR values).
_BORDER_COLORS: dict[str, str] = {
    "W": "rgba(230,210,140,.5)",
    "U": "rgba(96,160,230,.5)",
    "B": "rgba(150,96,190,.45)",
    "R": "rgba(255,96,52,.5)",
    "G": "rgba(110,190,110,.5)",
    "M": "rgba(220,86,96,.5)",
    "C": "rgba(255,255,255,.14)",
}
# Single-colour mana pips (keeps the design's R/B gradients). Generic/numeric/
# hybrid/X symbols fall through to a grey pip that shows the symbol as a label.
_PIP_STYLES: dict[str, dict[str, str]] = {
    "W": {
        "bg": "radial-gradient(circle at 35% 28%, #fff8e0, #e8d28a 55%, #b08a3a)",
        "color": "#3a2e10",
    },
    "U": {
        "bg": "radial-gradient(circle at 35% 28%, #bfe3ff, #2a7fd6 55%, #143f7a)",
        "color": "#ffffff",
    },
    "B": {
        "bg": "radial-gradient(circle at 35% 28%, #7a6a86, #2a1a34 58%, #0c0712)",
        "color": "#dccfee",
    },
    "R": {
        "bg": "radial-gradient(circle at 35% 28%, #ffc190, #e23a1e 52%, #7e1212)",
        "color": "#ffffff",
    },
    "G": {
        "bg": "radial-gradient(circle at 35% 28%, #cdebb0, #3fa83f 55%, #1f5a24)",
        "color": "#ffffff",
    },
}
_GENERIC_PIP = {"bg": "radial-gradient(circle at 35% 28%, #4a4a54, #2c2c34)", "color": "#e8e8ee"}

# Five-stop art-placeholder gradients by colour class (extends makeArt()).
_ART_STOPS: dict[str, tuple[str, str, str, str, str, str]] = {
    "W": ("#fff4d0", "#e8d28a", "#b89a4a", "#6a5526", "#2a2010", "rgba(255,240,180,.34)"),
    "U": ("#7ec8ff", "#2a7fd6", "#143f7a", "#0a1f40", "#060f1f", "rgba(120,190,255,.32)"),
    "B": ("#9a6ad6", "#6a2fa0", "#34164f", "#160a26", "#0a0612", "rgba(150,100,220,.34)"),
    "R": ("#ffa23a", "#ec3f1e", "#9a1414", "#340a0c", "#140608", "rgba(255,180,100,.36)"),
    "G": ("#9be08a", "#3fa83f", "#1f6a2a", "#0e3318", "#07150c", "rgba(150,220,140,.32)"),
    "M": ("#ff8a44", "#c52a55", "#6a1c46", "#2a0e22", "#120710", "rgba(255,140,90,.3)"),
    "C": ("#c9c2cf", "#8a8294", "#4a4452", "#241f2a", "#0e0b12", "rgba(200,195,210,.28)"),
}
_ART_HOTSPOTS: tuple[tuple[int, int], ...] = (
    (50, 8),
    (24, 18),
    (74, 16),
    (38, 12),
    (62, 22),
    (44, 30),
)


def parse_mana_pips(mana_cost: str) -> list[str]:
    """Extract mana symbols from a Scryfall mana-cost string.

    Args:
        mana_cost: Cost in Scryfall format, e.g. ``"{2}{R}{R}"`` or ``""``.

    Returns:
        Ordered symbol list, e.g. ``["2", "R", "R"]``. Empty for ``""``.
    """
    return re.findall(r"\{(.+?)\}", mana_cost or "")


def map_pips(symbols: list[str]) -> list[dict[str, str]]:
    """Map raw mana symbols to renderable pip descriptors.

    Args:
        symbols: Raw symbols from :func:`parse_mana_pips`.

    Returns:
        One ``{"label", "bg", "color"}`` dict per symbol. Single WUBRG symbols
        render as a coloured, unlabelled pip; everything else (numbers, ``X``,
        hybrids, phyrexian) renders as a grey pip labelled with the symbol.
    """
    pips: list[dict[str, str]] = []
    for sym in symbols:
        style = _PIP_STYLES.get(sym)
        if style is not None:
            pips.append({"label": "", "bg": style["bg"], "color": style["color"]})
        else:
            pips.append({"label": sym, "bg": _GENERIC_PIP["bg"], "color": _GENERIC_PIP["color"]})
    return pips


def classify_color(card: Card) -> str:
    """Classify a card into a single colour class for tint/pie/art.

    Args:
        card: The card to classify.

    Returns:
        ``"W"``/``"U"``/``"B"``/``"R"``/``"G"`` for monocolour, ``"M"`` for
        multicolour, ``"C"`` for colourless.
    """
    colors = card.colors or []
    if len(colors) == 0:
        return "C"
    if len(colors) == 1 and colors[0] in _PIP_STYLES:
        return colors[0]
    return "M"


def card_bucket(cmc: float) -> str:
    """Map a converted mana cost to its column bucket.

    Args:
        cmc: Converted mana cost.

    Returns:
        One of ``"1".."5"`` or ``"6+"``; cmc 0 and 1 both fall in ``"1"``.
    """
    n = int(cmc)
    if n <= 1:
        return "1"
    if n >= 6:
        return "6+"
    return str(n)


def is_land(card: Card) -> bool:
    """Return True if the card is a land (excluded from columns/curve/avg).

    Classifies on the front face so a modal/double-faced card whose front is a
    spell (e.g. a ``"Sorcery // Land"`` type line) is treated as a nonland.
    """
    type_line = card.type_line or _face_value(card, "type_line")
    front = type_line.split("//")[0]
    return "land" in front.lower()


def _face_value(card: Card, key: str) -> str:
    """Read ``key`` from the card's first face (DFC fallback) as a string."""
    if card.card_faces:
        val = card.card_faces[0].get(key)
        if isinstance(val, str):
            return val
    return ""


def _art_for(color: str, index: int) -> str:
    """Build the gradient art placeholder for a colour class at a position."""
    c0, c1, c2, c3, c4, glow = _ART_STOPS.get(color, _ART_STOPS["C"])
    hx, hy = _ART_HOTSPOTS[index % len(_ART_HOTSPOTS)]
    return (
        f"radial-gradient(130% 95% at {hx}% 118%, {c0} 0%, {c1} 22%, {c2} 48%, "
        f"{c3} 76%, {c4} 100%), "
        f"radial-gradient(55% 45% at {hy}% 22%, {glow}, transparent 60%)"
    )


# Characters that could break out of a CSS ``url('...')`` inside a double-quoted
# HTML ``style`` attribute (quotes, parens, angle brackets, semicolon, backslash,
# whitespace). A URL containing any of these is rejected, not embedded.
_UNSAFE_URL_CHARS = frozenset("'\"()<>;\\ \t\r\n")


def _is_safe_art_url(url: str) -> bool:
    """Return True if a URL is safe to embed in a CSS ``url()`` / style attribute."""
    return url.startswith(("https://", "http://")) and not any(c in _UNSAFE_URL_CHARS for c in url)


def pick_art(card: Card, color: str, index: int) -> str:
    """Choose a CSS ``background`` value for a card's art.

    Prefers the real Scryfall ``art_crop`` image (front face for DFCs), and
    falls back to a colour-keyed gradient placeholder when none is available or
    the image URL fails validation (defence-in-depth against a malformed/hostile
    URL breaking out of the inline ``style`` attribute it is rendered into).

    Args:
        card: The card.
        color: Its colour class (from :func:`classify_color`).
        index: Position index, varying the gradient hotspot for visual variety.

    Returns:
        A CSS ``background`` value (a ``url(...)`` layer or a gradient).
    """
    uris = card.image_uris
    if not uris and card.card_faces:
        face_uris = card.card_faces[0].get("image_uris")
        if isinstance(face_uris, dict):
            uris = face_uris
    art_url = uris.get("art_crop") if uris else None
    if art_url and _is_safe_art_url(art_url):
        return f"url('{art_url}') center/cover, #0b0608"
    return _art_for(color, index)


def _land_swatch(card: Card) -> str:
    """Build a small swatch background for a land from its colour identity."""
    ci = [c for c in (card.color_identity or []) if c in _PIE_COLORS]
    if not ci:
        return "radial-gradient(circle at 35% 28%,#6a5a76,#2a1a34 60%,#100a18)"
    if len(ci) == 1:
        _, mid, deep, dark, _, _ = _ART_STOPS[ci[0]]
        return f"radial-gradient(circle at 35% 28%,{mid},{deep} 60%,{dark})"
    return f"linear-gradient(135deg,{_PIE_COLORS[ci[0]]},{_PIE_COLORS[ci[1]]})"


def _build_card(dc: DeckCard, index: int) -> dict[str, Any]:
    """Build the view-model for a single mainboard nonland card."""
    card = dc.card
    color = classify_color(card)
    pip_syms = parse_mana_pips(card.mana_cost or _face_value(card, "mana_cost"))
    oracle = card.oracle_text or _face_value(card, "oracle_text")
    type_line = card.type_line or _face_value(card, "type_line")
    return {
        "id": card.id,
        "name": card.name,
        "cmc": card.cmc,
        "bucket": card_bucket(card.cmc),
        "color": color,
        "border": _BORDER_COLORS[color],
        "typeLine": type_line,
        "qty": dc.quantity,
        "rarity": card.rarity,
        "pips": map_pips(pip_syms),
        "oracle": oracle,
        "art": pick_art(card, color, index),
    }


def build_view_model(deck: Deck) -> dict[str, Any]:
    """Transform a fully-loaded deck into the viewer's data object.

    Considers mainboard cards only (``sideboard is False``). Lands are split
    into a separate list; the columns, mana curve, colour pie and average mana
    value are computed over mainboard nonland cards.

    Args:
        deck: A deck with ``deck_cards[].card`` populated
            (e.g. from ``DeckRepository.get_deck_with_cards``).

    Returns:
        A JSON-serialisable dict consumed by ``template.html``.
    """
    mainboard = [dc for dc in deck.deck_cards if not dc.sideboard]
    nonland = [dc for dc in mainboard if not is_land(dc.card)]
    lands = [dc for dc in mainboard if is_land(dc.card)]

    # Stable order so output is deterministic: by cmc, then name.
    nonland_sorted = sorted(nonland, key=lambda dc: (dc.card.cmc, dc.card.name))
    cards = [_build_card(dc, i) for i, dc in enumerate(nonland_sorted)]

    columns: list[dict[str, Any]] = []
    for bucket in _BUCKETS:
        bucket_cards = [c for c in cards if c["bucket"] == bucket]
        columns.append(
            {
                "label": bucket,
                "count": sum(c["qty"] for c in bucket_cards),
                "cards": bucket_cards,
            }
        )

    curve_max = max([col["count"] for col in columns] + [1])
    curve = [
        {
            "label": col["label"],
            "count": col["count"],
            "hLg": f"{round(col['count'] / curve_max * _CURVE_HEIGHT_PX)}px",
        }
        for col in columns
    ]

    # Colour pie over mainboard nonland cards.
    tally: dict[str, int] = dict.fromkeys(_COLOR_ORDER, 0)
    for c in cards:
        tally[c["color"]] += c["qty"]
    color_total = sum(tally.values()) or 1
    pie_legend: list[dict[str, str]] = []
    stops: list[str] = []
    cursor = 0.0
    for code in _COLOR_ORDER:
        qty = tally[code]
        if qty == 0:
            continue
        pct = qty / color_total * 100
        stops.append(f"{_PIE_COLORS[code]} {cursor:.4f}% {cursor + pct:.4f}%")
        cursor += pct
        pie_legend.append(
            {"name": _COLOR_NAMES[code], "color": _PIE_COLORS[code], "pct": f"{round(pct)}%"}
        )
    pie_gradient = f"conic-gradient({', '.join(stops)})" if stops else _PIE_COLORS["C"]

    nonland_total = sum(c["qty"] for c in cards)
    land_total = sum(dc.quantity for dc in lands)
    avg_cmc = sum(c["cmc"] * c["qty"] for c in cards) / nonland_total if nonland_total else 0.0
    fmt = (deck.format or "Unknown").title()
    total_cards = nonland_total + land_total
    noun = "card" if total_cards == 1 else "cards"

    return {
        "name": deck.name,
        "meta": f"{fmt} · {total_cards} {noun}",
        "totalCards": total_cards,
        "avgCmc": f"{avg_cmc:.1f}",
        "columns": columns,
        "curve": curve,
        "pieGradient": pie_gradient,
        "pieLegend": pie_legend,
        "lands": [
            {"name": dc.card.name, "qty": dc.quantity, "swatch": _land_swatch(dc.card)}
            for dc in sorted(lands, key=lambda dc: dc.card.name)
        ],
        "landTotal": land_total,
    }
