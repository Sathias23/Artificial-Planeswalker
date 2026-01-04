# search-pagination Specification Delta

**Target Spec:** `chainlit-ui`

## ADDED Requirements

### Requirement: Search Context Storage
The system SHALL store search parameters in user session to enable pagination without re-specifying search criteria.

#### Scenario: Store search context on query execution
- **WHEN** the agent executes a card search query via `search_cards_advanced` tool
- **AND** the search returns paginated results (total > page_size)
- **THEN** the search parameters are stored in user session with key "search_context"
- **AND** the stored context includes: colors, types, keywords, oracle_text_phrases, mana_value_min, mana_value_max, rarity, page_size, color_mode, format_filter, games
- **AND** the stored context does NOT include the current page number
- **AND** the context can be retrieved for subsequent pagination requests

#### Scenario: Search context serialization
- **WHEN** search parameters are stored in user session
- **THEN** all parameters are JSON-serializable
- **AND** None values are preserved
- **AND** list and dict types are stored correctly
- **AND** the context can be unpacked using `**search_context` for repository calls

#### Scenario: Search context cleared on new search
- **WHEN** the user initiates a new card search with different criteria
- **THEN** the old search context is replaced with the new context
- **AND** pagination for the old search is no longer available
- **AND** the new search starts at page 1

#### Scenario: Search context persists across messages
- **WHEN** the user navigates to page 2 of search results
- **AND** the user sends a non-search message (e.g., "tell me more about card X")
- **AND** the user then navigates to page 3
- **THEN** the original search context is still available
- **AND** pagination continues with the same search filters

### Requirement: Pagination Action Buttons Display
The system SHALL display Next and Previous action buttons for paginated search results with page counter information.

#### Scenario: Next button for non-final pages
- **WHEN** card search results are displayed
- **AND** the current page is less than total_pages
- **THEN** a "Next →" action button is included in the message
- **AND** the button has name="navigate_page"
- **AND** the button payload includes `{"page": current_page + 1}`
- **AND** the button uses icon="arrow-right"

#### Scenario: Previous button for non-first pages
- **WHEN** card search results are displayed
- **AND** the current page is greater than 1
- **THEN** a "← Previous" action button is included in the message
- **AND** the button has name="navigate_page"
- **AND** the button payload includes `{"page": current_page - 1}`
- **AND** the button uses icon="arrow-left"

#### Scenario: No pagination buttons on single-page results
- **WHEN** card search results fit on a single page (total_count <= page_size)
- **THEN** no pagination action buttons are displayed
- **AND** the search results show only the card list
- **AND** the pagination info text indicates "Showing all X results"

#### Scenario: Both buttons on middle pages
- **WHEN** card search results are on page 3 of 5
- **THEN** both "← Previous" and "Next →" buttons are displayed
- **AND** the Previous button has payload `{"page": 2}`
- **AND** the Next button has payload `{"page": 4}`
- **AND** the buttons appear side-by-side or in logical order

#### Scenario: Pagination info text
- **WHEN** paginated search results are displayed
- **THEN** the message includes pagination info text
- **AND** the text shows "Showing page X of Y (Z total results)"
- **AND** the text appears below the card list
- **AND** the text is separate from the action buttons

### Requirement: Pagination Message Tracking
The system SHALL track pagination messages in user session to enable action button cleanup.

#### Scenario: Store pagination message reference
- **WHEN** search results with pagination buttons are displayed
- **THEN** the message reference is stored in user session with key "pagination_message"
- **AND** the reference can be retrieved in pagination action callbacks
- **AND** the reference is updated each time new paginated results are shown

#### Scenario: Clear old pagination buttons on new page
- **WHEN** the user navigates to a new page
- **AND** a previous pagination message exists in the session
- **THEN** the old message's action buttons are removed
- **AND** the new page's results are displayed with fresh action buttons
- **AND** only one set of pagination buttons is active at a time

### Requirement: Page Navigation Action Callback
The system SHALL process page navigation button clicks to display the requested page with preserved search filters.

