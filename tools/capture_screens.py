"""tools/capture_screens.py -- render the front-page captures (Halo 2.0.10 round 6).

Reads tools/captures.json (name, scene, size, theme, scale), drives the real
TUI through the pilot scenes in scripts/capture_scenes.py and
scripts/capture_dialogs.py (fixture data only, the frozen clock and seeded
tips of scripts/screenshots.py) and writes, per capture:

  docs/media/<name>.svg        the Textual export (deterministic, byte-identical on rerun)
  docs/media/<name>.anim.svg   animated captures only: the frames hand-assembled
                               into one looping SMIL SVG (no GIF library)
  docs/media/<name>.png        headless Chrome's render of the SVG at the capture's
                               scale, when Chrome is found (skipped otherwise; the
                               SVG is kept either way)

`--check` re-renders every SVG into a scratch dir and compares it byte for
byte with the committed one (PNGs are never compared byte-wise -- Chrome builds
differ -- only their existence). See docs/MEDIA.md.

Usage: python tools/capture_screens.py [--out DIR] [--only a,b] [--no-png] [--check] [--chrome PATH]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CAPTURES = REPO / "tools" / "captures.json"
DEFAULT_OUT = REPO / "docs" / "media"
CHROME_ENV = os.environ.get("HALO_CHROME", "")  # read before scripts/screenshots.py scrubs HALO_*

_CHROME_CANDIDATES = (
    "C:/Program Files/Google/Chrome/Application/chrome.exe",
    "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)
_CHROME_NAMES = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome")


def load_captures() -> dict:
    return json.loads(CAPTURES.read_text(encoding="utf-8"))


def find_chrome(explicit: str = "") -> "str | None":
    for cand in (explicit, CHROME_ENV):
        if cand and Path(cand).exists():
            return cand
    for cand in _CHROME_CANDIDATES:
        if Path(cand).exists():
            return cand
    for name in _CHROME_NAMES:
        found = shutil.which(name)
        if found:
            return found
    return None


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")  # LF on every platform


def viewbox(svg: str) -> "tuple[float, float]":
    m = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg)
    if not m:
        raise ValueError("no viewBox in the export")
    return float(m.group(1)), float(m.group(2))


def assemble_animation(frames: "list[str]", seconds: "list[float]") -> str:
    """One looping SVG from per-frame Textual exports: every frame becomes a
    nested <svg> (its CSS class prefix renamed per frame so the style blocks
    cannot collide) whose `visibility` is stepped by a discrete <animate>."""
    width, height = viewbox(frames[0])
    total = sum(seconds)
    out = [f'<svg class="rich-terminal" width="{width:g}" height="{height:g}" viewBox="0 0 {width:g} {height:g}" '
           'xmlns="http://www.w3.org/2000/svg">',
           f"<!-- {len(frames)} frames, {total:g} s loop; assembled by tools/capture_screens.py -->"]
    start = 0.0
    for i, (frame, dur) in enumerate(zip(frames, seconds)):
        body = frame.replace("terminal-0-", f"terminal-f{i}-")
        body = re.sub(r"^<svg[^>]*>", f'<svg id="frame{i}" width="{width:g}" height="{height:g}" '
                      f'viewBox="0 0 {width:g} {height:g}" visibility="{"visible" if i == 0 else "hidden"}">',
                      body.strip(), count=1)
        end = start + dur
        times, values = [0.0], ["hidden"]
        if start > 0:
            times, values = [0.0, start / total], ["hidden", "visible"]
        else:
            values = ["visible"]
        if end < total:
            times.append(end / total)
            values.append("hidden")
        anim = (f'<animate attributeName="visibility" calcMode="discrete" dur="{total:g}s" repeatCount="indefinite" '
                f'keyTimes="{";".join(f"{t:.4f}" for t in times)}" values="{";".join(values)}"/>')
        cut = body.rindex("</svg>")
        out.append(body[:cut] + anim + body[cut:])
        start = end
    out.append("</svg>")
    return "\n".join(out) + "\n"


def render_png(chrome: str, svg_path: Path, png_path: Path, scale: int) -> bool:
    width, height = viewbox(svg_path.read_text(encoding="utf-8"))
    profile = tempfile.mkdtemp(prefix="halo-chrome-")
    cmd = [chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={profile}",
           f"--screenshot={png_path}", f"--window-size={int(width + 0.999)},{int(height + 0.999)}",
           f"--force-device-scale-factor={scale}", svg_path.resolve().as_uri()]
    try:
        subprocess.run(cmd, capture_output=True, timeout=90)
    except (OSError, subprocess.SubprocessError):
        return False
    finally:
        shutil.rmtree(profile, ignore_errors=True)
    return png_path.exists() and png_path.stat().st_size > 1000


async def render_all(spec: dict, only: "set[str] | None", out: Path) -> "list[dict]":
    sys.path.insert(0, str(REPO / "scripts"))
    import capture_dialogs  # noqa: E402  (sets the scoped env, frozen clock and seeded tips on import)

    made = []
    for cap in spec["captures"]:
        if only and cap["name"] not in only:
            continue
        size = tuple(cap.get("size") or spec["size"])
        frames = await capture_dialogs.SCENES[cap["scene"]](size, cap.get("theme") or spec["theme"])
        keep = frames[cap.get("still_frame", -1)]
        write_text(out / f"{cap['name']}.svg", keep)
        files = [f"{cap['name']}.svg"]
        if cap.get("anim"):
            write_text(out / f"{cap['name']}.anim.svg", assemble_animation(frames, cap["frame_seconds"]))
            files.append(f"{cap['name']}.anim.svg")
        made.append({"cap": cap, "files": files})
        print(f"  {cap['name']}: {len(frames)} frame(s)")
    return made


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the front-page captures (SVG, animated SVG, PNG)")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="output directory (default docs/media)")
    parser.add_argument("--only", default="", help="comma-separated capture names")
    parser.add_argument("--no-png", action="store_true", help="skip the Chrome PNG step")
    parser.add_argument("--check", action="store_true", help="re-render the SVGs and compare with the committed ones")
    parser.add_argument("--chrome", default="", help="path to a Chrome/Chromium binary")
    args = parser.parse_args()
    spec = load_captures()
    only = {n for n in args.only.split(",") if n} or None
    if args.check:
        scratch = Path(tempfile.mkdtemp(prefix="halo-capture-check-"))
        made = asyncio.run(render_all(spec, only, scratch))
        bad = []
        for item in made:
            for fname in item["files"]:
                committed = DEFAULT_OUT / fname
                if not committed.exists():
                    bad.append(f"{fname}: not committed")
                elif committed.read_bytes() != (scratch / fname).read_bytes():
                    bad.append(f"{fname}: differs from a fresh render")
            png = DEFAULT_OUT / f"{item['cap']['name']}.png"
            if not png.exists():
                bad.append(f"{png.name}: no PNG committed (run without --check)")
        shutil.rmtree(scratch, ignore_errors=True)
        for line in bad:
            print(f"MISMATCH {line}")
        print("capture check:", "FAILED" if bad else f"ok ({len(made)} captures)")
        return 1 if bad else 0
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    made = asyncio.run(render_all(spec, only, out))
    chrome = None if args.no_png else find_chrome(args.chrome)
    if chrome is None:
        print("no Chrome found (or --no-png): SVGs written, PNG step skipped")
        return 0
    failed = []
    for item in made:
        cap = item["cap"]
        png = out / f"{cap['name']}.png"
        if render_png(chrome, out / f"{cap['name']}.svg", png, int(cap.get("scale") or spec["scale"])):
            print(f"  {png.name}: {png.stat().st_size} bytes")
        else:
            failed.append(png.name)
    for name in failed:
        print(f"PNG failed: {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
