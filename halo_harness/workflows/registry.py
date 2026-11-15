"""halo_harness.workflows.registry -- every square and where it came from, and which ones a session has enabled
(Halo 3.3.16.0 R3, docs/WORKFLOWS-squares.md "The registry").

Four places, in this precedence:

    yours     <state>/workflows/<name>.yaml       (~/.halo/workflows; the state dir, so a test never writes ~/.halo)
    project   <repo>/.halo/workflows/<name>.yaml        (3.4.1.2: a trusted folder only; never a shipped name)
    packs     a running pack's contributes.workflows, ref `<pack>/<name>` (workflows/spec.py, as before)
    shipped   halo_harness/templates/workflows/<name>.yaml

A bare `<name>` resolves yours > project > shipped; `<pack>/<name>` names a pack's. A workflow is a square
when its contract says what it gives (contract.py); the others list and run as before.

Enabled: config `workflows.enabled` (default: the shipped `media` square). 3.6.0.0 R5d: lineups are gone, so a
lineup's `workflows:` list is not read; you change the set with `halo config set workflows.enabled ...`.

    squares(cwd=, state_dir=)          -> [Workflow] (one per bare name, its nearest place; every pack's)
    find_bare(name, cwd=, state_dir=)  -> (Workflow, "") | (None, why)
    group_of(wf)                       -> "yours" | "packs" | "shipped" (the library's three groups)
    check(wf, cwd=, state_dir=)        -> [problem lines] (a pack's ran with its manifest already)
    enabled_refs(lineup=None, ...)     -> [ref]
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
    """3.4.1.2 (ENGINE-1): the project's folder only when it is trusted (project_gate.py)."""
    from halo_harness.project_gate import project_dir
    repo = Path(cwd) if cwd is not None else Path.cwd()
    return [("yours", _state(state_dir) / "workflows"), *[(o, d) for d, o in project_dir(repo / ".halo" / "workflows", repo)],
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
    from halo_harness.project_gate import name_ok  # 3.4.1.2: a project file never takes a shipped or pack name
    return {p.stem: _read(origin, folder, p) for p in files if name_ok(origin, "workflows", p.stem)}


def find_bare(name: str, *, cwd=None, state_dir=None) -> "tuple[Optional[Workflow], str]":
    from halo_harness.packs import names as N
    from halo_harness.project_gate import name_ok, note
    if not N.is_valid_name(name):
        return None, f"{name!r} is not a workflow name: <name> (yours, the project's or shipped) or <pack>/<name>"
    for origin, folder in folders(cwd=cwd, state_dir=state_dir):
        path = folder / f"{name}.yaml"
        if path.is_file() and name_ok(origin, "workflows", name):
            return _read(origin, folder, path), ""
    skip = note("workflows", name, cwd)  # 3.4.1.2 (ENGINE-1): the project's file was there and is not used
    return None, skip or (f"no workflow {name!r}: not yours ({_state(state_dir) / 'workflows'}), not the project's, "
                          "not shipped (halo workflows list)")


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


# -- the enabled set -----------------------------------------------------------------------------------------------

def active_lineup() -> Optional[str]:
    """3.6.0.0 R5c: the plain session's name (crew/plain.py): no session reads a lineup since 3.6, and a map runs exactly
    main's workflows (crew/map_run.workflow_call), so the set is config's."""
    from halo_harness.crew.plain import NAME
    return NAME


def _config_refs() -> "list[str]":
    from halo_harness.theme import get_config_value
    try:
        got = get_config_value(CONFIG_KEY, None)
    except Exception:
        got = None
    return [str(x) for x in got if isinstance(x, str) and x.strip()] if isinstance(got, list) else list(DEFAULT_ENABLED)


def enabled_from(lineup=None, *, cwd=None, state_dir=None) -> "tuple[list, str]":
    """(refs, "config"): config `workflows.enabled` (default: the shipped `media` square). 3.6.0.0 R5d: a lineup's
    own `workflows:` list is not read any more (lineups are gone); `lineup` changes nothing."""
    return _config_refs(), "config"


def enabled_refs(lineup=None, *, cwd=None, state_dir=None) -> "list[str]":
    return enabled_from(lineup, cwd=cwd, state_dir=state_dir)[0]


def enabled_squares(lineup=None, *, cwd=None, state_dir=None) -> "list[Workflow]":
    """The enabled refs that resolve to a square, in the enabled order."""
    from halo_harness.workflows.spec import find
    out = []
    for ref in enabled_refs(lineup, cwd=cwd, state_dir=state_dir):
        wf, _why = find(ref, cwd=cwd, state_dir=state_dir)
        if wf is not None and wf.contract.square:
            out.append(wf)
    return out
