"""tests.test_tools_capabilities -- Halo 3.1.8.0 R5: `tools.capabilities` (isolation/capabilities.py): the one
table, which list wins (card, tier, bio, lineup), the narrowed registry of a lineup member and of the top
session (headless.build_session), an Orchestra worker's list from its run, the Agent tool's description,
`/tools`, and that allow/deny still apply inside the list. No model is called.

Run: python -m tests.test_tools_capabilities
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.isolation_rig import IsoEnv
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

ensure_default_provider_credentials()
test, TESTS = new_registry()


def _crew(e):
    e.lineup("crew", {"agents": [{"agent": "boss", "role": "main"},
                                 {"agent": "coder", "role": "coder", "tools": {"capabilities": ["read", "edit"]}},
                                 {"agent": "reviewer", "role": "reviewer"}, {"agent": "scout", "role": "researcher"},
                                 {"agent": "plain", "role": "tester"}],
                      "tiers": [{"name": "lead", "members": ["main"]},
                                {"name": "makers", "members": ["coder", "researcher"], "tools": {"capabilities": ["read", "web"]}},
                                {"name": "checkers", "members": ["reviewer", "tester"]}],
                      "tools": {"capabilities": ["read", "bash"]}})
    e.bio("boss", {"tools": {"capabilities": ["read", "agent"]}})
    e.bio("coder", {"tools": {"capabilities": ["bash"]}})
    e.bio("reviewer", {"tools": {"capabilities": ["read"]}})
    e.bio("scout", {})
    e.bio("plain", {})


@test
def test_the_one_table(ctx: Ctx):
    from halo_harness.isolation.capabilities import TABLE, capability_of
    from halo_harness.tools.registry import known_tool_names
    want = {"Read": "read", "Glob": "read", "Grep": "read", "Edit": "edit", "Write": "edit", "NotebookEdit": "edit",
            "Bash": "bash", "BashOutput": "bash", "WebFetch": "web", "WebSearch": "web", "Agent": "agent",
            "Task": "agent", "Media": "media", "ToolSearch": "mcp", "Skill": "recall", "TodoWrite": "recall",
            "OrchestraClaim": "edit", "OrchestraRelease": "edit"}
    ctx.check("each tool's capability", all(capability_of(n) == c for n, c in want.items()))
    ctx.check("an MCP tool is its server", capability_of("mcp__github__create_issue") == "mcp:github")
    ctx.check("a connector is its slug", capability_of("connector__claude_docs") == "mcp:claude_docs")
    ctx.check("a name outside the table is other", capability_of("AskUserQuestion") == "other" and capability_of("Zap") == "other")
    unmapped = sorted(n for n in known_tool_names() if capability_of(n) == "other")
    ctx.check(f"only the session's own bookkeeping tools are other, got {unmapped}",
              set(unmapped) <= {"AskUserQuestion", "EnterPlanMode", "ExitPlanMode", "SendUserMessage"})
    ctx.check("one capability per tool", len({t for ts in TABLE.values() for t in ts}) == sum(len(ts) for ts in TABLE.values()))


@test
def test_which_list_wins_card_tier_bio_lineup(ctx: Ctx):
    with IsoEnv() as e:
        _crew(e)
        from halo_harness.teams_runtime import load_team_control
        tc = load_team_control("crew")
        from halo_harness.isolation.capabilities import narrow_member
        from halo_harness.tools.registry import ToolRegistry
        got = {}
        for alias in ("coder", "researcher", "reviewer", "tester"):
            reg, lines = narrow_member(ToolRegistry(), tc, alias)
            got[alias] = (reg.names(), lines)
        ctx.check(f"the card wins, got {got['coder']}", got["coder"][1] == ["tools: read, edit (by lineup crew)"]
                  and set(got["coder"][0]) == {"Edit", "Glob", "Grep", "NotebookEdit", "Read", "Write"})
        ctx.check(f"then the tier, got {got['researcher'][1]}", got["researcher"][1] == ["tools: read, web (by lineup crew)"]
                  and "WebFetch" in got["researcher"][0] and "Bash" not in got["researcher"][0])
        ctx.check(f"then the bio, got {got['reviewer'][1]}", got["reviewer"][1] == ["tools: read (by bio reviewer)"]
                  and set(got["reviewer"][0]) == {"Glob", "Grep", "Read"})
        ctx.check(f"then the lineup's own, got {got['tester'][1]}", got["tester"][1] == ["tools: read, bash (by lineup crew)"]
                  and "Bash" in got["tester"][0] and "Edit" not in got["tester"][0])
        reg, lines = narrow_member(ToolRegistry(), None, "coder")
        ctx.check("no lineup: every tool, no line", lines is None and "Bash" in reg.names() and "Agent" in reg.names())


@test
def test_allow_and_deny_still_apply_inside_the_list(ctx: Ctx):
    from halo_harness.config.agents_md import AgentSpec
    from halo_harness.isolation.capabilities import narrow
    from halo_harness.tools.registry import ToolRegistry
    full = ToolRegistry()
    spec = AgentSpec(name="x", description="x", tools=["Read", "Edit", "Bash"], disallowed_tools=["Edit"])
    reg = full.filtered(spec.resolved_tools(full.names()))
    narrow(reg, ["read", "edit"])
    ctx.check(f"the file's deny keeps Edit out, the list keeps Bash out, got {reg.names()}", reg.names() == ["Read"])
    reg = full.without(["Grep"])
    narrow(reg, ["read"])
    ctx.check("a tool a deny rule removed never comes back", "Grep" not in reg.names() and "Read" in reg.names())


@test
def test_the_top_session_is_built_with_the_lineup_mains_list(ctx: Ctx):
    with IsoEnv() as e:
        _crew(e)
        from halo_harness import headless
        build = headless.build_session(cwd=e.root, model_ref_raw="or:deepseek/deepseek-v4.1-flash", bare=False,
                                       print_mode=True, cli_flags={"team": "crew"})
        names = build.tool_registry.names()
        ctx.check(f"main sees read and agent only, got {names}",
                  {"Agent", "Read"} <= set(names) and not {"Bash", "Edit", "Write", "WebFetch"} & set(names))
        ctx.check("the session's catalog agrees", not {"Bash", "Edit"} & set(build.session.session_catalog.names))
        ctx.check(f"its agent row line, got {build.session.opt_ins}", build.session.opt_ins == ["tools: read, agent (by bio boss)"])
        plain = headless.build_session(cwd=e.root, model_ref_raw="or:deepseek/deepseek-v4.1-flash", bare=False,
                                       print_mode=True)
        ctx.check("no declaring lineup: everything as before", "Bash" in plain.tool_registry.names() and not plain.session.opt_ins)


@test
def test_an_orchestra_worker_takes_its_list_from_its_run(ctx: Ctx):
    with IsoEnv() as e:
        _crew(e)
        from halo_harness.isolation.capabilities import session_caps
        env = {"HALO_ORCHESTRA_LANE": "2", "HALO_TOOLS_CAPS": "read,edit", "HALO_TOOLS_CAPS_BY": "bio coder"}
        ctx.check("the run's list", session_caps(team="crew", agent=None, env=env) == (["read", "edit"], "bio coder"))
        ctx.check("a worker the run did not narrow is not narrowed by the lineup's main",
                  session_caps(team="crew", agent=None, env={"HALO_ORCHESTRA_LANE": "2"}) == (None, ""))
        ctx.check("outside a run the main's list", session_caps(team="crew", agent=None, env={})[0] == ["read", "agent"])
        ctx.check("an --agent bio's own list", session_caps(team=None, agent="reviewer", env={}) == (["read"], "bio reviewer"))
        from tests.helpers.isolation_rig import Recorder, run_with_lane
        from halo_harness.orchestra.adapters import spawn_worker
        _repo, run_dir, lane = run_with_lane(lineup="crew", bio="reviewer")
        rec = Recorder()
        spawn_worker(None, run_dir=run_dir, runner=rec)(lane)
        env = rec.calls[0]["env"]
        ctx.check(f"the spawn hands the worker its list, got {env.get('HALO_TOOLS_CAPS')!r}",
                  env.get("HALO_TOOLS_CAPS") == "read" and env.get("HALO_TOOLS_CAPS_BY") == "bio reviewer")
        ctx.check("and the line it shows", env.get("HALO_OPT_INS") == "tools: read (by bio reviewer)")


@test
def test_the_agent_tool_says_what_the_members_may_use(ctx: Ctx):
    with IsoEnv() as e:
        _crew(e)
        from halo_harness.tools.agent import AgentTool
        tool = AgentTool()
        before = tool.description
        tool.lineup = "crew"
        text = tool.description
        ctx.check("one sentence naming each member's list", "Under lineup crew each member sees only the tools of its "
                  "capabilities: coder: read, edit; reviewer: read; researcher: read, web; tester: read, bash." in text)
        ctx.check("no lineup: the description as before", "Under lineup" not in before)


@test
def test_slash_tools_lists_them_by_capability(ctx: Ctx):
    from halo_harness.isolation.tools_view import tools_text
    text = tools_text(["Read", "Bash", "mcp__gh__issue", "Grep"], ["isolation: container (x)", "tools: read, bash (by lineup crew)"])
    ctx.check(f"a line per capability, got {text!r}", "  read           Grep, Read" in text and "  bash           Bash" in text
              and "  mcp:gh         mcp__gh__issue" in text)
    ctx.check("what narrowed it, then the other lines", "Narrowed to tools: read, bash (by lineup crew)" in text
              and text.endswith("isolation: container (x)"))
    ctx.check("nothing narrowed: says so", "Nothing narrows the list" in tools_text(["Read"]))
    from halo_harness.commands.builtins import _BUILTIN_SPECS
    ctx.check("/tools is a built-in", "tools" in _BUILTIN_SPECS)


@test
def test_a_bad_capability_is_one_line(ctx: Ctx):
    from halo_harness.isolation.capabilities import problems
    ctx.check("known names and mcp:<server> pass", not problems(["read", "mcp:github", "other"], "tools.capabilities"))
    ctx.check("an unknown name is one line", problems(["read", "net"], "tools.capabilities")
              == ['"tools.capabilities" \'net\' is not one of read, edit, bash, web, agent, mcp, media, recall, other or mcp:<server>'])
    with IsoEnv() as e:
        e.bio("coder", {})
        from halo_harness.teams_yaml import validate_team_template
        bad = validate_team_template({"agents": [{"agent": "coder", "role": "main", "tools": {"capabilities": ["nope"]}}],
                                      "tiers": [{"name": "t", "members": ["main"], "tools": {"capabilities": "read"}}]})
        ctx.check(f"a card's and a tier's list are checked, got {bad}",
                  any("agents[0].tools.capabilities" in p for p in bad) and any("tiers[0].tools.capabilities" in p for p in bad))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
