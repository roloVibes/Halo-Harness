"""halo_harness.tui.copy_outcome -- the one line a copy leaves behind (3.1.6.0
R5, the owner on Kali 2026-10-20: "I can't copy the text then paste it
somewhere else").

`tui/app.py`'s `copy_to_clipboard` emits OSC 52 (when `clipboard.osc52_
trusted()`) and its worker calls `run_copy_fallback`, which pipes the text
into the platform's clipboard tool and returns the status line for EVERY
copy -- what landed, never silence:

  * "copied N characters via xclip" (wl-copy, xsel, clip.exe, pbcopy) when
    the tool ran clean;
  * on Linux with no tool on PATH: "no clipboard tool: sudo apt install
    xclip (or wl-clipboard on Wayland); sent OSC 52, which <terminal> may
    ignore; saved N characters to ~/.halo/clipboard.txt";
  * a tool that failed names itself and its error the same way;
  * over SSH (SSH_CONNECTION): OSC 52 is the only path to the local
    clipboard, and the file is named;
  * tmux dropping OSC 52, or nothing sent at all: "Copy FAILED -- ...".

Whenever no tool landed, the text is ALSO written to `<state>/clipboard.txt`
(0600, overwritten each time) so the words are never lost. Every input is a
seam (`env`, `platform`, the clipboard module's own functions read at call
time so a test's stub of them is honoured).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from halo_harness.tui import clipboard as cb

APT_LINE = "sudo apt install xclip (or wl-clipboard on Wayland)"
TMUX_FIX = "tmux set -g set-clipboard on"
FALLBACK_NAME = "clipboard.txt"
OSC52_MAYBE = "OSC 52 (if your terminal honours it)"

# $COLORTERM usually carries a capability, not a terminal's name.
_NOT_A_NAME = {"truecolor", "24bit", "yes", "true", "1"}

_TIMEOUTS = {"information": 4, "warning": 12, "error": 12}


def terminal_name(env: "Optional[dict]" = None) -> str:
    """The terminal's name from $TERM_PROGRAM, $TERMINAL or $COLORTERM (in
    that order, a path reduced to its last part), else a VTE/Konsole hint,
    else "your terminal"."""
    environ = env if env is not None else os.environ
    for key in ("TERM_PROGRAM", "TERMINAL", "COLORTERM"):
        value = (environ.get(key) or "").strip()
        if value and value.lower() not in _NOT_A_NAME:
            return os.path.basename(value) or value
    if environ.get("KONSOLE_VERSION"):
        return "Konsole"
    if environ.get("VTE_VERSION"):
        return "your VTE terminal (GNOME Terminal, xfce4-terminal)"
    return "your terminal"


def over_ssh(env: "Optional[dict]" = None) -> bool:
    environ = env if env is not None else os.environ
    return bool(environ.get("SSH_CONNECTION") or environ.get("SSH_CLIENT"))


def tool_name_for(platform: str) -> "Optional[str]":
    """The tool `copy_via_external_tool` pipes into on `platform`, or None
    on Linux when none of xclip / wl-copy / xsel is on PATH."""
    if platform == "win32":
        return "clip.exe"
    if platform == "darwin":
        return "pbcopy"
    found = cb.find_clipboard_tool()
    return found[0] if found else None


def fallback_path() -> Path:
    from halo_harness.config.paths import bridge_home
    return bridge_home() / FALLBACK_NAME


def display_path(path) -> str:
    """`path` with the home directory (config.paths.home()) written as `~`."""
    from halo_harness.config.paths import home
    try:
        rel = Path(path).resolve().relative_to(home().resolve())
        return os.path.join("~", str(rel))
    except (ValueError, OSError, RuntimeError):
        return str(path)


def save_fallback(text: str) -> "Optional[Path]":
    """Write `text` to `<state>/clipboard.txt` (0600, replaced whole);
    the path, or None when the write failed."""
    try:
        from halo_harness.privateio import write_private_atomic
        path = fallback_path()
        write_private_atomic(path, text)
        return path
    except Exception:
        return None


def _tool_clause(tool: "Optional[str]", error: str) -> str:
    if tool is None:
        return f"no clipboard tool: {APT_LINE}"
    first = (error or "").strip().splitlines()[0][:120] if (error or "").strip() else ""
    return f"{tool} failed ({first})" if first else f"{tool} failed"


def describe_outcome(n: int, *, tool: "Optional[str]", tool_ok: bool, tool_error: str = "",
                     osc52_sent: bool, platform: str, env: "Optional[dict]" = None,
                     saved: "Optional[Path]" = None,
                     tmux_mode: "Optional[str]" = None) -> "tuple[str, str]":
    """`(status line, notify severity)` for one copy of `n` characters."""
    if tool_ok:
        return f"copied {n} characters via {tool or 'the clipboard tool'}", "information"
    saved_txt = (f"; saved {n} characters to {display_path(saved)}" if saved is not None
                 else f"; could not write {FALLBACK_NAME} in the state folder")
    clause = _tool_clause(tool, tool_error)
    if tmux_mode is not None and tmux_mode not in ("on", "external"):
        return (f"Copy FAILED -- tmux is dropping OSC 52 (set-clipboard is {tmux_mode}). Fix once: "
                f"'{TMUX_FIX}', then detach and re-attach; {clause}{saved_txt}", "error")
    if not osc52_sent:
        return (f"Copy FAILED -- nothing landed: {clause}, and OSC 52 was not sent "
                f"(this console does not relay it){saved_txt}", "error")
    if platform not in ("win32", "darwin") and over_ssh(env):
        return (f"over SSH, OSC 52 is the only path to your local clipboard: sent {n} characters "
                f"via {OSC52_MAYBE}{saved_txt}", "warning")
    if platform not in ("win32", "darwin"):
        return f"{clause}; sent OSC 52, which {terminal_name(env)} may ignore{saved_txt}", "warning"
    return f"copied {n} characters via {OSC52_MAYBE}; {clause}{saved_txt}", "warning"


def run_copy_fallback(text: str, *, osc52_sent: bool, platform: "Optional[str]" = None,
                      env: "Optional[dict]" = None) -> "tuple[str, str]":
    """Pipe `text` into the platform's clipboard tool, save the fallback
    file when it did not land, and return `describe_outcome`'s line. Runs on
    a worker thread (the subprocess call can take a moment)."""
    plat = platform if platform is not None else cb._platform()
    ok = bool(cb.copy_via_external_tool(text))
    tool = tool_name_for(plat)
    error = "" if ok else cb.last_copy_error()
    saved = None if ok else save_fallback(text)
    tmux_mode = cb.tmux_clipboard_mode(env)
    return describe_outcome(len(text), tool=tool, tool_ok=ok, tool_error=error, osc52_sent=osc52_sent,
                            platform=plat, env=env, saved=saved, tmux_mode=tmux_mode)


def timeout_for(severity: str) -> float:
    """How long the status line stays: short for a landed copy, long enough
    to read (and act on) for a warning or a failure."""
    return float(_TIMEOUTS.get(severity, 6))
