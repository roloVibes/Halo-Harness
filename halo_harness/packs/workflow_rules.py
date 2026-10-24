"""halo_harness.packs.workflow_rules -- what a pack's workflow file may say
(Halo 3.2.0.0 R5, docs/WORKFLOWS.md).

The shape is schemas/workflow_yaml.py; these are the meanings, checked with
the manifest (`manifest.validate_manifest` with a root), one line each,
`workflows/<name>.yaml line N: <key> ...`:

- a file under `workflows/` is declared in `contributes.workflows` (and a
  declared `workflows/<name>.yaml` path is in the pack); `name` is the stem;
- inputs: a type of text | path | json | artifact:<schema> (a schema the pack
  lists under `contributes.artifacts`), a default of that type;
- outputs: artifact:<schema> | files | summary, `from` a stage that gives it
  (a give of that name and kind; every stage gives its summary);
- prerequisites: grants the pack requests, capabilities it declares, files
  relative to the repo; the stage rules (workflow_stages.py).

    workflow_lines(manifest, root)     # [] when every workflow file is fine
    workflow_files(manifest, root)     # {name: path} of the files the pack ships
    read_workflow(path)                # (data or None, text)
"""

from __future__ import annotations

from pathlib import Path

from halo_harness.packs import names as N

INPUT_TYPES = ("text", "path", "json")
OUTPUT_TYPES = ("files", "summary")
ARTIFACT = "artifact:"


class Lines:
    """One file's problem lines, each `workflows/<name>.yaml line N: <key> ...` when the line is found."""

    def __init__(self, rel: str, text: str):
        self.rel, self.text, self.out = rel, text, []

    def add(self, key: str, msg: str, name: str = "", value=None) -> None:
        word = name or key.rsplit(".", 1)[-1].split("[")[0]
        self.raw(word, f"{key}{msg}", value)

    def raw(self, word: str, text: str, value=None) -> None:
        from halo_harness.packs.bio_rules import _line_of
        n = _line_of(self.text, word, value) if self.text and word else 0
        if not n and value is not None and word:
            n = _line_of(self.text, word)
        self.out.append(f"{self.rel} line {n}: {text}" if n else f"{self.rel}: {text}")


def read_workflow(path) -> "tuple[object, str]":
    from halo_harness.agents_yaml import _read_yaml_file
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return None, ""
    return _read_yaml_file(Path(path)), text


def workflow_files(manifest, root) -> "dict[str, Path]":
    folder = Path(root) / "workflows"
    try:
        return {p.stem: p for p in sorted(folder.glob("*.yaml")) if p.is_file()}
    except OSError:
        return {}


def is_artifact(t) -> bool:
    return isinstance(t, str) and t.startswith(ARTIFACT) and N.is_valid_name(t[len(ARTIFACT):])


def schema_of(t: str) -> str:
    return t[len(ARTIFACT):] if is_artifact(t) else ""


def _default_problem(kind: str, value) -> str:
    if value is None:
        return ""
    if kind == "text" and not isinstance(value, str):
        return f"is text, got {type(value).__name__}"
    if kind == "path" and (not isinstance(value, str) or not value.strip()):
        return "is a path (a string relative to the repo)"
    if kind == "path":
        from halo_harness.orchestra.goal import _outside
        if _outside(value):
            return f"{value!r} must be relative to the repo, inside it"
    if is_artifact(kind) and not isinstance(value, str):
        return "is the path of an artifact JSON file (a string)"
    return ""


def _inputs(L: Lines, data: dict, schemas: set) -> None:
    for name, spec in (data.get("inputs") or {}).items() if isinstance(data.get("inputs"), dict) else ():
        key = f"inputs.{name}"
        if not N.is_valid_name(str(name)):
            L.add(key, " is not an input name (letters, digits, - and _)", str(name))
            continue
        if not isinstance(spec, dict):
            continue
        kind = spec.get("type")
        if kind not in INPUT_TYPES and not is_artifact(kind):
            L.add(f"{key}.type", f" {kind!r} is not text, path, json or artifact:<schema>", "type", kind)
            continue
        if is_artifact(kind) and schema_of(kind) not in schemas:
            L.add(f"{key}.type", f" {kind!r}: the pack lists no artifact schema {schema_of(kind)!r} "
                  "(contributes.artifacts)", "type", kind)
        why = _default_problem(kind, spec.get("default"))
        if why:
            L.add(f"{key}.default", f" {why} (the input's type is {kind})", "default")
        if spec.get("required") is True and spec.get("default") is not None:
            L.add(f"{key}.required", ": a required input has no default (drop one of them)", "required")


