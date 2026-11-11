"""tools/capture_fresh.py -- a fresh scratch home for the Studio drivers (Halo 3.4.0.0 B: what tools/capture_start.py
kept besides the "Start here" overlay, which left with the guided first run for the first-run pack).

    fresh_home() -> Path    a scratch home with nothing of its own (the shipped lineups are copied in on first use)
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def fresh_home() -> Path:
    home = Path(tempfile.mkdtemp(prefix="halo-studio-fresh-"))
    os.environ["BRIDGE_TEST_HOME"] = str(home)
    os.environ.pop("BRIDGE_STATE_DIR", None)
    from halo_harness.providers.config import default_state_dir
    state = Path(default_state_dir())
    state.mkdir(parents=True, exist_ok=True)
    return state
