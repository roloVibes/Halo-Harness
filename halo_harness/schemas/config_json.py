"""halo_harness.schemas.config_json -- the shape of `~/.halo/config.json`.

Every top-level key some part of Halo reads (`get_config_value` /
`load_config` callers, the table in docs/CONFIG.md) with its type. The keys
holding a whole feature's settings (`remote`, `ollama`, `host`, ...) are
checked as mappings; what sits inside them is read by that feature, which
falls back to its default on a value it does not understand.

`REMOVED_SECTIONS` are sections of a feature that is gone (Org and
Paperclip, 3.1.4.0; the cc:/cx: routes' `subscription_routes` and
`settings`, 3.1.5.0): a config.json that still has one loads as before and
the section is ignored; `halo doctor --config` names it in one line
(`removed_line`). A `fleet` section (3.5.0.0) loads too: its renamed keys are read under their new names
(config/renamed_keys.py) and the doctor names the rest in one line.
"""

from __future__ import annotations

from halo_harness.schemas.check import BOOL, LIST, MAPPING, STRING, obj


def _theme_names() -> list:
    from halo_harness.themes.registry import values  # 3.3.12.0 R1: the palette registry, ids x the modifiers; R4: + auto
    return list(values())


# Top-level keys of a removed feature (the game themes, 3.1.5.0): a config.json
# that still has one loads as before and the key is ignored; `halo doctor
# --config` names it in one line (`removed_key_line`).
REMOVED_KEYS = {"theme_scene": "3.1.5.0", "theme_toggle_previous": "3.1.5.0", "theme_variant": "3.1.5.0"}


def removed_key_line(key: str) -> str:
    """The one doctor line for a leftover key of a removed feature."""
    return f"{key}: removed in {REMOVED_KEYS[key]} with the game themes, the key is ignored"


#: 3.3.13.0 R3: keys whose feature left the core for a shipped pack -> (pack id, the pack's own key).
MOVED_KEYS = {"remote.signal.enabled": ("signal", "on"), "remote.rate_per_minute": ("signal", "rate_per_minute"),
              "remote.verbosity": ("signal", "verbosity"), "remote.stale_window_s": ("signal", "stale_window_s"),
              "remote.pair_code_ttl_s": ("signal", "pair_ttl_s"),
              # 3.4.0.0 B2: the coach and /improve are the coach pack's (its rows under Settings -> From packs)
              "coach.probe.k": ("coach", "probe.k"), "coach.probe.budget_factor": ("coach", "probe.budget_factor"),
              "coach.library.cite": ("coach", "library.cite"), "improve.enabled": ("coach", "improve.enabled"),
              "improve.model": ("coach", "improve.model"), "improve.since_days": ("coach", "improve.since_days"),
              "improve.max_candidates": ("coach", "improve.max_candidates")}
MOVED_IN = {"signal": "3.3.13.0", "coach": "3.4.0.0"}
#: 3.4.0.0 B2: a top-level section whose feature is a shipped pack's now: ignored, one doctor line (`packed_line`).
PACKED_SECTIONS = {"coach": "coach", "improve": "coach"}


def moved_key_line(key: str) -> str:
    """The one line `halo config` and the doctor say for a key that moved to a pack."""
    pack, new = MOVED_KEYS[key]
    where = "Settings -> From packs" if pack == "coach" else f"Setup -> the {pack} pack's page"
    return (f"{key} moved to the {pack} pack in {MOVED_IN[pack]}: halo config set packs.settings.{pack}.{new} <value> "
            f"(or {where})")


def packed_line(section: str) -> str:
    pack = PACKED_SECTIONS[section]
    return (f"{section}: the {pack} pack's since {MOVED_IN[pack]}, this section is ignored (its settings are "
            f"packs.settings.{pack}.<key>, Settings -> From packs, while the pack is enabled)")


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

