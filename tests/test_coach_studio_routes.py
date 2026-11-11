"""tests.test_coach_studio_routes -- the coach's Studio routes, the coach pack's since 3.4.0.0 B2
(`/api/packs/coach/coach/...`, server/routes.py over server/coach_api.py), moved here from
test_studio_orchestra_api.py (an Orchestra run's card and its probe) and test_fleet_mission_api.py (a mission's card),
with the pack enabled in each Studio's home. Run: python -m tests.test_coach_studio_routes
"""

from __future__ import annotations

import sys
import threading  # noqa: F401  (the moved probe test's helpers use it)
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once  # noqa: E402

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()
import tests.helpers.coach_names  # noqa: E402,F401  (the coach pack's modules under their old names)
from tests.helpers import coach_pack as CP  # noqa: E402
from tests.helpers import orchestra_studio_rig as R  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
C = "packs/coach/coach/"


@test
def test_the_coach_route_reads_the_run_and_keeps_its_card(ctx: Ctx):
    """3.0.9.0 R3: GET orchestra/<run>/coach -> the coach's result (orchestra/coach.py), computed once and kept in
    <run>/coach.json; the R2 run's judged conflict (lane 5 with lane 4) is a structure card. 3.1.6.0 R2: POST .../probe
    shows the cost line, then runs on a thread beside the console (feed frames, 409 while it runs), its card leads."""
    repo, run_dir = R.finished_run()
    try:
        with R.Studio(repo) as s:
            CP.enable(s.state, cwd=repo)  # 3.4.0.0 B2: the coach pack's routes
            st, data = s.get(f"{C}orchestra/{run_dir.name}/coach")
            ctx.check(f"200 and the shape, got {st} {sorted(data)}", st == 200 and data["kind"] == "orchestra"
                      and data["run"] == run_dir.name and data["cached"] is False and data["model"] is False)
            ids = [x["id"] for x in data["suggestions"]]
            ctx.check(f"the judged conflict, got {ids}", "structure-5-after-4" in ids)
            ctx.check("kept in coach.json", (run_dir / "coach.json").is_file())
            st, again = s.get(f"{C}orchestra/{run_dir.name}/coach")
            ctx.check("the second read is the kept card", st == 200 and again["cached"] is True
                      and again["suggestions"] == data["suggestions"])
            ctx.check("an unknown run is a 404", s.get(f"{C}orchestra/nope/coach")[0] == 404)
            ctx.check("POST is a 405", s.post(f"{C}orchestra/{run_dir.name}/coach", {})[0] == 405)
            from tests.helpers.coach_probe_rig import studio_probe  # 3.1.6.0 R2: POST <coach>/probe
            got = studio_probe(s, run_dir)
            ctx.check(f"probe: the cost line first, nothing run, got {got['cost']}", got["cost"][0] == 200 and got["nothing_ran"]
                      and got["cost"][1]["estimate"]["line"].startswith("probe: 2 runs, up to $0.0345"))
            ctx.check(f"confirm: 202 on a thread, a 409 while it runs, got {got['start']} {got['again'][0]} {got['live']}",
                      got["start"][0] == 202 and got["again"][0] == 409 and got["live"] is True)
            f = got["frame"] or {}
            ctx.check(f"its step lines as orchestra_state frames naming no console run, got {f}", f.get("session_id") ==
                      f"coach-probe:{run_dir.name}" and "run" not in (f.get("data") or {}) and got["done"] is not None)
            card = got["coach"]["suggestions"][0]
            ctx.check(f"the probe's card leads, one run listed, got {card['kind']} {got['coach']['probe']} {len(got['runs'])}",
                      card["kind"] == "probe" and got["coach"]["probe"]["state"] == "done" and len(got["runs"]) == 1)
    finally:
        R.cleanup(repo)


@test
def test_the_mission_coach_route(ctx: Ctx):
    """3.0.9.0 R3: GET fleet/missions/<id>/coach -> the coach's card for a mission folder of this harness
    (a part asked longer than the median part, a refused edit, a judged conflict); 404 for an unknown one."""
    from tests.helpers.coach_seed import mission_folder
    from tests.test_studio_api import _Studio
    with _Studio() as s:
        folder = mission_folder(s.state)
        CP.enable(s.state)  # 3.4.0.0 B2: the coach pack's routes
        status, data, _ = s.call("GET", f"/api/packs/coach/coach/fleet/missions/{folder.name}/coach")
        ids = [x["id"] for x in data.get("suggestions") or []]
        ctx.check(f"200, the mission's cards, got {status} {ids}", status == 200 and data["kind"] == "mission"
                  and {"coordination-2-asked", "tools-3-claim-README.md", "structure-3-after-1"} <= set(ids))
        ctx.check("kept in the mission folder", (folder / "coach.json").is_file())
        ctx.check("an unknown mission is a 404", s.call("GET", "/api/packs/coach/coach/fleet/missions/m-20261017-ffff/coach")[0] == 404)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="coach studio route tests"))
