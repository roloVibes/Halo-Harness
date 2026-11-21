"""tests.test_helpers_words -- 3.6.0.10 MW rules M4 and M6: what main is told about handing work out.

M4: on Auto (a top session on the default map, no restriction, the Agent tool, a model that takes tools) main's lean
system text trades today's one delegate line for a FROZEN block (agent/helpers_words.py: when to hand work out; the
kinds THIS session can start, his own first), made at the first shaping and kept byte-equal, made again only when
main's model changes (A1). On his map, with roles off, in an `--agent` session, restricted, as a sub-agent, or for a
model that takes no tools, today's line stays letter for letter.
M6: per request, after the tools are capped (agent/prompt_wire.py), a short TAIL names the Workflow tool (when that
request sends it and it lists his workflows) and the Builder (when that request sends it); the frozen part never
changes with it. Below 65,536 the Builder is not sent, so main reads no word of it but its name among the tools left
out; at 65,536 it is sent and the tail says so; a smaller ask that drops it drops the tail in that request only.
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
            msgs = [{"role": "user", "content": [{"type": "text", "text": "hi"}]}]
            text, _m, _sent = shape(s, sc.system_prompt, msgs, reg.definitions(), purpose="turn")
            if crew_map is not None:
                ctx.check(f"{label}: M1 and M2 in place of today's line",
                          (M1 + "\n" + M2_CLEAN) in text and TODAY_ON not in text)
            else:
                _todays(ctx, label, text)


def _frozen_part(text: str) -> str:
    """The system text up to its tail and by-name line (what must not change between requests)."""
    for mark in ("\n\n" + M3, "\n\n" + M4, "\n\n" + BY_NAME):
        if mark in text:
            text = text[:text.index(mark)]
    return text


@test
def test_below_65536_main_reads_no_word_of_the_builder(ctx: Ctx):
    with _Home() as h:
        for platform in ("win32", "linux"):
            for window in (16384, 32768, 49152):
                s = _session(h, window=window, platform=platform, builder=True)
                text, sent = _shaped(s)
                ctx.check(f"{platform} {window:,}: the Builder is not sent", "Builder" not in sent)
                ctx.check(f"{platform} {window:,}: no M4, and \"Builder\" only among the tools left out",
                          M4 not in text and "Builder" not in _frozen_part(text) and M2_HEAD in text)


@test
def test_at_65536_the_tail_names_the_builder_and_a_smaller_ask_drops_it_there_only(ctx: Ctx):
    with _Home() as h:
        for platform in ("win32", "linux"):
            s = _session(h, window=65536, platform=platform, builder=True)
            text, sent = _shaped(s)
            after = text.split("\n\n" + M4, 1)[1] if ("\n\n" + M4) in text else None
            ctx.check(f"{platform}: the Builder is sent at 65,536 and the tail names it, last but the by-name line",
                      "Builder" in sent and after is not None and (after == "" or after.startswith("\n\n" + BY_NAME)))
            s._ladder_pass = {"small": True, "turn": getattr(s, "turn_count", None)}  # agent/degrade.py's smaller ask
            small, sent_small = _shaped(s)
            ctx.check(f"{platform}: a smaller ask sends no Builder and no tail",
                      "Builder" not in sent_small and M4 not in small)
            s._ladder_pass = None
            back, _sent = _shaped(s)
            ctx.check(f"{platform}: the next request sends it again, the tail with it", back == text)
            ctx.check(f"{platform}: the frozen part is byte-equal throughout",
                      _frozen_part(text) == _frozen_part(small) == _frozen_part(back) and M1 in _frozen_part(text))


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
        ctx.check(f"both sent: M3 then M4, got {both!r}", both == "\n\n" + M3 + "\n" + M4)
        s2 = _session(h, control="auto")
        s2._helpers_off = True
        ctx.check("today's line: no tail either", tail(s2, defs + [{"name": "Workflow"}, {"name": "Builder"}]) == "")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
