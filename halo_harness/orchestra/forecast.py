"""halo_harness.orchestra.forecast -- the cost forecast of an Orchestra plan
(Halo 3.1.2.0 R2, docs/ORCHESTRA.md "The forecast"; the shapes and the
pricing are work/forecast.py's).

For a plan (the lead's jobs, Studio's draft or an approved plan.json) one
line per lane and a total against the goal's `budget_usd`:

    <run>/forecast.json   {"run_id", "lanes": [{lane, job, model, tokens_in, tokens_out, usd, usd_low, usd_high,
                           source, priced}], "total": {usd, usd_low, usd_high, budget_usd, over, unpriced, units},
                           "heuristic": "...", "ts"}

The tokens: a job's `est_tokens` when the lead gave one (`{"in": n, "out":
n}`, or one number: 80% in, 20% out); else this heuristic, from the goal's
size and the claimed files (4 characters to a token):

    tokens_in  = 6000 (the worker's prompt, its rules and the tool schemas)
                 + the goal's WHAT / DONE WHEN / STOP WHEN / 4
                 + 3 x the bytes of every file the lane claims in, each once / 4   (it reads them a few times)
    tokens_out = 800 + 3 x the bytes of the units it claims / 4                    (it rewrites each unit about 3 times)

The lane's model: the job's `model`, else its bio's `models.preference`,
else the model of the goal's worker role (the same order as the coach's
lane facts). `for_goal` forecasts a goal before any split (a team's
orchestra stage): `workers` lanes sharing the goal's files equally.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from halo_harness.orchestra import jsonl
from halo_harness.work import forecast as F

PATH = "forecast.json"
BASE_IN, BASE_OUT, READS, WRITES, CHARS = 6000, 800, 3, 3, 4
HEURISTIC = ("tokens_in = 6000 + goal chars/4 + 3 x claimed files' bytes/4; tokens_out = 800 + 3 x claimed units' "
             "bytes/4; priced at the lane model's catalog price")


def est_tokens(raw) -> "Optional[tuple[int, int]]":
    """The lead's estimate as `(in, out)`, or None when it gave none (or nothing usable)."""
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)) and raw > 0:
        return int(raw * 0.8), int(raw * 0.2)
    if isinstance(raw, dict):
        t_in, t_out = raw.get("in"), raw.get("out")
        if all(isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0 for v in (t_in, t_out)) and t_in + t_out > 0:
            return int(t_in), int(t_out)
    return None


def est_dict(raw) -> dict:
    """The estimate as a job keeps it (`{"in", "out"}`), {} for none."""
    got = est_tokens(raw)
    return {"in": got[0], "out": got[1]} if got else {}


def _goal_chars(goal) -> int:
    g = goal if isinstance(goal, dict) else goal.to_dict()
    return sum(len(str(g.get(k) or "")) for k in ("what", "done_when", "stop_when"))


def _file_bytes(root: Path, rel: str, cache: dict) -> int:
    if rel not in cache:
        try:
            cache[rel] = (root / rel).stat().st_size
        except OSError:
            cache[rel] = 0
    return cache[rel]


def _unit_bytes(root: Path, key: str, cache: dict) -> int:
    rel, _, name = key.partition("#")
    if not name:
        return _file_bytes(root, rel, cache)
    if ("units", rel) not in cache:
        from halo_harness.orchestra.index import index_file
        try:
            text = (root / rel).read_text(encoding="utf-8", errors="replace").split("\n")
            cache[("units", rel)] = {u.key: sum(len(x) + 1 for x in text[u.start_line - 1:u.end_line])
                                     for u in index_file(root / rel, root=root)}
        except (OSError, ValueError, SyntaxError):
            cache[("units", rel)] = {}
    return cache[("units", rel)].get(key, 0)


