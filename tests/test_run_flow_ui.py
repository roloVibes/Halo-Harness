"""tests.test_run_flow_ui -- Halo 3.6.0.6 P (batch 2, entries 2 and 3): Run it, the ONE control that starts a real run of a
crew workflow from Studio (ui routes/crew/flows/RunFlow.tsx; its words and rules in runWords.ts, its form in
runFlowStore.ts). Pure: node, every platform (tests/helpers/node_ts.py), plus the source facts that hold the views to it.

1. the words, word for word: Run it, Run, Cancel, the line before Run (with the folder), the receipt, Watch it in Live,
   the goal drawer's head "Workflows", the palette's "Run a workflow";
2. what a row is offered: an enabled pack's, yours and this project's are run by name; one that ships with Halo is not
   (Copy makes it yours); a row with problems is offered off, its hover the first problem; the request is POST crew/run
   {name, task} with the task trimmed; Run is on once a task is typed and nothing is under way;
3. every view that shows a workflow offers it through RunFlow (Workflows beside Try it, the goal drawer, the Pack
   Manager, a pack's section drawn by Studio, a workflow box on the Map, the palette), only runFlowStore.ts posts the
   route, and a pack page's scoped client is not given it.
Run: python -m tests.test_run_flow_ui
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
SRC = Path(__file__).resolve().parent.parent / "halo_harness" / "studio" / "ui" / "src"
FLOWS = SRC / "routes" / "crew" / "flows"
WORDS = FLOWS / "runWords.ts"
LINE = ("Starts a new session in ~/work/shop that runs this workflow's steps on your models. It can change files there. "
        "Cost and time depend on the models its steps use.")


def node(body: str):
    from tests.helpers import node_ts
    js = f"const M = await import({json.dumps(WORDS.resolve().as_uri())});\nconst out = {{}};\n{body}\nconsole.log(JSON.stringify(out));"
    return node_ts.run(js)


@test
def test_the_words_are_the_rulings(ctx: Ctx):
    got = node("""
out.words = [M.RUN_IT, M.RUN, M.CANCEL, M.WATCH, M.RUN_HEAD, M.RUN_A_WORKFLOW, M.RUN_PATH];
out.line = M.runLine('~/work/shop');
out.started = M.startedLine('3f9c2a1b');
""")
    ctx.check(f"the buttons, heads and route, got {got.get('words')}",
              got.get("words") == ["Run it", "Run", "Cancel", "Watch it in Live", "Workflows", "Run a workflow", "crew/run"])
    ctx.check(f"the line before Run, word for word, got {got.get('line')!r}", got.get("line") == LINE)
    ctx.check(f"the receipt, got {got.get('started')!r}", got.get("started") == "Started: session 3f9c2a1b.")


@test
def test_what_each_row_is_offered_and_the_request(ctx: Ctx):
    got = node("""
const rows = [{name: 'doc-review--review-docs', scope: 'pack', problems: []}, {name: 'mine', scope: 'yours'},
              {name: 'here', scope: 'project', problems: []}, {name: 'code', scope: 'starter', problems: []},
              {name: 'broken', scope: 'yours', problems: ['step 1 names an agent that does not exist: ghost', 'second']}];
