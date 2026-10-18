"""halo_harness.schemas.check -- walk one document against one schema.

A schema is a JSON-schema-like dict (stdlib only):

    {"type": "object" | "array" | "string" | "boolean" | "integer" | "number",
     "type": [several of those],            # any one of them
     "properties": {key: schema},           # objects: the keys this file knows
     "additionalProperties": False,         # objects: a key outside properties is reported
     "items": schema,                       # arrays: every element
     "enum": [value, ...]}                  # the value is one of these

`check(doc, schema)` answers one finding per problem, each
`{"check": "unknown-key" | "wrong-type" | "bad-value", "key": <dotted path>,
"text": <one sentence>, "closest": <known key or "">}`. A `None` value is an
unset key and is never a wrong type (YAML reads `key:` with nothing after it
as None, and every loader treats it as unset). Shape only: what a value
means (a bio that exists, a lineup that resolves) is the validators' job.
"""

from __future__ import annotations

import difflib

_PY_NAMES = {"string": "a string", "boolean": "true or false", "integer": "a whole number",
             "number": "a number", "array": "a list", "object": "a mapping"}


def _is(value, kind: str) -> bool:
    if kind == "string":
        return isinstance(value, str)
    if kind == "boolean":
        return isinstance(value, bool)
    if kind == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if kind == "array":
        return isinstance(value, list)
    if kind == "object":
        return isinstance(value, dict)
    return True


def _kinds(schema: dict) -> list:
    kind = schema.get("type")
    if kind is None:
        return []
    return list(kind) if isinstance(kind, (list, tuple)) else [kind]


def _describe(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, dict):
        return "a mapping"
    if isinstance(value, list):
        return "a list"
    if isinstance(value, str):
        return f"the string {value!r}"
    return repr(value)


def closest_key(key: str, known) -> str:
    """The known key nearest to `key` (difflib's ratio, cutoff 0.6), or ""."""
    hits = difflib.get_close_matches(str(key), [str(k) for k in known], n=1, cutoff=0.6)
    return hits[0] if hits else ""


def _join(path: str, key) -> str:
    return f"{path}.{key}" if path else str(key)


def check(doc, schema: dict, path: str = "") -> list:
    """Every shape problem in `doc` against `schema` (see the module docstring)."""
    out: list = []
    if doc is None:
        return out
    kinds = _kinds(schema)
    if kinds and not any(_is(doc, k) for k in kinds):
        wanted = " or ".join(_PY_NAMES.get(k, k) for k in kinds)
        where = path or "the file"
        out.append({"check": "wrong-type", "key": path, "closest": "",
                    "text": f"{where} is {wanted}, got {_describe(doc)}"})
        return out
    if "enum" in schema and doc not in schema["enum"]:
        allowed = ", ".join(str(v) for v in schema["enum"])
        out.append({"check": "bad-value", "key": path, "closest": closest_key(str(doc), schema["enum"]),
                    "text": f"{path or 'the value'} is one of {allowed}, got {_describe(doc)}"})
    if isinstance(doc, dict):
        props = schema.get("properties") or {}
        for key, value in doc.items():
            sub = props.get(key)
            if sub is None:
                if schema.get("additionalProperties", True) is False:
                    near = closest_key(key, props)
                    hint = f" (closest known key: {near!r})" if near else ""
                    out.append({"check": "unknown-key", "key": _join(path, key), "closest": near,
                                "text": f"unknown key {_join(path, key)!r}{hint}; nothing reads it"})
                elif isinstance(schema.get("additionalProperties"), dict):
                    out += check(value, schema["additionalProperties"], _join(path, key))
                continue
            out += check(value, sub, _join(path, key))
    elif isinstance(doc, list) and isinstance(schema.get("items"), dict):
        for i, value in enumerate(doc):
            out += check(value, schema["items"], f"{path}[{i}]")
    return out


def obj(properties: dict, *, strict: bool = True) -> dict:
    """An object schema; `strict` reports keys outside `properties`."""
    return {"type": "object", "properties": properties, "additionalProperties": not strict}


def free(kind="object") -> dict:
    """A value of `kind` whose inside is not checked here (a validator owns it)."""
    return {"type": kind}


STRING, BOOL, INT, NUMBER, LIST, MAPPING = (free("string"), free("boolean"), free("integer"), free("number"),
                                            free("array"), free("object"))
