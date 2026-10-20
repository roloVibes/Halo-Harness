"""halo_harness.tui.clipboard_doctor -- `halo doctor`'s clipboard row on Linux
(3.1.6.0 R5, the owner on Kali 2026-10-20: copying the draft did nothing).

One row that says, in order: which clipboard tool a copy pipes into
(`xclip` / `wl-copy` / `xsel`, or none), whether the display session that
tool needs is up (`WAYLAND_DISPLAY` / `DISPLAY`), and the OSC 52 note (the
escape every copy also sends, which QTerminal, xfce4-terminal and GNOME
Terminal ignore by default). A WARN carries its fix: `clipboard_doctor_
parts()` returns `(line, fix_cmd, see_ref)` and `doctor.py` appends it with
its own `_fix()`, like every other doctor warning.

win32 and darwin keep `clipboard.clipboard_doctor_line()`'s own rows; this
module is only the Linux half (and the tmux case, which stays first: tmux
dropping OSC 52 is the blocker whatever else is installed).
"""
from __future__ import annotations

import os
from typing import Optional

from halo_harness.tui import clipboard as cb

APT_XCLIP = "sudo apt install xclip"
APT_WAYLAND = "sudo apt install wl-clipboard"
TMUX_FIX = "tmux set -g set-clipboard on"
SEE_DOC = "docs/TROUBLESHOOTING.md (Copy does nothing on Linux)"
DEFAULT_IGNORERS = "QTerminal, xfce4-terminal and GNOME Terminal do by default"


def session_text(env: dict) -> str:
    """Which display session is up, named with the variable that says so."""
    wayland = env.get("WAYLAND_DISPLAY") or ""
    x11 = env.get("DISPLAY") or ""
    if wayland and x11:
        return f"Wayland session up (WAYLAND_DISPLAY={wayland}, DISPLAY={x11})"
    if wayland:
        return f"Wayland session up (WAYLAND_DISPLAY={wayland})"
    if x11:
        return f"X11 session up (DISPLAY={x11})"
    return "no X11 or Wayland session (DISPLAY and WAYLAND_DISPLAY unset)"


def apt_fix_for(env: dict) -> str:
    """xclip on X11 (and under XWayland); wl-clipboard on a Wayland-only session."""
    if env.get("WAYLAND_DISPLAY") and not env.get("DISPLAY"):
        return APT_WAYLAND
    return APT_XCLIP


def _fallback_file() -> str:
    from halo_harness.tui.copy_outcome import display_path, fallback_path
    try:
        return display_path(fallback_path())
    except Exception:
        return "~/.halo/clipboard.txt"


def linux_clipboard_parts(env: "Optional[dict]" = None) -> "tuple[str, Optional[str], Optional[str]]":
    """`(line, fix_cmd, see_ref)` for the Linux clipboard row. `env` (default
    `os.environ`) is the seam for every variable read here; the tool search
    itself is `clipboard.find_clipboard_tool()` (PATH)."""
    from halo_harness.tui.copy_outcome import over_ssh, terminal_name
    environ = env if env is not None else os.environ
    found = cb.find_clipboard_tool()
    tool = found[0] if found else None
    session = session_text(environ)
    terminal = terminal_name(environ)
    osc_note = f"OSC 52 is sent too, which {terminal} may ignore ({DEFAULT_IGNORERS})"
    tmux_mode = cb.tmux_clipboard_mode(environ)
    if tmux_mode is not None and tmux_mode not in ("on", "external"):
        tool_part = f"{tool} found" if tool else "no xclip/wl-copy/xsel on PATH"
        line = (f"[WARN] Clipboard backend: tmux drops OSC 52 here (set-clipboard={tmux_mode}; it needs "
                f"set-clipboard on, then detach and re-attach); {tool_part}, {session}")
        return line, TMUX_FIX, None
    saved = f"each copy that no tool lands is also saved to {_fallback_file()}"
    if tool is None:
        no_session = not (environ.get("DISPLAY") or environ.get("WAYLAND_DISPLAY"))
        where = ("; over SSH OSC 52 is the only path to your local clipboard" if over_ssh(environ)
                 else "; a tool also needs halo running inside the desktop session" if no_session
                 else "")
        line = (f"[WARN] Clipboard backend: no clipboard tool (xclip/wl-copy/xsel) on PATH, {session}{where} "
                f"-- copies ride OSC 52 only, which {terminal} may ignore ({DEFAULT_IGNORERS}); {saved}; "
                f"Ctrl+V has no tool to read with")
        return line, apt_fix_for(environ), None
    needs = cb.TOOL_SESSION_VAR.get(tool, "DISPLAY")
    if environ.get(needs):
        line = (f"[OK] Clipboard backend: {tool}, {session} -- write: OSC 52 when trusted + {tool} floor; "
                f"read: {tool}; selection copies narrow to the dragged range; {osc_note}")
        return line, None, None
    other_up = environ.get("DISPLAY") or environ.get("WAYLAND_DISPLAY")
    line = (f"[WARN] Clipboard backend: {tool} found, but {needs} is unset, so it has no clipboard to "
            f"write; {session} -- {osc_note}; {saved}")
    if other_up:
        return line, apt_fix_for(environ), None
    if over_ssh(environ):
        line += "; over SSH OSC 52 is the only path to your local clipboard"
    return line, None, SEE_DOC


def clipboard_doctor_parts(env: "Optional[dict]" = None, *,
                           platform: "Optional[str]" = None) -> "tuple[str, Optional[str], Optional[str]]":
    """Every platform's row as `(line, fix_cmd, see_ref)` for doctor.py:
    Linux from `linux_clipboard_parts`, win32/darwin from the long-standing
    `clipboard_doctor_line` (both always OK there, nothing to fix)."""
    plat = platform if platform is not None else cb._platform()
    if plat in ("win32", "darwin"):
        return cb.clipboard_doctor_line(env, platform=plat), None, None
    return linux_clipboard_parts(env)
