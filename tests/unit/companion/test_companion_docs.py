"""Drift guard over README's ``## The companion app`` section (story 15-4).

The section is the only place a first-time user is told how to start the companion, what the app
prints, which port it picks, what a second launch does, and what a fresh install with no card
database looks like. Every one of those claims is true only because a constant, a message literal or
an entry-point return currently says so — and prose has no compiler, so this module is the compiler.
The idiom is ``test_image_cache_docs.py``'s, story 15-2's guard over the section immediately below
this one, and the pins follow the same rule: **key on the shipped symbol, never on a literal copied
out of the README**, so a rename that updates the prose moves the pin with it and a rename that does
not turns this red.

Where a value has no constant to import, the source file is parsed rather than transcribed. The four
``[planeswalker]`` announcements are lifted out of ``src/companion/app/server.py``'s AST — f-strings
included, with their interpolation slots rendered as wildcards and then checked against ``HOST`` and
``DEFAULT_PORT`` — so the README quotes the runner's own words, em dashes and all, and gaining a
fifth announcement fails here until the README grows one too. The exit statuses are read the same
way, off every integer ``return`` in the dispatcher, and the fresh-install panel copy is read out of
``ui/src/components/StatePanel/copy.ts`` at the entry whose key is the kebab spelling of the shipped
``database_not_initialized`` reason token.

**One deliberate divergence from ``test_image_cache_docs.py``.** That module terminates its scan on
an ATX heading of *any* level, because ``### Image cache (companion app)`` owns no subsections. This
section does own them — six ``###`` headings — so :func:`_extract_section` terminates on a heading
of the section's own level or higher, derived from :data:`SECTION_HEADING` rather than hardcoded.
Both bounds are tested rather than asserted in prose, including the one that matters most: the
neighbouring image-cache section must stay *outside* this extraction, or an assertion here could
pass on story 15-2's prose instead of this story's.

**Declared residue — what this guard does NOT prove:**

1. **No process is started and no socket is bound.** That the launch line is the *only* line the
   user sees depends on uvicorn suppressing its own banner when handed a pre-bound socket, and the
   ephemeral fallback depends on a real ``OSError`` at bind time. Neither is exercised here — both
   belong to ``tests/unit/companion/test_server.py``, which owns the runner. This module proves only
   that the README quotes the messages the runner would print, character for character.
2. **The announcement selector is a literal.** :data:`_ANNOUNCEMENT_PREFIX` is this module's own
   word for "a line the user sees on stdout"; the code has no constant for it. The count assertion
   is what makes that safe: exactly :data:`_EXPECTED_ANNOUNCEMENTS` are expected, so a prefix change
   that hid every message fails loudly instead of passing over an empty scan.
3. **Ordering and truth are not checked, only presence and provenance.** That the precedence
   sentence names ``--port`` before the environment variable is asserted; that the paragraph around
   it explains precedence *correctly* is a reviewer's judgement. Likewise the Node claim: this
   module checks that ``fastapi`` and ``uvicorn`` really are base dependencies in ``pyproject.toml``
   and that the section says Node is not required, not that the sentence between them reads well.
4. **The other half of the story is guarded elsewhere or not at all.** ``CHANGELOG.md`` is read by
   no test in this repository (deliberately — a changelog is a record, not a contract), the
   ``plugin/`` mirror of ``README.md`` is covered by CI's rebuild-and-diff rather than by an
   assertion here, and the ``NOTICE`` attribution URLs are pinned from the app's side by
   ``ui/tests/attribution.test.ts``.
5. **The failed-import recovery is prose about a defect, not a reproduction of it.** F4 (a
   schema-only ``cards.db`` a running companion has opened) is documented, not fixed; this module
   checks the recovery names stopping the app first and names the database file the shipped path
   builder builds. It never plants a partial database.
"""

import ast
import re
import tomllib
from pathlib import Path
from typing import get_args

import pytest

from src import paths
from src.companion import client, discovery
from src.companion.app import server, singleton
from src.companion.contracts import ErrorReason
from src.mcp_server import __main__ as entry_point
from src.mcp_server.tools.companion import SetActiveDeckResult

