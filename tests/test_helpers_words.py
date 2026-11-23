"""tests.test_helpers_words -- 3.6.0.10 MW rules M4 and M6: what main is told about handing work out.

M4: on Auto (a top session on the default map, no restriction, the Agent tool, a model that takes tools) main's lean
system text trades today's one delegate line for a FROZEN block (agent/helpers_words.py: when to hand work out; the
kinds THIS session can start, his own first), made at the first shaping and kept byte-equal, made again only when
main's model changes (A1). On his map, with roles off, in an `--agent` session, restricted, as a sub-agent, or for a
model that takes no tools, today's line stays letter for letter.
M6: per request, after the tools are capped (agent/prompt_wire.py), a short TAIL names the Workflow tool (when that
request sends it and it lists his workflows), and nothing else; the frozen part never changes with it. At 16,384 the
Builder is not sent, so main reads no word of it but its name among the tools left out; from 32,768 (MW batch 4) it is
sent and main reads only its own words: no tail line tells main to propose unasked (M4 below is the words that must not
be sent: the decisions' section 3). MW batch 4: the propose words live in the Builder's own words, on Auto only.
A scratch home of its own per test (ConfigHome restores every variable); never a model, a server or the network.
Run: python -m tests.test_helpers_words
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("BRIDGE_TEST_NO_BACKGROUND_NET", "1")

from tests.helpers.config_seed import ConfigHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
TODAY_ON = ("- On a big job delegate surveys, searches, test runs and mechanical edits with the Agent tool (`role:` picks "
            "the model table's model), independent pieces in parallel; keep judgement and the final review yourself.")
TODAY_OFF = ("- On a big job delegate surveys, searches, test runs and mechanical edits with the Agent tool (`model:` "
             "names a cheaper model), independent pieces in parallel; keep judgement and the final review yourself.")
M1 = ("- Hand work out instead of doing it all yourself: give each part of a job that can run on its own (a search or "
      "survey, a plan, a review, a test run, mechanical edits, a file your model cannot read) to a helper with the Agent "
      "tool; helpers on one job share one `task`; run independent parts in parallel; keep judgement and the final "
      "review yourself.")
M2_CLEAN = ("- Helpers you can start now (`subagent_type`): planner (plan, outline); researcher (research, investigate); "
            "coder (implement, fix, refactor); reviewer (review, audit, judge); writer (summarize, draft, docs, "
            "changelog); media-reader (image, screenshot, video, audio, pdf, transcribe); ops (deploy, release, install, "
            "ci); Judge (pass or fail a result); Tester (run tests, report). With no `subagent_type` Halo picks a kind "
            "from your words.")
M2_HEAD = "- Helpers you can start now (`subagent_type`): "
M3 = "- The Workflow tool lists workflows you can run by `name`: run one when it fits the whole job."
M4 = ("- Unasked, you may propose a helper or a workflow for work that will come back, with the Builder tool; nothing "
      "is written until the person approves its card.")
BY_NAME = "Other tools you can call by name"


class _Home(ConfigHome):
    def __enter__(self):
        super().__enter__()
        self._ollama = os.environ.get("OLLAMA_HOST")
        os.environ["OLLAMA_HOST"] = "http://127.0.0.1:9"
        return self

    def __exit__(self, *exc):
        if self._ollama is None:
            os.environ.pop("OLLAMA_HOST", None)
        else:
            os.environ["OLLAMA_HOST"] = self._ollama
        return super().__exit__(*exc)


def _session(h, *, window=16384, platform="linux", control="auto", builder=False, ref="ol:tiny:3b@lan"):
    from halo_harness.agent.prompt_measure import new_session
    return new_session(ref, window=window, platform=platform, cwd=h.repo, control=control, builder=builder)


def _shaped(s, text: str = "hi"):
    """(the system text, the names sent) of one request, shaped as a real one is (agent/prompt_wire.shape)."""
    from halo_harness.agent.prompt_wire import shape
    msgs = [{"role": "user", "content": [{"type": "text", "text": text}]}]
    out, _m, sent = shape(s, s.session_context.system_prompt, msgs, s.tool_registry.definitions(), purpose="measure")
    return out, [t.get("name") for t in sent or []]


def _his(h, name: str, does: str) -> None:
    folder = h.state / "crew" / "agents"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.yaml").write_text(f"format: agent/1\nname: {name}\ndoes: {does}\nmodel: auto\nuses:\n- read\n"
                                         "careful: ask-changes\n", encoding="utf-8")


def _todays(ctx: Ctx, label: str, text: str, line: str = TODAY_ON) -> None:
    ctx.check(f"{label}: today's line, letter for letter", line in text)
    ctx.check(f"{label}: no block", M1 not in text and M2_HEAD not in text and M3 not in text and M4 not in text)


@test
def test_todays_line_where_main_is_not_on_auto(ctx: Ctx):
    """His map, roles off, an `--agent` session (no map), a restricted one, a sub-agent, a model that takes no tools."""
    from halo_harness.crew.session_start import start_control, tool_state
    from halo_harness.theme import set_config_value
    with _Home() as h:
        maps = h.state / "crew" / "maps"
        maps.mkdir(parents=True)
        (maps / "mine.yaml").write_text("format: map/1\nname: mine\nboxes:\n- {id: coder, agent: coder}\nlines:\n"
                                        "- {from: main, to: coder}\n", encoding="utf-8")
        s = _session(h, control="mine")
        ctx.check(f"his map is held, got {getattr(s.team_control, 'name', None)!r}",
                  str(getattr(s.team_control, "name", None)).endswith("mine"))
        _todays(ctx, "his map", _shaped(s)[0])
        s = _session(h)
        s.team_control = start_control(None, cwd=h.repo)  # an `--agent` session: a plain session's answers, no map
        tool_state(s, s.team_control)
        _todays(ctx, "an --agent session", _shaped(s)[0])
        s = _session(h)
        s.agent_type_restriction = {"planner"}
        _todays(ctx, "a restricted session", _shaped(s)[0])
        s = _session(h)
        s.agent_runtime.depth = 1
        _todays(ctx, "a sub-agent", _shaped(s)[0])
        s = _session(h)
        s._prompt_card = {"tools": "none"}
        _todays(ctx, "a model that takes no tools", _shaped(s)[0])
        s = _session(h)
        s._helpers_off = True
        _todays(ctx, "the block turned off", _shaped(s)[0])
        set_config_value("roles.enabled", False)
        s = _session(h, control=None)
        ctx.check(f"roles off holds no control, got {s.team_control!r}", s.team_control is None)
        _todays(ctx, "roles off", _shaped(s)[0], TODAY_OFF)


@test
def test_on_auto_main_reads_when_to_hand_out_and_the_kinds(ctx: Ctx):
    with _Home() as h:
        for platform in ("win32", "linux"):
            text, _sent = _shaped(_session(h, platform=platform))
            ctx.check(f"{platform}: today's line is gone", TODAY_ON not in text)
            ctx.check(f"{platform}: M1 and M2, word for word, in the rules", (M1 + "\n" + M2_CLEAN) in text)
            ctx.check(f"{platform}: Halo's GUI line still follows",
                      (M2_CLEAN + "\n- Halo's GUI (agents, workflows, the map)") in text)


@test
def test_frozen_for_ten_requests_and_a_saved_agent_and_made_again_on_a_new_model(ctx: Ctx):
    from halo_harness.crew.session_start import new_session_state
    from halo_harness.model import parse_model_ref
    with _Home() as h:
        s = _session(h)
        first, _sent = _shaped(s)
        texts = []
        for i in range(10):
            if i == 5:  # an agent saved mid-session: the next session lists it; this one keeps its block
                _his(h, "sorter", "Sorts the inbox by sender and date.")
                s.agent_runtime.agents.update(new_session_state(type(s)(), cwd=h.repo).agent_runtime.agents)
            texts.append(_shaped(s, f"request {i}")[0])
        ctx.check("ten requests, a saved agent between: the system text is byte-equal",
                  all(t == first for t in texts) and "sorter" in s.agent_runtime.agents and "sorter" not in first)
        s.model_ref = parse_model_ref("ol:qwen3-coder:30b@lan")  # main's model changes (/model): made again
        again, _sent = _shaped(s)
        ctx.check("after the model changes the block is made again, his own first",
                  (M2_HEAD + "sorter (Sorts the inbox by sender and date); planner (") in again)
        ctx.check("and kept from then on", _shaped(s, "one more")[0] == again)


@test
def test_told_names_what_main_read_after_a_put(ctx: Ctx):
    """3.6.0.15 U6: an agent put and taken into the running session (crew/use_now.py) is told by N1 and listed as
    `kinds_added`; the block main reads and `kinds_told` stay the kinds the session STARTED with, also when the block is
    made again for another model."""
    from halo_harness.agent.helpers_words import told
    from halo_harness.crew import use_now
    from halo_harness.model import parse_model_ref
    with _Home() as h:
        s = _session(h)
        first, _sent = _shaped(s)
        before = told(s)
        body = {"format": "agent/1", "name": "sorter", "does": "Sorts the inbox by sender and date.", "uses": ["read"],
                "careful": "ask-changes", "model": "auto"}
        ctx.check("the put took", use_now.put(s, body, "yours", "c" * 64) == (True, ""))
        use_now.take(s)
        ctx.check("main can start sorter", "sorter" in s.agent_runtime.agents)
        ctx.check(f"kinds_told is what main read, got {told(s)} vs {before}",
                  before and told(s) == before and "sorter" not in (told(s) or {}).get("kinds_told", []))
        ctx.check("the system text is byte-equal", _shaped(s, "again")[0] == first)
        s.model_ref = parse_model_ref("ol:qwen3-coder:30b@lan")
        again, _sent = _shaped(s)
        ctx.check("made again for another model: the kinds it started with, no sorter",
                  M2_HEAD in again and "sorter" not in again)
        ctx.check(f"kinds_told still names no sorter, got {told(s)}", "sorter" not in (told(s) or {}).get("kinds_told", []))


@test
def test_a_real_session_on_auto_reads_the_block_and_one_with_no_map_todays_line(ctx: Ctx):
    """A real agent.loop.Session, built as headless.build_session builds one: on the default map (Auto) and with no
    map (an `--agent` session); its request shaped as the loop shapes it. Never a model call."""
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.loop import Session
    from halo_harness.agent.prompt_wire import shape
    from halo_harness.config.agents_md import discover_agents
    from halo_harness.crew import map_session
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.providers.stream import ProviderCreds
    from halo_harness.tools.registry import ToolRegistry, default_tools
    with _Home() as h:
        compiled = map_session.prepare(None, h.repo)[0]
        agents = map_session.agents(discover_agents(h.repo, settings=None), compiled)[0]
        for crew_map, label in ((compiled, "Auto"), (None, "no map (an --agent session)")):
            ref = "ol:tiny:3b@lan"
            reg = ToolRegistry(default_tools())
            sc = SessionContext(cwd=h.repo, model_label=ref, tool_registry=reg)
            s = Session(cwd=h.repo, model_ref=parse_model_ref(ref), model_profile=ModelProfile(context_tokens=16384),
                        creds=ProviderCreds(base_url="http://127.0.0.1:9", api_key="k"), state_dir=h.state,
                        model_label=ref, session_context=sc, max_turns=5, agents=agents, crew_map=crew_map)
            s.interactive = True  # the terminal app's session (controller.py)
            msgs = [{"role": "user", "content": [{"type": "text", "text": "hi"}]}]
            text, _m, _sent = shape(s, sc.system_prompt, msgs, reg.definitions(), purpose="turn")
            if crew_map is not None:
                ctx.check(f"{label}: M1 and M2 in place of today's line",
                          (M1 + "\n" + M2_CLEAN) in text and TODAY_ON not in text)
            else:
                _todays(ctx, label, text)
            want = MODE_LINE + ("\n" + M10 if crew_map is not None else "")  # 3.6.0.14 MW2: a local main's turn
            ctx.check(f"{label}: the turn's mode snapshot", _turn(s) == want)


@test
def test_a_one_shot_on_auto_reads_the_block_like_the_terminal_and_studio(ctx: Ctx):
    """3.6.0.12 OS (rewritten from the MW repair of 2026-11-21, where a one-shot read today's line letter for letter):
    a one-shot (`halo -p` with one prompt: headless.run_print_mode sets `many_turns` False) on Auto reads M1 and M2 like
    the same session facts in the terminal app (`interactive`, controller.py) and in a Studio session (stream-json:
    `many_turns` True), because its first ask now carries the tool block of the window it asks
    (prompt_wire.one_shot_shaper). The block is frozen at its first shaping. A local and a cloud model; the Agent tool's
    own kinds (M8) stay in every mode."""
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.helpers_words import told
    from halo_harness.agent.loop import Session
    from halo_harness.agent.prompt_wire import shape
    from halo_harness.config.agents_md import discover_agents
    from halo_harness.crew import map_session
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.providers.stream import ProviderCreds
    from halo_harness.tools.registry import ToolRegistry, default_tools
    with _Home() as h:
        compiled = map_session.prepare(None, h.repo)[0]
        agents = map_session.agents(discover_agents(h.repo, settings=None), compiled)[0]

        def real(ref, window, mode):
            reg = ToolRegistry(default_tools())
            sc = SessionContext(cwd=h.repo, model_label=ref, tool_registry=reg)
            s = Session(cwd=h.repo, model_ref=parse_model_ref(ref), model_profile=ModelProfile(context_tokens=window),
                        creds=ProviderCreds(base_url="http://127.0.0.1:9", api_key="k"), state_dir=h.state,
                        model_label=ref, session_context=sc, max_turns=5, agents=agents, crew_map=compiled)
            if mode == "one-shot":
                s.many_turns = False  # headless.run_print_mode, `-p` with one prompt
            elif mode == "terminal":
                s.interactive = True  # controller.py: the terminal app, and Studio's and remote sessions
            elif mode == "stream-json":
                s.many_turns = True  # headless.run_print_mode, `-p --input-format stream-json`
            elif mode == "unmarked":
                pass  # a session a script or a tool builds: neither mark
            else:
                s._helpers_off = True  # the same facts with the block turned off: today's text
            msgs = [{"role": "user", "content": [{"type": "text", "text": "hi"}]}]
            text = shape(s, sc.system_prompt, msgs, reg.definitions(), purpose="turn")[0]
            return s, text, getattr(reg.get("Agent"), "kinds_tail", "")

        s, local, _k = real("ol:tiny:3b@lan", 16384, "one-shot")
        ctx.check("a local one-shot: M1 and M2 in place of today's line",
                  (M1 + "\n" + M2_CLEAN) in local and TODAY_ON not in local)
        terminal = real("ol:tiny:3b@lan", 16384, "terminal")[1]
        ctx.check("a local one-shot: its whole system text is the terminal app's, byte for byte", local == terminal)
        ctx.check("a local one-shot: the same text on its second request", shape(
            s, s.session_context.system_prompt, [{"role": "user", "content": [{"type": "text", "text": "again"}]}],
            s.tool_registry.definitions(), purpose="turn")[0] == local)
        ctx.check(f"a local one-shot: the status row names the kinds it read, got {told(s)!r}",
                  bool((told(s) or {}).get("kinds_told")))
        # the join: ONE rule. A one-shot here is exactly a session the window ladder sizes by its prompt, however it
        # was marked or left unmarked: a session a script builds sets neither mark and is on the ladder too
        unmarked = real("ol:tiny:3b@lan", 16384, "unmarked")[1]
        ctx.check("a local session that sets neither mark reads the same text, byte for byte", unmarked == local)
        _todays(ctx, "the same session with the block turned off", real("ol:tiny:3b@lan", 16384, "today")[1])
        from types import SimpleNamespace
        from halo_harness.agent import helpers_words as H
        from halo_harness.agent.ollama_window_truth import many_turns
        marks = [{}, {"many_turns": False}, {"many_turns": True}, {"interactive": True}, {"interactive": False},
                 {"many_turns": False, "interactive": True}, {"many_turns": True, "interactive": False}]
        ctx.check("a one-shot is exactly what the window ladder sizes by its prompt, however the session is marked",
                  all(H.one_shot(SimpleNamespace(**m)) == (not many_turns(SimpleNamespace(**m))) for m in marks)
                  and H.one_shot(SimpleNamespace()) and not H.one_shot(SimpleNamespace(interactive=True)))
        for mode in ("terminal", "stream-json"):
            s, text, _k = real("ol:tiny:3b@lan", 16384, mode)
            ctx.check(f"a local session in {mode}: M1 and M2 in place of today's line",
                      (M1 + "\n" + M2_CLEAN) in text and TODAY_ON not in text)
            ctx.check(f"a local session in {mode}: the status row names the kinds it read",
                      bool((told(s) or {}).get("kinds_told")))
        cloud = {mode: real("ant:claude-opus-5-5", 200000, mode) for mode in ("one-shot", "terminal")}
        for mode, (s, text, kinds) in cloud.items():
            ctx.check(f"a cloud {mode}: no M1, no M2 head, no M3 in the system text",
                      M1 not in text and M2_HEAD not in text and M3 not in text)
            ctx.check(f"a cloud {mode}: the Agent tool's own words still end with the kinds (M8)", bool(kinds))
        ctx.check("a cloud one-shot reads what the terminal app reads, byte for byte (the system text and the kinds)",
                  cloud["one-shot"][1:] == cloud["terminal"][1:])


def _frozen_part(text: str) -> str:
    """The system text up to its tail and by-name line (what must not change between requests)."""
    for mark in ("\n\n" + M3, "\n\n" + M4, "\n\n" + BY_NAME):
        if mark in text:
            text = text[:text.index(mark)]
    return text


@test
def test_the_builder_is_sent_from_32768_and_the_system_text_says_nothing_of_it(ctx: Ctx):
    """3.6.0.10 MW batch 4 (the owner: a local main may be sent the Builder): at 16,384 it is not sent and "Builder" is
    only among the tools left out; at 32,768 and 49,152 it is sent (its short words) and main's system text holds no word
    of it and no M4. (On the base it was sent at 65,536 and up only.)"""
    with _Home() as h:
        for platform in ("win32", "linux"):
            for window in (16384, 32768, 49152):
                s = _session(h, window=window, platform=platform, builder=True)
                text, sent = _shaped(s)
                if window == 16384:
                    ctx.check(f"{platform} {window:,}: the Builder is not sent", "Builder" not in sent)
                    ctx.check(f"{platform} {window:,}: no M4, and \"Builder\" only among the tools left out",
                              M4 not in text and "Builder" not in _frozen_part(text) and BY_NAME in text)
                else:
                    ctx.check(f"{platform} {window:,}: the Builder is sent, got {sent}", "Builder" in sent)
                    ctx.check(f"{platform} {window:,}: no M4 and no word of the Builder in the system text",
                              M4 not in text and "Builder" not in text)
                ctx.check(f"{platform} {window:,}: the frozen block", M2_HEAD in text)


# The Builder's "when" sentence (tools/builder_tool.py): today's, and the Auto form (the decisions' section 3; the
# owner, 2026-11-21: "2 - yes"); today's whole description, byte for byte, by its sha256 on the base 8bf5c9c1
WHEN_TODAY = "Use it when the person asks for an agent, a workflow or a map change, never on your own."
WHEN_AUTO = ("Use it when the person asks for an agent, a workflow or a map change, or by yourself to propose an agent "
             "or a workflow for work that will come back.")
BUILDER_SHA = "9832d47c7a28792242d47e8b92c6b895d2584bb200099f121d908dc5a1b2f466"


def _proposes(text: str) -> bool:
    """Main's system text tells it to propose a helper, an agent or a workflow (today's plan-mode line "propose a plan"
    is not that, and stays)."""
    import re
    rest = text.replace("investigate and propose a plan", "")
    return "Unasked" in rest or "Builder" in rest or re.search(r"propos", rest, re.I) is not None


def _builder_words(s) -> "tuple[str, str]":
    """(the long words, the short words) of the session's Builder."""
    from halo_harness.tools.lean_descriptions import lean_definition
    d = s.tool_registry.get("Builder").definition()
    return d["description"], lean_definition(d)["description"]


