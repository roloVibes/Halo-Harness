"""halo_harness.remote.signal_config -- where the Signal bridge keeps its
files and how it reads its settings (Halo 2.0.9 round 3).

Everything lives under `<state>/remote/` (`~/.halo/remote/`, directory 0700):

    signal.json   the signal-cli settings (written by `halo remote signal
                  setup` in round 4; this module reads it)
    signal-cli/   signal-cli's own data directory (`-d`)
    peers.json    paired phones (pairing.py), 0600
    pending.json  contact requests, queued trust steps and notices, 0600
    audit.jsonl   one hashed line per command (audit.py), 0600

`signal.json` keys (all optional except `account`; unknown keys are kept):

    binary          path of signal-cli, or a list of argv words that start it
                    (tests use [sys.executable, ".../fake_signal_cli.py"])
    account         the account signal-cli runs as (a number, or an ACI for a
                    numberless linked account)
    identity_model  "dedicated" (default: a number of its own) or "linked"
                    (a secondary device of the owner's account, driven
                    through Note to Self)
    own_aci         the account's own ACI; required for "linked" (the
                    Note-to-Self filter compares against it)
    transport       "stdio" (default: spawn `signal-cli jsonRpc`), "socket"
                    (client of `daemon --socket`, POSIX) or "tcp" (client of
                    `daemon --tcp`)
    socket / tcp    the daemon endpoint for those two transports
                    (`tcp` is "127.0.0.1:7583")
    receive_mode    "manual" (default; the bridge calls `subscribeReceive`,
                    so messages wait on Signal's server while it is down),
                    "on-start" or "on-connection"
    data_dir        signal-cli's `-d` directory (default <remote>/signal-cli)
    extra_args      more global flags placed before the subcommand

The `remote.*` keys in `~/.halo/config.json` this round reads are listed in
`REMOTE_KEYS`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from halo_harness.config.paths import bridge_home
from halo_harness.privateio import ensure_private_dir

# config.json key -> default
REMOTE_KEYS = {
    "remote.rate_per_minute": 30,       # commands per minute per peer before the bridge drops and tells the phone once
    "remote.verbosity": "loud",         # relay level at attach: "loud" (text + cards) or "quiet" (cards, errors, turn_done)
    "remote.stale_window_s": 300,       # a signed command older (or newer) than this is refused
    "remote.pair_code_ttl_s": 600,      # lifetime of the one-time pairing code
}

SIGNAL_DEFAULTS = {
    "binary": "signal-cli",
    "account": "",
    "identity_model": "dedicated",
    "own_aci": "",
    "transport": "stdio",
    "socket": "",
    "tcp": "",
    "receive_mode": "manual",
    "data_dir": "",
    "extra_args": [],
}


def remote_dir() -> Path:
    d = bridge_home() / "remote"
    d.mkdir(parents=True, exist_ok=True)
    ensure_private_dir(d)
    return d


def signal_json_path() -> Path:
    return remote_dir() / "signal.json"


def load_signal_config(path=None) -> dict:
    """`signal.json` merged over `SIGNAL_DEFAULTS`; `data_dir` is resolved to
    its default. A missing or unreadable file gives the defaults."""
    cfg = dict(SIGNAL_DEFAULTS)
    try:
        raw = json.loads(Path(path or signal_json_path()).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raw = {}
    if isinstance(raw, dict):
        cfg.update(raw)
    if not cfg.get("data_dir"):
        cfg["data_dir"] = str(remote_dir() / "signal-cli")
    return cfg


def remote_setting(key: str) -> Any:
    """A `remote.*` value from config.json, or its default."""
    from halo_harness.theme import get_config_value
    default = REMOTE_KEYS[key]
    try:
        value = get_config_value(key, default)
    except Exception:
        return default
    if isinstance(default, int) and not isinstance(default, bool):
        return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else default
    return value if isinstance(value, str) and value else default


def bridge_settings() -> dict:
    """The four `remote.*` values the bridge reads, keyed without the prefix."""
    return {k.split(".", 1)[1]: remote_setting(k) for k in REMOTE_KEYS}

