"""halo_harness.doctor_config_conflicts -- the "same key, two files, two
values" findings of `halo doctor --config`.

Read off `halo config where`'s rows: every `loses` entry names a key this
file sets and the file that decides it; when the losing file's value and
the winning file's value differ, that is one `conflict` finding naming the
winner. Overriding a shipped template is how a template is customised, so a
shipped row never takes part; an active lineup extending another is
inheritance, not a clash, so those rows do not either. A variable in the env
file that the process environment also sets (with another value) is a
conflict the environment wins.
"""

from __future__ import annotations

import json
from pathlib import Path

_MISSING = object()


def _json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _yaml(path: Path):
    import yaml
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return _MISSING


def _mcp(row: dict, cwd) -> dict:
    from halo_harness.config.claude_json import load_claude_json
    from halo_harness.config.paths import lookup_project
    if row["path"].endswith("#projects"):
        proj = lookup_project(load_claude_json(), Path(cwd) if cwd is not None else Path.cwd()) or {}
        return proj.get("mcpServers") if isinstance(proj.get("mcpServers"), dict) else {}
    data = _json(Path(row["path"]))
    servers = data.get("mcpServers", data if "managed" in row["note"] else {})
    return servers if isinstance(servers, dict) else {}


def value_of(row: dict, key: str, cwd=None):
    """The value `row`'s file gives `key`, or _MISSING."""
    kind, path = row["kind"], Path(row["path"])
    if kind in ("settings", "config", "team-preset"):
        return _json(path).get(key, _MISSING)
    if kind == "mcp":
        return _mcp(row, cwd).get(key, _MISSING)
    if kind == "env":
        from halo_harness.providers.config import _parse_env_file
        return _parse_env_file(path).get(key, _MISSING)
    if kind in ("lineups", "bios"):
        return _yaml(path / f"{key}.yaml")
    if kind == "team":
        return _yaml(path)
    return _MISSING


def _routes_default(row: dict, cwd):
    from halo_harness.where.rows import display
    routes = Path(row["path"]).parent / "routes.json"
    return display(routes, cwd=cwd), _json(routes).get("default", _MISSING)


def _settings_theme(row: dict, cwd):
    from halo_harness.config.settings import resolve_settings
    try:
        layers = list(resolve_settings(Path(cwd) if cwd is not None else Path.cwd()).layers)
    except Exception:
        return None, _MISSING
    from halo_harness.where.rows import display
    for layer in reversed(layers):
        if "theme" in layer.data and layer.path is not None:
            return display(layer.path, cwd=cwd), layer.data["theme"]
    return None, _MISSING


# A config.json key decided by another file under another name (where/halo_files.py).
_NAMED = {"routes.json default": _routes_default, "settings.json theme": _settings_theme}


def _winner_row(rows: list, row: dict, entry: dict):
    """The row of the same kind that holds the winning file."""
    target = entry.get("to_path") or ""
    if not target:
        return None
    for r in rows:
        if r["kind"] == row["kind"] and (r["path"] == target or target in r["files"]):
            return r
    return None


def conflict_findings(rows: list, *, cwd=None) -> list:
    from halo_harness.doctor_config import finding
    out = []
    for row in rows:
        if row["scope"] == "shipped" or row["kind"] == "lineup" or not row["exists"]:
            continue
        for entry in row["loses"]:
            key, to = entry["key"], entry["to"]
            if row["kind"] == "env" and to == "the process environment":
                out.append(finding("conflict", "warns", row, f"{key} is set in {row['file']} and in the process "
                                   f"environment with different values; the process environment wins", key=key,
                                   fix=f"unset {key} in the shell, or change it in {row['file']}"))
                continue
            if row["kind"] == "config" and to in _NAMED:
                win, theirs = _NAMED[to](row, cwd)
                if win is not None and theirs is not _MISSING and theirs != value_of(row, key, cwd):
                    out.append(finding("conflict", "warns", row, f"{key} is set in {row['file']} and in {win} with "
                                       f"different values; {win} wins", key=key,
                                       fix=f"keep one: edit {row['file']} or {win}"))
                continue
            win = _winner_row(rows, row, entry)
            if win is None or win["scope"] == "shipped" or win is row:
                continue
            mine, theirs = value_of(row, key, cwd), value_of(win, key, cwd)
            if mine is _MISSING or theirs is _MISSING or mine == theirs:
                continue
            if row["kind"] == "team":
                out.append(finding("conflict", "warns", row, f"{row['file']} and {to} are both a team file for this "
                                   f"repo; {to} wins", key="team", fix=f"remove {row['file']}, or move it"))
                continue
            tags = [key] if row["kind"] == "lineups" else []
            what = {"lineups": "lineup", "bios": "bio", "mcp": "MCP server"}.get(row["kind"], "key")
            out.append(finding("conflict", "warns", row, f"{what} {key!r} is set in {row['file']} and in {to} with "
                               f"different values; {to} wins", key=key, lineups=tags,
                               fix=f"keep one: edit or remove it in {row['file']}"))
    return out
