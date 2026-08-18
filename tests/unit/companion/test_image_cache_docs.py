"""Drift guard over README's ``### Image cache (companion app)`` section (story 15-2).

The section documents four things that are true only because a constant currently says so — the
directory's name, the width of its shard, the shape of an entry's filename, and which environment
variable moves the whole thing — plus one *command* a user is invited to paste into a shell that
ends in ``rm -rf``. Prose has no compiler, so this module is the compiler: every load-bearing claim
is keyed on the shipped symbol (``images.CACHE_DIRECTORY_NAME``, ``images._cache_path``,
``images.cache_root``, ``singleton.LOCK_FILENAME``, ``discovery.COMPANION_FILENAME``) and never on a
literal copied out of the README, so a rename that updates the prose moves the pin with it and a
rename that does not turns this red. The precedent is
``test_images.py::test_the_wire_prose_in_contracts_matches_the_shipped_schedule``, which does the
same for the schedule published to the wire.

The one-liner the README tells a user to run is not merely matched, it is **executed**: extracted
from the fenced block, run in-process under this package's autouse ``isolated_data_dir`` fixture
(which pins ``PLANESWALKER_DATA_DIR`` at the test's ``tmp_path``), and compared against
:func:`src.companion.app.images.cache_root`. That single assertion carries both the override claim
and the command's correctness, because a documented deletion command that resolves the wrong
directory is the one defect in this section that would actually cost a user something.

**Declared residue — what this guard does NOT prove:**

1. **Only the Python expression is executed.** ``du``, ``find``, ``rm -rf``, ``Get-ChildItem`` and
   ``Remove-Item`` are never run, and the PowerShell block cannot be run on the Linux CI runner at
   all. A typo in the surrounding shell syntax — a lost quote, a wrong flag — is a reviewer's
   judgement, not this module's. What *is* pinned, after a reviewer measured the hole
   (2026-08-18), is that each clear block deletes the variable its own verified one-liner assigned:
   a correct payload beside an ``rm -rf`` aimed somewhere else used to pass. The ``uv run`` wrapper
   is also stripped, so this module cannot see that the documented commands require the checkout
   and its environment to be present — the README says so in words instead.
2. **It reads one section, found by heading.** Prose elsewhere in ``README.md`` (or in any other
   document) that contradicts this section is invisible here, and the ``plugin/`` mirror of this
   file is guarded by CI's rebuild-and-diff rather than by an assertion here. The heading itself is
   the non-vacuity anchor: :func:`_extract_section` fails by name rather than returning an empty
   string, so a removed or renamed section can never let the remaining assertions pass over
   nothing; it is fence-aware and terminates on any ATX level, both of which are tested rather than
   asserted in prose.
3. **The footprint figures are pinned by nothing.** ~90 KB per tile, 8.5 MB per deck and ~95 MB per
   library are measurements from the C3 retrospective (2026-08-02) with no constant to key on; they
   age with the corpus and with Scryfall's encoder. This module asserts the numbers are *present
   and labelled measured*, not that they are still true.
4. **Semantics are not checked, only subjects.** That the eviction paragraph names eviction and the
   staleness paragraph names ``image_uris`` does not prove either paragraph says something correct
   about them.
"""

import contextlib
import io
import re
from pathlib import Path

from src import paths
from src.companion import discovery
from src.companion.app import images, singleton

# ---------------------------------------------------------------------------------------------
# Repository layout — resolved from __file__, never from the current working directory, exactly as
# tests/unit/companion/test_import_boundary.py does it.
# ---------------------------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[3]
README_PATH = REPO_ROOT / "README.md"

SECTION_HEADING = "### Image cache (companion app)"
"""The section this module is the compiler for. Renaming it here and in README.md is one edit."""

# A synthetic Scryfall-shaped uuid. Its only job is to be fed to the shipped path builder so the
# documented example can be *derived* — the shard width and the `<size>_<face><ext>` filename shape
# come out of `images._cache_path`, never out of an assertion here.
_SYNTHETIC_CARD_ID = "813d0434-8e0f-4b0a-9c7e-1f2a3b4c5d6e"
_SYNTHETIC_SIZE = "normal"
_SYNTHETIC_FACE = 0
_SYNTHETIC_EXTENSION = ".jpg"

