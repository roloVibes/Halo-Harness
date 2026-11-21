"""tests.test_prompt_budget_pins -- Halo 3.3.16.1 "the local prompt diet": a budget that cannot be crossed
silently. The first turn Halo would send (agent/prompt_measure.first_turn: the system prompt and snapshots
of a fake home with a 250-line MEMORY.md and topic files, the built-in tools, a plain "hi"), measured for
five cases on Windows and on Linux, each pinned as an upper bound:

    an unknown remote model (the 32,768 default), a 16,384 window, 49,152, 65,536 (lean), a 200k cloud model

The unknown remote case must leave prompt + the reply's room at or under 26,000 of 32,768 and go out at
32,768 on both platforms (3.3.16.0 sent 16,970 + 16,384 and doubled the window to 65,536). Never a server,
never a model call. When one fails: a new tool or new prompt text pushed the first turn past its bound.
Run: python -m tests.test_prompt_budget_pins
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("BRIDGE_TEST_HOME", tempfile.mkdtemp(prefix="pb_pins-"))
os.environ.setdefault("BRIDGE_TEST_NO_BACKGROUND_NET", "1")

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()

# 3.6.0.10 M1b (2026-11-21): every case measures a NEW top session in the folder (crew/session_start.py: its control,
# the agents it finds, the Agent, Task and Workflow tools' lineup), as a real session starts. Each case's first turn
# on the base 9624c426 (F_W, win32 / linux; the larger is F_W):
#   an unknown remote model 8,014 / 7,975; 16,384 6,272 / 6,269; 49,152 8,012 / 7,973; 65,536 (lean) 8,012 / 7,973;
#   a 200k cloud model 17,255 / 16,905 (17,310 / 16,961 measured so: the lineup line on the Agent and Task tools; the
#   lean cases are byte-equal, the lean copies drop that line).
# (label, model ref, window, prompt bound, tool block bound, sent window)
CASES = (("an unknown remote model", "ol:room-model", 32768, 9000, 4500, 32768),
         ("a 16,384 window", "ol:tiny:3b@lan", 16384, 7000, 2200, 16384),
         ("a 49,152 window", "ol:qwen3-coder:30b@lan", 49152, 9000, 4500, 49152),
         ("a 65,536 window (lean)", "ol:qwen3-coder:30b@lan", 65536, 9000, None, 65536),
         ("a 200k cloud model", "ant:claude-opus-5-5", 200000, 18000, None, 200000))
# A real new Auto session someone answers also carries the Builder (headless.py adds it); on the base a request sent it
# only at 65,536 and up. Its wire size on the base 9624c426: 1,024 tokens (2026-11-21). These cases pin that session: the
# window's bound above plus the Builder's size, so the Builder cannot grow unseen either:
#   65,536: 9,000 + 1,024 = 10,024 (measured 9,036 / 8,997); 200k cloud: 18,000 + 1,024 = 19,024 (18,593 / 18,244).
# MW batch 4 (2026-11-21), the bounds unchanged: a lean main reads the Builder's short words (386 tokens; 403 with the
# Auto sentence), sent from 32,768: 32,768 8,581 / 8,542 (tool block 4,383 of 4,500); 49,152 8,579 / 8,540 (4,383);
# 65,536 8,579 / 8,540 (was 9,200 / 9,161); 200k cloud on Auto, the long words with the Auto sentence (1,041):
# 18,858 / 18,509 (was 18,841 / 18,492). Today's long words (not Auto) stay 1,024.
BUILDER_WIRE = 1024
# (label, model ref, window, prompt bound, sent window)
REAL_CASES = (("a new Auto session at 65,536", "ol:qwen3-coder:30b@lan", 65536, 9000 + BUILDER_WIRE, 65536),
              ("a new Auto session on a 200k cloud model", "ant:claude-opus-5-5", 200000, 18000 + BUILDER_WIRE, 200000))
# At 16,384 the Builder is not sent: the tools are the same; the system text only names it among the tools left out
NO_BUILDER = (("a 16,384 window", "ol:tiny:3b@lan", 16384),)
# 3.6.0.10 MW batch 4 (the owner, 2026-11-21: a local main may be sent the Builder): at 32,768 and 49,152 it is sent in
# its short words (tools/lean_descriptions.py) inside the same tool block bound (4,500) and prompt bound (9,000); the
# other tools sent are the same. (label, model ref, window, prompt bound, tool block bound): the CASES' own bounds.
LEAN_BUILDER = tuple((label, ref, window, prompt_max, tools_max) for label, ref, window, prompt_max, tools_max, _s in CASES
                     if window in (32768, 49152))
BY_NAME_MAX = 40  # "Other tools you can call by name (...): Builder." where no such line was (linux), else ", Builder"
AUTO_SEVEN = ("planner", "researcher", "coder", "reviewer", "writer", "media-reader", "ops")
UNKNOWN_TOTAL = 26000
SYSTEM_LEAN = 4000
_HOME: dict = {}


def why(what: str, bound: int) -> str:
    return (f"a new tool or prompt text pushed {what} past {bound:,}: give it a lean description "
            f"(tools/lean_descriptions.py), defer it, or raise this bound on purpose and say why in the CHANGELOG")


def _home() -> dict:
    from tests.helpers.fake_home import build_fake_home
    if "fh" not in _HOME:
        _HOME["fh"] = build_fake_home()
        os.environ["BRIDGE_TEST_HOME"] = str(_HOME["fh"]["home"])
    return _HOME["fh"]


def _measure(ref: str, window: int, platform: str, **kw) -> dict:
    from halo_harness.agent.prompt_measure import first_turn
    return first_turn(ref, window=window, platform=platform, cwd=_home()["proj"], **kw)


def _pins(ctx: Ctx, platform: str) -> None:
    for label, ref, window, prompt_max, tools_max, sent in CASES:
        m = _measure(ref, window, platform)
        tools = sum(r["tokens"] for r in m["tools"] if r["offered"])
        ctx.check(f"{platform}, {label}: the first turn is {m['prompt']:,} tokens -- " + why("the first turn", prompt_max),
                  m["prompt"] <= prompt_max)
        if tools_max is not None:
            ctx.check(f"{platform}, {label}: the tool block is {tools:,} tokens -- " + why("the lean tool block", tools_max),
                      tools <= tools_max)
        ctx.check(f"{platform}, {label}: sent at {m['sent_window']} (want {sent:,}) -- the prompt plus the reply's room "
                  f"({m['total']:,}) no longer fits the window it starts from", m["sent_window"] == sent)
        if window < 65536:
            ctx.check(f"{platform}, {label}: lean, got {m['lean']}", m["lean"] is True)


@test
def test_the_five_cases_on_windows(ctx: Ctx):
    _pins(ctx, "win32")


@test
def test_the_five_cases_on_linux(ctx: Ctx):
    _pins(ctx, "linux")


@test
def test_an_unknown_remote_model_stays_well_inside_32768(ctx: Ctx):
    for platform in ("win32", "linux"):
        m = _measure("ol:room-model", 32768, platform)
        ctx.check(f"{platform}: prompt + the reply's room {m['total']:,} -- " + why("prompt + room", UNKNOWN_TOTAL),
                  m["total"] <= UNKNOWN_TOTAL)
        ctx.check(f"{platform}: the window sent is 32,768, got {m['sent_window']}", m["sent_window"] == 32768)
        ctx.check(f"{platform}: the reply's room is a quarter of it, got {m['reply_room']}", m["reply_room"] == 8192)
        ctx.check(f"{platform}: the system message (memory in it) is {m['system_message']:,} -- "
                  + why("the lean system message", SYSTEM_LEAN), m["system_message"] <= SYSTEM_LEAN)


@test
def test_the_cloud_case_is_not_lean_and_carries_every_tool(ctx: Ctx):
    m = _measure("ant:claude-opus-5-5", 200000, "linux")
    ctx.check(f"a 200k cloud model is not lean, got {m['lean']}", m["lean"] is False)
    ctx.check(f"every tool offered, got {[r['name'] for r in m['tools'] if not r['offered']]}",
              all(r["offered"] for r in m["tools"]))


@test
def test_the_measured_session_is_a_new_auto_session(ctx: Ctx):
    """3.6.0.10 M1b: the stub a pin measures has what a real new Auto session has: control "auto", the 15 names (Auto's
    seven and the eight built-ins), the Agent, Task and Workflow tools' lineup, depth 0, no restriction."""
    from halo_harness.agent.prompt_measure import new_session
    from halo_harness.config.agents_md import BUILTIN_NAMES
    for control in ("auto", None):  # None: the folder's own control, which is Auto in a home that set no map
        s = new_session("ol:tiny:3b@lan", window=16384, platform="linux", cwd=_home()["proj"], control=control,
                        builder=True)
        names = list(s.agent_runtime.agents)
        ctx.check(f"control {control!r}: the session's control is auto, got {getattr(s.team_control, 'name', None)!r}",
                  getattr(s.team_control, "name", None) == "auto"
                  and s.agent_runtime.team_control is s.team_control)
        ctx.check(f"control {control!r}: the 15 names, got {names}",
                  len(names) == 15 and set(names) == set(AUTO_SEVEN) | set(BUILTIN_NAMES))
        ctx.check(f"control {control!r}: depth 0, no restriction",
                  s.agent_runtime.depth == 0 and s.agent_type_restriction is None)
        lineups = {n: getattr(s.tool_registry.get(n), "lineup", "-") for n in ("Agent", "Task", "Workflow")}
        ctx.check(f"control {control!r}: the tools' lineup is auto, got {lineups}",
                  all(v == "auto" for v in lineups.values()))
        ctx.check("the Builder is registered", s.tool_registry.get("Builder") is not None)
    s = new_session("ant:claude-opus-5-5", window=200000, platform="linux", cwd=_home()["proj"], control="auto")
    ctx.check("the cloud Agent tool carries the lineup line a new session's has",
              "The lineup is auto" in s.tool_registry.get("Agent").definition()["description"])
    m = _measure("ant:claude-opus-5-5", 200000, "linux", control="auto", builder=True)
    ctx.check("first_turn measures it: the Builder is sent on the cloud",
              any(r["name"] == "Builder" and r["offered"] for r in m["tools"]))


