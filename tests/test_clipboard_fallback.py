"""tests.test_clipboard_fallback -- Halo 3.1.6.0 R5: a copy never fails
silently (tui/copy_outcome.py). Pure (no Textual app): every status line a
copy can leave, the <state>/clipboard.txt fallback (written when no tool
landed, 0600, overwritten each copy), and the Linux tool detection that
prefers the tool whose display session is up. The Linux paths run on any
build host through tests/helpers/fake_clip_env.py (fake tools on PATH, the
clipboard module's `_platform()` seam, scrubbed SSH/tmux/display vars).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.fake_clip_env import LinuxClipEnv
from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all

test, TESTS = new_registry()


def _describe(**kw):
    from halo_harness.tui.copy_outcome import describe_outcome
    base = dict(tool="xclip", tool_ok=False, tool_error="", osc52_sent=True, platform="linux", env={},
                saved=Path("state") / "clipboard.txt", tmux_mode=None)
    base.update(kw)
    return describe_outcome(12, **base)


@test
def test_every_outcome_line(ctx: Ctx):
    for tool, plat in (("xclip", "linux"), ("wl-copy", "linux"), ("xsel", "linux"),
                       ("clip.exe", "win32"), ("pbcopy", "darwin")):
        line, sev = _describe(tool=tool, tool_ok=True, platform=plat, saved=None)
        ctx.check(f"{tool} landed -> {line!r}", line == f"copied 12 characters via {tool}" and sev == "information")
    line, sev = _describe(tool=None, env={"TERM_PROGRAM": "QTerminal"})
    ctx.check(f"linux, no tool: the apt line and the terminal, got {line!r}",
              line.startswith("no clipboard tool: sudo apt install xclip (or wl-clipboard on Wayland); "
                              "sent OSC 52, which QTerminal may ignore; saved 12 characters to ")
              and line.endswith("clipboard.txt") and sev == "warning")
    line, _sev = _describe(tool_error="Error: Can't open display: (null)\nmore")
    ctx.check(f"a failing tool names itself and its first error line, got {line!r}",
              line.startswith("xclip failed (Error: Can't open display: (null)); sent OSC 52, which your "
                              "terminal may ignore; saved 12 characters to "))
    line, sev = _describe(tool=None, env={"SSH_CONNECTION": "203.0.113.2 5000 203.0.113.9 22"})
    ctx.check(f"over SSH: OSC 52 is the only path, the file is named, got {line!r}",
              line.startswith("over SSH, OSC 52 is the only path to your local clipboard: sent 12 characters "
                              "via OSC 52 (if your terminal honours it); saved 12 characters to ")
              and "clipboard.txt" in line and sev == "warning")
    line, sev = _describe(tmux_mode="off", env={"SSH_CONNECTION": "x"})
    ctx.check(f"tmux dropping OSC 52 wins, with its fix, got {line!r}",
              line.startswith("Copy FAILED -- tmux is dropping OSC 52") and "tmux set -g set-clipboard on" in line
              and "clipboard.txt" in line and sev == "error")
    line, sev = _describe(tool="clip.exe", platform="win32", osc52_sent=False)
    ctx.check(f"nothing sent and the tool failed: a FAILED line, got {line!r}",
              line.startswith("Copy FAILED -- nothing landed: clip.exe failed") and sev == "error")
    line, sev = _describe(tool="clip.exe", platform="win32")
    ctx.check(f"win32, OSC 52 sent, clip.exe failed, got {line!r}",
              line.startswith("copied 12 characters via OSC 52 (if your terminal honours it); clip.exe failed")
              and sev == "warning")
    line, _sev = _describe(tool="pbcopy", platform="darwin", saved=None)
    ctx.check(f"a fallback file that could not be written says so, got {line!r}",
              line.endswith("could not write clipboard.txt in the state folder"))


@test
def test_terminal_name_order_and_capability_values(ctx: Ctx):
    from halo_harness.tui.copy_outcome import terminal_name
    ctx.check("TERM_PROGRAM first",
              terminal_name({"TERM_PROGRAM": "WezTerm", "TERMINAL": "qterminal"}) == "WezTerm")
    ctx.check("TERMINAL as a path reads as its name", terminal_name({"TERMINAL": "/usr/bin/qterminal"}) == "qterminal")
    ctx.check("COLORTERM=truecolor is not a name",
              terminal_name({"COLORTERM": "truecolor"}) == "your terminal")
    ctx.check("an old xfce4-terminal sets COLORTERM to its name",
              terminal_name({"COLORTERM": "xfce4-terminal"}) == "xfce4-terminal")
    ctx.check("VTE hint", "VTE" in terminal_name({"COLORTERM": "truecolor", "VTE_VERSION": "7600"}))


@test
def test_no_tool_on_path_saves_the_file_0600_and_overwrites_it(ctx: Ctx):
    from halo_harness.tui.copy_outcome import run_copy_fallback
    with LinuxClipEnv(env={"DISPLAY": ":0"}) as clip:
        line, sev = run_copy_fallback("first copy", osc52_sent=True)
        saved = clip.state_dir / "clipboard.txt"
        ctx.check(f"the file holds the text, line {line!r}",
                  saved.exists() and saved.read_text(encoding="utf-8") == "first copy")
        ctx.check("the line names the apt install and the file",
                  line.startswith("no clipboard tool: sudo apt install xclip") and "clipboard.txt" in line
                  and sev == "warning")
        if sys.platform != "win32":
            ctx.check(f"0600, got {oct(saved.stat().st_mode & 0o777)}", saved.stat().st_mode & 0o777 == 0o600)
        run_copy_fallback("second", osc52_sent=True)
        ctx.check("each copy overwrites it", saved.read_text(encoding="utf-8") == "second")


@test
def test_a_fake_xclip_on_path_lands_and_no_file_is_written(ctx: Ctx):
    from halo_harness.tui.copy_outcome import run_copy_fallback
    with LinuxClipEnv(tools=("xclip",), env={"DISPLAY": ":0"}) as clip:
        if clip.probe_error:  # a host where the fake cannot run (the GitHub Windows runner) skips with the reason
            raise SkipTest(f"the fake clipboard tool cannot run on this host: {clip.probe_error}")
        line, sev = run_copy_fallback("café — draft", osc52_sent=True)
        ctx.check(f"the fake xclip got the UTF-8 text, got {clip.sink('xclip')!r}", clip.sink("xclip") == "café — draft")
        ctx.check(f"copied N characters via xclip, got {line!r}", line == "copied 12 characters via xclip" and sev == "information")
        ctx.check("no fallback file", not (clip.state_dir / "clipboard.txt").exists())


@test
def test_a_failing_xclip_names_its_error_and_saves_the_file(ctx: Ctx):
    from halo_harness.tui.copy_outcome import run_copy_fallback
    with LinuxClipEnv(failing=("xclip",)) as clip:
        line, _sev = run_copy_fallback("no display", osc52_sent=True)
        ctx.check(f"the error reaches the line, got {line!r}",
                  line.startswith("xclip failed (Error: Can't open display: (null))"))
        ctx.check("the words are saved", (clip.state_dir / "clipboard.txt").read_text(encoding="utf-8") == "no display")


@test
def test_over_ssh_the_line_says_osc52_is_the_only_path(ctx: Ctx):
    from halo_harness.tui.copy_outcome import run_copy_fallback
    with LinuxClipEnv(env={"SSH_CONNECTION": "203.0.113.28 51000 203.0.113.48 22"}) as clip:
        line, _sev = run_copy_fallback("ssh words", osc52_sent=True)
        ctx.check(f"OSC 52 is the only path and the file is named, got {line!r}",
                  line.startswith("over SSH, OSC 52 is the only path to your local clipboard") and "clipboard.txt" in line)
        ctx.check("saved", (clip.state_dir / "clipboard.txt").read_text(encoding="utf-8") == "ssh words")


@test
def test_detection_prefers_the_tool_whose_session_is_up(ctx: Ctx):
    import halo_harness.tui.clipboard as cb
    with LinuxClipEnv(tools=("wl-copy", "xclip"), env={"DISPLAY": ":0"}):
        found = cb.find_clipboard_tool()
        ctx.check(f"X11 session: xclip over wl-copy, got {found}", found is not None and found[0] == "xclip")
        ctx.check("argv[0] is the resolved path", found is not None and Path(found[1][0]).parent.name == "bin")
    with LinuxClipEnv(tools=("wl-copy", "xclip"), env={"WAYLAND_DISPLAY": "wayland-0"}):
        ctx.check("Wayland session: wl-copy", (cb.find_clipboard_tool() or ("",))[0] == "wl-copy")
    with LinuxClipEnv(tools=("xsel",)):
        ctx.check("no session up: PATH order stands", (cb.find_clipboard_tool() or ("",))[0] == "xsel")
    with LinuxClipEnv():
        ctx.check("nothing on PATH: None", cb.find_clipboard_tool() is None)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