def _outputs(L: Lines, data: dict, stages: dict, schemas: set) -> None:
    for name, spec in (data.get("outputs") or {}).items() if isinstance(data.get("outputs"), dict) else ():
        key = f"outputs.{name}"
        if not isinstance(spec, dict):
            continue
        kind, src = spec.get("type"), spec.get("from")
        if kind not in OUTPUT_TYPES and not is_artifact(kind):
            L.add(f"{key}.type", f" {kind!r} is not artifact:<schema>, files or summary", "type", kind)
            continue
        if is_artifact(kind) and schema_of(kind) not in schemas:
            L.add(f"{key}.type", f" {kind!r}: the pack lists no artifact schema {schema_of(kind)!r} "
                  "(contributes.artifacts)", "type", kind)
        if src not in stages:
            L.add(f"{key}.from", f" {src!r} is not a stage of the workflow ({', '.join(stages) or 'none'})", "from", src)
            continue
        want = "artifact" if is_artifact(kind) else kind
        gives = {g.get("name"): g.get("kind") for g in stages[src].get("gives") or [] if isinstance(g, dict)}
        if want == "summary" and name == "summary" and not gives:
            continue  # a stage that declares no gives gives its summary
        if gives.get(name) != want:
            L.add(key, f": no stage gives it -- stage {src} gives "
                  + (", ".join(f"{k} ({v})" for k, v in gives.items()) or "only its summary")
                  + f"; give it {{name: {name}, kind: {want}}}", str(name))


def _prereqs(L: Lines, data: dict, manifest) -> None:
    pre = data.get("prerequisites") if isinstance(data.get("prerequisites"), dict) else {}
    from halo_harness.packs.manifest import requested
    asked, caps = set(requested(manifest)), set(capabilities(manifest))
    for g in pre.get("grants") or []:
        if g not in asked:
            L.add("prerequisites.grants", f" {g!r} is not a permission the pack requests", "grants", g)
    for c in pre.get("capabilities") or []:
        if c not in caps:
            L.add("prerequisites.capabilities", f" {c!r} is not a capability the pack declares", "capabilities", c)
    from halo_harness.orchestra.goal import _outside
    for f in pre.get("files") or []:
        if not isinstance(f, str) or _outside(f):
            L.add("prerequisites.files", f" {f!r} must be relative to the repo, inside it", "files", f)


def capabilities(manifest) -> "list[str]":
    caps = manifest.get("capabilities") if isinstance(manifest, dict) else None
    return [c for c in caps if isinstance(c, str)] if isinstance(caps, list) else []


def check_one(manifest, root, name: str, path: Path) -> "list[str]":
    """Every line for one workflow file."""
    from halo_harness.schemas import check
    from halo_harness.schemas.workflow_yaml import workflow
    rel = f"workflows/{name}.yaml"
    data, text = read_workflow(path)
    L = Lines(rel, text)
    if not isinstance(data, dict):
        return [f"{rel}: does not read as a YAML mapping (key: value)"]
    for f in check(data, workflow()):
        L.raw(str(f["key"] or "").rsplit(".", 1)[-1].split("[")[0], f["text"])
    if data.get("name") not in (None, name):
        L.add("name", f" {data.get('name')!r} differs from the file's name {name!r}", "name")
    from halo_harness.packs.typed import artifact_names
    from halo_harness.packs.workflow_stages import stage_lines
    schemas = set(artifact_names(manifest))
    stages = stage_lines(L, data, manifest, root)
    _inputs(L, data, schemas)
    _outputs(L, data, stages, schemas)
    _prereqs(L, data, manifest)
    return L.out


def workflow_lines(manifest, root=None) -> "list[str]":
    if root is None:
        return []
    from halo_harness.packs.bio_rules import declared_workflows
    declared = declared_workflows(manifest)
    files = workflow_files(manifest, root)
    items = ((manifest.get("contributes") or {}).get("workflows") or []) if isinstance(manifest, dict) else []
    out = [f"contributes.workflows: {item!r} is not workflows/<name>.yaml" for item in items
           if isinstance(item, str) and ("/" in item or item.endswith(".yaml"))
           and (Path(item).parent.as_posix() != "workflows" or Path(item).suffix != ".yaml")]
    out += [f"contributes.workflows: {item} is not in the pack" for item in items
            if isinstance(item, str) and "/" in item and Path(item).stem not in files]
    out += [f"workflows/{name}.yaml: {name!r} is not declared in contributes.workflows" for name in files
            if name not in declared]
    for name, path in files.items():
        if name in declared:
            out += check_one(manifest, root, name, path)
    return out
