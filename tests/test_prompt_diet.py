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
CLOUD_HASH = "1048ade682d5aa7954e758f5b891a185e535c122633cf02b6caf4ff6923f6924"  # 3.6.0.10 M8: roles ON is the default
CLOUD_HASH_3601 = "1041e557d192ef0a140fdb5d77d98f3c1600a53e1c3fa3ca578b8d79c5440758"  # 3.6.0.1: Studio's paragraph names agents, workflows, the Map
ROLES_3601 = ("With custom roles OFF (the default) every sub-agent runs the session model unless the call passes "
              "`model:`; with roles ON the model table (`roles.*`) picks it (`role:`).")
ROLES_M8 = ("With custom roles ON (the default) the model table (`roles.*`) picks a sub-agent's model (`role:`); with "
            "roles OFF it runs the session model unless the call passes `model:`.")


def _every_builtin() -> list:
    from halo_harness.tools.mcp_tool import ListMcpResourcesTool, ReadMcpResourceTool
    from halo_harness.tools import orchestra_claims as O
    from halo_harness.tools.copilot_ask import CopilotAskTool  # 3.3.17.0: registered only once Copilot is set up
    from halo_harness.tools.builder_tool import BuilderTool  # 3.6.0.10 MW batch 4: a top session's, sent to a lean main
    from halo_harness.tools.registry import default_tools
    return default_tools(platform="win32") + [ListMcpResourcesTool(), ReadMcpResourceTool(), O.OrchestraClaimTool(),
                                              O.OrchestraClaimsTool(), O.OrchestraNoteTool(), O.OrchestraReleaseTool(),
                                              CopilotAskTool(), BuilderTool()]


_FOLDER: dict = {}


def _session(ref: str, window: int, **extra):
    """3.6.0.10 M1b: a NEW Auto session's state (crew/session_start.py: the control, the agents, depth 0), as the
    measure's stub has it, in a project folder of this module's own."""
    from halo_harness.crew.session_start import new_session_state
    from halo_harness.model import parse_model_ref
    if "proj" not in _FOLDER:
        _FOLDER["proj"] = tempfile.mkdtemp(prefix="pb_diet-proj-")
    stub = SimpleNamespace(model_ref=parse_model_ref(ref), model_profile=SimpleNamespace(context_tokens=window),
                           _measure_window=window, **{"interactive": True, **extra})  # the terminal app's session
    return new_session_state(stub, cwd=_FOLDER["proj"], control="auto")


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


@test
def test_copilot_ask_sits_right_after_the_lineups_needs(ctx: Ctx):
    """3.3.17.0: copilot_ask (registered only once Copilot is set up) comes after the needs (Workflow when a
    square is needed) and before the other built-ins, so a lean budget keeps it before a TaskList."""
    from halo_harness.agent import prompt_diet as D
    from halo_harness.tools.copilot_ask import CopilotAskTool
    from halo_harness.tools.registry import ToolRegistry, default_tools
    defs = ToolRegistry(default_tools(platform="linux") + [CopilotAskTool()]).definitions()
    saved = D.workflow_needed
    try:
        D.workflow_needed = lambda s: True
        rank = D._bands(_session("ol:tiny:3b@lan", 12288), defs, "", None)
    finally:
        D.workflow_needed = saved
    by = {t["name"]: rank[id(t)] for t in defs}
    others = [r for n, r in by.items() if r[0] >= 2]
    ctx.check(f"Workflow < copilot_ask < every other built-in, got {by['Workflow']} {by['copilot_ask']}",
              by["Workflow"] < by["copilot_ask"] and all(by["copilot_ask"] < r for r in others))


# 3.6.0.10 MW batch 4 (the owner, 2026-11-21: "1 - yes"): a lean main is sent the Builder wherever the tool budget holds
BUILDER_AT = (("ol:tiny:3b@lan", 8192, False), ("ol:tiny:3b@lan", 16384, False), ("ol:room-model", 32768, True),
              ("ol:qwen3-coder:30b@lan", 49152, True))


@test
def test_a_lean_main_is_sent_the_builder_where_the_tool_budget_holds(ctx: Ctx):
    """A NEW top Auto session with the Builder registered (as headless.py registers it for a session someone answers):
    at 32,768 and 49,152 the Builder is sent, in its short words, inside the window's tool budget (4,500, unchanged);
    at 8,192 and 16,384 it cannot fit and the by-name line names it, as before."""
    from halo_harness.agent.prompt_diet import tools_budget
    from halo_harness.agent.prompt_measure import first_turn
    _session("ol:tiny:3b@lan", 16384)
    for platform in ("win32", "linux"):
        for ref, window, sent in BUILDER_AT:
            m = first_turn(ref, window=window, platform=platform, cwd=_FOLDER["proj"], control="auto", builder=True)
            names = [r["name"] for r in m["tools"] if r["offered"]]
            tools = sum(r["tokens"] for r in m["tools"] if r["offered"])
            label = f"{platform} {window:,}"
            ctx.check(f"{label}: the tool block {tools:,} stays inside its budget {tools_budget(window):,}",
                      tools <= tools_budget(window))
            if sent:
                row = next((r for r in m["tools"] if r["name"] == "Builder"), {})
                ctx.check(f"{label}: the Builder is sent, got {names}", "Builder" in names)
                ctx.check(f"{label}: in its short words ({row.get('tokens')} tokens, the long ones are 1,024)",
                          row.get("tokens") is not None and row["tokens"] < 1024)
            else:
                ctx.check(f"{label}: the Builder is not sent and the by-name line names it, got {m['left_out']}",
                          "Builder" not in names and "Builder" in m["left_out"])


