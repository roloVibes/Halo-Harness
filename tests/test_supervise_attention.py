"""tests.test_supervise_attention -- Halo 3.1.8.0 R1: the parked decisions
(supervise/decisions.py), their attention rows and answers
(fleet/supervise_attention.py, wired into fleet/attention.build and
studio/fleet_answer), the morning summary route (studio/supervise_api.py), and
an end-to-end parked plan review answered from Studio's Attention queue
(StudioFleetRig). No model is called.

Run: python -m tests.test_supervise_attention
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

ensure_default_provider_credentials()
test, TESTS = new_registry()
NOW = time.time()


class _Env:
    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
        d = Path(tempfile.mkdtemp(prefix="supervise-attn-"))
        os.environ["BRIDGE_TEST_HOME"] = str(d)
        os.environ["BRIDGE_STATE_DIR"] = str(d / ".halo")
        self.state_dir = d / ".halo"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        return self

    def __exit__(self, *exc):
        for k, v in self._saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


@test
def test_decisions_park_answer_and_close(ctx: Ctx):
    with _Env() as e:
        from halo_harness.supervise import decisions
        row = decisions.park(e.state_dir, "goal_budget", "g-1", "cap", "Goal g-1: over the budget", "spent $1",
                             run_dir="/tmp/run")
        ctx.check("parked open row carries its own keys", row["kind"] == "goal_budget" and set(row["keys"]) == {"a", "r", "s", "o"})
        ctx.check("one open row", len(decisions.open_rows(e.state_dir)) == 1)
        # a second park of the same decision returns the same row (not a duplicate)
        again = decisions.park(e.state_dir, "goal_budget", "g-1", "cap", "x", "y")
        ctx.check("parking it again is the same row", again["id"] == row["id"] and len(decisions.open_rows(e.state_dir)) == 1)
        saved, why = decisions.answer(e.state_dir, row["id"], "r", "2.50", by="me")
        ctx.check(f"answer records the key and text, got {why!r}", saved is not None and saved["answer"]["key"] == "r"
                  and saved["answer"]["text"] == "2.50")
        ctx.check("it is answered, not open", not decisions.open_rows(e.state_dir) and len(decisions.answered(e.state_dir)) == 1)
        decisions.close(e.state_dir, row["id"], "done")
        ctx.check("closed: neither open nor answered", not decisions.open_rows(e.state_dir) and not decisions.answered(e.state_dir))
        r2, why2 = decisions.answer(e.state_dir, "nope", "a")
        ctx.check("an unknown row is refused", r2 is None and "no parked" in why2)


@test
def test_a_gate_row_needs_a_number_for_r(ctx: Ctx):
    with _Env() as e:
        from halo_harness.supervise import decisions
        row = decisions.park(e.state_dir, "goal_gate", "g-2", "cap", "a gate", run_dir="/tmp/r")
        saved, why = decisions.answer(e.state_dir, row["id"], "r", "")
        ctx.check("r with no number is refused", saved is None and "number" in why)
        saved, why = decisions.answer(e.state_dir, row["id"], "r", "3")
        ctx.check("r with a number is taken", saved is not None)
        ctx.check("number() reads it", decisions.number("raise by 3", 1) == 3.0 and decisions.number("", 2) == 2.0)


@test
def test_rows_merge_into_the_attention_queue(ctx: Ctx):
    with _Env() as e:
        from halo_harness.fleet import attention
        from halo_harness.supervise import decisions
        decisions.park(e.state_dir, "goal_plan", "g-7", "plan", "Goal g-7: the plan waits", "do the thing",
                       run_dir=str(e.state_dir / "orchestra" / "r1"))
        rows = attention.build({"harnesses": [{"id": "L", "name": "me", "local": True, "sessions": []}]},
                               home=e.state_dir, now=NOW)
        plan = [r for r in rows if r["kind"] == "goal_plan"]
        ctx.check(f"the goal_plan row is in the queue, got {[r['kind'] for r in rows]}", len(plan) == 1)
        ctx.check("the row carries approve/reject/open and the decision id",
                  set(plan[0]["keys"]) == {"a", "r", "o"} and plan[0]["target"].get("decision"))
        ctx.check("goal_plan is a KEYS/TEXT_FOR/push kind", "goal_plan" in attention.KEYS and attention.TEXT_FOR.get("goal_plan") == "r")
        from halo_harness.fleet.push import PUSH_KINDS
        ctx.check("the goal kinds push to the phone", all(k in PUSH_KINDS for k in ("goal_plan", "goal_gate", "goal_budget", "goal_ask")))


@test
def test_open_target_points_at_the_run(ctx: Ctx):
    from halo_harness.fleet.supervise_attention import open_target
    t = open_target({"kind": "goal_gate", "target": {"run_dir": "/x/.halo/orchestra/run-9", "goal": "g-3"}})
    ctx.check(f"open points at the Orchestra run, got {t}", t["section"] == "orchestra" and t["run"] == "run-9" and t["goal"] == "g-3")


@test
def test_summary_route_line(ctx: Ctx):
    with _Env() as e:
        from halo_harness.supervise import history, pulse
        from halo_harness.studio.supervise_api import get_summary

        class _Req:
            method = "GET"
            path = "supervise/summary"
            state_dir = e.state_dir
        # no pulse: no line
        status, body = get_summary(_Req())
        ctx.check("no supervisor: running false, empty line", status == 200 and not body["running"] and body["line"] == "")
        # a live pulse + one done goal + one open decision
        pulse.Pulse(e.state_dir).write("running", {})
        history.append(e.state_dir, {"goal": "g-1", "from": "running", "to": "done", "cost_usd": 1.25})
        from halo_harness.supervise import decisions
        decisions.park(e.state_dir, "goal_ask", "g-2", "q", "a question", run_dir="/x")
        status, body = get_summary(_Req())
        ctx.check(f"the morning line reads done/waiting/cost, got {body['line']!r}",
                  body["running"] and body["line"] == "1 goal done, 1 waiting on you, $1.25")


@test
def test_end_to_end_a_parked_plan_answered_from_attention(ctx: Ctx):
    """StudioFleetRig: a parked goal_plan decision shows in the Fleet attention queue and Approve writes
    the owner's answer into its decision file (studio/fleet_panels_api + fleet_answer + supervise_attention)."""
    from tests.helpers.studio_fleet_rig import StudioFleetRig
    with StudioFleetRig() as rig:
        from halo_harness.supervise import decisions
        run_dir = rig.state / "orchestra" / "20261021-000000-aaaa"
        run_dir.mkdir(parents=True, exist_ok=True)
        row = decisions.park(rig.state, "goal_plan", "g-abc", "plan", "Goal g-abc: the plan waits for your review",
                             "write the release notes", run_dir=str(run_dir))
        status, body = rig.api("GET", "fleet/attention")
        plan = [r for r in body["rows"] if r["kind"] == "goal_plan"]
        ctx.check(f"the goal_plan row is served, got {[r['kind'] for r in body['rows']]}", len(plan) == 1)
        rid = plan[0]["id"]
        # Open answers with where to open it, sends nothing
        s_open, b_open = rig.api("POST", "fleet/attention/answer", {"id": rid, "key": "o"})
        ctx.check(f"Open points at the run, got {b_open}", s_open == 200 and (b_open.get("open") or {}).get("section") == "orchestra")
        ctx.check("Open did not answer the decision", not decisions.read(rig.state, row["id"]).get("answer"))
        # Approve writes the owner's answer into the decision file
        s_ans, b_ans = rig.api("POST", "fleet/attention/answer", {"id": rid, "key": "a"})
        ctx.check(f"Approve is accepted, got {b_ans}", s_ans == 200 and b_ans.get("ok"))
        saved = decisions.read(rig.state, row["id"])
        ctx.check("the decision file now carries the approve answer", (saved.get("answer") or {}).get("key") == "a")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
