"""Drift guard over story 15-4's release documentation — the companion guide
(``docs/companion.md``), README's ``## Requirements`` claim that repeats its Node promise, and the
Scryfall attribution in ``README.md`` and ``NOTICE``.

The operating prose lived in ``README.md`` as ``## The companion app`` until the README was
restructured: the deep-dive subsections moved verbatim into ``docs/companion.md`` under
``# The companion app — full guide``, and README keeps a shortened section that links into it.
This module follows the prose — its section is now the whole guide — while the claims that stayed
in README (``## Requirements``, the ``## What it does`` capability table, the attribution) are
still read out of README.

The guide is the only place a first-time user is told how to start the companion, what the app
prints, which port it picks, what a second launch does, and what a fresh install with no card
database looks like. Every one of those claims is true only because a constant, a message literal or
an entry-point return currently says so — and prose has no compiler, so this module is the compiler.
The idiom is ``test_image_cache_docs.py``'s, story 15-2's guard over the section immediately below
this one, and the pins follow the same rule: **key on the shipped symbol, never on a literal copied
out of the documentation**, so a rename that updates the prose moves the pin with it and a rename
that does not turns this red.

Where a value has no constant to import, the source file is parsed rather than transcribed. The four
``[planeswalker]`` announcements are lifted out of ``src/companion/app/server.py``'s AST — f-strings
included, with their interpolation slots rendered as wildcards and then checked against ``HOST`` and
``DEFAULT_PORT`` — so the guide quotes the runner's own words, em dashes and all, and gaining a
fifth announcement fails here until the guide grows one too. The exit statuses are read the same
way, off every integer ``return`` in the dispatcher, and the fresh-install panel copy is read out of
``ui/src/components/StatePanel/copy.ts`` at the entry whose key is the kebab spelling of the shipped
``database_not_initialized`` reason token.

**One deliberate divergence from ``test_image_cache_docs.py``.** That module terminates its scan on
an ATX heading of *any* level, because ``## Image cache`` owns no subsections. This section does own
them — the guide's ``##`` headings — so :func:`_extract_section` terminates on a heading of the
section's own level or higher, derived from :data:`SECTION_HEADING` rather than hardcoded. The
heading is now the guide's single ``#`` title, so the extraction is the whole file — which is the
point: everything in ``docs/companion.md`` is this module's remit, the image-cache section
included (:data:`OWNED_SUBSECTION_HEADING` pins that it is still there; story 15-2's guard reads it
by its own heading from the same file). Both bounds are tested rather than asserted in prose, and
because the section runs to end-of-file the extraction drops trailing blank lines, so a bounded and
an EOF-terminated extraction of the same prose compare equal.

**Declared residue — what this guard does NOT prove:**

1. **No process is started and no socket is bound.** That the launch line is the *only* line the
   user sees depends on uvicorn suppressing its own banner when handed a pre-bound socket, and the
   ephemeral fallback depends on a real ``OSError`` at bind time. Neither is exercised here — both
   belong to ``tests/unit/companion/test_server.py``, which owns the runner. This module proves only
   that the guide quotes the messages the runner would print, character for character.
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
   no test in this repository (deliberately — a changelog is a record, not a contract) and the
   ``plugin/`` mirror of ``README.md`` is covered by CI's rebuild-and-diff rather than by an
   assertion here. ``ui/tests/attribution.test.ts`` pins the footer's hrefs against ``NOTICE`` from
   the app's side; what it cannot see is the attribution's *subject*, which is what
   :class:`TestTheAttributionNamesWhatTheAppActuallyUses` adds from this side.
5. **The failed-import recovery is prose about a defect, not a reproduction of it.** F4 (a
   schema-only ``cards.db`` a running companion has opened) is documented, not fixed; this module
   checks the recovery names stopping the app first and names the database file the shipped path
   builder builds. It never plants a partial database.
6. **Two formatting pins are deliberate, and they are the only two.** Prose claims are compared
   through :func:`_claim`, which collapses whitespace and drops ``*`` and backticks — so re-wrapping
   a paragraph, or emphasising a word, cannot turn this module red. The exceptions:
   :func:`_announcement_pattern` matches each quoted announcement on **one line**, because that is
   what a user comparing the guide against their terminal needs (a ~140-character line in a file
   that wraps at ~95-100 columns, kept in a fenced block for exactly that reason); and the launch
   command must appear as a line of its own inside a fenced block, because it is the one thing in
   the section a reader copies rather than reads. Both are stated here rather than discovered.
7. **Anchors are checked for resolution, not for aim.** :meth:`…test_every_link_anchor_resolves`
   proves each ``](#slug)`` names a heading in the same file — in ``README.md`` *and* in
   ``docs/companion.md`` — and that every cross-document ``docs/companion.md#slug`` /
   ``../README.md#slug`` anchor names a heading in the file it points at. It cannot tell that the
   heading it names is the *useful* one. And renaming a heading is therefore not the "one edit" a
   naive reader might assume: it moves this module's constant, the heading, and every link — in-page
   or cross-document — that pointed at it.
"""

import ast
import re
import tomllib
from pathlib import Path
from typing import get_args

import pytest

from src import paths
from src.companion import client, discovery
from src.companion.app import images, server, singleton
from src.companion.contracts import ErrorReason
from src.mcp_server import __main__ as entry_point
from src.mcp_server.tools.companion import SetActiveDeckResult, ShowSuggestionsResult

# ---------------------------------------------------------------------------------------------
# Repository layout — resolved from __file__, never from the current working directory, exactly as
# tests/unit/companion/test_image_cache_docs.py does it.
# ---------------------------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[3]
README_PATH = REPO_ROOT / "README.md"
GUIDE_PATH = REPO_ROOT / "docs" / "companion.md"
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
SERVER_SOURCE_PATH = REPO_ROOT / "src" / "companion" / "app" / "server.py"
ENTRY_POINT_SOURCE_PATH = REPO_ROOT / "src" / "mcp_server" / "__main__.py"
STATE_PANEL_COPY_PATH = REPO_ROOT / "ui" / "src" / "components" / "StatePanel" / "copy.ts"
NOTICE_PATH = REPO_ROOT / "NOTICE"
FOOTER_COPY_PATH = REPO_ROOT / "ui" / "src" / "components" / "Footer" / "copy.ts"

