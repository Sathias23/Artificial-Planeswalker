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


# =============================================================================================
# 17-3: the push validity predicate, its reporter, and the drain arm's own gates — pinned the
# way their refetch twins above are, and for the same reason: these seams decide before anything
# is opened or after everything is measured, and a seam nothing exercises is wrong when it
# finally matters.
# =============================================================================================


def _push_run(index: int = 1, *, outstanding: int | None = None, **over: Any) -> dict[str, Any]:
    """One valid ``measure_push`` result, built by **the shipped builder** and then overridden.

    ``cdp.push_result`` rather than a dict literal — ``_run``'s rule (c7-7 review, P9): a
    hand-rolled fixture is pinned only to itself, and renaming a key in ``measure_push`` would
    leave every test here green and blow up mid-measurement. The arithmetic is chosen so the
    derived figures are round: ``stop - t_pre`` is 39 ms (the median of the real 17-3 warm run)
    and ``stop - t_post`` is 18 ms.

    Args:
        index: The run number.
        outstanding: The drain arm's positive-control count, or ``None`` for "not counted" —
            passed through the builder so the None-means-absent rule is the shipped one.
        **over: Keys to replace after construction; an unknown one is a drift and fails here.
    """
    result = cdp.push_result(
        run=index,
        status_code=200,
        response_text=None,
        clients=1,
        surfaces=dict.fromkeys(cdp.PUSH_SURFACES, 60.0),
        missing=[],
        observer_error=None,
        stop=60.0,
        t_pre=21.0,
        t_post=42.0,
        images_requested=6,
        images_from_network=0,
        images_painted=6,
        rows=6,
        images_outstanding_at_push=outstanding,
    )
    unknown = set(over) - set(result)
    assert not unknown, f"a push run dict has no {sorted(unknown)} key — this helper has drifted"
    result.update(over)
    return result


PUSH_ARGS = SimpleNamespace(json=None, arm="warm")
DRAIN_ARGS = SimpleNamespace(json=None, arm="drain")


class TestAPushRunThatMeasuredNothingIsRefused:
    """The refusals `_push_run_is_valid` centralized, pinned — printer and reporter both."""

    def test_a_rejected_post_is_refused_and_the_line_says_what_came_back(
        self, capsys: pytest.CaptureFixture[str]
    ):
        run = _push_run(1, status_code=400, response_text="payload_rejected")

        assert cdp._report_push([run], PUSH_ARGS) == 1
        assert "NO VALID RUNS" in capsys.readouterr().err

        cdp._print_run(run)
        line = capsys.readouterr().out
        assert "INVALID" in line and "400" in line and "payload_rejected" in line
        assert "layout" not in line, "a refused run printed a figure anyway"

    def test_missing_surfaces_are_refused_with_the_reason(self, capsys: pytest.CaptureFixture[str]):
        run = _push_run(1, missing=["rows"], observer_error="observer threw")

        assert cdp._report_push([run], PUSH_ARGS) == 1
        assert "NO VALID RUNS" in capsys.readouterr().err

        cdp._print_run(run)
        line = capsys.readouterr().out
        assert "INVALID" in line and "observer threw" in line

    def test_a_receipt_saying_nobody_listened_is_refused(self, capsys: pytest.CaptureFixture[str]):
        """`clients: 0` is a broadcast to nobody — nothing rendered BECAUSE of this push."""
        run = _push_run(1, clients=0)

        assert cdp._report_push([run], PUSH_ARGS) == 1
        assert "NO VALID RUNS" in capsys.readouterr().err

        cdp._print_run(run)
        assert "clients=0" in capsys.readouterr().out

    def test_the_twin_a_valid_warm_run_reports_both_clocks(
        self, capsys: pytest.CaptureFixture[str]
    ):
        """The positive twin for all three — and it pins that BOTH clocks are shown."""
        assert cdp._report_push([_push_run(1)], PUSH_ARGS) == 0
        out = capsys.readouterr().out
        assert "warm arm, layout over 1/1 valid runs" in out

        cdp._print_run(_push_run(1))
        line = capsys.readouterr().out
        assert "layout 39 ms" in line
        assert "from POST return 18 ms" in line
        assert "INVALID" not in line


class TestTheDrainPositiveControl:
    """A push measured after the queue drained is a warm measurement wearing a drain label."""

    def test_zero_outstanding_requests_fail_the_run_naming_the_control(
        self, capsys: pytest.CaptureFixture[str]
    ):
        run = _push_run(1, outstanding=0)

        assert cdp._push_run_is_valid(run) is not None
        assert "positive control" in str(cdp._push_run_is_valid(run))

        assert cdp._report_push([run], DRAIN_ARGS) == 1
        assert "NO VALID RUNS" in capsys.readouterr().err

        cdp._print_run(run)
        line = capsys.readouterr().out
        assert "INVALID" in line and "positive control" in line
        assert "layout" not in line

    def test_the_twin_a_genuinely_draining_run_is_valid_and_says_how_deep(
        self, capsys: pytest.CaptureFixture[str]
    ):
        run = _push_run(1, outstanding=106)

        assert cdp._push_run_is_valid(run) is None
        assert cdp._report_push([run], DRAIN_ARGS) == 0
        assert "drain arm, layout over 1/1 valid runs" in capsys.readouterr().out

        cdp._print_run(run)
        assert "106 image request(s) outstanding at the push" in capsys.readouterr().out

    def test_a_warm_run_without_the_key_is_not_failed_by_the_control(self):
        """The clause fires only when the drain arm counted — an absent key is not a zero."""
        assert cdp._push_run_is_valid(_push_run(1)) is None
        assert "images_outstanding_at_push" not in _push_run(1), (
            "the builder included the key for a run that never counted — the None-means-absent "
            "rule has drifted, and every warm run would now be judged by the drain's control"
        )

    def test_a_mixed_set_counts_only_the_draining_run(self, capsys: pytest.CaptureFixture[str]):
        runs = [_push_run(1, outstanding=0), _push_run(2, outstanding=106)]

        assert cdp._report_push(runs, DRAIN_ARGS) == 0
        assert "drain arm, layout over 1/2 valid runs" in capsys.readouterr().out


