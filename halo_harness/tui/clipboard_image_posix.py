"""halo_harness.tui.clipboard_image_posix -- the macOS/Linux/Pillow readers
for `tui/clipboard_image.py`'s own `read_clipboard_image` (split into its
own module purely to keep each file under the house 250-line write cap;
`clipboard_image.py`'s module docstring covers the design, this one just
holds the platform-specific argv/parsing for every OS that isn't Windows/
WSL). Same "no new hard dependency, each a subprocess under the timeout"
contract.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Callable, Optional

_SUBPROCESS_ERRORS = (OSError, subprocess.SubprocessError, ValueError)

_APPLESCRIPT_DATA_RE = re.compile(r"\xabdata (\w{4})([0-9a-fA-F]+)\xbb")


def macos_primary_argv() -> list:
    return ["osascript", "-e", "the clipboard as \xabclass PNGf\xbb"]


def macos_fallback_argv(tmp_path: str) -> list:
    return ["pngpaste", tmp_path]


def parse_applescript_data(stdout: str) -> Optional[bytes]:
    """`osascript`'s own `«data PNGf89504e47...»` text literal -> raw
    bytes -- AppleScript's `as «class PNGf»` coercion has no "write
    straight to a file" form, so the PNG bytes always come back hex-
    encoded in this wrapper on stdout."""
    m = _APPLESCRIPT_DATA_RE.search(stdout or "")
    if not m:
        return None
    try:
        return bytes.fromhex(m.group(2))
    except ValueError:
        return None


def macos_read_bytes(*, run: Callable, timeout_s: float) -> Optional[bytes]:
    try:
        proc = run(macos_primary_argv(), capture_output=True, text=True, timeout=timeout_s)
        data = parse_applescript_data(proc.stdout)
        if data:
            return data
    except _SUBPROCESS_ERRORS:
        pass
    if not shutil.which("pngpaste"):
        return None
    tmp_path = Path(tempfile.gettempdir()) / f"halo-clip-{uuid.uuid4().hex}.png"
    try:
        run(macos_fallback_argv(str(tmp_path)), capture_output=True, timeout=timeout_s)
        if tmp_path.exists():
            return tmp_path.read_bytes()
    except (_SUBPROCESS_ERRORS, OSError):
        pass
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass
    return None


def linux_argv_table() -> list:
    """`(tool_name, argv)` tried in order -- the first one actually on
    PATH is used; `xsel` carries no MIME-type selector of its own (same
    "last try" the brief names it) so its argv is identical to the plain-
    text read `tui/clipboard.py` already uses."""
    return [
        ("wl-paste", ["wl-paste", "--type", "image/png"]),
        ("xclip", ["xclip", "-selection", "clipboard", "-t", "image/png", "-o"]),
        ("xsel", ["xsel", "--clipboard", "--output"]),
    ]


def linux_read_bytes(*, run: Callable, timeout_s: float, which: Callable = shutil.which) -> Optional[bytes]:
    for _name, argv in linux_argv_table():
        if not which(argv[0]):
            continue
        try:
            proc = run(argv, capture_output=True, timeout=timeout_s)
            if proc.returncode == 0 and proc.stdout:
                return proc.stdout
        except _SUBPROCESS_ERRORS:
            continue
    return None


def pillow_grabclipboard_bytes() -> Optional[bytes]:
    try:
        from PIL import ImageGrab
    except ImportError:
        return None
    try:
        img = ImageGrab.grabclipboard()
        if img is None or not hasattr(img, "save"):
            return None  # grabclipboard() can also return a list of file paths -- not handled here
        import io
        buf = io.BytesIO()
        img.convert("RGB" if img.mode not in ("RGB", "RGBA", "L", "LA", "P") else img.mode).save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return None
