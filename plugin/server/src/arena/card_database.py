"""Resolve Arena's numeric ids to names and rules text from the client's local card database.

The game log names nothing: a card is a ``grpId``, an ability an ability id, a counter a small
integer. The client ships a SQLite file (``Raw_CardDatabase_*.mtga``) that maps all three to
English text, and this module reads it, read-only, one indexed lookup at a time.

Every lookup degrades to ``None`` rather than raising: the file belongs to another program, its
schema has drifted between client versions before, and a board with a few unnamed cards is still
worth showing.
"""

import logging
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_TAG = re.compile(r"<[^>]+>")
_MANA_SYMBOL = re.compile(r"o(\([^)]*\)|[^o(]+)")
_BRACED_COST = re.compile(r"\{((?:o[^o{}]+)+)\}")
_PROMPT_PARAMETER = re.compile(r"\{\d+,\s*(\w+)\}")
_INTERNAL_TEXT_PREFIXES = ("CLASSLEVEL", "#Deprecated")
_SELF_REFERENCE = "CARDNAME"


@dataclass(frozen=True)
class ArenaCard:
    """What the client's database says about one printing."""

    name: str
    mana_cost: str | None
    type_line: str | None
    power_toughness: str | None
    ability_text_ids: tuple[int, ...]


def format_mana_cost(old_school: str | None) -> str | None:
    """Convert the database's ``o2oGoG`` cost notation to ``{2}{G}{G}``.

    Args:
        old_school: The ``OldSchoolManaText`` value, where each symbol is prefixed with ``o`` and
            a hybrid symbol is parenthesised (``o(W/U)``).

    Returns:
        The braced cost, or ``None`` for a card with no mana cost (a land, a token).
    """
    if not old_school:
        return None
    symbols = [match.strip("()") for match in _MANA_SYMBOL.findall(old_school)]
    return "".join(f"{{{symbol}}}" for symbol in symbols) or None