# ---------------------------------------------------------------------------------------------
# Repository layout — resolved from __file__, never from the current working directory, exactly as
# tests/unit/companion/test_image_cache_docs.py does it.
# ---------------------------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[3]
README_PATH = REPO_ROOT / "README.md"
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
SERVER_SOURCE_PATH = REPO_ROOT / "src" / "companion" / "app" / "server.py"
ENTRY_POINT_SOURCE_PATH = REPO_ROOT / "src" / "mcp_server" / "__main__.py"
STATE_PANEL_COPY_PATH = REPO_ROOT / "ui" / "src" / "components" / "StatePanel" / "copy.ts"

SECTION_HEADING = "## The companion app"
"""The section this module is the compiler for. Renaming it here and in README.md is one edit."""

NEIGHBOUR_HEADING = "### Image cache (companion app)"
"""Story 15-2's section, which must stay outside this extraction — see the bounding test."""

_ANNOUNCEMENT_PREFIX = "[planeswalker] "
"""This module's selector for a line ``run()`` prints to the user's terminal.

The code has no constant for it (declared residue 2), so the count below is the safety net: a prefix
that changed under this module would find nothing and fail on the count, never pass on an empty set.
"""

_EXPECTED_ANNOUNCEMENTS = 4
"""How many user-facing lines ``server.run()`` can print: launch, fallback, and the two refusals.

Not a style rule — every one of them is a line the README promises the reader will recognise, so a
fifth arriving without a README entry is exactly the drift this module exists to catch.
"""

# Any ATX heading, capturing its level, so the scan can terminate on a heading of this section's own
# level or higher while letting its own `###` subsections through.
_ATX_HEADING = re.compile(r"^(?P<hashes>#{1,6}) ")

# `  'some-key': {` … `  },` in ui/src/components/StatePanel/copy.ts. Two-space indent on both ends,
# so a nested object inside the block cannot terminate it early.
_STATE_PANEL_BLOCK = re.compile(r"^  '(?P<key>[a-z0-9-]+)': \{\n(?P<body>.*?)^  \},$", re.M | re.S)
_HEADLINE = re.compile(r"headline: '(?P<text>[^']*)'")


def _copy_call(name: str) -> re.Pattern[str]:
    """Return a pattern matching ``name('…')`` or ``name("…")`` in the panel copy module.

    Both quote styles are accepted because the shipped copy uses whichever the sentence needs — the
    guidance line carries an apostrophe and is therefore double-quoted. A pattern that assumed one
    style would report "the shipped copy has no guidance" about a line that is plainly there.

    Args:
        name: The copy helper's name, ``action`` or ``guidance``.

    Returns:
        A compiled pattern with a ``text`` group holding the string literal's contents.
    """
    return re.compile(rf"{name}\(\s*(?P<q>['\"])(?P<text>.*?)(?P=q)", re.S)


def _read_readme() -> str:
    """Return README.md's text, read from the repository root rather than the working directory."""
    assert PYPROJECT_PATH.exists(), f"{REPO_ROOT} is not the repository root"
    return README_PATH.read_text(encoding="utf-8")


def _extract_section(readme: str) -> str:
    """Return the companion section, from its heading to the next heading of its level or higher.

    **The non-vacuity anchor.** Every assertion in this module reads what this returns, so a missing
    or renamed heading has to fail here, loudly and by name, rather than yield an empty string that
    every substring check would then pass over.

    Two bounding rules, one inherited and one deliberately different:

    * The scan is **fence-aware**, exactly as story 15-2's is. A ``### `` line inside a fenced block
      is sample text, not a heading; this section quotes shell commands, so without this a
      documented comment could truncate it mid-command.
    * The terminator is a heading of **this section's own level or higher**, derived from the hashes
      in :data:`SECTION_HEADING`. Story 15-2's guard terminates on any level because its section has
      no subsections; this one has six, and terminating on any level would leave every assertion
      below reading only the section's opening paragraphs.

    Args:
        readme: The full text of ``README.md``.

    Returns:
        The section's lines, heading included, joined with newlines.
    """
    own_level = len(SECTION_HEADING) - len(SECTION_HEADING.lstrip("#"))
    lines = readme.splitlines()
    starts = [i for i, line in enumerate(lines) if line.strip() == SECTION_HEADING]
    assert starts, (
        f"README.md has no {SECTION_HEADING!r} heading. Every claim this module guards lives in "
        "that section, so its absence fails here rather than passing vacuously on an empty scan. "
        "Restore the heading in README.md, or — if the section was deliberately renamed — update "
        f"SECTION_HEADING in {Path(__file__).name} to match."
    )
    assert len(starts) == 1, (
        f"README.md carries {len(starts)} lines reading {SECTION_HEADING!r} (at lines "
        f"{[i + 1 for i in starts]}). This module would guard only the first, so a second copy is "
        "an unguarded duplicate rather than a harmless one — delete it, or reword it so it is not "
        "an exact heading match."
    )
    start = starts[0]
    end = len(lines)
    in_fence = False
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        heading = _ATX_HEADING.match(lines[i])
        if heading is not None and len(heading.group("hashes")) <= own_level:
            end = i
            break
    return "\n".join(lines[start:end])


