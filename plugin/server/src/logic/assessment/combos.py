"""FR13/FR15 pure combo matching, bracket mapping & derived values (Story 5.6).

The combo seam of the deck-power feature (AD-11): the deterministic matcher that
assigns each Spellbook variant its ``included``/``almost_included`` bucket (FR13 —
matching is pure core per AD-9; Epic 6 only delivers the data), the closed
``BRACKET_TAG_TO_BRACKET`` map, and the derived-not-stored helpers (``combo_type``,
``earliest_turn_estimate``) that feed Story 5.7's two-card-infinite Bracket trigger and
``combo_potential`` dimension. Raw signals only: no 0–100 mapping, no Bracket floor, no
confidence tokens, no serialization — those belong to 5.7/5.8/Epic 7. The record shape
itself is :class:`~src.data.schemas.combo.ComboRecord` at the schema layer (see its
module docstring for the AD-11 placement rationale); this module owns the semantics.

Everything here is a pure function over already-loaded Pydantic schemas — no network,
DB, clock, file I/O, or randomness (AD-2). Commanders arrive as an already-resolved
name list (AD-13): the core never resolves or queries for them. Outputs are
deterministically ordered (sorted by ``spellbook_id``) so identical input always yields
identical output (AD-8 spirit).

Relationship to :data:`~src.logic.assessment.classifiers.WINCON_COMBO_PIECE`: that tag
is an independent text-level *pre-signal* (oracle-text heuristics). This module's
Spellbook-backed matching supersedes it for combo purposes but does not touch it — the
two must never be conflated, which is why this module deliberately imports no sibling
assessment module.

Decide-once policies (documented at each code site): lowercased name comparison with
DFC front-face indexing; quantity-aware shortfall buckets; the commander requirement as
a zone gate that credits the command-zone piece toward availability; sideboard rows NOT
filtered (the standing
5.3/5.4/5.5 policy — deck composition belongs to the caller; Epic 7 passes
mainboard-only rows); ``"infinite"``-substring type detection; and the naive
one-land-per-turn earliest-turn model. The type tokens and turn heuristic are
provisional v1 values — Story 5.9's benchmark pass owns tuning them.
"""

import math
from collections import Counter
from collections.abc import Sequence
from typing import Final

from src.data.schemas.combo import ComboBracketTag, ComboRecord
from src.data.schemas.deck import DeckCard

# ---------------------------------------------------------------------------
# The combo→bracket map (AC4)
# ---------------------------------------------------------------------------

#: The closed ``bracket_tag`` → Bracket-floor input map — the exact six pairs from the
#: architecture addendum §C / spine AD-11 (Spellbook's published tag→power mapping).
#: Literal-keyed so an invalid key is a mypy error at call sites (the 5.4 lesson); a
#: test pins totality over :data:`~src.data.schemas.combo.ComboBracketTag`. The Bracket
#: floor itself (WotC decision tree) is Story 5.7's — no other bracket arithmetic here.
BRACKET_TAG_TO_BRACKET: Final[dict[ComboBracketTag, int]] = {
    "CASUAL": 1,
    "ODDBALL": 2,
    "PRECON_APPROPRIATE": 2,
    "POWERFUL": 3,
    "SPICY": 3,
    "RUTHLESS": 4,
}

# ---------------------------------------------------------------------------
# The closed derived-type token vocabulary (AC5) — PROVISIONAL v1 (5.9 owns tuning)
# ---------------------------------------------------------------------------

#: Derived combo type: an infinite loop needing exactly two pieces — the FR15 hard
#: Bracket trigger input (``bucket == "included"`` and this type, evaluated by 5.7).
TWO_CARD_INFINITE: Final = "two_card_infinite"
#: Derived combo type: an infinite loop needing three or more pieces.
MULTI_CARD_INFINITE: Final = "multi_card_infinite"
#: Derived combo type: a finite/value combo — nothing produced reads "infinite".
NON_INFINITE: Final = "non_infinite"

#: The closed token set in fixed documented order — defined already bytewise-sorted so
#: the documented order and the AD-8 emission order coincide (the
#: ``STRUCTURAL_GAP_TOKENS`` precedent).
COMBO_TYPE_TOKENS: Final[tuple[str, ...]] = (
    MULTI_CARD_INFINITE,
    NON_INFINITE,
    TWO_CARD_INFINITE,
)

# ---------------------------------------------------------------------------
# Name normalization — one owner for the matching-name policy (AC3)
# ---------------------------------------------------------------------------