_NUMBER_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}

# `uv run python -c "<payload>"`, in either fenced block. The payload never contains a double quote
# (it quotes the directory name with single quotes precisely so both shells can wrap it in doubles),
# so a non-greedy `[^"]*` is exact rather than approximate.
_ONE_LINER = re.compile(r'python -c "(?P<code>[^"]+)"')

_EXPECTED_PAYLOAD_PREFIX = "from src import paths"
"""The only payload shape this module ``exec``\\ s — see :func:`_documented_one_liners`."""

# Any ATX heading, at any level: `#` through `######` followed by a space. `##`/`###` alone let a
# `#### ` sub-subsection extend this section into prose it does not own (review 2026-08-18).
_ATX_HEADING = re.compile(r"#{1,6} ")

# The shell capture the clear command deletes: `CACHE=$(…)` in bash, `$Cache = …` in PowerShell.
# The name is captured rather than assumed so the binding test compares what the README actually
# wrote on both lines, never a name this file expects it to have used.
_SHELL_ASSIGNMENTS = {
    "bash": re.compile(r"^(?P<name>[A-Za-z_][A-Za-z0-9_]*)=\$\(.*python -c ", re.MULTILINE),
    "powershell": re.compile(
        r"^\$(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*.*python -c ", re.MULTILINE
    ),
}
_DELETION_ARGUMENTS = {
    "bash": re.compile(r"rm -rf\s+(?P<target>\S+)"),
    "powershell": re.compile(r"Remove-Item[^\n]*?\s(?P<target>\$\S+)\s*$", re.MULTILINE),
}


def _read_readme() -> str:
    """Return README.md's text, read from the repository root rather than the working directory."""
    assert (REPO_ROOT / "pyproject.toml").exists(), f"{REPO_ROOT} is not the repository root"
    return README_PATH.read_text(encoding="utf-8")


def _extract_section(readme: str) -> str:
    """Return the image-cache section, from its heading to the next ATX heading of any level.

    **The non-vacuity anchor.** Every assertion in this module reads what this returns, so a
    missing or renamed heading has to fail here, loudly and by name, rather than yield an empty
    string that every substring check would then pass over.

    Two bounding rules the first cut got wrong (review 2026-08-18), both of which decide *which
    prose the whole module then reads*:

    * The terminator matches **any** ATX level (:data:`_ATX_HEADING`), not only ``##``/``###``. A
      ``#### `` sub-subsection appended after this section would otherwise be swallowed into it,
      and every "is this string present" assertion below would start reading someone else's prose.
    * The scan is **fence-aware**. A ``### `` line inside a fenced block is sample text, not a
      heading; without this a documented shell comment could truncate the section mid-command and
      the module would report a missing block that is plainly there.

    Args:
        readme: The full text of ``README.md``.

    Returns:
        The section's lines, heading included, joined with newlines.
    """
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
        if not in_fence and _ATX_HEADING.match(lines[i]):
            end = i
            break
    return "\n".join(lines[start:end])


def _documented_one_liners(section: str) -> list[str]:
    """Return every ``python -c`` payload the section tells a user to run, from fenced blocks only.

    **Prose is not executed** (review 2026-08-18). :func:`_run` ``exec``\\ s what this returns, so
    the extraction surface has to be the fenced blocks a reader would actually paste — never a
    sentence that happens to contain ``python -c "…"``. Each payload is additionally required to
    have the shape this section documents (:data:`_EXPECTED_PAYLOAD_PREFIX`), so a future command
    that reached for ``shutil.rmtree`` could not be run by the test suite on a developer's machine
    merely by being written down.

    Args:
        section: The extracted section text.

    Returns:
        Every ``python -c`` payload found inside a fenced block, in document order.
    """
    payloads = [
        match.group("code")
        for _language, body in _fenced_blocks(section)
        for match in _ONE_LINER.finditer(body)
    ]
    for code in payloads:
        assert code.startswith(_EXPECTED_PAYLOAD_PREFIX), (
            f"the documented one-liner {code!r} is not the path-printing command this guard "
            f"executes (it must start with {_EXPECTED_PAYLOAD_PREFIX!r}). This module runs what "
            "the README tells a user to run, so a payload that does anything other than print a "
            "path must not be executed here — verify it another way."
        )
    return payloads