@test
def test_a_real_new_auto_session_with_the_builder(ctx: Ctx):
    """3.6.0.10 M1b: the real new Auto session, the Builder on the wire, at 65,536 and on the cloud."""
    from halo_harness.agent.prompt_diet import wire_tokens
    from halo_harness.tools.builder_tool import BuilderTool
    size = wire_tokens(BuilderTool().definition())
    ctx.check(f"the Builder's wire size is {size:,}, at most {BUILDER_WIRE:,} -- " + why("the Builder", BUILDER_WIRE),
              size <= BUILDER_WIRE)
    for platform in ("win32", "linux"):
        for label, ref, window, prompt_max, sent in REAL_CASES:
            m = _measure(ref, window, platform, control="auto", builder=True)
            ctx.check(f"{platform}, {label}: the Builder is sent",
                      any(r["name"] == "Builder" and r["offered"] for r in m["tools"]))
            ctx.check(f"{platform}, {label}: the first turn is {m['prompt']:,} tokens -- "
                      + why("the first turn", prompt_max), m["prompt"] <= prompt_max)
            ctx.check(f"{platform}, {label}: sent at {m['sent_window']} (want {sent:,})", m["sent_window"] == sent)


@test
def test_at_16384_the_real_session_sends_no_builder_and_at_32768_and_49152_its_short_words(ctx: Ctx):
    """3.6.0.10 M1b: at 16,384 a real new Auto session sends the same tools as the pins measure; the only difference is
    the Builder's name among the tools left out (the by-name line). MW batch 4: at 32,768 and 49,152 it sends the same
    tools plus the Builder in its short words, inside the same bounds (on the base it sent no Builder there)."""
    for platform in ("win32", "linux"):
        for label, ref, window, prompt_max, tools_max in LEAN_BUILDER:
            old = _measure(ref, window, platform)
            new = _measure(ref, window, platform, control="auto", builder=True)
            sent_old = [(r["name"], r["tokens"]) for r in old["tools"] if r["offered"]]
            sent_new = [(r["name"], r["tokens"]) for r in new["tools"] if r["offered"]]
            tools = sum(t for _n, t in sent_new)
            ctx.check(f"{platform}, {label}: the same tools and the Builder, got {[n for n, _t in sent_new]}",
                      [x for x in sent_new if x[0] != "Builder"] == sent_old and "Builder" in [n for n, _t in sent_new])
            ctx.check(f"{platform}, {label}: the tool block is {tools:,} -- " + why("the lean tool block", tools_max),
                      tools <= tools_max)
            ctx.check(f"{platform}, {label}: the first turn is {new['prompt']:,} -- " + why("the first turn", prompt_max),
                      new["prompt"] <= prompt_max and new["sent_window"] == old["sent_window"])
            ctx.check(f"{platform}, {label}: the system message is {new['system_message']:,} -- "
                      + why("the lean system message", SYSTEM_LEAN), new["system_message"] <= SYSTEM_LEAN)
    for platform in ("win32", "linux"):
        for label, ref, window in NO_BUILDER:
            old = _measure(ref, window, platform)
            new = _measure(ref, window, platform, control="auto", builder=True)
            sent_old = [(r["name"], r["tokens"]) for r in old["tools"] if r["offered"]]
            sent_new = [(r["name"], r["tokens"]) for r in new["tools"] if r["offered"]]
            ctx.check(f"{platform}, {label}: the same tools sent, got {len(sent_new)} vs {len(sent_old)}",
                      sent_new == sent_old and "Builder" not in [n for n, _t in sent_new])
            grew, sys_grew = new["prompt"] - old["prompt"], new["system_message"] - old["system_message"]
            ctx.check(f"{platform}, {label}: only the by-name line grew ({grew} tokens, system {sys_grew})",
                      0 <= grew <= BY_NAME_MAX and 0 <= sys_grew <= BY_NAME_MAX and "Builder" in new["left_out"]
                      and new["sent_window"] == old["sent_window"])


