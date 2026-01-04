Artificial-Planeswalker is a Pydantic AI assistant for MTG Arena that turns Scryfall’s data into instant card lookups, card queries, and guided, format-aware deck building in a cooperative manner. It validates synergy and curve as you go, and persists decks in a SQL database that also stores Scryfall bulk data for fast, offline-friendly queries and analytics. Designed with clean separation between UI and logic, it plugs into a preferred front-end while keeping a type-safe, testable core. For the MVP front-end, a Chainlit interface will provide a ChatGPT style chat interface for interacting with the agent. Rather than using Scryfall's API, it uses the Scryfall bulk data download feature to populate a local data store, so data can be accessed by the agent without worrying about API limits.
Desired MVP Scope:
Epic 1 - Project and Environment Setup
Epic 2 - Scryfall local data store and bulk data population
Epic 3 - Pydantic AI agent setup with tools for querying Scryfall local data
Epic 4 - Simple Chainlit UI
Epic 5 - Deck creation and management functionality (Standard only)
Epic 6 - Simple deck synergy features
Future Roadmap scope:
- Deck view feature, showing the current deck/cards in a visual format similar to MTG Arena
- CopilotKit and AG-UI based chat assistant to replace the Chainlit chat, to access the agent alongside the deck view
- Deck management features 
- Advanced deck synergy