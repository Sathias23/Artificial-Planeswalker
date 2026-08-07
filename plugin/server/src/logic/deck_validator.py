"""Deck construction rule validation for Magic: The Gathering constructed formats.

This module provides business logic for validating deck construction rules:
- Maximum 4 copies of any card (except basic lands - unlimited); singleton
  formats (brawl, commander, ...) get a 1-copy limit instead
- Format legality checking, with banned cards reported separately from cards
  that are merely not in the format
- Clear error messages for rule violations

It also holds the **row projection** both shells render from (:func:`format_check`,
story c3-3): ``validate_deck`` reports only what is *wrong*, while a panel needs a
row per check including the ones that passed. The projection lives here rather than
in a shell so there is one implementation of it (AD-1) — the same reasoning that
moved c3-1's deck-count projection down into ``src/data/schemas``.

All functions are pure business logic with no database or UI dependencies.
"""

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

from src.data.schemas.card import Card
from src.data.schemas.deck import Deck


@dataclass
class ValidationResult:
    """Result of a deck construction validation operation.

    Attributes:
        is_valid: True if validation passed, False otherwise
        error_message: Human-readable error message if validation failed, None otherwise
    """

    is_valid: bool
    error_message: str | None


def is_basic_land(card: Card) -> bool:
    """Determine whether a card is a basic land.

    Basic lands are exempt from the 4-copy limit and can have unlimited copies in a deck.

    Args:
        card: The card to check

    Returns:
        True if the card's type_line contains "Basic Land" (case-insensitive), False otherwise

    Examples:
        >>> card = Card(type_line="Basic Land — Mountain", ...)
        >>> is_basic_land(card)
        True

        >>> card = Card(type_line="Land — Mountain", ...)  # Shock land, not basic
        >>> is_basic_land(card)
        False

        >>> card = Card(type_line="Creature — Goblin Warrior", ...)
        >>> is_basic_land(card)
        False
    """
    return "basic land" in card.type_line.lower()


def get_current_card_count(deck: Deck, card_id: str) -> int:
    """Calculate how many copies of a specific card are currently in a deck's mainboard.

    Only counts mainboard cards (sideboard is excluded).

    Args:
        deck: The deck to check
        card_id: The card ID to count

    Returns:
        Total quantity of the specified card in the deck's mainboard

    Examples:
        >>> deck = Deck(deck_cards=[
        ...     DeckCard(card_id="shock-id", quantity=3, sideboard=False),
        ...     DeckCard(card_id="negate-id", quantity=2, sideboard=False),
        ...     DeckCard(card_id="shock-id", quantity=1, sideboard=True),  # Sideboard excluded
        ... ])
        >>> get_current_card_count(deck, "shock-id")
        3
    """
    return sum(dc.quantity for dc in deck.deck_cards if dc.card_id == card_id and not dc.sideboard)