def _request(s, text: str = "hi") -> "tuple[str, dict]":
    from halo_harness.agent.prompt_wire import shape
    msgs = [{"role": "user", "content": [{"type": "text", "text": text}]}]
    out, _m, sent = shape(s, s.session_context.system_prompt, msgs, s.tool_registry.definitions(), purpose="measure")
    return out, {t.get("name"): t for t in sent or []}


def _real(h, *, crew_map, restriction=None, ref="ol:room-model"):
    """A real agent.loop.Session with the Builder, as headless.build_session builds one for a session someone answers."""
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.loop import Session
    from halo_harness.config.agents_md import discover_agents
    from halo_harness.crew import map_session
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.providers.stream import ProviderCreds
    from halo_harness.tools.builder_tool import BuilderTool
    from halo_harness.tools.registry import ToolRegistry, default_tools
    agents = map_session.agents(discover_agents(h.repo, settings=None), crew_map)[0] if crew_map is not None else None
    reg = ToolRegistry(default_tools() + [BuilderTool()])
    sc = SessionContext(cwd=h.repo, model_label=ref, tool_registry=reg)
    return Session(cwd=h.repo, model_ref=parse_model_ref(ref), model_profile=ModelProfile(context_tokens=32768),
                   creds=ProviderCreds(base_url="http://127.0.0.1:9", api_key="k"), state_dir=h.state, model_label=ref,
                   session_context=sc, max_turns=5, agents=agents, crew_map=crew_map, agent_type_restriction=restriction)


