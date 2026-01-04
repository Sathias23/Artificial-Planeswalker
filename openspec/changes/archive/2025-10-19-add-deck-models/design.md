# Design Document: Deck Database Models and CRUD Operations

## Context

This change implements the foundational database layer for deck management in Artificial-Planeswalker. Users need to create and persist Standard format Magic: The Gathering decks through the AI assistant. The design follows existing patterns established in the data layer (CardModel, CardRepository) and extends the SQLAlchemy + Pydantic architecture.

**Key Constraints:**
- Follow existing data layer patterns (Repository pattern, ORM → Pydantic conversion)
- Support Standard format initially (extensible to other formats)
- Type-safe async operations throughout
- Cascade delete behavior for deck-card associations

**Stakeholders:**
- Epic 4 Stories 4.2-4.5 depend on this foundation
- Epic 5 deck analysis features require deck data structure
- Agent tools will consume DeckRepository methods via dependency injection

## Goals / Non-Goals

**Goals:**
- Provide type-safe database models for decks and deck-card associations
- Enable CRUD operations for decks with proper relationship management
- Support mainboard and sideboard card tracking
- Maintain consistency with existing Card model patterns
- Enable efficient queries for deck retrieval and listing

**Non-Goals:**
- Deck validation logic (Epic 4 Story 4.3 - business logic layer)
- Mana curve analysis (Epic 5 - business logic layer)
- Synergy detection (Epic 5 - business logic layer)
- Multi-user deck ownership (MVP is single-user)
- Deck versioning or history tracking (post-MVP)
- Import/export functionality (post-MVP)

## Decisions

### Decision 1: Separate Deck and DeckCard Models

**Choice:** Use two separate models (DeckModel for metadata, DeckCardModel for card associations) with a many-to-many relationship pattern.

**Rationale:**
- Decks need metadata (name, format, timestamps) independent of cards
- Many-to-many relationship: one deck has many cards, one card can be in many decks
- Association table (DeckCard) stores quantity and sideboard flag (attributes on the relationship)
- Follows standard SQLAlchemy many-to-many with association object pattern

**Alternatives Considered:**
1. **Single denormalized Deck model with JSON array of card IDs and quantities**
   - ❌ Rejected: Loses referential integrity, harder to query, no foreign key constraints
2. **Direct many-to-many without association object**
   - ❌ Rejected: Can't store quantity and sideboard flag (relationship attributes)

**Implementation:**
```python
# DeckModel - src/data/models/deck.py
class DeckModel(Base):
    __tablename__ = "decks"
    id: Mapped[str] = mapped_column(String, primary_key=True, default_factory=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    format: Mapped[str] = mapped_column(String, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default_factory=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default_factory=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relationship to DeckCardModel (one-to-many)
    deck_cards: Mapped[list["DeckCardModel"]] = relationship("DeckCardModel", back_populates="deck", cascade="all, delete-orphan")

# DeckCardModel - src/data/models/deck_card.py
class DeckCardModel(Base):
    __tablename__ = "deck_cards"
    deck_id: Mapped[str] = mapped_column(String, ForeignKey("decks.id", ondelete="CASCADE"), primary_key=True)
    card_id: Mapped[str] = mapped_column(String, ForeignKey("cards.id"), primary_key=True)
    sideboard: Mapped[bool] = mapped_column(Boolean, primary_key=True, default=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relationships
    deck: Mapped["DeckModel"] = relationship("DeckModel", back_populates="deck_cards")
    card: Mapped["CardModel"] = relationship("CardModel")
```

### Decision 2: Composite Primary Key for DeckCard

**Choice:** Use composite primary key (deck_id, card_id, sideboard) for DeckCardModel.

**Rationale:**
- Ensures uniqueness: each card can only appear once in mainboard and once in sideboard per deck
- Prevents duplicate entries (e.g., "Lightning Bolt x4" appearing twice in mainboard)
- Sideboard as part of key allows same card in both mainboard and sideboard (MTG rules allow this)
- No surrogate ID needed (the combination is the natural key)

**Alternatives Considered:**
1. **Single surrogate ID (UUID) with unique constraint on (deck_id, card_id, sideboard)**
   - ❌ Rejected: Unnecessary complexity, composite key is the natural identifier
