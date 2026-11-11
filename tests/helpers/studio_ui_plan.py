"""tests.helpers.studio_ui_plan -- a goal run on Agents -> Live, checks of tests/test_studio_ui.py (Halo 3.0.9.0 round R2's
plan canvas; 3.4.0.0 D "the runs fold": Runs' console went, a goal run is a job on Live and its report a page of
History), kept here so that file stays small. One headless Chrome run (`python -m tests.helpers.studio_plan`,
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
        """3.4.0.0 D: a review run is its lead on Live, waiting on you (the sentence asks first), nothing open until Review
        the plan; then the plan beside the canvas: five lanes in two layer boxes (lane 2 takes lane 1's summary), one edge
        with its `summary` chip; 3.1.2.0 R2: each card's cost chip and the header's forecast total, red over the budget."""
        got = run(ctx)
        ctx.check(f"the lead waits on you, nothing open, the sentence asks, got {got.get('lead_waits')} / {got.get('nothing_open')} / {got.get('narration_asks')}",
                  got.get("lead_waits") == "waits" and got.get("nothing_open") is True and got.get("narration_asks") == "asks")
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
    def test_a_goal_run_is_a_job_on_live_and_its_report_is_in_history(ctx: Ctx):
        """3.4.0.0 D: Approve and run closes the plan; the run's five lanes are boxes in the run's block under its lead,
        a row per fact (state, model, cost, owns); a lane's click is its summary in the inspector (goal, owns, state,
        last output, cost ...) with Stop the run and its pages (Claims); released, the run finishes and leaves Live;
        History's row says how it ended and opens its report (eight checks, five lanes) with Replay."""
        got = run(ctx)
        ctx.check(f"approved: running, the plan closed, five lanes on Live, got {got.get('running')} / {got.get('plan_closed')} / {got.get('lanes_on_live')}",
                  got.get("running") == "running" and got.get("plan_closed") == "closed" and got.get("lanes_on_live") == 5)
        ctx.check(f"a row per fact on a lane, its owns line, the run's block titled by its goal, got {got.get('lane_rows')} / {got.get('lane_owns')!r} / "
                  f"{got.get('run_block')} / {got.get('run_block_title')!r}",
                  got.get("lane_rows") == ["STATE", "MODEL", "COST", "OWNS"] and got.get("lane_owns") == "basket.py#add_item"
                  and got.get("run_block") == 1 and "Write the five functions" in str(got.get("run_block_title")))
        ctx.check(f"the lane's summary first, Stop offered, the Claims page, got {got.get('lane_summary')} / {got.get('stop_offered')} / {got.get('claims_page')}",
                  got.get("lane_summary") == ["GOAL", "OWNS", "STATE", "LAST OUTPUT", "COST", "MODEL", "WORKTREE"]
                  and got.get("stop_offered") is True and got.get("claims_page") == "claims")
        ctx.check(f"finished, it left Live; History's row and its report, got {got.get('left_live')} / {got.get('history_row')!r} / {got.get('report')}",
                  got.get("left_live") == "gone" and "finished" in str(got.get("history_row")) and got.get("report") == {"checks": 8, "lanes": 5, "replay": True}
                  and (got.get("first_report") or {}).get("status") == "finished")

    @test
    def test_orchestra_plan_approve_runs_and_reject_stops_in_headless_chrome(ctx: Ctx):
        """3.4.0.0 D: a run started from Live's Run a goal panel (the form says what it does, may cost and writes) with
        Review the plan first on closes the panel and waits on you; rejected with a reason on the card, it stops with it
        and leaves Live."""
        got = run(ctx)
        ctx.check(f"the form says what, cost, writes, got {got.get('says')}", got.get("says") == ["WHAT IT DOES", "WHAT IT MAY COST", "WHERE IT WRITES"])
        ctx.check(f"rejected, got {got.get('review_on')} / {got.get('drawer_closed')} / {got.get('stopped')} / {got.get('stop_reason')!r}",
                  got.get("review_on") is True and got.get("drawer_closed") == "closed" and got.get("stopped") == "stopped"
                  and got.get("stop_reason") == "the plan was rejected: one lane per file instead")
