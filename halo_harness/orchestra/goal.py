"""halo_harness.orchestra.goal -- goal.json and the run folder.

A goal says WHAT YOU WANT (`what`), DONE WHEN (`done_when`) and STOP WHEN
(`stop_when`), plus how many workers (`workers`, 1..50), how many times the
gate may send a piece back (`return_cap`), the test command (`test`) and its
timeout (`test_timeout_s`, default 600), the
files the workers share (`files`, relative to the repo root), and who plays
the parts (`lineup`, `lead`, `worker`), and optionally the lanes' hand-offs
(`handoffs`: `{job id: {gives, needs, after}}`, orchestra/handoff_spec.py),
and whether the run pauses for the plan's review (`plan`: `auto` | `review`,
3.0.9.0 R2, orchestra/plan.py).

A run lives in `<repo>/.halo/orchestra/<run-id>/` (`run-id` =
`YYYYMMDD-HHMMSS-<4 hex>`, so names sort by time):

    run.json        {"run_id", "created", "repo_root", "lead_holder"}
    goal.json       the Goal
    workflow.json   workflow.designed_graph(goal.workers)
    events.jsonl    the timed log (orchestra/events.py)
    claims.jsonl    the claim log (orchestra/claims.py), created on first claim
"""

from __future__ import annotations

import secrets
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from halo_harness.orchestra import jsonl
from halo_harness.orchestra.workflow import MAX_WORKERS, designed_graph

TEXT_FIELDS = ("what", "done_when", "stop_when")
_LABELS = {"what": "WHAT YOU WANT", "done_when": "DONE WHEN", "stop_when": "STOP WHEN"}
RUNS_DIR = (".halo", "orchestra")


@dataclass
class Goal:
    what: str = ""
    done_when: str = ""
    stop_when: str = ""
    workers: int = 5
    return_cap: int = 2
    test: str = ""
    test_timeout_s: int = 600
    files: list = field(default_factory=list)
    lineup: str = ""
    lead: str = "main"
    worker: str = "subagent"
    handoffs: dict = field(default_factory=dict)  # 3.0.9.0: {job id: {gives, needs, after}} (handoff_spec.py)
    plan: str = "auto"  # 3.0.9.0 R2: "review" pauses after the split for the edited plan (orchestra/plan.py)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Goal":
        """Known keys only; missing ones take the defaults. No validation here."""
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        goal = cls(**known)
        goal.files = list(goal.files) if isinstance(goal.files, (list, tuple)) else goal.files
        goal.handoffs = dict(goal.handoffs) if isinstance(goal.handoffs, dict) else {}
        return goal


def validate_goal(data) -> list:
    """One plain sentence per problem; [] means valid. Accepts a Goal or a dict."""
    if isinstance(data, Goal):
        data = data.to_dict()
    if not isinstance(data, dict):
        return ["goal must be a JSON object"]
    problems = []
    for key in TEXT_FIELDS:
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            problems.append(f'"{key}" ({_LABELS[key]}) is required: one or more sentences')
    workers = data.get("workers", 5)
    if isinstance(workers, bool) or not isinstance(workers, int) or not 1 <= workers <= MAX_WORKERS:
        problems.append(f'"workers" must be a whole number from 1 to {MAX_WORKERS}, got {workers!r}')
    cap = data.get("return_cap", 2)
    if isinstance(cap, bool) or not isinstance(cap, int) or cap < 0:
        problems.append(f'"return_cap" must be a whole number 0 or more, got {cap!r}')
    timeout = data.get("test_timeout_s", 600)
    if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout < 1:
        problems.append(f'"test_timeout_s" must be a whole number of seconds, 1 or more, got {timeout!r}')
    if data.get("plan", "auto") not in ("auto", "review"):
        problems.append('"plan" is auto (run the split as the lead wrote it) or review (wait for the edited plan), '
                        f'got {data.get("plan")!r}')
    for key in ("test", "lineup", "lead", "worker"):
        value = data.get(key, "")
        if value is not None and not isinstance(value, str):
            problems.append(f'"{key}" must be a string')
    files = data.get("files", [])
    if not isinstance(files, list):
        problems.append('"files" must be a list of paths relative to the repo root')
    else:
        for i, f in enumerate(files):
            if not isinstance(f, str) or not f.strip():
                problems.append(f'files[{i}] must be a non-empty path')
            elif _outside(f):
                problems.append(f'files[{i}] ({f!r}) must be relative to the repo root, inside it')
    handoffs = data.get("handoffs", {})
    if handoffs is not None and not isinstance(handoffs, dict):
        problems.append('"handoffs" must map a job id (job-1, job-2, ...) to {gives, needs, after}')
    else:
        from halo_harness.orchestra.handoff_spec import shape_problems
        for jid, decl in (handoffs or {}).items():
            problems += shape_problems(decl, f"handoffs[{jid}]")
    unknown = sorted(k for k in data if k not in Goal.__dataclass_fields__)
    if unknown:
        problems.append("unknown field(s): " + ", ".join(unknown))
    return problems


