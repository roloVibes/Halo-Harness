"""halo_harness.fleet.capabilities_probe -- the MCP half of a harness's
capability catalog (Halo 3.0.6.0 "Fleet Missions" round R6): every
configured MCP server and its tools, plus the claude.ai connectors from their
discovery cache. Computed in code; nothing here calls a model.

MCP tool lists come from the per-server tool cache (`<home>/mcp/tools-cache/
<server>.json`, the same files lazy MCP start writes). A server with no cache
is connected once (through the ordinary `McpManager` handshake) and the cache
written; every probe runs on its own thread and the whole set waits at most
`timeout` seconds, so a server that does not answer is listed with
`tools: null` and a note while its probe finishes in the background for the
next gather. `spawn=False` (the default under BRIDGE_TEST_NO_BACKGROUND_NET)
starts no MCP server at all.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Callable, Optional

MCP_TIMEOUT_S = 8.0
DESC_MAX = 240
_inflight: dict = {}
_lock = threading.Lock()


# ---- MCP --------------------------------------------------------------------------------
def _cache_file(home: Path, name: str) -> Path:
    from halo_harness.mcp.manager import sanitize_name
    return Path(home) / "mcp" / "tools-cache" / f"{sanitize_name(name)}.json"


def _cached_tools(home: Path, name: str) -> Optional[list]:
    try:
        data = json.loads(_cache_file(home, name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    tools = data.get("tools") if isinstance(data, dict) else None
    return [t for t in tools if isinstance(t, dict) and t.get("name")] if isinstance(tools, list) else None


def _write_tools(home: Path, name: str, cfg, tools: list, instructions) -> None:
    from halo_harness.mcp import tools_cache
    path = _cache_file(home, name)
    data = {"hash": tools_cache.config_cache_key(cfg), "tools": [tools_cache.tool_to_dict(t) for t in tools],
            "instructions": instructions, "cached_at": time.time()}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + f".tmp{os.getpid()}.{threading.get_ident()}")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass


def live_tools(home: Path, name: str, cfg, cwd: Path) -> Optional[list]:
    """Connect once through a throwaway one-server McpManager, write the tool cache, return
    `[{name, description}]` (None when the server did not connect)."""
    from halo_harness.mcp.doctor_deep import resolve_tool_env
    from halo_harness.mcp.manager import McpManager
    mgr = McpManager({name: cfg}, tool_env=resolve_tool_env(cwd), cwd=cwd)
    h = mgr.handles[name]
    try:
        h.start()
        if h.state != "connected":
            return None
        tools = list(h.tools)
        _write_tools(home, name, cfg, tools, h.instructions)
        return [{"name": getattr(t, "name", ""), "description": getattr(t, "description", None) or ""} for t in tools]
    finally:
        try:
            mgr.close_all(timeout=5.0)
        except Exception:
            pass


def _configs(cwd: Path) -> dict:
    from halo_harness.config.claude_json import load_claude_json
    from halo_harness.mcp.manager import resolve_server_configs
    from halo_harness.mcp_setup import load_mcp_approvals
    resolved, _notices = resolve_server_configs(cwd=Path(cwd), claude_json=load_claude_json(), print_mode=False,
                                                approvals=load_mcp_approvals())
    return resolved


def _tool_rows(raw: list) -> list:
    out = []
    for t in raw:
        desc = " ".join(str(t.get("description") or "").split())
        out.append({"name": str(t.get("name")), "desc": desc[:DESC_MAX] + ("..." if len(desc) > DESC_MAX else "")})
    return sorted(out, key=lambda t: t["name"])


def _connectors() -> list:
    """claude.ai connectors from their discovery cache (never a `claude` start here)."""
    try:
        from halo_harness.mcp import connectors_bridge
        rows, _at = connectors_bridge.load_cache()
    except Exception:
        return []
    out = []
    for c in rows or []:
        name = str(getattr(c, "slug", "") or getattr(c, "name", "") or "")
        if name:
            tools = [{"name": str(t), "desc": ""} for t in (getattr(c, "tools", None) or [])]
            out.append({"name": f"claude.ai {getattr(c, 'name', name)}", "transport": "connector", "tools": tools or None,
                        **({} if tools else {"note": "a claude.ai connector; its tools list when it connects"})})
    return out


def mcp_servers(home: Path, cwd: Path, *, spawn: bool, timeout: float = MCP_TIMEOUT_S,
                probe: Optional[Callable] = None) -> list:
    """`[{name, transport, tools: [{name, desc}] | None, note?}]` for every configured server."""
    try:
        configs = _configs(cwd)
    except Exception as e:
        return [{"name": "(config)", "transport": "-", "tools": None, "note": f"could not read the MCP config ({type(e).__name__})"}]
    probe = probe or live_tools
    rows, waits = [], []
    for name in sorted(configs, key=str.lower):
        cfg = configs[name]
        row = {"name": name, "transport": cfg.type, "tools": None}
        rows.append(row)
        if cfg.disabled_reason or cfg.pending_approval:
            row["note"] = "disabled" if cfg.disabled_reason else "waiting for project approval"
            continue
        cached = _cached_tools(home, name)
        if cached is not None:
            row["tools"] = _tool_rows(cached)
            continue
        if not spawn:
            row["note"] = "no cached tool list yet (it is written the first time the server connects)"
            continue
        waits.append((row, _start_probe(home, name, cfg, cwd, probe)))
    deadline = time.monotonic() + timeout
    for row, slot in waits:
        slot["done"].wait(max(0.0, deadline - time.monotonic()))
        if slot["done"].is_set() and slot.get("tools") is not None:
            row["tools"] = _tool_rows(slot["tools"])
        else:
            row["note"] = (f"no answer within {timeout:g} s; listed on the next refresh" if not slot["done"].is_set()
                           else f"did not connect{(': ' + slot['error']) if slot.get('error') else ''}")
    return rows + _connectors()


def _start_probe(home: Path, name: str, cfg, cwd: Path, probe: Callable) -> dict:
    key = (str(home), name)
    with _lock:
        slot = _inflight.get(key)
        if slot is not None and not slot["done"].is_set():
            return slot  # still connecting from an earlier gather: wait on that one
        slot = _inflight[key] = {"done": threading.Event()}

    def run() -> None:
        try:
            slot["tools"] = probe(home, name, cfg, cwd)
        except Exception as e:
            slot["error"] = f"{type(e).__name__}"[:80]
        finally:
            slot["done"].set()
    threading.Thread(target=run, daemon=True, name=f"halo-caps-mcp-{name[:16]}").start()
    return slot
