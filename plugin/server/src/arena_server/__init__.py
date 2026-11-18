"""The ``arena-game-state`` MCP server: the live MTG Arena game, read from the client's log.

A second, separate server beside ``src/mcp_server``. It shares nothing with the deckbuilding
server at runtime: no card database, no session, no embedding model, so it starts in the time it
takes to import ``mcp`` and stays out of the way of anyone who never plays Arena.
"""
