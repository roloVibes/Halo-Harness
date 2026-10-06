"""halo_harness.agent.cc_control -- Halo 2.0.5 round 1: the `cc:` route's
stream-json CONTROL CHANNEL (`control_request`/`control_response`), kept
separate from `agent/cc_runtime.py` (already past this project's house
size conventions) per the round's own brief: "nothing new lands in
cc_runtime.py beyond the calls into it".

Wire shapes (live-verified against the installed claude 2.1.291,
`docs/harness/CC-CONTROL-CHANNEL.md` has the full transcripts):

    control_request  (halo -> claude):
        {"type": "control_request", "request_id": "<str>",
         "request": {"subtype": "<name>", ...payload}}
    control_response (claude -> halo):
        {"type": "control_response",
         "response": {"subtype": "success", "request_id": "<str>", "response": {...}}}
      or, for an unsupported/invalid request:
        {"type": "control_response",
         "response": {"subtype": "error", "request_id": "<str>", "error": "<message>"}}

Two ways a `control_response` can be waited for, chosen automatically by
`request_control` from `state.active_queue`:

  * MID-TURN: `agent/cc_runtime.py`'s own per-turn reader thread is the
    ONLY thing allowed to call `state.process.read_event()` while a turn
    is running (every other reader would race it on the same stdout
    stream). `request_control` registers a waiter in `state.
    control_waiters` keyed by `request_id` BEFORE sending, then blocks on
    a `threading.Event` with a real, enforced timeout; that reader's own
    `reader()` function calls `dispatch_control_response` the moment it
    sees the matching line (never queued/logged as a transcript item),
    waking the waiter.
  * IDLE (between turns -- today, only `switch_model_live`'s own
    `set_model` request): a background thread does the one, unavoidably
    blocking `read_event()` call (no portable read-with-timeout for a
    Windows pipe); THIS thread waits on a bounded `queue.get(timeout=)`
    instead, so an old claude (or the hermetic fake's own
    `FAKE_CLAUDE_CC_CONTROL=0`) that never answers at all cannot hang
    the caller. On a real timeout that background thread is simply
    ABANDONED -- safe only because `switch_model_live` always closes/
    kills this EXACT process the instant it gets None back, so the
    abandoned thread's blocked read unblocks (EOF) the moment that kill
    happens; see `_read_idle_until_response`'s own docstring. A NEW idle
    caller that cannot make that same "always closes on failure"
    guarantee must not reuse this path.

Detection ("ONCE per process", the brief's own words): `state.
control_channel_supported` is set True the moment ANY `system.init` line
carries a `capabilities` key at all (even an empty list -- live-verified
the installed version's own list: `interrupt_receipt_v1`,
`interrupt_cancel_queued_v1`, `interrupt_send_now_v1`, `msg_lifecycle_v1`,
`sdk_mcp_tools_list_changed`, `sdk_mcp_manifests`, `mcp_read_resource_v1`,
`mcp_tool_ui_meta_v1`, `ui_surface_v1`), captured by `cc_runtime.
_events_for_stdout_obj`. Failing that, the first REAL control_request a
caller sends settles it one way or the other: ANY `control_response` at
all (success, or a well-formed "Unsupported control request subtype: "
error -- also live-verified, see `_is_unsupported_subtype_error`) proves
the channel itself exists; only a timeout/EOF (no response whatsoever)
means it might not. `control_subtype_supported` is the finer-grained,
per-subtype cache callers actually read before trying again."""

from __future__ import annotations

import queue
import threading
import uuid
from typing import Optional

from halo_harness import events

_DEFAULT_TIMEOUT_S = 5.0


def _new_request_id() -> str:
    return f"halo_{uuid.uuid4().hex[:16]}"


def _is_unsupported_subtype_error(response: dict) -> bool:
    """Live-verified exact wording: `claude -p ...` answered a bogus
    `{"subtype": "frobnicate_xyz"}` with `{"subtype": "error",
    "error": "Unsupported control request subtype: frobnicate_xyz"}` --
    matched by PREFIX (never the whole message, which names the bogus
    subtype) so this stays correct if the installed version ever
    rephrases the REST of the sentence."""
    if not isinstance(response, dict) or response.get("subtype") != "error":
        return False
    return str(response.get("error") or "").lower().startswith("unsupported control request subtype")


