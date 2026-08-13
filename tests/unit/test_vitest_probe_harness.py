"""Unit tests for the vitest probe harness (``scripts/vitest_probe_harness.py``).

Every case here is a **fixture transcript**: the harness splits parsing from running precisely so
these can exist without npm, and nothing in this file spawns a process. The transcripts are the
shapes measured on master ``b90fa09`` (2026-08-13) plus the recorded lie shapes from the C4/C6
retrospectives.

Two rules shape the file, both standing agreements rather than taste:

* **Do-nothing negative controls.** The C4 retro named these the part least likely to be re-invented
  correctly, so the green transcript must score NOT-caught against an ``--expect-red``.
* **Every refusal test gets a positive twin** (C6 R8). A harness that refuses everything satisfies
  every refusal assert, so each defective transcript is paired with a near-identical clean one that
  must NOT refuse — the pair is the assertion, not either half.
"""

from __future__ import annotations

import json
import os
import subprocess

import pytest

import scripts.vitest_probe_harness as vph

# vitest prints its banner root with forward slashes; the harness compares separator-insensitively
# but case-SENSITIVELY, so building the expected root from the module keeps these tests portable
# while still letting the lowercase-drive case be a genuine mismatch.
OWNED_ROOT = str(vph._UI_DIR).replace("\\", "/")

GREEN = f"""
> artificial-planeswalker-ui@0.0.0 test
> vitest run


 RUN  v4.1.10 {OWNED_ROOT}


 Test Files  75 passed (75)
      Tests  2123 passed (2123)
   Start at  16:45:35
   Duration  6.19s (transform 10.79s, setup 12.32s, import 17.42s, tests 19.67s)
"""

# The measured red shape: one planted violation in a `src/**` component, so the FAIL line carries
# the jsdom `dom` project prefix that `ui/vite.config.ts` gives it.
RED = f"""
> artificial-planeswalker-ui@0.0.0 test
> vitest run


 RUN  v4.1.10 {OWNED_ROOT}

 FAIL  |dom| src/components/AgentView.test.tsx > AgentView > renders the transcript
AssertionError: expected 'x' to be 'y'

 Test Files  1 failed | 74 passed (75)
      Tests  1 failed | 2122 passed (2123)
   Start at  16:51:02
   Duration  7.02s
"""

# Lie #5: a plant that mutated a component into TSX that would not parse. Both numbers shrink
# TOGETHER, so the transcript is internally consistent and only the control's baseline exposes it.
SHRUNK = f"""
 RUN  v4.1.10 {OWNED_ROOT}

 Test Files  74 passed (74)
      Tests  2098 passed (2098)
"""

# Sighting #6 (c6-5, twice): a worker fork dies and takes a whole test file with it. The survivors
# still summarise cleanly, which is the entire danger.
CRASHED = f"""
 RUN  v4.1.10 {OWNED_ROOT}

[vitest-pool] Worker exited unexpectedly

 Test Files  74 passed (74)
      Tests  2098 passed (2098)
"""

# A file entered the run and never reported: the categories no longer add up to the run's own total.
DROPPED_FILE = f"""
 RUN  v4.1.10 {OWNED_ROOT}

 Test Files  74 passed (75)
      Tests  2098 passed (2123)
"""


def _case_flipped_root() -> str:
    """``OWNED_ROOT`` with its first ALPHABETIC character's case flipped.

    On Windows that character is the drive letter, so this reproduces recorded lies #1-2 exactly.
    On POSIX it is the first path segment's initial, which a case-sensitive comparison rejects
    just as firmly. Deriving it rather than hardcoding ``C:``→``c:`` matters twice over: the
    root-mismatch defence is the module's headline claim and the ONLY CI job running
    ``tests/unit/`` is ubuntu, so a Windows-skipped test lets that claim be regressed under fully
    green CI — and the hardcoded form was additionally a no-op (hence a refusal asserted against an
    unmodified GREEN transcript) on any checkout not living on ``C:``.
    """
    for index, char in enumerate(OWNED_ROOT):
        if char.isalpha():
            flipped = char.lower() if char.isupper() else char.upper()
            return OWNED_ROOT[:index] + flipped + OWNED_ROOT[index + 1 :]
    raise AssertionError(f"no alphabetic character to flip in {OWNED_ROOT!r}")


# Lies #1-2. Owning the cwd already prevents this; the banner cross-check is the belt to that
# braces. The `assert` is the non-vacuity anchor: if the flip were a no-op the fixture below would
# be a verbatim copy of GREEN and every test using it would assert a refusal against a clean run.
WRONG_ROOT_PATH = _case_flipped_root()
assert WRONG_ROOT_PATH != OWNED_ROOT
WRONG_ROOT = GREEN.replace(OWNED_ROOT, WRONG_ROOT_PATH)

