"""halo_harness.workflows.blocks_tier -- a tier block template added to a lineup (Halo 3.3.16.3, workflows/blocks.py):
its agents appended (an alias already taken gets a -2), its tier below the lineup's last one, the routing words the
lineup does not have yet. A shipped lineup is copied to yours under its own name first, as Studio's Save does; a
pack's lineup is never written; a lineup with no tiers says to add one first.

    merge(raw, t) -> (raw, tier name) | (None, why)     pure: the lineup mapping with the template in it
    add_tier(t, lineup, cwd=, state_dir=) -> (ok, line, {kind: tier, tier, path})
"""

from __future__ import annotations

import copy


def _unique(want: str, taken: set) -> str:
    out, n = want, 2
    while out in taken:
        out, n = f"{want}-{n}", n + 1
    return out


def merge(raw: dict, t: dict):
    from halo_harness.teams_tiers import assignment_keys, declared
    raw = copy.deepcopy(raw)
    if not declared(raw):
        return None, "it has no tiers: add one first (Studio: Add tier), then the block goes below it"
    taken = set(assignment_keys(raw.get("agents") or []))
    agents = list(raw.get("agents") or [])
    rename, members = {}, []
    for a in t.get("agents") or []:
        if not isinstance(a, dict):
            continue
        entry = dict(a)
        alias = _unique(str(entry.get("as") or entry.get("role") or "agent"), taken)
        rename[str(entry.get("as") or "")] = alias
        entry["as"], entry["role"] = alias, entry.get("role") or "custom"
        taken.add(alias)
        agents.append(entry)
        members.append(alias)
    tiers = list(raw.get("tiers") or [])
    tier = dict(t.get("tier") or {})
    name = _unique(str(tier.get("name") or t.get("name")), {str(x.get("name")) for x in tiers if isinstance(x, dict)})
    tiers.append({"name": name, "members": members, "purpose": str(tier.get("purpose") or "")})
    routing = dict(raw.get("routing") or {}) if isinstance(raw.get("routing"), dict) else {}
    for word, alias in (t.get("routing") or {}).items():
        routing.setdefault(str(word), rename.get(str(alias), str(alias)))
    raw.update(agents=agents, tiers=tiers, routing=routing)
    return raw, name


def add_tier(t: dict, lineup, *, cwd=None, state_dir=None):
    from halo_harness.agents_yaml import _read_yaml_file, _write_yaml_file
    from halo_harness.teams_yaml import find_team_template_path, user_teams_dir
    from halo_harness.workflows import registry
    lineup = lineup if lineup is not None else registry.active_lineup() or "auto"
    found = find_team_template_path(str(lineup), cwd=cwd, state_dir=state_dir)
    if found is None:
        return False, f"no lineup {lineup!r} (halo teams list)", {}
    path, source = found
    if source.startswith("pack"):
        return False, f"lineup {lineup} is {source}'s and read-only: Customize makes your copy first", {}
    raw = _read_yaml_file(path) or {}
    merged, name = merge(raw, t)
    if merged is None:
        return False, f"lineup {lineup}: {name}", {}
    note = ""
    if source not in ("user", "project"):
        path = user_teams_dir(state_dir) / f"{lineup}.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        note = f" (lineup {lineup} is shipped: your copy now)"
    wrote = _write_yaml_file(path, merged)
    if wrote:
        return False, wrote[0], {}
    n = len(merged["tiers"][-1]["members"])
    return True, f"tier {name} ({n} agents) added to lineup {lineup}{note}: wrote {path}", {"kind": "tier", "tier": name, "path": str(path)}
