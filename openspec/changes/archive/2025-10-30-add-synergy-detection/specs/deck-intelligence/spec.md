# Deck Intelligence - Synergy Detection Delta

## ADDED Requirements

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
