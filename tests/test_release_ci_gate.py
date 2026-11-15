"""tests.test_release_ci_gate -- scripts/release_gate.py, the gate of scripts/release.py (Halo 3.1.0.0 R1; 3.6.0.0
R13: the candidate branch), over a fake `gh` (tests/helpers/fake_gh.py) and a fake clock (no process, no network, no
real sleep). The main()-level flow (rc branch, fast-forward, tag) is in tests/test_release_script.py.

1. The push run on the candidate branch for the exact sha is found (after it appears) and polled until it
   completes; every required job green: the accepted line comes back.
2. The required jobs are one list: Linux x4, Windows x4, studio-ui; macOS x4 and realcheck behind their flags.
3. A red, skipped or missing required job stops the gate and names every failing job; a red macOS shard does not
   while macOS is not required, and does once it is.
4. A run that never finishes, or never appears, stops the gate; a run for another sha is refused; no `gh` is one line.
5. "driver retried once" lines in the run's log come back as warnings naming the job and the test.
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
BRANCH = "rc/9.9.9"


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
    got = gate.candidate_gate(SHA, branch=BRANCH, repo_dir=REPO_DIR, run_fn=gh, sleep_fn=clock.sleep,
                              clock_fn=clock.now, log=lines.append, **kw)
    return got, lines, clock


def _refused(ctx, gh, want: "list[str]", why: str, **kw) -> str:
    try:
        _gate(gh, **kw)
        ctx.check(f"{why}: the gate raises", False)
        return ""
    except gate.GateError as e:
        ctx.check(f"{why}: it names {want}, got {e}", all(w in str(e) for w in want))
        return str(e)


@test
def test_the_branch_run_is_found_polled_and_accepted(ctx: Ctx):
    gh = FakeGh(polls=4, appear_after=2)
    (accepted, warnings), lines, clock = _gate(gh)
    ctx.check(f"accepted, naming the run, the branch and the job count, got {accepted}",
              accepted == [f"suites run 303 on {BRANCH}: all 9 required jobs concluded success for {SHA[:12]}"])
    ctx.check(f"no retries, no warnings, got {warnings}", warnings == [])
    ctx.check(f"two looks for the run (10 s), three polls (30 s), got {clock.sleeps}",
              clock.sleeps == [10.0, 10.0, 30.0, 30.0, 30.0])
    ctx.check(f"each wait is logged, got {lines}", sum("waiting for the suites run 303" in ln for ln in lines) == 3)
    asked = [c for c in gh.gh_calls() if c[1:3] == ["run", "list"]]
    ctx.check(f"it asks for the push run on the branch for the exact sha, got {asked[:1]}",
              asked and "--branch" in asked[0] and BRANCH in asked[0] and SHA in asked[0] and "push" in asked[0])
    ctx.check("nothing is dispatched any more", not [c for c in gh.gh_calls() if c[1:3] == ["workflow", "run"]])


@test
def test_the_required_jobs_are_one_list_with_macos_and_realcheck_behind_flags(ctx: Ctx):
    base = gate.required_jobs(macos=False, realcheck=False)
    ctx.check(f"Linux x4, Windows x4, studio-ui, got {base}", len(base) == 9
              and sum(n.startswith("suites (linux, py3.12, shard ") for n in base) == 4
              and sum(n.startswith("suites (windows, py3.12, shard ") for n in base) == 4
              and "studio-ui (build + drift gate)" in base)
    both = gate.required_jobs(macos=True, realcheck=True)
    ctx.check(f"the flags add macOS x4 and realcheck, got {len(both)}", len(both) == 14
              and sum(n.startswith("suites (macos, ") for n in both) == 4 and "realcheck" in both)
    ctx.check("the defaults are the module's flags (off until the coordinator flips them)",
              gate.required_jobs() == gate.required_jobs(macos=gate.REQUIRE_MACOS, realcheck=gate.REQUIRE_REALCHECK)
              and gate.REQUIRE_MACOS is False and gate.REQUIRE_REALCHECK is False)
    ctx.check("the dry run's line names them", "suites (windows, py3.12, shard 3/4)" in gate.describe(BRANCH)
              and "90 min" in gate.describe(BRANCH) and "driver retried once" in gate.describe(BRANCH))


@test
def test_a_red_skipped_or_missing_required_job_stops_the_gate_naming_each(ctx: Ctx):
    win2, linux0 = "suites (windows, py3.12, shard 2/4)", "suites (linux, py3.12, shard 0/4)"
    _refused(ctx, FakeGh(conclusions={win2: "failure", linux0: "cancelled"}),
             [f"{linux0}: cancelled", f"{win2}: failure", "failing jobs"], "two red jobs")
    _refused(ctx, FakeGh(conclusions={"studio-ui (build + drift gate)": "skipped"}),
             ["studio-ui (build + drift gate): skipped"], "a skipped required job")
    _refused(ctx, FakeGh(conclusions={win2: None}), [f"{win2}: missing"], "a required job not in the run")
    mac = "suites (macos, py3.12, shard 1/4)"
    (accepted, _w), _l, _c = _gate(FakeGh(conclusions={mac: "failure", "realcheck": "failure"}))
    ctx.check("a red macOS shard and realcheck do not stop it while not required", bool(accepted))
    _refused(ctx, FakeGh(conclusions={mac: "failure"}), [f"{mac}: failure"], "macOS once required", macos=True)
    _refused(ctx, FakeGh(conclusions={"realcheck": None}), ["realcheck: missing"], "realcheck once required",
             realcheck=True)


@test
def test_a_run_that_never_finishes_never_appears_or_is_for_another_sha_stops_it(ctx: Ctx):
    _refused(ctx, FakeGh(polls=10_000), ["303", "90 min"], "never finishes")
    _refused(ctx, FakeGh(appear_after=None), ["no suites run (push) on rc/9.9.9", "appeared"], "never appears")
    _refused(ctx, FakeGh(head_sha="f" * 40), ["303 is for ffffffffffff"], "another sha")

    def no_gh(cmd, **kw):
        raise FileNotFoundError(cmd[0])
    _refused(ctx, no_gh, ["`gh` CLI"], "no gh")


@test
def test_driver_retries_come_back_as_warnings(ctx: Ctx):
    gh = FakeGh(retried=[("suites (windows, py3.12, shard 1/4)", "test_studio_local"),
                         ("suites (linux, py3.12, shard 3/4)", "test_studio_map")])
    (accepted, warnings), _l, _c = _gate(gh)
    ctx.check(f"still accepted (a retry warns, it does not stop), got {accepted}", bool(accepted))
    ctx.check(f"one warning per retry, naming the job and the test, got {warnings}",
              len(warnings) == 2 and warnings[0].startswith("suites (windows, py3.12, shard 1/4): test_studio_local -- "
                                                           "driver retried once: Runtime.evaluate timed out")
              and "test_studio_map" in warnings[1])
    ctx.check("the log is read once", sum(1 for c in gh.gh_calls() if "--log" in c) == 1)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
