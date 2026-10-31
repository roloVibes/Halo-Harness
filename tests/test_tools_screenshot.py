"""tests.test_tools_screenshot -- Halo 3.3.6.0 R6: the Screenshot tool (halo_harness/tools/screenshot.py) and its
capture (tools/screenshot_capture.py), with the capture seam (`RUNNER`) writing a fixture PNG -- never a real
capture:

1. the command per OS: Windows (PowerShell System.Drawing, the window by title through GetWindowRect, a region,
   a display), the Mac (`screencapture -x`, `-R`, `-D`, a window's bounds from System Events then `-R`), Linux
   (grim / grim + slurp, scrot, import, spectacle, gnome-screenshot -- the first present; a window by title
   through xdotool on X11, and the line on Wayland);
2. the window-not-found line (Windows NOTFOUND, xdotool finding none), the no-display line (SSH, no DISPLAY),
   no tool at all, a bad rect;
3. the PNG lands as shot-<n>.png in the session's images folder, read back with its size;
4. the result: the image block for a model that sees, {path, width, height, note} plus the ways on for one that
   cannot; registered beside Media, read-only, found by ToolSearch, in the media capability;
5. `/screenshot` words -> the tool's input.
Run: python -m tests.test_tools_screenshot
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "vision" / "shot.png"


class Seam:
    """RUNNER replaced: every argv recorded; the fixture copied to the destination unless told otherwise."""

    def __init__(self, answers=None):
        from halo_harness.tools import screenshot_capture as C
        self.C, self.calls, self.answers = C, [], list(answers or [])

    def __enter__(self):
        self.saved = self.C.RUNNER
        self.C.RUNNER = self.run
        return self

    def __exit__(self, *exc):
        self.C.RUNNER = self.saved

    def run(self, argv, *, dest, timeout):
        self.calls.append(list(argv))
        rc, out = self.answers.pop(0) if self.answers else (0, "OK 4 3")
        if rc == 0 and out != "no-file":
            shutil.copyfile(FIXTURE, dest)
        return rc, out, ""


def _which(*present):
    return lambda name: f"/usr/bin/{name}" if name in present else None


def _dest() -> Path:
    return Path(tempfile.mkdtemp(prefix="ey-shot-")) / "shot-1.png"


@test
def test_the_command_per_os(ctx: Ctx):
    from halo_harness.tools.screenshot_capture import plan
    d = _dest()
    w = plan("window", title="Ableton Live", dest=d, platform="win32")
    script = w["argv"][-1]
    ctx.check("Windows: PowerShell System.Drawing CopyFromScreen", w["argv"][0] == "powershell.exe" and "CopyFromScreen" in script
              and "System.Drawing" in script)
    ctx.check("Windows: the window by title through GetWindowRect", "GetWindowRect" in script and "*$title*" in script
              and "'Ableton Live'" in script)
    ctx.check("Windows: a quote in a title is doubled", "'it''s'" in plan("window", title="it's", dest=d, platform="win32")["argv"][-1])
    ctx.check("Windows: a region", "'10,20,300,200'" in plan("region", rect=[10, 20, 300, 200], dest=d, platform="win32")["argv"][-1])
    ctx.check("Windows: a display", "AllScreens" in plan("screen", display="2", dest=d, platform="win32")["argv"][-1])
    mac = plan("screen", dest=d, platform="darwin")
    ctx.check(f"Mac: screencapture -x, got {mac['argv']}", mac["argv"] == ["screencapture", "-x", str(d)])
    ctx.check("Mac: -R a region", plan("region", rect="5,6,70,80", dest=d, platform="darwin")["argv"][:4] == ["screencapture", "-x", "-R", "5,6,70,80"])
    ctx.check("Mac: -D a display", plan("screen", display=2, dest=d, platform="darwin")["argv"][:4] == ["screencapture", "-x", "-D", "2"])
    mw = plan("window", title="Safari", dest=d, platform="darwin")
    ctx.check("Mac: a window's bounds from System Events first", mw["argv"][0] == "osascript" and mw.get("then") == "mac-window")
    x11 = {"DISPLAY": ":0"}
    way = {"WAYLAND_DISPLAY": "wayland-0"}
    g = plan("screen", dest=d, platform="linux", env=way, which=_which("grim", "slurp", "scrot"))
    ctx.check(f"Linux: grim first, got {g['argv']}", g["argv"] == ["grim", str(d)] and g["tool"] == "grim")
    gr = plan("region", dest=d, platform="linux", env=way, which=_which("grim", "slurp"))
    ctx.check(f"Linux: grim + slurp for a region without a rect, got {gr['argv']}", gr["tool"] == "grim + slurp" and "slurp" in gr["argv"][-1])
    ctx.check("Linux: grim -g a rect", plan("region", rect=[1, 2, 30, 40], dest=d, platform="linux", env=way,
                                           which=_which("grim"))["argv"][:3] == ["grim", "-g", "1,2 30x40"])
    sc = plan("region", rect=[1, 2, 30, 40], dest=d, platform="linux", env=x11, which=_which("scrot", "import"))
    ctx.check(f"Linux: scrot -a, got {sc['argv']}", sc["argv"] == ["scrot", "-o", "-a", "1,2,30,40", str(d)])
    im = plan("region", rect=[1, 2, 30, 40], dest=d, platform="linux", env=x11, which=_which("import"))
    ctx.check(f"Linux: import -crop, got {im['argv']}", im["argv"] == ["import", "-window", "root", "-crop", "30x40+1+2", str(d)])
    sp = plan("screen", dest=d, platform="linux", env=x11, which=_which("spectacle"))
    ctx.check(f"Linux: spectacle, got {sp['argv']}", sp["argv"][:5] == ["spectacle", "-b", "-n", "-o", str(d)])
    gn = plan("screen", dest=d, platform="linux", env=x11, which=_which("gnome-screenshot"))
    ctx.check(f"Linux: gnome-screenshot, got {gn['argv']}", gn["argv"] == ["gnome-screenshot", "-f", str(d)])
    xw = plan("window", title="Firefox", dest=d, platform="linux", env=x11, which=_which("scrot", "xdotool"))
    ctx.check("Linux X11: a window through xdotool", xw["argv"][:4] == ["xdotool", "search", "--name", "Firefox"])
    ww = plan("window", title="Firefox", dest=d, platform="linux", env=way, which=_which("grim", "xdotool"))
    ctx.check(f"Linux Wayland: a window by title says so, got {ww}", "needs X11" in ww.get("error", ""))


@test
def test_the_lines_that_stop_it(ctx: Ctx):
    from halo_harness.tools.screenshot_capture import capture, plan
    d = _dest()
    ssh = plan("screen", dest=d, platform="linux", env={"SSH_CONNECTION": "192.0.2.10 1 192.0.2.20 22"}, which=_which("scrot"))
    ctx.check(f"no display under SSH: one line, got {ssh}", "no display" in ssh["error"] and "SSH" in ssh["error"])
    ctx.check("no display at all", "DISPLAY" in plan("screen", dest=d, platform="linux", env={}, which=_which("scrot"))["error"])
    ctx.check("no tool", "no screenshot tool" in plan("screen", dest=d, platform="linux", env={"DISPLAY": ":0"}, which=_which())["error"])
    ctx.check("a window needs a title", "title" in plan("window", dest=d, platform="win32")["error"])
    ctx.check("a bad rect", "rect is" in plan("region", rect="abc", dest=d, platform="win32")["error"])
    with Seam([(3, "NOTFOUND")]) as s:
        got = capture("window", title="Nope", dest=d, platform="win32")
    ctx.check(f"Windows: the window-not-found line, got {got}", got["ok"] is False and "no window whose title contains 'Nope'" in got["say"]
              and len(s.calls) == 1)
    with Seam([(1, "")]) as s:
        got = capture("window", title="Nope", dest=_dest(), platform="linux", env={"DISPLAY": ":0"}, which=_which("scrot", "xdotool"))
    ctx.check(f"Linux: xdotool finds none, got {got}", got["ok"] is False and "no window" in got["say"])
    with Seam([(0, "X=10\nY=20\nWIDTH=300\nHEIGHT=200\nSCREEN=0\n"), (0, "")]) as s:
        got = capture("window", title="Firefox", dest=_dest(), platform="linux", env={"DISPLAY": ":0"}, which=_which("scrot", "xdotool"))
    ctx.check(f"Linux: the window's geometry, then a region, got {s.calls}", got["ok"] and s.calls[1][:4] == ["scrot", "-o", "-a", "10,20,300,200"])
    with Seam([(0, "{100, 50}, {800, 600}"), (0, "")]) as s:
        got = capture("window", title="Safari", dest=_dest(), platform="darwin")
    ctx.check(f"Mac: the bounds, then -R, got {s.calls}", got["ok"] and s.calls[1][:4] == ["screencapture", "-x", "-R", "100,50,800,600"])
    with Seam([(1, "no-file")]):
        got = capture("screen", dest=_dest(), platform="darwin")
    ctx.check(f"a failed command says which tool, got {got}", got["ok"] is False and "screencapture -x did not capture" in got["say"])


@test
def test_the_png_lands_in_the_sessions_images_folder(ctx: Ctx):
    from halo_harness.tools.screenshot import capture_for, images_folder
    home = tempfile.mkdtemp(prefix="ey-home-")
    saved = os.environ.get("BRIDGE_TEST_HOME")
    os.environ["BRIDGE_TEST_HOME"] = home
    try:
        with Seam():
            a = capture_for("sess-1", "screen")
            b = capture_for("sess-1", "screen")
        folder = images_folder("sess-1")
        ctx.check(f"shot-1 then shot-2 in the session's folder, got {a.get('path')} {b.get('path')}",
                  Path(a["path"]).name == "shot-1.png" and Path(b["path"]).name == "shot-2.png" and Path(a["path"]).parent == folder
                  and str(folder).startswith(home) and folder.name == "sess-1" and folder.parent.name == "attachments")
        ctx.check(f"its size read back, got {a.get('width')} x {a.get('height')}", (a["width"], a["height"]) == (4, 3))
        os.environ["HALO_SCREENSHOT_FIXTURE"] = str(FIXTURE)
        try:
            from halo_harness.tools import screenshot_capture as C
            boom = lambda *a, **k: (_ for _ in ()).throw(AssertionError("ran"))  # noqa: E731
            saved_runner, C.RUNNER = C.RUNNER, boom
            try:
                f = capture_for("sess-2", "screen")
            finally:
                C.RUNNER = saved_runner
        finally:
            os.environ.pop("HALO_SCREENSHOT_FIXTURE", None)
        ctx.check(f"the test flag's fixture runs nothing, got {f}", f["ok"] and "fixture" in f["tool"])
    finally:
        if saved is None:
            os.environ.pop("BRIDGE_TEST_HOME", None)
        else:
            os.environ["BRIDGE_TEST_HOME"] = saved


@test
def test_the_block_or_the_note_by_model(ctx: Ctx):
    from halo_harness.tools.base import ToolContext
    from halo_harness.tools.screenshot import ScreenshotTool
    home = tempfile.mkdtemp(prefix="ey-home-")
    saved = os.environ.get("BRIDGE_TEST_HOME")
    os.environ["BRIDGE_TEST_HOME"] = home
    try:
        sdir = Path(home) / "sessions" / "s-eyes"
        with Seam():
            sees = ScreenshotTool().run({"target": "screen"}, ToolContext(cwd=Path(home), session_dir=sdir, vision=True))
            blind = ScreenshotTool().run({"target": "screen"}, ToolContext(cwd=Path(home), session_dir=sdir, vision=False,
                                                                           model_ref="ol:qwen3-coder:30b@lab"))
        ctx.check(f"a model that sees: a text line and the image block, got {type(sees.content)}",
                  isinstance(sees.content, list) and sees.content[1]["type"] == "image" and sees.content[1]["source"]["media_type"] == "image/png"
                  and "shot-1.png" in sees.content[0]["text"])
        head = json.loads(blind.content.splitlines()[0])
        ctx.check(f"one that cannot: path, size and the note, got {head}", head["width"] == 4 and head["height"] == 3
                  and head["note"] == f"ol:qwen3-coder:30b@lab cannot see images: the file is at {head['path']}"
                  and "attachments" in head["path"] and "s-eyes" in head["path"])
    finally:
        if saved is None:
            os.environ.pop("BRIDGE_TEST_HOME", None)
        else:
            os.environ["BRIDGE_TEST_HOME"] = saved


@test
def test_registered_read_only_and_found(ctx: Ctx):
    from halo_harness.isolation.capabilities import capability_of
    from halo_harness.tools.registry import ToolRegistry, default_tools
    from halo_harness.tools.screenshot import parse_args
    names = [t.name for t in default_tools()]
    ctx.check("registered right after Media", names.index("Screenshot") == names.index("Media") + 1)
    reg = ToolRegistry(default_tools())
    ctx.check("read-only", reg.is_read_only("Screenshot"))
    ctx.check("the media capability", capability_of("Screenshot") == "media")
    from halo_harness.tools.base import ToolContext
    found = reg.dispatch("ToolSearch", {"query": "screenshot"}, ToolContext(cwd=Path("."), registry=reg))
    ctx.check(f"ToolSearch finds it, got {str(found.content)[:120]}", "Screenshot" in str(found.content))
    ctx.check("/screenshot words", parse_args("") == {"target": "screen"} and parse_args("window Ableton Live") ==
              {"target": "window", "title": "Ableton Live"} and parse_args("region 1,2,3,4") == {"target": "region", "rect": "1,2,3,4"}
              and parse_args("display 2") == {"target": "screen", "display": "2"})


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
