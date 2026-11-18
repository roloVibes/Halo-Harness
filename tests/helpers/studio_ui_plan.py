"""tests.helpers.studio_ui_plan -- a goal run on Agents -> 3 · Map (3.6.0.0 R5; Live before), checks of tests/test_studio_ui.py (Halo 3.0.9.0 round R2's
plan canvas; 3.4.0.0 D "the runs fold": Runs' console went, a goal run is a job on Live and its report a page of
History; 3.6.0.3 B: its report is its own page of the Map's drawer, History's row still opens it), kept here so that file stays small. One headless Chrome run (`python -m tests.helpers.studio_plan`,
tests/helpers/studio_plan.py) over a Studio on a temp git repo with the R2 fakes (no model call); the runner caches it,
so the tests read one run."""
from __future__ import annotations

from tests.helpers.runner import Ctx, SkipTest

ARGS = ("-m", "tests.helpers.studio_plan")


def register(test, json_of, chrome) -> None:
    def run(ctx: Ctx) -> dict:
        if not chrome():
            raise SkipTest("no Chrome found (the goal run test needs headless Chrome)")
        r, got = json_of(*ARGS)
        ctx.check(f"the run finished, got {r.stdout[-300:]!r} {r.stderr[-600:]!r}", r.returncode == 0 and "failed" not in got)
        return got

    @test
    def test_orchestra_plan_canvas_draws_the_planned_lanes_in_headless_chrome(ctx: Ctx):
        """3.6.0.0 R5: a review run is the Map's line "A goal run is going", nothing open until Open and Review the plan; then the plan beside the canvas: five lanes in two layer boxes (lane 2 takes lane 1's summary), one edge
        with its `summary` chip; 3.1.2.0 R2: each card's cost chip and the header's forecast total, red over the budget."""
        got = run(ctx)
        ctx.check(f"the Map's line says the run, nothing open, got {got.get('lead_waits')} / {got.get('nothing_open')}",
                  got.get("lead_waits") == "waits" and got.get("nothing_open") is True)
        ctx.check(f"the canvas, got {got.get('canvas')}", got.get("canvas") == {"orchestra-plan": 1, "plan-canvas": 1, "plan-lane": 5,
                                                                             "plan-edge": 1, "plan-approve": 1, "orchestra-root": 0})
        ctx.check(f"two layers, the chip, lane 2 below, got {got.get('layers')} / {got.get('edge_label')} / {got.get('lane2_layer')}",
                  got.get("layers") == "2" and got.get("edge_label") == "summary" and got.get("lane2_layer") == "1")
        ctx.check(f"3.1.2.0 R2: a priced cost chip per lane, the total over the budget in the header, got "
                  f"{got.get('cost_chips')} / {got.get('cost_chip')!r} / {got.get('forecast')!r} / {got.get('forecast_over')!r}",
                  got.get("cost_chips") == 5 and str(got.get("cost_chip") or "").startswith("$")
                  and "of $0.0001 · over budget" in str(got.get("forecast")) and got.get("forecast_over") == "true")

    @test
    def test_orchestra_plan_drag_sets_after_and_a_problem_holds_approve(ctx: Ctx):
        """3.0.9.0 R2: dragging lane 3 into the second box makes it run after the first box's lanes
        (the edges draw, the draft saves it); a claim of lane 5's added to lane 4 outlines both
        cards in red, lists the problem and disables Approve and run (its title names it); Undo clears it."""
        got = run(ctx)
        ctx.check(f"the drag, got {got.get('lane3_layer')} / {got.get('edges_after_drag')} / {got.get('after_saved')}",
                  got.get("lane3_layer") == "1" and got.get("edges_after_drag") == 4 and got.get("edge_job1_job3") is True
                  and got.get("after_saved") == ["job-1", "job-4", "job-5"])
        ctx.check(f"the problem, got {got.get('problem')!r} / {got.get('red_cards')}",
                  "job-4 and job-5 both claim basket.py#total" in str(got.get("problem")) and got.get("red_cards") == ["job-4", "job-5"])
        ctx.check(f"Approve is held and names it, got {got.get('approve_disabled')} / {got.get('approve_names')!r}",
                  got.get("approve_disabled") is True and "Fix 1 problem first" in str(got.get("approve_names")))
        ctx.check("Undo clears it", got.get("undo_clears") == "clear")

    @test
    def test_a_goal_run_on_the_map_offers_its_own_report_page_when_it_ends(ctx: Ctx):
        """3.6.0.0 R5: Approve and run closes the plan; the run's pages (the Map's drawer) offer Stop the run while it
        runs; released, it finishes and leaves the Map's line; its report (eight checks, five lanes; no Replay: 3.6.0.3 B
        Z4 batch 4) is reached by its own door (3.6.0.3 B: History left). (The lanes as boxes under a lead went with Live.) L-B2: it
        ends with its page open: the page stays, its actions row holds still and offers "Open its report" where Stop
        was, no word names History; the press opens `report:<id>` ("Goal run"), whose Back returns to the run's page."""
        got = run(ctx)
        ctx.check(f"approved: the plan closed, its pages say it runs, got {got.get('plan_closed')} / {got.get('running')}",
                  got.get("running") == "running" and got.get("plan_closed") == "closed")
        page = str(got.get("run_page") or "")
        rid = page[4:] if page.startswith("run:") else ""
        ctx.check(f"it ended with its page open: the page stays, 'Open its report' first in the row, got {page!r} -> "
                  f"{got.get('ended_page')!r} / {got.get('ended_offer')!r} / first {got.get('ended_first')!r}",
                  bool(rid) and got.get("ended_page") == page and got.get("ended_offer") == "Open its report" and got.get("ended_first") is True)
        ctx.check(f"the actions row holds still, got {got.get('acts_live')} -> {got.get('acts_ended')}",
                  got.get("acts_live") is not None and got.get("acts_live") == got.get("acts_ended"))
        ctx.check(f"no word of the ended page names History, got {str(got.get('ended_words'))[:300]!r}",
                  "history" not in str(got.get("ended_words")).lower())
        ctx.check(f"his press opens report:<id>, 'Goal run', got {got.get('opened')}",
                  got.get("opened") == {"page": f"report:{rid}", "run": rid, "title": "Goal run"})
        ctx.check(f"the report's Back returns to the run's page, got {got.get('back_to')!r}", bool(rid) and got.get("back_to") == page)
        bars = [got.get("bar_live"), got.get("bar_ended"), got.get("bar_report")]
        ctx.check(f"the view bar's drawer button holds still on run:<id> (live, ended) and report:<id>, got {bars}",
                  bars[0] is not None and all(b == bars[0] for b in bars))
        ctx.check(f"finished, it left the Map's line; its report by its own door, got {got.get('left_live')} / {got.get('report')}",
                  got.get("left_live") == "gone" and got.get("report") == {"checks": 8, "lanes": 5, "replay": False}
                  and (got.get("first_report") or {}).get("status") == "finished")

    @test
    def test_orchestra_plan_approve_runs_and_reject_stops_in_headless_chrome(ctx: Ctx):
        """3.6.0.0 R5: a run started from the Map's Run a goal panel (the form says what it does, may cost and writes) with
        Review the plan first on closes the panel and waits on you; rejected with a reason on the card, it stops with it
        and leaves the Map's line."""
        got = run(ctx)
        ctx.check(f"the form says what, cost, writes, got {got.get('says')}", got.get("says") == ["WHAT IT DOES", "WHAT IT MAY COST", "WHERE IT WRITES"])
        ctx.check(f"rejected, got {got.get('review_on')} / {got.get('drawer_closed')} / {got.get('stopped')} / {got.get('stop_reason')!r}",
                  got.get("review_on") is True and got.get("drawer_closed") == "closed" and got.get("stopped") == "stopped"
                  and got.get("stop_reason") == "the plan was rejected: one lane per file instead")
