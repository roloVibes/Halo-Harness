"""halo_harness.workflows.members -- who is inside a square block, changed (Halo 3.3.16.3, docs/STUDIO-blocks.md "Drag
and drop"): an agent dragged into a square joins its `lineup.members` (on `auto`), one dragged out leaves (the last
agent cannot: the block's x takes the block off). A square of yours (or the project's) is written in place; a shipped
or a pack's square is copied to yours first (`my-<name>`, as `halo workflows new` does) and the lineup's board swaps
to the copy, its "when" kept -- the line says so.

    change(ref, add="", remove="", lineup=None, cwd=, state_dir=) -> (ok, line, {ref, copied_from, path})
    swap(old, new, lineup=None, cwd=, state_dir=) -> (ok, line)   the board's `old` becomes `new`, the rule carried
"""

from __future__ import annotations

from pathlib import Path


def _copy(wf, cwd, state_dir) -> "tuple[object, str]":
    from halo_harness.agents_yaml import _read_yaml_file, _write_yaml_file
    from halo_harness.workflows import registry
    from halo_harness.workflows.spec import find
    folder = registry.folders(cwd=cwd, state_dir=state_dir)[0][1]
    name, n = f"my-{wf.name}", 2
    while (folder / f"{name}.yaml").exists():
        name, n = f"my-{wf.name}-{n}", n + 1
    data = _read_yaml_file(Path(wf.path)) or {}
    folder.mkdir(parents=True, exist_ok=True)
    wrote = _write_yaml_file(folder / f"{name}.yaml", dict(data, name=name))
    if wrote:
        return None, wrote[0]
    got, why = find(name, cwd=cwd, state_dir=state_dir)
    return got, why


def swap(old: str, new: str, lineup=None, *, cwd=None, state_dir=None) -> "tuple[bool, str]":
    from halo_harness.workflows import registry
    from halo_harness.workflows.when_store import rule_of, set_rule
    rule = rule_of(old, lineup, cwd=cwd, state_dir=state_dir)
    ok, line = registry.enable(new, lineup, cwd=cwd, state_dir=state_dir)
    if not ok:
        return False, line
    if rule is not None:
        set_rule(new, rule.to_json(), lineup, cwd=cwd, state_dir=state_dir)
    ok, line2 = registry.disable(old, lineup, cwd=cwd, state_dir=state_dir)
    return ok, f"{new} is on the board in {old}'s place" if ok else line2


def _edit(data: dict, add: str, remove: str) -> str:
    """Change the square's mapping in place; "" or why it cannot."""
    lineup = data.get("lineup")
    if isinstance(lineup, str):
        return f"its agents are lineup {lineup}'s: change that lineup instead"
    lineup = dict(lineup) if isinstance(lineup, dict) else {}
    members = [m for m in lineup.get("members") or [] if isinstance(m, (dict, str))]
    lead = lineup.get("lead") if isinstance(lineup.get("lead"), dict) else None
    bio_of = lambda m: str(m.get("bio") if isinstance(m, dict) else m)  # noqa: E731
    if add:
        if lead is None:
            lineup["lead"] = {"bio": add, "model": "auto"}
        else:
            members.append({"bio": add, "model": "auto"})
    if remove:
        if not members and lead is not None and str(lead.get("bio")) == remove:
            return "the last agent cannot leave: the block's x takes the block off"
        if lead is not None and str(lead.get("bio")) == remove:
            first = members.pop(0)
            lineup["lead"] = first if isinstance(first, dict) else {"bio": first, "model": "auto"}
        else:
            at = next((i for i in range(len(members) - 1, -1, -1) if bio_of(members[i]) == remove), -1)
            if at < 0:
                return f"{remove} is not inside it"
            members.pop(at)
    if members:
        lineup["members"] = members
    else:
        lineup.pop("members", None)
    data["lineup"] = lineup
    return ""


def change(ref: str, add: str = "", remove: str = "", lineup=None, *, cwd=None, state_dir=None) -> "tuple[bool, str, dict]":
    from halo_harness.agents_yaml import _read_yaml_file, _write_yaml_file, resolve_agent_bio
    from halo_harness.workflows.spec import find
    add, remove = str(add or "").strip(), str(remove or "").strip()
    if not add and not remove:
        return False, "say who joins (add) or leaves (remove)", {}
    if add and resolve_agent_bio(add, cwd=cwd, state_dir=state_dir) is None:
        return False, f"no bio {add!r} (Agents -> Cast: the Bios panel lists them)", {}
    wf, why = find(ref, cwd=cwd, state_dir=state_dir)
    if wf is None:
        return False, why, {}
    copied = ""
    if wf.origin not in ("yours", "project"):
        copy, why = _copy(wf, cwd, state_dir)
        if copy is None:
            return False, why, {}
        ok, line = swap(wf.ref, copy.ref, lineup, cwd=cwd, state_dir=state_dir)
        if not ok:
            Path(copy.path).unlink(missing_ok=True)
            return False, line, {}
        copied, wf = wf.ref, copy
    data = _read_yaml_file(Path(wf.path)) or {}
    bad = _edit(data, add, remove)
    if bad:
        return False, f"{wf.ref}: {bad}", {}
    wrote = _write_yaml_file(Path(wf.path), data)
    if wrote:
        return False, wrote[0], {}
    what = f"{add} joined {wf.ref}" if add else f"{remove} left {wf.ref}"
    kind = "a pack's" if "/" in copied else "shipped"
    note = f" ({copied} is {kind}: copied to yours as {wf.ref} first)" if copied else ""
    return True, f"{what}{note}: wrote {wf.path}", {"ref": wf.ref, "copied_from": copied, "path": str(wf.path)}
