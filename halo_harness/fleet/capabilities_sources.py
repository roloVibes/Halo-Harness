"""halo_harness.fleet.capabilities_sources -- the quick sections of a
harness's capability catalog (Halo 3.0.6.0 "Fleet Missions" round R6), each
read from what this harness already keeps on disk; no network, no model:

    skills()         every skill a session here can load (names)
    roles()          the active lineup's roles and the bio each one runs, plus the owner's own lineups
    providers()      each model provider and whether it is enabled here (credentials, never a key)
    models()         the catalog's best models per job (`halo models --best-for`) and every local model
    craft_apps()     the craft-app MCP servers registered here (ArtCraft apps, ComfyUI)
    media()          ComfyUI and the media models its last scan found
    projects()       the repos this harness works in (basename, repo, branch; never a full path)
    integrations()   the Signal bridge

Every section is wrapped by the caller: one that raises is listed empty.
"""

from __future__ import annotations

import json
from pathlib import Path

MODELS_PER_KIND = 3
MODELS_MAX = 40
PROJECTS_MAX = 8
LOCAL_PROVIDERS = ("ollama", "local", "lmstudio", "mlx", "huggingface-local", "vllm")


def skills(cwd: Path) -> list:
    from halo_harness.commands.skills import discover_all_skills
    return sorted(discover_all_skills(Path(cwd)))


def roles(home: Path, cwd: Path) -> list:
    from halo_harness import teams_yaml
    from halo_harness.fleet.identity import config_value
    active = config_value("team", None, home)
    names = teams_yaml.list_team_templates(cwd=cwd, state_dir=home, include_templates=False)
    if isinstance(active, str) and active.strip() and active not in names:
        names = [active] + names
    out = []
    for lineup in names[:6]:
        raw = teams_yaml.load_team_template_raw(lineup, cwd=cwd, state_dir=home) or {}
        for entry in raw.get("agents") or []:
            if isinstance(entry, dict) and entry.get("role"):
                out.append({"role": str(entry["role"]), "bio": str(entry.get("agent") or ""), "lineup": lineup,
                            **({"active": True} if lineup == active else {})})
    return out


def providers(home: Path) -> list:
    from halo_harness.providers.enablement import PROVIDER_NAMES, is_enabled, label_for
    out = []
    for name in PROVIDER_NAMES + ("ollama",):
        try:
            ok = bool(is_enabled(name, state_dir=home))
        except Exception:
            ok = False
        try:
            label = label_for(name)
        except Exception:
            label = name
        out.append({"name": label, "id": name, "ok": ok})
    return out


def models(home: Path) -> list:
    """`[{id, provider, best_for: [kind...]}]`: the top MODELS_PER_KIND per job plus every local model."""
    import os
    from halo_harness.capabilities import KINDS, best_for
    from halo_harness.providers.config import load_routes
    from halo_harness.providers.model_enumeration import build_model_rows
    routes = load_routes(home / "routes.json" if (home / "routes.json").exists() else None)
    rows = [r for r in build_model_rows(home, env=dict(os.environ), routes=routes) if r.get("ref")]
    picked: dict = {}
    for kind in KINDS:
        for r in best_for(rows, kind, limit=MODELS_PER_KIND):
            picked.setdefault(r["ref"], {"id": r["ref"], "provider": r.get("provider") or "", "best_for": []})
            picked[r["ref"]]["best_for"].append(kind)
    for r in rows:
        prov = str(r.get("provider") or "").lower()
        if (prov in LOCAL_PROVIDERS or r.get("local")) and r.get("provider") != "alias":
            picked.setdefault(r["ref"], {"id": r["ref"], "provider": prov, "best_for": [], "local": True})
    return list(picked.values())[:MODELS_MAX]


def craft_apps(server_names: list) -> list:
    from halo_harness.design.crafts import APPS
    out = set()
    for name in server_names:
        low = str(name).lower()
        if low in APPS or (low.endswith("craft") and low.isidentifier()):
            out.add(low)
    return sorted(out)


def media(home: Path, server_names: list) -> dict:
    from halo_harness.providers.media_models import GENERATORS, load_cached
    doc = load_cached(home)
    rows = [r for r in doc.get("rows") or [] if isinstance(r, dict) and r.get("kind") in GENERATORS]
    names = {str(n).lower() for n in server_names}
    return {"comfyui": bool(rows) or "comfyui" in names,
            "models": [{"name": Path(str(r.get("file") or r.get("ref") or "")).name, "kind": r.get("kind")}
                       for r in rows][:40]}


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
    from halo_harness.remote.fleet_identity import project
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


def integrations(home: Path) -> dict:
    out = {"signal": False}
    try:
        from halo_harness.fleet.push import paired
        out["signal"] = bool(paired(home))
    except Exception:
        pass
    return out
