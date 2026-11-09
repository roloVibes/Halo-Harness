"""halo_signal.settings -- the pack's settings and signal-cli's account settings.

The pack's settings live under `packs.settings.signal` in ~/.halo/config.json (Setup -> Signal, or `halo config
set packs.settings.signal.<key> <value>`), over the defaults in pack.yaml:

    on               true   the bridge answers (false: `/signal off`, every phone told nothing and nothing read)
    rate_per_minute  30     commands per minute per phone before they are dropped (the phone is told once)
    verbosity        loud   loud: every turn of the attached session reaches the phone; quiet: only the phone's own
    stale_window_s   300    a signed message further than this from the clock is turned away
    pair_ttl_s       600    how long a pairing phrase is good for
    home_dir         ""     where a phone's sessions start (empty: your home folder); each phone may have its own
    model            ""     the model a phone's session starts on (empty: your default model)
    notify           [asks, errors, supervisor]   what arrives unprompted on a newly paired phone (`/notify`)

signal.json in the data folder holds signal-cli's side (written by `/signal link` and `/signal register`; unknown
keys are kept): binary (a path, or a list of argv words), account, identity_model (dedicated | linked), own_aci (for
linked: Note to Self), transport (stdio | socket | tcp), socket, tcp, receive_mode (manual), data_dir (default the
data folder's signal-cli/), extra_args.
"""

from __future__ import annotations

import json

from halo_harness.ext import get_config, set_config

from halo_signal import PACK, files

DEFAULTS = {"on": True, "rate_per_minute": 30, "verbosity": "loud", "stale_window_s": 300, "pair_ttl_s": 600,
            "home_dir": "", "model": "", "notify": ["asks", "errors", "supervisor"]}
SIGNAL_DEFAULTS = {"binary": "signal-cli", "account": "", "identity_model": "dedicated", "own_aci": "",
                   "transport": "stdio", "socket": "", "tcp": "", "receive_mode": "manual", "data_dir": "",
                   "extra_args": []}


def get(key: str):
    try:
        value = get_config(PACK, key, None)
    except Exception:
        value = None
    default = DEFAULTS[key]
    if value is None or type(value) is not type(default):
        return default
    return value


def put(key: str, value) -> "list[str]":
    try:
        return set_config(PACK, key, value)
    except Exception as e:
        return [f"{key}: {type(e).__name__}: {e}"]


def bridge() -> dict:
    return {k: get(k) for k in ("rate_per_minute", "verbosity", "stale_window_s", "pair_ttl_s")}


def signal_path():
    return files.path("signal.json")


def load_signal() -> dict:
    cfg = dict(SIGNAL_DEFAULTS)
    cfg.update(files.read_json(signal_path()))
    if not cfg.get("data_dir"):
        cfg["data_dir"] = str(files.path("signal-cli"))
    return cfg


def save_signal(**updates) -> dict:
    data = files.read_json(signal_path())
    data.update(updates)
    files.write_text(signal_path(), json.dumps(data, indent=2, sort_keys=True) + "\n")
    return data


def binary_words(cfg: dict) -> list:
    b = cfg.get("binary") or "signal-cli"
    return [str(x) for x in b] if isinstance(b, (list, tuple)) else [str(b)]
