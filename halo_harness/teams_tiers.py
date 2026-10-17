"""halo_harness.teams_tiers -- Halo 3.0.7.0 round R1: `tiers:` in a lineup.

A lineup may stack its members in tiers, an ordered list:

    tiers:
      - {name: lead, members: [main]}
      - {name: leads, members: [planner, reviewer], max_parallel: 2}
      - {name: workers, members: [worker]}

The rule: a member spawns only into the next tier down (tier n spawns
tier n+1). The main agent sits alone in tier 0. Each alias sits in at most
one tier; an alias no tier names joins an implicit last tier (`rest`), said
in a non-blocking "warning:" line. `max_parallel` caps how many members of
one tier run at once across the whole session tree. A lineup with no
`tiers` has one implicit tier (`all`) holding everyone, and spawning
follows the other sections only (nothing changes for existing lineups).

`teams_yaml.validate_team_template` calls `validate_tiers` for the
blocking lines; `tier_warnings` gives the "warning:" lines; the runtime
half (`TeamControl.tier_of/tier_gate/spawn_refusal`) and Studio's graph
(`studio/model.graph_for`) both read `effective_tiers`.
"""

from __future__ import annotations

from typing import Optional

IMPLICIT_ALL = "all"
IMPLICIT_REST = "rest"


def assignment_keys(agents) -> "list[str]":
    """The alias each assignment answers to (`as`, else its `role`), in
    lineup order, each once -- the same key `TeamControl.aliases` uses."""
    keys: "list[str]" = []
    for e in agents or []:
        if isinstance(e, dict) and isinstance(e.get("role"), str) and e.get("role"):
            key = e.get("as") if isinstance(e.get("as"), str) and e.get("as") else e["role"]
            if key not in keys:
                keys.append(key)
    return keys


def main_key(agents) -> "Optional[str]":
    """The main agent's alias, when exactly one assignment has role main."""
    mains = [e for e in agents or [] if isinstance(e, dict) and e.get("role") == "main"]
    if len(mains) != 1:
        return None
    return mains[0].get("as") if isinstance(mains[0].get("as"), str) and mains[0].get("as") else "main"


def declared(template) -> bool:
    tiers = template.get("tiers") if isinstance(template, dict) else None
    return isinstance(tiers, list) and len(tiers) > 0


def _positive_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def validate_tiers(tiers, agents) -> "list[str]":
    """One plain sentence per blocking problem in `tiers`; [] when valid
    (or absent). `agents` is the lineup's expanded `agents:` list."""
    if tiers is None:
        return []
    if not isinstance(tiers, list):
        return ['"tiers" must be a list of {name, members, max_parallel} entries']
    if not tiers:
        return []
    keys = assignment_keys(agents)
    known = ", ".join(keys) or "(none)"
    problems: "list[str]" = []
    names: "set[str]" = set()
    placed: "dict[str, str]" = {}
    for i, tier in enumerate(tiers):
        if not isinstance(tier, dict):
            problems.append(f'tiers[{i}] must be a mapping with "name" and "members"')
            continue
        name = tier.get("name")
        if not isinstance(name, str) or not name.strip():
            problems.append(f'tiers[{i}]: "name" is required')
            name = f"#{i}"
        elif name in names:
            problems.append(f"duplicate tier name: {name!r}")
        names.add(name)
        members = tier.get("members")
        if not isinstance(members, list) or not all(isinstance(m, str) and m for m in members):
            problems.append(f'tiers[{i}] {name!r}: "members" must be a list of aliases')
            members = []
        for m in members:
            if keys and m not in keys:
                problems.append(f"tiers[{i}] {name!r}: {m!r} is not an alias in this lineup (known: {known})")
            elif m in placed:
                problems.append(f"{m!r} is in two tiers: {placed[m]!r} and {name!r} (an alias sits in one tier)")
            else:
                placed[m] = name
        if "max_parallel" in tier and tier.get("max_parallel") is not None \
                and not _positive_int(tier.get("max_parallel")):
            problems.append(f'tiers[{i}] {name!r}: "max_parallel" must be a positive integer')
    main = main_key(agents)
    first = tiers[0] if isinstance(tiers[0], dict) else {}
    first_members = first.get("members") if isinstance(first.get("members"), list) else []
    if main is not None and first_members != [main]:
        found = ", ".join(str(m) for m in first_members) or "nothing"
        problems.append(f"tier 0 ({first.get('name')!r}) must hold the main agent {main!r} alone (found: {found})")
    return problems