class ArenaCardDatabase:
    """Read-only lookups against the client's card database.

    Construct with ``None`` (or a path that cannot be opened) for a database that answers ``None``
    to everything; :attr:`available` reports which one this is. Not thread-safe: build, use and
    close one on the same thread.
    """

    def __init__(self, path: Path | None) -> None:
        self._connection: sqlite3.Connection | None = None
        self._text_query: str | None = None
        self._cards: dict[int, ArenaCard | None] = {}
        self._texts: dict[int, str | None] = {}
        self._card_columns: set[str] = set()
        if path is None:
            return
        try:
            # A file URI must be absolute; a path from an environment variable need not be.
            connection = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
        except (sqlite3.Error, OSError, ValueError) as exc:
            logger.warning("Arena card database %s could not be opened: %s", path, exc)
            return
        try:
            connection.row_factory = sqlite3.Row
            self._text_query = self._find_text_query(connection)
            self._card_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(Cards)")
            }
        except sqlite3.Error as exc:
            logger.warning("Arena card database %s could not be read: %s", path, exc)
            connection.close()
            return
        if self._text_query is None or "GrpId" not in self._card_columns:
            logger.warning("Arena card database %s has an unrecognised schema", path)
            connection.close()
            return
        self._connection = connection

    @staticmethod
    def _find_text_query(connection: sqlite3.Connection) -> str | None:
        """Return the query that fetches one localized string, or ``None`` if no table fits."""
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name LIKE 'Localizations%'"
            )
        ]
        tables.sort(key=lambda name: (name != "Localizations_enUS", name))
        for table in tables:
            columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
            if not {"LocId", "Loc"} <= columns:
                continue
            # A string may be stored plain (0) and with markup (1); the lowest value is the
            # plain one when both exist.
            order = " ORDER BY Formatted" if "Formatted" in columns else ""
            return f"SELECT Loc FROM {table} WHERE LocId = ?{order} LIMIT 1"
        return None

    @property
    def available(self) -> bool:
        """Whether lookups can succeed at all."""
        return self._connection is not None

    def close(self) -> None:
        """Release the database file."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def text(self, loc_id: int | None) -> str | None:
        """Return the English string for a localization id, markup stripped."""
        if self._connection is None or self._text_query is None or not loc_id:
            return None
        if loc_id in self._texts:
            return self._texts[loc_id]
        value: str | None = None
        try:
            row = self._connection.execute(self._text_query, (loc_id,)).fetchone()
        except sqlite3.Error as exc:
            logger.debug("Arena text lookup %s failed: %s", loc_id, exc)
            row = None
        if row is not None and row[0]:
            plain = _TAG.sub("", str(row[0])).strip()
            # Rules text writes costs in the same notation as the cost column: {oT}, {o2oGoG}.
            plain = _BRACED_COST.sub(lambda m: format_mana_cost(m.group(1)) or m.group(0), plain)
            value = plain or None
        self._texts[loc_id] = value
        return value

    def card(self, grp_id: int | None) -> ArenaCard | None:
        """Return the card a ``grpId`` names, or ``None`` when the database does not know it."""
        if self._connection is None or not grp_id:
            return None
        if grp_id in self._cards:
            return self._cards[grp_id]
        card: ArenaCard | None = None
        try:
            row = self._connection.execute(
                "SELECT * FROM Cards WHERE GrpId = ?", (grp_id,)
            ).fetchone()
        except sqlite3.Error as exc:
            logger.debug("Arena card lookup %s failed: %s", grp_id, exc)
            row = None
        if row is not None:
            card = self._card_from_row(row)
        self._cards[grp_id] = card
        return card

    def _card_from_row(self, row: sqlite3.Row) -> ArenaCard | None:
        """Build an :class:`ArenaCard`, reading only the columns this database actually has."""

        def column(name: str) -> object:
            return row[name] if name in self._card_columns else None

        def loc(name: str) -> str | None:
            value = column(name)
            return self.text(value) if isinstance(value, int) else None

        name = loc("TitleId")
        if name is None:
            return None
        types = loc("TypeTextId")
        subtypes = loc("SubtypeTextId")
        type_line = f"{types} — {subtypes}" if types and subtypes else types
        power, toughness = column("Power"), column("Toughness")
        has_stats = power not in (None, "") and toughness not in (None, "")
        text_ids: list[int] = []
        for entry in str(column("AbilityIds") or "").split(","):
            # Each entry is "<ability id>:<text id>".
            _, _, text_id = entry.partition(":")
            if text_id.strip().isdigit():
                text_ids.append(int(text_id))
        return ArenaCard(
            name=name,
            mana_cost=format_mana_cost(
                str(column("OldSchoolManaText")) if column("OldSchoolManaText") else None
            ),
            type_line=type_line,
            power_toughness=f"{power}/{toughness}" if has_stats else None,
            ability_text_ids=tuple(text_ids),
        )

    def card_name(self, grp_id: int | None) -> str | None:
        """Return a card's name, or ``None`` when unknown."""
        card = self.card(grp_id)
        return card.name if card is not None else None

    def card_text(self, grp_id: int | None) -> str | None:
        """Return a one-line rules summary: cost, type line, stats and abilities.

        Returns:
            ``None`` for an unknown card; otherwise the parts the database has, joined by
            `` | ``, with the card's own name substituted for the ``CARDNAME`` placeholder.
        """
        card = self.card(grp_id)
        if card is None:
            return None
        abilities = [
            text.replace(_SELF_REFERENCE, card.name)
            for text in (self.text(text_id) for text_id in card.ability_text_ids)
            if text and not text.startswith(_INTERNAL_TEXT_PREFIXES)
        ]
        parts = [card.mana_cost, card.type_line, card.power_toughness, " / ".join(abilities)]
        return " | ".join(part for part in parts if part) or None

    def ability_text(self, ability_id: int | None, source_name: str | None = None) -> str | None:
        """Return an ability's rules text.

        Args:
            ability_id: The ability's ``grpId`` as the game log gives it.
            source_name: The card the ability belongs to, substituted for ``CARDNAME``.
        """
        if self._connection is None or not ability_id:
            return None
        try:
            row = self._connection.execute(
                "SELECT TextId FROM Abilities WHERE Id = ?", (ability_id,)
            ).fetchone()
        except sqlite3.Error as exc:
            logger.debug("Arena ability lookup %s failed: %s", ability_id, exc)
            return None
        text = self.text(row[0]) if row is not None else None
        if text and source_name:
            text = text.replace(_SELF_REFERENCE, source_name)
        return text

    def prompt_text(self, prompt_id: int | None, parameters: dict[str, str]) -> str | None:
        """Return the sentence the client shows for a decision prompt.

        Args:
            prompt_id: The prompt's id as the game log gives it.
            parameters: Values for the prompt's named placeholders (``{1, NumberOfCards}``).

        Returns:
            The prompt with its placeholders filled, or ``None`` when the database has no
            player-facing text for it or a placeholder has no value.
        """
        if self._connection is None or not prompt_id:
            return None
        try:
            row = self._connection.execute(
                "SELECT LocId FROM Prompts WHERE Id = ?", (prompt_id,)
            ).fetchone()
        except sqlite3.Error as exc:
            logger.debug("Arena prompt lookup %s failed: %s", prompt_id, exc)
            return None
        text = self.text(row[0]) if row is not None else None
        if not text or text.startswith(_INTERNAL_TEXT_PREFIXES):
            return None
        if any(name not in parameters for name in _PROMPT_PARAMETER.findall(text)):
            return None
        return _PROMPT_PARAMETER.sub(lambda m: parameters[m.group(1)], text)

    def counter_name(self, counter_type: int | None) -> str | None:
        """Return a counter kind's name (``+1/+1``, ``Loyalty``), or ``None`` when unknown."""
        if self._connection is None or counter_type is None:
            return None
        try:
            row = self._connection.execute(
                "SELECT LocId FROM Enums WHERE Type = 'CounterType' AND Value = ?",
                (counter_type,),
            ).fetchone()
        except sqlite3.Error as exc:
            logger.debug("Arena counter lookup %s failed: %s", counter_type, exc)
            return None
        return self.text(row[0]) if row is not None else None
