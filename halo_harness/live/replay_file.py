"""halo_harness.live.replay_file -- a run's replay as ONE self-contained file (Halo 3.4.1.0 R1 "Time"):
`<state>/replays/<id>.halo-replay`, JSON, that `halo replay open <file>` and Studio's History open on any machine.
docs/REPLAY.md is the reference.

    {"format": "halo-replay", "version": 1, "kind": "session", "id", "session_id", "title", "saved", "halo",
     "started", "ended", "cost_usd",
     "agents":  [{agent_id, parent, name, role, bio, lineup, model, state, since, ended, cost_usd, task}],
     "states":  [{t, agent_id, state, activity, tool?}],  "costs": [{t, usd}],  "agent_costs": [{t, agent_id, usd}],
     "marks":   [{t, kind, agent_id, name, text, to?}],   "bands": [{t0, t1, phase}],
     "plan":    null (3.6.0.0 R5b; a 3.4 / 3.5 file has the lineup's blocks here, read and never drawn)
     "facts":   {cost_usd, cost_unknown, tokens, model_cost, retries, failed_calls, steers}   3.4.1.0 R2: the record's
                                                          own figures (live/replay_facts.py), what Compare reads
     "includes": [line, ...]}                             what the file holds, in words (said before it is written)

3.4.1.0 R2: `kind` is "session" or "run" (a goal run, live/replay_run.py: `run_id`, the lead and its lanes as agents);
`facts` and `run_id` are new keys a version-1 reader ignores, so the version stays 1 and an R1 file still opens.

What it never holds: the prompts, the tool inputs and outputs, the thoughts, the working directory (3.4.1.0 R3:
`facts.artefacts` names the files it wrote by their path inside the project). Every string passes
`redact.sanitize_node`, the rule `halo export --sanitize` and `halo session export` apply, then (3.4.1.1, defect 56)
privacy_scrub.scrub: a path is project-relative or `~/...`, the user and machine names are out of every text
but the owner's own (the title) and a path inside the project.

    build(state_dir, sid, lineup=None, cwd=None) -> payload       save(state_dir, payload) -> Path
    load(path) / parse(text) -> payload (an older file upgraded)   saved(state_dir) -> rows, newest first

3.6.0.3: the payload's names and build moved to live/card_data.py (no change of behaviour) and are re-exported
here until the batch that deletes this module; what is left is the file code (save, load, path_for ...).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from halo_harness.live.card_data import (AGENT_KEYS, build, FORMAT, includes, plan_of, ReplayError, VERSION)  # noqa: F401 (moved in 3.6.0.3)

SUFFIX = ".halo-replay"
MAX_BYTES = 32_000_000
DROP_KEYS = {"path", "cwd", "_path", "_source", "file"}
_ID = re.compile(r"^[A-Za-z0-9_.-]{1,120}$")


def replays_dir(state_dir) -> Path:
    return Path(state_dir) / "replays"


def _scrub(obj):
    """Every path-like key out (a lineup's file, a square's folder), recursively."""
    if isinstance(obj, dict):
        return {k: _scrub(v) for k, v in obj.items() if k not in DROP_KEYS}
    if isinstance(obj, list):
        return [_scrub(v) for v in obj]
    return obj


def save(state_dir, payload: dict) -> Path:
    """Write the payload; every string passes privacy_scrub.scrub first (3.4.1.1, defect 56: whatever built or
    brought it, the file never holds this machine's home path, user name or machine name)."""
    from halo_harness.privacy_redact import redact  # 3.4.1.2 (PACKS-5): secrets, paths and names, one function
    original, payload = payload, redact(payload)
    if "_sanitize_error" in payload:
        raise ReplayError("the redactor could not clean this replay; nothing was written")
    pid = str(payload.get("id") or "")
    if not _ID.match(pid):
        raise ReplayError(f"not a replay id: {pid!r}")
    folder = replays_dir(state_dir)
    folder.mkdir(parents=True, exist_ok=True)
    path, n = folder / f"{pid}{SUFFIX}", 1
    while path.exists():  # 3.4.1.2 (PACKS-7): a file of the same id (an import) never replaces a saved replay
        n += 1
        path = folder / f"{pid[:110]}-{n}{SUFFIX}"
    if n > 1:
        payload["id"] = original["id"] = path.name[:-len(SUFFIX)]
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    tmp.replace(path)
    return path


def upgrade(data: dict) -> dict:
    """A file of an older shape as today's. Version 0: a 3.0.5.0-3.4.0.0 `GET live/replay` answer saved as is
    (session_id, agents, states, costs; no format)."""
    if data.get("format") == FORMAT:
        v = data.get("version")
        if not isinstance(v, int) or v < 1:
            raise ReplayError("a halo-replay file without a version number")
        if v > VERSION:
            raise ReplayError(f"this replay is version {v}; this Halo reads up to version {VERSION} (halo update)")
        return data
    if isinstance(data.get("agents"), list) and isinstance(data.get("states"), list) and data.get("session_id"):
        from halo_harness.privacy_redact import redact
        sid = str(data["session_id"])
        p = {"format": FORMAT, "version": VERSION, "kind": "session", "id": f"{sid}-v0", "session_id": sid, "upgraded_from": 0,
             "title": data.get("title") or "", "saved": None, "halo": "", "started": data.get("started"), "ended": data.get("ended"),
             "cost_usd": data.get("cost_usd"), "agents": [{k: a.get(k) for k in AGENT_KEYS} for a in data["agents"] if isinstance(a, dict)],
             "states": data["states"], "costs": data.get("costs") or [], "agent_costs": data.get("agent_costs") or [],
             "marks": data.get("marks") or [], "bands": data.get("bands") or [], "plan": None}
        p = redact(_scrub(p))
        if "_sanitize_error" in p:
            raise ReplayError("the redactor could not clean this file")
        p["includes"] = includes(p)
        return p
    raise ReplayError("not a Halo replay (no `format: halo-replay`, and not a session timeline)")


def parse(text: str) -> dict:
    from halo_harness.live.replay_guard import MAX_DEPTH, _depth_ok, _plain  # 3.4.1.2 (PACKS-7)
    try:
        data = json.loads(text)
    except (ValueError, RecursionError) as e:
        raise ReplayError(f"not a Halo replay: not JSON ({type(e).__name__})") from None
    if not _depth_ok(data):
        raise ReplayError(f"not a Halo replay: nested more than {MAX_DEPTH} levels deep")
    if not isinstance(data, dict):
        raise ReplayError("not a Halo replay: not a JSON object")
    p = _plain(upgrade(data))
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
