"""tests.test_capability_check_core -- a pack's capability checks are core's own (Halo 3.4.0.0 D, item 7; 3.5.0.0:
`contributes.capabilities`).

The capability checker is halo_harness/packs/capability_check.py over halo_harness/peers/needs.py and
halo_harness/peers/projects.py: a pack workflow's capability `requires` is checked and a pack declaring capabilities
shows its rows.
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
    h.install(h.source("caps-needs-gpu"), enable=True)
    from halo_harness.packs.discover import find
    return find("caps-needs-gpu", cwd=h.repo)


@test
def test_the_checker_is_core(ctx: Ctx):
    from halo_harness.peers.needs import has, norm_need
    ctx.check("has() answers in core", has({"clis": {"git": "2.45"}}, "cli:git") == "git 2.45 (CLI)" and norm_need("  GPU  x ") == "gpu x")
    import halo_harness.packs.capability_check as reg
    ctx.check(f"the registry is core's own module, got {reg.__file__}", "templates" not in Path(reg.__file__).parts)


@test
def test_a_pack_declaring_capabilities_shows_its_rows(ctx: Ctx):
    with PacksHome() as h:
        pack = _home(h)
        from halo_harness.packs.contrib_views import contributes, doctor_rows
        got = contributes(pack, [], running=True, cwd=h.repo, state_dir=h.state)["capabilities"]
        ctx.check(f"the capabilities part is listed, got {got}", got is not None)
        caps = {c["name"]: c for c in (got or {}).get("capabilities") or []}
        gpu = caps.get("gpu.render") or {}
        ctx.check(f"gpu.render: not available, why = no GPU here, got {gpu}", gpu.get("available") is False and gpu.get("why") == "no GPU here")
        rows = doctor_rows(pack, [], cwd=h.repo, state_dir=h.state)
        ctx.check(f"halo pack doctor's row says so, got {rows}", any("gpu.render" in str(r) for r in rows))


@test
def test_a_workflow_needing_a_missing_capability_is_refused(ctx: Ctx):
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