# 3.6.0.10 M7: on Auto main's lean text carries a block (agent/helpers_words.py: when to hand work out, the kinds it can
# start; a tail for the Workflow tool when a request sends it, and no line about the Builder) in place of today's
# 61-token delegate line. Block and longest tail hold at most crew/kinds.py CAP tokens, and CAP is at most each lean
# case's CAP_W = min(300, B_W - F_W + 61 - 100): B_W its bound, F_W its first turn on the base 9624c426 (the larger
# figure, written above CASES and REAL_CASES), 100 kept free. Measured 2026-11-21: block 225 (clean home), longest tail
# 28 (M3 alone; it was 74 with the Builder line, now gone). A new Auto session at 65,536 with the Builder sent:
# 9,200 / 9,161 (it was 9,246 / 9,207 with that line); every other lean case is unchanged. No bound moved.
F_W = {"an unknown remote model": 8014, "a 16,384 window": 6272, "a 49,152 window": 8012,
       "a 65,536 window (lean)": 8012, "a new Auto session at 65,536": 9036}
TODAY_LINE = 61
M2_HEAD = "- Helpers you can start now (`subagent_type`): "


def _lean_cases():
    """(label, ref, window, prompt bound, tool block bound or None, builder) of every lean case."""
    out = [(label, ref, window, bound, tools, False) for label, ref, window, bound, tools, _s in CASES if window < 200000]
    return out + [(label, ref, window, bound, None, True) for label, ref, window, bound, _s in REAL_CASES
                  if window < 200000]


