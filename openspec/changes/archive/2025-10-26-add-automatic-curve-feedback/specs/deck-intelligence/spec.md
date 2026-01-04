# deck-intelligence Delta Spec

## ADDED Requirements

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
