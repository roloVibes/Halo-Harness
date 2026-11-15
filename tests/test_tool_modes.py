"""tests.test_tool_modes -- Halo 3.6.0.0 R16: which built-in tool needs a prompt in which permission mode.

1. The Workflow tool stands where the Agent tool does (permissions.py DELEGATE_TOOL_NAMES): never mode-gated, in every
   mode and every entry point (print mode, an interactive session -- the TUI and Studio's Prompt panel --, a
   sub-agent's engine, headless). Before R16 it fell to the mode table's `other` row: ask, and in `-p` a denial no
   one could answer ("mode 'default' would ask for this Workflow call (other)").
2. A real `halo -p` in the default mode, over the repo's fake provider (tests/helpers/mock_openai.py, loopback),
   whose model calls Workflow: the tool runs (its own answer reaches the model's next request), no permission denial.
3. The table of every built-in tool by mode is pinned here (TABLE): every `Tool` class anywhere in halo_harness and
   every name a real session build registers must have a row, so a new tool fails this test until its row is
   written and no tool is left to the `other` row by accident. Tools that only read, plan or delegate are allowed in
   `-p`; what asks does so by design (it writes, runs a program, reaches the network, captures the screen).
4. A rule written for Agent holds Workflow back too (it spawns sub-agents): a deny or ask for `Agent`, `Task` or
   `Agent(<type>)` decides a Workflow call the same way, a bare `Agent` deny or `--disallowedTools Agent` takes
   Workflow out of the tool list, and an agent that may not delegate (`disallowed_tools: [Agent, Task]`) gets no
   Workflow either.
5. Plan mode: a Workflow call whose square runs on the Orchestra is refused in one line, before anything is written or
   started.

No real model, no real home, no LAN address. Run: python -m tests.test_tool_modes
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.fake_home import build_fake_home  # noqa: E402
from tests.helpers.mock_openai import MockUpstream, SCENARIOS, ScriptedTurns  # noqa: E402
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
from tests.helpers.session_rig import recorded, text_step, tool_step  # noqa: E402

ensure_default_provider_credentials()
test, TESTS = new_registry()

MODES = ("default", "acceptEdits", "plan", "auto", "dontAsk", "bypassPermissions")
# One letter per mode above, for an interactive session (the TUI, Studio's Prompt panel, headless): a = allow,
# ? = ask, d = deny. In print mode (`-p`) an ask is a denial (no one to answer) -- EnterPlanMode excepted (it only
# narrows). EnterPlanMode / ExitPlanMode are run by the loop itself (agent/loop.py: only a deny RULE gates them), the
# engine's row below is what decide() would say. Inputs: a path inside the project, a Bash/PowerShell command that
# writes (a read-only one is allowed in every mode).
TABLE = {
    "Agent":            "aaaaaa",  # delegates
    "Task":             "aaaaaa",  # delegates (Agent's other name)
    "Workflow":         "aaaaaa",  # delegates (R16: was ??dada, the `other` row)
    "AskUserQuestion":  "aaaada",  # asks the person; dontAsk asks nothing
    "Bash":             "??dada",  # runs a program
    "PowerShell":       "??dada",  # runs a program
    "BashOutput":       "aaaaaa",  # reads
    "Builder":          "aadada",  # asks on its own card before it writes
    "Edit":             "?adada",  # writes
    "Write":            "?adada",  # writes
    "NotebookEdit":     "?adada",  # writes
    "EnterPlanMode":    "??dada",  # the loop's own (only narrows; allowed in -p)
    "ExitPlanMode":     "??dada",  # the loop's own (a plan-review round trip)
    "Glob":             "aaaaaa",  # reads
    "Grep":             "aaaaaa",  # reads
    "Read":             "aaaaaa",  # reads
    "Media":            "??dada",  # runs ffmpeg, writes frames
    "Screenshot":       "??dada",  # captures this machine's screen
    "Skill":            "aaaaaa",  # reads a skill
    "SendUserMessage":  "aaaaaa",  # speaks to the person (R16: was ??dada)
    "TaskCreate":       "aaaaaa",  # plans: the session's task board (R16: was ??dada)
    "TaskUpdate":       "aaaaaa",  # plans: the session's task board (R16: was ??dada)
    "TaskList":         "aaaaaa",  # reads the board
    "TaskStop":         "??dada",  # stops a running process
    "TodoWrite":        "aaaaaa",  # plans
    "ToolSearch":       "aaaaaa",  # reads the catalog
    "WebFetch":         "??aada",  # the network
    "WebSearch":        "??aada",  # the network
    "copilot_ask":      "??dada",  # the network, Copilot Credits
    "knowledge_add":    "aadaaa",  # notes (plan mode writes nothing)
    "knowledge_search": "aaaaaa",  # reads
    "OrchestraClaim":   "aadaaa",  # the run's own claims log
    "OrchestraRelease": "aadaaa",
    "OrchestraClaims":  "aadaaa",
    "OrchestraNote":    "aadaaa",
    "ListMcpResourcesTool": "aaaaaa",  # reads (registered beside MCP servers, headless.py)
    "ReadMcpResourceTool":  "aaaaaa",  # reads
    "PreflightProbe":   "??dada",  # `halo preflight`'s canary, only in its own probe session
}
# Tool classes whose name is made per instance: one per MCP server tool / connector, decided by the mcp rules and the
# server's readOnlyHint (permissions.py `read_tool`), never by a fixed row.
PER_INSTANCE = {"McpTool", "ConnectorTool"}
_LETTER = {"allow": "a", "ask": "?", "deny": "d"}


def _tool_classes() -> list:
    """Every `Tool` subclass in halo_harness: each module whose source defines a class on a *Tool base is imported,
    then the subclass tree is walked, so a tool registered anywhere (not only in default_tools) is found."""
    import importlib
    import re
    from halo_harness.tools.base import Tool
    pkg = REPO / "halo_harness"
    for f in sorted(pkg.rglob("*.py")):
        if "node_modules" in f.parts or not re.search(r"^class \w+\([\w.]*Tool\):", f.read_text(encoding="utf-8"),
                                                       re.MULTILINE):
            continue
        mod = ".".join(f.relative_to(REPO).with_suffix("").parts)
        importlib.import_module(mod[:-len(".__init__")] if mod.endswith(".__init__") else mod)
    out, todo = [], list(Tool.__subclasses__())
    while todo:
        cls = todo.pop()
        out.append(cls)
        todo += cls.__subclasses__()
    return out


def _instance(cls):
    try:
        return cls()
    except TypeError:  # a constructor that needs its endpoint (WebSearch): the name and flags are class-level
        return object.__new__(cls)


def _every_builtin_tool() -> list:
    tools = {}
    for cls in _tool_classes():
        if cls.__name__ in PER_INSTANCE or cls.__module__.startswith("tests."):
            continue
        t = _instance(cls)
        tools.setdefault(str(getattr(t, "name", "") or cls.__name__), t)
    return [tools[n] for n in sorted(tools)]


def _session_tool_names() -> set:
    """The names a real `-p` session build registers (headless.build_session, `--brief` on), in a scratch home."""
    from tests.helpers import catalog_facts_seed as S
    from halo_harness import headless
    with S.home("tool-modes-") as (root, state):
        S.seed(state)
        repo = root / "repo"
        repo.mkdir()
        built = headless.build_session(cwd=repo, model_ref_raw="or:v/eyes", print_mode=True, cli_flags={"brief": True})
        return set(built.session.tool_registry.names())


def _input(name: str, cwd: Path) -> dict:
    return {"Read": {"file_path": str(cwd / "a.txt")}, "Edit": {"file_path": str(cwd / "a.txt")},
            "Write": {"file_path": str(cwd / "a.txt")}, "NotebookEdit": {"notebook_path": str(cwd / "a.ipynb")},
            "Bash": {"command": "make build"}, "PowerShell": {"command": "New-Item x"}}.get(name, {})


def _row(engine_for, tool, cwd: Path) -> str:
    return "".join(_LETTER[engine_for(m).decide(tool.name, _input(tool.name, cwd), tool).action] for m in MODES)


@test
def test_every_builtin_tool_has_its_pinned_row(ctx: Ctx):
    from halo_harness.permissions import PermissionEngine
    from halo_harness.tools.registry import known_tool_names
    cwd = Path(tempfile.mkdtemp(prefix="halo-tool-modes-"))
    tools = _every_builtin_tool()
    names = {t.name for t in tools}
    ctx.check(f"every name the harness knows is in the table, missing {sorted(set(known_tool_names()) - set(TABLE))}",
              set(known_tool_names()) <= set(TABLE))
    built = _session_tool_names()
    ctx.check(f"every tool a real session build registers has a row, missing {sorted(built - set(TABLE))}",
              "SendUserMessage" in built and built <= set(TABLE))
    ctx.check(f"the table names exactly the built-in tools: unpinned {sorted(names - set(TABLE))}, "
              f"gone {sorted(set(TABLE) - names)}", names == set(TABLE))
    got = {t.name: _row(lambda m: PermissionEngine(mode=m, cwd=cwd), t, cwd) for t in tools}
    wrong = {n: (got[n], TABLE.get(n)) for n in sorted(got) if got[n] != TABLE.get(n)}
    ctx.check(f"each tool's row, interactive (got, pinned): {wrong}", not wrong)
    for t in tools:
        want = TABLE.get(t.name, "")
        want_p = "aaaaaa" if t.name == "EnterPlanMode" else want.replace("?", "d")
        got_p = _row(lambda m: PermissionEngine(mode=m, cwd=cwd, print_mode=True), t, cwd)
        ctx.check(f"{t.name} in -p: {want_p}, got {got_p}", got_p == want_p)


@test
def test_workflow_stands_where_agent_does_in_every_entry_point(ctx: Ctx):
    from halo_harness.permissions import DELEGATE_TOOL_NAMES, PermissionEngine
    from halo_harness.tools.registry import default_tools
    cwd = Path(tempfile.mkdtemp(prefix="halo-tool-modes-"))
    tools = {t.name: t for t in default_tools()}
    ctx.check(f"Workflow is a delegate tool beside Agent and Task, got {sorted(DELEGATE_TOOL_NAMES)}",
              DELEGATE_TOOL_NAMES == {"Agent", "Task", "Workflow"})
    wf_input = {"task": "review the change", "name": "review-loop"}
    agent_input = {"description": "review", "prompt": "review the change", "subagent_type": "general-purpose"}
    for mode in MODES:
        for label, kw in (("-p", {"print_mode": True}), ("interactive", {}),
                          ("a sub-agent", {"parent": PermissionEngine(mode=mode, cwd=cwd)})):
            engine = PermissionEngine(mode=mode, cwd=cwd, **kw)
            wf = engine.decide("Workflow", dict(wf_input), tools["Workflow"])
            ag = engine.decide("Agent", dict(agent_input), tools["Agent"])
            ctx.check(f"{mode} / {label}: Workflow {wf.action} like Agent {ag.action}",
                      wf.action == ag.action == "allow" and wf.permission_denial is None)
    from halo_harness.permissions import parse_rule
    engine = PermissionEngine(mode="bypassPermissions", cwd=cwd, deny_rules=[parse_rule("Workflow", action="deny")])
    ctx.check("an explicit deny rule still governs Workflow",
              engine.decide("Workflow", dict(wf_input), tools["Workflow"]).action == "deny")


@test
def test_a_rule_for_agent_holds_workflow_back(ctx: Ctx):
    from halo_harness.permissions import PermissionEngine, freeze_tool_registry, parse_rule
    from halo_harness.tools.registry import ToolRegistry, default_tools
    cwd = Path(tempfile.mkdtemp(prefix="halo-tool-modes-"))
    tools = {t.name: t for t in default_tools()}
    wf_input = {"task": "review the change"}
    for raw in ("Agent", "Task", "Agent(general-purpose)"):
        deny, ask = [parse_rule(raw, action="deny")], [parse_rule(raw, action="ask")]
        for mode in MODES:
            for pm in (False, True):
                got = PermissionEngine(mode=mode, cwd=cwd, print_mode=pm, deny_rules=deny).decide(
                    "Workflow", dict(wf_input), tools["Workflow"])
                ctx.check(f"deny {raw} / {mode} / {'-p' if pm else 'interactive'}: Workflow denied naming the rule, got "
                          f"{got.action} {got.reason!r}", got.action == "deny" and raw in got.reason)
                got = PermissionEngine(mode=mode, cwd=cwd, print_mode=pm, ask_rules=ask).decide(
                    "Workflow", dict(wf_input), tools["Workflow"])
                want = ("allow" if mode == "bypassPermissions" else
                        "deny" if (pm or mode == "dontAsk") else "ask")
                ctx.check(f"ask {raw} / {mode} / {'-p' if pm else 'interactive'}: Workflow {want}, got {got.action}",
                          got.action == want)
        sub = PermissionEngine(mode="default", cwd=cwd, deny_rules=deny, parent=PermissionEngine(mode="default", cwd=cwd))
        ctx.check(f"deny {raw}: a sub-agent's Workflow call is denied too",
                  sub.decide("Workflow", dict(wf_input), tools["Workflow"]).action == "deny")
    other = PermissionEngine(mode="default", cwd=cwd, print_mode=True, deny_rules=[parse_rule("Bash", action="deny")])
    ctx.check("a rule for another tool leaves Workflow alone",
              other.decide("Workflow", dict(wf_input), tools["Workflow"]).action == "allow")
    for kw in ({"deny_rules": [parse_rule("Agent", action="deny")]}, {"disallowed_tools": ["Agent"]},
               {"disallowed_tools": ["Task"]}):
        names = freeze_tool_registry(ToolRegistry(default_tools()), **kw).names()
        ctx.check(f"{kw}: Agent, Task and Workflow leave the tool list, got {[n for n in ('Agent', 'Task', 'Workflow') if n in names]}",
                  not {"Agent", "Task", "Workflow"} & set(names) and "Read" in names)
    names = freeze_tool_registry(ToolRegistry(default_tools()), disallowed_tools=["Workflow"]).names()
    ctx.check("a Workflow deny leaves Agent", "Agent" in names and "Workflow" not in names)
    from halo_harness.config.agents_md import _builtin_specs
    from halo_harness.review.agents import FIXER_NAME, review_specs
    catalog = [t.name for t in default_tools()]
    for spec in [s for s in _builtin_specs().values() if s.disallowed_tools] + [review_specs([])[FIXER_NAME]]:
        got = spec.resolved_tools(catalog)
        ctx.check(f"{spec.name} may not delegate, so no Workflow either, got {sorted(set(got) & {'Agent', 'Task', 'Workflow'})}",
                  not {"Agent", "Task", "Workflow"} & set(got) and "Read" in got)


@test
def test_plan_mode_refuses_an_orchestra_square(ctx: Ctx):
    from tests.helpers.packs_home import PacksHome
    from tests.helpers.workflow_fakes import FakeRuntime, run_tool
    from halo_harness.permissions import PermissionEngine
    with PacksHome() as h:
        from halo_harness.theme import set_config_value  # the squares a session offers are config now (R5d)
        set_config_value("workflows.enabled", ["media", "code"])
        ran: list = []
        for mode in ("plan", "default"):
            rt = FakeRuntime(h.repo)
            rt.parent.permission_engine = PermissionEngine(mode=mode, cwd=h.repo)
            before = sorted(str(p) for p in h.repo.rglob("*"))

            def runner(run_dir):
                ran.append(mode)
                (Path(run_dir) / "report.json").write_text(json.dumps({"status": "finished", "cost_usd": 0.5,
                                                                        "finished": True}), encoding="utf-8")
            got = run_tool(rt, {"task": "fix the failing test", "name": "code"}, run_orchestra=runner, takes=["text"])
            if mode == "plan":
                ctx.check(f"plan: one line naming plan mode, an error, got {got.content!r}",
                          got.is_error and "plan mode" in got.content and "ExitPlanMode" in got.content
                          and "\n" not in got.content)
                ctx.check(f"plan: nothing started, got {ran}", ran == [])
                ctx.check("plan: nothing written in the repo", sorted(str(p) for p in h.repo.rglob("*")) == before)
                ctx.check(f"plan: no receipt, node or cost, got {rt.parent.log.nodes} {rt.parent.log.usage}",
                          not rt.parent.log.nodes and not rt.parent.log.usage
                          and not [r for _k, aid, r in rt.frames if aid.startswith("sq-")])
            else:
                ctx.check(f"default: the square runs, got {got.content.splitlines()[:1]} {ran}",
                          ran == ["default"] and not got.is_error)


@test
def test_print_mode_default_runs_a_workflow_call(ctx: Ctx):
    from tests.test_h9b_findings import _hermetic_child_env
    fh = build_fake_home()
    mock = MockUpstream().start()
    seen: list = []
    try:
        SCENARIOS["r16-workflow"] = ScriptedTurns([
            tool_step(("Workflow", {"task": "review the change in basket.py", "name": "review-loop"}, "call_wf")),
            recorded(text_step("the workflow answered"), seen)])
        env = _hermetic_child_env()
        env.update({"BRIDGE_TEST_HOME": str(fh["home"]), "BRIDGE_OPENROUTER_BASE_URL": mock.base_url,
                    "OPENROUTER_API_KEY": "test-key", "PYTHONPATH": str(REPO), "BRIDGE_TEST_NO_BACKGROUND_NET": "1",
                    "OLLAMA_HOST": "http://127.0.0.1:9", "HALO_NO_UPDATER": "1"})
        args = [sys.executable, "-m", "halo_harness", "-p", "run my review workflow", "--model", "or:mock/r16-workflow",
                "--cwd", str(fh["proj"]), "--output-format", "json", "--permission-mode", "default"]  # the fake home says auto
        r = subprocess.run(args, env=env, cwd=str(REPO), capture_output=True, encoding="utf-8", errors="replace",
                           timeout=120)
        obj = json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else {}
        ctx.check(f"exit 0, got {r.returncode} {r.stderr[-600:]!r}", r.returncode == 0)
        ctx.check(f"no permission denial, got {obj.get('permission_denials')!r}", not obj.get("permission_denials"))
        ctx.check(f"the turn ends on the model's answer, got {obj.get('result')!r}", obj.get("result") == "the workflow answered")
        tool_msgs = [m for m in (seen[-1].get("messages") if seen else []) if m.get("role") == "tool"]
        said = str(tool_msgs[-1].get("content")) if tool_msgs else ""
        ctx.check(f"the Workflow tool ran and its own answer reached the model, got {said[:300]!r}",
                  "review-loop" in said and "Permission denied" not in said and "no interactive prompt" not in said)
    finally:
        mock.stop()
        SCENARIOS.pop("r16-workflow", None)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
