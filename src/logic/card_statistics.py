"""The one set of card-statistics rules the agent and the companion both report from.

Land detection, mana-value bucketing and colour-pip counting each had several implementations —
four land rules in Python and a fifth in the companion UI — so the same deck got different land
counts, curves and colour counts from ``analyze_mana_curve`` and the companion's panels. This
module owns all three rules, and :func:`deck_statistics` computes them over a deck. The tool
(``src/mcp_server/tools/deck_analysis.py``) and the companion's deck detail
(:class:`DeckDetailWithStatistics`, served by ``GET /api/deck/{deck_id}``) both read from it, and
the UI draws the payload's figures rather than recomputing them.

The rules:

* **Land.** The word ``land`` in the type half (before the em-dash) of the card's **front face**.
  The front face's type line is ``card_faces[0].type_line`` when present, else the top-level
  ``type_line`` before ``" // "``. So a ``Sorcery // Land`` MDFC is a spell, a ``Card // Card``
  printing whose first face is a ``Land`` is a land, ``Artifact Creature — Lander`` is a spell
  and ``Land Creature — Forest Dryad`` is a land.
* **Mana-value bucket.** :data:`CURVE_BUCKETS` is ``1 … 7``: ``cmc`` rounds half up, anything at
  or below 1 folds into 1 (a 0-cost spell is castable on turn one) and anything at or above 7
  folds into 7, the open-ended "7 or more" bucket (UX-DR17).
* **Colour pips.** Read from the front face's cost (the split shape's front half first, then a
  non-blank top-level cost, then ``card_faces[0].mana_cost``), for non-land cards only, times the
  row's quantity. A hybrid credits each colour it can be paid with, Phyrexian is a modifier, a
  generic-hybrid such as ``{2/R}`` credits its colour, generic and ``{X}`` credit nothing, and
  ``{C}`` is colourless. These are ``ui/src/components/ManaCost/parse.ts``'s symbol rules.

Board policy: commander plus mainboard, sideboard excluded.

:func:`has_land_face` is a separate, deliberately different question — whether *any* face is a
land — used by the classifier to keep land-slot material (MDFCs included) out of ramp and tutors.

Pure functions over already-loaded Pydantic schemas: no I/O, no framework.
"""

import math
import re
from collections.abc import Iterable
from typing import Final, Literal, Self

from pydantic import BaseModel

from src.data.schemas.card import Card
from src.data.schemas.deck import Deck, DeckCard, DeckDetailFull

#: The curve's buckets, ascending. The last one means "7 or more".
CURVE_BUCKETS: Final[tuple[int, int, int, int, int, int, int]] = (1, 2, 3, 4, 5, 6, 7)

PipColour = Literal["W", "U", "B", "R", "G", "C"]

#: The colours a pip can credit, WUBRG then colourless — the order ``colour_pips`` is reported in.
PIP_COLOURS: Final[tuple[PipColour, ...]] = ("W", "U", "B", "R", "G", "C")

_FACE_SEPARATOR: Final = " // "
_TYPE_SUBTYPE_SEPARATOR: Final = "—"
_SYMBOL_RE: Final = re.compile(r"\{([^}]*)\}")
_DIGITS_RE: Final = re.compile(r"^\d+$")
_PIP_COLOUR_SET: Final[frozenset[str]] = frozenset(PIP_COLOURS)


# ---------------------------------------------------------------------------
# Land detection
# ---------------------------------------------------------------------------


def type_line_is_land(type_line: str) -> bool:
    """True when the word ``land`` appears before the em-dash of *type_line* (any case)."""
    return "land" in type_line.split(_TYPE_SUBTYPE_SEPARATOR)[0].lower().split()


def front_face_type_line(card: Card) -> str:
    """Return the type line of the card's front face.

    ``card_faces[0].type_line`` when the card has faces and the first one carries a type line,
    otherwise the top-level ``type_line`` before ``" // "``.
    """
    if card.card_faces and card.card_faces[0].type_line:
        return card.card_faces[0].type_line
    return card.type_line.split(_FACE_SEPARATOR)[0]


