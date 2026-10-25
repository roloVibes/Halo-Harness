"""tests.test_turn_marker -- Halo 3.2.2.0 R4: every finished turn ends with
one `turn_marker` line (`◼ done · 42 s · 3 tools · $0.012`, `◼ waiting on
you: <what>`, `◼ stopped: <why>`), a card the turn waits on gets a
`waiting` marker as it is shown, the TUI shows the line muted (never a
child's, never a card's mid-turn one), and Studio's Session feed carries it.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.turn_session import Calls, markers, new_session, text_step, tool_step

test, TESTS = new_registry()
ROOT = Path(__file__).resolve().parent.parent


class _Meter:
    def __init__(self, total=None):
        self.total_usd = total
        self.has_cost_data = total is not None


def _fake_session(**kw):
    s = SimpleNamespace(cost_meter=_Meter(kw.pop("cost", None)), max_turns=kw.pop("max_turns", 6))
    from halo_harness.agent import turn_marker as tm
    tm.reset_turn_state(s)
    for k, v in kw.items():
        setattr(s, k, v)
    return s


def _ev(kind, data=None, agent_id=None, turn=1):
    from halo_harness.events import Event
    return Event(kind, data or {}, turn=turn, agent_id=agent_id)


@test
def test_each_reason_has_its_line(ctx: Ctx):
    from halo_harness.agent.turn_marker import TurnTracker
    s = _fake_session(cost=0.010)
    t = TurnTracker(s)
    for _ in range(3):
        t.see(_ev("tool_use_ready", {"name": "Read"}))
    t.see(_ev("tool_use_ready", {"name": "Bash"}, agent_id="child"))  # a child's tool never counts
    s.cost_meter.total_usd = 0.022
    t.t0 -= 42
    done = t.end_marker("end_turn", turn=1)
    ctx.check(f"done line, got {done.data['text']!r}", done.data["text"] == "◼ done · 42 s · 3 tools · $0.012")
    ctx.check("state done", done.data["state"] == "done")
    cases = {
        "max_tokens": "◼ stopped: the reply hit its output limit (max_tokens)",
        "max_turns": "◼ stopped: the turn used its 6 model calls (--max-turns)",
        "interrupted": "◼ stopped: interrupted (Esc)",
    }
    for reason, want in cases.items():
        got = t.end_marker(reason, turn=1).data
        ctx.check(f"{reason} -> {want!r}, got {got['text']!r}", got["text"] == want and got["state"] == "stopped")
    t.see(_ev("error", {"message": "HTTP 502 from the provider\nmore detail"}))
    got = t.end_marker("error", turn=1).data["text"]
    ctx.check(f"an error names the provider error in one line, got {got!r}",
              got == "◼ stopped: HTTP 502 from the provider")
    s._turn_stop_why = "a UserPromptSubmit hook (no prompts after 6 pm)"
    got = t.end_marker("blocked", turn=1).data["text"]
    ctx.check(f"blocked names the hook, got {got!r}", got.startswith("◼ stopped: blocked by a UserPromptSubmit hook"))
    s._turn_stop_why = "the loop breaker ended the turn (Read repeated)"
    got = t.end_marker("end_turn", turn=1).data["text"]
    ctx.check(f"a loop-breaker end is a stop, got {got!r}", got == "◼ stopped: the loop breaker ended the turn (Read repeated)")


@test
def test_done_line_without_tools_or_cost(ctx: Ctx):
    from halo_harness.agent.turn_marker import TurnTracker, format_elapsed
    t = TurnTracker(_fake_session())
    got = t.end_marker("end_turn", turn=1).data["text"]
    ctx.check(f"no tools, no cost data -> just the time, got {got!r}", got == "◼ done · 0 s")
    ctx.check("minutes read as m and s", format_elapsed(125) == "2 m 05 s")


@test
def test_waiting_on_you_for_a_question_or_the_plan(ctx: Ctx):
    from halo_harness.agent.turn_marker import TurnTracker
    s = _fake_session()
    t = TurnTracker(s)
    t.see(_ev("message_start"))
    t.see(_ev("text_delta", {"text": "I found two configs.\nWhich one should I keep?"}))
    t.see(_ev("message_end"))
    got = t.end_marker("end_turn", turn=1).data
    ctx.check(f"a reply ending in a question waits on you, got {got['text']!r}",
              got["state"] == "waiting" and got["text"] == '◼ waiting on you: the question "Which one should I keep?"')
    s._turn_waiting_on = "the plan (written to /p/plan.md)"
    got = t.end_marker("end_turn", turn=1).data["text"]
    ctx.check(f"the print-mode plan waits on you, got {got!r}", got == "◼ waiting on you: the plan (written to /p/plan.md)")


@test
def test_cards_get_a_mid_turn_waiting_marker(ctx: Ctx):
    from halo_harness.agent.turn_marker import TurnTracker
    t = TurnTracker(_fake_session())
    perm = t.waiting_marker(_ev("permission_request", {"name": "Bash"})).data
    ctx.check(f"permission card, got {perm}", perm["text"] == "◼ waiting on you: permission for Bash" and perm["mid_turn"])
    q = t.waiting_marker(_ev("question", {"input": {"questions": [{"question": "Ship it?"}]}})).data
    ctx.check(f"question card, got {q['text']!r}", q["text"] == '◼ waiting on you: the question "Ship it?"')
    plan = t.waiting_marker(_ev("plan_review", {"plan": "x"})).data
    ctx.check(f"plan card, got {plan['text']!r}", plan["text"].startswith("◼ waiting on you: the plan"))


@test
def test_with_markers_places_the_line_before_turn_done(ctx: Ctx):
    from halo_harness.agent.turn_marker import with_markers
    evs = [_ev("message_start"), _ev("permission_request", {"name": "Write"}), _ev("turn_done", {"reason": "end_turn"}),
           _ev("turn_done", {"reason": "end_turn"}, agent_id="kid")]
    out = list(with_markers(_fake_session(), iter(evs), 1))
    kinds = [e.kind for e in out]
    ctx.check(f"card then its marker, the end marker right before turn_done; got {kinds}",
              kinds == ["message_start", "permission_request", "turn_marker", "turn_marker", "turn_done", "turn_done"])
    ctx.check("the end marker is the done line", out[3].data["state"] == "done" and not out[3].data.get("mid_turn"))


@test
def test_a_real_turn_ends_with_the_done_marker(ctx: Ctx):
    from tests.helpers.mock_openai import MockUpstream, SCENARIOS
    mock = MockUpstream().start()
    try:
        SCENARIOS["r4-marker-tools"] = Calls([tool_step("Glob", {"pattern": "*.md"}), text_step("Found none. Nothing is next.")])
        session = new_session(mock=mock, model="or:mock/r4-marker-tools")
        evs = list(session.turn("list the docs"))
        ms = markers(evs)
        ctx.check(f"one marker, got {[m.data for m in ms]}", len(ms) == 1)
        ctx.check(f"it says done with one tool, got {ms[0].data['text']!r}",
                  ms[0].data["text"].startswith("◼ done · ") and "1 tool" in ms[0].data["text"])
        ctx.check("it comes right before turn_done", [e.kind for e in evs][-2:] == ["turn_marker", "turn_done"])
    finally:
        mock.stop()


class _Transcript:
    def __init__(self):
        self.notes = []

    async def add_note(self, text, *, kind="note"):
        self.notes.append((text, kind))


@test
def test_tui_shows_the_marker_muted_and_skips_card_and_child_markers(ctx: Ctx):
    from halo_harness.events import turn_marker
    from halo_harness.tui.dispatch import apply_event
    app = SimpleNamespace(transcript=_Transcript(), notify=lambda *a, **k: None)
    asyncio.run(apply_event(app, turn_marker("done", "◼ done · 3 s", turn=1)))
    asyncio.run(apply_event(app, turn_marker("waiting", "◼ waiting on you: permission for Bash", turn=1, mid_turn=True)))
    child = turn_marker("done", "◼ done · 1 s", turn=1)
    child.agent_id = "kid"
    asyncio.run(apply_event(app, child))
    ctx.check(f"only the main end marker, kind marker; got {app.transcript.notes}",
              app.transcript.notes == [("◼ done · 3 s", "marker")])
    css = (ROOT / "halo_harness" / "tui" / "styles.tcss").read_text(encoding="utf-8")
    ctx.check("the marker style is muted", ".system-note-marker {\n    color: $bridge-muted;" in css)


@test
def test_studio_session_feed_carries_the_marker(ctx: Ctx):
    from halo_harness.events import turn_marker
    from halo_harness.remote.feed import event_frame
    from halo_harness.studio.feed_kinds import DEFAULT_KINDS
    ctx.check("Studio asks every session for turn_marker frames", "turn_marker" in DEFAULT_KINDS)
    frame = event_frame(turn_marker("stopped", "◼ stopped: interrupted (Esc)", turn=2))
    ctx.check(f"the frame carries the text, got {frame}",
              frame["event"] == "turn_marker" and frame["data"]["text"] == "◼ stopped: interrupted (Esc)")
    ui = ROOT / "halo_harness" / "studio" / "ui" / "src"
    known = (ui / "lib" / "events.ts").read_text(encoding="utf-8")
    ctx.check("the UI binds turn_marker (KNOWN_KINDS)", '"turn_marker"' in known)
    feed = (ui / "routes" / "shared" / "liveFeed.ts").read_text(encoding="utf-8")
    ctx.check("the Session live feed turns it into a state line",
              'onEvent("turn_marker", onMarker)' in feed and 'kind: "state"' in feed.split("function onMarker", 1)[1])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
