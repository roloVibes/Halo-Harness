"""halo_harness.crew.runner_session -- the step runner inside a session (Halo 3.6.0.0 R2; crew/runner.py).

    SessionBackend(runtime, tool_id, workflow, does)   what crew/runner.py calls for each agent turn

Each agent is spawned as a child through `agent/subagent.py run_agent_call` (the Agent tool's own path), with the spec
crew/spec.py builds from its file: the child shares the session's permission engine and rules and is never more
permissive than the session (subagent.py clamps it). So Live draws it as it draws every sub-agent (spawn, its turns,
done), each child row tagged as the workflow's (`square: {name, engine: "steps"}`), and the hand-off into the workflow
and what it handed back are talk between the caller and the workflow's node (live/talk.py), the frames Live already
draws. A watcher stops a child (its `abort`) when its cost passes what is left under the caps.

    run_workflow(runtime, name, request, *, cwd, tool_id, files) -> (Result, receipt text)   the Workflow tool's door
"""

from __future__ import annotations

import copy
import re
import threading
import time
from typing import Optional

from halo_harness.crew.runner import Call

WATCH_S = 0.5


class SessionBackend:
    def __init__(self, runtime, tool_id: str, workflow: str, does: str = "", spawn=None, node: str = "") -> None:
        self.runtime, self.tool_id, self.workflow, self.does = runtime, tool_id or "crew", workflow, does
        self.parent = getattr(runtime, "parent", None)
        self.node = node
        self._spawn = spawn
        self._n = 0
        self._lock = threading.Lock()
        self._specs: dict = {}

    def session_left(self) -> "Optional[float]":
        try:
            from halo_harness.tools.workflow import session_remaining
            return session_remaining(self.runtime)
        except Exception:
            return None

    def stopped(self) -> bool:
        ab = getattr(self.parent, "abort", None)
        return bool(ab is not None and getattr(ab, "is_set", lambda: False)())

    def _runtime_for(self, raw: dict):
        """The session's runtime with this agent's crew spec under its name (the workflow's agent, as its file says)."""
        from halo_harness.crew.spec import agent_spec
        name = str(raw.get("name"))
        with self._lock:
            self._specs[name] = agent_spec({k: v for k, v in raw.items() if not str(k).startswith("_")}, source="crew:workflow")
            rt = copy.copy(self.runtime)
            rt.agents = {**(getattr(self.runtime, "agents", None) or {}), **self._specs}
            self._n += 1
            n = self._n
        return rt, n

    def agent(self, raw: dict, prompt: str, *, step: int, limit_usd: "Optional[float]" = None) -> Call:
        spawn = self._spawn
        if spawn is None:
            from halo_harness.agent.subagent import run_agent_call as spawn
        from halo_harness.agent.agent_registry import tree_for
        rt, n = self._runtime_for(raw)
        name = str(raw.get("name"))
        box: dict = {}
        done, stop = threading.Event(), {}

        def _child(child) -> None:
            box["child"] = child
            aid = getattr(child, "agent_id", "")
            box["row"] = (lambda: (tree_for(self.parent).row(aid) or {})) if aid and self.parent is not None else (lambda: {})
            from halo_harness.workflows.receipts import mark_child
            mark_child(self.parent, child, self.workflow, "steps", does=self.does)

        watch = threading.Thread(target=_watch, args=(box, done, limit_usd, stop), daemon=True, name="crew-watch")
        watch.start()
        t0 = time.time()
        tool_input = {"description": f"{self.workflow} step {step}: {name}"[:60], "prompt": prompt, "subagent_type": name}
        try:
            _events, result = spawn(runtime=rt, tool_id=f"{self.tool_id}-s{step}-{n}", tool_input=tool_input,
                                    tool_name="Agent", on_child=_child)
        finally:
            done.set()
        row = (box.get("row") or (lambda: {}))() or {}
        text = unwrap(str(getattr(result, "content", "") or ""))
        err = bool(getattr(result, "is_error", False))
        why = stop.get("why", "")
        return Call(text=text, cost_usd=float(row.get("cost_usd") or 0.0), ok=not err and not why,
                    error=why or (text[:300] if err else ""), seconds=round(time.time() - t0, 1))


_WRAP = re.compile(r"^\s*<task_result[^>]*>\s*(.*?)\s*</task_result>\s*$", re.S)


def unwrap(text: str) -> str:
    """The child's reply without the Agent tool's `<task_result>` wrapper (the next step reads the words)."""
    m = _WRAP.match(text or "")
    return m.group(1).strip() if m else (text or "").strip()


def _watch(box: dict, done: threading.Event, limit: "Optional[float]", stop: dict) -> None:
    if limit is None:
        return
    while not done.wait(WATCH_S):
        r = (box.get("row") or (lambda: {}))() or {}
        if float(r.get("cost_usd") or 0.0) > max(0.0, limit) and box.get("child") is not None:
            stop["why"] = f"stopped at the cap: its cost passed the ${max(0.0, limit):.4f} left"
            getattr(box["child"], "abort").set()
            return


def _talk(session, node: str, ref: str, text: str, back: bool = False, re: Optional[str] = None) -> Optional[str]:
    try:
        from halo_harness.agent.agent_registry import agent_key, tree_for
        from halo_harness.live.talk import on_square
        d = on_square(tree_for(session), agent_key(session), node, ref, text, back=back, re=re)
        return d.get("id") if d else None
    except Exception:
        return None


def run_workflow(runtime, wf: dict, request: str, *, cwd, tool_id: str = "", files=(), spawn=None):
    """Run a crew workflow in this session: the workflow's node under the caller, the hand-off and the result as talk,
    each agent a child. (Result, the receipt's text)."""
    from halo_harness.crew import runner, store
    from halo_harness.workflows import receipts
    session = getattr(runtime, "parent", None)
    name = str(wf.get("name"))
    does = str(wf.get("for") or "")
    key = receipts.node(session, name, "steps", state="running", does=does)
    said = _talk(session, key, name, request)
    backend = SessionBackend(runtime, tool_id, name, does, spawn=spawn, node=key)

    def resolve(agent: str):
        return store.load("agent", agent, cwd=cwd)

    res = runner.run(wf, request, resolve=resolve, backend=backend, files=files)
    _talk(session, key, name, res.text or res.line, back=True, re=said)
    receipts.node(session, name, "steps", state="done" if res.state == "done" else "failed", cost_usd=res.cost_usd, key=key)
    head = (f"crew workflow {name} · ran on the step runner · {res.state} · ${res.cost_usd:.4f} -- {res.line}")
    body = "\n".join(runner.receipt(res))
    _log_receipt(session, name, res, head)
    return res, head + ("\n" + body if body else "") + "\n\n" + (res.text or "(the workflow handed back nothing)")


def _log_receipt(session, name: str, res, head: str) -> None:
    log = getattr(session, "log", None)
    if log is None or not hasattr(log, "_append"):
        return
    try:
        log._append({"type": "receipt", "kind": "workflow", "square": name, "engine": "steps", "status": res.state,
                     "cost_usd": res.cost_usd, "why": res.line, "line": head,
                     "steps": [{k: s.get(k) for k in ("n", "name", "state", "rounds", "stop", "cost_usd")} for s in res.steps]})
    except Exception:
        pass
