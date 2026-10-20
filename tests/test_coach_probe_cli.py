"""tests.test_coach_probe_cli -- Halo 3.1.6.0 R2: the coach probes' surfaces
(coach_cli.py `--probe`, `/coach --probe`, the report's and the Fleet digest's
probe line), over a reference run made with the fake lead, workers and judge
(tests/helpers/coach_probe_rig.py):

1. `halo coach <run> --probe` prints the cost line first and asks y/N: no answer
   or n runs nothing; `--json` without `--yes` prints the estimate only;
2. y (or `--yes`) runs it: the step lines, the contrast table, the pick and the
   Apply line; `--k 2` runs two pairs; a mission or a team run is one line, exit 1;
3. the run report's coach line and the Fleet digest's coach row end with
   "probe: N runs, $X, picked: ...";
4. `/coach --probe` shows the cost line and runs nothing; `--probe --yes` starts
   it on a thread and answers at once; the probe ends and its card leads `/coach`;
5. a tracked file the overlay writes into a worktree is never committed.
No model is ever called. Run: python -m tests.test_coach_probe_cli
"""
from __future__ import annotations

import io
import json
import sys
import time
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

ensure_scoped_state_dir_once()
test, TESTS = new_registry()


def _cli(argv, stdin: str = ""):
    from halo_harness.coach_cli import cmd_coach
    o, e = io.StringIO(), io.StringIO()
    saved, sys.stdin = sys.stdin, io.StringIO(stdin)
    try:
        with redirect_stdout(o), redirect_stderr(e):
            rc = cmd_coach(argv)
    finally:
        sys.stdin = saved
    return rc, o.getvalue(), e.getvalue()


@test
def test_the_cost_line_comes_first_and_y_n_guards_the_probe(ctx: Ctx):
    from tests.helpers.coach_probe_rig import Probe
    with Probe() as p:
        for answer in ("", "n\n"):
            rc, out, _ = _cli([str(p.run_dir), "--probe"], answer)
            ctx.check(f"answer {answer!r}: the cost line, then nothing run, got {rc} {out!r}", rc == 0
                      and out.splitlines()[0].startswith("probe: 2 runs, up to $0.0150 (each stops at $0.0075")
                      and "nothing run" in out and not (p.run_dir / "probe.json").exists() and p.log == [])
        rc, out, _ = _cli([str(p.run_dir), "--probe", "--json"])
        got = json.loads(out)
        ctx.check(f"--json without --yes: the estimate only, got {got}", rc == 0 and got["probe"] is None
                  and got["estimate"]["runs"] == 2 and got["estimate"]["cap_usd"] == 0.0075)
        rc, out, _ = _cli(["--help"])
        ctx.check("--help names --probe and --k", rc == 0 and "--probe" in out and "--k N" in out)


@test
def test_yes_runs_it_and_prints_the_contrast_and_the_pick(ctx: Ctx):
    from tests.helpers.coach_probe_rig import Probe
    from tests.helpers.coach_seed import mission_folder
    with Probe() as p:
        rc, out, err = _cli([str(p.run_dir), "--probe"], "y\n")
        lines = out.splitlines()
        ctx.check(f"y runs it, got {rc} {err!r}", rc == 0 and lines[0].startswith("probe: 2 runs, up to $0.0150"))
        ctx.check("the step lines", any("the run's lead drafts 1 pair(s)" in l for l in lines)
                  and any("the judge compares the anonymized deliverables" in l for l in lines))
        ctx.check(f"the contrast table, got {out[-900:]!r}", any(l.strip().startswith("the run itself") for l in lines)
                  and any(l.strip().startswith("* invariant") for l in lines) and "tests" in out and "rank" in out)
        ctx.check("the Apply line and the probe line", f"apply: halo coach {p.run_dir.name} --apply probe-" in out
                  and lines[-1].strip() == "probe: 2 runs, $0.0080, picked: invariant")
        rc, out, _ = _cli([str(p.run_dir), "--probe", "--yes", "--k", "2"])
        data = json.loads((p.run_dir / "probe.json").read_text(encoding="utf-8"))
        ctx.check(f"--yes --k 2: two pairs, four runs, got {rc} {[c['id'] for c in data['candidates']]}", rc == 0
                  and out.splitlines()[0].startswith("probe: 4 runs") and [c["pair"] for c in data["candidates"]] == [1, 1, 2, 2]
                  and len(data["outcomes"]) == 4 and all(o["status"] == "finished" for o in data["outcomes"].values()))
        rc, _, err = _cli([str(mission_folder(p.state)), "--probe", "--yes"])
        ctx.check(f"a mission is one line, exit 1, got {rc} {err!r}", rc == 1 and "takes an Orchestra run" in err)


