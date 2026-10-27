"""halo_harness.studio.settings_values -- what Studio's Settings section reads and checks (Halo 3.3.3.0 R2):
each catalog row's saved value against its default (settings_catalog.py), masked the way `halo config get`
masks (config_cli._mask_value, plus a `secret` row never shows its value at all), a keyed row's entries from
the saved section, and a posted value coerced and checked by its row's kind and choices. studio/settings_api.py
has the routes."""

from __future__ import annotations

import json

_MISSING = object()
_TRUE = ("true", "on", "yes", "1")
_FALSE = ("false", "off", "no", "0")


def walk(data, key: str):
    """The value at dotted `key` in `data`, or _MISSING."""
    cursor = data
    for part in key.split("."):
        if not isinstance(cursor, dict) or part not in cursor:
            return _MISSING
        cursor = cursor[part]
    return cursor


def masked(key: str, value, secret: bool = False):
    """The value as `halo config get` prints it (secret-shaped content redacted), as JSON; a secret row: None."""
    if secret:
        return None
    from halo_harness.config_cli import _mask_value
    text = _mask_value(key, value)
    try:
        return json.loads(text)
    except ValueError:
        return text


def _entries(r, data) -> "tuple[list, object]":
    """A keyed row's entries ({name, key, value, set}) and its whole section (masked)."""
    from halo_harness.settings_catalog import entry_names, keyed_parts, row
    section, leaf, listy = keyed_parts(r)
    whole = walk(data, section)
    out, seen = [], set()
    if listy and isinstance(whole, list):
        for i, item in enumerate(whole):
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or i)
            key = f"{section}[{name}]" + (f".{leaf}" if leaf else "")
            has = leaf in item
            out.append({"name": name, "key": key, "value": masked(key, item[leaf], r.secret) if has else None, "set": has})
            seen.add(name)
    elif not listy and isinstance(whole, dict):
        for name, child in whole.items():
            key = f"{section}.{name}"
            if row(key) is not None or any(x.key.startswith(key + ".") for x in _plain_rows()):
                continue  # a row of its own (roles.enabled, connectors.bridge)
            if leaf:
                if not isinstance(child, dict):
                    continue
                has = leaf in child
                value = child.get(leaf)
                key = f"{key}.{leaf}"
            else:
                has, value = True, child
            out.append({"name": str(name), "key": key, "value": masked(key, value, r.secret) if has else None, "set": has})
            seen.add(str(name))
    if not listy:
        for name in entry_names(r):
            if name not in seen:
                key = f"{section}.{name}" + (f".{leaf}" if leaf else "")
                out.append({"name": name, "key": key, "value": None, "set": False})
    return out, (masked(section, whole) if whole is not _MISSING else None)


def _plain_rows():
    from halo_harness.settings_catalog import rows
    return [x for x in rows() if x.kind != "keyed"]


def value_of(r, data) -> dict:
    """One row's view: {value, set, default, masked, cli} (a keyed row: entries and section too)."""
    from halo_harness.settings_catalog import cli_line, keyed_parts
    if r.kind == "keyed":
        entries, section = _entries(r, data)
        sec_key = keyed_parts(r)[0]
        return {"value": None, "set": any(e["set"] for e in entries), "default": r.default, "masked": r.secret,
                "entries": entries, "section": section, "cli": cli_line(sec_key, section)}
    got = walk(data, r.key)
    is_set = got is not _MISSING
    value = masked(r.key, got, r.secret) if is_set else None
    shown = value if is_set else r.default
    cli = cli_line(r.key, None if r.secret else shown)
    return {"value": value, "set": is_set, "default": r.default, "masked": bool(r.secret and is_set), "cli": cli}


def values(data) -> dict:
    from halo_harness.settings_catalog import rows
    return {r.key: value_of(r, data) for r in rows()}


def _shown(value, secret: bool) -> str:
    return "the value" if secret else repr(value)[:80]


def coerce(kind: str, choices, value, key: str, secret: bool = False) -> "tuple[object, list]":
    """(the value to write, []) or (None, [one line per problem]) for a value posted to a row of `kind`."""
    if value is None or (isinstance(value, str) and not value.strip() and kind not in ("list", "mapping")):
        return None, [f"{key}: needs a value (Reset to default clears it)"]
    shown = _shown(value, secret)
    if kind == "bool":
        if isinstance(value, bool):
            return value, []
        word = str(value).strip().lower()
        if word in _TRUE or word in _FALSE:
            return word in _TRUE, []
        return None, [f"{key}: {shown} is not true or false"]
    if kind == "int":
        if isinstance(value, int) and not isinstance(value, bool):
            return value, []
        if isinstance(value, float) and value.is_integer():
            return int(value), []
        if isinstance(value, str) and value.strip().lstrip("-").isdigit():
            return int(value.strip()), []
        return None, [f"{key}: {shown} is not a whole number"]
    if kind == "float":
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value, []
        try:
            return float(str(value).strip()), []
        except ValueError:
            return None, [f"{key}: {shown} is not a number"]
    if kind == "enum":
        word = value if isinstance(value, str) else json.dumps(value)
        if word in choices:
            return word, []
        return None, [f"{key}: {shown} is not one of {', '.join(choices)}"]
    if kind in ("list", "mapping"):
        want, name = (list, "a list") if kind == "list" else (dict, "a mapping")
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except ValueError as e:
                return None, [f"{key}: not valid JSON ({e})"]
        if isinstance(value, want):
            return value, []
        return None, [f"{key}: {shown} is not {name}"]
    if not isinstance(value, str):
        return None, [f"{key}: {shown} is not text"]
    return value.strip(), []


def write_list_entry(section: str, name: str, leaf: str, value=None, remove: bool = False) -> "list[str]":
    """Set (or remove) field `leaf` of the entry named `name` in the list at `section` (`ollama.hosts[lan].ssh`);
    the whole list is written back with `set_config_value`. Problems, or []."""
    from halo_harness.theme import get_config_value, set_config_value
    items = get_config_value(section, default=None)
    if not isinstance(items, list):
        return [f"{section} has no entries yet: add one with its JSON first"]
    for i, item in enumerate(items):
        if isinstance(item, dict) and (str(item.get("name") or i) == name):
            new = dict(item)
            if remove:
                new.pop(leaf, None)
            else:
                new[leaf] = value
            out = list(items)
            out[i] = new
            set_config_value(section, out)
            return []
    return [f"{section} has no entry named {name!r}"]