out.offers = rows.map((r) => M.offer(r));
out.runnable = M.runnable(rows).map((r) => r.name);
out.body = M.runBody('doc-review--review-docs', '  Review docs/a.md \\n');
out.can = [M.canRun('', false), M.canRun('  ', false), M.canRun('x', true), M.canRun('x', false)];
""")
    offers = got.get("offers") or []
    ctx.check(f"a pack's, yours and the project's are offered and on, got {offers[:3]}",
              offers[:3] == [{"show": True, "off": ""}] * 3)
    ctx.check(f"one that ships with Halo is not offered (Copy makes it yours), got {offers[3:4]}", offers[3:4] == [{"show": False, "off": ""}])
    ctx.check(f"a row with problems is off, its hover the first problem, got {offers[4:]}",
              offers[4:] == [{"show": True, "off": "step 1 names an agent that does not exist: ghost"}])
    ctx.check(f"the rows a view lists, got {got.get('runnable')}", got.get("runnable") == ["doc-review--review-docs", "mine", "here", "broken"])
    ctx.check(f"POST crew/run's body, the task trimmed, got {got.get('body')}",
              got.get("body") == {"name": "doc-review--review-docs", "task": "Review docs/a.md"})
    ctx.check(f"Run is on only with a task and nothing under way, got {got.get('can')}", got.get("can") == [False, False, False, True])


@test
def test_every_view_offers_the_one_run_it(ctx: Ctx):
    read = lambda p: p.read_text(encoding="utf-8")  # noqa: E731
    views = {"Workflows, beside Try it": (FLOWS / "FlowTry.tsx", "<RunItButton"),
             "the Run a goal drawer": (SRC / "routes" / "orchestra" / "WorkflowPicker.tsx", "<RunFlow"),
             "the Pack Manager": (SRC / "routes" / "packs" / "manager" / "Details.tsx", "<PackFlows"),
             "a pack's section, drawn by Studio": (SRC / "App.tsx", "<PackFlows"),
             "a workflow box on the Map": (SRC / "routes" / "crew" / "map" / "MapBox.tsx", "<MapRunIt"),
             "the palette": (SRC / "shell" / "commands.ts", "flowCommands()")}
    missing = [k for k, (p, mark) in views.items() if mark not in read(p)]
    ctx.check(f"every view offers Run it, these do not: {missing}", not missing)
    ctx.check("the Try it beside it is untouched (its button and words)",
              'data-testid="flow-try-send">Try it</Button>' in read(FLOWS / "FlowTry.tsx"))
    posting = sorted(str(p.relative_to(SRC)) for p in SRC.rglob("*.ts*") if "RUN_PATH" in read(p) and "api.post" in read(p))
    ctx.check(f"only runFlowStore.ts posts the route, got {posting}", posting == [str(Path("routes/crew/flows/runFlowStore.ts"))])
    others = sorted(str(p.relative_to(SRC)) for p in SRC.rglob("*.ts*") if '"crew/run"' in read(p) and p.name != "runWords.ts")
    ctx.check(f"no other file names the route, got {others}", not others)
    ctx.check("a pack page's scoped client is not given the route", "crew/run" not in read(SRC / "packlib" / "scoped.ts"))


@test
def test_watch_it_in_live_is_not_held_on_an_empty_drawing(ctx: Ctx):
    """Batch 2 repair (the checker's first finding): Watch it in Live lands on Agents -> 4 · Live with the pointer over the
    drawing, and the drawing kept "under the pointer" (runFrame.ts useHeld, 3.6.0.2 R12) was its first one: no box at all,
    so the run's group was never drawn until the pointer left. A drawing with no box is never held (drawnAll), in Agents'
    Live and in Session's drawer alike."""
    from tests.test_map_groups import _stubbed
    js = """const d = m.drawnAll;
console.log(JSON.stringify([d([], {}), d([{id: "main"}], {main: 107}), d([{id: "main"}, {id: "group:1"}], {main: 107}), d([{id: "a"}], {})]));"""
    got = _stubbed("routes/crew/map/runFrame.ts", js)
    ctx.check(f"no box: nothing to hold; every box measured: held; one unmeasured: not yet, got {got}", got == [False, True, False, False])
    read = lambda p: p.read_text(encoding="utf-8")  # noqa: E731
    ctx.check("Agents -> 4 · Live holds only a drawing with its boxes measured (drawnAll)",
              "useHeld<G>(held, map, fresh, drawnAll(fresh.boxes, heights))" in read(SRC / "routes" / "agents" / "LiveDraw.tsx"))
    ctx.check("Session's Live drawer the same",
              "drawnAll(live.boxes, heights))" in read(SRC / "routes" / "session" / "MapDown.tsx"))


@test
def test_the_workflows_form_draws_with_its_band(ctx: Ctx):
    """Batch 2 repair (the checker's second finding): the band ("What it costs and writes" above Try it, and the estimate
    beside it) came 0.3 s after the form, and its lines pushed Try it and Run it down by about 90 px. A saved workflow is
    opened with its band read in the same step (flowStore.ts openFlow: one POST crew/workflow-cost, as before), so the
    form's first draw holds it and the row never moves by itself."""
    src = (FLOWS / "flowStore.ts").read_text(encoding="utf-8")
    body = src[src.index("export async function openFlow"):src.index("export function newFlow")]
    ctx.check("openFlow reads the band before it puts the form, and asks once (no second, debounced read)",
              'bandOf(w)' in body and "put(w, w, { name, scope: r.scope }, \"\", r.maps, band, r.sig || \"\")" in body)  # 3.6.0.9 V: + its hash


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