def validate_card_addition(deck: Deck, card: Card, quantity: int) -> ValidationResult:
    """Validate whether adding a specified quantity of a card complies with deck construction rules.

    Validates:
    - Maximum 4 copies of any non-basic land card
    - Basic lands (unlimited copies allowed)

    Args:
        deck: The deck to add cards to
        card: The card to add
        quantity: The number of copies to add

    Returns:
        ValidationResult with is_valid=True if addition is allowed, or is_valid=False with an
        error message explaining the rule violation

    Examples:
        >>> # Valid addition under 4-copy limit
        >>> deck = Deck(deck_cards=[DeckCard(card_id="bolt-id", quantity=2, sideboard=False)])
        >>> card = Card(id="bolt-id", name="Lightning Bolt", type_line="Instant", ...)
        >>> result = validate_card_addition(deck, card, 2)
        >>> result.is_valid
        True

        >>> # Invalid: exceeds 4-copy limit
        >>> deck = Deck(deck_cards=[DeckCard(card_id="bolt-id", quantity=3, sideboard=False)])
        >>> result = validate_card_addition(deck, card, 2)
        >>> result.is_valid
        False
        >>> result.error_message
        "Cannot add 2 copies of 'Lightning Bolt'. Deck would have 5 copies
        (max 4 for non-basic lands)."

        >>> # Valid: basic lands are unlimited
        >>> deck = Deck(deck_cards=[DeckCard(card_id="mountain-id", quantity=20, sideboard=False)])
        >>> card = Card(id="mountain-id", name="Mountain", type_line="Basic Land — Mountain", ...)
        >>> result = validate_card_addition(deck, card, 10)
        >>> result.is_valid
        True
    """
    # Basic lands are exempt from the 4-copy limit
    if is_basic_land(card):
        return ValidationResult(is_valid=True, error_message=None)

    # Get current count in mainboard
    current_count = get_current_card_count(deck, card.id)

    # Check if adding would exceed 4-copy limit
    total_after_addition = current_count + quantity
    max_copies = 4

    if total_after_addition > max_copies:
        if current_count >= max_copies:
            # Already at limit
            error = (
                f"Cannot add {quantity} {'copy' if quantity == 1 else 'copies'} "
                f"of '{card.name}'. Deck already has {current_count} copies "
                f"(max {max_copies} for non-basic lands)."
            )
        else:
            # Would exceed limit
            error = (
                f"Cannot add {quantity} {'copy' if quantity == 1 else 'copies'} "
                f"of '{card.name}'. Deck would have {total_after_addition} copies "
                f"(max {max_copies} for non-basic lands)."
            )
        return ValidationResult(is_valid=False, error_message=error)

    return ValidationResult(is_valid=True, error_message=None)


# --- Whole-deck validation (Story 1.6, additive) ---

# Constructed-format (Standard) construction limits — Phase-1 scope (D-1.6b).
# The size limits apply regardless of the ``format`` string; the per-card
# legality check and the copy limit are format-aware (singleton formats get a
# 1-copy limit). Commander/Brawl 100-card minima remain out of scope (a
# documented limitation).
#
# Restated at c3-3, because that story changed WHO READS IT. Until then this
# limitation was reported to an agent, which could caveat it; c3-3 puts the size
# check on a panel a person looks at.
#
# ⚠️ CORRECTED AT c4-10, AND THE PREVIOUS VERSION OF THIS COMMENT WAS BACKWARDS.
# It read: "Brawl and standardbrawl are genuinely 60, so the 20 brawl-family
# decks in the real deck table are correct and only Commander is affected —
# measured, not assumed." Every clause of that is wrong except the last four
# words, and c4-10 is the story that put the sentence in front of a person.
#
# What is actually true, measured read-only against the shipped database by
# driving the real ASGI app (c4-10 Task 0):
#
#   * This repo's OWN SHIPPED SKILL says Brawl (Historic) is 100 EXACT and
#     Standard Brawl is 60 — plugin/skills/format-legality/SKILL.md:76-78. The
#     two are different formats and the old comment conflated them under
#     "brawl-family".
#   * The database agrees with the skill. All 18 `brawl` decks have a mainboard
#     of exactly 100 (min 100 / max 100). There are 2 `standardbrawl` decks,
#     genuinely 60.
#   * There are 0 commander decks, so the named at-risk population is EMPTY,
#     while the actually-affected one is the largest single format in the table:
#     18 of 40 decks, 45%, each shown "the minimum is 60" for an exact-100
#     format.
#
# No verdict changes today, because all 18 sit at exactly 100 — the defect is in
# the SENTENCE, not the badge. A 61-card Brawl deck would be told `pass`, and a
# 99-card one would be told the minimum is 60.
#
# STILL deliberately NOT fixed here (c4-10 Q13): a per-format minimum is a rule
# change in this module with MCP blast radius (`validate_deck` serves the agent
# tools too), and it needs its own vocabulary decision for EXACT-vs-MINIMUM
# formats before a sentence can be written for either. Ledgered in
# deferred-work.md with all four numbers and a named home.
_MIN_MAINBOARD = 60
_MAX_SIDEBOARD = 15
_MAX_COPIES = 4

