"""Unit tests for the CDP harness's reporting verdict (``scripts/cdp_harness.py``).

Scope is **the two seams that decide, before anything is opened or after everything is measured**:
the gate that refuses to touch the operator's real data directory, and the branch that refuses to
print a number. Both are reachable with no browser, no process and no network —
``refuse_the_operators_data_dir`` is the first thing :func:`~scripts.cdp_harness.cmd_refetch` does,
and ``_report_refetch`` / ``_print_refetch_run`` / ``_refetch_run_is_valid`` are pure functions over
run dicts. So are ``_largest_deck``'s and ``_card_the_deck_does_not_hold``'s failure paths, which is
why the honest statement of scope is *"the parts that decide"* rather than *"everything else needs
Chrome"* — much of the rest merely has not been worth testing, and the browser-driving half
genuinely does need Chrome and a copied 325 MB data directory.

**Why these two.** The refusal is the failure mode the C4 retrospective named: every probe harness
that lied in that epic lied by *producing zero results and being scored anyway*, and
``cdp_harness.py``'s own module docstring (trap 1) says so. The gate is the only thing standing
between a committed tool that drives ``add_card_to_deck`` and a live 325 MB database. A branch
nothing exercises is exactly the shape of thing that is wrong when it finally matters.

Two rules inherited from ``test_vitest_probe_harness.py``, both standing agreements:

* **Every refusal test gets a positive twin (C6 R8).** A reporter that refuses everything satisfies
  every refusal assert; the pair is the assertion, not either half.
* **A refusal must print no number.** "Refused" and "reported a number nobody should trust" are
  different failures, and only asserting the *absence* of the figure tells them apart.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from platformdirs import user_data_dir

import scripts.cdp_harness as cdp


def _run(index: int = 1, **over: Any) -> dict[str, Any]:
    """One valid ``measure_refetch`` result, built by **the shipped builder** and then overridden.

    ⚠️ ``cdp.refetch_result`` rather than a dict literal, and that is the whole point of the builder
    existing (c7-7 review, P9). A hand-rolled fixture is pinned only to itself: its "no unknown
    keys" assertion below would compare the literal to the literal, and renaming ``layout_ms`` in
    ``measure_refetch`` would leave every test here green and blow up mid-measurement — after the
    copied data directory has already been mutated. Built this way, a key rename is a CI failure.

    The arithmetic is chosen so the derived figures are round: ``stop - t_pre`` is 261 ms (the
    median of the real c7-7 run) and ``stop - t_post`` is 120 ms.

    Args:
        index: The run number.
        **over: Keys to replace after construction; an unknown one is a drift and fails here.

    Returns:
        The run dict.
    """
    result = cdp.refetch_result(
        run=index,
        status="ok",
        arrived=True,
        socket_live=True,
        frames=1,
        observer_error=None,
        stop=261.0,
        t_pre=0.0,
        t_post=141.0,
        tiles=99,
    )
    unknown = set(over) - set(result)
    assert not unknown, f"a run dict has no {sorted(unknown)} key — this helper has drifted"
    result.update(over)
    return result


ARGS = SimpleNamespace(json=None)


class TestARunThatMeasuredNothingIsRefused:
    """The C4 trap: a run that stamped nothing must never become a figure."""

    def test_no_valid_runs_refuses_and_prints_no_number(self, capsys: pytest.CaptureFixture[str]):
        """The tile never entered the DOM in any run — refuse, non-zero, and say so on stderr."""
        runs = [_run(1, layout_ms=None), _run(2, layout_ms=None)]

        assert cdp._report_refetch(runs, ARGS) == 1

        captured = capsys.readouterr()
        assert "NO VALID RUNS -- refusing to report a number." in captured.err
        assert "commit->repaint over" not in captured.out, (
            "a refusal printed the figures line anyway — the whole point is that it does not"
        )

    def test_the_twin_with_one_good_run_does_report(self, capsys: pytest.CaptureFixture[str]):
        """The same set plus ONE stamped run reports, so the refusal above is not vacuous."""
        runs = [_run(1, layout_ms=None), _run(2)]

        assert cdp._report_refetch(runs, ARGS) == 0

        captured = capsys.readouterr()
        assert "commit->repaint over 1/2 valid runs" in captured.out
        assert "NO VALID RUNS" not in captured.err

    def test_a_mutation_that_did_not_succeed_is_not_a_measurement(
        self, capsys: pytest.CaptureFixture[str]
    ):
        """A refused ``add_card_to_deck`` still stamps a time if an earlier run's tile lingers.

        Filtering on ``layout_ms`` alone would score that as a measurement of a mutation that never
        happened, so the status is part of the gate.
        """
        assert cdp._report_refetch([_run(1, status="not_found")], ARGS) == 1
        assert "NO VALID RUNS" in capsys.readouterr().err

    def test_the_twin_with_the_same_timing_but_an_ok_status_reports(
        self, capsys: pytest.CaptureFixture[str]
    ):
        """Identical run, ``status='ok'`` — reported. The status is the only difference."""
        assert cdp._report_refetch([_run(1)], ARGS) == 0
        assert "commit->repaint over 1/1 valid runs" in capsys.readouterr().out


class TestTheBudgetIsTheVerdict:
    """A measurement over budget must not exit 0, however valid the runs are."""

    def test_over_budget_reports_the_figures_and_still_fails(
        self, capsys: pytest.CaptureFixture[str]
    ):
        over = cdp.REFETCH_BUDGET_MS + 1.0
        assert cdp._report_refetch([_run(1, layout_ms=over)], ARGS) == 2
        assert "commit->repaint over 1/1 valid runs" in capsys.readouterr().out

    def test_under_budget_passes(self, capsys: pytest.CaptureFixture[str]):
        under = cdp.REFETCH_BUDGET_MS - 1.0
        assert cdp._report_refetch([_run(1, layout_ms=under)], ARGS) == 0
        capsys.readouterr()


class TestAPerRunLineNeverPrintsANumberItDoesNotHave:
    """``_print_refetch_run`` is the operator's live feed — its INVALID lines carry the reason."""

    def test_a_failed_mutation_says_what_the_tool_answered(
        self, capsys: pytest.CaptureFixture[str]
    ):
        cdp._print_refetch_run(_run(1, status="not_found"))
        line = capsys.readouterr().out
        assert "INVALID" in line and "not_found" in line
        assert "commit->repaint" not in line

    def test_an_unstamped_run_says_why(self, capsys: pytest.CaptureFixture[str]):
        cdp._print_refetch_run(_run(1, layout_ms=None, observer_error="observer threw"))
        line = capsys.readouterr().out
        assert "INVALID" in line and "observer threw" in line
        assert "commit->repaint" not in line

    def test_an_unstamped_run_with_no_observer_error_still_says_why(
        self, capsys: pytest.CaptureFixture[str]
    ):
        """The fallback reason: without it the operator gets 'INVALID -- ()' and no diagnosis."""
        cdp._print_refetch_run(_run(1, layout_ms=None))
        assert "the tile never entered the DOM" in capsys.readouterr().out

    def test_a_good_run_prints_both_clocks(self, capsys: pytest.CaptureFixture[str]):
        """The positive twin for all three above — and it pins that BOTH clocks are shown."""
        cdp._print_refetch_run(_run(1))
        line = capsys.readouterr().out
        assert "commit->repaint 261 ms" in line
        assert "from tool return 120 ms" in line
        assert "INVALID" not in line