# vitest prints "no tests" rather than a parenthesised tally when it collected nothing at all.
NO_SUMMARY = f"""
 RUN  v4.1.10 {OWNED_ROOT}

 Test Files  no tests
      Tests  no tests
"""

# A fully green tally paired with a non-zero exit: something failed OUTSIDE the tally (an
# unhandled rejection after the run, an afterAll hook, a worker error). Nothing here is red, so
# `--expect-green` would certify it — the c5-1 review-round-2 hole, in vitest dialect.
GREEN_TALLY_NONZERO_EXIT = GREEN

# A file-level FAIL line (no ` > `), which vitest prints when a file dies at transform time before
# any test inside it runs. The file's tests simply vanish from the count.
FILE_LEVEL_FAIL = f"""
 RUN  v4.1.10 {OWNED_ROOT}

 FAIL  |dom| src/components/AgentView.test.tsx
Error: Transform failed with 1 error

 Test Files  1 failed | 74 passed (75)
      Tests  2098 passed (2098)
"""


def _check(
    text, exit_code=0, *, expect_total=None, expect_red=None, expect_green=False, control=False
):
    """Parse *text* and score it, returning ``(refusals, complaints)``."""
    result = vph.parse_vitest_output(text, exit_code)
    return vph.check(
        result,
        expect_total=expect_total,
        expect_red=list(expect_red or []),
        expect_green=expect_green,
        control=control,
    )


# --------------------------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------------------------


def test_parses_the_measured_green_transcript() -> None:
    """The warm green run from master b90fa09 reads as 75 files / 2123 tests, nothing failed."""
    result = vph.parse_vitest_output(GREEN, 0)
    assert result.root == OWNED_ROOT
    assert (result.files_total, result.files_tally) == (75, 75)
    assert (result.tests_total, result.tests_tally) == (2123, 2123)
    assert result.tests_failed == 0
    assert result.failed == ()
    assert result.crashes == ()


def test_parses_the_measured_red_transcript() -> None:
    """A one-failure run yields the project-prefixed test id and the split category tally."""
    result = vph.parse_vitest_output(RED, 1)
    assert result.tests_total == 2123
    assert result.tests_tally == 2123
    assert result.tests_failed == 1
    assert result.failed == (
        "|dom| src/components/AgentView.test.tsx > AgentView > renders the transcript",
    )


def test_proof_line_states_counts_and_exit_status() -> None:
    """The pasteable line carries both totals, the failure count and npm's exit code."""
    assert vph.parse_vitest_output(GREEN, 0).proof_line() == (
        "vitest: 75 files / 2123 tests, 0 failed, exit 0"
    )
    assert vph.parse_vitest_output(RED, 1).proof_line() == (
        "vitest: 75 files / 2123 tests, 1 failed, exit 1"
    )


def test_ansi_colour_does_not_change_the_parse() -> None:
    """A transcript captured from a TTY parses identically to one captured through a pipe."""
    coloured = GREEN.replace(" Test Files ", " \x1b[1mTest Files\x1b[22m ")
    assert vph.parse_vitest_output(coloured, 0) == vph.parse_vitest_output(GREEN, 0)


@pytest.mark.parametrize("newline", ["\r\n", "\r"])
def test_carriage_returns_do_not_change_the_parse(newline: str) -> None:
    """Every pattern here anchors on `^`/`$`, and a stray `\\r` before `$` turns each of them into a
    silent non-match — i.e. an unparseable-summary REFUSAL on a perfectly good run. `text=True`
    translates newlines, but a transcript pasted from a Windows terminal or read with `newline=''`
    does not."""
    crlf = GREEN.replace("\n", newline)
    assert vph.parse_vitest_output(crlf, 0) == vph.parse_vitest_output(GREEN, 0)


def test_a_failures_own_output_cannot_impersonate_the_summary() -> None:
    """The LAST summary line wins: a failure printing a summary-shaped line is not read as one."""
    noisy = RED.replace(
        "AssertionError: expected 'x' to be 'y'",
        "AssertionError: expected '      Tests  1 passed (1)' to be 'y'",
    )
    assert vph.parse_vitest_output(noisy, 1).tests_total == 2123


# --------------------------------------------------------------------------------------------
# I/O matrix row 1 — the do-nothing control, and its negative control
# --------------------------------------------------------------------------------------------


def test_control_on_a_clean_green_tree_neither_refuses_nor_complains() -> None:
    """Row 1: a warm green run is a valid control."""
    assert _check(GREEN, 0, control=True) == ([], [])


def test_control_refuses_a_red_tree_rather_than_reporting_a_baseline() -> None:
    """Row 1's error handling: a red control REFUSES — the number it exists to produce is void."""
    refusals, complaints = _check(RED, 1, control=True)
    assert len(refusals) == 1
    assert "control run is NOT green" in refusals[0]
    assert complaints == []


