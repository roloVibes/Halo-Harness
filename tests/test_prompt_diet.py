"""tests.test_prompt_diet -- Halo 3.3.16.1 "the local prompt diet" (agent/prompt_diet.py,
tools/lean_descriptions.py, agent/prompt_lean_system.py, agent/reply_room.py,
providers/ollama_wire_estimate.py). In-process, a fake home of its own; never a server or a model call:

1. every built-in tool has a lean description (a new tool without one fails here), lean keeps every
   parameter and every required name;
2. an alias once: Task and Agent are one tool -- the wire carries Agent, a call named Task still resolves
   (and every pair of identical definitions in the registry is in ALIASES);
3. one shell on a lean Windows session (`prompt.shell`), the other left out and named; none on Linux;
4. the order: the core tools first, Workflow only when a square covers what the model lacks;
5. the lean system text keeps the instructions (tool calls, CLAUDE.md, read before edit, plan mode,
   memory, delegation) and drops the per-tool list; a cloud model with a large window gets today's bytes
   (a hash pin over the assembled prompt);
6. the reply's room: a quarter of the window at most, the class floor at least, never raised, a profile or
   the user's own max_tokens keeps the request; a first call starts where Halo's prompt is half at most;
7. the estimate that picks the window equals the estimate of the body sent, on a first turn and on a turn
   with a tool result.
Run: python -m tests.test_prompt_diet
"""
from __future__ import annotations

import hashlib
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("BRIDGE_TEST_HOME", tempfile.mkdtemp(prefix="pb_diet-"))
os.environ.setdefault("BRIDGE_TEST_NO_BACKGROUND_NET", "1")

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
CLOUD_HASH = "2f98df99f9ccafa086317a6b9d82c569796e9ad9da9d7c3e88b048ee6ef4ed8b"


def _every_builtin() -> list:
    from halo_harness.tools.mcp_tool import ListMcpResourcesTool, ReadMcpResourceTool
    from halo_harness.tools import orchestra_claims as O
    from halo_harness.tools.registry import default_tools
    return default_tools(platform="win32") + [ListMcpResourcesTool(), ReadMcpResourceTool(), O.OrchestraClaimTool(),
                                              O.OrchestraClaimsTool(), O.OrchestraNoteTool(), O.OrchestraReleaseTool()]


def _session(ref: str, window: int, **extra):
    from halo_harness.model import parse_model_ref
    return SimpleNamespace(model_ref=parse_model_ref(ref), model_profile=SimpleNamespace(context_tokens=window),
                           _measure_window=window, **extra)


@test
def test_every_builtin_tool_has_a_lean_description(ctx: Ctx):
    from halo_harness.tools.lean_descriptions import has_lean, lean_definition
    missing = [t.name for t in _every_builtin() if not has_lean(t.name)]
    ctx.check(f"a lean description for every built-in tool (add one to tools/lean_descriptions.py), missing {missing}",
              not missing)
    for t in _every_builtin():
        full, lean = t.definition(), lean_definition(t.definition())
        same_params = set((lean["input_schema"].get("properties") or {})) == set((full["input_schema"].get("properties") or {}))
        same_req = lean["input_schema"].get("required") == full["input_schema"].get("required")
        ctx.check(f"{t.name}: every parameter and required name kept, shorter", same_params and same_req
                  and len(str(lean)) <= len(str(full)) + 40)


@test
def test_an_alias_goes_on_the_wire_once_and_still_resolves(ctx: Ctx):
    import json
    from halo_harness.agent.prompt_diet import ALIASES, aliases_once
    from halo_harness.agent.repair import repair_tool_use_block
    from halo_harness.tools.registry import ToolRegistry, default_tools
    reg = ToolRegistry(default_tools())
    defs = reg.definitions()
    names = [d["name"] for d in aliases_once(defs)]
    ctx.check(f"Agent once, Task not on the wire, got {[n for n in names if n in ('Agent', 'Task')]}",
              "Agent" in names and "Task" not in names)
    out = repair_tool_use_block({"type": "tool_use", "id": "t1", "name": "Task",
                                 "input": {"description": "look", "prompt": "find it"}}, reg)
    ctx.check(f"a call named Task still resolves to the Task tool, got {out.ok} {out.block.get('name')}",
              out.ok and out.block.get("name") == "Task" and reg.get("Task") is not None)
    same: dict = {}
    for d in defs:
        same.setdefault(json.dumps([d["description"], d["input_schema"]], sort_keys=True), []).append(d["name"])
    pairs = [sorted(v) for v in same.values() if len(v) > 1]
    ctx.check(f"every pair of identical tools is an alias in ALIASES, got {pairs}",
              all(any(ALIASES.get(n) in v for n in v) for v in pairs))


