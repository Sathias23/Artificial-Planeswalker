"""The single shared oracle-text taxonomy for deck-power assessment (AD-10, Story 5.3).

One vocabulary, defined once: every pattern that decides "what counts as ramp / card draw /
removal / a tutor / a win condition / a hard bracket trigger" lives in this module and nowhere
else. Downstream scoring stories (5.4 Karsten mana math, 5.5 consistency/interaction signals,
5.7 Bracket floor) and Epic 7's ``flags`` block consume these classifications; MCP tools and
skills call these functions and must never re-implement the pattern lists (AD-10).

Everything here is a pure function over already-loaded Pydantic schemas (:class:`Card` /
:class:`DeckCard`) — no network, DB, clock, or file I/O (AD-2). Matching is lowercased
substring/regex over ``oracle_text`` + ``keywords`` (+ ``type_line`` where a category demands
it), the :mod:`src.logic.synergy` precedent. Outputs are deterministically ordered (sorted
name tuples) so identical input always yields identical output (AD-8 spirit).

Category semantics are documented on each pattern constant; the pattern lists are provisional
v1 vocabulary — Story 5.9's benchmark pass owns tuning them (tests pin canonical-card
behavior, not pattern contents).
"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from src.data.schemas.card import Card
from src.data.schemas.deck import DeckCard

# ---------------------------------------------------------------------------
# The closed category-token set (AC5) — this module owns it; downstream stories
# (5.4/5.5/5.7, Epic 7 flags) import these tokens, never restate the strings.
# ---------------------------------------------------------------------------

#: FR6 — mana acceleration (rocks, dorks, land-fetch to battlefield). Lands themselves are
#: never ramp: they produce mana, ramp *accelerates* it (AC2 guardrail).
RAMP: Final = "ramp"
#: FR6 — card draw / advantage ("draw a card/two cards/that many cards" wordings).
CARD_DRAW: Final = "card_draw"
#: FR6 — removal/interaction: spot removal, counters, damage-to-target, and mass wipes.
INTERACTION: Final = "interaction"
#: FR6 — generic library search to hand or top of library. Land-fetch belongs to ramp.
#: NOTE for 5.7: tutors do NOT feed the Bracket floor — WotC removed tutor restrictions from
#: Brackets in Oct 2025 (docs/deck-assess.md:119); this count informs soft consistency only.
TUTOR: Final = "tutor"
#: FR10 — explicit "you win the game" / "each opponent loses the game" win conditions.
WINCON_EXPLICIT: Final = "wincon_explicit"
#: FR10 — conservative text-level combo-piece heuristic (mass untap, copy effects, repeatable
#: "any number of times" loops). A pre-signal only: real combo matching is Story 5.6's job
#: against the Spellbook snapshot and supersedes this tag for combo purposes.
WINCON_COMBO_PIECE: Final = "wincon_combo_piece"
#: FR10 — evasive/haymaker finishers: large bodies carrying evasion, or team-pump haymakers.
WINCON_FINISHER: Final = "wincon_finisher"
#: FR12 — mass land denial (symmetric destruction counts: Armageddon is canonical).
MASS_LAND_DENIAL: Final = "mass_land_denial"
#: FR12 — extra-turn effects. Presence-detection only; chain refinement is Story 5.7's.
EXTRA_TURN: Final = "extra_turn"

#: The closed set, in fixed documented order — ``classify_deck`` keys exactly this.
CATEGORIES: Final[tuple[str, ...]] = (
    RAMP,
    CARD_DRAW,
    INTERACTION,
    TUTOR,
    WINCON_EXPLICIT,
    WINCON_COMBO_PIECE,
    WINCON_FINISHER,
    MASS_LAND_DENIAL,
    EXTRA_TURN,
)

# ---------------------------------------------------------------------------
# Text access: one helper owns the matching-text policy (Task 1)
# ---------------------------------------------------------------------------

# Reminder-text stripping — deliberate, documented ~10-line duplication of
# src/search/index_builder.strip_reminder_text: src/logic must not import src/search (peer
# layer, AD-2 purity), and reminder text is a classifier false-positive source (Menace's
# reminder trips "can't be blocked"; cycling's reminder contains "Draw a card."). Keep the
# two implementations aligned if the span rules ever change.
_REMINDER_TEXT_RE: Final = re.compile(r"\([^()\n]*\)")
_MULTISPACE_RE: Final = re.compile(r" {2,}")


def _strip_reminder_text(oracle_text: str) -> str:
    """Remove parenthetical reminder-text spans, peeling nested spans to a fixed point."""
    without = oracle_text
    while True:
        stripped = _REMINDER_TEXT_RE.sub("", without)
        if stripped == without:
            break
        without = stripped
    lines = [_MULTISPACE_RE.sub(" ", line).strip() for line in without.split("\n")]
    return "\n".join(line for line in lines if line)


def _match_text(card: Card) -> str:
    """Return the single lowercased, reminder-stripped text every classifier matches against.

    Policy (trap #1): multi-face cards (split/DFC/MDFC) persist ``oracle_text=""`` with the
    real text in ``card_faces`` — when the top-level text is empty, fall back to joining all
    faces' ``oracle_text`` values (faces without the key contribute nothing). Reminder text
    is stripped *before* lowercasing so parenthetical restatements never trip a pattern
    (trap #2). Centralizing here means the fallback + stripping policy has exactly one owner.

    Args:
        card: The already-loaded card schema.

    Returns:
        Lowercased oracle text (or joined face texts) with reminder spans removed.
    """
    text = card.oracle_text
    if not text and card.card_faces:
        text = "\n".join(face.get("oracle_text", "") for face in card.card_faces)
    return _strip_reminder_text(text).lower()


def _keywords_lower(card: Card) -> frozenset[str]:
    """Return the card's keywords lowercased (Scryfall stores ``"Flying"``; guard ``None``)."""
    return frozenset(keyword.lower() for keyword in card.keywords or ())


def _parse_power(power: str | None) -> int | None:
    """Parse a numeric power value, returning ``None`` for ``None``/``"*"``/``"1+*"``-style."""
    if power is None:
        return None
    try:
        return int(power)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# FR6 pattern vocabulary (Task 2)
# ---------------------------------------------------------------------------

# Ramp: activated/triggered mana production ("{T}: Add {C}{C}" — Sol Ring, Llanowar Elves).
# Mana costs/symbols use braces, so "add {" only ever matches mana production. Cost-reduction
# effects are deliberately OUT of v1 scope (keep the vocabulary tight; 5.9 may widen it).
_MANA_ADD_RE: Final = re.compile(r"\badd \{")
# Ramp: land-fetch to the battlefield (Rampant Growth, Cultivate). Claimed by ramp, NOT tutor
# (AC2 guardrail) — the ordering is enforced structurally: _TUTOR excludes land searches.
_LAND_FETCH_RE: Final = re.compile(
    r"search your library for [^.]*\bland\b[^.]*\bonto the battlefield\b"
)

# Card draw / advantage: "draw a card", "draw two/three/... cards", "draw X cards", "draw
# that many cards" (Divination, Rhystic Study). Opponent-facing draw ("each opponent draws")
# is an accepted v1 false positive; impulse-style exile-to-play is OUT of v1 scope.
_DRAW_RE: Final = re.compile(
    r"\bdraws? (?:a card|(?:two|three|four|five|six|seven|x|that many|\d+) cards?)\b"
)

# Removal/interaction: spot removal, counters, damage-to-target, mass wipes (Swords to
# Plowshares, Counterspell, Lightning Bolt, Wrath of God). A dedicated board_wipe sub-tag is
# deferred to 5.5 if its 8x8 math needs one. "\bcounter target\b" cannot match "+1/+1
# counter on target" (different token order).
_INTERACTION_RES: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"\bdestroy target\b"),
    re.compile(r"\bexile target\b"),
    re.compile(r"\bcounter target\b"),
    re.compile(r"\bdeals? (?:\d+|x) damage to (?:any target|target)\b"),
    re.compile(r"\b(?:destroy|exile) (?:all|each)\b"),
)

