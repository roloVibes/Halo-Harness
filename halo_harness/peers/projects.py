"""halo_harness.peers.projects -- the repos this harness works in, for its capabilities catalog (Halo 3.0.6.0 R6
as fleet/capabilities_sources.projects; 3.4.0.0 D: core, so packs/capability_check.host_catalog reads it with the
fleet pack off). Each row is {name, repo, branch} (the basename, never a full path), from the live sessions'
registry, Studio's folder and the newest history lines, at most PROJECTS_MAX.
"""

from __future__ import annotations

import json
from pathlib import Path

PROJECTS_MAX = 8


def _registry_roots(home: Path) -> list:
    """Project roots of the live sessions, read from the registry file (never pruned here)."""
    from halo_harness.remote import registry
    path = home / "run" / registry.FILENAME
    if not path.is_file():
        return []
    roots = []
    for e in registry._load(path):
        p = e.get("project") if isinstance(e, dict) else None
        if isinstance(p, dict) and p.get("root"):
            roots.append(str(p["root"]))
        elif isinstance(e, dict) and e.get("cwd"):
            roots.append(str(e["cwd"]))
    return roots


def _history_roots(home: Path, limit: int = 200) -> list:
    path = home / "history.jsonl"
    try:
        with path.open("rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 256_000))
            lines = f.read().decode("utf-8", errors="replace").splitlines()[-limit:]
    except OSError:
        return []
    out = []
    for line in reversed(lines):
        try:
            cwd = json.loads(line).get("project")
        except (ValueError, AttributeError):
            continue
        if isinstance(cwd, str) and cwd and cwd not in out:
            out.append(cwd)
    return out


def projects(home: Path, cwd: Path) -> list:
    from halo_harness.remote.session_identity import project
    seen, out = set(), []
    for root in _registry_roots(home) + [str(cwd)] + _history_roots(home):
        if len(out) >= PROJECTS_MAX:
            break
        if not Path(root).is_dir():
            continue
        p = project(root)
        top = str(p.get("root") or root)
        if top in seen or not p.get("repo"):
            continue
        seen.add(top)
        out.append({"name": Path(top).name, "repo": p.get("repo"), "branch": p.get("branch")})
    return out
