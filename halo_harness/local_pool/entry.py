"""halo_harness.local_pool.entry -- the running pool as the `huggingface.local_servers` entry named `pool` (Halo 3.3.8.0
R3; docs/CONFIG.md "huggingface.local_servers"; `hf:local/<model>@pool`).

    write(*, url, model, ctx, log, members, cache) -> the entry   {name: "pool", url: http://<LAN address>:<port>/v1,
        api_key_env: HALO_SECRET_POOL_API_KEY, max_ctx: the fit's window (agent/model_window.window_of and every
        request clamp to it), log: the controller's llama-server log (R2's server-log reader tails it), runtime:
        llama-server, members, model, cache, pool: true}
    remove() -> bool        the entry taken out (the pool stopped)
    current() -> the entry | None        clash() -> the line when a `pool` entry there is not the pool's
    name_for(url) -> "pool" when `url` is the pool entry's (a call's ledger line names the pool as its host), else None
    new_key() -> the generated api key, kept in the env file under KEY_ENV (never in config.json, never in a log line)
    key() -> the key in force | None
"""

from __future__ import annotations

import os
import secrets
from typing import Optional

from halo_harness.local_pool import POOL_SERVER_NAME

KEY_ENV = "HALO_SECRET_POOL_API_KEY"


def _servers() -> list:
    from halo_harness.theme import get_config_value
    raw = get_config_value("huggingface.local_servers", default=None)
    return [e for e in raw if isinstance(e, dict)] if isinstance(raw, list) else []


def current() -> Optional[dict]:
    return next((e for e in _servers() if str(e.get("name") or "").lower() == POOL_SERVER_NAME), None)


def _base(url: str) -> str:
    u = str(url or "").rstrip("/")
    return u[:-3] if u.endswith("/v1") else u


def name_for(url: str):
    e = current()
    return POOL_SERVER_NAME if e is not None and e.get("pool") is True and _base(e.get("url")) == _base(url) else None


def clash() -> str:
    e = current()
    if e is not None and e.get("pool") is not True:
        return (f"huggingface.local_servers has an entry named {POOL_SERVER_NAME!r} that the pool did not write: rename "
                "it first (the pool is hf:local/<model>@pool)")
    return ""


def write(*, url: str, model: str, ctx: int, log: str, members: list, cache: str) -> dict:
    from halo_harness.theme import set_config_value
    entry = {"name": POOL_SERVER_NAME, "url": url, "api_key_env": KEY_ENV, "max_ctx": int(ctx), "log": log,
             "runtime": "llama-server", "members": list(members), "model": model, "cache": cache, "pool": True}
    rows = [e for e in _servers() if str(e.get("name") or "").lower() != POOL_SERVER_NAME] + [entry]
    set_config_value("huggingface.local_servers", rows)
    return entry


def remove() -> bool:
    from halo_harness.theme import set_config_value
    rows = _servers()
    kept = [e for e in rows if not (str(e.get("name") or "").lower() == POOL_SERVER_NAME and e.get("pool") is True)]
    if len(kept) == len(rows):
        return False
    set_config_value("huggingface.local_servers", kept)
    return True


def new_key() -> str:
    from halo_harness.init_cli import _env_file_path, _write_env_var
    k = secrets.token_urlsafe(24)
    _write_env_var(_env_file_path(), KEY_ENV, k)
    os.environ[KEY_ENV] = k
    return k


def key() -> Optional[str]:
    if os.environ.get(KEY_ENV):
        return os.environ[KEY_ENV]
    try:
        from halo_harness.providers.config import load_provider_env_files
        load_provider_env_files()
    except Exception:
        return None
    return os.environ.get(KEY_ENV) or None
