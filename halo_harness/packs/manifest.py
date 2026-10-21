"""halo_harness.packs.manifest -- a pack's `pack.yaml` (Halo 3.2.0.0 R1,
docs/EXTENSION_API.md "The manifest").

    data, problems = load_manifest(root)     # read through agents_yaml._read_yaml_file
    validate_manifest(data, root=root)       # [] when valid; one line per problem

Shape comes from `schemas.check_file_shape("pack", ...)` (an unknown key
names the closest known one); meaning is checked here: the id rule, a
semver `version`, the `halo_api` / `halo` ranges, `requires`, the
permission names, `migrations`, and (with `root`) that every file
`contributes` names is there and that a contribution's permission is
requested. A pack folder is a Claude-plugin layout plus `pack.yaml`, so
`skills`, `commands` and `hooks` name the plugin layout's own places.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from halo_harness.packs import names as N
from halo_harness.packs import semver as V

MANIFEST = "pack.yaml"
#: The names `permissions:` takes besides `mcp:<server>` (one per MCP server a pack declares).
PERMISSIONS = ("hooks", "bash", "network", "home-write")
MCP_PREFIX = "mcp:"
CAPABILITY_RE = re.compile(r"^[a-z][a-z0-9._-]*$")
EVENT_RE = re.compile(r"^[a-z][a-z0-9_.-]*$")
#: The plugin layout's own places for these contributions (the plugin-root channel reads exactly these).
LAYOUT = {"skills": "skills", "commands": "commands", "hooks": "hooks/hooks.json"}
REQUIRED = ("id", "name", "version", "halo_api")


def manifest_path(root) -> Path:
    return Path(root) / MANIFEST


def load_manifest(root) -> "tuple[Optional[dict], list[str]]":
    """`(data, [])`, or `(None, [one line])` when pack.yaml is missing or is not a YAML mapping."""
    from halo_harness.agents_yaml import _read_yaml_file
    path = manifest_path(root)
    if not path.is_file():
        return None, [f"no {MANIFEST} in {Path(root).name or root}"]
    data = _read_yaml_file(path)
    if data is None:
        return None, [f"{MANIFEST} does not read as a YAML mapping (key: value)"]
    return data, []


def mcp_servers(root) -> dict:
    """The MCP servers the pack's plugin layout declares (`.mcp.json`, else `.claude-plugin/plugin.json`)."""
    from halo_harness.config.plugins import _read_plugin_mcp_servers
    try:
        return dict(_read_plugin_mcp_servers(Path(root)))
    except Exception:
        return {}


def requested(data) -> "list[str]":
    perms = (data or {}).get("permissions") if isinstance(data, dict) else None
    return [p for p in perms if isinstance(p, str)] if isinstance(perms, list) else []


def needed(data, root) -> "list[tuple[str, str]]":
    """`[(permission, what needs it)]`: hooks/hooks.json needs hooks, each MCP server mcp:<server>,
    an MCP server reached by url needs network too."""
    out: "list[tuple[str, str]]" = []
    if root is not None and (Path(root) / LAYOUT["hooks"]).is_file():
        out.append(("hooks", LAYOUT["hooks"]))
    for server, raw in sorted(mcp_servers(root).items()) if root is not None else []:
        out.append((MCP_PREFIX + server, f"MCP server {server}"))
        if isinstance(raw, dict) and raw.get("url"):
            out.append(("network", f"MCP server {server} (a url)"))
    return out


def _permission_lines(data, root) -> "list[str]":
    out: "list[str]" = []
    servers = set(mcp_servers(root)) if root is not None else None
    for p in requested(data):
        if p.startswith(MCP_PREFIX):
            server = p[len(MCP_PREFIX):]
            if not server:
                out.append(f"permissions: {p!r} names no MCP server (mcp:<server>)")
            elif servers is not None and server not in servers:
                out.append(f"permissions: {p!r} names an MCP server the pack does not declare in .mcp.json")
        elif p not in PERMISSIONS:
            out.append(f"permissions: {p!r} is not one of mcp:<server>, {', '.join(PERMISSIONS)}")
    if root is not None:
        asked = set(requested(data))
        for perm, why in needed(data, root):
            if perm not in asked:
                out.append(f"permissions: {why} needs {perm!r}, which the pack does not request")
    return out


