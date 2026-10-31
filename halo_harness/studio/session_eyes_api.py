"""halo_harness.studio.session_eyes_api -- Halo 3.3.6.0 R6: Studio takes an image into a session's steer, takes a
screenshot for it, and says before the send whether the session's model can see.

    POST sessions/<sid>/command {cmd: steer|submit, text, image: {media_type, data_b64, name?}, eyes?}
        (studio/sessions_api.py) the image written to the session's images folder (agent/image_attach: downscaled
        past 1568 px, the 5 MB rule), and the control socket's steer carries its path (`image_path`), never the
        bytes; `eyes` (lane | describe | send) is the offer's choice made on the chip
    POST sessions/<sid>/command {cmd: screenshot, target?, title?, rect?, display?}
        one capture of THIS machine's display (tools/screenshot.py) into that session's images folder ->
        {path, name, width, height, bytes, media_type, say}; the page attaches it to the next steer
    GET  sessions/<sid>/eyes?model=<ref>   {sees: {value, truth, source}, offer: bool, line, choices}
        what the chip shows before the send (agent/eyes_offer.offer_for: no request, the caches only)

The steer's image is local to this harness: Studio writes the file where the session reads it (one home).
"""

from __future__ import annotations

import base64
import binascii
from pathlib import Path

from halo_harness.agent.image_attach import MAX_IMAGE_BYTES

MEDIA = ("image/png", "image/jpeg", "image/gif", "image/webp")
EYES = ("lane", "describe", "send")
MAX_B64 = (MAX_IMAGE_BYTES * 4) // 3 + 1024 + 4 * 1024 * 1024  # a 5 MB image before its downscale, with room


def _folder(sid: str) -> Path:
    from halo_harness.tools.screenshot import images_folder
    return images_folder(sid)


def image_fields(sid: str, body: dict) -> "tuple[int, dict]":
    """(200, {image_path, media_type, eyes_choice?}) | (200, {}) without an image | (413 | 422, {error})."""
    img = body.get("image")
    if img is None and body.get("image_path"):
        p = Path(str(body["image_path"]))
        if not p.is_file() or p.parent != _folder(sid):
            return 422, {"error": "image_path must be a capture in this session's images folder", "problems": []}
        return 200, {"image_path": str(p), **_eyes(body)}
    if img is None:
        return 200, {}
    if not isinstance(img, dict) or str(img.get("media_type") or "") not in MEDIA:
        return 422, {"error": f"image is {{media_type: one of {', '.join(MEDIA)}, data_b64}}", "problems": []}
    raw = str(img.get("data_b64") or "")
    if "," in raw[:80] and raw.startswith("data:"):
        raw = raw.split(",", 1)[1]
    if len(raw) > MAX_B64:
        return 413, {"error": f"image is about {len(raw) * 3 // 4} bytes, over the 5 MB limit", "problems": []}
    try:
        data = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError):
        return 422, {"error": "image.data_b64 is not base64", "problems": []}
    from halo_harness.agent.image_attach import ImageTooLarge, image_block_from_bytes
    try:
        block = image_block_from_bytes(data, img["media_type"], _folder(sid))
    except ImageTooLarge as e:
        return 413, {"error": str(e), "problems": []}
    return 200, {"image_path": block["image_path"], "media_type": block["source"]["media_type"], **_eyes(body)}


def _eyes(body: dict) -> dict:
    e = str(body.get("eyes") or "")
    return {"eyes_choice": e} if e in EYES else {}


def screenshot(sid: str, body: dict) -> "tuple[int, dict]":
    from halo_harness.tools.screenshot import capture_for
    got = capture_for(sid, str(body.get("target") or "screen"), title=body.get("title"), rect=body.get("rect"),
                      display=body.get("display"))
    if not got.get("ok"):
        return 422, {"error": got.get("say") or "the screenshot did not happen", "problems": []}
    p = Path(got["path"])
    return 200, {"ok": True, "result": {"path": str(p), "name": p.name, "width": got.get("width"), "height": got.get("height"),
                                        "bytes": got.get("bytes"), "media_type": "image/png", "say": got.get("say")}}


def get_eyes(req):
    from halo_harness.agent.eyes_offer import offer_for
    model = str(req.query.get("model") or "").strip()
    if not model:
        return 422, {"error": "model is the session's model ref", "problems": []}
    return 200, offer_for(model)


ROUTES = [("GET", r"^sessions/(?P<sid>[A-Za-z0-9_.:-]+)/eyes$", get_eyes)]