#: Formats whose copy limit is 1 (basics exempt). Matched against the lowercase
#: Scryfall legality key (``validate_deck`` lowercases ``format`` defensively).
_SINGLETON_FORMATS = frozenset(
    {
        "brawl",
        "commander",
        "competitivebrawl",
        "duel",
        "gladiator",
        "oathbreaker",
        "paupercommander",
        "predh",
        "standardbrawl",
    }
)

#: Recognized Scryfall legality keys (the format names ``validate_deck`` can
#: meaningfully check). Mirrors the keys present in every card's ``legalities``
#: dict; a superset of ``_SINGLETON_FORMATS``. An unrecognized format is
#: reported as an ``unknown_format`` violation rather than silently flagging
#: every card illegal (``legalities.get("potato")`` → ``None`` for all cards).
_KNOWN_FORMATS = frozenset(
    {
        "alchemy",
        "brawl",
        "commander",
        "competitivebrawl",
        "duel",
        "future",
        "gladiator",
        "historic",
        "legacy",
        "modern",
        "oathbreaker",
        "oldschool",
        "pauper",
        "paupercommander",
        "penny",
        "pioneer",
        "predh",
        "premodern",
        "standard",
        "standardbrawl",
        "timeless",
        "tlr",
        "vintage",
    }
)


DeckViolationRule = Literal[
    "min_deck_size",
    "max_sideboard_size",
    "copy_limit",
    "singleton",
    "format_legality",
    "banned_card",
    "game_availability",
    "unknown_format",
]
"""The closed vocabulary of construction rules ``validate_deck`` can report.

A named alias rather than an inline ``Literal`` so :data:`CHECK_FOR_RULE` can be pinned against
its members: a rule added here without a row assignment fails
``test_format_check.py::TestRuleCoverage`` by name, instead of silently vanishing from the panel.

``banned_card`` is c3-3's addition (Q2, Brad 2026-07-31). Before it, a banned card and a card
simply not printed into the format were one ``format_legality`` violation, which UX-DR21 lists as
two separate checks. ``restricted`` is deliberately **not** a member: a restricted card is legal
with a 1-copy limit, which this validator does not model, so it keeps reporting as
``format_legality`` exactly as it did before the split.
"""


class DeckViolation(BaseModel):
    """A single deck-construction rule violation.

    Attributes:
        rule: The construction rule that was broken.
        card_name: The offending card's name when the violation is card-specific
            (``copy_limit`` / ``singleton`` / ``format_legality`` / ``banned_card`` /
            ``game_availability``); ``None`` for whole-deck rules
            (``min_deck_size`` / ``max_sideboard_size`` / ``unknown_format``).
        detail: Human-readable explanation of the violation.
    """

    rule: DeckViolationRule
    card_name: str | None = None
    detail: str


class DeckValidationReport(BaseModel):
    """Whole-deck construction-legality report.

    ``is_legal`` is ``True`` if and only if ``violations`` is empty.

    Attributes:
        is_legal: Whether the deck passed every checked rule.
        format: The format the deck was validated against.
        mainboard_count: Total mainboard cards (summed by quantity).
        sideboard_count: Total sideboard cards (summed by quantity).
        violations: Every rule violation found (empty when ``is_legal`` is True).
    """

    is_legal: bool
    format: str
    mainboard_count: int
    sideboard_count: int
    violations: list[DeckViolation] = []


