"""halo_harness.supervise.drift -- when a supervised Orchestra run drifts
(Halo 3.1.8.0 R2, docs/SUPERVISE.md "Replanning").

`drift(run_dir, cfg, *, now=None, others_usd=0.0) -> list[Drift]` reads the
run folder only (goal.json's `budget_usd`, split.json's plan, forecast.json,
lanes/*.json, events.jsonl, the spend through budget.run_spent) and names
each drift with its number:

    forecast  the live spend + every lane left at its forecast passes the goal's
              `budget_usd` -- or, with `others_usd` (the other goals' spend), the queue's
              `supervise.budget_usd` -- times `supervise.replan_forecast` (1.25 = 25 % over)
    returns   a lane left was sent back `supervise.replan_returns` times (2): by the gate
              or by a merge whose resolution failed the tests
    blocked   a lane left waited on a hand-off (it is `waiting` on its upstreams) or on a
              claim that was refused and never taken since, for `supervise.replan_block_s` (600)
    stalled   a writing lane logged no event for `supervise.replan_stall_s` (900)

A lane LEFT is a lane of the current plan (split.json) whose piece is not
merged; a merged lane and a lane a replan replaced never drift. Pure: no
model is called and nothing is written; tests pass fixture folders and `now`.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from halo_harness.orchestra import jsonl

KINDS = ("forecast", "returns", "blocked", "stalled")
DONE = ("written", "in_review", "merged")   # the lane's worker has nothing more to spend
EPS = 1e-9


@dataclass
class Drift:
    kind: str            # forecast | returns | blocked | stalled
    value: float         # the number measured: dollars, returns, seconds
    limit: float         # the threshold it passed
    text: str
    lane: Optional[int] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def line(self) -> str:
        return f"{self.kind}: {self.text}"


def plan_lanes(run_dir) -> "tuple[dict, dict]":
    """`({lane n: its job in split.json}, {lane n: its lane file})`."""
    run_dir = Path(run_dir)
    split = jsonl.read_json(run_dir / "split.json", {}) or {}
    jobs = {}
    for i, job in enumerate(split.get("jobs") or [], 1):
        if isinstance(job, dict):
            jobs[int(job.get("worker") or i)] = job
    files = {}
    for p in (run_dir / "lanes").glob("*.json"):
        if p.stem.isdigit():
            data = jsonl.read_json(p, {})
            files[int(p.stem)] = data if isinstance(data, dict) else {}
    return jobs, files


def lanes_left(jobs: dict, files: dict) -> list:
    """The plan's lanes whose piece is not merged (and that no replan replaced)."""
    return [n for n in sorted(jobs) if files.get(n, {}).get("state") != "merged" and not files.get(n, {}).get("replaced")]


def drift(run_dir, cfg: dict, *, now: Optional[float] = None, others_usd: float = 0.0) -> list:
    run_dir = Path(run_dir)
    now = time.time() if now is None else float(now)
    jobs, files = plan_lanes(run_dir)
    left = lanes_left(jobs, files)
    if not left:
        return []
    events = jsonl.read_lines(run_dir / "events.jsonl")
    out = forecast_drift(run_dir, cfg, left, files, others_usd)
    for n in left:
        lane, job = files.get(n, {}), jobs[n]
        name = f"lane {n} ({job.get('id') or f'job-{n}'})"
        returned = int(lane.get("pieces_returned") or 0)
        if returned >= int(cfg["replan_returns"]):
            out.append(Drift("returns", returned, int(cfg["replan_returns"]),
                             f"{name} was sent back {returned} times (supervise.replan_returns {cfg['replan_returns']})", n))
        blocked = _blocked(lane, job, n, events, now)
        if blocked and blocked[0] > float(cfg["replan_block_s"]):
            out.append(Drift("blocked", round(blocked[0], 1), float(cfg["replan_block_s"]),
                             f"{name} waited {blocked[0]:.0f}s on {blocked[1]} (supervise.replan_block_s "
                             f"{cfg['replan_block_s']:g})", n))
        if lane.get("state") == "writing":
            quiet = now - _last_seen(lane, n, events)
            if quiet > float(cfg["replan_stall_s"]):
                out.append(Drift("stalled", round(quiet, 1), float(cfg["replan_stall_s"]),
                                 f"{name} logged nothing for {quiet:.0f}s while writing (supervise.replan_stall_s "
                                 f"{cfg['replan_stall_s']:g})", n))
    return out


