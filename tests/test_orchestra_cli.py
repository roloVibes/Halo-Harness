"""tests.test_orchestra_cli -- Halo 3.0.3.0 round R1: `halo orchestra`
(orchestra_cli.py), run in-process: `new` from flags, from --goal and from
prompts; the no-terminal error; validation lines; `runs`, `status`,
`claims`, `log [--since]`; an unknown run; and the `halo orchestra` route in
cli.py. Every repo is a temp folder passed with --repo.
"""
from __future__ import annotations

import builtins
import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

ensure_scoped_state_dir_once()
test, TESTS = new_registry()
REPO_ROOT = Path(__file__).resolve().parent.parent


def _run(argv):
    from halo_harness.orchestra_cli import cmd_orchestra
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = cmd_orchestra(argv)
    return rc, out.getvalue(), err.getvalue()


def _repo() -> str:
    return str(Path(tempfile.mkdtemp(prefix="orch-cli-")))


FLAGS = ["--what", "five functions", "--done-when", "tests pass", "--stop-when", "two returns"]


@test
def test_new_from_flags_writes_the_files(ctx: Ctx):
    from halo_harness.orchestra import goal as G
    repo = _repo()
    rc, out, err = _run(["new", *FLAGS, "--workers", "3", "--test", "python -m unittest", "--file", "basket.py",
                         "--file", "README.md", "--lineup", "standard", "--repo", repo])
    ctx.check(f"rc 0, got {rc} {err!r}", rc == 0)
    run = G.latest_run(repo)
    ctx.check("a run folder exists", run is not None and (run / "workflow.json").is_file())
    g = G.load_goal(run / "goal.json")
    ctx.check("the flags landed in goal.json", (g.what, g.done_when, g.stop_when, g.workers, g.test, g.files, g.lineup)
              == ("five functions", "tests pass", "two returns", 3, "python -m unittest", ["basket.py", "README.md"],
                  "standard"))
    ctx.check(f"output names the run and the next step, got {out!r}", run.name in out and "halo orchestra status" in out)


@test
def test_new_from_the_template_and_from_prompts(ctx: Ctx):
    from halo_harness.orchestra import goal as G
    repo = _repo()
    tpl = REPO_ROOT / "halo_harness" / "templates" / "orchestra" / "goal.example.json"
    ctx.check("the example goal validates", G.validate_goal(json.loads(tpl.read_text(encoding="utf-8"))) == [])
    rc, _, _ = _run(["new", "--goal", str(tpl), "--workers", "2", "--repo", repo])
    g = G.load_goal(G.latest_run(repo) / "goal.json")
    ctx.check("--goal plus an override", rc == 0 and g.workers == 2 and g.files == ["basket.py"]
              and g.test == "python -m unittest")
    repo2 = _repo()
    answers = iter(["make it", "green", "red"])
    saved_input, saved_isatty = builtins.input, sys.stdin.isatty
    try:
        builtins.input = lambda prompt="": next(answers)
        sys.stdin.isatty = lambda: True
        rc, _, _ = _run(["new", "--repo", repo2])
    finally:
        builtins.input, sys.stdin.isatty = saved_input, saved_isatty
    g = G.load_goal(G.latest_run(repo2) / "goal.json")
    ctx.check("the three prompts fill the three fields", rc == 0 and (g.what, g.done_when, g.stop_when)
              == ("make it", "green", "red"))


@test
def test_new_without_a_terminal_and_with_bad_values(ctx: Ctx):
    repo = _repo()
    saved = sys.stdin.isatty
    try:
        sys.stdin.isatty = lambda: False
        rc, _, err = _run(["new", "--what", "x", "--repo", repo])
    finally:
        sys.stdin.isatty = saved
    ctx.check(f"rc 2 naming the missing flags, got {err!r}", rc == 2 and "--done-when" in err and "--stop-when" in err)
    rc, _, err = _run(["new", *FLAGS, "--workers", "99", "--file", "/etc/passwd", "--repo", repo])
    ctx.check(f"validation lines, got {err!r}", rc == 2 and '"workers" must be a whole number from 1 to 50' in err
              and "files[0]" in err)
    from halo_harness.orchestra import goal as G
    ctx.check("nothing was created", G.list_runs(repo) == [])


@test
def test_status_claims_log_and_runs_print(ctx: Ctx):
    from halo_harness.orchestra import events as run_events
    from halo_harness.orchestra import goal as G
    from halo_harness.orchestra.claims import ClaimLog
    repo = _repo()
    rc, out, _ = _run(["runs", "--repo", repo])
    ctx.check("runs with none says how to start", rc == 0 and "halo orchestra new" in out)
    rc, _, err = _run(["status", "--repo", repo])
    ctx.check("status with no runs is rc 1", rc == 1 and "no runs" in err)
    _run(["new", *FLAGS, "--file", "basket.py", "--repo", repo])
    run = G.latest_run(repo)
    rc, out, _ = _run(["claims", "--repo", repo])
    ctx.check("claims: none", rc == 0 and "no live claims" in out)
    ClaimLog(run).claim("s1/w1", "basket.py#total")
    run_events.log(run, "note", "hello from lane 2", lane=2)
    rc, out, _ = _run(["claims", run.name, "--repo", repo])
    ctx.check(f"claims lists key, holder, state, got {out!r}", rc == 0 and "basket.py#total" in out and "s1/w1" in out
              and "claimed" in out and "until" in out)
    rc, out, _ = _run(["status", "--repo", repo])
    ctx.check(f"status shows the three fields, steps and claims, got {out!r}", rc == 0 and "WHAT YOU WANT  five functions"
              in out and "DONE WHEN      tests pass" in out and "12 pending" in out and "live claims: 1" in out
              and "hello from lane 2" in out)
    rc, out, _ = _run(["log", "--repo", repo])
    lines = out.strip().splitlines()
    ctx.check(f"log prints both lines with times, got {lines}", rc == 0 and len(lines) == 2 and lines[0].startswith("+")
              and "lane 2" in lines[1])
    rc, out, _ = _run(["log", "--since", "1", "--repo", repo])
    ctx.check("--since skips seen entries", rc == 0 and len(out.strip().splitlines()) == 1 and "hello" in out)
    rc, out, _ = _run(["runs", "--repo", repo])
    ctx.check("runs lists the run", rc == 0 and run.name in out and "five functions" in out)
    rc, _, err = _run(["status", "nope", "--repo", repo])
    ctx.check("an unknown run names the runs", rc == 1 and run.name in err)


@test
def test_halo_orchestra_is_routed_from_the_main_cli(ctx: Ctx):
    from halo_harness import cli
    src = Path(cli.__file__).read_text(encoding="utf-8")
    ctx.check("cli.py routes `orchestra`", 'argv[0] == "orchestra"' in src and "cmd_orchestra" in src)
    rc, out, _ = _run([])
    ctx.check("bare `halo orchestra` prints help", rc == 0 and "new" in out and "status" in out)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
