"""halo_harness.fleet.mission_worker -- one mission part, run on this harness
(Halo 3.0.6.0 "Fleet Missions" round R7).

A member receives the fleet command

    run_task {mission, part, title, brief, kind: repo | files, claims: [...], outputs: [...], depends_on: [...],
              repo?, base?, branch, cwd?, budget_usd?, mirror: {mode: hub | shared}}

through fleet/control.py, gated by `fleet.allow_control` like a steer: `ask`
shows its owner the card from `describe` ("<hub> asks to run mission <m>
part <n> here: <title> (claims: ...)"), `none` refuses with the reason,
`all` applies it. `accept` checks the fields, finds the folder the part runs
in and starts it on its own thread (mission_worker_run.py): the reply only
says it started. The hub's own harness runs its parts through `start_local`
(no command, no mirror: the folder is its own). `stop(mission, part)` ends a
part running in this process; a part on another machine is stopped like any
agent (its session's row carries `mission` and `part`).

`BUILD(cwd, home)` -> `(session, run, close)` builds the session
(mission_worker_session.build); tests swap it for a fake.
"""

from __future__ import annotations

import re
import threading
from pathlib import Path
from typing import Callable, Optional

from halo_harness.fleet import mission as M

BUILD: Optional[Callable] = None  # None: mission_worker_session.build
RUNNING: dict = {}  # (mission, part) -> WorkerRun
_lock = threading.Lock()
_PART = re.compile(r"^\d{1,3}$")
_SHA = re.compile(r"^[0-9a-f]{7,64}$")


class TaskError(ValueError):
    pass


def _strs(value, n: int = 200) -> list:
    return [str(v)[:400] for v in value[:n]] if isinstance(value, list) else []


def check(fields: dict) -> dict:
    """The run_task fields, cleaned; TaskError naming the first problem."""
    f = fields if isinstance(fields, dict) else {}
    mid, part = str(f.get("mission") or ""), str(f.get("part") or "")
    if not M.valid_id(mid):
        raise TaskError(f"{mid!r} is not a mission id")
    if not _PART.match(part):
        raise TaskError(f"{part!r} is not a part number")
    kind = str(f.get("kind") or "files")
    if kind not in ("repo", "files"):
        raise TaskError(f"kind is repo or files, got {kind!r}")
    claims = _strs(f.get("claims"))
    from halo_harness.fleet.mission_plan_rules import bad_claim
    bad = next((bad_claim(c) for c in claims if bad_claim(c)), None)
    if bad:
        raise TaskError(bad)
    base = str(f.get("base") or "")
    out = {"mission": mid, "part": part, "title": " ".join(str(f.get("title") or "").split())[:160],
           "brief": str(f.get("brief") or "")[:20000], "kind": kind, "claims": claims, "outputs": _strs(f.get("outputs")),
           "depends_on": _strs(f.get("depends_on")), "repo": str(f.get("repo") or "")[:120] or None,
           "base": base if _SHA.match(base) else None, "branch": f"mission/{mid}/{part}",
           "cwd": Path(str(f.get("cwd") or "")).name or None, "budget_usd": None,
           "mirror": {"mode": str((f.get("mirror") if isinstance(f.get("mirror"), dict) else {}).get("mode") or "hub")}}
    try:
        out["budget_usd"] = float(f["budget_usd"]) if f.get("budget_usd") not in (None, "") else None
    except (TypeError, ValueError):
        raise TaskError("budget_usd is a number of dollars") from None
    if kind == "repo" and not out["repo"]:
        raise TaskError("a repo part names its repo")
    if out["mirror"]["mode"] not in ("hub", "shared", "local"):
        raise TaskError(f"mirror.mode is hub or shared, got {out['mirror']['mode']!r}")
    return out


def describe(fields: dict, hub: str) -> str:
    f = fields if isinstance(fields, dict) else {}
    claims = [str(c) for c in f.get("claims") or []] if isinstance(f.get("claims"), list) else []
    shown = ", ".join(claims[:6]) + (f" +{len(claims) - 6} more" if len(claims) > 6 else "") if claims else "nothing"
    title = " ".join(str(f.get("title") or "").split())[:200]
    return f"{hub} asks to run mission {f.get('mission')} part {f.get('part')} here: {title} (claims: {shown})"


def builder() -> Callable:
    if BUILD is not None:
        return BUILD
    from halo_harness.fleet.mission_worker_session import build
    return build


def _start(run) -> dict:
    key = (run.f["mission"], run.f["part"])
    with _lock:
        cur = RUNNING.get(key)
        if cur is not None and cur.is_alive():
            raise TaskError(f"mission {key[0]} part {key[1]} already runs here")
        RUNNING[key] = run
    run.start()
    return {"started": True, "mission": key[0], "part": key[1], "branch": run.f["branch"] if run.f["kind"] == "repo" else None}


def accept(handle, fields: dict, *, by: str = "", hub: str = "", entry: Optional[dict] = None) -> dict:
    """run_task on a member: check, place, start. Refused (control.py) for anything it cannot run."""
    from halo_harness.fleet import identity
    from halo_harness.fleet.control import Refused
    from halo_harness.fleet.mission_worker_run import WorkerRun
    try:
        f = check(fields)
        run = WorkerRun(f, home=identity.home(), hub=hub, by=by, entry=entry, origin=handle)
        run.place()
        return _start(run)
    except TaskError as e:
        raise Refused(str(e)) from None


def start_local(home, fields: dict, repo_root=None, on_done: Optional[Callable] = None) -> dict:
    """A part on the hub's own harness: same run, the mission folder is already here."""
    from halo_harness.fleet.mission_worker_run import WorkerRun
    f = check({**fields, "mirror": {"mode": "local"}})
    run = WorkerRun(f, home=home, hub="this hub", by="", entry=None, origin=None, repo_root=repo_root, on_done=on_done)
    run.place()
    return _start(run)


def stop(mission: str, part: str, reason: str = "stopped") -> bool:
    with _lock:
        run = RUNNING.get((mission, str(part)))
    if run is None or not run.is_alive():
        return False
    run.stop(reason)
    return True


def running(mission: Optional[str] = None) -> list:
    with _lock:
        return [k for k, r in RUNNING.items() if r.is_alive() and (mission is None or k[0] == mission)]
