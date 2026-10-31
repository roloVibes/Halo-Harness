"""halo_harness.agent.offline_promise -- a session's offline promise as a badge (Halo 3.3.7.0 R2;
plans/local-model-fit-brief.md G15: "100 % local -- 0 tokens left this machine", every call naming its host).

Read, never estimated:

- the session log's `usage` nodes (agent/log.py `append_usage`: one per model call, its `model` ref and `route`): a
  local model ref (ol:, hf:local/, hf:mlx/) is a local call, anything else a call to that route's provider;
- the traffic ledger's lines of the session (`session` = its id; ollama_steward/ledger.py): which server each local
  call went to (`host` {name, url}); a server this machine serves is "this machine", another one on the LAN "left this
  machine" (the line names it, and the halo host that serves it when one is paired: host_client.for_host).

    promise(state_dir, session_id, *, log_path=None) -> {line, calls, local, cloud {route: n}, hosts {name: {calls,
        here, via}}, left, per_call [line]}
    badge_line(session) -> the line for `/cost` and the Session header ("" when there is no call yet)

The lines:  "100 % local -- 0 tokens left this machine"
            "100 % local -- 4 calls left this machine, all on the LAN: pc x 4 (halo host at 192.0.2.10)"
            "67 % local -- 3 calls left this machine: openrouter x 1, pc x 2"
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Optional

NO_CALLS = "no model call yet"


def _is_local(ref: str) -> bool:
    try:
        from halo_harness.model import is_local_ref_string
        return bool(is_local_ref_string(ref))
    except Exception:
        return str(ref).startswith(("ol:", "hf:local/", "hf:mlx/"))


def usage_nodes(log_path) -> list:
    out = []
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            for raw in f:
                if '"usage"' not in raw:
                    continue
                try:
                    node = json.loads(raw)
                except ValueError:
                    continue
                if isinstance(node, dict) and node.get("type") == "usage" and node.get("model"):
                    out.append(node)
    except OSError:
        return []
    return out


def _route(node: dict) -> str:
    return str(node.get("route") or node.get("provider") or str(node.get("model")).split("/", 1)[0] or "a provider")


def _hosts(state_dir, session_id: str) -> "tuple[dict, list]":
    from types import SimpleNamespace
    from halo_harness.fleet.ollama_share import served_here
    from halo_harness.ollama_steward.host_client import for_host
    from halo_harness.ollama_steward.ledger import read_calls
    lines = [x for x in read_calls(state_dir, since=30 * 86400.0) if x.get("session") == session_id
             and x.get("kind") != "calibrate"]
    hosts: dict = {}
    per = []
    for x in lines:
        h = x.get("host") or {}
        name, url = str(h.get("name") or h.get("url") or "?"), str(h.get("url") or "")
        row = hosts.get(name)
        if row is None:
            here = served_here(url)
            c = None if here else for_host(SimpleNamespace(url=url, name=name))
            row = hosts[name] = {"calls": 0, "here": here, "via": f"halo host at {c.addr}" if c else ""}
        row["calls"] += 1
        where = "this machine" if row["here"] else (row["via"] or "on the LAN")
        per.append(f"{str(x.get('at') or '')[11:19]} {x.get('model')} -> {name} ({where})")
    return hosts, per


def promise(state_dir, session_id: str, *, log_path=None) -> dict:
    if log_path is None:
        from halo_harness.session_trace_cli import find_session_log
        log_path, _why = find_session_log(session_id)
    nodes = usage_nodes(log_path) if log_path else []
    hosts, per = _hosts(state_dir, session_id) if state_dir is not None else ({}, [])
    cloud = Counter(_route(n) for n in nodes if not _is_local(str(n.get("model"))))
    local = sum(1 for n in nodes if _is_local(str(n.get("model"))))
    lan = {k: v for k, v in hosts.items() if not v["here"]}
    led = sum(v["calls"] for v in hosts.values())
    local = max(local, led)
    total = local + sum(cloud.values())
    left = sum(cloud.values()) + sum(v["calls"] for v in lan.values())
    out = {"calls": total, "local": local, "cloud": dict(cloud), "hosts": hosts, "left": left, "per_call": per[-50:]}
    if not total:
        return {**out, "line": NO_CALLS}
    pct = round(100.0 * local / total)
    lan_words = ", ".join(f"{k} x {v['calls']}" + (f" ({v['via']})" if v["via"] else "") for k, v in lan.items())
    if left == 0:
        line = f"{pct} % local -- 0 tokens left this machine"
    elif not cloud:
        line = f"{pct} % local -- {left} call{'s' if left != 1 else ''} left this machine, all on the LAN: {lan_words}"
    else:
        words = ", ".join([f"{k} x {v}" for k, v in cloud.most_common()] + ([lan_words] if lan_words else []))
        line = f"{pct} % local -- {left} call{'s' if left != 1 else ''} left this machine: {words}"
    return {**out, "line": line}


def badge_line(session) -> str:
    """The `/cost` line (and `halo session show`'s); "" when the session made no call yet."""
    try:
        from halo_harness.config.paths import bridge_home
        log = getattr(session, "log", None)
        path = Path(getattr(log, "path", "") or "") if log is not None else None
        sid = getattr(session, "session_id", None) or getattr(log, "session_id", "") or ""
        got = promise(bridge_home(), str(sid),
                      log_path=path if path and path.exists() else None)
    except Exception:
        return ""
    return "" if got["line"] == NO_CALLS else f"Offline promise: {got['line']}"
