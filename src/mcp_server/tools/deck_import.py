"""Bulk Arena-export import for an existing saved deck."""

import logging
import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy.exc import DatabaseError
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.database import is_database_initialized
from src.data.repositories.deck import DeckRepository
from src.data.schemas.card import CardSummary
from src.mcp_server.tools.deck_management import DeckCardResult
from src.mcp_server.tools.deck_management import add_card_to_deck as _add_card_to_deck
from src.mcp_server.tools.messages import DATABASE_NOT_INITIALIZED_MESSAGE

logger = logging.getLogger(__name__)

type ArenaSection = Literal["commander", "deck", "sideboard"]
type ImportLineStatus = Literal["ok", "ambiguous", "not_found", "invalid", "exists", "error"]

_SECTION_HEADERS: dict[str, ArenaSection] = {
    "commander": "commander",
    "deck": "deck",
    "sideboard": "sideboard",
}
_MAX_EXPORT_CHARS = 50_000
_MAX_RESULT_LINES = 250
_MAX_QUANTITY = 250
_CARD_LINE_RE = re.compile(
    r"^(?P<quantity>\d+)\s+(?P<name>.+)\s+"
    r"\((?P<set_code>[^()\s]+)\)\s+(?P<collector_number>\S+)$"
)


class DeckImportLineResult(BaseModel):
    """Outcome for one nonblank, non-header Arena export line."""

    line_number: int
    raw_line: str
    section: ArenaSection | None = None
    quantity: int | None = None
    name: str | None = None
    set_code: str | None = None
    collector_number: str | None = None
    sideboard: bool | None = None
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
        return self.section == "sideboard"


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
        sideboard=section == "sideboard" if section is not None else None,
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

    for line_number, raw_line in enumerate(arena_export.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped:
            continue

        header = _SECTION_HEADERS.get(stripped.casefold())
        if header is not None:
            section = header
            continue

        match = _CARD_LINE_RE.fullmatch(stripped)
        if match is None:
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
                        "Commander, Deck, or Sideboard section."
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
                    message="card line appears before a Commander, Deck, or Sideboard section.",
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
        status=status,
        card_id=outcome.card_id,
        matches=outcome.matches,
        message=f"Line {parsed.line_number}: {outcome.message}",
    )


async def import_decklist(
    session: AsyncSession, *, deck_id: str, arena_export: str
) -> DeckImportResult:
    """Import an Arena export into an existing saved deck.

    The import is additive and line-independent: ``Commander`` and ``Deck`` cards
    go to the mainboard, ``Sideboard`` cards go to the sideboard, and successful
    lines remain committed when another line fails. Set and collector annotations
    are reported but do not constrain name resolution because card rows represent
    aggregated oracle identities rather than every printing.

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
        if raw_line.strip() and raw_line.strip().casefold() not in _SECTION_HEADERS
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

    try:
        deck = await DeckRepository(session).get_deck(deck_id)
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

    results: list[DeckImportLineResult] = []
    imported_lines = 0
    imported_copies = 0

    for item in items:
        if isinstance(item, DeckImportLineResult):
            results.append(item)
            continue

        try:
            outcome = await _add_card_to_deck(
                session,
                deck_id=deck_id,
                name=item.name,
                quantity=item.quantity,
                sideboard=item.sideboard,
            )
        except DatabaseError:
            logger.exception(
                "import_decklist line failed: deck_id=%s line_number=%s",
                deck_id,
                item.line_number,
            )
            results.append(
                DeckImportLineResult(
                    line_number=item.line_number,
                    raw_line=item.raw_line,
                    section=item.section,
                    quantity=item.quantity,
                    name=item.name,
                    set_code=item.set_code,
                    collector_number=item.collector_number,
                    sideboard=item.sideboard,
                    status="error",
                    message=f"Line {item.line_number}: a database error occurred.",
                )
            )
            continue

        result = _line_result(item, outcome)
        results.append(result)
        if result.status == "ok":
            imported_lines += 1
            imported_copies += item.quantity

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
