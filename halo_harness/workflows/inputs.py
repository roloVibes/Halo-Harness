"""halo_harness.workflows.inputs -- a workflow's typed inputs and its
prerequisites, checked before anything runs (Halo 3.2.0.0 R5).

    parse(wf, raw, repo=...)   -> (values, problems): `raw` is `{name: "text"}` from `--input k=v`
        text      the text as given
        path      relative to the repo, inside it, and there (a file or a folder)
        json      parsed JSON (a default in the file is taken as written)
        artifact:<schema>   the path of a JSON file in the repo, checked against the pack's schema
    prerequisites(wf, repo=..., cwd=..., state_dir=...) -> problems: each tool on PATH, each grant
        given to the pack, each capability available here (packs/fleet_registry.py), each file in the repo
    capability_problems(wf, names, ...) -> the same check for a stage's `needs`

One plain line per problem; [] means the run may start.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from halo_harness.workflows import spec


def _path_value(repo: Path, value) -> "tuple[str, str]":
    from halo_harness.orchestra.goal import _outside, norm_file
    if not isinstance(value, str) or not value.strip():
        return "", "is a path relative to the repo"
    rel = norm_file(value).rstrip("/") or "."
    if _outside(rel):
        return "", f"{value!r} must be relative to the repo, inside it"
    if not (repo / rel).exists():
        return "", f"{rel} is not in the repo ({repo})"
    return rel, ""


def parse(wf, raw: dict, *, repo) -> "tuple[dict, list]":
    from halo_harness.packs.typed import artifact_schema, check
    from halo_harness.packs.workflow_rules import is_artifact, schema_of
    repo = Path(repo)
    declared = spec.inputs(wf)
    problems = [f"the workflow has no input {k!r} (its inputs: {', '.join(declared) or 'none'})"
                for k in raw if k not in declared]
    values: dict = {}
    for name, sp in declared.items():
        kind, given = sp.get("type") or "text", name in raw
        value = raw[name] if given else sp.get("default")
        if value is None:
            if sp.get("required"):
                problems.append(f"input {name} is required: --input {name}=<{kind}>")
            continue
        if kind == "text":
            values[name] = str(value)
        elif kind == "path":
            rel, why = _path_value(repo, value)
            problems += [f"input {name} {why}"] if why else []
            values[name] = rel
        elif kind == "json":
            try:
                values[name] = json.loads(value) if given else value
            except ValueError as e:
                problems.append(f"input {name} is JSON, got {str(value)[:60]!r} ({e.msg})")
        elif is_artifact(kind):
            rel, why = _path_value(repo, value)
            if why:
                problems.append(f"input {name} {why}")
                continue
            try:
                doc = json.loads((repo / rel).read_text(encoding="utf-8-sig"))
            except (OSError, ValueError) as e:
                problems.append(f"input {name}: {rel} is not a JSON file ({e})")
                continue
            lines = check(doc, artifact_schema(wf.pack.root, schema_of(kind)))
            problems += [f"input {name} ({rel}) does not match {schema_of(kind)}: {ln}" for ln in lines]
            values[name] = rel
    return values, problems


def _caps(wf, *, cwd=None, state_dir=None) -> dict:
    from halo_harness.packs import state as S
    from halo_harness.packs.fleet_registry import host_catalog, pack_entry
    try:
        granted = S.granted(wf.pack.id, S.load(state_dir))
        entry = pack_entry(wf.pack, granted, host_catalog(state_dir, cwd), cwd=cwd, state_dir=state_dir)
    except Exception as e:  # a host the catalog cannot read: say so instead of guessing
        return {"": {"available": False, "why": f"the capabilities catalog could not be read ({type(e).__name__})"}}
    return {c["name"]: c for c in entry.get("capabilities") or []}


def capability_problems(wf, names, *, cwd=None, state_dir=None, where: str = "") -> "list[str]":
    from halo_harness.packs.workflow_rules import capabilities
    names = [n for n in names or [] if isinstance(n, str)]
    if not names:
        return []
    caps, declared = _caps(wf, cwd=cwd, state_dir=state_dir), set(capabilities(wf.pack.manifest))
    out = []
    for n in names:
        c = caps.get(n)
        if n not in declared:
            out.append(f"{where}capability {n} is not one the pack declares")
        elif c is not None and not c.get("available"):
            out.append(f"{where}capability {n} is not available here: {c.get('why')}")
    return out


def prerequisites(wf, *, repo, cwd=None, state_dir=None) -> "list[str]":
    from halo_harness.packs import state as S
    pre = wf.data.get("prerequisites") if isinstance(wf.data.get("prerequisites"), dict) else {}
    out = [f"prerequisite: {t} is not on PATH" for t in pre.get("tools") or [] if not shutil.which(str(t))]
    have = set(S.granted(wf.pack.id, S.load(state_dir)))
    out += [f"prerequisite: pack {wf.pack.id} runs without the {g} grant (halo pack enable {wf.pack.id} --grant {g})"
            for g in pre.get("grants") or [] if g not in have]
    out += capability_problems(wf, pre.get("capabilities"), cwd=cwd, state_dir=state_dir, where="prerequisite: ")
    out += [f"prerequisite: {f} is not in the repo" for f in pre.get("files") or [] if not (Path(repo) / str(f)).exists()]
    return out
