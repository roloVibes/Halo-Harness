"""halo_harness.packs.manifest_setup -- a pack's `contributes.setup`: its own Setup blocks (Halo 3.3.11.0 R3;
docs/EXTENSION_API.md "Setup blocks", stable in API 1.1).

    contributes:
      setup:
        - id: prefs                      # lower-case letters, digits, - and _
          title: Your preferences        # the step's name in Setup's rail
          kind: form                     # form | check | note
          fields: [style, depth]         # form: config.schema keys (left out: every key)
          after: model                   # optional: drawn right after this core step
        - id: reach
          title: Reach the service
          kind: check
          run: ["${halo_python}", "${CLAUDE_PLUGIN_ROOT}/setup/reach.py"]   # a command in the pack folder
          what: asks the service for its version
          cost: free
          time: seconds
          writes: nothing
        - {id: about, title: Before you start, kind: note, text: setup/about.md}   # markdown, a file in the pack

    setup_of(manifest)            the entries (mappings only)
    block(manifest, block_id)     one entry, or None
    key_of(pack_id, block_id)     "pack:<id>:<block>", the step id Setup and the checks job use
    split_key(key)                (pack_id, block_id) or ("", "")
    form_fields(manifest, entry)  the config.schema keys a form shows, in the schema's order
    setup_lines(data, root)       one line per problem, each naming the entry
"""

from __future__ import annotations

import re
from pathlib import Path

SETUP_KEYS = ("id", "title", "kind", "after", "help", "fields", "run", "what", "cost", "time", "writes", "text")
KINDS = ("form", "check", "note")
#: The core steps a block may follow (studio/ui/src/routes/setup/pages.ts ORDER, the Summary aside).
CORE_STEPS = ("providers", "local", "model", "permissions", "theme", "team", "linux", "check")
#: What a check says before it runs (the 3.3.x rule: an offered action says what it does, costs, takes and writes).
CHECK_WORDS = ("what", "cost", "time", "writes")
#: The keys each kind takes besides id, title, kind, after and help.
KIND_KEYS = {"form": ("fields",), "check": ("run",) + CHECK_WORDS, "note": ("text",)}
BLOCK_ID = re.compile(r"^[a-z][a-z0-9_]*(-[a-z0-9_]+)*$")
PREFIX = "pack:"


def _contributes(manifest) -> dict:
    c = manifest.get("contributes") if isinstance(manifest, dict) else None
    return c if isinstance(c, dict) else {}


def setup_of(manifest) -> "list[dict]":
    raw = _contributes(manifest).get("setup")
    return [e for e in raw if isinstance(e, dict)] if isinstance(raw, list) else []


def block(manifest, block_id: str):
    return next((e for e in setup_of(manifest) if e.get("id") == block_id), None)


def key_of(pack_id: str, block_id: str) -> str:
    return f"{PREFIX}{pack_id}:{block_id}"


def split_key(key) -> "tuple[str, str]":
    """`pack:<id>:<block>` -> `(id, block)`; anything else -> `("", "")`."""
    if not isinstance(key, str) or not key.startswith(PREFIX):
        return "", ""
    pack_id, sep, block_id = key[len(PREFIX):].partition(":")
    return (pack_id, block_id) if sep and pack_id and block_id else ("", "")


def schema_keys(manifest) -> "list[str]":
    from halo_harness.packs import settings as ST
    schema = ST.schema_of(manifest) or {}
    props = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    return [str(k) for k in props]


def form_fields(manifest, entry: dict) -> "list[str]":
    """The keys a form block shows: its `fields` in the schema's order, or every schema key when left out."""
    keys = schema_keys(manifest)
    wanted = entry.get("fields")
    if not isinstance(wanted, list):
        return keys
    named = {str(f) for f in wanted if isinstance(f, str)}
    return [k for k in keys if k in named]