2. **Composite key (deck_id, card_id) only, with sideboard as regular column**
   - ❌ Rejected: Can't add same card to mainboard and sideboard (MTG rules violation)

**Trade-offs:**
- ✅ Enforces data integrity at database level
- ✅ Simpler queries (no extra JOIN on surrogate ID)
- ⚠️ Slightly more complex delete operations (must specify deck_id, card_id, sideboard)

### Decision 3: Cascade Delete for Deck-Card Associations

**Choice:** Configure `ON DELETE CASCADE` for deck_id foreign key, but not for card_id.

**Rationale:**
- Deleting a deck should remove all its card associations (deck is parent)
- Deleting a card should NOT be possible if it's in any deck (card is shared resource)
- Prevents orphaned deck_card records when deck is deleted
- Maintains referential integrity

**Implementation:**
```python
deck_id: Mapped[str] = mapped_column(String, ForeignKey("decks.id", ondelete="CASCADE"), primary_key=True)
card_id: Mapped[str] = mapped_column(String, ForeignKey("cards.id"), primary_key=True)  # No cascade

# In DeckModel relationship
deck_cards: Mapped[list["DeckCardModel"]] = relationship("DeckCardModel", back_populates="deck", cascade="all, delete-orphan")
```

**Alternatives Considered:**
1. **Manual deletion in repository (no database cascade)**
   - ❌ Rejected: Error-prone, must remember to delete deck_cards before deck
2. **Cascade delete for card_id as well**
   - ❌ Rejected: Would delete cards from database when removed from deck (incorrect behavior)

### Decision 4: Auto-Managed Timestamps with datetime.now(UTC)

**Choice:** Use `default_factory=lambda: datetime.now(UTC)` and `onupdate=lambda: datetime.now(UTC)` for timestamps.

**Rationale:**
- Consistent with CardModel pattern (if timestamps are added to CardModel later)
- UTC timezone ensures consistency across environments
- SQLAlchemy manages timestamps automatically (no application code needed)
- `onupdate` ensures updated_at refreshes on any modification

**Implementation:**
```python
from datetime import datetime, UTC

created_at: Mapped[datetime] = mapped_column(DateTime, default_factory=lambda: datetime.now(UTC))
updated_at: Mapped[datetime] = mapped_column(DateTime, default_factory=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
```

**Alternatives Considered:**
1. **Database default (CURRENT_TIMESTAMP)**
   - ❌ Rejected: Less portable, inconsistent with Python datetime handling
2. **Application-managed timestamps in repository**
   - ❌ Rejected: More error-prone, must remember to update updated_at manually

### Decision 5: Repository Returns Pydantic Schemas

**Choice:** DeckRepository methods return Pydantic schemas (Deck, DeckCard) instead of SQLAlchemy models.

**Rationale:**
- Consistent with existing CardRepository pattern
- Enforces layer separation (data layer returns serializable DTOs)
- Enables future UI layer changes without coupling to ORM
- Pydantic validation ensures data integrity at layer boundaries

**Implementation:**
```python
async def create_deck(self, name: str, format: str) -> Deck:
    deck_model = DeckModel(name=name, format=format)
    self.session.add(deck_model)
    await self.session.commit()
    await self.session.refresh(deck_model)
    return Deck.model_validate(deck_model)  # ORM → Pydantic
```

**Alternatives Considered:**
1. **Return SQLAlchemy models directly**
   - ❌ Rejected: Couples agent layer to ORM, breaks abstraction
2. **Return dictionaries**
   - ❌ Rejected: Loses type safety, no validation

### Decision 6: Nested Card Schema in DeckCard

**Choice:** DeckCard Pydantic schema includes nested Card schema (full card details).

**Rationale:**
- Agent tools need card details (name, mana_cost, type_line) to display deck contents
- Avoids multiple repository calls (fetch deck, then fetch each card separately)
- Enables rich deck display (show card names, not just IDs)

**Implementation:**
```python
from src.data.schemas.card import Card

class DeckCard(BaseModel):
    deck_id: str
    card_id: str
    quantity: int
    sideboard: bool
    card: Card  # Nested full card details
```

