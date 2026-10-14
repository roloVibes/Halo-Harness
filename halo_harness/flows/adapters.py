"""halo_harness.flows.adapters -- what the flow runner calls out to.

    Adapters(model=None, auto_accept=False, poll_s=0.5, render_timeout_s=1800,
             state_dir=None, cwd=None, comfy_url=None, feed=None,
             one_shot=None, run_org=None, comfy_client=None, answer_gate=None)

* `one_shot(role, prompt, model) -> {text, cost_usd, ok, error}`: one turn
  of a brand-new bare session with no tools (orchestra/adapters.one_shot).
* `run_org(org_name, goal, budget_usd, on_event, approval_sink) -> {text,
  cost_usd, positions: {title: {text}}, is_error}`: the org runs in-process
  (`agent.subagent.run_org_call`) on a worker thread from a bare session
  (`headless.build_session(bare=True)`) with `_subagent_live_asks = True`,
  so an approval-gated position's `approval_request` reaches `approval_sink
  ({id, position, text, is_error}) -> {action: accept|edit|stop,
  instruction}`, and the answer goes back through `session.resolve_approval`.
  The org's `budget_usd` becomes min(the org's, the step's). `on_event(text,
  data)` gets one line per position start/finish. Each position's final
  text is read off the Agent tool results the run streams.
* `comfy_client()`: a `ComfyClient` for `comfy_url` or `resolve_url()`.
* `answer_gate(gate)`: tests only -- called right after a gate opens.
* `feed(Event)`: the session-feed sink for `flow_*` events (Studio, R5).

Every one of these can be replaced by passing a callable; tests always do.
"""

from __future__ import annotations

import os
import re
import threading
from pathlib import Path
from typing import Callable, Optional

ROLE_FLAGS = ("orchestrator", "planner", "coder", "reviewer", "judge", "researcher", "tester", "small",
              "subagent_default")


class Adapters:
    def __init__(self, *, model: Optional[str] = None, auto_accept: bool = False, poll_s: float = 0.5,
                 render_timeout_s: float = 1800, state_dir=None, cwd=None, comfy_url: Optional[str] = None,
                 feed: Optional[Callable] = None, one_shot: Optional[Callable] = None,
                 run_org: Optional[Callable] = None, comfy_client: Optional[Callable] = None,
                 answer_gate: Optional[Callable] = None):
        self.model, self.auto_accept, self.poll_s = model, bool(auto_accept), float(poll_s)
        self.render_timeout_s, self.state_dir, self.comfy_url = float(render_timeout_s), state_dir, comfy_url
        self.cwd = str(cwd or os.getcwd())
        self.feed, self.answer_gate = feed, answer_gate
        self._one_shot, self._run_org, self._comfy = one_shot, run_org, comfy_client

    # ---- models ----------------------------------------------------------------------------
    def one_shot(self, role: str, prompt: str, model: Optional[str]) -> dict:
        if self._one_shot is not None:
            return self._one_shot(role, prompt, model)
        from halo_harness.orchestra.adapters import one_shot, role_model
        return one_shot(prompt, model=role_model(role, model), cwd=Path(self.cwd))

    def run_org(self, org_name: str, goal: str, budget_usd: Optional[float], on_event: Callable,
                approval_sink: Callable) -> dict:
        if self._run_org is not None:
            return self._run_org(org_name, goal, budget_usd, on_event, approval_sink)
        return real_run_org(org_name, goal, budget_usd, on_event, approval_sink, model=self.model,
                            cwd=Path(self.cwd))

    # ---- ComfyUI ---------------------------------------------------------------------------
    def comfy_client(self):
        if self._comfy is not None:
            return self._comfy()
        from halo_harness.media.comfy_client import ComfyClient, resolve_url
        return ComfyClient(self.comfy_url or resolve_url(), timeout=60)


_TASK_RESULT = re.compile(r"^\s*<task_result[^>]*>\s*(.*?)\s*</task_result>\s*$", re.S)