@test
def test_on_auto_the_builder_may_propose_and_everywhere_else_its_words_are_todays(ctx: Ctx):
    """The decisions' section 3: the propose words live in ONE place, the Builder's own words, chosen ONCE per session at
    its start (crew/session_start.tool_state, by `on_auto`). On Auto (a local main's short words and a cloud main's long
    ones) its sentence is the Auto form and not "never on your own"; on his map, with roles off, in an `--agent` session,
    restricted: today's description byte for byte. Ten requests with an agent saved between: byte-equal Builder words;
    the system text never says "Unasked" or "propose"."""
    import hashlib
    import json
    from halo_harness.crew import map_session
    from halo_harness.crew.session_start import start_control, tool_state
    from halo_harness.theme import set_config_value
    with _Home() as h:
        for ref, window in (("ol:room-model", 32768), ("ant:claude-opus-5-5", 200000)):
            long, short = _builder_words(_session(h, window=window, builder=True, ref=ref))
            ctx.check(f"Auto, {ref}: the Auto sentence in the long and the short words, never \"never on your own\"",
                      WHEN_AUTO in long and WHEN_AUTO in short and "never on your own" not in long + short)
        ctx.check("a real Session on Auto: the Auto sentence",
                  WHEN_AUTO in _builder_words(_real(h, crew_map=map_session.prepare(None, h.repo)[0]))[0])
        s = _session(h, window=32768, builder=True, ref="ol:room-model")
        first, sent = _request(s)
        ctx.check("the request sends the Builder in its short Auto words",
                  "Builder" in sent and WHEN_AUTO in sent["Builder"]["description"])
        seen = []
        for i in range(10):
            if i == 5:
                _his(h, "sorter", "Sorts the inbox by sender and date.")
            text, sent = _request(s, f"request {i}")
            seen.append((json.dumps(sent.get("Builder"), sort_keys=True), _proposes(text)))
        ctx.check("ten requests, an agent saved between: the Builder's words byte-equal, no proposing in the system text",
                  len({w for w, _p in seen}) == 1 and not any(p for _w, p in seen) and not _proposes(first))

        def todays(label, sess):
            long, short = _builder_words(sess)
            ctx.check(f"{label}: today's description, byte for byte, and today's sentence in the short words",
                      hashlib.sha256(long.encode()).hexdigest() == BUILDER_SHA and WHEN_TODAY in short
                      and WHEN_AUTO not in short)
        maps = h.state / "crew" / "maps"
        maps.mkdir(parents=True)
        (maps / "mine.yaml").write_text("format: map/1\nname: mine\nboxes:\n- {id: coder, agent: coder}\nlines:\n"
                                        "- {from: main, to: coder}\n", encoding="utf-8")
        todays("his map", _session(h, control="mine", builder=True))
        s = _session(h, builder=True)
        s.team_control = start_control(None, cwd=h.repo)  # an `--agent` session: a plain session's answers, no map
        tool_state(s, s.team_control)
        todays("an --agent session", s)
        s = _session(h, builder=True)
        s.agent_type_restriction = {"planner"}  # known at the start, as a real Session has it
        tool_state(s, s.team_control)
        todays("a restricted session", s)
        todays("a real restricted Session",
               _real(h, crew_map=map_session.prepare(None, h.repo)[0], restriction={"planner"}))
        todays("a real --agent Session", _real(h, crew_map=None))
        set_config_value("roles.enabled", False)
        todays("roles off", _session(h, control=None, builder=True))