class TestTheRealDataDirectoryIsRefused:
    """The gate between a committed tool that WRITES and the operator's live 325 MB database.

    ``refetch`` is the first subcommand in this harness that mutates, and this refusal is the only
    thing that makes that acceptable. It was shipped untested at c7-7 and is tested here for the
    reason every guard in this repo is: a gate nothing exercises is a gate that is wrong when it
    finally matters. No browser, no process, no network — the check is the second thing
    :func:`~scripts.cdp_harness.cmd_refetch` does and it raises before anything is opened.

    Every refusal below is paired with a positive twin (C6 R8): a gate that refused *everything*
    would satisfy every refusal assert on its own, and the pair is the assertion.
    """

    def test_the_platform_default_is_refused_even_when_an_override_is_exported(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """The hole plain ``data_dir()`` left: an override disarms the gate against the default.

        ``src.paths.data_dir()`` returns the override when ``PLANESWALKER_DATA_DIR`` is set, so a
        gate that compared against *its* answer would wave the platform-default directory straight
        through for any operator who exports that variable for an unrelated reason — and that
        directory is the one holding the real cards.
        """
        monkeypatch.setenv("PLANESWALKER_DATA_DIR", str(tmp_path / "somewhere-else"))
        default = Path(user_data_dir("artificial-planeswalker", appauthor=False)).resolve()

        with pytest.raises(SystemExit) as refused:
            cdp.refuse_the_operators_data_dir(default)

        assert "refuses to touch your real data dir" in str(refused.value)
        assert str(default) in str(refused.value)

    def test_the_exported_override_is_refused_too(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """The other half: whatever the operator calls their data dir is their data dir."""
        mine = tmp_path / "my-real-data"
        monkeypatch.setenv("PLANESWALKER_DATA_DIR", str(mine))

        with pytest.raises(SystemExit) as refused:
            cdp.refuse_the_operators_data_dir(mine.resolve())

        assert str(mine.resolve()) in str(refused.value)

    @pytest.mark.parametrize("nested", ["copy", "copies/one"])
    def test_a_directory_inside_the_real_one_is_refused(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, nested: str
    ):
        """Plain equality let ``<real>/copy`` through — a scratch companion inside the live tree."""
        mine = tmp_path / "my-real-data"
        monkeypatch.setenv("PLANESWALKER_DATA_DIR", str(mine))

        with pytest.raises(SystemExit) as refused:
            cdp.refuse_the_operators_data_dir((mine / nested).resolve())

        assert "nested with it" in str(refused.value)

    def test_a_directory_containing_the_real_one_is_refused(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """The other nesting direction: the live dir must not become a child of the measurement."""
        mine = tmp_path / "parent" / "my-real-data"
        monkeypatch.setenv("PLANESWALKER_DATA_DIR", str(mine))

        with pytest.raises(SystemExit):
            cdp.refuse_the_operators_data_dir((tmp_path / "parent").resolve())

    def test_a_genuine_copy_is_allowed(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        """THE POSITIVE TWIN, and the one that keeps every refusal above meaningful.

        A gate that refused every path would pass all four assertions above and make the whole
        command unusable. A sibling of the real directory is exactly what the operator is told to
        pass, and it must go through.
        """
        monkeypatch.setenv("PLANESWALKER_DATA_DIR", str(tmp_path / "my-real-data"))

        cdp.refuse_the_operators_data_dir((tmp_path / "ap-copy").resolve())

    def test_the_check_creates_nothing(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        """``src.paths.data_dir()`` creates the directory it resolves; this must not.

        A refusal check that makes the thing it is checking for is a bad gate, and in a unit test
        it would create a real data directory on whatever machine the suite runs on.
        """
        ghost = tmp_path / "never-created"
        monkeypatch.setenv("PLANESWALKER_DATA_DIR", str(ghost))

        assert ghost.resolve() in cdp.operator_data_dirs(), "the override was not even considered"
        assert not ghost.exists(), "resolving the operator data dirs created one"

    def test_cmd_refetch_refuses_before_it_opens_anything(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """End to end through the entry point, with no Chrome and no companion in sight.

        Reachable because the gate runs *before* the ``cards.db`` check, the ``Companion`` and the
        ``Browser`` — which is also the property being asserted: the refusal is early enough that
        nothing has been started when it fires.
        """
        mine = tmp_path / "my-real-data"
        mine.mkdir()
        monkeypatch.setenv("PLANESWALKER_DATA_DIR", str(mine))

        with pytest.raises(SystemExit) as refused:
            cdp.cmd_refetch(SimpleNamespace(runs=5, data_dir=str(mine)))

        assert "refuses to touch your real data dir" in str(refused.value)

    def test_the_twin_gets_past_the_gate_and_fails_on_the_missing_database(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """The positive twin for the entry point: a real copy path reaches the NEXT refusal.

        Without this, ``cmd_refetch`` raising ``SystemExit`` for any input at all would satisfy the
        test above. The message proves which gate answered.
        """
        monkeypatch.setenv("PLANESWALKER_DATA_DIR", str(tmp_path / "my-real-data"))
        copy = tmp_path / "ap-copy"
        copy.mkdir()

        with pytest.raises(SystemExit) as refused:
            cdp.cmd_refetch(SimpleNamespace(runs=5, data_dir=str(copy)))

        assert "No cards.db" in str(refused.value)
        assert "refuses to touch" not in str(refused.value)

    @pytest.mark.parametrize("runs", [0, -1])
    def test_a_nonsense_run_count_is_refused_before_the_copy_is_touched(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, runs: int
    ):
        """``--runs 0`` used to sail past the loop having already mutated the copy via the primer.

        Refused first of all, so the diagnosis is the operator's argument rather than
        "NO VALID RUNS", which reads as a broken application.
        """
        monkeypatch.setenv("PLANESWALKER_DATA_DIR", str(tmp_path / "my-real-data"))

        with pytest.raises(SystemExit) as refused:
            cdp.cmd_refetch(SimpleNamespace(runs=runs, data_dir=str(tmp_path / "ap-copy")))

        assert "--runs must be at least 1" in str(refused.value)


class TestARepaintThisHarnessCannotAttributeToAPushIsNotAMeasurement:
    """SC-2 is about the PUSH path, so a run must prove the push is what moved the glass (P2).

    The failure this closes is quiet and plausible: if the socket had dropped, the SPA re-drives
    its boot on reconnect, the tile appears anyway, and every figure printed would be a perfectly
    reasonable number for the wrong path.
    """

    def test_a_run_whose_socket_was_down_is_refused(self, capsys: pytest.CaptureFixture[str]):
        assert cdp._report_refetch([_run(1, socket_live=False)], ARGS) == 1
        assert "NO VALID RUNS" in capsys.readouterr().err

    def test_a_run_that_received_no_deck_changed_frame_is_refused(
        self, capsys: pytest.CaptureFixture[str]
    ):
        assert cdp._report_refetch([_run(1, frames=0)], ARGS) == 1
        assert "NO VALID RUNS" in capsys.readouterr().err

    def test_the_per_run_line_names_the_reconnect_hazard(self, capsys: pytest.CaptureFixture[str]):
        """The operator sees WHY, because "INVALID" without a reason is not a diagnosis."""
        cdp._print_refetch_run(_run(1, frames=0))
        assert "reconnect re-drive would look the same" in capsys.readouterr().out

    def test_a_stamp_that_precedes_t0_is_refused(self, capsys: pytest.CaptureFixture[str]):
        """A negative interval is a clock nobody should trust, not a very fast repaint."""
        assert cdp._report_refetch([_run(1, layout_ms=-3.0)], ARGS) == 1
        assert "NO VALID RUNS" in capsys.readouterr().err

    def test_the_twin_a_pushed_run_with_a_live_socket_reports(
        self, capsys: pytest.CaptureFixture[str]
    ):
        """The positive twin for all four: the same run, correctly attributed, is a measurement."""
        assert cdp._report_refetch([_run(1)], ARGS) == 0
        out = capsys.readouterr().out
        assert "commit->repaint over 1/1 valid runs" in out
