# deck-intelligence Specification

## Purpose
TBD - created by archiving change add-mana-curve-analysis. Update Purpose after archive.
## Requirements
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

### Requirement: Contextual Curve Feedback Generation

The system SHALL provide a `generate_contextual_feedback()` function that generates appropriate mana curve feedback messages when cards are added to a deck, balancing helpfulness with brevity to avoid feedback fatigue.

#### Scenario: Generate positive reinforcement for good addition

- **GIVEN** a deck with inferred archetype "aggro" and average CMC 3.2 (slightly high)
- **AND** a user adds a 1-mana creature (e.g., "Monastery Swiftspear")
- **WHEN** `generate_contextual_feedback(deck, added_card)` is called
- **THEN** the function SHALL return positive feedback
- **AND** message like "Great addition! Strong early-game presence helps your aggressive strategy."

#### Scenario: Generate warning for top-heavy addition

- **GIVEN** a deck with 60 total cards and 18 cards at CMC 5+ (30%)
- **AND** a user adds a 6-mana card (e.g., "Titan of Industry")
- **WHEN** `generate_contextual_feedback(deck, added_card)` is called
- **THEN** the function SHALL return warning feedback
- **AND** message like "Your deck is getting top-heavy. Consider adding more 1-3 mana plays for early-game consistency."

#### Scenario: Skip feedback for insignificant curve changes

- **GIVEN** a deck with 30 cards and balanced curve distribution
- **AND** a user adds a 3-mana card that doesn't shift any CMC bucket by > 15%
- **WHEN** `generate_contextual_feedback(deck, added_card)` is called
- **THEN** the function SHALL return None (no feedback)
- **AND** avoid overwhelming user with feedback on every single addition

#### Scenario: Generate feedback for early deck construction

- **GIVEN** a deck with fewer than 5 cards
- **AND** a user adds any card
- **WHEN** `generate_contextual_feedback(deck, added_card)` is called
- **THEN** the function SHALL return feedback (even if change is small)
- **AND** help guide initial deck direction

#### Scenario: Detect missing early plays

- **GIVEN** a deck with 40 cards and only 3 cards at CMC ≤ 2 (7.5%)
- **AND** a user adds a 4-mana card
- **WHEN** `generate_contextual_feedback(deck, added_card)` is called
- **THEN** the function SHALL return warning feedback
- **AND** message like "You have very few early plays (7.5% at ≤ 2 mana). Consider adding more low-cost cards."

#### Scenario: Neutral observation for balanced addition

- **GIVEN** a deck with healthy curve distribution (no problems)
- **AND** a user adds a card that maintains curve balance
- **WHEN** `generate_contextual_feedback(deck, added_card)` is called
- **THEN** the function MAY return neutral observation
- **AND** message like "Curve remains balanced across 2-4 mana." (optional, not on every addition)

### Requirement: Feedback Throttling Strategy

The system SHALL implement a throttling strategy that determines when curve feedback should be generated, preventing feedback fatigue while providing guidance at critical moments.

#### Scenario: Throttle based on curve distribution shift

- **GIVEN** a deck before and after adding a card
- **WHEN** evaluating whether to generate feedback
- **THEN** feedback SHALL be generated IF any of:
  - Deck has < 5 cards (early construction)
  - Any CMC bucket changes by > 15% of total deck
  - New curve problems detected (e.g., top-heavy threshold crossed)
  - Existing problems resolved (e.g., early plays added)

#### Scenario: Skip feedback for incremental additions

- **GIVEN** a 50-card deck with balanced curve
- **WHEN** a user adds a card that shifts CMC buckets by < 10%
- **THEN** feedback SHALL NOT be generated
- **AND** user autonomy is preserved

#### Scenario: Always feedback on first card

- **GIVEN** a new empty deck
- **WHEN** a user adds the first card
- **THEN** feedback SHALL be generated
- **AND** establish tone of proactive guidance

### Requirement: Archetype-Aware Feedback

The system SHALL generate feedback that considers the inferred deck archetype (aggro, midrange, control) when evaluating card additions.

#### Scenario: Aggro deck low-drop validation

