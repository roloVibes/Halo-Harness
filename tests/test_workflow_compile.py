"""tests.test_workflow_compile -- a workflow and its inputs compiled to an
Orchestra goal (Halo 3.2.0.0 R5, workflows/compile.py, inputs.py,
conditions.py, bounds.py, pinned.py): the doc-review fixture's Goal, its
hand-offs and the pinned plan (one job per file for `for_each`); a `when` on
an input skips its stage at compile time and the stage after it runs after
the skipped one's upstreams; typed inputs and prerequisites are checked; the
lead may refine the briefs but never the stage set; a reviewed plan keeps
the stages; `halo workflow` and `halo orchestra new --workflow`.

Run: python -m tests.test_workflow_compile
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.workflow_rig import FakeLead, WorkflowRig  # noqa: E402

test, TESTS = new_registry()


def _cli(fn, argv) -> "tuple[int, str]":
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = fn(argv)
    return code, out.getvalue()


@test
def test_the_fixture_compiles_to_a_goal_handoffs_and_a_pinned_plan(ctx: Ctx):
    with WorkflowRig() as w:
        c = w.compile(docs="docs")
        ctx.check(f"no problems, got {c.problems}", c.problems == [] and c.goal is not None)
        g = c.goal
        ctx.check("one read job per Markdown file, then judge, then write",
                  [(j["id"], j["stage"], j["item"]) for j in c.jobs] == [("job-1", "read", "docs/guide.md"), ("job-2", "read", "docs/intro.md"),
                                                                          ("job-3", "judge", ""), ("job-4", "write", "")])
        ctx.check("titles and briefs filled from the item and the inputs", c.jobs[0]["title"] == "Read docs/guide.md"
                  and c.jobs[0]["brief"].startswith("Read docs/guide.md and list") and "(short summary)" in c.jobs[3]["brief"])
        ctx.check("roles are the pack's bios", [j["bio"] for j in c.jobs] == ["doc-review--reviewer"] * 3 + ["doc-review--writer"])
        ctx.check(f"the goal's fields, got {g.to_dict()}", g.workers == 4 and g.plan == "review" and g.budget_usd == 2.0
                  and g.lineup == "doc-review--review" and g.return_cap == 2 and g.files == [] and g.test == ""
                  and g.done_when.startswith("The report lists every finding") and "input docs = docs" in g.what)
        ctx.check("the hand-offs: judge takes each read's notes, write takes the verdict, an artifact is saved as JSON",
                  g.handoffs["job-3"]["needs"] == [{"from": "job-1", "take": "notes"}, {"from": "job-2", "take": "notes"}]
                  and g.handoffs["job-4"]["needs"] == [{"from": "job-3", "take": "verdict"}]
                  and g.handoffs["job-4"]["gives"] == [{"name": "report", "kind": "artifact", "paths": ["report.json"]}])
        wf = g.workflow
        ctx.check("the workflow block", wf["ref"] == "doc-review/review" and wf["version"] == "1.0.0"
                  and [s["jobs"] for s in wf["stages"]] == [["job-1", "job-2"], ["job-3"], ["job-4"]]
                  and wf["outputs"] == {"report": {"type": "artifact:review-report", "from": "write", "schema": "review-report"}})
        bounds = {(b["stage"], b["key"]): b["enforced"] for b in wf["bounds"]}
        ctx.check(f"bounds: the stages' and the workflow's budget held (3.2.1.0 R2), got {bounds}", bounds == {
            ("read", "retries"): True, ("read", "timeout_s"): True, ("judge", "budget_usd"): True, ("judge", "gate"): True,
            ("write", "retries"): True, ("", "budget_usd"): True, ("", "checkpoint"): True})
        from halo_harness.orchestra.goal import Goal, validate_goal
        ctx.check("goal.json round-trips and validates", validate_goal(g.to_dict()) == [] and Goal.from_dict(g.to_dict()).workflow == wf)
        one = w.compile(docs="docs/guide.md", style="long")
        ctx.check("one file: three jobs, the input in the brief", len(one.jobs) == 3 and "(long summary)" in one.jobs[2]["brief"])


@test
def test_a_when_on_an_input_skips_its_stage_and_rewires(ctx: Ctx):
    with WorkflowRig() as w:
        p = w.packs / "doc-review" / "workflows" / "review.yaml"  # the installed copy (the file is read at each find)
        p.write_text(p.read_text(encoding="utf-8").replace("    gate: human\n", "    gate: human\n    when: {input: style, equals: long}\n"),
                     encoding="utf-8")
        c = w.compile(docs="docs")
        ctx.check(f"judge skipped with why, got {c.skipped}", c.skipped == [{"stage": "judge", "why": "when input style equals 'long' is false (it is 'short')"}])
        ctx.check("write runs after the reads instead", [j["stage"] for j in c.jobs] == ["read", "read", "write"]
                  and c.jobs[2]["after"] == ["job-1", "job-2"] and "needs" not in c.jobs[2]["handoff"])
        ctx.check("no human gate left: plan auto", c.goal.plan == "auto")
        long = w.compile(docs="docs", style="long")
        ctx.check("true: the stage runs", [j["stage"] for j in long.jobs] == ["read", "read", "judge", "write"] and long.skipped == [])


@test
def test_inputs_and_prerequisites_are_checked(ctx: Ctx):
    with WorkflowRig() as w:
        ctx.check("a required input", w.compile().problems == ["input docs is required: --input docs=<path>"])
        got = w.compile(docs="../outside", colour="red").problems
        ctx.check(f"unknown and outside, got {got}", got == ["the workflow has no input 'colour' (its inputs: docs, style)",
                                                            "input docs '../outside' must be relative to the repo, inside it"])
        ctx.check("a path that is not there", w.compile(docs="nope").problems[0].startswith("input docs nope is not in the repo"))
        from halo_harness.packs.grants import enable
        from halo_harness.packs.discover import find
        from halo_harness.packs import state as S
        rec = S.entry("doc-review", w.state)
        S.put("doc-review", dict(rec, granted=[]), w.state)
        got = w.compile(docs="docs").problems
        ctx.check(f"without the bash grant: the prerequisite and the capability, got {got}", len(got) >= 2
                  and got[0] == "prerequisite: pack doc-review runs without the bash grant (halo pack enable doc-review --grant bash)"
                  and any("capability docs.review is not available here" in g for g in got))
        enable(find("doc-review", cwd=w.repo), grant=["bash"])
        ctx.check("granted again: clean", w.compile(docs="docs").problems == [])


@test
def test_the_lead_refines_briefs_but_never_the_stage_set(ctx: Ctx):
    from halo_harness.orchestra import jsonl
    from halo_harness.orchestra.split import StopRun
    from halo_harness.workflows.pinned import brief_of, split_pinned
    with WorkflowRig() as w:
        goal = w.compile(docs="docs").goal
        run = w.new_run(goal)
        lead = FakeLead(json.dumps({"jobs": [{"id": "job-1", "brief": "look at the links first"}, {"id": "job-2"},
                                             {"id": "job-3"}, {"id": "job-4"}]}))
        jobs = split_pinned(run, goal, [], call_model=lead, base="abc")
        split = jsonl.read_json(run / "split.json", {})
        ctx.check("the pinned jobs, in order, with bios", [j.id for j in jobs] == ["job-1", "job-2", "job-3", "job-4"]
                  and jobs[3].bio == "doc-review--writer" and split["workflow"]["refined"] == ["job-1"])
        ctx.check("the prompt lists the stages and says they are pinned", "pinned" in lead.prompts[0] and "stage judge" in lead.prompts[0])
        ctx.check("the refined brief wins, the rest keep the workflow's", brief_of(run, goal, "job-1") == "look at the links first"
                  and brief_of(run, goal, "job-2").startswith("Read docs/intro.md"))
        run2 = w.new_run(goal)
        drop = json.dumps({"jobs": [{"id": "job-1", "brief": "only one"}]})
        lead = FakeLead(drop, drop)
        jobs = split_pinned(run2, goal, [], call_model=lead, base="abc")
        ctx.check("an answer that drops jobs is asked again, then the workflow's briefs run", len(lead.prompts) == 2
                  and "the stage set is pinned" in lead.prompts[1] and len(jobs) == 4 and brief_of(run2, goal, "job-1").startswith("Read docs/guide"))
        try:
            split_pinned(w.new_run(goal), goal, [], call_model=FakeLead('{"stop": "nothing to review"}'), base="abc")
            stopped = ""
        except StopRun as e:
            stopped = str(e)
        ctx.check(f"stop still stops, got {stopped!r}", stopped == "the lead stopped the run: nothing to review")


@test
def test_a_reviewed_plan_keeps_the_stages(ctx: Ctx):
    from halo_harness.orchestra import plan as P
    from halo_harness.workflows.pinned import pinned_jobs
    with WorkflowRig() as w:
        goal = w.compile(docs="docs").goal
        run = w.new_run(goal)
        jobs = pinned_jobs(goal)
        ctx.check(f"the pinned plan passes as it is, got {P.check(run, jobs)}", P.check(run, jobs) == [])
        texts = [p["text"] for p in P.check(run, jobs[:3])]
        ctx.check(f"dropping a stage's job is refused, got {texts}", any("pins its stages" in t for t in texts))
        texts = [p["text"] for p in P.check(run, [jobs[1], jobs[0]] + jobs[2:])]
        ctx.check("reordering is refused", any("in that order" in t for t in texts))
        edited = [dict(j) for j in jobs]
        edited[0]["title"] = "Read the guide closely"
        ctx.check("a title edit is fine, and a stage may claim nothing", P.check(run, edited) == [])


@test
def test_the_cli_lists_shows_checks_and_makes_a_run(ctx: Ctx):
    from halo_harness.orchestra_cli import cmd_orchestra
    from halo_harness.workflows.cli import cmd_workflow
    with WorkflowRig() as w:
        r = ["--repo", str(w.repo)]
        code, out = _cli(cmd_workflow, ["list"] + r)
        ctx.check(f"list, got {out!r}", code == 0 and "doc-review/review" in out and "read, judge, write" in out)
        code, out = _cli(cmd_workflow, ["show", "doc-review/review"] + r)
        ctx.check(f"show, got {out!r}", code == 0 and "role reviewer -> doc-review--reviewer" in out and "when output judge.verdict is not empty" in out)
        code, out = _cli(cmd_workflow, ["check", "doc-review/review", "--input", "docs=docs"] + r)
        ctx.check(f"check, got {out!r}", code == 0 and "compiles: 4 job(s), plan review" in out and "job-3:verdict" in out)
        code, out = _cli(cmd_workflow, ["check", "doc-review/review"] + r)
        ctx.check(f"check without the input: 2, got {out!r}", code == 2 and "input docs is required" in out)
        code, out = _cli(cmd_workflow, ["show", "doc-review/nope"] + r)
        ctx.check(f"an unknown workflow: 1, got {out!r}", code == 1 and "declares no workflow 'nope'" in out)
        code, out = _cli(cmd_orchestra, ["new", "--workflow", "doc-review/review", "--input", "docs=docs"] + r)
        ctx.check(f"orchestra new --workflow, got {out!r}", code == 0 and "workflow doc-review/review: 4 job(s), plan review" in out)
        from halo_harness.orchestra.goal import latest_run, load_goal
        ctx.check("its goal.json carries the workflow", load_goal(latest_run(w.repo) / "goal.json").workflow["ref"] == "doc-review/review")
        from argparse import Namespace
        from halo_harness.workflows import goal as WG
        code, out = _cli(cmd_workflow, ["run", "doc-review/review", "--input", "docs=docs", "--as", "goal"] + r)
        if not WG.available():
            ctx.check(f"--as goal without the supervisor: one line, 2, got {out!r}", code == 2 and "not in this build" in out)
        else:
            ctx.check(f"--as goal queues it, got {out!r}", code == 0 and "queued g-" in out and "the supervisor runs it" in out)
            code, out = _cli(lambda a: WG.cli_add(w.state, Namespace(workflow="doc-review/review", inputs=["docs=docs"], repo=str(w.repo))), [])
            ctx.check(f"halo goal add --workflow's handler, got {out!r}", code == 0 and "queued g-" in out)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
