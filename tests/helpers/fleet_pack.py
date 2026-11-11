"""tests.helpers.fleet_pack -- the shipped fleet pack's modules under the names the fleet tests always used (Halo 3.4.0.0
C: the fleet left the core for halo_harness/templates/packs/fleet/).

    import tests.helpers.fleet_pack            # (once, before the first import of a moved name) the aliases are on
    from halo_harness.fleet import mission     # the pack's fleet/mission.py, the module `halo fleet` runs
    from tests.helpers import fleet_pack as FP
    FP.enable(state)                           # link the pack into the home of `state`, every grant given
    FP.module("fleet/hub.py")                  # one module of the pack, imported as Halo imports it

`on()` turns the pack on for the process and its children (a test module calls it at import: tests/run_all.py restores
`PACKS_TEST_*` after each module, so it never reaches the next one); `off()` turns it off. Importing this module puts a
finder in front of `sys.meta_path` that answers the moved names -- every
`halo_harness.fleet.<x>` the pack holds (`halo_harness.fleet` itself is a package of them), the Studio route modules
that went with it (`halo_harness.studio.fleet_pair_api`, `fleet_capabilities_api`, `fleet_mission_api`,
`fleet_hub_api`, `fleet_health_api`), `halo_harness.knowledge.share` and `halo_harness.packs.fleet_registry` /
`fleet_share` -- with the pack's own module object (`halo_packs.fleet.<path>`, imported through the pack's folder as
`halo fleet` and Studio import it), so a test's fake set on a module is the one the pack's code calls. Nothing in Halo
imports those names; the core's moved modules (halo_harness/peers/, halo_harness/live/) are imported by their names.
"""
from __future__ import annotations

import importlib
import importlib.abc
import importlib.util
import sys
import types
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PACK = REPO / "halo_harness" / "templates" / "packs" / "fleet"
OLD = "halo_harness.fleet"
NAMES = {
    "halo_harness.knowledge.share": "fleet/knowledge_share.py",
    "halo_harness.packs.fleet_registry": "fleet/fleet_registry.py",
    "halo_harness.packs.fleet_share": "fleet/fleet_share.py",
    **{f"halo_harness.studio.{n}": f"server/{n}.py" for n in ("fleet_pair_api", "fleet_capabilities_api",
                                                             "fleet_mission_api", "fleet_hub_api", "fleet_health_api")},
}


def module(rel: str):
    """The pack's module `rel` ("fleet/hub.py"), imported through its folder as `halo_packs.fleet.<path>`."""
    from halo_harness.studio.packs_routes import ensure_package
    name = ensure_package("fleet", PACK)
    return importlib.import_module(name + "." + ".".join(Path(rel).with_suffix("").parts))


def _rel(fullname: str):
    if fullname in NAMES:
        return NAMES[fullname]
    if fullname.startswith(OLD + "."):
        leaf = fullname[len(OLD) + 1:]
        if "." not in leaf and (PACK / "fleet" / f"{leaf}.py").is_file():
            return f"fleet/{leaf}.py"
    return None


class _Alias(importlib.abc.Loader):
    def __init__(self, rel):
        self.rel, self.spec = rel, None

    def create_module(self, spec):
        if self.rel is None:  # halo_harness.fleet: a package whose submodules this finder answers
            pkg = types.ModuleType(OLD)
            pkg.__path__ = []  # type: ignore[attr-defined]
            return pkg
        mod = module(self.rel)
        self.spec = getattr(mod, "__spec__", None)
        return mod

    def exec_module(self, mod):
        if self.spec is not None:  # the import system set the alias's spec: the module keeps its own
            mod.__spec__ = self.spec


class _Finder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == OLD:
            return importlib.util.spec_from_loader(fullname, _Alias(None), is_package=True)
        rel = _rel(fullname)
        return importlib.util.spec_from_loader(fullname, _Alias(rel)) if rel else None


def install_names() -> None:
    if not any(isinstance(f, _Finder) for f in sys.meta_path):
        sys.meta_path.insert(0, _Finder())


def enable(state: Path, cwd=None):
    """The pack linked into the home of `state` and enabled with every grant it requests; the pack."""
    from halo_harness.packs import grants as G
    from halo_harness.packs import registry
    from halo_harness.packs.discover import find
    from halo_harness.packs.link import link
    cwd = cwd or Path(state).parent / "project"
    Path(cwd).mkdir(parents=True, exist_ok=True)
    registry.invalidate()
    pack = find("fleet", cwd=cwd, state_dir=state)
    if pack is None:
        ok, lines = link(str(PACK), cwd=cwd, state_dir=state)
        assert ok, lines
        registry.invalidate()
        pack = find("fleet", cwd=cwd, state_dir=state)
    ok, lines = G.enable(pack, grant_all=True, state_dir=state)
    assert ok, lines
    registry.invalidate()
    return pack


def shipped(pack: str, run: bool) -> None:
    """Add `pack` to (or drop it from) PACKS_TEST_SHIPPED, keeping any other pack there (a coach test that needs the
    fleet runs both: coach_pack.on() + on())."""
    import os
    ids = [x.strip() for x in os.environ.get("PACKS_TEST_SHIPPED", "").split(",") if x.strip() and x.strip() != pack]
    ids += [pack] if run else []
    if ids:
        os.environ["PACKS_TEST_SHIPPED"] = ",".join(ids)
    else:
        os.environ.pop("PACKS_TEST_SHIPPED", None)
    from halo_harness.packs import registry
    registry.invalidate()


def on() -> None:
    """The fleet pack runs in every scratch home of this process and its children (packs/registry.py's
    PACKS_TEST_SHIPPED, honoured only under BRIDGE_TEST_HOME): the fleet tests' rigs need no link of their own."""
    shipped("fleet", True)


def off() -> None:
    shipped("fleet", False)


install_names()