def validate_deck(
    deck: Deck, *, format: str = "standard", games: list[str] | None = None
) -> DeckValidationReport:
    """Validate a deck against constructed deck-construction rules.

    Pure business logic (no database or UI). Checks:

    - **Mainboard size:** at least 60 cards (``min_deck_size``).
    - **Sideboard size:** at most 15 cards (``max_sideboard_size``).
    - **Copy limit:** at most 4 copies of any non-basic card, counted across
      mainboard and sideboard combined; basic lands are exempt (``copy_limit``).
      In singleton formats (``_SINGLETON_FORMATS`` — brawl, standardbrawl,
      commander, gladiator, etc.) the limit is 1 instead, reported as
      ``singleton``.
    - **Format legality:** each distinct card must be ``legal`` in ``format``.
      A card whose legality is exactly ``banned`` is reported as ``banned_card``;
      anything else that is not ``legal`` — ``not_legal``, and also ``restricted``
      — is reported as ``format_legality`` (c3-3, Q2). The two are separate
      because UX-DR21 asks for them as separate checks; ``restricted`` stays with
      the plain legality rule because a restricted card is legal with a 1-copy
      limit, which this validator does not model.
    - **Game availability:** when ``games`` is provided, each distinct card must
      be available on at least one requested platform (``game_availability``).

    The 60-card / 15-sideboard limits apply regardless of ``format`` (Phase-1
    scope, D-1.6b); the per-card legality check and the copy limit are
    format-aware. Commander/Brawl 100-card minima remain out of scope, as do
    "any number of copies" exemption cards (Seven Dwarves etc.) — the singleton
    rule shares the plain copy limit's blindness there.

    Because those size limits are **not** format-aware, the ``min_deck_size``
    violation deliberately does not attribute its minimum to ``format``: it
    reports "the minimum is 60", not "commander requires at least 60", which
    would be a false statement about a format this function never consulted.
    Story c3-3 renders that sentence on a panel a person reads, which is why the
    wording was made true in every format rather than usually true.

    Args:
        deck: The deck to validate (mainboard and sideboard via ``deck_cards``).
        format: The MTG format to check legality against (default ``"standard"``).
            Lowercased and stripped defensively here (Scryfall legality keys and
            the singleton-format set are lowercase), so direct callers get the
            same behavior as the MCP tool layer.
        games: Optional platforms (``paper``/``arena``/``mtgo``) the deck must be
            playable on; ``None`` skips the availability check.

    Returns:
        A ``DeckValidationReport`` whose ``is_legal`` is ``True`` iff there are no
        violations.
    """
    # Defensive normalization: Scryfall legality keys and _SINGLETON_FORMATS are
    # lowercase, and direct library callers bypass the tool layer's lowercasing.
    format = format.strip().lower()
    mainboard_count = sum(dc.quantity for dc in deck.deck_cards if not dc.sideboard)
    sideboard_count = sum(dc.quantity for dc in deck.deck_cards if dc.sideboard)
    violations: list[DeckViolation] = []

    # Valid-key guard: an unrecognized format has no key in any card's
    # ``legalities`` dict, so the per-card legality check below would flag every
    # card illegal with no hint the format *name* was the problem. Report the bad
    # format once and skip that check; structural rules (size, copy limits) still
    # apply since they are format-independent.
    known_format = format in _KNOWN_FORMATS
    if not known_format:
        violations.append(
            DeckViolation(
                rule="unknown_format",
                detail=(
                    f"'{format}' is not a recognized format; per-card legality was not checked."
                ),
            )
        )

    if mainboard_count < _MIN_MAINBOARD:
        violations.append(
            DeckViolation(
                rule="min_deck_size",
                detail=(
                    # Deliberately does NOT attribute the minimum to `format`. It used to read
                    # "{format} requires at least 60", which is false for Commander — the limit
                    # is applied regardless of format (D-1.6b) — and rendered a gap when there
                    # was no format at all. c3-3 puts this sentence in front of a person for the
                    # first time, so it was made true in every format rather than usually true.
                    f"Mainboard has {mainboard_count} cards; the minimum is {_MIN_MAINBOARD}."
                ),
            )
        )
    if sideboard_count > _MAX_SIDEBOARD:
        violations.append(
            DeckViolation(
                rule="max_sideboard_size",
                detail=f"Sideboard has {sideboard_count} cards; the maximum is {_MAX_SIDEBOARD}.",
            )
        )

    # Tally each distinct card once: combined copies (both boards) for the copy
    # limit, plus the card itself for the per-distinct-card legality/availability
    # checks. Insertion order follows first appearance, keeping output deterministic.
    combined_counts: dict[str, int] = {}
    card_by_id: dict[str, Card] = {}
    for dc in deck.deck_cards:
        if dc.card is None:
            continue
        combined_counts[dc.card_id] = combined_counts.get(dc.card_id, 0) + dc.quantity
        card_by_id[dc.card_id] = dc.card

    # Copy limit — combined across both boards, basic lands exempt. Singleton
    # formats cap non-basics at 1 copy (rule="singleton"); everything else at 4.
    singleton = format in _SINGLETON_FORMATS
    max_copies = 1 if singleton else _MAX_COPIES
    for card_id, total in combined_counts.items():
        card = card_by_id[card_id]
        if is_basic_land(card) or total <= max_copies:
            continue
        if singleton:
            violations.append(
                DeckViolation(
                    rule="singleton",
                    card_name=card.name,
                    detail=(
                        f"{total} copies of '{card.name}'; {format} is a singleton format "
                        f"(max 1 copy of any non-basic card)."
                    ),
                )
            )
        else:
            violations.append(
                DeckViolation(
                    rule="copy_limit",
                    card_name=card.name,
                    detail=(
                        f"{total} copies of '{card.name}' (max {_MAX_COPIES} for non-basic cards)."
                    ),
                )
            )

    # Per-distinct-card format legality + optional game availability.
    for card in card_by_id.values():
        # Read the value once and branch on it. Scryfall's legality vocabulary is four values
        # (measured over the shipped corpus: not_legal 516,401 / legal 362,238 / banned 1,275 /
        # restricted 89) and only `banned` splits off here. Note what this deliberately does NOT
        # do: `restricted` falls through to the same branch it always did, so the split changes
        # no verdict for a restricted card (c3-3, Q2 — ledgered, not fixed).
        if known_format:
            legality = card.legalities.get(format)
            if legality == "banned":
                violations.append(
                    DeckViolation(
                        rule="banned_card",
                        card_name=card.name,
                        detail=f"'{card.name}' is banned in {format}.",
                    )
                )
            elif legality != "legal":
                violations.append(
                    DeckViolation(
                        rule="format_legality",
                        card_name=card.name,
                        detail=f"'{card.name}' is not legal in {format}.",
                    )
                )
        if games and not (set(card.games) & set(games)):
            violations.append(
                DeckViolation(
                    rule="game_availability",
                    card_name=card.name,
                    detail=f"'{card.name}' is not available on {', '.join(games)}.",
                )
            )

    return DeckValidationReport(
        is_legal=not violations,
        format=format,
        mainboard_count=mainboard_count,
        sideboard_count=sideboard_count,
        violations=violations,
    )


