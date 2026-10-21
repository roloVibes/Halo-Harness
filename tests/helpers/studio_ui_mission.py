"""tests.helpers.studio_ui_mission -- the Fleet Mission checks of
tests/test_studio_ui.py (Halo 3.0.6.0 round R8), kept here so that file
stays small. One headless Chrome run (`python -m tests.helpers.studio_fleet
mission`, tests/helpers/studio_fleet_mission.py) over the Studio Fleet rig
and the seeded fakes (tests/helpers/studio_fleet_mseed.py: no model call);
the runner caches it, so the four tests read one run."""
from __future__ import annotations

from tests.helpers.runner import Ctx, SkipTest

ARGS = ("-m", "tests.helpers.studio_fleet", "mission")


def register(test, json_of, chrome) -> None:
    @test
    def test_fleet_mission_plan_draws_on_the_map_in_headless_chrome(ctx: Ctx):
        """3.0.6.0 R8: with no mission yet the Mission panel shows its five lines on
        how it works; a goal typed and Plan it (the fake lead) draws three part
        nodes on the map, each inside its harness box (gridcraft's part on
        kali@lab, ComfyUI's on you@studio, both locked), one depends_on edge
        and one sequenced edge with its chip, dashed while planned; the table
        has three rows and Attention a mission_plan row."""
        if not chrome():
            raise SkipTest("no Chrome found (the Mission test needs headless Chrome)")
        r, got = json_of(*ARGS)
        ctx.check(f"the run finished, got {r.stdout[-300:]!r} {r.stderr[-800:]!r}", r.returncode == 0)
        ctx.check(f"the about line and how it works, got {got.get('about')!r} / {got.get('how')}",
                  "One goal for the whole fleet" in str(got.get("about")) and got.get("how") == 5 and got.get("prefer_on") == "true")
        placed = got.get("placed") or {}
        ctx.check(f"three parts, each inside its harness box, got {placed} / {got.get('inside')}",
                  got.get("nodes") == 3 and sorted(got.get("inside") or []) == ["1:in", "2:in", "3:in"]
                  and placed.get("1") == placed.get("3") and placed.get("1", "").startswith("c0ffee") and placed.get("2") != placed.get("1"))
        ctx.check(f"one depends_on edge, one sequenced edge with its chip, two locks, got {got.get('edges')} / {got.get('seq_chips')} / {got.get('locks')}",
                  got.get("edges") == ["depends:2>3", "sequenced:1>3"] and got.get("seq_chips") == 1 and got.get("locks") == 2)
        ctx.check(f"dashed while planned, got {got.get('planned_dashed')!r}", str(got.get("planned_dashed")) not in ("", "none"))
        bases, mb = got.get("part_bases") or {}, str(got.get("mission_base") or "")
        ctx.check(f"3.0.9.0: the depends_on edge's chip names what it hands on, got {got.get('edge_labels')}",
                  got.get("edge_labels") == ["2>3:cover.png"])
        ctx.check(f"3.0.9.0: each repo part shows its base, got {bases} (mission base {mb[:7]!r})",
                  len(mb) >= 7 and bases.get("1") == f"base {mb[:7]}" and bases.get("2") == "" and bases.get("3") == "base: 1's head")
        ctx.check(f"the table and the attention row, got {got.get('table_rows')} / {got.get('plan_row')!r}",
                  got.get("table_rows") == 3 and "waits for your approval" in str(got.get("plan_row")))

    @test
    def test_fleet_mission_drag_reassigns_and_a_422_snaps_back(ctx: Ctx):
        """3.0.6.0 R8: dragging part 3 into this harness's box posts the reassign:
        the node moves there (still inside its box) and the route has it; dragging
        part 1, which needs gridcraft, there answers 422: the toast says why and
        the node snaps back into kali@lab's box."""
        if not chrome():
            raise SkipTest("no Chrome found (the Mission test needs headless Chrome)")
        r, got = json_of(*ARGS)
        ctx.check(f"the run finished, got {r.stderr[-300:]!r}", r.returncode == 0)
        ctx.check(f"the drag moved part 3, got {got.get('moved')} / {got.get('moved_api')!r} / {got.get('moved_inside')}",
                  got.get("moved") == "moved" and got.get("moved_api") == "you@studio" and sorted(got.get("moved_inside") or []) == ["1:in", "2:in", "3:in"])
        ctx.check(f"a 422 snaps back with the reason, got {got.get('refused_toast')!r} / {got.get('snapped')}",
                  "does not have gridcraft" in str(got.get("refused_toast")) and got.get("snapped") == "back"
                  and sorted(got.get("snapped_inside") or []) == ["1:in", "2:in", "3:in"])

    @test
    def test_fleet_mission_approve_run_and_the_asks_in_headless_chrome(ctx: Ctx):
        """3.0.6.0 R8: Approve, then Run: the Running face shows part 1 waiting on
        kali@lab's owner (asked, its node amber) and part 2 running here (solid);
        Attention lists the member's control ask; another hub's run_task on this
        harness opens a mission_ask row with the card's text, O opens the Mission
        panel on that mission, R denies it; when the member's owner allows, part 1
        runs with its agent's line, the rail shows the mission chips, the status
        bar counts one mission, and "Open the part's agent" selects it."""
        if not chrome():
            raise SkipTest("no Chrome found (the Mission test needs headless Chrome)")
        r, got = json_of(*ARGS)
        ctx.check(f"the run finished, got {r.stderr[-300:]!r}", r.returncode == 0)
        ctx.check(f"approved, then the run face, got {got.get('approved')} / {got.get('run_face')}",
                  got.get("approved") == "approved" and got.get("run_face") == "run")
        ctx.check(f"asked and running, got {got.get('asked')!r} / {got.get('node_states')} / {got.get('running_solid')!r}",
                  got.get("asked") == "waiting on kali@lab's owner to allow it" and got.get("local_running") == "running"
                  and (got.get("node_states") or {}).get("1") == "asked" and (got.get("node_states") or {}).get("2") == "running"
                  and got.get("running_solid") == "none")
        ctx.check(f"the member's control ask, got {got.get('control_row')!r}", "run_task waits on kali@lab's owner" in str(got.get("control_row")))
        ctx.check(f"the mission_ask row, O and R, got {got.get('ask_row')!r} / {got.get('ask_open')} / {got.get('ask_denied')}",
                  "asks to run mission m-20261015-0b5e part 2 here" in str(got.get("ask_row")) and got.get("ask_open") == "not here"
                  and got.get("ask_denied") == "refused" and got.get("ask_gone") == "gone" and got.get("reopened") == "run")
        ctx.check(f"allowed: its agent's line, the rail chips, the status bar, got {got.get('member_line')!r} / {got.get('rail_chips')} / {got.get('status_missions')!r}",
                  got.get("allowed") is True and got.get("member_line") == "gridcraft: write_range B2:D9" and got.get("rail_chips") == 2
                  and "1 mission" in str(got.get("status_missions")))
        ctx.check(f"Open the part's agent selects it, got {got.get('agent_opened')!r}",
                  str(got.get("agent_opened")).startswith("c0ffee") and "|5e55" in str(got.get("agent_opened")) and got.get("local_done") == "done")

    @test
    def test_fleet_mission_stop_and_the_report_in_headless_chrome(ctx: Ctx):
        """3.0.6.0 R8: Stop asks first, with a reason; the mission ends stopped (the
        member's part is stopped like any agent), the panel turns to the report,
        which lists the cost per harness, and the status bar no longer counts it."""
        if not chrome():
            raise SkipTest("no Chrome found (the Mission test needs headless Chrome)")
        r, got = json_of(*ARGS)
        ctx.check(f"the run finished, got {r.stderr[-300:]!r}", r.returncode == 0)
        ctx.check(f"Stop asks, then the mission is stopped, got {got.get('stop_asks')!r} / {got.get('stopped')} / {got.get('agent_stop_sent')}",
                  got.get("stop_asks") == "Stop the mission?" and got.get("stopped") == "stopped" and got.get("agent_stop_sent") == ["main"])
        rows = got.get("report_harnesses") or []
        ctx.check(f"the report lists the cost per harness, got {rows} / {got.get('report_total')!r}",
                  got.get("report_face") == "report" and len(rows) == 2 and any(x.startswith("you@studio|") and x.endswith("$0.042") for x in rows)
                  and any(x.startswith("kali@lab|") for x in rows) and got.get("report_total") == "$0.043")
        ctx.check(f"the status bar stops counting it, got {got.get('after_stop_status')}", got.get("after_stop_status") == "none")
