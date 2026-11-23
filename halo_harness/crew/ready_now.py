"""halo_harness.crew.ready_now -- after a Builder card is applied in a session on Auto, what it saved is ready in this
session now and what waits for the next session (Halo 3.6.0.5, the true lines: C18 to C22).

`ready_and_later(session, wrote)` reads three things and nothing else: the session's tool registry, the agents the
session started with and the crew store. It keeps nothing on the session and starts nothing (no watcher, no timer, no
thread, no network call). Only a session on Auto -- its own control, or its top session's, is the plain map
(crew/map_control.py `PlainMap`) -- gets an answer; any other session gets None, and so do a fault and a raise.

- A workflow W the card wrote is READY when the session holds the Workflow tool and crew/flow_door.py `named(W, cwd)`
  (the very call the Workflow tool makes) finds the file the card wrote. With no Workflow tool it waits (WF), but only
  when the offer's drop is the reason: when the session's own rules leave the tool out, no line at all. When
  `named(W)` finds another file (the project's own W runs first) it gets P3. When it finds nothing: no line at all
  rather than a line that may be false.
- An agent x the card wrote is READY when crew/session_tool.py `finish` put it into the session and the put took
  (crew/use_now.py, 3.6.0.15 U4: `took`); main can start it at its very next model call. A put that was refused waits
  with the put's why (TOOL, MODE, BUILTIN, AG2 for a name the session keeps, else AG1). An agent no put was made for
  (a caller that passes no `took`) waits: AG2 when the session started with an agent named x, else AG1. When x waits
  and is a step of a ready workflow and the step runner's own lookup (`store.load("agent", x, cwd=cwd)`,
  crew/runner_session.py) reads the card's file, the step clause is added.

`p_lines(answer)` writes the lines a person and main read (P1: the ready workflows, then the ready agents; P2; P3),
in that order. The words are the constants
below; the terminal (tui/dispatch.py READY_FIRST_WORDS) and Studio pin their copies to them.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

FIRST_WORDS = ("Ready in this session now:", "Saved for your next session:", "Not run under its name:")
P1 = FIRST_WORDS[0] + " {items}."
P1_ITEM = "the workflow {W}"
P1_AGENT = "the agent {x} (subagent_type `{x}`)"
P2 = FIRST_WORDS[1] + " the {kind} {name} ({why}{step})."
P3 = FIRST_WORDS[2] + " the workflow {W} (this project has its own workflow {W}, which runs first)."
WHY = {"WF": "this session started with no workflow, so it has no Workflow tool",
       "AG1": "this session's list of agents was fixed when it started",
       "AG2": "this session keeps the {name} it started with",
       "TOOL": "it asks for {tool}, which this session's main does not have",
       "MODE": "it asks for a mode above this session's",
       "BUILTIN": "a built-in has that name"}
STEP = "; as a step of the workflow {W} it can run now"


def _owner(session):
    """The session on Auto whose registry and agents count: `session` itself, else its top session. The top is asked
    only when the session is already in an agent tree (a session with none is its own top), so nothing is made."""
    from halo_harness.crew.map_control import PlainMap
    if session is None:
        return None
    if isinstance(getattr(session, "team_control", None), PlainMap):
        return session
    if getattr(session, "_agent_tree", None) is None:
        return None
    from halo_harness.crew.map_events import _top
    top = _top(session)
    if top is not None and isinstance(getattr(top, "team_control", None), PlainMap):
        return top
    return None


def _rules_leave_out_workflow(owner) -> bool:
    """True when the session's OWN rules keep the Workflow tool out, so WF's reason ("started with no workflow") is not
    the true one and no line is given (r/batch05): read from what the session recorded at its start -- a bare deny rule
    on its permission engine (settings or --disallowedTools; Agent or Task take Workflow too, permissions.py
    bare_deny_tool_names), its `--tools` list (cli_flags), a worker's capabilities (isolation/capabilities.py
    session_caps, the call narrow_session made). Only the offer's drop (workflows/offer.py) leaves this False."""
    from halo_harness.isolation.capabilities import allowed, session_caps
    from halo_harness.permissions import bare_deny_tool_names, split_tool_rule_list
    engine = getattr(owner, "permission_engine", None)
    if "Workflow" in bare_deny_tool_names(list(getattr(engine, "deny_rules", None) or [])):
        return True
    tools = (getattr(owner, "cli_flags", None) or {}).get("tools")
    if isinstance(tools, str) and tools.strip().lower() != "default" and "Workflow" not in split_tool_rule_list(tools):
        return True
    caps = session_caps(team=None, agent=None)[0]
    return caps is not None and not allowed("Workflow", caps)


