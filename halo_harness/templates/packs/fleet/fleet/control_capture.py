"""halo_harness.fleet.control_capture -- a hub's capture on a member's display (Halo 3.3.7.0 R4; the 3.3.6.0 R6
leftover: "the member would run `capture_for` itself and keep the file on its own disk").

    run(handle, fields) -> {ok, path, bytes, w, h, say, image?}
        the member's own capture (tools/screenshot.capture_for into that session's images folder on the member's disk,
        `fields`: target, title, rect, display); the hub gets the path and the size, never the image, unless this
        member's `fleet.share_captures` is true (then `image` is the PNG, base64, at most MAX_SHARE bytes)
fleet/control.py runs it under `fleet.allow_control` like a steer (`ask`: the owner's card first; `none`: refused). The
capture writes only into Halo's own attachments folder on the member.
"""

from __future__ import annotations

import base64
from pathlib import Path
from halo_harness.ext import core as _core

MAX_SHARE = 5 * 2 ** 20
TARGETS = ("screen", "window", "region")


def share_captures() -> bool:
    identity = _core.module("peers.identity")
    return identity.config_value("fleet.share_captures", False) is True


def run(handle, fields: dict) -> dict:
    capture_for = _core.get("tools.screenshot", "capture_for")
    target = str(fields.get("target") or "screen")
    if target not in TARGETS:
        raise ValueError(f"target is one of {', '.join(TARGETS)}, not {target!r}")
    rect = fields.get("rect")
    sid = getattr(handle, "session_id", None) or (handle.status() or {}).get("session_id") if handle is not None else None
    got = capture_for(sid, target, title=fields.get("title") or None, rect=rect if rect else None,
                      display=fields.get("display") or None)
    if not got.get("ok"):
        return {"ok": False, "say": got.get("say") or "the capture did not happen"}
    path = Path(got["path"])
    out = {"ok": True, "path": str(path), "bytes": got.get("bytes") or (path.stat().st_size if path.is_file() else None),
           "w": got.get("width"), "h": got.get("height"), "shared": False}
    if share_captures() and path.is_file() and path.stat().st_size <= MAX_SHARE:
        out.update(image=base64.b64encode(path.read_bytes()).decode("ascii"), shared=True)
    out["say"] = (f"captured on the member: {out['w']}x{out['h']}, {out['bytes']:,} bytes at {out['path']} (kept on its "
                  "disk" + ("; the image came with it: fleet.share_captures is on there)" if out["shared"] else
                         "; the image stays there: fleet.share_captures is off)"))
    return out