def heuristic(goal, claims: list, root, cache: Optional[dict] = None) -> "tuple[int, int]":
    """`(tokens_in, tokens_out)` from the goal's size and the claimed files (the module docstring's rule)."""
    cache = {} if cache is None else cache
    root = Path(root)
    files = list(dict.fromkeys(str(k).split("#", 1)[0] for k in claims))
    t_in = BASE_IN + _goal_chars(goal) // CHARS + READS * sum(_file_bytes(root, f, cache) for f in files) // CHARS
    t_out = BASE_OUT + WRITES * sum(_unit_bytes(root, str(k), cache) for k in claims) // CHARS
    return int(t_in), int(t_out)


def lane_model(job: dict, goal, cwd=None, state_dir=None) -> str:
    from halo_harness.orchestra.coach_lane_facts import _bio_model, _role_model
    g = goal if isinstance(goal, dict) else goal.to_dict()
    return str(job.get("model") or _bio_model(str(job.get("bio") or ""), cwd, state_dir)
               or _role_model(str(g.get("worker") or "subagent")) or "")


def for_jobs(jobs: list, goal, root, *, rows: Optional[list] = None, state_dir=None) -> dict:
    """`{lanes, total, heuristic}` for `jobs` (split.json's shape) of `goal` in repo `root`."""
    if rows is None:
        from halo_harness.orchestra.coach_prices import catalog
        rows = catalog(state_dir)
    cache: dict = {}
    lanes = []
    for i, job in enumerate(j for j in jobs if isinstance(j, dict)):
        est = est_tokens(job.get("est_tokens"))
        t_in, t_out = est if est else heuristic(goal, list(job.get("claims") or []), root, cache)
        x = F.line(str(job.get("id") or f"job-{i + 1}"), lane_model(job, goal, root, state_dir), t_in, t_out,
                   "lead" if est else "heuristic", rows)
        lanes.append(dict(x, lane=int(job.get("worker") or i + 1), job=x["unit"]))
    g = goal if isinstance(goal, dict) else goal.to_dict()
    return {"lanes": lanes, "total": F.total(lanes, g.get("budget_usd")), "heuristic": HEURISTIC}


def for_run(run_dir, jobs: Optional[list] = None, *, rows: Optional[list] = None, state_dir=None) -> dict:
    """The forecast of a run's plan: `jobs`, else the plan the editor opens (draft, else split.json)."""
    from halo_harness.orchestra import plan as P
    from halo_harness.orchestra.goal import load_goal, repo_root_of
    run_dir = Path(run_dir)
    jobs = P.current_jobs(run_dir) if jobs is None else jobs
    out = for_jobs(jobs, load_goal(run_dir / "goal.json"), repo_root_of(run_dir), rows=rows, state_dir=state_dir)
    return dict(out, run_id=run_dir.name)


def write(run_dir, jobs: Optional[list] = None, *, rows: Optional[list] = None, state_dir=None) -> dict:
    """forecast.json beside split.json (the plan's forecast as it stands); the forecast."""
    out = dict(for_run(run_dir, jobs, rows=rows, state_dir=state_dir), ts=round(time.time(), 3))
    jsonl.write_json(Path(run_dir) / PATH, out)
    return out


def write_quietly(run_dir, jobs: Optional[list] = None) -> Optional[dict]:
    """`write` for the runner: a forecast that cannot be made never stops a run."""
    try:
        return write(run_dir, jobs)
    except Exception:
        return None


def read(run_dir) -> Optional[dict]:
    data = jsonl.read_json(Path(run_dir) / PATH, None)
    return data if isinstance(data, dict) else None


def for_goal(goal: dict, root, *, rows: Optional[list] = None, state_dir=None) -> dict:
    """Before any split (a team's orchestra stage): `workers` lanes, the goal's files shared equally."""
    workers = max(1, int(goal.get("workers") or 1))
    files = [str(f) for f in goal.get("files") or []]
    jobs = [{"id": f"job-{i + 1}", "worker": i + 1, "claims": files[i::workers]} for i in range(workers)]
    return for_jobs(jobs, goal, root, rows=rows, state_dir=state_dir)


def warning(forecast: dict) -> str:
    """The line Approve shows when the forecast is over the budget ('' when it is not)."""
    t = forecast.get("total") or {}
    return f"the {F.words(t)} (Approve runs it anyway; raise budget_usd in goal.json or trim the plan)" \
        if t.get("over") else ""