def _string_templates(source: Path) -> list[list[str]]:
    """Return every string literal in *source* as its list of literal fragments.

    An f-string yields one entry per run of literal text, with its interpolations dropped — so
    ``f"a{x}b"`` becomes ``["a", "b"]`` and the caller can rebuild it as a pattern with a wildcard
    between the fragments. A plain literal yields a single-element list. Implicit concatenation is
    already resolved by the parser, so a message split across source lines arrives whole.

    :class:`ast.JoinedStr` nodes are **not** descended into: their child constants are the fragments
    being collected, and walking them as well would report every f-string twice.

    Args:
        source: A Python file to parse.

    Returns:
        One fragment list per string literal, in source order.
    """
    collected: list[list[str]] = []

    def visit(node: ast.AST) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.JoinedStr):
                collected.append(
                    [
                        part.value
                        for part in child.values
                        if isinstance(part, ast.Constant) and isinstance(part.value, str)
                    ]
                )
            elif isinstance(child, ast.Constant) and isinstance(child.value, str):
                collected.append([child.value])
            else:
                visit(child)

    visit(ast.parse(source.read_text(encoding="utf-8")))
    return collected


def _announcements() -> list[list[str]]:
    """Return the runner's user-facing stdout lines, as literal fragments, from its own AST.

    Returns:
        One fragment list per ``[planeswalker] …`` line ``server.run()`` can print.
    """
    return [
        fragments
        for fragments in _string_templates(SERVER_SOURCE_PATH)
        if fragments and fragments[0].startswith(_ANNOUNCEMENT_PREFIX)
    ]


def _announcement_pattern(fragments: list[str]) -> re.Pattern[str]:
    """Compile one announcement into a pattern whose interpolation slots are captured.

    Args:
        fragments: The literal runs of one announcement, in order.

    Returns:
        A pattern matching the rendered line on a single README line, with one ``slot<N>`` group per
        interpolation.
    """
    parts = [re.escape(fragments[0])]
    for index, fragment in enumerate(fragments[1:]):
        parts.append(rf"(?P<slot{index}>[^\n]*?)")
        parts.append(re.escape(fragment))
    return re.compile("".join(parts))


def _match_announcement(section: str, fragments: list[str]) -> re.Match[str]:
    """Assert the section quotes one announcement verbatim, and return the match.

    Args:
        section: The extracted README section.
        fragments: The literal runs of the announcement, from :func:`_announcements`.

    Returns:
        The match, so a caller can inspect what the README put in the interpolation slots.
    """
    rendered = "…".join(fragments)
    match = _announcement_pattern(fragments).search(section)
    assert match is not None, (
        f"README's {SECTION_HEADING!r} section does not quote the line server.run() prints:\n"
        f"    {rendered}\n"
        "(the … marks an interpolated value, which may be anything). The runner's wording changed "
        "and the README's did not, or the quoted block was reworded into a paraphrase — a user "
        "matching what is on their terminal against the README has to find the same characters, "
        "em dashes included. Fix README.md."
    )
    return match


