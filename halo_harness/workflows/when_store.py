"""halo_harness.workflows.when_store -- where a lineup's "when" rules live, read and written (Halo 3.3.16.3,
docs/WORKFLOWS-squares.md "When").

    a lineup of yours   its `workflows:` list: a plain ref, or `{ref, when: {needs, words, mode}}` (when.py)
    the auto lineup     config `workflows.when.<ref>` beside `workflows.enabled` (no lineup file of its own)

A shipped or a pack's lineup is never written: the line says how to copy it first.

    rules_for(lineup=None, cwd=, state_dir=)        -> {ref: Rule} (only the refs that carry one)
    edit_lineup(lineup, fn, cwd=, state_dir=)       -> (ok, path | problem): fn(items) changes the items in place
    set_rule(ref, raw | None, lineup=None, ...)     -> (ok, one line): the rule written (None / {} = the plain ref)
    rule_of(ref, lineup=None, ...)                  -> Rule | None
"""

from __future__ import annotations

from typing import Optional

from halo_harness.workflows import when as W

CONFIG_KEY = "workflows.when"


def _registry():
    from halo_harness.workflows import registry
    return registry


def config_rules() -> dict:
    from halo_harness.theme import get_config_value
    try:
        got = get_config_value(CONFIG_KEY, None)
    except Exception:
        got = None
    return dict(got) if isinstance(got, dict) else {}


def _full_ref(item_ref: str, own: str) -> str:
    from halo_harness.workflows.spec import split_ref
    pack_id, name = split_ref(item_ref)
    return f"{pack_id}/{name}" if pack_id else (f"{own}/{item_ref}" if own else item_ref)


def lineup_rules(raw: dict) -> dict:
    own = str(raw.get("_pack") or "") or str(raw.get("from_pack") or "").partition("@")[0].strip()
    out = {}
    for item in raw.get("workflows") or [] if isinstance(raw.get("workflows"), list) else []:
        ref, rule = W.item_ref(item), W.read(item)
        if ref and rule is not None:
            out[_full_ref(ref, own)] = rule
    return out


def rules_for(lineup=None, *, cwd=None, state_dir=None) -> dict:
    reg = _registry()
    lineup = lineup if lineup is not None else reg.active_lineup()
    if reg.uses_config(lineup):
        return {ref: rule for ref, raw in config_rules().items() if (rule := W.read(raw)) is not None}
    from halo_harness.teams_yaml import load_team_template_raw
    raw = load_team_template_raw(str(lineup), cwd=cwd, state_dir=state_dir) or {}
    return lineup_rules(raw)


def rule_of(ref: str, lineup=None, *, cwd=None, state_dir=None) -> Optional[W.Rule]:
    return rules_for(lineup, cwd=cwd, state_dir=state_dir).get(ref)


def edit_lineup(lineup: str, fn, *, cwd=None, state_dir=None) -> "tuple[bool, str]":
    """Change a lineup file's `workflows:` items (a lineup of yours or the project's only)."""
    from halo_harness.agents_yaml import _read_yaml_file, _write_yaml_file
    from halo_harness.teams_yaml import find_team_template_path
    found = find_team_template_path(lineup, cwd=cwd, state_dir=state_dir)
    if found is None:
        return False, f"no lineup {lineup!r} (halo teams list)"
    path, source = found
    if source not in ("user", "project"):
        return False, (f"lineup {lineup} is {source}'s and read-only: copy it to yours first "
                       f"(halo teams new <name> --from {lineup}), or enable on the auto lineup")
    raw = _read_yaml_file(path) or {}
    items = [i for i in raw.get("workflows") or [] if W.item_ref(i)] if isinstance(raw.get("workflows"), list) else []
    fn(items)
    raw["workflows"] = items
    problems = _write_yaml_file(path, raw)
    return (False, problems[0]) if problems else (True, str(path))


def _matches(item, ref: str) -> bool:
    got = W.item_ref(item)
    return got == ref or got == ref.partition("/")[2] and "/" in ref


def set_rule(ref: str, raw, lineup=None, *, cwd=None, state_dir=None) -> "tuple[bool, str]":
    """Write `ref`'s rule for the lineup (it must be enabled there); raw None or {} = the plain ref."""
    reg = _registry()
    lineup = lineup if lineup is not None else reg.active_lineup()
    bad = W.problems(raw) if raw else []
    if bad:
        return False, bad[0]
    rule = W.read(raw) if raw else None
    clean = rule.to_json() if rule is not None and not rule.plain else None
    if ref not in reg.enabled_refs(lineup, cwd=cwd, state_dir=state_dir):
        return False, f"{ref} is not on this lineup's board: enable it first (halo workflows enable {ref})"
    where = "the auto lineup" if reg.uses_config(lineup) else f"lineup {lineup}"
    from halo_harness.workflows.spec import find
    found, _why = find(ref, cwd=cwd, state_dir=state_dir)
    said = W.when_line(rule) if clean else f"when {W.label(None, found.contract.covers if found else ())} (its covers)"
    if reg.uses_config(lineup):
        from halo_harness.theme import set_config_value
        cur = config_rules()
        if clean:
            cur[ref] = clean
        else:
            cur.pop(ref, None)
        set_config_value(CONFIG_KEY, cur)
        return True, f"{ref} on {where}: {said} (wrote config {CONFIG_KEY})"

    def put(items: list) -> None:
        for i, item in enumerate(items):
            if _matches(item, ref):
                name = W.item_ref(item)
                items[i] = {"ref": name, "when": clean} if clean else name
    ok, wrote = edit_lineup(str(lineup), put, cwd=cwd, state_dir=state_dir)
    return (True, f"{ref} on {where}: {said} (wrote {wrote})") if ok else (False, wrote)


def drop_config_rule(ref: str) -> None:
    """A square taken off the auto lineup forgets its rule."""
    cur = config_rules()
    if ref in cur:
        from halo_harness.theme import set_config_value
        cur.pop(ref, None)
        set_config_value(CONFIG_KEY, cur)
