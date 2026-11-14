"""tests.helpers.coach_seed -- seeded run folders for the post-run coach (Halo
3.0.9.0 round R3; halo_harness/orchestra/coach.py): an Orchestra run written
file by file (goal.json, run.json, lanes/<n>.json, events.jsonl, merge.json,
report.json), a flow run, a mission folder and a team run, plus a model
catalog (rows as coach_prices.catalog returns them) and the bios the rules
name. No run engine, no model call.
"""
from __future__ import annotations

import json
from pathlib import Path

RUN = "20261017-120000-c0a1"
GOAL = {"what": "Write the five functions of basket.py", "done_when": "the tests pass", "stop_when": "two returns",
        "workers": 3, "files": ["basket.py"], "return_cap": 2, "worker": "subagent", "lead": "main", "lineup": "",
        "test": "python -m unittest", "plan": "auto"}
CATALOG = [{"ref": "or:vendor/cheap", "provider": "openrouter", "price_in_per_m": 0.1},
           {"ref": "or:vendor/strong", "provider": "openrouter", "price_in_per_m": 2.0},
           {"ref": "or:vendor/mid", "provider": "openrouter", "price_in_per_m": 1.0},
           {"ref": "or:vendor/top", "provider": "openrouter", "price_in_per_m": 5.0}]
MODELS_JSON = {"vendor/cheap": {"price_in_per_m": 0.1}, "vendor/strong": {"price_in_per_m": 2.0},
               "vendor/mid": {"price_in_per_m": 1.0}, "vendor/top": {"price_in_per_m": 5.0}}
BIOS = {"coach-cheap": {"models": {"preference": "or:vendor/cheap"}},
        "coach-strong": {"models": {"preference": "or:vendor/strong"}},
        "coach-deny": {"models": {"preference": "or:vendor/strong"}, "tools": {"deny": ["WebFetch", "Agent"]}},
        "coach-allow": {"models": {"preference": "or:vendor/strong"}, "tools": {"allow": ["Read", "Edit"]}}}


def write(path: Path, data) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def lines(path: Path, rows) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


def seed_home(state_dir: Path) -> None:
    """The bios (user scope) and models.json the coach reads."""
    from halo_harness.agents_yaml import save_agent_bio
    state_dir.mkdir(parents=True, exist_ok=True)
    write(state_dir / "models.json", MODELS_JSON)
    for name, bio in BIOS.items():
        ok, problems = save_agent_bio(name, {"description": name, **bio}, state_dir=state_dir)
        assert ok, problems


def lane(n: int, **kw) -> dict:
    key = f"basket.py#f{n}"
    row = {"lane": n, "job": f"job-{n}", "title": f"write f{n}", "claims": [key], "order": n, "state": "merged",
           "holder": f"s{n}/main", "branch": f"orchestra/{RUN}-worker-{n}", "worktree": "", "head": "", "cost_usd": 0.01,
           "started": 1000.0, "ended": 1100.0, "pieces_returned": 0, "session_ids": [], "written": {key: f"def f{n}():\n    return {n}"},
           "error": "", "reply": "done", "history": [], "handoff": {}, "after": [], "base": "", "gave": [], "bio": "",
           "model": "", "denied": []}
    row.update(kw)
    return row


def returned(times: int, how: str = "gate") -> list:
    text = "the gate sent the piece back" if how == "gate" else "piece sent back"
    return [{"state": "waiting", "ts": 1010.0 + i, "elapsed_s": 10.0 + i, "text": f"{text} ({i + 1}/2)"} for i in range(times)]


def event(ts: float, kind: str, text: str, lane=None, **data) -> dict:
    return {"ts": ts, "elapsed_s": ts - 1000.0, "lane": lane, "kind": kind, "text": text, "data": data}


def orchestra_run(root: Path, lanes: list, *, events=(), merge=None, goal=None, status: str = "finished",
                  run: str = RUN) -> Path:
    run_dir = Path(root) / ".halo" / "orchestra" / run
    write(run_dir / "goal.json", dict(GOAL, **(goal or {})))
    write(run_dir / "run.json", {"run_id": run, "created": 1000.0})
    for row in lanes:
        write(run_dir / "lanes" / f"{row['lane']}.json", row)
    lines(run_dir / "events.jsonl", list(events))
    if merge is not None:
        write(run_dir / "merge.json", merge)
    write(run_dir / "split.json", {"jobs": [{"id": r["job"], "title": r["title"], "claims": r["claims"], "worker": r["lane"],
                                             "order": r["lane"]} for r in lanes]})
    write(run_dir / "report.json", {"run_id": run, "status": status, "stop_reason": "", "cost_usd": 0.1,
                                    "lanes": [{"lane": r["lane"], "title": r["title"], "state": r["state"],
                                               "pieces_returned": r["pieces_returned"], "cost_usd": r["cost_usd"]} for r in lanes],
                                    "checks": []})
    return run_dir

