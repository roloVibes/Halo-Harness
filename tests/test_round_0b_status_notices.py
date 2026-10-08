"""tests.test_round_0b_status_notices -- Halo 2.0.7 round 0b: pending
background job / sub-agent completion notices stop impersonating the user.

Pre-0b, `_apply_pending_agent_notices`/`_apply_pending_job_notices` logged
each notice as a `user` node and yielded a `user_message` event -- the model
read a status blob interleaved with the owner's actual question (same user
turn) and answered the status first (rolo, 2026-10-08: "typing a question,
getting a blob back of what's been done, then an answer is not a good
flow"). The 0b contract, pinned here:

  * the log node is a `snapshot` with kind `status_notice` (never a user
    node), appended AFTER the human's own prompt node (log order);
  * `derive_request` folds its framed block into the SAME pending user
    turn, BEHIND the human's words, and the frame says the block is
    automated status, NOT a message from the human, and to answer the
    human first;
  * the event is a `status_notice` event (plain text + framed copy) --
    never `user_message` -- so the TUI renders a note, not a user bubble;
  * print mode ignores it exactly as it ignored the old user_message
    (its surface was always the `notification` toast, unchanged);
  * `/stats` never counts it as a turn (it is not a user node at all).
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.mock_openai import MockUpstream, SCENARIOS, ScriptedTurns
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials

ensure_default_provider_credentials()

test, TESTS = new_registry()

_FRAME_NEEDLES = (
    "NOT a message from the human",
    "Answer the human's own message first",
    "<status-notices",
    "</status-notices>",
)


def _text_step(text: str) -> list:
    return [
        {"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
        {"choices": [{"index": 0, "delta": {"content": text}}]},
        {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
    ]


def _new_session(*, mock, model):
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.loop import Session
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.permissions import PermissionEngine
    from halo_harness.providers.stream import ProviderCreds

    cwd = Path(tempfile.mkdtemp(prefix="r0b-e2e-"))
    os.environ["BRIDGE_TEST_HOME"] = str(Path(tempfile.mkdtemp(prefix="r0b-home-")))
    session_ctx = SessionContext(cwd=cwd, model_label=model, bare=True)
    return Session(
        cwd=cwd, model_ref=parse_model_ref(model), model_profile=ModelProfile(),
        creds=ProviderCreds(base_url=mock.base_url, api_key="k"),
        state_dir=Path(tempfile.mkdtemp(prefix="r0b-state-")), model_label=model,
        session_context=session_ctx, openrouter_base_url=mock.base_url, max_turns=10,
        permission_engine=PermissionEngine(mode="auto", cwd=cwd),
        agents={}, routes={},
    )


@test
def test_frame_shape_wraps_body_verbatim(ctx: Ctx):
    from halo_harness.agent.loop import _status_notice_block
    body = "[Background job bash_x (echo hi) finished, exit code 0]\nhi"
    framed = _status_notice_block(body)
    for needle in _FRAME_NEEDLES:
        ctx.check(f"frame carries {needle!r}", needle in framed)
    ctx.check("body rides verbatim inside the frame", body in framed)
    ctx.check("frame opens before the body",
              framed.index("<status-notices") < framed.index("bash_x"))
    ctx.check("frame closes after the body",
              framed.index("bash_x") < framed.index("</status-notices>"))


@test
def test_notice_rides_after_the_human_message_in_the_derived_request(ctx: Ctx):
    """The core 0b acceptance: with notices pending, a real turn's derived
    request carries the human's question FIRST and the framed status block
    SECOND, inside the same user turn -- and nothing user-shaped that could
    be read as the owner's own words."""
    from halo_harness.agent.derive import derive_request

    SCENARIOS["r0b-derive"] = ScriptedTurns([_text_step("the answer")])
    mock = MockUpstream().start()
    try:
        session = _new_session(mock=mock, model="or:mock/r0b-derive")
        session._pending_job_notices.append("[Background job bash_q (echo hi) finished, exit code 0]\nhi")
        session._pending_agent_notices.append("[Background sub-agent 'w' finished (task_id=t9)]\nthe result")
        events_seen = list(session.turn("what is the answer?"))
        ctx.check("no user_message event ever carries notice text",
                  not [e for e in events_seen if e.kind == "user_message"
                       and ("bash_q" in e.data.get("text", "") or "task_id=t9" in e.data.get("text", ""))])
        status_evs = [e for e in events_seen if e.kind == "status_notice"]
        ctx.check("both pending notices delivered as status_notice events", len(status_evs) == 2)

        _, messages, _ = derive_request(session.log)
        last_user = [m for m in messages if m.get("role") == "user"][-1]
        texts = [b.get("text", "") for b in last_user["content"] if b.get("type") == "text"]
        q_idx = texts.index("what is the answer?") if "what is the answer?" in texts else -1
        ctx.check("the human's question is present as its own text block", q_idx >= 0)
        frame_idx = [i for i, t in enumerate(texts) if "<status-notices" in t]
        ctx.check("the framed notice blocks are present", len(frame_idx) == 2)
        ctx.check("every frame block sits AFTER the human's question",
                  all(i > q_idx for i in frame_idx))
        joined = "\n".join(texts[q_idx:])
        for needle in _FRAME_NEEDLES:
            ctx.check(f"derived request carries {needle!r}", needle in joined)
        ctx.check("the job notice body reached the model inside the frame", "bash_q" in joined)
        ctx.check("the agent notice body reached the model inside the frame", "task_id=t9" in joined)

        ctx.check("no user node carries an agent/job notice kind anymore",
                  not [n for n in session.log.nodes()
                       if n.get("type") == "user" and n.get("kind") in ("agent_notice", "job_notice")])
        ctx.check("log order: human prompt node precedes every status_notice snapshot",
                  all(n.get("seq") < min(s.get("seq") for s in session.log.nodes()
                                         if s.get("type") == "snapshot" and s.get("kind") == "status_notice")
                      for n in session.log.nodes() if n.get("type") == "user" and n.get("kind") is None))
        ctx.check("queues drained", session._pending_job_notices == [] and session._pending_agent_notices == [])
    finally:
        mock.stop()


