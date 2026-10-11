"""halo_harness.design.crafts_probe -- which craft apps are really there
(Halo 3.0.1.0 round D4): the registered servers from the same user/project
MCP config every Halo session loads (`config.claude_json`), their parsed
configs, and a live probe that spawns each one through the ordinary
`McpManager` handshake (never a second JSON-RPC client), counts its tools
and checks that the app's render tool is among them. `halo design doctor
--probe` prints it; a design turn only names apps that are registered.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Optional

from halo_harness.design.crafts import APPS


def craft_server_entries(claude_json: Optional[dict] = None, cwd: Optional[Path] = None) -> dict:
    """{app: raw server entry} for every registered craft app (lower-cased
    names; project scope wins collisions, like any session)."""
    from halo_harness.config.claude_json import load_claude_json, mcp_servers_for
    data = load_claude_json() if claude_json is None else claude_json
    servers = mcp_servers_for(Path(cwd or os.getcwd()), data)
    return {name.lower(): raw for name, raw in servers.items() if isinstance(raw, dict) and name.lower() in APPS}


def registered_craft_servers(claude_json: Optional[dict] = None, cwd: Optional[Path] = None) -> set:
    try:
        return set(craft_server_entries(claude_json, cwd))
    except Exception:
        return set()


def craft_server_configs(claude_json: Optional[dict] = None, cwd: Optional[Path] = None) -> dict:
    """{app: McpServerConfig} via the manager's own parser."""
    from halo_harness.mcp.manager import parse_server
    out = {}
    for app, raw in craft_server_entries(claude_json, cwd).items():
        cfg = parse_server(app, raw, scope="user")
        if cfg is not None:
            out[app] = cfg
    return out


def _tool_names(handle) -> list:
    names = []
    for t in getattr(handle, "tools", None) or []:
        n = getattr(t, "name", None) or (t.get("name") if isinstance(t, dict) else None)
        if n:
            names.append(str(n))
    return names


def probe_craft(app: str, cfg, *, tool_env: Optional[dict] = None, cwd: Optional[Path] = None) -> dict:
    """Spawn one craft server, initialize, list tools, close. Returns
    {app, state, tool_count, render_tool, render_present, error, elapsed}."""
    from halo_harness.mcp.manager import McpManager, mcp_timeout_s
    render = APPS[app]["render"].split("__", 2)[-1] if app in APPS else ""
    mgr = McpManager({app: cfg}, tool_env=dict(os.environ if tool_env is None else tool_env), cwd=cwd or Path(os.getcwd()))
    h = mgr.handles[app]
    t0 = time.monotonic()
    try:
        h.start()
    except Exception as e:  # the handle records its own error; keep the message
        err = f"{type(e).__name__}: {e}"
    else:
        err = ""
    finally:
        names = _tool_names(h)
        snap = {"app": app, "state": getattr(h, "state", "unknown"), "tool_count": len(names), "render_tool": render,
                "render_present": bool(render) and render in names,
                "error": getattr(h, "error", None) or getattr(h, "tools_fetch_failed_error", None) or "",
                "elapsed": round(time.monotonic() - t0, 2)}
        mgr.close_all(timeout=mcp_timeout_s() + 5.0)
    if err and not snap["error"]:
        snap["error"] = err
    return snap


def probe_crafts(configs: Optional[dict] = None, *, tool_env: Optional[dict] = None, cwd: Optional[Path] = None) -> list:
    configs = craft_server_configs(cwd=cwd) if configs is None else configs
    return [probe_craft(app, cfg, tool_env=tool_env, cwd=cwd) for app, cfg in configs.items()]


def probe_lines(rows: list) -> list:
    out = []
    for r in rows:
        if r["state"] == "connected" and r["tool_count"]:
            verdict = f"up, {r['tool_count']} tool(s), render tool {r['render_tool']} {'present' if r['render_present'] else 'MISSING'}"
        else:
            verdict = f"{r['state']}: {r['error'] or 'no tools listed'}"
        out.append(f"  {r['app']:<12} {verdict}  ({r['elapsed']}s)")
    return out
