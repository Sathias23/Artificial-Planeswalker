---
title: 'Story 17.4: Open the companion from the agent'
type: 'feature'
created: '2026-08-22'
status: 'done'
baseline_commit: '69c80e0e5ec6ff740904959fb73aeb98a53475c1'
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Nothing in the plugin tells the agent how to get the companion on screen. Push tools answer `app_not_running` with "start it, then ask me again", the skills say "skip silently", and the launch command lives only in the README — so a user who doesn't already know the command never sees the glass.

**Approach:** Teach the agent to launch it, never the MCP server. A read-only `companion_status` tool reports running / URL / connected tabs / the exact launch command (install root derived from `__file__`); a new `companion` skill drives it — status first, then background-Bash launch with a new `--open` flag that pops the browser from the companion's own process (AD-15 intact); `app_not_running` copy and the four skills ripple from "skip silently" to "offer to open it via the companion skill".

## Boundaries & Constraints

**Always:** AD-15 — the companion stays a foreground, user/agent-launched process; the MCP server never spawns, detaches or supervises it. `companion_status` is read-only, sends no token, proves liveness only through `client.live_instance()`'s instance-id match, and never includes the token in its result. `--open` is the launcher's own `webbrowser.open` after the URL line (and in the already-running branch, the existing URL); a browser failure logs a warning and never changes exit status or stops serving. `launch_command` uses the `--directory "<root>"` form so it works for plugin installs (deferred-work.md:6516). Skill copy ripple covers all four existing skills + README; `plugin/` rebuilt in the same commit. `tools/companion.py` may import only the `src.companion` leaves (import-boundary test); `8765` literal stays solely in `server.py`.

**Ask First:** Adding any new `[planeswalker] ` print line to `server.run()` (docs test counts them and requires a verbatim README quote) — default is no new announcement. Any change to the `/health` shape beyond one optional `clients` integer.

**Never:** No `companion_start`/spawn tool; no daemon, service or auto-restart; no port scan or env-var rendezvous (discovery file is the sole channel); no change to push-tool result shapes or the `~200-token` result ceiling; no Electron/Tauri; no `${CLAUDE_PLUGIN_ROOT}` dependence inside `src/`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Running, tab open | live instance, `clients ≥ 1` | `status="running"`, `url`, `clients`, `launch_command`; message: already open, nothing to do | N/A |
| Running, no tab | live instance, `clients == 0` | `status="running"`, `clients=0`; message tells the agent to open `url` (or run `launch_command` — `--open` on the already-running branch opens a tab, exit 0) | N/A |
| Not running | no/stale discovery file or instance-id mismatch | `status="not_running"`, `url=None`, `launch_command` set; message: offer to start it | never raises; stale file ≠ error |
| Launch `--open` | `companion --open` binds fine | URL line printed, then browser opened to that URL, then serves | `webbrowser` raises → `logger.warning`, keep serving |
| Launch `--open`, already running | live instance found | prints existing already-running line, opens that URL, exit 0 | same |
| Bad argv | `companion --open=yes`, `--opne` | usage error, exit 2 (existing shape) | N/A |

</frozen-after-approval>

## Code Map

