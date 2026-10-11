"""halo_harness.remote.signal_errors -- signal-cli's JSON-RPC error codes as
Python exceptions (SIGNAL-RESEARCH.md sections 1 and 8). The bridge keys on
the numeric `code`, never on the message text.

    -1  user error              UserFailure
    -3  I/O error (network)     IOFailure       -> reconnect with backoff
    -4  untrusted / changed key UntrustedKey    -> block the peer, notify
    -5  server rate limit       RateLimited     -> pause `retry_after` s, surface `token`
    -6  captcha rejected        CaptchaRejected
"""

from __future__ import annotations

from typing import Optional


class SignalError(Exception):
    code = -32603

    def __init__(self, message: str = "", code: Optional[int] = None, data=None) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        self.data = data


class UserFailure(SignalError):
    code = -1


class IOFailure(SignalError):
    code = -3


class UntrustedKey(SignalError):
    code = -4


class RateLimited(SignalError):
    code = -5

    def __init__(self, message: str = "", code: Optional[int] = None, data=None,
                 retry_after: float = 0.0, token: str = "") -> None:
        super().__init__(message, code, data)
        self.retry_after = retry_after
        self.token = token


class CaptchaRejected(SignalError):
    code = -6


BY_CODE = {-1: UserFailure, -3: IOFailure, -4: UntrustedKey, -5: RateLimited, -6: CaptchaRejected}


def _results(data) -> list:
    if isinstance(data, dict):
        data = data.get("results", [])
    return [r for r in data if isinstance(r, dict)] if isinstance(data, list) else []


def error_from(err: dict) -> SignalError:
    """The exception for a JSON-RPC `error` object."""
    code = err.get("code") if isinstance(err, dict) else None
    message = str((err or {}).get("message") or "") if isinstance(err, dict) else str(err)
    data = err.get("data") if isinstance(err, dict) else None
    cls = BY_CODE.get(code, SignalError)
    if cls is RateLimited:
        retry, token = 0.0, ""
        for r in _results(data):
            if r.get("retryAfterSeconds"):
                retry = max(retry, float(r["retryAfterSeconds"]))
            token = token or str(r.get("token") or "")
        return RateLimited(message, code, data, retry_after=retry or 60.0, token=token)
    return cls(message, code if isinstance(code, int) else None, data)
