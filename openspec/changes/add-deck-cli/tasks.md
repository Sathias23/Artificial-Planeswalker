# Implementation Tasks

## Task Group 1: CLI Framework and Basic Commands (Foundation)
1. Create `scripts/manage_decks.py` with argparse structure and main entry point
2. Implement database session management helper (create_engine, session factory, async context)
3. Implement `list` command with table formatting and format filtering
4. Implement `show` command with deck details and card grouping
5. Add basic error handling for common cases (deck not found, database errors)
6. Test list and show commands manually with existing database

## Task Group 2: Deck Creation and Deletion
7. Implement `create` command with name, format, and optional strategy arguments
8. Implement `delete` command with confirmation flag requirement
9. Add error handling for duplicate deck names
10. Add user-friendly error messages for deletion failures
11. Test create and delete commands with edge cases

## Task Group 3: Card Management Commands
12. Implement `add-card` command with card name lookup via CardRepository
13. Implement `remove-card` command with confirmation flag
14. Implement `update-quantity` command for existing cards
15. Add case-insensitive card lookup using find_by_name_exact()
16. Add error handling for card not found, card already in deck, card not in deck
17. Add sideboard flag support for all card commands
18. Test card management commands with various scenarios

## Task Group 4: Merge Decks Functionality
19. Implement `merge` command with target and source deck arguments
20. Add --strategy flag with choices (COMBINE, MAXIMUM, REPLACE) and default to COMBINE
21. Add merge summary display (cards added, cards merged, strategy, color identity)
22. Add error handling for non-existent target/source decks
23. Test merge command with all three strategies and edge cases

## Task Group 5: Export Functionality
24. Implement `export` command with stdout output
25. Add file output support with --output flag
26. Add metadata support with --include-metadata flag
27. Format decklist as "Nx Card Name" with sideboard section
28. Test export command with various deck sizes and configurations

## Task Group 6: Help and Documentation
29. Add comprehensive --help text for main parser
30. Add command-specific help text for each subcommand
31. Add usage examples in script docstring
32. Update CLAUDE.md with CLI tool documentation and usage examples

## Task Group 7: Testing and Validation
33. Write unit tests for argument parsing (invalid inputs, type conversion)
34. Write integration tests for each command against in-memory database
35. Add integration tests for merge command with all strategies
36. Add performance tests for list/show commands with large datasets
37. Test error scenarios (database connection failures, permission errors)
38. Validate that CLI works without agent/UI dependencies installed

## Validation Steps
- [ ] All commands execute successfully with valid inputs
- [ ] Error messages are clear and actionable for common failures
- [ ] Help text is comprehensive and includes examples
- [ ] Operations complete in <1 second for typical decks
- [ ] CLI works independently of agent and UI layers
- [ ] Case-insensitive card lookup works correctly
- [ ] Confirmation flags prevent accidental deletions
- [ ] Merge command works with all three strategies (COMBINE, MAXIMUM, REPLACE)
- [ ] Export format is compatible with common MTG tools

## Dependencies
- Requires existing `DeckRepository` and `CardRepository` (already implemented)
- Requires database with card data imported (already available)
- No new Python dependencies (uses stdlib argparse and existing SQLAlchemy)

## Parallelization Notes
- Task Groups 1-2 are sequential (foundation required first)
- Task Group 3 can proceed after Group 1 (doesn't need create/delete)
- Task Group 4 can proceed after Group 1 (needs deck lookup pattern)
- Task Group 5 can proceed after Group 1 (only needs show command pattern)
- Task Groups 6-7 can proceed in parallel with implementation groups