# --- The row projection (Story c3-3) ---

FormatCheckStatus = Literal["pass", "advisory", "violation"]
"""How one check came out. Exactly three outcomes, and no fourth.

``pass`` — the check ran and the deck satisfies it. ``violation`` — the check ran and the deck
breaks it. ``advisory`` — the check could **not** be answered from local data, so neither verdict
would be honest. Domain vocabulary, not presentation: mapping these onto a visual tone is the
consuming shell's job, not this module's.
"""

FormatCheckName = Literal["legality", "size", "copy_limit", "sideboard", "banned", "rotation"]
"""The checks a format-check report covers, one row each."""

CHECK_ORDER: tuple[FormatCheckName, ...] = (
    "legality",
    "size",
    "copy_limit",
    "sideboard",
    "banned",
    "rotation",
)
"""The order rows are emitted in, declared rather than left to a dict's insertion accident.

The sequence is UX-DR21's own listing, so a reader can lay this beside the artefact and see they
agree. A consumer renders a stable panel because of this constant; reordering it reorders every
panel, which is why it is a named constant with a test on it rather than a literal inside a loop.
"""

CHECK_FOR_RULE: dict[DeckViolationRule, FormatCheckName | None] = {
    "min_deck_size": "size",
    "max_sideboard_size": "sideboard",
    "copy_limit": "copy_limit",
    "singleton": "copy_limit",
    "format_legality": "legality",
    "banned_card": "banned",
    # Not a row: UX-DR21 names six checks and platform availability is not one of them. It can
    # only be produced by passing `games` to validate_deck, which format_check never does — the
    # mapping is here so the coverage pin below is total rather than selective.
    "game_availability": None,
    # Not a row either, and for a different reason: an unrecognised format does not BREAK the
    # legality check, it makes it unanswerable. It is handled as the advisory branch of the
    # legality and banned rows rather than as a violation of anything.
    "unknown_format": None,
}
"""Which validator rule feeds which row, for **every** member of :data:`DeckViolationRule`.

Total by construction and pinned that way: ``test_format_check.py`` asserts the key set equals
the ``Literal``'s members, so a rule added to the vocabulary without a decision here fails by
name. ``None`` is a decision — *this rule is deliberately not shown* — not an omission.

Note that ``rotation`` appears in no value: nothing in this database can produce it. See
:func:`format_check`.
"""