class TestPushDrainRefusesTheOperatorsDataDir:
    """The drain arm WRITES — it empties `image_cache` — so it inherits `refetch`'s gate.

    Mirrors ``TestTheRealDataDirectoryIsRefused``'s entry-point pair: the refusal must fire
    before anything is opened, the positive twin must reach the NEXT gate, and an arm that only
    reads must not be gated at all.
    """

    def test_drain_refuses_the_real_data_dir_before_anything_is_opened(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        mine = tmp_path / "my-real-data"
        mine.mkdir()
        monkeypatch.setenv("PLANESWALKER_DATA_DIR", str(mine))

        with pytest.raises(SystemExit) as refused:
            cdp.cmd_push(SimpleNamespace(runs=None, deck_id=None, data_dir=str(mine), arm="drain"))

        assert "refuses to touch your real data dir" in str(refused.value)

    def test_the_twin_gets_past_the_gate_and_fails_on_the_missing_database(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """A real copy path reaches the next refusal, and the message proves which gate answered."""
        monkeypatch.setenv("PLANESWALKER_DATA_DIR", str(tmp_path / "my-real-data"))
        copy = tmp_path / "ap-copy"
        copy.mkdir()

        with pytest.raises(SystemExit) as refused:
            cdp.cmd_push(SimpleNamespace(runs=None, deck_id=None, data_dir=str(copy), arm="drain"))

        assert "No cards.db" in str(refused.value)
        assert "refuses to touch" not in str(refused.value)

    def test_an_arm_that_only_reads_is_not_gated(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """`warm` on the same directory sails past the gate — proven by reaching the Companion.

        The stub raises before a process could start, so this asserts exactly one thing: the
        warm arm got PAST where the drain arm refused, with nothing real opened either way.
        """
        mine = tmp_path / "my-real-data"
        mine.mkdir()
        monkeypatch.setenv("PLANESWALKER_DATA_DIR", str(mine))

        class _CompanionStub:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                raise RuntimeError("companion stub reached")

        monkeypatch.setattr(cdp, "Companion", _CompanionStub)

        with pytest.raises(RuntimeError, match="companion stub reached"):
            cdp.cmd_push(
                SimpleNamespace(runs=None, deck_id=None, data_dir=str(mine), arm="warm", port=None)
            )

    def test_a_nonsense_run_count_is_refused_first_of_all(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """`cmd_refetch`'s guard, inherited: the diagnosis is the operator's argument."""
        monkeypatch.setenv("PLANESWALKER_DATA_DIR", str(tmp_path / "my-real-data"))

        with pytest.raises(SystemExit) as refused:
            cdp.cmd_push(
                SimpleNamespace(runs=0, deck_id=None, data_dir=str(tmp_path / "x"), arm="warm")
            )

        assert "--runs must be at least 1" in str(refused.value)

    def test_a_deck_id_on_a_non_drain_arm_is_refused_not_ignored(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """A silently ignored argument is an operator who believes they measured the wrong deck."""
        monkeypatch.setenv("PLANESWALKER_DATA_DIR", str(tmp_path / "my-real-data"))

        with pytest.raises(SystemExit) as refused:
            cdp.cmd_push(
                SimpleNamespace(
                    runs=None, deck_id="813d0434", data_dir=str(tmp_path / "x"), arm="warm"
                )
            )

        assert "--deck-id applies only to --arm drain" in str(refused.value)


class TestEmptyingTheImageCache:
    """`_empty_image_cache` is the drain arm's cold-cache premise; a lie here mislabels the arm."""

    def test_a_populated_cache_is_emptied(self, tmp_path: Path):
        cache = tmp_path / "image_cache"
        (cache / "ab" / "ab01").mkdir(parents=True)
        (cache / "ab" / "ab01" / "normal_0.jpg").write_bytes(b"\xff\xd8pretend")

        cdp._empty_image_cache(tmp_path)

        assert not cache.exists() or not any(cache.rglob("*"))

    def test_an_absent_cache_is_a_no_op(self, tmp_path: Path):
        cdp._empty_image_cache(tmp_path)  # nothing to raise, nothing created

        assert not (tmp_path / "image_cache").exists()

    def test_files_that_survive_are_a_refusal_naming_the_stakes(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """An rmtree that removes nothing must end the run, not let a 'cold' arm run half-warm."""
        cache = tmp_path / "image_cache"
        cache.mkdir()
        (cache / "held.jpg").write_bytes(b"held open")
        monkeypatch.setattr(cdp.shutil, "rmtree", lambda *args, **kwargs: None)
        monkeypatch.setattr(cdp.time, "sleep", lambda seconds: None)

        with pytest.raises(SystemExit) as refused:
            cdp._empty_image_cache(tmp_path)

        assert "mislabelled measurement" in str(refused.value)
        assert "1 file(s) survived" in str(refused.value)
