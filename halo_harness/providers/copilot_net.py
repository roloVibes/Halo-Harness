"""halo_harness.providers.copilot_net -- one HTTP call of the Copilot door (Halo 3.3.17.0 R1).

Every request goes through `providers.http.urlopen_tls`: the TLS policy, the custom CA bundle and offline mode
apply with no code of their own here (an offline refusal raises before any socket opens, and comes back as a
`CopilotError` carrying the existing refusal line). An answer of any status is returned, never raised:
`Reply(status, headers, data, text)`.

Nothing here logs: a request body (a code, a refresh token) and an answer (an access token) never reach a log line.
"""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Optional

TIMEOUT_S = 60.0


class CopilotError(Exception):
    """One plain line: what went wrong and the one next step. `kind` names it for the doctor row and the tests:
    signin, expired, consent, licence, billing, throttled, offline, network, answer."""

    def __init__(self, line: str, kind: str = "answer", status: Optional[int] = None):
        super().__init__(line)
        self.line, self.kind, self.status = line, kind, status


@dataclass
class Reply:
    status: int
    headers: dict = field(default_factory=dict)
    data: object = None
    text: str = ""

    def header(self, name: str) -> str:
        low = name.lower()
        return next((str(v) for k, v in self.headers.items() if k.lower() == low), "")


def _decode(raw: bytes) -> "tuple[object, str]":
    text = raw.decode("utf-8", "replace") if raw else ""
    try:
        return (json.loads(text) if text.strip() else None), text
    except ValueError:
        return None, text


def request(method: str, url: str, *, form: Optional[dict] = None, body: Optional[dict] = None,
            headers: Optional[dict] = None, timeout: float = TIMEOUT_S) -> Reply:
    """One call; `form` is sent url-encoded, `body` as JSON."""
    from halo_harness.providers.http import UpstreamConnectError, is_offline_refusal_message, urlopen_tls
    hdrs = {"Accept": "application/json", "User-Agent": "halo-harness"}
    data = None
    if form is not None:
        data = urllib.parse.urlencode(form).encode("ascii")
        hdrs["Content-Type"] = "application/x-www-form-urlencoded"
    elif body is not None:
        data = json.dumps(body).encode("utf-8")
        hdrs["Content-Type"] = "application/json"
    hdrs.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    host = urllib.parse.urlparse(url).hostname or url
    try:
        with urlopen_tls(req, timeout=timeout) as resp:
            parsed, text = _decode(resp.read())
            return Reply(resp.status, dict(resp.headers.items()), parsed, text)
    except urllib.error.HTTPError as e:
        try:
            raw = e.read()
        except Exception:
            raw = b""
        parsed, text = _decode(raw)
        return Reply(e.code, dict(e.headers.items()) if e.headers else {}, parsed, text)
    except UpstreamConnectError as e:
        msg = str(e)
        if is_offline_refusal_message(msg):
            raise CopilotError(f"Copilot: {msg} (turn offline mode off to reach Copilot)", "offline") from None
        raise CopilotError(f"Copilot: cannot reach {host}: {msg}", "network") from None
    except (urllib.error.URLError, socket.timeout, OSError) as e:
        why = getattr(e, "reason", None) or e
        raise CopilotError(f"Copilot: cannot reach {host}: {why}", "network") from None


def error_text(reply: Reply) -> str:
    """The answer's own error words: `error_description`, `error.message`, `error` or the raw text, one line."""
    d = reply.data
    if isinstance(d, dict):
        err = d.get("error")
        if isinstance(d.get("error_description"), str):
            return d["error_description"].splitlines()[0][:300]
        if isinstance(err, dict):
            return str(err.get("message") or err.get("code") or "").splitlines()[0][:300] if (err.get("message") or err.get("code")) else ""
        if isinstance(err, str):
            return err[:300]
    return (reply.text or "").strip().splitlines()[0][:300] if (reply.text or "").strip() else ""