def is_land(card: Card) -> bool:
    """True when the card's front face is a land: the word ``land`` in its type half."""
    return type_line_is_land(front_face_type_line(card))


def has_land_face(card: Card) -> bool:
    """True when any face of the card is a land (whole word, in that face's type half).

    Checks every ``" // "`` half of the top-level ``type_line`` and every face's own
    ``type_line``. A different question from :func:`is_land`: an MDFC with a land back face is a
    spell to :func:`is_land` but has a land face here, which is what the classifier needs to keep
    land-slot material out of ramp and tutors.
    """
    type_lines = card.type_line.split(_FACE_SEPARATOR)
    if card.card_faces:
        type_lines.extend(face.type_line for face in card.card_faces if face.type_line)
    return any(type_line_is_land(type_line) for type_line in type_lines)


# ---------------------------------------------------------------------------
# Mana-value buckets
# ---------------------------------------------------------------------------


def mana_value_bucket(cmc: float) -> int:
    """Return the :data:`CURVE_BUCKETS` entry a mana value falls in.

    Rounds half up, then folds everything at or below 1 into 1 and everything at or above 7
    into 7.
    """
    rounded = math.floor(cmc + 0.5)
    return min(max(rounded, CURVE_BUCKETS[0]), CURVE_BUCKETS[-1])


# ---------------------------------------------------------------------------
# Colour pips
# ---------------------------------------------------------------------------


def _before_separator(cost: str) -> str:
    return cost.split(_FACE_SEPARATOR)[0].strip()


def front_face_mana_cost(card: Card) -> str:
    """Return the cost of the card's front face, or ``""`` when it has none.

    The split shape first (``"{1}{B} // {2}{U}"`` keeps its front half), then a non-blank
    top-level cost, then ``card_faces[0].mana_cost`` (itself split if it carries ``" // "``).
    """
    declared = card.mana_cost.strip()
    if _FACE_SEPARATOR in declared:
        return _before_separator(declared)
    if declared:
        return declared
    if card.card_faces:
        face_cost = (card.card_faces[0].mana_cost or "").strip()
        return _before_separator(face_cost) if _FACE_SEPARATOR in face_cost else face_cost
    return ""


def _symbol_colours(inner: str) -> tuple[str, ...]:
    """Return the colours one braced symbol credits, by ``parse.ts``'s ``classify`` rules."""
    upper = inner.upper()
    if _DIGITS_RE.match(upper) or upper == "X":
        return ()
    colours: list[str] = []
    others: list[str] = []
    phyrexian = False
    for part in upper.split("/"):
        if part == "P" and not phyrexian:
            phyrexian = True
            continue
        if part in _PIP_COLOUR_SET:
            colours.append(part)
            continue
        others.append(part)
    if not 1 <= len(colours) <= 2:
        return ()
    if len(colours) == 2 and colours[0] == colours[1]:
        return ()
    if len(others) > 1 or (others and not _DIGITS_RE.match(others[0])):
        return ()
    return tuple(colours)


def colour_pips(cost: str) -> dict[str, int]:
    """Count the pips a cost string credits to each colour, in :data:`PIP_COLOURS` order.

    Every colour is present, zeros kept. A hybrid ``{W/U}`` credits one white and one blue, so
    the counts can sum to more than the symbols in the cost.
    """
    counts: dict[str, int] = dict.fromkeys(PIP_COLOURS, 0)
    for inner in _SYMBOL_RE.findall(cost):
        for colour in _symbol_colours(inner):
            counts[colour] += 1
    return counts


# ---------------------------------------------------------------------------
# Deck statistics
# ---------------------------------------------------------------------------


class ColourPips(BaseModel):
    """How many mana symbols in a deck's costs credit one colour.

    Attributes:
        colour: ``W``, ``U``, ``B``, ``R``, ``G``, or ``C`` for colourless.
        count: The pips crediting it, summed over every copy.
    """

    colour: PipColour
    count: int