- **GIVEN** a deck with inferred archetype "aggro" (average CMC 2.5)
- **AND** a user adds a 5-mana card
- **WHEN** `generate_contextual_feedback(deck, added_card)` is called
- **THEN** feedback SHALL warn about high CMC for aggressive strategy
- **AND** message like "5-mana cards are risky in aggressive decks. Ensure you have enough early pressure."

#### Scenario: Control deck high-cost acceptance

- **GIVEN** a deck with inferred archetype "control" (average CMC 4.0)
- **AND** a user adds a 6-mana finisher
- **WHEN** `generate_contextual_feedback(deck, added_card)` is called
- **THEN** feedback SHALL recognize appropriate archetype fit
- **AND** message like "Strong finisher for a control deck. Make sure you have early interaction to reach late game."

#### Scenario: Midrange balanced curve enforcement

- **GIVEN** a deck with inferred archetype "midrange" (average CMC 3.2)
- **AND** a user adds a 2-mana card maintaining bell curve
- **WHEN** `generate_contextual_feedback(deck, added_card)` is called
- **THEN** feedback MAY acknowledge curve balance
- **AND** message like "Solid midrange curve shaping up." (if feedback threshold met)

### Requirement: Feedback Tone and Style

The system SHALL generate feedback using conversational, coaching tone rather than authoritative or prescriptive language.

#### Scenario: Use suggestive language

- **GIVEN** any feedback generation scenario
- **WHEN** constructing warning or recommendation messages
- **THEN** messages SHALL use suggestive phrasing like:
  - "Consider adding..."
  - "You might want to..."
  - "Your deck could benefit from..."
- **AND** avoid prescriptive commands like:
  - "You must add..." ❌
  - "Remove..." ❌
  - "You should..." ❌

#### Scenario: Maintain conversational tone

- **GIVEN** any feedback generation scenario
- **WHEN** messages are constructed
- **THEN** tone SHALL feel like advice from an experienced deck builder
- **AND** avoid robotic or overly formal language
- **AND** use contractions and natural phrasing where appropriate

#### Scenario: Balance criticism with support

- **GIVEN** feedback identifies a curve problem
- **WHEN** generating warning message
- **THEN** message SHALL identify the issue clearly
- **AND** suggest actionable improvement
- **AND** maintain encouraging tone (not discouraging)

### Requirement: Feedback Data Structure

The system SHALL define a `CurveFeedback` dataclass or Pydantic model containing feedback message, feedback type, and metadata.

#### Scenario: CurveFeedback structure

- **GIVEN** the `CurveFeedback` class definition
- **WHEN** inspecting the class
- **THEN** it SHALL contain fields:
  - `message: str` - Human-readable feedback text
  - `feedback_type: Literal["positive", "warning", "neutral"]` - Feedback classification
  - `triggered_by: str` - Reason for feedback (e.g., "top_heavy", "early_plays_added")
  - `should_display: bool` - Whether throttling logic says to show this feedback

#### Scenario: CurveFeedback validation

- **GIVEN** creating a `CurveFeedback` instance
- **WHEN** `CurveFeedback(message="...", feedback_type="positive", ...)` is instantiated
- **THEN** all fields SHALL be type-checked
- **AND** `feedback_type` SHALL be constrained to valid values ("positive", "warning", "neutral")
- **AND** invalid types SHALL raise Pydantic `ValidationError`

### Requirement: Unit Tests for Contextual Feedback

The system SHALL provide comprehensive unit tests for contextual feedback logic achieving 90%+ coverage.

#### Scenario: Test feedback generation for various scenarios

- **GIVEN** unit tests with mocked decks at various stages of construction
- **WHEN** testing `generate_contextual_feedback()` with aggro, midrange, control deck additions
- **THEN** appropriate feedback messages SHALL be returned
- **AND** positive, warning, and neutral feedback types SHALL be tested

#### Scenario: Test throttling logic

- **GIVEN** unit tests with decks before and after card additions
- **WHEN** testing throttling strategy with various curve distribution shifts
- **THEN** feedback SHALL be generated only when thresholds are met
- **AND** insignificant changes SHALL return None