def unplaced(template) -> "list[str]":
    """Aliases a declared `tiers` list leaves out (they join the implicit last tier)."""
    if not declared(template):
        return []
    placed = {m for t in template["tiers"] if isinstance(t, dict)
              for m in (t.get("members") if isinstance(t.get("members"), list) else []) if isinstance(m, str)}
    return [k for k in assignment_keys(template.get("agents")) if k not in placed]


def tier_warnings(template) -> "list[str]":
    """The non-blocking "warning:" lines: aliases in no tier."""
    left = unplaced(template)
    if not left:
        return []
    return [f"warning: tiers: {', '.join(repr(a) for a in left)} in no tier -- "
            f"{'they join' if len(left) > 1 else 'it joins'} the implicit last tier {_rest_name(template)!r}"]


def _rest_name(template) -> str:
    names = {t.get("name") for t in template.get("tiers") or [] if isinstance(t, dict)}
    name, n = IMPLICIT_REST, 2
    while name in names:
        name, n = f"{IMPLICIT_REST}-{n}", n + 1
    return name


def effective_tiers(template) -> "list[dict]":
    """`[{name, members, max_parallel, index, implicit}]` -- the declared
    tiers in order, then the implicit last tier when an alias is left out;
    with no `tiers`, the one implicit tier `all` holding everyone."""
    template = template if isinstance(template, dict) else {}
    keys = assignment_keys(template.get("agents"))
    if not declared(template):
        return [{"name": IMPLICIT_ALL, "members": keys, "max_parallel": None, "index": 0, "implicit": True}]
    out: "list[dict]" = []
    seen: "set[str]" = set()
    for tier in template["tiers"]:
        if not isinstance(tier, dict):
            continue
        members = [m for m in (tier.get("members") if isinstance(tier.get("members"), list) else [])
                   if isinstance(m, str) and m in keys and m not in seen]
        seen.update(members)
        cap = tier.get("max_parallel")
        out.append({"name": str(tier.get("name") or f"tier-{len(out)}"), "members": members,
                    "max_parallel": cap if _positive_int(cap) else None, "index": len(out), "implicit": False})
    left = [k for k in keys if k not in seen]
    if left:
        out.append({"name": _rest_name(template), "members": left, "max_parallel": None, "index": len(out),
                    "implicit": True})
    return out


# ---- the runtime rule (TeamControl delegates here) ------------------------------

def tier_index(tiers: "list[dict]", alias: "Optional[str]") -> "Optional[int]":
    if not alias:
        return None
    for t in tiers:
        if alias in t["members"]:
            return t["index"]
    return None


def gate_line(tiers: "list[dict]", caller: "Optional[str]", target: "Optional[str]") -> "Optional[str]":
    """None when `caller` may spawn `target` (one tier down); else the line
    that states the rule. A caller or target outside the lineup is not
    placed in a tier and passes."""
    n, m = tier_index(tiers, caller), tier_index(tiers, target)
    if n is None or m is None or m == n + 1:
        return None
    here = tiers[n]
    if n + 1 >= len(tiers):
        return (f"`{caller}` (tier {n} `{here['name']}`) is in the last tier: it does its work itself and "
                f"spawns no lineup member; `{target}` is in tier {m}")
    below = tiers[n + 1]
    return (f"`{caller}` (tier {n} `{here['name']}`) may spawn only into the next tier down "
            f"(tier {n + 1} `{below['name']}`); `{target}` is in tier {m}")


def parallel_line(tier: dict, live: int) -> "Optional[str]":
    cap = tier.get("max_parallel")
    if cap is None or live < cap:
        return None
    return f"tier `{tier['name']}` already runs {live} of {cap}: wait or raise max_parallel"