def _lean_text(ref: str, window: int, platform: str, cwd, **kw):
    """(the session, its lean system text): the measure's own stub (prompt_measure.new_session) shaped as a request."""
    from halo_harness.agent.prompt_measure import new_session
    from halo_harness.agent.prompt_wire import shape
    s = new_session(ref, window=window, platform=platform, cwd=cwd, **kw)
    msgs = [{"role": "user", "content": [{"type": "text", "text": "hi"}]}]
    text, _m, _t = shape(s, s.session_context.system_prompt, msgs, s.tool_registry.definitions(), purpose="measure")
    return s, text


def _block_holds(ctx: Ctx, where: str, cwd) -> None:
    from halo_harness.agent.helpers_words import frozen, longest_tail
    from halo_harness.agent.prompt_composition import tokens_of
    from halo_harness.crew.kinds import CAP
    for platform in ("win32", "linux"):
        for label, ref, window, bound, tools_max, builder in _lean_cases():
            kw = {"control": "auto", "builder": True} if builder else {}
            m = first_turn_at(ref, window, platform, cwd, **kw)
            tools = sum(r["tokens"] for r in m["tools"] if r["offered"])
            ctx.check(f"{where}, {platform}, {label}: the first turn is {m['prompt']:,} tokens -- "
                      + why("the first turn", bound), m["prompt"] <= bound)
            if tools_max is not None:
                ctx.check(f"{where}, {platform}, {label}: the tool block is {tools:,} -- " + why("the tool block", tools_max),
                          tools <= tools_max)
            if window == 32768:
                ctx.check(f"{where}, {platform}, {label}: the system message is {m['system_message']:,} -- "
                          + why("the lean system message", SYSTEM_LEAN), m["system_message"] <= SYSTEM_LEAN)
            s, text = _lean_text(ref, window, platform, cwd, **kw)
            block = frozen(s) or ""
            size = tokens_of(block) + tokens_of(longest_tail())
            ctx.check(f"{where}, {platform}, {label}: M2's head in the lean text", M2_HEAD in text and block in text)
            ctx.check(f"{where}, {platform}, {label}: block and longest tail {size} <= CAP {CAP}", size <= CAP)


