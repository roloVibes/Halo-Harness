"""tests.test_team_delegate_runs -- Halo 3.1.2.0 round R2: a team's orchestra
stage with `harness: <member>` runs on that fleet member
(team/remote_stage.py -> team/delegate.py -> the hub's `run_task` ->
fleet/mission_stage_run.py on the member), over tests/helpers/fleet_hub_rig.py's
two homes: home A runs the hub and the team, home B is the member (its fake
session behind the real Controller, `fleet.allow_control: all`) with a
checkout of the same repo. The member's ORCHESTRA seam is a fake
(no model). The stage's row shows the harness chip and the remote run id,
its report lands in stages/<id>/report.json, its unit follows the part;
a refused dispatch fails the stage with the reason.

Run: python -m tests.test_team_delegate_runs
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
ORIGIN = "https://example.invalid/launch.git"
TEAM = """\
name: launch
brief: docs/BRIEF.md
members:
  - {name: writer, lineup: standard, role: main}
blocks:
  - {id: site, kind: folder, path: site/, claims: file}
workflow:
  stages:
    - {id: build, kind: orchestra, harness: MEMBER, goal: {what: "Build the site", done_when: "it renders", workers: 2},
       writes: [site], trigger: manual}
"""


class Remote:
    """The member's seams: what ran there, and where."""

    def __init__(self):
        self.calls: list = []

    def orchestra(self, goal, root):
        self.calls.append(("orchestra", goal.get("what"), str(root)))
        return {"ok": True, "text": "Orchestra run 20261018-100000-aaaa finished", "cost_usd": 0.02,
                "run_id": "20261018-100000-aaaa", "report": {"status": "finished", "cost_usd": 0.02, "lanes": 2}}


def _wait(fn, timeout: float = 60.0, step=None):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if step is not None:
            step()
        got = fn()
        if got:
            return got
        time.sleep(0.2)
    return fn()


@test
def test_an_orchestra_stage_runs_on_the_member_and_a_refusal_fails(ctx: Ctx):
    from halo_harness.fleet import mission_stage_run as MSR
    from halo_harness.team import board as BD
    from halo_harness.team import spec as S
    from halo_harness.team.delegate import FleetDelegate
    from halo_harness.team.run import TeamRunner, open_run
    from halo_harness.work.store import UnitStore
    from tests.helpers import team_rig as R
    from tests.helpers.fleet_hub_rig import HubRig
    from tests.helpers.mission_seed import fleet
    from tests.helpers.orchestra_fixtures import git
    remote = Remote()
    MSR.ORCHESTRA = remote.orchestra
    try:
        with HubRig() as rig:
            member_repo = Path(rig.root_b)
            git(member_repo, "init", "-q")
            git(member_repo, "remote", "add", "origin", ORIGIN)
            fleet(rig, **{"fleet.allow_control": "all"})
            root, state = R.repo(TEAM.replace("MEMBER", rig.b_id))
            git(root, "remote", "add", "origin", ORIGIN)
            team = S.load_team(root, state)
            problems = S.validate_team(team, cwd=root, state_dir=state, preflight=False)
            ctx.check(f"the team file with remote stages is valid, got {problems}", problems == [])
            fakes = R.Fakes()
            runner = TeamRunner(team, open_run(team, cwd=root, state_dir=state), cwd=root, state_dir=state,
                                spawn=fakes.spawn, dispatch=FleetDelegate(home=rig.home_a))
            ctx.check("the board rows carry the member as the stage's harness",
                      [r["harness"] for r in runner.board()["stages"]] == [rig.b_id])
            runner.request("build")
            done = _wait(lambda: runner.row("build").get("state") in ("done", "failed"), 90, step=runner.tick)
            build = runner.row("build")
            ctx.check(f"the stage ran on the member and finished, got {build['state']} {build.get('error')!r}",
                      done and build["state"] == "done")
            ctx.check(f"the member ran the goal in its checkout, got {remote.calls}",
                      [c[0] for c in remote.calls] == ["orchestra"] and remote.calls[0][1] == "Build the site"
                      and Path(remote.calls[0][2]).resolve() == member_repo.resolve())
            ctx.check(f"the rows carry the remote run ids, got {build.get('remote')}",
                      build["remote"]["run"] == "20261018-100000-aaaa" and build["remote"]["harness"] == rig.b_id
                      and build["remote"]["part_state"] == "done")
            rep = BD.read_stage_file(runner.run_dir, "build", "report.json", None)
            refs = BD.read_stage_file(runner.run_dir, "build", "refs.json", None)
            ctx.check(f"the report and the refs landed in stages/build/, got {rep} {refs}",
                      rep == {"status": "finished", "cost_usd": 0.02, "lanes": 2}
                      and refs["orchestra_run"] == "20261018-100000-aaaa" and refs["harness"] == rig.b_id)
            ctx.check("the hand-back is the run's line, the cost the member's",
                      "finished" in (BD.read_stage_file(runner.run_dir, "build", "handback.md", "") or "")
                      and abs(build["cost_usd"] - 0.02) < 1e-9)
            units = {u.id: u for u in UnitStore(runner.run_dir).units()}
            ctx.check("the stage unit is done", units["build"].state == "done")
            from halo_harness.fleet import store
            rig.set_b(**{"fleet.allow_control": "none"})
            store.mark(rig.a_id, allow_control="none")  # the joined hub's own level wins over the config's
            from halo_harness.fleet import relay_runtime
            for relay in relay_runtime.relays():
                relay.entry["allow_control"] = "none"
            runner = TeamRunner(team, open_run(team, new=True, cwd=root, state_dir=state), cwd=root, state_dir=state,
                                spawn=fakes.spawn, dispatch=FleetDelegate(home=rig.home_a))
            runner.request("build")
            _wait(lambda: runner.row("build").get("state") == "failed", 30, step=runner.tick)
            row = runner.row("build")
            ctx.check(f"a refused dispatch fails the stage with the reason, got {row['state']} {row.get('error')!r}",
                      row["state"] == "failed" and rig.b_id in row["error"] and "refused" in row["error"])
    finally:
        MSR.ORCHESTRA = None


