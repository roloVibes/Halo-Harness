"""tests.helpers.studio_plan -- a goal run on Agents -> Live (Halo 3.0.9.0 round R2's plan canvas; 3.4.0.0 D "the runs
fold": Runs' console went, a goal run is a job on Live) in headless Chrome over the DevTools protocol
(tests/helpers/cdp.py), over a Studio server on a temp git repo with the R2 fakes as `orchestra_api.RUNNER` (no model
call). tests/test_studio_ui.py runs it as a subprocess with a scrubbed environment (tests/helpers/studio_ui_plan.py):

    python -m tests.helpers.studio_plan

* a review run waiting for its plan is its lead on Live, waiting on you, with Review the plan; nothing is open until
  that click, which opens the plan beside the canvas: five lanes in two layer boxes, one edge; each card's priced cost
  chip and the header's forecast total, red over the goal's budget;
* dragging lane 3 into the second box sets its `after` and draws its edges;
* a claim of lane 5's added to lane 4 (both in the first box) shows a problem on both cards and disables Approve and
  run; Undo clears it;
* Approve and run: the plan panel closes, the run turns running (the fake workers are held) and its five lanes are
  boxes under the lead, a row per fact; a click on a lane is its summary in the inspector, Claims one page; released,
  the run finishes and leaves Live, and History holds it: its row opens its report (the checks, the lanes), Replay on it;
* a second run from Live's Run a goal panel (the form says what it does, may cost and writes) with Review the plan
  first on: Reject asks for a reason on a card and the run stops with it.

Every step WAITS for the state it reads. The last stdout line is a JSON object of what it saw (exit 2: no Chrome)."""
from __future__ import annotations

import json
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402

TID = "document.querySelector('[data-testid=\"{}\"]')"
N = "document.querySelectorAll('[data-testid=\"{}\"]').length"
LANE = "document.querySelector('[data-testid=\"plan-lane\"][data-id=\"{}\"]')"
LAYER = "document.querySelector('[data-testid=\"plan-layer\"][data-layer=\"{}\"]')"


def runner(hold: threading.Event):
    """orchestra_api.RUNNER: the R2 fakes, the lead's split chained (job-2 takes job-1's summary)."""
    from tests.helpers import orchestra_fixtures as F
    from tests.helpers.orchestra_studio_rig import chained_answer

    def make(run_dir, goal, model):
        worker = F.FakeWorker()

        def spawn(lane):
            hold.wait(30)
            return worker(lane)
        return {"model_calls": F.FakeLead(chained_answer()), "spawn": spawn, "judge": F.FakeJudge()}
    return make


def click(c, expr: str) -> None:
    c.js(f"({expr}).scrollIntoView({{block: 'center', inline: 'center'}}); 1")
    time.sleep(0.15)
    c.click_on(expr)


def pick(c, testid: str, value: str) -> None:
    """Choose an <select> option the way a person does (React sees the change)."""
    c.js(f"(() => {{ const el = {TID.format(testid)}; const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;"
         f" set.call(el, {json.dumps(value)}); el.dispatchEvent(new Event('change', {{bubbles: true}})); return 1; }})()")


def lanes_and_layers(c, url: str, out: dict) -> None:
    c.go(url)
    out["lead_waits"] = c.wait(f"{TID.format('agents-live-lead')}?.dataset.state === 'waiting' && !!{TID.format('agents-live-review')} && 'waits'", 30)
    out["nothing_open"] = c.js(f"{N.format('orchestra-plan')} === 0 && {N.format('run-goal-drawer')} === 0 && {N.format('history-page')} === 0")
    out["narration_asks"] = c.wait(f"({TID.format('live-narration')}?.dataset.text || '').startsWith('waiting on you') && 'asks'", 10)
    click(c, TID.format("agents-live-review"))
    c.wait(f"{N.format('plan-lane')} === 5 && {N.format('plan-edge')} === 1", 30)
    out["canvas"] = {k: c.js(N.format(k)) for k in ("orchestra-plan", "plan-canvas", "plan-lane", "plan-edge", "plan-approve", "orchestra-root")}
    out["layers"] = c.js(f"{TID.format('plan-canvas')}.dataset.layers")
    out["edge_label"] = c.js(f"{TID.format('plan-edge-label')}.textContent")
    out["lane2_layer"] = c.js(f"{LANE.format('job-2')}.dataset.layer")
    out["cost_chips"] = c.js("[...document.querySelectorAll('[data-testid=\"plan-cost\"][data-priced]')].length")
    out["cost_chip"] = c.js(f"{LANE.format('job-1')}.querySelector('[data-testid=\"plan-cost\"]')?.textContent")
    out["forecast"] = c.js(f"{TID.format('plan-forecast')}?.textContent")
    out["forecast_over"] = c.js(f"{TID.format('plan-forecast')}?.dataset.over")


