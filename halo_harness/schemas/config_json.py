"""halo_harness.schemas.config_json -- the shape of `~/.halo/config.json`.

Every top-level key some part of Halo reads (`get_config_value` /
`load_config` callers, the table in docs/CONFIG.md) with its type. The keys
holding a whole feature's settings (`fleet`, `remote`, `ollama`, ...) are
checked as mappings; what sits inside them is read by that feature, which
falls back to its default on a value it does not understand.

`REMOVED_SECTIONS` are sections of a feature that is gone (Org and
Paperclip, 3.1.4.0; the cc:/cx: routes' `subscription_routes` and
`settings`, 3.1.5.0): a config.json that still has one loads as before and
the section is ignored; `halo doctor --config` names it in one line
(`removed_line`).
"""

from __future__ import annotations

from halo_harness.schemas.check import BOOL, LIST, MAPPING, STRING, obj


def _theme_names() -> list:
    from halo_harness.theme import VALID_THEMES
    return sorted(VALID_THEMES)


# Top-level keys of a removed feature (the game themes, 3.1.5.0): a config.json
# that still has one loads as before and the key is ignored; `halo doctor
# --config` names it in one line (`removed_key_line`).
REMOVED_KEYS = {"theme_scene": "3.1.5.0", "theme_toggle_previous": "3.1.5.0", "theme_variant": "3.1.5.0"}


def removed_key_line(key: str) -> str:
    """The one doctor line for a leftover key of a removed feature."""
    return f"{key}: removed in {REMOVED_KEYS[key]} with the game themes, the key is ignored"


_SCALARS = {
    "model": STRING,
    "team": STRING,
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

# `coach`: probe.k, probe.budget_factor (3.1.6.0 R2), library.cite (3.1.6.0 R3: false turns the library's
# citations off, orchestra/coach_citations.py); `models`: roster (3.1.9.0 R1: false keeps the model roster out
# of the main agent's context, providers/roster.py)
# `supervise` (3.1.8.0, supervise/settings.py): R2 adds replan none|auto|review, replan_forecast, replan_returns, replan_block_s, replan_stall_s, replan_cooldown_s, replan_max
# `knowledge` (3.1.8.0 R4, knowledge/): write, brief; `recall`: sources (3.1.8.0 R4, knowledge/sources.py)
# `databricks`: gateway.<endpoint>, dbu_price_usd (USD per DBU, default 0.07), prices.<endpoint> {in, out[, cache_read,
# cache_write]} USD per 1M tokens (3.3.3.1, providers/databricks_prices.py), catalog_max_age_hours
# `steer`: restart_when_silent, silent_restart_s (3.2.2.0 R4); `turn`: nudge_promises (3.2.2.0 R4, agent/turn_marker.py)
# `ollama`: ledger (3.3.4.0 R2, ollama_steward/ledger.py); `fleet`: ollama.share auto|all|off (3.3.4.0 R2, fleet/ollama_share.py)
# `ollama`: profiles (a map "<host>|<model>" -> {num_ctx, num_predict, keep_alive, tools_max, host_for, compact_at, note, by, at}),
# steward.apply auto|review|off, steward.slow_tok_s (3.3.4.0 R3, ollama_steward/profiles.py, steward.py)
# steward.model (a model ref), steward.job (bool), steward.every_s, steward.note_every_s (seconds) (3.3.4.0 R4,
# ollama_steward/job.py, agent.py); steward.probe_new (bool: the battery on a new or changed model, 3.3.6.0 R1)
# `host` (3.3.7.0 R1, host/state.py): port (7431), bind ("0.0.0.0"), enabled (true), tail_max (400)
# `local`: ladder (3.3.6.0 R4: the degradation ladder's rungs in order, or "off"; agent/degrade.py)
# `prompt`: lean auto|on|off, topics_max, memory_max_tokens, preflight ask|compact|send (3.3.5.0 R4, agent/prompt_lean.py,
# agent/preflight.py)
_SECTIONS = ("agents", "clipboard", "coach", "comfy", "connectors", "databricks", "embeddings", "experiential", "fleet",
             "governor", "host", "huggingface", "improve", "knowledge", "local", "models", "network", "ollama", "openai",
             "packs", "prompt", "providers", "recall", "remote", "roles", "routing", "steer", "supervise", "turn",
             "update", "worktree")
REMOVED_SECTIONS = {"orgs": "3.1.4.0", "paperclip": "3.1.4.0",
                    "settings": "3.1.5.0", "subscription_routes": "3.1.5.0"}


def removed_line(section: str) -> str:
    """The one doctor line for a leftover section of a removed feature."""
    return f"{section}: removed in {REMOVED_SECTIONS[section]}, the section is ignored"


def schema() -> dict:
    props = dict(_SCALARS)
    props["theme"] = {"type": "string", "enum": _theme_names()}
    props.update({name: MAPPING for name in _SECTIONS})
    return obj(props)


def known_keys() -> list:
    return sorted(schema()["properties"])
