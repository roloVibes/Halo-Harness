"""halo_harness.supervise.services_rows -- the pack services' files and the rows other processes read (Halo 3.3.13.0
R3; the supervisor's side is supervise/services.py, docs/SUPERVISE.md "Pack services").

    rows(state_dir=None) -> [row]   what the running supervisor last wrote; with none running a `running` row reads `off`
    row(key, state_dir=None)        one row, or None
    want(key, verb, state_dir=None) "start" | "stop" asked of the running supervisor (its next tick applies it)
    take_wants(applied, state_dir)  the tick removes the asks it applied, under the want file's lock
    state_line(row)                 "running since 09:12" | "stopped: <line>" | "off: <line>"
    declared(state_dir, cwd)        [(pack, entry, granted)] for every running pack's services
    health(pack_id, entry, state_dir, now)   (ok | stale | unknown, the line the program wrote in its health file)

A row: {key, pack, name, description, state: running | stopped | failed | off, pid, since, exit, line, autostart,
restart, health}. Files, both 0600: <state>/supervise/services.json {version, services: {key: {...}}} and
<state>/supervise/services-want.json {key: "start" | "stop"}; a service's stop file is
<state>/supervise/services/<pack>--<name>.stop.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

from halo_harness.packs import manifest_services as MS

ROW_KEYS = ("pack", "name", "description", "state", "pid", "since", "exit", "line", "autostart", "restart", "health")


def _root(state_dir=None) -> Path:
    from halo_harness.supervise.queue import root
    return root(state_dir)


def state_path(state_dir=None) -> Path:
    return _root(state_dir) / "services.json"


def want_path(state_dir=None) -> Path:
    return _root(state_dir) / "services-want.json"


def stop_file(key: str, state_dir=None) -> Path:
    return _root(state_dir) / "services" / (key.replace("/", "--") + ".stop")


def read_json(path: Path) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def write_json(path: Path, data: dict) -> None:
    from halo_harness.privateio import write_private_atomic
    try:
        write_private_atomic(path, json.dumps(data, indent=2, sort_keys=True))
    except OSError:
        pass


def data_dir(pack_id: str, state_dir=None) -> Path:
    from halo_harness.packs.state import packs_home
    return packs_home(state_dir) / ".data" / pack_id


def declared(state_dir=None, cwd=None) -> "list[tuple]":
    from halo_harness.packs import state as S
    from halo_harness.packs.registry import active
    data = S.load(state_dir)
    out = []
    for pack in active(cwd=cwd, state_dir=state_dir):
        granted = MS.GRANT in (S.granted(pack.id, data) or [])
        out += [(pack, e, granted) for e in MS.services_of(pack.manifest) if isinstance(e.get("name"), str)]
    return out


def health_file(pack_id: str, entry: dict, state_dir=None) -> Optional[Path]:
    rel = MS.health_of(entry).get("file")
    return (data_dir(pack_id, state_dir) / rel) if rel else None


def health(pack_id: str, entry: dict, state_dir=None, now: Optional[float] = None) -> "tuple[str, str]":
    path = health_file(pack_id, entry, state_dir)
    if path is None:
        return "unknown", ""
    try:
        age = (now or time.time()) - path.stat().st_mtime
    except OSError:
        return "unknown", ""
    doc = read_json(path)
    line = " ".join(str(doc.get("line") or doc.get("state") or "").split())[:200]
    return ("ok" if age <= MS.health_of(entry)["max_age_s"] else "stale"), line


def rows_of(rec: dict) -> list:
    return [{"key": k, **{f: r.get(f) for f in ROW_KEYS}} for k, r in sorted(rec.items()) if isinstance(r, dict)]


def rows(state_dir=None) -> list:
    from halo_harness.supervise import pulse
    out = rows_of(dict(read_json(state_path(state_dir)).get("services") or {}))
    if pulse.read(state_dir)["running"]:
        return out
    for r in out:
        if r["state"] == "running":
            r.update(state="off", line="the supervisor is not running (halo supervise starts it)")
    return out


def row(key: str, state_dir=None) -> Optional[dict]:
    return next((r for r in rows(state_dir) if r["key"] == key), None)


def want(key: str, verb: str, state_dir=None) -> str:
    if verb not in ("start", "stop"):
        return f"{verb!r}: start or stop"
    from halo_harness.filelock import file_lock
    with file_lock(want_path(state_dir)):  # 3.3.14.0 R2 (REVIEW #25): the tick takes its asks under the same lock
        data = read_json(want_path(state_dir))
        data[key] = verb
        write_json(want_path(state_dir), data)
    from halo_harness.supervise import pulse
    tail = "" if pulse.read(state_dir)["running"] else " (the supervisor is not running: `halo supervise` applies it)"
    return f"asked the supervisor to {verb} {key}{tail}"


def take_wants(applied: dict, state_dir=None) -> None:
    """The tick's side of services-want.json: remove only the asks it read (key and verb), under the file's lock, so a
    Start / Stop written after its read stays for the next tick (3.3.14.0 R2, REVIEW #25 CORE-7 / PERMS-11 / PACKS-8)."""
    from halo_harness.filelock import file_lock
    path = want_path(state_dir)
    with file_lock(path):
        data = read_json(path)
        write_json(path, {k: v for k, v in data.items() if applied.get(k) != v})


def enable_lines(pack, granted, state_dir=None) -> "list[str]":
    """`halo pack enable`'s line per service: where it starts and whether the supervisor runs now."""
    from halo_harness.supervise import pulse
    out = []
    for e in MS.services_of(pack.manifest):
        key = MS.key_of(pack.id, str(e.get("name")))
        if MS.GRANT not in (granted or []):
            out.append(f"service {key}: not running until granted (halo pack grant {pack.id} {MS.GRANT})")
            continue
        when = "starts with `halo supervise`" if e.get("autostart") is True else \
            "starts when you start it (halo supervise service start " + key + ")"
        running = "yes" if pulse.read(state_dir)["running"] else "no"
        out.append(f"service {key}: {when} (the supervisor running now: {running})")
    return out


def manager_block(pack, state_dir=None) -> list:
    """The Pack Manager row's services: [{name, key, state, line}] ("running since 09:12" / "stopped: <line>")."""
    entries = MS.services_of(pack.manifest)
    if not entries:
        return []
    by_key = {r["key"]: r for r in rows(state_dir)}
    out = []
    for e in entries:
        key = MS.key_of(pack.id, str(e.get("name")))
        r = by_key.get(key) or {"state": "off", "line": "the supervisor has not run it yet (halo supervise)"}
        out.append({"name": str(e.get("name")), "key": key, "state": r.get("state") or "off", "line": state_line(r),
                    "description": str(e.get("description") or "")})
    return out


def state_line(r: dict) -> str:
    if r.get("state") == "running":
        since = time.strftime("%H:%M", time.localtime(float(r.get("since") or time.time())))
        tail = f" ({r['line']})" if r.get("line") and r["line"] != "started" else ""
        return f"running since {since}{tail}"
    return f"{r.get('state') or 'off'}: {r.get('line') or 'not started'}"
