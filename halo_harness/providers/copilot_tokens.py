"""halo_harness.providers.copilot_tokens -- the Copilot door's tokens (Halo 3.3.17.0 R1).

* The refresh token is the one secret Halo keeps: the env file (`HALO_ENV_FILE`, else ~/.config/halo/env) as
  `HALO_SECRET_COPILOT_REFRESH`, written through `init_cli._write_env_var` (the writer `halo init` uses), removed by
  `forget_refresh`. Never config.json, never a log line, never the transcript.
* Access tokens live in this process's memory with their expiry (`_CACHE`), one per tenant + app + scope set, and are
  refreshed `EARLY_S` seconds before they expire. `halo copilot signout` forgets both.
"""

from __future__ import annotations

import os
import re
import threading
import time
from typing import Callable, Optional

from halo_harness.providers.copilot_config import SECRET_ENV, CopilotConfig, authority

EARLY_S = 60.0
_CACHE: dict = {}
_LOCK = threading.Lock()
NOW: Callable[[], float] = time.time  # a test's clock


def _key(cfg: CopilotConfig, api: str) -> tuple:
    return (cfg.tenant, cfg.client_id, " ".join(cfg.scope_list(api)))


def _env_path():
    from halo_harness.init_cli import _env_file_path
    return _env_file_path()


def refresh_token() -> str:
    """The stored refresh token: the env file first (another process may have signed in since), then this
    process's environment; '' when there is none."""
    try:
        from halo_harness.config.paths import env_file_path
        from halo_harness.providers.config import _parse_env_file
        got = _parse_env_file(env_file_path()).get(SECRET_ENV)
        if got:
            return got
    except Exception:
        pass
    return os.environ.get(SECRET_ENV, "")


def store_refresh(token: str) -> None:
    if not token:
        return
    from halo_harness.init_cli import _write_env_var
    _write_env_var(_env_path(), SECRET_ENV, token)
    os.environ[SECRET_ENV] = token


def forget_refresh() -> bool:
    """Drop the env file's line and this process's copy; True when one was there."""
    had = bool(os.environ.pop(SECRET_ENV, None))
    try:
        from halo_harness.config.paths import env_file_path
        p = env_file_path()
        if p.is_file():
            lines = p.read_text(encoding="utf-8").splitlines()
            pat = re.compile(rf"^\s*(export\s+)?{re.escape(SECRET_ENV)}\s*=")
            kept = [ln for ln in lines if not pat.match(ln)]
            if len(kept) != len(lines):
                from halo_harness.privateio import write_private_atomic
                write_private_atomic(p, "\n".join(kept) + ("\n" if kept else ""))
                had = True
    except OSError:
        pass
    return had


def remember(cfg: CopilotConfig, api: str, tokens: dict) -> dict:
    """Keep an answer's access token in memory (and a new refresh token in the env file); the cache entry."""
    try:
        life = float(tokens.get("expires_in") or 3600)
    except (TypeError, ValueError):
        life = 3600.0
    entry = {"access_token": str(tokens.get("access_token") or ""), "expires_at": NOW() + life}
    with _LOCK:
        _CACHE[_key(cfg, api)] = entry
    if tokens.get("refresh_token"):
        store_refresh(str(tokens["refresh_token"]))
    return entry


def cached(cfg: CopilotConfig, api: str) -> Optional[dict]:
    with _LOCK:
        return _CACHE.get(_key(cfg, api))


def forget_access(cfg: Optional[CopilotConfig] = None, api: Optional[str] = None) -> None:
    with _LOCK:
        if cfg is None:
            _CACHE.clear()
        else:
            _CACHE.pop(_key(cfg, api or cfg.api), None)


def refresh(cfg: CopilotConfig, api: str) -> dict:
    """`grant_type=refresh_token` once; the new cache entry, or a CopilotError (expired / consent)."""
    from halo_harness.providers import copilot_account as A
    from halo_harness.providers import copilot_errors as E
    from halo_harness.providers.copilot_net import request
    token = refresh_token()
    if not token:
        raise E.not_signed_in()
    scopes = cfg.scope_list(api)
    reply = request("POST", f"{authority(cfg.tenant)}/token", form={
        "client_id": cfg.client_id, "grant_type": "refresh_token", "refresh_token": token, "scope": " ".join(scopes)})
    if reply.status != 200 or not isinstance(reply.data, dict) or not reply.data.get("access_token"):
        err = E.token_error(reply, cfg.consent_scopes(api), refreshing=True)
        A.note_error(err.kind, err.line)
        raise err
    entry = remember(cfg, api, reply.data)
    A.note_token(entry["expires_at"], api)
    return entry


def access_token(cfg: CopilotConfig, api: Optional[str] = None) -> str:
    """A valid access token for `api`: the one in memory while it has more than EARLY_S seconds left, else a refresh."""
    api = api or cfg.api
    entry = cached(cfg, api)
    if entry and entry.get("access_token") and float(entry.get("expires_at") or 0) - EARLY_S > NOW():
        return entry["access_token"]
    return refresh(cfg, api)["access_token"]


def signout() -> list:
    """Forget the refresh token, every access token and the account record; the lines saying what went."""
    from halo_harness.providers import copilot_account as A
    lines = []
    lines.append(f"removed {SECRET_ENV} from the env file" if forget_refresh() else "no refresh token was stored")
    forget_access()
    if A.forget():
        lines.append("forgot the account record")
    return lines
