"""halo_harness.fleet.recording -- flight recordings (Halo 3.0.5.0 "Fleet"
round R4, D5): a session, or one agent and its sub-agents, as one
self-contained HTML replay (recording_page.py: inline CSS and JS, the
session as a JSON block, no network at all) written to
`~/.halo/recordings/<sid>[-<aid>].html`.

    render(hist, harness=, agent=) -> str     the page for a history (fleet/history.py's shape)
    write(home, hist, harness=, agent=) -> Path
    path_for(home, name) -> Path | None       a recording by its file name (the download route)
    from_tails(row, tails) -> hist            a member's session, from its rows and `agent_tail` entries

The JSON block escapes `<` and `/`, so neither a `</script>` nor a `://` in
anything an agent wrote ends up in the page as markup or as a link.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from halo_harness.fleet.recording_page import BODY, CSS, JS

DIR = "recordings"
MAX_ENTRIES = 600
_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,160}\.html$")


def _safe(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", str(text or ""))[:80] or "x"


def name_for(sid: str, agent: Optional[str] = None) -> str:
    return f"{_safe(sid)}{'-' + _safe(agent) if agent else ''}.html"


def _subtree(agents: list, root: str) -> set:
    keep, grow = {root}, True
    while grow:
        grow = False
        for a in agents:
            if a.get("parent") in keep and a["agent_id"] not in keep:
                keep.add(a["agent_id"])
                grow = True
    return keep


def scoped(hist: dict, agent: Optional[str]) -> dict:
    """The history cut to one agent and its sub-agents (the whole session when `agent` is empty)."""
    if not agent or not any(a.get("agent_id") == agent for a in hist.get("agents") or []):
        return hist
    keep = _subtree(hist["agents"], agent)
    agents = [a for a in hist["agents"] if a["agent_id"] in keep]
    states = [s for s in hist.get("states") or [] if s.get("agent_id") in keep]
    times = [s["t"] for s in states]
    return {**hist, "agents": agents, "states": states,
            "entries": {k: v for k, v in (hist.get("entries") or {}).items() if k in keep},
            "cost_usd": round(sum(float(a.get("cost_usd") or 0) for a in agents), 6),
            "started": min(times) if times else hist.get("started"), "ended": max(times) if times else hist.get("ended")}


def _data(hist: dict, harness: str, agent: Optional[str]) -> str:
    data = {k: hist.get(k) for k in ("session_id", "title", "cwd", "model", "started", "ended", "cost_usd")}
    data.update(harness=harness, focus=agent or "main", agents=hist.get("agents") or [], states=hist.get("states") or [],
                costs=hist.get("costs") or [],
                entries={k: (v or [])[-MAX_ENTRIES:] for k, v in (hist.get("entries") or {}).items()})
    if data["cwd"]:
        data["cwd"] = Path(str(data["cwd"])).name  # a full path never leaves in a file meant to be shared
    raw = json.dumps(data, ensure_ascii=False, default=str)
    return raw.replace("<", "\\u003c").replace(">", "\\u003e").replace("/", "\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def render(hist: dict, *, harness: str = "", agent: Optional[str] = None) -> str:
    hist = scoped(hist, agent)
    return ("<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            "<title>Halo flight recording</title><style>" + CSS + "</style></head>\n<body>\n" + BODY +
            "<script type=\"application/json\" id=\"data\">" + _data(hist, harness, agent) + "</script>\n"
            "<script>" + JS + "</script>\n</body></html>\n")


def write(home, hist: dict, *, harness: str = "", agent: Optional[str] = None) -> Path:
    from halo_harness.privateio import write_private_atomic
    folder = Path(home) / DIR
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name_for(str(hist.get("session_id") or "session"), agent)
    write_private_atomic(path, render(hist, harness=harness, agent=agent))
    return path


def path_for(home, name: str) -> Optional[Path]:
    if not _NAME.fullmatch(str(name or "")) or ".." in name:
        return None
    path = Path(home) / DIR / name
    return path if path.is_file() else None


def from_tails(row: dict, tails: dict) -> dict:
    """A member's session (its row from the hub's view, the agents' `agent_tail` entries) as a history."""
    from halo_harness.fleet.history import states_of
    agents, states, times = [], [], []
    for a in row.get("agents") or []:
        aid = str(a.get("agent_id") or "")
        ents = [e for e in tails.get(aid) or [] if isinstance(e, dict)]
        ts = [float(e["ts"]) for e in ents if isinstance(e.get("ts"), (int, float))]
        since = a.get("since") if isinstance(a.get("since"), (int, float)) else (min(ts) if ts else None)
        st = str(a.get("state") or "")
        end = max(ts) if ts and st in ("done", "failed", "stopped") else None
        states += states_of(aid, ents, end, "failed" if st == "failed" else "done" if end else "")
        times += ts + ([since] if since else [])
        agents.append({"agent_id": aid, "parent": a.get("parent"), "name": a.get("name") or aid, "role": a.get("role"),
                       "bio": a.get("bio"), "lineup": a.get("lineup"), "model": a.get("model"), "state": st,
                       "since": since, "ended": end, "cost_usd": a.get("cost_usd"), "task": a.get("task")})
    total = round(sum(float(a.get("cost_usd") or 0) for a in agents), 6)
    return {"session_id": row.get("session_id"), "title": row.get("title") or "", "cwd": row.get("cwd"),
            "model": row.get("model"), "started": min(times) if times else row.get("started"),
            "ended": max(times) if times else None, "cost_usd": total, "agents": agents,
            "entries": {a["agent_id"]: tails.get(a["agent_id"]) or [] for a in agents},
            "states": sorted(states, key=lambda s: (s["t"], s["agent_id"])),
            "costs": [{"t": max(times), "usd": total}] if times else []}