#: Scryfall's face separator in joined multi-face names (``"Alive // Well"``).
_FACE_SEPARATOR: Final = " // "


def _name_keys(name: str) -> tuple[str, ...]:
    """Return the lookup keys a deck-card name is indexed under.

    The decide-once normalization policy: comparison is lowercased, and a multi-face
    ``Card.name`` (the ``" // "``-joined form) is indexed under BOTH the full joined
    name and its front face — Spellbook names single faces, ``Card.name`` may be
    ``"A // B"`` (the pre-phase-2 ``detect_synergies`` '//' lesson). Variant piece
    names and commander names are compared lowercased against these keys.

    Args:
        name: The card name as stored on :class:`~src.data.schemas.card.Card`.

    Returns:
        One or two lowercased keys (full name, plus the front face when distinct).
    """
    lowered = name.lower()
    if _FACE_SEPARATOR in lowered:
        return (lowered, lowered.split(_FACE_SEPARATOR)[0])
    return (lowered,)


def _availability(deck_cards: Sequence[DeckCard]) -> dict[str, int]:
    """Build the name→total-quantity availability index (quantity-aware, AC3).

    Sideboard rows are NOT filtered — the standing 5.3/5.4/5.5 policy: deck-composition
    belongs to the caller; Epic 7 passes mainboard-only rows.

    Args:
        deck_cards: The deck's card associations.

    Returns:
        Total available quantity per normalized name key (see :func:`_name_keys`).
    """
    counts: dict[str, int] = {}
    for deck_card in deck_cards:
        for key in _name_keys(deck_card.card.name):
            counts[key] = counts.get(key, 0) + deck_card.quantity
    return counts


def _cmc_by_name(deck_cards: Sequence[DeckCard]) -> dict[str, float]:
    """Build the name→``Card.cmc`` join under the same normalization as the matcher.

    Multi-face ``cmc`` is Scryfall's front-face value (the 5.4 ``CurveSignals``
    wording), so both keys of a DFC map to the same number. When two distinct cards
    collide on a key (rare), the first occurrence in ``deck_cards`` order wins —
    deterministic for identical input. Sideboard rows are included (see
    :func:`_availability`).

    Args:
        deck_cards: The deck's card associations.

    Returns:
        Mana value per normalized name key.
    """
    mana_values: dict[str, float] = {}
    for deck_card in deck_cards:
        for key in _name_keys(deck_card.card.name):
            mana_values.setdefault(key, deck_card.card.cmc)
    return mana_values


# ---------------------------------------------------------------------------
# The pure matcher (AC3)
# ---------------------------------------------------------------------------


def match_combos(
    deck_cards: Sequence[DeckCard],
    *,
    commanders: Sequence[str],
    variants: Sequence[ComboRecord],
) -> tuple[ComboRecord, ...]:
    """Match Spellbook variants against a deck — the FR13 bucket assignment.

    Multiplicity-aware: availability is the name→total-quantity index, need is a
    multiset over the variant's ``cards``, and the shortfall is the total across pieces
    (a variant needing the same name twice needs quantity ≥ 2). Shortfall ``0`` →
    ``bucket="included"``; exactly ``1`` → ``bucket="almost_included"``; ``≥ 2`` → the
    variant is excluded from the output entirely.

    Commander requirement (decide-once): a command-zone requirement cannot be drawn
    into, so it is a hard gate. When ``commander_required`` is true — empty
    ``commanders`` excludes the variant (FR25: assess without commander-required
    variants; the ``commander_unidentified`` confidence token is the edge's job, not
    this module's); otherwise the requirement is satisfied iff at least one of the
    variant's pieces is among the resolved commander names, else excluded. This is a
    documented v1 proxy — the bool cannot say WHICH piece must command. Commander names
    are normalized identically to deck cards (:func:`_name_keys` — a DFC commander's
    front face matches a variant naming just that face). A satisfied command-zone piece
    is not a shortfall: the command zone always supplies it, so each commander-matching
    piece is credited one copy of availability (a two-card commander combo whose other
    piece is in the deck is ``included``, not ``almost_included``).

    Matched records are ``model_copy(update={"bucket": ...})`` copies — inputs are
    never mutated and the output is the SAME :class:`ComboRecord` shape (AD-11, no
    parallel type). Sideboard rows are NOT filtered — filter first if unwanted.

    Args:
        deck_cards: The deck's card associations (quantity-aware).
        commanders: Resolved commander names, passed in as data (AD-13) — the core
            never resolves or queries for them.
        variants: Candidate combo records from the snapshot repo (``bucket=None``).

    Returns:
        The matched records with buckets assigned, sorted ascending bytewise by
        ``spellbook_id`` regardless of input order — identical input yields identical
        output.
    """
    available = _availability(deck_cards)
    commander_keys = {key for name in commanders for key in _name_keys(name)}
    matched: list[ComboRecord] = []
    for variant in variants:
        if variant.commander_required:
            if not commander_keys:
                continue
            if not any(piece.lower() in commander_keys for piece in variant.cards):
                continue
        need = Counter(piece.lower() for piece in variant.cards)
        shortfall = 0
        for name, required in need.items():
            have = available.get(name, 0)
            if variant.commander_required and name in commander_keys:
                have += 1  # the command zone always supplies this piece
            shortfall += max(0, required - have)
        if shortfall == 0:
            matched.append(variant.model_copy(update={"bucket": "included"}))
        elif shortfall == 1:
            matched.append(variant.model_copy(update={"bucket": "almost_included"}))
    return tuple(sorted(matched, key=lambda record: record.spellbook_id))