# `coach` and `improve`: the coach pack's since 3.4.0.0 B2 (PACKED_SECTIONS); `models`: roster (3.1.9.0 R1: false keeps the model roster out
# of the main agent's context, providers/roster.py)
# `supervise` (3.1.8.0, supervise/settings.py): R2 adds replan none|auto|review, replan_forecast, replan_returns, replan_block_s, replan_stall_s, replan_cooldown_s, replan_max
# `knowledge` (3.1.8.0 R4, knowledge/): write, brief, gate_keep (3.3.16.2); `recall`: sources (3.1.8.0 R4, knowledge/sources.py)
# `databricks`: gateway.<endpoint>, dbu_price_usd (USD per DBU, default 0.07), prices.<endpoint> {in, out[, cache_read,
# cache_write]} USD per 1M tokens (3.3.3.1, providers/databricks_prices.py), catalog_max_age_hours
# `steer`: restart_when_silent, silent_restart_s (3.2.2.0 R4); `turn`: nudge_promises (3.2.2.0 R4, agent/turn_marker.py)
# `studio`: hover_cards (3.3.16.1: Agents' boxes show a hover card; false, their plain tooltips; Studio's lib/hover); alerts none|browser (3.4.1.0 R4, lib/alerts.ts)
# `ollama`: ledger (3.3.4.0 R2, ollama_steward/ledger.py)
# `control`: enabled, private; `harness`: name; `caps`: per_harness_usd_per_day, per_project_usd_per_day; `attention`:
# signal (3.5.0.0: the keys that were `fleet.*`, config/renamed_keys.py); `host`: allow_control
# `ollama`: profiles (a map "<host>|<model>" (3.3.7.0 R3: or "<host>|<model>|<role>", a lane's own) -> {num_ctx, num_predict, keep_alive, tools_max, host_for, compact_at, note, by, at}),
# steward.apply auto|review|off, steward.slow_tok_s (3.3.4.0 R3, ollama_steward/profiles.py, steward.py)
# steward.model (a model ref), steward.job (bool), steward.every_s, steward.note_every_s (seconds) (3.3.4.0 R4,
# ollama_steward/job.py, agent.py); steward.probe_new (bool: the battery on a new or changed model, 3.3.6.0 R1);
# steward.chat_tokens (int: the steward's chat's context budget, 3.3.7.0 R5, ollama_steward/chat.py)
# `host` (3.3.7.0 R1, host/state.py): port (7431), bind ("0.0.0.0"), enabled (true), tail_max (400)
# `pool` (3.3.8.0 R1, local_pool/members.py): rpc_port (50052), scan_subnets ([] of CIDRs); R3: claim_lease_s (120),
# allow_wifi (false), bind (an address), rpc_server_bin (a path or [program, args...])
# `local`: ladder (3.3.6.0 R4: the degradation ladder's rungs in order, or "off"; agent/degrade.py); min_resident_s (3.3.7.0 R3:
# the scheduler's minimum residency, local_sched/pivot.py); `routing`: local_hop (3.3.7.0 R3: the local -> local hop,
# agent/local_hop.py)
# `prompt`: lean auto|on|off, topics_max, memory_max_tokens, preflight ask|compact|send (3.3.5.0 R4, agent/prompt_lean.py,
# agent/preflight.py), shell auto|bash|powershell (3.3.16.1, agent/prompt_diet.py)
# `background`: when_done continue|tell|wait, self_turns (3.4.1.3, agent/bg_pickup.py)
_SECTIONS = ("agents", "attention", "background", "caps", "clipboard", "comfy", "connectors", "control", "copilot", "databricks",
             "embeddings", "experiential", "governor", "harness", "host", "huggingface", "knowledge", "local", "models", "network", "ollama", "openai",
             "packs", "pool", "prompt", "providers", "recall", "remote", "roles", "routing", "steer", "studio", "supervise", "turn",
             "update", "voice", "workflows", "worktree")  # 3.3.9.0 R1: voice (stt_model, tts_model, device, tts_voice); R2: the loop's
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
