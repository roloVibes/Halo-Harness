"""tests.test_doctor_clipboard_row -- Halo 3.1.6.0 R5: `halo doctor`'s
clipboard row on Linux (tui/clipboard_doctor.py): which tool it found (or
none, with the apt line), whether a Wayland or X11 session is up, the OSC 52
note, and the row's fix appended the way doctor.py appends every other one
(`_fix`). Runs on any build host through tests/helpers/fake_clip_env.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.fake_clip_env import LinuxClipEnv
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()


def _row() -> "tuple[str, str]":
    """(rendered doctor line, the bare line) on the faked Linux host."""
    from halo_harness.doctor import _fix
    from halo_harness.tui.clipboard_doctor import clipboard_doctor_parts
    line, fix, see = clipboard_doctor_parts()
    return _fix(line, cmd=fix, see=see), line


@test
def test_tool_found_on_x11_is_ok_and_names_everything(ctx: Ctx):
    with LinuxClipEnv(tools=("xclip",), env={"DISPLAY": ":0", "TERMINAL": "qterminal"}):
        rendered, _line = _row()
    ctx.check(f"OK, names xclip and the X11 session, got {rendered!r}",
              rendered.startswith("[OK] Clipboard backend: xclip, X11 session up (DISPLAY=:0)"))
    ctx.check("states the write/read verdict", "xclip floor" in rendered and "read: xclip" in rendered)
    ctx.check("the OSC 52 note names the terminal",
              "OSC 52 is sent too, which qterminal may ignore" in rendered)
    ctx.check("an OK row carries no fix", "-> fix:" not in rendered and "-> see:" not in rendered)


@test
def test_no_tool_is_a_warn_ending_with_the_apt_line(ctx: Ctx):
    with LinuxClipEnv(env={"DISPLAY": ":1"}):
        rendered, line = _row()
    ctx.check(f"WARN naming none and the session, got {rendered!r}",
              rendered.startswith("[WARN] Clipboard backend: no clipboard tool (xclip/wl-copy/xsel) on PATH, "
                                  "X11 session up (DISPLAY=:1)"))
    ctx.check("the OSC 52 note and the fallback file are named",
              "copies ride OSC 52 only" in line and "clipboard.txt" in line)
    ctx.check(f"ends with its fix, got {rendered[-40:]!r}", rendered.endswith(" -> fix: sudo apt install xclip"))


@test
def test_wayland_only_session_asks_for_wl_clipboard(ctx: Ctx):
    with LinuxClipEnv(env={"WAYLAND_DISPLAY": "wayland-0"}):
        rendered, _line = _row()
    ctx.check(f"names the Wayland session, got {rendered!r}", "Wayland session up (WAYLAND_DISPLAY=wayland-0)" in rendered)
    ctx.check("fix is wl-clipboard", rendered.endswith(" -> fix: sudo apt install wl-clipboard"))
    with LinuxClipEnv(tools=("wl-copy",), env={"WAYLAND_DISPLAY": "wayland-0"}):
        ok, _ = _row()
    ctx.check(f"wl-copy on Wayland is OK, got {ok!r}", ok.startswith("[OK] Clipboard backend: wl-copy, Wayland session up"))


@test
def test_a_tool_without_its_session_warns(ctx: Ctx):
    with LinuxClipEnv(tools=("xclip",), env={"SSH_CONNECTION": "1.2.3.4 5 6.7.8.9 22"}):
        rendered, _line = _row()
    ctx.check(f"xclip found but DISPLAY unset is a WARN, got {rendered!r}",
              rendered.startswith("[WARN] Clipboard backend: xclip found, but DISPLAY is unset, so it has no clipboard "
                                  "to write; no X11 or Wayland session"))
    ctx.check("over SSH it says OSC 52 is the only path, and points at the docs",
              "over SSH OSC 52 is the only path" in rendered and "-> see: docs/TROUBLESHOOTING.md" in rendered)
    with LinuxClipEnv(tools=("wl-copy",), env={"DISPLAY": ":0"}):
        rendered2, _ = _row()
    ctx.check(f"wl-copy on an X11 desktop: install xclip, got {rendered2!r}",
              "wl-copy found, but WAYLAND_DISPLAY is unset" in rendered2
              and rendered2.endswith(" -> fix: sudo apt install xclip"))


@test
def test_tmux_dropping_osc52_names_the_tmux_fix(ctx: Ctx):
    import halo_harness.tui.clipboard as cb
    with LinuxClipEnv(tools=("xclip",), env={"DISPLAY": ":0", "TMUX": "/tmp/tmux-1000/default,1,0"}):
        cb._TMUX_MODE_CACHE["/tmp/tmux-1000/default,1,0"] = "off"
        rendered, _line = _row()
    ctx.check(f"tmux first, with its own fix (not the apt line), got {rendered!r}",
              rendered.startswith("[WARN] Clipboard backend: tmux drops OSC 52 here")
              and rendered.endswith(" -> fix: tmux set -g set-clipboard on"))


@test
def test_win32_and_darwin_rows_are_unchanged(ctx: Ctx):
    from halo_harness.tui.clipboard_doctor import clipboard_doctor_parts
    win, fix, see = clipboard_doctor_parts({}, platform="win32")
    ctx.check(f"win32 row, nothing to fix, got {win!r}", win.startswith("[OK] Clipboard backend: win32") and not fix and not see)
    mac, _f, _s = clipboard_doctor_parts({}, platform="darwin")
    ctx.check("darwin row", mac.startswith("[OK] Clipboard backend: darwin") and "pbcopy" in mac)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