@test
def test_at_65536_the_builder_is_sent_and_main_reads_no_word_of_proposing_unasked(ctx: Ctx):
    """The decisions' section 3: the tail keeps only the Workflow clause, so main is never told to propose on its own
    (the Builder's own words say "never on your own"; two sentences that pull against each other are not sent). M4 is
    kept here as the words that must not be sent."""
    from halo_harness.agent.helpers_words import frozen
    with _Home() as h:
        for platform in ("win32", "linux"):
            s49 = _session(h, window=49152, platform=platform, builder=True)
            _shaped(s49)
            s = _session(h, window=65536, platform=platform, builder=True)
            text, sent = _shaped(s)
            ctx.check(f"{platform}: the Builder is sent at 65,536", "Builder" in sent)
            ctx.check(f"{platform}: no word of proposing unasked in main's system text",
                      "Unasked" not in text and M4 not in text and "propose a helper" not in text
                      and "with the Builder tool" not in text)
            ctx.check(f"{platform}: the frozen block is byte-equal to the one at 49,152",
                      frozen(s) is not None and frozen(s) == frozen(s49) and frozen(s) in text)
            s._ladder_pass = {"small": True, "turn": getattr(s, "turn_count", None)}  # agent/degrade.py's smaller ask
            small, sent_small = _shaped(s)
            ctx.check(f"{platform}: a smaller ask sends no Builder and no proposing words",
                      "Builder" not in sent_small and "Unasked" not in small and M4 not in small)
            s._ladder_pass = None
            back, _sent = _shaped(s)
            ctx.check(f"{platform}: the next request is byte-equal to the first", back == text)
            ctx.check(f"{platform}: a smaller ask changes nothing in the frozen block",
                      _frozen_part(text) == _frozen_part(small) == _frozen_part(back) and M1 in _frozen_part(text)
                      and frozen(s) == frozen(s49))


