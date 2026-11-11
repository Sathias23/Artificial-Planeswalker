"""Card repository for database operations on card data.

Also home of the one card-name resolver every name-taking tool calls: an exact ``COLLATE NOCASE``
match on ``name`` or ``printed_name`` (served by the ``ix_cards_*_nocase`` indexes), then an
escaped substring read collapsed to one card per Oracle id, ordered by name and capped at
:data:`MAX_NAME_MATCHES` + 1 rows so the caller learns whether more matched without reading them.
The statements are built once (:func:`_exact_name_statement`, :func:`_partial_name_statement`) and
run on either seam: :meth:`CardRepository.resolve_name` on the async session, and
:func:`resolve_name_on_connection` on the sync sqlite-vec connection, which compiles the same
``Select`` objects for SQLite.
"""

import math
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy import String, cast, func, not_, or_, select
from sqlalchemy.dialects import sqlite
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from src.data.models.card import CardModel
from src.data.repositories.base import LIKE_ESCAPE, BaseRepository, contains_pattern
from src.data.schemas.card import Card
from src.data.schemas.pagination import PaginatedResult

# Type alias for supported format filters
# Common MTG formats: standard, modern, commander, legacy, vintage, pioneer, pauper
FormatFilter = str | None

# Type alias for games availability filter
# Scryfall platforms: paper, arena, mtgo
GamesFilter = list[str] | None

#: The most candidates a name resolution returns; the partial read fetches one more to learn
#: whether the list was cut (:attr:`NameResolution.more`).
MAX_NAME_MATCHES = 10

#: The SQLite dialect the sync seam compiles statements with. ``named`` so a ``%`` in a compiled
#: ``LIKE`` stays a single ``%`` (the ``pyformat`` style would double it) and parameters bind by
#: name from ``compiled.params``.
_SQLITE_NAMED = sqlite.dialect(paramstyle="named")


@dataclass(frozen=True)
class NameResolution[T]:
    """The outcome of resolving a card name: one card, several candidates, or nothing.

    ``T`` is the row shape of the seam that resolved it: a :class:`Card` on the async session, a
    positional ``sqlite3`` row on the sync connection.

    Attributes:
        card: The one card the name names (an exact match, or the only partial match).
        matches: The candidates when the name matched more than one Oracle card, in name order,
            at most :data:`MAX_NAME_MATCHES`.
        more: ``True`` when more than :data:`MAX_NAME_MATCHES` Oracle cards matched, so
            ``matches`` is the first :data:`MAX_NAME_MATCHES` of them, not all.
    """

    card: T | None = None
    matches: list[T] = field(default_factory=list)
    more: bool = False

    @property
    def status(self) -> Literal["found", "ambiguous", "not_found"]:
        """``found`` (``card`` set), ``ambiguous`` (``matches`` set) or ``not_found``."""
        if self.card is not None:
            return "found"
        if self.matches:
            return "ambiguous"
        return "not_found"