def _steps_hold(body: dict, name: str) -> bool:
    for step in (body or {}).get("steps") or []:
        if isinstance(step, dict) and name in (step.get("agents") or []):
            return True
    return False


def _why_of(code: str) -> dict:
    """A refused put's why (crew/use_now.py `put`) -> the P2 why: {why, tool?}."""
    code = str(code or "")
    if code.startswith("tool:"):
        return {"why": "TOOL", "tool": code[len("tool:"):]}
    return {"why": {"mode": "MODE", "built-in": "BUILTIN", "outranked": "AG2"}.get(code, "AG1")}


def ready_and_later(session, wrote, took=None) -> Optional[dict]:
    """`{ready: [W], ready_agents: [x], later: [{kind, name, why, tool?, step?}], p3: [W]}` for the agents and
    workflows in `wrote` (paths), each list in written order; `took` is {x: (took, why)} of the puts `finish` made
    (3.6.0.15 U4). None off Auto or on any fault (a fault never stops a card)."""
    try:
        owner = _owner(session)
        if owner is None:
            return None
        from halo_harness.crew import store
        from halo_harness.crew.flow_door import named
        from halo_harness.crew.session_tool import _same_path
        cwd = getattr(owner, "cwd", None)
        seen: set = set()
        flows: list = []
        agents: list = []
        for p in wrote or []:
            p = Path(p)
            key = _same_path(p)
            if key in seen:
                continue
            seen.add(key)
            if p.parent.name == store.KINDS["workflow"]:
                flows.append((p.stem, key))
            elif p.parent.name == store.KINDS["agent"]:
                agents.append((p.stem, key))
        reg = getattr(owner, "tool_registry", None)
        has_tool = reg is not None and reg.get("Workflow") is not None
        wf = not has_tool and not _rules_leave_out_workflow(owner)  # WF only when its words name the reason
        ready: list = []
        bodies: dict = {}
        later: list = []
        p3: list = []
        for w, key in flows:
            if not has_tool:
                later += [{"kind": "workflow", "name": w, "why": "WF"}] if wf else []
                continue
            got = named(w, cwd)
            if got is None:
                continue
            if got.get("_path") and _same_path(got["_path"]) == key:
                ready.append(w)
                bodies[w] = got
            else:
                p3.append(w)
        start = getattr(getattr(owner, "agent_runtime", None), "agents", None) or {}
        ready_agents: list = []
        for x, key in agents:
            put = (took or {}).get(x)
            if put is not None and put[0]:
                ready_agents.append(x)
                continue
            item = {"kind": "agent", "name": x, **(_why_of(put[1]) if put is not None else
                                                     {"why": "AG2" if x in start else "AG1"})}
            step = next((w for w in ready if _steps_hold(bodies[w], x)), None)
            if step is not None:
                spec = store.load("agent", x, cwd=cwd)
                if isinstance(spec, dict) and spec.get("_path") and _same_path(spec["_path"]) == key:
                    item["step"] = step
            later.append(item)
        return {"ready": ready, "ready_agents": ready_agents, "later": later, "p3": p3}
    except Exception:
        return None


def p_lines(answer) -> list:
    """The lines for one answer: P1 once (the ready workflows, then the ready agents), one P2 per item that waits, one
    P3 per workflow the project's own file of that name runs before; [] for None."""
    if not answer:
        return []
    out = []
    items = ([P1_ITEM.format(W=w) for w in answer.get("ready") or []]
             + [P1_AGENT.format(x=x) for x in answer.get("ready_agents") or []])
    if items:
        out.append(P1.format(items=", ".join(items)))
    for it in answer.get("later") or []:
        why = WHY[it["why"]].format(name=it["name"], tool=it.get("tool") or "")
        step = STEP.format(W=it["step"]) if it.get("step") else ""
        out.append(P2.format(kind=it["kind"], name=it["name"], why=why, step=step))
    for w in answer.get("p3") or []:
        out.append(P3.format(W=w))
    return out
