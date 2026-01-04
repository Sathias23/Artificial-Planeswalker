# agent-tools Delta Spec

## ADDED Requirements

### Requirement: Toggle Auto-Feedback Tool

The agent SHALL provide a tool that enables users to toggle automatic mana curve feedback on or off.

#### Scenario: Disable auto-feedback

- **GIVEN** auto-feedback is currently enabled (default state)
- **AND** a user requests "disable curve feedback" or "turn off auto-feedback"
- **WHEN** the toggle_auto_feedback tool is invoked with enabled=False
- **THEN** the tool SHALL set `deps.auto_feedback_enabled = False` in session state
- **AND** return a confirmation message "Automatic curve feedback disabled. You can still request analysis with 'analyze my mana curve'."

#### Scenario: Enable auto-feedback

- **GIVEN** auto-feedback is currently disabled
- **AND** a user requests "enable curve feedback" or "turn on auto-feedback"
- **WHEN** the toggle_auto_feedback tool is invoked with enabled=True
- **THEN** the tool SHALL set `deps.auto_feedback_enabled = True` in session state
- **AND** return a confirmation message "Automatic curve feedback enabled. I'll provide real-time curve guidance as you build."

#### Scenario: Preference persists across messages

- **GIVEN** a user has disabled auto-feedback
- **WHEN** the user sends subsequent messages in the same session
- **THEN** auto-feedback SHALL remain disabled
- **AND** the preference SHALL persist until explicitly changed or session ends

#### Scenario: Default state is enabled

- **GIVEN** a new session starts with no prior auto-feedback preference
- **WHEN** a user adds their first card to a deck
- **THEN** auto-feedback SHALL be enabled by default
- **AND** the system SHALL generate contextual curve feedback

## MODIFIED Requirements

### Requirement: Add Card to Deck Tool

The agent SHALL provide a tool that enables adding cards to the active deck with quantity specification, Standard format validation, deck construction rule enforcement, **and automatic mana curve feedback when enabled**.

#### Scenario: Add card to active deck successfully

- **GIVEN** an active deck is set in session context
- **AND** a user requests "add 4 Lightning Bolt to my deck"
- **WHEN** the tool is invoked with name="Lightning Bolt" and quantity=4
- **AND** Lightning Bolt is Standard-legal
- **AND** the deck currently has 0 copies of Lightning Bolt
- **THEN** the tool SHALL add 4 copies of Lightning Bolt to the deck
- **AND** return a confirmation message with card name, quantity, and updated total deck count

#### Scenario: Add single card with default quantity

- **GIVEN** an active deck exists
- **AND** a user requests "add Sheoldred to my deck"
- **WHEN** the tool is invoked with name="Sheoldred" (no quantity specified)
- **THEN** the tool SHALL add 1 copy of the card (quantity defaults to 1)
- **AND** return confirmation with the added card details

#### Scenario: Automatic curve feedback after addition

- **GIVEN** an active deck exists
- **AND** auto-feedback is enabled (default)
- **AND** a user adds a card that significantly changes the curve
- **WHEN** the add_card_to_deck tool completes successfully
- **THEN** the tool SHALL invoke contextual feedback generation logic
- **AND** append curve feedback to the tool result message
- **AND** the agent SHALL include feedback in its response to the user

#### Scenario: Auto-feedback respects disabled preference

- **GIVEN** an active deck exists
- **AND** auto-feedback is disabled (user explicitly disabled)
- **WHEN** the add_card_to_deck tool completes successfully
- **THEN** the tool SHALL NOT generate curve feedback
- **AND** return only the standard card addition confirmation

#### Scenario: Auto-feedback skips insignificant changes

- **GIVEN** an active deck with 20 cards and balanced curve
- **AND** auto-feedback is enabled
- **WHEN** a user adds 1 card that doesn't significantly change curve distribution (< 15% shift in any CMC bucket)
- **THEN** the tool SHALL skip feedback generation
- **AND** return only the standard card addition confirmation
- **AND** avoid feedback fatigue from repetitive messages

#### Scenario: Positive reinforcement feedback

- **GIVEN** an aggro deck with few early drops
- **AND** auto-feedback is enabled
- **WHEN** a user adds a 1-mana creature
- **THEN** the feedback SHALL include positive reinforcement
- **AND** message like "Great addition! Strong early-game presence for an aggressive deck."

#### Scenario: Warning feedback for curve issues

- **GIVEN** a deck with many 5+ CMC cards
- **AND** auto-feedback is enabled
- **WHEN** a user adds another high-cost card
- **THEN** the feedback SHALL include a warning
- **AND** message like "Your deck is getting top-heavy. Consider adding more 1-3 mana plays for early-game consistency."
