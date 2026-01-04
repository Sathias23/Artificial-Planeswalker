# Card Queries Specification Delta

## ADDED Requirements

### Requirement: Rarity Filtering in Advanced Search

The CardRepository `search_advanced()` method SHALL accept an optional `rarity` parameter to filter cards by rarity with support for single or multiple rarity values.

#### Scenario: Filter by single rarity value

- **GIVEN** cards with rarities "common", "rare", and "mythic" exist in the database
- **WHEN** `search_advanced(rarity="rare")` is called
- **THEN** only cards with `rarity = "rare"` are returned
- **AND** cards with other rarity values are excluded

#### Scenario: Filter by multiple rarity values

- **GIVEN** cards with various rarities exist in the database
- **WHEN** `search_advanced(rarity=["rare", "mythic"])` is called
- **THEN** only cards with `rarity IN ("rare", "mythic")` are returned
- **AND** common and uncommon cards are excluded

#### Scenario: Rarity filter combined with color filter

- **GIVEN** red cards exist with rarities common, rare, and mythic
- **WHEN** `search_advanced(colors=["R"], rarity="rare")` is called
- **THEN** only red cards with `rarity = "rare"` are returned
- **AND** results match both color AND rarity criteria

#### Scenario: Rarity filter with format filter

- **GIVEN** rare cards exist with mixed Standard legality
- **WHEN** `search_advanced(rarity="rare", format_filter="standard")` is called
- **THEN** only Standard-legal rare cards are returned
- **AND** rare cards not legal in Standard are excluded

#### Scenario: Rarity filter case-insensitive

- **GIVEN** cards with `rarity = "rare"` exist
- **WHEN** `search_advanced(rarity="Rare")` is called
- **THEN** cards with `rarity = "rare"` are returned (case-insensitive match)

#### Scenario: No rarity parameter returns all rarities

- **GIVEN** cards with various rarities exist
- **WHEN** `search_advanced(rarity=None)` is called with no rarity filter
- **THEN** cards of all rarities are returned
- **AND** no rarity filtering is applied

#### Scenario: Empty list when no matches

- **GIVEN** no mythic red creatures exist
- **WHEN** `search_advanced(colors=["R"], types=["Creature"], rarity="mythic")` is called
- **THEN** an empty list is returned
- **AND** no error is raised

#### Scenario: Valid rarity values

- **GIVEN** the Scryfall card database
- **WHEN** querying by rarity
- **THEN** valid rarity values are: "common", "uncommon", "rare", "mythic"
- **AND** special values include: "special", "bonus" (for promotional/special cards)
