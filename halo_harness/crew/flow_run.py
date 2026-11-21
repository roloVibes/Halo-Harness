"""halo_harness.crew.flow_run -- a session runs a crew workflow by name, with no model asked to (Halo 3.6.0.6 P).

Studio's Run it starts `halo --headless --run-workflow <name> --workflow-task <task>` (studio/crew_flow_api.py
`post_run`); the session queues `run_workflow` on its own command pump (controller.run_workflow) and this runs it
there, between turns, through the Workflow tool's own code: `flow_door.run` on the step runner, the run's group
(tools/workflow.py `_for_run`: Live draws "workflow <name>"), the same receipt in the session's record
(crew/runner_session.py). Main gets no turn and no prompt grows.

    pump(session, data, out)    data = {name, task}; the receipt's first line (or why it did not run) as a notification
"""

from __future__ import annotations

import logging
from types import SimpleNamespace

log = logging.getLogger(__name__)


def pump(session, data: dict, out) -> None:
    from halo_harness import events
    from halo_harness.crew import flow_door
    from halo_harness.tools import workflow as W
    name, task = str(data.get("name") or "").strip(), str(data.get("task") or "").strip()
    runtime = getattr(session, "agent_runtime", None)
    if not name or not task or runtime is None:
        out(events.notification(f"workflow {name or '?'} did not run: it needs a name, a task and a session with agents",
                                level="error"))
        return
    session.abort.clear()
    session._map_asked = True  # noqa: SLF001  it was given work: Live draws it (crew/map_facts.py `asked`, not T10)
    session._busy.set()  # noqa: SLF001  (as /compact's pump: Studio and the terminal see the session busy)
    out(session.status_event())
    try:
        run = W._for_run(runtime, name, SimpleNamespace(tool_use_id=""), {})  # noqa: SLF001  the tool's own group
        got = flow_door.run(run, name, task, cwd=getattr(session, "cwd", None), spawn=W.SPAWN)
        if got is None:
            out(events.notification(f"no workflow named {name} that a session runs (yours, this project's or an "
                                    "enabled pack's)", level="error"))
        else:
            out(events.notification(got[0].splitlines()[0] if got[0] else name, level="error" if got[1] else "info"))
    except BaseException as e:  # never let the worker thread die silently
        log.exception("run_workflow %s failed", name)
        out(events.notification(f"workflow {name} stopped: {type(e).__name__}: {e}", level="error"))
    finally:
        session._end_busy_period()  # noqa: SLF001
        out(session.status_event())