@test
def test_one_shell_on_a_lean_windows_session(ctx: Ctx):
    from halo_harness.agent.prompt_diet import by_name_line, diet
    from halo_harness.theme import set_config_value, unset_config_value
    from halo_harness.tools.registry import ToolRegistry, default_tools
    win = ToolRegistry(default_tools(platform="win32")).definitions()
    for setting, kept, left in (("bash", "Bash", "PowerShell"), ("powershell", "PowerShell", "Bash")):
        set_config_value("prompt.shell", setting)
        try:
            out, dropped = diet(_session("ol:qwen3-coder:30b@lan", 49152), win, platform="win32")
        finally:
            unset_config_value("prompt.shell")
        names = [t["name"] for t in out]
        ctx.check(f"prompt.shell {setting}: {kept} offered, {left} left out, got {[n for n in names if n in (kept, left)]}",
                  kept in names and left not in names and left in dropped)
        ctx.check("the one line names it and ToolSearch", left in by_name_line(dropped) and "ToolSearch" in by_name_line(dropped))
    linux = ToolRegistry(default_tools(platform="linux")).names()
    ctx.check("Linux has no PowerShell tool at all", "PowerShell" not in linux and "Bash" in linux)


@test
def test_the_order_core_first_and_workflow_only_when_needed(ctx: Ctx):
    from halo_harness.agent import prompt_diet as D
    from halo_harness.providers.ollama_fit import CORE_TOOL_NAMES
    from halo_harness.tools.registry import ToolRegistry, default_tools
    defs = ToolRegistry(default_tools(platform="linux")).definitions()
    saved = D.workflow_needed
    try:
        D.workflow_needed = lambda s: False
        out, _ = D.diet(_session("ol:tiny:3b@lan", 12288), defs, platform="linux")
        names = {t["name"] for t in out}
        ctx.check(f"a 12k window: the core tools, no Workflow, got {sorted(names)}",
                  set(CORE_TOOL_NAMES) <= names and "Workflow" not in names)
        D.workflow_needed = lambda s: True
        out, _ = D.diet(_session("ol:tiny:3b@lan", 12288), defs, platform="linux")
        ctx.check("a square covers what the model lacks: Workflow right after the core",
                  "Workflow" in {t["name"] for t in out})
    finally:
        D.workflow_needed = saved
    ctx.check("the budgets: 2,200 to 16,384, 4,500 under 65,536, none above",
              (D.tools_budget(12288), D.tools_budget(16384), D.tools_budget(49152), D.tools_budget(65536))
              == (2200, 2200, 4500, None))


def _cloud_and_lean(session_ref: str, window: int):
    from halo_harness.agent.prompt import build_system_prompt
    from halo_harness.agent.prompt_wire import shape
    from halo_harness.tools.registry import ToolRegistry, default_tools
    defs = ToolRegistry(default_tools()).definitions()
    text = build_system_prompt(model_label=session_ref, cwd="/work", tool_definitions=defs, family="generic")
    msgs = [{"role": "user", "content": [{"type": "text", "text": "hi"}]}]
    return text, defs, shape(_session(session_ref, window), text, msgs, defs, purpose="measure")


@test
def test_the_lean_system_text_keeps_the_instructions(ctx: Ctx):
    from halo_harness.agent.prompt_composition import tokens_of
    text, _defs, (lean, _m, _t) = _cloud_and_lean("ol:qwen3-coder:30b@lan", 32768)
    for must in ("native tool calls", "CLAUDE.md", "Read a file before you edit it", "ExitPlanMode",
                 "memory directory", "Agent tool", "Your working directory is /work", "Never end a turn"):
        ctx.check(f"lean keeps {must!r}", must in lean)
    ctx.check("lean drops the per-tool list and the reference prose",
              "## Tools available in this session" not in lean and "Custom slash commands" not in lean)
    ctx.check(f"lean is a fraction of the full text: {tokens_of(lean)} of {tokens_of(text)}",
              tokens_of(lean) < 800 < 3000 < tokens_of(text))


