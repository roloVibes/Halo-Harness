"""halo_harness.fleet.mission_worker_session -- the session a mission part runs
in (Halo 3.0.6.0 "Fleet Missions" round R7): built in-process the way print
mode builds one (headless.build_session, `print_mode=True`: an ask becomes a
deny, nobody waits on a card), with the owner's own settings, permission
rules, MCP servers and skills, in the part's folder. It is registered as
`kind: mission-worker` with `mission`, `part` and `parent` (the mission id)
on its registry row (`open_row`), so Studio, the fleet and the hub's agent
tree see it and `pause | resume | stop` reach it like any session.

`build(cwd)` -> `(session, run, close)`: `run(prompt, handle)` drains one
turn (teed into the session's feed when it has a socket) and returns
`{text, cost_usd, ok, error, session_id}`. Tests replace
`mission_worker.BUILD` with a fake of the same shape.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Optional


def build(cwd, home=None):
    from halo_harness import headless
    from halo_harness.output import PrintModeSink
    b = headless.build_session(cwd=Path(cwd), print_mode=True)
    session = b.session

    def run(prompt: str, handle=None) -> dict:
        stream = io.StringIO()
        sink = PrintModeSink(output_format="json", session_id=b.session_log.session_id, model=b.model_ref.raw,
                             stream=stream, permission_denials=session.permission_denials)
        turn = session.turn(prompt)
        sink.consume(handle.tee(turn) if handle is not None else turn)
        try:
            obj = json.loads(stream.getvalue())
        except ValueError:
            obj = {}
        cost = float(obj.get("total_cost_usd") or 0.0)
        if not cost and getattr(session, "cost_meter", None) is not None and session.cost_meter.has_cost_data:
            cost = float(session.cost_meter.total_usd)
        return {"text": str(obj.get("result") or ""), "cost_usd": cost, "ok": bool(obj) and not obj.get("is_error"),
                "error": "" if obj and not obj.get("is_error") else str(obj.get("result") or "no result from the model")[:500],
                "session_id": b.session_log.session_id}

    def close() -> None:
        for fn in (lambda: session._fire_session_end("other"), session.job_registry.kill_all,
                   getattr(b.mcp_manager, "close_all", lambda: None), getattr(session, "close_runtimes", lambda: None)):
            try:
                fn()
            except Exception:
                pass
    return session, run, close


def open_row(session, cwd, *, mission: str, part: str, title: str):
    """Open the session's control socket as a `mission-worker` and put mission / part / parent on its row."""
    from halo_harness.remote import fleet_frames, registry, runtime
    act = runtime.start_for_session(session, cwd, kind="mission-worker")
    if act is None:
        return None
    act.entry.update(mission=mission, part=str(part), parent=mission, title=f"{mission} part {part}: {title}"[:120])
    try:
        log = getattr(session, "log", None)
        if log is not None and hasattr(log, "append_meta"):
            log.append_meta(title=act.entry["title"])
    except Exception:
        pass
    registry.update(act.session_id, mission=mission, part=str(part), parent=mission, title=act.entry["title"])
    fleet_frames.fleet_frame(act, "update")
    return act


def close_row(act) -> None:
    if act is not None:
        from halo_harness.remote import runtime
        runtime.stop_one(act)


def frame(act, data: dict) -> None:
    """A `fleet` frame on the session's feed (the relay carries it to the hub)."""
    if act is None:
        return
    try:
        act.handle.hub.publish_frame({"event": "fleet", "data": data, "turn": None, "agent_id": None})
    except Exception:
        pass


def last_text(session) -> Optional[str]:
    try:
        for node in reversed(session.log.nodes()):
            if node.get("type") == "assistant":
                return " ".join(c.get("text", "") for c in node.get("content") or [] if isinstance(c, dict))
    except Exception:
        return None
    return None