SECTION_HEADING = "# The companion app — full guide"
"""The section this module is the compiler for: the guide's title, so the section is the file.

**Renaming it is not one edit.** It moves this constant and the heading in ``docs/companion.md`` —
and README reaches the guide through ``docs/companion.md#…`` links whose anchors
``test_every_link_anchor_resolves`` checks, so a retitle that breaks an anchor turns that test red
rather than scrolling a reader nowhere.
"""

README_COMPANION_HEADING = "## The companion app"
"""README's shortened companion section — the launch commands and the link list into the guide.

This module's prose pins moved to the guide with the prose; what is still read from README is how a
reader *arrives*: the in-page links that point at this section, and the links out of it into
``docs/companion.md``.
"""

CAPABILITY_HEADING = "## What it does"
"""The capability table, which claims BOTH companion tools report the not-running token."""

REQUIREMENTS_HEADING = "## Requirements"
"""The other place the Node claim is made — in README, outside the guide, and read first."""

OWNED_SUBSECTION_HEADING = "## Image cache"
"""Story 15-2's section, now *inside* this extraction — see the bounding test.

In README the image-cache section sat beside this one and had to stay outside the scan; in the
guide it is one of the sections the single ``#`` title owns, and its own guard
(``test_image_cache_docs.py``) reads it by this heading from the same file. The bounding test pins
its presence, so the two modules can never silently end up reading different documents.
"""

_ANNOUNCEMENT_PREFIX = "[planeswalker] "
"""This module's selector for a line ``run()`` prints to the user's terminal.

The code has no constant for it (declared residue 2), so the count below is the safety net: a prefix
that changed under this module would find nothing and fail on the count, never pass on an empty set.
"""

_EXPECTED_ANNOUNCEMENTS = 4
"""How many user-facing lines ``server.run()`` can print: launch, fallback, and the two refusals.

Not a style rule — every one of them is a line the guide promises the reader will recognise, so a
fifth arriving without a guide entry is exactly the drift this module exists to catch.
"""

# Any ATX heading, capturing its level, so the scan can terminate on a heading of this section's own
# level or higher while letting its own `###` subsections through. Up to three leading spaces, which
# is what CommonMark allows and therefore what GitHub renders as a heading.
_ATX_HEADING = re.compile(r"^ {0,3}(?P<hashes>#{1,6}) ")

# A fenced-code delimiter. Both markers markdown allows, not only backticks, and the same three
# leading spaces — a fence indented inside a list item is still a fence, and one this scan did not
# recognise would neither toggle nor be skipped, so a `## ` sample line inside it would end the
# section early or, worse, a heading-shaped line would be read as prose (review, 2026-08-19).
_FENCE = re.compile(r"^ {0,3}(?P<marker>`{3,}|~{3,})")

# `  'some-key': {` … `  },` in ui/src/components/StatePanel/copy.ts. Two-space indent on both ends,
# so a nested object inside the block cannot terminate it early.
_STATE_PANEL_BLOCK = re.compile(r"^  '(?P<key>[a-z0-9-]+)': \{\n(?P<body>.*?)^  \},$", re.M | re.S)

# Both quote styles, symmetrically with `_copy_call`: the shipped copy uses whichever the sentence
# needs, and a headline that gained an apostrophe would flip to double quotes. A pattern that
# accepted only one style would report the headline missing from a file that plainly has it.
_HEADLINE = re.compile(r"headline: (?P<q>['\"])(?P<text>.*?)(?P=q)", re.S)


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


def _claim(text: str) -> str:
    """Return *text* with whitespace collapsed and markdown emphasis removed.

    Prose claims are compared through this, so re-wrapping a paragraph at a different column or
    emphasising a different word cannot turn this module red — the module's own rule is to guard
    meaning, and a guard that fires on a cosmetic reword is the kind that gets deleted. Byte-exact
    comparisons are reserved for the things a user matches character by character: the quoted
    announcements and the quoted panel copy.

    Args:
        text: Any markdown.

    Returns:
        The same text as one space-separated line, without ``*`` or backticks.
    """
    return re.sub(r"\s+", " ", text.replace("*", "").replace("`", "")).strip()


def _fenced_bodies(section: str) -> list[str]:
    """Return the body of every fenced block in *section*, in document order."""
    bodies: list[str] = []
    marker: str | None = None
    body: list[str] = []
    for line in section.splitlines():
        opener = _FENCE.match(line)
        if opener is not None:
            char = opener.group("marker")[0]
            if marker is None:
                marker, body = char, []
            elif char == marker:
                bodies.append("\n".join(body))
                marker = None
            continue
        if marker is not None:
            body.append(line)
    return bodies


def _prose(section: str) -> str:
    """Return *section* with every fenced block removed.

    A claim asserted against the whole section can be satisfied by a *quoted transcript* of the
    app's own output rather than by the documentation saying anything — the default port, say,
    appears inside the quoted launch line whether or not the prose ever names it. Claims about what
    the section *tells* the reader are therefore checked against this.
    """
    kept: list[str] = []
    marker: str | None = None
    for line in section.splitlines():
        opener = _FENCE.match(line)
        if opener is not None:
            char = opener.group("marker")[0]
            if marker is None:
                marker = char
            elif char == marker:
                marker = None
            continue
        if marker is None:
            kept.append(line)
    return "\n".join(kept)


def _paragraphs_crediting(text: str, href: str) -> list[str]:
    """Return every blank-line-delimited paragraph in *text* that carries *href*.

    Scoping matters here and was measured (firing proof 12, 2026-08-19): a file-wide substring check
    for the attribution's subject passed with the attribution itself reverted, because the word
    survived in a *section heading* elsewhere in ``NOTICE``. A credit is a sentence, not a file, so
    the assertion has to read the sentence.

    Args:
        text: A whole document.
        href: The URL whose credit paragraphs are wanted.

    Returns:
        Every paragraph containing *href*, in document order.
    """
    return [block for block in re.split(r"\n\s*\n", text) if href in block]


def _headings(text: str) -> list[str]:
    """Return every ATX heading line in *text*, skipping fenced blocks.

    The guide's plugin-install section quotes shell comments that start with ``# `` at column
    zero; a naive line scan would read those as headings and mint slugs no heading owns, quietly
    widening the set a dead anchor could hide in.

    Args:
        text: A whole markdown document.

    Returns:
        The heading lines, in document order.
    """
    found: list[str] = []
    marker: str | None = None
    for line in text.splitlines():
        opener = _FENCE.match(line)
        if opener is not None:
            char = opener.group("marker")[0]
            if marker is None:
                marker = char
            elif char == marker:
                marker = None
            continue
        if marker is None and _ATX_HEADING.match(line):
            found.append(line)
    return found