def test_green_transcript_scores_not_caught_against_an_expect_red() -> None:
    """The do-nothing negative control: an unplanted tree must not certify a probe as fired."""
    refusals, complaints = _check(GREEN, 0, expect_total=2123, expect_red=["AgentView"])
    assert refusals == []
    assert len(complaints) == 1
    assert "expected 'AgentView' to be RED" in complaints[0]


def test_green_transcript_satisfies_expect_green() -> None:
    """Positive twin: the same transcript, scored the way it should pass, does pass."""
    assert _check(GREEN, 0, expect_total=2123, expect_green=True) == ([], [])


# --------------------------------------------------------------------------------------------
# I/O matrix row 2 — a planted probe fires
# --------------------------------------------------------------------------------------------


def test_planted_probe_at_the_controls_total_is_scored_caught() -> None:
    """Row 2: total matches the baseline and the id is among the FAILs → nothing to report."""
    assert _check(RED, 1, expect_total=2123, expect_red=["AgentView"]) == ([], [])


def test_expect_red_matches_on_a_substring_of_the_printed_id() -> None:
    """A caller naming the probe need not reproduce the run's `|project| file > suite > test` id."""
    assert _check(RED, 1, expect_total=2123, expect_red=["AgentView.test.tsx"]) == ([], [])
    refusals, complaints = _check(RED, 1, expect_total=2123, expect_red=["DeckView"])
    assert (refusals, len(complaints)) == ([], 1)


def test_a_red_run_fails_expect_green() -> None:
    """The other half of row 2: the same red run cannot also be certified green."""
    refusals, complaints = _check(RED, 1, expect_total=2123, expect_green=True)
    assert refusals == []
    assert "expected a green suite" in complaints[0]


# --------------------------------------------------------------------------------------------
# I/O matrix row 3 — the plant broke a file's parse (lie #5)
# --------------------------------------------------------------------------------------------


def test_shrunken_collection_refuses_against_the_controls_total() -> None:
    """Row 3: 2098 against a baseline of 2123 is a 25-test shrink — refuse, score nothing."""
    refusals, complaints = _check(
        SHRUNK, 0, expect_total=2123, expect_red=["AgentView"], expect_green=True
    )
    assert len(refusals) == 1
    assert "shrank by 25" in refusals[0]
    assert complaints == []


def test_a_grown_collection_also_refuses() -> None:
    """The baseline is an equality, not a floor: a bigger tree is also not the tree it describes."""
    refusals, _ = _check(GREEN, 0, expect_total=2098)
    assert len(refusals) == 1
    assert "grew by 25" in refusals[0]


def test_the_matching_total_does_not_refuse() -> None:
    """Positive twin for row 3: the identical shape at its own total is scoreable."""
    assert _check(SHRUNK, 0, expect_total=2098, expect_green=True) == ([], [])


# --------------------------------------------------------------------------------------------
# I/O matrix row 4 — a worker-fork crash
# --------------------------------------------------------------------------------------------


# Parametrised over the CONSTANT, never over a copy of it: a seventh signature added to the module
# then arrives with coverage instead of shipping untested.
@pytest.mark.parametrize("signature", vph._CRASH_SIGNATURES)
def test_a_crash_signature_discards_the_run(signature: str) -> None:
    """Row 4: every recorded signature makes the transcript non-evidence, even at its own total."""
    text = GREEN.replace(" RUN ", f"{signature}\n RUN ")
    refusals, complaints = _check(text, 0, expect_total=2123, expect_green=True)
    assert any("crash signature" in r for r in refusals)
    assert complaints == []


@pytest.mark.parametrize("signature", vph._CRASH_SIGNATURES)
def test_a_signature_behind_an_error_prefix_is_still_seen(signature: str) -> None:
    """The pool's own message arrives as `Error: <signature>`, so the anchor admits that prefix."""
    text = GREEN.replace(" RUN ", f"Error: {signature}\n RUN ")
    refusals, _ = _check(text, 0, expect_total=2123, expect_green=True)
    assert any("crash signature" in r for r in refusals)


@pytest.mark.parametrize("signature", vph._CRASH_SIGNATURES)
def test_a_signature_quoted_mid_sentence_does_not_refuse(signature: str) -> None:
    """The anchor's whole purpose: a test that merely PRINTS a signature — this file's own suite,
    most obviously — must not refuse every run of the harness forever."""
    text = GREEN.replace(
        " RUN ", f"stdout | some.test.ts > it matches {signature} in output\n RUN "
    )
    refusals, complaints = _check(text, 0, expect_total=2123, expect_green=True)
    assert refusals == []
    assert complaints == []


def test_the_realistic_c6_5_shape_refuses_on_both_counts() -> None:
    """Row 4 as actually sighted: the worker died AND took a file's tests with it, so the crash
    signature and the shrink against the baseline both fire on the one transcript."""
    refusals, complaints = _check(CRASHED, 0, expect_total=2123, expect_green=True)
    assert any("crash signature" in r for r in refusals)
    assert any("shrank by 25" in r for r in refusals)
    assert complaints == []


