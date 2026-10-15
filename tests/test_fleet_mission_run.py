"""tests.test_fleet_mission_run -- Halo 3.0.6.0 "Fleet Missions" round R7: a
mission across two Halo homes on loopback (tests/helpers/fleet_hub_rig.py).
The hub A (the Windows host, GridCraft) and the member B (the Kali box,
nmap); the lead, the judge and the worker sessions are fakes (the worker's
session has a REAL PermissionEngine, so the claim guard runs as it does).

1. Under fleet.allow_control `ask` the run_task is a card in B's TUI naming
   the hub, the mission, the part and its claims; allowed, B starts a
   `mission-worker` session whose registry row carries mission / part /
   parent; an edit outside the part's claims is refused there and raised on
   the hub (log, attention row); the DAG holds (part 2 waits for part 1);
   the report counts cost per harness and per part; the journal and the
   digest have the mission.
2. `none` refuses with the reason: the part fails, its dependant is skipped,
   the mission fails with the reason in the report.
3. `stop` stops a part running on the member; with fleet.shared_dir set on
   both, nothing is mirrored.

Run: python -m tests.test_fleet_mission_run
"""
from __future__ import annotations

import json
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
SCRIPT = {"1": {"writes": ["artifacts/1/scan.xml"], "outside": ["MISSION.md", "../../config.json"], "cost": 0.05},
          "2": {"writes": ["artifacts/2/findings.xlsx"], "cost": 0.07}}


def _new(A, ctx):
    from tests.helpers.mission_seed import FakeLead, lead_answer
    A.LEAD = FakeLead(lead_answer(nobody=False))
    status, body = A.create(ctx, {"goal": "Scan the lab and build the findings workbook", "repo": False})
    assert status == 200, body
    return body["mission"]["id"]


def _worker_row(rig, mid: str):
    m = rig.member() or {}
    return next((s for s in m.get("sessions") or [] if s.get("kind") == "mission-worker" and s.get("mission") == mid), None)


@test
def test_ask_cards_the_owner_then_the_part_runs_as_a_mission_worker(ctx: Ctx):
    from halo_harness.fleet import digest, journal
    from halo_harness.fleet import mission_store as S
    from tests.helpers.fleet_hub_rig import HubRig, wait_for
    from tests.helpers.mission_seed import fleet, gate, mission_ctx, reset_fakes, wait_state
    with HubRig() as rig:
        controller, _act = fleet(rig)
        started, hold, script = [], {"1": gate()}, json.loads(json.dumps(SCRIPT))
        A, mctx = mission_ctx(rig, "", script, started, hold)
        mid = _new(A, mctx)
        status, body = A.run(mctx, mid)
        ctx.check(f"run: approved and running, got {status} {body.get('error')}", status == 200 and body["mission"]["state"] == "running")
        rid = rig.card(controller, 15)
        ctx.check(f"B's TUI holds the mission card, got {rid}", bool(rid) and rid.startswith("fleet-ask:mission-"))
        cards = [ev for ev in list(controller.events.queue) if getattr(ev, "kind", "") == "question"
                 and (ev.data or {}).get("id") == rid] if hasattr(controller.events, "queue") else []
        text = cards[0].data["input"]["question"] if cards else ""
        ctx.check(f"the card names the hub, mission, part and claims, got {text!r}",
                  text == f"hub-a asks to run mission {mid} part 1 here: Scan the lab network (claims: artifacts/1/**)")
        asked = wait_for(lambda: S.need(rig.home_a, mid)["parts"]["1"]["state"] == "asked", 5)
        ctx.check("the part is `asked` while the card is open", bool(asked))
        controller.answer_question(rid, "allow")
        row = wait_for(lambda: _worker_row(rig, mid), 15)
        ctx.check(f"allowed: a mission-worker session on B, its row carries mission / part / parent, got {row and {k: row.get(k) for k in ('kind', 'mission', 'part', 'parent')}}",
                  bool(row) and row["part"] == "1" and row["parent"] == mid)
        ctx.check("part 2 waits for part 1 (the DAG)", S.need(rig.home_a, mid)["parts"]["2"]["state"] == "pending")
        hold["1"].set()
        doc = wait_state(rig.home_a, mid, ("done", "failed", "stopped"), 60)
        ctx.check(f"the mission is done, got {doc['state']} {doc.get('stop_reason')}", doc["state"] == "done")
        ctx.check(f"part 1 ran before part 2, got {started}", [p for p, _t in started] == ["1", "2"])
        folder = S.folder(rig.home_a, mid)
        ctx.check("B's artifact and hand-back reached the hub's folder", (folder / "artifacts" / "1" / "scan.xml").is_file()
                  and "part 1 done" in (folder / "parts" / "1" / "handback.md").read_text(encoding="utf-8"))
        said = script["1"].get("denied") or []
        ctx.check(f"B's engine denied both edits outside the claims with the one-line reason, got {said}",
                  [d[1] for d in said] == ["deny", "deny"] and "may edit only its claims (artifacts/1/**)" in said[0][2]
                  and "outside the part's folder" in said[1][2])
        refused = S.read_log(rig.home_a, mid, ("claim_refused",))
        ctx.check(f"the edits outside the claims were refused on B and raised on the hub, got {[r.get('file') for r in refused]}",
                  {r.get("file") for r in refused} >= {"MISSION.md"} and all(r.get("harness") == rig.b_id for r in refused))
        status, att = rig.api("GET", "fleet/attention")
        claim = [r for r in att["rows"] if r["kind"] == "mission_claim"]
        ctx.check(f"a mission_claim attention row, got {[r['what'] for r in claim]}", bool(claim) and mid in claim[0]["what"])
        status, got = rig.api("POST", "fleet/attention/answer", {"id": claim[0]["id"], "key": "a"})
        ctx.check("it is set aside like a conflict", status == 200 and got.get("set_aside"))
        status, rep = rig.api("GET", f"fleet/missions/{mid}/report")
        hs = {h["name"]: h["cost_usd"] for h in rep["report"]["harnesses"]}
        ctx.check(f"the report: cost per harness, got {hs}", hs == {"bob@member": 0.05, "alice@hub": 0.07})
        ctx.check("and per part, with the lead's cost in the total", [p["cost_usd"] for p in rep["report"]["parts"]] == [0.05, 0.07]
                  and abs(rep["report"]["cost"]["total_usd"] - 0.121) < 1e-9 and rep["final"])
        ctx.check("report.md names who did what", "| 1 | bob@member | done | 0.0500 |" in (folder / "report.md").read_text(encoding="utf-8"))
        kinds = [r["kind"] for r in journal.read(rig.home_a, 0, kinds=None) if str(r.get("kind")).startswith("mission_")]
        ctx.check(f"journaled: planned, approved, run, parts, claim, end, got {sorted(set(kinds))}",
                  {"mission_planned", "mission_approved", "mission_run", "mission_part", "mission_claim", "mission_end"} <= set(kinds))
        d = digest.compute(rig.home_a, 0, local_id=rig.a_id, local_name="alice@hub")
        ctx.check("the digest lists the mission", any(m.get("mission") == mid for h in d["harnesses"] for m in h["missions"]))
        reset_fakes()


