"""halo_harness.tools.workflow -- the Workflow tool: the router (Halo 3.3.16.0 R3, docs/WORKFLOWS-squares.md).

`Workflow(need | name, task, files)` hands a task to a square: a workflow with a contract that this
session's lineup has enabled (workflows/registry.py). With `name` that square; with `need`, or neither
(the gaps derived from the task and its files minus what this model takes), the router's pick
(workflows/router.py). The run is the square's engine (workflows/square_run.py: `session` spawns one
agent through the Agent tool's own path, so the parent's permission engine and rules apply inside it;
`orchestra` compiles and runs the goal, bounded by `limits.wall_s`). Depth and the cap are enforced here.
Every hand-off is a receipt (workflows/receipts.py); a square that cannot start says so in one line and
the model goes on -- the router never opens a dialog.

On the main agent and on every bio its lineup lets delegate (a bio allowed Agent is allowed Workflow,
config/agents_md.py `resolved_tools`). Tests swap `SPAWN` / `RUN_ORCHESTRA` / `TAKES` for fakes.

3.3.16.2: offered only when a square is enabled for the session's lineup (workflows/offer.py drops it from
the tool list otherwise), and a role of the lineup that covers the reads takes the task before any square
(workflows/lineup_roles.py; the receipt says "handing the PDF to your media role: the lineup covers it").
"""

from __future__ import annotations

from typing import Callable, Optional

from halo_harness.tools.base import Tool, ToolContext, ToolResult

SPAWN: Optional[Callable] = None          # agent.subagent.run_agent_call (a test's fake)
RUN_ORCHESTRA: Optional[Callable] = None  # a run_dir -> None runner (a test's fake)
TAKES: Optional[list] = None              # what the model takes (a test's fake; default: the takes cache)

DESCRIPTION = (
    "Hand a task to a workflow square: a saved orchestration with a contract (what it takes, what it gives, "
    "the needs it covers), run on models picked for it. Use it when the task carries something your model "
    "does not take (a PDF, an image, audio, video) or asks for a plan, a review or research. `name` picks the "
    "square; `need` says what is needed (pdf, vision, audio, video, code, plan, research, media, review, "
    "work-data); with neither, the need is worked out from `task` and `files` minus what your model takes. "
    "Give `task` self-contained (the square has no memory of this conversation) and `files` as paths. The "
    "answer starts with one line saying which square took it and why; when no square can, that line says "
    "what could not be read and you carry on.")

INPUT_SCHEMA = {"type": "object", "properties": {
    "task": {"type": "string", "description": "What the square should do, self-contained"},
    "name": {"type": "string", "description": "The square to use (an enabled one)"},
    "need": {"type": "string", "description": "The need: pdf, vision, audio, video, code, plan, research, media, review, work-data"},
    "files": {"type": "array", "items": {"type": "string"}, "description": "Paths of the files the task is about"},
}, "required": ["task"]}


def _lineup(runtime) -> Optional[str]:
    return getattr(getattr(runtime, "team_control", None), "name", None)


def session_remaining(runtime) -> Optional[float]:
    """The lineup's budget left (budget.max_budget_usd - spent); None with no lineup cap."""
    tc = getattr(runtime, "team_control", None)
    cap = (getattr(tc, "budget", None) or {}).get("max_budget_usd") if tc is not None else None
    try:
        return None if cap is None else max(0.0, float(cap) - float(getattr(tc, "spend_usd", 0.0) or 0.0))
    except (TypeError, ValueError):
        return None


def _talk(session, node: str, ref: str, text: str, back: bool = False, re: Optional[str] = None) -> Optional[str]:
    """An orchestra square's hand-off or (`back`) its answer, as a talk between the caller and the square's node."""
    try:
        from halo_harness.agent.agent_registry import agent_key, tree_for
        from halo_harness.fleet.talk import on_square
        d = on_square(tree_for(session), agent_key(session), node, ref, text, back=back, re=re)
        return d.get("id") if d else None
    except Exception:
        return None


def session_band(runtime) -> str:
    tc = getattr(runtime, "team_control", None)
    band = (getattr(tc, "budget", None) or {}).get("band") if tc is not None else None
    return band if band in ("low", "mid", "high") else "mid"


