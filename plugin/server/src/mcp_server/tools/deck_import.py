"""Bulk Arena-export import for an existing saved deck."""

import logging
import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy.exc import DatabaseError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.database import is_database_initialized
from src.data.repositories.card import CardRepository
from src.data.repositories.deck import DeckRepository
from src.data.schemas.card import CardSummary
from src.data.schemas.deck import DeckCardEntry
from src.mcp_server.tools.deck_management import (
    MAX_CARD_QUANTITY,
    DeckCardResult,
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
    """Structured result of importing an Arena export into a saved deck."""

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


def _error_line(parsed: _ParsedArenaLine) -> DeckImportLineResult:
    """Build the ``error`` result for a valid line a database failure stopped."""
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
        status="error",
        message=f"Line {parsed.line_number}: a database error occurred.",
    )


def _line_result(parsed: _ParsedArenaLine, outcome: DeckCardResult) -> DeckImportLineResult:
    """Project an existing single-card add outcome into an import-line result."""
    if outcome.status == "card_not_found":
        status: ImportLineStatus = "not_found"
    elif outcome.status == "ok":
        status = "ok"
    elif outcome.status == "ambiguous":
        status = "ambiguous"
    elif outcome.status == "exists":
        status = "exists"
    elif outcome.status == "invalid":
        status = "invalid"
    elif outcome.status == "error":
        status = "error"
    else:
        status = "error"

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
        card_id=outcome.card_id,
        matches=outcome.matches,
        message=f"Line {parsed.line_number}: {outcome.message}",
    )


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
    itself fails nothing is added and the result is ``error``. A card named twice
    for the same board within one export is ``exists`` on its second line, just
    as it would be against a card already in the deck. Arena's optional
    ``About`` / ``Name`` metadata block is skipped. Set and collector annotations
    are reported but do not constrain name resolution because card rows
    represent aggregated oracle identities rather than every printing.

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
    results: list[DeckImportLineResult] = []
    # Rows already in the deck plus rows this import has claimed so far, keyed like the
    # association's primary key. Reproduces the per-line ``exists`` a sequential import gave.
    occupied: set[tuple[str, bool]] = {(dc.card_id, dc.sideboard) for dc in deck.deck_cards}
    pending: list[tuple[int, _ParsedArenaLine, DeckCardEntry]] = []

    for item in items:
        if isinstance(item, DeckImportLineResult):
            results.append(item)
            continue

        try:
            card, error_status, matches = await resolve_card(
                card_repo, card_id=None, name=item.name
            )
        except DatabaseError:
            logger.exception(
                "import_decklist line failed: deck_id=%s line_number=%s",
                deck_id,
                item.line_number,
            )
            results.append(_error_line(item))
            continue

        if error_status == "ambiguous":
            outcome = DeckCardResult(
                status="ambiguous",
                deck_id=deck_id,
                matches=[CardSummary.model_validate(c) for c in matches],
                message=ambiguous_message(item.name, len(matches)),
            )
        elif card is None:
            outcome = DeckCardResult(
                status="card_not_found",
                deck_id=deck_id,
                message=card_not_found_message(card_id=None, name=item.name),
            )
        elif (card.id, item.sideboard) in occupied:
            outcome = DeckCardResult(
                status="exists",
                deck_id=deck_id,
                card_id=card.id,
                message=card_exists_message(card.name, sideboard=item.sideboard),
            )
        else:
            occupied.add((card.id, item.sideboard))
            outcome = DeckCardResult(
                status="ok",
                deck_id=deck_id,
                card_id=card.id,
                message=card_added_message(card.name, item.quantity, sideboard=item.sideboard),
            )
            pending.append(
                (
                    len(results),
                    item,
                    DeckCardEntry(
                        card_id=card.id,
                        quantity=item.quantity,
                        sideboard=item.sideboard,
                        commander=item.commander,
                    ),
                )
            )
        results.append(_line_result(item, outcome))

    if pending:
        try:
            await deck_repo.add_cards_to_deck(deck_id, [entry for _, _, entry in pending])
        except IntegrityError:
            # Only reachable when another writer added one of these rows between resolution and
            # the commit: the in-memory ``occupied`` check covered everything the deck held when
            # it was loaded. The repository rolled back; nothing was added.
            logger.warning(
                "import_decklist bulk write hit a duplicate row: deck_id=%s lines=%d",
                deck_id,
                len(pending),
            )
            for index, item, _ in pending:
                results[index] = _error_line(item)
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
                "import_decklist bulk write failed: deck_id=%s lines=%d", deck_id, len(pending)
            )
            for index, item, _ in pending:
                results[index] = _error_line(item)
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

    imported_lines = len(pending)
    imported_copies = sum(item.quantity for _, item, _ in pending)
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
