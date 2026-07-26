"""FastAPI shell for the companion — importable by nothing outside itself (AD-3).

Modules under this package may depend on FastAPI, uvicorn and ``src.data``; in exchange no module
outside ``src/companion/app/`` may import them, so a stdio MCP session never transitively imports a
web framework merely to read a port number. The single exemption is a **function-local** import
inside ``src/mcp_server/__main__.py`` (the subcommand dispatcher, story c1-9); a module-level import
there still fails the guard.
"""
