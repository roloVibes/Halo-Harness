"""halo_harness.crew.session_start -- what a new top session's start sets, in ONE place (3.6.0.10 MW, rule M1), so
the measure (`agent/prompt_measure.first_turn`) and a real session (`agent/loop.Session.__init__`) cannot differ:

    start_control(crew_map, *, cwd, state_dir=None, session=None)  the session's control: a MapControl / PlainMap on a
                                                                    map, a plain session's answers with none, None with
                                                                    roles off ("One model for everything")
    tool_state(session, control)                                    the Agent, Task and Workflow tools' `lineup` and
                                                                    `map_control`; the runtime's `team_control`
    new_session_state(session, *, cwd, control=None)                a NEW top session's state on a stub: its control,
                                                                    its agents (as headless.build_session finds them),
                                                                    no restriction, the tools' state above
"""

from __future__ import annotations


def start_control(crew_map, *, cwd=None, state_dir=None, session=None):
    """The control a top-level, non-bare session holds (3.6.0.0 R5b): on a map, a MapControl (a map you chose) or a
    PlainMap (the default map); with no map, a plain session's answers (crew/plain.py), or None with roles off."""
    if crew_map is not None:  # 3.6.0.0 R3: a session on a map holds it where a lineup was (crew/map_control.py)
        from halo_harness.crew.map_control import control_for
        return control_for(crew_map, cwd=cwd, state_dir=state_dir, session=session)
    from halo_harness.crew.compile import in_use
    from halo_harness.crew.plain import load
    return load() if in_use(None, cwd)[0] else None


def tool_state(session, control) -> None:
    """What the start sets on the session's tools and runtime for `control` (None: roles off)."""
    from halo_harness.crew.compile import is_default
    # 3.6.0.0 R5 fix: on the default map the tools describe themselves as a plain session's did (no map tail)
    held = control if getattr(control, "is_map", False) and not is_default(getattr(control, "map", None)) else None
    registry = getattr(session, "tool_registry", None)
    # 3.1.9.0 R2: the Agent tool's description says when the lineup is `auto`
    for name in ("Agent", "Task", "Workflow"):  # 3.3.16.0 R3: Workflow lists the lineup's squares
        tool = registry.get(name) if registry is not None else None
        if tool is not None:
            tool.lineup = getattr(control, "name", None)
            tool.map_control = held
    runtime = getattr(session, "agent_runtime", None)
    if control is not None and runtime is not None:
        runtime.team_control = control


def new_session_state(session, *, cwd, control=None):
    """A NEW top session's state in `cwd` on `session` (a stub with `tool_registry`, `settings`, `state_dir`), as
    headless.build_session and Session.__init__ set it: the map (`control` is what `--map` would name; None: the
    folder's own, as a session started with no flag), its control, the agents a session discovers (packs' included,
    on a map merged with the map's own), depth 0, no restriction, and the tools' state."""
    from halo_harness.agent.subagent import AgentRuntime
    from halo_harness.config.agents_md import discover_agents
    from halo_harness.crew import map_session
    from halo_harness.packs.contribute import pack_plugin_roots
    compiled, _said = map_session.prepare({"map": control} if control else None, cwd)
    try:
        roots = pack_plugin_roots(cwd=cwd)
    except Exception:
        roots = []
    agents = discover_agents(cwd, settings=getattr(session, "settings", None), plugin_roots=(roots or None))
    if compiled is not None:
        agents, _targets = map_session.agents(agents, compiled)
    session.agent_runtime = AgentRuntime(parent=session, agents=agents, depth=0)
    session.agent_type_restriction = None
    session.team_control = start_control(compiled, cwd=cwd, state_dir=getattr(session, "state_dir", None),
                                         session=session)
    tool_state(session, session.team_control)
    return session
