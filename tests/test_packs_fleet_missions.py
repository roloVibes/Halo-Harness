"""tests.test_packs_fleet_missions -- missions reason with the packs' fleet
capabilities (Halo 3.2.0.0 R4, fleet/mission_assign.py, mission_plan.py,
mission_worker.pack_check, packs/fleet_registry.refusal):

1. `has` / `able` / `assign` with a pack capability on one of two harnesses:
   the part is pinned there ("pack doc-review: docs.review") with its
   `pack_needs`; one available nowhere is unassignable with the old wording;
2. the planner's block lists each harness's pack capabilities and "only one
   harness has" includes them;
3. the worker checks its own packs before a part runs: pack disabled, grant
   missing, no such pack -- one line each, the same in `start_local` and in
   the fleet command (refused before the owner is asked);
4. over two homes (tests/helpers/fleet_hub_rig.py): the member advertises
   docs.review, but runs doc-review without bash: its part is refused with
   the one line, its dependant is skipped, the mission fails with the line,
   the member's worker never started; a mission started with the pack's
   lineup carries its metadata.

Run: python -m tests.test_packs_fleet_missions
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402

ensure_default_provider_credentials()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
from tests.helpers.packs_home import DOC_REVIEW  # noqa: E402  (3.2.0.0 R6: the shipped reference pack)
LINE = "this harness does not run pack doc-review with bash"


def _packs(available: bool = True, gpu: bool = False) -> list:
    caps = [{"name": "docs.review", "description": "Reviews docs", "available": available, "capacity": {"parallel": 2},
             "why": "tools: or:x; bash granted" if available else "bash not granted"}]
    caps += [{"name": "gpu.render", "description": "Renders", "available": gpu, "why": "no GPU here", "capacity": {}}]
    return [{"id": "doc-review", "name": "Documentation Review", "version": "1.0.0", "capabilities": caps,
             "inspector": [{"label": "Review checklist", "source": "fleet/checklist.md"}], "metadata": {}}]


def _entries() -> list:
    from tests.helpers.mission_seed import kali_box, windows_host
    a = {"id": "hid-a", "name": "alice@hub"}
    b = {"id": "hid-b", "name": "bob@member"}
    return [{"harness": "hid-a", "name": "alice@hub", "local": True, "catalog": {**windows_host(a), "packs": _packs(False)}},
            {"harness": "hid-b", "name": "bob@member", "catalog": {**kali_box(b), "packs": _packs(True)}}]


@test
def test_has_able_assign_with_a_pack_capability_on_one_of_two(ctx: Ctx):
    from halo_harness.fleet.mission_assign import able, assign, has
    entries = _entries()
    a, b = entries[0]["catalog"], entries[1]["catalog"]
    ctx.check(f"has: where it is available, with the pack, got {has(b, 'docs.review')!r}", has(b, "docs.review") == "pack doc-review: docs.review")
    ctx.check("pack: narrows it", has(b, "pack:docs.review") == "pack doc-review: docs.review" and has(b, "skill:docs.review") is None)
    ctx.check("not where it is listed as not available", has(a, "docs.review") is None)
    ctx.check("able: the one harness", [e["name"] for e, _w in able(entries, ["docs.review"])] == ["bob@member"])
    part = assign({"id": "1", "needs": ["docs.review"], "harness": "alice@hub"}, entries, [], {})
    ctx.check(f"assign pins it there whatever the lead said, got {part}", part["harness"] == "hid-b" and part["pinned"] is True
              and part["reason"] == "only bob@member has pack doc-review: docs.review")
    ctx.check("its pack_needs", part["pack_needs"] == [{"need": "docs.review", "pack": "doc-review"}])
    part = assign({"id": "2", "needs": ["nmap", "docs.review"]}, entries, [], {})
    ctx.check("with another need of the same harness", part["harness"] == "hid-b" and part["pack_needs"] == [{"need": "docs.review", "pack": "doc-review"}])
    part = assign({"id": "3", "needs": ["gpu.render"]}, entries, [], {})
    ctx.check(f"available nowhere: unassignable, the old wording, got {part.get('unassignable')!r}",
              part["unassignable"] == "nobody in the fleet has gpu.render" and part["harness"] is None)
    part = assign({"id": "4", "needs": ["gridcraft", "docs.review"]}, entries, [], {})
    ctx.check("no one harness has both: split the part", part["unassignable"] == "no one harness has all of gridcraft, docs.review: split the part")


@test
def test_the_planner_sees_them(ctx: Ctx):
    from halo_harness.fleet.mission_assign import unique_lines
    from halo_harness.fleet.mission_plan import catalog_block, prompt
    entries = _entries()
    block = catalog_block(entries, {})
    ctx.check(f"each block lists its packs' capabilities, got {block!r}",
              "pack caps: docs.review (pack doc-review, 2 at once), gpu.render (not here: no GPU here)" in block
              and "pack caps: docs.review (not here: bash not granted), gpu.render (not here: no GPU here)" in block)
    only = unique_lines(entries)
    ctx.check(f"only one harness has: includes it, got {only}", any(ln.startswith("only bob@member has:") and "docs.review" in ln for ln in only)
              and not any("gpu.render" in ln for ln in only))
    text = prompt({"goal": "Review the docs", "repo": None}, entries, {})
    ctx.check("the prompt carries both, and names a pack capability as a need", "pack caps: docs.review (pack doc-review" in text
              and "only bob@member has:" in text and "a pack capability)" in text)
    plain = catalog_block([{**e, "catalog": {k: v for k, v in e["catalog"].items() if k != "packs"}} for e in entries], {})
    ctx.check("a fleet with no pack: no packs line", "pack caps" not in plain)


@test
def test_the_worker_checks_its_own_packs_before_a_part_runs(ctx: Ctx):
    from halo_harness.fleet import control
    from halo_harness.fleet import mission_worker as W
    from halo_harness.packs.discover import find
    from halo_harness.packs.grants import disable, enable
    from tests.helpers.packs_home import PacksHome
    with PacksHome() as h:
        h.install(h.source())

        def line(needs) -> str:
            try:
                W.pack_check({"needs": needs}, cwd=h.repo, home=h.state)
                return ""
            except W.TaskError as e:
                return str(e)
        ctx.check(f"installed, disabled: one line, got {line(['docs.review'])!r}", line(["docs.review"]) == LINE)
        enable(find("doc-review", cwd=h.repo))
        ctx.check("enabled without the grant: the same line", line(["docs.review"]) == LINE)
        enable(find("doc-review", cwd=h.repo), grant=["bash"])
        ctx.check("with the grant: it runs", line(["docs.review"]) == "" and line(["nmap", "pack:docs.review"]) == "")
        ctx.check("a pack: need no pack here declares", line(["pack:gpu.render"]) == "this harness has no pack with gpu.render")
        ctx.check("a need that is no pack's is not this check's", line(["gridcraft"]) == "")
        disable("doc-review")
        fields = {"mission": "m-20261023-0a0a", "part": "1", "title": "Review", "brief": "Review the docs.", "kind": "files",
                  "needs": ["docs.review"]}
        try:
            W.start_local(h.state, fields)
            said = ""
        except ValueError as e:
            said = str(e)
        ctx.check(f"the hub's own part: start_local refuses with it, got {said!r}", said == LINE)
        notes: list = []
        handle = SimpleNamespace(session=SimpleNamespace(), _note=notes.append, kind="tui", controller=None, cwd=h.repo)
        got = control.run(handle, {"cmd": "run_task", "fields": fields, "by": "alice@hub", "hub": "hub-a"},
                          {"share": "full", "allow_control": "ask", "allow_answers": False})
        ctx.check(f"a member's run_task: refused with the line before anyone is asked, got {got}",
                  got == {"state": "refused", "error": LINE} and notes and LINE in notes[-1])


def _install_on_b(root_b: str, grants=()) -> None:
    from halo_harness.packs.discover import find
    from halo_harness.packs.grants import enable
    from halo_harness.packs.install import install
    src = Path(tempfile.mkdtemp(prefix="r4-src-")) / "doc-review"
    shutil.copytree(DOC_REVIEW, src, ignore=shutil.ignore_patterns("__pycache__"))  # 3.2.0.0 R6: the shipped pack
    ok, lines = install(str(src), cwd=root_b)
    assert ok, lines
    ok, lines = enable(find("doc-review", cwd=root_b), grant=list(grants))
    assert ok, lines


@test
def test_a_member_refuses_the_part_and_the_mission_moves_on(ctx: Ctx):
    from halo_harness.config.paths import bridge_home
    from halo_harness.fleet import mission_store as S
    from halo_harness.fleet.identity import harness
    from tests.helpers.fleet_caps_seed import seed
    from tests.helpers.fleet_hub_rig import HubRig, wait_for
    from tests.helpers.mission_seed import kali_box, mission_ctx, reset_fakes, wait_state, windows_host
    with HubRig() as rig:
        _install_on_b(rig.root_b)  # enabled, bash not granted
        seed(rig.home_a, windows_host(rig.hub.state.identity))
        seed(bridge_home(), {**kali_box(harness()), "packs": _packs(True)})  # what it advertised before the grant went
        rig.set_b(**{"fleet.allow_control": "all"})
        rig.join()
        rig.session()
        wait_for(lambda: rig.hub.state.caps.catalogs.get(rig.b_id), 20.0)
        answer = json.dumps({"parts": [
            {"id": "1", "title": "Review the docs", "brief": "Review docs/ for dead links.", "kind": "files", "needs": ["docs.review"],
             "outputs": ["review.md"], "est_cost_usd": 0.1},
            {"id": "2", "title": "Sum it up", "brief": "One page from review.md.", "kind": "files", "needs": [], "harness": "alice@hub",
             "depends_on": ["1"], "est_cost_usd": 0.05}], "merge_order": []})
        started: list = []
        A, mctx = mission_ctx(rig, answer, {}, started)
        status, body = A.create(mctx, {"goal": "Review the docs and sum it up", "repo": False})
        plan = (body.get("plan") or {}).get("parts") or [{}]
        ctx.check(f"planned: part 1 pinned on the member by the pack capability, got {status} {plan[0]}", status == 200
                  and plan[0].get("harness") == rig.b_id and plan[0].get("pack_needs") == [{"need": "docs.review", "pack": "doc-review"}])
        mid = body["mission"]["id"]
        A.run(mctx, mid)
        doc = wait_state(rig.home_a, mid, ("done", "failed", "stopped"), 40)
        p1, p2 = doc["parts"]["1"], doc["parts"]["2"]
        ctx.check(f"the member refused it with the one line, got {p1['state']} {p1.get('error')!r}", p1["state"] == "failed" and p1["error"] == LINE)
        ctx.check(f"its dependant is skipped, got {p2['state']}", p2["state"] == "skipped")
        ctx.check(f"the mission failed with the line, got {doc['state']} {doc.get('stop_reason')!r}", doc["state"] == "failed"
                  and LINE in str(doc.get("stop_reason")))
        time.sleep(0.5)
        ctx.check(f"the member's worker never started, got {started}", started == [])
        ctx.check("the report says why", LINE in (S.folder(rig.home_a, mid) / "report.md").read_text(encoding="utf-8"))
        hubs_copy = json.dumps(rig.hub.state.caps.catalogs.get(rig.b_id) or {})
        ctx.check("the hub's copy of the member's catalog holds no local path", rig.root_b not in hubs_copy
                  and rig.root_b.replace("\\", "/") not in hubs_copy)
        reset_fakes()


@test
def test_a_mission_started_by_the_packs_lineup_carries_its_metadata(ctx: Ctx):
    from halo_harness.fleet import mission_api as A
    from halo_harness.fleet import mission_store as S
    from halo_harness.theme import set_config_value
    from tests.helpers.mission_seed import FakeLead
    from tests.helpers.packs_home import PacksHome
    with PacksHome() as h:
        h.install(h.source(), enable=True, grants=["bash"])
        A.LEAD = FakeLead(json.dumps({"parts": [{"id": "1", "title": "Review", "brief": "Review the docs.", "kind": "files",
                                                 "needs": [], "est_cost_usd": 0.1}], "merge_order": []}))
        try:
            ctx_ = A.Ctx(h.state, None, by="me")
            status, body = A.create(ctx_, {"goal": "Review the docs", "repo": False, "lineup": "doc-review--review"})
            meta = body["mission"].get("metadata")
            ctx.check(f"the lineup named: the pack's metadata, got {status} {meta}", meta == {"pack": "doc-review", "lineup": "doc-review--review",
                                                                                           "review": "docs", "style": "short"})
            md = (S.folder(h.state, body["mission"]["id"]) / "MISSION.md").read_text(encoding="utf-8")
            ctx.check("MISSION.md says it", "**Metadata:** pack=doc-review, lineup=doc-review--review, review=docs, style=short" in md)
            set_config_value("team", "doc-review--review")
            from halo_harness.fleet import identity
            identity.forget_cache()
            status, body = A.create(ctx_, {"goal": "Review again", "repo": False})
            ctx.check("the active lineup (config team) too", (body["mission"].get("metadata") or {}).get("pack") == "doc-review")
            set_config_value("team", "halo-dev-cycle")
            identity.forget_cache()
            status, body = A.create(ctx_, {"goal": "No pack", "repo": False})
            ctx.check("another lineup: no metadata key at all", "metadata" not in body["mission"])
        finally:
            A.LEAD = None


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