@test
def test_the_builder_ranks_last_of_the_builtins_before_pack_and_mcp_tools(ctx: Ctx):
    """On a top session the Builder is ranked with the built-ins, as the last of them (before the tools of packs and MCP
    servers, which rank by the task's words), so the room it needs is not taken first."""
    from halo_harness.agent import prompt_diet as D
    from halo_harness.agent.prompt_lean import _builtin_names
    from halo_harness.tools.builder_tool import BuilderTool
    from halo_harness.tools.registry import ToolRegistry, default_tools
    mcp = {"name": "mcp__shop__orders", "description": "List orders.", "input_schema": {"type": "object", "properties": {}}}
    defs = [mcp] + ToolRegistry(default_tools(platform="linux") + [BuilderTool()]).definitions()
    saved = D.workflow_needed
    try:
        D.workflow_needed = lambda s: False
        rank = D._bands(_session("ol:qwen3-coder:30b@lan", 49152), defs, "", None)
    finally:
        D.workflow_needed = saved
    by = {t["name"]: rank[id(t)] for t in defs}
    builtins = [by[n] for n in _builtin_names() if n in by and n != "Workflow"]  # Workflow unneeded ranks last of all
    ctx.check(f"every built-in < the Builder < an MCP tool, got {by['Builder']} {by[mcp['name']]}",
              all(r < by["Builder"] for r in builtins) and by["Builder"] < by[mcp["name"]])


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
                 "memory directory", "Agent tool", "Your working directory is /work", "Never end a turn",
                 "- Helpers you can start now (`subagent_type`): planner (plan, outline);"):  # 3.6.0.10 M4: on Auto
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
    ctx.check("the assembled prompt's bytes are 3.6.0.10's (a hash pin; only M8's roles sentence differs from 3.6.0.1's)",
              hashlib.sha256(fixed.encode("utf-8")).hexdigest() == CLOUD_HASH)
    text, defs, (out_text, _m, out_tools) = _cloud_and_lean("ant:claude-opus-5-5", 200000)
    ctx.check("the wire copy is the logged text, byte for byte, and every tool as it was",
              out_text == text and out_tools == defs)


@test
def test_m8_the_cloud_text_says_roles_are_on_by_default(ctx: Ctx):
    """3.6.0.10 MW rule M8: custom roles are ON by default (roles.py), so the cloud text's "With custom roles OFF (the
    default)" was false. CLOUD_HASH is pinned again once, and that sentence is the ONLY difference: put the old one
    back and the bytes are 3.6.0.1's (CLOUD_HASH_3601)."""
    from halo_harness.agent.prompt import build_system_prompt
    from halo_harness.roles import roles_mode_enabled
    tools = [{"name": "Bash", "description": "Runs a command."}, {"name": "Read", "description": "Reads a file."},
             {"name": "Write", "description": "Writes a file."}]
    fixed = build_system_prompt(model_label="ant:claude-opus-5-5", cwd="/work", tool_definitions=tools, family="claude")
    ctx.check("roles are on by default (the scratch home sets none)", roles_mode_enabled() is True)
    ctx.check("the false sentence is gone", ROLES_3601 not in fixed)
    ctx.check("the true one is there, once", fixed.count(ROLES_M8) == 1)
    ctx.check("only that sentence differs from 3.6.0.1's bytes",
              hashlib.sha256(fixed.replace(ROLES_M8, ROLES_3601).encode("utf-8")).hexdigest() == CLOUD_HASH_3601)


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


# ---- 3.6.0.12 OS: a one-shot's first ask carries the tool block of the window it asks ------------------------------

ONE_SHOT_REF, ONE_SHOT_CAP = "ol:tiny:1b", 65536
SHORT = "Reply with exactly one word: ready"
LONG = SHORT + ". Context follows. " + "word " * 1400  # about 2,000 tokens more: past half of 8,192 with any block


def _first(one_shot: bool, platform: str = "linux", text: str = SHORT):
    """(session, full tools, system, messages, the tools sent): a new Auto session's first request at the cap."""
    from halo_harness.agent.prompt_measure import _first_request
    if "proj" not in _FOLDER:
        _FOLDER["proj"] = tempfile.mkdtemp(prefix="pb_diet-proj-")
    return _first_request(ONE_SHOT_REF, window=ONE_SHOT_CAP, platform=platform, cwd=_FOLDER["proj"], control="auto",
                          one_shot=one_shot, text=text)