- `src/mcp_server/tools/companion.py` -- add `CompanionStatusResult` (pydantic; `status: Literal["running","not_running","error"]`, `url`, `clients`, `launch_command`, `message`) + `companion_status()` helper; alias `live_instance`/`probe_health`/`base_url` as `_client_*` (`:39-40` pattern) so tests stub them; install root = `Path(__file__).resolve().parents[2]`. Edit `_MESSAGES["app_not_running"]` (`:129-132`) and `_push_messages` (`:291-294`) to say the agent can open it (name the `companion` skill / `companion_status`).
- `src/mcp_server/server.py` -- one more `@mcp.tool()` closure beside `:499-720`; import helper at `:65-76`; update docstrings that describe `app_not_running` (`:509-718`) only where wording changes.
- `src/companion/client.py` -- `live_instance()` `:303`, `probe_health()` `:236`, `base_url()` `:219`; `HealthResponse` gains `clients: int | None = None`. READ the probe; don't add a verb.
- `src/companion/contracts.py:22-45` + `src/companion/app/routes/health.py:11-28` -- add `clients` from `state.connected_count` (`state.py:546`); regenerate/refresh committed OpenAPI/TS pins (`test_openapi_contract.py`).
- `src/companion/app/server.py` -- `run(port=None)` `:270` gains `open_browser: bool = False`; hook after URL line `:351-355` and in already-running branch `:317-323`; `webbrowser` precedent `src/viewer/present.py:58`.
- `src/mcp_server/__main__.py` -- `_USAGE` `:44-58` (add `--open`, still no `8765`); `_parse_companion_port` `:152-189` → widen return to (port, open) shape; `_run_companion` `:192-241` passes `open_browser`.
- `.claude/skills/companion/SKILL.md` (new) + `scripts/build_plugin.py` `SKILLS` `:49` + `.pre-commit-config.yaml:34-39` `files:` regex -- new skill ships in `plugin/skills/`.
- `.claude/skills/{format-legality:505-507, magic-deckbuilding:288-290, mana-curve-analysis:348-350, synergy-discovery:315-317}/SKILL.md` -- replace the "skip silently" bullet; add `companion_status` to each tool enumeration line.
- `README.md:28, 248-271, 298-325` -- document `companion_status`, `--open`, and the skill.
- Tests: `tests/integration/mcp_server/test_companion_tool.py` (`client_stub` `:234`, message-table pins `:1308`), `test_companion_degradation.py::closed_companion` `:58`, `tests/integration/mcp_server/test_entry_point.py` (`_RecordingRun` `:28`, usage-shape `:293`, `TestUsageErrors` `:235`), `tests/unit/companion/test_server.py::TestRun` `:345`, `test_client.py::plant_discovery` `:506`, `test_companion_docs.py` (`_EXPECTED_ANNOUNCEMENTS` `:126`), `tests/integration/test_build_plugin.py` (`:257-290` tool-name set, `:424` skill set).
- `_bmad-output/planning-artifacts/epics-companion-app.md` + `implementation-artifacts/{epic-17-context.md, sprint-status.yaml}` -- record Story 17.4 so the retro sees it.

## Tasks & Acceptance

**Execution:**
- [x] `src/companion/contracts.py`, `routes/health.py`, `client.py` -- add optional `clients` to `/health` + `HealthResponse`; refresh contract pins -- the only read-only tab count.
- [x] `src/mcp_server/tools/companion.py` + `server.py` -- `companion_status` tool, result model, message ripple -- the agent's read-only answer.
- [x] `src/companion/app/server.py` + `src/mcp_server/__main__.py` -- `--open` flag end to end -- the page actually appears.
- [x] `.claude/skills/companion/SKILL.md` + four existing skills + `build_plugin.py` + pre-commit regex -- skill: status → launch via background Bash (`uv run --directory "<root>" artificial-planeswalker companion --open`) → wait for the URL line → confirm; handles running/no-tab/not-running.
- [x] Tests per Code Map; probe proof `uv run python -m scripts.probe_harness --expect-red '<planted status test>'`.
- [x] `README.md`, epics file, epic-17 context, `sprint-status.yaml` (`17-4-open-the-companion-from-the-agent`), `plugin/` rebuild.

**Acceptance Criteria:**
- Given a fresh Claude Code session with the plugin and no companion running, when the user says "open the companion", then the agent calls `companion_status`, launches the printed command in background Bash, and a browser tab opens on the companion URL with no manual command typed.
- Given a live companion with one tab, when `companion_status` is called, then it reports running with `clients=1` and the agent does nothing further.
- Given the full suite + ruff + mypy, when run, then green, the tool-name and skill-set pins include the new entries, and `plugin/` matches the build.

## Design Notes

- Why no spawn tool: the MCP server is a stdio child of the session — a child companion dies with it and a detached one is a daemon (AD-15); Bash with `run_in_background` is already the agent's process owner.
- `--open` is idempotent by design: the already-running branch opens the existing URL, so the skill's launch step is safe to run on every "no tab open" case.
- Install root from `__file__` (`parents[2]` of `src/mcp_server/tools/…` = uv project dir) holds for both `plugin/server` and a clone.

## Verification

**Commands:**
- `uv run pytest -m "not integration"` + the touched integration files -- expected: green.
- `uv run ruff check . && uv run ruff format --check . && uv run mypy src/` -- expected: clean.
- `uv run python -m scripts.build_plugin` (or pre-commit) -- expected: `plugin/` unchanged after commit.