# Tutors: generic library search (Demonic/Vampiric/Mystical Tutor). The captured object span
# (up to the sentence end) must not mention lands (land searches are ramp's, or nothing) and
# must not put onto the battlefield (battlefield-tutors like Natural Order are OUT of v1
# scope — FR6 defines tutors as search to hand or top of library).
_SEARCH_LIBRARY_RE: Final = re.compile(r"search your library for ([^.]*)")


def _is_tutor(text: str) -> bool:
    """True if any library-search span targets a non-land card to hand/top of library."""
    for match in _SEARCH_LIBRARY_RE.finditer(text):
        span = match.group(1)
        if "land" not in span and "onto the battlefield" not in span:
            return True
    return False


# ---------------------------------------------------------------------------
# FR10 pattern vocabulary (Task 3)
# ---------------------------------------------------------------------------

# Explicit wincons (Thassa's Oracle, Approach of the Second Sun style). "you win the game"
# cannot match "you can't win the game" / "your opponents can't win the game" (both lack the
# exact "you win" token order).
_WINCON_EXPLICIT_RES: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"\byou win the game\b"),
    re.compile(r"\b(?:each opponent|each other player) loses the game\b"),
)

# Combo-piece heuristics — conservative, text-level pre-signals only (Story 5.6's Spellbook
# matching supersedes this tag for real combo detection): mass/targeted untap loop enablers
# (Dramatic Reversal, Deceiver Exarch), copy effects (Kiki-Jiki, Dualcaster), and literal
# "any number of times" loop text.
_COMBO_PIECE_RES: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"\buntap (?:all|each|another|target|up to)\b"),
    re.compile(r"\bcopy target (?:spell|ability)\b"),
    re.compile(r"\ba copy of\b"),
    re.compile(r"\bany number of times\b"),
)

