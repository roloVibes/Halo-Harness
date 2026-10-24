"""tests.test_front_page_media -- 2.0.10 round 6 (the front-page redo): every
image the README references exists and is under 1 MB; every PNG under
docs/media comes from tools/captures.json (a name match) and every capture
has its SVG (and, when animated, its .anim.svg) beside it; the hand-drawn
diagrams are small; the committed capture SVGs are byte-identical to a fresh
`tools/capture_screens.py --check` render (PNGs are never compared byte-wise,
Chrome builds differ -- only their existence and size).
"""

from __future__ import annotations

TIER = "full"  # the TUI capture renders (pilot scenes): the full tier

import json
import os
import re
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()

MEDIA = REPO_DIR / "docs" / "media"
ONE_MB = 1024 * 1024
DIAGRAM_CAP = 60 * 1024
_MD_IMG = re.compile(r"!\[[^\]]*\]\(([^)\s]+)\)")
_HTML_IMG = re.compile(r"""<img\b[^>]*?\bsrc=["']([^"']+)["']""", re.IGNORECASE)


def _captures() -> dict:
    return json.loads((REPO_DIR / "tools" / "captures.json").read_text(encoding="utf-8"))


def _readme_images() -> "list[str]":
    text = (REPO_DIR / "README.md").read_text(encoding="utf-8")
    return _MD_IMG.findall(text) + _HTML_IMG.findall(text)


@test
def test_every_readme_image_exists_and_is_under_1mb(ctx: Ctx):
    images = _readme_images()
    local = [i for i in images if not i.startswith(("http://", "https://"))]
    ctx.check(f"the README references local images, got {len(local)}", len(local) >= 15)
    for ref in sorted(set(local)):
        path = REPO_DIR / ref
        ctx.check(f"{ref} exists", path.is_file())
        if path.is_file():
            ctx.check(f"{ref} is under 1 MB (got {path.stat().st_size})", path.stat().st_size < ONE_MB)


@test
def test_every_readme_png_comes_from_captures_json(ctx: Ctx):
    names = {c["name"] for c in _captures()["captures"]}
    pngs = [i for i in _readme_images() if i.endswith(".png")]
    ctx.check("the README shows at least one PNG capture", pngs)
    for ref in sorted(set(pngs)):
        path = Path(ref)
        ctx.check(f"{ref} lives in docs/media/", path.parent.as_posix() == "docs/media")
        if path.stem in ("studio-orchestra", "studio-orchestra-start", "studio-orchestra-plan", "studio-orchestra-coach", "studio-roles", "studio-design", "studio-modes",
                         "hero",  # 3.1.6.0 R4: tools/hero_png.py, the wordmark over the Session dashboard
                         "studio-session-live",  # 3.1.5.0 R3: tools/capture_session_anim.py (with the studio-session and studio-roles-live GIFs)
                         "studio-fleet", "studio-roles-live", "studio-fleet-panels", "studio-fleet-capabilities", "studio-fleet-mission", "studio-team", "studio-session"):  # tools/capture_studio.py (and studio_modes_banner.py) render these, not the TUI pilots
            continue
        ctx.check(f"{ref} matches a capture name in tools/captures.json", path.stem in names)
    for ref in sorted({i for i in _readme_images() if i.endswith(".anim.svg")}):
        ctx.check(f"{ref} belongs to an animated capture",
                  any(c["name"] + ".anim.svg" == Path(ref).name and c.get("anim") for c in _captures()["captures"]))


@test
def test_every_capture_has_its_files_and_every_png_is_a_capture(ctx: Ctx):
    caps = _captures()["captures"]
    names = {c["name"] for c in caps}
    ctx.check("captures.json lists the nine TUI scenes (the HUD and level captures went in 3.1.5.0)", len(caps) >= 9)
    for cap in caps:
        n = cap["name"]
        for suffix in (".svg", ".png") + ((".anim.svg",) if cap.get("anim") else ()):
            path = MEDIA / (n + suffix)
            ctx.check(f"docs/media/{n}{suffix} exists", path.is_file())
            if path.is_file():
                ctx.check(f"docs/media/{n}{suffix} is under 1 MB", path.stat().st_size < ONE_MB)
        if (MEDIA / f"{n}.png").is_file():
            ctx.check(f"docs/media/{n}.png has the PNG signature", (MEDIA / f"{n}.png").read_bytes()[:8] == b"\x89PNG\r\n\x1a\n")
    for png in MEDIA.glob("*.png"):
        if png.stem in ("hero", "social-preview", "studio-design", "studio-modes",  # 3.1.6.0 R4: both from tools/hero_png.py
                        "studio-session-live",  # 3.1.5.0 R3: tools/capture_session_anim.py (with the studio-session and studio-roles-live GIFs)
                        "studio-orchestra", "studio-orchestra-start", "studio-orchestra-plan", "studio-orchestra-coach", "studio-roles",
                        "studio-fleet", "studio-roles-live", "studio-fleet-panels", "studio-fleet-capabilities", "studio-fleet-mission", "studio-team", "studio-session",
                        "studio-packs"):  # hero_png.py, tools/capture_studio.py (--mode fleet: tools/capture_fleet.py; 3.2.0.0 R7 --mode packs) and studio_modes_banner.py, not TUI captures
            continue
        ctx.check(f"{png.name} is a capture from captures.json", png.stem in names)
    ctx.check("the animated captures are the turn and the steer",
              {c["name"] for c in caps if c.get("anim")} == {"turn-phase-line", "steer-mid-turn"})


