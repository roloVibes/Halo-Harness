"""halo_harness.providers.ollama_key_migrate -- Halo 3.3.13.1 (the steward hotfix, plans/ROADMAP.md F1): an
`ollama.hosts[]` entry that holds its key VALUE in `api_key` (the usage audit found one in the owner's config.json)
is moved the first time the hosts are read (`providers.ollama.resolve_ollama_hosts`):

- the value goes into the env file (`HALO_ENV_FILE`, else `~/.config/halo/env`) under `HALO_SECRET_OLLAMA_<NAME>`
  (`init_providers._secret_env_var_name`, the name `halo init` has used since 3.2.3.0's C16) and into this process's
  environment;
- config.json keeps that NAME as `api_key_env` and loses `api_key` (the contract since 3.2.3.0);
- one line on stderr names the host and the variable, never the value.

An entry whose `api_key_env` already names a variable holding the same value just loses the copy. `halo doctor
--config` has a `key-value` row for any `api_key` that still looks like a key (`key_findings`).
"""

from __future__ import annotations

import os
import re
import sys
from typing import Callable, Optional

_NAME = re.compile(r"[A-Z_][A-Z0-9_]*")


def looks_like_key(value) -> bool:
    """A secret VALUE rather than an env-var NAME (UPPER_SNAKE) or nothing."""
    return isinstance(value, str) and bool(value.strip()) and not _NAME.fullmatch(value.strip())


def _plan(entry: dict) -> Optional[str]:
    """The env-var name to move this entry's key to, "" to drop a copy already held there, None to leave it."""
    if not isinstance(entry, dict) or not looks_like_key(entry.get("api_key")):
        return None
    have = entry.get("api_key_env")
    if isinstance(have, str) and have:
        return "" if os.environ.get(have) == entry["api_key"] else None
    from halo_harness.init_providers import _secret_env_var_name
    return _secret_env_var_name("OLLAMA", str(entry.get("name") or entry.get("url") or "default"))


def migrate(raw_hosts, *, say: Optional[Callable[[str], None]] = None):
    """`raw_hosts` back, with every key value moved out (config.json and the env file written when one moved)."""
    if not isinstance(raw_hosts, list) or not any(_plan(e) is not None for e in raw_hosts):
        return raw_hosts
    if os.environ.get("BRIDGE_TEST_NO_BACKGROUND_NET") and not (os.environ.get("BRIDGE_TEST_HOME")
                                                                 or os.environ.get("BRIDGE_STATE_DIR")):
        return raw_hosts  # a test process that lost its scratch home never rewrites the real config or env file
    say = say or (lambda line: print(line, file=sys.stderr))
    try:
        from halo_harness.init_cli import _env_file_path, _write_env_var
        from halo_harness.theme import set_config_value
        out, lines, path = [], [], None
        for entry in raw_hosts:
            name = _plan(entry)
            if name is None:
                out.append(entry)
                continue
            value = entry["api_key"].strip()
            moved = {k: v for k, v in entry.items() if k != "api_key"}
            if name:
                path = path or _env_file_path()
                _write_env_var(path, name, value)
                os.environ[name] = value
                moved["api_key_env"] = name
            out.append(moved)
            host = entry.get("name") or entry.get("url")
            lines.append(f"halo: ollama.hosts {host!r} kept its api_key as a value in config.json; moved it to "
                         f"{name} in {path} (config.json now names it: api_key_env)" if name else
                         f"halo: ollama.hosts {host!r} held a copy of the key {entry['api_key_env']} already names; "
                         "dropped the copy from config.json")
        set_config_value("ollama.hosts", out)
    except Exception as e:  # a read never fails over this: the key keeps working where it is
        say(f"halo: could not move an ollama.hosts api_key out of config.json ({type(e).__name__}); "
            "halo doctor --config names it")
        return raw_hosts
    for line in lines:
        say(line)
    return out


def key_findings(data, row: dict, finding: Callable) -> list:
    """`halo doctor --config`: one `key-value` row per `ollama.hosts[].api_key` that still holds a key value."""
    hosts = ((data or {}).get("ollama") or {}).get("hosts") if isinstance(data, dict) else None
    out = []
    for i, entry in enumerate(hosts if isinstance(hosts, list) else []):
        if isinstance(entry, dict) and looks_like_key(entry.get("api_key")):
            host = entry.get("name") or entry.get("url") or f"#{i}"
            out.append(finding("key-value", "warns", row, f"ollama.hosts {host!r}: api_key holds a key value in "
                               "config.json (the contract is an env-var name in api_key_env)",
                               key=f"ollama.hosts[{i}].api_key",
                               fix="the next halo command that reads ollama.hosts (halo models, Studio's Local) "
                                   "moves it to the env file; or set api_key_env to a variable that holds it"))
    return out
