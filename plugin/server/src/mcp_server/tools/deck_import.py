"""Bulk Arena-export import for an existing saved deck."""

import logging
import re
from collections.abc import Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from typing import Literal, Never, NoReturn

from pydantic import BaseModel, Field
from sqlalchemy.exc import DatabaseError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.database import is_database_initialized
from src.data.repositories.card import CardRepository
from src.data.repositories.deck import DeckRepository
from src.data.schemas.card import Card, CardSummary
from src.data.schemas.deck import MAX_CARD_QUANTITY, DeckCardEntry
from src.mcp_server.tools.deck_management import (
    ambiguous_message,
    card_added_message,
    card_exists_message,
    card_not_found_message,
    resolve_card,
)
from src.mcp_server.tools.messages import DATABASE_NOT_INITIALIZED_MESSAGE

logger = logging.getLogger(__name__)

type ArenaSection = Literal["commander", "deck", "sideboard", "companion"]
type ImportLineStatus = Literal["ok", "ambiguous", "not_found", "invalid", "exists", "error"]

_SECTION_HEADERS: dict[str, ArenaSection] = {
    "commander": "commander",
    "deck": "deck",
    "sideboard": "sideboard",
    "companion": "companion",
}
# Arena's optional metadata block: an ``About`` header followed by lines such as
# ``Name <deck name>``. Metadata lines are skipped, never imported.
_ABOUT_HEADER = "about"
_SIDEBOARD_SECTIONS: frozenset[ArenaSection] = frozenset({"sideboard", "companion"})
_MAX_EXPORT_CHARS = 50_000
_MAX_RESULT_LINES = 250
_MAX_QUANTITY = MAX_CARD_QUANTITY
_CARD_LINE_RE = re.compile(
    r"^(?P<quantity>\d+)\s+(?P<name>.+)\s+"
    r"\((?P<set_code>[^()\s]+)\)\s+(?P<collector_number>\S+)$"
)


class DeckImportLineResult(BaseModel):
    """Outcome for one nonblank, non-header Arena export line.

    ``status`` is ``ok`` (the line's copies were added), ``ambiguous`` (the name
    matched several cards — see ``matches``), ``not_found``, ``invalid`` (the line
    is malformed, its quantity is outside 1 to 250, or the lines naming its card
    for that board sum past 250), ``exists`` (the card is already in that board
    of the deck; its stored quantity is unchanged) or ``error`` (a database
    failure stopped it). Lines naming the same card for the same board — two
    Arena printings of one card, say — share one deck row: they are summed and
    answer together, and ``quantity`` stays each line's own parsed count.

    ``sideboard`` and ``commander`` are both derived from the line's section
    (``commander`` is True exactly for ``Commander``-section lines); either is
    None when no section could be determined.
    """

    line_number: int
    raw_line: str
    section: ArenaSection | None = None
    quantity: int | None = None
    name: str | None = None
    set_code: str | None = None
    collector_number: str | None = None
    sideboard: bool | None = None
    commander: bool | None = None
    status: ImportLineStatus
    card_id: str | None = None
    matches: list[CardSummary] = Field(default_factory=list)
    message: str


class DeckImportResult(BaseModel):
    """Structured result of importing an Arena export into a saved deck.

    ``status`` is ``ok`` when every line answered ``ok`` and ``partial`` when any
    did not. ``imported_lines`` counts the lines answered ``ok`` and
    ``imported_copies`` sums their quantities, so two printings of one card
    imported together count as two lines.
    """

    status: Literal[
        "ok",
        "partial",
        "invalid",
        "deck_not_found",
        "error",
        "database_not_initialized",
    ]
    deck_id: str | None = None
    results: list[DeckImportLineResult] = Field(default_factory=list)
    total_lines: int = 0
    imported_lines: int = 0
    imported_copies: int = 0
    message: str


@dataclass(frozen=True, slots=True)
class _ParsedArenaLine:
    """Parsed representation of one valid Arena card line."""

    line_number: int
    raw_line: str
    section: ArenaSection
    quantity: int
    name: str
    set_code: str
    collector_number: str

    @property
    def sideboard(self) -> bool:
        """Return whether this line belongs in the deck's sideboard."""
        return self.section in _SIDEBOARD_SECTIONS

    @property
    def commander(self) -> bool:
        """Return whether this line flags its card as the deck's commander."""
        return self.section == "commander"


