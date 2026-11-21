"""halo_harness.crew.session_start -- what a new top session's start sets, in ONE place (3.6.0.10 MW, rule M1), so
the measure (`agent/prompt_measure.first_turn`) and a real session (`agent/loop.Session.__init__`) cannot differ:

    start_control(crew_map, *, cwd, state_dir=None, session=None)  the session's control: a MapControl / PlainMap on a
                                                                    map, a plain session's answers with none, None with
                                                                    roles off ("One model for everything")
    tool_state(session, control)                                    the Agent, Task and Workflow tools' `lineup` and
                                                                    `map_control`; the runtime's `team_control`;
                                                                    on Auto the Agent and Task tools' `kinds_tail` (M8)
                                                                    and the Builder's `on_auto` (MW batch 4)
    start_agents(cwd, compiled, *, settings=None)                   the agents a new session gets (Studio's hand_to too)
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
    from halo_harness.agent.helpers_words import kinds_tail, on_auto  # 3.6.0.10 M8: on Auto, the kinds end the Agent/Task words
    said = kinds_tail(session)
    for name in ("Agent", "Task"):
        tool = registry.get(name) if registry is not None else None
        if tool is not None:
            tool.kinds_tail = said
    builder = registry.get("Builder") if registry is not None else None
    if builder is not None:  # 3.6.0.10 MW batch 4: its "when" sentence, chosen once: on Auto main may also propose
        builder.on_auto = on_auto(session)


def start_agents(cwd, compiled, *, settings=None) -> dict:
    """The agents a new session in `cwd` discovers (packs' included), on a map merged with the map's own (`compiled`,
    None: no map), as headless.build_session gives its runtime; Studio's "Main can hand work to" reads the same (M9)."""
    from halo_harness.config.agents_md import discover_agents
    from halo_harness.crew import map_session
    from halo_harness.packs.contribute import pack_plugin_roots
    try:
        roots = pack_plugin_roots(cwd=cwd)
    except Exception:
        roots = []
    agents = discover_agents(cwd, settings=settings, plugin_roots=(roots or None))
    if compiled is not None:
        agents, _targets = map_session.agents(agents, compiled)
    return agents


def new_session_state(session, *, cwd, control=None):
    """A NEW top session's state in `cwd` on `session` (a stub with `tool_registry`, `settings`, `state_dir`), as
    headless.build_session and Session.__init__ set it: the map (`control` is what `--map` would name; None: the
    folder's own, as a session started with no flag), its control, the agents a session discovers (packs' included,
    on a map merged with the map's own), depth 0, no restriction, and the tools' state."""
    from halo_harness.agent.subagent import AgentRuntime
    from halo_harness.crew import map_session
    compiled, _said = map_session.prepare({"map": control} if control else None, cwd)
    agents = start_agents(cwd, compiled, settings=getattr(session, "settings", None))
    session.agent_runtime = AgentRuntime(parent=session, agents=agents, depth=0)
    session.agent_type_restriction = None
    session.team_control = start_control(compiled, cwd=cwd, state_dir=getattr(session, "state_dir", None),
                                         session=session)
    tool_state(session, session.team_control)
    return session
