"""halo_harness.schemas.config_json -- the shape of `~/.halo/config.json`.

Every top-level key some part of Halo reads (`get_config_value` /
`load_config` callers, the table in docs/CONFIG.md) with its type. The keys
holding a whole feature's settings (`fleet`, `remote`, `ollama`, ...) are
checked as mappings; what sits inside them is read by that feature, which
falls back to its default on a value it does not understand.
"""

from __future__ import annotations

from halo_harness.schemas.check import BOOL, LIST, MAPPING, STRING, obj


def _theme_names() -> list:
    from halo_harness.theme import VALID_THEMES
    return sorted(VALID_THEMES)


_SCALARS = {
    "model": STRING,
    "team": STRING,
    "theme_toggle_previous": STRING,
    "theme_scene": BOOL,
    "theme_variant": STRING,
    "images": STRING,
    "intro": BOOL,
    "mcpPreload": LIST,
    "compactionModel": STRING,
    "quit_on_double_ctrl_c": BOOL,
    "tips": BOOL,
    "model_memory": STRING,
    "permission_mode": STRING,
    "effort": STRING,
}

_SECTIONS = ("agents", "clipboard", "comfy", "connectors", "databricks", "embeddings", "experiential", "fleet",
             "governor", "huggingface", "improve", "local", "network", "ollama", "openai", "orgs", "paperclip",
             "providers", "remote", "roles", "routing", "settings", "steer", "subscription_routes", "update",
             "worktree")


def schema() -> dict:
    props = dict(_SCALARS)
    props["theme"] = {"type": "string", "enum": _theme_names()}
    props.update({name: MAPPING for name in _SECTIONS})
    return obj(props)


def known_keys() -> list:
    return sorted(schema()["properties"])
