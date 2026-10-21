"""tests.test_supervise_replan_rows -- Halo 3.1.8.0 R2: the replan's rows and
lines. The goal_replan decision kind (supervise/decisions.py) and its attention
row (fleet/supervise_attention.py via fleet/attention.build, studio/fleet_answer,
fleet/push), a replan's goal_plan row, a row whose goal moved on, "replanned N
times" in `halo supervise status`, `halo goal show` and the run report, and
`halo goal add --replan`. No model is called.

Run: python -m tests.test_supervise_replan_rows
"""
from __future__ import annotations

import contextlib
import io
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
EPS = [{"n": 1, "at": NOW - 900, "why": ["returns"], "state": "applied", "settled": NOW - 880},
       {"n": 2, "at": NOW - 500, "why": ["forecast", "blocked"], "state": "rejected", "settled": NOW - 400},
       {"n": 3, "at": NOW - 100, "why": ["stalled"], "state": "dropped"}]


class _Env:
    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
        d = Path(tempfile.mkdtemp(prefix="replan-rows-"))
        os.environ["BRIDGE_TEST_HOME"] = str(d)
        os.environ["BRIDGE_STATE_DIR"] = str(d / ".halo")
        self.state_dir, self.repo = d / ".halo", d / "repo"
        self.state_dir.mkdir(parents=True)
        self.repo.mkdir()
        return self

    def __exit__(self, *exc):
        for k, v in self._saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


def _out(fn, *args) -> "tuple[int, str]":
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = fn(*args)
    return rc, buf.getvalue()


@test
def test_the_goal_replan_kind_and_its_attention_row(ctx: Ctx):
    with _Env() as e:
        from halo_harness.fleet import attention
        from halo_harness.fleet.push import PUSH_KINDS
        from halo_harness.fleet.supervise_attention import open_target
        from halo_harness.studio.fleet_answer import SUPERVISE
        from halo_harness.supervise import decisions
        row = decisions.park(e.state_dir, "goal_replan", "g-9", "replan-1", "Goal g-9: the lead's new plan failed the "
                             "check twice", "job-5 is a lane left and the plan drops it", run_dir="/x/.halo/orchestra/r-1",
                             replan=1)
        ctx.check("goal_replan is a decision kind with a/r/s/o and a text for r",
                  "goal_replan" in decisions.KINDS and set(row["keys"]) == {"a", "r", "s", "o"} and row["text_for"] == "r"
                  and row["keys"]["a"] == "apply the new plan" and row["keys"]["r"] == "keep the old plan")
        rows = attention.build({"harnesses": [{"id": "L", "name": "me", "local": True, "sessions": []}]},
                               home=e.state_dir, now=NOW)
        got = [r for r in rows if r["kind"] == "goal_replan"]
        ctx.check(f"the row is in the attention queue with its own keys, got {[r['kind'] for r in rows]}",
                  len(got) == 1 and set(got[0]["keys"]) == {"a", "r", "s", "o"} and got[0]["target"]["replan"] == 1)
        ctx.check("it is a KEYS / TEXT_FOR / push / answer kind", "goal_replan" in attention.KEYS
                  and attention.TEXT_FOR.get("goal_replan") == "r" and "goal_replan" in PUSH_KINDS and "goal_replan" in SUPERVISE)
        t = open_target(got[0])
        ctx.check(f"Open points at the run, got {t}", t["section"] == "orchestra" and t["run"] == "r-1" and t["goal"] == "g-9")
        saved, why = decisions.answer(e.state_dir, row["id"], "s", by="me")
        ctx.check(f"s is taken (no text needed), got {why!r}", saved is not None and saved["answer"]["key"] == "s")
        plan = decisions.park(e.state_dir, "goal_plan", "g-9", "replan-2", "Goal g-9: a new plan waits", "lane 5: retry",
                              run_dir="/x/.halo/orchestra/r-1", replan=2)
        ctx.check("a replan's review is a goal_plan row naming the replan", plan["kind"] == "goal_plan"
                  and plan["target"]["replan"] == 2 and plan["id"] != row["id"])


