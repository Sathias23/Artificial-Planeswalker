"""Run the FULL vitest suite and report, machine-readably, which frontend tests actually went red.

The frontend half of :mod:`scripts.probe_harness`, promoted at the Epic C6 retrospective (action
item R2). The pytest half owns argv so a Python probe cannot be narrowed; until this existed the
``ui/`` side had no equivalent, so every story rebuilt the validation by hand — roughly twenty
hand-run plants across six C6 stories.

**The lies this refuses to repeat.** The C4 retrospective recorded five *probe-harness lies*, under
every one of which a probe reads CAUGHT for free, and c6-5 sighted a sixth shape:

1-2. a forward-slash ``cwd`` with a **lowercase drive letter** breaks vitest's project-config
     resolution — ``'c:/…/ui'`` exits 1 having run nothing, ``'C:\\…\\ui'`` runs the suite. Defended
     by owning the cwd (:data:`_UI_DIR`, resolved with :meth:`Path.resolve`) and cross-checked
     against the RUN banner the run itself prints.
3.   the standalone-runner crash: test files invoked as a pair outside ``npm test`` die before a
     single assertion. Defended by owning argv — the run is CI's own command and nothing else.
4.   ``subprocess.run(["npm", "test"], shell=True)`` on Windows passes only the first list element
     to ``cmd.exe``. Defended by resolving npm through :func:`shutil.which` and never using a shell.
5.   a plant that mutated a component into TSX that would not parse, shrinking collection from
     ~1,655 to 1,596 with every assertion "caught". Defended by ``--expect-total``, whose value the
     ``--control`` run produces.
6.   a vitest worker-fork crash that silently drops a whole test *file* — seen twice in c6-5.
     Defended by :data:`_CRASH_SIGNATURES` and by the internal-consistency check.

**A refusal is not a verdict.** Anything that makes a run non-evidence — a crash signature, the
wrong resolved root, an unparseable summary, a tally that does not add up, a total that does not
match the control's — reports as a REFUSAL, exits non-zero, and scores *no* expectation. That is
the ``probe_harness.py`` precedent (its early return at the exit-code branch), and it exists so a
true complaint is never printed beside false ones.

**The collected count is the scoring criterion, not the exit code** (ruled at c6-3). npm's exit
status is printed in the proof line as corroboration and never decides a verdict alone.

**What this cannot see.** It proves a test id was reported failing by a full run; it does not read
the assertion, so it cannot tell a guard that fired for the planted reason from one that fired for
an unrelated one. It does not run ``tsc -b`` or the lint gates — only ``npm test``. It does not fix
the cold-eslint timeout flake (C6 R5) or the worker-fork crash; it only refuses to *score* a run
carrying them, which is why ``--control`` is specified warm.

Usage::

    uv run python -m scripts.vitest_probe_harness --control
    uv run python -m scripts.vitest_probe_harness --expect-total 2123 --expect-red AgentView
    uv run python -m scripts.vitest_probe_harness --expect-total 2123 --expect-green
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# OWNED, not configurable — the whole point of the script. `Path(__file__).resolve()` and never
# `os.path.abspath`: both make the path absolute, but only `resolve()` normalises a lowercase drive
# letter to `C:` (measured 2026-08-13). A lowercase-drive cwd is recorded lies #1-2, under which
# vitest resolves no project config, runs nothing, and every probe reads CAUGHT for free.
_UI_DIR = Path(__file__).resolve().parent.parent / "ui"

# The caller supplies EXPECTATIONS ONLY — never a test path, a `-t` filter, a `--project`, or any
# other vitest flag. This tuple is CI's `frontend` job verbatim (`.github/workflows/ci.yml`:
# `working-directory: ui`, `run: npm test`) and nothing more. C6 stories typed it by hand and c6-2
# drifted to `npm test -- --run`; argv ownership is what removes that variance.
_NPM_ARGS = ("test",)

# A bound on the run, because the failure class `_CRASH_SIGNATURES` exists for has a silent
# sibling: a worker that DEADLOCKS rather than dying prints nothing and never returns, and
# `capture_output=True` means the harness waits on a pipe forever with no output to show for it.
# The measured envelope is a 6.3 s warm run and a 48.9 s cold one whose eslint setup alone took
# 107 s (C6 R5's flake), so this is roughly an order of magnitude of headroom — generous enough
# that a slow machine is never mistaken for a hang, finite enough that a hang ends as a REFUSAL.
_RUN_TIMEOUT_SECONDS = 900

# Substrings that mean the run harmed itself. c6-5 sighted a vitest worker fork dying mid-run and
# taking a whole test FILE with it, twice — the surviving files still summarise cleanly, so without
# this the transcript looks like a smaller, greener suite. A run carrying either is discarded,
# never scored. Add to this tuple, not to the parser: the tests parametrise over it, so a seventh
# signature arrives with coverage rather than without.
_CRASH_SIGNATURES = (
    "[vitest-pool]",
    "Worker exited unexpectedly",
)


def _signature_pattern(signature: str) -> re.Pattern[str]:
    """Anchor a crash signature to the start of a line (an ``Error:`` prefix allowed).

    A bare substring search over the whole transcript makes the check hostage to test CONTENT: any
    suite that prints ``[vitest-pool]`` in its own output — a test ABOUT this harness, most
    obviously — would refuse every run forever, and a harness that refuses everything satisfies
    every refusal assert. The anchor is deliberately loose about a leading ``Error:`` because the
    pool's own message arrives that way; it is strict about the signature not being buried
    mid-sentence in someone else's prose.
    """
    return re.compile(
        r"^[^\S\n]*(?:\w*Error:[^\S\n]*)?" + re.escape(signature),
        re.MULTILINE,
    )


_CRASH_PATTERNS = tuple((sig, _signature_pattern(sig)) for sig in _CRASH_SIGNATURES)

# Terminal colour, stripped before parsing so a fixture captured from a TTY parses identically to
# one captured through a pipe (vitest disables colour only when it detects no TTY).
_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")

# CRLF and lone-CR normalisation, applied before anything anchors on `^`/`$`. `text=True` gives
# universal-newline translation, but a fixture transcript pasted from a Windows terminal or read
# with `newline=''` does not — and a stray `\r` before `$` turns every anchored pattern here into a
# silent non-match, i.e. an unparseable summary REFUSAL on a perfectly good run.
_LINE_BREAKS = re.compile(r"\r\n?")

# ` RUN  v4.1.10 <repo>/ui` — the run stating, in its own
# words, which root it resolved. Cross-checks lies #1-2 that owning the cwd already prevents.
_RUN_BANNER = re.compile(r"^\s*RUN\s+v[\d.]+\s+(?P<root>\S.*?)\s*$", re.MULTILINE)

# ` Test Files  1 failed | 74 passed (75)` and `      Tests  1 failed | 2122 passed (2123)`. The
# parenthesised figure is the total that ran; the pipe-separated body is the per-category breakdown
# whose sum must equal it. Both are needed and they catch DIFFERENT lies: a silently dropped file
# leaves `74 passed (75)` (sum != total), while a file that fails to parse shrinks both numbers
# together and is invisible without the control's baseline (`--expect-total`).
_TEST_FILES_LINE = re.compile(
    r"^\s*Test Files\s+(?P<body>\S.*?)\s*\((?P<total>\d+)\)\s*$", re.MULTILINE
)
_TESTS_LINE = re.compile(r"^\s*Tests\s+(?P<body>\S.*?)\s*\((?P<total>\d+)\)\s*$", re.MULTILINE)
# Every category vitest can print in that body. `todo` and `skipped` were collected and are part of
# the total, so they belong in the sum; anything vitest adds later that is NOT listed here makes the
# sum fall short of the total, which surfaces as a REFUSAL rather than as a silent miscount.
_CATEGORY_TOKEN = re.compile(r"(?P<count>\d+)\s+(?P<category>failed|passed|skipped|todo)\b")

# ` FAIL  |node| tests/lint-gates.test.ts > <suite> > <test>`. The project prefix is present because
# `ui/vite.config.ts` declares two vitest projects (`node` over `tests/**`, jsdom `dom` over
# `src/**`); it is captured into the id so `--expect-red 'node'`-style prefixes work and so the id
# printed here is the id the run printed.
_FAIL_LINE = re.compile(r"^\s*FAIL\s+(?P<nodeid>\S.*?)\s*$", re.MULTILINE)
# ` > ` is what separates a FAILING TEST from a FAILING FILE. vitest prefixes both with FAIL, but
# only a test id carries the `file > suite > test` path, and only test ids are countable against
# the `Tests` line's `failed` tally. Counting file-level lines toward that tally let a surplus
# file-level FAIL silently offset a test failure the harness could not name (review finding 11).
_TEST_ID_SEPARATOR = " > "


class HarnessRefusalError(RuntimeError):
    """Raised before a run happens when the environment cannot produce evidence."""


@dataclass(frozen=True)
class VitestResult:
    """What one full-suite vitest run observed.

    Attributes:
        root: The root path the run printed in its RUN banner, or ``None`` if no banner was found.
            Compared against :data:`_UI_DIR` so a run that resolved somewhere else is visible.
        files_total: The parenthesised total on the ``Test Files`` line, or ``None``.
        files_tally: Sum of every category on the ``Test Files`` line, or ``None``.
        tests_total: The parenthesised total on the ``Tests`` line, or ``None``. This is the number
            ``--expect-total`` is scored against — the collected count, not the exit code.
        tests_tally: Sum of every category on the ``Tests`` line, or ``None``.
        tests_failed: The ``failed`` category count on the ``Tests`` line, or ``None``. It is
            cross-checked against ``failed`` so a failure the harness cannot NAME is never scored
            as if it could be.
        failed: Ids the run printed on FAIL lines, in report order. Includes file-level FAIL lines
            as well as test-level ones, because ``--expect-red`` should be able to match either.
        exit_code: npm's exit status. Corroboration in the proof line; never a verdict on its own.
        crashes: Crash signatures found in the transcript, in :data:`_CRASH_SIGNATURES` order.
    """

    root: str | None
    files_total: int | None
    files_tally: int | None
    tests_total: int | None
    tests_tally: int | None
    tests_failed: int | None
    failed: tuple[str, ...]
    exit_code: int
    crashes: tuple[str, ...]

    @property
    def named_test_failures(self) -> tuple[str, ...]:
        """The subset of :attr:`failed` that names an individual TEST rather than a whole file."""
        return tuple(f for f in self.failed if _TEST_ID_SEPARATOR in f)

    def proof_line(self) -> str:
        """One pasteable line stating what was run and what came back."""
        files = "?" if self.files_total is None else self.files_total
        tests = "?" if self.tests_total is None else self.tests_total
        failed = len(self.failed) if self.tests_failed is None else self.tests_failed
        return f"vitest: {files} files / {tests} tests, {failed} failed, exit {self.exit_code}"


def _sum_categories(body: str) -> int:
    return sum(int(m.group("count")) for m in _CATEGORY_TOKEN.finditer(body))


def _category(body: str, name: str) -> int:
    return sum(
        int(m.group("count")) for m in _CATEGORY_TOKEN.finditer(body) if m.group("category") == name
    )


def parse_vitest_output(output: str, exit_code: int) -> VitestResult:
    """Turn a captured ``npm test`` transcript into a :class:`VitestResult`.

    Pure: no subprocess, no filesystem. Splitting parsing from running is what lets every negative
    control in the test suite be a fixture transcript that needs no npm — the C4 retro named the
    negative controls the part least likely to be re-invented correctly, so they must be cheap.

    Args:
        output: stdout and stderr of the run, concatenated.
        exit_code: npm's exit status, recorded but never scored alone.

    Returns:
        The parsed observation. Fields that could not be read are ``None`` rather than guessed —
        :func:`check` turns each of those into a REFUSAL.
    """
    text = _LINE_BREAKS.sub("\n", _ANSI.sub("", output))

    banner = _RUN_BANNER.search(text)
    # LAST match, not first: the summary block is printed at the end of the transcript, and a
    # failing test's own captured output can contain a summary-shaped line. The tail wins.
    files_matches = list(_TEST_FILES_LINE.finditer(text))
    tests_matches = list(_TESTS_LINE.finditer(text))
    files_match = files_matches[-1] if files_matches else None
    tests_match = tests_matches[-1] if tests_matches else None

    return VitestResult(
        root=banner.group("root") if banner is not None else None,
        files_total=int(files_match.group("total")) if files_match is not None else None,
        files_tally=(
            _sum_categories(files_match.group("body")) if files_match is not None else None
        ),
        tests_total=int(tests_match.group("total")) if tests_match is not None else None,
        tests_tally=(
            _sum_categories(tests_match.group("body")) if tests_match is not None else None
        ),
        tests_failed=(
            _category(tests_match.group("body"), "failed") if tests_match is not None else None
        ),
        failed=tuple(m.group("nodeid") for m in _FAIL_LINE.finditer(text)),
        exit_code=exit_code,
        crashes=tuple(sig for sig, pattern in _CRASH_PATTERNS if pattern.search(text)),
    )


def _same_root(reported: str) -> bool:
    """Is the run's own banner root the directory this harness owns?

    Separator-insensitive (vitest prints forward slashes; :data:`_UI_DIR` renders native ones) but
    deliberately CASE-SENSITIVE: a lowercase drive letter is recorded lies #1-2, and normalising it
    away here would delete the very thing this cross-check exists to see.
    """
    return str(Path(reported.strip())) == str(_UI_DIR)


def check(
    result: VitestResult,
    *,
    expect_total: int | None,
    expect_red: list[str],
    expect_green: bool,
    control: bool,
) -> tuple[list[str], list[str]]:
    """Score *result*, separating REFUSALS from expectation complaints.

    Returns:
        ``(refusals, complaints)``. **If ``refusals`` is non-empty, ``complaints`` is empty** — the
        run is not evidence, so scoring an expectation against it would pair a true complaint with
        false ones (the ``probe_harness.py`` early-return precedent). Both are printed; either being
        non-empty exits non-zero.
    """
    refusals: list[str] = []

    if result.crashes:
        refusals.append(
            f"the run carries a crash signature ({', '.join(result.crashes)}) — a vitest worker "
            "that dies takes a whole test file with it and the survivors still summarise cleanly, "
            "so this transcript is not evidence. Re-run; if it repeats, that is the deferred "
            "worker-fork bug, not your plant"
        )

    if result.root is None:
        refusals.append(
            "no ' RUN  vX.Y.Z <root>' banner in the output, so the run never announced a root — "
            "there is nothing here to prove vitest started"
        )
    elif not _same_root(result.root):
        refusals.append(
            f"the run resolved root {result.root!r}, not the owned {str(_UI_DIR)!r} — a mismatched "
            "root (notably a lowercase drive letter) makes vitest resolve no project config and "
            "run nothing, under which every probe reads CAUGHT for free"
        )

    if result.tests_total is None or result.files_total is None:
        refusals.append(
            "could not parse a 'Test Files' and 'Tests' summary pair from the run, so there is no "
            "collected count to validate — and an unvalidated count is exactly what this script "
            "exists to stop being pasted as a proof"
        )
    else:
        # Internal consistency. A file dropped silently mid-run leaves `74 passed (75)`: the
        # categories no longer add up to the total the run itself declared.
        if result.files_tally != result.files_total:
            refusals.append(
                f"the 'Test Files' categories sum to {result.files_tally} but the run declared "
                f"{result.files_total} — a file entered the run and did not report"
            )
        if result.tests_tally != result.tests_total:
            refusals.append(
                f"the 'Tests' categories sum to {result.tests_tally} but the run declared "
                f"{result.tests_total} — tests entered the run and did not report"
            )
        # The absolute total, against the number the control run produced. This is the check that
        # sees lie #5: a plant that breaks a file's parse shrinks BOTH numbers together, so the run
        # stays internally consistent and only the baseline exposes it.
        if expect_total is not None and result.tests_total != expect_total:
            delta = expect_total - result.tests_total
            direction = "shrank" if delta > 0 else "grew"
            refusals.append(
                f"collection {direction} by {abs(delta)}: expected {expect_total} tests (the "
                f"control's number) and the run reports {result.tests_total} — the tree under test "
                "is not the tree the baseline describes, so no expectation below is scoreable"
            )

    # A failure the harness cannot NAME cannot be matched by `--expect-red`, and treating it as
    # absent would read as "your probe did not fire". Counted against the TEST-level FAIL lines
    # only: a file-level `FAIL |dom| src/x.test.tsx` is legitimate output, but counting it here let
    # one file-level line offset one unnamed failing test and the shortfall pass unseen. Only the
    # short direction is refused — a surplus of file-level lines is harmless.
    named = result.named_test_failures
    if result.tests_failed is not None and len(named) < result.tests_failed:
        refusals.append(
            f"the run tallies {result.tests_failed} failed tests but printed only {len(named)} "
            f"test-level FAIL line(s) — there is a failure here the harness cannot name"
        )

    # The exit code never decides a verdict ALONE (ruled at c6-3: the collected count is the
    # scoring criterion). It does get a VETO. vitest exits non-zero for things that never reach the
    # `Tests` tally — an unhandled rejection after the run completes, an afterAll hook that throws,
    # an unhandled error in a worker — and such a run parses as perfectly consistent, prints no FAIL
    # line, and would let `--expect-green` certify it. That is precisely the hole c5-1 review round
    # 2 found in the pytest sibling, where `--expect-green` certified an ERROR-ridden suite green
    # until `_ERROR_LINE` was wired in. A tally with nothing red and a process that failed anyway is
    # a contradiction, and a contradiction is not evidence.
    if result.exit_code != 0 and not result.failed and result.tests_failed == 0:
        refusals.append(
            f"npm exited {result.exit_code} but the run's own tally is fully green "
            f"({result.tests_total} passed, no FAIL line) — something failed OUTSIDE the test "
            "tally (an unhandled rejection, a hook, a worker error), so this run is a "
            "contradiction rather than a green suite"
        )

    if refusals:
        return refusals, []

    complaints: list[str] = []

    # `--control` asserts the do-nothing baseline: the unplanted tree must read NOT-caught. A red
    # control is a REFUSAL rather than a complaint because it invalidates the number the control
    # exists to produce — HALT and report; never repair a test to make the control pass.
    if control and result.failed:
        return [
            "the control run is NOT green on this tree "
            f"(failed: {list(result.failed)}) — HALT: the baseline it exists to produce is void. "
            "If this is the known cold-eslint timeout flake (C6 R5), re-run warm; otherwise report "
            "it. Never repair a test to make the control pass"
        ], []

    if expect_green and result.failed:
        complaints.append(f"expected a green suite; failed: {list(result.failed)}")

    # Substring rather than equality, matching the pytest half: a vitest id is
    # `|project| file > suite > test`, and the author naming the probe should not have to reproduce
    # the run's exact spelling. A caller wanting exact matching can paste the whole id.
    #
    # Matched against ALL FAIL lines, file-level ones included, and that is deliberate: a plant that
    # breaks a file badly enough to fail at transform time produces `FAIL |dom| src/x.test.tsx` with
    # zero failing tests inside it, and an author who planted in that file should still see their
    # probe fire. The lie that shape could otherwise tell — the file's tests vanishing from the
    # count — is caught upstream by `--expect-total`, not here.
    for nodeid in expect_red:
        if not any(nodeid in failed for failed in result.failed):
            complaints.append(
                f"expected {nodeid!r} to be RED in the full vitest suite and it was not "
                f"(failures were: {list(result.failed)})"
            )

    return refusals, complaints


def _npm() -> str:
    """Resolve npm to an absolute path.

    Raises:
        HarnessRefusalError: If npm is not on PATH. Raised BEFORE any run, because
            ``subprocess.run(["npm", …])`` raises ``FileNotFoundError`` on Windows (npm is
            ``npm.cmd``) — and that error is exactly what drove recorded lie #4 to ``shell=True``,
            under which Windows passes only the first list element and nothing runs at all.
    """
    resolved = shutil.which("npm")
    if resolved is None:
        raise HarnessRefusalError(
            "npm is not on PATH; refusing to run. This harness resolves npm with shutil.which and "
            "never uses shell=True (recorded lie #4)"
        )
    return resolved


def _ui_dir() -> Path:
    """Return the owned ui directory.

    Raises:
        HarnessRefusalError: If it is not a directory. Without this a repo restructure surfaces as
            a raw ``NotADirectoryError`` traceback out of ``subprocess.run`` — an uncaught crash
            rather than the refusal it is, and one :func:`main` would not have caught.
    """
    if not _UI_DIR.is_dir():
        raise HarnessRefusalError(
            f"the owned ui directory {str(_UI_DIR)!r} does not exist; refusing to run. This path "
            "is derived from the script's own location, so a miss means the repo moved under it"
        )
    return _UI_DIR


def run_full_suite() -> VitestResult:
    """Run CI's own ``npm test`` in the owned ui directory and parse what came back.

    Raises:
        HarnessRefusalError: If npm or the ui directory is missing, or the run exceeded
            :data:`_RUN_TIMEOUT_SECONDS`.
    """
    argv = [_npm(), *_NPM_ARGS]
    cwd = _ui_dir()
    try:
        completed = subprocess.run(
            argv,
            cwd=cwd,  # owned; see `_UI_DIR`
            capture_output=True,
            text=True,
            # EXPLICIT utf-8, not the locale codec. `text=True` alone decodes with cp1252 on a
            # default Windows install, and vitest's FAILING output is the half carrying non-ASCII
            # (`×`, `❯`, `→`). Measured 2026-08-13 during this script's own firing proof: the green
            # run decoded fine, the red one raised UnicodeDecodeError inside subprocess's reader
            # threads, leaving BOTH streams None — the harness died only when there was a failure
            # to report, the one moment it exists for. `errors="replace"` so an odd byte degrades
            # one character rather than the whole verdict.
            encoding="utf-8",
            errors="replace",
            check=False,
            shell=False,  # never True: recorded lie #4
            timeout=_RUN_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise HarnessRefusalError(
            f"the run did not finish within {_RUN_TIMEOUT_SECONDS}s and was killed; refusing to "
            "report. A vitest worker that deadlocks rather than dying leaves no crash signature "
            "to find, so a hang can only be seen as a hang"
        ) from exc
    return parse_vitest_output(completed.stdout + completed.stderr, completed.returncode)


def main(argv: list[str] | None = None) -> int:
    """Run the vitest suite and report; exit non-zero on a refusal or an unmet expectation."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--control",
        action="store_true",
        help=(
            "do-nothing negative control: assert the UNPLANTED tree is green and print the "
            "--expect-total line the planted run must be scored with. Run warm"
        ),
    )
    parser.add_argument(
        "--expect-total",
        type=int,
        metavar="N",
        help="the total test count the control run produced; required unless --control",
    )
    parser.add_argument(
        "--expect-red",
        action="append",
        default=[],
        metavar="TESTID",
        help="assert this test id (or substring of one) is among the failures; repeatable",
    )
    parser.add_argument(
        "--expect-green",
        action="store_true",
        help="assert the whole vitest suite passed",
    )
    args = parser.parse_args(argv)

    # `--control` PRODUCES the baseline; it cannot also consume one. Accepting an expectation here
    # would let a caller assert the control against a stale number and call the tree pristine.
    if args.control and (args.expect_total is not None or args.expect_red or args.expect_green):
        parser.error("--control takes no expectations; it produces the --expect-total for them")
    if not args.control:
        # No committed expected-count constant exists (deliberately — nothing for a story to bump),
        # so a scored run must be handed the control's number or it has no count to validate.
        if args.expect_total is None:
            parser.error("--expect-total is required; get the number from a --control run")
        # And a validated count on its own scores NOTHING. Without this, `--expect-total 2123`
        # alone runs the whole suite, asserts nothing about it, exits 0, and prints a green proof
        # line certifying precisely nothing — a vacuous pass of exactly the shape this script was
        # built to stop being pasted as evidence.
        if not args.expect_red and not args.expect_green:
            parser.error(
                "a scored run needs an expectation: pass --expect-red and/or --expect-green "
                "(a validated total that scores nothing is a vacuous proof)"
            )
        # Self-contradictory: --expect-green asserts nothing is red, --expect-red asserts something
        # is. argparse accepts the pair happily, and one of them is guaranteed to complain.
        if args.expect_red and args.expect_green:
            parser.error("--expect-green and --expect-red contradict each other; pass one")
        # A blank id is a substring of every failure, so ANY red satisfies it — the vacuous
        # `--expect-red` (cf. the C4 retro's `expect(x.concat(f)).toContain(f)`, true of any
        # string).
        for nodeid in args.expect_red:
            if not nodeid.strip():
                parser.error("--expect-red needs a non-blank id; '' matches any failure at all")

    try:
        result = run_full_suite()
    except HarnessRefusalError as exc:
        print(f"vitest-probe-harness: REFUSAL — {exc}", file=sys.stderr)
        return 1

    refusals, complaints = check(
        result,
        expect_total=args.expect_total,
        expect_red=args.expect_red,
        expect_green=args.expect_green,
        control=args.control,
    )

    # SCORED FIRST, PRINTED SECOND, and stdout stays EMPTY on a refusal. The proof line is the most
    # pasteable artifact this script makes, and emitting it before `check()` published a clean
    # `vitest: 75 files / 2123 tests, …` on stdout for a run the very next line declared
    # non-evidence — precisely the "a refusal is not a verdict" rule, defeated by print order. On a
    # refusal everything goes to stderr behind an explicit tag, so nothing pasteable survives.
    if refusals:
        print(f"[REFUSED — NOT EVIDENCE] {result.proof_line()}", file=sys.stderr)
        for nodeid in result.failed:
            print(f"  (refused)  {nodeid}", file=sys.stderr)
        for refusal in refusals:
            print(f"vitest-probe-harness: REFUSAL — {refusal}", file=sys.stderr)
        return 1

    print(result.proof_line())
    for nodeid in result.failed:
        print(f"  RED    {nodeid}")
    for complaint in complaints:
        print(f"vitest-probe-harness: {complaint}", file=sys.stderr)
    if complaints:
        return 1

    if args.control:
        print(f"CONTROL GREEN — score the planted run with:  --expect-total {result.tests_total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