def forecast_drift(run_dir, cfg: dict, left: list, files: dict, others_usd: float = 0.0) -> list:
    from halo_harness.orchestra import forecast
    from halo_harness.supervise.budget import run_spent
    goal = jsonl.read_json(Path(run_dir) / "goal.json", {}) or {}
    fc = {int(x.get("lane") or 0): float(x.get("usd") or 0.0) for x in (forecast.read(run_dir) or {}).get("lanes") or []}
    spent = run_spent(run_dir)
    ahead = sum(max(0.0, fc.get(n, 0.0) - float(files.get(n, {}).get("cost_usd") or 0.0))
                for n in left if files.get(n, {}).get("state") not in DONE)
    projected, factor, out = round(spent + ahead, 6), float(cfg["replan_forecast"]), []
    caps = [("the goal's cap", goal.get("budget_usd"), projected)]
    if cfg.get("budget_usd") is not None:
        caps.append(("the queue's cap (supervise.budget_usd)", cfg["budget_usd"], round(projected + others_usd, 6)))
    for label, cap, total in caps:
        if cap is None or isinstance(cap, bool) or total <= float(cap) * factor + EPS:
            continue
        cap = float(cap)
        times = f"{total / cap:.2f}x " if cap > 0 else ""
        extra = f" + the other goals' ${others_usd:.4f}" if total != projected else ""
        out.append(Drift("forecast", total, round(cap * factor, 6),
                         f"spent ${spent:.4f} + the lanes left at their forecast ${ahead:.4f}{extra} = ${total:.4f}, "
                         f"{times}{label} ${cap:.4f} (supervise.replan_forecast {factor:g})"))
    return out


def _waiting_since(lane: dict) -> Optional[float]:
    """When the lane's trailing run of `waiting` history rows began."""
    since = None
    for row in reversed(lane.get("history") or []):
        if row.get("state") != "waiting":
            break
        since = float(row.get("ts") or 0.0)
    return since


def _blocked(lane: dict, job: dict, n: int, events: list, now: float) -> "Optional[tuple[float, str]]":
    """`(seconds, on what)` the lane has been blocked, or None."""
    ups = list(lane.get("after") or job.get("after") or [])
    ups += [str(x.get("from")) for x in ((job.get("handoff") or {}).get("needs") or []) if isinstance(x, dict)]
    if lane.get("state") == "waiting" and ups:
        since = _waiting_since(lane)
        if since is not None:
            return now - since, "a hand-off from " + ", ".join(dict.fromkeys(ups))
    if lane.get("state") != "writing" or job.get("assist"):  # an assist lane is refused its claims by design
        return None
    holder = str(lane.get("holder") or "")
    pending: dict = {}
    for e in events:
        d = e.get("data") or {}
        if e.get("kind") != "claim":
            continue
        if d.get("op") == "refused" and (d.get("lane_n") == n or (holder and d.get("holder") == holder)):
            pending.setdefault((d.get("holder"), d.get("key")), (float(e.get("ts") or 0.0), d.get("by") or "another holder"))
        elif d.get("op") in ("claim", "steal", "reassign"):
            pending.pop((d.get("holder"), d.get("key")), None)
    if not pending:
        return None
    (_who, key), (ts, by) = min(pending.items(), key=lambda kv: kv[1][0])
    return now - ts, f"a claim on {key} (held by {by})"


def _last_seen(lane: dict, n: int, events: list) -> float:
    holder = str(lane.get("holder") or "")
    last = max([float(r.get("ts") or 0.0) for r in lane.get("history") or []] + [float(lane.get("started") or 0.0)])
    for e in events:
        d = e.get("data") or {}
        if e.get("lane") == n or d.get("lane_n") == n or (holder and d.get("holder") == holder):
            last = max(last, float(e.get("ts") or 0.0))
    return last


def lines(drifts: list) -> list:
    return [d.line for d in drifts]


def kinds(drifts: list) -> list:
    return list(dict.fromkeys(d.kind for d in drifts))
