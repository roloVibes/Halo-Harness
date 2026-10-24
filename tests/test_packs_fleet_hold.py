"""tests.test_packs_fleet_hold -- the hub holds what a pack declares (Halo
3.2.1.0 R3, fleet/mission_hold.py, mission_run.py, mission_dispatch.py,
packs/fleet_share.py, docs/FLEET.md "Missions"):

1. capacity: three parts need docs.review (capacity.parallel 2) on one
   harness: two run, the third is `waiting` with the one log line ("part 3
   waits: <harness> runs 2/2 of pack doc-review: docs.review") and starts
   when one ends; a part with no pack need is never held and carries no
   `holds` or `waiting`; the planner reads "2 at a time";
2. over two homes (tests/helpers/fleet_hub_rig.py): the member advertises
   docs.review and runs doc-review without bash, the hub runs it with bash:
   the member refuses part 1 with the one line, the hub re-plans it once onto
   itself (the log, the decisions, plan.json and MISSION.md say so), it runs
   there and the mission is done; when the hub refuses it too, the part
   fails with the line and is not re-planned a second time;
3. an inspector line carries its file's text to the hub: inside the pack,
   a markdown or JSON file, the first 8 KB (cut says so), paths scrubbed;
   the capabilities command's answer and the hub's copy keep it.

Run: python -m tests.test_packs_fleet_hold
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402

ensure_default_provider_credentials()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
from tests.helpers.packs_home import DOC_REVIEW, PacksHome  # noqa: E402
from tests.test_packs_fleet_missions import LINE, _install_on_b, _packs  # noqa: E402

TOOLS_ROW = {"ref": "or:anthropic/claude-sonnet-4.6", "provider": "openrouter", "tools": True}


def _part(pid: str, needs: list, **kw) -> dict:
    return {"id": pid, "title": f"Review set {pid}", "brief": f"Review the docs of set {pid}.", "kind": "files",
            "needs": needs, "outputs": [f"review-{pid}.md"], "est_cost_usd": 0.1, **kw}


@test
def test_capacity_two_runs_two_then_the_third(ctx: Ctx):
    from halo_harness.fleet import capabilities as caps
    from halo_harness.fleet import identity, mission_api as A, mission_store as S, mission_worker as W
    from halo_harness.fleet.mission_doc import status_table
    from halo_harness.fleet.mission_plan import pack_line
    from halo_harness.theme import set_config_value
    from tests.helpers.fleet_hub_rig import wait_for
    from tests.helpers.mission_seed import FakeLead, gate, wait_state, worker
    with PacksHome() as h:
        h.catalog([TOOLS_ROW])
        h.install(h.source(), enable=True, grants=["bash"])
        set_config_value("fleet.mission.max_parallel", 3)
        identity.forget_cache()
        cat, _changed = caps.refresh(h.state, cwd=h.repo)
        ctx.check(f"the planner reads it, got {pack_line(cat)!r}", pack_line(cat) == "pack caps: docs.review (pack doc-review, 2 at a time)")
        started, holds = [], {p: gate() for p in "123"}
        A.LEAD = FakeLead(json.dumps({"parts": [_part("1", ["docs.review"]), _part("2", ["docs.review"]),
                                                _part("3", ["docs.review"]), _part("4", [])], "merge_order": []}))
        W.BUILD = worker({}, started, holds)
        try:
            mctx = A.Ctx(h.state, None, by="me")
            status, body = A.create(mctx, {"goal": "Review four sets of docs", "repo": False})
            mid = body["mission"]["id"]
            name = body["plan"]["parts"][0]["harness_name"]
            A.run(mctx, mid, force=True)
            states = lambda: [S.need(h.state, mid)["parts"][p]["state"] for p in "1234"]  # noqa: E731
            got = wait_for(lambda: states() if states() == ["running", "running", "waiting", "done"] else None, 30)
            ctx.check(f"two run, the third waits, the part with no pack need is not held, got {states()}", bool(got))
            line = f"part 3 waits: {name} runs 2/2 of pack doc-review: docs.review"
            p3 = S.need(h.state, mid)["parts"]["3"]
            ctx.check(f"the waits line, in the log once and on the part, got {p3.get('waiting')!r}", p3.get("waiting") == line
                      and [r.get("text") for r in S.read_log(h.state, mid, ("waits",))] == [line])
            table = status_table(S.need(h.state, mid))
            ctx.check(f"`halo fleet mission status` shows it, got {table!r}", f"part  3  waiting   $0.0000  {line}" in table)
            holds["1"].set()
            ctx.check("a slot frees: the third starts", bool(wait_for(lambda: S.need(h.state, mid)["parts"]["3"]["state"] == "running", 30)))
            for g in holds.values():
                g.set()
            doc = wait_state(h.state, mid, ("done", "failed", "stopped"), 40)
            p3, p4 = doc["parts"]["3"], doc["parts"]["4"]
            ctx.check(f"the mission is done, got {doc['state']} {doc.get('stop_reason')}", doc["state"] == "done")
            ctx.check(f"3 started after 1 ended, holding the capability, got {started} {p3}", [p for p, _t in started][-1] == "3"
                      and p3.get("holds") == ["doc-review/docs.review"] and p3.get("waiting") is None)
            ctx.check(f"nothing changes for a part with no pack need, got {p4}", "holds" not in p4 and "waiting" not in p4)
        finally:
            A.LEAD = None
            W.BUILD = None


def _install_on_a(rig, grants=("bash",)) -> None:
    from halo_harness.packs.discover import find
    from halo_harness.packs.grants import enable
    from halo_harness.packs.install import install
    src = Path(tempfile.mkdtemp(prefix="r3-src-")) / "doc-review"
    shutil.copytree(DOC_REVIEW, src, ignore=shutil.ignore_patterns("__pycache__"))
    ok, lines = install(str(src), cwd=rig.root_a, state_dir=rig.home_a)
    assert ok, lines
    ok, lines = enable(find("doc-review", cwd=rig.root_a, state_dir=rig.home_a), grant=list(grants), state_dir=rig.home_a)
    assert ok, lines


@test
def test_a_refused_part_moves_once_to_a_harness_that_has_it(ctx: Ctx):
    from halo_harness.config.paths import bridge_home
    from halo_harness.fleet.identity import harness
    from tests.helpers.fleet_caps_seed import seed
    from tests.helpers.fleet_hub_rig import HubRig, wait_for
    from tests.helpers.mission_seed import kali_box, mission_ctx, reset_fakes, windows_host
    with HubRig() as rig:
        _install_on_b(rig.root_b)  # bash not granted on the member
        _install_on_a(rig)  # the hub runs doc-review with bash
        seed(rig.home_a, {**windows_host(rig.hub.state.identity), "packs": _packs(True)})
        seed(bridge_home(), {**kali_box(harness()), "packs": _packs(True)})  # what it advertised before the grant went
        rig.set_b(**{"fleet.allow_control": "all"})
        rig.join()
        rig.session()
        wait_for(lambda: rig.hub.state.caps.catalogs.get(rig.b_id), 20.0)
        answer = json.dumps({"parts": [_part("1", ["docs.review"], harness="bob@member", reason="the lead's pick"),
                                       _part("2", [], harness="alice@hub", depends_on=["1"])], "merge_order": []})
        started: list = []
        A, mctx = mission_ctx(rig, answer, {}, started)
        try:
            _replan_runs(ctx, rig, A, mctx, started)
        finally:
            reset_fakes()


def _replan_runs(ctx: Ctx, rig, A, mctx, started: list) -> None:
    from halo_harness.fleet import mission_store as S
    from halo_harness.fleet.mission_plan import load_plan
    from halo_harness.packs.grants import disable
    from tests.helpers.fleet_caps_seed import seed
    from tests.helpers.fleet_hub_rig import wait_for
    from tests.helpers.mission_seed import wait_state, windows_host
    status, body = A.create(mctx, {"goal": "Review the docs and sum it up", "repo": False})
    mid = body["mission"]["id"]
    ctx.check(f"planned on the member (the lead's pick, both have it), got {body['plan']['parts'][0].get('harness')}",
              status == 200 and body["plan"]["parts"][0]["harness"] == rig.b_id)
    A.run(mctx, mid)
    doc = wait_state(rig.home_a, mid, ("done", "failed", "stopped"), 60)
    said = f"part 1 replanned: bob@member refused ({LINE}); alice@hub has pack doc-review: docs.review"
    p1 = doc["parts"]["1"]
    ctx.check(f"re-planned onto the hub, run there, the mission done, got {doc['state']} {p1} {doc.get('stop_reason')}",
              doc["state"] == "done" and p1["state"] == "done" and p1["harness"] == rig.a_id and p1.get("replanned") == said)
    log = [r.get("text") for r in S.read_log(rig.home_a, mid, ("replanned", "replan"))]
    from halo_harness.fleet.mission_doc import status_table
    ctx.check(f"the log says it once, with the reason, and the status table, got {log}", log == [said]
              and "      part 1 replanned: bob@member refused (this harness does not run pack" in status_table(doc))
    part = load_plan(rig.home_a, mid)["parts"][0]
    brief = (S.folder(rig.home_a, mid) / "parts" / "1" / "brief.md").read_text(encoding="utf-8")
    ctx.check(f"plan.json and the part's brief moved it, got {part.get('harness')} {part.get('reason')!r}", part["harness"] == rig.a_id
              and part["reason"] == said and "fleet mission on alice@hub" in brief)
    report = wait_for(lambda: (S.folder(rig.home_a, mid) / "report.md").read_text(encoding="utf-8"), 15) or ""
    ctx.check("the decisions and the report say it", any(d.get("what") == said for d in doc.get("decisions") or []) and said in report)
    ctx.check(f"both parts ran on the hub, the member's worker never started, got {started}", [p for p, _t in started] == ["1", "2"])
    disable("doc-review", state_dir=rig.home_a)  # the hub's catalog still says it has it: it refuses too
    seed(rig.home_a, {**windows_host(rig.hub.state.identity), "packs": _packs(True)})
    status, body = A.create(mctx, {"goal": "Review the docs again", "repo": False})
    mid = body["mission"]["id"]
    A.run(mctx, mid)
    doc = wait_state(rig.home_a, mid, ("done", "failed", "stopped"), 60)
    p1 = doc["parts"]["1"]
    log = [r.get("text") for r in S.read_log(rig.home_a, mid, ("replanned", "replan"))]
    ctx.check(f"refused again on the hub: failed with its line, re-planned once only, got {p1} {log}", p1["state"] == "failed"
              and p1["error"] == LINE and p1["harness"] == rig.a_id and len(log) == 1 and log[0].startswith("part 1 replanned: bob@member"))


NOTES_PACK = """id: notes-pack
name: Notes for the fleet
version: 0.1.0
halo_api: {min: "1.0"}
capabilities: [notes.write]
contributes:
  fleet:
    capabilities:
      - {name: notes.write, description: Writes the release notes}
    inspector:
      - {label: Notes, source: fleet/notes.md}
      - {label: Big table, source: fleet/big.json}
