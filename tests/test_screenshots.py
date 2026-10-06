"""tests.test_screenshots -- 2.0.5 round 2d: scripts/screenshots.py
renders the README's gallery from fixture data only, deterministically
(fixed seed, frozen clock, normalized export id, LF writes). This module
runs the script ONCE into a scratch dir and checks (a) every scene
exists and is non-trivial, (b) each carries its scene's marker string,
and (c) the committed docs/screenshots/*.svg are byte-identical to the
script's fresh output -- "the committed SVGs are the script's output,
nothing hand-edited" is enforced, not hoped for. A fixture change that
alters a scene fails here until the committed SVGs are re-rendered.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from functools import lru_cache
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()

SCENES = ("launch", "turn", "picker", "team-step", "mcp", "permission", "balances")

# One visible, stable string per scene -- decoded the way the SVG encodes
# text (entity nbsp -> space), so a marker never depends on raw XML.
MARKERS = {
    "launch.svg": ("_   _", "halo 2."),          # the banner rows + version line
    "turn.svg": ("Grep", "18"),                  # the running tool card + staged phase elapsed
    "picker.svg": ("atlas-pro", "ctx"),          # fixture rows + the context column
    "team-step.svg": ("Custom roles",),          # the switch, flipped on
    "mcp.svg": ("broken-fixture", "deep dive"),  # the failing server + the legend
    "permission.svg": ("fixture-build",),        # the fixture ask's command
    "balances.svg": ("$12.40", "OpenRouter"),    # the chip + the table row
}


def _child_env() -> dict:
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("HALO_", "ROLO_CLAUDE_", "OPENROUTER_", "DATABRICKS_", "ANTHROPIC_"))}
    env["BRIDGE_TEST_NO_BACKGROUND_NET"] = "1"
    env["OLLAMA_HOST"] = "http://127.0.0.1:1"
    env["PYTHONPATH"] = str(REPO_DIR)
    return env


import os  # noqa: E402  (used by _child_env above)


@lru_cache(maxsize=1)
def _rendered() -> Path:
    """One script run for the whole module (it takes a few seconds; every
    test reads its output from here)."""
    out = Path(tempfile.mkdtemp(prefix="halo-screenshots-test-"))
    result = subprocess.run(
        [sys.executable, str(REPO_DIR / "scripts" / "screenshots.py"), "--out", str(out)],
        capture_output=True, text=True, timeout=180, env=_child_env(), cwd=str(REPO_DIR))
    assert result.returncode == 0, f"screenshots.py failed:\n{result.stdout}\n{result.stderr}"
    return out


def _decoded(svg_path: Path) -> str:
    raw = svg_path.read_text(encoding="utf-8")
    return re.sub(r"&#160;", " ", " ".join(re.findall(r">([^<]+)<", raw)))


@test
def test_every_scene_exists_and_is_non_trivial(ctx: Ctx):
    out = _rendered()
    for scene in SCENES:
        path = out / f"{scene}.svg"
        ctx.check(f"{scene}.svg exists", path.exists())
        if not path.exists():
            continue
        size = path.stat().st_size
        ctx.check(f"{scene}.svg is non-trivial (size {size} > 4000)", size > 4000)
        ctx.check(f"{scene}.svg is an svg", path.read_text(encoding="utf-8").lstrip().startswith("<svg") or
                  "<svg" in path.read_text(encoding="utf-8")[:600])


@test
def test_every_scene_carries_its_marker(ctx: Ctx):
    out = _rendered()
    for fname, markers in MARKERS.items():
        text = _decoded(out / fname)
        for marker in markers:
            ctx.check(f"{fname} contains marker {marker!r}", marker in text)


@test
def test_committed_svgs_are_the_scripts_output(ctx: Ctx):
    out = _rendered()
    committed_dir = REPO_DIR / "docs" / "screenshots"
    for scene in SCENES:
        committed = committed_dir / f"{scene}.svg"
        ctx.check(f"docs/screenshots/{scene}.svg is committed", committed.exists())
        if not committed.exists():
            continue
        fresh = (out / f"{scene}.svg").read_bytes()
        ctx.check(f"docs/screenshots/{scene}.svg is byte-identical to a fresh render "
                  f"(re-run scripts/screenshots.py and commit its output if a fixture changed)",
                  committed.read_bytes() == fresh)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