@test
def test_diagrams_and_hero_exist_and_are_small(ctx: Ctx):
    diagrams = ("session-flow", "routes", "connectors-bridge", "remote-control")
    for d in diagrams:
        path = MEDIA / "diagrams" / f"{d}.svg"
        ctx.check(f"diagrams/{d}.svg exists", path.is_file())
        if path.is_file():
            ctx.check(f"diagrams/{d}.svg is at most 60 KB (got {path.stat().st_size})", path.stat().st_size <= DIAGRAM_CAP)
            ctx.check(f"diagrams/{d}.svg is an svg", "<svg" in path.read_text(encoding="utf-8")[:400])
    hero = MEDIA / "hero.svg"
    ctx.check("hero.svg exists and is at most 60 KB", hero.is_file() and hero.stat().st_size <= DIAGRAM_CAP)
    readme = (REPO_DIR / "README.md").read_text(encoding="utf-8")
    # 3.1.5.0 R4: the Signal section left the front page; remote-control.svg stays (the HANDBOOK draws it)
    for d in diagrams[:3]:
        ctx.check(f"the README shows diagrams/{d}.svg", f"docs/media/diagrams/{d}.svg" in readme)
    from halo_harness.banner import BANNER_ART
    hero_text = hero.read_text(encoding="utf-8") if hero.is_file() else ""
    # 2.0.11 round A2: tools/hero_svg.py draws the block art as vector cells
    # and carries the rows themselves in the <desc>, so the hero can never
    # drift from banner.py.
    ctx.check("the hero's wordmark is the launch banner's rows", all(row.rstrip() in hero_text for row in BANNER_ART.split("\n")))
    ctx.check("the hero carries an explicit size", 'width="1280" height="330"' in hero_text[:600])
    # 3.1.6.0 R4: the vector hero takes the Studio tagline and three short chips
    ctx.check("hero.svg carries the Studio tagline",
              "The Claude Code-compatible harness for any model, with Studio: every agent, live." in hero_text)
    for chip in ("Studio · every agent, live", "any model", "your Claude Code setup, in place"):
        ctx.check(f"hero.svg carries the chip {chip!r}", f">{chip}</text>" in hero_text)
    ctx.check("the five model chips left the hero", ">DeepSeek</text>" not in hero_text)


def _png_size(path: Path) -> "tuple[int, int]":
    head = path.read_bytes()[:24]  # the signature, then IHDR's length, type, width, height
    return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")


@test
def test_hero_png_and_social_preview_are_tools_hero_png_renders(ctx: Ctx):
    """3.1.6.0 R4: the README's first image is docs/media/hero.png, the
    wordmark over Studio's Session dashboard, and social-preview.png is the
    same picture at GitHub's size; tools/hero_png.py writes both from
    studio-session.png and the banner rows. Pixel identity is pinned where
    the committed pair was rendered (Windows); Pillow's FreeType build sets
    the line's anti-aliasing, so elsewhere a stale line is informational.
    Without Pillow (the CI lockfiles carry none) only the files are checked."""
    readme = (REPO_DIR / "README.md").read_text(encoding="utf-8")
    first = _HTML_IMG.findall(readme)[0] if _HTML_IMG.findall(readme) else ""
    ctx.check(f"the README's first image is docs/media/hero.png, got {first!r}", first == "docs/media/hero.png")
    ctx.check("the first image's alt text names the dashboard",
              'alt="Halo Harness: the wordmark over Studio\'s Session dashboard, every agent live"' in readme.split("\n## ", 1)[0])
    for name, size in (("hero.png", (2560, 720)), ("social-preview.png", (1280, 640))):
        path = MEDIA / name
        ctx.check(f"docs/media/{name} exists", path.is_file())
        if not path.is_file():
            continue
        ctx.check(f"docs/media/{name} is under 1 MB (got {path.stat().st_size})", path.stat().st_size < ONE_MB)
        ctx.check(f"docs/media/{name} has the PNG signature", path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n")
        ctx.check(f"docs/media/{name} is {size[0]}x{size[1]}, got {_png_size(path)}", _png_size(path) == size)
    import importlib.util
    if importlib.util.find_spec("PIL") is None:
        return
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("HALO_", "ROLO_CLAUDE_", "OPENROUTER_", "DATABRICKS_", "ANTHROPIC_"))}
    env["PYTHONPATH"] = str(REPO_DIR)
    result = subprocess.run([sys.executable, str(REPO_DIR / "tools" / "hero_png.py"), "--check"],
                            capture_output=True, text=True, timeout=120, env=env, cwd=str(REPO_DIR))
    out = result.stdout + result.stderr
    ctx.check(f"tools/hero_png.py --check rendered both without an error:{out[-800:]}",
              "hero check:" in out and "Traceback" not in out)
    if sys.platform == "win32":
        ctx.check(f"hero.png and social-preview.png are what tools/hero_png.py renders "
                  f"(re-run it, and with --social, then commit docs/media):{out[-800:]}",
                  result.returncode == 0 and "hero check: ok" in out)


