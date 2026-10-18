"""tests.helpers.studio_modes_dom -- the DOM helpers of tests/test_studio_modes.py
(moved here in 3.0.9.0 R2 so that file stays small): skip without Chrome, and
`tools/capture_studio.py --mode <mode> --dom` in a scrubbed environment."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parents[2]


def need_chrome() -> None:
    sys.path.insert(0, str(REPO_DIR / "tools"))
    from capture_screens import find_chrome
    from tests.helpers.runner import SkipTest
    if not find_chrome(os.environ.get("HALO_CHROME", "")):
        raise SkipTest("no Chrome found (the DOM checks need headless Chrome)")


def dom(mode: str) -> dict:
    """The capture tool's test-id counts for `mode` (its Start view's and the section's)."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HALO_", "OPENROUTER_", "DATABRICKS_", "ANTHROPIC_", "BRIDGE_"))}
    env.update(PYTHONPATH=str(REPO_DIR), BRIDGE_TEST_NO_BACKGROUND_NET="1")
    r = subprocess.run([sys.executable, str(REPO_DIR / "tools" / "capture_studio.py"), "--mode", mode, "--dom"], capture_output=True,
                       encoding="utf-8", errors="replace", timeout=300, env=env, cwd=str(REPO_DIR))
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {"error": (r.stdout + r.stderr)[-400:]}
