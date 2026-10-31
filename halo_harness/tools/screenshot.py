"""halo_harness.tools.screenshot -- Halo 3.3.6.0 R6: the built-in `Screenshot` tool (rolo: "Does halo have the
ability to take screenshots and have models visually see them?").

    Screenshot {target: screen | window | region, title?, rect?: [x, y, w, h], display?}

One capture of this machine's display (tools/screenshot_capture.py: PowerShell's System.Drawing on Windows,
`screencapture -x` on the Mac, grim / spectacle / gnome-screenshot / scrot / import on Linux), saved as
`shot-<n>.png` in the session's images folder (`~/.halo/attachments/<session-id>/`, agent/image_attach.py's).
A model that sees gets the image block (with one text line naming the file); one that cannot gets
{path, width, height, note: "<model> cannot see images: the file is at <path>"} and the three ways on from the
eyes offer (agent/eyes_turn.tool_lines). Read-only: it writes only into Halo's own attachments folder.
`capture_for(session_id, target, ...)` is the same capture for `/screenshot` and Studio's button.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Optional

from halo_harness.tools.base import Tool, ToolContext, ToolResult


def images_folder(session_id: Optional[str]) -> Path:
    from halo_harness.config.paths import bridge_home
    return bridge_home() / "attachments" / (session_id or "_unscoped")


def capture_for(session_id: Optional[str], target: str = "screen", *, title=None, rect=None, display=None) -> dict:
    """One capture into that session's images folder (screenshot_capture.capture's answer)."""
    from halo_harness.tools import screenshot_capture as C
    return C.capture(target, title=title, rect=rect, display=display, dest=C.next_shot_path(images_folder(session_id)))


def parse_args(text: str) -> dict:
    """`/screenshot` words -> the tool's input: "" -> screen; `window <title>`; `region x,y,w,h`; `display <n>`."""
    words = (text or "").strip()
    head, _, rest = words.partition(" ")
    head = head.lower()
    if head == "window":
        return {"target": "window", "title": rest.strip().strip("\"'")}
    if head == "region":
        return {"target": "region", **({"rect": rest.strip()} if rest.strip() else {})}
    if head == "display":
        return {"target": "screen", "display": rest.strip()}
    return {"target": "screen"}


class ScreenshotTool(Tool):
    name: str = "Screenshot"
    # kept short: every local model's prompt carries it (3.3.6.0 R6); the result says the path and the size
    description: str = "Screenshot the screen, a window (title) or a region (rect: x, y, w, h)."
    input_schema: dict = {"type": "object", "properties": {
        "target": {"type": "string", "enum": ["screen", "window", "region"]}, "title": {"type": "string"},
        "rect": {"type": "array", "items": {"type": "integer"}}, "display": {"type": "string"}}}
    is_read_only: bool = True
    is_destructive: bool = False
    result_cap: Optional[int] = None

    def summary(self, input: dict) -> str:
        t = (input or {}).get("target") or "screen"
        what = (input or {}).get("title") if t == "window" else (input or {}).get("rect") if t == "region" else ""
        return f"Screenshot({t}{': ' + str(what) if what else ''})"

    def permission_content(self, input: dict) -> str:
        return str((input or {}).get("target") or "screen")

    def run(self, input: dict, ctx: ToolContext) -> ToolResult:
        inp = input if isinstance(input, dict) else {}
        sid = Path(ctx.session_dir).name if ctx.session_dir else None
        got = capture_for(sid, str(inp.get("target") or "screen"), title=inp.get("title"), rect=inp.get("rect"),
                          display=inp.get("display"))
        if not got.get("ok"):
            return ToolResult(got.get("say") or "the screenshot did not happen", is_error=True)
        path, w, h = got["path"], got.get("width"), got.get("height")
        head = f"Screenshot saved at {path} ({w} x {h}, {got.get('bytes', 0) // 1024} KiB, {got.get('tool')})"
        if ctx.vision:
            data = Path(path).read_bytes()
            block = {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                                 "data": base64.b64encode(data).decode("ascii")}}
            return ToolResult([{"type": "text", "text": head}, block])
        session = getattr(getattr(ctx, "agent_runtime", None), "parent", None)
        lines = _note_lines(session, ctx.model_ref, path)
        body = {"path": path, "width": w, "height": h, "note": lines[0]}
        return ToolResult(json.dumps(body, ensure_ascii=False) + "\n" + "\n".join(lines[1:]))


def _note_lines(session, model_ref: Optional[str], path: str) -> list:
    if session is not None:
        try:
            from halo_harness.agent.eyes_turn import tool_lines
            return tool_lines(session, path)
        except Exception:
            pass
    return [f"{model_ref or 'this model'} cannot see images: the file is at {path}"]