#### Scenario: Test archetype-aware feedback

- **GIVEN** unit tests with decks of different archetypes
- **WHEN** testing feedback for same card additions to aggro vs control decks
- **THEN** feedback SHALL differ based on archetype context
- **AND** aggro deck SHALL warn about high CMC cards more aggressively

#### Scenario: Test feedback tone

- **GIVEN** unit tests for all feedback scenarios
- **WHEN** inspecting generated messages
- **THEN** messages SHALL use suggestive language ("consider", "might want")
- **AND** avoid prescriptive commands ("must", "should")
- **AND** maintain conversational tone

### Requirement: Synergy Detection Function

The system SHALL provide a `detect_synergies()` function that analyzes a deck's card list and returns detected synergy patterns including tribal synergies, keyword synergies, and mechanic combos.

#### Scenario: Detect Goblin tribal synergy

- **GIVEN** a deck with 12 Goblin creature cards (e.g., "Goblin Guide", "Goblin Chieftain", "Legion Warchief")
- **AND** 2 Goblin tribal payoff cards (e.g., "Goblin King" with "Other Goblins you control get +1/+1")
- **WHEN** `detect_synergies(deck.deck_cards)` is called
- **THEN** the function SHALL return a `SynergyAnalysis` containing:
  - `pattern_type = "tribal"`
  - `tribe = "Goblin"`
  - `affected_cards` list with all 14 Goblin-related cards
  - `explanation = "12 Goblin creatures synergize with 2 tribal payoff cards (Goblin King, etc.)"`
  - `strength = "strong"` (>30% of deck)

#### Scenario: Detect flying keyword synergy

- **GIVEN** a deck with 8 creatures with flying keyword
- **AND** 2 cards that care about flying (e.g., "Favorable Winds": "Creatures you control with flying get +1/+1")
- **WHEN** `detect_synergies(deck.deck_cards)` is called
- **THEN** the function SHALL return a synergy with:
  - `pattern_type = "keyword"`
  - `keyword = "flying"`
  - `affected_cards` list with 10 cards (8 creatures + 2 payoffs)
  - `explanation = "8 creatures with flying benefit from 2 flying-matters cards (Favorable Winds, etc.)"`
  - `strength = "moderate"` (10-30% of deck)

#### Scenario: Detect sacrifice combo synergy

- **GIVEN** a deck with 4 sacrifice outlets (e.g., "Witch's Oven", "Carrion Feeder")
- **AND** 6 cards with death/sacrifice triggers (e.g., "Cauldron Familiar": "When Cauldron Familiar dies, each opponent loses 1 life")
- **WHEN** `detect_synergies(deck.deck_cards)` is called
- **THEN** the function SHALL return a synergy with:
  - `pattern_type = "mechanic_combo"`
  - `mechanic = "sacrifice"`
  - `affected_cards` list with 10 cards
  - `explanation = "4 sacrifice outlets enable 6 cards with death/sacrifice triggers"`
  - `strength = "moderate"`

#### Scenario: Detect multiple synergy patterns in same deck

- **GIVEN** a deck with both Goblin tribal synergies AND sacrifice combo synergies
- **WHEN** `detect_synergies(deck.deck_cards)` is called
- **THEN** the function SHALL return a `SynergyAnalysis` with `synergies` list containing 2+ patterns
- **AND** each pattern SHALL be independently detected and explained

#### Scenario: No synergies in goodstuff deck

- **GIVEN** a deck with 60 cards from various strategies with no cohesive theme
- **AND** no repeated creature types, no keyword-matters cards, no obvious combos
- **WHEN** `detect_synergies(deck.deck_cards)` is called
- **THEN** the function SHALL return a `SynergyAnalysis` with `synergies = []`
- **AND** `total_count = 0`

#### Scenario: Weak synergy threshold filtering

- **GIVEN** a deck with only 2 Elf creatures (< 5% of deck)
- **AND** 1 Elf tribal payoff card
- **WHEN** `detect_synergies(deck.deck_cards)` is called
- **THEN** the function SHALL NOT return an Elf tribal synergy (too weak to be meaningful)
- **AND** only synergies meeting minimum thresholds SHALL be reported

