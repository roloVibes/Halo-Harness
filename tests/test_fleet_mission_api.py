"""tests.test_fleet_mission_api -- Halo 3.0.6.0 "Fleet Missions" round R7:
the mission routes and CLI over two Halo homes (tests/helpers/fleet_hub_rig.py):
the hub (A, the Windows host with GridCraft) and a member (B, the Kali box
with nmap), each with its seeded catalog. `POST /api/fleet/missions` drafts
and plans (the fake lead) with the parts pinned by capability; list, get,
edit a part, approve, report, the folder's text files with `..` refused; a
`mission` frame on every change and a `mission_plan` attention row while it
waits; the `halo fleet mission` verbs print and `--json` round-trips
(a child process that reaches the rig's Studio), and `/mission` answers.

Run: python -m tests.test_fleet_mission_api
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def lead(answer: str):
    from halo_harness.fleet import mission_api as A
    from tests.helpers.mission_seed import FakeLead
    A.LEAD = FakeLead(answer)
    return A.LEAD


def frames(rig, mid: str) -> list:
    return [f["data"] for f in rig.seen("fleet") if (f.get("data") or {}).get("action") == "mission"
            and f["data"].get("id") == mid]


@test
def test_the_routes_draft_plan_edit_approve_and_report(ctx: Ctx):
    from tests.helpers.fleet_hub_rig import HubRig
    from tests.helpers.mission_seed import lead_answer
    with HubRig() as rig:
        from tests.helpers.mission_seed import fleet
        fleet(rig)
        fake = lead(lead_answer())
        status, body = rig.api("POST", "fleet/missions", {"goal": "Scan the lab and build the findings workbook",
                                                          "budget_usd": 2, "repo": False}, timeout=60)
        ctx.check(f"POST fleet/missions drafts and plans, got {status} {body.get('error')}", status == 200 and body["plan"])
        mid = body["mission"]["id"]
        parts = {p["id"]: p for p in body["plan"]["parts"]}
        ctx.check(f"nmap -> the Kali box, gridcraft -> the Windows host, got {[(p['harness_name'], p['reason']) for p in parts.values()]}",
                  parts["1"]["harness"] == rig.b_id and parts["2"]["harness"] == rig.a_id
                  and "nmap" in parts["1"]["reason"] and "gridcraft" in parts["2"]["reason"])
        ctx.check("metasploit nobody has", parts["3"]["unassignable"] and parts["3"]["harness"] is None)
        ctx.check("the lead's prompt held both catalogs", "### bob@member" in fake.prompts[0] and "### alice@hub" in fake.prompts[0])
        ctx.check("no full local path in the route's JSON", rig.root_a not in json.dumps(body) and rig.root_b not in json.dumps(body))
        status, listing = rig.api("GET", "fleet/missions")
        ctx.check(f"GET fleet/missions lists it, got {status}", status == 200 and listing["missions"][0]["id"] == mid
                  and listing["missions"][0]["state"] == "planned" and listing["missions"][0]["parts"] == 3)
        status, got = rig.api("POST", f"fleet/missions/{mid}/approve")
        ctx.check(f"approve waits for the unassignable part (409 with the problem), got {status}", status == 409
                  and "unassignable" in got["error"] and got["problems"])
        status, att = rig.api("GET", "fleet/attention")
        row = next((r for r in att["rows"] if r["kind"] == "mission_plan"), None)
        ctx.check(f"a mission_plan attention row waits, got {row and row['what']}", row is not None and mid in row["what"]
                  and set(row["keys"]) == {"a", "r", "s", "o"} and row["text_for"] == "r")
        status, got = rig.api("POST", "fleet/attention/answer", {"id": row["id"], "key": "r", "text": "drop 3"})
        ctx.check(f"the row's edit drops part 3, got {status} {got.get('error')}", status == 200
                  and len(rig.api("GET", f"fleet/missions/{mid}")[1]["plan"]["parts"]) == 2)
        status, got = rig.api("POST", f"fleet/missions/{mid}/parts/2", {"harness": "bob@member"})
        ctx.check(f"giving the gridcraft part to the Kali box is 422, got {status}", status == 422 and "gridcraft" in got["error"])
        ctx.check("an unknown part is 404", rig.api("POST", f"fleet/missions/{mid}/parts/9", {"drop": True})[0] == 404)
        status, got = rig.api("POST", f"fleet/missions/{mid}/approve")
        ctx.check(f"approve, got {status} {got.get('error')}", status == 200 and got["mission"]["state"] == "approved"
                  and got["mission"]["approved_by"] == "alice@hub")
        status, got = rig.api("GET", f"fleet/missions/{mid}/report")
        ctx.check("GET report: the shape before the run", status == 200 and got["final"] is False
                  and {p["id"] for p in got["report"]["parts"]} == {"1", "2"} and "## Who did what" in got["markdown"])
        status, got = rig.api("GET", f"fleet/missions/{mid}/files?path=MISSION.md")
        ctx.check("GET files?path=MISSION.md", status == 200 and "| Part | Title | Harness | Why |" in got["text"])
        status, got = rig.api("GET", f"fleet/missions/{mid}/files")
        paths = [f["path"] for f in got.get("files") or []]
        ctx.check(f"GET files lists the folder, got {paths}", "plan.json" in paths and "parts/1/brief.md" in paths)
        ctx.check("a path with .. is 400", rig.api("GET", f"fleet/missions/{mid}/files?path=../../config.json")[0] == 400)
        ctx.check("an unknown mission is 404", rig.api("GET", "fleet/missions/m-20200101-abcd")[0] == 404)
        states = [f["state"] for f in frames(rig, mid)]
        ctx.check(f"a mission frame on every change, got {states}", states[:2] == ["drafted", "planned"] and "approved" in states)
        status, got = rig.api("POST", f"fleet/missions/{mid}/stop", {"reason": "not today"})
        ctx.check("stop before the run: stopped, with the reason", status == 200 and got["mission"]["state"] == "stopped"
                  and got["mission"]["stop_reason"] == "not today")
        ctx.check("a stopped mission does not stop twice", rig.api("POST", f"fleet/missions/{mid}/stop")[0] == 409)


@test
def test_the_cli_verbs_print_and_json_round_trips(ctx: Ctx):
    from halo_harness.privateio import write_private_atomic
    from tests.helpers.fleet_hub_rig import HubRig, cli
    from tests.helpers.mission_seed import lead_answer
    with HubRig() as rig:
        from tests.helpers.mission_seed import fleet
        fleet(rig)
        lead(lead_answer(nobody=False))
        write_private_atomic(rig.home_a / "studio.json", json.dumps({"pid": os.getpid(), "port": rig.server.server_address[1],
                                                                    "token": rig.server.token}))
        rc, out, err = cli(rig.root_a, "mission", "new", "Scan the lab and build the findings workbook", "--no-repo",
                           "--budget", "3", "--json", timeout=120)
        got = json.loads(out) if rc == 0 else {}
        ctx.check(f"new --json: drafted and planned through Studio, rc {rc} {err[-300:]}", rc == 0 and got.get("source") == "studio"
                  and got["mission"]["state"] == "planned" and got["mission"]["budget_usd"] == 3.0)
        mid = got.get("mission", {}).get("id", "")
        rc, out, _ = cli(rig.root_a, "mission", "plan", mid)
        ctx.check(f"plan prints the table with reasons, got {out[:500]!r}", rc == 0 and f"Mission {mid} (planned)" in out
                  and "bob@member (pinned)" in out and "why: only alice@hub has gridcraft" in out)
        rc, out, _ = cli(rig.root_a, "mission", "status", "--json")
        ctx.check("status --json lists it", rc == 0 and json.loads(out)["missions"][0]["id"] == mid)
        rc, out, _ = cli(rig.root_a, "mission", "approve", mid)
        ctx.check(f"approve, got {out[:200]!r}", rc == 0 and f"Mission {mid} approved." in out)
        rc, out, _ = cli(rig.root_a, "mission", "open", mid, "--json")
        ctx.check("open names the folder", rc == 0 and json.loads(out)["folder"].endswith(mid))
        rc, out, _ = cli(rig.root_a, "mission", "report", mid)
        ctx.check("report prints the markdown", rc == 0 and f"# Mission {mid}: approved" in out)
        rc, out, _ = cli(rig.root_a, "mission", "stop", mid, "--reason", "cli test")
        ctx.check(f"stop prints the parts by harness, got {out[:300]!r}", rc == 0 and f"Mission {mid} stopped" in out
                  and "reason: cli test" in out)
        rc, _out, err = cli(rig.root_a, "mission", "approve", "m-20200101-abcd")
        ctx.check(f"an unknown mission is exit 1, got {rc} {err!r}", rc == 1 and "no mission" in err)
        ctx.check("a verb that does not exist is usage (2)", cli(rig.root_a, "mission", "launch")[0] == 2)
        from halo_harness.commands.builtins import _cmd_mission
        os.environ["BRIDGE_TEST_HOME"], before = rig.root_a, os.environ["BRIDGE_TEST_HOME"]
        try:
            text = _cmd_mission("", None)
        finally:
            os.environ["BRIDGE_TEST_HOME"] = before
        ctx.check(f"/mission is the status, got {text!r}", mid in text and "stopped" in text)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="fleet mission api tests"))
