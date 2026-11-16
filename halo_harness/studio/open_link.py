"""fx studio batch 2: the address Halo starts a browser with on Linux carries no Studio key.

Every account on a Linux machine reads every process's command line (/proc/<pid>/cmdline), and a browser Halo starts
holds its URL there for as long as it runs. So the browser gets a one-time link instead of `#t=<key>`:
`?o=<stamp>.<nonce>.<mac>`, signed with the key (no file, no call to Studio: any process that knows the key makes one).
Studio answers it once, within two minutes, and only to a connection of its own account (/proc/net/tcp), with a
redirect to the page and its `#t=<key>`. Windows and macOS hand the URL to the browser by a call, not an argv."""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import threading
import time
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TTL = 120.0
_USED: set = set()
_LOCK = threading.Lock()


def _mac(key: str, stamp: str, nonce: str) -> str:
    return hmac.new(key.encode("utf-8"), f"{stamp}.{nonce}".encode("ascii"), hashlib.sha256).hexdigest()[:32]


def once_link(url: str, now: Optional[float] = None) -> str:
    """`url` with its `#t=<key>` swapped for a one-time `o=` (an address with no key comes back as it was)."""
    parts = urlsplit(url)
    if parts.hostname != "127.0.0.1" or not parts.fragment.startswith("t="):
        return url
    stamp, nonce = str(int(time.time() if now is None else now)), secrets.token_urlsafe(12)
    query = parse_qsl(parts.query, keep_blank_values=True) + [("o", f"{stamp}.{nonce}.{_mac(parts.fragment[2:], stamp, nonce)}")]
    return urlunsplit((parts.scheme, parts.netloc, parts.path or "/", urlencode(query), ""))


def redeem(path_query: str, key: str, *, now: Optional[float] = None, peer_uid: Optional[int] = None,
           own_uid: Optional[int] = None) -> Optional[str]:
    """The Location for a valid, unused link (its path and query without `o`, then `#t=<key>`); None otherwise."""
    parts = urlsplit(path_query)
    query = parse_qsl(parts.query, keep_blank_values=True)
    once = [v for k, v in query if k == "o"]
    bits = once[0].split(".") if len(once) == 1 else []
    if len(bits) != 3 or not bits[0].isdigit() or not hmac.compare_digest(bits[2], _mac(key, bits[0], bits[1])):
        return None
    age = (time.time() if now is None else now) - int(bits[0])
    # Root (uid 0) is let through: it reads every account's files and processes, the key included, so refusing it
    # guards nothing, and WSL2's localhost relay (a Windows browser opening a Studio inside WSL) connects as root.
    if not (-5 <= age <= TTL) or (peer_uid is not None and own_uid is not None and peer_uid not in (own_uid, 0)):
        return None
    with _LOCK:
        if once[0] in _USED:
            return None
        _USED.add(once[0])
    rest = urlencode([(k, v) for k, v in query if k != "o"])
    return (parts.path or "/") + (f"?{rest}" if rest else "") + f"#t={key}"


def peer_uid(server_port: int, client_port: int, table: Optional[str] = None) -> Optional[int]:
    """The account that owns the client end of a loopback connection to `server_port` (Linux's /proc/net/tcp; the
    `uid` column); None when it cannot be told (no such table, no such row)."""
    if table is None:
        try:
            with open("/proc/net/tcp", encoding="ascii") as f:
                table = f.read()
        except OSError:
            return None
    want = (f":{client_port:04X}", f":{server_port:04X}")
    for line in table.splitlines()[1:]:
        cols = line.split()
        if len(cols) > 7 and cols[1].endswith(want[0]) and cols[2].endswith(want[1]) and cols[7].isdigit():
            return int(cols[7])
    return None


GONE = (b"<!doctype html><meta charset=utf-8><title>Halo Studio</title><p>This link opens Studio once, for the account"
        b" that started it, within two minutes. Run <code>halo studio</code> again, or open the address it printed.</p>")


def answer(handler) -> None:
    """GET /?...&o=...: the redirect to the page with its key, or a page that says how to open Studio."""
    uid = getattr(os, "getuid", None)
    own = uid() if uid else None
    peer = peer_uid(handler.server.server_address[1], handler.client_address[1]) if own is not None else None
    where = redeem(handler.path, handler.server.token, peer_uid=peer, own_uid=own)
    if where:
        handler._send(302, b"", "text/plain; charset=utf-8", {"Location": where})
    else:
        handler._send(403, GONE, "text/html; charset=utf-8")