class CardRepository(BaseRepository):
    """Repository for card-related database operations.

    Provides methods for querying and manipulating card data.
    Extends BaseRepository for consistent session management.
    """

    def __init__(self, session: AsyncSession):
        """Initialize repository with database session.

        Args:
            session: AsyncSession for database operations
        """
        super().__init__(session)

    @staticmethod
    def _apply_format_filter(stmt: Select[Any], format_filter: FormatFilter) -> Select[Any]:
        """Apply format legality filter to a SELECT statement.

        Filters cards based on their legalities JSON field. Only cards with
        legalities.{format} = "legal" will be included.

        Args:
            stmt: SQLAlchemy SELECT statement to filter
            format_filter: Format to filter by ("standard" or None for no filter)

        Returns:
            Modified SELECT statement with format filter applied (if format_filter is not None)

        Example:
            stmt = select(CardModel).where(CardModel.name == "Lightning Bolt")
            stmt = CardRepository._apply_format_filter(stmt, "standard")
        """
        if format_filter is None:
            return stmt

        # SQLite stores JSON as text: json_extract(legalities, '$.standard') = 'legal'
        legality_check = func.json_extract(CardModel.legalities, f"$.{format_filter}") == "legal"
        return stmt.where(legality_check)

    @staticmethod
    def _apply_games_filter(stmt: Select[Any], games: GamesFilter) -> Select[Any]:
        """Apply games availability filter to a SELECT statement.

        Filters cards based on their games JSON array field. Uses OR logic:
        card must be available in at least one of the specified games.

        Args:
            stmt: SQLAlchemy SELECT statement to filter
            games: List of games to filter by (["paper", "arena", "mtgo"] or None for no filter)

        Returns:
            Modified SELECT statement with games filter applied (if games is not None/empty)

        Example:
            stmt = select(CardModel).where(CardModel.name == "Lightning Bolt")
            stmt = CardRepository._apply_games_filter(stmt, ["arena"])
        """
        if games is None or not games:
            return stmt

        # Card must be available in at least one specified game: a LIKE on the JSON array text,
        # escaped because ``lookup_card_by_name`` passes ``games`` through unvalidated.
        conditions = [
            cast(CardModel.games, String).like(contains_pattern(f'"{game}"'), escape=LIKE_ESCAPE)
            for game in games
        ]
        return stmt.where(or_(*conditions))

    @staticmethod
    def _apply_unique_oracle_filter(stmt: Select[Any]) -> Select[Any]:
        """Filter to one card per Oracle ID (removes duplicate printings).

        Uses a subquery to select only the first card (by ID) for each unique Oracle ID.
        This ensures users see only unique cards, not multiple printings of the same card.
        ``stmt`` must select ``cards.id`` and ``cards.oracle_id`` (the CTE reads both).

        Args:
            stmt: SQLAlchemy SELECT statement to filter

        Returns:
            Modified SELECT statement that returns only one card per Oracle ID

        Example:
            stmt = select(CardModel).where(CardModel.type_line == "Instant")
            stmt = CardRepository._apply_unique_oracle_filter(stmt)
            # Now returns only one Lightning Bolt instead of dozens of printings
        """
        # Create a CTE (Common Table Expression) from stmt to get filtered cards
        cte = stmt.cte("filtered_cards")

        # Select the minimum ID for each oracle_id from the CTE
        min_id_subquery = (
            select(func.min(cte.c.id).label("min_id")).group_by(cte.c.oracle_id)
        ).scalar_subquery()

        # Filter original statement to only include IDs that are the minimum for their oracle_id
        return stmt.where(CardModel.id.in_(min_id_subquery))

    async def get_by_id(self, card_id: str) -> Card | None:
        """Get a card by its primary-key id.

        Read-only point lookup used to confirm a card exists before associating it
        with a deck (deck tools pre-validate the card id to answer ``card_not_found``
        rather than surface the database's foreign-key rejection). No format/games
        filtering.

        Args:
            card_id: Card primary-key id (Scryfall UUID).

        Returns:
            The matching Card schema if found, None otherwise.

        Example:
            card = await repo.get_by_id("card-456")
            if card:
                print(f"Found: {card.name}")
        """
        stmt = select(CardModel).where(CardModel.id == card_id)
        result = await self.session.execute(stmt)
        card_model = result.scalar_one_or_none()

        if card_model is None:
            return None

        return Card.model_validate(card_model)

    async def resolve_name(
        self, name: str, *, format_filter: FormatFilter = None, games: GamesFilter = None
    ) -> NameResolution[Card]:
        """Resolve a card name the way every name-taking tool does.

        Strips ``name``; a blank one resolves to nothing without a query. Otherwise an exact
        case-insensitive match on ``name`` or ``printed_name`` (first printing by id) wins; failing
        that, a literal substring match on either (``%`` and ``_`` are not wildcards), one card per
        Oracle id, in name order, reading at most :data:`MAX_NAME_MATCHES` + 1 rows. One partial
        match is the card; several are ``matches``, with ``more`` saying whether the list was cut.

        Args:
            name: The exact or partial card name.
            format_filter: Optional format the card must be legal in.
            games: Optional platforms the card must be available on (any of them).

        Returns:
            A :class:`NameResolution` of :class:`Card` schemas.
        """
        name = name.strip()
        if not name:
            return NameResolution()

        exact = await self.find_by_name_exact(name, format_filter=format_filter, games=games)
        if exact is not None:
            return NameResolution(card=exact)

        stmt = _partial_name_statement((CardModel,), name, format_filter=format_filter, games=games)
        result = await self.session.execute(stmt)
        return _bucket([Card.model_validate(model) for model in result.scalars().all()])

    async def find_by_name_exact(
        self, name: str, format_filter: FormatFilter = None, games: GamesFilter = None
    ) -> Card | None:
        """Find a card by exact name match (case-insensitive).

        Performs a case-insensitive exact match on both the name and printed_name fields.
        This allows searching for both Oracle names (e.g., "Tombstone, Career Criminal")
        and printed names (e.g., "Nill, Vessel of Valgavoth" for OM1 cards).
        When multiple printings exist (same name, different sets), returns the
        first one ordered by ID. Optionally filters by format legality and game availability.

        The comparison is ``COLLATE NOCASE`` equality, so it is served by the
        ``ix_cards_*_nocase`` indexes rather than a table scan, and ``name`` is compared
        literally — ``%`` and ``_`` are not wildcards here. SQLite's ``NOCASE`` folds ASCII
        letters only (exactly like the ``lower()``/``LIKE`` path it replaced), so a non-ASCII case
        mismatch misses here and falls to the resolver's partial step.

        Args:
            name: Card name to search for (case-insensitive, matches name OR printed_name)
            format_filter: Optional format to filter by ("standard" or None)
            games: Optional list of games to filter by (["arena"] or None)

        Returns:
            Card schema if found, None otherwise (returns first printing if multiple exist)

        Example:
            card = await repo.find_by_name_exact("Lightning Bolt")
            card = await repo.find_by_name_exact("Nill, Vessel of Valgavoth")  # Finds OM1 card
            if card:
                print(f"Found: {card.name}")

            # With format filter
            card = await repo.find_by_name_exact("Lightning Bolt", format_filter="standard")

            # With games filter
            card = await repo.find_by_name_exact("Nill, Vessel of Valgavoth", games=["arena"])
        """
        stmt = _exact_name_statement((CardModel,), name, format_filter=format_filter, games=games)
        result = await self.session.execute(stmt)
        card_model = result.scalar_one_or_none()

        if card_model is None:
            return None

        return Card.model_validate(card_model)

    async def find_by_name_partial(
        self,
        query: str,
        format_filter: FormatFilter = None,
        games: GamesFilter = None,
        *,
        limit: int = MAX_NAME_MATCHES,
    ) -> list[Card]:
        """Find cards whose name or printed name contains ``query`` (case-insensitive, literal).

        One card per Oracle ID (no duplicate printings), in name order, at most ``limit`` of
        them. ``%`` and ``_`` in ``query`` match themselves. Optionally filters by format legality
        and game availability. The tools resolve names through :meth:`resolve_name`; this is the
        bare substring read for scripts.

        Args:
            query: Partial name to search for (case-insensitive, matches name OR printed_name)
            format_filter: Optional format to filter by ("standard" or None)
            games: Optional list of games to filter by (["arena"] or None)
            limit: The most cards to return (default :data:`MAX_NAME_MATCHES`).

        Returns:
            List of matching Card schemas (one per Oracle ID, empty list if no matches)

        Example:
            cards = await repo.find_by_name_partial("lightning")
            cards = await repo.find_by_name_partial("Nill")  # Finds OM1 cards with printed_name
            cards = await repo.find_by_name_partial("lightning", format_filter="standard")
            cards = await repo.find_by_name_partial("Nill", games=["arena"])
        """
        stmt = _partial_name_statement(
            (CardModel,), query, format_filter=format_filter, games=games, limit=limit
        )
        result = await self.session.execute(stmt)
        return [Card.model_validate(card) for card in result.scalars().all()]

    async def find_by_colors(
        self, color: str, format_filter: FormatFilter = None, games: GamesFilter = None
    ) -> list[Card]:
        """Find all cards containing a specific color in their colors array.

        Uses JSON operations to filter cards by color codes (W/U/B/R/G).
        Pass empty string to find colorless cards. Returns only one card per Oracle ID
        (no duplicate printings). Optionally filters by format legality and game availability.

        Args:
            color: Single color code (W/U/B/R/G) or empty string for colorless
            format_filter: Optional format to filter by ("standard" or None)
            games: Optional list of games to filter by (["arena"] or None)

        Returns:
            List of matching Card schemas (one per Oracle ID, empty list if no matches)

        Example:
            red_cards = await repo.find_by_colors("R")
            colorless = await repo.find_by_colors("")

            # With format filter
            standard_red = await repo.find_by_colors("R", format_filter="standard")

            # With games filter
            arena_red = await repo.find_by_colors("R", games=["arena"])
        """
        if color == "":
            # Find colorless cards (empty colors array)
            stmt = select(CardModel).where(CardModel.colors == [])
        else:
            # For SQLite, check if color exists in JSON array by casting to string
            # and using LIKE pattern matching

            # This checks if the color appears in the JSON array representation
            # e.g., '["R"]' or '["R", "U"]' will match when searching for "R"
            stmt = select(CardModel).where(cast(CardModel.colors, String).like(f'%"{color}"%'))

        stmt = self._apply_format_filter(stmt, format_filter)
        stmt = self._apply_games_filter(stmt, games)
        stmt = self._apply_unique_oracle_filter(stmt)
        result = await self.session.execute(stmt)
        card_models = result.scalars().all()

        return [Card.model_validate(card) for card in card_models]

    async def find_by_type(
        self, type_query: str, format_filter: FormatFilter = None, games: GamesFilter = None
    ) -> list[Card]:
        """Find all cards matching a type substring in their type_line (case-insensitive).

        Performs a case-insensitive substring search on the type_line field.
        Returns only one card per Oracle ID (no duplicate printings).
        Optionally filters by format legality and game availability.

        Args:
            type_query: Type or subtype to search for (e.g., "Instant", "Dragon")
            format_filter: Optional format to filter by ("standard" or None)
            games: Optional list of games to filter by (["arena"] or None)

        Returns:
            List of matching Card schemas (one per Oracle ID, empty list if no matches)

        Example:
            instants = await repo.find_by_type("Instant")
            dragons = await repo.find_by_type("Dragon")

            # With format filter
            standard_instants = await repo.find_by_type("Instant", format_filter="standard")

            # With games filter
            arena_instants = await repo.find_by_type("Instant", games=["arena"])
        """
        stmt = select(CardModel).where(
            CardModel.type_line.ilike(contains_pattern(type_query), escape=LIKE_ESCAPE)
        )
        stmt = self._apply_format_filter(stmt, format_filter)
        stmt = self._apply_games_filter(stmt, games)
        stmt = self._apply_unique_oracle_filter(stmt)
        result = await self.session.execute(stmt)
        card_models = result.scalars().all()

        return [Card.model_validate(card) for card in card_models]

    async def search_by_keywords(
        self, keyword: str, format_filter: FormatFilter = None, games: GamesFilter = None
    ) -> list[Card]:
        """Find all cards containing a keyword in their oracle text or keywords array.

        Performs case-insensitive search in both oracle_text and keywords JSON array.
        Useful for finding cards with specific abilities like "haste", "flying", etc.
        Returns only one card per Oracle ID (no duplicate printings).
        Optionally filters by format legality and game availability.

        Args:
            keyword: Keyword ability to search for (case-insensitive)
            format_filter: Optional format to filter by ("standard" or None)
            games: Optional list of games to filter by (["arena"] or None)

        Returns:
            List of matching Card schemas (one per Oracle ID, empty list if no matches)

        Example:
            haste_cards = await repo.search_by_keywords("haste")
            flying_cards = await repo.search_by_keywords("flying")

            # With format filter
            standard_haste = await repo.search_by_keywords("haste", format_filter="standard")

            # With games filter
            arena_haste = await repo.search_by_keywords("haste", games=["arena"])
        """

        # Search in oracle_text (case-insensitive)
        oracle_match = CardModel.oracle_text.ilike(contains_pattern(keyword), escape=LIKE_ESCAPE)

        # Search in keywords JSON array (cast to string and check for keyword)
        keywords_match = cast(CardModel.keywords, String).ilike(
            contains_pattern(f'"{keyword}"'), escape=LIKE_ESCAPE
        )

        stmt = select(CardModel).where(or_(oracle_match, keywords_match))
        stmt = self._apply_format_filter(stmt, format_filter)
        stmt = self._apply_games_filter(stmt, games)
        stmt = self._apply_unique_oracle_filter(stmt)
        result = await self.session.execute(stmt)
        card_models = result.scalars().all()

        return [Card.model_validate(card) for card in card_models]

    async def search_advanced(
        self,
        colors: list[str] | None = None,
        types: list[str] | None = None,
        keywords: list[str] | None = None,
        oracle_text_phrases: list[str] | None = None,
        mana_value_min: float | None = None,
        mana_value_max: float | None = None,
        rarity: str | list[str] | None = None,
        page: int = 1,
        page_size: int = 20,
        limit: int | None = None,
        format_filter: FormatFilter = None,
        games: GamesFilter = None,
        color_mode: Literal["any", "all", "exact", "at_most"] = "any",
    ) -> PaginatedResult[Card]:
        """Advanced card search with multiple filter criteria and pagination.

        Filters cards by any combination of colors, types, keywords, oracle text phrases,
        mana value range, and rarity. All filters are combined with AND logic (cards must
        match all specified criteria). Results are paginated. Optionally filters by format
        legality.

        Args:
            colors: List of color codes (W/U/B/R/G). How this filter is interpreted
                depends on the color_mode parameter.
            types: List of type strings to search for in type_line (e.g., ["Creature", "Dragon"])
            keywords: List of keywords to search for in oracle_text/keywords array
            oracle_text_phrases: List of text phrases to search for in oracle_text.
                ALL phrases must appear in the card's oracle text (AND logic).
                Case-insensitive substring matching.
                For example: ["target creature you control", "gains flying"]
            mana_value_min: Minimum mana value (CMC) inclusive
            mana_value_max: Maximum mana value (CMC) inclusive
            rarity: Single rarity value or list of rarity values (case-insensitive).
                Valid values: "common", "uncommon", "rare", "mythic", "special", "bonus".
                Multiple rarities use OR logic (e.g., ["rare", "mythic"] finds rare OR
                mythic cards).
            page: Page number for pagination (1-indexed, default: 1)
            page_size: Number of results per page (default: 20, max: 50)
            limit: DEPRECATED. Use page_size instead. Maintained for backward compatibility.
            format_filter: Optional format to filter by ("standard" or None)
            games: Optional list of games to filter by (["arena"] or None)
            color_mode: How to interpret the colors filter (default: "any"):
                - "any": Contains ANY of the specified colors (OR logic) - default
                  Example: ["W", "U"] → mono-white, mono-blue, white-blue, multicolor
                - "all": Contains ALL of the specified colors (AND logic)
                  Example: ["W", "U"] → white-blue, white-blue-red, etc.
                - "exact": Exactly these colors, no more, no less
                  Example: ["W", "U"] → only white-blue cards (not mono-white, not tricolor)
                - "at_most": Only these colors or fewer (color identity/subset)
                  Example: ["W", "U"] → colorless, mono-white, mono-blue, or white-blue

        Returns:
            PaginatedResult containing matching Card schemas with pagination metadata

        Example:
            # Find red creatures with haste under 4 mana
            result = await repo.search_advanced(
                colors=["R"],
                types=["Creature"],
                keywords=["haste"],
                mana_value_max=3,
                page=1,
                page_size=20
            )

            # Find Azorius (white-blue) cards exactly
            result = await repo.search_advanced(
                colors=["W", "U"],
                color_mode="exact",  # Only W/U, no other colors
                page=1,
                page_size=20
            )

            # Find cards that fit in white-blue color identity
            result = await repo.search_advanced(
                colors=["W", "U"],
                color_mode="at_most",  # Colorless, W, U, or W/U only
                page=1,
                page_size=20
            )

            # Find cards with specific oracle text
            result = await repo.search_advanced(
                oracle_text_phrases=["target creature you control", "gains flying"],
                page=1,
                page_size=20
            )

            # Backward compatibility with limit
            result = await repo.search_advanced(
                colors=["R"],
                limit=30  # Treated as page_size=30, page=1
            )
        """

        # Handle backward compatibility with limit parameter
        if limit is not None:
            page_size = limit
            page = 1

        # Cap page_size at 50
        page_size = min(page_size, 50)

        stmt = select(CardModel)

        # Apply color filter based on color_mode
        if colors:
            if color_mode == "any":
                # OR logic - card must have at least one of the colors (current behavior)
                color_conditions = []
                for color in colors:
                    color_conditions.append(cast(CardModel.colors, String).like(f'%"{color}"%'))
                stmt = stmt.where(or_(*color_conditions))

            elif color_mode == "all":
                # AND logic - card must have ALL of the specified colors
                for color in colors:
                    stmt = stmt.where(cast(CardModel.colors, String).like(f'%"{color}"%'))

            elif color_mode == "exact":
                # Exact match - card must have ALL specified colors and NO others
                # Use AND for all specified colors + length check
                for color in colors:
                    stmt = stmt.where(cast(CardModel.colors, String).like(f'%"{color}"%'))
                # Add json_array_length check to ensure no extra colors
                stmt = stmt.where(func.json_array_length(CardModel.colors) == len(colors))

            elif color_mode == "at_most":
                # Subset/color identity - card colors must be subset of specified colors
                # Use NOT LIKE for all colors not in the allowed set
                all_colors = {"W", "U", "B", "R", "G"}
                excluded_colors = all_colors - set(colors)
                for excluded in excluded_colors:
                    # Exclude cards that contain colors not in the allowed set
                    stmt = stmt.where(not_(cast(CardModel.colors, String).like(f'%"{excluded}"%')))

        # Special case: empty colors list with exact mode means colorless cards
        elif color_mode == "exact" and colors is not None and len(colors) == 0:
            # Find colorless cards (empty colors array)
            stmt = stmt.where(func.json_array_length(CardModel.colors) == 0)

        # Apply type filters (AND logic - must match all types)
        if types:
            for type_str in types:
                stmt = stmt.where(
                    CardModel.type_line.ilike(contains_pattern(type_str), escape=LIKE_ESCAPE)
                )

        # Apply keyword filters (AND logic - must have all keywords)
        if keywords:
            for keyword in keywords:
                oracle_match = CardModel.oracle_text.ilike(
                    contains_pattern(keyword), escape=LIKE_ESCAPE
                )
                keywords_match = cast(CardModel.keywords, String).ilike(
                    contains_pattern(f'"{keyword}"'), escape=LIKE_ESCAPE
                )
                stmt = stmt.where(or_(oracle_match, keywords_match))

        # Apply oracle text phrase filters (AND logic - all phrases must appear)
        if oracle_text_phrases:
            for phrase in oracle_text_phrases:
                stmt = stmt.where(
                    CardModel.oracle_text.ilike(contains_pattern(phrase), escape=LIKE_ESCAPE)
                )

        # Apply mana value range filters
        if mana_value_min is not None:
            stmt = stmt.where(CardModel.cmc >= mana_value_min)
        if mana_value_max is not None:
            stmt = stmt.where(CardModel.cmc <= mana_value_max)

        # Apply rarity filter (case-insensitive)
        if rarity is not None:
            # Normalize to list for uniform handling
            rarity_list = [rarity] if isinstance(rarity, str) else rarity

            if len(rarity_list) == 1:
                # Single rarity - direct comparison (case-insensitive)
                stmt = stmt.where(CardModel.rarity.ilike(rarity_list[0]))
            else:
                # Multiple rarities - OR logic (case-insensitive)
                rarity_conditions = [CardModel.rarity.ilike(r) for r in rarity_list]
                stmt = stmt.where(or_(*rarity_conditions))

        # Apply format filter
        stmt = self._apply_format_filter(stmt, format_filter)

        # Apply games filter
        stmt = self._apply_games_filter(stmt, games)

        # Apply unique oracle filter (removes duplicate printings)
        stmt = self._apply_unique_oracle_filter(stmt)

        # Get total count (after unique oracle filter, before pagination)
        count_query = select(func.count()).select_from(stmt.subquery())
        total_count = await self.session.scalar(count_query) or 0

        # Calculate pagination metadata
        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 0

        # Apply pagination
        offset = (page - 1) * page_size
        stmt = stmt.order_by(CardModel.cmc, CardModel.name).offset(offset).limit(page_size)

        # Execute query
        result = await self.session.execute(stmt)
        card_models = result.scalars().all()

        # Convert to Pydantic schemas
        cards = [Card.model_validate(card) for card in card_models]

        return PaginatedResult(
            items=cards,
            total_count=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )


# --- The one card-name resolver's statements -------------------------------------------------
#
# Built over any column set, so the async session can select the ``CardModel`` entity and the sync
# sqlite-vec connection a few columns, and both run the same SQL.


def _exact_name_statement(
    columns: Sequence[Any],
    name: str,
    *,
    format_filter: FormatFilter = None,
    games: GamesFilter = None,
) -> Select[Any]:
    """The exact step: ``COLLATE NOCASE`` equality on ``name`` OR ``printed_name``, first by id.

    One collated term per index: SQLite's OR optimisation needs an index for each term (the
    ``ix_cards_*_nocase`` pair) or it falls back to a table scan.
    """
    stmt = select(*columns).where(
        or_(
            CardModel.name.collate("NOCASE") == name,
            CardModel.printed_name.collate("NOCASE") == name,
        )
    )
    stmt = CardRepository._apply_format_filter(stmt, format_filter)
    stmt = CardRepository._apply_games_filter(stmt, games)
    return stmt.order_by(CardModel.id).limit(1)


def _partial_name_statement(
    columns: Sequence[Any],
    name: str,
    *,
    format_filter: FormatFilter = None,
    games: GamesFilter = None,
    limit: int = MAX_NAME_MATCHES + 1,
) -> Select[Any]:
    """The partial step: an escaped substring match on ``name`` OR ``printed_name``.

    One card per Oracle id, ordered by name then id, at most ``limit`` rows (by default one more
    than :data:`MAX_NAME_MATCHES`, so the caller can tell a full list from a cut one). ``columns``
    must include ``CardModel.id`` and ``CardModel.oracle_id`` (the one-per-Oracle filter reads
    both).
    """
    pattern = contains_pattern(name)
    stmt = select(*columns).where(
        or_(
            CardModel.name.ilike(pattern, escape=LIKE_ESCAPE),
            CardModel.printed_name.ilike(pattern, escape=LIKE_ESCAPE),
        )
    )
    stmt = CardRepository._apply_format_filter(stmt, format_filter)
    stmt = CardRepository._apply_games_filter(stmt, games)
    stmt = CardRepository._apply_unique_oracle_filter(stmt)
    return stmt.order_by(CardModel.name.collate("NOCASE"), CardModel.id).limit(limit)