# Finisher: haymaker team-pump text (Craterhoof Behemoth, Overrun — "creatures you control
# get/gain ... +X/+X").
_HAYMAKER_RE: Final = re.compile(r"\bcreatures you control (?:get|gain)[^.\n]*\+")
# Finisher: evasion carried in oracle text ("can't be blocked" — Inkwell Leviathan style).
_UNBLOCKABLE_RE: Final = re.compile(r"\bcan't be blocked\b")
#: Evasion keywords (matched lowercased against ``Card.keywords`` and oracle text).
_EVASION_KEYWORDS: Final[frozenset[str]] = frozenset(
    {"flying", "menace", "trample", "shadow", "fear", "intimidate", "skulk"}
)
#: Minimum numeric power for the "large body" half of the evasive-finisher check.
#: Provisional v1 threshold (Story 5.9 owns tuning); non-numeric power never qualifies (AC3).
_FINISHER_POWER_MIN: Final = 5


def _is_finisher(card: Card, text: str) -> bool:
    """True for haymaker text, or a large evasive body (power >= threshold + evasion)."""
    if _HAYMAKER_RE.search(text):
        return True
    power = _parse_power(card.power)
    if power is None or power < _FINISHER_POWER_MIN:
        return False
    if _keywords_lower(card) & _EVASION_KEYWORDS:
        return True
    return bool(_UNBLOCKABLE_RE.search(text))


# ---------------------------------------------------------------------------
# FR12 pattern vocabulary (Task 4)
# ---------------------------------------------------------------------------

# Mass land denial: destroy/exile/return-ALL-lands (symmetric destruction counts — Armageddon
# is canonical), symmetric each-player land sacrifice, and lands-don't-untap stax (Winter
# Orb, Rising Waters). Single-target land removal (Stone Rain) is NOT mass denial.
_MLD_RES: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"\b(?:destroy|exile|return) (?:all|each) [^.\n]*\blands?\b"),
    re.compile(r"\beach player sacrifices [^.\n]*\blands?\b"),
    re.compile(r"\blands don't untap\b"),
)

# Extra turns: "take(s) an extra turn" (Time Warp, Temporal Mastery). Presence sets the
# signal; chain refinement beyond presence-detection is Story 5.7's concern.
_EXTRA_TURN_RE: Final = re.compile(r"\btakes? an extra turn\b")


# ---------------------------------------------------------------------------
# Public classification surface (Task 1)
# ---------------------------------------------------------------------------


def classify_card(card: Card) -> frozenset[str]:
    """Classify one card into the closed category-token set.

    The joinable per-card primitive: downstream stories join these tags back to the ``Card``
    (5.4 filters ramp/draw by ``cmc``; 5.5 computes CMC distributions over interaction).
    Categories are independent tags, not exclusive buckets — a draw-plus-removal modal spell
    holds both (AC2).

    Args:
        card: The already-loaded card schema to classify.

    Returns:
        A (possibly empty) frozenset of category tokens, each a member of
        :data:`CATEGORIES`.
    """
    text = _match_text(card)
    tags: set[str] = set()

    # FR6 — ramp. Land-typed cards are never ramp (AC2): lands produce mana rather than
    # accelerate it, and this also keeps fetchlands out. The top-level type_line joins all
    # faces with "//", so any land face excludes the card — a deliberate conservative choice
    # for mana math (an MDFC playable as a land is land-slot material, not acceleration).
    is_land = "land" in card.type_line.lower()
    if not is_land and (_MANA_ADD_RE.search(text) or _LAND_FETCH_RE.search(text)):
        tags.add(RAMP)

    # FR6 — card draw / advantage.
    if _DRAW_RE.search(text):
        tags.add(CARD_DRAW)

    # FR6 — removal/interaction.
    if any(pattern.search(text) for pattern in _INTERACTION_RES):
        tags.add(INTERACTION)

    # FR6 — tutors (structurally disjoint from ramp's land-fetch: land searches never count).
    if not is_land and _is_tutor(text):
        tags.add(TUTOR)

    # FR10 — win-condition tags.
    if any(pattern.search(text) for pattern in _WINCON_EXPLICIT_RES):
        tags.add(WINCON_EXPLICIT)
    if any(pattern.search(text) for pattern in _COMBO_PIECE_RES):
        tags.add(WINCON_COMBO_PIECE)
    if _is_finisher(card, text):
        tags.add(WINCON_FINISHER)

    # FR12 — hard-trigger tags.
    if any(pattern.search(text) for pattern in _MLD_RES):
        tags.add(MASS_LAND_DENIAL)
    if _EXTRA_TURN_RE.search(text):
        tags.add(EXTRA_TURN)

    return frozenset(tags)


