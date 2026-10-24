"""tests.test_isolation_report -- Halo 3.1.8.0 R5: where the opt-ins show: `halo doctor`'s isolation and secrets
rows, the run report's `opt_ins` and its printed lines, `halo goal show`, the supervisor's failure kind for a
lane that stopped on one, Studio's run payload and the agent row. No docker, podman, sudo or op runs and no
model is called.

Run: python -m tests.test_isolation_report
"""
from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.isolation_rig import IsoEnv, Recorder, run_with_lane
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()


def _declaring_lane(e, *, docker: bool = True):
    if docker:
        e.tool("docker")
    e.lineup("ci", {"agents": [{"agent": "boss", "role": "main"}, {"agent": "reviewer", "role": "subagent"}],
                    "isolation": {"mode": "container", "image": "halo-test:3"}})
    e.bio("boss", {})
    e.bio("reviewer", {"tools": {"capabilities": ["read"]}, "secrets": {"broker": "env"},
                       "environment": {"secrets": [{"env": "SERVICE_TOKEN", "ref": "ENV:PATH"}]}})
    repo, run_dir, lane = run_with_lane(lineup="ci", bio="reviewer")
    from halo_harness.orchestra.adapters import spawn_worker
    result = spawn_worker(None, run_dir=run_dir, runner=Recorder())(lane)
    return repo, run_dir, lane, result


@test
def test_doctor_rows_say_which_modes_and_brokers_this_host_has(ctx: Ctx):
    with IsoEnv() as e:
        from halo_harness.doctor import _check_entries
        ids = [cid for cid, _line in _check_entries(e.root)]
        ctx.check(f"isolation and secrets are doctor rows, got {ids[-12:]}", "isolation" in ids and "secrets" in ids)
        from halo_harness.isolation.doctor_rows import isolation_row, secrets_row
        declared = [("lineup ci", {"mode": "container", "image": "x"}, {"broker": "1password", "refs": []})]
        row = isolation_row(declared, which=e.which, platform="linux")
        ctx.check(f"no engine: the lineup's container is a WARN line, got {row}",
                  row == "[WARN] Isolation: lineup ci declares container: no docker or podman on this host "
                         "-> see: docs/ISOLATION.md")
        row = secrets_row(declared, which=e.which)
        ctx.check(f"no op: the WARN line names it, got {row}",
                  row == "[WARN] Secrets: lineup ci declares 1password: no `op` on PATH -> see: docs/ISOLATION.md")
        e.tool("docker")
        e.fake_op({})
        row = isolation_row(declared, which=e.which, platform="linux")
        ctx.check(f"with docker: OK and who declares, got {row}", row.startswith("[OK] Isolation: container (docker)")
                  and row.endswith("declared by: lineup ci"))
        ctx.check("with op: OK", secrets_row(declared, which=e.which).startswith("[OK] Secrets: 1password (op on PATH)"))
        ctx.check("nothing declared: an OK line that says so", isolation_row([], which=e.which, platform="linux")
                  .endswith("declared by: none"))


@test
def test_the_run_report_has_a_line_per_lane(ctx: Ctx):
    with IsoEnv() as e:
        _repo, run_dir, lane, _result = _declaring_lane(e)
        from halo_harness.orchestra.goal import load_goal
        from halo_harness.orchestra.report import format_report, write_report
        report = write_report(run_dir, goal=load_goal(Path(run_dir) / "goal.json"), lanes=[lane], status="stopped",
                              stop_reason="test")
        want = ["isolation: container (halo-test:3)", "secrets: env (1 ref)", "tools: read (by bio reviewer)"]
        ctx.check(f"report.json keeps them, got {report.get('opt_ins')}", report.get("opt_ins") == [{"lane": 2, "lines": want}])
        text = format_report(report)
        ctx.check("and prints them", all(f"  lane 2: {ln}" in text for ln in want))
        ctx.check("no value of the ENV ref in the report", "PATH=" not in text and str(Path(sys.executable).parent) not in text)
    with IsoEnv() as e:
        e.lineup("open", {"agents": [{"agent": "boss", "role": "main"}]})
        e.bio("boss", {})
        _repo, run_dir, lane = run_with_lane(lineup="open")
        from halo_harness.orchestra.goal import load_goal
        from halo_harness.orchestra.report import write_report
        report = write_report(run_dir, goal=load_goal(Path(run_dir) / "goal.json"), lanes=[lane], status="stopped")
        ctx.check("nothing declared: no opt_ins key at all", "opt_ins" not in report)


@test
def test_goal_show_prints_the_lines(ctx: Ctx):
    with IsoEnv() as e:
        repo, run_dir, _lane, _result = _declaring_lane(e)
        from halo_harness.supervise import goal_cli, queue
        g = queue.add(e.state, "write it", repo=str(repo), kind="orchestra")
        queue.update(e.state, g["id"], lambda goal: goal.update(run_dir=str(run_dir)))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            goal_cli._show(e.state, g["id"], False)
        text = out.getvalue()
        ctx.check(f"each line under the run, got {text!r}", "  lane 2: isolation: container (halo-test:3)" in text
                  and "  lane 2: tools: read (by bio reviewer)" in text and "  lane 2: secrets: env (1 ref)" in text)


@test
def test_a_lane_that_stops_on_its_isolation_is_a_worker_failure(ctx: Ctx):
    with IsoEnv() as e:
        _repo, run_dir, lane, result = _declaring_lane(e, docker=False)
        line = "isolation: container asked, no docker or podman on this host"
        ctx.check(f"the spawn's error is the line, got {result}", result.get("error") == line)
        from halo_harness.supervise.runner import classify
        ctx.check("the supervisor files the stopped run as failure.kind worker",
                  classify(f"lane 2: {line}") == ("failed", "worker", "worker"))


@test
def test_studio_and_the_agent_row_get_the_same_lines(ctx: Ctx):
    with IsoEnv() as e:
        _repo, run_dir, _lane, _result = _declaring_lane(e)
        from halo_harness.studio.orchestra_model import run_payload
        lanes = run_payload(run_dir, False)["lanes"]
        ctx.check(f"the run view's lane carries them, got {lanes[0].get('opt_ins')}",
                  lanes[0].get("opt_ins") == ["isolation: container (halo-test:3)", "secrets: env (1 ref)",
                                              "tools: read (by bio reviewer)"])
        from halo_harness.agent.agent_registry import FIELDS, AgentTree

        class _Root:
            agent_id = None
            opt_ins = ["tools: read (by bio reviewer)"]
            model_ref = None
            log = None
        ctx.check("opt_ins is an agent row field", "opt_ins" in FIELDS)
        ctx.check("the main row carries the session's lines", AgentTree(_Root()).row("main").get("opt_ins") == _Root.opt_ins)
        ui = Path(__file__).resolve().parent.parent / "halo_harness" / "studio" / "ui" / "src" / "routes"
        ctx.check("the lanes view and the Agent panel render them", "lane-optins" in (ui / "orchestra" / "Lanes.tsx").read_text(
            encoding="utf-8") and "fleet-agent-optins" in (ui / "fleet" / "Agent.tsx").read_text(encoding="utf-8"))
        ctx.check("the Lineup tab has the three fields", all(t in (ui / "roles" / "OptInFields.tsx").read_text(encoding="utf-8")
                                                          for t in ("roles-isolation", "roles-secrets", "roles-capabilities")))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
