---
title: 'view_deck MCP tool'
type: 'feature'
created: '2026-06-28'
status: 'done'
baseline_commit: '25925c2d5f68071546ed35a7a9581eb703747a38'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** A saved deck can only be opened in a browser by running `scripts/view_deck.py` from a cloned repo. Packaged MCPB / Claude Desktop users (the public-release audience) have the server but no repo or shell, so they cannot visually view a deck at all.

**Approach:** Expose deck viewing as a stateless `view_deck` MCP tool that reuses the pure `render_html` renderer. Because the bundle runs as a local stdio server on the user's own machine, the tool renders the deck to a temp HTML file and best-effort opens it in the host's default browser, always returning the file path so a headless/remote host degrades gracefully instead of failing. The temp-file + browser-open side effect is factored into a shared `present_deck` helper that both the new tool and the existing CLI script call.

## Boundaries & Constraints

**Always:**
- Reuse the existing pure `render_html` (`src/viewer/render.py`) — do not duplicate or inline rendering, and keep `render_html` pure (no I/O).
- Follow the established tool-result convention: a Pydantic result model with a `status: Literal[...]` field + `message`, and the `database_not_initialized` guard via `is_database_initialized` returning the shared `DATABASE_NOT_INITIALIZED_MESSAGE`.
- Offload the temp-file write + `webbrowser.open` to `asyncio.to_thread` — the tool is an async Epic-1 tool on the FastMCP event loop and must not block it.
- Browser-open is best-effort and NEVER load-bearing: always populate `file_path` so the result is useful even when no browser can open.
- Add `view_deck` to the hand-maintained `manifest.json` `tools[]` array (not auto-discovered).
- Pass `mypy --strict` and `ruff` cleanly; Google-style docstrings; tool docstring doubles as the LLM-facing description.

**Ask First:**
- Changing `scripts/view_deck.py`'s CLI surface (its `--deck`/`--no-open` flags, logging, or exit codes) beyond the internal refactor to call `present_deck` — Brad uses the script directly.

**Never:**
- Add name-based resolution to the tool — `view_deck` takes a `deck_id` only, mirroring `load_deck`/`analyze_mana_curve` (D5 statelessness; the client supplies the id from `list_decks`/`create_deck`). Fuzzy-name resolution stays a CLI-only convenience.
- Introduce per-session server state or an "active deck" (D5).
- Return the full HTML blob inline in the structured result (return a file path, not the document).
- Modify the deck in any way (read-only).
- Add any new runtime dependency (`webbrowser`/`tempfile` are stdlib).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Happy path | valid `deck_id`, cards present, `open_browser` default (True) | `status="ok"`, `file_path` set to the written HTML, `opened_in_browser=True`, `deck_id`/`deck_name` echoed | N/A |
| Render only | valid `deck_id`, `open_browser=False` | `status="ok"`, `file_path` set, HTML written, `opened_in_browser=False`, no browser launched | N/A |
| Empty deck | valid `deck_id`, deck has 0 cards | `status="ok"`, renders the empty viewer (viewing an empty deck is valid) | N/A |
| Unknown deck | `deck_id` not found | `status="not_found"`, message names the id; no file written | graceful, no raise |
| DB not initialized | `cards` table missing/empty | `status="database_not_initialized"` + shared message naming `initialize_database` | graceful, no raise |
| DB error | repo raises `DatabaseError` | `status="error"`, generic message | logged via `logger.exception`, not raised to client |

</frozen-after-approval>

## Code Map

- `src/viewer/render.py` -- existing pure `render_html(deck) -> str`; consumed unchanged.
- `src/viewer/present.py` -- NEW: `present_deck` (render → temp file → best-effort open) + `deck_viewer_path` + `_slug`; owns the viewer's I/O side effects.
- `src/viewer/__init__.py` -- export `present_deck` alongside `render_html`.
- `src/mcp_server/tools/view_deck.py` -- NEW: `ViewDeckResult` model + async helper.
- `src/mcp_server/server.py` -- register the async `view_deck` `@mcp.tool()`; import the model + helper (aliased `_view_deck_helper`); update module docstring.
- `scripts/view_deck.py` -- refactor `_run` to call `present_deck`; drop its duplicated `_slug`/`tempfile`/`webbrowser`.
- Reuse (unchanged): `src/mcp_server/tools/messages.py` (`DATABASE_NOT_INITIALIZED_MESSAGE`); `src/data/database.py` (async `is_database_initialized`); `src/data/repositories/deck.py` (`DeckRepository.get_deck_with_cards`, eager-loads `deck_cards[].card`).
- `manifest.json` -- add `view_deck` to `tools[]`.
- `tests/integration/test_mcp_tools.py` + `tests/integration/conftest.py` -- tool tests (reuse `seeded_card_db`).
- `tests/unit/viewer/test_present.py` -- NEW: `present_deck` unit tests.

