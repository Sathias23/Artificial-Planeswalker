## ADDED Requirements

### Requirement: Mana Curve Calculation

The system SHALL provide a `calculate_mana_curve()` function that computes the distribution of cards by mana value from a deck's card list.

#### Scenario: Calculate curve for 60-card deck

- **GIVEN** a deck with 12 lands, 8 one-drops, 12 two-drops, 10 three-drops, 8 four-drops, 6 five-drops, 3 six-drops, and 1 seven-drop
- **WHEN** `calculate_mana_curve(deck.deck_cards)` is called
- **THEN** the function SHALL return `{0: 12, 1: 8, 2: 12, 3: 10, 4: 8, 5: 6, 6: 3, 7: 1}`
- **AND** lands SHALL be tracked separately from non-land spells

#### Scenario: Calculate curve with 7+ CMC grouping

- **GIVEN** a deck with 2 cards at CMC 7, 1 card at CMC 8, and 1 card at CMC 10
- **WHEN** `calculate_mana_curve(deck.deck_cards)` is called
- **THEN** all cards with CMC ≥ 7 SHALL be grouped in bucket `7+`
- **AND** the result SHALL contain `{..., 7: 4}` (sum of CMC 7, 8, 10)

#### Scenario: Calculate curve for empty deck

- **GIVEN** a deck with 0 cards
- **WHEN** `calculate_mana_curve([])` is called
- **THEN** the function SHALL return `{0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0}`

#### Scenario: Exclude sideboard cards from curve

- **GIVEN** a deck with 8 two-drops in mainboard and 4 two-drops in sideboard
- **WHEN** `calculate_mana_curve(deck.deck_cards)` is called
- **THEN** only mainboard cards SHALL be included in the curve
- **AND** the result SHALL contain `{..., 2: 8, ...}` (sideboard excluded)

#### Scenario: Handle X-cost spells

- **GIVEN** a card "Fireball" with mana cost `{X}{R}` (CMC = 1 in Scryfall data)
- **WHEN** calculating curve for a deck containing Fireball
- **THEN** Fireball SHALL be counted at CMC 1 (non-X portion only)

### Requirement: Curve Analysis Function

The system SHALL provide an `analyze_curve()` function that evaluates a mana curve and returns structured analysis including problems, recommendations, and inferred archetype.

#### Scenario: Analyze balanced midrange curve

- **GIVEN** a curve `{0: 0, 1: 4, 2: 8, 3: 12, 4: 10, 5: 4, 6: 2, 7: 0}` with 20 lands
- **WHEN** `analyze_curve(curve, total_cards=60)` is called
- **THEN** the function SHALL return `CurveAnalysis` with:
  - `archetype = "midrange"`
  - `problems = []` (no problems detected)
  - `average_cmc` approximately 3.0

#### Scenario: Detect top-heavy curve

- **GIVEN** a curve with 25 cards at CMC 5+ out of 60 total cards (42%)
- **WHEN** `analyze_curve(curve, total_cards=60)` is called
- **THEN** `problems` SHALL include "Top-heavy curve: 42% of deck is 5+ mana (recommend < 30%)"

#### Scenario: Detect missing early plays

- **GIVEN** a curve with only 6 cards at CMC ≤ 2 out of 60 total (10%)
- **WHEN** `analyze_curve(curve, total_cards=60)` is called
- **THEN** `problems` SHALL include "Insufficient early plays: Only 10% of deck is ≤ 2 mana (recommend > 20%)"

#### Scenario: Detect insufficient lands

- **GIVEN** a deck with 60 total cards and 18 lands (30%)
- **WHEN** `analyze_curve(curve, total_cards=60, land_count=18)` is called
- **THEN** `problems` SHALL include "Low land count: 18 lands (30%). Recommend 22-26 for 60-card deck."

#### Scenario: Detect mana flood risk

- **GIVEN** a deck with 60 total cards and 30 lands (50%)
- **WHEN** `analyze_curve(curve, total_cards=60, land_count=30)` is called
- **THEN** `problems` SHALL include "Excessive lands: 30 lands (50%). Risk of mana flood."

### Requirement: Archetype Inference

The system SHALL provide an `infer_archetype()` function that determines deck archetype (aggro, midrange, control) based on average CMC.

#### Scenario: Infer aggro archetype

- **GIVEN** a curve with average CMC of 2.2
- **WHEN** `infer_archetype(curve)` is called
- **THEN** the function SHALL return `"aggro"`