class FormatCheckRow(BaseModel):
    """One check in a deck's format report: what was checked, how it came out, and why.

    ``status`` is one of ``pass``, ``advisory`` or ``violation``. ``advisory`` means the check
    could not be answered rather than that the deck failed it — an unrecognised format, or a
    check with no local data behind it — so it should never be presented as a fault in the deck.
    A row is present for every check whether or not anything is wrong, so a panel can render a
    complete list rather than only bad news.

    Attributes:
        check: Which of the six checks this row reports.
        status: The outcome.
        detail: A human-readable sentence explaining the outcome. When several cards break the
            same check, this names the first and counts the rest.
    """

    check: FormatCheckName
    status: FormatCheckStatus
    detail: str


class FormatCheckReport(BaseModel):
    """A deck's construction legality, as one row per check rather than a list of faults.

    The same shape whatever the answer: a deck whose format cannot be checked gets this report
    with its unanswerable rows marked advisory, never a different body and never an error. Rows
    arrive in a fixed order, so a rendered panel does not reshuffle between refetches.

    Warning:
        ``is_legal`` is **not** a summary of the rows, and rendering it as the panel's headline
        will contradict them. When ``format_recognized`` is ``false`` there is nothing to check
        legality against, which the underlying validator counts as a broken rule — so
        ``is_legal`` is ``false`` while **every row is a pass or an advisory and not one is a
        violation**. Read ``is_legal`` as *"certified legal"*, not as *"something is wrong"*:
        it answers false both for a deck that breaks a rule and for a deck that could not be
        checked. To show a fault, look for a row whose ``status`` is ``violation``; to show
        "cannot be checked", branch on ``format_recognized``.

    Attributes:
        is_legal: Whether the deck was certified legal — no violation **and** nothing that
            prevented checking. Deliberately identical to the underlying validator's verdict, so
            the panel and the agent cannot disagree. See the warning above before rendering it.
        format: The format the deck was checked against, lowercased and stripped — which may
            differ in case from the format stored on the deck. Empty when the deck has none.
        format_recognized: Whether ``format`` is a format this project knows how to check.
            ``False`` means there was nothing to check legality against, which is why the
            legality and banned rows are advisory rather than passing.
        mainboard_count: Total mainboard cards, summed by quantity.
        sideboard_count: Total sideboard cards, summed by quantity.
        rows: One row per check, in a fixed order.
    """

    is_legal: bool
    format: str
    format_recognized: bool
    mainboard_count: int
    sideboard_count: int
    rows: list[FormatCheckRow]


