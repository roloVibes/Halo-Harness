"""The design pack's server/crafts_probe.py (was halo_harness.design.crafts_probe) -- which craft apps are really
there (Halo 3.0.1.0 round D4): the registered servers from the same user/project MCP config every Halo session loads
(`ext.host.mcp_servers`), and a live probe that starts each one through Halo's own MCP handshake
(`ext.host.mcp_probe`), counts its tools and checks that the app's render tool is among them. The pack's
`GET crafts?probe=1` route says it; a design turn only names apps that are registered.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from halo_harness.ext import host

from .crafts import APPS


def craft_server_entries(claude_json: Optional[dict] = None, cwd: Optional[Path] = None) -> dict:
    """{app: raw server entry} for every registered craft app (lower-cased
    names; project scope wins collisions, like any session)."""
    servers = host.mcp_servers(cwd, claude_json=claude_json)
    return {name.lower(): raw for name, raw in servers.items() if isinstance(raw, dict) and name.lower() in APPS}


def registered_craft_servers(claude_json: Optional[dict] = None, cwd: Optional[Path] = None) -> set:
    try:
        return set(craft_server_entries(claude_json, cwd))
    except Exception:
        return set()


def craft_server_configs(claude_json: Optional[dict] = None, cwd: Optional[Path] = None) -> dict:
    """{app: its server entry}: what a probe starts."""
    return dict(craft_server_entries(claude_json, cwd))


def probe_craft(app: str, entry: dict, *, tool_env: Optional[dict] = None, cwd: Optional[Path] = None) -> dict:
    """Start one craft server, initialize, list tools, close. Returns
    {app, state, tool_count, render_tool, render_present, error, elapsed}."""
    render = APPS[app]["render"].split("__", 2)[-1] if app in APPS else ""
    got = host.mcp_probe(app, entry, cwd=cwd, env=tool_env)  # the same key-stripped env a session gives its servers
    names = list(got.get("tools") or [])
    return {"app": app, "state": got.get("state", "unknown"), "tool_count": len(names), "render_tool": render,
            "render_present": bool(render) and render in names, "error": got.get("error") or "",
            "elapsed": got.get("elapsed", 0.0)}


def probe_crafts(configs: Optional[dict] = None, *, tool_env: Optional[dict] = None, cwd: Optional[Path] = None) -> list:
    configs = craft_server_configs(cwd=cwd) if configs is None else configs
    return [probe_craft(app, entry, tool_env=tool_env, cwd=cwd) for app, entry in configs.items()]


def probe_lines(rows: list) -> list:
    out = []
    for r in rows:
        if r["state"] == "connected" and r["tool_count"]:
            verdict = f"up, {r['tool_count']} tool(s), render tool {r['render_tool']} {'present' if r['render_present'] else 'MISSING'}"
        else:
            verdict = f"{r['state']}: {r['error'] or 'no tools listed'}"
        out.append(f"  {r['app']:<12} {verdict}  ({r['elapsed']}s)")
    return out