#### Scenario: Infer midrange archetype

- **GIVEN** a curve with average CMC of 3.1
- **WHEN** `infer_archetype(curve)` is called
- **THEN** the function SHALL return `"midrange"`

#### Scenario: Infer control archetype

- **GIVEN** a curve with average CMC of 4.2
- **WHEN** `infer_archetype(curve)` is called
- **THEN** the function SHALL return `"control"`

#### Scenario: Boundary case - midrange/control threshold

- **GIVEN** a curve with average CMC of exactly 3.5
- **WHEN** `infer_archetype(curve)` is called
- **THEN** the function SHALL return `"midrange"` (inclusive of lower bound)

### Requirement: Ideal Curve Recommendations

The system SHALL provide a `suggest_ideal_curve()` function that returns archetype-specific curve recommendations.

#### Scenario: Aggro deck recommendations

- **GIVEN** archetype is "aggro"
- **WHEN** `suggest_ideal_curve("aggro")` is called
- **THEN** recommendations SHALL include:
  - "60-70% of spells at CMC ≤ 3"
  - "Multiple 1-drops for consistent early pressure"
  - "Peak at CMC 2"
  - "22-24 lands typical for aggressive strategies"

#### Scenario: Midrange deck recommendations

- **GIVEN** archetype is "midrange"
- **WHEN** `suggest_ideal_curve("midrange")` is called
- **THEN** recommendations SHALL include:
  - "Bell curve peaking at CMC 3-4"
  - "Balanced distribution across CMC 2-5"
  - "24-26 lands for consistent curve-outs"

#### Scenario: Control deck recommendations

- **GIVEN** archetype is "control"
- **WHEN** `suggest_ideal_curve("control")` is called
- **THEN** recommendations SHALL include:
  - "50-60% of spells at CMC 3-6"
  - "Fewer 1-2 drops, prioritize card advantage and interaction"
  - "26-28 lands to hit land drops consistently"

### Requirement: Analyze Mana Curve Agent Tool

The system SHALL provide an `analyze_mana_curve` PydanticAI tool that enables users to request curve analysis through natural language queries.

#### Scenario: User requests curve analysis

- **GIVEN** a user has an active deck loaded
- **WHEN** the user sends message "analyze my mana curve"
- **THEN** the agent SHALL invoke `analyze_mana_curve` tool
- **AND** fetch the active deck from `AgentDependencies.deck_repository`
- **AND** return formatted curve analysis with chart, statistics, problems, and recommendations

#### Scenario: Analyze curve with no active deck

- **GIVEN** no active deck is loaded (session has no `active_deck_id`)
- **WHEN** user requests "analyze my mana curve"
- **THEN** the agent SHALL return error message "No active deck. Please create or load a deck first."

#### Scenario: Natural language variations

- **GIVEN** a user has an active deck loaded
- **WHEN** the user sends any of:
  - "is my curve good?"
  - "check my mana curve"
  - "how does my curve look?"
  - "analyze curve"
- **THEN** the agent SHALL invoke `analyze_mana_curve` tool in all cases

#### Scenario: Curve analysis includes land count

- **GIVEN** a deck with 60 cards including 24 lands
- **WHEN** `analyze_mana_curve` tool executes
- **THEN** the analysis SHALL include land count and percentage
- **AND** evaluate land count against archetype recommendations

### Requirement: Mana Curve Visualization Formatter

The system SHALL provide a `format_mana_curve()` function that renders curve analysis as formatted markdown text suitable for Chainlit display.

#### Scenario: Format curve as markdown table

- **GIVEN** a `CurveAnalysis` object with distribution `{0: 0, 1: 8, 2: 12, 3: 10, 4: 6, 5: 3, 6: 1, 7: 0}`
- **WHEN** `format_mana_curve(analysis)` is called
- **THEN** the output SHALL be a markdown table with columns: CMC, Count, % of Deck, Chart
- **AND** each row SHALL include a horizontal bar chart using block characters (▮)

#### Scenario: Bar chart scaling

- **GIVEN** a curve with maximum count of 12 cards at any CMC
- **WHEN** `format_mana_curve(analysis)` is called
- **THEN** bar chart SHALL scale to fit readable width
- **AND** 12 cards SHALL render as maximum bar width (e.g., 12 blocks)
- **AND** other CMCs SHALL scale proportionally

#### Scenario: Include summary statistics

