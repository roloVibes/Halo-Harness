"""halo_harness.where.claude_files -- the Claude Code files Halo reads, for
`halo config where`: every `settings.json` layer `resolve_settings` loads
(user, project, local, a `--settings` value, managed) and every place an MCP
server comes from (`~/.claude.json`, its projects entry for this folder,
`.mcp.json`, `managed-mcp.json`).

Precedence: a settings key goes to the layer whose value the merge kept
(the highest layer that set it; a list, `env` or `hooks` set in several
layers is merged, and the row says so); an MCP server name goes to the scope
`mcp.manager.resolve_server_configs` resolved it from.
"""

from __future__ import annotations

from pathlib import Path

from halo_harness.where.rows import make, settle

_LAYER_SCOPE = {"userSettings": "home", "projectSettings": "repo", "localSettings": "repo",
                "flagSettings": "env", "policySettings": "home"}
_LAYER_NOTE = {"userSettings": "Claude Code's user settings", "projectSettings": "this repo's shared settings",
               "localSettings": "this repo's own, uncommitted settings", "flagSettings": "the --settings value",
               "policySettings": "managed settings (highest)"}


def settings_rows(cwd: Path, settings_flag=None) -> list:
    from halo_harness.config.claude_json import is_trusted, load_claude_json
    from halo_harness.config.settings import resolve_settings
    trusted = is_trusted(cwd, load_claude_json())
    resolved = resolve_settings(cwd, settings_flag=settings_flag, trusted=trusted)
    layers = list(resolved.layers)
    rows = []
    for rank, layer in enumerate(reversed(layers), start=1):
        path = layer.path if layer.path is not None else Path("(--settings inline JSON)")
        note = _LAYER_NOTE.get(layer.name, layer.name)
        if layer.error is not None:
            note = f"{note}; {layer.error.message}"
        elif layer.name in ("projectSettings", "localSettings") and not trusted and layer.data:
            note = f"{note}; this folder is not trusted, so its allow rules, env and hooks are dropped"
        row = make("settings", path, _LAYER_SCOPE.get(layer.name, "home"), cwd=cwd, sets=sorted(layer.data),
                   rank=rank, note=note, label=None if layer.path is not None else "--settings (inline JSON)")
        rows.append(row)
    by_path = {row["path"]: layer for row, layer in zip(rows, reversed(layers))}
    merged = resolved.raw

    def winner(key):
        for row in rows:
            layer = by_path[row["path"]]
            if key in layer.data and layer.data[key] == merged.get(key):
                return row["path"]
        return f"merged from every layer that sets {key}"
    return settle(rows, winner, cwd=cwd)


def mcp_rows(cwd: Path, settings_flag=None) -> list:
    from halo_harness.config.claude_json import load_claude_json
    from halo_harness.config.paths import claude_json_path, lookup_project
    from halo_harness.mcp_setup import managed_mcp_json_path
    cj = load_claude_json()
    proj = lookup_project(cj, cwd) if isinstance(cj, dict) else {}
    user = cj.get("mcpServers") if isinstance(cj.get("mcpServers"), dict) else {}
    local = proj.get("mcpServers") if isinstance(proj.get("mcpServers"), dict) else {}
    dot = Path(cwd) / ".mcp.json"
    dot_names = _servers(dot)
    managed = managed_mcp_json_path()
    managed_names = _servers(managed)
    local_label = "~/.claude.json (projects entry for this folder)"
    rows = [
        make("mcp", managed, "home", cwd=cwd, sets=managed_names, rank=1,
             note="managed: when present, the only servers loaded"),
        make("mcp", str(claude_json_path()) + "#projects", "home", cwd=cwd, sets=sorted(local), rank=2,
             label=local_label, note="servers added with claude mcp add --scope local"),
        make("mcp", dot, "repo", cwd=cwd, sets=dot_names, rank=3, note="the repo's servers (asks once per server)"),
        make("mcp", claude_json_path(), "home", cwd=cwd, sets=sorted(user), rank=4, note="user servers"),
    ]
    rows[1]["exists"] = bool(local)
    scope_row = {"managed": rows[0], "local": rows[1], "project": rows[2], "user": rows[3]}
    try:
        from halo_harness.mcp.manager import resolve_server_configs
        from halo_harness.config.settings import resolve_settings
        resolved, _notices = resolve_server_configs(cwd=Path(cwd), claude_json=cj, plugin_servers={},
                                                    env_for_expansion={}, settings=resolve_settings(cwd, settings_flag=settings_flag))
    except Exception:
        resolved = {}

    def winner(name):
        cfg = resolved.get(name)
        row = scope_row.get(getattr(cfg, "scope", ""))
        return row["path"] if row is not None else None
    return settle(rows, winner, cwd=cwd)


def _servers(path: Path) -> list:
    import json
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return []
    servers = data.get("mcpServers", data) if isinstance(data, dict) else {}
    return sorted(servers) if isinstance(servers, dict) else []


def claude_rows(cwd: Path, settings_flag=None) -> list:
    return settings_rows(cwd, settings_flag) + mcp_rows(cwd, settings_flag)