def first_turn_at(ref: str, window: int, platform: str, cwd, **kw) -> dict:
    from halo_harness.agent.prompt_measure import first_turn
    return first_turn(ref, window=window, platform=platform, cwd=cwd, **kw)


@test
def test_the_block_holds_its_cap_at_every_lean_window(ctx: Ctx):
    from halo_harness.crew.kinds import CAP
    for label, _ref, _w, bound, _t, _b in _lean_cases():
        cap_w = min(300, bound - F_W[label] + TODAY_LINE - 100)
        ctx.check(f"{label}: CAP {CAP} <= CAP_W {cap_w}", CAP <= cap_w)
    _block_holds(ctx, "the pins' home", _home()["proj"])


@test
def test_thirty_agents_of_his_and_forty_claude_code_agents(ctx: Ctx):
    """M7: with 30 agents of his and 40 Claude Code agents every pin holds, the block gives way (his names first)."""
    from tests.helpers.fake_home import build_fake_home
    fh = _home()
    before = os.environ.get("BRIDGE_TEST_HOME")
    big = build_fake_home()
    os.environ["BRIDGE_TEST_HOME"] = str(big["home"])
    try:
        from halo_harness.crew.store import state_dir_of
        mine = state_dir_of() / "crew" / "agents"
        mine.mkdir(parents=True, exist_ok=True)
        for i in range(30):
            (mine / f"his-{i:02d}.yaml").write_text(
                f"format: agent/1\nname: his-{i:02d}\ndoes: Does the job number {i} for the owner every day.\n"
                "model: auto\nuses:\n- read\ncareful: ask-changes\n", encoding="utf-8")
        cc = Path(big["claude_dir"]) / "agents"
        cc.mkdir(parents=True, exist_ok=True)
        for i in range(40):
            (cc / f"cc-{i:02d}.md").write_text(f"---\nname: cc-{i:02d}\ndescription: Helper number {i}.\n---\n"
                                               f"You are helper {i}.\n", encoding="utf-8")
        _block_holds(ctx, "30 of his, 40 Claude Code", big["proj"])
        s, text = _lean_text("ol:tiny:3b@lan", 16384, "linux", big["proj"])
        ctx.check("his own lead, the rest counted", (M2_HEAD + "his-00, his-01") in text
                  and " more (a wrong name lists them all). With no `subagent_type`" in text)
    finally:
        os.environ["BRIDGE_TEST_HOME"] = before if before is not None else str(fh["home"])


@test
def test_copilot_set_up_grows_the_lean_first_turn_by_its_lean_size_at_most(ctx: Ctx):
    """3.3.17.0: with Copilot not set up (the default, every pin above) copilot_ask is not registered; set up,
    a lean first turn grows by no more than the tool's lean wire size."""
    from halo_harness.agent.prompt_diet import wire_tokens
    from halo_harness.theme import set_config_value, unset_config_value
    from halo_harness.tools.copilot_ask import CopilotAskTool
    from halo_harness.tools.lean_descriptions import lean_definition
    size = wire_tokens(lean_definition(CopilotAskTool().definition()))
    for label, ref, window in (("an unknown remote model", "ol:room-model", 32768), ("a 49,152 window", "ol:qwen3-coder:30b@lan", 49152)):
        for platform in ("win32", "linux"):
            before = _measure(ref, window, platform)
            set_config_value("copilot.tenant", "pretend-tenant")
            set_config_value("copilot.client_id", "00000000-0000-0000-0000-000000000000")
            try:
                after = _measure(ref, window, platform)
            finally:
                unset_config_value("copilot.tenant")
                unset_config_value("copilot.client_id")
            names = [r["name"] for r in after["tools"]]
            ctx.check(f"{platform}, {label}: copilot_ask registered once set up, got {'copilot_ask' in names}",
                      "copilot_ask" in names and "copilot_ask" not in [r["name"] for r in before["tools"]])
            ctx.check(f"{platform}, {label}: the first turn grew {after['prompt'] - before['prompt']:,} tokens, "
                      f"at most the tool's lean {size:,}", after["prompt"] - before["prompt"] <= size)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
