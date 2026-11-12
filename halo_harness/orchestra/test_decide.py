"""halo_harness.orchestra.test_decide -- a test command a project file wrote, decided as a Bash call (Halo 3.4.1.2,
ENGINE-1).

A goal's `test` that came from a project's workflow file (each stage's `verify.test`) or a project lineup's
`acceptance.test` is repo text; before 3.4.1.2 the gate ran it with `shell=True` past every rule. `gate.run_tests`
now asks first, as the Bash call it is: the armed pack policies, the deny / ask / allow rules of the repo's settings
(trust-filtered as a session there builds them) plus the rules the run carries (a Workflow run: the parent's), the
run's permission mode, then the PreToolUse and PermissionRequest hooks. Only an allow runs it; a deny or an ask (no
one answers a card inside the gate) is the test's failing result, with the line.

    origin(goal) -> "" | the file that wrote the test
    decide(command, *, cwd, mode="auto", rules=None) -> (action, line)
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional


def origin(goal) -> str:
    return str(getattr(goal, "test_from", "") or "")


def _engine(cwd: Path, mode: str, rules: Optional[dict]):
    from halo_harness.config.settings import resolve_settings
    from halo_harness.permissions import PermissionEngine, build_rules_from_settings, parse_rule
    from halo_harness.project_gate import trusted
    settings = resolve_settings(cwd, trusted=trusted(cwd))
    deny, ask, allow = build_rules_from_settings(settings, cwd=cwd)
    extra = rules if isinstance(rules, dict) else {}
    parsed = {k: [parse_rule(str(r), source="run", base_dir=cwd, action=k) for r in extra.get(k) or []
                  if isinstance(r, str)] for k in ("deny", "ask", "allow")}
    engine = PermissionEngine(deny_rules=deny + parsed["deny"], ask_rules=ask + parsed["ask"],
                              allow_rules=allow + parsed["allow"], mode=mode or "auto", cwd=cwd, print_mode=True)
    hooks = None
    try:
        from halo_harness.headless import build_hook_runner
        hooks = build_hook_runner(settings=settings, cwd=cwd, session_id="orchestra-gate", transcript_path="",
                                  effort=None, permission_mode=mode or "auto", mcp_manager=None, bare=False)
    except Exception:
        hooks = None
    return engine, hooks


def _hook(hooks, event: str, tool_input: dict):
    if hooks is None or not hooks.has_hooks(event):
        return None
    extra = {"tool_name": "Bash", "tool_input": tool_input, "tool_use_id": "orchestra-test"}
    return hooks.run(event, hooks.payload(event, extra=extra), matched="Bash", tool_name="Bash", tool_input=tool_input)


def decide(command: str, *, cwd, mode: str = "auto", rules: Optional[dict] = None) -> "tuple[str, str]":
    """(allow | ask | deny, the reason) for `command` run as Bash in `cwd` under `mode`."""
    from halo_harness.agent import policy_gate as G
    from halo_harness.permissions import Decision
    cwd = Path(cwd)
    tool_input = {"command": str(command)}
    try:
        engine, hooks = _engine(cwd, mode, rules)
    except Exception as e:  # the settings did not read: nothing decides it, so it does not run
        return "deny", f"the rules here did not read ({type(e).__name__}: {e})"
    w = G.before("Bash", tool_input, cwd=cwd, session="", agent="orchestra:gate", permission_mode=mode or "auto")
    if w is not None and w.action == "deny":
        return "deny", G.said(w)
    d = engine.decide("Bash", tool_input)
    if w is not None and w.action == "ask" and d.action != "deny":
        d = Decision("ask", G.said(w), source=w.source)
    if d.action == "deny":
        return "deny", d.reason
    pre = _hook(hooks, "PreToolUse", tool_input)
    if pre is not None:
        if pre.blocked:
            return "deny", f"a PreToolUse hook blocked it: {pre.block_reason or 'blocked'}"
        if pre.updated_input is not None and pre.updated_input != tool_input:
            return "ask", "a PreToolUse hook rewrote it, and the rewrite is not run unseen"
        if pre.permission_decision in ("allow", "deny", "ask") and G.hook_may(d, pre.permission_decision):
            d = Decision(pre.permission_decision, pre.permission_decision_reason or
                         f"{pre.permission_decision}ed by a PreToolUse hook", source="hook")
    if d.action == "ask":
        req = _hook(hooks, "PermissionRequest", tool_input)
        if req is not None and req.permission_decision in ("allow", "deny") and G.hook_may(d, req.permission_decision):
            d = Decision(req.permission_decision, req.permission_decision_reason or "answered by a PermissionRequest hook",
                         source="hook")
    return d.action, d.reason


def refused(goal, cwd) -> str:
    """'' when the goal's test may run (it is yours, or its Bash decision is allow); else the one line."""
    where = origin(goal)
    command = str(getattr(goal, "test", "") or "").strip()
    if not where or not command:
        return ""
    action, why = decide(command, cwd=cwd, mode=str(getattr(goal, "permission_mode", "") or "auto"),
                         rules=getattr(goal, "permission_rules", None))
    if action == "allow":
        return ""
    return (f"the test command {command!r} came from {where} and was not run: as a Bash call it is {action} "
            f"({why}); allow it with a rule such as Bash({command.split()[0] if command.split() else ''}:*), "
            "or run it yourself")
