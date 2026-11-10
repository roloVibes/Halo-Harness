"""halo_harness.providers.copilot_account -- what Halo remembers about the Copilot sign-in that is not a secret
(Halo 3.3.17.0 R1): `<state>/copilot/account.json`.

    {"username": "someone@pretend-tenant.example", "name": "...", "tenant": "...", "api": "workiq",
     "signed_in_at": <epoch>, "access_expires_at": <epoch>, "last_error": {"kind", "line", "at"} | null}

`halo copilot status`, the doctor row and Studio's card read it, so none of them needs a network call. The refresh
token lives in the env file (`HALO_SECRET_COPILOT_REFRESH`), the access token in memory only: neither is ever
written here.
"""

from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from typing import Optional

_KEYS = ("username", "name", "tenant", "api", "signed_in_at", "access_expires_at", "last_error")


def path() -> Path:
    from halo_harness.providers.copilot_config import state_dir
    return state_dir() / "account.json"


def load() -> dict:
    try:
        data = json.loads(path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(**fields) -> dict:
    """Merge `fields` (the known keys only) into the file and return the whole record."""
    data = load()
    data.update({k: v for k, v in fields.items() if k in _KEYS})
    try:
        from halo_harness.privateio import write_private_atomic
        p = path()
        p.parent.mkdir(parents=True, exist_ok=True)
        write_private_atomic(p, json.dumps(data, indent=2, ensure_ascii=False))
    except OSError:
        pass
    return data


def forget() -> bool:
    try:
        path().unlink()
        return True
    except OSError:
        return False


def note_error(kind: str, line: str) -> None:
    save(last_error={"kind": kind, "line": line, "at": time.time()})


def note_token(expires_at: float, api: str) -> None:
    save(access_expires_at=float(expires_at), api=api, last_error=None)


def id_claims(id_token: Optional[str]) -> dict:
    """The id token's payload, read without checking its signature: only who signed in is taken from it, for
    display. {} when there is none."""
    if not isinstance(id_token, str) or id_token.count(".") < 2:
        return {}
    part = id_token.split(".")[1]
    try:
        raw = base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))
        data = json.loads(raw.decode("utf-8"))
        return data if isinstance(data, dict) else {}
    except (ValueError, UnicodeDecodeError):
        return {}


def note_signin(id_token: Optional[str], tenant: str, api: str, expires_at: float) -> dict:
    claims = id_claims(id_token)
    who = str(claims.get("preferred_username") or claims.get("upn") or claims.get("email") or "")
    return save(username=who, name=str(claims.get("name") or ""), tenant=str(claims.get("tid") or tenant), api=api,
                signed_in_at=time.time(), access_expires_at=float(expires_at), last_error=None)


def when(epoch) -> str:
    """`2026-11-10 14:05` local time, '' for nothing."""
    if not isinstance(epoch, (int, float)) or isinstance(epoch, bool) or epoch <= 0:
        return ""
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(epoch))
