"""halo_harness.ollama_steward.log_status -- Halo 3.3.6.0 R3: is a host's server log live
(plans/local-model-fit-brief.md D3 item 16).

    status(state_dir, host, *, now=None, platform=None, read=False, path=None) -> {state, path, last_line_at, why, line,
        debug, readable, rung, paths, tail_cli, halo_cli, debug_action, member?}
    ladder(state_dir, host) -> {rung: "local" | "ssh" | "member" | "api-ps", why, member?, last_at?}
    group_of(line) -> "failure" | "truncation" | "fit" | "headroom" | None   (the Logs page's filter)
    debug_action(host_name) -> the debug window, said as a stated action (Halo never sets it)

The states: `live` (the newest log line is newer than the ledger's newest call to that host minus 60 s, or lines
arrive with no calls), `stale` (the ledger has calls in the last 15 minutes the log never saw), `quiet` (neither has
anything in the last 15 minutes), `unreadable` (the file or the ssh read did not answer), `remote-no-ssh` (on that
machine, no `ssh:` entry: a fleet member's push, else `/api/ps` only), `missing` (no log where Ollama writes it).
`debug: on` when debug-level lines appear (OLLAMA_DEBUG=1 is set there).
"""

from __future__ import annotations

import json
import sys
import time
from typing import Optional

LIVE_SLACK_S = 60.0
RECENT_S = 900.0
_TAIL_BYTES = 256 * 1024
GROUPS = (("failure", ("CUDA error", "illegal memory access", "terminated", "level=ERROR", "| 500 |", "| 499 |",
                       "aborting", "Load failed", "out of memory", "0xc0000409", "no user query")),
          ("truncation", ("truncating input prompt", "truncated = 1", "failed to find a memory slot", "context shift")),
          ("fit", ("offloaded", "KV buffer size", "graph splits", "overflowing", "starting llama-server",
                   "llama-server started", "load_tensors", "llama_kv_cache")),
          ("headroom", ('msg="gpu memory"', 'msg="system memory"', "inference compute", "common_memory_breakdown")))


def group_of(line: str) -> Optional[str]:
    for name, needles in GROUPS:
        if any(n in (line or "") for n in needles):
            return name
    return None


def debug_action(name: str) -> str:
    return (f"set OLLAMA_DEBUG=1 and restart Ollama on {name}; very verbose; it still does not log request bodies "
            "(a logging proxy does: halo ollama explain server-log); turn it off after")


def ago(seconds) -> str:
    if not isinstance(seconds, (int, float)):
        return "?"
    s = max(0, int(seconds))
    return f"{s} s" if s < 120 else f"{s // 60} min" if s < 7200 else f"{s // 3600} h" if s < 172800 else f"{s // 86400} d"