@test
def test_studio_serves_and_answers_a_goal_replan_row(ctx: Ctx):
    """StudioFleetRig: GET fleet/attention serves the row with its own keys; r (keep the old plan) with a why
    is written into the decision file for the supervisor."""
    from tests.helpers.studio_fleet_rig import StudioFleetRig
    with StudioFleetRig() as rig:
        from halo_harness.supervise import decisions
        run_dir = rig.state / "orchestra" / "20261021-000000-bbbb"
        run_dir.mkdir(parents=True, exist_ok=True)
        row = decisions.park(rig.state, "goal_replan", "g-def", "replan-1", "Goal g-def: the lead's new plan failed the "
                             "check twice", "job-5 is a lane left and the plan drops it", run_dir=str(run_dir), replan=1)
        status, body = rig.api("GET", "fleet/attention")
        got = [r for r in body["rows"] if r["kind"] == "goal_replan"]
        ctx.check(f"the goal_replan row is served with its keys, got {[r['kind'] for r in body['rows']]}",
                  status == 200 and len(got) == 1 and got[0]["keys"].get("r") == "keep the old plan")
        s_ans, b_ans = rig.api("POST", "fleet/attention/answer", {"id": got[0]["id"], "key": "r", "text": "keep it"})
        saved = decisions.read(rig.state, row["id"]) or {}
        ctx.check(f"r with a why is written into the decision file, got {s_ans} {b_ans}",
                  s_ans == 200 and (saved.get("answer") or {}).get("key") == "r" and saved["answer"]["text"] == "keep it")


@test
def test_a_row_whose_goal_moved_on_changes_nothing(ctx: Ctx):
    with _Env() as e:
        from halo_harness.orchestra import jsonl
        from halo_harness.supervise import apply, decisions, queue
        from halo_harness.supervise.loop import Supervisor
        g = queue.add(e.state_dir, "x", repo=str(e.repo), kind="job")
        rd = e.state_dir / "run"
        rd.mkdir()
        jsonl.write_json(rd / "replan.json", {"n": 1, "state": "review"})
        row = decisions.park(e.state_dir, "goal_plan", g["id"], "replan-1", "w", "d", run_dir=str(rd), replan=1)
        queue.set_state(e.state_dir, g["id"], "running", "resumed by hand")
        decisions.answer(e.state_dir, row["id"], "a", by="me")
        apply.decision(Supervisor(e.state_dir), decisions.read(e.state_dir, row["id"]))
        ctx.check("the row is closed with a note", "moved on" in (decisions.read(e.state_dir, row["id"]).get("note") or ""))
        ctx.check("nothing was applied", jsonl.read_json(rd / "replan.json", {})["state"] == "review"
                  and not (rd / "plan.json").exists() and queue.load(e.state_dir, g["id"])["state"] == "running")


@test
def test_the_replanned_line_in_status_show_and_the_report(ctx: Ctx):
    with _Env() as e:
        from halo_harness.orchestra.report import format_report, replan_line
        from halo_harness.supervise import cli, pulse, queue
        from halo_harness.supervise.goal_cli import cmd_goal
        from halo_harness.supervise.replan_rows import line
        ctx.check("no replans, no line", line({}) == "" and line({"replans": [EPS[2]]}) == "")
        want = "replanned 2 times (returns: applied; forecast+blocked: kept the old plan)"
        ctx.check(f"the line counts the replans that asked, got {line({'replans': EPS})!r}", line({"replans": EPS}) == want)
        g = queue.add(e.state_dir, "write the notes", repo=str(e.repo), kind="job")
        queue.update(e.state_dir, g["id"], lambda goal: goal.update(replans=EPS))
        pulse.Pulse(e.state_dir).write("running", {})
        rc, out = _out(cli._status, e.state_dir, False)
        ctx.check(f"`halo supervise status` prints it per goal, got {out!r}", rc == 0 and f"{g['id']}: {want}" in out)
        rc, out = _out(cmd_goal, ["show", g["id"]])
        ctx.check(f"`halo goal show` prints it, got {out!r}", rc == 0 and want in out)
        rep = {"run_id": "r-1", "status": "finished", "lanes": [], "checks": [],
               "replans": [{"n": 1, "why": ["returns: lane 5 (job-5) was sent back 2 times"], "by": "auto"}]}
        ctx.check(f"the run report's line, got {replan_line(rep)!r}", replan_line(rep) == "replanned 1 time (returns)"
                  and "  replanned 1 time (returns)" in format_report(rep))


@test
def test_halo_goal_add_replan(ctx: Ctx):
    with _Env() as e:
        from halo_harness.supervise import queue
        from halo_harness.supervise.goal_cli import cmd_goal
        rc, _ = _out(cmd_goal, ["add", "ship it", "--repo", str(e.repo), "--as", "job", "--replan", "review"])
        g = queue.all_goals(e.state_dir)[-1]
        ctx.check(f"--replan review is kept on the goal, got {g.get('replan')!r}", rc == 0 and g["replan"] == "review"
                  and g["replans"] == [])
        with contextlib.redirect_stderr(io.StringIO()):
            rc, _ = _out(cmd_goal, ["add", "x", "--repo", str(e.repo), "--replan", "sometimes"])
        ctx.check(f"a value it does not know is a usage error, got {rc}", rc == 2)
        try:
            queue.add(e.state_dir, "x", repo=str(e.repo), kind="job", replan="always")
            ctx.check("queue.add refuses it too", False)
        except ValueError as err:
            ctx.check(f"queue.add refuses it too, got {err}", "--replan" in str(err))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
