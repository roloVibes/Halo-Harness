"""halo_harness.studio.team_live -- the team runner Studio drives (Halo 3.0.8.0
R1), the shape of flow_runs.py / orchestra_live.py.

`start(team, run_dir, stage=None, seams=None, publish=None)` runs a
TeamRunner (with `watch`: block_change stages fire as their blocks change)
on a daemon thread until the run is over or idle, so no request thread waits
on a model or a gate. `request(stage)` hands a stage to that live runner
(an inbox the runner's own thread drains between ticks). A second thread
tails the run's events.jsonl every TAIL_S seconds and publishes each line on
Studio's live feed as a `team` frame:

    {session_id: "team:<run>", event: "team",
     data: {action: stage | gate | change | claim, run, kind, stage, text, ts, data, row?}}

`state`, `trigger` and `report` lines are `stage` actions and carry the
stage's board row; `note` lines stay in the file. One live runner per repo.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable, Optional

from halo_harness.team import board as BD

TAIL_S = 0.25
POLL_S = 0.25
ACTIONS = {"state": "stage", "trigger": "stage", "report": "stage", "gate": "gate", "change": "change",
           "claim": "claim"}
_lock = threading.Lock()
_live: dict = {}   # root -> {thread, run, inbox, done}


def live_run(root) -> Optional[str]:
    with _lock:
        cur = _live.get(str(Path(root).resolve()))
        return cur["run"] if cur and cur["thread"].is_alive() else None


def frame_of(run_dir: Path, entry: dict) -> Optional[dict]:
    action = ACTIONS.get(entry.get("kind"))
    if action is None:
        return None
    data = {"action": action, "run": run_dir.name, "kind": entry.get("kind"), "stage": entry.get("stage"),
            "text": entry.get("text"), "ts": entry.get("ts"), "data": entry.get("data") or {}}
    if action == "stage" and entry.get("stage"):
        data["row"] = BD.row(BD.read_board(run_dir), entry["stage"])
    return {"session_id": f"team:{run_dir.name}", "event": "team", "data": data, "turn": None, "agent_id": None,
            "ts": entry.get("ts") or time.time()}


def tail(run_dir: Path, publish: Callable, done: threading.Event, since: int = 0) -> None:
    seen = since
    while True:
        finished = done.is_set()
        for entry in BD.read_events(run_dir, since=seen):
            seen += 1
            frame = frame_of(run_dir, entry)
            if frame is not None:
                try:
                    publish(frame)
                except Exception:
                    pass
        if finished:
            return
        done.wait(TAIL_S)


def _work(team: dict, run_dir: Path, seams: dict, inbox: list, done: threading.Event) -> None:
    from halo_harness.team.run import TeamRunner
    try:
        runner = TeamRunner(team, run_dir, watch=True, cwd=team["root"], **seams)
        runner.adopt()

        def drain():
            with _lock:
                todo, inbox[:] = list(inbox), []
            for sid in todo:
                runner.request(sid, "Studio")

        drain()
        while True:
            runner.loop(until="idle", poll_s=POLL_S, sleep=lambda s: (time.sleep(s), drain()))
            drain()  # a stage handed over as the loop ended runs too
            if not runner.queue:
                break
    except Exception as e:  # the run log says what went wrong; Studio stays up
        try:
            BD.log(run_dir, "note", f"the runner stopped on an error: {type(e).__name__}: {e}",
                   error=f"{type(e).__name__}: {e}")
        except OSError:
            pass
    finally:
        done.set()


def start(team: dict, run_dir, *, stage: Optional[str] = None, seams: Optional[dict] = None,
          publish: Optional[Callable] = None) -> bool:
    """Start the live runner for this repo; False when one is already live (use `request`)."""
    run_dir = Path(run_dir)
    key = str(Path(team["root"]).resolve())
    with _lock:
        cur = _live.get(key)
        if cur and cur["thread"].is_alive():
            return False
        inbox = [stage] if stage else []
        done = threading.Event()
        since = len(BD.read_events(run_dir))
        t = threading.Thread(target=_work, args=(team, run_dir, dict(seams or {}), inbox, done),
                             name=f"halo-team-{run_dir.name}", daemon=True)
        _live[key] = {"thread": t, "run": run_dir.name, "inbox": inbox, "done": done}
    if publish is not None:
        threading.Thread(target=tail, args=(run_dir, publish, done, since), name=f"halo-team-tail-{run_dir.name}",
                         daemon=True).start()
    t.start()
    return True


def request(root, stage: str) -> bool:
    """Hand `stage` to the live runner of this repo; False when none is live."""
    with _lock:
        cur = _live.get(str(Path(root).resolve()))
        if not cur or not cur["thread"].is_alive():
            return False
        cur["inbox"].append(stage)
        return True


def wait(root, timeout: float = 5.0) -> bool:
    """Tests: block until this repo's live runner ends."""
    with _lock:
        cur = _live.get(str(Path(root).resolve()))
    if not cur:
        return True
    cur["thread"].join(timeout)
    return not cur["thread"].is_alive()
