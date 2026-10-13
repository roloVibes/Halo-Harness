"""halo_harness.mcp.errtext -- scrub an MCP connect/transport error text
before it is stored on a handle, printed by `/mcp`, `halo mcp list|get`,
bugreport, or appended to the per-server log.

A configured url is expanded (`?token=${PAT}` -> the real value) before it
is connected to, so an exception raised by httpx/the SDK (for example
`Client error '401 Unauthorized' for url 'https://host/sse?token=...'`)
carries the real query string. Every URL found in the text is cut down to
scheme://host:port/path and credential-shaped `key=value` / bearer text is
masked, the same way the rest of the MCP display already treats a url.
"""

from __future__ import annotations

import re
from typing import Optional

_URL_RE = re.compile(r"""(?i)\b(?:https?|wss?)://[^\s'"<>)\]]+""")
_TRAILING = ".,;:!?"


def scrub_error_text(text: Optional[str]) -> str:
    """URL query strings / userinfo / fragments and credential-shaped
    values removed; never raises."""
    if not text:
        return ""
    try:
        from halo_harness.mcp.doctor_probe import mask_secrets, mask_url

        def _sub(m: "re.Match") -> str:
            raw = m.group(0)
            core = raw.rstrip(_TRAILING)
            tail = raw[len(core):]
            masked = mask_url(core)
            return ("<url>" if masked == "?" else masked) + tail

        return mask_secrets(_URL_RE.sub(_sub, str(text)))
    except Exception:
        return str(text)
