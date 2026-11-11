"""tests.test_capability_check_core -- a pack's capability checks need no fleet pack (Halo 3.4.0.0 D, item 7).

Round C moved the capability checker (packs/fleet_registry.py, fleet/mission_assign.has / norm_need) into the fleet
pack, so with that pack off a pack workflow's capability `requires` went unchecked and a pack declaring capabilities
showed no rows. D moves it back into core (halo_harness/packs/fleet_registry.py, halo_harness/peers/needs.py,
halo_harness/peers/projects.py); the fleet pack re-exports it through ext.core. These tests run with the fleet pack
OFF (this module never imports tests.helpers.fleet_pack).
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.helpers.packs_home import PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
NO_GPU = {"hash": "test", "hardware": {"os": "linux", "gpu": [], "ram_gb": 64}, "clis": {}, "mcp": [], "models": []}


def _home(h) -> object:
    from halo_harness.peers.catalog import save
    save(dict(NO_GPU), h.state)
    h.install(h.source("fleet-needs-gpu"), enable=True)
    from halo_harness.packs.discover import find
    return find("fleet-needs-gpu", cwd=h.repo)


@test
def test_the_fleet_pack_is_off_and_the_checker_is_core(ctx: Ctx):
    with PacksHome() as h:
        from halo_harness.packs import fleet_door
        ctx.check("the fleet pack does not run in this home", not fleet_door.running(cwd=h.repo, state_dir=h.state))
        from halo_harness.peers.needs import has, norm_need
        ctx.check("has() answers in core", has({"clis": {"git": "2.45"}}, "cli:git") == "git 2.45 (CLI)" and norm_need("  GPU  x ") == "gpu x")
        import halo_harness.packs.fleet_registry as reg
        ctx.check(f"the registry is core's own module, got {reg.__file__}", "templates" not in Path(reg.__file__).parts)


@test
def test_a_pack_declaring_capabilities_shows_its_rows_with_the_fleet_pack_off(ctx: Ctx):
    with PacksHome() as h:
        pack = _home(h)
        from halo_harness.packs.contrib_views import contributes, doctor_rows
        got = contributes(pack, [], running=True, cwd=h.repo, state_dir=h.state)["fleet"]
        ctx.check(f"the fleet part is listed, got {got}", got is not None)
        caps = {c["name"]: c for c in (got or {}).get("capabilities") or []}
        gpu = caps.get("gpu.render") or {}
        ctx.check(f"gpu.render: not available, why = no GPU here, got {gpu}", gpu.get("available") is False and gpu.get("why") == "no GPU here")
        rows = doctor_rows(pack, [], cwd=h.repo, state_dir=h.state)
        ctx.check(f"halo pack doctor's row says so, got {rows}", any("gpu.render" in str(r) for r in rows))


@test
def test_a_workflow_needing_a_missing_capability_is_refused_with_the_fleet_pack_off(ctx: Ctx):
    with PacksHome() as h:
        pack = _home(h)
        from halo_harness.workflows.inputs import capability_problems
        wf = SimpleNamespace(pack=pack, data={})
        got = capability_problems(wf, ["gpu.render"], cwd=h.repo, state_dir=h.state, where="prerequisite: ")
        ctx.check(f"one line naming the capability and why, got {got}",
                  got == ["prerequisite: capability gpu.render is not available here: no GPU here"])
        from halo_harness.peers.catalog import save
        save(dict(NO_GPU, hardware={"os": "linux", "gpu": [{"name": "RTX 4090"}], "ram_gb": 64}), h.state)
        ctx.check("with a GPU in the catalog it passes", capability_problems(wf, ["gpu.render"], cwd=h.repo, state_dir=h.state) == [])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="capability checks in core"))