class DeckStatistics(BaseModel):
    """A deck's land count, spell count, mana curve and colour pips, over commander and mainboard.

    The sideboard is not counted. A card is a land when the word "land" appears in the type part
    of its front face, so a modal double-faced card whose front is a spell counts as a spell.

    Attributes:
        land_count: Land cards, summed over every copy.
        spell_count: Non-land cards, summed over every copy.
        curve: Non-land cards per mana value, for mana values 1 to 7 in that order. Mana values
            round half up; 0 and 1 share the first entry, and the last entry counts 7 or more.
        colour_pips: Six entries, one per colour in the order W, U, B, R, G, C, zeros kept: the
            pips in non-land front-face costs crediting that colour, summed over every copy. A
            hybrid symbol credits both of its colours; generic and X costs credit none.
    """

    land_count: int
    spell_count: int
    curve: tuple[int, int, int, int, int, int, int]
    colour_pips: tuple[ColourPips, ...]


def deck_statistics(deck_cards: Iterable[DeckCard]) -> DeckStatistics:
    """Compute the shared statistics over a deck's commander and mainboard rows.

    Args:
        deck_cards: The deck's card rows. Sideboard rows are skipped here.

    Returns:
        The statistics; an empty or all-land deck gives an all-zero curve and all-zero pips.
    """
    land_count = 0
    spell_count = 0
    curve = dict.fromkeys(CURVE_BUCKETS, 0)
    pips: dict[str, int] = dict.fromkeys(PIP_COLOURS, 0)
    for deck_card in deck_cards:
        if deck_card.sideboard:
            continue
        card = deck_card.card
        if is_land(card):
            land_count += deck_card.quantity
            continue
        spell_count += deck_card.quantity
        curve[mana_value_bucket(card.cmc)] += deck_card.quantity
        for colour, count in colour_pips(front_face_mana_cost(card)).items():
            pips[colour] += count * deck_card.quantity
    return DeckStatistics(
        land_count=land_count,
        spell_count=spell_count,
        curve=(
            curve[1],
            curve[2],
            curve[3],
            curve[4],
            curve[5],
            curve[6],
            curve[7],
        ),
        colour_pips=tuple(ColourPips(colour=colour, count=pips[colour]) for colour in PIP_COLOURS),
    )


def curve_distribution(statistics: DeckStatistics) -> dict[int, int]:
    """Return the curve as ``{bucket: count}`` over all seven :data:`CURVE_BUCKETS`, zeros kept."""
    return dict(zip(CURVE_BUCKETS, statistics.curve, strict=True))


class DeckDetailWithStatistics(DeckDetailFull):
    """A saved deck's metadata, card counts, full card list, and its card statistics.

    Everything ``DeckSummary`` carries, plus ``cards`` — one ``DeckCardFull`` per entry, each
    embedding the complete card record — and ``statistics``: the land count, spell count, mana
    curve and colour pips over the commander and mainboard, the same figures the agent's
    ``analyze_mana_curve`` tool reports for the deck. This is what a browser client renders a deck
    view from in a single request, and it draws the statistics as given rather than recomputing
    them.

    The order of ``cards`` is **not** meaningful and is not the order the cards were added. A
    consumer that wants a stable presentation order (by type, by mana value, by name) must sort
    them itself.

    Attributes:
        Lives in ``src/logic`` because ``src/data`` may not import logic. Not a second deck shape
        (AD-1): it reuses ``DeckDetailFull``'s fields and adds only logic's figures, as
        ``FormatCheckReport`` does. Build it with :meth:`from_deck`.
    """

    statistics: DeckStatistics

    @classmethod
    def from_deck(cls, deck: Deck) -> Self:
        """Project a full ``Deck`` into a detail with its statistics computed.

        Args:
            deck: The source deck, with ``deck_cards`` (and each entry's ``card``) already
                loaded. See ``DeckSummary.from_deck`` for what happens when they are not.

        Returns:
            The detail, with its counts and statistics computed rather than defaulted.
        """
        detail = DeckDetailFull.from_deck(deck)
        return cls(**dict(detail), statistics=deck_statistics(deck.deck_cards))
