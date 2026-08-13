"""Run the FULL test suite and report, machine-readably, which tests actually went red.

Why this exists (C4 retrospective, action item 4; scoped to the pytest side at c5-1 by Brad,
2026-08-07). The retro measured a recurring class of failure it named *probe-harness lies*: a story
claims "I planted a violation and the guard went red", and the claim is true of the command that was
run and false of the suite. The recorded shapes were a single-file ``pytest path/to/one_test.py``
presented as a full run, a ``-k`` filter that silently excluded the guard, and a run whose collected
count nobody looked at.

The fix is not discipline, it is **argv ownership**. This script builds its own pytest invocation
and accepts no test paths, no ``-k`` and no ``-m`` from the caller, so narrowing the run is not
something a caller can do wrong — there is no argument to get wrong. What the caller may supply
is the *expectation*: which node ids should be red, or that none should be. The collected count is
measured by a separate collection pass and printed with every result, so a run that shrank is
visible in the proof line itself rather than in nobody's memory.

**What this cannot see.** It proves a node id was reported failing by a full run; it does not read
the assertion, so it cannot tell a guard that fired for the planted reason from one that fired for
an unrelated one — that judgement stays with the author. It also cannot see the frontend:
``vitest`` and ``tsc -b`` are a separate toolchain, and three of the five recorded failure modes (a
lowercase-drive working directory, ``shell=True`` on Windows, an unparseable TSX file) are specific
to it. A story that touches ``ui/`` uses :mod:`scripts.vitest_probe_harness`, the other half.

Usage:
    uv run python -m scripts.probe_harness
    uv run python -m scripts.probe_harness --expect-green
    uv run python -m scripts.probe_harness --expect-red 'tests/unit/x.py::TestY::test_z'
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass

# OWNED, not configurable. Every argument that could narrow the run is fixed here: no test paths,
# no `-k`, no `-m` beyond the integration deselection the project's own gate uses. `--tb=no -q -rfE`
# asks for nothing but the one-line failure AND error summaries this script parses — `E` matters,
# because a fixture that breaks makes tests ERROR rather than FAIL, pytest still exits 1, and a
# harness reading only FAILED lines would certify that run green (c5-1 review, 2026-08-07).
_MARKER = "not integration"
_RUN_ARGV = (
    "uv",
    "run",
    "pytest",
    "-m",
    _MARKER,
    "-p",
    "no:cacheprovider",
    "--tb=no",
    "-q",
    "-rfE",
)
_COLLECT_ARGV = (
    "uv",
    "run",
    "pytest",
    "-m",
    _MARKER,
    "-p",
    "no:cacheprovider",
    "--collect-only",
    "-q",
)

# Non-greedy up to " - " or end of line, not `\S+`: a parametrized node id can itself contain a
# space (a string-valued param), and `\S+` silently truncated it there (c5-1 review round 2,
# 2026-08-07) — a truncated capture is a capture `--expect-red`'s substring check can miss on.
_FAILED_LINE = re.compile(r"^FAILED (?P<nodeid>.+?)(?: - |$)", re.MULTILINE)
_ERROR_LINE = re.compile(r"^ERROR (?P<nodeid>.+?)(?: - |$)", re.MULTILINE)
# `tests?` — pytest prints the singular "1 test collected" for a one-test collection.
_COLLECTED = re.compile(r"(?P<count>\d+)(?:/\d+)? tests? collected")
# The run's own summary line, e.g. "===== 2 failed, 2578 passed, 1 skipped in 147.77s =====".
# Anchored on pytest's `=` banner so this only ever reads the one line meant as a tally, never a
# coincidental "N passed" substring inside a test's own failure output.
_SUMMARY_LINE = re.compile(r"=+\s*(?P<body>.+?)\s+in\s+[\d.]+s(?:\s*\([^)]*\))?\s*=+")
# Every category here was collected and entered the run; `warnings` and `deselected` deliberately
# absent — the first is not a test, the second never entered the collected count (`--collect-only
# -q` reports the post-`-m` figure).
_SUMMARY_TOKEN = re.compile(
    r"(?P<count>\d+) (?P<category>failed|passed|skipped|xfailed|xpassed|errors?)\b"
)


@dataclass(frozen=True)
class ProbeResult:
    """What one full-suite run observed.

    Attributes:
        collected: Tests the collection pass found. Printed with every result so a run that shrank
            is visible in the proof line rather than invisible.
        failed: Node ids the run reported as FAILED, in report order.
        errored: Node ids the run reported as ERROR (e.g. a broken fixture), in report order — a
            pytest run can exit 1 with these and zero FAILED lines, and until c5-1 review round 2
            nothing here looked at them, so `--expect-green` certified that run green.
        exit_code: pytest's exit status for the run.
        summary_total: The sum of every category in the run's own printed summary line
            (failed + passed + skipped + xfailed + xpassed + error), or ``None`` if that line could
            not be parsed. Cross-checked against `collected` in :func:`_check` so a run whose own
            tally disagrees with the separate collection pass is visible rather than trusted blind.
    """

    collected: int
    failed: tuple[str, ...]
    errored: tuple[str, ...]
    exit_code: int
    summary_total: int | None

    def proof_line(self) -> str:
        """One pasteable line stating what was run and what came back."""
        bad = len(self.failed) + len(self.errored)
        verdict = (
            "0 failed" if not bad else f"{len(self.failed)} failed, {len(self.errored)} errored"
        )
        return (
            f"full suite (-m '{_MARKER}'): {self.collected} collected, {verdict}, "
            f"exit {self.exit_code}"
        )


def _run(argv: tuple[str, ...]) -> str:
    completed = subprocess.run(argv, capture_output=True, text=True, check=False)
    return completed.stdout + completed.stderr


def run_full_suite() -> ProbeResult:
    """Collect, then run, the whole suite this project gates on.

    Returns:
        The collected count, the failing and errored node ids, pytest's exit status, and the
        run's own summary tally (or ``None`` if unparseable).

    Raises:
        RuntimeError: If the collection pass produced no parseable count — which would mean the
            numbers below are unverified, and an unverified count is exactly what this script
            exists to stop being pasted as a proof.
    """
    collect_output = _run(_COLLECT_ARGV)
    match = _COLLECTED.search(collect_output)
    if match is None:
        raise RuntimeError(
            "could not parse a collected-test count from the collection pass; refusing to report "
            f"an unverified number. Raw tail:\n{collect_output[-2000:]}"
        )

    completed = subprocess.run(_RUN_ARGV, capture_output=True, text=True, check=False)
    output = completed.stdout + completed.stderr

    summary_match = _SUMMARY_LINE.search(output)
    summary_total = (
        sum(int(m.group("count")) for m in _SUMMARY_TOKEN.finditer(summary_match.group("body")))
        if summary_match is not None
        else None
    )

    return ProbeResult(
        collected=int(match.group("count")),
        failed=tuple(m.group("nodeid") for m in _FAILED_LINE.finditer(output)),
        errored=tuple(m.group("nodeid") for m in _ERROR_LINE.finditer(output)),
        exit_code=completed.returncode,
        summary_total=summary_total,
    )


def _check(result: ProbeResult, expect_red: list[str], expect_green: bool) -> list[str]:
    """Compare *result* against the caller's expectation, returning any complaints."""
    complaints: list[str] = []
    # 0 = all passed, 1 = tests failed. ANYTHING ELSE means the suite did not run: 2 is a collection
    # error or a usage error, 3 an internal error, 4 a bad invocation. This check exists because a
    # planted violation that happened to be a SyntaxError produced "0 failed" here on 2026-08-07 —
    # pytest never got far enough to fail anything, and only the collected count (1450 against
    # 2526) and this exit status said so. A run that did not happen must never read as evidence.
    # It returns immediately: every complaint below reads `result.failed`/`result.errored`/
    # `result.summary_total`, all of which this branch has just declared non-evidence, so scoring
    # them anyway would pair a true complaint with false ones in the same output (c5-1 review
    # round 2, 2026-08-07).
    if result.exit_code not in (0, 1):
        return [
            f"pytest exited {result.exit_code}, so the suite did not run to completion "
            f"(only {result.collected} tests collected) — no verdict below is evidence of anything"
        ]

    # The collected count comes from a separate `--collect-only` pass; this cross-checks it against
    # the sum of every category in the run's own summary line, so the two numbers disagreeing is
    # visible rather than silently trusted (c5-1 review round 2).
    if result.summary_total is None:
        complaints.append(
            "could not parse a summary line from the run to cross-check the collected count "
            f"({result.collected}) against"
        )
    elif result.summary_total != result.collected:
        complaints.append(
            f"collected {result.collected} tests but the run's own summary tallies "
            f"{result.summary_total} — the two passes disagree"
        )

    # ERROR is not FAILED: a broken fixture makes a test ERROR rather than FAIL, and pytest still
    # exits 1. Both count against a green expectation (c5-1 review round 2 — `_ERROR_LINE` existed
    # but nothing consulted it, so this exact case previously certified green).
    if expect_green and (result.failed or result.errored):
        complaints.append(
            f"expected a green suite; failed: {list(result.failed)}, "
            f"errored: {list(result.errored)}"
        )
    # Substring rather than equality: a parametrised guard reports as `...test_x[case]`, and the
    # author naming the test should not have to guess the id pytest will print. Ruled and kept as-is
    # at the c5-1 review round 2 decision (Brad, 2026-08-07): a caller wanting exact matching can
    # pass the full parametrised id.
    for nodeid in expect_red:
        if not any(nodeid in failed for failed in result.failed):
            complaints.append(
                f"expected {nodeid!r} to be RED in the full suite and it was not "
                f"(failures were: {list(result.failed)})"
            )
    return complaints


def main(argv: list[str] | None = None) -> int:
    """Run the suite and report; exit non-zero if an expectation was not met."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--expect-red",
        action="append",
        default=[],
        metavar="NODEID",
        help="assert this node id (or substring of one) is among the failures; repeatable",
    )
    parser.add_argument(
        "--expect-green",
        action="store_true",
        help="assert the whole suite passed",
    )
    args = parser.parse_args(argv)

    result = run_full_suite()
    print(result.proof_line())
    for nodeid in result.failed:
        print(f"  RED    {nodeid}")
    for nodeid in result.errored:
        print(f"  ERROR  {nodeid}")

    complaints = _check(result, args.expect_red, args.expect_green)
    for complaint in complaints:
        print(f"probe-harness: {complaint}", file=sys.stderr)
    return 1 if complaints else 0


if __name__ == "__main__":
    raise SystemExit(main())