#### Scenario: Navigate to next page
- **WHEN** the user clicks the "Next →" button
- **THEN** the `navigate_page` action callback is invoked
- **AND** the callback retrieves page number from `action.payload.get("page")`
- **AND** the callback retrieves search context from user session
- **AND** the callback removes action buttons from the previous pagination message
- **AND** the callback executes a new search with the same filters and new page number

#### Scenario: Navigate to previous page
- **WHEN** the user clicks the "← Previous" button
- **THEN** the `navigate_page` action callback is invoked
- **AND** the callback retrieves page number from `action.payload.get("page")`
- **AND** the callback retrieves search context from user session
- **AND** the callback executes a new search with preserved filters

#### Scenario: Search context preservation during navigation
- **WHEN** the user navigates pages
- **THEN** all original search filters are preserved (colors, types, keywords, etc.)
- **AND** the format filter active during the original search is maintained
- **AND** the games filter active during the original search is maintained
- **AND** the page size remains constant across navigation

#### Scenario: Display new page results
- **WHEN** the page navigation callback completes the search
- **THEN** the new page's card results are formatted and displayed
- **AND** new pagination buttons are shown with updated page number
- **AND** the pagination info text shows the new page number
- **AND** the new pagination message is stored in user session

#### Scenario: Missing search context handling
- **WHEN** the user clicks a pagination button
- **AND** the search context is not found in user session
- **THEN** an error message is sent "No active search. Please start a new search."
- **AND** the pagination buttons are removed
- **AND** the callback does NOT attempt to execute a search

#### Scenario: Invalid page number handling
- **WHEN** the pagination callback is invoked
- **AND** the page number in the payload is invalid (e.g., negative, non-integer)
- **THEN** an error message is sent "Invalid page number"
- **AND** the pagination buttons are removed
- **AND** the callback does NOT execute a search

#### Scenario: Search execution error handling
- **WHEN** the pagination callback executes a search
- **AND** the repository raises an exception
- **THEN** the error is caught and logged
- **AND** a user-friendly error message is sent "Error loading page {page}: {brief error}"
- **AND** the previous pagination buttons are NOT removed (user can retry)

### Requirement: Pagination Integration with Card Formatters
The system SHALL integrate pagination buttons into existing card list formatting logic without duplicating code.

#### Scenario: Card formatter includes pagination metadata
- **WHEN** the `format_card_list` function receives paginated results
- **THEN** the function accepts pagination metadata as parameters (page, total_pages, total_count)
- **AND** the function returns both formatted card list and pagination actions
- **AND** the function constructs pagination info text from metadata

#### Scenario: Card formatter works without pagination
- **WHEN** the `format_card_list` function receives non-paginated results
- **AND** pagination metadata is not provided or indicates single page
- **THEN** the function returns only the formatted card list
- **AND** no pagination actions are created
- **AND** the behavior is backward compatible with existing calls

#### Scenario: UI layer combines card list and pagination
- **WHEN** the UI layer displays search results
- **THEN** the card list and pagination actions are combined in a single `cl.Message`
- **AND** the message content includes the formatted card table
- **AND** the message actions include the pagination buttons
- **AND** the pagination info text appears in the message content

### Requirement: Backward Compatibility with Conversational Pagination
The system SHALL maintain support for conversational pagination commands alongside action-based navigation.

#### Scenario: Conversational "next page" command works
- **WHEN** a user types "show me the next page" or "next page" conversationally
- **AND** a search context exists in the session
- **THEN** the agent recognizes the pagination intent
- **AND** the agent invokes the search tool with incremented page number
- **AND** the behavior is identical to clicking the "Next →" button

#### Scenario: Conversational "previous page" command works
- **WHEN** a user types "show me the previous page" or "go back" conversationally
- **AND** a search context exists and current page > 1
- **THEN** the agent recognizes the pagination intent
- **AND** the agent invokes the search tool with decremented page number

#### Scenario: Conversational page number command works
- **WHEN** a user types "show me page 3" conversationally
- **AND** a search context exists
- **THEN** the agent recognizes the specific page request
- **AND** the agent invokes the search tool with the requested page number
- **AND** the search filters are preserved from the session context
