"""halo_harness.studio.design_api_turns -- live design turns for Studio's
Design mode (Halo 3.0.1.0 round D3). One turn per project at a time: it runs
`design.session.run_turn` in a thread, appends every streamed event to the
turn's list, and the page polls `turn/<id>?since=N` every 500 ms until `done`.
"""

from __future__ import annotations

import itertools
import threading

_IDS = itertools.count(1)
_LOCK = threading.Lock()
TURNS: dict = {}       # turn id -> turn
LIVE: dict = {}        # project slug -> the turn id still running


def live_turn(slug: str):
    tid = LIVE.get(slug)
    return tid if tid and tid in TURNS and not TURNS[tid]["done"] else None


def start(project, prompt: str, *, model: str = "", budget=None, runner=None, registered=None, after=None, **turn_kw):
    """Begin a turn; None when this project already has one running. `after(result)`
    returns extra keys for the finished result (a critique's pins); `turn_kw` goes
    to `run_turn` (tools_override, entries, max_turns)."""
    from halo_harness.design import session
    with _LOCK:
        if live_turn(project.slug):
            return None
        tid = f"t{next(_IDS)}"
        turn = {"id": tid, "slug": project.slug, "prompt": prompt, "events": [], "done": False, "result": None}
        TURNS[tid] = turn
        LIVE[project.slug] = tid

    def work() -> None:
        try:
            r = session.run_turn(project, prompt, model=model, on_event=turn["events"].append, max_budget_usd=budget,
                                 registered=registered, runner=runner, **turn_kw)
            turn["result"] = {"code": r["code"], "cost": r["cost"], "text": r["text"], "versions": [list(v) for v in r["versions"]]}
            if after is not None:
                turn["result"].update(after(turn["result"]))
        except Exception as e:  # a failed turn is a result the page can show, not a dead thread
            turn["result"] = {"code": 1, "cost": None, "text": "", "versions": [], "error": f"{type(e).__name__}: {e}"}
        finally:
            turn["done"] = True

    turn["thread"] = threading.Thread(target=work, name=f"halo-design-{tid}", daemon=True)
    turn["thread"].start()
    return turn


def poll(slug: str, tid: str, since: int):
    turn = TURNS.get(tid)
    if turn is None or turn["slug"] != slug:
        return None
    done = turn["done"]  # read before the events so a finished turn never loses its tail
    events = list(turn["events"])
    return {"id": tid, "events": events[since:], "next": len(events), "done": done, "result": turn["result"] if done else None}