def _panel_copy(reason: str) -> dict[str, str]:
    """Return the shipped StatePanel copy for one error reason, read out of the SPA's source.

    The lookup key is the **kebab spelling of the shipped reason token**, not a name this module
    remembers, so the block read here is provably the block the reason drives.

    Args:
        reason: A member of :data:`src.companion.contracts.ErrorReason`.

    Returns:
        ``headline``, ``action`` and ``guidance`` as the SPA declares them.
    """
    assert reason in get_args(ErrorReason), (
        f"{reason!r} is not one of the shipped ErrorReason tokens {get_args(ErrorReason)} — the "
        "token was renamed, and the panel this module reads is no longer the one it thinks it is"
    )
    source = STATE_PANEL_COPY_PATH.read_text(encoding="utf-8")
    key = reason.replace("_", "-")
    blocks = {
        match.group("key"): match.group("body") for match in _STATE_PANEL_BLOCK.finditer(source)
    }
    assert key in blocks, (
        f"{STATE_PANEL_COPY_PATH.name} has no {key!r} entry, which is the kebab spelling of the "
        f"shipped {reason!r} reason token. Either the panel copy moved (this module must follow "
        "it) or the fresh-install state lost its panel — in which case README's first-run "
        "narrative is describing a screen that no longer exists."
    )
    body = blocks[key]
    found = {}
    for field, pattern in (
        ("headline", _HEADLINE),
        ("action", _copy_call("action")),
        ("guidance", _copy_call("guidance")),
    ):
        match = pattern.search(body)
        assert match is not None, (
            f"the {key!r} panel copy declares no {field} — README quotes all three lines, so a "
            "missing one means the guard would silently stop checking a sentence the README still "
            "shows the reader"
        )
        found[field] = match.group("text")
    return found