def _file_lines(data, root: Path) -> "list[str]":
    contributes = data.get("contributes") if isinstance(data.get("contributes"), dict) else {}
    out: "list[str]" = []
    for kind, folder in (("agents", "agents"), ("teams", "teams")):
        for rel in _list(contributes, kind):
            if not isinstance(rel, str):
                continue
            p = Path(rel)
            suffixes = (".yaml", ".md") if kind == "agents" else (".yaml",)
            if p.is_absolute() or ".." in p.parts or len(p.parts) != 2 or p.parts[0] != folder \
                    or p.suffix not in suffixes:
                out.append(f"contributes.{kind}: {rel!r} is not {folder}/<name>{' or '.join(suffixes)}")
            elif p.suffix == ".yaml" and not N.is_valid_name(p.stem):
                out.append(f"contributes.{kind}: {p.stem!r} is not a valid name (letters, digits, - and _)")
            elif not (root / p).is_file():
                out.append(f"contributes.{kind}: {rel} is not in the pack")
    for kind, place in LAYOUT.items():
        value = contributes.get(kind)
        if value is None:
            continue
        if Path(str(value)).as_posix().rstrip("/") != place:
            out.append(f"contributes.{kind}: {value!r} -- a pack's {kind} live at {place} (the plugin layout)")
        elif not (root / place).exists():
            out.append(f"contributes.{kind}: {place} is not in the pack")
    servers = mcp_servers(root)
    for i, entry in enumerate(_list(contributes, "mcp")):
        name = entry.get("name") if isinstance(entry, dict) else None
        if not isinstance(name, str) or not name:
            out.append(f"contributes.mcp[{i}]: a name is required")
        elif name not in servers:
            out.append(f"contributes.mcp[{i}]: {name!r} is not a server in the pack's .mcp.json")
    plugin_name = _plugin_json_name(root)
    if plugin_name and plugin_name != data.get("id"):
        out.append(f".claude-plugin/plugin.json names the plugin {plugin_name!r}; a pack's plugin name is its id")
    return out


def _plugin_json_name(root: Path) -> str:
    import json
    try:
        raw = json.loads((root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return ""
    name = raw.get("name") if isinstance(raw, dict) else None
    return name.strip() if isinstance(name, str) else ""


def _list(data: dict, key: str) -> list:
    value = data.get(key)
    return value if isinstance(value, list) else []


def _meaning_lines(data) -> "list[str]":
    out = [f"{key}: required" for key in REQUIRED if data.get(key) in (None, "")]
    if data.get("id") not in (None, "") and N.pack_id_problem(data.get("id")):
        out.append(N.pack_id_problem(data.get("id")))
    version = data.get("version")
    if version not in (None, "") and not V.is_semver(version):
        out.append(f"version {version!r} is not semver (1.2.3)")
    for key in ("halo_api", "halo"):
        line = V.range_problem(data.get(key), where=key)
        if line:
            out.append(line)
    if isinstance(data.get("halo_api"), dict) and data["halo_api"].get("min") is None:
        out.append("halo_api.min: required (the extension API version the pack was written for, 1.0)")
    for cap in _list(data, "capabilities"):
        if isinstance(cap, str) and not CAPABILITY_RE.match(cap):
            out.append(f"capabilities: {cap!r} is not a capability name (lower-case, digits, . _ -)")
    for i, req in enumerate(_list(data, "requires")):
        if not isinstance(req, dict):
            continue
        if not N.is_valid_pack_id(req.get("pack")):
            out.append(f"requires[{i}]: pack {req.get('pack')!r} is not a pack id")
        elif req.get("pack") == data.get("id"):
            out.append(f"requires[{i}]: a pack does not require itself")
        rng = requirement_range(req)
        line = V.range_problem(rng, where=f"requires[{i}].version") if rng is not None else ""
        if rng is None:
            line = f"requires[{i}].version {req.get('version')!r} is not a version or a {{min, max}} range"
        if line:
            out.append(line)
    for i, m in enumerate(_list(data, "migrations")):
        if isinstance(m, dict):
            for key in ("from", "to"):
                if V.release(m.get(key)) is None:
                    out.append(f"migrations[{i}].{key}: {m.get(key)!r} is not a version")
            if not isinstance(m.get("note"), str) or not m["note"].strip():
                out.append(f"migrations[{i}].note: required (what changes for you)")
    for name in _list(data.get("contributes") if isinstance(data.get("contributes"), dict) else {}, "events"):
        if isinstance(name, str) and not EVENT_RE.match(name):
            out.append(f"contributes.events: {name!r} is not an event name (lower-case, digits, . _ -)")
    from halo_harness.packs.bio_rules import declared_workflows  # 3.2.0.0 R2: the names a lineup's workflows use
    out += [f"contributes.workflows: {w!r} is not a name (letters, digits, - and _)"
            for w in declared_workflows(data) if not N.is_valid_name(w)]
    return out


def requirement_range(req: dict) -> "Optional[dict]":
    """A `requires[]` entry's version as a range: a bare version is a minimum; None when malformed."""
    v = req.get("version")
    if v is None:
        return {}
    if isinstance(v, dict):
        return v
    return {"min": v} if V.release(v) is not None else None


def validate_manifest(data, *, root=None, folder_is_id: bool = False) -> "list[str]":
    """One line per problem; `[]` means valid. `root` checks the files; `folder_is_id` that the folder is named by the id."""
    from halo_harness.schemas import check_file_shape
    if not isinstance(data, dict):
        return [f"{MANIFEST} is a YAML mapping (key: value)"]
    out = [f["text"] for f in check_file_shape("pack", data)]
    out += _meaning_lines(data)
    if root is not None:
        root = Path(root)
        out += _file_lines(data, root)
        out += _permission_lines(data, root)
        from halo_harness.packs.bio_rules import roles_lines  # 3.2.0.0 R2: what a pack's bios and lineups may say
        out += roles_lines(data, root)
        if folder_is_id and isinstance(data.get("id"), str) and root.name != data["id"]:
            out.append(f"the folder is named {root.name!r}; a pack's folder is named by its id {data['id']!r}")
    else:
        out += _permission_lines(data, None)
    return out
