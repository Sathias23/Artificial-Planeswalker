# Agent Tools Spec Deltas

## ADDED Requirements

### Requirement: AI-Curated Card Suggestions

The agent SHALL provide intelligent card suggestions using LLM analysis combined with database validation.

#### Scenario: Successful suggestion workflow

- **GIVEN** user has active deck with 15 Goblin creatures and detected tribal synergy
- **WHEN** user requests card suggestions via natural language ("What cards would work well in my deck?")
- **THEN** agent invokes `suggest_synergy_cards()` tool
- **AND** Stage 1: Analysis agent generates structured deck needs (DeckAnalysis model)
- **AND** Stage 2: Database searches execute 3-5 parallel queries based on analysis
- **AND** Stage 2: Returns 50-150 unique candidate cards (default 75, configurable)
- **AND** Stage 3: Curation agent evaluates candidates and selects best 5-7 cards (CardSuggestions model)
- **AND** Validation filters suggestions to only cards present in candidate list
- **AND** Formatted output includes card names, explanations, priority rankings (1-5), and overall strategy
- **AND** All suggested cards are actual Goblin creatures or Goblin-matters cards (no hallucinations)
- **AND** All suggested cards are format-legal per active format filter

#### Scenario: Format filter enforcement

- **GIVEN** user has active Standard deck (format="standard")
- **WHEN** user requests card suggestions
- **THEN** Stage 2 database searches use `format_filter="standard"` parameter
- **AND** All 75 candidate cards have `legalities.standard = "legal"`
- **AND** All final suggestions are Standard-legal
- **AND** Formatted output includes note: "(Showing Standard-legal cards only)"

#### Scenario: Parallel database searches

- **GIVEN** analysis agent generates 4 deck need analyses
- **WHEN** Stage 2 executes candidate search
- **THEN** 4 database queries run in parallel via `asyncio.gather()`
- **AND** Total search time ≈ max(individual query times), not sum
- **AND** Target latency: <1 second for all 4 searches combined
- **AND** Results are deduplicated by card name across queries

#### Scenario: Hallucination prevention

- **GIVEN** curation agent suggests 7 cards in response
- **WHEN** 2 suggested card names do not exist in the 75-card candidate list
- **THEN** validation logic filters suggestions against candidate list
- **AND** Invalid suggestions are excluded (logged as warnings)
- **AND** Returns only 5 validated suggestions to user
- **AND** User never sees hallucinated (non-existent) card names

#### Scenario: LLM analysis failure

- **GIVEN** Stage 1 analysis agent call times out or returns invalid JSON
- **WHEN** `suggest_synergy_cards()` tool processes request
- **THEN** Exception is caught and logged with details
- **AND** Returns user-friendly error message: "Unable to analyze deck for suggestions. Please try again."
- **AND** Does not expose internal error details to user
- **AND** Does not proceed to Stage 2 or Stage 3

#### Scenario: No candidates found

- **GIVEN** analysis agent generates valid search criteria
- **WHEN** Stage 2 database searches return 0 results (restrictive format + narrow criteria)
- **THEN** Tool returns message: "No matching cards found in [format]. Try adjusting your deck composition or format filter."
- **AND** Does not proceed to Stage 3 (curation)

#### Scenario: Configurable candidate pool size

- **GIVEN** default candidate pool size is 75 cards
- **WHEN** Stage 2 calculates per-search limits
- **THEN** Divides 75 by number of analyses (3-5) → 15-25 cards per search
- **AND** If 3 analyses: 25 cards each × 3 = ~75 total after deduplication
- **AND** If 5 analyses: 15 cards each × 5 = ~75 total after deduplication
- **AND** Configuration allows range: 50-150 candidates (internal parameter)
- **AND** Values outside range are clamped: min(150, max(50, value))

#### Scenario: Structured outputs enforce type safety

- **GIVEN** analysis agent is configured with `output_type=DeckAnalysis`
- **WHEN** analysis agent completes LLM call
- **THEN** Response is automatically parsed to DeckAnalysis Pydantic model
- **AND** Model validation ensures: `primary_synergy` is non-empty string
- **AND** Model validation ensures: `search_criteria` is dict with valid keys
- **AND** Model validation ensures: `reasoning` is non-empty string
- **AND** Invalid responses raise ValidationError (caught and handled gracefully)

#### Scenario: Curation agent structured output

- **GIVEN** curation agent is configured with `output_type=CardSuggestions`
- **WHEN** curation agent completes LLM call
- **THEN** Response is automatically parsed to CardSuggestions Pydantic model
- **AND** Model validation ensures: `top_picks` list has 5-7 items
- **AND** Model validation ensures: Each pick has `priority` between 1-5
- **AND** Model validation ensures: Each pick has non-empty `synergy_fit` explanation
- **AND** Model validation ensures: `overall_strategy` is non-empty string

#### Scenario: Natural language intent detection

- **GIVEN** user types one of the following queries:
  - "What cards should I add to my Goblin deck?"
  - "Suggest cards for my deck"
  - "What would work well in my deck?"
  - "Recommend cards to improve my strategy"
  - "Find cards that fit my deck"
- **WHEN** main agent processes user input
- **THEN** Agent detects card suggestion intent
- **AND** Invokes `suggest_synergy_cards()` tool
- **AND** Returns contextual suggestions based on active deck

#### Scenario: Performance within budget

- **GIVEN** typical request (60-card deck, 3 detected synergies)
- **WHEN** full suggestion workflow executes
- **THEN** Stage 1 (analysis) completes in <5 seconds
- **AND** Stage 2 (search) completes in <1 second
- **AND** Stage 3 (curation) completes in <7 seconds
- **AND** Total latency is <10 seconds (acceptable for on-demand feature)
- **AND** Total token usage is <20,000 tokens per request
- **AND** Estimated API cost is ~$0.02 per request

#### Scenario: Fallback on curation failure

- **GIVEN** Stage 3 curation agent fails or all suggestions are invalid
- **WHEN** validation detects zero valid suggestions
- **THEN** Fallback mechanism activates
- **AND** Returns top 5 candidates sorted by mana_value (lowest first)
- **AND** Each fallback suggestion has generic explanation: "[Card name] is a format-legal card that may complement your deck."
- **AND** Each fallback suggestion has priority=3 (medium)
- **AND** Fallback is logged for debugging
- **AND** User still receives suggestions (graceful degradation)
