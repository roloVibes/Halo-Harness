"""tests.helpers.first_run_pack -- the shipped first-run pack in a test's scratch home (Halo 3.4.0.0 B: the guided
first run left the core for halo_harness/templates/packs/first-run/).

    from tests.helpers import first_run_pack as FR
    FR.install_names()        # the pack's modules under the names its tests always used (below)
    FR.enable(state)          # link the pack into the home whose state folder is `state`, every grant given
    FR.module("first_run/card.py")      # one module of the pack, imported as Studio and `halo start` import it

`install_names()` puts the pack's modules (imported through the pack's folder as `halo_packs.first_run.*`, the same
module objects `halo start` and the pack's routes use) into `sys.modules` under the names the moved tests import:
`halo_harness.start` (+ `.engine`, `.card`, ...) for first_run/, `halo_harness.start_cli` for cli/start.py and
`halo_harness.studio.start_job` for server/start_job.py. Nothing in Halo imports those names any more; only these
tests do, so a test's fake set on a module is the one the pack's code calls.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PACK = REPO / "halo_harness" / "templates" / "packs" / "first-run"
MODULES = ("auto_gate", "card", "engine", "errors", "fake", "fresh", "lineup", "sample_repo", "screen", "steps",
           "steps_run", "steps_setup")


def module(rel: str):
    from halo_harness.studio.packs_routes import ensure_package
    name = ensure_package("first-run", PACK)
    return importlib.import_module(name + "." + ".".join(Path(rel).with_suffix("").parts))


def install_names() -> None:
    pkg = module("first_run/__init__.py".replace("/__init__.py", ""))
    sys.modules["halo_harness.start"] = pkg
    for m in MODULES:
        sys.modules[f"halo_harness.start.{m}"] = module(f"first_run/{m}.py")
    sys.modules["halo_harness.start_cli"] = module("cli/start.py")
    sys.modules["halo_harness.studio.start_job"] = module("server/start_job.py")
    import halo_harness
    import halo_harness.studio
    halo_harness.start = pkg  # type: ignore[attr-defined]
    halo_harness.start_cli = sys.modules["halo_harness.start_cli"]  # type: ignore[attr-defined]
    halo_harness.studio.start_job = sys.modules["halo_harness.studio.start_job"]  # type: ignore[attr-defined]


def enable(state: Path, cwd=None):
    """The pack linked into the home of `state` and enabled with every grant it requests; the pack."""
    from halo_harness.packs import grants as G
    from halo_harness.packs import registry
    from halo_harness.packs.discover import find
    from halo_harness.packs.link import link
    cwd = cwd or Path(state).parent / "project"
    Path(cwd).mkdir(parents=True, exist_ok=True)
    registry.invalidate()
    pack = find("first-run", cwd=cwd, state_dir=state)
    if pack is None:
        ok, lines = link(str(PACK), cwd=cwd, state_dir=state)
        assert ok, lines
        registry.invalidate()
        pack = find("first-run", cwd=cwd, state_dir=state)
    ok, lines = G.enable(pack, grant_all=True, state_dir=state)
    assert ok, lines
    registry.invalidate()
    return pack
