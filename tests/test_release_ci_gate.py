"""tests.test_release_ci_gate -- Halo 3.1.0.0 round R1: scripts/release_gate.py,
step 0 of scripts/release.py, over a fake `gh` (tests/helpers/fake_gh.py) and
a fake clock (no process, no network, no real sleep). The main()-level
behaviour (dry run, refusals, --skip-windows) is in tests/test_release_script.py.

1. The dispatched Windows run is polled until it completes; the accepted run
   ids come back.
2. A run that never finishes stops the gate after the wait (90 min default).
3. A dispatch that never shows up in `gh run list` stops it too.
4. The Linux run must be green in its run AND its Linux job; the Windows run
   in its run AND its Windows job.
5. A run without the sha in its title (run-name not applied) is still found
   by its creation time; no `gh` on PATH is a one-line reason.
Run: python -m tests.test_release_ci_gate
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.fake_gh import FakeGh
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

REPO_DIR = Path(__file__).resolve().parent.parent
test, TESTS = new_registry()

_spec = importlib.util.spec_from_file_location("halo_release_gate_test", REPO_DIR / "scripts" / "release_gate.py")
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)
SHA = "a1b2c3d4" * 5


class _Clock:
    def __init__(self):
        self.t = 0.0
        self.sleeps: list = []

    def now(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.sleeps.append(s)
        self.t += s


def _gate(gh, clock=None, **kw):
    clock = clock or _Clock()
    lines: list = []
    got = gate.ci_gate(SHA, repo_dir=REPO_DIR, run_fn=gh, sleep_fn=clock.sleep, clock_fn=clock.now,
                       wall_fn=lambda: 1_900_000_000.0, log=lines.append, **kw)
    return got, lines, clock


@test
def test_the_windows_run_is_polled_until_it_completes(ctx: Ctx):
    gh = FakeGh(windows_polls=4)
    got, lines, clock = _gate(gh)
    ctx.check(f"both accepted, got {got}", got[0].startswith("Linux run 101 concluded success")
              and got[1].startswith("Windows run 202 concluded success"))
    ctx.check(f"three polls waited 30 s each, got {clock.sleeps}", clock.sleeps == [30.0, 30.0, 30.0])
    ctx.check(f"each wait is logged, got {lines}", sum("waiting for the Windows run 202" in ln for ln in lines) == 3)
    ctx.check("the dispatch names the exact sha", ["gh", "workflow", "run", "suites.yml", "-f", f"sha={SHA}"] in gh.gh_calls())


@test
def test_a_run_that_never_finishes_stops_after_the_wait(ctx: Ctx):
    gh = FakeGh(windows_polls=10_000)
    try:
        _gate(gh)
        ctx.check("the gate raises", False)
    except gate.GateError as e:
        ctx.check(f"it names the run and the 90 minutes, got {e}", "202" in str(e) and "90 min" in str(e))


@test
def test_a_dispatch_that_never_appears_stops_the_gate(ctx: Ctx):
    gh = FakeGh(created="2001-01-01T00:00:00Z")  # every dispatch run is older than this release's dispatch
    try:
        _gate(gh)
        ctx.check("the gate raises", False)
    except gate.GateError as e:
        ctx.check(f"it says so, got {e}", "never appeared" in str(e))


@test
def test_job_conclusions_count_not_only_the_run(ctx: Ctx):
    class _LinuxJobRed(FakeGh):
        def _view(self, run_id):
            v = super()._view(run_id)
            if run_id == "101":
                v["jobs"][0]["conclusion"] = "cancelled"
            return v
    try:
        _gate(_LinuxJobRed())
        ctx.check("a cancelled Linux job refuses", False)
    except gate.GateError as e:
        ctx.check(f"it names the Linux job, got {e}", "Linux job: cancelled" in str(e))
    try:
        _gate(FakeGh(windows="cancelled"))
        ctx.check("a cancelled Windows run refuses", False)
    except gate.GateError as e:
        ctx.check(f"it names the conclusion, got {e}", "concluded cancelled" in str(e))


@test
def test_an_untitled_dispatch_is_found_by_time_and_gh_missing_is_one_line(ctx: Ctx):
    got, _lines, _clock = _gate(FakeGh(title_has_sha=False))
    ctx.check(f"found without the sha in its title, got {got}", got[1].startswith("Windows run 202"))

    def no_gh(cmd, **kw):
        raise FileNotFoundError(cmd[0])
    try:
        _gate(no_gh)
        ctx.check("no gh refuses", False)
    except gate.GateError as e:
        ctx.check(f"it names gh, got {e}", "`gh` CLI" in str(e))
    ctx.check("describe() names the dispatch and the wait", "gh workflow run suites.yml" in gate.describe(SHA, False)
              and "90 min" in gate.describe(SHA, False) and "--skip-windows" in gate.describe(SHA, True))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
