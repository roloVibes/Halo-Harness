"""tests.test_kinds_start -- 3.6.0.10 MW rule M3: every name main is told can really be started. In seven homes built as
headless.build_session builds a session's agents (the map it prepares, the agents it discovers, packs' included, an
`--agent` session's restriction), each name crew/kinds.py lists goes through the Agent tool of a real Session on a
scripted loopback provider and registers a child: never "Unknown subagent_type", never "may not spawn". A wrong name's
error names every listed one. A scratch home per home (tests/helpers/packs_home.py), the variables restored; the
loopback mock ends in a `finally`; no real model, no network.
Run: python -m tests.test_kinds_start
"""
from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
SCN = "kinds-start-child"
WRONG = "no-such-helper"


@contextmanager
def _home():
    """A scratch home (PacksHome restores every BRIDGE_/HALO_/provider variable), Ollama on a dead port, a believable
    OpenRouter key for the loopback mock, the mock's scenario removed afterwards."""
    from tests.helpers.mock_openai import SCENARIOS, MockUpstream, _finish
    saved = os.environ.get("OLLAMA_HOST")
    os.environ["OLLAMA_HOST"] = "http://127.0.0.1:9"
    mock = None
    try:
        with PacksHome() as h:
            os.environ["OPENROUTER_API_KEY"] = "sk-or-test-default"
            os.environ["HALO_NO_UPDATER"] = "1"
            SCENARIOS[SCN] = lambda hd, _b: _finish(hd, [
                {"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
                {"choices": [{"index": 0, "delta": {"content": "child done"}}]},
                {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}])
            mock = MockUpstream().start()
            h.mock = mock
            h.repo.mkdir(parents=True, exist_ok=True)
            yield h
    finally:
        if mock is not None:
            mock.stop()
        SCENARIOS.pop(SCN, None)
        if saved is None:
            os.environ.pop("OLLAMA_HOST", None)
        else:
            os.environ["OLLAMA_HOST"] = saved


def _start(h, *, agent: str = ""):
    """(agents, map, restriction) as headless.build_session finds them; `agent` is `--agent <name>` (no map then)."""
    from halo_harness.config.agents_md import discover_agents
    from halo_harness.crew import map_session
    from halo_harness.packs.contribute import pack_plugin_roots
    discovered = discover_agents(h.repo, settings=None, plugin_roots=(pack_plugin_roots(cwd=h.repo) or None))
    if agent:
        return discovered, None, discovered[agent].allowed_subagent_types()
    compiled = map_session.prepare(None, h.repo)[0]
    agents = map_session.agents(discovered, compiled)[0] if compiled is not None else discovered
    return agents, compiled, None


def _session(h, agents, compiled, restriction):
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.loop import Session
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.providers.stream import ProviderCreds
    from halo_harness.tools.registry import ToolRegistry, default_tools
    ref = f"or:mock/{SCN}"
    ctx = SessionContext(cwd=h.repo, model_label=ref, tool_registry=ToolRegistry(default_tools()))
    return Session(cwd=h.repo, model_ref=parse_model_ref(ref), model_profile=ModelProfile(),
                   creds=ProviderCreds(base_url=h.mock.base_url, api_key="k"), state_dir=h.state, model_label=ref,
                   session_context=ctx, openrouter_base_url=h.mock.base_url, max_turns=5, agents=agents,
                   crew_map=compiled, agent_type_restriction=restriction)


def _call(session, name: str, n: int):
    tu = {"type": "tool_use", "id": f"call_{n}", "name": "Agent",
          "input": {"description": "check it", "prompt": "say done", "subagent_type": name,
                    "model": f"or:mock/{SCN}"}}  # the call's own model: every child on the loopback mock
    events = list(session._dispatch_tools(1, [tu]))
    result = next((e for e in events if e.kind == "tool_result"), None)
    started = [e for e in events if e.kind == "subagent_start"]
    return result, started


def _every_name_starts(ctx: Ctx, label: str, h, *, agent: str = "", want=None) -> list:
    from halo_harness.crew.kinds import kinds, names
    agents, compiled, restriction = _start(h, agent=agent)
    listed = names(kinds(agents, restriction))
    if want is not None:
        ctx.check(f"{label}: the list is {want}, got {listed}", listed == want)
    session = _session(h, agents, compiled, restriction)
    for i, name in enumerate(listed):
        result, started = _call(session, name, i)
        text = str((result.data if result else {}).get("content") or (result.data if result else {}).get("summary") or "")
        ctx.check(f"{label}: {name} starts (a child registered), got {text[:160]!r}",
                  result is not None and result.data.get("ok") is True and len(started) == 1
                  and "Unknown subagent_type" not in text and "may not spawn" not in text)
    result, _started = _call(session, WRONG, len(listed))
    data = result.data if result else {}
    text = f"{data.get('summary') or ''} {data.get('content') or ''}"
    ctx.check(f"{label}: a wrong name is refused and its error names every listed one, got {text[:200]!r}",
              data.get("ok") is False and all(n in text for n in listed))
    return listed


def _his(h, name: str, does: str, *, project: bool = False) -> None:
    folder = (h.repo / ".halo" / "crew" / "agents") if project else (h.state / "crew" / "agents")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.yaml").write_text(f"format: agent/1\nname: {name}\ndoes: {does}\nmodel: auto\nuses:\n- read\n"
                                         "careful: ask-changes\n", encoding="utf-8")


