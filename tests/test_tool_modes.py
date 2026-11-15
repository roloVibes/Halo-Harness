"""tests.test_tool_modes -- Halo 3.6.0.0 R16: which built-in tool needs a prompt in which permission mode.

1. The Workflow tool stands where the Agent tool does (permissions.py DELEGATE_TOOL_NAMES): never mode-gated, in every
   mode and every entry point (print mode, an interactive session -- the TUI and Studio's Prompt panel --, a
   sub-agent's engine, headless). Before R16 it fell to the mode table's `other` row: ask, and in `-p` a denial no
   one could answer ("mode 'default' would ask for this Workflow call (other)").
2. A real `halo -p` in the default mode, over the repo's fake provider (tests/helpers/mock_openai.py, loopback),
   whose model calls Workflow: the tool runs (its own answer reaches the model's next request), no permission denial.
3. The table of every built-in tool by mode is pinned here (TABLE): a new tool fails this test until its row is
   written, so no tool is left to the `other` row by accident. Tools that only read, plan or delegate are allowed in
   `-p`; what asks does so by design (it writes, runs a program, reaches the network, captures the screen).

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
}
_LETTER = {"allow": "a", "ask": "?", "deny": "d"}


def _every_builtin_tool() -> list:
    """Every tool Halo can offer a session, whatever the platform or setup: default_tools for Windows (PowerShell
    included), the ones only some sessions get (Builder, SendUserMessage, copilot_ask, WebSearch, the Orchestra's)."""
    from halo_harness.tools.builder_tool import BuilderTool
    from halo_harness.tools.copilot_ask import CopilotAskTool
    from halo_harness.tools.orchestra_claims import (OrchestraClaimTool, OrchestraClaimsTool, OrchestraNoteTool,
                                                    OrchestraReleaseTool)
    from halo_harness.tools.registry import default_tools
    from halo_harness.tools.send_user_message import SendUserMessageTool
    from halo_harness.tools.websearch import WebSearchTool
    tools = {t.name: t for t in default_tools("win32")}
    for t in (BuilderTool(), SendUserMessageTool(), CopilotAskTool(),
              WebSearchTool(base_url="http://127.0.0.1:9", api_key="unused", model="unused"),
              OrchestraClaimTool(), OrchestraReleaseTool(), OrchestraClaimsTool(), OrchestraNoteTool()):
        tools.setdefault(t.name, t)
    return [tools[n] for n in sorted(tools)]


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
