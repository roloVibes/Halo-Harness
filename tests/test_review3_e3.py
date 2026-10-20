"""tests.test_review3_e3 -- 3.0.2.0 review fix pass, round E (session data),
part 3: /resume and Ctrl+P switching the live session.

  * review item 13  the switch ran under a running turn (the turn's later
                    appends landed in the other session's file)
  * review item 72  the switch was incomplete (hook ids, spill
                    dir, counters, cost meter, title counter stayed behind);
                    the reopened log also had an EMPTY in-memory node list
"""
from __future__ import annotations

import json
import os
import queue
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.fake_home import build_fake_home
from tests.helpers.mock_openai import MockUpstream
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials

ensure_default_provider_credentials()

test, TESTS = new_registry()

_SAVED_HOME = os.environ.get("BRIDGE_TEST_HOME")


def _restore_home() -> None:
    if _SAVED_HOME is None:
        os.environ.pop("BRIDGE_TEST_HOME", None)
    else:
        os.environ["BRIDGE_TEST_HOME"] = _SAVED_HOME


def _setup():
    """A live session on a fresh scoped home, plus an OLDER saved session
    (meta, system, one user prompt, one reply) to resume."""
    from halo_harness.agent.log import SessionLog
    from halo_harness.hooks import HookRunner
    from tests.test_agent_tool import _make_session
    fh = build_fake_home()
    os.environ["BRIDGE_TEST_HOME"] = str(fh["home"])
    mock = MockUpstream().start()
    session = _make_session(fh, scenario="r3e3-unused", mock=mock)
    session.hook_runner = HookRunner({}, cwd=fh["proj"], session_id=session.log.session_id,
                                     transcript_path=str(session.log.path))
    older = SessionLog(fh["proj"])
    older.append_meta(model="or:mock/older", cwd=str(fh["proj"]))
    older.append_system("older system prompt")
    older.append_user([{"type": "text", "text": "the older prompt"}])
    older.append_assistant(content=[{"type": "text", "text": "the older reply"}])
    return fh, mock, session, older.session_id, older.path


def _drive(session, commands_in: list) -> list:
    commands, seen = queue.Queue(), []
    for c in commands_in + [None]:
        commands.put(c)
    session.run(commands, seen.append)
    return seen


@test
def test_i13_resume_while_a_turn_runs_is_refused_and_switches_nothing(ctx: Ctx):
    from halo_harness.controller import Controller
    fh, mock, session, older_id, _ = _setup()
    try:
        ctl = Controller(session=session, cwd=fh["proj"])
        before = session.log
        session._busy.set()
        try:
            msg = ctl.resume(older_id)
        finally:
            session._busy.clear()
        ctx.check(f"a reason comes back, got {msg!r}", "turn is running" in (msg or ""))
        ctx.check("session.log is untouched", session.log is before)
        ctx.check("nothing was queued for the worker", ctl.commands.empty())
    finally:
        mock.stop()
        _restore_home()


@test
def test_i13_i72_resume_switches_every_session_handle_between_turns(ctx: Ctx):
    from halo_harness.events import Command
    fh, mock, session, older_id, older_path = _setup()
    try:
        fired, loaded = [], []
        session._fire_session_end = lambda reason: fired.append(("end", reason, session.log.session_id))
        session._fire_session_start = lambda source: fired.append(("start", source, session.log.session_id))
        session.turn_count = 7
        session._last_prompt_tokens = 12345
        session._just_compacted = True
        old_meter, old_id = session.cost_meter, session.log.session_id
        seen = _drive(session, [Command("run_resume", {"session_id": older_id, "on_switched": loaded.append})])
        log = session.log
        ctx.check(f"the session now writes {older_id}, got {log.session_id}", log.session_id == older_id)
        ctx.check("the resumed log's nodes were READ (not an empty mirror)",
                  [n.get("type") for n in log.nodes()][:4] == ["meta", "system", "user", "assistant"])
        ctx.check("the controller callback got the loaded log", loaded == [log])
        ctx.check(f"SessionEnd on the old id, SessionStart(resume) on the new, got {fired}",
                  fired == [("end", "resume", old_id), ("start", "resume", older_id)])
        ctx.check("hook runner follows the new session",
                  session.hook_runner.session_id == older_id and session.hook_runner.transcript_path == str(older_path))
        ctx.check("tool-results spill dir follows the new session",
                  session.permission_engine.tool_results_dir == log.dir / older_id / "tool-results")
        ctx.check("turn counter, prompt-token estimate and compaction flag reset",
                  session.turn_count == 0 and session._last_prompt_tokens is None and not session._just_compacted)
        ctx.check("a fresh cost meter with the same prices", session.cost_meter is not old_meter
                  and session.cost_meter.price_in == old_meter.price_in
                  and session.cost_meter.price_cache_read == old_meter.price_cache_read)
        ctx.check("a status event with the new id followed",
                  any(e.kind == "status" and (e.data or {}).get("session_id") == older_id for e in seen))
        ctx.check("the session is idle again", not session.busy)
        session.log.append_assistant(content=[{"type": "text", "text": "a later reply"}])
        last = json.loads(older_path.read_text(encoding="utf-8").strip().split("\n")[-1])
        ctx.check("a later append lands in the resumed file", last.get("content", [{}])[0].get("text") == "a later reply")
    finally:
        mock.stop()
        _restore_home()


@test
def test_i72_unknown_session_id_leaves_the_current_session(ctx: Ctx):
    from halo_harness.events import Command
    fh, mock, session, _older_id, _ = _setup()
    try:
        before = session.log
        seen = _drive(session, [Command("run_resume", {"session_id": "0" * 32})])
        ctx.check("still on the current log", session.log is before)
        ctx.check("a notification says so", any(e.kind == "notification" for e in seen))
    finally:
        mock.stop()
        _restore_home()


@test
def test_i13_controller_resume_replays_the_resumed_session_once_switched(ctx: Ctx):
    from halo_harness.controller import Controller
    fh, mock, session, older_id, _ = _setup()
    try:
        ctl = Controller(session=session, cwd=fh["proj"]).start()
        ctx.check("resume is accepted while idle", ctl.resume(older_id) == "")
        replay = None
        while replay is None:
            ev = ctl.events.get(timeout=10)
            if ev is not None and ev.kind == "replay":
                replay = ev
        ctx.check(f"the replay carries the resumed conversation, got {replay.data}",
                  replay.data.get("switched") is True
                  and [m["text"] for m in replay.data["messages"]] == ["the older prompt", "the older reply"])
        ctx.check("the live session switched", session.log.session_id == older_id)
        ctl.commands.put(None)
        ctl._worker.join(timeout=10)
    finally:
        mock.stop()
        _restore_home()


@test
def test_i13_i72_tui_pick_notifies_on_refusal_and_resets_the_title_counter(ctx: Ctx):
    from halo_harness.tui.slash import resume_from_ui
    notes = []
    app = SimpleNamespace(_turn_done_count=3, notify=lambda text, **kw: notes.append(text),
                          controller=SimpleNamespace(resume=lambda sid: "A turn is running -- wait"))
    resume_from_ui(app, "abc")
    ctx.check("a refusal is shown as a notification", notes == ["A turn is running -- wait"])
    ctx.check("the title counter is untouched on a refusal", app._turn_done_count == 3)
    app.controller = SimpleNamespace(resume=lambda sid: "")
    resume_from_ui(app, "abc")
    ctx.check("a queued switch restarts the first-turn counter (auto-title)", app._turn_done_count == 0)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