class WorkflowTool(Tool):
    name = "Workflow"
    result_cap = None

    @property
    def description(self) -> str:
        try:
            from halo_harness.workflows.registry import enabled_squares
            on = enabled_squares(self.lineup)
        except Exception:
            on = []
        tail = (" Enabled squares: " + "; ".join(f"{w.ref} (covers {', '.join(w.contract.covers) or '-'})" for w in on) + "."
                if on else " No square is enabled for this lineup yet (halo workflows enable media).")
        return DESCRIPTION + tail

    lineup = None  # the session's lineup (the router reads the runtime's; this is only the description's)

    @property
    def input_schema(self) -> dict:
        return INPUT_SCHEMA

    def summary(self, input: dict) -> str:
        input = input if isinstance(input, dict) else {}
        return f"Workflow({input.get('name') or input.get('need') or 'auto'}: {str(input.get('task') or '')[:50]})"

    def run(self, input: dict, ctx: ToolContext) -> ToolResult:
        from halo_harness.workflows import receipts, registry, router, square_run
        runtime = ctx.agent_runtime
        if runtime is None:
            return ToolResult("Workflows need a session with agents; this one has none.", is_error=True)
        input = input if isinstance(input, dict) else {}
        task = str(input.get("task") or "").strip()
        if not task:
            return ToolResult("The task parameter is required", is_error=True)
        files = [str(f) for f in input.get("files") or [] if isinstance(f, str) and f.strip()]
        session = runtime.parent
        model_ref = ctx.model_ref or str(getattr(getattr(session, "model_ref", None), "raw", "") or "")
        squares = registry.enabled_squares(_lineup(runtime), cwd=ctx.cwd)
        r = router.route(task, files, name=str(input.get("name") or ""), need=str(input.get("need") or ""),
                         model_ref=model_ref, squares=squares, band=session_band(runtime),
                         hops=getattr(session, "_square_hops", None), remaining=session_remaining(runtime), takes=TAKES,
                         team=getattr(runtime, "team_control", None))
        if r.refused:
            rec = receipts.make(r, None, need=str(input.get("need") or ""), files=files)
            receipts.write(session, rec)
            return ToolResult(receipts.line(rec))
        if r.role:  # 3.3.16.2: the lineup's own role covers it (workflows/lineup_roles.py)
            from halo_harness.workflows.lineup_roles import run_role
            out = run_role(r.role, task, files, runtime=runtime, tool_id=ctx.tool_use_id or "", spawn=SPAWN)
            rec = receipts.make(r, out, need=str(input.get("need") or ""), files=files, engine="role")
            receipts.write(session, rec)
            return ToolResult(receipts.line(rec) + "\n\n" + (out.text or "(the role handed back nothing)"),
                              is_error=out.status == "failed")
        wf = r.square
        engine = wf.contract.run_engine(fleet=False)
        if engine == "session":
            model, _pick = square_run.lead_model(wf, task, files, r.gaps, main_ref=model_ref, state_dir=getattr(session, "state_dir", None))
            out = square_run.run_session(wf, task, files, runtime=runtime, tool_id=ctx.tool_use_id or "", model=model,
                                         cap=r.cap_usd, hops=r.hops, spawn=SPAWN,
                                         on_child=lambda child: receipts.mark_child(session, child, wf.ref, engine))
        else:
            key = receipts.node(session, wf.ref, engine, state="running")
            said = _talk(session, key, wf.ref, task)  # 3.3.16.2: the hand-off and what came back are talk (fleet/talk.py)
            out = square_run.run_orchestra(wf, task, files, repo=ctx.cwd, wall_s=wf.contract.wall_s, runner=RUN_ORCHESTRA)
            _talk(session, key, wf.ref, out.text, back=True, re=said)
            receipts.node(session, wf.ref, engine, state="done" if out.status == "done" else "failed", cost_usd=out.cost_usd, key=key)
            receipts.add_cost(session, wf.ref, out.cost_usd)
        rec = receipts.make(r, out, need=str(input.get("need") or ""), files=files, engine=engine)
        receipts.write(session, rec)
        return ToolResult(receipts.line(rec) + "\n\n" + (out.text or "(the square handed back nothing)"),
                          is_error=out.status == "failed")
