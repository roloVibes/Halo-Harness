"""halo_harness.packs.events_log -- every event a pack publishes, kept
(Halo 3.2.0.0 R5, docs/EXTENSION_API.md "Events and artifacts").

`ext.publish_event` appends each event it accepts to the pack's data folder,
`~/.halo/packs/.data/<id>/events.jsonl` (one JSON object per line: `{ts, pack,
kind, data, problems?}`), besides the Studio frame. That file is what a
subscription reads from any process: a bio's `triggers: [{on: event, name:
<pack>:<kind>}]` (agents_schedule.py) and a workflow stage's `after_event:
<pack>:<kind>` (workflows/runtime.py).

    check(pack_id, kind, data, cwd=..., state_dir=...)  -> (refusal, problems): refusal '' when the pack runs
                                                            here; problems = the data against the kind's schema
    append(pack_id, kind, data, problems, state_dir=...) -> the entry written
    since(name, ts, state_dir=...)                       -> entries of `<pack>:<kind>` (or every kind of
                                                            `<pack>`) newer than `ts`, oldest first
"""

from __future__ import annotations

import json
import time
from pathlib import Path

FILE = "events.jsonl"
KEEP = 2000  # lines kept per pack (the oldest go when it grows past twice that)


def log_path(pack_id: str, state_dir=None) -> Path:
    from halo_harness.packs.discover import user_packs_dir
    return user_packs_dir(state_dir) / ".data" / pack_id / FILE


def check(pack_id: str, kind: str, data, *, cwd=None, state_dir=None) -> "tuple[str, list]":
    from halo_harness.packs.discover import find
    from halo_harness.packs.studio_registry import active_pack
    from halo_harness.packs.typed import check as against, event_kinds, event_schema
    pack = active_pack(pack_id, cwd=cwd, state_dir=state_dir)
    if pack is None:
        state = "is not installed here" if find(pack_id, cwd=cwd, state_dir=state_dir) is None else "is disabled here"
        return f"pack {pack_id} {state}: its event {kind} is not published (halo pack enable {pack_id})", []
    if kind not in event_kinds(pack.manifest):
        return "", []  # an undeclared kind: published with Studio's generic line
    schema = event_schema(pack.root, pack.manifest, kind)
    return "", against(data, schema) if schema is not None else []


def append(pack_id: str, kind: str, data, problems=(), *, state_dir=None) -> dict:
    from halo_harness.orchestra import jsonl
    path = log_path(pack_id, state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {"ts": round(time.time(), 3), "pack": pack_id, "kind": kind, "data": data}
    if problems:
        entry["problems"] = list(problems)
    with jsonl.locked(path):
        jsonl.append_line(path, entry)
        lines = jsonl.read_lines(path)
        if len(lines) > 2 * KEEP:
            path.write_text("".join(json.dumps(e) + "\n" for e in lines[-KEEP:]), encoding="utf-8")
    return entry


def since(name: str, ts: float = 0.0, *, state_dir=None) -> "list[dict]":
    from halo_harness.orchestra import jsonl
    pack_id, _, kind = str(name).partition(":")
    if not pack_id:
        return []
    out = [e for e in jsonl.read_lines(log_path(pack_id, state_dir)) if isinstance(e, dict)]
    return [e for e in out if float(e.get("ts") or 0) > float(ts) and (not kind or e.get("kind") == kind)]


def is_pack_event(name) -> bool:
    """`<pack>:<kind>`: a pack's event name (the subscriptions' name space)."""
    from halo_harness.packs.workflow_stages import EVENT
    return isinstance(name, str) and bool(EVENT.match(name))
