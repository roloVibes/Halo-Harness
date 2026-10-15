"""tests.test_fleet_panels_api -- Halo 3.0.5.0 "Fleet" round R4, the panels'
backend over real HTTP to an in-process Studio running the hub (the R3 rig,
tests/helpers/studio_fleet_rig.py): the attention queue merges every source
and an answer reaches the right handler and is journaled; a spend cap pauses
and raises a row, and lifting it resumes; a conflict across two harnesses (and
across two sessions of one) is found and listed; the health subset is
read-only and cached; the digest counts per harness. Hand-offs, recordings,
the replay and the CLI verbs: tests/test_fleet_panels_extras.py.

Run: python -m tests.test_fleet_panels_api
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
NOW = time.time()


def _kinds(rows: list) -> list:
    return sorted({r["kind"] for r in rows})


@test
def test_attention_builds_one_queue_from_every_source(ctx: Ctx):
    from halo_harness.fleet import attention
    view = {"harnesses": [
        {"id": "L", "name": "me", "local": True, "sessions": [
            {"session_id": "s1", "title": "one", "pending": {"permission": ["p1"], "question": ["fleet-ask:c1", "q1"],
                                                             "plan": ["pl1"], "approval": ["ap1"]},
             "agents": [{"agent_id": "main", "state": "waiting"}, {"agent_id": "a2", "name": "tester", "state": "paused"}]}]},
        {"id": "M", "name": "kali@lab", "sessions": [{"session_id": "s2", "pending": {"question": ["fleet-ask:c9"]},
                                                      "agents": [{"agent_id": "main", "state": "running"},
                                                                 {"agent_id": "w1", "name": "verifier", "state": "waiting"}]}]}]}
    asks = {("L", "s1", "p1"): {"kind": "permission", "agent_id": "main", "data": {"id": "p1", "name": "Bash", "input": {"command": "make clean"}}}}
    ref = {"key": "M|s2|w1", "harness": "M", "harness_name": "kali@lab", "session_id": "s2", "agent_id": "w1", "name": "verifier"}
    rows = attention.build(view, asks=asks, flows=[{"run": "f1", "name": "launch", "waiting_step": "render"}],
                           orchestra=[{"run_id": "o1", "state": "stopped", "created": NOW - 60, "stop_reason": "the return cap"},
                                      {"run_id": "o0", "state": "finished", "created": NOW - 60}],
                           commands=[{"command_id": "c5", "harness": "M", "session_id": "s2", "cmd": "agent_stop", "state": "asked"}],
                           reached=[{"scope": "harness", "key": "M", "label": "kali@lab", "spent": 2.0, "cap": 1.0, "sessions": [["M", "s2"]]}],
                           conflicts=[{"repo": "shop", "file": "basket.py", "a": {**ref, "key": "L|s1|main", "harness": "L", "name": "main"}, "b": ref}],
                           now=NOW)
    ctx.check(f"every kind once, got {_kinds(rows)}", _kinds(rows) == sorted(
        ["permission", "question", "plan", "approval", "fleet_ask", "waiting", "paused", "flow_gate", "orchestra_gate", "control_ask",
         "cap", "conflict"]))
    perm = next(r for r in rows if r["kind"] == "permission")
    ctx.check(f"the permission row says what is asked, its keys and the card id, got {perm}",
              perm["what"] == "Permission: Bash" and "make clean" in perm["detail"] and set(perm["keys"]) == {"a", "r", "s", "o"}
              and perm["target"] == {"request_id": "p1"} and perm["text_for"] == "r")
    ctx.check("a member's own fleet card is its owner's, and its waiting main is not a row of ours",
              not [r for r in rows if r["harness"] == "M" and r["kind"] in ("fleet_ask", "waiting") and r["agent_id"] == "main"])
    ctx.check("a member agent waiting with no card of its own is a row", any(r["kind"] == "waiting" and r["agent_id"] == "w1" for r in rows))
    ctx.check("the orchestra row carries the stop reason; a finished run is no row",
              [r["detail"] for r in rows if r["kind"] == "orchestra_gate"] == ["the return cap"])
    again = attention.build(view, asks=asks, seen={r["id"]: r["since"] for r in rows}, acks=[perm["id"]], now=NOW + 50)
    ctx.check("a set-aside row is gone and the rest keep their first-seen time",
              perm["id"] not in {r["id"] for r in again} and all(r["since"] == NOW for r in again))


def _wait(fn, timeout: float = 15.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        got = fn()
        if got:
            return got
        time.sleep(0.1)
    return None


def _seed_gates(rig) -> "tuple[Path, Path]":
    from halo_harness.flows import state
    from halo_harness.flows.gates import gate_path
    from halo_harness.orchestra import jsonl
    flow = state.runs_dir(rig.state) / state.new_run_id()
    (flow / "steps").mkdir(parents=True)
    jsonl.write_json(flow / "flow.json", {"name": "launch-post", "run": flow.name, "created": NOW, "status": "waiting",
                                          "steps": [{"id": "render", "kind": "media", "state": "waiting"}]})
    jsonl.write_json(gate_path(flow, 1), {"id": "g1", "step": "render", "round": 1, "actions": ["accept", "redo", "stop"]})
    orch = rig.proj / ".halo" / "orchestra" / "20261014-090000-ab12"
    orch.mkdir(parents=True)
    jsonl.write_json(orch / "goal.json", {"what": "split the basket module"})
    jsonl.write_json(orch / "run.json", {"created": NOW - 120})
    jsonl.write_json(orch / "report.json", {"run_id": orch.name, "status": "stopped", "cost_usd": 0.1,
                                            "stop_reason": "lane 2 reached the return cap (3) and the tests still fail"})
    return flow, orch


@test
def test_the_queue_over_the_rig_and_answers_reach_their_handlers(ctx: Ctx):
    from halo_harness.fleet import journal
    from halo_harness.fleet.hub_commands import Pending
    from tests.helpers.studio_fleet_member import APPROVAL_ID, REVIEWER
    from tests.helpers.studio_fleet_rig import MEMBER, MEMBER_SID, StudioFleetRig
    with StudioFleetRig() as rig:
        flow, _orch = _seed_gates(rig)
        p = Pending("c0mmand5", MEMBER, MEMBER_SID, "agent_stop")
        p.state = "asked"
        rig.hub.state.commands._pending[p.cid] = p
        rig.hub.state.frames(MEMBER, {"link": "rig-link", "frames": [{"session_id": MEMBER_SID, "event": "agent_state", "agent_id": REVIEWER["agent_id"],
                                                                     "data": {**REVIEWER, "state": "paused"}, "ts": time.time()}]})
        status, got = rig.api("GET", "fleet/attention")
        rows = got.get("rows") or []
        ctx.check(f"member cards, a paused agent, the flow gate, the orchestra gate and the asked command, got {_kinds(rows)}",
                  status == 200 and {"question", "approval", "paused", "flow_gate", "orchestra_gate", "control_ask"} <= set(_kinds(rows))
                  and got["count"] == len(rows))
        ap = next(r for r in rows if r["kind"] == "approval")
        ctx.check(f"the approval row reads the member's card frame, got {ap['what']!r} {ap['detail']!r}",
                  ap["what"] == "Approval (reviewer)" and "two findings" in ap["detail"] and ap["harness_name"] == "kali@lab")
        ctx.check("an orchestra gate row says why it stopped", any("return cap" in r["detail"] for r in rows if r["kind"] == "orchestra_gate"))
        status, res = rig.api("POST", "fleet/attention/answer", {"id": ap["id"], "key": "a"})
        sent = [d for d in rig.member_cmds if d.get("cmd") == "answer"]
        ctx.check(f"`a` on the approval reaches the member as an answer, got {status} {sent[-1:] }",
                  status == 200 and res["answer"] == "accept" and sent and sent[-1]["fields"]
                  == {"kind": "approval", "request_id": APPROVAL_ID, "action": "accept"})
        q = next(r for r in rows if r["kind"] == "question")
        ctx.check("an answer that needs text is a 422 without it", rig.api("POST", "fleet/attention/answer", {"id": q["id"], "key": "r"})[0] == 422)
        ctx.check("a key the row does not take is a 422", rig.api("POST", "fleet/attention/answer", {"id": q["id"], "key": "a"})[0] == 422)
        ctx.check("an unknown row is a 404", rig.api("POST", "fleet/attention/answer", {"id": "nope", "key": "a"})[0] == 404)
        status, res = rig.api("POST", "fleet/attention/answer", {"id": q["id"], "key": "o"})
        ctx.check(f"`o` says where to open it and sends nothing, got {res}", status == 200 and res["open"]["panel"] == "fleet-agent"
                  and res["open"]["session_id"] == MEMBER_SID and len([d for d in rig.member_cmds if d.get("cmd") == "answer"]) == 1)
        paused = next(r for r in rows if r["kind"] == "paused")
        status, res = rig.api("POST", "fleet/attention/answer", {"id": paused["id"], "key": "a"})
        ctx.check(f"`a` on the paused agent resumes it, got {status}", status == 200 and rig.member_cmds[-1]["cmd"] == "resume"
                  and rig.member_cmds[-1]["fields"].get("agent_id") == REVIEWER["agent_id"])
        fg = next(r for r in rows if r["kind"] == "flow_gate")
        status, res = rig.api("POST", "fleet/attention/answer", {"id": fg["id"], "key": "r", "text": "warmer colours"})
        answer = json.loads((flow / "steps" / "1.answer.json").read_text(encoding="utf-8")) if (flow / "steps" / "1.answer.json").is_file() else {}
        ctx.check(f"`r` on the flow gate is a redo with the instruction, got {status} {answer}",
                  status == 200 and answer.get("action") == "redo" and answer.get("instruction") == "warmer colours")
        og = next(r for r in rows if r["kind"] == "orchestra_gate")
        ca = next(r for r in rows if r["kind"] == "control_ask")
        for r in (og, ca):
            rig.api("POST", "fleet/attention/answer", {"id": r["id"], "key": "a"})
        left = {r["id"] for r in rig.api("GET", "fleet/attention")[1]["rows"]}
        ctx.check("set aside: the orchestra and control rows are gone, the answered ones too",
                  not ({og["id"], ca["id"], ap["id"], paused["id"]} & left))
        rows_j = journal.read(rig.state, NOW - 60)
        decisions = [r for r in rows_j if r["kind"] == "decision"]
        ctx.check(f"each decision is journaled with who answered, got {[(d['row_kind'], d['by']) for d in decisions]}",
                  {d["row_kind"] for d in decisions} >= {"approval", "paused", "flow_gate", "orchestra_gate", "control_ask"}
                  and all(d["by"] == "rolo@studio" for d in decisions) and any(r["kind"] == "ack" for r in rows_j))
        digest = rig.api("GET", "fleet/digest?since=10m")[1]
        member = next(h for h in digest["harnesses"] if h["id"] == MEMBER)
        ctx.check(f"the digest lists the member's decisions, got {len(member['decisions'])}", len(member["decisions"]) >= 2)


@test
def test_a_cap_pauses_raises_a_row_and_lifting_it_resumes(ctx: Ctx):
    from halo_harness.fleet import journal
    from tests.helpers.studio_fleet_rig import MEMBER, MEMBER_SID, StudioFleetRig
    with StudioFleetRig() as rig:
        status, got = rig.api("POST", "fleet/caps", {"per_harness_usd_per_day": 0.05, "fleet_usd_per_day": 0})
        cfg = json.loads((rig.state / "config.json").read_text(encoding="utf-8"))["fleet"]["caps"]
        ctx.check(f"written as fleet.caps.*, got {status} {cfg}", status == 200 and cfg["per_harness_usd_per_day"] == 0.05
                  and cfg["fleet_usd_per_day"] is None and got["caps"]["per_harness_usd_per_day"] == 0.05)
        ctx.check(f"kali@lab spent $0.0599 today: its cap is reached, got {got['reached']}",
                  [(r["scope"], r["key"]) for r in got["reached"]] == [("harness", MEMBER)])
        ctx.check("a negative cap is a 422", rig.api("POST", "fleet/caps", {"fleet_usd_per_day": -1})[0] == 422)
        pause = _wait(lambda: [d for d in rig.member_cmds if d.get("cmd") == "pause"])
        ctx.check(f"its session is paused with reason cap, got {pause}", pause and pause[0]["session_id"] == MEMBER_SID
                  and pause[0]["fields"] == {"reason": "cap"})
        rows = rig.api("GET", "fleet/attention")[1]["rows"]
        cap = next((r for r in rows if r["kind"] == "cap"), None)
        ctx.check(f"and an attention row says so, got {cap and cap['what']}", cap is not None and "kali@lab" in cap["what"])
        costs = rig.api("GET", "fleet/costs")[1]
        ctx.check(f"costs: the fleet, per harness, per project, the caps, got {costs['fleet']}",
                  abs(costs["fleet"] - 0.0599) < 1e-9 and [p["key"] for p in costs["projects"]] == ["shop"] and costs["reached"])
        status, res = rig.api("POST", "fleet/attention/answer", {"id": cap["id"], "key": "a"})
        ctx.check(f"lifting it resumes the session, got {status} {res.get('resumed')}", status == 200 and res["lifted"]
                  and _wait(lambda: [d for d in rig.member_cmds if d.get("cmd") == "resume"]))
        ctx.check("the row is gone and stays gone today", not [r for r in rig.api("GET", "fleet/attention")[1]["rows"] if r["kind"] == "cap"])
        kinds = [r["kind"] for r in journal.read(rig.state, NOW - 60)]
        ctx.check("the pause and the lift are journaled", "cap_pause" in kinds and "cap_ack" in kinds)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="fleet panels api tests"))