@test
def test_the_workflow_tail_names_his_workflows_only_when_sent(ctx: Ctx):
    from halo_harness.agent.helpers_words import tail
    with _Home() as h:
        s = _session(h, window=32768)
        text, sent = _shaped(s)
        ctx.check("no workflow of his: no M3", "Workflow" in sent and M3 not in text)
        d = h.state / "crew" / "workflows"
        d.mkdir(parents=True)
        (d / "ship.yaml").write_text("format: workflow/1\nname: ship\nfor: Ship a change.\nsteps:\n  - {name: do, agents: "
                                     "[coder], gets: the task, hands: the change}\n", encoding="utf-8")
        text2, sent2 = _shaped(s)
        ctx.check("a workflow of his and the Workflow tool sent: M3 ends the text",
                  "Workflow" in sent2 and text2.endswith("\n\n" + M3) and _frozen_part(text2) == _frozen_part(text))
        defs = [{"name": "Read"}, {"name": "Agent"}]
        ctx.check("a request that does not send the Workflow tool or the Builder: no tail", tail(s, defs) == "")
        both = tail(s, defs + [{"name": "Workflow"}, {"name": "Builder"}])
        ctx.check(f"both sent: M3 only (the Builder adds nothing), got {both!r}", both == "\n\n" + M3)
        ctx.check("the Builder alone: no tail", tail(s, defs + [{"name": "Builder"}]) == "")
        s2 = _session(h, control="auto")
        s2._helpers_off = True
        ctx.check("today's line: no tail either", tail(s2, defs + [{"name": "Workflow"}, {"name": "Builder"}]) == "")