@test
def test_the_stage_unit_follows_the_part(ctx: Ctx):
    from halo_harness.team import spec as S
    from halo_harness.team.run import TeamRunner, open_run
    from halo_harness.work.store import UnitStore
    from tests.helpers import team_rig as R
    root, state = R.repo(TEAM.replace("MEMBER", "kali"))
    team = S.load_team(root, state)
    fakes = R.Fakes(dispatch_status=202)
    runner = TeamRunner(team, open_run(team, cwd=root, state_dir=state), cwd=root, state_dir=state, **fakes.seams())
    runner.request("build")
    runner.tick()
    send = next(c for c in fakes.calls if c[0] == "send_run")
    ctx.check(f"the stage went out as a run of its goal, got {send[3].get('kind')} {send[3].get('goal', {}).get('what')}",
              send[1] == "kali" and send[3]["kind"] == "orchestra" and send[3]["goal"]["what"] == "Build the site"
              and send[3]["repo"])
    unit = UnitStore(runner.run_dir).unit("build")
    ctx.check(f"asked: the row waits on the owner's card, the unit is waiting, got {runner.row('build')['waiting']!r} {unit.state}",
              runner.row("build")["state"] == "running" and unit.state == "waiting"
              and runner.row("build")["waiting"] == "orchestra run asked; the owner's card is open on kali")
    fakes.polls.append({"state": "running"})
    runner.tick()
    ctx.check("running on the member", UnitStore(runner.run_dir).unit("build").state == "running"
              and runner.row("build")["remote"]["part_state"] == "running")
    fakes.polls.append({"ok": False, "state": "failed", "text": "", "cost_usd": 0.01, "error": "the lead stopped",
                        "run_id": "r-1", "report": {"status": "stopped"}})
    runner.tick()
    row = runner.row("build")
    ctx.check(f"failed with the member's reason, got {row['state']} {row['error']!r}", row["state"] == "failed"
              and row["error"] == "the lead stopped" and row["remote"]["run"] == "r-1")
    runner2 = TeamRunner(team, open_run(team, new=True, cwd=root, state_dir=state), cwd=root, state_dir=state,
                         **R.Fakes(dispatch_status=403).seams())
    runner2.request("build")
    runner2.tick()
    ctx.check(f"403: failed with the reason, got {runner2.row('build')['error']!r}",
              runner2.row("build")["state"] == "failed" and runner2.row("build")["error"] == "kali refused: the owner said no")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="team delegated run tests"))
