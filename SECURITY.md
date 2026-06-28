# Security Policy

## Supported versions

Artificial Planeswalker is in early development. Security fixes are applied to
the latest release line only.

| Version | Supported          |
|---------|--------------------|
| 0.1.x   | :white_check_mark: |

## Reporting a vulnerability

Please report security issues **privately** — do not open a public issue.

- Email: **sathias@slopstudio.net**
- Or use GitHub's private vulnerability reporting: the **"Report a vulnerability"**
  button under the repository's **Security** tab.

Include steps to reproduce and the affected version or commit. You can expect an
acknowledgement within a few days.

## Scope and threat model

Artificial Planeswalker is a **local, stateless MCP server**. It makes **no LLM
calls and requires no API key** of its own — the MCP client supplies the model.
It exposes read and analysis tools over a local SQLite copy of public Scryfall
card data and the user's own local decks. There is no hosted network service, no
authentication surface, and the server stores no secrets.

Things worth knowing for a security review:

- **`report_bug` stores untrusted input.** The tool writes user-supplied text to
  the local database verbatim. Treat that content as untrusted when reading it
  back; the server never executes or renders it as code.
- **Card data is downloaded, not bundled.** On first run the server fetches
  Scryfall bulk data over HTTPS. No card data is committed to the repository.
- **The database is local.** The server reads and writes a SQLite file in your OS
  data directory (or `PLANESWALKER_DATA_DIR`). Protect that path with normal
  filesystem permissions.