# ---- 3.6.0.14 MW2: a LOCAL main on Auto is reminded at every task, after the permission mode line ------------------

LOCAL = "ol:qwen3:8b"
CLOUD = "ant:claude-opus-5-5"
M10 = ("If this job has parts that can run on their own, hand each one to a helper with the Agent tool before you work "
       "on it yourself (one call per part; `subagent_type` names the helper). A small job you do yourself.")
MODE_LINE = "permission mode: acceptEdits (edits in the working directory run without asking; commands ask first)"
PLAN_LINE = "permission mode: plan (read-only; call ExitPlanMode with the plan)"


class _Log:
    def __init__(self):
        self.snapshots = []

    def append_snapshot(self, content, *, kind):
        self.snapshots.append((kind, content[0]["text"]))


def _turn(s, mode: str = "acceptEdits", *, turn_start: bool = True, **kw):
    """The snapshot agent/loop.py logs at a turn's start (mode_notice.sync), on session `s` (a stub log, an engine)."""
    from halo_harness.agent import mode_notice
    from halo_harness.permissions import PermissionEngine
    if not isinstance(getattr(s, "log", None), _Log):
        s.log = _Log()
    if getattr(s, "permission_engine", None) is None:
        s.permission_engine = PermissionEngine(mode=mode, cwd=s.session_context.cwd)
    s.permission_engine.mode = mode
    return mode_notice.sync(s, turn_start=turn_start, **kw)