@test
def test_none_refuses_and_the_dependants_are_skipped(ctx: Ctx):
    from halo_harness.fleet import mission_store as S
    from tests.helpers.fleet_hub_rig import HubRig
    from tests.helpers.mission_seed import fleet, mission_ctx, reset_fakes, wait_state
    with HubRig() as rig:
        fleet(rig, **{"fleet.allow_control": "none"})
        A, mctx = mission_ctx(rig, "", json.loads(json.dumps(SCRIPT)), [])
        mid = _new(A, mctx)
        A.run(mctx, mid)
        doc = wait_state(rig.home_a, mid, ("done", "failed", "stopped"), 30)
        p1, p2 = doc["parts"]["1"], doc["parts"]["2"]
        ctx.check(f"the run_task is refused with the member's reason, got {p1['state']} {p1['error']!r}",
                  p1["state"] == "failed" and "fleet.allow_control: none" in str(p1["error"]))
        ctx.check(f"part 2 is skipped, got {p2['state']} {p2['error']!r}", p2["state"] == "skipped" and "part 1" in p2["error"])
        ctx.check(f"the mission failed with the reason, got {doc['state']} {doc['stop_reason']!r}", doc["state"] == "failed"
                  and "part 1 failed" in doc["stop_reason"])
        md = (S.folder(rig.home_a, mid) / "report.md").read_text(encoding="utf-8")
        ctx.check("the report says what failed", "## What failed" in md and "part 2 skipped" in md)
        reset_fakes()


@test
def test_stop_reaches_a_member_part_and_a_shared_dir_is_not_mirrored(ctx: Ctx):
    from halo_harness.config.paths import bridge_home
    from halo_harness.fleet import mission_store as S
    from tests.helpers.fleet_hub_rig import HubRig, wait_for
    from tests.helpers.mission_seed import fleet, gate, mission_ctx, reset_fakes, wait_state
    shared = tempfile.mkdtemp(prefix="mission-share-")
    with HubRig() as rig:
        (rig.home_a / "config.json").write_text(json.dumps({"fleet": {"name": "alice@hub", "shared_dir": shared}}), encoding="utf-8")
        fleet(rig, **{"fleet.allow_control": "all", "fleet.shared_dir": shared})
        hold = {"1": gate()}
        A, mctx = mission_ctx(rig, "", json.loads(json.dumps(SCRIPT)), [], hold)
        mid = _new(A, mctx)
        ctx.check("with fleet.shared_dir the mission lives on the share", S.folder(rig.home_a, mid).parent == Path(shared)
                  and S.need(rig.home_a, mid)["shared"] is True)
        A.run(mctx, mid)
        row = wait_for(lambda: _worker_row(rig, mid), 15)
        ctx.check("under `all` the part starts with no card", bool(row))
        status, body = A.stop(mctx, mid, "the owner changed plans")
        doc = wait_state(rig.home_a, mid, ("stopped",), 20)
        ctx.check(f"stop: the mission and its running part are stopped, got {doc['state']} {doc['parts']['1']['state']}",
                  doc["state"] == "stopped" and doc["parts"]["1"]["state"] == "stopped" and doc["parts"]["2"]["state"] == "skipped")
        res = wait_for(lambda: (S.read_text(S.folder(rig.home_a, mid), "parts/1/result.json") or None), 15)
        ctx.check(f"the worker on B was interrupted (its result says stopped), got {res!r}",
                  bool(res) and json.loads(res)["state"] == "stopped")
        ctx.check("nothing was mirrored: no file_put, no mirror folder on B",
                  not S.read_log(rig.home_a, mid, ("file_put",)) and not (bridge_home() / "fleet" / "missions" / mid).exists())
        reset_fakes()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="fleet mission run tests"))
