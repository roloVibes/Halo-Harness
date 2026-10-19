"""halo_harness.fleet.handoff -- hand an agent's work to someone else (Halo
3.0.5.0 "Fleet" round R4, D4). Two moves, both from an agent in Studio:

* **Take over**: you give the agent a new brief; it is a redirect steer
  (remote/agent_control.py `agent_steer` with `handoff`), recorded as a
  hand-off in the agent's transcript and its parent's.
* **Hand to...**: the agent's task, its last hand-back and the files it
  touched become one brief, a Markdown file,
  `<repo>/.halo/handoffs/<id>.md` (the state directory's `handoffs/` when the
  repo is not on this machine). Then the agent is stopped.

A hand-off never widens a permission: the steer is a note the agent reads,
the file is only text. Nothing here calls a model.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Optional


def handoff_id(aid: str, now: Optional[float] = None) -> str:
    return time.strftime("%Y%m%d-%H%M%S", time.localtime(now)) + "-" + re.sub(r"[^A-Za-z0-9]", "", str(aid or "agent"))[:10]


def handback_of(entries: list, row: dict) -> str:
    hand = next((e.get("text") for e in reversed(entries or []) if e.get("kind") == "handback" and e.get("text")), "")
    if hand:
        return str(hand)
    out = []
    for e in reversed(entries or []):
        if e.get("kind") == "text":
            out.insert(0, str(e.get("text") or ""))
        elif e.get("kind") in ("tool_call", "spawn", "user"):
            break
    return "".join(out) or str(row.get("last_text") or "")


def brief(*, harness: dict, session: dict, agent: dict, handback: str, files: list, by: str, to: str,
          now: Optional[float] = None) -> "tuple[str, str]":
    """(title, markdown) of the hand-off."""
    task = str(agent.get("task") or "").strip() or "(no task line)"
    title = f"Hand-off: {task.splitlines()[0][:100]}"
    when = time.strftime("%Y-%m-%d %H:%M", time.localtime(now))
    who = agent.get("name") or agent.get("agent_id")
    role = f" ({agent['role']})" if agent.get("role") and agent.get("role") != who else ""
    lines = [f"# {title}", "",
             f"From **{harness.get('name') or harness.get('id')}**, session {session.get('title') or session.get('session_id')} "
             f"(`{session.get('session_id')}`), agent **{who}**{role}, model {agent.get('model') or '?'}.",
             f"Handed to **{to}** by {by} on {when}.", "", "## The task", "", task, "", "## Its last hand-back", "",
             handback.strip() or "(it had not handed anything back yet)", "", "## Files it touched", ""]
    lines += [f"- `{f}`" for f in files] or ["(none recorded)"]
    proj = session.get("project") if isinstance(session.get("project"), dict) else {}
    if proj.get("repo") or proj.get("branch"):
        lines += ["", f"Repo {proj.get('repo') or '?'}, branch {proj.get('branch') or '?'}."]
    return title, "\n".join(lines) + "\n"


def to_file(root, hid: str, markdown: str) -> Path:
    from halo_harness.privateio import write_private_atomic
    folder = Path(root) / ".halo" / "handoffs" if (Path(root) / ".git").exists() else Path(root) / "handoffs"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{hid}.md"
    write_private_atomic(path, markdown)
    return path
