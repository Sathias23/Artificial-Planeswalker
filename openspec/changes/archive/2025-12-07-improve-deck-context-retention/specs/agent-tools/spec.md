# agent-tools Spec Delta

## ADDED Requirements

### Requirement: Abbreviated Search Results for Context Optimization

The system SHALL provide abbreviated search results when result count exceeds 10 cards, reducing context window consumption while maintaining full functionality through pagination.

#### Scenario: Search with 10 or fewer results shows full details
- **GIVEN** a search query that matches 5 cards
- **WHEN** `search_cards_advanced` is called
- **THEN** all 5 cards SHALL be displayed with full details (name, mana cost, type, oracle text, rarity, set)
- **AND** each card SHALL include hover-enabled HTML formatting
- **AND** each card SHALL include visual mana symbols
- **AND** the result SHALL NOT include compact view message

#### Scenario: Search with more than 10 results shows abbreviated format
- **GIVEN** a search query that matches 50 cards (page 1, page_size=20)
- **WHEN** `search_cards_advanced` is called
- **THEN** the first 10 cards SHALL be displayed with full details
- **AND** cards 11-20 SHALL be displayed in compact format (name, mana cost, type line only)
- **AND** compact entries SHALL still include hover-enabled HTML and mana symbols
- **AND** the result SHALL include message "_Use filters or pagination to see more details._"

#### Scenario: Abbreviated format reduces token consumption
- **GIVEN** a search returning 100 cards with full details (baseline: ~20,000 tokens)
- **WHEN** abbreviated format is applied (10 full + 90 compact)
- **THEN** token consumption SHALL be approximately 4,800 tokens
- **AND** token reduction SHALL be ~70% compared to baseline
- **AND** all 100 cards SHALL still be accessible (no data loss)

#### Scenario: Compact format maintains essential information
- **GIVEN** cards displayed in compact format
- **WHEN** a compact card entry is rendered
- **THEN** each entry SHALL include: number, hover-enabled card name, mana cost (visual symbols), type line
- **AND** the format SHALL be: "{number}. {card_name_with_hover} {mana_symbols} - {type_line}\n"
- **AND** oracle text, rarity, and set SHALL be omitted
- **AND** users can see full details via pagination or filtering

#### Scenario: Pagination works correctly with abbreviated results
- **GIVEN** a search with 104 results across 6 pages (page_size=20)
- **WHEN** user requests page 2
- **THEN** page 2 SHALL show first 10 results with full details, remaining 10 compact
- **AND** page navigation message SHALL indicate "Page 2 of 6, showing 21-40"
- **AND** users can navigate to any page to see different card details

#### Scenario: Abbreviated results include clear guidance
- **GIVEN** abbreviated results are displayed
- **WHEN** the compact view section is rendered
- **THEN** the section SHALL have header "**Additional Results** (compact view):"
- **AND** the section SHALL end with "_Use filters or pagination to see more details._"
- **AND** the message SHALL guide users to narrow results for more detail

#### Scenario: Filter count threshold is configurable
- **GIVEN** the abbreviated format threshold is defined
- **WHEN** the tool initializes
- **THEN** a constant `FULL_DETAIL_COUNT = 10` SHALL exist at module level
- **AND** the constant SHALL be easy to adjust if threshold needs tuning
- **AND** the constant SHALL be documented with rationale (balance detail vs. context)

#### Scenario: Search tools preserve context for deck operations
- **GIVEN** a user with active deck performs large search (50+ cards)
- **AND** search results use abbreviated format
- **WHEN** user subsequently adds a card to deck
- **THEN** the agent SHALL still have deck creation context in history
- **AND** the agent SHALL add card to correct deck (not create new deck)
- **AND** abbreviated results SHALL have preserved deck operation context

#### Scenario: Backward compatibility with existing UI
- **GIVEN** existing Chainlit UI expects search results as formatted markdown
- **WHEN** abbreviated results are rendered
- **THEN** all HTML formatting SHALL remain valid (spans, mana symbols)
- **AND** compact entries SHALL render correctly in chat interface
- **AND** hover functionality SHALL work for both full and compact entries
- **AND** no UI layout breakage occurs

### Requirement: Card Image Hover Preservation in Abbreviated Results

The system SHALL preserve card image hover functionality in abbreviated search results, ensuring users can preview card images regardless of result format (full or compact).

#### Scenario: Compact format includes hover-enabled card names
- **GIVEN** a search returns 50 cards with abbreviated formatting
- **WHEN** cards 11-50 are displayed in compact format
- **THEN** each card name SHALL be wrapped with `wrap_card_name_with_hover(card.name, card)` function
- **AND** hovering over card name SHALL display Scryfall card image in tooltip
- **AND** hover functionality SHALL be identical to full-detail card display
- **AND** no visual distinction between full and compact card hover

#### Scenario: Card hover uses existing card image infrastructure
- **GIVEN** abbreviated results include compact card entries
- **WHEN** compact entries are formatted
- **THEN** the same `wrap_card_name_with_hover` function SHALL be used as full results
- **AND** card image URLs SHALL come from `card.image_uris` field
- **AND** CSS class `.card-hover` SHALL be applied to card name spans
- **AND** no duplicate hover implementation required

#### Scenario: Hover gracefully degrades when images unavailable
- **GIVEN** a card in compact format has no image URLs
- **WHEN** the card name is formatted
- **THEN** `wrap_card_name_with_hover` SHALL fall back to plain text
- **AND** no broken image tooltips appear
- **AND** card name remains readable without hover

#### Scenario: Abbreviated results maintain visual consistency
- **GIVEN** a search displays 10 full-detail + 40 compact cards
- **WHEN** user hovers over any card name (full or compact)
- **THEN** the hover tooltip SHALL appear with identical styling
- **AND** card image size SHALL be consistent (250px desktop, 175px tablet, 140px mobile)
- **AND** tooltip position SHALL be consistent (above/below card name)
- **AND** user experience SHALL feel unified across both formats

### Requirement: Search Result Token Usage Optimization

The system SHALL optimize token usage for large search results through abbreviated formatting, preventing conversation history bloat while maintaining user experience.

#### Scenario: Token usage tracked and logged
- **GIVEN** a search is executed with abbreviated results
- **WHEN** results are formatted and returned
- **THEN** the tool SHALL log token count estimate at DEBUG level
- **AND** the log SHALL include: result count, full detail count, compact count, estimated tokens
- **AND** metrics SHALL enable monitoring of token optimization effectiveness

#### Scenario: Token optimization preserves all functionality
- **GIVEN** abbreviated results reduce token usage by 70%
- **WHEN** users interact with search results
- **THEN** users SHALL have access to all card information (via pagination/filters)
- **AND** no features SHALL be removed or degraded
- **AND** user experience SHALL remain intuitive
- **AND** token optimization SHALL be transparent to users

#### Scenario: Large result sets provide actionable guidance
- **GIVEN** a search returns 100+ results (indicating overly broad query)
- **WHEN** abbreviated results are displayed
- **THEN** the tool SHALL suggest refining search with filters
- **AND** the message SHALL be actionable: "Use filters to narrow results"
- **AND** the guidance SHALL appear in the compact view footer
- **AND** users understand how to get more specific results