"""


@test
def test_an_inspector_lines_text_reaches_the_hub(ctx: Ctx):
    from halo_harness.fleet import capabilities as caps
    from halo_harness.fleet import control
    from halo_harness.fleet.hub_capabilities import _trim
    from halo_harness.packs.fleet_share import INSPECTOR_BYTES, inspector_text
    with PacksHome() as h:
        src = h.sources / "notes-pack"
        (src / "fleet").mkdir(parents=True)
        (src / "pack.yaml").write_text(NOTES_PACK, encoding="utf-8")
        (src / "fleet" / "notes.md").write_bytes(f"# Notes\nRead {h.home / 'notes' / 'today.md'} and /home/someone/plan.md first.\n"
                                                 .encode("utf-8"))
        (src / "fleet" / "big.json").write_text(json.dumps([{"row": i, "text": "x" * 40} for i in range(400)]), encoding="utf-8")
        (src / "fleet" / "run.py").write_text("print('x')\n", encoding="utf-8")
        h.install(src, enable=True)
        lines = next(p for p in caps.gather(h.state, cwd=h.repo)["packs"] if p["id"] == "notes-pack")["inspector"]
        notes, big = lines
        ctx.check(f"a markdown file: its text, paths cut to their last part, got {notes}",
                  notes["text"] == "# Notes\nRead today.md and plan.md first.\n" and "cut" not in notes)
        ctx.check(f"a big JSON file: its first 8 KB, cut says so, got {len(big.get('text', ''))}",
                  len(big["text"]) == INSPECTOR_BYTES and big.get("cut") is True)
        root = h.state / "packs" / "notes-pack"
        ctx.check("outside the pack, another kind, or missing: no text", inspector_text(root, "../pack.yaml") == {}
                  and inspector_text(root, "fleet/run.py") == {} and inspector_text(root, "fleet/gone.md") == {}
                  and inspector_text(root, str(root / "fleet" / "notes.md")) == {})
        handle = SimpleNamespace(session=SimpleNamespace(), _note=lambda _m: None, kind="tui", controller=None)
        got = control.run(handle, {"cmd": "capabilities", "fields": {}}, {"share": "full", "allow_control": "none", "allow_answers": False})
        sent = next(p for p in got["result"]["packs"] if p["id"] == "notes-pack")["inspector"]
        ctx.check("the capabilities command's answer carries it", sent[0]["text"] == notes["text"] and sent[1].get("cut") is True)
        kept = _trim({"packs": [{"id": "notes-pack", "inspector": [{"label": "x", "source": "a.md", "text": "y" * 20000}]}]})
        ctx.check("the hub's copy keeps 8 KB of a longer one", len(kept["packs"][0]["inspector"][0]["text"]) == INSPECTOR_BYTES
                  and kept["packs"][0]["inspector"][0]["cut"] is True and _trim(got["result"])["packs"] == got["result"]["packs"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
