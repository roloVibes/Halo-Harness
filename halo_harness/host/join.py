"""halo_harness.host.join -- a peer's half of pairing with a host (Halo 3.3.7.0 R1): `halo host join <addr> --code`.

The exchange is the hub's (fleet/pair_kex.py: the six words, one round of Diffie-Hellman authenticated with the code,
the host's certificate fingerprint inside its code-authenticated reply), sent to `POST /host/v1/join`. The result is
stored in `~/.halo/fleet.json`'s `hosts` list (fleet/store.add_host): {url, name, host_id, key_ref, fingerprint, tls,
serves [{name, port, addr}], grants, joined_at, state}; the pair key goes to `fleet/keys/<key_ref>.key` (0600).
"""

from __future__ import annotations

import hmac
import http.client
import secrets
import time
from typing import Optional

from halo_harness.fleet import pair_kex, protocol, tls
from halo_harness.fleet.relay import HubError, _connect, _decode, detect_scheme, format_url, parse_url

JOIN_PATH = "/host/v1/join"


def parse_host_url(text: str) -> "tuple[Optional[str], str, int]":
    """relay.parse_url with the host's port (7431) when none is given."""
    from halo_harness.host.state import DEFAULT_PORT
    raw = (text or "").strip()
    scheme, host, port = parse_url(raw)
    bare = raw.split("://", 1)[-1].split("/", 1)[0]
    has_port = bare.rsplit("]", 1)[-1].count(":") == 1 if bare.startswith("[") else bare.count(":") == 1
    return scheme, host, port if has_port else DEFAULT_PORT


def join(url: str, code: str, harness: dict, *, fingerprint: Optional[str] = None, timeout: float = 10.0) -> dict:
    scheme, host, port = parse_host_url(url)
    scheme = scheme or detect_scheme(host, port, timeout)
    ckey = pair_kex.code_key(code)
    a_secret, a = pair_kex.keypair()
    ts, nonce = f"{time.time():.3f}", secrets.token_hex(16)
    body = protocol.doc(harness=harness, a=a, ts=ts, nonce=nonce, mac=pair_kex.mac(ckey, "join", harness["id"], a, ts, nonce))
    try:
        conn, seen = _connect(scheme, host, port, timeout, fingerprint)
        conn.request("POST", JOIN_PATH, body=protocol.encode(body), headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        status, data = resp.status, resp.read()
        conn.close()
    except tls.PinMismatch as e:
        raise HubError(str(e)) from None
    except (OSError, http.client.HTTPException) as e:
        raise HubError(f"cannot reach the host at {host}:{port}: {e}") from None
    reply = _decode(status, data)
    who = reply.get("hub") if isinstance(reply.get("hub"), dict) else {}
    b, fp = str(reply.get("b") or ""), str(who.get("fingerprint") or "")
    if not hmac.compare_digest(str(reply.get("mac") or ""), pair_kex.mac(ckey, "joined", a, b, who.get("id"), fp)):
        raise HubError("the host's answer does not prove it knows the code; not paired")
    if scheme == "https" and fp.lower() != (seen or "").lower():
        raise HubError("the certificate the host showed is not the one it vouched for; not paired")
    serves = [r for r in reply.get("serves") or [] if isinstance(r, dict)]
    for r in serves:
        r.setdefault("addr", host)
    return {"url": format_url(scheme, host, port), "name": who.get("name"), "host_id": who.get("id"),
            "fingerprint": fp or None, "tls": scheme == "https", "serves": serves,
            "grants": [g for g in reply.get("grants") or ["view"] if isinstance(g, str)],
            "host_version": who.get("version"), "key": pair_kex.pair_key(a_secret, b, ckey, a, b)}
