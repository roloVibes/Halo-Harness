"""halo_harness.fleet.handoff -- hand an agent's work to someone else (Halo
3.0.5.0 "Fleet" round R4, D4). Two moves, both from an agent in Studio:

* **Take over**: you give the agent a new brief; it is a redirect steer
  (remote/agent_control.py `agent_steer` with `handoff`), recorded as a
  hand-off in the agent's transcript and its parent's.
* **Hand to...**: the agent's task, its last hand-back and the files it
  touched become one brief. With Org mode on (`paperclip.enabled`) it is a
  Paperclip issue in the linked company, assigned to the chosen harness's
  company agent (`pick_agent`); with Org mode off it is a Markdown file,
  `<repo>/.halo/handoffs/<id>.md` (the state directory's `handoffs/` when the
  repo is not on this machine). Then the agent is stopped.

A hand-off never widens a permission: the steer is a note the agent reads,
the issue runs under the assignee's own permission engine, the file is only
text. Nothing here calls a model.
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


def pick_agent(agents: list, harness: dict) -> Optional[dict]:
    """The company agent that stands for `harness`: metadata halo_harness / harness (its id or name),
    else an agent whose name or title is the harness name (or its user part)."""
    hid, name = str(harness.get("id") or ""), str(harness.get("name") or "").lower()
    user = name.split("@")[0]
    for a in agents or []:
        meta = a.get("metadata") if isinstance(a.get("metadata"), dict) else {}
        if str(meta.get("halo_harness") or meta.get("harness") or "").lower() in (hid.lower(), name) and (hid or name):
            return a
    for a in agents or []:
        if any(str(a.get(k) or "").lower() in (name, user) for k in ("name", "title") if a.get(k)) and name:
            return a
    return None


def to_issue(state_dir, title: str, body: str, harness: dict, assignee: Optional[str] = None, client=None) -> dict:
    """A Paperclip issue in the linked company; `{issue, assignee, note}`."""
    from halo_harness.paperclip.client import Paperclip, load_config
    company = str(load_config(state_dir).get("company_id") or "")
    if not company:
        raise ValueError("Org mode is on but no company is linked (halo paperclip link --company ...)")
    client = client or Paperclip.from_config(state_dir, timeout=10)
    agent = None
    if not assignee:
        agent = pick_agent(client.agents(company), harness)
        assignee = agent.get("id") if agent else None
    payload = {"title": title, "description": body, "status": "todo", **({"assigneeAgentId": assignee} if assignee else {})}
    issue = client.create_issue(company, payload) or {}
    note = "" if assignee else f"no company agent stands for {harness.get('name')}: the issue is unassigned (assign it in Org)"
    return {"issue": {k: issue.get(k) for k in ("id", "identifier", "title", "status", "assigneeAgentId")},
            "assignee": assignee, "assignee_name": (agent or {}).get("name"), "note": note}


def to_file(root, hid: str, markdown: str) -> Path:
    from halo_harness.privateio import write_private_atomic
    folder = Path(root) / ".halo" / "handoffs" if (Path(root) / ".git").exists() else Path(root) / "handoffs"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{hid}.md"
    write_private_atomic(path, markdown)
    return path