@test
def test_a_one_shot_asked_at_16384_is_sent_the_tool_block_of_16384(ctx: Ctx):
    from halo_harness.agent.prompt_measure import one_shot_first_ask
    _first(True)
    for platform, text, want in (("win32", LONG, 16384), ("linux", LONG, 16384), ("linux", SHORT, 8192)):
        m = one_shot_first_ask(ONE_SHOT_REF, cap=ONE_SHOT_CAP, platform=platform, cwd=_FOLDER["proj"], text=text)
        print(f"  {platform}, {len(text):,} characters: asked {m['asked']:,}, prompt {m['prompt']:,}, "
              f"{len(m['tools'])} tools of {m['tool_tokens']:,} tokens")
        ctx.check(f"{platform}: the first ask is the first step that holds it, {want:,}, got {m['asked']:,} (prompt "
                  f"{m['prompt']:,})", m["asked"] == want and m["sent_window"] == want)
        ctx.check(f"{platform}: its tool block is at most 2,200 tokens, got {m['tool_tokens']:,} ({len(m['tools'])} "
                  f"tools)", m["tool_tokens"] <= 2200)
        ctx.check(f"{platform}: ToolSearch is sent, got {m['tools']}", "ToolSearch" in m["tools"])
        ctx.check(f"{platform}: the system text names what was left out (ToolSearch loads it)",
                  "Other tools you can call by name" in m["system"])


@test
def test_a_session_of_more_turns_is_sent_the_tool_block_it_was_sent_before(ctx: Ctx):
    """The same prompt: a session of more turns gets no reshaper, and its tools are byte-equal to the request shaped at
    the cap, the block every session was sent before 3.6.0.12 (the one-shot's too, before it is shaped again)."""
    import json
    from halo_harness.agent.prompt_wire import one_shot_shaper
    many = _first(False)
    once = _first(True)
    session, _full, system_text, messages, sent = many
    ctx.check("a session of more turns is never shaped again",
              one_shot_shaper(session, session.model_ref, (system_text, messages, sent),
                              raw=session._measure_raw) is None)
    ctx.check("its window is never a one-shot's", getattr(session, "_shape_window", None) is None)
    ctx.check(f"its tools are byte-equal to the request shaped at the cap ({len(sent)} and {len(once[4])} tools)",
              json.dumps(sent, sort_keys=True) == json.dumps(once[4], sort_keys=True))
    cloud = one_shot_shaper(SimpleNamespace(model_ref=None), None, ("", [], [{"name": "Read"}]), raw=("", [], []))
    ctx.check("a session with no local model is never shaped again", cloud is None)


@test
def test_a_one_shot_shaped_again_says_the_window_it_asks_once(ctx: Ctx):
    """agent/loop.py's sequence: shaped for the turn (the cap), then start_window, then the request shaped for the
    window asked: one "not offered" line, naming 16,384."""
    from halo_harness.agent import ollama_window_truth as T
    from halo_harness.agent.ollama_window import _state
    from halo_harness.agent.prompt_measure import MEASURE_HOST
    from halo_harness.agent.prompt_wire import one_shot_shaper, shape
    from halo_harness.agent.reply_room import PROVIDER_DEFAULT
    session, full, *_rest = _first(True, platform="win32", text=LONG)
    raw = session._measure_raw
    request = shape(session, *raw, purpose="turn")
    host = SimpleNamespace(name="gpu-box", url=MEASURE_HOST, max_ctx=ONE_SHOT_CAP)
    key = T._key(host.url, session.model_ref.model)
    with T._ASKED_LOCK:
        was = T._ASKED.get(key)
    try:
        reshape = one_shot_shaper(session, session.model_ref, request)
        asked = T.start_window(session, host=host, ref=session.model_ref,
                               decision=SimpleNamespace(profile={}, trained_context=None, fit_estimate=None),
                               cap=ONE_SHOT_CAP, cap_source="host max_ctx", request=request,
                               requested=PROVIDER_DEFAULT, reshape=reshape)[0]
        sent = reshape(None)
    finally:
        with T._ASKED_LOCK:
            if was is None:
                T._ASKED.pop(key, None)
            else:
                T._ASKED[key] = was
    lines = [m for m in _state(session).get("markers", []) if "not offered" in m]
    ctx.check(f"asked 16,384, got {asked:,}", asked == 16384)
    ctx.check(f"the request sent is shaped for it ({len(sent[2])} of {len(request[2])} tools)",
              len(sent[2]) < len(request[2]) and getattr(session, "_shape_window", None) == 16384)
    ctx.check(f"one line, naming 16,384, got {lines}", len(lines) == 1 and "(window 16,384)" in lines[0])
    from halo_harness.agent.prompt_diet import call_window
    from halo_harness.model import parse_model_ref
    ctx.check(f"the run's later calls are shaped for 16,384, got {call_window(session)}", call_window(session) == 16384)
    ref = session.model_ref
    session.model_ref = parse_model_ref("ol:other:7b")
    try:
        ctx.check("a switch of model starts over (the block is the model's)", call_window(session) == ONE_SHOT_CAP)
    finally:
        session.model_ref = ref
    ctx.check("the names left out are the request sent's (the by-name line reads them)",
              "ToolSearch" not in (session._diet_dropped or []) and len(session._diet_dropped) > len(request[2]) // 3)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
