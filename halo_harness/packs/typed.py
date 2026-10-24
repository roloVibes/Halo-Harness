"""halo_harness.packs.typed -- a pack's typed data (Halo 3.2.0.0 R5,
docs/EXTENSION_API.md "Events and artifacts").

* An ARTIFACT schema is `<pack>/artifacts/<schema>.json`, listed under
  `contributes.artifacts` (by name, or as that path). A workflow output of
  type `artifact:<schema>` is checked against it at the gate.
* An EVENT schema is `<pack>/events/<kind>.json`: a `contributes.events`
  entry is a kind (its schema is that file when the pack ships it) or
  `{kind, schema, description}`. `publish_event` checks a declared kind's
  data against it (ext/events.py).

A schema is the JSON-schema subset halo_harness.schemas.check reads (type,
properties, additionalProperties, items, enum) plus `required` and
`x-halo-view: table | markdown | keyvalue` (how Studio draws a document of
it; default keyvalue). `check(doc, schema)` answers one line per problem.

    artifact_names(manifest) / event_kinds(manifest)
    artifact_schema(root, name) / event_schema(root, manifest, kind)   -> the schema dict or None
    check(doc, schema)                                                 -> ["<key> ...", ...]
    typed_lines(manifest, root)                                        -> the manifest's lines
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from halo_harness.packs import names as N

VIEWS = ("table", "markdown", "keyvalue")
VIEW_KEY = "x-halo-view"


def _contributes(manifest) -> dict:
    c = manifest.get("contributes") if isinstance(manifest, dict) else None
    return c if isinstance(c, dict) else {}


def _stem(item: str) -> str:
    s = item.strip()
    return Path(s).stem if "/" in s or s.endswith(".json") else s


def artifact_names(manifest) -> "list[str]":
    """`contributes.artifacts`: names, or `artifacts/<name>.json` (the name is the stem)."""
    items = _contributes(manifest).get("artifacts")
    return [_stem(i) for i in items if isinstance(i, str) and i.strip()] if isinstance(items, list) else []


def event_entries(manifest) -> "list[dict]":
    """Every `contributes.events` entry as `{kind, schema?, description?}`."""
    items = _contributes(manifest).get("events")
    out = []
    for i in items if isinstance(items, list) else []:
        if isinstance(i, str) and i.strip():
            out.append({"kind": i.strip()})
        elif isinstance(i, dict) and isinstance(i.get("kind"), str):
            out.append({k: v for k, v in i.items() if k in ("kind", "schema", "description")})
    return out


def event_kinds(manifest) -> "list[str]":
    return [e["kind"] for e in event_entries(manifest)]


def load_schema(path) -> Optional[dict]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def artifact_schema_path(root, name: str) -> Path:
    return Path(root) / "artifacts" / f"{name}.json"


def artifact_schema(root, name: str) -> Optional[dict]:
    return load_schema(artifact_schema_path(root, name)) if N.is_valid_name(name) else None


def event_schema_path(root, manifest, kind: str) -> Optional[Path]:
    entry = next((e for e in event_entries(manifest) if e["kind"] == kind), None)
    if entry is None:
        return None
    rel = entry.get("schema") if isinstance(entry.get("schema"), str) else f"events/{kind}.json"
    return Path(root) / rel


def event_schema(root, manifest, kind: str) -> Optional[dict]:
    path = event_schema_path(root, manifest, kind)
    return load_schema(path) if path is not None and path.is_file() else None


def view_of(schema) -> str:
    v = schema.get(VIEW_KEY) if isinstance(schema, dict) else None
    return v if v in VIEWS else "keyvalue"


def _required(doc, schema: dict, path: str) -> "list[str]":
    out = []
    if isinstance(doc, dict) and isinstance(schema, dict):
        for key in schema.get("required") or []:
            if key not in doc or doc[key] is None:
                out.append(f"{path + '.' if path else ''}{key} is required")
        for key, sub in (schema.get("properties") or {}).items():
            if key in doc:
                out += _required(doc[key], sub, f"{path + '.' if path else ''}{key}")
    elif isinstance(doc, list) and isinstance(schema, dict) and isinstance(schema.get("items"), dict):
        for i, item in enumerate(doc):
            out += _required(item, schema["items"], f"{path}[{i}]")
    return out


def check(doc, schema) -> "list[str]":
    """One line per way `doc` does not match `schema` ([] = it matches)."""
    from halo_harness.schemas.check import check as shape
    if not isinstance(schema, dict):
        return ["the schema is not a JSON object"]
    if doc is None:
        return ["the document is empty (null)"]
    return [f["text"] for f in shape(doc, schema)] + _required(doc, schema, "")


def _schema_lines(where: str, rel: str, root) -> "list[str]":
    p = Path(rel)
    if p.is_absolute() or ".." in p.parts or p.suffix != ".json":
        return [f"{where}: {rel!r} is not a .json file inside the pack"]
    path = Path(root) / p
    if not path.is_file():
        return [f"{where}: {rel} is not in the pack"]
    schema = load_schema(path)
    if schema is None:
        return [f"{where}: {rel} is not a JSON object (a JSON schema)"]
    out = []
    if schema.get("type") not in (None, "object", "array"):
        out.append(f"{where}: {rel} describes {schema.get('type')!r}; a document is an object or a list")
    if VIEW_KEY in schema and schema[VIEW_KEY] not in VIEWS:
        out.append(f"{where}: {rel} {VIEW_KEY} {schema[VIEW_KEY]!r} is not one of {', '.join(VIEWS)}")
    return out


def typed_lines(manifest, root=None) -> "list[str]":
    """`contributes.artifacts` and `contributes.events`: names, and (with a root) each schema file."""
    out: "list[str]" = []
    items = _contributes(manifest).get("artifacts")
    for i, item in enumerate(items if isinstance(items, list) else []):
        where = f"contributes.artifacts[{i}]"
        if not isinstance(item, str) or not N.is_valid_name(_stem(item)):
            out.append(f"{where}: {item!r} is not a schema name (letters, digits, - and _) or artifacts/<name>.json")
        elif "/" in item.strip() and Path(item.strip()).parent.as_posix() != "artifacts":
            out.append(f"{where}: {item!r} -- an artifact schema lives at artifacts/<name>.json")
        elif root is not None:
            out += _schema_lines(where, f"artifacts/{_stem(item)}.json", root)
    for i, item in enumerate((_contributes(manifest).get("events") or []) if isinstance(_contributes(manifest).get("events"), list) else []):
        if isinstance(item, dict):
            kind = item.get("kind")
            if not isinstance(kind, str) or not kind.strip():
                out.append(f"contributes.events[{i}]: an entry is a kind or {{kind, schema}}; kind is required")
                continue
            from halo_harness.packs.manifest import EVENT_RE
            if not EVENT_RE.match(kind):
                out.append(f"contributes.events[{i}]: {kind!r} is not an event name (lower-case, digits, . _ -)")
            if root is not None and isinstance(item.get("schema"), str):
                out += _schema_lines(f"contributes.events[{i}].schema", item["schema"], root)
        elif isinstance(item, str) and root is not None and (Path(root) / "events" / f"{item}.json").is_file():
            out += _schema_lines(f"contributes.events[{i}]", f"events/{item}.json", root)
    return out
