"""halo_harness.ext.events -- a pack's frame on Studio's live feed
(extension API 1.0).

    publish_event("doc-review", "review.done", {"file": "README.md", "findings": 3})

The frame is `{"session_id": "pack:<id>", "event": "pack_event", "pack":
"<id>", "data": {"pack", "kind", "data"}, "ts"}`, published through
`EventBridge.publish_local` of the Studio this process serves (or the
`bridge` given). Answers True when a Studio took it, False when this
process serves none. `kind` is a name such as `review.done` (lower-case,
digits, `.`, `_`, `-`); the kinds a pack publishes are listed under
`contributes.events` in its pack.yaml (typed event schemas: planned).
"""

from __future__ import annotations

import time

FRAME_KIND = "pack_event"


def _bridge():
    """The bridge of the Studio this process serves; None when it serves none (Studio is never imported here)."""
    import sys
    S = sys.modules.get("halo_harness.studio.server")
    srv = getattr(S, "_BACKGROUND", {}).get("server") if S is not None else None
    if srv is None:
        return None
    from halo_harness.studio.events import bridge_for
    return bridge_for(srv)


def publish_event(pack_id: str, kind: str, data=None, *, bridge=None) -> bool:
    from halo_harness.packs.manifest import EVENT_RE
    from halo_harness.packs.names import pack_id_problem
    line = pack_id_problem(pack_id)
    if line:
        raise ValueError(line)
    if not isinstance(kind, str) or not EVENT_RE.match(kind):
        raise ValueError(f"event kind {kind!r} is not an event name (lower-case, digits, . _ -)")
    target = bridge if bridge is not None else _bridge()
    if target is None:
        return False
    target.publish_local({"session_id": f"pack:{pack_id}", "event": FRAME_KIND, "pack": pack_id,
                          "data": {"pack": pack_id, "kind": kind, "data": data}, "ts": time.time()})
    return True


__all__ = ["publish_event"]