def _id_lines(entries) -> "list[str]":
    out, seen = [], set()
    for i, e in enumerate(entries):
        bid = e.get("id")
        if not isinstance(bid, str) or not bid:
            out.append(f"contributes.setup[{i}].id: required (lower-case letters, digits, - and _)")
        elif not BLOCK_ID.match(bid):
            out.append(f"contributes.setup[{i}].id {bid!r} is not a block id (lower-case letters, digits, - and _, no --)")
        elif bid in seen:
            out.append(f"contributes.setup[{i}].id {bid!r} is used twice")
        else:
            seen.add(bid)
    return out


def _file_line(where: str, rel, root, *, what: str) -> str:
    if not isinstance(rel, str) or not rel.strip():
        return f"{where}: required ({what})"
    p = Path(rel.replace("\\", "/"))
    if p.is_absolute() or rel.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", rel) or ".." in p.parts or "$" in rel:
        return f"{where}: {rel!r} is outside the pack folder (a file in the pack: setup/<name>.md)"
    if root is not None and not (Path(root) / p).is_file():
        return f"{where}: {p.as_posix()} is not in the pack"
    return ""


def _kind_lines(where: str, e: dict, kind: str, data, root) -> "list[str]":
    out = []
    for other, keys in KIND_KEYS.items():
        for key in keys:
            if other != kind and key in e and key not in KIND_KEYS.get(kind, ()):
                out.append(f"{where}.{key}: only a {other} block takes {key} (this one is a {kind})")
    if kind == "form":
        keys = schema_keys(data)
        fields = e.get("fields")
        if not keys:
            out.append(f"{where}: a form block shows config.schema's keys, and the pack has no config.schema")
        if fields is not None and not isinstance(fields, list):
            out.append(f"{where}.fields: a list of config.schema keys")
        for f in fields if isinstance(fields, list) and keys else []:
            if not isinstance(f, str) or f not in keys:
                out.append(f"{where}.fields: {f!r} is not a key of config.schema ({', '.join(keys)})")
    elif kind == "check":
        from halo_harness.packs.manifest_policy import script_rel
        rel, why = script_rel(e.get("run"))
        if why:
            out.append(f"{where}.run: {why}")
        elif root is not None and not (Path(root) / rel).is_file():
            out.append(f"{where}.run: {rel} is not in the pack")
        for word in CHECK_WORDS:
            v = e.get(word)
            if not (isinstance(v, str) and v.strip()):
                out.append(f"{where}.{word}: required for a check (the line it shows before it runs)")
    elif kind == "note":
        line = _file_line(f"{where}.text", e.get("text"), root, what="a markdown file in the pack, setup/<name>.md")
        if line:
            out.append(line)
    return out


def setup_lines(data, root=None) -> "list[str]":
    """One line per problem in `contributes.setup`; [] for a pack without it."""
    c = _contributes(data)
    if "setup" not in c:
        return []
    if not isinstance(c["setup"], list):
        return ["contributes.setup: a list of blocks ({id, title, kind: form | check | note})"]
    entries = setup_of(data)
    out = [f"contributes.setup[{i}]: a block is a mapping ({{id, title, kind}})"
           for i, e in enumerate(c["setup"]) if not isinstance(e, dict)]
    out += _id_lines(entries)
    for i, e in enumerate(entries):
        where = f"contributes.setup[{i}]"
        title = e.get("title")
        if not (isinstance(title, str) and title.strip()):
            out.append(f"{where}.title: required (the step's name in Setup's rail)")
        if e.get("help") is not None and not isinstance(e.get("help"), str):
            out.append(f"{where}.help: a line a person reads")
        after = e.get("after")
        if after is not None and after not in CORE_STEPS:
            out.append(f"{where}.after {after!r} is not a core Setup step (one of {', '.join(CORE_STEPS)})")
        kind = e.get("kind")
        if kind not in KINDS:
            out.append(f"{where}.kind {kind!r} is not one of {', '.join(KINDS)}")
            continue
        out += _kind_lines(where, e, kind, data, root)
    return out
