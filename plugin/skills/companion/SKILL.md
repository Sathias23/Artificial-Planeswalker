---
name: companion
description: 'Open the Artificial Planeswalker companion app — the localhost browser view of the active deck — from the agent. Use when the user asks to open, start, launch, show or see the companion, or when any companion_* tool answers app_not_running and you want to offer to open it. Checks status first, launches in a background shell only when needed, and confirms the tab opened.'
---

# Companion — open the glass for the user

## Who you are

You are the one who puts the companion on screen. The user should never have to know the launch
command: you ask the server where things stand, start the companion yourself when it is not
running, and confirm the browser tab opened.

## The tools

- `companion_status` (`mcp__artificial-planeswalker__companion_status`) — read-only. Reports
  `status` (`running` / `not_running`), the `url`, how many browser tabs are connected
  (`clients`), and the exact `launch_command` to run. It never starts anything.
- A **background shell** (Bash with `run_in_background`, or your client's equivalent) — the only
  thing that may start the companion. The MCP server never spawns it; the process belongs to the
  shell you own, and it serves in the foreground until interrupted.

## The procedure

1. **Status first.** Call `companion_status`. Never launch without it.
2. **Branch on what it says:**
   - `running` with `clients >= 1` — the companion is already on screen. Say so; do nothing else.
   - `running` with `clients` `0` — it is up but nobody is looking. Run the `launch_command` in
     a **background** shell: its `--open` flag opens a browser tab on the *running* instance and
     exits `0` (it never starts a second one). Give the user the `url` to open by hand only if
     the browser could not be opened.
   - `running` with `clients` `null` — the count is **unknown** (an older companion, or a
     malformed reply), not zero: a tab may already be open. Prefer giving the user the `url` over
     running the launch command — popping a possibly-duplicate tab is worse than one extra click.
   - `not_running` — run the `launch_command` **exactly as returned**, in a **background** shell.
     It looks like:

     ```bash
     uv run --directory "<install root>" artificial-planeswalker companion --open
     ```

     The `--directory` is the server's own install root, so it works from any working directory
     and for a plugin install alike. Don't rewrite it or drop `--open`; adding `--port N` is fine
     when the user asked for a specific port.
3. **Wait for the URL line.** The launch prints one line to stdout when it is serving:

   ```
   [planeswalker] companion running at http://127.0.0.1:<port> — open this URL in your browser (Ctrl-C to stop)
   ```

   `--open` then pops the default browser on that URL from the companion's own process. A first
   launch from a fresh install may take a while (it installs the server's dependencies first);
   give it up to a minute before judging it failed. If the line instead says `already running at`,
   the browser was asked to open on the existing instance; a warning on stderr says if it couldn't.
   A third outcome is `another companion is already starting up` — a second launch lost the race
   for the instance lock while the first was still booting. Do not retry the launch in a loop:
   wait a moment for the winner to finish starting, then re-run `companion_status` and branch on
   what it says.
4. **Confirm — after a pause.** The tab's WebSocket handshake takes a moment after the browser
   opens, so wait a few seconds after the URL line before calling `companion_status` again; if
   `clients` is still `0`, check once more after another short pause before concluding anything.
   Then report the result in one line: running, the URL, and whether a tab is connected. Only if
   `clients` stays `0` did the browser not open (a warning on the launch's stderr says so) — give
   the user the URL to open by hand. If `clients` is `null`, the count will never appear (this
   companion does not report one) — do not re-poll for it; confirm by asking the user whether the
   tab opened, and give them the URL if it didn't.
5. **Then carry on.** Once it is up, `companion_set_active_deck` and the push tools work as
   normal. Re-run anything the user wanted on the glass.

## Rules that bite

- **Background only.** The command serves until Ctrl-C. Run it in the foreground and your session
  hangs.
- **Never invent the launch command.** `companion_status` returns the right one for this install;
  the one thing worth adding is `--port N`, and only when the user asked for that port.
- **One launch per need.** `--open` is idempotent, but do not retry-loop: one launch, one wait,
  one status check. If it is not up after that, tell the user what the launch printed.
- **Offer, don't nag.** When a push tool answers `app_not_running`, offer to open the companion
  once; the content is in chat regardless, and the visual channel never replaces the reply.
- **Do not stop it** unless the user asks; they own the tab.