_ROTATION_DETAIL = (
    "Rotation exposure cannot be checked: the local card data carries no set release dates."
)
"""Why the rotation row is permanently advisory (c3-3, Q3).

Measured on the shipped database rather than assumed: ``cards`` has 23 columns and none of them
is a release date, there is no sets table, and the importer reads ``released_at`` only to pick a
canonical printing before discarding it. Answering rotation properly needs a schema change, an
importer change, a migration, a full re-import **and** a rotation-schedule source Scryfall's bulk
data does not provide — which is its own story, ledgered in ``deferred-work.md``. Until then the
honest answer is that this cannot be determined, which is what ``advisory`` is for.
"""


def _summarise(violations: list[DeckViolation]) -> str:
    """Render *violations* as one sentence for a single row.

    The headlined violation is chosen by **sorting on card name**, not by taking the first as
    produced. Production order follows ``deck.deck_cards``, whose own schema documents that order
    as not meaningful — effectively Scryfall UUID order — so "the first offender" would have named
    an arbitrary card that no reader could predict (review, 2026-08-01). Alphabetical is
    arbitrary too, but it is *stable and explicable*, and it no longer depends on how the
    relationship happened to load. Whole-deck violations carry no card name and sort first.

    Args:
        violations: The violations that landed on one check; never empty.

    Returns:
        One violation's detail, followed by a count of the rest when there are any. The panel has
        one row per check, so N faults have to become one sentence somewhere; doing it here keeps
        the prose beside the rules rather than in a shell.
    """
    ordered = sorted(violations, key=lambda v: (v.card_name is not None, v.card_name or ""))
    remaining = len(ordered) - 1
    return ordered[0].detail if remaining == 0 else f"{ordered[0].detail} (+{remaining} more)"


def _unanswerable(format: str, subject: str) -> str:
    """Explain that *subject* could not be checked because *format* is not a usable format.

    Args:
        format: The normalised format string, possibly empty.
        subject: What could not be checked, as a noun phrase.

    Returns:
        A sentence naming the format when there is one to name. An empty format gets prose
        rather than a quoted empty string, which is true but reads as a bug. The empty-format
        wording blames no one: the format can be absent because the deck has none *or* because a
        caller passed a blank one, and this function cannot tell which (review, 2026-08-01).
    """
    if not format:
        return f"There is no format to check against, so {subject} could not be checked."
    return f"'{format}' is not a recognized format, so {subject} could not be checked."


