"""halo_harness.crew.try_flow -- one Try it run of a workflow, as its own process (Halo 3.6.0.0 R2; crew/trial_flow.py).

    python -m halo_harness.crew.try_flow <spec.json>      spec: {workflow, agents: {name: agent/1}, request, model}

Run in the throwaway copy (its cwd). It builds a print-mode session there (headless.build_session: an ask is answered
no and listed, as in an agent's Try it) whose agents are the workflow's own, as the form and their files hold them
(`--agents` JSON, crew/spec.py), then runs the step runner (crew/runner.py) with each agent a child of that session
(crew/runner_session.py). Each step, agent, check and the end is printed as one JSON line, `{"crew": <kind>, ...}`;
the exit code is 0 when the run is done, 1 otherwise. The session's own mode is the most permissive of its agents'
careful modes, so each child gets its own (subagent.py never lets a child above its parent).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RANK = ("default", "acceptEdits", "auto")


def _say(kind: str, data: dict) -> None:
    sys.stdout.write(json.dumps({"crew": kind, **data}, ensure_ascii=False, default=str) + "\n")
    sys.stdout.flush()


def main(argv: list) -> int:
    from halo_harness.crew import runner
    from halo_harness.crew.runner_session import SessionBackend
    from halo_harness.crew.spec import MODES, agents_json
    spec = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    wf, agents, request = spec["workflow"], spec.get("agents") or {}, str(spec.get("request") or "")
    bad, _found = runner.preflight(wf, lambda n: agents.get(n))
    if bad:  # before any session or model call: the problem lines
        res = runner.run(wf, request, resolve=lambda n: agents.get(n), backend=None, emit=_say)
        return 0 if res.state == "done" else 1
    table: dict = {}
    for raw in agents.values():
        table.update(agents_json(raw))
    mode = max((MODES.get(a.get("careful"), "default") for a in agents.values()), key=RANK.index, default="default")
    from halo_harness import headless
    build = headless.build_session(cwd=Path.cwd(), model_ref_raw=spec.get("model") or None, print_mode=True,
                                   permission_mode=mode, agents_flag=json.dumps(table))
    try:
        rt = build.session.agent_runtime
        backend = SessionBackend(rt, "try", str(wf.get("name")), str(wf.get("for") or ""))
        res = runner.run(wf, request, resolve=lambda n: agents.get(n), backend=backend, emit=_say)
    finally:
        if build.mcp_manager is not None:
            try:
                build.mcp_manager.close_all()
            except Exception:
                pass
    return 0 if res.state == "done" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
