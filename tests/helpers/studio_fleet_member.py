"""tests.helpers.studio_fleet_member -- the member harness `kali@lab` of
tests/helpers/studio_fleet_rig.py: what its relay announces to the hub (one
session on the shop repo: the main agent waiting on a question, a reviewer
that finished) and how its link answers the hub's commands (the R1 wire
shapes: agent_tail's entries, agent_follow, agent_steer, agent_stop, pause,
resume)."""
from __future__ import annotations

import time

MEMBER = "c0ffee5eed00000000000000000000a1"
MEMBER_SID = "a9b8c7d6e5f40000000000000000beef"
T0 = time.time() - 240

MAIN = {"agent_id": "main", "parent": None, "name": "main", "role": "main", "bio": "orchestrator", "lineup": "halo-dev-cycle",
        "model": "or:deepseek/deepseek-v4", "kind": "main", "task": "Review the basket diff on review/basket", "since": T0,
        "state": "waiting", "turns": 3, "cost_usd": 0.0412, "current": None, "last_text": "Two questions before I write the review."}
REVIEWER = {"agent_id": "r7e1v2w3", "parent": "main", "name": "reviewer", "role": "reviewer", "bio": "reviewer",
            "lineup": "halo-dev-cycle", "model": "or:deepseek/deepseek-v4-flash", "kind": "member",
            "task": "Review basket.py for pricing bugs", "since": T0 + 20, "state": "done", "turns": 4, "cost_usd": 0.0187,
            "current": None, "last_text": "Two findings: the discount applies after tax (line 41); a zero quantity passes the guard (line 58)."}

TAILS = {
    "main": [
        {"kind": "user", "text": "Review the basket diff on review/basket and tell me what to fix", "ts": T0},
        {"kind": "spawn", "id": "call_r1", "name": "reviewer", "task": "Review basket.py for pricing bugs", "ts": T0 + 20},
        {"kind": "tool_result", "id": "call_r1", "text": REVIEWER["last_text"], "is_error": False, "ts": T0 + 200},
        {"kind": "text", "text": "I read the reviewer's findings. Two questions before I write the review.", "ts": T0 + 210},
        {"kind": "ask", "what": "question", "ts": T0 + 212},
    ],
    "r7e1v2w3": [
        {"kind": "user", "text": "Review basket.py for pricing bugs", "ts": T0 + 20},
        {"kind": "tool_call", "id": "call_v1", "name": "Read", "input": {"file_path": "basket.py"}, "label": "Read: basket.py", "ts": T0 + 30},
        {"kind": "tool_result", "id": "call_v1", "text": "def total(items): ...", "is_error": False, "ts": T0 + 31},
        {"kind": "handback", "text": REVIEWER["last_text"], "ts": T0 + 190},
    ],
}


def session_row(rec: dict) -> dict:
    return {"session_id": MEMBER_SID, "title": "review the basket diff", "mode": "default", "kind": "tui", "cwd": "shop",
            "started": T0, "pid": 4242, "harness": {k: rec.get(k) for k in ("id", "name", "host", "user", "version", "os")},
            "project": {"root": "shop", "repo": "shop", "branch": "review/basket", "dirty": False}, "parent": None,
            "status": "waiting", "busy": True, "pending": {"question": ["q-basket-1"]}, "model": MAIN["model"],
            "cost_usd": 0.0599, "agents_live": 1, "agents": [dict(MAIN), dict(REVIEWER)]}


def announce_body(rec: dict) -> dict:
    return {"link": "rig-link", "harness": {k: rec.get(k) for k in ("name", "host", "user", "version", "os")}, "share": "full",
            "allow_control": "all", "allow_answers": False, "sessions": [session_row(rec)]}


def answer(doc: dict) -> dict:
    """The member's `done` result for one command doc (the R1 shapes)."""
    cmd, fields = doc.get("cmd"), doc.get("fields") or {}
    aid = str(fields.get("agent_id") or "main")
    if cmd == "agent_tail":
        return {"agent_id": aid, "events": TAILS.get(aid, [])}
    if cmd == "agent_follow":
        return {"agent_id": aid, "following": [aid] if fields.get("on", True) else []}
    if cmd == "agent_steer":
        return {"agent_id": aid, "mode": fields.get("mode") or "nudge", "delivered": "inbox"}
    if cmd == "agent_stop":
        return {"agent_id": aid, "stopping": [aid]}
    if cmd == "pause":
        return {"paused": aid}
    if cmd == "resume":
        return {"resumed": aid, "was_paused": True}
    return {}
