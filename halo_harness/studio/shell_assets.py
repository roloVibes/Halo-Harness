"""halo_harness.studio.shell_assets -- the last touch on the served index.html (Halo 3.6.0.0 R0a, the boot hop).

A Studio page opened while another Studio page in the same tab was still loading (a reload pressed twice, a deep link
typed into a tab that shows Studio, a link clicked as the page came up) now and then never ran its script: Chrome
handed the new page the `studio.js` load the old page had in flight, the old page's going cancelled it, and the new
page sat with its owner salt on <html> and an empty #root (seen about 1 in 250 back-to-back navigations under
HALO_STUDIO_SLOW_MS=400; the Session driver hid it by going through about:blank). Every served page now names its
script and its sheet with a query of its own (`./studio.js?b=<nonce>`), so no page can share another page's load:
each fetches and runs its own. The files are the same (the server ignores the query); every answer is `no-store`
already, so nothing is cached that the query would bypass.

    shell_page(page, handler)   the owner salt (owner_proof.owner_attr) and the per-page asset names
    fresh_assets(page)          the per-page asset names alone
"""
from __future__ import annotations

import re
import secrets

_ASSET = re.compile(rb'((?:src|href)=")(\./studio\.(?:js|css))(")')


def fresh_assets(page: bytes) -> bytes:
    """index.html with `?b=<nonce>` on its studio.js and studio.css (one nonce per page)."""
    nonce = secrets.token_hex(6).encode("ascii")
    return _ASSET.sub(lambda m: m.group(1) + m.group(2) + b"?b=" + nonce + m.group(3), page)


def shell_page(page: bytes, handler) -> bytes:
    """The served shell: the owner proof's salt for a navigation the person made, then its own asset names."""
    from halo_harness.studio.owner_proof import owner_attr
    return fresh_assets(owner_attr(page, handler))