**Manual checks:**
- From a plugin install: ask the agent to open the companion → tab opens; ask again → "already open".

## Implementation Record

- Probe proof (committed harness, full `-m "not integration"` suite, planted `assert result.status == "running"  # PLANTED` in `test_not_running_offers_the_launch_command_and_no_url`):
  `full suite (-m 'not integration'): 3322 collected, 1 failed, 0 errored, exit 1` · `RED tests/integration/mcp_server/test_companion_tool.py::TestCompanionStatusIsReadOnlyAndNamesTheNextStep::test_not_running_offers_the_launch_command_and_no_url` · `harness exit=0`. Plant restored (`grep -c PLANTED` → 0).
- Gates on the final tree: ruff check + format clean; mypy `94 source files` clean; touched integration files + `tests/unit/companion` → `1707 passed, 1 skipped`; `plugin/` rebuild idempotent (5 skills).
- Deviation from Code Map: install root is `Path(__file__).resolve().parents[3]` (the Code Map's `parents[2]` is `src/`); a test asserts `pyproject.toml` lives there.
- Matrix coverage: rows 1–3 → `TestCompanionStatusIsReadOnlyAndNamesTheNextStep` (test_companion_tool.py) + `test_companion_degradation.py`; rows 4–5 → `TestOpenBrowser` (test_server.py); row 6 → `TestUsageErrors` (test_entry_point.py).

## Suggested Review Order

**Entry point — the read-only answer the agent acts on**

- Two-probe liveness: record proves identity, second health body yields tab count; any disagreement is `not_running`
  [`companion.py:779`](../../src/mcp_server/tools/companion.py#L779)

- Install root from `__file__` (`parents[3]` = uv project dir) — works for clone and plugin alike, no env dependence
  [`companion.py:719`](../../src/mcp_server/tools/companion.py#L719)

- The exact launch string the skill must run verbatim (`--directory` + `--open`)
  [`companion.py:731`](../../src/mcp_server/tools/companion.py#L731)

- Result vocabulary; token never enters it
  [`companion.py:745`](../../src/mcp_server/tools/companion.py#L745)

- FastMCP registration beside the push tools
  [`server.py:502`](../../src/mcp_server/server.py#L502)

**`--open` — the companion opens its own browser (AD-15 intact)**

- Own-process `webbrowser.open`; failure is a warning, never an exit-status change
  [`server.py:271`](../../src/companion/app/server.py#L271)

- Idempotent by design: already-running branch opens the live URL so the skill can relaunch whenever no tab is open
  [`server.py:350`](../../src/companion/app/server.py#L350)

- Normal path: browser asked only after the URL line is printed
  [`server.py:388`](../../src/companion/app/server.py#L388)

- Bare-flag parsing; `--open=yes` / duplicate are usage errors (exit 2)
  [`__main__.py:182`](../../src/mcp_server/__main__.py#L182)

**`/health` gains the only read-only tab count**

- Optional `clients` — older companions still parse
  [`contracts.py:50`](../../src/companion/contracts.py#L50)

- Route reads the registry's live count; `None` on a never-started app
  [`health.py:39`](../../src/companion/app/routes/health.py#L39)

**The skill and the copy ripple**

- The procedure: status → background launch → wait for URL line → paused re-check
  [`SKILL.md:23`](../../.claude/skills/companion/SKILL.md#L23)

- Four existing skills: "skip silently" → "offer to open it once"
  [`SKILL.md:290`](../../.claude/skills/magic-deckbuilding/SKILL.md#L290)

- New skill ships via the plugin build
  [`build_plugin.py:55`](../../scripts/build_plugin.py#L55)

- User-facing docs incl. how to stop an agent-launched companion
  [`README.md:263`](../../README.md#L263)

**Tests**

- Status tool: three states, vanishing/foreign instance, negative clamp, no token, launch-command root
  [`test_companion_tool.py:1449`](../../tests/integration/mcp_server/test_companion_tool.py#L1449)

- `--open` behaviours incl. already-running and failure-keeps-serving
  [`test_server.py:949`](../../tests/unit/companion/test_server.py#L949)

- Real socket counted by `/health` (closes the verification gap the review found)
  [`test_app.py:160`](../../tests/unit/companion/test_app.py#L160)