def format_check(deck: Deck) -> FormatCheckReport:
    """Project a deck's validation onto one row per check, passes included.

    ``validate_deck`` answers "what is wrong with this deck", which is what an agent asked a
    question needs. A panel needs the other half too: a row for every check, so a reader can see
    that the copy limit was examined and satisfied rather than inferring it from silence. This
    reshapes the former into the latter and reimplements no rule doing it — every verdict below
    comes from a violation the validator produced, or from its absence.

    Five of the six checks are answerable. **Rotation is not**, at any cost short of a schema
    change, so its row is permanently advisory; see ``_ROTATION_DETAIL``. An unrecognised or
    missing format makes two more rows advisory rather than failing them, because a format that
    cannot be checked is not the same as a deck that breaks the rules.

    Args:
        deck: The deck to check. It must have been loaded with its cards eagerly attached
            (``DeckRepository.get_deck_with_cards``) — a deck whose ``deck_cards`` were never
            loaded reads as empty and produces a confident report about a 0-card deck.

    Returns:
        A ``FormatCheckReport`` carrying one row per check, in ``CHECK_ORDER``.
    """
    # The format is always the deck's own. A what-if `format=` override existed briefly and was
    # stripped at review (2026-08-01): the route never passed it, and `validate_deck` already
    # takes an explicit format for any caller asking a what-if question.
    checked = deck.format
    report = validate_deck(deck, format=checked or "")
    normalised = report.format
    recognized = not any(v.rule == "unknown_format" for v in report.violations)

    by_check: dict[FormatCheckName, list[DeckViolation]] = {name: [] for name in CHECK_ORDER}
    for violation in report.violations:
        row = CHECK_FOR_RULE[violation.rule]
        if row is not None:
            by_check[row].append(violation)

    # THE STRUCTURAL *PASS* SENTENCES NEVER NAME A FORMAT, and that is a correctness rule rather
    # than a style choice (review, 2026-08-01). `_MIN_MAINBOARD` is applied regardless of format
    # (D-1.6b, restated above), so a sentence of the shape "{format} requires at least 60" is an
    # affirmative claim about a format the validator never consulted — and for Commander it is
    # simply false, stated on a panel a person reads. It also read as a bug when there was no
    # format at all ("Mainboard has 60 cards;  requires at least 60."), and it contradicted the
    # row above it for an unrecognised one ("'potato' is not a recognized format" / "potato
    # requires at least 60"). Stating the limit without attributing it is true in every format,
    # in all three cases, and needs no rule this module does not have. The rule is scoped to the
    # pass sentences deliberately: a singleton VIOLATION lands on the copy_limit row saying
    # "{format} is a singleton format", and there the attribution is true and was consulted.
    passed: dict[FormatCheckName, str] = {
        "legality": f"Every card is legal in {normalised}.",
        "size": (f"Mainboard has {report.mainboard_count} cards; the minimum is {_MIN_MAINBOARD}."),
        "copy_limit": "No card exceeds the copy limit; basic lands are exempt.",
        "sideboard": (
            f"Sideboard has {report.sideboard_count} cards; the maximum is {_MAX_SIDEBOARD}."
        ),
        "banned": f"No card is banned in {normalised}.",
    }
    # What each format-dependent row says when there is no format to check it against. Only these
    # two are affected. Size and sideboard are format-independent and keep answering; the copy
    # limit is format-AWARE (singleton formats cap at 1) but keeps answering too, because an
    # unrecognised format is never in `_SINGLETON_FORMATS` (a subset of `_KNOWN_FORMATS`, pinned
    # by TestFormatSetInvariant) and so falls back to the 4-copy rule.
    unanswerable: dict[FormatCheckName, str] = {
        "legality": _unanswerable(normalised, "legality"),
        "banned": _unanswerable(normalised, "banned cards"),
    }

    rows: list[FormatCheckRow] = []
    for name in CHECK_ORDER:
        if name == "rotation":
            rows.append(FormatCheckRow(check=name, status="advisory", detail=_ROTATION_DETAIL))
        # `and not by_check[name]` is defensive, and deliberately so: the advisory arm runs first,
        # so without it a violation on an unanswerable row would be silently swallowed — reported
        # as "could not be checked" while `is_legal` said False with nothing to show for it.
        # Unreachable today (validate_deck skips the per-card check when the format is unknown, so
        # no legality or banned violation can coexist with an unrecognised format), but the
        # projection was *assuming* that rather than checking it, and the assumption lives in a
        # different function (review, 2026-08-01).
        elif not recognized and name in unanswerable and not by_check[name]:
            rows.append(FormatCheckRow(check=name, status="advisory", detail=unanswerable[name]))
        elif by_check[name]:
            rows.append(
                FormatCheckRow(check=name, status="violation", detail=_summarise(by_check[name]))
            )
        else:
            rows.append(FormatCheckRow(check=name, status="pass", detail=passed[name]))

    return FormatCheckReport(
        is_legal=report.is_legal,
        format=normalised,
        format_recognized=recognized,
        mainboard_count=report.mainboard_count,
        sideboard_count=report.sideboard_count,
        rows=rows,
    )