def _measured(h, ref: str, **kw) -> str:
    """The permission-mode snapshot a first request built by the measure's stub carries (prompt_measure._first_request,
    the gym's and the measure's)."""
    from halo_harness.agent.prompt_measure import _first_request
    kw.setdefault("control", "auto")
    _s, _f, _sys, messages, _sent = _first_request(ref, window=16384, platform="linux", cwd=h.repo,
                                                   mode="acceptEdits", text="tidy the notes", **kw)
    found = [b.get("text") for m in messages for b in (m.get("content") if isinstance(m.get("content"), list) else [])
             if isinstance(b, dict) and str(b.get("text", "")).startswith("permission mode:")]
    return found[0] if len(found) == 1 else f"<{len(found)} mode snapshots>"


@test
def test_a_local_main_on_auto_is_reminded_after_the_mode_line(ctx: Ctx):
    from halo_harness.agent import helpers_words
    with _Home() as h:
        ctx.check("M10, word for word", helpers_words.M10 == M10)
        got = _measured(h, LOCAL)
        ctx.check(f"the first request: the mode line, then the reminder on the next line, got {got!r}",
                  got == MODE_LINE + "\n" + M10)
        s = _session(h, ref=LOCAL)
        ctx.check("remind() gives the line", helpers_words.remind(s) == M10)
        ctx.check("the loop's turn snapshot is the measure's, byte for byte", _turn(s) == got)


