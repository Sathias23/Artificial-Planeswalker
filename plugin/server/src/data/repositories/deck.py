"""Deck repository for database operations on deck data."""

import logging
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal

from sqlalchemy import delete, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import DatabaseError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.data.models.deck import DeckModel
from src.data.models.deck_card import DeckCardModel
from src.data.repositories.base import BaseRepository
from src.data.schemas.deck import Deck, DeckCard

logger = logging.getLogger(__name__)

# Sentinel value to distinguish "not provided" from "clear with None"
_UNSET = object()


class MergeStrategy(str, Enum):
    """Strategy for merging card quantities when combining decks.

    - COMBINE: Sum quantities from both decks (2 + 3 = 5)
    - MAXIMUM: Take the higher quantity (max(2, 3) = 3)
    - REPLACE: Use source deck quantity (target gets 3, source had 3)
    """

    COMBINE = "COMBINE"
    MAXIMUM = "MAXIMUM"
    REPLACE = "REPLACE"


class DeckRepository(BaseRepository):
    """Repository for deck-related database operations.

    Provides methods for querying and manipulating deck and deck-card data.
    Extends BaseRepository for consistent session management.
    """

    def __init__(self, session: AsyncSession):
        """Initialize repository with database session.

        Args:
            session: AsyncSession for database operations
        """
        super().__init__(session)

    async def create_deck(
        self,
        name: str,
        format: str,
        strategy: str | None = None,
        tags: list[str] | None = None,
    ) -> Deck:
        """Create a new deck.

        Transaction management: Explicitly rolls back on any database error
        to prevent session state contamination.

        Args:
            name: Deck name
            format: Deck format (e.g., "standard")
            strategy: Optional deck strategy description
            tags: Optional list of tags/win conditions

        Returns:
            Deck schema with generated id and timestamps

        Raises:
            IntegrityError: If deck name already exists (UNIQUE constraint)
            DatabaseError: For other database-level errors

        Example:
            deck = await repo.create_deck(
                name="Mono Red Aggro",
                format="standard",
                strategy="Fast aggro with burn spells",
                tags=["aggro", "burn"]
            )
        """
        try:
            deck_model = DeckModel(name=name, format=format, strategy=strategy, tags=None)
            if tags:
                deck_model.tags_list = tags
            self.session.add(deck_model)
            await self.session.commit()
            await self.session.refresh(deck_model)
            return Deck.model_validate(deck_model)

        except IntegrityError as e:
            await self.session.rollback()
            logger.warning(
                "IntegrityError in create_deck: name=%s, format=%s, strategy=%s - %s",
                name,
                format,
                strategy,
                str(e),
            )
            raise

        except DatabaseError as e:
            await self.session.rollback()
            logger.error(
                "DatabaseError in create_deck: name=%s, format=%s, strategy=%s, "
                "in_transaction=%s - %s",
                name,
                format,
                strategy,
                self.session.in_transaction(),
                str(e),
            )
            raise

    async def get_deck(self, deck_id: str) -> Deck | None:
        """Get a deck by ID without loading cards.

        Args:
            deck_id: Deck UUID

        Returns:
            Deck schema if found, None otherwise

        Example:
            deck = await repo.get_deck(deck_id="deck-123")
        """
        stmt = select(DeckModel).where(DeckModel.id == deck_id)
        result = await self.session.execute(stmt)
        deck_model = result.scalar_one_or_none()

        if deck_model is None:
            return None

        return Deck.model_validate(deck_model)

    async def update_deck(
        self,
        deck_id: str,
        name: str | None = None,
        strategy: str | None | object = _UNSET,
        tags: list[str] | None | object = _UNSET,
    ) -> Deck | None:
        """Update deck metadata.

        Args:
            deck_id: Deck UUID
            name: New deck name (optional, no update if not provided)
            strategy: New deck strategy (optional, pass None to clear, omit to leave unchanged)
            tags: New tags list (optional, pass None to clear, omit to leave unchanged)

        Returns:
            Updated Deck schema if found, None otherwise

        Example:
            # Update name only
            deck = await repo.update_deck(deck_id="deck-123", name="New Name")

            # Update strategy only
            deck = await repo.update_deck(
                deck_id="deck-123",
                strategy="Control with card advantage"
            )

            # Clear strategy
            deck = await repo.update_deck(deck_id="deck-123", strategy=None)

            # Update tags
            deck = await repo.update_deck(deck_id="deck-123", tags=["aggro", "burn"])
        """
        stmt = select(DeckModel).where(DeckModel.id == deck_id)
        result = await self.session.execute(stmt)
        deck_model = result.scalar_one_or_none()

        if deck_model is None:
            return None

        # Track if any updates were made
        updated = False

        if name is not None:
            deck_model.name = name
            updated = True

        # Use sentinel value to distinguish "not provided" from "clear with None"
        if strategy is not _UNSET:
            deck_model.strategy = strategy  # type: ignore[assignment]
            updated = True

        if tags is not _UNSET:
            deck_model.tags_list = tags  # type: ignore[assignment]
            updated = True

        # Always update timestamp if any field changed
        if updated:
            deck_model.updated_at = datetime.now(UTC)

        await self.session.commit()
        await self.session.refresh(deck_model)
        return Deck.model_validate(deck_model)

    async def delete_deck(self, deck_id: str) -> bool:
        """Delete a deck and all associated cards (cascade).

        Transaction management: Explicitly rolls back on any database error
        to prevent session state contamination.

        Args:
            deck_id: Deck UUID

        Returns:
            True if deck was deleted, False if not found

        Raises:
            DatabaseError: For database-level errors

        Example:
            success = await repo.delete_deck(deck_id="deck-123")
        """
        try:
            stmt = delete(DeckModel).where(DeckModel.id == deck_id)
            result: CursorResult[Any] = await self.session.execute(stmt)  # type: ignore[assignment]
            await self.session.commit()
            return result.rowcount > 0

        except DatabaseError as e:
            await self.session.rollback()
            logger.error(
                "DatabaseError in delete_deck: deck_id=%s, in_transaction=%s - %s",
                deck_id,
                self.session.in_transaction(),
                str(e),
            )
            raise

    async def list_decks(self, format_filter: str | None = None) -> list[Deck]:
        """List all decks, optionally filtered by format.

        Decks are ordered by created_at descending (newest first), with id as a
        secondary key so the order is deterministic when decks share a created_at
        timestamp (rapid creation can tie on the clock).
        Eager loads deck_cards relationship for accurate card counts.

        Args:
            format_filter: Optional format to filter by (e.g., "standard")

        Returns:
            List of Deck schemas with deck_cards populated (empty list if no decks)

        Example:
            all_decks = await repo.list_decks()
            standard_decks = await repo.list_decks(format_filter="standard")
        """
        stmt = select(DeckModel)

        if format_filter is not None:
            stmt = stmt.where(DeckModel.format == format_filter)

        stmt = stmt.order_by(DeckModel.created_at.desc(), DeckModel.id)
        stmt = stmt.options(selectinload(DeckModel.deck_cards).selectinload(DeckCardModel.card))
        result = await self.session.execute(stmt)
        deck_models = result.scalars().all()

        return [Deck.model_validate(deck) for deck in deck_models]

    async def find_deck_by_name(self, name: str) -> Deck | None:
        """Find a deck by case-insensitive partial name match.

        Searches for decks where the name contains the query string,
        case-insensitively. Returns the first match if multiple decks match.

        Args:
            name: Name query string (partial match supported)

        Returns:
            First matching Deck schema if found, None otherwise

        Example:
            deck = await repo.find_deck_by_name("mono red")
            # Matches "Mono Red Aggro", "mono red control", etc.
        """
        stmt = select(DeckModel).where(DeckModel.name.ilike(f"%{name}%"))
        result = await self.session.execute(stmt)
        deck_model = result.scalar_one_or_none()

        if deck_model is None:
            return None

        return Deck.model_validate(deck_model)

    async def add_card_to_deck(
        self, deck_id: str, card_id: str, quantity: int, sideboard: bool = False
    ) -> DeckCard:
        """Add a card to a deck (mainboard or sideboard).

        Transaction management: Explicitly rolls back on any database error
        to prevent session state contamination.

        Args:
            deck_id: Deck UUID
            card_id: Card UUID
            quantity: Number of copies (must be >= 1)
            sideboard: True for sideboard, False for mainboard

        Returns:
            DeckCard schema with card details

        Raises:
            ValueError: If quantity < 1 (rejected before any write)
            IntegrityError: If card already exists in the specified location
            DatabaseError: For other database-level errors

        Example:
            deck_card = await repo.add_card_to_deck(
                deck_id="deck-123",
                card_id="card-456",
                quantity=4,
                sideboard=False
            )
        """
        if quantity < 1:
            # Reject before touching the session so a bad quantity never persists an
            # orphan row (which validate_deck would later undercount). DeckCard validates
            # this on read; this is the write-path backstop for every caller.
            raise ValueError("Quantity must be at least 1")

        try:
            deck_card_model = DeckCardModel(
                deck_id=deck_id, card_id=card_id, quantity=quantity, sideboard=sideboard
            )
            self.session.add(deck_card_model)
            await self.session.commit()

            # Reload with card relationship
            stmt = (
                select(DeckCardModel)
                .where(
                    DeckCardModel.deck_id == deck_id,
                    DeckCardModel.card_id == card_id,
                    DeckCardModel.sideboard == sideboard,
                )
                .options(selectinload(DeckCardModel.card))
            )
            result = await self.session.execute(stmt)
            deck_card_model = result.scalar_one()

            return DeckCard.model_validate(deck_card_model)

        except IntegrityError as e:
            await self.session.rollback()
            logger.warning(
                "IntegrityError in add_card_to_deck: deck_id=%s, card_id=%s, sideboard=%s - %s",
                deck_id,
                card_id,
                sideboard,
                str(e),
            )
            raise

        except DatabaseError as e:
            await self.session.rollback()
            logger.error(
                "DatabaseError in add_card_to_deck: deck_id=%s, card_id=%s, in_transaction=%s - %s",
                deck_id,
                card_id,
                self.session.in_transaction(),
                str(e),
            )
            raise

    async def remove_card_from_deck(
        self, deck_id: str, card_id: str, sideboard: bool = False
    ) -> bool:
        """Remove a card from a deck.

        Transaction management: Explicitly rolls back on any database error
        to prevent session state contamination.

        Args:
            deck_id: Deck UUID
            card_id: Card UUID
            sideboard: True for sideboard, False for mainboard

        Returns:
            True if card was removed, False if not found

        Raises:
            DatabaseError: For database-level errors

        Example:
            success = await repo.remove_card_from_deck(
                deck_id="deck-123",
                card_id="card-456",
                sideboard=False
            )
        """
        try:
            stmt = delete(DeckCardModel).where(
                DeckCardModel.deck_id == deck_id,
                DeckCardModel.card_id == card_id,
                DeckCardModel.sideboard == sideboard,
            )
            result: CursorResult[Any] = await self.session.execute(stmt)  # type: ignore[assignment]
            await self.session.commit()
            return result.rowcount > 0

        except DatabaseError as e:
            await self.session.rollback()
            logger.error(
                "DatabaseError in remove_card_from_deck: deck_id=%s, card_id=%s, "
                "in_transaction=%s - %s",
                deck_id,
                card_id,
                self.session.in_transaction(),
                str(e),
            )
            raise

    async def update_card_quantity(
        self, deck_id: str, card_id: str, quantity: int, sideboard: bool = False
    ) -> DeckCard | None:
        """Update the quantity of a card in a deck.

        Transaction management: Explicitly rolls back on any database error
        to prevent session state contamination.

        Args:
            deck_id: Deck UUID
            card_id: Card UUID
            quantity: New quantity (must be >= 1)
            sideboard: True for sideboard, False for mainboard

        Returns:
            Updated DeckCard schema if found, None otherwise

        Raises:
            ValueError: If quantity < 1 (rejected before any write)
            DatabaseError: For database-level errors

        Example:
            deck_card = await repo.update_card_quantity(
                deck_id="deck-123",
                card_id="card-456",
                quantity=2,
                sideboard=False
            )
        """
        if quantity < 1:
            # Backstop the write path: never persist a quantity DeckCard would reject on read.
            raise ValueError("Quantity must be at least 1")

        try:
            stmt = (
                select(DeckCardModel)
                .where(
                    DeckCardModel.deck_id == deck_id,
                    DeckCardModel.card_id == card_id,
                    DeckCardModel.sideboard == sideboard,
                )
                .options(selectinload(DeckCardModel.card))
            )
            result = await self.session.execute(stmt)
            deck_card_model = result.scalar_one_or_none()

            if deck_card_model is None:
                return None

            deck_card_model.quantity = quantity
            await self.session.commit()
            await self.session.refresh(deck_card_model)
            return DeckCard.model_validate(deck_card_model)

        except DatabaseError as e:
            await self.session.rollback()
            logger.error(
                "DatabaseError in update_card_quantity: deck_id=%s, card_id=%s, "
                "quantity=%s, in_transaction=%s - %s",
                deck_id,
                card_id,
                quantity,
                self.session.in_transaction(),
                str(e),
            )
            raise

    async def update_deck_color_identity(self, deck_id: str) -> Deck | None:
        """Compute and update deck color identity from all cards in the deck.

        Color identity is determined by combining the color identities of all
        cards in the deck (mainboard and sideboard). Colors are sorted in WUBRG order.

        Args:
            deck_id: Deck UUID

        Returns:
            Updated Deck schema with computed color_identity, None if not found

        Example:
            # After adding cards to deck, update color identity
            deck = await repo.update_deck_color_identity(deck_id="deck-123")
            # deck.color_identity == ["W", "R"] for a Boros deck
        """
        # Load deck with cards
        stmt = (
            select(DeckModel)
            .where(DeckModel.id == deck_id)
            .options(selectinload(DeckModel.deck_cards).selectinload(DeckCardModel.card))
        )
        result = await self.session.execute(stmt)
        deck_model = result.scalar_one_or_none()

        if deck_model is None:
            return None

        # Collect all unique colors from deck cards
        color_set: set[str] = set()
        for deck_card in deck_model.deck_cards:
            card_colors = deck_card.card.colors or []
            color_set.update(card_colors)

        # Sort colors in WUBRG order
        wubrg_order = ["W", "U", "B", "R", "G"]
        sorted_colors = [c for c in wubrg_order if c in color_set]

        # Update deck color identity
        deck_model.color_identity_list = sorted_colors if sorted_colors else None

        await self.session.commit()
        await self.session.refresh(deck_model)
        return Deck.model_validate(deck_model)

    async def get_deck_with_cards(self, deck_id: str) -> Deck | None:
        """Get a deck with all cards loaded (eager loading).

        Performs eager loading to retrieve deck with all associated cards
        in a single query. Cards are loaded with full Card details.

        Args:
            deck_id: Deck UUID

        Returns:
            Deck schema with deck_cards list populated, None if not found

        Example:
            deck = await repo.get_deck_with_cards(deck_id="deck-123")
            if deck:
                for deck_card in deck.deck_cards:
                    print(f"{deck_card.quantity}x {deck_card.card.name}")
        """
        stmt = (
            select(DeckModel)
            .where(DeckModel.id == deck_id)
            .options(selectinload(DeckModel.deck_cards).selectinload(DeckCardModel.card))
        )
        result = await self.session.execute(stmt)
        deck_model = result.scalar_one_or_none()

        if deck_model is None:
            return None

        return Deck.model_validate(deck_model)

    async def merge_decks(
        self,
        target_deck_id: str,
        source_deck_id: str,
        strategy: Literal["COMBINE", "MAXIMUM", "REPLACE"] | MergeStrategy = MergeStrategy.COMBINE,
    ) -> Deck | None:
        """Merge cards from source deck into target deck using specified strategy.

        This operation combines cards from two decks, respecting mainboard/sideboard
        locations. The source deck remains unchanged (non-destructive merge).

        Transaction management: Explicitly rolls back on any database error
        to prevent session state contamination.

        Args:
            target_deck_id: UUID of deck to merge cards into (modified)
            source_deck_id: UUID of deck to merge cards from (unchanged)
            strategy: Merge strategy for overlapping cards:
                - COMBINE: Sum quantities (2 + 3 = 5)
                - MAXIMUM: Take higher quantity (max(2, 3) = 3)
                - REPLACE: Use source quantity (target gets 3)

        Returns:
            Updated Deck schema with merged cards, None if either deck not found

        Raises:
            IntegrityError: If merge violates database constraints
            DatabaseError: For other database-level errors

        Example:
            # Combine quantities from both decks
            merged = await repo.merge_decks(
                target_deck_id="deck-123",
                source_deck_id="deck-456",
                strategy=MergeStrategy.COMBINE
            )

            # Take maximum quantity when cards overlap
            merged = await repo.merge_decks(
                target_deck_id="deck-123",
                source_deck_id="deck-456",
                strategy="MAXIMUM"
            )
        """
        try:
            # Convert string strategy to enum if needed
            if isinstance(strategy, str):
                strategy = MergeStrategy(strategy)

            # Load both decks with cards
            target_deck = await self.get_deck_with_cards(target_deck_id)
            source_deck = await self.get_deck_with_cards(source_deck_id)

            # Return None if either deck doesn't exist
            if target_deck is None or source_deck is None:
                return None

            # Track cards added and merged for logging
            cards_added = 0
            cards_merged = 0

            # Build a lookup map for target deck cards: (card_id, sideboard) -> quantity
            target_card_map: dict[tuple[str, bool], int] = {
                (dc.card_id, dc.sideboard): dc.quantity for dc in target_deck.deck_cards
            }

            # Process each card from source deck
            for source_card in source_deck.deck_cards:
                card_key = (source_card.card_id, source_card.sideboard)

                if card_key in target_card_map:
                    # Card exists in target - apply merge strategy
                    target_quantity = target_card_map[card_key]
                    source_quantity = source_card.quantity

                    if strategy == MergeStrategy.COMBINE:
                        new_quantity = target_quantity + source_quantity
                    elif strategy == MergeStrategy.MAXIMUM:
                        new_quantity = max(target_quantity, source_quantity)
                    elif strategy == MergeStrategy.REPLACE:
                        new_quantity = source_quantity
                    else:
                        # Should never happen with type hints, but be defensive
                        raise ValueError(f"Invalid merge strategy: {strategy}")

                    # Update quantity if it changed
                    if new_quantity != target_quantity:
                        await self.update_card_quantity(
                            deck_id=target_deck_id,
                            card_id=source_card.card_id,
                            quantity=new_quantity,
                            sideboard=source_card.sideboard,
                        )
                        cards_merged += 1
                else:
                    # Card doesn't exist in target - add it
                    await self.add_card_to_deck(
                        deck_id=target_deck_id,
                        card_id=source_card.card_id,
                        quantity=source_card.quantity,
                        sideboard=source_card.sideboard,
                    )
                    cards_added += 1

            # Update target deck color identity
            await self.update_deck_color_identity(target_deck_id)

            # Update timestamp
            stmt = select(DeckModel).where(DeckModel.id == target_deck_id)
            result = await self.session.execute(stmt)
            deck_model = result.scalar_one_or_none()
            if deck_model:
                deck_model.updated_at = datetime.now(UTC)
                await self.session.commit()

            # Expire all objects to ensure fresh data on next query
            self.session.expire_all()

            # Reload deck with all cards for return value
            updated_deck = await self.get_deck_with_cards(target_deck_id)

            # Log successful merge
            logger.info(
                "Merged decks: target_id=%s, source_id=%s, strategy=%s, "
                "cards_added=%d, cards_merged=%d",
                target_deck_id,
                source_deck_id,
                strategy.value,
                cards_added,
                cards_merged,
            )

            return updated_deck

        except IntegrityError as e:
            await self.session.rollback()
            logger.warning(
                "IntegrityError in merge_decks: target_id=%s, source_id=%s, strategy=%s - %s",
                target_deck_id,
                source_deck_id,
                strategy.value if isinstance(strategy, MergeStrategy) else strategy,
                str(e),
            )
            raise

        except DatabaseError as e:
            await self.session.rollback()
            logger.error(
                "DatabaseError in merge_decks: target_id=%s, source_id=%s, strategy=%s, "
                "in_transaction=%s - %s",
                target_deck_id,
                source_deck_id,
                strategy.value if isinstance(strategy, MergeStrategy) else strategy,
                self.session.in_transaction(),
                str(e),
            )
            raise
