"""tests.test_install_lock_floor -- 3.6.0.0 fix package update-install: requirements.lock installs on the oldest
Python halo supports. pyproject says `requires-python = ">=3.10"` and both installers accept 3.10, but the lock was
compiled for the generating interpreter only: `rpds-py==2026.6.3` (needs 3.11) carried no marker, so on a machine
whose Python is 3.10 (stock Ubuntu 22.04, its WSL image) `uv tool install --constraints requirements.lock .`, the
README's no-installer line and every `halo update` failed with "No solution found".

1. offline, everywhere: the lock's own header says it was compiled for the floor (`--python-version <floor>`), and
   no pin in it is known to need a newer Python without a marker that keeps it off the floor;
2. where uv is on PATH and the index answers: uv resolves pyproject.toml against the lock for the floor and for
   the newest supported minor (skipped, never failed, when uv is missing or offline).
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent


def _floor() -> str:
    text = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    return re.search(r'requires-python\s*=\s*">=\s*(3\.\d+)"', text).group(1)


@test
def test_the_lock_is_compiled_for_the_oldest_supported_python(ctx: Ctx):
    floor = _floor()
    text = (REPO / "requirements.lock").read_text(encoding="utf-8")
    header = "\n".join(text.splitlines()[:3])
    ctx.check(f"the header's command names --python-version {floor}, got {header!r}",
              re.search(rf"--python-version[ =]{re.escape(floor)}\b", header) is not None)
    # the one pin the floor tripped over: rpds-py's newest releases need 3.11
    rpds = re.findall(r"^rpds-py==(\S+)( ;[^\\\n]*)?", text, re.M)
    ctx.check(f"rpds-py is forked by Python version (the newest only from 3.11), got {rpds}",
              len(rpds) == 2 and all("python_full_version" in (m or "") for _v, m in rpds))


@test
def test_uv_resolves_the_lock_on_the_floor_and_the_newest_python(ctx: Ctx):
    uv = shutil.which("uv")
    if not uv:
        raise SkipTest("uv is not on PATH")
    for version in (_floor(), "3.13"):
        r = subprocess.run([uv, "pip", "compile", "pyproject.toml", "-c", "requirements.lock", "--python-version",
                            version, "-q", "--no-header"], cwd=REPO, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=180)
        if r.returncode != 0 and re.search(r"(?i)failed to fetch|connect|dns|offline|timed out|network", r.stderr):
            raise SkipTest(f"the package index did not answer: {r.stderr.strip()[:200]}")
        ctx.check(f"Python {version}: the lock resolves, got {r.returncode} {r.stderr.strip()[-400:]!r}",
                  r.returncode == 0 and "rpds-py==" in r.stdout)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
