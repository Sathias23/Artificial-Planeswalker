# Security Policy

## Supported versions

Artificial Planeswalker is in early development. Security fixes are applied to
the latest release line only.

| Version | Supported          |
|---------|--------------------|
| 0.5.x   | :white_check_mark: |
| < 0.5   | :x:                |

## Reporting a vulnerability

Please report security issues **privately** — do not open a public issue.

- Email: **sathias@slopstudio.net**
- Or use GitHub's private vulnerability reporting: the **"Report a vulnerability"**
  button under the repository's **Security** tab.

Include steps to reproduce and the affected version or commit. You can expect an
acknowledgement within a few days.

## Scope and threat model

Artificial Planeswalker is a **local, stateless MCP server** plus an **optional
local companion app**. It makes **no LLM calls and requires no API key** of its
own — the MCP client supplies the model. It exposes read and analysis tools over
a local SQLite copy of public Scryfall card data and the user's own local decks.
There is no hosted service and the server stores no secrets of its own.

### The MCP server

- **stdio is the only supported transport.** The MCP client launches the server
  as a child process and talks to it over its pipes; nothing listens on a socket.
  `src/mcp_server/__main__.py` still honours `MCP_TRANSPORT=sse` /
  `streamable-http` for development, but those modes are unauthenticated and are
  **not** a supported deployment.
- **Tool inputs are bounded.** Every LLM-supplied argument has a ceiling (deck
  name, strategy, tags, card quantity, page size); non-finite numeric bounds are
  rejected before they reach SQL, and every value is bound as a parameter, never
  interpolated. Bad input yields a `status="invalid"` result, not an exception.
- **`initialize_database` and `build_search_index` are declared destructive**
  (`destructiveHint`) so clients that gate such tools behind confirmation can.

### The companion app (`artificial-planeswalker companion`)

The companion is a browser view of the active deck. When it is running it is a
**loopback-only HTTP + WebSocket service**:

- **Binds to `127.0.0.1`** on port `8765` (override with `COMPANION_PORT`); it
  never binds to a routable interface.
- **Bearer token.** A random token is minted at launch and written to a discovery
  file in the local data directory; the MCP server's push tools read it from there
  and every mutating request must present it. The token is compared in constant
  time and never logged.
- **WebSocket tickets are single-use** and short-lived: the page asks the app
  for a ticket (the browser never sees the bearer token), and a ticket opens at
  most one socket before it is destroyed.
- **Exact `Host` and `Origin` checks.** Requests whose `Host` is not the loopback
  address:port the app was launched on, or whose `Origin` (when present) is not
  the app's own origin, are refused. This is what blocks DNS-rebinding and
  cross-site requests from other tabs.
- **64 KB request-body cap** enforced by middleware on every request.
- **Image proxy host allow-list.** Card images are fetched only from Scryfall's
  image hosts, cached on disk, and never from a caller-supplied URL — the proxy
  cannot be pointed at internal addresses.

### Data on disk

- **Card data is downloaded, not bundled.** On first run the server fetches
  Scryfall bulk data over HTTPS. No card data is committed to the repository.
- **The database and caches are local.** The server reads and writes a SQLite
  file, the embedding model cache, the image cache, and the companion discovery
  file (which holds the bearer token) in your OS data directory (or
  `PLANESWALKER_DATA_DIR`). Protect that directory with normal filesystem
  permissions — anyone who can read the discovery file can push to a running
  companion on the same machine.