@test
def test_a_clean_home(ctx: Ctx):
    with _home() as h:
        _every_name_starts(ctx, "clean", h, want=["planner", "researcher", "coder", "reviewer", "writer",
                                                  "media-reader", "ops", "Judge", "Tester"])


@test
def test_his_crew_agents_yours_and_a_trusted_projects(ctx: Ctx):
    from tests.helpers.trust_dir import trust
    with _home() as h:
        _his(h, "sorter", "Sorts the inbox by sender and date.")
        _his(h, "tidier", "Tidies the notes folder.", project=True)
        trust(h.repo)
        listed = _every_name_starts(ctx, "his crew agents", h)
        ctx.check(f"his two lead, got {listed[:2]}", set(listed[:2]) == {"sorter", "tidier"})


@test
def test_forty_claude_code_agents(ctx: Ctx):
    with _home() as h:
        folder = h.home / ".claude" / "agents"
        folder.mkdir(parents=True, exist_ok=True)
        for i in range(40):
            (folder / f"cc-{i:02d}.md").write_text(f"---\nname: cc-{i:02d}\ndescription: Helper number {i}.\n---\n"
                                                   f"You are helper {i}.\n", encoding="utf-8")
        listed = _every_name_starts(ctx, "40 Claude Code agents", h)
        ctx.check(f"all 40 listed, got {len(listed)} names", sum(n.startswith("cc-") for n in listed) == 40)


@test
def test_a_packs_agents(ctx: Ctx):
    with _home() as h:
        h.install(h.source("doc-review"), enable=True)
        listed = _every_name_starts(ctx, "a pack's", h)
        ctx.check(f"the pack's crew agents are listed, got {listed}",
                  any(n.startswith("doc-review--") for n in listed))


@test
def test_roles_off(ctx: Ctx):
    from halo_harness.theme import set_config_value
    with _home() as h:
        set_config_value("roles.enabled", False)
        _every_name_starts(ctx, "roles off", h,
                           want=["Explore", "Plan", "Coder", "Reviewer", "Researcher", "Judge", "Tester"])


@test
def test_his_own_coder_and_explore(ctx: Ctx):
    with _home() as h:
        _his(h, "coder", "Writes code the way this house does.")
        _his(h, "explore", "Finds where things are.")
        listed = _every_name_starts(ctx, "his coder and explore", h)
        ctx.check(f"coder once, explore in, Explore out, got {listed}",
                  listed.count("coder") == 1 and "explore" in listed and "Explore" not in listed)


@test
def test_an_agent_session_restricted_to_planner(ctx: Ctx):
    with _home() as h:
        folder = h.repo / ".claude" / "agents"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "boss.md").write_text("---\nname: boss\ndescription: Runs the job.\ntools: Read, Agent(planner)\n---\n"
                                        "You run the job.\n", encoding="utf-8")
        (folder / "lead.md").write_text("---\nname: lead\ndescription: Leads.\ntools: [Read, \"Agent(planner)\", \"Agent(Judge)\"]\n---\n"
                                        "You lead.\n", encoding="utf-8")
        # an --agent session has no map: Auto's planner is not there, so nothing it may start is listed
        _every_name_starts(ctx, "--agent boss", h, agent="boss", want=[])
        _every_name_starts(ctx, "--agent lead", h, agent="lead", want=["Judge"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
