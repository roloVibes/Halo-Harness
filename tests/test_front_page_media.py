"""tests.test_front_page_media -- 2.0.10 round 6 (the front-page redo): every
image the README references exists and is under 1 MB; every PNG under
docs/media comes from tools/captures.json (a name match) and every capture
has its SVG (and, when animated, its .anim.svg) beside it; the hand-drawn
diagrams are small; the committed capture SVGs are byte-identical to a fresh
`tools/capture_screens.py --check` render (PNGs are never compared byte-wise,
Chrome builds differ -- only their existence and size).
"""

from __future__ import annotations

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
    ctx.check(f"the README references local images, got {len(local)}", len(local) >= 20)
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
        ctx.check(f"{ref} matches a capture name in tools/captures.json", path.stem in names)
    for ref in sorted({i for i in _readme_images() if i.endswith(".anim.svg")}):
        ctx.check(f"{ref} belongs to an animated capture",
                  any(c["name"] + ".anim.svg" == Path(ref).name and c.get("anim") for c in _captures()["captures"]))


@test
def test_every_capture_has_its_files_and_every_png_is_a_capture(ctx: Ctx):
    caps = _captures()["captures"]
    names = {c["name"] for c in caps}
    ctx.check("captures.json lists the eleven brief scenes plus the auto-mode one", len(caps) >= 12)
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
        ctx.check(f"{png.name} is a capture from captures.json", png.stem in names)
    ctx.check("the two animated captures are the turn and the steer",
              {c["name"] for c in caps if c.get("anim")} == {"turn-phase-line", "steer-mid-turn"})


@test
def test_diagrams_and_hero_exist_and_are_small(ctx: Ctx):
    diagrams = ("session-flow", "routes", "roles-orgs", "connectors-bridge", "remote-control")
    for d in diagrams:
        path = MEDIA / "diagrams" / f"{d}.svg"
        ctx.check(f"diagrams/{d}.svg exists", path.is_file())
        if path.is_file():
            ctx.check(f"diagrams/{d}.svg is at most 60 KB (got {path.stat().st_size})", path.stat().st_size <= DIAGRAM_CAP)
            ctx.check(f"diagrams/{d}.svg is an svg", "<svg" in path.read_text(encoding="utf-8")[:400])
    hero = MEDIA / "hero.svg"
    ctx.check("hero.svg exists and is at most 60 KB", hero.is_file() and hero.stat().st_size <= DIAGRAM_CAP)
    readme = (REPO_DIR / "README.md").read_text(encoding="utf-8")
    for d in diagrams:
        ctx.check(f"the README shows diagrams/{d}.svg", f"docs/media/diagrams/{d}.svg" in readme)
    from halo_harness.banner import BANNER
    hero_text = hero.read_text(encoding="utf-8") if hero.is_file() else ""
    ctx.check("the hero's wordmark is the launch banner's rows", all(row.rstrip().replace("&", "&amp;") in hero_text for row in BANNER.split("\n")))


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
    ctx.check(f"tools/capture_screens.py --check exits 0 (re-run tools/capture_screens.py and commit docs/media if a "
              f"fixture changed):\n{result.stdout[-1500:]}\n{result.stderr[-800:]}", result.returncode == 0)
    ctx.check("the check reports ok", "capture check: ok" in result.stdout)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
