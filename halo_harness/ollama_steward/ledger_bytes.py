"""halo_harness.ollama_steward.ledger_bytes -- Halo 3.3.5.0 R1: the bytes a
local call moved, for the ledger line's `bytes_in` (the request body as sent,
JSON) and `bytes_out` (the reply's text, thinking and tool arguments as they
streamed), which the Local tab's traffic view sums per minute.
"""

from __future__ import annotations

import json


def body_bytes(body) -> int:
    try:
        return len(json.dumps(body or {}, ensure_ascii=False, default=str).encode("utf-8"))
    except (TypeError, ValueError):
        return 0


def event_bytes(ev) -> int:
    """The reply bytes one stream event carries (a text, thinking or tool-argument delta)."""
    if not isinstance(ev, dict) or ev.get("type") != "content_block_delta":
        return 0
    d = ev.get("delta") if isinstance(ev.get("delta"), dict) else {}
    piece = d.get("text") or d.get("thinking") or d.get("partial_json") or ""
    return len(piece.encode("utf-8")) if isinstance(piece, str) else 0
