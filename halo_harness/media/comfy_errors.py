"""halo_harness.media.comfy_errors -- ComfyUI's own words for a failure: a
`POST /prompt` validation reply names each failing node and its class, an
execution error in /history names the node that raised.
"""

from __future__ import annotations

import json


def execution_error_text(prompt_id: str, status: dict) -> str:
    for msg in status.get("messages") or []:
        if isinstance(msg, (list, tuple)) and len(msg) > 1 and msg[0] == "execution_error":
            d = msg[1] or {}
            return (f"prompt {prompt_id} failed in node {d.get('node_id')} ({d.get('node_type')}): "
                    f"{d.get('exception_type', 'error')}: {str(d.get('exception_message', '')).strip()}")
    return f"prompt {prompt_id} failed: {json.dumps(status)[:400]}"


def http_error_text(method: str, path: str, raw: bytes, reason) -> str:
    """The server's own words: a /prompt validation reply names each node."""
    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        text = raw.decode("utf-8", "replace").strip()[:300]
        return f"{method} {path.split('?')[0]}: {text or reason}"
    parts = []
    err = data.get("error") if isinstance(data, dict) else None
    if isinstance(err, dict):
        parts.append(str(err.get("message") or err.get("type") or "error") + (f": {err['details']}" if err.get("details") else ""))
    elif err:
        parts.append(str(err))
    for nid, ne in ((data.get("node_errors") or {}) if isinstance(data, dict) else {}).items():
        for e in (ne or {}).get("errors") or []:
            parts.append(f"node {nid} ({ne.get('class_type')}): {e.get('message')}" + (f" -- {e['details']}" if e.get("details") else ""))
    return f"{method} {path.split('?')[0]}: " + ("; ".join(parts) or str(reason))