@test
def test_a_cloud_main_and_every_other_session_read_todays_mode_line(ctx: Ctx):
    from halo_harness.agent import helpers_words
    from halo_harness.crew.session_start import start_control, tool_state
    with _Home() as h:
        maps = h.state / "crew" / "maps"
        maps.mkdir(parents=True)
        (maps / "mine.yaml").write_text("format: map/1\nname: mine\nboxes:\n- {id: coder, agent: coder}\nlines:\n"
                                        "- {from: main, to: coder}\n", encoding="utf-8")
        for label, kw in (("a cloud main", {"ref": CLOUD}), ("his map", {"ref": LOCAL, "control": "mine"}),
                          ("the block turned off (the gym's before)", {"ref": LOCAL, "helpers_off": True})):
            ref = kw.pop("ref")
            got = _measured(h, ref, **kw)
            ctx.check(f"{label}: the first request carries today's line, byte for byte, got {got!r}", got == MODE_LINE)
        cloud = _session(h, ref=CLOUD)
        ctx.check("a cloud main: no reminder", helpers_words.remind(cloud) == "")
        ctx.check("a cloud main's turn: today's line", _turn(cloud) == MODE_LINE)
        cases = []
        s = _session(h, ref=LOCAL)
        s.team_control = start_control(None, cwd=h.repo)  # an `--agent` session: no map
        tool_state(s, s.team_control)
        cases.append(("an --agent session", s))
        s = _session(h, ref=LOCAL)
        s._helpers_block = (s.model_ref.raw, None)  # the block was made and did not fit: frozen() is None
        cases.append(("a block that does not fit", s))
        s = _session(h, ref=LOCAL)
        s.agent_runtime.depth = 1
        cases.append(("a helper", s))
        s = _session(h, ref=LOCAL)
        s._helpers_off = True
        cases.append(("the block turned off", s))
        for label, s in cases:
            ctx.check(f"{label}: remind() is empty", helpers_words.remind(s) == "")
            ctx.check(f"{label}: the turn's snapshot is today's, byte for byte", _turn(s) == MODE_LINE)


@test
def test_every_turn_carries_the_same_reminder_and_only_at_a_turns_start(ctx: Ctx):
    from halo_harness.model import parse_model_ref
    with _Home() as h:
        s = _session(h, ref=LOCAL)
        first, second = _turn(s), _turn(s)
        ctx.check("two turns: the same bytes", first == second == MODE_LINE + "\n" + M10)
        # a turn that background results opened is no task: today's line, byte for byte (agent/loop.py passes it)
        ctx.check("a turn opened by background results: no reminder", _turn(s, task=False) == MODE_LINE)
        loop = (Path(__file__).resolve().parent.parent / "halo_harness" / "agent" / "loop.py").read_text(encoding="utf-8")
        ctx.check("the loop asks for the reminder only when the turn is a task of the person's",
                  loop.count("_mode_notice.sync(self, turn_start=True, task=not _bg)") == 1
                  and "_mode_notice.sync(self, turn_start=True)" not in loop)
        text = _turn(s, "plan", turn_start=False)  # plan mode entered in the middle of a turn: today's words
        ctx.check(f"a change mid-turn: the note and the mode line, no reminder, got {text!r}",
                  text is not None and text.endswith("\n\n" + PLAN_LINE) and M10 not in text)
        text = _turn(s)  # a turn that changes the mode: the note, the new mode line, the reminder after it
        ctx.check(f"a turn that leaves plan mode: the reminder follows the new mode line, got {text!r}",
                  text is not None and text.endswith("\n\n" + MODE_LINE + "\n" + M10) and text.count(M10) == 1)
        text = _turn(s, "plan")  # a turn that enters plan mode
        ctx.check(f"a turn that enters plan mode: the reminder after the plan mode line, got {text!r}",
                  text is not None and text.endswith("\n\n" + PLAN_LINE + "\n" + M10))
        _turn(s)  # out of plan mode again
        s.model_ref = parse_model_ref(CLOUD)  # main's model switches to a cloud one: the line goes
        ctx.check("after a switch to a cloud model: today's line", _turn(s) == MODE_LINE)
        s.model_ref = parse_model_ref(LOCAL)  # and back to a local one: it comes back
        ctx.check("after a switch back to a local model: the reminder again", _turn(s) == MODE_LINE + "\n" + M10)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
