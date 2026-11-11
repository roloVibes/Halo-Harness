"""halo_harness.workflows.registry -- every square and where it came from, and which ones a lineup
has enabled (Halo 3.3.16.0 R3, docs/WORKFLOWS-squares.md "The registry").

Four places, in this precedence:

    yours     <state>/workflows/<name>.yaml       (~/.halo/workflows; the state dir, so a test never writes ~/.halo)
    project   <repo>/.halo/workflows/<name>.yaml
    packs     a running pack's contributes.workflows, ref `<pack>/<name>` (workflows/spec.py, as before)
    shipped   halo_harness/templates/workflows/<name>.yaml

A bare `<name>` resolves yours > project > shipped; `<pack>/<name>` names a pack's. A workflow is a square
when its contract says what it gives (contract.py); the others list and run as before.

Enabled per lineup: a lineup's `workflows:` list (any ref; `workflows: []` is none, on purpose); the auto
lineup, no lineup and (3.3.16.2) a lineup with no `workflows:` key read `workflows.enabled` in config
(default: the shipped `media` square). `enabled_from` says which of the two answered.

    squares(cwd=, state_dir=)          -> [Workflow] (one per bare name, its nearest place; every pack's)
    find_bare(name, cwd=, state_dir=)  -> (Workflow, "") | (None, why)
    group_of(wf)                       -> "yours" | "packs" | "shipped" (the library's three groups)
    check(wf, cwd=, state_dir=)        -> [problem lines] (a pack's ran with its manifest already)
    enabled_refs(lineup=None, ...)     -> [ref]
    enable(ref, lineup=None, ...) / disable(...)  -> (ok, one line saying what changed)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from halo_harness.workflows.spec import Workflow

DEFAULT_ENABLED = ("media",)
CONFIG_KEY = "workflows.enabled"
ORDER = ("yours", "project", "shipped")


@dataclass
class Place:
    """Where a square that is not a pack's came from (a Workflow's `pack` for it)."""
    id: str
    root: Path
    manifest: dict = field(default_factory=dict)
    version: str = ""


def shipped_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "templates" / "workflows"


def _state(state_dir) -> Path:
    if state_dir is not None:
        return Path(state_dir)
    from halo_harness.config.paths import bridge_home
    return bridge_home()


def folders(*, cwd=None, state_dir=None) -> "list[tuple[str, Path]]":
    repo = Path(cwd) if cwd is not None else Path.cwd()
    return [("yours", _state(state_dir) / "workflows"), ("project", repo / ".halo" / "workflows"),
            ("shipped", shipped_dir())]


def _read(origin: str, folder: Path, path: Path) -> Workflow:
    from halo_harness.packs.workflow_rules import read_workflow
    data, _text = read_workflow(path)
    return Workflow(pack=Place(origin, folder.parent), name=path.stem, path=path,
                    data=data if isinstance(data, dict) else {}, origin=origin)


def _place(origin: str, folder: Path) -> "dict[str, Workflow]":
    try:
        files = sorted(p for p in folder.glob("*.yaml") if p.is_file())
    except OSError:
        return {}
    return {p.stem: _read(origin, folder, p) for p in files}


def find_bare(name: str, *, cwd=None, state_dir=None) -> "tuple[Optional[Workflow], str]":
    from halo_harness.packs import names as N
    if not N.is_valid_name(name):
        return None, f"{name!r} is not a workflow name: <name> (yours, the project's or shipped) or <pack>/<name>"
    for origin, folder in folders(cwd=cwd, state_dir=state_dir):
        path = folder / f"{name}.yaml"
        if path.is_file():
            return _read(origin, folder, path), ""
    return None, (f"no workflow {name!r}: not yours ({_state(state_dir) / 'workflows'}), not the project's, not shipped "
                  "(halo workflows list)")


def squares(*, cwd=None, state_dir=None) -> "list[Workflow]":
    seen: dict = {}
    for origin, folder in folders(cwd=cwd, state_dir=state_dir):
        for name, wf in _place(origin, folder).items():
            seen.setdefault(name, wf)
    bare = [seen[n] for o in ORDER for n in sorted(seen) if seen[n].origin == o]
    from halo_harness.workflows.spec import all_workflows
    try:
        packs = all_workflows(cwd=cwd, state_dir=state_dir)
    except Exception:
        packs = []
    return [w for w in bare if w.origin != "shipped"] + packs + [w for w in bare if w.origin == "shipped"]


def group_of(wf) -> str:
    origin = getattr(wf, "origin", "pack")
    return "packs" if origin == "pack" else ("shipped" if origin == "shipped" else "yours")


def check(wf, *, cwd=None, state_dir=None) -> "list[str]":
    if getattr(wf, "origin", "pack") == "pack":
        return []
    from halo_harness.packs.workflow_rules import check_one
    return check_one({}, Path(wf.path).parent.parent, wf.name, Path(wf.path))


# -- the enabled sets ---------------------------------------------------------------------------------------------

def active_lineup() -> Optional[str]:
    from halo_harness.lineup_default import lineup_in_use
    return lineup_in_use()[0]


def uses_config(lineup) -> bool:
    from halo_harness.lineup_default import DEFAULT_LINEUP
    return not lineup or lineup == DEFAULT_LINEUP


def _config_refs() -> "list[str]":
    from halo_harness.theme import get_config_value
    try:
        got = get_config_value(CONFIG_KEY, None)
    except Exception:
        got = None
    return [str(x) for x in got if isinstance(x, str) and x.strip()] if isinstance(got, list) else list(DEFAULT_ENABLED)


def _lineup_refs(raw: dict) -> "list[str]":
    from halo_harness.workflows.spec import split_ref
    own = str(raw.get("_pack") or "") or str(raw.get("from_pack") or "").partition("@")[0].strip()
    out = []
    from halo_harness.workflows.when import item_ref  # 3.3.16.3: an item may be {ref, when}
    for item in raw.get("workflows") or [] if isinstance(raw.get("workflows"), list) else []:
        if item_ref(item):
            pack_id, name = split_ref(item_ref(item))
            out.append(f"{pack_id}/{name}" if pack_id else (f"{own}/{item_ref(item)}" if own else item_ref(item)))
    return list(dict.fromkeys(out))


def enabled_from(lineup=None, *, cwd=None, state_dir=None) -> "tuple[list, str]":
    """(refs, where): `where` is "lineup" (its own `workflows:` list, `[]` = none on purpose) or "config"
    (`workflows.enabled`: the auto lineup, no lineup, and since 3.3.16.2 a lineup with no `workflows:` key)."""
    lineup = lineup if lineup is not None else active_lineup()
    if uses_config(lineup):
        return _config_refs(), "config"
    from halo_harness.teams_yaml import load_team_template_raw
    raw = load_team_template_raw(str(lineup), cwd=cwd, state_dir=state_dir) or {}
    if "workflows" not in raw:  # 3.3.16.2: no key inherits config's set, exactly like the auto lineup
        return _config_refs(), "config"
    return _lineup_refs(raw), "lineup"


def enabled_refs(lineup=None, *, cwd=None, state_dir=None) -> "list[str]":
    return enabled_from(lineup, cwd=cwd, state_dir=state_dir)[0]


def _write_lineup(lineup: str, ref: str, on: bool, *, cwd=None, state_dir=None) -> "tuple[bool, str]":
    """3.3.16.3: the lineup's items change in place, so a `{ref, when}` item keeps its rule (when_store.py)."""
    from halo_harness.workflows.when import item_ref
    from halo_harness.workflows.when_store import edit_lineup

    def flip(items: list) -> None:
        if on:
            items.append(ref)
        else:
            items[:] = [i for i in items if item_ref(i) != ref and not (item_ref(i) == ref.partition("/")[2] and "/" in ref)]
    return edit_lineup(lineup, flip, cwd=cwd, state_dir=state_dir)