@test
def test_a_cloud_model_with_a_large_window_gets_todays_bytes(ctx: Ctx):
    from halo_harness.agent.prompt import build_system_prompt
    tools = [{"name": "Bash", "description": "Runs a command."}, {"name": "Read", "description": "Reads a file."},
             {"name": "Write", "description": "Writes a file."}]
    fixed = build_system_prompt(model_label="ant:claude-opus-5-5", cwd="/work", tool_definitions=tools, family="claude")
    ctx.check("the assembled prompt's bytes are 3.3.16.0's (a hash pin)",
              hashlib.sha256(fixed.encode("utf-8")).hexdigest() == CLOUD_HASH)
    text, defs, (out_text, _m, out_tools) = _cloud_and_lean("ant:claude-opus-5-5", 200000)
    ctx.check("the wire copy is the logged text, byte for byte, and every tool as it was",
              out_text == text and out_tools == defs)


@test
def test_the_reply_room_follows_the_window(ctx: Ctx):
    from halo_harness.agent.reply_room import fitted, room
    got = {w: room(w, 16384)[0] for w in (8192, 16384, 32768, 49152, 65536, 131072)}
    ctx.check(f"a quarter of the window, the class floor at least, got {got}",
              got == {8192: 2048, 16384: 4096, 32768: 8192, 49152: 12288, 65536: 16384, 131072: 16384})
    ctx.check("never raised: a small request keeps its size", room(32768, 4096) == (4096, False))
    ctx.check("a steward profile's num_predict or the user's max_tokens keeps the request",
              room(32768, 16384, profile_num_predict=4096) == (16384, False)
              and room(32768, 16384, explicit=16384) == (16384, False))
    ctx.check("a first call starts in a window where Halo's prompt is half at most (8,192 -> 16,384)",
              fitted(8192, 6000, 16384, first=True)[:2] == (4096, 16384))
    ctx.check("a later call is raised only for prompt + room, and the room never raises it again",
              fitted(8192, 6000, 16384) == (2048, 8192, True) and fitted(32768, 30000, 16384)[0] <= 65536 - 30000)


@test
def test_the_estimate_that_picks_the_window_is_the_wire_bodys(ctx: Ctx):
    from halo_harness.providers.ollama import OllamaHost
    from halo_harness.providers.ollama_prompt import estimate_request_tokens
    from halo_harness.providers.ollama_request import build_ollama_request_body
    from halo_harness.providers.ollama_wire_estimate import wire_estimate
    from halo_harness.providers.profiles import ProviderProfile
    from halo_harness.tools.registry import ToolRegistry, default_tools
    tools = ToolRegistry(default_tools()).definitions()
    system = "You are a test agent.\n\nRules here."
    first = [{"role": "user", "content": [{"type": "text", "text": "snapshot"}, {"type": "text", "text": "hi"}]}]
    later = first + [{"role": "assistant", "content": [{"type": "text", "text": "reading"}, {
        "type": "tool_use", "id": "toolu_1", "name": "Read", "input": {"file_path": "/a.txt"}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "toolu_1", "content": "line 1\nline 2\n" * 40}]}]
    for label, msgs in (("a first turn", first), ("a turn with a tool result", later)):
        body = build_ollama_request_body(system_text=system, messages=msgs, tools=tools, route=SimpleNamespace(upstream_model="m"),
                                         profile=ProviderProfile(), host=OllamaHost("h", "http://h:11434"),
                                         requested_max_tokens=8192)
        sent = estimate_request_tokens(body["messages"], body.get("tools"), "", reply_tokens=body["options"]["num_predict"])
        chosen = wire_estimate(system, msgs, tools, reply_tokens=8192)
        ctx.check(f"{label}: the window's estimate {chosen} == the sent body's {sent}", chosen == sent)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