## Tasks & Acceptance

**Execution:**
- [x] `src/viewer/present.py` (NEW) -- add `present_deck(deck: Deck, *, open_browser: bool = True) -> tuple[Path, bool]` (render via `render_html`, write `deck_viewer_path(deck.name)`, then `webbrowser.open(path.as_uri())` when `open_browser` and return its bool as `opened`), plus `deck_viewer_path` + `_slug` moved here. Module docstring.
- [x] `src/viewer/__init__.py` -- export `present_deck` (and `deck_viewer_path` if useful) next to `render_html`.
- [x] `src/mcp_server/tools/view_deck.py` (NEW) -- `ViewDeckResult(BaseModel)` with `status: Literal["ok","not_found","error","database_not_initialized"]`, `deck_id: str | None = None`, `deck_name: str | None = None`, `file_path: str | None = None`, `opened_in_browser: bool = False`, `message: str`; async `view_deck(session, *, deck_id, open_browser=True)` helper: `database_not_initialized` guard → `DeckRepository.get_deck_with_cards` (catch `DatabaseError` → `error`) → `None` → `not_found` → `present_deck` via `asyncio.to_thread` → `ok`.
- [x] `src/mcp_server/server.py` -- register `@mcp.tool() async def view_deck(deck_id: str, open_browser: bool = True) -> ViewDeckResult` wrapping `_view_deck_helper` inside `async with session_factory()`; import the model + helper; extend the module docstring to mention it.
- [x] `scripts/view_deck.py` -- refactor `_run` to `out_path, _ = present_deck(deck, open_browser=open_browser)`; remove the now-shared `_slug`/`tempfile`/`webbrowser` lines. Keep CLI flags, logging, and exit codes unchanged.
- [x] `manifest.json` -- add `{ "name": "view_deck", "description": "Render a saved deck and open it in the default browser (returns the HTML file path)." }` to `tools[]`.
- [x] `tests/integration/mcp_server/test_view_deck_tool.py` (NEW) -- per-tool helper tests (matching the `tests/integration/mcp_server/` per-tool convention): happy path (default open, `webbrowser.open` monkeypatched → `ok`, `opened_in_browser=True`, opener got the file URI), render-only (`open_browser=False` → `ok`, no opener call), unknown id → `not_found`; temp dir redirected to `tmp_path`.
- [x] `tests/integration/mcp_server/test_first_run_data_init.py` -- add `test_view_deck_guards_uninitialized_db` (reuses the shared `empty_session_factory`) → `database_not_initialized`, mirroring the other relational-tool guards.
- [x] `tests/integration/test_mcp_tools.py` -- end-to-end `view_deck` through the in-process MCP client (create deck + add card → `view_deck` with `open_browser=False`) asserting `ok` / `deck_name` / `file_path` exists; proves tool registration + wiring.
- [x] `tests/unit/viewer/test_present.py` (NEW) -- `present_deck` unit tests over a hand-built `Deck`: returns `(path, True)` and writes the file with `webbrowser.open` monkeypatched; returns `(path, False)` with `open_browser=False` and makes no opener call.

**Acceptance Criteria:**
- Given a saved deck with cards on an initialized DB, when `view_deck` is called via the MCP client with `open_browser=False`, then `status="ok"`, `file_path` points to a written HTML file containing the deck's rendered content, and `opened_in_browser` is `False` (no browser launched).
- Given the same deck with default `open_browser=True` and `webbrowser.open` monkeypatched, when `view_deck` is called, then `opened_in_browser` is `True` and the patched opener received the rendered file's URI.
- Given `scripts/view_deck.py` after the refactor, when run as `uv run python scripts/view_deck.py --deck <name> --no-open`, then it still renders to the temp path via `present_deck` with no behavioral regression.
- Given the gate `uv run pytest tests/integration/test_mcp_tools.py tests/unit/viewer`, `uv run ruff check .`, and `uv run mypy src/`, when run, then all pass and no test launches a real browser or performs network/model I/O.

## Spec Change Log