def _outside(f: str) -> bool:
    """An absolute path (POSIX, Windows drive or UNC) or one that climbs out with `..`."""
    p = f.replace("\\", "/")
    return (p.startswith("/") or (len(p) > 1 and p[1] == ":") or p == ".." or p.startswith("../")
            or "/../" in p or p.endswith("/.."))


def load_goal(path) -> Goal:
    """Read and validate goal.json. Raises ValueError naming every problem."""
    data = jsonl.read_json(path, None)
    if data is None:
        raise ValueError(f"{path}: missing or not valid JSON")
    problems = validate_goal(data)
    if problems:
        raise ValueError(f"{path}: " + "; ".join(problems))
    return Goal.from_dict(data)


def save_goal(goal: Goal, path) -> Path:
    """Write goal.json whole (temp file + replace). Returns the path."""
    jsonl.write_json(path, goal.to_dict())
    return Path(path)


def norm_file(path: str) -> str:
    """A goal file entry in the one form keys use: forward slashes, no `./`."""
    p = str(path).replace("\\", "/").strip()
    while p.startswith("./"):
        p = p[2:]
    return p


def runs_root(repo_root) -> Path:
    return Path(repo_root).joinpath(*RUNS_DIR)


def new_run_id(now: Optional[float] = None) -> str:
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(time.time() if now is None else now))
    return f"{stamp}-{secrets.token_hex(2)}"


def new_run(repo_root, goal: Goal, *, lead_holder: Optional[str] = None) -> Path:
    """Create `<repo>/.halo/orchestra/<run-id>/` with run.json, goal.json, an
    empty events.jsonl and workflow.json. Raises ValueError for an invalid goal."""
    problems = validate_goal(goal)
    if problems:
        raise ValueError("; ".join(problems))
    goal = Goal.from_dict(goal.to_dict())
    goal.files = [norm_file(f) for f in goal.files]
    root = runs_root(repo_root)
    root.mkdir(parents=True, exist_ok=True)
    ignore = root / ".gitignore"
    if not ignore.exists():
        ignore.write_text("# Orchestra run state: never committed, never merged.\n*\n", encoding="utf-8")
    while True:
        run_dir = root / new_run_id()
        try:
            run_dir.mkdir()
            break
        except FileExistsError:
            continue
    created = time.time()
    jsonl.write_json(run_dir / "run.json", {"run_id": run_dir.name, "created": created,
                                            "repo_root": str(Path(repo_root).resolve()),
                                            "lead_holder": lead_holder})
    save_goal(goal, run_dir / "goal.json")
    (run_dir / "events.jsonl").write_text("", encoding="utf-8")
    jsonl.write_json(run_dir / "workflow.json", designed_graph(goal.workers))
    return run_dir


def run_meta(run_dir) -> dict:
    """run.json as a dict ({} when missing)."""
    data = jsonl.read_json(Path(run_dir) / "run.json", {})
    return data if isinstance(data, dict) else {}


def repo_root_of(run_dir) -> Path:
    """The repo a run belongs to: run.json's `repo_root`, else three levels up."""
    root = run_meta(run_dir).get("repo_root")
    return Path(root) if root else Path(run_dir).resolve().parents[2]


def set_lead_holder(run_dir, holder: str) -> None:
    """Record which holder (`<session_id>/<agent_id>`) is the run's lead."""
    meta = run_meta(run_dir)
    meta["lead_holder"] = holder
    jsonl.write_json(Path(run_dir) / "run.json", meta)


def list_runs(repo_root) -> list:
    """Every run folder of this repo, oldest first (names sort by time)."""
    root = runs_root(repo_root)
    try:
        return sorted(p for p in root.iterdir() if p.is_dir() and (p / "goal.json").is_file())
    except OSError:
        return []


def latest_run(repo_root) -> Optional[Path]:
    runs = list_runs(repo_root)
    return runs[-1] if runs else None


def resolve_run(repo_root, name: Optional[str] = None) -> Optional[Path]:
    """A run by id, by unique id prefix, or by path; the latest when `name` is empty."""
    if not name:
        return latest_run(repo_root)
    as_path = Path(name)
    if as_path.is_dir() and (as_path / "goal.json").is_file():
        return as_path
    matches = [p for p in list_runs(repo_root) if p.name == name or p.name.startswith(name)]
    return matches[0] if len(matches) == 1 else None