@test
def test_every_svg_has_an_explicit_size(ctx: Ctx):
    """2.0.11 round A1: a viewBox-only SVG has no intrinsic size, so an
    <img> of it (GitHub's file view, the page a README click opens) lays it
    out at about 300x150 px -- every capture showed as a thumbnail. The
    export helper (`scripts/screenshots.py::sized_svg`) and the animation
    assembler now write `width`/`height`; this pins every committed SVG."""
    root = re.compile(r"<svg\b[^>]*>")
    svgs = sorted(MEDIA.rglob("*.svg")) + sorted((REPO_DIR / "docs" / "screenshots").glob("*.svg"))
    ctx.check(f"found the committed SVGs, got {len(svgs)}", len(svgs) >= 20)
    for path in svgs:
        tag = root.search(path.read_text(encoding="utf-8")[:4000])
        head = tag.group(0) if tag else ""
        ctx.check(f"{path.relative_to(REPO_DIR).as_posix()} root carries width and height",
                  ' width="' in head and ' height="' in head)
    sys.path.insert(0, str(REPO_DIR / "scripts"))
    from svgsize import sized_svg  # pure: scripts/screenshots.py freezes the clock and seeds the RNG on import
    once = sized_svg('<svg class="rich-terminal" viewBox="0 0 1482 928.4" xmlns="x">\n</svg>')
    ctx.check("sized_svg adds width/height from the viewBox", 'width="1482" height="928.4" viewBox="0 0 1482 928.4"' in once)
    ctx.check("sized_svg is idempotent", sized_svg(once) == once)


@test
def test_media_carries_no_real_paths_hosts_or_versions(ctx: Ctx):
    bad = re.compile(r"C:\\Users|C:/Users|/home/[a-z]|/Users/[A-Za-z]|AppData|\b(?:10|192\.168|172\.(?:1[6-9]|2\d|3[01]))\.\d+\.\d+(?:\.\d+)?\b")
    for path in sorted(MEDIA.rglob("*.svg")):
        text = path.read_text(encoding="utf-8")
        ctx.check(f"{path.relative_to(REPO_DIR).as_posix()} has no real path or private address", bad.search(text) is None)
        ctx.check(f"{path.relative_to(REPO_DIR).as_posix()} is LF only", "\r" not in text)


@lru_cache(maxsize=1)
def _check_run() -> "subprocess.CompletedProcess":
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("HALO_", "ROLO_CLAUDE_", "OPENROUTER_", "DATABRICKS_", "ANTHROPIC_"))}
    env["BRIDGE_TEST_NO_BACKGROUND_NET"] = "1"
    env["OLLAMA_HOST"] = "http://127.0.0.1:1"
    env["PYTHONPATH"] = str(REPO_DIR)
    return subprocess.run([sys.executable, str(REPO_DIR / "tools" / "capture_screens.py"), "--check"],
                          capture_output=True, text=True, timeout=300, env=env, cwd=str(REPO_DIR))


@test
def test_committed_capture_svgs_are_a_fresh_renders_output(ctx: Ctx):
    result = _check_run()
    out = result.stdout + result.stderr
    # Byte identity of a Textual SVG holds on the platform that rendered
    # the committed set (Windows); Linux renders differ in timing-driven
    # cells, so there only "every capture rendered, no error" is pinned
    # and a MISMATCH line is informational.
    rendered = all(f"{name}:" in out for name in ("auto-mode", "turn-phase-line", "review-cards", "steer-mid-turn"))
    ctx.check(f"every capture re-rendered without an error:{out[-1200:]}",
              rendered and "Traceback" not in out and "ERROR" not in out)
    if sys.platform == "win32":
        ctx.check(f"the committed SVGs are byte-identical to a fresh render on this platform "
                  f"(re-run tools/capture_screens.py and commit docs/media if a fixture changed):{out[-800:]}",
                  result.returncode == 0 and "capture check: ok" in out)
    else:
        ctx.check("the check finished (mismatches are informational off-Windows)", "capture check:" in out)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
