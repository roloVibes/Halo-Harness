"""halo_harness.crew.tools_try -- the builder's Try it tools (Halo 3.6.0.0 R2, the design's tool table).

    try_agent     {name | body: agent/1, request}       one throwaway run of the agent (crew/trial.py)
    try_workflow  {name | body: workflow/1, request}    one throwaway run of the workflow (crew/trial_flow.py)

They start the same run the page's Try it button does and write nothing: no row, no file. The run's cost is the
run's own, said first in its record (the cost band), never the builder's; the builder's cap counts only its own calls.
The page opens the run under Try it (`tries` in the builder's reply). An unsaved body is checked with the format first.
"""

from __future__ import annotations

from halo_harness.crew import store
from halo_harness.crew.formats import agent_problems, workflow_problems


def _body(kind: str, args: dict, ctx):
    body = args.get("body") if isinstance(args.get("body"), dict) else None
    if body is None:
        got = store.load(kind, str(args.get("name") or "").strip(), cwd=ctx.get("cwd"), state_dir=ctx.get("state_dir"))
        body = store.clean(got) if got else None
    return body


def _started(rec: dict, ctx, what: str) -> dict:
    ctx.setdefault("tries", []).append(rec)
    est = (rec.get("estimate") or {}).get("line") or ""
    return {"text": f"started Try it run {rec['id']} of {what} on a throwaway copy ({est}); the person sees its result "
                    "under Try it. Nothing was written.", "rows": []}


def try_agent(args: dict, ctx) -> dict:
    request = str(args.get("request") or "").strip()
    raw = _body("agent", args, ctx)
    if raw is None or not request:
        return {"text": "try_agent needs an agent (its name or its body) and a test request", "rows": []}
    raw = store.clean({**raw, "format": "agent/1"})
    bad = agent_problems(raw, name=str(raw.get("name") or ""))
    if bad:
        return {"text": f"cannot try it: {bad[0]}", "rows": []}
    from halo_harness.crew import trial
    rec = trial.start(raw, request, cwd=ctx.get("cwd"), state_dir=ctx.get("state_dir"), publish=ctx.get("publish"))
    return _started(rec, ctx, f"the agent {raw['name']}")


def try_workflow(args: dict, ctx) -> dict:
    request = str(args.get("request") or "").strip()
    wf = _body("workflow", args, ctx)
    if wf is None or not request:
        return {"text": "try_workflow needs a workflow (its name or its body) and a test request", "rows": []}
    wf = store.clean({**wf, "format": "workflow/1"})
    bad = workflow_problems(wf, name=str(wf.get("name") or ""))
    if bad:
        return {"text": f"cannot try it: {bad[0]}", "rows": []}
    from halo_harness.crew import runner, trial_flow
    problems, agents = runner.preflight(wf, lambda n: _agent(n, ctx))
    if problems:
        return {"text": f"cannot try it: {problems[0]}", "rows": []}
    rec = trial_flow.start_flow(wf, {n: store.clean(a) for n, a in agents.items()}, request, cwd=ctx.get("cwd"),
                                state_dir=ctx.get("state_dir"), publish=ctx.get("publish"))
    return _started(rec, ctx, f"the workflow {wf['name']}")


def _agent(name: str, ctx):
    got = store.load("agent", name, cwd=ctx.get("cwd"), state_dir=ctx.get("state_dir"))
    return store.clean(got) if got else None


TOOLS = {
    "try_agent": (try_agent, '{"name" | "body", "request"}  (one throwaway run; writes nothing; its cost is the run\'s)'),
    "try_workflow": (try_workflow, '{"name" | "body", "request"}  (one throwaway run of every step; writes nothing)'),
}