def drag_into_layer(c, rig, out: dict) -> None:
    c.js(f"{LAYER.format('1')}.scrollIntoView({{block: 'center'}}); 1")
    c.wait(f"!!{LANE.format('job-3')} && !!{LAYER.format('1')}", 5)
    x0, y0, w0, h0 = c.rect(LANE.format("job-3"))
    x1, y1, w1, h1 = c.rect(LAYER.format("1"))
    c.drag(x0 + w0 / 2, y0 + 20, x1 + w1 / 2, y1 + h1 - 30, steps=12)
    out["lane3_layer"] = c.wait(f"{LANE.format('job-3')}?.dataset.layer === '1' && '1'", 10)
    out["edges_after_drag"] = c.wait(f"{N.format('plan-edge')} > 1 && {N.format('plan-edge')}", 10)
    out["edge_job1_job3"] = c.js("!!document.querySelector('[data-testid=\"plan-edge\"][data-from=\"job-1\"][data-to=\"job-3\"]')")
    c.wait(f"!{TID.format('plan-saving')}", 10)
    out["after_saved"] = rig.plan_jobs()[2].get("after")


def overlap_problem(c, out: dict) -> None:
    click(c, f"{LANE.format('job-4')}.querySelector('.pc-title')")
    c.wait("document.querySelector('[data-testid=\"plan-inspector\"]')?.dataset.id === 'job-4'", 10)
    pick(c, "plan-claim-add", "basket.py#total")
    out["problem"] = c.wait(f"{N.format('plan-problem')} > 0 && {TID.format('plan-problem')}.textContent", 15)
    out["approve_disabled"] = c.js(f"{TID.format('plan-approve')}.disabled")
    out["approve_names"] = c.js(f"{TID.format('plan-approve')}.title")
    out["red_cards"] = c.js("[...document.querySelectorAll('[data-testid=\"plan-lane\"][data-problem]')].map((e) => e.dataset.id).sort()")
    click(c, TID.format("plan-undo"))
    out["undo_clears"] = c.wait(f"{N.format('plan-problem')} === 0 && !{TID.format('plan-approve')}.disabled && 'clear'", 15)


LANE_BOX = "document.querySelector('[data-testid=\"agents-live-lane\"][data-lane=\"{}\"]')"


def approve_runs(c, rig, out: dict) -> None:
    click(c, TID.format("plan-approve"))
    out["running"] = c.wait(f"{TID.format('agents-live-lead')}?.dataset.state === 'running' && 'running'", 20)
    out["plan_closed"] = c.wait(f"{N.format('orchestra-plan')} === 0 && 'closed'", 15)
    out["lanes_on_live"] = c.wait(f"{N.format('agents-live-lane')} === 5 && 5", 20)
    out["lane_rows"] = c.wait(f"(() => {{ const b = {LANE_BOX.format(1)}; const rows = b && [...b.querySelectorAll('.ag-run-k')].map((x) => x.textContent);"
                              f" return rows && rows.length >= 4 ? rows : null; }})()", 10)
    out["lane_owns"] = c.js(f"{LANE_BOX.format(1)}.querySelector('[data-testid=\"lane-owns\"] .ag-run-v')?.textContent")
    out["run_block"] = c.js("document.querySelectorAll('[data-testid=\"live-group\"][data-kind=\"run\"], [data-testid=\"live-block\"][data-kind=\"run\"]').length")
    out["run_block_title"] = c.js("document.querySelector('[data-testid=\"live-block-bar\"][data-kind=\"run\"]')?.textContent || "
                                  "document.querySelector('[data-testid=\"live-group\"][data-kind=\"run\"]')?.textContent")
    click(c, LANE_BOX.format(1))
    out["lane_summary"] = c.wait(f"{TID.format('run-inspector')}?.dataset.pick === 'lane' && {TID.format('run-inspector')}.dataset.lane === '1'"
                                 f" && [...{TID.format('run-summary-facts')}.querySelectorAll('dt')].map((d) => d.textContent)", 10)
    out["stop_offered"] = c.js(f"!!{TID.format('run-stop')}")
    click(c, TID.format("run-open-claims"))
    out["claims_page"] = c.wait(f"{TID.format('run-page')}?.dataset.block === 'claims' && !!{TID.format('lane-claims')} && 'claims'", 10)
    click(c, TID.format("run-page-back"))
    c.wait(f"!!{TID.format('run-summary-facts')}", 5)
    rig.hold.set()
    try:
        out["left_live"] = c.wait(f"{N.format('roles-live-map')} === 1 && {N.format('agents-live-lead')} === 0 && {N.format('agents-live-lane')} === 0"
                                  f" && !!{TID.format('live-history')} && 'gone'", 60)
        click(c, TID.format("live-history"))
        row = "document.querySelector('[data-testid=\"live-history-row\"][data-kind=\"run\"]')"
        out["history_row"] = c.wait(f"{row}?.textContent", 15)
        click(c, row)
        out["report"] = c.wait(f"{TID.format('history-report')}?.dataset.state === 'finished' && {N.format('report-check')}"
                               f" && {{checks: {N.format('report-check')}, lanes: {N.format('report-lane')}, replay: !!{TID.format('history-report-replay')}}}", 15)
    finally:
        out["first_report"] = {k: rig.last_report().get(k) for k in ("status", "stop_reason")}
    click(c, TID.format("history-report-back"))
    c.wait(f"!!{TID.format('live-history-row')}", 5)
    c.key("Escape")
    c.wait(f"{N.format('live-history-drawer')} === 0", 5)