def test_the_crashed_transcript_without_its_signature_still_refuses_for_the_shrink() -> None:
    """Positive twin for row 4, and the attribution test: strip ONLY the signature and score the
    same transcript at the same baseline. The crash refusal must disappear while the shrink refusal
    stays — which is what proves the crash check fired above on its own merits rather than the
    harness refusing everything it is handed."""
    clean = CRASHED.replace("[vitest-pool] Worker exited unexpectedly\n", "")
    refusals, _ = _check(clean, 0, expect_total=2123)
    assert not any("crash signature" in r for r in refusals)
    assert any("shrank by 25" in r for r in refusals)


def test_the_crashed_numbers_at_their_own_total_are_fully_scoreable() -> None:
    """The other half of the twin: with neither the signature nor a baseline mismatch, the very
    same numbers pass clean — so neither refusal above is an artefact of the fixture's shape."""
    clean = CRASHED.replace("[vitest-pool] Worker exited unexpectedly\n", "")
    assert _check(clean, 0, expect_total=2098, expect_green=True) == ([], [])


# --------------------------------------------------------------------------------------------
# I/O matrix row 5 — a silent file drop with no signature
# --------------------------------------------------------------------------------------------


def test_categories_that_do_not_sum_to_the_total_refuse() -> None:
    """Row 5: `74 passed (75)` — a file entered the run and never reported."""
    refusals, complaints = _check(DROPPED_FILE, 0, expect_total=2123, expect_green=True)
    assert any("'Test Files' categories sum to 74" in r for r in refusals)
    assert any("'Tests' categories sum to 2098" in r for r in refusals)
    assert complaints == []


def test_multi_category_tallies_that_do_sum_are_accepted() -> None:
    """Positive twin for row 5: skipped and todo are part of the total, not a shortfall."""
    text = f"""
 RUN  v4.1.10 {OWNED_ROOT}

 Test Files  1 failed | 73 passed | 1 skipped (75)
      Tests  1 failed | 2100 passed | 20 skipped | 2 todo (2123)
 FAIL  |dom| src/components/AgentView.test.tsx > AgentView > renders
"""
    assert _check(text, 1, expect_total=2123, expect_red=["AgentView"]) == ([], [])


def test_a_failure_the_harness_cannot_name_refuses() -> None:
    """A tally of 2 failures with one FAIL line means a red the harness could never match."""
    text = RED.replace("Tests  1 failed | 2122 passed", "Tests  2 failed | 2121 passed")
    refusals, complaints = _check(text, 1, expect_total=2123, expect_red=["AgentView"])
    assert any("cannot name" in r for r in refusals)
    assert complaints == []


def test_extra_fail_lines_beyond_the_tally_are_not_refused() -> None:
    """Positive twin: vitest also prefixes a failed FILE with FAIL, so a surplus is harmless."""
    text = RED.replace(
        " FAIL  |dom|", " FAIL  |dom| src/components/AgentView.test.tsx\n FAIL  |dom|"
    )
    assert _check(text, 1, expect_total=2123, expect_red=["AgentView"]) == ([], [])


def test_a_file_level_fail_cannot_offset_an_unnamed_failing_test() -> None:
    """The MIXTURE, and the reason the count is over test-level lines only. Two failures tallied,
    two FAIL lines printed — but one of them names a FILE, so only one actual test is named and the
    other is a red the harness could never match. A raw line count stays silent on exactly this."""
    text = RED.replace("Tests  1 failed | 2122 passed", "Tests  2 failed | 2121 passed").replace(
        " FAIL  |dom|", " FAIL  |dom| src/components/DeckView.test.tsx\n FAIL  |dom|"
    )
    refusals, complaints = _check(text, 1, expect_total=2123, expect_red=["AgentView"])
    assert any("cannot name" in r and "only 1 test-level" in r for r in refusals)
    assert complaints == []


def test_a_file_level_fail_can_satisfy_expect_red() -> None:
    """A plant that breaks a file at TRANSFORM time fails the file with zero failing tests inside
    it, and the author who planted there should still see their probe fire. The lie that shape
    could otherwise tell — the file's tests vanishing from the count — is caught by --expect-total
    upstream, which is why matching FAIL lines loosely here is safe."""
    assert _check(FILE_LEVEL_FAIL, 1, expect_total=2098, expect_red=["AgentView"]) == ([], [])


def test_the_transform_error_shape_is_caught_by_the_total_not_by_the_fail_line() -> None:
    """Its negative control: the same transcript against the real baseline refuses on the shrink,
    naming the 25 tests the broken file took with it (lie #5) rather than the FAIL line."""
    refusals, _ = _check(FILE_LEVEL_FAIL, 1, expect_total=2123, expect_red=["AgentView"])
    assert any("shrank by 25" in r for r in refusals)


