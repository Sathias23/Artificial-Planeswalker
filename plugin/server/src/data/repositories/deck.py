"""Deck repository for database operations on deck data."""

import logging
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal

from sqlalchemy import case, delete, distinct, func, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import DatabaseError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from src.data.models.card import CardModel
from src.data.models.deck import DeckModel
from src.data.models.deck_card import DeckCardModel
from src.data.repositories.base import BaseRepository
from src.data.schemas.card import Card
from src.data.schemas.deck import Deck, DeckCard, DeckCardEntry, DeckSummary

logger = logging.getLogger(__name__)

# Sentinel value to distinguish "not provided" from "clear with None"
_UNSET = object()

#: Canonical colour order for every stored identity (AGENTS.md: colour codes are WUBRG-ordered).
_WUBRG_ORDER = ("W", "U", "B", "R", "G")


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
        to prevent session state contamination. A ``DatabaseError`` raised while
        re-reading after the commit is not a failed write; the method answers with the
        state it wrote (see :meth:`_reload_committed`).

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

        # Committed. Snapshot first, re-read second (see ``_reload_committed``).
        written = Deck.model_validate(deck_model)
        if await self._reload_committed(
            "create_deck", written.id, lambda: self._reload_after_commit(deck_model)
        ):
            return Deck.model_validate(deck_model)
        return written

    async def clone_deck(self, deck_id: str, name: str | None = None) -> Deck | None:
        """Copy metadata and every association in one transaction, preserving the source.

        A committed snapshot includes all cards even if the postcommit refresh fails.

        Args:
            deck_id: Source deck id.
            name: Copy name, or None for the source name plus " (copy)".

        Returns:
            The independent copy with all card rows, or None if the source is missing.

        Raises:
            DatabaseError: A precommit database failure, after rollback.
        """
        try:
            # One statement snapshots metadata, associations and cards together, even
            # with SQLite's legacy transaction mode (SELECT does not begin a transaction).
            result = await self.session.execute(
                select(DeckModel)
                .where(DeckModel.id == deck_id)
                .options(joinedload(DeckModel.deck_cards).joinedload(DeckCardModel.card))
                .execution_options(populate_existing=True)
            )
            source_model = result.unique().scalar_one_or_none()
            if source_model is None:
                return None
            source = Deck.model_validate(source_model)
            model = DeckModel(
                name=name if name is not None else f"{source.name} (copy)",
                format=source.format,  # type: ignore[arg-type]
                strategy=source.strategy,
            )
            model.tags_list = source.tags
            model.color_identity_list = source.color_identity
            self.session.add(model)
            await self.session.flush()
            self.session.add_all(
                DeckCardModel(
                    deck_id=model.id,
                    card_id=row.card_id,
                    quantity=row.quantity,
                    sideboard=row.sideboard,
                    commander=row.commander,
                )
                for row in source.deck_cards
            )
            await self.session.commit()
        except DatabaseError as e:
            await self.session.rollback()
            logger.error("DatabaseError in clone_deck: deck_id=%s - %s", deck_id, str(e))
            raise

        written = Deck.model_validate(model).model_copy(
            update={
                "deck_cards": [
                    row.model_copy(update={"deck_id": model.id}, deep=True)
                    for row in source.deck_cards
                ]
            }
        )
        await self._reload_committed(
            "clone_deck", written.id, lambda: self._reload_after_commit(model)
        )
        return written

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

        Transaction management: Explicitly rolls back on any database error
        to prevent session state contamination. A ``DatabaseError`` raised while
        re-reading after the commit is not a failed write; the method answers with the
        state it wrote (see :meth:`_reload_committed`).

        Returns:
            Updated Deck schema if found, None otherwise

        Raises:
            DatabaseError: For database-level errors

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
        try:
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

        except DatabaseError as e:
            await self.session.rollback()
            logger.error(
                "DatabaseError in update_deck: deck_id=%s, in_transaction=%s - %s",
                deck_id,
                self.session.in_transaction(),
                str(e),
            )
            raise

        # Committed. Snapshot first, re-read second (see ``_reload_committed``).
        written = Deck.model_validate(deck_model)
        if await self._reload_committed(
            "update_deck", deck_id, lambda: self._reload_after_commit(deck_model)
        ):
            return Deck.model_validate(deck_model)
        return written

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

    async def list_deck_summaries(self, format_filter: str | None = None) -> list[DeckSummary]:
        """List every deck's metadata and counts without loading a single card row.

        The count-only counterpart of :meth:`list_decks`: same filter, same
        ``created_at DESC, id`` order, same values — but the three counts are computed
        by the database instead of by summing an eager-loaded ``deck_cards`` collection,
        so listing 52 decks reads 52 rows rather than every card of every deck.

        The aggregates mirror ``DeckSummary._summary_fields`` exactly:
        ``mainboard_count`` and ``sideboard_count`` are quantity sums split on the
        ``sideboard`` flag, and ``distinct_cards`` counts distinct ``card_id`` values
        across **both** boards, so a card held in the mainboard and the sideboard counts
        once. A deck with no cards outer-joins to nothing and coalesces to three zeroes.

        Args:
            format_filter: Optional format to filter by (e.g., "standard")

        Returns:
            List of DeckSummary schemas (empty list if no decks match)

        Example:
            summaries = await repo.list_deck_summaries()
        """
        mainboard = func.coalesce(
            func.sum(case((DeckCardModel.sideboard.is_(False), DeckCardModel.quantity), else_=0)),
            0,
        )
        sideboard = func.coalesce(
            func.sum(case((DeckCardModel.sideboard.is_(True), DeckCardModel.quantity), else_=0)),
            0,
        )
        distinct_cards = func.count(distinct(DeckCardModel.card_id))

        stmt = select(DeckModel, mainboard, sideboard, distinct_cards).outerjoin(
            DeckCardModel, DeckCardModel.deck_id == DeckModel.id
        )

        if format_filter is not None:
            stmt = stmt.where(DeckModel.format == format_filter)

        stmt = stmt.group_by(DeckModel.id).order_by(DeckModel.created_at.desc(), DeckModel.id)

        result = await self.session.execute(stmt)

        return [
            DeckSummary(
                id=deck.id,
                name=deck.name,
                format=deck.format,
                strategy=deck.strategy,
                color_identity=deck.color_identity_list,
                tags=deck.tags_list,
                mainboard_count=int(main_count),
                sideboard_count=int(side_count),
                distinct_cards=int(distinct_count),
                created_at=deck.created_at,
                updated_at=deck.updated_at,
            )
            for deck, main_count, side_count, distinct_count in result.all()
        ]

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
        self,
        deck_id: str,
        card_id: str,
        quantity: int,
        sideboard: bool = False,
        commander: bool = False,
    ) -> DeckCard:
        """Add a card to a deck (mainboard or sideboard).

        Transaction management: Explicitly rolls back on any database error
        to prevent session state contamination. A ``DatabaseError`` raised while
        re-reading after the commit is not a failed write; the method answers with the
        state it wrote (see :meth:`_reload_committed`).

        Args:
            deck_id: Deck UUID
            card_id: Card UUID
            quantity: Number of copies (must be >= 1)
            sideboard: True for sideboard, False for mainboard
            commander: Mark this card as one of the deck's commanders
                (flag two cards for partners)

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
                sideboard=False,
                commander=False
            )
        """
        if quantity < 1:
            # Reject before touching the session so a bad quantity never persists an
            # orphan row (which validate_deck would later undercount). DeckCard validates
            # this on read; this is the write-path backstop for every caller.
            raise ValueError("Quantity must be at least 1")

        try:
            deck_card_model = DeckCardModel(
                deck_id=deck_id,
                card_id=card_id,
                quantity=quantity,
                sideboard=sideboard,
                commander=commander,
            )
            self.session.add(deck_card_model)
            # Flush first so the metadata refresh sees the new row (and a dangling deck or card
            # id raises IntegrityError here, before any deck row is touched).
            await self.session.flush()
            deck_model = await self._refresh_deck_metadata(deck_id)
            # The card is read before the commit so the answer can be built without any I/O
            # afterwards (the association's ``card`` relation is ``noload``).
            card_model = await self.session.get(CardModel, card_id)
            await self.session.commit()

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

        # Committed. Snapshot first, re-read second (see ``_reload_committed``).
        assert card_model is not None  # the flush enforced the foreign key
        written = DeckCard(
            deck_id=deck_id,
            card_id=card_id,
            quantity=quantity,
            sideboard=sideboard,
            commander=commander,
            card=Card.model_validate(card_model),
        )
        reloaded: list[DeckCardModel] = []

        async def reload() -> None:
            await self._reload_after_commit(deck_model)
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
            reloaded.append(result.scalar_one())

        if await self._reload_committed("add_card_to_deck", deck_id, reload):
            return DeckCard.model_validate(reloaded[0])
        return written

    async def add_cards_to_deck(
        self, deck_id: str, entries: Sequence[DeckCardEntry]
    ) -> list[DeckCard]:
        """Add many cards to a deck in one transaction: one commit, one reload.

        The bulk sibling of :meth:`add_card_to_deck` for ``import_decklist``. Every entry is
        staged, committed together, and the new rows are reloaded (with their cards) in one
        query. On any database error before or at the commit the session is rolled back and
        **nothing** is added. A ``DatabaseError`` raised while
        re-reading after the commit is not a failed write; the method answers with the
        state it wrote (see :meth:`_reload_committed`).

        Args:
            deck_id: Deck UUID
            entries: The rows to add. The caller must not repeat a ``(card_id, sideboard)``
                pair (the association's primary key) and must not name a row already in the
                deck — either is an ``IntegrityError`` that rolls back the whole batch. Each
                entry's quantity is at least 1 by construction; the upper cap
                (``MAX_CARD_QUANTITY``) is the caller's job.

        Returns:
            One ``DeckCard`` per entry, in entry order; an empty list (and no commit) for no
            entries.

        Raises:
            IntegrityError: If any entry duplicates a row in the deck or in ``entries``.
            DatabaseError: For other database-level errors.
        """
        if not entries:
            return []

        try:
            self.session.add_all(
                DeckCardModel(
                    deck_id=deck_id,
                    card_id=entry.card_id,
                    quantity=entry.quantity,
                    sideboard=entry.sideboard,
                    commander=entry.commander,
                )
                for entry in entries
            )
            await self.session.flush()
            deck_model = await self._refresh_deck_metadata(deck_id)
            # The cards are read before the commit so the answer can be built without any I/O
            # afterwards (the association's ``card`` relation is ``noload``).
            card_ids = {entry.card_id for entry in entries}
            cards_by_id = {
                card.id: Card.model_validate(card)
                for card in (
                    await self.session.execute(select(CardModel).where(CardModel.id.in_(card_ids)))
                ).scalars()
            }
            await self.session.commit()

        except IntegrityError as e:
            await self.session.rollback()
            logger.warning(
                "IntegrityError in add_cards_to_deck: deck_id=%s, entries=%d - %s",
                deck_id,
                len(entries),
                str(e),
            )
            raise

        except DatabaseError as e:
            await self.session.rollback()
            logger.error(
                "DatabaseError in add_cards_to_deck: deck_id=%s, entries=%d, "
                "in_transaction=%s - %s",
                deck_id,
                len(entries),
                self.session.in_transaction(),
                str(e),
            )
            raise

        # Committed. Snapshot first, re-read second (see ``_reload_committed``).
        written = [
            DeckCard(
                deck_id=deck_id,
                card_id=entry.card_id,
                quantity=entry.quantity,
                sideboard=entry.sideboard,
                commander=entry.commander,
                card=cards_by_id[entry.card_id],  # the flush enforced every foreign key
            )
            for entry in entries
        ]
        reloaded: list[DeckCard] = []

        async def reload() -> None:
            await self._reload_after_commit(deck_model)
            stmt = (
                select(DeckCardModel)
                .where(
                    DeckCardModel.deck_id == deck_id,
                    DeckCardModel.card_id.in_(card_ids),
                )
                .options(selectinload(DeckCardModel.card))
            )
            result = await self.session.execute(stmt)
            by_key = {(row.card_id, row.sideboard): row for row in result.scalars()}
            reloaded.extend(
                DeckCard.model_validate(by_key[(entry.card_id, entry.sideboard)])
                for entry in entries
            )

        if await self._reload_committed("add_cards_to_deck", deck_id, reload):
            return reloaded
        return written

    async def remove_card_from_deck(
        self, deck_id: str, card_id: str, sideboard: bool = False
    ) -> bool:
        """Remove a card from a deck.

        Transaction management: Explicitly rolls back on any database error
        to prevent session state contamination. A ``DatabaseError`` raised while
        re-reading after the commit is not a failed write; the method answers with the
        state it wrote (see :meth:`_reload_committed`).

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
            if result.rowcount == 0:
                # Nothing left the deck, so its identity and timestamp stay untouched.
                await self.session.rollback()
                return False
            deck_model = await self._refresh_deck_metadata(deck_id)
            await self.session.commit()

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

        # Committed: the row is gone whatever the re-read says (see ``_reload_committed``).
        await self._reload_committed(
            "remove_card_from_deck", deck_id, lambda: self._reload_after_commit(deck_model)
        )
        return True

    async def update_card_quantity(
        self, deck_id: str, card_id: str, quantity: int, sideboard: bool = False
    ) -> DeckCard | None:
        """Update the quantity of a card in a deck.

        Transaction management: Explicitly rolls back on any database error
        to prevent session state contamination. A ``DatabaseError`` raised while
        re-reading after the commit is not a failed write; the method answers with the
        state it wrote (see :meth:`_reload_committed`).

        Args:
            deck_id: Deck UUID
            card_id: Card UUID
            quantity: New quantity (must be >= 1)
            sideboard: True for sideboard, False for mainboard

        Returns:
            Updated DeckCard schema if found, None otherwise. A quantity equal to the stored
            one is a no-op: the row is returned as is and the deck's ``updated_at`` and
            ``color_identity`` are not touched.

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

            if deck_card_model.quantity == quantity:
                # Nothing changes, so the deck's identity and timestamp stay untouched (the same
                # no-op rule as a remove that matched no row).
                unchanged = DeckCard.model_validate(deck_card_model)
                await self.session.rollback()  # closes the read transaction; expires the row
                return unchanged

            deck_card_model.quantity = quantity
            await self.session.flush()
            deck_model = await self._refresh_deck_metadata(deck_id)
            await self.session.commit()

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

        # Committed. Snapshot first (the pre-commit select eager-loaded ``card``), re-read second
        # (see ``_reload_committed``).
        written = DeckCard.model_validate(deck_card_model)

        async def reload() -> None:
            await self._reload_after_commit(deck_model)
            await self.session.refresh(deck_card_model)

        if await self._reload_committed("update_card_quantity", deck_id, reload):
            return DeckCard.model_validate(deck_card_model)
        return written

    async def _refresh_deck_metadata(self, deck_id: str) -> DeckModel | None:
        """Recompute a deck's colour identity and bump ``updated_at`` inside the open transaction.

        The one place every card mutation (add, bulk add, remove, quantity update, merge; import
        goes through bulk add) keeps the deck row honest. Identity is the WUBRG-ordered union of
        ``card.color_identity`` over mainboard and sideboard rows — *identity*, not ``colors``, so
        a colourless-cost card with a blue identity makes the deck blue (search filters keep using
        ``colors``). Does **not** commit: callers flush their own rows first so the query sees
        them, then commit once, keeping one transaction per repository write.

        The colours come from a JOIN over ``deck_cards`` rather than the deck's ``deck_cards``
        collection: an eager load onto a deck already in the identity map leaves an
        already-populated collection as it was, so a stale (empty) collection would silently
        compute an empty identity. The query always reads what the flush wrote.

        Args:
            deck_id: Deck UUID

        Returns:
            The mutated ``DeckModel`` (still pending), or ``None`` if the deck does not exist.
        """
        deck_model = await self.session.get(DeckModel, deck_id)
        if deck_model is None:
            return None

        stmt = (
            select(CardModel.color_identity)
            .join(DeckCardModel, DeckCardModel.card_id == CardModel.id)
            .where(DeckCardModel.deck_id == deck_id)
        )
        color_set: set[str] = set()
        for (card_identity,) in await self.session.execute(stmt):
            color_set.update(card_identity or [])

        deck_model.color_identity_list = [c for c in _WUBRG_ORDER if c in color_set]
        deck_model.updated_at = datetime.now(UTC)
        return deck_model

    async def _reload_after_commit(self, deck_model: DeckModel | None) -> None:
        """Re-read a just-committed deck row so the identity map matches the database.

        ``expire_on_commit=False`` leaves the aware ``updated_at`` assigned by
        :meth:`_refresh_deck_metadata` in memory while the ``DateTime`` column stores it naive;
        a later read in the same session would otherwise hand back the aware value. An explicit
        refresh (never ``expire``, whose lazy reload would be implicit I/O under asyncio) keeps
        the two consistent.

        Args:
            deck_model: The deck returned by :meth:`_refresh_deck_metadata`; ``None`` is a no-op.
        """
        if deck_model is not None:
            await self.session.refresh(deck_model)

    async def _reload_committed(
        self, label: str, deck_id: str, reload: Callable[[], Awaitable[None]]
    ) -> bool:
        """Run a writer's post-commit re-read; a failure there is never a failed write.

        The discipline every writer follows: the ``try``/rollback/re-raise block ends at the
        commit; then the answer is **snapshotted from the in-memory instances first** (with
        ``expire_on_commit=False`` they hold exactly the values written, so the snapshot needs
        no I/O); and only then is the database re-read, through here. A ``DatabaseError`` from
        *reload* cannot undo a landed commit, so re-raising it would report a successful write
        as a failure and invite a retry of a change that already happened. Instead the broken
        read transaction is rolled back, a warning is logged, and ``False`` tells the caller to
        answer with its snapshot. That rollback expires every instance in the session, which is
        why the snapshot must come first: after a ``False`` return no caller may touch an ORM
        attribute (under asyncio that would be implicit lazy I/O).

        Args:
            label: The writer's name, for the log line.
            deck_id: The deck the write touched, for the log line.
            reload: The re-read to attempt (a refresh, a select, or both).

        Returns:
            ``True`` when the re-read succeeded and the caller may answer from the refreshed
            instances; ``False`` when it failed and the snapshot is the answer.
        """
        try:
            await reload()
        except DatabaseError as e:
            await self.session.rollback()
            logger.warning(
                "%s committed but the post-commit re-read failed: deck_id=%s - %s",
                label,
                deck_id,
                str(e),
            )
            return False
        return True

    async def update_deck_color_identity(self, deck_id: str) -> Deck | None:
        """Recompute and commit a deck's colour identity (and ``updated_at``) from its cards.

        A committing wrapper over the refresh every card mutation already runs; useful for
        repairing a deck written before the repository maintained its metadata. Colour identity
        is the WUBRG-ordered union of the cards' ``color_identity`` (mainboard and sideboard).
        A ``DatabaseError`` raised while re-reading after the commit is not a failed write; the
        method answers with the state it wrote (see :meth:`_reload_committed`).

        Args:
            deck_id: Deck UUID

        Returns:
            Updated Deck schema with computed color_identity, None if not found

        Example:
            deck = await repo.update_deck_color_identity(deck_id="deck-123")
            # deck.color_identity == ["W", "R"] for a Boros deck
        """
        try:
            deck_model = await self._refresh_deck_metadata(deck_id)
            if deck_model is None:
                return None

            await self.session.commit()

        except (IntegrityError, DatabaseError) as e:
            await self.session.rollback()
            logger.error(
                "DatabaseError in update_deck_color_identity: deck_id=%s, in_transaction=%s - %s",
                deck_id,
                self.session.in_transaction(),
                str(e),
            )
            raise

        # Committed. Snapshot first, re-read second (see ``_reload_committed``).
        written = Deck.model_validate(deck_model)
        if await self._reload_committed(
            "update_deck_color_identity", deck_id, lambda: self._reload_after_commit(deck_model)
        ):
            return Deck.model_validate(deck_model)
        return written

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
        to prevent session state contamination. A ``DatabaseError`` raised while
        re-reading after the commit is not a failed write; the method answers with the
        state it wrote (see :meth:`_reload_committed`).

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
            # The rows as written, keyed the same way: every per-row call below returns the row
            # it persisted, so the answer can be assembled without re-reading anything.
            written_rows: dict[tuple[str, bool], DeckCard] = {
                (dc.card_id, dc.sideboard): dc for dc in target_deck.deck_cards
            }

            # Process each card from source deck
            for source_card in source_deck.deck_cards:
                card_key = (source_card.card_id, source_card.sideboard)

                if card_key in target_card_map:
                    # Card exists in target - apply merge strategy. Quantity-only
                    # merge: the target's commander flag is kept as-is by design.
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
                        updated_row = await self.update_card_quantity(
                            deck_id=target_deck_id,
                            card_id=source_card.card_id,
                            quantity=new_quantity,
                            sideboard=source_card.sideboard,
                        )
                        if updated_row is not None:
                            written_rows[card_key] = updated_row
                        cards_merged += 1
                else:
                    # Card doesn't exist in target - add it
                    written_rows[card_key] = await self.add_card_to_deck(
                        deck_id=target_deck_id,
                        card_id=source_card.card_id,
                        quantity=source_card.quantity,
                        sideboard=source_card.sideboard,
                        commander=source_card.commander,
                    )
                    cards_added += 1

            # Every add/quantity call above already refreshed the target's metadata; this final
            # pass covers an empty source (no per-row call ran) so a merge always stamps the deck.
            deck_model = await self._refresh_deck_metadata(target_deck_id)
            await self.session.commit()

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

        # Committed. Snapshot first — from the metadata row as stamped and the rows each call
        # above persisted — before ``expire_all`` drops every loaded value (see
        # ``_reload_committed``).
        assert deck_model is not None  # the target was found above
        written = Deck(
            id=deck_model.id,
            name=deck_model.name,
            format=deck_model.format,
            strategy=deck_model.strategy,
            color_identity=deck_model.color_identity_list,
            tags=deck_model.tags_list,
            created_at=deck_model.created_at,
            updated_at=deck_model.updated_at,
            deck_cards=list(written_rows.values()),
        )
        reloaded: list[Deck | None] = []

        async def reload() -> None:
            # Expire all objects to ensure fresh data on the re-read
            self.session.expire_all()
            reloaded.append(await self.get_deck_with_cards(target_deck_id))

        fresh = await self._reload_committed("merge_decks", target_deck_id, reload)

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
        if fresh and reloaded[0] is not None:
            return reloaded[0]
        return written
