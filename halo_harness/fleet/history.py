"""halo_harness.fleet.history -- one session as a timeline, read from its
transcripts on disk (Halo 3.0.5.0 "Fleet" round R4). A flight recording
(recording.py), the canvas replay (`GET /api/fleet/replay`) and the digest
(digest.py) read it; nothing here calls a model.

    find(state_dir, sid) -> Path | None    <state>/sessions/<project>/<sid>.jsonl
    read_nodes(path) -> [node, ...]         its JSON lines (a file over CAP_BYTES: the last CAP_BYTES of it)
    read(path) -> {session_id, title, cwd, model, started, ended, cost_usd,
                   agents:  [{agent_id, parent, name, role, bio, lineup, model, state, since, ended, cost_usd, task}],
                   entries: {agent_id: [entry, ...]}               agent/agent_transcript.py's entries
                   states:  [{t, agent_id, state, activity, tool?}]  when each agent typed, ran a tool, waited, ended
                   costs:   [{t, usd}]}                            the running total, one point per usage line

A sub-agent is `<sid>/subagents/agent-<id>.jsonl` beside its `.meta.json`
(its own children one folder deeper); the main agent is "main". A state
change is one point per entry: a text or a thought is "typing", a tool call
"tool" (with its name), a card it opened "waiting", its end "done" or
"failed".
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from halo_harness.agent.agent_transcript import entries_from_nodes, first_line

CAP_BYTES = 4_000_000
MAX_AGENTS = 120
MAIN = "main"
EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")


def find(state_dir, sid: str) -> Optional[Path]:
    root = Path(state_dir) / "sessions"
    if not sid or not root.is_dir() or any(c in sid for c in "/\\*?["):
        return None
    hits = sorted(root.glob(f"*/{sid}.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    return hits[0] if hits else None


def read_nodes(path, cap: int = CAP_BYTES) -> list:
    try:
        size = Path(path).stat().st_size
        with open(path, "rb") as f:
            if size > cap:
                f.seek(size - cap)
                f.readline()  # a partial first line
            raw = f.read()
    except OSError:
        return []
    out = []
    for line in raw.decode("utf-8", "replace").splitlines():
        if line.strip():
            try:
                node = json.loads(line)
            except ValueError:
                continue
            if isinstance(node, dict):
                out.append(node)
    return out


def _ts(node) -> Optional[float]:
    t = node.get("ts") if isinstance(node, dict) else None
    return float(t) if isinstance(t, (int, float)) and not isinstance(t, bool) else None


def _usage(nodes: list) -> list:
    return [(_ts(n) or 0.0, float(n["cost_usd"])) for n in nodes
            if n.get("type") == "usage" and isinstance(n.get("cost_usd"), (int, float))]


def _meta(nodes: list, key: str):
    for n in nodes:
        if n.get("type") == "meta" and n.get(key) not in (None, ""):
            return n[key]
    return None


def _title(nodes: list) -> str:
    for n in reversed(nodes):
        if n.get("type") == "meta" and isinstance(n.get("title"), str) and n["title"]:
            return n["title"]
    return ""


def _activity(entry: dict) -> "tuple[str, str, str]":
    """(state, activity, tool) after this entry."""
    kind = entry.get("kind")
    if kind in ("tool_call", "spawn"):
        return "running", "tool", str(entry.get("name") or "")
    if kind == "ask":
        return "waiting", "waiting", ""
    if kind == "handback":
        return "done", "done", ""
    if kind == "done":
        return "done", "done", ""
    return "running", "typing", ""


def states_of(aid: str, entries: list, ended: Optional[float], end_state: str) -> list:
    out, last = [], None
    for e in entries:
        t = e.get("ts")
        if not isinstance(t, (int, float)):
            continue
        state, act, tool = _activity(e)
        if state == "done":
            continue  # its end comes from `ended` (the meta's finish, or the session's last line)
        cur = (state, act, tool)
        if cur != last:
            out.append({"t": float(t), "agent_id": aid, "state": state, "activity": act, **({"tool": tool} if tool else {})})
            last = cur
    if ended is not None and end_state:
        out.append({"t": float(ended), "agent_id": aid, "state": end_state, "activity": "failed" if end_state == "failed" else "done"})
    return out


def _task(entries: list) -> str:
    return next((first_line(e.get("text"), 200) for e in entries if e.get("kind") == "user" and e.get("text")), "")


def _children(folder: Path, parent: str, out: list) -> None:
    sub = folder / "subagents"
    if not sub.is_dir():
        return
    for meta_path in sorted(sub.glob("agent-*.meta.json")):
        if len(out) >= MAX_AGENTS:
            return
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            meta = {}
        stem = meta_path.name[:-len(".meta.json")]
        aid = str(meta.get("agent_id") or stem[len("agent-"):])
        out.append((aid, parent, meta if isinstance(meta, dict) else {}, sub / f"{stem}.jsonl"))
        _children(sub / stem, aid, out)


def read(path, *, live_states: Optional[dict] = None) -> dict:
    """The session at `path` as one timeline. `live_states` ({agent_id: state}) keeps a live agent live."""
    path = Path(path)
    live_states = live_states or {}
    nodes = read_nodes(path)
    times = [t for t in (_ts(n) for n in nodes) if t is not None]
    started, ended = (min(times), max(times)) if times else (None, None)
    main_entries = entries_from_nodes(nodes, final=MAIN not in live_states)
    main_cost = round(sum(c for _t, c in _usage(nodes)), 6)
    main_state = live_states.get(MAIN) or "done"
    agents = [{"agent_id": MAIN, "parent": None, "name": "main", "role": "main", "bio": _meta(nodes, "agent") or None,
               "lineup": None, "model": _meta(nodes, "model"), "state": main_state, "since": started, "ended": ended,
               "cost_usd": main_cost, "task": _task(main_entries)}]
    entries = {MAIN: main_entries}
    states = states_of(MAIN, main_entries, ended, "" if main_state in ("running", "waiting", "paused") else "done")
    usage = list(_usage(nodes))
    kids: list = []
    _children(path.parent / path.stem, MAIN, kids)
    for aid, parent, meta, log in kids:
        cnodes = read_nodes(log)
        live = live_states.get(aid)
        failed = bool(meta.get("is_error")) or meta.get("status") == "failed"
        state = live or ("failed" if failed else "done" if meta.get("finished") else "running")
        ents = entries_from_nodes(cnodes, final=live is None and bool(meta.get("finished")))
        ctimes = [t for t in (_ts(n) for n in cnodes) if t is not None]
        since = meta.get("started") if isinstance(meta.get("started"), (int, float)) else (min(ctimes) if ctimes else None)
        fin = meta.get("finished") if isinstance(meta.get("finished"), (int, float)) else None
        cost = round(sum(c for _t, c in _usage(cnodes)), 6)
        usage += _usage(cnodes)
        agents.append({"agent_id": aid, "parent": parent, "name": meta.get("type") or aid, "role": meta.get("role"),
                       "bio": meta.get("type"), "lineup": meta.get("lineup"), "model": meta.get("model"), "state": state,
                       "since": since, "ended": fin, "cost_usd": cost, "task": _task(ents) or str(meta.get("description") or "")})
        entries[aid] = ents
        st = states_of(aid, ents, fin, "" if live else state if state in ("done", "failed") else "")
        if since is not None and (not st or st[0]["t"] > since):
            st.insert(0, {"t": float(since), "agent_id": aid, "state": "running", "activity": "typing"})
        states += st
    total, costs = 0.0, []
    for t, c in sorted(usage):
        total += c
        costs.append({"t": t, "usd": round(total, 6)})
    all_t = [s["t"] for s in states] + ([started] if started else []) + ([ended] if ended else [])
    return {"session_id": path.stem, "title": _title(nodes), "cwd": _meta(nodes, "cwd"), "model": _meta(nodes, "model"),
            "started": min(all_t) if all_t else None, "ended": max(all_t) if all_t else None,
            "cost_usd": round(total, 6), "agents": agents, "entries": entries,
            "states": sorted(states, key=lambda s: (s["t"], s["agent_id"])), "costs": costs}


def edited_files(entries: list) -> list:
    """The files an agent's Edit / Write calls named, in order, once each."""
    seen: list = []
    for e in entries or []:
        if e.get("kind") == "tool_call" and e.get("name") in EDIT_TOOLS and isinstance(e.get("input"), dict):
            f = e["input"].get("file_path") or e["input"].get("notebook_path") or e["input"].get("path")
            if isinstance(f, str) and f and f not in seen:
                seen.append(f)
    return seen
