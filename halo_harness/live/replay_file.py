"""halo_harness.live.replay_file -- a run's replay as ONE self-contained file (Halo 3.4.1.0 R1 "Time"):
`<state>/replays/<id>.halo-replay`, JSON, that `halo replay open <file>` and Studio's History open on any machine.
docs/REPLAY.md is the reference.

    {"format": "halo-replay", "version": 1, "kind": "session", "id", "session_id", "title", "saved", "halo",
     "started", "ended", "cost_usd",
     "agents":  [{agent_id, parent, name, role, bio, lineup, model, state, since, ended, cost_usd, task}],
     "states":  [{t, agent_id, state, activity, tool?}],  "costs": [{t, usd}],  "agent_costs": [{t, agent_id, usd}],
     "marks":   [{t, kind, agent_id, name, text, to?}],   "bands": [{t0, t1, phase}],
     "plan":    {"lineup", "graph", "squares"} | null,    the lineup's blocks as they were when it was saved
     "facts":   {cost_usd, cost_unknown, tokens, model_cost, retries, failed_calls, steers}   3.4.1.0 R2: the record's
                                                          own figures (live/replay_facts.py), what Compare reads
     "includes": [line, ...]}                             what the file holds, in words (said before it is written)

3.4.1.0 R2: `kind` is "session" or "run" (a goal run, live/replay_run.py: `run_id`, the lead and its lanes as agents);
`facts` and `run_id` are new keys a version-1 reader ignores, so the version stays 1 and an R1 file still opens.

What it never holds: the prompts, the tool inputs and outputs, the thoughts, the working directory, any path. Every
string passes `redact.sanitize_node`, the rule `halo export --sanitize` and `halo session export` apply.

    build(state_dir, sid, lineup=None, cwd=None) -> payload       save(state_dir, payload) -> Path
    load(path) / parse(text) -> payload (an older file upgraded)   saved(state_dir) -> rows, newest first
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Optional

FORMAT = "halo-replay"
VERSION = 1
SUFFIX = ".halo-replay"
MAX_BYTES = 32_000_000
AGENT_KEYS = ("agent_id", "parent", "name", "role", "bio", "lineup", "model", "state", "since", "ended", "cost_usd", "task")
DROP_KEYS = {"path", "cwd", "_path", "_source", "file"}
_ID = re.compile(r"^[A-Za-z0-9_.-]{1,120}$")


class ReplayError(ValueError):
    """A file that is not a replay, or one this Halo cannot read; the message says which."""


def replays_dir(state_dir) -> Path:
    return Path(state_dir) / "replays"


def _scrub(obj):
    """Every path-like key out (a lineup's file, a square's folder), recursively."""
    if isinstance(obj, dict):
        return {k: _scrub(v) for k, v in obj.items() if k not in DROP_KEYS}
    if isinstance(obj, list):
        return [_scrub(v) for v in obj]
    return obj


def plan_of(lineup: Optional[str], cwd=None, state_dir=None) -> Optional[dict]:
    """The lineup's blocks now (its graph and its enabled squares), as Live's plan reads them; None when it does not load."""
    if not lineup:
        return None
    try:
        from halo_harness.studio import model as M
        from halo_harness import teams_yaml as T
        resolved = T.resolve_team_template(lineup, cwd=cwd, state_dir=state_dir)
        if not resolved:
            return None
        graph = M.graph_for(resolved, cwd=cwd, state_dir=state_dir)
    except Exception:
        return None
    squares: list = []
    try:
        from halo_harness.workflows import registry
        from halo_harness.workflows.squares_cli import rows
        on = set(registry.enabled_refs(lineup, cwd=cwd))
        squares = [r for r in rows(Path(cwd or "."), lineup) if r.get("ref") in on and r.get("square")]
    except Exception:
        squares = []
    return _scrub({"lineup": lineup, "graph": graph, "squares": squares})


def includes(p: dict) -> list:
    n_agents = len(p.get("agents") or [])
    kinds: dict = {}
    for m in p.get("marks") or []:
        kinds[m.get("kind")] = kinds.get(m.get("kind"), 0) + 1
    marks = ", ".join(f"{n} {k}" for k, n in kinds.items()) or "no marks"
    plan = p.get("plan") or {}
    return [f"{n_agents} agent{'s' if n_agents != 1 else ''}: names, roles, models, tasks (first line), states, costs",
            f"{len(p.get('states') or [])} state changes and the cost over time; marks: {marks}"
            + ("; the record's figures (cost, tokens, models, retries)" if p.get("facts") else ""),
            "a goal run's record: the lead and its lanes, each lane's state changes (not each step)" if p.get("kind") == "run"
            else f"the lineup's blocks: {plan.get('lineup')}" if plan else "no lineup blocks (the lineup did not load)",
            "not included: prompts, tool inputs and outputs, thoughts, the working directory, any path",
            "every text passed the export redactor (`halo session export`'s rules)"]


def build(state_dir, sid: str, *, lineup: Optional[str] = None, cwd=None, live_states: Optional[dict] = None) -> dict:
    """The replay of session `sid` on this machine. Raises ReplayError when there is no such session."""
    from halo_harness import __version__
    from halo_harness.live import history, replay_facts, timeline
    from halo_harness.redact import sanitize_node
    path = history.find(state_dir, sid)
    if path is None:
        raise ReplayError(f"no transcript of session {sid!r} on this machine")
    hist = history.read(path, live_states=live_states)
    if not lineup:
        from halo_harness.lineup_default import lineup_in_use
        lineup = lineup_in_use()[0]
    p = {"format": FORMAT, "version": VERSION, "kind": "session", "id": "", "session_id": hist["session_id"],
         "title": hist.get("title") or "", "saved": round(time.time(), 3), "halo": __version__,
         "started": hist.get("started"), "ended": hist.get("ended"), "cost_usd": hist.get("cost_usd"),
         "agents": [{k: a.get(k) for k in AGENT_KEYS} for a in hist.get("agents") or []],
         "states": hist.get("states") or [], "costs": hist.get("costs") or [], "agent_costs": hist.get("agent_costs") or [],
         **timeline.of(hist), "plan": plan_of(lineup, cwd=cwd, state_dir=state_dir), "facts": replay_facts.session_facts(path)}
    p["id"] = f"{p['session_id']}-{time.strftime('%Y%m%d-%H%M%S', time.localtime(p['saved']))}"
    p = sanitize_node(p)
    if "_sanitize_error" in p:
        raise ReplayError("the redactor could not clean this session's timeline; nothing was written")
    p["includes"] = includes(p)
    return p


def save(state_dir, payload: dict) -> Path:
    pid = str(payload.get("id") or "")
    if not _ID.match(pid):
        raise ReplayError(f"not a replay id: {pid!r}")
    folder = replays_dir(state_dir)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{pid}{SUFFIX}"
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    tmp.replace(path)
    return path


def upgrade(data: dict) -> dict:
    """A file of an older shape as today's. Version 0: a 3.0.5.0-3.4.0.0 `GET fleet/replay` answer saved as is
    (session_id, agents, states, costs; no format)."""
    if data.get("format") == FORMAT:
        v = data.get("version")
        if not isinstance(v, int) or v < 1:
            raise ReplayError("a halo-replay file without a version number")
        if v > VERSION:
            raise ReplayError(f"this replay is version {v}; this Halo reads up to version {VERSION} (halo update)")
        return data
    if isinstance(data.get("agents"), list) and isinstance(data.get("states"), list) and data.get("session_id"):
        from halo_harness.redact import sanitize_node
        sid = str(data["session_id"])
        p = {"format": FORMAT, "version": VERSION, "kind": "session", "id": f"{sid}-v0", "session_id": sid, "upgraded_from": 0,
             "title": data.get("title") or "", "saved": None, "halo": "", "started": data.get("started"), "ended": data.get("ended"),
             "cost_usd": data.get("cost_usd"), "agents": [{k: a.get(k) for k in AGENT_KEYS} for a in data["agents"] if isinstance(a, dict)],
             "states": data["states"], "costs": data.get("costs") or [], "agent_costs": data.get("agent_costs") or [],
             "marks": data.get("marks") or [], "bands": data.get("bands") or [], "plan": None}
        p = sanitize_node(_scrub(p))
        if "_sanitize_error" in p:
            raise ReplayError("the redactor could not clean this file")
        p["includes"] = includes(p)
        return p
    raise ReplayError("not a Halo replay (no `format: halo-replay`, and not a session timeline)")


def parse(text: str) -> dict:
    try:
        data = json.loads(text)
    except ValueError as e:
        raise ReplayError(f"not a Halo replay: not JSON ({e})") from None
    if not isinstance(data, dict):
        raise ReplayError("not a Halo replay: not a JSON object")
    p = upgrade(data)
    if not _ID.match(str(p.get("id") or "")):
        raise ReplayError(f"not a replay id: {p.get('id')!r}")
    return p


def load(path) -> dict:
    path = Path(path)
    try:
        size = path.stat().st_size
        if size > MAX_BYTES:
            raise ReplayError(f"{path.name} is {size} bytes; a replay is at most {MAX_BYTES}")
        return parse(path.read_text(encoding="utf-8"))
    except OSError as e:
        raise ReplayError(f"cannot read {path}: {e.strerror or e}") from None


def path_for(state_dir, rid: str) -> Optional[Path]:
    if not _ID.match(rid or ""):
        return None
    p = replays_dir(state_dir) / f"{rid}{SUFFIX}"
    return p if p.is_file() else None


def row(p: dict, path: Optional[Path] = None) -> dict:
    t0, t1 = p.get("started"), p.get("ended")
    span = t1 - t0 if isinstance(t0, (int, float)) and isinstance(t1, (int, float)) else None
    return {"id": p.get("id"), "kind": p.get("kind") or "session", "session_id": p.get("session_id"), "run_id": p.get("run_id"),
            "title": p.get("title") or "", "saved": p.get("saved"),
            "started": t0, "ended": t1, "secs": span, "cost_usd": p.get("cost_usd"), "agents": len(p.get("agents") or []),
            "marks": len(p.get("marks") or []), "bytes": path.stat().st_size if path else None,
            "path": str(path) if path else None, "version": p.get("version")}


def saved(state_dir) -> list:
    folder = replays_dir(state_dir)
    out = []
    for path in folder.glob(f"*{SUFFIX}") if folder.is_dir() else []:
        try:
            out.append(row(load(path), path))
        except ReplayError:
            continue
    return sorted(out, key=lambda r: -(r.get("saved") or 0))