### Requirement: Tribal Synergy Detection

The system SHALL detect tribal synergies by extracting creature types from card type lines, counting occurrences, and identifying tribal payoff cards that care about specific creature types.

#### Scenario: Extract creature types from type line

- **GIVEN** a card "Goblin Guide" with `type_line = "Creature — Goblin Scout"`
- **WHEN** extracting creature types for synergy detection
- **THEN** the function SHALL identify ["Goblin", "Scout"] as creature types
- **AND** ignore card types (Creature, Legendary, etc.)

#### Scenario: Identify tribal payoff cards

- **GIVEN** a card "Goblin King" with oracle text "Other Goblin creatures you control get +1/+1 and have mountainwalk"
- **WHEN** analyzing for tribal payoffs
- **THEN** the function SHALL identify this as a Goblin tribal payoff card
- **AND** match oracle text patterns like "Goblin creatures", "other Goblins", "Goblin you control"

#### Scenario: Count tribal density

- **GIVEN** a 60-card deck with 18 Elf creatures and 3 Elf tribal payoff cards
- **WHEN** calculating tribal synergy strength
- **THEN** tribal density SHALL be 21/60 = 35%
- **AND** strength SHALL be classified as "strong" (>30%)

#### Scenario: Multi-tribe deck detection

- **GIVEN** a deck with 10 Elves and 8 Goblins
- **WHEN** `detect_synergies()` is called
- **THEN** the function SHALL detect BOTH Elf tribal and Goblin tribal patterns separately
- **AND** each SHALL be evaluated independently for strength

#### Scenario: Minimum threshold for tribal synergy

- **GIVEN** a deck with 4 Goblin creatures (< 10% of deck)
- **WHEN** evaluating tribal synergies
- **THEN** the function SHALL require minimum 5 creatures of same type
- **AND** synergies below threshold SHALL NOT be reported

### Requirement: Keyword Synergy Detection

The system SHALL detect keyword synergies by identifying keyword abilities on creatures and finding cards that care about those keywords.

#### Scenario: Detect lifelink synergy

- **GIVEN** a deck with 6 creatures with lifelink keyword
- **AND** 2 cards that care about lifegain (e.g., "Ajani's Pridemate": "Whenever you gain life, put a +1/+1 counter on Ajani's Pridemate")
- **WHEN** `detect_synergies()` is called
- **THEN** the function SHALL detect a lifelink synergy
- **AND** explanation SHALL mention lifegain triggers benefiting from lifelink creatures

#### Scenario: Extract keywords from oracle text

- **GIVEN** a card "Serra Angel" with oracle text "Flying, vigilance"
- **WHEN** extracting keywords for synergy detection
- **THEN** the function SHALL identify ["flying", "vigilance"] as keywords
- **AND** handle comma-separated keyword lists

#### Scenario: Match keyword-matters cards

- **GIVEN** a card "Gravitational Shift" with oracle text "Creatures with flying get +2/+0. Creatures without flying get -2/-0."
- **WHEN** analyzing for keyword synergies
- **THEN** the function SHALL identify this as a flying-matters card
- **AND** match oracle text patterns like "with flying", "creatures with [keyword]", "[keyword] you control"

#### Scenario: Detect multiple keyword synergies

- **GIVEN** a deck with flying synergies (8 creatures + 2 payoffs) AND lifelink synergies (6 creatures + 2 payoffs)
- **WHEN** `detect_synergies()` is called
- **THEN** the function SHALL detect BOTH keyword synergies separately
- **AND** each SHALL have independent affected_cards lists

#### Scenario: Common keywords to detect

- **GIVEN** the keyword synergy detection implementation
- **WHEN** reviewing supported keywords
- **THEN** the function SHALL support common keywords including:
  - flying, lifelink, deathtouch, trample, vigilance, first strike, double strike
  - menace, reach, haste, hexproof, indestructible
- **AND** be extensible for future keyword additions

### Requirement: Mechanic Combo Detection

The system SHALL detect mechanic combo synergies by identifying card pairs or groups that enable powerful interactions such as sacrifice combos, card draw engines, and graveyard synergies.

