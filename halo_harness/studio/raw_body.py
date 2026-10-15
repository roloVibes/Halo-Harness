"""halo_harness.studio.raw_body -- a Studio route that answers with bytes, not
JSON (Halo 3.0.5.0 "Fleet" round R4: a flight recording's HTML at
`GET /api/fleet/recordings/<name>`). A handler returns `(200, RawBody(...))`;
studio/server.py `_api` sends it with its own content type and headers, behind
the same token guard as every route.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# A recording is one self-contained page: its inline style and script only, nothing fetched.
RECORDING_CSP = ("default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; "
                 "base-uri 'none'; form-action 'none'")


@dataclass
class RawBody:
    body: bytes
    ctype: str = "application/octet-stream"
    headers: dict = field(default_factory=dict)


def html_download(body: bytes, name: str) -> RawBody:
    safe = "".join(c for c in str(name) if c.isalnum() or c in "._-")[:160] or "recording.html"
    return RawBody(body, "text/html; charset=utf-8",
                   {"Content-Security-Policy": RECORDING_CSP, "Content-Disposition": f'attachment; filename="{safe}"'})
