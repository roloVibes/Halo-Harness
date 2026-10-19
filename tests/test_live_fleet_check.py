"""tests.test_live_fleet_check -- Halo 3.1.2.0 R3: the whole two-machine check
(tools/live_fleet_check.py -> halo_harness/fleet/live_check.py) run in-process
against tests/helpers/fleet_hub_rig.py's two harnesses with `--fake`.

Home A is the hub box, home B is the member (joined, `fleet.allow_control:
all`, its catalog on the hub). `live_check_fakes.install(member_home=B)` gives
both sides their fakes, so no model is called: the mission part writes its
file and hands back, the delegated agent stage returns a canned
report, and only the member's index answers the recall query. Every step
PASSes; a member that refuses the task makes the mission step FAIL and the
run exit code 1; `--json` writes the report in its documented shape.

Run: python -m tests.test_live_fleet_check
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _tool():
    spec = importlib.util.spec_from_file_location("live_fleet_check_tool", REPO / "tools" / "live_fleet_check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _ready(rig):
    from tests.helpers.fleet_hub_rig import wait_for
    from tests.helpers.mission_seed import fleet
    fleet(rig, **{"fleet.allow_control": "all"})
    wait_for(lambda: rig.member_session_online("fakesession0000000000000000000001"), 20.0)
    from halo_harness.fleet.live_check import member_of
    return wait_for(lambda: member_of(rig.hub), 20.0)


@test
def test_every_step_passes_over_the_two_home_rig(ctx: Ctx):
    from halo_harness.fleet import live_check as LC
    from halo_harness.fleet.live_check_fakes import install
    from tests.helpers.fleet_hub_rig import HubRig
    with HubRig() as rig:
        member = _ready(rig)
        ctx.check("a member is online on the hub", member is not None and member["name"] == "bob@member")
        restore = install(member_home=Path(rig.root_b) / ".halo")
        try:
            repo = Path(tempfile.mkdtemp(prefix="lc-team-")).resolve()
            report = LC.run_all(rig.hub, rig.home_a, member=member, fake=True, timeout=40.0, repo=repo)
        finally:
            restore()
        names = [s["name"] for s in report["steps"]]
        ctx.check(f"the four steps ran in order, got {names}", names == ["who", "mission", "team", "recall"])
        for s in report["steps"]:
            ctx.check(f"step {s['name']} PASS: {s['evidence']}", s["ok"])
        ctx.check(f"the run is OK and names both harnesses, got {report['hub']} / {report['member']}",
                  report["ok"] and report["hub"] == rig.hub.state.name and report["member"] == "bob@member")
        who = next(s for s in report["steps"] if s["name"] == "who")
        ctx.check(f"who named the member for nmap and this host for gridcraft: {who['evidence']}",
                  "bob@member" in who["evidence"] and "alice@hub" in who["evidence"])
        mission = next(s for s in report["steps"] if s["name"] == "mission")
        ctx.check(f"the mission hand-back carries the nmap line: {mission['evidence']}", "Nmap version" in mission["evidence"])
        team = next(s for s in report["steps"] if s["name"] == "team")
        ctx.check(f"the team step ran the delegated stage on the member: {team['evidence']}",
                  "agent stage ran on bob@member and its gate was accepted here" in team["evidence"])
        recall = next(s for s in report["steps"] if s["name"] == "recall")
        ctx.check(f"recall came only from the member, this host answered 0: {recall['evidence']}",
                  "bob@member" in recall["evidence"] and "own index answered 0" in recall["evidence"])
        text = LC.render(report)
        ctx.check(f"render prints PASS lines and an OK summary:\n{text}",
                  text.count("[PASS]") == 4 and "OK:" in text and "4/4" in text)


@test
def test_a_refusing_member_fails_the_mission_step_and_the_exit_code(ctx: Ctx):
    from halo_harness.fleet import live_check as LC
    from halo_harness.fleet import store
    from halo_harness.fleet.live_check_fakes import install
    from tests.helpers.fleet_hub_rig import HubRig
    with HubRig() as rig:
        member = _ready(rig)
        ctx.check("a member is online", member is not None)
        restore = install(member_home=Path(rig.root_b) / ".halo")
        try:
            rig.set_b(**{"fleet.allow_control": "none"})  # the member refuses run_task
            store.mark(rig.a_id, allow_control="none")
            from halo_harness.fleet import relay_runtime
            for relay in relay_runtime.relays():
                relay.entry["allow_control"] = "none"
            report = LC.run_all(rig.hub, rig.home_a, member=member, fake=True, timeout=20.0,
                                repo=Path(tempfile.mkdtemp(prefix="lc-team2-")).resolve())
        finally:
            restore()
        mission = next(s for s in report["steps"] if s["name"] == "mission")
        ctx.check(f"the mission step FAILs with the reason: {mission['evidence']}",
                  not mission["ok"] and ("refused" in mission["evidence"] or "would not take" in mission["evidence"]))
        ctx.check("the whole run is not OK", report["ok"] is False)
        mod = _tool()
        ctx.check("main's hub path would exit 1 on a failed report (render + rc)",
                  LC.render(report).startswith("Halo fleet two-machine check") and (0 if report["ok"] else 1) == 1)
        ctx.check("the tool module exposes the CLI entry points", hasattr(mod, "main") and hasattr(mod, "write_json"))


@test
def test_the_json_report_shape(ctx: Ctx):
    mod = _tool()
    report = {"ok": True, "fake": True, "hub": "alice@hub", "member": "bob@member", "member_id": "b-1",
              "started": 1.0, "ended": 2.0,
              "steps": [{"name": "who", "ok": True, "evidence": "who nmap -> bob@member", "seconds": 0.1},
                        {"name": "mission", "ok": True, "evidence": "part 1 ran", "seconds": 0.2},
                        {"name": "team", "ok": True, "evidence": "stages ran", "seconds": 0.3},
                        {"name": "recall", "ok": True, "evidence": "1 hit from bob@member", "seconds": 0.1}]}
    import json
    out = Path(tempfile.mkdtemp(prefix="lc-json-")) / "r.json"
    path = mod.write_json(report, str(out))
    back = json.loads(Path(path).read_text(encoding="utf-8"))
    ctx.check("the report round-trips with every top-level key",
              set(back) == {"ok", "fake", "hub", "member", "member_id", "started", "ended", "steps"})
    ctx.check("each step has name, ok, evidence, seconds",
              all(set(s) >= {"name", "ok", "evidence", "seconds"} for s in back["steps"])
              and [s["name"] for s in back["steps"]] == ["who", "mission", "team", "recall"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="live fleet check tests"))
