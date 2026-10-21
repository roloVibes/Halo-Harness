"""halo_harness.packs.settings -- a pack's settings (Halo 3.2.0.0 R1).

A pack declares `config: {schema: {...}, defaults: {...}}` in pack.yaml; you
set values in `~/.halo/config.json` under `packs.settings.<id>` (`halo
config set packs.settings.<id>.<key> <value>`). `values(pack)` is the
defaults with your values on top; `problems(pack)` checks your values (and
the defaults) against the schema, in the `schemas.check` format:

    config:
      schema: {properties: {style: {type: string, enum: [short, long]}}, additionalProperties: false}
      defaults: {style: short}

A schema without a `type` is an object schema.
"""

from __future__ import annotations

from typing import Optional

from halo_harness.schemas.check import check


def _config(pack_manifest: dict) -> dict:
    cfg = pack_manifest.get("config") if isinstance(pack_manifest, dict) else None
    return cfg if isinstance(cfg, dict) else {}


def schema_of(pack_manifest: dict) -> Optional[dict]:
    schema = _config(pack_manifest).get("schema")
    if not isinstance(schema, dict):
        return None
    return schema if "type" in schema else {"type": "object", **schema}


def defaults_of(pack_manifest: dict) -> dict:
    d = _config(pack_manifest).get("defaults")
    return dict(d) if isinstance(d, dict) else {}


def user_values(pack_id: str) -> dict:
    from halo_harness.theme import get_config_value
    raw = get_config_value(f"packs.settings.{pack_id}", default=None)
    return dict(raw) if isinstance(raw, dict) else {}


def values(pack) -> dict:
    """The defaults with `packs.settings.<id>` on top (one level: a key you set replaces the default's)."""
    out = defaults_of(pack.manifest)
    out.update(user_values(pack.id))
    return out


def problems(pack) -> "list[str]":
    """One line per value that does not fit the pack's schema (yours, then the defaults)."""
    schema = schema_of(pack.manifest)
    if schema is None:
        return []
    out = [f"packs.settings.{pack.id}.{f['key']}: {f['text']}" if f["key"] else f"packs.settings.{pack.id}: {f['text']}"
           for f in check(user_values(pack.id), schema)]
    out += [f"{pack.id}: pack.yaml config.defaults: {f['text']}" for f in check(defaults_of(pack.manifest), schema)]
    return out


def set_value(pack, key: str, value) -> "list[str]":
    """Write `packs.settings.<id>.<key>` after checking it against the schema; `[]` on success."""
    from halo_harness.theme import set_config_value
    if not isinstance(key, str) or not key or any(not part for part in key.split(".")):
        return [f"{key!r} is not a setting name"]
    trial = user_values(pack.id)
    cursor = trial
    parts = key.split(".")
    for part in parts[:-1]:
        cursor = cursor.setdefault(part, {}) if isinstance(cursor.get(part, {}), dict) else {}
    cursor[parts[-1]] = value
    schema = schema_of(pack.manifest)
    found = check(trial, schema) if schema is not None else []
    if found:
        return [f"packs.settings.{pack.id}.{f['key']}: {f['text']}" for f in found]
    try:
        set_config_value(f"packs.settings.{pack.id}.{key}", value)
    except Exception as e:  # CorruptConfigError: config.json does not parse
        return [str(e)]
    return []
