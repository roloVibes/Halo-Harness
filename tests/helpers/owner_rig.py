"""tests.helpers.owner_rig -- one HTTP request to a test's Studio as a browser would make it, any header or none
(Halo 3.3.14.0 R1: the owner proof and a pack's key, studio/owner_proof.py).

    status, headers, body = fetch(url, method="POST", data=b"{}", headers={"Authorization": "Bearer ..."})
"""

from __future__ import annotations

import urllib.error
import urllib.request


def fetch(url: str, *, method: str = "GET", data: "bytes | None" = None, headers: "dict | None" = None):
    """`(status, headers, body bytes)`; an HTTP error answers its own status, headers and body."""
    req = urllib.request.Request(url, data=data, method=method)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()