#### Scenario: Detect sacrifice combo

- **GIVEN** a deck with 3 sacrifice outlets (e.g., "Witch's Oven": "Sacrifice a creature: Create a Food token")
- **AND** 5 cards with death triggers (e.g., "Cauldron Familiar": "When Cauldron Familiar dies, each opponent loses 1 life")
- **WHEN** `detect_synergies()` is called
- **THEN** the function SHALL detect a sacrifice mechanic combo
- **AND** explanation SHALL describe how sacrifice outlets enable death trigger cards

#### Scenario: Detect graveyard synergy

- **GIVEN** a deck with 4 self-mill cards (e.g., "Stitcher's Supplier": "When Stitcher's Supplier enters or dies, mill three cards")
- **AND** 6 cards that benefit from full graveyard (e.g., "Grim Flayer": "Delirium — Grim Flayer gets +2/+2 as long as there are four or more card types among cards in your graveyard")
- **WHEN** `detect_synergies()` is called
- **THEN** the function SHALL detect a graveyard mechanic combo
- **AND** explanation SHALL describe how self-mill enables graveyard payoffs

#### Scenario: Detect card draw + discard combo

- **GIVEN** a deck with 3 repeated card draw engines (e.g., "Phyrexian Arena": "At the beginning of your upkeep, you draw a card and you lose 1 life")
- **AND** 4 cards that benefit from discarding (e.g., "Bone Miser": "Whenever you discard a creature card, create a 2/2 black Zombie creature token")
- **WHEN** `detect_synergies()` is called
- **THEN** the function SHALL detect a card advantage mechanic combo
- **AND** identify the synergy between drawing extra cards and discard payoffs

#### Scenario: Pattern matching for mechanic combos

- **GIVEN** the mechanic combo detection implementation
- **WHEN** analyzing cards for combos
- **THEN** the function SHALL use pattern matching on oracle text for:
  - Sacrifice: "sacrifice" + "when [card] dies", "when [card] is put into graveyard"
  - Graveyard: "mill", "put cards into graveyard" + "delirium", "threshold", "card in graveyard"
  - Card draw: "draw" + "discard", "madness", "when you discard"
- **AND** patterns SHALL be case-insensitive

#### Scenario: Minimum threshold for mechanic combos

- **GIVEN** a deck with 1 sacrifice outlet and 2 death trigger cards (3 total)
- **WHEN** evaluating mechanic combos
- **THEN** the function SHALL require minimum 4 cards total in combo (2 enablers + 2 payoffs OR 1 enabler + 3 payoffs)
- **AND** synergies below threshold SHALL NOT be reported

### Requirement: SynergyPattern Data Structure

The system SHALL define a `SynergyPattern` dataclass or Pydantic model containing pattern type, affected cards, explanation, and strength classification.

#### Scenario: SynergyPattern structure

- **GIVEN** the `SynergyPattern` class definition
- **WHEN** inspecting the class
- **THEN** it SHALL contain fields:
  - `pattern_type: Literal["tribal", "keyword", "mechanic_combo"]` - Type of synergy
  - `subtype: str` - Specific tribe, keyword, or mechanic name (e.g., "Goblin", "flying", "sacrifice")
  - `affected_cards: list[str]` - Card names involved in synergy
  - `explanation: str` - Human-readable description of synergy
  - `strength: Literal["weak", "moderate", "strong"]` - Synergy density classification

#### Scenario: Strength classification thresholds

- **GIVEN** a synergy with `affected_cards` list
- **WHEN** classifying synergy strength
- **THEN** strength SHALL be determined by percentage of deck:
  - "strong": >30% of deck involved in synergy
  - "moderate": 10-30% of deck
  - "weak": <10% of deck (typically filtered out)

#### Scenario: SynergyPattern validation

- **GIVEN** creating a `SynergyPattern` instance
- **WHEN** `SynergyPattern(pattern_type="tribal", subtype="Goblin", ...)` is instantiated
- **THEN** all fields SHALL be type-checked
- **AND** `pattern_type` SHALL be constrained to valid values
- **AND** invalid types SHALL raise Pydantic `ValidationError`

