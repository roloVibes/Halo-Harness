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


def flow_run(state_dir: Path, run: str = "20261017-120500-f10a") -> Path:
    """A finished flow whose confirm gate looped three times and whose render was drawn again twice."""
    run_dir = Path(state_dir) / "flows" / "runs" / run
    steps = [{"id": "intake", "kind": "intake", "state": "done"}, {"id": "render", "kind": "render", "state": "done"},
             {"id": "approve", "kind": "confirm", "state": "done"}]
    write(run_dir / "flow.json", {"name": "social-post", "run": run, "created": 1000.0, "status": "finished", "steps": steps,
                                  "cost_usd": 0.2})
    write(run_dir / "steps" / "1.json", {"id": "intake", "kind": "intake", "rounds": 0, "cost_usd": 0.0})
    write(run_dir / "steps" / "2.json", {"id": "render", "kind": "render", "rounds": 3, "cost_usd": 0.1,
                                         "instructions": ["make the sky darker", "the logo is too small"]})
    write(run_dir / "steps" / "3.json", {"id": "approve", "kind": "confirm", "rounds": 3, "cost_usd": 0.0})
    lines(run_dir / "events.jsonl", [])
    write(run_dir / "report.json", {"run": run, "name": "social-post", "status": "finished", "stop_reason": None,
                                    "cost_usd": 0.2, "steps": [{"id": s["id"], "kind": s["kind"], "state": "done",
                                                                "cost_usd": 0.1 if s["id"] == "render" else 0.0} for s in steps]})
    return run_dir


def mission_folder(home: Path, mid: str = "m-20261017-c0a1") -> Path:
    """An ended mission (mission.json, plan.json, report.json, log.jsonl): part 2 sat `asked` for 200 s (the
    median part took 55 s), part 3's edit was refused, part 3's merge conflicted with part 1 in docs/a.md,
    part 4 changed no file, an output the plan named is missing."""
    from halo_harness.fleet import mission as M
    folder = Path(home) / "fleet" / "missions" / mid
    parts = [{"id": "1", "title": "write a", "kind": "repo", "state": "done", "harness_name": "hub", "duration_s": 60.0,
              "files": ["docs/a.md"], "cost_usd": 0.1}, {"id": "2", "title": "write b", "kind": "repo", "state": "done",
              "harness_name": "kali", "duration_s": 50.0, "files": ["docs/b.md"], "cost_usd": 0.1},
             {"id": "3", "title": "fix a", "kind": "repo", "state": "done", "harness_name": "hub", "duration_s": 70.0,
              "files": ["docs/a.md"], "cost_usd": 0.1}, {"id": "4", "title": "check", "kind": "repo", "state": "done",
              "harness_name": "hub", "duration_s": 10.0, "files": [], "cost_usd": 0.0}]
    doc = M.new_doc(mid=mid, goal="Ship the docs", hub={"id": "hub-id", "name": "hub"})
    doc.update(state="done", ended=doc["created"] + 400, parts={p["id"]: dict(M.new_part_state(p), state="done", harness="h-" + p["harness_name"],
               harness_name=p["harness_name"], files=p["files"], cost_usd=p["cost_usd"]) for p in parts})
    write(folder / "mission.json", doc)
    write(folder / "plan.json", {"parts": [{"id": p["id"], "title": p["title"], "kind": "repo", "harness": "h-" + p["harness_name"],
                                            "harness_name": p["harness_name"], "depends_on": [], "outputs": [], "claims": p["files"]}
                                           for p in parts]})
    write(folder / "report.json", {"mission": mid, "state": "done", "cost": {"total_usd": 0.3}, "parts": parts,
                                   "refused": [{"part": "3", "file": "README.md", "tool": "Edit", "harness": "hub", "ts": 5.0}],
                                   "merge": {"merged": ["1", "2", "3"], "conflicts": [{"part": "3", "file": "docs/a.md"}]},
                                   "missing_outputs": ["artifacts/2/cover.png"]})
    lines(folder / "log.jsonl", [{"ts": 100.0, "kind": "part", "part": "2", "state": "asked"},
                                 {"ts": 300.0, "kind": "part", "part": "2", "state": "running"},
                                 {"ts": 350.0, "kind": "part", "part": "2", "state": "done"}])
    return folder


def team_run(root: Path, run: str = "20261017-121000-7ea0") -> Path:
    """A done team run: stage `copy` gated twice (one redo), a write of `site/index.html` refused."""
    run_dir = Path(root) / ".halo" / "team" / run
    write(run_dir / "board.json", {"run": run, "team": "launch", "state": "done", "stages": [
        {"id": "copy", "kind": "agent", "state": "done", "round": 2, "cost_usd": 0.1},
        {"id": "ship", "kind": "agent", "state": "done", "round": 1, "cost_usd": 0.0}]})
    write(run_dir / "run.json", {"run_id": run, "created": 1000.0})
    lines(run_dir / "events.jsonl", [
        {"ts": 1.0, "kind": "gate", "stage": "copy", "text": "waiting at copy (round 1)", "data": {"gate": {"round": 1}}},
        {"ts": 2.0, "kind": "gate", "stage": "copy", "text": "copy: redo -- shorter", "data": {"action": "redo",
                                                                                              "answer": {"text": "shorter"}}},
        {"ts": 3.0, "kind": "gate", "stage": "copy", "text": "waiting at copy (round 2)", "data": {"gate": {"round": 2}}},
        {"ts": 4.0, "kind": "claim", "stage": "ship", "text": "block `site`: `site/index.html` is held by writer",
         "data": {"refused": True, "member": "editor", "key": "site/index.html", "by": "writer"}}])
    return run_dir
