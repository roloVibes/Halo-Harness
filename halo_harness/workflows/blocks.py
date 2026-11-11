"""halo_harness.workflows.blocks -- block templates: blocks you can start from (Halo 3.3.16.3 "Blocks",
docs/WORKFLOWS-squares.md "Block templates").

A template is a small YAML file under halo_harness/templates/blocks/: `{name, title, kind: square | tier, ...}`.

    square   `square:` is a whole workflow file (a square's contract and its stages); adding it writes
             <state>/workflows/<as>.yaml (YOURS -- never a shipped file) and enables it for the lineup, wired to
             main by its covers (the plain rule)
    tier     `tier: {name, purpose}`, `agents:` (lineup entries), `routing:` (words -> alias); adding it appends
             the agents (an alias already taken gets a -2), the tier below the lineup's last one and the routing
             words the lineup does not have yet. A shipped lineup is copied to yours under its name first (as
             Studio's Save does); a pack's lineup is never written.

Every agent of a template sits on an `auto` model (its bio's `models.preference: auto`, a square member's
`model: auto`), so a template names no provider; pin the models afterwards. 3.3.17.0: or on `cp:work` (your work's
Copilot, billed by your tenant), whose Costs line then says "tenant credits" (contract.costs_words).

    names() / load(name) -> (template | None, why)
    problems(t) -> [line]       loads, validates, names no provider
    summary(t) -> dict          {name, title, kind, as, does, covers, agents: [{bio, model}], costs, path}
    add(name, as_=None, lineup=None, cwd=, state_dir=) -> (ok, line, {kind, ref, path})
    remove(ref, lineup=None, cwd=, state_dir=) -> (ok, line)    undo of a square's add: off, its file deleted
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

KINDS = ("square", "tier")


def folder() -> Path:
    return Path(__file__).resolve().parent.parent / "templates" / "blocks"


def names() -> "list[str]":
    try:
        return sorted(p.stem for p in folder().glob("*.yaml") if p.is_file())
    except OSError:
        return []


def load(name: str) -> "tuple[Optional[dict], str]":
    from halo_harness.agents_yaml import _read_yaml_file
    path = folder() / f"{name}.yaml"
    if not str(name).replace("-", "").isalnum() or not path.is_file():
        return None, f"no block template {name!r} (halo blocks list: {', '.join(names())})"
    data = _read_yaml_file(path)
    if not isinstance(data, dict):
        return None, f"{path} does not read as a YAML mapping"
    return dict(data, _path=str(path)), ""


def agents_of(t: dict) -> "list[dict]":
    if t.get("kind") == "tier":
        return [{"bio": str(a.get("agent") or ""), "model": "auto", "alias": str(a.get("as") or a.get("role") or "")}
                for a in t.get("agents") or [] if isinstance(a, dict)]
    lineup = (t.get("square") or {}).get("lineup") or {}
    lead = lineup.get("lead") if isinstance(lineup, dict) else None
    out = [{"bio": str(lead.get("bio") or ""), "model": str(lead.get("model") or "auto"), "lead": True}] if isinstance(lead, dict) else []
    for m in lineup.get("members") or [] if isinstance(lineup, dict) else []:
        if isinstance(m, dict):
            out.append({"bio": str(m.get("bio") or ""), "model": str(m.get("model") or "auto")})
    return out


def problems(t: dict, *, cwd=None, state_dir=None) -> "list[str]":
    from halo_harness.agents_yaml import resolve_agent_bio
    from halo_harness.workflows.contract import problems as contract_problems
    out = []
    if t.get("kind") not in KINDS:
        return [f"kind {t.get('kind')!r} is not square or tier"]
    if not str(t.get("title") or "").strip():
        out.append("title: a few words the library shows")
    if t["kind"] == "square":
        sq = t.get("square") if isinstance(t.get("square"), dict) else {}
        out += contract_problems(sq)
        if not sq.get("gives"):
            out.append("square: says no gives, so it is not a square")
    else:
        tier = t.get("tier") if isinstance(t.get("tier"), dict) else {}
        if not str(tier.get("name") or "").strip() or not str(tier.get("purpose") or "").strip():
            out.append("tier: names its tier and says its purpose")
    agents = agents_of(t)
    if not agents:
        out.append("no agents: a block shows who is inside it")
    for a in agents:
        bio = resolve_agent_bio(a["bio"], cwd=cwd, state_dir=state_dir) if a["bio"] else None
        if bio is None:
            out.append(f"agent {a['bio']!r}: no such bio")
            continue
        pref = str((bio.get("models") or {}).get("preference") or "")
        if "cp:work" in (a["model"], pref) and {a["model"], pref} <= {"auto", "cp:work"}:
            continue  # 3.3.17.0: a bio on cp:work (your work's Copilot, the tenant's) names no paid provider
        if a["model"] != "auto" or pref != "auto":
            out.append(f"agent {a['bio']}: names a model ({a['model']}, bio preference {pref or '-'}): a template stays on auto")
    return out


def summary(t: dict) -> dict:
    sq = t.get("square") if isinstance(t.get("square"), dict) else {}
    tier = t.get("tier") if isinstance(t.get("tier"), dict) else {}
    budget = sq.get("budget") if isinstance(sq.get("budget"), dict) else {}
    from halo_harness.workflows.contract import costs_words, tenant_of  # 3.3.17.0: a member on cp:work
    costs = costs_words(f"band {budget.get('band', 'mid')} · cap ${budget['cap_usd']}" if budget.get("cap_usd") is not None
                        else f"band {budget.get('band', 'mid')}", tenant_of(a["model"] for a in agents_of(t))) \
        if t.get("kind") == "square" else "your models, picked per task"
    return {"name": t.get("name"), "title": t.get("title"), "kind": t.get("kind"),
            "as": str(t.get("as") or sq.get("name") or tier.get("name") or t.get("name")),
            "does": str(sq.get("does") or tier.get("purpose") or ""), "covers": list(sq.get("covers") or []),
            "agents": agents_of(t), "costs": costs, "path": t.get("_path", "")}


def add(name: str, as_: Optional[str] = None, lineup=None, *, cwd=None, state_dir=None) -> "tuple[bool, str, dict]":
    t, why = load(name)
    if t is None:
        return False, why, {}
    bad = problems(t, cwd=cwd, state_dir=state_dir)
    if bad:
        return False, f"template {name}: {bad[0]}", {}
    if t["kind"] == "tier":
        from halo_harness.workflows.blocks_tier import add_tier
        return add_tier(t, lineup, cwd=cwd, state_dir=state_dir)
    from halo_harness.agents_yaml import _write_yaml_file
    from halo_harness.packs import names as N
    from halo_harness.workflows import registry
    ref = str(as_ or summary(t)["as"])
    if not N.is_valid_name(ref):
        return False, f"{ref!r} is not a name (letters, digits, - and _)", {}
    dest = registry.folders(cwd=cwd, state_dir=state_dir)[0][1] / f"{ref}.yaml"
    if dest.exists():
        return False, f"{dest} is there already: pick another name (--as <name>)", {}
    dest.parent.mkdir(parents=True, exist_ok=True)
    wrote = _write_yaml_file(dest, dict(t["square"], name=ref))
    if wrote:
        return False, wrote[0], {}
    ok, line = registry.enable(ref, lineup, cwd=cwd, state_dir=state_dir)
    if not ok:
        dest.unlink(missing_ok=True)
        return False, line, {}
    return True, f"{ref} added from template {name}: wrote {dest}; {line}", {"kind": "square", "ref": ref, "path": str(dest)}


def remove(ref: str, lineup=None, *, cwd=None, state_dir=None) -> "tuple[bool, str]":
    """Undo a square's add: off for the lineup, then its file (yours only) deleted."""
    from halo_harness.workflows import registry
    from halo_harness.workflows.spec import find
    wf, why = find(ref, cwd=cwd, state_dir=state_dir)
    if wf is None:
        return False, why
    if wf.origin != "yours":
        return False, f"{ref} is {wf.origin}'s: only a square of yours a template wrote is removed"
    ok, line = registry.disable(ref, lineup, cwd=cwd, state_dir=state_dir)
    if not ok:
        return False, line
    Path(wf.path).unlink(missing_ok=True)
    return True, f"{line}; deleted {wf.path}"