def reject_stops(c, rig, out: dict) -> None:
    click(c, TID.format("live-run-goal"))
    c.wait(f"!!{TID.format('orchestra-goal-form')} && !!{TID.format('run-goal-says')}", 20)
    out["says"] = c.js(f"[...{TID.format('run-goal-says')}.querySelectorAll('dt')].map((d) => d.textContent)")
    for label, text in (("WHAT YOU WANT", "Write the five functions of basket.py"), ("DONE WHEN", "the tests pass"),
                        ("STOP WHEN", "two returns"), ("SHARED FILES (comma separated)", "basket.py")):
        expr = (f"[...document.querySelectorAll('[data-testid=\"orchestra-goal-form\"] .field')].find((f) => "
                f"f.querySelector('.field-label').textContent === {json.dumps(label)}).querySelector('textarea, input')")
        click(c, expr)
        c.type_text(text)
    click(c, TID.format("orchestra-review"))
    out["review_on"] = c.wait(f"{TID.format('orchestra-review')}.checked && (({TID.format('run-goal-does')}?.textContent || '').includes('the plan waits for you')) && true", 5)
    click(c, TID.format("orchestra-run"))
    out["drawer_closed"] = c.wait(f"{N.format('run-goal-drawer')} === 0 && {TID.format('agents-live-lead')}?.dataset.state === 'waiting' && 'closed'", 30)
    click(c, TID.format("agents-live-review"))
    c.wait(f"{N.format('plan-lane')} === 5", 30)
    click(c, TID.format("plan-reject"))
    c.wait(f"!!{TID.format('plan-reject-card')}", 10)
    click(c, TID.format("plan-reject-reason"))
    c.type_text("one lane per file instead")
    click(c, TID.format("plan-reject-confirm"))
    out["stopped"] = c.wait(f"{N.format('agents-live-lead')} === 0 && {N.format('orchestra-plan')} === 0 && 'stopped'", 30)
    out["stop_reason"] = rig.last_report().get("stop_reason")


class PlanDriver(Driver):
    """A goal run on Live, its plan review, its lanes, its report in History, over tests/helpers/studio_plan_rig.py."""

    @contextmanager
    def session(self, c):
        from tests.helpers.studio_plan_rig import PlanRig
        with PlanRig() as rig:
            url = rig.url("agents").replace("&open=all", "")  # 3.4.0.0 D: Live as it opens (one thing per section)
            yield ((lanes_and_layers, (c, url, self.out)), (drag_into_layer, (c, rig, self.out)), (overlap_problem, (c, self.out)),
                   (approve_runs, (c, rig, self.out)), (reject_stops, (c, rig, self.out)))


def main() -> int:
    # tests/test_studio_ui.py scrubs BRIDGE_*: the base scopes the home first, or the Studio server's fleet
    # identity and run folder land in the real ~/.halo (the suite's real-state-dir guard fails on a runner without one)
    return PlanDriver().main()


if __name__ == "__main__":
    sys.exit(main())