def channel_supported(state) -> Optional[bool]:
    """True/False once known for this `claude` subprocess, else None
    (never yet decided either way -- the first `system.init` carried no
    `capabilities` key AND no control_request has been tried yet)."""
    return state.control_channel_supported


def subtype_known_unsupported(state, subtype: str) -> bool:
    """True only when a REAL round trip on THIS process already proved
    `subtype` unsupported (or the whole channel is known unsupported) --
    the one case a caller should skip straight to its v1 fallback. Both
    "unknown, never tried" and "known supported" return False, so the
    caller's own `request_control` call is what actually finds out."""
    if state.control_channel_supported is False:
        return True
    return state.control_subtype_supported.get(subtype) is False


def _mark_channel_result(state, subtype: str, response: Optional[dict]) -> None:
    with state.lock:
        if response is None:
            if state.control_channel_supported is None:
                state.control_channel_supported = False
            state.control_subtype_supported[subtype] = False
            return
        state.control_channel_supported = True
        state.control_subtype_supported[subtype] = not _is_unsupported_subtype_error(response)


def dispatch_control_response(state, obj: dict) -> None:
    """Called from `cc_runtime.py`'s per-turn reader the moment it sees a
    `{"type": "control_response", ...}` line -- wakes the matching
    `request_control` waiter, if one is still registered (a response
    that arrives after its own caller already gave up on the timeout is
    simply dropped; `request_control`'s pop-on-timeout already removed
    the entry, so there's nothing left to wake)."""
    response = obj.get("response") if isinstance(obj.get("response"), dict) else None
    request_id = response.get("request_id") if response else None
    if not request_id:
        return
    with state.control_cond:
        waiter = state.control_waiters.get(request_id)
        if waiter is None:
            return
        waiter["response"] = response
        waiter["event"].set()
        state.control_cond.notify_all()


def request_control(state, subtype: str, *, request_id: Optional[str] = None,
                     timeout: float = _DEFAULT_TIMEOUT_S, **payload) -> Optional[dict]:
    """Sends one `control_request` and returns the inner `response` dict
    (success OR a well-formed error shape) -- None on a send failure, a
    timeout (mid-turn only), or the child hanging up with no reply
    (idle). See the module docstring for the two wait modes; the choice
    is made here, automatically, from `state.active_queue`."""
    request_id = request_id or _new_request_id()
    request = {"subtype": subtype}
    request.update(payload)
    mid_turn = False
    waiter: Optional[dict] = None
    with state.lock:
        mid_turn = state.active_queue is not None
        if mid_turn:
            waiter = {"event": threading.Event(), "response": None}
            state.control_waiters[request_id] = waiter
    try:
        state.process.send_control_request(request_id, request)
    except (BrokenPipeError, OSError):
        if mid_turn:
            with state.lock:
                state.control_waiters.pop(request_id, None)
        _mark_channel_result(state, subtype, None)
        return None
    if mid_turn:
        got = waiter["event"].wait(timeout=timeout)
        with state.lock:
            state.control_waiters.pop(request_id, None)
        response = waiter["response"] if got else None
    else:
        response = _read_idle_until_response(state, request_id, timeout=timeout)
    _mark_channel_result(state, subtype, response)
    return response


