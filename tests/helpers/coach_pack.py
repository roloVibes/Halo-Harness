"""tests.helpers.coach_pack -- the shipped coach pack in a test's scratch home (Halo 3.4.0.0 B2: the coach left the core
for halo_harness/templates/packs/coach/).

    from tests.helpers import coach_pack as CP
    CP.install_names()        # the pack's modules under the names the coach's tests always used (below)
    CP.enable(state)          # link the pack into the home whose state folder is `state`, every grant given
    CP.module("engine/coach.py")        # one module of the pack, imported as `halo coach` and Studio import it

`install_names()` puts the pack's modules (imported through the pack's folder as `halo_packs.coach.*`, the same module
objects `halo coach` and the pack's routes use) into `sys.modules` under the names the moved tests import:
`halo_harness.orchestra.coach*` and `.probe_*` for engine/, `halo_harness.coach_cli` / `.coach_library_cli` /
`.improve_cli` for cli/, `halo_harness.improve(.*)` for improve/ and `halo_harness.studio.coach_api` /
`.coach_probe_job` for server/. Nothing in Halo imports those names any more; only these tests do, so a fake a test
sets on a module is the one the pack's code calls.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PACK = REPO / "halo_harness" / "templates" / "packs" / "coach"
ENGINE = ("coach", "coach_apply", "coach_ask", "coach_citations", "coach_compare", "coach_compose", "coach_experience",
          "coach_library", "coach_library_share", "coach_mission_rules", "coach_orchestra_rules", "coach_probe",
          "coach_probe_card", "coach_probe_prompt", "coach_probe_schema", "coach_record", "coach_rules", "probe_overlay",
          "probe_runs")
IMPROVE = ("apply", "config", "dismissed", "draft", "evidence")
NAMES = {**{f"halo_harness.orchestra.{m}": f"engine/{m}.py" for m in ENGINE},
         **{f"halo_harness.improve.{m}": f"improve/{m}.py" for m in IMPROVE},
         "halo_harness.coach_cli": "cli/coach.py", "halo_harness.coach_library_cli": "cli/library.py",
         "halo_harness.improve_cli": "cli/improve.py", "halo_harness.studio.coach_api": "server/coach_api.py",
         "halo_harness.studio.coach_probe_job": "server/coach_probe_job.py"}


def module(rel: str):
    from halo_harness.studio.packs_routes import ensure_package
    name = ensure_package("coach", PACK)
    parts = Path(rel).with_suffix("").parts
    parts = parts[:-1] if parts[-1] == "__init__" else parts
    return importlib.import_module(name + "." + ".".join(parts))


def install_names() -> None:
    import halo_harness
    sys.modules["halo_harness.improve"] = module("improve/__init__.py")
    halo_harness.improve = sys.modules["halo_harness.improve"]  # type: ignore[attr-defined]
    for name, rel in NAMES.items():
        mod = module(rel)
        sys.modules[name] = mod
        parent, _, leaf = name.rpartition(".")
        setattr(importlib.import_module(parent), leaf, mod)


def enable(state: Path, cwd=None):
    """The pack linked into the home of `state` and enabled with every grant it requests; the pack."""
    from halo_harness.packs import grants as G
    from halo_harness.packs import registry
    from halo_harness.packs.discover import find
    from halo_harness.packs.link import link
    cwd = cwd or Path(state).parent / "project"
    Path(cwd).mkdir(parents=True, exist_ok=True)
    registry.invalidate()
    pack = find("coach", cwd=cwd, state_dir=state)
    if pack is None:
        ok, lines = link(str(PACK), cwd=cwd, state_dir=state)
        assert ok, lines
        registry.invalidate()
        pack = find("coach", cwd=cwd, state_dir=state)
    ok, lines = G.enable(pack, grant_all=True, state_dir=state)
    assert ok, lines
    registry.invalidate()
    return pack


def on() -> None:
    """The coach pack runs in every scratch home of this process and its children (PACKS_TEST_SHIPPED, as
    tests/helpers/fleet_pack.on() does for the fleet; 3.4.0.0: the fleet's coach_library and mission coach reach it)."""
    from tests.helpers.fleet_pack import shipped
    shipped("coach", True)


def off() -> None:
    from tests.helpers.fleet_pack import shipped
    shipped("coach", False)