def newest_call(state_dir, host) -> Optional[float]:
    """The `at` of the ledger's newest line to `host` (its last 256 KB read)."""
    from halo_harness.ollama_steward.ledger import host_matches, parse_at, traffic_path
    try:
        with open(traffic_path(state_dir), "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - _TAIL_BYTES))
            rows = f.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return None
    for raw in reversed(rows):
        try:
            line = json.loads(raw)
        except ValueError:
            continue
        if isinstance(line, dict) and host_matches(line, host.name):
            return parse_at(line.get("at"))
    return None


def _member_events(state_dir, host) -> Optional[dict]:
    """The newest event a fleet member pushed for the server at `host`'s address (fleet/control_probes.py)."""
    import urllib.parse
    from halo_harness.ollama_steward.server_events import read_events
    try:
        u = urllib.parse.urlparse(host.url)
        want = ((u.hostname or "").lower(), u.port or 11434)
    except ValueError:
        return None
    rows = [r for r in read_events(state_dir, since=86400.0) if r.get("from") and r.get("addr")
            and (str(r["addr"]).lower(), int(r.get("port") or 11434)) == want]
    return rows[-1] if rows else None


def ladder(state_dir, host) -> dict:
    from halo_harness.fleet.ollama_share import served_here
    if served_here(host.url):
        return {"rung": "local", "why": ""}
    if getattr(host, "ssh", None):
        return {"rung": "ssh", "why": f"read over ssh ({host.ssh})"}
    ev = _member_events(state_dir, host)
    if ev is not None:
        return {"rung": "member", "member": ev.get("from"), "last_at": ev.get("at"),
                "why": f"on that machine, no ssh entry: {ev.get('from')}'s ledger push carries its events"}
    return {"rung": "api-ps", "why": "on that machine, no ssh entry: no log -- fit from /api/ps (size_vram < size = spill)"}


def _local(st: dict, host, platform, path=None) -> None:
    from pathlib import Path
    from halo_harness.ollama_steward.hardware_readers import server_log_path
    from halo_harness.ollama_steward.log_tail import local_tail, tail_lines
    target = Path(path) if path is not None else server_log_path(platform)
    win = (platform or sys.platform).startswith("win")
    if target.exists():
        rows = local_tail(target, 400)
        st.update(path=str(target), readable=True, lines=rows,
                  paths=[str(p) for p in sorted(target.parent.glob("server*.log"))] +
                  ([str(target.parent / "app.log")] if win and (target.parent / "app.log").exists() else []),
                  tail_cli=(f'Get-Content -Wait -Tail 50 "{target}"' if win else f"tail -f {target}"))
        try:
            st["mtime"] = target.stat().st_mtime
        except OSError:
            st.update(readable=False, state="unreadable", why=f"{target} could not be read")
        return
    if (platform or sys.platform).startswith("linux"):
        rows, _src, why = tail_lines(host, 200, platform=platform)
        st.update(path="journalctl -u ollama", paths=["journalctl -u ollama"], tail_cli="journalctl -u ollama -f",
                  readable=why is None, lines=rows)
        if why:
            st.update(state="unreadable", why=why)
        return
    st.update(state="missing", path=str(target), why=f"no server log at {target}: is Ollama installed on this machine?")


def _remote(st: dict, state_dir, host, lad: dict, read: bool) -> None:
    from halo_harness.ollama_steward import server_log_remote as R
    if lad["rung"] != "ssh":
        st.update(state="remote-no-ssh", why=lad["why"], path="", member=lad.get("member"))
        if lad.get("last_at"):
            from halo_harness.ollama_steward.ledger import parse_at
            st["last_line_at"] = parse_at(lad["last_at"])
        return
    rs = R.host_state(state_dir, host.name)
    if read and not rs.get("read_at"):
        R.read_new_remote(state_dir, host)
        rs = R.host_state(state_dir, host.name)
    win = rs.get("platform") == "windows"
    st.update(path=f"ssh {host.ssh}: {rs.get('path') or ('%LOCALAPPDATA%/Ollama/server.log' if win else '~/.ollama/logs/server.log')}",
              last_line_at=rs.get("last_line_at"), debug=bool(rs.get("debug")), readable=bool(rs.get("ok_at")),
              tail_cli=(f'ssh {host.ssh} powershell -NoProfile -Command "Get-Content -Wait -Tail 50 '
                        '$env:LOCALAPPDATA/Ollama/server.log"' if win else
                        f"ssh {host.ssh} journalctl -u ollama -f" if rs.get("path") == "journalctl -u ollama" else
                        f"ssh {host.ssh} tail -f ~/.ollama/logs/server.log"))
    if not rs.get("read_at"):
        st.update(state="unreadable", why=f"not read yet: the steward reads it every {R.REMOTE_S:.0f} s "
                  f"(halo ollama log --host {host.name})")
    elif rs.get("why"):
        st.update(state="unreadable", why=str(rs["why"]))


def status(state_dir, host, *, now: Optional[float] = None, platform: Optional[str] = None, read: bool = False,
           path=None) -> dict:
    from halo_harness.ollama_steward.server_rules import line_time, strip_prefix
    now = time.time() if now is None else now
    lad = ladder(state_dir, host)
    st: dict = {"host": host.name, "state": None, "path": "", "paths": [], "last_line_at": None, "why": "", "debug": False,
                "readable": False, "rung": lad["rung"], "tail_cli": "", "halo_cli": f"halo ollama log --host {host.name} --follow",
                "debug_action": debug_action(host.name)}
    if lad["rung"] == "local" or path is not None:
        _local(st, host, platform, path)
    else:
        _remote(st, state_dir, host, lad, read)
    rows = st.pop("lines", None) or []
    if rows:
        times = [t for t in (line_time(strip_prefix(x)) for x in rows) if t is not None]
        st["last_line_at"] = max(times) if times else st.get("mtime")
        st["debug"] = any("level=DEBUG" in x for x in rows)
    st.pop("mtime", None)
    if st["state"] is None:
        call, last = newest_call(state_dir, host), st.get("last_line_at")
        recent = call is not None and now - call <= RECENT_S
        if recent and last is not None and last >= call - LIVE_SLACK_S:
            st["state"] = "live"
        elif recent:
            st.update(state="stale", why=f"the ledger has calls the log never saw (the newest call {ago(now - call)} ago, "
                      + (f"the newest log line {ago(now - last)} ago)" if last else "no timed line in the log)"))
        elif last is not None and now - last <= RECENT_S:
            st["state"] = "live"
        else:
            st.update(state="quiet", why="no calls and no log lines in the last 15 minutes")
    last = st.get("last_line_at")
    head = {"remote-no-ssh": "on that machine, no ssh entry"}.get(st["state"], st["state"])
    st["line"] = (head + (f", last line {ago(now - last)} ago" if isinstance(last, (int, float)) else "") +
                  (" · debug: on" if st["debug"] else "") + (f" · {st['path']}" if st["path"] else "") +
                  (f" ({st['why']})" if st["why"] and st["state"] != "live" else ""))
    return st
