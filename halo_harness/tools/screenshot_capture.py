"""halo_harness.tools.screenshot_capture -- Halo 3.3.6.0 R6: one screen capture on this machine's display, per
OS, behind a runner seam (tests never take a real capture: the seam writes a fixture PNG).

    plan(target, *, title=None, rect=None, display=None, dest, platform=None, env=None, which=None)
        -> {argv, tool} | {error}            the command that writes `dest` (nothing runs)
    capture(target="screen", *, title=None, rect=None, display=None, dest, ...) -> {ok, path, width, height,
        bytes, tool, say}                    plan + RUNNER + the PNG read back (5 MB rule: image_attach)

Windows: PowerShell with System.Drawing (`Graphics.CopyFromScreen`); a window by title through user32
`GetWindowRect` on the first process whose main window title contains it; a display is
`Screen.AllScreens[n-1]`. macOS: `screencapture -x` (`-R x,y,w,h` a region, `-D n` a display; a window by
title: its bounds from System Events, then `-R`). Linux: the first present of grim (Wayland; a region without a
rect through `slurp`), spectacle, gnome-screenshot, scrot, import; a window by title through `xdotool`'s
geometry (X11). No display (no DISPLAY / WAYLAND_DISPLAY, e.g. under SSH): one line, nothing runs.
`RUNNER(argv, *, dest, timeout)` -> (returncode, stdout, stderr) is the seam; under the test flag
(BRIDGE_TEST_HOME) `HALO_SCREENSHOT_FIXTURE=<png>` copies that file instead of running anything.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

TARGETS = ("screen", "window", "region")
LINUX_TOOLS = ("grim", "spectacle", "gnome-screenshot", "scrot", "import")
TIMEOUT_S = 30.0
_PS = r"""
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
Add-Type @'
using System; using System.Runtime.InteropServices;
public struct HaloRect { public int Left, Top, Right, Bottom; }
public static class HaloWin { [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out HaloRect r); }
'@
$target = '__TARGET__'; $title = '__TITLE__'; $rect = '__RECT__'; $display = '__DISPLAY__'; $dest = '__DEST__'
if ($target -eq 'window') {
  $p = Get-Process | Where-Object { $_.MainWindowHandle -ne 0 -and $_.MainWindowTitle -like "*$title*" } | Select-Object -First 1
  if (-not $p) { Write-Output 'NOTFOUND'; exit 3 }
  $r = New-Object HaloRect; [void][HaloWin]::GetWindowRect($p.MainWindowHandle, [ref]$r)
  $x = $r.Left; $y = $r.Top; $w = $r.Right - $r.Left; $h = $r.Bottom - $r.Top
} elseif ($target -eq 'region') {
  $v = $rect.Split(','); $x = [int]$v[0]; $y = [int]$v[1]; $w = [int]$v[2]; $h = [int]$v[3]
} elseif ($display -ne '') {
  $b = [System.Windows.Forms.Screen]::AllScreens[[int]$display - 1].Bounds; $x = $b.X; $y = $b.Y; $w = $b.Width; $h = $b.Height
} else {
  $b = [System.Windows.Forms.SystemInformation]::VirtualScreen; $x = $b.X; $y = $b.Y; $w = $b.Width; $h = $b.Height
}
$bmp = New-Object System.Drawing.Bitmap $w, $h
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($x, $y, 0, 0, $bmp.Size)
$bmp.Save($dest, [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $bmp.Dispose()
Write-Output "OK $w $h"
"""


def _run(argv: list, *, dest: Path, timeout: float = TIMEOUT_S) -> "tuple[int, str, str]":
    try:
        from halo_harness.providers.config import tool_child_env
        env = tool_child_env()
    except Exception:
        env = None
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False, env=env)
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, "", f"{type(e).__name__}: {e}"
    return r.returncode, r.stdout or "", r.stderr or ""


RUNNER = _run


def _q(text) -> str:
    return str(text or "").replace("'", "''")


def _rect(rect) -> Optional[list]:
    if isinstance(rect, str):
        rect = [p for p in rect.replace("x", ",").replace(" ", ",").split(",") if p.strip()]
    try:
        vals = [int(float(v)) for v in rect or []]
    except (TypeError, ValueError):
        return None
    return vals if len(vals) == 4 and vals[2] > 0 and vals[3] > 0 else None


def _windows(target, title, rect, display, dest) -> dict:
    script = (_PS.replace("__TARGET__", target).replace("__TITLE__", _q(title))
              .replace("__RECT__", ",".join(map(str, rect or []))).replace("__DISPLAY__", _q(display or ""))
              .replace("__DEST__", _q(dest)))
    return {"argv": ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script], "tool": "PowerShell System.Drawing"}


def _mac(target, title, rect, display, dest) -> dict:
    argv = ["screencapture", "-x"]
    if target == "window":
        bounds = ('tell application "System Events" to tell (first process whose (name of windows) contains "'
                  f'{str(title).replace(chr(34), "")}") to get {{position, size}} of (first window whose name contains '
                  f'"{str(title).replace(chr(34), "")}")')
        return {"argv": ["osascript", "-e", bounds], "tool": "screencapture -x -R (the window's bounds)", "then": "mac-window"}
    if target == "region":
        argv += ["-R", ",".join(map(str, rect))]
    elif display:
        argv += ["-D", str(display)]
    return {"argv": argv + [str(dest)], "tool": "screencapture -x"}


def _linux(target, title, rect, display, dest, env, which) -> dict:
    if not (env.get("DISPLAY") or env.get("WAYLAND_DISPLAY")):
        why = "an SSH session with no display" if env.get("SSH_CONNECTION") or env.get("SSH_TTY") else "no DISPLAY or WAYLAND_DISPLAY"
        return {"error": f"no display to capture here ({why}): a screenshot needs this machine's own screen"}
    wayland = bool(env.get("WAYLAND_DISPLAY"))
    tools = [t for t in LINUX_TOOLS if which(t)]
    if not tools:
        return {"error": "no screenshot tool found: install grim (Wayland) or scrot / ImageMagick's import (X11)"}
    if target == "window":
        if wayland or not which("xdotool"):
            return {"error": "a window by title needs X11 and xdotool here: capture the screen or a region instead"}
        return {"argv": ["xdotool", "search", "--name", str(title), "getwindowgeometry", "--shell"], "tool": "xdotool",
                "then": "linux-window"}
    tool, d, g = tools[0], str(dest), rect
    if tool == "grim":
        if target == "region" and not g:
            return {"argv": ["sh", "-c", f"grim -g \"$(slurp)\" '{d}'"], "tool": "grim + slurp"}
        return {"argv": ["grim"] + (["-g", f"{g[0]},{g[1]} {g[2]}x{g[3]}"] if g else (["-o", str(display)] if display else [])) + [d],
                "tool": "grim"}
    if tool == "scrot":
        return {"argv": ["scrot", "-o"] + (["-a", ",".join(map(str, g))] if g else ["-s"] if target == "region" else []) + [d],
                "tool": "scrot"}
    if tool == "import":
        return {"argv": ["import", "-window", "root"] + (["-crop", f"{g[2]}x{g[3]}+{g[0]}+{g[1]}"] if g else []) + [d]
                if g or target != "region" else ["import", d], "tool": "import"}
    if tool == "spectacle":
        return {"argv": ["spectacle", "-b", "-n", "-o", d] + (["-r"] if target == "region" else ["-f"]), "tool": "spectacle",
                "crop": g}
    return {"argv": ["gnome-screenshot", "-f", d] + (["-a"] if target == "region" and not g else []), "tool": "gnome-screenshot",
            "crop": g}


def plan(target: str = "screen", *, title=None, rect=None, display=None, dest, platform=None, env=None, which=None) -> dict:
    target = target if target in TARGETS else "screen"
    platform, env, which = platform or sys.platform, os.environ if env is None else env, which or shutil.which
    if target == "window" and not str(title or "").strip():
        return {"error": "a window capture needs its title (title: a part of the window's title)"}
    g = _rect(rect)
    if rect is not None and g is None:
        return {"error": f"rect is [x, y, width, height] in pixels, got {rect!r}"}
    if target == "region" and g is None and platform in ("win32", "darwin"):
        return {"error": "a region needs rect: [x, y, width, height]"}
    if platform == "win32":
        return _windows(target, title, g, display, dest)
    if platform == "darwin":
        return _mac(target, title, g, display, dest)
    return _linux(target, title, g, display, dest, env, which)


def _fixture(dest: Path) -> bool:
    """Under the test flag, `HALO_SCREENSHOT_FIXTURE` stands in for the screen (a subprocess test's seam)."""
    src = os.environ.get("HALO_SCREENSHOT_FIXTURE")
    if not (src and os.environ.get("BRIDGE_TEST_HOME") and Path(src).is_file()):
        return False
    shutil.copyfile(src, dest)
    return True


def _then(p: dict, out: str, dest: Path, env, which) -> dict:
    """The second step of a window by title: its bounds -> a region capture of them."""
    nums = [int(n) for n in re.findall(r"-?\d+", out or "")]
    if p["then"] == "linux-window":
        kv = dict(line.split("=", 1) for line in (out or "").splitlines() if "=" in line)
        try:
            g = [int(kv["X"]), int(kv["Y"]), int(kv["WIDTH"]), int(kv["HEIGHT"])]
        except (KeyError, ValueError):
            return {"error": "no window with that title"}
        return {**plan("region", rect=g, dest=dest, platform="linux", env=env, which=which), "tool": "xdotool + a region"}
    if len(nums) < 4:
        return {"error": "no window with that title"}
    return {"argv": ["screencapture", "-x", "-R", ",".join(map(str, nums[:4])), str(dest)], "tool": p["tool"]}


def capture(target: str = "screen", *, title=None, rect=None, display=None, dest: Path, platform=None, env=None,
            which=None) -> dict:
    """See the module docstring. Never raises: {ok: False, say} names what stopped it."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tool = "a fixture (the test flag)"
    if not _fixture(dest):
        p = plan(target, title=title, rect=rect, display=display, dest=dest, platform=platform, env=env, which=which)
        if p.get("error"):
            return {"ok": False, "say": p["error"]}
        rc, out, err = RUNNER(p["argv"], dest=dest, timeout=TIMEOUT_S)
        if p.get("then"):
            if rc != 0:
                return {"ok": False, "say": f"no window whose title contains {title!r}"}
            p = _then(p, out, dest, env, which)
            if p.get("error"):
                return {"ok": False, "say": f"{p['error']}: {title!r}"}
            rc, out, err = RUNNER(p["argv"], dest=dest, timeout=TIMEOUT_S)
        tool = p["tool"]
        if "NOTFOUND" in (out or ""):
            return {"ok": False, "say": f"no window whose title contains {title!r}"}
        if rc != 0 or not dest.is_file():
            return {"ok": False, "say": f"{tool} did not capture ({(err or out or f'exit {rc}').strip()[:160]})"}
        if p.get("crop"):
            tool += _crop(dest, p["crop"])
    from halo_harness.agent.image_attach import ImageTooLarge, downscale_and_cap
    from halo_harness.tools.imageutil import sniff_dimensions
    data = dest.read_bytes()
    try:
        final, _media = downscale_and_cap(data, "image/png")
    except ImageTooLarge as e:
        dest.unlink(missing_ok=True)
        return {"ok": False, "say": str(e)}
    if final != data:
        dest.write_bytes(final)
    dims = sniff_dimensions(final) or (None, None)
    return {"ok": True, "path": str(dest), "width": dims[0], "height": dims[1], "bytes": len(final), "tool": tool,
            "say": f"captured the {target} ({dims[0]} x {dims[1]}, {len(final) // 1024} KiB) with {tool}"}


def _crop(dest: Path, g: list) -> str:
    """spectacle / gnome-screenshot take no rect: the whole screen cut to it (Pillow), else the whole screen."""
    try:
        from PIL import Image
        with Image.open(dest) as img:
            img.crop((g[0], g[1], g[0] + g[2], g[1] + g[3])).save(dest, format="PNG")
        return " (cut to the region)"
    except Exception:
        return " (the whole screen: this tool takes no region and Pillow is not installed)"


def next_shot_path(folder: Path) -> Path:
    """`shot-<n>.png`, the first free index in the session's images folder."""
    folder.mkdir(parents=True, exist_ok=True)
    n = 1
    while (folder / f"shot-{n}.png").exists():
        n += 1
    return folder / f"shot-{n}.png"