- **GIVEN** a `CurveAnalysis` with average CMC 2.8, 60 total cards, 24 lands
- **WHEN** `format_mana_curve(analysis)` is called
- **THEN** formatted output SHALL include:
  - Total Cards: 60
  - Average CMC: 2.8
  - Lands: 24 (40%)
  - Inferred Archetype: midrange

#### Scenario: Display problems and recommendations

- **GIVEN** a `CurveAnalysis` with detected problems and archetype recommendations
- **WHEN** `format_mana_curve(analysis)` is called
- **THEN** formatted output SHALL include:
  - "⚠️ Problems Detected:" section (if problems exist)
  - List of detected problems
  - "💡 Recommendations:" section
  - Archetype-specific suggestions

#### Scenario: Format curve with no problems

- **GIVEN** a `CurveAnalysis` with `problems = []`
- **WHEN** `format_mana_curve(analysis)` is called
- **THEN** formatted output SHALL include "✅ No curve problems detected!"
- **AND** still display archetype recommendations

### Requirement: CurveAnalysis Data Structure

The system SHALL define a `CurveAnalysis` dataclass or Pydantic model containing curve distribution, detected problems, recommendations, and metadata.

#### Scenario: CurveAnalysis structure

- **GIVEN** the `CurveAnalysis` class definition
- **WHEN** inspecting the class
- **THEN** it SHALL contain fields:
  - `distribution: dict[int, int]` - Card count by CMC bucket
  - `problems: list[str]` - Detected curve issues
  - `recommendations: list[str]` - Archetype-specific advice
  - `archetype: str` - Inferred or specified archetype
  - `average_cmc: float` - Average converted mana cost
  - `total_cards: int` - Total non-land cards
  - `land_count: int` - Number of lands

#### Scenario: CurveAnalysis validation

- **GIVEN** creating a `CurveAnalysis` instance
- **WHEN** `CurveAnalysis(distribution={...}, problems=[], ...)` is instantiated
- **THEN** all fields SHALL be type-checked
- **AND** invalid types SHALL raise Pydantic `ValidationError`

### Requirement: Unit Tests for Mana Curve Logic

The system SHALL provide comprehensive unit tests for all mana curve functions achieving 90%+ coverage.

#### Scenario: Test calculate_mana_curve with various deck compositions

- **GIVEN** unit tests with mocked DeckCard lists
- **WHEN** testing `calculate_mana_curve()` with aggro, midrange, control deck compositions
- **THEN** correct distributions SHALL be returned
- **AND** 7+ CMC grouping SHALL be validated

#### Scenario: Test analyze_curve problem detection

- **GIVEN** unit tests with various curve distributions
- **WHEN** testing `analyze_curve()` with top-heavy, land-light, and balanced curves
- **THEN** correct problems SHALL be detected for each scenario
- **AND** no false positives SHALL occur for balanced curves

#### Scenario: Test archetype inference boundary cases

- **GIVEN** unit tests for archetype inference
- **WHEN** testing with average CMCs at exact thresholds (2.5, 3.5)
- **THEN** consistent archetype classification SHALL occur
- **AND** edge cases SHALL be handled deterministically

#### Scenario: Test ideal curve recommendations

- **GIVEN** unit tests for each archetype
- **WHEN** testing `suggest_ideal_curve()` for aggro, midrange, control
- **THEN** archetype-specific recommendations SHALL be returned
- **AND** recommendations SHALL be actionable and specific

### Requirement: Integration Tests for Analyze Mana Curve Tool

The system SHALL provide integration tests validating end-to-end curve analysis through the agent tool.

#### Scenario: End-to-end curve analysis with real deck

- **GIVEN** an integration test with test database and sample deck
- **WHEN** invoking `analyze_mana_curve` tool via agent
- **THEN** tool SHALL fetch deck from repository
- **AND** calculate curve correctly
- **AND** return formatted markdown output

#### Scenario: Tool error handling for missing deck

- **GIVEN** an integration test with no active deck
- **WHEN** invoking `analyze_mana_curve` tool
- **THEN** tool SHALL handle missing deck gracefully
- **AND** return user-friendly error message

#### Scenario: Tool integration with agent dependencies

- **GIVEN** an integration test with `AgentDependencies` container
- **WHEN** invoking tool with dependencies
- **THEN** tool SHALL access `deck_repository` correctly
- **AND** use `active_deck_id` from session state