def _set(ref: str, on: bool, lineup=None, *, cwd=None, state_dir=None) -> "tuple[bool, str]":
    from halo_harness.workflows.spec import find
    lineup = lineup if lineup is not None else active_lineup()
    wf, why = find(ref, cwd=cwd, state_dir=state_dir)
    if on and wf is None:
        return False, why
    ref = wf.ref if wf is not None else str(ref).strip()
    if on and not wf.contract.square:
        return False, f"{ref} is not a square: its file says no `gives` (halo workflows show {ref})"
    refs, source = enabled_from(lineup, cwd=cwd, state_dir=state_dir)
    where = "the auto lineup" if uses_config(lineup) else f"lineup {lineup}"
    if (ref in refs) == on:
        inherited = " (from config workflows.enabled: the lineup sets no `workflows:`)" \
            if source == "config" and not uses_config(lineup) else ""
        return True, f"{ref} is already {'on' if on else 'off'} for {where}{inherited}"
    refs = refs + [ref] if on else [r for r in refs if r != ref]
    if uses_config(lineup):
        from halo_harness.theme import set_config_value
        set_config_value(CONFIG_KEY, refs)
        ok, wrote = True, f"config {CONFIG_KEY}"
        if not on:
            from halo_harness.workflows.when_store import drop_config_rule
            drop_config_rule(ref)
    else:
        ok, wrote = _write_lineup(str(lineup), ref, on, cwd=cwd, state_dir=state_dir)
        if not ok:
            return False, wrote
    return True, f"{ref} {'enabled' if on else 'disabled'} for {where} (wrote {wrote})"


def enable(ref: str, lineup=None, *, cwd=None, state_dir=None) -> "tuple[bool, str]":
    return _set(ref, True, lineup, cwd=cwd, state_dir=state_dir)


def disable(ref: str, lineup=None, *, cwd=None, state_dir=None) -> "tuple[bool, str]":
    return _set(ref, False, lineup, cwd=cwd, state_dir=state_dir)


def enabled_squares(lineup=None, *, cwd=None, state_dir=None) -> "list[Workflow]":
    """The enabled refs that resolve to a square, in the enabled order."""
    from halo_harness.workflows.spec import find
    out = []
    for ref in enabled_refs(lineup, cwd=cwd, state_dir=state_dir):
        wf, _why = find(ref, cwd=cwd, state_dir=state_dir)
        if wf is not None and wf.contract.square:
            out.append(wf)
    return out