@test
def test_tui_renders_status_notice_as_a_note_never_a_user_bubble(ctx: Ctx):
    import asyncio
    from halo_harness import events
    from halo_harness.tui.dispatch import _apply_event_inner

    calls = []

    class _FakeTranscript:
        async def add_user(self, text):
            calls.append(("user", text))
        async def add_note(self, text, *, kind="note"):
            calls.append(("note", text, kind))

    class _FakeApp:
        def __init__(self):
            self.transcript = _FakeTranscript()

    ev = events.status_notice("[Background job bash_z finished]\nout", framed="<status-notices>x</status-notices>")
    asyncio.run(_apply_event_inner(_FakeApp(), ev))
    ctx.check("rendered exactly once", len(calls) == 1)
    ctx.check("as a transcript NOTE, not a user bubble", calls[0][0] == "note")
    ctx.check("with the status note kind", calls[0][2] == "status")
    ctx.check("the note shows the plain notice text", "bash_z" in calls[0][1])


@test
def test_print_mode_sink_output_identical_with_and_without_notices(ctx: Ctx):
    """Print mode's contract (roadmap: "print mode keeps its current
    behavior"): the old user_message notice event printed NOTHING (the
    TextSink has no user_message branch), so the new status_notice event
    must print nothing either -- the notification toast remains the only
    print-mode surface, exactly as before."""
    import io
    from halo_harness import events
    from halo_harness.output import PrintModeSink

    def _capture(evs):
        buf = io.StringIO()
        sink = PrintModeSink(stream=buf, output_format="text")
        for e in evs:
            sink._handle(e)
        sink.finish()
        return buf.getvalue()

    base = [events.message_start(turn=1), events.text_delta("hi", turn=1),
            events.message_end(turn=1), events.turn_done(turn=1),
            events.notification("Background job finished: bash_q")]
    with_notice = base[:4] + [events.status_notice("[Background job bash_q finished]\nout"),
                              events.notification("Background job finished: bash_q")]
    a, b = _capture(base), _capture(with_notice)
    ctx.check("the status_notice event adds no print-mode output", a == b)
    ctx.check("sanity: the streams are not empty", "hi" in a)


@test
def test_stats_never_counts_a_status_notice_as_a_turn(ctx: Ctx):
    from halo_harness.controller import compute_session_stats

    SCENARIOS["r0b-stats"] = ScriptedTurns([_text_step("ok")])
    mock = MockUpstream().start()
    try:
        session = _new_session(mock=mock, model="or:mock/r0b-stats")
        session._pending_job_notices.append("[Background job bash_s (true) finished, exit code 0]\ndone")
        list(session.turn("one real question"))
        stats = compute_session_stats(session.log.nodes())
        ctx.check(f"exactly one turn counted, got {stats['turns']}", stats["turns"] == 1)
    finally:
        mock.stop()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
