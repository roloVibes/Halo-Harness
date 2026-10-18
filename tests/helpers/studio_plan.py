"""tests.helpers.studio_plan -- the Orchestra plan canvas and the Flow graph
(Halo 3.0.9.0 round R2) in headless Chrome over the DevTools protocol
(tests/helpers/cdp.py), over a Studio server on a temp git repo with the R2
fakes as `orchestra_api.RUNNER` (no model call). tests/test_studio_ui.py runs
it as a subprocess with a scrubbed environment (tests/helpers/studio_ui_plan.py):

    python -m tests.helpers.studio_plan

* a review run (lane 2 takes lane 1's summary) opens on the plan canvas:
  five lanes in two layer boxes, one edge;
* dragging lane 3 into the second box sets its `after` and draws its edges;
* a claim of lane 5's added to lane 4 (both in the first box) shows a
  problem on both cards and disables Approve and run; Undo clears it;
* Approve and run: the run turns running (the fake workers are held) and the
  console comes back; released, it finishes;
* a second run from the Start view's form with "Review the plan before it
  runs" on: Reject asks for a reason on a card and the run stops with it;
* the Flow section's "Show as graph" draws the social-post template's eight
  steps in their layers, the confirm step marked as the gate.

The last stdout line is a JSON object of what it saw (exit 2: no Chrome)."""
from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

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
    c.wait(f"{N.format('plan-lane')} === 5 && {N.format('plan-edge')} === 1", 30)
    out["canvas"] = {k: c.js(N.format(k)) for k in ("orchestra-plan", "plan-canvas", "plan-lane", "plan-edge", "plan-approve", "orchestra-root")}
    out["layers"] = c.js(f"{TID.format('plan-canvas')}.dataset.layers")
    out["edge_label"] = c.js(f"{TID.format('plan-edge-label')}.textContent")
    out["lane2_layer"] = c.js(f"{LANE.format('job-2')}.dataset.layer")


def drag_into_layer(c, rig, out: dict) -> None:
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


def approve_runs(c, rig, out: dict) -> None:
    click(c, TID.format("plan-approve"))
    out["running"] = c.wait(f"{TID.format('run-state')}?.textContent === 'RUNNING' && 'running'", 20)
    out["console_back"] = c.wait(f"{N.format('orchestra-root')} === 1 && {N.format('orchestra-plan')} === 0 && 'back'", 10)
    rig.hold.set()
    try:
        out["finished"] = c.wait(f"{TID.format('run-state')}?.textContent === 'FINISHED' && 'finished'", 60)
    finally:
        out["first_report"] = {k: rig.last_report().get(k) for k in ("status", "stop_reason")}
        out["first_state_text"] = c.js(f"{TID.format('run-state')}?.textContent")
        out["first_dom"] = {k: c.js(N.format(k)) for k in ("orchestra-plan", "orchestra-root", "start-view", "plan-lane", "panel-about")}
        out["first_text"] = c.js("document.querySelector('.stage')?.innerText.slice(0, 300)")


def reject_stops(c, rig, url: str, out: dict) -> None:
    c.go(url.replace("#t=", "&view=start#t="))
    c.wait(f"!!{TID.format('orchestra-goal-form')}", 20)
    for label, text in (("WHAT YOU WANT", "Write the five functions of basket.py"), ("DONE WHEN", "the tests pass"),
                        ("STOP WHEN", "two returns"), ("FILES (comma separated)", "basket.py")):
        expr = (f"[...document.querySelectorAll('[data-testid=\"orchestra-goal-form\"] .field')].find((f) => "
                f"f.querySelector('.field-label').textContent === {json.dumps(label)}).querySelector('textarea, input')")
        click(c, expr)
        c.type_text(text)
    click(c, TID.format("orchestra-review"))
    out["review_on"] = c.js(f"{TID.format('orchestra-review')}.checked")
    click(c, TID.format("orchestra-run"))
    c.wait(f"{N.format('plan-lane')} === 5", 30)
    click(c, TID.format("plan-reject"))
    c.wait(f"!!{TID.format('plan-reject-card')}", 10)
    click(c, TID.format("plan-reject-reason"))
    c.type_text("one lane per file instead")
    click(c, TID.format("plan-reject-confirm"))
    out["stopped"] = c.wait(f"{TID.format('run-state')}?.textContent === 'STOPPED' && 'stopped'", 30)
    out["stop_reason"] = rig.last_report().get("stop_reason")


def flow_graph(c, url: str, out: dict) -> None:
    c.go(url.replace("mode=orchestra", "mode=flow").replace("#t=", "&view=start#t="))
    c.wait(f"!!{TID.format('flow-show-graph')}", 20)
    click(c, TID.format("flow-show-graph"))
    c.wait(f"{N.format('flow-step')} === 8", 20)
    out["flow"] = {k: c.js(N.format(k)) for k in ("flow-graph", "flow-step", "flow-graph-layer", "flow-graph-edge")}
    out["flow_gate"] = c.js("[...document.querySelectorAll('[data-testid=\"flow-step\"][data-gate]')].map((e) => e.dataset.id)")
    click(c, TID.format("flow-graph-back"))
    out["flow_back"] = c.wait(f"{N.format('flow-step')} === 0 && !!{TID.format('flow-intake-form')} && 'back'", 10)


def main() -> int:
    from capture_studio import find_chrome
    exe = find_chrome()
    if not exe:
        print(json.dumps({"error": "no Chrome found"}))
        return 2
    from tests.helpers.cdp import Chrome
    from tests.helpers.studio_plan_rig import PlanRig
    out: dict = {}
    c = Chrome(exe)
    try:
        with PlanRig() as rig:
            url = rig.url()
            steps = ((lanes_and_layers, (c, url, out)), (drag_into_layer, (c, rig, out)), (overlap_problem, (c, out)),
                     (approve_runs, (c, rig, out)), (reject_stops, (c, rig, url, out)), (flow_graph, (c, url, out)))
            for fn, args in steps:
                try:
                    fn(*args)
                except Exception as e:  # what it saw so far still prints; the test names the step
                    out["failed"] = f"{fn.__name__}: {type(e).__name__}: {e}"[:400]
                    break
            c.go("about:blank")
    finally:
        c.close()
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
