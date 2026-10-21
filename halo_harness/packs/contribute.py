"""halo_harness.packs.contribute -- what an active pack adds to a session
(Halo 3.2.0.0 R1). A pack that is disabled, or has a problem, adds nothing.

- `pack_plugin_roots(cwd=...)`: every active pack's root, for
  `headless.build_session`'s plugin-root list -- its skills (`<id>:<skill>`),
  commands (`<id>:<command>`), `agents/*.md`, hooks and MCP servers
  (`plugin_<id>_<server>`) load through the plugin-root channel unchanged.
- `hook_roots(roots)` drops a pack root whose `hooks` permission is not
  granted; `mcp_filter(root)` is the set of a pack's MCP servers that are
  granted (`mcp:<server>`, and `network` for one reached by url).
- `agent_dirs` / `team_dirs`: the pack tier of `agent_search_dirs` and
  `team_search_dirs` (after the home's folder, before the shipped one):
  `agents/*.yaml` and `teams/*.yaml` read in place, label `pack:<id>`,
  listed as `<id>--<name>` (`folder_names`, `folder_file`); `localize`
  attaches `_pack`, `_name` and `_pack_scope` and qualifies the names a
  pack's file uses for its own bios and lineups.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from halo_harness.packs import names as N
from halo_harness.packs.names import read_only_source  # noqa: F401  (re-exported: the read-only rule)


def _active(cwd=None, state_dir=None) -> list:
    from halo_harness.packs.registry import active
    try:
        return active(cwd=cwd, state_dir=state_dir)
    except Exception:  # an unreadable pack folder never breaks a session
        return []


def pack_plugin_roots(*, cwd=None, state_dir=None) -> "list[str]":
    return [str(p.root) for p in _active(cwd, state_dir)]


def agent_dirs(*, cwd=None, state_dir=None) -> "list[tuple[Path, str]]":
    return [(p.root / "agents", N.pack_source(p.id)) for p in _active(cwd, state_dir)]


def team_dirs(*, cwd=None, state_dir=None) -> "list[tuple[Path, str]]":
    return [(p.root / "teams", N.pack_source(p.id)) for p in _active(cwd, state_dir)]


def _stems(d: Path, skip: str = "") -> "list[str]":
    try:
        return [p.stem for p in d.glob("*.yaml") if p.is_file() and not (skip and p.name.endswith(skip))]
    except OSError:
        return []


def folder_names(d: Path, source: str, *, skip: str = "") -> "list[str]":
    """The names a search folder lists: its file stems, qualified `<id>--<stem>` for a pack's folder."""
    pack_id = N.pack_of_source(source)
    stems = [s for s in _stems(Path(d), skip) if not pack_id or N.is_valid_name(s)]
    return [N.qualify(pack_id, s) for s in stems] if pack_id else stems


def folder_file(d: Path, source: str, name: str) -> Optional[Path]:
    """The file `name` would be in search folder `d` (None in a pack's folder for a name that is not the pack's)."""
    pack_id = N.pack_of_source(source)
    if not pack_id:
        return Path(d) / f"{name}.yaml"
    owner, rest = N.unqualify(name)
    return Path(d) / f"{rest}.yaml" if owner == pack_id else None


def _pack(pack_id: str, cwd=None, state_dir=None):
    from halo_harness.packs.registry import snapshot
    return snapshot(cwd=cwd, state_dir=state_dir).pack(pack_id)


def localize(data: dict, source: str, name: str, *, kind: str, cwd=None, state_dir=None) -> dict:
    """A pack file's data as Halo lists it: `_pack`, `_name`, `_pack_scope`, and its own names qualified
    (a lineup's `agents[].agent` and `extends`, a bio's `extends`, when the pack has that bio or lineup)."""
    pack_id = N.pack_of_source(source)
    if not pack_id:
        return data
    pack = _pack(pack_id, cwd, state_dir)
    root = pack.root if pack is not None else None
    bios = set(_stems(root / "agents")) if root is not None else set()
    lineups = set(_stems(root / "teams")) if root is not None else set()
    out = dict(data)
    out["_pack"], out["_name"] = pack_id, N.unqualify(name)[1]
    out["_pack_scope"] = pack.scope if pack is not None else ""
    own_parent = lineups if kind == "lineup" else bios
    if isinstance(out.get("extends"), str) and out["extends"].strip() in own_parent:
        out["extends"] = N.qualify(pack_id, out["extends"].strip())
    if kind == "lineup" and isinstance(out.get("agents"), list):
        out["agents"] = [{**e, "agent": N.qualify(pack_id, e["agent"].strip())}
                         if isinstance(e, dict) and isinstance(e.get("agent"), str) and e["agent"].strip() in bios
                         else e for e in out["agents"]]
    return out


def _granted(pack, state_dir=None) -> "set[str]":
    from halo_harness.packs import state as S
    return set(S.granted(pack.id, S.load(state_dir)))


def _active_pack_for_root(root, state_dir=None):
    from halo_harness.packs.discover import same_path
    for p in _active(None, state_dir) + _active_for_root_cwd(root, state_dir):
        if same_path(p.root, root):
            return p
    return None


def _active_for_root_cwd(root, state_dir=None) -> list:
    """A project pack's root is `<repo>/.halo/packs/<id>`: read that repo's active packs too."""
    root = Path(root)
    if root.parent.name == "packs" and root.parent.parent.name == ".halo":
        return _active(root.parent.parent.parent, state_dir)
    return []


def hook_roots(roots, *, state_dir=None) -> list:
    """`roots` without the active packs whose `hooks` permission is not granted (other roots unchanged)."""
    out = []
    for root in roots or []:
        pack = _active_pack_for_root(root, state_dir)
        if pack is None or "hooks" in _granted(pack, state_dir):
            out.append(root)
    return out


def mcp_filter(root, *, state_dir=None) -> "Optional[set[str]]":
    """The MCP server names an active pack may start (None: `root` is not an active pack, no filter)."""
    from halo_harness.packs import manifest as MF
    pack = _active_pack_for_root(root, state_dir)
    if pack is None:
        return None
    granted = _granted(pack, state_dir)
    allowed = set()
    for server, raw in MF.mcp_servers(pack.root).items():
        url = isinstance(raw, dict) and bool(raw.get("url"))
        if MF.MCP_PREFIX + server in granted and (not url or "network" in granted):
            allowed.add(server)
    return allowed