# --------------------------------------------------------------------------------------------
# The exit-code veto
# --------------------------------------------------------------------------------------------


def test_a_nonzero_exit_against_a_fully_green_tally_refuses() -> None:
    """vitest exits non-zero for failures that never reach the tally (an unhandled rejection, an
    afterAll hook, a worker error). Such a run parses as consistent and prints no FAIL line, so
    --expect-green would certify it — the c5-1 review-round-2 hole, in vitest dialect."""
    refusals, complaints = _check(GREEN_TALLY_NONZERO_EXIT, 1, expect_total=2123, expect_green=True)
    assert any("fully green" in r and "OUTSIDE the test tally" in r for r in refusals)
    assert complaints == []


def test_the_same_transcript_at_exit_zero_is_certified_green() -> None:
    """Positive twin: the exit code is the ONLY difference, so the veto is what fired above and
    the harness is not simply refusing every green transcript it sees."""
    assert _check(GREEN_TALLY_NONZERO_EXIT, 0, expect_total=2123, expect_green=True) == ([], [])


def test_a_nonzero_exit_with_a_red_tally_is_not_vetoed() -> None:
    """The exit code still never decides a verdict ALONE: an ordinary red run exits non-zero and is
    scored normally. Only the CONTRADICTION — nothing red, process failed — is refused."""
    assert _check(RED, 1, expect_total=2123, expect_red=["AgentView"]) == ([], [])


# --------------------------------------------------------------------------------------------
# I/O matrix row 6 — the wrong resolved root
# --------------------------------------------------------------------------------------------


def test_a_case_flipped_root_in_the_banner_refuses() -> None:
    """Row 6: lies #1-2, asserted on EVERY platform. On Windows the flipped character is the drive
    letter, which is the lie verbatim; on POSIX it is the first segment's initial, which the same
    case-sensitive comparison rejects. Not skipif-Windows, because the only CI job running
    tests/unit/ is ubuntu — a skipped test here means the module's headline claim can be regressed
    with fully green CI, and only on the one platform where the lie was actually recorded."""
    refusals, complaints = _check(WRONG_ROOT, 0, expect_total=2123, expect_green=True)
    assert any("resolved root" in r for r in refusals)
    assert complaints == []


@pytest.mark.skipif(os.name != "nt", reason="drive-letter case is a Windows concept")
def test_the_case_flip_is_the_recorded_drive_letter_lie_on_windows() -> None:
    """Pins what the platform-independent test above is actually reproducing here: `C:` → `c:`."""
    assert OWNED_ROOT[:2] == OWNED_ROOT[:2].upper()
    assert WRONG_ROOT_PATH[:2] == OWNED_ROOT[:2].lower()


def test_an_unrelated_root_refuses() -> None:
    """Row 6, portably: any root that is not the owned ui directory is a mismatch."""
    text = GREEN.replace(OWNED_ROOT, "/somewhere/else/ui")
    refusals, _ = _check(text, 0, expect_total=2123)
    assert any("resolved root" in r for r in refusals)


def test_a_missing_banner_refuses() -> None:
    """No banner means the run never announced a root — there is nothing here proving it started."""
    text = "\n".join(line for line in GREEN.splitlines() if " RUN " not in line)
    refusals, _ = _check(text, 0, expect_total=2123)
    assert any("never announced a root" in r for r in refusals)


@pytest.mark.parametrize("spelling", [OWNED_ROOT, str(vph._UI_DIR)])
def test_both_spellings_of_the_owned_root_are_accepted(spelling: str) -> None:
    """Positive twin for row 6: the comparison is separator-insensitive, so neither vitest's
    forward-slash banner nor the native-separator form is what makes the mismatches above fire.

    On POSIX the two spellings coincide and this is one case run twice — harmless, and the honest
    description of a check that only has work to do on Windows. The mismatch tests above are the
    ones that must bite everywhere, and they do.
    """
    text = GREEN.replace(OWNED_ROOT, spelling)
    assert _check(text, 0, expect_total=2123, expect_green=True) == ([], [])


# --------------------------------------------------------------------------------------------
# An unparseable summary
# --------------------------------------------------------------------------------------------


def test_an_unparseable_summary_refuses_and_scores_nothing() -> None:
    """`no tests` gives no collected count, and an unvalidated count is what this script refuses."""
    refusals, complaints = _check(
        NO_SUMMARY, 1, expect_total=2123, expect_red=["AgentView"], expect_green=True
    )
    assert len(refusals) == 1
    assert "no collected count to validate" in refusals[0]
    assert complaints == []


# --------------------------------------------------------------------------------------------
# I/O matrix row 7 — npm not on PATH, and the invocation contract
# --------------------------------------------------------------------------------------------


