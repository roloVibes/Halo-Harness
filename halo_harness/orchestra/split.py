"""halo_harness.orchestra.split -- the lead's split: one job per worker.

The lead answers ONE model call (`call_model(prompt) -> str`, or
`(str, cost_usd)`) with JSON:

    {"jobs": [{"title": "...", "claims": ["basket.py#add_item", ...]}, ...]}

or `{"stop": "<reason>"}` when STOP WHEN already applies. Code checks the
answer: every claim key exists in the index of the goal's files, no key (or
an overlapping key) is in two jobs, every job has a title and at least one
key, and there are at most `goal.workers` jobs (fewer is fine). A failed
check retries the call once with the problems listed; a second failure
stops the run with the reason.

The result is `<run>/split.json`:

    {"base": "<sha>", "lead_cost_usd": 0.0012, "lead_sessions": ["<session id>"],
     "jobs": [{"id": "job-1", "title", "claims", "worker": 1, "order": 1}]}

and one `claim` per key under the placeholder holder `lane:<n>` (a long
TTL), which the lane's worker takes over when it joins
(`ClaimLog.reassign`, called by the lead's code in workers.join_lane).
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Optional

from halo_harness.orchestra import events as run_events
from halo_harness.orchestra import jsonl
from halo_harness.orchestra.claims import ClaimLog
from halo_harness.orchestra.index import overlaps

PLACEHOLDER_TTL_S = 7 * 24 * 3600


class StopRun(Exception):
    """The run stops here; `str(e)` is the reason the report shows."""


@dataclass
class Job:
    id: str
    title: str
    claims: list = field(default_factory=list)
    worker: int = 0
    order: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Job":
        return cls(id=str(data.get("id") or ""), title=str(data.get("title") or ""),
                   claims=list(data.get("claims") or []), worker=int(data.get("worker") or 0),
                   order=int(data.get("order") or data.get("worker") or 0))


def placeholder(lane: int) -> str:
    return f"lane:{int(lane)}"


def split_prompt(goal, units: list, problems: Optional[list] = None) -> str:
    rows = "\n".join(f"  {u.key}  ({u.kind}, lines {u.start_line}-{u.end_line})" for u in units)
    text = (
        "You are the lead orchestrator. Split this goal into jobs, one job per worker.\n\n"
        f"WHAT YOU WANT: {goal.what}\nDONE WHEN: {goal.done_when}\nSTOP WHEN: {goal.stop_when}\n\n"
        f"Workers available: {goal.workers} (use fewer when the goal has fewer independent parts).\n"
        f"Claimable units of the shared files (key, kind, lines):\n{rows}\n\n"
        "Each job claims the SMALLEST units its worker edits; two jobs never share or overlap a unit "
        "(a whole-file key overlaps every unit of that file). Answer with JSON only:\n"
        '{"jobs": [{"title": "one line", "claims": ["file#unit", ...]}]}\n'
        'If STOP WHEN already applies, answer {"stop": "the reason"} instead.'
    )
    if problems:
        text += "\n\nYour previous answer had these problems; fix every one:\n" + "\n".join(
            f"- {p}" for p in problems)
    return text


def parse_answer(text: str):
    """The JSON object in the model's answer (a ```json fence or the first
    {...} span), or None."""
    text = str(text or "")
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    candidates = [fence.group(1)] if fence else []
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        candidates.append(text[start:end + 1])
    for raw in candidates:
        try:
            data = json.loads(raw)
        except ValueError:
            continue
        if isinstance(data, dict):
            return data
    return None


def validate_jobs(data, unit_keys: list, workers: int) -> list:
    """Plain problems with a parsed answer; [] means the jobs are usable."""
    if not isinstance(data, dict):
        return ['the answer is not a JSON object like {"jobs": [...]}']
    jobs = data.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        return ['"jobs" must be a non-empty list']
    problems = []
    if len(jobs) > workers:
        problems.append(f"{len(jobs)} jobs, but only {workers} worker(s): give at most {workers} jobs")
    known = set(unit_keys)
    seen: dict = {}
    for i, job in enumerate(jobs, 1):
        if not isinstance(job, dict):
            problems.append(f"job {i} is not an object with a title and claims")
            continue
        if not str(job.get("title") or "").strip():
            problems.append(f"job {i} has no title")
        claims = job.get("claims")
        if not isinstance(claims, list) or not claims:
            problems.append(f"job {i} claims nothing: give it at least one key")
            continue
        for key in claims:
            if not isinstance(key, str) or key not in known:
                problems.append(f"job {i}: {key!r} is not a key of the goal's files")
                continue
            for other_key, other_job in seen.items():
                if other_job != i and overlaps(other_key, key):
                    same = "is" if other_key == key else f"overlaps {other_key!r},"
                    problems.append(f"job {i}: {key!r} {same} already in job {other_job}")
            seen.setdefault(key, i)
    return problems


def _call(call_model: Callable, prompt: str) -> tuple:
    answer = call_model(prompt)
    if isinstance(answer, tuple):
        return str(answer[0] or ""), float(answer[1] or 0.0), None
    if isinstance(answer, dict):
        return str(answer.get("text") or ""), float(answer.get("cost_usd") or 0.0), answer.get("session_id")
    return str(answer or ""), 0.0, None


def split_goal(run_dir, goal, units: list, *, call_model: Callable, base: str = "",
               lead_holder: str = "") -> list:
    """Ask the lead once (retry once with the problems), validate, write
    split.json and take the placeholder claims. Returns the Jobs; raises
    StopRun with the reason when the lead stops or both answers fail."""
    run_dir = Path(run_dir)
    keys = [u.key for u in units]
    cost = 0.0
    sessions: list = []
    problems: list = []
    data = None
    for attempt in (1, 2):
        text, spent, sid = _call(call_model, split_prompt(goal, units, problems if attempt == 2 else None))
        cost += spent
        sessions += [sid] if sid else []
        data = parse_answer(text)
        if isinstance(data, dict) and str(data.get("stop") or "").strip():
            raise StopRun(f"the lead stopped the run: {str(data['stop']).strip()}")
        problems = validate_jobs(data, keys, goal.workers)
        if not problems:
            break
        run_events.log(run_dir, "state", f"split answer {attempt} rejected: " + "; ".join(problems),
                       step="split", attempt=attempt, problems=problems)
    if problems:
        raise StopRun("the lead's split failed the check twice: " + "; ".join(problems))
    jobs = []
    for i, raw in enumerate(data["jobs"], 1):
        order = raw.get("order")
        order = order if isinstance(order, int) and not isinstance(order, bool) else i
        jobs.append(Job(id=f"job-{i}", title=str(raw["title"]).strip(), claims=list(raw["claims"]),
                        worker=i, order=order))
    jsonl.write_json(run_dir / "split.json", {"base": base, "lead_cost_usd": round(cost, 6), "lead_sessions": sessions,
                                             "jobs": [j.to_dict() for j in jobs]})
    log = ClaimLog(run_dir)
    for job in jobs:
        for key in job.claims:
            log.claim(placeholder(job.worker), key, ttl_s=PLACEHOLDER_TTL_S, note=f"{job.id}: {job.title}")
    run_events.log(run_dir, "state", f"split into {len(jobs)} job(s)", step="split", jobs=len(jobs),
                   lead=lead_holder or None)
    return jobs


def load_split(run_dir) -> Optional[dict]:
    """split.json when it is there and lists jobs, else None."""
    data = jsonl.read_json(Path(run_dir) / "split.json", None)
    if isinstance(data, dict) and isinstance(data.get("jobs"), list) and data["jobs"]:
        return data
    return None


def load_jobs(run_dir) -> list:
    data = load_split(run_dir)
    return [Job.from_dict(j) for j in data["jobs"]] if data else []
