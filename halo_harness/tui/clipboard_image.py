"""halo_harness.tui.clipboard_image -- Halo 2.0.3.1: reads an IMAGE off the
real OS clipboard (the read-side counterpart to tui/clipboard.py's OSC-52
COPY path, same module-split reasoning: `tui/clipboard.py`'s own docstring
covers the TEXT read/write directions, this one is images only). Every
platform reader is a subprocess under `timeout_s`, no new hard dependency
(Pillow's own `ImageGrab.grabclipboard()` is tried too, but only ever as
one more backend, never a requirement). `backend`, when given, is the
WHOLE read -- no platform reader or Pillow fallback ever runs alongside it,
which is what makes it a real test seam (a test passes one and never
touches a real clipboard, subprocess, or Pillow import at all). The reader
never runs on the UI thread -- `tui/app.py`/`tui/slash.py` call it from a
`thread=True` worker, same convention every other subprocess-backed slash
command here already uses.

macOS/Linux/Pillow readers live in the sibling `clipboard_image_posix`
module (split purely to keep each file under the house 250-line write
cap); this module holds Windows/WSL plus the shared storage/dispatch.

Deliverable 2 ("storage and limits") lives here too: Pillow importable and
the long side over 1568px -> downscaled, re-encoded PNG; without Pillow,
or already small enough, the bytes pass through as read. Still over 5MB
after that -> `agent.image_attach.ImageTooLarge`, never a silently-dropped
attachment.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from halo_harness.agent.image_attach import ImageTooLarge, downscale_and_cap, next_attachment_path
from halo_harness.config.paths import bridge_home
from halo_harness.tools.imageutil import sniff_dimensions, sniff_media_type
from halo_harness.tui.clipboard_image_posix import (
    linux_argv_table, linux_read_bytes, macos_primary_argv, macos_fallback_argv,
    macos_read_bytes, parse_applescript_data, pillow_grabclipboard_bytes,
)

_SUBPROCESS_ERRORS = (OSError, subprocess.SubprocessError, ValueError)

# Re-exported so a caller/test can do `from halo_harness.tui.clipboard_image
# import ImageTooLarge` without reaching into agent.image_attach directly.
__all__ = ["ClipboardImage", "ImageTooLarge", "read_clipboard_image",
           "windows_primary_argv", "windows_fallback_argv", "wsl_save_argv", "wsl_path_convert_argv",
           "is_wsl", "macos_primary_argv", "macos_fallback_argv", "parse_applescript_data",
           "linux_argv_table"]


@dataclass
class ClipboardImage:
    path: Path
    width: Optional[int]
    height: Optional[int]
    media_type: str
    bytes: int


def _default_inbox_dir() -> Path:
    """Used only when a caller doesn't know (or care about) a session id
    yet -- `tui/app.py`/`tui/slash.py`'s real callers always pass `dest_dir=
    agent.image_attach.attachments_dir_for_session(session)` instead, the
    documented `~/.halo/attachments/<session-id>/` location."""
    return bridge_home() / "attachments" / "_inbox"


# ---- Windows (and the WSL variant, via powershell.exe) --------------------

def windows_primary_argv(tmp_path: str) -> list:
    script = ("Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing; "
              "$i = [Windows.Forms.Clipboard]::GetImage(); "
              f"if ($i) {{ $i.Save('{tmp_path}', [System.Drawing.Imaging.ImageFormat]::Png); 'ok' }}")
    return ["powershell", "-NoProfile", "-Command", script]


def windows_fallback_argv(tmp_path: str) -> list:
    script = ("Add-Type -AssemblyName System.Drawing; $i = Get-Clipboard -Format Image; "
              f"if ($i) {{ $i.Save('{tmp_path}', [System.Drawing.Imaging.ImageFormat]::Png); 'ok' }}")
    return ["powershell", "-NoProfile", "-Command", script]


def wsl_save_argv(win_tmp_path: str) -> list:
    """Same script as `windows_primary_argv`, run through `powershell.exe`
    (the Windows-side binary reachable from WSL) saving to a WINDOWS path."""
    return ["powershell.exe"] + windows_primary_argv(win_tmp_path)[1:]


def wsl_path_convert_argv(win_path: str) -> list:
    return ["wslpath", "-u", win_path]


def is_wsl(proc_version_text: str) -> bool:
    return "microsoft" in (proc_version_text or "").lower()


def _running_under_wsl() -> bool:
    try:
        return is_wsl(Path("/proc/version").read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return False


def _save_then_read(argv: list, tmp_path: Path, *, run: Callable, timeout_s: float) -> Optional[bytes]:
    try:
        proc = run(argv, capture_output=True, text=True, timeout=timeout_s)
    except _SUBPROCESS_ERRORS:
        return None
    try:
        if "ok" in (proc.stdout or "") and tmp_path.exists():
            return tmp_path.read_bytes()
    except OSError:
        return None
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass
    return None


def _windows_read_bytes(*, run: Callable, timeout_s: float) -> Optional[bytes]:
    tmp_dir = Path(tempfile.gettempdir())
    tmp1 = tmp_dir / f"halo-clip-{uuid.uuid4().hex}.png"
    data = _save_then_read(windows_primary_argv(str(tmp1)), tmp1, run=run, timeout_s=timeout_s)
    if data:
        return data
    tmp2 = tmp_dir / f"halo-clip-{uuid.uuid4().hex}.png"
    return _save_then_read(windows_fallback_argv(str(tmp2)), tmp2, run=run, timeout_s=timeout_s)


def _wsl_read_bytes(*, run: Callable, timeout_s: float) -> Optional[bytes]:
    win_tmp = f"C:\\Windows\\Temp\\halo-clip-{uuid.uuid4().hex}.png"
    try:
        proc = run(wsl_save_argv(win_tmp), capture_output=True, text=True, timeout=timeout_s)
        if "ok" not in (proc.stdout or ""):
            return None
        conv = run(wsl_path_convert_argv(win_tmp), capture_output=True, text=True, timeout=timeout_s)
        wsl_path = (conv.stdout or "").strip()
        if not wsl_path:
            return None
        data = Path(wsl_path).read_bytes()
        try:
            Path(wsl_path).unlink()
        except OSError:
            pass
        return data
    except (_SUBPROCESS_ERRORS, OSError):
        return None


# ---- the public entry point --------------------------------------------

def read_clipboard_image(backend: Optional[Callable] = None, timeout_s: float = 2.0, *,
                          dest_dir: Optional[Path] = None, platform: Optional[str] = None,
                          run: Optional[Callable] = None) -> Optional[ClipboardImage]:
    """`None` for "nothing usable on the clipboard right now" (no tool
    installed, an empty clipboard, every reader failed/timed out) -- never
    raises for that case. Raises `ImageTooLarge` when a real image WAS
    found but is still over the 5 MB cap after downscaling (deliverable
    2) -- a distinct, catchable case so the caller can show a specific
    line instead of the generic "no image" one. `backend` bypasses EVERY
    platform reader and Pillow entirely when given (even a `None` return)
    -- the hermetic test seam."""
    if backend is not None:
        try:
            data = backend()
        except Exception:
            data = None
    else:
        plat = platform if platform is not None else sys.platform
        runner = run if run is not None else subprocess.run
        try:
            if plat == "win32":
                data = _windows_read_bytes(run=runner, timeout_s=timeout_s)
            elif plat == "darwin":
                data = macos_read_bytes(run=runner, timeout_s=timeout_s)
            elif _running_under_wsl():
                data = _wsl_read_bytes(run=runner, timeout_s=timeout_s)
            else:
                data = linux_read_bytes(run=runner, timeout_s=timeout_s)
        except Exception:
            data = None
        if not data:
            data = pillow_grabclipboard_bytes()
    if not data:
        return None

    media_type = sniff_media_type(data) or "image/png"
    final_data, final_media_type = downscale_and_cap(data, media_type)  # may raise ImageTooLarge
    dims = sniff_dimensions(final_data)
    width, height = dims if dims else (None, None)
    dest = next_attachment_path(dest_dir if dest_dir is not None else _default_inbox_dir(), final_media_type)
    dest.write_bytes(final_data)
    return ClipboardImage(path=dest, width=width, height=height, media_type=final_media_type,
                           bytes=len(final_data))