def test_missing_npm_raises_before_any_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """Row 7: shutil.which returns None → a refusal naming npm, raised before any subprocess.

    Matched on HarnessRefusalError, not the RuntimeError base: `main()` catches only the subclass,
    so a future rewrite that raised a bare RuntimeError would satisfy a base-class match while
    turning this refusal into an uncaught traceback.
    """
    monkeypatch.setattr("shutil.which", lambda _name: None)

    def explode(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("a run was started despite npm being unresolvable")

    monkeypatch.setattr(subprocess, "run", explode)
    with pytest.raises(vph.HarnessRefusalError, match="npm"):
        vph.run_full_suite()


def test_a_missing_ui_directory_raises_before_any_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """A repo restructure must surface as a refusal, not as a raw NotADirectoryError out of
    subprocess.run — which is an uncaught crash, and one `main()`'s except clause would miss."""
    monkeypatch.setattr("shutil.which", lambda _name: r"C:\fake\npm.cmd")
    monkeypatch.setattr(vph, "_UI_DIR", vph._UI_DIR / "does-not-exist")

    def explode(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("a run was started against a nonexistent ui directory")

    monkeypatch.setattr(subprocess, "run", explode)
    with pytest.raises(vph.HarnessRefusalError, match="does not exist"):
        vph.run_full_suite()


def test_a_hung_run_is_refused_rather_than_waited_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """The silent sibling of the crash signatures: a worker that DEADLOCKS prints nothing and never
    returns, and capture_output=True then waits on a pipe forever with no output to show for it."""
    monkeypatch.setattr("shutil.which", lambda _name: r"C:\fake\npm.cmd")

    def timeout(*_args: object, **kwargs: object) -> None:
        raise subprocess.TimeoutExpired(cmd="npm test", timeout=kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(vph.HarnessRefusalError, match="did not finish within"):
        vph.run_full_suite()


def test_the_run_is_cis_own_command_with_no_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    """Positive twin for row 7, and AC 3: the resolved npm path, shell=False, the owned cwd."""
    recorded: dict[str, object] = {}
    monkeypatch.setattr("shutil.which", lambda _name: r"C:\fake\npm.cmd")

    class Completed:
        stdout = GREEN
        stderr = ""
        returncode = 0

    def fake_run(argv, **kwargs):
        recorded["argv"] = argv
        recorded.update(kwargs)
        return Completed()

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = vph.run_full_suite()

    assert recorded["argv"] == [r"C:\fake\npm.cmd", "test"]
    assert recorded["shell"] is False
    assert recorded["cwd"] == vph._UI_DIR
    # Asserted, not merely swallowed by **kwargs: an unbounded capture_output run waits on a hung
    # vitest forever, which is the one failure the crash signatures cannot see.
    assert recorded["timeout"] == vph._RUN_TIMEOUT_SECONDS
    assert isinstance(recorded["timeout"], int) and recorded["timeout"] > 0
    assert result.tests_total == 2123


def test_the_run_decodes_as_utf8_not_the_locale_codec(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression, found by this script's own firing proof (2026-08-13): `text=True` alone decodes
    with cp1252 on Windows, and it is vitest's FAILING output that carries non-ASCII. The green run
    survived; the red one killed subprocess's reader threads and returned two None streams — the
    harness dying exactly when it had a failure to report."""
    recorded: dict[str, object] = {}
    monkeypatch.setattr("shutil.which", lambda _name: r"C:\fake\npm.cmd")

    class Completed:
        stdout = RED.replace(" FAIL ", " × ❯ FAIL ")
        stderr = ""
        returncode = 1

    def fake_run(argv, **kwargs):
        recorded.update(kwargs)
        return Completed()

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = vph.run_full_suite()

    assert recorded["encoding"] == "utf-8"
    assert recorded["errors"] == "replace"
    assert result.tests_failed == 1


def test_the_owned_ui_dir_is_fully_resolved() -> None:
    """AC 3's cwd half, on every platform. `resolve()` is idempotent, so a path equal to its own
    resolution is one that went through it — which `os.path.abspath` would not have produced."""
    assert vph._UI_DIR.is_absolute()
    assert vph._UI_DIR == vph._UI_DIR.resolve()
    assert vph._UI_DIR.name == "ui"


@pytest.mark.skipif(os.name != "nt", reason="drive-letter case is a Windows concept")
def test_the_owned_ui_dir_has_an_uppercase_drive_letter() -> None:
    """The Windows specialisation of the above, with the non-vacuity anchor that makes it mean
    something: the same path through os.path.abspath KEEPS a lowercase drive (measured), which is
    exactly why the module resolves rather than abspaths."""
    assert vph._UI_DIR.drive != ""
    assert vph._UI_DIR.drive == vph._UI_DIR.drive.upper()
    assert os.path.abspath("c:/Users") == r"c:\Users"  # the rejected alternative, measured


# --------------------------------------------------------------------------------------------
# The CLI surface
# --------------------------------------------------------------------------------------------


def _stub_run(monkeypatch: pytest.MonkeyPatch, text: str, exit_code: int) -> None:
    monkeypatch.setattr(vph, "run_full_suite", lambda: vph.parse_vitest_output(text, exit_code))


def test_main_control_prints_the_expect_total_paste_line(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC 1: a green control prints the proof line and the literal line the planted run consumes."""
    _stub_run(monkeypatch, GREEN, 0)
    assert vph.main(["--control"]) == 0
    out = capsys.readouterr().out
    assert "vitest: 75 files / 2123 tests, 0 failed, exit 0" in out
    assert "CONTROL GREEN — score the planted run with:  --expect-total 2123" in out


def test_main_scores_a_planted_probe_zero(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC 4's scoring half: the planted id is reported RED and the process exits 0."""
    _stub_run(monkeypatch, RED, 1)
    assert vph.main(["--expect-total", "2123", "--expect-red", "AgentView"]) == 0
    assert "  RED    |dom| src/components/AgentView.test.tsx" in capsys.readouterr().out


def test_main_exits_non_zero_on_a_refusal_without_printing_a_complaint(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A refusal is not a verdict: the expectation is never scored beside it."""
    _stub_run(monkeypatch, SHRUNK, 0)
    assert vph.main(["--expect-total", "2123", "--expect-red", "AgentView"]) == 1
    err = capsys.readouterr().err
    assert "REFUSAL" in err
    assert "to be RED" not in err


def test_a_refused_run_leaves_nothing_pasteable_on_stdout(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The proof line is the most pasteable artifact this script makes, so a REFUSED run must not
    emit one. Printing before check() published a clean `vitest: …` on stdout for a run the very
    next line declared non-evidence — the "a refusal is not a verdict" rule beaten by print order.
    Asserting on stdout is the part the sibling test above structurally cannot see."""
    _stub_run(monkeypatch, SHRUNK, 0)
    assert vph.main(["--expect-total", "2123", "--expect-red", "AgentView"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "[REFUSED — NOT EVIDENCE]" in captured.err
    assert "vitest: 74 files / 2098 tests" in captured.err  # visible, but tagged and on stderr


def test_a_refused_red_run_does_not_print_pasteable_red_ids(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The same rule for the RED id lines: a refused run's failures are shown for diagnosis, on
    stderr and marked `(refused)`, never in the `  RED    ` form a proof would quote."""
    _stub_run(monkeypatch, RED, 1)
    assert vph.main(["--expect-total", "2098", "--expect-red", "AgentView"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "  RED    " not in captured.err
    assert "(refused)  |dom| src/components/AgentView.test.tsx" in captured.err


def test_main_exits_non_zero_when_a_probe_did_not_fire(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The negative control at the CLI boundary: a clean tree does not certify a probe."""
    _stub_run(monkeypatch, GREEN, 0)
    assert vph.main(["--expect-total", "2123", "--expect-red", "AgentView"]) == 1
    err = capsys.readouterr().err
    assert "to be RED" in err
    assert "REFUSAL" not in err


def test_main_rejects_a_control_carrying_expectations() -> None:
    """--control produces the baseline; letting it consume one would certify a stale tree."""
    with pytest.raises(SystemExit):
        vph.main(["--control", "--expect-total", "2123"])


def test_main_requires_a_baseline_for_a_scored_run() -> None:
    """No committed count constant exists, so a scored run must be handed the control's number."""
    with pytest.raises(SystemExit):
        vph.main(["--expect-red", "AgentView"])


def test_main_rejects_a_validated_total_that_scores_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The vacuous pass: --expect-total alone ran the whole suite, asserted nothing about it, and
    exited 0 behind a green proof line certifying precisely nothing — the exact shape this script
    exists to stop being pasted as evidence."""
    _stub_run(monkeypatch, GREEN, 0)
    with pytest.raises(SystemExit):
        vph.main(["--expect-total", "2123"])


def test_main_rejects_contradictory_expectations(monkeypatch: pytest.MonkeyPatch) -> None:
    """--expect-green says nothing is red and --expect-red says something is; argparse takes the
    pair happily and one of them is then guaranteed to complain."""
    _stub_run(monkeypatch, RED, 1)
    with pytest.raises(SystemExit):
        vph.main(["--expect-total", "2123", "--expect-green", "--expect-red", "AgentView"])


@pytest.mark.parametrize("blank", ["", "   "])
def test_main_rejects_a_blank_expect_red(blank: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """A blank id is a substring of every failure, so ANY red satisfies it — the vacuous probe, cf.
    the C4 retro's `expect(x.concat(f)).toContain(f)`, true for any string."""
    _stub_run(monkeypatch, RED, 1)
    with pytest.raises(SystemExit):
        vph.main(["--expect-total", "2123", "--expect-red", blank])


def test_main_accepts_the_two_valid_scored_shapes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Positive twin for the four rejections above: the legitimate invocations still work, so the
    new argument validation is not simply refusing everything."""
    _stub_run(monkeypatch, RED, 1)
    assert vph.main(["--expect-total", "2123", "--expect-red", "AgentView"]) == 0
    _stub_run(monkeypatch, GREEN, 0)
    assert vph.main(["--expect-total", "2123", "--expect-green"]) == 0


def test_main_reports_an_unresolvable_npm_as_a_refusal(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Row 7 at the CLI boundary: exit non-zero, and say which tool is missing."""
    monkeypatch.setattr("shutil.which", lambda _name: None)
    assert vph.main(["--control"]) == 1
    assert "npm is not on PATH" in capsys.readouterr().err


# --------------------------------------------------------------------------------------------
# Command drift — the surface argv ownership does NOT cover
# --------------------------------------------------------------------------------------------
#
# `_NPM_ARGS == ("test",)` compares the constant against a copy of itself and would survive any
# drift at all. Owning argv fixes what this script types; it does not fix what `npm test` MEANS.
# That meaning lives in two files nothing here used to read:
#
#   * `ui/package.json`'s `"test"` script. Change it to `vitest run --project dom` and every probe
#     this harness will ever score silently narrows to half the suite, with all tests still green.
#     Change it to bare `vitest` and `run_full_suite()` blocks on watch mode until the timeout.
#   * `.github/workflows/ci.yml`'s `frontend` job. The owned invocation is only "CI's own command"
#     for as long as CI's own command is still `npm test` in `ui/`.
#
# Repo idiom for pinning package.json in a test is `ui/tests/package-contract.test.ts`; this is the
# Python-side equivalent, homed with the harness it protects.

REPO_ROOT = vph._UI_DIR.parent

# Flags and forms that would narrow a vitest run, or stop it being one run that terminates.
_NARROWING = (
    "--project",
    "--shard",
    "--dir",
    "--related",
    "--changed",
    "--testNamePattern",
    "-t ",
    "--watch",
    "&&",
    ";",
    "|",
)


def _narrowing_tokens(script: str) -> list[str]:
    return [token for token in _NARROWING if token in script]


def _ci_frontend_block() -> list[str]:
    """The `frontend:` job's lines from `.github/workflows/ci.yml`.

    A plain indentation scan rather than a YAML parse: pyyaml reaches this environment only
    transitively through pre-commit, and the repo's own standing rule (see the `websockets` note in
    pyproject.toml) is that a committed tool does not lean on another package's dependency.
    """
    lines = (
        (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8").splitlines()
    )
    start = next(i for i, line in enumerate(lines) if line.rstrip() == "  frontend:")
    block: list[str] = []
    for line in lines[start + 1 :]:
        if line.strip() and not line.startswith("   "):
            break
        block.append(line)
    return block


def test_the_ui_test_script_is_still_a_single_full_non_interactive_run() -> None:
    """`npm test` must still MEAN "run every test once and exit"."""
    package = json.loads((vph._UI_DIR / "package.json").read_text(encoding="utf-8"))
    script = package["scripts"]["test"]

    assert script.startswith("vitest run"), (
        f"ui/package.json's test script is {script!r}. Bare `vitest` is WATCH mode, which makes "
        "run_full_suite() block until the timeout with no output"
    )
    assert _narrowing_tokens(script) == [], (
        f"ui/package.json's test script is {script!r}, which narrows or chains the run — every "
        "probe this harness scores would silently inherit that narrowing while staying green"
    )


def test_the_narrowing_detector_actually_detects_narrowing() -> None:
    """Non-vacuity anchor for the test above: a checker that finds nothing in anything would pass
    it for any script at all. These are the exact drifts the review named."""
    assert _narrowing_tokens("vitest run --project dom") == ["--project"]
    assert _narrowing_tokens("vitest run && echo ok") == ["&&"]
    assert _narrowing_tokens("vitest run -t AgentView") == ["-t "]
    assert not "vitest".startswith("vitest run")  # bare `vitest` fails the watch-mode assert


def test_the_owned_invocation_still_equals_cis_own_command() -> None:
    """Argv ownership is only worth anything while the owned argv IS what CI runs."""
    block = _ci_frontend_block()
    # Non-vacuity: prove the block was actually found and is the job we think it is, so a rename
    # surfaces here rather than turning every assertion below into a vacuous pass over [].
    assert len(block) > 20
    assert any("name: lint" in line for line in block)

    owned = "npm " + " ".join(vph._NPM_ARGS)
    assert any(line.strip() == "working-directory: ui" for line in block), (
        "CI's frontend job no longer runs in ui/, so the harness's owned cwd is no longer CI's"
    )
    assert any(line.strip() == f"run: {owned}" for line in block), (
        f"CI's frontend job no longer contains a `run: {owned}` step, so the harness's owned argv "
        "has drifted from the command it is supposed to mirror"
    )
