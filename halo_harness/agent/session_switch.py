"""halo_harness.agent.session_switch -- `/resume` and Ctrl+P: continue a
DIFFERENT existing session inside the running `Session` object.

Two rules, both from the 3.0.1.0 review:

  * NEVER UNDER A RUNNING TURN. `Controller.resume` refuses while the
    session is busy, and the switch itself runs on the session's own worker
    thread (the `run_resume` command), so it is strictly ordered with turns:
    no later append of a running turn can land in the other session's file,
    and no request is ever derived from a half-swapped log. The whole-log
    read happens there too, off the UI thread.
  * A COMPLETE SWITCH. Everything `Session.clear()` treats as session-keyed
    follows the new log: the live `cc:` claude process and the `cx:` state
    (both hold the OLD conversation), the hook runner's session id and
    transcript path (hook payloads and CLAUDE_ENV_FILE), the permission
    engine's tool-results spill dir, the turn counter, timeline, prompt-token
    estimate, compaction flags, prune state and cost meter. SessionEnd fires
    on the old session and SessionStart(resume) on the new one.
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

from halo_harness import events

log = logging.getLogger(__name__)


def load_log(cwd, session_id: str):
    """The `SessionLog` for `session_id` with its nodes read from disk
    (a bare `SessionLog(cwd, session_id=...)` starts with an EMPTY in-memory
    mirror, which is what `derive_request` reads)."""
    from halo_harness.agent.log import SessionLog

    new_log = SessionLog(cwd, session_id=session_id)
    new_log._nodes = new_log.read_all()
    return new_log


def switch_log(session, new_log) -> None:
    """Point `session` at `new_log` (already loaded) and reset every
    per-session handle. Never call while a turn runs (see the module
    docstring); `pump_resume` is the one caller."""
    from halo_harness.agent import cc_runtime, codex_runtime
    from halo_harness.agent.invariants import synthesize_missing_results
    from halo_harness.model import CostMeter

    if getattr(session, "_cc_state", None) is not None:
        cc_runtime.close_cc(session)
        session._cc_state = None
    session._cc_fork_session = False
    if getattr(session, "_cx_state", None) is not None:
        codex_runtime.close_cx(session)
    session._fire_session_end("resume")
    session._reset_prune_state()
    session.log = new_log
    if session.hook_runner is not None:
        session.hook_runner.session_id = new_log.session_id
        session.hook_runner.transcript_path = str(new_log.path)
    if session.permission_engine is not None:
        session.permission_engine.tool_results_dir = new_log.dir / new_log.session_id / "tool-results"
    session.turn_count = 0
    session._timeline.reset()
    session._last_prompt_tokens = None
    session._just_compacted = False
    session._compaction_backoff_remaining = 0
    cm = session.cost_meter
    session.cost_meter = CostMeter(price_in=cm.price_in, price_out=cm.price_out,
                                   price_cache_read=cm.price_cache_read, price_cache_write=cm.price_cache_write)
    session.permission_denials = []
    # same repairs a fresh process applies when it resumes a log: pair any
    # dangling tool_use, and rebuild the prune-commit set from the log
    if new_log.nodes():
        synthesize_missing_results(new_log, reason="ABORTED_BEFORE_DISPATCH")
    for node in new_log.nodes():
        if node.get("type") == "prune_commit" and isinstance(node.get("stub_ids"), list):
            session._prune_committed_stub_ids |= {i for i in node["stub_ids"] if isinstance(i, str)}
    session._fire_session_start("resume")


def pump_resume(session, data: dict, out) -> None:
    """The worker-thread side of `run_resume`: hold the session busy (input
    typed meanwhile becomes a steer, resubmitted afterwards, as for /clear),
    read the target log, switch, hand the loaded log to the controller's
    `on_switched` callback (it emits the replay), then a fresh status."""
    on_switched: Optional[Callable] = data.get("on_switched")
    session.abort.clear()
    session._busy.set()
    try:
        new_log = load_log(session.cwd, str(data.get("session_id") or ""))
        if not new_log.nodes():  # nothing saved under that id: stay on the current session
            out(events.notification(f"/resume: no saved session {new_log.session_id}", level="warning"))
            return
        switch_log(session, new_log)
        if callable(on_switched):
            on_switched(new_log)
        out(session.status_event(phase="idle"))
    except BaseException as e:  # never let the worker thread die silently
        log.exception("/resume failed")
        out(events.notification(f"/resume failed: {type(e).__name__}: {e}", level="error"))
    finally:
        session._end_busy_period()
