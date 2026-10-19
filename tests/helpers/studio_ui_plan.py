"""tests.helpers.studio_ui_plan -- the Orchestra plan canvas
checks of tests/test_studio_ui.py (Halo 3.0.9.0 round R2), kept here so that
file stays small. One headless Chrome run (`python -m tests.helpers.studio_plan`,
tests/helpers/studio_plan.py) over a Studio on a temp git repo with the R2
fakes (no model call); the runner caches it, so the tests read one run."""
from __future__ import annotations

from tests.helpers.runner import Ctx, SkipTest

ARGS = ("-m", "tests.helpers.studio_plan")


def register(test, json_of, chrome) -> None:
    def run(ctx: Ctx) -> dict:
        if not chrome():
            raise SkipTest("no Chrome found (the plan canvas test needs headless Chrome)")
        r, got = json_of(*ARGS)
        ctx.check(f"the run finished, got {r.stdout[-300:]!r} {r.stderr[-600:]!r}", r.returncode == 0 and "failed" not in got)
        return got

    @test
    def test_orchestra_plan_canvas_draws_the_planned_lanes_in_headless_chrome(ctx: Ctx):
        """3.0.9.0 R2: a review run opens on the plan canvas instead of the console: five lanes in
        two layer boxes (lane 2 takes lane 1's summary), one edge with its `summary` chip. 3.1.2.0 R2:
        each card's cost chip and the header's forecast total, red over the goal's budget_usd."""
        got = run(ctx)
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
    def test_orchestra_plan_approve_runs_and_reject_stops_in_headless_chrome(ctx: Ctx):
        """3.0.9.0 R2: Approve and run turns the run running and the console comes back, then it
        finishes; a run started from the Start view with "Review the plan before it runs" on is
        rejected with a reason on the card and stops with it."""
        got = run(ctx)
        ctx.check(f"approved, got {got.get('running')} / {got.get('console_back')} / {got.get('finished')}",
                  got.get("running") == "running" and got.get("console_back") == "back" and got.get("finished") == "finished")
        ctx.check(f"rejected, got {got.get('review_on')} / {got.get('stopped')} / {got.get('stop_reason')!r}",
                  got.get("review_on") is True and got.get("stopped") == "stopped"
                  and got.get("stop_reason") == "the plan was rejected: one lane per file instead")