class TestTheCompanionSectionMatchesTheShippedApp:
    """README's release documentation against the code it describes (story 15-4)."""

    def test_the_documented_section_exists(self) -> None:
        """The anchor: nothing below this test means anything if the section is gone."""
        section = _extract_section(_read_readme())

        assert section.startswith(SECTION_HEADING)
        assert len(section.splitlines()) > 40, (
            f"{SECTION_HEADING!r} is present but nearly empty — the guard would pass vacuously on "
            "a stub. Restore the companion documentation in README.md."
        )
        assert NEIGHBOUR_HEADING not in section, (
            f"the extraction swallowed {NEIGHBOUR_HEADING!r}, story 15-2's section. Every "
            "'the section says X' assertion below would then be able to pass on that section's "
            "prose instead of this one's — fix the bound in _extract_section, not the README."
        )

    def test_every_line_the_runner_prints_is_quoted_verbatim(self) -> None:
        """Matrix rows 1, 2, 3 and 4: all four stdout lines, from the runner's own AST.

        The count is asserted first. A fifth announcement added to ``server.run()`` fails here until
        the README quotes it too, which is the whole point: the section promises a reader that what
        they see on their terminal is written down.
        """
        announcements = _announcements()

        assert len(announcements) == _EXPECTED_ANNOUNCEMENTS, (
            f"{SERVER_SOURCE_PATH.name} prints {len(announcements)} {_ANNOUNCEMENT_PREFIX!r} "
            f"lines, not {_EXPECTED_ANNOUNCEMENTS}. Either a new line reaches the user and "
            "README's companion section does not mention it (document it, then raise the count), "
            "or one was removed and the README still promises it."
        )

        section = _extract_section(_read_readme())
        for fragments in announcements:
            _match_announcement(section, fragments)

    def test_the_quoted_launch_line_carries_the_shipped_host_and_default_port(self) -> None:
        """Matrix row 1: the URL in the launch line is ``HOST`` and ``DEFAULT_PORT``, not a memory.

        ``DEFAULT_PORT`` is "the single place in ``src/`` that names the number", so a change to it
        has exactly one prose consequence and this is where it lands.
        """
        section = _extract_section(_read_readme())
        launch = [f for f in _announcements() if "companion running at" in f[0]]
        assert len(launch) == 1, "server.run() no longer prints exactly one launch line"

        slots = _match_announcement(section, launch[0]).groupdict()

        assert slots["slot0"] == server.HOST, (
            f"README's launch line names {slots['slot0']!r} where the runner interpolates "
            f"server.HOST ({server.HOST!r}). The address the app binds and the address the README "
            "tells a user to open have to be the same string — the section explains at length why "
            "it is the literal rather than `localhost`."
        )
        assert slots["slot1"] == str(server.DEFAULT_PORT), (
            f"README's launch line names port {slots['slot1']!r} but server.DEFAULT_PORT is "
            f"{server.DEFAULT_PORT}. The default port moved and the prose did not."
        )

    def test_both_already_running_messages_are_documented_and_kept_apart(self) -> None:
        """Matrix rows 3 and 4: two refusals, and the difference between them is the point.

        One names a URL because a live companion was verified answering; the other refuses to name
        one because the other instance has not published its port yet. Collapsing them into a single
        sentence would document a system that does not exist, so both are pinned — and the one that
        must name a URL is checked for naming the *shipped* base URL, not merely some URL.
        """
        section = _extract_section(_read_readme())
        verified = [f for f in _announcements() if "is already running at" in f[0]]
        starting = [f for f in _announcements() if "already starting up" in f[0]]

        assert len(verified) == 1 and len(starting) == 1, (
            "server.run() no longer prints exactly one 'already running' and one 'already starting "
            "up' line — the README documents two distinct refusals and this guard can no longer "
            "tell which is which"
        )

        slot = _match_announcement(section, verified[0]).group("slot0")
        assert slot == client.base_url(server.DEFAULT_PORT), (
            f"README quotes the steady-state refusal naming {slot!r}, but the runner interpolates "
            f"client.base_url(port), which for the default port is "
            f"{client.base_url(server.DEFAULT_PORT)!r}."
        )

        _match_announcement(section, starting[0])
        assert "http://" not in "".join(starting[0]), (
            "the startup-window refusal now names a URL in its own literal text. It deliberately "
            "did not, because no URL can be stated honestly during another launch's startup "
            "window, and README's section explains that absence — reconcile the two."
        )

    def test_the_documented_launch_command_is_the_installed_console_script(self) -> None:
        """Matrix row 1: ``uv run <console script> <subcommand>``, both halves read from source.

        The script name comes from ``[project.scripts]`` and the subcommand from the dispatcher's
        own usage text, so a rename on either side lands here rather than on a user's terminal.
        """
        scripts = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))["project"]["scripts"]
        assert len(scripts) == 1, (
            f"pyproject declares {len(scripts)} console scripts {sorted(scripts)}; this guard "
            "assumes the one the README documents. Say which one the section means."
        )
        script_name = next(iter(scripts))

        subcommands = re.findall(
            r"^  (?P<name>\S+)\s+run the companion backend", entry_point._USAGE, re.M
        )
        assert len(subcommands) == 1, (
            "the dispatcher's usage text no longer names exactly one subcommand that runs the "
            f"companion backend (found {subcommands}); README's launch command cannot be derived"
        )
        command = f"uv run {script_name} {subcommands[0]}"

        section = _extract_section(_read_readme())
        assert command in section, (
            f"README's companion section never spells the launch command {command!r}, built from "
            f"pyproject's [project.scripts] and the dispatcher's usage text. The console script or "
            "the subcommand was renamed and the documentation was not."
        )
        assert f"```bash\n{command}\n```" in section, (
            f"{command!r} appears in prose but not as a copy-pasteable ```bash block of its own. "
            "The single documented launch command is the one thing in this section a reader will "
            "copy rather than read."
        )

    def test_the_default_port_and_both_overrides_are_the_shipped_ones(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Matrix row 5: precedence, the environment variable's name, and the accepted range.

        The precedence is not merely asserted as prose — it is *exercised* against
        :func:`server.resolve_preferred_port` first, so the sentence the README carries is checked
        against behaviour rather than against another sentence.
        """
        monkeypatch.setenv(server.PORT_ENV_VAR, str(server.DEFAULT_PORT + 2))
        assert server.resolve_preferred_port(server.DEFAULT_PORT + 1) == server.DEFAULT_PORT + 1
        assert server.resolve_preferred_port(None) == server.DEFAULT_PORT + 2
        assert server.resolve_preferred_port(server._MAX_PORT + 1) == server.DEFAULT_PORT
        monkeypatch.delenv(server.PORT_ENV_VAR)
        assert server.resolve_preferred_port(None) == server.DEFAULT_PORT

        section = _extract_section(_read_readme())

        assert f"**{server.DEFAULT_PORT}**" in section, (
            f"the section does not name server.DEFAULT_PORT ({server.DEFAULT_PORT}) as the port "
            "the companion prefers"
        )
        assert server.PORT_ENV_VAR in section, (
            f"the section never names {server.PORT_ENV_VAR}, the only environment variable that "
            "moves the companion's port — a reader has no way to discover it from the app itself"
        )
        precedence = f"`--port` beats `{server.PORT_ENV_VAR}`"
        assert precedence in section, (
            f"the section does not state the measured precedence {precedence!r}. The exercises "
            "above prove --port wins; the README has to say so, because a user who sets both and "
            "gets the other one has no way to tell which was supposed to win."
        )
        assert f"`{server._MIN_PORT}..{server._MAX_PORT}`" in section, (
            f"the accepted range is {server._MIN_PORT}..{server._MAX_PORT} (server._MIN_PORT / "
            "server._MAX_PORT) and the section does not say so"
        )
        assert "ignored" in section, (
            "the section does not say an out-of-range port is ignored — the distinction between "
            "ignored-with-a-warning and refused is the whole of matrix row 5's error handling"
        )

    def test_the_documented_exit_statuses_are_the_only_ones_the_dispatcher_returns(self) -> None:
        """Matrix rows 3, 5 and 8: ``0`` for every companion outcome, ``2`` only for a typo.

        Both halves are read from the entry point rather than from memory: every integer ``return``
        in the dispatcher's AST, and the status a malformed ``--port`` actually produces when
        :func:`main` is called.
        """
        returns = {
            node.value.value
            for node in ast.walk(ast.parse(ENTRY_POINT_SOURCE_PATH.read_text(encoding="utf-8")))
            if isinstance(node, ast.Return)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, int)
        }
        assert returns == {0, 2}, (
            f"{ENTRY_POINT_SOURCE_PATH.name} returns the statuses {sorted(returns)}; README's "
            "companion section tells the reader 2 is the only non-zero status the program mints. A "
            "new status is a new thing a user can see and must be documented."
        )
        assert entry_point.main(["companion", "--port", "not-an-integer"]) == 2
        assert entry_point.main(["companion", "--help"]) == 0

        section = _extract_section(_read_readme())
        assert "exits `2`" in section, (
            "the section does not tell a reader that a malformed --port exits 2, which is the one "
            "failure status this program can produce"
        )
        assert "exit `0`" in section or "exits `0`" in section, (
            "the section does not state the exit status of an ordinary companion run — a user who "
            "sees 'already running' and checks $LASTEXITCODE must not conclude something failed"
        )

    def test_the_discovery_and_lock_filenames_are_the_shipped_constants(self) -> None:
        """Matrix rows 8 and 9: what a clean stop removes, and what an unclean exit leaves.

        Both names are keyed on the constant that spells them, so a rename moves the prose with it —
        the same pin story 15-2's leftovers list carries, applied to the paragraph that explains
        *why* those files are there.
        """
        section = _extract_section(_read_readme())

        for name, symbol in (
            (discovery.COMPANION_FILENAME, "discovery.COMPANION_FILENAME"),
            (singleton.LOCK_FILENAME, "singleton.LOCK_FILENAME"),
        ):
            assert name in section, (
                f"the section never names {name!r} ({symbol}). A reader who finds it in their data "
                "directory, or who wants to know what a crash left behind, has nothing to match it "
                "against."
            )

        assert "sole" in section and "no port scan" in section, (
            f"the section does not say {discovery.COMPANION_FILENAME} is the sole rendezvous with "
            "no port scan — that is what makes an ephemeral port harmless rather than alarming"
        )
        assert "deliberately" in section, (
            f"the section lists {singleton.LOCK_FILENAME} as a leftover without saying it is left "
            "behind deliberately; an undeclared leftover reads as a bug, and deleting it out from "
            "under a running app is a correctness bug"
        )
        assert "stale" in section and "reclaims" in section, (
            "the section does not describe an unclean exit as leaving a stale discovery file that "
            "the next launch reclaims — matrix row 9 calls that the expected post-crash state, and "
            "a reader who is not told will try to clean it up by hand"
        )

    def test_the_fresh_install_narrative_quotes_the_shipped_panel(self) -> None:
        """Matrix row 6: the app starts anyway, and the page says what the SPA actually says.

        All three lines come out of ``StatePanel/copy.ts`` at the entry keyed by the shipped
        ``database_not_initialized`` token, and the database file name comes from the path builder —
        so a reworded panel or a renamed file fails here rather than at a confused user.
        """
        section = _extract_section(_read_readme())
        copy = _panel_copy("database_not_initialized")

        for field, text in copy.items():
            assert text in section, (
                f"README's first-run narrative does not quote the panel's {field}:\n    {text}\n"
                "The reader is told what the page will say so they can recognise it; a "
                "paraphrase of a screen is not a description of it. Update README.md to match the "
                "shipped copy."
            )

        assert paths.database_path().name in section, (
            f"the section never names {paths.database_path().name}, the file whose absence the "
            "whole first-run narrative is about"
        )
        assert "starts" in section and "no restart" in section, (
            "the section does not say both halves of matrix row 6: the app starts anyway with no "
            "database, and it picks one up with no restart because readiness is re-probed per "
            "request. Either half alone leaves the reader restarting the app for no reason."
        )

    def test_the_failed_import_recovery_says_stop_the_app_first(self) -> None:
        """Matrix row 7: F4, documented rather than fixed — so the recovery must be exact.

        A partial database that a running companion has opened cannot be deleted or replaced until
        the app stops. The order of the two steps is the whole content of the fix, so it is pinned
        as an ordered claim rather than as two present words.
        """
        section = _extract_section(_read_readme())

        marker = "Recovering from a failed first import"
        assert marker in section, (
            "the section carries no failed-first-import recovery. F4 is a known, unfixed defect "
            "reachable on a public release; story 15-4's ruling was to document it, so removing "
            "the paragraph removes the only thing standing between a user and a stuck install."
        )
        recovery = section[section.index(marker) :]
        assert "Stop the companion first" in recovery, (
            "the recovery paragraph does not tell the reader to stop the companion first, which is "
            "the only step that makes the rest possible — a running app holds the partial database"
        )
        stop = recovery.index("Stop the companion first")
        for step in ("delete", "re-run the import"):
            assert step in recovery[stop:], (
                f"the recovery paragraph does not name {step!r} after stopping the app; the order "
                "is the fix, and a recovery given out of order does not work"
            )

    def test_the_section_says_the_companion_is_optional(self) -> None:
        """Story 15-4's first acceptance criterion, and the epic's standing guarantee.

        The status token is read off ``SetActiveDeckResult``'s closed set rather than typed here, so
        a renamed outcome cannot leave the README promising a word the tools no longer return.
        """
        section = _extract_section(_read_readme())
        statuses = get_args(SetActiveDeckResult.model_fields["status"].annotation)
        not_running = [status for status in statuses if "not_running" in status]
        assert len(not_running) == 1, (
            f"SetActiveDeckResult's statuses {sorted(statuses)} no longer contain exactly one "
            "'not running' outcome — the README names the one the tools report with the app closed"
        )

        assert "optional" in section, (
            "the section never says the companion is optional. Every agent workflow completes with "
            "the app closed, and that guarantee is the reason the deprecation of view_deck is safe."
        )
        assert "with the app closed" in section, (
            "the section does not state plainly that every agent workflow completes with the app "
            "closed — 'optional' alone leaves a reader wondering what they lose"
        )
        assert not_running[0] in section, (
            f"the section does not name the {not_running[0]!r} status the companion tools report "
            "when the app is not up, so a reader who sees it has nowhere to look it up"
        )

    def test_the_section_says_node_is_never_required_and_pyproject_agrees(self) -> None:
        """SC-4: a fresh install launches with one ``uv`` command and no build step.

        The claim is checked against ``pyproject.toml`` before it is checked against the prose: if
        ``fastapi`` or ``uvicorn`` ever moved into an extra or a dependency group, the README's
        "no extra, no dependency group" sentence would be false and this fails on the *code* side.
        """
        pyproject = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
        base = {re.split(r"[<>=!\[ ]", spec)[0] for spec in pyproject["project"]["dependencies"]}
        assert {"fastapi", "uvicorn"} <= base, (
            f"fastapi and uvicorn are no longer both base dependencies (found {sorted(base)}). "
            "README's companion section tells the reader there is no extra and no dependency group "
            "to install — that sentence is now false."
        )

        section = _extract_section(_read_readme())
        assert "Node is never required" in section, (
            "the section does not state that Node is never required at install or runtime. The "
            "absence of a Node prerequisite is the point of the committed bundle, and a reader who "
            "is not told assumes an npm step."
        )
        assert "change" in section and "ui/" in section, (
            "the section states the Node claim without its honest caveat — Node *is* required to "
            "change the UI, and a claim without its exception is the kind of promise that gets "
            "found out"
        )

    def test_ordinary_prose_edits_elsewhere_in_the_readme_do_not_move_this_guard(self) -> None:
        """The silent half: this guard is about one section and must ignore the rest of the file.

        A guard that fires on any README edit gets disabled by the third person it inconveniences.
        Edits before *and* after the section are both exercised, because the extraction is bounded
        at both ends — and the trailing cases are the two heading levels that must terminate it.
        """
        original = _read_readme()
        section = _extract_section(original)

        edited_before = original.replace(
            SECTION_HEADING, "An unrelated prose edit above the companion.\n\n" + SECTION_HEADING, 1
        )
        assert edited_before != original, "the fixture text for this test no longer exists"
        assert _extract_section(edited_before) == section, (
            "an edit above the section changed what the guard reads — the extraction is not "
            "bounded at its start"
        )

        for trailing in (
            "\n## A brand new trailing section\n\nMore unrelated prose.\n",
            "\n# A trailing top-level heading\n\nMore unrelated prose.\n",
        ):
            assert _extract_section(original + trailing) == section, (
                f"the trailing block {trailing.splitlines()[1]!r} changed what the guard reads — "
                "the extraction is not bounded at its end"
            )

    def test_the_sections_own_subheadings_stay_inside_it(self) -> None:
        """The counterpart bound, and the one story 15-2's guard does not need.

        This section owns six ``###`` subsections. A terminator that stopped at any ATX level would
        cut the extraction off after two paragraphs, and every "the section says X" assertion above
        would then fail with a message about prose that is plainly there.
        """
        original = _read_readme()
        section = _extract_section(original)

        subheadings = [
            line
            for line in section.splitlines()
            if _ATX_HEADING.match(line) and line != SECTION_HEADING
        ]
        assert len(subheadings) >= 4, (
            f"the extraction found only {len(subheadings)} subheading(s) inside "
            f"{SECTION_HEADING!r}. Either the section was flattened (in which case this bound no "
            "longer needs proving) or the terminator regressed to stopping at any ATX level."
        )

        planted = original.replace(
            SECTION_HEADING, SECTION_HEADING + "\n\n#### A planted sub-subsection\n\nProse.", 1
        )
        assert "#### A planted sub-subsection" in _extract_section(planted), (
            "a `####` sub-subsection truncated the section — a heading deeper than this section's "
            "own level is part of it, not its terminator"
        )

    def test_a_heading_inside_a_fenced_block_does_not_truncate_the_section(self) -> None:
        """A ``## `` line inside a fence is sample text, and the scan must read it as such.

        This section quotes shell commands, so a documented comment or a markdown sample could
        otherwise end the section early and hide the rest of it from every assertion above.
        """
        original = _read_readme()
        section = _extract_section(original)
        planted = original.replace(
            SECTION_HEADING,
            SECTION_HEADING + "\n\n```bash\n## this is a shell comment, not a heading\n```",
            1,
        )

        extracted = _extract_section(planted)

        assert "## this is a shell comment" in extracted, (
            "a `##` line inside a fenced block truncated the section — the extraction is not "
            "fence-aware, so a documented shell comment can hide the rest of the section from "
            "every assertion in this module"
        )
        assert extracted.endswith(section.split("\n", 1)[1]), (
            "the fenced sample changed where the section ends, not only what it contains"
        )
