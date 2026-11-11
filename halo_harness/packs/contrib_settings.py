"""halo_harness.packs.contrib_settings -- a pack's own rows in Studio's Settings and `halo settings` (Halo 3.4.0.0 B;
docs/EXTENSION_API.md "CLI verbs, slash commands, doctor rows and settings rows", draft in API 1.3).

    contributes:
      settings:
        - {key: model, title: The coach's model, help: "...", type: string, default: ""}

Each entry is one row of the Settings catalog while the pack is enabled: its value lives at
`packs.settings.<id>.<key>` in config.json (the same place `ext.get_config` reads), its group is the pack's, and the
row says it is from the pack. No code of the pack runs for it, so it takes no grant. With the pack off the rows are
gone; a value left in config.json is ignored, and `halo doctor --config` says so in one line.

    entries(manifest)             the `settings` entries
    lines(data, root)             one line per problem, each naming the entry
    rows(cwd, state_dir)          [{key: "packs.settings.<id>.<key>", pack, title, help, type, default}]
"""

from __future__ import annotations

import re

KEYS = ("key", "title", "help", "type", "default")
TYPES = {"string": str, "integer": int, "number": (int, float), "boolean": bool}
KEY = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$")


def entries(manifest) -> "list[dict]":
    from halo_harness.packs.contrib_cli import entries as _entries
    return _entries(manifest, "settings")


def lines(data, root=None) -> "list[str]":
    c = data.get("contributes") if isinstance(data, dict) else None
    raw = c.get("settings") if isinstance(c, dict) else None
    if raw is None:
        return []
    if not isinstance(raw, list):
        return ["contributes.settings: a list of {key, title, help, type, default}"]
    out, seen = [], set()
    for i, e in enumerate(raw):
        where = f"contributes.settings[{i}]"
        if not isinstance(e, dict):
            out.append(f"{where}: a mapping {{key, title, help, type, default}}")
            continue
        out += [f"{where}: unknown key {k!r} ({', '.join(KEYS)})" for k in e if k not in KEYS]
        key = e.get("key")
        if not isinstance(key, str) or not KEY.match(key):
            out.append(f"{where}.key: {key!r} is not a settings key (lower-case words joined by .)")
        elif key in seen:
            out.append(f"{where}.key: {key!r} is used twice")
        seen.add(key)
        if not isinstance(e.get("title"), str) or not e["title"].strip():
            out.append(f"{where}.title: required (the row's name)")
        kind = e.get("type")
        if kind not in TYPES:
            out.append(f"{where}.type: {kind!r} is not one of {', '.join(TYPES)}")
        elif "default" in e and e["default"] is not None and not (isinstance(e["default"], TYPES[kind])
                                                                 and not (kind != "boolean" and isinstance(e["default"], bool))):
            out.append(f"{where}.default: {e['default']!r} is not of type {kind}")
    return out


def rows(cwd=None, state_dir=None) -> "list[dict]":
    try:
        from halo_harness.packs import registry
        packs = registry.active(cwd=cwd, state_dir=state_dir)
    except Exception:
        return []
    out = []
    for p in packs:
        for e in entries(p.manifest):
            if isinstance(e.get("key"), str) and e.get("type") in TYPES:
                out.append({"key": f"packs.settings.{p.id}.{e['key']}", "pack": p.id, "title": str(e.get("title") or ""),
                            "help": str(e.get("help") or ""), "type": e["type"], "default": e.get("default")})
    return out


def row_for(key: str, cwd=None, state_dir=None):
    """The enabled pack's row whose key is `key` (`packs.settings.<id>.<key>`), or None (`halo config get/set`)."""
    if not str(key or "").startswith("packs.settings."):
        return None
    return next((r for r in rows(cwd, state_dir) if r["key"] == key), None)


def value_problem(row: dict, value) -> str:
    """'' when `value` fits the row's type, else the one line `halo config set` prints."""
    kind = row["type"]
    ok = isinstance(value, TYPES[kind]) and not (kind != "boolean" and isinstance(value, bool))
    word = {"integer": "an integer", "number": "a number", "boolean": "true or false"}.get(kind, "a string")
    return "" if ok else f"{row['key']} is {word} (the {row['pack']} pack's row {row['title']!r}); {value!r} is not"