- **Implementation refinement (test homes):** the spec's single `tests/integration/test_mcp_tools.py` test task was split to match the codebase's established per-tool test convention — helper tests in `tests/integration/mcp_server/test_view_deck_tool.py`, the `database_not_initialized` guard alongside the other relational tools in `test_first_run_data_init.py` (reusing the shared `empty_session_factory`), and one end-to-end client test kept in `test_mcp_tools.py`. No behavioral change; ACs unchanged. KEEP: the per-tool split (discoverability + fixture reuse).
- **Review patches (step-04, no loopback):** adversarial + edge-case review found the "browser-open never load-bearing" contract was under-implemented. Patched (code only; frozen intent unchanged): (1) `present_deck` now catches `webbrowser.Error`/`OSError` from `webbrowser.open` (a headless host can *raise*, not just return `False`); (2) the `view_deck` tool wraps the `present_deck` offload in `try/except OSError` → graceful `status="error"` on a write failure; (3) the viewer temp filename is keyed on the unique `deck.id` (not just the lossy name slug) and the slug is ASCII-restricted, removing the same-slug overwrite/race (`deck_viewer_path` now takes the `Deck`); (4) added failure-path tests (browser raises → still `ok`; write fails → `error`). KEEP: the graceful-degradation contract is now test-backed.

## Design Notes

**Shared `present_deck` (why):** removes the temp-file/slug/browser duplication between the new tool and the existing script; `render.py` stays pure (`deck → str`) while `present.py` owns the I/O. Both composition roots — the MCP tool and the CLI — call it.

```python
def present_deck(deck: Deck, *, open_browser: bool = True) -> tuple[Path, bool]:
    html = render_html(deck)
    path = deck_viewer_path(deck.name)
    path.write_text(html, encoding="utf-8")
    opened = webbrowser.open(path.as_uri()) if open_browser else False
    return path, opened
```

The tool helper mirrors `load_deck`'s guard → resolve → result flow, wrapping `present_deck` in `asyncio.to_thread` so the sync file-write + `webbrowser.open` (which spawns the OS handler) never blocks the FastMCP event loop.

## Verification

**Commands:**
- `uv run pytest tests/integration/test_mcp_tools.py tests/unit/viewer` -- expected: all `view_deck` + `present_deck` tests pass; no real browser launched.
- `uv run ruff check . && uv run ruff format --check .` -- expected: clean.
- `uv run mypy src/` -- expected: no errors (strict).
- `uv run python scripts/view_deck.py --deck "<existing deck>" --no-open` -- expected: prints the rendered temp path, no regression.

## Suggested Review Order

**The tool (start here)**

- The MCP tool surface — what the LLM sees; stateless `deck_id` + `open_browser`.
  [`server.py:361`](../../src/mcp_server/server.py#L361)

- Tool helper: db guard → resolve deck → present → graceful `not_found`/`error`.
  [`view_deck.py:55`](../../src/mcp_server/tools/view_deck.py#L55)

- The structured result envelope (`status` / `file_path` / `opened_in_browser`).
  [`view_deck.py:33`](../../src/mcp_server/tools/view_deck.py#L33)

**Shared presentation helper (the reuse)**

- `present_deck`: pure `render_html` → temp file → best-effort browser open.
  [`present.py:39`](../../src/viewer/present.py#L39)

- Browser-open is best-effort — swallows `Error`/`OSError` so a render never fails.
  [`present.py:59`](../../src/viewer/present.py#L59)

- Temp path keyed on the unique `deck.id`, so same-slug names never collide.
  [`present.py:30`](../../src/viewer/present.py#L30)

**Graceful degradation + de-duplication**

- Write failure (`OSError`) converted to a graceful `error`, never raised to the client.
  [`view_deck.py:92`](../../src/mcp_server/tools/view_deck.py#L92)

- CLI script now reuses `present_deck` (drops duplicated slug/tempfile/browser).
  [`scripts/view_deck.py:94`](../../scripts/view_deck.py#L94)

- Hand-maintained MCPB manifest gains the `view_deck` entry.
  [`manifest.json:49`](../../manifest.json#L49)

**Tests**

- Helper: happy path, render-only, `not_found`, browser-raises, write-fails.
  [`test_view_deck_tool.py:66`](../../tests/integration/mcp_server/test_view_deck_tool.py#L66)

- `present_deck` unit isolation (render patched; write + open behavior).
  [`test_present.py:37`](../../tests/unit/viewer/test_present.py#L37)

- `database_not_initialized` guard alongside the sibling tools.
  [`test_first_run_data_init.py:207`](../../tests/integration/mcp_server/test_first_run_data_init.py#L207)

- End-to-end `view_deck` through the in-process MCP client.
  [`test_mcp_tools.py:227`](../../tests/integration/test_mcp_tools.py#L227)