def _read_idle_until_response(state, request_id: str, *, timeout: float) -> Optional[dict]:
    """IDLE-mode wait -- see the module docstring's second bullet. A
    background thread does the one, unavoidably blocking (no portable
    read-with-timeout for a Windows pipe) `read_event()` call; THIS
    thread blocks on a bounded `queue.get(timeout=timeout)` instead, so
    a child that never answers at all (an old claude with no control
    channel, or the hermetic fake's own `FAKE_CLAUDE_CC_CONTROL=0`) can
    never hang the caller forever.

    On a genuine timeout the background thread is simply ABANDONED,
    never joined -- safe ONLY because the one caller of this path
    (`agent/cc_runtime.switch_model_live`) closes/kills this EXACT
    process the instant it gets None back (never reuses it), so the
    abandoned thread's own blocked read unblocks (EOF) the moment that
    kill happens and it exits on its own; it can never be confused with
    a LATER turn's reader, which always belongs to a freshly started
    process with its own, different stdout stream. A caller that cannot
    make that same guarantee must not use the idle path."""
    q: "queue.Queue" = queue.Queue(maxsize=1)

    def _read_one() -> None:
        try:
            q.put(state.process.read_event())
        except Exception:
            q.put(None)

    threading.Thread(target=_read_one, daemon=True, name="cc-control-idle-read").start()
    try:
        obj = q.get(timeout=timeout)
    except queue.Empty:
        return None
    if not isinstance(obj, dict) or obj.get("type") != "control_response":
        return None
    response = obj.get("response") or {}
    return response if response.get("request_id") == request_id else None


def forward_compact(session, *, trigger: str, turn_no: int, custom_instructions: Optional[str] = None):
    """Halo 2.0.5 round 1 (brief item H3, compaction). Live-verified
    against 2.1.291 (no real model auth needed for THIS path): `/compact`
    sent as a plain "user" stdin line is answered LOCALLY by claude
    itself -- a `system.status {"status": "compacting"}` line, then a
    terminal `system.status` carrying `compact_result` ("success" or
    "failed") and, on failure, `compact_error` (the exact live string
    for an early conversation: "Not enough messages to compact."),
    before the local command's own ordinary `assistant`+`result` pair.
    `docs/harness/CC-CONTROL-CHANNEL.md` has the full transcript.

    Only `trigger == "manual"` (`/compact`, `agent/loop.py`'s
    `_pump_compaction`) can ever reach a cc: session at all -- the
    "auto"/"overflow" triggers live inside the NATIVE turn loop's own
    pre-turn/retry checks, which `turn_body_cc` never calls into (Claude
    Code auto-compacts its own context on its own; that is unchanged and
    is not this function's concern). Never writes a `compacted` marker
    into halo's OWN log the way native compaction does -- there is
    nothing to splice: halo's log is a complete, passive RECORD for a
    cc: session (never replayed to the child the way `derive_request`
    replays it for every other route), so nothing is lost by NOT
    rewriting it, and pretending otherwise would mislead `/export` and
    every other reader of that log.

    Runs on the session's own WORKER thread with no turn active
    (`_pump_compaction`'s own contract) -- see the module docstring's
    IDLE-mode paragraph for why a direct, synchronous, un-timed read
    here is the right, consistent choice."""
    state = getattr(session, "_cc_state", None)
    if state is None or not state.process.alive:
        yield events.compaction(phase="failed", trigger=trigger, turn=turn_no,
                                  reason="cc: has no active Claude Code conversation yet to compact.")
        return False
    text = f"/compact {custom_instructions}" if custom_instructions else "/compact"
    try:
        state.process.send_user_line(text)
    except (BrokenPipeError, OSError) as e:
        yield events.compaction(phase="failed", trigger=trigger, turn=turn_no,
                                  reason=f"could not send /compact to Claude Code: {e}")
        return False
    yield events.compaction(phase="start", trigger=trigger, turn=turn_no)
    ok = False
    reason = "Claude Code never confirmed the compaction (the subprocess ended)"
    summary = None
    while True:
        obj = state.process.read_event()
        if obj is None:
            break
        if obj.get("type") == "system" and obj.get("subtype") == "status" and "compact_result" in obj:
            ok = obj.get("compact_result") == "success"
            summary = obj.get("compact_summary") or obj.get("summary")
            reason = obj.get("compact_error") or "compaction failed"
            continue
        if obj.get("type") == "result":
            break
    if ok:
        yield events.compaction(phase="done", trigger=trigger, turn=turn_no, summary=summary)
    else:
        yield events.compaction(phase="failed", trigger=trigger, turn=turn_no, reason=reason)
    return ok
