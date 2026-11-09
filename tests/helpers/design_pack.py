"""tests.helpers.design_pack -- the shipped design pack in a test's scratch home (Halo 3.3.13.0 R2: the Design section
left the core for halo_harness/templates/packs/design/).

    from tests.helpers import design_pack as DP
    DP.enable(state)             # link the pack into the home whose state folder is `state`, every grant given
    api = DP.module("server/api.py")   # the routes' own module (set RUNNER / REGISTERED on it: no model call)
    DP.seed(state)               # the demo "Launch page" project (the pack's tests/seed.py) in that home
    url.replace("mode=x", f"mode={DP.MODE}")    # the section; its routes are DP.API + "/..."
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PACK = REPO / "halo_harness" / "templates" / "packs" / "design"
MODE = "design--design"
API = "/api/packs/design/design"


def enable(state: Path, cwd=None):
    """The pack linked into the home of `state` and enabled with every grant it requests; the pack."""
    from halo_harness.packs import grants as G
    from halo_harness.packs import registry
    from halo_harness.packs.discover import find
    from halo_harness.packs.link import link
    cwd = cwd or Path(state).parent / "project"
    Path(cwd).mkdir(parents=True, exist_ok=True)
    registry.invalidate()
    pack = find("design", cwd=cwd, state_dir=state)
    if pack is None:
        ok, lines = link(str(PACK), cwd=cwd, state_dir=state)
        assert ok, lines
        registry.invalidate()
        pack = find("design", cwd=cwd, state_dir=state)
    ok, lines = G.enable(pack, grant_all=True, state_dir=state)
    assert ok, lines
    return pack


def module(rel: str):
    """One of the pack's modules, the same object Studio's routes import (ext.testing.pack_module)."""
    from halo_harness.ext import testing
    return testing.pack_module(PACK, rel)


def seed(state: Path):
    """The pack's demo project (tests/seed.py, loaded by its path: `tests` here is Halo's own package)."""
    spec = importlib.util.spec_from_file_location("design_pack_seed", PACK / "tests" / "seed.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.seed(state)
