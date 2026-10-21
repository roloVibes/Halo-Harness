"""halo_harness.supervise.asks -- a supervised job's asks, parked in Attention
(Halo 3.1.8.0 R1).

A `job` goal runs `halo -p` with HALO_SUPERVISE_GOAL=<g-id> and
HALO_SUPERVISE_ASKS=park|deny. The print run opens its control socket as every
`halo -p` does (remote.runtime.start_for_print); `attach_print_run` then
writes `<state>/supervise/sessions/<g-id>.json` {session_id, pid} and, with
`park`, makes the run's asks block on their waiters as an interactive
session's do (`session.interactive`). With `deny` a print run's asks are
denied at once, as always.

The supervisor taps every live session's feed (loop.py); a permission_request,
question, plan_review or approval_request frame of a job goal's session
becomes a `goal_ask` decision (decisions.py) with a deadline of
`supervise.tick_s * 720`. The owner's answer goes back over that session's
control socket (`answer`, the path Studio and the phone use); a row past its
deadline is answered for the owner: a permission denied, a question answered
"(no answer came: decide yourself and say what you chose)", a plan sent back.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

from halo_harness.privateio import write_private_atomic
from halo_harness.supervise import decisions

ASK_KINDS = {"permission_request": "permission", "question": "question", "plan_review": "plan",
             "approval_request": "approval"}
NO_ANSWER = "(no answer came: decide yourself and say what you chose)"


def sessions_dir(state_dir) -> Path:
    from halo_harness.supervise.queue import root
    return root(state_dir) / "sessions"


def attach_print_run(session, act, *, state_dir=None) -> bool:
    """Called by headless.run_print_mode once the control socket is open (HALO_SUPERVISE_GOAL set)."""
    gid = os.environ.get("HALO_SUPERVISE_GOAL") or ""
    if not gid or act is None:
        return False
    try:
        write_private_atomic(sessions_dir(state_dir) / f"{gid}.json",
                             json.dumps({"goal": gid, "session_id": act.session_id, "pid": os.getpid(),
                                         "ts": round(time.time(), 3)}))
    except OSError:
        return False
    if os.environ.get("HALO_SUPERVISE_ASKS") == "park":
        session.interactive = True  # an ask blocks on its waiter until the supervisor answers it
    return True


def session_goals(state_dir) -> dict:
    """{session_id: goal id} of the job goals whose print run has registered."""
    d = sessions_dir(state_dir)
    out = {}
    for p in d.glob("*.json") if d.is_dir() else []:
        try:
            row = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(row, dict) and row.get("session_id"):
            out[str(row["session_id"])] = str(row.get("goal") or p.stem)
    return out


def _what(kind: str, data: dict) -> "tuple[str, str]":
    from halo_harness.remote.bridge_cards import describe_input, normalize_questions, one_line
    if kind == "permission":
        name = str(data.get("name") or "a tool")
        return f"Permission: {name}", one_line(describe_input(name, data.get("input")) or data.get("reason"), 240)
    if kind == "question":
        qs = normalize_questions(data)
        return "Question", one_line(qs[0]["question"] if qs else "", 240)
    if kind == "plan":
        return "Plan review", one_line(data.get("plan"), 240)
    return f"Approval ({data.get('position') or 'next step'})", one_line(data.get("text"), 240)


def park_frame(state_dir, frame: dict, goals: dict, wait_s: float) -> Optional[dict]:
    """A job goal session's ask frame as a goal_ask row, else None."""
    kind = ASK_KINDS.get(str(frame.get("event") or ""))
    data = frame.get("data") if isinstance(frame.get("data"), dict) else {}
    sid = str(frame.get("session_id") or "")
    gid = goals.get(sid)
    if kind is None or gid is None:
        return None
    rid = str(data.get("id") or ("plan" if kind == "plan" else ""))
    if not rid:
        return None
    what, detail = _what(kind, data)
    keys = decisions.QUESTION_KEYS if kind == "question" else (
        {"a": "approve", "r": "send back", "s": "stop the goal", "o": "open the session"} if kind == "plan" else
        {"a": "accept", "r": "edit", "s": "stop the goal", "o": "open the session"} if kind == "approval" else None)
    return decisions.park(state_dir, "goal_ask", gid, f"{sid[:8]}-{rid}", f"Goal {gid}: {what}", detail,
                          deadline=round(time.time() + wait_s, 3), keys=keys, session_id=sid, request_id=rid,
                          ask=kind, agent_id=frame.get("agent_id") or "main")


def _entry(session_id: str) -> Optional[dict]:
    from halo_harness.remote import registry
    return next((r for r in registry.list_live() if r.get("session_id") == session_id), None)


def fields_for(row: dict, key: str, text: str) -> dict:
    """The control socket's `answer` fields for the owner's key on a goal_ask row."""
    t = row.get("target") or {}
    kind, rid = t.get("ask"), t.get("request_id")
    if kind == "permission":
        return {"kind": "permission", "request_id": rid, "action": "allow" if key == "a" else "deny", "scope": "once",
                "message": text if key == "r" else ("the goal was stopped" if key == "s" else "")}
    if kind == "question":
        return {"kind": "question", "request_id": rid, "answer": text if key == "r" and text else NO_ANSWER}
    if kind == "plan":
        return {"kind": "plan", "approved": key == "a", "feedback": text if key == "r" else ""}
    return {"kind": "approval", "request_id": rid, "action": {"a": "accept", "r": "edit"}.get(key, "stop"),
            "instruction": text if key == "r" else ""}


def send(row: dict, key: str, text: str = "") -> str:
    """Answer the job's card over its session's socket; '' when it went, else why not."""
    from halo_harness.remote.client import ControlClient, default_token_for
    sid = str((row.get("target") or {}).get("session_id") or "")
    entry = _entry(sid)
    if entry is None:
        return f"session {sid[:8]} is gone"
    client = ControlClient(str(entry.get("endpoint") or ""), default_token_for(entry), timeout=5)
    try:
        resp = client.call("answer", **fields_for(row, key, text))
    except Exception as e:
        return f"{type(e).__name__}: {e}"
    finally:
        client.close()
    return "" if resp.get("ok") else str(resp.get("error") or "the session refused the answer")


def expired(state_dir, now: Optional[float] = None) -> list:
    """The open goal_ask rows past their deadline."""
    now = time.time() if now is None else now
    return [r for r in decisions.open_rows(state_dir)
            if r.get("kind") == "goal_ask" and r.get("deadline") and float(r["deadline"]) <= now]