**Trade-offs:**
- ✅ Reduces number of database queries (eager loading)
- ✅ Simplifies agent tool logic (all data in one place)
- ⚠️ Slightly larger response size (includes full card data)
- Mitigation: Acceptable for MVP (typical deck has 60-75 cards, manageable response size)

**Eager Loading Strategy:**
```python
async def get_deck_with_cards(self, deck_id: str) -> Deck | None:
    stmt = select(DeckModel).where(DeckModel.id == deck_id).options(
        selectinload(DeckModel.deck_cards).selectinload(DeckCardModel.card)
    )
    result = await self.session.execute(stmt)
    deck_model = result.scalar_one_or_none()
    return Deck.model_validate(deck_model) if deck_model else None
```

### Decision 7: Format Field as String with Validation

**Choice:** Store format as String column with Pydantic validation for allowed values.

**Rationale:**
- MVP only supports "standard", but design for extensibility (modern, commander, etc.)
- String column is simple and flexible
- Pydantic Literal type hint enforces valid formats at application layer
- Database index on format enables fast filtering

**Implementation:**
```python
# Model
format: Mapped[str] = mapped_column(String, nullable=False, index=True)

# Pydantic Schema
from typing import Literal

class Deck(BaseModel):
    format: Literal["standard"]  # Extend to Literal["standard", "modern", "commander"] post-MVP
```

**Alternatives Considered:**
1. **Enum column in database**
   - ❌ Rejected: Database-specific syntax, harder to extend, less portable
2. **No validation (accept any string)**
   - ❌ Rejected: Allows invalid formats, breaks deck building logic

## Risks / Trade-offs

### Risk 1: Performance with Large Deck Collections

**Risk:** Listing decks with `list_decks()` could be slow if users create hundreds of decks.

**Mitigation:**
- MVP scope is single-user with expected <50 decks
- Add pagination parameters to `list_decks()` post-MVP if needed (`limit`, `offset`)
- Database index on created_at supports fast ordering

**Trade-off:** Accept current implementation for MVP, optimize if user feedback indicates performance issues.

### Risk 2: Concurrent Updates to Same Deck

**Risk:** Two simultaneous updates to the same deck could cause race conditions (unlikely in single-user MVP).

**Mitigation:**
- SQLite serializes writes (no concurrent writes)
- Post-MVP: Add optimistic locking (version field) if moving to PostgreSQL or multi-user

**Trade-off:** Single-user MVP doesn't need concurrency control.

### Risk 3: Card Deletion Impact

**Risk:** Deleting a card from the cards table while it's in decks would break referential integrity.

**Mitigation:**
- Foreign key constraint on `card_id` prevents deletion (raises error)
- Expected behavior: cards are never deleted (Scryfall data is append-only)
- If card deletion is needed post-MVP, implement "soft delete" or cascading logic

**Trade-off:** Accept foreign key constraint error for MVP (cards shouldn't be deleted).

## Migration Plan

### Step 1: Create Tables
- Run `init_database()` to create `decks` and `deck_cards` tables
- Verify schema with `sqlite3 data/cards.db ".schema decks"`

### Step 2: Verify Foreign Keys
- Test foreign key constraints work (attempt to add card with invalid card_id)
- Verify cascade delete (delete deck, check deck_cards are removed)

### Step 3: Smoke Test
- Create test script: create deck → add cards → retrieve → delete
- Verify all operations succeed and data is persisted correctly

### Rollback Plan
- If tables cause issues: `DROP TABLE deck_cards; DROP TABLE decks;`
- Restore from backup if data corruption occurs (unlikely with new tables)

## Open Questions

1. **Should we support deck descriptions/notes?**
   - ⏸️ Deferred to post-MVP (add `description` column later if needed)

2. **Should we track deck archetype (aggro, control, etc.)?**
   - ⏸️ Deferred to post-MVP (could infer from cards or add manual field)

3. **Should we support deck tags/categories?**
   - ⏸️ Deferred to post-MVP (add JSON tags column if needed)

4. **Should we validate maximum sideboard size (15 cards)?**
   - ⏸️ Deferred to Story 4.3 (business logic layer, not data layer)

5. **Should we store deck statistics (total cards, mana curve)?**
   - ⏸️ Deferred to Epic 5 (calculated on-demand, not persisted initially)