# ---------------------------------------------------------------------------
# Derived values — computed here, never stored (AC5)
# ---------------------------------------------------------------------------


def combo_type(combo: ComboRecord) -> str:
    """Derive the closed combo-type token for a record (AD-11 derived-not-stored).

    Infinite policy (decide-once, provisional): a combo is infinite when the substring
    ``"infinite"`` appears in any lowercased ``produces`` entry (Spellbook ``produces``
    entries are feature names like ``"Infinite mana"``) — conservative, 5.9 may tune.
    Two-card means ``len(combo.cards) == 2`` over the stored, multiplicity-inclusive
    piece list.

    Args:
        combo: The combo record (bucket state irrelevant).

    Returns:
        One :data:`COMBO_TYPE_TOKENS` member.
    """
    if not any("infinite" in produced.lower() for produced in combo.produces):
        return NON_INFINITE
    return TWO_CARD_INFINITE if len(combo.cards) == 2 else MULTI_CARD_INFINITE


def earliest_turn_estimate(combo: ComboRecord, deck_cards: Sequence[DeckCard]) -> int:
    """Estimate the earliest turn the combo could be fully deployed — PROVISIONAL v1.

    The naive one-land-per-turn model (implementation-owned per the spine's "Deferred";
    Story 5.9 tunes): assume one land drop per turn and nothing else, so mana available
    on turn ``T`` is ``T`` and cumulative mana is ``T*(T+1)/2``. The estimate is the
    smallest ``T`` with ``T >= ceil(max piece mana value)`` (you must be able to cast
    the biggest piece) and ``T*(T+1)/2 >= ceil(total piece mana value)`` (you must have
    paid for all pieces). Worked examples: pieces (2, 2) → total 4, max 2 → T=3 (T=2:
    3 < 4); pieces (1, 1) → T=2 (T=1: 1 < 2); pieces (6,) → T=6; no pieces → 1 (floor).
    Ramp/tutor acceleration is deliberately ignored — 5.7 combines this with ramp
    density for ``speed``; modeling it here would double-count acceleration.

    Piece mana values are joined from the deck's ``Card.cmc`` (front-face semantics)
    via the same name normalization as the matcher. Pieces not resolvable in the deck
    (e.g. the missing ``almost_included`` piece) are skipped from the sum — a
    documented optimistic undercount; a combo with zero resolvable pieces returns ``1``
    (the floor), never raises. ``cmc`` floats are ``ceil``-ed before comparison, so the
    result is pure integer arithmetic — deterministic, always ``int >= 1``. Sideboard
    rows are included in the join — filter first if unwanted.

    Args:
        combo: The combo record whose pieces to cost out.
        deck_cards: The deck's card associations (the name→cmc source).

    Returns:
        The estimated earliest turn, an ``int >= 1``.
    """
    mana_by_name = _cmc_by_name(deck_cards)
    piece_values = [
        mana_by_name[piece.lower()] for piece in combo.cards if piece.lower() in mana_by_name
    ]
    if not piece_values:
        return 1
    max_value = math.ceil(max(piece_values))
    total_value = math.ceil(sum(piece_values))
    turn = max(1, max_value)
    while turn * (turn + 1) // 2 < total_value:
        turn += 1
    return turn