def _invalid_line(
    *,
    line_number: int,
    raw_line: str,
    message: str,
    section: ArenaSection | None = None,
    quantity: int | None = None,
    name: str | None = None,
    set_code: str | None = None,
    collector_number: str | None = None,
) -> DeckImportLineResult:
    """Build an invalid per-line result while retaining parsed metadata."""
    return DeckImportLineResult(
        line_number=line_number,
        raw_line=raw_line,
        section=section,
        quantity=quantity,
        name=name,
        set_code=set_code,
        collector_number=collector_number,
        sideboard=section in _SIDEBOARD_SECTIONS if section is not None else None,
        commander=section == "commander" if section is not None else None,
        status="invalid",
        message=f"Line {line_number}: {message}",
    )


def _parse_arena_export(
    arena_export: str,
) -> tuple[list[_ParsedArenaLine | DeckImportLineResult], int]:
    """Parse an Arena export, retaining invalid card lines in source order.

    Returns:
        The ordered card-line items and the number of syntactically valid card lines.
    """
    items: list[_ParsedArenaLine | DeckImportLineResult] = []
    parsed_count = 0
    section: ArenaSection | None = None
    in_metadata = False

    for line_number, raw_line in enumerate(arena_export.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped:
            continue

        if stripped.casefold() == _ABOUT_HEADER:
            section = None
            in_metadata = True
            continue

        header = _SECTION_HEADERS.get(stripped.casefold())
        if header is not None:
            section = header
            in_metadata = False
            continue

        match = _CARD_LINE_RE.fullmatch(stripped)
        if match is None:
            # Metadata lines under ``About`` (e.g. ``Name <deck name>``) are not
            # card lines; skip them without emitting a result.
            if in_metadata:
                continue
            result_section = section
            # A non-card line may be a misspelled/unsupported section header. Fail
            # closed so following cards cannot leak into the previous location.
            if not stripped[0].isdigit():
                section = None
            items.append(
                _invalid_line(
                    line_number=line_number,
                    raw_line=raw_line,
                    section=result_section,
                    message=(
                        "expected 'QUANTITY Card Name (SET) COLLECTOR' under a "
                        "Commander, Deck, Companion, or Sideboard section."
                    ),
                )
            )
            continue

        quantity_text = match.group("quantity")
        normalized_quantity = quantity_text.lstrip("0") or "0"
        name = match.group("name").strip()
        set_code = match.group("set_code")
        collector_number = match.group("collector_number")

        if not name:
            items.append(
                _invalid_line(
                    line_number=line_number,
                    raw_line=raw_line,
                    section=section,
                    set_code=set_code,
                    collector_number=collector_number,
                    message="card name must not be empty.",
                )
            )
            continue
        if len(normalized_quantity) > len(str(_MAX_QUANTITY)):
            items.append(
                _invalid_line(
                    line_number=line_number,
                    raw_line=raw_line,
                    section=section,
                    name=name,
                    set_code=set_code,
                    collector_number=collector_number,
                    message=f"quantity must be between 1 and {_MAX_QUANTITY}.",
                )
            )
            continue

        quantity = int(normalized_quantity)

        if section is None:
            items.append(
                _invalid_line(
                    line_number=line_number,
                    raw_line=raw_line,
                    quantity=quantity,
                    name=name,
                    set_code=set_code,
                    collector_number=collector_number,
                    message=(
                        "card line appears before a Commander, Deck, Companion, "
                        "or Sideboard section."
                    ),
                )
            )
            continue
        if quantity < 1:
            items.append(
                _invalid_line(
                    line_number=line_number,
                    raw_line=raw_line,
                    section=section,
                    quantity=quantity,
                    name=name,
                    set_code=set_code,
                    collector_number=collector_number,
                    message=f"quantity must be >= 1 (got {quantity}).",
                )
            )
            continue
        if quantity > _MAX_QUANTITY:
            items.append(
                _invalid_line(
                    line_number=line_number,
                    raw_line=raw_line,
                    section=section,
                    quantity=quantity,
                    name=name,
                    set_code=set_code,
                    collector_number=collector_number,
                    message=f"quantity must be between 1 and {_MAX_QUANTITY}.",
                )
            )
            continue

        items.append(
            _ParsedArenaLine(
                line_number=line_number,
                raw_line=raw_line,
                section=section,
                quantity=quantity,
                name=name,
                set_code=set_code,
                collector_number=collector_number,
            )
        )
        parsed_count += 1

    return items, parsed_count


@dataclass(frozen=True, slots=True)
class _FoundLine:
    """A parsed line whose name resolved to one card, awaiting :func:`_sum_printings`."""

    index: int  # the line's slot in the ordered results
    parsed: _ParsedArenaLine
    card: Card


def _resolved_line(
    parsed: _ParsedArenaLine,
    *,
    status: ImportLineStatus,
    message: str,
    card_id: str | None = None,
    matches: list[CardSummary] | None = None,
) -> DeckImportLineResult:
    """Build the result for a parsed line, prefixing ``message`` with its line number."""
    return DeckImportLineResult(
        line_number=parsed.line_number,
        raw_line=parsed.raw_line,
        section=parsed.section,
        quantity=parsed.quantity,
        name=parsed.name,
        set_code=parsed.set_code,
        collector_number=parsed.collector_number,
        sideboard=parsed.sideboard,
        commander=parsed.commander,
        status=status,
        card_id=card_id,
        matches=matches or [],
        message=f"Line {parsed.line_number}: {message}",
    )


def _error_line(parsed: _ParsedArenaLine) -> DeckImportLineResult:
    """Build the ``error`` result for a valid line a database failure stopped."""
    return _resolved_line(parsed, status="error", message="a database error occurred.")


def _unhandled_status(status: Never) -> NoReturn:
    """Fail loudly on a resolver status the import does not handle (a bug, not a line outcome).

    Typed ``Never`` so mypy rejects the call unless every status above it was handled. At run time
    it raises before the import writes anything, and the MCP call answers ``isError`` naming the
    status rather than a line ``error`` that would blame the database.
    """
    raise AssertionError(
        f"import_decklist: the card resolver answered an unhandled status {status!r}; "
        "nothing was written."
    )


def _sum_printings(
    found: Sequence[_FoundLine], occupied: AbstractSet[tuple[str, bool]]
) -> tuple[dict[int, DeckImportLineResult], list[DeckCardEntry]]:
    """Lines of one export naming the same (card_id, sideboard) are one row: sum, cap, write.

    Card rows are oracle identities, so two Arena printings of one card (``2 Island (ELD) 250`` and
    ``2 Island (THB) 251``) resolve to the same row. The found lines are grouped by the
    association's primary key ``(card_id, sideboard)`` in first-seen order, and each group is
    decided whole:

    - The deck already holds that row (``occupied``): every line is ``exists`` and the stored
      quantity is left alone (the import never merges into an existing row).
    - The lines' quantities sum past ``MAX_CARD_QUANTITY``: every line is ``invalid`` and none of
      the copies is added. Adding only part of them would leave the deck short without saying so.
    - Otherwise every line is ``ok`` and the group becomes one entry of the summed quantity,
      flagged commander when any of its lines is (a ``Commander`` and a ``Deck`` line of one card
      share the mainboard row).

    Groups never span boards: the same card in ``Deck`` and ``Sideboard`` is two rows.

    Args:
        found: The lines whose names resolved to one card, in source order.
        occupied: The ``(card_id, sideboard)`` rows the deck held when it was loaded.

    Returns:
        Each found line's result keyed by its ``index``, and the entries for the one bulk write.
    """
    groups: dict[tuple[str, bool], list[_FoundLine]] = {}
    for line in found:
        groups.setdefault((line.card.id, line.parsed.sideboard), []).append(line)

    results: dict[int, DeckImportLineResult] = {}
    entries: list[DeckCardEntry] = []
    for (card_id, sideboard), lines in groups.items():
        card_name = lines[0].card.name
        total = sum(line.parsed.quantity for line in lines)
        line_numbers = ", ".join(str(line.parsed.line_number) for line in lines)

        if (card_id, sideboard) in occupied:
            message = card_exists_message(card_name, sideboard=sideboard)
            for line in lines:
                results[line.index] = _resolved_line(
                    line.parsed, status="exists", card_id=card_id, message=message
                )
            continue

        if total > MAX_CARD_QUANTITY:
            board = "sideboard" if sideboard else "mainboard"
            message = (
                f"'{card_name}' totals {total} copies in the {board} across lines {line_numbers}, "
                f"more than the {MAX_CARD_QUANTITY} one card can have; none of them were added."
            )
            for line in lines:
                results[line.index] = _resolved_line(
                    line.parsed, status="invalid", card_id=card_id, message=message
                )
            continue

        for line in lines:
            message = card_added_message(card_name, line.parsed.quantity, sideboard=sideboard)
            if len(lines) > 1:
                message = (
                    f"{message.removesuffix('.')} "
                    f"({total} copies in all from lines {line_numbers})."
                )
            results[line.index] = _resolved_line(
                line.parsed, status="ok", card_id=card_id, message=message
            )
        entries.append(
            DeckCardEntry(
                card_id=card_id,
                quantity=total,
                sideboard=sideboard,
                commander=any(line.parsed.commander for line in lines),
            )
        )
    return results, entries


async def import_decklist(
    session: AsyncSession, *, deck_id: str, arena_export: str
) -> DeckImportResult:
    """Import an Arena export into an existing saved deck.

    The import is additive: ``Commander`` and ``Deck`` cards go to the mainboard
    (``Commander`` cards additionally flagged as the deck's commanders), and
    ``Sideboard`` and ``Companion`` cards go to the sideboard. Every line is
    resolved first, then all resolvable lines are written in **one transaction**:
    a line that fails to resolve (unknown, ambiguous, malformed, or already in
    that board) is reported and never blocks the others, but if the single write
    itself fails nothing is added and the result is ``error``. Set and collector
    annotations are reported but do not constrain name resolution because card
    rows represent aggregated oracle identities rather than every printing, so
    lines naming the same card for the same board (two Arena printings of one
    card, or a card under both ``Commander`` and ``Deck``) are summed into one
    row (:func:`_sum_printings`): all of them ``ok``, or all ``invalid`` when the
    sum passes 250 copies. ``exists`` means the card was already in that board of
    the deck before the import; its stored quantity is left alone. Arena's
    optional ``About`` / ``Name`` metadata block is skipped. A resolver status
    the import does not handle raises before anything is written.

    Args:
        session: Async database session.
        deck_id: Existing saved deck id.
        arena_export: Arena-format export text.

    Returns:
        A top-level status and one ordered result per nonblank, non-header line.
    """
    deck_id = deck_id.strip()
    if not deck_id:
        return DeckImportResult(status="invalid", message="deck_id must not be empty.")
    if not arena_export or not arena_export.strip():
        return DeckImportResult(
            status="invalid", deck_id=deck_id, message="arena_export must not be empty."
        )
    if len(arena_export) > _MAX_EXPORT_CHARS:
        return DeckImportResult(
            status="invalid",
            deck_id=deck_id,
            message=f"arena_export must not exceed {_MAX_EXPORT_CHARS} characters.",
        )

    result_line_count = sum(
        1
        for raw_line in arena_export.splitlines()
        if raw_line.strip()
        and raw_line.strip().casefold() not in _SECTION_HEADERS
        and raw_line.strip().casefold() != _ABOUT_HEADER
    )
    if result_line_count > _MAX_RESULT_LINES:
        return DeckImportResult(
            status="invalid",
            deck_id=deck_id,
            message=f"arena_export must not contain more than {_MAX_RESULT_LINES} card lines.",
        )

    items, parsed_count = _parse_arena_export(arena_export)
    if parsed_count == 0:
        invalid_results = [item for item in items if isinstance(item, DeckImportLineResult)]
        return DeckImportResult(
            status="invalid",
            deck_id=deck_id,
            results=invalid_results,
            total_lines=len(invalid_results),
            message="The export contains no parseable Arena card lines.",
        )

    try:
        initialized = await is_database_initialized(session)
    except DatabaseError:
        logger.exception("import_decklist database initialization check failed")
        return DeckImportResult(
            status="error",
            deck_id=deck_id,
            message="A database error occurred checking the card database.",
        )
    if not initialized:
        return DeckImportResult(
            status="database_not_initialized",
            deck_id=deck_id,
            message=DATABASE_NOT_INITIALIZED_MESSAGE,
        )

    deck_repo = DeckRepository(session)
    try:
        # One deck load, with its rows: the in-memory ``exists`` check below needs them.
        deck = await deck_repo.get_deck_with_cards(deck_id)
    except DatabaseError:
        logger.exception("import_decklist failed to load deck_id=%s", deck_id)
        return DeckImportResult(
            status="error",
            deck_id=deck_id,
            message="A database error occurred loading the target deck.",
        )
    if deck is None:
        return DeckImportResult(
            status="deck_not_found",
            deck_id=deck_id,
            message=f"No deck found with id '{deck_id}'.",
        )

    card_repo = CardRepository(session)
    # Pass 1: resolve every line. Unparseable, ambiguous, unknown and failed lines are decided
    # here; a line that resolved to one card leaves its slot empty for pass 2.
    slots: list[DeckImportLineResult | None] = []
    found: list[_FoundLine] = []

    for item in items:
        if isinstance(item, DeckImportLineResult):
            slots.append(item)
            continue

        try:
            resolution = await resolve_card(card_repo, card_id=None, name=item.name)
        except DatabaseError:
            logger.exception(
                "import_decklist line failed: deck_id=%s line_number=%s",
                deck_id,
                item.line_number,
            )
            slots.append(_error_line(item))
            continue

        resolved = resolution.status
        match resolved:
            case "found":
                assert resolution.card is not None  # ``found`` means ``card`` is set
                found.append(_FoundLine(index=len(slots), parsed=item, card=resolution.card))
                slots.append(None)
            case "ambiguous":
                slots.append(
                    _resolved_line(
                        item,
                        status="ambiguous",
                        matches=[CardSummary.model_validate(c) for c in resolution.matches],
                        message=ambiguous_message(item.name, resolution),
                    )
                )
            case "not_found":
                slots.append(
                    _resolved_line(
                        item,
                        status="not_found",
                        message=card_not_found_message(card_id=None, name=item.name),
                    )
                )
            case _:
                _unhandled_status(resolved)

    # Pass 2: sum the found lines per deck row against the rows the deck already holds.
    occupied = frozenset((dc.card_id, dc.sideboard) for dc in deck.deck_cards)
    summed, entries = _sum_printings(found, occupied)
    results = [slot if slot is not None else summed[index] for index, slot in enumerate(slots)]
    ok_lines = [line for line in found if results[line.index].status == "ok"]

    if entries:
        try:
            await deck_repo.add_cards_to_deck(deck_id, entries)
        except IntegrityError:
            # Only reachable when another writer added one of these rows between resolution and
            # the commit: the in-memory ``occupied`` check covered everything the deck held when
            # it was loaded. The repository rolled back; nothing was added.
            logger.warning(
                "import_decklist bulk write hit a duplicate row: deck_id=%s lines=%d",
                deck_id,
                len(ok_lines),
            )
            for line in ok_lines:
                results[line.index] = _error_line(line.parsed)
            return DeckImportResult(
                status="error",
                deck_id=deck_id,
                results=results,
                total_lines=len(results),
                message=(
                    f"The deck '{deck.name}' changed while importing; nothing was added — "
                    "re-run the import."
                ),
            )
        except DatabaseError:
            # The repository rolled the session back; nothing was added.
            logger.exception(
                "import_decklist bulk write failed: deck_id=%s lines=%d", deck_id, len(ok_lines)
            )
            for line in ok_lines:
                results[line.index] = _error_line(line.parsed)
            return DeckImportResult(
                status="error",
                deck_id=deck_id,
                results=results,
                total_lines=len(results),
                message=(
                    f"A database error occurred writing the imported cards to deck "
                    f"'{deck.name}'; nothing was added."
                ),
            )

    imported_lines = len(ok_lines)
    imported_copies = sum(line.parsed.quantity for line in ok_lines)
    status: Literal["ok", "partial"] = (
        "ok" if results and all(result.status == "ok" for result in results) else "partial"
    )
    return DeckImportResult(
        status=status,
        deck_id=deck_id,
        results=results,
        total_lines=len(results),
        imported_lines=imported_lines,
        imported_copies=imported_copies,
        message=(
            f"Imported {imported_lines} of {len(results)} card line(s) "
            f"({imported_copies} total copies) into deck '{deck.name}'."
        ),
    )
