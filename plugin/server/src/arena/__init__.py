"""Read the live MTG Arena game state from the client's own log.

With "Detailed Logs (Plugin Support)" switched on, the Arena client writes every game-state
message it receives to ``Player.log``. This package replays those messages into the current state
of the latest game and names the cards from the client's local card database, so an agent can be
shown the board without a screenshot.

Framework-free like ``src/logic``: stdlib and ``pydantic`` only, and nothing here touches the
project's own card database. ``src/arena_server`` is the MCP surface over it.

* :mod:`~src.arena.locate` finds the log and the card database on this machine.
* :mod:`~src.arena.log_reader` scans the log and feeds the tracker.
* :mod:`~src.arena.tracker` replays game-state diffs into the current raw state.
* :mod:`~src.arena.card_database` resolves Arena ids to names and rules text.
* :mod:`~src.arena.snapshot` renders the tracker's state as the result an agent reads.
* :mod:`~src.arena.reader` ties them together behind one never-raising call.
"""