@dataclass(frozen=True, slots=True)
class CategoryCount:
    """One category's deck-level aggregation: quantity-aware count + explaining names.

    Attributes:
        count: Quantity-aware total (a 4-of counts 4) of cards holding the category tag.
        card_names: Unique contributing card names, lexicographically sorted — the NFR2/FR23
            explainability payload (Epic 7 surfaces *which* cards drove a result).
    """

    count: int
    card_names: tuple[str, ...]


def classify_deck(deck_cards: Sequence[DeckCard]) -> Mapping[str, CategoryCount]:
    """Aggregate per-card classifications over a deck, quantity-aware and deterministic.

    Every token in :data:`CATEGORIES` is present as a key (zero-filled when no card holds
    it), so consumers never need membership checks. Sideboard rows are NOT filtered —
    deck-composition policy (what is "in the deck") belongs to the caller, not the taxonomy.

    Args:
        deck_cards: The deck's card associations (each carries ``quantity`` and the nested
            ``Card``).

    Returns:
        A mapping from every category token to its :class:`CategoryCount`; identical input
        always yields identical output (sorted name tuples, fixed key set).
    """
    counts: dict[str, int] = dict.fromkeys(CATEGORIES, 0)
    names: dict[str, set[str]] = {token: set() for token in CATEGORIES}

    for deck_card in deck_cards:
        for token in classify_card(deck_card.card):
            counts[token] += deck_card.quantity
            names[token].add(deck_card.card.name)

    return {
        token: CategoryCount(count=counts[token], card_names=tuple(sorted(names[token])))
        for token in CATEGORIES
    }


@dataclass(frozen=True, slots=True)
class HardTriggerFlag:
    """An FR12 deck-level hard-trigger result: the boolean plus the cards that drove it.

    Attributes:
        triggered: Whether any card in the input set carries the trigger (Story 5.7 consumes
            this for the Bracket floor).
        card_names: Unique contributing card names, sorted (FR23's ``flags`` explainability).
    """

    triggered: bool
    card_names: tuple[str, ...]


def _detect_hard_trigger(deck_cards: Sequence[DeckCard], token: str) -> HardTriggerFlag:
    """Scan a deck for one hard-trigger category and package the FR12 flag shape."""
    bucket = classify_deck(deck_cards)[token]
    return HardTriggerFlag(triggered=bucket.count > 0, card_names=bucket.card_names)


def detect_mass_land_denial(deck_cards: Sequence[DeckCard]) -> HardTriggerFlag:
    """Detect mass land denial across a deck (FR12; WotC hard bracket trigger).

    Symmetric destruction still counts — Armageddon is the canonical mass-land-denial card.

    Args:
        deck_cards: The deck's card associations.

    Returns:
        The deck-level boolean plus the sorted contributing card names.
    """
    return _detect_hard_trigger(deck_cards, MASS_LAND_DENIAL)


def detect_extra_turn_cards(deck_cards: Sequence[DeckCard]) -> HardTriggerFlag:
    """Detect extra-turn effects across a deck (FR12; WotC hard bracket trigger).

    A single extra-turn spell (Time Warp) sets the signal — chain refinement beyond
    presence-detection is Story 5.7's concern.

    Args:
        deck_cards: The deck's card associations.

    Returns:
        The deck-level boolean plus the sorted contributing card names.
    """
    return _detect_hard_trigger(deck_cards, EXTRA_TURN)