def _bucket[T](rows: Sequence[T]) -> NameResolution[T]:
    """Turn the partial step's rows (at most ``MAX_NAME_MATCHES + 1``) into a resolution."""
    if not rows:
        return NameResolution()
    if len(rows) == 1:
        return NameResolution(card=rows[0])
    return NameResolution(matches=list(rows[:MAX_NAME_MATCHES]), more=len(rows) > MAX_NAME_MATCHES)


def _fetch_all(conn: sqlite3.Connection, stmt: Select[Any]) -> list[Any]:
    """Run ``stmt`` on a plain ``sqlite3`` connection, compiled for SQLite with named params."""
    compiled = stmt.compile(dialect=_SQLITE_NAMED)
    return conn.execute(str(compiled), compiled.params).fetchall()


def resolve_name_on_connection(
    conn: sqlite3.Connection, name: str, columns: Sequence[Any]
) -> NameResolution[Any]:
    """:meth:`CardRepository.resolve_name` for the sync sqlite-vec connection.

    The same strip, blank guard, statements and buckets, with no format or games filter (the one
    caller, ``find_similar_cards``, filters the alternatives, not the seed). Rows come back as the
    connection's rows of ``columns``, in that order.

    Args:
        conn: A ``sqlite3`` connection that sees the ``cards`` table.
        name: The exact or partial card name.
        columns: The ``CardModel`` columns to read; must include ``id`` and ``oracle_id``.

    Returns:
        A :class:`NameResolution` of rows.
    """
    name = name.strip()
    if not name:
        return NameResolution()

    exact = _fetch_all(conn, _exact_name_statement(columns, name))
    if exact:
        return NameResolution(card=exact[0])
    return _bucket(_fetch_all(conn, _partial_name_statement(columns, name)))
