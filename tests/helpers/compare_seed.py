"""tests.helpers.compare_seed -- what Compare reads (Halo 3.4.1.0 R2 "Time"), beside tests/helpers/replay_seed.py's
session (main + a scout that hands back + a fixer that fails, $0.03, 100 s):

- a second session `SID_B`: main on or:mock/glm-5.3 with a reviewer sub-agent, 60 s, $0.012 (main's own $0.004 and
  the reviewer's $0.008 -- the main transcript ALSO carries the reviewer's rolled-up total, which must count once), a
  steer at +30 s, one provider retry, tokens on every call, and an unpriced call on or:mock/free (its cost unknown
  unless `priced`);
- a goal run `RUN` in `<repo>/.halo/orchestra/`: the lead's split on or:mock/lead ($0.01), two lanes (lane 1 on
  or:mock/glm-5.3 merged after one piece sent back, lane 2 failed), the plan reviewed and approved, the report
  "finished", $0.05, 90 s; a fake key in the goal and a lane title, the repo's path in run.json.
No model, no git.
"""
from __future__ import annotations

import json
from pathlib import Path

from tests.helpers.replay_seed import FAKE_KEY, T0

SID_B = "replay0000seed0000000000000002"
RUN = "20261111-090000-ab12"
TB = T0 + 1000.0
TR = T0 + 5000.0


def _lines(path: Path, rows: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def _json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def seed_b(state: Path, priced: bool = False) -> Path:
    folder = state / "sessions" / "seed-proj"
    use = {"input_tokens": 1000, "output_tokens": 200}
    _lines(folder / f"{SID_B}.jsonl", [
        {"type": "meta", "ts": TB, "model": "or:mock/glm-5.3", "title": "ship it, the second way"},
        {"type": "user", "ts": TB + 1, "content": "Ship the basket fix"},
        {"type": "assistant", "ts": TB + 5, "content": [{"type": "tool_use", "id": "a1", "name": "Agent", "input": {"subagent_type": "reviewer", "prompt": "review"}}]},
        {"type": "usage", "ts": TB + 6, "usage": use, "cost_usd": 0.004, "model": "or:mock/glm-5.3", "retries": 1, "status": "ok"},
        {"type": "usage", "ts": TB + 7, "usage": use, "cost_usd": 0.0 if priced else None, "model": "or:mock/free", "status": "ok"},
        {"type": "user", "ts": TB + 30, "kind": "steer", "content": "use the smaller fix"},
        {"type": "usage", "ts": TB + 40, "usage": {"input_tokens": 2000, "output_tokens": 400}, "cost_usd": 0.008, "agent_id": "rev1",
         "model": "or:mock/glm-5.3", "role": "reviewer", "ok": True},
        {"type": "tool_result", "ts": TB + 40, "tool_use_id": "a1", "tool": "Agent", "content": "looks fine"},
        {"type": "assistant", "ts": TB + 60, "content": [{"type": "text", "text": "Shipped."}]}])
    sub = folder / SID_B / "subagents"
    _json(sub / "agent-rev1.meta.json", {"agent_id": "rev1", "type": "reviewer", "role": "reviewer", "lineup": "dev", "model": "or:mock/glm-5.3",
                                         "started": TB + 6, "finished": TB + 39, "status": "completed", "is_error": False, "description": "review"})
    _lines(sub / "agent-rev1.jsonl", [
        {"type": "user", "ts": TB + 6, "content": "review"},
        {"type": "usage", "ts": TB + 20, "usage": {"input_tokens": 2000, "output_tokens": 400}, "cost_usd": 0.008, "model": "or:mock/glm-5.3", "status": "ok"},
        {"type": "assistant", "ts": TB + 38, "content": [{"type": "text", "text": "looks fine"}]}])
    return folder / f"{SID_B}.jsonl"


def _lane(n: int, state: str, model: str, cost: float, t0: float, t1: float, history: list, returned: int = 0) -> dict:
    return {"lane": n, "job": f"job-{n}", "title": f"write f{n}" + (f" {FAKE_KEY}" if n == 2 else ""), "claims": [f"basket.py#f{n}"],
            "order": n, "state": state, "holder": f"s{n}/main", "branch": f"orchestra/{RUN}-worker-{n}", "worktree": "/secret-project/wt",
            "head": "", "cost_usd": cost, "started": t0, "ended": t1, "pieces_returned": returned, "session_ids": [], "written": {},
            "error": "", "reply": "", "history": [{"state": s, "ts": t, "elapsed_s": t - TR, "text": ""} for s, t in history],
            "handoff": {}, "after": [], "base": "", "gave": [], "bio": "", "model": model, "denied": []}


def seed_run(repo: Path) -> Path:
    run = repo / ".halo" / "orchestra" / RUN
    _json(run / "run.json", {"run_id": RUN, "created": TR, "repo_root": str(repo / "secret-project"), "lead_holder": None})
    _json(run / "goal.json", {"what": f"Write the basket functions {FAKE_KEY}", "done_when": "the tests pass", "stop_when": "two returns",
                              "workers": 2, "files": ["basket.py"], "worker": "or:mock/worker", "lead": "or:mock/lead", "plan": "review",
                              "test": "python -m unittest"})
    (run / "events.jsonl").write_text("", encoding="utf-8")
    _json(run / "split.json", {"base": "", "lead_cost_usd": 0.01, "lead_sessions": [], "jobs": []})
    _json(run / "plan.json", {"approved": True, "jobs": [], "ts": TR + 8, "by": "studio"})
    _json(run / "lanes" / "1.json", _lane(1, "merged", "or:mock/glm-5.3", 0.03, TR + 10, TR + 80,
                                          [("joined", TR + 10), ("writing", TR + 12), ("written", TR + 40), ("waiting", TR + 45),
                                           ("writing", TR + 46), ("written", TR + 70), ("merged", TR + 80)], returned=1))
    _json(run / "lanes" / "2.json", _lane(2, "failed", "or:mock/worker", 0.01, TR + 10, TR + 50,
                                          [("joined", TR + 10), ("writing", TR + 15), ("failed", TR + 50)]))
    _json(run / "report.json", {"run_id": RUN, "status": "finished", "stop_reason": "", "tests_ok": True, "cost_usd": 0.05,
                                "elapsed_s": 90.0, "ts": TR + 90, "lanes": [], "checks": []})
    return run
