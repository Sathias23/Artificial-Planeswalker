# Implementation Tasks

## 1. Data Layer - Format Legality Filtering
- [x] 1.1 Add `find_standard_legal_cards()` method to CardRepository
- [x] 1.2 Extend existing query methods with optional `format_filter` parameter
- [x] 1.3 Implement JSON field query for `legalities.standard = "legal"`
- [x] 1.4 Write unit tests for format filtering logic
- [x] 1.5 Write integration tests with sample Standard-legal and illegal cards

## 2. Agent Context - Session Format State
- [x] 2.1 Add `format_filter` field to AgentDependencies or session context
- [x] 2.2 Initialize format filter as None (disabled) by default
- [x] 2.3 Provide context accessor for current format filter state

## 3. Format Filter Control Tool
- [x] 3.1 Create `set_format_filter` agent tool
- [x] 3.2 Implement tool to accept format parameter ("standard" or None)
- [x] 3.3 Update session context with format preference
- [x] 3.4 Return confirmation message indicating filter status
- [x] 3.5 Write unit tests for format filter tool

## 4. Integrate Format Filter into Existing Tools
- [x] 4.1 Update card lookup tool to pass format filter to repository
- [x] 4.2 Update advanced search tool to pass format filter to repository
- [x] 4.3 Add format indicator to tool responses when filter is active
- [x] 4.4 Write integration tests for filtered card queries

## 5. Documentation and Examples
- [x] 5.1 Update CLAUDE.md with format filter usage examples
- [x] 5.2 Add docstrings explaining format filter behavior
- [x] 5.3 Document valid format values (currently only "standard")
