"""halo_harness.studio.design_turns -- live design turns for Studio's
Design mode (Halo 3.0.1.0 round D3; 3.1.0.0 R2 renamed it from
design_api_turns.py). One turn per project at a time: it runs
`design.session.run_turn` in a thread and appends every streamed event to the
turn's list. 3.0.7.0 R3: every step is also a `design_turn` frame on the live
feed (`session_id: "design:<slug>"`, data `{slug, turn, state: started|event|
done, n?, event?, prompt?, result?}`, a tool call's input cut to a short
line), so the page follows a turn over SSE; `turn/<id>?since=N` stays the
fallback poll. `cancel(slug, tid)` stops a running turn (the child is killed,
the turn ends with code 130 and `cancelled: true`).
"""

from __future__ import annotations

import itertools
import json
import threading
import time

_IDS = itertools.count(1)
_LOCK = threading.Lock()
TURNS: dict = {}       # turn id -> turn
LIVE: dict = {}        # project slug -> the turn id still running
TOOL_INPUT_CHARS = 160
TEXT_CHARS = 20000


def live_turn(slug: str):
    tid = LIVE.get(slug)
    return tid if tid and tid in TURNS and not TURNS[tid]["done"] else None


def slim(event: dict) -> dict:
    """An event as the live feed carries it: tool inputs as one short line, long text capped."""
    if not isinstance(event, dict) or event.get("type") != "assistant":
        if isinstance(event, dict) and isinstance(event.get("result"), str) and len(event["result"]) > TEXT_CHARS:
            return {**event, "result": event["result"][:TEXT_CHARS]}
        return event
    blocks = []
    for b in (event.get("message") or {}).get("content") or []:
        if not isinstance(b, dict):
            continue
        if b.get("type") == "tool_use":
            line = json.dumps(b.get("input") or {}, ensure_ascii=False, default=str)
            blocks.append({"type": "tool_use", "name": b.get("name") or "tool", "input_line": line[:TOOL_INPUT_CHARS]})
        elif b.get("type") == "text":
            blocks.append({"type": "text", "text": str(b.get("text") or "")[:TEXT_CHARS]})
    return {"type": "assistant", "message": {"content": blocks}}


def _frame(slug: str, tid: str, data: dict) -> dict:
    return {"session_id": f"design:{slug}", "event": "design_turn", "data": {"slug": slug, "turn": tid, **data},
            "turn": None, "agent_id": None, "ts": time.time()}


def start(project, prompt: str, *, model: str = "", budget=None, runner=None, registered=None, after=None, publish=None, **turn_kw):
    """Begin a turn; None when this project already has one running. `after(result)`
    returns extra keys for the finished result (a critique's pins); `publish(frame)`
    puts each step on the live feed; `turn_kw` goes to `run_turn` (tools_override,
    entries, max_turns)."""
    from halo_harness.design import session
    with _LOCK:
        if live_turn(project.slug):
            return None
        tid = f"t{next(_IDS)}"
        turn = {"id": tid, "slug": project.slug, "prompt": prompt, "events": [], "done": False, "result": None,
                "cancel": threading.Event()}
        TURNS[tid] = turn
        LIVE[project.slug] = tid

    def send(data: dict) -> None:
        if publish is not None:
            try:
                publish(_frame(project.slug, tid, data))
            except Exception:  # the feed is a convenience: the poll still has every event
                pass

    def on_event(obj: dict) -> None:
        turn["events"].append(obj)
        send({"state": "event", "n": len(turn["events"]) - 1, "event": slim(obj)})

    def work() -> None:
        try:
            r = session.run_turn(project, prompt, model=model, on_event=on_event, max_budget_usd=budget,
                                 registered=registered, runner=runner, cancel=turn["cancel"], **turn_kw)
            turn["result"] = {"code": r["code"], "cost": r["cost"], "text": r["text"], "versions": [list(v) for v in r["versions"]]}
            if turn["cancel"].is_set():
                turn["result"]["cancelled"] = True
            if after is not None:
                turn["result"].update(after(turn["result"]))
        except Exception as e:  # a failed turn is a result the page can show, not a dead thread
            turn["result"] = {"code": 1, "cost": None, "text": "", "versions": [], "error": f"{type(e).__name__}: {e}"}
        finally:
            turn["done"] = True
            send({"state": "done", "result": turn["result"]})

    send({"state": "started", "prompt": prompt[:TEXT_CHARS]})
    turn["thread"] = threading.Thread(target=work, name=f"halo-design-{tid}", daemon=True)
    turn["thread"].start()
    return turn


def cancel(slug: str, tid: str):
    """(status, body): stop a running turn of this project."""
    turn = TURNS.get(tid)
    if turn is None or turn["slug"] != slug:
        return 404, {"error": "no such turn"}
    if turn["done"]:
        return 409, {"error": "that turn has already finished", "result": turn["result"]}
    turn["cancel"].set()
    return 200, {"cancelled": True, "turn": tid}


def poll(slug: str, tid: str, since: int):
    turn = TURNS.get(tid)
    if turn is None or turn["slug"] != slug:
        return None
    done = turn["done"]  # read before the events so a finished turn never loses its tail
    events = list(turn["events"])
    return {"id": tid, "events": events[since:], "next": len(events), "done": done, "result": turn["result"] if done else None}
