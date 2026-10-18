"""halo_harness.start.lineup -- step 1 of `halo start`: a lineup of your own
and its cards as a table (Halo 3.1.1.0 R1).

`own_lineup(name, state_dir)` copies the shipped lineup `name` into your
scope as `my-<name>` (`ensure_builtin_team_templates` first, as every lineup
surface does); a `my-<name>` that is already there is kept as it is, and a
name that is already one of yours is used as it is. The copy is not applied:
your active lineup stays what it was, and the start's Orchestra run names
the copy in its goal. `card_rows(name)` is one row per card: its tier, alias,
role, bio and how many instances.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from halo_harness import teams_yaml as T
from halo_harness.start.steps import OWN_PREFIX


class LineupError(ValueError):
    pass


def own_name(name: str) -> str:
    return name if name.startswith(OWN_PREFIX) else OWN_PREFIX + name


def own_lineup(name: str, *, state_dir=None, cwd=None) -> "tuple[str, list[str]]":
    """`(the lineup the start uses, lines saying what happened)`; LineupError when it cannot."""
    try:
        T.ensure_builtin_team_templates(state_dir=state_dir)
    except Exception:
        pass
    shipped = T.list_bundled_team_templates()
    if name not in shipped:
        found = T.find_team_template_path(name, cwd=cwd, state_dir=state_dir)
        if found is None:
            raise LineupError(f"no lineup named {name!r} (shipped: {', '.join(shipped) or 'none'})")
        return name, [f"{name} is already one of yours ({found[1]} scope): the start uses it as it is"]
    target = own_name(name)
    found = T.find_team_template_path(target, cwd=cwd, state_dir=state_dir)
    if found is not None:
        return target, [f"{target} is already yours ({found[0]}): kept as it is"]
    import yaml
    data = yaml.safe_load((T.bundled_team_templates_dir() / f"{name}.yaml").read_text(encoding="utf-8")) or {}
    data = dict(data, name=target, description=f"My copy of {name}: " + str(data.get("description") or ""))
    ok, problems = T.save_team_template(target, data, cwd=cwd, state_dir=state_dir)
    if not ok:
        raise LineupError(f"could not save {target}: " + "; ".join(problems))
    path = T.user_teams_dir(state_dir) / f"{target}.yaml"
    return target, [f"copied the shipped {name} to {target} ({path})",
                    "your active lineup is unchanged: halo teams use " + target + " makes it the one sessions use"]


def card_rows(name: str, *, state_dir=None, cwd=None) -> "list[dict]":
    """One row per card of `name`: `{tier, card, role, bio, instances}`, in tier order."""
    from halo_harness.teams_tiers import effective_tiers
    template = T.resolve_team_template(name, cwd=cwd, state_dir=state_dir) or {}
    entries = {}
    for e in template.get("agents") or []:
        if isinstance(e, dict) and e.get("role"):
            entries.setdefault(str(e.get("as") or e["role"]), e)
    rows = []
    for tier in effective_tiers(template):
        for key in tier["members"]:
            e = entries.get(key) or {}
            rows.append({"tier": tier["name"], "card": key, "role": str(e.get("role") or ""),
                         "bio": str(e.get("agent") or ""), "instances": int(e.get("instances") or 1)})
    return rows


def card_table(rows: "list[dict]") -> "list[str]":
    """The rows as fixed-width text lines with a header."""
    head = f"{'tier':<10} {'card':<12} {'role':<12} {'bio':<18} n"
    lines = [head, "-" * len(head)]
    for r in rows:
        lines.append(f"{r['tier'][:10]:<10} {r['card'][:12]:<12} {r['role'][:12]:<12} {r['bio'][:18]:<18} {r['instances']}")
    return lines


def lineup_path(name: str, *, state_dir=None, cwd=None) -> Optional[Path]:
    found = T.find_team_template_path(name, cwd=cwd, state_dir=state_dir)
    return found[0] if found else None
