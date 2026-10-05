"""halo_harness.agent.image_attach -- Halo 2.0.3.1 (clipboard image paste):
shared plumbing for turning any image SOURCE (a clipboard read, an
existing file path, a stream-json inline base64 entry) into the two shapes
this harness needs, plus the reverse direction.

  * a WIRE block: a real Anthropic-shaped `{"type": "image", "source":
    {"type": "base64", ...}}`, used immediately for the CURRENT turn's live
    request (cc:/cx: consume this directly; every other dialect gets it
    indirectly once `rehydrate_messages` below expands the log's own
    path-only block back out).
  * a LOG block: the SAME image, minus the base64 bytes -- `image_path`
    (plus `media_type`/`width`/`height` for a caption/chip) is what
    actually reaches `~/.halo/sessions/.../<id>.jsonl`. `agent/loop.py`'s
    own user-turn construction is the ONE place that chooses between a
    real wire block and this log shape; this module just builds each half.

Rehydration (`rehydrate_image_block`/`rehydrate_messages`) is the
reconstruction half: given a path-only block, read the file back and
rebuild a real wire block -- called every time a request is (re)derived
from the log (agent/loop.py's `_derive_and_build`/`_run_compaction`), not
only on an explicit `--resume`/`/resume`, since the log never carries
anything BUT a path for an image turn to begin with. A missing file
degrades to a plain text caption instead of raising -- the turn still
runs, it just can no longer show the model that one image.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Optional

from halo_harness.tools.imageutil import sniff_dimensions, sniff_media_type

# Claude Code's own soft-resize threshold (tools/imageutil.MAX_IMAGE_DIM
# documents the same number for the OTHER image path, tool-result images --
# kept as a separate literal here rather than importing it, since this
# module's own downscale RULE is deliberately stricter: unconditional
# above this threshold, not just a last-resort before a HARD 8000px/5MB
# rejection).
SOFT_RESIZE_DIM = 1568
MAX_IMAGE_BYTES = 5 * 1024 * 1024

_EXT_FOR_MEDIA_TYPE = {"image/png": "png", "image/jpeg": "jpg", "image/gif": "gif", "image/webp": "webp"}


class ImageTooLarge(Exception):
    """Raised (never returned as a block) when an image is still over the
    5 MB cap after any possible downscale -- the caller shows ONE plain
    line and the turn proceeds without that attachment."""

    def __init__(self, num_bytes: int):
        self.num_bytes = num_bytes
        super().__init__(f"image is {num_bytes} bytes, over the 5 MB limit even after downscaling")


def media_type_for(path: Path, data: bytes) -> str:
    """The real media type from `data`'s own magic bytes, falling back to
    the extension when the sniffer doesn't recognize the format (a plain
    lossy WEBP bitstream, most likely) -- never raises."""
    from halo_harness.tools.imageutil import IMAGE_EXTENSIONS
    return sniff_media_type(data) or IMAGE_EXTENSIONS.get(path.suffix.lower()) or "image/png"


def _downscale_via_pillow(data: bytes) -> Optional[bytes]:
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        import io
        img = Image.open(io.BytesIO(data))
        img.load()
        width, height = img.size
        scale = SOFT_RESIZE_DIM / max(width, height)
        if scale >= 1.0:
            return None  # already small enough -- nothing to do
        img = img.resize((max(1, round(width * scale)), max(1, round(height * scale))))
        buf = io.BytesIO()
        img.convert("RGB" if img.mode not in ("RGB", "RGBA", "L", "LA", "P") else img.mode).save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return None


def downscale_and_cap(data: bytes, media_type: str) -> "tuple[bytes, str]":
    """Deliverable 2 ("Storage and limits"): Pillow importable and the long
    side exceeds `SOFT_RESIZE_DIM` -> downscaled, keeping aspect, and
    re-encoded PNG; without Pillow (or an image already small enough) the
    bytes pass through unchanged. Returns `(final_bytes, final_media_type)`
    -- raises `ImageTooLarge` when the result is STILL over `MAX_IMAGE_
    BYTES` (checked AFTER any downscale, so a huge screenshot gets a real
    chance to shrink under the cap before being refused)."""
    dims = sniff_dimensions(data)
    out, out_media_type = data, media_type
    if dims and max(dims) > SOFT_RESIZE_DIM:
        resized = _downscale_via_pillow(data)
        if resized is not None:
            out, out_media_type = resized, "image/png"
    if len(out) > MAX_IMAGE_BYTES:
        raise ImageTooLarge(len(out))
    return out, out_media_type


def next_attachment_path(attachments_dir: Path, media_type: str) -> Path:
    """`clip-<n>.<ext>` -- the first free index under `attachments_dir`
    (deliverable 2: `~/.halo/attachments/<session-id>/clip-<n>.png`)."""
    ext = _EXT_FOR_MEDIA_TYPE.get(media_type, "png")
    attachments_dir.mkdir(parents=True, exist_ok=True)
    existing = {p.name for p in attachments_dir.glob("clip-*")}
    n = 1
    while f"clip-{n}.{ext}" in existing:
        n += 1
    return attachments_dir / f"clip-{n}.{ext}"


def attachments_dir_for_session(session) -> Path:
    """`~/.halo/attachments/<session-id>` for a live `Session` (state dir
    via `config.paths`, so `BRIDGE_TEST_HOME` scopes it same as every other
    state-dir read) -- a session with no log yet (shouldn't happen for a
    real caller) falls back to an `_unscoped` bucket rather than raising."""
    from halo_harness.config.paths import bridge_home
    session_id = getattr(getattr(session, "log", None), "session_id", None) or "_unscoped"
    return bridge_home() / "attachments" / session_id


def _wire_block(data: bytes, media_type: str, *, image_path: str) -> dict:
    block = {"type": "image", "source": {"type": "base64", "media_type": media_type,
                                           "data": base64.b64encode(data).decode("ascii")},
             "image_path": image_path}
    dims = sniff_dimensions(data)
    if dims:
        block["width"], block["height"] = dims
    return block


def image_block_from_path(path: "str | Path") -> dict:
    """An EXISTING image file (a drag, `/paste <path>`, `--image <path>`,
    a stream-json `path` entry) -> a real wire block -- referenced in
    place, never copied/downscaled: this is the user's own file, not one
    Halo is managing in `~/.halo/attachments/`."""
    p = Path(path)
    data = p.read_bytes()
    media_type = media_type_for(p, data)
    return _wire_block(data, media_type, image_path=str(p))


def image_block_from_bytes(data: bytes, media_type: str, attachments_dir: Path) -> dict:
    """Bytes with no file of their own yet (a stream-json inline `base64`
    entry) -- downscaled/capped exactly like a clipboard read (deliverable
    2: these are equally ephemeral, so the same rule applies), written to
    the next free slot under `attachments_dir`, and turned into a real
    wire block. Raises `ImageTooLarge` the same way `downscale_and_cap`
    does; the caller decides how to surface that."""
    final_data, final_media_type = downscale_and_cap(data, media_type)
    dest = next_attachment_path(attachments_dir, final_media_type)
    dest.write_bytes(final_data)
    return _wire_block(final_data, final_media_type, image_path=str(dest))


def image_block_for_log(block: dict) -> dict:
    """The LOG-node shape for an image block this module built: `image_
    path` plus `media_type`/`width`/`height` for a caption, NEVER `source.
    data` -- see the module docstring's "model-visible means logged, but
    never the bytes" rule. A block with no `image_path` at all (never
    produced by this module; defensive only, e.g. a hand-built test
    fixture) is logged with whatever media_type it carries and no path,
    which `rehydrate_image_block` below simply leaves alone."""
    out: dict = {"type": "image"}
    if block.get("image_path"):
        out["image_path"] = block["image_path"]
    source = block.get("source") if isinstance(block.get("source"), dict) else {}
    media_type = source.get("media_type") or block.get("media_type")
    if media_type:
        out["media_type"] = media_type
    if "width" in block and "height" in block:
        out["width"], out["height"] = block["width"], block["height"]
    return out


def path_mention_text(block: dict) -> str:
    """The plain-text stand-in for an image block used whenever a real
    image block should never be sent at all (the no-vision gate, agent/
    loop.py) -- deliberately plain prose, no safety/refusal wording, just
    naming where the file is."""
    path = block.get("image_path")
    return f"[Image: {path}]" if path else "[Image attached]"


def rehydrate_image_block(block: dict) -> dict:
    """A path-only LOG-shaped image block -> a real wire block, read fresh
    from disk. A block that already carries real `source.data` (a tool-
    result image derived some OTHER way, never one this module logged)
    passes through unchanged. A missing/unreadable file degrades to a
    plain text note instead of raising -- `derive_request`'s caller still
    gets a request it can send, just without that one image."""
    if not isinstance(block, dict) or block.get("type") != "image":
        return block
    source = block.get("source")
    if isinstance(source, dict) and source.get("data"):
        return block
    path_str = block.get("image_path")
    if not path_str:
        return block
    try:
        data = Path(path_str).read_bytes()
    except OSError:
        return {"type": "text", "text": f"[Image: {path_str} (file no longer available)]"}
    media_type = block.get("media_type") or sniff_media_type(data) or "image/png"
    return {"type": "image", "source": {"type": "base64", "media_type": media_type,
                                          "data": base64.b64encode(data).decode("ascii")}}


def rehydrate_messages(messages: list) -> list:
    """Every image block across `messages` (Anthropic-shaped, agent/
    derive.py's own derived-transcript output) rehydrated in place. A
    message with nothing to rehydrate is returned BY REFERENCE, unchanged
    -- the common (no-image-anywhere-in-this-request) case stays a cheap
    no-op rather than a defensive full copy of the whole transcript on
    every single model call."""
    out = []
    for msg in messages:
        content = msg.get("content") if isinstance(msg, dict) else None
        if not isinstance(content, list):
            out.append(msg)
            continue
        needs_work = any(
            isinstance(b, dict) and b.get("type") == "image"
            and not (isinstance(b.get("source"), dict) and b["source"].get("data"))
            for b in content
        )
        if not needs_work:
            out.append(msg)
            continue
        new_msg = dict(msg)
        new_msg["content"] = [rehydrate_image_block(b) if isinstance(b, dict) else b for b in content]
        out.append(new_msg)
    return out