def unwrap(text: str) -> str:
    """A position's text without the `<task_result task_id=...>` wrapper the Agent tool adds."""
    m = _TASK_RESULT.match(str(text or ""))
    return (m.group(1) if m else str(text or "")).strip()


def org_for_run(org_name: str, budget_usd: Optional[float]) -> dict:
    """The org definition with `budget_usd` = min(the org's own, the step's)."""
    from halo_harness.orgs import load_org
    org = load_org(org_name)
    if org is None:
        raise RuntimeError(f"org {org_name!r} is not found or does not validate")
    org = dict(org)
    if budget_usd is not None:
        own = org.get("budget_usd")
        org["budget_usd"] = min(float(own), float(budget_usd)) if isinstance(own, (int, float)) else float(budget_usd)
    return org


def run_org_on(session, org_name: str, org: dict, goal: str, on_event: Callable, approval_sink: Callable) -> dict:
    """Run `org` from `session` (its caller) on a worker thread; see the module docstring."""
    from halo_harness.agent.subagent import run_org_call
    from halo_harness.orgs import root_position
    session._subagent_live_asks = True
    names: dict = {}
    positions: dict = {}

    def sink(ev) -> None:
        kind, data = getattr(ev, "kind", ""), getattr(ev, "data", {}) or {}
        if kind == "tool_use_ready" and data.get("name") in ("Agent", "Task") and isinstance(data.get("input"), dict):
            names[data.get("id")] = str(data["input"].get("subagent_type") or "")
        elif kind == "tool_result" and data.get("id") in names and names[data.get("id")]:
            positions[names[data["id"]]] = {"text": unwrap(data.get("content") or data.get("summary") or "")}
        elif kind in ("subagent_start", "subagent_end"):
            word = "started" if kind == "subagent_start" else ("failed" if data.get("is_error") else "finished")
            on_event(f"{data.get('name')} {word}", {"agent_id": data.get("agent_id")})
        elif kind == "approval_request":
            decision = approval_sink({"id": data.get("id"), "position": data.get("position"),
                                      "text": data.get("text"), "is_error": data.get("is_error")})
            session.resolve_approval(data.get("id"), decision or {"action": "stop"})

    box: dict = {}

    def work() -> None:
        try:
            _events, box["result"] = run_org_call(
                runtime=session.agent_runtime, tool_id="flow-org", tool_name="Agent",
                tool_input={"org": org_name, "prompt": goal, "description": f"Run org {org_name}"},
                on_event=sink, org_override=org)
        except BaseException as e:  # reported below, never lost on the worker thread
            box["error"] = e

    t = threading.Thread(target=work, name=f"flow-org-{org_name}", daemon=True)
    t.start()
    t.join()
    if "error" in box:
        raise RuntimeError(f"org {org_name}: {type(box['error']).__name__}: {box['error']}")
    result = box.get("result")
    text = unwrap(getattr(result, "content", "") or "")
    root = root_position(org)
    if root is not None:
        positions[root["title"]] = {"text": text}
    cost = float(session.cost_meter.total_usd or 0.0) if getattr(session, "cost_meter", None) else 0.0
    return {"text": text, "cost_usd": cost, "positions": positions, "is_error": bool(getattr(result, "is_error", False))}


def real_run_org(org_name: str, goal: str, budget_usd: Optional[float], on_event: Callable,
                 approval_sink: Callable, *, model: Optional[str], cwd: Path) -> dict:
    from halo_harness import headless
    org = org_for_run(org_name, budget_usd)
    roles_flag = [f"{r}={model}" for r in ROLE_FLAGS] if model else None
    build = headless.build_session(cwd=cwd, bare=True, print_mode=True, model_ref_raw=model, roles_flag=roles_flag,
                                   permission_mode="auto")
    session = build.session
    try:
        return run_org_on(session, org_name, org, goal, on_event, approval_sink)
    finally:
        for close in (lambda: session._fire_session_end("other"), session.job_registry.kill_all,
                      getattr(build.mcp_manager, "close_all", lambda: None)):
            try:
                close()
            except Exception:
                pass