### Requirement: SynergyAnalysis Data Structure

The system SHALL define a `SynergyAnalysis` dataclass or Pydantic model containing a list of detected synergy patterns and summary statistics.

#### Scenario: SynergyAnalysis structure

- **GIVEN** the `SynergyAnalysis` class definition
- **WHEN** inspecting the class
- **THEN** it SHALL contain fields:
  - `synergies: list[SynergyPattern]` - Detected synergy patterns
  - `total_count: int` - Number of synergies detected
  - `deck_cohesion: Literal["low", "moderate", "high"]` - Overall deck synergy assessment

#### Scenario: Calculate deck cohesion

- **GIVEN** a `SynergyAnalysis` with 3 detected synergies covering 45% of deck cards
- **WHEN** calculating `deck_cohesion`
- **THEN** cohesion SHALL be "high" (multiple synergies, >40% coverage)

#### Scenario: Deck cohesion thresholds

- **GIVEN** synergy detection results
- **WHEN** classifying deck cohesion
- **THEN** cohesion SHALL be determined by:
  - "high": 2+ synergies covering >40% of deck OR 1 strong synergy >50%
  - "moderate": 1-2 synergies covering 20-40% of deck
  - "low": 0-1 synergies covering <20% of deck

#### Scenario: SynergyAnalysis validation

- **GIVEN** creating a `SynergyAnalysis` instance
- **WHEN** `SynergyAnalysis(synergies=[...], total_count=2, ...)` is instantiated
- **THEN** all fields SHALL be type-checked
- **AND** `total_count` SHALL match `len(synergies)`
- **AND** invalid data SHALL raise Pydantic `ValidationError`

### Requirement: Detect Synergies Agent Tool

The system SHALL provide a `detect_synergies` PydanticAI tool that enables users to request synergy analysis through natural language queries.

#### Scenario: User requests synergy analysis

- **GIVEN** a user has an active deck loaded
- **WHEN** the user sends message "what synergies does my deck have?"
- **THEN** the agent SHALL invoke `detect_synergies` tool
- **AND** fetch the active deck from `AgentDependencies.deck_repository`
- **AND** return formatted synergy analysis with detected patterns and explanations

#### Scenario: Analyze synergies with no active deck

- **GIVEN** no active deck is loaded (session has no `active_deck_id`)
- **WHEN** user requests "what synergies does my deck have?"
- **THEN** the agent SHALL return error message "No active deck. Please create or load a deck first."

#### Scenario: Natural language variations

- **GIVEN** a user has an active deck loaded
- **WHEN** the user sends any of:
  - "analyze my synergies"
  - "show me card synergies"
  - "what cards work well together?"
  - "does my deck have synergies?"
- **THEN** the agent SHALL invoke `detect_synergies` tool in all cases

#### Scenario: Empty synergy result handling

- **GIVEN** a deck with no detected synergies
- **WHEN** `detect_synergies` tool executes
- **THEN** the agent SHALL return helpful message like "No obvious synergies detected yet. As you add more cards with shared themes or mechanics, synergies will emerge."

### Requirement: Synergy Formatting for Display

The system SHALL provide a `format_synergies()` function that renders synergy analysis as formatted markdown suitable for Chainlit display.

#### Scenario: Format synergies grouped by type

- **GIVEN** a `SynergyAnalysis` with 1 tribal synergy, 1 keyword synergy, 1 mechanic combo
- **WHEN** `format_synergies(analysis)` is called
- **THEN** the output SHALL be markdown with sections:
  - "🧬 Synergies Detected (3)"
  - "### Tribal Synergies" section
  - "### Keyword Synergies" section
  - "### Mechanic Combos" section
- **AND** each section SHALL list affected cards and explanations

#### Scenario: Format individual synergy pattern

- **GIVEN** a `SynergyPattern` with `pattern_type="tribal"`, `subtype="Goblin"`, 14 affected cards, explanation
- **WHEN** formatting this pattern
- **THEN** output SHALL include:
  - Synergy header: "**Goblin Tribal** (14 cards, strong)"
  - Explanation text
  - Bulleted list of affected card names (or first 10 + "... and 4 more" if >10)

