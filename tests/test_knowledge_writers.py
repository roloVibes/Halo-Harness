"""tests.test_knowledge_writers -- Halo 3.1.8.0 R4: findings and decisions are
written where the knowing happens (knowledge/writers.py), through the mock
rigs (a real temp repo, real git and tests, fake workers that leave a
transcript; seeded coach runs; parked supervisor rows):

1. the Orchestra judge's conflict resolution with evidence -> a finding by
   `judge` ("<file>: hunk 1 resolved for lane 2 because <evidence line>"), and
   the gate's final verdict -> a finding by `gate` per lane ("<units> passes
   `<test>` at <sha>"), confidence checked;
2. a lane the gate sent back for a reason -> a decision by `gate` with the
   reason and the alternatives;
3. the coach's Apply -> a decision by `coach` (what changed on which bio, why,
   the Undo id); the Apply's own record is what it was;
4. the owner's answer to a supervisor row -> a decision by `supervisor` (the
   answer and its why, the other answers as alternatives); `o` (open) and a
   goal_ask write nothing;
5. `knowledge.write: false` -> no writer writes anything.
No model call. Run: python -m tests.test_knowledge_writers
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers import outcomes_rig as R  # noqa: E402

ensure_scoped_state_dir_once()
test, TESTS = new_registry()


def _by(role: str, kind: str, state_dir=None) -> list:
    from halo_harness.knowledge.store import entries
    return [e for e in entries(state_dir, kind=kind) if e["by"] == role]


def _config(home: Path, value) -> None:
    path = home / "config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"knowledge": {"write": value}}), encoding="utf-8")


@test
def test_the_judge_and_the_gate_write_findings(ctx: Ctx):
    from halo_harness.orchestra.run import run
    from tests.helpers import orchestra_fixtures as F
    with R.home():
        repo = F.make_repo()
        test = (f"{F.PY} -m unittest -q test_basket.BasketTest.test_apply_discount test_basket.BasketTest.test_total "
                "test_basket.BasketTest.test_subtotal")
        run_dir = F.make_run(repo, workers=2, return_cap=2, test=test)
        worker = R.TranscriptWorker(F.FakeWorker(F.CONFLICT_SOLUTIONS, F.CONFLICT_IMPORTS), {1: ["code-lane"], 2: ["research"]})
        report = run(run_dir, model_calls=F.FakeLead(F.split_answer([["apply_discount"], ["subtotal", "total"]])),
                     spawn=worker, judge=F.FakeJudge())
        judged, gated = _by("judge", "finding"), _by("gate", "finding")
    ctx.check(f"the run finished with a judged conflict, got {report['status']}", report["status"] == "finished")
    j = judged[0] if judged else {}
    ctx.check(f"one judge finding for the file, got {[e['title'] for e in judged]}",
              len(judged) == 1 and j["title"].startswith("basket.py: hunk 1 resolved for lane 2 because "))
    ctx.check(f"because the incoming lane's first line that shows something, got {j.get('title')!r}",
              "because sources: 4 -- search python decimal" in j.get("title", "") and "none run" not in j.get("title", ""))
    ctx.check(f"its evidence: the lanes' lines and the tests after the merge, got {j.get('evidence')}",
              any(ln.startswith("lane 2 (code, incoming): ") for ln in j.get("evidence", []))
              and any(ln.startswith("lane 1 (code, merged): tests: `python -m pytest") for ln in j.get("evidence", []))
              and j["evidence"][-1].startswith("tests: `") and " exit 0" in j["evidence"][-1])
    ctx.check("checked, with the run, the repo and the body", j.get("confidence") == "checked" and j["run"] == run_dir.name
              and j["repo"] == repo.name and j["body"].startswith("What: the fresh judge's answer for hunk 1 of basket.py"))
    sha = str(report.get("finished") or "")[:12]
    titles = sorted(e["title"] for e in gated)
    ctx.check(f"a gate finding per lane, got {titles}", len(gated) == 2 and sha and all(t.endswith(f" at {sha}") for t in titles)
              and titles[0].startswith("basket.py#apply_discount passes `") and titles[1].startswith("basket.py#subtotal, basket.py#total passes `"))
    ctx.check("each checked, by gate, its evidence the gate's test line", all(e["confidence"] == "checked"
              and e["evidence"][0].startswith("tests: `") and "exit 0" in e["evidence"][0] for e in gated))


@test
def test_a_send_back_is_a_decision(ctx: Ctx):
    from halo_harness.orchestra.goal import load_goal
    from halo_harness.orchestra.run import run
    from tests.helpers import orchestra_fixtures as F
    with R.home():
        repo = F.make_repo()
        run_dir = F.make_run(repo, workers=2, return_cap=2)
        worker = R.TranscriptWorker(F.FakeWorker(), {1: ["code-no-tests", "code-lane"], 2: ["code-lane"]})
        report = run(run_dir, model_calls=F.FakeLead(F.split_answer([["add_item", "remove_item", "subtotal"],
                                                                     ["apply_discount", "total"]])),
                     spawn=worker, judge=F.FakeJudge())
        test = load_goal(run_dir / "goal.json").test
        rows = _by("gate", "decision")
    d = rows[0] if rows else {}
    ctx.check(f"the run finished, one gate decision, got {report['status']} {[e['title'] for e in rows]}",
              report["status"] == "finished" and len(rows) == 1)
    ctx.check(f"lane 1 sent back with its reason, said once, got {d.get('title')!r}",
              d.get("title", "").startswith("lane 1 sent back: no test run in this lane's work: run ")
              and "piece back" not in d.get("title", ""))
    ctx.check(f"alternatives and the evidence, got {d.get('alternatives')} {d.get('evidence')}",
              d.get("alternatives") == ["merge the piece as it is", "stop the run"] and d["evidence"][0].startswith("tests: `")
              and "tests: none run" in d["evidence"] and d["confidence"] == "")
    ctx.check("its body says how many times it went back and why", "returned 1 time)" in d["body"]
              and f"Why: The gate sent your piece back: no test run in this lane's work: run {test}." in d["body"])


@test
def test_the_coach_apply_is_a_decision(ctx: Ctx):
    from halo_harness.orchestra import coach_apply as CA
    from halo_harness.orchestra.coach import cached
    from tests.helpers import coach_seed as S
    from tests.test_orchestra_coach import Home
    denied = [{"tool_name": "WebFetch", "reason": "denied by rule 'WebFetch'"}]
    with Home() as h:
        run = S.orchestra_run(h.root, [S.lane(1, bio="coach-deny", denied=denied)])
        row = CA.apply(cached(run, catalog=S.CATALOG, state_dir=h.state), "tools-1-WebFetch", run, state_dir=h.state)
        rows = _by("coach", "decision", h.state)
    d = rows[0] if rows else {}
    ctx.check(f"one coach decision, got {[e['title'] for e in rows]}", len(rows) == 1
              and d["title"].startswith("coach: bio coach-deny tools.deny -> "))
    ctx.check("its body names the file, the why and the Undo id", "(written to coach-deny.yaml)" in d["body"]
              and f"`halo coach --undo {row['apply_id']}`" in d["body"] and "Why: " in d["body"])
    ctx.check("its evidence is the card's why, the run its run", d["evidence"] and d["run"] == S.RUN
              and d["alternatives"] == ["leave it as it was"])
    ctx.check("the Apply's own row is as before", row["op"] == "apply" and row["target"] == "bio" and "entry" in row)


@test
def test_a_supervisor_answer_is_a_decision(ctx: Ctx):
    from halo_harness.supervise import decisions
    state = Path(tempfile.mkdtemp(prefix="know-sup-")) / ".halo"
    run_dir = Path(tempfile.mkdtemp(prefix="know-sup-run-")) / "repo" / ".halo" / "orchestra" / "20261024-090000-c0de"
    row = decisions.park(state, "goal_gate", "g-7", "cap", "Goal g-7: the gate sent a piece back past the return cap",
                         "lane 2 reached the return cap (2)", run_dir=str(run_dir))
    decisions.answer(state, row["id"], "r", "2 -- the flaky test is fixed upstream", by="owner-zed")
    rows = _by("supervisor", "decision", state)
    d = rows[0] if rows else {}
    ctx.check(f"one supervisor decision, got {[e['title'] for e in rows]}", len(rows) == 1 and d["title"] ==
              "Goal g-7: the gate sent a piece back past the return cap -> raise the cap by N")
    ctx.check("the answer and its why", "Why: 2 -- the flaky test is fixed upstream." in d["body"]
              and d["evidence"][0] == "answer: r (raise the cap by N) -- 2 -- the flaky test is fixed upstream")
    ctx.check("the other answers are its alternatives, the run its run", d["alternatives"] ==
              ["raise the cap by 1 and resume", "stop"] and d["run"] == run_dir.name and d["repo"] == "repo")
    ctx.check("never the person who answered", "owner-zed" not in json.dumps({k: v for k, v in d.items() if k != "path"}))
    plan = decisions.park(state, "goal_plan", "g-8", "plan", "Goal g-8: the plan waits for your review", "w")
    decisions.answer(state, plan["id"], "o")
    ask = decisions.park(state, "goal_ask", "g-9", "x", "Goal g-9: a card", "Bash")
    decisions.answer(state, ask["id"], "a")
    ctx.check("`o` and a goal_ask write nothing", len(_by("supervisor", "decision", state)) == 1)


@test
def test_knowledge_write_false_writes_nothing(ctx: Ctx):
    from halo_harness.knowledge import writers as W
    from halo_harness.knowledge.store import entries
    from halo_harness.supervise import decisions
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
    home = Path(tempfile.mkdtemp(prefix="know-off-"))
    os.environ["BRIDGE_TEST_HOME"] = str(home)
    os.environ.pop("BRIDGE_STATE_DIR", None)
    try:
        state = home / ".halo"
        _config(state, False)
        row = decisions.park(state, "goal_budget", "g-1", "cap", "Goal g-1: over the budget", "spent $1")
        decisions.answer(state, row["id"], "a")
        lane = type("L", (), {"n": 1, "pieces_returned": 1, "job": type("J", (), {"title": "t", "claims": ["a.py#f"]})(),
                              "data": lambda self: {}})()
        wrote = W.sent_back(state / "run", lane, "why", None) + W.answered(state, dict(row, answer={"key": "a"}))
        ctx.check(f"knowledge.write false: nothing written, got {entries(state)} {wrote}", entries(state) == [] and wrote == [])
        _config(state, True)
        ctx.check("on again: the same writer writes", len(W.answered(state, dict(row, answer={"key": "a"}))) == 1
                  and W.enabled())
    finally:
        for k, v in saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