def _fenced_blocks(section: str) -> list[tuple[str, str]]:
    """Return every fenced block in *section* as ``(language, body)``.

    An unlabelled fence yields an empty language, so a block that lost its ``bash`` tag reads as
    "no bash block" rather than as an untagged pass.

    Args:
        section: The extracted section text.

    Returns:
        One ``(language, body)`` pair per fenced block, in document order.
    """
    blocks: list[tuple[str, str]] = []
    language: str | None = None
    body: list[str] = []
    for line in section.splitlines():
        if line.startswith("```"):
            if language is None:
                language = line[3:].strip()
                body = []
            else:
                blocks.append((language, "\n".join(body)))
                language = None
        elif language is not None:
            body.append(line)
    assert language is None, (
        "a fenced block in README's image-cache section is never closed — everything after it "
        "reads as commentary rather than as a command, so a missing-block failure below would "
        "name the wrong cause. Close the fence in README.md."
    )
    return blocks


def _run(code: str) -> str:
    """Execute one README payload in-process and return what it printed, stripped."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        exec(compile(code, "<README image-cache one-liner>", "exec"), {})  # noqa: S102
    return buffer.getvalue().strip()


class TestTheImageCacheSectionMatchesTheShippedCache:
    """README's stewardship section against the code it describes (story 15-2, AC 1-5)."""

    def test_the_documented_section_exists(self) -> None:
        """The anchor: nothing below this test means anything if the section is gone."""
        section = _extract_section(_read_readme())

        assert section.startswith(SECTION_HEADING)
        assert len(section.splitlines()) > 10, (
            f"{SECTION_HEADING!r} is present but nearly empty — the guard would pass vacuously on "
            "a stub. Restore the stewardship prose in README.md."
        )

    def test_the_documented_directory_is_the_shipped_directory_name(self) -> None:
        """AC 1: the name in the prose is ``images.CACHE_DIRECTORY_NAME``, not a remembered word."""
        section = _extract_section(_read_readme())

        assert f"{images.CACHE_DIRECTORY_NAME}/" in section, (
            f"README's {SECTION_HEADING!r} section does not name the shipped cache directory "
            f"{images.CACHE_DIRECTORY_NAME!r}. Either the constant was renamed and the prose was "
            "not (edit README.md), or the prose was rewritten around a different name (edit "
            "src/companion/app/images.py, or the prose)."
        )

    def test_the_documented_location_follows_the_data_dir_override(self) -> None:
        """AC 1: the section says the location moves with ``PLANESWALKER_DATA_DIR``."""
        section = _extract_section(_read_readme())

        assert "PLANESWALKER_DATA_DIR" in section, (
            "the section does not tell the reader the cache follows PLANESWALKER_DATA_DIR, which "
            "is the whole reason images.cache_root() resolves through src.paths at call time"
        )

    def test_the_documented_layout_is_the_path_the_shipped_code_builds(self) -> None:
        """AC 1: the example path is derived from ``images._cache_path``, never asserted flat.

        Shard width, directory nesting and the ``<size>_<face><ext>`` filename all come out of the
        function, so any change to the layout fails here naming the path the code now builds.
        """
        section = _extract_section(_read_readme())
        built = images._cache_path(
            Path(images.CACHE_DIRECTORY_NAME),
            _SYNTHETIC_CARD_ID,
            _SYNTHETIC_SIZE,
            _SYNTHETIC_FACE,
            _SYNTHETIC_EXTENSION,
        )

        assert built.as_posix() in section, (
            f"README's documented layout example does not match the path images._cache_path "
            f"actually builds, which is {built.as_posix()!r}. The shipped layout changed and the "
            "prose did not — edit the example in README.md."
        )

        assert len(built.parts) >= 3, (
            "images._cache_path no longer builds a sharded path — it returned "
            f"{built.as_posix()!r}, "
            "which has no shard segment to describe. The layout changed shape; rewrite both the "
            "prose in README.md and this assertion."
        )
        shard_width = len(built.parts[1])
        shard_word = _NUMBER_WORDS.get(shard_width, str(shard_width))
        assert f"{shard_word}-character shard" in section, (
            f"images._cache_path shards on {shard_width} character(s) but README does not describe "
            f"a {shard_word}-character shard — edit the prose in README.md."
        )

    def test_the_documented_command_resolves_the_shipped_cache_root(self) -> None:
        """AC 2: the README's own one-liner, executed, prints exactly ``images.cache_root()``.

        Runs under the autouse ``isolated_data_dir`` fixture, so ``PLANESWALKER_DATA_DIR`` is
        pinned at this test's ``tmp_path`` — which makes this simultaneously the override claim and
        the proof that the documented ``rm -rf`` target is the directory the app writes to.
        """
        section = _extract_section(_read_readme())
        one_liners = _documented_one_liners(section)

        assert one_liners, (
            f'no `python -c "..."` command was found in README\'s {SECTION_HEADING!r} section. '
            "The inspect/clear blocks are the point of the section; extraction returning nothing "
            "is a failure, never a pass. Restore the fenced command blocks in README.md."
        )

        expected = str(images.cache_root())
        for code in one_liners:
            printed = _run(code)
            assert printed == expected, (
                f"the documented command {code!r} resolves a different directory than the app "
                f"writes to: it printed {printed!r}, images.cache_root() is {expected!r}. A "
                "documented deletion command that points elsewhere is the one defect in this "
                "section that costs a user data — fix README.md."
            )

    def test_each_clear_command_deletes_the_path_its_own_block_resolved(self) -> None:
        """AC 2: the ``rm -rf`` argument is the variable the *verified* one-liner assigned.

        The gap this closes was measured, not argued (review 2026-08-18): with
        ``rm -rf "$CACHE"`` rewritten to ``rm -rf ~/.cache/planeswalker-images`` and the correct
        ``CACHE=$(uv run python -c …)`` line above it untouched, all eleven guards stayed green —
        the payload test still passed (the payload was still right) and the block test still passed
        (``rm -rf`` was still present). Nothing tied the verified path to the deleted one, which is
        precisely the defect this section's own docstring calls the only one that costs a user data.
        """
        section = _extract_section(_read_readme())
        blocks = _fenced_blocks(section)

        for language in ("bash", "powershell"):
            clearing = [
                body
                for spoken, body in blocks
                if spoken == language and _DELETION_ARGUMENTS[language].search(body)
            ]
            assert clearing, f"no ```{language} block deletes anything — see the block test"

            for body in clearing:
                assignment = _SHELL_ASSIGNMENTS[language].search(body)
                assert assignment, (
                    f"the ```{language} clear block deletes a path it never resolved: it carries "
                    "no `python -c` assignment of its own, so nothing in this suite verifies what "
                    "it is about to delete. Resolve the path in the same block you delete it from."
                )
                target = _DELETION_ARGUMENTS[language].search(body)
                assert target is not None  # the filter above already matched
                deleted = target.group("target").strip('"').lstrip("$").rstrip("/")
                assert deleted == assignment.group("name"), (
                    f"the ```{language} clear block resolves the cache into "
                    f"{assignment.group('name')!r} and then deletes {target.group('target')!r} — a "
                    "verified path and an unverified deletion target. Delete the variable the "
                    "block just resolved, in README.md."
                )

    def test_both_platforms_get_a_copy_pasteable_block_for_both_actions(self) -> None:
        """AC 2: each platform gets an *inspect* block and a *clear* block, not just one block.

        Presence of the language alone was too weak, and it was measured rather than argued: with
        the PowerShell **inspect** block deleted, a `"```powershell" in section` check still passed
        because the PowerShell **clear** block kept the token alive (firing proof 4, 2026-08-18).
        The section promises a Windows user and a macOS/Linux user each two actions, so each of the
        four is asserted on the verb that performs it.
        """
        section = _extract_section(_read_readme())
        blocks = _fenced_blocks(section)

        for language, inspect_verbs, clear_verb in (
            ("bash", ("du ", "find "), "rm -rf"),
            ("powershell", ("Get-ChildItem", "Measure-Object"), "Remove-Item"),
        ):
            spoken = [body for spoken_language, body in blocks if spoken_language == language]
            assert spoken, (
                f"no ```{language} block in README's {SECTION_HEADING!r} section — "
                f"{'macOS/Linux' if language == 'bash' else 'Windows'} users have nothing to paste"
            )
            assert any(any(verb in body for verb in inspect_verbs) for body in spoken), (
                f"no ```{language} block inspects the cache (looked for {inspect_verbs}); a user "
                "on that platform is told the cache grows without bound and given no way to see "
                "how big it got. Restore the inspect block in README.md."
            )
            assert any(clear_verb in body for body in spoken), (
                f"no ```{language} block clears the cache (looked for {clear_verb!r}); AC 2 asks "
                "for a copy-pasteable removal command on both platforms. Restore the clear block "
                "in README.md."
            )

    def test_the_eviction_paragraph_states_the_measured_footprint(self) -> None:
        """AC 3: nothing is evicted, and the footprint quoted is the measured one.

        The figures have no constant to key on (declared residue 3) — this asserts they are
        present and that the measurement is distinguished from the earlier arithmetic estimate,
        not that they are still accurate against today's corpus.
        """
        section = _extract_section(_read_readme())
        lowered = section.lower()

        assert "evict" in lowered, "the section never mentions eviction at all"
        assert "no ttl" in lowered, "the section does not state plainly that there is no TTL"
        for figure in ("90 KB", "8.5 MB", "95 MB"):
            assert figure in section, (
                f"the measured footprint {figure} (C3 retrospective, 2026-08-02) is missing — the "
                "eviction paragraph must quote a measurement, not an estimate"
            )
        assert "12 MB" in section and "estimate" in lowered, (
            "the earlier ~12 MB arithmetic estimate must appear beside the measurement, labelled "
            "as the estimate it was, so the two figures do not disagree in silence"
        )
        assert "measured" in lowered, "neither figure is labelled as the measured one"

    def test_the_staleness_paragraph_names_its_cause_and_its_remedy(self) -> None:
        """AC 5: accepted staleness, with the key that causes it and the deletion that fixes it."""
        section = _extract_section(_read_readme())

        assert "image_uris" in section, (
            "the staleness paragraph does not name image_uris, the field whose change is the "
            "trigger for the accepted staleness"
        )
        assert "id + size + face" in section, (
            "the staleness paragraph does not state the cache key (id + size + face), which is "
            "the cause rather than an aside"
        )
        assert "delete" in section.lower(), "the staleness paragraph names no remedy"

    def test_the_leftovers_list_names_every_file_an_uninstall_leaves(self) -> None:
        """AC 4: the three real leftovers, each keyed on the constant that spells it."""
        section = _extract_section(_read_readme())

        for name, symbol in (
            (images.CACHE_DIRECTORY_NAME, "images.CACHE_DIRECTORY_NAME"),
            (singleton.LOCK_FILENAME, "singleton.LOCK_FILENAME"),
            (discovery.COMPANION_FILENAME, "discovery.COMPANION_FILENAME"),
        ):
            assert name in section, (
                f"the uninstall paragraph does not name {name!r} ({symbol}) — a leftovers list "
                "that omits a file the user will find in their data directory is not a disclosure"
            )

        window = section[section.index(discovery.COMPANION_FILENAME) :][:400].lower()
        assert "clean" in window, (
            f"{discovery.COMPANION_FILENAME} is listed unconditionally; it is left behind only "
            "when the process did not exit cleanly, and the condition is the informative half"
        )

        for other in (paths.database_path().name, paths.fastembed_cache_dir().name):
            assert other in section, (
                f"the section does not mention {other}, the data directory's other resident — a "
                "reader deciding whether to delete the whole directory needs to know what else "
                "goes with it"
            )

    def test_the_two_cache_disable_behaviours_are_disclosed(self) -> None:
        """The two lifecycle exposures that stay unbuilt are at least stated, with their remedy."""
        section = _extract_section(_read_readme())
        lowered = section.lower()

        limit = images.DISK_CACHE_WRITE_FAILURE_LIMIT
        # `.get`, never `[]`: raising the limit past six must fail with the message below, not with
        # a bare KeyError from the lookup that was supposed to produce that message.
        assert f"{_NUMBER_WORDS.get(limit, str(limit))} *consecutive*" in lowered, (
            f"DISK_CACHE_WRITE_FAILURE_LIMIT is {images.DISK_CACHE_WRITE_FAILURE_LIMIT} but the "
            "section does not say so — edit README.md, or the constant's prose moved without it"
        )
        assert "restart" in lowered, (
            "neither disable path names its remedy; restarting the app is the whole of it, and a "
            "disclosure without a remedy is a complaint"
        )
        assert "still served" in lowered, (
            "the section does not say that every image is still served with the cache disabled, "
            "which is what makes both behaviours acceptable rather than defects"
        )

    def test_ordinary_prose_edits_elsewhere_in_the_readme_do_not_move_this_guard(self) -> None:
        """The silent half: this guard is about one section and must ignore the rest of the file.

        A guard that fires on any README edit gets disabled by the third person it inconveniences.
        Edits before *and* after the section are both exercised, because the extraction is bounded
        at both ends.
        """
        original = _read_readme()
        section = _extract_section(original)

        # Anchored on the one heading this module owns, never on a neighbouring section's title —
        # a guard that goes red when someone renames "Semantic search index" is guarding the wrong
        # thing (review 2026-08-18).
        edited_before = original.replace(
            SECTION_HEADING, "An unrelated prose edit above the cache.\n\n" + SECTION_HEADING, 1
        )
        assert edited_before != original, "the fixture text for this test no longer exists"
        assert _extract_section(edited_before) == section, (
            "an edit above the section changed what the guard reads — the extraction is not "
            "bounded at its start"
        )

        for trailing in (
            "\n## A brand new trailing section\n\nMore unrelated prose.\n",
            # Both ATX levels the first cut did not terminate on: a deeper sub-subsection and a
            # top-level heading. Either one, unbounded, would pull foreign prose into the section
            # and let a "the section says X" assertion pass on someone else's sentence.
            "\n#### A trailing sub-subsection\n\nMore unrelated prose.\n",
            "\n# A trailing top-level heading\n\nMore unrelated prose.\n",
        ):
            assert _extract_section(original + trailing) == section, (
                f"the trailing block {trailing.splitlines()[1]!r} changed what the guard reads — "
                "the extraction is not bounded at its end"
            )

    def test_a_heading_inside_a_fenced_block_does_not_truncate_the_section(self) -> None:
        """A ``### `` line inside a fence is sample text, and the scan must read it as such.

        Without fence tracking, a documented shell comment (``### step 2``) or any markdown sample
        would end the section early, and every assertion below it would then fail with a
        "the section does not say X" message about prose that is plainly there.
        """
        original = _read_readme()
        section = _extract_section(original)
        planted = original.replace(
            SECTION_HEADING,
            SECTION_HEADING + "\n\n```bash\n### this is a shell comment, not a heading\n```",
            1,
        )

        extracted = _extract_section(planted)

        assert "### this is a shell comment" in extracted, (
            "a `###` line inside a fenced block truncated the section — the extraction is not "
            "fence-aware, so a documented shell comment can hide the rest of the section from "
            "every assertion in this module"
        )
        assert extracted.endswith(section.split("\n", 1)[1]), (
            "the fenced sample changed where the section ends, not only what it contains"
        )