#### Scenario: Format deck cohesion summary

- **GIVEN** a `SynergyAnalysis` with `deck_cohesion="high"`
- **WHEN** `format_synergies(analysis)` is called
- **THEN** formatted output SHALL include:
  - "**Deck Cohesion:** High"
  - Summary message like "Your deck has strong synergies! Cards work well together to support a cohesive strategy."

#### Scenario: Format empty synergy list

- **GIVEN** a `SynergyAnalysis` with `synergies = []` and `deck_cohesion="low"`
- **WHEN** `format_synergies(analysis)` is called
- **THEN** formatted output SHALL include:
  - "🧬 Synergies Detected (0)"
  - "No obvious synergies detected yet."
  - Helpful guidance: "As you add more cards with shared creature types, keywords, or mechanics, synergies will emerge."

#### Scenario: Strength indicators in formatting

- **GIVEN** a `SynergyPattern` with `strength="strong"`
- **WHEN** formatting the pattern
- **THEN** the strength indicator SHALL be displayed:
  - "strong" → "💪 Strong"
  - "moderate" → "✅ Moderate"
  - "weak" → "⚠️ Weak" (rarely displayed due to filtering)

### Requirement: Unit Tests for Synergy Detection

The system SHALL provide comprehensive unit tests for all synergy detection functions achieving 90%+ coverage.

#### Scenario: Test tribal synergy detection

- **GIVEN** unit tests with mocked deck data
- **WHEN** testing `detect_synergies()` with Goblin deck, Elf deck, multi-tribe deck
- **THEN** correct tribal synergies SHALL be detected
- **AND** tribe names, affected cards, and strength classifications SHALL be accurate

#### Scenario: Test keyword synergy detection

- **GIVEN** unit tests with mocked decks containing keyword synergies
- **WHEN** testing with flying-matters deck, lifelink deck, deathtouch deck
- **THEN** correct keyword synergies SHALL be detected
- **AND** keyword-matters cards SHALL be correctly matched

#### Scenario: Test mechanic combo detection

- **GIVEN** unit tests with mocked decks containing mechanic combos
- **WHEN** testing sacrifice combo, graveyard synergy, card draw combo
- **THEN** correct mechanic combos SHALL be detected
- **AND** enabler/payoff relationships SHALL be identified

#### Scenario: Test edge cases

- **GIVEN** unit tests for edge cases
- **WHEN** testing empty deck, single card, no synergies, weak synergies below threshold
- **THEN** functions SHALL handle edge cases gracefully
- **AND** return empty lists or appropriate default values

#### Scenario: Test synergy strength classification

- **GIVEN** unit tests with various deck compositions
- **WHEN** testing strength classification logic
- **THEN** "weak", "moderate", "strong" classifications SHALL match thresholds (10%, 30%)
- **AND** boundary cases SHALL be tested

### Requirement: Integration Tests for Synergy Detection Tool

The system SHALL provide integration tests validating end-to-end synergy analysis through the agent tool.

#### Scenario: End-to-end synergy analysis with real deck

- **GIVEN** an integration test with test database and sample deck containing tribal synergies
- **WHEN** invoking `detect_synergies` tool via agent
- **THEN** tool SHALL fetch deck from repository
- **AND** detect synergies correctly
- **AND** return formatted markdown output

#### Scenario: Tool error handling for missing deck

- **GIVEN** an integration test with no active deck
- **WHEN** invoking `detect_synergies` tool
- **THEN** tool SHALL handle missing deck gracefully
- **AND** return user-friendly error message

#### Scenario: Tool integration with agent dependencies

- **GIVEN** an integration test with `AgentDependencies` container
- **WHEN** invoking tool with dependencies
- **THEN** tool SHALL access `deck_repository` correctly
- **AND** use `active_deck_id` from session state

#### Scenario: Natural language query variations

- **GIVEN** an integration test with active deck
- **WHEN** testing agent with various synergy query phrases
- **THEN** all natural language variations SHALL trigger synergy tool
- **AND** agent SHALL invoke tool correctly regardless of phrasing

