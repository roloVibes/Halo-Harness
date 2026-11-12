"""tests.helpers.trust_dir -- trust a scratch folder the way the person does, in the scoped home (Halo 3.4.1.2).

Since 3.4.1.2 (ENGINE-1) a project's own `.halo/workflows/`, `.halo/teams/` and `.halo/agents/` load only in a trusted
folder (halo_harness/project_gate.py). A test whose scratch project carries such files trusts it first:

    trust(proj)        # adds the folder to <scoped home>/trust.json (config/claude_json.is_trusted condition c)
    untrust(proj)
Never touches the real ~/.halo: `bridge_home()` is the test's BRIDGE_TEST_HOME / BRIDGE_STATE_DIR.
"""
from __future__ import annotations

import json
import os
from pathlib import Path


def _path() -> Path:
    from halo_harness.config.paths import bridge_home
    if not (os.environ.get("BRIDGE_TEST_HOME") or os.environ.get("BRIDGE_STATE_DIR")):
        raise RuntimeError("trust_dir: scope the home first (BRIDGE_TEST_HOME)")
    return bridge_home() / "trust.json"


def _edit(proj, on: bool) -> None:
    from halo_harness.config.paths import normalize_cwd
    path = _path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    data = data if isinstance(data, dict) else {}
    for key in {normalize_cwd(Path(proj)), normalize_cwd(Path(proj).resolve())}:  # a temp dir may be a short name
        if on:
            data[key] = True
        else:
            data.pop(key, None)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def trust(proj) -> None:
    _edit(proj, True)


def untrust(proj) -> None:
    _edit(proj, False)
