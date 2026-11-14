"""halo_harness.live.talk -- one agent's words to another, as one shape (Halo 3.3.16.2, the owner: "a section that
does this for model to model or agent to agent conversations ... so we see models conversing with each other").

Every message is an `agent_talk` frame (the agent tree's listener publishes it, remote/agent_frames.py; Studio's own
bridge for a hand-over) whose data is:

    {"id": "m<n>", "from": <agent id>, "to": <agent id or "">, "text": <at most TALK_CAP characters>, "why": <WHYS>,
     "ts", "from_name"?, "to_name"?, "re"?: <the id it answers>, "cut"?: true, "chars"?: <the whole length>,
     "square"?: <the square's name>, "machine"?: <the machine handed to>}

Where it comes from, each where the thing already happens (no model is called):

    task       a parent hands a child its task: the child's turn starts (agent/agent_hooks.py turn_started)
    hand-back  the child's last words to its parent: the child's turn ends (turn_ended); `re` is the task's id
    steer      an agent steers another through the control socket's `agent_steer` with `from_agent`
               (remote/agent_control.py); the user's own steer stays YOU and is never a talk
    square     a Workflow square hand-off and what came back: a session square's agent (its row's `square`), or an
               orchestra square's node (tools/workflow.py)
    hand-over  Studio's "Hand to..." an agent's work to another machine (studio/live_handoff_api.py)

The transcripts keep the whole text as before; a frame carries at most TALK_CAP characters and says when it was cut.
There is no mailbox between agents in this harness: no other path exists.
"""
from __future__ import annotations

import itertools
import time
from typing import Optional

TALK_CAP = 4000
WHYS = ("task", "hand-back", "steer", "square", "hand-over")
_IDS = itertools.count(1)


def shape(frm: str, to: str, text, why: str, *, re: Optional[str] = None, from_name: Optional[str] = None,
          to_name: Optional[str] = None, square: Optional[str] = None, machine: Optional[str] = None,
          ts: Optional[float] = None) -> dict:
    text = str(text or "")
    d = {"id": f"m{next(_IDS)}", "from": str(frm or ""), "to": str(to or ""), "text": text[:TALK_CAP], "why": why,
         "ts": ts or time.time()}
    if len(text) > TALK_CAP:
        d["cut"], d["chars"] = True, len(text)
    for k, v in (("re", re), ("from_name", from_name), ("to_name", to_name), ("square", square), ("machine", machine)):
        if v:
            d[k] = v
    return d


def emit(tree, d: dict) -> dict:
    try:
        tree._emit("agent_talk", d["from"], d)
    except Exception:
        pass
    return d


def _name(row: Optional[dict], aid: str) -> str:
    row = row or {}
    return str(row.get("name") or row.get("role") or aid)


def _square(row: Optional[dict]) -> str:
    sq = (row or {}).get("square")
    return str(sq.get("name") or "") if isinstance(sq, dict) else ""


def final_text(session) -> str:
    """The session's last assistant text (its hand-back), "" when it wrote none."""
    try:
        nodes = session.log.nodes()
    except Exception:
        return ""
    for node in reversed(nodes or []):
        if isinstance(node, dict) and node.get("type") == "assistant":
            text = "".join(b.get("text", "") for b in node.get("content") or [] if isinstance(b, dict) and b.get("type") == "text")
            if text.strip():
                return text.strip()
    return ""


def on_turn_started(tree, aid: str, text: str) -> Optional[dict]:
    """A child's turn starts: its parent's task (or a square's brief), parent -> child. None for the main agent."""
    row = tree.row(aid)
    parent = (row or {}).get("parent")
    if aid == tree.root_id or not parent or not str(text or "").strip():
        return None
    sq = _square(row)
    d = shape(parent, aid, text, "square" if sq else "task", from_name=_name(tree.row(parent), parent),
              to_name=_name(row, aid), square=sq or None)
    tree.__dict__.setdefault("_talk_open", {})[aid] = d["id"]
    return emit(tree, d)


def on_turn_ended(tree, aid: str, session) -> Optional[dict]:
    """A child's turn ends: its last words back to its parent, answering the task (`re`). None for the main agent."""
    row = tree.row(aid)
    parent = (row or {}).get("parent")
    if aid == tree.root_id or not parent:
        return None
    text = final_text(session)
    if not text:
        return None
    sq = _square(row)
    asked = tree.__dict__.setdefault("_talk_open", {}).pop(aid, None)
    return emit(tree, shape(aid, parent, text, "square" if sq else "hand-back", re=asked, from_name=_name(row, aid),
                            to_name=_name(tree.row(parent), parent), square=sq or None))


def on_steer(tree, req: dict, aid: str, text: str) -> Optional[dict]:
    """`agent_steer` from another agent of this tree (`from_agent`): a steer talk. A person's steer is not a talk."""
    frm = str((req or {}).get("from_agent") or "")
    if not frm or frm == aid or tree.row(frm) is None:
        return None
    return emit(tree, shape(frm, aid, text, "steer", from_name=_name(tree.row(frm), frm), to_name=_name(tree.row(aid), aid)))


def on_square(tree, caller: str, node: str, ref: str, text: str, *, back: bool = False,
              re: Optional[str] = None) -> Optional[dict]:
    """An orchestra square: the task to its node, then (`back`) what came back to the caller (re: the task's id)."""
    if not back:
        return emit(tree, shape(caller, node, text, "square", square=ref, from_name=_name(tree.row(caller), caller), to_name=ref))
    return emit(tree, shape(node, caller, text or "(the square handed back nothing)", "square", square=ref, re=re,
                            from_name=ref, to_name=_name(tree.row(caller), caller)))


def hand_over_frame(*, harness: str, session_id: str, aid: str, name: str, machine: str, text: str) -> dict:
    """Studio's "Hand to...": the frame its own bridge publishes (the agent's brief, addressed to the machine)."""
    d = shape(aid, "", text, "hand-over", from_name=name, to_name=machine, machine=machine)
    return {"session_id": session_id, "harness": harness, "event": "agent_talk", "agent_id": aid, "turn": None,
            "data": d, "ts": d["ts"]}