@test
def test_the_report_and_the_digest_carry_the_probe_line(ctx: Ctx):
    from halo_harness.fleet import digest
    from halo_harness.orchestra import coach_probe as CP
    from halo_harness.orchestra.report import format_report, load_report
    from tests.helpers.coach_probe_rig import Probe
    with Probe() as p:
        ctx.check("no probe yet: no probe line", "probe:" not in format_report(load_report(p.run_dir), p.run_dir))
        CP.probe(p.run_dir)
        last = format_report(load_report(p.run_dir), p.run_dir).splitlines()[-1]
        ctx.check(f"the report's coach line ends with the probe, got {last!r}", last.startswith("  coach: ")
                  and last.endswith("; probe: 2 runs, $0.0080, picked: invariant"))
        d = digest.compute(p.state, 0.0, local_id="me", local_name="here")
        row = next(b for b in d["harnesses"] if b["local"])["coach"][-1]
        ctx.check(f"the digest's coach row keeps it, got {row.get('probe')!r}", row.get("probe") == "probe: 2 runs, $0.0080, picked: invariant"
                  and "picked: invariant" in digest.text(d))


@test
def test_slash_coach_probe_shows_the_cost_then_runs_on_a_thread(ctx: Ctx):
    from halo_harness.commands.builtins import _cmd_coach
    from halo_harness.orchestra import coach_probe as CP
    from tests.helpers.coach_probe_rig import Probe
    with Probe() as p:
        facade = SimpleNamespace(session=SimpleNamespace(cwd=p.repo), cwd=p.repo)
        out = _cmd_coach(f"{p.run_dir.name} --probe", facade)
        ctx.check(f"/coach --probe: the cost line, nothing run, got {out!r}", out.startswith("probe: 2 runs, up to $0.0150")
                  and "add --yes to run it" in out and not (p.run_dir / "probe.json").exists())
        out = _cmd_coach(f"{p.run_dir.name} --probe --yes", facade)
        ctx.check(f"--yes starts it and answers at once, got {out!r}", f"probe started on run {p.run_dir.name}" in out)
        end = time.monotonic() + 90
        while CP.live(p.run_dir) and time.monotonic() < end:
            time.sleep(0.1)
        data = CP.read(p.run_dir) or {}
        ctx.check(f"the probe ended, got {data.get('state')} {data.get('error')}", data.get("state") == "done" and not CP.live(p.run_dir))
        out = _cmd_coach(p.run_dir.name, facade)
        ctx.check(f"its card leads /coach, got {out[:200]!r}", out.splitlines()[2].startswith("[high] probe")
                  and "the judge: Deliverable" in out)


@test
def test_a_tracked_overlay_file_is_never_committed(ctx: Ctx):
    from halo_harness.orchestra import gitops
    from halo_harness.orchestra.probe_overlay import IGNORE, write_scope
    from tests.helpers import orchestra_fixtures as F
    from tests.helpers.orchestra_studio_rig import cleanup
    repo = F.make_repo("coach-probe-scope-")
    try:
        (repo / ".halo" / "agents").mkdir(parents=True)
        (repo / ".halo" / "agents" / "coder.yaml").write_text("name: coder\n", encoding="utf-8")
        F.git(repo, "add", "-A")
        F.git(repo, "commit", "-q", "-m", "a tracked bio")
        written = write_scope(repo, {".halo/.gitignore": IGNORE, ".halo/agents/coder.yaml": "name: coder\nnotes: x\n",
                                     ".halo/teams/line.yaml": "name: line\n"})
        ctx.check(f"three files written, got {written}", len(written) == 3)
        ctx.check(f"the run's commit finds nothing to commit, got {F.git(repo, 'status', '--porcelain')!r}",
                  gitops.commit_all(repo, "worker 1: x") is None and F.git(repo, "status", "--porcelain").strip() == "")
    finally:
        cleanup(repo)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="coach probe cli tests"))