def _slug(heading: str) -> str:
    """Return GitHub's in-page anchor for an ATX *heading* line.

    GitHub lowercases the text, drops everything that is not a word character, a hyphen or a space,
    and turns the remaining spaces into hyphens. Reimplemented rather than imported because the
    alternative is a dependency for one function, and the round-trip is exercised by the assertion
    that every link in the file resolves.
    """
    text = heading.lstrip(" #").strip().lower()
    return re.sub(r"[^\w\- ]", "", text).replace(" ", "-")


def _read_readme() -> str:
    """Return README.md's text, read from the repository root rather than the working directory."""
    assert PYPROJECT_PATH.exists(), f"{REPO_ROOT} is not the repository root"
    return README_PATH.read_text(encoding="utf-8")


def _read_guide() -> str:
    """Return docs/companion.md's text, read from the repository root, not the working directory."""
    assert PYPROJECT_PATH.exists(), f"{REPO_ROOT} is not the repository root"
    return GUIDE_PATH.read_text(encoding="utf-8")


def _extract_section(
    document: str, heading: str = SECTION_HEADING, source: str = "docs/companion.md"
) -> str:
    """Return one section, from its heading to the next heading of its level or higher.

    **The non-vacuity anchor.** Every assertion in this module reads what this returns, so a missing
    or renamed heading has to fail here, loudly and by name, rather than yield an empty string that
    every substring check would then pass over.

    Three bounding rules, one inherited and two deliberately different:

    * The scan is **fence-aware**, exactly as story 15-2's is. A heading-shaped line inside a fenced
      block is sample text, not a heading; the guide quotes shell commands whose comments start with
      ``#``, so without this a documented comment could truncate it mid-command.
    * The terminator is a heading of **this section's own level or higher**, derived from the hashes
      in :data:`SECTION_HEADING`. Story 15-2's guard terminates on any level because its section has
      no subsections; this one owns every ``##`` section in the guide, and terminating on any level
      would leave every assertion below reading only the guide's opening paragraphs.
    * **Trailing blank lines are dropped.** The default section is the guide's ``#`` title and runs
      to end-of-file, while a section bounded by a later heading keeps the blank separator before
      it — and the bounds test compares the two for equality, so the comparison has to be about
      prose rather than about where the file happens to end.

    Args:
        document: The full text of the file named by *source*.
        heading: The ATX heading line to extract from. Defaults to this module's own section; the
            README blocks (``## Requirements``, the capability table) are read with the same
            machinery rather than a second scanner.
        source: The file's repo-relative name, for failure messages only.

    Returns:
        The section's lines, heading included, trailing blank lines dropped, joined with newlines.
    """
    own_level = len(heading) - len(heading.lstrip("#"))
    lines = document.splitlines()
    starts = [i for i, line in enumerate(lines) if line.strip() == heading]
    assert starts, (
        f"{source} has no {heading!r} heading. Every claim this module guards against it lives in "
        f"that section, so its absence fails here rather than passing vacuously on an empty scan. "
        f"Restore the heading in {source}, or — if the section was deliberately renamed — update "
        f"{Path(__file__).name} to match (and every link anchor that pointed at it)."
    )
    assert len(starts) == 1, (
        f"{source} carries {len(starts)} lines reading {heading!r} (at lines "
        f"{[i + 1 for i in starts]}). This module would guard only the first, so a second copy is "
        "an unguarded duplicate rather than a harmless one — delete it, or reword it so it is not "
        "an exact heading match."
    )
    start = starts[0]
    end = len(lines)
    fence: str | None = None
    for i in range(start + 1, len(lines)):
        opener = _FENCE.match(lines[i])
        if opener is not None:
            char = opener.group("marker")[0]
            if fence is None:
                fence = char
            elif char == fence:
                fence = None
            continue
        if fence is not None:
            continue
        found = _ATX_HEADING.match(lines[i])
        if found is not None and len(found.group("hashes")) <= own_level:
            end = i
            break
    # An unclosed fence leaves every later line "inside" it, so the scan runs to EOF and the section
    # silently widens to the rest of the file — at which point every "the section says X" assertion
    # below is satisfiable by some other section's prose. That has to fail here, naming the cause.
    # (For the guide's own title the extraction is the whole file either way, but the guard still
    # matters there: an unclosed fence would swallow the rest of the guide's *headings* as prose.)
    assert fence is None, (
        f"a fenced block opened inside {source}'s {heading!r} section is never closed, so the "
        f"extraction ran to the end of the file with every later line read as sample text rather "
        f"than as prose and headings. Close the fence in {source}."
    )
    while end > start and not lines[end - 1].strip():
        end -= 1
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
        A pattern matching the rendered line on a single line of the guide, with one
        ``slot<N>`` group per interpolation.
    """
    parts = [re.escape(fragments[0])]
    for index, fragment in enumerate(fragments[1:]):
        parts.append(rf"(?P<slot{index}>[^\n]*?)")
        parts.append(re.escape(fragment))
    return re.compile("".join(parts))


def _match_announcement(section: str, fragments: list[str]) -> re.Match[str]:
    """Assert the section quotes one announcement verbatim, and return the match.

    Args:
        section: The extracted guide section.
        fragments: The literal runs of the announcement, from :func:`_announcements`.

    Returns:
        The match, so a caller can inspect what the guide put in the interpolation slots.
    """
    rendered = "…".join(fragments)
    match = _announcement_pattern(fragments).search(section)
    assert match is not None, (
        f"the guide's {SECTION_HEADING!r} section does not quote the line server.run() prints:\n"
        f"    {rendered}\n"
        "(the … marks an interpolated value, which may be anything). The runner's wording changed "
        "and the guide's did not, or the quoted block was reworded into a paraphrase — a user "
        "matching what is on their terminal against the guide has to find the same characters, "
        "em dashes included. Fix docs/companion.md."
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
        "it) or the fresh-install state lost its panel — in which case the guide's first-run "
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
            f"the {key!r} panel copy declares no {field} — the guide quotes all three lines, so a "
            "missing one means the guard would silently stop checking a sentence the guide still "
            "shows the reader"
        )
        text = match.group("text")
        # The literal is compared raw against the guide's rendered prose, so an escape sequence
        # would make the two differ in a way no author could see: `\\'` reads as a backslash
        # here and as an apostrophe on the glass. Rejected rather than half-decoded — decoding
        # TypeScript escapes properly is a parser, and a wrong parser here would be worse than no
        # guard.
        assert "\\" not in text, (
            f"the {key!r} panel's {field} literal contains a backslash escape ({text!r}). This "
            "module compares the literal against the guide's rendered prose, so it cannot tell "
            "what that escape renders as. Either write the character directly in copy.ts, or "
            "teach this module to decode it — do not leave the comparison quietly wrong."
        )
        found[field] = text
    return found


class TestTheCompanionSectionMatchesTheShippedApp:
    """The guide's release documentation against the code it describes (story 15-4)."""

    def test_the_documented_section_exists(self) -> None:
        """The anchor: nothing below this test means anything if the section is gone."""
        section = _extract_section(_read_guide())

        assert section.startswith(SECTION_HEADING)
        assert len(section.splitlines()) > 40, (
            f"{SECTION_HEADING!r} is present but nearly empty — the guard would pass vacuously on "
            "a stub. Restore the companion documentation in docs/companion.md."
        )
        # The inverse of the bound this test pinned when the section lived in README: there the
        # neighbouring image-cache section had to stay OUT of the scan; in the guide it is one of
        # the sections the title owns, and its own guard reads it by this heading from this file.
        # Losing it here means the two doc-guard modules no longer agree on where the prose lives.
        assert f"\n{OWNED_SUBSECTION_HEADING}\n" in section, (
            f"the extraction no longer contains {OWNED_SUBSECTION_HEADING!r}, story 15-2's "
            "section. The guide's title owns every section in the file, image cache included — "
            "either the section moved out of docs/companion.md (move test_image_cache_docs.py "
            "with it) or the extraction stopped short of it."
        )

    def test_every_line_the_runner_prints_is_quoted_verbatim(self) -> None:
        """Matrix rows 1, 2, 3 and 4: all four stdout lines, from the runner's own AST.

        The count is asserted first. A fifth announcement added to ``server.run()`` fails here until
        the guide quotes it too, which is the whole point: the guide promises a reader that what
        they see on their terminal is written down.
        """
        announcements = _announcements()

        assert len(announcements) == _EXPECTED_ANNOUNCEMENTS, (
            f"{SERVER_SOURCE_PATH.name} prints {len(announcements)} {_ANNOUNCEMENT_PREFIX!r} "
            f"lines, not {_EXPECTED_ANNOUNCEMENTS}. Either a new line reaches the user and "
            "the companion guide does not mention it (document it, then raise the count), "
            "or one was removed and the guide still promises it."
        )

        section = _extract_section(_read_guide())
        for fragments in announcements:
            _match_announcement(section, fragments)

    def test_the_quoted_launch_line_carries_the_shipped_host_and_default_port(self) -> None:
        """Matrix row 1: the URL in the launch line is ``HOST`` and ``DEFAULT_PORT``, not a memory.

        ``DEFAULT_PORT`` is "the single place in ``src/`` that names the number", so a change to it
        has exactly one prose consequence and this is where it lands.
        """
        section = _extract_section(_read_guide())
        launch = [f for f in _announcements() if "companion running at" in f[0]]
        assert len(launch) == 1, "server.run() no longer prints exactly one launch line"

        slots = _match_announcement(section, launch[0]).groupdict()

        assert slots["slot0"] == server.HOST, (
            f"the guide's launch line names {slots['slot0']!r} where the runner interpolates "
            f"server.HOST ({server.HOST!r}). The address the app binds and the address the guide "
            "tells a user to open have to be the same string — the section explains at length why "
            "it is the literal rather than `localhost`."
        )
        assert slots["slot1"] == str(server.DEFAULT_PORT), (
            f"the guide's launch line names port {slots['slot1']!r} but server.DEFAULT_PORT is "
            f"{server.DEFAULT_PORT}. The default port moved and the prose did not."
        )

    def test_the_quoted_fallback_line_names_the_shipped_default_port(self) -> None:
        """Matrix row 2: the port in the fallback example is ``DEFAULT_PORT``, not any port.

        The gap this closes was measured, not argued (review, 2026-08-19): the fallback
        announcement's port sits in an interpolation slot, so ``port 8765`` rewritten to
        ``port 9999`` left all fifteen tests green. It is the residue of this module's own firing
        proof 8 — moving ``DEFAULT_PORT`` turns three tests red, and fixing those three still leaves
        the fallback example naming the retired port.
        """
        section = _extract_section(_read_guide())
        fallback = [f for f in _announcements() if "is unavailable" in "".join(f)]
        assert len(fallback) == 1, "server.run() no longer prints exactly one fallback line"

        slot = _match_announcement(section, fallback[0]).group("slot0")

        assert slot == str(server.DEFAULT_PORT), (
            f"the guide's fallback example says port {slot!r} is unavailable, but the port the app "
            f"would have preferred is server.DEFAULT_PORT ({server.DEFAULT_PORT}). The example "
            "shows a reader a conflict on a port the app never tries."
        )

    def test_both_already_running_messages_are_documented_and_kept_apart(self) -> None:
        """Matrix rows 3 and 4: two refusals, and the difference between them is the point.

        One names a URL because a live companion was verified answering; the other refuses to name
        one because the other instance has not published its port yet. Collapsing them into a single
        sentence would document a system that does not exist, so both are pinned — and the one that
        must name a URL is checked for naming the *shipped* base URL, not merely some URL.
        """
        section = _extract_section(_read_guide())
        verified = [f for f in _announcements() if "is already running at" in f[0]]
        starting = [f for f in _announcements() if "already starting up" in f[0]]

        assert len(verified) == 1 and len(starting) == 1, (
            "server.run() no longer prints exactly one 'already running' and one 'already starting "
            "up' line — the guide documents two distinct refusals and this guard can no longer "
            "tell which is which"
        )

        slot = _match_announcement(section, verified[0]).group("slot0")
        assert slot == client.base_url(server.DEFAULT_PORT), (
            f"the guide quotes the steady-state refusal naming {slot!r}, but the runner "
            f"interpolates client.base_url(port), which for the default port is "
            f"{client.base_url(server.DEFAULT_PORT)!r}."
        )

        _match_announcement(section, starting[0])
        assert "http://" not in "".join(starting[0]), (
            "the startup-window refusal now names a URL in its own literal text. It deliberately "
            "did not, because no URL can be stated honestly during another launch's startup "
            "window, and the guide explains that absence — reconcile the two."
        )

    def test_the_documented_launch_command_is_the_installed_console_script(self) -> None:
        """Matrix row 1: ``uv run <console script> <subcommand>``, both halves read from source.

        The script name comes from ``[project.scripts]`` and the subcommand from the dispatcher's
        own usage text, so a rename on either side lands here rather than on a user's terminal.
        """
        scripts = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))["project"]["scripts"]
        assert len(scripts) == 1, (
            f"pyproject declares {len(scripts)} console scripts {sorted(scripts)}; this guard "
            "assumes the one the guide documents. Say which one the section means."
        )
        script_name = next(iter(scripts))

        subcommands = re.findall(
            r"^  (?P<name>\S+)\s+run the companion backend", entry_point._USAGE, re.M
        )
        assert len(subcommands) == 1, (
            "the dispatcher's usage text no longer names exactly one subcommand that runs the "
            f"companion backend (found {subcommands}); the guide's launch command cannot be derived"
        )
        command = f"uv run {script_name} {subcommands[0]}"

        section = _extract_section(_read_guide())
        assert command in section, (
            f"the companion guide never spells the launch command {command!r}, built from "
            f"pyproject's [project.scripts] and the dispatcher's usage text. The console script or "
            "the subcommand was renamed and the documentation was not."
        )
        assert any(command in body.splitlines() for body in _fenced_bodies(section)), (
            f"{command!r} appears in the section but never as a line of its own inside a fenced "
            "block. The single documented launch command is the one thing here a reader copies "
            "rather than reads, and a command that has to be picked out of a sentence is one they "
            "will get wrong. (The fence's language tag is not pinned — only that there is one.)"
        )

    def test_the_default_port_and_both_overrides_are_the_shipped_ones(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Matrix row 5: precedence, the environment variable's name, and the accepted range.

        The precedence is not merely asserted as prose — it is *exercised* against
        :func:`server.resolve_preferred_port` first, so the sentence the guide carries is checked
        against behaviour rather than against another sentence.
        """
        # If DEFAULT_PORT ever moved near the ceiling these probes would exceed _MAX_PORT and the
        # test would silently invert into asserting the *ignore* path — passing while proving the
        # opposite of what it claims (review, 2026-08-19).
        explicit, from_env = server.DEFAULT_PORT + 1, server.DEFAULT_PORT + 2
        assert server._MIN_PORT <= explicit <= server._MAX_PORT, "probe port out of range"
        assert server._MIN_PORT <= from_env <= server._MAX_PORT, "probe port out of range"

        monkeypatch.setenv(server.PORT_ENV_VAR, str(from_env))
        assert server.resolve_preferred_port(explicit) == explicit
        assert server.resolve_preferred_port(None) == from_env
        assert server.resolve_preferred_port(server._MAX_PORT + 1) == server.DEFAULT_PORT
        monkeypatch.delenv(server.PORT_ENV_VAR)
        assert server.resolve_preferred_port(None) == server.DEFAULT_PORT

        section = _extract_section(_read_guide())

        prose = _claim(_prose(section))
        assert f"prefers port {server.DEFAULT_PORT}" in prose, (
            f"the section's prose does not name server.DEFAULT_PORT ({server.DEFAULT_PORT}) as the "
            "port the companion prefers. Asserted against the prose with fenced blocks removed, "
            "on purpose: the number appears inside the quoted launch line whether or not the "
            "documentation ever tells the reader what it is."
        )
        assert server.PORT_ENV_VAR in section, (
            f"the section never names {server.PORT_ENV_VAR}, the only environment variable that "
            "moves the companion's port — a reader has no way to discover it from the app itself"
        )
        precedence = f"--port beats {server.PORT_ENV_VAR}"
        assert precedence in prose, (
            f"the section does not state the measured precedence {precedence!r}. The exercises "
            "above prove --port wins; the guide has to say so, because a user who sets both and "
            "gets the other one has no way to tell which was supposed to win."
        )
        assert f"{server._MIN_PORT}..{server._MAX_PORT}" in prose, (
            f"the accepted range is {server._MIN_PORT}..{server._MAX_PORT} (server._MIN_PORT / "
            "server._MAX_PORT) and the section does not say so"
        )
        assert "ignored with a logged warning" in prose, (
            "the section does not say an out-of-range or unparseable port is *ignored with a "
            "logged warning*. 'Ignored' alone survives a reword that drops the warning, and the "
            "warning is the half that tells a user their configuration did nothing — the "
            "distinction between ignored-with-a-warning and refused is all of matrix row 5's error "
            "handling."
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
            f"{ENTRY_POINT_SOURCE_PATH.name} returns the statuses {sorted(returns)}; the guide's "
            "companion section tells the reader 2 is the only non-zero status the program mints. A "
            "new status is a new thing a user can see and must be documented."
        )
        # The AST walk above reads `return <int>` only. A `sys.exit(3)` would produce a status the
        # walk cannot see, and the guide's "the only non-zero status it ever returns" would become
        # unfalsifiable rather than false (review, 2026-08-19). The dispatcher's own docstring says
        # nothing here calls sys.exit; this is that sentence, enforced.
        exits = [
            node
            for node in ast.walk(ast.parse(ENTRY_POINT_SOURCE_PATH.read_text(encoding="utf-8")))
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "exit"
        ]
        assert not exits, (
            f"{ENTRY_POINT_SOURCE_PATH.name} now calls sys.exit at line(s) "
            f"{[node.lineno for node in exits]}. The exit status stops being the value main() "
            "returns, so the AST check above no longer sees every status a user can observe and "
            "the guide's claim about the only non-zero status cannot be checked at all."
        )

        assert entry_point.main(["companion", "--port", "not-an-integer"]) == 2
        assert entry_point.main(["companion", "--help"]) == 0

        section = _extract_section(_read_guide())
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
        section = _extract_section(_read_guide())

        for name, symbol in (
            (discovery.COMPANION_FILENAME, "discovery.COMPANION_FILENAME"),
            (singleton.LOCK_FILENAME, "singleton.LOCK_FILENAME"),
        ):
            assert name in section, (
                f"the section never names {name!r} ({symbol}). A reader who finds it in their data "
                "directory, or who wants to know what a crash left behind, has nothing to match it "
                "against."
            )

        claims = _claim(section)
        assert "sole rendezvous" in claims and "no port scan" in claims, (
            f"the section does not say {discovery.COMPANION_FILENAME} is the sole rendezvous with "
            "no port scan — that is what makes an ephemeral port harmless rather than alarming"
        )
        assert "behind deliberately" in claims, (
            f"the section lists {singleton.LOCK_FILENAME} as a leftover without saying it is left "
            "behind deliberately; an undeclared leftover reads as a bug, and deleting it out from "
            "under a running app is a correctness bug"
        )
        assert "stale" in claims and "reclaims it" in claims, (
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
        section = _extract_section(_read_guide())
        copy = _panel_copy("database_not_initialized")

        for field, text in copy.items():
            assert text in section, (
                f"the guide's first-run narrative does not quote the panel's {field}:\n    {text}\n"
                "The reader is told what the page will say so they can recognise it; a "
                "paraphrase of a screen is not a description of it. Update docs/companion.md to "
                "match the shipped copy."
            )

        assert paths.database_path().name in section, (
            f"the section never names {paths.database_path().name}, the file whose absence the "
            "whole first-run narrative is about"
        )
        claims = _claim(section)
        assert "starts anyway" in claims and "no restart" in claims, (
            "the section does not say both halves of matrix row 6: the app starts anyway with no "
            "database, and it picks one up with no restart because readiness is re-probed per "
            "request. Either half alone leaves the reader restarting the app for no reason."
        )

    def test_the_failed_import_recovery_says_stop_the_app_first(self) -> None:
        """Matrix row 7: F4, documented rather than fixed — so the recovery must be exact.

        A partial database that a running companion has opened needs the app stopped before it can
        be replaced. The order of the two steps is the whole content of the fix, so it is pinned as
        an ordered claim rather than as two present words.

        The platform split is pinned with it (Greptile P2, PR #88, 2026-08-19). The paragraph first
        claimed the delete was blocked everywhere, which is true only on Windows: POSIX unlink
        succeeds while the pooled connections keep the old inode alive
        (``AsyncAdaptedQueuePool``, ``deps.py:305``), so a re-import lands a new file the companion
        never reads and the page never heals. That is the *quieter* failure and the one worth
        naming, so a future tidy-up may not collapse the two platforms back into one sentence.
        """
        section = _extract_section(_read_guide())

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
        before = _claim(recovery[:stop])
        for platform in ("Windows", "macOS and Linux"):
            assert platform in before, (
                f"the recovery paragraph does not name {platform!r} before the fix. The two "
                "platforms fail differently — Windows refuses the delete, POSIX allows it and "
                "strands the companion on the old file — and a single unqualified claim is wrong "
                "on one of them whichever way it is written"
            )
        assert "never fills in" in before or "never heals" in before, (
            "the recovery paragraph names both platforms but not the POSIX consequence. The "
            "delete succeeding is not the problem; the companion going on reading the replaced "
            "file is, and that is the half a reader cannot discover for themselves"
        )

    def test_the_section_says_the_companion_is_optional(self) -> None:
        """Story 15-4's first acceptance criterion, and the epic's standing guarantee.

        The status token is read off ``SetActiveDeckResult``'s closed set rather than typed here, so
        a renamed outcome cannot leave the docs promising a word the tools no longer return.
        """
        section = _extract_section(_read_guide())
        # BOTH tools, because README's capability table claims both report it. Reading only the
        # control tool's set left the claim about the push tool unguarded (review, 2026-08-19).
        tokens = set()
        for result in (SetActiveDeckResult, ShowSuggestionsResult):
            statuses = get_args(result.model_fields["status"].annotation)
            not_running = [status for status in statuses if "not_running" in status]
            assert len(not_running) == 1, (
                f"{result.__name__}'s statuses {sorted(statuses)} no longer contain exactly one "
                "'not running' outcome — README's capability table says BOTH companion tools "
                "report one when the app is closed"
            )
            tokens.add(not_running[0])
        assert len(tokens) == 1, (
            f"the two companion tools report different not-running tokens {sorted(tokens)}; "
            "README's table names a single one for both"
        )
        not_running = sorted(tokens)

        claims = _claim(section)
        assert "is optional, and nothing depends on it" in claims, (
            "the section never says plainly that the companion is optional and that nothing "
            "depends on it. Every agent workflow completes with the app closed, and that "
            "guarantee is the reason deprecating view_deck is safe."
        )
        assert "with the app closed" in claims, (
            "the section does not state plainly that every agent workflow completes with the app "
            "closed — 'optional' alone leaves a reader wondering what they lose"
        )
        assert not_running[0] in claims, (
            f"the section does not name the {not_running[0]!r} status the companion tools report "
            "when the app is not up, so a reader who sees it has nowhere to look it up"
        )

        # The claim is *made* in the capability table, outside this section — that is the row a
        # reader meets first, and it says BOTH tools report the token. Left unguarded it could name
        # a status neither model returns (firing proof 14, 2026-08-19, which passed until this).
        capabilities = _extract_section(_read_readme(), CAPABILITY_HEADING, source="README.md")
        assert not_running[0] in capabilities, (
            f"README's {CAPABILITY_HEADING!r} table does not name {not_running[0]!r}, the status "
            "both companion tools return with the app closed. The table is where the promise that "
            "the companion is optional is first made, and a promise with no token to check is not "
            "one a reader can act on."
        )

    def test_the_section_says_node_is_never_required_and_pyproject_agrees(self) -> None:
        """SC-4: a fresh install launches with one ``uv`` command and no build step.

        The claim is checked against ``pyproject.toml`` before it is checked against the prose: if
        ``fastapi`` or ``uvicorn`` ever moved into an extra or a dependency group, the guide's
        "no extra, no dependency group" sentence would be false and this fails on the *code* side.
        """
        pyproject = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
        base = {re.split(r"[<>=!\[ ]", spec)[0] for spec in pyproject["project"]["dependencies"]}
        assert {"fastapi", "uvicorn"} <= base, (
            f"fastapi and uvicorn are no longer both base dependencies (found {sorted(base)}). "
            "the companion guide tells the reader there is no extra and no dependency group "
            "to install — that sentence is now false."
        )

        section = _claim(_extract_section(_read_guide()))
        assert "Node is never required" in section, (
            "the section does not state that Node is never required at install or runtime. The "
            "absence of a Node prerequisite is the point of the committed bundle, and a reader who "
            "is not told assumes an npm step."
        )
        assert "Node is required to change the UI" in section, (
            "the section states the Node claim without its honest caveat — Node *is* required to "
            "change the UI, and a claim without its exception is the kind of promise that gets "
            "found out"
        )

        # The same claim is restated in README's ## Requirements — a different document now, where
        # a reader meets it first. Left unguarded, that copy could say the opposite and every test
        # here would stay green — measured, not argued (review, 2026-08-19).
        requirements = _claim(
            _extract_section(_read_readme(), REQUIREMENTS_HEADING, source="README.md")
        )
        assert "Node is not required at install or at runtime" in requirements, (
            f"README's {REQUIREMENTS_HEADING!r} block does not repeat the claim the companion "
            "section makes, and the two are free to contradict each other. It is the first place a "
            "reader looks to find out what they must install."
        )

    def test_every_link_anchor_resolves_and_the_guide_is_linked_to(self) -> None:
        """Story 15-4's anchor pin, widened to the two documents the prose now spans.

        Measured (review, 2026-08-19): rewriting ``](#the-companion-app)`` to a slug naming no
        heading, in the capability table and the requirements list, left the suite green. A dead
        anchor scrolls a reader nowhere and looks like a working link — and the restructure added a
        second way to die: README reaches the guide through ``docs/companion.md#slug`` anchors, and
        the guide points back through ``../README.md#slug`` ones, none of which either file can
        check against itself. So every in-page anchor is resolved against its own document, every
        cross-document anchor against the document it points at, and the arrival paths are pinned:
        README's shortened companion section is linked to from outside itself, and it links into
        the guide — without those, the guide is only reachable by knowing it exists.
        """
        readme = _read_readme()
        guide = _read_guide()
        slugs = {
            "README.md": {_slug(line) for line in _headings(readme)},
            "docs/companion.md": {_slug(line) for line in _headings(guide)},
        }
        for name, found in slugs.items():
            assert len(found) > 5, f"no headings were found in {name} — the slug scan is vacuous"

        for name, text in (("README.md", readme), ("docs/companion.md", guide)):
            targets = re.findall(r"\]\(#(?P<slug>[^)]*)\)", text)
            assert targets, f"{name} contains no in-page links at all — this check is vacuous"
            dead = sorted({target for target in targets if target not in slugs[name]})
            assert not dead, (
                f"{name} links to {dead}, which match no heading in the same file. A dead in-page "
                f"anchor looks exactly like a working one. Known headings resolve to: "
                f"{sorted(slugs[name])}."
            )

        for source, text, pattern, target_doc in (
            ("README.md", readme, r"\]\(docs/companion\.md#(?P<slug>[^)]*)\)", "docs/companion.md"),
            ("docs/companion.md", guide, r"\]\(\.\./README\.md#(?P<slug>[^)]*)\)", "README.md"),
        ):
            crossing = re.findall(pattern, text)
            assert crossing, (
                f"{source} carries no anchored links into {target_doc} at all — the two documents "
                "were split on the promise that each would route the reader to the other, and this "
                "check is vacuous without at least one such link"
            )
            dead = sorted({slug for slug in crossing if slug not in slugs[target_doc]})
            assert not dead, (
                f"{source} links to {target_doc} anchors {dead}, which match no heading there. A "
                "dead cross-document anchor opens the right page and then scrolls the reader "
                f"nowhere. Known headings resolve to: {sorted(slugs[target_doc])}."
            )

        own = _slug(README_COMPANION_HEADING)
        readme_section = _extract_section(readme, README_COMPANION_HEADING, source="README.md")
        outside = readme.replace(readme_section, "")
        assert f"](#{own})" in outside, (
            f"nothing outside README's companion section links to #{own}. The capability table's "
            "row and the requirements list are how a reader arrives there; without them the "
            "section — and the guide it links to — is only reachable by scrolling."
        )
        assert "docs/companion.md" in readme_section, (
            "README's companion section never links into docs/companion.md, so the full guide is "
            "unreachable from the place that summarises it — the shortened section is only honest "
            "while it says where the rest went."
        )

    def test_ordinary_prose_edits_elsewhere_in_the_guide_do_not_move_this_guard(self) -> None:
        """The silent half: this guard is about one section and must ignore what sits outside it.

        A guard that fires on any edit around the guide gets disabled by the third person it
        inconveniences. Edits before *and* after the section are both exercised, because the
        extraction is bounded at both ends. The section is the guide's ``#`` title, so the one
        trailing heading level that must terminate it is another ``#`` — a trailing ``##`` section
        is *supposed* to be swallowed now (that is the containment test's planted case), because a
        new ``##`` section added to the guide is new companion prose this module owns.
        """
        original = _read_guide()
        section = _extract_section(original)

        edited_before = original.replace(
            SECTION_HEADING, "An unrelated prose edit above the companion.\n\n" + SECTION_HEADING, 1
        )
        assert edited_before != original, "the fixture text for this test no longer exists"
        assert _extract_section(edited_before) == section, (
            "an edit above the section changed what the guard reads — the extraction is not "
            "bounded at its start"
        )

        trailing = "\n# A trailing top-level heading\n\nMore unrelated prose.\n"
        assert _extract_section(original + trailing) == section, (
            f"the trailing block {trailing.splitlines()[1]!r} changed what the guard reads — "
            "the extraction is not bounded at its end"
        )

    def test_the_sections_own_subheadings_stay_inside_it(self) -> None:
        """The counterpart bound, and the one story 15-2's guard does not need.

        This section is the guide's title and owns every ``##`` section in the file. A terminator
        that stopped at any ATX level would cut the extraction off after the opening paragraphs,
        and every "the section says X" assertion above would then fail with a message about prose
        that is plainly there.
        """
        original = _read_guide()
        section = _extract_section(original)

        subheadings = [
            line
            for line in section.splitlines()
            if _ATX_HEADING.match(line) and line != SECTION_HEADING
        ]
        assert len(subheadings) >= 4, (
            f"the extraction found only {len(subheadings)} subheading(s) inside "
            f"{SECTION_HEADING!r}. Either the guide was flattened (in which case this bound no "
            "longer needs proving) or the terminator regressed to stopping at any ATX level."
        )

        # Both depths the terminator must let through: a deeper sub-subsection planted at the top,
        # and a sibling-of-the-subsections `##` appended at the end — the level that used to
        # terminate this scan when the section lived in README under a `##` heading.
        planted = original.replace(
            SECTION_HEADING, SECTION_HEADING + "\n\n#### A planted sub-subsection\n\nProse.", 1
        )
        assert "#### A planted sub-subsection" in _extract_section(planted), (
            "a `####` sub-subsection truncated the section — a heading deeper than this section's "
            "own level is part of it, not its terminator"
        )
        appended = original + "\n## An appended companion section\n\nProse.\n"
        assert "## An appended companion section" in _extract_section(appended), (
            "a `##` section appended to the guide fell outside the extraction — every `##` "
            "section in docs/companion.md is companion prose this module owns, and one the scan "
            "cannot see is one no assertion here can ever guard"
        )

    def test_a_heading_inside_a_fenced_block_does_not_truncate_the_section(self) -> None:
        """A ``# `` line inside a fence is sample text, and the scan must read it as such.

        The guide quotes shell commands whose comments start with ``#`` at column zero — the
        plugin-install section really does — so without fence-awareness a documented comment could
        end the section early and hide the rest of it from every assertion above.
        """
        original = _read_guide()
        section = _extract_section(original)
        planted = original.replace(
            SECTION_HEADING,
            SECTION_HEADING + "\n\n```bash\n# this is a shell comment, not a heading\n```",
            1,
        )

        extracted = _extract_section(planted)

        assert "# this is a shell comment" in extracted, (
            "a `#` line inside a fenced block truncated the section — the extraction is not "
            "fence-aware, so a documented shell comment can hide the rest of the section from "
            "every assertion in this module"
        )
        assert extracted.endswith(section.split("\n", 1)[1]), (
            "the fenced sample changed where the section ends, not only what it contains"
        )


class TestTheAttributionNamesWhatTheAppActuallyUses:
    """Story 15-4's attribution widening, pinned from the documentation's side.

    ``ui/tests/attribution.test.ts`` already proves every footer ``href`` appears in ``NOTICE``.
    What no test could see — measured by reverting both files, which left the Python suite and
    the frontend suite green (review, 2026-08-19) — is the attribution's **subject**: the footer
    has always said *"Card data and imagery courtesy of Scryfall"*, the companion does cache
    imagery, and until this story the docs claimed only card data. ``NOTICE`` ships in the
    distribution via ``license-files``, so that gap was a licensing one, not a wording one.

    The subjects are read out of the footer's own copy module rather than typed here, so the
    documentation is pinned to what the app claims rather than to what this file remembers.
    """

    def test_the_docs_claim_every_subject_the_footer_claims(self) -> None:
        """README and NOTICE name each thing the app's own attribution sentence names."""
        footer = FOOTER_COPY_PATH.read_text(encoding="utf-8")
        lead = re.search(r"\{\s*text:\s*'(?P<text>[^']*courtesy of\s*)'", footer)
        assert lead is not None, (
            f"{FOOTER_COPY_PATH.name} no longer opens its attribution with a '… courtesy of ' run, "
            "so this module cannot read what the app claims. Update the pattern deliberately — do "
            "not let the check pass on nothing."
        )
        subjects = [
            part.strip().lower()
            for part in lead.group("text").replace("courtesy of", "").split(" and ")
            if part.strip()
        ]
        assert len(subjects) >= 2, (
            f"the footer's attribution names only {subjects}; this guard exists because it names "
            "more than one thing (card data AND imagery) and the documentation named fewer"
        )

        href = re.search(r"href:\s*'(?P<href>https://[^']*scryfall[^']*)'", footer)
        assert href is not None, (
            f"{FOOTER_COPY_PATH.name} no longer links Scryfall, so there is no credit to scope "
            "these assertions to"
        )

        for path in (README_PATH, NOTICE_PATH):
            credits = _paragraphs_crediting(path.read_text(encoding="utf-8"), href.group("href"))
            assert credits, (
                f"{path.name} never credits {href.group('href')} at all — the attribution is "
                "missing entirely, not merely narrow"
            )
            # EVERY crediting paragraph, not merely one of them: a passage that credits Scryfall for
            # less than the app takes from Scryfall is the gap this class exists for, wherever it
            # sits. Scoped to the paragraph rather than to the file, for the reason
            # _paragraphs_crediting records.
            for credit in credits:
                for subject in subjects:
                    assert subject in credit.lower(), (
                        f"a paragraph in {path.name} credits Scryfall without naming {subject!r}, "
                        f"which the app's own footer does credit ({FOOTER_COPY_PATH.name}):\n\n"
                        f"{credit}\n\nThe app and its documentation must claim the same thing — "
                        "NOTICE ships in the distribution under license-files, so a narrower claim "
                        "there is a licensing gap rather than a wording preference."
                    )

    def test_both_obligation_urls_appear_in_the_readme_as_well_as_the_notice(self) -> None:
        """The two links a reader must be able to follow, in the file a reader actually opens.

        Bounded rather than a bare substring, for the reason ``attribution.test.ts`` gives: a plain
        containment check passes while the documented URL is a prefix of a longer, different one.
        """
        hrefs = re.findall(
            r"href:\s*'(?P<href>https://[^']+)'", FOOTER_COPY_PATH.read_text("utf-8")
        )
        assert len(hrefs) == 2, (
            f"the footer declares {len(hrefs)} attribution links {hrefs}; this guard expects the "
            "two licensing obligations (Scryfall's terms and the Fan Content Policy)"
        )

        for path in (README_PATH, NOTICE_PATH):
            text = path.read_text(encoding="utf-8")
            for href in hrefs:
                pattern = re.compile(f"{re.escape(href)}(?![\\w/-])")
                assert pattern.search(text), (
                    f"{path.name} does not carry {href!r} as a complete URL — it is absent, or "
                    "present only as the prefix of a longer one. Both licensing obligations must "
                    "resolve to the same page from the app and from the documentation."
                )

    def test_the_app_really_does_cache_the_imagery_the_docs_now_claim(self) -> None:
        """The non-vacuity leg: the widening is only correct because the companion caches images.

        Keyed on the shipped cache directory rather than on prose, so if image caching were ever
        removed this test says so — and the attribution could be narrowed back deliberately instead
        of by drift.
        """
        assert images.CACHE_DIRECTORY_NAME, "the companion no longer names an image cache directory"
        readme = README_PATH.read_text(encoding="utf-8")
        assert f"{images.CACHE_DIRECTORY_NAME}/" in readme, (
            f"README no longer documents {images.CACHE_DIRECTORY_NAME}/, the directory whose "
            "existence is why the attribution names imagery at all"
        )
