"""halo_harness.workflows.spec -- a pack's workflow, found by its reference
(Halo 3.2.0.0 R5, docs/WORKFLOWS.md).

A workflow is named `<pack id>/<name>` (`doc-review/review`); the pack must
run here (installed, enabled, no problem: packs/registry.py), declare the
name in `contributes.workflows` and ship `workflows/<name>.yaml`. A pack with
a problem in a workflow file does not run at all (the manifest line says
which key, packs/workflow_rules.py), so a found workflow is a valid one.

    find(ref, cwd=..., state_dir=...)          -> (Workflow, "") or (None, why)
    all_workflows(cwd=..., state_dir=...)      -> every workflow of the packs that run here
    stages(wf) / inputs(wf) / outputs(wf)      -> the file's parts, defaults filled
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from halo_harness.packs import names as N


@dataclass
class Workflow:
    pack: object            # packs.discover.Pack
    name: str
    path: Path
    data: dict = field(default_factory=dict)

    @property
    def ref(self) -> str:
        return f"{self.pack.id}/{self.name}"

    @property
    def description(self) -> str:
        return str(self.data.get("description") or "")


def split_ref(ref) -> "tuple[Optional[str], str]":
    """`("doc-review", "review")` for `doc-review/review` (or `doc-review--review`); `(None, ref)` otherwise."""
    s = str(ref or "").strip()
    if "/" in s:
        pack_id, _, name = s.partition("/")
    else:
        pack_id, name = N.unqualify(s)
    return (pack_id, name) if pack_id and N.is_valid_pack_id(pack_id) and N.is_valid_name(name) else (None, s)


def _load(pack, name: str) -> Optional[Workflow]:
    from halo_harness.packs.workflow_rules import read_workflow, workflow_files
    path = workflow_files(pack.manifest, pack.root).get(name)
    if path is None:
        return None
    data, _text = read_workflow(path)
    return Workflow(pack=pack, name=name, path=path, data=data if isinstance(data, dict) else {})


def find(ref, *, cwd=None, state_dir=None) -> "tuple[Optional[Workflow], str]":
    from halo_harness.packs.bio_rules import declared_workflows
    from halo_harness.packs.discover import find as find_pack
    from halo_harness.packs.studio_registry import active_pack
    pack_id, name = split_ref(ref)
    if pack_id is None:
        return None, f"{ref!r} is not a workflow name: <pack>/<name>, like doc-review/review"
    pack = active_pack(pack_id, cwd=cwd, state_dir=state_dir)
    if pack is None:
        known = find_pack(pack_id, cwd=cwd, state_dir=state_dir)
        why = "is not installed here" if known is None else (
            "has a problem: " + "; ".join(known.problems[:3]) if known.problems else "is not enabled here")
        return None, f"pack {pack_id} {why} (halo pack list)"
    if name not in declared_workflows(pack.manifest):
        names = ", ".join(declared_workflows(pack.manifest)) or "none"
        return None, f"pack {pack_id} declares no workflow {name!r} (its workflows: {names})"
    wf = _load(pack, name)
    if wf is None:
        return None, f"pack {pack_id} declares {name!r} but ships no workflows/{name}.yaml"
    return wf, ""


def all_workflows(*, cwd=None, state_dir=None) -> "list[Workflow]":
    from halo_harness.packs.bio_rules import declared_workflows
    from halo_harness.packs.contribute import _active
    out = []
    for pack in _active(cwd, state_dir):
        for name in declared_workflows(pack.manifest):
            wf = _load(pack, name)
            if wf is not None:
                out.append(wf)
    return out


def stages(wf: Workflow) -> "list[dict]":
    return [s for s in wf.data.get("stages") or [] if isinstance(s, dict) and s.get("id")]


def inputs(wf: Workflow) -> "dict[str, dict]":
    raw = wf.data.get("inputs")
    return {str(k): (v if isinstance(v, dict) else {}) for k, v in raw.items()} if isinstance(raw, dict) else {}


def outputs(wf: Workflow) -> "dict[str, dict]":
    raw = wf.data.get("outputs")
    return {str(k): v for k, v in raw.items() if isinstance(v, dict)} if isinstance(raw, dict) else {}
